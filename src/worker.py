#!/usr/bin/env python3
import json
import logging
import os
import redis # type: ignore
import matplotlib # type: ignore
matplotlib.use("Agg")
import matplotlib.pyplot as plt # type: ignore
from jobs import JobStatus
from jobs import JobResult

from jobs import get_job_by_id
from jobs import q
from jobs import rd
from jobs import save_result
from jobs import start_job
from jobs import update_job_status

LOG_LEVEL = os.environ.get("LOG_LEVEL", "WARNING")
logging.basicConfig(level=LOG_LEVEL)

KEY_WEST_ID = "8724580"
LAKE_MICHIGAN_ID = "9087031"


#Get all water level readings in the requested date range
def get_readings_in_range(red_data: redis.Redis, start_date: str, end_date: str) -> list[dict]:
    readings_in_range = []

    for each in red_data.keys():
        reading_id = each.decode("utf-8")
        output = red_data.get(reading_id)

        if output is not None:
            reading = json.loads(output.decode("utf-8"))
            timestamp = reading.get("timestamp")

            if timestamp is None:
                continue

            reading_date = timestamp[0:10]

            if start_date <= reading_date <= end_date:
                readings_in_range.append(reading)

    return readings_in_range


#Gets readings for one station from a list of readings
def get_station_readings(readings: list[dict], station_id: str) -> list[dict]:
    station_readings = []

    for reading in readings:
        if reading.get("station_id") == station_id:
            station_readings.append(reading)

    return station_readings


#Gets average water level from readings
def get_average_water_level(readings: list[dict]) -> float | None:
    water_levels = []

    for reading in readings:
        water_level = reading.get("water_level")

        if water_level is not None:
            water_levels.append(water_level)

    if len(water_levels) == 0:
        return None

    return round(sum(water_levels) / len(water_levels), 3)


#Gets max water level from readings
def get_max_water_level(readings: list[dict]) -> float | None:
    water_levels = []

    for reading in readings:
        water_level = reading.get("water_level")

        if water_level is not None:
            water_levels.append(water_level)

    if len(water_levels) == 0:
        return None

    return max(water_levels)


#Gets min water level from readings
def get_min_water_level(readings: list[dict]) -> float | None:
    water_levels = []

    for reading in readings:
        water_level = reading.get("water_level")

        if water_level is not None:
            water_levels.append(water_level)

    if len(water_levels) == 0:
        return None

    return min(water_levels)


#Build plot and return plot file name
def build_plot(job_id: str, readings: list[dict]) -> str:
    key_west_readings = get_station_readings(readings, KEY_WEST_ID)
    lake_michigan_readings = get_station_readings(readings, LAKE_MICHIGAN_ID)

    key_west_times = []
    key_west_levels = []
    lake_michigan_times = []
    lake_michigan_levels = []

    key_west_average = get_average_water_level(key_west_readings)
    lake_michigan_average = get_average_water_level(lake_michigan_readings)

    for reading in key_west_readings:
        if reading.get("water_level") is not None and key_west_average is not None:
            key_west_times.append(reading.get("timestamp"))
            key_west_levels.append(reading.get("water_level") - key_west_average)

    for reading in lake_michigan_readings:
        if reading.get("water_level") is not None and lake_michigan_average is not None:
            lake_michigan_times.append(reading.get("timestamp"))
            lake_michigan_levels.append(reading.get("water_level") - lake_michigan_average)

    key_west_x = list(range(len(key_west_times)))
    lake_michigan_x = list(range(len(lake_michigan_times)))

    os.makedirs("/plots", exist_ok=True)
    plot_file = f"/plots/baywatch_plot_{job_id}.png"

    plt.figure()
    plt.plot(key_west_x, key_west_levels, label="Key West")
    plt.plot(lake_michigan_x, lake_michigan_levels, label="Lake Michigan")
    plt.legend()
    plt.xlabel("Hours Since Start Date")
    plt.ylabel("Water Level Change From Average (m)")
    plt.title("Hourly Water Level Variation Comparison")
    plt.tight_layout()
    plt.savefig(plot_file)
    plt.close()

    return plot_file


#Build final result object
def build_result(job_id: str, start_date: str, end_date: str, readings: list[dict]) -> JobResult:
    key_west_readings = get_station_readings(readings, KEY_WEST_ID)
    lake_michigan_readings = get_station_readings(readings, LAKE_MICHIGAN_ID)

    return JobResult(
        job_id = job_id,
        start_date = start_date,
        end_date = end_date,
        total_readings_found = len(readings),
        key_west_average = get_average_water_level(key_west_readings),
        lake_michigan_average = get_average_water_level(lake_michigan_readings),
        key_west_max = get_max_water_level(key_west_readings),
        lake_michigan_max = get_max_water_level(lake_michigan_readings),
        key_west_min = get_min_water_level(key_west_readings),
        lake_michigan_min = get_min_water_level(lake_michigan_readings),
        plot_file = build_plot(job_id, readings),
    )


#Worker checks queue and creates water level plot for each job
@q.worker
def do_work(job_id: str) -> None:
    logging.info("Worker got job")

    try:
        start_job(job_id)
        job = get_job_by_id(job_id)

        readings_in_range = get_readings_in_range(rd, job.start_date, job.end_date)
        result = build_result(job.job_id, job.start_date, job.end_date, readings_in_range)

        save_result(job_id, result)
        update_job_status(job_id, JobStatus.complete)

        logging.info(f"Completed job {job_id} with {result.total_readings_found} readings found")

    except KeyError:
        logging.error(f"Worker could not find job {job_id}")
    except Exception as e:
        logging.error(f"Worker failed job {job_id}: {e}")
        try:
            update_job_status(job_id, JobStatus.error)
        except KeyError:
            logging.error(f"Could not update error status for job {job_id}")


#Start worker when script is run
if __name__ == "__main__":
    do_work()
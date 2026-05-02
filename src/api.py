#!/usr/bin/env python3
import json
from datetime import datetime
from typing import Any
import redis  # type: ignore
import requests  # type: ignore
from fastapi import FastAPI  # type: ignore
from fastapi import HTTPException  # type: ignore
from pydantic import BaseModel  # type: ignore
from jobs import JobStatus, add_job
from jobs import get_job_by_id
from jobs import get_job_ids as get_saved_job_ids
from jobs import get_result_by_id
from jobs import rd
import logging
import os


LOG_LEVEL = os.environ.get("LOG_LEVEL", "WARNING")
logging.basicConfig(level=LOG_LEVEL)


app = FastAPI()

#JSON links for NOAA hourly water level data
KEY_WEST_URL = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?product=hourly_height&application=TideTrack&begin_date=20250101&end_date=20250107&datum=MLLW&station=8724580&time_zone=gmt&units=metric&format=json"
LAKE_MICHIGAN_URL = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?product=hourly_height&application=TideTrack&begin_date=20250101&end_date=20250107&datum=IGLD&station=9087031&time_zone=gmt&units=metric&format=json"

STATIONS = {
    "8724580": {
        "name": "Key West",
        "datum": "MLLW",
        "units": "metric",
        "url": KEY_WEST_URL,
    },
    "9087031": {
        "name": "Holland, MI",
        "datum": "IGLD",
        "units": "metric",
        "url": LAKE_MICHIGAN_URL,
    },
}


#BaseModel with the fields from the NOAA data
## Same idea as homework 8, sparse fields are optional w/ | None = None
class WaterLevel(BaseModel):
    reading_id: str
    station_id: str
    station_name: str
    latitude: str | None = None
    longitude: str | None = None
    timestamp: str
    water_level: float | None = None
    sigma: float | None = None
    flags: str | None = None
    datum: str | None = None
    units: str | None = None


#BaseModel for job input
class JobInput(BaseModel):
    start_date: str
    end_date: str


#Checks that input date is in YYYY-MM-DD format
def check_date(date: str) -> bool:
    try:
        datetime.strptime(date, "%Y-%m-%d")
        return True
    except ValueError:
        return False


#Turns NOAA string values into floats if possible
def safe_float(value: Any) -> float | None:
    if value is None or value == "":
        return None

    try:
        return float(value)
    except ValueError:
        return None


#Creates reading id from station id and timestamp
def build_reading_id(station_id: str, timestamp: str) -> str:
    clean_time = timestamp.replace(" ", "_").replace(":", "")
    return station_id + "_" + clean_time


#Load NOAA data from web with requests.get
def get_water_data(url: str) -> dict:
    output = requests.get(url, timeout=60)
    output.raise_for_status()

    return output.json()


#Build water level objects from the NOAA data
def build_water_levels(data: dict[str, Any], datum: str, units: str) -> list[WaterLevel]:
    metadata = data.get("metadata", {})
    readings_initial = data.get("data", [])
    readings = []

    station_id = metadata.get("id")
    station_name = metadata.get("name")

    if station_id is None or station_name is None:
        return readings

    for reading in readings_initial:
        timestamp = reading.get("t")

        #Need an id for Redis key, so skip if no timestamp
        if timestamp is None:
            continue

        readings.append(
            WaterLevel(
                reading_id=build_reading_id(station_id, timestamp),
                station_id=station_id,
                station_name=station_name,
                latitude=metadata.get("lat"),
                longitude=metadata.get("lon"),
                timestamp=timestamp,
                water_level=safe_float(reading.get("v")),
                sigma=safe_float(reading.get("s")),
                flags=reading.get("f"),
                datum=datum,
                units=units,
            )
        )

    return readings


#Get all reading IDs in Redis database and return list of strings
def get_reading_ids(red_data: redis.Redis) -> list[str]:
    reading_ids = []
    for key in red_data.keys():
        reading_ids.append(key.decode("utf-8"))

    return reading_ids


#Returns all readings in redis as list of dicts
def get_all_readings(red_data: redis.Redis) -> list[dict]:
    result = []

    for reading_id in get_reading_ids(red_data):
        output = red_data.get(reading_id)

        if output is not None:
            result.append(json.loads(output.decode("utf-8")))

    return result


#Find spec reading in Redis by reading ID and return dict
def find_reading(reading_id: str, red_data: redis.Redis) -> dict:
    output = red_data.get(reading_id)

    if output is None:
        raise HTTPException(status_code=404, detail=f"Didn't find reading {reading_id}")

    return json.loads(output.decode("utf-8"))


#Gets all station ids from the saved readings
def get_station_ids(red_data: redis.Redis) -> list[str]:
    station_ids = []

    for reading in get_all_readings(red_data):
        station_id = reading.get("station_id")

        if station_id is not None and station_id not in station_ids:
            station_ids.append(station_id)

    return station_ids


#Gets all readings for one station
def get_readings_by_station(station_id: str, red_data: redis.Redis) -> list[dict]:
    result = []

    for reading in get_all_readings(red_data):
        if reading.get("station_id") == station_id:
            result.append(reading)

    if len(result) == 0:
        raise HTTPException(status_code=404, detail=f"Didn't find station {station_id}")

    return result


#Explains all API routes
@app.get("/help")
def get_help() -> dict:
    return {
        "message": "BayWatch API for NOAA hourly water level data",
        "routes": {
            "POST /data": "Load Key West and Lake Michigan water level data into Redis",
            "GET /data": "Return all water level readings from Redis",
            "DELETE /data": "Delete all water level readings from Redis",
            "GET /stations": "Return all station ids currently loaded",
            "GET /stations/{station_id}": "Return all readings for one station id",
            "GET /readings/{reading_id}": "Return one specific water level reading",
            "POST /jobs": "Create a water level comparison plot job",
            "GET /jobs": "Return all saved job ids",
            "GET /jobs/{jobid}": "Return saved job info for one job id",
            "GET /results/{jobid}": "Return analysis result for one completed job",
        },
    }


#Posts NOAA data to Redis, deletes old data
@app.post("/data")
def post_data() -> dict:
    logging.info("POST /data called")

    try:
        # Clear old data before loading the new set
        for key in rd.keys():
            rd.delete(key)

        total_readings = 0
        station_counts = {}

        for station_id in STATIONS:
            station = STATIONS[station_id]
            data = get_water_data(station["url"])
            readings = build_water_levels(data, station["datum"], station["units"])

            station_counts[station_id] = len(readings)

            # Store each reading object in Redis using reading_id as the key
            for reading in readings:
                rd.set(reading.reading_id, json.dumps(reading.model_dump()))

            total_readings += len(readings)

        return {
            "message": "NOAA water level data loaded into Redis",
            "total_readings": total_readings,
            "station_counts": station_counts,
        }

    except requests.RequestException as e:
        logging.error(f"Could not download NOAA data: {e}")
        raise HTTPException(status_code=500, detail="Could not download NOAA data")


#Gets all data from Redis and returns readings in list of dicts
@app.get("/data")
def get_data() -> list[dict]:
    logging.info("GET /data called")
    return get_all_readings(rd)


#Deletes all data from Redis
@app.delete("/data")
def delete_data() -> dict:
    logging.info("DELETE /data called")
    reading_ids = get_reading_ids(rd)
    for reading_id in reading_ids:
        rd.delete(reading_id)

    return {"message": "NOAA water level data deleted from Redis"}


#Gets list of all station ids from Redis
@app.get("/stations")
def get_stations() -> list[str]:
    return get_station_ids(rd)


#Gets all readings for one station
@app.get("/stations/{station_id}")
def get_station(station_id: str) -> list[dict]:
    return get_readings_by_station(station_id, rd)


#Get singular water level object from Redis from reading ID
@app.get("/readings/{reading_id}")
def get_reading(reading_id: str) -> dict:
    return find_reading(reading_id, rd)


#Create new job and save job info in redis
@app.post("/jobs")
def post_job(job_input: JobInput) -> dict:
    if check_date(job_input.start_date) == False or check_date(job_input.end_date) == False:
        logging.warning("Invalid job input: dates are not in YYYY-MM-DD format")
        raise HTTPException(
            status_code=400,
            detail="Dates must be in YYYY-MM-DD format",
        )

    if job_input.start_date > job_input.end_date:
        logging.warning("Invalid job input: start_date greater than end_date")
        raise HTTPException(
            status_code=400,
            detail="start_date must be less than or equal to end_date",
        )

    job = add_job(job_input.start_date, job_input.end_date)
    return job.model_dump()


#Gets all saved job ids
@app.get("/jobs")
def get_jobs() -> list[str]:
    return get_saved_job_ids()


#Gets saved job info from id
@app.get("/jobs/{jobid}")
def get_job(jobid: str) -> dict:
    try:
        job = get_job_by_id(jobid)
        return job.model_dump()

    except KeyError:
        raise HTTPException(status_code=404, detail="Didn't find job")


#Gets analysis results for a specific job id
@app.get("/results/{jobid}")
def get_result(jobid: str) -> dict:

    try:
        job = get_job_by_id(jobid)
    except KeyError:
        logging.warning("Did not find job with this id for results route")
        raise HTTPException(status_code=404, detail="Didn't find job")

    if job.status != JobStatus.complete:
        return {"message": "Job is not complete yet"}

    try:
        result = get_result_by_id(jobid)
        return result.model_dump(mode="json")
    except KeyError:
        logging.warning("Didn't find result for completed job")
        raise HTTPException(status_code=404, detail="Didn't find result")
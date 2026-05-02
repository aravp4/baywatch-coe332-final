#!/usr/bin/env python3
from jobs import JobResult
from worker import build_result
from worker import get_average_water_level
from worker import get_max_water_level
from worker import get_min_water_level
from worker import get_station_readings


#Check station readings are filtered correctly
def test_get_station_readings():
    reading_test = [
        {"station_id": "8724580", "water_level": 1.0},
        {"station_id": "8724580", "water_level": 2.0},
        {"station_id": "9087031", "water_level": 3.0},
    ]

    result = get_station_readings(reading_test, "8724580")

    assert isinstance(result, list) == True
    assert len(result) == 2


#Check average water level calculation
def test_get_average_water_level():
    reading_test = [
        {"water_level": 1.0},
        {"water_level": 2.0},
        {"water_level": 3.0},
    ]

    result = get_average_water_level(reading_test)

    assert result == 2.0


#Check max and min water level calculations
def test_get_max_min_water_level():
    reading_test = [
        {"water_level": 1.0},
        {"water_level": 2.0},
        {"water_level": 3.0},
    ]

    assert get_max_water_level(reading_test) == 3.0
    assert get_min_water_level(reading_test) == 1.0


#Check that build_result creates a JobResult object w/ correct values
def test_build_result():
    reading_test = [
        {
            "reading_id": "8724580_2025-01-01_0000",
            "station_id": "8724580",
            "station_name": "Key West",
            "timestamp": "2025-01-01 00:00",
            "water_level": 1.0,
        },
        {
            "reading_id": "8724580_2025-01-01_0100",
            "station_id": "8724580",
            "station_name": "Key West",
            "timestamp": "2025-01-01 01:00",
            "water_level": 2.0,
        },
        {
            "reading_id": "9087031_2025-01-01_0000",
            "station_id": "9087031",
            "station_name": "Holland, MI",
            "timestamp": "2025-01-01 00:00",
            "water_level": 3.0,
        },
    ]

    result = build_result("a12345", "2025-01-01", "2025-01-07", reading_test)

    assert isinstance(result, JobResult) == True
    assert result.job_id == "a12345"
    assert result.start_date == "2025-01-01"
    assert result.end_date == "2025-01-07"
    
    assert result.total_readings_found == 3
    assert result.key_west_average == 1.5
    assert result.lake_michigan_average == 3.0
    assert isinstance(result.plot_file, str) == True
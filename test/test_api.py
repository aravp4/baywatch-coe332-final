#!/usr/bin/env python3
import requests

api_port = "http://127.0.0.1:8000"

response_help = requests.get(f"{api_port}/help")
response_data = requests.get(f"{api_port}/data")
response_stations = requests.get(f"{api_port}/stations")
response_jobs = requests.get(f"{api_port}/jobs")

valid_job = requests.post(
    f"{api_port}/jobs",
    json={"start_date": "2025-01-01", "end_date": "2025-01-07"},
)

#Check invalid entry w/ the start date bigger than the end date
invalid_job = requests.post(
    f"{api_port}/jobs",
    json={"start_date": "2025-01-07", "end_date": "2025-01-01"},
)


#Check help route works and returns a dict
def test_help_route():
    assert response_help.status_code == 200
    assert isinstance(response_help.json(), dict) == True


#Check the main routes work first for data/stations/jobs
def test_data_route():
    assert response_data.status_code == 200
    assert isinstance(response_data.json(), list) == True


def test_stations_route():
    assert response_stations.status_code == 200
    assert isinstance(response_stations.json(), list) == True


def test_jobs_route():
    assert response_jobs.status_code == 200
    assert isinstance(response_jobs.json(), list) == True


#Testing posting for both valid and invalid jobs w/ http codes and values
def test_post_jobs_valid():
    assert valid_job.status_code == 200
    assert isinstance(valid_job.json(), dict) == True

    #Check proper format for job object
    assert "job_id" in valid_job.json()
    assert "status" in valid_job.json()
    assert "start_date" in valid_job.json()
    assert "end_date" in valid_job.json()


#Invalid job should return a 400 level error
def test_post_jobs_invalid_range():
    assert invalid_job.status_code == 400
    assert isinstance(invalid_job.json(), dict) == True

    #Check that the error message is in the response for invalid job
    assert "detail" in invalid_job.json()
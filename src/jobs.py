#!/usr/bin/env python3
import json
import logging
import os
import uuid
from enum import Enum
import redis  # type: ignore
from hotqueue import HotQueue  # type: ignore
from pydantic import BaseModel  # type: ignore


LOG_LEVEL = os.environ.get("LOG_LEVEL", "WARNING")
logging.basicConfig(level=LOG_LEVEL)

_redis_ip = os.environ.get("REDIS_IP", "redis-db")
_redis_port = "6379"
rd = redis.Redis(host=_redis_ip, port=6379, db=0)
q = HotQueue("queue", host=_redis_ip, port=6379, db=1)
jdb = redis.Redis(host=_redis_ip, port=6379, db=2)
rdb = redis.Redis(host=_redis_ip, port=6379, db=3)


class JobStatus(str, Enum):
    queue = "queued"
    in_progress = "in_progress"
    complete = "complete"
    error = "error"


class Job(BaseModel):
    job_id: str
    status: JobStatus
    start_date: str
    end_date: str


class JobResult(BaseModel):
    job_id: str
    start_date: str
    end_date: str
    total_readings_found: int
    key_west_average: float | None = None
    lake_michigan_average: float | None = None
    key_west_max: float | None = None
    lake_michigan_max: float | None = None
    key_west_min: float | None = None
    lake_michigan_min: float | None = None
    plot_file: str


#Generate a unique job id
def _generate_job_id() -> str:
    return str(uuid.uuid4())


#Save job object in Redis jobs database
def save_job(job_id: str, job: Job) -> bool:
    jdb.set(job_id, json.dumps(job.model_dump(mode="json")))
    return True


#Put job id on the queue
def _queue_job(job_id: str) -> bool:
    q.put(job_id)
    return True


#Get a saved job w/ its id
def get_job_by_id(job_id: str) -> Job:
    output = jdb.get(job_id)

    if output is None:
        logging.warning("Did not find job w/ this id")
        raise KeyError("Didn't find job w/ that id")

    raw_data = json.loads(output.decode("utf-8"))
    return Job(**raw_data)


#Get all saved job ids
def get_job_ids() -> list[str]:
    job_ids = []
    for key in jdb.keys():
        job_ids.append(key.decode("utf-8"))

    return job_ids


#Create new job, save it, and queue it
def add_job(start_date: str, end_date: str) -> Job:
    job_id = _generate_job_id()
    job = Job(
        job_id = job_id,
        status = JobStatus.queue,
        start_date = start_date,
        end_date = end_date,
    )
    save_job(job_id, job)
    _queue_job(job_id)
    return job


#Update job to in_progress after starting
def start_job(job_id: str) -> bool:
    job = get_job_by_id(job_id)
    job.status = JobStatus.in_progress
    return save_job(job_id, job)


#Update saved job status
def update_job_status(job_id: str, status: JobStatus) -> bool:
    job = get_job_by_id(job_id)
    job.status = status
    return save_job(job_id, job)


#Save result in Redis db
def save_result(job_id: str, result: JobResult) -> bool:
    rdb.set(job_id, json.dumps(result.model_dump(mode="json")))
    return True


#Get a result w/ its id
def get_result_by_id(job_id: str) -> JobResult:
    output = rdb.get(job_id)

    if output is None:
        logging.warning("Did not find result for job")
        raise KeyError("Didn't find result w/ that id")

    res = json.loads(output.decode("utf-8"))
    return JobResult(**res)
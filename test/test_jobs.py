#!/usr/bin/env python3
from jobs import JobStatus
from jobs import _generate_job_id


#Check if generate_job_id returns a string for the job id
def test_generate_job_id_type():
    job_id = _generate_job_id()
    assert isinstance(job_id, str) == True


#Check if generated job id isn't empty
def test_generate_job_id_unique():
    job_id_1 = _generate_job_id()
    job_id_2 = _generate_job_id()
    assert (job_id_1 != job_id_2)


#Checking job status values match strings
def test_job_status_values():
    assert JobStatus.queue.value == "queued"
    assert JobStatus.in_progress.value == "in_progress"
    assert JobStatus.complete.value == "complete"
    assert JobStatus.error.value == "error"
import sys
import os

# this is needed to import classes from other modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

import time
from client.vectorflow import Vectorflow

vectorflow = Vectorflow()
filepath = './src/api/tests/fixtures/test_medium_text.txt'

# Test Single File Embed
response = vectorflow.embed(filepath)
if response.status_code == 500:
    exit(0)

response_json = response.json()
job_id = response_json['JobID']
print(f"Job ID: {job_id}")

job_status = None
count = 0
while job_status != "COMPLETED" and job_status != "FAILED" and count < 10:
    print(f"fetching job status for job {job_id}")
    response = vectorflow.get_job_status(job_id)
    response_json = response.json()
    job_status = response_json['JobStatus']
    count += 1
    time.sleep(3)

print(f"Job status: {job_status}")
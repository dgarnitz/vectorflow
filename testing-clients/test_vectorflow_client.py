import sys
import os

# this is needed to import classes from other modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

import time
from client.vectorflow import Vectorflow

vectorflow = Vectorflow()
vectorflow.embeddings_api_key = os.getenv("OPEN_AI_KEY")

##########################
# Test Single File Embed #
##########################

filepath = './src/api/tests/fixtures/test_medium_text.txt'
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

##########################
# Test Streaming Upload ##
##########################
paths = ['./src/api/tests/fixtures/test_pdf.pdf','./src/api/tests/fixtures/test_medium_text.txt','./src/api/tests/fixtures/test_medium_text.txt']
response = vectorflow.upload(paths)
if response.status_code == 500:
    exit(0)

response_json = response.json()
print(response_json)

if "successful_uploads" in response_json and len(response_json["successful_uploads"]) > 0:
    jobs_ids = [v for _,v in response_json["successful_uploads"].items()]
    
    time.sleep(5) # wait for processing to complete 
    response = vectorflow.get_job_statuses(jobs_ids)
    print(response)
    json_response = response.json()
    print(json_response)

    time.sleep(5) # wait for processing to complete 
    response = vectorflow.get_job_statuses(jobs_ids)
    print(response)
    json_response = response.json()
    print(json_response)

    time.sleep(5) # wait for processing to complete 
    response = vectorflow.get_job_statuses(jobs_ids)
    print(response)
    json_response = response.json()
    print(json_response)

    time.sleep(5) # wait for processing to complete 
    response = vectorflow.get_job_statuses(jobs_ids)
    print(response)
    json_response = response.json()
    print(json_response)
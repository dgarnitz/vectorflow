import sys
import os

# this is needed to import classes from other modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

import time
from client.src.vectorflow_client.vectorflow import Vectorflow

vectorflow = Vectorflow()
vectorflow.embeddings_api_key = os.getenv("OPEN_AI_KEY")

##########################
# Test Single File Embed #
##########################

filepath = './src/api/tests/fixtures/test_medium_text.txt'
embed_response = vectorflow.embed(filepath)
if embed_response.status_code >= 400:
    print(f"request failed with status code: {embed_response.status_code}")
    if embed_response.message:
        print(f"message: {embed_response.message}")
    if embed_response.error:
        print(f"error: {embed_response.error}")
    exit(0)

print(f"Job ID: {embed_response.job_id}")

job_status = None
count = 0
while job_status != "COMPLETED" and job_status != "FAILED" and count < 10:
    print(f"fetching job status for job {embed_response.job_id}")
    status_response = vectorflow.get_job_status(embed_response.job_id)
    job_status = status_response.job_status
    count += 1
    time.sleep(3)

print(f"Job status: {job_status}")

##########################
# Test Streaming Upload ##
##########################
paths = ['./src/api/tests/fixtures/test_pdf.pdf','./src/api/tests/fixtures/test_medium_text.txt','./src/api/tests/fixtures/test_medium_text.txt']
streaming_response = vectorflow.upload(paths)
if streaming_response.status_code == 500:
    exit(0)

print(streaming_response)

if streaming_response.successful_uploads and len(streaming_response.successful_uploads) > 0:
    jobs_ids = [job.job_id for job in streaming_response.successful_uploads]
    
    time.sleep(5) # wait for processing to complete 
    response = vectorflow.get_job_statuses(jobs_ids)
    print(response)

    time.sleep(5) # wait for processing to complete 
    response = vectorflow.get_job_statuses(jobs_ids)
    print(response)

    time.sleep(5) # wait for processing to complete 
    response = vectorflow.get_job_statuses(jobs_ids)
    print(response)

    time.sleep(5) # wait for processing to complete 
    response = vectorflow.get_job_statuses(jobs_ids)
    print(response)
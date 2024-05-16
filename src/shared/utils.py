import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))
import uuid
import requests
import json
import logging
from services.database.database import get_db, safe_db_operation
import services.database.job_service as job_service
from shared.job_status import JobStatus
import services.database.batch_service as batch_service

def generate_uuid_from_tuple(t, namespace_uuid='6ba7b810-9dad-11d1-80b4-00c04fd430c8'):
    namespace = uuid.UUID(namespace_uuid)
    name = "-".join(map(str, t))
    unique_uuid = uuid.uuid5(namespace, name)

    return str(unique_uuid)

def str_to_bool(value):
    return str(value).lower() in ["true", "1", "yes"]

def send_embeddings_to_webhook(embedded_chunks: list[dict], job):
    headers = {
        "X-Embeddings-Webhook-Key": job.webhook_key,
        "Content-Type": "application/json"
    }
    
    data = {
        'Embeddings': embedded_chunks,
        'DocumentID': job.document_id if (hasattr(job, 'document_id') and job.document_id) else "",
        'JobID': job.id
    }

    response = requests.post(
        job.webhook_url, 
        headers=headers, 
        json=data
    )

    return response


def update_batch_and_job_status(job_id, batch_status, batch_id):
    try:
        if not job_id and batch_id:
            job = safe_db_operation(batch_service.get_batch, batch_id)
            job_id = job.job_id
        updated_batch_status = safe_db_operation(batch_service.update_batch_status, batch_id, batch_status)
        job = safe_db_operation(job_service.update_job_with_batch, job_id, updated_batch_status)
        if job.job_status == JobStatus.COMPLETED:
            logging.info(f"Job {job_id} completed successfully")
        elif job.job_status == JobStatus.PARTIALLY_COMPLETED:
            logging.info(f"Job {job_id} partially completed. {job.batches_succeeded} out of {job.total_batches} batches succeeded")
        elif job.job_status == JobStatus.FAILED:
            logging.info(f"Job {job_id} failed. {job.batches_succeeded} out of {job.total_batches} batches succeeded")
                
    except Exception as e:
        logging.error('Error updating job and batch status: %s', e)
        safe_db_operation(job_service.update_job_status, job_id, JobStatus.FAILED)    



def update_batch_status(job_id, batch_status, batch_id, retries = None, bypass_retries=False):
    try:
        updated_batch_status = safe_db_operation(batch_service.update_batch_status, batch_id, batch_status)
        logging.info(f"Status for batch {batch_id} as part of job {job_id} updated to {updated_batch_status}") 
        if updated_batch_status == BatchStatus.FAILED and (retries == config.MAX_BATCH_RETRIES or bypass_retries):
            logging.info(f"Batch {batch_id} failed. Updating job status.")
            update_batch_and_job_status(job_id, BatchStatus.FAILED, batch_id)     
    except Exception as e:
        logging.error('Error updating batch status: %s', e)



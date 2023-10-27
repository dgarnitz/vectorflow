import uuid
import requests
import json
import logging
import batch_service
from job_service import JobStatus, job_service
import safe_db_operation



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

    except Exception as e:
        logging.error('Error updating job and batch status: %s', e)
        safe_db_operation(job_service.update_job_status, job_id, JobStatus.FAILED)

import uuid
import requests
import json

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
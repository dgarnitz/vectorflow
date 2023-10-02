import uuid
import requests

def generate_uuid_from_tuple(t, namespace_uuid='6ba7b810-9dad-11d1-80b4-00c04fd430c8'):
    namespace = uuid.UUID(namespace_uuid)
    name = "-".join(map(str, t))
    unique_uuid = uuid.uuid5(namespace, name)

    return str(unique_uuid)

def str_to_bool(value):
    return str(value).lower() in ["true", "1", "yes"]

def send_embeddings_to_webhook(text_embeddings_list, job):
    headers = {
        "X-Embeddings-Webhook-Key": job.webhook_key,
        "Content-Type": "application/json"
    }

    # text_embeddings_list is list[(str, list[float])], should serialize automatically without json.dumps()
    data = {
        'Embeddings': text_embeddings_list,
        'DocumentID': job.document_id,
        'JobID': job.id
    }

    response = requests.post(
        job.webhook_url, 
        headers=headers, 
        json=data
    )

    return response
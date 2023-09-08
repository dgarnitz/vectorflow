import sys
import os

# this is needed to import classes from the API. it will be removed when the worker is refactored
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

import ssl
import time
import pika
import json
import openai
import pinecone
import requests 
import logging
import uuid
import weaviate
import worker.config as config
import services.database.batch_service as batch_service
import services.database.job_service as job_service
from services.database.database import get_db
from shared.job_status import JobStatus
from shared.batch_status import BatchStatus
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct
from pymilvus import Collection, connections
from shared.embeddings_type import EmbeddingsType
from shared.vector_db_type import VectorDBType

logging.basicConfig(filename='./vdb-upload-log.txt', level=logging.INFO)
logging.basicConfig(filename='./vdb-upload-errors.txt', level=logging.ERROR)

def upload_batch(batch_id, text_embeddings_list):
    with get_db() as db:
        batch = batch_service.get_batch(db, batch_id)
        
        if batch.batch_status == BatchStatus.EMBEDDING_COMPLETE:
            batch_service.update_batch_status(db, batch.id, BatchStatus.VDB_UPLOAD)
        else:
            batch_service.update_batch_retry_count(db, batch.id, batch.retries+1)
            logging.info(f"Retrying vector db upload of batch {batch.id}")

        db.refresh(batch)

        vectors_uploaded = write_embeddings_to_vector_db(text_embeddings_list, batch.vector_db_metadata, batch.id, batch.job_id)
    
    if vectors_uploaded:
        update_batch_and_job_status(batch.job_id, BatchStatus.COMPLETED, batch.id)
    else:
        update_batch_and_job_status(batch.job_id, BatchStatus.FAILED, batch.id)

def write_embeddings_to_vector_db(text_embeddings_list, vector_db_metadata, batch_id, job_id):
    if vector_db_metadata.vector_db_type == VectorDBType.PINECONE:
        upsert_list = create_pinecone_source_chunk_dict(text_embeddings_list, batch_id, job_id)
        return write_embeddings_to_pinecone(upsert_list, vector_db_metadata)
    elif vector_db_metadata.vector_db_type == VectorDBType.QDRANT:
        upsert_list = create_qdrant_source_chunk_dict(text_embeddings_list, batch_id, job_id)
        return write_embeddings_to_qdrant(upsert_list, vector_db_metadata)
    elif vector_db_metadata.vector_db_type == VectorDBType.WEAVIATE:
        return write_embeddings_to_weaviate(text_embeddings_list, vector_db_metadata, batch_id, job_id)
    elif vector_db_metadata.vector_db_type == VectorDBType.MILVUS:
        upsert_list = create_milvus_source_chunk_dict(text_embeddings_list, batch_id, job_id)
        return write_embeddings_to_milvus(upsert_list, vector_db_metadata)
    else:
        logging.error('Unsupported vector DB type:', vector_db_metadata.vector_db_type)

def create_pinecone_source_chunk_dict(text_embeddings_list, batch_id, job_id):
    upsert_list = []
    for i, (source_text, embedding) in enumerate(text_embeddings_list):
        upsert_list.append(
            {"id": generate_uuid_from_tuple((job_id, batch_id, i)), 
            "values": embedding, 
            "metadata": {"source_text": source_text}})
    return upsert_list

def write_embeddings_to_pinecone(upsert_list, vector_db_metadata):
    pinecone_api_key = os.getenv('VECTOR_DB_KEY')
    pinecone.init(api_key=pinecone_api_key, environment=vector_db_metadata.environment)
    index = pinecone.Index(vector_db_metadata.index_name)
    if not index:
        logging.error(f"Index {vector_db_metadata.index_name} does not exist in environment {vector_db_metadata.environment}")
        return None
    
    logging.info(f"Starting pinecone upsert for {len(upsert_list)} vectors")

    batch_size = config.PINECONE_BATCH_SIZE
    vectors_uploaded = 0

    for i in range(0,len(upsert_list), batch_size):
        try:
            upsert_response = index.upsert(vectors=upsert_list[i:i+batch_size])
            vectors_uploaded += upsert_response["upserted_count"]
        except Exception as e:
            logging.error('Error writing embeddings to pinecone:', e)
            return None
    
    logging.info(f"Successfully uploaded {vectors_uploaded} vectors to pinecone")
    return vectors_uploaded

def generate_uuid_from_tuple(t, namespace_uuid='6ba7b810-9dad-11d1-80b4-00c04fd430c8'):
    namespace = uuid.UUID(namespace_uuid)
    name = "-".join(map(str, t))
    unique_uuid = uuid.uuid5(namespace, name)

    return str(unique_uuid)

def create_qdrant_source_chunk_dict(text_embeddings_list, batch_id, job_id):
    upsert_list = []
    for i, (source_text, embedding) in enumerate(text_embeddings_list):
        upsert_list.append(
            PointStruct(
                id=generate_uuid_from_tuple((job_id, batch_id, i)),
                vector=embedding,
                payload={"source_text": source_text}
            )
        )
    return upsert_list

def write_embeddings_to_qdrant(upsert_list, vector_db_metadata):
    qdrant_client = QdrantClient(
        url=vector_db_metadata.environment, 
        api_key=os.getenv('VECTOR_DB_KEY'),
        grpc_port=6334, 
        prefer_grpc=True,
        timeout=5
    ) if vector_db_metadata.environment != os.getenv('LOCAL_VECTOR_DB') else QdrantClient(os.getenv('LOCAL_VECTOR_DB'), port=6333)

    index = qdrant_client.get_collection(collection_name=vector_db_metadata.index_name)
    if not index:
        logging.error(f"Collection {vector_db_metadata.index_name} does not exist at cluster URL {vector_db_metadata.environment}")
        return None
    
    logging.info(f"Starting qdrant upsert for {len(upsert_list)} vectors")

    batch_size = config.PINECONE_BATCH_SIZE

    for i in range(0, len(upsert_list), batch_size):
        try:
            qdrant_client.upsert(
                collection_name=vector_db_metadata.index_name,
                points=upsert_list[i:i+batch_size]
            )
        except Exception as e:
            logging.error('Error writing embeddings to qdrant:', e)
            return None
    
    logging.info(f"Successfully uploaded {len(upsert_list)} vectors to qdrant")
    return len(upsert_list)
    
def write_embeddings_to_weaviate(text_embeddings_list, vector_db_metadata,  batch_id, job_id):
    client = weaviate.Client(
        url=vector_db_metadata.environment,
        auth_client_secret=weaviate.AuthApiKey(api_key=os.getenv('VECTOR_DB_KEY')),
    )

    index = client.schema.get()
    class_list = [class_dict["class"] for class_dict in index["classes"]]
    if not index or not vector_db_metadata.index_name in class_list:
        logging.error(f"Collection {vector_db_metadata.index_name} does not exist at cluster URL {vector_db_metadata.environment}")
        return None
    
    logging.info(f"Starting Weaviate upsert for {len(text_embeddings_list)} vectors")
    try:
        with client.batch(batch_size=config.PINECONE_BATCH_SIZE, dynamic=True, num_workers=2) as batch:
            for i, (text, vector) in enumerate(text_embeddings_list):
                properties = {
                    "source_data": text,
                    "vectoflow_id": generate_uuid_from_tuple((job_id, batch_id, i))
                }

                client.batch.add_data_object(
                    properties,
                    vector_db_metadata.index_name,
                    vector=vector
                )
    except Exception as e:
        logging.error('Error writing embeddings to weaviate:', e)
        return None
    
    logging.info(f"Successfully uploaded {len(text_embeddings_list)} vectors to Weaviate")
    return len(text_embeddings_list)

def create_milvus_source_chunk_dict(text_embeddings_list, batch_id, job_id):
    ids = []
    source_texts = []
    embeddings = []
    for i, (source_text, embedding) in enumerate(text_embeddings_list):
        ids.append(generate_uuid_from_tuple((job_id, batch_id, i)))
        source_texts.append(source_text)
        embeddings.append(embedding)
    return [ids, source_texts, embeddings]

def write_embeddings_to_milvus(upsert_list, vector_db_metadata):
    connections.connect("default", 
        uri = vector_db_metadata.environment,
        token = os.getenv('VECTOR_DB_KEY')
    )

    collection = Collection(vector_db_metadata.index_name)
    if not collection:
        logging.error(f"Index {vector_db_metadata.index_name} does not exist in environment {vector_db_metadata.environment}")
        return None
    
    logging.info(f"Starting Milvus insert for {len(upsert_list)} vectors")
    batch_size = config.PINECONE_BATCH_SIZE
    vectors_uploaded = 0

    for i in range(0,len(upsert_list), batch_size):
        try:
            insert_response = collection.insert(upsert_list[i:i+batch_size])
            vectors_uploaded += insert_response.insert_count
        except Exception as e:
            logging.error('Error writing embeddings to milvus:', e)
            return None
    
    logging.info(f"Successfully uploaded {vectors_uploaded} vectors to milvus")
    return vectors_uploaded

def update_batch_and_job_status(job_id, batch_status, batch_id):
    try:
        with get_db() as db:
            updated_batch_status = batch_service.update_batch_status(db, batch_id, batch_status)
            job = job_service.update_job_with_batch(db, job_id, updated_batch_status)
            if job.job_status == JobStatus.COMPLETED:
                logging.info(f"Job {job_id} completed successfully")
            elif job.job_status == JobStatus.PARTIALLY_COMPLETED:
                logging.info(f"Job {job_id} partially completed. {job.batches_succeeded} out of {job.total_batches} batches succeeded")
                
    except Exception as e:
        logging.error('Error updating job and batch status:', e)

def callback(ch, method, properties, body):
    try:
        data = json.loads(body)
        batch_id, text_embeddings_list, vector_db_key = data
        os.environ["VECTOR_DB_KEY"] = vector_db_key

        logging.info("Batch retrieved successfully")
        upload_batch(batch_id, text_embeddings_list)
        logging.info("Batch processed successfully")
    except Exception as e:
        logging.error('Error processing batch:', e)

    ch.basic_ack(delivery_tag=method.delivery_tag)

def start_connection():
    while True:
        try:
            credentials = pika.PlainCredentials(os.getenv('RABBITMQ_USERNAME'), os.getenv('RABBITMQ_PASSWORD'))

            connection_params = pika.ConnectionParameters(
                host=os.getenv('RABBITMQ_HOST'),
                credentials=credentials,
                port=os.getenv('RABBITMQ_PORT'),
                heartbeat=600,
                ssl_options=pika.SSLOptions(ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)),
                virtual_host="/"
            ) if os.getenv('RABBITMQ_PORT') == "5671" else pika.ConnectionParameters(
                host=os.getenv('RABBITMQ_HOST'),
                credentials=credentials,
                heartbeat=600,
            )

            connection = pika.BlockingConnection(connection_params)
            channel = connection.channel()

            queue_name = os.getenv('VDB_UPLOAD_QUEUE')
            channel.queue_declare(queue=queue_name)

            channel.basic_consume(queue=queue_name, on_message_callback=callback)

            logging.info('Waiting for messages.')
            channel.start_consuming()
            
        except Exception as e:
            logging.error('ERROR connecting to RabbitMQ, retrying now. See exception:', e)
            time.sleep(config.PIKA_RETRY_INTERVAL) # Wait before retrying

if __name__ == "__main__":
    start_connection()
 
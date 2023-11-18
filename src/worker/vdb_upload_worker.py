import sys
import os

# this is needed to import classes from the API. it will be removed when the worker is refactored
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

import time
import pika
import json
import pinecone
import logging
import weaviate
import redis
import lancedb
import pymongo
import pyarrow as pa
import numpy as np
import worker.config as config
import services.database.batch_service as batch_service
import services.database.job_service as job_service
from services.database.database import get_db, safe_db_operation
from shared.job_status import JobStatus
from shared.batch_status import BatchStatus
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct
from pymilvus import Collection, connections
from shared.embeddings_type import EmbeddingsType
from shared.vector_db_type import VectorDBType
from shared.utils import generate_uuid_from_tuple
from urllib.parse import quote_plus
from services.rabbitmq.rabbit_service import create_connection_params
from pika.exceptions import AMQPConnectionError

logging.basicConfig(filename='./vdb-log.txt', level=logging.INFO)
logging.basicConfig(filename='./vdb-errors.txt', level=logging.ERROR)

def upload_batch(batch_id, chunks_with_embeddings):
    batch = safe_db_operation(batch_service.get_batch, batch_id)
    if batch.batch_status == BatchStatus.FAILED:
        safe_db_operation(batch_service.update_batch_retry_count, batch.id, batch.retries+1)
        logging.info(f"Retrying vector db upload of batch {batch.id}")

    batch = safe_db_operation(batch_service.get_batch, batch_id)
    vectors_uploaded = write_embeddings_to_vector_db(chunks_with_embeddings, batch.vector_db_metadata, batch.id, batch.job_id)

    if vectors_uploaded:
        status = safe_db_operation(batch_service.update_batch_status_with_successful_minibatch, batch.id)
        update_batch_and_job_status(batch.job_id, status, batch.id)
    else:
        update_batch_and_job_status(batch.job_id, BatchStatus.FAILED, batch.id)

def write_embeddings_to_vector_db(chunks, vector_db_metadata, batch_id, job_id):
    # NOTE: the legacy code expects a list of tuples, (text_chunk, embedding) of form (str, list[float])
    text_embeddings_list = [(chunk['text'], chunk['vector']) for chunk in chunks]
    
    job = safe_db_operation(job_service.get_job, job_id)
    source_filename = job.source_filename
    
    if vector_db_metadata.vector_db_type == VectorDBType.PINECONE:
        upsert_list = create_pinecone_source_chunk_dict(text_embeddings_list, batch_id, job_id, source_filename)
        return write_embeddings_to_pinecone(upsert_list, vector_db_metadata)
    elif vector_db_metadata.vector_db_type == VectorDBType.QDRANT:
        upsert_list = create_qdrant_source_chunk_dict(text_embeddings_list, batch_id, job_id, source_filename)
        return write_embeddings_to_qdrant(upsert_list, vector_db_metadata)
    elif vector_db_metadata.vector_db_type == VectorDBType.WEAVIATE:
        return write_embeddings_to_weaviate(text_embeddings_list, vector_db_metadata, batch_id, job_id, source_filename)
    elif vector_db_metadata.vector_db_type == VectorDBType.MILVUS:
        upsert_list = create_milvus_source_chunk_dict(text_embeddings_list, batch_id, job_id, source_filename)
        return write_embeddings_to_milvus(upsert_list, vector_db_metadata)
    elif vector_db_metadata.vector_db_type == VectorDBType.REDIS:
        upsert_list = create_redis_source_chunk_dict(text_embeddings_list, batch_id, job_id, source_filename)
        return write_embeddings_to_redis(upsert_list, vector_db_metadata)
    elif vector_db_metadata.vector_db_type == VectorDBType.LANCEDB:
        upsert_list = create_lancedb_source_chunks(text_embeddings_list, batch_id, job_id, source_filename)
        return write_embeddings_to_lancedb(upsert_list, batch_id)
    elif vector_db_metadata.vector_db_type == VectorDBType.MONGODB:
        upsert_list = create_mongodb_source_chunk_dict(text_embeddings_list, batch_id, job_id, source_filename)
        return write_embeddings_to_mongodb(upsert_list, vector_db_metadata)
    else:
        logging.error('Unsupported vector DB type: %s', vector_db_metadata.vector_db_type.value)

def create_mongodb_source_chunk_dict(text_embeddings_list, batch_id, job_id, source_filename):
    upsert_list = []
    for i, (source_text, embedding) in enumerate(text_embeddings_list):
        upsert_list.append(
            {"_id": generate_uuid_from_tuple((job_id, batch_id, i)), 
            "values": embedding, 
            "source_text": source_text,
            "source_document": source_filename
            })
    return upsert_list

def write_embeddings_to_mongodb(upsert_list, vector_db_metadata):
    mongo_conn_uri = vector_db_metadata.environment
    mongo_password = quote_plus(os.getenv('VECTOR_DB_KEY'))
    mongo_conn_uri = mongo_conn_uri.replace("<password>", mongo_password)

    mongo_client = pymongo.MongoClient(mongo_conn_uri)
    db_name, collection = vector_db_metadata.index_name.split(".")
    db = mongo_client[db_name]

    try:
        db.command("ping")
    except Exception as e:
        logging.error(f"Error connecting to MongoDB via python client: {e}")
        return None

    if collection not in db.list_collection_names():
        logging.error(f"Index {vector_db_metadata.index_name} does not exist in environment {vector_db_metadata.environment}")
        return None
    
    index = db.get_collection(collection)
    
    logging.info(f"Starting MongoDB upsert for {len(upsert_list)} vectors")

    batch_size = config.PINECONE_BATCH_SIZE
    vectors_uploaded = 0

    for i in range(0,len(upsert_list), batch_size):
        try:
            upsert_batch = upsert_list[i:i+batch_size]
            upsert_response = index.insert_many(upsert_batch)
            vectors_uploaded += len(upsert_batch)
        except Exception as e:
            logging.error('Error writing embeddings to Mongo:', e)
            return None
    
    logging.info(f"Successfully uploaded {vectors_uploaded} vectors to MongoDB")
    return vectors_uploaded

def create_pinecone_source_chunk_dict(text_embeddings_list, batch_id, job_id, source_filename):
    upsert_list = []
    for i, (source_text, embedding) in enumerate(text_embeddings_list):
        upsert_list.append(
            {"id": generate_uuid_from_tuple((job_id, batch_id, i)), 
            "values": embedding, 
            "metadata": {"source_text": source_text, "source_document": source_filename}})
    return upsert_list

def write_embeddings_to_pinecone(upsert_list, vector_db_metadata):
    pinecone_api_key = os.getenv('VECTOR_DB_KEY')
    pinecone.init(api_key=pinecone_api_key, environment=vector_db_metadata.environment)
    index = pinecone.GRPCIndex(vector_db_metadata.index_name)
    if not index:
        logging.error(f"Index {vector_db_metadata.index_name} does not exist in environment {vector_db_metadata.environment}")
        return None
    
    logging.info(f"Starting pinecone upsert for {len(upsert_list)} vectors")

    batch_size = config.PINECONE_BATCH_SIZE
    vectors_uploaded = 0

    for i in range(0,len(upsert_list), batch_size):
        try:
            upsert_response = index.upsert(vectors=upsert_list[i:i+batch_size])
            vectors_uploaded += upsert_response.upserted_count
        except Exception as e:
            logging.error('Error writing embeddings to pinecone:', e)
            return None
    
    logging.info(f"Successfully uploaded {vectors_uploaded} vectors to pinecone")
    return vectors_uploaded

def create_redis_source_chunk_dict(text_embeddings_list, batch_id, job_id, source_filename):
    ids = []
    source_texts = []
    source_documents = []
    embeddings = []

    for i, (source_text, embedding) in enumerate(text_embeddings_list):
        ids.append(generate_uuid_from_tuple((job_id, batch_id, i)))
        source_texts.append(source_text)
        embeddings.append(embedding)
        source_documents.append(source_filename)

    return [ids, source_texts, embeddings, source_documents]

def write_embeddings_to_redis(upsert_list, vector_db_metadata):
    redis_client = redis.from_url(url=vector_db_metadata.environment, password=os.getenv('VECTOR_DB_KEY'), decode_responses=True)
    
    try:
        redis_client.ft(vector_db_metadata.index_name).info()
    except redis.exceptions.ResponseError as e:
        if "Unknown Index name" in str(e):
            logging.error(f"Index {vector_db_metadata.index_name} does not exist at redis URL {vector_db_metadata.environment}")
            return None
    
    logging.info(f"Starting redis upsert for {len(upsert_list)} vectors")

    redis_pipeline = redis_client.pipeline()

    for i in range(0,len(upsert_list[0])):
        key = f'{vector_db_metadata.collection}:{upsert_list[0][i]}'
        obj = {"source_data": upsert_list[1][i], "embeddings": np.array(upsert_list[2][i]).tobytes(), "source_document": upsert_list[3][i]}

        redis_pipeline.hset(key, mapping=obj)

    res = redis_pipeline.execute()

    logging.info(f"Successfully uploaded {len(res)} vectors to redis")
    return len(res)

def create_qdrant_source_chunk_dict(text_embeddings_list, batch_id, job_id, source_filename):
    upsert_list = []
    for i, (source_text, embedding) in enumerate(text_embeddings_list):
        upsert_list.append(
            PointStruct(
                id=generate_uuid_from_tuple((job_id, batch_id, i)),
                vector=embedding,
                payload={"source_text": source_text, "source_document": source_filename}
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

def write_embeddings_to_weaviate(text_embeddings_list, vector_db_metadata,  batch_id, job_id, source_filename):
    client = weaviate.Client(
        url=vector_db_metadata.environment,
        auth_client_secret=weaviate.AuthApiKey(api_key=os.getenv('VECTOR_DB_KEY')),
    ) if vector_db_metadata.environment != os.getenv('LOCAL_VECTOR_DB') else weaviate.Client(url=vector_db_metadata.environment)

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
                    "vectoflow_id": generate_uuid_from_tuple((job_id, batch_id, i)),
                    "source_document": source_filename
                }

                client.batch.add_data_object(
                    properties,
                    vector_db_metadata.index_name,
                    vector=vector
                )
    except Exception as e:
        logging.error('Error writing embeddings to weaviate: %s', e)
        return None
    
    logging.info(f"Successfully uploaded {len(text_embeddings_list)} vectors to Weaviate")
    return len(text_embeddings_list)

def create_milvus_source_chunk_dict(text_embeddings_list, batch_id, job_id, source_filename):
    ids = []
    source_texts = []
    embeddings = []
    source_filenames = []
    for i, (source_text, embedding) in enumerate(text_embeddings_list):
        ids.append(generate_uuid_from_tuple((job_id, batch_id, i)))
        source_texts.append(source_text)
        embeddings.append(embedding)
        source_filenames.append(source_filename)
    return [ids, source_texts, embeddings, source_filenames]

def write_embeddings_to_milvus(upsert_list, vector_db_metadata):
    if vector_db_metadata.environment != os.getenv('LOCAL_VECTOR_DB'):
        connections.connect("default", 
            uri = vector_db_metadata.environment,
            token = os.getenv('VECTOR_DB_KEY')
        )
    else:
        connections.connect("default", 
            host = vector_db_metadata.environment
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
            logging.error('Error writing embeddings to milvus: %s', e)
            return None
    
    logging.info(f"Successfully uploaded {vectors_uploaded} vectors to milvus")
    return vectors_uploaded

def create_lancedb_source_chunks(text_embeddings_list, batch_id, job_id, source_filename):
    upsert_list = []
    for i, (source_text, embedding) in enumerate(text_embeddings_list):
        upsert_list.append(
            {
                "id": generate_uuid_from_tuple((job_id, batch_id, i)),
                "vector": embedding,
                "source_text": source_text, 
                "source_document": source_filename
            }
        )
    return upsert_list

def write_embeddings_to_lancedb(upsert_list, batch_id):
    # right now only local connection, since its serverless and their cloud is in beta
    batch = safe_db_operation(batch_service.get_batch, batch_id)
    db = lancedb.connect(batch.vector_db_metadata.environment)
    try:
        table = db.open_table(batch.vector_db_metadata.index_name)
    except FileNotFoundError as e:
        logging.info(f"Table {batch.vector_db_metadata.index_name} does not exist in environment {batch.vector_db_metadata.environment}.")

        if batch.embeddings_metadata.embeddings_type == EmbeddingsType.OPEN_AI:
            schema = pa.schema(
                [
                    pa.field("id", pa.string()),
                    pa.field("vector", pa.list_(pa.float32(), 1536)),
                    pa.field("source_text", pa.string()),
                    pa.field("source_document", pa.string()),
                ])
            table = db.create_table(batch.vector_db_metadata.index_name, schema=schema)
            logging.info(f"Created table {batch.vector_db_metadata.index_name} in environment {batch.vector_db_metadata.environment}.")
        else:
            logging.error(f"Embeddings type {batch.embeddings_metadata.embeddings_type} not supported for LanceDB. Only Open AI")
            return None

    logging.info(f"Starting LanceDB upsert for {len(upsert_list)} vectors")

    batch_size = config.PINECONE_BATCH_SIZE
    vectors_uploaded = 0

    for i in range(0,len(upsert_list), batch_size):
        try:
            table.add(data=upsert_list[i:i+batch_size])
            vectors_uploaded += batch_size
        except Exception as e:
            logging.error('Error writing embeddings to lance db:', e)
            return None
    
    logging.info(f"Successfully uploaded {vectors_uploaded} vectors to lance db")
    return vectors_uploaded

# TODO: refactor into utils
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

def callback(ch, method, properties, body):
    # do these outside the try-catch so it can update the batch status if there's an error
    # if this parsing logic fails, the batch shouldn't be marked as failed
    data = json.loads(body)
    batch_id, chunks_with_embeddings, vector_db_key = data

    if vector_db_key:
        os.environ["VECTOR_DB_KEY"] = vector_db_key
    else:
        logging.info("No vector DB key provided")
    
    try:
        logging.info("Batch retrieved successfully")
        upload_batch(batch_id, chunks_with_embeddings)
        logging.info("Batch processed successfully")
    except Exception as e:
        logging.error('Error processing batch: %s', e)
        update_batch_and_job_status(None, batch_id, BatchStatus.FAILED)

    ch.basic_ack(delivery_tag=method.delivery_tag)

def start_connection(max_retries=5, retry_delay=5):
    for attempt in range(max_retries):
        try:
            connection_params = create_connection_params()
            connection = pika.BlockingConnection(connection_params)
            channel = connection.channel()

            queue_name = os.getenv('VDB_UPLOAD_QUEUE')
            channel.queue_declare(queue=queue_name)

            channel.basic_consume(queue=queue_name, on_message_callback=callback)

            logging.info('Waiting for messages.')
            channel.start_consuming()
            return  # If successful, exit the function
            
        except AMQPConnectionError as e:
            logging.error('AMQP Connection Error: %s', e)
        except Exception as e:
            logging.error('Unexpected error: %s', e)
        finally:
            if connection and not connection.is_closed:
                connection.close()

        logging.info('Retrying to connect in %s seconds (Attempt %s/%s)', retry_delay, attempt + 1, max_retries)
        time.sleep(retry_delay)

if __name__ == "__main__":
    while True:
        try:
            start_connection()
        except Exception as e:
            logging.error('Error in start_connection: %s', e)
            logging.info('Restarting start_connection after encountering an error.')
            time.sleep(config.PIKA_RETRY_INTERVAL) 

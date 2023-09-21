import sys
import os

# this is needed to import classes from other directories
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

import json
import pika
import logging
import time
import ssl
import torch
import pinecone
import numpy as np
from img2vec_pytorch import Img2Vec
from PIL import Image
from io import BytesIO
import services.database.job_service as job_service
from services.database.database import get_db
from shared.job_status import JobStatus
from shared.utils import generate_uuid_from_tuple
from shared.vector_db_type import VectorDBType

# global configs
logging.basicConfig(filename='./image-worker-log.txt', level=logging.INFO)
connection = None
img2vec = None

def embed_image(image_bytes):
    image_file = BytesIO(image_bytes)
    img = Image.open(image_file)

    # Get a vector from img2vec, returned as a torch FloatTensor
    vector_tensor = img2vec.get_vec(img, tensor=True)

    embedding_list = transform_vector_to_list(vector_tensor)
    return embedding_list

def transform_vector_to_list(vector):
    squeezed_tensor = vector.squeeze()
    numpy_array = squeezed_tensor.numpy()
    return numpy_array.tolist()

def create_pinecone_source_chunk_dict(embeddings_list, job_id, filename):
    upsert_list = []
    for i, embedding in enumerate(embeddings_list):
        upsert_list.append(
            {"id": generate_uuid_from_tuple((job_id, i)), 
            "values": embedding, 
            "metadata": {"source_document": filename}})
    return upsert_list

def write_embeddings_to_pinecone(upsert_list, vector_db_metadata):
    pinecone_api_key = os.getenv('VECTOR_DB_KEY')
    pinecone.init(api_key=pinecone_api_key, environment=vector_db_metadata.environment)
    index = pinecone.GRPCIndex(vector_db_metadata.index_name)
    if not index:
        logging.error(f"Index {vector_db_metadata.index_name} does not exist in environment {vector_db_metadata.environment}")
        return None
    
    logging.info(f"Starting pinecone upsert for {len(upsert_list)} vectors")

    batch_size = 128
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

def upload_embeddings(embeddings, job):
    with get_db() as db:
        if job.vector_db_metadata.vector_db_type == VectorDBType.PINECONE:
            upsert_list = create_pinecone_source_chunk_dict(embeddings, job.job_id, job.source_filename)
            vectors_uploaded = write_embeddings_to_pinecone(upsert_list, job.vector_db_metadata)
            
            if vectors_uploaded:
                job_service.update_job_status(db, job.job_id, JobStatus.COMPLETED)
            else:
                job_service.update_job_status(db, job.job_id, JobStatus.FAILED)
        else:
            logging.error('Unsupported vector DB type:', job.vector_db_metadata.vector_db_type)
            job_service.update_job_status(db, job.job_id, JobStatus.FAILED)

def process_image(image_bytes, job_id):
    with get_db() as db:
        job = job_service.get_job_with_vdb_metadata(db, job_id)
        
        # TODO: update this logic once the batch creation logic is moved out of the API
        if job.job_status == JobStatus.NOT_STARTED or job.job_status == JobStatus.CREATING_BATCHES:
            job_service.update_job_status(db, job.id, JobStatus.PROCESSING_BATCHES)

    try:
        embeddings = embed_image(image_bytes)
        upload_embeddings(embeddings, job)
    except Exception as e:
        logging.error('Error embedding image:', e)
        with get_db() as db:
            job_service.update_job_status(db, job.id, JobStatus.FAILED)

def callback(ch, method, properties, body):
    try:
        data = json.loads(body)
        image_bytes = data['image_bytes']
        job_id = data['job_id']
        os.environ["VECTOR_DB_KEY"] = data['vector_db_key']

        logging.info("Batch retrieved successfully")
        process_image(image_bytes, job_id)
        logging.info("Batch processed successfully")
    except Exception as e:
        logging.error('Error with initial image processing:', e)

    ch.basic_ack(delivery_tag=method.delivery_tag)

def start_connection():
    global connection
    
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

            consume_channel = connection.channel()
            consume_queue_name = os.getenv('IMAGE_QUEUE')
            consume_channel.queue_declare(queue=consume_queue_name)
            consume_channel.basic_consume(queue=consume_queue_name, on_message_callback=callback)

            logging.info('Waiting for messages.')
            consume_channel.start_consuming()
            
        except Exception as e:
            logging.error('ERROR connecting to RabbitMQ, retrying now. See exception:', e)
            time.sleep(10) # Wait before retrying

if __name__ == "__main__":
    # Initialize Img2Vec with GPU if possible
    if torch.cuda.is_available():
        try:
            img2vec = Img2Vec(cuda=True)
            logging.info("Model moved to GPU.")
        except Exception as e:
            logging.error("Error moving model to GPU. Staying on CPU. Error:", e)
    else:
        img2vec = Img2Vec(cuda=False)
        logging.info("CUDA not available. Model stays on CPU.")
    
    start_connection()
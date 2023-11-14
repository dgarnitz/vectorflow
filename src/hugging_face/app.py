import os
import sys

# this is needed to import classes from other directories
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

import logging
import argparse
import time
import pika
import json
import ssl
import torch
import services.database.batch_service as batch_service
from sentence_transformers import SentenceTransformer
from services.database.database import get_db, safe_db_operation
from shared.batch_status import BatchStatus
from services.database import job_service
from shared.utils import send_embeddings_to_webhook
from shared.job_status import JobStatus
from services.rabbitmq.rabbit_service import create_connection_params
from pika.exceptions import AMQPConnectionError

model = None
publish_channel = None

logging.basicConfig(filename='./hf-log.txt', level=logging.INFO)
logging.basicConfig(filename='./hf-errors.txt', level=logging.ERROR)

def embed(batch_id, batch_of_chunks_to_embed, vector_db_key): 
    global model

    try:
        if torch.cuda.is_available():
            try:
                model = model.to('cuda')
                logging.info("Model moved to GPU.")
            except Exception as e:
                logging.error("Error moving model to GPU. Staying on CPU. Error: %s", e)
        else:
            logging.info("CUDA not available. Model stays on CPU.")
        
        # does tokenization for you
        logging.info(f"Starting embedding with model: {model_name}")
        chunk_list = [chunk['text'] for chunk in batch_of_chunks_to_embed]
        embeddings = model.encode(chunk_list, normalize_embeddings=True)
        logging.info(f"Embedding complete with model: {model_name}")
        
        embeddings_list = embeddings.tolist()
        for chunk, embedding in zip(batch_of_chunks_to_embed, embeddings_list):
            chunk['vector'] = embedding

        batch = safe_db_operation(batch_service.get_batch, batch_id)
        job = safe_db_operation(job_service.get_job, batch.job_id)

        safe_db_operation(batch_service.augment_minibatches_embedded, batch_id)

        if job.webhook_url and job.webhook_key:
            response = send_embeddings_to_webhook(batch_of_chunks_to_embed, job)
            if response.status_code == 200:
                status = safe_db_operation(batch_service.update_batch_status_with_successful_minibatch, batch.id)
                update_batch_and_job_status(batch.job_id, status, batch.id)
            else:
                update_batch_and_job_status(batch.job_id, BatchStatus.FAILED, batch.id)
                logging.error(f"Error sending embeddings to webhook. Status code: {response.status_code}")
        else:
            upload_to_vector_db(batch_id, batch_of_chunks_to_embed, vector_db_key)
    except Exception as e:
        logging.error('Error embedding batch: %s', e)

        # TODO: Add retry logic and handle partial failure case
        update_batch_status(BatchStatus.FAILED, batch_id)
        
def upload_to_vector_db(batch_id, batches_for_upload, vector_db_key):
    try:
        serialized_data = json.dumps((batch_id, batches_for_upload, vector_db_key))
        publish_channel.basic_publish(exchange='',
                                      routing_key=os.getenv('VDB_UPLOAD_QUEUE'),
                                      body=serialized_data)
        logging.info(f"Text embeddings for {batch_id} published to {os.getenv('VDB_UPLOAD_QUEUE')} queue")
    except Exception as e:
        logging.error('Error publishing message to RabbitMQ: %s', e)
        update_batch_status(BatchStatus.FAILED, batch_id)

def update_batch_status(batch_status, batch_id):
    try:
        with get_db() as db:
            updated_batch_status = batch_service.update_batch_status(db, batch_id, batch_status)
            logging.info(f"Batch {batch_id} status updated to {updated_batch_status}")      
    except Exception as e:
        logging.error('Error updating batch status: %s', e)

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

def get_args():
    parser = argparse.ArgumentParser(description="Run Flask app with specified model name")
    parser.add_argument('--model_name', type=str, required=True, help='Name of the model to load')
    return parser.parse_args()

def callback(ch, method, properties, body):
    try:
       batch_id, batch_of_chunks_to_embed, vector_db_key = json.loads(body)
       logging.info("Batch retrieved successfully")
       embed(batch_id, batch_of_chunks_to_embed, vector_db_key)
       logging.info("Batch processed successfully")
    except Exception as e:
        logging.error('Error processing batch: %s', e)

    ch.basic_ack(delivery_tag=method.delivery_tag)

def start_connection(max_retries=5, retry_delay=5):
    global publish_channel
    global model_name
    
    for attempt in range(max_retries):
        try:
            connection_params = create_connection_params()
            connection = pika.BlockingConnection(connection_params)
            consume_channel = connection.channel()
            publish_channel = connection.channel() 

            consume_queue_name = model_name
            publish_queue_name = os.getenv('VDB_UPLOAD_QUEUE')

            consume_channel.queue_declare(queue=consume_queue_name)
            publish_channel.queue_declare(queue=publish_queue_name)

            consume_channel.basic_consume(queue=consume_queue_name, on_message_callback=callback)

            logging.info('Waiting for messages.')
            consume_channel.start_consuming()
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
    args = get_args()
    model_name = args.model_name
    model = SentenceTransformer(model_name)
    while True:
        try:
            start_connection()

        except Exception as e:
            logging.error('Error in start_connection: %s', e)
            logging.info('Restarting start_connection after encountering an error.')
            time.sleep(10)
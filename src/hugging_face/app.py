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
from services.database.database import get_db
from shared.batch_status import BatchStatus

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
                logging.error("Error moving model to GPU. Staying on CPU. Error:", e)
        else:
            logging.info("CUDA not available. Model stays on CPU.")
        
        # does tokenization for you
        logging.info(f"Starting embedding with model: {model_name}")
        embeddings = model.encode(batch_of_chunks_to_embed, normalize_embeddings=True)
        logging.info(f"Embedding complete with model: {model_name}")
        
        embeddings_list = embeddings.tolist()
        text_embeddings_list = list(zip(batch_of_chunks_to_embed, embeddings_list))
        upload_to_vector_db(batch_id, text_embeddings_list, vector_db_key)
    except Exception as e:
        logging.error('Error embedding batch:', e)

        # TODO: Add retry logic and handle partial failure case
        update_batch_status(BatchStatus.FAILED, batch_id)
        
def upload_to_vector_db(batch_id, text_embeddings_list, vector_db_key):
    try:
        serialized_data = json.dumps((batch_id, text_embeddings_list, vector_db_key))
        publish_channel.basic_publish(exchange='',
                                      routing_key=os.getenv('VDB_UPLOAD_QUEUE'),
                                      body=serialized_data)
        logging.info(f"Text embeddings for {batch_id} published to {os.getenv('VDB_UPLOAD_QUEUE')} queue")

        update_batch_status(BatchStatus.EMBEDDING_COMPLETE, batch_id)
    except Exception as e:
        logging.error('Error publishing message to RabbitMQ:', e)

def update_batch_status(batch_status, batch_id):
    try:
        with get_db() as db:
            updated_batch_status = batch_service.update_batch_status(db, batch_id, batch_status)
            logging.info(f"Batch {batch_id} status updated to {updated_batch_status}")      
    except Exception as e:
        logging.error('Error updating batch status:', e)

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
        logging.error('Error processing batch:', e)

    ch.basic_ack(delivery_tag=method.delivery_tag)

def start_connection():
    global publish_channel
    global model_name
    
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
            publish_channel = connection.channel() 

            consume_queue_name = model_name
            publish_queue_name = os.getenv('VDB_UPLOAD_QUEUE')

            consume_channel.queue_declare(queue=consume_queue_name)
            publish_channel.queue_declare(queue=publish_queue_name)

            consume_channel.basic_consume(queue=consume_queue_name, on_message_callback=callback)

            logging.info('Waiting for messages.')
            consume_channel.start_consuming()
            
        except Exception as e:
            logging.error('ERROR connecting to RabbitMQ, retrying now. See exception:', e)
            time.sleep(10) # Wait before retrying

if __name__ == "__main__": 
    args = get_args()
    model_name = args.model_name
    model = SentenceTransformer(model_name)
    start_connection()
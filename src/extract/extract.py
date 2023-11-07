import sys
import os

# this is needed to import classes from the API. it will be removed when the worker is refactored
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

import logging
import json
import pika
import time
import fitz
from pathlib import Path
from shared.job_status import JobStatus
from shared.batch_status import BatchStatus
from services.database.database import safe_db_operation
from models.batch import Batch
from services.database import batch_service, job_service
from services.minio.minio_service import create_minio_client
from docx import Document
from io import BytesIO
from llama_index import download_loader
from shared.vectorflow_request import VectorflowRequest
from services.rabbitmq.rabbit_service import create_connection_params
from pika.exceptions import AMQPConnectionError

logging.basicConfig(filename='./extract-log.txt', level=logging.INFO)
logging.basicConfig(filename='./extract-error-log.txt', level=logging.ERROR)

def extract_file(filename, vectorflow_request_dict, job_id):
    safe_db_operation(job_service.update_job_status, job_id, JobStatus.CREATING_BATCHES)

    logging.info("Extracting VectorflowRequest from dictionary")
    vectorflow_request = VectorflowRequest._from_dict(vectorflow_request_dict)

    logging.info(f"Extracting file {filename} from Minio")
    minio_client = create_minio_client()
    minio_client.fget_object(os.getenv('MINIO_BUCKET'), filename, filename)

    logging.info(f"Processing file {filename}")
    try:
        batch_count = process_file_from_disk(filename, vectorflow_request, job_id)
    except Exception as e:
        logging.error('Error processing file: %s', e)
        safe_db_operation(job_service.update_job_status, job_id, JobStatus.FAILED)

        # TODO: remove this when retry is implemented
        remove_from_minio(filename)
        os.remove(filename)
        return

    if not batch_count:
        safe_db_operation(job_service.update_job_status, job_id, JobStatus.FAILED)
        logging.error(f"No batches created for job {job_id}")

        # TODO: remove this when retry is implemented
        remove_from_minio(filename)
        return

    remove_from_minio(filename)
    os.remove(filename)

    logging.info("File removed from Minio and local storage")
    logging.info(f"Created {batch_count} batches")

def process_file_from_disk(file_path, vectorflow_request, job_id):
    with open(file_path, 'rb') as f:
        content = f.read()

    filename = Path(file_path).name

    if filename.endswith('.txt'):
        file_content = content.decode('utf-8')
    
    elif filename.endswith('.docx'):
        doc = Document(file_path)
        file_content = "\n".join([paragraph.text for paragraph in doc.paragraphs])

    elif filename.endswith('.md'):
        temp_file_path = Path('./temp_file.md')
        with open(temp_file_path, 'wb') as temp_file:
            temp_file.write(content)
            
        MarkdownReader = download_loader("MarkdownReader")
        loader = MarkdownReader()
        documents = loader.load_data(file=temp_file_path)

        file_content = "\n".join([document.text for document in documents])
        temp_file_path.unlink()
    
    elif filename.endswith('.html'):
        file_content = repr(content.decode('utf-8'))

    else:
        with fitz.open(stream=BytesIO(content), filetype='pdf') as doc:
            file_content = ""
            for page in doc:
                file_content += page.get_text()

    batch_count = create_batches(file_content, job_id, vectorflow_request)
    return batch_count

def create_batches(file_content, job_id, vectorflow_request):
    logging.info("Creating batches")
    chunks = [chunk for chunk in split_file(file_content, vectorflow_request.lines_per_batch)]
    
    batches = [Batch(job_id=job_id, embeddings_metadata=vectorflow_request.embeddings_metadata, vector_db_metadata=vectorflow_request.vector_db_metadata) for _ in chunks]
    batches = safe_db_operation(batch_service.create_batches, batches)

    job = safe_db_operation(job_service.update_job_total_batches, job_id, len(batches))

    for batch, chunk in zip(batches, chunks):
        try:
            logging.info("Publishing message to RabbitMQ")
            data = (batch.id, chunk, vectorflow_request.vector_db_key, vectorflow_request.embedding_api_key)
            json_data = json.dumps(data)
            publish_channel.basic_publish(exchange='',
                                        routing_key=os.getenv('EMBEDDING_QUEUE'),
                                        body=json_data)
            logging.info("Message published successfully")
        except Exception as e:
            logging.error('Error publishing message to RabbitMQ: %s', e)

            # TODO: Add retry
            update_batch_and_job_status(batch.id, BatchStatus.FAILED) # TODO: add batch failure logic here

    return job.total_batches if job else None
    
def split_file(file_content, lines_per_chunk=1000):
    lines = file_content.splitlines()
    for i in range(0, len(lines), lines_per_chunk):
        yield lines[i:i+lines_per_chunk]

def remove_from_minio(filename):
    client = create_minio_client()
    client.remove_object(os.getenv("MINIO_BUCKET"), filename)

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
        elif job.job_status == JobStatus.FAILED:
            logging.info(f"Job {job_id} failed. {job.batches_succeeded} out of {job.total_batches} batches succeeded")
                
    except Exception as e:
        logging.error('Error updating job and batch status: %s', e)
        safe_db_operation(job_service.update_job_status, job_id, JobStatus.FAILED)

####################
## RabbitMQ Logic ##
####################

def callback(ch, method, properties, body):
    # do these outside the try-catch so it can update the batch status if there's an error
    # if this parsing logic fails, the batch shouldn't be marked as failed
    data = json.loads(body)
    job_id, filename, vectorflow_request = data
    
    try:
        logging.info("Batch retrieved successfully")
        extract_file(filename, vectorflow_request, job_id)
        logging.info("Batch processed successfully")
    except Exception as e:
        logging.error('Error processing batch: %s', e)
        safe_db_operation(job_service.update_job_status, job_id, JobStatus.FAILED)

    ch.basic_ack(delivery_tag=method.delivery_tag)

def start_connection(max_retries=5, retry_delay=5):
    global publish_channel
    global connection

    for attempt in range(max_retries):
        try:
            connection_params = create_connection_params()
            connection = pika.BlockingConnection(connection_params)
            consume_channel = connection.channel()
            publish_channel = connection.channel()

            consume_queue_name = os.getenv('EXTRACTION_QUEUE')
            publish_queue_name = os.getenv('EMBEDDING_QUEUE')

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

    raise Exception('Failed to connect after {} attempts'.format(max_retries))

if __name__ == "__main__":
    while True:
        try:
            start_connection()

        except Exception as e:
            logging.error('Error in start_connection: %s', e)
            logging.info('Restarting start_connection after encountering an error.')
            time.sleep(10)
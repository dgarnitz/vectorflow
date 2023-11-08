import os
import pika
import ssl
import logging
import time
from pika.exceptions import ConnectionClosed, ChannelClosed

def create_connection_params():
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
    return connection_params

def publish_message_to_retry_queue(channel, retry_queue, message, publish_attempts=5):
    for attempt in range(publish_attempts):
        try:
            channel.basic_publish(exchange='',
                                  routing_key=retry_queue,
                                  body=message)
            logging.info("Message retried successfully")
            break  # Exit the loop if publish is successful
        except ConnectionClosed:
            logging.error("Connection was closed, retrying...")
            connection_params = create_connection_params()
            connection = pika.BlockingConnection(connection_params)
            channel = connection.channel()
            channel.queue_declare(queue=retry_queue)
        except ChannelClosed:
            logging.error("Channel was closed, retrying...")
            connection_params = create_connection_params()
            connection = pika.BlockingConnection(connection_params)
            channel = connection.channel()
            channel.queue_declare(queue=retry_queue)
        except Exception as e:
            logging.error("Failed to publish message: %s", e)
        time.sleep(2 ** attempt)  # Exponential backoff
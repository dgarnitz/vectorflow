import os
import pika
import ssl

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
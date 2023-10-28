import pika
import os
import ssl

class Pipeline:
    def __init__(self):
        self.credentials = pika.PlainCredentials(os.getenv('RABBITMQ_USERNAME'), os.getenv('RABBITMQ_PASSWORD'))
        self.embedding_queue = os.getenv('EMBEDDING_QUEUE')
        self.image_queue = os.getenv('IMAGE_QUEUE')
        self.channel = None

    def connect(self, queue):
        connection_params = self._get_connection_params()
        connection = pika.BlockingConnection(connection_params)
        self.channel = connection.channel()
        self.channel.queue_declare(queue=queue)

    def disconnect(self):
        if self.channel and self.channel.is_open:
            self.channel.close()

    def _get_connection_params(self):
        if os.getenv('RABBITMQ_PORT') == "5671":
            return pika.ConnectionParameters(
                host=os.getenv('RABBITMQ_HOST'),
                credentials=self.credentials,
                port=os.getenv('RABBITMQ_PORT'),
                ssl_options=pika.SSLOptions(ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)),
                virtual_host="/"
            )
        else:
            return pika.ConnectionParameters(
                host=os.getenv('RABBITMQ_HOST'),
                credentials=self.credentials,
            )

    def add_to_queue(self, data, queue):
        self.channel.basic_publish(exchange='', routing_key=queue, body=data)

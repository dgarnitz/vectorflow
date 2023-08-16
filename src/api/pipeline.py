import pika
import os
import ssl

class Pipeline:
    def __init__(self):
        self.credentials = pika.PlainCredentials(os.getenv('RABBITMQ_USERNAME'), os.getenv('RABBITMQ_PASSWORD'))
        self.queue_name = os.getenv('RABBITMQ_QUEUE')
        self.channel = None

    def connect(self):
        connection_params = self._get_connection_params()
        connection = pika.BlockingConnection(connection_params)
        self.channel = connection.channel()
        self.channel.queue_declare(queue=self.queue_name)

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


    def add_to_queue(self, data):
        self.channel.basic_publish(exchange='', routing_key=self.queue_name, body=str(data))

    # NOTE: for debugging and testing
    def get_from_queue(self):
        method_frame, header_frame, body = self.channel.basic_get(queue=self.queue_name)
        if method_frame:
            self.channel.basic_ack(method_frame.delivery_tag)
            return body
        return None

    # NOTE: for debugging and testing
    def get_queue_size(self):
        response = self.channel.queue_declare(queue=self.queue_name, passive=True)
        return response.method.message_count
    
import pika
import os

class Pipeline:
    def __init__(self):
        credentials = pika.PlainCredentials(os.getenv('RABBITMQ_USERNAME'), os.getenv('RABBITMQ_PASSWORD'))

        connection_params = pika.ConnectionParameters(
            host=os.getenv('RABBITMQ_HOST'),
            credentials=credentials
        )

        connection = pika.BlockingConnection(connection_params)
        self.channel = connection.channel()
        self.queue_name = os.getenv('RABBITMQ_QUEUE')
        self.channel.queue_declare(queue=self.queue_name)

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
    
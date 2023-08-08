from queue import Queue

class Pipeline:
    def __init__(self):
        self.queue = Queue()

    def add_to_queue(self, data):
        self.queue.put(data)

    def get_from_queue(self):
        return self.queue.get()
    
    def get_queue_size(self):
        return self.queue.qsize()
    
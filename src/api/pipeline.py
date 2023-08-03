from queue import Queue
from shared.job_status import JobStatus
from shared.batch_status import BatchStatus
from models.job import Job

class Pipeline:
    def __init__(self):
        self.queue = Queue()
        self.database = {'jobs': dict(), 'batches': dict()}

    def add_to_queue(self, data):
        self.queue.put(data)

    def get_from_queue(self):
        return self.queue.get()
    
    def get_queue_size(self):
        return self.queue.qsize()
    
    def create_job(self, webhook_url):
        #self.database['jobs'][job_id] = Job(job_id=job_id, webhook_url=webhook_url)
        print("mocking job creation")
        return 123
    
    def update_job_with_batch(self, job_id, batch_id, batch_status):
        batch = self.database['batches'][batch_id]
        batch.batch_status = BatchStatus[batch_status]
        
        job = self.database['jobs'][job_id]
        job.batches_processed += 1

        if batch.batch_status == BatchStatus.COMPLETED:
            job.batches_succeeded += 1

        if job.batches_processed == job.total_batches:
            if job.batches_succeeded == job.total_batches:
                job.job_status = JobStatus.COMPLETED
            elif job.batches_succeeded > 0:
                job.job_status = JobStatus.PARTIALLY_COMPLETED
            else:
                job.job_status = JobStatus.FAILED
        else:
            job.job_status = JobStatus.IN_PROGRESS

        return job.job_status

    def update_job_total_batches(self, job_id, total_batches):
        self.database['jobs'][job_id].total_batches = total_batches
    
    def get_job_status(self, job_id):
        try:
            status = self.database['jobs'][job_id].job_status
            return status
        except KeyError:
            return None
    
    def create_batch(self, batch):
        self.database['batches'][batch.batch_id] = batch
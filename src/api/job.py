from job_status import JobStatus

class Job:
    def __init__(self, job_id, webhook_url):
        self.job_id = job_id
        self.webhook_url = webhook_url
        self.job_status = JobStatus.NOT_STARTED
        self.batches_processed = 0
        self.batches_succeeded = 0
        self.total_batches = 0
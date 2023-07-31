import datetime
from batch_status import BatchStatus

class Batch:
    def __init__(self, source_data, batch_id, job_id, embeddings_metadata, vector_db_metadata) -> None:
        self.source_data = source_data
        self.batch_id = batch_id
        self.job_id = job_id
        self.embeddings_metadata = embeddings_metadata
        self.vector_db_metadata = vector_db_metadata
        self.batch_status = BatchStatus.NOT_STARTED
        self.start_time = datetime.datetime.now()
        self.retries = 0

    def serialize(self):
        if not isinstance(self.source_data, list):
            raise ValueError("source_data must be a list of strings")

        # Ensure all elements of source_data are strings
        source_data = [item.decode() if isinstance(item, bytes) else item for item in self.source_data]

        return {
            'source_data': source_data,
            'batch_id': self.batch_id,
            'job_id': self.job_id,
            'embeddings_metadata': self.embeddings_metadata.to_dict() if self.embeddings_metadata else None,
            'vector_db_metadata': self.vector_db_metadata.to_dict() if self.vector_db_metadata else None,
            'batch_status': self.batch_status.value if self.batch_status else 'NOT_STARTED',
            'start_time': self.start_time.isoformat(),
            'retries': self.retries
        }

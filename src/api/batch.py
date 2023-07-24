from src.api.batch_status import BatchStatus

class Batch:
    def __init__(self, source_data, batch_id, job_id, embeddings_metadata, vector_db_metadata) -> None:
        self.source_data = source_data
        self.batch_id = batch_id
        self.job_id = job_id
        self.embeddings_metadata = embeddings_metadata # TODO: this could be swapped for an ID that can be looked up in the DB
        self.vector_db_metadata = vector_db_metadata # TODO: this could be swapped for an ID that can be looked up in the DB
        self.batch_status = BatchStatus.NOT_STARTED

    def serialize(self):
        if not isinstance(self.source_data, str):
            raise ValueError("source_data must be a string")
        return {
            #TODO: unclear the best way to pass source_data to the worker. Need a more permanent solution
            'source_data': self.source_data,
            'batch_id': self.batch_id,
            'job_id': self.job_id,
            'embeddings_metadata': self.embeddings_metadata.to_dict() if self.embeddings_metadata else None,
            'vector_db_metadata': self.vector_db_metadata.to_dict() if self.vector_db_metadata else None,
            'batch_status': self.batch_status.value if self.batch_status else 'NOT_STARTED'
        }
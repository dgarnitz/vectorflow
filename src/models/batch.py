from sqlalchemy import ForeignKey, Column, Integer, String, DateTime, Enum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from services.database.database import Base
from shared.batch_status import BatchStatus
from models.embeddings_metadata import EmbeddingsMetadata
from models.vector_db_metadata import VectorDBMetadata

class Batch(Base):
    __tablename__ = 'batches'

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(Integer, ForeignKey('jobs.id'))  
    batch_status = Column(Enum(BatchStatus), default=BatchStatus.NOT_STARTED)
    start_time = Column(DateTime(timezone=True), server_default=func.now())
    retries = Column(Integer, default=0)
    minibatch_count = Column(Integer)
    minibatches_embedded = Column(Integer)
    minibatches_uploaded = Column(Integer)

    embeddings_metadata_id = Column(Integer, ForeignKey('embeddings_metadata.id'))
    embeddings_metadata = relationship(EmbeddingsMetadata)

    vector_db_metadata_id = Column(Integer, ForeignKey('vector_db_metadata.id'))
    vector_db_metadata = relationship(VectorDBMetadata)

    def serialize(self):
        return {
            'batch_id': self.id,
            'job_id': self.job_id,
            'embeddings_metadata': self.embeddings_metadata.serialize() if self.embeddings_metadata else None,
            'vector_db_metadata': self.vector_db_metadata.serialize() if self.vector_db_metadata else None,
            'batch_status': self.batch_status.value if self.batch_status else 'NOT_STARTED',
            'start_time': self.start_time,
            'retries': self.retries
        }


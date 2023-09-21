from models.embeddings_metadata import EmbeddingsMetadata
from sqlalchemy import Column, Integer, String, DateTime, Enum, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from services.database.database import Base
from shared.job_status import JobStatus

class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    webhook_url = Column(String)
    job_status = Column(Enum(JobStatus), default=JobStatus.NOT_STARTED)
    batches_processed = Column(Integer, default=0)
    batches_succeeded = Column(Integer, default=0)
    total_batches = Column(Integer, default=0)
    start_time = Column(DateTime(timezone=True), default=func.now())
    source_filename = Column(String)

    embeddings_metadata_id = Column(Integer, ForeignKey('embeddings_metadata.id'))
    embeddings_metadata = relationship(EmbeddingsMetadata)

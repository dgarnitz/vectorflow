from sqlalchemy.orm import Session
from models.batch import Batch
from shared.batch_status import BatchStatus
from sqlalchemy.orm import joinedload

def create_batches(db: Session, batches: list[Batch]):
    db.add_all(batches)
    db.commit()
    return batches

def get_batch(db: Session, batch_id: str):
    return (
        db.query(Batch)
        .options(
            joinedload(Batch.embeddings_metadata),
            joinedload(Batch.vector_db_metadata),
        )
        .filter(Batch.id == batch_id)
        .first()
    )

def update_batch_status(db: Session, batch_id: int, batch_status: BatchStatus):
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if batch:
        batch.batch_status = batch_status
        db.commit()
        db.refresh(batch)
        return batch.batch_status
    return None

def update_batch_retry_count(db: Session, batch_id: int, retries: int):
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if batch:
        batch.retries = retries
        db.commit()
        db.refresh(batch)
        return batch.retries
    return None
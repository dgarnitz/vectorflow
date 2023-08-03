from sqlalchemy.orm import Session
from database import SessionLocal
from models.batch import Batch
from shared.batch_status import BatchStatus

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_batches(db: Session, batches: list[Batch]):
    db.add_all(batches)
    db.commit()
    return len(batches)

def get_batch(db: Session, batch_id: str):
    return db.query(Batch).filter(Batch.batch_id == batch_id).first()

def update_batch_status(db: Session, batch_id: int, batch_status: str):
    batch = db.query(Batch).filter(Batch.batch_id == batch_id).first()
    if batch:
        batch.batch_status = BatchStatus[batch_status]
        db.commit()
        db.refresh(batch)
        return batch.batch_status
    return None

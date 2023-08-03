from sqlalchemy.orm import Session
from database import SessionLocal
from models.batch import Batch

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_batch(db: Session, batch: Batch):
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return batch

def create_batches(db: Session, batches: list[Batch]):
    db.add_all(batches)
    db.commit()
    return len(batches)

def get_batch(db: Session, batch_id: str):
    return db.query(Batch).filter(Batch.batch_id == batch_id).first()

from sqlalchemy.orm import Session
from database import SessionLocal
from models.batch import Batch
from models.job import Job

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_job(db: Session, webhook_url: str):
    job = Job(webhook_url=webhook_url)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job

def get_job(db: Session, job_id: str):
    return db.query(Job).filter(Job.job_id == job_id).first()

def update_job_with_batch(db: Session, job_id: int, batch: Batch):
    # do the update
    return job

def update_job_total_batches(db: Session, job_id: int, total_batches: int):
    job = db.query(Job).filter(Job.job_id == job_id).first()
    if job:
        job.total_batches = total_batches
        db.commit()
        db.refresh(job)
        return job
    return None

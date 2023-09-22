from sqlalchemy.orm import Session, joinedload
from models.batch import Batch

#this is required for Batch's foreign relation to work, otherwise Job won't laod and it throws an error
from models.job import Job
 
from shared.batch_status import BatchStatus

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

# TODO: tackle scenario of hanging batches
def update_batch_status_with_successful_minibatch(db: Session, batch_id: int):
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if batch:
        if batch.minibatch_count and batch.minibatches_uploaded:
            batch.minibatches_uploaded += 1
        elif batch.minibatch_count and not batch.minibatches_uploaded:
            batch.minibatches_uploaded = 1

        # if no minibatches, then its a complete batch
        if not batch.minibatch_count:
            batch.batch_status = BatchStatus.COMPLETED
        elif batch.minibatches_uploaded == batch.minibatch_count and batch.minibatches_embedded == batch.minibatch_count:
            batch.batch_status = BatchStatus.COMPLETED
        
        db.commit()
        db.refresh(batch)
        return batch.batch_status
    return None

def update_batch_minibatch_count(db: Session, batch_id: int, minibatch_count: int):
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if batch:
        batch.minibatch_count = minibatch_count
        db.commit()
        db.refresh(batch)
        return batch.minibatch_count
    return None

def augment_minibatches_embedded(db: Session, batch_id: int):
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if batch:
        if batch.minibatches_embedded:
            batch.minibatches_embedded += 1
        else:
            batch.minibatches_embedded = 1
        db.commit()
        db.refresh(batch)
        return batch.minibatches_embedded
    return None
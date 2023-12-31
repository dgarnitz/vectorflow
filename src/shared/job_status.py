from enum import Enum

class JobStatus(Enum):
    NOT_STARTED = 'NOT_STARTED'
    IN_PROGRESS = 'IN_PROGRESS'
    CREATING_BATCHES = 'CREATING_BATCHES'
    PROCESSING_BATCHES = 'PROCESSING_BATCHES'
    COMPLETED = 'COMPLETED'
    FAILED = 'FAILED'
    PARTIALLY_COMPLETED = 'PARTIALLY_COMPLETED'
from enum import Enum

class BatchStatus(Enum):
    NOT_STARTED = 'NOT_STARTED'
    PROCESSING = 'PROCESSING'
    COMPLETED = 'COMPLETED'
    FAILED = 'FAILED'
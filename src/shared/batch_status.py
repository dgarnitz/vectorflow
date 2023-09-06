from enum import Enum

class BatchStatus(Enum):
    NOT_STARTED = 'NOT_STARTED'
    EMBEDDING = 'EMBEDDING'
    VDB_UPLOAD = 'VDB_UPLOAD'
    COMPLETED = 'COMPLETED'
    FAILED = 'FAILED'
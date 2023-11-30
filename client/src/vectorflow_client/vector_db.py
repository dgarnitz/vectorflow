from .vector_db_type import VectorDBType

class VectorDB:

    def __init__(self, vector_db_type: VectorDBType = VectorDBType.QDRANT, 
               index_name: str = "test-1536", 
               environment: str = "qdrant", 
               collection: str = None):
        self.vector_db_type = vector_db_type
        self.index_name = index_name
        self.environment = environment
        self.collection = collection

    def serialize(self):
        data = {
            'vector_db_type': self.vector_db_type.name if self.vector_db_type else None,
            'index_name': self.index_name,
            'environment': self.environment,
            'collection': self.collection
        }

        return {k: v for k, v in data.items() if v is not None}

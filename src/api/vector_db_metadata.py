from enum import Enum

class VectorDBMetadata:
    def __init__(self, vector_db_type, index_name, environment):
        self.vector_db_type = vector_db_type
        self.index_name = index_name
        self.environment = environment

    def to_dict(self):
        return {
            'vector_db_type': self.vector_db_type.name if isinstance(self.vector_db_type, Enum) else self.vector_db_type,
            'index_name': self.index_name,
            'environment': self.environment,
        }
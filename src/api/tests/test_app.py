import unittest
import json
import os
from flask import Flask
from flask.testing import FlaskClient
from models.job import Job
from shared.batch_status import BatchStatus
from api import app, pipeline, auth
from models.embeddings_metadata import EmbeddingsMetadata
from shared.embeddings_type import EmbeddingsType
from models.vector_db_metadata import VectorDBMetadata
from shared.job_status import JobStatus
from shared.vector_db_type import VectorDBType
from models.batch import Batch 
from unittest.mock import patch

class TestApp(unittest.TestCase):
    def setUp(self):
        self.app = app.app
        self.client = self.app.test_client()
        app.auth.set_internal_api_key('test_key')
        self.headers = {
            "Authorization": app.auth.internal_api_key,
            "X-VectorDB-Key": "test_vdb_key",
            "X-EmbeddingAPI-Key": "test__embed_key"
        }

    @patch('api.app.send_telemetry')
    @patch('services.database.database.safe_db_operation')
    @patch('services.database.job_service.create_job')
    @patch('api.app.process_file')
    def test_embed_endpoint(self, mock_process_file, mock_create_job, mock_safe_db_operation, mock_send_telemetry):
        mock_process_file.return_value = 2
        test_embeddings_metadata = EmbeddingsMetadata(embeddings_type=EmbeddingsType.OPEN_AI)
        test_vector_db_metadata = VectorDBMetadata(vector_db_type=VectorDBType.PINECONE, 
                                                   index_name="test_index", 
                                                   environment="test_environment")
        mock_create_job.return_value = Job(id=1, job_status=JobStatus.NOT_STARTED)
        mock_safe_db_operation.return_value = "test_db"

        with open('api/tests/fixtures/test_text.txt', 'rb') as data_file:
            response = self.client.post('/embed', 
                                        data={'SourceData': data_file, 
                                            'EmbeddingsMetadata': json.dumps(test_embeddings_metadata.serialize()), 
                                            'VectorDBMetadata': json.dumps(test_vector_db_metadata.serialize())},
                                        headers=self.headers)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['message'], "Successfully added 2 batches to the queue")
        self.assertEqual(response.json['JobID'], 1)

    def test_embed_endpoint_no_vectorflow_key(self):
        test_embeddings_metadata = EmbeddingsMetadata(embeddings_type=EmbeddingsType.OPEN_AI)
        test_vector_db_metadata = VectorDBMetadata(vector_db_type=VectorDBType.PINECONE, 
                                                   index_name="test_index", 
                                                   environment="test_environment")

        headers = {}
        with open('api/tests/fixtures/test_text.txt', 'rb') as data_file:
            response = self.client.post('/embed', 
                                        data={'SourceData': data_file, 
                                            'EmbeddingsMetadata': json.dumps(test_embeddings_metadata.serialize()), 
                                            'VectorDBMetadata': json.dumps(test_vector_db_metadata.serialize())},
                                        headers=headers)
        
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json['error'], "Invalid credentials")

    def test_embed_endpoint_no_vectordb_key(self):
        test_embeddings_metadata = EmbeddingsMetadata(embeddings_type=EmbeddingsType.OPEN_AI)
        test_vector_db_metadata = VectorDBMetadata(vector_db_type=VectorDBType.PINECONE, 
                                                   index_name="test_index", 
                                                   environment="test_environment")

        current_local_vector_db = os.getenv("LOCAL_VECTOR_DB")
        del os.environ["LOCAL_VECTOR_DB"]
        headers = {"Authorization": app.auth.internal_api_key}
        with open('api/tests/fixtures/test_text.txt', 'rb') as data_file:
            response = self.client.post('/embed', 
                                        data={'SourceData': data_file, 
                                            'EmbeddingsMetadata': json.dumps(test_embeddings_metadata.serialize()), 
                                            'VectorDBMetadata': json.dumps(test_vector_db_metadata.serialize())},
                                        headers=headers)
        
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json['error'], "Missing required fields")
        os.environ["LOCAL_VECTOR_DB"] = current_local_vector_db

    def test_embed_endpoint_no_file(self):
        test_embeddings_metadata = EmbeddingsMetadata(embeddings_type=EmbeddingsType.OPEN_AI)
        test_vector_db_metadata = VectorDBMetadata(vector_db_type=VectorDBType.PINECONE, 
                                                   index_name="test_index", 
                                                   environment="test_environment")
        
        response = self.client.post('/embed', 
                                    data={ 
                                        'EmbeddingsMetadata': json.dumps(test_embeddings_metadata.serialize()), 
                                        'VectorDBMetadata': json.dumps(test_vector_db_metadata.serialize())},
                                    headers=self.headers)
        
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json['error'], "No file part in the request")

    def test_embed_endpoint_no_hugging_face_model_name(self):
        test_embeddings_metadata = EmbeddingsMetadata(embeddings_type=EmbeddingsType.HUGGING_FACE)
        test_vector_db_metadata = VectorDBMetadata(vector_db_type=VectorDBType.PINECONE, 
                                                   index_name="test_index", 
                                                   environment="test_environment")
        
        response = self.client.post('/embed', 
                                    data={ 
                                        'EmbeddingsMetadata': json.dumps(test_embeddings_metadata.serialize()), 
                                        'VectorDBMetadata': json.dumps(test_vector_db_metadata.serialize())},
                                    headers=self.headers)
        
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json['error'], 'Hugging face embeddings models require a "hugging_face_model_name" in the "embeddings_metadata"')

    @patch('services.database.database.safe_db_operation')
    @patch('services.database.job_service.get_job')
    def test_get_job_status_endpoint_no_job(self, mock_get_job, mock_safe_db_operation):
        # arrange
        mock_get_job.return_value = None
        mock_safe_db_operation.return_value = "test_db"

        # act
        response = self.client.get('/jobs/1/status', headers=self.headers)
        
        # assert
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json['error'], 'Job not found')
    
    @patch('services.database.database.safe_db_operation')
    @patch('services.database.job_service.get_job')
    def test_get_job_status_endpoint_job_exists(self, mock_get_job, mock_safe_db_operation):
        # arrange
        job = Job(id=1, job_status=JobStatus.NOT_STARTED)
        mock_get_job.return_value = job
        mock_safe_db_operation.return_value = "test_db"

        # act
        response = self.client.get(f"/jobs/{job.id}/status", headers=self.headers)

        # assert
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['JobStatus'], JobStatus.NOT_STARTED.value)

    def test_split_file(self):
        # arrange
        file_content = "test\n" * 2048

        # act
        chunks = [chunk for chunk in app.split_file(file_content)]

        # assert
        self.assertEqual(len(chunks), 3)

    def test_get_s3_file_name(self):
        # arrange
        pre_signed_url = "https://s3.amazonaws.com/my-bucket-name/myfolder/myfile.txt"

        # act
        filename = app.get_s3_file_name(pre_signed_url)

        # assert
        self.assertEqual(filename, "myfile.txt")

if __name__ == '__main__':
    unittest.main()

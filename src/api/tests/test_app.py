import unittest
import json
import auth
from flask import Flask
from flask.testing import FlaskClient
from batch_status import BatchStatus
from app import app, pipeline, auth
from embeddings_metadata import EmbeddingsMetadata
from embeddings_type import EmbeddingsType
from vector_db_metadata import VectorDBMetadata
from vector_db_type import VectorDBType
from batch import Batch 

class TestApp(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.client = self.app.test_client()
        auth.set_internal_api_key('test_key')
        self.headers = {
            "VectorFlowKey": auth.internal_api_key
        }

    def test_embed_endpoint(self):
        test_embeddings_metadata = EmbeddingsMetadata(EmbeddingsType.OPEN_AI)
        test_vector_db_metadata = VectorDBMetadata(VectorDBType.PINECONE, "test_index", "test_environment")

        with open('tests/fixtures/test_text.txt', 'rb') as data_file:
            response = self.client.post('/embed', 
                                        data={'SourceData': data_file, 
                                            'EmbeddingsMetadata': json.dumps(test_embeddings_metadata.to_dict()), 
                                            'VectorDBMetadata': json.dumps(test_vector_db_metadata.to_dict())},
                                        headers=self.headers)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(pipeline.get_queue_size(), 2) 

        job = pipeline.database['jobs'][response.json['JobID']]
        self.assertEqual(job.batches_processed, 0)
        self.assertEqual(job.total_batches, 2)
        self.assertEqual(job.batches_succeeded, 0)

        batch = pipeline.database['batches'][f"{job.job_id}-0"]
        self.assertEqual(batch.batch_status.value, BatchStatus.NOT_STARTED.value)

        batch_status = BatchStatus(batch.batch_status.value)
        self.assertEqual(batch_status, BatchStatus.NOT_STARTED) 

    def test_get_job_status_endpoint_no_job(self):
        response = self.client.get('/jobs/1/status', headers=self.headers)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json['error'], 'Job not found')
    
    def test_get_job_status_endpoint_job_exists(self):
        job_id = pipeline.create_job('test_webhook_url')

        response = self.client.get(f"/jobs/{job_id}/status", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['JobStatus'], 'NOT_STARTED')
    
    def test_dequeue_endpoint_empty(self):
        response = self.client.get('/dequeue', headers=self.headers)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json['error'], 'No jobs in queue') 

    def test_dequeue_endpoint_not_empty(self):
        test_embeddings_metadata = EmbeddingsMetadata(EmbeddingsType.OPEN_AI)
        test_vector_db_metadata = VectorDBMetadata(VectorDBType.PINECONE, "test_index", "test_environment")

        with open('tests/fixtures/test_text.txt', 'rb') as data_file:
            source_data=[data_file.read().decode('utf-8')]
            batch = Batch(source_data=source_data, 
                          batch_id=1,
                          job_id=1, 
                          embeddings_metadata=test_embeddings_metadata, 
                          vector_db_metadata=test_vector_db_metadata)
            pipeline.add_to_queue(batch)
        
        #check that it enqueued properly
        self.assertEqual(pipeline.get_queue_size(), 1)

        # test the dequeue endpoint
        response = self.client.get('/dequeue', headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(pipeline.get_queue_size(), 0)

        batch = response.json['batch']
        self.assertEqual(batch['job_id'], 1)
        self.assertEqual(batch['batch_id'], 1)
        self.assertEqual(batch['embeddings_metadata']['embeddings_type'], 'OPEN_AI')
        self.assertEqual(batch['vector_db_metadata']['vector_db_type'], 'PINECONE')

    def test_update_job_status_endpoint_complete(self):
        # arrange
        test_job_id = pipeline.create_job('test_webhook_url')
        test_batch = Batch(source_data='test_source_data', 
                           batch_id=12131,
                           job_id=test_job_id, 
                           embeddings_metadata=None, 
                           vector_db_metadata=None)
        pipeline.database['batches'][test_batch.batch_id] = test_batch
        pipeline.database['jobs'][test_job_id].total_batches = 1
        
        # act
        response = self.client.put(f"/jobs/{test_job_id}", json={'batch_id': 12131, 'batch_status': 'COMPLETED'}, headers=self.headers)

        # assert
        self.assertEqual(response.status_code, 200)

    def test_update_job_status_endpoint_in_progress(self):
        # arrange
        test_job_id = pipeline.create_job('test_webhook_url')
        test_batch = Batch(source_data='test_source_data', 
                           batch_id=12131,
                           job_id=test_job_id, 
                           embeddings_metadata=None, 
                           vector_db_metadata=None)
        pipeline.database['batches'][test_batch.batch_id] = test_batch
        pipeline.database['jobs'][test_job_id].total_batches = 2
        
        # act
        response = self.client.put(f"/jobs/{test_job_id}", json={'batch_id': 12131, 'batch_status': 'COMPLETED'}, headers=self.headers)

        # assert
        self.assertEqual(response.status_code, 202)
    
    def test_update_job_status_endpoint_partially_complete(self):
        # arrange
        test_job_id = pipeline.create_job('test_webhook_url')
        test_batch = Batch(source_data='test_source_data', 
                           batch_id=12131,
                           job_id=test_job_id, 
                           embeddings_metadata=None, 
                           vector_db_metadata=None)
        pipeline.database['batches'][test_batch.batch_id] = test_batch
        pipeline.database['jobs'][test_job_id].total_batches = 2
        pipeline.database['jobs'][test_job_id].batches_processed = 1
        
        # act
        response = self.client.put(f"/jobs/{test_job_id}", json={'batch_id': 12131, 'batch_status': 'COMPLETED'}, headers=self.headers)

        # assert
        self.assertEqual(response.status_code, 206)

    def test_update_job_status_endpoint_failed(self):
        # arrange
        test_job_id = pipeline.create_job('test_webhook_url')
        test_batch = Batch(source_data='test_source_data', 
                           batch_id=12131,
                           job_id=test_job_id, 
                           embeddings_metadata=None, 
                           vector_db_metadata=None)
        pipeline.database['batches'][test_batch.batch_id] = test_batch
        pipeline.database['jobs'][test_job_id].total_batches = 1
        
        # act
        response = self.client.put(f"/jobs/{test_job_id}", json={'batch_id': 12131, 'batch_status': 'FAILED'}, headers=self.headers)

        # assert
        self.assertEqual(response.status_code, 404)
        

if __name__ == '__main__':
    unittest.main()

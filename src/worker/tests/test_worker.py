import unittest
import worker.worker as worker
import worker.config as config
from models.batch import Batch
from models.embeddings_metadata import EmbeddingsMetadata
from models.job import Job
from shared.batch_status import BatchStatus
from shared.embeddings_type import EmbeddingsType
from shared.job_status import JobStatus
from unittest.mock import patch

class TestWorker(unittest.TestCase):
    @patch('sqlalchemy.orm.session.Session.refresh')
    @patch('services.database.batch_service.update_batch_status')
    @patch('services.database.job_service.update_job_status')
    @patch('services.database.database.get_db')
    @patch('services.database.job_service.get_job')
    @patch('services.database.batch_service.get_batch')
    @patch('worker.worker.embed_openai_batch')
    @patch('worker.worker.update_batch_and_job_status')
    def test_process_batch_success(
        self, 
        mock_update_batch_and_job_status, 
        mock_embed_openai_batch, 
        mock_get_batch, 
        mock_get_job, 
        mock_get_db,
        mock_update_job_status,
        mock_update_batch_status,
        mock_db_refresh):
        # arrange
        source_data = "source_data"
        job = Job(id=1, webhook_url="test_webhook_url", job_status=JobStatus.NOT_STARTED,)
        batch = Batch(id=1, job_id=1, batch_status=BatchStatus.NOT_STARTED, embeddings_metadata=EmbeddingsMetadata(embeddings_type=EmbeddingsType.OPEN_AI))
        mock_embed_openai_batch.return_value = 1
        mock_get_batch.return_value = batch
        mock_get_job.return_value = job
        mock_get_db.return_value = "test_db"

        # act
        worker.process_batch(batch, source_data)

        # assert
        mock_embed_openai_batch.assert_called_once_with(batch, source_data)
        mock_update_batch_and_job_status.assert_called_with(batch.job_id, BatchStatus.COMPLETED, batch.id)

    @patch('sqlalchemy.orm.session.Session.refresh')
    @patch('services.database.batch_service.update_batch_status')
    @patch('services.database.job_service.update_job_status')
    @patch('services.database.database.get_db')
    @patch('services.database.job_service.get_job')
    @patch('services.database.batch_service.get_batch')
    @patch('worker.worker.embed_openai_batch')
    @patch('worker.worker.update_batch_and_job_status')
    def test_process_batch_failure_no_vectors(
        self, 
        mock_update_batch_and_job_status, 
        mock_embed_openai_batch, 
        mock_get_batch, 
        mock_get_job, 
        mock_get_db,
        mock_update_job_status,
        mock_update_batch_status,
        mock_db_refresh):
        # arrange
        source_data = "source_data"
        job = Job(id=1, webhook_url="test_webhook_url", job_status=JobStatus.NOT_STARTED,)
        batch = Batch(id=1, job_id=1, batch_status=BatchStatus.NOT_STARTED, embeddings_metadata=EmbeddingsMetadata(embeddings_type=EmbeddingsType.OPEN_AI))
        mock_embed_openai_batch.return_value = 0
        mock_get_batch.return_value = batch
        mock_get_job.return_value = job
        mock_get_db.return_value = "test_db"

        # act
        worker.process_batch(batch, source_data)

        # assert
        mock_embed_openai_batch.assert_called_once_with(batch, source_data)
        mock_update_batch_and_job_status.assert_called_with(batch.job_id, BatchStatus.FAILED, batch.id)

    @patch('sqlalchemy.orm.session.Session.refresh')
    @patch('services.database.batch_service.update_batch_status')
    @patch('services.database.job_service.update_job_status')
    @patch('services.database.database.get_db')
    @patch('services.database.job_service.get_job')
    @patch('services.database.batch_service.get_batch')
    @patch('worker.worker.embed_openai_batch')
    @patch('worker.worker.update_batch_and_job_status')
    def test_process_batch_failure_openai(
        self, 
        mock_update_batch_and_job_status, 
        mock_embed_openai_batch, 
        mock_get_batch, 
        mock_get_job, 
        mock_get_db,
        mock_update_job_status,
        mock_update_batch_status,
        mock_db_refresh):
        # arrange
        source_data = "source_data"
        job = Job(id=1, webhook_url="test_webhook_url", job_status=JobStatus.NOT_STARTED,)
        batch = Batch(id=1, job_id=1, batch_status=BatchStatus.NOT_STARTED, embeddings_metadata=EmbeddingsMetadata(embeddings_type=EmbeddingsType.OPEN_AI))
        mock_embed_openai_batch.return_value = 0
        mock_get_batch.return_value = batch
        mock_get_job.return_value = job
        mock_get_db.return_value = "test_db"

        # act
        worker.process_batch(batch, source_data)

        # assert
        mock_embed_openai_batch.assert_called_once_with(batch, source_data)
        mock_update_batch_and_job_status.assert_called_with(batch.job_id, BatchStatus.FAILED, batch.id)

    def test_chunk_data(self):
        # arrange
        # 384 characters, should be 3 chunks, since the last chunk will be partial
        data = ["thisistest"] * 38
        data.append("test") 

        # act
        chunks = worker.chunk_data(data, 256, 128)

        # assert
        self.assertEqual(len(chunks), 3)
        self.assertEqual(len(chunks[2]), 128)

    def test_create_pinecone_source_chunk_dict(self):
        # arrange
        data = "thisistest" * 38 + "test"
        chunks = worker.chunk_data(data, 256, 128)
        text_embeddings_dict = [(chunk, [1.0, 2.0, 3.0, 4.0, 5.0]) for chunk in chunks]
        batch_id = 1
        job_id = 1

        # act
        upsert_list = worker.create_pinecone_source_chunk_dict(text_embeddings_dict, batch_id, job_id)

        # assert
        self.assertEqual(len(upsert_list), 3)
        self.assertEqual(upsert_list[0]['metadata']['source_text'], chunks[0])
        self.assertEqual(upsert_list[0]['values'], [1.0, 2.0, 3.0, 4.0, 5.0])

    def test_chunk_paragraph(self):
        data = ["This is an example paragraph.\n\n"] * 4
        
        chunks = worker.chunk_data_by_paragraph(data, chunk_size=35, overlap=0)

        self.assertEqual(len(chunks), 4)

    def test_chunk_paragraph_overlap(self):
        data = ["This is an example paragraph.\n\n"] * 2

        chunks = worker.chunk_data_by_paragraph(data, chunk_size=35, overlap=15)

        expected_overlap = 'This is an exam'
        self.assertEqual(chunks[0][:15], expected_overlap)

    def test_chunk_paragraph_bound(self):
        data = ["This is \n\n a very early paragraph."]

        chunks = worker.chunk_data_by_paragraph(data, chunk_size=35, overlap=0, bound=0.75)

        self.assertEqual(len(chunks), 1)

    def test_chunk_sentence(self):
        data = ["I am a sentence. I am a sentence but with a question? I am still a sentence! Can I consider myself a sentence..."]
        
        chunks = worker.chunk_by_sentence(data)

        self.assertEqual(len(chunks), 4)


    def test_create_openai_batches(self):
        # arrange
        batches = ["test"] * config.MAX_OPENAI_EMBEDDING_BATCH_SIZE * 4

        # act
        openai_batches = worker.create_openai_batches(batches)

        # assert
        self.assertEqual(len(openai_batches), 4)

if __name__ == '__main__':
    unittest.main()

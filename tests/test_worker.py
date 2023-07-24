import unittest
from src.api.batch_status import BatchStatus
import src.worker.worker as worker
from unittest.mock import patch, call

class TestWorker(unittest.TestCase):
    @patch('src.worker.worker.embed_openai_batch')
    @patch('src.worker.worker.update_job_status')
    def test_process_batch_success(self, mock_update_job_status, mock_embed_openai_batch):
        # arrange
        batch = {"embeddings_metadata": {"embeddings_type": "OPEN_AI"}, "job_id": "test_job_id", "batch_id": "test_batch_id"}
        mock_embed_openai_batch.return_value = 1

        # act
        worker.process_batch(batch)

        # assert
        mock_embed_openai_batch.assert_called_once_with(batch)
        mock_update_job_status.assert_called_with(batch['job_id'], BatchStatus.COMPLETED, batch['batch_id'])

    @patch('src.worker.worker.embed_openai_batch')
    @patch('src.worker.worker.update_job_status')
    def test_process_batch_failure_no_vectors(self, mock_update_job_status, mock_embed_openai_batch):
        # arrange
        batch = {"embeddings_metadata": {"embeddings_type": "OPEN_AI"}, "job_id": "test_job_id", "batch_id": "test_batch_id"}
        mock_embed_openai_batch.return_value = 0

        # act
        worker.process_batch(batch)

        # assert
        mock_embed_openai_batch.assert_called_once_with(batch)
        mock_update_job_status.assert_called_with(batch['job_id'], BatchStatus.FAILED, batch['batch_id'])

    @patch('src.worker.worker.embed_openai_batch')
    @patch('src.worker.worker.update_job_status')
    def test_process_batch_failure_openai(self, mock_update_job_status, mock_embed_openai_batch):
        # arrange
        batch = {"embeddings_metadata": {"embeddings_type": "OPEN_AI"}, "job_id": "test_job_id", "batch_id": "test_batch_id"}
        mock_embed_openai_batch.side_effect = Exception("Simulated Exception")

        # act
        worker.process_batch(batch)

        # assert
        mock_embed_openai_batch.assert_called_once_with(batch)
        mock_update_job_status.assert_called_with(batch['job_id'], BatchStatus.FAILED, batch['batch_id'])

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

    def test_create_source_chunk_dict(self):
        # arrange
        data = "thisistest" * 38 + "test"
        chunks = worker.chunk_data(data, 256, 128)
        embeddings = [[1.0, 2.0, 3.0, 4.0, 5.0]] * 3
        batch_id = 1
        job_id = 1

        # act
        upsert_list = worker.create_source_chunk_dict(chunks, embeddings, batch_id, job_id)

        # assert
        self.assertEqual(len(upsert_list), 3)
        self.assertEqual(upsert_list[0]['metadata']['source_text'], chunks[0])
        self.assertEqual(upsert_list[0]['id'], "1_1_0")
        self.assertEqual(upsert_list[0]['values'], embeddings[0])

if __name__ == '__main__':
    unittest.main()

import unittest
import images.image_worker as image_worker
import torch


class TestImageWorker(unittest.TestCase):
    def test_transform_vector_to_list(self):
        # arrange
        tensor = torch.randn(1, 512, 1, 1)

        # act
        result = image_worker.transform_vector_to_list(tensor)

        # assert
        self.assertEqual(len(result), 512)
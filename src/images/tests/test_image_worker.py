import unittest
import images.image_worker as image_worker
import torch
from unittest.mock import patch
from PIL import Image
from io import BytesIO

class TestImageWorker(unittest.TestCase):
    def test_transform_vector_to_list(self):
        # arrange
        tensor = torch.randn(1, 512, 1, 1)

        # act
        result = image_worker.transform_vector_to_list(tensor)

        # assert
        self.assertEqual(len(result), 512)

    @patch('img2vec_pytorch.img_to_vec.Img2Vec')
    def test_embed_image(self, mock_img2vec):
        # arrange
        # Create an image using PIL
        img = Image.new('RGB', (60, 30), color = 'red')

        # Save image to BytesIO object
        buffered = BytesIO()
        img.save(buffered, format="JPEG")

        # Get byte array from the BytesIO object
        img_byte_array = buffered.getvalue()

        tensor = torch.randn(1, 512, 1, 1)
        mock_img2vec_instance = mock_img2vec.return_value  # This will give you the instance of the mock
        mock_img2vec_instance.get_vec.return_value = tensor  # Now set the return value on that instance
        image_worker.img2vec = mock_img2vec_instance  # Assign the instance to image_worker.img2vec

        # act
        embedding = image_worker.embed_image(img_byte_array)

        # assert
        self.assertEqual(len(embedding), 512)
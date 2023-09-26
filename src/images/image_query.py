import sys
import os

# this is needed to import classes from other modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

import json
import logging
import pinecone
from flask import Flask, request, jsonify
from flask_cors import CORS
from img2vec_pytorch import Img2Vec
from shared.image_search_request import ImageSearchRequest
from shared.vector_db_type import VectorDBType
from PIL import Image
from io import BytesIO
from images.image_worker import transform_vector_to_list

logging.basicConfig(filename='./image-query-log.txt', level=logging.INFO)

img2vec = None
app = Flask(__name__)
CORS(app) 

@app.route("/search", methods=['POST'])
def search_image():
    try:
        image_bytes = request.files['SourceData'].read()
        embedding = embed_image(image_bytes)

        image_search_dict = json.loads(request.form.get('ImageSearchRequest'))
        image_search_request = ImageSearchRequest._from_dict(image_search_dict)
        results = search_vector_db(embedding, image_search_request)

        if "error" in results:
            return jsonify({"error": results["error"]}), 404

        if "vectors" in results:
            return jsonify({"vectors": results["vectors"], "similar_images": results['similar_images']}), 200
        return jsonify({"similar_images": results['similar_images']}), 200
    except Exception as e:
        logging.error(e)
        return jsonify({"error": str(e)}), 500

def embed_image(image_bytes):
    image_file = BytesIO(image_bytes)
    img = Image.open(image_file)

    # Get a vector from img2vec, returned as a torch FloatTensor
    vector_tensor = img2vec.get_vec(img, tensor=True)
    embedding_list = transform_vector_to_list(vector_tensor)
    return embedding_list

def search_vector_db(embedding, image_search_request):
    vector_db_metadata = image_search_request.vector_db_metadata
    if vector_db_metadata.vector_db_type == VectorDBType.PINECONE:
        return search_pinecone(embedding, image_search_request)
    else:
        logging.error('Unsupported vector DB type:', vector_db_metadata.vector_db_type)
        return {"error": "Unsupported vector DB type"}
    
def search_pinecone(embedding, image_search_request):
    try:
        pinecone.init(api_key=image_search_request.vector_db_key, environment=image_search_request.vector_db_metadata.environment)
        index = pinecone.GRPCIndex(image_search_request.vector_db_metadata.index_name)
        if not index:
            logging.error(f"Index {image_search_request.vector_db_metadata.index_name} does not exist in environment {image_search_request.vector_db_metadata.environment}")
            return {"error": f"Index {image_search_request.vector_db_metadata.index_name} does not exist in environment {image_search_request.vector_db_metadata.environment}"}
        
        logging.info(f"Starting pinecone query")
        query_results = index.query(
            vector=embedding,
            top_k=image_search_request.top_k,
            include_values=True,
            include_metadata=True
        )

        if not query_results:
            return {"error": "No results found"}

        results = {"similar_images": [], "vectors": []} if image_search_request.return_vectors else {"similar_images": []} 
        for match in query_results["matches"]:
            results["similar_images"].append({
                "id": match.id,
                "score": match.score,
                "metadata": match.metadata
            })
            if image_search_request.return_vectors:
                results["vectors"].append(match.values)

        return results
    
    except Exception as e:
        logging.error(e)
        return {"error": f"error querying pinecone: {str(e)}"}

if __name__ == '__main__':
   logging.info("Initializing Img2Vec on CPU.")
   img2vec = Img2Vec(cuda=False)
   app.run(host='0.0.0.0', debug=True, port=5050)
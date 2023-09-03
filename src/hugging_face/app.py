import logging
import torch
import argparse
from flask import Flask, request, jsonify
from flask_cors import CORS
from sentence_transformers import SentenceTransformer

model = None
app = Flask(__name__)
CORS(app)

logging.basicConfig(filename='./hf-log.txt', level=logging.INFO)
logging.basicConfig(filename='./hf-errors.txt', level=logging.ERROR)

@app.route("/embeddings", methods=['POST'])
def embeddings(): 
    batch = request.form.get('batch')

    try:
        # does tokenization for you
        # also capable of taking in an array of strings to be embedding
        # TODO: determine optimal amount to send to the model
        logging.info(f"Starting embedding with model: {model_name}")
        embeddings = model.encode(batch, normalize_embeddings=True)
        logging.info(f"Embedding complete with model: {model_name}")
        return jsonify({"data": embeddings.tolist()}), 200
    except Exception as e:
        logging.error('Error embedding batch:', e)
        return jsonify({"error": str(e)}), 400

def get_args():
    parser = argparse.ArgumentParser(description="Run Flask app with specified model name")
    parser.add_argument('--model_name', type=str, required=True, help='Name of the model to load')
    return parser.parse_args()

if __name__ == '__main__':
    args = get_args()
    model_name = args.model_name
    model = SentenceTransformer(model_name)
    app.run(host='0.0.0.0', port=5050, debug=True)
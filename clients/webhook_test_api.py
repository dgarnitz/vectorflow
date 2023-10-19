from flask import Flask, request, jsonify
import json
import time

app = Flask(__name__)

@app.route('/vectors', methods=['POST'])
def receive_vectors():
    # Convert request.data bytes to string
    data_str = request.data.decode('utf-8')

    # Deserialize the string
    try:
        data = json.loads(data_str)
    except json.JSONDecodeError:
        print("json error")
        return jsonify({"error": "Failed to decode the received data"}), 400

    # Extract embeddings, DocumentID, and JobID
    embeddings = data.get('Embeddings', [])
    document_id = data.get('DocumentID')
    job_id = data.get('JobID')

    # Assuming embeddings is a list of dictionaries
    # Convert the structure back to a tuple: (str, list[float])
    try:
        embeddings = [(item['text'], item['vector']) for item in embeddings]
    except (TypeError, IndexError):
        print(" #### ERROR HERE ####")
        return jsonify({"error": "Failed to parse embeddings"}), 400

    # Print the data
    print({
        "Embeddings": len(embeddings),
        "DocumentID": document_id,
        "JobID": job_id
    })

    return jsonify({"message": "Data received and printed!"}), 200

@app.route('/validate', methods=['POST'])
def validate():
    # Convert request.data bytes to string
    data_str = request.data.decode('utf-8')

    # Deserialize the string
    try:
        data = json.loads(data_str)
    except json.JSONDecodeError:
        print("json error")
        return jsonify({"error": "Failed to decode the received data"}), 400
    
    print("Received data")
    chunks = data.get('chunks')

    if not chunks:
        return jsonify({"error": "No chunks"}), 400
    
    valid_chunks = []
    for i, chunk in enumerate(chunks):
        if i % 2 == 0:
            valid_chunks.append(chunk)

    print(valid_chunks)
    return jsonify({"valid_chunks": valid_chunks}), 200


if __name__ == '__main__':
    app.run(host='localhost', port=6060)

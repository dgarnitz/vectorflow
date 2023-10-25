import requests
import json

internal_api_key = "test123"
url = "http://localhost:8000/jobs/status"
job_ids = [1,2, 3]

headers = {
    "Authorization": internal_api_key,
}

data = {
    'JobIDs': job_ids
}


print("sending request")
response = requests.post(
    url, 
    headers=headers, 
    json=data
)

print(response)
json_response = response.json()
print(json_response)

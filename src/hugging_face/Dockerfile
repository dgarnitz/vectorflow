# Use an official Python runtime as a parent image
FROM python:3.9.9-slim-buster

# The environment variable ensures that the python output is set straight
# to the terminal without buffering it first
ENV PYTHONUNBUFFERED 1

# create root application directory
WORKDIR /app

# Copy Hugging Face contents into the container at /app
COPY hugging_face /app/hugging_face

# install requirements
RUN pip install --no-cache-dir -r /app/hugging_face/requirements.txt

# Set the working directory to /app/worker, as 'worker.py' is here
WORKDIR /app/hugging_face

# Run worker.py when the container launches
ENTRYPOINT ["python", "app.py"]
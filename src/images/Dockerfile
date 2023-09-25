# Use an official Python runtime as a parent image
FROM python:3.9.9-slim-buster

# The environment variable ensures that the python output is set straight
# to the terminal without buffering it first
ENV PYTHONUNBUFFERED 1

# create root application directory
WORKDIR /app

# Copy the 'api' and 'worker' contents into the container at /app
COPY images /app/images
COPY shared /app/shared
COPY models /app/models
COPY services /app/services
COPY worker /app/worker

# install requirements
RUN pip install --no-cache-dir -r /app/images/requirements.txt

# run script to enable docker compose to sync with rabbitmq
COPY ../scripts/wait-for-it.sh /wait-for-it.sh
RUN chmod +x /wait-for-it.sh

# Set the working directory to /app/worker, as 'worker.py' is here
WORKDIR /app/images

# Run worker.py when the container launches
CMD ["python", "image_worker.py"]

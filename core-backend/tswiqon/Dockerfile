# core-backend/tswiqon/Dockerfile
FROM python:3.11-slim
# Using Python 3.11 slim version

WORKDIR /usr/src/app

# Install OS dependencies if needed later (e.g., for libraries like OpenCV)
# RUN apt-get update && apt-get install -y --no-install-recommends some-package && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Specify the command to run the listener script
CMD [ "python", "listener.py" ]
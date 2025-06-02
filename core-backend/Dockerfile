# Start from a Python base image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file for the API into the container
# This will be core-backend/requirements.txt
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code from core-backend into the container
# This will include main.py (or app.py)
COPY . .

# Expose port 8080, a common port for applications.
# Cloud Run will map external traffic to this port if specified.
EXPOSE 8080

# Command to run the FastAPI application using Uvicorn on port 8080.
# For pre-built images, a fixed port is often preferred.
# Cloud Run can then map its $PORT to this fixed container port.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--forwarded-allow-ips", "*"]
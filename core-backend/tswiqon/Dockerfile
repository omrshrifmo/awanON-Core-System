# Start from a Python base image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Add WORKDIR to PYTHONPATH to ensure modules within /app are easily discoverable
ENV PYTHONPATH /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install Python dependencies
# Ensure litellm is installed with framework-specific extras if needed e.g. [vertexai]
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
COPY . .

# Expose port 8080 for health checks (if implemented in listener.py)
EXPOSE 8080

# Command to run only the Uvicorn health check server for listener.py's health_app
# This is for testing the health check endpoint in isolation.
CMD ["sh", "-c", "uvicorn listener:health_app --host 0.0.0.0 --port ${PORT:-8080} --log-level info"]
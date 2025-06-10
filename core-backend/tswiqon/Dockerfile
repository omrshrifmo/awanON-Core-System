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

# Command to run the listener script when the container starts
# Ensure listener.py is executable or called with python
CMD ["python", "listener.py"]
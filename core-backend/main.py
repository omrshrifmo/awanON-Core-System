import os
import json
import uuid
import logging
import pika
from fastapi import FastAPI, HTTPException, BackgroundTasks, status, Request
from pydantic import BaseModel, Field
from typing import Optional, Dict

# --- Configuration ---
# Basic Logging Setup
logging.basicConfig(level=logging.INFO, format='[CoreAPI] %(asctime)s - %(levelname)s - %(message)s')

# RabbitMQ Configuration from Environment Variables
RABBITMQ_HOST = os.getenv('RABBITMQ_HOST', 'rabbitmq')
RABBITMQ_PORT = int(os.getenv('RABBITMQ_PORT', 5672))
RABBITMQ_USER = os.getenv('RABBITMQ_USER', 'user')
RABBITMQ_PASS = os.getenv('RABBITMQ_PASS', 'password')
TARGET_QUEUES = {
    "tswiqon": "tswiqon_tasks"  # Map target company name to its specific queue
    # Add other AI company queues here as they are created
}
DEFAULT_FALLBACK_QUEUE = "default_tasks_queue" # A general queue if target is unknown

# Database Configuration (Placeholders for now, will be expanded)
# DATABASE_URL = os.getenv('DATABASE_URL') 
# We'll integrate SQLAlchemy and database models in a later step.
# For now, tasks are just sent to RabbitMQ and their state is tracked by the bridge.

# --- Pydantic Models for API ---
class TaskCreationPayload(BaseModel):
    details: str = Field(..., description="The specific details or prompt for the task.")
    target_company_name: Optional[str] = Field("tswiqon", description="The target AI company service to handle the task (e.g., 'tswiqon'). Defaults to 'tswiqon'.")
    # We can add more fields like user_id, priority, etc. later

class TaskCreationResponse(BaseModel):
    task_id: str
    message: str
    status_code: int
    target_queue: str

class HealthCheckResponse(BaseModel):
    status: str = "OK"

# --- FastAPI Application Instance ---
app = FastAPI(
    title="awanON Core API",
    description="Manages tasks and interactions with awanON AI company services.",
    version="0.1.0"
)

# --- RabbitMQ Connection Helper ---
def get_rabbitmq_connection_params():
    credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
    return pika.ConnectionParameters(
        host=RABBITMQ_HOST,
        port=RABBITMQ_PORT,
        credentials=credentials,
        heartbeat=600,
        blocked_connection_timeout=300
    )

def publish_task_to_rabbitmq(task_id: str, payload: TaskCreationPayload, target_queue: str):
    try:
        connection = pika.BlockingConnection(get_rabbitmq_connection_params())
        channel = connection.channel()
        
        # Ensure the target queue exists and is durable
        channel.queue_declare(queue=target_queue, durable=True)
        
        message_body = {
            "task_id": task_id,
            "target_company_name": payload.target_company_name,
            "payload": {"details": payload.details}, # Matching the structure tswiqon_agent expects
            "sent_at": logging.Formatter().formatTime(logging.LogRecord(None,None,"",0,"",(),None,None)) # Get current time in a simple format
        }
        
        channel.basic_publish(
            exchange='',
            routing_key=target_queue,
            body=json.dumps(message_body),
            properties=pika.BasicProperties(
                delivery_mode=2,  # Make message persistent
                correlation_id=task_id # Useful for tracking later
            )
        )
        logging.info(f"Task {task_id} published to queue '{target_queue}' for company '{payload.target_company_name}'.")
        connection.close()
    except pika.exceptions.AMQPConnectionError as e:
        logging.error(f"RabbitMQ Connection Error when publishing task {task_id}: {e}")
        # Re-raise or handle as appropriate, maybe a retry mechanism later
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"Could not connect to RabbitMQ: {e}")
    except Exception as e:
        logging.error(f"Error publishing task {task_id} to RabbitMQ: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error publishing task: {e}")

# --- API Endpoints ---
@app.get("/", response_model=HealthCheckResponse, tags=["General"])
async def health_check():
    """
    Health check endpoint to confirm the API is running.
    """
    return HealthCheckResponse(status="awanON Core API is healthy and running!")

@app.post("/api/v1/tasks", 
            response_model=TaskCreationResponse, 
            status_code=status.HTTP_202_ACCEPTED,
            tags=["Tasks"])
async def create_task(payload: TaskCreationPayload, background_tasks: BackgroundTasks):
    """
    Creates a new task and dispatches it to the appropriate AI company service via RabbitMQ.
    
    - **details**: The primary prompt or instruction for the task.
    - **target_company_name**: (Optional) Specify which AI company should handle this. 
      Currently known: 'tswiqon'. Defaults to 'tswiqon'.
    """
    task_id = str(uuid.uuid4())
    logging.info(f"Received task creation request. Assigning Task ID: {task_id} for company: {payload.target_company_name}")

    target_queue = TARGET_QUEUES.get(payload.target_company_name.lower() if payload.target_company_name else "tswiqon", DEFAULT_FALLBACK_QUEUE)
    
    if target_queue == DEFAULT_FALLBACK_QUEUE and payload.target_company_name:
        logging.warning(f"Target company '{payload.target_company_name}' unknown. Routing task {task_id} to fallback queue '{DEFAULT_FALLBACK_QUEUE}'.")
        # Optionally, we could reject unknown targets if a fallback isn't desired:
        # raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Target company '{payload.target_company_name}' is not a known service.")

    # Publish to RabbitMQ in the background to avoid blocking the API response
    try:
        # Direct publish for now. For more resilience, background_tasks.add_task could be used,
        # but direct call gives immediate feedback on publishing errors here.
        publish_task_to_rabbitmq(task_id, payload, target_queue)
        
        # TODO: Here, we would also create a record in our PostgreSQL database for this task_id
        # with an initial status like 'PENDING' or 'QUEUED'.
        # This will be done in a subsequent step when DB integration is added.
        # For now, the bridge will pick up the task from RabbitMQ and create the initial DB record.
        
        return TaskCreationResponse(
            task_id=task_id, 
            message=f"Task accepted and queued for company '{payload.target_company_name}'.",
            status_code=status.HTTP_202_ACCEPTED,
            target_queue=target_queue
        )
    except HTTPException as http_exc: # Catch HTTPExceptions raised by publish_task_to_rabbitmq
        raise http_exc 
    except Exception as e: # Catch any other unexpected errors during publishing preparation
        logging.error(f"Failed to queue task {task_id} before publishing attempt: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to queue task: {e}")

# --- Placeholder for database interactions (to be added later) ---
# from sqlalchemy.orm import Session
# from . import crud, models, schemas
# from .database import SessionLocal, engine
# models.Base.metadata.create_all(bind=engine) # Create database tables (if not exist)

# def get_db():
#     db = SessionLocal()
#     try:
#         yield db
#     finally:
#         db.close()

# @app.get("/api/v1/tasks/{task_id}", tags=["Tasks"]) # Placeholder
# async def get_task_status(task_id: str, db: Session = Depends(get_db)):
#     # db_task = crud.get_task(db, task_id=task_id) # Example
#     # if db_task is None:
#     #     raise HTTPException(status_code=404, detail="Task not found")
#     # return db_task
#     raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Fetching task status not yet implemented directly in core_api. Query bridge service.")


# --- Optional: Add Middleware (e.g., for logging, auth) ---
@app.middleware("http")
async def log_requests(request: Request, call_next):
    idem = str(uuid.uuid4())
    logging.info(f"rid={idem} start request path={request.url.path} method={request.method}")
    response = await call_next(request)
    logging.info(f"rid={idem} completed_request status_code={response.status_code}")
    return response


if __name__ == "__main__":
    # This is for local debugging only. Uvicorn in CMD of Dockerfile is the primary way to run.
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
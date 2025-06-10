import os
import json
import uuid
import logging
import pika
from urllib.parse import urlparse # Ensure this is at the top
from datetime import timedelta
from fastapi import FastAPI, HTTPException, BackgroundTasks, status, Request, Depends, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import Optional, Dict

# Import our database and model components
from database import engine, get_db
from models import Base, CoreTask, User
from schemas import (
    TaskCreationPayload, TaskCreationResponse, CoreTaskResponse, HealthCheckResponse,
    UserCreate, UserResponse, Token
)
import crud
import auth_utils

# --- Configuration ---
# Basic Logging Setup
logging.basicConfig(level=logging.INFO, format='[CoreAPI] %(asctime)s - %(levelname)s - %(message)s')

# RabbitMQ Configuration from Environment Variables
RABBITMQ_URL = os.getenv('RABBITMQ_URL')
RABBITMQ_VHOST = None # Initialize RABBITMQ_VHOST

if RABBITMQ_URL:
    logging.info(f"Parsing RabbitMQ URL for connection parameters.")
    # Mask password in log
    # Ensure RABBITMQ_PASS is defined before this line if it's used from else block or globally
    # For safety, re-fetch RABBITMQ_PASS if it's only defined in the else block or ensure global scope
    temp_pass_for_logging = os.getenv('RABBITMQ_PASS', '****') # Default to **** if not set globally yet
    if RABBITMQ_URL and '@' in RABBITMQ_URL:
        url_parts = RABBITMQ_URL.split('@')
        credentials_part = url_parts[0].split('//')[1]
        if ':' in credentials_part:
             temp_pass_for_logging = credentials_part.split(':')[1]

    logging_url = RABBITMQ_URL.replace(temp_pass_for_logging, "****") if temp_pass_for_logging else RABBITMQ_URL
    logging.info(f"Original RabbitMQ URL (password masked): {logging_url}")

    parsed_url = urlparse(RABBITMQ_URL)
    RABBITMQ_HOST = parsed_url.hostname
    RABBITMQ_PORT = parsed_url.port
    RABBITMQ_USER = parsed_url.username
    RABBITMQ_PASS = parsed_url.password # This will be the one from the URL

    # Extract vhost, remove leading '/' if present
    RABBITMQ_VHOST = parsed_url.path.lstrip('/') if parsed_url.path else None
    if not RABBITMQ_VHOST: # If path is empty or just '/', default it
         RABBITMQ_VHOST = 'vbjaudbu' # Default to specific vhost if not in URL path
    logging.info(f"Parsed RabbitMQ VHost: {RABBITMQ_VHOST}")

else:
    logging.info("RabbitMQ URL not found, using individual environment variables.")
    RABBITMQ_HOST = os.getenv('RABBITMQ_HOST', 'localhost')
    RABBITMQ_PORT = int(os.getenv('RABBITMQ_PORT', 5672))
    RABBITMQ_USER = os.getenv('RABBITMQ_USER', 'guest')
    RABBITMQ_PASS = os.getenv('RABBITMQ_PASS', 'guest')
    RABBITMQ_VHOST = os.getenv('RABBITMQ_VHOST', 'vbjaudbu') # Default to specific vhost
    logging.info(f"Using RabbitMQ VHost from individual env vars (or default): {RABBITMQ_VHOST}")

TARGET_QUEUES = {
    "tswiqon": "tswiqon_tasks"  # Map target company name to its specific queue
    # Add other AI company queues here as they are created
}
DEFAULT_FALLBACK_QUEUE = "default_tasks_queue" # A general queue if target is unknown

# Database Configuration
DATABASE_URL = os.getenv('DATABASE_URL')
if DATABASE_URL:
    # Create database tables if they don't exist
    Base.metadata.create_all(bind=engine)
    logging.info("Database tables created/verified successfully.")
else:
    logging.warning("DATABASE_URL not set. Database functionality will be disabled.")

# JWT Secret Key for token generation (typically in auth_utils, but good to ensure it's loaded)
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not JWT_SECRET_KEY:
    logging.warning("JWT_SECRET_KEY is not set. This is required for authentication.")
    # Potentially raise an error or exit if JWT is critical for startup
    # raise RuntimeError("JWT_SECRET_KEY must be set in the environment for the application to start.")


# --- FastAPI Application Instance ---
app = FastAPI(
    title="awanON Core API",
    description="Manages tasks and interactions with awanON AI company services.",
    version="0.1.0"
)

# --- CORS Configuration ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins like ["http://localhost:3000", "http://localhost:5173"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Authentication Router ---
auth_router = APIRouter(prefix="/auth", tags=["Authentication"])

@auth_router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register_user(user: UserCreate, db: Session = Depends(get_db)):
    """
    Register a new user account.
    """
    # Check if username already exists
    db_user_by_username = crud.get_user_by_username(db, username=user.username)
    if db_user_by_username:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    # Check if email already exists (if provided)
    if user.email:
        db_user_by_email = crud.get_user_by_email(db, email=user.email)
        if db_user_by_email:
            raise HTTPException(status_code=400, detail="Email already registered")
    
    return crud.create_user(db=db, user=user)

@auth_router.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """
    Login endpoint to obtain JWT access token.
    """
    user = crud.get_user_by_username(db, username=form_data.username)
    if not user or not auth_utils.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=auth_utils.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth_utils.create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

# Include the authentication router
app.include_router(auth_router)

# --- RabbitMQ Connection Helper ---
def get_rabbitmq_connection_params():
    # RABBITMQ_USER, RABBITMQ_PASS, RABBITMQ_HOST, RABBITMQ_PORT, RABBITMQ_VHOST are now expected to be set globally (or module-level)
    # by the logic above.

    if not RABBITMQ_USER or not RABBITMQ_PASS: # Should not happen if variables are correctly parsed/defaulted
        logging.error("RabbitMQ username or password not set. Cannot create credentials.")
        raise ValueError("RabbitMQ username or password not configured.")

    credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)

    # Determine vhost_to_use explicitly
    # The global RABBITMQ_VHOST should be correctly set by the parsing logic or fallbacks already.
    # If it somehow ended up as None or empty string from parsing an actual URL like amqp://host// (empty path)
    # then default it here again.
    vhost_to_use = RABBITMQ_VHOST
    if not vhost_to_use: # Final safety net
        vhost_to_use = 'vbjaudbu'
        logging.warning(f"RabbitMQ VHost was empty or None after parsing/env fallback, defaulting to: {vhost_to_use}")

    logging.info(f"Attempting RabbitMQ connection with: Host={RABBITMQ_HOST}, Port={RABBITMQ_PORT}, VHost={vhost_to_use}, User={RABBITMQ_USER}")

    return pika.ConnectionParameters(
        host=RABBITMQ_HOST,
        port=RABBITMQ_PORT,
        credentials=credentials,
        virtual_host=vhost_to_use, # Crucial: ensure this is used
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
async def create_task(
    payload: TaskCreationPayload, 
    background_tasks: BackgroundTasks, 
    db: Session = Depends(get_db),
    current_user: User = Depends(auth_utils.get_current_user)
):
    """
    Creates a new task and dispatches it to the appropriate AI company service via RabbitMQ.
    
    - **details**: The primary prompt or instruction for the task.
    - **target_company_name**: (Optional) Specify which AI company should handle this. 
      Currently known: 'tswiqon'. Defaults to 'tswiqon'.
    """
    task_id = str(uuid.uuid4())
    logging.info(f"Received task creation request from user '{current_user.username}'. Assigning Task ID: {task_id} for company: {payload.target_company_name}")

    target_queue = TARGET_QUEUES.get(payload.target_company_name.lower() if payload.target_company_name else "tswiqon", DEFAULT_FALLBACK_QUEUE)
    
    if target_queue == DEFAULT_FALLBACK_QUEUE and payload.target_company_name:
        logging.warning(f"Target company '{payload.target_company_name}' unknown. Routing task {task_id} to fallback queue '{DEFAULT_FALLBACK_QUEUE}'.")
        # Optionally, we could reject unknown targets if a fallback isn't desired:
        # raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Target company '{payload.target_company_name}' is not a known service.")

    try:
        # 1. Create task record in core_api database with PENDING status
        if DATABASE_URL:
            db_task = crud.create_core_task(db, task_id, payload)
            logging.info(f"Task {task_id} created in core_api database with status: {db_task.status}")
        
        # 2. Publish to RabbitMQ
        publish_task_to_rabbitmq(task_id, payload, target_queue)
        
        # 3. Update task status to DISPATCHED
        if DATABASE_URL:
            crud.update_core_task_status(db, task_id, "DISPATCHED")
            logging.info(f"Task {task_id} status updated to DISPATCHED")
        
        return TaskCreationResponse(
            task_id=task_id, 
            message=f"Task accepted and queued for company '{payload.target_company_name}'.",
            status_code=status.HTTP_202_ACCEPTED,
            target_queue=target_queue
        )
    except HTTPException as http_exc: # Catch HTTPExceptions raised by publish_task_to_rabbitmq
        # If RabbitMQ publish failed, update task status to reflect the error
        if DATABASE_URL:
            try:
                crud.update_core_task_status(db, task_id, "FAILED")
            except Exception as db_err:
                logging.error(f"Failed to update task {task_id} status to FAILED: {db_err}")
        raise http_exc 
    except Exception as e: # Catch any other unexpected errors during publishing preparation
        logging.error(f"Failed to queue task {task_id} before publishing attempt: {e}")
        # Update task status to FAILED if it was created
        if DATABASE_URL:
            try:
                crud.update_core_task_status(db, task_id, "FAILED")
            except Exception as db_err:
                logging.error(f"Failed to update task {task_id} status to FAILED: {db_err}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to queue task: {e}")

@app.get("/api/v1/tasks/{task_id}", 
         response_model=CoreTaskResponse,
         tags=["Tasks"])
async def get_core_task_status(
    task_id: str, 
    db: Session = Depends(get_db),
    current_user: User = Depends(auth_utils.get_current_user)
):
    """
    Retrieve the status of a task from core_api's perspective.
    
    This shows the task's status as tracked by core_api (PENDING, DISPATCHED, FAILED).
    For detailed processing status and results, query the bridge service.
    """
    if not DATABASE_URL:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, 
            detail="Database not configured. Cannot retrieve task status from core_api."
        )
    
    db_task = crud.get_core_task(db, task_id=task_id)
    if db_task is None:
        raise HTTPException(status_code=404, detail="Task not found in core_api records")
    
    return db_task


@app.get("/api/v1/tasks", 
         tags=["Tasks"])
async def list_core_tasks(
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db),
    current_user: User = Depends(auth_utils.get_current_user)
):
    """
    List tasks tracked by core_api with pagination.
    
    - **skip**: Number of tasks to skip (for pagination)
    - **limit**: Maximum number of tasks to return (max 100)
    """
    if not DATABASE_URL:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, 
            detail="Database not configured. Cannot retrieve tasks from core_api."
        )
    
    if limit > 100:
        limit = 100
    
    tasks = crud.get_core_tasks(db, skip=skip, limit=limit)
    return {"tasks": tasks, "skip": skip, "limit": limit, "count": len(tasks)}


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
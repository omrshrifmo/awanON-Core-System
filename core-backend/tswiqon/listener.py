# core-backend/tswiqon/listener.py

import os
import sys
import json
import time
import signal
import logging
import threading
from urllib.parse import urlparse
import ssl

import pika
import uvicorn
from fastapi import FastAPI
from dotenv import load_dotenv

# --- Early prints to see if the script starts at all ---
print("[TswiqON] Python script starting...")

# --- Load environment variables FIRST ---
load_dotenv()
print("[TswiqON] Dotenv loaded (if .env file exists).")

# --- Setup basic logging ---
logging.basicConfig(level=logging.INFO, format='[TswiqON Agent] %(asctime)s - %(levelname)s - %(message)s')

# --- FastAPI Health Check (Defined Early) ---
health_app = FastAPI(docs_url=None, redoc_url=None, title="TswiqonAgentHealth")

@health_app.get("/healthz", status_code=200)
async def health_check_endpoint():
    """This endpoint is checked by Cloud Run to see if the container is alive."""
    # A simple 200 OK is all Cloud Run needs to consider the container started.
    return {"status": "healthy"}

def run_fastapi_health_check():
    """Starts the Uvicorn server in a separate thread."""
    port = int(os.getenv("PORT", "8081"))
    logging.info(f"HEALTH_CHECK: Starting Uvicorn health check server on host 0.0.0.0, port {port}.")
    try:
        uvicorn.run(health_app, host="0.0.0.0", port=port, log_config=None)
    except Exception as e:
        logging.critical(f"HEALTH_CHECK: Uvicorn server failed to start: {e}", exc_info=True)
        # In a real scenario, this might trigger a graceful shutdown of the main script.

# --- Main Application Logic (to be run after health check is up) ---
def run_main_application():
    """
    This function contains the core logic: RAG init and RabbitMQ connection.
    It will be called by the main thread after the health check thread has started.
    """
    try:
        # --- Heavy Imports and Initializations ---
        # By placing these here, any import errors will happen after the health check is running.
        from models import CompanyBlueprintV1 # Ensure models.py is in PYTHONPATH
        from agent_workflow import run_agent_workflow
        import rag_utils # RAG utilities for document ingestion and retrieval
        print("[TswiqON] Main application imports loaded.")

        # --- RabbitMQ Configuration ---
        RABBITMQ_URL = os.getenv('RABBITMQ_URL')
        RABBITMQ_HOST = None
        RABBITMQ_PORT = None # Will be int after parsing
        RABBITMQ_USER = None
        RABBITMQ_PASS = None
        RABBITMQ_VHOST = None
        RABBITMQ_SSL = False # For AMQPS

        if RABBITMQ_URL:
            safe_log_url = RABBITMQ_URL
            try:
                if "@" in safe_log_url:
                    scheme_user_part = safe_log_url.split("://")[0] + "://" + safe_log_url.split("://")[1].split(":")[0]
                    host_part = safe_log_url.split("@")[1]
                    safe_log_url = f"{scheme_user_part}:********@{host_part}"
            except Exception:
                pass # If parsing fails, log original
            logging.info(f"Parsing RABBITMQ_URL: {safe_log_url}")
            parsed_url = urlparse(RABBITMQ_URL)
            RABBITMQ_HOST = parsed_url.hostname
            RABBITMQ_PORT = parsed_url.port
            RABBITMQ_USER = parsed_url.username
            RABBITMQ_PASS = parsed_url.password
            RABBITMQ_VHOST = parsed_url.path.strip('/') if parsed_url.path and parsed_url.path != '/' else parsed_url.username
            if not RABBITMQ_VHOST: # Fallback for username as vhost if path is empty
                RABBITMQ_VHOST = parsed_url.username if parsed_url.username else 'guest' # Default to guest if username also empty
            if parsed_url.scheme == 'amqps':
                RABBITMQ_SSL = True
                if RABBITMQ_PORT is None: RABBITMQ_PORT = 5671
            elif parsed_url.scheme == 'amqp':
                if RABBITMQ_PORT is None: RABBITMQ_PORT = 5672
            logging.info(f"Parsed RabbitMQ params from URL: Host={RABBITMQ_HOST}, Port={RABBITMQ_PORT}, VHost={RABBITMQ_VHOST}, User={RABBITMQ_USER}, SSL={RABBITMQ_SSL}")
        else:
            logging.info("RABBITMQ_URL not set, attempting to use individual RabbitMQ environment variables.")
            RABBITMQ_HOST = os.getenv('RABBITMQ_HOST', 'rabbitmq')
            RABBITMQ_PORT = os.getenv('RABBITMQ_PORT')
            RABBITMQ_USER = os.getenv('RABBITMQ_USER', 'user')
            RABBITMQ_PASS = os.getenv('RABBITMQ_PASS', 'password')
            RABBITMQ_VHOST = os.getenv('RABBITMQ_VHOST', '/')
            RABBITMQ_SSL = os.getenv('RABBITMQ_SSL_FALLBACK', 'False').lower() == 'true'
            if RABBITMQ_PORT is None:
                RABBITMQ_PORT = "5671" if RABBITMQ_SSL else "5672"
            logging.info(f"Using individual RabbitMQ params: Host={RABBITMQ_HOST}, Port={RABBITMQ_PORT}, VHost={RABBITMQ_VHOST}, User={RABBITMQ_USER}, SSL={RABBITMQ_SSL}")

        if RABBITMQ_PORT is not None:
            try:
                RABBITMQ_PORT = int(RABBITMQ_PORT)
            except ValueError:
                default_port_for_error = 5671 if RABBITMQ_SSL else 5672
                logging.error(f"Could not convert parsed/env RABBITMQ_PORT '{RABBITMQ_PORT}' to int. Using default {default_port_for_error}.")
                RABBITMQ_PORT = default_port_for_error
        else: # This case should ideally be caught by previous checks if URL or individual vars are missing
            default_port_for_error = 5671 if RABBITMQ_SSL else 5672
            logging.critical(f"RABBITMQ_PORT is None after parsing and fallbacks. Critical misconfiguration. Using default {default_port_for_error}.")
            RABBITMQ_PORT = default_port_for_error
        
        if not RABBITMQ_VHOST: # Final vhost fallback if it's still empty (e.g. from individual env vars)
             RABBITMQ_VHOST = RABBITMQ_USER if RABBITMQ_USER else 'guest'
             logging.info(f"Applied final vhost fallback: {RABBITMQ_VHOST}")

        if not all([RABBITMQ_HOST, isinstance(RABBITMQ_PORT, int), RABBITMQ_USER, RABBITMQ_PASS, RABBITMQ_VHOST]):
            logging.critical(f"FATAL: RabbitMQ configuration incomplete after all checks. H={RABBITMQ_HOST} P={RABBITMQ_PORT}({type(RABBITMQ_PORT)}) U={RABBITMQ_USER} V={RABBITMQ_VHOST} PASS_SET={'Yes' if RABBITMQ_PASS else 'No'}")
            return # Exit the thread

        # LiteLLM Model Configuration
        LITELLM_MODEL_NAME = os.getenv('LITELLM_MODEL_NAME', 'groq/llama3-8b-8192')
        logging.info(f"Using LiteLLM model: {LITELLM_MODEL_NAME}")
        GROQ_API_KEY = os.getenv("GROQ_API_KEY")
        if "groq" in LITELLM_MODEL_NAME.lower() and not GROQ_API_KEY:
            logging.warning("LITELLM_MODEL_NAME indicates Groq, but GROQ_API_KEY is not set.")
        
        # Queues
        LISTEN_QUEUE_NAME = 'tswiqon_tasks'
        PUBLISH_QUEUE_NAME = 'tswiqon_tasks_results'

        # --- RAG Initialization ---
        logging.info("Main app thread: Initializing RAG system: Creating/Loading FAISS index...")
        rag_utils.create_and_save_faiss_index()
        logging.info("Main app thread: RAG system initialization complete.")

        # --- RabbitMQ Listening Logic ---
        def callback(ch, method, properties, body):
            task_data = json.loads(body.decode())
            task_id = task_data.get('task_id')
            target_company_name = task_data.get('target_company_name', 'Unnamed AI Company')
            details = task_data.get('payload', {}).get('details', "No details provided.")
            logging.info(f"Received task ID: {task_id} for '{target_company_name}' with details: {details}")

            graph_result = run_agent_workflow(details, target_company_name, LITELLM_MODEL_NAME)
            
            current_status = graph_result.get('status_message', 'Task completed')
            if 'error' in graph_result and graph_result['error']:
                current_status = graph_result.get('status_message', f"Task failed: {graph_result['error']}")

            result_message = {
                'task_id': task_id,
                'status': current_status,
                'result': {},
                'target_company_name': target_company_name
            }
            excluded_keys_from_graph_result = {'workflow_execution_log'}
            for key, value in graph_result.items():
                if key not in excluded_keys_from_graph_result:
                    result_message['result'][key] = value
            result_message['result']['model_used'] = LITELLM_MODEL_NAME
            workflow_log_list = graph_result.get('workflow_execution_log', [])
            execution_log_str = "\n".join(map(str, workflow_log_list))
            result_message['result']['execution_log'] = execution_log_str

            logging.info(f"Task ID {task_id}: Publishing result. Blueprint snippet: {str(result_message.get('result', {}).get('blueprint', 'N/A'))[:200]}")
            try:
                ch.basic_publish(
                    exchange='',
                    routing_key=PUBLISH_QUEUE_NAME,
                    body=json.dumps(result_message, indent=2),
                    properties=pika.BasicProperties(delivery_mode=2)
                )
                logging.info(f"Published result for task ID: {task_id} to {PUBLISH_QUEUE_NAME}")
            except Exception as e:
                logging.error(f"Failed to publish result for task ID {task_id}: {e}")
            ch.basic_ack(delivery_tag=method.delivery_tag)
            logging.info(f"Acknowledged task ID: {task_id}")

        def start_listening():
            while True:
                try:
                    credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
                    logging.info(f"RabbitMQ listener: Attempting connection to Host={RABBITMQ_HOST}, Port={RABBITMQ_PORT}, VHost={RABBITMQ_VHOST}, SSL={RABBITMQ_SSL}")
                    ssl_options = None
                    if RABBITMQ_SSL:
                        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
                        context.check_hostname = False
                        context.verify_mode = ssl.CERT_NONE
                        ssl_options = pika.SSLOptions(context=context)
                        logging.info("RabbitMQ listener: SSL/TLS enabled.")

                    connection_params = pika.ConnectionParameters(
                        host=RABBITMQ_HOST,
                        port=RABBITMQ_PORT,
                        virtual_host=RABBITMQ_VHOST,
                        credentials=credentials,
                        ssl_options=ssl_options,
                        heartbeat=600,
                        blocked_connection_timeout=300
                    )
                    connection = pika.BlockingConnection(connection_params)
                    channel = connection.channel()
                    channel.queue_declare(queue=LISTEN_QUEUE_NAME, durable=True)
                    channel.queue_declare(queue=PUBLISH_QUEUE_NAME, durable=True)
                    channel.basic_qos(prefetch_count=1)
                    channel.basic_consume(queue=LISTEN_QUEUE_NAME, on_message_callback=callback)
                    logging.info(f"RabbitMQ listener: Waiting for messages on '{LISTEN_QUEUE_NAME}'...")
                    channel.start_consuming()
                except pika.exceptions.AMQPConnectionError as e:
                    logging.error(f"RabbitMQ listener: Connection error: {e}. Retrying in 10 seconds...")
                    time.sleep(10)
                except Exception as e:
                    logging.error(f"RabbitMQ listener: An unexpected error occurred: {e}. Retrying in 10 seconds...", exc_info=True)
                    time.sleep(10)
        
        logging.info("Main app thread: Attempting to start RabbitMQ listener (start_listening())...")
        start_listening() # This call will block

    except Exception as e:
        logging.critical(f"MAIN_APP_THREAD_OUTER: An unhandled exception occurred: {e}", exc_info=True)
        # Consider how to signal the main thread or health check if this critical part fails

# --- Script Entry Point ---
if __name__ == '__main__':
    logging.info("Main thread: Initializing TswiqON Agent service...")

    # 1. Start the FastAPI Health Check server in a separate daemon thread.
    # This thread will start IMMEDIATELY and respond to Cloud Run.
    health_thread = threading.Thread(target=run_fastapi_health_check, daemon=True, name="HealthCheckThread")
    health_thread.start()
    logging.info("Main thread: Health check server thread initiated.")

    # Give a very brief moment for the health thread to potentially log its startup
    time.sleep(0.1)

    # 2. Start the main application logic in the main thread.
    # This can take a long time to initialize (RAG, etc.), but it won't block the health check.
    logging.info("Main thread: Starting main application logic (run_main_application)...")
    run_main_application()

    # If run_main_application ever exits (which it shouldn't unless there's a critical error
    # in start_listening that isn't handled by its internal retry loop), the container will stop.
    logging.info("Main thread: Main application loop (run_main_application) has exited. Agent shutting down.")
    # The main thread exiting will cause the container to exit.
    # Daemon threads (like health_thread) are automatically stopped when no non-daemon threads are left.
import pika
import os
import json
import time
import logging
from typing import TypedDict, Optional, List, Tuple, Annotated, Sequence # Added Sequence
import uvicorn # Added for health check
from fastapi import FastAPI # Added for health check
import threading # Added for health check
from urllib.parse import urlparse # Ensure this is at the top
import ssl # Added for RabbitMQ SSL
# os is already imported
from pydantic import ValidationError
from litellm import completion, BudgetManager # budget_manager for cost tracking (optional)
from models import CompanyBlueprintV1 # Make sure models.py is in the same directory or PYTHONPATH is set
from agent_workflow import run_agent_workflow
import rag_utils # RAG utilities for document ingestion and retrieval

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='[TswiqON Agent] %(asctime)s - %(levelname)s - %(message)s')


# --- FastAPI Health Check (Run in a separate thread) ---
health_app = FastAPI(docs_url=None, redoc_url=None, title="TswiqonAgentHealth")

@health_app.get("/healthz", status_code=200)
async def health_check_endpoint():
    # Basic health check, can be expanded later if needed
    return {"status": "healthy", "message": "Tswiqon Agent is running."}

def run_fastapi_health_check():
    port = int(os.getenv("PORT", "8080")) # Use PORT from Cloud Run, default 8080
    logging.info(f"HEALTH_CHECK: Attempting to start Uvicorn on host 0.0.0.0 port {port} for health endpoint /healthz.")
    # Using log_config=None to prevent Uvicorn from overriding root logger, if desired.
    # Otherwise, uvicorn's default log_level="info" is often acceptable.
    uvicorn.run(health_app, host="0.0.0.0", port=port, log_config=None)
# --- End FastAPI Health Check ---


# RabbitMQ Configuration
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
        # Basic password masking for logging
        if "@" in safe_log_url:
            scheme_user_part = safe_log_url.split("://")[0] + "://" + safe_log_url.split("://")[1].split(":")[0]
            host_part = safe_log_url.split("@")[1]
            safe_log_url = f"{scheme_user_part}:********@{host_part}"
    except Exception:
        pass # If parsing fails, log original
    logging.info(f"Parsing RABBITMQ_URL: {safe_log_url}")

    # from urllib.parse import urlparse # Ensure this import is present
    parsed_url = urlparse(RABBITMQ_URL)

    RABBITMQ_HOST = parsed_url.hostname
    RABBITMQ_PORT = parsed_url.port
    RABBITMQ_USER = parsed_url.username
    RABBITMQ_PASS = parsed_url.password

    RABBITMQ_VHOST = parsed_url.path.strip('/') if parsed_url.path and parsed_url.path != '/' else parsed_url.username
    if not RABBITMQ_VHOST:
        RABBITMQ_VHOST = 'guest'

    if parsed_url.scheme == 'amqps':
        RABBITMQ_SSL = True
        if RABBITMQ_PORT is None:
            RABBITMQ_PORT = 5671
    elif parsed_url.scheme == 'amqp':
        if RABBITMQ_PORT is None:
            RABBITMQ_PORT = 5672

    logging.info(f"Parsed RabbitMQ params: Host={RABBITMQ_HOST}, Port={RABBITMQ_PORT}, VHost={RABBITMQ_VHOST}, User={RABBITMQ_USER}, SSL={RABBITMQ_SSL}")

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
else:
    default_port_for_error = 5671 if RABBITMQ_SSL else 5672
    logging.critical(f"RABBITMQ_PORT is None after parsing and fallbacks. Critical misconfiguration. Using default {default_port_for_error}.")
    RABBITMQ_PORT = default_port_for_error

if not RABBITMQ_VHOST:
    RABBITMQ_VHOST = RABBITMQ_USER if RABBITMQ_USER else 'guest'
    logging.info(f"Applied final vhost fallback: {RABBITMQ_VHOST}")

# LiteLLM Model Configuration
LITELLM_MODEL_NAME = os.getenv('LITELLM_MODEL_NAME', 'groq/llama3-8b-8192')
logging.info(f"Using LiteLLM model: {LITELLM_MODEL_NAME}")
# Note: LiteLLM expects API keys (e.g., GROQ_API_KEY, OPENAI_API_KEY) to be set as environment variables.
# This script doesn't handle them directly but relies on LiteLLM's internal environment variable loading.
# Ensure GROQ_API_KEY is set in the environment if using a Groq model.
GROQ_API_KEY = os.getenv("GROQ_API_KEY") # Explicitly get it for logging or other direct use if needed.
if "groq" in LITELLM_MODEL_NAME.lower() and not GROQ_API_KEY:
    logging.warning("LITELLM_MODEL_NAME indicates Groq, but GROQ_API_KEY is not set in the environment.")
elif not GROQ_API_KEY and "groq" not in LITELLM_MODEL_NAME.lower():
    logging.info("GROQ_API_KEY is not set, which is expected if not using a Groq model.")
else:
    logging.info("GROQ_API_KEY is set.")


# Optional: Setup a budget manager for LiteLLM if you want to track costs
# budget_manager = BudgetManager(project_name="awanon_tswiqon")

# Name of the queues for TswiqON agent
LISTEN_QUEUE_NAME = 'tswiqon_tasks'
PUBLISH_QUEUE_NAME = 'tswiqon_tasks_results'

def get_llm_response_for_blueprint(task_details_str: str, target_company_name: str) -> (dict, str):
    """
    Generates a company blueprint using an LLM, attempting to format the output
    according to the CompanyBlueprintV1 Pydantic model.
    """
    system_prompt = (
        "You are an expert strategic business consultant AI. Your task is to generate a detailed company blueprint "
        "based on a given specialization. The output MUST be a valid JSON object that conforms to the "
        "CompanyBlueprintV1 Pydantic model. Respond with *ONLY* the JSON object and nothing else. "
        "Do not include any markdown formatting like ```json or ``` at the beginning or end. "
        "Do not include any explanatory text or conversation outside of the JSON structure itself. "
        f"The company blueprint is for '{target_company_name}'. "
        "The JSON must include these exact fields: "
        "- company_name_suggestion: string (creative name for the AI company) "
        "- specialization: string (the given specialization) "
        "- mission_statement_draft: string (at least 20 characters) "
        "- key_ai_employee_roles: array of objects with role_title, responsibilities (array), and optional reports_to "
        "- initial_sop_ideas: array of 3-5 strings for Standard Operating Procedures "
        "- estimated_time_to_operational_setup_days: number (optional) "
        "The specialization for the company is: " + task_details_str
    )
    
    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": f"Generate the company blueprint for a company specializing in: {task_details_str}"}]

    try:
        logging.info(f"Sending request to LLM: {LITELLM_MODEL_NAME} for task related to: {task_details_str}")
        # Using LiteLLM's ability to directly get Pydantic model (for OpenAI-compatible models)
        # For models that don't directly support 'response_model', we'd parse JSON and validate.
        # Groq with Llama3 should work well with JSON mode or structured output prompting.
        
        # Forcing JSON output if model supports it (many OpenAI-compatible models do)
        response = completion(
            model=LITELLM_MODEL_NAME,
            messages=messages,
            # For OpenAI models and some others that support it:
            response_format={"type": "json_object"}, 
            # Or if using Instructor with LiteLLM:
            # response_model=CompanyBlueprintV1,
            # max_tokens=2000 # Adjust as needed
        )
        
        llm_output_content = response.choices[0].message.content
        logging.info(f"Raw LLM Output: {llm_output_content[:500]}...") # Log snippet of raw output

        try:
            # Attempt to parse the LLM string output as JSON
            blueprint_data = json.loads(llm_output_content)
            # Validate with Pydantic
            CompanyBlueprintV1(**blueprint_data) 
            logging.info(f"Successfully generated and validated blueprint for: {target_company_name}")
            return blueprint_data, LITELLM_MODEL_NAME
        except json.JSONDecodeError as e:
            logging.error(f"JSONDecodeError from LLM output: {e}")
            logging.error(f"Problematic LLM output snippet: {llm_output_content[:500]}")
            return {"error": "LLM output was not valid JSON.", "details": str(e), "raw_output": llm_output_content}, LITELLM_MODEL_NAME
        except ValidationError as e:
            logging.error(f"Pydantic ValidationError for blueprint: {e}")
            logging.error(f"Problematic LLM output snippet: {llm_output_content[:500]}")
            return {"error": "LLM output did not conform to Pydantic model.", "details": str(e), "raw_output": llm_output_content}, LITELLM_MODEL_NAME

    except Exception as e:
        logging.error(f"Error calling LLM or processing its response: {e}")
        return {"error": "Failed to get valid response from LLM.", "details": str(e)}, LITELLM_MODEL_NAME


def callback(ch, method, properties, body):
    task_data = json.loads(body.decode())
    task_id = task_data.get('task_id')
    target_company_name = task_data.get('target_company_name', 'Unnamed AI Company') # Default if not provided
    details = task_data.get('payload', {}).get('details', "No details provided.")

    logging.info(f"Received task ID: {task_id} for '{target_company_name}' with details: {details}")

    # Use LangGraph workflow instead of single LLM call
    graph_result = run_agent_workflow(details, target_company_name, LITELLM_MODEL_NAME)

    # Prepare the main part of the result, excluding log for now
    # final_blueprint_data = graph_result.get('blueprint', {}) # This is already under 'result' in the new structure
    # current_status = 'completed_langgraph_blueprint' if 'error' not in graph_result else 'failed_langgraph_blueprint'

    # Determine status based on presence of 'error' key in graph_result
    # The 'status_message' from graph_result can also be used for more detailed status.
    current_status = graph_result.get('status_message', 'Task completed') # Default to this
    if 'error' in graph_result and graph_result['error']:
        current_status = graph_result.get('status_message', f"Task failed: {graph_result['error']}")


    result_message = {
        'task_id': task_id,
        'status': current_status, # Use the status from graph_result or a derived one
        'result': {
            # Spread other keys from graph_result like 'blueprint', 'validation_result', 'workflow_steps', 'error' etc.
            # but be careful not to overwrite 'execution_log' if it's also a top-level key in graph_result
        },
        'target_company_name': target_company_name
    }

    # Populate result_message['result'] carefully
    # Keys to exclude from direct spreading if they are handled differently or part of 'result.blueprint'
    excluded_keys_from_graph_result = {'workflow_execution_log'} # 'status_message' is used for top-level status

    for key, value in graph_result.items():
        if key not in excluded_keys_from_graph_result:
            result_message['result'][key] = value

    result_message['result']['model_used'] = LITELLM_MODEL_NAME # Add model_name

    # Process and add execution_log
    workflow_log_list = graph_result.get('workflow_execution_log', [])
    execution_log_str = "\n".join(map(str, workflow_log_list))
    result_message['result']['execution_log'] = execution_log_str


    # Ensure 'task_id' is available in this scope, or extract from result_message if necessary
    # Assuming task_id was part of the initial message or derived earlier in the callback
    task_id_for_log = result_message.get('task_id', 'UNKNOWN_TASK_ID') # Get task_id from result_message or use a placeholder

    logging.info(f"Task ID {task_id_for_log}: Publishing result_message. Blueprint content (first 500 chars): {str(result_message.get('result', {}).get('blueprint', 'N/A'))[:500]}")

    blueprint_content = result_message.get('result', {}).get('blueprint')
    if isinstance(blueprint_content, dict) and 'error' in blueprint_content:
        logging.error(f"Task ID {task_id_for_log}: Blueprint field in result_message contains an error object: {blueprint_content}")
    elif blueprint_content is None:
        logging.warning(f"Task ID {task_id_for_log}: Blueprint field in result_message is None.")
    elif not blueprint_content: # Catches empty string, empty dict, empty list etc.
        logging.warning(f"Task ID {task_id_for_log}: Blueprint field in result_message is empty or falsy: '{blueprint_content}'")

    try:
        ch.basic_publish(
            exchange='',
            routing_key=PUBLISH_QUEUE_NAME,
            body=json.dumps(result_message, indent=2), # Pretty print for easier debugging in RabbitMQ
            properties=pika.BasicProperties(delivery_mode=2) # Make message persistent
        )
        logging.info(f"Published result for task ID: {task_id} to {PUBLISH_QUEUE_NAME}")
    except Exception as e:
        logging.error(f"Failed to publish result for task ID {task_id}: {e}")

    ch.basic_ack(delivery_tag=method.delivery_tag)
    logging.info(f"Acknowledged task ID: {task_id}")


def start_listening():
    while True:
        try:
            # Global vars RABBITMQ_USER, RABBITMQ_PASS, RABBITMQ_HOST, RABBITMQ_PORT, RABBITMQ_VHOST, RABBITMQ_SSL are used here.
            if not all([RABBITMQ_HOST, isinstance(RABBITMQ_PORT, int), RABBITMQ_USER, RABBITMQ_PASS, RABBITMQ_VHOST]):
                 logging.error(f"RabbitMQ configuration incomplete: H={RABBITMQ_HOST} P={RABBITMQ_PORT}({type(RABBITMQ_PORT)}) U={RABBITMQ_USER} V={RABBITMQ_VHOST} PASS_SET={'Yes' if RABBITMQ_PASS else 'No'}")
                 # Optional: raise an error or exit if this is critical, or just wait and retry.
                 time.sleep(10) # Wait before retrying connection setup
                 continue

            credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
            logging.info(f"Final RabbitMQ connection params for listener: Host={RABBITMQ_HOST}, Port={RABBITMQ_PORT}, VHost={RABBITMQ_VHOST}, SSL={RABBITMQ_SSL}")

            ssl_options = None
            if RABBITMQ_SSL:
                # import ssl # Ensure ssl is imported locally if not globally for this function
                context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
                ssl_options = pika.SSLOptions(context=context)
                logging.info("SSL/TLS enabled for RabbitMQ connection in listener.")

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

            # Declare durable queues
            channel.queue_declare(queue=LISTEN_QUEUE_NAME, durable=True)
            channel.queue_declare(queue=PUBLISH_QUEUE_NAME, durable=True)
            
            channel.basic_qos(prefetch_count=1) # Process one message at a time
            channel.basic_consume(queue=LISTEN_QUEUE_NAME, on_message_callback=callback)

            logging.info(f"TswiqON Agent connected to RabbitMQ on host '{RABBITMQ_HOST}'. Waiting for messages on '{LISTEN_QUEUE_NAME}'...")
            channel.start_consuming()
        
        except pika.exceptions.AMQPConnectionError as e:
            logging.error(f"RabbitMQ connection error: {e}. Retrying in 10 seconds...")
            time.sleep(10)
        except Exception as e:
            logging.error(f"An unexpected error occurred in start_listening: {e}. Retrying in 10 seconds...")
            time.sleep(10)


if __name__ == '__main__':
    # Ensure logging is configured early (already done at global scope)

    logging.info("Main thread: Initializing listener service...")

    # Start health check thread early
    health_thread = threading.Thread(target=run_fastapi_health_check, daemon=True)
    health_thread.start()
    logging.info("Main thread: Health check server thread started.")

    # main_tasks_failed = False # Not strictly needed in this simplified version
    try:
        # logging.info("Main thread: Starting RAG initialization and RabbitMQ listener setup...")
        # logging.info("Main thread: Initializing RAG system: Creating/Loading FAISS index...")
        # rag_utils.create_and_save_faiss_index() # Assuming this can raise exceptions
        # logging.info("Main thread: RAG system initialization complete.")

        # logging.info("Main thread: Attempting to start RabbitMQ listener (start_listening())...")
        # start_listening() # This is expected to be a blocking call that loops internally

        # logging.info("Main thread: start_listening() has exited.")
        # main_tasks_failed = True # Treat this as a failure to keep listening

        logging.info("Main thread: Simplified startup for port test. RAG and RabbitMQ listener are bypassed. Entering keep-alive sleep.")
        while True:
            time.sleep(3600) # Sleep for 1 hour
            logging.info("Main thread: Still alive in simplified test mode. Health check should be responsive.")

    except KeyboardInterrupt:
        logging.info("Main thread (simplified test): Listener service interrupted by user.")
        # main_tasks_failed = True
    except Exception as e:
        logging.critical(f"Main thread (simplified test): An unhandled exception occurred: {e}", exc_info=True)
        # main_tasks_failed = True
    # finally: # Finally block not strictly needed if the loop is the main point
        # logging.info("Main thread: Main task execution block finished or encountered an error.")

    # The script will only reach here if the keep-alive loop is broken by an unhandled exception
    # not caught by the generic Exception, or if a system exit signal is received.
    # The main_tasks_failed logic is removed as the primary purpose now is just to keep alive.
    logging.info("Main thread: Listener service (simplified test mode) shutting down.")
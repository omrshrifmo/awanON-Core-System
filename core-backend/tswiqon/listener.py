import pika
import os
import json
import time
import logging
from pydantic import ValidationError
from litellm import completion, BudgetManager # budget_manager for cost tracking (optional)
from models import CompanyBlueprintV1 # Make sure models.py is in the same directory or PYTHONPATH is set
from agent_workflow import run_agent_workflow

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='[TswiqON Agent] %(asctime)s - %(levelname)s - %(message)s')

# RabbitMQ connection parameters from environment variables
RABBITMQ_HOST = os.getenv('RABBITMQ_HOST', 'localhost')
RABBITMQ_PORT = int(os.getenv('RABBITMQ_PORT', 5672))
RABBITMQ_USER = os.getenv('RABBITMQ_USER', 'user')
RABBITMQ_PASS = os.getenv('RABBITMQ_PASS', 'password')
credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)

# LiteLLM Model Configuration
LITELLM_MODEL_NAME = os.getenv('LITELLM_MODEL_NAME', 'groq/llama3-8b-8192')
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
    blueprint_result = run_agent_workflow(details, target_company_name, LITELLM_MODEL_NAME)

    result_message = {
        'task_id': task_id,
        'status': 'completed_langgraph_blueprint' if 'error' not in blueprint_result else 'failed_langgraph_blueprint',
        'result': {
            **blueprint_result,
            'model_used': LITELLM_MODEL_NAME
        },
        'target_company_name': target_company_name
    }

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
            connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST, port=RABBITMQ_PORT, credentials=credentials, heartbeat=600, blocked_connection_timeout=300))
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
    try:
        start_listening()
    except KeyboardInterrupt:
        logging.info("TswiqON Agent shutting down...")
    except Exception as e:
        logging.critical(f"TswiqON Agent failed to start: {e}")
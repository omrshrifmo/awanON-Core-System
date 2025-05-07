# core backend/tswiqon/listener.py
import pika
import time
import os
import json
import sys
import signal

# --- Configuration ---
RABBITMQ_URL = os.environ.get('RABBITMQ_URL')
COMPANY_QUEUE = os.environ.get('COMPANY_QUEUE') # Queue this company listens to
COMPANY_NAME = os.environ.get('COMPANY_NAME', 'AI_Company')
RESPONSE_QUEUE = 'bridge_task_updates_queue' # Queue to send responses/updates back to the bridge

if not RABBITMQ_URL:
    print(f"[{COMPANY_NAME}] FATAL ERROR: RABBITMQ_URL environment variable is not set.", file=sys.stderr)
    sys.exit(1)
if not COMPANY_QUEUE:
    print(f"[{COMPANY_NAME}] FATAL ERROR: COMPANY_QUEUE environment variable is not set.", file=sys.stderr)
    sys.exit(1)

connection = None
consuming_channel = None
publishing_channel = None

# --- Graceful Shutdown Handler ---
def shutdown(signum, frame):
    global connection, consuming_channel, publishing_channel
    print(f"\n[{COMPANY_NAME}] Received shutdown signal ({signum}). Closing RabbitMQ resources...")
    # Stop consuming first
    if consuming_channel and consuming_channel.is_open:
        try:
            consuming_channel.stop_consuming()
            print(f"[{COMPANY_NAME}] Stopped consuming.")
        except Exception as e:
            print(f"[{COMPANY_NAME}] Error stopping consuming: {e}", file=sys.stderr)
    # Close publishing channel
    if publishing_channel and publishing_channel.is_open:
        try:
            publishing_channel.close()
            print(f"[{COMPANY_NAME}] Publishing channel closed.")
        except Exception as e:
            print(f"[{COMPANY_NAME}] Error closing publishing channel: {e}", file=sys.stderr)
    # Close connection
    if connection and connection.is_open:
        try:
            connection.close()
            print(f"[{COMPANY_NAME}] RabbitMQ connection closed.")
        except Exception as e:
            print(f"[{COMPANY_NAME}] Error closing connection: {e}", file=sys.stderr)
    sys.exit(0)

signal.signal(signal.SIGTERM, shutdown)
signal.signal(signal.SIGINT, shutdown)

# --- Function to Publish Response ---
def publish_response(task_id, status, details=None, result=None):
    global connection, publishing_channel # Ensure we use the global vars
    response_message = {
        "task_id": task_id,
        "status_update": status,
        "details": details,
        "result": result, # Include result data if any
        "timestamp": time.time()
    }
    try:
        # Ensure channel is available
        if not publishing_channel or not publishing_channel.is_open:
            if connection and connection.is_open:
                publishing_channel = connection.channel()
                # Declare the response queue here as well (makes publisher robust)
                publishing_channel.queue_declare(queue=RESPONSE_QUEUE, durable=True)
                print(f"[{COMPANY_NAME}] Re-established publishing channel.")
            else:
                print(f"[{COMPANY_NAME}] Cannot publish response: Connection is not open.", file=sys.stderr)
                return # Or try reconnecting the whole connection

        publishing_channel.basic_publish(
            exchange='',
            routing_key=RESPONSE_QUEUE,
            body=json.dumps(response_message),
            properties=pika.BasicProperties(
                delivery_mode=2,  # Make message persistent
            ))
        print(f"[{COMPANY_NAME}] Published response for task {task_id} to queue '{RESPONSE_QUEUE}': Status={status}")
    except Exception as e:
        print(f"[{COMPANY_NAME}] Error publishing response for task {task_id}: {e}", file=sys.stderr)
        # Consider error handling - maybe try reconnecting publish channel

# --- RabbitMQ Message Callback ---
def callback(ch, method, properties, body):
    print(f"\n[{COMPANY_NAME}] Received message (Delivery Tag: {method.delivery_tag}):")
    task_id = None # Define task_id outside try block
    try:
        message_body_str = body.decode('utf-8')
        message_data = json.loads(message_body_str)
        task_id = message_data.get('taskId', 'N/A') # Extract task_id early

        print(f"  Task ID: {task_id}")
        print(f"  Payload: {message_data.get('payload', 'N/A')}")
        print(f"  Sent At: {message_data.get('sentAt', 'N/A')}")

        # --- TODO: Replace this print with actual processing logic ---
        # e.g., parse payload, pass to LangGraph/CEO agent
        print(f"[{COMPANY_NAME}] Simulating processing for task {task_id}...")
        # Send "acknowledged" status back immediately
        publish_response(task_id, f"acknowledged_by_{COMPANY_NAME}", details="Task received, processing started.")
        time.sleep(2) # Simulate work
        # --- End TODO ---

        # Simulate completion and send result
        # In a real scenario, this would happen after agent processing finishes
        final_result = {"summary": f"Completed work for task {task_id}", "output_file": f"/path/to/result_{task_id}.txt"}
        publish_response(task_id, "completed_simple", details="Task processing finished.", result=final_result)


    except json.JSONDecodeError:
        print(f"  Error: Could not decode JSON from body.", file=sys.stderr)
        # Publish failure status if task_id was parsed? Maybe not if format is wrong.
    except UnicodeDecodeError:
        print(f"  Error: Could not decode body as UTF-8.", file=sys.stderr)
    except Exception as e:
        print(f"  Error processing message: {e}", file=sys.stderr)
        # Publish failure status if task_id is available
        if task_id and task_id != 'N/A':
            publish_response(task_id, "failed", details=f"Error during processing: {e}")

    # Acknowledge the original message from the company queue
    print(f"[{COMPANY_NAME}] Acknowledging original task message {task_id}.")
    try:
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as e:
        print(f"[{COMPANY_NAME}] Error acknowledging message {task_id}: {e}", file=sys.stderr)


# --- Main Connection and Consumption Logic ---
def main():
    global connection, consuming_channel, publishing_channel
    print(f"[{COMPANY_NAME}] Listener starting...")
    print(f"[{COMPANY_NAME}] Attempting to connect to RabbitMQ at {RABBITMQ_URL}...")
    parameters = pika.URLParameters(RABBITMQ_URL)
    connection = None
    attempts = 0
    max_attempts = 15
    wait_time = 5

    # Robust connection loop
    while attempts < max_attempts:
        try:
            connection = pika.BlockingConnection(parameters)
            print(f"[{COMPANY_NAME}] Connected to RabbitMQ!")
            break
        except pika.exceptions.AMQPConnectionError as e:
            attempts += 1
            print(f"[{COMPANY_NAME}] Connection attempt {attempts}/{max_attempts} failed: {e}. Retrying in {wait_time} seconds...")
            time.sleep(wait_time)
        except Exception as e:
            attempts += 1
            print(f"[{COMPANY_NAME}] An unexpected error during connection attempt {attempts}/{max_attempts}: {e}. Retrying in {wait_time} seconds...")
            time.sleep(wait_time)

    if not connection or not connection.is_open:
        print(f"[{COMPANY_NAME}] Could not connect to RabbitMQ after {max_attempts} attempts. Exiting.", file=sys.stderr)
        sys.exit(1)

    try:
        # Create separate channels for consuming and publishing if desired, or reuse one carefully
        consuming_channel = connection.channel()
        publishing_channel = connection.channel() # Create channel for publishing responses

        # Declare the queue this listener consumes from
        consuming_channel.queue_declare(queue=COMPANY_QUEUE, durable=True)
        print(f"[{COMPANY_NAME}] Declared consuming queue '{COMPANY_QUEUE}'.")

        # Declare the queue this listener publishes responses to
        publishing_channel.queue_declare(queue=RESPONSE_QUEUE, durable=True)
        print(f"[{COMPANY_NAME}] Declared response queue '{RESPONSE_QUEUE}'.")

        consuming_channel.basic_qos(prefetch_count=1) # Process one message at a time
        consuming_channel.basic_consume(queue=COMPANY_QUEUE, on_message_callback=callback)

        print(f"[{COMPANY_NAME}] Waiting for messages on queue '{COMPANY_QUEUE}'. To exit press CTRL+C or send SIGTERM")
        consuming_channel.start_consuming() # This blocks until shutdown

    except Exception as e:
        print(f"[{COMPANY_NAME}] An error occurred during setup or consumption: {e}", file=sys.stderr)
    finally:
        # Cleanup is now handled by the signal handler (shutdown function) mostly
        print(f"[{COMPANY_NAME}] Exiting main function.")
        if connection and connection.is_open:
            try:
                connection.close()
                print(f"[{COMPANY_NAME}] Final RabbitMQ connection closed.")
            except Exception as e:
                print(f"[{COMPANY_NAME}] Error closing connection in finally: {e}", file=sys.stderr)


if __name__ == '__main__':
    main()
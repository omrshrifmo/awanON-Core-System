# core backend/tswiqon/listener.py
import pika
import time
import os
import json
import sys
import signal # For graceful shutdown

# --- Configuration ---
RABBITMQ_URL = os.environ.get('RABBITMQ_URL')
QUEUE_NAME = os.environ.get('COMPANY_QUEUE')
COMPANY_NAME = os.environ.get('COMPANY_NAME', 'AI_Company')

if not RABBITMQ_URL:
    print(f"[{COMPANY_NAME}] FATAL ERROR: RABBITMQ_URL environment variable is not set.", file=sys.stderr)
    sys.exit(1)
if not QUEUE_NAME:
    print(f"[{COMPANY_NAME}] FATAL ERROR: COMPANY_QUEUE environment variable is not set.", file=sys.stderr)
    sys.exit(1)

connection = None
channel = None

# --- Graceful Shutdown Handler ---
def shutdown(signum, frame):
    global connection, channel
    print(f"\n[{COMPANY_NAME}] Received shutdown signal ({signum}). Closing RabbitMQ connection...")
    if channel and channel.is_open:
        try:
            channel.stop_consuming()
            print(f"[{COMPANY_NAME}] Stopped consuming.")
        except Exception as e:
            print(f"[{COMPANY_NAME}] Error stopping consuming: {e}", file=sys.stderr)
    if connection and connection.is_open:
        try:
            connection.close()
            print(f"[{COMPANY_NAME}] RabbitMQ connection closed.")
        except Exception as e:
            print(f"[{COMPANY_NAME}] Error closing connection: {e}", file=sys.stderr)
    sys.exit(0)

signal.signal(signal.SIGTERM, shutdown)
signal.signal(signal.SIGINT, shutdown)

# --- RabbitMQ Message Callback ---
def callback(ch, method, properties, body):
    print(f"\n[{COMPANY_NAME}] Received message (Delivery Tag: {method.delivery_tag}):")
    try:
        # Decode body assuming UTF-8 encoding
        message_body_str = body.decode('utf-8')
        message_data = json.loads(message_body_str)
        print(f"  Task ID: {message_data.get('taskId', 'N/A')}")
        print(f"  Payload: {message_data.get('payload', 'N/A')}")
        print(f"  Sent At: {message_data.get('sentAt', 'N/A')}")
        # --- TODO: Replace this print with actual processing logic ---
        # e.g., parse the task, pass it to the AI CEO / LangGraph entrypoint
        print(f"[{COMPANY_NAME}] Simulating processing...")
        time.sleep(1) # Simulate work
        # --- End TODO ---

    except json.JSONDecodeError:
        print(f"  Error: Could not decode JSON from body.", file=sys.stderr)
        print(f"  Raw Body (first 100 chars): {body[:100]}", file=sys.stderr)
    except UnicodeDecodeError:
        print(f"  Error: Could not decode body as UTF-8.", file=sys.stderr)
        print(f"  Raw Body (first 100 chars): {body[:100]}", file=sys.stderr)
    except Exception as e:
        print(f"  Error processing message: {e}", file=sys.stderr)

    # Acknowledge that the message has been received and processed (or failed)
    # This removes it from the queue. If it's not ack'd, RabbitMQ will re-queue it.
    print(f"[{COMPANY_NAME}] Acknowledging message.")
    try:
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as e:
        print(f"[{COMPANY_NAME}] Error acknowledging message: {e}", file=sys.stderr)


# --- Main Connection and Consumption Logic ---
def main():
    global connection, channel
    print(f"[{COMPANY_NAME}] Listener starting...")
    print(f"[{COMPANY_NAME}] Attempting to connect to RabbitMQ...")
    # Using URLParameters allows connecting via the environment variable URL
    parameters = pika.URLParameters(RABBITMQ_URL)
    connection = None
    attempts = 0
    max_attempts = 15 # Increased attempts
    wait_time = 5 # seconds

    # Robust connection loop
    while attempts < max_attempts:
        try:
            connection = pika.BlockingConnection(parameters)
            print(f"[{COMPANY_NAME}] Connected to RabbitMQ!")
            break # Exit loop on success
        except pika.exceptions.AMQPConnectionError as e:
            attempts += 1
            print(f"[{COMPANY_NAME}] Connection attempt {attempts}/{max_attempts} failed: {e}. Retrying in {wait_time} seconds...")
            time.sleep(wait_time)
        except Exception as e: # Catch other potential exceptions
            attempts += 1
            print(f"[{COMPANY_NAME}] An unexpected error occurred during connection attempt {attempts}/{max_attempts}: {e}. Retrying in {wait_time} seconds...")
            time.sleep(wait_time)


    if not connection or not connection.is_open:
        print(f"[{COMPANY_NAME}] Could not connect to RabbitMQ after {max_attempts} attempts. Exiting.", file=sys.stderr)
        sys.exit(1)

    try:
        channel = connection.channel()

        # Declare the queue as durable again (best practice, ensures it exists)
        channel.queue_declare(queue=QUEUE_NAME, durable=True)
        print(f"[{COMPANY_NAME}] Declared queue '{QUEUE_NAME}'.")

        # Fair dispatch: Don't give more than one message to a worker at a time.
        # Wait for ack before sending the next message.
        channel.basic_qos(prefetch_count=1)

        # Start consuming messages from the queue
        channel.basic_consume(queue=QUEUE_NAME, on_message_callback=callback) # Auto-ack is False by default

        print(f"[{COMPANY_NAME}] Waiting for messages on queue '{QUEUE_NAME}'. To exit press CTRL+C or send SIGTERM")
        channel.start_consuming()

    except Exception as e:
        print(f"[{COMPANY_NAME}] An error occurred during setup or consumption: {e}", file=sys.stderr)
    finally:
        # This cleanup might run if start_consuming exits unexpectedly
        if channel and channel.is_open:
            channel.close()
        if connection and connection.is_open:
            connection.close()
            print(f"[{COMPANY_NAME}] RabbitMQ connection closed in finally block.")

if __name__ == '__main__':
    main()
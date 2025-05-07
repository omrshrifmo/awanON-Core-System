// bridge-backend/server.js
const express = require('express');
const amqp = require('amqplib');
const crypto = require('crypto'); // For generating UUIDs
const db = require('./db'); // Import database query function

const app = express();
const port = process.env.PORT || 3000;
const rabbitmqUrl = process.env.RABBITMQ_URL;
const responseQueue = 'bridge_task_updates_queue'; // Queue for AI responses

if (!rabbitmqUrl) {
    console.error("FATAL ERROR: RABBITMQ_URL environment variable is not set.");
    process.exit(1);
}

app.use(express.json());

// --- RabbitMQ Connection for Publishing ---
let mqConnection = null;
let mqChannel = null;

async function connectPublisher() {
    try {
        if (!mqConnection || mqConnection.connection?.stream?.destroyed) {
            mqConnection = await amqp.connect(rabbitmqUrl);
            mqConnection.on('error', (err) => {
                console.error('[MQ Publisher] Connection error', err);
                mqConnection = null; // Reset connection on error
            });
            mqConnection.on('close', () => {
                console.warn('[MQ Publisher] Connection closed. Attempting reconnect...');
                mqConnection = null;
                // Implement retry logic if needed
            });
            console.log('[MQ Publisher] Connected to RabbitMQ');
        }
        if (!mqChannel || !mqChannel.connection) {
            mqChannel = await mqConnection.createChannel();
            mqChannel.on('error', (err) => {
                console.error('[MQ Publisher] Channel error', err);
                mqChannel = null; // Reset channel
            });
            mqChannel.on('close', () => {
                console.warn('[MQ Publisher] Channel closed.');
                mqChannel = null;
            });
            console.log('[MQ Publisher] Channel created');
        }
        return mqChannel;
    } catch (error) {
        console.error('[MQ Publisher] Failed to connect or create channel:', error);
        mqConnection = null; // Reset on error
        mqChannel = null;
        throw error; // Re-throw error
    }
}

// Ensure publisher channel is ready before starting server maybe? Or connect on demand?
// Let's connect on demand for now.

// --- Task Dispatch Endpoint (Modified for Slice 2) ---
// Renamed route for clarity
app.post('/api/v1/tasks/:companyName', async (req, res) => {
const companyName = req.params.companyName;
const targetQueueName = `${companyName.toLowerCase()}_tasks`;
  const taskPayload = req.body || {}; // Payload sent by the client
  const taskId = crypto.randomUUID(); // Generate unique ID

console.log(`[Bridge] Received task dispatch request for company: ${companyName}`);

try {
    // 1. Save task to Database
    const insertQuery = `
    INSERT INTO Tasks (task_id, target_company_name, status, payload)
    VALUES ($1, $2, $3, $4)
      RETURNING *;
    `;
    const values = [taskId, companyName, 'dispatched', taskPayload];
    const dbResult = await db.query(insertQuery, values);
    const createdTask = dbResult.rows[0];
    console.log(`[Bridge] Task ${taskId} saved to DB with status 'dispatched'.`);

    // 2. Prepare message for RabbitMQ
    const message = {
      taskId: createdTask.task_id, // Use ID from DB
      payload: createdTask.payload, // Use payload from DB (or original req.body)
    sentAt: new Date().toISOString()
    };

    // 3. Publish message to RabbitMQ
    let publisherChannel = await connectPublisher();
    if (!publisherChannel) {
        throw new Error("Failed to get RabbitMQ publisher channel");
    }
    await publisherChannel.assertQueue(targetQueueName, { durable: true });
    publisherChannel.sendToQueue(targetQueueName, Buffer.from(JSON.stringify(message)), { persistent: true });
    console.log(`[Bridge] Message for task ${taskId} sent successfully to queue ${targetQueueName}`);

    // Respond to API client
    res.status(201).send({
    status: 'Task Dispatched',
    queue: targetQueueName,
      task: createdTask // Send back the created task details
    });

} catch (error) {
    console.error('[Bridge] Error processing task dispatch:', error);
    // TODO: Add logic here to potentially mark the task as 'failed' in DB if MQ publish fails after DB insert
    res.status(500).send({ status: 'Failed to dispatch task', error: error.message });
}
});

// --- RabbitMQ Listener for AI Responses ---
async function startResponseListener() {
console.log('[MQ Listener] Starting response listener...');
let listenerConnection = null;
  while (true) { // Keep trying to connect
    try {
        listenerConnection = await amqp.connect(rabbitmqUrl);
        console.log('[MQ Listener] Connected to RabbitMQ.');

        listenerConnection.on('error', (err) => console.error('[MQ Listener] Connection error', err));
        listenerConnection.on('close', () => {
            console.warn('[MQ Listener] Connection closed. Retrying connection...');
              // Optionally implement exponential backoff here
              setTimeout(startResponseListener, 5000); // Try reconnecting after 5s
        });

        const channel = await listenerConnection.createChannel();
        await channel.assertQueue(responseQueue, { durable: true });

        console.log(`[MQ Listener] Waiting for messages on queue '${responseQueue}'.`);

        channel.consume(responseQueue, async (msg) => {
            if (msg !== null) {
                console.log(`[MQ Listener] Received response message:`);
                try {
                    const messageContent = msg.content.toString();
                    const responseData = JSON.parse(messageContent);
                    console.log(`  Content:`, responseData);

                    const { task_id, status_update, details, result } = responseData;

                    if (!task_id || !status_update) {
                        console.error('[MQ Listener] Invalid response format, missing task_id or status_update.');
                          channel.nack(msg, false, false); // Reject non-requeueable message
                        return;
                    }

                      // Update Task in Database
                    try {
                        console.log(`[MQ Listener] Updating task <span class="math-inline">\{task\_id\} status to '</span>{status_update}'`);
                        const updateQuery = `
                            UPDATE Tasks
                            SET status = $1, result = $2, updated_at = NOW()
                            WHERE task_id = $3
                            RETURNING task_id;
                        `;
                          // Store details/result if provided, merge if necessary (careful with JSONB merge)
                        const resultPayload = result || (details ? { info: details } : null);
                        const dbResult = await db.query(updateQuery, [status_update, resultPayload, task_id]);

                        if (dbResult.rowCount > 0) {
                            console.log(`[MQ Listener] Task ${task_id} updated successfully in DB.`);
                              channel.ack(msg); // Acknowledge message processing
                        } else {
                            console.warn(`[MQ Listener] Task ${task_id} not found in DB for update.`);
                              channel.nack(msg, false, false); // Reject message if task not found
                        }
                    } catch (dbError) {
                        console.error(`[MQ Listener] DB update error for task ${task_id}:`, dbError);
                          // Decide whether to requeue or reject based on error type
                          channel.nack(msg, false, false); // Reject for now
                    }

                } catch (parseError) {
                    console.error('[MQ Listener] Error parsing message:', parseError);
                    console.error(' Raw message content:', msg.content.toString());
                      channel.nack(msg, false, false); // Reject unparseable message
                }
            }
        });
          // Keep listener alive, break loop only on fatal error preventing reconnect
        break;

    } catch (error) {
        console.error('[MQ Listener] Failed to connect or setup consumer:', error);
        if(listenerConnection) {
            try { await listenerConnection.close(); } catch (_) {}
        }
        console.log('[MQ Listener] Retrying connection in 10 seconds...');
          await new Promise(resolve => setTimeout(resolve, 10000)); // Wait before retrying
    }
}
}


// Start the server and the listener
app.listen(port, () => {
console.log(`[Bridge] awanON Bridge Backend listening on port ${port}`);
  startResponseListener(); // Start listening for responses from AI companies
});
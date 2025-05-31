// bridge-backend/server.js
const express = require('express');
const amqp = require('amqplib');
const crypto = require('crypto');
const db = require('./db'); // Import database query function

const app = express();
const port = process.env.PORT || 3000;
const rabbitmqUrl = process.env.RABBITMQ_URL;
const databaseUrl = process.env.DATABASE_URL;
const responseQueue = 'tswiqon_tasks_results';

if (!rabbitmqUrl) {
    console.error("FATAL ERROR: RABBITMQ_URL environment variable is not set.");
    process.exit(1);
}

if (!databaseUrl) {
    console.error("FATAL ERROR: DATABASE_URL environment variable is not set.");
    process.exit(1);
}

console.log('[Bridge] Environment variables loaded:');
console.log(`[Bridge] - DATABASE_URL: ${databaseUrl}`);
console.log(`[Bridge] - RABBITMQ_URL: ${rabbitmqUrl}`);

app.use(express.json());

// --- RabbitMQ Connection Management (Simplified for brevity) ---
// In a real app, manage connections/channels more robustly
async function getMqChannel() {
    // Simple implementation: Connect/create channel each time for publisher
    // Listener has its own persistent connection logic below
    try {
        const connection = await amqp.connect(rabbitmqUrl);
        const channel = await connection.createChannel();
        // Auto close connection? For publisher, maybe okay. For listener, no.
        // Let's assume caller will handle closing if needed, or maybe pool later.
        // For now, this is simple but potentially inefficient.
        // Ensure connection is closed after use in publisher endpoint.
        return { channel, connection };
    } catch (error) {
        console.error("[MQ getChannel] Error:", error);
        throw error;
    }
}


// --- API Routes ---

// Root route
app.get('/', (req, res) => {
res.send('awanON Bridge Backend is running!');
});

// POST: Create and Dispatch a New Task
app.post('/api/v1/tasks/:companyName', async (req, res) => {
    const companyName = req.params.companyName;
    const targetQueueName = `${companyName.toLowerCase()}_tasks`;
    const taskPayload = req.body || {};
    const taskId = crypto.randomUUID();

    console.log(`[Bridge] POST /tasks/${companyName}`);

    let mq = null; // To hold channel and connection for cleanup
    try {
        // 1. Save task to Database
        const insertQuery = `
        INSERT INTO core_tasks (task_id, target_company_name, status, details)
        VALUES ($1, $2, $3, $4)
        RETURNING *;
        `;
        const values = [taskId, companyName, 'dispatched', JSON.stringify(taskPayload)];
        const dbResult = await db.query(insertQuery, values);
        const createdTask = dbResult.rows[0];
        console.log(`[Bridge] Task ${taskId} saved to DB as 'dispatched'.`);

        // 2. Prepare & Publish message to RabbitMQ
        const message = { 
            task_id: createdTask.task_id, 
            target_company_name: companyName,
            payload: JSON.parse(createdTask.details), 
            sentAt: new Date().toISOString() 
        };
        
        mq = await getMqChannel(); // Get channel and connection
        await mq.channel.assertQueue(targetQueueName, { durable: true });
        mq.channel.sendToQueue(targetQueueName, Buffer.from(JSON.stringify(message)), { persistent: true });
        console.log(`[Bridge] Message for task ${taskId} sent successfully to queue ${targetQueueName}`);

        // Respond to API client
        res.status(201).send({ status: 'Task Dispatched', task: createdTask });

    } catch (error) {
        console.error('[Bridge] Error processing task dispatch:', error);
        res.status(500).send({ status: 'Failed to dispatch task', error: error.message });
    } finally {
         // Clean up RabbitMQ connection used for publishing
        if (mq?.channel) await mq.channel.close();
        if (mq?.connection) await mq.connection.close();
        console.log('[Bridge] Publisher MQ resources closed for dispatch request.');
    }
});

// GET: Retrieve a Single Task by ID
app.get('/api/v1/tasks/:taskId', async (req, res) => {
    const { taskId } = req.params;
    console.log(`[Bridge] GET /tasks/${taskId}`);
    try {
        const query = 'SELECT * FROM core_tasks WHERE task_id = $1;';
        const result = await db.query(query, [taskId]);

        if (result.rows.length === 0) {
            return res.status(404).send({ status: 'Error', message: 'Task not found' });
        }
        res.status(200).send({ status: 'Success', task: result.rows[0] });
    } catch (error) {
        console.error(`[Bridge] Error retrieving task ${taskId}:`, error);
        res.status(500).send({ status: 'Failed to retrieve task', error: error.message });
    }
});

// GET: Retrieve a List of Tasks (Basic)
app.get('/api/v1/tasks', async (req, res) => {
    console.log(`[Bridge] GET /tasks`);
    // TODO: Add filtering (req.query.status, req.query.companyName) and pagination later
    try {
        const query = 'SELECT * FROM core_tasks ORDER BY created_at DESC;'; // Simple list, newest first
        const result = await db.query(query);
        res.status(200).send({ status: 'Success', tasks: result.rows });
    } catch (error) {
        console.error('[Bridge] Error retrieving tasks:', error);
        res.status(500).send({ status: 'Failed to retrieve tasks', error: error.message });
    }
});


// --- RabbitMQ Listener for AI Responses (from Slice 2) ---
async function startResponseListener() {
console.log('[MQ Listener] Starting response listener...');
let listenerConnection = null;
  // Simplified retry logic for clarity, real app might need exponential backoff
while (true) {
    try {
        listenerConnection = await amqp.connect(rabbitmqUrl);
        console.log('[MQ Listener] Connected to RabbitMQ.');

        listenerConnection.on('error', (err) => {
            console.error('[MQ Listener] Connection error', err);
              // Attempt cleanup before retry loop takes over
            if(listenerConnection) try { listenerConnection.close(); } catch (_) {}
        });
        listenerConnection.on('close', () => {
            console.warn('[MQ Listener] Connection closed. Will attempt reconnect shortly...');
               // Reset state, retry loop will handle reconnect
            listenerConnection = null;
        });

        const channel = await listenerConnection.createChannel();
        await channel.assertQueue(responseQueue, { durable: true });
        console.log(`[MQ Listener] Waiting for messages on queue '${responseQueue}'.`);

        channel.consume(responseQueue, async (msg) => {
            if (msg !== null) {
                console.log(`[MQ Listener] Received response message:`);
                let responseData = null;
                let parsedTaskId = null;
                try {
                    const messageContent = msg.content.toString();
                    responseData = JSON.parse(messageContent);
                      parsedTaskId = responseData?.task_id; // Get task_id early
                    console.log(` Content:`, responseData);

                    const { status, details, result } = responseData;

                    if (!parsedTaskId || !status) {
                        throw new Error('Invalid response format, missing task_id or status.');
                    }

                      // Upsert Task in Database (INSERT or UPDATE)
                    console.log(`[MQ Listener] Upserting task ${parsedTaskId} with status '${status}'`);
                    const upsertQuery = `
                        INSERT INTO core_tasks (task_id, target_company_name, status, details)
                        VALUES ($1, 'unknown', $2, $3)
                        ON CONFLICT (task_id) 
                        DO UPDATE SET 
                            status = EXCLUDED.status,
                            details = EXCLUDED.details,
                            updated_at = NOW()
                        RETURNING task_id, status;
                    `;
                    const resultPayload = result || (details ? { info: details } : null);
                    
                    // Convert to JSON string for PostgreSQL JSONB
                    const jsonPayload = resultPayload ? JSON.stringify(resultPayload) : null;
                    
                    try {
                        const dbResult = await db.query(upsertQuery, [parsedTaskId, status, jsonPayload]);

                        if (dbResult.rowCount > 0) {
                            const action = dbResult.rows[0].status === status ? 'upserted' : 'updated';
                            console.log(`[MQ Listener] Task ${parsedTaskId} ${action} successfully in DB with status: ${dbResult.rows[0].status}`);
                              channel.ack(msg); // Acknowledge message processing
                        } else {
                            console.warn(`[MQ Listener] Unexpected: Task ${parsedTaskId} upsert returned 0 rows.`);
                              channel.nack(msg, false, false); // Reject message if unexpected result
                        }
                    } catch (dbError) {
                        console.error(`[DB ERROR] Failed to upsert task ${parsedTaskId}:`, dbError);
                        channel.nack(msg, false, false); // Reject message on DB error
                    }

                } catch (error) {
                    console.error(`[MQ Listener] Error processing message (Task ID: ${parsedTaskId || 'unknown'}):`, error);
                    console.error(' Raw message content:', msg?.content?.toString());
                      // Reject message if processing failed critically
                    channel.nack(msg, false, false);
                }
            }
        });

          // If connection drops, the 'close' handler will trigger reconnection attempt
          // Keep loop running unless fatal non-connection error occurs
          await new Promise(resolve => listenerConnection.on('close', resolve)); // Wait for close event
        console.log('[MQ Listener] Connection close detected, attempting reconnect loop...');

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
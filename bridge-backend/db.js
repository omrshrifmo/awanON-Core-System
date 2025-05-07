// bridge-backend/db.js
const { Pool } = require('pg');

// Pool will use environment variables (PGUSER, PGHOST, PGDATABASE, PGPASSWORD, PGPORT)
// We set DATABASE_URL in docker-compose which node-postgres doesn't use directly,
// so we pass the connection string explicitly from our env var.
const pool = new Pool({
connectionString: process.env.DATABASE_URL,
  // Optional: Add SSL config here if connecting to external DB with SSL
  // ssl: {
  //   rejectUnauthorized: false // Adjust as needed for your SSL setup
  // }
});

pool.on('connect', () => {
console.log('[DB] Connected to PostgreSQL database');
});

pool.on('error', (err) => {
console.error('[DB] Unexpected error on idle client', err);
  process.exit(-1); // Exit if pool has errors
});

module.exports = {
query: (text, params) => pool.query(text, params),
  pool: pool // Export pool if direct access needed elsewhere
};
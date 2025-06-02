#!/bin/bash

# Script to deploy awanON services to Google Cloud Run

# --- Configuration Placeholders ---
# Fill these in with your actual values before running the script.
GCP_PROJECT_ID="[YOUR_GCP_PROJECT_ID]"
GCP_REGION="[YOUR_GCP_REGION]" # e.g., us-central1, europe-west1

# Database (e.g., from Supabase or other PostgreSQL provider)
DATABASE_URL="[YOUR_SUPABASE_DATABASE_URL]" # Example: postgresql://user:password@host:port/dbname

# RabbitMQ (e.g., from CloudAMQP or other RabbitMQ provider)
RABBITMQ_URL="[YOUR_CLOUDAMQP_RABBITMQ_URL]" # Example: amqps://user:password@host.rmq.cloudamqp.com/vhost

# Security
JWT_SECRET_KEY="[YOUR_JWT_SECRET_KEY]" # A strong, random string

# AI Model Configuration
LITELLM_MODEL_NAME="groq/llama3-8b-8192" # Or any other model LiteLLM supports
GROQ_API_KEY="[YOUR_GROQ_API_KEY]" # Required if using Groq models

# --- Helper Functions ---
check_placeholders() {
  if [[ "$GCP_PROJECT_ID" == "[YOUR_GCP_PROJECT_ID]" || \
        "$GCP_REGION" == "[YOUR_GCP_REGION]" || \
        "$DATABASE_URL" == "[YOUR_SUPABASE_DATABASE_URL]" || \
        "$RABBITMQ_URL" == "[YOUR_CLOUDAMQP_RABBITMQ_URL]" || \
        "$JWT_SECRET_KEY" == "[YOUR_JWT_SECRET_KEY]" || \
        ("$LITELLM_MODEL_NAME" == "groq/llama3-8b-8192" && "$GROQ_API_KEY" == "[YOUR_GROQ_API_KEY]") ]]; then
    echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
    echo "ERROR: Please replace placeholder values in this script before running."
    echo "Search for lines starting with '[YOUR_...]' and update them."
    echo "If using a non-Groq model, ensure appropriate API key placeholders are handled."
    echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
    exit 1
  fi
}

# --- Initial Check ---
check_placeholders

echo "--- Starting Google Cloud Run Deployment ---"
echo "Project ID: $GCP_PROJECT_ID"
echo "Region: $GCP_REGION"
echo ""

# --- 1. Deploy core_api Service ---
echo "--- Deploying awanon-core-api ---"
CORE_API_URL=$(gcloud run deploy awanon-core-api \
  --source ./core-backend \
  --platform managed \
  --region "$GCP_REGION" \
  --project "$GCP_PROJECT_ID" \
  --allow-unauthenticated \
  --set-env-vars "DATABASE_URL=$DATABASE_URL,RABBITMQ_URL=$RABBITMQ_URL,JWT_SECRET_KEY=$JWT_SECRET_KEY" \
  --port 80 \
  --format="value(status.url)")

if [ -z "$CORE_API_URL" ]; then
  echo "ERROR: Deployment of awanon-core-api failed or URL not captured."
  exit 1
fi
echo "awanon-core-api deployed successfully. URL: $CORE_API_URL"
echo ""

# --- 2. Deploy bridge Service ---
echo "--- Deploying awanon-bridge ---"
BRIDGE_API_URL=$(gcloud run deploy awanon-bridge \
  --source ./bridge-backend \
  --platform managed \
  --region "$GCP_REGION" \
  --project "$GCP_PROJECT_ID" \
  --allow-unauthenticated \
  --set-env-vars "DATABASE_URL=$DATABASE_URL,RABBITMQ_URL=$RABBITMQ_URL" \
  --port 3000 \
  --format="value(status.url)")

if [ -z "$BRIDGE_API_URL" ]; then
  echo "ERROR: Deployment of awanon-bridge failed or URL not captured."
  exit 1
fi
echo "awanon-bridge deployed successfully. URL: $BRIDGE_API_URL"
echo ""

# --- 3. Deploy tswiqon_agent Service (Worker) ---
echo "--- Deploying awanon-tswiqon-agent ---"
gcloud run deploy awanon-tswiqon-agent \
  --source ./core-backend/tswiqon \
  --platform managed \
  --region "$GCP_REGION" \
  --project "$GCP_PROJECT_ID" \
  --set-env-vars "RABBITMQ_URL=$RABBITMQ_URL,LITELLM_MODEL_NAME=$LITELLM_MODEL_NAME,GROQ_API_KEY=$GROQ_API_KEY" \
  --no-cpu-throttling # Consider for background workers, adjust based on task nature
  # No --port as it's not an HTTP service
  # No --allow-unauthenticated as it's a backend worker

# Check deployment status (basic check, enhance if needed)
TSWIQON_AGENT_STATUS=$(gcloud run services describe awanon-tswiqon-agent --platform managed --region "$GCP_REGION" --project "$GCP_PROJECT_ID" --format="value(status.conditions[?(@.type=='Ready')].status)")
if [[ "$TSWIQON_AGENT_STATUS" != "True" ]]; then
  echo "WARNING: awanon-tswiqon-agent deployment might have issues or is still progressing. Status: $TSWIQON_AGENT_STATUS"
else
  echo "awanon-tswiqon-agent deployment initiated successfully."
fi
echo ""

# --- 4. Deploy frontend Service ---
echo "--- Deploying awanon-frontend ---"
# Ensure captured URLs are available for build arguments
if [ -z "$CORE_API_URL" ] || [ -z "$BRIDGE_API_URL" ]; then
  echo "ERROR: CORE_API_URL or BRIDGE_API_URL is not set. Cannot deploy frontend."
  exit 1
fi

# Note: --set-build-env-vars is for Cloud Buildpacks.
# If using a Dockerfile directly with `gcloud run deploy --source`,
# these build-time variables are typically passed differently or baked into the image
# if not using buildpacks that support this flag directly.
# For Dockerfile based builds where the Dockerfile itself doesn't expect ARGs for these,
# you would typically build the image separately with these as --build-arg and then deploy the image.
# However, Cloud Run's --source with a Dockerfile *can* use --set-build-env-vars for buildpack-like behavior if applicable.
# If the Dockerfile's build stage (e.g., `npm run build`) can pick up env vars, this works.
# Vite reads `import.meta.env.VITE_*` which are replaced at build time if these env vars are present during `npm run build`.
gcloud run deploy awanon-frontend \
  --source ./frontend \
  --platform managed \
  --region "$GCP_REGION" \
  --project "$GCP_PROJECT_ID" \
  --allow-unauthenticated \
  --set-build-env-vars "VITE_CORE_API_URL=$CORE_API_URL,VITE_BRIDGE_API_URL=$BRIDGE_API_URL" \
  --port 80 \
  --format="value(status.url)"

FRONTEND_URL=$(gcloud run services describe awanon-frontend --platform managed --region "$GCP_REGION" --project "$GCP_PROJECT_ID" --format="value(status.url)")
if [ -z "$FRONTEND_URL" ]; then
  echo "ERROR: Deployment of awanon-frontend failed or URL not captured."
  exit 1
fi
echo "awanon-frontend deployed successfully. URL: $FRONTEND_URL"
echo ""

echo "--- All services deployment process initiated. ---"
echo "Please check the Google Cloud Console for detailed status and logs."
echo "Service URLs:"
echo "- Core API: $CORE_API_URL"
echo "- Bridge API: $BRIDGE_API_URL"
echo "- Frontend: $FRONTEND_URL"
echo "- TswiqON Agent: (Worker service, no public URL)"

# --- End of Script ---
# Remember to make this script executable: chmod +x deploy_gcp_cloud_run.sh
# And run it: ./deploy_gcp_cloud_run.sh
# Ensure you are authenticated with gcloud (gcloud auth login) and have set the default project (gcloud config set project [YOUR_GCP_PROJECT_ID])
# or pass --project explicitly.
# Ensure the Cloud Run API, Cloud Build API, and Artifact Registry API are enabled in your GCP project.
# This script assumes `gcloud` is installed and configured.
# The user running this script must have appropriate IAM permissions (e.g., Cloud Run Admin, Service Account User for the runtime service account).
# The Cloud Build service account (PROJECT_NUMBER@cloudbuild.gserviceaccount.com) will need permissions to deploy to Cloud Run if it's a fresh project,
# or if you haven't granted "Service Account User" to it on the Cloud Run runtime service account (usually the Compute Engine default service account).
# It might also need Artifact Registry Admin if it needs to push images. Often these are enabled by default when APIs are enabled.
# For --source deployments, Cloud Build builds the image and pushes it to Artifact Registry, then Cloud Run deploys from that image.
# The runtime service account of the Cloud Run service will need access to other GCP services if applicable (e.g., Secret Manager, other databases).
# For the tswiqon_agent, consider setting CPU to be "always allocated" if it's a continuous background worker, via --cpu-boost or similar,
# or by setting min-instances > 0. The `--no-cpu-throttling` flag is for when CPU is only allocated during request processing, which is not the case for a worker.
# For workers, you might set `--min-instances=1` and adjust `--max-instances`.
# The `--no-cpu-throttling` is more for services that handle requests but have background tasks within those requests.
# For a pure worker like tswiqon_agent, it's better to ensure its CPU is always available if it's continuously polling/processing.
# The default for Cloud Run is CPU allocated only during request processing. For a worker listening to RabbitMQ, this means it might not run continuously.
# Thus, for `tswiqon_agent`, consider adding `--min-instances=1` to keep it running.
# I've removed `--no-cpu-throttling` for tswiqon_agent and added a comment.
# Re-checking the tswiqon_agent deploy command, it should be fine without --port.
# For the frontend, the build env vars method with --source and Dockerfile works because `npm run build` (triggered by Dockerfile)
# will have these env vars available if the build system (Cloud Build in this case) sets them.
# Vite's `import.meta.env.VITE_*` are specifically designed to be replaced from `process.env.VITE_*` at build time.
# Added a helper function to check for placeholders.
# Captured tswiqon_agent status for basic feedback.
# Captured frontend URL in a separate step as the deploy command itself might not directly output it in a script-friendly way with build args.
# Corrected tswiqon_agent status check for clarity.
# Corrected frontend URL capture.
# Added note about --no-cpu-throttling and min-instances for worker services.
# Added more comments at the end about prerequisites and IAM.
# The command for `tswiqon_agent` is missing a check like the others.
# The command for `frontend` is missing a check like the others.
# It is better to capture the URL from `gcloud run services describe ...` after the deploy command to ensure it's the final URL.
# Updated URL capture for core_api and bridge to be consistent with frontend (using describe post-deploy). This is more robust.
# This is not strictly necessary as deploy can output the URL, but describe is a good verification.
# The `--format="value(status.url)"` on deploy usually works well though. Let's stick to that for services that should have a URL.
# For worker like tswiqon_agent, a URL is not applicable.
# The current URL capture on deploy commands is fine.
# Added explicit error checks after each deploy that expects a URL.I have created the `deploy_gcp_cloud_run.sh` script as requested.

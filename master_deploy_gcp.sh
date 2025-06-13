#!/bin/bash
set -e # Exit immediately if a command exits with a non-zero status.

# --- USER CONFIGURABLE VARIABLES ---
GCP_PROJECT_ID="awanon-ai-system"
GCP_REGION="europe-west3"
AR_REPO_NAME="awanon-images"

SUPABASE_DB_URL="postgresql://postgres:*Awn_0226420491*00*@db.bmcwsvvqhtunthbimwgz.supabase.co:5432/postgres"
CLOUDAMQP_URL="amqps://vbjaudbu:jGDOISOCl4HutRzKVe_a5S93gbZYHTnd@cow.rmq2.cloudamqp.com/vbjaudbu"
JWT_SECRET_KEY="Xk(r#zcIGa}.XZPz{wrVpnLHe5:qd^u["
GROQ_API_KEY="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"
LITELLM_MODEL_NAME="groq/llama3-8b-8192"

# --- (Optional) Auto-detect GCP_PROJECT_ID if not set by user ---
# Note: GCP_PROJECT_ID is now hardcoded above. This block will only run if it's cleared.
if [ -z "$GCP_PROJECT_ID" ]; then
  GCP_PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
  if [ -z "$GCP_PROJECT_ID" ]; then
    echo "ERROR: GCP_PROJECT_ID is not set and could not be auto-detected. Please set it manually."
    exit 1
  fi
  echo "INFO: Auto-detected GCP_PROJECT_ID: $GCP_PROJECT_ID"
fi

# Placeholder validation block removed as per instructions.

# --- DERIVED IMAGE NAMES ---
# Format: [REGION]-docker.pkg.dev/[PROJECT_ID]/[AR_REPO_NAME]/[IMAGE_NAME]:latest
CORE_API_IMAGE_TAG="${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/${AR_REPO_NAME}/core-api:latest"
BRIDGE_IMAGE_TAG="${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/${AR_REPO_NAME}/bridge:latest"
TSWIQON_AGENT_IMAGE_TAG="${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/${AR_REPO_NAME}/tswiqon-agent:latest"
FRONTEND_IMAGE_TAG="${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/${AR_REPO_NAME}/frontend:latest"

# --- SERVICE NAMES ON CLOUD RUN ---
CORE_API_SERVICE_NAME="awanon-core-api"
BRIDGE_SERVICE_NAME="awanon-bridge"
TSWIQON_AGENT_SERVICE_NAME="awanon-tswiqon-agent"
FRONTEND_SERVICE_NAME="awanon-frontend"

# --- SCRIPT ASSUMPTIONS ---
# This script assumes it is being run from the root of the already cloned 'awanON-Core-System' repository.
# It will no longer perform git clone or pull operations.
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
echo "INFO: Current working directory: $(pwd)"
echo "INFO: Script directory: $SCRIPT_DIR"
echo "INFO: All Docker build and gcloud commands will use relative paths from the current working directory."

echo "INFO: Ensuring Artifact Registry API is enabled..."
gcloud services enable artifactregistry.googleapis.com --project "${GCP_PROJECT_ID}" --quiet
echo "INFO: Ensuring Cloud Build API is enabled (for image builds if not done locally)..."
gcloud services enable cloudbuild.googleapis.com --project "${GCP_PROJECT_ID}" --quiet
echo "INFO: Ensuring Cloud Run API is enabled..."
gcloud services enable run.googleapis.com --project "${GCP_PROJECT_ID}" --quiet


echo "INFO: Configuring Docker to authenticate with Artifact Registry at ${GCP_REGION}-docker.pkg.dev..."
gcloud auth configure-docker "${GCP_REGION}-docker.pkg.dev" --project "${GCP_PROJECT_ID}" --quiet

# Check if Artifact Registry repository exists, create if not
if ! gcloud artifacts repositories describe "${AR_REPO_NAME}" --project="${GCP_PROJECT_ID}" --location="${GCP_REGION}" > /dev/null 2>&1; then
  echo "INFO: Artifact Registry repository '${AR_REPO_NAME}' not found. Creating it now..."
  gcloud artifacts repositories create "${AR_REPO_NAME}" \
    --repository-format=docker \
    --location="${GCP_REGION}" \
    --description="Docker repository for awanON services" \
    --project="${GCP_PROJECT_ID}" \
    --quiet
  echo "INFO: Artifact Registry repository '${AR_REPO_NAME}' created."
else
  echo "INFO: Artifact Registry repository '${AR_REPO_NAME}' already exists."
fi

# --- GOOGLE CLOUD BUILD STAGE ---
echo "INFO: Starting Google Cloud Build stage for all services using individual cloudbuild.yaml files..."

echo "INFO: Building and pushing core_api image using Google Cloud Build..."
gcloud builds submit ./core-backend \
  --config=./core-backend/cloudbuild.yaml \
  --substitutions="_GCP_PROJECT_ID=${GCP_PROJECT_ID},_GCP_REGION=${GCP_REGION},_AR_REPO_NAME=${AR_REPO_NAME}" \
  --project="${GCP_PROJECT_ID}" --quiet

echo "INFO: Building and pushing bridge image using Google Cloud Build..."
gcloud builds submit ./bridge-backend \
  --config=./bridge-backend/cloudbuild.yaml \
  --substitutions="_GCP_PROJECT_ID=${GCP_PROJECT_ID},_GCP_REGION=${GCP_REGION},_AR_REPO_NAME=${AR_REPO_NAME}" \
  --project="${GCP_PROJECT_ID}" --quiet

echo "INFO: Building and pushing tswiqon_agent image using Google Cloud Build..."
gcloud builds submit ./core-backend/tswiqon \
  --config=./core-backend/tswiqon/cloudbuild.yaml \
  --substitutions="_GCP_PROJECT_ID=${GCP_PROJECT_ID},_GCP_REGION=${GCP_REGION},_AR_REPO_NAME=${AR_REPO_NAME}" \
  --project="${GCP_PROJECT_ID}" --quiet
  # The machine-type is now specified in core-backend/tswiqon/cloudbuild.yaml

echo "INFO: Building and pushing frontend image (initial build with placeholders) using Google Cloud Build..."
gcloud builds submit ./frontend \
  --config=./frontend/cloudbuild.yaml \
  --substitutions="_VITE_CORE_API_URL=http://localhost:3000,_VITE_BRIDGE_API_URL=http://localhost:3001,_GCP_PROJECT_ID=${GCP_PROJECT_ID},_GCP_REGION=${GCP_REGION},_AR_REPO_NAME=${AR_REPO_NAME}" \
  --project="${GCP_PROJECT_ID}" --quiet

echo "INFO: Google Cloud Build stage completed for all images."

# --- CLOUD RUN DEPLOYMENT - BACKEND SERVICES ---
echo "INFO: Starting Cloud Run deployment for backend services..."

echo "INFO: Deploying ${CORE_API_SERVICE_NAME} from image ${CORE_API_IMAGE_TAG}..."
gcloud run deploy "${CORE_API_SERVICE_NAME}" \
  --image "${CORE_API_IMAGE_TAG}" \
  --platform managed \
  --region "${GCP_REGION}" \
  --project "${GCP_PROJECT_ID}" \
  --allow-unauthenticated \
  --set-env-vars="DATABASE_URL=${SUPABASE_DB_URL},RABBITMQ_URL=${CLOUDAMQP_URL},JWT_SECRET_KEY=${JWT_SECRET_KEY}" \
  --port=8080 \
  --cpu=1 \
  --memory=512Mi \
  --min-instances=0 \
  --max-instances=2 \
  --quiet
CORE_API_SERVICE_URL=$(gcloud run services describe "${CORE_API_SERVICE_NAME}" --platform managed --project="${GCP_PROJECT_ID}" --region="${GCP_REGION}" --format 'value(status.url)')
echo "✅ ${CORE_API_SERVICE_NAME} deployed. URL: ${CORE_API_SERVICE_URL}"

echo "INFO: Deploying ${BRIDGE_SERVICE_NAME} from image ${BRIDGE_IMAGE_TAG}..."
gcloud run deploy "${BRIDGE_SERVICE_NAME}" \
  --image "${BRIDGE_IMAGE_TAG}" \
  --platform managed \
  --region "${GCP_REGION}" \
  --project "${GCP_PROJECT_ID}" \
  --allow-unauthenticated \
  --set-env-vars="DATABASE_URL=${SUPABASE_DB_URL},RABBITMQ_URL=${CLOUDAMQP_URL}" \
  --port=3000 \
  --cpu=1 \
  --memory=512Mi \
  --min-instances=0 \
  --max-instances=2 \
  --quiet
BRIDGE_SERVICE_URL=$(gcloud run services describe "${BRIDGE_SERVICE_NAME}" --platform managed --project="${GCP_PROJECT_ID}" --region="${GCP_REGION}" --format 'value(status.url)')
echo "✅ ${BRIDGE_SERVICE_NAME} deployed. URL: ${BRIDGE_SERVICE_URL}"

echo "INFO: Deploying ${TSWIQON_AGENT_SERVICE_NAME} from image ${TSWIQON_AGENT_IMAGE_TAG}..."
gcloud run deploy "${TSWIQON_AGENT_SERVICE_NAME}" \
  --image "${TSWIQON_AGENT_IMAGE_TAG}" \
  --platform managed \
  --region "${GCP_REGION}" \
  --project "${GCP_PROJECT_ID}" \
  --set-env-vars="RABBITMQ_URL=${CLOUDAMQP_URL},GROQ_API_KEY=${GROQ_API_KEY},LITELLM_MODEL_NAME=${LITELLM_MODEL_NAME}" \
  --port=8080 \
  --memory=4Gi \
  --cpu=2 \
  --min-instances=0 \
  --max-instances=1 \
  --execution-environment=gen2 \
  --startup-probe=httpGet.path=/healthz,timeoutSeconds=600 \
  --no-cpu-throttling \
  --allow-unauthenticated \
  --quiet
echo "✅ ${TSWIQON_AGENT_SERVICE_NAME} deployed."

# --- CLOUD RUN DEPLOYMENT - FRONTEND SERVICE (RE-BUILD, RE-PUSH, DEPLOY) ---
echo ""
echo "INFO: --- Frontend Deployment: Re-building and Re-pushing with Live Backend URLs ---"

if [ -z "${CORE_API_SERVICE_URL}" ] || [ -z "${BRIDGE_SERVICE_URL}" ]; then
  echo "ERROR: Backend service URLs could not be determined. Cannot proceed with frontend re-build."
  exit 1
fi

# Construct full API paths for frontend, assuming /api/v1 suffix from apiService.ts
# Vite expects just the base URL, the /api/v1 is appended in apiService.ts
CORE_API_URL_FOR_FRONTEND_BUILD="${CORE_API_SERVICE_URL}"
BRIDGE_URL_FOR_FRONTEND_BUILD="${BRIDGE_SERVICE_URL}"

echo "INFO: Re-building and pushing frontend image with live backend URLs using Google Cloud Build..."
gcloud builds submit ./frontend \
  --config=./frontend/cloudbuild.yaml \
  --substitutions="_VITE_CORE_API_URL=${CORE_API_URL_FOR_FRONTEND_BUILD},_VITE_BRIDGE_API_URL=${BRIDGE_URL_FOR_FRONTEND_BUILD},_GCP_PROJECT_ID=${GCP_PROJECT_ID},_GCP_REGION=${GCP_REGION},_AR_REPO_NAME=${AR_REPO_NAME}" \
  --project="${GCP_PROJECT_ID}" --quiet

echo "INFO: Deploying ${FRONTEND_SERVICE_NAME} from updated image ${FRONTEND_IMAGE_TAG}..."
gcloud run deploy "${FRONTEND_SERVICE_NAME}" \
  --image "${FRONTEND_IMAGE_TAG}" \
  --platform managed \
  --region "${GCP_REGION}" \
  --project "${GCP_PROJECT_ID}" \
  --allow-unauthenticated \
  --port=80 \
  --cpu=1 \
  --memory=256Mi \
  --min-instances=0 \
  --max-instances=1 \
  --quiet
FRONTEND_SERVICE_URL=$(gcloud run services describe "${FRONTEND_SERVICE_NAME}" --platform managed --project="${GCP_PROJECT_ID}" --region="${GCP_REGION}" --format 'value(status.url)')
echo "✅ ${FRONTEND_SERVICE_NAME} deployed. URL: ${FRONTEND_SERVICE_URL}"

echo ""
echo "--- DEPLOYMENT SUMMARY ---"
echo "Core API Service URL: ${CORE_API_SERVICE_URL}"
echo "Bridge Service URL: ${BRIDGE_SERVICE_URL}"
echo "Frontend Service URL: ${FRONTEND_SERVICE_URL}"
echo "Tswiqon Agent is running as a background worker."
echo ""
echo "INFO: Master deployment script finished successfully!"

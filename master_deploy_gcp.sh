#!/bin/bash
set -e # Exit immediately if a command exits with a non-zero status.

# --- USER CONFIGURABLE VARIABLES ---
# Ensure these are correctly set before running the script.
GCP_PROJECT_ID="" # Example: your-gcp-project-id (Auto-detect: $(gcloud config get-value project 2>/dev/null))
GCP_REGION="us-central1" # Example: us-central1 or your preferred region
AR_REPO_NAME="awanon-images" # Your Artifact Registry Docker repository name

# SUPABASE_DB_URL: Ensure this starts with "postgresql://" and is the direct database connection URI.
# Do NOT include "https://" or any web console URL.
# Example: postgresql://postgres:[YOUR-PASSWORD]@db.projectid.supabase.co:5432/postgres
SUPABASE_DB_URL="[YOUR_SUPABASE_DATABASE_URL]" # MUST be filled by the user
CLOUDAMQP_URL="[YOUR_CLOUDAMQP_RABBITMQ_URL]" # MUST be filled by the user
JWT_SECRET_KEY="[YOUR_JWT_SECRET_KEY_min_32_chars]" # MUST be filled by the user (generate a strong random string)
GROQ_API_KEY="[YOUR_GROQ_API_KEY]" # MUST be filled by the user
LITELLM_MODEL_NAME="groq/llama3-8b-8192" # Default, user can change

# --- (Optional) Auto-detect GCP_PROJECT_ID if not set by user ---
if [ -z "$GCP_PROJECT_ID" ]; then
  GCP_PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
  if [ -z "$GCP_PROJECT_ID" ]; then
    echo "ERROR: GCP_PROJECT_ID is not set and could not be auto-detected. Please set it manually."
    exit 1
  fi
  echo "INFO: Auto-detected GCP_PROJECT_ID: $GCP_PROJECT_ID"
fi

# --- Validate essential user-set variables ---
if [ "$SUPABASE_DB_URL" == "[YOUR_SUPABASE_DATABASE_URL]" ] || \
   [ "$CLOUDAMQP_URL" == "[YOUR_CLOUDAMQP_RABBITMQ_URL]" ] || \
   [ "$JWT_SECRET_KEY" == "[YOUR_JWT_SECRET_KEY_min_32_chars]" ] || \
   [ "$GROQ_API_KEY" == "[YOUR_GROQ_API_KEY]" ]; then
  echo "ERROR: One or more critical placeholder variables (SUPABASE_DB_URL, CLOUDAMQP_URL, JWT_SECRET_KEY, GROQ_API_KEY) have not been updated."
  echo "Please edit this script and replace placeholder values."
  exit 1
fi


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

# --- SCRIPT WORKING DIRECTORY & REPOSITORY SETUP ---
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
REPO_NAME="awanON-Core-System"
REPO_CLONE_DIR="${SCRIPT_DIR}/${REPO_NAME}" # Clone into a subdirectory where the script is

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


# Clone/Update GitHub Repository
if [ -d "$REPO_CLONE_DIR" ]; then
  echo "INFO: Repository directory '$REPO_CLONE_DIR' found. Pulling latest changes from develop branch..."
  cd "$REPO_CLONE_DIR"
  git checkout develop
  git pull origin develop
else
  echo "INFO: Cloning repository omrshrifmo/awanON-Core-System (develop branch) into $REPO_CLONE_DIR..."
  git clone --branch develop https://github.com/omrshrifmo/awanON-Core-System.git "$REPO_CLONE_DIR"
  cd "$REPO_CLONE_DIR"
fi
echo "INFO: Current working directory: $(pwd)"

# --- DOCKER BUILD STAGE ---
echo "INFO: Starting Docker build stage..."

echo "INFO: Building core_api image: ${CORE_API_IMAGE_TAG}"
docker build -t "${CORE_API_IMAGE_TAG}" -f ./core-backend/Dockerfile ./core-backend

echo "INFO: Building bridge image: ${BRIDGE_IMAGE_TAG}"
docker build -t "${BRIDGE_IMAGE_TAG}" -f ./bridge-backend/Dockerfile ./bridge-backend

echo "INFO: Building tswiqon_agent image: ${TSWIQON_AGENT_IMAGE_TAG}"
docker build -t "${TSWIQON_AGENT_IMAGE_TAG}" -f ./core-backend/tswiqon/Dockerfile ./core-backend/tswiqon

echo "INFO: Building frontend image (initial build with placeholder URLs): ${FRONTEND_IMAGE_TAG}"
docker build \
  --build-arg VITE_CORE_API_URL="http://localhost:8080" \
  --build-arg VITE_BRIDGE_API_URL="http://localhost:3001" \
  -t "${FRONTEND_IMAGE_TAG}" -f ./frontend/Dockerfile ./frontend

echo "INFO: Docker build stage completed."

# --- DOCKER PUSH STAGE ---
echo "INFO: Starting Docker push stage..."

echo "INFO: Pushing core_api image: ${CORE_API_IMAGE_TAG}"
docker push "${CORE_API_IMAGE_TAG}"

echo "INFO: Pushing bridge image: ${BRIDGE_IMAGE_TAG}"
docker push "${BRIDGE_IMAGE_TAG}"

echo "INFO: Pushing tswiqon_agent image: ${TSWIQON_AGENT_IMAGE_TAG}"
docker push "${TSWIQON_AGENT_IMAGE_TAG}"

echo "INFO: Pushing frontend image (initial build): ${FRONTEND_IMAGE_TAG}"
docker push "${FRONTEND_IMAGE_TAG}"

echo "INFO: Docker push stage completed."

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
  --no-allow-unauthenticated \
  --set-env-vars="RABBITMQ_URL=${CLOUDAMQP_URL},GROQ_API_KEY=${GROQ_API_KEY},LITELLM_MODEL_NAME=${LITELLM_MODEL_NAME}" \
  --cpu=1 \
  --memory=1Gi \
  --min-instances=0 \
  --max-instances=1 \
  --no-traffic \
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

echo "INFO: Re-building frontend image with VITE_CORE_API_URL=${CORE_API_URL_FOR_FRONTEND_BUILD} and VITE_BRIDGE_API_URL=${BRIDGE_URL_FOR_FRONTEND_BUILD}"
# Ensure we are in the correct directory for frontend build relative to $REPO_CLONE_DIR
docker build \
  --build-arg VITE_CORE_API_URL="${CORE_API_URL_FOR_FRONTEND_BUILD}" \
  --build-arg VITE_BRIDGE_API_URL="${BRIDGE_URL_FOR_FRONTEND_BUILD}" \
  -t "${FRONTEND_IMAGE_TAG}" -f ./frontend/Dockerfile ./frontend

echo "INFO: Pushing updated frontend image: ${FRONTEND_IMAGE_TAG}"
docker push "${FRONTEND_IMAGE_TAG}"

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

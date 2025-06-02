#!/bin/bash
set -e # Exit immediately if a command exits with a non-zero status.

# --- USER CONFIGURABLE VARIABLES ---
GCP_PROJECT_ID="awanon-ai-system" # Example: your-gcp-project-id (Auto-detect: $(gcloud config get-value project 2>/dev/null))
GCP_REGION="europe-west3" # Example: us-central1 or your preferred region
AR_REPO_NAME="awanon-images" # Your Artifact Registry Docker repository name

SUPABASE_DB_URL="postgresql://postgres:[YOUR-PASSWORD]@db.bmcwsvvqhtunthbimwgz.supabase.co:5432/postgres" # MUST be filled by the user
CLOUDAMQP_URL="amqps://vbjaudbu:jGDOISOCl4HutRzKVe_a5S93gbZYHTnd@cow.rmq2.cloudamqp.com/vbjaudbu" # MUST be filled by the user
JWT_SECRET_KEY="Xk(r#zcIGa}.XZPz{wrVpnLHe5:qd^u[" # MUST be filled by the user (generate a strong random string)
GROQ_API_KEY="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" # MUST be filled by the user

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

# --- Helper Functions ---
check_placeholders() {
  if [[ "$GCP_PROJECT_ID" == "[YOUR_GCP_PROJECT_ID]" || \
        "$GCP_REGION" == "[YOUR_GCP_REGION]" || \
        "$AR_REPO_NAME" == "[YOUR_ARTIFACT_REGISTRY_REPO_NAME]" || # Added check for AR_REPO_NAME
        "$SUPABASE_DB_URL" == "[YOUR_SUPABASE_DATABASE_URL]" || \
        "$CLOUDAMQP_URL" == "[YOUR_CLOUDAMQP_RABBITMQ_URL]" || \
        "$JWT_SECRET_KEY" == "[YOUR_JWT_SECRET_KEY_min_32_chars]" || \
        ( ( "$LITELLM_MODEL_NAME" == *"groq"* || "$LITELLM_MODEL_NAME" == "groq/"* ) && "$GROQ_API_KEY" == "[YOUR_GROQ_API_KEY]") \
     ]]; then
    echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
    echo "ERROR: Please replace placeholder values in this script before running."
    echo "Search for lines containing '[YOUR_...]' and update them."
    echo "Ensure AR_REPO_NAME is also set if it's different from the default 'awanon-images'."
    echo "If LITELLM_MODEL_NAME is a Groq model, ensure GROQ_API_KEY is set."
    echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
    exit 1
  fi
}

# --- Initial Check ---
check_placeholders
echo "Placeholders check passed."
echo ""


# --- DEPLOYMENT ---

echo "Deploying ${CORE_API_SERVICE_NAME}..."
gcloud run deploy ${CORE_API_SERVICE_NAME} \
  --image "${CORE_API_IMAGE_TAG}" \
  --platform managed \
  --region "${GCP_REGION}" \
  --project "${GCP_PROJECT_ID}" \
  --allow-unauthenticated \
  --set-env-vars="DATABASE_URL=${SUPABASE_DB_URL},RABBITMQ_URL=${CLOUDAMQP_URL},JWT_SECRET_KEY=${JWT_SECRET_KEY}" \
  --port=8080 \
  --quiet
  # Add --cpu, --memory, --min-instances, --max-instances as needed

CORE_API_PUBLIC_URL=$(gcloud run services describe ${CORE_API_SERVICE_NAME} --platform managed --project=${GCP_PROJECT_ID} --region=${GCP_REGION} --format 'value(status.url)')
echo "✅ ${CORE_API_SERVICE_NAME} deployed. URL: ${CORE_API_PUBLIC_URL}"

echo "Deploying ${BRIDGE_SERVICE_NAME}..."
gcloud run deploy ${BRIDGE_SERVICE_NAME} \
  --image "${BRIDGE_IMAGE_TAG}" \
  --platform managed \
  --region "${GCP_REGION}" \
  --project "${GCP_PROJECT_ID}" \
  --allow-unauthenticated \
  --set-env-vars="DATABASE_URL=${SUPABASE_DB_URL},RABBITMQ_URL=${CLOUDAMQP_URL}" \
  --port=3000 \
  --quiet
  # Add --cpu, --memory, etc.

BRIDGE_PUBLIC_URL=$(gcloud run services describe ${BRIDGE_SERVICE_NAME} --platform managed --project=${GCP_PROJECT_ID} --region=${GCP_REGION} --format 'value(status.url)')
echo "✅ ${BRIDGE_SERVICE_NAME} deployed. URL: ${BRIDGE_PUBLIC_URL}"

echo "Deploying ${TSWIQON_AGENT_SERVICE_NAME}..."
gcloud run deploy ${TSWIQON_AGENT_SERVICE_NAME} \
  --image "${TSWIQON_AGENT_IMAGE_TAG}" \
  --platform managed \
  --region "${GCP_REGION}" \
  --project "${GCP_PROJECT_ID}" \
  --no-allow-unauthenticated \
  --set-env-vars="RABBITMQ_URL=${CLOUDAMQP_URL},GROQ_API_KEY=${GROQ_API_KEY},LITELLM_MODEL_NAME=${LITELLM_MODEL_NAME}" \
  --min-instances=1 \
  --cpu-always-allocated \
  --no-traffic \
  --quiet
  # For tswiqon_agent, consider increasing memory if FAISS index building is intensive: --memory=1Gi
echo "✅ ${TSWIQON_AGENT_SERVICE_NAME} deployed."

echo ""
echo "--- Frontend Deployment ---"
echo "The frontend image in Artifact Registry ('${FRONTEND_IMAGE_TAG}') was likely built with placeholder API URLs"
echo "from 'build_images.sh' (e.g., http://localhost:8080)."
echo "For a functional deployment, you MUST rebuild and re-push the frontend image with the"
echo "actual public URLs of the deployed backend services if this is the first full deployment or if URLs changed."
echo ""
echo "Please run these commands MANUALLY after replacing placeholders if needed:"
echo ""
echo "export CORE_API_URL_FOR_FRONTEND=\"${CORE_API_PUBLIC_URL}\""
echo "export BRIDGE_URL_FOR_FRONTEND=\"${BRIDGE_PUBLIC_URL}\""
echo ""
echo "echo \"Rebuilding frontend image with VITE_CORE_API_URL=\${CORE_API_URL_FOR_FRONTEND} and VITE_BRIDGE_API_URL=\${BRIDGE_URL_FOR_FRONTEND}\""
echo "# Ensure you are in the project root directory"
echo "docker build \\"
echo "  --build-arg VITE_CORE_API_URL=\"\${CORE_API_URL_FOR_FRONTEND}\" \\"
echo "  --build-arg VITE_BRIDGE_API_URL=\"\${BRIDGE_URL_FOR_FRONTEND}\" \\"
echo "  -t \"${FRONTEND_IMAGE_TAG}\" -f ./frontend/Dockerfile ./frontend"
echo ""
echo "echo \"Pushing updated frontend image...\""
echo "docker push \"${FRONTEND_IMAGE_TAG}\""
echo ""
echo "Once the frontend image is rebuilt and pushed with correct API URLs, deploy it by running:"
echo "gcloud run deploy ${FRONTEND_SERVICE_NAME} \\"
echo "  --image \"${FRONTEND_IMAGE_TAG}\" \\"
echo "  --platform managed \\"
echo "  --region \"${GCP_REGION}\" \\"
echo "  --project \"${GCP_PROJECT_ID}\" \\"
echo "  --allow-unauthenticated \\"
echo "  --port=80 \\" # Nginx in frontend Dockerfile listens on port 80
echo "  --quiet"
echo ""
echo "echo \"✅ Frontend deployment command ready (run manually after image update).\""

echo ""
echo "Deployment script finished. Check the GCP Cloud Run console for status."
echo "Make sure Docker is authenticated with gcloud ('gcloud auth configure-docker ${GCP_REGION}-docker.pkg.dev') before pushing images."
# Added --quiet to gcloud run deploy commands
# Added min-instances and cpu-always-allocated and no-traffic for tswiqon_agent
# Added --project to all gcloud commands to be explicit.
# Refined placeholder check and added AR_REPO_NAME to it.
# Made frontend rebuild instructions more explicit with export and context for docker build.
# Corrected the placeholder for AR_REPO_NAME in the check_placeholders function.
# Added reminder about docker authentication at the end.
# Added explicit port for tswiqon_agent (removed, as it's a worker)
# Ensured JWT_SECRET_KEY placeholder has _min_32_chars suffix as per input.
# Added --no-allow-unauthenticated for tswiqon_agent.
# Corrected frontend build commands to be copy-paste friendly.
# Removed --no-allow-unauthenticated from tswiqon as it's default for --no-traffic.
# The default when --no-traffic is specified is that the service does not receive traffic and is private.
# If `--no-allow-unauthenticated` is specified, it means only authenticated requests can invoke the service (if it were receiving traffic).
# For a worker with --no-traffic, it's implicitly private.
# Re-added --no-allow-unauthenticated for clarity that it's not a public service, though --no-traffic largely implies this.
# The service will not be invokable via HTTP, but its identity is still relevant for outbound calls.
# Final check of placeholders and structure.The `deploy_services_gcp.sh` script has been created with the provided content. I've ensured the `--project` flag is included in all `gcloud` commands and refined the placeholder check function as requested.

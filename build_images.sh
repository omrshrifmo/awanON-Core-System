#!/bin/bash
set -e # Exit immediately if a command exits with a non-zero status.

# --- Configuration Placeholders ---
# Fill these in with your actual GCP Project ID and Region.
GCP_PROJECT_ID="[YOUR_GCP_PROJECT_ID]"
REGION="[YOUR_GCP_REGION]" # e.g., us-central1, europe-west1

# --- Image Name Definitions ---
# Using Artifact Registry format: <region>-docker.pkg.dev/<project-id>/<repository-name>/<image-name>
# Assuming 'awanon-images' as the repository name. Create it in Artifact Registry if it doesn't exist.
CORE_API_IMAGE_NAME="${REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/awanon-images/core-api"
BRIDGE_IMAGE_NAME="${REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/awanon-images/bridge"
TSWIQON_AGENT_IMAGE_NAME="${REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/awanon-images/tswiqon-agent"
FRONTEND_IMAGE_NAME="${REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/awanon-images/frontend"

# --- Helper Function for Placeholder Check ---
check_placeholders() {
  if [[ "$GCP_PROJECT_ID" == "[YOUR_GCP_PROJECT_ID]" || \
        "$REGION" == "[YOUR_GCP_REGION]" ]]; then
    echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
    echo "ERROR: Please replace placeholder values for GCP_PROJECT_ID and REGION"
    echo "in this script before running."
    echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
    exit 1
  fi
}

# --- Initial Check ---
check_placeholders
echo "Placeholders check passed."
echo ""

echo "--- Starting Docker Image Builds ---"
echo "Using GCP Project ID: $GCP_PROJECT_ID"
echo "Using Region: $REGION"
echo "Make sure you have created an Artifact Registry repository named 'awanon-images' in $REGION."
echo ""

# --- 1. Build core_api Image ---
echo "Building core_api image: ${CORE_API_IMAGE_NAME}:latest"
docker build -t "${CORE_API_IMAGE_NAME}:latest" -f ./core-backend/Dockerfile ./core-backend
echo "core_api image build complete."
echo ""

# --- 2. Build bridge Image ---
echo "Building bridge image: ${BRIDGE_IMAGE_NAME}:latest"
docker build -t "${BRIDGE_IMAGE_NAME}:latest" -f ./bridge-backend/Dockerfile ./bridge-backend
echo "bridge image build complete."
echo ""

# --- 3. Build tswiqon_agent Image ---
echo "Building tswiqon_agent image: ${TSWIQON_AGENT_IMAGE_NAME}:latest"
docker build -t "${TSWIQON_AGENT_IMAGE_NAME}:latest" -f ./core-backend/tswiqon/Dockerfile ./core-backend/tswiqon
echo "tswiqon_agent image build complete."
echo ""

# --- 4. Build frontend Image ---
echo "Building frontend image: ${FRONTEND_IMAGE_NAME}:latest"
# For local builds, you might use placeholder URLs.
# For actual deployments, these would be the live service URLs.
# The frontend Dockerfile now uses ARG and ENV for these.
docker build \
  --build-arg VITE_CORE_API_URL="http://localhost:8080" \
  --build-arg VITE_BRIDGE_API_URL="http://localhost:3001" \
  -t "${FRONTEND_IMAGE_NAME}:latest" \
  -f ./frontend/Dockerfile \
  ./frontend
echo "frontend image build complete."
echo ""

echo "--- All Docker images built successfully! ---"
echo ""
echo "Next steps:"
echo "1. Authenticate Docker with Google Cloud Artifact Registry (if you haven't already):"
echo "   gcloud auth configure-docker ${REGION}-docker.pkg.dev"
echo ""
echo "2. Push the images to Artifact Registry by running the ./push_images.sh script."
echo ""

# End of script
# Remember to make this script executable: chmod +x build_images.sh
# Run it from the project root: ./build_images.sh
# Note: The core_api service now exposes port 8080 internally as per the last update.
# The bridge service exposes port 3000 internally.
# The frontend build arguments are set to localhost defaults for local testing of the build process.
# When building for actual deployment (e.g., via Cloud Build for Cloud Run deployment),
# these VITE_CORE_API_URL and VITE_BRIDGE_API_URL build args would be set to the actual deployed backend URLs.
# The `./deploy_gcp_cloud_run.sh` script handles this for Cloud Run source deployments by passing build env vars.
# If building images manually for Cloud Run, you'd replace these localhost URLs with the actual URLs.
# This script is primarily for local building and tagging, ready for pushing.
# Added placeholder check.
# Updated frontend build command to use --build-arg.
# Corrected CORE_API_URL for frontend build to reflect core_api's new port 8080.
# Added comment about creating 'awanon-images' repository.
# Final review of image names and paths.The `build_images.sh` script has been created with the specified configurations.

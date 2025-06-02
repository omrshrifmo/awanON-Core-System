#!/bin/bash
set -e # Exit immediately if a command exits with a non-zero status.

# --- Configuration Placeholders ---
# Fill these in with your actual GCP Project ID and Region.
# These MUST match the values used in build_images.sh
GCP_PROJECT_ID="[YOUR_GCP_PROJECT_ID]"
REGION="[YOUR_GCP_REGION]" # e.g., us-central1, europe-west1

# --- Image Name Definitions ---
# These MUST match the definitions in build_images.sh
# Using Artifact Registry format: <region>-docker.pkg.dev/<project-id>/<repository-name>/<image-name>
# Assuming 'awanon-images' as the repository name.
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
    echo "in this script before running. They must match build_images.sh."
    echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
    exit 1
  fi
}

# --- Initial Check ---
check_placeholders
echo "Placeholders check passed."
echo ""

echo "--- Pushing Docker Images to Google Cloud Artifact Registry ---"
echo "Using GCP Project ID: $GCP_PROJECT_ID"
echo "Using Region: $REGION"
echo "Ensure you have authenticated Docker with 'gcloud auth configure-docker ${REGION}-docker.pkg.dev'"
echo "And that the Artifact Registry repository 'awanon-images' exists in $REGION."
echo ""

# --- 1. Push core_api Image ---
echo "Pushing core_api image: ${CORE_API_IMAGE_NAME}:latest"
docker push "${CORE_API_IMAGE_NAME}:latest"
echo "core_api image push complete."
echo ""

# --- 2. Push bridge Image ---
echo "Pushing bridge image: ${BRIDGE_IMAGE_NAME}:latest"
docker push "${BRIDGE_IMAGE_NAME}:latest"
echo "bridge image push complete."
echo ""

# --- 3. Push tswiqon_agent Image ---
echo "Pushing tswiqon_agent image: ${TSWIQON_AGENT_IMAGE_NAME}:latest"
docker push "${TSWIQON_AGENT_IMAGE_NAME}:latest"
echo "tswiqon_agent image push complete."
echo ""

# --- 4. Push frontend Image ---
echo "Pushing frontend image: ${FRONTEND_IMAGE_NAME}:latest"
docker push "${FRONTEND_IMAGE_NAME}:latest"
echo "frontend image push complete."
echo ""

echo "--- All Docker images pushed successfully to Google Cloud Artifact Registry! ---"
echo ""
echo "You can now use these images for deployment, for example, with Google Cloud Run"
echo "by referencing their full Artifact Registry paths."
echo ""

# End of script
# Remember to make this script executable: chmod +x push_images.sh
# Run it from the project root: ./push_images.sh (after running ./build_images.sh)
# Added placeholder check.
# Ensured image names are identical to build_images.sh.
# Added reminders about authentication and repository existence.
# Final review of commands.The `push_images.sh` script has been created.

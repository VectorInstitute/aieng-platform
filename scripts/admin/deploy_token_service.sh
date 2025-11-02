#!/bin/bash
#
# Deploy Firebase Token Generation Service to Cloud Run
#
# This script builds and deploys the token service that generates fresh
# Firebase custom tokens for workspace service accounts.
#
# Usage:
#   ./deploy_token_service.sh [OPTIONS]
#
# Options:
#   --project PROJECT_ID       GCP project ID (default: coderd)
#   --region REGION           Cloud Run region (default: us-central1)
#   --service-name NAME       Service name (default: firebase-token-service)
#   --allow-unauthenticated   Allow unauthenticated requests (NOT recommended)
#   --dry-run                 Show commands without executing
#

set -euo pipefail

# Default configuration
PROJECT_ID="${GCP_PROJECT:-coderd}"
REGION="us-central1"
SERVICE_NAME="firebase-token-service"
ALLOW_UNAUTHENTICATED="false"
DRY_RUN="false"
FIRESTORE_DATABASE="onboarding"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --project)
      PROJECT_ID="$2"
      shift 2
      ;;
    --region)
      REGION="$2"
      shift 2
      ;;
    --service-name)
      SERVICE_NAME="$2"
      shift 2
      ;;
    --allow-unauthenticated)
      ALLOW_UNAUTHENTICATED="true"
      shift
      ;;
    --dry-run)
      DRY_RUN="true"
      shift
      ;;
    *)
      echo -e "${RED}Unknown option: $1${NC}"
      exit 1
      ;;
  esac
done

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
SERVICE_DIR="${PROJECT_ROOT}/services/token-service"

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Firebase Token Service Deployment${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${YELLOW}Configuration:${NC}"
echo "  Project ID:          ${PROJECT_ID}"
echo "  Region:              ${REGION}"
echo "  Service Name:        ${SERVICE_NAME}"
echo "  Firestore Database:  ${FIRESTORE_DATABASE}"
echo "  Service Directory:   ${SERVICE_DIR}"
echo "  Dry Run:             ${DRY_RUN}"
echo ""

# Function to execute or print commands
run_cmd() {
  if [[ "${DRY_RUN}" == "true" ]]; then
    echo -e "${YELLOW}[DRY RUN]${NC} $*"
  else
    echo -e "${GREEN}▶${NC} $*"
    "$@"
  fi
}

# Verify service directory exists
if [[ ! -d "${SERVICE_DIR}" ]]; then
  echo -e "${RED}✗ Service directory not found: ${SERVICE_DIR}${NC}"
  exit 1
fi

echo -e "${GREEN}✓${NC} Service directory found"

# Check required files
REQUIRED_FILES=("main.py" "requirements.txt" "Dockerfile")
for file in "${REQUIRED_FILES[@]}"; do
  if [[ ! -f "${SERVICE_DIR}/${file}" ]]; then
    echo -e "${RED}✗ Required file not found: ${file}${NC}"
    exit 1
  fi
done
echo -e "${GREEN}✓${NC} All required files present"
echo ""

# Step 1: Set GCP project
echo -e "${BLUE}Step 1: Configure GCP Project${NC}"
run_cmd gcloud config set project "${PROJECT_ID}"
echo ""

# Step 2: Enable required APIs
echo -e "${BLUE}Step 2: Enable Required APIs${NC}"
REQUIRED_APIS=(
  "run.googleapis.com"
  "cloudbuild.googleapis.com"
  "artifactregistry.googleapis.com"
)

for api in "${REQUIRED_APIS[@]}"; do
  echo -e "${GREEN}▶${NC} Enabling ${api}..."
  run_cmd gcloud services enable "${api}" --project="${PROJECT_ID}"
done
echo ""

# Step 3: Build and deploy to Cloud Run
echo -e "${BLUE}Step 3: Build and Deploy to Cloud Run${NC}"
echo -e "${GREEN}▶${NC} Building container image and deploying..."

DEPLOY_CMD=(
  gcloud run deploy "${SERVICE_NAME}"
  --source="${SERVICE_DIR}"
  --platform=managed
  --region="${REGION}"
  --project="${PROJECT_ID}"
  --set-env-vars="GCP_PROJECT=${PROJECT_ID},FIRESTORE_DATABASE=${FIRESTORE_DATABASE}"
  --memory=512Mi
  --cpu=1
  --timeout=60s
  --max-instances=10
  --min-instances=0
  --concurrency=80
)

if [[ "${ALLOW_UNAUTHENTICATED}" == "false" ]]; then
  DEPLOY_CMD+=(--no-allow-unauthenticated)
else
  DEPLOY_CMD+=(--allow-unauthenticated)
  echo -e "${YELLOW}⚠ Warning: Allowing unauthenticated access${NC}"
fi

run_cmd "${DEPLOY_CMD[@]}"
echo ""

# Step 4: Get service URL
if [[ "${DRY_RUN}" == "false" ]]; then
  echo -e "${BLUE}Step 4: Retrieve Service URL${NC}"
  SERVICE_URL=$(gcloud run services describe "${SERVICE_NAME}" \
    --platform=managed \
    --region="${REGION}" \
    --project="${PROJECT_ID}" \
    --format='value(status.url)')

  echo -e "${GREEN}✓${NC} Service deployed successfully!"
  echo ""
  echo -e "${GREEN}Service URL:${NC} ${SERVICE_URL}"
  echo ""

  # Step 5: Set IAM permissions for workspace service accounts
  echo -e "${BLUE}Step 5: Configure IAM Permissions${NC}"
  echo -e "${YELLOW}Note: You need to grant Cloud Run Invoker role to workspace service accounts${NC}"
  echo ""
  echo "Run the following command for each workspace service account:"
  echo ""
  echo -e "${BLUE}gcloud run services add-iam-policy-binding ${SERVICE_NAME} \\${NC}"
  echo -e "${BLUE}  --region=${REGION} \\${NC}"
  echo -e "${BLUE}  --project=${PROJECT_ID} \\${NC}"
  echo -e "${BLUE}  --member='serviceAccount:WORKSPACE_SA_EMAIL' \\${NC}"
  echo -e "${BLUE}  --role='roles/run.invoker'${NC}"
  echo ""
  echo "Or grant access to the default compute service account:"
  echo ""

  # Get project number
  PROJECT_NUMBER=$(gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)')
  DEFAULT_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

  echo -e "${BLUE}gcloud run services add-iam-policy-binding ${SERVICE_NAME} \\${NC}"
  echo -e "${BLUE}  --region=${REGION} \\${NC}"
  echo -e "${BLUE}  --project=${PROJECT_ID} \\${NC}"
  echo -e "${BLUE}  --member='serviceAccount:${DEFAULT_SA}' \\${NC}"
  echo -e "${BLUE}  --role='roles/run.invoker'${NC}"
  echo ""

  # Step 6: Test the service
  echo -e "${BLUE}Step 6: Test the Service${NC}"
  echo "Test the health endpoint:"
  echo ""
  echo -e "${BLUE}curl ${SERVICE_URL}/health${NC}"
  echo ""
  echo "Test token generation (requires authentication):"
  echo ""
  echo -e "${BLUE}curl -X POST ${SERVICE_URL}/generate-token \\${NC}"
  echo -e "${BLUE}  -H \"Authorization: Bearer \$(gcloud auth print-identity-token)\" \\${NC}"
  echo -e "${BLUE}  -H \"Content-Type: application/json\" \\${NC}"
  echo -e "${BLUE}  -d '{\"github_handle\": \"your-github-username\"}'${NC}"
  echo ""

  # Save service URL to config file
  CONFIG_FILE="${PROJECT_ROOT}/.token-service-url"
  echo "${SERVICE_URL}" > "${CONFIG_FILE}"
  echo -e "${GREEN}✓${NC} Service URL saved to ${CONFIG_FILE}"
  echo ""
fi

echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}Deployment Complete!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

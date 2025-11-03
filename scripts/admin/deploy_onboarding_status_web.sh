#!/bin/bash
#
# Deploy Onboarding Status Web Dashboard to Cloud Run
#
# This script builds and deploys the Next.js web dashboard that displays
# real-time participant onboarding status from Firestore.
#
# Usage:
#   ./deploy_onboarding_status_web.sh [OPTIONS]
#
# Options:
#   --project PROJECT_ID       GCP project ID (default: coderd)
#   --region REGION           Cloud Run region (default: us-central1)
#   --service-name NAME       Service name (default: onboarding-status-web)
#   --allow-unauthenticated   Allow unauthenticated requests (default: true for dashboards)
#   --dry-run                 Show commands without executing
#

set -euo pipefail

# Default configuration
PROJECT_ID="${GCP_PROJECT:-coderd}"
REGION="us-central1"
SERVICE_NAME="onboarding-status-web"
ALLOW_UNAUTHENTICATED="true"  # Public dashboard by default
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
    --no-allow-unauthenticated)
      ALLOW_UNAUTHENTICATED="false"
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
SERVICE_DIR="${PROJECT_ROOT}/services/onboarding-status-web"

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Onboarding Status Web Dashboard Deployment${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${YELLOW}Configuration:${NC}"
echo "  Project ID:          ${PROJECT_ID}"
echo "  Region:              ${REGION}"
echo "  Service Name:        ${SERVICE_NAME}"
echo "  Firestore Database:  ${FIRESTORE_DATABASE}"
echo "  Service Directory:   ${SERVICE_DIR}"
echo "  Allow Unauth:        ${ALLOW_UNAUTHENTICATED}"
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
REQUIRED_FILES=("package.json" "Dockerfile" "next.config.js")
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
  "firestore.googleapis.com"
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
  --set-env-vars="GCP_PROJECT_ID=${PROJECT_ID},FIRESTORE_DATABASE_ID=${FIRESTORE_DATABASE}"
  --memory=1Gi
  --cpu=1
  --timeout=300s
  --max-instances=10
  --min-instances=0
  --concurrency=80
)

if [[ "${ALLOW_UNAUTHENTICATED}" == "true" ]]; then
  DEPLOY_CMD+=(--allow-unauthenticated)
  echo -e "${YELLOW}Note: Allowing unauthenticated access (public dashboard)${NC}"
else
  DEPLOY_CMD+=(--no-allow-unauthenticated)
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
  echo -e "${GREEN}Dashboard URL:${NC} ${SERVICE_URL}"
  echo ""

  # Step 5: Configure IAM if needed
  if [[ "${ALLOW_UNAUTHENTICATED}" == "false" ]]; then
    echo -e "${BLUE}Step 5: Configure IAM Permissions${NC}"
    echo -e "${YELLOW}Note: Service requires authentication${NC}"
    echo ""
    echo "Grant access to specific users or service accounts:"
    echo ""
    echo -e "${BLUE}gcloud run services add-iam-policy-binding ${SERVICE_NAME} \\${NC}"
    echo -e "${BLUE}  --region=${REGION} \\${NC}"
    echo -e "${BLUE}  --project=${PROJECT_ID} \\${NC}"
    echo -e "${BLUE}  --member='user:EMAIL' \\${NC}"
    echo -e "${BLUE}  --role='roles/run.invoker'${NC}"
    echo ""
  fi

  # Step 6: Test the service
  echo -e "${BLUE}Step 6: Test the Dashboard${NC}"
  echo "Open the dashboard in your browser:"
  echo ""
  echo -e "${BLUE}${SERVICE_URL}${NC}"
  echo ""
  echo "The dashboard will display:"
  echo "  • Total participants"
  echo "  • Onboarded count"
  echo "  • Not onboarded count"
  echo "  • Completion percentage"
  echo "  • Real-time participant status table"
  echo ""
  echo "The dashboard auto-refreshes every 30 seconds"
  echo ""

  # Save service URL to config file
  CONFIG_FILE="${PROJECT_ROOT}/.onboarding-status-url"
  echo "${SERVICE_URL}" > "${CONFIG_FILE}"
  echo -e "${GREEN}✓${NC} Dashboard URL saved to ${CONFIG_FILE}"
  echo ""
fi

echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}Deployment Complete!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

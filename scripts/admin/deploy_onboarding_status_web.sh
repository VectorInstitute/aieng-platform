#!/bin/bash
#
# Deploy Onboarding Status Web Dashboard to Cloud Run
#
# This script builds and deploys the Next.js web dashboard that displays
# real-time participant onboarding status from Firestore with GitHub OAuth authentication.
#
# Usage:
#   ./deploy_onboarding_status_web.sh [OPTIONS]
#
# Options:
#   --project PROJECT_ID            GCP project ID (default: coderd)
#   --region REGION                Cloud Run region (default: us-central1)
#   --service-name NAME            Service name (default: onboarding-status-web)
#   --github-token TOKEN           GitHub personal access token with read:org scope (required)
#   --github-client-id ID          GitHub OAuth App Client ID (required)
#   --github-client-secret SECRET  GitHub OAuth App Client Secret (required)
#   --nextauth-secret SECRET       NextAuth secret key (auto-generated if not provided)
#   --nextauth-url URL             NextAuth URL (auto-detected from service URL if not provided)
#   --allow-unauthenticated        Allow unauthenticated requests (default: true, required for OAuth callback)
#   --dry-run                      Show commands without executing
#
# Environment Variables:
#   GITHUB_TOKEN                   GitHub token (alternative to --github-token flag)
#   GITHUB_CLIENT_ID               GitHub OAuth Client ID (alternative to --github-client-id flag)
#   GITHUB_CLIENT_SECRET           GitHub OAuth Client Secret (alternative to --github-client-secret flag)
#   NEXTAUTH_SECRET                NextAuth secret (alternative to --nextauth-secret flag)
#   GCP_PROJECT                    GCP project ID (alternative to --project flag)
#

set -euo pipefail

# Default configuration
PROJECT_ID="${GCP_PROJECT:-coderd}"
REGION="us-central1"
SERVICE_NAME="onboarding-status-web"
ALLOW_UNAUTHENTICATED="true"  # Must be true for OAuth callback to work
DRY_RUN="false"
FIRESTORE_DATABASE="onboarding"
GITHUB_TOKEN="${GITHUB_TOKEN:-}"
GITHUB_CLIENT_ID="${GITHUB_CLIENT_ID:-}"
GITHUB_CLIENT_SECRET="${GITHUB_CLIENT_SECRET:-}"
NEXTAUTH_SECRET="${NEXTAUTH_SECRET:-}"
NEXTAUTH_URL="${NEXTAUTH_URL:-}"

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
    --github-token)
      GITHUB_TOKEN="$2"
      shift 2
      ;;
    --github-client-id)
      GITHUB_CLIENT_ID="$2"
      shift 2
      ;;
    --github-client-secret)
      GITHUB_CLIENT_SECRET="$2"
      shift 2
      ;;
    --nextauth-secret)
      NEXTAUTH_SECRET="$2"
      shift 2
      ;;
    --nextauth-url)
      NEXTAUTH_URL="$2"
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

# Validate GitHub token
if [[ -z "${GITHUB_TOKEN}" ]]; then
  echo -e "${RED}✗ GitHub token not provided${NC}"
  echo ""
  echo "A GitHub token is required to check participant GitHub invite status."
  echo "Please provide a token using one of these methods:"
  echo ""
  echo "  1. Set the GITHUB_TOKEN environment variable:"
  echo -e "     ${BLUE}export GITHUB_TOKEN=ghp_your_token_here${NC}"
  echo ""
  echo "  2. Pass it as a command line argument:"
  echo -e "     ${BLUE}./deploy_onboarding_status_web.sh --github-token ghp_your_token_here${NC}"
  echo ""
  echo "The token needs the following permissions:"
  echo "  • read:org (to read organization membership and invitations)"
  echo "  • read:user (to read user profile information)"
  echo ""
  echo "Create a token at: https://github.com/settings/tokens"
  echo ""
  exit 1
fi

# Validate GitHub OAuth credentials
if [[ -z "${GITHUB_CLIENT_ID}" ]]; then
  echo -e "${RED}✗ GitHub OAuth Client ID not provided${NC}"
  echo ""
  echo "A GitHub OAuth App Client ID is required for authentication."
  echo "Please provide it using one of these methods:"
  echo ""
  echo "  1. Set the GITHUB_CLIENT_ID environment variable:"
  echo -e "     ${BLUE}export GITHUB_CLIENT_ID=your_client_id${NC}"
  echo ""
  echo "  2. Pass it as a command line argument:"
  echo -e "     ${BLUE}./deploy_onboarding_status_web.sh --github-client-id your_client_id${NC}"
  echo ""
  echo "Create a GitHub OAuth App at:"
  echo "  https://github.com/organizations/AI-Engineering-Platform/settings/applications"
  echo ""
  exit 1
fi

if [[ -z "${GITHUB_CLIENT_SECRET}" ]]; then
  echo -e "${RED}✗ GitHub OAuth Client Secret not provided${NC}"
  echo ""
  echo "A GitHub OAuth App Client Secret is required for authentication."
  echo "Please provide it using one of these methods:"
  echo ""
  echo "  1. Set the GITHUB_CLIENT_SECRET environment variable:"
  echo -e "     ${BLUE}export GITHUB_CLIENT_SECRET=your_client_secret${NC}"
  echo ""
  echo "  2. Pass it as a command line argument:"
  echo -e "     ${BLUE}./deploy_onboarding_status_web.sh --github-client-secret your_client_secret${NC}"
  echo ""
  exit 1
fi

# Generate NextAuth secret if not provided
if [[ -z "${NEXTAUTH_SECRET}" ]]; then
  echo -e "${YELLOW}⚠ NextAuth secret not provided, generating one...${NC}"
  NEXTAUTH_SECRET=$(openssl rand -base64 32)
  echo -e "${GREEN}✓${NC} Generated NextAuth secret"
fi

echo -e "${YELLOW}Configuration:${NC}"
echo "  Project ID:          ${PROJECT_ID}"
echo "  Region:              ${REGION}"
echo "  Service Name:        ${SERVICE_NAME}"
echo "  Firestore Database:  ${FIRESTORE_DATABASE}"
echo "  Service Directory:   ${SERVICE_DIR}"
echo "  Allow Unauth:        ${ALLOW_UNAUTHENTICATED}"
echo "  GitHub Token:        ${GREEN}✓ Set${NC} (${#GITHUB_TOKEN} chars)"
echo "  GitHub Client ID:    ${GREEN}✓ Set${NC} (${#GITHUB_CLIENT_ID} chars)"
echo "  GitHub Client Secret: ${GREEN}✓ Set${NC} (${#GITHUB_CLIENT_SECRET} chars)"
echo "  NextAuth Secret:     ${GREEN}✓ Set${NC} (${#NEXTAUTH_SECRET} chars)"
echo "  NextAuth URL:        ${NEXTAUTH_URL:-Will be auto-detected}"
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

# If NEXTAUTH_URL is not set, we'll need to get the service URL first and update it
# For initial deployment, we'll use a placeholder and update it after
INITIAL_DEPLOY=false
if [[ -z "${NEXTAUTH_URL}" ]]; then
  INITIAL_DEPLOY=true
  # Try to get existing service URL
  EXISTING_URL=$(gcloud run services describe "${SERVICE_NAME}" \
    --platform=managed \
    --region="${REGION}" \
    --project="${PROJECT_ID}" \
    --format='value(status.url)' 2>/dev/null || echo "")

  if [[ -n "${EXISTING_URL}" ]]; then
    NEXTAUTH_URL="${EXISTING_URL}/onboarding"
    echo -e "${GREEN}✓${NC} Using existing service URL for NextAuth: ${NEXTAUTH_URL}"
  else
    # For first deployment, use a placeholder
    NEXTAUTH_URL="https://${SERVICE_NAME}-placeholder.run.app/onboarding"
    echo -e "${YELLOW}⚠${NC} Using placeholder URL for initial deployment, will update after service is created"
  fi
fi

DEPLOY_CMD=(
  gcloud run deploy "${SERVICE_NAME}"
  --source="${SERVICE_DIR}"
  --platform=managed
  --region="${REGION}"
  --project="${PROJECT_ID}"
  --set-env-vars="GCP_PROJECT_ID=${PROJECT_ID},FIRESTORE_DATABASE_ID=${FIRESTORE_DATABASE},GITHUB_TOKEN=${GITHUB_TOKEN},GITHUB_CLIENT_ID=${GITHUB_CLIENT_ID},GITHUB_CLIENT_SECRET=${GITHUB_CLIENT_SECRET},NEXTAUTH_SECRET=${NEXTAUTH_SECRET},NEXTAUTH_URL=${NEXTAUTH_URL}"
  --memory=1Gi
  --cpu=1
  --timeout=300s
  --max-instances=10
  --min-instances=0
  --concurrency=80
)

if [[ "${ALLOW_UNAUTHENTICATED}" == "true" ]]; then
  DEPLOY_CMD+=(--allow-unauthenticated)
  echo -e "${YELLOW}Note: Allowing unauthenticated access (required for OAuth callback)${NC}"
else
  DEPLOY_CMD+=(--no-allow-unauthenticated)
fi

run_cmd "${DEPLOY_CMD[@]}"
echo ""

# Step 4: Get service URL and update if needed
if [[ "${DRY_RUN}" == "false" ]]; then
  echo -e "${BLUE}Step 4: Retrieve Service URL${NC}"
  SERVICE_URL=$(gcloud run services describe "${SERVICE_NAME}" \
    --platform=managed \
    --region="${REGION}" \
    --project="${PROJECT_ID}" \
    --format='value(status.url)')

  ACTUAL_NEXTAUTH_URL="${SERVICE_URL}/onboarding"

  # If we used a placeholder, update the service with the actual URL
  if [[ "${INITIAL_DEPLOY}" == "true" ]] && [[ "${NEXTAUTH_URL}" != "${ACTUAL_NEXTAUTH_URL}" ]]; then
    echo -e "${YELLOW}⚠${NC} Updating NextAuth URL with actual service URL..."
    gcloud run services update "${SERVICE_NAME}" \
      --platform=managed \
      --region="${REGION}" \
      --project="${PROJECT_ID}" \
      --set-env-vars="GCP_PROJECT_ID=${PROJECT_ID},FIRESTORE_DATABASE_ID=${FIRESTORE_DATABASE},GITHUB_TOKEN=${GITHUB_TOKEN},GITHUB_CLIENT_ID=${GITHUB_CLIENT_ID},GITHUB_CLIENT_SECRET=${GITHUB_CLIENT_SECRET},NEXTAUTH_SECRET=${NEXTAUTH_SECRET},NEXTAUTH_URL=${ACTUAL_NEXTAUTH_URL}"
    echo -e "${GREEN}✓${NC} Updated NextAuth URL to: ${ACTUAL_NEXTAUTH_URL}"
  fi

  echo -e "${GREEN}✓${NC} Service deployed successfully!"
  echo ""
  echo -e "${GREEN}Dashboard URL:${NC} ${SERVICE_URL}"
  echo ""

  # Step 5: Configure GitHub OAuth callback URL
  echo -e "${BLUE}Step 5: Configure GitHub OAuth Callback URL${NC}"
  CALLBACK_URL="${SERVICE_URL}/onboarding/api/auth/callback/github"
  echo ""
  echo -e "${YELLOW}⚠ IMPORTANT: Update your GitHub OAuth App configuration${NC}"
  echo ""
  echo "Go to: https://github.com/organizations/AI-Engineering-Platform/settings/applications"
  echo ""
  echo "Update your OAuth App with these URLs:"
  echo -e "  ${BLUE}Homepage URL:${NC}              ${SERVICE_URL}"
  echo -e "  ${BLUE}Authorization callback URL:${NC} ${CALLBACK_URL}"
  echo ""
  echo "Without this update, GitHub OAuth authentication will not work!"
  echo ""

  # Step 6: Authentication info
  echo -e "${BLUE}Step 6: Authentication${NC}"
  echo ""
  echo "This dashboard requires GitHub OAuth authentication."
  echo "Only members of the AI-Engineering-Platform organization can access it."
  echo ""
  echo "Authentication flow:"
  echo "  1. User visits the dashboard"
  echo "  2. User is redirected to sign in with GitHub"
  echo "  3. GitHub verifies organization membership"
  echo "  4. User is granted access if they are a member"
  echo ""

  # Step 7: Test the service
  echo -e "${BLUE}Step 7: Test the Dashboard${NC}"
  echo ""
  echo "Open the dashboard in your browser:"
  echo -e "  ${BLUE}${SERVICE_URL}/onboarding${NC}"
  echo ""
  echo "You will be prompted to sign in with GitHub."
  echo ""
  echo "After authentication, the dashboard will display:"
  echo "  • Total participants"
  echo "  • Onboarded count"
  echo "  • Not onboarded count"
  echo "  • Completion percentage"
  echo "  • GitHub invitation status"
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

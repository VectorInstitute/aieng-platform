#!/bin/bash
set -euo pipefail

# Script to create a new Coder token for analytics collection
# This token is used in the GitHub Actions workflow: .github/workflows/collect-coder-analytics.yml

# Color codes for logging
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly CYAN='\033[0;36m'
readonly NC='\033[0m' # No Color
readonly BOLD='\033[1m'

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $*"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $*"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $*" >&2
}

log_step() {
    echo -e "${CYAN}[STEP]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $*"
}

# Error handler
error_exit() {
    log_error "$1"
    exit "${2:-1}"
}

# Trap errors
trap 'error_exit "Script failed at line $LINENO"' ERR

# Main script
log_info "Starting Coder token creation process"

TIMESTAMP=$(date +%Y%m%d-%H%M%S)
TOKEN_NAME="${1:-analytics-collection-$TIMESTAMP}"
TOKEN_LIFETIME="${2:-168h}"  # Default: 7 days (168 hours - maximum allowed)

log_step "Validating Coder CLI installation"
if ! command -v coder &> /dev/null; then
    error_exit "Coder CLI is not installed. Please install it first."
fi
log_success "Coder CLI found: $(coder version | head -1)"

log_step "Checking Coder authentication status"
if ! coder login --check &> /dev/null; then
    error_exit "Not authenticated to Coder. Please run 'coder login' first."
fi
log_success "Authenticated to Coder"

log_step "Creating new token"
log_info "Token name: ${BOLD}${TOKEN_NAME}${NC}"
log_info "Token lifetime: ${BOLD}${TOKEN_LIFETIME}${NC}"

# Create the token and capture output
if ! TOKEN_OUTPUT=$(coder tokens create --name "$TOKEN_NAME" --lifetime "$TOKEN_LIFETIME" 2>&1); then
    error_exit "Failed to create token: $TOKEN_OUTPUT"
fi

log_success "Token created successfully"

# Get token details including expiry
log_step "Fetching token details"
TOKEN_LIST=$(coder tokens list)
TOKEN_INFO=$(echo "$TOKEN_LIST" | grep "$TOKEN_NAME" || true)

if [ -n "$TOKEN_INFO" ]; then
    EXPIRES_AT=$(echo "$TOKEN_INFO" | awk '{print $4}')

    # Calculate days remaining (using date command for portability)
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        EXPIRES_EPOCH=$(date -j -f "%Y-%m-%dT%H:%M:%SZ" "$EXPIRES_AT" +%s 2>/dev/null || echo "0")
    else
        # Linux
        EXPIRES_EPOCH=$(date -d "$EXPIRES_AT" +%s 2>/dev/null || echo "0")
    fi

    CURRENT_EPOCH=$(date +%s)
    SECONDS_REMAINING=$((EXPIRES_EPOCH - CURRENT_EPOCH))
    DAYS_REMAINING=$((SECONDS_REMAINING / 86400))
    HOURS_REMAINING=$(((SECONDS_REMAINING % 86400) / 3600))

    log_info "Token expires at: ${BOLD}${EXPIRES_AT}${NC}"
    log_info "Time remaining: ${BOLD}${DAYS_REMAINING} days, ${HOURS_REMAINING} hours${NC}"
fi

# Display the token prominently
echo ""
echo -e "${BOLD}${GREEN}===========================================${NC}"
echo -e "${BOLD}${GREEN}         TOKEN VALUE (COPY THIS)${NC}"
echo -e "${BOLD}${GREEN}===========================================${NC}"
echo -e "${BOLD}${YELLOW}${TOKEN_OUTPUT}${NC}"
echo -e "${BOLD}${GREEN}===========================================${NC}"
echo ""

log_warning "Store this token securely. It won't be shown again!"

# Next steps
echo -e "${BOLD}${CYAN}Next Steps:${NC}"
echo ""
echo -e "  ${BOLD}1.${NC} Update the GitHub Actions secret:"
echo -e "     ${GREEN}gh secret set CODER_TOKEN --repo VectorInstitute/aieng-platform${NC}"
echo ""
echo -e "  ${BOLD}2.${NC} Or update manually at:"
echo -e "     ${BLUE}https://github.com/VectorInstitute/aieng-platform/settings/secrets/actions${NC}"
echo ""
echo -e "  ${BOLD}3.${NC} List all tokens:"
echo -e "     ${GREEN}coder tokens list${NC}"
echo ""
echo -e "  ${BOLD}4.${NC} Remove old tokens:"
echo -e "     ${GREEN}coder tokens remove <TOKEN_ID>${NC}"
echo ""

log_info "Token will expire in ${TOKEN_LIFETIME} (maximum allowed: 168h)"
log_success "Script completed successfully"

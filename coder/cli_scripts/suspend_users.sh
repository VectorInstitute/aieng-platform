#!/usr/bin/env bash

# Script to suspend non-owner users in Coder
# Usage: ./suspend_users.sh [--dry-run]

set -euo pipefail

# Colors for output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly NC='\033[0m' # No Color

# Configuration
readonly CODER_URL="https://platform.vectorinstitute.ai"
DRY_RUN=false

# Parse arguments
if [[ "${1:-}" == "--dry-run" ]]; then
    DRY_RUN=true
fi

# Logging functions
log_info() {
    printf "${BLUE}[%s]${NC} INFO: %s\n" "$(date +'%Y-%m-%d %H:%M:%S')" "$*"
}

log_success() {
    printf "${GREEN}[%s]${NC} SUCCESS: %s\n" "$(date +'%Y-%m-%d %H:%M:%S')" "$*"
}

log_warning() {
    printf "${YELLOW}[%s]${NC} WARNING: %s\n" "$(date +'%Y-%m-%d %H:%M:%S')" "$*"
}

log_error() {
    printf "${RED}[%s]${NC} ERROR: %s\n" "$(date +'%Y-%m-%d %H:%M:%S')" "$*" >&2
}

# Check if coder CLI is installed
if ! command -v coder &> /dev/null; then
    log_error "coder CLI is not installed or not in PATH"
    exit 1
fi

log_info "Starting user suspension script${DRY_RUN:+ (DRY RUN MODE)}"

# Log in to coder
log_info "Logging in to Coder at ${CODER_URL}"
if ! coder login "${CODER_URL}"; then
    log_error "Failed to log in to Coder"
    exit 1
fi
log_success "Successfully logged in to Coder"

# Get a list of all usernames and store it in an array
log_info "Fetching list of users"
users_output=$(coder users list -c username 2>&1) || {
    log_error "Failed to fetch user list"
    exit 1
}

# Filter and store users in an array (compatible with bash 3.2+)
# Trim whitespace from each line
users=()
while IFS= read -r line; do
    # Trim leading and trailing whitespace
    line=$(echo "${line}" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
    if [[ -n "${line}" ]]; then
        users+=("${line}")
    fi
done <<EOF
$(echo "${users_output}" | grep -v "USERNAME" | grep -v "^[[:space:]]*$")
EOF

user_count=${#users[@]}
if [[ ${user_count} -eq 0 ]]; then
    log_warning "No users found"
    exit 0
fi

log_info "Found ${user_count} user(s) to process"

# Counters for summary
suspended_count=0
skipped_count=0
error_count=0

# Iterate over the list of users
for user in "${users[@]}"; do
    # Skip empty lines
    [[ -z "${user}" ]] && continue

    log_info "Processing user: ${user}"

    # Get user role
    user_info=$(coder users show "${user}" 2>&1)
    exit_code=$?
    if [[ ${exit_code} -ne 0 ]]; then
        log_error "Failed to get info for user: ${user} (exit code: ${exit_code})"
        log_error "Error output: ${user_info}"
        ((error_count++))
        continue
    fi

    role=$(echo "${user_info}" | grep "Roles:" | awk '{ print $2 }')

    if [[ -z "${role}" ]]; then
        log_warning "Could not determine role for user: ${user}"
        ((error_count++))
        continue
    fi

    # If role is not "Owner", suspend the user
    if [[ "${role}" != "Owner" ]]; then
        if [[ "${DRY_RUN}" == true ]]; then
            log_info "Would suspend user: ${user} (role: ${role})"
            ((suspended_count++))
        else
            # The <<< "" simulates the Enter button to confirm user suspension
            if coder users suspend "${user}" <<< "" 2>&1; then
                log_success "Suspended user: ${user} (role: ${role})"
                ((suspended_count++))
            else
                log_error "Failed to suspend user: ${user}"
                ((error_count++))
            fi
        fi
    else
        log_warning "Skipped owner: ${user}"
        ((skipped_count++))
    fi
done

# Print summary
echo ""
log_info "=== Summary ==="
log_info "Total users processed: ${user_count}"
log_success "Users suspended: ${suspended_count}"
log_warning "Users skipped (owners): ${skipped_count}"
if [[ ${error_count} -gt 0 ]]; then
    log_error "Errors encountered: ${error_count}"
    exit 1
else
    log_success "Script completed successfully"
fi

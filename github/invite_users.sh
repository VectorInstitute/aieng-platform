#!/usr/bin/env bash

# Script to invite GitHub users to AI-Engineering-Platform organization
# Usage: ./invite_users.sh <csv_file> [--dry-run] [--role ROLE]
#
# CSV Format: Single column with GitHub usernames (no header required)
# Example CSV:
#   username1
#   username2
#   username3

set -euo pipefail

# Colors for output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly NC='\033[0m' # No Color

# Configuration
readonly ORG_NAME="AI-Engineering-Platform"
DRY_RUN=false
ROLE="member"  # Default role: member or admin

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

# Usage function
usage() {
    cat << EOF
Usage: $0 <csv_file> [OPTIONS]

Invite GitHub users to ${ORG_NAME} organization.

Arguments:
    csv_file        Path to CSV file containing GitHub usernames (one per line)

Options:
    --dry-run       Preview actions without making changes
    --role ROLE     Set member role (member or admin, default: member)
    -h, --help      Show this help message

Examples:
    $0 users.csv
    $0 users.csv --dry-run
    $0 users.csv --role admin
    $0 users.csv --dry-run --role admin

CSV Format:
    Single column with GitHub usernames, no header required:
        username1
        username2
        username3
EOF
    exit 1
}

# Parse arguments
CSV_FILE=""
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --role)
            ROLE="$2"
            if [[ "${ROLE}" != "member" && "${ROLE}" != "admin" ]]; then
                log_error "Invalid role: ${ROLE}. Must be 'member' or 'admin'"
                exit 1
            fi
            shift 2
            ;;
        -h|--help)
            usage
            ;;
        -*)
            log_error "Unknown option: $1"
            usage
            ;;
        *)
            if [[ -z "${CSV_FILE}" ]]; then
                CSV_FILE="$1"
            else
                log_error "Multiple CSV files specified"
                usage
            fi
            shift
            ;;
    esac
done

# Validate CSV file argument
if [[ -z "${CSV_FILE}" ]]; then
    log_error "CSV file argument is required"
    usage
fi

if [[ ! -f "${CSV_FILE}" ]]; then
    log_error "CSV file not found: ${CSV_FILE}"
    exit 1
fi

# Check if gh CLI is installed
if ! command -v gh &> /dev/null; then
    log_error "gh (GitHub CLI) is not installed or not in PATH"
    log_error "Install it from: https://cli.github.com/"
    exit 1
fi

# Check if authenticated
if ! gh auth status &> /dev/null; then
    log_error "Not authenticated with GitHub CLI"
    log_error "Run: gh auth login"
    exit 1
fi

# Check if we have the required admin:org scope
if ! gh auth status 2>&1 | grep -q "admin:org"; then
    log_error "Missing required 'admin:org' scope"
    log_error "Run: gh auth refresh -h github.com -s admin:org"
    exit 1
fi

if [[ "${DRY_RUN}" == true ]]; then
    log_info "Starting GitHub invitation script (DRY RUN MODE)"
else
    log_info "Starting GitHub invitation script"
fi
log_info "Organization: ${ORG_NAME}"
log_info "Role: ${ROLE}"
log_info "CSV file: ${CSV_FILE}"

# Verify organization access
log_info "Verifying access to organization: ${ORG_NAME}"
if ! gh api "orgs/${ORG_NAME}" &> /dev/null; then
    log_error "Cannot access organization: ${ORG_NAME}"
    log_error "Make sure you have admin permissions for this organization"
    exit 1
fi
log_success "Organization access verified"

# Read usernames from CSV file
log_info "Reading usernames from CSV file"
usernames=()
line_number=0
while IFS= read -r line || [[ -n "${line}" ]]; do
    ((line_number++))

    # Trim whitespace
    username=$(echo "${line}" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')

    # Skip empty lines
    [[ -z "${username}" ]] && continue

    # Skip lines that look like headers (case-insensitive)
    if [[ "${username}" =~ ^(username|user|github|name)$ ]] && [[ ${line_number} -eq 1 ]]; then
        log_info "Skipping header line: ${username}"
        continue
    fi

    # Validate username format (GitHub usernames: alphanumeric and hyphens)
    if [[ ! "${username}" =~ ^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?$ ]]; then
        log_warning "Invalid username format at line ${line_number}: ${username}"
        continue
    fi

    usernames+=("${username}")
done < "${CSV_FILE}"

user_count=${#usernames[@]}
if [[ ${user_count} -eq 0 ]]; then
    log_error "No valid usernames found in CSV file"
    exit 1
fi

log_success "Found ${user_count} valid username(s) to process"

# Counters for summary
invited_count=0
already_member_count=0
error_count=0

# Fetch pending invitations once (outside the loop for efficiency)
log_info "Fetching pending invitations..."
pending_invitations=$(gh api "orgs/${ORG_NAME}/invitations" --jq ".[].login" 2>/dev/null || echo "")

# Process each username
for username in "${usernames[@]}"; do
    log_info "Processing user: ${username}"

    # Check if user exists on GitHub
    if ! gh api "users/${username}" &> /dev/null; then
        log_error "GitHub user not found: ${username}"
        ((error_count++))
        continue
    fi

    # Check if user is already a member
    if gh api "orgs/${ORG_NAME}/members/${username}" &> /dev/null 2>&1; then
        log_warning "User ${username} is already a member of ${ORG_NAME}"
        ((already_member_count++))
        continue
    fi

    # Check if there's a pending invitation
    if echo "${pending_invitations}" | grep -q "^${username}$"; then
        log_warning "User ${username} already has a pending invitation"
        ((already_member_count++))
        continue
    fi

    # Add user to organization
    if [[ "${DRY_RUN}" == true ]]; then
        log_info "Would add user: ${username} as ${ROLE}"
        ((invited_count++))
    else
        invite_result=$(gh api \
            --method PUT \
            -H "Accept: application/vnd.github+json" \
            -H "X-GitHub-Api-Version: 2022-11-28" \
            "orgs/${ORG_NAME}/memberships/${username}" \
            -f "role=${ROLE}" 2>&1)

        exit_code=$?
        if [[ ${exit_code} -eq 0 ]]; then
            log_success "Added user: ${username} as ${ROLE}"
            ((invited_count++))
        else
            log_error "Failed to add user: ${username}"
            log_error "Error: ${invite_result}"
            ((error_count++))
        fi
    fi
done

# Print summary
echo ""
log_info "=== Summary ==="
log_info "Total users processed: ${user_count}"
log_success "Users invited: ${invited_count}"
log_warning "Already members/pending: ${already_member_count}"

if [[ ${error_count} -gt 0 ]]; then
    log_error "Errors encountered: ${error_count}"
    exit 1
else
    if [[ "${DRY_RUN}" == true ]]; then
        log_info "Dry run completed successfully. Run without --dry-run to invite users."
    else
        log_success "Script completed successfully"
    fi
fi

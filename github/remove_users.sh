#!/usr/bin/env bash

# Script to remove GitHub users from AI-Engineering-Platform organization
# Usage: ./remove_users.sh <csv_file> [--dry-run]
#
# CSV Format: Single column with GitHub usernames or emails (no header required)
# Example CSV:
#   username1
#   user2@example.com
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

Remove GitHub users from ${ORG_NAME} organization.

Arguments:
    csv_file        Path to CSV file containing GitHub usernames or emails (one per line)

Options:
    --dry-run       Preview actions without making changes
    -h, --help      Show this help message

Examples:
    $0 users.csv
    $0 users.csv --dry-run

CSV Format:
    Single column with GitHub usernames or emails, no header required:
        username1
        user2@example.com
        username3

Notes:
    - For usernames: Removes existing organization members
    - For emails: Cancels pending invitations (cannot remove members by email)

WARNING: This will permanently remove users/invitations from the organization.
         Make sure to use --dry-run first to preview the changes.
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
    log_info "Starting GitHub user removal script (DRY RUN MODE)"
else
    log_info "Starting GitHub user removal script"
fi
log_info "Organization: ${ORG_NAME}"
log_info "CSV file: ${CSV_FILE}"

# Verify organization access
log_info "Verifying access to organization: ${ORG_NAME}"
if ! gh api "orgs/${ORG_NAME}" &> /dev/null; then
    log_error "Cannot access organization: ${ORG_NAME}"
    log_error "Make sure you have admin permissions for this organization"
    exit 1
fi
log_success "Organization access verified"

# Read identifiers (usernames or emails) from CSV file
log_info "Reading identifiers from CSV file"
identifiers=()
line_number=0
while IFS= read -r line || [[ -n "${line}" ]]; do
    ((line_number++))

    # Trim whitespace
    identifier=$(echo "${line}" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')

    # Skip empty lines
    [[ -z "${identifier}" ]] && continue

    # Skip lines that look like headers (case-insensitive)
    if [[ "${identifier}" =~ ^(username|user|github|name|email)$ ]] && [[ ${line_number} -eq 1 ]]; then
        log_info "Skipping header line: ${identifier}"
        continue
    fi

    # Validate format: either GitHub username or email
    # GitHub usernames: alphanumeric and hyphens, 1-39 characters
    # Email: basic email validation
    if [[ "${identifier}" =~ ^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?$ ]] || [[ "${identifier}" =~ ^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$ ]]; then
        identifiers+=("${identifier}")
    else
        log_warning "Invalid format at line ${line_number}: ${identifier}"
        log_warning "Must be a valid GitHub username or email address"
        continue
    fi
done < "${CSV_FILE}"

identifier_count=${#identifiers[@]}
if [[ ${identifier_count} -eq 0 ]]; then
    log_error "No valid usernames or emails found in CSV file"
    exit 1
fi

log_success "Found ${identifier_count} valid identifier(s) to process"

# Warning for non-dry-run mode
if [[ "${DRY_RUN}" == false ]]; then
    log_warning "This will remove ${identifier_count} user(s)/invitation(s) from ${ORG_NAME}"
    log_warning "Press Ctrl+C within 5 seconds to cancel..."
    sleep 5
fi

# Counters for summary
removed_count=0
invitation_cancelled_count=0
not_member_count=0
error_count=0

# Fetch pending invitations once (outside the loop for efficiency)
log_info "Fetching pending invitations..."
pending_invitations_json=$(gh api "orgs/${ORG_NAME}/invitations" 2>/dev/null || echo "[]")

# Process each identifier
for identifier in "${identifiers[@]}"; do
    log_info "Processing: ${identifier}"

    # Determine if identifier is an email or username
    is_email=false
    if [[ "${identifier}" =~ ^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$ ]]; then
        is_email=true
    fi

    if [[ "${is_email}" == true ]]; then
        # Process as email - look for pending invitations to cancel
        email="${identifier}"

        # Find invitation ID for this email
        invitation_id=$(echo "${pending_invitations_json}" | jq -r --arg email "${email}" '.[] | select(.email == $email) | .id' 2>/dev/null)

        if [[ -z "${invitation_id}" ]]; then
            log_warning "No pending invitation found for email: ${email}"
            log_warning "Note: Cannot remove organization members by email - please use their username"
            ((not_member_count++))
            continue
        fi

        # Cancel the invitation
        if [[ "${DRY_RUN}" == true ]]; then
            log_info "Would cancel invitation for: ${email} (invitation ID: ${invitation_id})"
            ((invitation_cancelled_count++))
        else
            cancel_result=$(gh api \
                --method DELETE \
                -H "Accept: application/vnd.github+json" \
                -H "X-GitHub-Api-Version: 2022-11-28" \
                "orgs/${ORG_NAME}/invitations/${invitation_id}" 2>&1)

            exit_code=$?
            if [[ ${exit_code} -eq 0 ]]; then
                log_success "Cancelled invitation for: ${email}"
                ((invitation_cancelled_count++))
            else
                log_error "Failed to cancel invitation for: ${email}"
                log_error "Error: ${cancel_result}"
                ((error_count++))
            fi
        fi
    else
        # Process as username
        username="${identifier}"

        # Check if user exists on GitHub
        if ! gh api "users/${username}" &> /dev/null; then
            log_error "GitHub user not found: ${username}"
            ((error_count++))
            continue
        fi

        # Check if user is a member of the organization
        if ! gh api "orgs/${ORG_NAME}/members/${username}" &> /dev/null 2>&1; then
            log_warning "User ${username} is not a member of ${ORG_NAME}"
            ((not_member_count++))
            continue
        fi

        # Remove user from organization
        if [[ "${DRY_RUN}" == true ]]; then
            log_info "Would remove user: ${username}"
            ((removed_count++))
        else
            remove_result=$(gh api \
                --method DELETE \
                -H "Accept: application/vnd.github+json" \
                -H "X-GitHub-Api-Version: 2022-11-28" \
                "orgs/${ORG_NAME}/members/${username}" 2>&1)

            exit_code=$?
            if [[ ${exit_code} -eq 0 ]]; then
                log_success "Removed user: ${username}"
                ((removed_count++))
            else
                log_error "Failed to remove user: ${username}"
                log_error "Error: ${remove_result}"
                ((error_count++))
            fi
        fi
    fi
done

# Print summary
echo ""
log_info "=== Summary ==="
log_info "Total identifiers processed: ${identifier_count}"
log_success "Users removed: ${removed_count}"
log_success "Invitations cancelled: ${invitation_cancelled_count}"
log_warning "Not members/no invitations: ${not_member_count}"

if [[ ${error_count} -gt 0 ]]; then
    log_error "Errors encountered: ${error_count}"
    exit 1
else
    if [[ "${DRY_RUN}" == true ]]; then
        log_info "Dry run completed successfully. Run without --dry-run to remove users/invitations."
    else
        log_success "Script completed successfully"
    fi
fi

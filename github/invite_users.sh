#!/usr/bin/env bash

# Script to invite GitHub users to AI-Engineering-Platform organization
# Usage: ./invite_users.sh <csv_file> [--dry-run] [--role ROLE]
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
    csv_file        Path to CSV file containing GitHub usernames or emails (one per line)

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
    Single column with GitHub usernames or emails, no header required:
        username1
        user2@example.com
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

# Counters for summary
invited_count=0
already_member_count=0
error_count=0

# Fetch pending invitations once (outside the loop for efficiency)
log_info "Fetching pending invitations..."
pending_invitations_json=$(gh api "orgs/${ORG_NAME}/invitations" 2>/dev/null || echo "[]")
pending_logins=$(echo "${pending_invitations_json}" | jq -r '.[].login // empty' 2>/dev/null || echo "")
pending_emails=$(echo "${pending_invitations_json}" | jq -r '.[].email // empty' 2>/dev/null || echo "")

# Process each identifier
for identifier in "${identifiers[@]}"; do
    log_info "Processing: ${identifier}"

    # Determine if identifier is an email or username
    is_email=false
    if [[ "${identifier}" =~ ^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$ ]]; then
        is_email=true
    fi

    if [[ "${is_email}" == true ]]; then
        # Process as email
        email="${identifier}"

        # Check if email already has a pending invitation
        if echo "${pending_emails}" | grep -qiF "${email}"; then
            log_warning "Email ${email} already has a pending invitation"
            ((already_member_count++))
            continue
        fi

        # Try to find if a user with this email is already a member
        # Note: We can't directly check membership by email, so we'll rely on invitation attempt

        # Map role for email invitations (GitHub API uses different values)
        # member -> direct_member, admin -> admin
        email_role="${ROLE}"
        if [[ "${ROLE}" == "member" ]]; then
            email_role="direct_member"
        fi

        # Send invitation by email
        if [[ "${DRY_RUN}" == true ]]; then
            log_info "Would send invitation to: ${email} as ${ROLE}"
            ((invited_count++))
        else
            invite_result=$(gh api \
                --method POST \
                -H "Accept: application/vnd.github+json" \
                -H "X-GitHub-Api-Version: 2022-11-28" \
                "orgs/${ORG_NAME}/invitations" \
                -f "email=${email}" \
                -f "role=${email_role}" 2>&1)

            exit_code=$?
            if [[ ${exit_code} -eq 0 ]]; then
                log_success "Sent invitation to: ${email} as ${ROLE}"
                ((invited_count++))
            else
                # Check if error indicates user is already a member
                if echo "${invite_result}" | grep -q "already a member\|already an invitee"; then
                    log_warning "Email ${email} is already a member or has a pending invitation"
                    ((already_member_count++))
                else
                    log_error "Failed to invite email: ${email}"
                    log_error "Error: ${invite_result}"
                    ((error_count++))
                fi
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

        # Check if user is already a member
        if gh api "orgs/${ORG_NAME}/members/${username}" &> /dev/null 2>&1; then
            log_warning "User ${username} is already a member of ${ORG_NAME}"
            ((already_member_count++))
            continue
        fi

        # Check if there's a pending invitation
        if echo "${pending_logins}" | grep -qF "${username}"; then
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
    fi
done

# Print summary
echo ""
log_info "=== Summary ==="
log_info "Total identifiers processed: ${identifier_count}"
log_success "Invitations sent: ${invited_count}"
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

# CLI Reference

The `aieng-platform-onboard` package provides a command-line tool for bootcamp participant onboarding, authentication, environment setup, and admin operations.

## Installation

```bash
pip install aieng-platform-onboard
```

## Commands

### `onboard`

Main command for onboarding bootcamp participants with team-specific API keys.

### `onboard admin`

Admin commands for managing participants and teams.

#### Usage

```bash
onboard [OPTIONS]
```

#### Participant Onboarding

Standard onboarding flow for bootcamp participants:

```bash
onboard \
  --bootcamp-name fall-2025 \
  --gcp-project coderd \
  --test-script tests/integration/test_api_keys.py \
  --output-dir .
```

#### Admin Status Report

View onboarding status for all participants (requires admin credentials):

```bash
onboard --admin-status-report --gcp-project coderd
```

## Admin Commands

### `onboard admin setup-participants`

Setup participants and teams from CSV file.

#### Usage

```bash
onboard admin setup-participants <csv_file> [--dry-run]
```

#### Arguments

| Argument | Description | Required |
|----------|-------------|----------|
| `csv_file` | Path to CSV file | Yes |

#### CSV Format

Required columns:
- `github_handle` - GitHub username
- `team_name` - Team name

Optional columns:
- `email` - Email address
- `first_name` - First name
- `last_name` - Last name

#### Options

| Option | Description |
|--------|-------------|
| `--dry-run` | Validate and preview changes without modifying Firestore |

#### Examples

**Setup participants from CSV:**
```bash
onboard admin setup-participants participants.csv
```

**Dry run (validate only):**
```bash
onboard admin setup-participants participants.csv --dry-run
```

**Sample CSV:**
```csv
github_handle,team_name,email,first_name,last_name
alice,team-alpha,alice@example.com,Alice,Smith
bob,team-alpha,bob@example.com,Bob,Jones
charlie,team-beta,charlie@example.com,Charlie,Brown
```

#### Requirements

- Admin credentials (service account or gcloud auth)
- Firestore write access

## Options

### Required (for participant onboarding)

| Option | Description | Example |
|--------|-------------|---------|
| `--bootcamp-name` | Name of the bootcamp | `--bootcamp-name fall-2025` |
| `--test-script` | Path to integration test script | `--test-script tests/integration/test_api_keys.py` |

### Optional

| Option | Description | Default |
|--------|-------------|---------|
| `--gcp-project` | GCP project ID | `coderd` |
| `--output-dir` | Directory for .env file | `.` (current directory) |
| `--firebase-api-key` | Firebase Web API key for token exchange | (from `FIREBASE_WEB_API_KEY` env var) |
| `--skip-test` | Skip integration tests | `False` |
| `--force` | Force re-onboarding even if already onboarded | `False` |
| `--admin-status-report` | Display onboarding status for all participants (admin only) | `False` |
| `--version` | Show version number and exit | - |

## Onboarding Process

The participant onboarding flow consists of 9 steps:

1. **Identify Participant** - Detects GitHub username from environment
2. **Fetch Authentication Token** - Retrieves fresh token from service
3. **Connect to Firestore** - Initializes secure Firestore connection
4. **Fetch Your Profile** - Reads participant data and team assignment
5. **Fetch Team API Keys** - Retrieves team-specific API keys
6. **Fetch Global Configuration** - Fetches shared configuration keys
7. **Create Environment File** - Generates .env file with all keys
8. **Run Integration Test** - Validates API keys (optional)
9. **Mark as Onboarded** - Updates participant status in Firestore

## Environment Variables

The following environment variables are used:

| Variable | Description | Required |
|----------|-------------|----------|
| `GITHUB_USER` | GitHub username for authentication | Yes |
| `FIREBASE_WEB_API_KEY` | Firebase Web API key (can be passed via `--firebase-api-key`) | Yes |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to GCP service account key (admin only) | For `--admin-status-report` |

## Exit Codes

| Code | Description |
|------|-------------|
| `0` | Success |
| `1` | Failure (authentication, connection, or configuration error) |

## Examples

### Basic Onboarding

```bash
export GITHUB_USER=myusername
onboard \
  --bootcamp-name fall-2025 \
  --test-script tests/integration/test_api_keys.py
```

### Skip Integration Tests

```bash
onboard \
  --bootcamp-name fall-2025 \
  --test-script tests/integration/test_api_keys.py \
  --skip-test
```

### Force Re-onboarding

```bash
onboard \
  --bootcamp-name fall-2025 \
  --test-script tests/integration/test_api_keys.py \
  --force
```

### Custom Output Directory

```bash
onboard \
  --bootcamp-name fall-2025 \
  --test-script tests/integration/test_api_keys.py \
  --output-dir ~/my-bootcamp
```

### Admin Status Report

```bash
# Requires admin credentials
gcloud auth application-default login
onboard --admin-status-report --gcp-project coderd
```

### Setup Participants

```bash
# Setup participants from CSV
onboard admin setup-participants config/participants.csv

# Validate CSV without making changes
onboard admin setup-participants config/participants.csv --dry-run
```

## Generated Files

### .env File

The onboarding process creates a `.env` file containing:

- Team-specific API keys (OpenAI/Gemini, Langfuse)
- Global shared configuration
- Bootcamp-specific settings

**Location:** Specified by `--output-dir` (default: current directory)

**Usage:**
```bash
source .env
```

## Troubleshooting

### Authentication Failures

- Ensure `GITHUB_USER` environment variable is set
- Verify you're added to the participant list (contact admin)
- Check token service is deployed and accessible

### Connection Failures

- Verify GCP project ID is correct
- Check Firebase Web API key is valid
- Ensure Firestore security rules allow participant access

### Integration Test Failures

- Check that .env file was created successfully
- Verify API keys are valid (contact admin if needed)
- Use `--skip-test` to bypass tests if keys need manual verification

### Admin Command Failures

- Ensure you're authenticated with proper GCP permissions:
  ```bash
  gcloud auth application-default login
  ```
- Or set `GOOGLE_APPLICATION_CREDENTIALS` to service account key path
- Verify you have Firestore read/write access for the project

### CSV Validation Errors

- Check CSV has required columns: `github_handle`, `team_name`
- Verify GitHub handles are valid (alphanumeric and hyphens, max 39 chars)
- Ensure team names are valid (alphanumeric, hyphens, underscores)
- Check for duplicate GitHub handles

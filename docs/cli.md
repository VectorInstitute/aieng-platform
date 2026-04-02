# CLI Reference

The `aieng-platform-onboard` package provides command-line tools for bootcamp participant onboarding, authentication, and administration.

## Installation

```bash
pip install aieng-platform-onboard
```

## Overview

The CLI provides two main commands:

- **`onboard`** - Participant onboarding with team-specific API keys
- **`onboard admin`** - Admin commands for managing participants and teams

Admin subcommands:

| Command | Description |
|---------|-------------|
| `setup-participants` | Load participants and teams from a CSV into Firestore |
| `delete-participants` | Remove participants (and optionally empty teams) from Firestore |
| `delete-workspaces` | Delete Coder workspaces and associated GCP resources by date |
| `offboard-users` | Remove Coder users who are no longer in the GitHub org |
| `create-gemini-keys` | Provision Gemini API keys for teams in GCP |

---

## Participant Onboarding

Main command for onboarding bootcamp participants with team-specific API keys.

### Usage

```bash
onboard [OPTIONS]
```

### Options

#### Required

| Option | Description | Example |
|--------|-------------|---------|
| `--bootcamp-name` | Name of the bootcamp | `--bootcamp-name fall-2025` |
| `--test-script` | Path to integration test script | `--test-script tests/integration/test_api_keys.py` |

#### Optional

| Option | Description | Default |
|--------|-------------|---------|
| `--gcp-project` | GCP project ID | `coderd` |
| `--output-dir` | Directory for .env file | `.` (current directory) |
| `--firebase-api-key` | Firebase Web API key for token exchange | (from `FIREBASE_WEB_API_KEY` env var) |
| `--skip-test` | Skip integration tests | `False` |
| `--force` | Force re-onboarding even if already onboarded | `False` |
| `--admin-status-report` | Display onboarding status for all participants (admin only) | `False` |
| `--version` | Show version number and exit | - |

### Onboarding Process

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

### Examples

**Basic Onboarding:**
```bash
export GITHUB_USER=myusername
onboard \
  --bootcamp-name fall-2025 \
  --test-script tests/integration/test_api_keys.py
```

**Skip Integration Tests:**
```bash
onboard \
  --bootcamp-name fall-2025 \
  --test-script tests/integration/test_api_keys.py \
  --skip-test
```

**Force Re-onboarding:**
```bash
onboard \
  --bootcamp-name fall-2025 \
  --test-script tests/integration/test_api_keys.py \
  --force
```

**Custom Output Directory:**
```bash
onboard \
  --bootcamp-name fall-2025 \
  --test-script tests/integration/test_api_keys.py \
  --output-dir ~/my-bootcamp
```

**Admin Status Report:**
```bash
# Requires admin credentials
gcloud auth application-default login
onboard --admin-status-report --gcp-project coderd
```

---

## Admin Commands

Admin commands for managing bootcamp participants and teams in Firestore.

### `onboard admin setup-participants`

Setup participants and teams from a CSV file. This command creates both team documents and participant documents in Firestore.

#### Usage

```bash
onboard admin setup-participants <csv_file> [OPTIONS]
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

**Sample CSV:**
```csv
github_handle,team_name,email,first_name,last_name
alice,team-alpha,alice@example.com,Alice,Smith
bob,team-alpha,bob@example.com,Bob,Jones
charlie,team-beta,charlie@example.com,Charlie,Brown
```

#### Options

| Option | Description |
|--------|-------------|
| `--dry-run` | Validate and preview changes without modifying Firestore |

#### Examples

**Setup participants from CSV:**
```bash
onboard admin setup-participants config/participants.csv
```

**Dry run (validate only):**
```bash
onboard admin setup-participants config/participants.csv --dry-run
```

#### Requirements

- Admin credentials (service account or gcloud auth)
- Firestore write access

---

### `onboard admin create-gemini-keys`

Create Gemini API keys for teams and store them in the Firestore onboarding database. This command automates the API key provisioning workflow by creating keys in a specified GCP project, validating them against the Gemini API, and updating team documents.

#### Usage

```bash
onboard admin create-gemini-keys --project <gcp-project-id> --bootcamp <bootcamp-name> [OPTIONS]
```

#### Arguments

| Argument | Description | Required |
|----------|-------------|----------|
| `--project` | GCP project ID where API keys will be created | Yes |
| `--bootcamp` | Bootcamp identifier for key naming (e.g., "agent-bootcamp") | Yes |

#### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--dry-run` | Preview operations without creating keys or modifying Firestore | `False` |
| `--skip-validation` | Skip Gemini API validation step (faster but skips key testing) | `False` |
| `--overwrite-existing` | Replace existing keys for teams that already have them | `False` |
| `--teams` | Comma-separated list of specific teams to process | All teams |

#### Key Naming Convention

Keys are created with the format: `{bootcamp}-{team}-gemini`

Example: `agent-bootcamp-team-alpha-gemini`

#### Workflow

1. **Validate Prerequisites** - Checks gcloud CLI, project access, API enablement, and permissions
2. **Fetch Teams** - Retrieves teams from Firestore (or filtered subset)
3. **Process Each Team**:
   - Create API key in GCP with restrictions to `generativelanguage.googleapis.com`
   - Retrieve the key string
   - Validate key against Gemini API (unless `--skip-validation`)
   - Update team document with key and metadata
4. **Display Summary** - Shows results table with created/skipped/failed teams

#### Examples

**Preview what would happen (no changes):**
```bash
onboard admin create-gemini-keys \
  --project ai-agentic-bootcamp-july-2025 \
  --bootcamp agent-bootcamp \
  --dry-run
```

**Create keys for all teams:**
```bash
onboard admin create-gemini-keys \
  --project ai-agentic-bootcamp-july-2025 \
  --bootcamp agent-bootcamp
```

**Create keys for specific teams only:**
```bash
onboard admin create-gemini-keys \
  --project ai-agentic-bootcamp-july-2025 \
  --bootcamp agent-bootcamp \
  --teams team-alpha,team-beta,team-gamma
```

**Skip validation for faster processing:**
```bash
onboard admin create-gemini-keys \
  --project ai-agentic-bootcamp-july-2025 \
  --bootcamp agent-bootcamp \
  --skip-validation
```

**Replace existing keys:**
```bash
onboard admin create-gemini-keys \
  --project ai-agentic-bootcamp-july-2025 \
  --bootcamp agent-bootcamp \
  --overwrite-existing
```

#### Requirements

- Admin credentials (service account or gcloud auth)
- GCP project access with API Keys service enabled
- IAM permissions: `serviceusage.apiKeysAdmin` or `owner` role
- Firestore write access to onboarding database
- Generative Language API enabled in target project

#### Team Document Updates

The command updates team documents with:
- `openai_api_key` - The Gemini API key string
- `openai_api_key_project` - GCP project where key was created
- `openai_api_key_created_at` - Timestamp of key creation
- `updated_at` - Last update timestamp

#### Error Handling

- **Default Behavior**: Skips teams that already have API keys
- **Partial Failures**: Continues processing all teams and displays detailed summary
- **Validation Failures**: Retries 3 times with exponential backoff
- **Quota Exceeded**: Stops processing and provides clear error message
- **Audit Trail**: Logs all created key resource names for manual review

---

### `onboard admin delete-workspaces`

Delete Coder workspaces (and their associated GCP resources) created before a given date. By default, Coder triggers a Terraform destroy to clean up the underlying VM and persistent disk. Failed Terraform runs can be retried automatically in orphan mode.

#### Usage

```bash
onboard admin delete-workspaces --before <YYYY-MM-DD> [OPTIONS]
```

#### Arguments

| Argument | Description | Required |
|----------|-------------|----------|
| `--before` | Delete workspaces created before this date (YYYY-MM-DD) | Yes |

#### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--dry-run` | Show what would be deleted without making changes | `False` |
| `--orphan` | Delete workspace records without running Terraform destroy (skips GCP cleanup) | `False` |
| `--no-auto-orphan` | Disable automatic retry with `--orphan` when Terraform fails | `False` |

#### Examples

**Preview workspaces that would be deleted:**
```bash
onboard admin delete-workspaces --before 2025-01-01 --dry-run
```

**Delete all workspaces from before a date:**
```bash
onboard admin delete-workspaces --before 2025-01-01
```

**Skip Terraform destroy (e.g. if workspace state is broken):**
```bash
onboard admin delete-workspaces --before 2025-01-01 --orphan
```

**Disable auto-orphan fallback:**
```bash
onboard admin delete-workspaces --before 2025-01-01 --no-auto-orphan
```

#### Requirements

- Coder CLI installed and authenticated (`coder login`)
- Admin role in the Coder deployment

---

### `onboard admin offboard-users`

Offboard Coder users who are no longer members of the GitHub organization. Users authenticate to Coder via GitHub OAuth, but removing someone from the GitHub org does **not** automatically clean up their Coder account. This command identifies the gap and closes it.

For each stale user the command:

1. Deletes (or orphans) all their Coder workspaces
2. Suspends or deletes their Coder account
3. Removes them from the Firestore onboarding database

Coder deployment owners are always skipped regardless of org membership.

#### Usage

```bash
onboard admin offboard-users --org <github-org> [OPTIONS]
```

#### Arguments

| Argument | Description | Required |
|----------|-------------|----------|
| `--org` | GitHub organization slug to check membership against | Yes |

#### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--dry-run` | Show what would be done without making any changes | `False` |
| `--suspend` | Suspend Coder accounts instead of deleting them (reversible) | `False` |
| `--skip-workspaces` | Skip workspace deletion (Coder account and Firestore still cleaned up) | `False` |
| `--skip-firestore` | Skip Firestore onboarding database cleanup | `False` |
| `--orphan` | Delete workspaces without running Terraform destroy | `False` |
| `--no-auto-orphan` | Disable automatic retry with `--orphan` when Terraform fails | `False` |

#### Examples

**Preview who would be offboarded:**
```bash
onboard admin offboard-users --org AI-Engineering-Platform --dry-run
```

**Suspend accounts (safer, reversible) instead of deleting:**
```bash
onboard admin offboard-users --org AI-Engineering-Platform --suspend
```

**Full hard delete (workspaces + Coder account + Firestore):**
```bash
onboard admin offboard-users --org AI-Engineering-Platform
```

**Skip Firestore cleanup (e.g. already cleaned up manually):**
```bash
onboard admin offboard-users --org AI-Engineering-Platform --skip-firestore
```

**Force-orphan all workspace deletions (if Terraform is unreliable):**
```bash
onboard admin offboard-users --org AI-Engineering-Platform --orphan
```

#### Requirements

- `gh` CLI installed and authenticated (`gh auth login`)
- Coder CLI installed and authenticated (`coder login`)
- Admin role in the Coder deployment
- Admin credentials for Firestore (unless `--skip-firestore`)

#### Recommended workflow

```bash
# 1. Always preview first
onboard admin offboard-users --org AI-Engineering-Platform --dry-run

# 2. Run with --suspend to verify before committing to deletion
onboard admin offboard-users --org AI-Engineering-Platform --suspend

# 3. Once confident, run the full delete
onboard admin offboard-users --org AI-Engineering-Platform
```

---

### `onboard admin delete-participants`

Delete participants from Firestore database. Can optionally remove empty teams after participant deletion.

#### Usage

```bash
onboard admin delete-participants <csv_file> [OPTIONS]
```

#### Arguments

| Argument | Description | Required |
|----------|-------------|----------|
| `csv_file` | Path to CSV file with participants to delete | Yes |

#### CSV Format

Required columns:
- `github_handle` - GitHub username of participant to delete

**Sample CSV:**
```csv
github_handle
alice
bob
```

#### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--dry-run` | Validate and preview changes without modifying Firestore | `False` |
| `--keep-empty-teams` | Keep teams even if they become empty after removing participants | `False` |

#### Examples

**Delete participants from CSV:**
```bash
onboard admin delete-participants config/to_remove.csv
```

**Dry run (preview only):**
```bash
onboard admin delete-participants config/to_remove.csv --dry-run
```

**Delete participants but keep empty teams:**
```bash
onboard admin delete-participants config/to_remove.csv --keep-empty-teams
```

#### Requirements

- Admin credentials (service account or gcloud auth)
- Firestore write access

---

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `GITHUB_USER` | GitHub username for authentication | Yes (for participant onboarding) |
| `FIREBASE_WEB_API_KEY` | Firebase Web API key (can be passed via `--firebase-api-key`) | Yes (for participant onboarding) |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to GCP service account key | Yes (for admin commands) |

---

## Exit Codes

| Code | Description |
|------|-------------|
| `0` | Success |
| `1` | Failure (authentication, connection, or configuration error) |

---

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

---

## Troubleshooting

### Authentication Failures

- Ensure `GITHUB_USER` environment variable is set
- Verify you're added to the participant list (contact admin)
- Check token service is deployed and accessible

**Step 2 fails with a JSON parse error** (`Expecting value: line 2 column 1`): the workspace service account does not have `roles/run.invoker` on the `firebase-token-service` Cloud Run service. Cloud Run's IAM layer rejects the request before it reaches the Flask app, returning a non-JSON body. An admin must run:
```bash
gcloud run services add-iam-policy-binding firebase-token-service \
  --region=us-central1 \
  --project=coderd \
  --member="serviceAccount:<workspace-sa>@<project>.iam.gserviceaccount.com" \
  --role="roles/run.invoker"
```
See the [Developer Guide](developer_guide.md#deploying-a-new-bootcamp) for the full new-bootcamp checklist.

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

- Check CSV has required columns: `github_handle`, `team_name` (for setup-participants)
- Check CSV has required column: `github_handle` (for delete-participants)
- Verify GitHub handles are valid (alphanumeric and hyphens, max 39 chars)
- Ensure team names are valid (alphanumeric, hyphens, underscores)
- Check for duplicate GitHub handles in CSV

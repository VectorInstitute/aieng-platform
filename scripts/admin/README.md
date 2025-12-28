# Admin Scripts for Bootcamp Onboarding

This directory contains administrative scripts for setting up the Firestore database for bootcamp participant onboarding.

## Prerequisites

1. **Python Environment**: Ensure you have Python 3.12+ and `uv` installed
2. **GCP Authentication**: Authenticate with appropriate permissions
   ```bash
   gcloud auth application-default login
   ```
3. **Required Permissions**:
   - Firestore Admin (`roles/datastore.owner`)
   - API Keys Admin (`roles/serviceusage.apiKeysAdmin`)
4. **Install Dependencies**:
   ```bash
   cd /path/to/aieng-platform
   uv sync
   ```

## Setup Workflow

Follow these steps in order to set up the onboarding system:

### 1. Prepare Participant List

Create a CSV file with participant information:

```csv
github_handle,team_name,email
alice-smith,example-team,alice.smith@example.com
bob-jones,example-team,bob.jones@example.com
```

See `config/participants.csv.example` for a template.

**Required columns:**
- `github_handle`: GitHub username (alphanumeric with hyphens, max 39 chars)
- `team_name`: Team name (alphanumeric with hyphens/underscores)
- `email`: Email address (optional but recommended)

### 2. Setup Participants and Teams

Load participants from CSV into Firestore:

```bash
python scripts/admin/setup_participants.py config/participants.csv

# Dry-run to validate without making changes:
python scripts/admin/setup_participants.py config/participants.csv --dry-run
```

This script:
- Validates CSV data
- Creates team documents in Firestore
- Creates participant documents in Firestore
- Groups participants by team

### 3. Setup Global/Shared Keys

Store keys that are shared across all participants (Embedding, Weaviate, Langfuse host):

**Option A: From .env file**
```bash
python scripts/admin/setup_global_keys.py --env-file .env.example
```

**Option B: Interactive input**
```bash
python scripts/admin/setup_global_keys.py
```

**Option C: View existing keys**
```bash
python scripts/admin/setup_global_keys.py --show-existing
```

Required keys:
- `EMBEDDING_API_KEY`, `EMBEDDING_BASE_URL`
- `WEAVIATE_API_KEY`, `WEAVIATE_HTTP_HOST`, `WEAVIATE_GRPC_HOST`, etc.
- `LANGFUSE_HOST`

### 4. Generate Gemini API Keys

Create Google Cloud API keys for each team:

```bash
python scripts/admin/generate_gemini_keys.py <bootcamp-name> \
  --gcp-project ai-agentic-bootcamp-july-2025

# Example:
python scripts/admin/generate_gemini_keys.py fall-2025 \
  --gcp-project ai-agentic-bootcamp-july-2025

# Dry-run first to validate:
python scripts/admin/generate_gemini_keys.py fall-2025 \
  --gcp-project ai-agentic-bootcamp-july-2025 \
  --dry-run
```

This script:
- Creates API keys named `{bootcamp-name}-{team-name}-gemini`
- Restricts keys to `generativelanguage.googleapis.com`
- Stores keys in team documents in Firestore
- Skips teams that already have keys (use `--force` to override)

### 5. Upload Langfuse Keys for Teams

Upload Langfuse API keys for each team from a CSV file:

```bash
python scripts/admin/upload_langfuse_keys.py config/langfuse_keys.csv

# Dry-run first to validate:
python scripts/admin/upload_langfuse_keys.py config/langfuse_keys.csv --dry-run
```

**CSV Format:**
```csv
team_name,langfuse_secret_key,langfuse_public_key
example-team,sk-lf-...,pk-lf-...
awesome-team,sk-lf-...,pk-lf-...
```

See `config/langfuse_keys.csv.example` for a template.

This script:
- Validates Langfuse key formats (sk-lf-... and pk-lf-...)
- Updates team documents with Langfuse secret and public keys
- Verifies teams exist before updating
- Shows preview of changes before applying

### 6. Generate Participant Authentication Tokens

Create Firebase authentication tokens for secure participant access:

```bash
python scripts/admin/generate_participant_tokens.py <bootcamp-name> \
  --gcp-project coderd

# Example:
python scripts/admin/generate_participant_tokens.py fall-2025 \
  --gcp-project coderd

# Dry-run first to validate:
python scripts/admin/generate_participant_tokens.py fall-2025 \
  --gcp-project coderd \
  --dry-run
```

This script:
- Generates Firebase custom tokens for each participant
- Stores tokens in GCP Secret Manager: `{bootcamp-name}-token-{github-handle}`
- Enables secure, per-participant access to Firestore
- Enforces team isolation via security rules

**Required Permissions:**
- `roles/secretmanager.admin` - To create/update secrets
- Firebase Admin SDK access

### 7. Verify Setup

Validate the complete Firestore setup:

```bash
python scripts/admin/verify_firestore_setup.py

# Strict mode (treat warnings as errors):
python scripts/admin/verify_firestore_setup.py --strict

# Show detailed team summary:
python scripts/admin/verify_firestore_setup.py --show-teams
```

This script checks:
- ✅ All global keys are present
- ✅ All teams have required fields
- ✅ All teams have API keys
- ✅ All participants reference valid teams
- ✅ No orphaned data

### 8. Deploy Firestore Security Rules

Deploy security rules to protect your Firestore database.

**Important**: Since we're using a named database (`onboarding`), rules must be deployed manually via the Firebase Console. The Firebase CLI only supports deploying to the default database.

**Steps:**

1. Go to Firebase Console: https://console.firebase.google.com/project/coderd/firestore/rules

2. Click on the **Rules** tab

3. Copy the contents of `config/firestore.rules` into the editor

4. Click **Publish** to deploy the rules

**What the rules do:**
- Enforce team isolation (users can only access their own team's data)
- Allow authenticated users to read global keys
- Allow users to update their own `onboarded` status
- Block all write operations except those explicitly allowed

## Script Reference

### `setup_participants.py`

**Purpose**: Load participants and teams from CSV into Firestore

**Usage**:
```bash
python scripts/admin/setup_participants.py <csv-file> [--dry-run]
```

**Arguments**:
- `csv_file`: Path to CSV file with participant data
- `--dry-run`: Validate without making changes

**Exit codes**:
- `0`: Success
- `1`: Validation error or failure

---

### `generate_gemini_keys.py`

**Purpose**: Generate Google Cloud API keys for Gemini for each team

**Usage**:
```bash
python scripts/admin/generate_gemini_keys.py <bootcamp-name> \
  --gcp-project <project-id> \
  [--dry-run] \
  [--force]
```

**Arguments**:
- `bootcamp_name`: Name of the bootcamp (used in key naming)
- `--gcp-project`: GCP project ID where keys should be created (required)
- `--dry-run`: Show what would be done without creating keys
- `--force`: Create new keys even if teams already have keys

**Key naming**: `{bootcamp-name}-{team-name}-gemini`

**Exit codes**:
- `0`: All keys generated successfully
- `1`: One or more failures

---

### `setup_global_keys.py`

**Purpose**: Store shared keys in Firestore (Embedding, Weaviate, Langfuse host)

**Usage**:
```bash
python scripts/admin/setup_global_keys.py \
  [--env-file <path>] \
  [--dry-run] \
  [--show-existing]
```

**Arguments**:
- `--env-file`: Path to .env file containing keys (if omitted, prompts interactively)
- `--dry-run`: Show what would be stored without making changes
- `--show-existing`: Display existing global keys and exit

**Exit codes**:
- `0`: Success
- `1`: Validation error or failure

---

### `upload_langfuse_keys.py`

**Purpose**: Upload Langfuse API keys for each team from CSV file

**Usage**:
```bash
python scripts/admin/upload_langfuse_keys.py <csv-file> [--dry-run]
```

**Arguments**:
- `csv_file`: Path to CSV file with team Langfuse keys
- `--dry-run`: Show what would be done without making changes

**CSV Format**:
```csv
team_name,langfuse_secret_key,langfuse_public_key
example-team,sk-lf-...,pk-lf-...
```

**What it does**:
- Validates Langfuse key formats (must start with `sk-lf-` and `pk-lf-`)
- Checks that teams exist in Firestore before updating
- Updates team documents with Langfuse secret and public keys
- Shows preview of changes with masked key values

**Exit codes**:
- `0`: All teams updated successfully
- `1`: One or more failures or validation errors

---

### `generate_participant_tokens.py`

**Purpose**: Generate Firebase authentication tokens for each participant

**Usage**:
```bash
python scripts/admin/generate_participant_tokens.py <bootcamp-name> \
  --gcp-project <project-id> \
  [--dry-run] \
  [--force]
```

**Arguments**:
- `bootcamp_name`: Name of the bootcamp (used in secret naming)
- `--gcp-project`: GCP project ID for Secret Manager and Firebase (required)
- `--dry-run`: Show what would be done without making changes
- `--force`: Regenerate tokens even if they already exist

**What it does**:
- Generates Firebase custom tokens with `github_handle` claim
- Stores tokens in Secret Manager: `{bootcamp-name}-token-{github-handle}`
- Enables secure, per-participant Firestore access
- Enforces team isolation via security rules

**Exit codes**:
- `0`: All tokens generated successfully
- `1`: One or more failures

**Required Permissions**:
- `roles/secretmanager.admin` - To create/update secrets in Secret Manager
- Firebase Admin SDK access (via Application Default Credentials)

---

### `verify_firestore_setup.py`

**Purpose**: Validate the complete Firestore database setup

**Usage**:
```bash
python scripts/admin/verify_firestore_setup.py [--strict] [--show-teams]
```

**Arguments**:
- `--strict`: Treat warnings as errors
- `--show-teams`: Display detailed team summary table

**Checks performed**:
- Global keys completeness
- Teams structure and fields
- Team API keys presence
- Participants structure and team references
- Data consistency

**Exit codes**:
- `0`: Verification passed
- `1`: Errors found (or warnings in strict mode)

---

### `utils.py`

**Purpose**: Shared utilities for admin scripts

**Exports**:
- Constants: `FIRESTORE_PROJECT_ID`, `FIRESTORE_DATABASE_ID`, collection names
- Functions: Firestore client initialization, validation, data retrieval
- Logging setup

## Firestore Schema

```
firestore/
├── teams/{team-name}/
│   ├── team_name: string
│   ├── openai_api_key: string (Gemini)
│   ├── openai_api_key_name: string
│   ├── participants: array<string>
│   ├── created_at: timestamp
│   └── updated_at: timestamp
│
├── participants/{github-handle}/
│   ├── github_handle: string
│   ├── team_name: string
│   ├── email: string (optional)
│   ├── onboarded: boolean
│   ├── onboarded_at: timestamp (optional)
│   ├── created_at: timestamp
│   └── updated_at: timestamp
│
└── global_keys/bootcamp-shared/
    ├── EMBEDDING_API_KEY: string
    ├── EMBEDDING_BASE_URL: string
    ├── WEAVIATE_API_KEY: string
    ├── WEAVIATE_HTTP_HOST: string
    ├── WEAVIATE_GRPC_HOST: string
    ├── WEAVIATE_HTTP_PORT: string
    ├── WEAVIATE_GRPC_PORT: string
    ├── WEAVIATE_HTTP_SECURE: string
    ├── WEAVIATE_GRPC_SECURE: string
    ├── LANGFUSE_HOST: string
    ├── created_at: timestamp
    └── updated_at: timestamp
```

## Security Rules

Firestore security rules are defined in `config/firestore.rules`.

**Access control**:
- **Global keys**: Read-only for authenticated users
- **Teams**: Read-only for authenticated users
- **Participants**: Users can only read/update their own document (can only update `onboarded` and `onboarded_at` fields)

**To apply rules**:
```bash
firebase deploy --only firestore:rules
# Or manually via Firebase Console
```

## Troubleshooting

### Authentication Issues

```bash
# Re-authenticate
gcloud auth application-default login

# Check active account
gcloud auth list
```

### Firestore Connection Issues

Ensure you're targeting the correct project:
```bash
gcloud config set project coderd
```

### API Key Creation Issues

Check permissions:
```bash
gcloud projects get-iam-policy coderd \
  --flatten="bindings[].members" \
  --filter="bindings.members:user:$(gcloud config get-value account)"
```

Required role: `roles/serviceusage.apiKeysAdmin`

### Missing Dependencies

```bash
cd /path/to/aieng-platform
uv sync
```

## Best Practices

1. **Always run with `--dry-run` first** to validate before making changes
2. **Verify setup** after each step using `verify_firestore_setup.py`
3. **Keep CSV file secure** - it contains participant information
4. **Back up Firestore** before making bulk changes
5. **Use consistent naming** for bootcamp names (alphanumeric with hyphens)
6. **Document team names** and communicate them to participants

## Example Complete Setup

```bash
# 1. Prepare CSV
cat > config/bootcamp-fall-2025.csv <<EOF
github_handle,team_name,email
alice,team-alpha,alice@example.com
bob,team-alpha,bob@example.com
carol,team-beta,carol@example.com
EOF

# 2. Setup participants (dry-run first)
python scripts/admin/setup_participants.py config/bootcamp-fall-2025.csv --dry-run
python scripts/admin/setup_participants.py config/bootcamp-fall-2025.csv

# 3. Setup global keys
python scripts/admin/setup_global_keys.py --env-file .env.example --dry-run
python scripts/admin/setup_global_keys.py --env-file .env.example

# 4. Generate Gemini keys (dry-run first)
python scripts/admin/generate_gemini_keys.py fall-2025 \
  --gcp-project ai-agentic-bootcamp-july-2025 --dry-run
python scripts/admin/generate_gemini_keys.py fall-2025 \
  --gcp-project ai-agentic-bootcamp-july-2025

# 5. Verify everything
python scripts/admin/verify_firestore_setup.py --strict
```

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review script logs for detailed error messages
3. Verify GCP permissions and authentication
4. Contact AI Engineering team

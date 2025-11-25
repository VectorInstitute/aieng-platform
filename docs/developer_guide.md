# Developer Guide

This guide provides comprehensive information for developers and administrators working with the AI Engineering Platform infrastructure.

## Overview

The AI Engineering Platform consists of multiple components that work together to provide secure, isolated development environments and automated participant management. This guide covers deployment, configuration, and maintenance procedures.

---

## Platform Components

### 1. Coder Server
- **Purpose**: Provides containerized development environments
- **Deployment**: GCP VM with Terraform
- **Documentation**: See [Coder Deployment](index.md#1-coder-deployment-for-gcp)

### 2. Participant Onboarding System
- **Purpose**: Automated participant authentication and API key distribution
- **Components**: Firebase Authentication, Firestore, Cloud Functions
- **Documentation**: See [Participant Onboarding](index.md#2-participant-onboarding-system)

### 3. Onboarding Status Dashboard
- **Purpose**: Real-time monitoring of participant onboarding status
- **Deployment**: Next.js on Cloud Run with Load Balancer path-based routing
- **Access**: `https://platform.vectorinstitute.ai/onboarding`

---

## Infrastructure Deployment

### Coder Server Deployment

Follow the comprehensive deployment guide in the `coder/deploy/` directory.

**Quick Start:**
```bash
cd coder/deploy
terraform init
terraform plan
terraform apply
```

For detailed instructions, see [`coder/deploy/README.md`](../coder/deploy/README.md).

### Onboarding Status Web Dashboard

The onboarding status dashboard is deployed on Cloud Run and integrated with the main platform load balancer using path-based routing.

**Setup Guide:** [Onboarding Status Web - Load Balancer Setup](onboarding-status-web-load-balancer-setup.md)

This guide covers:

- Configuring Next.js with basePath for path-based routing
- Creating serverless Network Endpoint Groups (NEG)
- Setting up backend services for Cloud Run
- Configuring load balancer path matchers
- Deployment and verification procedures
- Troubleshooting common issues

**Automated Deployment (Recommended):**

The service is automatically deployed via GitHub Actions when changes are pushed to the `main` branch. The workflow:
- Builds and tests the Docker container
- Pushes to Google Artifact Registry
- Deploys to Cloud Run
- Verifies health checks

**Manual Deployment:**
```bash
./scripts/admin/deploy_onboarding_status_web.sh
```

**Access URL:**
```
https://platform.vectorinstitute.ai/onboarding
```

**Required GitHub Secrets for Automated Deployment:**

Configure these secrets in GitHub repository settings (`Settings` → `Secrets and variables` → `Actions`):

1. **GCP_PROJECT_ID**: Your GCP project ID (e.g., `coderd`)
2. **WIF_PROVIDER**: Workload Identity Federation provider
   - Format: `projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/POOL_ID/providers/PROVIDER_ID`
3. **GCP_SERVICE_ACCOUNT**: Service account email for deployment
   - Format: `SERVICE_ACCOUNT_NAME@PROJECT_ID.iam.gserviceaccount.com`
   - Required roles: `roles/run.admin`, `roles/iam.serviceAccountUser`, `roles/artifactregistry.admin`
4. **GH_ORG_TOKEN**: Personal access token with `read:org` scope for checking GitHub organization membership

---

## Service Architecture

### Load Balancer Configuration

The platform uses a single Google Cloud Load Balancer to route traffic to multiple backend services:

```
platform.vectorinstitute.ai/
├── /                    → Coder Server (VM: coder-entrypoint)
├── /onboarding          → Cloud Run (onboarding-status-web)
└── /onboarding/*        → Cloud Run (onboarding-status-web)
```

**Key Resources:**

| Resource | Name | Purpose |
|----------|------|---------|
| External IP | `coderd-https-lb-ip` | Static IP for load balancer |
| HTTPS Forwarding Rule | `coderd-https-forwarding-rule` | Routes HTTPS traffic |
| HTTPS Proxy | `coderd-https-proxy` | SSL termination |
| URL Map | `https-url-map` | Path-based routing configuration |
| Backend Service (Coder) | `coderd-backend` | Routes to Coder VM |
| Backend Service (Onboarding) | `onboarding-backend` | Routes to Cloud Run |

### Firebase Services

The platform uses Firebase for authentication and data storage:

- **Firebase Authentication**: Custom token generation for participants
- **Firestore**: Participant data, team assignments, and API keys
- **Firebase Security Rules**: Enforce team-level data isolation

---

## Administration

### Participant Management

#### Adding Participants

Use the admin scripts to add new participants:

```bash
python scripts/admin/setup_participants.py
```

**Requirements:**
- CSV file with participant information
- Firebase admin credentials
- Team assignments

#### Viewing Onboarding Status

**Command Line:**
```bash
onboard --admin-status-report --gcp-project coderd
```

**Web Dashboard:**
```
https://platform.vectorinstitute.ai/onboarding
```

The dashboard provides:
- Real-time participant status
- Onboarding completion rates
- Filtering by status
- CSV export functionality

---

## Monitoring and Maintenance

### Health Checks

**Coder Server:**
```bash
curl -I https://platform.vectorinstitute.ai/
```

**Onboarding Dashboard:**
```bash
curl -I https://platform.vectorinstitute.ai/onboarding
```

**Onboarding API:**
```bash
curl https://platform.vectorinstitute.ai/onboarding/api/participants
```

### Log Access

**Cloud Run Logs:**
```bash
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=onboarding-status-web" \
  --project=coderd \
  --limit=50 \
  --format=json
```

**Coder Server Logs:**
```bash
# SSH into VM
gcloud compute ssh coder-entrypoint --project=coderd --zone=us-central1-a

# View logs
sudo journalctl -u coder -f
```

### Resource Management

**List Active Services:**
```bash
# Cloud Run services
gcloud run services list --project=coderd

# Compute instances
gcloud compute instances list --project=coderd

# Backend services
gcloud compute backend-services list --project=coderd
```

---

# Coder Templates Configuration Guide

This guide provides comprehensive instructions for configuring and deploying Coder templates to support workspace VMs in GCP.

## Prerequisites

- Coder server deployed and accessible
- GCP project for workspace VMs (can be separate from Coder server project)
- Appropriate GCP permissions configured
- Coder CLI installed

## Architecture Overview

The setup consists of two main components:

1. **Coder Server**: Runs the control plane and executes Terraform templates
2. **Workspace VMs**: Individual development environments created from templates

## GCP Permissions Setup

### Required Service Accounts

1. **Coder Server Service Account**: Used by Coder to create resources
   - Example: `coder-admin@coderd.iam.gserviceaccount.com`

2. **Workspace VM Service Account**: Used by individual workspace VMs
   - Default compute service account: `PROJECT_NUMBER-compute@developer.gserviceaccount.com`

### Permission Configuration

#### For Coder Server Service Account

Grant the following roles on the workspace project:

```bash
gcloud projects add-iam-policy-binding WORKSPACE_PROJECT_ID \
  --member="serviceAccount:CODER_SERVER_SERVICE_ACCOUNT" \
  --role="roles/compute.admin"

gcloud projects add-iam-policy-binding WORKSPACE_PROJECT_ID \
  --member="serviceAccount:CODER_SERVER_SERVICE_ACCOUNT" \
  --role="roles/iam.serviceAccountUser"
```

#### For Workspace VM Service Account

Grant the following roles on the workspace project:

```bash
gcloud projects add-iam-policy-binding WORKSPACE_PROJECT_ID \
  --member="serviceAccount:PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
  --role="roles/compute.admin"

gcloud projects add-iam-policy-binding WORKSPACE_PROJECT_ID \
  --member="serviceAccount:PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
  --role="roles/iam.serviceAccountUser"
```

### Enable Required APIs

```bash
gcloud config set project WORKSPACE_PROJECT_ID
gcloud services enable compute.googleapis.com
```

## Template Configuration

### 1. Configure Template for Target Project

Update the provider configuration in `main.tf`:

```hcl
provider "google" {
  zone    = var.zone
  project = "your-workspace-project-id"
}
```

### 2. Update Service Account Reference

Ensure the service account email matches your workspace project:

```hcl
locals {
  default_service_account_email = "PROJECT_NUMBER-compute@developer.gserviceaccount.com"
}
```

### 3. Update Resource Project References

Ensure all resources reference the correct project:

```hcl
resource "google_compute_disk" "pd" {
  project = "your-workspace-project-id"
  # ... other configuration
}
```

### 4. Configure Template Variables

Copy and update the terraform variables file:

```bash
cd templates/bootcamp
cp terraform.tfvars.example terraform.tfvars
```

Update `terraform.tfvars` with your values:

```hcl
project = "your-workspace-project-id"
region = "us-central1"
zone = "us-central1-a"
machine_type = "e2-medium"
pd_size = 10
github_repo = "https://github.com/your-org/your-repo"
github_branch = "main"
github_app_id = "primary-github"
container_image = "your-org/your-image:latest"
jupyterlab = "true"
codeserver = "true"
streamlit = "true"
```

## Deployment Steps

### 1. Install Coder CLI

```bash
curl -fsSL https://coder.com/install.sh | sh
```

Or using Homebrew:

```bash
brew install coder/coder/coder
```

### 2. Authenticate with Coder Instance

```bash
coder login https://your-coder-instance-url
```

### 3. Deploy Template

Navigate to the template directory and push:

```bash
cd templates/bootcamp
coder templates push bootcamp --directory . --url https://your-coder-instance-url
```

### 4. Verify Deployment

Visit your Coder instance dashboard to confirm the template is available and can create workspaces successfully.

## Troubleshooting

### Permission Errors

If you encounter `403: Required 'compute.disks.create' permission` errors:

1. Verify the Coder server service account has `roles/compute.admin` on the workspace project
2. Check that the workspace VM service account has necessary permissions
3. Ensure all project references in the template are correct
4. Wait 1-2 minutes for IAM changes to propagate

### Template Push Failures

1. Verify Coder CLI authentication
2. Check template syntax with `terraform validate`
3. Ensure all required variables are defined in `terraform.tfvars`

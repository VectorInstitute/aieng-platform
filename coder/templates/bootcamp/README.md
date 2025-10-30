# Bootcamp Workspace Template for Coder on GCP

This template provisions Coder workspaces on Google Cloud Platform (GCP) for Vecto Bootcamp environments. It uses Terraform to launch a VM, attach a persistent disk, and run a Docker container with your preferred development stack.

## Features

- **GCP VM Provisioning**: Deploys a VM with configurable machine type, region, and zone.
- **Persistent Disk**: Attaches a managed disk for workspace data, mounted at `/home/coder`.
- **Custom Docker Image**: Supports custom container images for Python, ML, or other stacks.
- **Workspace Apps**: Optionally enables JupyterLab, code-server, and Streamlit via Terraform variables.
- **GitHub Integration**: Clones a specified repository and branch on workspace startup.
- **External Auth**: Integrates with GitHub authentication for secure access.

## Prerequisites

- [Coder](https://coder.com) instance running on GCP
- [Terraform](https://developer.hashicorp.com/terraform/install)
- [gcloud CLI](https://cloud.google.com/sdk/docs/install)
- GCP Service Account with required IAM roles (Compute Admin, Service Account User)
- Docker image available in Google Artifact Registry

## Usage

1. **Configure Variables**
   Copy `terraform.tfvars.example` to `terraform.tfvars` and update values:
   - `project`, `region`, `zone`: GCP settings
   - `machine_type`: VM type (e.g., `e2-medium`)
   - `container_image`: Docker image URI
   - `jupyterlab`, `codeserver`, `streamlit`: `"true"` or `"false"` to enable apps
   - `github_repo`, `github_branch`: Repository and branch to clone

2. **Push Template to Coder**
   ```sh
   coder login <your-coder-instance-url>
   cp terraform.tfvars.example terraform.tfvars
   coder templates push
   ```

3. **Verify Workspace**
   Launch a workspace from the Coder dashboard and confirm your environment is set up.

## Reference

- [Coder Templates Documentation](https://coder.com/docs/admin/templates/creating-templates)
- [GCP VM Documentation](https://cloud.google.com/compute/docs/instances)
- [Docker Build & Push Guide](../../docker/README.md)

> **Note:**
> This template is a starting point. Customize the Terraform files and Docker images to fit your

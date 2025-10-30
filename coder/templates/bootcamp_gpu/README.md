# Bootcamp GPU Workspace Template for Coder on GCP

This template provisions Coder workspaces on Google Cloud Platform (GCP) with GPU access, designed for bootcamps and development environments that require accelerated computing.

## Features

- **GCP VM with GPU**: Deploys a VM instance with configurable GPU type.
- **Persistent Disk**: Attaches a managed disk for workspace data, mounted at `/home/coder`.
- **Custom Docker Image**: Supports custom container images with CUDA, Python, and other ML/AI tools.
- **Workspace Apps**: Optionally enables JupyterLab, code-server, and Streamlit via Terraform variables.
- **GitHub Integration**: Clones a specified repository and branch on workspace startup.
- **External Auth**: Integrates with GitHub authentication for secure access.

## Prerequisites

- [Coder](https://coder.com) instance running on GCP
- [Terraform](https://developer.hashicorp.com/terraform/install)
- [gcloud CLI](https://cloud.google.com/sdk/docs/install)
- GCP Service Account with required IAM roles (Compute Admin, Service Account User)
- Docker image with GPU support (see [`docker/nvidia_cuda/Dockerfile`](../../docker/nvidia_cuda/Dockerfile)) available in Google Artifact Registry.

## Usage

1. **Configure Variables**
   Copy `terraform.tfvars.example` to `terraform.tfvars` and update values:
   - `project`, `region`, `zone`: GCP settings
   - `machine_type`: VM type (e.g., `n1-standard-4`)
   - `guest_accelerator_type`: GPU type (e.g., `nvidia-tesla-t4`)
   - `container_image`: Docker image URI
   - `jupyterlab`, `codeserver`, `streamlit`: `"true"` or `"false"` to enable apps

2. **Push Template to Coder**
   ```sh
   coder login <your-coder-instance-url>
   cp terraform.tfvars.example terraform.tfvars
   coder templates push <template-name>
   ```

3. **Verify Workspace**
   Launch a workspace from the Coder dashboard and confirm GPU availability (e.g., `nvidia-smi`).

## Reference

- [Coder Templates Documentation](https://coder.com/docs/admin/templates/creating-templates)
- [GCP GPU VM Documentation](https://cloud.google.com/compute/docs/gpus)
- [Docker CUDA Images](https://hub.docker.com/r/nvidia/cuda)

> **Note:**
> This template is a starting point. Customize the Terraform files and Docker images to fit your bootcamp requirements.

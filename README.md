# AI Engineering Platform

## 1. Coder Deployment for GCP

The folder `coder` contains all resources needed to deploy a [Coder](https://coder.com) instance on Google Cloud Platform (GCP), along with reusable workspace templates and Docker images for the workspace environment.

### Structure

- **deploy/**  
  Terraform scripts and startup automation for provisioning the Coder server on a GCP VM.  
  
- **docker/**  
  Dockerfiles and guides for building custom images used by Coder workspace templates.  

- **templates/**  
  Coder workspace templates for reproducible, containerized development environments on GCP.  

## Usage

1. **Provision Coder on GCP**  
   Follow the steps in [`deploy/README.md`](coder/deploy/README.md) to set up your GCP environment and deploy the Coder server using Terraform.

2. **Build and Push Docker Images**  
   Use [`docker/README.md`](coder/docker/README.md) to build and upload Docker images required by your templates.

3. **Push Workspace Templates**  
   See [`templates/README.md`](coder/templates/README.md) for instructions on uploading workspace templates to your Coder instance.
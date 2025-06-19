# Coder Deploy

Deployment scripts for the Coder (https://coder.com) cloud development environment on a GCP instance. Leverages Terraform for a simple, turnkey deployment from the command line.

## Setup

First, install all the following software on your local environment:
- [gcloud CLI](https://cloud.google.com/sdk/docs/install)
- [Terraform](https://developer.hashicorp.com/terraform/install)
- [Python 3.10+](https://www.python.org/downloads/)
- [Docker](https://docs.docker.com/engine/install/)

### gcloud environment setup

    gcloud init
    gcloud auth login
    gcloud auth application-default login
    gcloud config set project <gcp-project-name>

### GCP Service Account setup

You will also need a service account in GCP that will be connected to this VM. There are some clear and simple instructions from Coder here:

https://github.com/coder/coder/tree/main/examples/templates/gcp-linux#readme

### Terraform environment setup

You'll need a `terraform.tfvars` file in this folder. Copy over the example file and update values as needed:

    cp terraform.tfvars.example terraform.tfvars

## Terraform Deployment

### Start the instance

    terraform init -var-file=terraform.tfvars
    terraform apply -var-file=terraform.tfvars

### Stop the instance

    terraform destroy -var-file=../terraform.tfvars
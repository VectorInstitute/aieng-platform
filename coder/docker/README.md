# Docker Build & Push Guide

This guide explains how to build Docker images from the directories in this folder and push them to Google Cloud Artifact Registry using the `gcloud` CLI.

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) installed
- [gcloud CLI](https://cloud.google.com/sdk/docs/install) installed and authenticated
- Access to a Google Cloud project with Artifact Registry enabled

## Steps

### 1. Gcloud environment setup

```sh
gcloud init
gcloud auth login
gcloud auth application-default login
gcloud config set project <gcp-project-id>
```

### 2. Create the artifact repository

Skip this step if you already have an artifact repository in Google Cloud Artifact Registry that you can use.

```sh
gcloud artifacts repositories create <repository-name> --repository-format=docker --location=<location> --description="Docker repository"
```

Example:

```sh
gcloud artifacts repositories create vector-bootcamp --repository-format=docker --location=us-central1 --description="Docker repository for docker images used in the Vector Bootcamp"
```

### 3. Build and push the docker images to the repository

Navigate to the directory containing the `Dockerfile` you want to and run the following

```sh
gcloud builds submit --region=<location> --tag <location>-docker.pkg.dev/<project-id>/<repository-name>/<image-name>:<tag-name>
```

Example:

```sh
gcloud builds submit --region=us-central1 --tag us-central1-docker.pkg.dev/axial-iris-462715-e6/vbootcamp/bootcamp-image:test
```

After the build is complete, you can find the docker imgae in the repository in Google Cloud Artifact Registry.

## References

- [Build and push a Docker image with Cloud Build](https://cloud.google.com/build/docs/build-push-docker-image)
- [gcloud CLI Documentation](https://cloud.google.com/sdk/gcloud)

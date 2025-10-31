# AI Engineering Platform

----------------------------------------------------------------------------------------

[![PyPI](https://img.shields.io/pypi/v/aieng-platform-onboard)](https://pypi.org/project/aieng-platform-onboard)
[![code checks](https://github.com/VectorInstitute/aieng-platform/actions/workflows/code_checks.yml/badge.svg)](https://github.com/VectorInstitute/aieng-platform/actions/workflows/code_checks.yml)
[![docs](https://github.com/VectorInstitute/aieng-platform/actions/workflows/docs.yml/badge.svg)](https://github.com/VectorInstitute/aieng-platform/actions/workflows/docs.yml)
![GitHub License](https://img.shields.io/github/license/VectorInstitute/aieng-platform)


Infrastructure and tooling for AI Engineering bootcamps, providing secure, isolated development environments and automated participant onboarding.

## Overview

This platform consists of two main components:

1. **Coder Deployment** - Containerized development environments on GCP
2. **Participant Onboarding System** - Secure, automated participant onboarding

---

## 1. Coder Deployment for GCP

The `coder` folder contains all resources needed to deploy a [Coder](https://coder.com) instance on Google Cloud Platform (GCP), along with reusable workspace templates and Docker images for the workspace environment.

### Structure

- **deploy/** - Terraform scripts and startup automation for provisioning the Coder server on a GCP VM
- **docker/** - Dockerfiles and guides for building custom images used by Coder workspace templates
- **templates/** - Coder workspace templates for reproducible, containerized development environments on GCP

### Usage

1. **Provision Coder on GCP** - Follow the steps in [`coder/deploy/README.md`](coder/deploy/README.md)
2. **Build and Push Docker Images** - See [`coder/docker/README.md`](coder/docker/README.md)
3. **Push Workspace Templates** - See [`coder/templates/README.md`](coder/templates/README.md)

---

## 2. Participant Onboarding System

Automated system for securely distributing team-specific API keys to bootcamp participants using Firebase Authentication and Firestore.

### Features

**Secure Authentication** - Firebase custom tokens with per-participant access
**Team Isolation** - Firestore security rules enforce team-level data separation
**Automated Onboarding** - One-command setup for participants
**API Key Management** - Automated generation and distribution of:

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                          Admin Phase                            │
├─────────────────────────────────────────────────────────────────┤
│  1. Setup participants and teams in Firestore                   │
│  2. Generate team-specific API keys                             │
│  3. Setup shared keys                                           │
│  4. Generate Firebase authentication tokens                     │
│  5. Deploy Firestore security rules                             │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                       Participant Phase                         │
├─────────────────────────────────────────────────────────────────┤
│  1. Run onboarding script in Coder workspace                    │
│  2. Script authenticates using Firebase custom token            │
│  3. Fetch team-specific API keys (security rules enforced)      │
│  4. Create .env file with all credentials                       │
│  5. Run integration tests to verify keys                        │
└─────────────────────────────────────────────────────────────────┘
```

## Requirements

- Python 3.12+
- `uv` package manager
- GCP project with Firestore and Secret Manager enabled
- Firebase project with Authentication enabled
- Appropriate GCP permissions (see admin guide)

## Installation

```bash
# Clone repository
git clone <repository-url>
cd aieng-platform

# Install dependencies
uv sync

# Authenticate with GCP
gcloud auth application-default login
```

---

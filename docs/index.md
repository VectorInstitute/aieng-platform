# AI Engineering Platform

----------------------------------------------------------------------------------------

[![PyPI](https://img.shields.io/pypi/v/aieng-platform-onboard)](https://pypi.org/project/aieng-platform-onboard)
[![code checks](https://github.com/VectorInstitute/aieng-platform/actions/workflows/code_checks.yml/badge.svg)](https://github.com/VectorInstitute/aieng-platform/actions/workflows/code_checks.yml)
[![unit tests](https://github.com/VectorInstitute/aieng-platform/actions/workflows/unit_tests.yml/badge.svg)](https://github.com/VectorInstitute/aieng-platform/actions/workflows/unit_tests.yml)
[![docs](https://github.com/VectorInstitute/aieng-platform/actions/workflows/docs.yml/badge.svg)](https://github.com/VectorInstitute/aieng-platform/actions/workflows/docs.yml)
[![codecov](https://codecov.io/github/VectorInstitute/aieng-platform/graph/badge.svg?token=83MYFZ3UPA)](https://codecov.io/github/VectorInstitute/aieng-platform)
![GitHub License](https://img.shields.io/github/license/VectorInstitute/aieng-platform)


Infrastructure and tooling for AI Engineering bootcamps, providing secure, isolated development environments and automated participant onboarding.

## Overview

This platform consists of the following components:

1. **Coder Deployment** - Containerized development environments supported by [Coder](https://coder.com)
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

- **Secure Authentication** - Firebase custom tokens with per-participant access
- **Team Isolation** - Firestore security rules enforce team-level data separation
- **Automated Onboarding** - One-command setup for participants
- **API Key Management** - Automated generation and distribution of API keys

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                          Admin Phase                            │
├─────────────────────────────────────────────────────────────────┤
│  1. Setup teams and participants in Firestore                   │
│  2. Generate team-specific API keys and shared keys             │
│  3. Add users to github AI-Engineering-Platform org             │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                       Participant Phase                         │
├─────────────────────────────────────────────────────────────────┤
│  1. Run onboarding script in Coder workspace                    │
│  2. Script authenticates using token server                     │
│  3. Fetches team-specific API keys (security rules enforced)    │
│  4. Creates .env file with all credentials                      │
│  5. Runs integration tests to verify keys, marks onboard status │
└─────────────────────────────────────────────────────────────────┘
```

---

# Onboarding Status Web - Load Balancer Path-Based Routing Setup

This document provides step-by-step instructions for configuring path-based routing to serve the Onboarding Status Web dashboard at `https://platform.vectorinstitute.ai/onboarding` using Google Cloud Load Balancer.

## Overview

The setup routes traffic from `platform.vectorinstitute.ai/onboarding` to a Cloud Run service while keeping all other traffic (including the root path) routed to the Coder server VM.

**Architecture:**
- `platform.vectorinstitute.ai/` → Coder Server (VM: `coder-entrypoint`)
- `platform.vectorinstitute.ai/onboarding` → Cloud Run (`onboarding-status-web`)

## Prerequisites

- GCP project: `coderd`
- Existing load balancer with:
  - External IP: `coderd-https-lb-ip`
  - HTTPS forwarding rule: `coderd-https-forwarding-rule`
  - HTTPS proxy: `coderd-https-proxy`
  - URL map: `https-url-map`
  - Backend service: `coderd-backend` (pointing to Coder VM)
- Cloud Run service: `onboarding-status-web` already deployed

## Step 1: Configure Next.js Base Path

Update the Next.js configuration to serve the app under the `/onboarding` path.

**File:** `services/onboarding-status-web/next.config.js`

```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  basePath: '/onboarding',
  output: 'standalone',
  eslint: {
    ignoreDuringBuilds: true,
  },
  typescript: {
    ignoreBuildErrors: false,
  },
}

module.exports = nextConfig
```

**Important:** Update the API fetch path in the client code to use the absolute path:

**File:** `services/onboarding-status-web/app/page.tsx`

Change:
```javascript
const response = await fetch('/api/participants', {
```

To:
```javascript
const response = await fetch('/onboarding/api/participants', {
```

## Step 2: Create Serverless Network Endpoint Group (NEG)

Create a serverless NEG that points to the Cloud Run service.

```bash
gcloud compute network-endpoint-groups create onboarding-status-neg \
  --project=coderd \
  --region=us-central1 \
  --network-endpoint-type=serverless \
  --cloud-run-service=onboarding-status-web
```

**Verification:**
```bash
gcloud compute network-endpoint-groups describe onboarding-status-neg \
  --project=coderd \
  --region=us-central1
```

## Step 3: Create Backend Service

Create a backend service for the onboarding dashboard.

```bash
gcloud compute backend-services create onboarding-backend \
  --project=coderd \
  --global \
  --load-balancing-scheme=EXTERNAL_MANAGED
```

**Verification:**
```bash
gcloud compute backend-services describe onboarding-backend \
  --project=coderd \
  --global
```

## Step 4: Add NEG to Backend Service

Connect the serverless NEG to the backend service.

```bash
gcloud compute backend-services add-backend onboarding-backend \
  --project=coderd \
  --global \
  --network-endpoint-group=onboarding-status-neg \
  --network-endpoint-group-region=us-central1
```

**Verification:**
```bash
gcloud compute backend-services describe onboarding-backend \
  --project=coderd \
  --global \
  --format="yaml(name,backends)"
```

## Step 5: Backup Current URL Map

Before making changes, backup the existing URL map configuration.

```bash
gcloud compute url-maps export https-url-map \
  --project=coderd \
  --destination=url-map-backup-$(date +%Y%m%d).yaml
```

## Step 6: Update URL Map with Path-Based Routing

Add path matcher rules to route `/onboarding` traffic to the Cloud Run backend.

```bash
gcloud compute url-maps add-path-matcher https-url-map \
  --project=coderd \
  --path-matcher-name=onboarding-matcher \
  --default-service=coderd-backend \
  --path-rules="/onboarding=onboarding-backend,/onboarding/*=onboarding-backend"
```

**Verification:**
```bash
gcloud compute url-maps describe https-url-map \
  --project=coderd
```

Expected output should show:
```yaml
defaultService: .../coderd-backend
hostRules:
- hosts:
  - '*'
  pathMatcher: onboarding-matcher
pathMatchers:
- defaultService: .../coderd-backend
  name: onboarding-matcher
  pathRules:
  - paths:
    - /onboarding
    - /onboarding/*
    service: .../onboarding-backend
```

## Step 7: Deploy Updated Next.js Application

Deploy the updated application with the basePath configuration.

```bash
./scripts/admin/deploy_onboarding_status_web.sh
```

## Step 8: Verify and Test

Wait 5-10 minutes for the load balancer configuration to propagate across Google's network.

### Test Coder Platform (unchanged)
```bash
curl -I https://platform.vectorinstitute.ai/
```
Expected: HTTP 200 with Coder server headers

### Test Onboarding Dashboard
```bash
curl -I https://platform.vectorinstitute.ai/onboarding
```
Expected: HTTP 200 with Next.js headers

### Test Onboarding API
```bash
curl -s https://platform.vectorinstitute.ai/onboarding/api/participants | jq '.summary'
```
Expected: JSON response with participant summary

### Browser Test
Open `https://platform.vectorinstitute.ai/onboarding` in a browser. You should see:
- Dashboard loads without errors
- Participant data appears in the table
- No JSON parsing errors in browser console

## Troubleshooting

### Issue: 404 on Cloud Run Direct URL

**Symptom:** `https://onboarding-status-web-736624225747.us-central1.run.app/` returns 404

**Status:** This is expected behavior! The app is configured with `basePath: '/onboarding'`, so:
- ❌ `https://[cloud-run-url]/` → 404 (no root route)
- ✅ `https://[cloud-run-url]/onboarding` → Works
- ✅ `https://platform.vectorinstitute.ai/onboarding` → Works (intended access)

Users should always access via the load balancer URL, not the direct Cloud Run URL.

### Issue: API Returns HTML Instead of JSON

**Symptom:** Browser console shows `Unexpected token '<', "<!doctype "... is not valid JSON`

**Cause:** The fetch is going to the wrong endpoint (hitting Coder server instead of Cloud Run)

**Solution:** Ensure the fetch uses the absolute path `/onboarding/api/participants` in `app/page.tsx`

### Issue: Changes Not Taking Effect

**Cause:** Browser cache or load balancer propagation delay

**Solution:**
1. Wait 5-10 minutes for load balancer changes to propagate
2. Hard refresh browser (Ctrl+Shift+R or Cmd+Shift+R)
3. Clear browser cache

### Rollback Procedure

If you need to rollback the URL map changes:

```bash
# Remove the path matcher
gcloud compute url-maps remove-path-matcher https-url-map \
  --project=coderd \
  --path-matcher-name=onboarding-matcher

# Or restore from backup
gcloud compute url-maps import https-url-map \
  --project=coderd \
  --source=url-map-backup-YYYYMMDD.yaml \
  --global
```

## Resources Created

This setup creates the following GCP resources:

| Resource Type | Name | Purpose |
|--------------|------|---------|
| Network Endpoint Group | `onboarding-status-neg` | Connects load balancer to Cloud Run service |
| Backend Service | `onboarding-backend` | Backend for onboarding dashboard traffic |
| URL Map Path Rules | `/onboarding`, `/onboarding/*` | Routes specific paths to Cloud Run |

## Maintenance

### Redeploying the Application

To redeploy with code changes:

```bash
# Make your code changes, then deploy
./scripts/admin/deploy_onboarding_status_web.sh
```

The load balancer configuration remains intact and doesn't need to be reconfigured.

### Updating Load Balancer Configuration

If you need to modify the path rules:

```bash
# Export current config
gcloud compute url-maps export https-url-map \
  --project=coderd \
  --destination=url-map-current.yaml

# Edit url-map-current.yaml, then import
gcloud compute url-maps import https-url-map \
  --project=coderd \
  --source=url-map-current.yaml \
  --global
```

### Checking Resource Status

```bash
# List all backend services
gcloud compute backend-services list --project=coderd

# List all NEGs
gcloud compute network-endpoint-groups list --project=coderd

# View URL map configuration
gcloud compute url-maps describe https-url-map --project=coderd
```

## Notes

- **No Downtime:** The load balancer update is non-disruptive. Existing traffic continues to flow during configuration changes.
- **Default Behavior:** All traffic not matching `/onboarding` or `/onboarding/*` continues to route to the Coder server.
- **SSL Certificate:** The existing SSL certificate (`myservice-ssl-cert`) covers `platform.vectorinstitute.ai` and is used for both the Coder server and the onboarding dashboard.
- **Propagation Time:** Load balancer configuration changes take 5-10 minutes to propagate globally.

## Reference

- [Cloud Run Serverless NEGs](https://cloud.google.com/load-balancing/docs/negs/serverless-neg-concepts)
- [URL Map Path Rules](https://cloud.google.com/load-balancing/docs/url-map-concepts)
- [Next.js basePath](https://nextjs.org/docs/app/api-reference/next-config-js/basePath)

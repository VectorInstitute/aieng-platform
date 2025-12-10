# Coder Analytics Dashboard

A Next.js dashboard for visualizing Coder workspace usage analytics with team-level aggregation.

## Features

- **Real-time Analytics**: Displays workspace usage metrics updated every 6 hours
- **Team Aggregation**: Maps GitHub users to teams using Firestore data
- **Activity Tracking**: Classifies workspaces as active, inactive, or stale
- **Multi-tab Interface**:
  - Overview: Platform-wide metrics
  - Teams: Team-level breakdowns
  - Workspaces: Detailed workspace table with filters
  - Templates: Template usage statistics
- **Google OAuth Authentication**: Secure access restricted to @vectorinstitute.ai domain
- **Auto-refresh**: Dashboard automatically refreshes data every 5 minutes

## Architecture

### Data Flow

```
GitHub Actions (every 6h)
  → Coder CLI (coder list -a -o json)
  → GCS Bucket (coder-analytics-snapshots/latest.json)
  → Next.js API (/analytics/api/snapshot)
  → Firestore (team mappings)
  → Dashboard (client-side filtering)
```

### Tech Stack

- **Frontend**: Next.js 14 with App Router, React 18, TypeScript
- **Styling**: Tailwind CSS with Vector Institute brand colors
- **Icons**: Lucide React
- **Auth**: Google OAuth 2.0 with PKCE flow
- **Session**: iron-session (encrypted cookies)
- **Database**: Firestore (for user-to-team mapping)
- **Storage**: Google Cloud Storage (for analytics snapshots)
- **Deployment**: Docker + Google Cloud Run

## Getting Started

### Prerequisites

- Node.js 20+
- Docker (for building)
- Google Cloud Platform account with:
  - Firestore database (`onboarding`)
  - GCS bucket (`coder-analytics-snapshots`)
  - Google OAuth client credentials

### Local Development

1. **Install dependencies**:
   ```bash
   cd services/analytics
   npm install
   ```

2. **Set up environment variables**:
   ```bash
   cp .env.example .env.local
   # Edit .env.local with your credentials
   ```

3. **Run development server**:
   ```bash
   npm run dev
   ```

4. **Open browser**:
   Navigate to `http://localhost:3000/analytics`

## Deployment

Pushes to `main` branch trigger automatic deployment to Cloud Run via GitHub Actions.

**Workflow**: `.github/workflows/deploy-analytics.yml`

## Data Collection

Analytics data is collected automatically via GitHub Actions every 6 hours.

**Workflow**: `.github/workflows/collect-coder-analytics.yml`

See full documentation in README for more details.

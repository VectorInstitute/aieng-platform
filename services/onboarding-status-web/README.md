# Onboarding Status Web Dashboard

A modern, real-time web dashboard built with Next.js to display participant onboarding status for the AI Engineering bootcamp.

## Features

- **Real-time Status Tracking**: Displays live participant onboarding status fetched from Firestore
- **Clean, Polished UI**: Modern, responsive design with dark mode support
- **Summary Statistics**: Shows total participants, onboarded count, completion percentage
- **Auto-refresh**: Dashboard automatically refreshes every 30 seconds
- **Production-Ready**: Deployed on Google Cloud Run with automatic scaling

## Architecture

- **Frontend**: Next.js 14 with React 18 and TypeScript
- **Styling**: Tailwind CSS with custom animations
- **Backend**: Next.js API routes
- **Database**: Google Cloud Firestore (onboarding database)
- **Deployment**: Google Cloud Run with Docker

## Project Structure

```
services/onboarding-status-web/
├── app/
│   ├── api/
│   │   └── participants/
│   │       └── route.ts         # API endpoint to fetch Firestore data
│   ├── globals.css              # Global styles with Tailwind
│   ├── layout.tsx               # Root layout component
│   └── page.tsx                 # Main dashboard page
├── public/                      # Static assets
├── Dockerfile                   # Multi-stage Docker build
├── next.config.js              # Next.js configuration
├── package.json                # Dependencies
├── postcss.config.js           # PostCSS configuration
├── tailwind.config.js          # Tailwind CSS configuration
└── tsconfig.json               # TypeScript configuration
```

## Local Development

### Prerequisites

- Node.js 20+
- npm or yarn
- Google Cloud credentials with Firestore access

### Setup

1. Install dependencies:
   ```bash
   npm install
   ```

2. Set environment variables:
   ```bash
   export GCP_PROJECT_ID=coderd
   export FIRESTORE_DATABASE_ID=onboarding
   ```

3. Run the development server:
   ```bash
   npm run dev
   ```

4. Open [http://localhost:3000](http://localhost:3000) in your browser

## Deployment

### Deploy to Cloud Run

Use the provided deployment script:

```bash
cd /path/to/aieng-platform
./scripts/admin/deploy_onboarding_status_web.sh
```

### Deployment Options

```bash
# Deploy with default settings (public dashboard)
./scripts/admin/deploy_onboarding_status_web.sh

# Deploy with custom project
./scripts/admin/deploy_onboarding_status_web.sh --project YOUR_PROJECT_ID

# Deploy with authentication required
./scripts/admin/deploy_onboarding_status_web.sh --no-allow-unauthenticated

# Dry run (show commands without executing)
./scripts/admin/deploy_onboarding_status_web.sh --dry-run
```

### Manual Deployment

1. Build the Docker image:
   ```bash
   docker buildx build --platform linux/amd64 \
     -t gcr.io/coderd/onboarding-status-web:latest \
     services/onboarding-status-web
   ```

2. Push to Google Container Registry:
   ```bash
   docker push gcr.io/coderd/onboarding-status-web:latest
   ```

3. Deploy to Cloud Run:
   ```bash
   gcloud run deploy onboarding-status-web \
     --image gcr.io/coderd/onboarding-status-web:latest \
     --platform managed \
     --region us-central1 \
     --project coderd \
     --allow-unauthenticated \
     --set-env-vars GCP_PROJECT_ID=coderd,FIRESTORE_DATABASE_ID=onboarding
   ```

## Environment Variables

- `GCP_PROJECT_ID`: Google Cloud Project ID (default: `coderd`)
- `FIRESTORE_DATABASE_ID`: Firestore database ID (default: `onboarding`)
- `PORT`: Port to run the server on (default: `8080`)

## API Endpoints

### GET /api/participants

Returns participant onboarding status and summary statistics.

**Response:**
```json
{
  "participants": [
    {
      "github_handle": "user123",
      "team_name": "team-alpha",
      "onboarded": true,
      "onboarded_at": "2025-11-03T10:30:00Z"
    }
  ],
  "summary": {
    "total": 50,
    "onboarded": 35,
    "notOnboarded": 15,
    "percentage": 70.0
  }
}
```

## Dashboard Features

### Summary Cards
- **Total Participants**: Shows total number of participants
- **Onboarded**: Count of successfully onboarded participants (green)
- **Not Onboarded**: Count of pending participants (red)
- **Completion Rate**: Percentage of completed onboarding (blue)

### Progress Bar
- Visual representation of overall onboarding progress
- Animated gradient fill

### Participants Table
- Sortable list of all participants
- Displays GitHub handle, team name, and status
- Color-coded status badges (green for onboarded, red for not onboarded)
- Hover effects for better UX

### Auto-refresh
- Dashboard automatically fetches fresh data every 30 seconds
- Shows last updated timestamp

## Security

- Uses Google Cloud service account authentication for Firestore access
- Runs as non-root user in Docker container
- Follows Cloud Run security best practices
- CORS configured for API routes

## Performance

- **Optimized Build**: Multi-stage Docker build for minimal image size
- **Static Generation**: Pre-rendered pages where possible
- **Code Splitting**: Automatic code splitting by Next.js
- **Caching**: Intelligent caching strategies

## Monitoring

The service URL is saved to `.onboarding-status-url` in the project root after deployment.

View logs:
```bash
gcloud run services logs read onboarding-status-web \
  --project coderd \
  --region us-central1
```

## Troubleshooting

### Build Failures

If the Docker build fails:
1. Ensure `package-lock.json` exists: `npm install`
2. Check that the `public` directory exists
3. Verify Node.js version compatibility

### Firestore Connection Issues

If the dashboard can't fetch data:
1. Verify service account has Firestore read permissions
2. Check environment variables are set correctly
3. Ensure Firestore database ID is correct
4. Review Cloud Run logs for detailed errors

### Deployment Issues

If deployment fails:
1. Enable required APIs: Cloud Run, Cloud Build, Artifact Registry, Firestore
2. Check GCP project permissions
3. Verify billing is enabled on the project
4. Use `--dry-run` flag to preview commands

## Contributing

When making changes:
1. Test locally with `npm run dev`
2. Build Docker image to verify: `docker buildx build --platform linux/amd64 .`
3. Deploy to a test environment first
4. Update this README if adding new features

## License

See LICENSE.md in the project root.

## Support

For issues or questions, contact the bootcamp admin team.

---

**Live Dashboard**: https://onboarding-status-web-736624225747.us-central1.run.app

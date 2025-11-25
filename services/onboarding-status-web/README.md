# Onboarding Status Web Dashboard

A modern, real-time web dashboard built with Next.js to display participant onboarding status for the AI Engineering bootcamp.

## Features

- **GitHub OAuth Authentication**: Secure authentication with organization membership verification
- **Organization Access Control**: Only members of AI-Engineering-Platform organization can access
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
│   │   ├── auth/
│   │   │   └── [...nextauth]/
│   │   │       └── route.ts     # NextAuth.js API route handler
│   │   ├── participants/
│   │   │   └── route.ts         # API endpoint to fetch Firestore data
│   │   └── github-status/
│   │       └── route.ts         # API endpoint to check GitHub org status
│   ├── auth/
│   │   ├── signin/
│   │   │   └── page.tsx         # Custom sign-in page
│   │   └── error/
│   │       └── page.tsx         # Authentication error page
│   ├── globals.css              # Global styles with Tailwind
│   ├── layout.tsx               # Root layout with auth header
│   └── page.tsx                 # Main dashboard page
├── components/
│   ├── session-provider.tsx    # NextAuth session provider wrapper
│   └── auth-button.tsx          # User profile and sign out button
├── lib/
│   └── auth.ts                  # NextAuth.js configuration
├── types/
│   └── next-auth.d.ts          # TypeScript definitions for NextAuth
├── public/                      # Static assets
├── middleware.ts               # Route protection middleware
├── Dockerfile                   # Multi-stage Docker build
├── next.config.js              # Next.js configuration
├── package.json                # Dependencies
├── .env.example                # Environment variables template
├── postcss.config.js           # PostCSS configuration
├── tailwind.config.js          # Tailwind CSS configuration
└── tsconfig.json               # TypeScript configuration
```

## Local Development

### Prerequisites

- Node.js 20+
- npm or yarn
- Google Cloud credentials with Firestore access
- GitHub OAuth App credentials
- GitHub Personal Access Token with `read:org` and `read:user` scopes

### Setup

1. **Create a GitHub OAuth Application**:
   - Go to https://github.com/organizations/AI-Engineering-Platform/settings/applications
   - Click "New OAuth App" or "Register a new application"
   - Set Application name: `Onboarding Status Dashboard (Dev)`
   - Set Homepage URL: `http://localhost:3000`
   - Set Authorization callback URL: `http://localhost:3000/onboarding/api/auth/callback/github`
   - Copy the Client ID and generate a Client Secret

2. **Create a GitHub Personal Access Token**:
   - Go to https://github.com/settings/tokens
   - Click "Generate new token" (classic)
   - Select scopes: `read:org`, `read:user`
   - Copy the generated token

3. **Install dependencies**:
   ```bash
   npm install
   ```

4. **Configure environment variables**:
   ```bash
   # Copy the example file
   cp .env.example .env.local

   # Edit .env.local with your credentials
   # Set the following variables:
   # - GITHUB_CLIENT_ID
   # - GITHUB_CLIENT_SECRET
   # - GITHUB_TOKEN
   # - NEXTAUTH_SECRET (generate with: openssl rand -base64 32)
   # - NEXTAUTH_URL=http://localhost:3000/onboarding
   ```

5. **Run the development server**:
   ```bash
   npm run dev
   ```

6. **Access the dashboard**:
   - Open http://localhost:3000/onboarding in your browser
   - Sign in with your GitHub account
   - You must be a member of the AI-Engineering-Platform organization to access

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

### Required Variables

- `GITHUB_CLIENT_ID`: GitHub OAuth App Client ID
- `GITHUB_CLIENT_SECRET`: GitHub OAuth App Client Secret
- `GITHUB_TOKEN`: GitHub Personal Access Token with `read:org` and `read:user` scopes
- `NEXTAUTH_SECRET`: Secret key for NextAuth.js (generate with `openssl rand -base64 32`)
- `NEXTAUTH_URL`: Full URL of the application (e.g., `https://yourdomain.com/onboarding`)

### Optional Variables

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

- **GitHub OAuth Authentication**: All routes protected by NextAuth.js middleware
- **Organization Membership Verification**: Only AI-Engineering-Platform members can access
- **Session Management**: Secure JWT-based sessions with HTTP-only cookies
- **API Protection**: All API routes require valid authentication
- **Google Cloud IAM**: Service account authentication for Firestore access
- **Container Security**: Runs as non-root user in Docker container
- **Cloud Run Best Practices**: Follows Google Cloud Run security guidelines
- **CORS Configuration**: Properly configured for API routes

### Authentication Flow

1. User visits the dashboard
2. Middleware redirects unauthenticated users to `/auth/signin`
3. User clicks "Sign in with GitHub"
4. GitHub OAuth redirects to authorization page
5. After approval, GitHub redirects back with authorization code
6. NextAuth exchanges code for access token
7. Server verifies user is a member of AI-Engineering-Platform organization
8. If verified, user session is created and stored in JWT
9. User is redirected to the dashboard
10. All subsequent requests include the session token for authentication

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

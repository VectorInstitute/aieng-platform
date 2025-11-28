# Onboarding Status Web Authentication

## Overview

The Onboarding Status Web dashboard uses Google OAuth 2.0 with server-side sessions for authentication. Only @vectorinstitute.ai email addresses can access the dashboard.

## Architecture

- **Library**: `@vector-institute/aieng-auth-core`
- **Session Management**: `iron-session` with encrypted HTTP-only cookies
- **Security**: PKCE flow, domain restriction, encrypted sessions
- **Path**: All routes under `/onboarding` base path

## Authentication Flow

1. User visits `/onboarding` → redirected to `/onboarding/login` if not authenticated
2. Click "Sign in with Google" → `/onboarding/api/auth/login`
3. Google OAuth flow with PKCE
4. Callback to `/onboarding/api/auth/callback`
5. Session created, user redirected to dashboard

## Files

### Configuration
- `lib/auth-config.ts` - OAuth config
- `lib/session.ts` - Session management

### API Routes
- `app/api/auth/login/route.ts` - Initiate OAuth
- `app/api/auth/callback/route.ts` - Handle callback
- `app/api/auth/logout/route.ts` - Destroy session
- `app/api/auth/session/route.ts` - Get session info

### Pages
- `app/page.tsx` - Protected dashboard
- `app/login/page.tsx` - Login page
- `app/dashboard-content.tsx` - Dashboard UI

## Environment Variables

```bash
# OAuth
NEXT_PUBLIC_GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-your-secret
SESSION_SECRET=generate-with-openssl-rand-base64-32

# URLs
NEXT_PUBLIC_APP_URL=http://localhost:3000
REDIRECT_URI=http://localhost:3000/onboarding/api/auth/callback

# Domain restriction
ALLOWED_DOMAINS=vectorinstitute.ai
```

## Local Development

1. Copy OAuth credentials from `aieng-template-auth/apps/demo-nextjs/.env`
2. Update redirect URI in `.env`: `http://localhost:3000/onboarding/api/auth/callback`
3. Run `npm run dev`
4. Visit `http://localhost:3000/onboarding`
5. Sign in with @vectorinstitute.ai account

## Production Deployment

### Required GitHub Secrets
- `GOOGLE_CLIENT_ID` - Shared Vector OAuth client ID
- `GOOGLE_CLIENT_SECRET` - OAuth client secret
- `SESSION_SECRET` - Generated with `openssl rand -base64 32`
- `APP_URL` - Production URL (e.g., `https://your-service.run.app`)
- `REDIRECT_URI` - Production callback URL (e.g., `https://your-service.run.app/onboarding/api/auth/callback`)

### Setup Steps
1. Get shared OAuth client ID from admin
2. Ask admin to add production redirect URI to Google OAuth client
3. Set GitHub secrets in repository settings
4. Deploy via GitHub Actions workflow

## Troubleshooting

**"Invalid redirect_uri"**
- Verify redirect URI registered in Google Cloud Console
- Check `REDIRECT_URI` matches registered value

**"Unauthorized domain"**
- User must have @vectorinstitute.ai email
- Check `ALLOWED_DOMAINS` environment variable

**Session issues**
- Verify `SESSION_SECRET` is at least 32 characters
- Clear browser cookies

## Dependencies

```json
{
  "@vector-institute/aieng-auth-core": "^0.1.x",
  "iron-session": "^8.0.1"
}
```

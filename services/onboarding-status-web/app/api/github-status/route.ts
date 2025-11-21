import { NextRequest, NextResponse } from 'next/server';
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

const ORG_NAME = 'AI-Engineering-Platform';

// Cache for GitHub status to avoid rate limits
// Cache expires after 5 minutes
const statusCache = new Map<string, { status: string; timestamp: number }>();
const CACHE_TTL = 5 * 60 * 1000; // 5 minutes

export type GitHubStatus = 'member' | 'pending' | 'not_invited';

interface GitHubStatusResponse {
  github_handle: string;
  status: GitHubStatus;
}

/**
 * Check if gh CLI is available and authenticated
 */
async function checkGhCli(): Promise<{ available: boolean; error?: string }> {
  try {
    await execAsync('gh --version');
    await execAsync('gh auth status');
    return { available: true };
  } catch {
    return {
      available: false,
      error: 'GitHub CLI not available or not authenticated'
    };
  }
}

/**
 * Get pending invitations from GitHub org
 * Returns usernames in lowercase for case-insensitive comparison
 */
async function getPendingInvitations(): Promise<Set<string>> {
  try {
    const { stdout } = await execAsync(
      `gh api "orgs/${ORG_NAME}/invitations" --jq '.[].login // empty'`
    );
    const logins = stdout
      .trim()
      .split('\n')
      .filter(login => login.length > 0)
      .map(login => login.toLowerCase());
    return new Set(logins);
  } catch (error) {
    console.error('Error fetching pending invitations:', error);
    return new Set();
  }
}

/**
 * Check if a user is a member of the organization
 */
async function isOrgMember(username: string): Promise<boolean> {
  try {
    await execAsync(`gh api "orgs/${ORG_NAME}/members/${username}" 2>/dev/null`);
    return true;
  } catch {
    return false;
  }
}

/**
 * Determine GitHub status for a single user
 */
async function getGitHubStatus(
  username: string,
  pendingInvitations: Set<string>
): Promise<GitHubStatus> {
  // Normalize username for cache key (case-insensitive)
  const normalizedUsername = username.toLowerCase();

  // Check cache first
  const cached = statusCache.get(normalizedUsername);
  if (cached && Date.now() - cached.timestamp < CACHE_TTL) {
    return cached.status as GitHubStatus;
  }

  let status: GitHubStatus;

  // Check if user is a member
  const isMember = await isOrgMember(username);
  if (isMember) {
    status = 'member';
  } else if (pendingInvitations.has(normalizedUsername)) {
    status = 'pending';
  } else {
    status = 'not_invited';
  }

  // Update cache with normalized username
  statusCache.set(normalizedUsername, { status, timestamp: Date.now() });

  return status;
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { github_handles } = body;

    if (!Array.isArray(github_handles)) {
      return NextResponse.json(
        { error: 'github_handles must be an array' },
        { status: 400 }
      );
    }

    // Check if gh CLI is available
    const ghCheck = await checkGhCli();
    if (!ghCheck.available) {
      console.warn('GitHub CLI not available:', ghCheck.error);
      // Return all as not_invited if gh CLI is not available
      const statuses: GitHubStatusResponse[] = github_handles.map(handle => ({
        github_handle: handle,
        status: 'not_invited' as GitHubStatus
      }));
      return NextResponse.json({ statuses, warning: ghCheck.error });
    }

    // Fetch pending invitations once for efficiency
    const pendingInvitations = await getPendingInvitations();

    // Check status for each user
    const statusPromises = github_handles.map(async (handle) => {
      const status = await getGitHubStatus(handle, pendingInvitations);
      return {
        github_handle: handle,
        status
      };
    });

    const statuses = await Promise.all(statusPromises);

    return NextResponse.json({ statuses });
  } catch (error) {
    console.error('Error checking GitHub status:', error);
    return NextResponse.json(
      {
        error: 'Failed to check GitHub status',
        details: error instanceof Error ? error.message : 'Unknown error'
      },
      { status: 500 }
    );
  }
}

// Force dynamic behavior
export const dynamic = 'force-dynamic';
export const revalidate = 0;

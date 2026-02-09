import { Firestore } from '@google-cloud/firestore';
import { NextRequest, NextResponse } from 'next/server';

// Initialize Firestore client
const getFirestoreClient = () => {
  const projectId = process.env.GCP_PROJECT_ID || 'coderd';
  const databaseId = process.env.FIRESTORE_DATABASE_ID || 'onboarding';

  return new Firestore({
    projectId,
    databaseId,
  });
};

interface ParticipantData {
  github_handle: string;
  team_name: string;
  onboarded: boolean;
  onboarded_at?: string | null;
  first_name?: string;
  last_name?: string;
  bootcamp_name?: string;
}

export async function GET(request: NextRequest) {
  try {
    // Get role filter from query params, default to 'participants'
    const searchParams = request.nextUrl.searchParams;
    const role = searchParams.get('role') || 'participants';

    const db = getFirestoreClient();
    const participantsRef = db.collection('participants');
    const snapshot = await participantsRef.get();

    const participants: ParticipantData[] = [];

    snapshot.forEach((doc) => {
      const data = doc.data();
      const teamName = data.team_name || 'N/A';

      // Filter based on role parameter
      if (role === 'facilitators') {
        // Show only facilitators
        if (teamName === 'facilitators') {
          participants.push({
            github_handle: doc.id,
            team_name: teamName,
            onboarded: data.onboarded || false,
            onboarded_at: data.onboarded_at,
            first_name: data.first_name || '',
            last_name: data.last_name || '',
            bootcamp_name: data.bootcamp_name || '',
          });
        }
      } else {
        // Default: show only participants (exclude facilitators)
        if (teamName !== 'facilitators') {
          participants.push({
            github_handle: doc.id,
            team_name: teamName,
            onboarded: data.onboarded || false,
            onboarded_at: data.onboarded_at,
            first_name: data.first_name || '',
            last_name: data.last_name || '',
            bootcamp_name: data.bootcamp_name || '',
          });
        }
      }
    });

    // Sort by team name, then by github handle
    participants.sort((a, b) => {
      if (a.team_name !== b.team_name) {
        return a.team_name.localeCompare(b.team_name);
      }
      return a.github_handle.localeCompare(b.github_handle);
    });

    // Calculate summary
    const total = participants.length;
    const onboarded = participants.filter((p) => p.onboarded).length;
    const notOnboarded = total - onboarded;
    const percentage = total > 0 ? (onboarded / total) * 100 : 0;

    return NextResponse.json({
      participants,
      summary: {
        total,
        onboarded,
        notOnboarded,
        percentage: parseFloat(percentage.toFixed(1)),
      },
    });
  } catch (error) {
    console.error('Error fetching participants:', error);
    return NextResponse.json(
      {
        error: 'Failed to fetch participants',
        details: error instanceof Error ? error.message : 'Unknown error'
      },
      { status: 500 }
    );
  }
}

// Force dynamic behavior to always fetch fresh data
export const dynamic = 'force-dynamic';
export const revalidate = 0;

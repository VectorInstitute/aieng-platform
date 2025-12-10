import { NextResponse } from 'next/server';
import { getAllTeams } from '@/lib/firestore';
import type { TeamListResponse } from '@/lib/types';

// Force dynamic route
export const dynamic = 'force-dynamic';

// Cache for 5 minutes
export const revalidate = 300;

/**
 * GET /api/teams
 * Fetch list of all teams with member counts
 */
export async function GET() {
  try {
    console.log('Fetching teams from Firestore...');

    const teams = await getAllTeams();

    const response: TeamListResponse = {
      teams: teams.map((team) => ({
        team_name: team.team_name,
        member_count: team.participants?.length || 0,
      })),
    };

    console.log(`Loaded ${response.teams.length} teams`);

    return NextResponse.json(response, {
      status: 200,
      headers: {
        'Cache-Control': 'public, s-maxage=300, stale-while-revalidate=60',
      },
    });
  } catch (error) {
    console.error('Error fetching teams:', error);

    return NextResponse.json(
      {
        error: 'Failed to fetch teams',
        message: error instanceof Error ? error.message : 'Unknown error',
      },
      {
        status: 500,
      }
    );
  }
}

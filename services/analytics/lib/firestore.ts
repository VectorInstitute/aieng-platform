import { Firestore } from '@google-cloud/firestore';
import type { ParticipantData, TeamData } from './types';

const projectId = process.env.GCP_PROJECT_ID || 'coderd';
const databaseId = process.env.FIRESTORE_DATABASE_ID || 'onboarding';

// Initialize Firestore client
const db = new Firestore({
  projectId,
  databaseId,
});

/**
 * Get team mappings for all participants
 * Maps GitHub handle (lowercase) to participant data including team_name
 * @returns Map of github_handle -> ParticipantData
 */
export async function getTeamMappings(): Promise<Map<string, ParticipantData>> {
  try {
    const snapshot = await db.collection('participants').get();
    const mappings = new Map<string, ParticipantData>();

    snapshot.forEach((doc) => {
      const data = doc.data();
      const participantData: ParticipantData = {
        github_handle: doc.id,
        team_name: data.team_name || 'Unassigned',
        first_name: data.first_name,
        last_name: data.last_name,
        email: data.email,
        onboarded: data.onboarded,
        onboarded_at: data.onboarded_at,
      };

      // Store with lowercase key for case-insensitive matching
      mappings.set(doc.id.toLowerCase(), participantData);
    });

    console.log(`Loaded ${mappings.size} participant mappings from Firestore`);
    return mappings;
  } catch (error) {
    console.error('Error fetching team mappings from Firestore:', error);
    throw new Error(`Failed to fetch team mappings: ${error instanceof Error ? error.message : 'Unknown error'}`);
  }
}

/**
 * Get all teams with their participant lists
 * @returns Array of team data
 */
export async function getAllTeams(): Promise<TeamData[]> {
  try {
    const snapshot = await db.collection('teams').get();
    const teams: TeamData[] = [];

    snapshot.forEach((doc) => {
      const data = doc.data();
      teams.push({
        team_name: doc.id,
        participants: data.participants || [],
        openai_api_key: data.openai_api_key,
        openai_api_key_name: data.openai_api_key_name,
        langfuse_secret_key: data.langfuse_secret_key,
        langfuse_public_key: data.langfuse_public_key,
        created_at: data.created_at,
        updated_at: data.updated_at,
      });
    });

    console.log(`Loaded ${teams.length} teams from Firestore`);
    return teams;
  } catch (error) {
    console.error('Error fetching teams from Firestore:', error);
    throw new Error(`Failed to fetch teams: ${error instanceof Error ? error.message : 'Unknown error'}`);
  }
}

/**
 * Get a single participant by GitHub handle
 * @param githubHandle GitHub username (case-insensitive)
 * @returns ParticipantData or null if not found
 */
export async function getParticipant(githubHandle: string): Promise<ParticipantData | null> {
  try {
    const normalizedHandle = githubHandle.toLowerCase();
    const doc = await db.collection('participants').doc(normalizedHandle).get();

    if (!doc.exists) {
      return null;
    }

    const data = doc.data()!;
    return {
      github_handle: doc.id,
      team_name: data.team_name || 'Unassigned',
      first_name: data.first_name,
      last_name: data.last_name,
      email: data.email,
      onboarded: data.onboarded,
      onboarded_at: data.onboarded_at,
    };
  } catch (error) {
    console.error(`Error fetching participant ${githubHandle}:`, error);
    return null;
  }
}

/**
 * Get a single team by name
 * @param teamName Team name
 * @returns TeamData or null if not found
 */
export async function getTeam(teamName: string): Promise<TeamData | null> {
  try {
    const doc = await db.collection('teams').doc(teamName).get();

    if (!doc.exists) {
      return null;
    }

    const data = doc.data()!;
    return {
      team_name: doc.id,
      participants: data.participants || [],
      openai_api_key: data.openai_api_key,
      openai_api_key_name: data.openai_api_key_name,
      langfuse_secret_key: data.langfuse_secret_key,
      langfuse_public_key: data.langfuse_public_key,
      created_at: data.created_at,
      updated_at: data.updated_at,
    };
  } catch (error) {
    console.error(`Error fetching team ${teamName}:`, error);
    return null;
  }
}

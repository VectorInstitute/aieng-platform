import { Firestore } from '@google-cloud/firestore';
import type { TeamData } from './types';

const projectId = process.env.GCP_PROJECT_ID || 'coderd';
const databaseId = process.env.FIRESTORE_DATABASE_ID || 'onboarding';

// Initialize Firestore client
const db = new Firestore({
  projectId,
  databaseId,
});

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

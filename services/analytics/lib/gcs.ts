import { Storage } from '@google-cloud/storage';
import type { CoderSnapshot } from './types';

const projectId = process.env.GCP_PROJECT_ID || 'coderd';
const bucketName = process.env.GCS_BUCKET_NAME || 'coder-analytics-snapshots';

// Initialize GCS client
const storage = new Storage({
  projectId,
});

const bucket = storage.bucket(bucketName);

/**
 * Fetch the latest Coder analytics snapshot from GCS
 * @returns The latest snapshot with workspace and template data
 */
export async function getLatestSnapshot(): Promise<CoderSnapshot> {
  try {
    const file = bucket.file('latest.json');

    // Check if file exists
    const [exists] = await file.exists();
    if (!exists) {
      console.error('latest.json does not exist in GCS bucket');
      // Return empty snapshot if file doesn't exist
      return {
        timestamp: new Date().toISOString(),
        workspaces: [],
        templates: [],
      };
    }

    // Download and parse the file
    const [contents] = await file.download();
    const snapshot = JSON.parse(contents.toString()) as CoderSnapshot;

    return snapshot;
  } catch (error) {
    console.error('Error fetching latest snapshot from GCS:', error);
    throw new Error(`Failed to fetch latest snapshot: ${error instanceof Error ? error.message : 'Unknown error'}`);
  }
}

/**
 * Fetch historical snapshots from GCS for the last N days
 * @param days Number of days of history to fetch (default: 30)
 * @returns Array of snapshots sorted by timestamp (newest first)
 */
export async function getSnapshotHistory(days: number = 30): Promise<CoderSnapshot[]> {
  try {
    const cutoffDate = new Date();
    cutoffDate.setDate(cutoffDate.getDate() - days);

    // List all files in the snapshots/ directory
    const [files] = await bucket.getFiles({ prefix: 'snapshots/' });

    // Filter files by date and fetch their contents
    const snapshots: CoderSnapshot[] = [];

    for (const file of files) {
      // Extract timestamp from filename (format: YYYY-MM-DD-HH-mm.json)
      const filename = file.name.split('/').pop();
      if (!filename || !filename.endsWith('.json')) {
        continue;
      }

      // Parse date from filename
      const match = filename.match(/^(\d{4}-\d{2}-\d{2})/);
      if (!match) {
        continue;
      }

      const fileDate = new Date(match[1]);
      if (fileDate < cutoffDate) {
        continue;
      }

      // Download and parse the file
      try {
        const [contents] = await file.download();
        const snapshot = JSON.parse(contents.toString()) as CoderSnapshot;
        snapshots.push(snapshot);
      } catch (error) {
        console.warn(`Failed to parse snapshot file ${file.name}:`, error);
      }
    }

    // Sort by timestamp (newest first)
    snapshots.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());

    return snapshots;
  } catch (error) {
    console.error('Error fetching snapshot history from GCS:', error);
    throw new Error(`Failed to fetch snapshot history: ${error instanceof Error ? error.message : 'Unknown error'}`);
  }
}

/**
 * Check if the GCS bucket exists and is accessible
 * @returns true if bucket exists and is accessible
 */
export async function checkBucketExists(): Promise<boolean> {
  try {
    const [exists] = await bucket.exists();
    return exists;
  } catch (error) {
    console.error('Error checking bucket existence:', error);
    return false;
  }
}

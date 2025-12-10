import { NextResponse } from 'next/server';
import { getLatestSnapshot } from '@/lib/gcs';
import { getTeamMappings } from '@/lib/firestore';
import {
  enrichWorkspaceData,
  aggregateByTeam,
  calculatePlatformMetrics,
  calculateTemplateMetrics,
  calculateDailyEngagement,
} from '@/lib/metrics';
import type { AnalyticsSnapshot } from '@/lib/types';

// Force dynamic route
export const dynamic = 'force-dynamic';

// Cache for 5 minutes (data updates every 6 hours, so this is fine)
export const revalidate = 300;

/**
 * GET /api/snapshot
 * Fetch the latest Coder analytics snapshot with enriched metrics
 */
export async function GET() {
  try {
    console.log('Fetching latest Coder analytics snapshot...');

    // Fetch data in parallel
    const [snapshot, teamMappings] = await Promise.all([
      getLatestSnapshot(),
      getTeamMappings(),
    ]);

    console.log(`Snapshot contains ${snapshot.workspaces.length} workspaces and ${snapshot.templates.length} templates`);
    console.log(`Loaded ${teamMappings.size} team mappings`);

    // Enrich workspace data with team information
    const workspaceMetrics = enrichWorkspaceData(snapshot.workspaces, teamMappings);
    console.log(`Enriched ${workspaceMetrics.length} workspace metrics`);

    // Calculate aggregated metrics
    const teamMetrics = aggregateByTeam(workspaceMetrics);
    const platformMetrics = calculatePlatformMetrics(workspaceMetrics);
    const templateMetrics = calculateTemplateMetrics(workspaceMetrics, snapshot.templates);
    const dailyEngagement = calculateDailyEngagement(workspaceMetrics);

    console.log(`Calculated metrics for ${teamMetrics.length} teams and ${dailyEngagement.length} days of engagement`);

    // Build response
    const response: AnalyticsSnapshot = {
      timestamp: snapshot.timestamp,
      platform_metrics: platformMetrics,
      team_metrics: teamMetrics,
      workspace_metrics: workspaceMetrics,
      template_metrics: templateMetrics,
      daily_engagement: dailyEngagement,
    };

    return NextResponse.json(response, {
      status: 200,
      headers: {
        'Cache-Control': 'public, s-maxage=300, stale-while-revalidate=60',
      },
    });
  } catch (error) {
    console.error('Error fetching analytics snapshot:', error);

    return NextResponse.json(
      {
        error: 'Failed to fetch analytics data',
        message: error instanceof Error ? error.message : 'Unknown error',
      },
      {
        status: 500,
      }
    );
  }
}

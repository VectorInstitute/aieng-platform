import { NextResponse } from 'next/server';
import { getLatestSnapshot } from '@/lib/gcs';
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

    // Fetch snapshot (team data is pre-enriched at collection time)
    const snapshot = await getLatestSnapshot();

    console.log(`Snapshot contains ${snapshot.workspaces.length} workspaces and ${snapshot.templates.length} templates`);

    // Enrich workspace data with calculated metrics (team data already in snapshot)
    const workspaceMetrics = enrichWorkspaceData(snapshot.workspaces);
    console.log(`Enriched ${workspaceMetrics.length} workspace metrics`);

    // Get accumulated usage from snapshot (if available)
    const accumulatedUsage = snapshot.accumulated_usage;

    // Calculate aggregated metrics with accumulated usage
    const teamMetrics = aggregateByTeam(workspaceMetrics, accumulatedUsage);
    const platformMetrics = calculatePlatformMetrics(workspaceMetrics);
    const templateMetrics = calculateTemplateMetrics(workspaceMetrics, snapshot.templates, accumulatedUsage);
    const dailyEngagement = calculateDailyEngagement(snapshot.workspaces);

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

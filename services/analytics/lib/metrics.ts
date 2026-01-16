import type {
  CoderWorkspace,
  CoderTemplate,
  WorkspaceMetrics,
  TeamMetrics,
  PlatformMetrics,
  TemplateMetrics,
  ActivityStatus,
  WorkspaceStatus,
  HealthStatus,
  DailyEngagement,
} from './types';

// ===== Activity Thresholds =====

const ACTIVITY_THRESHOLDS = {
  ACTIVE_DAYS: 7,      // 7 days - workspace used recently
  INACTIVE_DAYS: 30,   // 30 days - workspace not used lately
  STALE_DAYS: 30,      // 30+ days - workspace abandoned
} as const;

// ===== Utility Functions =====

/**
 * Calculate days between two dates
 */
function daysBetween(date1: Date, date2: Date): number {
  const diffTime = Math.abs(date2.getTime() - date1.getTime());
  return Math.floor(diffTime / (1000 * 60 * 60 * 24));
}

/**
 * Calculate hours between two dates
 */
function hoursBetween(date1: Date, date2: Date): number {
  const diffTime = Math.abs(date2.getTime() - date1.getTime());
  return Math.floor(diffTime / (1000 * 60 * 60));
}

/**
 * Get workspace usage hours from pre-calculated field or fallback to latest build
 * The collection script calculates total usage across all builds
 */
function getWorkspaceUsageHours(workspace: CoderWorkspace): number {
  // Use pre-calculated total_usage_hours from collection script if available
  if (workspace.total_usage_hours !== undefined && workspace.total_usage_hours !== null) {
    return workspace.total_usage_hours;
  }

  // Fallback: calculate from latest build only (less accurate)
  try {
    const resources = workspace.latest_build?.resources || [];
    let earliestConnection: Date | null = null;
    let latestConnection: Date | null = null;

    for (const resource of resources) {
      const agents = resource.agents || [];
      for (const agent of agents) {
        if (agent.first_connected_at) {
          const firstConnected = new Date(agent.first_connected_at);
          if (!earliestConnection || firstConnected < earliestConnection) {
            earliestConnection = firstConnected;
          }
        }
        if (agent.last_connected_at) {
          const lastConnected = new Date(agent.last_connected_at);
          if (!latestConnection || lastConnected > latestConnection) {
            latestConnection = lastConnected;
          }
        }
      }
    }

    if (earliestConnection && latestConnection) {
      return hoursBetween(earliestConnection, latestConnection);
    }

    return 0;
  } catch (error) {
    console.warn(`Error calculating usage hours for workspace ${workspace.id}:`, error);
    return 0;
  }
}

/**
 * Get workspace active hours from pre-calculated field
 * The collection script fetches this from Coder Insights API
 */
function getWorkspaceActiveHours(workspace: CoderWorkspace): number {
  // Use pre-calculated active_hours from collection script
  if (workspace.active_hours !== undefined && workspace.active_hours !== null) {
    return workspace.active_hours;
  }

  return 0;
}

/**
 * Calculate total active hours for a group of workspaces, ensuring logical consistency
 *
 * Active hours from Insights API are per-user across all time (including deleted workspaces).
 * To ensure active hours ≤ total hours, we cap each user's active hours at their total workspace hours.
 *
 * @param workspaces - Array of workspace metrics to aggregate
 * @returns Total active hours across all unique users, capped at their workspace totals
 */
function calculateTotalActiveHours(workspaces: WorkspaceMetrics[]): number {
  // Track active hours and total hours per unique user
  const userActiveHours = new Map<string, number>();
  const userTotalHours = new Map<string, number>();

  workspaces.forEach((workspace) => {
    const user = workspace.owner_github_handle;

    // Active hours are per-user (same across all their workspaces), so take max
    const existingActive = userActiveHours.get(user) || 0;
    userActiveHours.set(user, Math.max(existingActive, workspace.active_hours));

    // Total hours are per-workspace, so sum them up
    const existingTotal = userTotalHours.get(user) || 0;
    userTotalHours.set(user, existingTotal + workspace.workspace_hours);
  });

  // Cap each user's active hours at their total hours (handles deleted workspaces)
  let totalActive = 0;
  userActiveHours.forEach((activeHours, user) => {
    const totalHours = userTotalHours.get(user) || 0;
    totalActive += Math.min(activeHours, totalHours);
  });

  return totalActive;
}

/**
 * Classify activity status based on days since last active
 */
function classifyActivityStatus(daysSinceActive: number): ActivityStatus {
  if (daysSinceActive <= ACTIVITY_THRESHOLDS.ACTIVE_DAYS) {
    return 'active';
  } else if (daysSinceActive <= ACTIVITY_THRESHOLDS.INACTIVE_DAYS) {
    return 'inactive';
  } else {
    return 'stale';
  }
}

/**
 * Extract the most recent last_connected_at timestamp from workspace agents
 */
export function getLastActiveTimestamp(workspace: CoderWorkspace): string {
  let mostRecent = workspace.created_at;

  try {
    const resources = workspace.latest_build?.resources || [];
    for (const resource of resources) {
      const agents = resource.agents || [];
      for (const agent of agents) {
        if (agent.last_connected_at && agent.last_connected_at > mostRecent) {
          mostRecent = agent.last_connected_at;
        }
      }
    }
  } catch (error) {
    console.warn(`Error extracting last active timestamp for workspace ${workspace.id}:`, error);
  }

  return mostRecent;
}

/**
 * Determine current workspace status from build data
 */
export function getCurrentStatus(workspace: CoderWorkspace): WorkspaceStatus {
  try {
    const latestBuild = workspace.latest_build;
    if (!latestBuild) {
      return 'unknown';
    }

    const jobStatus = latestBuild.job?.status;
    const transition = latestBuild.transition;

    // Check if build failed
    if (jobStatus === 'failed' || jobStatus === 'canceled') {
      return 'error';
    }

    // Check agent status if available
    const resources = latestBuild.resources || [];
    for (const resource of resources) {
      const agents = resource.agents || [];
      for (const agent of agents) {
        if (agent.status === 'connected' && agent.lifecycle_state === 'ready') {
          return 'running';
        }
      }
    }

    // Fallback to transition type
    if (transition === 'start' && jobStatus === 'succeeded') {
      return 'running';
    } else if (transition === 'stop' && jobStatus === 'succeeded') {
      return 'stopped';
    }

    return 'unknown';
  } catch (error) {
    console.warn(`Error determining status for workspace ${workspace.id}:`, error);
    return 'unknown';
  }
}

/**
 * Determine health status from workspace agents
 */
export function getHealthStatus(workspace: CoderWorkspace): HealthStatus {
  try {
    const resources = workspace.latest_build?.resources || [];
    for (const resource of resources) {
      const agents = resource.agents || [];
      for (const agent of agents) {
        const apps = agent.apps || [];
        for (const app of apps) {
          if (app.health === 'unhealthy') {
            return 'unhealthy';
          }
        }
      }
    }

    // If no unhealthy apps found, consider healthy
    return 'healthy';
  } catch (error) {
    console.warn(`Error determining health for workspace ${workspace.id}:`, error);
    return 'unknown';
  }
}

// ===== Main Enrichment Functions =====

/**
 * Enrich workspace data with calculated metrics
 * Team information is now pre-enriched in the snapshot at collection time
 */
export function enrichWorkspaceData(
  workspaces: CoderWorkspace[]
): WorkspaceMetrics[] {
  const now = new Date();

  return workspaces.map((workspace) => {
    const lastActive = getLastActiveTimestamp(workspace);
    const daysSinceActive = daysBetween(new Date(lastActive), now);
    const daysSinceCreated = daysBetween(new Date(workspace.created_at), now);
    const workspaceHours = getWorkspaceUsageHours(workspace);
    const activeHours = getWorkspaceActiveHours(workspace);

    // Use pre-enriched data from snapshot
    const teamName = workspace.team_name || 'Unassigned';
    const firstName = workspace.owner_first_name;
    const lastName = workspace.owner_last_name;

    // Build owner name
    let ownerName = workspace.owner_name;
    if (firstName && lastName) {
      ownerName = `${firstName} ${lastName}`;
    }

    return {
      workspace_id: workspace.id,
      workspace_name: workspace.name || `${workspace.owner_name}/workspace`,
      owner_github_handle: workspace.owner_name,
      owner_name: ownerName,
      team_name: teamName,
      template_id: workspace.template_id,
      template_name: workspace.template_name,
      template_display_name: workspace.template_display_name,
      current_status: getCurrentStatus(workspace),
      health_status: getHealthStatus(workspace),
      created_at: workspace.created_at,
      last_active: lastActive,
      last_build_at: workspace.latest_build.created_at,
      days_since_created: daysSinceCreated,
      days_since_active: daysSinceActive,
      workspace_hours: workspaceHours,
      active_hours: activeHours,
      total_builds: workspace.latest_build.build_number,
      last_build_status: workspace.latest_build.job?.status || 'unknown',
      activity_status: classifyActivityStatus(daysSinceActive),
    };
  });
}

/**
 * Aggregate workspace metrics by team
 */
export function aggregateByTeam(
  workspaces: WorkspaceMetrics[],
  accumulatedUsage?: Record<string, { owner_name: string; template_name: string; team_name: string; total_active_hours: number }>
): TeamMetrics[] {
  const teams = new Map<string, WorkspaceMetrics[]>();

  // Group workspaces by team
  workspaces.forEach((workspace) => {
    const teamWorkspaces = teams.get(workspace.team_name) || [];
    teamWorkspaces.push(workspace);
    teams.set(workspace.team_name, teamWorkspaces);
  });

  // Calculate metrics for each team
  return Array.from(teams.entries()).map(([teamName, teamWorkspaces]) => {
    // Template distribution
    const templateDistribution: Record<string, number> = {};
    teamWorkspaces.forEach((workspace) => {
      const count = templateDistribution[workspace.template_display_name] || 0;
      templateDistribution[workspace.template_display_name] = count + 1;
    });

    // Total workspace hours (sum of all workspace lifetime hours)
    const totalWorkspaceHours = teamWorkspaces.reduce((sum, w) => sum + w.workspace_hours, 0);

    // Calculate total active hours and total workspaces from accumulated usage data
    let totalActiveHours = calculateTotalActiveHours(teamWorkspaces);  // Default to current
    let totalWorkspacesEver = teamWorkspaces.length;  // Default to current count

    if (accumulatedUsage) {
      totalActiveHours = 0;
      const allWorkspaceIds = new Set<string>();
      let hasWorkspaceIds = false;

      Object.values(accumulatedUsage).forEach((record) => {
        if (record.team_name === teamName) {
          totalActiveHours += record.total_active_hours;
          // Collect all unique workspace IDs ever created for this team
          if (record.workspace_ids && record.workspace_ids.length > 0) {
            hasWorkspaceIds = true;
            record.workspace_ids.forEach(id => allWorkspaceIds.add(id));
          }
        }
      });

      // Only use accumulated count if we have workspace_ids data
      if (hasWorkspaceIds) {
        totalWorkspacesEver = allWorkspaceIds.size;
      }
    }

    // Average workspace hours
    const avgWorkspaceHours =
      teamWorkspaces.length > 0 ? totalWorkspaceHours / teamWorkspaces.length : 0;

    // Calculate active days (unique dates when workspaces were active)
    const activeDates = new Set<string>();
    teamWorkspaces.forEach((workspace) => {
      // Add creation date
      const createdDate = new Date(workspace.created_at).toISOString().split('T')[0];
      activeDates.add(createdDate);

      // Add last active date if different from created
      const lastActiveDate = new Date(workspace.last_active).toISOString().split('T')[0];
      if (lastActiveDate !== createdDate) {
        activeDates.add(lastActiveDate);
      }
    });

    // Member activity
    const memberMap = new Map<string, { workspaces: WorkspaceMetrics[] }>();
    teamWorkspaces.forEach((workspace) => {
      const member = memberMap.get(workspace.owner_github_handle) || { workspaces: [] };
      member.workspaces.push(workspace);
      memberMap.set(workspace.owner_github_handle, member);
    });

    const members = Array.from(memberMap.entries()).map(([githubHandle, data]) => {
      const mostRecentWorkspace = data.workspaces.reduce((most, current) =>
        new Date(current.last_active) > new Date(most.last_active) ? current : most
      );

      return {
        github_handle: githubHandle,
        name: mostRecentWorkspace.owner_name,
        workspace_count: data.workspaces.length,
        last_active: mostRecentWorkspace.last_active,
        activity_status: mostRecentWorkspace.activity_status,
      };
    });

    // Sort members by last active (most recent first)
    members.sort((a, b) => new Date(b.last_active).getTime() - new Date(a.last_active).getTime());

    // Count unique active users (users with at least one active workspace in last 7 days)
    const activeUsers = new Set<string>();
    teamWorkspaces.forEach((workspace) => {
      if (workspace.activity_status === 'active') {
        activeUsers.add(workspace.owner_github_handle);
      }
    });

    return {
      team_name: teamName,
      total_workspaces: totalWorkspacesEver,  // All-time count including deleted
      unique_active_users: activeUsers.size,
      total_workspace_hours: Math.round(totalWorkspaceHours),
      total_active_hours: Math.round(totalActiveHours),
      avg_workspace_hours: Math.round(avgWorkspaceHours * 10) / 10,
      active_days: activeDates.size,
      template_distribution: templateDistribution,
      members,
    };
  });
}

/**
 * Calculate platform-wide metrics
 */
export function calculatePlatformMetrics(workspaces: WorkspaceMetrics[]): PlatformMetrics {
  const activeWorkspaces = workspaces.filter((w) => w.activity_status === 'active');
  const inactiveWorkspaces = workspaces.filter((w) => w.activity_status === 'inactive');
  const staleWorkspaces = workspaces.filter((w) => w.activity_status === 'stale');
  const healthyWorkspaces = workspaces.filter((w) => w.health_status === 'healthy');

  // Unique users
  const uniqueUsers = new Set(workspaces.map((w) => w.owner_github_handle));

  // Unique teams
  const uniqueTeams = new Set(workspaces.map((w) => w.team_name));

  // Most popular template
  const templateCounts = new Map<string, { name: string; displayName: string; count: number }>();
  workspaces.forEach((workspace) => {
    const existing = templateCounts.get(workspace.template_name) || {
      name: workspace.template_name,
      displayName: workspace.template_display_name,
      count: 0,
    };
    existing.count++;
    templateCounts.set(workspace.template_name, existing);
  });

  let mostPopularTemplate = null;
  let maxCount = 0;
  templateCounts.forEach((data) => {
    if (data.count > maxCount) {
      maxCount = data.count;
      mostPopularTemplate = {
        name: data.name,
        display_name: data.displayName,
        count: data.count,
      };
    }
  });

  // Average days since active
  const avgDaysSinceActive =
    workspaces.length > 0
      ? workspaces.reduce((sum, w) => sum + w.days_since_active, 0) / workspaces.length
      : 0;

  // Healthy rate percentage
  const healthyRate = workspaces.length > 0 ? (healthyWorkspaces.length / workspaces.length) * 100 : 0;

  return {
    total_workspaces: workspaces.length,
    total_users: uniqueUsers.size,
    total_teams: uniqueTeams.size,
    active_workspaces: activeWorkspaces.length,
    inactive_workspaces: inactiveWorkspaces.length,
    stale_workspaces: staleWorkspaces.length,
    total_templates: templateCounts.size,
    most_popular_template: mostPopularTemplate,
    healthy_rate: Math.round(healthyRate * 10) / 10,
    avg_days_since_active: Math.round(avgDaysSinceActive * 10) / 10,
  };
}

/**
 * Calculate template-level metrics
 */
export function calculateTemplateMetrics(
  workspaces: WorkspaceMetrics[],
  templates: CoderTemplate[],
  accumulatedUsage?: Record<string, { owner_name: string; template_name: string; team_name: string; total_active_hours: number }>
): TemplateMetrics[] {
  // Group workspaces by template
  const templateMap = new Map<string, WorkspaceMetrics[]>();
  workspaces.forEach((workspace) => {
    const existing = templateMap.get(workspace.template_id) || [];
    existing.push(workspace);
    templateMap.set(workspace.template_id, existing);
  });

  // Calculate metrics for each template
  return templates.map((template) => {
    const templateWorkspaces = templateMap.get(template.id) || [];
    const activeWorkspaces = templateWorkspaces.filter((w) => w.activity_status === 'active');

    // Total workspace hours (sum of all workspace lifetime hours)
    const totalWorkspaceHours = templateWorkspaces.reduce((sum, w) => sum + w.workspace_hours, 0);

    // Calculate total active hours and total workspaces from accumulated usage data
    let totalActiveHours = calculateTotalActiveHours(templateWorkspaces);  // Default to current
    let totalWorkspacesEver = templateWorkspaces.length;  // Default to current count

    if (accumulatedUsage) {
      totalActiveHours = 0;
      const allWorkspaceIds = new Set<string>();
      let hasWorkspaceIds = false;

      Object.values(accumulatedUsage).forEach((record) => {
        if (record.template_name === template.name) {
          totalActiveHours += record.total_active_hours;
          // Collect all unique workspace IDs ever created for this template
          if (record.workspace_ids && record.workspace_ids.length > 0) {
            hasWorkspaceIds = true;
            record.workspace_ids.forEach(id => allWorkspaceIds.add(id));
          }
        }
      });

      // Only use accumulated count if we have workspace_ids data
      if (hasWorkspaceIds) {
        totalWorkspacesEver = allWorkspaceIds.size;
      }
    }

    // Average workspace hours
    const avgWorkspaceHours =
      templateWorkspaces.length > 0 ? totalWorkspaceHours / templateWorkspaces.length : 0;

    // Team distribution
    const teamDistribution: Record<string, number> = {};
    templateWorkspaces.forEach((workspace) => {
      const count = teamDistribution[workspace.team_name] || 0;
      teamDistribution[workspace.team_name] = count + 1;
    });

    // Count unique active users for this template (users with at least one active workspace in last 7 days)
    const activeUsers = new Set<string>();
    activeWorkspaces.forEach((workspace) => {
      activeUsers.add(workspace.owner_github_handle);
    });

    return {
      template_id: template.id,
      template_name: template.name,
      template_display_name: template.display_name,
      total_workspaces: totalWorkspacesEver,  // All-time count including deleted
      active_workspaces: activeWorkspaces.length,
      unique_active_users: activeUsers.size,
      total_workspace_hours: Math.round(totalWorkspaceHours),
      total_active_hours: Math.round(totalActiveHours),
      avg_workspace_hours: Math.round(avgWorkspaceHours * 10) / 10,
      team_distribution: teamDistribution,
    };
  });
}

/**
 * Calculate daily user engagement from workspace data
 * Returns array of daily unique users and active workspaces for the last 60 days
 *
 * A user is considered "engaged" if they initiate a connection to their workspace via apps, web terminal, or SSH.
 * This function processes all builds for each workspace and extracts all agent connection timestamps.
 */
export function calculateDailyEngagement(workspaces: CoderWorkspace[]): DailyEngagement[] {
  const now = new Date();
  const daysToShow = 60;

  // Create a map to store engagement data by date
  const engagementMap = new Map<string, Set<string>>();
  const workspaceActivityMap = new Map<string, Set<string>>();

  // Initialize map for last 60 days
  for (let i = 0; i < daysToShow; i++) {
    const date = new Date(now);
    date.setDate(date.getDate() - i);
    const dateStr = date.toISOString().split('T')[0];
    engagementMap.set(dateStr, new Set());
    workspaceActivityMap.set(dateStr, new Set());
  }

  // Process each workspace and all its builds
  workspaces.forEach((workspace) => {
    const workspaceId = workspace.id;
    const ownerHandle = workspace.owner_name.toLowerCase();
    const allBuilds = workspace.all_builds || [];

    // Track dates when this workspace had connections
    const workspaceConnectionDates = new Set<string>();

    // Process all builds to find all connection dates
    allBuilds.forEach((build) => {
      try {
        // Count workspace start actions as engagement (user initiating connection)
        if (build.transition === 'start' && build.created_at) {
          const dateStr = build.created_at.split('T')[0];
          if (engagementMap.has(dateStr)) {
            engagementMap.get(dateStr)!.add(ownerHandle);
            workspaceConnectionDates.add(dateStr);
          }
        }

        const resources = build.resources || [];

        for (const resource of resources) {
          const agents = resource.agents || [];

          for (const agent of agents) {
            // Extract all connection timestamps from this agent
            const firstConnected = agent.first_connected_at;
            const lastConnected = agent.last_connected_at;

            // Add engagement for first connection date
            if (firstConnected) {
              const dateStr = firstConnected.split('T')[0];
              if (engagementMap.has(dateStr)) {
                engagementMap.get(dateStr)!.add(ownerHandle);
                workspaceConnectionDates.add(dateStr);
              }
            }

            // Add engagement for last connection date (if different from first)
            if (lastConnected && lastConnected !== firstConnected) {
              const dateStr = lastConnected.split('T')[0];
              if (engagementMap.has(dateStr)) {
                engagementMap.get(dateStr)!.add(ownerHandle);
                workspaceConnectionDates.add(dateStr);
              }
            }
          }
        }
      } catch (error) {
        console.warn(`Error processing build for workspace ${workspaceId}:`, error);
      }
    });

    // Add workspace to active workspaces for all dates it had connections
    workspaceConnectionDates.forEach((dateStr) => {
      workspaceActivityMap.get(dateStr)?.add(workspaceId);
    });
  });

  // Convert to array and sort by date
  const engagement: DailyEngagement[] = Array.from(engagementMap.entries())
    .map(([date, users]) => ({
      date,
      unique_users: users.size,
      active_workspaces: workspaceActivityMap.get(date)?.size || 0,
    }))
    .sort((a, b) => a.date.localeCompare(b.date));

  return engagement;
}

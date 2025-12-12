import type { TeamMetrics, ActivityStatus } from './types';

/**
 * Member data for aggregation
 */
interface MemberData {
  github_handle: string;
  name: string;
  workspace_count: number;
  last_active: string;
  activity_status: ActivityStatus;
}

/**
 * Extract company name from team name
 *
 * @param teamName - Full team name (e.g., "scotiabank-2-tangerine", "bell-1")
 * @returns Company name (e.g., "scotiabank", "bell")
 *
 * @example
 * extractCompanyName("scotiabank-2-tangerine") // "scotiabank"
 * extractCompanyName("bell-1") // "bell"
 * extractCompanyName("hitachi-rail-1") // "hitachi-rail"
 * extractCompanyName("facilitators") // "facilitators"
 */
export function extractCompanyName(teamName: string): string {
  // Special cases: teams without numeric suffix
  if (teamName === 'facilitators' || teamName === 'Unassigned') {
    return teamName;
  }

  // Extract prefix before first "-{digit}" pattern
  // Handles: "scotiabank-2-tangerine", "bell-1", "hitachi-rail-1"
  const match = teamName.match(/^([a-z-]+?)-(\d+)/);
  return match ? match[1] : teamName;
}

/**
 * Aggregate teams by company
 * Groups individual teams (e.g., "bell-1", "bell-2") into company-level aggregates (e.g., "bell")
 * Follows pattern from lib/metrics.ts:aggregateByTeam()
 *
 * @param teams - Array of individual team metrics with workspaces_for_template count
 * @returns Array of company-aggregated metrics
 *
 * Aggregation rules:
 * - Sum numeric metrics (workspaces, hours, active_days)
 * - Deduplicate members by github_handle, keeping most recent activity
 * - Sum workspace_count across team instances for each member
 * - Merge template distributions
 * - Calculate active_days as union of all dates (not sum)
 */
export function aggregateByCompany(
  teams: (TeamMetrics & { workspaces_for_template: number })[]
): (TeamMetrics & { workspaces_for_template: number })[] {
  // Group teams by company using Map
  const companyMap = new Map<string, (TeamMetrics & { workspaces_for_template: number })[]>();

  teams.forEach(team => {
    const company = extractCompanyName(team.team_name);
    const companyTeams = companyMap.get(company) || [];
    companyTeams.push(team);
    companyMap.set(company, companyTeams);
  });

  // Aggregate each company
  return Array.from(companyMap.entries()).map(([companyName, companyTeams]) => {
    // Sum numeric metrics
    const total_workspaces = companyTeams.reduce((sum, t) => sum + t.total_workspaces, 0);
    const total_workspace_hours = companyTeams.reduce((sum, t) => sum + t.total_workspace_hours, 0);
    const total_active_hours = companyTeams.reduce((sum, t) => sum + t.total_active_hours, 0);
    const workspaces_for_template = companyTeams.reduce((sum, t) => sum + t.workspaces_for_template, 0);
    const avg_workspace_hours = total_workspaces > 0 ? total_workspace_hours / total_workspaces : 0;

    // Deduplicate members by github_handle, keep most recent activity
    const memberMap = new Map<string, MemberData>();
    companyTeams.forEach(team => {
      team.members.forEach(member => {
        const existing = memberMap.get(member.github_handle);
        if (!existing || new Date(member.last_active) > new Date(existing.last_active)) {
          // Keep most recent, but sum workspace_count
          memberMap.set(member.github_handle, {
            ...member,
            workspace_count: (existing?.workspace_count || 0) + member.workspace_count
          });
        }
      });
    });

    const members = Array.from(memberMap.values())
      .sort((a, b) => new Date(b.last_active).getTime() - new Date(a.last_active).getTime());

    // Count unique active users
    const unique_active_users = members.filter(m => m.activity_status === 'active').length;

    // Merge template distributions
    const template_distribution: Record<string, number> = {};
    companyTeams.forEach(team => {
      Object.entries(team.template_distribution).forEach(([template, count]) => {
        template_distribution[template] = (template_distribution[template] || 0) + count;
      });
    });

    // Calculate active days as union of all dates
    const activeDates = new Set<string>();
    companyTeams.forEach(team => {
      team.members.forEach(member => {
        const date = new Date(member.last_active).toISOString().split('T')[0];
        activeDates.add(date);
      });
    });

    return {
      team_name: companyName,
      total_workspaces,
      unique_active_users,
      total_workspace_hours: Math.round(total_workspace_hours),
      total_active_hours: Math.round(total_active_hours),
      avg_workspace_hours: Math.round(avg_workspace_hours * 10) / 10,
      active_days: activeDates.size,
      workspaces_for_template,
      template_distribution,
      members
    };
  });
}

// ===== Coder API Types =====

export interface CoderWorkspace {
  id: string;
  created_at: string;
  updated_at: string;
  owner_id: string;
  owner_name: string;  // This is the GitHub username!
  owner_avatar_url?: string;

  // Pre-enriched participant data from snapshot (added at collection time)
  team_name: string;  // Team assignment at snapshot time
  owner_first_name?: string;  // First name at snapshot time
  owner_last_name?: string;  // Last name at snapshot time

  organization_id: string;
  organization_name: string;
  template_id: string;
  template_name: string;
  template_display_name: string;
  template_icon?: string;
  name?: string;
  total_usage_hours?: number;  // Total usage hours across all builds (added by collection script)
  active_hours?: number;  // Active interaction hours from Insights API (added by collection script)
  all_builds?: any[];  // Full build history (added by collection script)
  latest_build: {
    id: string;
    created_at: string;
    updated_at: string;
    build_number: number;
    transition: 'start' | 'stop' | 'delete';
    job: {
      status: 'succeeded' | 'failed' | 'pending' | 'running' | 'canceled';
      started_at: string;
      completed_at: string;
    };
    resources: Array<{
      type: string;
      name: string;
      agents: Array<{
        id: string;
        created_at: string;
        updated_at: string;
        first_connected_at: string;
        last_connected_at: string;
        started_at: string;
        ready_at: string;
        status: 'connected' | 'connecting' | 'disconnected' | 'timeout';
        lifecycle_state: 'ready' | 'starting' | 'start_timeout' | 'shutting_down' | 'off';
        name: string;
        version: string;
        apps?: Array<{
          slug: string;
          display_name: string;
          health: 'healthy' | 'unhealthy' | 'initializing';
        }>;
      }>;
    }>;
  };
}

export interface CoderTemplate {
  id: string;
  created_at: string;
  updated_at: string;
  organization_id: string;
  organization_name: string;
  name: string;
  display_name: string;
  description?: string;
  icon?: string;
  default_ttl_ms?: number;
  max_ttl_ms?: number;
  workspace_count?: number;
}

export interface CoderSnapshot {
  timestamp: string;  // ISO 8601
  workspaces: CoderWorkspace[];
  templates: CoderTemplate[];
}

// ===== Firestore Types =====

export interface ParticipantData {
  github_handle: string;
  team_name: string;
  first_name?: string;
  last_name?: string;
  email?: string;
  onboarded?: boolean;
  onboarded_at?: string;
}

export interface TeamData {
  team_name: string;
  participants: string[];  // Array of github_handles
  openai_api_key?: string;
  openai_api_key_name?: string;
  langfuse_secret_key?: string;
  langfuse_public_key?: string;
  created_at?: string;
  updated_at?: string;
}

// ===== Analytics Metrics Types =====

export type ActivityStatus = 'active' | 'inactive' | 'stale';
export type WorkspaceStatus = 'running' | 'stopped' | 'error' | 'unknown';
export type HealthStatus = 'healthy' | 'unhealthy' | 'unknown';

export interface WorkspaceMetrics {
  // Identifiers
  workspace_id: string;
  workspace_name: string;
  owner_github_handle: string;
  owner_name: string;  // From Firestore participants
  team_name: string;   // From Firestore mapping

  // Template info
  template_id: string;
  template_name: string;
  template_display_name: string;

  // Status
  current_status: WorkspaceStatus;
  health_status: HealthStatus;

  // Activity
  created_at: string;
  last_active: string;  // Most recent agent last_connected_at
  last_build_at: string;
  days_since_created: number;
  days_since_active: number;
  workspace_hours: number;  // Total usage hours (from first connection to last connection)
  active_hours: number;     // Actual active interaction hours from Insights API

  // Build metrics
  total_builds: number;
  last_build_status: 'succeeded' | 'failed' | 'pending' | 'running' | 'canceled';

  // Computed flags
  activity_status: ActivityStatus;
}

export interface TeamMetrics {
  team_name: string;

  // Counts
  total_workspaces: number;
  unique_active_users: number;    // Number of unique users with activity in last 7 days

  // Time-based metrics
  total_workspace_hours: number;  // Sum of all workspace usage hours (first to last connection)
  total_active_hours: number;     // Sum of actual active interaction hours from Insights API
  avg_workspace_hours: number;    // Average workspace usage hours (first to last connection)
  active_days: number;            // Number of unique days with workspace activity

  // Template breakdown
  template_distribution: Record<string, number>;

  // Members
  members: Array<{
    github_handle: string;
    name: string;
    workspace_count: number;
    last_active: string;
    activity_status: ActivityStatus;
  }>;
}

export interface PlatformMetrics {
  // Overall
  total_workspaces: number;
  total_users: number;
  total_teams: number;

  // Activity levels
  active_workspaces: number;    // Last 7 days
  inactive_workspaces: number;  // 7-30 days
  stale_workspaces: number;     // 30+ days

  // Templates
  total_templates: number;
  most_popular_template: {
    name: string;
    display_name: string;
    count: number;
  } | null;

  // Health
  healthy_rate: number;  // Percentage
  avg_days_since_active: number;
}

export interface TemplateMetrics {
  template_id: string;
  template_name: string;
  template_display_name: string;
  total_workspaces: number;
  active_workspaces: number;
  unique_active_users: number;    // Number of unique users with activity in last 7 days
  total_workspace_hours: number;  // Sum of workspace usage hours (first to last connection) for this template
  total_active_hours: number;     // Sum of actual active interaction hours from Insights API
  avg_workspace_hours: number;    // Average workspace usage hours (first to last connection)
  team_distribution: Record<string, number>;
}

// ===== API Response Types =====

export interface DailyEngagement {
  date: string;  // ISO date string (YYYY-MM-DD)
  unique_users: number;
  active_workspaces: number;
}

export interface AnalyticsSnapshot {
  timestamp: string;
  platform_metrics: PlatformMetrics;
  team_metrics: TeamMetrics[];
  workspace_metrics: WorkspaceMetrics[];
  template_metrics: TemplateMetrics[];
  daily_engagement: DailyEngagement[];
}

export interface TeamListResponse {
  teams: Array<{
    team_name: string;
    member_count: number;
  }>;
}

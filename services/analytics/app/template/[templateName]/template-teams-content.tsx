'use client';

import { useState, useEffect, useCallback, useMemo } from 'react';
import Link from 'next/link';
import { ArrowLeft, Users, ArrowUpDown, ArrowUp, ArrowDown } from 'lucide-react';
import type { User } from '@vector-institute/aieng-auth-core';
import type { AnalyticsSnapshot, TeamMetrics } from '@/lib/types';
import { Tooltip } from '@/app/components/tooltip';

type SortColumn = 'team_name' | 'workspaces_for_template' | 'unique_active_users' | 'total_workspace_hours' | 'total_active_hours' | 'active_days';
type SortDirection = 'asc' | 'desc';

interface TemplateTeamsContentProps {
  user: User | null;
  templateName: string;
}

export default function TemplateTeamsContent({ user, templateName }: TemplateTeamsContentProps) {
  const [data, setData] = useState<AnalyticsSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sortColumn, setSortColumn] = useState<SortColumn>('workspaces_for_template');
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc');

  const handleLogout = async () => {
    try {
      await fetch('/analytics/api/auth/logout', { method: 'POST' });
      window.location.href = '/analytics/login';
    } catch (error) {
      console.error('Logout failed:', error);
    }
  };

  const fetchData = useCallback(async () => {
    try {
      const response = await fetch('/analytics/api/snapshot');
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const json = await response.json();
      setData(json);
      setError(null);
    } catch (err) {
      console.error('Failed to fetch analytics data:', err);
      setError(err instanceof Error ? err.message : 'Failed to fetch data');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Find the template
  const template = data?.template_metrics.find(t => t.template_name === decodeURIComponent(templateName));

  // Filter team metrics for this template
  const templateTeams: (TeamMetrics & { workspaces_for_template: number })[] = useMemo(() => {
    if (!data || !template) return [];

    return data.team_metrics
      .map(team => {
        const workspacesForTemplate = template.team_distribution[team.team_name] || 0;
        return {
          ...team,
          workspaces_for_template: workspacesForTemplate
        };
      })
      .filter(team => team.workspaces_for_template > 0);
  }, [data, template]);

  // Sort template teams
  const sortedTemplateTeams = useMemo(() => {
    const sorted = [...templateTeams].sort((a, b) => {
      let aValue: string | number = a[sortColumn];
      let bValue: string | number = b[sortColumn];

      // Handle null/undefined values
      if (aValue === null || aValue === undefined) aValue = sortColumn === 'team_name' ? '' : 0;
      if (bValue === null || bValue === undefined) bValue = sortColumn === 'team_name' ? '' : 0;

      // For strings, use locale compare
      if (typeof aValue === 'string' && typeof bValue === 'string') {
        return sortDirection === 'asc'
          ? aValue.localeCompare(bValue)
          : bValue.localeCompare(aValue);
      }

      // For numbers
      return sortDirection === 'asc'
        ? (aValue as number) - (bValue as number)
        : (bValue as number) - (aValue as number);
    });

    return sorted;
  }, [templateTeams, sortColumn, sortDirection]);

  // Handle column header click
  const handleSort = (column: SortColumn) => {
    if (sortColumn === column) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortColumn(column);
      setSortDirection('desc');
    }
  };

  // Get sort icon for a column
  const getSortIcon = (column: SortColumn) => {
    if (sortColumn !== column) {
      return <ArrowUpDown className="w-3 h-3 opacity-50" />;
    }
    return sortDirection === 'asc' ? (
      <ArrowUp className="w-3 h-3" />
    ) : (
      <ArrowDown className="w-3 h-3" />
    );
  };

  // Loading state
  if (loading && !data) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 via-slate-100 to-slate-50 dark:from-slate-900 dark:via-slate-800 dark:to-slate-900 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-vector-magenta dark:border-vector-violet mx-auto"></div>
          <p className="mt-4 text-slate-600 dark:text-slate-400">Loading team data...</p>
        </div>
      </div>
    );
  }

  // Error state
  if (error && !data) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 via-slate-100 to-slate-50 dark:from-slate-900 dark:via-slate-800 dark:to-slate-900 flex items-center justify-center">
        <div className="text-center">
          <p className="text-red-600 dark:text-red-400">Error: {error}</p>
          <button
            onClick={fetchData}
            className="mt-4 px-4 py-2 bg-vector-magenta text-white rounded-xl hover:bg-vector-magenta/90"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (!data) return null;

  if (!template) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 via-slate-100 to-slate-50 dark:from-slate-900 dark:via-slate-800 dark:to-slate-900 flex items-center justify-center">
        <div className="text-center">
          <p className="text-red-600 dark:text-red-400">Template not found</p>
          <Link
            href="/"
            className="mt-4 inline-block px-4 py-2 bg-vector-magenta text-white rounded-xl hover:bg-vector-magenta/90"
          >
            Back to Analytics
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-900 dark:to-slate-800">
      {/* Vector Brand Header Accent */}
      <div className="h-1 bg-gradient-to-r from-vector-magenta via-vector-violet to-vector-cobalt"></div>

      <div className="p-4 md:p-8">
        <div className="max-w-7xl mx-auto">
          <div className="mb-8 animate-fade-in">
            <div className="flex items-center justify-between">
              <div>
                <Link
                  href="/"
                  className="inline-flex items-center gap-2 text-sm text-slate-600 dark:text-slate-400 hover:text-vector-magenta dark:hover:text-vector-violet transition-colors mb-3"
                >
                  <ArrowLeft className="h-4 w-4" />
                  Back to Analytics
                </Link>
                <h1 className="text-4xl md:text-5xl font-bold bg-gradient-to-r from-vector-magenta via-vector-violet to-vector-cobalt bg-clip-text text-transparent mb-2">
                  {template.template_display_name}
                </h1>
                <p className="text-slate-700 dark:text-slate-300 text-lg">
                  Team breakdown for this template
                </p>
              </div>
              <div className="flex items-center gap-4">
                {user && (
                  <div className="text-right">
                    <p className="text-xs text-slate-500 dark:text-slate-400 uppercase tracking-wide">Signed in as</p>
                    <p className="text-sm font-semibold bg-gradient-to-r from-vector-magenta to-vector-violet bg-clip-text text-transparent">{user.email}</p>
                  </div>
                )}
                <button
                  onClick={handleLogout}
                  className="px-4 py-2 text-sm font-semibold text-white bg-gradient-to-r from-slate-600 to-slate-700 hover:from-vector-magenta hover:to-vector-violet rounded-lg shadow-sm hover:shadow-md transition-all duration-200"
                >
                  Logout
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-4 md:px-8 pb-8">
        {/* Summary Cards */}
        <div className="grid gap-6 md:grid-cols-3 mb-8 animate-fade-in">
          <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-xl border-2 border-slate-200 dark:border-slate-700 p-6">
            <div className="text-sm font-semibold text-slate-600 dark:text-slate-400 uppercase tracking-wider mb-2">
              Total Workspaces
            </div>
            <div className="text-3xl font-bold text-slate-900 dark:text-white">
              {template.total_workspaces}
            </div>
          </div>

          <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-xl border-2 border-slate-200 dark:border-slate-700 p-6">
            <div className="text-sm font-semibold text-slate-600 dark:text-slate-400 uppercase tracking-wider mb-2">
              Active Workspaces
            </div>
            <div className="text-3xl font-bold text-vector-turquoise">
              {template.active_workspaces}
            </div>
          </div>

          <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-xl border-2 border-slate-200 dark:border-slate-700 p-6">
            <div className="text-sm font-semibold text-slate-600 dark:text-slate-400 uppercase tracking-wider mb-2">
              Total Hours
            </div>
            <div className="text-3xl font-bold text-slate-900 dark:text-white">
              {template.total_workspace_hours.toLocaleString()}h
            </div>
          </div>
        </div>

        {/* Teams Table */}
        <div className="animate-slide-up">
          <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-xl border-2 border-slate-200 dark:border-slate-700 overflow-hidden">
            <div className="px-6 py-5 border-b border-slate-200 dark:border-slate-700">
              <h2 className="text-2xl font-bold text-slate-900 dark:text-white flex items-center gap-2">
                <Users className="h-6 w-6 text-vector-magenta" />
                Teams Using This Template
              </h2>
              <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
                {sortedTemplateTeams.length} teams have created workspaces from this template
              </p>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-slate-100 dark:bg-slate-800 border-b-2 border-vector-magenta/20 dark:border-vector-violet/30">
                  <tr>
                    <th
                      className="px-6 py-4 text-left text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider cursor-pointer hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors"
                      onClick={() => handleSort('team_name')}
                    >
                      <div className="flex items-center gap-2">
                        Team
                        {getSortIcon('team_name')}
                      </div>
                    </th>
                    <th
                      className="px-6 py-4 text-right text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider cursor-pointer hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors"
                      onClick={() => handleSort('workspaces_for_template')}
                    >
                      <Tooltip content="Number of workspaces created by this team from this template">
                        <div className="flex items-center justify-end gap-2">
                          Workspaces
                          {getSortIcon('workspaces_for_template')}
                        </div>
                      </Tooltip>
                    </th>
                    <th
                      className="px-6 py-4 text-right text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider cursor-pointer hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors"
                      onClick={() => handleSort('unique_active_users')}
                    >
                      <Tooltip content="Number of unique team members who have used workspaces in the last 7 days">
                        <div className="flex items-center justify-end gap-2">
                          Active Users
                          {getSortIcon('unique_active_users')}
                        </div>
                      </Tooltip>
                    </th>
                    <th
                      className="px-6 py-4 text-right text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider cursor-pointer hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors"
                      onClick={() => handleSort('total_workspace_hours')}
                    >
                      <Tooltip content="Sum of workspace usage hours (time from first connection to last connection) for this team">
                        <div className="flex items-center justify-end gap-2">
                          Total Hours
                          {getSortIcon('total_workspace_hours')}
                        </div>
                      </Tooltip>
                    </th>
                    <th
                      className="px-6 py-4 text-right text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider cursor-pointer hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors"
                      onClick={() => handleSort('total_active_hours')}
                    >
                      <Tooltip content="Sum of actual active interaction hours based on agent activity heartbeats (excludes idle time)">
                        <div className="flex items-center justify-end gap-2">
                          Active Hours
                          {getSortIcon('total_active_hours')}
                        </div>
                      </Tooltip>
                    </th>
                    <th
                      className="px-6 py-4 text-right text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider cursor-pointer hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors"
                      onClick={() => handleSort('active_days')}
                    >
                      <Tooltip content="Number of days with activity in the last 7 days for this team" position="right">
                        <div className="flex items-center justify-end gap-2">
                          Active Days
                          {getSortIcon('active_days')}
                        </div>
                      </Tooltip>
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200 dark:divide-slate-700">
                  {sortedTemplateTeams.map((team) => (
                    <tr
                      key={team.team_name}
                      className="hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors"
                    >
                      <td className="px-6 py-4 text-sm font-medium text-slate-900 dark:text-white">
                        <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-slate-100 text-slate-700 dark:bg-slate-700 dark:text-slate-200 border border-slate-300 dark:border-slate-600">
                          {team.team_name}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-right text-sm text-slate-700 dark:text-slate-300">
                        {team.workspaces_for_template}
                      </td>
                      <td className="px-6 py-4 text-right text-sm">
                        <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-vector-violet/10 text-vector-violet border border-vector-violet/30">
                          {team.unique_active_users}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-right text-sm text-slate-700 dark:text-slate-300">
                        {team.total_workspace_hours.toLocaleString()}h
                      </td>
                      <td className="px-6 py-4 text-right text-sm">
                        <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800">
                          {team.total_active_hours.toLocaleString()}h
                        </span>
                      </td>
                      <td className="px-6 py-4 text-right text-sm text-vector-turquoise">
                        {team.active_days}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

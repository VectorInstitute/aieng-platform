'use client';

import { useCallback, useEffect, useState } from 'react';
import type { User } from '@vector-institute/aieng-auth-core';

interface Participant {
  github_handle: string;
  team_name: string;
  onboarded: boolean;
  onboarded_at?: string;
  first_name?: string;
  last_name?: string;
  github_status?: 'member' | 'pending' | 'not_invited';
  bootcamp_name?: string;
}

interface Summary {
  total: number;
  onboarded: number;
  notOnboarded: number;
  percentage: number;
}

interface ApiResponse {
  participants: Participant[];
  summary: Summary;
}

interface DashboardContentProps {
  user: User | null;
}

export default function DashboardContent({ user }: DashboardContentProps) {
  const [data, setData] = useState<ApiResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [statusFilter, setStatusFilter] = useState<'all' | 'onboarded' | 'not_onboarded'>('all');
  const [roleFilter, setRoleFilter] = useState<'participants' | 'facilitators'>('participants');
  const [bootcampFilter, setBootcampFilter] = useState<string>('all');

  const handleLogout = async () => {
    try {
      await fetch('/onboarding/api/auth/logout', { method: 'POST' });
      window.location.href = '/onboarding/login';
    } catch (error) {
      console.error('Logout failed:', error);
    }
  };

  const fetchData = useCallback(async () => {
    try {
      setError(null);
      const response = await fetch(`/onboarding/api/participants?role=${roleFilter}`, {
        cache: 'no-store'
      });

      if (!response.ok) {
        throw new Error(`Failed to fetch: ${response.statusText}`);
      }

      const result = await response.json();

      // Fetch GitHub status for all participants
      try {
        const github_handles = result.participants.map((p: Participant) => p.github_handle);
        const statusResponse = await fetch('/onboarding/api/github-status', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ github_handles }),
          cache: 'no-store'
        });

        if (statusResponse.ok) {
          const statusData = await statusResponse.json();
          const statusMap = new Map(
            statusData.statuses.map((s: { github_handle: string; status: string }) => [
              s.github_handle,
              s.status
            ])
          );

          // Merge GitHub status with participant data
          result.participants = result.participants.map((p: Participant) => ({
            ...p,
            github_status: statusMap.get(p.github_handle) || 'not_invited'
          }));
        }
      } catch (statusErr) {
        console.warn('Failed to fetch GitHub status:', statusErr);
        // Continue without GitHub status if it fails
      }

      setData(result);
      setLastUpdated(new Date());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch data');
      console.error('Error fetching participants:', err);
    } finally {
      setLoading(false);
    }
  }, [roleFilter]);

  useEffect(() => {
    fetchData();

    // Auto-refresh every 30 seconds
    const interval = setInterval(fetchData, 30000);

    return () => clearInterval(interval);
  }, [fetchData]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-900 dark:to-slate-800">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-vector-magenta dark:border-vector-violet mx-auto"></div>
          <p className="mt-4 text-slate-600 dark:text-slate-400">Loading participant data...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-900 dark:to-slate-800 p-4">
        <div className="card p-8 max-w-md w-full text-center">
          <div className="text-vector-magenta text-5xl mb-4">⚠️</div>
          <h2 className="text-2xl font-bold text-slate-900 dark:text-white mb-2">Error</h2>
          <p className="text-slate-600 dark:text-slate-400 mb-4">{error}</p>
          <button
            onClick={fetchData}
            className="px-6 py-2 bg-vector-magenta text-white rounded-lg hover:bg-vector-violet transition-colors font-semibold"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (!data) {
    return null;
  }

  const { participants, summary } = data;

  // Get unique bootcamp names for filter options
  const bootcampNames = Array.from(
    new Set(participants.map((p) => p.bootcamp_name || 'Unknown').filter(Boolean))
  ).sort();

  // Filter participants based on status and bootcamp
  const filteredParticipants = participants.filter((participant) => {
    // Status filter
    if (statusFilter === 'onboarded' && !participant.onboarded) return false;
    if (statusFilter === 'not_onboarded' && participant.onboarded) return false;

    // Bootcamp filter
    if (bootcampFilter !== 'all') {
      const participantBootcamp = participant.bootcamp_name || 'Unknown';
      if (participantBootcamp !== bootcampFilter) return false;
    }

    return true;
  });

  // Helper function to render GitHub status badge
  const renderGitHubStatus = (status?: 'member' | 'pending' | 'not_invited') => {
    if (!status) {
      return (
        <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-400 border border-slate-300 dark:border-slate-600">
          <svg className="w-3 h-3 mr-1" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
          </svg>
          Unknown
        </span>
      );
    }

    switch (status) {
      case 'member':
        return (
          <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-vector-turquoise/10 text-vector-turquoise dark:bg-vector-turquoise/20 dark:text-vector-turquoise border border-vector-turquoise/30">
            <svg className="w-3 h-3 mr-1" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
            </svg>
            Member
          </span>
        );
      case 'pending':
        return (
          <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-amber-50 text-amber-700 dark:bg-amber-900/20 dark:text-amber-400 border border-amber-200 dark:border-amber-800">
            <svg className="w-3 h-3 mr-1 animate-pulse" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z" clipRule="evenodd" />
            </svg>
            Pending
          </span>
        );
      case 'not_invited':
        return (
          <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-slate-100 text-slate-700 dark:bg-slate-700 dark:text-slate-300 border border-slate-300 dark:border-slate-600">
            <svg className="w-3 h-3 mr-1" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
            </svg>
            Not Invited
          </span>
        );
    }
  };

  // CSV export function
  const exportToCSV = () => {
    const headers = ['#', 'Name', 'GitHub Handle', 'GitHub Status', 'Team Name', 'Bootcamp', 'Status', 'Onboarded At'];
    const rows = filteredParticipants.map((participant, index) => {
      const name = participant.first_name && participant.last_name
        ? `${participant.first_name} ${participant.last_name}`
        : participant.first_name || participant.last_name || 'N/A';
      const status = participant.onboarded ? 'Onboarded' : 'Not Onboarded';
      const onboardedAt = participant.onboarded_at || 'N/A';
      const githubStatus = participant.github_status
        ? participant.github_status === 'member'
          ? 'Member'
          : participant.github_status === 'pending'
          ? 'Pending'
          : 'Not Invited'
        : 'Unknown';
      const bootcamp = participant.bootcamp_name || 'N/A';

      return [
        index + 1,
        name,
        participant.github_handle,
        githubStatus,
        participant.team_name,
        bootcamp,
        status,
        onboardedAt
      ];
    });

    const csvContent = [
      headers.join(','),
      ...rows.map(row => row.map(cell => `"${cell}"`).join(','))
    ].join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);

    link.setAttribute('href', url);
    link.setAttribute('download', `participants_${statusFilter}_${new Date().toISOString().split('T')[0]}.csv`);
    link.style.visibility = 'hidden';

    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-900 dark:to-slate-800">
      {/* Vector Brand Header Accent */}
      <div className="h-1 bg-gradient-to-r from-vector-magenta via-vector-violet to-vector-cobalt"></div>

      <div className="p-4 md:p-8">
        <div className="max-w-7xl mx-auto">
          {/* Header */}
          <div className="mb-8 animate-fade-in">
            <div className="flex items-center justify-between">
              <div>
                <h1 className="text-4xl md:text-5xl font-bold bg-gradient-to-r from-vector-magenta via-vector-violet to-vector-cobalt bg-clip-text text-transparent mb-2">
                  Onboarding Status
                </h1>
                <p className="text-slate-700 dark:text-slate-300 text-lg">
                  Track technical onboarding progress in real-time
                </p>
                {lastUpdated && (
                  <p className="text-sm text-slate-500 dark:text-slate-400 mt-2">
                    Last updated: {lastUpdated.toLocaleTimeString()}
                  </p>
                )}
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

        {/* Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8 animate-slide-up">
          <div className="card p-6">
            <div className="text-sm font-semibold text-slate-600 dark:text-slate-400 mb-1 uppercase tracking-wide">
              Total Participants
            </div>
            <div className="text-3xl font-bold text-slate-900 dark:text-white">
              {summary.total}
            </div>
          </div>

          <div className="card p-6 border-l-4 border-vector-turquoise">
            <div className="text-sm font-semibold text-slate-600 dark:text-slate-400 mb-1 uppercase tracking-wide">
              Onboarded
            </div>
            <div className="text-3xl font-bold text-vector-turquoise">
              {summary.onboarded}
            </div>
          </div>

          <div className="card p-6 border-l-4 border-vector-tangerine">
            <div className="text-sm font-semibold text-slate-600 dark:text-slate-400 mb-1 uppercase tracking-wide">
              Not Onboarded
            </div>
            <div className="text-3xl font-bold text-vector-tangerine">
              {summary.notOnboarded}
            </div>
          </div>

          <div className="card p-6 border-l-4 border-vector-magenta">
            <div className="text-sm font-semibold text-slate-600 dark:text-slate-400 mb-1 uppercase tracking-wide">
              Completion Rate
            </div>
            <div className="text-3xl font-bold text-vector-magenta">
              {summary.percentage}%
            </div>
          </div>
        </div>

        {/* Progress Bar */}
        <div className="card p-6 mb-8 animate-slide-up" style={{ animationDelay: '100ms' }}>
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wide">
              Overall Progress
            </span>
            <span className="text-sm font-bold text-slate-700 dark:text-slate-300">
              {summary.onboarded} of {summary.total}
            </span>
          </div>
          <div className="w-full bg-slate-200 dark:bg-slate-700 rounded-full h-4 overflow-hidden">
            <div
              className="bg-gradient-to-r from-vector-magenta via-vector-violet to-vector-cobalt h-4 rounded-full transition-all duration-1000 ease-out"
              style={{ width: `${summary.percentage}%` }}
            ></div>
          </div>
        </div>

        {/* Filter and Export Controls */}
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-4 mb-6 animate-slide-up" style={{ animationDelay: '150ms' }}>
          <div>
            <label htmlFor="role-filter" className="block text-sm font-semibold text-slate-700 dark:text-slate-300 mb-2">
              Filter by Role
            </label>
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                <svg className="h-5 w-5 text-slate-400 dark:text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
                </svg>
              </div>
              <select
                id="role-filter"
                value={roleFilter}
                onChange={(e) => setRoleFilter(e.target.value as 'participants' | 'facilitators')}
                className="w-full pl-10 pr-4 py-3 rounded-xl border-2 border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white font-semibold shadow-sm hover:border-vector-magenta dark:hover:border-vector-violet focus:ring-2 focus:ring-vector-magenta focus:border-vector-magenta dark:focus:ring-vector-violet dark:focus:border-vector-violet transition-all duration-200 appearance-none cursor-pointer"
                style={{
                  backgroundImage: `url("data:image/svg+xml,%3csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 20 20'%3e%3cpath stroke='%236b7280' stroke-linecap='round' stroke-linejoin='round' stroke-width='1.5' d='M6 8l4 4 4-4'/%3e%3c/svg%3e")`,
                  backgroundPosition: 'right 0.5rem center',
                  backgroundRepeat: 'no-repeat',
                  backgroundSize: '1.5em 1.5em'
                }}
              >
                <option value="participants">Participants</option>
                <option value="facilitators">Facilitators</option>
              </select>
            </div>
          </div>

          <div>
            <label htmlFor="bootcamp-filter" className="block text-sm font-semibold text-slate-700 dark:text-slate-300 mb-2">
              Filter by Bootcamp
            </label>
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                <svg className="h-5 w-5 text-slate-400 dark:text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
                </svg>
              </div>
              <select
                id="bootcamp-filter"
                value={bootcampFilter}
                onChange={(e) => setBootcampFilter(e.target.value)}
                className="w-full pl-10 pr-4 py-3 rounded-xl border-2 border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white font-semibold shadow-sm hover:border-vector-magenta dark:hover:border-vector-violet focus:ring-2 focus:ring-vector-magenta focus:border-vector-magenta dark:focus:ring-vector-violet dark:focus:border-vector-violet transition-all duration-200 appearance-none cursor-pointer"
                style={{
                  backgroundImage: `url("data:image/svg+xml,%3csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 20 20'%3e%3cpath stroke='%236b7280' stroke-linecap='round' stroke-linejoin='round' stroke-width='1.5' d='M6 8l4 4 4-4'/%3e%3c/svg%3e")`,
                  backgroundPosition: 'right 0.5rem center',
                  backgroundRepeat: 'no-repeat',
                  backgroundSize: '1.5em 1.5em'
                }}
              >
                <option value="all">All Bootcamps</option>
                {bootcampNames.map((bootcamp) => (
                  <option key={bootcamp} value={bootcamp}>
                    {bootcamp}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <label htmlFor="status-filter" className="block text-sm font-semibold text-slate-700 dark:text-slate-300 mb-2">
              Filter by Status
            </label>
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                <svg className="h-5 w-5 text-slate-400 dark:text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z" />
                </svg>
              </div>
              <select
                id="status-filter"
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value as 'all' | 'onboarded' | 'not_onboarded')}
                className="w-full pl-10 pr-4 py-3 rounded-xl border-2 border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white font-semibold shadow-sm hover:border-vector-magenta dark:hover:border-vector-violet focus:ring-2 focus:ring-vector-magenta focus:border-vector-magenta dark:focus:ring-vector-violet dark:focus:border-vector-violet transition-all duration-200 appearance-none cursor-pointer"
                style={{
                  backgroundImage: `url("data:image/svg+xml,%3csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 20 20'%3e%3cpath stroke='%236b7280' stroke-linecap='round' stroke-linejoin='round' stroke-width='1.5' d='M6 8l4 4 4-4'/%3e%3c/svg%3e")`,
                  backgroundPosition: 'right 0.5rem center',
                  backgroundRepeat: 'no-repeat',
                  backgroundSize: '1.5em 1.5em'
                }}
              >
                <option value="all">All Participants ({participants.length})</option>
                <option value="onboarded">Onboarded ({summary.onboarded})</option>
                <option value="not_onboarded">Not Onboarded ({summary.notOnboarded})</option>
              </select>
            </div>
          </div>

          <div className="flex items-end">
            <button
              onClick={exportToCSV}
              className="group relative inline-flex items-center justify-center w-full px-6 py-3 rounded-xl bg-gradient-to-r from-vector-magenta via-vector-violet to-vector-cobalt hover:from-vector-violet hover:via-vector-cobalt hover:to-vector-turquoise text-white font-bold shadow-lg shadow-vector-magenta/30 hover:shadow-xl hover:shadow-vector-violet/40 transform hover:-translate-y-0.5 active:translate-y-0 transition-all duration-200"
            >
              <svg className="w-5 h-5 mr-2 transition-transform group-hover:translate-y-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M9 19l3 3m0 0l3-3m-3 3V10" />
              </svg>
              <span>Export CSV</span>
              <span className="ml-2 px-2 py-0.5 bg-white/20 rounded-md text-sm font-bold">
                {filteredParticipants.length}
              </span>
            </button>
          </div>
        </div>

        {/* Participants Table */}
        <div className="card overflow-hidden animate-slide-up" style={{ animationDelay: '200ms' }}>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-slate-100 dark:bg-slate-800 border-b-2 border-vector-magenta/20 dark:border-vector-violet/30">
                <tr>
                  <th className="px-6 py-4 text-left text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                    #
                  </th>
                  <th className="px-6 py-4 text-left text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                    Name
                  </th>
                  <th className="px-6 py-4 text-left text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                    GitHub Handle
                  </th>
                  <th className="px-6 py-4 text-center text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                    GitHub Invite
                  </th>
                  <th className="px-6 py-4 text-left text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                    Team Name
                  </th>
                  <th className="px-6 py-4 text-center text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                    Status
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200 dark:divide-slate-700">
                {filteredParticipants.map((participant, index) => (
                  <tr
                    key={participant.github_handle}
                    className="hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors"
                  >
                    <td className="px-6 py-4 text-sm text-slate-500 dark:text-slate-400">
                      {index + 1}
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center">
                        <span className="text-sm font-medium text-slate-900 dark:text-white">
                          {participant.first_name && participant.last_name
                            ? `${participant.first_name} ${participant.last_name}`
                            : participant.first_name || participant.last_name || 'N/A'}
                        </span>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <span className="text-sm text-slate-600 dark:text-slate-400">
                        {participant.github_handle}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-center">
                      {renderGitHubStatus(participant.github_status)}
                    </td>
                    <td className="px-6 py-4">
                      <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-slate-100 text-slate-700 dark:bg-slate-700 dark:text-slate-200 border border-slate-300 dark:border-slate-600">
                        {participant.team_name}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-center">
                      {participant.onboarded ? (
                        <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-vector-turquoise/10 text-vector-turquoise dark:bg-vector-turquoise/20 dark:text-vector-turquoise border border-vector-turquoise/30">
                          <svg className="w-4 h-4 mr-1" fill="currentColor" viewBox="0 0 20 20">
                            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                          </svg>
                          Onboarded
                        </span>
                      ) : (
                        <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-vector-tangerine/10 text-vector-tangerine dark:bg-vector-tangerine/20 dark:text-vector-tangerine border border-vector-tangerine/30">
                          <svg className="w-4 h-4 mr-1" fill="currentColor" viewBox="0 0 20 20">
                            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                          </svg>
                          Not Onboarded
                        </span>
                      )}
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

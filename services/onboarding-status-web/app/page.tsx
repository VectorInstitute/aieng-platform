'use client';

import { useEffect, useState } from 'react';

interface Participant {
  github_handle: string;
  team_name: string;
  onboarded: boolean;
  onboarded_at?: string;
  first_name?: string;
  last_name?: string;
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

export default function Home() {
  const [data, setData] = useState<ApiResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [statusFilter, setStatusFilter] = useState<'all' | 'onboarded' | 'not_onboarded'>('all');
  const [roleFilter, setRoleFilter] = useState<'participants' | 'facilitators'>('participants');

  const fetchData = async () => {
    try {
      setError(null);
      const response = await fetch(`/onboarding/api/participants?role=${roleFilter}`, {
        cache: 'no-store'
      });

      if (!response.ok) {
        throw new Error(`Failed to fetch: ${response.statusText}`);
      }

      const result = await response.json();
      setData(result);
      setLastUpdated(new Date());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch data');
      console.error('Error fetching participants:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();

    // Auto-refresh every 30 seconds
    const interval = setInterval(fetchData, 30000);

    return () => clearInterval(interval);
  }, [roleFilter]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-900 dark:to-slate-800">
        <div className="text-center">
          <div className="inline-block h-12 w-12 animate-spin rounded-full border-4 border-solid border-blue-600 border-r-transparent"></div>
          <p className="mt-4 text-slate-600 dark:text-slate-400">Loading participant data...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-900 dark:to-slate-800 p-4">
        <div className="card p-8 max-w-md w-full text-center">
          <div className="text-red-500 text-5xl mb-4">⚠️</div>
          <h2 className="text-2xl font-bold text-slate-900 dark:text-white mb-2">Error</h2>
          <p className="text-slate-600 dark:text-slate-400 mb-4">{error}</p>
          <button
            onClick={fetchData}
            className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
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

  // Filter participants based on status
  const filteredParticipants = participants.filter((participant) => {
    if (statusFilter === 'onboarded') return participant.onboarded;
    if (statusFilter === 'not_onboarded') return !participant.onboarded;
    return true; // 'all'
  });

  // CSV export function
  const exportToCSV = () => {
    const headers = ['#', 'Name', 'GitHub Handle', 'Team Name', 'Status', 'Onboarded At'];
    const rows = filteredParticipants.map((participant, index) => {
      const name = participant.first_name && participant.last_name
        ? `${participant.first_name} ${participant.last_name}`
        : participant.first_name || participant.last_name || 'N/A';
      const status = participant.onboarded ? 'Onboarded' : 'Not Onboarded';
      const onboardedAt = participant.onboarded_at || 'N/A';

      return [
        index + 1,
        name,
        participant.github_handle,
        participant.team_name,
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
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-900 dark:to-slate-800 p-4 md:p-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8 animate-fade-in">
          <h1 className="text-4xl md:text-5xl font-bold text-slate-900 dark:text-white mb-2">
            Onboarding Status
          </h1>
          <p className="text-slate-600 dark:text-slate-400">
            Track technical onboarding progress in real-time
          </p>
          {lastUpdated && (
            <p className="text-sm text-slate-500 dark:text-slate-500 mt-2">
              Last updated: {lastUpdated.toLocaleTimeString()}
            </p>
          )}
        </div>

        {/* Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8 animate-slide-up">
          <div className="card p-6">
            <div className="text-sm font-medium text-slate-600 dark:text-slate-400 mb-1">
              Total Participants
            </div>
            <div className="text-3xl font-bold text-slate-900 dark:text-white">
              {summary.total}
            </div>
          </div>

          <div className="card p-6 border-l-4 border-green-500">
            <div className="text-sm font-medium text-slate-600 dark:text-slate-400 mb-1">
              Onboarded
            </div>
            <div className="text-3xl font-bold text-green-600 dark:text-green-400">
              {summary.onboarded}
            </div>
          </div>

          <div className="card p-6 border-l-4 border-red-500">
            <div className="text-sm font-medium text-slate-600 dark:text-slate-400 mb-1">
              Not Onboarded
            </div>
            <div className="text-3xl font-bold text-red-600 dark:text-red-400">
              {summary.notOnboarded}
            </div>
          </div>

          <div className="card p-6 border-l-4 border-blue-500">
            <div className="text-sm font-medium text-slate-600 dark:text-slate-400 mb-1">
              Completion Rate
            </div>
            <div className="text-3xl font-bold text-blue-600 dark:text-blue-400">
              {summary.percentage}%
            </div>
          </div>
        </div>

        {/* Progress Bar */}
        <div className="card p-6 mb-8 animate-slide-up" style={{ animationDelay: '100ms' }}>
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-slate-700 dark:text-slate-300">
              Overall Progress
            </span>
            <span className="text-sm font-medium text-slate-700 dark:text-slate-300">
              {summary.onboarded} of {summary.total}
            </span>
          </div>
          <div className="w-full bg-slate-200 dark:bg-slate-700 rounded-full h-4 overflow-hidden">
            <div
              className="bg-gradient-to-r from-green-500 to-green-600 h-4 rounded-full transition-all duration-1000 ease-out"
              style={{ width: `${summary.percentage}%` }}
            ></div>
          </div>
        </div>

        {/* Filter and Export Controls */}
        <div className="flex flex-col sm:flex-row gap-4 mb-6 animate-slide-up" style={{ animationDelay: '150ms' }}>
          <div className="flex-1">
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
                className="w-full sm:w-72 pl-10 pr-4 py-3 rounded-xl border-2 border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white font-medium shadow-sm hover:border-slate-300 dark:hover:border-slate-600 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 dark:focus:ring-blue-400 dark:focus:border-blue-400 transition-all duration-200 appearance-none cursor-pointer"
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

          <div className="flex-1">
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
                className="w-full sm:w-72 pl-10 pr-4 py-3 rounded-xl border-2 border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white font-medium shadow-sm hover:border-slate-300 dark:hover:border-slate-600 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 dark:focus:ring-blue-400 dark:focus:border-blue-400 transition-all duration-200 appearance-none cursor-pointer"
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
              className="group relative inline-flex items-center px-6 py-3 rounded-xl bg-gradient-to-r from-emerald-600 via-emerald-600 to-teal-600 hover:from-emerald-700 hover:via-emerald-700 hover:to-teal-700 text-white font-semibold shadow-lg shadow-emerald-500/30 hover:shadow-xl hover:shadow-emerald-500/40 transform hover:-translate-y-0.5 active:translate-y-0 transition-all duration-200"
            >
              <svg className="w-5 h-5 mr-2 transition-transform group-hover:translate-y-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M9 19l3 3m0 0l3-3m-3 3V10" />
              </svg>
              <span>Export to CSV</span>
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
              <thead className="bg-slate-50 dark:bg-slate-800 border-b border-slate-200 dark:border-slate-700">
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
                    <td className="px-6 py-4">
                      <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300">
                        {participant.team_name}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-center">
                      {participant.onboarded ? (
                        <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300">
                          <svg className="w-4 h-4 mr-1" fill="currentColor" viewBox="0 0 20 20">
                            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                          </svg>
                          Onboarded
                        </span>
                      ) : (
                        <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300">
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
  );
}

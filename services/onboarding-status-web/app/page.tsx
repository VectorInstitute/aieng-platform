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

  const fetchData = async () => {
    try {
      setError(null);
      const response = await fetch('/api/participants', {
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
  }, []);

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

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-900 dark:to-slate-800 p-4 md:p-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8 animate-fade-in">
          <h1 className="text-4xl md:text-5xl font-bold text-slate-900 dark:text-white mb-2">
            Participant Onboarding Status
          </h1>
          <p className="text-slate-600 dark:text-slate-400">
            Track participant onboarding progress in real-time
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
                {participants.map((participant, index) => (
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

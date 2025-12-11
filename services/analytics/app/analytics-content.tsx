'use client';

import type { User } from '@vector-institute/aieng-auth-core';
import { useAnalyticsData } from './hooks/use-analytics-data';
import { PageHeader } from './components/page-header';
import { LoadingState } from './components/loading-state';
import { ErrorState } from './components/error-state';
import { TemplatesTable } from './components/templates-table';
import { EngagementChart } from './components/engagement-chart';

interface AnalyticsContentProps {
  user: User | null;
}

async function handleLogout() {
  try {
    await fetch('/analytics/api/auth/logout', { method: 'POST' });
    window.location.href = '/analytics/login';
  } catch (error) {
    console.error('Logout failed:', error);
  }
}

export default function AnalyticsContent({ user }: AnalyticsContentProps) {
  const { data, loading, error, lastUpdated, refetch } = useAnalyticsData();

  if (loading && !data) {
    return <LoadingState />;
  }

  if (error && !data) {
    return <ErrorState error={error} onRetry={refetch} />;
  }

  if (!data) return null;

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-900 dark:to-slate-800">
      <PageHeader user={user} onLogout={handleLogout} lastUpdated={lastUpdated} />

      <div className="max-w-7xl mx-auto px-4 md:px-8 pb-8">
        <div className="mb-8 animate-slide-up">
          <TemplatesTable templates={data.template_metrics} />
        </div>

        <div className="animate-slide-up" style={{ animationDelay: '100ms' }}>
          <EngagementChart data={data.daily_engagement} />
        </div>
      </div>
    </div>
  );
}

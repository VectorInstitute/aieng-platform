'use client';

interface DashboardHeaderProps {
  lastUpdated?: Date | null;
}

export default function DashboardHeader({ lastUpdated }: DashboardHeaderProps) {
  return (
    <div>
      <h1 className="text-2xl md:text-3xl font-bold text-slate-900 dark:text-white">
        AI Engineering Platform
      </h1>
      <div className="flex items-center gap-2">
        <p className="text-base text-slate-600 dark:text-slate-400">
          Onboarding Status
        </p>
        {lastUpdated && (
          <>
            <span className="text-slate-400 dark:text-slate-600">•</span>
            <p className="text-sm text-slate-500 dark:text-slate-500">
              {lastUpdated.toLocaleTimeString()}
            </p>
          </>
        )}
      </div>
    </div>
  );
}

interface ErrorStateProps {
  error: string;
  onRetry: () => void;
}

export function ErrorState({ error, onRetry }: ErrorStateProps) {
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-900 dark:to-slate-800 flex items-center justify-center p-4">
      <div className="card p-8 max-w-md w-full text-center">
        <div className="text-vector-magenta text-5xl mb-4">⚠️</div>
        <h2 className="text-2xl font-bold text-slate-900 dark:text-white mb-2">Error</h2>
        <p className="text-slate-600 dark:text-slate-400 mb-4">{error}</p>
        <button
          onClick={onRetry}
          className="px-6 py-2 text-sm font-semibold text-white bg-gradient-to-r from-slate-600 to-slate-700 hover:from-vector-magenta hover:to-vector-violet rounded-lg shadow-sm hover:shadow-md transition-all duration-200"
        >
          Retry
        </button>
      </div>
    </div>
  );
}

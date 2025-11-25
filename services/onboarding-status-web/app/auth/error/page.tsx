'use client';

import { useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { Suspense } from 'react';

function AuthErrorContent() {
  const searchParams = useSearchParams();
  const error = searchParams.get('error');

  const getErrorMessage = () => {
    switch (error) {
      case 'AccessDenied':
        return {
          title: 'Access Denied',
          description:
            'You are not a member of the AI-Engineering-Platform organization. Please contact your administrator if you believe this is an error.',
        };
      case 'Configuration':
        return {
          title: 'Configuration Error',
          description:
            'There is a problem with the server configuration. Please contact your administrator.',
        };
      case 'Verification':
        return {
          title: 'Verification Failed',
          description:
            'The verification token has expired or has already been used. Please try signing in again.',
        };
      default:
        return {
          title: 'Authentication Error',
          description:
            'An error occurred during authentication. Please try again.',
        };
    }
  };

  const { title, description } = getErrorMessage();

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-900 dark:to-slate-800">
      <div className="card p-8 max-w-md w-full text-center">
        <div className="mb-6">
          <div className="text-6xl mb-4">❌</div>
          <h1 className="text-3xl font-bold text-slate-900 dark:text-white mb-2">
            {title}
          </h1>
          <p className="text-slate-600 dark:text-slate-400">{description}</p>
        </div>

        {error === 'AccessDenied' && (
          <div className="mb-6 p-4 bg-amber-50 dark:bg-amber-900/20 rounded-lg border border-amber-200 dark:border-amber-800">
            <p className="text-sm text-amber-800 dark:text-amber-300">
              <strong>Organization Required:</strong> This application is only
              accessible to members of the{' '}
              <a
                href="https://github.com/AI-Engineering-Platform"
                target="_blank"
                rel="noopener noreferrer"
                className="underline hover:text-amber-900 dark:hover:text-amber-200"
              >
                AI-Engineering-Platform
              </a>{' '}
              organization on GitHub.
            </p>
          </div>
        )}

        <Link
          href="/onboarding/auth/signin"
          className="inline-flex items-center px-6 py-3 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-semibold shadow-lg transition-all duration-200"
        >
          <svg
            className="w-5 h-5 mr-2"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M10 19l-7-7m0 0l7-7m-7 7h18"
            />
          </svg>
          Try Again
        </Link>
      </div>
    </div>
  );
}

export default function AuthError() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-900 dark:to-slate-800">
          <div className="text-center">
            <div className="inline-block h-12 w-12 animate-spin rounded-full border-4 border-solid border-blue-600 border-r-transparent"></div>
            <p className="mt-4 text-slate-600 dark:text-slate-400">Loading...</p>
          </div>
        </div>
      }
    >
      <AuthErrorContent />
    </Suspense>
  );
}

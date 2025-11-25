'use client';

import { signOut, useSession } from 'next-auth/react';
import Image from 'next/image';

export default function AuthButton() {
  const { data: session } = useSession();

  if (!session) {
    return null;
  }

  return (
    <div className="flex items-center gap-4">
      <div className="flex items-center gap-3 px-4 py-2 bg-slate-100 dark:bg-slate-800 rounded-lg">
        {session.user?.image && (
          <Image
            src={session.user.image}
            alt={session.user.name || 'User'}
            width={32}
            height={32}
            className="rounded-full"
          />
        )}
        <div className="text-sm">
          <p className="font-medium text-slate-900 dark:text-white">
            {session.user?.name || session.user?.login}
          </p>
          <p className="text-slate-600 dark:text-slate-400">
            @{session.user?.login}
          </p>
        </div>
      </div>
      <button
        onClick={() => signOut({ callbackUrl: '/onboarding/auth/signin' })}
        className="px-4 py-2 rounded-lg bg-red-600 hover:bg-red-700 text-white font-medium transition-colors duration-200"
      >
        Sign Out
      </button>
    </div>
  );
}

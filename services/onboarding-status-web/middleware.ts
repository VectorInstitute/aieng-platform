import { auth } from '@/lib/auth';
import { NextResponse } from 'next/server';

export default auth((req) => {
  const isAuthenticated = !!req.auth;
  const isAuthPage = req.nextUrl.pathname.startsWith('/auth');

  // If not authenticated and not on auth page, redirect to signin
  if (!isAuthenticated && !isAuthPage) {
    const signInUrl = new URL('/onboarding/auth/signin', req.nextUrl.origin);
    signInUrl.searchParams.set('callbackUrl', req.url);
    return NextResponse.redirect(signInUrl);
  }

  return NextResponse.next();
});

export const config = {
  matcher: [
    // Match all routes except the ones specified
    '/',
    '/((?!api/auth|_next/static|_next/image|favicon.ico|auth).*)',
  ],
};

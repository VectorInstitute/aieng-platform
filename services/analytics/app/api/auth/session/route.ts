import { NextResponse } from 'next/server';
import { getSession } from '@/lib/session';

export const dynamic = 'force-dynamic';

export async function GET() {
  try {
    const session = await getSession();

    return NextResponse.json({
      isAuthenticated: session.isAuthenticated || false,
      user: session.user || null,
    });
  } catch (error) {
    console.error('Session error:', error);
    return NextResponse.json({
      isAuthenticated: false,
      user: null,
    });
  }
}

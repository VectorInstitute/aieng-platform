import { DefaultSession } from 'next-auth';

declare module 'next-auth' {
  interface Session {
    accessToken?: string;
    user: {
      login?: string;
    } & DefaultSession['user'];
  }

  interface Profile {
    login?: string;
  }
}

declare module '@auth/core/jwt' {
  interface JWT {
    accessToken?: string;
    login?: string;
  }
}

import NextAuth from 'next-auth';
import GitHub from 'next-auth/providers/github';

const GITHUB_ORG = 'AI-Engineering-Platform';

export const { handlers, signIn, signOut, auth } = NextAuth({
  basePath: '/onboarding/api/auth',
  trustHost: true,
  providers: [
    GitHub({
      clientId: process.env.GITHUB_CLIENT_ID!,
      clientSecret: process.env.GITHUB_CLIENT_SECRET!,
      authorization: {
        params: {
          scope: 'read:user read:org',
        },
      },
    }),
  ],
  callbacks: {
    async signIn({ account, profile }) {
      if (account?.provider === 'github' && account.access_token) {
        try {
          // Check if user is a member of the organization
          const response = await fetch(
            `https://api.github.com/orgs/${GITHUB_ORG}/members/${profile?.login}`,
            {
              headers: {
                Authorization: `Bearer ${account.access_token}`,
                Accept: 'application/vnd.github+json',
              },
            }
          );

          // If the request returns 204, the user is a member
          if (response.status === 204) {
            return true;
          }

          // User is not a member
          console.log(`User ${profile?.login} is not a member of ${GITHUB_ORG}`);
          return false;
        } catch (error) {
          console.error('Error checking organization membership:', error);
          return false;
        }
      }
      return false;
    },
    async jwt({ token, account, profile }) {
      // Persist the OAuth access_token and user profile to the token right after signin
      if (account) {
        token.accessToken = account.access_token;
        token.login = profile?.login;
      }
      return token;
    },
    async session({ session, token }) {
      // Send properties to the client
      session.accessToken = token.accessToken;
      if (session.user) {
        session.user.login = token.login;
      }
      return session;
    },
  },
  pages: {
    signIn: '/auth/signin',
    error: '/auth/error',
  },
  session: {
    strategy: 'jwt',
  },
});

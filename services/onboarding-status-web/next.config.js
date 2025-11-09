/** @type {import('next').NextConfig} */
const nextConfig = {
  basePath: '/onboarding',
  output: 'standalone',
  eslint: {
    ignoreDuringBuilds: true,
  },
  typescript: {
    ignoreBuildErrors: false,
  },
}

module.exports = nextConfig

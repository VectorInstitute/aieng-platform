/** @type {import('next').NextConfig} */
const nextConfig = {
  basePath: '/analytics',
  output: 'standalone',
  eslint: {
    ignoreDuringBuilds: true,
  },
  typescript: {
    ignoreBuildErrors: false,
  },
}

module.exports = nextConfig

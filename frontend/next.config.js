/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Proxy /api/v1 requests to backend
  //
  // Configuration options:
  //   BACKEND_URL=https://xxx.onrender.com    → proxies /api/v1/* to backend
  //   NEXT_PUBLIC_API_URL=https://xxx/api/v1  → also used as rewrite source
  //
  // On Vercel, set BACKEND_URL in project settings.
  // On the frontend, set NEXT_PUBLIC_USE_API=true to use the proxy.
  async rewrites() {
    const backendUrl = process.env.BACKEND_URL
      || (process.env.NEXT_PUBLIC_API_URL || '').replace(/\/api\/v1\/?$/, '')
    if (backendUrl) {
      return [
        {
          source: '/api/v1/:path*',
          destination: `${backendUrl}/api/v1/:path*`,
        },
      ]
    }
    return []
  },
}
module.exports = nextConfig

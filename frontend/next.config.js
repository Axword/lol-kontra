const configuredApiUrl = process.env.NEXT_PUBLIC_API_URL
const vercelDeployment = process.env.VERCEL_ENV !== 'development' && (
  process.env.VERCEL === '1' || ['production', 'preview'].includes(process.env.VERCEL_ENV)
)

if (vercelDeployment) {
  const message = 'Vercel requires NEXT_PUBLIC_API_URL pointing to a separate public HTTPS Django API (including /api/v1), without credentials, query or fragment. Set it in the Vercel Production/Preview environment before rebuilding.'
  let api
  try {
    api = new URL(configuredApiUrl)
  } catch {
    throw new Error(message)
  }
  const normalizeHost = host => host.toLowerCase().replace(/\.$/, '')
  const host = normalizeHost(api.hostname)
  const local = host === 'localhost' || host.endsWith('.localhost') || /^127\./.test(host)
    || ['0.0.0.0', '[::]', '[::1]'].includes(host) || /^\[::ffff:7f[0-9a-f]{2}:[0-9a-f]{1,4}\]$/.test(host)
  const frontendHosts = [
    process.env.VERCEL_URL, process.env.VERCEL_BRANCH_URL,
    process.env.VERCEL_PROJECT_PRODUCTION_URL, process.env.NEXT_PUBLIC_APP_URL,
  ].filter(Boolean).map(value => {
    try {
      return normalizeHost(new URL(value.includes('://') ? value : `https://${value}`).hostname)
    } catch {
      return ''
    }
  })
  if (api.protocol !== 'https:' || !/^https:\/\//i.test(configuredApiUrl)
    || /\s/.test(configuredApiUrl) || api.username || api.password
    || configuredApiUrl.includes('?') || configuredApiUrl.includes('#')
    || local || frontendHosts.includes(host)) {
    // Never echo the URL: a mistaken value may contain credentials or tokens.
    throw new Error(message)
  }
}

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: 'standalone',
  experimental: {
    // 
  },
  env: {
    NEXT_PUBLIC_API_URL: configuredApiUrl || 'http://localhost:8000/api/v1',
  },
}
module.exports = nextConfig

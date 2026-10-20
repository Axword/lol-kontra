import { NextRequest, NextResponse } from 'next/server'
import { GAME_ORIGIN, LEGACY_ORIGIN, MIGRATED_COOKIE, safeMigrationPath } from './lib/domain-migration'

export function middleware(request: NextRequest) {
  const host = request.headers.get('host')?.split(':')[0].toLowerCase()
  if (host !== new URL(LEGACY_ORIGIN).hostname) return NextResponse.next()
  const path = request.nextUrl.pathname
  if (path.startsWith('/_next/') || path === '/legacy-migration' || path === '/migration/complete') return NextResponse.next()
  const next = safeMigrationPath(path + request.nextUrl.search)
  if (request.cookies.get(MIGRATED_COOKIE)?.value === '1' || path.startsWith('/api/') || /\.[a-z0-9]+$/iu.test(path)) {
    return NextResponse.redirect(new URL(next, GAME_ORIGIN), 308)
  }
  if (request.method !== 'GET' && request.method !== 'HEAD') return NextResponse.next()
  const bridge = request.nextUrl.clone()
  bridge.pathname = '/legacy-migration'
  bridge.search = ''
  bridge.searchParams.set('next', next)
  const response = NextResponse.rewrite(bridge)
  response.headers.set('Cache-Control', 'private, no-store')
  return response
}

export const config = { matcher: '/:path*' }

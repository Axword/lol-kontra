import { NextRequest, NextResponse } from 'next/server'
import { GAME_ORIGIN, LEGACY_ORIGIN, MIGRATED_COOKIE, safeMigrationPath } from '@/lib/domain-migration'

export function GET(request: NextRequest) {
  const response = NextResponse.redirect(new URL(safeMigrationPath(request.nextUrl.searchParams.get('next')), GAME_ORIGIN), 308)
  if (request.headers.get('host') === new URL(LEGACY_ORIGIN).host) {
    response.cookies.set(MIGRATED_COOKIE, '1', { httpOnly: true, secure: true, sameSite: 'lax', path: '/', maxAge: 31536000 })
  }
  response.headers.set('Cache-Control', 'private, no-store')
  return response
}

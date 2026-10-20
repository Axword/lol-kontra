import { NextRequest, NextResponse } from 'next/server'
import { GAME_ORIGIN, TRANSFER_COOKIE, parseMigrationSession } from '@/lib/domain-migration'

export async function POST(request: NextRequest) {
  if (request.headers.get('origin') !== GAME_ORIGIN || request.headers.get('host') !== new URL(GAME_ORIGIN).host) {
    return new NextResponse(null, { status: 403 })
  }
  let response: NextResponse
  try {
    const cookie = request.cookies.get(TRANSFER_COOKIE)?.value
    if (!cookie || cookie.length > 4096) throw new Error('missing_migration')
    const session = parseMigrationSession(JSON.parse(Buffer.from(cookie, 'base64url').toString('utf8')))
    response = NextResponse.json(session)
  } catch { response = NextResponse.json({ error: 'migration_expired' }, { status: 410 }) }
  response.cookies.set(TRANSFER_COOKIE, '', { httpOnly: true, secure: true, sameSite: 'lax', path: '/', maxAge: 0 })
  response.headers.set('Cache-Control', 'private, no-store')
  response.headers.set('Referrer-Policy', 'no-referrer')
  return response
}

import { NextRequest, NextResponse } from 'next/server'
import { GAME_ORIGIN, LEGACY_ORIGIN, TRANSFER_COOKIE, safeMigrationPath } from '@/lib/domain-migration'
import { validToken } from '@/lib/profile-access'

export async function POST(request: NextRequest) {
  if (request.headers.get('origin') !== LEGACY_ORIGIN || request.headers.get('host') !== new URL(GAME_ORIGIN).host) {
    return new NextResponse(null, { status: 403 })
  }
  if (!request.headers.get('content-type')?.startsWith('application/x-www-form-urlencoded')
      || Number(request.headers.get('content-length') || 0) > 4096) return new NextResponse(null, { status: 400 })
  const body = await request.text()
  if (body.length > 4096) return new NextResponse(null, { status: 400 })
  const form = new URLSearchParams(body)
  const token = form.get('guest_token')
  if (!validToken(token) || form.getAll('guest_token').length !== 1) return new NextResponse(null, { status: 400 })
  const response = NextResponse.redirect(`${GAME_ORIGIN}/migration`, 303)
  response.cookies.set(TRANSFER_COOKIE, Buffer.from(JSON.stringify({ guestToken: token, next: safeMigrationPath(form.get('next')) })).toString('base64url'), {
    httpOnly: true, secure: true, sameSite: 'lax', path: '/', maxAge: 300,
  })
  response.headers.set('Cache-Control', 'private, no-store')
  response.headers.set('Referrer-Policy', 'no-referrer')
  return response
}

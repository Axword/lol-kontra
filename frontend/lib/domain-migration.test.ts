// @vitest-environment node
import { describe, expect, it } from 'vitest'
import { NextRequest } from 'next/server'
import { POST as receive } from '@/app/profile-transfer/route'
import { POST as consume } from '@/app/profile-transfer/session/route'
import { GET as complete } from '@/app/migration/complete/route'
import { middleware } from '@/middleware'
import { GAME_ORIGIN, LEGACY_ORIGIN, MIGRATED_COOKIE, TRANSFER_COOKIE, readStoredProfile, safeMigrationPath } from './domain-migration'

const token = 'private-migration-test-token'
function request(origin: string, path: string, init: NonNullable<ConstructorParameters<typeof NextRequest>[1]> = {}) {
  const headers = new Headers(init.headers)
  if (!headers.has('host')) headers.set('host', new URL(origin).host)
  return new NextRequest(origin + path, { ...init, headers })
}
const form = (extra = {}) => request(GAME_ORIGIN, '/profile-transfer', { method: 'POST',
  headers: { origin: LEGACY_ORIGIN, 'content-type': 'application/x-www-form-urlencoded', ...extra },
  body: new URLSearchParams({ guest_token: token, next: '/daily/20?from=old' }).toString() })

describe('profile-preserving domain migration', () => {
  it('keeps paths and ordinary query parameters but never redirects credentials or external URLs', () => {
    expect(safeMigrationPath('/daily/20?from=old')).toBe('/daily/20?from=old')
    expect(safeMigrationPath('/profile?guest_token=secret&from=old')).toBe('/profile?from=old')
    for (const value of ['//attacker.test', '/\\attacker.test', 'https://attacker.test', '/profile-transfer', '/migration/complete', '/\n']) {
      expect(safeMigrationPath(value)).toBe('/')
    }
  })
  it('reads the existing old identity without creating or changing one', () => {
    const storage = { getItem: () => JSON.stringify({ state: { guestToken: token } }) }
    expect(readStoredProfile(storage)).toBe(token)
    expect(readStoredProfile({ getItem: () => null })).toBeNull()
    expect(readStoredProfile({ getItem: () => '{' })).toBeNull()
    expect(() => readStoredProfile({ getItem: () => { throw new Error('blocked') } })).toThrow('blocked')
  })
  it('hands off through a top-level POST and a short-lived private cookie, never a URL token', async () => {
    const response = await receive(form())
    expect(response.status).toBe(303)
    expect(response.headers.get('location')).toBe(`${GAME_ORIGIN}/migration`)
    expect(response.headers.get('location')).not.toContain(token)
    expect(response.headers.get('set-cookie')).toMatch(/HttpOnly/u)
    expect(response.headers.get('set-cookie')).toMatch(/Secure/u)
    expect(response.headers.get('set-cookie')).toMatch(/SameSite=lax/iu)
    expect(response.headers.get('set-cookie')).toMatch(/Max-Age=300/u)
    const cookie = response.cookies.get(TRANSFER_COOKIE)!
    const result = await consume(request(GAME_ORIGIN, '/profile-transfer/session', { method: 'POST',
      headers: { origin: GAME_ORIGIN, cookie: `${TRANSFER_COOKIE}=${cookie.value}` } }))
    expect(await result.json()).toEqual({ guestToken: token, next: '/daily/20?from=old' })
    expect(result.headers.get('cache-control')).toBe('private, no-store')
    expect(result.headers.get('set-cookie')).toMatch(/Max-Age=0/u)
  })
  it('rejects other origins, malformed input and missing handoffs without echoing secrets', async () => {
    expect((await receive(form({ origin: 'https://attacker.test' }))).status).toBe(403)
    expect((await receive(form({ host: new URL(LEGACY_ORIGIN).host }))).status).toBe(403)
    expect((await receive(form({ 'content-length': '9000' }))).status).toBe(400)
    const response = await consume(request(GAME_ORIGIN, '/profile-transfer/session', { method: 'POST', headers: { origin: GAME_ORIGIN } }))
    expect(response.status).toBe(410)
    expect(await response.text()).not.toContain(token)
    expect((await consume(request(GAME_ORIGIN, '/profile-transfer/session', { method: 'POST', headers: { origin: LEGACY_ORIGIN } }))).status).toBe(403)
  })
  it('bridges old profiles first and permanently redirects subsequent visits without affecting OVH or previews', () => {
    const first = middleware(request(LEGACY_ORIGIN, '/daily/20?from=old'))
    const rewrite = new URL(first.headers.get('x-middleware-rewrite')!)
    expect(rewrite.pathname).toBe('/legacy-migration')
    expect(rewrite.searchParams.get('next')).toBe('/daily/20?from=old')
    const migrated = middleware(request(LEGACY_ORIGIN, '/daily/20?from=old', { headers: { cookie: `${MIGRATED_COOKIE}=1` } }))
    expect(migrated.status).toBe(308)
    expect(migrated.headers.get('location')).toBe(`${GAME_ORIGIN}/daily/20?from=old`)
    for (const origin of [GAME_ORIGIN, 'https://preview.vercel.app', 'https://lol-kontra.vercel.app.attacker.test']) {
      expect(middleware(request(origin, '/')).headers.get('x-middleware-next')).toBe('1')
    }
    for (const path of ['/_next/static/chunk.js', '/legacy-migration', '/migration/complete']) {
      expect(middleware(request(LEGACY_ORIGIN, path)).headers.get('x-middleware-next')).toBe('1')
    }
  })
  it('records completion only on the old host and keeps an explicit recovery route available', () => {
    const response = complete(request(LEGACY_ORIGIN, '/migration/complete?next=%2Fprofile'))
    expect(response.status).toBe(308)
    expect(response.headers.get('location')).toBe(`${GAME_ORIGIN}/profile`)
    expect(response.cookies.get(MIGRATED_COOKIE)?.value).toBe('1')
    expect(complete(request(GAME_ORIGIN, '/migration/complete')).cookies.get(MIGRATED_COOKIE)).toBeUndefined()
    expect(middleware(request(LEGACY_ORIGIN, '/legacy-migration?next=/profile', { headers: { cookie: `${MIGRATED_COOKIE}=1` } })).headers.get('x-middleware-next')).toBe('1')
  })
})

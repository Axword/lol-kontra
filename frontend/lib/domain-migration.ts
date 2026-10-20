import { validToken } from './profile-access'

export const LEGACY_ORIGIN = 'https://lol-kontra.vercel.app'
export const GAME_ORIGIN = 'https://lol-kontra.axword.pl'
export const TRANSFER_COOKIE = '__Host-words-v-transfer'
export const MIGRATED_COOKIE = '__Host-words-v-migrated'

export function safeMigrationPath(value: unknown): string {
  if (typeof value !== 'string' || value.length > 2048 || !value.startsWith('/')
      || value.startsWith('//') || /[\\\r\n]/u.test(value)) return '/'
  const url = new URL(value, GAME_ORIGIN)
  if (url.origin !== GAME_ORIGIN || /^\/(migration|profile-transfer|legacy-migration)(\/|$)/u.test(url.pathname)) return '/'
  // Old bookmarks must not put bearer credentials into navigation or analytics.
  for (const key of [...url.searchParams.keys()]) {
    if (/token|credential|access/iu.test(key)) url.searchParams.delete(key)
  }
  return url.pathname + url.search
}

export function readStoredProfile(storage: Pick<Storage, 'getItem'>): string | null {
  const raw = storage.getItem('worldsxi-prefs')
  try {
    const token = JSON.parse(raw || 'null')?.state?.guestToken
    return validToken(token) ? token : null
  } catch { return null }
}

export function migrationCompleteUrl(next: string): string {
  return `${LEGACY_ORIGIN}/migration/complete?next=${encodeURIComponent(safeMigrationPath(next))}`
}

export type MigrationSession = { guestToken: string; next: string }
export function parseMigrationSession(value: unknown): MigrationSession {
  if (!value || typeof value !== 'object' || !validToken((value as MigrationSession).guestToken)) {
    throw new Error('invalid_migration')
  }
  return { guestToken: (value as MigrationSession).guestToken, next: safeMigrationPath((value as MigrationSession).next) }
}

const FORMAT = 'words-v-guest-access'
export const MAX_PROFILE_FILE_BYTES = 4096

export function validToken(value: unknown): value is string {
  return typeof value === 'string' && value.length >= 16 && value.length <= 64
    && value.trim() === value && /^[A-Za-z0-9_-]+$/u.test(value)
}

export function profileAccessFile(guestToken: string): string {
  if (!validToken(guestToken)) throw new Error('invalid_profile_file')
  return JSON.stringify({ format: FORMAT, version: 1, guest_token: guestToken }, null, 2)
}

export function readProfileAccessFile(text: string): string {
  if (text.length > MAX_PROFILE_FILE_BYTES) throw new Error('invalid_profile_file')
  let data: unknown
  try { data = JSON.parse(text) } catch { throw new Error('invalid_profile_file') }
  if (!data || typeof data !== 'object' || Array.isArray(data)) throw new Error('invalid_profile_file')
  const record = data as Record<string, unknown>
  if (Object.keys(record).sort().join(',') !== 'format,guest_token,version'
    || record.format !== FORMAT || record.version !== 1 || !validToken(record.guest_token)) {
    throw new Error('invalid_profile_file')
  }
  return record.guest_token
}

export function downloadProfileAccess(guestToken: string) {
  const content = profileAccessFile(guestToken)
  const url = URL.createObjectURL(new Blob([content], { type: 'application/json' }))
  const link = document.createElement('a')
  link.href = url
  link.download = 'worlds-kontra-profil.json'
  document.body.appendChild(link)
  link.click()
  link.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

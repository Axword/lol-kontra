import { describe, expect, it } from 'vitest'
import { profileAccessFile, readProfileAccessFile } from './profile-access'

const token = 'test-private-profile-123456'
describe('private profile access file', () => {
  it('round trips only a guest credential, without scores or addresses', () => {
    const text = profileAccessFile(token)
    expect(readProfileAccessFile(text)).toBe(token)
    expect(Object.keys(JSON.parse(text)).sort()).toEqual(['format', 'guest_token', 'version'])
    expect(text).not.toMatch(/https?:|nickname|score|points/u)
  })
  it.each(['null', '[]', '{}', '{', JSON.stringify({ format: 'words-v-guest-access', version: 2, guest_token: token }),
    JSON.stringify({ format: 'words-v-guest-access', version: 1, guest_token: `${token}\n` }),
    JSON.stringify({ format: 'words-v-guest-access', version: 1, guest_token: token, score: 0 }), ' '.repeat(4097)])(
    'rejects invalid or tampered files without including their contents in errors', text => {
      expect(() => readProfileAccessFile(text)).toThrow('invalid_profile_file')
    })
})

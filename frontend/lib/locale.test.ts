import { describe, expect, it } from 'vitest'
import { guestDisplayName } from './locale'

describe('guest display names', () => {
  it('translates the generated prefix without changing the nickname', () => {
    expect(guestDisplayName('Gość-Axword', 'en')).toBe('Guest-Axword')
    expect(guestDisplayName('Guest-Axword', 'pl')).toBe('Gość-Axword')
    expect(guestDisplayName('Gość-Gość fan', 'en')).toBe('Guest-Gość fan')
    expect(guestDisplayName('Axword', 'en')).toBe('Axword')
  })
})

import { beforeEach, describe, expect, it } from 'vitest'
import { usePrefs } from './store'

beforeEach(() => {
  localStorage.clear()
  usePrefs.setState({ guestToken: '', locale: 'pl', seenHelp: false })
})

describe('guest persistence', () => {
  it('creates one identity and reuses it for subsequent moves', () => {
    const first = usePrefs.getState().ensureGuestToken()
    expect(first.length).toBeGreaterThan(15)
    expect(usePrefs.getState().ensureGuestToken()).toBe(first)
    expect(JSON.parse(localStorage.getItem('worldsxi-prefs')!).state.guestToken).toBe(first)
  })
  it('keeps an existing guest identity when storage hydrates', async () => {
    localStorage.setItem('worldsxi-prefs', JSON.stringify({ state: { guestToken: 'existing-guest-identity', locale: 'en', seenHelp: true }, version: 0 }))
    await usePrefs.persist.rehydrate()
    expect(usePrefs.getState().ensureGuestToken()).toBe('existing-guest-identity')
    expect(usePrefs.getState().locale).toBe('en')
  })
  it('does not create an identity merely by opening a migration page', async () => {
    localStorage.removeItem('worldsxi-prefs')
    await usePrefs.persist.rehydrate()
    expect(usePrefs.getState().guestToken).toBe('')
    const token = usePrefs.getState().ensureGuestToken()
    expect(token.length).toBeGreaterThan(15)
  })
})

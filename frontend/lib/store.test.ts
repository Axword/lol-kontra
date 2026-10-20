import { beforeEach, describe, expect, it, vi } from 'vitest'
import { usePrefs } from './store'

beforeEach(() => {
  localStorage.clear()
  vi.spyOn(navigator, 'languages', 'get').mockReturnValue(['en-US'])
  usePrefs.setState({ guestToken: '', locale: 'en', localePreference: 'auto', seenHelp: false })
})

describe('device language', () => {
  it.each([
    [['pl-PL', 'en-US'], 'pl'], [['pl'], 'pl'], [['PL-pl'], 'pl'],
    [['en-US', 'pl-PL'], 'en'], [['de-DE', 'pl'], 'en'], [['vi-VN'], 'en'],
  ] as const)('starts with %s as %s without creating a guest', async (languages, expected) => {
    vi.spyOn(navigator, 'languages', 'get').mockReturnValue([...languages])
    localStorage.removeItem('worldsxi-prefs')
    await usePrefs.persist.rehydrate()
    expect(usePrefs.getState()).toMatchObject({ locale: expected, localePreference: 'auto', guestToken: '' })
  })

  it('falls back to navigator.language if languages is unavailable', async () => {
    vi.spyOn(navigator, 'languages', 'get').mockReturnValue([])
    vi.spyOn(navigator, 'language', 'get').mockReturnValue('pl-PL')
    localStorage.removeItem('worldsxi-prefs')
    await usePrefs.persist.rehydrate()
    expect(usePrefs.getState().locale).toBe('pl')
  })

  it('replaces the old automatic Polish default while retaining the profile and help preference', async () => {
    localStorage.setItem('worldsxi-prefs', JSON.stringify({ state: {
      guestToken: 'existing-guest-identity', locale: 'pl', seenHelp: true,
    }, version: 0 }))
    await usePrefs.persist.rehydrate()
    expect(usePrefs.getState()).toMatchObject({ locale: 'en', localePreference: 'auto',
      guestToken: 'existing-guest-identity', seenHelp: true })
    usePrefs.getState().syncDeviceLocale()
    expect(JSON.parse(localStorage.getItem('worldsxi-prefs')!).state.guestToken).toBe('existing-guest-identity')
  })

  it.each(['pl', 'en'] as const)('remembers a manual %s choice after hydration and device language changes', async (locale) => {
    usePrefs.setState({ guestToken: 'existing-guest-identity', seenHelp: true })
    usePrefs.getState().setLocale(locale)
    vi.spyOn(navigator, 'languages', 'get').mockReturnValue([locale === 'en' ? 'pl-PL' : 'en-US'])
    await usePrefs.persist.rehydrate()
    usePrefs.getState().syncDeviceLocale()
    expect(usePrefs.getState()).toMatchObject({ locale, localePreference: locale,
      guestToken: 'existing-guest-identity', seenHelp: true })
  })

  it('preserves an English choice made before device detection was added', async () => {
    vi.spyOn(navigator, 'languages', 'get').mockReturnValue(['pl-PL'])
    localStorage.setItem('worldsxi-prefs', JSON.stringify({ state: {
      guestToken: 'existing-guest-identity', locale: 'en', seenHelp: true,
    }, version: 0 }))
    await usePrefs.persist.rehydrate()
    expect(usePrefs.getState()).toMatchObject({ locale: 'en', localePreference: 'en' })
  })

  it('uses English for the first server/hydration snapshot', () => {
    expect(usePrefs.getInitialState().locale).toBe('en')
  })
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

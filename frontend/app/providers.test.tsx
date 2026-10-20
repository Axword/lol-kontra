import { act, cleanup, render } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import Providers from './providers'
import { usePrefs } from '@/lib/store'

function Language() { return <span>{usePrefs(state => state.locale)}</span> }
beforeEach(() => {
  localStorage.clear()
  usePrefs.setState({ guestToken: 'existing-guest-identity', locale: 'en', localePreference: 'auto' })
  vi.spyOn(navigator, 'languages', 'get').mockReturnValue(['en-US'])
})
afterEach(cleanup)

describe('language changes', () => {
  it('updates the page language when device preferences change and retains the profile', () => {
    const view = render(<Providers><Language /></Providers>)
    expect(document.documentElement.lang).toBe('en')
    vi.spyOn(navigator, 'languages', 'get').mockReturnValue(['pl-PL'])
    act(() => window.dispatchEvent(new Event('languagechange')))
    expect(document.documentElement.lang).toBe('pl')
    expect(view.container.textContent).toBe('pl')
    expect(usePrefs.getState().guestToken).toBe('existing-guest-identity')
  })
  it('keeps a manual choice when the device language changes', () => {
    usePrefs.getState().setLocale('pl')
    render(<Providers><Language /></Providers>)
    act(() => window.dispatchEvent(new Event('languagechange')))
    expect(document.documentElement.lang).toBe('pl')
  })
})

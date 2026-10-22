import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import ThemeToggle from './ThemeToggle'
import { usePrefs } from '@/lib/store'
import { themeBootstrap } from '@/lib/theme-bootstrap'

let systemDark = false
let change: (() => void) | undefined
beforeEach(() => {
  localStorage.clear(); document.documentElement.dataset.theme = 'light'; systemDark = false
  usePrefs.setState({ locale: 'en', guestToken: 'keep-this-profile' })
  vi.stubGlobal('matchMedia', vi.fn(() => ({ matches: systemDark, addEventListener: (_: string, cb: () => void) => { change = cb }, removeEventListener: vi.fn() })))
})
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks() })

it('persists a dark choice across remounts without changing the guest identity', () => {
  const first = render(<ThemeToggle />)
  fireEvent.click(screen.getByRole('button', { name: 'Switch to dark mode' }))
  expect(document.documentElement.dataset.theme).toBe('dark')
  expect(localStorage.getItem('axword-theme')).toBe('dark')
  first.unmount(); render(<ThemeToggle />)
  expect(screen.getByRole('button', { name: 'Switch to light mode' }).getAttribute('aria-pressed')).toBe('true')
  expect(usePrefs.getState().guestToken).toBe('keep-this-profile')
  expect(JSON.parse(localStorage.getItem('worldsxi-prefs')!).state.guestToken).toBe('keep-this-profile')
})
it('follows system changes until a manual choice is saved', () => {
  render(<ThemeToggle />)
  systemDark = true; act(() => change?.())
  expect(document.documentElement.dataset.theme).toBe('dark')
  fireEvent.click(screen.getByRole('button', { name: 'Switch to light mode' }))
  act(() => change?.())
  expect(document.documentElement.dataset.theme).toBe('light')
})
it('initializes the first paint to the saved theme and accepts cross-tab changes', () => {
  localStorage.setItem('axword-theme', 'dark')
  new Function(themeBootstrap)()
  expect(document.documentElement.dataset.theme).toBe('dark')
  render(<ThemeToggle />)
  localStorage.setItem('axword-theme', 'light')
  act(() => window.dispatchEvent(new StorageEvent('storage', { key: 'axword-theme' })))
  expect(document.documentElement.dataset.theme).toBe('light')
})
it('still toggles when storage is blocked', () => {
  render(<ThemeToggle />)
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('blocked') })
  fireEvent.click(screen.getByRole('button', { name: 'Switch to dark mode' }))
  expect(document.documentElement.dataset.theme).toBe('dark')
})

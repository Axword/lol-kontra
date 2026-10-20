import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { metadata } from '@/app/layout'
import pl from '@/i18n/pl.json'
import en from '@/i18n/en.json'
import Sidebar from './Sidebar'
import TopBar from './TopBar'

const prefs = vi.hoisted(() => ({ locale: 'pl' as 'pl' | 'en', setLocale: vi.fn() }))
vi.mock('@/lib/store', () => ({ usePrefs: (select: (state: typeof prefs) => unknown) => select(prefs) }))
vi.mock('next/navigation', () => ({ usePathname: () => '/' }))
vi.mock('@/app/providers', () => ({ default: () => null }))
vi.mock('./GuestIdentity', () => ({ default: () => null }))
vi.mock('@/lib/sound', () => ({
  isSoundEnabled: () => true, toggleSound: vi.fn(), sound: { click: vi.fn(), open: vi.fn() },
}))

beforeEach(() => {
  Object.defineProperty(window, 'matchMedia', { configurable: true, value: () => ({
    matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn(),
  }) })
})
afterEach(cleanup)

describe('WORDS V branding', () => {
  it('uses the requested five-player name in metadata and both translations', () => {
    expect(metadata.title).toBe('WORDS V — quiz League of Legends i Worlds')
    expect(pl.game.title).toBe('WORDS V')
    expect(en.game.title).toBe('WORDS V')
  })

  it.each(['pl', 'en'] as const)('shows the same requested brand in the navigation and mobile header in %s', (locale) => {
    prefs.locale = locale
    const { container } = render(<>
      <Sidebar open={false} onClose={vi.fn()} />
      <TopBar onMenu={vi.fn()} onHelp={vi.fn()} />
    </>)
    expect(screen.getAllByText('WORDS V').length).toBe(2)
    expect(screen.getAllByText('WORDS V').every((element) => element.closest('a')?.getAttribute('href') === '/')).toBe(true)
    expect(container.textContent).not.toContain('Worlds XI')
  })
})

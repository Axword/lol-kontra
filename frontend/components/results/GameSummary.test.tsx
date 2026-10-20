import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { Daily, GameState } from '@/lib/api'
import GameSummary from './GameSummary'

const prefs = vi.hoisted(() => ({ locale: 'pl' as 'pl' | 'en' }))
const query = vi.hoisted(() => ({ data: undefined as any, isLoading: false, isError: false, refetch: vi.fn() }))
const distributionHook = vi.hoisted(() => vi.fn())
vi.mock('@/lib/api', () => ({ useScoreDistribution: (...args: unknown[]) => distributionHook(...args) }))
vi.mock('@/lib/store', () => ({ usePrefs: (select: (state: typeof prefs) => unknown) => select(prefs) }))
vi.mock('./CompletedRoster', () => ({ default: () => <div data-testid="completed-roster">Completed roster</div> }))
vi.mock('./FinalNicknamePrompt', () => ({ default: () => null }))

const daily: Daily = { id: 7, date: '2026-10-07', status: 'scored', slots: [] }
const state: GameState = {
  id: 1, daily: 7, total_points: 438.5, is_scored: true, errors_used: 2, errors_left: 8,
  max_errors: 10, slots_total: 5, correct_count: 5, is_over: true, answers: [],
}
const data = {
  distribution: [{ score: 300, count: 2 }, { score: 439, count: 1 }],
  total_submissions: 3, rank: 1, percentile: 66.7, avg_score: 346.3, seeded_count: 2, real_count: 1,
}

beforeEach(() => {
  prefs.locale = 'pl'
  query.data = data
  query.isLoading = false
  query.isError = false
  query.refetch.mockClear()
  distributionHook.mockReturnValue(query)
})
afterEach(cleanup)

describe('finished-game result dialog', () => {
  it.each(['pl', 'en'] as const)('opens the compact graph automatically with the server result in %s', (locale) => {
    prefs.locale = locale
    render(<GameSummary daily={daily} state={state} />)
    const dialog = screen.getByRole('dialog', { name: locale === 'pl' ? 'Gra zakończona' : 'Game finished' })
    expect(distributionHook).toHaveBeenCalledWith(7, 438.5)
    expect(dialog.getAttribute('aria-modal')).toBe('true')
    expect(document.activeElement).toBe(within(dialog).getByRole('button', { name: locale === 'pl' ? 'Zamknij' : 'Close' }))
    expect(within(dialog).getByText(locale === 'pl' ? 'Końcowy wynik' : 'Final score').nextElementSibling?.textContent)
      .toBe(locale === 'pl' ? '438,5' : '438.5')
    expect(within(dialog).getByText(locale === 'pl' ? 'Percentyl' : 'Percentile', { exact: true }).nextElementSibling?.textContent)
      .toMatch(/^66[.,]7%$/)
    expect(within(dialog).getByRole('img', {
      name: locale === 'pl' ? 'Rozkład wyników z oznaczeniem Twojego wyniku' : 'Score distribution with your score marked',
    })).toBeTruthy()
    expect(within(dialog).queryByText(locale === 'pl' ? /rozgrywek testowych/ : /test games/)).toBeNull()
    expect(within(dialog).getByRole('link', { name: locale === 'pl' ? 'Ranking' : 'Leaderboard' }).getAttribute('href')).toBe('/leaderboard')
    expect(within(dialog).queryByRole('button', { name: '10' })).toBeNull()
  })

  it('closes with Escape, preserves the completed roster, and reopens with focus restored', () => {
    render(<GameSummary daily={daily} state={state} />)
    fireEvent.keyDown(document.activeElement!, { key: 'Escape' })
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(screen.getByTestId('completed-roster')).toBeTruthy()
    expect(document.body.style.overflow).toBe('')
    const reopen = screen.getByRole('button', { name: 'Twój wynik' })
    expect(document.activeElement).toBe(reopen)
    reopen.focus()
    fireEvent.click(reopen)
    const dialog = screen.getByRole('dialog', { name: 'Gra zakończona' })
    expect(document.body.style.overflow).toBe('hidden')
    const last = within(dialog).getByRole('link', { name: 'Ranking' })
    last.focus()
    fireEvent.keyDown(last, { key: 'Tab' })
    const close = within(dialog).getByRole('button', { name: 'Zamknij' })
    expect(document.activeElement).toBe(close)
    fireEvent.click(close)
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(document.activeElement).toBe(reopen)
    fireEvent.click(reopen)
    expect(screen.getByRole('dialog')).toBeTruthy()
  })

  it('closes on the backdrop and retains a way to reopen the result', () => {
    const { container } = render(<GameSummary daily={daily} state={state} />)
    fireEvent.click(container.querySelector('.picker-backdrop')!)
    expect(screen.queryByRole('dialog')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Twój wynik' }))
    expect(screen.getByRole('dialog', { name: 'Gra zakończona' })).toBeTruthy()
  })

  it('keeps loading and error states inside the dialog and recovers after a retry', () => {
    query.data = undefined
    query.isLoading = true
    const view = render(<GameSummary daily={daily} state={state} />)
    expect(within(screen.getByRole('dialog')).getByText('Liczę rozkład wyników…')).toBeTruthy()
    expect(within(screen.getByRole('dialog')).getByText('Końcowy wynik').nextElementSibling?.textContent).toBe('438,5')
    expect(screen.queryByRole('img')).toBeNull()
    query.isLoading = false
    query.isError = true
    view.rerender(<GameSummary daily={daily} state={state} />)
    const dialog = screen.getByRole('dialog')
    expect(within(dialog).getByRole('alert')).toBeTruthy()
    expect(within(dialog).getByText('Końcowy wynik').nextElementSibling?.textContent).toBe('438,5')
    expect(within(dialog).getByText('Percentyl').nextElementSibling?.textContent).toBe('—')
    fireEvent.click(within(dialog).getByRole('button', { name: 'Spróbuj ponownie' }))
    expect(query.refetch).toHaveBeenCalledOnce()
    query.isError = false
    query.data = data
    view.rerender(<GameSummary daily={daily} state={state} />)
    expect(within(screen.getByRole('dialog')).queryByRole('alert')).toBeNull()
    expect(within(screen.getByRole('dialog')).getByRole('img')).toBeTruthy()
  })
})

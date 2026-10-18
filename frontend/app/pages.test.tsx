import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import HomePage from './page'
import DailyPage from './daily/[id]/page'
import ResultsPage from './results/[id]/page'
import LeaderboardPage from './leaderboard/page'
import ArchiveList from '@/components/archive/ArchiveList'

const fixture = vi.hoisted(() => ({
  id: '7',
  daily: {} as any, game: {} as any, stats: {} as any, archive: {} as any, leaderboard: {} as any,
  gameHook: vi.fn(),
}))
vi.mock('next/navigation', () => ({ useParams: () => ({ id: fixture.id }) }))
vi.mock('@/lib/store', () => ({ usePrefs: (select: (state: any) => unknown) => select({ locale: 'pl', guestToken: 'alice', ensureGuestToken: () => 'alice' }) }))
vi.mock('@/lib/daily', async (original) => ({ ...await original<typeof import('@/lib/daily')>(), useGameDate: () => '2026-10-17' }))
vi.mock('@/lib/api', () => ({
  api: { get: vi.fn() }, useDailyToday: () => fixture.daily, useDaily: () => fixture.daily,
  useGameState: (...args: unknown[]) => { fixture.gameHook(...args); return fixture.game },
  useArchive: () => fixture.archive, useLeaderboard: () => fixture.leaderboard,
}))
vi.mock('@tanstack/react-query', () => ({ useQuery: () => fixture.stats }))
vi.mock('@/components/layout/GameLayout', () => ({ default: ({ children }: any) => <main>{children}</main> }))
vi.mock('@/components/roster/RosterBoard', () => ({ default: () => <div data-testid="roster">board</div> }))
vi.mock('@/components/results/GameSummary', () => ({ default: () => <div>summary</div> }))
vi.mock('@/components/leaderboard/DailyTop10', () => ({ default: () => <div data-testid="daily-ranking">ranking</div> }))

const query = (data: unknown = undefined) => ({ data, isLoading: false, isError: false, error: null, refetch: vi.fn() })
beforeEach(() => {
  fixture.id = '7'
  fixture.daily = query({ id: 7, date: '2026-10-16', status: 'published', slots: [{ id: 1, role: 'top', conditions: [] }] })
  fixture.game = query({ id: 1, daily: 7, answers: [], is_over: false })
  fixture.stats = query({ results: [] })
  fixture.archive = query({ results: [] })
  fixture.leaderboard = query({ results: [] })
})
afterEach(cleanup)

describe('game pages handle failures', () => {
  it.each([HomePage, DailyPage])('shows a retry when game state fails', (Page) => {
    fixture.game = { ...query(), isError: true, error: new Error('offline') }
    render(<Page />)
    expect(screen.getByRole('alert').textContent).toContain('Nie udało się wczytać stanu gry')
    expect(screen.queryByText('Wczytywanie stanu gry…')).toBeNull()
    expect(screen.queryByTestId('roster')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Spróbuj ponownie' }))
    expect(fixture.game.refetch).toHaveBeenCalledOnce()
  })

  it.each(['0', '-1', '1.5', 'oops'])('rejects invalid daily id %s without showing the board', (id) => {
    fixture.id = id
    render(<DailyPage />)
    expect(screen.getByText('Nie znaleziono planszy')).toBeTruthy()
    expect(screen.queryByTestId('roster')).toBeNull()
  })

  it.each([{ date: '2026-10-18', status: 'published' }, { date: '2026-10-16', status: 'draft' }])('rejects unavailable boards %s', (daily) => {
    fixture.daily.data = { ...fixture.daily.data, ...daily }
    render(<DailyPage />)
    expect(fixture.gameHook).toHaveBeenCalledWith(undefined, 'alice')
    expect(screen.getByText('Nie znaleziono planszy')).toBeTruthy()
    expect(screen.queryByTestId('roster')).toBeNull()
  })

  it('labels a direct link to today correctly', () => {
    fixture.daily.data.date = '2026-10-17'
    render(<DailyPage />)
    expect(screen.getByText('Dzisiejsza plansza')).toBeTruthy()
    expect(screen.queryByText(/Plansza archiwalna/)).toBeNull()
  })
})

describe('results pages', () => {
  it('does not show global rankings or playable links for an invalid board id', () => {
    fixture.id = 'missing'
    render(<ResultsPage />)
    expect(screen.getByText('Nie znaleziono planszy')).toBeTruthy()
    expect(screen.queryByTestId('daily-ranking')).toBeNull()
    expect(screen.queryByText('zagraj tę planszę')).toBeNull()
  })

  it('distinguishes a failed statistics request from an unsolved slot', () => {
    fixture.stats = { ...query(), isError: true, error: new Error('offline') }
    render(<ResultsPage />)
    expect(screen.getByText('Nie udało się wczytać odpowiedzi')).toBeTruthy()
    expect(screen.queryByText('Brak oficjalnych odpowiedzi dla tej pozycji.')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Spróbuj ponownie' }))
    expect(fixture.stats.refetch).toHaveBeenCalledOnce()
  })

  it('does not show results for a future board', () => {
    fixture.daily.data.date = '2026-10-18'
    render(<ResultsPage />)
    expect(screen.getByText('Nie znaleziono planszy')).toBeTruthy()
    expect(screen.queryByTestId('daily-ranking')).toBeNull()
  })

  it('distinguishes a failed leaderboard from an empty one', () => {
    fixture.leaderboard = { ...query(), isError: true, error: new Error('offline') }
    render(<LeaderboardPage />)
    expect(screen.queryByText('Ranking jest jeszcze pusty.')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Spróbuj ponownie' }))
    expect(fixture.leaderboard.refetch).toHaveBeenCalledOnce()
  })
})

describe('archive', () => {
  it('shows only public boards through today and links today to the home page', () => {
    fixture.archive.data.results = [
      { id: 1, date: '2026-10-16', status: 'published' },
      { id: 2, date: '2026-10-17', status: 'published' },
      { id: 3, date: '2026-10-18', status: 'published' },
      { id: 4, date: '2026-10-15', status: 'draft' },
    ]
    render(<ArchiveList />)
    expect(screen.getAllByRole('link').map((link) => link.getAttribute('href'))).toEqual(['/daily/1', '/'])
    expect(screen.getByText('Dziś')).toBeTruthy()
  })
  it('distinguishes an offline archive from an empty archive', () => {
    fixture.archive = { ...query(), isError: true }
    render(<ArchiveList />)
    expect(screen.queryByText('Brak archiwalnych plansz.')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Spróbuj ponownie' }))
    expect(fixture.archive.refetch).toHaveBeenCalledOnce()
  })
})

import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api, LeaderboardEntry, LeaderboardLimit, LeaderboardResult } from '@/lib/api'
import { usePrefs } from '@/lib/store'
import LeaderboardPage from './page'

vi.mock('@/components/layout/GameLayout', () => ({ default: ({ children }: { children: React.ReactNode }) => <main>{children}</main> }))
vi.mock('@/lib/daily', async (original) => ({ ...await original<typeof import('@/lib/daily')>(), useGameDate: () => '2026-10-19' }))
const token = '1234abcd-1111-4111-8111-111111111111'
function entry(rank: number | null, username = `Player ${rank}`): LeaderboardEntry {
  return { username, rank, is_guest: true, total_points: rank == null ? 0 : 45, games_played: rank == null ? 0 : 3,
    avg_points: rank == null ? null : 15, best_score: rank == null ? null : 0, diamond_picks: 0, legendary_answers: 0 }
}
function response(limit: LeaderboardLimit = 50, own = entry(127, 'Same nickname')): LeaderboardResult {
  return { limit, total_players: 200, results: Array.from({ length: limit }, (_, index) => entry(index + 1, index === 1 ? 'Same nickname' : `Player ${index + 1}`)), current_player: own }
}
let client: QueryClient
const mount = () => render(<QueryClientProvider client={client}><LeaderboardPage /></QueryClientProvider>)
const bodyRows = () => within(screen.getByRole('table')).getAllByRole('row').slice(1)
beforeEach(() => {
  usePrefs.setState({ guestToken: token, locale: 'pl' })
  client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
})
afterEach(() => { cleanup(); client.clear() })

describe('full leaderboard', () => {
  it.each([127, 2])('defaults to fifty players and appends a separate identified own row at global rank %s', async (rank) => {
    const post = vi.spyOn(api, 'post').mockResolvedValue({ data: response(50, entry(rank, 'Same nickname')) })
    mount()
    const select = screen.getByRole('combobox', { name: 'Graczy na stronie' }) as HTMLSelectElement
    expect(select.value).toBe('50')
    expect(within(select).getAllByRole('option').map((option) => option.textContent)).toEqual(['10', '25', '50', '100'])
    await screen.findByRole('table')
    const rows = bodyRows()
    expect(rows).toHaveLength(51)
    expect(rows[50].getAttribute('data-current-player')).toBe('true')
    expect(within(rows[50]).getAllByRole('cell')[0].textContent).toBe(String(rank))
    expect(within(rows[50]).getByText('Ty')).toBeTruthy()
    expect(within(rows[50]).getByText('Same nickname').className).toContain('underline')
    expect(screen.getAllByText('Same nickname')).toHaveLength(2)
    expect(rows[1].hasAttribute('data-current-player')).toBe(false)
    expect(post).toHaveBeenCalledWith('/leaderboard/', { limit: 50, guest_token: token, page: 1, mode: 'weighted' }, { signal: expect.any(AbortSignal) })
  })

  it.each([10, 25, 100] as const)('loads limit %s from the server without showing stale fifty-row data under the new selection', async (limit) => {
    let finish!: (value: { data: LeaderboardResult }) => void
    const post = vi.spyOn(api, 'post').mockResolvedValueOnce({ data: response() })
      .mockImplementationOnce(() => new Promise((resolve) => { finish = resolve }))
    mount()
    await screen.findByRole('table')
    expect(bodyRows()).toHaveLength(51)
    const select = screen.getByRole('combobox') as HTMLSelectElement
    fireEvent.change(select, { target: { value: String(limit) } })
    await screen.findByRole('status')
    expect(select.value).toBe(String(limit))
    expect(screen.queryByRole('table')).toBeNull()
    expect(screen.queryByText('Ty')).toBeNull()
    await waitFor(() => expect(post).toHaveBeenCalledTimes(2))
    await act(async () => { finish({ data: response(limit) }) })
    await screen.findByRole('table')
    expect(bodyRows()).toHaveLength(limit + 1)
    expect(post).toHaveBeenLastCalledWith('/leaderboard/', { limit, guest_token: token, page: 1, mode: 'weighted' }, { signal: expect.any(AbortSignal) })
  })

  it.each(['pl', 'en'] as const)('shows an unranked own player without inventing a rank or zero average in %s', async (locale) => {
    usePrefs.setState({ locale })
    vi.spyOn(api, 'post').mockResolvedValue({ data: { ...response(), results: [], total_players: 0, current_player: entry(null, 'Fresh guest') } })
    mount()
    await screen.findByRole('table')
    expect(bodyRows()).toHaveLength(1)
    const row = bodyRows()[0]
    const cells = within(row).getAllByRole('cell')
    expect(cells.map((cell) => cell.textContent)).toEqual(['—', `Fresh guest${locale === 'pl' ? 'Ty' : 'You'}`, '—', '—', '0', '—'])
    expect(screen.queryByText('Ranking jest jeszcze pusty.')).toBeNull()
    expect(row.getAttribute('data-current-player')).toBe('true')
  })

  it('does not fabricate an own row while data is loading or when the server has no current player', async () => {
    let finish!: (value: { data: LeaderboardResult }) => void
    vi.spyOn(api, 'post').mockImplementationOnce(() => new Promise((resolve) => { finish = resolve }))
    mount()
    expect(screen.getByRole('status')).toBeTruthy()
    expect(screen.queryByText('Ty')).toBeNull()
    await act(async () => { finish({ data: { ...response(), results: [], total_players: 0, current_player: null } }) })
    await screen.findByText('Ranking jest jeszcze pusty.')
    expect(screen.queryByRole('table')).toBeNull()
    expect(screen.queryByText('Ty')).toBeNull()
  })

  it('retries a failed personalized request with the selected limit and identity', async () => {
    const post = vi.spyOn(api, 'post').mockRejectedValueOnce(new Error('offline')).mockResolvedValueOnce({ data: response() })
    mount()
    await screen.findByRole('alert')
    expect(screen.queryByRole('table')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Spróbuj ponownie' }))
    await screen.findByRole('table')
    expect(post).toHaveBeenCalledTimes(2)
    expect(post.mock.calls.every(([path, payload]) => {
      const body = payload as { guest_token: string; limit: number }
      return path === '/leaderboard/' && body.guest_token === token && body.limit === 50
    })).toBe(true)
  })

  it('moves through global pages and resets to page one when sorting changes', async () => {
    const post = vi.spyOn(api, 'post').mockImplementation(async (_path, body) => {
      const options = body as { limit: LeaderboardLimit; page: number; mode: string }
      return { data: { ...response(options.limit), page: options.page, total_pages: 4,
        results: Array.from({ length: 50 }, (_, i) => entry((options.page - 1) * 50 + i + 1)) } }
    })
    mount()
    await screen.findByRole('table')
    expect((screen.getByRole('button', { name: 'Poprzednia' }) as HTMLButtonElement).disabled).toBe(true)
    fireEvent.click(screen.getByRole('button', { name: 'Następna' }))
    await screen.findByText('Player 51')
    expect(within(bodyRows()[0]).getAllByRole('cell')[0].textContent).toBe('51')
    expect((screen.getByRole('spinbutton', { name: 'Numer strony' }) as HTMLInputElement).value).toBe('2')
    fireEvent.click(screen.getByRole('button', { name: 'Ostatnia' }))
    await screen.findByText('Player 151')
    expect((screen.getByRole('button', { name: 'Następna' }) as HTMLButtonElement).disabled).toBe(true)
    fireEvent.click(screen.getByRole('button', { name: 'Według średniej' }))
    await screen.findByText('Player 1')
    expect(post).toHaveBeenLastCalledWith('/leaderboard/', { limit: 50, page: 1, mode: 'average', guest_token: token }, { signal: expect.any(AbortSignal) })
  })
})

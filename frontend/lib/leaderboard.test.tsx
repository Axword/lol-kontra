import { act, cleanup, renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReactNode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api, LeaderboardLimit, LeaderboardResult, leaderboardKey, useLeaderboard } from './api'

const clock = vi.hoisted(() => ({ date: '2026-10-19' }))
vi.mock('./daily', async (original) => ({ ...await original<typeof import('./daily')>(), useGameDate: () => clock.date }))
const alice = '1234abcd-1111-4111-8111-111111111111'
const bob = '5678abcd-2222-4222-8222-222222222222'
function response(limit: LeaderboardLimit = 50, username = 'Alice'): LeaderboardResult {
  return { results: [], limit, total_players: 200, current_player: { username, is_guest: true, rank: 127,
    total_points: 45, games_played: 3, avg_points: 15, best_score: 0, diamond_picks: 1, legendary_answers: 2 } }
}
let client: QueryClient
const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>
beforeEach(() => {
  clock.date = '2026-10-19'
  client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
})
afterEach(() => { cleanup(); client.clear() })

describe('leaderboard request limits and identity', () => {
  it('keeps legacy public daily calls on GET and preserves the enabled argument', async () => {
    const get = vi.spyOn(api, 'get').mockResolvedValue({ data: { ...response(), current_player: null } })
    const post = vi.spyOn(api, 'post')
    const hook = renderHook(({ enabled }) => useLeaderboard(7, enabled), { wrapper, initialProps: { enabled: false } })
    expect(get).not.toHaveBeenCalled()
    hook.rerender({ enabled: true })
    await waitFor(() => expect(hook.result.current.data?.limit).toBe(50))
    expect(get).toHaveBeenCalledWith('/leaderboard/', { params: { daily_id: 7, limit: 50 }, signal: expect.any(AbortSignal) })
    expect(post).not.toHaveBeenCalled()
  })

  it('requests each selected limit server-side and keeps the guest token out of URLs and query parameters', async () => {
    const get = vi.spyOn(api, 'get')
    const post = vi.spyOn(api, 'post').mockImplementation(async (_path, payload) => ({ data: response((payload as { limit: LeaderboardLimit }).limit) }))
    const hook = renderHook(({ limit }) => useLeaderboard(undefined, true, { limit, guestToken: alice }), { wrapper, initialProps: { limit: 50 as LeaderboardLimit } })
    await waitFor(() => expect(hook.result.current.data?.limit).toBe(50))
    for (const limit of [10, 25, 100] as const) {
      hook.rerender({ limit })
      await waitFor(() => expect(hook.result.current.data?.limit).toBe(limit))
      expect(client.getQueryData(leaderboardKey(undefined, limit, alice, clock.date))).toEqual(response(limit))
    }
    expect(post.mock.calls.map((call) => call[1])).toEqual([50, 10, 25, 100].map((limit) => ({ limit, guest_token: alice })))
    post.mock.calls.forEach(([url, _body, config]) => {
      expect(url).toBe('/leaderboard/')
      expect(config?.params).toBeUndefined()
    })
    expect(get).not.toHaveBeenCalled()
  })

  it('isolates the current player by guest identity and Warsaw game date', async () => {
    const post = vi.spyOn(api, 'post').mockImplementation(async (_path, payload) => ({ data: response(50, (payload as { guest_token: string }).guest_token === alice ? 'Alice' : 'Bob') }))
    const hook = renderHook(({ token }) => useLeaderboard(undefined, true, { guestToken: token }), { wrapper, initialProps: { token: alice } })
    await waitFor(() => expect(hook.result.current.data?.current_player?.username).toBe('Alice'))
    hook.rerender({ token: bob })
    expect(hook.result.current.data).toBeUndefined()
    await waitFor(() => expect(hook.result.current.data?.current_player?.username).toBe('Bob'))
    clock.date = '2026-10-20'
    hook.rerender({ token: bob })
    expect(hook.result.current.data).toBeUndefined()
    await waitFor(() => expect(hook.result.current.data?.current_player?.username).toBe('Bob'))
    expect(post).toHaveBeenCalledTimes(3)
    expect(client.getQueryData<LeaderboardResult>(leaderboardKey(undefined, 50, alice, '2026-10-19'))?.current_player?.username).toBe('Alice')
  })

  it('cancels an old limit request and does not let its late response replace the new limit', async () => {
    let finish!: (value: { data: LeaderboardResult }) => void
    const post = vi.spyOn(api, 'post').mockImplementationOnce(() => new Promise((resolve) => { finish = resolve }))
      .mockResolvedValueOnce({ data: response(10) })
    const hook = renderHook(({ limit }) => useLeaderboard(undefined, true, { limit, guestToken: alice }), { wrapper, initialProps: { limit: 50 as LeaderboardLimit } })
    await waitFor(() => expect(post).toHaveBeenCalledOnce())
    const signal = post.mock.calls[0][2]?.signal
    hook.rerender({ limit: 10 })
    expect(signal?.aborted).toBe(true)
    await waitFor(() => expect(hook.result.current.data?.limit).toBe(10))
    await act(async () => { finish({ data: response(50, 'Old response') }) })
    expect(hook.result.current.data?.limit).toBe(10)
    expect(hook.result.current.data?.current_player?.username).toBe('Alice')
  })

  it('waits for an explicitly requested guest identity and never requests invalid daily IDs', () => {
    const get = vi.spyOn(api, 'get')
    const post = vi.spyOn(api, 'post')
    renderHook(() => useLeaderboard(undefined, true, { guestToken: '' }), { wrapper })
    renderHook(() => useLeaderboard(0, true, { guestToken: alice }), { wrapper })
    expect(get).not.toHaveBeenCalled()
    expect(post).not.toHaveBeenCalled()
  })
})

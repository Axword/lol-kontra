import { act, cleanup, renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReactNode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api, AnswerResult, GameState, gameStateKey, useAnswerSlot, useDaily, useDailyToday, useGameState, usePlayerAutocomplete } from './api'

const clock = vi.hoisted(() => ({ date: '2026-10-17' }))
vi.mock('./daily', async (original) => ({ ...await original<typeof import('./daily')>(), useGameDate: () => clock.date }))

function state(overrides: Partial<GameState> = {}): GameState {
  return { id: 1, daily: 7, total_points: 0, is_scored: false, is_practice: false, errors_used: 0,
    errors_left: 10, max_errors: 10, slots_total: 5, correct_count: 0, is_over: false, answers: [], ...overrides }
}
function answer(overrides: Partial<AnswerResult> = {}): AnswerResult {
  return { id: 9, daily_slot: 15, slot_role: 'top', player: 2, player_nickname: 'Zeus', player_slug: 'zeus',
    is_correct: true, rarity_tier: 'rare', rarity_percent: 12.34, points_awarded: 25, is_diamond_pick: false,
    pick_percent: 12.3, pick_count: 5, sample_size: 40, is_provisional: false, unchanged: false,
    submission_id: 1, total_points: 25, errors_used: 0, errors_left: 10, max_errors: 10,
    slots_total: 5, correct_count: 1, is_over: false, is_scored: false, is_practice: false, ...overrides }
}
const payload = { slot_id: 15, player_slug: 'zeus', guest_token: 'alice' }
let client: QueryClient
const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>

beforeEach(() => {
  clock.date = '2026-10-17'
  client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
})
afterEach(() => { cleanup(); client.clear() })

describe('game identity and cache', () => {
  it('waits for a guest token, then isolates the results of different guests', async () => {
    const get = vi.spyOn(api, 'get').mockResolvedValueOnce({ data: state() }).mockResolvedValueOnce({ data: state({ id: 2, total_points: 100 }) })
    const hook = renderHook(({ token }) => useGameState(7, token), { wrapper, initialProps: { token: '' } })
    expect(get).not.toHaveBeenCalled()
    hook.rerender({ token: 'alice' })
    await waitFor(() => expect(hook.result.current.data?.id).toBe(1))
    hook.rerender({ token: 'bob' })
    expect(hook.result.current.data).toBeUndefined()
    await waitFor(() => expect(hook.result.current.data?.id).toBe(2))
    expect(get.mock.calls.map((call) => (call[1]?.params as { guest_token: string }).guest_token)).toEqual(['alice', 'bob'])
    expect(client.getQueryData(gameStateKey(7, 'alice', clock.date))).toMatchObject({ total_points: 0 })
  })

  it('does not reuse the previous board or the previous day’s official game', async () => {
    vi.spyOn(api, 'get').mockResolvedValueOnce({ data: state() })
      .mockResolvedValueOnce({ data: state({ daily: 8, id: 2 }) })
      .mockResolvedValueOnce({ data: state({ daily: 8, id: 3, is_practice: true }) })
    const hook = renderHook(({ id }) => useGameState(id, 'alice'), { wrapper, initialProps: { id: 7 } })
    await waitFor(() => expect(hook.result.current.data?.id).toBe(1))
    hook.rerender({ id: 8 })
    expect(hook.result.current.data).toBeUndefined()
    await waitFor(() => expect(hook.result.current.data?.id).toBe(2))
    clock.date = '2026-10-18'
    hook.rerender({ id: 8 })
    expect(hook.result.current.data).toBeUndefined()
    await waitFor(() => expect(hook.result.current.data?.is_practice).toBe(true))
  })

  it.each([0, -1, 1.5, NaN, Infinity, Number.MAX_SAFE_INTEGER + 1])('does not request an invalid board id %s', (id) => {
    const get = vi.spyOn(api, 'get')
    renderHook(() => { useGameState(id, 'alice'); return useDaily(id) }, { wrapper })
    expect(get).not.toHaveBeenCalled()
  })

  it('refreshes today’s board when the game date changes', async () => {
    const get = vi.spyOn(api, 'get').mockResolvedValueOnce({ data: { id: 7 } }).mockResolvedValueOnce({ data: { id: 8 } })
    const hook = renderHook(() => useDailyToday(), { wrapper })
    await waitFor(() => expect(hook.result.current.data?.id).toBe(7))
    clock.date = '2026-10-18'
    hook.rerender()
    await waitFor(() => expect(hook.result.current.data?.id).toBe(8))
    expect(get).toHaveBeenCalledTimes(2)
  })
})

describe('answer reconciliation', () => {
  it.each([false, true])('refreshes only the current guest statistics when a game finishes (finished: %s)', async (finished) => {
    client.setQueryData(['guest-profile', 'alice'], { stats: { games_played: 0 } })
    client.setQueryData(['guest-profile', 'bob'], { stats: { games_played: 7 } })
    vi.spyOn(api, 'post').mockResolvedValue({ data: answer({ is_over: finished }) })
    const hook = renderHook(() => useAnswerSlot(7), { wrapper })
    await act(async () => { await hook.result.current.mutateAsync(payload) })
    expect(client.getQueryState(['guest-profile', 'alice'])?.isInvalidated).toBe(finished)
    expect(client.getQueryState(['guest-profile', 'bob'])?.isInvalidated).toBe(false)
  })

  it('uses server counters, replaces the same slot and keeps other answers', async () => {
    const existing = answer({ daily_slot: 20, id: 20, slot_role: 'mid' })
    client.setQueryData(gameStateKey(7, 'alice', clock.date), state({ answers: [existing, answer({ is_correct: false })] }))
    client.setQueryData(gameStateKey(7, 'bob', clock.date), state({ id: 99 }))
    for (const key of [['answer-stats', 7], ['score-distribution', 7, 25], ['leaderboard', 7], ['leaderboard', 'all']]) client.setQueryData(key, {})
    vi.spyOn(api, 'post').mockResolvedValue({ data: answer({ total_points: 85, correct_count: 2, errors_used: 3, errors_left: 7, is_scored: true, is_practice: true }) })
    const hook = renderHook(() => useAnswerSlot(7), { wrapper })
    await act(async () => { await hook.result.current.mutateAsync(payload) })
    const result = client.getQueryData<GameState>(gameStateKey(7, 'alice', clock.date))!
    expect(result).toMatchObject({ total_points: 85, correct_count: 2, errors_used: 3, errors_left: 7, is_scored: true, is_practice: true })
    expect(result.answers).toHaveLength(2)
    expect(result.answers.find((a) => a.daily_slot === 15)?.rarity_percent).toBe(12.34)
    expect(result.answers.find((a) => a.daily_slot === 20)).toEqual(existing)
    expect(client.getQueryData(gameStateKey(7, 'bob', clock.date))).toMatchObject({ id: 99, total_points: 0 })
    expect(client.getQueryState(['answer-stats', 7])?.isInvalidated).toBe(true)
    expect(client.getQueryState(['score-distribution', 7, 25])?.isInvalidated).toBe(true)
    expect(client.getQueryState(['leaderboard', 'all'])?.isInvalidated).toBe(true)
  })

  it('updates the original board if navigation happens while a move is in flight', async () => {
    let finish!: (value: { data: AnswerResult }) => void
    const post = vi.spyOn(api, 'post').mockImplementation(() => new Promise((resolve) => { finish = resolve }))
    const hook = renderHook(({ id }) => useAnswerSlot(id), { wrapper, initialProps: { id: 7 } })
    let request!: Promise<AnswerResult>
    act(() => { request = hook.result.current.mutateAsync(payload) })
    await waitFor(() => expect(post).toHaveBeenCalledOnce())
    hook.rerender({ id: 8 })
    await act(async () => { finish({ data: answer() }); await request })
    expect(client.getQueryData(gameStateKey(7, 'alice', clock.date))).toMatchObject({ daily: 7, total_points: 25 })
    expect(client.getQueryData(gameStateKey(8, 'alice', clock.date))).toBeUndefined()
  })

  it('reconciles answers made in a second active window with the server counters', async () => {
    const key = gameStateKey(7, 'alice', clock.date)
    client.setQueryData(key, state())
    const otherWindowAnswer = answer({ id: 20, daily_slot: 20, slot_role: 'mid' })
    vi.spyOn(api, 'post').mockResolvedValue({ data: answer({
      answers: [otherWindowAnswer, answer()], total_points: 50, correct_count: 2,
    }) })
    const hook = renderHook(() => useAnswerSlot(7), { wrapper })
    await act(async () => { await hook.result.current.mutateAsync(payload) })
    const result = client.getQueryData<GameState>(key)!
    expect(result.correct_count).toBe(2)
    expect(result.answers.filter((a) => a.is_correct)).toHaveLength(2)
    expect(result.answers.find((a) => a.daily_slot === 20)).toMatchObject({ player_nickname: 'Zeus' })
  })

  it('cancels an older state read so it cannot overwrite a successful move', async () => {
    const key = gameStateKey(7, 'alice', clock.date)
    client.setQueryData(key, state())
    let finish!: (value: { data: GameState }) => void
    const get = vi.spyOn(api, 'get').mockImplementation(() => new Promise((resolve) => { finish = resolve }))
    vi.spyOn(api, 'post').mockResolvedValue({ data: answer() })
    const hook = renderHook(() => ({ state: useGameState(7, 'alice'), answer: useAnswerSlot(7) }), { wrapper })
    let read!: ReturnType<typeof hook.result.current.state.refetch>
    act(() => { read = hook.result.current.state.refetch() })
    await waitFor(() => expect(get).toHaveBeenCalledOnce())
    const signal = get.mock.calls[0][1]?.signal
    await act(async () => { await hook.result.current.answer.mutateAsync(payload) })
    expect(signal?.aborted).toBe(true)
    await act(async () => { finish({ data: state() }); await read })
    expect(client.getQueryData(key)).toMatchObject({ total_points: 25, correct_count: 1 })
  })

  it('refreshes state after a lost response without retrying the mutation', async () => {
    const key = gameStateKey(7, 'alice', clock.date)
    client.setQueryData(key, state())
    const post = vi.spyOn(api, 'post').mockRejectedValue(new Error('connection lost'))
    const hook = renderHook(() => useAnswerSlot(7), { wrapper })
    await act(async () => { await expect(hook.result.current.mutateAsync(payload)).rejects.toThrow('connection lost') })
    expect(post).toHaveBeenCalledOnce()
    expect(client.getQueryState(key)?.isInvalidated).toBe(true)
  })
})

describe('autocomplete cancellation', () => {
  it('cancels the old search and never displays its results for a new query', async () => {
    const get = vi.spyOn(api, 'get').mockImplementation(() => new Promise(() => {}))
    const hook = renderHook(({ q }) => usePlayerAutocomplete(q, 'mid'), { wrapper, initialProps: { q: ' fa ' } })
    await waitFor(() => expect(get).toHaveBeenCalledOnce())
    expect(get.mock.calls[0][1]?.params).toEqual({ q: 'fa', role: 'mid' })
    const signal = get.mock.calls[0][1]?.signal
    hook.rerender({ q: 'faker' })
    await waitFor(() => expect(get).toHaveBeenCalledTimes(2))
    expect(signal?.aborted).toBe(true)
    expect(hook.result.current.data).toBeUndefined()
  })
})

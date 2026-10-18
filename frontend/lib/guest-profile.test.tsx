import { act, cleanup, renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReactNode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from './api'
import { usePrefs } from './store'
import { GuestProfile, guestProfileKey, useGuestProfile, useGuestToken, useUpdateGuestNickname } from './guest-profile'

const token = '1234abcd-1111-4111-8111-111111111111'
const otherToken = '5678abcd-2222-4222-8222-222222222222'
const profile: GuestProfile = {
  nickname: null, display_name: 'Gość-1234abcd',
  stats: { games_played: 3, total_points: 1350, avg_points: 450, best_score: 480,
    legendary_answers: 2, diamond_picks: 1, current_streak: 2, max_streak: 3 },
}
let client: QueryClient
const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>

beforeEach(() => {
  localStorage.clear()
  usePrefs.setState({ guestToken: token, locale: 'pl', seenHelp: true })
  client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
})
afterEach(() => { cleanup(); client.clear() })

describe('private guest profile', () => {
  it('reads without changing a nickname and isolates each guest in the cache', async () => {
    const post = vi.spyOn(api, 'post').mockResolvedValueOnce({ data: profile })
      .mockResolvedValueOnce({ data: { ...profile, display_name: 'Gość-5678abcd' } })
    const hook = renderHook(({ guestToken }) => useGuestProfile(guestToken), { wrapper, initialProps: { guestToken: '' } })
    expect(post).not.toHaveBeenCalled()
    hook.rerender({ guestToken: token })
    await waitFor(() => expect(hook.result.current.data?.display_name).toBe(profile.display_name))
    hook.rerender({ guestToken: otherToken })
    expect(hook.result.current.data).toBeUndefined()
    await waitFor(() => expect(hook.result.current.data?.display_name).toBe('Gość-5678abcd'))
    expect(post.mock.calls.map((call) => call[1])).toEqual([{ guest_token: token }, { guest_token: otherToken }])
    expect(client.getQueryData(guestProfileKey(token))).toEqual(profile)
  })

  it('saves a nickname while preserving the existing identity and game progress', async () => {
    const renamed = { ...profile, nickname: 'Knight Fan', display_name: 'Gość-Knight Fan' }
    const post = vi.spyOn(api, 'post').mockResolvedValue({ data: renamed })
    const gameKey = ['game-state', 18, token, '2026-10-18']
    const progress = { total_points: 490.91, correct_count: 1, errors_left: 9, answers: [{ player: 417 }] }
    client.setQueryData(gameKey, progress)
    client.setQueryData(['leaderboard', 'all'], { results: [] })
    const hook = renderHook(() => ({ token: useGuestToken(), update: useUpdateGuestNickname() }), { wrapper })
    await act(async () => { await hook.result.current.update.mutateAsync({ guest_token: hook.result.current.token, nickname: 'Knight Fan' }) })
    expect(post).toHaveBeenCalledWith('/guest/profile/', { guest_token: token, nickname: 'Knight Fan' })
    expect(client.getQueryData(guestProfileKey(token))).toEqual(renamed)
    expect(client.getQueryData(gameKey)).toEqual(progress)
    expect(client.getQueryState(gameKey)?.isInvalidated).toBe(false)
    expect(client.getQueryState(['leaderboard', 'all'])?.isInvalidated).toBe(true)
    expect(usePrefs.getState()).toMatchObject({ guestToken: token, locale: 'pl', seenHelp: true })
    expect(JSON.parse(localStorage.getItem('worldsxi-prefs')!).state.guestToken).toBe(token)
  })
})

import { act, cleanup, renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReactNode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from './api'
import { usePrefs } from './store'
import { GuestProfile, guestProfileKey, useGuestProfile, useGuestToken, useUpdateGuestNickname, useUpdateSupportedTeam } from './guest-profile'
import { communityKey, DailyCommunity, useDailyCommunity } from './community'

vi.mock('./daily', async (original) => ({ ...await original<typeof import('./daily')>(), useGameDate: () => '2026-10-19' }))

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

  it('saves and clears only the team field while preserving nickname and game cache', async () => {
    const team = { id: 't1', code: 'T1', name: 'T1', region: 'LCK', logo_url: '/teams/worlds-2026/t1.png' }
    const named = { ...profile, nickname: 'Fan', display_name: 'Gość-Fan', supported_team: team }
    const post = vi.spyOn(api, 'post').mockResolvedValueOnce({ data: named })
      .mockResolvedValueOnce({ data: { ...named, supported_team: null } })
    const gameKey = ['game-state', 19, token]
    client.setQueryData(gameKey, { total_points: 500, correct_count: 1 })
    const hook = renderHook(() => useUpdateSupportedTeam(), { wrapper })
    await act(async () => { await hook.result.current.mutateAsync({ guest_token: token, supported_team: 't1' }) })
    expect(post).toHaveBeenNthCalledWith(1, '/guest/profile/', { guest_token: token, supported_team: 't1' })
    expect(client.getQueryData<GuestProfile>(guestProfileKey(token))?.nickname).toBe('Fan')
    await act(async () => { await hook.result.current.mutateAsync({ guest_token: token, supported_team: null }) })
    expect(client.getQueryData<GuestProfile>(guestProfileKey(token))?.supported_team).toBeNull()
    expect(client.getQueryData(gameKey)).toEqual({ total_points: 500, correct_count: 1 })
    expect(usePrefs.getState().guestToken).toBe(token)
  })

  it('cancels an older profile read so it cannot overwrite a newly saved team', async () => {
    const team = { id: 't1', code: 'T1', name: 'T1', region: 'LCK', logo_url: '/teams/worlds-2026/t1.png' }
    let finishRead!: (value: { data: GuestProfile }) => void
    let readSignal: AbortSignal | undefined
    vi.spyOn(api, 'post').mockImplementationOnce((_url, _payload, config) => {
      readSignal = config?.signal as AbortSignal
      return new Promise((resolve) => { finishRead = resolve })
    }).mockResolvedValueOnce({ data: { ...profile, supported_team: team } })
    const hook = renderHook(() => ({ profile: useGuestProfile(token), update: useUpdateSupportedTeam() }), { wrapper })
    await waitFor(() => expect(readSignal).toBeDefined())
    await act(async () => { await hook.result.current.update.mutateAsync({ guest_token: token, supported_team: 't1' }) })
    expect(readSignal?.aborted).toBe(true)
    await act(async () => { finishRead({ data: profile }) })
    expect(client.getQueryData<GuestProfile>(guestProfileKey(token))?.supported_team?.id).toBe('t1')
  })

  it.each(['nickname', 'team'] as const)('refreshes active community names and badges after changing the %s', async (field) => {
    const team = { id: 't1', code: 'T1', name: 'T1', region: 'LCK', logo_url: '/teams/worlds-2026/t1.png' }
    const current: DailyCommunity = { author: { name: 'Axword', url: 'https://x.com/AxwordLol', description: 'Autor' },
      can_view_solutions: true, can_comment: false, comments: [], team_ranking: [],
      player_ranking: [{ nickname: 'Old name', team: null, score: 15 }],
    }
    const refreshed: DailyCommunity = { ...current, player_ranking: [{ nickname: field === 'nickname' ? 'New name' : 'Old name', team: field === 'team' ? team : null, score: 15 }] }
    client.setQueryData(communityKey(19, token, '2026-10-19'), current)
    const post = vi.spyOn(api, 'post').mockImplementation(async (path) => ({ data: path === '/guest/profile/' ? profile : refreshed }))
    const hook = renderHook(() => ({ community: useDailyCommunity(19, token), name: useUpdateGuestNickname(), team: useUpdateSupportedTeam() }), { wrapper })
    expect(hook.result.current.community.data).toEqual(current)
    expect(post).not.toHaveBeenCalled()
    await act(async () => {
      if (field === 'nickname') await hook.result.current.name.mutateAsync({ guest_token: token, nickname: 'New name' })
      else await hook.result.current.team.mutateAsync({ guest_token: token, supported_team: 't1' })
    })
    await waitFor(() => expect(hook.result.current.community.data).toEqual(refreshed))
    expect(post).toHaveBeenNthCalledWith(2, '/dailies/19/community/', { guest_token: token }, expect.objectContaining({ signal: expect.any(AbortSignal) }))
    expect(usePrefs.getState().guestToken).toBe(token)
  })
})

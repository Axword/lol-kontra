import { act, cleanup, renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReactNode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from './api'
import { communityImageUrl, communityKey, DailyCommunity, useDailyCommunity, usePostCommunityComment } from './community'

vi.mock('./daily', async (original) => ({ ...await original<typeof import('./daily')>(), useGameDate: () => '2026-10-19' }))
const data: DailyCommunity = {
  author: { name: 'Axword', url: 'https://x.com/AxwordLol', description: 'Autor wyzwania' },
  can_view_solutions: false, can_comment: false, comments: [], player_ranking: [], team_ranking: [],
}
let client: QueryClient
const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>
const originalBase = api.defaults.baseURL
beforeEach(() => { client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } }) })
afterEach(() => { cleanup(); client.clear(); api.defaults.baseURL = originalBase })

describe('daily community requests', () => {
  it('reads anonymous metadata with GET and sends guest identity without a comment for a private read', async () => {
    const get = vi.spyOn(api, 'get').mockResolvedValue({ data })
    const post = vi.spyOn(api, 'post').mockResolvedValue({ data: { ...data, can_view_solutions: true } })
    const hook = renderHook(({ token }) => useDailyCommunity(19, token), { wrapper, initialProps: { token: '' } })
    await waitFor(() => expect(hook.result.current.data).toEqual(data))
    expect(get.mock.calls[0][0]).toBe('/dailies/19/community/')
    expect(post).not.toHaveBeenCalled()
    hook.rerender({ token: 'private-guest' })
    await waitFor(() => expect(hook.result.current.data?.can_view_solutions).toBe(true))
    expect(post.mock.calls[0][1]).toEqual({ guest_token: 'private-guest' })
    expect(client.getQueryData(communityKey(19, '', '2026-10-19'))).toEqual(data)
  })

  it('publishes only explicit text and replaces the exact guest/daily cache with the server response', async () => {
    const published = { ...data, can_view_solutions: true, can_comment: false }
    const post = vi.spyOn(api, 'post').mockResolvedValue({ data: published })
    client.setQueryData(communityKey(18, 'guest', '2026-10-19'), data)
    client.setQueryData(communityKey(19, 'other', '2026-10-19'), data)
    const hook = renderHook(() => usePostCommunityComment(19, 'guest'), { wrapper })
    expect(post).not.toHaveBeenCalled()
    await act(async () => { await hook.result.current.mutateAsync('Great board') })
    expect(post).toHaveBeenCalledWith('/dailies/19/community/', { guest_token: 'guest', comment: 'Great board' })
    expect(client.getQueryData(communityKey(19, 'guest', '2026-10-19'))).toEqual(published)
    expect(client.getQueryData(communityKey(18, 'guest', '2026-10-19'))).toEqual(data)
    expect(client.getQueryData(communityKey(19, 'other', '2026-10-19'))).toEqual(data)
  })

  it('keeps existing community data when moderation rejects a comment', async () => {
    vi.spyOn(api, 'post').mockRejectedValue({ isAxiosError: true, response: { status: 400, data: { comment: ['Niedozwolona treść.'] } } })
    const key = communityKey(19, 'guest', '2026-10-19')
    client.setQueryData(key, data)
    const hook = renderHook(() => usePostCommunityComment(19, 'guest'), { wrapper })
    await act(async () => { await expect(hook.result.current.mutateAsync('Rejected text')).rejects.toBeTruthy() })
    expect(client.getQueryData(key)).toEqual(data)
  })

  it('does not request invalid or unavailable boards', () => {
    const get = vi.spyOn(api, 'get')
    const post = vi.spyOn(api, 'post')
    renderHook(() => useDailyCommunity(0, 'guest'), { wrapper })
    renderHook(() => useDailyCommunity(20, 'guest', false), { wrapper })
    expect(get).not.toHaveBeenCalled()
    expect(post).not.toHaveBeenCalled()
  })
})

describe('Django roster image URL', () => {
  it('preserves root-relative API prefixes and resolves relative paths against the configured API', () => {
    api.defaults.baseURL = 'https://lol-kontra.onrender.com/api/v1'
    expect(communityImageUrl('/api/v1/roster-shares/private.png')).toBe('https://lol-kontra.onrender.com/api/v1/roster-shares/private.png')
    expect(communityImageUrl('/roster-shares/private.png')).toBe('https://lol-kontra.onrender.com/roster-shares/private.png')
    expect(communityImageUrl('roster-shares/private.png')).toBe('https://lol-kontra.onrender.com/api/v1/roster-shares/private.png')
    expect(communityImageUrl('https://cdn.example.com/board.png')).toBe('https://cdn.example.com/board.png')
    expect(communityImageUrl(null)).toBeNull()
    expect(communityImageUrl('javascript:alert(1)')).toBeNull()
  })
})

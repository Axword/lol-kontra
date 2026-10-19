import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api, AnswerResult, GameState, gameStateKey, useAnswerSlot, useGameState } from '@/lib/api'
import { communityKey, DailyCommunity as CommunityData } from '@/lib/community'
import { usePrefs } from '@/lib/store'
import DailyCommunity from './DailyCommunity'

vi.mock('@/lib/daily', async (original) => ({ ...await original<typeof import('@/lib/daily')>(), useGameDate: () => '2026-10-19' }))
const token = '1234abcd-1111-4111-8111-111111111111'
const masked: CommunityData = { author: { name: 'Axword', url: 'https://x.com/AxwordLol', description: 'Autor wyzwania' },
  can_view_solutions: false, can_comment: false,
  comments: [{ id: 1, nickname: 'Fan', team: null, score: 15, created_at: '2026-10-19T07:00:00Z', text: null, roster_image_url: null }],
  player_ranking: [], team_ranking: [],
}
const initialState: GameState = { id: 1, daily: 19, total_points: 115, is_scored: false, is_practice: false,
  correct_count: 4, slots_total: 5, errors_used: 0, errors_left: 10, max_errors: 10, is_over: false, answers: [] }
let client: QueryClient
beforeEach(() => {
  usePrefs.setState({ locale: 'pl', guestToken: token })
  client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
})
afterEach(() => { cleanup(); client.clear() })

describe('community follows game completion', () => {
  it('refetches a fresh cached masked community after the last correct answer and reveals its comment, PNG and form', async () => {
    const final: AnswerResult = { id: 5, daily_slot: 95, slot_role: 'support', player: 5, player_nickname: 'Keria', player_slug: 'keria',
      is_correct: true, rarity_percent: 0, rarity_tier: 'legendary', points_awarded: -100, deduction: 100,
      is_diamond_pick: true, pick_percent: 0, pick_count: 0, sample_size: 1, is_provisional: true, unchanged: false,
      submission_id: 1, total_points: 15, errors_used: 0, errors_left: 10, max_errors: 10,
      slots_total: 5, correct_count: 5, is_over: true, is_scored: true, is_practice: false,
    }
    const visible: CommunityData = { ...masked, can_view_solutions: true, can_comment: true,
      comments: [{ ...masked.comments[0], text: 'A rare support pick', roster_image_url: '/api/v1/roster-shares/unguessable.png' }] }
    client.setQueryData(gameStateKey(19, token, '2026-10-19'), initialState)
    client.setQueryData(communityKey(19, token, '2026-10-19'), masked)
    const get = vi.spyOn(api, 'get')
    const post = vi.spyOn(api, 'post').mockImplementation(async (path) => {
      if (path === '/submissions/answer/') return { data: final }
      if (path === '/dailies/19/community/') return { data: visible }
      throw new Error(`Unexpected request: ${path}`)
    })
    function Game() {
      const state = useGameState(19, token).data
      const answer = useAnswerSlot(19)
      return <>
        <button type="button" onClick={() => answer.mutate({ guest_token: token, slot_id: 95, player_slug: 'keria' })}>Finish board</button>
        <DailyCommunity dailyId={19} state={state} />
      </>
    }
    render(<QueryClientProvider client={client}><Game /></QueryClientProvider>)
    expect(screen.getByText('Ukończ planszę, aby zobaczyć komentarz i skład.')).toBeTruthy()
    expect(screen.queryByRole('textbox')).toBeNull()
    expect(post).not.toHaveBeenCalled()
    expect(get).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: 'Finish board' }))
    await screen.findByText('A rare support pick')
    expect(screen.getByRole('textbox', { name: 'Twój komentarz' })).toBeTruthy()
    expect(screen.getByRole('img', { name: 'Skład gracza Fan' }).getAttribute('src')).toContain('/api/v1/roster-shares/unguessable.png')
    expect(screen.queryByText('Ukończ planszę, aby zobaczyć komentarz i skład.')).toBeNull()
    expect(post).toHaveBeenNthCalledWith(2, '/dailies/19/community/', { guest_token: token }, expect.objectContaining({ signal: expect.any(AbortSignal) }))
    expect(post.mock.calls.every((call) => !(call[1] as Record<string, unknown>).comment)).toBe(true)
    await waitFor(() => expect(client.getQueryData<GameState>(gameStateKey(19, token, '2026-10-19'))?.total_points).toBe(15))
  })
})

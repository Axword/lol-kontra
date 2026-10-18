import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { api, type AnswerResult, type Daily, type GameState, gameStateKey, useGameState } from '@/lib/api'
import RosterBoard from './RosterBoard'

vi.mock('@/lib/daily', async (original) => ({
  ...await original<typeof import('@/lib/daily')>(),
  useGameDate: () => '2026-10-18',
}))
vi.mock('@/lib/store', () => ({
  usePrefs: (select: (state: unknown) => unknown) => select({
    locale: 'pl', guestToken: 'knight-regression', ensureGuestToken: () => 'knight-regression',
  }),
}))
vi.mock('@/lib/sound', () => ({
  sound: { open: vi.fn(), close: vi.fn(), pick: vi.fn(), success: vi.fn(), error: vi.fn() },
}))

const daily: Daily = {
  id: 18, date: '2026-10-18', status: 'published', slots: [{
    id: 88, position: 3, role: 'mid', label_pl: 'Mid', label_en: 'Mid', conditions: [
      { id: 1, condition_type: 'residency', operator: 'eq', value: 'LPL', label_pl: 'Grał w LPL', label_en: 'Played in LPL' },
      { id: 2, condition_type: 'career_top5_champion', operator: 'eq', value: 'Orianna', label_pl: 'Orianna w TOP 5 kariery', label_en: 'Orianna in career TOP 5' },
    ],
  }],
}

const previousMiss = {
  id: 9, daily_slot: 88, slot_role: 'mid' as const, player: 1,
  player_nickname: 'Previous player', player_slug: 'previous-player', is_correct: false,
  rarity_tier: null, rarity_percent: null, points_awarded: 0, is_diamond_pick: false,
}

const initialState: GameState = {
  id: 7, daily: 18, total_points: 500, is_scored: false, is_practice: false,
  errors_used: 1, errors_left: 9, max_errors: 10, slots_total: 5,
  correct_count: 0, is_over: false, answers: [previousMiss],
}

let client: QueryClient
afterEach(() => { cleanup(); client?.clear() })

describe('answer feedback with the real picker and query cache', () => {
  it('accepts Knight and clears an earlier miss when the API validates his career Orianna condition', async () => {
    const result: AnswerResult = {
      ...previousMiss, player: 417, player_nickname: 'Knight', player_slug: 'knight-zhuo-ding',
      is_correct: true, rarity_tier: 'epic', rarity_percent: 9.09,
      points_awarded: -9.09, deduction: 9.09,
      pick_percent: 9.09, pick_count: 1, sample_size: 11, is_provisional: true,
      unchanged: false, submission_id: 7, total_points: 490.91,
      errors_used: 1, errors_left: 9, max_errors: 10, slots_total: 5,
      correct_count: 1, is_over: false, is_scored: false, is_practice: false,
    }
    result.answers = [{ ...result }]
    vi.spyOn(api, 'get').mockResolvedValue({ data: { results: [{
      id: 417, slug: 'knight-zhuo-ding', nickname: 'Knight', primary_role: 'mid',
      portrait_url: null, country_code: 'CN', residency: 'LPL', real_name: 'Zhuo Ding',
    }] } })
    const post = vi.spyOn(api, 'post').mockResolvedValue({ data: result })
    client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
    client.setQueryData(gameStateKey(18, 'knight-regression', '2026-10-18'), initialState)

    function Game() {
      const state = useGameState(18, 'knight-regression').data!
      return <RosterBoard daily={daily} state={state} />
    }
    render(<QueryClientProvider client={client}><Game /></QueryClientProvider>)

    fireEvent.click(screen.getAllByRole('button', { name: /Mid – puste/ })[0])
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'knight' } })
    fireEvent.click(await screen.findByRole('option', { name: 'Knight' }))

    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    expect(post).toHaveBeenCalledWith('/submissions/answer/', {
      daily_id: 18, slot_id: 88, player_slug: 'knight-zhuo-ding', guest_token: 'knight-regression',
    })
    expect(screen.getByRole('status').textContent).toContain('Knight pasuje.')
    expect(screen.getByRole('status').textContent).toMatch(/9[,.]1%/)
    expect(screen.getByRole('status').textContent).not.toMatch(/pkt|pts|9[,.]09/)
    expect(screen.queryByRole('alert')).toBeNull()
    expect(screen.queryByText(/nie spełnia warunków/)).toBeNull()
    expect(screen.getAllByRole('button', { name: 'Mid – Knight' }).every((button) => (button as HTMLButtonElement).disabled)).toBe(true)
    expect(client.getQueryData<GameState>(gameStateKey(18, 'knight-regression', '2026-10-18'))).toMatchObject({
      total_points: 490.91, correct_count: 1, errors_used: 1, errors_left: 9,
      answers: [{ player_slug: 'knight-zhuo-ding', is_correct: true }],
    })
  })
})

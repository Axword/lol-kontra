import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
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
  it('keeps a first correct pick at 0% on the toast, card and resumed board even when current popularity is 100%', async () => {
    const fakerDaily: Daily = { ...daily, slots: [{ ...daily.slots[0], conditions: [
      { id: 1, condition_type: 'country', operator: 'eq', value: 'KR', label_pl: 'Koreańczyk', label_en: 'Korean' },
      { id: 2, condition_type: 'worlds_champion', operator: 'eq', value: true, label_pl: 'Mistrz Worlds', label_en: 'Worlds champion' },
    ] }] }
    const start: GameState = { ...initialState, errors_used: 0, errors_left: 10, answers: [] }
    const result: AnswerResult = {
      ...previousMiss, player: 418, player_nickname: 'Faker', player_slug: 'faker',
      is_correct: true, rarity_tier: 'legendary', rarity_percent: 0, points_awarded: 0, deduction: 0,
      is_diamond_pick: true, pick_percent: 0, pick_count: 0, sample_size: 0, is_provisional: true,
      unchanged: false, submission_id: 7, total_points: 500,
      errors_used: 0, errors_left: 10, max_errors: 10, slots_total: 5,
      correct_count: 1, is_over: false, is_scored: false, is_practice: false,
    }
    result.answers = [{ ...result }]
    vi.spyOn(api, 'get').mockResolvedValue({ data: { results: [{
      id: 418, slug: 'faker', nickname: 'Faker', primary_role: 'mid',
      portrait_url: null, country_code: 'KR', residency: 'LCK', real_name: 'Lee Sang-hyeok',
    }] } })
    vi.spyOn(api, 'post').mockResolvedValue({ data: result })
    client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
    const key = gameStateKey(18, 'knight-regression', '2026-10-18')
    client.setQueryData(key, start)
    client.setQueryData(['answer-stats', 18], { results: [{ slot_id: 88, player_slug: 'faker', pick_percent: 100 }] })
    function Game() {
      return <RosterBoard daily={fakerDaily} state={useGameState(18, 'knight-regression').data!} />
    }
    const view = render(<QueryClientProvider client={client}><Game /></QueryClientProvider>)
    fireEvent.click(screen.getAllByRole('button', { name: 'Mid – puste' })[0])
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'faker' } })
    fireEvent.click(await screen.findByRole('option', { name: 'Faker' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    const feedback = screen.getByRole('status')
    expect(feedback.textContent).toContain('Faker pasuje.')
    expect(within(feedback).getByText('0%')).toBeTruthy()
    expect(within(feedback).getByRole('img', { name: 'Diamentowy wybór' })).toBeTruthy()
    for (const selector of ['.rift-card', '.rift-marker', '.slot-list-mobile button']) {
      const card = view.container.querySelector<HTMLElement>(selector)!
      expect(within(card).getByText('0%')).toBeTruthy()
      expect(within(card).queryByText('100%')).toBeNull()
      expect(card.getAttribute('data-rarity')).toBe('diamond')
    }
    const saved = JSON.parse(JSON.stringify(client.getQueryData<GameState>(key))) as GameState
    expect(saved).toMatchObject({ total_points: 500, answers: [{ rarity_percent: 0, is_diamond_pick: true }] })
    view.unmount()
    client.clear()
    client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
    client.setQueryData(key, saved)
    client.setQueryData(['answer-stats', 18], { results: [{ slot_id: 88, player_slug: 'faker', pick_percent: 100 }] })
    const resumed = render(<QueryClientProvider client={client}><Game /></QueryClientProvider>)
    const card = resumed.container.querySelector<HTMLElement>('.rift-card')!
    expect(within(card).getByText('0%')).toBeTruthy()
    expect(within(card).getByRole('img', { name: 'Diamentowy wybór' })).toBeTruthy()
    expect(within(card).queryByText('100%')).toBeNull()
    expect(saved.total_points).toBe(500)
  })

  it('finds Faker on Top and leaves the slot open with nine lives after the server rejects his role', async () => {
    const topDaily: Daily = { ...daily, slots: [{ ...daily.slots[0], role: 'top', label_pl: 'Top', label_en: 'Top' }] }
    const start: GameState = { ...initialState, errors_used: 0, errors_left: 10, answers: [] }
    const miss: AnswerResult = {
      ...previousMiss, slot_role: 'top', player: 418, player_nickname: 'Faker', player_slug: 'faker',
      pick_percent: null, pick_count: null, sample_size: null, is_provisional: true,
      unchanged: false, submission_id: 7, total_points: 500,
      errors_used: 1, errors_left: 9, max_errors: 10, slots_total: 5,
      correct_count: 0, is_over: false, is_scored: false, is_practice: false,
    }
    miss.answers = [{ ...miss }]
    const get = vi.spyOn(api, 'get').mockResolvedValue({ data: { results: [{
      id: 418, slug: 'faker', nickname: 'Faker', primary_role: 'mid',
      portrait_url: 'https://example.com/faker.png', country_code: 'KR', residency: 'LCK', real_name: 'Lee Sang-hyeok',
    }] } })
    const post = vi.spyOn(api, 'post').mockResolvedValue({ data: miss })
    client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
    const key = gameStateKey(18, 'knight-regression', '2026-10-18')
    client.setQueryData(key, start)
    function Game() {
      return <RosterBoard daily={topDaily} state={useGameState(18, 'knight-regression').data!} />
    }
    render(<QueryClientProvider client={client}><Game /></QueryClientProvider>)
    fireEvent.click(screen.getAllByRole('button', { name: 'Top – puste' })[0])
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'fa' } })
    const option = await screen.findByRole('option', { name: 'Faker' })
    expect(option.textContent).toBe('Faker')
    expect(option.querySelector('img')?.getAttribute('src')).toBe('https://example.com/faker.png')
    expect(get.mock.calls[0][1]?.params).toEqual({ q: 'fa' })
    fireEvent.click(option)
    await waitFor(() => expect(screen.getByRole('alert').textContent).toBe('Faker nie spełnia warunków. Pozostało żyć: 9.'))
    expect(post).toHaveBeenCalledWith('/submissions/answer/', {
      daily_id: 18, slot_id: 88, player_slug: 'faker', guest_token: 'knight-regression',
    })
    expect(screen.getByRole('dialog')).toBeTruthy()
    expect((screen.getByRole('combobox') as HTMLInputElement).disabled).toBe(false)
    expect(client.getQueryData<GameState>(key)).toMatchObject({
      total_points: 500, errors_used: 1, errors_left: 9, correct_count: 0,
      answers: [{ player_slug: 'faker', is_correct: false }],
    })
    fireEvent.click(screen.getByRole('button', { name: 'Zamknij' }))
    expect(screen.getAllByRole('button', { name: 'Top – puste' }).every((button) => !(button as HTMLButtonElement).disabled)).toBe(true)
    fireEvent.click(screen.getAllByRole('button', { name: 'Top – puste' })[0])
    expect(screen.getByRole('dialog')).toBeTruthy()
  })

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

import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { DailyCommunity as CommunityData } from '@/lib/community'
import type { GameState } from '@/lib/api'
import DailyCommunity from './DailyCommunity'

const mocks = vi.hoisted(() => ({
  query: { data: undefined as CommunityData | undefined, isLoading: false, isError: false, error: undefined as unknown, refetch: vi.fn() },
  post: { mutate: vi.fn(), isPending: false, isError: false, error: undefined as unknown, isSuccess: false, reset: vi.fn() },
}))
vi.mock('@/lib/store', () => ({ usePrefs: (select: (state: unknown) => unknown) => select({ locale: 'pl', guestToken: 'same-guest' }) }))
vi.mock('@/lib/community', () => ({
  useDailyCommunity: () => mocks.query, usePostCommunityComment: () => mocks.post,
  communityImageUrl: (path: string | null) => path ? `https://api.example.com${path}` : null,
}))
const team = { id: 't1', code: 'T1', name: 'T1', region: 'LCK', logo_url: '/teams/worlds-2026/t1.png' }
const data: CommunityData = {
  author: { name: 'Axword', url: 'https://x.com/AxwordLol', description: 'Autor wyzwania' },
  can_view_solutions: false, can_comment: false,
  comments: [{ id: 1, nickname: 'Fan', team, score: 15, created_at: '2026-10-19T07:00:00Z', text: 'Secret answer explanation', roster_image_url: '/api/v1/roster-shares/private.png' }],
  player_ranking: [{ nickname: 'Best player', team, score: 0 }, { nickname: 'Another player', team: null, score: 15 }],
  team_ranking: [{ team, players: 2, average_score: 7.5 }],
}
const finished: GameState = { id: 1, daily: 19, total_points: 15, is_scored: true, is_practice: false,
  errors_used: 0, errors_left: 10, max_errors: 10, slots_total: 5, correct_count: 5, is_over: true, answers: [] }
beforeEach(() => {
  mocks.query.data = { ...data }
  mocks.query.isLoading = false; mocks.query.isError = false; mocks.query.error = undefined
  mocks.post.isPending = false; mocks.post.isError = false; mocks.post.error = undefined; mocks.post.isSuccess = false
})
afterEach(cleanup)

describe('daily community', () => {
  it('keeps comments and roster spoilers hidden before finishing even if the response accidentally contains them', () => {
    render(<DailyCommunity dailyId={19} state={{ ...finished, is_over: false }} />)
    expect(screen.getByRole('link', { name: 'Axword' }).getAttribute('href')).toBe('https://x.com/AxwordLol')
    expect(screen.getByText('Ukończ planszę, aby zobaczyć komentarz i skład.')).toBeTruthy()
    expect(screen.queryByText('Secret answer explanation')).toBeNull()
    expect(screen.queryByRole('img', { name: 'Skład gracza Fan' })).toBeNull()
    expect(screen.queryByRole('textbox')).toBeNull()
    expect(mocks.post.mutate).not.toHaveBeenCalled()
    expect(screen.getByRole('tabpanel', { name: 'Gracze' }).textContent).toContain('Best player0')
  })

  it('displays the real saved roster image and comment after finishing without offering a second comment', () => {
    mocks.query.data = { ...data, can_view_solutions: true, can_comment: false }
    render(<DailyCommunity dailyId={19} state={finished} />)
    expect(screen.getByText('Secret answer explanation')).toBeTruthy()
    const image = screen.getByRole('img', { name: 'Skład gracza Fan' })
    expect(image.getAttribute('src')).toBe('https://api.example.com/api/v1/roster-shares/private.png')
    expect(image.getAttribute('width')).toBe('720')
    expect(image.getAttribute('height')).toBe('500')
    expect(image.closest('a')?.getAttribute('href')).toBe(image.getAttribute('src'))
    expect(screen.queryByRole('textbox')).toBeNull()
  })

  it('posts text only after an explicit action and lets the server attach the saved roster', () => {
    mocks.query.data = { ...data, can_view_solutions: true, can_comment: true }
    const view = render(<DailyCommunity dailyId={19} state={finished} />)
    expect(mocks.post.mutate).not.toHaveBeenCalled()
    const input = screen.getByRole('textbox', { name: 'Twój komentarz' }) as HTMLTextAreaElement
    expect(input.maxLength).toBe(500)
    fireEvent.change(input, { target: { value: 'Great board' } })
    fireEvent.click(screen.getByRole('button', { name: 'Opublikuj ze składem' }))
    expect(mocks.post.mutate).toHaveBeenCalledWith('Great board', expect.objectContaining({ onSuccess: expect.any(Function) }))
    mocks.post.isSuccess = true
    mocks.query.data = { ...data, can_view_solutions: true, can_comment: false }
    view.rerender(<DailyCommunity dailyId={19} state={finished} />)
    expect(screen.getByRole('status').textContent).toBe('Komentarz opublikowany.')
    expect(screen.queryByRole('textbox')).toBeNull()
  })

  it('preserves rejected text and shows the server moderation error', () => {
    mocks.query.data = { ...data, can_view_solutions: true, can_comment: true }
    const view = render(<DailyCommunity dailyId={19} state={finished} />)
    const input = screen.getByRole('textbox') as HTMLTextAreaElement
    fireEvent.change(input, { target: { value: 'Rejected comment' } })
    mocks.post.isError = true
    mocks.post.error = { isAxiosError: true, response: { status: 400, data: { comment: ['Niedozwolona treść.'] } } }
    view.rerender(<DailyCommunity dailyId={19} state={finished} />)
    expect(screen.getByRole('alert').textContent).toBe('Niedozwolona treść.')
    expect(input.value).toBe('Rejected comment')
    expect(input.getAttribute('aria-invalid')).toBe('true')
  })

  it('shows team averages and supporter counts when switching rankings, including with keyboard navigation', () => {
    render(<DailyCommunity dailyId={19} state={finished} />)
    const players = screen.getByRole('tab', { name: 'Gracze' })
    fireEvent.keyDown(players, { key: 'ArrowRight' })
    const teams = screen.getByRole('tab', { name: 'Drużyny' })
    expect(document.activeElement).toBe(teams)
    expect(teams.getAttribute('aria-selected')).toBe('true')
    const panel = screen.getByRole('tabpanel', { name: 'Drużyny' })
    expect(within(panel).getByText('Gracze: 2')).toBeTruthy()
    expect(within(panel).getByText('7,5').getAttribute('title')).toBe('Średni wynik')
    fireEvent.keyDown(teams, { key: 'Home' })
    expect(screen.getByRole('tabpanel', { name: 'Gracze' })).toBeTruthy()
  })

  it('shows loading and retry states while keeping the author card available', () => {
    mocks.query.data = undefined
    mocks.query.isLoading = true
    const view = render(<DailyCommunity dailyId={19} state={finished} />)
    expect(screen.getByRole('status').textContent).toBe('Wczytywanie komentarzy…')
    expect(screen.queryByRole('textbox')).toBeNull()
    expect(screen.getByRole('link', { name: 'Axword' })).toBeTruthy()
    mocks.query.isLoading = false; mocks.query.isError = true
    view.rerender(<DailyCommunity dailyId={19} state={finished} />)
    fireEvent.click(screen.getByRole('button', { name: 'Spróbuj ponownie' }))
    expect(mocks.query.refetch).toHaveBeenCalledOnce()
  })

  it('does not permit comments from practice games', () => {
    mocks.query.data = { ...data, can_view_solutions: true, can_comment: true }
    render(<DailyCommunity dailyId={19} state={{ ...finished, is_practice: true }} />)
    expect(screen.queryByRole('textbox')).toBeNull()
  })
})

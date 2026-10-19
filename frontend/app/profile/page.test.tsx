import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '@/lib/api'
import { GuestProfile, guestProfileKey } from '@/lib/guest-profile'
import { usePrefs } from '@/lib/store'
import ProfilePage from './page'

vi.mock('@/components/layout/GameLayout', () => ({ default: ({ children }: { children: React.ReactNode }) => <main>{children}</main> }))
const token = '1234abcd-1111-4111-8111-111111111111'
const profile: GuestProfile = {
  nickname: 'Old name', display_name: 'Gość-Old name',
  stats: { games_played: 3, total_points: 1350, avg_points: 450, best_score: 480,
    legendary_answers: 2, diamond_picks: 1, current_streak: 2, max_streak: 3 },
}
let client: QueryClient
const mount = () => render(<QueryClientProvider client={client}><ProfilePage /></QueryClientProvider>)
beforeEach(() => {
  localStorage.clear()
  usePrefs.setState({ guestToken: token, locale: 'pl', seenHelp: true })
  client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
})
afterEach(() => { cleanup(); client.clear() })

describe('guest nickname and statistics', () => {
  it('saves the nickname with the same token, displays real statistics and allows resetting the name', async () => {
    const post = vi.spyOn(api, 'post').mockResolvedValueOnce({ data: profile })
      .mockResolvedValueOnce({ data: { ...profile, nickname: 'Knight Fan', display_name: 'Gość-Knight Fan' } })
      .mockResolvedValueOnce({ data: { ...profile, nickname: null, display_name: 'Gość-1234abcd' } })
    mount()
    const input = screen.getByRole('textbox', { name: 'Nick' }) as HTMLInputElement
    await waitFor(() => expect(input.value).toBe('Old name'))
    for (const [label, value] of [['Rozegrane gry', '3'], ['Suma punktów', '1350'], ['Najlepszy wynik', '480'], ['Średni wynik', '450']]) {
      expect(within(screen.getByText(label).parentElement!).getByRole('definition').textContent?.replace(/\s/g, '')).toBe(value)
    }
    expect(screen.getByText(/wyniki są przypisane do tej przeglądarki/)).toBeTruthy()
    fireEvent.change(input, { target: { value: 'Knight Fan' } })
    fireEvent.click(screen.getByRole('button', { name: 'Zapisz' }))
    await screen.findByText('Nick zapisany.')
    expect(post).toHaveBeenNthCalledWith(2, '/guest/profile/', { guest_token: token, nickname: 'Knight Fan' })
    expect(input.value).toBe('Knight Fan')
    fireEvent.change(input, { target: { value: '' } })
    fireEvent.click(screen.getByRole('button', { name: 'Zapisz' }))
    await waitFor(() => expect(client.getQueryData<GuestProfile>(guestProfileKey(token))?.nickname).toBeNull())
    expect(post).toHaveBeenNthCalledWith(3, '/guest/profile/', { guest_token: token, nickname: '' })
    expect(usePrefs.getState()).toMatchObject({ guestToken: token, seenHelp: true })
  })

  it('shows the backend nickname validation message without resetting identity or game progress', async () => {
    const post = vi.spyOn(api, 'post').mockResolvedValueOnce({ data: profile }).mockRejectedValueOnce({
      isAxiosError: true, response: { status: 400, data: { nickname: ['Ten nick jest zbyt długi.'] } },
    })
    const gameKey = ['game-state', 18, token, '2026-10-18']
    const progress = { total_points: 490.91, correct_count: 1, answers: [{ player: 417 }] }
    client.setQueryData(gameKey, progress)
    mount()
    const input = screen.getByRole('textbox', { name: 'Nick' }) as HTMLInputElement
    await waitFor(() => expect(input.value).toBe('Old name'))
    fireEvent.change(input, { target: { value: 'A rejected nickname' } })
    fireEvent.click(screen.getByRole('button', { name: 'Zapisz' }))
    expect((await screen.findByRole('alert')).textContent).toBe('Ten nick jest zbyt długi.')
    expect(input.getAttribute('aria-invalid')).toBe('true')
    expect(input.value).toBe('A rejected nickname')
    expect(post).toHaveBeenNthCalledWith(2, '/guest/profile/', { guest_token: token, nickname: 'A rejected nickname' })
    expect(client.getQueryData(gameKey)).toEqual(progress)
    expect(usePrefs.getState()).toMatchObject({ guestToken: token, seenHelp: true })
  })

  it('preserves input typed before the initial request finishes', async () => {
    let finish!: (value: { data: GuestProfile }) => void
    vi.spyOn(api, 'post').mockImplementationOnce(() => new Promise((resolve) => { finish = resolve }))
    mount()
    const input = screen.getByRole('textbox', { name: 'Nick' }) as HTMLInputElement
    fireEvent.change(input, { target: { value: 'Still typing' } })
    await act(async () => { finish({ data: profile }) })
    expect(input.value).toBe('Still typing')
  })

  it('keeps newer edits while a save is pending', async () => {
    let finish!: (value: { data: GuestProfile }) => void
    vi.spyOn(api, 'post').mockResolvedValueOnce({ data: profile })
      .mockImplementationOnce(() => new Promise((resolve) => { finish = resolve }))
    mount()
    const input = screen.getByRole('textbox', { name: 'Nick' }) as HTMLInputElement
    await waitFor(() => expect(input.value).toBe('Old name'))
    fireEvent.change(input, { target: { value: 'Submitted name' } })
    fireEvent.click(screen.getByRole('button', { name: 'Zapisz' }))
    await waitFor(() => expect((screen.getByRole('button', { name: 'Zapisywanie…' }) as HTMLButtonElement).disabled).toBe(true))
    fireEvent.change(input, { target: { value: 'Newer edit' } })
    await act(async () => { finish({ data: { ...profile, nickname: 'Submitted name', display_name: 'Gość-Submitted name' } }) })
    expect(input.value).toBe('Newer edit')
    expect(screen.queryByText('Nick zapisany.')).toBeNull()
  })

  it('shows expanded real statistics and the most picked players with portraits and counts', async () => {
    vi.spyOn(api, 'post').mockResolvedValue({ data: { ...profile, stats: { ...profile.stats,
      correct_answers: 14, incorrect_attempts: 2, accuracy_percent: 87.5, perfect_games: 2, average_pick_percent: 8.4,
      top_players: [
        { id: 1, slug: 'faker', nickname: 'Faker', portrait_url: 'https://static.wikia.nocookie.net/faker.png', pick_count: 4 },
        { id: 2, slug: 'knight', nickname: 'Knight', portrait_url: null, pick_count: 2 },
      ],
    } } })
    mount()
    await screen.findByText('Faker')
    for (const [label, value] of [
      ['Poprawne odpowiedzi', '14'], ['Pomyłki', '2'], ['Skuteczność', '87,5%'], ['Gry bez pomyłki', '2'],
      ['Średnia popularność wyborów', '8,4%'], ['Diamentowe wybory', '1'], ['Wybory poniżej 2%', '2'],
      ['Obecna seria dni', '2'], ['Najdłuższa seria dni', '3'],
    ]) {
      expect(within(screen.getByText(label).parentElement!).getByRole('definition').textContent).toBe(value)
    }
    const list = screen.getByRole('list')
    const rows = within(list).getAllByRole('listitem')
    expect(rows).toHaveLength(2)
    expect(rows[0].textContent).toBe('FakerWybory: 4')
    expect(rows[0].querySelector('img')?.getAttribute('src')).toBe('https://static.wikia.nocookie.net/faker.png')
    expect(rows[1].textContent).toBe('KnightWybory: 2')
    expect(rows[1].querySelector('img')).toBeNull()
  })

  it('handles an empty profile and older profile responses without inventing player statistics', async () => {
    vi.spyOn(api, 'post').mockResolvedValue({ data: { ...profile, stats: { ...profile.stats, games_played: 0 } } })
    mount()
    await screen.findByText('Brak poprawnych wyborów.')
    expect(screen.queryByRole('list')).toBeNull()
    expect(within(screen.getByText('Skuteczność').parentElement!).getByRole('definition').textContent).toBe('0%')
    expect(screen.getByText('Najczęściej wybierani zawodnicy')).toBeTruthy()
  })
})

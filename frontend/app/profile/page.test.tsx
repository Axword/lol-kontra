import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '@/lib/api'
import { GuestProfile, guestProfileKey } from '@/lib/guest-profile'
import { usePrefs } from '@/lib/store'
import ProfilePage from './page'
import GuestIdentity from '@/components/layout/GuestIdentity'

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
    expect(screen.getByText(/Wyniki są zapisane na serwerze/)).toBeTruthy()
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

  it('shares the profile badge with the header and preserves an unsaved nickname when choosing or clearing a team', async () => {
    const team = { id: 't1', code: 'T1', name: 'T1', region: 'LCK', logo_url: '/teams/worlds-2026/t1.png' }
    const post = vi.spyOn(api, 'post').mockResolvedValueOnce({ data: { ...profile, supported_team: null } })
      .mockResolvedValueOnce({ data: { ...profile, supported_team: team } })
      .mockResolvedValueOnce({ data: { ...profile, supported_team: null } })
    const get = vi.spyOn(api, 'get').mockResolvedValue({ data: { season: 2026, teams: [team], source_url: 'https://lolesports.com/' } })
    const gameKey = ['game-state', 19, token, '2026-10-19']
    const progress = { total_points: 15, correct_count: 5, is_over: true }
    client.setQueryData(gameKey, progress)
    render(<QueryClientProvider client={client}><GuestIdentity /><ProfilePage /></QueryClientProvider>)
    const input = screen.getByRole('textbox', { name: 'Nick' }) as HTMLInputElement
    await waitFor(() => expect(input.value).toBe('Old name'))
    fireEvent.change(input, { target: { value: 'Unsaved nickname' } })
    const badge = screen.getByRole('region', { name: 'Odznaka' })
    fireEvent.click(within(badge).getByRole('button', { name: 'Wybierz drużynę' }))
    fireEvent.click(await screen.findByRole('button', { name: 'T1 T1 · LCK' }))
    await screen.findByRole('button', { name: 'Kibicuję: T1' })
    expect(within(badge).getByText('T1')).toBeTruthy()
    expect(badge.querySelector('img')?.getAttribute('src')).toBe(team.logo_url)
    expect(input.value).toBe('Unsaved nickname')
    expect(post).toHaveBeenNthCalledWith(2, '/guest/profile/', { guest_token: token, supported_team: 't1' })
    fireEvent.click(within(badge).getByRole('button', { name: 'Zmień drużynę' }))
    fireEvent.click(screen.getByRole('button', { name: 'Bez drużyny' }))
    await waitFor(() => expect(client.getQueryData<GuestProfile>(guestProfileKey(token))?.supported_team).toBeNull())
    expect(within(badge).getByRole('button', { name: 'Wybierz drużynę' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Zmień nick: Old name' })).toBeTruthy()
    expect(input.value).toBe('Unsaved nickname')
    expect(client.getQueryData<GuestProfile>(guestProfileKey(token))?.nickname).toBe('Old name')
    expect(post).toHaveBeenNthCalledWith(3, '/guest/profile/', { guest_token: token, supported_team: null })
    expect(get).toHaveBeenCalledTimes(1)
    expect(client.getQueryData(gameKey)).toEqual(progress)
    expect(usePrefs.getState()).toMatchObject({ guestToken: token, seenHelp: true })
  })

  it('retains the profile selection and nickname draft after a badge save fails, then returns focus with Escape', async () => {
    const team = { id: 't1', code: 'T1', name: 'T1', region: 'LCK', logo_url: '/teams/worlds-2026/t1.png' }
    const other = { id: 'g2', code: 'G2', name: 'G2', region: 'LEC', logo_url: '/teams/worlds-2026/g2.png' }
    let fail!: (error: unknown) => void
    vi.spyOn(api, 'post').mockResolvedValueOnce({ data: { ...profile, supported_team: team } })
      .mockImplementationOnce(() => new Promise((_resolve, reject) => { fail = reject }))
    vi.spyOn(api, 'get').mockResolvedValue({ data: { season: 2026, teams: [team, other], source_url: 'https://lolesports.com/' } })
    mount()
    const input = screen.getByRole('textbox', { name: 'Nick' }) as HTMLInputElement
    await waitFor(() => expect(input.value).toBe('Old name'))
    fireEvent.change(input, { target: { value: 'Draft stays' } })
    const badge = screen.getByRole('region', { name: 'Odznaka' })
    const open = within(badge).getByRole('button', { name: 'Zmień drużynę' })
    fireEvent.click(open)
    fireEvent.click(await screen.findByRole('button', { name: 'G2 G2 · LEC' }))
    const dialog = screen.getByRole('dialog', { name: 'Kibicuję' })
    await waitFor(() => expect(within(dialog).getByRole('status').textContent).toBe('Zapisywanie…'))
    expect((within(dialog).getByRole('button', { name: 'G2 G2 · LEC' }) as HTMLButtonElement).disabled).toBe(true)
    await act(async () => { fail({ isAxiosError: true, response: { status: 400, data: { supported_team: ['Nie udało się zmienić drużyny.'] } } }) })
    expect((await within(dialog).findByRole('alert')).textContent).toBe('Nie udało się zmienić drużyny.')
    expect(client.getQueryData<GuestProfile>(guestProfileKey(token))?.supported_team?.id).toBe('t1')
    fireEvent.keyDown(document.activeElement!, { key: 'Escape' })
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(document.activeElement).toBe(open)
    expect(input.value).toBe('Draft stays')
    expect(within(badge).getByText('T1')).toBeTruthy()
  })
})

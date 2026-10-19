import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '@/lib/api'
import { usePrefs } from '@/lib/store'
import GuestIdentity from './GuestIdentity'
import { GuestProfile, guestProfileKey } from '@/lib/guest-profile'

const token = '1234abcd-1111-4111-8111-111111111111'
let client: QueryClient
const profile: GuestProfile = {
  nickname: null, display_name: 'Gość-1234abcd', supported_team: null,
  stats: { games_played: 1, total_points: 450, avg_points: 450, best_score: 450,
    legendary_answers: 1, diamond_picks: 0, current_streak: 1, max_streak: 1 },
}
const team = { id: 't1', code: 'T1', name: 'T1', region: 'LCK', logo_url: '/teams/worlds-2026/t1.png' }
const teams = { season: 2026, teams: [team], source_url: 'https://lolesports.com/' }
const mount = () => render(<QueryClientProvider client={client}><GuestIdentity /></QueryClientProvider>)
beforeEach(() => {
  usePrefs.setState({ guestToken: token, locale: 'pl', seenHelp: true })
  client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
})
afterEach(() => { cleanup(); client.clear() })

describe('guest identity in the header', () => {
  it('edits the nickname from the header with Enter and preserves identity and game progress', async () => {
    const user = userEvent.setup()
    const post = vi.spyOn(api, 'post').mockResolvedValueOnce({ data: profile })
      .mockResolvedValueOnce({ data: { ...profile, nickname: 'Knight Fan', display_name: 'Gość-Knight Fan' } })
    const get = vi.spyOn(api, 'get')
    const gameKey = ['game-state', 19, token]
    const progress = { total_points: 433.33, correct_count: 2 }
    client.setQueryData(gameKey, progress)
    mount()
    const button = await screen.findByRole('button', { name: 'Zmień nick: 1234abcd' })
    expect(button.textContent).toBe('NICK: 1234abcd')
    expect(screen.queryByRole('link')).toBeNull()
    expect(get).not.toHaveBeenCalled()
    expect(post.mock.calls[0][1]).toEqual({ guest_token: token })
    await user.click(button)
    const input = screen.getByRole('textbox', { name: 'Nick' })
    expect(document.activeElement).toBe(input)
    await user.type(input, 'Knight Fan{Enter}')
    await screen.findByRole('button', { name: 'Zmień nick: Knight Fan' })
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(post).toHaveBeenNthCalledWith(2, '/guest/profile/', { guest_token: token, nickname: 'Knight Fan' })
    expect(document.activeElement).toBe(button)
    expect(client.getQueryData(gameKey)).toEqual(progress)
    expect(usePrefs.getState()).toMatchObject({ guestToken: token, seenHelp: true })
  })

  it('keeps rejected names in the editor and closes with Escape without changing the profile', async () => {
    const user = userEvent.setup()
    vi.spyOn(api, 'post').mockResolvedValueOnce({ data: profile }).mockRejectedValueOnce({
      isAxiosError: true, response: { status: 400, data: { nickname: ['Ten nick jest niedozwolony.'] } },
    })
    mount()
    const button = await screen.findByRole('button', { name: 'Zmień nick: 1234abcd' })
    await user.click(button)
    const input = screen.getByRole('textbox', { name: 'Nick' }) as HTMLInputElement
    await user.type(input, 'Rejected name{Enter}')
    expect((await screen.findByRole('alert')).textContent).toBe('Ten nick jest niedozwolony.')
    expect(input.value).toBe('Rejected name')
    expect(input.getAttribute('aria-invalid')).toBe('true')
    await user.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(document.activeElement).toBe(button)
    expect(client.getQueryData(guestProfileKey(token))).toEqual(profile)
    expect(usePrefs.getState().guestToken).toBe(token)
  })

  it('loads teams only after opening the badge, saves and clears support without changing the nickname', async () => {
    const supported = { ...profile, nickname: 'Fan', display_name: 'Gość-Fan', supported_team: team }
    const post = vi.spyOn(api, 'post').mockResolvedValueOnce({ data: { ...supported, supported_team: null } })
      .mockResolvedValueOnce({ data: supported }).mockResolvedValueOnce({ data: { ...supported, supported_team: null } })
    let finish!: (value: { data: typeof teams }) => void
    const get = vi.spyOn(api, 'get').mockImplementationOnce(() => new Promise((resolve) => { finish = resolve }))
    mount()
    await screen.findByRole('button', { name: 'Zmień nick: Fan' })
    expect(get).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: 'Wybierz drużynę' }))
    expect(screen.getByRole('dialog', { name: 'Kibicuję' })).toBeTruthy()
    expect(screen.getByRole('status').textContent).toBe('Wczytywanie drużyn…')
    await act(async () => { finish({ data: teams }) })
    fireEvent.click(await screen.findByRole('button', { name: 'T1 T1 · LCK' }))
    const badge = await screen.findByRole('button', { name: 'Kibicuję: T1' })
    expect(badge.querySelector('img')?.getAttribute('src')).toBe(team.logo_url)
    expect(post).toHaveBeenNthCalledWith(2, '/guest/profile/', { guest_token: token, supported_team: 't1' })
    expect(screen.getByRole('button', { name: 'Zmień nick: Fan' })).toBeTruthy()
    fireEvent.click(badge)
    expect(screen.getByRole('button', { name: 'T1 T1 · LCK' }).getAttribute('aria-pressed')).toBe('true')
    fireEvent.click(screen.getByRole('button', { name: 'Bez drużyny' }))
    await screen.findByRole('button', { name: 'Wybierz drużynę' })
    expect(post).toHaveBeenNthCalledWith(3, '/guest/profile/', { guest_token: token, supported_team: null })
    expect(get).toHaveBeenCalledTimes(1)
    expect(usePrefs.getState().guestToken).toBe(token)
  })

  it('shows team save errors and retains the previous selection', async () => {
    vi.spyOn(api, 'post').mockResolvedValueOnce({ data: profile }).mockRejectedValueOnce({
      isAxiosError: true, response: { status: 400, data: { supported_team: ['Nieprawidłowa drużyna.'] } },
    })
    vi.spyOn(api, 'get').mockResolvedValue({ data: teams })
    mount()
    fireEvent.click(await screen.findByRole('button', { name: 'Wybierz drużynę' }))
    fireEvent.click(await screen.findByRole('button', { name: 'T1 T1 · LCK' }))
    expect((await screen.findByRole('alert')).textContent).toBe('Nieprawidłowa drużyna.')
    expect(screen.getByRole('dialog')).toBeTruthy()
    expect(client.getQueryData<GuestProfile>(guestProfileKey(token))?.supported_team).toBeNull()
  })

  it('allows retrying a failed team list and traps keyboard focus inside the dialog', async () => {
    const user = userEvent.setup()
    vi.spyOn(api, 'post').mockResolvedValue({ data: profile })
    const get = vi.spyOn(api, 'get').mockRejectedValueOnce({
      isAxiosError: true, response: { status: 400, data: { detail: 'Nie udało się wczytać drużyn.' } },
    }).mockResolvedValueOnce({ data: teams })
    mount()
    await user.click(await screen.findByRole('button', { name: 'Wybierz drużynę' }))
    const dialog = screen.getByRole('dialog')
    await screen.findByRole('alert')
    await user.click(screen.getByRole('button', { name: 'Spróbuj ponownie' }))
    const teamButton = await screen.findByRole('button', { name: 'T1 T1 · LCK' })
    teamButton.focus()
    await user.tab()
    expect(document.activeElement).toBe(within(dialog).getByRole('button', { name: 'Zamknij' }))
    expect(get).toHaveBeenCalledTimes(2)
  })
})

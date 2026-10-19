import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '@/lib/api'
import { GuestProfile } from '@/lib/guest-profile'
import { usePrefs } from '@/lib/store'
import FinalNicknamePrompt from './FinalNicknamePrompt'

const token = '1234abcd-1111-4111-8111-111111111111'
const profile: GuestProfile = { nickname: null, has_custom_nickname: false, display_name: 'Gość-1234abcd', stats: {
  games_played: 1, total_points: 15, avg_points: 15, best_score: 15, legendary_answers: 1,
  diamond_picks: 1, current_streak: 1, max_streak: 1,
} }
let client: QueryClient
const mount = (eligible = true) => render(<QueryClientProvider client={client}><FinalNicknamePrompt eligible={eligible} /></QueryClientProvider>)
beforeEach(() => {
  usePrefs.setState({ guestToken: token, locale: 'pl' })
  client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
})
afterEach(() => { cleanup(); client.clear() })

describe('nickname after finishing', () => {
  it('waits for the profile and saves only the nickname after explicit submission', async () => {
    let finish!: (value: { data: GuestProfile }) => void
    const post = vi.spyOn(api, 'post').mockImplementationOnce(() => new Promise((resolve) => { finish = resolve }))
      .mockResolvedValueOnce({ data: { ...profile, nickname: 'My result', has_custom_nickname: true } })
    mount()
    expect(screen.queryByRole('textbox')).toBeNull()
    await act(async () => { finish({ data: profile }) })
    const input = await screen.findByRole('textbox', { name: 'Zapisz jako…' })
    expect(input.getAttribute('placeholder')).toBe('Gość-1234abcd')
    expect(post).toHaveBeenCalledTimes(1)
    fireEvent.change(input, { target: { value: 'My result' } })
    fireEvent.click(screen.getByRole('button', { name: 'Zapisz nick' }))
    await waitFor(() => expect(screen.queryByRole('textbox')).toBeNull())
    expect(post).toHaveBeenNthCalledWith(2, '/guest/profile/', { guest_token: token, nickname: 'My result' })
    expect(post.mock.calls.every(([path]) => path === '/guest/profile/')).toBe(true)
    expect(usePrefs.getState().guestToken).toBe(token)
  })

  it.each([
    { ...profile, nickname: 'Already named', has_custom_nickname: false },
    { ...profile, nickname: null, has_custom_nickname: true },
    { ...profile, nickname: 'Legacy nickname', has_custom_nickname: undefined },
  ])('does not prompt someone who already used a custom nickname', async (saved) => {
    const post = vi.spyOn(api, 'post').mockResolvedValue({ data: saved })
    mount()
    await waitFor(() => expect(post).toHaveBeenCalledOnce())
    await act(async () => {})
    expect(screen.queryByRole('textbox')).toBeNull()
  })

  it('does not prompt a practice or unfinished result', async () => {
    vi.spyOn(api, 'post').mockResolvedValue({ data: profile })
    mount(false)
    await act(async () => {})
    expect(screen.queryByRole('textbox')).toBeNull()
  })

  it('shows moderation feedback without posting a comment or discarding the typed name', async () => {
    const post = vi.spyOn(api, 'post').mockResolvedValueOnce({ data: profile }).mockRejectedValueOnce({
      isAxiosError: true, response: { status: 400, data: { nickname: ['Ten nick jest niedozwolony.'] } },
    })
    mount()
    const input = await screen.findByRole('textbox') as HTMLInputElement
    fireEvent.change(input, { target: { value: 'Rejected name' } })
    fireEvent.click(screen.getByRole('button', { name: 'Zapisz nick' }))
    expect((await screen.findByRole('alert')).textContent).toBe('Ten nick jest niedozwolony.')
    expect(input.value).toBe('Rejected name')
    expect(post).toHaveBeenCalledTimes(2)
  })
})

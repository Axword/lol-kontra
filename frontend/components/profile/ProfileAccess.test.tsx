import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '@/lib/api'
import { usePrefs } from '@/lib/store'
import { GuestProfile, guestProfileKey } from '@/lib/guest-profile'
import { profileAccessFile } from '@/lib/profile-access'
import ProfileAccess from './ProfileAccess'

const current = 'current-profile-123456'
const imported = 'imported-profile-123456'
const profile: GuestProfile = { nickname: 'Returning', display_name: 'Gość-Returning', has_custom_nickname: true,
  stats: { games_played: 7, total_points: 35, avg_points: 5, best_score: 0, legendary_answers: 2,
    diamond_picks: 3, current_streak: 2, max_streak: 3 } }
let client: QueryClient
beforeEach(() => { usePrefs.setState({ guestToken: current, locale: 'pl' }); client = new QueryClient({ defaultOptions: { queries: { retry: false } } }) })
afterEach(() => { cleanup(); client.clear() })
function renderAccess() {
  const onRestored = vi.fn()
  const view = render(<StrictMode><QueryClientProvider client={client}><ProfileAccess guestToken={current} onRestored={onRestored} /></QueryClientProvider></StrictMode>)
  return { ...view, onRestored }
}
function upload(text = profileAccessFile(imported)) {
  const file = new File([text], 'profile.json', { type: 'application/json' })
  Object.defineProperty(file, 'text', { value: async () => text })
  fireEvent.change(screen.getByLabelText('Wczytaj dostęp do profilu'), { target: { files: [file] } })
}
describe('profile access transfer', () => {
  it('requires server verification and confirmation before switching the identity', async () => {
    const post = vi.spyOn(api, 'post').mockResolvedValue({ data: profile })
    client.setQueryData(['private-old-data'], 'old')
    const view = renderAccess()
    upload()
    await screen.findByText('Gość-Returning · 7 rozegranych gier')
    expect(usePrefs.getState().guestToken).toBe(current)
    expect(post.mock.calls[0][0]).toBe('/guest/profile/preview/')
    expect(post.mock.calls[0][1]).toEqual({ guest_token: imported })
    fireEvent.click(screen.getByRole('button', { name: 'Użyj tego profilu' }))
    await waitFor(() => expect(usePrefs.getState().guestToken).toBe(imported))
    expect(client.getQueryData(['private-old-data'])).toBeUndefined()
    expect(client.getQueryData(guestProfileKey(imported))).toEqual(profile)
    expect(view.onRestored).toHaveBeenCalledOnce()
  })
  it('retains the current profile if the target database does not contain the imported one', async () => {
    vi.spyOn(api, 'post').mockRejectedValue({ response: { status: 404 } })
    renderAccess(); upload()
    await screen.findByRole('alert')
    expect(usePrefs.getState().guestToken).toBe(current)
    expect(screen.queryByRole('button', { name: 'Użyj tego profilu' })).toBeNull()
  })
  it('rejects injected scores locally without making a request', async () => {
    const post = vi.spyOn(api, 'post')
    renderAccess(); upload(JSON.stringify({ ...JSON.parse(profileAccessFile(imported)), points: 0 }))
    await screen.findByRole('alert')
    expect(post).not.toHaveBeenCalled()
    expect(usePrefs.getState().guestToken).toBe(current)
  })
  it('cancels without activating the imported profile', async () => {
    vi.spyOn(api, 'post').mockResolvedValue({ data: profile })
    renderAccess(); upload()
    await screen.findByRole('button', { name: 'Użyj tego profilu' })
    fireEvent.click(screen.getByRole('button', { name: 'Anuluj' }))
    expect(usePrefs.getState().guestToken).toBe(current)
  })
  it('restores the original identity if browser storage refuses the imported key', async () => {
    vi.spyOn(api, 'post').mockResolvedValue({ data: profile })
    const view = renderAccess(); upload()
    await screen.findByRole('button', { name: 'Użyj tego profilu' })
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('Storage blocked') })
    fireEvent.click(screen.getByRole('button', { name: 'Użyj tego profilu' }))
    await screen.findByRole('alert')
    expect(usePrefs.getState().guestToken).toBe(current)
    expect(view.onRestored).not.toHaveBeenCalled()
  })
  it('does not overwrite an identity changed in another part of the app after previewing', async () => {
    vi.spyOn(api, 'post').mockResolvedValue({ data: profile })
    renderAccess(); upload()
    await screen.findByRole('button', { name: 'Użyj tego profilu' })
    act(() => usePrefs.setState({ guestToken: 'other-current-profile-1234' }))
    fireEvent.click(screen.getByRole('button', { name: 'Użyj tego profilu' }))
    await screen.findByRole('alert')
    expect(usePrefs.getState().guestToken).toBe('other-current-profile-1234')
  })
  it('does not let a late earlier file replace a more recent preview', async () => {
    let resolveFirst!: (value: { data: GuestProfile }) => void
    vi.spyOn(api, 'post').mockImplementationOnce(() => new Promise(resolve => { resolveFirst = resolve }))
      .mockResolvedValueOnce({ data: { ...profile, display_name: 'Recent' } })
    renderAccess(); upload()
    await waitFor(() => expect(resolveFirst).toBeTypeOf('function'))
    // A new file selection can race even when the native input is disabled.
    upload(profileAccessFile('newer-imported-profile-1234'))
    await screen.findByText('Recent · 7 rozegranych gier')
    await act(async () => { resolveFirst({ data: profile }) })
    expect(screen.queryByText('Gość-Returning · 7 rozegranych gier')).toBeNull()
  })
})

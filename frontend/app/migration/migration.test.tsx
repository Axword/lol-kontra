import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '@/lib/api'
import { usePrefs } from '@/lib/store'
import * as migration from '@/lib/domain-migration'
import ProfileMigration from './migration'

const current = 'new-profile-123456789'
const original = 'old-profile-123456789'
const profile = { display_name: 'Gość-Axword', stats: { games_played: 2 } }
let client: QueryClient
beforeEach(() => {
  usePrefs.setState({ guestToken: current })
  client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ guestToken: original, next: '/daily/20' }) }))
  vi.spyOn(api, 'post').mockResolvedValue({ data: profile })
  vi.spyOn(migration, 'migrationCompleteUrl')
  // jsdom reports navigation as an error; the state and destination are checked below.
  vi.spyOn(console, 'error').mockImplementation(() => {})
})
afterEach(() => { cleanup(); client.clear(); vi.unstubAllGlobals() })
function open() {
  return render(<StrictMode><QueryClientProvider client={client}><ProfileMigration /></QueryClientProvider></StrictMode>)
}
describe('cross-domain profile recovery', () => {
  it('verifies the old identity once and requires confirmation before replacing an existing profile', async () => {
    open()
    await screen.findByText('Gość-Axword · 2 rozegranych gier')
    expect(usePrefs.getState().guestToken).toBe(current)
    expect(fetch).toHaveBeenCalledOnce()
    expect(api.post).toHaveBeenCalledOnce()
    fireEvent.click(screen.getByRole('button', { name: 'Przenieś mój profil' }))
    await waitFor(() => expect(usePrefs.getState().guestToken).toBe(original))
    expect(migration.migrationCompleteUrl).toHaveBeenCalledWith('/daily/20')
  })
  it('keeps the new identity when the user chooses it', async () => {
    open()
    fireEvent.click(await screen.findByRole('button', { name: 'Zachowaj bieżący profil' }))
    expect(usePrefs.getState().guestToken).toBe(current)
    expect(migration.migrationCompleteUrl).toHaveBeenCalledWith('/daily/20')
  })
  it('restores automatically when the new domain has no identity yet', async () => {
    usePrefs.setState({ guestToken: '' })
    open()
    await waitFor(() => expect(usePrefs.getState().guestToken).toBe(original))
    expect(screen.queryByRole('button', { name: 'Przenieś mój profil' })).toBeNull()
  })
  it('preserves the current identity if server verification fails', async () => {
    vi.mocked(api.post).mockRejectedValue({ response: { status: 404 } })
    open()
    await screen.findByRole('alert')
    expect(usePrefs.getState().guestToken).toBe(current)
    expect(migration.migrationCompleteUrl).not.toHaveBeenCalled()
    expect(screen.getByRole('link', { name: 'Spróbuj ponownie ze starej strony' }).getAttribute('href')).toContain('/legacy-migration?')
  })
  it('preserves the current identity and offers recovery when the handoff expires', async () => {
    vi.mocked(fetch).mockResolvedValue({ ok: false } as Response)
    open()
    await screen.findByRole('alert')
    expect(usePrefs.getState().guestToken).toBe(current)
    expect(api.post).not.toHaveBeenCalled()
  })
})

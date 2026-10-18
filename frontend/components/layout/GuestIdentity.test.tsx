import { cleanup, render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '@/lib/api'
import { usePrefs } from '@/lib/store'
import GuestIdentity from './GuestIdentity'

const token = '1234abcd-1111-4111-8111-111111111111'
let client: QueryClient
beforeEach(() => {
  usePrefs.setState({ guestToken: token, locale: 'pl' })
  client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
})
afterEach(() => { cleanup(); client.clear() })

describe('guest identity in the header', () => {
  it('links the server guest display name to the editable profile', async () => {
    const post = vi.spyOn(api, 'post').mockResolvedValue({ data: { nickname: null, display_name: 'Gość-1234abcd' } })
    render(<QueryClientProvider client={client}><GuestIdentity /></QueryClientProvider>)
    const link = await screen.findByRole('link', { name: 'Gość-1234abcd' })
    expect(link.getAttribute('href')).toBe('/profile')
    expect(link.getAttribute('title')).toBe('Gość-1234abcd')
    expect(post.mock.calls[0][1]).toEqual({ guest_token: token })
    expect(usePrefs.getState().guestToken).toBe(token)
  })
})

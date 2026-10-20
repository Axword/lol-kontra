'use client'
import type { QueryClient } from '@tanstack/react-query'
import { guestProfileKey, type GuestProfile } from './guest-profile'
import { usePrefs } from './store'

export async function activateProfile(client: QueryClient, expected: string, token: string, profile: GuestProfile) {
  await client.cancelQueries()
  if (usePrefs.getState().guestToken !== expected) throw new Error('profile_changed')
  try { usePrefs.setState({ guestToken: token }) }
  catch {
    try { usePrefs.setState({ guestToken: expected }) } catch { /* Restore memory even when persistence is blocked. */ }
    throw new Error('profile_storage_failed')
  }
  client.clear()
  client.setQueryData(guestProfileKey(token), profile)
}

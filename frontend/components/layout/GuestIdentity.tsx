'use client'
import Link from 'next/link'
import { usePrefs } from '@/lib/store'
import { useGuestProfile, useGuestToken } from '@/lib/guest-profile'

export default function GuestIdentity() {
  const locale = usePrefs((state) => state.locale)
  const guestToken = useGuestToken()
  const profile = useGuestProfile(guestToken)
  const name = profile.data?.display_name || (locale === 'pl' ? 'Gość' : 'Guest')

  return <Link href="/profile" title={name} className="min-w-0 max-w-[112px] truncate px-1 text-[11px] font-medium"
    style={{ color: 'var(--text-dim)' }}>{name}</Link>
}

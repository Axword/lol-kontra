'use client'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useEffect, useState } from 'react'
import { BookOpen, ChevronRight, Menu, Volume2, VolumeX } from 'lucide-react'
import { usePrefs } from '@/lib/store'
import { isSoundEnabled, sound, toggleSound } from '@/lib/sound'
import GuestIdentity from './GuestIdentity'

type Props = {
  onMenu: () => void
  onHelp: () => void
}

export default function TopBar({ onMenu, onHelp }: Props) {
  const pathname = usePathname()
  const locale = usePrefs((s) => s.locale)
  const setLocale = usePrefs((s) => s.setLocale)
  const [soundEnabled, setSoundEnabled] = useState(true)
  useEffect(() => setSoundEnabled(isSoundEnabled()), [])

  const section = pathname.startsWith('/infinity') ? 'Infinity' : pathname.startsWith('/archiwum')
    ? (locale === 'pl' ? 'Archiwum' : 'Archive')
    : pathname.startsWith('/leaderboard')
    ? (locale === 'pl' ? 'Ranking' : 'Leaderboard')
    : pathname.startsWith('/profile')
    ? (locale === 'pl' ? 'Profil' : 'Profile')
    : pathname.startsWith('/results')
    ? (locale === 'pl' ? 'Wyniki' : 'Results')
    : null

  return (
    <header className="sticky top-0 z-30 border-b" style={{ background: '#fff', borderColor: 'var(--line)' }}>
      <div className="max-w-[1180px] mx-auto min-h-14 px-3 py-2 sm:h-14 sm:px-6 sm:py-0 flex flex-wrap sm:flex-nowrap items-center gap-2 sm:gap-4">
        <button
          type="button"
          onClick={onMenu}
          aria-label={locale === 'pl' ? 'Otwórz menu' : 'Open menu'}
          className="lg:hidden shrink-0 h-9 w-9 flex items-center justify-center"
          style={{ color: 'var(--text-dim)' }}
        >
          <Menu size={19} strokeWidth={1.7} aria-hidden="true" />
        </button>

        <div className="min-w-0 flex items-center gap-3 text-[13px]">
          <Link href="/" className="font-semibold whitespace-nowrap" style={{ color: 'var(--text)' }}><span className="sm:hidden">WORLDS KONTRA</span><span className="hidden sm:inline">League of Legends</span></Link>
          {section && (
            <span className="hidden sm:flex items-center gap-3 min-w-0" style={{ color: 'var(--text-faint)' }}>
              <ChevronRight size={14} aria-hidden="true" />
              <span className="truncate">{section}</span>
            </span>
          )}
        </div>

        <div className="ml-auto min-w-0 max-[420px]:w-full flex items-center justify-end gap-1 sm:gap-2">
          <GuestIdentity />
          <div className="shrink-0 flex items-center border" style={{ borderColor: 'var(--line)' }}>
            {(['pl', 'en'] as const).map((language) => (
              <button
                type="button"
                key={language}
                aria-pressed={locale === language}
                onClick={() => { setLocale(language); sound.click() }}
                className="h-8 px-2.5 text-[11px] font-semibold uppercase transition-colors"
                style={{
                  background: locale === language ? 'var(--gold)' : '#fff',
                  color: locale === language ? '#fff' : 'var(--text-dim)',
                }}
              >
                {language}
              </button>
            ))}
          </div>
          <button
            type="button"
            aria-label={locale === 'pl'
              ? (soundEnabled ? 'Wyłącz dźwięk' : 'Włącz dźwięk')
              : (soundEnabled ? 'Mute sound' : 'Enable sound')}
            aria-pressed={soundEnabled}
            title={locale === 'pl' ? 'Dźwięk' : 'Sound'}
            onClick={() => {
              const enabled = toggleSound()
              setSoundEnabled(enabled)
              if (enabled) sound.click()
            }}
            className="shrink-0 h-9 w-9 flex items-center justify-center transition-colors"
            style={{ color: soundEnabled ? 'var(--text-dim)' : 'var(--text-faint)' }}
          >
            {soundEnabled
              ? <Volume2 size={18} strokeWidth={1.7} aria-hidden="true" />
              : <VolumeX size={18} strokeWidth={1.7} aria-hidden="true" />}
          </button>
          <button
            type="button"
            aria-label={locale === 'pl' ? 'Zasady gry' : 'How to play'}
            title={locale === 'pl' ? 'Zasady gry' : 'How to play'}
            onClick={() => { sound.open(); onHelp() }}
            className="shrink-0 h-9 w-9 flex items-center justify-center transition-colors"
            style={{ color: 'var(--text-dim)' }}
          >
            <BookOpen size={18} strokeWidth={1.7} aria-hidden="true" />
          </button>
        </div>
      </div>
    </header>
  )
}

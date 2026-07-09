'use client'
import { useState } from 'react'
import { sound, isSoundEnabled, toggleSound } from '@/lib/sound'

export default function TopBar({
  errorsLeft = 10,
  errorsTotal = 10,
  onMenu,
  onHelp,
  locale = 'pl',
  onLocaleChange,
}: {
  errorsLeft?: number
  errorsTotal?: number
  onMenu: () => void
  onHelp: () => void
  locale?: string
  onLocaleChange?: (l: string) => void
}) {
  const [snd, setSnd] = useState(isSoundEnabled())

  const handleSound = () => {
    const n = toggleSound()
    setSnd(n)
    if (n) sound.click()
  }

  return (
    <div className="h-[52px] px-3 sm:px-5 flex items-center justify-between bg-[#0d1117] border-b border-zinc-800/80">
      {/* left */}
      <div className="flex items-center gap-3">
        <button
          onClick={onMenu}
          className="lg:hidden p-1.5 rounded-lg hover:bg-zinc-800 text-zinc-400 hover:text-white transition"
          aria-label="Menu"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <line x1="3" y1="6" x2="21" y2="6" />
            <line x1="3" y1="12" x2="21" y2="12" />
            <line x1="3" y1="18" x2="21" y2="18" />
          </svg>
        </button>

        {/* wordmark */}
        <div className="font-bold text-[15px] tracking-tight">
          <span className="text-[#C89B3C]">Worlds</span><span className="text-white"> XI</span>
        </div>

        {/* lang */}
        <div className="hidden sm:flex items-center bg-zinc-900 border border-zinc-800 rounded-full text-[10px] font-semibold overflow-hidden">
          {(['pl', 'en'] as const).map(l => (
            <button
              key={l}
              onClick={() => { onLocaleChange?.(l); sound.click() }}
              className={`px-2.5 py-1.5 uppercase transition ${locale === l ? 'bg-[#C89B3C] text-black' : 'text-zinc-400 hover:text-white'}`}
            >{l}</button>
          ))}
        </div>
      </div>

      {/* right */}
      <div className="flex items-center gap-2">
        {/* sound */}
        <button
          onClick={handleSound}
          title={snd ? 'Wyłącz dźwięk' : 'Włącz dźwięk'}
          className="p-1.5 rounded-lg border border-zinc-800 text-zinc-400 hover:text-white hover:border-zinc-600 bg-transparent transition"
        >
          {snd ? (
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
              <path d="M19.07 4.93a10 10 0 0 1 0 14.14" />
              <path d="M15.54 8.46a5 5 0 0 1 0 7.07" />
            </svg>
          ) : (
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
              <line x1="23" y1="9" x2="17" y2="15" />
              <line x1="17" y1="9" x2="23" y2="15" />
            </svg>
          )}
        </button>

        {/* help */}
        <button
          onClick={() => { sound.open(); onHelp() }}
          className="w-[28px] h-[28px] rounded-lg border border-zinc-800 text-zinc-400 hover:text-white hover:border-zinc-600 bg-transparent flex items-center justify-center text-[12px] font-bold transition"
          title="Zasady"
        >?</button>

        <a
          href="/profile"
          className="text-[12px] text-zinc-400 hover:text-white px-2.5 py-1.5 rounded-lg hover:bg-zinc-900 transition"
        >
          Zaloguj
        </a>
      </div>
    </div>
  )
}

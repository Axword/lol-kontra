'use client'
import { useState } from 'react'
import { sound, isSoundEnabled, toggleSound } from '@/lib/sound'

export default function TopBar({
  errorsLeft = 10,
  errorsTotal = 10,
  onMenu,
  onHelp,
  locale = 'pl',
  onLocaleChange
}: {
  errorsLeft?: number,
  errorsTotal?: number,
  onMenu: () => void,
  onHelp: () => void,
  locale?: string,
  onLocaleChange?: (l:string)=>void
}) {
  const [snd, setSnd] = useState(isSoundEnabled())

  const handleSound = () => {
    const n = toggleSound()
    setSnd(n)
    if(n) sound.click()
  }

  return (
    <div className="w-full">
      {/* upper row – slim, like kontra.games header */}
      <div className="h-[52px] px-3 sm:px-5 flex items-center justify-between bg-[#0d1117]/95 border-b border-zinc-800 backdrop-blur">
        {/* left: hamburger + lang */}
        <div className="flex items-center gap-3">
          <button
            onClick={onMenu}
            className="lg:hidden p-2 -ml-1 rounded-lg hover:bg-zinc-800 text-zinc-300"
            aria-label="Menu"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg>
          </button>

          {/* lang switch – PL | EN */}
          <div className="flex items-center bg-zinc-900 border border-zinc-800 rounded-full text-[11px] font-semibold overflow-hidden">
            {(['pl','en'] as const).map(l => (
              <button
                key={l}
                onClick={()=>{ onLocaleChange?.(l); sound.click() }}
                className={`px-2.5 py-1.5 uppercase transition ${locale===l ? 'bg-[#C89B3C] text-black' : 'text-zinc-400 hover:text-white'}`}
              >{l}</button>
            ))}
          </div>
          <div className="hidden sm:block text-[11px] text-zinc-500">League of Legends • Worlds XI</div>
        </div>

        {/* right: login */}
        <div className="flex items-center gap-2 sm:gap-3">
          <a href="/leaderboard" className="text-[12px] sm:text-[13px] text-zinc-300 hover:text-white px-3 py-1.5 rounded-lg hover:bg-zinc-900 transition">
            Moje wyniki
          </a>
          <a href="/profile" className="text-[12px] sm:text-[13px] bg-[#1a2330] border border-[#C89B3C]/30 text-[#E8C467] px-3 py-1.5 rounded-lg hover:bg-[#202b3a] transition hidden sm:inline-block">
            Profil
          </a>
        </div>
      </div>

      {/* second bar – game status */}
      <div className="px-3 sm:px-5 py-2.5 bg-[#0a0e13] border-b border-zinc-900 flex flex-wrap items-center justify-between gap-2">
        {/* left – score placeholder – will be injected by parent */}
        <div id="topbar-left-slot" className="flex items-center gap-3 min-h-[24px]"></div>

        {/* right – errors + sound + help */}
        <div className="flex items-center gap-2 sm:gap-3 ml-auto">
          {/* errors */}
          <div className="flex items-center gap-2 bg-[#11151c] border border-zinc-800 rounded-full px-3 py-1">
            <span className="text-[11px] text-zinc-400 hidden sm:inline">Błędy:</span>
            <span className="text-[13px] font-bold text-white">{errorsLeft}<span className="text-zinc-500">/{errorsTotal}</span></span>
            <div className="flex gap-[3px] ml-1">
              {Array.from({length: errorsTotal}).map((_,i)=>(
                <span key={i} className={`w-1.5 h-1.5 rounded-full ${i < errorsTotal - errorsLeft ? 'bg-red-500/70' : 'bg-emerald-500/80'}`} />
              ))}
            </div>
          </div>

          {/* sound */}
          <button
            onClick={handleSound}
            title={snd ? 'Wyłącz dźwięk' : 'Włącz dźwięk'}
            className={`p-[7px] rounded-full border transition ${snd ? 'border-zinc-700 text-zinc-300 hover:text-white bg-zinc-900' : 'border-zinc-800 text-zinc-500 bg-zinc-950'}`}
          >
            {snd ? (
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/></svg>
            ) : (
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><line x1="23" y1="9" x2="17" y2="15"/><line x1="17" y1="9" x2="23" y2="15"/></svg>
            )}
          </button>

          {/* help */}
          <button
            onClick={()=>{ sound.open(); onHelp() }}
            className="w-[30px] h-[30px] rounded-full border border-zinc-700 text-zinc-300 hover:text-white hover:border-zinc-500 bg-zinc-900 flex items-center justify-center text-[13px] font-bold"
            title="Pomoc / zasady"
          >?</button>
        </div>
      </div>
    </div>
  )
}

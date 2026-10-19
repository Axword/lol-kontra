'use client'
import { useId } from 'react'
import { usePrefs } from '@/lib/store'
import { sound } from '@/lib/sound'
import { useDialog } from './useDialog'

export default function HelpModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const locale = usePrefs((s) => s.locale)
  const pl = locale === 'pl'
  const dialogRef = useDialog<HTMLDivElement>(open, () => { sound.close(); onClose() })
  const titleId = useId()

  if (!open) return null

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
      <div className="absolute inset-0" style={{ background: 'rgba(24,36,28,.35)' }} onClick={() => { sound.close(); onClose() }} />
      <div ref={dialogRef} role="dialog" aria-modal="true" aria-labelledby={titleId} tabIndex={-1} className="relative flex max-h-[calc(100dvh-32px)] w-full max-w-xl flex-col border bg-white rise" style={{ borderColor: 'var(--line)' }}>
        <div className="flex items-center justify-between gap-4 border-b px-6 py-5 sm:px-8" style={{ borderColor: 'var(--line)' }}>
          <h2 id={titleId} className="text-[24px] font-semibold leading-tight">{pl ? 'Zasady' : 'How to play'}</h2>
          <button aria-label={pl ? 'Zamknij' : 'Close'} onClick={() => { sound.close(); onClose() }} className="flex h-10 w-10 shrink-0 items-center justify-center border text-[24px] leading-none transition-colors hover:bg-[#f0f4f0]" style={{ borderColor: 'var(--line)', color: 'var(--text-dim)' }}>
            &times;
          </button>
        </div>

        <div className="min-h-0 space-y-7 overflow-y-auto px-6 py-6 text-sm leading-relaxed sm:px-8 scroll-thin">
          <p style={{ color: 'var(--text-dim)' }}>
            {pl
              ? 'Dobierz pięciu zawodników, którzy wystąpili na Worlds. Każdy musi spełniać wszystkie warunki swojej pozycji.'
              : 'Pick five players who appeared at Worlds. Each must meet every condition of their position.'}
          </p>

          <ol className="space-y-3 pl-5" style={{ listStyle: 'decimal' }}>
            <li>{pl ? 'Wybierz pozycję na mapie lub kartę pod mapą na telefonie.' : 'Select a position on the map, or a card below it on mobile.'}</li>
            <li>{pl ? 'Trafienie zamyka pozycję na stałe.' : 'A correct answer locks that position.'}</li>
            <li>{pl ? 'Pomyłka kosztuje jedno z dziesięciu żyć – pozycja zostaje otwarta.' : 'A miss costs one of ten lives – the position stays open.'}</li>
            <li>{pl ? 'Gra kończy się po pięciu trafieniach albo po dziesięciu pomyłkach.' : 'The game ends after five hits or ten misses.'}</li>
          </ol>

          <p style={{ color: 'var(--text-dim)' }}>
            {pl
              ? 'WR i liczba gier dotyczą Worlds, łącznie z play-in. TOP 5 kariery i TOP 5 na Worlds to osobne warunki, liczone według liczby gier, z remisami na piątym miejscu. „Powyżej” i „poniżej” nie obejmują równej wartości.'
              : 'Win rate and game counts cover Worlds, including play-ins. Career top fives and Worlds top fives are separate conditions, based on games played, including ties for fifth. “Above” and “below” exclude an equal value.'}
          </p>

          <div>
            <h3 className="mb-3 text-base font-semibold">{pl ? 'Punktacja' : 'Scoring'}</h3>
            <p className="mb-5" style={{ color: 'var(--text-dim)' }}>
              {pl
                ? 'Im rzadziej wybierani zawodnicy, tym niższy wynik. Im mniej, tym lepiej.'
                : 'Rarer picks give you a lower score. Lower is better.'}
            </p>
            <p style={{ color: 'var(--text-dim)' }}>
              {pl
                ? 'Zaczynasz z 500 punktami — po 100 za każdą otwartą pozycję. Poprawny wybór zastępuje te 100 punktów swoim procentem popularności. Pięć wyborów po 1%, 2%, 3%, 4% i 5% daje końcowy wynik 15. Najlepszy możliwy wynik to 0.'
                : 'Start with 500 points — 100 for each open position. A correct pick replaces those 100 points with its pick percentage. Picks of 1%, 2%, 3%, 4% and 5% give a final score of 15. The best possible score is 0.'}
            </p>
            <p className="mt-4" style={{ color: 'var(--text-dim)' }}>
              {pl
                ? 'Po wyczerpaniu żyć każda nieuzupełniona pozycja pozostaje warta 100 punktów. Procenty zależą od wyborów uczestników, a końcowy wykres pokazuje Twój wynik na ich tle. Wyniki archiwalnych plansz też liczą się do ich rankingów.'
                : 'When you run out of lives, each unfilled position remains worth 100 points. Pick shares come from participants’ choices; the final chart compares your score with theirs. Archived boards also count towards their rankings.'}
            </p>
          </div>
        </div>

        <div className="shrink-0 border-t px-6 py-5 text-right sm:px-8" style={{ borderColor: 'var(--line)' }}>
          <button onClick={() => { sound.close(); onClose() }} className="btn btn-gold">
            {pl ? 'Zaczynam' : 'Got it'}
          </button>
        </div>
      </div>
    </div>
  )
}

'use client'
import { sound } from '@/lib/sound'
import { useEffect } from 'react'

export default function HelpModal({ open, onClose }: { open: boolean, onClose: () => void }) {
  useEffect(() => {
    const h = (e: KeyboardEvent) => { if(e.key==='Escape') { sound.close(); onClose() } }
    if(open) window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [open, onClose])

  if (!open) return null
  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/70" onClick={()=>{sound.close(); onClose()}} />
      <div className="relative w-full max-w-2xl bg-panel border border-line-strong rounded-console overflow-hidden">
        <div className="px-5 py-4 border-b border-line flex justify-between items-center">
          <h2 className="text-lg font-bold text-ink">Jak grać – Worlds XI</h2>
          <button onClick={()=>{sound.close(); onClose()}} className="text-muted hover:text-ink text-xl transition-colors">×</button>
        </div>
        <div className="p-5 space-y-4 text-[13.5px] leading-relaxed text-ink/90 max-h-[70vh] overflow-y-auto">
          <p><b className="text-ink">Cel:</b> Ułóż skład 5 zawodników League of Legends spełniających warunki na danej pozycji (Top / Jungle / Mid / ADC / Support).</p>
          <ol className="list-decimal pl-5 space-y-1">
            <li>Kliknij kartę roli – zobaczysz warunki, jakie musi spełniać zawodnik.</li>
            <li>Wyszukaj zawodnika – wpisz min. 2 litery nicku.</li>
            <li>Wybór jest weryfikowany <b>natychmiast</b>. Trafienie blokuje slot.</li>
            <li>Błędny wybór zabiera jedno z <b>10 żyć</b> – możesz próbować dalej (retry).</li>
            <li>Gra kończy się po skompletowaniu 5 poprawnych picków lub po 10 błędach.</li>
          </ol>

          <div className="bg-bg border border-line rounded-console p-3">
            <div className="font-semibold text-accent mb-2">Punktacja</div>
            <p className="text-[13px] mb-2">
              Startujesz z <b>500 pkt</b>. Każde trafienie <b>odejmuje</b> punkty –
              im rzadszy pick, tym więcej odejmiesz (<b className="text-accent">niższy wynik = lepszy</b>).
            </p>
            <ul className="text-ink/90 space-y-0.5 text-[13px]">
              <li>Strata = <b>100 − pick%</b> (np. pick 25% → -75 pkt)</li>
              <li><span className="r-common">Common</span> &gt;20% picków – np. 25% → <b>-75</b></li>
              <li><span className="r-rare">Rare</span> 10–20% – np. 15% → <b>-85</b></li>
              <li><span className="r-epic">Epic</span> 1–10% – np. 3% → <b>-97</b></li>
              <li><span className="r-legendary">Legendary</span> &lt;1% – np. 0.3% → <b>-99.7</b></li>
              <li><span className="text-ink font-semibold">◆ Diamond Pick</span> – najrzadszy poprawny pick w slocie → pełne <b>-100</b></li>
            </ul>
            <div className="text-[11px] text-muted mt-2">
              <b className="text-ink">Idealna gra</b> = 5×◆ = 0 pkt. Niższy wynik = lepszy.
            </div>
          </div>

          <div className="bg-bg border border-line rounded-console p-3">
            <div className="font-semibold text-ink mb-1">💡 Wskazówki</div>
            <ul className="text-[12.5px] text-ink/80 space-y-0.5">
              <li>• Im mniej oczywisty pick – tym lepszy wynik.</li>
              <li>• Faker odejmie mało (popularny). Zapomniany zawodnik z 2015 = Legendary.</li>
              <li>• Sprawdź historię drużyn i lata Worlds – tam są ukryte perełki.</li>
              <li>• Warunki na karcie roli <b>zawsze są widoczne</b> – czytaj je przed wyborem.</li>
            </ul>
          </div>

          <p className="text-[11px] text-muted">Dane: Leaguepedia • Nieoficjalny fanowski projekt • Not affiliated with Riot Games</p>
        </div>
        <div className="px-5 py-3 border-t border-line bg-surface/50 text-right">
          <button onClick={()=>{sound.close(); onClose()}} className="btn-coral text-sm px-4 py-2">Rozumiem</button>
        </div>
      </div>
    </div>
  )
}

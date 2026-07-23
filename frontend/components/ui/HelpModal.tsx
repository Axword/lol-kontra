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
      <div className="absolute inset-0 bg-black/75 backdrop-blur-sm" onClick={()=>{sound.close(); onClose()}} />
      <div className="relative w-full max-w-2xl bg-[#0f141b] border border-zinc-800 rounded-[20px] shadow-2xl overflow-hidden">
        <div className="px-5 py-4 border-b border-zinc-800 flex justify-between items-center">
          <h2 className="text-lg font-bold">Jak grać – Worlds XI</h2>
          <button onClick={()=>{sound.close(); onClose()}} className="text-zinc-400 hover:text-white text-xl">×</button>
        </div>
        <div className="p-5 space-y-4 text-[13.5px] leading-relaxed text-zinc-300 max-h-[70vh] overflow-y-auto">
          <p><b className="text-white">Cel:</b> Ułóż skład 5 zawodników League of Legends spełniających warunki na danej pozycji (Top / Jungle / Mid / ADC / Support).</p>
          <ol className="list-decimal pl-5 space-y-1">
            <li>Kliknij ikonę roli na mapie Rift.</li>
            <li>Wyszukaj zawodnika – zobaczysz flagę kraju, region, liczbę występów na Worlds.</li>
            <li>Wybór jest weryfikowany <b>natychmiast</b>. Trafienie blokuje slot.</li>
            <li>Błędny wybór zabiera jedno z <b>10 żyć</b> – możesz próbować dalej.</li>
            <li>Gra kończy się po skompletowaniu 5 poprawnych picków lub po 10 błędach.</li>
          </ol>
          <div className="bg-zinc-950 border border-zinc-800 rounded-xl p-3">
            <div className="font-semibold text-[#C89B3C] mb-1">Punktacja (styl kontra.games)</div>
            <ul className="text-zinc-300 space-y-0.5 text-[13px]">
              <li>Startujesz z <b>500 pkt</b> – każde trafienie <b>odejmuje</b> punkty.</li>
              <li>Strata = <b>100 − pick%</b> (im rzadszy pick, tym więcej odejmiesz).</li>
              <li>Common &gt;20% picków – np. 25% → <b>-75</b></li>
              <li><span className="text-[#3B82F6]">Rare 10–20%</span> – np. 15% → <b>-85</b></li>
              <li><span className="text-[#A855F7]">Epic 1–10%</span> – np. 3% → <b>-97</b></li>
              <li><span className="text-[#F59E0B]">Legendary &lt;1%</span> – np. 0.3% → <b>-99.7</b></li>
              <li><span className="text-[#22D3EE]">💎 Diamond Pick</span> – najrzadszy poprawny pick w slocie → pełne <b>-100</b></li>
            </ul>
            <div className="text-[11px] text-zinc-500 mt-1.5"><b className="text-zinc-300">Niższy wynik = lepszy.</b> Idealna gra = 5×💎 = 0 pkt.</div>
          </div>
          <p className="text-zinc-400">Im mniej oczywisty pick – tym lepszy wynik. Faker odejmie mało. Zapomniany zawodnik z 2015 w tych samych warunkach może dać Legendary.</p>
          <p className="text-[11px] text-zinc-500">Dane: Leaguepedia • Nieoficjalny fanowski projekt • Not affiliated with Riot Games</p>
        </div>
        <div className="px-5 py-3 border-t border-zinc-800 bg-zinc-950/50 text-right">
          <button onClick={()=>{sound.close(); onClose()}} className="btn-gold text-sm px-4 py-2">Rozumiem</button>
        </div>
      </div>
    </div>
  )
}

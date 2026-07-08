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
            <li>Wybierz – możesz zmienić do momentu wysłania całego składu.</li>
            <li><b>1 skład dziennie.</b> Masz 10 “żyć” – błędny wybór zabiera życie (UI).</li>
            <li>Po wysłaniu – wynik natychmiastowy (tryb instant).</li>
          </ol>
          <div className="bg-zinc-950 border border-zinc-800 rounded-xl p-3">
            <div className="font-semibold text-[#C89B3C] mb-1">Punktacja za rzadkość</div>
            <ul className="text-zinc-300 space-y-0.5 text-[13px]">
              <li>Common &gt;20% – <b>10 pkt</b></li>
              <li><span className="text-[#3B82F6]">Rare 10–20%</span> – <b>25 pkt</b></li>
              <li><span className="text-[#A855F7]">Epic 1–10%</span> – <b>60 pkt</b></li>
              <li><span className="text-[#F59E0B]">Legendary &lt;1%</span> – <b>120 pkt</b></li>
              <li><span className="text-[#22D3EE]">💎 Diamond Pick</span> – <b>+50 pkt</b> – pierwszy na świecie dany zawodnik danego dnia</li>
            </ul>
          </div>
          <p className="text-zinc-400">Im mniej oczywisty pick – tym więcej punktów. Faker da Ci Common 10 pkt. Duke w tych samych warunkach może dać Legendary 120 pkt.</p>
          <p className="text-[11px] text-zinc-500">Dane: Leaguepedia • Nieoficjalny fanowski projekt • Not affiliated with Riot Games</p>
        </div>
        <div className="px-5 py-3 border-t border-zinc-800 bg-zinc-950/50 text-right">
          <button onClick={()=>{sound.close(); onClose()}} className="btn-gold text-sm px-4 py-2">Rozumiem</button>
        </div>
      </div>
    </div>
  )
}

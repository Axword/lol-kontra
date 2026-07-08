'use client'
import { DailySlot } from '@/lib/api'
import PlayerSearch from './PlayerSearch'
import { useRosterStore } from '@/lib/store'

const roleLabels: Record<string, string> = {
  top: 'Top',
  jungle: 'Jungle',
  mid: 'Mid',
  adc: 'ADC',
  support: 'Support'
}

export default function SlotCard({ slot, disabled }: { slot: DailySlot, disabled?: boolean }) {
  const pick = useRosterStore(s => s.picks[slot.id])
  const clearPick = useRosterStore(s => s.clearPick)

  return (
    <div className="card-lol">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="text-xs uppercase tracking-wider text-lol-muted">{roleLabels[slot.role] || slot.role}</div>
          <div className="flex flex-wrap gap-2 mt-2">
            {slot.conditions.map(c => (
              <span key={c.id} className="pill">{c.label_pl}</span>
            ))}
          </div>
        </div>
        {pick?.playerNickname && (
          <button onClick={()=>clearPick(slot.id)} disabled={disabled} className="text-xs text-lol-muted hover:text-white">usuń</button>
        )}
      </div>
      <div className="mt-3">
        {pick?.playerNickname ? (
          <div className="flex items-center gap-3 bg-black/30 rounded-xl px-4 py-3 border border-zinc-800">
            <div className="w-9 h-9 rounded-full bg-zinc-800 flex items-center justify-center text-sm font-bold text-lol-gold">
              {pick.playerNickname.slice(0,2).toUpperCase()}
            </div>
            <div>
              <div className="font-semibold">{pick.playerNickname}</div>
              <div className="text-xs text-lol-muted">{pick.playerSlug}</div>
            </div>
          </div>
        ) : (
          <PlayerSearch role={slot.role} slotId={slot.id} disabled={!!disabled} />
        )}
      </div>
    </div>
  )
}

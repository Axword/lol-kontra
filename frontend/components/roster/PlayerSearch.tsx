'use client'
import { useState } from 'react'
import { usePlayerAutocomplete } from '@/lib/api'
import { useRosterStore } from '@/lib/store'

export default function PlayerSearch({ slotId, role, disabled }: { slotId: number, role?: string, disabled?: boolean }) {
  const [q, setQ] = useState('')
  const { data, isLoading } = usePlayerAutocomplete(q)
  const setPick = useRosterStore(s => s.setPick)

  return (
    <div className="relative">
      <input
        disabled={disabled}
        value={q}
        onChange={e=>setQ(e.target.value)}
        placeholder={`Szukaj gracza ${role ? '('+role+')' : ''}…`}
        className="w-full bg-zinc-900 border border-zinc-800 rounded-xl px-4 py-3 outline-none focus:border-lol-gold"
      />
      {q.length >= 1 && (
        <div className="absolute z-20 mt-1 w-full bg-zinc-950 border border-zinc-800 rounded-xl max-h-72 overflow-auto shadow-xl">
          {isLoading && <div className="p-3 text-sm text-lol-muted">Szukam…</div>}
          {data?.map(p => (
            <button
              key={p.slug}
              onClick={()=>{ setPick(slotId, p.slug, p.nickname); setQ('') }}
              className="w-full text-left px-4 py-2 hover:bg-zinc-900 flex justify-between"
            >
              <span className="font-medium">{p.nickname}</span>
              <span className="text-xs text-lol-muted">{p.primary_role.toUpperCase()} • {p.residency} • Worlds {p.worlds_count}</span>
            </button>
          ))}
          {data && data.length===0 && <div className="p-3 text-sm text-lol-muted">Brak wyników</div>}
        </div>
      )}
    </div>
  )
}

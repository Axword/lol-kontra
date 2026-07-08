'use client'
import { DailySlot } from '@/lib/api'
import { roleNamesPl, countryFlag } from '@/lib/flags'
import { useRosterStore } from '@/lib/store'
import Image from 'next/image'
import { useState } from 'react'

type Props = {
  slots: DailySlot[]
  onPick: (slot: DailySlot) => void
  disabled?: boolean
}

// Role icon component – loads SVG from /public/roles/
function RoleIcon({ role, filled, size=44 }: { role: string, filled?: boolean, size?: number }) {
  const src = `/roles/${role}.svg`
  return (
    <div
      className="relative flex items-center justify-center rounded-full"
      style={{
        width: size,
        height: size,
        background: filled 
          ? 'radial-gradient(circle, rgba(200,155,60,0.25) 0%, rgba(10,14,19,0.9) 70%)'
          : 'radial-gradient(circle, rgba(30,35,45,0.9) 0%, rgba(10,14,19,0.95) 70%)',
        boxShadow: filled ? '0 0 18px rgba(200,155,60,0.35), inset 0 0 10px rgba(200,155,60,0.15)' : '0 0 0 1px #2a2f3a inset',
        border: filled ? '2px solid #C89B3C' : '2px solid #3a3f4a'
      }}
    >
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={src}
        alt={role}
        width={size * 0.62}
        height={size * 0.62}
        style={{
          filter: filled 
            ? 'brightness(1.2) sepia(0.3) saturate(1.3) hue-rotate(-10deg)'
            : 'grayscale(1) brightness(0.75)',
          opacity: filled ? 1 : 0.85
        }}
        draggable={false}
      />
    </div>
  )
}

export default function RiftBoard({ slots, onPick, disabled }: Props) {
  const picks = useRosterStore(s => s.picks)
  const clearPick = useRosterStore(s => s.clearPick)
  const [hoverRole, setHoverRole] = useState<string | null>(null)

  const byRole: Record<string, DailySlot | undefined> = {}
  slots.forEach(s => { byRole[s.role] = s })

  const positions = [
    { role: 'top',     left: '14%', top: '18%', label: 'TOP' },
    { role: 'jungle',  left: '30%', top: '42%', label: 'JUNGLE' },
    { role: 'mid',     left: '52%', top: '50%', label: 'MID' },
    { role: 'adc',     left: '72%', top: '72%', label: 'ADC' },
    { role: 'support', left: '82%', top: '84%', label: 'SUP' },
  ] as const

  return (
    <div className="relative w-full rounded-[20px] border border-[#2a2d35] overflow-hidden bg-[#05070a] shadow-2xl">
      {/* Map background */}
      <div className="relative w-full" style={{ aspectRatio: '1 / 1', maxHeight: '680px' }}>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src="/rift-map-gold.png"
          alt="Summoner's Rift"
          className="absolute inset-0 w-full h-full object-cover"
          style={{
            filter: 'brightness(0.72) contrast(1.05) saturate(0.9)',
            opacity: 0.95
          }}
          draggable={false}
        />
        {/* dark vignette */}
        <div className="absolute inset-0" style={{
          background: 'radial-gradient(ellipse at center, transparent 35%, rgba(5,7,10,0.35) 75%, rgba(5,7,10,0.6) 100%)'
        }}/>
        {/* gold outer glow */}
        <div className="absolute inset-0 rounded-[20px] pointer-events-none" style={{
          boxShadow: 'inset 0 0 40px rgba(200,155,60,0.07)'
        }}/>

        {/* Role nodes */}
        {positions.map(pos => {
          const slot = byRole[pos.role]
          if (!slot) return null
          const pick = picks[slot.id]
          const isHover = hoverRole === pos.role
          return (
            <div
              key={pos.role}
              className="absolute"
              style={{ left: pos.left, top: pos.top, transform: 'translate(-50%, -50%)' }}
              onMouseEnter={()=>setHoverRole(pos.role)}
              onMouseLeave={()=>setHoverRole(null)}
            >
              <button
                onClick={() => !disabled && onPick(slot)}
                disabled={disabled}
                className="group relative flex flex-col items-center transition-transform duration-150 hover:scale-105 focus:outline-none"
                style={{ filter: isHover ? 'drop-shadow(0 0 10px rgba(200,155,60,0.45))' : undefined }}
              >
                <RoleIcon role={pos.role} filled={!!pick} size={68} />
                {/* role label */}
                <div className="mt-1.5 text-center">
                  <div className="text-[10px] tracking-widest text-[#C8AC6E] font-semibold drop-shadow" style={{ textShadow: '0 1px 4px #000' }}>
                    {pos.label}
                  </div>
                  <div className="text-[11px] text-zinc-200 font-medium max-w-[120px] truncate drop-shadow" style={{ textShadow: '0 1px 3px #000' }}>
                    {pick?.playerNickname || <span className="text-zinc-400">— wybierz —</span>}
                  </div>
                </div>

                {/* tooltip with conditions on hover */}
                <div className={`absolute left-1/2 -translate-x-1/2 ${pos.top?.includes('7') || pos.top?.includes('8') ? 'bottom-[100%] mb-2' : 'top-[100%] mt-2'} 
                  ${isHover ? 'opacity-100' : 'opacity-0 pointer-events-none'} 
                  transition-opacity duration-150 z-30 w-64`}>
                  <div className="bg-[#0f141b]/95 border border-[#C89B3C]/30 rounded-xl px-3 py-2 backdrop-blur text-left shadow-xl">
                    <div className="text-[11px] text-[#C8AC6E] font-semibold mb-1">
                      {roleNamesPl[pos.role as keyof typeof roleNamesPl]} – warunki:
                    </div>
                    <ul className="space-y-0.5">
                      {slot.conditions.map(c => (
                        <li key={c.id} className="text-[11px] text-zinc-300">• {c.label_pl}</li>
                      ))}
                    </ul>
                    {pick && (
                      <div className="mt-1.5 pt-1.5 border-t border-zinc-800 text-[10px] text-emerald-400">
                        Wybrany: {pick.playerNickname}
                      </div>
                    )}
                  </div>
                </div>
              </button>

              {/* clear X */}
              {pick && !disabled && (
                <button
                  onClick={(e)=>{ e.stopPropagation(); clearPick(slot.id)}}
                  className="absolute -top-1 -right-1 w-5 h-5 rounded-full bg-[#0b0f14] border border-[#C89B3C]/50 text-[#C89B3C] text-[11px] flex items-center justify-center hover:bg-[#C89B3C] hover:text-black transition"
                  title="Usuń wybór"
                >×</button>
              )}

              {/* pulse when empty */}
              {!pick && !disabled && (
                <div className="absolute inset-0 rounded-full pointer-events-none animate-ping opacity-[0.07]" style={{ background: '#C89B3C' }} />
              )}
            </div>
          )
        })}

        {/* Top bar – title */}
        <div className="absolute top-3 left-1/2 -translate-x-1/2 px-4 py-1.5 rounded-full bg-black/55 border border-[#C89B3C]/25 backdrop-blur text-center">
          <div className="text-[10px] tracking-[0.2em] text-[#C8AC6E]">WORLDS XI</div>
          <div className="text-[11px] text-zinc-300">Kliknij ikonę roli → wybierz zawodnika</div>
        </div>
      </div>

      {/* Bottom conditions strip – desktop */}
      <div className="hidden md:block bg-[#0a0e13]/95 border-t border-zinc-800 px-4 py-3">
        <div className="grid grid-cols-5 gap-3 text-[11px]">
          {(['top','jungle','mid','adc','support'] as const).map(r => {
            const slot = byRole[r]
            const pick = slot ? picks[slot.id] : undefined
            if (!slot) return <div key={r}/>
            return (
              <div key={r} className="min-w-0">
                <div className="text-[#C8AC6E] uppercase tracking-wider text-[10px] mb-0.5">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={`/roles/${r}.svg`} alt="" className="inline w-3 h-3 mr-1 opacity-80 align-[-2px]" style={{filter:'brightness(1.1)'}} />
                  {r}
                </div>
                <div className="text-zinc-200 truncate font-medium">
                  {pick?.playerNickname || <span className="text-zinc-500">—</span>}
                </div>
                <div className="text-zinc-500 truncate">
                  {slot.conditions.map(c=>c.label_pl).join(' • ')}
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

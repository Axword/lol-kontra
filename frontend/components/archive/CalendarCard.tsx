'use client'
import Link from 'next/link'
import { sound } from '@/lib/sound'

type Props = {
  id: number,
  date: string, // YYYY-MM-DD
  solved?: boolean,
  score?: number | null,
  isToday?: boolean,
}

const monthsPl = ['STY', 'LUT', 'MAR', 'KWI', 'MAJ', 'CZE', 'LIP', 'SIE', 'WRZ', 'PAŹ', 'LIS', 'GRU']
const weekdaysPl = ['N', 'Pn', 'Wt', 'Śr', 'Cz', 'Pt', 'Sb']

export default function CalendarCard({ id, date, solved, score, isToday }: Props) {
  const d = new Date(date + 'T12:00:00')
  const day = d.getDate()
  const month = monthsPl[d.getMonth()] || ''
  const weekday = weekdaysPl[d.getDay()] || ''
  const year = d.getFullYear()

  return (
    <Link
      href={`/daily/${id}`}
      onClick={() => sound.click()}
      className={`group block transition-transform duration-150 hover:scale-[1.02] focus:outline-none`}
    >
      <div className={`relative bg-panel border rounded-console overflow-hidden
        ${isToday ? 'border-accent' : 'border-line'}`}>

        {/* header strip */}
        <div className="px-3 py-1.5 border-b border-line flex items-center justify-between">
          <span className="text-[10px] tracking-[0.15em] font-semibold text-accent">{month} {year}</span>
          <span className="text-[10px] text-muted uppercase">{weekday}</span>
        </div>

        {/* date body */}
        <div className="text-center py-3 px-2">
          <div className="text-[34px] font-extrabold leading-none tracking-tighter text-ink mono">{day}</div>
          <div className="text-[10px] text-muted mt-1">Daily #{id}</div>
        </div>

        {/* footer */}
        <div className="border-t border-line px-2.5 py-[7px] text-[11px]">
          {solved ? (
            <div className="flex items-center justify-between text-warn font-semibold">
              <span>✓ rozwiązane</span>
              <span className="text-ink">{score ?? '—'} pkt</span>
            </div>
          ) : isToday ? (
            <div className="text-accent font-semibold text-center tracking-wide">ZAGRAJ DZIŚ</div>
          ) : (
            <div className="text-muted text-center">zagraj</div>
          )}
        </div>
      </div>
    </Link>
  )
}

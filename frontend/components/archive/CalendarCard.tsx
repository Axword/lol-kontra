'use client'
import Link from 'next/link'
import { sound } from '@/lib/sound'

type Props = {
  id: number
  date: string
  status: string
  solved?: boolean
  score?: number | null
  isToday?: boolean
}

const monthsPl = ['sty','lut','mar','kwi','maj','cze','lip','sie','wrz','paź','lis','gru']
const weekdaysPl = ['nd','pn','wt','śr','cz','pt','sb']

export default function CalendarCard({ id, date, status, solved, score, isToday }: Props) {
  const d = new Date(date + 'T12:00:00')
  const day = d.getDate()
  const month = monthsPl[d.getMonth()] ?? ''
  const weekday = weekdaysPl[d.getDay()] ?? ''

  return (
    <Link
      href={`/daily/${id}`}
      onClick={() => sound.click()}
      className="group block focus:outline-none"
    >
      <div className={`
        relative flex flex-col items-center
        bg-[#0d1117] border rounded-xl overflow-hidden
        transition-all duration-150
        hover:border-[#C89B3C]/60 hover:bg-[#111822]
        ${isToday
          ? 'border-[#C89B3C]/70 shadow-[0_0_12px_rgba(200,155,60,0.15)]'
          : 'border-zinc-800'}
        ${solved ? 'border-emerald-800/50' : ''}
      `}>
        {/* month */}
        <div className={`w-full text-center py-1 text-[10px] font-semibold uppercase tracking-wider
          ${isToday ? 'bg-[#C89B3C] text-black' : 'bg-zinc-900 text-zinc-400'}`}>
          {month}
        </div>

        {/* day number */}
        <div className="py-2 text-center">
          <div className="text-[10px] text-zinc-500 uppercase">{weekday}</div>
          <div className={`text-[28px] font-bold leading-none mt-0.5 ${isToday ? 'text-[#C89B3C]' : 'text-zinc-200 group-hover:text-white'}`}>
            {day}
          </div>
          <div className="text-[9px] text-zinc-600 mt-1">#{id}</div>
        </div>

        {/* status strip */}
        <div className={`w-full text-center py-1 text-[10px]
          ${solved ? 'bg-emerald-950/60 text-emerald-400' : isToday ? 'bg-[#C89B3C]/10 text-[#C89B3C]' : 'bg-zinc-900/50 text-zinc-500'}`}>
          {solved ? (score != null ? `${score} pkt` : '✓') : isToday ? 'graj' : 'zagraj'}
        </div>
      </div>
    </Link>
  )
}

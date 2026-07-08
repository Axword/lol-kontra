'use client'
import Link from 'next/link'
import { sound } from '@/lib/sound'

type Props = {
  id: number,
  date: string, // YYYY-MM-DD
  status: string,
  solved?: boolean,
  score?: number | null,
  isToday?: boolean,
}

const monthsPl = ['STY','LUT','MAR','KWI','MAJ','CZE','LIP','SIE','WRZ','PAŹ','LIS','GRU']
const weekdaysPl = ['N','Pn','Wt','Śr','Cz','Pt','Sb']

export default function CalendarCard({ id, date, status, solved, score, isToday }: Props) {
  const d = new Date(date + 'T12:00:00')
  const day = d.getDate()
  const month = monthsPl[d.getMonth()] || ''
  const weekday = weekdaysPl[d.getDay()] || ''
  const year = d.getFullYear()

  return (
    <Link
      href={`/daily/${id}`}
      onClick={()=>sound.click()}
      className={`group block relative transition-transform hover:scale-[1.025] focus:outline-none`}
    >
      <div className={`
        relative bg-[#f7f3e9] text-[#1a1a1a] rounded-[14px] overflow-hidden
        border border-[#d6c9a8] shadow-[0_2px_10px_rgba(0,0,0,0.35)]
        ${isToday ? 'ring-2 ring-[#C89B3C] shadow-[0_0_18px_rgba(200,155,60,0.25)]' : ''}
      `}>
        {/* top red bar – calendar header */}
        <div className="bg-[#c0392b] text-white text-center py-[6px] relative">
          <div className="text-[10px] tracking-widest font-bold">{month} {year}</div>
          {/* binder rings */}
          <div className="absolute -top-[5px] left-[22%] w-[10px] h-[10px] bg-[#e8e0d0] rounded-full border border-[#b8a080] shadow-sm" />
          <div className="absolute -top-[5px] right-[22%] w-[10px] h-[10px] bg-[#e8e0d0] rounded-full border border-[#b8a080] shadow-sm" />
        </div>

        {/* date body */}
        <div className="text-center py-3 px-2 bg-[#fbf8f0]">
          <div className="text-[10px] text-zinc-500 uppercase tracking-wider">{weekday}</div>
          <div className="text-[34px] font-extrabold leading-none tracking-tighter text-[#1e1e1e] mt-0.5">{day}</div>
          <div className="text-[10px] text-zinc-500 mt-1">Daily #{id}</div>
        </div>

        {/* footer strip */}
        <div className="bg-[#f1e9d6] border-t border-[#e0d4b8] px-2.5 py-[7px] text-[11px]">
          {solved ? (
            <div className="flex items-center justify-between text-[#2d6a2d] font-semibold">
              <span>✓ rozwiązane</span>
              <span className="text-[#C89B3C]">{score ?? '—'} pkt</span>
            </div>
          ) : isToday ? (
            <div className="text-[#b67600] font-semibold text-center">▶ zagraj dziś</div>
          ) : (
            <div className="text-zinc-600 text-center">
              {status === 'scored' ? 'zakończone' : status}
              <span className="text-[#0a7d4a]"> • zagraj</span>
            </div>
          )}
        </div>

        {/* subtle paper texture overlay */}
        <div className="absolute inset-0 pointer-events-none opacity-[0.035]" style={{
          backgroundImage: `repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0,0,0,0.5) 2px, rgba(0,0,0,0.5) 3px)`
        }}/>
      </div>
    </Link>
  )
}

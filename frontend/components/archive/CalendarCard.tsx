'use client'
import Link from 'next/link'
import { usePrefs } from '@/lib/store'
import { Check, Minus } from 'lucide-react'

const MONTHS_PL = ['sty', 'lut', 'mar', 'kwi', 'maj', 'cze', 'lip', 'sie', 'wrz', 'paź', 'lis', 'gru']
const MONTHS_EN = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']

export default function CalendarCard({
  id, date, isToday, completed, compact = false,
}: {
  id: number
  date: string
  isToday?: boolean
  completed?: boolean
  compact?: boolean
}) {
  const locale = usePrefs((s) => s.locale)
  const d = new Date(date + 'T00:00:00')
  const months = locale === 'pl' ? MONTHS_PL : MONTHS_EN
  const status = completed === undefined ? '—' : completed ? (locale === 'pl' ? 'Zrobione' : 'Done') : (locale === 'pl' ? 'Niezrobione' : 'Not done')

  return (
    <Link
      href={isToday ? '/' : `/daily/${id}`}
      aria-current={isToday ? 'date' : undefined}
      aria-label={`${d.toLocaleDateString(locale === 'pl' ? 'pl-PL' : 'en-GB', { day: 'numeric', month: 'long', year: 'numeric' })} · ${status}`}
      className={`relative flex flex-col border text-center transition-colors ${compact ? 'min-h-[106px] w-[90px] shrink-0 px-2 py-3' : 'min-h-[132px] px-3 py-4'} ${isToday ? 'bg-[#eef5ef]' : 'bg-white hover:bg-[#eef4ef]'}`}
      style={{ borderColor: isToday ? 'var(--gold)' : 'var(--line)' }}
    >
      <div className="text-xs" style={{ color: 'var(--text-dim)' }}>
        {compact ? d.toLocaleDateString(locale === 'pl' ? 'pl-PL' : 'en-GB', { weekday: 'short' }).toUpperCase() : `${months[d.getMonth()]} ${d.getFullYear()}`}
      </div>
      <div className={`${compact ? 'my-2 text-[23px]' : 'my-3 text-[30px]'} font-semibold leading-none tabular`} style={{ color: isToday ? 'var(--gold)' : 'var(--text)' }}>{d.getDate()}{compact && d.getDate() === 1 && <span className="ml-1 text-[10px] font-normal" style={{ color: 'var(--text-faint)' }}>{months[d.getMonth()]}</span>}</div>
      <div
        className="mt-auto text-xs"
        style={{
          color: isToday ? 'var(--gold)' : 'var(--text-dim)',
        }}
      >
        {isToday ? (locale === 'pl' ? 'Dziś' : 'Today') : `#${id}`}
      </div>
      <div className="mt-2 flex items-center justify-center gap-1 text-[10px]" style={{ color: completed ? 'var(--gold)' : 'var(--text-faint)' }}>
        {completed === true ? <Check size={12} aria-hidden="true" /> : completed === false ? <Minus size={12} aria-hidden="true" /> : null}{status}
      </div>
    </Link>
  )
}

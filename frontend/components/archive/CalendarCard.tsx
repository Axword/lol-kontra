'use client'
import Link from 'next/link'
import { usePrefs } from '@/lib/store'

const MONTHS_PL = ['sty', 'lut', 'mar', 'kwi', 'maj', 'cze', 'lip', 'sie', 'wrz', 'paź', 'lis', 'gru']
const MONTHS_EN = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']

export default function CalendarCard({
  id, date, isToday,
}: {
  id: number
  date: string
  isToday?: boolean
}) {
  const locale = usePrefs((s) => s.locale)
  const d = new Date(date + 'T00:00:00')
  const months = locale === 'pl' ? MONTHS_PL : MONTHS_EN

  return (
    <Link
      href={isToday ? '/' : `/daily/${id}`}
      aria-current={isToday ? 'date' : undefined}
      className={`flex min-h-[132px] flex-col border px-3 py-4 text-center transition-colors ${isToday ? 'bg-[#eef5ef]' : 'bg-white hover:bg-[#eef4ef]'}`}
      style={{ borderColor: isToday ? 'var(--gold)' : 'var(--line)' }}
    >
      <div className="text-xs" style={{ color: 'var(--text-dim)' }}>
        {months[d.getMonth()]} {d.getFullYear()}
      </div>
      <div className="my-3 text-[30px] font-semibold leading-none tabular" style={{ color: isToday ? 'var(--gold)' : 'var(--text)' }}>{d.getDate()}</div>
      <div
        className="mt-auto text-xs"
        style={{
          color: isToday ? 'var(--gold)' : 'var(--text-dim)',
        }}
      >
        {isToday ? (locale === 'pl' ? 'Dziś' : 'Today') : `#${id}`}
      </div>
    </Link>
  )
}

'use client'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useEffect, useState } from 'react'
import { Archive, CalendarDays, Trophy, User, X } from 'lucide-react'
import { usePrefs } from '@/lib/store'
import { useDialog } from '../ui/useDialog'

const links = [
  { href: '/', pl: 'Dzisiejsza plansza', en: "Today's board", icon: CalendarDays },
  { href: '/archiwum', pl: 'Archiwum', en: 'Archive', icon: Archive },
  { href: '/leaderboard', pl: 'Ranking', en: 'Leaderboard', icon: Trophy },
  { href: '/profile', pl: 'Profil', en: 'Profile', icon: User },
]

export default function Sidebar({ open, onClose }: { open: boolean; onClose: () => void }) {
  const pathname = usePathname()
  const locale = usePrefs((s) => s.locale)
  const [mobile, setMobile] = useState(false)
  const dialogRef = useDialog<HTMLElement>(open && mobile, onClose)
  useEffect(() => {
    const query = window.matchMedia('(max-width: 1023px)')
    const update = () => setMobile(query.matches)
    update()
    query.addEventListener('change', update)
    return () => query.removeEventListener('change', update)
  }, [])
  useEffect(() => { onClose() }, [pathname, onClose])

  return (
    <>
      <div
        aria-hidden="true"
        className={'fixed inset-0 z-40 lg:hidden transition-opacity ' + (open ? 'opacity-100' : 'opacity-0 pointer-events-none')}
        style={{ background: 'rgba(27,39,30,.28)' }}
        onClick={onClose}
      />
      <aside
        ref={dialogRef}
        role={open && mobile ? 'dialog' : undefined}
        aria-modal={open && mobile ? true : undefined}
        aria-label={locale === 'pl' ? 'Nawigacja' : 'Navigation'}
        tabIndex={-1}
        className={'fixed lg:sticky top-0 left-0 h-[100dvh] z-50 w-[220px] max-w-[90vw] shrink-0 flex flex-col overflow-y-auto border-r transition-transform duration-200 ' +
          (open ? 'translate-x-0 visible' : '-translate-x-full invisible lg:visible lg:translate-x-0')}
        style={{ background: '#fff', borderColor: 'var(--line)' }}
      >
        <div className="h-14 shrink-0 px-6 flex items-center border-b" style={{ borderColor: 'var(--line)' }}>
          <Link href="/" onClick={onClose} className="font-bold text-[20px] tracking-[-.055em]" style={{ color: 'var(--text)' }}>WORDS V</Link>
          <button
            type="button"
            aria-label={locale === 'pl' ? 'Zamknij menu' : 'Close menu'}
            onClick={onClose}
            className="lg:hidden ml-auto -mr-2 h-9 w-9 flex items-center justify-center"
            style={{ color: 'var(--text-dim)' }}
          >
            <X size={18} strokeWidth={1.7} aria-hidden="true" />
          </button>
        </div>

        <nav className="p-3 pt-6 space-y-1" aria-label={locale === 'pl' ? 'Menu główne' : 'Main menu'}>
          {links.map((link) => {
            const active = link.href === '/'
              ? pathname === '/' || pathname.startsWith('/daily')
              : pathname === link.href || pathname.startsWith(link.href + '/')
            const Icon = link.icon
            return (
              <Link
                key={link.href}
                href={link.href}
                onClick={onClose}
                aria-current={active ? 'page' : undefined}
                className="min-h-11 px-3 flex items-center gap-3 border text-[13px] transition-colors"
                style={{
                  borderColor: active ? 'var(--line)' : 'transparent',
                  background: active ? '#f0f5f1' : 'transparent',
                  color: active ? 'var(--gold)' : 'var(--text-dim)',
                  fontWeight: active ? 600 : 400,
                }}
              >
                <Icon size={18} strokeWidth={1.7} aria-hidden="true" />
                <span>{locale === 'pl' ? link.pl : link.en}</span>
              </Link>
            )
          })}
        </nav>
      </aside>
    </>
  )
}

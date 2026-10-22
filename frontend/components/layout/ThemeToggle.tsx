'use client'
import { Moon, Sun } from 'lucide-react'
import { setTheme, useTheme } from '@/lib/theme'
import { usePrefs } from '@/lib/store'

export default function ThemeToggle() {
  const theme = useTheme()
  const pl = usePrefs(s => s.locale) === 'pl'
  const label = pl ? (theme === 'dark' ? 'Włącz jasny motyw' : 'Włącz ciemny motyw') : (theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode')
  return <button type="button" aria-label={label} title={label} aria-pressed={theme === 'dark'} onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')} className="shrink-0 h-9 w-9 flex items-center justify-center" style={{ color: 'var(--text-dim)' }}>
    {theme === 'dark' ? <Sun size={18} strokeWidth={1.7} aria-hidden /> : <Moon size={18} strokeWidth={1.7} aria-hidden />}
  </button>
}

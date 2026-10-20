import type { RarityTier } from './api'

export const rarityPalette = {
  common: { background: '#ffffff', text: '#536056', border: '#9aa79d' },
  uncommon: { background: '#baf0cf', text: '#187240', border: '#35a463' },
  rare: { background: '#d4e6fb', text: '#245b9e', border: '#5792d6' },
  epic: { background: '#e4c9f5', text: '#7850a5', border: '#a274d0' },
  legendary: { background: '#ffe58c', text: '#865900', border: '#d2a12d' },
  diamond: { background: '#dcf7ff', text: '#126d8c', border: '#35a9cc' },
} as const satisfies Record<RarityTier | 'diamond', { background: string; text: string; border: string }>

export function rarityForPercent(percent: number | null | undefined): RarityTier | null {
  if (typeof percent !== 'number' || !Number.isFinite(percent) || percent < 0 || percent > 100) return null
  if (percent < 2) return 'legendary'
  if (percent < 5) return 'epic'
  if (percent < 15) return 'rare'
  if (percent < 25) return 'uncommon'
  return 'common'
}

export function formatPickPercent(percent: number, locale: 'pl' | 'en'): string {
  const crossesTier = rarityForPercent(Math.round(percent * 10) / 10) !== rarityForPercent(percent)
  const formatter = new Intl.NumberFormat(locale, percent > 0 && percent < 0.1
    ? { maximumSignificantDigits: 2 }
    : { maximumFractionDigits: crossesTier ? 2 : 1 })
  // Keep a rounded label on its actual side of the rarity threshold.
  const displayPercent = crossesTier ? Math.floor(percent * 100) / 100 : percent
  return `${formatter.format(displayPercent)}%`
}

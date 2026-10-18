import type { RarityTier } from './api'

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

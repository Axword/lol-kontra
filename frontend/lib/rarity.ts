import type { RarityTier } from './api'

export const rarityPalette = {
  common: { background: 'var(--rarity-common-bg)', text: 'var(--rarity-common)', border: 'var(--rarity-common-border)' },
  uncommon: { background: 'var(--rarity-uncommon-bg)', text: 'var(--rarity-uncommon)', border: 'var(--rarity-uncommon-border)' },
  rare: { background: 'var(--rarity-rare-bg)', text: 'var(--rarity-rare)', border: 'var(--rarity-rare-border)' },
  epic: { background: 'var(--rarity-epic-bg)', text: 'var(--rarity-epic)', border: 'var(--rarity-epic-border)' },
  legendary: { background: 'var(--rarity-legendary-bg)', text: 'var(--rarity-legendary)', border: 'var(--rarity-legendary-border)' },
  diamond: { background: 'var(--rarity-diamond-bg)', text: 'var(--rarity-diamond)', border: 'var(--rarity-diamond-border)' },
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

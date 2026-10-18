import { Gem } from 'lucide-react'
import { rarityLabel } from '@/lib/flags'
import { formatPickPercent, rarityForPercent } from '@/lib/rarity'

type Props = {
  percent: number | null | undefined
  locale: 'pl' | 'en'
  className?: string
  isDiamond?: boolean
}

export default function RarityIndicator({ percent, locale, className = '', isDiamond = false }: Props) {
  const rarity = rarityForPercent(percent)
  if (!rarity || percent == null) return null
  const tier = isDiamond ? 'diamond' : rarity
  return <span className={`rarity-indicator rarity-${tier} tabular ${className}`}
    data-rarity={tier} title={rarityLabel(tier, locale)}>
    {isDiamond && <Gem size={12} strokeWidth={1.8} role="img"
      aria-label={locale === 'pl' ? 'Diamentowy wybór' : 'Diamond pick'} className="rarity-diamond shrink-0" />}
    <span>{formatPickPercent(percent, locale)}</span>
  </span>
}

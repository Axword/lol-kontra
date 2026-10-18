import { Gem } from 'lucide-react'
import { rarityLabel } from '@/lib/flags'
import { formatPickPercent, rarityForPercent } from '@/lib/rarity'

type Props = {
  percent: number | null | undefined
  locale: 'pl' | 'en'
  className?: string
}

export default function RarityIndicator({ percent, locale, className = '' }: Props) {
  const tier = rarityForPercent(percent)
  if (!tier || percent == null) return null
  const diamond = percent === 0
  return <span className={`rarity-indicator rarity-${tier} tabular ${className}`}
    data-rarity={tier} title={rarityLabel(tier, locale)}>
    {diamond && <Gem size={12} strokeWidth={1.8} role="img"
      aria-label={locale === 'pl' ? 'Diamentowy wybór' : 'Diamond pick'} className="rarity-diamond shrink-0" />}
    <span>{formatPickPercent(percent, locale)}</span>
  </span>
}

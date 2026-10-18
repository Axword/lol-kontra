/**
 * Nazwy krajów i ról.
 *
 * Świadomie NIE ma tu emotikonowych flag ani ikon. Kraj pokazujemy jako
 * dwuliterowy kod w prostokątnej ramce (klasa `.country-code`) plus pełną nazwę,
 * a rolę jako płaskie SVG z /public/roles/ albo wersaliki.
 */

export const countryNames: Record<string, string> = {
  KR: 'Korea Południowa', CN: 'Chiny', TW: 'Tajwan', HK: 'Hongkong', MO: 'Makau',
  JP: 'Japonia', VN: 'Wietnam', TH: 'Tajlandia', SG: 'Singapur', MY: 'Malezja',
  PH: 'Filipiny', ID: 'Indonezja', AU: 'Australia', NZ: 'Nowa Zelandia',
  US: 'Stany Zjednoczone', CA: 'Kanada', MX: 'Meksyk', BR: 'Brazylia',
  AR: 'Argentyna', CL: 'Chile', PE: 'Peru', CO: 'Kolumbia', EC: 'Ekwador',
  DK: 'Dania', SE: 'Szwecja', NO: 'Norwegia', FI: 'Finlandia', IS: 'Islandia',
  DE: 'Niemcy', FR: 'Francja', ES: 'Hiszpania', PT: 'Portugalia', IT: 'Włochy',
  PL: 'Polska', CZ: 'Czechy', SK: 'Słowacja', HU: 'Węgry', RO: 'Rumunia',
  BG: 'Bułgaria', GR: 'Grecja', TR: 'Turcja', RU: 'Rosja', UA: 'Ukraina',
  BY: 'Białoruś', LT: 'Litwa', LV: 'Łotwa', EE: 'Estonia',
  NL: 'Holandia', BE: 'Belgia', GB: 'Wielka Brytania', IE: 'Irlandia',
  CH: 'Szwajcaria', AT: 'Austria', HR: 'Chorwacja', SI: 'Słowenia',
  RS: 'Serbia', BA: 'Bośnia i Hercegowina', MK: 'Macedonia Północna',
  IL: 'Izrael', AM: 'Armenia', KZ: 'Kazachstan',
}

export const countryNamesEn: Record<string, string> = {
  KR: 'South Korea', CN: 'China', TW: 'Taiwan', HK: 'Hong Kong', JP: 'Japan',
  VN: 'Vietnam', DK: 'Denmark', PL: 'Poland', DE: 'Germany', FR: 'France',
  ES: 'Spain', SE: 'Sweden', US: 'United States', CA: 'Canada', BR: 'Brazil',
  GB: 'United Kingdom', NL: 'Netherlands', BE: 'Belgium', TR: 'Turkey',
  HR: 'Croatia', SI: 'Slovenia', NO: 'Norway', FI: 'Finland', RO: 'Romania',
}

export function countryCode(code?: string): string {
  return (code || '').toUpperCase().slice(0, 3)
}

export function countryLabel(code?: string, locale: 'pl' | 'en' = 'pl'): string {
  if (!code) return ''
  const key = code.toUpperCase()
  const table = locale === 'en' ? countryNamesEn : countryNames
  if (table[key]) return table[key]
  try {
    return new Intl.DisplayNames([locale], { type: 'region' }).of(key) || key
  } catch {
    return key
  }
}

export const roleNames: Record<string, { pl: string; en: string }> = {
  top: { pl: 'Top', en: 'Top' },
  jungle: { pl: 'Dżungla', en: 'Jungle' },
  mid: { pl: 'Mid', en: 'Mid' },
  adc: { pl: 'Strzelec', en: 'Bot' },
  support: { pl: 'Wsparcie', en: 'Support' },
}

export function roleLabel(role: string, locale: 'pl' | 'en' = 'pl'): string {
  return roleNames[role]?.[locale] || role
}

export const ROLE_ORDER: Array<'top' | 'jungle' | 'mid' | 'adc' | 'support'> = [
  'top', 'jungle', 'mid', 'adc', 'support',
]

export const rarityNames: Record<string, { pl: string; en: string }> = {
  common: { pl: 'Popularny', en: 'Common' },
  rare: { pl: 'Rzadki', en: 'Rare' },
  epic: { pl: 'Epicki', en: 'Epic' },
  legendary: { pl: 'Legendarny', en: 'Legendary' },
}

export function rarityLabel(tier?: string | null, locale: 'pl' | 'en' = 'pl'): string {
  if (!tier) return ''
  return rarityNames[tier]?.[locale] || tier
}

export const rarityColor: Record<string, string> = {
  common: 'var(--rarity-common)',
  rare: 'var(--rarity-rare)',
  epic: 'var(--rarity-epic)',
  legendary: 'var(--rarity-legendary)',
  diamond: 'var(--rarity-diamond)',
}

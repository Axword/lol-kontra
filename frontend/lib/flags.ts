/**
 * Nazwy krajów, ról i rzadkości.
 *
 * Świadomie NIE ma tu emotikonowych flag. Emoji renderują się inaczej na
 * każdym systemie (na Windowsie flagi w ogóle nie działają i pokazują się jako
 * dwie litery w ramce), więc kraj pokazujemy jako dwuliterowy kod w ramce
 * (klasa `.cc`) plus pełną nazwę.
 */

export const countryNames: Record<string, { pl: string; en: string }> = {
  KR: { pl: 'Korea Południowa', en: 'South Korea' },
  CN: { pl: 'Chiny', en: 'China' },
  TW: { pl: 'Tajwan', en: 'Taiwan' },
  HK: { pl: 'Hongkong', en: 'Hong Kong' },
  MO: { pl: 'Makau', en: 'Macau' },
  JP: { pl: 'Japonia', en: 'Japan' },
  VN: { pl: 'Wietnam', en: 'Vietnam' },
  TH: { pl: 'Tajlandia', en: 'Thailand' },
  SG: { pl: 'Singapur', en: 'Singapore' },
  MY: { pl: 'Malezja', en: 'Malaysia' },
  PH: { pl: 'Filipiny', en: 'Philippines' },
  ID: { pl: 'Indonezja', en: 'Indonesia' },
  AU: { pl: 'Australia', en: 'Australia' },
  NZ: { pl: 'Nowa Zelandia', en: 'New Zealand' },
  US: { pl: 'Stany Zjednoczone', en: 'United States' },
  CA: { pl: 'Kanada', en: 'Canada' },
  MX: { pl: 'Meksyk', en: 'Mexico' },
  BR: { pl: 'Brazylia', en: 'Brazil' },
  AR: { pl: 'Argentyna', en: 'Argentina' },
  CL: { pl: 'Chile', en: 'Chile' },
  PE: { pl: 'Peru', en: 'Peru' },
  CO: { pl: 'Kolumbia', en: 'Colombia' },
  EC: { pl: 'Ekwador', en: 'Ecuador' },
  UY: { pl: 'Urugwaj', en: 'Uruguay' },
  DK: { pl: 'Dania', en: 'Denmark' },
  SE: { pl: 'Szwecja', en: 'Sweden' },
  NO: { pl: 'Norwegia', en: 'Norway' },
  FI: { pl: 'Finlandia', en: 'Finland' },
  IS: { pl: 'Islandia', en: 'Iceland' },
  DE: { pl: 'Niemcy', en: 'Germany' },
  FR: { pl: 'Francja', en: 'France' },
  ES: { pl: 'Hiszpania', en: 'Spain' },
  PT: { pl: 'Portugalia', en: 'Portugal' },
  IT: { pl: 'Włochy', en: 'Italy' },
  PL: { pl: 'Polska', en: 'Poland' },
  CZ: { pl: 'Czechy', en: 'Czechia' },
  SK: { pl: 'Słowacja', en: 'Slovakia' },
  HU: { pl: 'Węgry', en: 'Hungary' },
  RO: { pl: 'Rumunia', en: 'Romania' },
  BG: { pl: 'Bułgaria', en: 'Bulgaria' },
  GR: { pl: 'Grecja', en: 'Greece' },
  TR: { pl: 'Turcja', en: 'Türkiye' },
  RU: { pl: 'Rosja', en: 'Russia' },
  UA: { pl: 'Ukraina', en: 'Ukraine' },
  BY: { pl: 'Białoruś', en: 'Belarus' },
  LT: { pl: 'Litwa', en: 'Lithuania' },
  LV: { pl: 'Łotwa', en: 'Latvia' },
  EE: { pl: 'Estonia', en: 'Estonia' },
  NL: { pl: 'Holandia', en: 'Netherlands' },
  BE: { pl: 'Belgia', en: 'Belgium' },
  GB: { pl: 'Wielka Brytania', en: 'United Kingdom' },
  IE: { pl: 'Irlandia', en: 'Ireland' },
  CH: { pl: 'Szwajcaria', en: 'Switzerland' },
  AT: { pl: 'Austria', en: 'Austria' },
  HR: { pl: 'Chorwacja', en: 'Croatia' },
  SI: { pl: 'Słowenia', en: 'Slovenia' },
  RS: { pl: 'Serbia', en: 'Serbia' },
  BA: { pl: 'Bośnia i Hercegowina', en: 'Bosnia and Herzegovina' },
  MK: { pl: 'Macedonia Północna', en: 'North Macedonia' },
  IL: { pl: 'Izrael', en: 'Israel' },
  AM: { pl: 'Armenia', en: 'Armenia' },
  KZ: { pl: 'Kazachstan', en: 'Kazakhstan' },
}

export type Locale = 'pl' | 'en'

export function countryCode(code?: string): string {
  return (code || '').toUpperCase().slice(0, 3)
}

export function countryLabel(code?: string, locale: Locale = 'pl'): string {
  if (!code) return ''
  const key = code.toUpperCase()
  return countryNames[key]?.[locale] || key
}

export const roleNames: Record<string, { pl: string; en: string }> = {
  top: { pl: 'Top', en: 'Top' },
  jungle: { pl: 'Dżungla', en: 'Jungle' },
  mid: { pl: 'Mid', en: 'Mid' },
  adc: { pl: 'Strzelec', en: 'Bot' },
  support: { pl: 'Wsparcie', en: 'Support' },
}

export function roleLabel(role: string, locale: Locale = 'pl'): string {
  return roleNames[role]?.[locale] || role
}

/** Zachowane dla zgodności ze starszymi importami. */
export const roleNamesPl: Record<string, string> = {
  top: 'Top', jungle: 'Dżungla', mid: 'Mid', adc: 'Strzelec', support: 'Wsparcie',
}

export const rarityNames: Record<string, { pl: string; en: string }> = {
  common: { pl: 'Popularny', en: 'Common' },
  rare: { pl: 'Rzadki', en: 'Rare' },
  epic: { pl: 'Epicki', en: 'Epic' },
  legendary: { pl: 'Legendarny', en: 'Legendary' },
}

export function rarityLabel(tier?: string | null, locale: Locale = 'pl'): string {
  if (!tier) return ''
  return rarityNames[tier]?.[locale] || tier
}

/** Klasa CSS koloru dla tieru rzadkości (definicje w globals.css). */
export const rarityClass: Record<string, string> = {
  common: 'r-common',
  rare: 'r-rare',
  epic: 'r-epic',
  legendary: 'r-legendary',
  diamond: 'r-diamond',
}

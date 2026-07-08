// simple country code -> flag emoji + name
export const countryNames: Record<string, string> = {
  KR: 'Korea Południowa',
  CN: 'Chiny',
  US: 'USA',
  DK: 'Dania',
  DE: 'Niemcy',
  FR: 'Francja',
  PL: 'Polska',
  ES: 'Hiszpania',
  SE: 'Szwecja',
  CA: 'Kanada',
  BR: 'Brazylia',
  VN: 'Wietnam',
  TW: 'Tajwan',
  JP: 'Japonia',
  AU: 'Australia',
  TR: 'Turcja',
  RU: 'Rosja',
  NL: 'Holandia',
  BE: 'Belgia',
  GB: 'Wielka Brytania',
  NO: 'Norwegia',
  FI: 'Finlandia',
  HR: 'Chorwacja',
  SI: 'Słowenia',
  IT: 'Włochy',
  RO: 'Rumunia',
  PT: 'Portugalia',
  AR: 'Argentyna',
  CL: 'Chile',
  PE: 'Peru',
  MX: 'Meksyk',
  HK: 'Hong Kong',
  SG: 'Singapur',
  MY: 'Malezja',
  TH: 'Tajlandia',
  PH: 'Filipiny',
  ID: 'Indonezja',
}

export function countryFlag(code?: string): string {
  if (!code) return '🏳️'
  const cc = code.toUpperCase().slice(0,2)
  if (cc.length !== 2) return '🏳️'
  // regional indicator symbols
  const first = 127397 + cc.charCodeAt(0)
  const second = 127397 + cc.charCodeAt(1)
  try {
    return String.fromCodePoint(first, second)
  } catch {
    return '🏳️'
  }
}

export function countryLabel(code?: string, locale: 'pl'|'en'='pl'): string {
  if (!code) return ''
  return countryNames[code.toUpperCase()] || code.toUpperCase()
}

export const roleIcons: Record<string, string> = {
  top: '🛡️',
  jungle: '🌿',
  mid: '✨',
  adc: '🏹',
  support: '💚',
}

export const roleNamesPl: Record<string, string> = {
  top: 'Top',
  jungle: 'Dżungla',
  mid: 'Mid',
  adc: 'ADC',
  support: 'Support',
}

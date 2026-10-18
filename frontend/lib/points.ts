export function formatPoints(value: number, locale = 'pl') {
  return new Intl.NumberFormat(locale === 'pl' ? 'pl-PL' : 'en-US', { maximumFractionDigits: 2 }).format(value)
}

export function formatDeduction(value: number, locale = 'pl') {
  return value > 0 ? `−${formatPoints(value, locale)}` : '0'
}

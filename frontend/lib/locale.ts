export type Locale = 'pl' | 'en'

/** The first browser language is the player's preference; unsupported languages use English. */
export function deviceLocale(): Locale {
  if (typeof navigator === 'undefined') return 'en'
  const language = navigator.languages?.[0] || navigator.language
  return /^pl(?:-|$)/iu.test(language || '') ? 'pl' : 'en'
}

/** Localize only the generated prefix, preserving the player's nickname. */
export function guestDisplayName(name: string, locale: Locale) {
  return name.replace(/^(?:Gość|Guest)-/u, locale === 'pl' ? 'Gość-' : 'Guest-')
}

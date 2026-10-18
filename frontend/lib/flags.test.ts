import { describe, expect, it } from 'vitest'
import { countryLabel } from './flags'

describe('country translations', () => {
  it('translates countries missing from the English table instead of showing Polish', () => {
    expect(countryLabel('RU', 'en')).toBe('Russia')
    expect(countryLabel('TH', 'en')).toBe('Thailand')
    expect(countryLabel('CA', 'en')).toBe('Canada')
  })
  it('preserves Polish labels and normalizes country codes', () => {
    expect(countryLabel('ru', 'pl')).toBe('Rosja')
    expect(countryLabel('KR', 'en')).toBe('South Korea')
  })
  it('handles missing or unrecognized region codes without crashing the picker', () => {
    expect(countryLabel(undefined, 'en')).toBe('')
    expect(countryLabel('UNKNOWN', 'en')).toBe('UNKNOWN')
  })
})

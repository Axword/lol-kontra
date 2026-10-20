import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import { rarityPalette } from './rarity'

describe('accepted rarity palette', () => {
  it('keeps the inline palette identical to the existing CSS colors', () => {
    const css = readFileSync(resolve(process.cwd(), 'app/globals.css'), 'utf8')
    for (const [tier, colors] of Object.entries(rarityPalette)) {
      expect(css).toContain(`--rarity-${tier}: ${colors.text};`)
      expect(css).toContain(`.rarity-surface[data-rarity="${tier}"] { --rarity-bg: ${colors.background}; --rarity-border: ${colors.border}; }`)
    }
  })
})

import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import { rarityPalette } from './rarity'

describe('theme-aware rarity palette', () => {
  it('resolves every rarity label to readable colors in both themes', () => {
    const css = readFileSync(resolve(process.cwd(), 'app/globals.css'), 'utf8')
    const blocks = [...css.matchAll(/:root(?:\[data-theme="dark"\])?\s*\{([^}]+)\}/g)]
    let tokens: Record<string, string> = {}
    for (const block of blocks) {
      tokens = { ...tokens, ...Object.fromEntries([...block[1].matchAll(/(--[\w-]+):\s*(#[\da-f]+);/gi)].map(m => [m[1], m[2]])) }
      for (const colors of Object.values(rarityPalette)) {
        const resolveColor = (value: string) => tokens[value.slice(4, -1)]
        const text = resolveColor(colors.text)
        const background = resolveColor(colors.background)
        expect(text).toBeTruthy()
        expect(background).toBeTruthy()
        expect(contrast(text, background)).toBeGreaterThanOrEqual(4.5)
      }
    }
  })
})

function contrast(a: string, b: string) {
  const luminance = (hex: string) => hex.slice(1).match(/../g)!.map(x => parseInt(x, 16) / 255)
    .map(x => x <= .04045 ? x / 12.92 : ((x + .055) / 1.055) ** 2.4)
    .reduce((sum, x, i) => sum + x * [.2126, .7152, .0722][i], 0)
  const [light, dark] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (light + .05) / (dark + .05)
}

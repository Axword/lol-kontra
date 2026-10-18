import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import RarityIndicator from './RarityIndicator'

afterEach(cleanup)

describe('rarity percentage', () => {
  it('shows a miniature diamond for an exact zero without adding points or a visible tier label', () => {
    const { container } = render(<RarityIndicator percent={0} locale="pl" />)
    expect(screen.getByRole('img', { name: 'Diamentowy wybór' })).toBeTruthy()
    expect(container.textContent).toBe('0%')
    expect(container.firstElementChild?.getAttribute('title')).toBe('Złoty')
  })

  it.each([null, undefined, NaN, Infinity, -1, 101])('does not invent rarity for an unknown or invalid percentage %s', (percent) => {
    const { container } = render(<RarityIndicator percent={percent} locale="pl" />)
    expect(container.firstChild).toBeNull()
  })

  it.each([
    [9.09, '9,1%', 'Rzadki'], [1.99, '1,99%', 'Złoty'], [2, '2%', 'Epicki'],
    [4.99, '4,99%', 'Epicki'], [5, '5%', 'Rzadki'], [14.99, '14,99%', 'Rzadki'],
    [15, '15%', 'Pospolity'], [0.001, '0,001%', 'Złoty'],
    [1.9999, '1,99%', 'Złoty'], [4.9999, '4,99%', 'Epicki'], [14.9999, '14,99%', 'Rzadki'],
  ])('formats %s%% without rounding into a different rarity or implying a zero pick', (percent, display, label) => {
    const { container } = render(<RarityIndicator percent={Number(percent)} locale="pl" />)
    expect(container.textContent).toBe(display)
    expect(container.firstElementChild?.getAttribute('title')).toBe(label)
    expect(screen.queryByRole('img')).toBeNull()
  })

  it('uses English decimal formatting and labels', () => {
    const { container } = render(<RarityIndicator percent={9.09} locale="en" />)
    expect(container.textContent).toBe('9.1%')
    expect(container.firstElementChild?.getAttribute('title')).toBe('Rare')
  })
})

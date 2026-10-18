import { cleanup, fireEvent, render, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { DailySlot, GameAnswer } from '@/lib/api'
import RiftBoard from './RiftBoard'
import SlotList from './SlotList'

const prefs = vi.hoisted(() => ({ locale: 'pl' as 'pl' | 'en' }))
vi.mock('@/lib/store', () => ({
  usePrefs: (select: (state: typeof prefs) => unknown) => select(prefs),
}))

const slots: DailySlot[] = [
  { id: 11, position: 1, role: 'top', label_pl: 'Top', label_en: 'Top', conditions: [
    { id: 1, condition_type: 'country', operator: 'eq', value: 'KR', label_pl: 'Koreańczyk', label_en: 'Korean player' },
  ] },
  { id: 12, position: 2, role: 'mid', label_pl: 'Mid', label_en: 'Mid', conditions: [
    { id: 2, condition_type: 'worlds_champion', operator: 'eq', value: true, label_pl: 'Mistrz Worlds', label_en: 'Worlds champion' },
  ] },
  { id: 13, position: 3, role: 'jungle', label_pl: 'Dżungla', label_en: 'Jungle', conditions: [
    { id: 3, condition_type: 'country', operator: 'eq', value: 'DK', label_pl: 'Duńczyk', label_en: 'Danish player' },
  ] },
]

const solved: GameAnswer = {
  id: 1, daily_slot: 11, slot_role: 'top', player: 101, player_nickname: 'Zeus', player_slug: 'zeus',
  is_correct: true, rarity_tier: 'epic', rarity_percent: 4.25, points_awarded: -4.25, deduction: 4.25, is_diamond_pick: false,
}
const missed: GameAnswer = {
  id: 2, daily_slot: 13, slot_role: 'jungle', player: 102, player_nickname: 'Wrong player', player_slug: 'wrong',
  is_correct: false, rarity_tier: null, rarity_percent: null, points_awarded: 0, is_diamond_pick: false,
}
const answers = { 11: solved, 13: missed }

beforeEach(() => { prefs.locale = 'pl' })
afterEach(cleanup)

describe('the map and mobile roster show server answers', () => {
  it.each([false, true])('shows a portrait from the saved answer without a separate portraits map, inspect=%s', (inspect) => {
    const url = 'https://static.wikia.nocookie.net/lolesports_gamepedia/images/zeus.png'
    const answer = { ...solved, player_portrait_url: url }
    const { container, rerender } = render(<>
      <RiftBoard slots={slots} answers={{ 11: answer }} onPick={vi.fn()} inspect={inspect} />
      <SlotList slots={slots} answers={{ 11: answer }} onPick={vi.fn()} inspect={inspect} />
    </>)
    for (const selector of ['.rift-card', '.rift-marker', '.slot-list-mobile button']) {
      const card = container.querySelector(selector)!
      const image = card.querySelector('img')!
      expect(image.getAttribute('src')).toBe(url)
      expect(card.textContent).toContain('Zeus')
      fireEvent.error(image)
      expect(card.querySelector('img')?.getAttribute('src')).toBe('/roles/top.svg')
      expect(card.textContent).toContain('Zeus')
    }
    // Reconstructing the saved state on page load supplies the photo again.
    rerender(<>
      <RiftBoard key="reloaded-map" slots={slots} answers={{ 11: JSON.parse(JSON.stringify(answer)) }} onPick={vi.fn()} inspect={inspect} />
      <SlotList key="reloaded-list" slots={slots} answers={{ 11: JSON.parse(JSON.stringify(answer)) }} onPick={vi.fn()} inspect={inspect} />
    </>)
    expect(container.querySelectorAll(`img[src="${url}"]`).length).toBe(3)
  })

  it('falls back to role icons for absent portraits and never shows a wrong answer portrait', () => {
    const { container } = render(<>
      <RiftBoard slots={slots} answers={{ 11: { ...solved, player_portrait_url: null },
        13: { ...missed, player_portrait_url: 'https://example.com/wrong.png' } }} onPick={vi.fn()} />
      <SlotList slots={slots} answers={{ 11: { ...solved, player_portrait_url: null },
        13: { ...missed, player_portrait_url: 'https://example.com/wrong.png' } }} onPick={vi.fn()} />
    </>)
    for (const selector of ['.rift-card', '.rift-marker', '.slot-list-mobile button']) {
      expect(container.querySelector(selector)?.querySelector('img')?.getAttribute('src')).toBe('/roles/top.svg')
    }
    expect(container.querySelector('img[src="https://example.com/wrong.png"]')).toBeNull()
  })

  it('uses the saved answer portrait when a solutions portrait is null', () => {
    const url = 'https://example.com/zeus.png'
    const { container } = render(<RiftBoard slots={slots}
      answers={{ 11: { ...solved, player_portrait_url: url } }} portraits={{ 101: null }} onPick={vi.fn()} />)
    expect(container.querySelector('.rift-card img')?.getAttribute('src')).toBe(url)
  })

  it.each(['pl', 'en'] as const)('shows zero and positive candidate counts on mobile and announces them in %s', (locale) => {
    prefs.locale = locale
    const candidateCounts = { 11: 0, 12: 8 }
    const { container } = render(<>
      <RiftBoard slots={slots} answers={{}} onPick={vi.fn()} inspect candidateCounts={candidateCounts} />
      <SlotList slots={slots} answers={{}} onPick={vi.fn()} inspect candidateCounts={candidateCounts} />
    </>)
    const markers = container.querySelectorAll<HTMLElement>('.rift-marker')
    const rows = container.querySelectorAll<HTMLElement>('.slot-list-mobile button')
    for (const [index, count] of [0, 8].entries()) {
      expect(markers[index].querySelector('strong')?.textContent).toBe(String(count))
      expect(markers[index].getAttribute('aria-label')).toContain(`${count} ${locale === 'pl' ? 'pasujących zawodników' : 'matching players'}`)
      expect(rows[index].textContent).toContain(`· ${count} ${locale === 'pl' ? 'zawodników' : 'players'}`)
    }
    expect(markers[2].querySelector('strong')).toBeNull()
    expect(rows[2].textContent).not.toMatch(/zawodników|players/)
  })

  it.each(['pl', 'en'] as const)('shows conditions, the solved nickname and only the pick percentage in %s', (locale) => {
    prefs.locale = locale
    const { container } = render(<>
      <RiftBoard slots={slots} answers={answers} onPick={vi.fn()} />
      <SlotList slots={slots} answers={answers} onPick={vi.fn()} />
    </>)
    const cards = container.querySelectorAll<HTMLElement>('.rift-card')
    const mobileRows = container.querySelectorAll<HTMLElement>('.slot-list-mobile button')
    expect(cards.length).toBe(slots.length)
    expect(mobileRows.length).toBe(slots.length)
    slots.forEach((slot, index) => {
      const label = locale === 'pl' ? slot.conditions[0].label_pl : slot.conditions[0].label_en
      expect(within(cards[index]).getByText(label)).toBeTruthy()
      expect(within(container).getAllByRole('button', { name: cards[index].getAttribute('aria-label')!, description: label }).length).toBe(2)
      expect(within(mobileRows[index]).getByText(label)).toBeTruthy()
    })
    expect(within(cards[0]).getByText('Zeus')).toBeTruthy()
    expect(within(mobileRows[0]).getByText(/Zeus/)).toBeTruthy()
    const percent = locale === 'pl' ? '4,3%' : '4.3%'
    expect(within(cards[0]).getByText(percent)).toBeTruthy()
    expect(within(mobileRows[0]).getByText(percent)).toBeTruthy()
    expect(cards[0].textContent).not.toMatch(/pkt|pts|−4/)
    expect(mobileRows[0].textContent).not.toMatch(/pkt|pts|−4/)
  })

  it('does not invent a percentage when the answer has no official sample', () => {
    const { container } = render(<RiftBoard
      slots={slots} answers={{ 11: { ...solved, rarity_percent: null } }} onPick={vi.fn()}
    />)
    const card = container.querySelector<HTMLElement>('.rift-card')!
    expect(card.textContent).not.toMatch(/pkt|pts/)
    expect(card.textContent).not.toContain('%')
    expect(card.hasAttribute('data-rarity')).toBe(false)
  })

  it.each([
    [0, 'legendary'], [1.99, 'legendary'], [2, 'epic'], [4.99, 'epic'],
    [5, 'rare'], [9.09, 'rare'], [14.99, 'rare'], [15, 'uncommon'], [24.99, 'uncommon'], [25, 'common'], [100, 'common'],
  ])('uses the same rarity for %s%% while playing, reviewing and on mobile', (percent, tier) => {
    const { container } = render(<>
      <RiftBoard slots={slots} answers={{ 11: { ...solved, rarity_percent: Number(percent) } }} onPick={vi.fn()} />
      <RiftBoard slots={slots} answers={{ 11: { ...solved, rarity_percent: Number(percent) } }} onPick={vi.fn()} inspect />
      <SlotList slots={slots} answers={{ 11: { ...solved, rarity_percent: Number(percent) } }} onPick={vi.fn()} />
    </>)
    const surfaces = container.querySelectorAll('.rarity-surface[data-rarity]')
    expect(surfaces.length).toBe(5)
    surfaces.forEach((surface) => {
      expect(surface.getAttribute('data-rarity')).toBe(tier)
      expect(surface.textContent).not.toMatch(/pkt|pts/)
    })
    expect(container.querySelectorAll('svg[aria-label="Diamentowy wybór"]').length).toBe(0)
  })

  it.each([0, 1, 40, null])('keeps a historical first pick diamond at %s%% on the map and mobile', (percent) => {
    const answer = { ...solved, rarity_percent: percent, is_diamond_pick: true }
    const { container } = render(<>
      <RiftBoard slots={slots} answers={{ 11: answer }} onPick={vi.fn()} inspect />
      <SlotList slots={slots} answers={{ 11: answer }} onPick={vi.fn()} inspect />
    </>)
    const surfaces = container.querySelectorAll('.rarity-surface[data-rarity]')
    expect(surfaces.length).toBe(3)
    surfaces.forEach((surface) => expect(surface.getAttribute('data-rarity')).toBe('diamond'))
    expect(container.querySelectorAll('svg[aria-label="Diamentowy wybór"]').length).toBe(percent === null ? 0 : 3)
    expect(container.querySelector('[data-rarity="legendary"]')).toBeNull()
  })
})

describe('roster selection follows the server game state', () => {
  it.each([
    ['map cards', '.rift-card'],
    ['map markers', '.rift-marker'],
    ['mobile rows', '.slot-list-mobile button'],
  ])('opens only unsolved slots and blocks a finished game on %s', (_surface, selector) => {
    const onPick = vi.fn()
    const board = (disabled = false) => <>
      <RiftBoard slots={slots} answers={answers} onPick={onPick} disabled={disabled} />
      <SlotList slots={slots} answers={answers} onPick={onPick} disabled={disabled} />
    </>
    const view = render(board())
    const buttons = view.container.querySelectorAll<HTMLButtonElement>(selector)
    expect(buttons.length).toBe(slots.length)
    expect(Array.from(buttons, (button) => button.disabled)).toEqual([true, false, false])
    buttons.forEach((button) => fireEvent.click(button))
    expect(onPick.mock.calls).toEqual([[slots[1]], [slots[2]]])

    onPick.mockClear()
    view.rerender(board(true))
    view.container.querySelectorAll<HTMLButtonElement>(selector).forEach((button) => {
      expect(button.disabled).toBe(true)
      fireEvent.click(button)
    })
    expect(onPick).not.toHaveBeenCalled()
  })
})

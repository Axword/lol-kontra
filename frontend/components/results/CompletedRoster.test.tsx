import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { Daily, DailySolutions, GameState, Role, SolutionPlayer } from '@/lib/api'
import CompletedRoster from './CompletedRoster'

const prefs = vi.hoisted(() => ({ locale: 'pl' as 'pl' | 'en', guestToken: 'my-guest-token' }))
const query = vi.hoisted(() => ({
  data: undefined as DailySolutions | undefined,
  isLoading: false, isError: false, refetch: vi.fn(),
}))
const solutionsHook = vi.hoisted(() => vi.fn())
vi.mock('@/lib/api', () => ({ useDailySolutions: (...args: unknown[]) => solutionsHook(...args) }))
vi.mock('@/lib/store', () => ({ usePrefs: (select: (state: typeof prefs) => unknown) => select(prefs) }))

const roles: Role[] = ['top', 'jungle', 'mid', 'adc', 'support']
const daily: Daily = {
  id: 7, date: '2026-10-07', status: 'scored',
  slots: roles.map((role, index) => ({
    id: index + 11, position: index + 1, role, label_pl: role, label_en: role,
    conditions: [{ id: index + 1, condition_type: 'country', operator: 'eq', value: 'KR',
      label_pl: `Warunek ${index + 1}`, label_en: `Condition ${index + 1}` }],
  })),
}
const names = ['Faker', 'Zeus', 'Canyon', 'Ruler', 'Keria', 'BeryL', 'Darien', 'Deft']
const shares = [40, 25, 15, 10, 5, 3, 2, 0]
const players: SolutionPlayer[] = names.map((nickname, index) => ({
  id: index + 1, slug: nickname.toLowerCase(), nickname,
  portrait_url: index === 0 ? 'https://static.wikia.nocookie.net/lolesports_gamepedia/images/faker.png' : null,
  primary_role: 'mid', country_code: 'KR', residency: 'LCK', real_name: `Hidden real name ${index}`,
  pick_count: shares[index], pick_percent: shares[index],
}))
const mine = [1, 3, 5, 7, 8]
const popular = [1, 2, 3, 4, 5]
const rare = [4, 5, 6, 7, 8]
const data: DailySolutions = {
  daily_id: daily.id,
  slots: daily.slots.map((slot) => ({ slot_id: slot.id, role: slot.role, sample_size: 100, players })),
  popular: Object.fromEntries(daily.slots.map((slot, index) => [String(slot.id), popular[index]])),
  rare: Object.fromEntries(daily.slots.map((slot, index) => [String(slot.id), rare[index]])),
}
const state: GameState = {
  id: 1, daily: daily.id, total_points: 438, is_scored: true, is_practice: false,
  errors_used: 2, errors_left: 8, max_errors: 10, slots_total: 5, correct_count: 5, is_over: true,
  answers: daily.slots.map((slot, index) => {
    const player = players[mine[index] - 1]
    return { id: index + 1, daily_slot: slot.id, slot_role: slot.role, player: player.id,
      player_nickname: player.nickname, player_slug: player.slug, is_correct: true,
      rarity_tier: null, rarity_percent: player.pick_percent, points_awarded: -player.pick_percent,
      deduction: player.pick_percent, is_diamond_pick: false }
  }),
}

beforeEach(() => {
  prefs.locale = 'pl'
  query.data = data
  query.isLoading = false
  query.isError = false
  query.refetch.mockClear()
  solutionsHook.mockReturnValue(query)
})
afterEach(cleanup)

function selectedNames(container: HTMLElement) {
  return Array.from(container.querySelectorAll('.rift-card .rift-player-name'), (element) => element.textContent)
}

describe('completed roster choices', () => {
  it('keeps the historical roster and earned score while displaying current real pick percentages', () => {
    const historical = { ...state, total_points: 366.67,
      answers: state.answers.map((answer) => ({ ...answer, rarity_percent: 41.7, points_awarded: -41.7 })) }
    const snapshot = JSON.stringify(historical)
    const { container } = render(<CompletedRoster daily={daily} state={historical} />)
    expect(selectedNames(container)).toEqual(mine.map((id) => names[id - 1]))
    const card = container.querySelector<HTMLElement>('.rift-card')!
    expect(within(card).getByText('40%')).toBeTruthy()
    expect(container.textContent).not.toContain('41,7%')
    expect(JSON.stringify(historical)).toBe(snapshot)
    expect(historical.total_points).toBe(366.67)
  })

  it('switches between the actual, popular, rare and all answers without reusing players', () => {
    const { container } = render(<CompletedRoster daily={daily} state={state} />)
    expect(solutionsHook).toHaveBeenCalledWith(7, 'my-guest-token')
    const select = screen.getByRole('combobox', { name: 'Wyświetlany skład' })
    for (const [mode, ids] of [['mine', mine], ['popular', popular], ['rare', rare]] as const) {
      fireEvent.change(select, { target: { value: mode } })
      expect(selectedNames(container)).toEqual(ids.map((id) => names[id - 1]))
      expect(new Set(selectedNames(container)).size).toBe(5)
      container.querySelectorAll<HTMLButtonElement>('.rift-card').forEach((button) => expect(button.disabled).toBe(false))
    }
    fireEvent.change(select, { target: { value: 'all' } })
    expect(selectedNames(container)).toEqual([])
    container.querySelectorAll<HTMLElement>('.rift-card').forEach((card) => {
      expect(within(card).getByText('8 zawodników')).toBeTruthy()
    })
    container.querySelectorAll<HTMLElement>('.slot-list-mobile button').forEach((row) => {
      expect(within(row).getByText(/· 8 zawodników$/)).toBeTruthy()
    })
    container.querySelectorAll<HTMLElement>('.rift-marker').forEach((marker) => {
      expect(marker.getAttribute('aria-label')).toMatch(/8 pasujących zawodników$/)
      expect(marker.querySelector('strong')?.textContent).toBe('8')
    })
    fireEvent.change(select, { target: { value: 'mine' } })
    expect(selectedNames(container)).toEqual(mine.map((id) => names[id - 1]))
    expect(container.querySelector('.slot-list-mobile')?.textContent).not.toContain('8 zawodników')
    expect(container.querySelector('.rift-marker strong')).toBeNull()
    expect(state.answers.map((answer) => answer.player)).toEqual(mine)
  })

  it('opens solved roles with candidate nicknames, available photos and colored pick percentages', () => {
    const { container } = render(<CompletedRoster daily={daily} state={state} />)
    const card = container.querySelector<HTMLButtonElement>('.rift-card')!
    card.focus()
    fireEvent.click(card)
    const dialog = screen.getByRole('dialog', { name: 'Top' })
    expect(within(dialog).getByText('Warunek 1')).toBeTruthy()
    const input = within(dialog).getByRole('textbox', { name: 'Nick zawodnika' })
    expect(document.activeElement).toBe(input)
    const expectedTiers = ['common', 'common', 'common', 'rare', 'rare', 'epic', 'epic', 'legendary']
    for (const [index, player] of players.entries()) {
      const row = within(dialog).getByText(player.nickname).closest('li')!
      expect(row.textContent).toBe(`${player.nickname}${player.pick_percent}%`)
      expect(row.querySelector('[data-rarity]')?.getAttribute('data-rarity')).toBe(expectedTiers[index])
      expect(Boolean(within(row).queryByRole('img', { name: 'Diamentowy wybór' }))).toBe(player.pick_percent === 0)
      expect(row.querySelector('img')?.getAttribute('src') ?? null).toBe(player.portrait_url)
    }
    expect(dialog.textContent).not.toMatch(/Hidden real name|LCK|KR|pkt|pts/)
    const firstRow = within(dialog).getByText('Faker').closest('li')!
    fireEvent.error(firstRow.querySelector('img')!)
    expect(firstRow.querySelector('img')).toBeNull()
    expect(firstRow.textContent).toBe('Faker40%')
    fireEvent.change(input, { target: { value: '  cAnYoN  ' } })
    expect(within(dialog).getByText('Canyon')).toBeTruthy()
    expect(within(dialog).queryByText('Faker')).toBeNull()
    fireEvent.keyDown(input, { key: 'Escape' })
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(document.activeElement).toBe(card)
    expect(document.body.style.overflow).toBe('')
    fireEvent.click(card)
    expect((screen.getByRole('textbox', { name: 'Nick zawodnika' }) as HTMLInputElement).value).toBe('')
    expect(within(screen.getByRole('dialog')).getByText('Faker')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Zamknij' }))
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('keeps the actual roster usable while solutions are missing and offers an error retry', () => {
    query.data = undefined
    query.isLoading = true
    const view = render(<CompletedRoster daily={daily} state={state} />)
    expect(selectedNames(view.container)).toEqual(mine.map((id) => names[id - 1]))
    for (const label of ['Najrzadszy skład', 'Najpopularniejszy skład', 'Wszystkie odpowiedzi']) {
      expect((screen.getByRole('option', { name: label }) as HTMLOptionElement).disabled).toBe(true)
    }
    fireEvent.click(view.container.querySelector('.rift-card')!)
    expect(within(screen.getByRole('dialog')).getByRole('status').textContent).toBe('Wczytywanie odpowiedzi…')
    query.isLoading = false
    query.isError = true
    view.rerender(<CompletedRoster daily={daily} state={state} />)
    expect(within(screen.getByRole('dialog')).getByRole('alert')).toBeTruthy()
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Spróbuj ponownie' }))
    expect(query.refetch).toHaveBeenCalledOnce()
    query.isError = false
    query.data = data
    view.rerender(<CompletedRoster daily={daily} state={state} />)
    expect(screen.queryByRole('alert')).toBeNull()
    expect((screen.getByRole('option', { name: 'Najrzadszy skład' }) as HTMLOptionElement).disabled).toBe(false)
    const input = within(screen.getByRole('dialog')).getByRole('textbox', { name: 'Nick zawodnika' })
    fireEvent.change(input, { target: { value: 'no matching nickname' } })
    expect(within(screen.getByRole('dialog')).getByText('Brak wyników')).toBeTruthy()
  })

  it('localizes the roster switch and candidate search in English', () => {
    prefs.locale = 'en'
    const { container } = render(<CompletedRoster daily={daily} state={state} />)
    const select = screen.getByRole('combobox', { name: 'Displayed roster' })
    expect(within(select).getAllByRole('option').map((option) => option.textContent))
      .toEqual(['My roster', 'Rarest roster', 'Most popular roster', 'All answers'])
    fireEvent.change(select, { target: { value: 'all' } })
    expect(container.querySelector('.slot-list-mobile button')?.textContent).toContain('8 players')
    expect(container.querySelector('.rift-marker')?.getAttribute('aria-label')).toMatch(/8 matching players$/)
    fireEvent.click(container.querySelector('.rift-card')!)
    expect(within(screen.getByRole('dialog')).getByText('Condition 1')).toBeTruthy()
    const zeroPickRow = within(screen.getByRole('dialog')).getByText('Deft').closest('li')!
    expect(within(zeroPickRow).getByText('0%')).toBeTruthy()
    expect(within(zeroPickRow).getByRole('img', { name: 'Diamond pick' })).toBeTruthy()
    expect(screen.getByRole('textbox', { name: 'Player nickname' })).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Close' }))
    expect(screen.queryByRole('dialog')).toBeNull()
  })
})

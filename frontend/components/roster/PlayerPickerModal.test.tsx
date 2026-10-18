import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import PlayerPickerModal from './PlayerPickerModal'

const query = vi.hoisted(() => ({
  data: [{ id: 1, slug: 'zeus', nickname: 'Zeus', portrait_url: null as string | null, country_code: 'KR', residency: 'LCK', real_name: 'Choi Woo-je', primary_role: 'top' }],
  isFetching: false,
  isError: false,
  refetch: vi.fn(),
}))
vi.mock('@/lib/api', () => ({ usePlayerAutocomplete: () => query }))
vi.mock('@/lib/store', () => ({ usePrefs: (select: (state: {locale: string}) => unknown) => select({ locale: 'pl' }) }))
vi.mock('@/lib/sound', () => ({ sound: { pick: vi.fn() } }))

const slot = {
  id: 1, position: 1, role: 'top' as const, label_pl: 'Top', label_en: 'Top',
  conditions: [{ id: 1, condition_type: 'country', operator: 'eq', value: 'KR', label_pl: 'Koreańczyk', label_en: 'Korean' }],
}

afterEach(() => { cleanup(); vi.useRealTimers() })
beforeEach(() => {
  vi.useFakeTimers()
  query.isFetching = false
  query.isError = false
  query.refetch.mockClear()
  query.data[0].portrait_url = null
})

function search(text: string) {
  fireEvent.change(screen.getByRole('combobox'), { target: { value: text } })
  act(() => { vi.advanceTimersByTime(250) })
}

describe('player picker interaction', () => {
  it('shows only the nickname and an available portrait in search results', () => {
    query.data[0].portrait_url = 'https://static.wikia.nocookie.net/lolesports_gamepedia/images/test.png'
    render(<PlayerPickerModal slot={slot} open onClose={vi.fn()} onSelect={vi.fn()} />)
    search('zeus')
    const option = screen.getByRole('option')
    expect(option.textContent).toBe('Zeus')
    expect(option.querySelector('img')?.getAttribute('src')).toBe(query.data[0].portrait_url)
    expect(option.querySelector('svg')).toBeNull()
    expect(screen.queryByText(/Choi Woo-je|LCK|Korea Południowa/)).toBeNull()
    fireEvent.error(option.querySelector('img')!)
    expect(option.querySelector('img')).toBeNull()
    expect(option.textContent).toBe('Zeus')
  })
  it('focuses a labelled search field and restores scroll and focus on close', () => {
    const trigger = document.createElement('button')
    document.body.appendChild(trigger)
    trigger.focus()
    const view = render(<PlayerPickerModal slot={slot} open onClose={vi.fn()} onSelect={vi.fn()} />)
    expect(screen.getByRole('dialog').getAttribute('aria-modal')).toBe('true')
    expect(document.activeElement).toBe(screen.getByRole('combobox'))
    expect(document.body.style.overflow).toBe('hidden')
    view.unmount()
    expect(document.body.style.overflow).toBe('')
    expect(document.activeElement).toBe(trigger)
    trigger.remove()
  })

  it('selects a result with Enter only when the search field has focus', () => {
    const select = vi.fn()
    render(<PlayerPickerModal slot={slot} open onClose={vi.fn()} onSelect={select} />)
    search('zeus')
    fireEvent.keyDown(screen.getByRole('button', { name: 'Zamknij' }), { key: 'Enter' })
    expect(select).not.toHaveBeenCalled()
    fireEvent.keyDown(screen.getByRole('combobox'), { key: 'Enter' })
    expect(select).toHaveBeenCalledOnce()
    expect(select).toHaveBeenCalledWith(query.data[0])
  })

  it('blocks repeated keyboard and pointer submission while busy', () => {
    const select = vi.fn()
    const view = render(<PlayerPickerModal slot={slot} open onClose={vi.fn()} onSelect={select} />)
    search('zeus')
    view.rerender(<PlayerPickerModal slot={slot} open busy onClose={vi.fn()} onSelect={select} />)
    fireEvent.keyDown(screen.getByRole('combobox'), { key: 'Enter' })
    fireEvent.click(screen.getByRole('option'))
    expect(select).not.toHaveBeenCalled()
  })

  it('hides stale results and blocks Enter while a new search is loading', () => {
    query.isFetching = true
    const select = vi.fn()
    render(<PlayerPickerModal slot={slot} open onClose={vi.fn()} onSelect={select} />)
    search('zeus')
    fireEvent.keyDown(screen.getByRole('combobox'), { key: 'Enter' })
    expect(screen.queryByRole('option')).toBeNull()
    expect(select).not.toHaveBeenCalled()
  })

  it('traps keyboard focus and closes with Escape', () => {
    const close = vi.fn()
    render(<PlayerPickerModal slot={slot} open onClose={close} onSelect={vi.fn()} />)
    const input = screen.getByRole('combobox')
    fireEvent.keyDown(input, { key: 'Tab' })
    expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Zamknij' }))
    fireEvent.keyDown(document.activeElement!, { key: 'Escape' })
    expect(close).toHaveBeenCalledOnce()
  })

  it('shows a retry for search errors rather than an empty results message', () => {
    query.isError = true
    const select = vi.fn()
    render(<PlayerPickerModal slot={slot} open onClose={vi.fn()} onSelect={select} />)
    search('zeus')
    fireEvent.keyDown(screen.getByRole('combobox'), { key: 'Enter' })
    expect(select).not.toHaveBeenCalled()
    expect(screen.queryByRole('option')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Nie udało się wyszukać. Spróbuj ponownie.' }))
    expect(query.refetch).toHaveBeenCalledOnce()
    expect(screen.queryByText('Brak wyników')).toBeNull()
    expect(screen.queryByRole('option')).toBeNull()
  })

  it('announces feedback inside the open picker', () => {
    render(<PlayerPickerModal slot={slot} open error="Pozostało żyć: 9." onClose={vi.fn()} onSelect={vi.fn()} />)
    expect(screen.getByRole('alert').textContent).toContain('Pozostało żyć: 9.')
  })

  it('does not select a cached player after the search text is cleared', () => {
    const select = vi.fn()
    render(<PlayerPickerModal slot={slot} open onClose={vi.fn()} onSelect={select} />)
    search('zeus')
    search('')
    fireEvent.keyDown(screen.getByRole('combobox'), { key: 'Enter' })
    expect(select).not.toHaveBeenCalled()
    expect(screen.queryByRole('option')).toBeNull()
  })
})

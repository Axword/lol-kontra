import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, renderHook } from '@testing-library/react'
import { gameDate, isAvailableDaily, isValidDailyId, useGameDate } from './daily'
import { AxiosError, AxiosHeaders } from 'axios'
import { formatApiError, retryApiQuery } from './errors'

afterEach(() => { cleanup(); vi.useRealTimers() })

describe('game calendar', () => {
  it('switches at Warsaw midnight in summer and winter', () => {
    expect(gameDate(new Date('2026-07-01T21:59:59Z'))).toBe('2026-07-01')
    expect(gameDate(new Date('2026-07-01T22:00:00Z'))).toBe('2026-07-02')
    expect(gameDate(new Date('2026-01-01T22:59:59Z'))).toBe('2026-01-01')
    expect(gameDate(new Date('2026-01-01T23:00:00Z'))).toBe('2026-01-02')
  })
  it('handles the daylight-saving transition', () => {
    expect(gameDate(new Date('2026-10-24T22:00:00Z'))).toBe('2026-10-25')
    expect(gameDate(new Date('2026-10-25T22:00:00Z'))).toBe('2026-10-25')
    expect(gameDate(new Date('2026-10-25T23:00:00Z'))).toBe('2026-10-26')
  })
  it('rejects draft and future boards, but allows older published boards', () => {
    expect(isAvailableDaily({ date: '2026-10-18', status: 'published' }, '2026-10-17')).toBe(false)
    expect(isAvailableDaily({ date: '2026-10-16', status: 'draft' }, '2026-10-17')).toBe(false)
    for (const status of ['published', 'closed', 'scored']) expect(isAvailableDaily({ date: '2026-10-16', status }, '2026-10-17')).toBe(true)
  })
  it('accepts only positive safe integer board ids', () => {
    for (const value of [undefined, '7', 0, -1, 1.5, NaN, Infinity, Number.MAX_SAFE_INTEGER + 1]) expect(isValidDailyId(value)).toBe(false)
    expect(isValidDailyId(7)).toBe(true)
  })
  it('switches an open page at midnight and clears its clock on unmount', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-10-17T21:59:59Z'))
    const hook = renderHook(() => useGameDate())
    expect(hook.result.current).toBe('2026-10-17')
    act(() => { vi.advanceTimersByTime(1_000) })
    expect(hook.result.current).toBe('2026-10-18')
    hook.unmount()
    expect(vi.getTimerCount()).toBe(0)
  })
  it('refreshes the date immediately when a suspended tab regains focus', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-10-17T21:00:00Z'))
    const hook = renderHook(() => useGameDate())
    vi.setSystemTime(new Date('2026-10-18T21:00:00Z'))
    act(() => { window.dispatchEvent(new Event('focus')) })
    expect(hook.result.current).toBe('2026-10-18')
  })
})

function error(data: unknown, status = 400) {
  return new AxiosError('request failed', undefined, undefined, undefined, { data, status, statusText: '', headers: new AxiosHeaders(), config: { headers: new AxiosHeaders() } })
}
describe('request errors', () => {
  it('extracts DRF detail and field errors and preserves a network fallback', () => {
    expect(formatApiError(error({ detail: 'Gra zakończona', code: 'game_over' }), 'retry')).toBe('Gra zakończona')
    expect(formatApiError(error({ non_field_errors: ['Nieprawidłowy skład'] }), 'retry')).toBe('Nieprawidłowy skład')
    expect(formatApiError(error({ player_slug: ['Nie znaleziono gracza'] }), 'retry')).toBe('Nie znaleziono gracza')
    expect(formatApiError(new Error('network'), 'retry')).toBe('retry')
  })
  it('does not retry missing or invalid requests and bounds network retries', () => {
    expect(retryApiQuery(0, error({}, 404))).toBe(false)
    expect(retryApiQuery(0, error({}, 400))).toBe(false)
    expect(retryApiQuery(0, error({}, 503))).toBe(true)
    expect(retryApiQuery(0, new Error('offline'))).toBe(true)
    expect(retryApiQuery(2, new Error('offline'))).toBe(false)
  })
})

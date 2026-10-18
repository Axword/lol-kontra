import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import ScoreDistribution from './ScoreDistribution'

const result = vi.hoisted(() => ({ data: {} as any, isLoading: false, isError: false, refetch: vi.fn() }))
vi.mock('@/lib/api', () => ({ useScoreDistribution: () => result }))
vi.mock('@/lib/store', () => ({ usePrefs: (select: (state: { locale: string }) => unknown) => select({ locale: 'pl' }) }))
beforeEach(() => { result.data = { distribution: [], total_submissions: 0 }; result.isError = false })
afterEach(cleanup)

describe('score comparison', () => {
  it('shows a finalisation message without fabricating a histogram for an empty response', () => {
    render(<ScoreDistribution dailyId={7} userScore={60} />)
    expect(screen.getByText(/Pojawi się po przeliczeniu punktów/)).toBeTruthy()
    expect(screen.queryByText('Średnia')).toBeNull()
    expect(screen.queryByRole('button')).toBeNull()
  })
  it('offers a retry after a request fails', () => {
    result.isError = true
    render(<ScoreDistribution dailyId={7} userScore={60} />)
    fireEvent.click(screen.getByRole('button', { name: 'Spróbuj ponownie' }))
    expect(result.refetch).toHaveBeenCalledOnce()
    expect(screen.queryByText(/Pojawi się po przeliczeniu punktów/)).toBeNull()
  })
  it('highlights the same rounded score bucket used by the API', () => {
    result.data = { distribution: [{ score: 10, count: 1 }], total_submissions: 1 }
    render(<ScoreDistribution dailyId={7} userScore={9.9} />)
    const bar = screen.getByText('10–19: 1').parentElement?.firstElementChild as HTMLElement
    expect(bar.style.background).toBe('var(--gold)')
    fireEvent.click(screen.getByRole('button', { name: '5' }))
    expect(screen.getByText('10–14: 1')).toBeTruthy()
  })
  it('labels a practice score as a comparison rather than a ranked submission', () => {
    result.data = { distribution: [{ score: 10, count: 2 }], total_submissions: 2, rank: 3, avg_score: 10 }
    render(<ScoreDistribution dailyId={7} userScore={0} practice />)
    expect(screen.getByText('Pozycja porównawcza').nextElementSibling?.textContent).toBe('3')
    expect(screen.queryByText('3 / 2')).toBeNull()
    expect(screen.queryByText('Miejsce')).toBeNull()
  })
})

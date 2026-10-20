import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import PreviousChallenges from './PreviousChallenges'

const mocks = vi.hoisted(() => ({
  archive: { data: { results: [] as {id: number; date: string; status: string}[] }, isLoading: false, isError: false, refetch: vi.fn() },
  progress: { data: undefined as {results: {daily_id: number; completed: boolean}[]} | undefined, isError: false, refetch: vi.fn() },
}))
vi.mock('@/lib/api', () => ({ useArchive: () => mocks.archive }))
vi.mock('@/lib/challenge-calendar', () => ({useChallengeCalendar: () => ({...mocks.archive, data: {pages: [mocks.archive.data]}, hasNextPage: false})}))
vi.mock('@/lib/store', () => ({ usePrefs: (selector: (s: unknown) => unknown) => selector({locale: 'pl', guestToken: 'player'}) }))
vi.mock('@/lib/daily', () => ({useGameDate: () => '2026-10-20', isAvailableDaily: (daily: {date: string; status: string}, today: string) => daily.date <= today && daily.status === 'published'}))
vi.mock('@/lib/challenge-progress', async original => ({...await original<typeof import('@/lib/challenge-progress')>(), useChallengeProgress: () => mocks.progress}))
beforeEach(() => {
  mocks.archive.data.results = [{id: 19, date:'2026-10-19', status:'published'}, {id:18,date:'2026-10-18',status:'published'},
    {id:20,date:'2026-10-20',status:'published'}, {id:21,date:'2026-10-21',status:'published'}, {id:17,date:'2026-10-17',status:'draft'}]
  mocks.progress.data = {results:[{daily_id:18, completed:true}, {daily_id:19, completed:false}]}
  mocks.archive.isError = false; mocks.archive.isLoading = false; mocks.progress.isError = false
})
afterEach(cleanup)
describe('previous challenges calendar', () => {
  it('links only available boards, orders dates and shows personal completion markers', () => {
    render(<PreviousChallenges currentId={20} />)
    const links = screen.getAllByRole('link')
    expect(links.map(link => link.getAttribute('href'))).toEqual(['/archiwum','/daily/18','/daily/19'])
    expect(links[1].getAttribute('aria-label')).toContain('Zrobione')
    expect(links[2].getAttribute('aria-label')).toContain('Niezrobione')
  })
  it('does not claim an unfinished board when private progress failed', () => {
    mocks.progress.isError = true
    render(<PreviousChallenges currentId={20} />)
    expect(screen.queryByText('Zrobione')).toBeNull()
    expect(screen.queryByText('Niezrobione')).toBeNull()
    fireEvent.click(screen.getByRole('button', {name:'Wczytaj statusy ponownie'}))
    expect(mocks.progress.refetch).toHaveBeenCalledOnce()
  })
  it('offers a retry when the public calendar is offline', () => {
    mocks.archive.isError = true
    render(<PreviousChallenges currentId={20} />)
    expect(screen.queryByText('Brak wcześniejszych wyzwań.')).toBeNull()
    fireEvent.click(screen.getByRole('button', {name:'Wczytaj wyzwania ponownie'}))
    expect(mocks.archive.refetch).toHaveBeenCalledOnce()
  })
  it('allows dragging without opening a challenge and still allows a later click', () => {
    render(<PreviousChallenges currentId={20} />)
    const rail = screen.getByRole('group', {name:'Lista poprzednich wyzwań'})
    Object.assign(rail,{setPointerCapture:vi.fn(),hasPointerCapture:vi.fn(() => true),releasePointerCapture:vi.fn()})
    rail.scrollLeft = 250
    const pointer = (type:string, x:number) => {
      const event = new Event(type,{bubbles:true,cancelable:true})
      Object.defineProperties(event,{pointerId:{value:1},pointerType:{value:'mouse'},clientX:{value:x},button:{value:0}})
      fireEvent(rail,event)
    }
    pointer('pointerdown',100);pointer('pointermove',200);pointer('pointerup',200)
    expect(rail.scrollLeft).toBe(150)
    const challenge = screen.getAllByRole('link')[1]
    expect(fireEvent.click(challenge,{detail:1})).toBe(false)
    pointer('pointerdown',200);pointer('pointerup',200)
    const click = new MouseEvent('click',{bubbles:true,cancelable:true,detail:1})
    let allowed = false
    challenge.addEventListener('click',event => {allowed = !event.defaultPrevented;event.preventDefault()},{once:true})
    fireEvent(challenge,click)
    expect(allowed).toBe(true)
    expect(rail.className).not.toContain('cursor-grabbing')
  })
})

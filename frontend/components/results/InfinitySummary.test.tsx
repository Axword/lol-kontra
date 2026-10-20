import {cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest'
import InfinitySummary from './InfinitySummary'
import type {InfinityRun} from '@/lib/infinity'
const prefs=vi.hoisted(()=>({locale:'pl' as 'pl'|'en'}))
vi.mock('@/lib/store',()=>({usePrefs:(select:(s:typeof prefs)=>unknown)=>select(prefs)}))
const run:InfinityRun={id:'finished-run',board_id:'board',slots:[],answers:[],correct_count:23,completed_boards:4,errors_used:10,errors_left:0,max_errors:10,is_over:true,
  ranking_result:{periods:{daily:{rank:2,previous_rank:5,improved:true,best:23,total_players:8},
    weekly:{rank:1,previous_rank:1,improved:false,best:30,total_players:8},
    monthly:{rank:3,previous_rank:7,improved:true,best:23,total_players:8},
    all_time:{rank:8,previous_rank:null,improved:false,best:23,total_players:12}}}}
beforeEach(()=>{prefs.locale='pl'})
afterEach(cleanup)
describe('Infinity result popup',()=>{
  it.each(['pl','en'] as const)('shows four ranks, real promotions and the run score in %s',locale=>{
    prefs.locale=locale
    render(<InfinitySummary run={run} onRestart={vi.fn()} pending={false} error={false} />)
    const dialog=within(screen.getByRole('dialog'))
    expect(dialog.getByText('23')).toBeTruthy()
    expect(dialog.getByText(locale==='pl'?'Awans z #5 na #2':'Up from #5 to #2')).toBeTruthy()
    expect(dialog.queryByText(/#1.*#1/)).toBeNull()
    expect(dialog.getByRole('link',{name:locale==='pl'?'Miesięczny':'Monthly'}).getAttribute('href')).toBe('/infinity/leaderboard?period=monthly')
    expect(dialog.getAllByRole('listitem')).toHaveLength(4)
  })
  it('can be closed, reopened and restarted without changing the saved result',()=>{
    const start=vi.fn()
    render(<InfinitySummary run={run} onRestart={start} pending={false} error={false} />)
    fireEvent.click(screen.getByRole('button',{name:'Zamknij'}))
    expect(screen.queryByRole('dialog')).toBeNull()
    fireEvent.click(screen.getByRole('button',{name:'Twój wynik'}))
    expect(screen.getByText('Awans z #5 na #2')).toBeTruthy()
    fireEvent.click(screen.getByRole('button',{name:'Zagraj ponownie'}))
    expect(start).toHaveBeenCalledOnce()
  })
  it('does not invent an upgrade for a first or non-improving run',()=>{
    const data={...run,ranking_result:{periods:Object.fromEntries(Object.entries(run.ranking_result!.periods).map(([k,v])=>[k,{...v,previous_rank:null,improved:false}]))}} as InfinityRun
    render(<InfinitySummary run={data} onRestart={vi.fn()} pending={true} error={false} />)
    expect(screen.queryByText(/Awans/)).toBeNull()
    expect(screen.getByRole('button',{name:'Losowanie…'}).hasAttribute('disabled')).toBe(true)
  })
})

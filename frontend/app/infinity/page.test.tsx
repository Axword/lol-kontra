import { cleanup,fireEvent,render,screen } from '@testing-library/react'
import { afterEach,beforeEach,describe,expect,it,vi } from 'vitest'
import InfinityPage from './page'
import type { InfinityRun } from '@/lib/infinity'
const mocks=vi.hoisted(()=>({locale:'pl' as 'pl'|'en',query:{data:{run:null,personal_best:0} as {run:InfinityRun|null;personal_best:number},isLoading:false,isError:false,refetch:vi.fn()},start:{mutate:vi.fn(),isPending:false,isError:false},answer:{mutate:vi.fn(),isPending:false}}))
vi.mock('@/lib/store',()=>({usePrefs:(select:(s:unknown)=>unknown)=>select({locale:mocks.locale})}))
vi.mock('@/lib/guest-profile',()=>({useGuestToken:()=> 'same-guest'}))
vi.mock('@/lib/infinity',()=>({useInfinity:()=>mocks.query,useStartInfinity:()=>mocks.start,useInfinityAnswer:()=>mocks.answer}))
vi.mock('@/components/layout/GameLayout',()=>({default:({children}:{children:React.ReactNode})=><main>{children}</main>}))
vi.mock('@/components/roster/PlayerPickerModal',()=>({default:({open,onSelect,error}:{open:boolean;onSelect:(p:unknown)=>void;error:string|null})=>open?<div role="dialog"><button onClick={()=>onSelect({slug:'faker',nickname:'Faker'})}>Pick Faker</button>{error}</div>:null}))
vi.mock('@/lib/sound',()=>({sound:{open:vi.fn(),close:vi.fn(),success:vi.fn(),error:vi.fn()}}))
const run:InfinityRun={id:'existing-run',board_id:'existing-board',correct_count:14,completed_boards:2,errors_used:9,errors_left:1,max_errors:10,is_over:false,answers:[],slots:[{id:1,position:1,role:'mid',label_pl:'Mid',label_en:'Mid',conditions:[{id:1,condition_type:'worlds_final',operator:'eq',value:true,label_pl:'Grał w finale Worlds',label_en:'Played a Worlds final'}]}]}
beforeEach(()=>{mocks.locale='pl';mocks.query.data={run:null,personal_best:0};mocks.query.isLoading=false;mocks.query.isError=false})
afterEach(cleanup)
describe('Infinity game',()=>{
  it.each(['pl','en'] as const)('starts only after an explicit click and describes the shared error budget in %s',locale=>{
    mocks.locale=locale
    render(<InfinityPage />)
    expect(mocks.start.mutate).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button',{name:locale==='pl'?'Graj w Infinity':'Play Infinity'}))
    expect(mocks.start.mutate).toHaveBeenCalledOnce()
    expect(screen.getByRole('link',{name:locale==='pl'?'Ranking Infinity':'Infinity leaderboard'}).getAttribute('href')).toBe('/infinity/leaderboard')
  })
  it('resumes the server run with its remaining lives and sends the exact board identity',()=>{
    mocks.query.data={run,personal_best:18}
    render(<InfinityPage />)
    expect(screen.getByText('1 / 10')).toBeTruthy()
    expect(screen.getByText('14')).toBeTruthy()
    fireEvent.click(screen.getAllByRole('button',{name:'Mid – puste'})[0])
    fireEvent.click(screen.getByRole('button',{name:'Pick Faker'}))
    expect(mocks.answer.mutate.mock.calls[0][0]).toEqual({run_id:run.id,board_id:run.board_id,position:1,player_slug:'faker'})
  })
  it('closes an obsolete picker when another window advances the board',()=>{
    mocks.query.data={run,personal_best:18}
    const view=render(<InfinityPage />)
    fireEvent.click(screen.getAllByRole('button',{name:'Mid – puste'})[0])
    expect(screen.getByRole('dialog')).toBeTruthy()
    mocks.query.data={run:{...run,board_id:'next-board'},personal_best:18}
    view.rerender(<InfinityPage />)
    expect(screen.queryByRole('dialog')).toBeNull()
  })
  it('offers a new run only after the tenth error',()=>{
    mocks.query.data={run:{...run,is_over:true,errors_used:10,errors_left:0},personal_best:18}
    render(<InfinityPage />)
    expect(screen.getByText('Seria zakończona')).toBeTruthy()
    fireEvent.click(screen.getByRole('button',{name:'Zagraj ponownie'}))
    expect(mocks.start.mutate).toHaveBeenCalledOnce()
  })
})

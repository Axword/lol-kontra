import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {afterEach,expect,it,vi} from 'vitest'
import InfinityLeaderboard from './page'
const query=vi.hoisted(()=>vi.fn(()=>({data:{results:[],page:1,total_pages:1,total_players:0},isLoading:false,isError:false})))
vi.mock('@/lib/store',()=>({usePrefs:(select:(s:{locale:string})=>unknown)=>select({locale:'en'})}))
vi.mock('@/lib/infinity',()=>({useInfinityRanking:query}))
vi.mock('next/navigation',()=>({useSearchParams:()=>new URLSearchParams('period=monthly')}))
vi.mock('@/components/layout/GameLayout',()=>({default:({children}:{children:React.ReactNode})=><main>{children}</main>}))
afterEach(cleanup)
it('opens the linked period and resets pagination when changing one of the four periods',()=>{
  render(<InfinityLeaderboard />)
  expect(query).toHaveBeenLastCalledWith(1,'monthly')
  for(const [label,period] of [['Daily','daily'],['Weekly','weekly'],['Monthly','monthly'],['All-time','all_time']]){
    fireEvent.click(screen.getByRole('button',{name:label}))
    expect(query).toHaveBeenLastCalledWith(1,period)
    expect(screen.getByRole('button',{name:label}).getAttribute('aria-pressed')).toBe('true')
  }
})

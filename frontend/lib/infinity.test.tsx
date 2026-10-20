import { act,cleanup,renderHook,waitFor } from '@testing-library/react'
import { QueryClient,QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { afterEach,beforeEach,describe,expect,it,vi } from 'vitest'
import { api } from './api'
import { infinityKey,useInfinity,useInfinityAnswer,useStartInfinity } from './infinity'

let client:QueryClient
const wrapper=({children}:{children:ReactNode})=><QueryClientProvider client={client}>{children}</QueryClientProvider>
beforeEach(()=>{client=new QueryClient({defaultOptions:{queries:{retry:false},mutations:{retry:false}}})})
afterEach(()=>{cleanup();client.clear()})
describe('private Infinity state',()=>{
  it('waits for an identity, then reads through POST without exposing it in a URL',async()=>{
    const post=vi.spyOn(api,'post').mockResolvedValue({data:{run:null,personal_best:0}})
    const hook=renderHook(({token})=>useInfinity(token),{wrapper,initialProps:{token:''}})
    expect(post).not.toHaveBeenCalled()
    hook.rerender({token:'existing-guest'})
    await waitFor(()=>expect(hook.result.current.data?.personal_best).toBe(0))
    expect(post.mock.calls[0].slice(0,2)).toEqual(['/infinity/state/',{guest_token:'existing-guest'}])
  })
  it.each(['answer','start'] as const)('keeps an in-flight %s response with its original profile after switching identities',async(kind)=>{
    let finish!:(value:unknown)=>void
    vi.spyOn(api,'post').mockImplementation(()=>new Promise(resolve=>{finish=resolve}))
    const oldState={run:null,personal_best:2}
    const newState={run:null,personal_best:9}
    client.setQueryData(infinityKey('old-guest'),oldState)
    client.setQueryData(infinityKey('new-guest'),newState)
    const hook=renderHook(({token})=>({answer:useInfinityAnswer(token),start:useStartInfinity(token)}),{wrapper,initialProps:{token:'old-guest'}})
    act(()=>{if(kind==='answer')hook.result.current.answer.mutate({run_id:'run',board_id:'board',position:1,player_slug:'faker'});else hook.result.current.start.mutate()})
    await waitFor(()=>expect(finish).toBeTypeOf('function'))
    hook.rerender({token:'new-guest'})
    await act(async()=>{finish({data:{run:null,personal_best:3,correct:true}})})
    await waitFor(()=>expect(client.getQueryData(infinityKey('old-guest'))).toMatchObject({personal_best:3}))
    expect(client.getQueryData(infinityKey('new-guest'))).toEqual(newState)
  })
})

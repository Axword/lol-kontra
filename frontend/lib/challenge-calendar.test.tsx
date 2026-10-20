import { act, cleanup, renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, expect, it, vi } from 'vitest'
import { api } from './api'
import { useChallengeCalendar } from './challenge-calendar'

afterEach(cleanup)
it('loads older challenges beyond the first archive page without following an external next URL', async () => {
  const get = vi.spyOn(api, 'get').mockResolvedValueOnce({data: {results:[{id:31,date:'2026-10-20',status:'published'}], next:'https://example.test/ignored?page=2'}})
    .mockResolvedValueOnce({data: {results:[{id:1,date:'2026-09-01',status:'published'}], next:null}})
  const client = new QueryClient({defaultOptions:{queries:{retry:false}}})
  const wrapper = ({children}: {children:React.ReactNode}) => <QueryClientProvider client={client}>{children}</QueryClientProvider>
  const {result, unmount} = renderHook(() => useChallengeCalendar('2026-10-20'),{wrapper})
  await waitFor(() => expect(result.current.hasNextPage).toBe(true))
  await act(async () => {await result.current.fetchNextPage()})
  await waitFor(() => expect(result.current.data?.pages.flatMap(page => page.results.map(item => item.id))).toEqual([31,1]))
  expect(result.current.hasNextPage).toBe(false)
  expect(get).toHaveBeenLastCalledWith('/dailies/', {params:{ordering:'-date',page:2},signal:expect.any(AbortSignal)})
  unmount();client.clear()
})

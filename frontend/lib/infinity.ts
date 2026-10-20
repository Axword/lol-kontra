'use client'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, DailySlot, GameAnswer } from './api'

export type InfinityRun = {
  id: string; board_id: string; slots: DailySlot[]; answers: GameAnswer[]
  correct_count: number; completed_boards: number; errors_used: number
  errors_left: number; max_errors: number; is_over: boolean
  ranking_result?: {periods:Record<InfinityPeriod,{rank:number|null;previous_rank:number|null;improved:boolean;best:number;total_players:number}>}|null
}
export type InfinityPeriod='daily'|'weekly'|'monthly'|'all_time'
export type InfinityState = { run: InfinityRun | null; personal_best: number }
type Move = InfinityState & { correct: boolean; unchanged: boolean; player_nickname: string }
export const infinityKey = (token: string) => ['infinity-state', token] as const

export function useInfinity(token: string) {
  return useQuery<InfinityState>({ queryKey: infinityKey(token), enabled: !!token,
    queryFn: async ({signal}) => (await api.post('/infinity/state/', {guest_token:token}, {signal})).data,
    refetchOnWindowFocus: 'always' })
}
export function useStartInfinity(token: string) {
  const client = useQueryClient()
  return useMutation<InfinityState, unknown, void, {key:ReturnType<typeof infinityKey>}>({ mutationFn: async () => (await api.post('/infinity/start/', {guest_token:token})).data,
    onMutate: async () => { const key=infinityKey(token);await client.cancelQueries({queryKey:key});return {key} },
    onSuccess: (data,_variables,context) => {if(context)client.setQueryData(context.key,data)},
    onError: (_error,_variables,context) => {if(context)void client.invalidateQueries({queryKey:context.key})} })
}
export function useInfinityAnswer(token: string) {
  const client = useQueryClient()
  return useMutation<Move, unknown, {run_id:string;board_id:string;position:number;player_slug:string}, {key:ReturnType<typeof infinityKey>}>({
    mutationFn: async move => (await api.post('/infinity/answer/', {...move,guest_token:token})).data,
    onMutate: async () => {const key=infinityKey(token);await client.cancelQueries({queryKey:key});return {key}},
    onSuccess: async (data,_variables,context) => {
      if(!context)return
      await client.cancelQueries({queryKey:context.key})
      client.setQueryData(context.key, data)
      void client.invalidateQueries({queryKey:['infinity-leaderboard']})
    },
    onError: (_error,_variables,context) => {if(context)void client.invalidateQueries({queryKey:context.key})},
  })
}
export type InfinityRanking = { results:{rank:number;nickname:string;correct_count:number;completed_boards:number;is_active:boolean}[];page:number;total_pages:number;total_players:number;period:InfinityPeriod }
export function useInfinityRanking(page: number,period:InfinityPeriod='all_time') {
  return useQuery<InfinityRanking>({queryKey:['infinity-leaderboard',period,page],
    queryFn:async ({signal}) => (await api.get('/infinity/leaderboard/', {params:{page,page_size:25,period},signal})).data })
}

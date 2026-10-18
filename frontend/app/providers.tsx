'use client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useEffect, useState, ReactNode } from 'react'
import { retryApiQuery } from '@/lib/errors'
import { usePrefs } from '@/lib/store'

export default function Providers({ children }: { children: ReactNode }) {
  const locale = usePrefs((state) => state.locale)
  useEffect(() => { document.documentElement.lang = locale }, [locale])
  const [client] = useState(() => new QueryClient({
    defaultOptions: {
      queries: { staleTime: 30_000, refetchOnWindowFocus: false, retry: retryApiQuery }
    }
  }))
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>
}

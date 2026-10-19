import './globals.css'
import type { Metadata, Viewport } from 'next'
import { Analytics } from '@vercel/analytics/next'
import { ReactNode } from 'react'
import Providers from './providers'

export const metadata: Metadata = {
  title: 'WORDS V',
  description: 'Codzienna zagadka o zawodnikach League of Legends z mistrzostw świata.',
}

export const viewport: Viewport = {
  themeColor: '#f5f6f4',
  width: 'device-width',
  initialScale: 1,
}

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="pl" suppressHydrationWarning>
      <body className="antialiased">
        <Providers>{children}</Providers>
        <Analytics />
      </body>
    </html>
  )
}

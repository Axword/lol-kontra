import './globals.css'
import type { Metadata, Viewport } from 'next'
import { Analytics } from '@vercel/analytics/next'
import { ReactNode } from 'react'
import Providers from './providers'

export const metadata: Metadata = {
  metadataBase: new URL('https://lol-kontra.axword.pl'),
  title: 'WORDS V — quiz League of Legends i Worlds',
  description: 'Codzienny quiz o zawodnikach League of Legends. Ułóż pięcioosobowy skład na podstawie wskazówek o Worlds, bohaterach i karierze graczy.',
  openGraph: {
    type: 'website',
    locale: 'pl_PL',
    siteName: 'WORDS V',
    title: 'WORDS V — quiz League of Legends i Worlds',
    description: 'Ułóż skład League of Legends z pięciu graczy pasujących do codziennych wskazówek.',
  },
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

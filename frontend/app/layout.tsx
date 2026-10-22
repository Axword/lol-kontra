import './globals.css'
import type { Metadata, Viewport } from 'next'
import { Analytics } from '@vercel/analytics/next'
import { ReactNode } from 'react'
import Providers from './providers'
import { themeBootstrap } from '@/lib/theme-bootstrap'

export const metadata: Metadata = {
  metadataBase: new URL('https://lol-kontra.axword.pl'),
  icons: {
    icon: [
      { url: '/favicon.ico', sizes: 'any' },
      { url: '/favicon.svg', type: 'image/svg+xml', sizes: 'any' },
      { url: '/favicon-48.png', type: 'image/png', sizes: '48x48' },
    ],
    apple: [{ url: '/apple-touch-icon.png', sizes: '180x180' }],
  },
  verification: { google: 'uQcprjX4WAMuuT3G4sWeBkMMaOZps6AK7zZR0vm1KxQ' },
  title: 'Kontra Quiz League of Legends — WORLDS KONTRA',
  description: 'Kontra Quiz League of Legends: codzienna zagadka WORLDS KONTRA o zawodnikach LoL. Ułóż skład na podstawie wskazówek o Worlds, bohaterach i karierze graczy.',
  openGraph: {
    type: 'website',
    locale: 'pl_PL',
    siteName: 'WORLDS KONTRA',
    title: 'Kontra Quiz League of Legends — WORLDS KONTRA',
    description: 'Kontra Quiz League of Legends — dopasuj pięciu zawodników do wskazówek o Worlds i ich karierze.',
  },
}

export const viewport: Viewport = {
  themeColor: '#f5f6f4',
  width: 'device-width',
  initialScale: 1,
}

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head><script dangerouslySetInnerHTML={{ __html: themeBootstrap }} /></head>
      <body className="antialiased">
        <Providers>{children}</Providers>
        <Analytics />
      </body>
    </html>
  )
}

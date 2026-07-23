import './globals.css'
import type { Metadata } from 'next'
import { ReactNode } from 'react'
import Providers from './providers'

export const metadata: Metadata = {
  title: 'Worlds XI – LoL Roster Challenge',
  description: 'Codzienna gra LoL Esports – ułóż skład, zbieraj rzadkie picki',
}

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="pl" className="dark" suppressHydrationWarning>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="bg-bg text-ink antialiased">
        <Providers>
          {children}
        </Providers>
      </body>
    </html>
  )
}

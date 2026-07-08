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
      <body className="bg-[#06080c] text-[#E8E6E3] antialiased">
        <Providers>
          {children}
        </Providers>
      </body>
    </html>
  )
}

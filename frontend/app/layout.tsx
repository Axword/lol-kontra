import './globals.css'
import type { Metadata } from 'next'
import { ReactNode } from 'react'
import Providers from './providers'

export const metadata: Metadata = {
  title: 'Worlds XI – LoL Roster Challenge',
  description: 'Codzienna gra LoL Esports – ułóż skład, zbieraj rzadkie picki',
}

/*
  IBM Plex Mono nie jest już pobierany z Google Fonts: build zależał od sieci,
  a strona wysyłała żądanie do zewnętrznego serwera przy każdym wejściu.
  Stos w globals.css schodzi na systemową czcionkę o stałej szerokości znaku
  (SF Mono / Consolas / Menlo), która wszędzie wygląda poprawnie. Żeby wrócić
  do Plex Mono, wrzuć woff2 do /public/fonts i dodaj @font-face.
*/
export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="pl" className="dark" suppressHydrationWarning>
      <body className="bg-bg text-ink antialiased">
        <Providers>
          {children}
        </Providers>
      </body>
    </html>
  )
}

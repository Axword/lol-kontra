import type { Metadata } from 'next'
import HomeGame from './home-game'

export const metadata: Metadata = {
  alternates: { canonical: '/' },
}

export default function HomePage() {
  return <HomeGame />
}

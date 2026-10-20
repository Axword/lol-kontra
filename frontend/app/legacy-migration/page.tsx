import type { Metadata } from 'next'
import LegacyBridge from './bridge'

export const metadata: Metadata = { title: 'WORLDS KONTRA', robots: { index: false, follow: true } }
export default function LegacyMigrationPage({ searchParams }: { searchParams: { next?: string } }) {
  return <LegacyBridge next={searchParams.next} />
}

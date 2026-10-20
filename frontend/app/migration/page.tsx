import type { Metadata } from 'next'
import ProfileMigration from './migration'

export const metadata: Metadata = { title: 'Przywracanie profilu — WORLDS KONTRA', robots: { index: false, follow: true } }
export default function MigrationPage() { return <ProfileMigration /> }

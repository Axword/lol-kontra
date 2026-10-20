import type { Metadata } from 'next'
import ProfileMigration from './migration'

export const metadata: Metadata = { title: 'WORLDS KONTRA', robots: { index: false, follow: true } }
export default function MigrationPage() { return <ProfileMigration /> }

'use client'
import Link from 'next/link'
import { usePrefs } from '@/lib/store'

export default function LoadError({ title, onRetry, archive = false }: {
  title?: string
  onRetry?: () => void
  archive?: boolean
}) {
  const pl = usePrefs((s) => s.locale) === 'pl'
  return (
    <div className="panel p-6 max-w-md mx-auto my-12 text-center" role="alert">
      <p className="display text-[17px] mb-3">
        {title || (pl ? 'Nie udało się wczytać danych' : 'Could not load the data')}
      </p>
      <div className="flex justify-center flex-wrap gap-2">
        {onRetry && <button className="btn btn-gold cut-sm" onClick={onRetry}>
          {pl ? 'Spróbuj ponownie' : 'Try again'}
        </button>}
        {archive && <Link href="/archiwum" className="btn cut-sm">
          {pl ? 'Wróć do archiwum' : 'Back to archive'}
        </Link>}
      </div>
    </div>
  )
}

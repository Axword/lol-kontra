'use client'
import { useState, type ReactNode } from 'react'

export default function PlayerPortrait({ url, fallback = null, className = '' }: { url?: string | null; fallback?: ReactNode; className?: string }) {
  const [failedUrl, setFailedUrl] = useState<string | null>(null)
  if (!url || failedUrl === url) return fallback

  // The adjacent nickname already names this person for assistive technology.
  // eslint-disable-next-line @next/next/no-img-element
  return <img src={url} alt="" width={48} height={48} loading="lazy" referrerPolicy="no-referrer"
    className={`h-12 w-12 shrink-0 object-cover object-top ${className}`} onError={() => setFailedUrl(url)} />
}

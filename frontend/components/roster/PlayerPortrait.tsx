'use client'
import { useState } from 'react'

export default function PlayerPortrait({ url }: { url?: string | null }) {
  const [failedUrl, setFailedUrl] = useState<string | null>(null)
  if (!url || failedUrl === url) return null

  // The adjacent nickname already names this person for assistive technology.
  // eslint-disable-next-line @next/next/no-img-element
  return <img src={url} alt="" width={48} height={48} loading="lazy" referrerPolicy="no-referrer"
    className="h-12 w-12 shrink-0 object-cover object-top" onError={() => setFailedUrl(url)} />
}

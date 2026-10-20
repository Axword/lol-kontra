'use client'
import { useEffect } from 'react'
import { notFound, useParams } from 'next/navigation'
import { usePrefs } from '@/lib/store'
import HomePage from '../home-game'

export default function LocalizedHomePage() {
  const locale = useParams()?.locale
  const setLocale = usePrefs((state) => state.setLocale)
  useEffect(() => {
    if (locale === 'pl' || locale === 'en') setLocale(locale)
  }, [locale, setLocale])
  if (locale !== 'pl' && locale !== 'en') notFound()
  return <HomePage />
}

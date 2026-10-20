import type { MetadataRoute } from 'next'

export default function sitemap(): MetadataRoute.Sitemap {
  return [
    { url: 'https://lol-kontra.axword.pl/', changeFrequency: 'daily' },
    { url: 'https://lol-kontra.axword.pl/archiwum', changeFrequency: 'daily' },
  ]
}

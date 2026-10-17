/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Obraz produkcyjny kopiuje tylko `.next/standalone` – Next wkłada tam
  // serwer razem z tymi zależnościami, których faktycznie używa, więc
  // do finalnego obrazu nie trafia całe node_modules (~400 MB).
  output: 'standalone',
}
module.exports = nextConfig

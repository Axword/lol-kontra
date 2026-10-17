# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Worlds XI – obraz produkcyjny
#
# Aplikacja nie ma backendu: baza zawodników i codzienne zagadki są generowane
# do statycznych plików JSON podczas budowania obrazu (hook `prebuild`
# w package.json uruchamia scripts/generate-data.mjs). Kontener serwuje
# gotowy build Next.js i nie potrzebuje bazy danych ani zmiennych środowiskowych.
#
# Uwaga: wygenerowane dane obejmują ~60 dni wstecz i ~200 dni w przód od DNIA
# BUDOWANIA obrazu. Po tym oknie trzeba obraz przebudować, żeby gra miała
# kolejne zagadki.
# ---------------------------------------------------------------------------

# --- 1. zależności ---------------------------------------------------------
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
# `npm ci` wymaga package-lock.json; fallback dla świeżo sklonowanego repo bez locka.
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

# --- 2. budowanie ----------------------------------------------------------
FROM node:20-alpine AS builder
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# `npm run build` odpala prebuild -> generate-data.mjs -> public/data/*
RUN npm run build

# --- 3. obraz uruchomieniowy ----------------------------------------------
FROM node:20-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

# Nie uruchamiamy aplikacji jako root.
RUN addgroup -g 1001 -S nodejs && adduser -S nextjs -u 1001

# `output: 'standalone'` w next.config.js pakuje serwer razem z potrzebnymi
# zależnościami – stąd brak `npm install` na tym etapie.
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
# public zawiera mapę, ikony ról ORAZ wygenerowane dane gry (public/data)
COPY --from=builder --chown=nextjs:nodejs /app/public ./public

USER nextjs
EXPOSE 3000

# Bez curl/wget w obrazie – healthcheck robimy samym node.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD node -e "fetch('http://127.0.0.1:'+(process.env.PORT||3000)+'/data/index.json').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"

CMD ["node", "server.js"]

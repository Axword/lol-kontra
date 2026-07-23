#!/usr/bin/env node
/**
 * generate-data.mjs
 * ------------------------------------------------------------------
 * Zastępuje backend Django: przy każdym buildzie/deployu generuje
 * statyczne pliki JSON z codziennymi zagadkami (styl kontra.games
 * "Mundialowa Jedenastka" – 5 slotów z warunkami, rzadkość picków,
 * diamond pick).
 *
 * Wszystko jest DETERMINISTYCZNE względem daty (seedowany PRNG),
 * więc każdy build daje te same zagadki dla tych samych dni.
 *
 * Wyjście (frontend/public/data/):
 *   players.json          – odchudzona baza 876 graczy Worlds
 *   index.json            – lista dostępnych dni (archiwum + przyszłość)
 *   dailies/<id>.json     – pełna definicja jednej zagadki (sloty,
 *                           warunki, poprawne odpowiedzi + pick%)
 * ------------------------------------------------------------------
 */
import { readFileSync, writeFileSync, mkdirSync, rmSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const __dirname = dirname(fileURLToPath(import.meta.url))
const ROOT = join(__dirname, '..')
const OUT = join(ROOT, 'public', 'data')

const DAYS_BACK = 60      // archiwum
const DAYS_FORWARD = 200  // zapas na przyszłość – build ważny ~6 mies.
const EPOCH = '2026-01-01' // daily #1

// ---------------------------------------------------------------- utils

function hashString(str) {
  let h = 2166136261 >>> 0
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i)
    h = Math.imul(h, 16777619)
  }
  return h >>> 0
}

function mulberry32(seed) {
  let a = seed >>> 0
  return function () {
    a |= 0; a = (a + 0x6D2B79F5) | 0
    let t = Math.imul(a ^ (a >>> 15), 1 | a)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

function isoDate(d) { return d.toISOString().slice(0, 10) }
function addDays(iso, n) {
  const d = new Date(iso + 'T12:00:00Z')
  d.setUTCDate(d.getUTCDate() + n)
  return isoDate(d)
}
function daysBetween(a, b) {
  return Math.round((new Date(b + 'T12:00:00Z') - new Date(a + 'T12:00:00Z')) / 86400000)
}

function slugifyTeam(s) {
  if (!s) return ''
  s = String(s).toLowerCase().replace(/[^a-z0-9]+/g, '')
  const aliases = {
    sktelecomt1: 't1', skt1: 't1', skt: 't1', t1: 't1',
    damwon: 'dwg', damwonkia: 'dwg', dpluskia: 'dwg', dplusgaming: 'dwg',
    g2esports: 'g2', g2: 'g2',
    edwardgaming: 'edg', edg: 'edg',
    royalnevergiveup: 'rng', rng: 'rng',
    jdgaming: 'jdg', jdg: 'jdg',
    invictusgaming: 'ig', ig: 'ig',
    geng: 'geng', gengesports: 'geng',
    samsunggalaxy: 'ssg', samsungwhite: 'ssw', samsungblue: 'ssb',
  }
  return aliases[s] || s
}

// ---------------------------------------------------------------- dedupe
// Źródło zawiera duplikaty slugów (ten sam zawodnik zapisany 2×: raz z
// pełnymi danymi, raz jako "śmieciowy" rekord z pustym birth_year, błędnym
// krajem i worlds_count = 0). To powoduje, że w wyszukiwarce ten sam gracz
// pojawia się wielokrotnie, a warunki bazujące na wieku/regionie dostają
// sprzeczne wartości. Scalamy duplikaty zachowując rekord z największą
// kompletnością i uzupełniając braki z drugiego.
function completeness(p) {
  let s = 0
  if (p.real_name) s++
  if (p.birth_year != null) s += 2
  if (p.country_code && p.country_code !== 'KR') s++ // śmieciowe duplikaty często wymuszają KR
  if ((p.worlds_count || 0) > 0) s += 2
  if ((p.attributes?.top_champions_career || []).length) s += 2
  if ((p.attributes?.teams || []).length) s++
  if ((p.attributes?.worlds_appearances || []).length) s++
  return s
}

function mergePlayers(a, b) {
  const primary = completeness(a) >= completeness(b) ? a : b
  const secondary = primary === a ? b : a
  const out = { ...primary }
  for (const key of ['real_name', 'birth_year', 'country_code', 'residency', 'continent', 'primary_role', 'worlds_count', 'worlds_titles_count']) {
    if ((out[key] === undefined || out[key] === null || out[key] === '') && secondary[key] != null && secondary[key] !== '') {
      out[key] = secondary[key]
    }
  }
  out.attributes = out.attributes || {}
  const sa = secondary.attributes || {}
  for (const key of ['top_champions_career', 'worlds_appearances', 'worlds_titles', 'teams', 'leagues', 'coaches']) {
    const pa = (out.attributes[key] || []).filter(Boolean)
    const pb = (sa[key] || []).filter(Boolean)
    out.attributes[key] = Array.from(new Set([...pa, ...pb].map(String)))
  }
  if ((out.secondary_roles || []).length === 0 && (secondary.secondary_roles || []).length) out.secondary_roles = secondary.secondary_roles
  return out
}

function dedupePlayers(list) {
  const map = new Map()
  for (const p of list) {
    const slug = (p.slug || '').toLowerCase()
    if (!slug) continue
    if (!map.has(slug)) map.set(slug, p)
    else map.set(slug, mergePlayers(map.get(slug), p))
  }
  return [...map.values()]
}

// ---------------------------------------------------------------- data

const RAW_PLAYERS = JSON.parse(readFileSync(join(ROOT, 'data', 'players.source.json'), 'utf8'))
// scal duplikaty slugów (ten sam gracz zapisany wielokrotnie) – naprawia
// błędne dane (wiek/region) oraz to, że w wyszukiwarce gracz pojawia się kilka razy
const players = dedupePlayers(RAW_PLAYERS)

// Zdobywcy Worlds (fixture nie ma worlds_titles – fallback jak w starym backendzie)
const WORLDS_CHAMPIONS = new Set([
  'faker', 'bengi', 'wolf', 'bang', 'duke', 'marin', 'easyhoon', 'tom', 'blank', 'untara',
  'cuvee', 'ambition', 'crown', 'ruler', 'corejj', 'haru',
  'theshy', 'ning', 'rookie', 'jackeylove', 'baolan',
  'doinb', 'tian', 'lwx', 'crisp', 'gimgoon',
  'canyon', 'showmaker', 'ghost', 'beryl', 'nuguri',
  'scout', 'viper', 'meiko', 'flandre', 'jiejie',
  'zeus', 'oner', 'gumayusi', 'keria',
  'deft', 'pyosik', 'zeka', 'kingen',
  'kanavi', 'knight', '369', 'missing', 'bin', 'elk', 'on',
  'impact', 'piglet', 'pooh', 'mata', 'imp', 'dandy', 'pawn', 'looper',
  'mafa', 'cool', 'uzi', 'clearlove', 'toyz', 'stanley', 'mistake', 'bebe',
])

// "Sława" gracza -> do estymacji jak często ludzie by go wybierali (pick %)
const FAME = {
  faker: 100, caps: 80, chovy: 75, ruler: 70, uzi: 70, theshy: 65, canyon: 60,
  showmaker: 60, keria: 60, zeus: 55, oner: 50, gumayusi: 55, deft: 55, viper: 55,
  knight: 50, bin: 45, jankos: 55, rekkles: 60, perkz: 55, wunder: 35, mikyx: 35,
  bwipo: 35, hylissang: 35, upset: 30, humanoid: 30, elk: 35, meiko: 40, xun: 20,
  peanut: 45, bengi: 35, wolf: 30, bang: 40, mata: 35, scout: 40, doinb: 40,
  rookie: 45, jackeylove: 50, kanavi: 40, tian: 30, crisp: 30, zeka: 40, kingen: 30,
  impact: 40, corejj: 40, doublelift: 50, bjergsen: 50, sneaky: 35, jensen: 35,
  fudge: 20, blaber: 30, licorice: 15, beryl: 40, ghost: 25, nuguri: 35, ambition: 30,
  crown: 25, cuvee: 20, pray: 30, gorilla: 25, khan: 30, clid: 25, bdd: 30, kiin: 30,
}

function fameOf(p) {
  const base = FAME[p.slug] ?? 0
  let w = 1 + base
  w += (p.worlds_count || 0) * 2.2
  if (p.is_active) w += 4
  if (WORLDS_CHAMPIONS.has(p.slug)) w += 12
  const years = p.attributes?.worlds_appearances || []
  if (years.some(y => y >= 2023)) w += 6 // świeżo w pamięci
  return w
}

// ---------------------------------------------------------------- warunki

// typy: residency | country | continent | active | worlds_min | worlds_year |
//       team | champion | birth_max | birth_min
function playerMatches(p, cond) {
  const a = p.attributes || {}
  switch (cond.t) {
    case 'residency': {
      const leagues = (a.leagues || []).map(x => String(x).toUpperCase())
      return String(p.residency).toUpperCase() === cond.v || leagues.includes(cond.v)
    }
    case 'country': return String(p.country_code).toUpperCase() === cond.v
    case 'continent': return String(p.continent) === cond.v
    case 'active': return !!p.is_active === cond.v
    case 'worlds_min': return (p.worlds_count || 0) >= cond.v
    case 'worlds_year': return (a.worlds_appearances || []).includes(cond.v)
    case 'team': {
      const teams = (a.teams || []).map(slugifyTeam)
      return teams.includes(cond.v)
    }
    case 'champion': return WORLDS_CHAMPIONS.has(p.slug)
    case 'champion_pick': return (p.attributes?.top_champions_career || []).includes(cond.v)
    case 'birth_max': return p.birth_year != null && p.birth_year <= cond.v
    case 'birth_min': return p.birth_year != null && p.birth_year >= cond.v
    case 'secondary_role': {
      // Gracz grał na innej roli niż primary (np. na supporcie ale primary mid)
      const secs = (p.secondary_roles || []).map(String)
      return secs.includes(cond.v)
    }
    case 'played_in_championship_team': {
      // Gracz grał w drużynie, która wygrała Worlds (niekoniecznie sam jest mistrzem)
      const teams = (a.teams || []).map(slugifyTeam)
      const championshipTeams = [
        't1', 'samsung-galaxy', 'ssg', 'damwon-gaming', 'dwg',
        'invictus-gaming', 'ig', 'funplus-phoenix', 'fpx',
        'edward-gaming', 'edg', 'drx',
      ]
      return teams.some(t => championshipTeams.includes(t))
    }
    default: return false
  }
}

const CONDITION_POOL = [
  { t: 'residency', v: 'LCK', pl: 'Grał w LCK', en: 'Played in LCK' },
  { t: 'residency', v: 'LPL', pl: 'Grał w LPL', en: 'Played in LPL' },
  { t: 'residency', v: 'LEC', pl: 'Grał w LEC', en: 'Played in LEC' },
  { t: 'residency', v: 'LCS', pl: 'Grał w LCS', en: 'Played in LCS' },
  { t: 'residency', v: 'PCS', pl: 'Grał w PCS', en: 'Played in PCS' },
  { t: 'residency', v: 'CBLOL', pl: 'Grał w CBLOL', en: 'Played in CBLOL' },
  { t: 'country', v: 'KR', pl: 'Koreańczyk', en: 'Korean' },
  { t: 'country', v: 'CN', pl: 'Chińczyk', en: 'Chinese' },
  { t: 'country', v: 'TW', pl: 'Tajwańczyk', en: 'Taiwanese' },
  { t: 'continent', v: 'Europe', pl: 'Europejczyk', en: 'European' },
  { t: 'continent', v: 'North America', pl: 'Z Ameryki Północnej', en: 'North American' },
  { t: 'continent', v: 'Asia', pl: 'Z Azji', en: 'Asian' },
  { t: 'active', v: true, pl: 'Aktywny zawodnik', en: 'Active player' },
  { t: 'active', v: false, pl: 'Zakończył karierę', en: 'Retired' },
  { t: 'worlds_min', v: 2, pl: 'Min. 2 razy na Worlds', en: '2+ Worlds appearances' },
  { t: 'worlds_min', v: 3, pl: 'Min. 3 razy na Worlds', en: '3+ Worlds appearances' },
  { t: 'worlds_min', v: 5, pl: 'Min. 5 razy na Worlds', en: '5+ Worlds appearances' },
  { t: 'champion', v: true, pl: 'Wygrał Worlds', en: 'Worlds champion' },
  { t: 'birth_max', v: 1995, pl: 'Urodzony przed 1996', en: 'Born before 1996' },
  { t: 'birth_min', v: 2000, pl: 'Urodzony w 2000 lub później', en: 'Born in 2000 or later' },
  ...[2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025]
    .map(y => ({ t: 'worlds_year', v: y, pl: `Grał na Worlds ${y}`, en: `Played at Worlds ${y}` })),
  ...[
    ['t1', 'T1 / SKT'], ['fnatic', 'Fnatic'], ['g2', 'G2 Esports'], ['cloud9', 'Cloud9'],
    ['ktrolster', 'KT Rolster'], ['tsm', 'TSM'], ['teamliquid', 'Team Liquid'],
    ['edg', 'EDward Gaming'], ['ig', 'Invictus Gaming'], ['geng', 'Gen.G'],
    ['jdg', 'JD Gaming'], ['bilibiligaming', 'Bilibili Gaming'], ['rng', 'RNG'],
    ['hanwhalifeesports', 'Hanwha Life'], ['flyquest', 'FlyQuest'],
  ].map(([slug, name]) => ({ t: 'team', v: slug, pl: `Grał w ${name}`, en: `Played for ${name}` })),
  // Gracze którzy grali na innej roli niż ich primary
  { t: 'secondary_role', v: 'top', pl: 'Grał też na Top', en: 'Also played Top' },
  { t: 'secondary_role', v: 'jungle', pl: 'Grał też w Jungle', en: 'Also played Jungle' },
  { t: 'secondary_role', v: 'mid', pl: 'Grał też na Mid', en: 'Also played Mid' },
  { t: 'secondary_role', v: 'adc', pl: 'Grał też na ADC', en: 'Also played ADC' },
  { t: 'secondary_role', v: 'support', pl: 'Grał też na Support', en: 'Also played Support' },
  // Drużyna zdobyła mistrzostwo (gracz grał w niej, ale niekoniecznie jest mistrzem)
  { t: 'played_in_championship_team', v: true, pl: 'Grał w drużynie mistrzów Worlds', en: 'Played for a Worlds champion team' },
]

const ROLE_ORDER = ['top', 'jungle', 'mid', 'adc', 'support']

// ---------------------------------------------------------------- generator

const byRole = {}
for (const r of ROLE_ORDER) {
  byRole[r] = players.filter(p => p.primary_role === r || (p.secondary_roles || []).includes(r))
}

function generateSlot(date, role, position, dailyId) {
  const rnd = mulberry32(hashString(`${date}|${role}|worlds-xi-v1`))
  const rolePool = byRole[role]

  let best = null
  for (let attempt = 0; attempt < 80; attempt++) {
    const k = rnd() < 0.6 ? 2 : 3
    const chosen = []
    const usedTypes = new Set()
    let guard = 0
    while (chosen.length < k && guard++ < 100) {
      const c = CONDITION_POOL[Math.floor(rnd() * CONDITION_POOL.length)]
      // max 1 warunek danego typu, bez sprzeczności typu kraj+kontynent w nadmiarze
      if (usedTypes.has(c.t)) continue
      if (c.t === 'continent' && usedTypes.has('country')) continue
      if (c.t === 'country' && usedTypes.has('continent')) continue
      usedTypes.add(c.t)
      chosen.push(c)
    }
    const candidates = rolePool.filter(p => chosen.every(c => playerMatches(p, c)))
    const n = candidates.length
    if (n >= 12 && n <= 90) {
      const score = Math.abs(n - 35)
      if (!best || score < best.score) best = { chosen, candidates, score }
      if (n >= 25 && n <= 50) break // idealny zakres – kończymy
    }
  }

  if (!best) {
    // fallback – sam warunek "grał na Worlds" (spełnia każdy w bazie)
    best = {
      chosen: [{ t: 'worlds_min', v: 1, pl: 'Grał na Worlds', en: 'Worlds appearance' }],
      candidates: rolePool.slice(),
      score: 999,
    }
  }

  // --- pytania o picki (signature champion) ---
  // Źródłem są dane o często granych championach (top_champions_career) z
  // bazy – to samo, co dostarczyłaby biblioteka typu lolfandom. Dodajemy
  // warunek "Często grał na X" tylko gdy w puli jest co najmniej 6, a nie
  // więcej niż (liczba kandydatów - 3) graczy z danym championem.
  const champCounts = {}
  for (const p of best.candidates) {
    for (const c of (p.attributes?.top_champions_career || [])) {
      if (!c || !String(c).trim()) continue
      champCounts[c] = (champCounts[c] || 0) + 1
    }
  }
  const champOpts = Object.entries(champCounts)
    .filter(([, n]) => n >= 5 && n <= best.candidates.length - 2)
  if (champOpts.length && best.chosen.length < 3 && rnd() < 0.85) {
    const [champ] = champOpts[Math.floor(rnd() * champOpts.length)]
    const champCond = { t: 'champion_pick', v: champ, pl: `Często grał na ${champ}`, en: `Often played ${champ}` }
    const filtered = best.candidates.filter(p => (p.attributes?.top_champions_career || []).includes(champ))
    if (filtered.length >= 10 && filtered.length <= 90) {
      best.chosen.push(champCond)
      best.candidates = filtered
    }
  }

  // symulowany rozkład popularności picków (pick %)
  const weights = best.candidates.map(fameOf)
  const totalW = weights.reduce((s, w) => s + w, 0)
  const answers = best.candidates
    .map((p, i) => [p.slug, Math.max(0.1, Math.round((weights[i] / totalW) * 1000) / 10)])
    .sort((a, b) => b[1] - a[1])

  // diamond pick = najrzadszy kandydat (remis rozstrzyga PRNG)
  const minPct = answers[answers.length - 1][1]
  const rarest = answers.filter(a => a[1] === minPct)
  const diamond = rarest[Math.floor(rnd() * rarest.length)][0]

  return {
    id: dailyId * 10 + position,
    position,
    role,
    label_pl: role[0].toUpperCase() + role.slice(1),
    label_en: role[0].toUpperCase() + role.slice(1),
    conditions: best.chosen.map((c, i) => ({
      id: dailyId * 100 + position * 10 + i,
      label_pl: c.pl,
      label_en: c.en,
    })),
    answers, // [ [slug, pick_percent], ... ] – malejąco wg popularności
    diamond,
  }
}

function generateDaily(date) {
  const id = daysBetween(EPOCH, date) + 1
  return {
    id,
    date,
    slots: ROLE_ORDER.map((role, i) => generateSlot(date, role, i + 1, id)),
  }
}

// ---------------------------------------------------------------- main

rmSync(OUT, { recursive: true, force: true })
mkdirSync(join(OUT, 'dailies'), { recursive: true })

// 1. players.json – odchudzony (do wyszukiwarki)
function decodeEntities(s) {
  if (!s) return ''
  return String(s)
    .replace(/<[^>]*>/g, '')
    .replace(/&amp;/g, '&')
    .replace(/&quot;/g, '"')
    .replace(/&apos;/g, "'")
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&nbsp;/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}
const slim = players.map(p => ({
  slug: p.slug,
  nickname: decodeEntities(p.nickname),
  real_name: decodeEntities(p.real_name),
  country_code: p.country_code || '',
  residency: p.residency || '',
  primary_role: p.primary_role,
  secondary_roles: p.secondary_roles || [],
  worlds_count: p.worlds_count || 0,
  is_active: !!p.is_active,
}))
writeFileSync(join(OUT, 'players.json'), JSON.stringify(slim))

// 2. dailies
const today = isoDate(new Date())
const start = addDays(today, -DAYS_BACK)
const total = DAYS_BACK + DAYS_FORWARD + 1
const index = []
for (let i = 0; i < total; i++) {
  const date = addDays(start, i)
  const daily = generateDaily(date)
  writeFileSync(join(OUT, 'dailies', `${daily.id}.json`), JSON.stringify(daily))
  index.push({ id: daily.id, date })
}

writeFileSync(join(OUT, 'index.json'), JSON.stringify({
  generated_at: new Date().toISOString(),
  epoch: EPOCH,
  days: index,
}))

console.log(`✔ wygenerowano dane gry: ${slim.length} graczy, ${index.length} dni (${start} → ${index[index.length - 1].date})`)
console.log(`  → frontend/public/data/`)

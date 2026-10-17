#!/usr/bin/env node
/**
 * generate-data.mjs
 * ------------------------------------------------------------------
 * Zastępuje backend: przy każdym buildzie generuje statyczne pliki JSON
 * z codziennymi zagadkami (styl kontra.games "Mundialowa Jedenastka" –
 * 5 slotów z warunkami, rzadkość picków, diamond pick).
 *
 * Wszystko jest DETERMINISTYCZNE względem daty (seedowany PRNG),
 * więc każdy build daje te same zagadki dla tych samych dni.
 *
 * Wyjście (frontend/public/data/):
 *   players.json          – odchudzona baza graczy Worlds (do wyszukiwarki)
 *   index.json            – lista dostępnych dni (archiwum + przyszłość)
 *   dailies/<id>.json     – pełna definicja jednej zagadki
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

// Widełki liczby poprawnych odpowiedzi na slot.
const MIN_CANDIDATES = 5
const MAX_CANDIDATES = 90
const IDEAL_MIN = 22
const IDEAL_MAX = 55

// Ile dni wstecz pamiętamy motywy, żeby zagadki się nie powtarzały.
const THEME_MEMORY_DAYS = 10

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

const TEAM_ALIASES = {
  sktelecomt1: 't1', skt1: 't1', skt: 't1', t1: 't1',
  damwon: 'dwg', damwongaming: 'dwg', damwonkia: 'dwg', dwgkia: 'dwg',
  dpluskia: 'dwg', dplusgaming: 'dwg', dplus: 'dwg',
  g2esports: 'g2', g2: 'g2',
  edwardgaming: 'edg', edg: 'edg',
  royalnevergiveup: 'rng', rng: 'rng', royalclub: 'rng',
  jdgaming: 'jdg', jdg: 'jdg',
  invictusgaming: 'ig', ig: 'ig',
  geng: 'geng', gengesports: 'geng',
  samsunggalaxy: 'ssg', samsungwhite: 'ssw', samsungblue: 'ssb',
  teamsololmid: 'tsm', tsmftx: 'tsm', tsm: 'tsm',
  topesports: 'tes',
  bilibiligaming: 'blg', billibilligaming: 'blg',
  weibogaming: 'wbg',
  lngesports: 'lng',
  hanwhalifeesports: 'hle',
  ktrolster: 'kt',
  afreecafreecs: 'kdf', kwangdongfreecs: 'kdf',
  cloud9: 'c9',
  teamliquid: 'tl',
  counterlogicgaming: 'clg',
  madlions: 'mad', madlionskoi: 'mad',
  rogueeuropeanteam: 'rge', rogue: 'rge',
  misfitsgaming: 'misfits',
  teamvitality: 'vitality',
  fnatic: 'fnatic',
  flyquest: 'flyquest',
  drx: 'drx', kingzoneddragon: 'drx', longzhugaming: 'drx',
  teamwe: 'we', worldelite: 'we',
  psgtalon: 'psg',
  flashwolves: 'flashwolves', yoeflashwolves: 'flashwolves',
  ahqesportsclub: 'ahq',
  gamkingdom: 'gam', gamesports: 'gam',
  fnaticacademy: 'fnaticacademy',
}

function slugifyTeam(s) {
  if (!s) return ''
  const raw = String(s).toLowerCase().replace(/[^a-z0-9]+/g, '')
  return TEAM_ALIASES[raw] || raw
}

/**
 * Zespoły akademickie / rezerwowe zaśmiecają historię drużyn – gracz "grał
 * w Cloud9" nie powinien być prawdziwy tylko dlatego, że przewinął się przez
 * Cloud9 Academy. Odfiltrowujemy je z faktów o karierze.
 */
function isSquadTeam(slug) {
  return /academy|challenger|juniors|rezerw|scholastic|prospects/.test(slug)
}

// ---------------------------------------------------------------- dedupe
// Źródło zawiera duplikaty slugów (ten sam zawodnik zapisany 2×: raz z
// pełnymi danymi, raz jako "śmieciowy" rekord z pustym birth_year, błędnym
// krajem i worlds_count = 0). Scalamy zachowując rekord z największą
// kompletnością i uzupełniając braki z drugiego.
function completeness(p) {
  let s = 0
  if (p.real_name) s++
  if (p.birth_year != null) s += 2
  if (p.country_code && p.country_code !== 'KR') s++
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
const players = dedupePlayers(RAW_PLAYERS)

// Zdobywcy Worlds. Fixture ma puste `worlds_titles` dla WSZYSTKICH graczy,
// więc jedynym źródłem jest ta lista – stąd warunek "Wygrał Worlds" opiera się
// na niej, a nie na danych.
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

// Region ligi -> kraje uznawane za "miejscowe" (do warunku o imporcie).
const LEAGUE_HOME_COUNTRIES = {
  LCK: ['KR'],
  LPL: ['CN'],
  LMS: ['TW', 'HK', 'MO'],
  PCS: ['TW', 'HK', 'MO', 'SG', 'MY', 'PH', 'ID', 'TH'],
  VCS: ['VN'],
  CBLOL: ['BR'],
  LLA: ['MX', 'AR', 'CL', 'PE', 'CO', 'EC', 'UY'],
  TCL: ['TR'],
  LCL: ['RU', 'UA', 'BY', 'KZ', 'AM'],
}
// Ligi, w których "miejscowość" określa kontynent, a nie kraj.
const LEAGUE_HOME_CONTINENTS = { LEC: 'Europe', LCS: 'North America' }

const WILDCARD_LEAGUES = new Set(['PCS', 'LMS', 'VCS', 'CBLOL', 'LLA', 'TCL', 'LCL', 'LJL', 'OPL', 'LCO'])

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

// ---------------------------------------------------------------- fakty o graczu
// Liczone RAZ na gracza. Generator sprawdza setki tysięcy kombinacji, więc
// wyliczanie tego w pętli warunków byłoby najwolniejszym miejscem skryptu.

function buildFacts(p) {
  const a = p.attributes || {}
  const years = Array.from(new Set((a.worlds_appearances || []).map(Number).filter(Boolean))).sort((x, y) => x - y)

  // najdłuższa seria kolejnych lat na Worlds
  let streak = years.length ? 1 : 0
  let run = streak
  let hasGap = false
  for (let i = 1; i < years.length; i++) {
    if (years[i] === years[i - 1] + 1) { run++; streak = Math.max(streak, run) }
    else { run = 1; if (years[i] - years[i - 1] >= 2) hasGap = true }
  }

  const teams = Array.from(new Set((a.teams || []).map(slugifyTeam).filter(t => t && !isSquadTeam(t))))
  const champs = Array.from(new Set((a.top_champions_career || []).map(c => String(c).trim()).filter(Boolean)))
  const league = String(p.residency || '').toUpperCase()
  const country = String(p.country_code || '').toUpperCase()

  let isImport = false
  if (league && country) {
    if (LEAGUE_HOME_COUNTRIES[league]) isImport = !LEAGUE_HOME_COUNTRIES[league].includes(country)
    else if (LEAGUE_HOME_CONTINENTS[league]) isImport = !!p.continent && p.continent !== LEAGUE_HOME_CONTINENTS[league]
  }

  const debut = years.length ? years[0] : null
  const last = years.length ? years[years.length - 1] : null

  return {
    years,
    yearSet: new Set(years),
    worlds: p.worlds_count || years.length,
    debut,
    last,
    streak,
    hasGap,
    teams,
    teamSet: new Set(teams),
    champSet: new Set(champs),
    league,
    leagues: new Set([league, ...(a.leagues || []).map(x => String(x).toUpperCase())].filter(Boolean)),
    country,
    continent: String(p.continent || ''),
    isImport,
    isWildcard: WILDCARD_LEAGUES.has(league),
    isChampion: WORLDS_CHAMPIONS.has(p.slug),
    birth: p.birth_year ?? null,
    debutAge: p.birth_year != null && debut != null ? debut - p.birth_year : null,
    active: !!p.is_active,
  }
}

for (const p of players) p.__f = buildFacts(p)

function fameOf(p) {
  const f = p.__f
  let w = 1 + (FAME[p.slug] ?? 0)
  w += f.worlds * 2.2
  if (f.active) w += 4
  if (f.isChampion) w += 12
  if (f.last != null && f.last >= 2023) w += 6 // świeżo w pamięci
  return w
}

// ---------------------------------------------------------------- warunki

function playerMatches(p, cond) {
  const f = p.__f
  switch (cond.t) {
    // --- pochodzenie i liga ---
    case 'residency': return f.leagues.has(cond.v)
    case 'country': return f.country === cond.v
    case 'continent': return f.continent === cond.v
    case 'import': return f.isImport
    case 'wildcard': return f.isWildcard

    // --- status kariery ---
    case 'active': return f.active === cond.v
    case 'birth_max': return f.birth != null && f.birth <= cond.v
    case 'birth_min': return f.birth != null && f.birth >= cond.v

    // --- występy na Worlds ---
    case 'worlds_min': return f.worlds >= cond.v
    case 'worlds_year': return f.yearSet.has(cond.v)
    case 'debut_max': return f.debut != null && f.debut <= cond.v
    case 'debut_min': return f.debut != null && f.debut >= cond.v
    case 'last_max': return f.last != null && f.last <= cond.v
    case 'last_min': return f.last != null && f.last >= cond.v
    case 'streak_min': return f.streak >= cond.v
    case 'comeback': return f.hasGap
    case 'debut_age_max': return f.debutAge != null && f.debutAge <= cond.v
    case 'debut_age_min': return f.debutAge != null && f.debutAge >= cond.v

    // --- tytuły ---
    case 'champion': return f.isChampion
    case 'never_champion': return !f.isChampion && f.worlds >= cond.v

    // --- drużyny ---
    case 'team': return f.teamSet.has(cond.v)
    case 'team_pair': return cond.v.every(t => f.teamSet.has(t))
    case 'teams_min': return f.teams.length >= cond.v
    case 'one_club': return f.teams.length === 1

    // --- championy ---
    case 'champion_pick': return f.champSet.has(cond.v)

    default: return false
  }
}

/**
 * Pula warunków.
 *
 * `fam` (rodzina) służy do tego, żeby jeden slot – i cała plansza dnia – nie
 * dostały dwóch warunków mówiących o tym samym ("Grał w LCK" + "Koreańczyk"
 * to praktycznie jedno pytanie).
 */
const CONDITION_POOL = [
  // ---- liga / region ----
  { t: 'residency', v: 'LCK', fam: 'league', pl: 'Grał w LCK', en: 'Played in LCK' },
  { t: 'residency', v: 'LPL', fam: 'league', pl: 'Grał w LPL', en: 'Played in LPL' },
  { t: 'residency', v: 'LEC', fam: 'league', pl: 'Grał w LEC', en: 'Played in LEC' },
  { t: 'residency', v: 'LCS', fam: 'league', pl: 'Grał w LCS', en: 'Played in LCS' },
  { t: 'residency', v: 'PCS', fam: 'league', pl: 'Grał w PCS', en: 'Played in PCS' },
  { t: 'residency', v: 'CBLOL', fam: 'league', pl: 'Grał w CBLOL', en: 'Played in CBLOL' },
  { t: 'residency', v: 'VCS', fam: 'league', pl: 'Grał w VCS', en: 'Played in VCS' },
  { t: 'residency', v: 'LMS', fam: 'league', pl: 'Grał w LMS', en: 'Played in LMS' },
  { t: 'wildcard', v: true, fam: 'league', pl: 'Reprezentował region wildcard', en: 'Wildcard region' },

  // ---- narodowość ----
  { t: 'country', v: 'KR', fam: 'origin', pl: 'Koreańczyk', en: 'Korean' },
  { t: 'country', v: 'CN', fam: 'origin', pl: 'Chińczyk', en: 'Chinese' },
  { t: 'country', v: 'TW', fam: 'origin', pl: 'Tajwańczyk', en: 'Taiwanese' },
  { t: 'country', v: 'VN', fam: 'origin', pl: 'Wietnamczyk', en: 'Vietnamese' },
  { t: 'country', v: 'BR', fam: 'origin', pl: 'Brazylijczyk', en: 'Brazilian' },
  { t: 'country', v: 'US', fam: 'origin', pl: 'Amerykanin', en: 'American' },
  { t: 'country', v: 'DE', fam: 'origin', pl: 'Niemiec', en: 'German' },
  { t: 'country', v: 'PL', fam: 'origin', pl: 'Polak', en: 'Polish' },
  { t: 'country', v: 'FR', fam: 'origin', pl: 'Francuz', en: 'French' },
  { t: 'country', v: 'DK', fam: 'origin', pl: 'Duńczyk', en: 'Danish' },
  { t: 'country', v: 'TR', fam: 'origin', pl: 'Turek', en: 'Turkish' },
  { t: 'country', v: 'ES', fam: 'origin', pl: 'Hiszpan', en: 'Spanish' },
  { t: 'continent', v: 'Europe', fam: 'origin', pl: 'Europejczyk', en: 'European' },
  { t: 'continent', v: 'North America', fam: 'origin', pl: 'Z Ameryki Północnej', en: 'North American' },
  { t: 'continent', v: 'Asia', fam: 'origin', pl: 'Z Azji', en: 'Asian' },
  { t: 'import', v: true, fam: 'import', pl: 'Import – grał poza swoim regionem', en: 'Import – played outside home region' },

  // ---- status ----
  { t: 'active', v: true, fam: 'status', pl: 'Wciąż aktywny', en: 'Still active' },
  { t: 'active', v: false, fam: 'status', pl: 'Zakończył karierę', en: 'Retired' },

  // ---- rocznik ----
  { t: 'birth_max', v: 1993, fam: 'birth', pl: 'Urodzony przed 1994', en: 'Born before 1994' },
  { t: 'birth_max', v: 1995, fam: 'birth', pl: 'Urodzony przed 1996', en: 'Born before 1996' },
  { t: 'birth_min', v: 1999, fam: 'birth', pl: 'Urodzony w 1999 lub później', en: 'Born in 1999 or later' },
  { t: 'birth_min', v: 2002, fam: 'birth', pl: 'Urodzony w 2002 lub później', en: 'Born in 2002 or later' },

  // ---- liczba występów ----
  { t: 'worlds_min', v: 2, fam: 'worlds_count', pl: 'Min. 2 razy na Worlds', en: '2+ Worlds appearances' },
  { t: 'worlds_min', v: 3, fam: 'worlds_count', pl: 'Min. 3 razy na Worlds', en: '3+ Worlds appearances' },
  { t: 'worlds_min', v: 5, fam: 'worlds_count', pl: 'Min. 5 razy na Worlds', en: '5+ Worlds appearances' },
  { t: 'worlds_min', v: 7, fam: 'worlds_count', pl: 'Weteran – min. 7 razy na Worlds', en: 'Veteran – 7+ Worlds' },

  // ---- debiut / ostatni start ----
  { t: 'debut_max', v: 2015, fam: 'debut', pl: 'Debiut na Worlds do 2015', en: 'Worlds debut by 2015' },
  { t: 'debut_max', v: 2017, fam: 'debut', pl: 'Debiut na Worlds do 2017', en: 'Worlds debut by 2017' },
  { t: 'debut_min', v: 2020, fam: 'debut', pl: 'Debiut na Worlds od 2020', en: 'Worlds debut since 2020' },
  { t: 'debut_min', v: 2023, fam: 'debut', pl: 'Debiut na Worlds od 2023', en: 'Worlds debut since 2023' },
  { t: 'last_max', v: 2018, fam: 'last', pl: 'Ostatni Worlds w 2018 lub wcześniej', en: 'Last Worlds in 2018 or earlier' },
  { t: 'last_min', v: 2023, fam: 'last', pl: 'Grał na Worlds w 2023 lub później', en: 'Worlds in 2023 or later' },
  { t: 'streak_min', v: 3, fam: 'streak', pl: 'Na Worlds 3 lata z rzędu', en: '3 Worlds in a row' },
  { t: 'streak_min', v: 4, fam: 'streak', pl: 'Na Worlds 4 lata z rzędu', en: '4 Worlds in a row' },
  { t: 'comeback', v: true, fam: 'streak', pl: 'Wrócił na Worlds po przerwie', en: 'Returned to Worlds after a gap' },
  { t: 'debut_age_max', v: 18, fam: 'debut_age', pl: 'Debiut na Worlds jako nastolatek', en: 'Worlds debut as a teenager' },
  { t: 'debut_age_min', v: 24, fam: 'debut_age', pl: 'Debiut na Worlds po 24. roku życia', en: 'Worlds debut aged 24+' },

  // ---- tytuły ----
  { t: 'champion', v: true, fam: 'title', pl: 'Wygrał Worlds', en: 'Worlds champion' },
  { t: 'never_champion', v: 3, fam: 'title', pl: 'Mimo 3+ startów nigdy nie wygrał Worlds', en: 'Never won Worlds despite 3+ trips' },
  { t: 'never_champion', v: 5, fam: 'title', pl: 'Mimo 5+ startów nigdy nie wygrał Worlds', en: 'Never won Worlds despite 5+ trips' },

  // ---- historia drużyn ----
  { t: 'one_club', v: true, fam: 'team_count', pl: 'Jednoklubowiec – cała kariera w jednej organizacji', en: 'One-club player' },
  { t: 'teams_min', v: 5, fam: 'team_count', pl: 'Grał w min. 5 organizacjach', en: '5+ organisations' },
  { t: 'teams_min', v: 8, fam: 'team_count', pl: 'Objechał ligi – min. 8 organizacji', en: '8+ organisations' },

  // ---- lata Worlds ----
  ...[2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025]
    .map(y => ({ t: 'worlds_year', v: y, fam: 'year', pl: `Grał na Worlds ${y}`, en: `Played at Worlds ${y}` })),

  // ---- konkretne organizacje ----
  ...[
    ['t1', 'T1 / SKT'], ['fnatic', 'Fnatic'], ['g2', 'G2 Esports'], ['c9', 'Cloud9'],
    ['kt', 'KT Rolster'], ['tsm', 'TSM'], ['tl', 'Team Liquid'], ['clg', 'CLG'],
    ['edg', 'EDward Gaming'], ['ig', 'Invictus Gaming'], ['geng', 'Gen.G'],
    ['jdg', 'JD Gaming'], ['blg', 'Bilibili Gaming'], ['rng', 'RNG'], ['tes', 'Top Esports'],
    ['hle', 'Hanwha Life'], ['flyquest', 'FlyQuest'], ['drx', 'DRX'], ['dwg', 'DWG KIA'],
    ['we', 'Team WE'], ['vitality', 'Team Vitality'], ['rge', 'Rogue'], ['mad', 'MAD Lions'],
    ['psg', 'PSG Talon'], ['ahq', 'ahq e-Sports'], ['flashwolves', 'Flash Wolves'],
    ['dignitas', 'Dignitas'], ['100thieves', '100 Thieves'], ['origen', 'Origen'],
    ['misfits', 'Misfits'], ['lng', 'LNG Esports'], ['wbg', 'Weibo Gaming'],
  ].map(([slug, name]) => ({ t: 'team', v: slug, fam: `team:${slug}`, pl: `Grał w ${name}`, en: `Played for ${name}` })),

  // ---- pary organizacji (bardzo zgadywalne: "i tu, i tu") ----
  ...[
    [['fnatic', 'g2'], 'Fnatic i G2'],
    [['t1', 'kt'], 'T1 i KT Rolster'],
    [['c9', 'tl'], 'Cloud9 i Team Liquid'],
    [['tsm', 'c9'], 'TSM i Cloud9'],
    [['edg', 'rng'], 'EDG i RNG'],
    [['t1', 'geng'], 'T1 i Gen.G'],
  ].map(([pair, name]) => ({
    t: 'team_pair', v: pair, fam: `pair:${pair.join('-')}`,
    pl: `Grał i w ${name.split(' i ')[0]}, i w ${name.split(' i ')[1]}`,
    en: `Played for both ${name.replace(' i ', ' and ')}`,
  })),
]

// Rodziny, które nie powinny występować razem w jednym slocie – mówią o tym samym.
const CONFLICTING_FAMILIES = [
  ['league', 'origin'],   // "Grał w LCK" + "Koreańczyk" to prawie ten sam warunek
  ['league', 'import'],
  ['debut', 'year'],
  ['last', 'year'],
  ['debut', 'last'],
  ['worlds_count', 'streak'],
  ['team_count', 'team'],
]

function familiesConflict(a, b) {
  const fa = a.startsWith('team:') ? 'team' : a.startsWith('pair:') ? 'team' : a
  const fb = b.startsWith('team:') ? 'team' : b.startsWith('pair:') ? 'team' : b
  if (fa === fb) return true
  return CONFLICTING_FAMILIES.some(([x, y]) => (fa === x && fb === y) || (fa === y && fb === x))
}

/**
 * Waga losowania rodziny warunków. Chodzi o to, żeby plansze opierały się na
 * faktach, które fan LoL-a faktycznie kojarzy ("grał w G2", "wygrał Worlds",
 * "Polak"), a nie na statystykach, których nikt nie pamięta. Liczba organizacji
 * w karierze jest policzalna, ale nie do zgadnięcia – stąd niska waga.
 */
const FAMILY_WEIGHT = {
  team: 2.2,        // "Grał w Fnatic" – najlepszy typ pytania
  title: 1.8,       // mistrz Worlds / nigdy nie wygrał
  origin: 1.5,      // narodowość
  league: 1.5,
  year: 1.3,        // "Grał na Worlds 2018"
  champion: 1.2,    // signature champion
  import: 1.2,
  worlds_count: 1.0,
  status: 1.0,
  debut: 0.9,
  last: 0.9,
  birth: 0.8,
  streak: 0.7,
  debut_age: 0.6,
  team_count: 0.25, // policzalne, ale niezgadywalne – tylko jako dodatek
}

function weightOf(c) {
  const fam = c.fam.startsWith('team:') || c.fam.startsWith('pair:') ? 'team' : c.fam
  let w = FAMILY_WEIGHT[fam] ?? 1
  // Kontynent to bardzo szerokie pytanie – rzadziej niż konkretny kraj.
  if (c.t === 'continent') w *= 0.4
  return w
}

/** Pula do losowania z uwzględnieniem wag (powielone wpisy = większa szansa). */
const WEIGHTED_POOL = []
for (const c of CONDITION_POOL) {
  const n = Math.max(1, Math.round(weightOf(c) * 4))
  for (let i = 0; i < n; i++) WEIGHTED_POOL.push(c)
}

const ROLE_ORDER = ['top', 'jungle', 'mid', 'adc', 'support']

// ---------------------------------------------------------------- generator

const byRole = {}
for (const r of ROLE_ORDER) {
  byRole[r] = players.filter(p => p.primary_role === r || (p.secondary_roles || []).includes(r))
}

function condKey(c) {
  return `${c.t}:${Array.isArray(c.v) ? c.v.join('+') : c.v}`
}

function baseFamily(fam) {
  return fam.startsWith('team:') || fam.startsWith('pair:') ? 'team' : fam
}

/**
 * Dla każdej roli i każdego warunku – lista pasujących zawodników.
 * Liczone raz; generator robi potem tylko przecięcia zbiorów, dzięki czemu
 * może przejrzeć znacznie więcej kombinacji niż przy filtrowaniu całej puli.
 */
const condIndex = {}
for (const role of ROLE_ORDER) {
  condIndex[role] = CONDITION_POOL.map(c => byRole[role].filter(p => playerMatches(p, c)))
}

function intersect(a, b) {
  const set = new Set(b)
  return a.filter(p => set.has(p))
}

/**
 * Buduje jeden slot.
 *
 * Zamiast twardo wykluczać warunki użyte ostatnio (przy 10-dniowej pamięci
 * wykluczyłoby to praktycznie całą pulę), używamy KAR: powtórzony warunek jest
 * możliwy, ale przegrywa ze świeżym o zbliżonej liczbie kandydatów.
 *
 * Liczba warunków nie jest ustalana z góry. Zaczynamy od jednego "kotwicznego"
 * i dokładamy kolejne tylko wtedy, gdy pula kandydatów jest wciąż za szeroka.
 * Bez tego wąskie, ale najlepsze pytania ("Grał w Cloud9" – kilkunastu graczy
 * na rolę) nigdy nie przechodziły, bo każdy drugi warunek ścinał je do zera.
 */
function generateSlot(date, role, position, dailyId, ctx) {
  const rnd = mulberry32(hashString(`${date}|${role}|worlds-xi-v2`))
  const index = condIndex[role]

  /**
   * Kara za rozmiar puli. Celowo PŁASKA w szerokim przedziale: zagadka z 10
   * poprawnymi odpowiedziami jest tak samo dobra jak ta z 35 (a często lepsza –
   * to właśnie w wąskich pytaniach kryją się rzadkie picki). Wcześniejsza wersja
   * liczyła odległość od 38 kandydatów i przez to systematycznie odrzucała
   * najlepszy typ pytania, czyli "Grał w <organizacja>".
   */
  function sizePenalty(n) {
    if (n < 7) return (7 - n) * 5
    if (n > 45) return (n - 45) * 0.8
    return 0
  }

  function penaltyFor(chosen, n) {
    let pen = 0
    let guess = 0
    for (const c of chosen) {
      const key = condKey(c)
      const fam = baseFamily(c.fam)
      if (ctx.todayKeys.has(key)) pen += 60        // ten sam warunek dziś w innym slocie
      else if (ctx.recentKeys.has(key)) pen += 12  // był w ostatnich dniach
      if ((ctx.todayFamilies.get(fam) || 0) >= 2) pen += 25 // trzeci slot z tym motywem
      guess = Math.max(guess, weightOf(c))
    }
    // Jeden warunek jest OK, gdy sam w sobie jest wąski ("Grał w Fnatic" –
    // kilkunastu graczy na rolę). Karzemy tylko pojedyncze warunki, które
    // zostawiają szeroką pulę, bo to zagadka bez pomysłu.
    if (chosen.length === 1) pen += 5 + (n > 26 ? 12 : 0)
    else if (chosen.length === 3) pen += 4
    // Premia liczona z NAJMOCNIEJSZEGO warunku w slocie – wystarczy jeden dobry
    // "haczyk" ("Grał w Fnatic"), żeby zagadka była zgadywalna; drugi warunek
    // ma ją tylko zawęzić.
    pen -= guess * 5
    return pen
  }

  const pickCondition = () => {
    const c = WEIGHTED_POOL[Math.floor(rnd() * WEIGHTED_POOL.length)]
    return { cond: c, idx: CONDITION_POOL.indexOf(c) }
  }

  let best = null
  const consider = (chosen, candidates) => {
    const n = candidates.length
    if (n < MIN_CANDIDATES || n > MAX_CANDIDATES) return
    const score = sizePenalty(n) + penaltyFor(chosen, n)
    if (!best || score < best.score) best = { chosen, candidates, score }
  }

  for (let attempt = 0; attempt < 320; attempt++) {
    const first = pickCondition()
    let chosen = [first.cond]
    let candidates = index[first.idx]
    if (candidates.length < MIN_CANDIDATES) continue // za wąski warunek – nic nie uratuje

    consider(chosen, candidates)

    // Dokładamy drugi warunek zawsze, gdy da się to zrobić bez zejścia poniżej
    // progu, a trzeci tylko wtedy, gdy pula wciąż jest za szeroka.
    let guard = 0
    while (chosen.length < 3 && guard++ < 40) {
      if (chosen.length === 2 && candidates.length <= IDEAL_MAX) break
      const next = pickCondition()
      if (chosen.some(x => familiesConflict(x.fam, next.cond.fam))) continue
      const merged = intersect(candidates, index[next.idx])
      if (merged.length < MIN_CANDIDATES) continue
      chosen = [...chosen, next.cond]
      candidates = merged
      consider(chosen, candidates)
    }

    if (best && best.score <= -9) break // bardzo dobry zestaw – nie ma po co szukać dalej
  }

  if (!best) {
    // Wariant awaryjny – najszerszy sensowny warunek dla tej roli.
    const idx = CONDITION_POOL.findIndex(c => c.t === 'worlds_min' && c.v === 2)
    best = { chosen: [CONDITION_POOL[idx]], candidates: index[idx], score: 999 }
  }

  // --- pytanie o signature championa ---
  // Dokładamy "Często grał na X" tylko wtedy, gdy realnie zawęża pulę,
  // ale nie sprowadza jej do kilku osób.
  if (best.chosen.length < 3 && best.candidates.length > IDEAL_MIN) {
    const champCounts = {}
    for (const p of best.candidates) {
      for (const c of p.__f.champSet) champCounts[c] = (champCounts[c] || 0) + 1
    }
    const champOpts = Object.entries(champCounts)
      .filter(([, n]) => n >= MIN_CANDIDATES && n <= best.candidates.length - 2)
    if (champOpts.length && rnd() < 0.5) {
      const [champ] = champOpts[Math.floor(rnd() * champOpts.length)]
      const filtered = best.candidates.filter(p => p.__f.champSet.has(champ))
      if (filtered.length >= MIN_CANDIDATES && filtered.length <= MAX_CANDIDATES) {
        best.chosen = [...best.chosen, { t: 'champion_pick', v: champ, fam: 'champion', pl: `Często grał na ${champ}`, en: `Often played ${champ}` }]
        best.candidates = filtered
      }
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
    slot: {
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
    },
    chosen: best.chosen,
  }
}

/** Warunki użyte w ostatnich dniach – żeby zagadki się nie powtarzały. */
const recentDays = []

function generateDaily(date) {
  const id = daysBetween(EPOCH, date) + 1

  const recentKeys = new Set(recentDays.slice(-THEME_MEMORY_DAYS).flat())
  const ctx = { recentKeys, todayKeys: new Set(), todayFamilies: new Map() }

  const slots = []
  for (let i = 0; i < ROLE_ORDER.length; i++) {
    const { slot, chosen } = generateSlot(date, ROLE_ORDER[i], i + 1, id, ctx)
    slots.push(slot)
    for (const c of chosen) {
      ctx.todayKeys.add(condKey(c))
      const fam = baseFamily(c.fam)
      ctx.todayFamilies.set(fam, (ctx.todayFamilies.get(fam) || 0) + 1)
    }
  }

  recentDays.push([...ctx.todayKeys])
  return { id, date, slots }
}

// ---------------------------------------------------------------- main

rmSync(OUT, { recursive: true, force: true })
mkdirSync(join(OUT, 'dailies'), { recursive: true })

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

// 1. players.json – odchudzony (do wyszukiwarki)
// `primary_role` jest potrzebne, żeby panel wyboru filtrował listę do roli slotu.
const slim = players.map(p => ({
  slug: p.slug,
  nickname: decodeEntities(p.nickname),
  real_name: decodeEntities(p.real_name),
  country_code: p.country_code || '',
  residency: p.residency || '',
  primary_role: p.primary_role,
  worlds_count: p.worlds_count || 0,
  is_active: !!p.is_active,
}))
writeFileSync(join(OUT, 'players.json'), JSON.stringify(slim))

// 2. dailies
const today = isoDate(new Date())
const start = addDays(today, -DAYS_BACK)
const total = DAYS_BACK + DAYS_FORWARD + 1
const index = []
const stats = { conditions: 0, candidates: [], fallbacks: 0 }

for (let i = 0; i < total; i++) {
  const date = addDays(start, i)
  const daily = generateDaily(date)
  writeFileSync(join(OUT, 'dailies', `${daily.id}.json`), JSON.stringify(daily))
  index.push({ id: daily.id, date })
  for (const s of daily.slots) {
    stats.conditions += s.conditions.length
    stats.candidates.push(s.answers.length)
    if (s.conditions.length === 1) stats.fallbacks++
  }
}

writeFileSync(join(OUT, 'index.json'), JSON.stringify({
  generated_at: new Date().toISOString(),
  epoch: EPOCH,
  days: index,
}))

const avgCand = Math.round(stats.candidates.reduce((s, n) => s + n, 0) / stats.candidates.length)
const minCand = Math.min(...stats.candidates)
const maxCand = Math.max(...stats.candidates)
console.log(`✔ dane gry: ${slim.length} graczy, ${index.length} dni (${start} → ${index[index.length - 1].date})`)
console.log(`  pula warunków: ${CONDITION_POOL.length} · śr. warunków na slot: ${(stats.conditions / stats.candidates.length).toFixed(2)}`)
console.log(`  kandydatów na slot: min ${minCand} · śr. ${avgCand} · max ${maxCand} · awaryjnych slotów: ${stats.fallbacks}`)
console.log(`  → frontend/public/data/`)

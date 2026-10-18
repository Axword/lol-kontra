const assert = require('node:assert/strict')
const { readFileSync } = require('node:fs')
const path = require('node:path')
const test = require('node:test')
const vm = require('node:vm')

const configPath = path.join(__dirname, 'next.config.js')
const source = readFileSync(configPath, 'utf8')

function loadConfig(env = {}) {
  const context = { process: { env }, module: { exports: {} }, URL }
  vm.runInNewContext(source, context, { filename: configPath })
  return context.module.exports
}

test('local development keeps the localhost API fallback', () => {
  assert.equal(loadConfig().env.NEXT_PUBLIC_API_URL, 'http://localhost:8000/api/v1')
})

test('Docker can use the same-origin relative API outside Vercel', () => {
  assert.equal(loadConfig({ NEXT_PUBLIC_API_URL: '/api/v1' }).env.NEXT_PUBLIC_API_URL, '/api/v1')
})

test('Vercel development mode keeps local settings even with VERCEL=1', () => {
  assert.equal(loadConfig({ VERCEL: '1', VERCEL_ENV: 'development' }).env.NEXT_PUBLIC_API_URL,
    'http://localhost:8000/api/v1')
})

for (const deployment of [{ VERCEL: '1' }, { VERCEL_ENV: 'production' }, { VERCEL_ENV: 'preview' }]) {
  test(`deployment ${JSON.stringify(deployment)} requires an explicit API`, () => {
    assert.throws(() => loadConfig(deployment), /NEXT_PUBLIC_API_URL/)
  })
}

test('a separate public HTTPS API is accepted on Vercel', () => {
  const api = 'https://api.example.com/api/v1'
  assert.equal(loadConfig({ VERCEL: '1', NEXT_PUBLIC_API_URL: api }).env.NEXT_PUBLIC_API_URL, api)
})

test('a separate Vercel API project is accepted', () => {
  const api = 'https://backend-project.vercel.app/api/v1'
  assert.equal(loadConfig({ VERCEL: '1', VERCEL_URL: 'frontend-project.vercel.app', NEXT_PUBLIC_API_URL: api })
    .env.NEXT_PUBLIC_API_URL, api)
})

for (const api of [
  '', ' ', '/api/v1', '//api.example.com/api/v1', 'not-a-url',
  'http://api.example.com/api/v1', 'https:api.example.com/api/v1',
  'https://api.example.com/api/v1?token=private-query', 'https://api.example.com/api/v1?',
  'https://api.example.com/api/v1#private-fragment', 'https://api.example.com/api/v1#',
  'https://user:private-password@api.example.com/api/v1',
  ' https://api.example.com/api/v1', 'https://api.example.com/api/v1 ',
]) {
  test(`Vercel rejects invalid API option ${api ? api.split(':')[0] : '(empty)'} (${api.length} chars)`, () => {
    assert.throws(() => loadConfig({ VERCEL: '1', NEXT_PUBLIC_API_URL: api }), /NEXT_PUBLIC_API_URL/)
  })
}

for (const host of [
  'localhost', 'LOCALHOST.', 'dev.localhost', '127.0.0.1', '127.20.30.40',
  '127.1', '2130706433', '0x7f000001', '0.0.0.0', '[::1]', '[::]', '[::ffff:127.0.0.1]',
]) {
  test(`Vercel rejects loopback or local-only API ${host}`, () => {
    assert.throws(() => loadConfig({ VERCEL_ENV: 'production', NEXT_PUBLIC_API_URL: `https://${host}/api/v1` }),
      /NEXT_PUBLIC_API_URL/)
  })
}

for (const variable of ['VERCEL_URL', 'VERCEL_BRANCH_URL', 'VERCEL_PROJECT_PRODUCTION_URL', 'NEXT_PUBLIC_APP_URL']) {
  test(`Vercel rejects this frontend hostname from ${variable}`, () => {
    assert.throws(() => loadConfig({
      VERCEL: '1', [variable]: 'frontend.example.com', NEXT_PUBLIC_API_URL: 'https://frontend.example.com/api/v1',
    }), /NEXT_PUBLIC_API_URL/)
  })
}

test('frontend hostname comparison supports full URLs, case and trailing DNS dots', () => {
  assert.throws(() => loadConfig({
    VERCEL_ENV: 'preview', NEXT_PUBLIC_APP_URL: 'https://Frontend.Example.com/',
    NEXT_PUBLIC_API_URL: 'https://frontend.example.com./api/v1',
  }), /NEXT_PUBLIC_API_URL/)
})

test('configuration errors do not reveal credentials, query values or fragments', () => {
  for (const api of [
    'https://user:private-password@api.example.com/api/v1',
    'https://api.example.com/api/v1?token=private-query',
    'https://api.example.com/api/v1#private-fragment',
  ]) {
    assert.throws(() => loadConfig({ VERCEL: '1', NEXT_PUBLIC_API_URL: api }), error => {
      assert.match(error.message, /NEXT_PUBLIC_API_URL/)
      assert.doesNotMatch(error.message, /private-password|private-query|private-fragment|user:|api\.example/)
      return true
    })
  }
})

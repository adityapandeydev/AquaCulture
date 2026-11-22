// Drives the whole product in Chrome and measures its motion.
// Usage: node e2e/tour.mjs <screenshot folder> <csv file>. The app must run on http://127.0.0.1:5190 with an empty test database.
import { mkdirSync, readFileSync } from 'node:fs'
import { chromium } from 'playwright-core'

const [out = 'e2e/shots', csvPath] = process.argv.slice(2)
mkdirSync(out, { recursive: true })
const base = process.env.APP_URL ?? 'http://127.0.0.1:5190'
const email = `tour-${Date.now()}@aquatech.invalid`
const problems = []
const results = {}

const browser = await chromium.launch({ channel: 'chrome' })
const context = await browser.newContext({ viewport: { width: 1360, height: 860 }, colorScheme: 'light' })
const page = await context.newPage()
page.on('console', (m) => { if (['error', 'warning'].includes(m.type()) && !/401/.test(m.text())) problems.push(`console ${m.type()}: ${m.text()}`) })
page.on('pageerror', (e) => problems.push('page error: ' + e.message))
const shot = (name, p = page) => p.screenshot({ path: `${out}/${name}.png` })
const settle = (ms = 900) => page.waitForTimeout(ms)
const expect = (ok, text) => { if (!ok) problems.push('failed: ' + text) }

/** Wait until charts have finished drawing, and report how long it took. */
async function drawn() {
  const began = Date.now()
  await page.waitForFunction(() => document.querySelector('.chart .draw path') && document.getAnimations().every((a) => !['draw', 'pop'].includes(a.animationName) || a.playState === 'finished'), null, { timeout: 8000 })
  const open = await page.evaluate(() => /^inset\((-10px|calc\(0% - 10px\))/.test(getComputedStyle(document.querySelector('.chart .draw')).clipPath))
  expect(open, 'the chart line is fully drawn')
  return Date.now() - began
}

/** Frames drawn while something moves, in a window of time. */
async function frames(action, ms = 900) {
  await page.evaluate(() => {
    window.__gaps = []
    let last = performance.now()
    window.__run = true
    const tick = (t) => { window.__gaps.push(t - last); last = t; if (window.__run) requestAnimationFrame(tick) }
    requestAnimationFrame((t) => { last = t; requestAnimationFrame(tick) })
  })
  await action()
  await page.waitForTimeout(ms)
  return page.evaluate(() => {
    window.__run = false
    const g = window.__gaps.slice(1).sort((a, b) => a - b)
    return { frames: g.length, median_ms: +g[Math.floor(g.length / 2)].toFixed(1), p95_ms: +g[Math.floor(g.length * 0.95)].toFixed(1), worst_ms: +g.at(-1).toFixed(1) }
  })
}

// Boot
await page.addInitScript(() => {
  window.__cls = 0
  new PerformanceObserver((l) => { for (const e of l.getEntries()) if (!e.hadRecentInput) window.__cls += e.value }).observe({ type: 'layout-shift', buffered: true })
  window.__long = []
  new PerformanceObserver((l) => { for (const e of l.getEntries()) window.__long.push(Math.round(e.duration)) }).observe({ type: 'longtask', buffered: true })
})
const started = Date.now()
await page.goto(base, { waitUntil: 'commit' })
await page.waitForTimeout(350); await shot('01-boot-drop')
await page.waitForTimeout(450); await shot('02-boot-rise')
await page.waitForFunction(() => !document.getElementById('boot'), null, { timeout: 8000 })
results.boot_seconds_first_visit = (Date.now() - started) / 1000
await settle(500); await shot('03-sign-in')

// Account
await page.getByText('Create account', { exact: true }).first().click()
await page.getByLabel('Name').fill('Asha Rao')
await page.getByLabel('Email').fill(email)
await page.getByLabel('Password').fill('a long test password')
await page.getByRole('button', { name: 'Create account' }).click()
await page.getByRole('heading', { name: 'Add your first pond' }).waitFor()
await settle(); await shot('04-empty')

// Demo pond
await page.getByRole('link', { name: 'Add a pond' }).first().click()
await page.getByLabel('Name').fill('North pond')
await page.getByText('Recorded demo').click()
await page.getByLabel('Timezone').selectOption('Asia/Kolkata')
await page.getByRole('button', { name: 'Use these values' }).click()
await page.getByLabel('Critical oxygen').fill('2')
await settle(); await page.screenshot({ path: `${out}/05-new-pond.png`, fullPage: true })
await page.getByRole('button', { name: 'Add pond' }).click()
await page.getByRole('heading', { name: 'Import readings' }).waitFor()

// Import
const csv = csvPath ? (csvPath.endsWith('.json') ? JSON.parse(readFileSync(csvPath, 'utf8')).csv : readFileSync(csvPath, 'utf8')) : null
if (!csv) throw new Error('Give a CSV file')
await page.getByLabel('CSV file').setInputFiles({ name: 'north-pond.csv', mimeType: 'text/csv', buffer: Buffer.from(csv) })
await page.getByRole('button', { name: /Store [\d,]+ readings/ }).waitFor()
await settle(500); await shot('06-import-preview')
await page.getByRole('button', { name: /Store [\d,]+ readings/ }).click()
await page.getByRole('heading', { name: 'Replay a forecast' }).waitFor()
await settle(1200)
await page.locator('#issue').fill(String(Number(await page.locator('#issue').getAttribute('max')) - 60))
await page.screenshot({ path: `${out}/07-data.png`, fullPage: true })
await page.getByRole('button', { name: 'Make the forecasts' }).click()
await page.getByRole('heading', { name: 'Low-oxygen chance' }).waitFor()
await page.locator('.chance').nth(3).waitFor({ timeout: 20000 })
await settle(3000); results.chart_drawn_wait_ms = await drawn(); await page.screenshot({ path: `${out}/08-now.png`, fullPage: true })
const chart = page.locator('.chart')
const box = await chart.boundingBox()
await page.mouse.move(box.x + box.width * 0.8, box.y + 120); await settle(200); await shot('09-chart-hover')
expect((await page.locator('.tip').count()) === 1, 'the chart shows a tooltip')
expect((await page.getByText('No value is forecast this far ahead').count()) === 1, 'the +12 h value is withheld')
expect((await page.locator('.range').count()) === 1, 'only one 90% range is drawn')
results.frames_chart_redraw = await frames(() => page.getByText('7 days').click())
await settle(600); await shot('10-seven-days')
results.frames_hover = await frames(async () => { for (let i = 0; i < 40; i++) await page.mouse.move(box.x + 60 + i * ((box.width - 120) / 40), box.y + 100) }, 100)
await page.getByRole('button', { name: 'Show table' }).click(); await settle(400); await shot('11-table')
await page.getByRole('button', { name: 'Show chart' }).click()

// Tabs and pages
results.frames_tab = await frames(() => page.getByRole('link', { name: 'Accuracy' }).click())
await settle(400); await shot('12-accuracy')
await page.getByRole('link', { name: 'Settings' }).click(); await settle(); await page.screenshot({ path: `${out}/13-settings.png`, fullPage: true })
await page.getByRole('button', { name: 'Delete this pond' }).click(); await settle(400); await shot('14-dialog')
await page.keyboard.press('Escape')

// Live pond with a device
await page.getByRole('link', { name: 'All ponds' }).click(); await settle(400)
await page.getByRole('link', { name: 'Add a pond' }).click()
await page.getByLabel('Name').fill('Prawn tank')
await page.getByLabel('Species').selectOption('vannamei')
await page.getByLabel('Low oxygen').fill('4')
await page.getByRole('button', { name: 'Add pond' }).click()
await page.getByLabel('Device name').fill('Probe 1')
await page.getByRole('button', { name: 'Add device' }).click()
await page.getByRole('heading', { name: 'Save this key now' }).waitFor(); await settle(400); await shot('15-device-key')
const key = await page.locator('dialog .secret').innerText()
await page.getByRole('button', { name: 'I saved it' }).click()
const send = (value) => context.request.post(base + '/api/v1/ingest', { headers: { Authorization: 'Device ' + key }, data: { readings: [{ observed_at: new Date().toISOString(), do_mgL: value, ph: 8, temperature_c: 27 }] } })
expect((await send(3.2)).ok(), 'the device can send')
await page.getByRole('link', { name: 'Now', exact: true }).click(); await settle(400)
await page.reload(); await page.locator('.gauge').waitFor(); await settle(1500); await page.screenshot({ path: `${out}/16-live.png`, fullPage: true })
expect((await page.getByText('There is no forecast model for this species').count()) === 1, 'shrimp has no forecast')

results.frames_page = await frames(() => page.getByRole('link', { name: 'AquaTech' }).click())
await settle(1200); await shot('17-ponds')
const order = await page.locator('.row h2').allInnerTexts()
expect(order.length === 2, 'two ponds are listed')
await page.getByRole('link', { name: /Alerts/ }).first().click(); await settle(); await shot('18-alerts')
await page.getByRole('button', { name: 'Acknowledge' }).first().click(); await settle(1200)
await page.getByRole('link', { name: 'Model' }).click(); await settle(1200); await page.screenshot({ path: `${out}/19-model.png`, fullPage: true })

// Idle cost: what still runs when nothing happens
await page.getByRole('link', { name: 'Ponds', exact: true }).click(); await settle(2500)
results.running_when_idle = await page.evaluate(() => document.getAnimations().filter((a) => a.playState === 'running').map((a) => a.animationName ?? 'transition'))
const cdp = await context.newCDPSession(page)
await cdp.send('Performance.enable')
const metric = async () => Object.fromEntries((await cdp.send('Performance.getMetrics')).metrics.map((m) => [m.name, m.value]))
const a = await metric(); await page.waitForTimeout(4000); const b = await metric()
results.idle_main_thread_percent = +(((b.TaskDuration - a.TaskDuration) / 4) * 100).toFixed(2)
results.idle_layouts = b.LayoutCount - a.LayoutCount
results.layout_shift = +(await page.evaluate(() => window.__cls)).toFixed(4)
results.long_tasks_ms = await page.evaluate(() => window.__long)

// Dark, phone, reduced motion, signed out
await page.getByRole('button', { name: 'Use the dark theme' }).click(); await settle(500); await shot('20-dark-ponds')
await page.locator('.row', { hasText: 'North pond' }).click(); await settle(2000); await page.screenshot({ path: `${out}/21-dark-now.png`, fullPage: true })
await page.setViewportSize({ width: 390, height: 844 }); await settle(1000); await page.screenshot({ path: `${out}/22-phone-now.png`, fullPage: true })
const overflow = await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)
expect(overflow <= 0, `the phone page scrolls sideways by ${overflow}px`)
await page.getByRole('link', { name: 'Ponds' }).first().click(); await settle(); await shot('23-phone-ponds')
// A slow phone: the processor runs six times slower.
await cdp.send('Emulation.setCPUThrottlingRate', { rate: 6 })
results.slow_phone_page = await frames(() => page.getByRole('link', { name: /Alerts/ }).first().click(), 1200)
results.slow_phone_pond = await frames(async () => { await page.getByRole('link', { name: 'Ponds' }).first().click(); await page.locator('.row', { hasText: 'North pond' }).click() }, 1800)
results.slow_phone_scroll = await frames(async () => { for (let i = 0; i < 12; i++) { await page.mouse.wheel(0, 120); await page.waitForTimeout(40) } }, 200)
await cdp.send('Emulation.setCPUThrottlingRate', { rate: 1 })
await page.emulateMedia({ reducedMotion: 'reduce' }); await page.reload(); await settle(1500)
results.running_with_reduced_motion = await page.evaluate(() => document.getAnimations().filter((a) => a.playState === 'running').length)
expect(results.running_with_reduced_motion === 0, 'reduced motion leaves nothing running')
await page.getByRole('button', { name: 'Sign out' }).click(); await page.getByLabel('Email').waitFor()
await page.goto(base + '/alerts'); await page.getByLabel('Email').waitFor()
expect(page.url().endsWith('/sign-in'), 'signed-out visitors are sent to sign in')

// A repeat visit in one session must not replay the long boot.
const again = Date.now()
await page.emulateMedia({ reducedMotion: 'no-preference' })
await page.goto(base); await page.waitForFunction(() => !document.getElementById('boot'))
results.boot_seconds_repeat = (Date.now() - again) / 1000
await browser.close()
console.log(JSON.stringify(results, null, 1))
console.log(problems.length ? 'PROBLEMS\n' + problems.join('\n') : 'no problems')
process.exit(problems.length ? 1 : 0)

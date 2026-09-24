import fs from 'node:fs/promises'
import { existsSync } from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { fileURLToPath } from 'node:url'
import { chromium } from 'playwright'
import { PlaywrightAgent } from '@midscene/web/playwright'

const inputPath = process.argv[2]
if (!inputPath) {
  throw new Error('runner input file is required')
}

const input = JSON.parse(await fs.readFile(inputPath, 'utf8'))
const interpolate = (text) => String(text || '').replace(/\{\{\s*([^{}]+?)\s*\}\}|\$\{\s*([A-Za-z0-9_]+)\s*\}/g, (match, doubleBraceKey, dollarKey) => {
  const key = doubleBraceKey || dollarKey
  const value = input.variables?.[key] ?? input.variables?.[key.toLowerCase()]
  return value === undefined || value === null ? match : String(value)
})
let scenarioPrompt = interpolate(input.prompt)
const scenarioContext = interpolate(input.context)

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
// The stored case carries container paths and hostnames. The same case also runs
// straight from a developer machine, where neither resolves, so pick the first
// candidate that actually exists instead of making the case environment-specific.
const inContainer = existsSync('/.dockerenv') || existsSync('/app/web/assets')
const fileChooserAllowedDir = [
  process.env.MIDSCENE_FILE_CHOOSER_ALLOWED_DIR,
  input.file_chooser_allowed_dir,
  '/app/web/assets/uat_fp_documents',
  path.join(repoRoot, 'web', 'assets', 'uat_fp_documents'),
].find((candidate) => candidate && existsSync(candidate))
  || path.join(repoRoot, 'web', 'assets', 'uat_fp_documents')

const resolveMockApiBaseUrl = (configured) => {
  const baseUrl = String(configured || 'http://host.docker.internal:8001').replace(/\/+$/, '')
  if (inContainer) return baseUrl
  return baseUrl.replace('host.docker.internal', '127.0.0.1')
}

const viewport = {
  width: Number(input.viewport?.width || 1280),
  height: Number(input.viewport?.height || 800),
}

const requestedHeaded = input.headed === true
const hasDisplay = Boolean(process.env.DISPLAY || process.env.WAYLAND_DISPLAY)
const headless = requestedHeaded && process.platform === 'linux' && !hasDisplay
  ? true
  : !requestedHeaded

const runDir = process.env.MIDSCENE_RUN_DIR || path.join(path.dirname(fileURLToPath(import.meta.url)), 'midscene_run')
const videoDir = path.join(runDir, 'videos')

const sleep = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds))

// The UAT gateway in front of the webhook endpoint answers with a 5xx HTML error
// page every so often. That is an upstream blip, not a rejection of the payload, so
// it is the one failure worth retrying; a real backend rejection comes back as 200
// with success=false and must fail immediately.
const isUpstreamBlip = (body) => {
  const upstreamStatus = Number(body?.data?.response_info?.status_code || body?.data?.status_code || 0)
  return upstreamStatus >= 500
}

async function apiJson(baseUrl, pathname, payload, attempts = 3) {
  let lastError = null
  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    let response
    let body = {}
    try {
      response = await fetch(`${baseUrl}${pathname}`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(payload),
      })
      body = await response.json().catch(() => ({}))
    } catch (error) {
      lastError = error
      await sleep(5000)
      continue
    }
    if (response.ok && body.success !== false && body.data?.success !== false) return body
    lastError = new Error(`${pathname} failed (${response.status}): ${JSON.stringify(body)}`)
    if (response.status < 500 && !isUpstreamBlip(body)) break
    await sleep(5000)
  }
  throw lastError
}

function randomPhone() {
  return `1${Math.floor(3000000000 + Math.random() * 6999999999)}`
}

const reportMetadata = {
  environment: String(input.variables?.report_environment || input.variables?.environment || 'unknown'),
  phone: String(input.variables?.phone_number || ''),
  merchant: String(input.variables?.merchant_id || ''),
  application: String(input.variables?.application_id || ''),
}

async function writeEvidenceIndex() {
  const imageNames = [
    ['注册信息填写页', 'registration-completed.png'],
    ['安全问题填写完成', 'security-question-completed.png'],
    ['企业信息填写完成', 'business-page-filled.png'],
  ]
  const sections = []
  for (const [label, filename] of imageNames) {
    const imagePath = path.join(runDir, filename)
    try {
      const image = (await fs.readFile(imagePath)).toString('base64')
      sections.push(`<section><h2>${label}</h2><p>${filename}</p><img src="data:image/png;base64,${image}" alt="${label}" /></section>`)
    } catch {
      sections.push(`<section><h2>${label}</h2><p>本次运行未生成：${filename}</p></section>`)
    }
  }
  const metadata = Object.entries(reportMetadata)
    .map(([key, value]) => `<li><strong>${key}</strong>：${value || '-'}</li>`)
    .join('')
  await fs.writeFile(
    path.join(runDir, 'evidence-index.html'),
    `<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>AI UI 步骤证据</title><style>body{font-family:Arial,sans-serif;margin:32px;color:#1f2937}h1{margin-bottom:8px}ul{line-height:1.8;padding-left:20px}section{margin:28px 0;padding:18px;border:1px solid #d1d5db;border-radius:8px}img{display:block;max-width:100%;height:auto;border:1px solid #e5e7eb}p{color:#6b7280}</style><h1>AI UI 步骤证据</h1><ul>${metadata}</ul>${sections.join('')}</html>`,
    'utf8',
  )
}

async function fillCode(page, code) {
  const inputs = page.locator('div[aria-label$="Digit"] input')
  await inputs.first().waitFor({ state: 'visible', timeout: 15000 })
  for (let index = 0; index < code.length; index += 1) await inputs.nth(index).fill(code[index])
  // An auto-advancing OTP widget can swallow or shift digits, and that looks exactly
  // like a rejected code two steps later. Read the boxes back while the cause is
  // still local. Locator has allInnerTexts/allTextContents but no bulk value
  // reader, so the values come from the DOM nodes themselves.
  const typed = (await inputs.evaluateAll((nodes) => nodes.map((node) => node.value || ''))).join('')
  if (typed !== code) {
    throw new Error(`验证码回读不一致：期望 ${code}，实际读到 ${typed || '(空)'}`)
  }
}

const readSelectedValue = (select) => select.evaluate((element) => {
  const values = Array.from(element.querySelectorAll(
    '.el-select__selected-item, .el-tag__content, input.el-select__input',
  )).map((node) => {
    if (node instanceof HTMLInputElement) return node.value.trim()
    return node.textContent?.trim() || ''
  })
  return values.some((value) => value && value !== '请选择')
})

// The country/industry option lists are populated only after the business
// registration lookup responds, so option nodes must be awaited instead of
// assuming they exist once the page rendered.
async function waitForSelectOptions(page, timeout = 60000) {
  await page.waitForFunction(
    () => document.querySelectorAll('.el-select .el-select-dropdown__item').length > 0,
    { timeout },
  )
}

async function selectFirstVisibleOption(page, select) {
  const wrapper = select.locator('.el-select__wrapper')
  const combobox = select.locator('input.el-select__input').first()
  // Each select on this page renders its popper inline inside .el-select rather
  // than teleporting it to the body, so scope the dropdown to the select and
  // never guess which document-level popper belongs to it.
  const dropdown = select.locator('.el-select-dropdown').first()
  const option = select.locator('.el-select-dropdown__item:not(.is-disabled)').first()
  let lastError = null
  for (let attempt = 0; attempt < 3; attempt += 1) {
    try {
      await option.waitFor({ state: 'attached', timeout: 30000 })
      await select.scrollIntoViewIfNeeded()
      if (await combobox.getAttribute('aria-expanded') !== 'true') {
        await wrapper.click()
      }
      await dropdown.waitFor({ state: 'visible', timeout: 10000 })
      await option.click()
      await page.keyboard.press('Escape')
      await sleep(300)
      if (await readSelectedValue(select)) return
      lastError = new Error('下拉项点击后未检测到已选值')
    } catch (error) {
      lastError = error
    }
    await page.keyboard.press('Escape').catch(() => {})
    await sleep(1000)
  }
  throw new Error(`下拉项选择失败：${lastError?.message || lastError}`)
}

// Element Plus toasts disappear on their own, so upload rejections have to be
// captured as they happen instead of read back after the fact.
async function installNoticeCollector(page) {
  await page.evaluate(() => {
    if (window.__noticeCollectorInstalled) return
    window.__noticeCollectorInstalled = true
    window.__notices = []
    const record = (node) => {
      if (!(node instanceof HTMLElement)) return
      if (!node.matches('.el-message, .el-notification, .el-message-box, .el-message-box__wrapper')) return
      const text = node.textContent?.trim().replace(/\s+/g, ' ')
      if (text && !window.__notices.includes(text)) window.__notices.push(text)
    }
    new MutationObserver((records) => {
      for (const mutation of records) mutation.addedNodes.forEach(record)
    }).observe(document.body, { childList: true, subtree: true })
  })
}

const readNotices = (page) => page.evaluate(() => window.__notices || []).catch(() => [])

// The upload rejection is silent in the UI, so the server's own answer is the only
// evidence available. The rejecting call is not necessarily the upload endpoint
// itself, so record every application request instead of guessing its URL.
const uploadResponses = []

function installUploadResponseRecorder(page) {
  page.on('response', async (response) => {
    const request = response.request()
    if (!['xhr', 'fetch'].includes(request.resourceType())) return
    const contentType = response.headers()['content-type'] || ''
    const record = {
      method: request.method(),
      url: response.url(),
      status: response.status(),
      body: '',
    }
    if (/json|text/i.test(contentType)) {
      record.body = (await response.text().catch(() => '')).slice(0, 900)
    }
    uploadResponses.push(record)
    if (uploadResponses.length > 200) uploadResponses.shift()
  })
}

// This page renders its upload control with show-upload-list=false, so the accepted
// file never appears as an .el-upload-list entry. The upload endpoint's own 200 with
// sanityCheck=true is the acceptance signal; the card header's 已完善 state is the gate.
async function waitForUploadResponse(startIndex, timeout = 40000) {
  const deadline = Date.now() + timeout
  while (Date.now() < deadline) {
    const hit = uploadResponses
      .slice(startIndex)
      .find((response) => /files\/upload\/image/.test(response.url) && response.status === 200)
    if (hit) return hit
    await sleep(500)
  }
  return null
}

// A filled slot drops its own input[type="file"] and shows the file name instead,
// so the slot's own text is the only way to tell what the page currently holds.
// Nested form items put ancestors first in DOM order, so the deepest match wins.
const readSlotText = async (container, label) => {
  const content = container
    .locator('.el-form-item')
    .filter({ hasText: label })
    .last()
    .locator('.el-form-item__content')
    .first()
  const text = await content.innerText().catch(() => '')
  return text.replace(/\s+/g, ' ').trim()
}

// The identity-type radio group is preselected asynchronously, and its watcher
// clears the file list, which silently discards a file uploaded before it fires.
async function waitForIdentityTypeSettled(page, card) {
  await page.waitForFunction(
    (element) => Array.from(element.querySelectorAll('input[type="radio"]')).some((node) => node.checked),
    await card.elementHandle(),
    { timeout: 30000 },
  ).catch(() => {})
  await sleep(2000)
}

async function uploadFileByLabel(page, container, label, filePath) {
  const filename = path.basename(filePath)
  const holdsFile = async () => (await readSlotText(container, label)).includes(filename)
  for (let attempt = 0; attempt < 4; attempt += 1) {
    if (await holdsFile()) return
    const labelNode = container.getByText(label, { exact: true }).first()
    await labelNode.waitFor({ state: 'visible', timeout: 30000 })
    const fileInput = labelNode.locator('xpath=following::input[@type="file"][1]')
    await fileInput.waitFor({ state: 'attached', timeout: 10000 })
    const startIndex = uploadResponses.length
    await fileInput.setInputFiles(filePath)
    if (!await waitForUploadResponse(startIndex)) {
      throw new Error(`${label} 上传未收到服务端成功响应，页面提示：${JSON.stringify(await readNotices(page))}`)
    }
    // The file name has to survive the page's own post-upload watchers, so it is
    // sampled again after it first appears instead of trusting the first sighting.
    for (let tick = 0; tick < 8; tick += 1) {
      await sleep(1000)
      if (!await holdsFile()) continue
      await sleep(2000)
      if (await holdsFile()) return
      break
    }
  }
  throw new Error(`${label} 连续上传后仍未保留在该栏位，栏位内容：${await readSlotText(container, label)}，页面提示：${JSON.stringify(await readNotices(page))}`)
}

async function dumpUploadTimeline() {
  await fs.writeFile(
    path.join(runDir, 'director-all-responses.json'),
    JSON.stringify(uploadResponses, null, 2),
    'utf8',
  ).catch(() => {})
}

// 已完善/待完善 in the card header is the page's own per-person validation verdict,
// which covers the uploads and every field at once.
async function waitForPersonCardCompleted(page, card, personLabel) {
  const header = card.locator('.el-collapse-item__header')
  try {
    await page.waitForFunction(
      (element) => /已完善/.test(element.textContent || ''),
      await header.elementHandle(),
      { timeout: 30000 },
    )
  } catch {
    const cardText = (await card.innerText().catch(() => '')).replace(/\s+/g, ' ').slice(0, 800)
    await dumpUploadTimeline()
    throw new Error(`${personLabel} 填写后卡片仍未显示“已完善”：${cardText}，页面提示：${JSON.stringify(await readNotices(page))}`)
  }
}

async function fillFollowingInput(page, container, label, value) {
  const labelNode = container.getByText(label, { exact: true }).first()
  await labelNode.waitFor({ state: 'visible', timeout: 30000 })
  const input = labelNode.locator(
    'xpath=following::input[not(@type="file") and not(@readonly) and not(@disabled)][1]',
  )
  await input.waitFor({
    state: 'visible',
    timeout: 30000,
  })
  await input.fill(value)
  await input.press('Tab')
  if (await input.inputValue() !== value) {
    throw new Error(`${label}填写后回读不一致`)
  }
}

// Element Plus keeps its validation text in .el-form-item__error next to the
// offending control, so pair each message with the nearest label to make a
// failed submit diagnosable without replaying the whole run.
async function dumpFormErrors(page, filename) {
  const details = await page.evaluate(() => {
    const errors = Array.from(document.querySelectorAll('.el-form-item__error')).map((node) => {
      const item = node.closest('.el-form-item')
      const label = item?.querySelector('.el-form-item__label, .label')?.textContent?.trim() || ''
      return `${label} => ${node.textContent?.trim() || ''}`
    })
    const cards = Array.from(document.querySelectorAll('.el-collapse-item__header')).map(
      (node) => node.textContent?.trim().replace(/\s+/g, ' ') || '',
    )
    // A blocking dialog keeps the route unchanged without producing any field
    // error, which otherwise looks identical to a silent submit failure.
    const dialogs = Array.from(document.querySelectorAll('.el-overlay, .el-message-box__wrapper'))
      .filter((node) => node instanceof HTMLElement && node.offsetParent !== null)
      .map((node) => node.textContent?.trim().replace(/\s+/g, ' ').slice(0, 300) || '')
      .filter(Boolean)
    return { errors, cards, dialogs, url: location.href }
  })
  await fs.writeFile(path.join(runDir, filename), JSON.stringify(details, null, 2), 'utf8')
  return details
}

// `dpu_users.token` is empty on UAT, so MockAPI cannot recover the signup token
// from the database. The portal sends it on every authenticated XHR, so the
// Authorization header of the page's own traffic is the one reliable source.
function installAuthorizationTokenRecorder(page) {
  const holder = { token: '' }
  page.on('request', (request) => {
    const header = request.headers().authorization || request.headers().Authorization || ''
    const bearer = header.replace(/^Bearer\s+/i, '').trim()
    if (bearer && bearer !== 'null' && bearer !== 'undefined') holder.token = bearer
  })
  return holder
}

async function attachSessionToken(mockApiBaseUrl, common, tokenHolder) {
  for (let attempt = 0; attempt < 10 && !tokenHolder.token; attempt += 1) {
    await sleep(1000)
  }
  if (!tokenHolder.token) {
    throw new Error('未能从 UAT 页面请求头中取到用户 token，后续 MockAPI 步骤无法鉴权')
  }
  await apiJson(mockApiBaseUrl, '/api/register/attach-session-token', {
    session_id: common.session_id,
    username: common.username,
    token: tokenHolder.token,
  })
  return tokenHolder.token
}

// Every DOM phase can stall on a control that never appears, and a stalled phase has
// no deadline of its own: the run only ends when the service's watchdog SIGKILLs the
// process, which loses the final JSON, every page dump and the tail of the video --
// exactly the evidence needed to tell a stall apart from a rejection. Each phase
// therefore names itself in the report before it starts and carries its own deadline.
async function runStep(page, agent, { name, slug, timeout }, body) {
  const note = async (text) => {
    if (agent) await agent.recordToReport(text).catch(() => {})
  }
  const elapsed = (since) => Math.round((Date.now() - since) / 1000)
  await note(`步骤开始：${name}`)
  const started = Date.now()
  const work = body()
  // Promise.race leaves the loser running, so a rejection arriving after the deadline
  // must not surface as an unhandled rejection once this function has already thrown.
  work.catch(() => {})
  let timer
  try {
    const result = await Promise.race([
      work,
      new Promise((_, reject) => {
        timer = setTimeout(
          () => reject(new Error(`步骤「${name}」超过 ${Math.round(timeout / 1000)} 秒未完成`)),
          timeout,
        )
      }),
    ])
    await note(`步骤完成：${name}（${elapsed(started)} 秒）`)
    return result
  } catch (error) {
    await dumpPage(page, `step-${slug}-failed`)
    const pageText = (await page.locator('body').innerText().catch(() => ''))
      .replace(/\s+/g, ' ')
      .slice(0, 1200)
    await note(`步骤失败：${name}（${elapsed(started)} 秒）`)
    throw new Error(
      `${describeError(error)}\n步骤：${name}，耗时 ${elapsed(started)} 秒，` +
        `当前 URL：${page.url()}，页面文本：${pageText}`,
    )
  } finally {
    clearTimeout(timer)
  }
}

async function runUatApiBootstrap(page, input, agent = null) {
  const config = input.uat_api_bootstrap
  if (!config?.enabled) return null
  const phone = String(input.variables?.phone_number || randomPhone())
  const uatBaseUrl = config.uat_base_url || 'https://expressfinance-uat.business.hsbc.com'
  const mockApiBaseUrl = resolveMockApiBaseUrl(config.mockapi_base_url)
  const tokenHolder = installAuthorizationTokenRecorder(page)
  await fs.writeFile(path.join(runDir, 'run-metadata.json'), JSON.stringify({ ...reportMetadata, phone }, null, 2), 'utf8')
  if (agent) await agent.recordToReport(
    `测试元数据：环境 ${reportMetadata.environment}；手机号 ${phone}；Merchant ${reportMetadata.merchant}；选中申请单 ${reportMetadata.application}`,
  )
  await page.goto(`${uatBaseUrl}/zh-Hans/`, { waitUntil: 'domcontentloaded', timeout: 60000 })
  await page.getByText('丰泊国际', { exact: true }).waitFor({ state: 'visible', timeout: 60000 })
  if (agent) await agent.recordToReport('UAT 首页已打开，准备选择 FP 产品')
  const fundparkCard = page.locator('div.default-product-selection').filter({ hasText: /丰泊国际/ }).filter({ hasText: /美元循环额度/ }).first()
  await fundparkCard.waitFor({ state: 'visible', timeout: 30000 })
  await fundparkCard.getByRole('button', { name: '立即开始' }).click()
  if (agent) await agent.recordToReport('已点击首页“丰泊国际”美元循环额度 FP 卡片')
  await page.getByRole('textbox', { name: '手机号码' }).fill(phone)
  await page.getByRole('button', { name: '发送验证码' }).click()
  await fillCode(page, String(config.verification_code || '666666'))
  await dumpPage(page, 'registration-verification-completed')
  if (agent) await agent.recordToReport(
    `截图：注册验证码填写完成、点击下一步前（registration-verification-completed.png）；手机号 ${phone}`,
  )
  const nextButton = page.getByRole('button', { name: '下一步' })
  await nextButton.waitFor({ state: 'visible', timeout: 30000 })
  // Verification is server-side, so 下一步 stays disabled while the OTP is being
  // checked and forever if it was rejected. Clicking a disabled button silently
  // does nothing and the failure only surfaces on the next locator.
  for (let attempt = 0; attempt < 10; attempt += 1) {
    if (await nextButton.isEnabled().catch(() => false)) break
    await sleep(1000)
  }
  await nextButton.click()
  // The password fields belong to the account-setup step, which only renders once
  // the OTP has been accepted. A bare fill() here reports a locator timeout and
  // hides the actual reason (rejected code, throttling, or a service message).
  const passwordInputs = page.locator('input[type="password"]')
  try {
    await passwordInputs.first().waitFor({ state: 'visible', timeout: 60000 })
  } catch {
    const details = await dumpFormErrors(page, 'signup-otp-blocked.json')
    await dumpPage(page, 'signup-otp-blocked-page')
    const pageText = (await page.locator('body').innerText().catch(() => '')).replace(/\s+/g, ' ').slice(0, 1500)
    throw new Error(
      `验证码提交后未进入设置密码步骤，说明手机验证未通过或注册流程被拦截。` +
        `当前页面：${page.url()}，字段报错：${JSON.stringify(details.errors)}，` +
        `弹窗：${JSON.stringify(details.dialogs)}，页面文本：${pageText}`,
    )
  }
  await passwordInputs.nth(0).fill(config.password || 'Aa11111111..')
  await passwordInputs.nth(1).fill(config.password || 'Aa11111111..')
  await page.locator('[role="combobox"]').first().click()
  await page.locator('[role="option"]').first().click()
  const enabledTextInputs = page.locator('input[type="text"]:not([disabled])')
  await enabledTextInputs.nth(1).fill(config.security_answer || 'Test123')
  await enabledTextInputs.nth(2).fill(`${phone}@163.com`)
  await dumpPage(page, 'security-question-completed')
  if (agent) await agent.recordToReport(
    `截图：安全问题填写完成（security-question-completed.png）；手机号 ${phone}`,
  )
  const authorizationLabels = page.locator('label').filter({ hasText: /同意|授权/ })
  for (let index = 0; index < await authorizationLabels.count(); index += 1) {
    await authorizationLabels.nth(index).click()
  }
  await dumpPage(page, 'registration-completed')
  if (agent) await agent.recordToReport(
    `截图：注册信息填写完成、提交前（registration-completed.png）；环境 ${reportMetadata.environment}；手机号 ${phone}`,
  )
  const observedUrls = []
  const recordUrl = (url) => {
    if (url && !observedUrls.includes(url)) observedUrls.push(url)
  }
  page.on('request', (request) => recordUrl(request.url()))
  await page.getByRole('button', { name: '注册' }).click()
  await sleep(1000)
  const applyButton = page.getByRole('button', { name: '立即申请' }).first()
  await applyButton.waitFor({ state: 'visible', timeout: 90000 })
  await applyButton.click()
  await sleep(1000)
  if (agent) await agent.recordToReport('FP 注册已提交，准备处理 SP 授权')

  const pages = page.context().pages()
  const amazonPage = pages.find((candidate) => candidate !== page && candidate.url().includes('sellercentral.amazon.com'))
  const candidateUrls = [
    amazonPage?.url(),
    page.url(),
    ...pages.map((candidate) => candidate.url()),
    ...observedUrls,
  ].filter(Boolean)
  let state = ''
  for (const candidateUrl of candidateUrls) {
    try {
      const candidateState = new URL(candidateUrl).searchParams.get('state')
      if (candidateState) {
        state = candidateState
        break
      }
    } catch {}
  }
  if (!state) throw new Error(`UAT SP 请求中未找到 state，当前 URL: ${amazonPage?.url() || '(无新标签页)'}`)

  const sessionResponse = await apiJson(mockApiBaseUrl, '/api/connect', {
    env: 'uat', phone_number: phone, username: input.username || 'admin',
  })
  const session = sessionResponse.data || {}
  const common = {
    session_id: session.session_id,
    username: input.username || 'admin',
    operation_name: 'AI UI UAT FP USD 500K hybrid bootstrap',
  }
  // The UAT signup token lives only in the browser, and /api/connect cannot
  // recover it (dpu_users.token is empty in this environment), so the lender-side
  // steps have no authorization until it is handed to the session explicitly.
  await attachSessionToken(mockApiBaseUrl, common, tokenHolder)
  const binding = await apiJson(mockApiBaseUrl, '/api/mock/multi-shop-binding', { ...common, state })
  if (amazonPage) await amazonPage.close()
  const authUrl = binding.data?.auth_url || binding.data?.url
  if (authUrl) {
    const authPage = await page.context().newPage()
    await authPage.goto(authUrl, { waitUntil: 'domcontentloaded', timeout: 60000 }).catch(() => {})
    // The auth callback persists the idempotency key that sp-status-update looks
    // up, and closing the tab too early aborts that request.
    await sleep(3000)
    await authPage.close().catch(() => {})
  }
  const sellerId = binding.data?.selling_partner_id
  // The key is written asynchronously by the callback, so a first miss is a race
  // rather than a real rejection.
  let spStatusError = null
  for (let attempt = 0; attempt < 5; attempt += 1) {
    try {
      await apiJson(mockApiBaseUrl, '/api/mock/sp-status-update', {
        ...common, platform_seller_id: sellerId, status: 'SUCCESS',
      })
      spStatusError = null
      break
    } catch (error) {
      spStatusError = error
      await sleep(3000)
    }
  }
  if (spStatusError) throw spStatusError
  const redirect = await apiJson(mockApiBaseUrl, '/api/mock/multi-shop-3pl-redirect', common)
  const redirectUrl = redirect.data?.redirect_url || redirect.data?.url
  if (!redirectUrl) throw new Error(`3PL redirect 响应缺少 URL: ${JSON.stringify(redirect)}`)
  // Keep the authenticated UAT application page alive. The legacy offline flow
  // opens the 3PL redirect in a second tab, while the original tab advances to
  // commercial information after the redirect callback updates backend state.
  const redirectPage = await page.context().newPage()
  await redirectPage.goto(redirectUrl, { waitUntil: 'domcontentloaded', timeout: 60000 }).catch(() => {})
  await sleep(1500)
  await redirectPage.close().catch(() => {})
  // The 3PL callback updates backend state asynchronously, so the first reload can
  // still land on the pre-authorization /offline-3pl guide page. Reload until the
  // route advances instead of silently skipping every DOM step below.
  await runStep(page, agent, {
    name: '等待 3PL 回跳后进入申请页',
    slug: '3pl-redirect-settle',
    timeout: 600000,
  }, async () => {
    for (let attempt = 0; attempt < 8; attempt += 1) {
      await page.reload({ waitUntil: 'domcontentloaded', timeout: 60000 }).catch(() => {})
      await sleep(3000)
      if (/\/offer|\/business-information|\/director/.test(page.url())) break
    }
    if (!/\/offer|\/business-information|\/director/.test(page.url())) {
      await dumpPage(page, 'stuck-page')
      throw new Error(`3PL 回跳后页面未进入 offer/商业信息，当前 URL：${page.url()}`)
    }
  })
  if (page.url().includes('/offer')) {
    await runStep(page, agent, {
      name: 'offer 页点击“立即申请”',
      slug: 'offer-apply',
      timeout: 240000,
    }, async () => {
      await dumpPage(page, 'offer-page')
      const applyButton = page.getByRole('button', { name: '立即申请' }).first()
      await applyButton.waitFor({ state: 'visible', timeout: 30000 })
      await applyButton.click()
      // Third-party analytics keep this page's `load` event pending well past the
      // route change, so only the URL commit is awaited here.
      await page.waitForURL(/\/business-information|\/director/, {
        timeout: 90000,
        waitUntil: 'commit',
      })
      await page.locator('input.el-input__inner:not(.el-select__input)').first().waitFor({
        state: 'visible',
        timeout: 30000,
      })
      await dumpPage(page, 'business-page')
    })
  }
  const suffix = String(Date.now()).slice(-8)
  if (page.url().includes('/business-information')) {
    await runStep(page, agent, {
      name: '填写企业信息并提交',
      slug: 'business-information',
      timeout: 240000,
    }, async () => {
      const companyEnglishName = `MOCK FP TEST ${suffix}`
      const companyChineseName = `测试企业${suffix}`
      const textInputs = page.locator('input.el-input__inner:not(.el-select__input)')
      await textInputs.nth(2).fill(suffix)
      await textInputs.nth(2).press('Tab')
      await waitForSelectOptions(page)
      const selects = page.locator('.el-select')
      for (let index = 0; index < 4; index += 1) {
        await selectFirstVisibleOption(page, selects.nth(index))
      }
      await page.locator('textarea.el-textarea__inner').fill('家居用品')
      const checkboxes = page.locator('input.el-checkbox__original')
      for (const index of [0, 6, 12]) await checkboxes.nth(index).check()
      await textInputs.nth(0).fill(companyEnglishName)
      await textInputs.nth(1).fill(companyChineseName)
      await textInputs.nth(2).fill(suffix)
      await textInputs.nth(2).press('Tab')
      const fieldValues = [
        await textInputs.nth(0).inputValue(),
        await textInputs.nth(1).inputValue(),
        await textInputs.nth(2).inputValue(),
      ]
      if (fieldValues[0] !== companyEnglishName || fieldValues[1] !== companyChineseName || fieldValues[2] !== suffix) {
        throw new Error(`企业注册信息填写后回读为空：${JSON.stringify(fieldValues)}`)
      }
      const selectedValues = await selects.evaluateAll((elements) => elements.slice(0, 4).map((element) => {
        const values = Array.from(element.querySelectorAll(
          '.el-select__selected-item, .el-tag__content, input.el-select__input',
        )).map((node) => {
          if (node instanceof HTMLInputElement) return node.value.trim()
          return node.textContent?.trim() || ''
        })
        return values.filter((value) => value && value !== '请选择')
      }))
      if (selectedValues.some((values) => values.length === 0)) {
        throw new Error(`企业业务下拉项选择后回读为空：${JSON.stringify(selectedValues)}`)
      }
      await dumpPage(page, 'business-page-filled')
      if (agent) await agent.recordToReport(
        '截图：企业信息填写完成、点击下一页前（business-page-filled.png）',
      )
      await page.getByRole('button', { name: '下一页' }).click()
      await page.waitForURL(/\/director|\/shareholder/, { timeout: 60000 }).catch(() => {})
      if (!/\/director|\/shareholder/.test(page.url())) {
        const validationText = await page.locator('body').innerText()
        throw new Error(`企业信息页点击“下一页”后未进入董事/股东页面，页面校验信息：${validationText.slice(0, 1200)}`)
      }
      await dumpPage(page, 'director-page')
    })
  }
  if (/\/director|\/shareholder/.test(page.url())) {
    const frontDocument = path.join(fileChooserAllowedDir, '身份证正面.png')
    const backDocument = path.join(fileChooserAllowedDir, '身份证反面.png')
    const personCards = page.locator('.el-collapse-item')
    const firstPersonCard = personCards.nth(0)
    const secondPersonCard = personCards.nth(1)
    await runStep(page, agent, {
      name: '等待董事/股东卡片渲染',
      slug: 'director-cards',
      timeout: 150000,
    }, async () => {
      await page.getByText('董事/股东信息', { exact: true }).waitFor({ state: 'visible', timeout: 30000 })
      await page.getByText(/^1\.董事股东\s*-/).waitFor({ state: 'visible', timeout: 30000 })
      await page.waitForFunction(
        () => document.querySelectorAll('.el-collapse-item').length >= 2,
        { timeout: 30000 },
      )
      if (await personCards.count() < 2) {
        throw new Error(`董事/股东卡片渲染后数量不足，实际数量：${await personCards.count()}，页面URL：${page.url()}`)
      }
      await installNoticeCollector(page)
      installUploadResponseRecorder(page)
    })
    // Each person is a separate step because the two cards fail for different
    // reasons: the first can stall on the identity-type watcher clearing a fresh
    // upload, the second on its collapse panel never expanding.
    for (const [card, label, slug, birthDate, emailPrefix] of [
      [firstPersonCard, '第一名董事/股东', 'director-1', '1990/01/01', 'director1'],
      [secondPersonCard, '第二名董事/股东', 'director-2', '1992/02/02', 'director2'],
    ]) {
      await runStep(page, agent, {
        name: `填写${label}`,
        slug,
        timeout: 300000,
      }, async () => {
        if (card === secondPersonCard) {
          await card.locator('.el-collapse-item__header').click()
          await card.getByText('身份证明文件正面', { exact: true }).waitFor({
            state: 'visible',
            timeout: 30000,
          })
        }
        await waitForIdentityTypeSettled(page, card)
        await uploadFileByLabel(page, card, '身份证明文件正面', frontDocument)
        await uploadFileByLabel(page, card, '身份证明文件反面', backDocument)
        await fillFollowingInput(page, card, '出生日期（年/月/日）', birthDate)
        await fillFollowingInput(page, card, '手机号码', randomPhone())
        await fillFollowingInput(page, card, '邮箱地址', `${emailPrefix}_${suffix}@example.com`)
        await waitForPersonCardCompleted(page, card, label)
      })
    }
    await runStep(page, agent, {
      name: '提交董事/股东信息',
      slug: 'director-submit',
      timeout: 180000,
    }, async () => {
      await dumpPage(page, 'director-page-uploaded')
      // The birth-date picker panel stays open after filling, and it overlays the
      // form footer.
      await page.keyboard.press('Escape')
      await page.getByRole('button', { name: '下一页' }).click()
      // Submitting persists both directors server-side before routing, so the page
      // stays put for several seconds. Wait for the route to change instead of
      // sampling the URL once.
      await page.waitForURL((url) => !url.pathname.includes('/director-shareholder-information'), {
        timeout: 90000,
      }).catch(() => {})
      if (page.url().includes('/director-shareholder-information')) {
        const details = await dumpFormErrors(page, 'director-page-errors.json')
        await dumpPage(page, 'director-page-submitted')
        throw new Error(`董事/股东信息点击“下一页”后未继续，字段级校验信息：${JSON.stringify(details.errors)}，弹窗与提示：${JSON.stringify(details.dialogs)} ${JSON.stringify(await readNotices(page))}`)
      }
      await dumpPage(page, 'offer-selection-page')
    })
  }
  if (page.url().includes('/offer-selection')) {
    await runStep(page, agent, {
      name: 'offer-selection 页点击“去解锁”',
      slug: 'offer-unlock',
      timeout: 180000,
    }, async () => {
      // The 500K journey is the "unlock a higher limit" branch: 去激活 only activates
      // the small pre-approved limit, which never reaches 500K underwriting.
      const unlockButton = page.getByRole('button', { name: '去解锁' }).first()
      await unlockButton.waitFor({ state: 'visible', timeout: 30000 })
      await unlockButton.click()
      await page.waitForURL((url) => !url.pathname.includes('/offer-selection'), {
        timeout: 90000,
        waitUntil: 'commit',
      }).catch(() => {})
      await sleep(3000)
      await dumpPage(page, 'after-unlock-page')
    })
  }
  // Underwriting through drawdown are lender-side callbacks with no UI of their
  // own, so they are driven through MockAPI on the session created above rather
  // than by asking the AI to find controls that do not exist on the page.
  const application = page.url().includes('/offer-loading') || page.url().includes('/offer-')
    ? await runUatMockProgression(page, mockApiBaseUrl, common, input, agent)
    : null
  if (application) {
    await page.reload({ waitUntil: 'domcontentloaded', timeout: 60000 }).catch(() => {})
    await sleep(3000)
    await fs.writeFile(path.join(runDir, 'final-page.txt'), await page.locator('body').innerText(), 'utf8')
  }
  return {
    phone,
    state,
    session_id: session.session_id,
    selling_partner_id: sellerId,
    redirect_url: redirectUrl,
    business_info_completed: page.url().includes('/director'),
    director_info_completed: !page.url().includes('/director-shareholder-information'),
    mock_progression_completed: Boolean(application),
  }
}

// fp-scheduled-submit is dispatched as a background job, so the POST only hands
// back a job id and the outcome has to be polled.
async function runFpScheduledSubmit(mockApiBaseUrl, common, journey, agent = null, timeout = 900000) {
  const accepted = await apiJson(mockApiBaseUrl, '/api/mock/fp-scheduled-submit', { ...common, journey })
  const jobId = accepted.data?.job_id
  if (!jobId) throw new Error(`fp-scheduled-submit 未返回 job_id: ${JSON.stringify(accepted)}`)
  const deadline = Date.now() + timeout
  while (Date.now() < deadline) {
    await sleep(5000)
    const response = await fetch(
      `${mockApiBaseUrl}/api/mock/fp-scheduled-submit/jobs/${jobId}?username=${encodeURIComponent(common.username)}`,
    )
    const body = await response.json().catch(() => ({}))
    const job = body.data || {}
    if (['PENDING', 'RUNNING'].includes(job.job_status)) continue
    if (job.job_status !== 'SUCCESS' || !job.success) {
      throw new Error(`fp-scheduled-submit 失败：${JSON.stringify(job)}`)
    }
    await fs.writeFile(
      path.join(runDir, 'mock-scheduled-submit.json'),
      JSON.stringify(job, null, 2),
      'utf8',
    ).catch(() => {})
    if (agent) await agent.recordToReport(`MockAPI 步骤完成：fp-scheduled-submit（${job.application_status}）`)
    return job
  }
  throw new Error('fp-scheduled-submit 轮询超时')
}

// Snapshots are diagnostics only. A page caught mid-navigation makes page.content()
// itself throw, so every read has to be guarded rather than only the write.
const dumpPage = async (page, name) => {
  for (const [suffix, read] of [
    ['html', () => page.content()],
    ['txt', () => page.locator('body').innerText()],
  ]) {
    try {
      await fs.writeFile(path.join(runDir, `${name}.${suffix}`), await read(), 'utf8')
    } catch {}
  }
  try {
    await page.screenshot({
      path: path.join(runDir, `${name}.png`),
      fullPage: true,
      animations: 'disabled',
    })
  } catch {}
}

// The tab can be sitting on the provider's error page, where reload() would just
// re-fetch that error. Navigating to the recorded portal URL is the only way back.
async function gotoPortal(page, portalUrl, settle = 5000) {
  await page.goto(portalUrl, { waitUntil: 'domcontentloaded', timeout: 60000 }).catch(() => {})
  await sleep(settle)
}

// Accepting the PSP binding opens the provider's authorization site in a new window
// AND navigates this tab to the same URL. The provider's page cannot be completed in
// a test run, and its authorization message is single-use, so the tab that follows it
// lands on "Decryption Error" and never returns on its own. The binding result comes
// from the mocked psp events instead, and the portal re-reads it on load -- so every
// step after the accept has to navigate back to the recorded portal URL explicitly
// rather than reload whatever the tab currently shows.
async function acceptUatOfferAndBindPsp(page, portalUrl, runSteps, agent = null) {
  const activateButton = page.getByRole('button', { name: '激活额度' }).first()
  if (await activateButton.isVisible().catch(() => false)) {
    await activateButton.click()
    await sleep(3000)
    await dumpPage(page, 'after-activate-page')
    if (agent) await agent.recordToReport(`已通过 DOM 点击“激活额度”，当前页面：${page.url()}`)
  }
  const acceptButton = page.getByRole('button', { name: '接受' }).last()
  await acceptButton.waitFor({ state: 'visible', timeout: 30000 })
  const popupPromise = page.waitForEvent('popup', { timeout: 20000 }).catch(() => null)
  await acceptButton.click()
  const popup = await popupPromise
  if (popup) {
    if (agent) await agent.recordToReport(`支付服务商授权窗口已打开：${popup.url()}`)
    await popup.close().catch(() => {})
  }
  await dumpPage(page, 'after-psp-accept-page')
  // Accepting is what registers the pending binding server-side, so the events are
  // only meaningful after the click.
  await runSteps([
    ['psp-start PROCESSING', '/api/mock/psp-start', { status: 'PROCESSING' }],
    ['psp-completed SUCCESS', '/api/mock/psp-completed', { status: 'SUCCESS' }],
  ])
  await gotoPortal(page, portalUrl)
  await dumpPage(page, 'after-psp-completed-page')
  if (agent) await agent.recordToReport(`PSP 绑定完成后页面：${page.url()}`)
}

// The activation route never turns into the borrowing screen: 立即提现 lives on the
// product's own main page, a sibling of the /apply/<id>/... branch.
const mainUrlFromPortal = (portalUrl) => {
  const url = new URL(portalUrl)
  url.pathname = `${url.pathname.split('/apply/')[0]}/main`
  url.search = ''
  url.hash = ''
  return url.toString()
}

// /api/mock/drawdown only replays the lender's disbursement.completed callback,
// so the borrower's own 支用 request has to happen in the UI first to create the
// dpu_drawdown row that callback updates.
async function requestUatDrawdown(page, portalUrl, amount, agent = null) {
  const mainUrl = mainUrlFromPortal(portalUrl)
  // Match only real controls: the offer copy itself contains 提现 ("您可提现的额度…"),
  // so a text-node match silently clicks a paragraph and looks like a no-op. The
  // button reads 立刻提现, not 立即提现.
  const entrySelector = /^(立刻|立即|马上)?(支用|提款|借款|提现|申请支用|申请提现)$/
  // The button renders immediately but arrives disabled until the lender side has
  // turned the signed limit into a drawable one, so visibility alone is not
  // readiness: latching onto the disabled button leaves Playwright's own 30s
  // actionability wait as the only tolerance and the run dies at exactly 30s.
  let entry = null
  let lastState = ''
  for (let attempt = 0; attempt < 8 && !entry; attempt += 1) {
    if (attempt > 0) await sleep(12000)
    await gotoPortal(page, mainUrl)
    for (const candidate of [
      page.getByRole('button', { name: entrySelector }).first(),
      page.getByRole('link', { name: entrySelector }).first(),
    ]) {
      if (!(await candidate.isVisible().catch(() => false))) continue
      if (await candidate.isEnabled().catch(() => false)) {
        entry = candidate
        break
      }
      lastState = `可见但禁用（aria-disabled=${await candidate.getAttribute('aria-disabled').catch(() => '?')}）`
    }
  }
  if (!entry) {
    const pageText = (await page.locator('body').innerText().catch(() => '')).replace(/\s+/g, ' ').slice(0, 1500)
    await dumpPage(page, 'drawdown-entry-missing')
    throw new Error(
      `e签完成后支用入口不可用（${lastState || '未找到支用入口'}），` +
        `说明贷款人侧尚未把已签额度置为可支用，或已存在在途支用申请。` +
        `当前页面：${page.url()}，页面文本：${pageText}`,
    )
  }
  await dumpPage(page, 'drawdown-main-page')
  await entry.click()
  await sleep(4000)
  await dumpPage(page, 'drawdown-page')
  // The form is 提现金额 / 指定银行 / SWIFT代码 / 账户号码 / 账户持有人名称, and the
  // last one arrives disabled and pre-filled. Submitting with only the amount trips
  // field validation on the three bank fields.
  const editableInputs = page.locator(
    'form input.el-input__inner:not([readonly]):not([disabled])',
  )
  const amountInput = editableInputs.nth(0)
  await amountInput.waitFor({ state: 'visible', timeout: 30000 })
  await amountInput.fill(String(amount))
  await amountInput.press('Tab')

  // The inner combobox input sits under .el-select__selection, which swallows the
  // pointer event; the wrapper is the control's real hit area.
  const bankSelect = page.locator('form .el-select__wrapper').first()
  await bankSelect.waitFor({ state: 'visible', timeout: 30000 })
  await bankSelect.click()
  const bankOption = page.locator('.el-select-dropdown__item:visible').first()
  await bankOption.waitFor({ state: 'visible', timeout: 30000 })
  const bankName = (await bankOption.innerText().catch(() => '')).trim()
  await bankOption.click()
  await sleep(1500)

  // Same test bank identity MockAPI posts through /dpu-merchant/bank-info.
  await editableInputs.nth(1).fill('IBALHKHH')
  await editableInputs.nth(2).fill(`128${String(Date.now()).slice(-10)}`)
  await editableInputs.nth(2).press('Tab')
  await sleep(1500)
  await dumpPage(page, 'drawdown-form-filled')
  if (agent) await agent.recordToReport(`已填写支用表单：金额 ${amount}，银行 ${bankName}`)

  const submitButton = page.getByRole('button', { name: /^(确认|提交|下一步|申请支用)$/ }).first()
  await submitButton.waitFor({ state: 'visible', timeout: 30000 })
  await submitButton.click()
  await sleep(6000)
  await dumpPage(page, 'drawdown-submitted')
  const submittedText = await page.locator('body').innerText().catch(() => '')
  if (submittedText.includes('以下项目有误')) {
    const errors = await page.locator('.el-form-item__error').allInnerTexts().catch(() => [])
    throw new Error(`支用表单提交被字段校验拦下：${JSON.stringify(errors)}`)
  }
  if (agent) await agent.recordToReport(`已通过 DOM 提交支用申请：${amount}`)
}

// The lender-side steps of the 500K journey, in the order the backend accepts
// them. Each one is a webhook MockAPI replays, so a failure here is a real
// backend rejection and must stop the run.
async function runUatMockProgression(page, mockApiBaseUrl, common, input, agent = null) {
  const esignAmount = Number(input.variables?.esign_amount || 500000)
  const drawdownAmount = Number(input.variables?.drawdown_amount || 200000)
  const journey = String(input.variables?.journey || '500K')
  // Clicking 去解锁 only queues the limit application; the lender's scheduled task
  // is what moves it to SUBMITTED, and underwriting needs that row to exist.
  await runFpScheduledSubmit(mockApiBaseUrl, common, journey, agent)
  const results = []
  const runSteps = async (steps) => {
    for (const [label, pathname, payload] of steps) {
      const response = await apiJson(mockApiBaseUrl, pathname, { ...common, ...payload })
      results.push({ label, data: response.data || {} })
      await fs.writeFile(
        path.join(runDir, 'mock-progression.json'),
        JSON.stringify(results, null, 2),
        'utf8',
      ).catch(() => {})
      if (agent) await agent.recordToReport(`MockAPI 步骤完成：${label}`)
      await sleep(2000)
    }
  }
  await runSteps([
    ['underwriting APPROVED', '/api/mock/underwritten', { amount: esignAmount, status: 'APPROVED', use_latest_submitted_limit_application: true }],
    ['approved-offer APPROVED', '/api/mock/approved-offer', { amount: esignAmount, status: 'APPROVED' }],
    // Without activate-offer the approved limit is never turned into a live quote,
    // so the backend has nothing to draw down against later.
    ['activate-offer', '/api/mock/fp-activate-offer', { currency: 'USD', funder_resource: 'FUNDPARK' }],
  ])
  // Accepting the PSP binding sends this tab to the provider's single-use
  // authorization URL, which it can never come back from, so the portal address is
  // recorded here and every later step navigates to it instead of reloading.
  const portalUrl = page.url()
  await gotoPortal(page, portalUrl)
  await dumpPage(page, 'post-activate-offer-page')
  await acceptUatOfferAndBindPsp(page, portalUrl, runSteps, agent)
  await runSteps([
    ['esign SUCCESS', '/api/mock/esign', { signed_amount: esignAmount, status: 'SUCCESS' }],
  ])
  await gotoPortal(page, portalUrl)
  await dumpPage(page, 'post-esign-page')
  // /api/mock/drawdown only replays the lender's disbursement.completed callback, so
  // it needs the dpu_drawdown row that the borrower's own 支用 request creates in the
  // task centre the esign SUCCESS lands on.
  await requestUatDrawdown(page, portalUrl, drawdownAmount, agent)
  await runSteps([
    ['drawdown APPROVED', '/api/mock/drawdown', { amount: drawdownAmount, status: 'APPROVED' }],
  ])
  return results
}

async function findNewestReport() {
  let newest = null
  const walk = async (dir) => {
    let entries
    try {
      entries = await fs.readdir(dir, { withFileTypes: true })
    } catch {
      return
    }
    for (const entry of entries) {
      const full = path.join(dir, entry.name)
      if (entry.isDirectory()) {
        await walk(full)
      } else if (entry.name.endsWith('.html')) {
        const stat = await fs.stat(full)
        if (!newest || stat.mtimeMs > newest.mtimeMs) {
          newest = { path: full, mtimeMs: stat.mtimeMs }
        }
      }
    }
  }
  await walk(path.join(runDir, 'report'))
  return newest ? newest.path : null
}

const describeError = (error) => String(error?.stack || error?.message || error)

const outcome = {
  status: 'failed',
  error: '',
  finalize_error: '',
  url: input.url,
  title: '',
  requested_headed: requestedHeaded,
  headed: !headless,
  report_path: null,
}

const browser = await chromium.launch({
  headless,
  args: [
    '--no-sandbox',
    '--disable-setuid-sandbox',
    '--incognito',
    '--disable-extensions',
    '--disable-sync',
  ],
})

try {
  await fs.mkdir(videoDir, { recursive: true })
  // Every run receives a brand-new incognito browser context. Do not use a
  // persistent profile or inherited storage, because UAT SP/3P redirect URLs
  // are account-bound and must stay with the account created in this run.
  const context = await browser.newContext({
    viewport,
    storageState: undefined,
    recordVideo: {
      dir: videoDir,
      size: viewport,
    },
  })
  const page = await context.newPage()
  const agent = new PlaywrightAgent(page, {
    waitForNetworkIdleTimeout: Number(input.network_idle_timeout || 3000),
    waitForNavigationTimeout: Number(input.navigation_timeout || 30000),
  })
  const bootstrap = await runUatApiBootstrap(page, input, agent)
  if (!bootstrap) await page.goto(input.url, { waitUntil: 'domcontentloaded', timeout: Number(input.navigation_timeout || 30000) })
  if (bootstrap) input.variables = { ...(input.variables || {}), ...bootstrap }
  if (bootstrap && page.url().includes('/offer')) {
    const offerStep = '  And I complete the FP application progression until underwriting is ready'
    const offerIndex = scenarioPrompt.indexOf(offerStep)
    if (offerIndex >= 0) {
      scenarioPrompt = `Scenario: UAT FP USD 500K continuation after applying for the pre-approved offer\n${scenarioPrompt.slice(offerIndex).replace(/^  And /, '  When ')}`
    }
  }
  if (bootstrap && (bootstrap.business_info_completed || page.url().includes('/director'))) {
    const directorStep = "  And I fill the first person's birth date, identity number, mobile phone number, email address and residential address"
    const directorIndex = scenarioPrompt.indexOf(directorStep)
    if (directorIndex >= 0) {
      scenarioPrompt = `Scenario: UAT FP USD 500K director and shareholder continuation\n${scenarioPrompt.slice(directorIndex).replace(/^  And /, '  When ')}`
    }
  }
  if (bootstrap && bootstrap.director_info_completed) {
    const contactStep = '  And I select the first available contact and submit the application'
    const contactIndex = scenarioPrompt.indexOf(contactStep)
    if (contactIndex >= 0) {
      scenarioPrompt = `Scenario: UAT FP USD 500K continuation after director information\n${scenarioPrompt.slice(contactIndex).replace(/^  And /, '  When ')}`
    }
  }

  // The bootstrap already drove every step of this journey through the DOM and
  // MockAPI, so replaying the Gherkin scenario would only ask the AI to look for
  // controls the lender-side callbacks never render.
  if (bootstrap?.mock_progression_completed) {
    outcome.status = 'passed'
    outcome.driven_by = 'dom+mockapi'
  } else {
    try {
      await agent.runGherkinScenario(scenarioPrompt, {
        context: scenarioContext || undefined,
        fileChooserAllowedDir,
        replanningCycleLimit: Number(input.replanning_cycle_limit || process.env.MIDSCENE_REPLANNING_CYCLE_LIMIT || 40),
      })
      outcome.status = 'passed'
    } catch (error) {
      outcome.error = describeError(error)
    }
  }

  // The report is the main debugging artifact, so flush it for failed runs too.
  // A finalize failure is kept apart from `error` so it cannot be mistaken for a
  // scenario failure when the steps themselves passed.
  for (const finalize of [() => agent.recordToReport('Final state'), () => agent.destroy()]) {
    try {
      await finalize()
    } catch (error) {
      if (!outcome.finalize_error) outcome.finalize_error = describeError(error)
    }
  }

  outcome.url = page.url()
  outcome.title = await page.title().catch(() => '')
} catch (error) {
  outcome.error = describeError(error)
} finally {
  await writeEvidenceIndex().catch(() => {})
  outcome.report_path = await findNewestReport()
  outcome.video_dir = videoDir
  await browser.close()
}

console.log(JSON.stringify(outcome))
process.exit(outcome.status === 'passed' ? 0 : 1)

import axios from 'axios'

const client = axios.create({
  timeout: 30000,
})

const isLocalHost = typeof window !== 'undefined'
  && (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')

const aiClient = axios.create({
  baseURL: '',
  timeout: 150000,
})

const aiFallbackClient = axios.create({
  baseURL: isLocalHost ? 'http://127.0.0.1:8017' : '',
  timeout: 150000,
})

function attachErrorPayload(error) {
  const payload = error?.response?.data
  if (payload) {
    error.payload = payload?.data ?? payload
  }
  return Promise.reject(error)
}

client.interceptors.response.use((response) => response, attachErrorPayload)
aiClient.interceptors.response.use((response) => response, attachErrorPayload)
aiFallbackClient.interceptors.response.use((response) => response, attachErrorPayload)

function unwrap(response) {
  const payload = response.data
  if (payload?.success === false) {
    const error = new Error(payload.message || payload.error_message || 'Request failed')
    error.payload = payload
    error.response = response
    throw error
  }
  return payload?.data ?? payload
}

export async function fetchHealth() {
  const response = await client.get('/api/health')
  return response.data
}

export async function fetchEnums() {
  const response = await client.get('/api/enums')
  return unwrap(response)
}

export async function fetchSessions(sessionId) {
  const response = await client.get('/api/sessions', {
    params: sessionId ? { session_id: sessionId } : undefined,
  })
  return unwrap(response)
}

export async function fetchLogs(params = {}) {
  const response = await client.get('/api/logs', { params })
  return unwrap(response)
}

export async function fetchEnvironmentMonitor(params = {}) {
  const response = await client.get('/api/environment-monitor', { params })
  return unwrap(response)
}

export async function fetchUserOperations(params = {}) {
  const response = await client.get('/api/audit/operations', { params })
  return unwrap(response)
}

export async function loginUser(payload) {
  const response = await client.post('/api/auth/login', payload)
  return unwrap(response)
}

export async function registerUser(payload) {
  const response = await client.post('/api/auth/register', payload)
  return unwrap(response)
}

export async function fetchContactIssues() {
  const response = await client.get('/api/contact-issues')
  return unwrap(response)
}

export async function createContactIssue(payload) {
  const response = await client.post('/api/contact-issues', payload)
  return unwrap(response)
}

export async function replyContactIssueApi(issueId, payload) {
  const response = await client.post(`/api/contact-issues/${issueId}/reply`, payload)
  return unwrap(response)
}

export async function deleteContactIssueApi(issueId) {
  const response = await client.delete(`/api/contact-issues/${issueId}`)
  return unwrap(response)
}

export async function connectSession(payload) {
  const response = await client.post('/api/connect', payload)
  return unwrap(response)
}

export async function disconnectSession(sessionId) {
  const response = await client.post('/api/disconnect', null, {
    params: { session_id: sessionId },
  })
  return unwrap(response)
}

export async function registerAccount(payload) {
  const response = await client.post('/api/register', payload)
  return unwrap(response)
}

export async function registerAndRunMultiShop(payload) {
  const response = await client.post('/api/register-and-run-multishop', payload, {
    timeout: 180000,
  })
  return unwrap(response)
}

export async function fetchDowsureMerchantAccounts(sessionId) {
  const response = await client.get('/api/mock/dowsure-merchant-accounts', {
    params: { session_id: sessionId },
  })
  return unwrap(response)
}

export async function fetchApplicationCodes(sessionId) {
  const response = await client.get('/api/mock/application-codes', {
    params: { session_id: sessionId },
  })
  return unwrap(response)
}

export async function fetchWebankSellerOffers(sessionId) {
  const response = await client.get('/api/mock/webank-seller-offers', {
    params: { session_id: sessionId },
  })
  return unwrap(response)
}

export async function fetchPspAuthorizationRows(sessionId) {
  const response = await client.get('/api/mock/psp-authorization-rows', {
    params: { session_id: sessionId },
  })
  return unwrap(response)
}

export async function fetchLimitApplications(sessionId) {
  const response = await client.get('/api/mock/limit-applications', {
    params: { session_id: sessionId },
  })
  return unwrap(response)
}

export async function fetchDrawdownRepaymentRows(sessionId) {
  const response = await client.get('/api/mock/drawdown-repayment-rows', {
    params: { session_id: sessionId },
  })
  return unwrap(response)
}

export async function runMockOperation(endpoint, payload, options = {}) {
  const config = {}
  if (options.timeout) config.timeout = options.timeout
  const response = await client.post(endpoint, payload, config)
  return unwrap(response)
}

export async function runScenarioApi(endpoint, payload, options = {}) {
  const config = {
    timeout: options.timeout,
  }
  if (options.headers && typeof options.headers === 'object') {
    config.headers = options.headers
  }
  const response = await client.post(endpoint, payload, {
    ...config,
  })
  return unwrap(response)
}

export async function fetchScheduledSubmitJob(jobId, username) {
  const response = await client.get(`/api/mock/fp-scheduled-submit/jobs/${jobId}`, {
    params: username ? { username } : undefined,
  })
  return unwrap(response)
}

export async function sendAiChat(payload) {
  try {
    const response = await aiClient.post('/api/ai/chat', payload)
    return unwrap(response)
  } catch (error) {
    const detail = error?.response?.data?.data?.reply || error?.response?.data?.detail || error?.message || ''
    const shouldFallback =
      String(detail).includes('QWEN_API_KEY is not configured') ||
      String(detail).includes('Network Error') ||
      String(detail).includes('ERR_ABORTED')

    if (!shouldFallback) {
      throw error
    }

    if (!isLocalHost) {
      throw error
    }

    const fallbackResponse = await aiFallbackClient.post('/api/ai/chat', payload)
    return unwrap(fallbackResponse)
  }
}

export async function fetchPromptTemplates(username) {
  const response = await client.get('/api/prompt-templates', { params: { username } })
  return unwrap(response)
}

export async function createPromptTemplate(payload) {
  const response = await client.post('/api/prompt-templates', payload)
  return unwrap(response)
}

export async function updatePromptTemplate(templateId, payload) {
  const response = await client.put(`/api/prompt-templates/${templateId}`, payload)
  return unwrap(response)
}

export async function deletePromptTemplate(templateId, payload) {
  const response = await client.delete(`/api/prompt-templates/${templateId}`, { data: payload })
  return unwrap(response)
}

export async function togglePromptTemplate(templateId, payload) {
  const response = await client.post(`/api/prompt-templates/${templateId}/toggle`, payload)
  return unwrap(response)
}

export async function executePromptTemplate(templateId, payload) {
  const response = await aiClient.post(`/api/prompt-templates/${templateId}/execute`, payload)
  return unwrap(response)
}

export async function fetchScenarioStepOverrides(username) {
  const response = await client.get('/api/scenario-overrides', { params: { username } })
  return unwrap(response)
}

export async function fetchAiUiRuntimeStatus(username) {
  const response = await client.get('/api/ai-ui/status', { params: { username } })
  return unwrap(response)
}

export async function fetchAiUiCases(username) {
  const response = await client.get('/api/ai-ui/cases', { params: { username } })
  return unwrap(response)
}

export async function generateAiUiCase(payload) {
  const response = await client.post('/api/ai-ui/generate', payload)
  return unwrap(response)
}

export async function saveAiUiCase(payload, caseId = null) {
  const response = caseId
    ? await client.put(`/api/ai-ui/cases/${encodeURIComponent(caseId)}`, payload)
    : await client.post('/api/ai-ui/cases', payload)
  return unwrap(response)
}

export async function deleteAiUiCase(caseId, username) {
  const response = await client.delete(`/api/ai-ui/cases/${encodeURIComponent(caseId)}`, {
    params: { username },
  })
  return unwrap(response)
}

export async function fetchAiUiRuns(username) {
  const response = await client.get('/api/ai-ui/runs', { params: { username } })
  return unwrap(response)
}

export async function startAiUiRun(payload) {
  const response = await client.post('/api/ai-ui/runs', payload)
  return unwrap(response)
}

export async function fetchAiUiRun(runId, username) {
  const response = await client.get(`/api/ai-ui/runs/${encodeURIComponent(runId)}`, {
    params: { username },
  })
  return unwrap(response)
}

export async function stopAiUiRun(runId, username) {
  const response = await client.post(`/api/ai-ui/runs/${encodeURIComponent(runId)}/stop`, null, {
    params: { username },
  })
  return unwrap(response)
}

export async function fetchShopPerformanceBuiltinPresets(username) {
  const response = await client.get('/api/mock/shop-performance-cny-boost/presets', {
    params: { username },
  })
  return unwrap(response)
}

export async function fetchCompanyImageTemplates(username) {
  const response = await client.get('/api/company-image-templates', {
    params: { username },
  })
  return unwrap(response)
}

export async function saveCompanyImageTemplate(payload, templateId = null) {
  const formData = new FormData()
  formData.append('username', payload.username)
  formData.append('name', payload.name)
  formData.append('image_type', payload.image_type)
  if (payload.file) formData.append('file', payload.file)
  const response = templateId
    ? await client.put(`/api/company-image-templates/${templateId}`, formData)
    : await client.post('/api/company-image-templates', formData)
  return unwrap(response)
}

export async function deleteCompanyImageTemplate(templateId, username) {
  const response = await client.delete(`/api/company-image-templates/${templateId}`, {
    params: { username },
  })
  return unwrap(response)
}

export async function saveScenarioStepOverride(payload) {
  const response = await client.post('/api/scenario-overrides', payload)
  return unwrap(response)
}

export async function deleteScenarioStepOverride(payload) {
  const response = await client.delete('/api/scenario-overrides', { data: payload })
  return unwrap(response)
}

export async function fetchScenarioMetaOverrides(username) {
  const response = await client.get('/api/scenario-overrides/meta', { params: username ? { username } : {} })
  return unwrap(response)
}

export async function saveScenarioMetaOverride(payload) {
  const response = await client.post('/api/scenario-overrides/meta', payload)
  return unwrap(response)
}

export async function fetchScenarioStepMetaOverrides(username) {
  const response = await client.get('/api/scenario-overrides/step-meta', { params: username ? { username } : {} })
  return unwrap(response)
}

export async function saveScenarioStepMetaOverride(payload) {
  const response = await client.post('/api/scenario-overrides/step-meta', payload)
  return unwrap(response)
}

export async function deleteScenarioStepMetaOverride(payload) {
  const response = await client.delete('/api/scenario-overrides/step-meta', { data: payload })
  return unwrap(response)
}

export async function fetchScenarioStepOrders(username) {
  const response = await client.get('/api/scenario-overrides/order', { params: username ? { username } : {} })
  return unwrap(response)
}

export async function fetchScenarioStepSource(endpoint) {
  const response = await client.get('/api/scenario-overrides/step-source', { params: { endpoint } })
  return unwrap(response)
}

export async function saveScenarioStepOrder(payload) {
  const response = await client.post('/api/scenario-overrides/order', payload)
  return unwrap(response)
}

// ---------------------------------------------------------------------------
// Admin: user management
// ---------------------------------------------------------------------------

export async function fetchAdminUsers(adminUsername) {
  const response = await client.get('/api/admin/users', { params: { username: adminUsername } })
  return unwrap(response)
}

export async function updateAdminUser(targetUsername, payload) {
  const response = await client.put(`/api/admin/users/${encodeURIComponent(targetUsername)}`, payload)
  return unwrap(response)
}

export async function deleteAdminUser(targetUsername, adminUsername) {
  const response = await client.delete(`/api/admin/users/${encodeURIComponent(targetUsername)}`, {
    data: { admin_username: adminUsername },
  })
  return unwrap(response)
}

export async function approveAdminUser(targetUsername, adminUsername, note = '') {
  const response = await client.post(`/api/admin/users/${encodeURIComponent(targetUsername)}/approve`, {
    admin_username: adminUsername,
    note,
  })
  return unwrap(response)
}

export async function rejectAdminUser(targetUsername, adminUsername, note = '') {
  const response = await client.post(`/api/admin/users/${encodeURIComponent(targetUsername)}/reject`, {
    admin_username: adminUsername,
    note,
  })
  return unwrap(response)
}

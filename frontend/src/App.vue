<script setup>
import { marked } from 'marked'
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import {
  ArrowDown,
  ArrowRight,
  Bell,
  CaretRight,
  Check,
  CircleCheck,
  CircleClose,
  Clock,
  Connection,
  Cpu,
  Delete,
  Document,
  DocumentCopy,
  Edit,
  Expand,
  Fold,
  Key,
  Link,
  Lock,
  Monitor,
  Moon,
  Plus,
  Promotion,
  Refresh,
  Right,
  Sunny,
  ChatDotRound,
  ChatLineRound,
  Loading,
  Position,
  Top,
  Search,
  Setting,
  SwitchButton,
  Tickets,
  User,
} from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox, ElNotification } from 'element-plus'
import {
  connectSession,
  createContactIssue,
  deleteContactIssueApi,
  disconnectSession,
  fetchEnums,
  fetchDrawdownRepaymentRows,
  fetchEnvironmentMonitor,
  fetchHealth,
  fetchContactIssues,
  fetchApplicationCodes,
  fetchDowsureMerchantAccounts,
  fetchWebankSellerOffers,
  fetchLimitApplications,
  fetchLogs,
  fetchPspAuthorizationRows,
  fetchScheduledSubmitJob,
  fetchSessions,
  fetchUserOperations,
  loginUser,
  registerAccount,
  registerAndRunMultiShop,
  registerUser,
  replyContactIssueApi,
  runScenarioApi,
  runMockOperation,
  sendAiChat,
  fetchPromptTemplates,
  fetchScenarioStepOverrides,
  fetchShopPerformanceBuiltinPresets,
  fetchCompanyImageTemplates,
  saveCompanyImageTemplate,
  deleteCompanyImageTemplate,
  saveScenarioStepOverride,
  deleteScenarioStepOverride,
  fetchScenarioMetaOverrides,
  saveScenarioMetaOverride,
  fetchScenarioStepMetaOverrides,
  saveScenarioStepMetaOverride,
  deleteScenarioStepMetaOverride,
  fetchScenarioStepOrders,
  fetchScenarioStepSource,
  saveScenarioStepOrder,
  createPromptTemplate,
  updatePromptTemplate,
  deletePromptTemplate,
  togglePromptTemplate,
  executePromptTemplate,
  fetchAiUiRuntimeStatus,
  fetchAiUiCases,
  generateAiUiCase,
  saveAiUiCase,
  deleteAiUiCase,
  fetchAiUiRuns,
  startAiUiRun,
  fetchAiUiRun,
  stopAiUiRun,
  fetchAdminUsers,
  updateAdminUser,
  deleteAdminUser,
  approveAdminUser,
  rejectAdminUser,
} from './api.js'

const defaultEnvironments = ['sit', 'uat', 'dev', 'preprod', 'reg', 'local']
const defaultAiSqlDataSources = ['sit', 'uat', 'dev', 'preprod', 'reg', 'local', 'douke', 'dowsure']
const defaultJourneys = ['200K', '500K', '2000K']
const defaultCurrencies = ['USD', 'CNY']
const aiUiEnvironmentOptions = [
  { value: 'sit', label: 'SIT', url: 'https://expressfinance-dpu-sit.dowsure.com/en/' },
  { value: 'dev', label: 'DEV', url: 'https://expressfinance-dpu-dev.dowsure.com/en/sign-up-step1' },
  { value: 'uat', label: 'UAT', url: 'https://expressfinance-uat.business.hsbc.com/zh-Hans/' },
  { value: 'preprod', label: 'PREPROD', url: 'https://expressfinance-preprod.business.hsbc.com/zh-Hans/sign-up' },
  { value: 'reg', label: 'REG', url: 'https://expressfinance-dpu-reg.dowsure.com/en/' },
  { value: 'custom', label: '自定义', url: '' },
]
const upstreamBaseUrls = {
  sit: 'https://sit.api.expressfinance.business.hsbc.com',
  dev: 'https://dpu-gateway-dev.dowsure.com',
  uat: 'https://uat.api.expressfinance.business.hsbc.com',
  preprod: 'https://preprod.api.expressfinance.business.hsbc.com',
  reg: 'https://dpu-gateway-reg.dowsure.com',
  local: 'http://192.168.11.3:8080',
}
const apiConfigEndpointPaths = {
  'api_config.create_offerid_url': '/dpu-merchant/mock/generate-shop-performance',
  'self.api_config.create_offerid_url': '/dpu-merchant/mock/generate-shop-performance',
  'api_config.redirect_url': '/dpu-merchant/amazon/redirect',
  'self.api_config.redirect_url': '/dpu-merchant/amazon/redirect',
  'api_config.register_url': '/dpu-user/auth/signup',
  'self.api_config.register_url': '/dpu-user/auth/signup',
  'api_config.multi_shop_sp_auth_url': '/dpu-auth/amazon-sp/auth',
  'self.api_config.multi_shop_sp_auth_url': '/dpu-auth/amazon-sp/auth',
  'api_config.link_sap_3pl_url': '/dpu-merchant/mock/link-sp-3pl-shops',
  'self.api_config.link_sap_3pl_url': '/dpu-merchant/mock/link-sp-3pl-shops',
  'api_config.create_psp_auth_url': '/dpu-openapi/test/create-psp-auth-token',
  'self.api_config.create_psp_auth_url': '/dpu-openapi/test/create-psp-auth-token',
  'api_config.webhook_url': '/dpu-openapi/webhook-notifications',
  'self.api_config.webhook_url': '/dpu-openapi/webhook-notifications',
  'api_config.update_offer_url': '/dpu-auth/amazon-sp/updateOffer',
  'self.api_config.update_offer_url': '/dpu-auth/amazon-sp/updateOffer',
}
const defaultFunderResources = ['FUNDPARK', 'HSBC', 'DOWSURE']
const journeyLabels = {
  '200K': 'tier 1',
  '500K': 'tier 2',
  '2000K': 'tier 3',
}

const health = ref('checking')
const loadingHealth = ref(false)
const loadingEnums = ref(false)
const connecting = ref(false)
const registering = ref(false)
const registeringAndBinding = ref(false)
const disconnecting = ref(false)
const loadingSessions = ref(false)
const runningOperationKey = ref('')
const enumOptions = ref(null)
const activeOperationKey = ref('')
const activeSessionId = ref('')
const selectedApplicationUniqueId = ref('')
const applicationCodeOptions = ref([])
const loadingApplicationCodes = ref(false)
const dowsureMerchantAccounts = ref([])
const loadingDowsureMerchantAccounts = ref(false)
const webankSellerOffers = ref([])
const loadingWebankSellerOffers = ref(false)
const limitApplicationRows = ref([])
const loadingLimitApplications = ref(false)
const selectedLimitApplicationUniqueId = ref('')
const limitApplicationSelectionTouched = ref(false)
const drawdownRepaymentRows = ref([])
const loadingDrawdownRepaymentRows = ref(false)
const selectedDowsureRepaymentLoanCode = ref('')
const drawdownRepaymentSelectionTouched = ref(false)
const pspAuthorizationRows = ref([])
const loadingPspAuthorizationRows = ref(false)
const selectedPspMerchantAccountId = ref('')
const pspSelectionTouched = ref(false)
const operationResults = reactive({})
const liveSessions = ref([])
const eventLogs = ref([])
const activityFeed = ref([])
const auditOperations = ref([])
const expandedAuditOperationIds = ref(new Set())
const auditQuery = reactive({ phone_number: '', session_id: '' })
const auditLoading = ref(false)
const auditError = ref('')
const environmentMonitor = ref({ overall: 'checking', checked_at: '', items: [] })
const environmentMonitorLoading = ref(false)
const environmentMonitorError = ref('')
const environmentMonitorRefreshSeconds = ref(60)
let environmentMonitorRefreshTimer = null
const promptTemplates = ref([])
const promptTemplatesLoading = ref(false)
const promptTemplatesError = ref('')
// 提示词模板：名称/描述模糊搜索 + 分页
const promptTemplateSearch = ref('')
const promptTemplatePage = ref(1)
const promptTemplatePageSize = ref(6)
const filteredPromptTemplates = computed(() => {
  const kw = promptTemplateSearch.value.trim().toLowerCase()
  if (!kw) return promptTemplates.value
  return promptTemplates.value.filter((t) => (
    (t.title || '').toLowerCase().includes(kw)
    || (t.description || '').toLowerCase().includes(kw)
  ))
})
const promptTemplatesTotal = computed(() => filteredPromptTemplates.value.length)
const pagedPromptTemplates = computed(() => {
  const start = (promptTemplatePage.value - 1) * promptTemplatePageSize.value
  return filteredPromptTemplates.value.slice(start, start + promptTemplatePageSize.value)
})
// 搜索变化时回到第 1 页；分页越界（如删到只剩前面几页）时自动收回。
watch(promptTemplateSearch, () => { promptTemplatePage.value = 1 })
watch(promptTemplatesTotal, (total) => {
  const maxPage = Math.max(1, Math.ceil(total / promptTemplatePageSize.value))
  if (promptTemplatePage.value > maxPage) promptTemplatePage.value = maxPage
})
const promptTemplateFormVisible = ref(false)
const promptTemplateSaving = ref(false)
const promptTemplateForm = reactive({
  id: null,
  title: '',
  description: '',
  logic_type: 'sql',
  logic: '',
  example_prompt: '',
  locked_env: '',
})
const promptTemplateUseVisible = ref(false)
const promptTemplateUseTarget = ref(null)
const promptTemplateUseLoading = ref(false)
const promptTemplateUseError = ref('')
const promptTemplateUseResult = ref(null)
const promptTemplateUseForm = reactive({
  user_input: '',
  env: 'reg',
})
// 按占位符拆分的分列参数输入（key = 占位符名，如 phone / offer_id）。
const promptTemplateUseParams = reactive({})

// Admin: user management
const adminUsers = ref([])
const adminUsersLoading = ref(false)
const adminUsersError = ref('')
const adminUsersPage = ref(1)
const adminUsersPageSize = ref(20)
const adminUsersPagedData = computed(() => {
  const start = (adminUsersPage.value - 1) * adminUsersPageSize.value
  return adminUsers.value.slice(start, start + adminUsersPageSize.value)
})
const adminUserEditVisible = ref(false)
const adminUserEditSaving = ref(false)
const adminUserEditForm = reactive({
  original_username: '',
  new_username: '',
  new_password: '',
  notes: '',
})

// Pending review screen: shown after registration until admin approves/rejects
const pendingReviewUsername = ref('')
const pendingReviewStatus = ref('') // '' | 'loading' | 'approved' | 'rejected'
let notifySocket = null

const PROMPT_PARAM_HINT_MAP = {
  offer_id: '3P offer id',
  tpl_offer_id: '3PL offer id',
  amazon_3pl_offer_id: 'Amazon 3PL offer id',
  application_unique_id: '申请单号',
  application_code: '申请单号（application_code）',
  douke_application_id: 'douke 申请单号',
  value: '目标数值',
  amount: '金额',
  status: '目标状态',
  phone: '手机号',
  phone_number: '手机号',
  merchant_id: '商户号',
  user_id: '用户 ID',
  id_card_match: '身份证是否一致',
  company_name_match: '企业名字是否一致',
  legal_name_match: '法人名字是否一致',
  psp_type: 'PSP 服务商类型',
  psp_subject_type: '主体类型',
  env: '环境',
  shop_type: '店铺类型（DPU_3PL/SP/3PL）',
  country: '国家（US/CA/DE/UK/GB/FR/IT/ES/JP）',
  is_admit: '是否准入（1=准入，0=不准入）',
  seller_id: 'sellerId（留空自动生成）',
  access_mode: '店铺是否准入（ADMITTED/NOT_ADMITTED）',
  sp_mode: 'SP 授权（AUTHORIZED/NOT_AUTHORIZED）',
  quota_year1_sales_value: 'CUSTOM 年销售额',
}

// 使用模板弹窗里可留空的占位符（后端会自动生成/兜底），不做必填校验。
const OPTIONAL_PROMPT_PARAMS = new Set(['seller_id', 'quota_year1_sales_value'])
const PROMPT_PARAM_SELECT_OPTIONS = {
  company_name_match: [
    { label: '一致（Y）', value: 'Y' },
    { label: '不一致（N）', value: 'N' },
  ],
  legal_name_match: [
    { label: '一致（Y）', value: 'Y' },
    { label: '不一致（N）', value: 'N' },
  ],
  id_card_match: [
    { label: '一致（Y）', value: 'Y' },
    { label: '不一致（N）', value: 'N' },
  ],
  psp_type: ['P1', 'P2', 'P3', 'P4', 'P5', 'P6', 'P8', 'P9', 'P11']
    .map((value) => ({ label: value, value })),
  shop_type: [
    { label: 'DPU_3PL', value: 'DPU_3PL' },
    { label: 'SP', value: 'SP' },
    { label: '3PL', value: '3PL' },
  ],
  country: [
    { label: 'US', value: 'US' },
    { label: 'CA', value: 'CA' },
    { label: 'DE', value: 'DE' },
    { label: 'UK', value: 'UK' },
    { label: 'GB', value: 'GB' },
    { label: 'FR', value: 'FR' },
    { label: 'IT', value: 'IT' },
    { label: 'ES', value: 'ES' },
    { label: 'JP', value: 'JP' },
  ],
  is_admit: [
    { label: '准入（1）', value: '1' },
    { label: '不准入（0）', value: '0' },
  ],
  access_mode: [
    { label: '准入（ADMITTED）', value: 'ADMITTED' },
    { label: '不准入（NOT_ADMITTED）', value: 'NOT_ADMITTED' },
  ],
  sp_mode: [
    { label: '已授权（AUTHORIZED）', value: 'AUTHORIZED' },
    { label: '未授权（NOT_AUTHORIZED）', value: 'NOT_AUTHORIZED' },
  ],
}

const PSP_SUBJECT_TYPE_OPTIONS = {
  payment_user: [
    { label: '个人（PERSONAL）', value: 'PERSONAL' },
    { label: '企业（ENTERPRISE）', value: 'ENTERPRISE' },
  ],
  P3: [
    { label: '个人（CN_ID_CARD）', value: 'CN_ID_CARD' },
    { label: '企业（CREDIT_CODE）', value: 'CREDIT_CODE' },
  ],
  P2: [
    { label: '个人（0）', value: '0' },
    { label: '企业（1）', value: '1' },
  ],
}

const useDialogTargetPlaceholders = computed(() => {
  const logic = promptTemplateUseTarget.value?.logic || ''
  if (!logic) return []
  const matches = new Set()
  const regex = /\$\{(\w+)\}/g
  let m
  while ((m = regex.exec(logic)) !== null) {
    matches.add(m[1])
  }
  const placeholders = Array.from(matches)
  // 将三个一致性选项连续展示：身份证、企业名字、法人名字。
  if (matches.has('id_card_match')) {
    const nameFields = ['company_name_match', 'legal_name_match'].filter((key) => matches.has(key))
    const ordered = placeholders.filter((key) => !nameFields.includes(key))
    ordered.splice(ordered.indexOf('id_card_match') + 1, 0, ...nameFields)
    return ordered
  }
  return placeholders
})

const useDialogParamHints = computed(() => {
  return useDialogTargetPlaceholders.value.map((key) => PROMPT_PARAM_HINT_MAP[key] || key)
})

// 每个占位符一个输入项：{ key, label }，供弹窗按列渲染独立输入框。
const useDialogParamFields = computed(() => {
  return useDialogTargetPlaceholders.value.map((key) => ({
    key,
    label: PROMPT_PARAM_HINT_MAP[key] || key,
    options: getPromptTemplateParamOptions(key),
    placeholder: key === 'psp_subject_type' && !getPromptTemplateParamOptions(key).length
      ? (promptTemplateUseParams.psp_type ? '不适用' : '请先选择 PSP 服务商类型')
      : '',
    help: key === 'quota_year1_sales_value'
      ? '填写 5000 万到 2 亿，权重占比高。'
      : '',
    disabled: (
      key === 'quota_year1_sales_value'
      && promptTemplateUseParams.access_mode === 'NOT_ADMITTED'
    ) || (
      (
        (key === 'country' && promptTemplateUseParams.shop_type === '3PL')
        || (key === 'sp_mode' && ['3PL', 'SP'].includes(promptTemplateUseParams.shop_type))
      )
    ) || (
      key === 'psp_subject_type' && !getPromptTemplateParamOptions(key).length
    ),
  }))
})

const useDialogInputLabel = computed(() => {
  const hints = useDialogParamHints.value
  if (!hints.length) return '需要 AI 处理的内容'
  return `请提供：${hints.join('、')}`
})

const useDialogInputPlaceholder = computed(() => {
  const hints = useDialogParamHints.value
  if (hints.length) {
    return hints.length === 1 ? `请输入${hints[0]}` : `请按顺序输入：${hints.join('、')}`
  }
  const example = promptTemplateUseTarget.value?.example_prompt
  if (example) return example
  return '请描述需要执行的内容'
})

// Env dropdown options for the "use template" dialog. When a template pins an
// env that isn't in defaultEnvironments (e.g. external sources like douke /
// dowsure), surface it as the only option and let the locked-env path keep the
// picker disabled.
const useDialogEnvOptions = computed(() => {
  const lockedEnv = (promptTemplateUseTarget.value?.locked_env || '').trim().toLowerCase()
  if (lockedEnv) {
    return defaultEnvironments.includes(lockedEnv) ? defaultEnvironments : [lockedEnv]
  }
  return defaultEnvironments
})
const registerResult = ref(null)
const registerAutoConnected = ref(false)
const wsConnected = ref(false)
const wsError = ref('')
const darkMode = ref(false)
const toolRailCollapsed = ref(false)
const toolRailOpen = ref(typeof window !== 'undefined' ? window.innerWidth >= 1024 : true)
const isMobileViewport = ref(typeof window !== 'undefined' ? window.innerWidth < 1024 : false)
const aiExecutionEnv = ref('sit')
const aiMessages = ref([])
const aiInput = ref('')
const aiSending = ref(false)
const aiError = ref('')
const aiModel = ref('claude-haiku-4.5')
const aiReasoningEffort = ref('medium')
const aiLastUsedModel = ref('')
const aiModelOptions = [
  { value: 'claude-sonnet-4.6', label: 'Claude Sonnet 4.6' },
  { value: 'claude-opus-4.7', label: 'Claude Opus 4.7' },
  { value: 'claude-haiku-4.5', label: 'Claude Haiku 4.5' },
  { value: 'deepseek-3.2', label: 'DeepSeek 3.2' },
  { value: 'DeepSeek-V4-Flash', label: 'DeepSeek V4 Flash' },
  { value: 'DeepSeek-V4-Pro', label: 'DeepSeek V4 Pro' },
  { value: 'Qwen3.5-35B-A3B', label: 'Qwen3.5 35B-A3B' },
  { value: 'qwen3-coder-next', label: 'Qwen3 Coder Next' },
  { value: 'GLM-5.1', label: 'GLM 5.1' },
  { value: 'glm-5', label: 'GLM 5' },
  { value: 'minimax-m2.1', label: 'MiniMax M2.1' },
  { value: 'minimax-m2.5', label: 'MiniMax M2.5' },
]
const aiReasoningOptions = [
  { value: 'low', label: '低' },
  { value: 'medium', label: '中' },
  { value: 'high', label: '高' },
  { value: 'extreme', label: '极高' },
]
const currentView = ref('console')
const aiUiCases = ref([])
const aiUiRuns = ref([])
const aiUiRuntime = ref(null)
const aiUiLoading = ref(false)
const aiUiSaving = ref(false)
const aiUiGenerating = ref(false)
const aiUiError = ref('')
const aiUiSelectedCaseId = ref('')
const aiUiActiveRunId = ref('')
const aiUiNaturalLanguage = ref('')
const aiUiStructuredYaml = ref('')
const aiUiVariablesText = ref('{}')
const aiUiStructuredSpec = ref(null)
const aiUiRunConfirmVisible = ref(false)
const aiUiPendingCase = ref(null)
const aiUiPageMode = ref('cases')
const aiUiPageModes = [
  { key: 'cases', label: '案例' },
  { key: 'reports', label: '报告' },
]
let aiUiPollTimer = null
const aiUiForm = reactive({
  id: null,
  environment: 'sit',
  name: 'OFFLINE 注册入口检查-SIT-样板',
  url: 'https://expressfinance-dpu-sit.dowsure.com/en/',
  context: '这是 OFFLINE_SIGNUP_URL_DICT 的 SIT 页面入口冒烟用例。只验证环境 URL、FundPark USD 产品进入注册页以及手机号验证控件，不发送短信、不创建客户。',
  prompt: `Scenario: OFFLINE signup entry smoke test
  Given the SIT HSBC Express Finance homepage is open
  When I click the "Get started" button for the FundPark USD Line of Credit product
  Then the page should show "Enter your contact details to begin"
  And the page should show the "Mobile number" field
  And the "Get code" button should be disabled before a mobile number is entered`,
  headed: false,
  viewport: { width: 1440, height: 900 },
})
const logSearchLoading = ref(false)
const logSearchResults = ref([])
const authStorageKey = 'mockapi-auth-user'
const authUser = ref(null)
const loginError = ref('')
const registerError = ref('')
const authMode = ref('login')

const loginForm = reactive({
  username: '',
  password: '',
  remember: false,
})

const userRegisterForm = reactive({
  username: '',
  password: '',
  answer: '',
})

const captchaChallenge = reactive({
  left: 3,
  right: 3,
})

const DEFAULT_LOG_PREVIEW_LIMIT = 100
const DEFAULT_LOG_SEARCH_LIMIT = 500

const logSearchForm = reactive({
  keyword: '',
  timeRange: [],
  limit: DEFAULT_LOG_PREVIEW_LIMIT,
})

function formatJsonBlock(payload) {
  return JSON.stringify(payload ?? {}, null, 2)
}

function isAuditOperationExpanded(id) {
  return expandedAuditOperationIds.value.has(String(id))
}

function toggleAuditOperationDetail(id) {
  const key = String(id)
  const next = new Set(expandedAuditOperationIds.value)
  if (next.has(key)) {
    next.delete(key)
  } else {
    next.add(key)
  }
  expandedAuditOperationIds.value = next
}

const contactForm = reactive({
  issue: '',
})
const contactAdminForm = reactive({
  username: '',
  password: '',
  reply: '',
})
const contactAdminLoggedIn = ref(false)
const contactAdminError = ref('')
const contactIssues = ref([])
const interfaceStepEnabled = reactive({})
const activeInterfaceScenarioKey = ref('fpUsd500k')
const activeScenarioTab = ref('base')
const expandedScenarioTrees = reactive({ fpUsd500k: false, fpUsd2k: false, dsCny: false })
const expandedScenarioDirectories = reactive({ singleShop: false, multiShop: false })
const scenarioLibrarySearch = ref('')
const debugInterfaceSearch = ref('')
const interfacePageMode = ref('scenario')
const interfaceFocusMode = ref('scenario')
const stepFocusTab = ref('params')
const debugRequestHeadersText = ref('{\n  "Content-Type": "application/json"\n}')
const debugRequestBodyText = ref('{}')
const debugRequestQueryText = ref('{}')
const debugActualMethod = ref('POST')
const debugActualUrlText = ref('')
const debugRequestError = ref('')
const debugSending = ref(false)
const scenarioSaveState = ref('已保存')
const scenarioExecuting = ref(false)
// Flipped by handleScenarioStop; the scenario loop checks it between steps and
// aborts as soon as it sees true. Reset back to false whenever a new run starts.
const scenarioStopRequested = ref(false)
// Per-user configurable parameter overrides for scenario steps.
//   key   -> `${scenarioKey}::${stepKey}`
//   value -> { [field]: value }
// Persisted on the backend via /api/scenario-overrides. Loaded once when the
// authenticated user is known; mirrored back to backend whenever the user
// presses 保存 on a step's 参数 tab.
const scenarioStepOverrides = reactive({})
const scenarioStepOverrideDraft = reactive({})
const scenarioStepOverrideSaving = reactive({})
// Presets and company templates are persisted as one whole-array payload per
// step, rebuilt from the in-memory list on every save. Until a load has
// actually succeeded that list only holds the builtin defaults, so writing it
// back would erase the user's custom records. Saves stay blocked while false.
const scenarioStepOverridesLoaded = ref(false)
const SHOP_PERFORMANCE_PRESET_SCENARIO = 'mockApi'
const SHOP_PERFORMANCE_PRESET_STEP = 'shop-performance-presets'
const DOWSURE_COMPANY_TEMPLATE_SCENARIO = 'mockApi'
const DOWSURE_COMPANY_TEMPLATE_STEP = 'dowsure-cny-company-templates'
const DEFAULT_DOWSURE_CNY_COMPANY_TEMPLATE = {
  name: '广州测试科技有限公司',
  template: {
    enName: '',
    cnName: '广州测试科技有限公司',
    regNo: '91440101MA5D6YRJ0X',
    address: '广州市天河区测试路1号',
    contactNumber: { countryCode: '+86', number: '' },
    operationAddressFlag: true,
    operationAddress: '',
    businessDocName: '营业执照.png',
  },
  directorTemplate: {
    position: 'DIRECTOR_AND_LEGAL_REPRESENTATIVE',
    nameCn: '奉晓慧',
    nameEn: '',
    mobileNumber: { countryCode: '+86', number: '18374816332' },
    dowsurePersonInfoExtend: {
      idNumber: '431121199611248750',
      idCardStartDate: '02/06/2026',
      idCardEndDate: '',
      longTermFlag: 'true',
      addressDetail: '广州市天河区测试路1号',
    },
    dateOfBirth: '03/06/2026',
    frontDocName: '身份证正面.png',
    backDocName: '身份证反面.png',
    emailAddress: '18374816332@qq.com',
    idDocumentType: 'PRC_RESIDENT_ID_CARD',
  },
  contactTemplate: {
    isDraft: false,
    isExistingPerson: false,
    selectedPersonId: '',
    fullChineseName: '奉晓慧',
    email: '18374816332@qq.com',
    mobileNumber: '18374816332',
    phoneCountryCode: '+86',
  },
}
const BACKUP_DOWSURE_CNY_COMPANY_TEMPLATE = {
  name: '测广州市昆袄祝山脸从股份有限公司',
  template: {
    enName: '',
    cnName: '测广州市昆袄祝山脸从股份有限公司',
    regNo: '914401000747111984',
    address: '甘肃省兰州市盘快饺题路247号301',
    contactNumber: { countryCode: '+86', number: '' },
    operationAddressFlag: true,
    operationAddress: '',
    businessDocName: '营业执照.png',
  },
  directorTemplate: {
    position: 'DIRECTOR_AND_LEGAL_REPRESENTATIVE',
    nameCn: '测近智',
    nameEn: '',
    mobileNumber: { countryCode: '+86', number: '19443548216' },
    dowsurePersonInfoExtend: {
      idNumber: '620100197108054266',
      idCardStartDate: '10/08/2025',
      idCardEndDate: '',
      longTermFlag: 'true',
      addressDetail: '甘肃省兰州市盘快饺题路247号301',
    },
    dateOfBirth: '05/08/1971',
    frontDocName: '身份证正面.png',
    backDocName: '身份证反面.png',
    emailAddress: '19443548216@qq.com',
    idDocumentType: 'PRC_RESIDENT_ID_CARD',
  },
  contactTemplate: {
    isDraft: false,
    isExistingPerson: false,
    selectedPersonId: '',
    fullChineseName: '测近智',
    email: '19443548216@qq.com',
    mobileNumber: '19443548216',
    phoneCountryCode: '+86',
  },
}
const BUILTIN_DOWSURE_CNY_COMPANY_TEMPLATES = [
  DEFAULT_DOWSURE_CNY_COMPANY_TEMPLATE,
  BACKUP_DOWSURE_CNY_COMPANY_TEMPLATE,
]
const BUILTIN_DOWSURE_CNY_COMPANY_TEMPLATE_NAMES = new Set(
  BUILTIN_DOWSURE_CNY_COMPANY_TEMPLATES.map((item) => item.name),
)
function cloneDowsureCompanyTemplate(item) {
  return JSON.parse(JSON.stringify(item))
}
const BUILTIN_SHOP_PERFORMANCE_NAMES = [
  'webank准入ccb准入',
  'webank不准入ccb准入',
  'webank准入ccb不准入',
  'webank不准入ccb不准入',
  '店铺5',
  '店铺6',
  '店铺7',
  '店铺8',
  '店铺9',
  '店铺10',
  '店铺11',
  '店铺12',
  '店铺13',
  '店铺14',
  '店铺15',
  '店铺16',
]
const BUILTIN_SHOP_PERFORMANCE_NAME_SET = new Set(BUILTIN_SHOP_PERFORMANCE_NAMES)
function createBuiltinShopPerformancePresets() {
  return BUILTIN_SHOP_PERFORMANCE_NAMES.map((name) => ({
    name,
    custom_sql: '',
    builtin_sql: '',
    is_builtin: true,
    is_customized: false,
  }))
}
function mergeShopPerformancePresets(savedPresets = []) {
  const presetsByName = new Map(
    createBuiltinShopPerformancePresets().map((item) => [item.name, item]),
  )
  savedPresets
    .filter((preset) => preset?.name && preset?.custom_sql)
    .forEach((preset) => {
      const name = String(preset.name).trim()
      presetsByName.set(name, {
        name,
        custom_sql: String(preset.custom_sql),
        builtin_sql: '',
        is_builtin: BUILTIN_SHOP_PERFORMANCE_NAME_SET.has(name),
        is_customized: true,
      })
    })
  return Array.from(presetsByName.values())
}
function serializeShopPerformancePresets(presets) {
  return presets
    .filter((preset) => (
      preset?.name
      && String(preset.custom_sql || '').trim()
      && (!preset.is_builtin || preset.is_customized)
    ))
    .map((preset) => ({
      name: String(preset.name).trim(),
      custom_sql: String(preset.custom_sql).trim(),
    }))
}
const shopPerformancePresets = ref(createBuiltinShopPerformancePresets())
const shopPerformanceBuiltinLoading = ref(false)
const shopPerformancePresetForm = reactive({
  name: '',
  custom_sql: '',
})
const shopPerformancePresetSaving = ref(false)
const shopPerformancePresetError = ref('')
const editingShopPerformancePresetName = ref('')
const shopPerformanceManagerVisible = ref(false)
const shopPerformanceEditorVisible = ref(false)
const BUILTIN_COMPANY_IMAGE_TEMPLATES = [
  {
    id: 'builtin:business_license',
    name: '测广州市昆袄祝山脸从股份有限公司营业执照',
    image_type: 'business_license',
    filename: 'business_license.png',
    is_builtin: true,
  },
  {
    id: 'builtin:director_id_front',
    name: '默认法人身份证正面',
    image_type: 'director_id_front',
    filename: 'director_id_front.png',
    is_builtin: true,
  },
  {
    id: 'builtin:director_id_back',
    name: '默认法人身份证反面',
    image_type: 'director_id_back',
    filename: 'director_id_back.png',
    is_builtin: true,
  },
]
const companyImageTemplates = ref(BUILTIN_COMPANY_IMAGE_TEMPLATES.map((item) => ({ ...item })))
const companyImageManagerVisible = ref(false)
const companyImageSaving = ref(false)
const companyImageError = ref('')
const companyImageFile = ref(null)
const companyImageLocalPreview = ref('')
const companyImageFileInputKey = ref(0)
const companyImageForm = reactive({
  id: '',
  name: '',
  image_type: 'business_license',
  filename: '',
  is_builtin: false,
})
const dowsureCnyCompanyTemplates = ref(
  BUILTIN_DOWSURE_CNY_COMPANY_TEMPLATES.map(cloneDowsureCompanyTemplate),
)
const dowsureCompanyTemplateForm = reactive({
  name: DEFAULT_DOWSURE_CNY_COMPANY_TEMPLATE.name,
  templateText: JSON.stringify(DEFAULT_DOWSURE_CNY_COMPANY_TEMPLATE.template, null, 2),
  directorTemplateText: JSON.stringify(DEFAULT_DOWSURE_CNY_COMPANY_TEMPLATE.directorTemplate, null, 2),
  contactTemplateText: JSON.stringify(DEFAULT_DOWSURE_CNY_COMPANY_TEMPLATE.contactTemplate, null, 2),
})
const dowsureCompanyTemplateSaving = ref(false)
const dowsureCompanyTemplateError = ref('')
const editingDowsureCompanyTemplateName = ref('')
const dowsureCompanyTemplateManagerVisible = ref(false)
function scenarioStepOverrideKey(scenarioKey, stepKey) {
  return `${scenarioKey || ''}::${stepKey || ''}`
}

// Admin-editable scenario meta overrides (name / description). All users see
// the override after admin saves it.
const scenarioMetaOverrides = reactive({})
const scenarioMetaEditVisible = ref(false)
const scenarioMetaEditSaving = ref(false)
const scenarioMetaEditForm = reactive({
  scenarioKey: '',
  name: '',
  description: '',
})

// Admin-editable step display overrides. Stored globally and applied before
// per-user ordering/enabling so every user sees the same hidden/renamed steps.
const scenarioStepMetaOverrides = reactive({})
const scenarioStepMetaEditVisible = ref(false)
const scenarioStepMetaEditSaving = ref(false)
const scenarioStepMetaEditDeleting = ref(false)
const scenarioStepMetaEditForm = reactive({
  scenarioKey: '',
  stepKey: '',
  title: '',
  description: '',
  isHidden: false,
})

// Admin-only step editing stays local until the toolbar 保存 button is used.
// Added steps are copied from an existing step so they retain the same
// executable request definition and can be inserted after any current step.
const scenarioStepStructureDraft = reactive({})
const scenarioStepStructureDeleted = reactive({})
const scenarioAddStepVisible = ref(false)
const scenarioAddStepForm = reactive({ scenarioKey: '', afterStepKey: '', sourceStepKey: '' })

// Per-user drag-and-drop step ordering for scenarios. Persisted server-side.
//   scenarioStepOrders    -> committed order pulled from backend on login
//   scenarioStepOrderDraft-> in-flight order while user drags around; only
//                            copied into scenarioStepOrders when they click
//                            保存 in the toolbar
const scenarioStepOrders = reactive({})
const scenarioStepOrderDraft = reactive({})
const scenarioDragState = ref({ scenarioKey: '', stepKey: '' })
const mockOperationEditMode = ref(false)
const mockOperationDragState = ref('')
let mockOperationLongPressTimer = null
const scenarioExecutionHistory = ref([])
const scenarioStepResults = reactive({})
const scenarioStepSourceCache = reactive({})
const scenarioStepSourceLoading = reactive({})
const scenarioStepSourceErrors = reactive({})
const expandedScenarioSteps = reactive({})
const scenarioStepDetailTabs = reactive({})
const latestScenarioRunContext = ref(null)
const scenarioHistoryDetailVisible = ref(false)
const selectedScenarioHistoryRecord = ref(null)
const scenarioHistoryDetailPayloadMode = ref('mock')
const scenarioAssertions = ref([
  { target: 'HTTP 状态码', rule: '等于 200', enabled: true },
  { target: '响应体 success', rule: '等于 true', enabled: true },
  { target: '业务 traceId', rule: '存在且非空', enabled: true },
])
const scenarioVariables = reactive({
  env: '${env}',
  phone_number: '${phone_number}',
  email: '${email}',
  session_id: '${session_id}',
  merchant_id: '${merchant_id}',
  platform_offer_id: '${platform_offer_id}',
  application_unique_id: '${application_unique_id}',
  limit_application_unique_id: '${limit_application_unique_id}',
  lender_approved_offer_id: '${lender_approved_offer_id}',
  // step-wise register variables (used by DMF/FP/DS scenarios when the
  // pre-registration flow is split into individual /api/register/* calls)
  offer_id: '${offer_id}',
  verification_code: '${verification_code}',
  token: '${token}',
  state: '${state}',
  selling_partner_id: '${selling_partner_id}',
})
const scenarioSettings = reactive({
  stopOnFailure: true,
  saveResponse: true,
  validateSession: false,
  timeout: '30s',
})

const scenarioHistoryStorageKey = 'mockapi-scenario-execution-history'

const connectionForm = reactive({
  env: 'reg',
  phone_number: '',
})

const registerForm = reactive({
  env: 'reg',
  journey: '500K',
  currency: 'USD',
  funder_resource: 'FUNDPARK',
  offline: false,
})

// Some currency/funder combinations are not supported by the DPU registration
// flow today. Block them on the frontend so users don't trigger an inevitable
// backend failure. Each entry pins which mode (online/offline) is affected.
//   - Online  + USD + HSBC      → HSBC USD 只走线下
//   - Online  + CNY + HSBC      → 线上 CNY 资方限制
//   - Online  + CNY + FUNDPARK  → 线上 CNY 资方限制
//   - Offline + CNY + HSBC      → 线下 CNY 资方限制
//   - Offline + CNY + FUNDPARK  → 线下 CNY 资方限制
//   - Online  + USD + DOWSURE   → 注册及注册并完成绑店均禁用
//   - Offline + USD + DOWSURE   → 注册及注册并完成绑店均禁用
// DOWSURE + CNY registration itself is allowed in both modes; only the combined
// online register-and-bind flow is gated, see dowsureOnlineBindingBlocked below.
const BLOCKED_REGISTER_COMBOS = [
  { offline: false, currency: 'USD', funder_resource: 'HSBC' },
  { offline: false, currency: 'CNY', funder_resource: 'HSBC' },
  { offline: false, currency: 'CNY', funder_resource: 'FUNDPARK' },
  { offline: true, currency: 'CNY', funder_resource: 'HSBC' },
  { offline: true, currency: 'CNY', funder_resource: 'FUNDPARK' },
  { offline: false, currency: 'USD', funder_resource: 'DOWSURE' },
  { offline: true, currency: 'USD', funder_resource: 'DOWSURE' },
]
const onlineUsdHsbcBlocked = computed(() =>
  BLOCKED_REGISTER_COMBOS.some(
    (combo) =>
      combo.offline === registerForm.offline
      && combo.currency === registerForm.currency
      && combo.funder_resource === registerForm.funder_resource
  )
)
const onlineUsdHsbcBlockedReason = computed(() => {
  const modeText = registerForm.offline ? '线下模式' : '线上模式'
  const combo = `${registerForm.currency} + ${registerForm.funder_resource}`
  return `${modeText}不支持 ${combo} 组合，请切换模式或更换币种/资方。`
})
const dowsureOnlineBindingBlocked = computed(() =>
  !registerForm.offline
  && registerForm.currency !== 'USD'
  && registerForm.funder_resource === 'DOWSURE'
)
const registerAndBindingBlocked = computed(() =>
  onlineUsdHsbcBlocked.value || dowsureOnlineBindingBlocked.value
)
const registerAndBindingBlockedReason = computed(() =>
  onlineUsdHsbcBlocked.value
    ? onlineUsdHsbcBlockedReason.value
    : 'DOWSURE 线上模式不支持注册并完成绑店，请切换到线下模式。'
)

const operationForms = reactive({
  linkSp3pl: {},
  underwritten: { amount: 500000, status: 'APPROVED' },
  dowsureCreditResult: {
    applicationCode: '',
    amount: 100000,
    processingFee: 0,
    creditResultList: [],
  },
  webankCreditResult: { application_code: '', businessSum: 500000, seller_offers: [] },
  cgbCreditResult: { amount: 200000, processingFee: 0, creditStatus: 'APPROVE' },
  cgbLoanResult: { application_code: '', amount: 100000, processingFee: 0 },
  cgbRepaymentResult: {
    application_code: '',
    payment_principal: 50000,
    payment_interest: 500,
    payment_overdue_interest: 0,
  },
  webankDrawdownResult: { application_code: '', loan_amount: 500000, service_fee_amount: 100 },
  webankRepaymentResult: {
    application_code: '',
    payment_principal: 10000,
    payment_interest: 0,
    payment_penalty_interest: 0,
  },
  dowsureEsignDrawdownResult: {
    application_code: '',
    credit_contract_no: '',
    amount: 100000,
    processing_fee: 0,
  },
  dowsureRepaymentResult: {
    application_code: '',
    payment_principal: 1000,
    payment_overdue_interest: 0,
  },
  dowsureRetryCallback: { application_code: '' },
  approvedOffer: { amount: 500000, status: 'APPROVED', failure_reason_index: 1, rejection_reason: 'fraud' },
  pspStart: { status: 'PROCESSING' },
  pspCompleted: { status: 'SUCCESS' },
  esign: { signed_amount: 500000, status: 'SUCCESS' },
  drawdown: { amount: 100000, status: 'APPROVED', failure_reason_index: 1 },
  repaymentStart: { principal_amount: 1000 },
  repayment: { principal_amount: 1000, status: 'Success', failure_reason_index: 1 },
  multiShopBinding: { state: '', platform_seller_id: '' },
  spStatusUpdate: { platform_seller_id: '', status: 'SUCCESS', failure_reason_index: 1 },
  multiShop3plRedirect: {},
  systemEvent: {
    event_type: 'EXCEPTION-APPLICATION-CREATION',
    application_unique_id: '',
    error_code: 'B-6003',
  },
  applicationAbandon: { abandon_reason: 'SellerCancelled' },
  pspHsbcStart: {},
  pspHsbcCompleted: { result: 'SUCCESS' },
})

let logSocket = null
let sessionPollTimer = null

const reasonOptions = computed(() => enumOptions.value?.returned_failure_reasons ?? [])
const approvedRejectionOptions = computed(() => enumOptions.value?.approved_rejection_reasons ?? [])
const drawdownReasonOptions = computed(() => enumOptions.value?.drawdown_failure_reasons ?? [])
const repaymentReasonOptions = computed(() => enumOptions.value?.repayment_failure_reasons ?? [])
const spFailureOptions = computed(() => enumOptions.value?.sp_update_failure_reasons ?? [])
const applicationAbandonOptions = computed(() => enumOptions.value?.application_abandon_reasons ?? [])
const aiSqlDataSources = computed(() => enumOptions.value?.ai_sql_data_sources ?? defaultAiSqlDataSources)
const pendingContactIssuesCount = computed(() => contactIssues.value.filter((item) => item.status !== '已回复').length)
const repliedContactIssuesCount = computed(() => contactIssues.value.filter((item) => item.status === '已回复').length)
const pendingContactIssues = computed(() => contactIssues.value.filter((item) => item.status !== '已回复'))
const isAuthenticated = computed(() => Boolean(authUser.value))
const isAdmin = computed(() => authUser.value?.role === 'admin')
const authDisplayName = computed(() => authUser.value?.username || '未登录')
const authRoleLabel = computed(() => (isAdmin.value ? '管理员账号' : '普通账号'))
const auditStats = computed(() => {
  const rows = auditOperations.value || []
  const successCount = rows.filter((item) => item.success === true).length
  const failedCount = rows.filter((item) => item.success === false).length
  const userCount = new Set(rows.map((item) => item.username).filter(Boolean)).size
  return [
    { label: '记录数', value: rows.length, hint: '当前筛选结果' },
    { label: '成功', value: successCount, hint: 'success = true' },
    { label: '失败', value: failedCount, hint: 'success = false' },
    { label: isAdmin.value ? '用户数' : '最近时间', value: isAdmin.value ? userCount : (rows[0]?.created_at || '-'), hint: isAdmin.value ? '涉及账号' : '最新操作' },
  ]
})
const environmentMonitorItems = computed(() => environmentMonitor.value?.items || [])
const environmentMonitorOverallLabel = computed(() => {
  const status = environmentMonitor.value?.overall
  if (status === 'operational') return 'OPERATIONAL'
  if (status === 'degraded') return 'DEGRADED'
  if (status === 'down') return 'DOWN'
  return 'CHECKING'
})
const environmentMonitorOverallType = computed(() => {
  const status = environmentMonitor.value?.overall
  if (status === 'operational') return 'success'
  if (status === 'down') return 'danger'
  if (status === 'degraded') return 'warning'
  return 'info'
})
function statusLabel(status) {
  if (status === 'operational' || status === 'ok') return '正常'
  if (status === 'down') return '异常'
  if (status === 'checking') return '检测中'
  return '波动'
}
function statusTagType(status) {
  if (status === 'operational' || status === 'ok') return 'success'
  if (status === 'down') return 'danger'
  if (status === 'checking') return 'info'
  return 'warning'
}
function availabilityState(value) {
  if (value === null || value === undefined || value === '') return 'checking'
  const numericValue = Number(value)
  if (!Number.isFinite(numericValue)) return 'checking'
  if (numericValue < 60) return 'down'
  if (numericValue < 80) return 'degraded'
  return 'ok'
}
function availabilityLabel(value) {
  return statusLabel(availabilityState(value))
}
function availabilityTagType(value) {
  return statusTagType(availabilityState(value))
}
function environmentCardState(item) {
  const states = [availabilityState(item?.availability), availabilityState(item?.channel_availability)]
  if (states.includes('down')) return 'down'
  if (states.includes('degraded')) return 'degraded'
  if (states.every((state) => state === 'ok')) return 'operational'
  return 'checking'
}
const activeToolModule = computed(() => {
  if (currentView.value === 'interfaceTest') return 'interfaceTest'
  if (currentView.value === 'aiUi') return 'aiUi'
  if (currentView.value === 'mockApi') return 'mockApi'
  if (currentView.value === 'activity') return 'activity'
  if (currentView.value === 'environmentMonitor') return 'environmentMonitor'
  if (currentView.value === 'ai') return 'ai'
  if (currentView.value === 'promptTemplates') return 'promptTemplates'
  if (currentView.value === 'about') return 'about'
  if (currentView.value === 'contact') return 'contact'
  if (currentView.value === 'contactAdmin') return 'contactAdmin'
  if (currentView.value === 'userManagement') return 'userManagement'
  return ''
})

const sessionSummary = computed(() => {
  const current = liveSessions.value.find((item) => item.session_id === activeSessionId.value)
  if (current) return current
  if (registerResult.value?.session?.session_id === activeSessionId.value) return registerResult.value.session
  return activityFeed.value.find((item) => item.kind === 'connect')?.payload ?? null
})

const activeOperation = computed(() => (
  operations.value.find((item) => item.key === activeOperationKey.value) ?? null
))

const interfaceTestOperation = computed(() => (
  operations.value.find((item) => item.key === activeOperationKey.value) ?? null
))

const interfaceTestPayloadPreview = computed(() => {
  if (!interfaceTestOperation.value) {
    return selectedInterfaceStep.value?.payload ?? {}
  }
  return buildPayload(interfaceTestOperation.value)
})

// Base scenario definitions. Display name / description may be overridden by
// admins through /api/scenario-overrides/meta and merged in below.
const scenarioBaseDefs = [
  {
    key: 'fpUsd500k',
    category: 'singleShop',
    code: '100132',
    name: 'FP-USD-500K-Offline',
    priority: 'P0',
    description: '完整 FP USD 500K 线下注册接口自动化场景（含 sp-updateOffer + 3PL 兜底）',
    bootstrap: { env: 'reg', currency: 'USD', funder_resource: 'FUNDPARK', offline: true },
    buildSteps: () => buildFpUsdScenarioSteps('500K', { prefix: 'FP-USD-500K-Offline', offline: true }),
  },
  {
    key: 'fpUsd500kOfflineDrawdown200k',
    category: 'singleShop',
    code: '100139',
    name: 'FP-USD-500K-Offline-Drawdown-200K',
    priority: 'P0',
    description: '完整 FP USD 500K 线下流程，执行至 eSign 成功后按 200K 放款',
    bootstrap: { env: 'reg', currency: 'USD', funder_resource: 'FUNDPARK', offline: true },
    buildSteps: () => buildFpUsdScenarioSteps('500K', {
      prefix: 'FP-USD-500K-Offline-Drawdown-200K',
      offline: true,
      drawdownAmount: 200000,
    }),
  },
  {
    key: 'fpUsd500kOnline',
    category: 'singleShop',
    code: '100136',
    name: 'FP-USD-500K-Online',
    priority: 'P0',
    description: 'FP USD 500K 线上注册并绑店（前 5 步走线上注册链路），后续步骤与 FP-USD-500K-Offline 完全一致',
    bootstrap: { env: 'reg', currency: 'USD', funder_resource: 'FUNDPARK', offline: false },
    buildSteps: () => buildFpUsdScenarioSteps('500K', { prefix: 'FP-USD-500K-Online', offline: false }),
  },
  {
    key: 'fpUsd800kOnline',
    category: 'singleShop',
    code: '100138',
    name: 'FP-USD-800K-Online',
    priority: 'P0',
    description: 'FP USD 800K 线上注册并绑店。唯一区别是第 1 步生成 offerId 用 tier3（yearlyRepaymentAmount=16666667），其余步骤与 FP-USD-500K-Online 完全一致',
    bootstrap: { env: 'reg', currency: 'USD', funder_resource: 'FUNDPARK', offline: false },
    buildSteps: () => buildFpUsdScenarioSteps('500K', {
      prefix: 'FP-USD-800K-Online',
      offline: false,
      createOfferJourney: '2000K',
      withActivateAdditionalLimit: true,
    }),
  },
  {
    key: 'fpUsd2k',
    category: 'singleShop',
    code: '100133',
    name: 'FP-USD-2K-Offline',
    priority: 'P0',
    description: '完整 FP USD 2K 线下注册接口自动化场景（含 sp-updateOffer + 3PL 兜底）',
    bootstrap: { env: 'reg', currency: 'USD', funder_resource: 'FUNDPARK', offline: true },
    buildSteps: () => buildFpUsdScenarioSteps('2K', { prefix: 'FP-USD-2K-Offline', offline: true }),
  },
  {
    key: 'fpUsd2kOnline',
    category: 'singleShop',
    code: '100137',
    name: 'FP-USD-2K-Online',
    priority: 'P0',
    description: 'FP USD 2K 线上注册并绑店（前 5 步走线上注册链路），后续步骤与 FP-USD-2K-Offline 完全一致',
    bootstrap: { env: 'reg', currency: 'USD', funder_resource: 'FUNDPARK', offline: false },
    buildSteps: () => buildFpUsdScenarioSteps('2K', { prefix: 'FP-USD-2K-Online', offline: false }),
  },
  {
    key: 'dsCny',
    category: 'singleShop',
    code: '100134',
    name: 'DS-CNY',
    priority: 'P0',
    description: 'DS CNY 注册后直接执行 3PL 重定向，再创建申请单并提交企业/法人信息',
    bootstrap: { env: 'reg', currency: 'CNY', funder_resource: 'DOWSURE', offline: true },
    buildSteps: () => buildDsCnyScenarioSteps(),
  },
  {
    key: 'dmf',
    category: 'singleShop',
    code: '100135',
    name: 'DMF',
    priority: 'P0',
    description: 'DMF (HSBC USD) 注册绑店场景，前 9 步与 FP-USD 一致，注册请求头使用 HSBC/USD',
    bootstrap: { env: 'reg', currency: 'USD', funder_resource: 'HSBC', offline: true },
    buildSteps: () => buildDmfScenarioSteps(),
  },
  {
    key: 'multiFpUsd2kIncrease',
    category: 'multiShop',
    code: '100139',
    name: 'FP-USD-2K提额',
    priority: 'P0',
    description: '多店铺 FP USD 2K 提额临时场景，先照搬 FP-USD-2K-Online 流程',
    bootstrap: { env: 'reg', currency: 'USD', funder_resource: 'FUNDPARK', offline: false },
    buildSteps: () => [
      ...buildFpUsdScenarioSteps('2K', { prefix: 'Multi-FP-USD-2K-Increase', offline: false }),
      {
        ...makeUnderwrittenStep('Multi-FP-USD-2K-Increase-additional-underwritten'),
        title: '提额underwritten',
        description: '提额流程追加核保步骤，继续调用 /api/mock/underwritten。',
      },
      makeIncreaseApprovedOfferStep('Multi-FP-USD-2K-Increase-additional-approved-offer', 500000),
      {
        ...makePspStartStep('Multi-FP-USD-2K-Increase-additional-psp-start'),
        title: '提额psp-start',
        description: '提额流程追加 PSP started，继续调用 /api/mock/psp-start。',
      },
      {
        ...makePspCompletedStep('Multi-FP-USD-2K-Increase-additional-psp-completed'),
        title: '提额psp-completed',
        description: '提额流程追加 PSP completed，继续调用 /api/mock/psp-completed。',
      },
      makeIncreaseEsignStep('Multi-FP-USD-2K-Increase-additional-esign', 500000),
    ],
  },
  {
    key: 'multiFpUsd500kIncrease',
    category: 'multiShop',
    code: '100140',
    name: 'FP-USD-500K提额',
    priority: 'P0',
    description: '多店铺 FP USD 500K 提额临时场景，先照搬 FP-USD-500K-Offline 流程',
    bootstrap: { env: 'reg', currency: 'USD', funder_resource: 'FUNDPARK', offline: true },
    buildSteps: () => [
      ...buildFpUsdScenarioSteps('500K', { prefix: 'Multi-FP-USD-500K-Increase', offline: true }),
      {
        key: 'Multi-FP-USD-500K-Increase-second-shop-state',
        type: 'api',
        method: 'POST',
        kind: '场景步骤',
        title: '第二家店铺生成 state 并申请 SP 授权 URL',
        endpoint: '/api/register/sp-auth-url',
        operationKey: null,
        payload: {
          env: '${env}',
          phone_number: '${phone_number}',
          token: '${token}',
          currency: 'USD',
          funder_resource: 'FUNDPARK',
          offline: true,
        },
        description: '第二家店铺 SP 授权 URL 生成步骤，复用注册分步接口 /api/register/sp-auth-url。',
      },
      {
        key: 'Multi-FP-USD-500K-Increase-second-shop-sp-auth',
        type: 'api',
        method: 'POST',
        kind: '场景步骤',
        title: '查询 SP auth-result 并回调 Amazon SP auth',
        endpoint: '/api/register/sp-auth-callback',
        operationKey: null,
        payload: {
          env: '${env}',
          phone_number: '${phone_number}',
          token: '${token}',
          state: '${state}',
          selling_partner_id: '${selling_partner_id}',
          currency: 'USD',
          funder_resource: 'FUNDPARK',
        },
        description: '查询第二家店铺 SP auth-result，并回调 Amazon SP auth。',
      },
      {
        key: 'Multi-FP-USD-500K-Increase-second-shop-3pl-redirect',
        type: 'api',
        method: 'POST',
        kind: '场景步骤',
        title: '3PL 重定向回调 (amazon/redirect + POST)',
        endpoint: '/api/register/3pl-redirect',
        operationKey: null,
        payload: {
          env: '${env}',
          phone_number: '${phone_number}',
        },
        description: '第二家店铺 3PL 重定向回调，复用注册分步接口 /api/register/3pl-redirect。',
      },
      {
        key: 'Multi-FP-USD-500K-Increase-second-shop-3pl-redirect-cleanup',
        type: 'api', method: 'POST', kind: 'SQL步骤',
        title: '第二家店铺 移除 TESTOFFER 后缀并更新店铺记录',
        endpoint: '/api/register/remove-test-offer-suffix', operationKey: null,
        payload: { env: '${env}', phone_number: '${phone_number}' },
      },
      {
        ...makePspStartStep('Multi-FP-USD-500K-Increase-second-shop-psp-start'),
        title: '第二家店铺psp-start',
        description: '第二家店铺 PSP started，调用 /api/mock/psp-start；后端按最新 ACTIVE SP 店铺解析 merchantAccountId。',
      },
      {
        ...makePspCompletedStep('Multi-FP-USD-500K-Increase-second-shop-psp-completed'),
        title: '第二家店铺psp-completed',
        description: '第二家店铺 PSP completed，调用 /api/mock/psp-completed；默认承接上一条 psp-start 的 pending 店铺。',
      },
      {
        key: 'Multi-FP-USD-500K-Increase-start-reassessment',
        type: 'api',
        method: 'POST',
        kind: '场景步骤',
        title: '开始额度重新评估',
        endpoint: '/api/mock/restart-reassessment',
        operationKey: null,
        payload: {
          business_context: 'REASSESSMENT',
          currency: 'USD',
          funder_resource: 'FUNDPARK',
        },
        description: '调用 /dpu-merchant/reassessment/start-reassessment，触发额度重新评估。',
      },
      {
        key: 'Multi-FP-USD-500K-Increase-reassessment-underwritten',
        type: 'api',
        method: 'POST',
        kind: '场景步骤',
        title: '提额underwritten',
        endpoint: '/api/mock/underwritten',
        operationKey: null,
        payload: {
          amount: 500000,
          status: 'APPROVED',
          use_latest_submitted_limit_application: true,
        },
        fields: [
          {
            key: 'amount', label: '核保额度', type: 'number', default: 500000,
          },
          {
            key: 'status', label: '核保状态', type: 'select', default: 'APPROVED',
            options: [
              { label: 'APPROVED - 通过', value: 'APPROVED' },
              { label: 'REJECTED - 拒绝', value: 'REJECTED' },
            ],
          },
        ],
        description: '提额重新评估后的核保步骤，调用 /api/mock/underwritten；后端按最新 SUBMITTED dpu_limit_application 填充 dpuLimitApplicationId。',
      },
      {
        key: 'Multi-FP-USD-500K-Increase-submit-additional-documents',
        type: 'api',
        method: 'POST',
        kind: '场景步骤',
        title: '提交额外文档资料',
        endpoint: '/api/mock/fp-submit-additional-documents',
        operationKey: null,
        payload: { currency: 'USD', funder_resource: 'FUNDPARK' },
        description: '提交额度重新评估所需的额外文档资料。',
      },
      {
        key: 'Multi-FP-USD-500K-Increase-submit-additional-business-info',
        type: 'api',
        method: 'POST',
        kind: '场景步骤',
        title: '提交额外公司信息',
        endpoint: '/api/mock/fp-submit-additional-business-info',
        operationKey: null,
        payload: { currency: 'USD', funder_resource: 'FUNDPARK' },
        description: '提交额度重新评估所需的额外公司信息。',
      },
      {
        key: 'Multi-FP-USD-500K-Increase-submit-additional-director-info',
        type: 'api',
        method: 'POST',
        kind: '场景步骤',
        title: '提交额外董事信息',
        endpoint: '/api/mock/fp-submit-additional-director-info',
        operationKey: null,
        payload: { currency: 'USD', funder_resource: 'FUNDPARK' },
        description: '提交额度重新评估所需的额外董事信息。',
      },
      makeIncreaseApprovedOfferStep('Multi-FP-USD-500K-Increase-reassessment-approved-offer', 500000),
      makeIncreaseEsignStep('Multi-FP-USD-500K-Increase-reassessment-esign', 500000),
    ],
  },
  {
    key: 'multiDmf',
    category: 'multiShop',
    code: '100141',
    name: 'DMF多店铺',
    priority: 'P0',
    description: 'DMF 多店铺场景，先迁移单店铺 DMF 前 13 个步骤',
    bootstrap: { env: 'reg', currency: 'USD', funder_resource: 'HSBC', offline: true },
    buildSteps: () => buildDmfMultiShopScenarioSteps(),
  },
  {
    key: 'multiDsCny',
    category: 'multiShop',
    code: '100142',
    name: 'DS-CNY多店铺',
    priority: 'P0',
    description: '照搬单店铺 DS-CNY 全流程，并在提交联系人信息后、开始信用评估前追加第二家店铺（生成 offerId / redirect / 更新3PL店铺数据 / 校验 kiosk seller_id）',
    bootstrap: { env: 'reg', currency: 'CNY', funder_resource: 'DOWSURE', offline: true },
    buildSteps: () => buildDsCnyMultiShopScenarioSteps(),
  },
]

function scenarioStepMetaOverrideKey(scenarioKey, stepKey) {
  return `${scenarioKey || ''}::${stepKey || ''}`
}

function applyScenarioStepMetaOverrides(scenarioKey, steps) {
  return (steps || [])
    .map((step) => {
      const override = scenarioStepMetaOverrides[scenarioStepMetaOverrideKey(scenarioKey, step.key)] || {}
      if (override.is_hidden) return null
      return {
        ...step,
        title: (override.title || '').trim() || step.title,
        description: override.description != null && override.description !== ''
          ? override.description
          : step.description,
      }
    })
    .filter(Boolean)
}

function scenarioStepStructure(scenarioKey, baseSteps) {
  const deleted = new Set(scenarioStepStructureDeleted[scenarioKey] || [])
  const added = scenarioStepStructureDraft[scenarioKey] || []
  return [...baseSteps, ...added].filter((step) => step?.key && !deleted.has(step.key))
}

const interfaceScenarios = computed(() => scenarioBaseDefs.map((def) => {
  const override = scenarioMetaOverrides[def.key] || {}
  return {
    key: def.key,
    category: def.category || 'singleShop',
    code: def.code,
    name: (override.name || '').trim() || def.name,
    priority: def.priority,
    description: override.description != null && override.description !== ''
      ? override.description
      : def.description,
    bootstrap: def.bootstrap,
    steps: scenarioStepStructure(
      def.key,
      applyScenarioStepMetaOverrides(def.key, def.buildSteps()),
    ),
  }
}))

const scenarioDirectoryDefs = [
  { key: 'singleShop', name: '单店铺' },
  { key: 'multiShop', name: '多店铺' },
]

const activeInterfaceScenario = computed(() => (
  interfaceScenarios.value.find((item) => item.key === activeInterfaceScenarioKey.value)
  ?? interfaceScenarios.value[0]
))

// Apply the same draft > persisted > base order precedence used by the main
// step list to every scenario listed in the sidebar tree. Returns a fresh
// step array; scenarios keep their base definition intact.
function orderScenarioSteps(scenario) {
  if (!scenario) return []
  const rawSteps = scenario.steps || []
  const draftOrder = scenarioStepOrderDraft[scenario.key]
  const persistedOrder = scenarioStepOrders[scenario.key]
  const activeOrder = Array.isArray(draftOrder) && draftOrder.length
    ? draftOrder
    : (Array.isArray(persistedOrder) && persistedOrder.length ? persistedOrder : null)
  if (!activeOrder) return rawSteps.slice()
  const byKey = new Map(rawSteps.map((step) => [step.key, step]))
  const seen = new Set()
  const inOrder = []
  for (const key of activeOrder) {
    const step = byKey.get(key)
    if (step && !seen.has(key)) {
      inOrder.push(step)
      seen.add(key)
    }
  }
  for (const step of rawSteps) {
    if (!seen.has(step.key)) inOrder.push(step)
  }
  return inOrder
}

const filteredInterfaceScenarios = computed(() => {
  const keyword = scenarioLibrarySearch.value.trim().toLowerCase()
  const scenariosWithOrder = interfaceScenarios.value.map((scenario) => ({
    ...scenario,
    steps: orderScenarioSteps(scenario),
  }))
  if (!keyword) return scenariosWithOrder
  return scenariosWithOrder
    .map((scenario) => {
      const nameHit = scenario.name.toLowerCase().includes(keyword) || scenario.code?.toLowerCase().includes(keyword)
      const matchedSteps = scenario.steps.filter((step) => step.title?.toLowerCase().includes(keyword) || step.endpoint?.toLowerCase().includes(keyword))
      if (nameHit) return scenario
      if (matchedSteps.length) return { ...scenario, steps: matchedSteps }
      return null
    })
    .filter(Boolean)
})

const filteredInterfaceScenarioGroups = computed(() => {
  const grouped = new Map(scenarioDirectoryDefs.map((item) => [item.key, { ...item, scenarios: [] }]))
  for (const scenario of filteredInterfaceScenarios.value) {
    const category = scenario.category || 'singleShop'
    if (!grouped.has(category)) grouped.set(category, { key: category, name: category, scenarios: [] })
    grouped.get(category).scenarios.push(scenario)
  }
  return Array.from(grouped.values()).filter((group) => group.scenarios.length)
})

const filteredInterfaceScenarioCount = computed(() => (
  filteredInterfaceScenarioGroups.value.reduce((total, group) => total + group.scenarios.length, 0)
))

const interfaceAutomationSteps = computed(() => {
  const scenario = activeInterfaceScenario.value
  const rawSteps = scenario?.steps || []
  // Order precedence: draft > persisted > base. Any step not mentioned in the
  // override list keeps its base position (appended after listed ones).
  const scenarioKey = scenario?.key
  const draftOrder = scenarioKey ? scenarioStepOrderDraft[scenarioKey] : null
  const persistedOrder = scenarioKey ? scenarioStepOrders[scenarioKey] : null
  const activeOrder = Array.isArray(draftOrder) && draftOrder.length
    ? draftOrder
    : (Array.isArray(persistedOrder) && persistedOrder.length ? persistedOrder : null)
  let orderedSteps = rawSteps
  if (activeOrder) {
    const byKey = new Map(rawSteps.map((step) => [step.key, step]))
    const seen = new Set()
    const inOrder = []
    for (const key of activeOrder) {
      const step = byKey.get(key)
      if (step && !seen.has(key)) {
        inOrder.push(step)
        seen.add(key)
      }
    }
    for (const step of rawSteps) {
      if (!seen.has(step.key)) inOrder.push(step)
    }
    orderedSteps = inOrder
  }
  return orderedSteps.map((step, index) => ({
    ...step,
    order: index + 1,
    operation: step.operationKey ? operations.value.find((item) => item.key === step.operationKey) : null,
    enabled: interfaceStepEnabled[step.key] !== false,
  }))
})

const enabledInterfaceStepCount = computed(() => (
  interfaceAutomationSteps.value.filter((step) => step.enabled).length
))

const debugInterfaceSteps = computed(() => {
  const byEndpoint = new Map()
  for (const scenario of interfaceScenarios.value) {
    const orderedSteps = orderScenarioSteps(scenario)
    orderedSteps.forEach((rawStep, index) => {
      const operation = rawStep.operationKey ? operations.value.find((item) => item.key === rawStep.operationKey) : null
      const endpoint = rawStep.endpoint || operation?.endpoint || ''
      if (typeof endpoint !== 'string' || !endpoint.startsWith('/api/')) return
      const method = rawStep.method || operation?.method || 'POST'
      const dedupeKey = `${method.toUpperCase()} ${endpoint}`
      const source = {
        scenarioKey: scenario.key,
        scenarioName: scenario.name,
        stepKey: rawStep.key,
        stepTitle: rawStep.title,
        order: index + 1,
      }
      if (!byEndpoint.has(dedupeKey)) {
        byEndpoint.set(dedupeKey, {
          ...rawStep,
          key: `debug::${dedupeKey}`,
          sourceStepKey: rawStep.key,
          sourceScenarioKey: scenario.key,
          sourceScenarioName: scenario.name,
          sourceStepOrder: index + 1,
          title: rawStep.title || endpoint,
          method,
          endpoint,
          operation,
          enabled: true,
          debugSources: [source],
        })
        return
      }
      const item = byEndpoint.get(dedupeKey)
      item.debugSources.push(source)
    })
  }
  return Array.from(byEndpoint.values())
    .sort((a, b) => a.endpoint.localeCompare(b.endpoint) || a.title.localeCompare(b.title))
    .map((step, index) => ({ ...step, order: index + 1 }))
})

const filteredDebugInterfaceSteps = computed(() => {
  const keyword = debugInterfaceSearch.value.trim().toLowerCase()
  if (!keyword) return debugInterfaceSteps.value
  return debugInterfaceSteps.value.filter((step) => {
    const searchableText = [
      step.title,
      step.endpoint,
      step.method,
      step.sourceStepKey,
      step.sourceScenarioName,
      ...(step.debugSources || []).flatMap((source) => [
        source.scenarioName,
        source.stepTitle,
        source.stepKey,
      ]),
    ]
    return searchableText
      .filter(Boolean)
      .join(' ')
      .toLowerCase()
      .includes(keyword)
  })
})

const selectedInterfaceStep = computed(() => {
  if (interfacePageMode.value === 'debug') {
    return filteredDebugInterfaceSteps.value.find((step) => step.key === activeOperationKey.value)
      ?? filteredDebugInterfaceSteps.value[0]
      ?? null
  }
  return interfaceAutomationSteps.value.find((step) => step.key === activeOperationKey.value)
    ?? interfaceAutomationSteps.value[0]
    ?? null
})

const scenarioTabs = [
  { key: 'base', label: '基本信息' },
  { key: 'params', label: '参数' },
  { key: 'hooks', label: '前/后置' },
  { key: 'assertions', label: '断言' },
  { key: 'history', label: '执行历史' },
  { key: 'settings', label: '设置' },
]

const interfacePageModes = [
  { key: 'debug', label: '调试' },
  { key: 'scenario', label: '场景' },
  { key: 'report', label: '报告' },
]

const scenarioStepEditorTabs = [
  { key: 'params', label: '参数' },
  { key: 'body', label: 'Mock Body' },
  { key: 'headers', label: 'Mock Headers' },
  { key: 'response', label: 'Response' },
  { key: 'actualBody', label: '实际请求体' },
  { key: 'actualHeaders', label: '实际请求头' },
  { key: 'actualResponse', label: '实际响应体' },
  { key: 'logic', label: '底层逻辑' },
]

const debugStepEditorTabs = [
  { key: 'actualHeaders', label: '请求头' },
  { key: 'actualBody', label: '请求体' },
  { key: 'actualQuery', label: 'Query' },
  { key: 'actualResponse', label: '响应体' },
  { key: 'actualResponseHeaders', label: '响应头' },
  { key: 'logic', label: '底层逻辑' },
]

const activeStepEditorTabs = computed(() => (
  interfacePageMode.value === 'debug' ? debugStepEditorTabs : scenarioStepEditorTabs
))

const applicationOptions = computed(() => sessionSummary.value?.applications ?? [])

const selectedApplication = computed(() => (
  applicationOptions.value.find((item) => item.application_unique_id === selectedApplicationUniqueId.value)
  ?? applicationOptions.value[0]
  ?? null
))

const selectedApplicationCurrency = computed(() => (
  selectedApplication.value?.finance_product_currency
  || sessionSummary.value?.finance_product_currency
  || sessionSummary.value?.preferred_currency
  || '-'
))

const hsbcUsdDisabledOperationKeys = new Set([
  'underwritten',
  'dowsureCreditResult',
  'webankCreditResult',
  'dowsureEsignDrawdownResult',
  'dowsureRepaymentResult',
  'dowsureRetryCallback',
  'approvedOffer',
  'pspStart',
  'pspCompleted',
  'esign',
  'drawdown',
  'repaymentStart',
  'repayment',
  'applicationAbandon',
])

const hsbcUsdDisabledReason = '当前申请单为 HSBC USD，通用/DOWSURE 状态流操作不可执行'

const dowsureCnyOnlyOperationKeys = new Set([
  'webankCreditResult',
  'webankDrawdownResult',
  'webankRepaymentResult',
  'cgbCreditResult',
  'cgbLoanResult',
  'cgbRepaymentResult',
])

const dowsureCnyOnlyReason = '该模块仅 DOWSURE CNY 申请单可用'

const dowsureCnyDisabledOperationKeys = new Set([
  'underwritten',
  'approvedOffer',
  'pspStart',
  'pspCompleted',
  'esign',
  'drawdown',
  'repaymentStart',
  'repayment',
  'systemEvent',
  'applicationAbandon',
  'pspHsbcStart',
  'pspHsbcCompleted',
])

const dowsureCnyDisabledReason = '当前申请单为 DOWSURE CNY，通用 FP/HSBC 状态流操作不可执行'

const fundparkUsdDisabledOperationKeys = new Set([
  'dowsureCreditResult',
  'webankCreditResult',
  'dowsureEsignDrawdownResult',
  'dowsureRepaymentResult',
  'dowsureRetryCallback',
  'systemEvent',
  'pspHsbcStart',
  'pspHsbcCompleted',
])

const fundparkUsdDisabledReason = '当前申请单为 FUNDPARK USD，DOWSURE/HSBC/系统事件类操作不可执行'

function normalizeUpper(value) {
  return String(value ?? '').trim().toUpperCase()
}

const selectedApplicationLender = computed(() => {
  const app = selectedApplication.value ?? {}
  const session = sessionSummary.value ?? {}
  return normalizeUpper(
    app.lender_code
    || app.funder_resource
    || app.finance_product
    || app.finance_product_code
    || app.product
    || session.lender_code
    || session.funder_resource
    || session.finance_product
    || registerResult.value?.register_result?.funder_resource
    || registerResult.value?.funder_resource
    || '',
  )
})

const selectedApplicationIsHsbcUsd = computed(() => {
  const currency = normalizeUpper(selectedApplicationCurrency.value)
  const lender = selectedApplicationLender.value
  return currency === 'USD' && lender.includes('HSBC')
})

const selectedApplicationIsDowsureCny = computed(() => {
  const currency = normalizeUpper(selectedApplicationCurrency.value)
  const lender = selectedApplicationLender.value
  return currency === 'CNY' && lender.includes('DOWSURE')
})

const selectedApplicationIsFundparkUsd = computed(() => {
  const currency = normalizeUpper(selectedApplicationCurrency.value)
  const lender = selectedApplicationLender.value
  return currency === 'USD' && (lender.includes('FUNDPARK') || lender.includes('FUND PARK'))
})

function getOperationDisabledState(operation) {
  const key = operation?.key
  if (
    dowsureCnyOnlyOperationKeys.has(key)
    && activeSessionId.value
    && !selectedApplicationIsDowsureCny.value
  ) {
    return { disabled: true, reason: dowsureCnyOnlyReason, chip: 'DOWSURE CNY 专用' }
  }
  if (selectedApplicationIsHsbcUsd.value && hsbcUsdDisabledOperationKeys.has(key)) {
    return { disabled: true, reason: hsbcUsdDisabledReason, chip: 'HSBC USD 禁用' }
  }
  if (selectedApplicationIsDowsureCny.value && dowsureCnyDisabledOperationKeys.has(key)) {
    return { disabled: true, reason: dowsureCnyDisabledReason, chip: 'DOWSURE CNY 禁用' }
  }
  if (selectedApplicationIsFundparkUsd.value && fundparkUsdDisabledOperationKeys.has(key)) {
    return { disabled: true, reason: fundparkUsdDisabledReason, chip: 'FUNDPARK USD 禁用' }
  }
  return { disabled: false, reason: '', chip: '' }
}

function isOperationDisabled(operation) {
  return getOperationDisabledState(operation).disabled
}

function operationDisabledReason(operation) {
  return getOperationDisabledState(operation).reason
}

function operationDisabledChip(operation) {
  return getOperationDisabledState(operation).chip
}

const shouldShowPspAuthorizationRows = computed(() => (
  ['pspStart', 'pspCompleted', 'pspHsbcStart', 'pspHsbcCompleted'].includes(activeOperation.value?.key)
))

const shouldShowLimitApplications = computed(() => (
  activeOperation.value?.key === 'underwritten'
))

const shouldShowDrawdownRepaymentRows = computed(() => (
  ['repaymentStart', 'repayment', 'dowsureRepaymentResult', 'webankRepaymentResult', 'cgbRepaymentResult'].includes(activeOperation.value?.key)
))

const shouldShowDowsureMerchantAccounts = computed(() => (
  activeOperation.value?.key === 'dowsureCreditResult'
))

const shouldShowWebankSellerOffers = computed(() => (
  activeOperation.value?.key === 'webankCreditResult'
))

const applicationCodeOperationKeys = [
  'dowsureCreditResult',
  'dowsureEsignDrawdownResult',
  'dowsureRepaymentResult',
  'dowsureRetryCallback',
  'webankCreditResult',
  'webankDrawdownResult',
  'webankRepaymentResult',
  'cgbCreditResult',
  'cgbLoanResult',
  'cgbRepaymentResult',
]

const shouldLoadApplicationCodes = computed(() => (
  applicationCodeOperationKeys.includes(activeOperation.value?.key)
))

const consoleStatusCards = computed(() => [
  {
    label: 'API',
    value: health.value === 'ok' ? '正常' : '异常',
    detail: health.value === 'ok' ? 'health check passed' : String(health.value || 'checking'),
    tone: health.value === 'ok' ? 'success' : 'error',
  },
  {
    label: 'Session',
    value: activeSessionId.value ? '已连接' : '未连接',
    detail: activeSessionId.value ? activeSessionId.value : '先连接 session 再执行 mock',
    tone: activeSessionId.value ? 'success' : 'warning',
  },
  {
    label: 'Env',
    value: sessionSummary.value?.env || connectionForm.env,
    detail: sessionSummary.value?.phone_number || '当前选择环境',
    tone: 'info',
  },
  {
    label: 'Logs',
    value: wsConnected.value ? '实时' : '未连接',
    detail: wsError.value || String(eventLogs.value.length) + ' 条缓存日志',
    tone: wsConnected.value ? 'success' : 'warning',
  },
])

const logStatusText = computed(() => {
  if (!activeSessionId.value) return '未连接会话'
  if (wsConnected.value) return '实时日志已连接'
  if (wsError.value) return '日志连接异常: ' + wsError.value
  return '日志连接中'
})

const isLogPreviewMode = computed(() => {
  const [startTime, endTime] = logSearchForm.timeRange || []
  return !logSearchForm.keyword?.trim() && !startTime && !endTime
})

const registerStatusMessage = computed(() => {
  if (!registerResult.value) return ''
  return registerAutoConnected.value
    ? '已自动连接到新注册账号，可以直接执行 mock 操作。'
    : '注册已完成，但还没有可用会话，请点击连接 session 继续。'
})

const operations = computed(() => [
  { key: 'multiShopBinding', title: '多店铺 SP 绑定', icon: Link, endpoint: '/api/mock/multi-shop-binding', description: '输入 state，获取 SP 授权 URL；可选填 Platform Seller ID。', fields: [
    { prop: 'state', label: 'State', type: 'text', placeholder: '请输入 state' },
    { prop: 'platform_seller_id', label: 'Platform Seller ID', type: 'text', placeholder: '可为空，默认自动生成' },
  ] },
  { key: 'spStatusUpdate', title: 'SP 状态更新', icon: Cpu, endpoint: '/api/mock/sp-status-update', description: '更新 SP 状态。', fields: [
    { prop: 'platform_seller_id', label: 'Platform Seller ID', type: 'text', placeholder: '可为空，默认使用当前 session' },
    { prop: 'status', label: '状态', type: 'select', options: ['SUCCESS', 'FAIL'] },
    { prop: 'failure_reason_index', label: '失败原因', type: 'select', options: spFailureOptions.value.map((item) => ({ label: item.label, value: item.index })), visible: (form) => form.status === 'FAIL' },
  ] },
  { key: 'multiShop3plRedirect', title: '多店铺 3PL Redirect', icon: Link, endpoint: '/api/mock/multi-shop-3pl-redirect', description: '生成 3PL 跳转 URL。', fields: [] },
  { key: 'linkSp3pl', title: 'SP-3PL 关联', icon: Link, endpoint: '/api/mock/link-sp-3pl', description: '根据当前会话手机号触发 SP 与 3PL 店铺关联。', fields: [] },
  { key: 'underwritten', title: '核保', icon: Document, endpoint: '/api/mock/underwritten', description: '提交核保额度和状态。', fields: [
    { prop: 'amount', label: '核保额度', type: 'number', min: 1, step: 1000 },
    { prop: 'status', label: '状态', type: 'select', options: enumOptions.value?.underwritten_statuses ?? [] },
  ] },
  { key: 'dowsureCreditResult', title: '授信结果 CCB', icon: Check, endpoint: '/api/mock/dowsure-credit-result', description: '发送 CCB credit-result，包含原核保店铺额度列表；applicationCode 从数据库带出，默认最新一条。', fields: [
    { prop: 'applicationCode', label: 'Application Code', type: 'select', options: applicationCodeOptions.value },
    { prop: 'amount', label: '授信金额', type: 'number', min: 0, step: 1000 },
    { prop: 'processingFee', label: 'Processing Fee', type: 'number', min: 0, step: 100 },
  ] },
  { key: 'dowsureEsignDrawdownResult', title: '支用结果 CCB', icon: Promotion, endpoint: '/api/mock/dowsure-esign-drawdown-result', description: '发送 CCB loan 结果。', fields: [
    { prop: 'application_code', label: 'Application Code', type: 'select', options: applicationCodeOptions.value },
    { prop: 'credit_contract_no', label: 'Credit Contract No', type: 'text', placeholder: '可为空，默认使用授信结果' },
    { prop: 'amount', label: '放款金额', type: 'number', min: 0.01, step: 1000 },
    { prop: 'processing_fee', label: 'Processing Fee', type: 'number', min: 0, step: 100 },
  ] },
  { key: 'dowsureRepaymentResult', title: '还款结果 CCB', icon: Refresh, endpoint: '/api/mock/dowsure-repayment-result', description: '发送 CCB repayment 结果。', fields: [
    { prop: 'application_code', label: 'Application Code', type: 'select', options: applicationCodeOptions.value },
    { prop: 'payment_principal', label: 'Payment Principal', type: 'number', min: 0, step: 100 },
    { prop: 'payment_overdue_interest', label: 'Overdue Interest', type: 'number', min: 0, step: 100 },
  ] },
  { key: 'dowsureRetryCallback', title: '重试请求 CCB', icon: Refresh, endpoint: '/api/mock/dowsure-retry-callback', description: '调用 CCB callback retry，limit=100；Application Code 仅用于当前申请单反显。', fields: [
    { prop: 'application_code', label: 'Application Code', type: 'select', options: applicationCodeOptions.value },
  ] },
  { key: 'webankCreditResult', title: '授信结果 WEBANK', icon: Check, endpoint: '/api/mock/webank-credit-result', description: '输入 businessSum，并按店铺输入 applySellerBusinessSum；applicationCode 从数据库带出，默认最新一条。', fields: [
    { prop: 'application_code', label: 'Application Code', type: 'select', options: applicationCodeOptions.value },
    { prop: 'businessSum', label: 'businessSum', type: 'number', min: 0, step: 1000 },
  ] },
  { key: 'cgbCreditResult', title: '授信结果 CGB', icon: Check, endpoint: '/api/mock/cgb-credit-result', description: '按当前 Session 手机号查询 applicationCode（默认最新一条，可切换），自动拼接 creditCode 和 creditContractNo；creditStatus 由前端输入。', fields: [
    { prop: 'application_code', label: 'Application Code', type: 'select', options: applicationCodeOptions.value },
    { prop: 'creditStatus', label: 'creditStatus', type: 'select', options: ['APPROVE', 'REJECT'] },
    { prop: 'amount', label: '授信金额 amount', type: 'number', min: 0, step: 1000 },
    { prop: 'processingFee', label: 'Processing Fee', type: 'number', min: 0, step: 100 },
  ] },
  { key: 'cgbLoanResult', title: '支用回传 CGB', icon: Promotion, endpoint: '/api/mock/cgb-loan-result', description: '按当前 Session 手机号查询 applicationCode，并自动生成 CGB loanCode 与 loanContractNo。', fields: [
    { prop: 'application_code', label: 'Application Code', type: 'select', options: applicationCodeOptions.value },
    { prop: 'amount', label: '支用金额 amount', type: 'number', min: 0, step: 1000 },
    { prop: 'processingFee', label: 'Processing Fee', type: 'number', min: 0, step: 100 },
  ] },
  { key: 'cgbRepaymentResult', title: '还款结果 CGB', icon: Refresh, endpoint: '/api/mock/cgb-repayment-result', description: '按当前手机号、DPU 放款记录和 DOWSURE t_loan 组装 CGB 还款回传；还款本金、利息和逾期利息由前端输入。', fields: [
    { prop: 'application_code', label: 'Application Code', type: 'select', options: applicationCodeOptions.value },
    { prop: 'payment_principal', label: 'paymentPrincipal', type: 'number', min: 0, step: 0.01 },
    { prop: 'payment_interest', label: 'paymentInterest', type: 'number', min: 0, step: 0.01 },
    { prop: 'payment_overdue_interest', label: 'paymentOverdueInterest', type: 'number', min: 0, step: 0.01 },
  ] },
  { key: 'webankDrawdownResult', title: '支用结果 WEBANK', icon: Promotion, endpoint: '/api/mock/webank-drawdown-result', description: '输入 loanAmount 与 serviceFee.amount，系统从数据库反查 loanCode 后发送 WEBANK loan-result。', fields: [
    { prop: 'application_code', label: 'Application Code', type: 'select', options: applicationCodeOptions.value },
    { prop: 'loan_amount', label: '支用金额', type: 'number', min: 0, step: 1000 },
    { prop: 'service_fee_amount', label: 'serviceFee.amount', type: 'number', min: 0, step: 100 },
  ] },
  { key: 'webankRepaymentResult', title: '还款结果 WEBANK', icon: Refresh, endpoint: '/api/mock/webank-repayment-result', description: '选择还款单并输入还款金额，remainPrincipalAmount 自动按 outstanding_amount - paymentPrincipal 计算。', fields: [
    { prop: 'application_code', label: 'Application Code', type: 'select', options: applicationCodeOptions.value },
    { prop: 'payment_principal', label: 'paymentPrincipal', type: 'number', min: 0, step: 1000 },
    { prop: 'payment_interest', label: 'paymentInterest', type: 'number', min: 0, step: 1000 },
    { prop: 'payment_penalty_interest', label: 'paymentPenaltyInterest', type: 'number', min: 0, step: 1000 },
  ] },
  { key: 'approvedOffer', title: '审批', icon: Check, endpoint: '/api/mock/approved-offer', description: '发送审批额度、状态和原因。', fields: [
    { prop: 'amount', label: '审批金额', type: 'number', min: 1, step: 1000 },
    { prop: 'status', label: '状态', type: 'select', options: enumOptions.value?.approved_offer_statuses ?? [] },
    { prop: 'failure_reason_index', label: '退回原因', type: 'select', options: reasonOptions.value.map((item) => ({ label: item.label, value: item.index })), visible: (form) => form.status === 'RETURNED' },
    { prop: 'rejection_reason', label: '拒绝原因', type: 'select', options: approvedRejectionOptions.value.map((item) => ({ label: item.label, value: item.value })), visible: (form) => form.status === 'REJECTED' },
  ] },
  { key: 'pspStart', title: 'PSP 开始', icon: Promotion, endpoint: '/api/mock/psp-start', description: '发送 PSP started 状态。', fields: [{ prop: 'status', label: '状态', type: 'select', options: enumOptions.value?.psp_start_statuses ?? [] }] },
  { key: 'pspCompleted', title: 'PSP 完成', icon: Check, endpoint: '/api/mock/psp-completed', description: '发送 PSP completed 状态。', fields: [{ prop: 'status', label: '状态', type: 'select', options: enumOptions.value?.psp_completed_statuses ?? [] }] },
  { key: 'esign', title: '电子签', icon: Document, endpoint: '/api/mock/esign', description: '发送签约金额和签约结果。', fields: [
    { prop: 'signed_amount', label: '签约金额', type: 'number', min: 1, step: 1000 },
    { prop: 'status', label: '状态', type: 'select', options: enumOptions.value?.esign_statuses ?? [] },
  ] },
  { key: 'drawdown', title: '放款', icon: Promotion, endpoint: '/api/mock/drawdown', description: '提交放款金额、状态和失败原因。', fields: [
    { prop: 'amount', label: '放款金额', type: 'number', min: 0.01, step: 1000 },
    { prop: 'status', label: '状态', type: 'select', options: enumOptions.value?.drawdown_statuses ?? [] },
    { prop: 'failure_reason_index', label: '失败原因', type: 'select', options: drawdownReasonOptions.value.map((item) => ({ label: `${item.code} ${item.label}`, value: item.index })), visible: (form) => form.status === 'REJECTED' },
  ] },
  { key: 'repaymentStart', title: '还款开始', icon: Refresh, endpoint: '/api/mock/repayment-start', description: '发送还款开始通知。', fields: [
    { prop: 'principal_amount', label: '本金', type: 'number', min: 0.01, step: 100 },
  ] },
  { key: 'repayment', title: '还款结果', icon: Refresh, endpoint: '/api/mock/repayment', description: '发送还款结果和失败原因。', fields: [
    { prop: 'principal_amount', label: '本金', type: 'number', min: 0.01, step: 100 },
    { prop: 'status', label: '状态', type: 'select', options: enumOptions.value?.repayment_statuses ?? [] },
    { prop: 'failure_reason_index', label: '失败原因', type: 'select', options: repaymentReasonOptions.value.map((item) => ({ label: `${item.code} ${item.label}`, value: item.index })), visible: (form) => form.status === 'Failure' },
  ] },
  { key: 'systemEvent', title: '系统事件通知', icon: Monitor, endpoint: '/api/mock/system-event', description: '发送 system events 通知。', fields: [
    { prop: 'event_type', label: '事件类型', type: 'select', options: enumOptions.value?.system_event_types ?? [] },
    { prop: 'error_code', label: '错误码', type: 'select', options: ['B-6003', 'B-6005'], visible: (form) => form.event_type === 'EXCEPTION-APPLICATION-CREATION' },
  ] },
  { key: 'applicationAbandon', title: 'Abandon', icon: Monitor, endpoint: '/api/mock/application-abandon', description: '发送 application.status Abandoned 通知。', fields: [
    { prop: 'abandon_reason', label: 'Abandon Reason', type: 'select', options: applicationAbandonOptions.value.map((item) => ({ label: item.label, value: item.value })) },
  ] },
  { key: 'pspHsbcStart', title: 'PSP 开始 HSBC', icon: Promotion, endpoint: '/api/mock/psp-hsbc-start', description: '发送 HSBC PSP started 通知。', fields: [] },
  { key: 'pspHsbcCompleted', title: 'PSP 完成 HSBC', icon: Check, endpoint: '/api/mock/psp-hsbc-completed', description: '发送 HSBC PSP completed 通知。', fields: [{ prop: 'result', label: '结果', type: 'select', options: ['SUCCESS', 'FAIL'] }] },
])

function isOperationVisible(operation) {
  return true
}

function orderMockOperations(items) {
  const configuredOrder = mockOperationEditMode.value
    ? scenarioStepOrderDraft.mockOperations || scenarioStepOrders.mockOperations
    : scenarioStepOrders.mockOperations
  if (!Array.isArray(configuredOrder) || !configuredOrder.length) return items
  const byKey = new Map(items.map((item) => [item.key, item]))
  const seen = new Set()
  const ordered = []
  for (const key of configuredOrder) {
    const item = byKey.get(key)
    if (item && !seen.has(key)) {
      ordered.push(item)
      seen.add(key)
    }
  }
  for (const item of items) {
    if (!seen.has(item.key)) ordered.push(item)
  }
  return ordered
}

const visibleOperations = computed(() => orderMockOperations(operations.value.filter(isOperationVisible)))

watch(
  visibleOperations,
  (items) => {
    if (currentView.value === 'interfaceTest') return
    if (activeOperationKey.value && !items.some((operation) => operation.key === activeOperationKey.value)) {
      activeOperationKey.value = ''
    }
  },
)

function buildDmfScenarioSteps() {
  // DMF: HSBC + USD 线下注册场景。前 8 步走拆分版 /api/register/*，每步独立接口、
  // 独立响应；控制台“注册并完成绑店”按钮仍然走老的 /api/register-and-run-multishop。
  return [
    ...buildRegisterStepGroup({
      prefix: 'DMF',
      journey: '500K',
      currency: 'USD',
      funderResource: 'HSBC',
      offline: true,
    }),
    {
      key: 'DMF-application',
      type: 'api',
      method: 'POST',
      kind: '自定义请求',
      title: '创建申请单',
      endpoint: '/api/mock/create-application-context',
      operationKey: null,
      payload: {
        journey: '500K',
        currency: 'USD',
        funder_resource: 'HSBC',
      },
    },
    {
      key: 'DMF-business-info',
      type: 'api',
      method: 'POST',
      kind: '自定义请求',
      title: '邓白氏提交企业信息 (HSBC USD)',
      endpoint: '/api/mock/fp-business-profile',
      operationKey: null,
      payload: {
        journey: '500K',
        currency: 'USD',
        funder_resource: 'HSBC',
      },
    },
    {
      key: 'DMF-registration-documents',
      type: 'api',
      method: 'POST',
      kind: '自定义请求',
      title: '上传邓白氏企业资料',
      endpoint: '/api/mock/fp-registration-documents',
      operationKey: null,
      payload: {
        journey: '500K',
        currency: 'USD',
        funder_resource: 'HSBC',
      },
    },
    {
      key: 'DMF-director-info',
      type: 'api',
      method: 'POST',
      kind: '自定义请求',
      title: '提交邓白氏法人资料',
      endpoint: '/api/mock/fp-director-info',
      operationKey: null,
      payload: {
        journey: '500K',
        currency: 'USD',
        funder_resource: 'HSBC',
      },
    },
    {
      key: 'DMF-contact-information',
      type: 'api',
      method: 'POST',
      kind: '自定义请求',
      title: '提交联系人信息',
      endpoint: '/api/mock/fp-add-contact-information',
      operationKey: null,
      payload: {
        journey: '500K',
        currency: 'USD',
        funder_resource: 'HSBC',
      },
    },
    {
      key: 'DMF-start-reassessment',
      type: 'api',
      method: 'POST',
      kind: '自定义请求',
      title: '开始额度评估',
      endpoint: '/api/mock/hsbc-start-reassessment',
      operationKey: null,
      payload: {
        journey: '500K',
        currency: 'USD',
        funder_resource: 'HSBC',
      },
    },
    {
      key: 'DMF-link-sp-3pl-shops',
      type: 'api',
      method: 'POST',
      kind: '自定义请求',
      title: '关联SP和3PL店铺',
      endpoint: '/api/mock/fp-link-sp-3pl-shops',
      operationKey: null,
      payload: { journey: '500K' },
      description: 'DMF 开始额度评估后关联 SP 和 3PL 店铺。',
    },
    {
      key: 'DMF-poll-application-ready',
      type: 'api',
      method: 'POST',
      kind: '自定义请求',
      title: '轮询申请单状态',
      endpoint: '/api/mock/dmf-poll-application-ready',
      operationKey: null,
      payload: {
        journey: '500K',
        currency: 'USD',
        funder_resource: 'HSBC',
      },
    },
    {
      key: 'DMF-indicative-offer',
      type: 'api',
      method: 'POST',
      kind: '自定义请求',
      title: '获取 HSBC offer',
      endpoint: '/api/mock/system-event',
      operationKey: null,
      payload: {
        event_type: 'INDICATIVE-OFFER',
      },
      fields: [
        {
          key: 'event_type', label: '事件类型', type: 'select', default: 'INDICATIVE-OFFER',
          options: [
            { label: 'INDICATIVE-OFFER - 下发额度', value: 'INDICATIVE-OFFER' },
            { label: 'EXCEPTION-APPLICATION-CREATION - 申请单异常', value: 'EXCEPTION-APPLICATION-CREATION' },
            { label: 'IN-PROCESS - 处理中', value: 'IN-PROCESS' },
            { label: 'ERROR - 错误', value: 'ERROR' },
            { label: 'ETB-customer - ETB 客户', value: 'ETB-customer' },
          ],
        },
        {
          key: 'error_code', label: '错误码', type: 'select', default: 'B-6003',
          visibleWhen: (form) => form?.event_type === 'EXCEPTION-APPLICATION-CREATION',
          options: [
            { label: 'B-6003', value: 'B-6003' },
            { label: 'B-6005', value: 'B-6005' },
          ],
        },
      ],
    },
    {
      key: 'DMF-activate-offer',
      type: 'api',
      method: 'POST',
      kind: '自定义请求',
      title: '激活offer',
      endpoint: '/api/mock/fp-activate-offer',
      operationKey: null,
      payload: {
        currency: 'USD',
        funder_resource: 'HSBC',
      },
      description: 'DMF 获取 HSBC offer 后激活 offer，上游调用 /dpu-merchant/credit-offer/activate-offer，body 为 {}。',
    },
    {
      key: 'DMF-boss-application-status',
      type: 'api',
      method: 'POST',
      kind: '自定义请求',
      title: 'BOSS审批申请单状态',
      endpoint: '/api/mock/boss-application-status',
      operationKey: null,
      payload: {
        currency: 'USD',
        funder_resource: 'HSBC',
        approved_date: '2026-06-01',
        approved_limit: '10000.00',
        interest_type: 'Float',
        rate: '3.0',
        tenor: 120,
        application_status: 'APPROVED',
        update_by: 'boss',
        psp_status: 'Init',
        psp_aggregate_status: 'NORMAL',
        event_type: 'NTB-customer',
      },
      fields: makeBossApplicationStatusFields(),
      description: '按 merchant_id 查询最新 dpu_application，并用最新 application_unique_id 调用 handleBossApplicationStatus。',
    },
    makeCompleteAllHsbcPspStep('DMF-complete-all-psp-bindings'),
  ]
}

function makeCompleteAllHsbcPspStep(key) {
  return {
    key,
    type: 'api',
    method: 'POST',
    kind: '自定义请求',
    title: '完成所有店铺的PSP绑定',
    endpoint: '/api/mock/psp-hsbc-complete-all',
    operationKey: null,
    payload: {
      result: 'SUCCESS',
      max_iterations: 20,
    },
    description: '循环查询 dpu_merchant_account_limit 中 psp_status=INITIAL 的店铺，按 merchant_account_id 查 ACTIVE SP authorization_id，并依次调用 psp-hsbc-start / psp-hsbc-completed，直到没有 INITIAL 记录。',
  }
}

function makeBossApplicationStatusFields() {
  return [
    { key: 'approved_limit', label: '审批额度', type: 'text', default: '10000.00' },
    {
      key: 'interest_type',
      label: '计息类型',
      type: 'select',
      default: 'Float',
      options: [
        { label: 'Fixed', value: 'Fixed' },
        { label: 'Float', value: 'Float' },
      ],
    },
    { key: 'rate', label: '利率', type: 'text', default: '3.0' },
    { key: 'tenor', label: '期限', type: 'number', default: 120 },
    {
      key: 'application_status',
      label: '申请单状态',
      type: 'select',
      default: 'APPROVED',
      options: [
        { label: 'APPROVED - 通过', value: 'APPROVED' },
        { label: 'REJECTED - 拒绝', value: 'REJECTED' },
      ],
    },
    {
      key: 'psp_status',
      label: 'PSP 状态',
      type: 'select',
      default: 'Init',
      options: [
        { label: 'NotStart', value: 'NotStart' },
        { label: 'Init', value: 'Init' },
        { label: 'Locked', value: 'Locked' },
      ],
    },
    {
      key: 'psp_aggregate_status',
      label: 'PSP 聚合状态',
      type: 'select',
      default: 'NORMAL',
      options: [
        { label: 'NORMAL', value: 'NORMAL' },
        { label: 'FROZEN', value: 'FROZEN' },
        { label: 'DEDUCTION', value: 'DEDUCTION' },
      ],
    },
    {
      key: 'event_type',
      label: '事件类型',
      type: 'select',
      default: 'NTB-customer',
      options: [
        { label: 'NTB-customer', value: 'NTB-customer' },
        { label: 'ETB-customer', value: 'ETB-customer' },
      ],
    },
  ]
}

function buildDmfMultiShopScenarioSteps() {
  const baseSteps = buildDmfScenarioSteps()
    .slice(0, 13)
    .map((step) => ({
      ...step,
      key: String(step.key || '').replace(/^DMF-/, 'Multi-DMF-'),
    }))
  return [
    ...baseSteps,
    {
      key: 'Multi-DMF-second-shop-state',
      type: 'api',
      method: 'POST',
      kind: '场景步骤',
      title: '第二家店铺生成 state 并申请 SP 授权 URL',
      endpoint: '/api/register/sp-auth-url',
      operationKey: null,
      payload: {
        env: '${env}',
        phone_number: '${phone_number}',
        token: '${token}',
        currency: 'USD',
        funder_resource: 'HSBC',
        offline: true,
      },
      description: 'DMF 第二家店铺 SP 授权 URL 生成步骤，复用注册分步接口 /api/register/sp-auth-url。',
    },
    {
      key: 'Multi-DMF-second-shop-sp-auth',
      type: 'api',
      method: 'POST',
      kind: '场景步骤',
      title: '查询 SP auth-result 并回调 Amazon SP auth',
      endpoint: '/api/register/sp-auth-callback',
      operationKey: null,
      payload: {
        env: '${env}',
        phone_number: '${phone_number}',
        token: '${token}',
        state: '${state}',
        selling_partner_id: '${selling_partner_id}',
        currency: 'USD',
        funder_resource: 'HSBC',
      },
      description: '查询 DMF 第二家店铺 SP auth-result，并回调 Amazon SP auth。',
    },
    {
      key: 'Multi-DMF-second-shop-3pl-redirect',
      type: 'api',
      method: 'POST',
      kind: '场景步骤',
      title: '3PL 重定向回调 (amazon/redirect + POST)',
      endpoint: '/api/register/3pl-redirect',
      operationKey: null,
      payload: {
        env: '${env}',
        phone_number: '${phone_number}',
      },
      description: 'DMF 第二家店铺 3PL 重定向回调，复用注册分步接口 /api/register/3pl-redirect。',
    },
    {
      key: 'Multi-DMF-second-shop-3pl-redirect-cleanup',
      type: 'api', method: 'POST', kind: 'SQL步骤',
      title: '第二家店铺 移除 TESTOFFER 后缀并更新店铺记录',
      endpoint: '/api/register/remove-test-offer-suffix', operationKey: null,
      payload: { env: '${env}', phone_number: '${phone_number}' },
    },
    {
      key: 'Multi-DMF-start-reassessment',
      type: 'api',
      method: 'POST',
      kind: '自定义请求',
      title: '开始额度评估',
      endpoint: '/api/mock/hsbc-start-reassessment',
      operationKey: null,
      payload: {
        journey: '500K',
        currency: 'USD',
        funder_resource: 'HSBC',
      },
      description: 'DMF 多店铺开始额度评估，调用 /api/mock/hsbc-start-reassessment。',
    },
    {
      key: 'Multi-DMF-link-sp-3pl-shops',
      type: 'api',
      method: 'POST',
      kind: '自定义请求',
      title: '关联SP和3PL店铺',
      endpoint: '/api/mock/fp-link-sp-3pl-shops',
      operationKey: null,
      payload: { journey: '500K' },
      description: 'DMF 多店铺开始额度评估后关联 SP 和 3PL 店铺。',
    },
    {
      key: 'Multi-DMF-poll-application-ready',
      type: 'api',
      method: 'POST',
      kind: '自定义请求',
      title: '轮询申请单状态',
      endpoint: '/api/mock/dmf-poll-application-ready',
      operationKey: null,
      payload: {
        journey: '500K',
        currency: 'USD',
        funder_resource: 'HSBC',
      },
      description: 'DMF 多店铺轮询申请单状态，等待 HSBC 申请单及店铺数据传输就绪。',
    },
    {
      key: 'Multi-DMF-indicative-offer',
      type: 'api',
      method: 'POST',
      kind: '自定义请求',
      title: '获取 HSBC offer',
      endpoint: '/api/mock/system-event',
      operationKey: null,
      payload: {
        event_type: 'INDICATIVE-OFFER',
      },
      fields: [
        {
          key: 'event_type', label: '事件类型', type: 'select', default: 'INDICATIVE-OFFER',
          options: [
            { label: 'INDICATIVE-OFFER - 下发额度', value: 'INDICATIVE-OFFER' },
            { label: 'EXCEPTION-APPLICATION-CREATION - 申请单异常', value: 'EXCEPTION-APPLICATION-CREATION' },
            { label: 'IN-PROCESS - 处理中', value: 'IN-PROCESS' },
            { label: 'ERROR - 错误', value: 'ERROR' },
            { label: 'ETB-customer - ETB 客户', value: 'ETB-customer' },
          ],
        },
      ],
      description: 'DMF 多店铺触发 HSBC system-event 获取 indicative offer。',
    },
    {
      key: 'Multi-DMF-third-shop-state',
      type: 'api',
      method: 'POST',
      kind: '场景步骤',
      title: '第三家店铺生成 state 并申请 SP 授权 URL',
      endpoint: '/api/register/sp-auth-url',
      operationKey: null,
      payload: {
        env: '${env}',
        phone_number: '${phone_number}',
        token: '${token}',
        currency: 'USD',
        funder_resource: 'HSBC',
        offline: true,
      },
      description: 'DMF 第三家店铺 SP 授权 URL 生成步骤，复用注册分步接口 /api/register/sp-auth-url。',
    },
    {
      key: 'Multi-DMF-third-shop-sp-auth',
      type: 'api',
      method: 'POST',
      kind: '场景步骤',
      title: '查询 SP auth-result 并回调 Amazon SP auth',
      endpoint: '/api/register/sp-auth-callback',
      operationKey: null,
      payload: {
        env: '${env}',
        phone_number: '${phone_number}',
        token: '${token}',
        state: '${state}',
        selling_partner_id: '${selling_partner_id}',
        currency: 'USD',
        funder_resource: 'HSBC',
      },
      description: '查询 DMF 第三家店铺 SP auth-result，并回调 Amazon SP auth。',
    },
    {
      key: 'Multi-DMF-third-shop-3pl-redirect',
      type: 'api',
      method: 'POST',
      kind: '场景步骤',
      title: '3PL 重定向回调 (amazon/redirect + POST)',
      endpoint: '/api/register/3pl-redirect',
      operationKey: null,
      payload: {
        env: '${env}',
        phone_number: '${phone_number}',
      },
      description: 'DMF 第三家店铺 3PL 重定向回调，复用注册分步接口 /api/register/3pl-redirect。',
    },
    {
      key: 'Multi-DMF-third-shop-3pl-redirect-cleanup',
      type: 'api', method: 'POST', kind: 'SQL步骤',
      title: '第三家店铺 移除 TESTOFFER 后缀并更新店铺记录',
      endpoint: '/api/register/remove-test-offer-suffix', operationKey: null,
      payload: { env: '${env}', phone_number: '${phone_number}' },
    },
    {
      key: 'Multi-DMF-increase-start-reassessment',
      type: 'api',
      method: 'POST',
      kind: '场景步骤',
      title: '开始提额额度评估',
      endpoint: '/api/mock/restart-reassessment',
      operationKey: null,
      payload: {
        business_context: 'REASSESSMENT',
        currency: 'USD',
        funder_resource: 'HSBC',
      },
      description: 'DMF 第三家店铺绑定后触发提额额度评估，上游 body 为 {"businessContext":"REASSESSMENT"}。',
    },
    {
      key: 'Multi-DMF-increase-poll-new-application-ready',
      type: 'api',
      method: 'POST',
      kind: '场景步骤',
      title: '轮询新申请单状态',
      endpoint: '/api/mock/dmf-poll-application-ready',
      operationKey: null,
      payload: {
        journey: '500K',
        currency: 'USD',
        funder_resource: 'HSBC',
        use_latest_submitted_application: true,
      },
      description: '提额后按 merchant_id 查询最新 SUBMITTED 申请单，再用新的 application_unique_id 轮询后续状态。',
    },
    {
      key: 'Multi-DMF-increase-indicative-offer',
      type: 'api',
      method: 'POST',
      kind: '场景步骤',
      title: '重新获取 HSBC offer',
      endpoint: '/api/mock/system-event',
      operationKey: null,
      payload: {
        event_type: 'INDICATIVE-OFFER',
        application_unique_id: '${application_unique_id}',
      },
      fields: [
        {
          key: 'event_type', label: '事件类型', type: 'select', default: 'INDICATIVE-OFFER',
          options: [
            { label: 'INDICATIVE-OFFER - 下发额度', value: 'INDICATIVE-OFFER' },
            { label: 'EXCEPTION-APPLICATION-CREATION - 申请单异常', value: 'EXCEPTION-APPLICATION-CREATION' },
            { label: 'IN-PROCESS - 处理中', value: 'IN-PROCESS' },
            { label: 'ERROR - 错误', value: 'ERROR' },
            { label: 'ETB-customer - ETB 客户', value: 'ETB-customer' },
          ],
        },
      ],
      description: '使用第 25 步选中的新 application_unique_id 查询新的 applicationId，并重新触发 HSBC indicative offer。',
    },
    {
      key: 'Multi-DMF-increase-activate-offer',
      type: 'api',
      method: 'POST',
      kind: '场景步骤',
      title: '激活offer',
      endpoint: '/api/mock/fp-activate-offer',
      operationKey: null,
      payload: {
        currency: 'USD',
        funder_resource: 'HSBC',
        application_unique_id: '${application_unique_id}',
      },
      description: 'DMF 多店铺提额重新获取 HSBC offer 后，使用新的 application_unique_id 激活 offer，上游 body 为 {}。',
    },
    {
      key: 'Multi-DMF-increase-boss-application-status',
      type: 'api',
      method: 'POST',
      kind: '场景步骤',
      title: 'BOSS审批申请单状态',
      endpoint: '/api/mock/boss-application-status',
      operationKey: null,
      payload: {
        currency: 'USD',
        funder_resource: 'HSBC',
        approved_date: '2026-06-01',
        approved_limit: '10000.00',
        interest_type: 'Float',
        rate: '3.0',
        tenor: 120,
        application_status: 'APPROVED',
        update_by: 'boss',
        psp_status: 'Init',
        psp_aggregate_status: 'NORMAL',
        event_type: 'NTB-customer',
      },
      fields: makeBossApplicationStatusFields(),
      description: '按 merchant_id 查询最新 dpu_application，并用最新 application_unique_id 调用 handleBossApplicationStatus。',
    },
    makeCompleteAllHsbcPspStep('Multi-DMF-complete-all-psp-bindings'),
  ]
}

// Produce the 8 stateless /api/register/* steps for a scenario. Each step
// reads what it needs from the previous step's response via scenarioVariables
// (see resolveScenarioPayload + the harvest loop in handleScenarioStepRun).
//
// Titles are tuned per online/offline mode: the online flow additionally
// creates an offer_id and hits amazon/redirect twice inside the send-sms /
// signup adapter methods; we surface that in the step title so users can tell
// what's actually going on without having to read the request/response tabs.
function buildRegisterStepGroup({
  prefix, journey, currency, funderResource, offline, spStatus = 'SUCCESS',
  // Override just for the create-offer step (yearlyRepaymentAmount is derived
  // from this journey key). Lets scenarios like fp-usd-800k-online create a
  // tier3 offer (journey='2000K' → 16666667) while keeping the rest of the
  // flow on 500K.
  createOfferJourney,
}) {
  // Online mode registers with the offer_id already attached (Amazon 3P), so
  // once Amazon SP auth callback returns the flow is finished — there is no
  // need to run sp-updateOffer / wait for dpu_manual_offer / call 3PL redirect.
  // The offline flow (DMF) still needs those 3 extra steps to bind
  // the 3P shop after registration.
  const signupTitle = offline
    ? 'POST 用户注册'
    : 'GET redirect + POST 用户注册'
  const effectiveCreateOfferJourney = createOfferJourney || journey
  const onlineOfferSteps = offline ? [] : [
    {
      key: `${prefix}-create-offer`, type: 'api', method: 'POST', kind: '场景步骤',
      title: '生成 offerId', endpoint: '/api/register/create-offer', operationKey: null,
      payload: { env: '${env}', journey: effectiveCreateOfferJourney, currency },
      // 生成 offerId 的 journey / currency 可由用户在「参数」Tab 配置并保存；
      // journey 决定 yearlyRepaymentAmount（200K/500K/2000K→tier1/2/3）。
      fields: [
        {
          key: 'journey', label: 'Offer 额度档位', type: 'select', default: effectiveCreateOfferJourney,
          options: [
            { label: '200K (tier1)', value: '200K' },
            { label: '500K (tier2)', value: '500K' },
            { label: '2000K (tier3 / 800K)', value: '2000K' },
          ],
        },
        {
          key: 'currency', label: '币种', type: 'select', default: currency,
          options: [
            { label: 'USD', value: 'USD' },
            { label: 'CNY', value: 'CNY' },
          ],
        },
      ],
    },
    {
      key: `${prefix}-amazon-redirect`, type: 'api', method: 'POST', kind: '场景步骤',
      title: 'GET redirect + POST redirect 让 offerId 生效',
      endpoint: '/api/register/amazon-redirect', operationKey: null,
      payload: {
        env: '${env}', offer_id: '${offer_id}', phone_number: '${phone_number}',
        currency, funder_resource: funderResource,
      },
    },
    {
      key: `${prefix}-amazon-redirect-cleanup`, type: 'api', method: 'POST', kind: 'SQL步骤',
      title: '移除 TESTOFFER 后缀并更新店铺记录',
      endpoint: '/api/register/remove-test-offer-suffix', operationKey: null,
      payload: { env: '${env}', phone_number: '${phone_number}' },
    },
  ]
  const baseSteps = [
    ...onlineOfferSteps,
    {
      key: `${prefix}-sms`, type: 'api', method: 'POST', kind: '场景步骤',
      title: '发送注册短信', endpoint: '/api/register/send-sms', operationKey: null,
      // Online scenarios prepend create-offer + amazon-redirect steps, so we
      // pass the harvested offer_id back into send-sms; offline flows leave it
      // empty and send-sms won't generate one.
      payload: {
        env: '${env}', journey, currency, funder_resource: funderResource, offline,
        offer_id: '${offer_id}',
      },
    },
    {
      key: `${prefix}-token`, type: 'api', method: 'POST', kind: '场景步骤',
      title: '读取验证码并调用 validateSmsCode-sign', endpoint: '/api/register/validate-sms', operationKey: null,
      payload: {
        env: '${env}', phone_number: '${phone_number}',
        currency, funder_resource: funderResource, offer_id: '${offer_id}',
      },
    },
    {
      key: `${prefix}-signup`, type: 'api', method: 'POST', kind: '场景步骤',
      title: signupTitle, endpoint: '/api/register/signup', operationKey: null,
      payload: {
        env: '${env}', phone_number: '${phone_number}', email: '${email}',
        verification_code: '${verification_code}', journey, currency,
        funder_resource: funderResource, offline, offer_id: '${offer_id}',
      },
    },
    {
      key: `${prefix}-state`, type: 'api', method: 'POST', kind: '场景步骤',
      title: '生成 state 并申请 SP 授权 URL', endpoint: '/api/register/sp-auth-url', operationKey: null,
      payload: {
        env: '${env}', phone_number: '${phone_number}', token: '${token}',
        currency, funder_resource: funderResource, offline,
      },
    },
    {
      key: `${prefix}-sp-auth`, type: 'api', method: 'POST', kind: '场景步骤',
      title: '查询 SP auth-result 并回调 Amazon SP auth', endpoint: '/api/register/sp-auth-callback', operationKey: null,
      payload: {
        env: '${env}', phone_number: '${phone_number}', token: '${token}',
        state: '${state}', selling_partner_id: '${selling_partner_id}',
        currency, funder_resource: funderResource,
      },
    },
  ]

  // 线上注册已经带着 offer_id 完成绑店，SP auth 回调返回后即结束。
  // 线下模式 (DMF) 需要额外三步：sp-updateOffer 上报授权结果、
  // 等待 dpu_manual_offer 生成 platform_offer_id、以及 3PL 重定向回调。
  if (!offline) {
    return baseSteps
  }
  return [
    ...baseSteps,
    {
      key: `${prefix}-update-offer`, type: 'api', method: 'POST', kind: '场景步骤',
      title: 'sp-updateOffer 上报 SP 授权结果', endpoint: '/api/register/sp-update-offer', operationKey: null,
      payload: {
        env: '${env}', phone_number: '${phone_number}',
        selling_partner_id: '${selling_partner_id}', sp_status: spStatus,
      },
      fields: [
        {
          key: 'sp_status',
          label: 'SP 状态',
          type: 'select',
          default: spStatus,
          options: [
            { label: 'SUCCESS - 通过', value: 'SUCCESS' },
            { label: 'FAIL - 拒绝', value: 'FAIL' },
          ],
        },
        {
          key: 'failure_reason_index',
          label: '失败原因',
          type: 'select',
          default: 4,
          visibleWhen: (form) => form?.sp_status === 'FAIL',
          options: [
            { label: '1 - 资方国家与卖家上报国家不一致', value: 1 },
            { label: '2 - 已存在生效的额度审批', value: 2 },
            { label: '3 - 该资方在该商品组合下已有 offer', value: 3 },
            { label: '4 - others（默认）', value: 4 },
          ],
        },
      ],
    },
    {
      key: `${prefix}-3pl-auth`, type: 'api', method: 'POST', kind: '场景步骤',
      title: '等待 dpu_manual_offer 生成 platform_offer_id', endpoint: '/api/register/3pl-link-wait', operationKey: null,
      payload: {
        env: '${env}', phone_number: '${phone_number}',
        selling_partner_id: '${selling_partner_id}', offline,
      },
    },
    {
      key: `${prefix}-3pl-auth-result`, type: 'api', method: 'POST', kind: '场景步骤',
      title: '3PL 重定向回调 (amazon/redirect + POST)', endpoint: '/api/register/3pl-redirect', operationKey: null,
      payload: { env: '${env}', phone_number: '${phone_number}' },
    },
    {
      key: `${prefix}-3pl-redirect-cleanup`, type: 'api', method: 'POST', kind: 'SQL步骤',
      title: '移除 TESTOFFER 后缀并更新店铺记录',
      endpoint: '/api/register/remove-test-offer-suffix', operationKey: null,
      payload: { env: '${env}', phone_number: '${phone_number}' },
    },
  ]
}

function buildFpUsdScenarioSteps(limitLabel, options = {}) {
  // `prefix` decides the step keys — different scenarios that share the same
  // step layout must use different prefixes, otherwise their step run states
  // collide in scenarioStepResults.
  const prefix = options.prefix || limitLabel
  const offerName = limitLabel === '2K' ? '选择offer额度-2k' : '选择offer额度-500k'
  const journey = limitLabel === '2K' ? '200K' : '500K'
  // `offline` toggles the register step group. FP-USD scenarios normally
  // register online; the 500k-online variant explicitly forces offline=false
  // and keeps the same downstream steps.
  const offline = options.offline ?? false
  const baseSteps = [
    ...buildRegisterStepGroup({
      prefix,
      journey,
      currency: 'USD',
      funderResource: 'FUNDPARK',
      offline,
      // 800k-online 场景需要单独用 2000K 的 yearlyRepaymentAmount (16666667)
      // 生成一个 tier3 offer，但后续所有步骤仍然走 500K 的额度/journey。
      createOfferJourney: options.createOfferJourney,
    }),
    { key: `${prefix}-application`, type: 'api', method: 'POST', kind: '自定义请求', title: '创建申请单', endpoint: '/api/mock/create-application-context', operationKey: null, payload: { journey } },
    { key: `${prefix}-business-info`, type: 'api', method: 'POST', kind: '自定义请求', title: '邓白氏提交企业信息', endpoint: '/api/mock/fp-business-profile', operationKey: null, payload: { journey } },
    { key: `${prefix}-director-info`, type: 'api', method: 'POST', kind: '自定义请求', title: '邓白氏提交法人信息', endpoint: '/api/mock/fp-director-info', operationKey: null, payload: { journey } },
    ...(limitLabel === '2K'
      ? [{ key: `${prefix}-bank-info`, type: 'api', method: 'POST', kind: '自定义请求', title: 'bank-info', endpoint: '/api/mock/fp-bank-info', operationKey: null, payload: { journey } }]
      : []),
    { key: `${prefix}-offer-select`, type: 'api', method: 'POST', kind: '自定义请求', title: offerName, endpoint: '/api/mock/fp-offer-limit-select', operationKey: null, payload: { journey } },
    { key: `${prefix}-offer-quote`, type: 'api', method: 'POST', kind: '自定义请求', title: '创建offer额度报价', endpoint: '/api/mock/fp-offer-quote-activate', operationKey: null, payload: { journey } },
    { key: `${prefix}-associate`, type: 'api', method: 'POST', kind: '自定义请求', title: '关联SP和3PL店铺', endpoint: '/api/mock/fp-link-sp-3pl-shops', operationKey: null, payload: { journey } },
    { key: `${prefix}-scheduled`, type: 'api', method: 'POST', kind: '自定义请求', title: 'run-fp-scheduled-tasks-and-poll-submitted', endpoint: '/api/mock/fp-scheduled-submit', operationKey: null, payload: { journey } },
  ]
  // 「激活 offer 额度报价」是 approved-offer 之后单独发出的 activate-offer 调用，
  // 复用 /api/mock/fp-activate-offer 已有的路由。所有 FP-USD 场景都需要。
  const activateOfferQuoteStep = {
    key: `${prefix}-activate-offer-quote`,
    type: 'api',
    method: 'POST',
    kind: '自定义请求',
    title: '激活offer额度报价',
    endpoint: '/api/mock/fp-activate-offer',
    operationKey: null,
    payload: { currency: 'USD', funder_resource: 'FUNDPARK' },
  }
  if (limitLabel === '2K') {
    return [
      ...baseSteps,
      makeApprovedOfferStep(`${prefix}-approved-offer`, 500000),
      activateOfferQuoteStep,
      makeEsignStep(`${prefix}-esign`),
      makeDrawdownStep(`${prefix}-drawdown`, 'disbursement-completed'),
    ]
  }
  const activateAdditionalLimitStep = options.withActivateAdditionalLimit ? [
    {
      key: `${prefix}-activate-additional-limit`,
      type: 'api',
      method: 'POST',
      kind: '自定义请求',
      title: '激活额外的额度',
      endpoint: '/api/mock/fp-activate-additional-limit',
      operationKey: null,
      payload: { currency: 'USD', funder_resource: 'FUNDPARK' },
    },
    {
      key: `${prefix}-submit-additional-documents`,
      type: 'api',
      method: 'POST',
      kind: '自定义请求',
      title: '提交额外文档资料',
      endpoint: '/api/mock/fp-submit-additional-documents',
      operationKey: null,
      payload: { currency: 'USD', funder_resource: 'FUNDPARK' },
    },
    {
      key: `${prefix}-submit-additional-business-info`,
      type: 'api',
      method: 'POST',
      kind: '自定义请求',
      title: '提交额外公司信息',
      endpoint: '/api/mock/fp-submit-additional-business-info',
      operationKey: null,
      payload: { currency: 'USD', funder_resource: 'FUNDPARK' },
    },
    {
      key: `${prefix}-submit-additional-director-info`,
      type: 'api',
      method: 'POST',
      kind: '自定义请求',
      title: '提交额外董事信息',
      endpoint: '/api/mock/fp-submit-additional-director-info',
      operationKey: null,
      payload: { currency: 'USD', funder_resource: 'FUNDPARK' },
    },
    {
      key: `${prefix}-re-approved-offer`,
      type: 'api',
      method: 'POST',
      kind: '自定义请求',
      title: 're-approved-offer（拉取最新申请单再次审批）',
      endpoint: '/api/mock/fp-re-approved-offer',
      operationKey: null,
      payload: { amount: 800000, status: 'APPROVED' },
      fields: [
        { key: 'amount', label: '审批额度', type: 'number', default: 800000 },
        {
          key: 'status', label: '审批结果', type: 'select', default: 'APPROVED',
          options: [
            { label: 'APPROVED - 通过', value: 'APPROVED' },
            { label: 'RETURNED - 退回', value: 'RETURNED' },
            { label: 'REJECTED - 拒绝', value: 'REJECTED' },
          ],
        },
        {
          key: 'rejection_reason', label: '拒绝原因', type: 'select', default: 'others',
          visibleWhen: (form) => form?.status === 'REJECTED',
          options: [
            { label: 'fraud - 欺诈', value: 'fraud' },
            { label: 'others - 其他', value: 'others' },
          ],
        },
        {
          key: 'failure_reason_index', label: '退回原因序号 (1-7)', type: 'number', default: 1,
          visibleWhen: (form) => form?.status === 'RETURNED',
        },
      ],
    },
    {
      key: `${prefix}-activate-offer`,
      type: 'api',
      method: 'POST',
      kind: '自定义请求',
      title: '激活新的 offer',
      endpoint: '/api/mock/fp-activate-offer',
      operationKey: null,
      payload: { currency: 'USD', funder_resource: 'FUNDPARK' },
    },
  ] : []
  return [
    ...baseSteps,
    makeUnderwrittenStep(`${prefix}-underwritten`),
    makeApprovedOfferStep(`${prefix}-approved-offer`, 500000),
    activateOfferQuoteStep,
    ...activateAdditionalLimitStep,
    makePspStartStep(`${prefix}-psp-start`),
    makePspCompletedStep(`${prefix}-psp-completed`),
    // 800K 走了 re-approved-offer 之后，dpu_credit_offer 有更新的一行，
    // esign 必须重新按 merchant_id 查最新 lender_approved_offer_id；其它
    // 场景没有 activate-additional-limit 分支，正常走老 /api/mock/esign。
    makeEsignStep(`${prefix}-esign`, {
      refresh: !!options.withActivateAdditionalLimit,
      defaultAmount: options.withActivateAdditionalLimit ? 800000 : 500000,
    }),
    ...(options.drawdownAmount
      ? [makeDrawdownStep(`${prefix}-drawdown`, 'disbursement-completed', options.drawdownAmount)]
      : []),
  ]
}

// --- Reusable step factories with editable field schemas ---
// Each factory returns a step object identical in shape to the inline ones, but
// also carries a `fields` array so the 参数 tab can render an editable form
// (sp-updateOffer pattern). Defaults match the historical hard-coded payload.

function makeUnderwrittenStep(key) {
  return {
    key, type: 'api', method: 'POST', kind: '自定义请求',
    title: 'underwritten', endpoint: '/api/mock/underwritten', operationKey: 'underwritten',
    fields: [
      { key: 'amount', label: '核保额度', type: 'number', default: 500000 },
      {
        key: 'status', label: '核保结果', type: 'select', default: 'APPROVED',
        options: [
          { label: 'APPROVED - 通过', value: 'APPROVED' },
          { label: 'REJECTED - 拒绝', value: 'REJECTED' },
        ],
      },
    ],
  }
}

function makeApprovedOfferStep(key, defaultAmount) {
  return {
    key, type: 'api', method: 'POST', kind: '自定义请求',
    title: 'approved-offer', endpoint: '/api/mock/approved-offer', operationKey: 'approvedOffer',
    fields: [
      { key: 'amount', label: '审批额度', type: 'number', default: defaultAmount || 500000 },
      {
        key: 'status', label: '审批结果', type: 'select', default: 'APPROVED',
        options: [
          { label: 'APPROVED - 通过', value: 'APPROVED' },
          { label: 'RETURNED - 退回', value: 'RETURNED' },
          { label: 'REJECTED - 拒绝', value: 'REJECTED' },
        ],
      },
      {
        key: 'rejection_reason', label: '拒绝原因', type: 'select', default: 'others',
        visibleWhen: (form) => form?.status === 'REJECTED',
        options: [
          { label: 'fraud - 欺诈', value: 'fraud' },
          { label: 'others - 其他', value: 'others' },
        ],
      },
      {
        key: 'failure_reason_index', label: '退回原因序号 (1-7)', type: 'number', default: 1,
        visibleWhen: (form) => form?.status === 'RETURNED',
      },
    ],
  }
}

function makeIncreaseApprovedOfferStep(key, defaultAmount) {
  return {
    ...makeApprovedOfferStep(key, defaultAmount),
    title: '提额approved-offer',
    endpoint: '/api/mock/fp-increase-approved-offer',
    operationKey: null,
    payload: { amount: defaultAmount || 500000, status: 'APPROVED' },
    description: '先查询同一 merchant_id 下最新两条 dpu_application，校验旧申请单 APPROVED，再用最新 application_unique_id 调用 approved-offer。',
  }
}

function makePspStartStep(key) {
  return {
    key, type: 'api', method: 'POST', kind: '自定义请求',
    title: 'psp-start', endpoint: '/api/mock/psp-start', operationKey: 'pspStart',
    fields: [
      {
        key: 'status', label: 'PSP 启动状态', type: 'select', default: 'PROCESSING',
        options: [
          { label: 'PROCESSING - 处理中', value: 'PROCESSING' },
          { label: 'FAIL - 失败', value: 'FAIL' },
          { label: 'INITIAL - 重置', value: 'INITIAL' },
        ],
      },
    ],
  }
}

function makePspCompletedStep(key) {
  return {
    key, type: 'api', method: 'POST', kind: '自定义请求',
    title: 'psp-completed', endpoint: '/api/mock/psp-completed', operationKey: 'pspCompleted',
    fields: [
      {
        key: 'status', label: 'PSP 完成状态', type: 'select', default: 'SUCCESS',
        options: [
          { label: 'SUCCESS - 成功', value: 'SUCCESS' },
          { label: 'FAIL - 失败', value: 'FAIL' },
          { label: 'INITIAL - 重置', value: 'INITIAL' },
        ],
      },
    ],
  }
}

function makeEsignStep(key, options = {}) {
  // 800K 场景的 esign 必须先从 dpu_credit_offer 拉最新 lender_approved_offer_id
  // （re-approved-offer 会新落一条记录），所以走 /api/mock/fp-re-esign 而不是
  // 老的 /api/mock/esign。其它场景保持原行为。
  const useReEsign = !!options.refresh
  return {
    key,
    type: 'api',
    method: 'POST',
    kind: '自定义请求',
    title: useReEsign ? 'esign（拉取最新 credit-offer 再签）' : 'esign',
    endpoint: useReEsign ? '/api/mock/fp-re-esign' : '/api/mock/esign',
    operationKey: useReEsign ? null : 'esign',
    fields: [
      { key: 'signed_amount', label: '签约金额', type: 'number', default: options.defaultAmount || 500000 },
      {
        key: 'status', label: '电子签结果', type: 'select', default: 'SUCCESS',
        options: [
          { label: 'SUCCESS - 成功', value: 'SUCCESS' },
          { label: 'FAIL - 失败', value: 'FAIL' },
        ],
      },
    ],
  }
}

function makeIncreaseEsignStep(key, defaultAmount) {
  return {
    ...makeEsignStep(key, { defaultAmount: defaultAmount || 500000 }),
    title: '提额esign',
    endpoint: '/api/mock/fp-increase-esign',
    operationKey: null,
    payload: { signed_amount: defaultAmount || 500000, status: 'SUCCESS' },
    description: '先查询同一 merchant_id 下最新两条 dpu_credit_offer，校验旧记录 e_sign_status=SUCCESS，再用最新 lender_approved_offer_id 调用 esign。',
  }
}

function makeDrawdownStep(key, title, defaultAmount = 500000) {
  return {
    key, type: 'api', method: 'POST', kind: '自定义请求',
    title: title || 'drawdown', endpoint: '/api/mock/drawdown', operationKey: 'drawdown',
    fields: [
      { key: 'amount', label: '放款金额', type: 'number', default: defaultAmount },
      {
        key: 'status', label: '放款结果', type: 'select', default: 'APPROVED',
        options: [
          { label: 'APPROVED - 通过', value: 'APPROVED' },
          { label: 'REJECTED - 拒绝', value: 'REJECTED' },
        ],
      },
      {
        key: 'failure_reason_index', label: '失败原因序号 (1-5)', type: 'number', default: 1,
        visibleWhen: (form) => form?.status === 'REJECTED',
      },
    ],
  }
}

// 准入类型选择器：DS-CNY 各店铺「更新3PL店铺经营数据」步骤共用，避免多处维护同一份选项。
function buildAccessTypeField() {
  const optionsByName = new Map(
    shopPerformancePresets.value
      .filter((preset) => preset?.name)
      .map((preset) => [preset.name, { label: preset.name, value: preset.name }]),
  )
  return {
    key: 'access_type', label: '准入类型', type: 'select', default: 'webank准入ccb准入',
    options: Array.from(optionsByName.values()),
  }
}

function buildDsCnyScenarioSteps() {
  const registerSteps = buildRegisterStepGroup({
    prefix: 'DS-CNY',
    journey: '500K',
    currency: 'CNY',
    funderResource: 'DOWSURE',
    offline: true,
  })
  const skippedBindingSteps = new Set([
    'DS-CNY-state',
    'DS-CNY-sp-auth',
    'DS-CNY-update-offer',
    'DS-CNY-3pl-auth',
    // 原合并的 3PL 重定向回调步骤已拆成下面的 create-offer + amazon-redirect 两步。
    'DS-CNY-3pl-auth-result',
  ])

  return [
    ...registerSteps.filter((step) => !skippedBindingSteps.has(step.key)),
    // 拆分原「3PL 重定向回调」：先固定生成 CNY 950000 的 offerId。
    {
      key: 'DS-CNY-create-offer',
      type: 'api',
      method: 'POST',
      kind: '场景步骤',
      title: '生成 offerId',
      endpoint: '/api/register/create-offer',
      operationKey: null,
      payload: {
        env: '${env}',
        currency: 'CNY',
        yearly_repayment_amount: 950000,
      },
    },
    // 再 GET redirect + POST redirect 让 offerId 生效。
    {
      key: 'DS-CNY-amazon-redirect',
      type: 'api',
      method: 'POST',
      kind: '场景步骤',
      title: 'GET redirect + POST redirect 让 offerId 生效',
      endpoint: '/api/register/amazon-redirect',
      operationKey: null,
      payload: {
        env: '${env}',
        offer_id: '${offer_id}',
        phone_number: '${phone_number}',
        currency: 'CNY',
        funder_resource: 'DOWSURE',
        // signup 后 harvest 的用户 token，用于给 amazon/redirect 带 Authorization: Bearer。
        token: '${token}',
      },
    },
    {
      key: 'DS-CNY-shop-performance-sql',
      type: 'api',
      method: 'POST',
      kind: 'SQL步骤',
      title: '更新3PL店铺经营数据',
      endpoint: '/api/mock/shop-performance-cny-boost',
      operationKey: null,
      payload: {
        offer_id: '${platform_offer_id}',
        access_type: 'webank准入ccb准入',
      },
      // 准入类型：按所选店铺跑对应经营数据 SQL（选项复用 buildAccessTypeField）。
      fields: [buildAccessTypeField()],
    },
    {
      key: 'DS-CNY-kiosk-seller-id-check',
      type: 'api',
      method: 'POST',
      kind: 'SQL步骤',
      title: '校验 kiosk 生成 seller_id',
      endpoint: '/api/mock/kiosk-seller-id-check',
      operationKey: null,
      payload: {
        offer_id: '${platform_offer_id}',
      },
    },
    {
      key: 'DS-CNY-remove-test-offer-suffix',
      type: 'api',
      method: 'POST',
      kind: 'SQL步骤',
      title: '移除 TESTOFFER 后缀并更新店铺记录',
      endpoint: '/api/register/remove-test-offer-suffix',
      operationKey: null,
      payload: {
        env: '${env}',
        phone_number: '${phone_number}',
      },
    },
    {
      key: 'DS-CNY-application',
      type: 'api',
      method: 'POST',
      kind: '自定义请求',
      title: '创建 DOWSURE 申请单',
      endpoint: '/api/mock/create-application-context',
      operationKey: null,
      payload: {
        journey: '500K',
        currency: 'CNY',
        funder_resource: 'DOWSURE',
        offer_id: '${platform_offer_id}',
        tier_code: 4,
      },
    },
    {
      key: 'DS-CNY-business-info',
      type: 'api',
      method: 'POST',
      kind: '自定义请求',
      title: '邓白氏提交企业信息',
      endpoint: '/api/mock/fp-business-profile',
      operationKey: null,
      payload: {
        journey: '500K',
        currency: 'CNY',
        funder_resource: 'DOWSURE',
        cnName: '广州测试科技有限公司',
      },
      // 企业中文名可在「参数」里切换；后端仅 CNY+DOWSURE 分支使用 cnName。
      fields: [
        {
          key: 'cnName', label: '企业中文名', type: 'select', default: '广州测试科技有限公司',
          options: [
            ...dowsureCnyCompanyTemplates.value
              .filter((item) => item?.name && item?.template?.cnName)
              .map((item) => ({ label: item.name, value: item.template.cnName })),
          ],
        },
        {
          key: 'businessLicenseImageId',
          label: '企业营业执照',
          type: 'select',
          default: 'builtin:business_license',
          options: companyImageOptions('business_license'),
        },
      ],
    },
    {
      key: 'DS-CNY-director-info',
      type: 'api',
      method: 'POST',
      kind: '自定义请求',
      title: '邓白氏提交法人信息',
      endpoint: '/api/mock/fp-director-info',
      operationKey: null,
      // 不再固定 nameCn/addressDetail：法人信息自动跟随上一步 business-info 选择的公司。
      // 选默认公司→法人「奉晓慧」；选备用公司「测广州市昆袄祝山脸从股份有限公司」→法人「测近智」。
      payload: {
        journey: '500K',
        currency: 'CNY',
        funder_resource: 'DOWSURE',
      },
      fields: [
        {
          key: 'directorIdFrontImageId',
          label: '法人身份证正面',
          type: 'select',
          default: 'builtin:director_id_front',
          options: companyImageOptions('director_id_front'),
        },
        {
          key: 'directorIdBackImageId',
          label: '法人身份证反面',
          type: 'select',
          default: 'builtin:director_id_back',
          options: companyImageOptions('director_id_back'),
        },
      ],
    },
    {
      key: 'DS-CNY-contact-person',
      type: 'api',
      method: 'POST',
      kind: '自定义请求',
      title: '提交联系人信息',
      endpoint: '/api/mock/fp-add-contact-information',
      operationKey: null,
      payload: {
        journey: '500K',
        currency: 'CNY',
        funder_resource: 'DOWSURE',
      },
    },
    {
      key: 'DS-CNY-start-reassessment',
      type: 'api',
      method: 'POST',
      kind: '自定义请求',
      title: '开始信用评估',
      endpoint: '/api/mock/dowsure-start-reassessment',
      operationKey: null,
      payload: {
        journey: '500K',
        currency: 'CNY',
        funder_resource: 'DOWSURE',
      },
    },
  ]
}

function buildDsCnyMultiShopScenarioSteps() {
  // 照搬单店铺 DS-CNY 全流程，然后在「提交联系人信息」之后、「开始信用评估」之前
  // 追加第二家店铺步骤（照搬 DS-CNY 第 4/5/6/7 步：生成 offerId → redirect →
  // 更新3PL店铺数据 → 校验 kiosk 生成 seller_id）。每次 create-offer 会生成一个新的
  // amazon3plOfferId 并写入 ${offer_id}/${platform_offer_id}，供后续 redirect/店铺数据/
  // kiosk 步骤复用，因此第二家店铺沿用相同的 payload 即可。
  const baseSteps = buildDsCnyScenarioSteps()
  const secondShopSteps = [
    {
      key: 'DS-CNY-second-shop-create-offer',
      type: 'api',
      method: 'POST',
      kind: '场景步骤',
      title: '第二家店铺 生成 offerId',
      endpoint: '/api/register/create-offer',
      operationKey: null,
      payload: {
        env: '${env}',
        currency: 'CNY',
        yearly_repayment_amount: 950000,
      },
    },
    {
      key: 'DS-CNY-second-shop-amazon-redirect',
      type: 'api',
      method: 'POST',
      kind: '场景步骤',
      title: '第二家店铺 GET redirect + POST redirect 让 offerId 生效',
      endpoint: '/api/register/amazon-redirect',
      operationKey: null,
      payload: {
        env: '${env}',
        offer_id: '${offer_id}',
        phone_number: '${phone_number}',
        currency: 'CNY',
        funder_resource: 'DOWSURE',
        token: '${token}',
      },
    },
    {
      key: 'DS-CNY-second-shop-amazon-redirect-cleanup',
      type: 'api', method: 'POST', kind: 'SQL步骤',
      title: '第二家店铺 移除 TESTOFFER 后缀并更新店铺记录',
      endpoint: '/api/register/remove-test-offer-suffix', operationKey: null,
      payload: { env: '${env}', phone_number: '${phone_number}' },
    },
    {
      key: 'DS-CNY-second-shop-shop-performance-sql',
      type: 'api',
      method: 'POST',
      kind: 'SQL步骤',
      title: '第二家店铺 更新3PL店铺经营数据',
      endpoint: '/api/mock/shop-performance-cny-boost',
      operationKey: null,
      payload: {
        offer_id: '${platform_offer_id}',
        access_type: 'webank准入ccb准入',
      },
      fields: [buildAccessTypeField()],
    },
    {
      key: 'DS-CNY-second-shop-kiosk-seller-id-check',
      type: 'api',
      method: 'POST',
      kind: 'SQL步骤',
      title: '第二家店铺 校验 kiosk 生成 seller_id',
      endpoint: '/api/mock/kiosk-seller-id-check',
      operationKey: null,
      payload: {
        offer_id: '${platform_offer_id}',
      },
    },
  ]
  // 第三家店铺：再照搬 DS-CNY 第 4/5/6/7 步生成一家新店铺。
  const thirdShopSteps = [
    {
      key: 'DS-CNY-third-shop-create-offer',
      type: 'api',
      method: 'POST',
      kind: '场景步骤',
      title: '第三家店铺 生成 offerId',
      endpoint: '/api/register/create-offer',
      operationKey: null,
      payload: {
        env: '${env}',
        currency: 'CNY',
        yearly_repayment_amount: 950000,
      },
    },
    {
      key: 'DS-CNY-third-shop-amazon-redirect',
      type: 'api',
      method: 'POST',
      kind: '场景步骤',
      title: '第三家店铺 GET redirect + POST redirect 让 offerId 生效',
      endpoint: '/api/register/amazon-redirect',
      operationKey: null,
      payload: {
        env: '${env}',
        offer_id: '${offer_id}',
        phone_number: '${phone_number}',
        currency: 'CNY',
        funder_resource: 'DOWSURE',
        token: '${token}',
      },
    },
    {
      key: 'DS-CNY-third-shop-amazon-redirect-cleanup',
      type: 'api', method: 'POST', kind: 'SQL步骤',
      title: '第三家店铺 移除 TESTOFFER 后缀并更新店铺记录',
      endpoint: '/api/register/remove-test-offer-suffix', operationKey: null,
      payload: { env: '${env}', phone_number: '${phone_number}' },
    },
    {
      key: 'DS-CNY-third-shop-shop-performance-sql',
      type: 'api',
      method: 'POST',
      kind: 'SQL步骤',
      title: '第三家店铺 更新3PL店铺经营数据',
      endpoint: '/api/mock/shop-performance-cny-boost',
      operationKey: null,
      payload: {
        offer_id: '${platform_offer_id}',
        access_type: 'webank准入ccb准入',
      },
      fields: [buildAccessTypeField()],
    },
    {
      key: 'DS-CNY-third-shop-kiosk-seller-id-check',
      type: 'api',
      method: 'POST',
      kind: 'SQL步骤',
      title: '第三家店铺 校验 kiosk 生成 seller_id',
      endpoint: '/api/mock/kiosk-seller-id-check',
      operationKey: null,
      payload: {
        offer_id: '${platform_offer_id}',
      },
    },
  ]
  secondShopSteps.push(...thirdShopSteps)
  const insertBeforeKey = 'DS-CNY-start-reassessment'
  const idx = baseSteps.findIndex((step) => step.key === insertBeforeKey)
  if (idx === -1) {
    return [...baseSteps, ...secondShopSteps]
  }
  return [...baseSteps.slice(0, idx), ...secondShopSteps, ...baseSteps.slice(idx)]
}


const aiQuickPrompts = [
  '帮我看一下当前 session 的状态，哪些关键信息还缺失？',
  '查询当前手机号对应的 merchant_id',
  '根据最近日志分析失败原因，并告诉我下一步怎么查',
  'SELECT merchant_id, phone_number FROM dpu_users ORDER BY created_at DESC LIMIT 5',
]

watch(applicationOptions, (applications) => {
  if (!applications.length) {
    selectedApplicationUniqueId.value = ''
    return
  }
  if (!selectedApplicationUniqueId.value || !applications.some((item) => item.application_unique_id === selectedApplicationUniqueId.value)) {
    selectedApplicationUniqueId.value = (
      sessionSummary.value?.selected_application_unique_id
      || sessionSummary.value?.application_unique_id
      || applications[0].application_unique_id
      || ''
    )
  }
})

watch(
  () => connectionForm.env,
  (value) => {
    registerForm.env = value
    if (interfacePageMode.value === 'debug') {
      void prepareDebugRequestDraft()
    }
  },
)

watch(
  [activeOperationKey, activeSessionId],
  () => {
    if (shouldShowLimitApplications.value) {
      loadLimitApplications()
    } else {
      limitApplicationRows.value = []
      selectedLimitApplicationUniqueId.value = ''
      limitApplicationSelectionTouched.value = false
    }
    if (shouldShowDrawdownRepaymentRows.value) {
      loadDrawdownRepaymentRows()
    } else {
      drawdownRepaymentRows.value = []
      selectedDowsureRepaymentLoanCode.value = ''
      drawdownRepaymentSelectionTouched.value = false
    }
    if (shouldShowDowsureMerchantAccounts.value) {
      loadDowsureMerchantAccounts()
    } else {
      dowsureMerchantAccounts.value = []
      operationForms.dowsureCreditResult.creditResultList = []
    }
    if (shouldShowWebankSellerOffers.value) {
      loadWebankSellerOffers()
    } else {
      webankSellerOffers.value = []
      operationForms.webankCreditResult.seller_offers = []
    }
    if (shouldShowPspAuthorizationRows.value) {
      loadPspAuthorizationRows()
    } else {
      selectedPspMerchantAccountId.value = ''
      pspSelectionTouched.value = false
    }
    if (shouldLoadApplicationCodes.value) {
      loadApplicationCodes()
    } else {
      applicationCodeOptions.value = []
    }
  },
)

watch(
  operations,
  (items) => {
    interfaceScenarios.value.flatMap((scenario) => scenario.steps).forEach((item) => {
      if (interfaceStepEnabled[item.key] === undefined) interfaceStepEnabled[item.key] = true
    })
    if (!activeOperationKey.value && activeInterfaceScenario.value.steps.length > 0) {
      activeOperationKey.value = activeInterfaceScenario.value.steps[0].key
    }
  },
  { immediate: true },
)

watch(activeInterfaceScenarioKey, () => {
  const steps = interfaceAutomationSteps.value
  if (!steps.some((step) => step.key === activeOperationKey.value)) {
    activeOperationKey.value = steps[0]?.key || ''
  }
  if (activeInterfaceScenario.value.bootstrap?.env) {
    connectionForm.env = activeInterfaceScenario.value.bootstrap.env
    registerForm.env = activeInterfaceScenario.value.bootstrap.env
  }
})

watch(darkMode, (value) => {
  document.documentElement.classList.toggle('mockapi-dark', value)
  window.localStorage.setItem('mockapi-theme', value ? 'dark' : 'light')
}, { immediate: true })

watch(
  [stepFocusTab, () => selectedInterfaceStep.value?.key, () => getScenarioStepSourceEndpoint(selectedInterfaceStep.value)],
  () => {
    if (stepFocusTab.value === 'logic' && selectedInterfaceStep.value) {
      loadScenarioStepLogicSource(selectedInterfaceStep.value)
    }
  },
)

watch(
  [() => selectedInterfaceStep.value?.key, interfacePageMode],
  () => {
    if (interfacePageMode.value === 'debug') {
      void prepareDebugRequestDraft()
    }
  },
)

watch(filteredDebugInterfaceSteps, (steps) => {
  if (interfacePageMode.value !== 'debug') return
  if (!steps.length) return
  if (!steps.some((step) => step.key === activeOperationKey.value)) {
    activeOperationKey.value = steps[0].key
  }
})

watch(scenarioExecutionHistory, persistScenarioExecutionHistory, { deep: true })

onMounted(async () => {
  const savedTheme = window.localStorage.getItem('mockapi-theme')
  if (savedTheme) {
    darkMode.value = savedTheme === 'dark'
  } else {
    darkMode.value = window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false
  }
  syncRailViewport()
  window.addEventListener('resize', syncRailViewport)
  restoreScenarioExecutionHistory()
  restoreAuthUser()
  loadContactIssues()
  startEnvironmentMonitorAutoRefresh()
  await Promise.all([refreshHealth(), loadEnums(), loadSessions(), refreshScenarioMetaOverrides(), refreshScenarioStepMetaOverrides()])
  if (authUser.value?.username) {
    refreshScenarioStepOverrides()
    refreshScenarioStepOrders()
    refreshCompanyImageTemplates()
  }
})

watch(
  () => authUser.value?.username,
  (username) => {
    if (username) {
      refreshScenarioStepOverrides()
      refreshScenarioMetaOverrides()
      refreshScenarioStepMetaOverrides()
      refreshScenarioStepOrders()
      refreshCompanyImageTemplates()
    } else {
      // Clear cached overrides on logout so the next user doesn't see them.
      Object.keys(scenarioStepOrders).forEach((key) => { delete scenarioStepOrders[key] })
      Object.keys(scenarioStepOrderDraft).forEach((key) => { delete scenarioStepOrderDraft[key] })
      Object.keys(scenarioStepMetaOverrides).forEach((key) => { delete scenarioStepMetaOverrides[key] })
      Object.keys(scenarioStepOverrides).forEach((key) => {
        delete scenarioStepOverrides[key]
      })
      scenarioStepOverridesLoaded.value = false
      shopPerformancePresets.value = createBuiltinShopPerformancePresets()
      resetShopPerformancePresetForm()
      dowsureCnyCompanyTemplates.value = BUILTIN_DOWSURE_CNY_COMPANY_TEMPLATES.map(cloneDowsureCompanyTemplate)
      resetDowsureCompanyTemplateForm()
      companyImageTemplates.value = BUILTIN_COMPANY_IMAGE_TEMPLATES.map((item) => ({ ...item }))
      resetCompanyImageForm()
      aiUiCases.value = []
      aiUiRuns.value = []
      aiUiRuntime.value = null
      aiUiActiveRunId.value = ''
      clearAiUiPoll()
    }
  },
)

onBeforeUnmount(() => {
  clearAiUiPoll()
  stopMockOperationLongPress()
  closeSocket()
  stopSessionPolling()
  stopEnvironmentMonitorAutoRefresh()
  window.removeEventListener('resize', syncRailViewport)
})

function syncRailViewport() {
  isMobileViewport.value = window.innerWidth < 1024
}

async function refreshHealth() {
  loadingHealth.value = true
  try {
    await fetchHealth()
    health.value = 'ok'
  } catch (error) {
    health.value = normalizeError(error)
  } finally {
    loadingHealth.value = false
  }
}

async function loadEnums() {
  loadingEnums.value = true
  try {
    enumOptions.value = await fetchEnums()
  } catch (error) {
    pushActivity('error', '加载枚举失败', normalizeError(error))
  } finally {
    loadingEnums.value = false
  }
}

async function loadSessions() {
  loadingSessions.value = true
  try {
    if (!activeSessionId.value) {
      liveSessions.value = []
      return
    }
    liveSessions.value = await fetchSessions(activeSessionId.value)
  } catch (error) {
    pushActivity('error', '刷新会话列表失败', normalizeError(error))
  } finally {
    loadingSessions.value = false
  }
}

async function refreshSessionsQuietly() {
  if (!activeSessionId.value) return
  try {
    liveSessions.value = await fetchSessions(activeSessionId.value)
  } catch (error) {
    pushActivity('error', '轮询刷新会话失败', normalizeError(error))
  }
}

function startSessionPolling() {
  stopSessionPolling()
  sessionPollTimer = window.setInterval(refreshSessionsQuietly, 5000)
}

function stopSessionPolling() {
  if (!sessionPollTimer) return
  window.clearInterval(sessionPollTimer)
  sessionPollTimer = null
}

async function loadPspAuthorizationRows() {
  if (!activeSessionId.value) {
    pspAuthorizationRows.value = []
    selectedPspMerchantAccountId.value = ''
    pspSelectionTouched.value = false
    return
  }
  loadingPspAuthorizationRows.value = true
  try {
    const result = await fetchPspAuthorizationRows(activeSessionId.value)
    pspAuthorizationRows.value = result.rows ?? []
    const currentSelectionStillValid = pspAuthorizationRows.value.some(
      (row) => row.merchant_account_id === selectedPspMerchantAccountId.value && isPspRowSelectable(row),
    )
    if (pspSelectionTouched.value) {
      if (!currentSelectionStillValid) {
        selectedPspMerchantAccountId.value = ''
        pspSelectionTouched.value = false
      }
    } else {
      const defaultMerchantAccountId = result.default_selected_merchant_account_id
      const defaultRow = pspAuthorizationRows.value.find(
        (row) => row.merchant_account_id === defaultMerchantAccountId && isPspRowSelectable(row),
      )
      selectedPspMerchantAccountId.value = defaultRow?.merchant_account_id || ''
    }
    if (!pspAuthorizationRows.value.some((row) => row.merchant_account_id === selectedPspMerchantAccountId.value && isPspRowSelectable(row))) {
      selectedPspMerchantAccountId.value = ''
    }
  } catch (error) {
    pspAuthorizationRows.value = []
    selectedPspMerchantAccountId.value = ''
    pspSelectionTouched.value = false
    pushActivity('error', '加载 PSP 授权状态失败', normalizeError(error))
  } finally {
    loadingPspAuthorizationRows.value = false
  }
}

async function loadLimitApplications() {
  if (!activeSessionId.value) {
    limitApplicationRows.value = []
    selectedLimitApplicationUniqueId.value = ''
    limitApplicationSelectionTouched.value = false
    return
  }
  loadingLimitApplications.value = true
  try {
    const result = await fetchLimitApplications(activeSessionId.value)
    limitApplicationRows.value = result.rows ?? []
    const currentSelectionStillValid = limitApplicationRows.value.some(
      (row) => row.limit_application_unique_id === selectedLimitApplicationUniqueId.value,
    )
    if (limitApplicationSelectionTouched.value) {
      if (!currentSelectionStillValid) {
        selectedLimitApplicationUniqueId.value = ''
        limitApplicationSelectionTouched.value = false
      }
    } else {
      selectedLimitApplicationUniqueId.value = result.default_selected_limit_application_unique_id || ''
    }
    if (!limitApplicationRows.value.some((row) => row.limit_application_unique_id === selectedLimitApplicationUniqueId.value)) {
      selectedLimitApplicationUniqueId.value = ''
    }
  } catch (error) {
    limitApplicationRows.value = []
    selectedLimitApplicationUniqueId.value = ''
    limitApplicationSelectionTouched.value = false
    pushActivity('error', '加载核保单失败', normalizeError(error))
  } finally {
    loadingLimitApplications.value = false
  }
}

function selectLimitApplicationRow(row) {
  selectedLimitApplicationUniqueId.value = row?.limit_application_unique_id || ''
  limitApplicationSelectionTouched.value = true
}

async function loadDrawdownRepaymentRows() {
  if (!activeSessionId.value) {
    drawdownRepaymentRows.value = []
    selectedDowsureRepaymentLoanCode.value = ''
    drawdownRepaymentSelectionTouched.value = false
    return
  }
  loadingDrawdownRepaymentRows.value = true
  try {
    const result = await fetchDrawdownRepaymentRows(activeSessionId.value)
    drawdownRepaymentRows.value = result.rows ?? []
    const currentSelectionStillValid = drawdownRepaymentRows.value.some(
      (row) => repaymentRowSelectionKey(row) === selectedDowsureRepaymentLoanCode.value,
    )
    if (drawdownRepaymentSelectionTouched.value) {
      if (!currentSelectionStillValid) {
        selectedDowsureRepaymentLoanCode.value = ''
        drawdownRepaymentSelectionTouched.value = false
      }
    } else {
      selectedDowsureRepaymentLoanCode.value = result.default_selected_lender_loan_id || ''
    }
    if (!drawdownRepaymentRows.value.some((row) => repaymentRowSelectionKey(row) === selectedDowsureRepaymentLoanCode.value)) {
      selectedDowsureRepaymentLoanCode.value = ''
    }
  } catch (error) {
    drawdownRepaymentRows.value = []
    selectedDowsureRepaymentLoanCode.value = ''
    drawdownRepaymentSelectionTouched.value = false
    pushActivity('error', '加载还款单失败', normalizeError(error))
  } finally {
    loadingDrawdownRepaymentRows.value = false
  }
}

function selectDrawdownRepaymentRow(row) {
  selectedDowsureRepaymentLoanCode.value = repaymentRowSelectionKey(row)
  drawdownRepaymentSelectionTouched.value = true
}

function repaymentRowSelectionKey(row) {
  return String(row?.lender_loan_id || row?.lender_drawdown_id || '').trim()
}

function applyApplicationCodeDefaults() {
  const codes = applicationCodeOptions.value
  const fallback = codes.length ? codes[0] : ''
  const targets = [
    ['dowsureCreditResult', 'applicationCode'],
    ['dowsureEsignDrawdownResult', 'application_code'],
    ['dowsureRepaymentResult', 'application_code'],
    ['dowsureRetryCallback', 'application_code'],
    ['webankCreditResult', 'application_code'],
    ['webankDrawdownResult', 'application_code'],
    ['webankRepaymentResult', 'application_code'],
    ['cgbCreditResult', 'application_code'],
    ['cgbLoanResult', 'application_code'],
    ['cgbRepaymentResult', 'application_code'],
  ]
  for (const [formKey, prop] of targets) {
    const form = operationForms[formKey]
    if (!form) continue
    const current = String(form[prop] ?? '').trim()
    if (!current || !codes.includes(current)) {
      form[prop] = fallback
    }
  }
}

async function loadApplicationCodes() {
  if (!activeSessionId.value) {
    applicationCodeOptions.value = []
    applyApplicationCodeDefaults()
    return
  }
  loadingApplicationCodes.value = true
  try {
    const result = await fetchApplicationCodes(activeSessionId.value)
    applicationCodeOptions.value = result.application_codes ?? []
    applyApplicationCodeDefaults()
  } catch (error) {
    applicationCodeOptions.value = []
    applyApplicationCodeDefaults()
    pushActivity('error', '加载 applicationCode 失败', normalizeError(error))
  } finally {
    loadingApplicationCodes.value = false
  }
}

async function loadDowsureMerchantAccounts() {
  if (!activeSessionId.value) {
    dowsureMerchantAccounts.value = []
    operationForms.dowsureCreditResult.creditResultList = []
    return
  }
  loadingDowsureMerchantAccounts.value = true
  try {
    const result = await fetchDowsureMerchantAccounts(activeSessionId.value)
    dowsureMerchantAccounts.value = result.accounts ?? []
    operationForms.dowsureCreditResult.creditResultList = dowsureMerchantAccounts.value.map((item) => ({
      offerId: item.offerId || '',
      sellerId: item.sellerId || '',
      amount: item.amount ?? operationForms.dowsureCreditResult.amount ?? 0,
    }))
  } catch (error) {
    dowsureMerchantAccounts.value = []
    operationForms.dowsureCreditResult.creditResultList = []
    pushActivity('error', '加载 DOWSURE 店铺失败', normalizeError(error))
  } finally {
    loadingDowsureMerchantAccounts.value = false
  }
}

async function loadWebankSellerOffers() {
  if (!activeSessionId.value) {
    webankSellerOffers.value = []
    operationForms.webankCreditResult.seller_offers = []
    return
  }
  loadingWebankSellerOffers.value = true
  try {
    const result = await fetchWebankSellerOffers(activeSessionId.value)
    webankSellerOffers.value = result.offers ?? []
    operationForms.webankCreditResult.seller_offers = webankSellerOffers.value.map((item) => ({
      offer_id: item.offer_id ?? '',
      seller_id: item.seller_id ?? '',
      marketplace_country: item.marketplace_country ?? '',
      admissionStatus: 'ADMITTED',
      applySellerBusinessSum: 0,
    }))
  } catch (error) {
    webankSellerOffers.value = []
    operationForms.webankCreditResult.seller_offers = []
    pushActivity('error', '加载 WEBANK 店铺失败', normalizeError(error))
  } finally {
    loadingWebankSellerOffers.value = false
  }
}

async function handleConnect() {
  connecting.value = true
  try {
    await establishSession({ ...connectionForm }, '会话连接成功')
  } catch (error) {
    const message = normalizeError(error)
    ElMessage.error(message === 'PHONE_NOT_FOUND' ? '该手机号不存在' : message)
    pushActivity('error', '会话连接失败', message === 'PHONE_NOT_FOUND' ? '该手机号不存在' : message)
  } finally {
    connecting.value = false
  }
}

async function handleDisconnect() {
  if (!activeSessionId.value) return
  const sessionId = activeSessionId.value
  disconnecting.value = true
  try {
    await disconnectSession(sessionId)
    pushActivity('disconnect', '会话已断开', { session_id: sessionId })
    closeSocket()
    stopSessionPolling()
    activeSessionId.value = ''
    await loadSessions()
  } catch (error) {
    pushActivity('error', '断开会话失败', normalizeError(error))
  } finally {
    disconnecting.value = false
  }
}

async function handleRegister() {
  if (onlineUsdHsbcBlocked.value) {
    showRegisterToast('warning', onlineUsdHsbcBlockedReason.value)
    return
  }
  registering.value = true
  try {
    registerAutoConnected.value = false
    registerResult.value = await registerAccount({ ...registerForm, username: authUser.value?.username })
    showRegisterToast('success', '注册成功')
    pushActivity('register', '注册完成', registerResult.value)

    if (registerResult.value?.phone_number) {
      connectionForm.env = registerForm.env
      connectionForm.phone_number = registerResult.value.phone_number
      try {
        await connectAfterRegister(registerResult.value.phone_number, registerForm.env)
        registerAutoConnected.value = true
      } catch (error) {
        pushActivity('error', '注册后自动连接失败', `${normalizeError(error)}。你也可以直接点击“连接 session”重试。`)
        registerAutoConnected.value = false
      }
    }
  } catch (error) {
    registerAutoConnected.value = false
    showRegisterToast('error', `注册失败：${normalizeError(error)}`)
    pushActivity('error', '注册失败', normalizeError(error))
  } finally {
    registering.value = false
  }
}

async function handleRegisterAndRunMultiShop() {
  if (registerAndBindingBlocked.value) {
    showRegisterToast('warning', registerAndBindingBlockedReason.value)
    return
  }
  registeringAndBinding.value = true
  try {
    registerAutoConnected.value = false
    const payload = {
      ...registerForm,
      sp_status: 'SUCCESS',
      username: authUser.value?.username,
    }
    registerResult.value = await registerAndRunMultiShop(payload)
    showRegisterToast('success', '注册成功')
    pushActivity('register', '注册并完成绑店完成', registerResult.value)

    const session = registerResult.value?.session
    const phoneNumber = session?.phone_number || registerResult.value?.register_result?.phone_number
    if (phoneNumber) {
      connectionForm.env = payload.env
      connectionForm.phone_number = phoneNumber
      try {
        await connectAfterRegister(phoneNumber, payload.env)
        registerAutoConnected.value = true
      } catch (error) {
        pushActivity('error', '注册并完成绑店后自动连接失败', `${normalizeError(error)}。你也可以直接点击“连接 session”重试。`)
      }
    }
  } catch (error) {
    registerAutoConnected.value = false
    showRegisterToast('error', `注册失败：${normalizeError(error)}`)
    pushActivity('error', '注册并完成绑店失败', normalizeError(error))
  } finally {
    registeringAndBinding.value = false
  }
}

async function handleOperationRun(operation, payloadOverrides = {}) {
  if (!activeSessionId.value) {
    pushActivity('error', '请先连接会话', '当前没有 session_id，无法执行 mock 操作。')
    return null
  }
  if (isOperationDisabled(operation)) {
    const reason = operationDisabledReason(operation)
    pushActivity('error', `${operation.title} 已禁用`, reason)
    ElMessage.warning(reason)
    return null
  }

  runningOperationKey.value = operation.key
  const requestPayload = { ...buildPayload(operation), ...payloadOverrides }
  const requestDetail = {
    method: 'POST',
    endpoint: operation.endpoint,
    body: requestPayload,
  }
  // Some mock endpoints (e.g. /api/mock/drawdown) take longer than the axios
  // default 30s to finish server-side because they fan out into multiple
  // upstream calls. Fall back to per-endpoint overrides via getScenarioStepTimeout
  // so scenario-tree runs match the longer wait users would tolerate.
  const timeoutMs = getMockOperationTimeout(operation)
  try {
    const data = await runMockOperation(operation.endpoint, requestPayload, timeoutMs ? { timeout: timeoutMs } : {})
    const successResult = buildOperationResult('success', data)
    operationResults[operation.key] = successResult
    syncDowsureFollowupFields(operation.key, data)
    showOperationToast('success', `${operation.title} 执行成功`, data)
    pushActivity('mock', `${operation.title} 已执行`, data)
    if (['pspStart', 'pspCompleted'].includes(operation.key)) {
      await loadPspAuthorizationRows()
    }
    return { request: requestDetail, response: successResult, error: false }
  } catch (error) {
    const failureResult = buildOperationResult('error', getErrorPayload(error), normalizeError(error))
    operationResults[operation.key] = failureResult
    showOperationToast('error', `${operation.title} 执行失败`, failureResult)
    pushActivity('error', `${operation.title} 执行失败`, failureResult)
    return { request: requestDetail, response: failureResult, error: true }
  } finally {
    runningOperationKey.value = ''
  }
}

async function handleScenarioStepRun(step) {
  if (step.endpoint === 'flow: register-and-run-multishop') {
    const bootstrapResult = await bootstrapScenarioSession()
    latestScenarioRunContext.value = {
      env: connectionForm.env,
      phone_number: bootstrapResult.session?.phone_number || bootstrapResult.register?.register_result?.phone_number || '',
      merchant_id: bootstrapResult.session?.merchant_id || '',
      application_unique_id: bootstrapResult.session?.application_unique_id || '',
    }
    const platformOfferId = extractPlatformOfferId(bootstrapResult)
    if (platformOfferId) {
      scenarioVariables.platform_offer_id = platformOfferId
    }
    const bootstrapKeys = interfaceAutomationSteps.value
      .filter((item) => item.endpoint === 'flow: register-and-run-multishop')
      .map((item) => item.key)
    bootstrapKeys.forEach((key) => {
      scenarioStepResults[key] = {
        status: 'success',
        at: new Date().toLocaleTimeString(),
        request: {
          method: 'POST',
          endpoint: '/api/register-and-run-multishop',
          body: getScenarioBootstrapPayload(),
        },
        response: bootstrapResult,
        payload: bootstrapResult,
      }
    })
    pushActivity('scenario', '线下注册并完成绑店完成', {
      scenario: activeInterfaceScenario.value.name,
      session_id: bootstrapResult.session?.session_id,
      phone_number: bootstrapResult.session?.phone_number,
    })
    return
  }
  if (!step.operation && step.endpoint.startsWith('/api/')) {
    const payload = buildScenarioApiPayload(step)
    const startedAt = performance.now()
    let data = null
    try {
      if (step.endpoint === '/api/mock/fp-scheduled-submit') {
        data = await runScheduledSubmitScenarioStep(step, payload, startedAt)
      } else {
        data = await runScenarioApi(step.endpoint, payload, {
          timeout: getScenarioStepTimeout(step),
        })
      }
      const durationMs = Math.round(performance.now() - startedAt)
      if (data?.success === false || data?.retryable) {
        const failure = buildOperationResult('error', data, data.error || data.message || '等待窗口内仍未拿到继续流程所需状态')
        scenarioStepResults[step.key] = {
          status: 'error',
          at: new Date().toLocaleTimeString(),
          durationMs,
          request: { method: step.method || 'POST', endpoint: step.endpoint, body: payload },
          response: failure,
          payload: failure,
        }
        pushActivity('error', `${step.title} 等待超时`, failure)
        return
      }
      scenarioStepResults[step.key] = {
        status: 'success',
        at: new Date().toLocaleTimeString(),
        durationMs,
        request: { method: step.method || 'POST', endpoint: step.endpoint, body: payload },
        response: data,
        payload: data,
      }
      // Prefer values just returned from the current step, then values
      // harvested into scenarioVariables during this run, then anything the
      // context already holds. Only fall back to the ambient session summary
      // (which may still reflect a *previous* connect) if none of the above
      // is available — this stops the header row from showing stale phone /
      // merchant details after a fresh register-and-run.
      const runPhoneCandidate = (
        data?.phone_number
        || (scenarioVariables.phone_number && !String(scenarioVariables.phone_number).startsWith('${')
          ? scenarioVariables.phone_number
          : '')
        || latestScenarioRunContext.value?.phone_number
        || sessionSummary.value?.phone_number
        || connectionForm.phone_number
        || ''
      )
      const runMerchantCandidate = (
        data?.merchant_id
        || (scenarioVariables.merchant_id && !String(scenarioVariables.merchant_id).startsWith('${')
          ? scenarioVariables.merchant_id
          : '')
        || latestScenarioRunContext.value?.merchant_id
        || sessionSummary.value?.merchant_id
        || ''
      )
      latestScenarioRunContext.value = {
        env: connectionForm.env,
        phone_number: runPhoneCandidate,
        merchant_id: runMerchantCandidate,
        application_unique_id: data?.application_unique_id || latestScenarioRunContext.value?.application_unique_id || '',
      }
      if (data?.application_unique_id) {
        scenarioVariables.application_unique_id = data.application_unique_id
      }
      if (data?.limit_application_unique_id) {
        scenarioVariables.limit_application_unique_id = data.limit_application_unique_id
      }
      if (data?.lender_approved_offer_id) {
        scenarioVariables.lender_approved_offer_id = data.lender_approved_offer_id
      }
      const platformOfferId = extractPlatformOfferId(data)
      if (platformOfferId) {
        scenarioVariables.platform_offer_id = platformOfferId
      }
      // Harvest values produced by the new /api/register/* step endpoints
      // (phone_number / email / offer_id / verification_code / token / state /
      // selling_partner_id) so the subsequent steps can interpolate them.
      const registerHarvest = ['phone_number', 'email', 'offer_id', 'verification_code', 'token', 'state', 'selling_partner_id', 'merchant_id']
      for (const key of registerHarvest) {
        const value = data?.[key]
        if (value && typeof value === 'string') {
          scenarioVariables[key] = value
        }
      }
      // create-offer 返回的 offer_id 就是上游 amazon3plOfferId，等价于后续步骤要用的
      // platform_offer_id。extractPlatformOfferId 只认包含 TESTOFFER 的值，这里显式回填，
      // 保证 DS-CNY 的 shop-performance-sql / create-application 能拿到 ${platform_offer_id}。
      if (step.endpoint === '/api/register/create-offer' && typeof data?.offer_id === 'string' && data.offer_id) {
        scenarioVariables.platform_offer_id = data.offer_id
      }
      // After the signup step the user actually exists in the DB; open a
      // session immediately so later /api/mock/* steps (create-application,
      // business-info, ...) see activeSessionId. Then push the freshly-issued
      // signup token onto the session's service so downstream calls don't have
      // to re-lookup dpu_users.token (which is sometimes absent in env).
      if (step.endpoint === '/api/register/signup' && data?.success && data?.phone_number) {
        try {
          const envForConnect = (
            scenarioVariables.env
            || activeInterfaceScenario.value?.bootstrap?.env
            || connectionForm.env
            || data?.env
            || 'reg'
          )
          await connectAfterRegister(data.phone_number, envForConnect)
          scenarioVariables.session_id = activeSessionId.value || scenarioVariables.session_id
          if (activeSessionId.value && data?.token) {
            try {
              await runScenarioApi(
                '/api/register/attach-session-token',
                {
                  session_id: activeSessionId.value,
                  token: data.token,
                  username: authUser.value?.username,
                },
                { timeout: 15000 },
              )
            } catch (tokenAttachError) {
              pushActivity('error', '注册 token 同步到 session 失败', normalizeError(tokenAttachError))
            }
          }
        } catch (error) {
          pushActivity('error', '注册后自动连接 session 失败', normalizeError(error))
        }
      }
      pushActivity('scenario', `${step.title} 已执行`, data)
    } catch (error) {
      const durationMs = Math.round(performance.now() - startedAt)
      const failure = buildOperationResult('error', getErrorPayload(error), normalizeError(error))
      scenarioStepResults[step.key] = {
        status: 'error',
        at: new Date().toLocaleTimeString(),
        durationMs,
        request: { method: step.method || 'POST', endpoint: step.endpoint, body: payload },
        response: failure,
        payload: failure,
      }
      pushActivity('error', `${step.title} 执行失败`, failure)
    }
    return
  }
  if (!step.operation) {
    const placeholder = { message: '该步骤是场景编排节点，暂未绑定单步 mock 接口。' }
    scenarioStepResults[step.key] = {
      status: 'idle',
      at: new Date().toLocaleTimeString(),
      request: { method: step.method || 'FLOW', endpoint: step.endpoint, body: step.payload || null },
      response: placeholder,
      payload: placeholder,
    }
    pushActivity('scenario', `${step.title} 是场景编排步骤，暂未绑定单步 mock 接口`, {
      scenario: activeInterfaceScenario.value.name,
      step: step.title,
      endpoint: step.endpoint,
    })
    return
  }
  activeOperationKey.value = step.key
  // Merge any user-saved scenario step overrides (e.g. amount / status /
  // failure_reason_index on approved-offer) into the payload passed to the
  // legacy operation runner. Without this the override map is silently
  // ignored for operationKey-backed steps and the request keeps using the
  // legacy operationForms defaults.
  const scenarioKey = activeInterfaceScenario.value?.key
  const overrideKey = scenarioKey ? scenarioStepOverrideKey(scenarioKey, step.key) : null
  const savedOverride = overrideKey ? scenarioStepOverrides[overrideKey] : null
  const overridePayload = {}
  if (savedOverride && step?.fields?.length) {
    for (const field of step.fields) {
      if (savedOverride[field.key] === undefined) continue
      if (!isStepFieldVisible(field, savedOverride)) continue
      overridePayload[field.key] = savedOverride[field.key]
    }
  }
  const result = await handleOperationRun(step.operation, {
    operation_name: getScenarioOperationName(step),
    ...overridePayload,
  })
  if (result) {
    scenarioStepResults[step.key] = {
      status: result.error ? 'error' : 'success',
      at: new Date().toLocaleTimeString(),
      request: result.request,
      response: result.response,
      payload: result.response,
    }
  }
}

function markScenarioStep(step, status, payload = null) {
  scenarioStepResults[step.key] = {
    status,
    at: new Date().toLocaleTimeString(),
    request: getScenarioStepRequest(step),
    response: payload,
    payload,
  }
}

function getScenarioJourney(scenario = activeInterfaceScenario.value) {
  return scenario.key === 'fpUsd2k' ? '200K' : '500K'
}

function getScenarioBootstrapConfig(scenario = activeInterfaceScenario.value) {
  return {
    currency: scenario.bootstrap?.currency || 'USD',
    funder_resource: scenario.bootstrap?.funder_resource || 'FUNDPARK',
    offline: scenario.bootstrap?.offline ?? true,
    sp_status: scenario.bootstrap?.sp_status || 'SUCCESS',
  }
}

async function bootstrapScenarioSession() {
  const env = connectionForm.env || registerForm.env || activeInterfaceScenario.value.bootstrap?.env || 'reg'
  const journey = getScenarioJourney()
  const payload = getScenarioBootstrapPayload(env, journey)
  const bootstrapConfig = getScenarioBootstrapConfig()
  registerForm.env = env
  registerForm.journey = journey
  registerForm.currency = bootstrapConfig.currency
  registerForm.funder_resource = bootstrapConfig.funder_resource
  registerForm.offline = bootstrapConfig.offline
  registerResult.value = await registerAndRunMultiShop(payload)
  const phoneNumber = registerResult.value?.session?.phone_number || registerResult.value?.register_result?.phone_number
  if (!phoneNumber) {
    throw new Error('线下注册并完成绑店成功但没有返回 phone_number')
  }
  connectionForm.env = env
  connectionForm.phone_number = phoneNumber
  const existingSession = registerResult.value?.session
  let session = existingSession
  if (existingSession?.session_id) {
    activeSessionId.value = existingSession.session_id
    selectedApplicationUniqueId.value = (
      existingSession.selected_application_unique_id
      || existingSession.application_unique_id
      || existingSession.applications?.[0]?.application_unique_id
      || ''
    )
    pushActivity('connect', '复用绑店流程返回会话', existingSession)
    await loadSessions()
    connectLogs(existingSession.session_id)
    startSessionPolling()
  } else {
    session = await connectAfterRegister(phoneNumber, env)
  }
  await loadSessions()
  registerAutoConnected.value = true
  return { register: registerResult.value, session }
}

function getScenarioBootstrapPayload(env = connectionForm.env || registerForm.env || activeInterfaceScenario.value.bootstrap?.env || 'reg', journey = getScenarioJourney()) {
  const bootstrapConfig = getScenarioBootstrapConfig()
  return {
    env,
    journey,
    currency: bootstrapConfig.currency,
    funder_resource: bootstrapConfig.funder_resource,
    offline: bootstrapConfig.offline,
    sp_status: bootstrapConfig.sp_status,
    username: authUser.value?.username,
    operation_name: `${activeInterfaceScenario.value.name}.register-and-run-multishop`,
  }
}

function getScenarioByKey(scenarioKey) {
  return interfaceScenarios.value.find((item) => item.key === scenarioKey) || activeInterfaceScenario.value
}

function buildScenarioApiPayload(step, scenario = activeInterfaceScenario.value) {
  const applyShopPerformancePreset = (payload) => {
    const selectedPreset = shopPerformancePresets.value.find(
      (preset) => preset?.name === String(payload?.access_type || '').trim(),
    )
    return selectedPreset
      ? { ...payload, custom_sql: selectedPreset.custom_sql }
      : payload
  }
  const resolved = applyShopPerformancePreset(resolveScenarioPayload(step.payload || {}))
  // Apply any user-saved overrides for this step on top of the resolved payload.
  // Hidden fields (e.g. failure_reason_index when sp_status=SUCCESS) are dropped
  // so we don't accidentally send stale values from a previous config.
  const scenarioKey = scenario?.key
  const sourceStepKey = step.sourceStepKey || step.key
  if (scenarioKey && step?.fields?.length) {
    const stored = scenarioStepOverrides[scenarioStepOverrideKey(scenarioKey, sourceStepKey)]
    if (stored && typeof stored === 'object') {
      const merged = { ...resolved }
      for (const field of step.fields) {
        const value = stored[field.key]
        if (value === undefined) continue
        if (!isStepFieldVisible(field, { ...resolved, ...stored })) {
          delete merged[field.key]
          continue
        }
        merged[field.key] = value
      }
      return {
        session_id: activeSessionId.value,
        username: authUser.value?.username,
        operation_name: getScenarioOperationName(step, scenario),
        ...applyShopPerformancePreset(merged),
      }
    }
  }
  return {
    session_id: activeSessionId.value,
    username: authUser.value?.username,
    operation_name: getScenarioOperationName(step, scenario),
    ...resolved,
  }
}

function getScenarioOperationName(step, scenario = activeInterfaceScenario.value) {
  return `${scenario.name}.${step.sourceStepKey || step.key}`
}

function resolveScenarioPayload(payload) {
  if (Array.isArray(payload)) {
    return payload.map((item) => resolveScenarioPayload(item))
  }
  if (payload && typeof payload === 'object') {
    return Object.fromEntries(
      Object.entries(payload).map(([key, value]) => [key, resolveScenarioPayload(value)]),
    )
  }
  if (typeof payload !== 'string') return payload
  const match = payload.match(/^\$\{([a-zA-Z0-9_]+)\}$/)
  if (!match) return payload
  const resolved = scenarioVariables[match[1]]
  if (!resolved || resolved === payload) return ''
  return resolved
}

function getScenarioStepTimeout(step) {
  if (step.endpoint === '/api/mock/fp-scheduled-submit') return 10 * 60 * 1000
  if (step.endpoint === '/api/mock/drawdown') return 10 * 60 * 1000
  if (step.endpoint === '/api/mock/fp-re-approved-offer') return 10 * 60 * 1000
  if (step.endpoint === '/api/mock/fp-increase-approved-offer') return 10 * 60 * 1000
  if (step.endpoint === '/api/mock/fp-increase-esign') return 10 * 60 * 1000
  // 轮询申请单状态的后端最长会等 5 分钟（dpu_application + dpu_lender_shop_data_transmission
  // 三个条件齐了才返回），前端必须给到至少 5 分钟才能拿到结果，留 20s 缓冲。
  if (step.endpoint === '/api/mock/dmf-poll-application-ready') return 320000
  if (step.endpoint === '/api/mock/kiosk-seller-id-check') return 320000
  return undefined
}

// Longer-running mock endpoints called through the legacy operation runner
// (handleOperationRun → runMockOperation) need explicit per-endpoint timeouts;
// axios' default 30s otherwise wins and drawdown/etc. show up as ETIMEDOUT
// even though the server is still finishing.
function getMockOperationTimeout(operation) {
  const endpoint = operation?.endpoint || ''
  if (endpoint === '/api/mock/drawdown') return 10 * 60 * 1000
  return null
}

// Hard 10-minute cap on how long the scheduled-submit polling loop will wait
// for the backend job to finish. If the job hasn't reached SUCCESS/FAILED by
// then we surface the timeout as a failure to the user instead of hanging.
const SCHEDULED_SUBMIT_POLL_DEADLINE_MS = 10 * 60 * 1000

async function runScheduledSubmitScenarioStep(step, payload, startedAt) {
  const startResult = await runScenarioApi(step.endpoint, payload, {
    timeout: getScenarioStepTimeout(step),
  })
  const jobId = startResult?.job_id
  if (!jobId) {
    return {
      success: false,
      error: 'scheduled-submit 已提交但没有返回 job_id，无法轮询任务状态',
      start_result: startResult,
    }
  }

  scenarioStepResults[step.key] = {
    status: 'idle',
    at: new Date().toLocaleTimeString(),
    durationMs: Math.round(performance.now() - startedAt),
    request: { method: step.method || 'POST', endpoint: step.endpoint, body: payload },
    response: startResult,
    payload: startResult,
  }
  pushActivity('scenario', `${step.title} 已提交后台任务`, { job_id: jobId })

  const deadline = performance.now() + SCHEDULED_SUBMIT_POLL_DEADLINE_MS
  let poll = 0
  while (performance.now() < deadline) {
    poll += 1
    const jobResult = await fetchScheduledSubmitJob(jobId, authUser.value?.username)
    const jobStatus = jobResult?.job_status
    scenarioStepResults[step.key] = {
      status: 'idle',
      at: new Date().toLocaleTimeString(),
      durationMs: Math.round(performance.now() - startedAt),
      request: { method: 'GET', endpoint: `/api/mock/fp-scheduled-submit/jobs/${jobId}`, body: null },
      response: jobResult,
      payload: jobResult,
    }

    if (jobStatus === 'SUCCESS' || jobStatus === 'FAILED') {
      const finalResult = jobResult?.result && typeof jobResult.result === 'object'
        ? { ...jobResult.result, job_id: jobId, job_status: jobStatus }
        : { ...jobResult, job_id: jobId, job_status: jobStatus }
      return finalResult
    }

    const retryAfter = Number(jobResult?.retry_after || 3)
    if (poll === 1 || poll % 10 === 0) {
      pushActivity('scenario', `${step.title} 后台任务轮询中`, { job_id: jobId, poll, job_status: jobStatus })
    }
    // Cap retry_after so an ill-behaved backend can't sleep beyond the
    // remaining budget; also floor at 1s to keep the loop from hot-spinning.
    const remainingMs = deadline - performance.now()
    if (remainingMs <= 0) break
    const sleepMs = Math.min(Math.max(retryAfter, 1) * 1000, remainingMs)
    await sleep(sleepMs)
  }

  return {
    success: false,
    error: 'scheduled-submit 后台任务 10 分钟内未完成，已停止轮询',
    job_id: jobId,
    job_status: 'POLL_TIMEOUT',
  }
}

function sleep(ms) {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms)
  })
}

function resetScenarioRuntimeVariables() {
  scenarioVariables.env = '${env}'
  scenarioVariables.phone_number = '${phone_number}'
  scenarioVariables.email = '${email}'
  scenarioVariables.session_id = '${session_id}'
  scenarioVariables.merchant_id = '${merchant_id}'
  scenarioVariables.platform_offer_id = '${platform_offer_id}'
  scenarioVariables.application_unique_id = '${application_unique_id}'
  scenarioVariables.limit_application_unique_id = '${limit_application_unique_id}'
  scenarioVariables.lender_approved_offer_id = '${lender_approved_offer_id}'
  scenarioVariables.offer_id = '${offer_id}'
  scenarioVariables.verification_code = '${verification_code}'
  scenarioVariables.token = '${token}'
  scenarioVariables.state = '${state}'
  scenarioVariables.selling_partner_id = '${selling_partner_id}'
}

function extractPlatformOfferId(payload) {
  if (!payload || typeof payload !== 'object') return ''
  const roots = [payload.result, payload.data, payload].filter(Boolean)
  for (const root of roots) {
    const stepOfferId = extractPlatformOfferIdFromSteps(root.steps)
    if (stepOfferId) return stepOfferId
    const direct = getValidPlatformOfferId(
      root.platform_offer_id
      || root.offer_id
      || root.register_result?.offer_id
      || root.redirect_post?.payload?.offerId
      || root.request_info?.body?.offerId,
    )
    if (direct) return direct
  }
  return ''
}

function extractPlatformOfferIdFromSteps(steps) {
  if (!Array.isArray(steps)) return ''
  const reversedSteps = [...steps].reverse()
  const preferredSteps = reversedSteps.filter((item) => (
    String(item?.step || '').includes('3PL')
    || String(item?.step || '').includes('manual offer')
    || item?.endpoint === 'dpu_manual_offer'
  ))
  for (const step of [...preferredSteps, ...reversedSteps]) {
    const candidates = [
      step?.result?.platform_offer_id,
      step?.result?.redirect_post?.payload?.offerId,
      step?.result?.request_info?.body?.offerId,
      step?.response?.platform_offer_id,
      step?.response?.body?.platform_offer_id,
      step?.response?.body?.offerId,
      step?.payload?.offerId,
    ]
    const offerId = candidates.map(getValidPlatformOfferId).find(Boolean)
    if (offerId) return offerId
  }
  return ''
}

function getValidPlatformOfferId(value) {
  const offerId = String(value || '').trim()
  if (!offerId || offerId.startsWith('${')) return ''
  if (!offerId.includes('TESTOFFER')) return ''
  return offerId
}

function getScenarioStepRequest(step) {
  if (!step) return null
  if (step.endpoint === 'flow: register-and-run-multishop') {
    return { method: 'POST', endpoint: '/api/register-and-run-multishop', body: getScenarioBootstrapPayload() }
  }
  if (!step.operation && step.endpoint.startsWith('/api/')) {
    return { method: step.method || 'POST', endpoint: step.endpoint, body: buildScenarioApiPayload(step) }
  }
  if (step.operation) {
    return { method: 'POST', endpoint: step.operation.endpoint, body: buildPayload(step.operation) }
  }
  return { method: step.method || 'FLOW', endpoint: step.endpoint, body: step.payload || null }
}

function getScenarioStepRequestBody(step) {
  const body = scenarioStepResults[step.key]?.request?.body ?? getScenarioStepRequest(step)?.body ?? null
  if (body?.request_info?.body) return body.request_info.body
  if (body?.body && body?.method && body?.url) return body.body
  return body
}

function getScenarioStepResponse(step) {
  return normalizeScenarioStepResponse(scenarioStepResults[step.key]?.response ?? scenarioStepResults[step.key]?.payload ?? null)
}

// Walk the response tree of a step and surface every "real" upstream HTTP call
// recorded by the backend. Different layers store the request snapshot under
// slightly different keys; we accept all known shapes so the two extra Tabs
// (实际请求体 / 实际请求头) can always show something useful.
function isLocalMockApiRequestUrl(url) {
  const raw = String(url || '')
  if (raw.startsWith('/api/')) return true
  try {
    const parsed = new URL(raw)
    const host = parsed.hostname
    return ['localhost', '127.0.0.1', '0.0.0.0', '::1'].includes(host) && parsed.pathname.startsWith('/api/')
  } catch {
    return false
  }
}

function getScenarioStepActualRequests(step) {
  return extractScenarioActualRequests([
    scenarioStepResults[step.key]?.response,
    scenarioStepResults[step.key]?.payload,
  ])
}

function extractScenarioActualRequests(payloads) {
  const seen = new Set()
  const out = []
  const pushRequest = (candidate) => {
    if (!candidate || typeof candidate !== 'object' || !candidate.url) return
    const url = candidate.url || ''
    if (isLocalMockApiRequestUrl(url)) return
    const method = candidate.method || candidate.http_method || 'POST'
    const headers = candidate.headers || candidate.header || null
    const params = candidate.params ?? null
    const body = candidate.body ?? candidate.json ?? candidate.payload ?? null
    const key = `${method}|${url}|${JSON.stringify(headers || {})}|${JSON.stringify(params || {})}|${JSON.stringify(body || {})}`
    if (!seen.has(key)) {
      seen.add(key)
      out.push({ url, method, headers, params, body })
    }
  }
  const visit = (node) => {
    if (!node || typeof node !== 'object') return
    if (Array.isArray(node)) {
      node.forEach(visit)
      return
    }
    if (node.redirect_get && node.redirect_url && !node.redirect_get.request_info) {
      pushRequest({
        method: 'GET',
        url: node.redirect_url,
        headers: {},
        params: node.redirect_url.includes('?') ? null : { offerId: node.platform_offer_id },
        body: null,
      })
    }
    if (node.redirect_post && node.redirect_url && !node.redirect_post.request_info) {
      pushRequest({
        method: 'POST',
        url: String(node.redirect_url).split('?')[0],
        headers: { 'Content-Type': 'application/json' },
        params: null,
        body: node.redirect_post.payload ?? null,
      })
    }
    const candidate = node.request_info || node.actual_request
    if (candidate && typeof candidate === 'object' && candidate.url) {
      const url = candidate.url || ''
      if (isLocalMockApiRequestUrl(url)) {
        for (const value of Object.values(node)) {
          if (value && typeof value === 'object') visit(value)
        }
        return
      }
      pushRequest(candidate)
    }
    for (const value of Object.values(node)) {
      if (value && typeof value === 'object') visit(value)
    }
  }
  ;(Array.isArray(payloads) ? payloads : [payloads]).forEach(visit)
  return out
}

function getScenarioStepActualResponses(step) {
  return extractScenarioActualResponses([
    scenarioStepResults[step.key]?.response,
    scenarioStepResults[step.key]?.payload,
  ])
}

function extractScenarioActualResponses(payloads) {
  const seen = new Set()
  const out = []
  const pushResponse = (candidate) => {
    if (!candidate || typeof candidate !== 'object') return
    const body = candidate.json
      ?? parseMaybeJson(candidate.body)
      ?? candidate.body
      ?? candidate.response_json
      ?? parseMaybeJson(candidate.response_body)
      ?? candidate.response_body
      ?? null
    const statusCode = candidate.status_code ?? null
    const headers = candidate.headers ?? candidate.response_headers ?? null
    const key = `${statusCode || ''}|${JSON.stringify(headers || {})}|${JSON.stringify(body || '')}`
    if (!seen.has(key)) {
      seen.add(key)
      out.push({ status_code: statusCode, headers, body })
    }
  }
  const visit = (node) => {
    if (!node || typeof node !== 'object') return
    if (Array.isArray(node)) {
      node.forEach(visit)
      return
    }
    if (node.redirect_get && !node.redirect_get.response_info) pushResponse(node.redirect_get)
    if (node.redirect_post && !node.redirect_post.response_info) pushResponse(node.redirect_post)
    const responseInfo = node.response_info || node.actual_response || null
    const hasResponseShape = responseInfo || node.response_json !== undefined || node.response_body !== undefined
    if (hasResponseShape) {
      pushResponse(responseInfo || node)
    }
    for (const value of Object.values(node)) {
      if (value && typeof value === 'object') visit(value)
    }
  }
  ;(Array.isArray(payloads) ? payloads : [payloads]).forEach(visit)
  return out
}

function getScenarioHistoryStepActualRequests(step) {
  return extractScenarioActualRequests([step?.response, step?.payload])
}

function getScenarioHistoryStepActualResponses(step) {
  return extractScenarioActualResponses([step?.response, step?.payload])
}

function getScenarioHistoryStepDisplayRequest(step) {
  if (scenarioHistoryDetailPayloadMode.value !== 'actual') return step?.request ?? null
  const actualRequests = getScenarioHistoryStepActualRequests(step)
  return actualRequests.length ? actualRequests : null
}

function getScenarioHistoryStepDisplayResponse(step) {
  if (scenarioHistoryDetailPayloadMode.value !== 'actual') return step?.response ?? null
  const actualResponses = getScenarioHistoryStepActualResponses(step)
  return actualResponses.length ? actualResponses : null
}

function parseMaybeJson(value) {
  if (!value || typeof value !== 'string') return null
  try {
    return JSON.parse(value)
  } catch {
    return null
  }
}

function pickTraceId(payload, body) {
  return (
    body?.traceId
    || payload?.traceId
    || payload?.response_info?.headers?.traceId
    || payload?.response_info?.headers?.['X-Trace-Id']
    || payload?.response_headers?.traceId
    || payload?.response_headers?.['X-Trace-Id']
    || null
  )
}

function getResponseBody(payload) {
  if (!payload || typeof payload !== 'object') return payload
  return (
    payload.response_json
    || payload.response_info?.json
    || parseMaybeJson(payload.response_body)
    || parseMaybeJson(payload.response_info?.body)
    || parseMaybeJson(payload.response)
    || payload.data
    || payload
  )
}

function normalizeNestedStepResult(step) {
  const request = step.payload ?? step.request ?? step.request_body ?? null
  const responsePayload = step.result ?? step.response ?? null
  return {
    step: step.step || step.name || step.title || null,
    endpoint: step.endpoint || step.url || null,
    request,
    response: normalizeScenarioStepResponse(responsePayload),
  }
}

function normalizeScenarioStepResponse(payload) {
  if (!payload) return null
  if (typeof payload !== 'object') return payload

  const body = getResponseBody(payload)

  if (body && typeof body === 'object' && Array.isArray(body.steps)) {
    const normalizedBody = {
      success: body.success ?? payload.success ?? null,
      application_unique_id: body.application_unique_id ?? payload.application_unique_id ?? null,
      steps: body.steps.map(normalizeNestedStepResult),
    }
    return {
      success: payload.success ?? body.success ?? body.isSuccess ?? null,
      status_code: payload.status_code ?? payload.response_info?.status_code ?? body.code ?? null,
      traceId: pickTraceId(payload, body),
      body: normalizedBody,
    }
  }

  const normalized = {
    success: payload.success ?? body?.success ?? body?.isSuccess ?? null,
    status_code: payload.status_code ?? payload.response_info?.status_code ?? body?.code ?? null,
    traceId: pickTraceId(payload, body),
    body,
  }

  if (payload.error_message) normalized.error_message = payload.error_message
  return normalized
}

function getScenarioStepDetailTab(step) {
  return scenarioStepDetailTabs[step.key] || 'params'
}

function setScenarioStepDetailTab(step, tab) {
  scenarioStepDetailTabs[step.key] = tab
}

function getScenarioStepDescription(step) {
  const request = getScenarioStepRequest(step)
  const fields = step.operation?.fields || []
  return {
    title: step.title,
    kind: step.kind,
    method: request?.method || step.method || 'FLOW',
    endpoint: request?.endpoint || step.endpoint,
    description: step.operation?.description || (
      step.type === 'flow'
        ? `${step.title} 由场景执行器统一驱动，执行服务端流程后会回填该节点结果。`
        : `${step.title} 是当前场景中的接口编排步骤。`
    ),
    fieldCount: fields.length,
    fields: fields.map((field) => ({
      label: field.label,
      prop: field.prop,
      type: field.type || 'text',
    })),
  }
}

function getScenarioStepSourceEndpoint(step) {
  if (!step) return ''
  const request = getScenarioStepRequest(step)
  return request?.endpoint || step.operation?.endpoint || step.endpoint || ''
}

function getScenarioStepLogicRequest(step) {
  if (!step) return null
  const actualRequest = getScenarioStepActualRequests(step)[0]
  if (!actualRequest) return null
  return {
    method: actualRequest.method || 'POST',
    endpoint: actualRequest.url || '',
    body: actualRequest.body ?? null,
  }
}

function getScenarioStepPlannedRequests(step) {
  return getScenarioStepLogic(step)?.planned_requests || []
}

function formatScenarioRequestValue(value) {
  if (value == null || value === '') return '(无)'
  if (typeof value === 'string') return value
  return JSON.stringify(value, null, 2)
}

function getScenarioStepLogic(step) {
  const endpoint = getScenarioStepSourceEndpoint(step)
  if (!endpoint) return null
  return scenarioStepSourceCache[endpoint] || {
    language: 'Python',
    endpoint,
    planned_requests: [],
    blocks: [],
  }
}

async function loadScenarioStepLogicSource(step) {
  const endpoint = getScenarioStepSourceEndpoint(step)
  if (!endpoint) return null
  if (scenarioStepSourceCache[endpoint]) return scenarioStepSourceCache[endpoint]
  if (scenarioStepSourceLoading[endpoint]) {
    for (let i = 0; i < 20; i += 1) {
      await new Promise((resolve) => setTimeout(resolve, 50))
      if (!scenarioStepSourceLoading[endpoint]) return scenarioStepSourceCache[endpoint] || null
    }
    return scenarioStepSourceCache[endpoint] || null
  }
  scenarioStepSourceLoading[endpoint] = true
  delete scenarioStepSourceErrors[endpoint]
  try {
    scenarioStepSourceCache[endpoint] = await fetchScenarioStepSource(endpoint)
    return scenarioStepSourceCache[endpoint]
  } catch (error) {
    scenarioStepSourceErrors[endpoint] = error?.payload?.message || error?.message || '源码加载失败'
    return null
  } finally {
    scenarioStepSourceLoading[endpoint] = false
  }
}

function getScenarioResponseState(step) {
  const status = scenarioStepResults[step.key]?.status
  if (status === 'error') return { type: 'danger', label: 'Error' }
  if (status === 'success') return { type: 'success', label: 'Latest' }
  return { type: 'info', label: 'Empty' }
}

function hasScenarioStepDetail(step) {
  return Boolean(expandedScenarioSteps[step.key] || selectedInterfaceStep.value?.key === step.key || scenarioStepResults[step.key])
}

function toggleScenarioStep(step) {
  activeOperationKey.value = step.key
  expandedScenarioSteps[step.key] = !expandedScenarioSteps[step.key]
}

function toggleScenarioTreeNode(scenarioKey) {
  expandedScenarioTrees[scenarioKey] = !expandedScenarioTrees[scenarioKey]
}

function scenarioDirectoryExpanded(directoryKey) {
  return Boolean(expandedScenarioDirectories[directoryKey] || scenarioLibrarySearch.value.trim())
}

function toggleScenarioDirectory(directoryKey) {
  expandedScenarioDirectories[directoryKey] = !expandedScenarioDirectories[directoryKey]
}

function scenarioCategoryForKey(scenarioKey) {
  return interfaceScenarios.value.find((item) => item.key === scenarioKey)?.category || 'singleShop'
}

function selectScenarioFromTree(scenarioKey) {
  activeInterfaceScenarioKey.value = scenarioKey
  expandedScenarioDirectories[scenarioCategoryForKey(scenarioKey)] = true
  expandedScenarioTrees[scenarioKey] = !expandedScenarioTrees[scenarioKey]
  interfacePageMode.value = 'scenario'
  interfaceFocusMode.value = 'scenario'
}

function selectStepFromTree(scenarioKey, stepKey) {
  activeOperationKey.value = stepKey
  interfaceFocusMode.value = 'step'
  interfacePageMode.value = 'scenario'
  stepFocusTab.value = 'params'
  debugRequestError.value = ''
  expandedScenarioSteps[stepKey] = true
  activeInterfaceScenarioKey.value = scenarioKey
  expandedScenarioDirectories[scenarioCategoryForKey(scenarioKey)] = true
  expandedScenarioTrees[scenarioKey] = true
}

async function selectDebugInterface(stepKey) {
  interfacePageMode.value = 'debug'
  interfaceFocusMode.value = 'step'
  stepFocusTab.value = 'actualBody'
  activeOperationKey.value = stepKey
  await prepareDebugRequestDraft(debugInterfaceSteps.value.find((step) => step.key === stepKey))
}

async function switchInterfacePageMode(mode) {
  interfacePageMode.value = mode
  if (mode === 'debug') {
    interfaceFocusMode.value = 'step'
    const visibleDebugSteps = filteredDebugInterfaceSteps.value.length
      ? filteredDebugInterfaceSteps.value
      : debugInterfaceSteps.value
    if (!visibleDebugSteps.some((step) => step.key === activeOperationKey.value)) {
      activeOperationKey.value = visibleDebugSteps[0]?.key || ''
    }
    stepFocusTab.value = 'actualBody'
    await prepareDebugRequestDraft()
    return
  }
  interfaceFocusMode.value = 'scenario'
}

function getDebugStepEndpoint(step) {
  return step?.endpoint || step?.operation?.endpoint || ''
}

function getDebugStepPayload(step) {
  if (!step) return {}
  if (getDebugStepEndpoint(step).startsWith('/api/')) {
    return buildScenarioApiPayload(step, getScenarioByKey(step.sourceScenarioKey))
  }
  if (step.operation) {
    return buildPayload(step.operation)
  }
  return step.payload || {}
}

function getCurrentUpstreamBaseUrl() {
  const env = String(connectionForm.env || registerForm.env || activeInterfaceScenario.value?.bootstrap?.env || 'reg').toLowerCase()
  return upstreamBaseUrls[env] || `https://dpu-gateway-${env}.dowsure.com`
}

function joinUpstreamUrl(path) {
  if (!path) return ''
  if (/^https?:\/\//i.test(path)) return path
  return `${getCurrentUpstreamBaseUrl()}${path.startsWith('/') ? path : `/${path}`}`
}

function normalizeDebugUpstreamUrl(value) {
  const raw = String(value || '').trim()
  if (!raw) return ''
  if (/^https?:\/\//i.test(raw)) {
    const fullUrlPathMatch = raw.match(/^https?:\/\/[^/]+(\/dpu-[^'"`{}\s)]*)/i)
    return fullUrlPathMatch ? joinUpstreamUrl(fullUrlPathMatch[1]) : raw
  }

  const withoutPrefix = raw
    .replace(/^[fFrRbBuU]+(?=["'`])/, '')
    .replace(/^["'`]+|["'`,)]+$/g, '')
    .trim()

  if (apiConfigEndpointPaths[withoutPrefix]) {
    return joinUpstreamUrl(apiConfigEndpointPaths[withoutPrefix])
  }

  const apiConfigMatch = withoutPrefix.match(/(?:self\.)?api_config\.[A-Za-z_][A-Za-z0-9_]*/)
  if (apiConfigMatch && apiConfigEndpointPaths[apiConfigMatch[0]]) {
    return joinUpstreamUrl(apiConfigEndpointPaths[apiConfigMatch[0]])
  }

  const dpuPathMatch = withoutPrefix.match(/\/dpu-[^'"`{}\s)]*/)
  if (dpuPathMatch) {
    return joinUpstreamUrl(dpuPathMatch[0])
  }

  if (withoutPrefix.startsWith('/')) return joinUpstreamUrl(withoutPrefix)
  return withoutPrefix
}

function getDebugActualRequestSeed(step) {
  if (!step) {
    return {
      method: 'POST',
      url: '',
      headers: { 'Content-Type': 'application/json' },
      body: {},
    }
  }
  const actual = getScenarioStepActualRequests(step)[0] || null
  const planned = getScenarioStepPlannedRequests(step)[0] || null
  const source = actual || planned || {}
  const method = source.method || source.http_method || step.method || 'POST'
  const url = normalizeDebugUpstreamUrl(source.url || source.endpoint || '')
  const headers = source.headers || source.header || { 'Content-Type': 'application/json' }
  const body = source.body ?? source.json ?? source.payload ?? getDebugStepPayload(step)
  return {
    method,
    url,
    headers,
    body,
  }
}

function splitDebugUrlAndQuery(value) {
  const raw = String(value || '').trim()
  if (!raw) return { url: '', query: {} }
  try {
    const parsed = new URL(raw)
    const query = {}
    parsed.searchParams.forEach((valueItem, key) => {
      if (query[key] === undefined) {
        query[key] = valueItem
      } else if (Array.isArray(query[key])) {
        query[key].push(valueItem)
      } else {
        query[key] = [query[key], valueItem]
      }
    })
    parsed.search = ''
    return { url: parsed.toString(), query }
  } catch {
    const [base, queryString] = raw.split('?', 2)
    const query = {}
    if (queryString) {
      new URLSearchParams(queryString).forEach((valueItem, key) => {
        if (query[key] === undefined) query[key] = valueItem
        else if (Array.isArray(query[key])) query[key].push(valueItem)
        else query[key] = [query[key], valueItem]
      })
    }
    return { url: base || raw, query }
  }
}

function buildDebugUrlWithQuery(value, query) {
  const raw = String(value || '').trim()
  if (!raw || !query || typeof query !== 'object' || !Object.keys(query).length) return raw
  const appendParams = (params) => {
    Object.entries(query).forEach(([key, val]) => {
      if (val == null || val === '') return
      if (Array.isArray(val)) {
        val.forEach((item) => {
          if (item != null && item !== '') params.append(key, String(item))
        })
      } else {
        params.set(key, String(val))
      }
    })
  }
  try {
    const parsed = new URL(raw)
    appendParams(parsed.searchParams)
    return parsed.toString()
  } catch {
    const params = new URLSearchParams(raw.includes('?') ? raw.split('?').slice(1).join('?') : '')
    appendParams(params)
    const base = raw.split('?')[0]
    const queryString = params.toString()
    return queryString ? `${base}?${queryString}` : base
  }
}

async function prepareDebugRequestDraft(step = selectedInterfaceStep.value) {
  resetDebugRequestDraft(step)
  if (!step) return
  await loadScenarioStepLogicSource(step)
  if (interfacePageMode.value === 'debug' && selectedInterfaceStep.value?.key === step.key) {
    resetDebugRequestDraft(step)
  }
}

function resetDebugRequestDraft(step = selectedInterfaceStep.value) {
  const seed = getDebugActualRequestSeed(step)
  const splitUrl = splitDebugUrlAndQuery(seed.url)
  debugRequestError.value = ''
  debugActualMethod.value = seed.method || 'POST'
  debugActualUrlText.value = splitUrl.url || ''
  debugRequestQueryText.value = JSON.stringify(splitUrl.query || {}, null, 2)
  debugRequestHeadersText.value = JSON.stringify(normalizeDebugJsonDraftValue(seed.headers || { 'Content-Type': 'application/json' }), null, 2)
  debugRequestBodyText.value = JSON.stringify(normalizeDebugJsonDraftValue(seed.body ?? {}), null, 2)
}

function normalizeDebugJsonDraftValue(value) {
  let current = value
  for (let i = 0; i < 3; i += 1) {
    if (typeof current !== 'string') return current
    const trimmed = current.trim()
    if (!trimmed) return {}
    try {
      current = JSON.parse(trimmed)
    } catch {
      return current
    }
  }
  return current
}

function parseDebugJson(text, label) {
  const raw = String(text || '').trim()
  if (!raw) return {}
  try {
    return normalizeDebugJsonDraftValue(JSON.parse(raw))
  } catch (error) {
    throw new Error(`${label} 不是合法 JSON：${error.message}`)
  }
}

function prettifyDebugJsonDraft(kind) {
  const configs = {
    headers: { ref: debugRequestHeadersText, label: '请求头', tab: 'actualHeaders' },
    body: { ref: debugRequestBodyText, label: '请求体', tab: 'actualBody' },
    query: { ref: debugRequestQueryText, label: 'Query', tab: 'actualQuery' },
  }
  const config = configs[kind]
  if (!config) return
  try {
    const value = parseDebugJson(config.ref.value, config.label)
    config.ref.value = JSON.stringify(value, null, 2)
    debugRequestError.value = ''
    ElMessage({ type: 'success', message: `${config.label}已格式化`, duration: 1200 })
  } catch (error) {
    stepFocusTab.value = config.tab
    debugRequestError.value = error.message
  }
}

async function handleDebugStepRun() {
  const step = selectedInterfaceStep.value
  if (!step) {
    debugRequestError.value = '请选择一个 /api 接口步骤'
    return
  }
  const url = debugActualUrlText.value.trim()
  if (!url) {
    debugRequestError.value = '请先填写实际上游 URL'
    stepFocusTab.value = 'actualBody'
    return
  }
  let headers
  let body
  let query
  try {
    headers = parseDebugJson(debugRequestHeadersText.value, '请求头')
    body = parseDebugJson(debugRequestBodyText.value, '请求体')
    query = parseDebugJson(debugRequestQueryText.value, 'Query')
  } catch (error) {
    debugRequestError.value = error.message
    return
  }

  debugRequestError.value = ''
  debugSending.value = true
  const startedAt = performance.now()
  const method = debugActualMethod.value || step.method || 'POST'
  const requestUrl = buildDebugUrlWithQuery(url, query)
  const debugScenario = getScenarioByKey(step.sourceScenarioKey)
  try {
    const data = await runScenarioApi('/api/mock/upstream-debug', {
      method,
      url: requestUrl,
      headers,
      body,
      timeout_seconds: Math.max(1, Math.ceil((getScenarioStepTimeout(step) || 60000) / 1000)),
      username: authUser.value?.username,
      operation_name: `${debugScenario?.name || 'debug'}.${step.sourceStepKey || step.key}.upstream-debug`,
    }, {
      timeout: getScenarioStepTimeout(step) || 60000,
    })
    const durationMs = Math.round(performance.now() - startedAt)
    scenarioStepResults[step.key] = {
      status: data?.success === false ? 'error' : 'success',
      at: new Date().toLocaleTimeString(),
      durationMs,
      request: { method, endpoint: requestUrl, headers, query, body },
      response: data,
      payload: data,
    }
    pushActivity('scenario', `${step.title} 调试执行完成`, data)
  } catch (error) {
    const durationMs = Math.round(performance.now() - startedAt)
    const failure = buildOperationResult('error', getErrorPayload(error), normalizeError(error))
    scenarioStepResults[step.key] = {
      status: 'error',
      at: new Date().toLocaleTimeString(),
      durationMs,
      request: { method, endpoint: requestUrl, headers, query, body },
      response: failure,
      payload: failure,
    }
    debugRequestError.value = failure.error || failure.message || '调试请求失败'
    pushActivity('error', `${step.title} 调试失败`, failure)
  } finally {
    debugSending.value = false
  }
}

function scenarioStepStatus(stepKey) {
  return scenarioStepResults[stepKey]?.status || 'idle'
}

function methodBadgeClass(step) {
  if (!step) return 'is-post'
  if (step.type === 'script') return 'is-script'
  const method = (step.method || 'POST').toUpperCase()
  if (method === 'GET') return 'is-get'
  if (method === 'PUT') return 'is-put'
  if (method === 'DELETE') return 'is-delete'
  if (method === 'PATCH') return 'is-patch'
  return 'is-post'
}

function formatStepDuration(ms) {
  if (ms == null) return ''
  if (ms < 1000) return `${ms} ms`
  return `${(ms / 1000).toFixed(2)} s`
}

async function copyResponseText(payload) {
  if (payload == null) return
  const text = typeof payload === 'string' ? payload : JSON.stringify(payload, null, 2)
  try {
    await navigator.clipboard.writeText(text)
    ElMessage({ type: 'success', message: '已复制到剪贴板', duration: 1500 })
  } catch (error) {
    ElMessage({ type: 'warning', message: '复制失败，请手动选择文本', duration: 2000 })
  }
}

function renderMarkdown(text) {
  if (!text) return ''
  // 解码 JSON unicode 转义序列（如 \u003d → =）和字面 \n，让粘贴的 JSON 字符串可读
  const decoded = text
    .replace(/\\u([0-9a-fA-F]{4})/g, (_, h) => String.fromCharCode(parseInt(h, 16)))
    .replace(/\\n/g, '\n')
    .replace(/\\t/g, '\t')
  const html = marked.parse(decoded, { breaks: true, gfm: true })
  return html.replace(
    /<pre><code(?: class="language-([^"]*)")?>([\s\S]*?)<\/code><\/pre>/g,
    (_, lang, code) => {
      const label = lang || 'plaintext'
      const raw = code.replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#39;/g, "'")
      const escaped = raw.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      return `<div class="chat-code-block"><div class="chat-code-header"><span class="chat-code-lang">${label}</span><button type="button" class="chat-code-copy" data-code="${encodeURIComponent(raw)}"><svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg> 复制</button></div><pre class="chat-code-pre"><code>${escaped}</code></pre></div>`
    }
  )
}

async function onChatBubbleClick(event) {
  const btn = event.target.closest('.chat-code-copy')
  if (!btn) return
  const raw = decodeURIComponent(btn.dataset.code || '')
  try {
    await navigator.clipboard.writeText(raw)
    const original = btn.innerHTML
    btn.innerHTML = '✓ 已复制'
    btn.disabled = true
    setTimeout(() => { btn.innerHTML = original; btn.disabled = false }, 1800)
  } catch {
    ElMessage({ type: 'warning', message: '复制失败，请手动选择文本', duration: 2000 })
  }
}

function renderInlineText(text) {
  if (!text) return ''
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/`([^`]+)`/g, '<code class="chat-inline-code">$1</code>')
    .replace(/\n/g, '<br>')
}

function parseChatContent(text) {
  if (!text) return [{ type: 'text', content: '' }]
  const segments = []
  const codeBlockRegex = /```(\w*)\n?([\s\S]*?)```/g
  let lastIndex = 0
  let match
  while ((match = codeBlockRegex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      segments.push({ type: 'text', content: text.slice(lastIndex, match.index) })
    }
    const lang = match[1] || 'plaintext'
    segments.push({ type: 'code', lang, content: match[2].replace(/\n$/, '') })
    lastIndex = match.index + match[0].length
  }
  if (lastIndex < text.length) {
    segments.push({ type: 'text', content: text.slice(lastIndex) })
  }
  return segments.length ? segments : [{ type: 'text', content: text }]
}

function restoreScenarioExecutionHistory() {
  try {
    const raw = window.localStorage.getItem(scenarioHistoryStorageKey)
    if (!raw) return
    const parsed = JSON.parse(raw)
    if (Array.isArray(parsed)) {
      scenarioExecutionHistory.value = parsed
    }
  } catch (error) {
    window.localStorage.removeItem(scenarioHistoryStorageKey)
  }
}

function persistScenarioExecutionHistory() {
  try {
    window.localStorage.setItem(scenarioHistoryStorageKey, JSON.stringify(scenarioExecutionHistory.value))
  } catch (error) {
    pushActivity('error', '执行历史保存失败', normalizeError(error))
  }
}

function cloneScenarioPayload(payload) {
  if (payload === undefined) return null
  try {
    return JSON.parse(JSON.stringify(payload))
  } catch (error) {
    return String(payload)
  }
}

function buildScenarioStepSnapshot(step, fallbackStatus = 'idle') {
  const result = scenarioStepResults[step.key]
  return {
    key: step.key,
    order: step.order,
    title: step.title,
    kind: step.kind,
    method: result?.request?.method || step.method || 'POST',
    endpoint: result?.request?.endpoint || step.endpoint,
    status: result?.status || fallbackStatus,
    at: result?.at || null,
    request: cloneScenarioPayload(result?.request ?? getScenarioStepRequest(step)),
    response: cloneScenarioPayload(result?.response ?? result?.payload ?? null),
    error_message: result?.response?.error_message || result?.payload?.error_message || result?.response?.message || null,
  }
}

function buildScenarioRunStepSnapshots(enabledSteps) {
  return enabledSteps.map((step) => buildScenarioStepSnapshot(step, step.enabled === false ? 'skipped' : 'idle'))
}

function addScenarioExecutionRecord(record) {
  scenarioExecutionHistory.value = [record, ...scenarioExecutionHistory.value]
}

function openScenarioHistoryDetail(record) {
  selectedScenarioHistoryRecord.value = record
  scenarioHistoryDetailPayloadMode.value = 'mock'
  scenarioHistoryDetailVisible.value = true
}

// Build a human-readable summary block for the scenario history drawer.
// Success → headline + total count, no failures.
// Stopped → headline "已停止", no failures (treated as user action).
// Failure → headline "失败", and list the offending steps' titles + messages.
function scenarioHistoryRecordOutcome(record) {
  if (!record) return { variant: 'idle', tagType: 'info', headline: '未执行', body: '', failures: [] }
  const status = record.status || '未执行'
  const failures = (record.steps || [])
    .filter((step) => step?.status === 'error')
    .map((step) => ({
      title: step.title || step.key,
      message: step.error_message || '未提供错误信息',
    }))
  if (status === '完成' && failures.length === 0) {
    return {
      variant: 'success',
      tagType: 'success',
      headline: '执行成功',
      body: `场景全部 ${record.steps?.length || 0} 个步骤已完成。`,
      failures: [],
    }
  }
  if (status === '已停止') {
    return {
      variant: 'warning',
      tagType: 'warning',
      headline: '已停止',
      body: '用户在执行过程中点了停止，剩余步骤未执行。',
      failures,
    }
  }
  if (status === '未执行') {
    return {
      variant: 'warning',
      tagType: 'warning',
      headline: '未执行',
      body: '执行前校验失败，例如没有连接 session。',
      failures: [],
    }
  }
  // Default to failure
  const firstFailure = failures[0]
  const body = firstFailure
    ? `${failures.length} 个步骤失败，首个失败：${firstFailure.title} — ${firstFailure.message}`
    : '场景执行失败。'
  return {
    variant: 'danger',
    tagType: 'danger',
    headline: '执行失败',
    body,
    failures,
  }
}

function getScenarioBootstrapKeys() {
  return interfaceAutomationSteps.value
    .filter((item) => [
      'flow: register-and-run-multishop',
      'flow: create-application-from-session',
      'flow: offer-limit-selected',
      'flow: linked-during-bootstrap',
      'flow: offer-quote-confirmed',
    ].includes(item.endpoint))
    .map((item) => item.key)
}

function getScenarioPostBootstrapFlowKeys() {
  return interfaceAutomationSteps.value
    .filter((item) => ['underwritten', 'approvedOffer', 'pspStart', 'pspCompleted', 'esign', 'drawdown'].includes(item.operationKey))
    .map((item) => item.key)
}

async function handleScenarioSave() {
  const scenario = activeInterfaceScenario.value
  if (!scenario) return
  if (!authUser.value?.username) {
    ElMessage.warning('请先登录后再保存场景')
    return
  }
  scenarioSaveState.value = '保存中'
  const scenarioKey = scenario.key
  const steps = scenario.steps || []
  try {
    // Save each step's enabled flag (merged with any existing param overrides)
    // to scenario_step_overrides so the choice sticks across reloads / browsers.
    await Promise.all(steps.map(async (step) => {
      const enabled = interfaceStepEnabled[step.key] !== false
      const overrideKey = scenarioStepOverrideKey(scenarioKey, step.key)
      const existing = scenarioStepOverrides[overrideKey] || {}
      // Strip _enabled from copy so we can rebuild it cleanly below.
      const paramValues = { ...existing }
      delete paramValues._enabled
      // Skip writing a row when the step is enabled AND has no stored param
      // overrides — no point in polluting the table with default rows. If a
      // previous save wrote `_enabled=false` and the user re-enabled it, we
      // fall through and rewrite with `_enabled=true` so the DB catches up.
      const hasParamOverride = Object.keys(paramValues).length > 0
      const previouslyDisabled = existing._enabled === false
      if (enabled && !hasParamOverride && !previouslyDisabled) return
      const payload = { ...paramValues, _enabled: enabled }
      await saveScenarioStepOverride({
        username: authUser.value.username,
        scenario_key: scenarioKey,
        step_key: step.key,
        payload,
      })
      scenarioStepOverrides[overrideKey] = payload
    }))
    // Persist the drag-and-drop step order (if the user rearranged anything).
    // Only writes when there's a draft — leaves any previously-saved order
    // untouched otherwise.
    if (Array.isArray(scenarioStepOrderDraft[scenarioKey]) && scenarioStepOrderDraft[scenarioKey].length) {
      const draftOrder = scenarioStepOrderDraft[scenarioKey].slice()
      await saveScenarioStepOrder({
        username: authUser.value.username,
        scenario_key: scenarioKey,
        step_order: draftOrder,
      })
      scenarioStepOrders[scenarioKey] = draftOrder
      delete scenarioStepOrderDraft[scenarioKey]
    }
    await saveScenarioStepOrder({
      username: authUser.value.username,
      scenario_key: `${scenarioKey}::structure`,
      step_order: [
        JSON.stringify({
          added: scenarioStepStructureDraft[scenarioKey] || [],
          deleted: scenarioStepStructureDeleted[scenarioKey] || [],
        }),
      ],
    })
    delete scenarioStepStructureDraft[scenarioKey]
    delete scenarioStepStructureDeleted[scenarioKey]
    scenarioSaveState.value = `已保存 ${new Date().toLocaleTimeString()}`
    pushActivity('scenario', `${scenario.name} 已保存`, {
      scenario: scenario.name,
      enabled_steps: enabledInterfaceStepCount.value,
    })
    ElMessage.success('场景已保存')
  } catch (error) {
    scenarioSaveState.value = '保存失败'
    ElMessage.error(error?.payload?.message || error?.message || '保存失败')
  }
}

function handleScenarioCreate() {
  activeInterfaceScenarioKey.value = 'fpUsd2k'
  activeScenarioTab.value = 'base'
  scenarioSaveState.value = '未保存'
  ElMessage.success('已创建 FP-USD-2K 场景草稿')
  pushActivity('scenario', '新建场景草稿', { scenario: 'FP-USD-2K' })
}

function handleScenarioImport() {
  activeInterfaceScenarioKey.value = 'fpUsd500k'
  activeScenarioTab.value = 'steps'
  ElMessage.success('已导入 FP-USD-500K 场景模板')
  pushActivity('scenario', '导入场景模板', { scenario: 'FP-USD-500K', steps: 18 })
}

function handleScenarioAddStep() {
  activeScenarioTab.value = 'steps'
  ElMessage.info('当前场景步骤来自 MeterSphere 模板，新增步骤请先在模板中维护。')
  pushActivity('scenario', '点击添加步骤', { scenario: activeInterfaceScenario.value.name })
}

async function handleScenarioServerExecute() {
  if (scenarioExecuting.value) return
  if (scenarioSettings.validateSession && !activeSessionId.value) {
    const record = {
      id: `${Date.now()}`,
      scenario: activeInterfaceScenario.value.name,
      env: connectionForm.env,
      at: new Date().toLocaleString(),
      duration: '0s',
      success: 0,
      skipped: 0,
      failed: enabledInterfaceStepCount.value,
      status: '未执行',
      context: cloneScenarioPayload(latestScenarioRunContext.value),
      steps: buildScenarioRunStepSnapshots(interfaceAutomationSteps.value.filter((step) => step.enabled)),
    }
    addScenarioExecutionRecord(record)
    ElMessage.warning('执行前校验失败：请先连接 session')
    pushActivity('scenario', `${record.scenario} 执行前校验失败`, record)
    activeScenarioTab.value = 'history'
    return
  }
  scenarioExecuting.value = true
  scenarioStopRequested.value = false
  // Clear previous run's step dots/responses so the tree shows a fresh state.
  Object.keys(scenarioStepResults).forEach((key) => {
    delete scenarioStepResults[key]
  })
  try {
    latestScenarioRunContext.value = null
    resetScenarioRuntimeVariables()
    // Seed env into scenarioVariables so register-step scenarios can resolve
    // ${env}. The env picker in the toolbar (connectionForm.env) always wins,
    // otherwise the scenario would silently run against its bootstrap default
    // (e.g. reg) even after the user changed the dropdown to uat.
    const scenarioEnvSeed = (
      connectionForm.env
      || registerForm.env
      || activeInterfaceScenario.value?.bootstrap?.env
      || 'reg'
    )
    if (scenarioEnvSeed) {
      scenarioVariables.env = scenarioEnvSeed
    }
    const startedAt = new Date()
    const enabledSteps = interfaceAutomationSteps.value.filter((step) => step.enabled)
    let successCount = 0
    let skippedCount = 0
    let failCount = 0
    let bootstrapDone = false
    let stoppedByUser = false

    for (const step of enabledSteps) {
      if (scenarioStopRequested.value) {
        stoppedByUser = true
        break
      }
      if (step.endpoint === 'flow: register-and-run-multishop') {
        if (!bootstrapDone) {
          try {
            const bootstrapResult = await bootstrapScenarioSession()
            getScenarioBootstrapKeys().forEach((key) => {
              scenarioStepResults[key] = {
                status: 'success',
                at: new Date().toLocaleTimeString(),
                request: {
                  method: 'POST',
                  endpoint: '/api/register-and-run-multishop',
                  body: getScenarioBootstrapPayload(),
                },
                response: bootstrapResult,
                payload: bootstrapResult,
              }
            })
            const bootstrapCount = interfaceAutomationSteps.value
              .filter((item) => (
                item.enabled
                && item.endpoint === 'flow: register-and-run-multishop'
              ))
              .length
            successCount += bootstrapCount
            bootstrapDone = true
            const platformOfferId = extractPlatformOfferId(bootstrapResult)
            if (platformOfferId) {
              scenarioVariables.platform_offer_id = platformOfferId
            }
            pushActivity('scenario', '线下注册并完成绑店完成', {
              scenario: activeInterfaceScenario.value.name,
              session_id: bootstrapResult.session?.session_id,
              phone_number: bootstrapResult.session?.phone_number,
            })
          } catch (error) {
            getScenarioBootstrapKeys().forEach((key) => {
              const failure = buildOperationResult('error', getErrorPayload(error), normalizeError(error))
              scenarioStepResults[key] = {
                status: 'error',
                at: new Date().toLocaleTimeString(),
                request: {
                  method: 'POST',
                  endpoint: '/api/register-and-run-multishop',
                  body: getScenarioBootstrapPayload(),
                },
                response: failure,
                payload: failure,
              }
            })
            failCount += 1
            if (scenarioSettings.stopOnFailure) break
          }
        }
        continue
      }
      if (!step.operation && !step.endpoint.startsWith('/api/')) {
        skippedCount += 1
        markScenarioStep(step, 'skipped', { message: '该步骤未绑定可执行接口。' })
        continue
      }
      // /api/register/* endpoints are stateless — they create / look up the
      // session themselves via phone_number, so don't require an existing
      // active session before running.
      const isStatelessRegisterStep = typeof step.endpoint === 'string'
        && step.endpoint.startsWith('/api/register/')
      if (!activeSessionId.value && !isStatelessRegisterStep) {
        failCount += 1
        markScenarioStep(step, 'error', { success: false, error_message: '当前没有 session_id，无法继续执行。' })
        if (scenarioSettings.stopOnFailure) break
        continue
      }
      await handleScenarioStepRun(step)
      const result = scenarioStepResults[step.key]
      if (result?.success === false || result?.status === 'error') {
        failCount += 1
        if (scenarioSettings.stopOnFailure) break
      } else {
        successCount += 1
      }
      if (scenarioStopRequested.value) {
        stoppedByUser = true
        break
      }
    }

    const record = {
      id: `${Date.now()}`,
      scenario: activeInterfaceScenario.value.name,
      env: connectionForm.env,
      at: startedAt.toLocaleString(),
      duration: `${Math.max(1, Math.round((Date.now() - startedAt.getTime()) / 1000))}s`,
      success: successCount,
      skipped: skippedCount,
      failed: failCount,
      status: stoppedByUser ? '已停止' : (failCount > 0 ? '失败' : '完成'),
      context: cloneScenarioPayload(latestScenarioRunContext.value),
      variables: cloneScenarioPayload(scenarioVariables),
      steps: buildScenarioRunStepSnapshots(enabledSteps),
    }
    addScenarioExecutionRecord(record)
    activeScenarioTab.value = 'history'
    pushActivity('scenario', `${record.scenario} 服务端执行${record.status}`, record)
    ElMessage({
      type: failCount > 0 ? 'warning' : 'success',
      message: `${record.scenario} ${record.status}：成功 ${successCount}，跳过 ${skippedCount}，失败 ${failCount}`,
    })
  } finally {
    scenarioExecuting.value = false
    scenarioStopRequested.value = false
  }
}

function handleScenarioStop() {
  if (!scenarioExecuting.value) return
  scenarioStopRequested.value = true
  pushActivity('scenario', `${activeInterfaceScenario.value?.name || '场景'} 已请求停止`, {
    requestedAt: new Date().toISOString(),
  })
  ElMessage.warning('已请求停止，当前步骤完成后中止后续执行。')
}

function syncDowsureFollowupFields(operationKey, data) {
  if (operationKey === 'dowsureCreditResult') {
    if (data.applicationCode) {
      operationForms.dowsureEsignDrawdownResult.application_code = data.applicationCode
      operationForms.dowsureRepaymentResult.application_code = data.applicationCode
    }
    if (Object.prototype.hasOwnProperty.call(data, 'creditContractNo')) {
      operationForms.dowsureEsignDrawdownResult.credit_contract_no = data.creditContractNo
    }
  }

  if (operationKey === 'dowsureEsignDrawdownResult') {
    if (data.applicationCode) {
      operationForms.dowsureRepaymentResult.application_code = data.applicationCode
    }
  }
}

async function handleAiSend() {
  const text = aiInput.value.trim()
  if (!text || aiSending.value) return
  aiError.value = ''

  // 如果模型切换了，先插入切换提示，再放用户消息
  const currentModel = aiModel.value
  if (aiLastUsedModel.value && aiLastUsedModel.value !== currentModel) {
    aiMessages.value.push({
      id: `${Date.now()}-model-switch`,
      role: 'system',
      content: `已由 ${aiLastUsedModel.value} 切换至 ${currentModel}`,
      at: new Date().toLocaleTimeString(),
    })
  }
  aiLastUsedModel.value = currentModel

  aiMessages.value.push({
    id: `${Date.now()}-user`,
    role: 'user',
    content: text,
    at: new Date().toLocaleTimeString(),
    model: currentModel,
  })
  aiInput.value = ''
  aiSending.value = true

  try {
    const history = aiMessages.value
      .filter((item) => ['user', 'assistant', 'tool'].includes(item.role))
      .filter((item) => !item.meta?.error)
      .slice(0, -1)
      .slice(-12)
      .map((item) => ({ role: item.role, content: item.content }))
    const response = await sendAiChat({
      message: text,
      history,
      context: buildAiContext(),
      model: aiModel.value,
      reasoning_effort: aiReasoningEffort.value,
    })

    aiMessages.value.push({
      id: `${Date.now()}-assistant`,
      role: 'assistant',
      content: response.reply || '抱歉，我没有理解您的问题，请补充更具体的描述。',
      at: new Date().toLocaleTimeString(),
      meta: {
        mode: response.mode,
        tool_name: response.tool_name,
        tool_result: response.tool_result,
        missing_fields: response.missing_fields,
        template: response.template,
        rendered: response.rendered,
        params: response.params,
        execution: response.execution,
      },
    })
  } catch (error) {
    aiError.value = normalizeError(error)
    aiMessages.value.push({
      id: `${Date.now()}-error`,
      role: 'assistant',
      content: `请求失败: ${normalizeError(error)}`,
      at: new Date().toLocaleTimeString(),
      meta: { error: true },
    })
  } finally {
    aiSending.value = false
  }
}

function buildPayload(operation) {
  const payload = { session_id: activeSessionId.value, username: authUser.value?.username }
  if (selectedApplicationUniqueId.value) {
    payload.application_unique_id = selectedApplicationUniqueId.value
  }
  if (['pspStart', 'pspCompleted'].includes(operation.key) && selectedPspMerchantAccountId.value) {
    payload.merchant_account_id = selectedPspMerchantAccountId.value
  }
  if (operation.key === 'underwritten' && selectedLimitApplicationUniqueId.value) {
    payload.limit_application_unique_id = selectedLimitApplicationUniqueId.value
  }
  if (['repaymentStart', 'repayment', 'dowsureRepaymentResult', 'webankRepaymentResult', 'cgbRepaymentResult'].includes(operation.key) && selectedDowsureRepaymentLoanCode.value) {
    payload.loan_code = selectedDowsureRepaymentLoanCode.value
  }
  const form = operationForms[operation.key] ?? {}
  for (const field of operation.fields) {
    if (field.visible && !field.visible(form)) continue
    const value = form[field.prop]
    if (field.type === 'text') {
      if (value !== undefined && value !== null && String(value).trim() !== '') {
        payload[field.prop] = String(value).trim()
      }
    } else if (value !== undefined && value !== null && value !== '') {
      payload[field.prop] = value
    }
  }
  if (operation.key === 'dowsureCreditResult') {
    if (!payload.applicationCode) {
      payload.applicationCode = selectedApplication.value?.application_unique_id || sessionSummary.value?.application_unique_id || ''
    }
    payload.creditResultList = (form.creditResultList ?? [])
      .map((item) => ({
        offerId: String(item.offerId ?? '').trim(),
        sellerId: String(item.sellerId ?? '').trim(),
        amount: item.amount ?? 0,
      }))
      .filter((item) => item.offerId && item.sellerId)
  }
  if (operation.key === 'webankCreditResult') {
    payload.seller_offers = (form.seller_offers ?? [])
      .filter((item) => item.admissionStatus !== 'NOT_ADMITTED')
      .map((item) => ({
        applySellerId: String(item.seller_id ?? '').trim(),
        applySellerBusinessSum: item.applySellerBusinessSum ?? 0,
        sellerSiteCountryName: String(item.marketplace_country ?? '').trim(),
      }))
      .filter((item) => item.applySellerId)
  }
  return payload
}

function pushActivity(kind, title, payload) {
  activityFeed.value.unshift({
    id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
    kind,
    title,
    payload,
    at: new Date().toLocaleString(),
  })
  activityFeed.value = activityFeed.value.slice(0, 30)
}

function clearLogs() {
  eventLogs.value = []
}

function showRegisterToast(type, message) {
  ElMessage({
    type,
    message,
    duration: 2000,
    showClose: true,
  })
}

function showOperationToast(type, title, payload) {
  ElNotification({
    type,
    title,
    message: summarizeOperationResult(payload),
    duration: type === 'success' ? 2600 : 5000,
    showClose: true,
    customClass: type === 'success' ? 'operation-toast-success' : 'operation-toast-error',
  })
}

function buildOperationResult(status, payload, fallbackMessage = '') {
  if (status === 'success') return payload
  if (payload && typeof payload === 'object') {
    return {
      success: false,
      ...payload,
      error_message: payload.error_message || payload.message || payload.detail || fallbackMessage || null,
    }
  }
  return {
    success: false,
    error_message: fallbackMessage || String(payload || '未知错误'),
  }
}

function getErrorPayload(error) {
  return error?.payload || error?.response?.data || null
}

function summarizeOperationResult(payload) {
  if (payload && typeof payload === 'object') {
    return payload.error_message || payload.message || payload.detail || JSON.stringify(payload).slice(0, 180)
  }
  return String(payload || '')
}

function openInterfaceTestView() {
  closeToolRail()
  currentView.value = 'interfaceTest'
  interfacePageMode.value = 'scenario'
  interfaceFocusMode.value = 'scenario'
  Object.keys(expandedScenarioDirectories).forEach((key) => {
    expandedScenarioDirectories[key] = false
  })
  Object.keys(expandedScenarioTrees).forEach((key) => {
    expandedScenarioTrees[key] = false
  })
  if (!activeOperationKey.value && activeInterfaceScenario.value.steps.length > 0) {
    activeOperationKey.value = activeInterfaceScenario.value.steps[0].key
  }
}

function clearAiUiPoll() {
  if (!aiUiPollTimer) return
  window.clearTimeout(aiUiPollTimer)
  aiUiPollTimer = null
}

function aiUiEnvironmentLabel(environment) {
  return aiUiEnvironmentOptions.find((item) => item.value === environment)?.label || '自定义'
}

function inferAiUiEnvironment(url) {
  const normalizedUrl = String(url || '').trim().replace(/\/+$/, '')
  return aiUiEnvironmentOptions.find((item) => item.url && item.url.replace(/\/+$/, '') === normalizedUrl)?.value || 'custom'
}

function handleAiUiEnvironmentChange(environment) {
  const option = aiUiEnvironmentOptions.find((item) => item.value === environment)
  if (option?.url) aiUiForm.url = option.url
  else aiUiForm.url = ''
}

function resetAiUiForm() {
  aiUiForm.id = null
  aiUiForm.environment = 'sit'
  aiUiForm.name = 'OFFLINE 注册入口检查-SIT-样板'
  aiUiForm.url = 'https://expressfinance-dpu-sit.dowsure.com/en/'
  aiUiForm.context = '这是 OFFLINE_SIGNUP_URL_DICT 的 SIT 页面入口冒烟用例。只验证环境 URL、FundPark USD 产品进入注册页以及手机号验证控件，不发送短信、不创建客户。'
  aiUiForm.prompt = `Scenario: OFFLINE signup entry smoke test
  Given the SIT HSBC Express Finance homepage is open
  When I click the "Get started" button for the FundPark USD Line of Credit product
  Then the page should show "Enter your contact details to begin"
  And the page should show the "Mobile number" field
  And the "Get code" button should be disabled before a mobile number is entered`
  aiUiForm.headed = false
  aiUiForm.viewport = { width: 1440, height: 900 }
  aiUiNaturalLanguage.value = ''
  aiUiStructuredYaml.value = ''
  aiUiVariablesText.value = '{}'
  aiUiStructuredSpec.value = null
}

function editAiUiCase(item) {
  aiUiForm.id = item.id
  aiUiForm.environment = item.environment || inferAiUiEnvironment(item.url)
  aiUiForm.name = item.name || ''
  aiUiForm.url = item.url || aiUiEnvironmentOptions.find((option) => option.value === aiUiForm.environment)?.url || ''
  aiUiForm.context = item.context || ''
  aiUiForm.prompt = item.prompt || ''
  aiUiForm.headed = Boolean(item.headed)
  aiUiForm.viewport = { width: item.viewport?.width || 1440, height: item.viewport?.height || 900 }
  aiUiNaturalLanguage.value = ''
  aiUiStructuredSpec.value = item.structured_spec || null
  aiUiStructuredYaml.value = item.structured_spec?.yaml || ''
  aiUiVariablesText.value = JSON.stringify(item.variables || item.structured_spec?.variables || {}, null, 2)
  aiUiSelectedCaseId.value = item.id
}

async function refreshAiUiPage() {
  if (!authUser.value?.username) return
  aiUiLoading.value = true
  aiUiError.value = ''
  try {
    const [cases, runs, runtime] = await Promise.all([
      fetchAiUiCases(authUser.value.username),
      fetchAiUiRuns(authUser.value.username),
      fetchAiUiRuntimeStatus(authUser.value.username),
    ])
    aiUiCases.value = Array.isArray(cases) ? cases : []
    aiUiRuns.value = Array.isArray(runs) ? [...runs].reverse() : []
    aiUiRuntime.value = runtime || null
    if (!aiUiSelectedCaseId.value && aiUiCases.value.length) editAiUiCase(aiUiCases.value[0])
    if (aiUiActiveRunId.value) await pollAiUiRun(aiUiActiveRunId.value)
  } catch (error) {
    aiUiError.value = error?.payload?.message || error?.message || 'AI UI 数据加载失败'
  } finally {
    aiUiLoading.value = false
  }
}

function openAiUiView() {
  closeToolRail()
  currentView.value = 'aiUi'
  void refreshAiUiPage()
}

function switchAiUiPageMode(mode) {
  aiUiPageMode.value = mode === 'reports' ? 'reports' : 'cases'
  if (aiUiPageMode.value === 'reports') void refreshAiUiPage()
}

function openAiUiReport(path) {
  if (!path) return
  window.open(path, '_blank', 'noopener,noreferrer')
}

async function generateAiUiStructuredCase() {
  if (!authUser.value?.username) return ElMessage.warning('请先登录')
  if (aiUiNaturalLanguage.value.trim().length < 8) {
    return ElMessage.warning('请先用一句完整自然语言描述测试场景')
  }
  aiUiGenerating.value = true
  aiUiError.value = ''
  try {
    const result = await generateAiUiCase({
      username: authUser.value.username,
      instruction: aiUiNaturalLanguage.value.trim(),
      environment: aiUiForm.environment,
      context: aiUiForm.context,
    })
    aiUiStructuredSpec.value = result
    aiUiStructuredYaml.value = result.yaml || ''
    aiUiVariablesText.value = JSON.stringify(result.variables || {}, null, 2)
    aiUiForm.name = result.name || aiUiForm.name
    aiUiForm.prompt = result.gherkin || aiUiForm.prompt
    if (result.environment && aiUiEnvironmentOptions.some((option) => option.value === result.environment)) {
      aiUiForm.environment = result.environment
      handleAiUiEnvironmentChange(result.environment)
    }
    ElMessage.success('已生成结构化用例并转换为 Gherkin')
  } catch (error) {
    aiUiError.value = error?.payload?.message || error?.message || '自然语言转换失败'
  } finally {
    aiUiGenerating.value = false
  }
}

function parseAiUiVariables() {
  const text = aiUiVariablesText.value.trim()
  if (!text) return {}
  const parsed = JSON.parse(text)
  if (!parsed || Array.isArray(parsed) || typeof parsed !== 'object') {
    throw new Error('变量必须是 JSON 对象')
  }
  return Object.fromEntries(Object.entries(parsed).map(([key, value]) => [key, String(value)]))
}

async function saveAiUiCaseRecord() {
  if (!authUser.value?.username) return ElMessage.warning('请先登录')
  aiUiSaving.value = true
  aiUiError.value = ''
  try {
    const variables = parseAiUiVariables()
    const row = await saveAiUiCase({
      username: authUser.value.username,
      name: aiUiForm.name,
      environment: aiUiForm.environment,
      url: aiUiForm.url,
      context: aiUiForm.context,
      prompt: aiUiForm.prompt,
      variables,
      structured_spec: aiUiStructuredSpec.value,
      headed: aiUiForm.headed,
      viewport: aiUiForm.viewport,
    }, aiUiForm.id)
    const index = aiUiCases.value.findIndex((item) => item.id === row.id)
    if (index >= 0) aiUiCases.value[index] = row
    else aiUiCases.value.unshift(row)
    editAiUiCase(row)
    ElMessage.success('AI UI 用例已保存')
  } catch (error) {
    aiUiError.value = error?.payload?.message || error?.message || '保存失败'
  } finally {
    aiUiSaving.value = false
  }
}

async function removeAiUiCase(item) {
  try {
    await ElMessageBox.confirm(`确定删除「${item.name}」吗？`, '删除确认', {
      type: 'warning',
      confirmButtonText: '确定删除',
      cancelButtonText: '取消',
    })
    await deleteAiUiCase(item.id, authUser.value.username)
    aiUiCases.value = aiUiCases.value.filter((row) => row.id !== item.id)
    if (aiUiForm.id === item.id) resetAiUiForm()
    ElMessage.success('AI UI 用例已删除')
  } catch (error) {
    if (error === 'cancel' || error === 'close') return
    aiUiError.value = error?.payload?.message || error?.message || '删除失败'
  }
}

async function runAiUiCase(item = null) {
  const target = item || aiUiCases.value.find((row) => row.id === aiUiSelectedCaseId.value)
  if (!target) return ElMessage.warning('请先保存一个 AI UI 用例')
  aiUiPendingCase.value = target
  aiUiRunConfirmVisible.value = true
}

async function confirmAiUiRun() {
  const target = aiUiPendingCase.value
  if (!target) return
  aiUiRunConfirmVisible.value = false
  aiUiSelectedCaseId.value = target.id
  aiUiError.value = ''
  try {
    const run = await startAiUiRun({ username: authUser.value.username, case_id: target.id })
    aiUiActiveRunId.value = run.id
    aiUiRuns.value = [run, ...aiUiRuns.value.filter((row) => row.id !== run.id)]
    await pollAiUiRun(run.id)
  } catch (error) {
    aiUiError.value = error?.payload?.message || error?.message || '启动失败'
  }
}

async function pollAiUiRun(runId) {
  clearAiUiPoll()
  if (!runId || !authUser.value?.username) return
  try {
    const run = await fetchAiUiRun(runId, authUser.value.username)
    const index = aiUiRuns.value.findIndex((row) => row.id === run.id)
    if (index >= 0) aiUiRuns.value[index] = run
    else aiUiRuns.value.unshift(run)
    if (['running'].includes(run.status)) {
      aiUiPollTimer = window.setTimeout(() => pollAiUiRun(runId), 1500)
    } else {
      aiUiActiveRunId.value = ''
    }
  } catch (error) {
    aiUiError.value = error?.payload?.message || error?.message || '执行状态查询失败'
  }
}

async function stopAiUiCaseRun(run) {
  clearAiUiPoll()
  try {
    const updated = await stopAiUiRun(run.id, authUser.value.username)
    const index = aiUiRuns.value.findIndex((row) => row.id === updated.id)
    if (index >= 0) aiUiRuns.value[index] = updated
    aiUiActiveRunId.value = ''
  } catch (error) {
    aiUiError.value = error?.payload?.message || error?.message || '停止失败'
  }
}

function openMockApiView() {
  if (!requireAdminView('interfaceTest')) return
  closeToolRail()
  currentView.value = 'mockApi'
}

function openActivityView() {
  closeToolRail()
  currentView.value = 'activity'
  refreshAuditOperations()
}

function openEnvironmentMonitorView() {
  closeToolRail()
  currentView.value = 'environmentMonitor'
  refreshEnvironmentMonitor()
  resetEnvironmentMonitorCountdown()
}

async function refreshEnvironmentMonitor(force = false) {
  environmentMonitorLoading.value = true
  environmentMonitorError.value = ''
  try {
    const result = await fetchEnvironmentMonitor({ force })
    environmentMonitor.value = result || { overall: 'checking', checked_at: '', items: [] }
    if (!force && result?.overall === 'checking') {
      window.setTimeout(() => {
        if (currentView.value === 'environmentMonitor') refreshEnvironmentMonitor(false)
      }, 2500)
    }
  } catch (error) {
    environmentMonitorError.value = normalizeError(error)
  } finally {
    environmentMonitorLoading.value = false
    resetEnvironmentMonitorCountdown()
  }
}

function resetEnvironmentMonitorCountdown() {
  environmentMonitorRefreshSeconds.value = 60
}

function startEnvironmentMonitorAutoRefresh() {
  stopEnvironmentMonitorAutoRefresh()
  environmentMonitorRefreshTimer = window.setInterval(() => {
    if (currentView.value !== 'environmentMonitor') {
      resetEnvironmentMonitorCountdown()
      return
    }
    environmentMonitorRefreshSeconds.value -= 1
    if (environmentMonitorLoading.value && environmentMonitorRefreshSeconds.value <= 0) {
      environmentMonitorRefreshSeconds.value = 1
      return
    }
    if (environmentMonitorRefreshSeconds.value <= 0 && !environmentMonitorLoading.value) {
      refreshEnvironmentMonitor(true)
    }
  }, 1000)
}

function stopEnvironmentMonitorAutoRefresh() {
  if (!environmentMonitorRefreshTimer) return
  window.clearInterval(environmentMonitorRefreshTimer)
  environmentMonitorRefreshTimer = null
}

async function refreshAuditOperations() {
  if (!authUser.value?.username) {
    auditOperations.value = []
    auditError.value = '请先登录后再查看使用日志'
    return
  }
  auditLoading.value = true
  auditError.value = ''
  try {
    const params = {
      username: authUser.value.username,
      limit: 200,
    }
    const phone = auditQuery.phone_number.trim()
    const session = auditQuery.session_id.trim()
    if (phone) params.phone_number = phone
    if (session) params.session_id = session
    const rows = await fetchUserOperations(params)
    auditOperations.value = Array.isArray(rows) ? rows : []
    expandedAuditOperationIds.value = new Set()
  } catch (error) {
    auditError.value = error?.payload?.message || error?.message || '查询失败'
    auditOperations.value = []
  } finally {
    auditLoading.value = false
  }
}

function resetAuditQuery() {
  auditQuery.phone_number = ''
  auditQuery.session_id = ''
  refreshAuditOperations()
}

function backToConsole() {
  currentView.value = 'console'
}

function openAboutView() {
  closeToolRail()
  currentView.value = 'about'
}

function openContactView() {
  closeToolRail()
  currentView.value = 'contact'
}

function openContactAdminView() {
  if (!requireAdminView('contactAdmin')) return
  closeToolRail()
  currentView.value = 'contactAdmin'
}

function openUserManagementView() {
  if (!requireAdminView('userManagement')) return
  closeToolRail()
  currentView.value = 'userManagement'
  refreshAdminUsers()
}

async function refreshAdminUsers() {
  if (!authUser.value?.username) return
  adminUsersLoading.value = true
  adminUsersError.value = ''
  adminUsersPage.value = 1
  try {
    const rows = await fetchAdminUsers(authUser.value.username)
    adminUsers.value = Array.isArray(rows) ? rows : []
  } catch (error) {
    adminUsersError.value = error?.payload?.message || error?.message || '加载用户失败'
    adminUsers.value = []
  } finally {
    adminUsersLoading.value = false
  }
}

function openAdminUserEdit(user) {
  adminUserEditForm.original_username = user.username
  adminUserEditForm.new_username = user.username
  adminUserEditForm.new_password = ''
  adminUserEditForm.notes = user.notes || ''
  adminUserEditVisible.value = true
}

async function saveAdminUserEdit() {
  if (!authUser.value?.username) return
  const payload = { admin_username: authUser.value.username }
  const nu = adminUserEditForm.new_username.trim()
  if (nu && nu !== adminUserEditForm.original_username) payload.new_username = nu
  if (adminUserEditForm.new_password.trim()) payload.new_password = adminUserEditForm.new_password.trim()
  // always pass notes so it can be cleared to ''
  payload.notes = adminUserEditForm.notes
  adminUserEditSaving.value = true
  try {
    await updateAdminUser(adminUserEditForm.original_username, payload)
    ElMessage.success('账号已更新')
    adminUserEditVisible.value = false
    await refreshAdminUsers()
  } catch (error) {
    ElMessage.error(error?.payload?.message || error?.message || '更新失败')
  } finally {
    adminUserEditSaving.value = false
  }
}

async function removeAdminUser(user) {
  if (!authUser.value?.username) return
  try {
    await ElMessageBox.confirm(
      `确定永久删除账号「${user.username}」吗？该操作不可撤销，账号及其历史数据将被清除。`,
      '删除确认',
      { type: 'warning', confirmButtonText: '确定删除', cancelButtonText: '取消', confirmButtonClass: 'el-button--danger' },
    )
  } catch {
    return
  }
  try {
    await deleteAdminUser(user.username, authUser.value.username)
    ElMessage.success(`账号「${user.username}」已删除`)
    await refreshAdminUsers()
  } catch (error) {
    ElMessage.error(error?.payload?.message || error?.message || '删除失败')
  }
}

async function approveUser(user) {
  if (!authUser.value?.username) return
  try {
    await approveAdminUser(user.username, authUser.value.username)
    ElMessage.success(`已通过「${user.username}」的注册申请`)
    await refreshAdminUsers()
  } catch (error) {
    ElMessage.error(error?.payload?.message || error?.message || '操作失败')
  }
}

async function rejectUser(user) {
  if (!authUser.value?.username) return
  let note = ''
  try {
    const { value } = await ElMessageBox.prompt(
      `拒绝「${user.username}」的注册申请，可选填拒绝原因（将推送给用户）：`,
      '拒绝注册',
      { confirmButtonText: '确定拒绝', cancelButtonText: '取消', inputPlaceholder: '拒绝原因（可留空）', type: 'warning' },
    )
    note = value || ''
  } catch {
    return
  }
  try {
    await rejectAdminUser(user.username, authUser.value.username, note)
    ElMessage.success(`已拒绝「${user.username}」的注册申请`)
    await refreshAdminUsers()
  } catch (error) {
    ElMessage.error(error?.payload?.message || error?.message || '操作失败')
  }
}

function toggleToolRail() {
  toolRailOpen.value = !toolRailOpen.value
}

function closeToolRail(force = false) {
  if (force || isMobileViewport.value) {
    toolRailOpen.value = false
  }
}

function resetLogSearch() {
  logSearchForm.keyword = ''
  logSearchForm.timeRange = []
  logSearchForm.limit = DEFAULT_LOG_PREVIEW_LIMIT
  runLogSearch()
}

async function runLogSearch() {
  logSearchLoading.value = true
  try {
    const [startTime, endTime] = logSearchForm.timeRange || []
    const previewMode = isLogPreviewMode.value
    logSearchResults.value = await fetchLogs({
      username: authUser.value?.username,
      keyword: logSearchForm.keyword?.trim() || undefined,
      start_time: startTime || undefined,
      end_time: endTime || undefined,
      session_id: previewMode ? undefined : (activeSessionId.value || undefined),
      limit: previewMode ? DEFAULT_LOG_PREVIEW_LIMIT : (logSearchForm.limit || DEFAULT_LOG_SEARCH_LIMIT),
    })
  } catch (error) {
    pushActivity('error', '日志查询失败', normalizeError(error))
  } finally {
    logSearchLoading.value = false
  }
}

function clearAiChat() {
  aiMessages.value = []
  aiError.value = ''
}

function openAiPage() {
  closeToolRail()
  aiExecutionEnv.value = sessionSummary.value?.env || connectionForm.env || registerForm.env || 'reg'
  currentView.value = 'ai'
}

function openPromptTemplatesView() {
  closeToolRail()
  currentView.value = 'promptTemplates'
  refreshPromptTemplates()
}

async function refreshScenarioMetaOverrides() {
  // Available to every authenticated user; admins use the upsert endpoint
  // to write back. Falls silent on failure so UI just shows defaults.
  try {
    const rows = await fetchScenarioMetaOverrides(authUser.value?.username)
    Object.keys(scenarioMetaOverrides).forEach((key) => {
      delete scenarioMetaOverrides[key]
    })
    if (Array.isArray(rows)) {
      for (const row of rows) {
        if (!row?.scenario_key) continue
        scenarioMetaOverrides[row.scenario_key] = {
          name: row.name || '',
          description: row.description || '',
          updated_by: row.updated_by || '',
          updated_at: row.updated_at || '',
        }
      }
    }
  } catch (error) {
    // silent — defaults still apply
  }
}

async function refreshScenarioStepMetaOverrides() {
  try {
    const rows = await fetchScenarioStepMetaOverrides(authUser.value?.username)
    Object.keys(scenarioStepMetaOverrides).forEach((key) => {
      delete scenarioStepMetaOverrides[key]
    })
    if (Array.isArray(rows)) {
      for (const row of rows) {
        if (!row?.scenario_key || !row?.step_key) continue
        scenarioStepMetaOverrides[scenarioStepMetaOverrideKey(row.scenario_key, row.step_key)] = {
          title: row.title || '',
          description: row.description || '',
          is_hidden: Boolean(row.is_hidden),
          updated_by: row.updated_by || '',
          updated_at: row.updated_at || '',
        }
      }
    }
  } catch (error) {
    // silent - defaults still apply
  }
}

async function refreshScenarioStepOrders() {
  if (!authUser.value?.username) return
  try {
    const rows = await fetchScenarioStepOrders(authUser.value.username)
    Object.keys(scenarioStepOrders).forEach((key) => {
      delete scenarioStepOrders[key]
    })
    Object.keys(scenarioStepOrderDraft).forEach((key) => {
      delete scenarioStepOrderDraft[key]
    })
    if (Array.isArray(rows)) {
      for (const row of rows) {
        if (!row?.scenario_key) continue
        const order = Array.isArray(row.step_order) ? row.step_order.filter(Boolean).map(String) : []
        if (row.scenario_key.endsWith('::structure')) {
          const scenarioKey = row.scenario_key.slice(0, -'::structure'.length)
          try {
            const structure = JSON.parse(order[0] || '{}')
            if (Array.isArray(structure.added) && structure.added.length) scenarioStepStructureDraft[scenarioKey] = structure.added
            if (Array.isArray(structure.deleted) && structure.deleted.length) scenarioStepStructureDeleted[scenarioKey] = structure.deleted
          } catch (error) {
            // Ignore malformed legacy structure rows.
          }
          continue
        }
        if (order.length) scenarioStepOrders[row.scenario_key] = order
      }
    }
  } catch (error) {
    // silent — defaults still apply
  }
}

// --- Scenario step drag-and-drop handlers ---
function onScenarioStepDragStart(event, scenarioKey, stepKey) {
  scenarioDragState.value = { scenarioKey, stepKey }
  try {
    event.dataTransfer.effectAllowed = 'move'
    event.dataTransfer.setData('text/plain', `${scenarioKey}::${stepKey}`)
  } catch (err) {
    // Safari sometimes throws on setData for certain elements — ignore.
  }
}

function onScenarioStepDragOver(event, scenarioKey, stepKey) {
  // Only accept intra-scenario moves; different scenarios keep their own order.
  if (scenarioDragState.value.scenarioKey !== scenarioKey) return
  event.dataTransfer.dropEffect = 'move'
}

function onScenarioStepDrop(event, scenarioKey, targetStepKey) {
  const src = scenarioDragState.value
  scenarioDragState.value = { scenarioKey: '', stepKey: '' }
  if (!src.scenarioKey || src.scenarioKey !== scenarioKey) return
  if (!src.stepKey || src.stepKey === targetStepKey) return
  const scenarioDef = scenarioBaseDefs.find((def) => def.key === scenarioKey)
  const scenarioRuntime = interfaceScenarios.value.find((item) => item.key === scenarioKey)
  const baseStepKeys = (scenarioRuntime?.steps || scenarioDef?.buildSteps?.() || [])
    .map((step) => step?.key)
    .filter(Boolean)
  const currentOrder = scenarioStepOrderDraft[scenarioKey]
    || scenarioStepOrders[scenarioKey]
    || baseStepKeys
  const nextOrder = currentOrder.slice()
  const srcIndex = nextOrder.indexOf(src.stepKey)
  const targetIndex = nextOrder.indexOf(targetStepKey)
  if (srcIndex === -1 || targetIndex === -1) return
  nextOrder.splice(srcIndex, 1)
  let insertIndex = nextOrder.indexOf(targetStepKey)
  // 根据鼠标落点决定插入到目标步骤上方还是下方，拖动上下位置更直观。
  const targetElement = event?.currentTarget
  if (targetElement?.getBoundingClientRect) {
    const rect = targetElement.getBoundingClientRect()
    if (event.clientY > rect.top + rect.height / 2) insertIndex += 1
  }
  nextOrder.splice(insertIndex, 0, src.stepKey)
  scenarioStepOrderDraft[scenarioKey] = nextOrder
  scenarioSaveState.value = '未保存'
}

function onScenarioStepDragEnd() {
  scenarioDragState.value = { scenarioKey: '', stepKey: '' }
}

function startMockOperationLongPress() {
  if (!isAdmin.value) return
  stopMockOperationLongPress()
  mockOperationLongPressTimer = window.setTimeout(() => {
    mockOperationEditMode.value = true
    if (!Array.isArray(scenarioStepOrderDraft.mockOperations)) {
      scenarioStepOrderDraft.mockOperations = visibleOperations.value.map((item) => item.key)
    }
    ElMessage.info('已进入排版模式，拖动模块调整顺序')
  }, 550)
}

function stopMockOperationLongPress() {
  clearTimeout(mockOperationLongPressTimer)
  mockOperationLongPressTimer = null
}

function onMockOperationDragStart(event, operationKey) {
  if (!isAdmin.value || !mockOperationEditMode.value) return
  mockOperationDragState.value = operationKey
  event.dataTransfer.effectAllowed = 'move'
  event.dataTransfer.setData('text/plain', operationKey)
}

function onMockOperationDrop(event, targetKey) {
  if (!isAdmin.value || !mockOperationEditMode.value) return
  event.preventDefault()
  const sourceKey = mockOperationDragState.value || event.dataTransfer.getData('text/plain')
  mockOperationDragState.value = ''
  if (!sourceKey || sourceKey === targetKey) return
  const currentOrder = (scenarioStepOrderDraft.mockOperations || visibleOperations.value.map((item) => item.key)).slice()
  const sourceIndex = currentOrder.indexOf(sourceKey)
  const targetIndex = currentOrder.indexOf(targetKey)
  if (sourceIndex === -1 || targetIndex === -1) return
  currentOrder.splice(sourceIndex, 1)
  currentOrder.splice(currentOrder.indexOf(targetKey), 0, sourceKey)
  scenarioStepOrderDraft.mockOperations = currentOrder
}

function onMockOperationDragEnd() {
  mockOperationDragState.value = ''
}

function cancelMockOperationLayout() {
  delete scenarioStepOrderDraft.mockOperations
  mockOperationEditMode.value = false
}

async function saveMockOperationLayout() {
  if (!authUser.value?.username || !isAdmin.value) return
  const order = (scenarioStepOrderDraft.mockOperations || visibleOperations.value.map((item) => item.key)).slice()
  try {
    await saveScenarioStepOrder({
      username: authUser.value.username,
      scenario_key: 'mockOperations',
      step_order: order,
    })
    scenarioStepOrders.mockOperations = order
    delete scenarioStepOrderDraft.mockOperations
    mockOperationEditMode.value = false
    ElMessage.success('Mock 操作排版已保存，所有账号将使用新顺序')
  } catch (error) {
    ElMessage.error(error?.payload?.message || error?.message || '排版保存失败')
  }
}

function openScenarioMetaEditor() {
  if (!isAdmin.value) {
    ElMessage.warning('仅管理员可编辑场景名称与描述')
    return
  }
  const scenario = activeInterfaceScenario.value
  if (!scenario) return
  scenarioMetaEditForm.scenarioKey = scenario.key
  scenarioMetaEditForm.name = scenario.name || ''
  scenarioMetaEditForm.description = scenario.description || ''
  scenarioMetaEditVisible.value = true
}

async function saveScenarioMetaEditor() {
  if (!authUser.value?.username) return
  if (!scenarioMetaEditForm.scenarioKey) {
    scenarioMetaEditVisible.value = false
    return
  }
  scenarioMetaEditSaving.value = true
  try {
    const row = await saveScenarioMetaOverride({
      username: authUser.value.username,
      scenario_key: scenarioMetaEditForm.scenarioKey,
      name: scenarioMetaEditForm.name?.trim() || null,
      description: scenarioMetaEditForm.description,
    })
    if (row?.scenario_key) {
      scenarioMetaOverrides[row.scenario_key] = {
        name: row.name || '',
        description: row.description || '',
        updated_by: row.updated_by || '',
        updated_at: row.updated_at || '',
      }
    }
    ElMessage.success('场景信息已保存')
    scenarioMetaEditVisible.value = false
  } catch (error) {
    ElMessage.error(error?.payload?.message || error?.message || '保存失败')
  } finally {
    scenarioMetaEditSaving.value = false
  }
}

function openScenarioStepMetaEditor(scenario, step) {
  if (!isAdmin.value) {
    ElMessage.warning('仅管理员可编辑步骤名称与描述')
    return
  }
  if (!scenario?.key || !step?.key) return
  const override = scenarioStepMetaOverrides[scenarioStepMetaOverrideKey(scenario.key, step.key)] || {}
  scenarioStepMetaEditForm.scenarioKey = scenario.key
  scenarioStepMetaEditForm.stepKey = step.key
  scenarioStepMetaEditForm.title = override.title || step.title || ''
  scenarioStepMetaEditForm.description = override.description || step.description || ''
  scenarioStepMetaEditForm.isHidden = Boolean(override.is_hidden)
  scenarioStepMetaEditVisible.value = true
}

function openScenarioAddStep(scenario, afterStep) {
  if (!isAdmin.value) {
    ElMessage.warning('仅管理员可添加步骤')
    return
  }
  const steps = scenario?.steps || []
  scenarioAddStepForm.scenarioKey = scenario?.key || ''
  scenarioAddStepForm.afterStepKey = afterStep?.key || ''
  scenarioAddStepForm.sourceStepKey = steps.find((item) => item.key !== afterStep?.key)?.key || ''
  scenarioAddStepVisible.value = true
}

function addScenarioStepAfter() {
  const scenario = interfaceScenarios.value.find((item) => item.key === scenarioAddStepForm.scenarioKey)
  const source = scenario?.steps?.find((item) => item.key === scenarioAddStepForm.sourceStepKey)
  if (!scenario || !source) return
  const suffix = `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`
  const step = JSON.parse(JSON.stringify({
    ...source,
    key: `${scenario.key}-custom-${suffix}`,
    title: `${source.title}（副本）`,
  }))
  const current = (scenarioStepStructureDraft[scenario.key] || []).slice()
  const deleted = new Set(scenarioStepStructureDeleted[scenario.key] || [])
  deleted.delete(step.key)
  scenarioStepStructureDeleted[scenario.key] = Array.from(deleted)
  const all = scenario.steps.filter((item) => !deleted.has(item.key)).map((item) => item.key)
  const addedByKey = new Map(current.map((item) => [item.key, item]))
  addedByKey.set(step.key, step)
  scenarioStepStructureDraft[scenario.key] = Array.from(addedByKey.values())
  const order = (scenarioStepOrderDraft[scenario.key] || scenarioStepOrders[scenario.key] || all).filter((key) => key !== step.key)
  const index = Math.max(0, order.indexOf(scenarioAddStepForm.afterStepKey))
  order.splice(index + 1, 0, step.key)
  scenarioStepOrderDraft[scenario.key] = order
  scenarioSaveState.value = '未保存'
  scenarioAddStepVisible.value = false
  ElMessage.success('步骤已加入草稿，点击右上角保存后生效')
}

async function saveScenarioStepMetaEditor() {
  if (!authUser.value?.username || !scenarioStepMetaEditForm.scenarioKey || !scenarioStepMetaEditForm.stepKey) return
  scenarioStepMetaEditSaving.value = true
  try {
    const row = await saveScenarioStepMetaOverride({
      username: authUser.value.username,
      scenario_key: scenarioStepMetaEditForm.scenarioKey,
      step_key: scenarioStepMetaEditForm.stepKey,
      title: scenarioStepMetaEditForm.title?.trim() || null,
      description: scenarioStepMetaEditForm.description,
      is_hidden: scenarioStepMetaEditForm.isHidden,
    })
    if (row?.scenario_key && row?.step_key) {
      scenarioStepMetaOverrides[scenarioStepMetaOverrideKey(row.scenario_key, row.step_key)] = {
        title: row.title || '',
        description: row.description || '',
        is_hidden: Boolean(row.is_hidden),
        updated_by: row.updated_by || '',
        updated_at: row.updated_at || '',
      }
    }
    ElMessage.success('步骤信息已保存')
    scenarioStepMetaEditVisible.value = false
  } catch (error) {
    ElMessage.error(error?.payload?.message || error?.message || '保存失败')
  } finally {
    scenarioStepMetaEditSaving.value = false
  }
}

async function hideScenarioStepMeta(scenario, step) {
  if (!isAdmin.value || !authUser.value?.username || !scenario?.key || !step?.key) return
  try {
    await ElMessageBox.confirm(`确定删除步骤「${step.title}」吗？点击右上角保存后才会对场景生效。`, '删除步骤', { type: 'warning' })
  } catch {
    return
  }
  const deleted = new Set(scenarioStepStructureDeleted[scenario.key] || [])
  deleted.add(step.key)
  scenarioStepStructureDeleted[scenario.key] = Array.from(deleted)
  // 如果目标步骤来自新增草稿，同时从新增列表移除，避免下一次计算时被重新带回。
  if (Array.isArray(scenarioStepStructureDraft[scenario.key])) {
    scenarioStepStructureDraft[scenario.key] = scenarioStepStructureDraft[scenario.key]
      .filter((item) => item?.key !== step.key)
  }
  scenarioSaveState.value = '未保存'
    if (activeOperationKey.value === step.key) {
      activeOperationKey.value = interfaceAutomationSteps.value[0]?.key || ''
      interfaceFocusMode.value = activeOperationKey.value ? 'step' : 'scenario'
    }
    ElMessage.success('步骤已加入删除草稿，点击右上角保存后生效')
}

async function resetScenarioStepMetaEditor() {
  if (!isAdmin.value || !authUser.value?.username || !scenarioStepMetaEditForm.scenarioKey || !scenarioStepMetaEditForm.stepKey) return
  scenarioStepMetaEditDeleting.value = true
  try {
    const rowKey = scenarioStepMetaOverrideKey(scenarioStepMetaEditForm.scenarioKey, scenarioStepMetaEditForm.stepKey)
    await deleteScenarioStepMetaOverride({
      username: authUser.value.username,
      scenario_key: scenarioStepMetaEditForm.scenarioKey,
      step_key: scenarioStepMetaEditForm.stepKey,
    })
    delete scenarioStepMetaOverrides[rowKey]
    ElMessage.success('已恢复默认步骤信息')
    scenarioStepMetaEditVisible.value = false
  } catch (error) {
    ElMessage.error(error?.payload?.message || error?.message || '恢复失败')
  } finally {
    scenarioStepMetaEditDeleting.value = false
  }
}

async function refreshScenarioStepOverrides() {
  if (!authUser.value?.username) return
  scenarioStepOverridesLoaded.value = false
  try {
    const rows = await fetchScenarioStepOverrides(authUser.value.username)
    Object.keys(scenarioStepOverrides).forEach((key) => {
      delete scenarioStepOverrides[key]
    })
    shopPerformancePresets.value = createBuiltinShopPerformancePresets()
    dowsureCnyCompanyTemplates.value = BUILTIN_DOWSURE_CNY_COMPANY_TEMPLATES.map(cloneDowsureCompanyTemplate)
    if (Array.isArray(rows)) {
      for (const row of rows) {
        if (!row?.scenario_key || !row?.step_key) continue
        const payload = { ...(row.payload || {}) }
        scenarioStepOverrides[scenarioStepOverrideKey(row.scenario_key, row.step_key)] = payload
        if (
          row.scenario_key === SHOP_PERFORMANCE_PRESET_SCENARIO
          && row.step_key === SHOP_PERFORMANCE_PRESET_STEP
        ) {
          shopPerformancePresets.value = mergeShopPerformancePresets(
            Array.isArray(payload.presets) ? payload.presets : [],
          )
        }
        if (
          row.scenario_key === DOWSURE_COMPANY_TEMPLATE_SCENARIO
          && row.step_key === DOWSURE_COMPANY_TEMPLATE_STEP
        ) {
          const customTemplates = Array.isArray(payload.templates)
            ? payload.templates
              .map(normalizeDowsureCompanyTemplate)
              .filter(Boolean)
            : []
          const templatesByName = new Map(
            BUILTIN_DOWSURE_CNY_COMPANY_TEMPLATES
              .map(cloneDowsureCompanyTemplate)
              .map((item) => [item.name, item]),
          )
          customTemplates.forEach((item) => templatesByName.set(item.name, item))
          dowsureCnyCompanyTemplates.value = Array.from(templatesByName.values())
        }
        // If the saved payload embeds an `_enabled` flag, mirror it onto the
        // in-memory step-enabled map so the tree renders the disabled state
        // that this user previously saved. Missing / true keeps the default
        // (enabled). Doing this here means the state is applied before any
        // scenario is rendered — the scenario tree already respects
        // interfaceStepEnabled when it computes step.enabled.
        if (payload._enabled === false) {
          interfaceStepEnabled[row.step_key] = false
        } else if (payload._enabled === true) {
          interfaceStepEnabled[row.step_key] = true
        }
      }
    }
    scenarioStepOverridesLoaded.value = true
  } catch (error) {
    // Keep scenarioStepOverridesLoaded false so whole-array saves stay blocked
    // instead of writing the builtin-only list back over the stored records.
    pushActivity('error', '加载场景参数偏好失败，请刷新页面后再保存配置', normalizeError(error))
    ElMessage.error('加载已保存的 Mock 配置失败，请刷新页面后再编辑，避免覆盖已有配置')
  }
}

// Guard for the whole-array payloads (shop performance presets, company
// templates). They are rebuilt from the in-memory list on every save, so
// writing before a successful load would drop the stored custom records.
function ensureScenarioStepOverridesLoaded() {
  if (scenarioStepOverridesLoaded.value) return true
  ElMessage.error('已保存的 Mock 配置尚未加载成功，请刷新页面后再编辑，避免覆盖已有配置')
  refreshScenarioStepOverrides()
  return false
}

function getScenarioStepOverride(scenarioKey, stepKey) {
  return scenarioStepOverrides[scenarioStepOverrideKey(scenarioKey, stepKey)] || null
}

function getScenarioStepOverrideDraft(scenarioKey, step) {
  if (!step?.fields?.length) return null
  const key = scenarioStepOverrideKey(scenarioKey, step.key)
  if (!scenarioStepOverrideDraft[key]) {
    const stored = scenarioStepOverrides[key] || {}
    const draft = {}
    for (const field of step.fields) {
      draft[field.key] = stored[field.key] != null ? stored[field.key] : field.default
    }
    scenarioStepOverrideDraft[key] = reactive(draft)
  }
  return scenarioStepOverrideDraft[key]
}

function isStepFieldVisible(field, draft) {
  if (typeof field?.visibleWhen !== 'function') return true
  try {
    return Boolean(field.visibleWhen(draft || {}))
  } catch (error) {
    return true
  }
}

function resetShopPerformancePresetForm() {
  shopPerformancePresetForm.name = ''
  shopPerformancePresetForm.custom_sql = ''
  shopPerformancePresetError.value = ''
  editingShopPerformancePresetName.value = ''
}

async function refreshShopPerformanceBuiltinPresets() {
  if (!authUser.value?.username || shopPerformanceBuiltinLoading.value) return
  shopPerformanceBuiltinLoading.value = true
  try {
    const payload = await fetchShopPerformanceBuiltinPresets(authUser.value.username)
    const builtinRows = Array.isArray(payload?.presets) ? payload.presets : []
    const builtinSqlByName = new Map(
      builtinRows
        .filter((item) => item?.name && item?.custom_sql)
        .map((item) => [String(item.name), String(item.custom_sql)]),
    )
    shopPerformancePresets.value = shopPerformancePresets.value.map((preset) => {
      if (!preset.is_builtin) return preset
      const builtinSql = builtinSqlByName.get(preset.name) || preset.builtin_sql || ''
      return {
        ...preset,
        builtin_sql: builtinSql,
        custom_sql: preset.is_customized ? preset.custom_sql : builtinSql,
      }
    })
  } catch (error) {
    ElMessage.error(error?.payload?.message || error?.message || '加载内置店铺配置失败')
  } finally {
    shopPerformanceBuiltinLoading.value = false
  }
}

async function openShopPerformanceManager() {
  shopPerformanceManagerVisible.value = true
  await refreshShopPerformanceBuiltinPresets()
}

function startNewShopPerformancePreset() {
  resetShopPerformancePresetForm()
  shopPerformanceEditorVisible.value = true
}

function companyImageTypeLabel(imageType) {
  return {
    business_license: '企业营业执照',
    director_id_front: '法人身份证正面',
    director_id_back: '法人身份证反面',
  }[imageType] || imageType
}

function companyImageOptions(imageType) {
  return companyImageTemplates.value
    .filter((item) => item.image_type === imageType)
    .map((item) => ({ label: item.name, value: String(item.id) }))
}

const companyImagePreviewUrl = computed(() => {
  if (companyImageLocalPreview.value) return companyImageLocalPreview.value
  const username = encodeURIComponent(authUser.value?.username || '')
  if (companyImageForm.is_builtin) {
    return `/api/company-image-templates/builtin/${companyImageForm.image_type}/content?username=${username}`
  }
  if (companyImageForm.id) {
    return `/api/company-image-templates/${companyImageForm.id}/content?username=${username}`
  }
  return ''
})

async function refreshCompanyImageTemplates() {
  if (!authUser.value?.username) return
  try {
    const rows = await fetchCompanyImageTemplates(authUser.value.username)
    const templatesByKey = new Map(
      BUILTIN_COMPANY_IMAGE_TEMPLATES.map((item) => [
        `${item.image_type}:${item.name}`,
        { ...item },
      ]),
    )
    if (Array.isArray(rows)) {
      rows.forEach((item) => {
        templatesByKey.set(`${item.image_type}:${item.name}`, { ...item, is_builtin: false })
      })
    }
    companyImageTemplates.value = Array.from(templatesByKey.values())
  } catch (error) {
    pushActivity('error', '加载公司图片模板失败', normalizeError(error))
  }
}

function resetCompanyImageForm() {
  companyImageForm.id = ''
  companyImageForm.name = ''
  companyImageForm.image_type = 'business_license'
  companyImageForm.filename = ''
  companyImageForm.is_builtin = false
  companyImageFile.value = null
  companyImageLocalPreview.value = ''
  companyImageError.value = ''
  companyImageFileInputKey.value += 1
}

function editCompanyImageTemplate(item) {
  companyImageForm.id = item?.is_builtin ? '' : String(item?.id || '')
  companyImageForm.name = item?.name || ''
  companyImageForm.image_type = item?.image_type || 'business_license'
  companyImageForm.filename = item?.filename || ''
  companyImageForm.is_builtin = Boolean(item?.is_builtin)
  companyImageFile.value = null
  companyImageLocalPreview.value = ''
  companyImageError.value = ''
  companyImageFileInputKey.value += 1
}

function handleCompanyImageFileChange(event) {
  companyImageFile.value = event?.target?.files?.[0] || null
  companyImageLocalPreview.value = ''
  if (companyImageFile.value) {
    const reader = new FileReader()
    reader.onload = () => {
      companyImageLocalPreview.value = String(reader.result || '')
    }
    reader.readAsDataURL(companyImageFile.value)
  }
}

async function saveCompanyImageRecord() {
  if (!authUser.value?.username) return
  const name = companyImageForm.name.trim()
  if (!name) {
    companyImageError.value = '请输入图片名称'
    return
  }
  if (!companyImageForm.id && !companyImageFile.value) {
    companyImageError.value = companyImageForm.is_builtin
      ? '替换内置图片时请选择新的图片文件'
      : '请选择要上传的图片'
    return
  }
  companyImageSaving.value = true
  companyImageError.value = ''
  const replacingBuiltin = companyImageForm.is_builtin
  try {
    await saveCompanyImageTemplate(
      {
        username: authUser.value.username,
        name,
        image_type: companyImageForm.image_type,
        file: companyImageFile.value,
      },
      companyImageForm.id || null,
    )
    ElMessage.success(
      companyImageForm.id
        ? '图片配置已更新'
        : (replacingBuiltin ? '内置图片已替换' : '图片配置已创建'),
    )
    resetCompanyImageForm()
    await refreshCompanyImageTemplates()
  } catch (error) {
    companyImageError.value = error?.payload?.detail || error?.payload?.message || error?.message || '保存失败'
    ElMessage.error(companyImageError.value)
  } finally {
    companyImageSaving.value = false
  }
}

async function removeCompanyImageTemplate(item) {
  if (!item?.id || item.is_builtin || !authUser.value?.username) return
  try {
    await ElMessageBox.confirm(`确定删除图片配置「${item.name}」吗？`, '删除图片配置', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    await deleteCompanyImageTemplate(item.id, authUser.value.username)
    if (companyImageForm.id === String(item.id)) resetCompanyImageForm()
    await refreshCompanyImageTemplates()
    ElMessage.success('图片配置已删除')
  } catch (error) {
    ElMessage.error(error?.payload?.message || error?.message || '删除失败')
  }
}

async function openCompanyImageManager() {
  companyImageManagerVisible.value = true
  await refreshCompanyImageTemplates()
}

function normalizeDowsureCompanyTemplate(item) {
  const name = String(item?.name || '').trim()
  const source = item?.template
  const directorSource = item?.directorTemplate
  const contactSource = item?.contactTemplate
  if (
    !name
    || !source
    || typeof source !== 'object'
    || Array.isArray(source)
    || !directorSource
    || typeof directorSource !== 'object'
    || Array.isArray(directorSource)
    || !contactSource
    || typeof contactSource !== 'object'
    || Array.isArray(contactSource)
  ) return null
  const cnName = String(source.cnName || '').trim()
  const regNo = String(source.regNo || '').trim()
  const address = String(source.address || '').trim()
  const directorName = String(directorSource.nameCn || '').trim()
  const directorMobile = String(directorSource.mobileNumber?.number || '').trim()
  const directorExtend = directorSource.dowsurePersonInfoExtend
  const idNumber = String(directorExtend?.idNumber || '').trim()
  const directorAddress = String(directorExtend?.addressDetail || '').trim()
  const dateOfBirth = String(directorSource.dateOfBirth || '').trim()
  const contactName = String(contactSource.fullChineseName || '').trim()
  const contactMobile = String(contactSource.mobileNumber || '').trim()
  const contactEmail = String(contactSource.email || '').trim()
  if (
    !cnName
    || !regNo
    || !address
    || !directorName
    || !directorMobile
    || !idNumber
    || !directorAddress
    || !dateOfBirth
    || !contactName
    || !contactMobile
    || !contactEmail
  ) return null
  const contactNumber = source.contactNumber && typeof source.contactNumber === 'object'
    ? source.contactNumber
    : {}
  return {
    name,
    template: {
      enName: String(source.enName || ''),
      cnName,
      regNo,
      address,
      contactNumber: {
        countryCode: String(contactNumber.countryCode || '+86'),
        number: '',
      },
      operationAddressFlag: source.operationAddressFlag !== false,
      operationAddress: String(source.operationAddress || ''),
      businessDocName: String(source.businessDocName || '营业执照.png'),
    },
    directorTemplate: {
      position: String(directorSource.position || 'DIRECTOR_AND_LEGAL_REPRESENTATIVE'),
      nameCn: directorName,
      nameEn: String(directorSource.nameEn || ''),
      mobileNumber: {
        countryCode: String(directorSource.mobileNumber?.countryCode || '+86'),
        number: directorMobile,
      },
      dowsurePersonInfoExtend: {
        idNumber,
        idCardStartDate: String(directorExtend?.idCardStartDate || ''),
        idCardEndDate: String(directorExtend?.idCardEndDate || ''),
        longTermFlag: String(directorExtend?.longTermFlag ?? 'true'),
        addressDetail: directorAddress,
      },
      dateOfBirth,
      frontDocName: String(directorSource.frontDocName || '身份证正面.png'),
      backDocName: String(directorSource.backDocName || '身份证反面.png'),
      emailAddress: String(directorSource.emailAddress || `${directorMobile}@qq.com`),
      idDocumentType: String(directorSource.idDocumentType || 'PRC_RESIDENT_ID_CARD'),
    },
    contactTemplate: {
      isDraft: Boolean(contactSource.isDraft),
      isExistingPerson: Boolean(contactSource.isExistingPerson),
      selectedPersonId: String(contactSource.selectedPersonId || ''),
      fullChineseName: contactName,
      email: contactEmail,
      mobileNumber: contactMobile,
      phoneCountryCode: String(contactSource.phoneCountryCode || '+86'),
    },
  }
}

function resetDowsureCompanyTemplateForm() {
  dowsureCompanyTemplateForm.name = DEFAULT_DOWSURE_CNY_COMPANY_TEMPLATE.name
  dowsureCompanyTemplateForm.templateText = JSON.stringify(DEFAULT_DOWSURE_CNY_COMPANY_TEMPLATE.template, null, 2)
  dowsureCompanyTemplateForm.directorTemplateText = JSON.stringify(DEFAULT_DOWSURE_CNY_COMPANY_TEMPLATE.directorTemplate, null, 2)
  dowsureCompanyTemplateForm.contactTemplateText = JSON.stringify(DEFAULT_DOWSURE_CNY_COMPANY_TEMPLATE.contactTemplate, null, 2)
  dowsureCompanyTemplateError.value = ''
  editingDowsureCompanyTemplateName.value = ''
}

function startNewDowsureCompanyTemplate() {
  resetDowsureCompanyTemplateForm()
  dowsureCompanyTemplateForm.name = ''
}

function openDowsureCompanyTemplateManager() {
  dowsureCompanyTemplateManagerVisible.value = true
  if (dowsureCnyCompanyTemplates.value.length) {
    editDowsureCompanyTemplate(dowsureCnyCompanyTemplates.value[0])
  } else {
    startNewDowsureCompanyTemplate()
  }
}

function editDowsureCompanyTemplate(item) {
  dowsureCompanyTemplateForm.name = item?.name || ''
  dowsureCompanyTemplateForm.templateText = JSON.stringify(item?.template || {}, null, 2)
  dowsureCompanyTemplateForm.directorTemplateText = JSON.stringify(item?.directorTemplate || {}, null, 2)
  dowsureCompanyTemplateForm.contactTemplateText = JSON.stringify(item?.contactTemplate || {}, null, 2)
  dowsureCompanyTemplateError.value = ''
  editingDowsureCompanyTemplateName.value = item?.name || ''
}

function parseDowsureCompanyTemplate() {
  let parsed
  let directorParsed
  let contactParsed
  try {
    parsed = JSON.parse(dowsureCompanyTemplateForm.templateText || '{}')
    directorParsed = JSON.parse(dowsureCompanyTemplateForm.directorTemplateText || '{}')
    contactParsed = JSON.parse(dowsureCompanyTemplateForm.contactTemplateText || '{}')
  } catch (error) {
    return { error: `三接口模板中存在无效 JSON：${error.message}` }
  }
  const normalized = normalizeDowsureCompanyTemplate({
    name: dowsureCompanyTemplateForm.name,
    template: parsed,
    directorTemplate: directorParsed,
    contactTemplate: contactParsed,
  })
  if (!normalized) {
    return { error: '必须同时完整配置企业、法人和联系人模板，请检查必填姓名、证件号、手机号、邮箱和地址。' }
  }
  return { template: normalized }
}

async function saveDowsureCompanyTemplate() {
  if (!authUser.value?.username) {
    ElMessage.warning('请先登录后再保存公司模板')
    return
  }
  if (!ensureScenarioStepOverridesLoaded()) return
  const name = dowsureCompanyTemplateForm.name.trim()
  if (!name) {
    ElMessage.warning('请输入参数名称')
    return
  }
  const parsed = parseDowsureCompanyTemplate()
  if (parsed.error) {
    dowsureCompanyTemplateError.value = parsed.error
    ElMessage.error(parsed.error)
    return
  }
  dowsureCompanyTemplateError.value = ''
  const existingName = editingDowsureCompanyTemplateName.value
  const nextTemplates = dowsureCnyCompanyTemplates.value
    .filter((item) => item.name !== existingName && item.name !== name)
    .concat(parsed.template)
  const key = scenarioStepOverrideKey(DOWSURE_COMPANY_TEMPLATE_SCENARIO, DOWSURE_COMPANY_TEMPLATE_STEP)
  dowsureCompanyTemplateSaving.value = true
  try {
    await saveScenarioStepOverride({
      username: authUser.value.username,
      scenario_key: DOWSURE_COMPANY_TEMPLATE_SCENARIO,
      step_key: DOWSURE_COMPANY_TEMPLATE_STEP,
      payload: { templates: nextTemplates },
    })
    dowsureCnyCompanyTemplates.value = nextTemplates
    scenarioStepOverrides[key] = { templates: nextTemplates }
    ElMessage.success(`「${name}」已保存，可在企业中文名下拉框中选择`)
    startNewDowsureCompanyTemplate()
  } catch (error) {
    ElMessage.error(error?.payload?.message || error?.message || '保存失败')
  } finally {
    dowsureCompanyTemplateSaving.value = false
  }
}

async function deleteDowsureCompanyTemplate(item) {
  if (!authUser.value?.username || !item?.name) return
  if (BUILTIN_DOWSURE_CNY_COMPANY_TEMPLATE_NAMES.has(item.name)) {
    ElMessage.warning('内置公司模板不能删除')
    return
  }
  if (!ensureScenarioStepOverridesLoaded()) return
  try {
    await ElMessageBox.confirm(`确定删除「${item.name}」吗？`, '删除公司模板', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  const nextTemplates = dowsureCnyCompanyTemplates.value.filter((entry) => entry.name !== item.name)
  const key = scenarioStepOverrideKey(DOWSURE_COMPANY_TEMPLATE_SCENARIO, DOWSURE_COMPANY_TEMPLATE_STEP)
  try {
    await saveScenarioStepOverride({
      username: authUser.value.username,
      scenario_key: DOWSURE_COMPANY_TEMPLATE_SCENARIO,
      step_key: DOWSURE_COMPANY_TEMPLATE_STEP,
      payload: { templates: nextTemplates },
    })
    dowsureCnyCompanyTemplates.value = nextTemplates
    scenarioStepOverrides[key] = { templates: nextTemplates }
    if (editingDowsureCompanyTemplateName.value === item.name) startNewDowsureCompanyTemplate()
    ElMessage.success(`「${item.name}」已删除`)
  } catch (error) {
    ElMessage.error(error?.payload?.message || error?.message || '删除失败')
  }
}

function editShopPerformancePreset(preset) {
  shopPerformancePresetForm.name = preset?.name || ''
  shopPerformancePresetForm.custom_sql = preset?.custom_sql || ''
  shopPerformancePresetError.value = ''
  editingShopPerformancePresetName.value = preset?.name || ''
  shopPerformanceEditorVisible.value = true
}

function validateShopPerformanceCustomSql(customSql) {
  let sql = String(customSql || '').trim()
  if (!sql) return '请输入自定义经营数据 SQL。'
  if (sql.endsWith(';')) sql = sql.slice(0, -1).trim()
  if (sql.includes(';')) return '自定义 SQL 只允许单条 UPDATE，不能包含多个语句。'
  const compactSql = sql.replace(/\s+/g, ' ').trim()
  if (!/^UPDATE\s+(?:dpu_seller_center\.)?dpu_3pl_shop_performance\s+SET\s+/i.test(compactSql)) {
    return '自定义 SQL 必须以 UPDATE dpu_seller_center.dpu_3pl_shop_performance SET 开始。'
  }
  if (!/\sWHERE\s+/i.test(compactSql)) {
    return '自定义 SQL 必须包含 WHERE 条件。'
  }
  if (!/\bamazon_3pl_offer_id\s*=\s*(?:'[^']*'|"[^"]*"|[^\s,)]+)/i.test(compactSql)) {
    return "WHERE 条件必须使用 amazon_3pl_offer_id = '...' 限定目标店铺。"
  }
  const forbidden = compactSql.match(/\b(DELETE|INSERT|REPLACE|DROP|TRUNCATE|ALTER|CREATE|GRANT|REVOKE|CALL)\b/i)
  if (forbidden) {
    return `自定义 SQL 不允许包含 ${forbidden[1].toUpperCase()}。`
  }
  return ''
}

async function saveShopPerformancePreset() {
  if (!authUser.value?.username) {
    ElMessage.warning('请先登录后再保存 Mock 接口参数')
    return
  }
  if (!ensureScenarioStepOverridesLoaded()) return
  const existingName = editingShopPerformancePresetName.value
  const name = BUILTIN_SHOP_PERFORMANCE_NAME_SET.has(existingName)
    ? existingName
    : shopPerformancePresetForm.name.trim()
  const customSql = shopPerformancePresetForm.custom_sql.trim()
  if (!name) {
    ElMessage.warning('请输入参数名称，例如“店铺20”')
    return
  }
  if (!customSql) {
    ElMessage.warning('请输入自定义经营数据 SQL')
    return
  }
  const validationError = validateShopPerformanceCustomSql(customSql)
  if (validationError) {
    shopPerformancePresetError.value = validationError
    ElMessage.error(validationError)
    return
  }
  shopPerformancePresetError.value = ''
  const nextEffectivePresets = shopPerformancePresets.value
    .filter((preset) => preset.name !== existingName && preset.name !== name)
    .concat({
      name,
      custom_sql: customSql,
      builtin_sql: shopPerformancePresets.value.find((preset) => preset.name === name)?.builtin_sql || '',
      is_builtin: BUILTIN_SHOP_PERFORMANCE_NAME_SET.has(name),
      is_customized: true,
    })
  const persistedPresets = serializeShopPerformancePresets(nextEffectivePresets)
  const nextPresets = mergeShopPerformancePresets(persistedPresets)
  const key = scenarioStepOverrideKey(SHOP_PERFORMANCE_PRESET_SCENARIO, SHOP_PERFORMANCE_PRESET_STEP)
  shopPerformancePresetSaving.value = true
  try {
    await saveScenarioStepOverride({
      username: authUser.value.username,
      scenario_key: SHOP_PERFORMANCE_PRESET_SCENARIO,
      step_key: SHOP_PERFORMANCE_PRESET_STEP,
      payload: { presets: persistedPresets },
    })
    shopPerformancePresets.value = nextPresets
    scenarioStepOverrides[key] = { presets: persistedPresets }
    await refreshShopPerformanceBuiltinPresets()
    ElMessage.success(`「${name}」参数已保存，可在接口测试的店铺下拉框中选择`)
    shopPerformanceEditorVisible.value = false
    resetShopPerformancePresetForm()
  } catch (error) {
    ElMessage.error(error?.payload?.message || error?.message || '保存失败')
  } finally {
    shopPerformancePresetSaving.value = false
  }
}

async function deleteShopPerformancePreset(preset) {
  if (!authUser.value?.username || !preset?.name) return
  if (!ensureScenarioStepOverridesLoaded()) return
  const isBuiltin = BUILTIN_SHOP_PERFORMANCE_NAME_SET.has(preset.name)
  if (isBuiltin && !preset.custom_sql) {
    ElMessage.info('当前已经是内置配置')
    return
  }
  try {
    await ElMessageBox.confirm(
      isBuiltin
        ? `确定将「${preset.name}」恢复为后端内置配置吗？`
        : `确定删除「${preset.name}」吗？删除后接口测试下拉框将不再显示该选项。`,
      isBuiltin ? '恢复内置配置' : '删除 Mock 参数',
      {
      type: 'warning',
      confirmButtonText: isBuiltin ? '恢复' : '删除',
      cancelButtonText: '取消',
      },
    )
  } catch {
    return
  }
  const persistedPresets = serializeShopPerformancePresets(
    shopPerformancePresets.value.filter((item) => item.name !== preset.name),
  )
  const nextPresets = mergeShopPerformancePresets(persistedPresets)
  const key = scenarioStepOverrideKey(SHOP_PERFORMANCE_PRESET_SCENARIO, SHOP_PERFORMANCE_PRESET_STEP)
  try {
    await saveScenarioStepOverride({
      username: authUser.value.username,
      scenario_key: SHOP_PERFORMANCE_PRESET_SCENARIO,
      step_key: SHOP_PERFORMANCE_PRESET_STEP,
      payload: { presets: persistedPresets },
    })
    shopPerformancePresets.value = nextPresets
    scenarioStepOverrides[key] = { presets: persistedPresets }
    await refreshShopPerformanceBuiltinPresets()
    if (editingShopPerformancePresetName.value === preset.name) resetShopPerformancePresetForm()
    ElMessage.success(isBuiltin ? `「${preset.name}」已恢复内置配置` : `「${preset.name}」已删除`)
  } catch (error) {
    ElMessage.error(error?.payload?.message || error?.message || '删除失败')
  }
}

function isStepFieldDisabled(field, draft) {
  if (typeof field?.disabledWhen !== 'function') return Boolean(field?.disabled)
  try {
    return Boolean(field.disabledWhen(draft || {}))
  } catch (error) {
    return Boolean(field?.disabled)
  }
}

async function saveScenarioStepOverrideForStep(scenarioKey, step) {
  if (!authUser.value?.username) {
    ElMessage.warning('请先登录后再保存参数')
    return
  }
  if (!step?.fields?.length) return
  const draft = getScenarioStepOverrideDraft(scenarioKey, step)
  const payload = {}
  for (const field of step.fields) {
    if (!isStepFieldVisible(field, draft)) continue
    const value = draft[field.key]
    if (value === '' || value == null) continue
    payload[field.key] = value
  }
  const key = scenarioStepOverrideKey(scenarioKey, step.key)
  // Preserve the _enabled flag if the user previously toggled the step off /
  // on via the scenario tree — saving fresh params shouldn't wipe that state.
  const previous = scenarioStepOverrides[key] || {}
  if (previous._enabled !== undefined) {
    payload._enabled = previous._enabled
  }
  scenarioStepOverrideSaving[key] = true
  try {
    await saveScenarioStepOverride({
      username: authUser.value.username,
      scenario_key: scenarioKey,
      step_key: step.key,
      payload,
    })
    scenarioStepOverrides[key] = { ...payload }
    ElMessage.success(`${step.title} 参数已保存`)
  } catch (error) {
    ElMessage.error(error?.payload?.message || error?.message || '保存失败')
  } finally {
    scenarioStepOverrideSaving[key] = false
  }
}

async function resetScenarioStepOverrideForStep(scenarioKey, step) {
  if (!authUser.value?.username) {
    ElMessage.warning('请先登录后再操作')
    return
  }
  if (!step?.fields?.length) return
  const key = scenarioStepOverrideKey(scenarioKey, step.key)
  scenarioStepOverrideSaving[key] = true
  try {
    await deleteScenarioStepOverride({
      username: authUser.value.username,
      scenario_key: scenarioKey,
      step_key: step.key,
    })
    delete scenarioStepOverrides[key]
    delete scenarioStepOverrideDraft[key]
    ElMessage.success(`${step.title} 已重置为默认参数`)
  } catch (error) {
    ElMessage.error(error?.payload?.message || error?.message || '重置失败')
  } finally {
    scenarioStepOverrideSaving[key] = false
  }
}

async function refreshPromptTemplates() {
  if (!authUser.value?.username) {
    promptTemplates.value = []
    promptTemplatesError.value = '请先登录'
    return
  }
  promptTemplatesLoading.value = true
  promptTemplatesError.value = ''
  try {
    const rows = await fetchPromptTemplates(authUser.value.username)
    promptTemplates.value = Array.isArray(rows) ? rows : []
  } catch (error) {
    promptTemplatesError.value = error?.payload?.message || error?.message || '加载模板失败'
    promptTemplates.value = []
  } finally {
    promptTemplatesLoading.value = false
  }
}

function openPromptTemplateForm(template) {
  if (!isAdmin.value) return
  if (template) {
    promptTemplateForm.id = template.id
    promptTemplateForm.title = template.title
    promptTemplateForm.description = template.description
    promptTemplateForm.logic_type = template.logic_type
    promptTemplateForm.logic = template.logic
    promptTemplateForm.example_prompt = template.example_prompt || ''
    promptTemplateForm.locked_env = template.locked_env || ''
  } else {
    promptTemplateForm.id = null
    promptTemplateForm.title = ''
    promptTemplateForm.description = ''
    promptTemplateForm.logic_type = 'sql'
    promptTemplateForm.logic = ''
    promptTemplateForm.example_prompt = ''
    promptTemplateForm.locked_env = ''
  }
  promptTemplateFormVisible.value = true
}

async function savePromptTemplate() {
  if (!authUser.value?.username) return
  if (!promptTemplateForm.title.trim() || !promptTemplateForm.logic.trim()) {
    ElMessage.warning('标题和逻辑不能为空')
    return
  }
  promptTemplateSaving.value = true
  try {
    const payload = {
      username: authUser.value.username,
      title: promptTemplateForm.title,
      description: promptTemplateForm.description,
      logic_type: promptTemplateForm.logic_type,
      logic: promptTemplateForm.logic,
      example_prompt: promptTemplateForm.example_prompt,
      locked_env: (promptTemplateForm.locked_env || '').trim().toLowerCase() || null,
    }
    if (promptTemplateForm.id) {
      await updatePromptTemplate(promptTemplateForm.id, payload)
      ElMessage.success('模板已更新')
    } else {
      await createPromptTemplate(payload)
      ElMessage.success('模板已创建')
    }
    promptTemplateFormVisible.value = false
    await refreshPromptTemplates()
  } catch (error) {
    ElMessage.error(error?.payload?.message || error?.message || '保存失败')
  } finally {
    promptTemplateSaving.value = false
  }
}

async function removePromptTemplate(template) {
  if (!isAdmin.value || !authUser.value?.username) return
  try {
    await ElMessageBox.confirm(`确定删除模板「${template.title}」吗？`, '提示', { type: 'warning' })
  } catch {
    return
  }
  try {
    await deletePromptTemplate(template.id, { username: authUser.value.username })
    ElMessage.success('模板已删除')
    await refreshPromptTemplates()
  } catch (error) {
    ElMessage.error(error?.payload?.message || error?.message || '删除失败')
  }
}

async function togglePromptTemplateDisabled(template) {
  if (!isAdmin.value || !authUser.value?.username) return
  const nextDisabled = !template.is_disabled
  try {
    const updated = await togglePromptTemplate(template.id, {
      username: authUser.value.username,
      is_disabled: nextDisabled,
    })
    Object.assign(template, updated)
    ElMessage.success(nextDisabled ? '模板已禁用' : '模板已启用')
  } catch (error) {
    ElMessage.error(error?.payload?.message || error?.message || '切换状态失败')
  }
}

function openPromptTemplateUse(template) {
  if (template?.is_disabled) {
    ElMessage.warning('该模板已被管理员禁用，暂不可使用')
    return
  }
  promptTemplateUseTarget.value = template
  promptTemplateUseForm.user_input = ''
  // 重置分列参数：清空旧值，按当前模板占位符建空输入。
  Object.keys(promptTemplateUseParams).forEach((k) => delete promptTemplateUseParams[k])
  for (const key of useDialogTargetPlaceholders.value) {
    promptTemplateUseParams[key] = ''
  }
  // If the template pins an environment (e.g. douke approval), force it and
  // disable the picker in the dialog; otherwise fall back to the user's
  // current session env.
  const lockedEnv = (template?.locked_env || '').trim().toLowerCase()
  promptTemplateUseForm.env = lockedEnv || sessionSummary.value?.env || connectionForm.env || 'reg'
  promptTemplateUseResult.value = null
  promptTemplateUseError.value = ''
  promptTemplateUseVisible.value = true
}

function handlePromptTemplateParamChange(key) {
  if (key === 'psp_type') {
    promptTemplateUseParams.psp_subject_type = ''
  }
  if (key === 'access_mode' && promptTemplateUseParams.access_mode === 'NOT_ADMITTED') {
    promptTemplateUseParams.quota_year1_sales_value = ''
  }
  normalizePromptTemplateShopParams()
}

function getPromptTemplateParamOptions(key) {
  if (key === 'psp_subject_type') {
    const pspType = promptTemplateUseParams.psp_type
    if (['P1', 'P4', 'P5', 'P6', 'P11'].includes(pspType)) {
      return PSP_SUBJECT_TYPE_OPTIONS.payment_user
    }
    return PSP_SUBJECT_TYPE_OPTIONS[pspType] || []
  }
  if (
    key === 'country'
    && promptTemplateUseTarget.value?.title === '广发-豆沙添加店铺'
  ) {
    return [
      { label: 'US', value: 'US' },
      { label: 'DE', value: 'DE' },
    ]
  }
  if (key === 'country' && promptTemplateUseParams.shop_type === '3PL') {
    return [{ label: 'DE', value: 'DE' }]
  }
  if (key === 'sp_mode' && promptTemplateUseParams.shop_type === '3PL') {
    return [{ label: '未授权（NOT_AUTHORIZED）', value: 'NOT_AUTHORIZED' }]
  }
  if (key === 'sp_mode' && promptTemplateUseParams.shop_type === 'SP') {
    return [{ label: '已授权（AUTHORIZED）', value: 'AUTHORIZED' }]
  }
  return PROMPT_PARAM_SELECT_OPTIONS[key] || null
}

function normalizePromptTemplateShopParams() {
  if (promptTemplateUseParams.shop_type === '3PL') {
    promptTemplateUseParams.country = 'DE'
    promptTemplateUseParams.sp_mode = 'NOT_AUTHORIZED'
  }
  if (promptTemplateUseParams.shop_type === 'SP') {
    promptTemplateUseParams.sp_mode = 'AUTHORIZED'
  }
}

function isPromptTemplateParamOptional(key) {
  if (key === 'psp_subject_type') {
    return !getPromptTemplateParamOptions(key).length
  }
  return OPTIONAL_PROMPT_PARAMS.has(key)
}

function copyPromptToAi(template) {
  if (template?.is_disabled) {
    ElMessage.warning('该模板已被管理员禁用，AI 助手不会再触发对应逻辑')
    return
  }
  const text = template?.example_prompt
  if (!text) return
  closeToolRail()
  aiExecutionEnv.value = sessionSummary.value?.env || connectionForm.env || registerForm.env || 'reg'
  currentView.value = 'ai'
  aiInput.value = text
  ElMessage.success('已将完整提示词带入 AI 助手输入框')
}

async function executePromptTemplateAction() {
  const template = promptTemplateUseTarget.value
  if (!template || !authUser.value?.username) return
  // 有占位符时用分列输入拼装 user_input（key = value，逐行），无占位符走自由文本。
  const paramFields = useDialogParamFields.value
  let userInput = ''
  if (paramFields.length) {
    normalizePromptTemplateShopParams()
    const missing = paramFields.filter(
      (f) => !isPromptTemplateParamOptional(f.key) && !String(promptTemplateUseParams[f.key] ?? '').trim(),
    )
    if (missing.length) {
      ElMessage.warning(`请填写：${missing.map((f) => f.label).join('、')}`)
      return
    }
    const invalidPhone = paramFields.find((f) => (
      ['phone', 'phone_number'].includes(f.key)
      && !/^(?:\d{8}|\d{11})$/.test(String(promptTemplateUseParams[f.key] ?? '').trim())
    ))
    if (invalidPhone) {
      ElMessage.warning('请输入 8 位或 11 位数字手机号')
      return
    }
    userInput = paramFields
      .map((f) => `${f.key} = ${String(promptTemplateUseParams[f.key] ?? '').trim()}`)
      .join('\n')
  } else {
    if (!promptTemplateUseForm.user_input.trim()) {
      ElMessage.warning('请输入描述')
      return
    }
    userInput = promptTemplateUseForm.user_input
  }
  promptTemplateUseLoading.value = true
  promptTemplateUseError.value = ''
  promptTemplateUseResult.value = null
  try {
    const payload = {
      username: authUser.value.username,
      user_input: userInput,
      env: promptTemplateUseForm.env || undefined,
    }
    // 有分列参数时把结构化 params 一并传给后端，后端直接机械替换 ${key}、跳过 AI，
    // 避免超长脚本（存储过程）被 AI 截断或改写。
    if (paramFields.length) {
      const params = {}
      for (const f of paramFields) {
        params[f.key] = String(promptTemplateUseParams[f.key] ?? '').trim()
      }
      payload.params = params
    }
    const result = await executePromptTemplate(template.id, payload)
    promptTemplateUseResult.value = result
  } catch (error) {
    const responseData = error?.payload?.data || error?.payload
    if (responseData?.execution || responseData?.summary || responseData?.rendered) {
      promptTemplateUseResult.value = responseData
      promptTemplateUseError.value = error?.payload?.message || responseData?.execution?.message || error?.message || '执行失败'
    } else {
      promptTemplateUseError.value = error?.payload?.message || error?.message || '执行失败'
    }
  } finally {
    promptTemplateUseLoading.value = false
  }
}

async function handleLogin() {
  const username = loginForm.username.trim()
  const password = loginForm.password.trim()
  if (!username || !password) {
    loginError.value = '请输入账号和密码'
    return
  }

  let user
  try {
    user = await loginUser({ username, password })
  } catch (error) {
    const msg = error?.payload?.message || error?.message || ''
    // Server returns success:false with message '__pending__' for pending accounts
    if (msg === '__pending__' || error?.payload?.data?.status === 'pending') {
      pendingReviewUsername.value = username
      pendingReviewStatus.value = 'loading'
      authMode.value = 'register'
      openNotifySocket(username)
      return
    }
    loginError.value = normalizeError(error)
    return
  }

  // Check if response indicates pending (success=false path via unwrap throwing)
  authUser.value = {
    username: user.username,
    role: user.role,
    login_at: new Date().toLocaleString(),
  }
  window.localStorage.setItem(authStorageKey, JSON.stringify(authUser.value))
  loginError.value = ''
  loginForm.password = ''
  currentView.value = 'console'
  closeToolRail()
  pushActivity('auth', user.role === 'admin' ? '管理员已登录' : '用户已登录', {
    username: user.username,
    role: user.role,
  })
}

function openRegisterPage() {
  authMode.value = 'register'
  loginError.value = ''
  registerError.value = ''
  userRegisterForm.username = loginForm.username.trim()
  userRegisterForm.password = ''
  userRegisterForm.answer = ''
  refreshCaptchaChallenge()
}

function openLoginPage() {
  authMode.value = 'login'
  loginError.value = ''
  registerError.value = ''
  userRegisterForm.password = ''
  userRegisterForm.answer = ''
}

function refreshCaptchaChallenge() {
  captchaChallenge.left = Math.floor(Math.random() * 8) + 2
  captchaChallenge.right = Math.floor(Math.random() * 8) + 2
  userRegisterForm.answer = ''
}

async function handleUserRegister() {
  const username = userRegisterForm.username.trim()
  const password = userRegisterForm.password.trim()
  const answer = Number(userRegisterForm.answer)
  const expected = captchaChallenge.left + captchaChallenge.right

  if (!username || !password) {
    registerError.value = '请输入账号和密码'
    return
  }
  if (username === 'admin') {
    registerError.value = 'admin 为管理员账号，不能注册'
    return
  }
  if (!Number.isFinite(answer) || answer !== expected) {
    registerError.value = '验证答案不正确'
    refreshCaptchaChallenge()
    return
  }

  try {
    await registerUser({ username, password })
  } catch (error) {
    registerError.value = normalizeError(error)
    return
  }

  registerError.value = ''
  // Stay on register panel and show inline review status
  pendingReviewUsername.value = username
  pendingReviewStatus.value = 'loading'
  openNotifySocket(username)
}

function handleLogout() {
  const username = authUser.value?.username
  authUser.value = null
  window.localStorage.removeItem(authStorageKey)
  currentView.value = 'console'
  closeToolRail()
  closeSocket()
  closeNotifySocket()
  stopSessionPolling()
  pushActivity('auth', '用户已退出', { username })
}

function openNotifySocket(username) {
  closeNotifySocket()
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const url = `${protocol}//${window.location.host}/ws/notify/${encodeURIComponent(username)}`
  notifySocket = new WebSocket(url)
  notifySocket.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data)
      if (msg.type === 'approved') {
        closeNotifySocket()
        pendingReviewStatus.value = 'approved'
      } else if (msg.type === 'rejected') {
        closeNotifySocket()
        pendingReviewStatus.value = 'rejected'
      }
    } catch {
      // ignore parse errors
    }
  }
  notifySocket.onerror = () => { /* silent */ }
  notifySocket.onclose = () => { notifySocket = null }
}

function closeNotifySocket() {
  if (notifySocket) {
    try { notifySocket.close() } catch { /* ignore */ }
    notifySocket = null
  }
}

function restoreAuthUser() {
  const raw = window.localStorage.getItem(authStorageKey)
  if (!raw) return
  try {
    const saved = JSON.parse(raw)
    if (!saved?.username || !['admin', 'user'].includes(saved.role)) return
    authUser.value = saved
    currentView.value = 'console'
  } catch (error) {
    window.localStorage.removeItem(authStorageKey)
    console.warn('Failed to restore auth user', error)
  }
}

function requireAdminView(fallbackView = 'ai') {
  if (isAdmin.value) return true
  currentView.value = fallbackView === 'logs' || fallbackView === 'contactAdmin' || fallbackView === 'userManagement' ? 'ai' : fallbackView
  ElMessage({
    type: 'warning',
    message: '当前账号无管理员权限',
    duration: 2200,
    showClose: true,
  })
  return false
}

function isPspRowSelectable(row) {
  return String(row?.psp_status || '').toUpperCase() !== 'SUCCESS'
}

function selectPspAuthorizationRow(row) {
  if (!isPspRowSelectable(row)) return
  selectedPspMerchantAccountId.value = row.merchant_account_id
  pspSelectionTouched.value = true
}

function useAiPrompt(prompt) {
  aiInput.value = prompt
}

async function submitContactIssue() {
  const issue = contactForm.issue.trim()
  if (!issue) {
    pushActivity('contact', '问题内容为空', '请先输入需要反馈的问题。')
    return
  }
  try {
    const contactIssue = await createContactIssue({
      created_by: authUser.value?.username,
      issue,
      env: sessionSummary.value?.env || connectionForm.env,
      phone_number: sessionSummary.value?.phone_number || connectionForm.phone_number || null,
      session_id: activeSessionId.value || null,
      merchant_id: sessionSummary.value?.merchant_id || null,
    })
    contactIssues.value.unshift(contactIssue)
    pushActivity('contact', '已留下问题', contactIssue)
    contactForm.issue = ''
  } catch (error) {
    pushActivity('error', '提交问题失败', normalizeError(error))
  }
}

function handleContactAdminLogin() {
  const username = contactAdminForm.username.trim()
  const password = contactAdminForm.password.trim()
  if (username === 'admin' && password === 'admin') {
    contactAdminLoggedIn.value = true
    contactAdminError.value = ''
    contactAdminForm.password = ''
    pushActivity('contact', '联系我们管理员已登录', { username })
    return
  }
  contactAdminError.value = '账号或密码不正确'
}

function handleContactAdminLogout() {
  contactAdminLoggedIn.value = false
  contactAdminForm.username = ''
  contactAdminForm.password = ''
  contactAdminForm.reply = ''
  contactAdminError.value = ''
}

async function replyContactIssue(issue) {
  const reply = contactAdminForm.reply.trim()
  if (!reply) {
    contactAdminError.value = '请先填写回复内容'
    return
  }
  try {
    const updated = await replyContactIssueApi(issue.id, {
      reply,
      replied_by: authUser.value?.username,
    })
    const index = contactIssues.value.findIndex((item) => item.id === issue.id)
    if (index >= 0) contactIssues.value[index] = updated
    contactAdminForm.reply = ''
    contactAdminError.value = ''
    pushActivity('contact', '已回复联系我们问题', {
      issue_id: issue.id,
      reply,
    })
  } catch (error) {
    contactAdminError.value = normalizeError(error)
  }
}

async function deleteContactIssue(issueId) {
  const target = contactIssues.value.find((item) => item.id === issueId)
  if (!target) return
  const confirmed = window.confirm('确认删除这个问题吗？删除后不会再展示在问题记录里。')
  if (!confirmed) return
  try {
    await deleteContactIssueApi(issueId)
    contactIssues.value = contactIssues.value.filter((item) => item.id !== issueId)
    contactAdminError.value = ''
    pushActivity('contact', '已删除联系我们问题', {
      issue_id: issueId,
      status: target.status,
    })
  } catch (error) {
    contactAdminError.value = normalizeError(error)
  }
}

async function loadContactIssues() {
  try {
    contactIssues.value = await fetchContactIssues()
  } catch (error) {
    console.warn('Failed to load contact issues', error)
  }
}

function connectLogs(sessionId) {
  closeSocket()
  wsError.value = ''
  wsConnected.value = false
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const socketUrl = `${protocol}//${window.location.host}/ws/logs/${sessionId}`
  logSocket = new WebSocket(socketUrl)

  logSocket.onopen = () => {
    wsConnected.value = true
  }
  logSocket.onmessage = (event) => {
    try {
      eventLogs.value.unshift(JSON.parse(event.data))
      eventLogs.value = eventLogs.value.slice(0, 300)
    } catch {
      eventLogs.value.unshift({
        timestamp: new Date().toLocaleString(),
        level: 'INFO',
        formatted: event.data,
      })
    }
  }
  logSocket.onerror = () => {
    wsError.value = 'WebSocket 连接失败'
    wsConnected.value = false
  }
  logSocket.onclose = () => {
    wsConnected.value = false
  }
}

function closeSocket() {
  if (logSocket) {
    logSocket.close()
    logSocket = null
  }
}

function normalizeError(error) {
  const detail = error?.response?.data?.detail
  if (typeof detail === 'string') return detail
  return error?.message || '未知错误'
}

function toggleOperationPanel(key) {
  const operation = operations.value.find((item) => item.key === key)
  if (isOperationDisabled(operation)) {
    ElMessage.warning(operationDisabledReason(operation))
    return
  }
  activeOperationKey.value = activeOperationKey.value === key ? '' : key
}

function levelTagType(level) {
  if (level === 'ERROR') return 'danger'
  if (level === 'WARNING') return 'warning'
  if (level === 'INFO') return 'success'
  return 'info'
}

function fieldOptions(field) {
  return (field.options ?? []).map((option) => (
    typeof option === 'object' ? option : { label: option, value: option }
  ))
}

function journeyLabel(journey) {
  return journeyLabels[journey] ?? journey
}

async function establishSession(payload, title = '会话连接成功') {
  const data = await connectSession({
    ...payload,
    username: authUser.value?.username,
  })
  activeSessionId.value = data.session_id
  selectedApplicationUniqueId.value = data.selected_application_unique_id || data.application_unique_id || data.applications?.[0]?.application_unique_id || ''
  pushActivity('connect', title, data)
  await loadSessions()
  connectLogs(data.session_id)
  startSessionPolling()
  return data
}

async function connectAfterRegister(phoneNumber, env) {
  const attempts = 4
  let lastError = null

  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    try {
      return await establishSession(
        { env, phone_number: phoneNumber },
        attempt === 1 ? '注册后已自动连接会话' : `注册后自动连接成功，第 ${attempt} 次重试成功`,
      )
    } catch (error) {
      lastError = error
      if (attempt < attempts) {
        await new Promise((resolve) => window.setTimeout(resolve, 1200))
      }
    }
  }

  throw lastError
}

function buildAiContext() {
  return {
    active_session_id: activeSessionId.value,
    session: sessionSummary.value,
    selected_application_unique_id: selectedApplicationUniqueId.value,
    selected_application: selectedApplication.value,
    selected_env: aiExecutionEnv.value,
    selected_register_env: registerForm.env,
    selected_currency: registerForm.currency,
    selected_funder_resource: registerForm.funder_resource,
    preferred_currency: sessionSummary.value?.preferred_currency,
    selected_journey: registerForm.journey,
    recent_logs: eventLogs.value.slice(0, 20),
    recent_activities: activityFeed.value.slice(0, 12),
  }
}
</script>

<template>
  <div class="app-shell" :class="{ 'theme-dark': darkMode, 'rail-open': isAuthenticated && toolRailOpen }">
    <button
      class="theme-floating-toggle"
      type="button"
      :title="darkMode ? '切换为浅色模式' : '切换为深色模式'"
      :aria-label="darkMode ? '切换为浅色模式' : '切换为深色模式'"
      @click="darkMode = !darkMode"
    >
      <el-icon><Moon v-if="darkMode" /><Sunny v-else /></el-icon>
    </button>
    <div v-if="isAuthenticated" class="console-skyscape" aria-hidden="true">
      <div class="console-skyscape__mountain console-skyscape__mountain--haze"></div>
      <div class="console-skyscape__mountain console-skyscape__mountain--mid"></div>
      <div class="console-skyscape__mountain console-skyscape__mountain--near"></div>
    </div>
    <section v-if="!isAuthenticated" class="login-view">
      <el-card shadow="never" class="login-panel">
        <div class="login-scene" :class="{ active: authMode === 'register' }">
          <div class="login-skyscape" aria-hidden="true">
            <div class="login-skyscape__sky"></div>
            <div class="login-skyscape__sunlight"></div>
            <div class="login-skyscape__mountain login-skyscape__mountain--haze"></div>
            <div class="login-skyscape__mountain login-skyscape__mountain--mid"></div>
            <div class="login-skyscape__mountain login-skyscape__mountain--near"></div>
            <div class="login-skyscape__mountain login-skyscape__mountain--front"></div>
            <div class="login-skyscape__palm login-skyscape__palm--a">
              <span class="login-skyscape__trunk"></span>
              <span class="login-skyscape__leaf login-skyscape__leaf--l"></span>
              <span class="login-skyscape__leaf login-skyscape__leaf--r"></span>
              <span class="login-skyscape__leaf login-skyscape__leaf--lu"></span>
              <span class="login-skyscape__leaf login-skyscape__leaf--ru"></span>
            </div>
            <div class="login-skyscape__palm login-skyscape__palm--b">
              <span class="login-skyscape__trunk"></span>
              <span class="login-skyscape__leaf login-skyscape__leaf--l"></span>
              <span class="login-skyscape__leaf login-skyscape__leaf--r"></span>
              <span class="login-skyscape__leaf login-skyscape__leaf--lu"></span>
              <span class="login-skyscape__leaf login-skyscape__leaf--ru"></span>
            </div>
            <div class="login-skyscape__palm login-skyscape__palm--c">
              <span class="login-skyscape__trunk"></span>
              <span class="login-skyscape__leaf login-skyscape__leaf--l"></span>
              <span class="login-skyscape__leaf login-skyscape__leaf--r"></span>
              <span class="login-skyscape__leaf login-skyscape__leaf--lu"></span>
              <span class="login-skyscape__leaf login-skyscape__leaf--ru"></span>
            </div>
          </div>

          <div class="login-area">
            <div class="login-access">
              <div class="login-card-outer">
                <div class="login-card-inner">
                  <div class="login-card-head">
                    <h1 class="login-title">欢迎回来</h1>
                    <p class="login-subtitle">登录后进入 DPU Mock 控台，管理 session、触发 workflow 并查看实时日志。</p>
                  </div>

                  <el-form label-position="top" class="tight-form login-form" @submit.prevent="handleLogin">
                    <div class="login-inputs">
                      <el-form-item label="账号">
                        <el-input
                          v-model.trim="loginForm.username"
                          :prefix-icon="User"
                          autocomplete="username"
                          placeholder="请输入账号 / 邮箱"
                        />
                      </el-form-item>
                      <el-form-item label="密码">
                        <el-input
                          v-model="loginForm.password"
                          type="password"
                          show-password
                          :prefix-icon="Lock"
                          autocomplete="current-password"
                          placeholder="请输入密码"
                          @keydown.enter.prevent="handleLogin"
                        />
                      </el-form-item>
                    </div>

                    <div class="login-meta-row">
                      <label class="login-remember">
                        <input v-model="loginForm.remember" type="checkbox" />
                        <span>记住我</span>
                      </label>
                      <button type="button" class="login-forgot">忘记密码？</button>
                    </div>

                    <p v-if="loginError" class="login-error">{{ loginError }}</p>

                    <el-button class="login-main-button" type="primary" native-type="submit">
                      <span>登 录</span>
                      <el-icon class="login-main-arrow"><Right /></el-icon>
                    </el-button>

                    <div class="login-secure-pill">
                      <el-icon><CircleCheck /></el-icon>
                      安全连接已启用
                    </div>

                    <p class="login-switch">
                      还没有账号？<button type="button" @click="openRegisterPage">创建账号</button>
                    </p>
                  </el-form>
                </div>
              </div>
            </div>

            <div class="login-register">
              <div class="login-card-outer">
                <div class="login-card-inner">
                  <div class="login-card-head">
                    <h1 class="login-title">创建账号</h1>
                    <p class="login-subtitle">注册一个新账号以使用 Mock 控台，体验完整的 mock 工作流。</p>
                  </div>

                  <el-form v-if="!pendingReviewUsername" label-position="top" class="tight-form login-form register-form" @submit.prevent="handleUserRegister">
                    <div class="login-inputs">
                      <el-form-item label="账号">
                        <el-input
                          v-model.trim="userRegisterForm.username"
                          :prefix-icon="User"
                          autocomplete="username"
                          placeholder="设置账号 / 邮箱"
                        />
                      </el-form-item>
                      <el-form-item label="密码">
                        <el-input
                          v-model="userRegisterForm.password"
                          type="password"
                          show-password
                          :prefix-icon="Lock"
                          autocomplete="new-password"
                          placeholder="设置登录密码"
                          @keydown.enter.prevent="handleUserRegister"
                        />
                      </el-form-item>
                      <el-form-item :label="`验证题：${captchaChallenge.left} + ${captchaChallenge.right} = ?`">
                        <div class="captcha-row">
                          <el-input
                            v-model.trim="userRegisterForm.answer"
                            inputmode="numeric"
                            placeholder="输入计算结果"
                            @keydown.enter.prevent="handleUserRegister"
                          />
                          <el-button plain @click="refreshCaptchaChallenge">换一题</el-button>
                        </div>
                      </el-form-item>
                    </div>

                    <p v-if="registerError" class="login-error">{{ registerError }}</p>

                    <el-button class="login-main-button" type="primary" native-type="submit">
                      <span>注 册</span>
                      <el-icon class="login-main-arrow"><Right /></el-icon>
                    </el-button>

                    <div class="login-secure-pill">
                      <el-icon><CircleCheck /></el-icon>
                      安全连接已启用
                    </div>

                    <p class="login-switch">
                      已有账号？<button type="button" @click="openLoginPage">登录</button>
                    </p>
                  </el-form>

                  <!-- Inline review status (replaces form after submit) -->
                  <div v-else class="register-review-status">
                    <div class="register-review-icon-wrap" :class="pendingReviewStatus">
                      <el-icon v-if="pendingReviewStatus === 'approved'" class="review-icon review-icon--ok"><CircleCheck /></el-icon>
                      <el-icon v-else-if="pendingReviewStatus === 'rejected'" class="review-icon review-icon--fail"><CircleClose /></el-icon>
                      <el-icon v-else class="review-icon review-icon--loading"><Loading /></el-icon>
                    </div>
                    <p v-if="pendingReviewStatus === 'loading'" class="register-review-title">等待管理员审核</p>
                    <p v-else-if="pendingReviewStatus === 'approved'" class="register-review-title register-review-title--ok">审核通过！</p>
                    <p v-else class="register-review-title register-review-title--fail">审核未通过</p>
                    <p class="register-review-hint">
                      <template v-if="pendingReviewStatus === 'loading'">账号 <code>{{ pendingReviewUsername }}</code> 已提交，请等待管理员审核。</template>
                      <template v-else-if="pendingReviewStatus === 'approved'">您的账号已激活，现在可以登录了。</template>
                      <template v-else>请联系管理员了解详情。</template>
                    </p>
                    <el-button
                      v-if="pendingReviewStatus !== 'loading'"
                      type="primary"
                      class="login-main-button"
                      @click="() => { pendingReviewUsername = ''; pendingReviewStatus = ''; closeNotifySocket(); openLoginPage() }"
                    >去登录</el-button>
                    <el-button
                      v-else
                      plain
                      style="margin-top: 8px; width: 100%"
                      @click="() => { pendingReviewUsername = ''; pendingReviewStatus = ''; closeNotifySocket(); openLoginPage() }"
                    >返回登录</el-button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </el-card>
    </section>
    <template v-else>
    <button
      class="tool-edge-toggle"
      :class="{ active: toolRailOpen }"
      type="button"
      :title="toolRailOpen ? '收起工具入口' : '展开工具入口'"
      :aria-label="toolRailOpen ? '收起工具入口' : '展开工具入口'"
      @click="toggleToolRail"
    >
      <el-icon><Fold v-if="toolRailOpen" /><Expand v-else /></el-icon>
      <span>{{ toolRailOpen ? '收起工具' : '展开工具' }}</span>
    </button>
    <div v-if="toolRailOpen && isMobileViewport" class="tool-rail-scrim" @click="closeToolRail(true)"></div>
    <aside class="tool-side-rail" :class="{ open: toolRailOpen }" aria-label="工具入口">
      <div class="tool-side-rail-head">
        <span>工具入口</span>
        <button type="button" aria-label="收起工具入口" @click="closeToolRail(true)">
          <el-icon><Fold /></el-icon>
        </button>
      </div>
      <div class="side-user-card" title="当前登录账号">
        <span class="side-user-avatar">
          <el-icon><User /></el-icon>
        </span>
        <span class="side-user-meta">
          <strong>{{ authDisplayName }}</strong>
          <small>{{ authRoleLabel }}</small>
        </span>
      </div>
      <nav class="side-tool-nav">
        <button class="side-tool-action tone-console" :class="{ active: currentView === 'console' }" type="button" @click="backToConsole">
          <span class="side-tool-icon"><el-icon><Monitor /></el-icon></span>
          <span class="side-tool-label">
            <strong>Mock 控制台</strong>
            <small>session 与 mock 操作</small>
          </span>
        </button>
        <button class="side-tool-action tone-api" :class="{ active: activeToolModule === 'interfaceTest' }" type="button" @click="openInterfaceTestView">
          <span class="side-tool-icon"><el-icon><Tickets /></el-icon></span>
          <span class="side-tool-label">
            <strong>接口测试</strong>
            <small>workflow 调试入口</small>
          </span>
        </button>
        <button class="side-tool-action tone-ai-ui" :class="{ active: activeToolModule === 'aiUi' }" type="button" @click="openAiUiView">
          <span class="side-tool-icon"><el-icon><Cpu /></el-icon></span>
          <span class="side-tool-label">
            <strong>AI UI 自动化</strong>
            <small>视觉驱动 UI 用例</small>
          </span>
        </button>
        <button v-if="isAdmin" class="side-tool-action tone-api" :class="{ active: activeToolModule === 'mockApi' }" type="button" @click="openMockApiView">
          <span class="side-tool-icon"><el-icon><Monitor /></el-icon></span>
          <span class="side-tool-label">
            <strong>Mock 接口</strong>
            <small>经营数据参数配置</small>
          </span>
        </button>
        <button class="side-tool-action tone-activity" :class="{ active: activeToolModule === 'activity' }" type="button" @click="openActivityView">
          <span class="side-tool-icon"><el-icon><Clock /></el-icon></span>
          <span class="side-tool-label">
            <strong>使用日志</strong>
            <small>{{ isAdmin ? '所有用户操作记录' : '我的历史操作记录' }}</small>
          </span>
        </button>
        <button class="side-tool-action tone-monitor" :class="{ active: activeToolModule === 'environmentMonitor' }" type="button" @click="openEnvironmentMonitorView">
          <span class="side-tool-icon"><el-icon><Cpu /></el-icon></span>
          <span class="side-tool-label">
            <strong>环境监测</strong>
            <small>网关检测/请求测试健康度</small>
          </span>
        </button>
        <button class="side-tool-action tone-ai" :class="{ active: activeToolModule === 'ai' }" type="button" @click="openAiPage">
          <span class="side-tool-icon"><el-icon><ChatLineRound /></el-icon></span>
          <span class="side-tool-label">
            <strong>AI 助手</strong>
            <small>智能问答 / SQL 生成</small>
          </span>
        </button>
        <button class="side-tool-action tone-prompt" :class="{ active: activeToolModule === 'promptTemplates' }" type="button" @click="openPromptTemplatesView">
          <span class="side-tool-icon"><el-icon><Tickets /></el-icon></span>
          <span class="side-tool-label">
            <strong>提示词模板</strong>
            <small>{{ isAdmin ? '管理模板 / 描述触发' : '描述触发 admin 预设逻辑' }}</small>
          </span>
        </button>
        <button class="side-tool-action tone-about" :class="{ active: activeToolModule === 'about' }" type="button" @click="openAboutView">
          <span class="side-tool-icon"><el-icon><Document /></el-icon></span>
          <span class="side-tool-label">
            <strong>关于我们</strong>
            <small>项目说明与使用指引</small>
          </span>
        </button>
        <button class="side-tool-action tone-contact" :class="{ active: activeToolModule === 'contact' }" type="button" @click="openContactView">
          <span class="side-tool-icon"><el-icon><Position /></el-icon></span>
          <span class="side-tool-label">
            <strong>联系我们</strong>
            <small>提交问题与建议</small>
          </span>
        </button>
        <button v-if="isAdmin" class="side-tool-action tone-reply" :class="{ active: activeToolModule === 'contactAdmin' }" type="button" @click="openContactAdminView">
          <span class="side-tool-icon"><el-icon><Connection /></el-icon></span>
          <span class="side-tool-label">
            <strong>回复问题</strong>
            <small>管理员答复入口</small>
          </span>
        </button>
        <button v-if="isAdmin" class="side-tool-action tone-users" :class="{ active: activeToolModule === 'userManagement' }" type="button" @click="openUserManagementView">
          <span class="side-tool-icon"><el-icon><Setting /></el-icon></span>
          <span class="side-tool-label">
            <strong>用户管理</strong>
            <small>账号查看与权限维护</small>
          </span>
        </button>
      </nav>

      <button class="side-tool-action logout-action" type="button" @click="handleLogout">
        <span class="side-tool-icon"><el-icon><SwitchButton /></el-icon></span>
        <span class="side-tool-label">
          <strong>退出登录</strong>
          <small>切回登录页</small>
        </span>
      </button>
    </aside>
    <section class="hero-panel">
      <button
        class="hero-tool-toggle"
        :class="{ active: activeToolModule }"
        type="button"
        :title="toolRailCollapsed ? '展开工具入口' : '收起工具入口'"
        :aria-label="toolRailCollapsed ? '展开工具入口' : '收起工具入口'"
        @click="toggleToolRail"
      >
        <el-icon><Expand v-if="toolRailCollapsed" /><Fold v-else /></el-icon>
        <span>{{ toolRailCollapsed ? '展开工具' : '收起工具' }}</span>
      </button>
      <div>
        <span class="eyebrow">
          <span class="eyebrow-dot"></span>
          DPU Mock Console
        </span>
        <h1>DPU Mock API 操作台</h1>
        <p class="hero-copy">
          连接账号、触发 workflow webhook、查看实时日志；所有操作都绑定当前环境和 session。
        </p>
        <div class="hero-status-grid" aria-label="console status">
          <div
            v-for="card in consoleStatusCards"
            :key="card.label"
            class="status-card"
            :class="`tone-${card.tone}`"
          >
            <span>{{ card.label }}</span>
            <strong>{{ card.value }}</strong>
            <code>{{ card.detail }}</code>
          </div>
        </div>
      </div>
      <div class="hero-action-stack">
        <div class="hero-action hero-user-chip" title="当前登录账号">
          <el-icon><User /></el-icon>
          <span>{{ authDisplayName }}</span>
          <el-tag size="small" :type="isAdmin ? 'success' : 'info'" effect="plain">{{ isAdmin ? '管理员' : '用户' }}</el-tag>
        </div>
        <button
          class="hero-action tool-toggle-action"
          :class="{ active: activeToolModule }"
          type="button"
          :title="toolRailCollapsed ? '展开工具入口' : '收起工具入口'"
          :aria-label="toolRailCollapsed ? '展开工具入口' : '收起工具入口'"
          @click="toggleToolRail"
        >
          <el-icon><Expand v-if="toolRailCollapsed" /><Fold v-else /></el-icon>
          <span>{{ toolRailCollapsed ? '展开工具' : '收起工具' }}</span>
        </button>
        <template v-if="!toolRailCollapsed">
          <button class="hero-action" :class="{ active: currentView === 'console' }" type="button" @click="backToConsole">
            <el-icon><Monitor /></el-icon>
            <span>Mock 控制台</span>
          </button>
          <button class="hero-action" :class="{ active: activeToolModule === 'interfaceTest' }" type="button" @click="openInterfaceTestView">
            <el-icon><Tickets /></el-icon>
            <span>接口测试</span>
          </button>
          <button class="hero-action" :class="{ active: activeToolModule === 'activity' }" type="button" @click="openActivityView">
            <el-icon><Clock /></el-icon>
            <span>使用日志</span>
          </button>
          <button class="hero-action" :class="{ active: activeToolModule === 'environmentMonitor' }" type="button" @click="openEnvironmentMonitorView">
            <el-icon><Cpu /></el-icon>
            <span>环境监测</span>
          </button>
          <button class="hero-action" :class="{ active: activeToolModule === 'ai' }" type="button" @click="openAiPage">
            <el-icon><ChatLineRound /></el-icon>
            <span>AI 助手</span>
          </button>
          <button class="hero-action" :class="{ active: activeToolModule === 'about' }" type="button" @click="openAboutView">
            <el-icon><Document /></el-icon>
            <span>关于我们</span>
          </button>
          <button class="hero-action" :class="{ active: activeToolModule === 'contact' }" type="button" @click="openContactView">
            <el-icon><Position /></el-icon>
            <span>联系我们</span>
          </button>
          <button v-if="isAdmin" class="hero-action" :class="{ active: activeToolModule === 'contactAdmin' }" type="button" @click="openContactAdminView">
            <el-icon><Connection /></el-icon>
            <span>回复问题</span>
          </button>
          <button v-if="isAdmin" class="hero-action" :class="{ active: activeToolModule === 'userManagement' }" type="button" @click="openUserManagementView">
            <el-icon><Setting /></el-icon>
            <span>用户管理</span>
          </button>
          <button class="hero-action" type="button" @click="handleLogout">
            <el-icon><SwitchButton /></el-icon>
            <span>退出</span>
          </button>
        </template>
      </div>
    </section>


    <section v-if="currentView === 'interfaceTest'" class="interface-test-view">
      <div class="log-system-head interface-test-head">
        <div>
          <p class="eyebrow">Interface Test</p>
          <h2>接口测试</h2>
          <p>按 workflow 顺序列出所有 mock 接口，选择接口后可查看请求参数、预览 payload 并直接发起调用。</p>
        </div>
        <div class="interface-test-actions">
          <div class="interface-page-switch" role="tablist" aria-label="接口测试页面切换">
            <button
              v-for="mode in interfacePageModes"
              :key="mode.key"
              type="button"
              role="tab"
              :aria-selected="interfacePageMode === mode.key"
              :class="{ active: interfacePageMode === mode.key }"
              @click="switchInterfacePageMode(mode.key)"
            >{{ mode.label }}</button>
          </div>
          <el-tag :type="activeSessionId ? 'success' : 'warning'" effect="plain">{{ activeSessionId ? 'Session 已连接' : '未连接 Session' }}</el-tag>
          <el-button plain :icon="Refresh" @click="backToConsole">返回控制台</el-button>
        </div>
      </div>

      <div v-if="false" class="interface-session-strip">
        <section class="interface-session-card">
          <div class="interface-session-head">
            <div>
              <h3>会话连接</h3>
              <p>自动化执行会自行注册并建立 session，也可以手动绑定已有手机号。</p>
            </div>
            <el-tag :type="activeSessionId ? 'success' : 'warning'" effect="plain">{{ activeSessionId ? '已连接' : '未连接' }}</el-tag>
          </div>
          <div class="interface-session-form">
            <el-select v-model="connectionForm.env" aria-label="连接环境">
              <el-option
                v-for="env in enumOptions?.environments ?? defaultEnvironments"
                :key="`api-connect-${env}`"
                :label="env"
                :value="env"
              />
            </el-select>
            <el-input v-model.trim="connectionForm.phone_number" placeholder="8位或11位数字" />
            <el-button type="primary" :icon="Connection" :loading="connecting" @click="handleConnect">连接 session</el-button>
          </div>
        </section>

        <section class="interface-session-card">
          <div class="interface-session-head">
            <div>
              <h3>新账号注册</h3>
              <p>注册完成后会自动尝试连接，可直接继续接口测试。</p>
            </div>
            <el-switch v-model="registerForm.offline" active-text="线下模式" inactive-text="线上模式" />
          </div>
          <div class="interface-register-form">
            <el-select v-model="registerForm.env" aria-label="注册环境">
              <el-option
                v-for="env in enumOptions?.environments ?? defaultEnvironments"
                :key="`api-reg-${env}`"
                :label="env"
                :value="env"
              />
            </el-select>
            <el-select v-if="!registerForm.offline" v-model="registerForm.journey" aria-label="Journey">
              <el-option
                v-for="journey in enumOptions?.journeys ?? defaultJourneys"
                :key="`api-journey-${journey}`"
                :label="journeyLabel(journey)"
                :value="journey"
              />
            </el-select>
            <el-select v-model="registerForm.currency" aria-label="币种">
              <el-option
                v-for="currency in enumOptions?.currencies ?? defaultCurrencies"
                :key="`api-currency-${currency}`"
                :label="currency"
                :value="currency"
              />
            </el-select>
            <el-select v-model="registerForm.funder_resource" aria-label="资方代码">
              <el-option
                v-for="resource in enumOptions?.funder_resources ?? defaultFunderResources"
                :key="`api-funder-${resource}`"
                :label="resource"
                :value="resource"
              />
            </el-select>
            <el-button
              type="primary"
              :icon="Promotion"
              :loading="registering"
              :disabled="onlineUsdHsbcBlocked"
              :title="onlineUsdHsbcBlocked ? onlineUsdHsbcBlockedReason : ''"
              @click="handleRegister"
            >执行注册</el-button>
            <el-button
              type="primary"
              plain
              :icon="Link"
              :loading="registeringAndBinding"
              :disabled="registerAndBindingBlocked"
              :title="registerAndBindingBlocked ? registerAndBindingBlockedReason : ''"
              @click="handleRegisterAndRunMultiShop"
            >注册并完成绑店</el-button>
          </div>
        </section>
      </div>

      <div class="interface-automation-shell" :class="{ 'is-report': interfacePageMode === 'report' }">
        <aside v-if="interfacePageMode !== 'report'" class="scenario-library" aria-label="场景集合">
          <div v-if="interfacePageMode === 'debug'" class="debug-interface-list">
            <div class="scenario-tree-head">
              <strong>
                调试接口 ({{ filteredDebugInterfaceSteps.length }}<template v-if="debugInterfaceSearch.trim()">/{{ debugInterfaceSteps.length }}</template>)
              </strong>
              <el-tag size="small" effect="plain">全局接口</el-tag>
            </div>
            <el-input
              v-model.trim="debugInterfaceSearch"
              class="debug-interface-search"
              size="small"
              clearable
              placeholder="搜索接口名 / endpoint / 场景"
            />
            <div v-if="!filteredDebugInterfaceSteps.length" class="debug-interface-empty">
              没有匹配接口。
            </div>
            <button
              v-for="(step, index) in filteredDebugInterfaceSteps"
              :key="`debug-interface-${step.key}`"
              class="debug-interface-item"
              :class="{ active: activeOperationKey === step.key }"
              type="button"
              @click="selectDebugInterface(step.key)"
            >
              <span class="scenario-tree-step-index">{{ index + 1 }}</span>
              <span
                class="scenario-tree-step-method"
                :class="step.type === 'script' ? 'is-script' : 'is-api'"
              >{{ step.type === 'script' ? 'SCRIPT' : (step.method || 'POST') }}</span>
              <span class="debug-interface-title" :title="`${step.title}\n${step.endpoint}`">
                <strong>{{ step.title }}</strong>
                <small>{{ step.endpoint }}</small>
                <em>{{ step.debugSources?.length || 1 }} 个场景使用</em>
              </span>
              <span
                class="scenario-tree-step-dot"
                :class="`is-${scenarioStepStatus(step.key)}`"
                :title="scenarioStepStatus(step.key)"
              ></span>
            </button>
          </div>
          <div v-else class="scenario-tree">
            <div class="scenario-tree-head">
              <strong>全部场景 ({{ filteredInterfaceScenarioCount }})</strong>
              <el-tag size="small" effect="plain">DPU产品流程</el-tag>
            </div>

            <div
              v-for="directory in filteredInterfaceScenarioGroups"
              :key="directory.key"
              class="scenario-tree-directory"
            >
              <div
                class="scenario-tree-directory-node"
                role="button"
                tabindex="0"
                @click="toggleScenarioDirectory(directory.key)"
                @keydown.enter.prevent="toggleScenarioDirectory(directory.key)"
                @keydown.space.prevent="toggleScenarioDirectory(directory.key)"
              >
                <button
                  class="scenario-tree-toggle"
                  type="button"
                  :aria-label="scenarioDirectoryExpanded(directory.key) ? '收起' : '展开'"
                  @click.stop="toggleScenarioDirectory(directory.key)"
                >
                  <el-icon>
                    <ArrowDown v-if="scenarioDirectoryExpanded(directory.key)" />
                    <ArrowRight v-else />
                  </el-icon>
                </button>
                <span class="scenario-tree-name">{{ directory.name }}</span>
                <small>{{ directory.scenarios.length }}</small>
              </div>

              <div v-if="scenarioDirectoryExpanded(directory.key)" class="scenario-tree-scenario-list">
                <div
                  v-for="scenario in directory.scenarios"
                  :key="scenario.key"
                  class="scenario-tree-group"
                  :class="{ active: activeInterfaceScenarioKey === scenario.key }"
                >
                  <div
                    class="scenario-tree-node"
                    role="button"
                    tabindex="0"
                    @click="selectScenarioFromTree(scenario.key)"
                    @keydown.enter.prevent="selectScenarioFromTree(scenario.key)"
                    @keydown.space.prevent="selectScenarioFromTree(scenario.key)"
                  >
                    <button
                      class="scenario-tree-toggle"
                      type="button"
                      :aria-label="expandedScenarioTrees[scenario.key] ? '收起' : '展开'"
                      @click.stop="toggleScenarioTreeNode(scenario.key)"
                    >
                      <el-icon>
                        <ArrowDown v-if="expandedScenarioTrees[scenario.key]" />
                        <ArrowRight v-else />
                      </el-icon>
                    </button>
                    <span class="scenario-tree-name">{{ scenario.name }}</span>
                    <small>{{ scenario.steps.length }}</small>
                  </div>

                  <ul v-if="expandedScenarioTrees[scenario.key]" class="scenario-tree-step-list">
                    <li
                      v-for="(step, index) in scenario.steps"
                      :key="`${scenario.key}-${step.key}`"
                      class="scenario-tree-step"
                      :class="{
                        active: activeInterfaceScenarioKey === scenario.key && activeOperationKey === step.key && interfacePageMode === 'scenario' && interfaceFocusMode === 'step',
                        disabled: interfaceStepEnabled[step.key] === false,
                        'is-dragging': scenarioDragState.scenarioKey === scenario.key && scenarioDragState.stepKey === step.key,
                        'not-draggable': !isAdmin,
                      }"
                      :draggable="isAdmin"
                      @click="selectStepFromTree(scenario.key, step.key)"
                      @dragstart="isAdmin && onScenarioStepDragStart($event, scenario.key, step.key)"
                      @dragover.prevent="isAdmin && onScenarioStepDragOver($event, scenario.key, step.key)"
                      @drop.prevent="isAdmin && onScenarioStepDrop($event, scenario.key, step.key)"
                      @dragend="onScenarioStepDragEnd"
                    >
                      <span v-if="isAdmin" class="scenario-tree-step-handle" title="拖动调整顺序">⋮⋮</span>
                      <span v-else class="scenario-tree-step-handle scenario-tree-step-handle--placeholder"></span>
                      <span class="scenario-tree-step-index">{{ index + 1 }}</span>
                      <span
                        class="scenario-tree-step-method"
                        :class="step.type === 'script' ? 'is-script' : 'is-api'"
                      >{{ step.type === 'script' ? 'SCRIPT' : (step.method || 'POST') }}</span>
                      <span class="scenario-tree-step-title" :title="step.title">{{ step.title }}</span>
                      <el-switch
                        :model-value="interfaceStepEnabled[step.key] !== false"
                        size="small"
                        class="scenario-tree-step-switch"
                        @click.stop
                        @change="(val) => { interfaceStepEnabled[step.key] = val }"
                      />
                      <span
                        class="scenario-tree-step-dot"
                        :class="`is-${scenarioStepStatus(step.key)}`"
                        :title="scenarioStepStatus(step.key)"
                      ></span>
                    </li>
                  </ul>
                </div>
              </div>
            </div>
          </div>
        </aside>

        <main class="scenario-workbench">
          <div class="scenario-toolbar">
            <div class="scenario-title-block">
              <div class="scenario-status-line">
                <strong>{{ interfacePageMode === 'debug' ? '单接口调试' : activeInterfaceScenario.name }}</strong>
              </div>
              <p v-if="interfacePageMode === 'debug'">
                汇总所有场景里出现过的接口，选择一个接口后配置真实上游请求头和请求体单独调用。
              </p>
              <p v-else>{{ activeInterfaceScenario.description }} · {{ enabledInterfaceStepCount }} / {{ interfaceAutomationSteps.length }} 个步骤启用</p>
            </div>
            <div class="scenario-run-actions">
              <el-select v-model="connectionForm.env" class="scenario-env-select" aria-label="执行环境">
                <el-option
                  v-for="env in enumOptions?.environments ?? defaultEnvironments"
                  :key="`scenario-env-${env}`"
                  :label="env"
                  :value="env"
                />
              </el-select>
              <template v-if="interfacePageMode !== 'debug'">
                <el-button type="primary" :icon="Promotion" :loading="scenarioExecuting" @click="handleScenarioServerExecute">服务端执行</el-button>
                <el-button
                  type="danger"
                  plain
                  :disabled="!scenarioExecuting || scenarioStopRequested"
                  @click="handleScenarioStop"
                >{{ scenarioStopRequested ? '停止中…' : '停止' }}</el-button>
                <el-button v-if="isAdmin" type="primary" plain :disabled="scenarioExecuting" @click="handleScenarioSave">保存</el-button>
              </template>
            </div>
          </div>

          <section v-if="latestScenarioRunContext" class="scenario-panel scenario-run-context">
            <div><span>执行环境</span><strong>{{ latestScenarioRunContext.env || '-' }}</strong></div>
            <div><span>手机号</span><strong>{{ latestScenarioRunContext.phone_number || '-' }}</strong></div>
            <div><span>Merchant ID</span><strong>{{ latestScenarioRunContext.merchant_id || '-' }}</strong></div>
            <div><span>Application Unique ID</span><strong>{{ latestScenarioRunContext.application_unique_id || '-' }}</strong></div>
          </section>

          <div v-if="interfacePageMode === 'scenario' && interfaceFocusMode !== 'step'" class="scenario-tabs">
            <button
              v-for="tab in scenarioTabs"
              :key="tab.key"
              type="button"
              :class="{ active: activeScenarioTab === tab.key }"
              @click="activeScenarioTab = tab.key"
            >{{ tab.label }}</button>
          </div>

          <template v-if="interfacePageMode === 'scenario' && interfaceFocusMode !== 'step'">
          <section v-if="activeScenarioTab === 'base'" class="scenario-panel scenario-base-panel">
            <div class="scenario-base-item">
              <span>场景名称</span>
              <strong>{{ activeInterfaceScenario.name }}</strong>
              <button
                v-if="isAdmin"
                class="scenario-base-edit"
                type="button"
                title="编辑场景名称与描述"
                @click="openScenarioMetaEditor"
              >
                <el-icon><Edit /></el-icon>
              </button>
            </div>
            <div class="scenario-base-description scenario-base-item">
              <span>场景描述</span>
              <strong>{{ activeInterfaceScenario.description || '-' }}</strong>
            </div>
            <div class="scenario-base-item">
              <span>步骤启用</span>
              <strong>{{ enabledInterfaceStepCount }} / {{ interfaceAutomationSteps.length }}</strong>
            </div>
          </section>

          <section v-else-if="activeScenarioTab === 'params'" class="scenario-panel">
            <div class="scenario-panel-head">
              <strong>场景变量</strong>
              <span>变量会在执行时注入到请求体和脚本上下文。</span>
            </div>
            <div class="scenario-variable-table">
              <div><span>Key</span><span>Value</span><span>Scope</span></div>
              <div v-for="(value, key) in scenarioVariables" :key="key">
                <strong>{{ key }}</strong>
                <el-input v-model="scenarioVariables[key]" />
                <span>Scenario</span>
              </div>
            </div>
          </section>

          <section v-else-if="activeScenarioTab === 'hooks'" class="scenario-panel scenario-hooks-panel">
            <div>
              <strong>前置操作</strong>
              <p>初始化 env、session、手机号、merchant 变量；校验当前用户登录状态。</p>
            </div>
            <div>
              <strong>后置操作</strong>
              <p>写入执行历史、刷新会话摘要、保留最近响应和错误信息。</p>
            </div>
          </section>

          <section v-else-if="activeScenarioTab === 'assertions'" class="scenario-panel">
            <div class="scenario-panel-head">
              <strong>统一断言</strong>
              <span>执行结果需要同时满足 HTTP、业务成功和 trace 信息。</span>
            </div>
            <div class="scenario-assertion-list">
              <label v-for="assertion in scenarioAssertions" :key="assertion.target">
                <el-checkbox v-model="assertion.enabled" />
                <strong>{{ assertion.target }}</strong>
                <span>{{ assertion.rule }}</span>
              </label>
            </div>
          </section>

          <section v-else-if="activeScenarioTab === 'history'" class="scenario-panel">
            <div class="scenario-panel-head">
              <strong>执行历史</strong>
              <span>本机持续保留服务端执行记录。</span>
            </div>
            <div v-if="scenarioExecutionHistory.length === 0" class="scenario-empty">暂无执行历史。</div>
            <div v-for="item in scenarioExecutionHistory" :key="item.id" class="scenario-history-row">
              <el-tag :type="item.status === '完成' ? 'success' : item.status === '未执行' ? 'warning' : 'danger'" effect="plain">{{ item.status }}</el-tag>
              <strong>{{ item.scenario }}</strong>
              <span>{{ item.env }}</span>
              <span>{{ item.at }}</span>
              <span>成功 {{ item.success }} / 跳过 {{ item.skipped }} / 失败 {{ item.failed }}</span>
              <code>{{ item.duration }}</code>
              <el-button size="small" plain @click="openScenarioHistoryDetail(item)">详情</el-button>
            </div>
          </section>

          <section v-else-if="activeScenarioTab === 'settings'" class="scenario-panel scenario-settings-panel">
            <label><span>失败后停止</span><el-switch v-model="scenarioSettings.stopOnFailure" /></label>
            <label><span>保存响应详情</span><el-switch v-model="scenarioSettings.saveResponse" /></label>
            <label><span>执行前校验 session</span><el-switch v-model="scenarioSettings.validateSession" /></label>
            <label><span>默认超时</span><el-input v-model="scenarioSettings.timeout" /></label>
          </section>
          </template>

          <template v-else-if="selectedInterfaceStep && (interfacePageMode === 'debug' || (interfacePageMode === 'scenario' && interfaceFocusMode === 'step'))">
            <section class="step-editor">
              <div v-if="interfacePageMode === 'debug'" class="debug-request-console">
                <div class="debug-request-console-head">
                  <div>
                    <strong>单接口调试</strong>
                    <span>{{ selectedInterfaceStep.title }}</span>
                  </div>
                  <div class="debug-request-state">
                    <span
                      class="step-editor-status"
                      :class="`is-${scenarioStepStatus(selectedInterfaceStep.key)}`"
                    >
                      {{ scenarioStepStatus(selectedInterfaceStep.key) === 'success' ? '成功' : scenarioStepStatus(selectedInterfaceStep.key) === 'error' ? '失败' : '未执行' }}
                    </span>
                    <span v-if="scenarioStepResults[selectedInterfaceStep.key]?.durationMs != null" class="step-editor-duration">
                      {{ formatStepDuration(scenarioStepResults[selectedInterfaceStep.key].durationMs) }}
                    </span>
                  </div>
                </div>
                <div class="debug-request-urlbar">
                  <el-select model-value="HTTP" class="debug-protocol-select" disabled>
                    <el-option label="HTTP" value="HTTP" />
                  </el-select>
                  <el-select v-model="debugActualMethod" class="debug-method-select">
                    <el-option label="GET" value="GET" />
                    <el-option label="POST" value="POST" />
                    <el-option label="PUT" value="PUT" />
                    <el-option label="PATCH" value="PATCH" />
                    <el-option label="DELETE" value="DELETE" />
                  </el-select>
                  <el-input
                    v-model.trim="debugActualUrlText"
                    class="debug-url-input"
                    placeholder="https://dpu-gateway-reg.dowsure.com/..."
                  />
                  <button
                    class="step-editor-send"
                    type="button"
                    :disabled="debugSending"
                    @click="handleDebugStepRun"
                  >
                    <el-icon><Promotion /></el-icon>
                    <span>{{ debugSending ? '发送中' : '服务端执行' }}</span>
                  </button>
                  <button class="step-editor-send is-plain" type="button" :disabled="debugSending" @click="resetDebugRequestDraft()">
                    <el-icon><Refresh /></el-icon>
                    <span>重置</span>
                  </button>
                </div>
              </div>
              <div v-else class="step-editor-head">
                <span class="step-editor-method" :class="methodBadgeClass(selectedInterfaceStep)">
                  {{ selectedInterfaceStep.type === 'script' ? 'SCRIPT' : (selectedInterfaceStep.method || 'POST') }}
                </span>
                <code class="step-editor-endpoint" :title="selectedInterfaceStep.endpoint">{{ selectedInterfaceStep.endpoint }}</code>
                <span
                  class="step-editor-status"
                  :class="`is-${scenarioStepStatus(selectedInterfaceStep.key)}`"
                >
                  {{ scenarioStepStatus(selectedInterfaceStep.key) === 'success' ? '成功' : scenarioStepStatus(selectedInterfaceStep.key) === 'error' ? '失败' : '未执行' }}
                </span>
                <span v-if="scenarioStepResults[selectedInterfaceStep.key]?.durationMs != null" class="step-editor-duration">
                  {{ formatStepDuration(scenarioStepResults[selectedInterfaceStep.key].durationMs) }}
                </span>
                <button
                  v-if="interfacePageMode === 'debug'"
                  class="step-editor-send"
                  type="button"
                  :disabled="debugSending"
                  @click="handleDebugStepRun"
                >
                  <el-icon><Promotion /></el-icon>
                  <span>{{ debugSending ? '发送中' : '发送' }}</span>
                </button>
                <button v-if="interfacePageMode === 'debug'" class="step-editor-send is-plain" type="button" :disabled="debugSending" @click="resetDebugRequestDraft()">
                  <el-icon><Refresh /></el-icon>
                  <span>重置</span>
                </button>
              </div>

              <h3 class="step-editor-title">{{ selectedInterfaceStep.title }}</h3>
              <p class="step-editor-desc">{{ getScenarioStepDescription(selectedInterfaceStep).description }}</p>
              <el-alert
                v-if="debugRequestError"
                class="debug-request-alert"
                type="error"
                :title="debugRequestError"
                show-icon
                :closable="false"
              />

              <div class="step-editor-tabs">
                <button
                  v-for="tab in activeStepEditorTabs"
                  :key="tab.key"
                  type="button"
                  :class="{ active: stepFocusTab === tab.key }"
                  @click="stepFocusTab = tab.key"
                >{{ tab.label }}</button>
              </div>

              <section v-if="stepFocusTab === 'params'" class="step-editor-panel">
                <div class="scenario-description-grid">
                  <div>
                    <span>Method</span>
                    <code>{{ getScenarioStepDescription(selectedInterfaceStep).method }}</code>
                  </div>
                  <div>
                    <span>Endpoint</span>
                    <code>{{ getScenarioStepDescription(selectedInterfaceStep).endpoint }}</code>
                  </div>
                  <div>
                    <span>Fields</span>
                    <strong>
                      {{ (selectedInterfaceStep.fields?.length || getScenarioStepDescription(selectedInterfaceStep).fieldCount) }} 个参数
                    </strong>
                  </div>
                </div>

                <div v-if="interfacePageMode === 'debug'" class="debug-source-summary">
                  <strong>接口来源</strong>
                  <span
                    v-for="source in selectedInterfaceStep.debugSources || []"
                    :key="`debug-source-${selectedInterfaceStep.key}-${source.scenarioKey}-${source.stepKey}`"
                  >{{ source.scenarioName }} #{{ source.order }}</span>
                </div>

                <!-- Configurable fields (saved per user, used on next run) -->
                <template v-else-if="selectedInterfaceStep.fields?.length">
                  <div class="scenario-step-config-form">
                    <div
                      v-for="field in selectedInterfaceStep.fields"
                      v-show="isStepFieldVisible(field, getScenarioStepOverrideDraft(activeInterfaceScenario.key, selectedInterfaceStep))"
                      :key="`step-config-${selectedInterfaceStep.key}-${field.key}`"
                      class="scenario-step-config-row"
                    >
                      <label>
                        <span>{{ field.label }}</span>
                        <code>{{ field.key }}</code>
                      </label>
                      <el-select
                        v-if="field.type === 'select'"
                        v-model="getScenarioStepOverrideDraft(activeInterfaceScenario.key, selectedInterfaceStep)[field.key]"
                        class="scenario-step-config-input"
                        :disabled="isStepFieldDisabled(field, getScenarioStepOverrideDraft(activeInterfaceScenario.key, selectedInterfaceStep))"
                      >
                        <el-option
                          v-for="option in field.options || []"
                          :key="`step-config-opt-${selectedInterfaceStep.key}-${field.key}-${option.value}`"
                          :label="option.label"
                          :value="option.value"
                        />
                      </el-select>
                      <el-input
                        v-else-if="field.type === 'number'"
                        v-model.number="getScenarioStepOverrideDraft(activeInterfaceScenario.key, selectedInterfaceStep)[field.key]"
                        type="number"
                        class="scenario-step-config-input"
                        :disabled="isStepFieldDisabled(field, getScenarioStepOverrideDraft(activeInterfaceScenario.key, selectedInterfaceStep))"
                      />
                      <el-input
                        v-else-if="field.type === 'textarea'"
                        v-model="getScenarioStepOverrideDraft(activeInterfaceScenario.key, selectedInterfaceStep)[field.key]"
                        type="textarea"
                        :autosize="field.autosize || { minRows: 4, maxRows: 10 }"
                        :placeholder="field.placeholder || ''"
                        class="scenario-step-config-input"
                        :disabled="isStepFieldDisabled(field, getScenarioStepOverrideDraft(activeInterfaceScenario.key, selectedInterfaceStep))"
                      />
                      <el-input
                        v-else
                        v-model="getScenarioStepOverrideDraft(activeInterfaceScenario.key, selectedInterfaceStep)[field.key]"
                        class="scenario-step-config-input"
                        :disabled="isStepFieldDisabled(field, getScenarioStepOverrideDraft(activeInterfaceScenario.key, selectedInterfaceStep))"
                      />
                      <small v-if="field.hint" class="scenario-step-config-note">{{ field.hint }}</small>
                    </div>
                  </div>
                  <div v-if="isAuthenticated" class="scenario-step-config-actions">
                    <el-button
                      type="primary"
                      :loading="scenarioStepOverrideSaving[scenarioStepOverrideKey(activeInterfaceScenario.key, selectedInterfaceStep.key)]"
                      @click="saveScenarioStepOverrideForStep(activeInterfaceScenario.key, selectedInterfaceStep)"
                    >保存参数</el-button>
                    <el-button
                      plain
                      :disabled="!scenarioStepOverrides[scenarioStepOverrideKey(activeInterfaceScenario.key, selectedInterfaceStep.key)]"
                      @click="resetScenarioStepOverrideForStep(activeInterfaceScenario.key, selectedInterfaceStep)"
                    >重置为默认</el-button>
                    <span
                      v-if="scenarioStepOverrides[scenarioStepOverrideKey(activeInterfaceScenario.key, selectedInterfaceStep.key)]"
                      class="scenario-step-config-hint"
                    >已保存自定义参数，下次执行场景会自动使用</span>
                    <span v-else class="scenario-step-config-hint">未保存，执行时使用默认值</span>
                  </div>
                  <div v-else class="scenario-step-config-actions">
                    <span class="scenario-step-config-hint">
                      {{ scenarioStepOverrides[scenarioStepOverrideKey(activeInterfaceScenario.key, selectedInterfaceStep.key)]
                        ? '当前使用已保存参数（只读）'
                        : '当前使用默认参数（登录后可修改并保存）' }}
                    </span>
                  </div>
                </template>
                <div v-else-if="getScenarioStepDescription(selectedInterfaceStep).fields.length" class="scenario-field-summary">
                  <div
                    v-for="field in getScenarioStepDescription(selectedInterfaceStep).fields"
                    :key="`step-editor-field-${selectedInterfaceStep.key}-${field.prop}`"
                  >
                    <strong>{{ field.label }}</strong>
                    <code>{{ field.prop }}</code>
                    <span>{{ field.type }}</span>
                  </div>
                </div>
                <div v-else class="response-empty">该步骤没有可配置参数。</div>
                <div v-if="interfacePageMode !== 'debug' && isAdmin && selectedInterfaceStep" class="scenario-step-admin-actions">
                  <el-button
                    plain
                    :icon="Plus"
                    @click="openScenarioAddStep(activeInterfaceScenario, selectedInterfaceStep)"
                  >添加步骤</el-button>
                  <el-button
                    plain
                    :icon="Edit"
                    @click="openScenarioStepMetaEditor(activeInterfaceScenario, selectedInterfaceStep)"
                  >编辑步骤</el-button>
                  <el-button
                    plain
                    type="danger"
                    :icon="Delete"
                    @click="hideScenarioStepMeta(activeInterfaceScenario, selectedInterfaceStep)"
                  >删除步骤</el-button>
                </div>
              </section>

              <section v-else-if="stepFocusTab === 'body'" class="step-editor-panel response-block">
                <div class="response-block-head">
                  <strong>MockAPI Request Body</strong>
                  <el-tag size="small" effect="plain">本地封装层预览</el-tag>
                </div>
                <pre>{{ JSON.stringify(getDebugStepPayload(selectedInterfaceStep), null, 2) }}</pre>
              </section>

              <section v-else-if="stepFocusTab === 'headers'" class="step-editor-panel response-block">
                <div class="response-block-head">
                  <strong>MockAPI Request Headers</strong>
                  <el-tag size="small" effect="plain">本地封装层预览</el-tag>
                </div>
                <pre>{{ JSON.stringify({ 'Content-Type': 'application/json' }, null, 2) }}</pre>
              </section>

              <section v-else-if="stepFocusTab === 'response'" class="step-editor-panel response-block">
                <div class="response-block-head">
                  <strong>Response</strong>
                  <el-tag
                    size="small"
                    :type="getScenarioResponseState(selectedInterfaceStep).type"
                    effect="plain"
                  >{{ getScenarioResponseState(selectedInterfaceStep).label }}</el-tag>
                  <span v-if="scenarioStepResults[selectedInterfaceStep.key]?.durationMs != null" class="response-meta">
                    {{ formatStepDuration(scenarioStepResults[selectedInterfaceStep.key].durationMs) }}
                  </span>
                  <button
                    v-if="getScenarioStepResponse(selectedInterfaceStep)"
                    class="response-copy"
                    type="button"
                    title="复制响应"
                    @click="copyResponseText(getScenarioStepResponse(selectedInterfaceStep))"
                  >
                    <el-icon><DocumentCopy /></el-icon>
                    <span>复制</span>
                  </button>
                </div>
                <pre v-if="getScenarioStepResponse(selectedInterfaceStep)">{{ JSON.stringify(getScenarioStepResponse(selectedInterfaceStep), null, 2) }}</pre>
                <div v-else class="response-empty">执行该步骤后在这里查看最新响应。</div>
              </section>

              <section v-else-if="stepFocusTab === 'actualBody'" class="step-editor-panel response-block">
                <div class="response-block-head">
                  <strong>实际请求体</strong>
                  <div class="response-block-actions">
                    <el-tag size="small" effect="plain">{{ interfacePageMode === 'debug' ? '编辑上游 URL 和 body 后发送' : '场景执行时发往上游的真实 body' }}</el-tag>
                    <button
                      v-if="interfacePageMode === 'debug'"
                      class="response-copy"
                      type="button"
                      title="格式化 JSON"
                      @click="prettifyDebugJsonDraft('body')"
                    >
                      <span>格式化 JSON</span>
                    </button>
                  </div>
                </div>
                <template v-if="interfacePageMode === 'debug'">
                  <el-input
                    v-model="debugRequestBodyText"
                    type="textarea"
                    :autosize="{ minRows: 18, maxRows: 34 }"
                    class="debug-json-editor"
                    spellcheck="false"
                    placeholder="{ }"
                  />
                </template>
                <template v-else-if="getScenarioStepActualRequests(selectedInterfaceStep).length">
                  <div
                    v-for="(req, idx) in getScenarioStepActualRequests(selectedInterfaceStep)"
                    :key="`actual-body-${selectedInterfaceStep.key}-${idx}`"
                    class="actual-request-item"
                  >
                    <div class="actual-request-meta">
                      <el-tag
                        v-if="getScenarioStepActualRequests(selectedInterfaceStep).length > 1"
                        size="small"
                        effect="plain"
                      >#{{ idx + 1 }}</el-tag>
                      <code class="actual-request-method">{{ req.method || 'POST' }}</code>
                      <span class="actual-request-url">{{ req.url || '-' }}</span>
                    </div>
                    <pre>{{ req.body == null ? '(无 body)' : (typeof req.body === 'string' ? req.body : JSON.stringify(req.body, null, 2)) }}</pre>
                  </div>
                </template>
                <div v-else class="response-empty">执行该步骤后可在这里查看真正发往上游的请求体。</div>
              </section>

              <section v-else-if="stepFocusTab === 'actualHeaders'" class="step-editor-panel response-block">
                <div class="response-block-head">
                  <strong>实际请求头</strong>
                  <div class="response-block-actions">
                    <el-tag size="small" effect="plain">{{ interfacePageMode === 'debug' ? '编辑发往上游的 headers' : '场景执行时发往上游的真实 headers' }}</el-tag>
                    <button
                      v-if="interfacePageMode === 'debug'"
                      class="response-copy"
                      type="button"
                      title="格式化 JSON"
                      @click="prettifyDebugJsonDraft('headers')"
                    >
                      <span>格式化 JSON</span>
                    </button>
                  </div>
                </div>
                <template v-if="interfacePageMode === 'debug'">
                  <el-input
                    v-model="debugRequestHeadersText"
                    type="textarea"
                    :autosize="{ minRows: 14, maxRows: 28 }"
                    class="debug-json-editor"
                    spellcheck="false"
                    placeholder="{ }"
                  />
                </template>
                <template v-else-if="getScenarioStepActualRequests(selectedInterfaceStep).length">
                  <div
                    v-for="(req, idx) in getScenarioStepActualRequests(selectedInterfaceStep)"
                    :key="`actual-headers-${selectedInterfaceStep.key}-${idx}`"
                    class="actual-request-item"
                  >
                    <div class="actual-request-meta">
                      <el-tag
                        v-if="getScenarioStepActualRequests(selectedInterfaceStep).length > 1"
                        size="small"
                        effect="plain"
                      >#{{ idx + 1 }}</el-tag>
                      <code class="actual-request-method">{{ req.method || 'POST' }}</code>
                      <span class="actual-request-url">{{ req.url || '-' }}</span>
                    </div>
                    <pre>{{ req.headers ? JSON.stringify(req.headers, null, 2) : '(无 headers)' }}</pre>
                  </div>
                </template>
                <div v-else class="response-empty">执行该步骤后可在这里查看真正发往上游的请求头。</div>
              </section>

              <section v-else-if="stepFocusTab === 'actualQuery'" class="step-editor-panel response-block">
                <div class="response-block-head">
                  <strong>Query</strong>
                  <div class="response-block-actions">
                    <el-tag size="small" effect="plain">发送时会拼接到实际上游 URL</el-tag>
                    <button
                      class="response-copy"
                      type="button"
                      title="格式化 JSON"
                      @click="prettifyDebugJsonDraft('query')"
                    >
                      <span>格式化 JSON</span>
                    </button>
                  </div>
                </div>
                <el-input
                  v-model="debugRequestQueryText"
                  type="textarea"
                  :autosize="{ minRows: 10, maxRows: 22 }"
                  class="debug-json-editor"
                  spellcheck="false"
                  placeholder="{ }"
                />
              </section>

              <section v-else-if="stepFocusTab === 'actualResponse'" class="step-editor-panel response-block">
                <div class="response-block-head">
                  <strong>实际响应体</strong>
                  <el-tag size="small" effect="plain">上游返回的真实 body</el-tag>
                </div>
                <template v-if="getScenarioStepActualResponses(selectedInterfaceStep).length">
                  <div
                    v-for="(resp, idx) in getScenarioStepActualResponses(selectedInterfaceStep)"
                    :key="`actual-response-${selectedInterfaceStep.key}-${idx}`"
                    class="actual-request-item"
                  >
                    <div class="actual-request-meta">
                      <el-tag
                        v-if="getScenarioStepActualResponses(selectedInterfaceStep).length > 1"
                        size="small"
                        effect="plain"
                      >#{{ idx + 1 }}</el-tag>
                      <code class="actual-request-method">{{ resp.status_code || 'HTTP' }}</code>
                      <span class="actual-request-url">response body</span>
                    </div>
                    <pre>{{ resp.body == null ? '(无 body)' : (typeof resp.body === 'string' ? resp.body : JSON.stringify(resp.body, null, 2)) }}</pre>
                  </div>
                </template>
                <div v-else class="response-empty">执行该步骤后可在这里查看真正的上游响应体。</div>
              </section>

              <section v-else-if="stepFocusTab === 'actualResponseHeaders'" class="step-editor-panel response-block">
                <div class="response-block-head">
                  <strong>实际响应头</strong>
                  <el-tag size="small" effect="plain">上游返回的真实 headers</el-tag>
                </div>
                <template v-if="getScenarioStepActualResponses(selectedInterfaceStep).length">
                  <div
                    v-for="(resp, idx) in getScenarioStepActualResponses(selectedInterfaceStep)"
                    :key="`actual-response-headers-${selectedInterfaceStep.key}-${idx}`"
                    class="actual-request-item"
                  >
                    <div class="actual-request-meta">
                      <el-tag
                        v-if="getScenarioStepActualResponses(selectedInterfaceStep).length > 1"
                        size="small"
                        effect="plain"
                      >#{{ idx + 1 }}</el-tag>
                      <code class="actual-request-method">{{ resp.status_code || 'HTTP' }}</code>
                      <span class="actual-request-url">response headers</span>
                    </div>
                    <pre>{{ resp.headers ? JSON.stringify(resp.headers, null, 2) : '(无 headers)' }}</pre>
                  </div>
                </template>
                <div v-else class="response-empty">执行该步骤后可在这里查看真正的上游响应头。</div>
              </section>

              <section v-else-if="stepFocusTab === 'logic'" class="step-editor-panel response-block">
                <div class="response-block-head">
                  <strong>底层逻辑</strong>
                  <el-tag size="small" effect="plain">语言：{{ getScenarioStepLogic(selectedInterfaceStep)?.language || 'Python' }}</el-tag>
                </div>
                <div
                  v-if="scenarioStepSourceLoading[getScenarioStepSourceEndpoint(selectedInterfaceStep)]"
                  class="response-empty"
                >正在读取后端 Python 源码...</div>
                <div
                  v-else-if="scenarioStepSourceErrors[getScenarioStepSourceEndpoint(selectedInterfaceStep)]"
                  class="response-empty"
                >{{ scenarioStepSourceErrors[getScenarioStepSourceEndpoint(selectedInterfaceStep)] }}</div>
                <template v-else-if="getScenarioStepLogic(selectedInterfaceStep)?.blocks?.length">
                  <div
                    v-for="(block, idx) in getScenarioStepLogic(selectedInterfaceStep).blocks"
                    :key="`step-source-${selectedInterfaceStep.key}-${idx}`"
                    class="scenario-source-card"
                  >
                    <div class="scenario-source-meta">
                      <strong>{{ block.title }}</strong>
                      <span>{{ block.file }}:{{ block.start_line }}</span>
                      <code>{{ block.function }}</code>
                    </div>
                    <pre>{{ block.source }}</pre>
                  </div>
                </template>
                <div v-else class="response-empty">这个步骤没有匹配到后端路由源码。</div>
              </section>
            </section>
          </template>

          <section v-else-if="interfacePageMode === 'report'" class="scenario-panel">
            <div class="scenario-panel-head">
              <strong>执行历史</strong>
              <span>本机持续保留服务端执行记录。</span>
            </div>
            <div v-if="scenarioExecutionHistory.length === 0" class="scenario-empty">暂无执行历史。</div>
            <div v-for="item in scenarioExecutionHistory" :key="item.id" class="scenario-history-row">
              <el-tag :type="item.status === '完成' ? 'success' : item.status === '未执行' ? 'warning' : 'danger'" effect="plain">{{ item.status }}</el-tag>
              <strong>{{ item.scenario }}</strong>
              <span>{{ item.env }}</span>
              <span>{{ item.at }}</span>
              <span>成功 {{ item.success }} / 跳过 {{ item.skipped }} / 失败 {{ item.failed }}</span>
              <code>{{ item.duration }}</code>
              <el-button size="small" plain @click="openScenarioHistoryDetail(item)">详情</el-button>
            </div>
          </section>
        </main>
      </div>

      <el-dialog v-model="scenarioMetaEditVisible" title="编辑场景信息" width="520px" append-to-body>
        <el-form label-position="top">
          <el-form-item label="场景名称">
            <el-input v-model="scenarioMetaEditForm.name" placeholder="场景显示名" maxlength="120" show-word-limit />
          </el-form-item>
          <el-form-item label="场景描述">
            <el-input
              v-model="scenarioMetaEditForm.description"
              type="textarea"
              :rows="4"
              placeholder="场景说明，例如：完整 FP USD 500K 接口自动化场景"
              maxlength="600"
              show-word-limit
            />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="scenarioMetaEditVisible = false">取消</el-button>
          <el-button type="primary" :loading="scenarioMetaEditSaving" @click="saveScenarioMetaEditor">保存</el-button>
        </template>
      </el-dialog>

      <el-dialog v-model="scenarioStepMetaEditVisible" title="编辑步骤" width="520px" append-to-body>
        <el-form label-position="top">
          <el-form-item label="步骤名称">
            <el-input v-model="scenarioStepMetaEditForm.title" placeholder="步骤显示名" maxlength="120" show-word-limit />
          </el-form-item>
          <el-form-item label="步骤描述">
            <el-input
              v-model="scenarioStepMetaEditForm.description"
              type="textarea"
              :rows="4"
              placeholder="步骤说明，仅影响前端展示"
              maxlength="600"
              show-word-limit
            />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button
            plain
            :loading="scenarioStepMetaEditDeleting"
            @click="resetScenarioStepMetaEditor"
          >恢复默认</el-button>
          <el-button @click="scenarioStepMetaEditVisible = false">取消</el-button>
          <el-button type="primary" :loading="scenarioStepMetaEditSaving" @click="saveScenarioStepMetaEditor">保存</el-button>
        </template>
      </el-dialog>

      <el-dialog v-model="scenarioAddStepVisible" title="在下一步添加步骤" width="520px" append-to-body>
        <el-form label-position="top">
          <el-form-item label="复制哪个步骤">
            <el-select v-model="scenarioAddStepForm.sourceStepKey" style="width: 100%">
              <el-option
                v-for="step in (interfaceScenarios.find((item) => item.key === scenarioAddStepForm.scenarioKey)?.steps || [])"
                :key="`add-source-${step.key}`"
                :label="step.title"
                :value="step.key"
              />
            </el-select>
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="scenarioAddStepVisible = false">取消</el-button>
          <el-button type="primary" @click="addScenarioStepAfter">添加到草稿</el-button>
        </template>
      </el-dialog>
    </section>

    <section v-else-if="currentView === 'aiUi'" class="tool-page-view ai-ui-view">
      <header class="tool-page-head ai-ui-page-head">
        <div class="head-copy">
          <span class="eyebrow"><span class="eyebrow-dot"></span>Midscene.js</span>
          <h2>AI UI 自动化</h2>
          <p>用自然语言描述页面动作和视觉断言，独立执行浏览器 UI 测试。</p>
        </div>
        <div class="ai-ui-head-actions">
          <div class="ai-ui-page-switch" role="tablist" aria-label="AI UI 页面切换">
            <button
              v-for="mode in aiUiPageModes"
              :key="mode.key"
              type="button"
              role="tab"
              :aria-selected="aiUiPageMode === mode.key"
              :class="{ active: aiUiPageMode === mode.key }"
              @click="switchAiUiPageMode(mode.key)"
            >{{ mode.label }}</button>
          </div>
          <el-tag :type="aiUiRuntime?.dependencies && aiUiRuntime?.configured ? 'success' : 'warning'" effect="plain">
            {{ aiUiRuntime?.dependencies && aiUiRuntime?.configured ? '运行环境就绪' : '需要配置运行环境' }}
          </el-tag>
          <el-button plain :icon="Refresh" :loading="aiUiLoading" @click="refreshAiUiPage">刷新</el-button>
          <el-button plain @click="backToConsole">返回控制台</el-button>
        </div>
      </header>

      <div v-if="aiUiError" class="ai-ui-error">{{ aiUiError }}</div>
      <template v-if="aiUiPageMode === 'cases'">
      <div class="ai-ui-layout">
        <aside class="ai-ui-case-list surface-card">
          <div class="ai-ui-section-head">
            <div><strong>用例</strong><span>{{ aiUiCases.length }} 条</span></div>
            <el-button type="primary" plain :icon="Plus" @click="resetAiUiForm">新建</el-button>
          </div>
          <div v-if="!aiUiCases.length" class="ai-ui-empty">还没有 AI UI 用例，先创建一个页面冒烟用例。</div>
          <button
            v-for="item in aiUiCases"
            :key="item.id"
            type="button"
            class="ai-ui-case-item"
            :class="{ active: item.id === aiUiSelectedCaseId }"
            @click="editAiUiCase(item)"
          >
            <strong>{{ item.name }}</strong>
            <small>{{ item.url }}</small>
            <div class="ai-ui-case-meta">
              <el-tag size="small" effect="plain">{{ aiUiEnvironmentLabel(item.environment || inferAiUiEnvironment(item.url)) }}</el-tag>
              <span>{{ item.updated_at || item.created_at }}</span>
            </div>
          </button>
        </aside>

        <main class="ai-ui-editor surface-card">
          <div class="ai-ui-section-head">
            <div>
              <strong>{{ aiUiForm.id ? '编辑 UI 用例' : '新建 UI 用例' }}</strong>
              <span>步骤使用 Midscene Gherkin：Given / When / Then / And</span>
            </div>
            <div class="ai-ui-editor-actions">
              <el-button
                type="success"
                plain
                :disabled="!aiUiForm.id || Boolean(aiUiActiveRunId)"
                @click="runAiUiCase()"
              >执行</el-button>
            </div>
          </div>
          <section class="ai-ui-generator">
            <div class="ai-ui-generator-head">
              <div>
                <strong>自然语言生成结构化用例</strong>
                <span>先描述场景，生成后可继续编辑，再保存执行。</span>
              </div>
              <el-button type="primary" plain :loading="aiUiGenerating" @click="generateAiUiStructuredCase">生成 YAML</el-button>
            </div>
            <el-input
              v-model="aiUiNaturalLanguage"
              type="textarea"
              :rows="3"
              placeholder="例如：UAT 手机号注册进入安全设置页，填写密码，选择第一个安全问题并输入 test，不要提交。"
            />
          </section>
          <el-form label-position="top" class="ai-ui-form">
            <el-form-item label="用例名称">
              <el-input v-model.trim="aiUiForm.name" maxlength="200" />
            </el-form-item>
            <el-form-item label="运行环境">
              <el-select
                v-model="aiUiForm.environment"
                aria-label="AI UI 运行环境"
                @change="handleAiUiEnvironmentChange"
              >
                <el-option
                  v-for="option in aiUiEnvironmentOptions"
                  :key="`ai-ui-env-${option.value}`"
                  :label="option.label"
                  :value="option.value"
                />
              </el-select>
              <span class="ai-ui-field-hint">选择环境后自动填充 OFFLINE_SIGNUP_URL_DICT 对应地址。</span>
            </el-form-item>
            <el-form-item label="目标 URL">
              <el-input
                v-model.trim="aiUiForm.url"
                :disabled="aiUiForm.environment !== 'custom'"
                placeholder="https://uat.example.com 或 http://127.0.0.1:8000"
              />
            </el-form-item>
            <el-form-item label="测试上下文">
              <el-input v-model="aiUiForm.context" type="textarea" :rows="3" placeholder="补充业务背景、页面规则和不应点击的区域。" />
            </el-form-item>
            <el-form-item label="自然语言步骤">
              <el-input v-model="aiUiForm.prompt" type="textarea" :rows="14" class="ai-ui-prompt-input" />
            </el-form-item>
            <div class="ai-ui-structured-grid">
              <el-form-item label="结构化 YAML（生成预览）">
                <el-input v-model="aiUiStructuredYaml" type="textarea" :rows="10" class="ai-ui-prompt-input" />
              </el-form-item>
              <el-form-item label="变量 JSON">
                <el-input v-model="aiUiVariablesText" type="textarea" :rows="10" class="ai-ui-prompt-input" />
              </el-form-item>
            </div>
            <div class="ai-ui-options">
              <el-form-item label="浏览器">
                <el-switch v-model="aiUiForm.headed" active-text="显示浏览器" inactive-text="无头执行" />
              </el-form-item>
              <el-form-item label="视口宽度">
                <el-input-number v-model="aiUiForm.viewport.width" :min="800" :max="2560" />
              </el-form-item>
              <el-form-item label="视口高度">
                <el-input-number v-model="aiUiForm.viewport.height" :min="600" :max="1600" />
              </el-form-item>
            </div>
          </el-form>
          <div class="ai-ui-footer-actions">
            <div class="ai-ui-footer-action-buttons">
              <el-button type="primary" plain :loading="aiUiSaving" @click="saveAiUiCaseRecord">保存用例</el-button>
              <el-button v-if="aiUiForm.id" type="danger" plain @click="removeAiUiCase(aiUiForm)">删除用例</el-button>
            </div>
            <span>执行结果会保留在右侧历史中，Midscene 会生成 HTML 报告。</span>
          </div>
        </main>
      </div>
      </template>

      <section v-else class="ai-ui-report-page surface-card">
        <div class="ai-ui-report-head">
          <div>
            <strong>执行历史</strong>
            <span>查看 AI UI 案例的最近执行状态与 Midscene 报告。</span>
          </div>
          <el-button plain :icon="Refresh" :loading="aiUiLoading" @click="refreshAiUiPage">刷新历史</el-button>
        </div>
        <div v-if="!aiUiRuns.length" class="ai-ui-empty">暂无执行历史，先到“案例”页保存并执行一个用例。</div>
        <div v-else class="ai-ui-report-list">
          <article v-for="run in aiUiRuns" :key="run.id" class="ai-ui-report-row">
            <div class="ai-ui-report-main">
              <div class="ai-ui-report-title">
                <strong>{{ run.case_name }}</strong>
                <el-tag
                  size="small"
                  effect="plain"
                  :type="run.status === 'passed' ? 'success' : run.status === 'failed' ? 'danger' : run.status === 'running' ? 'warning' : 'info'"
                >
                  {{ run.status === 'passed' ? '通过' : run.status === 'failed' ? '失败' : run.status === 'running' ? '执行中' : '已停止' }}
                </el-tag>
              </div>
              <div class="ai-ui-report-meta">
                <span>开始 {{ run.started_at || '-' }}</span>
                <span>结束 {{ run.finished_at || '-' }}</span>
                <span>环境 {{ aiUiEnvironmentLabel(run.environment) }}</span>
              </div>
              <pre v-if="run.error" class="ai-ui-run-error">{{ run.error }}</pre>
              <div v-if="run.result?.analysis" class="ai-ui-run-analysis">
                <strong>AI 结果解析</strong>
                <span>{{ run.result.analysis.summary }}</span>
                <span v-if="run.result.analysis.blocker">卡点：{{ run.result.analysis.blocker }}</span>
                <span v-if="run.result.analysis.suggestion">建议：{{ run.result.analysis.suggestion }}</span>
              </div>
            </div>
            <div class="ai-ui-report-actions">
              <el-button v-if="run.status === 'running'" size="small" type="warning" plain @click="stopAiUiCaseRun(run)">停止</el-button>
              <el-button
                v-if="run.result?.report_url"
                size="small"
                type="primary"
                plain
                @click="openAiUiReport(`${run.result.report_url}?username=${encodeURIComponent(authUser.username)}`)"
              >打开报告</el-button>
              <el-button
                v-if="run.result?.report_url"
                size="small"
                plain
                @click="openAiUiReport(`/api/ai-ui/runs/${encodeURIComponent(run.id)}/sop?username=${encodeURIComponent(authUser.username)}`)"
              >导出 SOP</el-button>
              <el-button size="small" plain @click="switchAiUiPageMode('cases')">查看案例</el-button>
            </div>
          </article>
        </div>
        <div class="ai-ui-runtime">
          <strong>运行环境</strong>
          <span>Node.js：{{ aiUiRuntime?.node ? '已找到' : '未找到' }}</span>
          <span>Midscene / Playwright：{{ aiUiRuntime?.dependencies ? '已安装' : '未安装' }}</span>
          <span>视觉模型：{{ aiUiRuntime?.configured ? '已配置' : '未配置' }}</span>
          <code v-if="aiUiRuntime && !aiUiRuntime.dependencies">{{ aiUiRuntime.install_command }}</code>
        </div>
      </section>
      <el-dialog v-model="aiUiRunConfirmVisible" title="执行前确认" width="520px" append-to-body>
        <div class="ai-ui-confirm">
          <p>即将执行用例：<strong>{{ aiUiPendingCase?.name || '-' }}</strong></p>
          <p>环境：<strong>{{ aiUiEnvironmentLabel(aiUiPendingCase?.environment) }}</strong></p>
          <p>目标地址：<code>{{ aiUiPendingCase?.url || '-' }}</code></p>
          <p>执行会启动独立 Chromium，并按当前 Gherkin 步骤操作页面。</p>
        </div>
        <template #footer>
          <el-button @click="aiUiRunConfirmVisible = false">取消</el-button>
          <el-button type="primary" @click="confirmAiUiRun">确认执行</el-button>
        </template>
      </el-dialog>
    </section>

    <section v-else-if="currentView === 'mockApi' && isAdmin" class="tool-page-view mock-api-view">
      <header class="tool-page-head">
        <div class="head-copy">
          <span class="eyebrow">
            <span class="eyebrow-dot"></span>
            Mock API
          </span>
          <h2>Mock 接口</h2>
          <p>集中维护 DS-CNY 的经营数据参数和企业信息模板，保存后会同步到接口测试的对应下拉框。</p>
        </div>
        <el-button plain :icon="Refresh" @click="openInterfaceTestView">返回接口测试</el-button>
      </header>

      <el-card shadow="never" class="surface-card mock-api-card">
        <div class="mock-api-endpoint">
          <div>
            <span class="mock-api-method">POST</span>
            <code>/api/mock/shop-performance-cny-boost</code>
          </div>
          <span class="mock-api-count">{{ shopPerformancePresets.length }} 条店铺记录</span>
        </div>
        <div class="mock-api-summary-record">
          <div>
            <strong>经营数据参数配置</strong>
            <span>已反显 {{ shopPerformancePresets.length }} 条店铺记录，可进入详情编辑内置配置或新增记录。</span>
          </div>
          <el-button type="primary" plain :icon="Edit" @click="openShopPerformanceManager">编辑配置</el-button>
        </div>
      </el-card>

      <el-card shadow="never" class="surface-card mock-api-card">
        <div class="mock-api-endpoint">
          <div class="mock-api-linked-endpoints">
            <span><span class="mock-api-method">POST</span><code>/api/mock/fp-business-profile</code></span>
            <span><span class="mock-api-method">POST</span><code>/api/mock/fp-director-info</code></span>
            <span><span class="mock-api-method">POST</span><code>/api/mock/fp-add-contact-information</code></span>
          </div>
          <span class="mock-api-count">{{ dowsureCnyCompanyTemplates.length }} 个公司模板</span>
        </div>
        <div class="mock-api-summary-record">
          <div>
            <strong>三接口公司模板配置</strong>
            <span>
              已配置 {{ dowsureCnyCompanyTemplates.length }} 条记录：{{ dowsureCnyCompanyTemplates.map((item) => item.name).join('、') }}
            </span>
          </div>
          <el-button type="primary" plain :icon="Edit" @click="openDowsureCompanyTemplateManager">编辑配置</el-button>
        </div>
      </el-card>

      <el-card shadow="never" class="surface-card mock-api-card">
        <div class="mock-api-endpoint">
          <div class="mock-api-linked-endpoints">
            <span><span class="mock-api-method">IMAGE</span><code>/api/mock/fp-business-profile</code></span>
            <span><span class="mock-api-method">IMAGE</span><code>/api/mock/fp-director-info</code></span>
          </div>
          <span class="mock-api-count">{{ companyImageTemplates.length }} 个图片配置</span>
        </div>
        <div class="mock-api-summary-record">
          <div>
            <strong>三接口公司图片配置</strong>
            <span>上传企业营业执照、法人身份证正面和反面，保存后同步到接口测试的图片下拉框。</span>
          </div>
          <el-button type="primary" plain :icon="Edit" @click="openCompanyImageManager">编辑配置</el-button>
        </div>
      </el-card>

      <el-dialog
        v-model="shopPerformanceManagerVisible"
        title="经营数据参数详情"
        width="min(920px, 92vw)"
        top="5vh"
        append-to-body
        class="mock-api-manager-dialog"
      >
        <div class="mock-api-dialog-toolbar">
          <span>已反显16条内置店铺记录；编辑后保存同名 SQL 覆盖，不修改则继续使用后端原配置。</span>
          <el-button type="primary" plain :icon="Plus" @click="startNewShopPerformancePreset">新增记录</el-button>
        </div>
        <div class="mock-api-preset-list">
          <div v-if="shopPerformancePresets.length" class="mock-api-preset-grid">
            <article v-for="preset in shopPerformancePresets" :key="`dialog-preset-${preset.name}`" class="mock-api-preset-item">
              <div>
                <strong>{{ preset.name }}</strong>
                <code>{{ preset.custom_sql || '使用后端内置经营数据配置' }}</code>
              </div>
              <div class="mock-api-preset-actions">
                <el-button link type="primary" @click="editShopPerformancePreset(preset)">编辑</el-button>
                <el-button
                  v-if="!preset.is_builtin || preset.custom_sql"
                  link
                  :type="preset.is_builtin ? 'warning' : 'danger'"
                  @click="deleteShopPerformancePreset(preset)"
                >
                  {{ preset.is_builtin ? '恢复内置' : '删除' }}
                </el-button>
              </div>
            </article>
          </div>
          <div v-else class="response-empty">暂无记录，请点击“新增记录”。</div>
        </div>
      </el-dialog>

      <el-dialog
        v-model="shopPerformanceEditorVisible"
        :title="editingShopPerformancePresetName ? `编辑店铺配置：${editingShopPerformancePresetName}` : '新增店铺配置'"
        width="min(860px, 92vw)"
        top="8vh"
        append-to-body
        class="mock-api-manager-dialog"
        @closed="resetShopPerformancePresetForm"
      >
        <div class="mock-api-form mock-api-dialog-editor">
          <div class="mock-api-form-head">
            <div>
              <h3>{{ editingShopPerformancePresetName ? `编辑：${editingShopPerformancePresetName}` : '新增经营数据参数' }}</h3>
              <p>保存后会同步到接口测试的“准入类型”下拉框；内置记录保存同名 SQL 后覆盖原配置。</p>
            </div>
          </div>
          <div class="mock-api-form-grid">
            <el-form-item label="参数名称">
              <el-input
                v-model.trim="shopPerformancePresetForm.name"
                :disabled="BUILTIN_SHOP_PERFORMANCE_NAME_SET.has(editingShopPerformancePresetName)"
                placeholder="例如：店铺20"
              />
            </el-form-item>
            <el-form-item label="自定义经营数据 SQL">
              <el-input
                v-model="shopPerformancePresetForm.custom_sql"
                type="textarea"
                :autosize="{ minRows: 8, maxRows: 16 }"
                placeholder="填写 UPDATE dpu_3pl_shop_performance ... WHERE amazon_3pl_offer_id = '${platform_offer_id}'；不修改时继续使用后端内置配置"
              />
              <p v-if="shopPerformancePresetError" class="mock-api-validation-error">{{ shopPerformancePresetError }}</p>
            </el-form-item>
          </div>
          <div class="scenario-step-config-actions">
            <el-button type="primary" :loading="shopPerformancePresetSaving" @click="saveShopPerformancePreset">保存记录</el-button>
            <el-button @click="shopPerformanceEditorVisible = false">取消</el-button>
          </div>
        </div>
      </el-dialog>

      <el-dialog
        v-model="dowsureCompanyTemplateManagerVisible"
        title="三接口公司模板详情"
        width="min(1180px, 94vw)"
        top="3vh"
        append-to-body
        class="mock-api-manager-dialog"
      >
        <div class="mock-api-dialog-toolbar">
          <span>每条记录包含企业、法人和联系人三份模板。</span>
          <el-button type="primary" plain :icon="Plus" @click="startNewDowsureCompanyTemplate">新增记录</el-button>
        </div>
        <div class="mock-api-preset-list">
          <div class="mock-api-preset-grid">
            <article v-for="item in dowsureCnyCompanyTemplates" :key="`dialog-company-${item.name}`" class="mock-api-preset-item">
              <div>
                <strong>{{ item.name }}</strong>
                <code>{{ item.template.cnName }} · 法人 {{ item.directorTemplate.nameCn }} · 联系人 {{ item.contactTemplate.fullChineseName }}/{{ item.contactTemplate.mobileNumber }}</code>
              </div>
              <div class="mock-api-preset-actions">
                <el-button link type="primary" @click="editDowsureCompanyTemplate(item)">编辑</el-button>
                <el-button
                  v-if="!BUILTIN_DOWSURE_CNY_COMPANY_TEMPLATE_NAMES.has(item.name)"
                  link
                  type="danger"
                  @click="deleteDowsureCompanyTemplate(item)"
                >
                  删除
                </el-button>
              </div>
            </article>
          </div>
        </div>
        <div class="mock-api-form mock-api-dialog-editor">
          <div class="mock-api-form-head">
            <div>
              <h3>{{ editingDowsureCompanyTemplateName ? `编辑：${editingDowsureCompanyTemplateName}` : '新增三接口公司模板' }}</h3>
              <p>三份模板必须同时完整配置并一次保存。</p>
            </div>
            <el-button v-if="editingDowsureCompanyTemplateName" plain @click="startNewDowsureCompanyTemplate">取消编辑</el-button>
          </div>
          <el-form class="mock-api-form-grid dowsure-template-form-grid" label-position="left" label-width="250px">
            <el-form-item label="参数名称">
              <el-input v-model.trim="dowsureCompanyTemplateForm.name" placeholder="例如：广州测试科技有限公司" />
            </el-form-item>
            <el-form-item label="/api/mock/fp-business-profile">
              <el-input v-model="dowsureCompanyTemplateForm.templateText" type="textarea" :autosize="{ minRows: 8, maxRows: 16 }" />
            </el-form-item>
            <el-form-item label="/api/mock/fp-director-info">
              <el-input v-model="dowsureCompanyTemplateForm.directorTemplateText" type="textarea" :autosize="{ minRows: 12, maxRows: 22 }" />
            </el-form-item>
            <el-form-item label="/api/mock/fp-add-contact-information">
              <el-input v-model="dowsureCompanyTemplateForm.contactTemplateText" type="textarea" :autosize="{ minRows: 7, maxRows: 14 }" />
              <p v-if="dowsureCompanyTemplateError" class="mock-api-validation-error">{{ dowsureCompanyTemplateError }}</p>
            </el-form-item>
          </el-form>
          <div class="scenario-step-config-actions">
            <el-button type="primary" :loading="dowsureCompanyTemplateSaving" @click="saveDowsureCompanyTemplate">同步保存三接口记录</el-button>
            <span class="scenario-step-config-hint">模板 id、营业执照和身份证文件地址由 Mock 后端自动补充。</span>
          </div>
        </div>
      </el-dialog>

      <el-dialog
        v-model="companyImageManagerVisible"
        title="三接口公司图片配置"
        width="min(900px, 94vw)"
        top="5vh"
        append-to-body
        class="mock-api-manager-dialog"
        @closed="resetCompanyImageForm"
      >
        <div class="mock-api-dialog-toolbar">
          <span>图片在执行对应接口时上传到当前环境的 dpu-file 网关。</span>
          <el-button type="primary" plain :icon="Plus" @click="resetCompanyImageForm">新增图片</el-button>
        </div>
        <div class="mock-api-preset-list">
          <div class="mock-api-preset-grid">
            <article v-for="item in companyImageTemplates" :key="`company-image-${item.id}`" class="mock-api-preset-item">
              <div>
                <strong>{{ item.name }}</strong>
                <code>{{ companyImageTypeLabel(item.image_type) }} · {{ item.filename }}<template v-if="item.file_size"> · {{ Math.ceil(item.file_size / 1024) }}KB</template></code>
              </div>
              <div class="mock-api-preset-actions">
                <el-tag v-if="item.is_builtin" size="small" effect="plain">内置</el-tag>
                <el-button link type="primary" @click="editCompanyImageTemplate(item)">编辑</el-button>
                <template v-if="!item.is_builtin">
                  <el-button link type="danger" @click="removeCompanyImageTemplate(item)">删除</el-button>
                </template>
              </div>
            </article>
          </div>
        </div>
        <div class="mock-api-form mock-api-dialog-editor">
          <div class="mock-api-form-head">
            <div>
              <h3>
                {{ companyImageForm.id
                  ? `编辑：${companyImageForm.name}`
                  : (companyImageForm.is_builtin ? `编辑内置图片：${companyImageForm.name}` : '新增公司图片') }}
              </h3>
              <p>支持 PNG、JPEG、WEBP，单张不超过 10MB。</p>
            </div>
            <el-button v-if="companyImageForm.id || companyImageForm.is_builtin" plain @click="resetCompanyImageForm">取消编辑</el-button>
          </div>
          <el-form class="mock-api-form-grid" label-position="top">
            <el-form-item label="图片名称">
              <el-input
                v-model.trim="companyImageForm.name"
                :disabled="companyImageForm.is_builtin"
                placeholder="例如：测广州市昆袄祝山脸从股份有限公司营业执照"
              />
            </el-form-item>
            <el-form-item label="图片用途">
              <el-select v-model="companyImageForm.image_type" :disabled="companyImageForm.is_builtin">
                <el-option label="企业营业执照" value="business_license" />
                <el-option label="法人身份证正面" value="director_id_front" />
                <el-option label="法人身份证反面" value="director_id_back" />
              </el-select>
            </el-form-item>
            <el-form-item :label="companyImageForm.id ? '替换图片（可选）' : (companyImageForm.is_builtin ? '替换内置图片' : '上传图片')">
              <input
                :key="companyImageFileInputKey"
                class="company-image-file-input"
                type="file"
                accept="image/png,image/jpeg,image/webp"
                @change="handleCompanyImageFileChange"
              />
              <span v-if="companyImageFile" class="scenario-step-config-hint">已选择：{{ companyImageFile.name }}</span>
              <span v-else-if="companyImageForm.filename" class="scenario-step-config-hint">当前文件：{{ companyImageForm.filename }}</span>
              <div v-if="companyImagePreviewUrl" class="company-image-preview">
                <img :src="companyImagePreviewUrl" :alt="companyImageForm.name || '公司图片预览'" />
              </div>
            </el-form-item>
            <p v-if="companyImageError" class="mock-api-validation-error">{{ companyImageError }}</p>
          </el-form>
          <div class="scenario-step-config-actions">
            <el-button type="primary" :loading="companyImageSaving" @click="saveCompanyImageRecord">
              {{ companyImageForm.id || companyImageForm.is_builtin ? '保存修改' : '上传并保存' }}
            </el-button>
            <el-button @click="resetCompanyImageForm">清空</el-button>
          </div>
        </div>
      </el-dialog>
    </section>

    <section v-else-if="currentView === 'activity'" class="tool-page-view activity-page-view">
      <header class="tool-page-head">
        <div class="head-copy">
          <span class="eyebrow">
            <span class="eyebrow-dot"></span>
            Usage Log
          </span>
          <h2>使用日志</h2>
          <p>{{ isAdmin ? '管理员可查看所有人的历史操作记录。' : '当前账号的历史 mock 操作记录，可按手机号或 Session ID 过滤。' }}</p>
        </div>
        <el-button :icon="Refresh" plain :loading="auditLoading" @click="refreshAuditOperations">刷新</el-button>
      </header>

      <el-card shadow="never" class="surface-card activity-page-card">
        <div class="usage-log-stats">
          <article v-for="stat in auditStats" :key="stat.label" class="usage-log-stat">
            <span>{{ stat.label }}</span>
            <strong>{{ stat.value }}</strong>
            <small>{{ stat.hint }}</small>
          </article>
        </div>

        <el-form class="audit-query-form" :inline="true" @submit.prevent="refreshAuditOperations">
          <el-form-item label="手机号">
            <el-input
              v-model.trim="auditQuery.phone_number"
              placeholder="8 位或 11 位手机号"
              clearable
              @keydown.enter.prevent="refreshAuditOperations"
            />
          </el-form-item>
          <el-form-item label="Session ID">
            <el-input
              v-model.trim="auditQuery.session_id"
              placeholder="UUID"
              clearable
              @keydown.enter.prevent="refreshAuditOperations"
            />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :icon="Search" :loading="auditLoading" @click="refreshAuditOperations">
              查询
            </el-button>
            <el-button :icon="Refresh" plain @click="resetAuditQuery">重置</el-button>
          </el-form-item>
        </el-form>

        <p v-if="auditError" class="login-error">{{ auditError }}</p>

        <div class="activity-list">
          <div v-if="!auditLoading && auditOperations.length === 0" class="session-empty">
            <span class="session-empty__icon">
              <el-icon><Clock /></el-icon>
            </span>
            <p class="session-empty__title">还没有操作记录</p>
            <p class="session-empty__hint">登录、连接 session、执行 mock 等操作后会在这里出现。</p>
          </div>
          <div v-for="item in auditOperations" :key="item.id" class="activity-item">
            <div class="activity-summary-row">
              <span
                class="activity-status-line"
                :class="{
                  success: item.success === true,
                  failed: item.success === false,
                }"
              ></span>
              <div class="activity-summary-main">
                <div class="activity-head">
                  <div class="activity-title-group">
                    <strong>{{ item.operation_name || 'operation' }}</strong>
                    <el-tag v-if="item.success === false" size="small" type="danger" effect="plain">失败</el-tag>
                    <el-tag v-else-if="item.success === true" size="small" type="success" effect="plain">成功</el-tag>
                    <el-tag v-else size="small" type="info" effect="plain">未知</el-tag>
                  </div>
                  <time>{{ item.created_at }}</time>
                </div>
                <div class="audit-meta">
                  <span v-if="isAdmin"><b>用户</b>{{ item.username || '-' }}</span>
                  <span><b>手机号</b>{{ item.phone_number || '-' }}</span>
                  <span><b>Session</b>{{ item.session_id || '-' }}</span>
                  <span><b>环境</b>{{ item.env || '-' }}</span>
                  <span><b>Merchant</b>{{ item.merchant_id || '-' }}</span>
                </div>
              </div>
              <el-button
                class="activity-detail-toggle"
                size="small"
                plain
                :icon="isAuditOperationExpanded(item.id) ? ArrowDown : ArrowRight"
                @click="toggleAuditOperationDetail(item.id)"
              >
                {{ isAuditOperationExpanded(item.id) ? '收起详情' : '详情' }}
              </el-button>
            </div>
            <div v-if="isAuditOperationExpanded(item.id)" class="activity-detail-panel">
              <section>
                <strong>Request</strong>
                <pre>{{ formatJsonBlock(item.request_payload) }}</pre>
              </section>
              <section>
                <strong>Response</strong>
                <pre>{{ formatJsonBlock(item.response_payload) }}</pre>
              </section>
            </div>
          </div>
        </div>
      </el-card>

    </section>

    <section v-else-if="currentView === 'environmentMonitor'" class="tool-page-view environment-monitor-view">
      <header class="tool-page-head">
        <div class="head-copy">
          <span class="eyebrow">
            <span class="eyebrow-dot"></span>
            Environment Monitor
          </span>
          <h2>环境监测</h2>
          <p>网关检测 / 请求测试健康度。</p>
        </div>
        <div class="environment-monitor-actions">
          <el-tag type="info" effect="plain">自动刷新：{{ environmentMonitorRefreshSeconds }}s</el-tag>
          <el-button :icon="Refresh" plain :loading="environmentMonitorLoading" @click="refreshEnvironmentMonitor(true)">刷新</el-button>
        </div>
      </header>

      <el-card shadow="never" class="surface-card environment-monitor-card">
        <template #header>
          <div class="card-head environment-monitor-head">
            <div class="head-copy">
              <h3>环境监测</h3>
              <p>网关检测 / 请求测试健康度。</p>
            </div>
            <div class="environment-monitor-actions">
              <span v-if="environmentMonitor.checked_at" class="environment-monitor-time">{{ environmentMonitor.checked_at }}</span>
              <el-tag type="info" effect="plain">自动刷新：{{ environmentMonitorRefreshSeconds }}s</el-tag>
              <el-button :icon="Refresh" plain :loading="environmentMonitorLoading" @click="refreshEnvironmentMonitor(true)">刷新</el-button>
            </div>
          </div>
        </template>

        <p v-if="environmentMonitorError" class="login-error">{{ environmentMonitorError }}</p>
        <div class="environment-monitor-grid">
          <article
            v-for="item in environmentMonitorItems"
            :key="item.env"
            class="environment-card"
            :class="environmentCardState(item)"
          >
            <div class="environment-card-head">
              <div class="environment-badge">
                <strong>{{ item.env === 'preprod' ? 'PPROD' : item.label }}</strong>
              </div>
              <div>
                <h4>{{ item.display_env || item.env }}</h4>
                <p>{{ item.base_url }}</p>
              </div>
              <el-tag
                class="environment-status-tag"
                :type="availabilityTagType(item.availability)"
                effect="light"
              >
                {{ availabilityLabel(item.availability) }}
              </el-tag>
            </div>
            <section class="environment-check-block channel-check-block">
              <div class="environment-metrics">
                <div>
                  <span>请求延迟</span>
                  <strong>{{ item.latency_ms ?? '-' }}<small>ms</small></strong>
                </div>
                <div>
                  <span>端点 PING</span>
                  <strong>{{ item.endpoint_ping_ms ?? '-' }}<small>ms</small></strong>
                </div>
              </div>
              <div class="environment-availability" :class="availabilityState(item.availability)">
                <span>网关可用性</span>
                <strong>{{ item.availability ?? '--' }}<small v-if="item.availability !== null && item.availability !== undefined">%</small></strong>
              </div>
              <div class="environment-history" :class="{ empty: !item.history?.length }" aria-label="最近请求记录">
                <template v-if="item.history?.length">
                  <i
                    v-for="(status, index) in item.history"
                    :key="`${item.env}-gateway-${index}`"
                    :class="status"
                  ></i>
                </template>
                <span v-else>暂无历史请求样本</span>
              </div>
              <div class="environment-card-foot">
                <span>最近 {{ item.sample_count || 0 }}/60 次请求</span>
                <span>实时日志样本</span>
              </div>
            </section>

            <section class="environment-check-block channel-check-block">
              <div class="environment-channel-head">
                <div>
                  <span>渠道健康度</span>
                </div>
                <el-tag
                  size="small"
                  :type="availabilityTagType(item.channel_availability)"
                  effect="light"
                >
                  {{ availabilityLabel(item.channel_availability) }}
                </el-tag>
              </div>
              <div class="environment-availability" :class="availabilityState(item.channel_availability)">
                <span>自动测试可用性</span>
                <strong>{{ item.channel_availability ?? '--' }}<small v-if="item.channel_availability !== null && item.channel_availability !== undefined">%</small></strong>
              </div>
              <div class="environment-history channel" :class="{ empty: !item.channel_history?.length }" aria-label="最近 send-sms 自动测试记录">
                <template v-if="item.channel_history?.length">
                  <i
                    v-for="(status, index) in item.channel_history"
                    :key="`${item.env}-channel-${index}`"
                    :class="status"
                  ></i>
                </template>
                <span v-else>等待半小时自动测试样本</span>
              </div>
              <div class="environment-card-foot">
                <span>最近 {{ item.channel_sample_count || 0 }}/60 次测试</span>
                <span>{{ item.channel_checked_at || '启动后自动执行' }}</span>
              </div>
            </section>
          </article>
        </div>
      </el-card>

    </section>

    <section v-else-if="currentView === 'about'" class="tool-page-view about-page-view">
      <div class="log-system-head">
        <div>
          <p class="eyebrow">About</p>
          <h2>关于我们</h2>
          <p>DPU Mock API 操作台用于统一管理测试账号、会话上下文、DPU 状态模拟、日志检索和问题协作。</p>
        </div>
        <el-button plain :icon="Refresh" @click="backToConsole">返回控制台</el-button>
      </div>

      <el-card shadow="never" class="surface-card tool-page-card help-page-card">
        <div class="help-section help-callout">
          <h3>工具定位</h3>
          <p>DPU Mock API 操作台是面向 DPU 测试、联调和回归验证的内部控制台。它把账号注册、session 连接、workflow webhook 模拟、实时日志、历史日志检索和问题交接集中在同一个页面，减少脚本切换、手工拼请求和环境信息遗漏。</p>
          <p>页面设计以执行效率和可追溯性为优先：所有关键操作都围绕当前环境、手机号、session、merchant 和接口结果展开，便于测试人员、研发和支持同学在同一上下文中定位问题。</p>
        </div>
        <div class="help-section">
          <h3>适用场景</h3>
          <ol>
            <li>新建 SIT、UAT、REG 等环境的测试账号，并快速进入可执行 mock 的状态。</li>
            <li>在指定 session 下模拟核保、审批、PSP、电子签、放款、还款、多店铺等 DPU 业务状态。</li>
            <li>联调或回归时复现某个 webhook 节点，确认请求 URL、请求体、响应体和业务错误。</li>
            <li>排查“页面显示成功但业务状态未推进”“接口 200 但业务失败”“session 失效或环境选错”等问题。</li>
            <li>将问题现场沉淀到“联系我们”，让管理员或后续处理人能基于相同上下文继续跟进。</li>
          </ol>
        </div>
        <div class="help-section">
          <h3>标准使用流程</h3>
          <ol>
            <li>在“连接与注册”选择目标环境，输入手机号连接已有 session，或按 Journey、币种、资方代码注册新账号。</li>
            <li>确认右侧“当前会话”中的环境、手机号、Merchant 等信息，避免跨环境或跨账号误操作。</li>
            <li>进入“Mock 操作面板”，选择需要推进的业务节点，填写金额、状态、失败原因或 state 等参数。</li>
            <li>执行后查看当前步骤下方的返回结果，同时进入“使用日志”确认请求已被记录。</li>
            <li>如果结果异常，可先在“使用日志”查看操作请求和响应；需要确认环境可用性时进入“环境监测”。</li>
            <li>需要交接时，在“联系我们”记录现象、预期、复现步骤、手机号、session、关键日志和截图线索。</li>
          </ol>
        </div>
        <div class="help-section">
          <h3>核心模块能力</h3>
          <dl>
            <dt>连接与注册</dt>
            <dd>用于创建或连接测试账号上下文。注册支持 Journey、币种、资方代码和线上/线下模式选择；连接成功后会建立 session，后续 mock 操作都会绑定这个上下文。</dd>
            <dt>Mock 操作面板</dt>
            <dd>集中触发 DPU 关键业务节点，包括 SP/3PL 关联、核保、审批、PSP started/completed、电子签、放款、还款、系统事件和 Abandon。每个操作保留独立参数区，降低误填风险。</dd>
            <dt>使用日志</dt>
            <dd>用于追溯账号操作记录，重点查看每次 mock 操作的请求参数、响应结果、执行账号、手机号、session 和 merchant。</dd>
            <dt>环境监测</dt>
            <dd>用于查看 dev、reg、sit、uat、preprod 网关可用性、响应延迟和近期状态条，辅助判断是否为环境波动。</dd>
            <dt>AI 助手</dt>
            <dd>用于辅助分析当前 session、日志和 mock 结果，也可以帮助整理 SQL、接口现象和排查思路。AI 输出只作为诊断辅助，关键业务结论仍应以接口返回、日志和数据库状态为准。</dd>
            <dt>联系我们</dt>
            <dd>用于异步交接问题现场。建议写清楚环境、手机号、session、已执行步骤、预期状态、实际状态、错误日志和截图信息，方便管理员或后续处理人快速接手。</dd>
            <dt>管理员登录</dt>
            <dd>管理员入口已调整为“回复问题”，用于集中查看和回复已提交的问题，适合团队内部维护待处理事项、补充处理结论和保留协作记录。</dd>
          </dl>
        </div>
        <div class="help-section">
          <h3>数据与安全边界</h3>
          <dl>
            <dt>环境隔离</dt>
            <dd>执行前必须确认当前环境。SIT、UAT、REG、DEV、PREPROD 的数据和网关地址不同，跨环境使用手机号或 session 会导致误判。</dd>
            <dt>测试数据</dt>
            <dd>本工具面向测试和联调用例，不应输入真实客户敏感信息。需要生产或迁移相关操作时，应按专项流程和授权要求执行。</dd>
            <dt>结果判定</dt>
            <dd>按钮执行成功只代表接口调用完成，不等同于完整业务链路成功。关键节点应结合返回体、使用日志和必要的数据库状态共同确认。</dd>
            <dt>审计线索</dt>
            <dd>使用日志用于辅助追溯，但不替代正式测试报告。重要验证结论仍应沉淀到 MeterSphere、缺陷单或版本验证记录中。</dd>
          </dl>
        </div>
        <div class="help-section">
          <h3>协作建议</h3>
          <dl>
            <dt>复现问题</dt>
            <dd>先固定环境、手机号、session 和执行时间窗口，再描述失败节点。不要只写“失败了”，应说明停在哪一步、期望推进到哪一步。</dd>
            <dt>提交信息</dt>
            <dd>优先提供可直接排查的信息：环境、手机号、session_id、merchant_id、接口名称、请求时间、traceId、关键响应体和截图。</dd>
            <dt>处理结论</dt>
            <dd>管理员回复时建议包含原因判断、已采取动作、是否需要重试、是否需要研发介入，以及后续验证标准。</dd>
          </dl>
        </div>
      </el-card>
    </section>

    <section v-else-if="currentView === 'contact'" class="tool-page-view contact-page-view">
      <div class="log-system-head">
        <div>
          <p class="eyebrow">Ask Us</p>
          <h2>联系我们</h2>
          <p>把问题现场、期望结果和关键信息整理清楚，管理员会统一处理。</p>
        </div>
        <el-button plain :icon="Refresh" @click="backToConsole">返回控制台</el-button>
      </div>

      <div class="contact-overview-grid">
        <div class="contact-stat-card">
          <span>问题总数</span>
          <strong>{{ contactIssues.length }}</strong>
          <p>当前浏览器已记录的问题总量</p>
        </div>
        <div class="contact-stat-card">
          <span>待回复</span>
          <strong>{{ pendingContactIssuesCount }}</strong>
          <p>需要管理员继续处理的问题</p>
        </div>
        <div class="contact-stat-card">
          <span>已回复</span>
          <strong>{{ repliedContactIssuesCount }}</strong>
          <p>已完成答复的问题</p>
        </div>
      </div>

      <div class="contact-page-stack">
        <el-card shadow="never" class="surface-card contact-admin-card">
          <template #header>
            <div class="card-head">
              <div class="head-copy">
                <h3>提交问题</h3>
                <p>建议按“现象 + 预期 + 复现步骤 + 关键上下文”来写。</p>
              </div>
            </div>
          </template>

          <div class="contact-context">
            <div><span>环境</span><strong>{{ sessionSummary?.env || connectionForm.env }}</strong></div>
            <div><span>手机号</span><strong>{{ sessionSummary?.phone_number || connectionForm.phone_number || '-' }}</strong></div>
            <div><span>Session</span><strong>{{ activeSessionId || '-' }}</strong></div>
          </div>

          <el-form label-position="top" class="tight-form contact-question-form">
            <el-form-item label="问题描述">
              <el-input
                v-model="contactForm.issue"
                type="textarea"
                :rows="8"
                placeholder="例如：reg 环境下已执行审批和 PSP started，但没有推进到 eSign。期望继续到签约完成。手机号 / session / 报错如下..."
              />
            </el-form-item>
            <el-button type="primary" :icon="Position" @click="submitContactIssue">提交问题</el-button>
          </el-form>
        </el-card>

        <el-card shadow="never" class="surface-card contact-admin-card">
          <template #header>
            <div class="card-head">
              <div class="head-copy">
                <h3>问题记录</h3>
                <p>按最新提交时间倒序展示，已回复内容会保留在对应问题下方。</p>
              </div>
              <el-tag type="info" effect="plain">{{ contactIssues.length }} 条</el-tag>
            </div>
          </template>

          <section class="contact-issue-list">
            <div v-if="contactIssues.length === 0" class="contact-empty">还没有提交的问题。</div>
            <article v-for="item in contactIssues" :key="item.id" class="contact-issue-item">
              <div class="contact-issue-head">
                <el-tag :type="item.status === '已回复' ? 'success' : 'warning'" effect="plain">{{ item.status }}</el-tag>
                <span>{{ item.created_at }}</span>
              </div>
              <p class="contact-issue-text">{{ item.issue }}</p>
              <div class="contact-issue-meta">
                <span>{{ item.env }}</span>
                <span>{{ item.phone_number }}</span>
                <span>{{ item.session_id }}</span>
              </div>
              <div v-if="item.reply" class="contact-reply-result">
                <span>回复 {{ item.replied_at }}</span>
                <p>{{ item.reply }}</p>
              </div>
            </article>
          </section>
        </el-card>
      </div>
    </section>

    <section v-else-if="currentView === 'ai'" class="ai-page-view">
      <div class="ai-page-shell">
        <main class="ai-conversation-panel">
          <div class="ai-conversation-head">
            <div>
              <p class="eyebrow">DPU Chat</p>
              <h2>AI 助手</h2>
              <p>像聊天一样提问，也可以直接执行只读 SQL、查询 merchant、分析最近日志和当前 session。</p>
            </div>
            <div class="ai-conversation-actions">
              <el-select v-model="aiExecutionEnv" class="ai-exec-select" aria-label="AI 执行环境">
                <el-option
                  v-for="env in aiSqlDataSources"
                    :key="`ai-${env}`"
                    :label="env"
                    :value="env"
                />
              </el-select>
              <el-tag size="large" :type="aiSending ? 'warning' : 'success'">{{ aiSending ? '处理中' : '就绪' }}</el-tag>
              <el-button :icon="Delete" plain @click="clearAiChat">清空对话</el-button>
              <el-button plain :icon="Refresh" @click="backToConsole">返回控制台</el-button>
            </div>
          </div>

          <div class="ai-context-strip">
            <div><span>Session</span><strong>{{ activeSessionId || '-' }}</strong></div>
            <div><span>环境</span><strong>{{ sessionSummary?.env || connectionForm.env }}</strong></div>
            <div><span>手机号</span><strong>{{ sessionSummary?.phone_number || connectionForm.phone_number || '-' }}</strong></div>
            <div><span>Merchant</span><strong>{{ sessionSummary?.merchant_id || '-' }}</strong></div>
            <div><span>实时日志</span><strong>{{ logStatusText }}</strong></div>
          </div>

          <div v-if="aiMessages.length === 0" class="ai-empty-state">
            <p>可以直接问业务问题，也可以粘贴 SQL。比如“帮我看当前 session 为什么没推进到 eSign”，或者直接输入一条 SELECT。</p>
            <p>助手会带上当前环境、Session、手机号、Merchant 和最近日志上下文；需要切换查询环境时，直接改上方环境选择。</p>
            <div class="ai-prompt-grid">
              <button v-for="prompt in aiQuickPrompts" :key="prompt" type="button" @click="useAiPrompt(prompt)">
                {{ prompt }}
              </button>
            </div>
          </div>

          <div class="ai-chat-body ai-page-chat-body">
            <template v-for="message in aiMessages" :key="message.id">
              <div v-if="message.role === 'system'" class="chat-model-switch">
                <span class="chat-model-switch-icon">⇌</span>
                <span>{{ message.content }}</span>
              </div>
              <div v-else class="chat-message" :class="message.role">
              <div class="chat-avatar" :class="message.role">
                <el-icon v-if="message.role === 'user'"><User /></el-icon>
                <svg v-else viewBox="0 0 24 24" width="20" height="20" fill="currentColor" aria-hidden="true">
                  <path d="M22.282 9.821a5.985 5.985 0 0 0-.516-4.91 6.046 6.046 0 0 0-6.51-2.9A6.065 6.065 0 0 0 4.981 4.18a5.985 5.985 0 0 0-3.998 2.9 6.046 6.046 0 0 0 .743 7.097 5.98 5.98 0 0 0 .51 4.911 6.051 6.051 0 0 0 6.515 2.9A5.985 5.985 0 0 0 13.26 24a6.056 6.056 0 0 0 5.772-4.206 5.99 5.99 0 0 0 3.997-2.9 6.056 6.056 0 0 0-.747-7.073zm-9.022 12.61a4.476 4.476 0 0 1-2.876-1.04l.141-.081 4.779-2.758a.795.795 0 0 0 .392-.681v-6.737l2.02 1.168a.071.071 0 0 1 .038.052v5.583a4.504 4.504 0 0 1-4.494 4.494zM3.6 18.304a4.47 4.47 0 0 1-.535-3.014l.142.085 4.783 2.759a.771.771 0 0 0 .78 0l5.843-3.369v2.332a.08.08 0 0 1-.033.062L9.74 19.95a4.5 4.5 0 0 1-6.14-1.646zM2.34 7.896a4.485 4.485 0 0 1 2.366-1.973V11.6a.766.766 0 0 0 .388.676l5.815 3.355-2.02 1.168a.076.076 0 0 1-.071 0l-4.83-2.786A4.504 4.504 0 0 1 2.34 7.872zm16.597 3.855-5.833-3.387L15.119 7.2a.076.076 0 0 1 .071 0l4.83 2.791a4.494 4.494 0 0 1-.676 8.105v-5.678a.79.79 0 0 0-.407-.667zm2.01-3.023-.141-.085-4.774-2.782a.776.776 0 0 0-.785 0L9.409 9.23V6.897a.066.066 0 0 1 .028-.061l4.83-2.787a4.5 4.5 0 0 1 6.68 4.66zm-12.64 4.135-2.02-1.164a.08.08 0 0 1-.038-.057V6.075a4.5 4.5 0 0 1 7.375-3.453l-.142.08L8.704 5.46a.795.795 0 0 0-.393.681zm1.097-2.365 2.602-1.5 2.607 1.5v2.999l-2.597 1.5-2.607-1.5z"/>
                </svg>
              </div>
              <div class="chat-content">
                <div class="chat-meta">
                  <span>{{ message.at }}</span>
                </div>
                <div class="chat-bubble" v-html="renderMarkdown(message.content)" @click="onChatBubbleClick"></div>
                <details v-if="message.meta?.rendered" class="chat-detail">
                  <summary>已执行 SQL / 脚本</summary>
                  <pre>{{ message.meta.rendered }}</pre>
                </details>
                <details v-if="message.meta?.execution" class="chat-detail">
                  <summary>模板执行结果</summary>
                  <pre>{{ JSON.stringify(message.meta.execution, null, 2) }}</pre>
                </details>
                <details v-if="message.meta?.tool_result" class="chat-detail">
                  <summary>工具结果</summary>
                  <pre>{{ JSON.stringify(message.meta.tool_result, null, 2) }}</pre>
                </details>
              </div>
            </div>
            </template>
          </div>

          <div v-if="aiError" class="chat-error">{{ aiError }}</div>

          <div class="ai-page-input">
            <div class="ai-composer">
              <el-input
                v-model="aiInput"
                type="textarea"
                :rows="4"
                resize="none"
                placeholder="问 DPU 问题、让它分析日志，或直接输入 SQL，例如：select merchant_id from dpu_users where phone_number='...'"
                @keydown.enter.exact.prevent="handleAiSend"
              />
              <div class="ai-composer-toolbar">
                <div class="ai-composer-trailing">
                  <el-select
                    v-model="aiModel"
                    size="small"
                    class="ai-composer-select ai-composer-select-model"
                    aria-label="推理模型"
                  >
                    <el-option
                      v-for="opt in aiModelOptions"
                      :key="opt.value"
                      :label="opt.label"
                      :value="opt.value"
                    />
                  </el-select>
                  <el-select
                    v-model="aiReasoningEffort"
                    size="small"
                    class="ai-composer-select ai-composer-select-effort"
                    aria-label="思考级别"
                  >
                    <el-option
                      v-for="opt in aiReasoningOptions"
                      :key="opt.value"
                      :label="opt.label"
                      :value="opt.value"
                    />
                  </el-select>
                  <button
                    type="button"
                    class="ai-composer-send"
                    :class="{ disabled: !aiInput.trim() || aiSending }"
                    :disabled="!aiInput.trim() || aiSending"
                    aria-label="发送"
                    @click="handleAiSend"
                  >
                    <el-icon v-if="aiSending"><Loading /></el-icon>
                    <el-icon v-else><Top /></el-icon>
                  </button>
                </div>
              </div>
            </div>
          </div>
        </main>
      </div>
    </section>

    <section v-else-if="currentView === 'promptTemplates'" class="tool-page-view prompt-templates-view">
      <div class="log-system-head">
        <div class="head-copy">
          <span class="eyebrow"><span class="eyebrow-dot"></span> PROMPT TEMPLATES</span>
          <h2>提示词模板</h2>
          <p>
            {{ isAdmin
              ? '维护可执行的 SQL / HTTP / Python 模板，用户在 AI 助手描述需求后会自动填参并执行。'
              : 'admin 预设的可执行模板，描述你的需求，AI 会自动填参并执行对应 SQL / HTTP / Python。' }}
          </p>
        </div>
        <div class="prompt-templates-head-actions">
          <el-input
            v-model="promptTemplateSearch"
            class="prompt-templates-search"
            placeholder="按名称/描述搜索模板"
            clearable
            :prefix-icon="Search"
          />
          <el-button :icon="Refresh" plain :loading="promptTemplatesLoading" @click="refreshPromptTemplates">刷新</el-button>
          <el-button v-if="isAdmin" type="primary" :icon="Plus" @click="openPromptTemplateForm(null)">新建模板</el-button>
        </div>
      </div>

      <p v-if="promptTemplatesError" class="login-error" style="margin: 0 0 12px">{{ promptTemplatesError }}</p>

      <div v-if="!promptTemplatesLoading && promptTemplates.length === 0" class="session-empty">
        <span class="session-empty__icon"><el-icon><Tickets /></el-icon></span>
        <p class="session-empty__title">还没有模板</p>
        <p class="session-empty__hint">
          {{ isAdmin ? '点击右上角「新建模板」开始维护可执行脚本。' : '请联系管理员先创建提示词模板。' }}
        </p>
      </div>

      <div v-else-if="!promptTemplatesLoading && promptTemplatesTotal === 0" class="session-empty">
        <span class="session-empty__icon"><el-icon><Search /></el-icon></span>
        <p class="session-empty__title">没有匹配的模板</p>
        <p class="session-empty__hint">换个关键词，或清空搜索框查看全部。</p>
      </div>

      <div v-else-if="promptTemplatesTotal > 0" class="prompt-templates-grid">
        <article
          v-for="template in pagedPromptTemplates"
          :key="template.id"
          class="prompt-template-card"
          :class="{ 'is-disabled': template.is_disabled }"
        >
          <header class="prompt-template-card__head">
            <div>
              <div class="prompt-template-card__tags">
                <el-tag size="small" effect="dark" :type="template.logic_type === 'sql' ? 'success' : (template.logic_type === 'http' ? 'warning' : 'info')">
                  {{ template.logic_type?.toUpperCase() || 'SQL' }}
                </el-tag>
                <el-tag v-if="template.is_disabled" size="small" type="danger" effect="plain">已禁用</el-tag>
              </div>
              <h3>{{ template.title }}</h3>
            </div>
            <div class="prompt-template-card__meta">
              <span>{{ template.created_by || '-' }}</span>
              <span>{{ template.updated_at || template.created_at }}</span>
            </div>
          </header>
          <p class="prompt-template-card__desc">{{ template.description || '（无描述）' }}</p>
          <div class="prompt-template-card__body">
            <section class="prompt-template-card__column">
              <div class="prompt-template-card__column-head">
                <strong>底层逻辑</strong>
                <small>admin 写入，AI 会按描述填参</small>
              </div>
              <pre class="prompt-template-card__logic">{{ template.logic }}</pre>
            </section>
            <section class="prompt-template-card__column">
              <div class="prompt-template-card__column-head">
                <strong>完整提示词</strong>
                <small>可直接复制到 AI 助手触发同样逻辑</small>
                <el-button
                  v-if="template.example_prompt"
                  size="small"
                  plain
                  :icon="DocumentCopy"
                  @click="copyPromptToAi(template)"
                >发送到 AI 助手</el-button>
              </div>
              <pre v-if="template.example_prompt" class="prompt-template-card__logic">{{ template.example_prompt }}</pre>
              <div v-else class="prompt-template-card__empty">未配置完整提示词</div>
            </section>
          </div>
          <footer class="prompt-template-card__actions">
            <el-button
              type="primary"
              :icon="Promotion"
              :disabled="template.is_disabled"
              @click="openPromptTemplateUse(template)"
            >使用</el-button>
            <template v-if="isAdmin">
              <el-button plain :icon="Document" @click="openPromptTemplateForm(template)">编辑</el-button>
              <el-button
                plain
                :type="template.is_disabled ? 'success' : 'warning'"
                :icon="template.is_disabled ? SwitchButton : SwitchButton"
                @click="togglePromptTemplateDisabled(template)"
              >{{ template.is_disabled ? '启用' : '禁用' }}</el-button>
              <el-button plain type="danger" :icon="Delete" @click="removePromptTemplate(template)">删除</el-button>
            </template>
          </footer>
        </article>
      </div>

      <div v-if="promptTemplatesTotal > promptTemplatePageSize" class="prompt-templates-pagination">
        <el-pagination
          layout="prev, pager, next, total"
          background
          :total="promptTemplatesTotal"
          :page-size="promptTemplatePageSize"
          :current-page="promptTemplatePage"
          @current-change="(pg) => (promptTemplatePage = pg)"
        />
      </div>

      <el-dialog
        v-model="promptTemplateFormVisible"
        :title="promptTemplateForm.id ? '编辑模板' : '新建模板'"
        width="640px"
      >
        <el-form label-position="top" class="prompt-template-form">
          <el-form-item label="标题">
            <el-input v-model.trim="promptTemplateForm.title" placeholder="例：修改 offer 3PL sales_value" />
          </el-form-item>
          <el-form-item label="描述">
            <el-input
              v-model.trim="promptTemplateForm.description"
              type="textarea"
              :rows="2"
              placeholder="告诉用户这个模板能做什么、需要提供哪些信息。"
            />
          </el-form-item>
          <el-form-item label="逻辑类型">
            <el-select v-model="promptTemplateForm.logic_type">
              <el-option label="SQL" value="sql" />
              <el-option label="HTTP" value="http" />
              <el-option label="Python" value="python" />
            </el-select>
          </el-form-item>
          <el-form-item label="逻辑">
            <el-input
              v-model="promptTemplateForm.logic"
              type="textarea"
              :rows="10"
              placeholder="UPDATE shop_performance SET sales_value = ${value} WHERE platform_offer_id = '${offer_id}' AND platform_type = '3PL';"
            />
          </el-form-item>
          <el-form-item label="完整提示词（可选）">
            <el-input
              v-model="promptTemplateForm.example_prompt"
              type="textarea"
              :rows="3"
              placeholder="例：把 amzn1.lending.offer.cny.xxxTESTOFFER 3pl sales_value 提升到 3505000"
            />
          </el-form-item>
          <el-form-item label="锁定环境（可选）">
            <el-input
              v-model.trim="promptTemplateForm.locked_env"
              placeholder="留空表示由用户选；填入后将锁定该环境（例：douke、dowsure、reg、uat）"
            />
            <p class="prompt-template-form__hint" style="margin: 4px 0 0; color: var(--muted); font-size: 12px;">
              填入后，使用模板弹窗里的环境下拉会被置灰，只能在该环境执行。
            </p>
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="promptTemplateFormVisible = false">取消</el-button>
          <el-button type="primary" :loading="promptTemplateSaving" @click="savePromptTemplate">保存</el-button>
        </template>
      </el-dialog>

      <el-dialog
        v-model="promptTemplateUseVisible"
        :title="promptTemplateUseTarget ? `使用模板：${promptTemplateUseTarget.title}` : '使用模板'"
        width="720px"
        class="prompt-template-use-dialog"
        append-to-body
      >
        <div v-if="promptTemplateUseTarget" class="prompt-template-use">
          <section class="prompt-template-use__meta">
            <el-tag size="small" effect="dark" :type="promptTemplateUseTarget.logic_type === 'sql' ? 'success' : (promptTemplateUseTarget.logic_type === 'http' ? 'warning' : 'info')">
              {{ promptTemplateUseTarget.logic_type?.toUpperCase() || 'SQL' }}
            </el-tag>
            <p v-if="promptTemplateUseTarget.description">{{ promptTemplateUseTarget.description }}</p>
          </section>

          <el-form label-position="top" class="prompt-template-use__form">
            <el-form-item label="执行环境">
              <el-select
                v-model="promptTemplateUseForm.env"
                :disabled="!!promptTemplateUseTarget?.locked_env"
              >
                <el-option
                  v-for="env in useDialogEnvOptions"
                  :key="env"
                  :label="env"
                  :value="env"
                />
              </el-select>
              <p v-if="promptTemplateUseTarget?.locked_env" class="prompt-template-use__lock-hint">
                该模板已锁定到「{{ promptTemplateUseTarget.locked_env }}」环境，不可修改。
              </p>
            </el-form-item>
            <el-form-item :label="useDialogParamFields.length ? '请提供参数' : useDialogInputLabel">
              <div v-if="useDialogParamFields.length" class="prompt-template-use__params">
                <div
                  v-for="field in useDialogParamFields"
                  :key="field.key"
                  class="prompt-template-use__param"
                >
                  <label class="prompt-template-use__param-label">
                    <span>{{ field.label }}</span>
                    <code>{{ field.key }}</code>
                  </label>
                  <small v-if="field.help" class="prompt-template-use__param-help">
                    {{ field.help }}
                  </small>
                  <el-select
                    v-if="field.options"
                    v-model="promptTemplateUseParams[field.key]"
                    :placeholder="field.placeholder || `请选择${field.label}`"
                    :disabled="field.disabled"
                    :clearable="!field.disabled"
                    @change="handlePromptTemplateParamChange(field.key)"
                  >
                    <el-option
                      v-for="option in field.options"
                      :key="option.value"
                      :label="option.label"
                      :value="option.value"
                    />
                  </el-select>
                  <el-input
                    v-else-if="['phone', 'phone_number'].includes(field.key)"
                    v-model="promptTemplateUseParams[field.key]"
                    type="tel"
                    inputmode="numeric"
                    maxlength="11"
                    placeholder="请输入 8 位或 11 位手机号"
                  />
                  <el-input
                    v-else-if="field.key === 'user_id'"
                    v-model="promptTemplateUseParams[field.key]"
                    type="number"
                    min="1"
                    step="1"
                    :placeholder="`请输入${field.label}`"
                  />
                  <el-input
                    v-else
                    v-model="promptTemplateUseParams[field.key]"
                    :disabled="field.disabled"
                    :placeholder="field.disabled
                      ? '不准入店铺不允许填写 CUSTOM 年销售额'
                      : `请输入${field.label}`"
                  />
                </div>
              </div>
              <el-input
                v-else
                v-model="promptTemplateUseForm.user_input"
                type="textarea"
                :rows="4"
                :placeholder="useDialogInputPlaceholder"
              />
            </el-form-item>
          </el-form>

          <p v-if="promptTemplateUseError" class="login-error" style="margin: 0">{{ promptTemplateUseError }}</p>

          <div v-if="promptTemplateUseResult" class="prompt-template-use-result">
            <h4>填好的脚本</h4>
            <pre>{{ promptTemplateUseResult.rendered }}</pre>
            <h4>执行结果</h4>
            <pre>{{ JSON.stringify(promptTemplateUseResult.execution, null, 2) }}</pre>
            <div
              v-if="promptTemplateUseResult.summary && promptTemplateUseResult.summary.summary"
              class="prompt-template-use-summary"
            >
              <h4>AI 解读</h4>
              <p class="prompt-template-use-summary-text">{{ promptTemplateUseResult.summary.summary }}</p>
              <div
                v-if="promptTemplateUseResult.cross_env_hits && promptTemplateUseResult.cross_env_hits.length"
                class="prompt-template-use-summary-probe"
              >
                <p class="prompt-template-use-summary-probe-title">
                  顺手跨环境核查（{{ promptTemplateUseResult.summary.probe_label || '同一业务键' }}）：
                </p>
                <ul>
                  <li v-for="hit in promptTemplateUseResult.cross_env_hits" :key="hit.env">
                    <strong>{{ hit.env }}</strong>：命中 {{ hit.row_count }} 条<span
                      v-if="hit.rows && hit.rows.length"
                    >，{{ Object.entries(hit.rows[0]).map(([k, v]) => `${k}=${v}`).join('、') }}</span>
                  </li>
                </ul>
              </div>
            </div>
            <p v-if="promptTemplateUseResult.notes" class="prompt-template-use-notes">说明：{{ promptTemplateUseResult.notes }}</p>
          </div>
        </div>
        <template #footer>
          <el-button @click="promptTemplateUseVisible = false">关闭</el-button>
          <el-button
            type="primary"
            :loading="promptTemplateUseLoading"
            @click="executePromptTemplateAction"
          >
            提交执行
          </el-button>
        </template>
      </el-dialog>
    </section>

    <section v-else-if="currentView === 'userManagement'" class="tool-page-view user-management-view">
      <div class="log-system-head">
        <div>
          <p class="eyebrow"><span class="eyebrow-dot"></span> USER MANAGEMENT</p>
          <h2>用户管理</h2>
          <p>查看、编辑所有注册账号，可修改账号名、密码、备注，或永久删除账号。</p>
        </div>
        <el-button plain :icon="Refresh" :loading="adminUsersLoading" @click="refreshAdminUsers">刷新</el-button>
      </div>

      <p v-if="adminUsersError" class="login-error" style="margin: 0 0 12px">{{ adminUsersError }}</p>

      <el-card shadow="never" class="surface-card">
        <div v-if="adminUsersLoading && adminUsers.length === 0" class="session-empty">
          <span class="session-empty__icon"><el-icon><Setting /></el-icon></span>
          <p class="session-empty__title">加载中…</p>
        </div>
        <div v-else-if="adminUsers.length === 0" class="session-empty">
          <span class="session-empty__icon"><el-icon><User /></el-icon></span>
          <p class="session-empty__title">暂无账号</p>
        </div>
        <div v-else class="user-management-table">
          <div class="user-table-head user-table-row">
            <span class="col-username">账号</span>
            <span class="col-role">角色</span>
            <span class="col-status">状态</span>
            <span class="col-notes">备注</span>
            <span class="col-created">注册时间</span>
            <span class="col-login">最近登录</span>
            <span class="col-actions"></span>
          </div>
          <article
            v-for="user in adminUsersPagedData"
            :key="user.id"
            class="user-table-row"
            :class="{ 'is-admin-row': user.role === 'admin', 'is-pending-row': user.status === 'pending' }"
          >
            <span class="col-username">
              <code>{{ user.username }}</code>
              <el-tag v-if="user.role === 'admin'" size="small" type="success" effect="plain" style="margin-left: 6px;">管理员</el-tag>
            </span>
            <span class="col-role">{{ user.role === 'admin' ? '管理员' : '普通用户' }}</span>
            <span class="col-status">
              <el-tag
                size="small"
                effect="plain"
                :type="user.status === 'active' ? 'success' : user.status === 'pending' ? 'warning' : 'danger'"
              >{{ user.status === 'active' ? '正常' : user.status === 'pending' ? '待审核' : '已拒绝' }}</el-tag>
            </span>
            <span class="col-notes user-notes-cell">{{ user.notes || '—' }}</span>
            <span class="col-created">{{ user.created_at || '—' }}</span>
            <span class="col-login">{{ user.last_login_at || '从未登录' }}</span>
            <span class="col-actions">
              <template v-if="user.status === 'pending'">
                <el-button size="small" type="success" plain :icon="Check" @click="approveUser(user)">通过</el-button>
                <el-button size="small" type="danger" plain @click="rejectUser(user)">拒绝</el-button>
              </template>
              <template v-else>
                <el-button size="small" plain :icon="Edit" @click="openAdminUserEdit(user)">编辑</el-button>
                <el-button
                  size="small"
                  plain
                  type="danger"
                  :icon="Delete"
                  :disabled="user.role === 'admin'"
                  :title="user.role === 'admin' ? '不能删除管理员账号' : ''"
                  @click="removeAdminUser(user)"
                >删除</el-button>
              </template>
            </span>
          </article>
          <div v-if="adminUsers.length > adminUsersPageSize" class="user-table-pagination">
            <el-pagination
              v-model:current-page="adminUsersPage"
              v-model:page-size="adminUsersPageSize"
              :page-sizes="[10, 20, 50]"
              :total="adminUsers.length"
              layout="total, sizes, prev, pager, next"
              background
              small
            />
          </div>
        </div>
      </el-card>

      <!-- Edit user dialog -->
      <el-dialog
        v-model="adminUserEditVisible"
        title="编辑账号"
        width="480px"
      >
        <el-form label-position="top" class="prompt-template-form">
          <el-form-item label="账号名">
            <el-input v-model.trim="adminUserEditForm.new_username" placeholder="账号名" autocomplete="off" />
          </el-form-item>
          <el-form-item label="新密码（留空不修改）">
            <el-input
              v-model="adminUserEditForm.new_password"
              type="password"
              show-password
              placeholder="留空则不更改密码"
              autocomplete="new-password"
            />
          </el-form-item>
          <el-form-item label="备注">
            <el-input
              v-model="adminUserEditForm.notes"
              type="textarea"
              :rows="3"
              placeholder="填写备注，例如：负责 UAT 环境 / 内部测试账号"
            />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="adminUserEditVisible = false">取消</el-button>
          <el-button type="primary" :loading="adminUserEditSaving" @click="saveAdminUserEdit">保存</el-button>
        </template>
      </el-dialog>
    </section>

    <section v-else-if="currentView === 'contactAdmin'" class="tool-page-view contact-admin-view">
      <div class="log-system-head">
        <div>
          <p class="eyebrow">Admin</p>
          <h2>回复问题</h2>
          <p>管理员在这里统一回复“联系我们”提交的问题。</p>
        </div>
        <el-button plain :icon="Refresh" @click="backToConsole">返回控制台</el-button>
      </div>

      <div class="contact-admin-grid contact-admin-grid-stack">
        <el-card shadow="never" class="surface-card contact-admin-card">
          <template #header>
            <div class="card-head">
              <div class="head-copy">
                <h3>待处理问题</h3>
                <p>这里只显示未回复的问题；回复后会回显到“联系我们”的问题记录里。</p>
              </div>
              <el-tag type="info" effect="plain">{{ pendingContactIssues.length }} 条</el-tag>
            </div>
          </template>

          <section class="contact-issue-list contact-issue-list-admin">
            <div v-if="pendingContactIssues.length === 0" class="contact-empty">暂无待处理问题。</div>
            <article v-for="item in pendingContactIssues" :key="item.id" class="contact-issue-item">
              <div class="contact-issue-head">
                <div class="contact-issue-state">
                  <el-tag :type="item.status === '已回复' ? 'success' : 'warning'" effect="plain">{{ item.status }}</el-tag>
                  <span>{{ item.created_at }}</span>
                </div>
                <el-button
                  type="danger"
                  plain
                  :icon="Delete"
                  @click="deleteContactIssue(item.id)"
                >删除</el-button>
              </div>
              <p class="contact-issue-text">{{ item.issue }}</p>
              <div class="contact-issue-meta">
                <span>{{ item.env }}</span>
                <span>{{ item.phone_number }}</span>
                <span>{{ item.session_id }}</span>
              </div>
              <div v-if="item.reply" class="contact-reply-result">
                <span>回复 {{ item.replied_at }}</span>
                <p>{{ item.reply }}</p>
              </div>
              <el-button
                type="primary"
                plain
                :icon="ChatLineRound"
                @click="replyContactIssue(item)"
              >回复该问题</el-button>
            </article>
          </section>
        </el-card>

        <el-card shadow="never" class="surface-card contact-admin-card">
          <template #header>
            <div class="card-head">
              <div class="head-copy">
                <h3>回复问题</h3>
                <p>先填写回复内容，再在上方选择一个待处理问题。</p>
              </div>
              <el-tag type="success" effect="plain">{{ authDisplayName }} 已登录</el-tag>
            </div>
          </template>

          <div class="contact-reply-box">
            <el-input
              v-model="contactAdminForm.reply"
              type="textarea"
              :rows="5"
              placeholder="输入回复内容，然后在上方选择一个待回复问题。"
            />
          </div>

          <p v-if="contactAdminError" class="contact-error">{{ contactAdminError }}</p>
        </el-card>
      </div>
    </section>

    <section v-else class="workspace-grid">
      <div class="workspace-row">
        <el-card shadow="never" class="surface-card workspace-row__main connection-card">
          <template #header>
            <div class="card-head">
              <div class="head-copy">
                <h2>连接与注册</h2>
                <p>先建立 session，再执行 mock 操作。</p>
              </div>
              <el-space>
                <el-button :icon="Refresh" plain :loading="loadingHealth || loadingSessions" @click="loadSessions(); refreshHealth()">
                  刷新状态
                </el-button>
                <el-button :icon="Delete" type="danger" plain :disabled="!activeSessionId" :loading="disconnecting" @click="handleDisconnect">
                  断开会话
                </el-button>
              </el-space>
            </div>
          </template>

          <div class="dual-panel">
            <div class="form-block">
              <h3><el-icon><Connection /></el-icon> 会话连接</h3>
              <el-form label-position="top" class="tight-form">
                <el-form-item label="环境">
                  <el-select v-model="connectionForm.env">
                    <el-option
                      v-for="env in enumOptions?.environments ?? defaultEnvironments"
                      :key="env"
                      :label="env"
                      :value="env"
                    />
                  </el-select>
                </el-form-item>
                <el-form-item label="手机号">
                  <el-input v-model.trim="connectionForm.phone_number" placeholder="8位或11位数字" />
                </el-form-item>
                <el-button type="primary" :icon="Connection" :loading="connecting" @click="handleConnect">
                  连接 session
                </el-button>
              </el-form>
            </div>

            <div class="form-block">
              <h3><el-icon><Document /></el-icon> 新账号注册</h3>
              <el-form label-position="top" class="tight-form">
                <el-form-item label="环境">
                  <el-select v-model="registerForm.env">
                    <el-option
                      v-for="env in enumOptions?.environments ?? defaultEnvironments"
                      :key="`reg-${env}`"
                      :label="env"
                      :value="env"
                    />
                  </el-select>
                </el-form-item>
                <div class="form-row register-fields" :class="{ 'is-offline': registerForm.offline }">
                  <el-form-item v-if="!registerForm.offline" label="Journey">
                    <el-select v-model="registerForm.journey">
                      <el-option
                        v-for="journey in enumOptions?.journeys ?? defaultJourneys"
                        :key="journey"
                        :label="journeyLabel(journey)"
                        :value="journey"
                      />
                    </el-select>
                  </el-form-item>
                  <el-form-item label="币种" :class="{ 'full-row': registerForm.offline }">
                    <el-select v-model="registerForm.currency">
                      <el-option
                        v-for="currency in enumOptions?.currencies ?? defaultCurrencies"
                        :key="currency"
                        :label="currency"
                        :value="currency"
                      />
                    </el-select>
                  </el-form-item>
                  <el-form-item label="资方代码" class="full-row">
                    <el-select v-model="registerForm.funder_resource">
                      <el-option
                        v-for="funderResource in enumOptions?.funder_resources ?? defaultFunderResources"
                        :key="funderResource"
                        :label="funderResource"
                        :value="funderResource"
                      />
                    </el-select>
                  </el-form-item>
                </div>
                <el-form-item>
                  <el-switch v-model="registerForm.offline" active-text="线下模式" inactive-text="线上模式" />
                </el-form-item>
                <div class="register-actions">
                  <el-button
                    type="primary"
                    :icon="Promotion"
                    :loading="registering"
                    :disabled="onlineUsdHsbcBlocked"
                    :title="onlineUsdHsbcBlocked ? onlineUsdHsbcBlockedReason : ''"
                    @click="handleRegister"
                  >
                    执行注册
                  </el-button>
                  <el-button
                    type="primary"
                    plain
                    :icon="Connection"
                    :loading="registeringAndBinding"
                    :disabled="registerAndBindingBlocked"
                    :title="registerAndBindingBlocked ? registerAndBindingBlockedReason : ''"
                    @click="handleRegisterAndRunMultiShop"
                  >
                    注册并完成绑店
                  </el-button>
                </div>
              </el-form>
            </div>
          </div>

        </el-card>

        <el-card shadow="never" class="surface-card workspace-row__side session-card">
          <template #header>
            <div class="card-head">
              <div class="head-copy">
                <h2>当前会话</h2>
                <p>活动连接与最近状态。</p>
              </div>
            </div>
          </template>

          <div v-if="sessionSummary" class="session-summary">
            <div class="summary-row"><span>Session ID</span><strong>{{ sessionSummary.session_id }}</strong></div>
            <div class="summary-row"><span>环境</span><strong>{{ sessionSummary.env }}</strong></div>
            <div class="summary-row"><span>手机号</span><strong>{{ sessionSummary.phone_number }}</strong></div>
            <div class="summary-row"><span>Merchant</span><strong>{{ sessionSummary.merchant_id || '-' }}</strong></div>
            <div class="summary-row"><span>选中申请单</span><strong>{{ selectedApplicationUniqueId || '-' }}</strong></div>
            <div class="summary-row"><span>申请单数量</span><strong>{{ applicationOptions.length }}</strong></div>
          </div>
          <div v-else class="session-empty">
            <span class="session-empty__icon">
              <el-icon><Bell /></el-icon>
            </span>
            <p class="session-empty__title">还没有活动会话</p>
            <p class="session-empty__hint">连接 session 后会显示 ID、Merchant 与申请单。</p>
          </div>
        </el-card>
      </div>

      <el-card shadow="never" class="surface-card mock-panel-card">
        <template #header>
          <div class="card-head">
              <div class="head-copy">
                <h2>Mock 操作面板</h2>
                <p>{{ mockOperationEditMode ? '排版模式：拖动模块调整顺序，保存后全局生效。' : '按当前 session 执行 webhook 模拟操作，执行结果会保留在对应步骤下方。' }}</p>
              </div>
              <div v-if="isAdmin" class="mock-layout-actions">
                <el-tag v-if="mockOperationEditMode" size="small" type="warning" effect="plain">排版中</el-tag>
                <el-button v-if="mockOperationEditMode" size="small" @click="cancelMockOperationLayout">取消</el-button>
                <el-button v-if="mockOperationEditMode" size="small" type="primary" @click="saveMockOperationLayout">保存排版</el-button>
                <span v-else class="mock-layout-hint">长按模块进入排版</span>
              </div>
            </div>
          </template>

          <div class="operation-context">
            <div>
              <span>环境</span>
              <strong>{{ sessionSummary?.env || connectionForm.env }}</strong>
            </div>
            <div>
              <span>手机号</span>
              <strong>{{ sessionSummary?.phone_number || connectionForm.phone_number || '-' }}</strong>
            </div>
            <div>
              <span>Merchant ID</span>
              <strong>{{ sessionSummary?.merchant_id || '-' }}</strong>
            </div>
          </div>

          <div v-if="sessionSummary" class="application-selector">
            <span class="application-selector-label">申请单</span>
            <div class="application-selector-current">
              <div>
                <span>Application</span>
                <strong>{{ selectedApplicationUniqueId || sessionSummary?.application_unique_id || '-' }}</strong>
              </div>
              <div>
                <span>Currency</span>
                <strong>{{ selectedApplicationCurrency }}</strong>
              </div>
              <div>
                <span>Lender</span>
                <strong>{{ selectedApplication?.lender_code || sessionSummary?.lender_code || '-' }}</strong>
              </div>
              <div>
                <span>Status</span>
                <strong>{{ selectedApplication?.application_status || sessionSummary?.application_status || '-' }}</strong>
              </div>
            </div>
            <el-select
              v-if="applicationOptions.length > 1"
              v-model="selectedApplicationUniqueId"
              filterable
              class="application-select"
              popper-class="application-select-popper"
              :popper-options="{ modifiers: [{ name: 'preventOverflow', options: { boundary: 'clippingParents' } }] }"
            >
              <el-option
                v-for="application in applicationOptions"
                :key="application.application_unique_id"
                :label="application.application_unique_id"
                :value="application.application_unique_id"
              >
                <div class="application-option">
                  <strong>{{ application.application_unique_id }}</strong>
                  <span>{{ application.finance_product_currency || selectedApplicationCurrency }}</span>
                  <span>{{ application.application_status || '-' }}</span>
                  <span>{{ application.lender_code || '-' }}</span>
                </div>
              </el-option>
            </el-select>
            <span v-else class="application-single-note">默认最新申请单</span>
          </div>

          <div class="operation-panels operation-button-list">
            <template v-for="operation in visibleOperations" :key="operation.key">
            <div
              class="operation-row"
              :class="{ active: activeOperationKey === operation.key, disabled: isOperationDisabled(operation), 'is-layout-item': mockOperationEditMode, 'is-layout-dragging': mockOperationDragState === operation.key }"
              :draggable="isAdmin && mockOperationEditMode"
              @pointerdown="startMockOperationLongPress"
              @pointerup="stopMockOperationLongPress"
              @pointerleave="stopMockOperationLongPress"
              @pointercancel="stopMockOperationLongPress"
              @dragstart="onMockOperationDragStart($event, operation.key)"
              @dragover.prevent="isAdmin && mockOperationEditMode"
              @drop="onMockOperationDrop($event, operation.key)"
              @dragend="onMockOperationDragEnd"
            >
              <button
                type="button"
                class="operation-toggle"
                :aria-expanded="activeOperationKey === operation.key"
                :aria-disabled="isOperationDisabled(operation)"
                :disabled="isOperationDisabled(operation)"
                :title="isOperationDisabled(operation) ? operationDisabledReason(operation) : operation.description"
                @click="toggleOperationPanel(operation.key)"
              >
                <span class="operation-toggle-main">
                  <span class="operation-toggle-badge">
                    <el-icon><CaretRight /></el-icon>
                  </span>
                  <span class="operation-toggle-text">
                    <b>{{ operation.title }}</b>
                    <code>{{ operation.endpoint }}</code>
                  </span>
                </span>
                <span class="operation-toggle-meta">
                  <span v-if="isOperationDisabled(operation)" class="operation-disabled-chip">{{ operationDisabledChip(operation) }}</span>
                  <el-icon class="operation-toggle-arrow"><component :is="activeOperationKey === operation.key ? ArrowDown : ArrowRight" /></el-icon>
                </span>
              </button>
            </div>

            <div
              v-if="activeOperationKey === operation.key && activeOperation"
              class="operation-detail-dock"
            >
            <div class="operation-detail-head">
              <div>
                <p>{{ activeOperation.title }}</p>
                <span>{{ activeOperation.description }}</span>
              </div>
              <el-button size="small" text @click="toggleOperationPanel(activeOperation.key)">
                收起
              </el-button>
            </div>
            <div
              class="operation-body"
              :class="{ 'dowsure-credit-body': activeOperation.key === 'dowsureCreditResult' }"
            >
              <code class="endpoint-chip">{{ activeOperation.endpoint }}</code>
              <el-form label-position="top" class="tight-form">
                <div v-if="shouldShowPspAuthorizationRows" class="psp-status-panel">
                  <div class="psp-status-head">
                    <span>店铺授权状态</span>
                    <el-button size="small" text :loading="loadingPspAuthorizationRows" @click="loadPspAuthorizationRows">
                      刷新
                    </el-button>
                  </div>
                  <div class="psp-status-table">
                    <div class="psp-status-row psp-status-header">
                      <span>merchant_account_id</span>
                      <span>SP authorization_id</span>
                      <span>SP 状态</span>
                      <span>3P 状态</span>
                      <span>PSP 状态</span>
                      <span>选择</span>
                    </div>
                    <div v-if="!loadingPspAuthorizationRows && pspAuthorizationRows.length === 0" class="psp-status-empty">
                      暂无店铺授权记录。
                    </div>
                    <div
                      v-for="row in pspAuthorizationRows"
                      :key="row.merchant_account_id"
                      class="psp-status-row"
                      :class="{ selected: row.merchant_account_id === selectedPspMerchantAccountId }"
                    >
                      <strong>{{ row.merchant_account_id || '-' }}</strong>
                      <strong>{{ row.sp_authorization_id || '-' }}</strong>
                      <span>{{ row.sp_status || '-' }}</span>
                      <span>{{ row.three_pl_status || '-' }}</span>
                      <span>{{ row.psp_status || '-' }}</span>
                      <el-button
                        size="small"
                        :type="row.merchant_account_id === selectedPspMerchantAccountId ? 'primary' : 'default'"
                        :disabled="!isPspRowSelectable(row)"
                        @click="selectPspAuthorizationRow(row)"
                      >
                        {{ row.merchant_account_id === selectedPspMerchantAccountId ? '已选中' : '选择' }}
                      </el-button>
                    </div>
                  </div>
                </div>

                <div v-if="shouldShowLimitApplications" class="limit-applications-panel">
                  <div class="psp-status-head">
                    <span>核保单</span>
                    <el-button size="small" text :loading="loadingLimitApplications" @click="loadLimitApplications">
                      刷新
                    </el-button>
                  </div>
                  <div class="limit-applications-table">
                    <div class="limit-applications-row limit-applications-header">
                      <span>limit_application_unique_id</span>
                      <span>status</span>
                      <span>created_at</span>
                      <span>选择</span>
                    </div>
                    <div v-if="!loadingLimitApplications && limitApplicationRows.length === 0" class="psp-status-empty">
                      暂无核保单记录，默认执行时会使用最新核保单。
                    </div>
                    <div
                      v-for="row in limitApplicationRows"
                      :key="row.limit_application_unique_id"
                      class="limit-applications-row"
                      :class="{ selected: row.limit_application_unique_id === selectedLimitApplicationUniqueId }"
                    >
                      <strong>{{ row.limit_application_unique_id || '-' }}</strong>
                      <span>{{ row.status || '-' }}</span>
                      <span>{{ row.created_at || '-' }}</span>
                      <el-button
                        size="small"
                        :type="row.limit_application_unique_id === selectedLimitApplicationUniqueId ? 'primary' : 'default'"
                        @click="selectLimitApplicationRow(row)"
                      >
                        {{ row.limit_application_unique_id === selectedLimitApplicationUniqueId ? '已选中' : '选择' }}
                      </el-button>
                    </div>
                  </div>
                </div>

                <div v-if="shouldShowDrawdownRepaymentRows" class="drawdown-repayment-panel">
                  <div class="psp-status-head">
                    <span>还款单</span>
                    <el-button size="small" text :loading="loadingDrawdownRepaymentRows" @click="loadDrawdownRepaymentRows">
                      刷新
                    </el-button>
                  </div>
                  <div class="drawdown-repayment-table">
                    <div class="drawdown-repayment-row drawdown-repayment-header">
                      <span>lender_loan_id</span>
                      <span>{{ activeOperation.key === 'cgbRepaymentResult' ? 'CGB loanCode（lender_drawdown_id）' : 'WEBANK loanCode' }}</span>
                      <span>total_interest_rate</span>
                      <span>outstanding_amount</span>
                      <span>repayment_status</span>
                      <span>选择</span>
                    </div>
                    <div v-if="!loadingDrawdownRepaymentRows && drawdownRepaymentRows.length === 0" class="psp-status-empty">
                      暂无还款单记录，默认执行时会使用最新 dpu_drawdown 记录。
                    </div>
                    <div
                      v-for="row in drawdownRepaymentRows"
                      :key="`${row.lender_loan_id || row.lender_drawdown_id}-${row.lender_drawdown_id || ''}`"
                      class="drawdown-repayment-row"
                      :class="{ selected: repaymentRowSelectionKey(row) === selectedDowsureRepaymentLoanCode }"
                    >
                      <strong>{{ row.lender_loan_id || '-' }}</strong>
                      <span>{{ row.lender_drawdown_id || '-' }}</span>
                      <span>{{ row.total_interest_rate ?? '-' }}</span>
                      <span>{{ row.outstanding_amount ?? '-' }}</span>
                      <span>{{ row.repayment_status || '-' }}</span>
                      <el-button
                        size="small"
                        :type="repaymentRowSelectionKey(row) === selectedDowsureRepaymentLoanCode ? 'primary' : 'default'"
                        @click="selectDrawdownRepaymentRow(row)"
                      >
                        {{ repaymentRowSelectionKey(row) === selectedDowsureRepaymentLoanCode ? '已选中' : '选择' }}
                      </el-button>
                    </div>
                  </div>
                </div>

                <div
                  v-if="activeOperation.key === 'dowsureCreditResult'"
                  class="operation-fields"
                  :class="{ empty: activeOperation.fields.length === 0 }"
                >
                  <template v-if="activeOperation.fields.length">
                    <template v-for="field in activeOperation.fields" :key="`${activeOperation.key}-${field.prop}`">
                      <el-form-item v-if="!field.visible || field.visible(operationForms[activeOperation.key])" :label="field.label">
                        <el-input
                          v-if="field.type === 'text'"
                          v-model="operationForms[activeOperation.key][field.prop]"
                          :placeholder="field.placeholder"
                        />
                        <el-input-number
                          v-else-if="field.type === 'number'"
                          v-model="operationForms[activeOperation.key][field.prop]"
                          :min="field.min"
                          :step="field.step || 1"
                          controls-position="right"
                          class="full-width"
                        />
                        <el-select v-else-if="field.type === 'select'" v-model="operationForms[activeOperation.key][field.prop]">
                          <el-option
                            v-for="option in fieldOptions(field)"
                            :key="`${field.prop}-${option.value}`"
                            :label="option.label"
                            :value="option.value"
                          />
                        </el-select>
                      </el-form-item>
                    </template>
                  </template>
                  <div v-else class="no-params">这个操作不需要额外参数。</div>
                </div>

                <div v-if="shouldShowDowsureMerchantAccounts" class="dowsure-accounts-panel">
                  <div class="psp-status-head">
                    <span>DOWSURE 店铺额度（offerId / sellerId 自动带出）</span>
                    <el-button size="small" text :loading="loadingDowsureMerchantAccounts" @click="loadDowsureMerchantAccounts">
                      刷新
                    </el-button>
                  </div>
                  <div class="dowsure-accounts-table">
                    <div class="dowsure-accounts-row dowsure-accounts-header">
                      <span>offerId</span>
                      <span>sellerId</span>
                      <span>amount</span>
                    </div>
                    <div v-if="!loadingDowsureMerchantAccounts && operationForms.dowsureCreditResult.creditResultList.length === 0" class="psp-status-empty">
                      暂无 DOWSURE 店铺记录。
                    </div>
                    <div
                      v-for="row in operationForms.dowsureCreditResult.creditResultList"
                      :key="row.offerId || row.sellerId"
                      class="dowsure-accounts-row"
                    >
                      <strong>{{ row.offerId || '-' }}</strong>
                      <strong>{{ row.sellerId || '-' }}</strong>
                      <el-input-number
                        v-model="row.amount"
                        :min="0"
                        :step="1000"
                        controls-position="right"
                        class="full-width"
                      />
                    </div>
                  </div>
                </div>

                <div v-if="shouldShowWebankSellerOffers" class="dowsure-accounts-panel">
                  <div class="psp-status-head">
                    <span>WEBANK 店铺额度</span>
                    <el-button size="small" text :loading="loadingWebankSellerOffers" @click="loadWebankSellerOffers">
                      刷新
                    </el-button>
                  </div>
                  <div class="dowsure-accounts-table webank-seller-offers-table">
                    <div class="dowsure-accounts-row dowsure-accounts-header">
                      <span>offer_id</span>
                      <span>seller_id</span>
                      <span>marketplace_country</span>
                      <span>准入状态</span>
                      <span>applySellerBusinessSum</span>
                    </div>
                    <div v-if="!loadingWebankSellerOffers && operationForms.webankCreditResult.seller_offers.length === 0" class="psp-status-empty">
                      暂无 WEBANK 店铺记录。
                    </div>
                    <div
                      v-for="row in operationForms.webankCreditResult.seller_offers"
                      :key="row.offer_id || row.seller_id"
                      class="dowsure-accounts-row"
                    >
                      <strong>{{ row.offer_id || '-' }}</strong>
                      <strong>{{ row.seller_id || '-' }}</strong>
                      <span>{{ row.marketplace_country || '-' }}</span>
                      <el-select v-model="row.admissionStatus" class="full-width">
                        <el-option label="准入" value="ADMITTED" />
                        <el-option label="不准入" value="NOT_ADMITTED" />
                      </el-select>
                      <el-input-number
                        v-model="row.applySellerBusinessSum"
                        :min="0"
                        :step="1000"
                        controls-position="right"
                        class="full-width"
                      />
                    </div>
                  </div>
                </div>

                <div
                  v-if="activeOperation.key !== 'dowsureCreditResult'"
                  class="operation-fields"
                  :class="{ empty: activeOperation.fields.length === 0 }"
                >
                  <template v-if="activeOperation.fields.length">
                    <template v-for="field in activeOperation.fields" :key="`${activeOperation.key}-${field.prop}`">
                      <el-form-item v-if="!field.visible || field.visible(operationForms[activeOperation.key])" :label="field.label">
                        <el-input
                          v-if="field.type === 'text'"
                          v-model="operationForms[activeOperation.key][field.prop]"
                          :placeholder="field.placeholder"
                        />
                        <el-input-number
                          v-else-if="field.type === 'number'"
                          v-model="operationForms[activeOperation.key][field.prop]"
                          :min="field.min"
                          :step="field.step || 1"
                          controls-position="right"
                          class="full-width"
                        />
                        <el-select v-else-if="field.type === 'select'" v-model="operationForms[activeOperation.key][field.prop]">
                          <el-option
                            v-for="option in fieldOptions(field)"
                            :key="`${field.prop}-${option.value}`"
                            :label="option.label"
                            :value="option.value"
                          />
                        </el-select>
                      </el-form-item>
                    </template>
                  </template>
                  <div v-else class="no-params">这个操作不需要额外参数。</div>
                </div>

                <el-button
                  class="operation-run-button"
                  type="primary"
                  :disabled="!activeSessionId || isOperationDisabled(activeOperation)"
                  :loading="runningOperationKey === activeOperation.key"
                  :title="isOperationDisabled(activeOperation) ? operationDisabledReason(activeOperation) : ''"
                  @click="handleOperationRun(activeOperation)"
                >
                  执行 {{ activeOperation.title }}
                </el-button>
              </el-form>

              <div
                v-if="operationResults[activeOperation.key]"
                class="result-strip"
                :class="{ 'result-strip-error': operationResults[activeOperation.key]?.success === false }"
              >
                <span class="result-title">最近一次执行结果</span>
                <pre>{{ JSON.stringify(operationResults[activeOperation.key], null, 2) }}</pre>
              </div>
            </div>
          </div>
            </template>
          </div>
      </el-card>
    </section>

    </template>

    <el-drawer
      v-model="scenarioHistoryDetailVisible"
      size="58%"
      class="scenario-history-drawer"
      title="执行详情"
    >
      <section v-if="selectedScenarioHistoryRecord" class="scenario-history-detail">
        <div class="scenario-detail-header">
          <div>
            <span>场景</span>
            <strong>{{ selectedScenarioHistoryRecord.scenario }}</strong>
          </div>
          <div>
            <span>状态</span>
            <el-tag :type="selectedScenarioHistoryRecord.status === '完成' ? 'success' : selectedScenarioHistoryRecord.status === '未执行' ? 'warning' : 'danger'" effect="plain">
              {{ selectedScenarioHistoryRecord.status }}
            </el-tag>
          </div>
          <div>
            <span>环境</span>
            <strong>{{ selectedScenarioHistoryRecord.env }}</strong>
          </div>
          <div>
            <span>耗时</span>
            <strong>{{ selectedScenarioHistoryRecord.duration }}</strong>
          </div>
          <div class="scenario-detail-mode-switch">
            <span>内容</span>
            <div class="scenario-detail-mode-buttons">
              <button
                type="button"
                :class="{ active: scenarioHistoryDetailPayloadMode === 'mock' }"
                @click="scenarioHistoryDetailPayloadMode = 'mock'"
              >Mock</button>
              <button
                type="button"
                :class="{ active: scenarioHistoryDetailPayloadMode === 'actual' }"
                @click="scenarioHistoryDetailPayloadMode = 'actual'"
              >实际</button>
            </div>
          </div>
        </div>

        <div
          class="scenario-detail-summary"
          :class="`is-${scenarioHistoryRecordOutcome(selectedScenarioHistoryRecord).variant}`"
        >
          <div class="scenario-detail-summary-head">
            <el-tag
              :type="scenarioHistoryRecordOutcome(selectedScenarioHistoryRecord).tagType"
              effect="dark"
            >{{ scenarioHistoryRecordOutcome(selectedScenarioHistoryRecord).headline }}</el-tag>
            <span class="scenario-detail-summary-counts">
              成功 {{ selectedScenarioHistoryRecord.success || 0 }} · 跳过 {{ selectedScenarioHistoryRecord.skipped || 0 }} · 失败 {{ selectedScenarioHistoryRecord.failed || 0 }}
            </span>
          </div>
          <p class="scenario-detail-summary-body">{{ scenarioHistoryRecordOutcome(selectedScenarioHistoryRecord).body }}</p>
          <ul
            v-if="scenarioHistoryRecordOutcome(selectedScenarioHistoryRecord).failures.length"
            class="scenario-detail-summary-failures"
          >
            <li
              v-for="(item, idx) in scenarioHistoryRecordOutcome(selectedScenarioHistoryRecord).failures"
              :key="`scenario-history-failure-${idx}`"
            >
              <strong>{{ item.title }}</strong>
              <span>{{ item.message }}</span>
            </li>
          </ul>
        </div>

        <div v-if="selectedScenarioHistoryRecord.context" class="scenario-detail-context">
          <div><span>手机号</span><strong>{{ selectedScenarioHistoryRecord.context.phone_number || '-' }}</strong></div>
          <div><span>Merchant ID</span><strong>{{ selectedScenarioHistoryRecord.context.merchant_id || '-' }}</strong></div>
          <div><span>Application Unique ID</span><strong>{{ selectedScenarioHistoryRecord.context.application_unique_id || '-' }}</strong></div>
        </div>

        <div class="scenario-detail-step-list">
          <article
            v-for="step in selectedScenarioHistoryRecord.steps || []"
            :key="`${selectedScenarioHistoryRecord.id}-${step.key}`"
            class="scenario-detail-step"
          >
            <div class="scenario-detail-step-head">
              <span class="step-index">{{ step.order }}</span>
              <el-tag
                size="small"
                :type="step.status === 'success' ? 'success' : step.status === 'skipped' ? 'info' : step.status === 'idle' ? 'warning' : 'danger'"
                effect="plain"
              >
                {{ step.status === 'success' ? '成功' : step.status === 'skipped' ? '跳过' : step.status === 'idle' ? '未执行' : '失败' }}
              </el-tag>
              <strong>{{ step.title }}</strong>
              <code>{{ step.endpoint }}</code>
            </div>
            <p v-if="step.error_message" class="scenario-detail-error">{{ step.error_message }}</p>
            <div class="scenario-detail-payload-grid">
              <div class="response-block">
                <div class="response-block-head">
                  <strong>{{ scenarioHistoryDetailPayloadMode === 'actual' ? '实际 Request' : 'Mock Request' }}</strong>
                  <el-tag size="small" effect="plain">
                    {{ scenarioHistoryDetailPayloadMode === 'actual'
                      ? `${getScenarioHistoryStepActualRequests(step).length || 0} 个上游请求`
                      : (step.method || 'POST') }}
                  </el-tag>
                </div>
                <pre v-if="getScenarioHistoryStepDisplayRequest(step)">{{ JSON.stringify(getScenarioHistoryStepDisplayRequest(step), null, 2) }}</pre>
                <div v-else class="response-empty">该步骤没有记录到实际上游请求。</div>
              </div>
              <div class="response-block">
                <div class="response-block-head">
                  <strong>{{ scenarioHistoryDetailPayloadMode === 'actual' ? '实际 Response' : 'Mock Response' }}</strong>
                  <el-tag size="small" effect="plain">
                    {{ scenarioHistoryDetailPayloadMode === 'actual'
                      ? `${getScenarioHistoryStepActualResponses(step).length || 0} 个上游响应`
                      : step.status }}
                  </el-tag>
                </div>
                <pre v-if="getScenarioHistoryStepDisplayResponse(step)">{{ JSON.stringify(getScenarioHistoryStepDisplayResponse(step), null, 2) }}</pre>
                <div v-else class="response-empty">该步骤没有记录到实际上游响应。</div>
              </div>
            </div>
          </article>
        </div>
      </section>
    </el-drawer>
  </div>
</template>


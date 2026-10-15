export const aiUiEnvironmentOptions = [
  { value: 'sit', label: 'SIT', url: 'https://expressfinance-dpu-sit.dowsure.com/en/' },
  { value: 'dev', label: 'DEV', url: 'https://expressfinance-dpu-dev.dowsure.com/en/sign-up-step1' },
  { value: 'uat', label: 'UAT', url: 'https://expressfinance-uat.business.hsbc.com/zh-Hans/' },
  { value: 'preprod', label: 'PREPROD', url: 'https://expressfinance-preprod.business.hsbc.com/zh-Hans/sign-up' },
  { value: 'reg', label: 'REG', url: 'https://expressfinance-dpu-reg.dowsure.com/en/' },
  { value: 'custom', label: '自定义', url: '' },
]

export function aiUiEnvironmentLabel(environment) {
  return aiUiEnvironmentOptions.find((item) => item.value === environment)?.label || '自定义'
}

export function inferAiUiEnvironment(url) {
  const normalizedUrl = String(url || '').trim().replace(/\/+$/, '')
  return aiUiEnvironmentOptions.find((item) => item.url && item.url.replace(/\/+$/, '') === normalizedUrl)?.value || 'custom'
}

export function aiUiEnvironmentUrl(environment) {
  return aiUiEnvironmentOptions.find((item) => item.value === environment)?.url || ''
}

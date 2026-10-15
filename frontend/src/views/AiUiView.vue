<script setup>
import { Plus, Refresh } from '@element-plus/icons-vue'
import PageHeader from '../components/PageHeader.vue'
import {
  aiUiEnvironmentLabel,
  aiUiEnvironmentOptions,
  aiUiEnvironmentUrl,
  inferAiUiEnvironment,
} from '../utils/aiUiEnvironments.js'

const PAGE_MODES = [
  { key: 'cases', label: '案例' },
  { key: 'reports', label: '报告' },
]
const RUN_STATUS = {
  passed: { label: '通过', type: 'success' },
  failed: { label: '失败', type: 'danger' },
  running: { label: '执行中', type: 'warning' },
}

defineProps({
  cases: { type: Array, default: () => [] },
  runs: { type: Array, default: () => [] },
  runtime: { type: Object, default: null },
  loading: { type: Boolean, default: false },
  saving: { type: Boolean, default: false },
  generating: { type: Boolean, default: false },
  error: { type: String, default: '' },
  selectedCaseId: { type: [String, Number], default: '' },
  activeRunId: { type: [String, Number], default: '' },
  pendingCase: { type: Object, default: null },
  username: { type: String, default: '' },
})

const form = defineModel('form', { type: Object, required: true })
const pageMode = defineModel('pageMode', { type: String, default: 'cases' })
const naturalLanguage = defineModel('naturalLanguage', { type: String, default: '' })
const structuredYaml = defineModel('structuredYaml', { type: String, default: '' })
const variablesText = defineModel('variablesText', { type: String, default: '{}' })
const confirmVisible = defineModel('confirmVisible', { type: Boolean, default: false })

const emit = defineEmits([
  'back', 'refresh', 'new-case', 'edit-case', 'run', 'generate', 'save', 'remove', 'stop', 'confirm-run',
])

function switchMode(mode) {
  pageMode.value = mode === 'reports' ? 'reports' : 'cases'
  if (pageMode.value === 'reports') emit('refresh')
}

function handleEnvironmentChange(environment) {
  form.value.url = aiUiEnvironmentUrl(environment)
}

function runStatus(status) {
  return RUN_STATUS[status] || { label: '已停止', type: 'info' }
}

function openReport(path) {
  if (!path) return
  window.open(path, '_blank', 'noopener,noreferrer')
}

function withUser(path, username) {
  return `${path}?username=${encodeURIComponent(username)}`
}
</script>

<template>
  <section class="tool-page-view ai-ui-view">
    <PageHeader
      class="ai-ui-page-head"
      eyebrow="Midscene.js"
      title="AI UI 自动化"
      description="用自然语言描述页面动作和视觉断言，独立执行浏览器 UI 测试。"
      @back="emit('back')"
    >
      <template #actions>
        <div class="ai-ui-head-actions">
          <div class="ai-ui-page-switch" role="tablist" aria-label="AI UI 页面切换">
            <button
              v-for="mode in PAGE_MODES"
              :key="mode.key"
              type="button"
              role="tab"
              :aria-selected="pageMode === mode.key"
              :class="{ active: pageMode === mode.key }"
              @click="switchMode(mode.key)"
            >{{ mode.label }}</button>
          </div>
          <el-tag :type="runtime?.dependencies && runtime?.configured ? 'success' : 'warning'" effect="plain">
            {{ runtime?.dependencies && runtime?.configured ? '运行环境就绪' : '需要配置运行环境' }}
          </el-tag>
          <el-button plain :icon="Refresh" :loading="loading" @click="emit('refresh')">刷新</el-button>
        </div>
      </template>
    </PageHeader>

    <div v-if="error" class="ai-ui-error">{{ error }}</div>

    <div v-if="pageMode === 'cases'" class="ai-ui-layout">
      <aside class="ai-ui-case-list surface-card">
        <div class="ai-ui-section-head">
          <div><strong>用例</strong><span>{{ cases.length }} 条</span></div>
          <el-button type="primary" plain :icon="Plus" @click="emit('new-case')">新建</el-button>
        </div>
        <div v-if="!cases.length" class="ai-ui-empty">还没有 AI UI 用例，先创建一个页面冒烟用例。</div>
        <button
          v-for="item in cases"
          :key="item.id"
          type="button"
          class="ai-ui-case-item"
          :class="{ active: item.id === selectedCaseId }"
          :aria-pressed="item.id === selectedCaseId"
          @click="emit('edit-case', item)"
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
            <strong>{{ form.id ? '编辑 UI 用例' : '新建 UI 用例' }}</strong>
            <span>步骤使用 Midscene Gherkin：Given / When / Then / And</span>
          </div>
          <div class="ai-ui-editor-actions">
            <el-button
              type="success"
              plain
              :disabled="!form.id || Boolean(activeRunId)"
              @click="emit('run')"
            >执行</el-button>
          </div>
        </div>
        <section class="ai-ui-generator">
          <div class="ai-ui-generator-head">
            <div>
              <strong>自然语言生成结构化用例</strong>
              <span>先描述场景，生成后可继续编辑，再保存执行。</span>
            </div>
            <el-button type="primary" plain :loading="generating" @click="emit('generate')">生成 YAML</el-button>
          </div>
          <el-input
            v-model="naturalLanguage"
            type="textarea"
            :rows="3"
            aria-label="自然语言场景描述"
            placeholder="例如：UAT 手机号注册进入安全设置页，填写密码，选择第一个安全问题并输入 test，不要提交。"
          />
        </section>
        <el-form label-position="top" class="ai-ui-form">
          <el-form-item label="用例名称">
            <el-input v-model.trim="form.name" maxlength="200" />
          </el-form-item>
          <el-form-item label="运行环境">
            <el-select
              v-model="form.environment"
              aria-label="AI UI 运行环境"
              @change="handleEnvironmentChange"
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
              v-model.trim="form.url"
              :disabled="form.environment !== 'custom'"
              placeholder="https://uat.example.com 或 http://127.0.0.1:8000"
            />
          </el-form-item>
          <el-form-item label="测试上下文">
            <el-input v-model="form.context" type="textarea" :rows="3" placeholder="补充业务背景、页面规则和不应点击的区域。" />
          </el-form-item>
          <el-form-item label="自然语言步骤">
            <el-input v-model="form.prompt" type="textarea" :rows="14" class="ai-ui-prompt-input" />
          </el-form-item>
          <div class="ai-ui-structured-grid">
            <el-form-item label="结构化 YAML（生成预览）">
              <el-input v-model="structuredYaml" type="textarea" :rows="10" class="ai-ui-prompt-input" />
            </el-form-item>
            <el-form-item label="变量 JSON">
              <el-input v-model="variablesText" type="textarea" :rows="10" class="ai-ui-prompt-input" />
            </el-form-item>
          </div>
          <div class="ai-ui-options">
            <el-form-item label="浏览器">
              <el-switch v-model="form.headed" active-text="显示浏览器" inactive-text="无头执行" />
            </el-form-item>
            <el-form-item label="视口宽度">
              <el-input-number v-model="form.viewport.width" :min="800" :max="2560" />
            </el-form-item>
            <el-form-item label="视口高度">
              <el-input-number v-model="form.viewport.height" :min="600" :max="1600" />
            </el-form-item>
          </div>
        </el-form>
        <div class="ai-ui-footer-actions">
          <div class="ai-ui-footer-action-buttons">
            <el-button type="primary" plain :loading="saving" @click="emit('save')">保存用例</el-button>
            <el-button v-if="form.id" type="danger" plain @click="emit('remove', form)">删除用例</el-button>
          </div>
          <span>执行结果会保留在“报告”页的历史中，Midscene 会生成 HTML 报告。</span>
        </div>
      </main>
    </div>

    <section v-else class="ai-ui-report-page surface-card">
      <div class="ai-ui-report-head">
        <div>
          <strong>执行历史</strong>
          <span>查看 AI UI 案例的最近执行状态与 Midscene 报告。</span>
        </div>
        <el-button plain :icon="Refresh" :loading="loading" @click="emit('refresh')">刷新历史</el-button>
      </div>
      <div v-if="!runs.length" class="ai-ui-empty">暂无执行历史，先到“案例”页保存并执行一个用例。</div>
      <div v-else class="ai-ui-report-list">
        <article v-for="run in runs" :key="run.id" class="ai-ui-report-row">
          <div class="ai-ui-report-main">
            <div class="ai-ui-report-title">
              <strong>{{ run.case_name }}</strong>
              <el-tag size="small" effect="plain" :type="runStatus(run.status).type">
                {{ runStatus(run.status).label }}
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
            <el-button v-if="run.status === 'running'" size="small" type="warning" plain @click="emit('stop', run)">停止</el-button>
            <el-button
              v-if="run.result?.report_url"
              size="small"
              type="primary"
              plain
              @click="openReport(withUser(run.result.report_url, username))"
            >打开报告</el-button>
            <el-button
              v-if="run.result?.report_url"
              size="small"
              plain
              @click="openReport(withUser(`/api/ai-ui/runs/${encodeURIComponent(run.id)}/sop`, username))"
            >导出 SOP</el-button>
            <el-button size="small" plain @click="switchMode('cases')">查看案例</el-button>
          </div>
        </article>
      </div>
      <div class="ai-ui-runtime">
        <strong>运行环境</strong>
        <span>Node.js：{{ runtime?.node ? '已找到' : '未找到' }}</span>
        <span>Midscene / Playwright：{{ runtime?.dependencies ? '已安装' : '未安装' }}</span>
        <span>视觉模型：{{ runtime?.configured ? '已配置' : '未配置' }}</span>
        <code v-if="runtime && !runtime.dependencies">{{ runtime.install_command }}</code>
      </div>
    </section>

    <el-dialog v-model="confirmVisible" title="执行前确认" width="min(520px, 92vw)" append-to-body>
      <div class="ai-ui-confirm">
        <p>即将执行用例：<strong>{{ pendingCase?.name || '-' }}</strong></p>
        <p>环境：<strong>{{ aiUiEnvironmentLabel(pendingCase?.environment) }}</strong></p>
        <p>目标地址：<code>{{ pendingCase?.url || '-' }}</code></p>
        <p>执行会启动独立 Chromium，并按当前 Gherkin 步骤操作页面。</p>
      </div>
      <template #footer>
        <el-button @click="confirmVisible = false">取消</el-button>
        <el-button type="primary" @click="emit('confirm-run')">确认执行</el-button>
      </template>
    </el-dialog>
  </section>
</template>

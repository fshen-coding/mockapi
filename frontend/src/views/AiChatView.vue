<script setup>
import { Back, Delete, Loading, Top, User } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { renderMarkdown } from '../utils/markdown.js'

defineProps({
  messages: { type: Array, default: () => [] },
  sending: { type: Boolean, default: false },
  error: { type: String, default: '' },
  envOptions: { type: Array, default: () => [] },
  modelOptions: { type: Array, default: () => [] },
  reasoningOptions: { type: Array, default: () => [] },
  quickPrompts: { type: Array, default: () => [] },
  context: { type: Object, default: () => ({}) },
})

const input = defineModel('input', { type: String, default: '' })
const execEnv = defineModel('execEnv', { type: String, default: '' })
const model = defineModel('model', { type: String, default: '' })
const reasoningEffort = defineModel('reasoningEffort', { type: String, default: '' })

const emit = defineEmits(['send', 'clear', 'back'])

async function onBubbleClick(event) {
  const btn = event.target.closest('.chat-code-copy')
  if (!btn) return
  const raw = decodeURIComponent(btn.dataset.code || '')
  try {
    await navigator.clipboard.writeText(raw)
    const original = btn.innerHTML
    btn.textContent = '✓ 已复制'
    btn.disabled = true
    setTimeout(() => { btn.innerHTML = original; btn.disabled = false }, 1800)
  } catch {
    ElMessage({ type: 'warning', message: '复制失败，请手动选择文本', duration: 2000 })
  }
}

function formatJson(value) {
  return JSON.stringify(value, null, 2)
}
</script>

<template>
  <section class="ai-page-view">
    <div class="ai-page-shell">
      <main class="ai-conversation-panel">
        <div class="ai-conversation-head">
          <div>
            <p class="eyebrow">DPU Chat</p>
            <h2>AI 助手</h2>
            <p>像聊天一样提问，也可以直接执行只读 SQL、查询 merchant、分析最近日志和当前 session。</p>
          </div>
          <div class="ai-conversation-actions">
            <el-select v-model="execEnv" class="ai-exec-select" aria-label="AI 执行环境">
              <el-option v-for="env in envOptions" :key="`ai-${env}`" :label="env" :value="env" />
            </el-select>
            <el-tag size="large" :type="sending ? 'warning' : 'success'">{{ sending ? '处理中' : '就绪' }}</el-tag>
            <el-button :icon="Delete" plain @click="emit('clear')">清空对话</el-button>
            <el-button plain :icon="Back" @click="emit('back')">返回控制台</el-button>
          </div>
        </div>

        <div class="ai-context-strip">
          <div><span>Session</span><strong>{{ context.sessionId || '-' }}</strong></div>
          <div><span>环境</span><strong>{{ context.env || '-' }}</strong></div>
          <div><span>手机号</span><strong>{{ context.phoneNumber || '-' }}</strong></div>
          <div><span>Merchant</span><strong>{{ context.merchantId || '-' }}</strong></div>
          <div><span>实时日志</span><strong>{{ context.logStatus || '-' }}</strong></div>
        </div>

        <div v-if="messages.length === 0" class="ai-empty-state">
          <p>可以直接问业务问题，也可以粘贴 SQL。比如“帮我看当前 session 为什么没推进到 eSign”，或者直接输入一条 SELECT。</p>
          <p>助手会带上当前环境、Session、手机号、Merchant 和最近日志上下文；需要切换查询环境时，直接改上方环境选择。</p>
          <div class="ai-prompt-grid">
            <button v-for="prompt in quickPrompts" :key="prompt" type="button" @click="input = prompt">
              {{ prompt }}
            </button>
          </div>
        </div>

        <div class="ai-chat-body ai-page-chat-body" aria-live="polite">
          <template v-for="message in messages" :key="message.id">
            <div v-if="message.role === 'system'" class="chat-model-switch">
              <span class="chat-model-switch-icon" aria-hidden="true">⇌</span>
              <span>{{ message.content }}</span>
            </div>
            <div v-else class="chat-message" :class="message.role">
              <div class="chat-avatar" :class="message.role" :aria-label="message.role === 'user' ? '我' : 'AI 助手'">
                <el-icon v-if="message.role === 'user'"><User /></el-icon>
                <svg v-else viewBox="0 0 24 24" width="20" height="20" fill="currentColor" aria-hidden="true">
                  <path d="M22.282 9.821a5.985 5.985 0 0 0-.516-4.91 6.046 6.046 0 0 0-6.51-2.9A6.065 6.065 0 0 0 4.981 4.18a5.985 5.985 0 0 0-3.998 2.9 6.046 6.046 0 0 0 .743 7.097 5.98 5.98 0 0 0 .51 4.911 6.051 6.051 0 0 0 6.515 2.9A5.985 5.985 0 0 0 13.26 24a6.056 6.056 0 0 0 5.772-4.206 5.99 5.99 0 0 0 3.997-2.9 6.056 6.056 0 0 0-.747-7.073zm-9.022 12.61a4.476 4.476 0 0 1-2.876-1.04l.141-.081 4.779-2.758a.795.795 0 0 0 .392-.681v-6.737l2.02 1.168a.071.071 0 0 1 .038.052v5.583a4.504 4.504 0 0 1-4.494 4.494zM3.6 18.304a4.47 4.47 0 0 1-.535-3.014l.142.085 4.783 2.759a.771.771 0 0 0 .78 0l5.843-3.369v2.332a.08.08 0 0 1-.033.062L9.74 19.95a4.5 4.5 0 0 1-6.14-1.646zM2.34 7.896a4.485 4.485 0 0 1 2.366-1.973V11.6a.766.766 0 0 0 .388.676l5.815 3.355-2.02 1.168a.076.076 0 0 1-.071 0l-4.83-2.786A4.504 4.504 0 0 1 2.34 7.872zm16.597 3.855-5.833-3.387L15.119 7.2a.076.076 0 0 1 .071 0l4.83 2.791a4.494 4.494 0 0 1-.676 8.105v-5.678a.79.79 0 0 0-.407-.667zm2.01-3.023-.141-.085-4.774-2.782a.776.776 0 0 0-.785 0L9.409 9.23V6.897a.066.066 0 0 1 .028-.061l4.83-2.787a4.5 4.5 0 0 1 6.68 4.66zm-12.64 4.135-2.02-1.164a.08.08 0 0 1-.038-.057V6.075a4.5 4.5 0 0 1 7.375-3.453l-.142.08L8.704 5.46a.795.795 0 0 0-.393.681zm1.097-2.365 2.602-1.5 2.607 1.5v2.999l-2.597 1.5-2.607-1.5z"/>
                </svg>
              </div>
              <div class="chat-content">
                <div class="chat-meta">
                  <span>{{ message.at }}</span>
                </div>
                <div class="chat-bubble" v-html="renderMarkdown(message.content)" @click="onBubbleClick"></div>
                <details v-if="message.meta?.rendered" class="chat-detail">
                  <summary>已执行 SQL / 脚本</summary>
                  <pre>{{ message.meta.rendered }}</pre>
                </details>
                <details v-if="message.meta?.execution" class="chat-detail">
                  <summary>模板执行结果</summary>
                  <pre>{{ formatJson(message.meta.execution) }}</pre>
                </details>
                <details v-if="message.meta?.tool_result" class="chat-detail">
                  <summary>工具结果</summary>
                  <pre>{{ formatJson(message.meta.tool_result) }}</pre>
                </details>
              </div>
            </div>
          </template>
        </div>

        <div v-if="error" class="chat-error" role="alert">{{ error }}</div>

        <div class="ai-page-input">
          <div class="ai-composer">
            <el-input
              v-model="input"
              type="textarea"
              :rows="4"
              resize="none"
              aria-label="输入消息"
              placeholder="问 DPU 问题、让它分析日志，或直接输入 SQL，例如：select merchant_id from dpu_users where phone_number='...'"
              @keydown.enter.exact.prevent="emit('send')"
            />
            <div class="ai-composer-toolbar">
              <div class="ai-composer-trailing">
                <el-select v-model="model" size="small" class="ai-composer-select ai-composer-select-model" aria-label="推理模型">
                  <el-option v-for="opt in modelOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
                </el-select>
                <el-select v-model="reasoningEffort" size="small" class="ai-composer-select ai-composer-select-effort" aria-label="思考级别">
                  <el-option v-for="opt in reasoningOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
                </el-select>
                <button
                  type="button"
                  class="ai-composer-send"
                  :class="{ disabled: !input.trim() || sending }"
                  :disabled="!input.trim() || sending"
                  aria-label="发送"
                  @click="emit('send')"
                >
                  <el-icon v-if="sending"><Loading /></el-icon>
                  <el-icon v-else><Top /></el-icon>
                </button>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  </section>
</template>

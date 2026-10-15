<script setup>
import { computed } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import PageHeader from '../components/PageHeader.vue'

const HISTORY_WINDOW = 60

const props = defineProps({
  monitor: { type: Object, default: () => ({ items: [] }) },
  refreshSeconds: { type: Number, default: 60 },
  loading: { type: Boolean, default: false },
  error: { type: String, default: '' },
})

defineEmits(['refresh'])

const items = computed(() => props.monitor?.items || [])

const STATE_LABELS = { ok: '正常', down: '异常', degraded: '波动', checking: '检测中' }
const STATE_TAG_TYPES = { ok: 'success', down: 'danger', degraded: 'warning', checking: 'info' }
const HISTORY_LABELS = { ok: '成功', success: '成功', fail: '失败', failed: '失败', down: '失败', slow: '慢', degraded: '波动' }

function availabilityState(value) {
  if (value === null || value === undefined || value === '') return 'checking'
  const numericValue = Number(value)
  if (!Number.isFinite(numericValue)) return 'checking'
  if (numericValue < 60) return 'down'
  if (numericValue < 80) return 'degraded'
  return 'ok'
}

function availabilityLabel(value) {
  return STATE_LABELS[availabilityState(value)]
}

function availabilityTagType(value) {
  return STATE_TAG_TYPES[availabilityState(value)]
}

function cardState(item) {
  const states = [availabilityState(item?.availability), availabilityState(item?.channel_availability)]
  if (states.includes('down')) return 'down'
  if (states.includes('degraded')) return 'degraded'
  if (states.every((state) => state === 'ok')) return 'operational'
  return 'checking'
}

function historyLabel(status, index) {
  return `第 ${index + 1} 次：${HISTORY_LABELS[status] || status || '未知'}`
}

function hasValue(value) {
  return value !== null && value !== undefined
}
</script>

<template>
  <section class="tool-page-view environment-monitor-view">
    <PageHeader
      eyebrow="Environment Monitor"
      title="环境监测"
      description="网关检测 / 请求测试健康度。"
      :show-back="false"
    >
      <template #actions>
        <div class="environment-monitor-actions">
          <span v-if="monitor.checked_at" class="environment-monitor-time">{{ monitor.checked_at }}</span>
          <el-tag type="info" effect="plain">自动刷新：{{ refreshSeconds }}s</el-tag>
          <el-button :icon="Refresh" plain :loading="loading" @click="$emit('refresh')">刷新</el-button>
        </div>
      </template>
    </PageHeader>

    <el-card shadow="never" class="surface-card environment-monitor-card">
      <p v-if="error" class="login-error">{{ error }}</p>
      <div class="environment-monitor-grid">
        <article
          v-for="item in items"
          :key="item.env"
          class="environment-card"
          :class="cardState(item)"
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
              <strong>{{ item.availability ?? '--' }}<small v-if="hasValue(item.availability)">%</small></strong>
            </div>
            <div class="environment-history" :class="{ empty: !item.history?.length }" role="list" aria-label="最近请求记录">
              <template v-if="item.history?.length">
                <i
                  v-for="(status, index) in item.history"
                  :key="`${item.env}-gateway-${index}`"
                  :class="status"
                  role="listitem"
                  :title="historyLabel(status, index)"
                  :aria-label="historyLabel(status, index)"
                ></i>
              </template>
              <span v-else>暂无历史请求样本</span>
            </div>
            <div class="environment-card-foot">
              <span>最近 {{ item.sample_count || 0 }}/{{ HISTORY_WINDOW }} 次请求</span>
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
              <strong>{{ item.channel_availability ?? '--' }}<small v-if="hasValue(item.channel_availability)">%</small></strong>
            </div>
            <div class="environment-history channel" :class="{ empty: !item.channel_history?.length }" role="list" aria-label="最近 send-sms 自动测试记录">
              <template v-if="item.channel_history?.length">
                <i
                  v-for="(status, index) in item.channel_history"
                  :key="`${item.env}-channel-${index}`"
                  :class="status"
                  role="listitem"
                  :title="historyLabel(status, index)"
                  :aria-label="historyLabel(status, index)"
                ></i>
              </template>
              <span v-else>等待半小时自动测试样本</span>
            </div>
            <div class="environment-card-foot">
              <span>最近 {{ item.channel_sample_count || 0 }}/{{ HISTORY_WINDOW }} 次测试</span>
              <span>{{ item.channel_checked_at || '启动后自动执行' }}</span>
            </div>
          </section>
        </article>
      </div>
    </el-card>
  </section>
</template>

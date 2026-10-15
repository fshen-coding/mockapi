<script setup>
import { ref, watch } from 'vue'
import { ArrowDown, ArrowRight, Clock, Refresh, Search } from '@element-plus/icons-vue'
import PageHeader from '../components/PageHeader.vue'

const props = defineProps({
  operations: { type: Array, default: () => [] },
  stats: { type: Array, default: () => [] },
  isAdmin: { type: Boolean, default: false },
  loading: { type: Boolean, default: false },
  error: { type: String, default: '' },
})

const query = defineModel('query', { type: Object, required: true })

const emit = defineEmits(['refresh', 'reset'])

const expandedIds = ref(new Set())

watch(() => props.operations, () => {
  expandedIds.value = new Set()
})

function isExpanded(id) {
  return expandedIds.value.has(String(id))
}

function toggleDetail(id) {
  const key = String(id)
  const next = new Set(expandedIds.value)
  if (next.has(key)) {
    next.delete(key)
  } else {
    next.add(key)
  }
  expandedIds.value = next
}

function formatJsonBlock(payload) {
  return JSON.stringify(payload ?? {}, null, 2)
}
</script>

<template>
  <section class="tool-page-view activity-page-view">
    <PageHeader
      eyebrow="Usage Log"
      title="使用日志"
      :description="isAdmin ? '管理员可查看所有人的历史操作记录。' : '当前账号的历史 mock 操作记录，可按手机号或 Session ID 过滤。'"
      :show-back="false"
    >
      <template #actions>
        <el-button :icon="Refresh" plain :loading="loading" @click="emit('refresh')">刷新</el-button>
      </template>
    </PageHeader>

    <el-card shadow="never" class="surface-card activity-page-card">
      <div class="usage-log-stats">
        <article v-for="stat in stats" :key="stat.label" class="usage-log-stat">
          <span>{{ stat.label }}</span>
          <strong>{{ stat.value }}</strong>
          <small>{{ stat.hint }}</small>
        </article>
      </div>

      <el-form class="audit-query-form" :inline="true" @submit.prevent="emit('refresh')">
        <el-form-item label="手机号">
          <el-input
            v-model.trim="query.phone_number"
            placeholder="8 位或 11 位手机号"
            clearable
            @keydown.enter.prevent="emit('refresh')"
          />
        </el-form-item>
        <el-form-item label="Session ID">
          <el-input
            v-model.trim="query.session_id"
            placeholder="UUID"
            clearable
            @keydown.enter.prevent="emit('refresh')"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :icon="Search" :loading="loading" @click="emit('refresh')">
            查询
          </el-button>
          <el-button :icon="Refresh" plain @click="emit('reset')">重置</el-button>
        </el-form-item>
      </el-form>

      <p v-if="error" class="login-error">{{ error }}</p>

      <div class="activity-list">
        <div v-if="!loading && operations.length === 0" class="session-empty">
          <span class="session-empty__icon">
            <el-icon><Clock /></el-icon>
          </span>
          <p class="session-empty__title">还没有操作记录</p>
          <p class="session-empty__hint">登录、连接 session、执行 mock 等操作后会在这里出现。</p>
        </div>
        <div v-for="item in operations" :key="item.id" class="activity-item">
          <div class="activity-summary-row">
            <span
              class="activity-status-line"
              :class="{
                success: item.success === true,
                failed: item.success === false,
              }"
              aria-hidden="true"
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
              :icon="isExpanded(item.id) ? ArrowDown : ArrowRight"
              :aria-expanded="isExpanded(item.id)"
              @click="toggleDetail(item.id)"
            >
              {{ isExpanded(item.id) ? '收起详情' : '详情' }}
            </el-button>
          </div>
          <div v-if="isExpanded(item.id)" class="activity-detail-panel">
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
</template>

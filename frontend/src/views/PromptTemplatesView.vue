<script setup>
import { computed, ref, watch } from 'vue'
import { Delete, Document, DocumentCopy, Plus, Promotion, Refresh, Search, SwitchButton, Tickets } from '@element-plus/icons-vue'
import PageHeader from '../components/PageHeader.vue'

const PAGE_SIZE = 6
const LOGIC_TAG_TYPES = { sql: 'success', http: 'warning' }

const props = defineProps({
  templates: { type: Array, default: () => [] },
  isAdmin: { type: Boolean, default: false },
  loading: { type: Boolean, default: false },
  error: { type: String, default: '' },
})

const emit = defineEmits(['refresh', 'create', 'edit', 'use', 'toggle', 'remove', 'send-to-ai'])

const search = ref('')
const page = ref(1)

const filteredTemplates = computed(() => {
  const keyword = search.value.trim().toLowerCase()
  if (!keyword) return props.templates
  return props.templates.filter((item) => (
    (item.title || '').toLowerCase().includes(keyword)
    || (item.description || '').toLowerCase().includes(keyword)
  ))
})
const total = computed(() => filteredTemplates.value.length)
const pagedTemplates = computed(() => {
  const start = (page.value - 1) * PAGE_SIZE
  return filteredTemplates.value.slice(start, start + PAGE_SIZE)
})

watch(search, () => { page.value = 1 })
// 删到只剩前几页时，把越界的页码收回来。
watch(total, (value) => {
  const maxPage = Math.max(1, Math.ceil(value / PAGE_SIZE))
  if (page.value > maxPage) page.value = maxPage
})

function logicTagType(logicType) {
  return LOGIC_TAG_TYPES[logicType] || 'info'
}
</script>

<template>
  <section class="tool-page-view prompt-templates-view">
    <PageHeader
      eyebrow="Prompt Templates"
      title="提示词模板"
      :description="isAdmin
        ? '维护可执行的 SQL / HTTP / Python 模板，用户在 AI 助手描述需求后会自动填参并执行。'
        : 'admin 预设的可执行模板，描述你的需求，AI 会自动填参并执行对应 SQL / HTTP / Python。'"
      :show-back="false"
    >
      <template #actions>
        <div class="prompt-templates-head-actions">
          <el-input
            v-model="search"
            class="prompt-templates-search"
            placeholder="按名称/描述搜索模板"
            aria-label="搜索模板"
            clearable
            :prefix-icon="Search"
          />
          <el-button :icon="Refresh" plain :loading="loading" @click="emit('refresh')">刷新</el-button>
          <el-button v-if="isAdmin" type="primary" :icon="Plus" @click="emit('create')">新建模板</el-button>
        </div>
      </template>
    </PageHeader>

    <p v-if="error" class="login-error page-error">{{ error }}</p>

    <div v-if="!loading && templates.length === 0" class="session-empty">
      <span class="session-empty__icon"><el-icon><Tickets /></el-icon></span>
      <p class="session-empty__title">还没有模板</p>
      <p class="session-empty__hint">
        {{ isAdmin ? '点击右上角「新建模板」开始维护可执行脚本。' : '请联系管理员先创建提示词模板。' }}
      </p>
    </div>

    <div v-else-if="!loading && total === 0" class="session-empty">
      <span class="session-empty__icon"><el-icon><Search /></el-icon></span>
      <p class="session-empty__title">没有匹配的模板</p>
      <p class="session-empty__hint">换个关键词，或清空搜索框查看全部。</p>
    </div>

    <div v-else-if="total > 0" class="prompt-templates-grid">
      <article
        v-for="template in pagedTemplates"
        :key="template.id"
        class="prompt-template-card"
        :class="{ 'is-disabled': template.is_disabled }"
      >
        <header class="prompt-template-card__head">
          <div>
            <div class="prompt-template-card__tags">
              <el-tag size="small" effect="dark" :type="logicTagType(template.logic_type)">
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
                @click="emit('send-to-ai', template)"
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
            @click="emit('use', template)"
          >使用</el-button>
          <template v-if="isAdmin">
            <el-button plain :icon="Document" @click="emit('edit', template)">编辑</el-button>
            <el-button
              plain
              :type="template.is_disabled ? 'success' : 'warning'"
              :icon="SwitchButton"
              @click="emit('toggle', template)"
            >{{ template.is_disabled ? '启用' : '禁用' }}</el-button>
            <el-button plain type="danger" :icon="Delete" @click="emit('remove', template)">删除</el-button>
          </template>
        </footer>
      </article>
    </div>

    <div v-if="total > PAGE_SIZE" class="prompt-templates-pagination">
      <el-pagination
        v-model:current-page="page"
        layout="prev, pager, next, total"
        background
        :total="total"
        :page-size="PAGE_SIZE"
      />
    </div>
  </section>
</template>

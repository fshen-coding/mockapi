<script setup>
import { computed } from 'vue'
import { Position } from '@element-plus/icons-vue'
import PageHeader from '../components/PageHeader.vue'

const props = defineProps({
  issues: { type: Array, default: () => [] },
  env: { type: String, default: '' },
  phoneNumber: { type: String, default: '' },
  sessionId: { type: String, default: '' },
})

const issueText = defineModel('issueText', { type: String, default: '' })

defineEmits(['back', 'submit'])

const pendingCount = computed(() => props.issues.filter((item) => item.status !== '已回复').length)
const repliedCount = computed(() => props.issues.filter((item) => item.status === '已回复').length)
</script>

<template>
  <section class="tool-page-view contact-page-view">
    <PageHeader
      eyebrow="Ask Us"
      title="联系我们"
      description="把问题现场、期望结果和关键信息整理清楚，管理员会统一处理。"
      @back="$emit('back')"
    />

    <div class="contact-overview-grid">
      <div class="contact-stat-card">
        <span>问题总数</span>
        <strong>{{ issues.length }}</strong>
        <p>当前浏览器已记录的问题总量</p>
      </div>
      <div class="contact-stat-card">
        <span>待回复</span>
        <strong>{{ pendingCount }}</strong>
        <p>需要管理员继续处理的问题</p>
      </div>
      <div class="contact-stat-card">
        <span>已回复</span>
        <strong>{{ repliedCount }}</strong>
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
          <div><span>环境</span><strong>{{ env || '-' }}</strong></div>
          <div><span>手机号</span><strong>{{ phoneNumber || '-' }}</strong></div>
          <div><span>Session</span><strong>{{ sessionId || '-' }}</strong></div>
        </div>

        <el-form label-position="top" class="tight-form contact-question-form">
          <el-form-item label="问题描述">
            <el-input
              v-model="issueText"
              type="textarea"
              :rows="8"
              placeholder="例如：reg 环境下已执行审批和 PSP started，但没有推进到 eSign。期望继续到签约完成。手机号 / session / 报错如下..."
            />
          </el-form-item>
          <el-button type="primary" :icon="Position" @click="$emit('submit')">提交问题</el-button>
        </el-form>
      </el-card>

      <el-card shadow="never" class="surface-card contact-admin-card">
        <template #header>
          <div class="card-head">
            <div class="head-copy">
              <h3>问题记录</h3>
              <p>按最新提交时间倒序展示，已回复内容会保留在对应问题下方。</p>
            </div>
            <el-tag type="info" effect="plain">{{ issues.length }} 条</el-tag>
          </div>
        </template>

        <section class="contact-issue-list">
          <div v-if="issues.length === 0" class="contact-empty">还没有提交的问题。</div>
          <article v-for="item in issues" :key="item.id" class="contact-issue-item">
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
</template>

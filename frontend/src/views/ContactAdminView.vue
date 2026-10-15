<script setup>
import { ChatLineRound, Delete } from '@element-plus/icons-vue'
import PageHeader from '../components/PageHeader.vue'

defineProps({
  issues: { type: Array, default: () => [] },
  operatorName: { type: String, default: '' },
  error: { type: String, default: '' },
})

const replyText = defineModel('replyText', { type: String, default: '' })

defineEmits(['back', 'delete', 'reply'])
</script>

<template>
  <section class="tool-page-view contact-admin-view">
    <PageHeader
      eyebrow="Admin"
      title="回复问题"
      description="管理员在这里统一回复“联系我们”提交的问题。"
      @back="$emit('back')"
    />

    <div class="contact-admin-grid contact-admin-grid-stack">
      <el-card shadow="never" class="surface-card contact-admin-card">
        <template #header>
          <div class="card-head">
            <div class="head-copy">
              <h3>待处理问题</h3>
              <p>这里只显示未回复的问题；回复后会回显到“联系我们”的问题记录里。</p>
            </div>
            <el-tag type="info" effect="plain">{{ issues.length }} 条</el-tag>
          </div>
        </template>

        <section class="contact-issue-list contact-issue-list-admin">
          <div v-if="issues.length === 0" class="contact-empty">暂无待处理问题。</div>
          <article v-for="item in issues" :key="item.id" class="contact-issue-item">
            <div class="contact-issue-head">
              <div class="contact-issue-state">
                <el-tag :type="item.status === '已回复' ? 'success' : 'warning'" effect="plain">{{ item.status }}</el-tag>
                <span>{{ item.created_at }}</span>
              </div>
              <el-button type="danger" plain :icon="Delete" @click="$emit('delete', item.id)">删除</el-button>
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
            <el-button type="primary" plain :icon="ChatLineRound" @click="$emit('reply', item)">回复该问题</el-button>
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
            <el-tag type="success" effect="plain">{{ operatorName }} 已登录</el-tag>
          </div>
        </template>

        <div class="contact-reply-box">
          <el-input
            v-model="replyText"
            type="textarea"
            :rows="5"
            placeholder="输入回复内容，然后在上方选择一个待回复问题。"
          />
        </div>

        <p v-if="error" class="contact-error">{{ error }}</p>
      </el-card>
    </div>
  </section>
</template>

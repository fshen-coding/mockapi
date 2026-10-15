<script setup>
import { computed, ref, watch } from 'vue'
import { Check, Delete, Edit, Refresh, Setting, User } from '@element-plus/icons-vue'
import PageHeader from '../components/PageHeader.vue'

const props = defineProps({
  users: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  error: { type: String, default: '' },
  editSaving: { type: Boolean, default: false },
})

const editVisible = defineModel('editVisible', { type: Boolean, default: false })
const editForm = defineModel('editForm', { type: Object, required: true })

const emit = defineEmits(['refresh', 'approve', 'reject', 'edit', 'remove', 'save'])

const STATUS_LABELS = { active: '正常', pending: '待审核' }
const STATUS_TAG_TYPES = { active: 'success', pending: 'warning' }

const page = ref(1)
const pageSize = ref(20)

watch(() => props.users, () => {
  page.value = 1
})

const pagedUsers = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return props.users.slice(start, start + pageSize.value)
})

function statusLabel(status) {
  return STATUS_LABELS[status] || '已拒绝'
}

function statusTagType(status) {
  return STATUS_TAG_TYPES[status] || 'danger'
}
</script>

<template>
  <section class="tool-page-view user-management-view">
    <PageHeader
      eyebrow="User Management"
      title="用户管理"
      description="查看、编辑所有注册账号，可修改账号名、密码、备注，或永久删除账号。"
      :show-back="false"
    >
      <template #actions>
        <el-button plain :icon="Refresh" :loading="loading" @click="emit('refresh')">刷新</el-button>
      </template>
    </PageHeader>

    <p v-if="error" class="login-error page-error">{{ error }}</p>

    <el-card shadow="never" class="surface-card">
      <div v-if="loading && users.length === 0" class="session-empty">
        <span class="session-empty__icon"><el-icon><Setting /></el-icon></span>
        <p class="session-empty__title">加载中…</p>
      </div>
      <div v-else-if="users.length === 0" class="session-empty">
        <span class="session-empty__icon"><el-icon><User /></el-icon></span>
        <p class="session-empty__title">暂无账号</p>
      </div>
      <div v-else class="user-management-table" role="table" aria-label="用户列表">
        <div class="user-table-head user-table-row" role="row">
          <span class="col-username" role="columnheader">账号</span>
          <span class="col-role" role="columnheader">角色</span>
          <span class="col-status" role="columnheader">状态</span>
          <span class="col-notes" role="columnheader">备注</span>
          <span class="col-created" role="columnheader">注册时间</span>
          <span class="col-login" role="columnheader">最近登录</span>
          <span class="col-actions" role="columnheader"><span class="sr-only">操作</span></span>
        </div>
        <article
          v-for="user in pagedUsers"
          :key="user.id"
          class="user-table-row"
          role="row"
          :class="{ 'is-admin-row': user.role === 'admin', 'is-pending-row': user.status === 'pending' }"
        >
          <span class="col-username" role="cell">
            <code>{{ user.username }}</code>
            <el-tag v-if="user.role === 'admin'" size="small" type="success" effect="plain" class="user-admin-tag">管理员</el-tag>
          </span>
          <span class="col-role" role="cell">{{ user.role === 'admin' ? '管理员' : '普通用户' }}</span>
          <span class="col-status" role="cell">
            <el-tag size="small" effect="plain" :type="statusTagType(user.status)">{{ statusLabel(user.status) }}</el-tag>
          </span>
          <span class="col-notes user-notes-cell" role="cell">{{ user.notes || '—' }}</span>
          <span class="col-created" role="cell">{{ user.created_at || '—' }}</span>
          <span class="col-login" role="cell">{{ user.last_login_at || '从未登录' }}</span>
          <span class="col-actions" role="cell">
            <template v-if="user.status === 'pending'">
              <el-button size="small" type="success" plain :icon="Check" @click="emit('approve', user)">通过</el-button>
              <el-button size="small" type="danger" plain @click="emit('reject', user)">拒绝</el-button>
            </template>
            <template v-else>
              <el-button size="small" plain :icon="Edit" @click="emit('edit', user)">编辑</el-button>
              <el-button
                size="small"
                plain
                type="danger"
                :icon="Delete"
                :disabled="user.role === 'admin'"
                :title="user.role === 'admin' ? '不能删除管理员账号' : ''"
                @click="emit('remove', user)"
              >删除</el-button>
            </template>
          </span>
        </article>
        <div v-if="users.length > pageSize" class="user-table-pagination">
          <el-pagination
            v-model:current-page="page"
            v-model:page-size="pageSize"
            :page-sizes="[10, 20, 50]"
            :total="users.length"
            layout="total, sizes, prev, pager, next"
            background
            size="small"
          />
        </div>
      </div>
    </el-card>

    <el-dialog v-model="editVisible" title="编辑账号" width="min(480px, 92vw)" append-to-body>
      <el-form label-position="top" class="prompt-template-form">
        <el-form-item label="账号名">
          <el-input v-model.trim="editForm.new_username" placeholder="账号名" autocomplete="off" />
        </el-form-item>
        <el-form-item label="新密码（留空不修改）">
          <el-input
            v-model="editForm.new_password"
            type="password"
            show-password
            placeholder="留空则不更改密码"
            autocomplete="new-password"
          />
        </el-form-item>
        <el-form-item label="备注">
          <el-input
            v-model="editForm.notes"
            type="textarea"
            :rows="3"
            placeholder="填写备注，例如：负责 UAT 环境 / 内部测试账号"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="editSaving" @click="emit('save')">保存</el-button>
      </template>
    </el-dialog>
  </section>
</template>

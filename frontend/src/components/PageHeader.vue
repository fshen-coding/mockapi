<script setup>
import { Back } from '@element-plus/icons-vue'

defineProps({
  eyebrow: { type: String, default: '' },
  title: { type: String, required: true },
  description: { type: String, default: '' },
  backLabel: { type: String, default: '返回控制台' },
  showBack: { type: Boolean, default: true },
})

defineEmits(['back'])
</script>

<template>
  <div class="log-system-head">
    <div>
      <p v-if="eyebrow" class="eyebrow">{{ eyebrow }}</p>
      <h2>{{ title }}</h2>
      <p v-if="description || $slots.description">
        <slot name="description">{{ description }}</slot>
      </p>
    </div>
    <div v-if="showBack || $slots.actions" class="page-header-actions">
      <slot name="actions" />
      <el-button v-if="showBack" plain :icon="Back" @click="$emit('back')">{{ backLabel }}</el-button>
    </div>
  </div>
</template>

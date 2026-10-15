<script setup>
defineProps({
  operationKey: { type: String, required: true },
  fields: { type: Array, default: () => [] },
  // 由父组件持有的 reactive 表单对象，字段值直接写回其中。
  form: { type: Object, required: true },
})

function fieldOptions(field) {
  return (field.options ?? []).map((option) => (
    typeof option === 'object' ? option : { label: option, value: option }
  ))
}
</script>

<template>
  <div class="operation-fields" :class="{ empty: fields.length === 0 }">
    <template v-if="fields.length">
      <template v-for="field in fields" :key="`${operationKey}-${field.prop}`">
        <el-form-item v-if="!field.visible || field.visible(form)" :label="field.label">
          <el-input
            v-if="field.type === 'text'"
            v-model="form[field.prop]"
            :placeholder="field.placeholder"
          />
          <el-input-number
            v-else-if="field.type === 'number'"
            v-model="form[field.prop]"
            :min="field.min"
            :step="field.step || 1"
            controls-position="right"
            class="full-width"
          />
          <el-select
            v-else-if="field.type === 'select'"
            v-model="form[field.prop]"
            :filterable="Boolean(field.allowCreate)"
            :allow-create="Boolean(field.allowCreate)"
            :default-first-option="Boolean(field.allowCreate)"
            :placeholder="field.placeholder"
          >
            <el-option
              v-for="option in fieldOptions(field)"
              :key="`${field.prop}-${option.value}`"
              :label="option.label"
              :value="option.value"
            />
          </el-select>
        </el-form-item>
      </template>
    </template>
    <div v-else class="no-params">这个操作不需要额外参数。</div>
  </div>
</template>

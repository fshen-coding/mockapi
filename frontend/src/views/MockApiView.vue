<script setup>
import { computed } from 'vue'
import { Edit } from '@element-plus/icons-vue'
import PageHeader from '../components/PageHeader.vue'

const props = defineProps({
  shopPerformancePresets: { type: Array, default: () => [] },
  companyTemplates: { type: Array, default: () => [] },
  companyImageTemplates: { type: Array, default: () => [] },
})

defineEmits(['back', 'edit-shop-performance', 'edit-company-templates', 'edit-company-images'])

const companyTemplateNames = computed(() => props.companyTemplates.map((item) => item.name).join('、'))
</script>

<template>
  <section class="tool-page-view mock-api-view">
    <PageHeader
      eyebrow="Mock API"
      title="Mock 接口"
      description="集中维护 DS-CNY 的经营数据参数和企业信息模板，保存后会同步到接口测试的对应下拉框。"
      back-label="返回接口测试"
      @back="$emit('back')"
    />

    <el-card shadow="never" class="surface-card mock-api-card">
      <div class="mock-api-endpoint">
        <div>
          <span class="mock-api-method">POST</span>
          <code>/api/mock/shop-performance-cny-boost</code>
        </div>
        <span class="mock-api-count">{{ shopPerformancePresets.length }} 条店铺记录</span>
      </div>
      <div class="mock-api-summary-record">
        <div>
          <strong>经营数据参数配置</strong>
          <span>已反显 {{ shopPerformancePresets.length }} 条店铺记录，可进入详情编辑内置配置或新增记录。</span>
        </div>
        <el-button type="primary" plain :icon="Edit" @click="$emit('edit-shop-performance')">编辑配置</el-button>
      </div>
    </el-card>

    <el-card shadow="never" class="surface-card mock-api-card">
      <div class="mock-api-endpoint">
        <div class="mock-api-linked-endpoints">
          <span><span class="mock-api-method">POST</span><code>/api/mock/fp-business-profile</code></span>
          <span><span class="mock-api-method">POST</span><code>/api/mock/fp-director-info</code></span>
          <span><span class="mock-api-method">POST</span><code>/api/mock/fp-add-contact-information</code></span>
        </div>
        <span class="mock-api-count">{{ companyTemplates.length }} 个公司模板</span>
      </div>
      <div class="mock-api-summary-record">
        <div>
          <strong>三接口公司模板配置</strong>
          <span>已配置 {{ companyTemplates.length }} 条记录：{{ companyTemplateNames }}</span>
        </div>
        <el-button type="primary" plain :icon="Edit" @click="$emit('edit-company-templates')">编辑配置</el-button>
      </div>
    </el-card>

    <el-card shadow="never" class="surface-card mock-api-card">
      <div class="mock-api-endpoint">
        <div class="mock-api-linked-endpoints">
          <span><span class="mock-api-method">IMAGE</span><code>/api/mock/fp-business-profile</code></span>
          <span><span class="mock-api-method">IMAGE</span><code>/api/mock/fp-director-info</code></span>
        </div>
        <span class="mock-api-count">{{ companyImageTemplates.length }} 个图片配置</span>
      </div>
      <div class="mock-api-summary-record">
        <div>
          <strong>三接口公司图片配置</strong>
          <span>上传企业营业执照、法人身份证正面和反面，保存后同步到接口测试的图片下拉框。</span>
        </div>
        <el-button type="primary" plain :icon="Edit" @click="$emit('edit-company-images')">编辑配置</el-button>
      </div>
    </el-card>
  </section>
</template>

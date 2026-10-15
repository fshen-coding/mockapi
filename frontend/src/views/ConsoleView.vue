<script setup>
import { inject } from 'vue'
import { ArrowDown, ArrowRight, Bell, CaretRight, Connection, Delete, Document, Promotion, Refresh } from '@element-plus/icons-vue'
import OperationFields from '../components/OperationFields.vue'

// 状态和业务逻辑仍由 App.vue 持有，这里只负责渲染。
const {
  activeOperation,
  activeOperationKey,
  activeSessionId,
  applicationOptions,
  cancelMockOperationLayout,
  connecting,
  connectionForm,
  defaultCurrencies,
  defaultEnvironments,
  defaultFunderResources,
  defaultJourneys,
  disconnecting,
  drawdownRepaymentRows,
  enumOptions,
  handleConnect,
  handleDisconnect,
  handleOperationRun,
  handleRegister,
  handleRegisterAndRunMultiShop,
  isAdmin,
  isOperationDisabled,
  isPspRowSelectable,
  journeyLabel,
  limitApplicationRows,
  loadDowsureMerchantAccounts,
  loadDrawdownRepaymentRows,
  loadLimitApplications,
  loadPspAuthorizationRows,
  loadSessions,
  loadWebankSellerOffers,
  loadingDowsureMerchantAccounts,
  loadingDrawdownRepaymentRows,
  loadingHealth,
  loadingLimitApplications,
  loadingPspAuthorizationRows,
  loadingSessions,
  loadingWebankSellerOffers,
  mockOperationDragState,
  mockOperationEditMode,
  onMockOperationDragEnd,
  onMockOperationDragStart,
  onMockOperationDrop,
  onlineUsdHsbcBlocked,
  onlineUsdHsbcBlockedReason,
  operationDisabledChip,
  operationDisabledReason,
  operationForms,
  operationResults,
  pspAuthorizationRows,
  refreshHealth,
  registerAndBindingBlocked,
  registerAndBindingBlockedReason,
  registerForm,
  registering,
  registeringAndBinding,
  repaymentRowSelectionKey,
  runningOperationKey,
  saveMockOperationLayout,
  selectDrawdownRepaymentRow,
  selectLimitApplicationRow,
  selectPspAuthorizationRow,
  selectedApplication,
  selectedApplicationCurrency,
  selectedApplicationUniqueId,
  selectedDowsureRepaymentLoanCode,
  selectedLimitApplicationUniqueId,
  selectedPspMerchantAccountId,
  sessionSummary,
  shouldShowDowsureMerchantAccounts,
  shouldShowDrawdownRepaymentRows,
  shouldShowLimitApplications,
  shouldShowPspAuthorizationRows,
  shouldShowWebankSellerOffers,
  startMockOperationLongPress,
  stopMockOperationLongPress,
  toggleOperationPanel,
  visibleOperations,
} = inject('consoleContext')
</script>

<template>
<section class="workspace-grid">
  <div class="workspace-row">
    <el-card shadow="never" class="surface-card workspace-row__main connection-card">
      <template #header>
        <div class="card-head">
          <div class="head-copy">
            <h2>连接与注册</h2>
            <p>先建立 session，再执行 mock 操作。</p>
          </div>
          <el-space>
            <el-button :icon="Refresh" plain :loading="loadingHealth || loadingSessions" @click="loadSessions(); refreshHealth()">
              刷新状态
            </el-button>
            <el-button :icon="Delete" type="danger" plain :disabled="!activeSessionId" :loading="disconnecting" @click="handleDisconnect">
              断开会话
            </el-button>
          </el-space>
        </div>
      </template>

      <div class="dual-panel">
        <div class="form-block">
          <h3><el-icon><Connection /></el-icon> 会话连接</h3>
          <el-form label-position="top" class="tight-form">
            <el-form-item label="环境">
              <el-select v-model="connectionForm.env">
                <el-option
                  v-for="env in enumOptions?.environments ?? defaultEnvironments"
                  :key="env"
                  :label="env"
                  :value="env"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="手机号">
              <el-input v-model.trim="connectionForm.phone_number" placeholder="8位或11位数字" />
            </el-form-item>
            <el-button type="primary" :icon="Connection" :loading="connecting" @click="handleConnect">
              连接 session
            </el-button>
          </el-form>
        </div>

        <div class="form-block">
          <h3><el-icon><Document /></el-icon> 新账号注册</h3>
          <el-form label-position="top" class="tight-form">
            <el-form-item label="环境">
              <el-select v-model="registerForm.env">
                <el-option
                  v-for="env in enumOptions?.environments ?? defaultEnvironments"
                  :key="`reg-${env}`"
                  :label="env"
                  :value="env"
                />
              </el-select>
            </el-form-item>
            <div class="form-row register-fields" :class="{ 'is-offline': registerForm.offline }">
              <el-form-item v-if="!registerForm.offline" label="Journey">
                <el-select v-model="registerForm.journey">
                  <el-option
                    v-for="journey in enumOptions?.journeys ?? defaultJourneys"
                    :key="journey"
                    :label="journeyLabel(journey)"
                    :value="journey"
                  />
                </el-select>
              </el-form-item>
              <el-form-item label="币种" :class="{ 'full-row': registerForm.offline }">
                <el-select v-model="registerForm.currency">
                  <el-option
                    v-for="currency in enumOptions?.currencies ?? defaultCurrencies"
                    :key="currency"
                    :label="currency"
                    :value="currency"
                  />
                </el-select>
              </el-form-item>
              <el-form-item label="资方代码" class="full-row">
                <el-select v-model="registerForm.funder_resource">
                  <el-option
                    v-for="funderResource in enumOptions?.funder_resources ?? defaultFunderResources"
                    :key="funderResource"
                    :label="funderResource"
                    :value="funderResource"
                  />
                </el-select>
              </el-form-item>
            </div>
            <el-form-item>
              <el-switch v-model="registerForm.offline" active-text="线下模式" inactive-text="线上模式" />
            </el-form-item>
            <div class="register-actions">
              <el-button
                type="primary"
                :icon="Promotion"
                :loading="registering"
                :disabled="onlineUsdHsbcBlocked"
                :title="onlineUsdHsbcBlocked ? onlineUsdHsbcBlockedReason : ''"
                @click="handleRegister"
              >
                执行注册
              </el-button>
              <el-button
                type="primary"
                plain
                :icon="Connection"
                :loading="registeringAndBinding"
                :disabled="registerAndBindingBlocked"
                :title="registerAndBindingBlocked ? registerAndBindingBlockedReason : ''"
                @click="handleRegisterAndRunMultiShop"
              >
                注册并完成绑店
              </el-button>
            </div>
          </el-form>
        </div>
      </div>

    </el-card>

    <el-card shadow="never" class="surface-card workspace-row__side session-card">
      <template #header>
        <div class="card-head">
          <div class="head-copy">
            <h2>当前会话</h2>
            <p>活动连接与最近状态。</p>
          </div>
        </div>
      </template>

      <div v-if="sessionSummary" class="session-summary">
        <div class="summary-row"><span>Session ID</span><strong>{{ sessionSummary.session_id }}</strong></div>
        <div class="summary-row"><span>环境</span><strong>{{ sessionSummary.env }}</strong></div>
        <div class="summary-row"><span>手机号</span><strong>{{ sessionSummary.phone_number }}</strong></div>
        <div class="summary-row"><span>Merchant</span><strong>{{ sessionSummary.merchant_id || '-' }}</strong></div>
        <div class="summary-row"><span>选中申请单</span><strong>{{ selectedApplicationUniqueId || '-' }}</strong></div>
        <div class="summary-row"><span>申请单数量</span><strong>{{ applicationOptions.length }}</strong></div>
      </div>
      <div v-else class="session-empty">
        <span class="session-empty__icon">
          <el-icon><Bell /></el-icon>
        </span>
        <p class="session-empty__title">还没有活动会话</p>
        <p class="session-empty__hint">连接 session 后会显示 ID、Merchant 与申请单。</p>
      </div>
    </el-card>
  </div>

  <el-card shadow="never" class="surface-card mock-panel-card">
    <template #header>
      <div class="card-head">
          <div class="head-copy">
            <h2>Mock 操作面板</h2>
            <p>{{ mockOperationEditMode ? '排版模式：拖动模块调整顺序，保存后全局生效。' : '按当前 session 执行 webhook 模拟操作，执行结果会保留在对应步骤下方。' }}</p>
          </div>
          <div v-if="isAdmin" class="mock-layout-actions">
            <el-tag v-if="mockOperationEditMode" size="small" type="warning" effect="plain">排版中</el-tag>
            <el-button v-if="mockOperationEditMode" size="small" @click="cancelMockOperationLayout">取消</el-button>
            <el-button v-if="mockOperationEditMode" size="small" type="primary" @click="saveMockOperationLayout">保存排版</el-button>
            <span v-else class="mock-layout-hint">长按模块进入排版</span>
          </div>
        </div>
      </template>

      <div class="operation-context">
        <div>
          <span>环境</span>
          <strong>{{ sessionSummary?.env || connectionForm.env }}</strong>
        </div>
        <div>
          <span>手机号</span>
          <strong>{{ sessionSummary?.phone_number || connectionForm.phone_number || '-' }}</strong>
        </div>
        <div>
          <span>Merchant ID</span>
          <strong>{{ sessionSummary?.merchant_id || '-' }}</strong>
        </div>
      </div>

      <div v-if="sessionSummary" class="application-selector">
        <span class="application-selector-label">申请单</span>
        <div class="application-selector-current">
          <div>
            <span>Application</span>
            <strong>{{ selectedApplicationUniqueId || sessionSummary?.application_unique_id || '-' }}</strong>
          </div>
          <div>
            <span>Currency</span>
            <strong>{{ selectedApplicationCurrency }}</strong>
          </div>
          <div>
            <span>Lender</span>
            <strong>{{ selectedApplication?.lender_code || sessionSummary?.lender_code || '-' }}</strong>
          </div>
          <div>
            <span>Status</span>
            <strong>{{ selectedApplication?.application_status || sessionSummary?.application_status || '-' }}</strong>
          </div>
        </div>
        <el-select
          v-if="applicationOptions.length > 1"
          v-model="selectedApplicationUniqueId"
          filterable
          class="application-select"
          popper-class="application-select-popper"
          :popper-options="{ modifiers: [{ name: 'preventOverflow', options: { boundary: 'clippingParents' } }] }"
        >
          <el-option
            v-for="application in applicationOptions"
            :key="application.application_unique_id"
            :label="application.application_unique_id"
            :value="application.application_unique_id"
          >
            <div class="application-option">
              <strong>{{ application.application_unique_id }}</strong>
              <span>{{ application.finance_product_currency || selectedApplicationCurrency }}</span>
              <span>{{ application.application_status || '-' }}</span>
              <span>{{ application.lender_code || '-' }}</span>
            </div>
          </el-option>
        </el-select>
        <span v-else class="application-single-note">默认最新申请单</span>
      </div>

      <div class="operation-panels operation-button-list">
        <template v-for="operation in visibleOperations" :key="operation.key">
        <div
          class="operation-row"
          :class="{ active: activeOperationKey === operation.key, disabled: isOperationDisabled(operation), 'is-layout-item': mockOperationEditMode, 'is-layout-dragging': mockOperationDragState === operation.key }"
          :draggable="isAdmin && mockOperationEditMode"
          @pointerdown="startMockOperationLongPress"
          @pointerup="stopMockOperationLongPress"
          @pointerleave="stopMockOperationLongPress"
          @pointercancel="stopMockOperationLongPress"
          @dragstart="onMockOperationDragStart($event, operation.key)"
          @dragover.prevent="isAdmin && mockOperationEditMode"
          @drop="onMockOperationDrop($event, operation.key)"
          @dragend="onMockOperationDragEnd"
        >
          <button
            type="button"
            class="operation-toggle"
            :aria-expanded="activeOperationKey === operation.key"
            :aria-disabled="isOperationDisabled(operation)"
            :disabled="isOperationDisabled(operation)"
            :title="isOperationDisabled(operation) ? operationDisabledReason(operation) : operation.description"
            @click="toggleOperationPanel(operation.key)"
          >
            <span class="operation-toggle-main">
              <span class="operation-toggle-badge">
                <el-icon><CaretRight /></el-icon>
              </span>
              <span class="operation-toggle-text">
                <b>{{ operation.title }}</b>
                <code>{{ operation.endpoint }}</code>
              </span>
            </span>
            <span class="operation-toggle-meta">
              <span v-if="isOperationDisabled(operation)" class="operation-disabled-chip">{{ operationDisabledChip(operation) }}</span>
              <el-icon class="operation-toggle-arrow"><component :is="activeOperationKey === operation.key ? ArrowDown : ArrowRight" /></el-icon>
            </span>
          </button>
        </div>

        <div
          v-if="activeOperationKey === operation.key && activeOperation"
          class="operation-detail-dock"
        >
        <div class="operation-detail-head">
          <div>
            <p>{{ activeOperation.title }}</p>
            <span>{{ activeOperation.description }}</span>
          </div>
          <el-button size="small" text @click="toggleOperationPanel(activeOperation.key)">
            收起
          </el-button>
        </div>
        <div
          class="operation-body"
          :class="{ 'dowsure-credit-body': activeOperation.key === 'dowsureCreditResult' }"
        >
          <code class="endpoint-chip">{{ activeOperation.endpoint }}</code>
          <el-form label-position="top" class="tight-form">
            <div v-if="shouldShowPspAuthorizationRows" class="psp-status-panel">
              <div class="psp-status-head">
                <span>店铺授权状态</span>
                <el-button size="small" text :loading="loadingPspAuthorizationRows" @click="loadPspAuthorizationRows">
                  刷新
                </el-button>
              </div>
              <div class="psp-status-table">
                <div class="psp-status-row psp-status-header">
                  <span>merchant_account_id</span>
                  <span>SP authorization_id</span>
                  <span>SP 状态</span>
                  <span>3P 状态</span>
                  <span>PSP 状态</span>
                  <span>选择</span>
                </div>
                <div v-if="!loadingPspAuthorizationRows && pspAuthorizationRows.length === 0" class="psp-status-empty">
                  暂无店铺授权记录。
                </div>
                <div
                  v-for="row in pspAuthorizationRows"
                  :key="row.merchant_account_id"
                  class="psp-status-row"
                  :class="{ selected: row.merchant_account_id === selectedPspMerchantAccountId }"
                >
                  <strong>{{ row.merchant_account_id || '-' }}</strong>
                  <strong>{{ row.sp_authorization_id || '-' }}</strong>
                  <span>{{ row.sp_status || '-' }}</span>
                  <span>{{ row.three_pl_status || '-' }}</span>
                  <span>{{ row.psp_status || '-' }}</span>
                  <el-button
                    size="small"
                    :type="row.merchant_account_id === selectedPspMerchantAccountId ? 'primary' : 'default'"
                    :disabled="!isPspRowSelectable(row)"
                    @click="selectPspAuthorizationRow(row)"
                  >
                    {{ row.merchant_account_id === selectedPspMerchantAccountId ? '已选中' : '选择' }}
                  </el-button>
                </div>
              </div>
            </div>

            <div v-if="shouldShowLimitApplications" class="limit-applications-panel">
              <div class="psp-status-head">
                <span>核保单</span>
                <el-button size="small" text :loading="loadingLimitApplications" @click="loadLimitApplications">
                  刷新
                </el-button>
              </div>
              <div class="limit-applications-table">
                <div class="limit-applications-row limit-applications-header">
                  <span>limit_application_unique_id</span>
                  <span>status</span>
                  <span>created_at</span>
                  <span>选择</span>
                </div>
                <div v-if="!loadingLimitApplications && limitApplicationRows.length === 0" class="psp-status-empty">
                  暂无核保单记录，默认执行时会使用最新核保单。
                </div>
                <div
                  v-for="row in limitApplicationRows"
                  :key="row.limit_application_unique_id"
                  class="limit-applications-row"
                  :class="{ selected: row.limit_application_unique_id === selectedLimitApplicationUniqueId }"
                >
                  <strong>{{ row.limit_application_unique_id || '-' }}</strong>
                  <span>{{ row.status || '-' }}</span>
                  <span>{{ row.created_at || '-' }}</span>
                  <el-button
                    size="small"
                    :type="row.limit_application_unique_id === selectedLimitApplicationUniqueId ? 'primary' : 'default'"
                    @click="selectLimitApplicationRow(row)"
                  >
                    {{ row.limit_application_unique_id === selectedLimitApplicationUniqueId ? '已选中' : '选择' }}
                  </el-button>
                </div>
              </div>
            </div>

            <div v-if="shouldShowDrawdownRepaymentRows" class="drawdown-repayment-panel">
              <div class="psp-status-head">
                <span>还款单</span>
                <el-button size="small" text :loading="loadingDrawdownRepaymentRows" @click="loadDrawdownRepaymentRows">
                  刷新
                </el-button>
              </div>
              <div class="drawdown-repayment-table">
                <div class="drawdown-repayment-row drawdown-repayment-header">
                  <span>lender_loan_id</span>
                  <span>{{ activeOperation.key === 'cgbRepaymentResult' ? 'CGB loanCode（lender_drawdown_id）' : 'WEBANK loanCode' }}</span>
                  <span>total_interest_rate</span>
                  <span>outstanding_amount</span>
                  <span>repayment_status</span>
                  <span>选择</span>
                </div>
                <div v-if="!loadingDrawdownRepaymentRows && drawdownRepaymentRows.length === 0" class="psp-status-empty">
                  暂无还款单记录，默认执行时会使用最新 dpu_drawdown 记录。
                </div>
                <div
                  v-for="row in drawdownRepaymentRows"
                  :key="`${row.lender_loan_id || row.lender_drawdown_id}-${row.lender_drawdown_id || ''}`"
                  class="drawdown-repayment-row"
                  :class="{ selected: repaymentRowSelectionKey(row) === selectedDowsureRepaymentLoanCode }"
                >
                  <strong>{{ row.lender_loan_id || '-' }}</strong>
                  <span>{{ row.lender_drawdown_id || '-' }}</span>
                  <span>{{ row.total_interest_rate ?? '-' }}</span>
                  <span>{{ row.outstanding_amount ?? '-' }}</span>
                  <span>{{ row.repayment_status || '-' }}</span>
                  <el-button
                    size="small"
                    :type="repaymentRowSelectionKey(row) === selectedDowsureRepaymentLoanCode ? 'primary' : 'default'"
                    @click="selectDrawdownRepaymentRow(row)"
                  >
                    {{ repaymentRowSelectionKey(row) === selectedDowsureRepaymentLoanCode ? '已选中' : '选择' }}
                  </el-button>
                </div>
              </div>
            </div>

            <OperationFields
              v-if="activeOperation.key === 'dowsureCreditResult'"
              :operation-key="activeOperation.key"
              :fields="activeOperation.fields"
              :form="operationForms[activeOperation.key]"
            />

            <div v-if="shouldShowDowsureMerchantAccounts" class="dowsure-accounts-panel">
              <div class="psp-status-head">
                <span>DOWSURE 店铺额度（offerId / sellerId 自动带出）</span>
                <el-button size="small" text :loading="loadingDowsureMerchantAccounts" @click="loadDowsureMerchantAccounts">
                  刷新
                </el-button>
              </div>
              <div class="dowsure-accounts-table">
                <div class="dowsure-accounts-row dowsure-accounts-header">
                  <span>offerId</span>
                  <span>sellerId</span>
                  <span>amount</span>
                </div>
                <div v-if="!loadingDowsureMerchantAccounts && operationForms.dowsureCreditResult.creditResultList.length === 0" class="psp-status-empty">
                  暂无 DOWSURE 店铺记录。
                </div>
                <div
                  v-for="row in operationForms.dowsureCreditResult.creditResultList"
                  :key="row.offerId || row.sellerId"
                  class="dowsure-accounts-row"
                >
                  <strong>{{ row.offerId || '-' }}</strong>
                  <strong>{{ row.sellerId || '-' }}</strong>
                  <el-input-number
                    v-model="row.amount"
                    :min="0"
                    :step="1000"
                    controls-position="right"
                    class="full-width"
                  />
                </div>
              </div>
            </div>

            <div v-if="shouldShowWebankSellerOffers" class="dowsure-accounts-panel">
              <div class="psp-status-head">
                <span>WEBANK 店铺额度</span>
                <el-button size="small" text :loading="loadingWebankSellerOffers" @click="loadWebankSellerOffers">
                  刷新
                </el-button>
              </div>
              <div class="dowsure-accounts-table webank-seller-offers-table">
                <div class="dowsure-accounts-row dowsure-accounts-header">
                  <span>offer_id</span>
                  <span>seller_id</span>
                  <span>marketplace_country</span>
                  <span>准入状态</span>
                  <span>applySellerBusinessSum</span>
                </div>
                <div v-if="!loadingWebankSellerOffers && operationForms.webankCreditResult.seller_offers.length === 0" class="psp-status-empty">
                  暂无 WEBANK 店铺记录。
                </div>
                <div
                  v-for="row in operationForms.webankCreditResult.seller_offers"
                  :key="row.offer_id || row.seller_id"
                  class="dowsure-accounts-row"
                >
                  <strong>{{ row.offer_id || '-' }}</strong>
                  <strong>{{ row.seller_id || '-' }}</strong>
                  <span>{{ row.marketplace_country || '-' }}</span>
                  <el-select v-model="row.admissionStatus" class="full-width">
                    <el-option label="准入" value="ADMITTED" />
                    <el-option label="不准入" value="NOT_ADMITTED" />
                  </el-select>
                  <el-input-number
                    v-model="row.applySellerBusinessSum"
                    :min="0"
                    :step="1000"
                    controls-position="right"
                    class="full-width"
                  />
                </div>
              </div>
            </div>

            <OperationFields
              v-if="activeOperation.key !== 'dowsureCreditResult'"
              :operation-key="activeOperation.key"
              :fields="activeOperation.fields"
              :form="operationForms[activeOperation.key]"
            />

            <el-button
              class="operation-run-button"
              type="primary"
              :disabled="!activeSessionId || isOperationDisabled(activeOperation)"
              :loading="runningOperationKey === activeOperation.key"
              :title="isOperationDisabled(activeOperation) ? operationDisabledReason(activeOperation) : ''"
              @click="handleOperationRun(activeOperation)"
            >
              执行 {{ activeOperation.title }}
            </el-button>
          </el-form>

          <div
            v-if="operationResults[activeOperation.key]"
            class="result-strip"
            :class="{ 'result-strip-error': operationResults[activeOperation.key]?.success === false }"
          >
            <span class="result-title">最近一次执行结果</span>
            <pre>{{ JSON.stringify(operationResults[activeOperation.key], null, 2) }}</pre>
          </div>
        </div>
      </div>
        </template>
      </div>
  </el-card>
</section>
</template>

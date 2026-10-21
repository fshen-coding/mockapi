<script setup>
import { inject } from 'vue'
import { ArrowDown, ArrowRight, Back, Delete, DocumentCopy, Edit, Plus, Promotion, Refresh } from '@element-plus/icons-vue'

// 状态和业务逻辑仍由 App.vue 持有，这里只负责渲染。
const {
  activeInterfaceScenario,
  activeInterfaceScenarioKey,
  activeOperationKey,
  activeScenarioTab,
  activeSessionId,
  activeStepEditorTabs,
  addScenarioStepAfter,
  backToConsole,
  connectionForm,
  copyResponseText,
  debugActualMethod,
  debugActualUrlText,
  debugInterfaceSearch,
  debugInterfaceSteps,
  debugRequestBodyText,
  debugRequestError,
  debugRequestHeadersText,
  debugRequestQueryText,
  debugSending,
  defaultEnvironments,
  enabledInterfaceStepCount,
  enumOptions,
  expandedScenarioTrees,
  filteredDebugInterfaceSteps,
  filteredInterfaceScenarioCount,
  filteredInterfaceScenarioGroups,
  formatStepDuration,
  getDebugStepPayload,
  getScenarioResponseState,
  getScenarioStepActualRequests,
  getScenarioStepActualResponses,
  getScenarioStepDescription,
  getScenarioStepLogic,
  getScenarioStepOverrideDraft,
  getScenarioStepResponse,
  getScenarioStepSourceEndpoint,
  handleDebugStepRun,
  handleScenarioSave,
  handleScenarioServerExecute,
  handleScenarioStop,
  hideScenarioStepMeta,
  interfaceAutomationSteps,
  interfaceFocusMode,
  interfacePageMode,
  interfacePageModes,
  interfaceScenarios,
  interfaceStepEnabled,
  isAdmin,
  isAuthenticated,
  isStepFieldDisabled,
  isStepFieldVisible,
  latestScenarioRunContext,
  methodBadgeClass,
  onScenarioStepDragEnd,
  onScenarioStepDragOver,
  onScenarioStepDragStart,
  onScenarioStepDrop,
  openScenarioAddStep,
  openScenarioHistoryDetail,
  openScenarioMetaEditor,
  openScenarioStepMetaEditor,
  prettifyDebugJsonDraft,
  resetDebugRequestDraft,
  resetScenarioStepMetaEditor,
  resetScenarioStepOverrideForStep,
  saveScenarioMetaEditor,
  saveScenarioStepMetaEditor,
  saveScenarioStepOverrideForStep,
  scenarioAddStepForm,
  scenarioAddStepVisible,
  scenarioAssertions,
  scenarioDirectoryExpanded,
  scenarioDragState,
  scenarioExecuting,
  scenarioExecutionHistory,
  scenarioHistoryLoading,
  scenarioHistoryError,
  scenarioHistoryHasMore,
  loadScenarioExecutionHistory,
  scenarioMetaEditForm,
  scenarioMetaEditSaving,
  scenarioMetaEditVisible,
  scenarioSettings,
  scenarioStepMetaEditDeleting,
  scenarioStepMetaEditForm,
  scenarioStepMetaEditSaving,
  scenarioStepMetaEditVisible,
  scenarioStepOverrideKey,
  scenarioStepOverrideSaving,
  scenarioStepOverrides,
  scenarioStepResults,
  scenarioStepSourceErrors,
  scenarioStepSourceLoading,
  scenarioStepStatus,
  scenarioStopRequested,
  scenarioTabs,
  scenarioVariables,
  selectDebugInterface,
  selectScenarioFromTree,
  selectStepFromTree,
  selectedInterfaceStep,
  stepFocusTab,
  switchInterfacePageMode,
  toggleScenarioDirectory,
  toggleScenarioTreeNode,
} = inject('interfaceTestContext')
</script>

<template>
<section class="interface-test-view">
  <div class="log-system-head interface-test-head">
    <div>
      <p class="eyebrow">Interface Test</p>
      <h2>接口测试</h2>
      <p>按 workflow 顺序列出所有 mock 接口，选择接口后可查看请求参数、预览 payload 并直接发起调用。</p>
    </div>
    <div class="interface-test-actions">
      <div class="interface-page-switch" role="tablist" aria-label="接口测试页面切换">
        <button
          v-for="mode in interfacePageModes"
          :key="mode.key"
          type="button"
          role="tab"
          :aria-selected="interfacePageMode === mode.key"
          :class="{ active: interfacePageMode === mode.key }"
          @click="switchInterfacePageMode(mode.key)"
        >{{ mode.label }}</button>
      </div>
      <el-tag :type="activeSessionId ? 'success' : 'warning'" effect="plain">{{ activeSessionId ? 'Session 已连接' : '未连接 Session' }}</el-tag>
      <el-button plain :icon="Back" @click="backToConsole">返回控制台</el-button>
    </div>
  </div>

  <div class="interface-automation-shell" :class="{ 'is-report': interfacePageMode === 'report' }">
    <aside v-if="interfacePageMode !== 'report'" class="scenario-library" aria-label="场景集合">
      <div v-if="interfacePageMode === 'debug'" class="debug-interface-list">
        <div class="scenario-tree-head">
          <strong>
            调试接口 ({{ filteredDebugInterfaceSteps.length }}<template v-if="debugInterfaceSearch.trim()">/{{ debugInterfaceSteps.length }}</template>)
          </strong>
          <el-tag size="small" effect="plain">全局接口</el-tag>
        </div>
        <el-input
          v-model.trim="debugInterfaceSearch"
          class="debug-interface-search"
          size="small"
          clearable
          placeholder="搜索接口名 / endpoint / 场景"
        />
        <div v-if="!filteredDebugInterfaceSteps.length" class="debug-interface-empty">
          没有匹配接口。
        </div>
        <button
          v-for="(step, index) in filteredDebugInterfaceSteps"
          :key="`debug-interface-${step.key}`"
          class="debug-interface-item"
          :class="{ active: activeOperationKey === step.key }"
          type="button"
          @click="selectDebugInterface(step.key)"
        >
          <span class="scenario-tree-step-index">{{ index + 1 }}</span>
          <span
            class="scenario-tree-step-method"
            :class="step.type === 'script' ? 'is-script' : 'is-api'"
          >{{ step.type === 'script' ? 'SCRIPT' : (step.method || 'POST') }}</span>
          <span class="debug-interface-title" :title="`${step.title}\n${step.endpoint}`">
            <strong>{{ step.title }}</strong>
            <small>{{ step.endpoint }}</small>
            <em>{{ step.debugSources?.length || 1 }} 个场景使用</em>
          </span>
          <span
            class="scenario-tree-step-dot"
            :class="`is-${scenarioStepStatus(step.key)}`"
            :title="scenarioStepStatus(step.key)"
          ></span>
        </button>
      </div>
      <div v-else class="scenario-tree">
        <div class="scenario-tree-head">
          <strong>全部场景 ({{ filteredInterfaceScenarioCount }})</strong>
          <el-tag size="small" effect="plain">DPU产品流程</el-tag>
        </div>

        <div
          v-for="directory in filteredInterfaceScenarioGroups"
          :key="directory.key"
          class="scenario-tree-directory"
        >
          <div
            class="scenario-tree-directory-node"
            role="button"
            tabindex="0"
            @click="toggleScenarioDirectory(directory.key)"
            @keydown.enter.prevent="toggleScenarioDirectory(directory.key)"
            @keydown.space.prevent="toggleScenarioDirectory(directory.key)"
          >
            <button
              class="scenario-tree-toggle"
              type="button"
              :aria-label="scenarioDirectoryExpanded(directory.key) ? '收起' : '展开'"
              @click.stop="toggleScenarioDirectory(directory.key)"
            >
              <el-icon>
                <ArrowDown v-if="scenarioDirectoryExpanded(directory.key)" />
                <ArrowRight v-else />
              </el-icon>
            </button>
            <span class="scenario-tree-name">{{ directory.name }}</span>
            <small>{{ directory.scenarios.length }}</small>
          </div>

          <div v-if="scenarioDirectoryExpanded(directory.key)" class="scenario-tree-scenario-list">
            <div
              v-for="scenario in directory.scenarios"
              :key="scenario.key"
              class="scenario-tree-group"
              :class="{ active: activeInterfaceScenarioKey === scenario.key }"
            >
              <div
                class="scenario-tree-node"
                role="button"
                tabindex="0"
                @click="selectScenarioFromTree(scenario.key)"
                @keydown.enter.prevent="selectScenarioFromTree(scenario.key)"
                @keydown.space.prevent="selectScenarioFromTree(scenario.key)"
              >
                <button
                  class="scenario-tree-toggle"
                  type="button"
                  :aria-label="expandedScenarioTrees[scenario.key] ? '收起' : '展开'"
                  @click.stop="toggleScenarioTreeNode(scenario.key)"
                >
                  <el-icon>
                    <ArrowDown v-if="expandedScenarioTrees[scenario.key]" />
                    <ArrowRight v-else />
                  </el-icon>
                </button>
                <span class="scenario-tree-name">{{ scenario.name }}</span>
                <small>{{ scenario.steps.length }}</small>
              </div>

              <ul v-if="expandedScenarioTrees[scenario.key]" class="scenario-tree-step-list">
                <li
                  v-for="(step, index) in scenario.steps"
                  :key="`${scenario.key}-${step.key}`"
                  class="scenario-tree-step"
                  :class="{
                    active: activeInterfaceScenarioKey === scenario.key && activeOperationKey === step.key && interfacePageMode === 'scenario' && interfaceFocusMode === 'step',
                    disabled: interfaceStepEnabled[step.key] === false,
                    'is-dragging': scenarioDragState.scenarioKey === scenario.key && scenarioDragState.stepKey === step.key,
                    'not-draggable': !isAdmin,
                  }"
                  :draggable="isAdmin"
                  @click="selectStepFromTree(scenario.key, step.key)"
                  @dragstart="isAdmin && onScenarioStepDragStart($event, scenario.key, step.key)"
                  @dragover.prevent="isAdmin && onScenarioStepDragOver($event, scenario.key, step.key)"
                  @drop.prevent="isAdmin && onScenarioStepDrop($event, scenario.key, step.key)"
                  @dragend="onScenarioStepDragEnd"
                >
                  <span v-if="isAdmin" class="scenario-tree-step-handle" title="拖动调整顺序">⋮⋮</span>
                  <span v-else class="scenario-tree-step-handle scenario-tree-step-handle--placeholder"></span>
                  <span class="scenario-tree-step-index">{{ index + 1 }}</span>
                  <span
                    class="scenario-tree-step-method"
                    :class="step.type === 'script' ? 'is-script' : 'is-api'"
                  >{{ step.type === 'script' ? 'SCRIPT' : (step.method || 'POST') }}</span>
                  <span class="scenario-tree-step-title" :title="step.title">{{ step.title }}</span>
                  <el-switch
                    :model-value="interfaceStepEnabled[step.key] !== false"
                    size="small"
                    class="scenario-tree-step-switch"
                    @click.stop
                    @change="(val) => { interfaceStepEnabled[step.key] = val }"
                  />
                  <span
                    class="scenario-tree-step-dot"
                    :class="`is-${scenarioStepStatus(step.key)}`"
                    :title="scenarioStepStatus(step.key)"
                  ></span>
                </li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </aside>

    <main class="scenario-workbench">
      <div class="scenario-toolbar">
        <div class="scenario-title-block">
          <div class="scenario-status-line">
            <strong>{{ interfacePageMode === 'debug' ? '单接口调试' : activeInterfaceScenario.name }}</strong>
          </div>
          <p v-if="interfacePageMode === 'debug'">
            汇总所有场景里出现过的接口，选择一个接口后配置真实上游请求头和请求体单独调用。
          </p>
          <p v-else>{{ activeInterfaceScenario.description }} · {{ enabledInterfaceStepCount }} / {{ interfaceAutomationSteps.length }} 个步骤启用</p>
        </div>
        <div class="scenario-run-actions">
          <el-select v-model="connectionForm.env" class="scenario-env-select" aria-label="执行环境">
            <el-option
              v-for="env in enumOptions?.environments ?? defaultEnvironments"
              :key="`scenario-env-${env}`"
              :label="env"
              :value="env"
            />
          </el-select>
          <template v-if="interfacePageMode !== 'debug'">
            <el-button type="primary" :icon="Promotion" :loading="scenarioExecuting" @click="handleScenarioServerExecute">服务端执行</el-button>
            <el-button
              type="danger"
              plain
              :disabled="!scenarioExecuting || scenarioStopRequested"
              @click="handleScenarioStop"
            >{{ scenarioStopRequested ? '停止中…' : '停止' }}</el-button>
            <el-button v-if="isAdmin" type="primary" plain :disabled="scenarioExecuting" @click="handleScenarioSave">保存</el-button>
          </template>
        </div>
      </div>

      <section v-if="latestScenarioRunContext" class="scenario-panel scenario-run-context">
        <div><span>执行环境</span><strong>{{ latestScenarioRunContext.env || '-' }}</strong></div>
        <div><span>手机号</span><strong>{{ latestScenarioRunContext.phone_number || '-' }}</strong></div>
        <div><span>Merchant ID</span><strong>{{ latestScenarioRunContext.merchant_id || '-' }}</strong></div>
        <div><span>Application Unique ID</span><strong>{{ latestScenarioRunContext.application_unique_id || '-' }}</strong></div>
      </section>

      <div v-if="interfacePageMode === 'scenario' && interfaceFocusMode !== 'step'" class="scenario-tabs">
        <button
          v-for="tab in scenarioTabs"
          :key="tab.key"
          type="button"
          :class="{ active: activeScenarioTab === tab.key }"
          @click="activeScenarioTab = tab.key"
        >{{ tab.label }}</button>
      </div>

      <template v-if="interfacePageMode === 'scenario' && interfaceFocusMode !== 'step'">
      <section v-if="activeScenarioTab === 'base'" class="scenario-panel scenario-base-panel">
        <div class="scenario-base-item">
          <span>场景名称</span>
          <strong>{{ activeInterfaceScenario.name }}</strong>
          <button
            v-if="isAdmin"
            class="scenario-base-edit"
            type="button"
            title="编辑场景名称与描述"
            @click="openScenarioMetaEditor"
          >
            <el-icon><Edit /></el-icon>
          </button>
        </div>
        <div class="scenario-base-description scenario-base-item">
          <span>场景描述</span>
          <strong>{{ activeInterfaceScenario.description || '-' }}</strong>
        </div>
        <div class="scenario-base-item">
          <span>步骤启用</span>
          <strong>{{ enabledInterfaceStepCount }} / {{ interfaceAutomationSteps.length }}</strong>
        </div>
      </section>

      <section v-else-if="activeScenarioTab === 'params'" class="scenario-panel">
        <div class="scenario-panel-head">
          <strong>场景变量</strong>
          <span>变量会在执行时注入到请求体和脚本上下文。</span>
        </div>
        <div class="scenario-variable-table">
          <div><span>Key</span><span>Value</span><span>Scope</span></div>
          <div v-for="(value, key) in scenarioVariables" :key="key">
            <strong>{{ key }}</strong>
            <el-input v-model="scenarioVariables[key]" />
            <span>Scenario</span>
          </div>
        </div>
      </section>

      <section v-else-if="activeScenarioTab === 'hooks'" class="scenario-panel scenario-hooks-panel">
        <div>
          <strong>前置操作</strong>
          <p>初始化 env、session、手机号、merchant 变量；校验当前用户登录状态。</p>
        </div>
        <div>
          <strong>后置操作</strong>
          <p>写入执行历史、刷新会话摘要、保留最近响应和错误信息。</p>
        </div>
      </section>

      <section v-else-if="activeScenarioTab === 'assertions'" class="scenario-panel">
        <div class="scenario-panel-head">
          <strong>统一断言</strong>
          <span>执行结果需要同时满足 HTTP、业务成功和 trace 信息。</span>
        </div>
        <div class="scenario-assertion-list">
          <label v-for="assertion in scenarioAssertions" :key="assertion.target">
            <el-checkbox v-model="assertion.enabled" />
            <strong>{{ assertion.target }}</strong>
            <span>{{ assertion.rule }}</span>
          </label>
        </div>
      </section>

      <section v-else-if="activeScenarioTab === 'history'" class="scenario-panel">
        <div class="scenario-panel-head">
          <strong>执行历史</strong>
          <span>执行记录保存在服务端，按当前账号加载。</span>
          <el-button size="small" :loading="scenarioHistoryLoading" @click="loadScenarioExecutionHistory()">刷新</el-button>
        </div>
        <div v-if="scenarioHistoryError" role="alert" class="scenario-empty">{{ scenarioHistoryError }}</div>
        <div v-else-if="scenarioExecutionHistory.length === 0" class="scenario-empty">{{ scenarioHistoryLoading ? '加载执行历史中…' : '暂无执行历史。' }}</div>
        <el-button v-if="scenarioHistoryHasMore" size="small" :loading="scenarioHistoryLoading" @click="loadScenarioExecutionHistory(true)">加载更多</el-button>
        <div v-for="item in scenarioExecutionHistory" :key="item.id" class="scenario-history-row">
          <el-tag :type="item.status === '完成' ? 'success' : item.status === '未执行' ? 'warning' : 'danger'" effect="plain">{{ item.status }}</el-tag>
          <strong>{{ item.scenario }}</strong>
          <span>{{ item.env }}</span>
          <span>{{ item.at }}</span>
          <span>成功 {{ item.success }} / 跳过 {{ item.skipped }} / 失败 {{ item.failed }}</span>
          <code>{{ item.duration }}</code>
          <el-button size="small" plain @click="openScenarioHistoryDetail(item)">详情</el-button>
        </div>
      </section>

      <section v-else-if="activeScenarioTab === 'settings'" class="scenario-panel scenario-settings-panel">
        <label><span>失败后停止</span><el-switch v-model="scenarioSettings.stopOnFailure" /></label>
        <label><span>保存响应详情</span><el-switch v-model="scenarioSettings.saveResponse" /></label>
        <label><span>执行前校验 session</span><el-switch v-model="scenarioSettings.validateSession" /></label>
        <label><span>默认超时</span><el-input v-model="scenarioSettings.timeout" /></label>
      </section>
      </template>

      <template v-else-if="selectedInterfaceStep && (interfacePageMode === 'debug' || (interfacePageMode === 'scenario' && interfaceFocusMode === 'step'))">
        <section class="step-editor">
          <div v-if="interfacePageMode === 'debug'" class="debug-request-console">
            <div class="debug-request-console-head">
              <div>
                <strong>单接口调试</strong>
                <span>{{ selectedInterfaceStep.title }}</span>
              </div>
              <div class="debug-request-state">
                <span
                  class="step-editor-status"
                  :class="`is-${scenarioStepStatus(selectedInterfaceStep.key)}`"
                >
                  {{ scenarioStepStatus(selectedInterfaceStep.key) === 'success' ? '成功' : scenarioStepStatus(selectedInterfaceStep.key) === 'error' ? '失败' : '未执行' }}
                </span>
                <span v-if="scenarioStepResults[selectedInterfaceStep.key]?.durationMs != null" class="step-editor-duration">
                  {{ formatStepDuration(scenarioStepResults[selectedInterfaceStep.key].durationMs) }}
                </span>
              </div>
            </div>
            <div class="debug-request-urlbar">
              <el-select model-value="HTTP" class="debug-protocol-select" disabled>
                <el-option label="HTTP" value="HTTP" />
              </el-select>
              <el-select v-model="debugActualMethod" class="debug-method-select">
                <el-option label="GET" value="GET" />
                <el-option label="POST" value="POST" />
                <el-option label="PUT" value="PUT" />
                <el-option label="PATCH" value="PATCH" />
                <el-option label="DELETE" value="DELETE" />
              </el-select>
              <el-input
                v-model.trim="debugActualUrlText"
                class="debug-url-input"
                placeholder="https://dpu-gateway-reg.dowsure.com/..."
              />
              <button
                class="step-editor-send"
                type="button"
                :disabled="debugSending"
                @click="handleDebugStepRun"
              >
                <el-icon><Promotion /></el-icon>
                <span>{{ debugSending ? '发送中' : '服务端执行' }}</span>
              </button>
              <button class="step-editor-send is-plain" type="button" :disabled="debugSending" @click="resetDebugRequestDraft()">
                <el-icon><Refresh /></el-icon>
                <span>重置</span>
              </button>
            </div>
          </div>
          <div v-else class="step-editor-head">
            <span class="step-editor-method" :class="methodBadgeClass(selectedInterfaceStep)">
              {{ selectedInterfaceStep.type === 'script' ? 'SCRIPT' : (selectedInterfaceStep.method || 'POST') }}
            </span>
            <code class="step-editor-endpoint" :title="selectedInterfaceStep.endpoint">{{ selectedInterfaceStep.endpoint }}</code>
            <span
              class="step-editor-status"
              :class="`is-${scenarioStepStatus(selectedInterfaceStep.key)}`"
            >
              {{ scenarioStepStatus(selectedInterfaceStep.key) === 'success' ? '成功' : scenarioStepStatus(selectedInterfaceStep.key) === 'error' ? '失败' : '未执行' }}
            </span>
            <span v-if="scenarioStepResults[selectedInterfaceStep.key]?.durationMs != null" class="step-editor-duration">
              {{ formatStepDuration(scenarioStepResults[selectedInterfaceStep.key].durationMs) }}
            </span>
            <button
              v-if="interfacePageMode === 'debug'"
              class="step-editor-send"
              type="button"
              :disabled="debugSending"
              @click="handleDebugStepRun"
            >
              <el-icon><Promotion /></el-icon>
              <span>{{ debugSending ? '发送中' : '发送' }}</span>
            </button>
            <button v-if="interfacePageMode === 'debug'" class="step-editor-send is-plain" type="button" :disabled="debugSending" @click="resetDebugRequestDraft()">
              <el-icon><Refresh /></el-icon>
              <span>重置</span>
            </button>
          </div>

          <h3 class="step-editor-title">{{ selectedInterfaceStep.title }}</h3>
          <p class="step-editor-desc">{{ getScenarioStepDescription(selectedInterfaceStep).description }}</p>
          <el-alert
            v-if="debugRequestError"
            class="debug-request-alert"
            type="error"
            :title="debugRequestError"
            show-icon
            :closable="false"
          />

          <div class="step-editor-tabs">
            <button
              v-for="tab in activeStepEditorTabs"
              :key="tab.key"
              type="button"
              :class="{ active: stepFocusTab === tab.key }"
              @click="stepFocusTab = tab.key"
            >{{ tab.label }}</button>
          </div>

          <section v-if="stepFocusTab === 'params'" class="step-editor-panel">
            <div class="scenario-description-grid">
              <div>
                <span>Method</span>
                <code>{{ getScenarioStepDescription(selectedInterfaceStep).method }}</code>
              </div>
              <div>
                <span>Endpoint</span>
                <code>{{ getScenarioStepDescription(selectedInterfaceStep).endpoint }}</code>
              </div>
              <div>
                <span>Fields</span>
                <strong>
                  {{ (selectedInterfaceStep.fields?.length || getScenarioStepDescription(selectedInterfaceStep).fieldCount) }} 个参数
                </strong>
              </div>
            </div>

            <div v-if="interfacePageMode === 'debug'" class="debug-source-summary">
              <strong>接口来源</strong>
              <span
                v-for="source in selectedInterfaceStep.debugSources || []"
                :key="`debug-source-${selectedInterfaceStep.key}-${source.scenarioKey}-${source.stepKey}`"
              >{{ source.scenarioName }} #{{ source.order }}</span>
            </div>

            <!-- Configurable fields (saved per user, used on next run) -->
            <template v-else-if="selectedInterfaceStep.fields?.length">
              <div class="scenario-step-config-form">
                <div
                  v-for="field in selectedInterfaceStep.fields"
                  v-show="isStepFieldVisible(field, getScenarioStepOverrideDraft(activeInterfaceScenario.key, selectedInterfaceStep))"
                  :key="`step-config-${selectedInterfaceStep.key}-${field.key}`"
                  class="scenario-step-config-row"
                >
                  <label>
                    <span>{{ field.label }}</span>
                    <code>{{ field.key }}</code>
                  </label>
                  <el-select
                    v-if="field.type === 'select'"
                    v-model="getScenarioStepOverrideDraft(activeInterfaceScenario.key, selectedInterfaceStep)[field.key]"
                    class="scenario-step-config-input"
                    :disabled="isStepFieldDisabled(field, getScenarioStepOverrideDraft(activeInterfaceScenario.key, selectedInterfaceStep))"
                  >
                    <el-option
                      v-for="option in field.options || []"
                      :key="`step-config-opt-${selectedInterfaceStep.key}-${field.key}-${option.value}`"
                      :label="option.label"
                      :value="option.value"
                    />
                  </el-select>
                  <el-input
                    v-else-if="field.type === 'number'"
                    v-model.number="getScenarioStepOverrideDraft(activeInterfaceScenario.key, selectedInterfaceStep)[field.key]"
                    type="number"
                    class="scenario-step-config-input"
                    :disabled="isStepFieldDisabled(field, getScenarioStepOverrideDraft(activeInterfaceScenario.key, selectedInterfaceStep))"
                  />
                  <el-input
                    v-else-if="field.type === 'textarea'"
                    v-model="getScenarioStepOverrideDraft(activeInterfaceScenario.key, selectedInterfaceStep)[field.key]"
                    type="textarea"
                    :autosize="field.autosize || { minRows: 4, maxRows: 10 }"
                    :placeholder="field.placeholder || ''"
                    class="scenario-step-config-input"
                    :disabled="isStepFieldDisabled(field, getScenarioStepOverrideDraft(activeInterfaceScenario.key, selectedInterfaceStep))"
                  />
                  <el-input
                    v-else
                    v-model="getScenarioStepOverrideDraft(activeInterfaceScenario.key, selectedInterfaceStep)[field.key]"
                    class="scenario-step-config-input"
                    :disabled="isStepFieldDisabled(field, getScenarioStepOverrideDraft(activeInterfaceScenario.key, selectedInterfaceStep))"
                  />
                  <small v-if="field.hint" class="scenario-step-config-note">{{ field.hint }}</small>
                </div>
              </div>
              <div v-if="isAuthenticated" class="scenario-step-config-actions">
                <el-button
                  type="primary"
                  :loading="scenarioStepOverrideSaving[scenarioStepOverrideKey(activeInterfaceScenario.key, selectedInterfaceStep.key)]"
                  @click="saveScenarioStepOverrideForStep(activeInterfaceScenario.key, selectedInterfaceStep)"
                >保存参数</el-button>
                <el-button
                  plain
                  :disabled="!scenarioStepOverrides[scenarioStepOverrideKey(activeInterfaceScenario.key, selectedInterfaceStep.key)]"
                  @click="resetScenarioStepOverrideForStep(activeInterfaceScenario.key, selectedInterfaceStep)"
                >重置为默认</el-button>
                <span
                  v-if="scenarioStepOverrides[scenarioStepOverrideKey(activeInterfaceScenario.key, selectedInterfaceStep.key)]"
                  class="scenario-step-config-hint"
                >已保存自定义参数，下次执行场景会自动使用</span>
                <span v-else class="scenario-step-config-hint">未保存，执行时使用默认值</span>
              </div>
              <div v-else class="scenario-step-config-actions">
                <span class="scenario-step-config-hint">
                  {{ scenarioStepOverrides[scenarioStepOverrideKey(activeInterfaceScenario.key, selectedInterfaceStep.key)]
                    ? '当前使用已保存参数（只读）'
                    : '当前使用默认参数（登录后可修改并保存）' }}
                </span>
              </div>
            </template>
            <div v-else-if="getScenarioStepDescription(selectedInterfaceStep).fields.length" class="scenario-field-summary">
              <div
                v-for="field in getScenarioStepDescription(selectedInterfaceStep).fields"
                :key="`step-editor-field-${selectedInterfaceStep.key}-${field.prop}`"
              >
                <strong>{{ field.label }}</strong>
                <code>{{ field.prop }}</code>
                <span>{{ field.type }}</span>
              </div>
            </div>
            <div v-else class="response-empty">该步骤没有可配置参数。</div>
            <div v-if="interfacePageMode !== 'debug' && isAdmin && selectedInterfaceStep" class="scenario-step-admin-actions">
              <el-button
                plain
                :icon="Plus"
                @click="openScenarioAddStep(activeInterfaceScenario, selectedInterfaceStep)"
              >添加步骤</el-button>
              <el-button
                plain
                :icon="Edit"
                @click="openScenarioStepMetaEditor(activeInterfaceScenario, selectedInterfaceStep)"
              >编辑步骤</el-button>
              <el-button
                plain
                type="danger"
                :icon="Delete"
                @click="hideScenarioStepMeta(activeInterfaceScenario, selectedInterfaceStep)"
              >删除步骤</el-button>
            </div>
          </section>

          <section v-else-if="stepFocusTab === 'body'" class="step-editor-panel response-block">
            <div class="response-block-head">
              <strong>MockAPI Request Body</strong>
              <el-tag size="small" effect="plain">本地封装层预览</el-tag>
            </div>
            <pre>{{ JSON.stringify(getDebugStepPayload(selectedInterfaceStep), null, 2) }}</pre>
          </section>

          <section v-else-if="stepFocusTab === 'headers'" class="step-editor-panel response-block">
            <div class="response-block-head">
              <strong>MockAPI Request Headers</strong>
              <el-tag size="small" effect="plain">本地封装层预览</el-tag>
            </div>
            <pre>{{ JSON.stringify({ 'Content-Type': 'application/json' }, null, 2) }}</pre>
          </section>

          <section v-else-if="stepFocusTab === 'response'" class="step-editor-panel response-block">
            <div class="response-block-head">
              <strong>Response</strong>
              <el-tag
                size="small"
                :type="getScenarioResponseState(selectedInterfaceStep).type"
                effect="plain"
              >{{ getScenarioResponseState(selectedInterfaceStep).label }}</el-tag>
              <span v-if="scenarioStepResults[selectedInterfaceStep.key]?.durationMs != null" class="response-meta">
                {{ formatStepDuration(scenarioStepResults[selectedInterfaceStep.key].durationMs) }}
              </span>
              <button
                v-if="getScenarioStepResponse(selectedInterfaceStep)"
                class="response-copy"
                type="button"
                title="复制响应"
                @click="copyResponseText(getScenarioStepResponse(selectedInterfaceStep))"
              >
                <el-icon><DocumentCopy /></el-icon>
                <span>复制</span>
              </button>
            </div>
            <pre v-if="getScenarioStepResponse(selectedInterfaceStep)">{{ JSON.stringify(getScenarioStepResponse(selectedInterfaceStep), null, 2) }}</pre>
            <div v-else class="response-empty">执行该步骤后在这里查看最新响应。</div>
          </section>

          <section v-else-if="stepFocusTab === 'actualBody'" class="step-editor-panel response-block">
            <div class="response-block-head">
              <strong>实际请求体</strong>
              <div class="response-block-actions">
                <el-tag size="small" effect="plain">{{ interfacePageMode === 'debug' ? '编辑上游 URL 和 body 后发送' : '场景执行时发往上游的真实 body' }}</el-tag>
                <button
                  v-if="interfacePageMode === 'debug'"
                  class="response-copy"
                  type="button"
                  title="格式化 JSON"
                  @click="prettifyDebugJsonDraft('body')"
                >
                  <span>格式化 JSON</span>
                </button>
              </div>
            </div>
            <template v-if="interfacePageMode === 'debug'">
              <el-input
                v-model="debugRequestBodyText"
                type="textarea"
                :autosize="{ minRows: 18, maxRows: 34 }"
                class="debug-json-editor"
                spellcheck="false"
                placeholder="{ }"
              />
            </template>
            <template v-else-if="getScenarioStepActualRequests(selectedInterfaceStep).length">
              <div
                v-for="(req, idx) in getScenarioStepActualRequests(selectedInterfaceStep)"
                :key="`actual-body-${selectedInterfaceStep.key}-${idx}`"
                class="actual-request-item"
              >
                <div class="actual-request-meta">
                  <el-tag
                    v-if="getScenarioStepActualRequests(selectedInterfaceStep).length > 1"
                    size="small"
                    effect="plain"
                  >#{{ idx + 1 }}</el-tag>
                  <code class="actual-request-method">{{ req.method || 'POST' }}</code>
                  <span class="actual-request-url">{{ req.url || '-' }}</span>
                </div>
                <pre>{{ req.body == null ? '(无 body)' : (typeof req.body === 'string' ? req.body : JSON.stringify(req.body, null, 2)) }}</pre>
              </div>
            </template>
            <div v-else class="response-empty">执行该步骤后可在这里查看真正发往上游的请求体。</div>
          </section>

          <section v-else-if="stepFocusTab === 'actualHeaders'" class="step-editor-panel response-block">
            <div class="response-block-head">
              <strong>实际请求头</strong>
              <div class="response-block-actions">
                <el-tag size="small" effect="plain">{{ interfacePageMode === 'debug' ? '编辑发往上游的 headers' : '场景执行时发往上游的真实 headers' }}</el-tag>
                <button
                  v-if="interfacePageMode === 'debug'"
                  class="response-copy"
                  type="button"
                  title="格式化 JSON"
                  @click="prettifyDebugJsonDraft('headers')"
                >
                  <span>格式化 JSON</span>
                </button>
              </div>
            </div>
            <template v-if="interfacePageMode === 'debug'">
              <el-input
                v-model="debugRequestHeadersText"
                type="textarea"
                :autosize="{ minRows: 14, maxRows: 28 }"
                class="debug-json-editor"
                spellcheck="false"
                placeholder="{ }"
              />
            </template>
            <template v-else-if="getScenarioStepActualRequests(selectedInterfaceStep).length">
              <div
                v-for="(req, idx) in getScenarioStepActualRequests(selectedInterfaceStep)"
                :key="`actual-headers-${selectedInterfaceStep.key}-${idx}`"
                class="actual-request-item"
              >
                <div class="actual-request-meta">
                  <el-tag
                    v-if="getScenarioStepActualRequests(selectedInterfaceStep).length > 1"
                    size="small"
                    effect="plain"
                  >#{{ idx + 1 }}</el-tag>
                  <code class="actual-request-method">{{ req.method || 'POST' }}</code>
                  <span class="actual-request-url">{{ req.url || '-' }}</span>
                </div>
                <pre>{{ req.headers ? JSON.stringify(req.headers, null, 2) : '(无 headers)' }}</pre>
              </div>
            </template>
            <div v-else class="response-empty">执行该步骤后可在这里查看真正发往上游的请求头。</div>
          </section>

          <section v-else-if="stepFocusTab === 'actualQuery'" class="step-editor-panel response-block">
            <div class="response-block-head">
              <strong>Query</strong>
              <div class="response-block-actions">
                <el-tag size="small" effect="plain">发送时会拼接到实际上游 URL</el-tag>
                <button
                  class="response-copy"
                  type="button"
                  title="格式化 JSON"
                  @click="prettifyDebugJsonDraft('query')"
                >
                  <span>格式化 JSON</span>
                </button>
              </div>
            </div>
            <el-input
              v-model="debugRequestQueryText"
              type="textarea"
              :autosize="{ minRows: 10, maxRows: 22 }"
              class="debug-json-editor"
              spellcheck="false"
              placeholder="{ }"
            />
          </section>

          <section v-else-if="stepFocusTab === 'actualResponse'" class="step-editor-panel response-block">
            <div class="response-block-head">
              <strong>实际响应体</strong>
              <el-tag size="small" effect="plain">上游返回的真实 body</el-tag>
            </div>
            <template v-if="getScenarioStepActualResponses(selectedInterfaceStep).length">
              <div
                v-for="(resp, idx) in getScenarioStepActualResponses(selectedInterfaceStep)"
                :key="`actual-response-${selectedInterfaceStep.key}-${idx}`"
                class="actual-request-item"
              >
                <div class="actual-request-meta">
                  <el-tag
                    v-if="getScenarioStepActualResponses(selectedInterfaceStep).length > 1"
                    size="small"
                    effect="plain"
                  >#{{ idx + 1 }}</el-tag>
                  <code class="actual-request-method">{{ resp.status_code || 'HTTP' }}</code>
                  <span class="actual-request-url">response body</span>
                </div>
                <pre>{{ resp.body == null ? '(无 body)' : (typeof resp.body === 'string' ? resp.body : JSON.stringify(resp.body, null, 2)) }}</pre>
              </div>
            </template>
            <div v-else class="response-empty">执行该步骤后可在这里查看真正的上游响应体。</div>
          </section>

          <section v-else-if="stepFocusTab === 'actualResponseHeaders'" class="step-editor-panel response-block">
            <div class="response-block-head">
              <strong>实际响应头</strong>
              <el-tag size="small" effect="plain">上游返回的真实 headers</el-tag>
            </div>
            <template v-if="getScenarioStepActualResponses(selectedInterfaceStep).length">
              <div
                v-for="(resp, idx) in getScenarioStepActualResponses(selectedInterfaceStep)"
                :key="`actual-response-headers-${selectedInterfaceStep.key}-${idx}`"
                class="actual-request-item"
              >
                <div class="actual-request-meta">
                  <el-tag
                    v-if="getScenarioStepActualResponses(selectedInterfaceStep).length > 1"
                    size="small"
                    effect="plain"
                  >#{{ idx + 1 }}</el-tag>
                  <code class="actual-request-method">{{ resp.status_code || 'HTTP' }}</code>
                  <span class="actual-request-url">response headers</span>
                </div>
                <pre>{{ resp.headers ? JSON.stringify(resp.headers, null, 2) : '(无 headers)' }}</pre>
              </div>
            </template>
            <div v-else class="response-empty">执行该步骤后可在这里查看真正的上游响应头。</div>
          </section>

          <section v-else-if="stepFocusTab === 'logic'" class="step-editor-panel response-block">
            <div class="response-block-head">
              <strong>底层逻辑</strong>
              <el-tag size="small" effect="plain">语言：{{ getScenarioStepLogic(selectedInterfaceStep)?.language || 'Python' }}</el-tag>
            </div>
            <div
              v-if="scenarioStepSourceLoading[getScenarioStepSourceEndpoint(selectedInterfaceStep)]"
              class="response-empty"
            >正在读取后端 Python 源码...</div>
            <div
              v-else-if="scenarioStepSourceErrors[getScenarioStepSourceEndpoint(selectedInterfaceStep)]"
              class="response-empty"
            >{{ scenarioStepSourceErrors[getScenarioStepSourceEndpoint(selectedInterfaceStep)] }}</div>
            <template v-else-if="getScenarioStepLogic(selectedInterfaceStep)?.blocks?.length">
              <div
                v-for="(block, idx) in getScenarioStepLogic(selectedInterfaceStep).blocks"
                :key="`step-source-${selectedInterfaceStep.key}-${idx}`"
                class="scenario-source-card"
              >
                <div class="scenario-source-meta">
                  <strong>{{ block.title }}</strong>
                  <span>{{ block.file }}:{{ block.start_line }}</span>
                  <code>{{ block.function }}</code>
                </div>
                <pre>{{ block.source }}</pre>
              </div>
            </template>
            <div v-else class="response-empty">这个步骤没有匹配到后端路由源码。</div>
          </section>
        </section>
      </template>

      <section v-else-if="interfacePageMode === 'report'" class="scenario-panel">
        <div class="scenario-panel-head">
          <strong>执行历史</strong>
          <span>执行记录保存在服务端，按当前账号加载。</span>
          <el-button size="small" :loading="scenarioHistoryLoading" @click="loadScenarioExecutionHistory()">刷新</el-button>
        </div>
        <div v-if="scenarioHistoryError" role="alert" class="scenario-empty">{{ scenarioHistoryError }}</div>
        <div v-else-if="scenarioExecutionHistory.length === 0" class="scenario-empty">{{ scenarioHistoryLoading ? '加载执行历史中…' : '暂无执行历史。' }}</div>
        <el-button v-if="scenarioHistoryHasMore" size="small" :loading="scenarioHistoryLoading" @click="loadScenarioExecutionHistory(true)">加载更多</el-button>
        <div v-for="item in scenarioExecutionHistory" :key="item.id" class="scenario-history-row">
          <el-tag :type="item.status === '完成' ? 'success' : item.status === '未执行' ? 'warning' : 'danger'" effect="plain">{{ item.status }}</el-tag>
          <strong>{{ item.scenario }}</strong>
          <span>{{ item.env }}</span>
          <span>{{ item.at }}</span>
          <span>成功 {{ item.success }} / 跳过 {{ item.skipped }} / 失败 {{ item.failed }}</span>
          <code>{{ item.duration }}</code>
          <el-button size="small" plain @click="openScenarioHistoryDetail(item)">详情</el-button>
        </div>
      </section>
    </main>
  </div>

  <el-dialog v-model="scenarioMetaEditVisible" title="编辑场景信息" width="520px" append-to-body>
    <el-form label-position="top">
      <el-form-item label="场景名称">
        <el-input v-model="scenarioMetaEditForm.name" placeholder="场景显示名" maxlength="120" show-word-limit />
      </el-form-item>
      <el-form-item label="场景描述">
        <el-input
          v-model="scenarioMetaEditForm.description"
          type="textarea"
          :rows="4"
          placeholder="场景说明，例如：完整 FP USD 500K 接口自动化场景"
          maxlength="600"
          show-word-limit
        />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="scenarioMetaEditVisible = false">取消</el-button>
      <el-button type="primary" :loading="scenarioMetaEditSaving" @click="saveScenarioMetaEditor">保存</el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="scenarioStepMetaEditVisible" title="编辑步骤" width="520px" append-to-body>
    <el-form label-position="top">
      <el-form-item label="步骤名称">
        <el-input v-model="scenarioStepMetaEditForm.title" placeholder="步骤显示名" maxlength="120" show-word-limit />
      </el-form-item>
      <el-form-item label="步骤描述">
        <el-input
          v-model="scenarioStepMetaEditForm.description"
          type="textarea"
          :rows="4"
          placeholder="步骤说明，仅影响前端展示"
          maxlength="600"
          show-word-limit
        />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button
        plain
        :loading="scenarioStepMetaEditDeleting"
        @click="resetScenarioStepMetaEditor"
      >恢复默认</el-button>
      <el-button @click="scenarioStepMetaEditVisible = false">取消</el-button>
      <el-button type="primary" :loading="scenarioStepMetaEditSaving" @click="saveScenarioStepMetaEditor">保存</el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="scenarioAddStepVisible" title="在下一步添加步骤" width="520px" append-to-body>
    <el-form label-position="top">
      <el-form-item label="复制哪个步骤">
        <el-select v-model="scenarioAddStepForm.sourceStepKey" style="width: 100%">
          <el-option
            v-for="step in (interfaceScenarios.find((item) => item.key === scenarioAddStepForm.scenarioKey)?.steps || [])"
            :key="`add-source-${step.key}`"
            :label="step.title"
            :value="step.key"
          />
        </el-select>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="scenarioAddStepVisible = false">取消</el-button>
      <el-button type="primary" @click="addScenarioStepAfter">添加到草稿</el-button>
    </template>
  </el-dialog>
</section>
</template>

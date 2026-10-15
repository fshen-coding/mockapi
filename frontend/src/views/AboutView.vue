<script setup>
import PageHeader from '../components/PageHeader.vue'

defineEmits(['back'])
</script>

<template>
  <section class="tool-page-view about-page-view">
    <PageHeader
      eyebrow="About"
      title="关于我们"
      description="Mock API 操作台用于统一管理测试账号、会话上下文、DPU 状态模拟、日志检索和问题协作。"
      @back="$emit('back')"
    />

    <el-card shadow="never" class="surface-card tool-page-card help-page-card">
      <div class="help-section help-callout">
        <h3>工具定位</h3>
        <p>Mock API 操作台是面向 DPU 测试、联调和回归验证的内部控制台。它把账号注册、session 连接、workflow webhook 模拟、实时日志、历史日志检索和问题交接集中在同一个页面，减少脚本切换、手工拼请求和环境信息遗漏。</p>
        <p>页面设计以执行效率和可追溯性为优先：所有关键操作都围绕当前环境、手机号、session、merchant 和接口结果展开，便于测试人员、研发和支持同学在同一上下文中定位问题。</p>
      </div>
      <div class="help-section">
        <h3>适用场景</h3>
        <ol>
          <li>新建 SIT、UAT、REG 等环境的测试账号，并快速进入可执行 mock 的状态。</li>
          <li>在指定 session 下模拟核保、审批、PSP、电子签、放款、还款、多店铺等 DPU 业务状态。</li>
          <li>联调或回归时复现某个 webhook 节点，确认请求 URL、请求体、响应体和业务错误。</li>
          <li>排查“页面显示成功但业务状态未推进”“接口 200 但业务失败”“session 失效或环境选错”等问题。</li>
          <li>将问题现场沉淀到“联系我们”，让管理员或后续处理人能基于相同上下文继续跟进。</li>
        </ol>
      </div>
      <div class="help-section">
        <h3>标准使用流程</h3>
        <ol>
          <li>在“连接与注册”选择目标环境，输入手机号连接已有 session，或按 Journey、币种、资方代码注册新账号。</li>
          <li>确认右侧“当前会话”中的环境、手机号、Merchant 等信息，避免跨环境或跨账号误操作。</li>
          <li>进入“Mock 操作面板”，选择需要推进的业务节点，填写金额、状态、失败原因或 state 等参数。</li>
          <li>执行后查看当前步骤下方的返回结果，同时进入“使用日志”确认请求已被记录。</li>
          <li>如果结果异常，可先在“使用日志”查看操作请求和响应；需要确认环境可用性时进入“环境监测”。</li>
          <li>需要交接时，在“联系我们”记录现象、预期、复现步骤、手机号、session、关键日志和截图线索。</li>
        </ol>
      </div>
      <div class="help-section">
        <h3>核心模块能力</h3>
        <dl>
          <dt>连接与注册</dt>
          <dd>用于创建或连接测试账号上下文。注册支持 Journey、币种、资方代码和线上/线下模式选择；连接成功后会建立 session，后续 mock 操作都会绑定这个上下文。</dd>
          <dt>Mock 操作面板</dt>
          <dd>集中触发 DPU 关键业务节点，包括 SP/3PL 关联、核保、审批、PSP started/completed、电子签、放款、还款、系统事件和 Abandon。每个操作保留独立参数区，降低误填风险。</dd>
          <dt>使用日志</dt>
          <dd>用于追溯账号操作记录，重点查看每次 mock 操作的请求参数、响应结果、执行账号、手机号、session 和 merchant。</dd>
          <dt>环境监测</dt>
          <dd>用于查看 dev、reg、sit、uat、preprod 网关可用性、响应延迟和近期状态条，辅助判断是否为环境波动。</dd>
          <dt>AI 助手</dt>
          <dd>用于辅助分析当前 session、日志和 mock 结果，也可以帮助整理 SQL、接口现象和排查思路。AI 输出只作为诊断辅助，关键业务结论仍应以接口返回、日志和数据库状态为准。</dd>
          <dt>联系我们</dt>
          <dd>用于异步交接问题现场。建议写清楚环境、手机号、session、已执行步骤、预期状态、实际状态、错误日志和截图信息，方便管理员或后续处理人快速接手。</dd>
          <dt>管理员登录</dt>
          <dd>管理员入口已调整为“回复问题”，用于集中查看和回复已提交的问题，适合团队内部维护待处理事项、补充处理结论和保留协作记录。</dd>
        </dl>
      </div>
      <div class="help-section">
        <h3>数据与安全边界</h3>
        <dl>
          <dt>环境隔离</dt>
          <dd>执行前必须确认当前环境。SIT、UAT、REG、DEV、PREPROD 的数据和网关地址不同，跨环境使用手机号或 session 会导致误判。</dd>
          <dt>测试数据</dt>
          <dd>本工具面向测试和联调用例，不应输入真实客户敏感信息。需要生产或迁移相关操作时，应按专项流程和授权要求执行。</dd>
          <dt>结果判定</dt>
          <dd>按钮执行成功只代表接口调用完成，不等同于完整业务链路成功。关键节点应结合返回体、使用日志和必要的数据库状态共同确认。</dd>
          <dt>审计线索</dt>
          <dd>使用日志用于辅助追溯，但不替代正式测试报告。重要验证结论仍应沉淀到 MeterSphere、缺陷单或版本验证记录中。</dd>
        </dl>
      </div>
      <div class="help-section">
        <h3>协作建议</h3>
        <dl>
          <dt>复现问题</dt>
          <dd>先固定环境、手机号、session 和执行时间窗口，再描述失败节点。不要只写“失败了”，应说明停在哪一步、期望推进到哪一步。</dd>
          <dt>提交信息</dt>
          <dd>优先提供可直接排查的信息：环境、手机号、session_id、merchant_id、接口名称、请求时间、traceId、关键响应体和截图。</dd>
          <dt>处理结论</dt>
          <dd>管理员回复时建议包含原因判断、已采取动作、是否需要重试、是否需要研发介入，以及后续验证标准。</dd>
        </dl>
      </div>
    </el-card>
  </section>
</template>

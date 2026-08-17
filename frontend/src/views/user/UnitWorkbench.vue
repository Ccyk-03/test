<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'

import { deleteRecord, getUnitHistory, listUnits, renameRecord, renameUnit } from '../../api/units'
import { useConversationStore } from '../../stores/conversation'
import { useUserStore } from '../../stores/user'
import { formatTime } from '../../utils/format'

const route = useRoute()
const router = useRouter()
const store = useUserStore()
const conversationStore = useConversationStore()

const unitNo = computed(() => {
  const n = Number(route.params.unitNo)
  return n >= 1 && n <= 6 ? n : 1
})

const units = ref([])
const running = ref(false)
const result = ref(null)       // 工作区当前展示的结果（流式输出时实时更新）
const history = ref([])        // 当前任务 + 当前单元的历史记录（左侧功能栏）

// 本单元是否已成功生成过：是则下方主按钮变为「进入下一单元」（单元 6 则为「完成」）
// 本单元当前是否已成功生成（以最近一次记录为准）：
// 成功 → 主按钮为「进入下一单元」（单元 6 为「完成」）；
// 未生成或最近一次失败 → 主按钮为「执行优化」（可重试）。
const hasGenerated = computed(() => history.value.length > 0 && history.value[0].status === 'success')
const completingTask = ref(false)
const isTaskCompleted = computed(() => !!conversationStore.current?.completed_at)

// 单元 6 生成完 → 点「完成」保存当前任务进度
async function handleCompleteTask() {
  await ElMessageBox.confirm(
    `确认完成任务 #${conversationStore.conversationNo}？完成进度将保存，之后仍可随时查看。`,
    '完成任务',
    { type: 'success', confirmButtonText: '完成', cancelButtonText: '取消' },
  )
  completingTask.value = true
  try {
    await conversationStore.completeCurrent()
    ElMessage.success(`任务 #${conversationStore.conversationNo} 已完成，进度已保存`)
  } catch {
    // 错误提示由请求拦截器统一展示
  } finally {
    completingTask.value = false
  }
}

const form = reactive({
  input_prompt: '',
})

// ---- 修改流程（两段式对话框）----
const reviseDialog1 = ref(false)   // 对话框 1：上一次生成的最终提示词
const reviseDialog2 = ref(false)   // 对话框 2：需要修改的提示词
const revisePrev = ref('')         // 对话框 1 内容（预填 T_{n-1}）
const revisePrompt = ref('')       // 对话框 2 内容
const reviseLoadingPrev = ref(false)

// ---- 记录重命名 / 删除 ----
const renameVisible = ref(false)
const renameTarget = ref(null)
const renameName = ref('')

// ---- 优化单元重命名（按用户存储显示名）----
const unitRenameVisible = ref(false)
const unitRenameName = ref('')

function openUnitRename() {
  unitRenameName.value = currentUnit.value?.name || ''
  unitRenameVisible.value = true
}

async function handleUnitRename() {
  if (!unitRenameName.value.trim()) {
    ElMessage.warning('请输入单元名称')
    return
  }
  await renameUnit(unitNo.value, unitRenameName.value.trim())
  ElMessage.success('单元已重命名')
  unitRenameVisible.value = false
  conversationStore.bumpUnits() // 通知顶部导航栏同步刷新
  await refresh()
}

const currentUnit = computed(() => units.value.find((u) => u.unit_no === unitNo.value))

// 基础模板来源的中文描述
function sourceLabel(source, chainedFrom) {
  if (source === 'chained') return `链式来自单元 ${chainedFrom} 的输出 T${chainedFrom}`
  if (source === 'manual') return '手动输入的上一次最终提示词'
  if (source === 'default') return '默认模板（无链式历史回退）'
  return '无基础模板（首次对话，结合 s1 指令）'
}

// 链式状态提示：单元 1、2 用 s1；单元 3-6 用 s2（基础模板按链式规则）
const chainInfo = computed(() => {
  if (unitNo.value === 1) {
    return { type: 'info', text: '结合 s1 指令直接优化，无基础模板' }
  }
  if (unitNo.value === 2) {
    return { type: 'info', text: '结合 s1 指令，基础模板自动使用单元 1 的优化输出 T1' }
  }
  const u = units.value.find((x) => x.unit_no === unitNo.value)
  if (u?.has_chained_base) {
    return {
      type: 'success',
      text: `结合 s2 指令，基础模板将自动使用您在单元 ${unitNo.value - 1} 的优化输出 T${unitNo.value - 1}`,
    }
  }
  return {
    type: 'warning',
    text: `暂无单元 ${unitNo.value - 1} 的成功历史，本轮将回退使用本单元默认模板`,
  }
})

async function refresh() {
  await conversationStore.ensure()
  // 尚未选择任何任务（任务选择对话框未确定）：工作区保持空态
  if (!conversationStore.conversationNo) {
    units.value = []
    history.value = []
    result.value = null
    return
  }
  units.value = await listUnits(conversationStore.conversationNo)
  // 左侧记录栏：仅显示当前任务 + 当前单元的历史记录
  history.value = await getUnitHistory(unitNo.value, 10, conversationStore.conversationNo)
  // 自动把最近一次运行结果展示到上方工作区（页面刷新/进入单元时结果直接可见）
  if (!result.value && history.value.length) {
    viewHistory(history.value[0], true)
  }
}

// 执行前兜底：极少数绕过对话框直接进入的场景下，自动创建任务 1
async function ensureTaskReady() {
  if (!conversationStore.conversationNo) {
    const conv = await conversationStore.startNew()
    ElMessage.info(`已创建任务 #${conv.conversation_no}`)
  }
}

// ---- 任务切换（顶栏切换器）：重置工作区并刷新为所选任务的数据 ----
watch(
  () => conversationStore.conversationNo,
  (newNo, oldNo) => {
    if (newNo && oldNo && newNo !== oldNo) {
      result.value = null
      form.input_prompt = ''
      running.value = false // 复位：防止上一次生成中断后按钮仍处于禁用
      refresh()
    }
  },
)

// ---- 流式请求（SSE）：后端 stream=1 时逐段返回输出，前端实时展示 ----
async function streamRequest(url, body, onDelta) {
  const resp = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${store.token}`,
    },
    body: JSON.stringify(body),
  })
  if (resp.status === 401) {
    store.logout()
    router.push('/login')
    throw new Error('登录已过期，请重新登录')
  }
  if (!resp.ok || !resp.body) {
    const data = await resp.json().catch(() => ({}))
    throw new Error(typeof data.detail === 'string' ? data.detail : `请求失败（HTTP ${resp.status}）`)
  }

  const reader = resp.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let meta = null

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    let idx
    while ((idx = buffer.indexOf('\n\n')) !== -1) {
      const raw = buffer.slice(0, idx)
      buffer = buffer.slice(idx + 2)
      for (const line of raw.split('\n')) {
        if (!line.startsWith('data: ')) continue
        const payload = JSON.parse(line.slice(6))
        if (payload.type === 'delta') {
          onDelta(payload.text)
        } else if (payload.type === 'meta') {
          meta = payload
        } else if (payload.type === 'error') {
          throw new Error(payload.message)
        }
      }
    }
  }
  return meta
}

async function handleRun() {
  if (!form.input_prompt.trim()) {
    ElMessage.warning('请先输入待优化提示词 t' + unitNo.value)
    return
  }
  await ensureTaskReady()
  const requestedUnit = unitNo.value
  const submittedInput = form.input_prompt.trim()
  running.value = true
  result.value = {
    unit_no: requestedUnit,
    action: 'optimize',
    input_prompt: submittedInput,
    output_text: '',
    base_template_source: null,
    chained_from_unit: null,
    model_name: '',
    usage: null,
    elapsed_ms: null,
  }
  try {
    const meta = await streamRequest(
      `/api/units/${requestedUnit}/run?stream=1`,
      { input_prompt: submittedInput, conversation_no: conversationStore.conversationNo },
      (text) => {
        if (unitNo.value === requestedUnit && result.value) result.value.output_text += text
      },
    )
    if (unitNo.value !== requestedUnit) return // 已切换单元，丢弃过期结果
    result.value.base_template_source = meta.base_template_source
    result.value.chained_from_unit = meta.chained_from_unit
    result.value.model_name = meta.model_name
    result.value.usage = meta.usage
    result.value.elapsed_ms = meta.elapsed_ms
    ElMessage.success(`单元 ${requestedUnit} 优化完成（耗时 ${meta.elapsed_ms} ms）`)
    form.input_prompt = '' // 输入完成自动清空输入框
    await refresh()
  } catch (e) {
    if (unitNo.value === requestedUnit) {
      ElMessage.error(e.message || '优化失败')
    }
  } finally {
    if (unitNo.value === requestedUnit) {
      running.value = false
    }
  }
}

// ---- 修改流程：点击「修改本单元」→ 对话框 1 → 对话框 2 → 结合 s3 修改 ----
async function openRevise() {
  revisePrompt.value = ''
  if (unitNo.value === 1) {
    // 单元 1 无上一对话：跳过对话框 1
    revisePrev.value = ''
    reviseDialog2.value = true
    return
  }
  // 预填：自动取同一对话内上一单元最近一次成功输出作为「上一次生成的最终提示词」
  revisePrev.value = ''
  reviseDialog1.value = true
  reviseLoadingPrev.value = true
  try {
    const prevHistory = await getUnitHistory(unitNo.value - 1, 1, conversationStore.conversationNo)
    if (prevHistory.length && prevHistory[0].status === 'success') {
      revisePrev.value = prevHistory[0].output_text || ''
    }
  } finally {
    reviseLoadingPrev.value = false
  }
}

function confirmDialog1() {
  if (!revisePrev.value.trim()) {
    ElMessage.warning('请输入上一次生成的最终提示词（或确认自动预填内容）')
    return
  }
  reviseDialog1.value = false
  reviseDialog2.value = true
}

async function handleRevise() {
  if (!revisePrompt.value.trim()) {
    ElMessage.warning('请输入需要修改的提示词')
    return
  }
  await ensureTaskReady()
  const requestedUnit = unitNo.value
  const submittedPrompt = revisePrompt.value.trim()
  reviseDialog2.value = false
  running.value = true
  result.value = {
    unit_no: requestedUnit,
    action: 'revise',
    input_prompt: submittedPrompt,
    output_text: '',
    base_template_source: null,
    chained_from_unit: null,
    model_name: '',
    usage: null,
    elapsed_ms: null,
  }
  try {
    const meta = await streamRequest(
      `/api/units/${requestedUnit}/revise?stream=1`,
      {
        previous_final_prompt: revisePrev.value,
        prompt_to_revise: submittedPrompt,
        conversation_no: conversationStore.conversationNo,
      },
      (text) => {
        if (unitNo.value === requestedUnit && result.value) result.value.output_text += text
      },
    )
    if (unitNo.value !== requestedUnit) return // 已切换单元，丢弃过期结果
    result.value.base_template_source = meta.base_template_source
    result.value.chained_from_unit = meta.chained_from_unit
    result.value.model_name = meta.model_name
    result.value.usage = meta.usage
    result.value.elapsed_ms = meta.elapsed_ms
    ElMessage.success(`单元 ${requestedUnit} 修改完成（结合 s3 指令，耗时 ${meta.elapsed_ms} ms）`)
    revisePrompt.value = '' // 修改完成后清空对话框输入
    await refresh()
  } catch (e) {
    if (unitNo.value === requestedUnit) {
      ElMessage.error(e.message || '修改失败')
    }
  } finally {
    if (unitNo.value === requestedUnit) {
      running.value = false
    }
  }
}

async function copyResult() {
  await navigator.clipboard.writeText(result.value.output_text)
  ElMessage.success('已复制优化结果')
}

function viewHistory(item, silent = false) {
  // 历史记录回看：在工作区展示该次结果（含当时的输入），不修改下方输入框
  // silent=true 用于页面加载时自动展示，不弹提示
  result.value = {
    unit_no: item.unit_no,
    action: item.action,
    input_prompt: item.input_prompt,
    output_text: item.output_text || '（该次运行失败，无输出）',
    base_template_source: item.base_template_source,
    chained_from_unit: item.base_template_source === 'chained' ? item.unit_no - 1 : null,
    base_template_preview: item.base_template ? item.base_template.slice(0, 200) : '',
    model_name: item.model_name || '',
    usage: {
      prompt_tokens: item.prompt_tokens,
      completion_tokens: item.completion_tokens,
      total_tokens: item.total_tokens,
    },
    elapsed_ms: item.elapsed_ms,
    created_at: item.created_at,
  }
  if (!silent) {
    ElMessage.info(`已载入 ${formatTime(item.created_at)} 的运行记录`)
  }
}

// 点击左侧记录：在工作区回看该次结果
function viewRecordFromList(item) {
  viewHistory(item)
}

function openRename(item) {
  renameTarget.value = item
  renameName.value = item.display_name || ''
  renameVisible.value = true
}

async function handleRename() {
  if (!renameName.value.trim()) {
    ElMessage.warning('请输入记录名称')
    return
  }
  await renameRecord(renameTarget.value.unit_no, renameTarget.value.id, renameName.value.trim())
  ElMessage.success('记录已重命名')
  renameVisible.value = false
  await refresh()
}

async function handleDelete(item) {
  await ElMessageBox.confirm(
    '确认删除该条任务记录？删除后左侧列表不再展示，但管理端审计中仍保留可查。',
    '删除确认',
    { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
  )
  const wasShown = result.value && result.value.created_at === item.created_at
  await deleteRecord(item.unit_no, item.id)
  ElMessage.success('记录已删除')
  if (wasShown) {
    result.value = null // 当前展示的记录被删除：清空后由 refresh 自动加载下一条
  }
  await refresh()
}

// 操作出口：进入下一流程层级（返回主界面在顶部导航栏）
function nextUnit() {
  if (unitNo.value < 6) {
    router.push(`/user/unit/${unitNo.value + 1}`)
  } else {
    router.push('/user/unit/1')
  }
}

// 切换单元时重置工作台：下方输入框清空（由用户自己输入），工作区自动加载该单元最近结果
watch(unitNo, () => {
  result.value = null
  form.input_prompt = ''
  running.value = false // 复位：防止流式生成中途切单元导致按钮永久禁用
  refresh()
})

onMounted(refresh)
</script>

<template>
  <div class="workbench">
    <!-- 左侧功能栏：对话切换 + 当前对话全部运行记录（点击可回看） -->
    <aside class="side-panel">
      <el-card shadow="never" class="side-card">
        <template #header>
          <span class="card-header">📋 任务 #{{ conversationStore.conversationNo }} · 单元 {{ unitNo }} 记录</span>
        </template>
        <div v-if="!history.length" class="side-empty">
          任务 #{{ conversationStore.conversationNo }} 暂无记录<br />执行优化后在此展示
        </div>
        <div
          v-for="h in history"
          :key="h.id"
          class="history-item"
          :class="{ active: result && result.created_at === h.created_at }"
          @click="viewRecordFromList(h)"
        >
          <div class="history-content">
            <div class="history-top">
              <el-tag :type="h.action === 'revise' ? 'warning' : 'primary'" size="small">
                {{ h.action === 'revise' ? '修改' : '优化' }}
              </el-tag>
              <el-tag :type="h.status === 'success' ? 'success' : 'danger'" size="small">
                {{ h.status === 'success' ? '成功' : '失败' }}
              </el-tag>
            </div>
            <div v-if="h.display_name" class="history-name">✏️ {{ h.display_name }}</div>
            <div class="history-time">{{ formatTime(h.created_at) }}</div>
            <div class="history-preview">{{ h.input_prompt.slice(0, 40) }}…</div>
          </div>
          <!-- 卡片右侧：两个按钮竖直排列（上：重命名，下：删除） -->
          <div class="history-actions" @click.stop>
            <el-button size="small" @click="openRename(h)">重命名</el-button>
            <el-button size="small" type="danger" plain @click="handleDelete(h)">删除</el-button>
          </div>
        </div>
      </el-card>
    </aside>

    <!-- 右侧主区：上方工作区 + 下方输入框 -->
    <main class="main-panel">
      <!-- 上方工作区：展示所有效果 -->
      <el-card shadow="never" class="workspace-card">
        <template #header>
          <div class="workspace-header">
            <div class="workspace-title">
              <el-tag type="info" effect="dark" size="small">任务 #{{ conversationStore.conversationNo }}</el-tag>
              <span class="unit-name">{{ currentUnit?.name || `单元 ${unitNo}` }}</span>
              <el-button link type="primary" size="small" @click="openUnitRename">✏️ 重命名</el-button>
              <el-tag v-if="result?.action === 'revise'" type="warning" size="small">修改模式 · s3 指令</el-tag>
              <el-tag
                v-if="result && result.base_template_source"
                :type="result.base_template_source === 'chained' ? 'success' : result.base_template_source === 'manual' ? 'warning' : 'info'"
                size="small"
              >
                {{ sourceLabel(result.base_template_source, result.chained_from_unit) }}
              </el-tag>
            </div>
            <div class="nav-btns">
              <el-button v-if="unitNo > 1" size="small" @click="router.push(`/user/unit/${unitNo - 1}`)">
                ← 上一单元
              </el-button>
            </div>
          </div>
        </template>

        <el-alert :type="chainInfo.type" :closable="false" show-icon :title="chainInfo.text" class="chain-alert" />

        <div class="workspace-body">
          <!-- 空状态 -->
          <el-empty
            v-if="!result && !running"
            description="在下方输入提示词，点击「执行优化」后，效果将展示在此处"
          />

          <!-- 等待首个输出片段（推理模型思考阶段） -->
          <div v-if="running && result && !result.output_text" class="thinking-box">
            <el-skeleton :rows="6" animated />
            <div class="loading-text">模型正在推理分析中，输出开始后将在此实时展示…</div>
          </div>

          <!-- 效果展示：输入的提示词 + 优化结果（流式实时更新） -->
          <div v-if="result" class="result-flow">
            <div class="input-block">
              <div class="block-label">📝 输入的提示词 t{{ result.unit_no }}</div>
              <div class="result-text input-text">{{ result.input_prompt }}</div>
            </div>

            <div class="output-block">
              <div class="block-label">
                ✨ 优化结果 T{{ result.unit_no }}
                <span v-if="running" class="typing-tip">⏳ 生成中…</span>
                <el-button
                  v-if="!running && result.output_text"
                  link
                  type="primary"
                  size="small"
                  @click="copyResult"
                >
                  复制结果
                </el-button>
              </div>
              <div class="result-text output-text">
                {{ result.output_text }}<span v-if="running && result.output_text" class="cursor">▍</span>
              </div>
            </div>
          </div>
        </div>
      </el-card>

      <!-- 下方输入框 -->
      <el-card shadow="never" class="input-card">
        <el-input
          v-model="form.input_prompt"
          type="textarea"
          :rows="4"
          maxlength="20000"
          show-word-limit
          :placeholder="`在此输入第 ${unitNo} 个镜头的分镜提示词，例如：Vincent 在急救室双手握紧除颤仪，大喊：Charge to 200 joules! Clear!`"
          @keydown.ctrl.enter="handleRun"
        />
        <div class="input-actions">
          <div class="run-tip">Ctrl + Enter 快捷执行</div>
          <div class="input-btns">
            <el-button :disabled="running" @click="openRevise">✏️ 修改本单元</el-button>
            <!-- 单元 6 已生成 → 「完成」（保存任务进度）；其余单元已生成 → 「进入下一单元」；未生成 → 「执行优化」 -->
            <el-button
              v-if="hasGenerated && unitNo === 6"
              type="success"
              :disabled="running || isTaskCompleted"
              :loading="completingTask"
              @click="handleCompleteTask"
            >
              {{ isTaskCompleted ? '任务已完成' : '完成' }}
            </el-button>
            <el-button
              v-else-if="hasGenerated"
              type="primary"
              :disabled="running"
              @click="nextUnit"
            >
              进入下一单元 →
            </el-button>
            <el-button v-else type="primary" :loading="running" @click="handleRun">
              {{ running ? '优化中…' : `执行优化 → 输出 T${unitNo}` }}
            </el-button>
          </div>
        </div>
      </el-card>
    </main>

    <!-- 修改流程 · 对话框 1：上一次生成的最终提示词 -->
    <el-dialog
      v-model="reviseDialog1"
      :title="`修改单元 ${unitNo} · 第 1 步：输入上一次生成的最终提示词`"
      width="640px"
      :close-on-click-modal="false"
    >
      <el-alert
        type="info"
        :closable="false"
        show-icon
        :title="`已自动预填单元 ${unitNo - 1} 最近一次生成的最终提示词 T${unitNo - 1}，可直接确认或修改`"
        class="dialog-alert"
      />
      <el-input
        v-model="revisePrev"
        type="textarea"
        :rows="10"
        v-loading="reviseLoadingPrev"
        maxlength="20000"
        show-word-limit
        placeholder="上一次生成的最终提示词（将作为本次修改的基础模板）"
      />
      <template #footer>
        <el-button @click="reviseDialog1 = false">取消</el-button>
        <el-button type="primary" @click="confirmDialog1">下一步 →</el-button>
      </template>
    </el-dialog>

    <!-- 修改流程 · 对话框 2：需要修改的提示词 -->
    <el-dialog
      v-model="reviseDialog2"
      :title="`修改单元 ${unitNo} · 第 2 步：输入需要修改的提示词`"
      width="640px"
      :close-on-click-modal="false"
    >
      <el-alert
        type="info"
        :closable="false"
        show-icon
        title="系统将结合 s3 指令，在上一次最终提示词的基础上修改生成新的提示词"
        class="dialog-alert"
      />
      <el-input
        v-model="revisePrompt"
        type="textarea"
        :rows="10"
        maxlength="20000"
        show-word-limit
        placeholder="需要修改的提示词"
      />
      <template #footer>
        <el-button @click="reviseDialog2 = false">取消</el-button>
        <el-button type="primary" :loading="running" @click="handleRevise">确认修改</el-button>
      </template>
    </el-dialog>

    <!-- 优化单元重命名 -->
    <el-dialog v-model="unitRenameVisible" title="重命名优化单元" width="420px" :close-on-click-modal="false">
      <el-input
        v-model="unitRenameName"
        maxlength="50"
        show-word-limit
        placeholder="请输入单元名称"
        @keyup.enter="handleUnitRename"
      />
      <template #footer>
        <el-button @click="unitRenameVisible = false">取消</el-button>
        <el-button type="primary" @click="handleUnitRename">确认重命名</el-button>
      </template>
    </el-dialog>

    <!-- 对话记录重命名 -->
    <el-dialog v-model="renameVisible" title="重命名任务记录" width="420px" :close-on-click-modal="false">
      <el-input
        v-model="renameName"
        maxlength="50"
        show-word-limit
        placeholder="请输入记录名称（如：镜头2-初版）"
        @keyup.enter="handleRename"
      />
      <template #footer>
        <el-button @click="renameVisible = false">取消</el-button>
        <el-button type="primary" @click="handleRename">确认重命名</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.workbench {
  width: 100%;
  flex: 1;
  min-height: 0;
  display: flex;
  gap: 12px;
  align-items: stretch;
}

/* ---------- 左侧功能栏（贴屏幕左侧） ---------- */
.side-panel {
  width: 280px;
  flex-shrink: 0;
}

.side-card {
  border-radius: 8px;
  height: 100%;
}

.side-card :deep(.el-card__body) {
  height: 100%;
  overflow-y: auto;
}

.card-header {
  font-weight: 600;
  font-size: 14px;
}

.side-empty {
  color: #c0c4cc;
  font-size: 13px;
  text-align: center;
  padding: 32px 0;
  line-height: 1.8;
}

.history-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px;
  border: 1px solid #ebeef5;
  border-radius: 6px;
  margin-bottom: 8px;
  cursor: pointer;
  transition: border-color 0.2s;
}

.history-item:hover {
  border-color: #409eff;
}

.history-item.active {
  border-color: #409eff;
  background: #ecf5ff;
}

.history-content {
  flex: 1;
  min-width: 0;
}

.history-top {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-bottom: 4px;
  flex-wrap: wrap;
}

.history-actions {
  display: flex;
  flex-direction: column;
  gap: 6px;
  flex-shrink: 0;
}

.history-actions :deep(.el-button + .el-button) {
  margin-left: 0; /* 竖直排列时去掉 Element 默认的相邻按钮左边距 */
}

.history-time {
  font-size: 12px;
  color: #909399;
  margin-bottom: 2px;
}

.history-name {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 2px;
}

.history-preview {
  font-size: 13px;
  color: #606266;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ---------- 右侧主区 ---------- */
.main-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 0;
  min-height: 0;
}

.workspace-card {
  border-radius: 8px;
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.workspace-card :deep(.el-card__body) {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.workspace-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.workspace-title {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.unit-name {
  font-size: 16px;
  font-weight: 600;
}

.nav-btns {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.chain-alert {
  margin-bottom: 12px;
}

.workspace-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 4px 2px;
}

.thinking-box {
  padding: 8px 0;
}

.loading-text {
  margin-top: 12px;
  text-align: center;
  font-size: 13px;
  color: #909399;
}

.result-flow {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.input-block,
.output-block {
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 12px;
}

.input-block {
  background: #fafafa;
}

.block-label {
  font-size: 13px;
  font-weight: 600;
  color: #606266;
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.typing-tip {
  font-size: 12px;
  font-weight: 400;
  color: #409eff;
}

.cursor {
  color: #409eff;
  animation: blink 1s step-start infinite;
}

@keyframes blink {
  50% {
    opacity: 0;
  }
}

.input-text {
  color: #606266;
}

.output-text {
  color: #303133;
}

/* ---------- 下方输入框 ---------- */
.input-card {
  border-radius: 8px;
}

.input-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 10px;
}

.run-tip {
  font-size: 12px;
  color: #c0c4cc;
}

.input-btns {
  display: flex;
  gap: 8px;
}

.dialog-alert {
  margin-bottom: 12px;
}
</style>

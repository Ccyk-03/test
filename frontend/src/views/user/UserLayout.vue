<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import { listUnits } from '../../api/units'
import { useConversationStore } from '../../stores/conversation'
import { useUserStore } from '../../stores/user'
import { formatTime } from '../../utils/format'

const route = useRoute()
const router = useRouter()
const store = useUserStore()
const conversationStore = useConversationStore()

const units = ref([])

// ---- 任务选择对话框（进入用户界面时弹出）----
const taskDialogVisible = ref(false)
const selectedTaskNo = ref(0)
// 是否已完成任务选择：未选择任务时不渲染工作台（只显示对话框）
const taskSelected = ref(false)

const currentUnit = computed(() => Number(route.params.unitNo) || 1)

// 步骤状态：已运行过 → finish；当前单元 → process；其余 → wait
function stepStatus(unitNo) {
  if (units.value.find((u) => u.unit_no === unitNo)?.last_run_at) return 'finish'
  if (unitNo === currentUnit.value) return 'process'
  return 'wait'
}

// 进度边界：跟踪「访问过的最大单元」+ 已完成单元，取最大者。
// 例：进入单元 4 后，即便回看单元 1，1 2 3 4 仍可点击，5 6 锁定；
//     单元 2 正在生成中途切回单元 1，也不会把单元 2 锁掉。
const reachedUnit = ref(1)

const maxReachedUnit = computed(() => {
  const completed = units.value.filter((u) => u.last_run_at).map((u) => u.unit_no)
  return Math.max(reachedUnit.value, ...completed, 1)
})

// 单元是否可点击查看：编号 ≤ 进度边界
function canGoUnit(unitNo) {
  return unitNo <= maxReachedUnit.value
}

function goUnit(unitNo) {
  if (!canGoUnit(unitNo)) return
  router.push(`/user/unit/${unitNo}`)
}

function backHome() {
  router.push('/')
}

async function loadUnits() {
  units.value = conversationStore.conversationNo
    ? await listUnits(conversationStore.conversationNo)
    : []
}

onMounted(async () => {
  await conversationStore.ensure()
  await loadUnits()
  // 默认选中当前（最新）任务；无任务时列表为空
  selectedTaskNo.value = conversationStore.conversationNo
  taskDialogVisible.value = true
})

// 切换任务（顶栏切换器）时：进度边界复位 + 顶部进度条刷新
watch(
  () => conversationStore.conversationNo,
  () => {
    reachedUnit.value = 1
    loadUnits()
  },
)

// 切换单元时：更新进度边界 + 刷新进度（修复：单元完成后步骤条不更新的问题）
watch(currentUnit, (u) => {
  if (u > reachedUnit.value) reachedUnit.value = u
  loadUnits()
})

// 单元重命名后，顶部导航栏名称同步刷新
watch(
  () => conversationStore.unitsVersion,
  () => loadUnits(),
)


// ---- 任务选择对话框操作 ----
function selectTask(no) {
  selectedTaskNo.value = no
}

function confirmTask() {
  if (!selectedTaskNo.value) {
    ElMessage.warning('请先选择一个任务')
    return
  }
  conversationStore.select(selectedTaskNo.value)
  taskSelected.value = true
  taskDialogVisible.value = false
}

async function addTask() {
  const conv = await conversationStore.startNew()
  selectedTaskNo.value = conv.conversation_no
  conversationStore.select(conv.conversation_no)
  taskSelected.value = true
  taskDialogVisible.value = false
  ElMessage.success(`任务 #${conv.conversation_no} 已创建`)
}

function cancelTask() {
  taskDialogVisible.value = false
  router.push('/') // 取消进入：返回系统主界面
}
</script>

<template>
  <div class="user-layout">
    <header class="layout-header">
      <div class="header-left">
        <span class="header-title">抽卡师的魔法</span>
        <el-tag type="success" effect="dark">用户操作界面</el-tag>
        <!-- 任务切换器（仅在此顶栏切换；未选择任务前不显示） -->
        <el-select
          v-if="taskSelected"
          v-model="conversationStore.conversationNo"
          size="small"
          style="width: 170px"
        >
          <el-option
            v-for="c in conversationStore.conversations"
            :key="c.conversation_no"
            :value="c.conversation_no"
            :label="`任务 #${c.conversation_no}（${c.stage_done}/6 阶段${c.completed_at ? '·已完成' : ''}）`"
          />
        </el-select>
      </div>
      <div class="header-right">
        <span>{{ store.username }}</span>
        <el-button type="primary" plain size="small" @click="backHome">返回主界面</el-button>
      </div>
    </header>

    <!-- 链式迭代进度：6 个优化单元（当前选中任务内；未选择任务时不显示） -->
    <div v-if="taskSelected" class="steps-bar">
      <el-steps :active="currentUnit - 1" align-center finish-status="success">
        <el-step
          v-for="u in units"
          :key="u.unit_no"
          :status="stepStatus(u.unit_no)"
        >
          <template #title>
            <span
              class="step-title"
              :class="canGoUnit(u.unit_no) ? 'clickable-step' : 'locked-step'"
              @click="goUnit(u.unit_no)"
            >
              {{ u.name || `单元 ${u.unit_no}` }}{{ canGoUnit(u.unit_no) ? '' : ' 🔒' }}
            </span>
          </template>
          <template #description>
            <span v-if="u.has_chained_base" class="chain-tip">⚡ 链式可用</span>
            <span v-else class="chain-tip">—</span>
          </template>
        </el-step>
      </el-steps>
    </div>

    <!-- 工作台：未选择任务时不进入（不渲染） -->
    <main v-if="taskSelected" class="layout-main">
      <router-view />
    </main>

    <!-- 任务选择对话框（进入用户界面时弹出） -->
    <el-dialog
      v-model="taskDialogVisible"
      title="选择任务"
      width="480px"
      :close-on-click-modal="false"
      :show-close="false"
    >
      <!-- 无任务：显示暂无任务记录 -->
      <div v-if="!conversationStore.conversations.length" class="no-task">
        <el-empty description="暂无任务记录" />
      </div>
      <!-- 有任务：列表选择 -->
      <div v-else class="task-list">
        <div
          v-for="c in conversationStore.conversations"
          :key="c.conversation_no"
          class="task-item"
          :class="{ active: selectedTaskNo === c.conversation_no }"
          @click="selectTask(c.conversation_no)"
        >
          <div class="task-main">
            <span class="task-name">任务 #{{ c.conversation_no }}</span>
            <el-tag v-if="c.completed_at" type="success" size="small">已完成</el-tag>
            <el-progress
              :percentage="Math.round((c.stage_done / 6) * 100)"
              :stroke-width="8"
              :show-text="false"
              class="task-progress"
            />
            <span class="task-count">{{ c.stage_done }}/6 阶段</span>
          </div>
          <div class="task-time">
            {{ c.last_run_at ? `最近运行：${formatTime(c.last_run_at)}` : `创建于：${formatTime(c.created_at)}` }}
          </div>
        </div>
      </div>

      <template #footer>
        <template v-if="conversationStore.conversations.length">
          <el-button type="success" plain @click="addTask">新建</el-button>
          <el-button type="primary" @click="confirmTask">确定</el-button>
          <el-button @click="cancelTask">取消</el-button>
        </template>
        <template v-else>
          <el-button type="primary" @click="addTask">新增</el-button>
          <el-button @click="cancelTask">取消</el-button>
        </template>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.user-layout {
  min-height: 100%;
  display: flex;
  flex-direction: column;
}

.layout-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 32px;
  background: #fff;
  box-shadow: 0 1px 4px rgba(0, 21, 41, 0.08);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-title {
  font-size: 17px;
  font-weight: 600;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 14px;
}

.steps-bar {
  background: #fff;
  padding: 20px 32px 8px;
}

.step-title {
  display: inline-block;
}

.clickable-step {
  cursor: pointer;
}

.locked-step {
  cursor: not-allowed;
  color: #c0c4cc;
}

.chain-tip {
  font-size: 12px;
  color: #67c23a;
}

.layout-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  padding: 12px;
}

/* ---------- 任务选择对话框 ---------- */
.no-task {
  padding: 20px 0;
}

.task-list {
  max-height: 360px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.task-item {
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 12px 14px;
  cursor: pointer;
  transition: border-color 0.2s;
}

.task-item:hover {
  border-color: #409eff;
}

.task-item.active {
  border-color: #409eff;
  background: #ecf5ff;
}

.task-main {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 6px;
}

.task-name {
  font-size: 15px;
  font-weight: 600;
  flex-shrink: 0;
}

.task-progress {
  flex: 1;
}

.task-count {
  font-size: 12px;
  color: #909399;
  flex-shrink: 0;
}

.task-time {
  font-size: 12px;
  color: #909399;
}
</style>

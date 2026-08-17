<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { getAuditDetail, listAudit } from '../../api/admin'
import { formatTimeFull } from '../../utils/format'

const loading = ref(false)
const items = ref([])
const total = ref(0)

const filters = reactive({
  username: '',
  unit_no: null,
  action: '',
  status: '',
  time_range: null,
  page: 1,
  page_size: 10,
})

// 详情抽屉
const drawerVisible = ref(false)
const detail = ref(null)
const detailLoading = ref(false)

async function refresh() {
  loading.value = true
  try {
    const params = { page: filters.page, page_size: filters.page_size }
    if (filters.username) params.username = filters.username
    if (filters.unit_no) params.unit_no = filters.unit_no
    if (filters.action) params.action = filters.action
    if (filters.status) params.status = filters.status
    if (filters.time_range?.length === 2) {
      params.start = filters.time_range[0]
      params.end = filters.time_range[1]
    }
    const resp = await listAudit(params)
    items.value = resp.items
    total.value = resp.total
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  filters.page = 1
  refresh()
}

function handleReset() {
  Object.assign(filters, { username: '', unit_no: null, action: '', status: '', time_range: null, page: 1 })
  refresh()
}

function handlePageChange(page) {
  filters.page = page
  refresh()
}

async function openDetail(row) {
  drawerVisible.value = true
  detailLoading.value = true
  try {
    detail.value = await getAuditDetail(row.id)
  } catch {
    drawerVisible.value = false
  } finally {
    detailLoading.value = false
  }
}

onMounted(refresh)
</script>

<template>
  <div>
    <!-- 筛选表单 -->
    <el-card shadow="never" class="filter-card">
      <el-form inline>
        <el-form-item label="用户名">
          <el-input v-model="filters.username" placeholder="模糊匹配" clearable style="width: 140px" />
        </el-form-item>
        <el-form-item label="单元">
          <el-select v-model="filters.unit_no" placeholder="全部" clearable style="width: 120px">
            <el-option v-for="n in 6" :key="n" :label="`单元 ${n}`" :value="n" />
          </el-select>
        </el-form-item>
        <el-form-item label="操作">
          <el-select v-model="filters.action" placeholder="全部" clearable style="width: 120px">
            <el-option label="优化" value="optimize" />
            <el-option label="修改" value="revise" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filters.status" placeholder="全部" clearable style="width: 120px">
            <el-option label="成功" value="success" />
            <el-option label="失败" value="error" />
          </el-select>
        </el-form-item>
        <el-form-item label="时间范围">
          <el-date-picker
            v-model="filters.time_range"
            type="datetimerange"
            start-placeholder="开始时间"
            end-placeholder="结束时间"
            value-format="YYYY-MM-DDTHH:mm:ss"
            style="width: 360px"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">查询</el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 审计列表 -->
    <el-card shadow="never">
      <template #header>
        <span class="card-header">账号使用历史审计（共 {{ total }} 条，点击行查看完整详情）</span>
      </template>
      <el-table :data="items" v-loading="loading" border stripe @row-click="openDetail">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="username" label="账号" width="110" />
        <el-table-column label="任务" width="70">
          <template #default="{ row }">#{{ row.conversation_no }}</template>
        </el-table-column>
        <el-table-column label="单元" width="80">
          <template #default="{ row }">单元 {{ row.unit_no }}</template>
        </el-table-column>
        <el-table-column label="操作" width="80">
          <template #default="{ row }">
            <el-tag :type="row.action === 'revise' ? 'warning' : 'primary'" size="small">
              {{ row.action === 'revise' ? '修改' : '优化' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="row.status === 'success' ? 'success' : 'danger'" size="small">
              {{ row.status === 'success' ? '成功' : '失败' }}
            </el-tag>
            <el-tag v-if="row.is_deleted" type="danger" size="small" effect="plain">已删除</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="模板来源" width="110">
          <template #default="{ row }">
            <el-tag
              :type="row.base_template_source === 'chained' ? 'success' : row.base_template_source === 'manual' ? 'warning' : 'info'"
              size="small"
            >
              {{ { chained: '链式', default: '默认', manual: '手动', none: '无' }[row.base_template_source] || row.base_template_source }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="输入（截断）" min-width="160" show-overflow-tooltip>
          <template #default="{ row }">{{ row.input_preview }}</template>
        </el-table-column>
        <el-table-column label="输出（截断）" min-width="160" show-overflow-tooltip>
          <template #default="{ row }">{{ row.output_preview || '—' }}</template>
        </el-table-column>
        <el-table-column prop="total_tokens" label="Token" width="90" />
        <el-table-column label="耗时" width="100">
          <template #default="{ row }">{{ row.elapsed_ms ? `${row.elapsed_ms}ms` : '—' }}</template>
        </el-table-column>
        <el-table-column label="时间" width="170">
          <template #default="{ row }">{{ formatTimeFull(row.created_at) }}</template>
        </el-table-column>
      </el-table>
      <el-pagination
        class="pager"
        layout="total, prev, pager, next, sizes"
        :total="total"
        :page-sizes="[10, 20, 50]"
        v-model:current-page="filters.page"
        v-model:page-size="filters.page_size"
        @current-change="handlePageChange"
        @size-change="handleSearch"
      />
    </el-card>

    <!-- 详情抽屉 -->
    <el-drawer v-model="drawerVisible" title="审计记录完整详情" size="55%">
      <div v-loading="detailLoading">
        <template v-if="detail">
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item label="账号">{{ detail.username }}</el-descriptions-item>
            <el-descriptions-item label="单元">任务 #{{ detail.conversation_no }} · 单元 {{ detail.unit_no }}</el-descriptions-item>
            <el-descriptions-item label="操作类型">
              <el-tag :type="detail.action === 'revise' ? 'warning' : 'primary'" size="small">
                {{ detail.action === 'revise' ? '修改（s3 指令）' : '优化' }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="状态">
              <el-tag :type="detail.status === 'success' ? 'success' : 'danger'" size="small">
                {{ detail.status === 'success' ? '成功' : '失败' }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="记录名称">{{ detail.display_name || '—' }}</el-descriptions-item>
            <el-descriptions-item label="用户侧状态">
              {{ detail.is_deleted ? '已删除（用户删除，审计保留）' : '正常' }}
            </el-descriptions-item>
            <el-descriptions-item label="基础模板来源">
              {{
                {
                  chained: `链式（来自单元 ${detail.unit_no - 1} 的输出）`,
                  default: '默认模板（无链式历史回退）',
                  manual: '手动输入的上一次最终提示词',
                  none: '无基础模板（首次对话 s1 指令）',
                }[detail.base_template_source] || detail.base_template_source
              }}
            </el-descriptions-item>
            <el-descriptions-item label="模型">{{ detail.model_name || '—' }}</el-descriptions-item>
            <el-descriptions-item label="Token（输入/输出/合计）">
              {{ detail.prompt_tokens }} / {{ detail.completion_tokens }} / {{ detail.total_tokens }}
            </el-descriptions-item>
            <el-descriptions-item label="耗时">{{ detail.elapsed_ms ? `${detail.elapsed_ms}ms` : '—' }}</el-descriptions-item>
            <el-descriptions-item label="时间">{{ formatTimeFull(detail.created_at) }}</el-descriptions-item>
          </el-descriptions>

          <h4>{{ detail.action === 'revise' ? '需要修改的提示词' : `待优化提示词 t${detail.unit_no}` }}</h4>
          <pre class="detail-block">{{ detail.input_prompt }}</pre>

          <h4>生效指令（管理端配置 + 用户本次追加）</h4>
          <pre class="detail-block">{{ detail.unit_instruction || '（空）' }}</pre>

          <h4 v-if="detail.base_template">
            基础模板快照（{{
              { chained: '链式', default: '默认', manual: '手动输入', none: '无' }[detail.base_template_source]
            }}）
          </h4>
          <pre v-if="detail.base_template" class="detail-block">{{ detail.base_template }}</pre>

          <h4>优化结果 T{{ detail.unit_no }}</h4>
          <pre class="detail-block">{{ detail.output_text || '（无输出）' }}</pre>

          <div v-if="detail.status === 'error'">
            <h4>失败原因</h4>
            <pre class="detail-block error-block">{{ detail.error_message }}</pre>
          </div>
        </template>
      </div>
    </el-drawer>
  </div>
</template>

<style scoped>
.filter-card {
  margin-bottom: 16px;
}

.card-header {
  font-weight: 600;
}

.pager {
  margin-top: 14px;
  justify-content: flex-end;
}

.detail-block {
  background: #f5f7fa;
  border: 1px solid #ebeef5;
  border-radius: 6px;
  padding: 12px;
  font-size: 13px;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 260px;
  overflow: auto;
  font-family: inherit;
}

.error-block {
  color: #f56c6c;
}

h4 {
  margin: 18px 0 8px;
  font-size: 14px;
}
</style>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import { createUser, deleteUser, listUsers, resetPassword } from '../../api/admin'
import { useUserStore } from '../../stores/user'
import { formatTimeFull } from '../../utils/format'

const store = useUserStore()
const users = ref([])
const loading = ref(false)

// 管理员账户仅可设置一个：已存在管理员时禁止再创建管理员角色
const hasAdmin = computed(() => users.value.some((u) => u.role === 'admin'))

// 创建账号对话框
const createVisible = ref(false)
const createFormRef = ref()
const createForm = reactive({ username: '', password: '', role: 'user' })

// 重置密码对话框
const resetVisible = ref(false)
const resetForm = reactive({ userId: null, username: '', password: '' })

const createRules = {
  username: [
    { required: true, message: '请输入用户名（至少 2 位）', trigger: 'blur' },
    { min: 2, max: 50, message: '长度 2-50 位', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码（至少 6 位）', trigger: 'blur' },
    { min: 6, max: 128, message: '长度 6-128 位', trigger: 'blur' },
  ],
  role: [{ required: true, message: '请选择角色', trigger: 'change' }],
}

async function refresh() {
  loading.value = true
  try {
    users.value = await listUsers()
  } finally {
    loading.value = false
  }
}

async function handleCreate() {
  await createFormRef.value.validate()
  await createUser({ ...createForm })
  ElMessage.success(`账号 ${createForm.username} 创建成功`)
  createVisible.value = false
  Object.assign(createForm, { username: '', password: '', role: 'user' })
  await refresh()
}

function openReset(user) {
  Object.assign(resetForm, { userId: user.id, username: user.username, password: '' })
  resetVisible.value = true
}

async function handleReset() {
  if (resetForm.password.length < 6) {
    ElMessage.warning('密码至少 6 位')
    return
  }
  await resetPassword(resetForm.userId, resetForm.password)
  ElMessage.success(`账号 ${resetForm.username} 密码已重置`)
  resetVisible.value = false
}

async function handleDelete(user) {
  await ElMessageBox.confirm(
    `确认删除账号「${user.username}」？其历史审计记录将保留。`,
    '删除确认',
    { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
  )
  await deleteUser(user.id)
  ElMessage.success(`账号 ${user.username} 已删除`)
  await refresh()
}

onMounted(refresh)
</script>

<template>
  <div>
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>账号与权限管理（共 {{ users.length }} 个账号）</span>
          <el-button type="primary" @click="createVisible = true">+ 创建账号</el-button>
        </div>
      </template>

      <el-table :data="users" v-loading="loading" border stripe>
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="username" label="用户名" min-width="140" />
        <el-table-column label="角色（权限）" width="140">
          <template #default="{ row }">
            <el-tag :type="row.role === 'admin' ? 'danger' : 'info'">
              {{ row.role === 'admin' ? '管理员' : '普通用户' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'danger'" size="small">
              {{ row.is_active ? '正常' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" min-width="170">
          <template #default="{ row }">{{ formatTimeFull(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openReset(row)">重置密码</el-button>
            <el-button
              v-if="row.id !== store.user?.id"
              link
              type="danger"
              size="small"
              @click="handleDelete(row)"
            >
              删除
            </el-button>
            <el-tag v-else size="small" type="warning">当前账号</el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 创建账号对话框 -->
    <el-dialog v-model="createVisible" title="创建账号（分配角色权限）" width="420px">
      <el-form ref="createFormRef" :model="createForm" :rules="createRules" label-width="70px">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="createForm.username" placeholder="2-50 位" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="createForm.password" type="password" placeholder="至少 6 位" />
        </el-form-item>
        <el-form-item label="角色" prop="role">
          <el-radio-group v-model="createForm.role">
            <el-radio value="user">普通用户</el-radio>
            <el-radio value="admin" :disabled="hasAdmin">
              管理员{{ hasAdmin ? '（仅可设置一个，已存在）' : '' }}
            </el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" @click="handleCreate">创建</el-button>
      </template>
    </el-dialog>

    <!-- 重置密码对话框 -->
    <el-dialog v-model="resetVisible" :title="`重置密码：${resetForm.username}`" width="420px">
      <el-input
        v-model="resetForm.password"
        type="password"
        placeholder="输入新密码（至少 6 位）"
      />
      <template #footer>
        <el-button @click="resetVisible = false">取消</el-button>
        <el-button type="primary" @click="handleReset">确认重置</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-weight: 600;
}
</style>

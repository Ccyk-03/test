<script setup>
import { useRoute, useRouter } from 'vue-router'

import { useUserStore } from '../../stores/user'

const route = useRoute()
const router = useRouter()
const store = useUserStore()

function backHome() {
  router.push('/')
}
</script>

<template>
  <el-container class="admin-layout">
    <el-aside width="210px" class="layout-aside">
      <div class="aside-title">🛠️ 管理界面</div>
      <el-menu
        :default-active="route.path"
        router
        background-color="#001529"
        text-color="#c0c4cc"
        active-text-color="#ffffff"
      >
        <el-menu-item index="/admin/users">👥 账号管理</el-menu-item>
        <el-menu-item index="/admin/audit">📋 审计查询</el-menu-item>
        <el-menu-item index="/admin/config">⚙️ 优化单元配置</el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="layout-header">
        <span>抽卡师的魔法</span>
        <div class="header-right">
          <span class="header-user">{{ store.username }}（管理员）</span>
          <el-button type="primary" plain size="small" @click="backHome">返回系统主界面</el-button>
        </div>
      </el-header>
      <el-main class="layout-main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
.admin-layout {
  min-height: 100%;
}

.layout-aside {
  background: #001529;
  display: flex;
  flex-direction: column;
}

.aside-title {
  color: #fff;
  font-size: 16px;
  font-weight: 600;
  padding: 18px 20px;
}

.layout-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #fff;
  box-shadow: 0 1px 4px rgba(0, 21, 41, 0.08);
  font-weight: 600;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-user {
  font-size: 13px;
  font-weight: 400;
  color: #909399;
}

.layout-main {
  background: #f5f7fa;
  padding: 16px;
}
</style>

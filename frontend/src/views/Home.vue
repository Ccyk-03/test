<script setup>
import { useRouter } from 'vue-router'

import { useUserStore } from '../stores/user'

const router = useRouter()
const store = useUserStore()

function goUser() {
  router.push('/user')
}

function goAdmin() {
  if (store.isAdmin) {
    router.push('/admin')
  }
}

function handleLogout() {
  store.logout()
  router.push('/login')
}
</script>

<template>
  <div class="home-page">
    <header class="home-header">
      <div class="title">抽卡师的魔法</div>
      <div class="user-info">
        <span class="username">
          {{ store.username }}
          <el-tag size="small" :type="store.isAdmin ? 'danger' : 'info'">
            {{ store.isAdmin ? '管理员' : '普通用户' }}
          </el-tag>
        </span>
        <el-button link type="primary" @click="handleLogout">退出登录</el-button>
      </div>
    </header>

    <main class="home-main">
      <h2 class="welcome">欢迎使用系统主界面，请选择要进入的操作端口</h2>
      <div class="entry-cards">
        <!-- 用户操作界面入口 -->
        <el-card class="entry-card" shadow="hover" @click="goUser">
          <div class="card-icon">🚀</div>
          <div class="card-title">用户操作界面</div>
          <div class="card-desc">
            6 组提示词优化单元，链式递进迭代：<br />
            输入待优化提示词 tᵢ，自动输出优化结果 Tᵢ
          </div>
          <el-button type="primary">进入用户界面</el-button>
        </el-card>

        <!-- 管理界面入口 -->
        <el-card
          class="entry-card"
          :class="{ disabled: !store.isAdmin }"
          shadow="hover"
          @click="goAdmin"
        >
          <div class="card-icon">🛠️</div>
          <div class="card-title">管理界面</div>
          <div class="card-desc">
            账号权限管理 · 审计历史查询 ·<br />
            优化单元与统一指令配置
          </div>
          <el-button type="danger" :disabled="!store.isAdmin">
            {{ store.isAdmin ? '进入管理界面' : '仅管理员可用' }}
          </el-button>
        </el-card>
      </div>
    </main>
  </div>
</template>

<style scoped>
.home-page {
  min-height: 100%;
  display: flex;
  flex-direction: column;
}

.home-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 32px;
  background: #fff;
  box-shadow: 0 1px 4px rgba(0, 21, 41, 0.08);
}

.home-header .title {
  font-size: 18px;
  font-weight: 600;
  color: #303133;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.username {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
}

.home-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 40px;
  padding: 24px;
}

.welcome {
  font-size: 20px;
  font-weight: 500;
  color: #606266;
  margin: 0;
}

.entry-cards {
  display: flex;
  gap: 32px;
  flex-wrap: wrap;
  justify-content: center;
}

.entry-card {
  width: 320px;
  text-align: center;
  cursor: pointer;
  border-radius: 12px;
  transition: transform 0.2s;
}

.entry-card:hover {
  transform: translateY(-4px);
}

.entry-card.disabled {
  cursor: not-allowed;
  opacity: 0.75;
}

.card-icon {
  font-size: 44px;
  margin-bottom: 8px;
}

.card-title {
  font-size: 18px;
  font-weight: 600;
  margin-bottom: 10px;
}

.card-desc {
  font-size: 13px;
  color: #909399;
  line-height: 1.8;
  margin-bottom: 18px;
}
</style>

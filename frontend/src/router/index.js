import { createRouter, createWebHistory } from 'vue-router'
import { ElMessage } from 'element-plus'

import { useUserStore } from '../stores/user'

const routes = [
  { path: '/login', name: 'login', component: () => import('../views/Login.vue') },
  { path: '/', name: 'home', component: () => import('../views/Home.vue') },
  {
    // 用户操作界面：6 个优化单元工作台
    path: '/user',
    component: () => import('../views/user/UserLayout.vue'),
    redirect: '/user/unit/1',
    children: [
      {
        path: 'unit/:unitNo(\\d+)',
        name: 'unit-workbench',
        component: () => import('../views/user/UnitWorkbench.vue'),
      },
    ],
  },
  {
    // 管理界面：账号管理 / 审计查询 / 单元配置
    path: '/admin',
    component: () => import('../views/admin/AdminLayout.vue'),
    redirect: '/admin/users',
    children: [
      { path: 'users', name: 'admin-users', component: () => import('../views/admin/UserManage.vue') },
      { path: 'audit', name: 'admin-audit', component: () => import('../views/admin/AuditQuery.vue') },
      { path: 'config', name: 'admin-config', component: () => import('../views/admin/UnitConfig.vue') },
    ],
  },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// 全局路由守卫：登录校验 + 管理端角色校验
router.beforeEach((to) => {
  const store = useUserStore()

  // 未登录 → 跳登录页（记录来源以便登录后回跳）
  if (to.path !== '/login' && !store.isLoggedIn) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }
  // 已登录访问登录页 → 回主界面
  if (to.path === '/login' && store.isLoggedIn) {
    return { path: '/' }
  }
  // 非管理员访问管理端 → 拦截回主界面
  if (to.path.startsWith('/admin') && !store.isAdmin) {
    ElMessage.warning('无权限：管理界面仅管理员可用')
    return { path: '/' }
  }
  return true
})

export default router

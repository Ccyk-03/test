import request from './request'

// 登录：{username, password} → {access_token, user}
export const login = (username, password) =>
  request.post('/auth/login', { username, password })

// 当前用户信息（刷新页面恢复登录态用）
export const getMe = () => request.get('/auth/me')

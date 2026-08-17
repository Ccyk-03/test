import request from './request'

// ---------- 账号管理 ----------
export const listUsers = () => request.get('/admin/users')
export const createUser = (data) => request.post('/admin/users', data)
export const deleteUser = (userId) => request.delete(`/admin/users/${userId}`)
export const resetPassword = (userId, password) =>
  request.put(`/admin/users/${userId}/password`, { password })

// ---------- 审计查询 ----------
export const listAudit = (params) => request.get('/admin/audit', { params })
export const getAuditDetail = (logId) => request.get(`/admin/audit/${logId}`)

// ---------- 优化单元配置 ----------
export const getUnitConfigs = () => request.get('/admin/units')
export const updateUnitConfig = (unitNo, data) =>
  request.put(`/admin/units/${unitNo}`, data)

// ---------- 三份调用指令 s1/s2/s3 ----------
export const getGlobalConfig = () => request.get('/admin/global')
export const updateGlobalConfig = (data) => request.put('/admin/global', data)

// ---------- LLM 模型配置（GPT 接口预留） ----------
export const getModelConfig = () => request.get('/admin/model')
export const updateModelConfig = (data) => request.put('/admin/model', data)

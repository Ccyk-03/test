import request from './request'

// 6 个优化单元概览（指定对话内的链式进度；不传为当前对话）
export const listUnits = (conversationNo = null) =>
  request.get('/units', { params: conversationNo ? { conversation_no: conversationNo } : {} })

// 执行一轮优化（非流式，同步返回优化结果）
export const runUnit = (unitNo, data) => request.post(`/units/${unitNo}/run`, data)

// 修改已生成提示词（结合 s3 指令；data: {previous_final_prompt, prompt_to_revise, custom_instruction}）
export const reviseUnit = (unitNo, data) => request.post(`/units/${unitNo}/revise`, data)

// 当前用户在某对话内该单元的最近运行历史
export const getUnitHistory = (unitNo, limit = 10, conversationNo = null) =>
  request.get(`/units/${unitNo}/history`, {
    params: { limit, ...(conversationNo ? { conversation_no: conversationNo } : {}) },
  })

// 优化单元重命名（全局生效）
export const renameUnit = (unitNo, name) =>
  request.put(`/units/${unitNo}/rename`, { name })

// 对话记录重命名 / 删除（软删除，管理端审计保留）
export const renameRecord = (unitNo, recordId, name) =>
  request.put(`/units/${unitNo}/records/${recordId}/rename`, { name })
export const deleteRecord = (unitNo, recordId) =>
  request.delete(`/units/${unitNo}/records/${recordId}`)

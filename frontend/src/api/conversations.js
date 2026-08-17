import request from './request'

// 当前用户的全部对话（按对话号倒序，最新在前）
export const getConversations = () => request.get('/conversations')

// 开启新对话：完成当前 6 阶段后重新开始新一轮任务
export const startConversation = () => request.post('/conversations')

// 指定对话的全部运行记录（跨 6 个阶段，用于回看历史对话）
export const getConversationRecords = (conversationNo) =>
  request.get(`/conversations/${conversationNo}/records`)

// 完成任务：保存当前任务进度（要求 6 个阶段均有成功记录）
export const completeConversation = (conversationNo) =>
  request.put(`/conversations/${conversationNo}/complete`)

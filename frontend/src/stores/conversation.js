import { defineStore } from 'pinia'

import { completeConversation, getConversations, startConversation } from '../api/conversations'

// 对话状态（跨组件共享）：一个对话 = 一轮 6 阶段（单元 1-6）优化任务。
// 工作台与顶部进度条（UserLayout）通过本 store 同步当前选中的对话。
export const useConversationStore = defineStore('conversation', {
  state: () => ({
    conversations: [],   // 对话列表（按对话号倒序）
    conversationNo: 0,   // 当前选中的对话号
    unitsVersion: 0,     // 单元显示名版本号：重命名后 +1，通知导航栏刷新
  }),
  getters: {
    current: (state) => state.conversations.find((c) => c.conversation_no === state.conversationNo) || null,
  },
  actions: {
    /** 确保已加载对话列表并选中一个有效对话（默认最新）。
     *  没有任何任务时 conversationNo = 0（不自动创建，由任务选择对话框的「新增」创建）。 */
    async ensure() {
      this.conversations = await getConversations()
      if (!this.conversations.length) {
        this.conversationNo = 0
        return
      }
      if (!this.conversations.some((c) => c.conversation_no === this.conversationNo)) {
        this.conversationNo = this.conversations[0].conversation_no
      }
    },
    /** 重新拉取对话列表（进度数会变）。 */
    async refreshList() {
      this.conversations = await getConversations()
      if (!this.conversations.some((c) => c.conversation_no === this.conversationNo)) {
        this.conversationNo = this.conversations[0].conversation_no
      }
    },
    /** 开启新对话并切换为当前。 */
    async startNew() {
      const conv = await startConversation()
      this.conversations = [conv, ...this.conversations]
      this.conversationNo = conv.conversation_no
      return conv
    },
    /** 切换查看/继续的对话。 */
    select(conversationNo) {
      this.conversationNo = conversationNo
    },
    /** 单元显示名变更（重命名）后调用：通知顶部导航栏刷新。 */
    bumpUnits() {
      this.unitsVersion += 1
    },
    /** 完成当前任务：保存进度（后端要求 6 阶段均有成功记录）。 */
    async completeCurrent() {
      const updated = await completeConversation(this.conversationNo)
      const idx = this.conversations.findIndex((c) => c.conversation_no === updated.conversation_no)
      if (idx !== -1) this.conversations.splice(idx, 1, updated)
      return updated
    },
  },
})

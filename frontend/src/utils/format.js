// 时间显示格式化：后端返回 ISO 字符串（如 2026-08-16T14:03:24.123456），
// 界面统一用空格替代 T 展示，符合中文阅读习惯。

/** ISO 时间 → "MM-DD HH:MM:SS"（如 "08-16 14:03:24"） */
export const formatTime = (iso) => {
  if (!iso) return ''
  return String(iso).replace('T', ' ').slice(5, 19)
}

/** ISO 时间 → "YYYY-MM-DD HH:MM:SS"（如 "2026-08-16 14:03:24"） */
export const formatTimeFull = (iso) => {
  if (!iso) return ''
  return String(iso).replace('T', ' ').slice(0, 19)
}

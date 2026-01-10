// 通用格式化工具，避免各页面重复实现

export const formatDate = (value, opts = {}) => {
  if (!value) return ''
  try {
    const date = value instanceof Date ? value : new Date(value)
    return date.toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', ...opts })
  } catch {
    return String(value)
  }
}

export const formatDateTime = (value, opts = {}) => {
  if (!value) return ''
  try {
    const date = value instanceof Date ? value : new Date(value)
    return date.toLocaleString('zh-CN', {
      hour12: false,
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      ...opts,
    })
  } catch {
    return String(value)
  }
}

export const formatBytes = (bytes, decimals = 1) => {
  if (!bytes || Number.isNaN(bytes)) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  const value = parseFloat((bytes / Math.pow(k, i)).toFixed(decimals))
  return `${value} ${sizes[i] || 'B'}`
}

export const formatNumber = (num, decimals = 0) => {
  if (num === null || num === undefined || Number.isNaN(num)) return ''
  return Number(num).toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })
}

export const formatDuration = (seconds) => {
  if (seconds === null || seconds === undefined || Number.isNaN(seconds)) return ''
  const s = Math.max(0, Math.floor(seconds))
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = s % 60
  const parts = []
  if (h) parts.push(`${h}h`)
  if (m || h) parts.push(`${m}m`)
  parts.push(`${sec}s`)
  return parts.join(' ')
}

export const safeText = (value, fallback = '') => {
  if (value === null || value === undefined) return fallback
  return String(value)
}

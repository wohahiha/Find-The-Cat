import { defineStore } from 'pinia'
import api from '@/api/client'
import realtime from '@/utils/realtime'

const PAGE_SIZE = 10

export const useNotificationStore = defineStore('notifications', {
  state: () => ({
    items: [],
    unread: 0,
    loading: false,
    hasMore: true,
    page: 1,
    status: 'all', // 'all' | 'unread'
    drawerOpen: false,
    socket: null,
    reconnectTimer: null,
    pingTimer: null,
  }),
  actions: {
    _isAuthed() {
      if (typeof window === 'undefined') return false
      return !!(localStorage.getItem('ftc_access') || sessionStorage.getItem('ftc_access'))
    },
    _wsUrl() {
      const base = import.meta.env.VITE_BACKEND_URL || window.location.origin
      const wsBase = base.replace(/^http/, 'ws').replace(/\/$/, '')
      const token =
        sessionStorage.getItem('ftc_access') ||
        localStorage.getItem('ftc_access') ||
        ''
      const query = token ? `?token=${encodeURIComponent(token)}` : ''
      return `${wsBase}/ws/notify/${query}`
    },
    ensureSocket() {
      if (!this._isAuthed()) return
      // 交由统一实时管理器处理，避免重复连接
      realtime.startNotify()
    },
    disconnect() {
      realtime.stopNotify()
    },
    async fetchUnreadCount() {
      try {
        const res = await api.get('/notifications/unread-count/')
        this.unread = res.data?.data?.unread ?? 0
      } catch (e) {
        // ignore
      }
    },
    async fetchList({ reset = false, status = 'all' } = {}) {
      if (!this._isAuthed()) return
      if (reset) {
        this.page = 1
        this.items = []
        this.hasMore = true
      }
      if (!this.hasMore) return
      this.loading = true
      try {
        const res = await api.get('/notifications/', {
          params: { page: this.page, page_size: PAGE_SIZE, status },
        })
        const payload = res.data || {}
        const data = payload.data ?? payload
        const extra = payload.extra || {}
        const list = Array.isArray(data) ? data : data?.items || []
        if (reset) {
          this.items = list
        } else {
          this.items = [...this.items, ...list]
        }
        const pageSize = extra.page_size || PAGE_SIZE
        this.hasMore = extra.has_next ?? list.length >= pageSize
        this.page = extra.next_page || this.page + 1
        this.status = status
      } catch (e) {
        // ignore
      } finally {
        this.loading = false
      }
    },
    async markRead(id) {
      if (!this._isAuthed()) return
      try {
        await api.post(`/notifications/${id}/read/`)
        this.items = this.items.map((n) => (n.id === id ? { ...n, read_at: n.read_at || new Date().toISOString() } : n))
        if (this.unread > 0) this.unread -= 1
      } catch (e) {
        // ignore
      }
    },
    async markAllRead() {
      if (!this._isAuthed()) return
      try {
        await api.post('/notifications/mark-all-read/')
        this.items = this.items.map((n) => ({ ...n, read_at: n.read_at || new Date().toISOString() }))
        this.unread = 0
      } catch (e) {
        // ignore
      }
    },
    ingestRealtime(payload) {
      if (!payload || !payload.id) return
      // 去重
      if (this.items.find((n) => n.id === payload.id)) return
      this.items = [{ ...payload, read_at: null }, ...this.items]
      this.unread += 1
    },
  },
})

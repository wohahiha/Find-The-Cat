import { defineStore } from 'pinia'
import api from '@/api/client'

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
      if (this.socket || !this._isAuthed()) return
      try {
        const url = this._wsUrl()
        const ws = new WebSocket(url)
        ws.onopen = () => {
          this.socket = ws
          // heartbeat
          if (this.pingTimer) clearInterval(this.pingTimer)
          this.pingTimer = setInterval(() => {
            if (this.socket && this.socket.readyState === WebSocket.OPEN) {
              this.socket.send(JSON.stringify({ type: 'ping' }))
            }
          }, 25000)
        }
        ws.onclose = () => {
          this.socket = null
          if (this.pingTimer) {
            clearInterval(this.pingTimer)
            this.pingTimer = null
          }
          if (this.reconnectTimer) clearTimeout(this.reconnectTimer)
          // 简单重连
          this.reconnectTimer = setTimeout(() => {
            this.ensureSocket()
          }, 5000)
        }
        ws.onerror = () => {
          ws.close()
        }
        ws.onmessage = (evt) => {
          try {
            const data = JSON.parse(evt.data)
            if (data.event === 'notification') {
              this.ingestRealtime(data)
              this.fetchUnreadCount()
            }
          } catch (e) {
            // ignore
          }
        }
      } catch (e) {
        // ignore
      }
    },
    disconnect() {
      if (this.reconnectTimer) {
        clearTimeout(this.reconnectTimer)
        this.reconnectTimer = null
      }
      if (this.pingTimer) {
        clearInterval(this.pingTimer)
        this.pingTimer = null
      }
      if (this.socket) {
        this.socket.close()
        this.socket = null
      }
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
        const data = res.data?.data || {}
        const list = data.items || []
        if (reset) {
          this.items = list
        } else {
          this.items = [...this.items, ...list]
        }
        this.hasMore = list.length >= PAGE_SIZE
        this.page += 1
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

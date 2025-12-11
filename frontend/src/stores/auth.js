import { defineStore } from 'pinia'
import api from '@/api/client'
import realtime from '@/utils/realtime'

const hasWindow = typeof window !== 'undefined'
const storage = hasWindow ? window.localStorage : null
const session = hasWindow ? window.sessionStorage : null

const loadToken = (key) => {
  if (!hasWindow) return ''
  return (session?.getItem(key) || storage?.getItem(key) || '')
}

const resolveUrl = (url) => {
  if (!url) return ''
  const normalized = url.replace(/\\/g, '/')
  if (/^https?:\/\//i.test(normalized)) return normalized
  const backendBase = import.meta.env.VITE_BACKEND_URL || ''
  const apiPrefix = '/api'
  if (normalized.startsWith('/')) {
    const base = backendBase || apiPrefix
    return `${base.replace(/\/$/, '')}${normalized}`
  }
  try {
    const base = backendBase || (hasWindow ? window.location.origin : '')
    return new URL(normalized, base || undefined).toString()
  } catch {
    return normalized
  }
}

export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: null,
    accessToken: loadToken('ftc_access') || '',
    refreshToken: loadToken('ftc_refresh') || '',
    remember: true,
    loading: false,
  }),
  actions: {
    async fetchMe() {
      const res = await api.get('/accounts/me/')
      this.user = res.data?.data?.user || res.data?.user || null
      // 登录后启动通知通道
      realtime.startNotify()
      if (hasWindow) {
        try {
          const avatar = resolveUrl(this.user?.avatar || '')
          if (avatar) {
            localStorage.setItem('ftc_avatar', avatar)
          } else {
            localStorage.removeItem('ftc_avatar')
          }
        } catch (e) {
          // ignore storage errors
        }
      }
      return this.user
    },
    async login(payload) {
      this.loading = true
      try {
        const res = await api.post('/accounts/auth/login/', payload)
        const data = res.data?.data || {}
        this.accessToken = data.access || ''
        this.refreshToken = data.refresh || ''
        this.remember = !!payload.remember
        // storage choice
        const store = payload.remember ? storage : session
        if (store) {
          store.setItem('ftc_access', this.accessToken)
          store.setItem('ftc_refresh', this.refreshToken)
        }
        // clear the other store to avoid stale tokens
        const otherStore = payload.remember ? session : storage
        if (otherStore) {
          otherStore.removeItem('ftc_access')
          otherStore.removeItem('ftc_refresh')
        }
        await this.fetchMe().catch(() => null)
        return res.data
      } finally {
        this.loading = false
      }
    },
    async register(payload) {
      return api.post('/accounts/auth/register/', payload).then((res) => res.data)
    },
    logout() {
      this.user = null
      this.accessToken = ''
      this.refreshToken = ''
      delete api.defaults.headers.common.Authorization
      realtime.stopAll()
      if (storage) {
        storage.removeItem('ftc_access')
        storage.removeItem('ftc_refresh')
        storage.removeItem('ftc_avatar')
      }
      if (session) {
        session.removeItem('ftc_access')
        session.removeItem('ftc_refresh')
        session.removeItem('ftc_avatar')
      }
    },
  },
})

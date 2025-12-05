import { defineStore } from 'pinia'
import api from '@/api/client'

const hasWindow = typeof window !== 'undefined'
const storage = hasWindow ? window.localStorage : null
const session = hasWindow ? window.sessionStorage : null

const loadToken = (key) => {
  if (!hasWindow) return ''
  return (session?.getItem(key) || storage?.getItem(key) || '')
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
      if (storage) {
        storage.removeItem('ftc_access')
        storage.removeItem('ftc_refresh')
      }
      if (session) {
        session.removeItem('ftc_access')
        session.removeItem('ftc_refresh')
      }
    },
  },
})

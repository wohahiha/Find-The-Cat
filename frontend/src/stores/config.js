import { defineStore } from 'pinia'
import api from '@/api/client'

const fallbackBrand = import.meta.env.VITE_BRAND || 'Find The Cat'

export const useConfigStore = defineStore('config', {
  state: () => ({
    brand: fallbackBrand,
    loaded: false,
  }),
  actions: {
    async fetchBrand() {
      if (this.loaded && this.brand) return this.brand
      try {
        const res = await api.get('/system/public/brand/')
        const name = res?.data?.data?.brand || res?.data?.brand || fallbackBrand
        this.brand = name || fallbackBrand
      } catch (e) {
        this.brand = this.brand || fallbackBrand
      } finally {
        this.loaded = true
      }
      return this.brand
    },
  },
})

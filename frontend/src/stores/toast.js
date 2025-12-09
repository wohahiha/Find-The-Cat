import { defineStore } from 'pinia'

let counter = 0

export const useToastStore = defineStore('toast', {
  state: () => ({
    items: [],
  }),
  actions: {
    push({ type = 'info', message = '', duration = 3000 }) {
      if (!message) return null
      const id = ++counter
      const toast = { id, type, message }
      this.items.push(toast)
      if (duration > 0) {
        setTimeout(() => this.remove(id), duration)
      }
      return id
    },
    success(message, duration = 3000) {
      return this.push({ type: 'success', message, duration })
    },
    error(message, duration = 4000) {
      return this.push({ type: 'error', message, duration })
    },
    info(message, duration = 3000) {
      return this.push({ type: 'info', message, duration })
    },
    remove(id) {
      this.items = this.items.filter((t) => t.id !== id)
    },
    clear() {
      this.items = []
    },
  },
})

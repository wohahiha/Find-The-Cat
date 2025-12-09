<template>
  <div class="pointer-events-none fixed inset-0 z-[9999] flex flex-col items-end gap-3 px-4 py-6 sm:pt-8 sm:pr-6">
    <transition-group name="toast" tag="div" class="flex flex-col gap-3 w-full sm:w-auto">
      <div
        v-for="toast in items"
        :key="toast.id"
        class="pointer-events-auto flex w-full sm:w-80 items-start gap-3 rounded-lg border p-4 shadow-panel"
        :class="variantClass(toast.type)"
      >
        <span class="material-symbols-outlined text-lg">
          {{ icon(toast.type) }}
        </span>
        <p class="text-sm leading-relaxed">{{ toast.message }}</p>
        <button
          class="ml-auto text-sm text-text/70 hover:text-text"
          type="button"
          aria-label="Close toast"
          @click="remove(toast.id)"
        >
          ✕
        </button>
      </div>
    </transition-group>
  </div>
</template>

<script setup>
import { storeToRefs } from 'pinia'
import { useToastStore } from '@/stores/toast'

const toastStore = useToastStore()
const { items } = storeToRefs(toastStore)
const remove = toastStore.remove

const variantClass = (type) => {
  if (type === 'success') return 'bg-green-500/10 border-green-500/40 text-text'
  if (type === 'error') return 'bg-red-500/10 border-red-500/40 text-text'
  return 'bg-panel border-border-panel text-text'
}

const icon = (type) => {
  if (type === 'success') return 'check_circle'
  if (type === 'error') return 'error'
  return 'info'
}
</script>

<style scoped>
.toast-enter-active,
.toast-leave-active {
  transition: all 200ms ease;
}
.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}
</style>

<template>
  <div class="flex w-full flex-col items-center justify-center gap-2 rounded-lg border border-danger/50 bg-danger/10 px-4 py-6 text-center text-text">
    <span class="material-symbols-outlined text-3xl text-danger">error</span>
    <p class="text-sm font-semibold">{{ message || '出错了，请稍后再试' }}</p>
    <div class="flex items-center gap-3">
      <button
        v-if="retryLabel"
        class="rounded-md bg-border-panel px-3 py-2 text-sm font-semibold text-text hover:bg-input-border"
        type="button"
        @click="$emit('retry')"
      >
        {{ retryLabel }}
      </button>
      <slot />
    </div>
  </div>
</template>

<script setup>
defineProps({
  message: {
    type: String,
    default: '',
  },
  retryLabel: {
    type: String,
    default: '重试',
  },
})
</script>

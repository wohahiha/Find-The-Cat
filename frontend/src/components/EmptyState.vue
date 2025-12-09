<template>
  <div class="flex w-full flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-border-panel bg-panel/60 px-4 py-8 text-center text-muted">
    <span class="material-symbols-outlined text-3xl text-primary/70">hourglass_empty</span>
    <p class="text-sm font-medium text-text/80">{{ title }}</p>
    <p v-if="description" class="text-xs text-muted">{{ description }}</p>
    <button
      v-if="actionLabel"
      class="mt-2 inline-flex items-center justify-center rounded-md bg-border-panel px-3 py-2 text-sm font-semibold text-text hover:bg-input-border"
      type="button"
      @click="$emit('action')"
    >
      {{ actionLabel }}
    </button>
  </div>
</template>

<script setup>
defineProps({
  title: {
    type: String,
    default: '暂无数据',
  },
  description: {
    type: String,
    default: '',
  },
  actionLabel: {
    type: String,
    default: '',
  },
})
</script>

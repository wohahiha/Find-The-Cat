<template>
  <div class="space-y-4 rounded-xl border border-border-panel bg-panel/80 p-6 shadow-panel">
    <div class="flex items-center gap-3">
      <span class="material-symbols-outlined text-primary text-2xl">pending_actions</span>
      <div class="space-y-1">
        <h1 class="text-2xl font-bold leading-tight tracking-tight">{{ title }}</h1>
        <p v-if="description" class="text-sm text-muted leading-relaxed">{{ description }}</p>
      </div>
    </div>
    <div class="rounded-lg border border-dashed border-input-border bg-background-dark/40 p-4 text-sm text-muted leading-relaxed">
      <slot>页面建设中，功能与数据对接将在后续补充。</slot>
    </div>
  </div>
</template>

<script setup>
defineProps({
  title: {
    type: String,
    default: '页面建设中',
  },
  description: {
    type: String,
    default: '',
  },
})
</script>

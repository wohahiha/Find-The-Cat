<template>
  <div
    v-for="n in count"
    :key="n"
    class="w-full rounded-lg bg-border-panel/60 animate-pulse"
    :style="{ height: height }"
  ></div>
</template>

<script setup>
defineProps({
  count: {
    type: Number,
    default: 3,
  },
  height: {
    type: String,
    default: '12px',
  },
})
</script>

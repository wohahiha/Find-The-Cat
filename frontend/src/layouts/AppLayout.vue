<template>
  <div :class="['dark min-h-screen bg-background-dark text-text', themeClass]">
    <div class="relative min-h-screen">
      <div class="absolute inset-0 bg-background-dark"></div>
      <div
        class="absolute inset-0"
        :class="gradientClass"
      ></div>
      <div class="relative z-10 min-h-screen">
        <router-view />
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const theme = computed(() => 'blue')
const themeClass = computed(() => '')
const gradientClass = computed(() => 'bg-[radial-gradient(circle_at_center,_rgba(37,71,244,0.12),_transparent_46%)]')
</script>

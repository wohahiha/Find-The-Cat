<template>
  <div class="flex items-center justify-center gap-2 text-muted">
    <span class="loader inline-block"></span>
    <slot>加载中…</slot>
  </div>
</template>

<style scoped>
.loader {
  width: 18px;
  height: 18px;
  border: 2px solid rgba(255, 255, 255, 0.2);
  border-top-color: #ffffff;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>

<template>
  <div class="dark min-h-screen bg-background-dark text-text flex items-center justify-center px-4">
    <div class="max-w-lg w-full space-y-4 text-center">
      <div class="inline-flex h-16 w-16 items-center justify-center rounded-full bg-primary/15 text-primary text-2xl font-bold">
        404
      </div>
      <h1 class="text-3xl font-bold tracking-tight">页面未找到</h1>
      <p class="text-sm text-muted leading-relaxed">
        你访问的页面不存在或已迁移。请检查链接，或返回首页继续浏览。
      </p>
      <div class="flex items-center justify-center gap-3">
        <router-link
          to="/"
          class="inline-flex h-10 items-center justify-center rounded-lg bg-primary px-4 text-sm font-bold text-primary-foreground hover:bg-primary/90"
        >
          回到首页
        </router-link>
        <router-link
          to="/profile"
          class="inline-flex h-10 items-center justify-center rounded-lg border border-input-border px-4 text-sm font-bold text-text hover:border-primary hover:text-primary"
        >
          个人中心
        </router-link>
      </div>
    </div>
  </div>
</template>

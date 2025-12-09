<template>
  <AppShell>
    <div class="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      <header class="space-y-2">
        <p class="text-xs uppercase tracking-[0.08em] text-primary">危险操作</p>
        <h1 class="text-3xl font-bold leading-tight tracking-tight">注销账号</h1>
        <p class="text-sm text-muted">此操作不可逆，请确认你的密码以继续。</p>
      </header>

      <div class="rounded-xl border border-border-panel bg-panel/90 p-5 shadow-panel space-y-4">
        <div class="space-y-2">
          <label class="text-sm font-semibold">密码确认</label>
          <input
            v-model="password"
            type="password"
            class="h-11 w-full rounded-lg border border-input-border bg-input px-3 text-sm text-text placeholder:text-muted focus:border-primary focus:ring-2 focus:ring-primary/40 outline-none"
            placeholder="请输入密码"
            :disabled="submitting"
          />
        </div>
        <p class="text-xs text-danger leading-relaxed">
          注销后你的账号、比赛记录和相关数据可能被删除或无法恢复。请谨慎操作。
        </p>
        <div class="flex items-center gap-3">
          <button
            class="h-11 flex-1 rounded-lg bg-danger text-white text-sm font-semibold hover:bg-danger/90 disabled:opacity-60"
            type="button"
            :disabled="submitting"
            @click="deactivate"
          >
            确认注销
          </button>
          <RouterLink
            to="/profile"
            class="inline-flex h-11 items-center justify-center rounded-lg border border-input-border px-4 text-sm font-semibold text-text hover:border-primary hover:text-primary"
          >
            返回
          </RouterLink>
        </div>
      </div>
    </div>
  </AppShell>
</template>

<script setup>
import { ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import AppShell from '@/components/AppShell.vue'
import api from '@/api/client'
import { parseApiError } from '@/api/errors'
import { useToastStore } from '@/stores/toast'

const router = useRouter()
const toast = useToastStore()
const password = ref('')
const submitting = ref(false)

const deactivate = async () => {
  if (!password.value) {
    toast.error('请输入密码')
    return
  }
  submitting.value = true
  try {
    await api.post('/accounts/me/deactivate/', { password: password.value })
    toast.success('注销成功')
    router.push('/login')
  } catch (err) {
    toast.error(parseApiError(err))
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <AppShell>
    <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <div class="space-y-1">
          <p class="text-xs uppercase tracking-[0.08em] text-primary">靶机管理</p>
          <h1 class="text-3xl font-bold leading-tight tracking-tight">我的靶机</h1>
          <p class="text-sm text-muted">查看靶机状态，支持停止释放。</p>
        </div>
        <button
          class="inline-flex h-10 items-center justify-center rounded-lg border border-input-border px-4 text-sm font-semibold text-text hover:border-primary hover:text-primary"
          type="button"
          @click="fetchMachines"
        >
          刷新
        </button>
      </div>

      <div v-if="loading" class="space-y-3">
        <SkeletonBlock :count="3" height="16px" />
      </div>
      <ErrorState v-else-if="error" :message="error" retry-label="重试" @retry="fetchMachines" />
      <EmptyState v-else-if="!machines.length" title="暂无靶机" />
      <div v-else class="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
        <div
          v-for="machine in machines"
          :key="machine.id"
          class="flex flex-col rounded-xl border border-border-panel bg-panel/90 p-5 shadow-panel space-y-3"
        >
          <div class="flex items-start justify-between gap-2">
            <div>
              <p class="text-lg font-bold leading-tight">{{ machine.name || `靶机 ${machine.id}` }}</p>
              <p class="text-xs text-muted mt-1 line-clamp-2">{{ machine.description }}</p>
            </div>
            <span class="inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold bg-primary/15 text-primary">
              {{ machine.status || 'running' }}
            </span>
          </div>
          <div class="text-xs text-muted space-y-1">
            <p v-if="machine.expire_at">到期：{{ formatDateTime(machine.expire_at) }}</p>
            <p v-if="machine.created_at">创建：{{ formatDateTime(machine.created_at) }}</p>
            <p v-if="machine.challenge">关联题目：{{ machine.challenge }}</p>
          </div>
          <button
            class="h-10 rounded-lg border border-input-border text-sm font-semibold text-text hover:border-primary hover:text-primary disabled:opacity-60"
            type="button"
            :disabled="stopping[machine.id]"
            @click="stopMachine(machine.id)"
          >
            停止
          </button>
        </div>
      </div>
    </div>
  </AppShell>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import AppShell from '@/components/AppShell.vue'
import api from '@/api/client'
import { SkeletonBlock, EmptyState, ErrorState } from '@/components/ui'
import { parseApiError } from '@/api/errors'
import { useToastStore } from '@/stores/toast'
import { formatDateTime } from '@/utils/format'

const machines = ref([])
const loading = ref(false)
const error = ref('')
const stopping = reactive({})
const toast = useToastStore()

const fetchMachines = async () => {
  loading.value = true
  error.value = ''
  try {
    const res = await api.get('/machines/')
    const data = res?.data?.data || res?.data || {}
    machines.value = data.items || data || []
  } catch (err) {
    const msg = parseApiError(err)
    error.value = msg
    toast.error(msg)
  } finally {
    loading.value = false
  }
}

const stopMachine = async (id) => {
  stopping[id] = true
  try {
    await api.post(`/machines/${id}/stop/`, {})
    toast.success('已停止靶机')
    fetchMachines()
  } catch (err) {
    toast.error(parseApiError(err))
  } finally {
    stopping[id] = false
  }
}

onMounted(() => {
  fetchMachines()
})
</script>

<template>
  <AppShell>
    <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <div class="space-y-1">
          <p class="text-xs uppercase tracking-[0.08em] text-primary">靶机管理</p>
          <h1 class="text-3xl font-bold leading-tight tracking-tight">我的靶机</h1>
          <p class="text-sm text-muted">查看靶机状态，支持重启、延时与停止。</p>
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
            <p v-if="machine.challenge">
              关联题目：
              <RouterLink
                class="text-primary hover:underline"
                :to="challengeLink(machine)"
              >
                {{ machine.challenge }}
              </RouterLink>
            </p>
            <p v-if="countdowns[machine.id] !== null && countdowns[machine.id] !== undefined">
              剩余：{{ displayCountdown(countdowns[machine.id]) }}
            </p>
            <p v-if="machine.remaining_extend_times !== undefined && machine.remaining_extend_times !== null">
              可延时次数：{{ machine.remaining_extend_times === -1 ? '不限' : machine.remaining_extend_times }}
            </p>
          </div>
          <div class="grid grid-cols-1 gap-2">
            <div class="grid grid-cols-3 gap-2">
              <button
                class="h-10 rounded-lg border border-input-border text-sm font-semibold text-text hover:border-primary hover:text-primary disabled:opacity-60"
                type="button"
                :disabled="stopping[machine.id]"
                @click="restartMachine(machine)"
              >
                重启
              </button>
              <button
                class="h-10 rounded-lg border border-input-border text-sm font-semibold text-text hover:border-primary hover:text-primary disabled:opacity-60"
                type="button"
                :disabled="stopping[machine.id]"
                @click="extendMachine(machine)"
              >
                延时
              </button>
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
      </div>
    </div>
  </AppShell>
</template>

<script setup>
import { onMounted, onBeforeUnmount, reactive, ref } from 'vue'
import AppShell from '@/components/AppShell.vue'
import api from '@/api/client'
import { SkeletonBlock, EmptyState, ErrorState } from '@/components/ui'
import { parseApiError } from '@/api/errors'
import { useToastStore } from '@/stores/toast'
import { formatDateTime } from '@/utils/format'
import realtime from '@/utils/realtime'

const machines = ref([])
const loading = ref(false)
const error = ref('')
const stopping = reactive({})
const countdowns = reactive({})
const toast = useToastStore()
let countdownTimer = null

const fetchMachines = async () => {
  loading.value = true
  error.value = ''
  try {
    const res = await api.get('/machines/', { params: { page_size: 50 } })
    const data = res?.data?.data || res?.data || {}
    const list = data.items || data || []
    machines.value = list
    list.forEach((m) => updateCountdown(m))
  } catch (err) {
    const msg = parseApiError(err)
    error.value = msg
    toast.error(msg)
  } finally {
    loading.value = false
  }
}

const stopMachine = async (id) => {
  if (!id) return
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

const restartMachine = async (machine) => {
  if (!machine?.contest || !machine?.challenge) {
    toast.error('缺少靶机上下文，无法重启')
    return
  }
  stopping[machine.id] = true
  try {
    await api.post('/machines/', {
      contest_slug: machine.contest,
      challenge_slug: machine.challenge,
    })
    toast.success('靶机已重新启动')
    fetchMachines()
  } catch (err) {
    toast.error(parseApiError(err))
  } finally {
    stopping[machine.id] = false
  }
}

const extendMachine = async (machine) => {
  if (!machine?.id) return
  stopping[machine.id] = true
  try {
    await api.post(`/machines/${machine.id}/extend/`, {})
    toast.success('靶机已延时')
    fetchMachines()
  } catch (err) {
    toast.error(parseApiError(err))
  } finally {
    stopping[machine.id] = false
  }
}

const challengeLink = (machine) => {
  if (!machine?.contest || !machine?.challenge) return `/contests`
  // 跳转到比赛题目页，携带 query 以便前端打开对应题目
  return {
    path: `/contests/${machine.contest}/challenges`,
    query: { challenge: machine.challenge },
  }
}

const updateCountdown = (machine) => {
  if (!machine?.id) return
  if (machine.remaining_seconds === undefined || machine.remaining_seconds === null) {
    countdowns[machine.id] = null
    return
  }
  countdowns[machine.id] = machine.remaining_seconds
}

const displayCountdown = (seconds) => {
  if (seconds === null || seconds === undefined) return '--'
  const s = Math.max(0, Math.floor(seconds))
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = s % 60
  if (h > 0) return `${h}h ${m}m ${sec}s`
  if (m > 0) return `${m}m ${sec}s`
  return `${sec}s`
}

const tickCountdown = () => {
  Object.keys(countdowns).forEach((key) => {
    const cur = countdowns[key]
    if (cur === null || cur === undefined) return
    countdowns[key] = Math.max(0, cur - 1)
  })
}

let offRealtime = null
const handleRealtime = (evt) => {
  if (!evt || !evt.event || !evt.event.startsWith('machine_')) return
  fetchMachines()
}

onMounted(() => {
  fetchMachines()
  countdownTimer = setInterval(tickCountdown, 1000)
  offRealtime = realtime.onAny(handleRealtime)
})

onBeforeUnmount(() => {
  if (offRealtime) offRealtime()
  if (countdownTimer) clearInterval(countdownTimer)
})
</script>

<template>
  <AppShell>
    <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <div class="space-y-1">
          <p class="text-xs uppercase tracking-[0.08em] text-primary">记分板</p>
          <h1 class="text-3xl font-bold leading-tight tracking-tight">{{ contestTitle }}</h1>
          <p class="text-sm text-muted">实时分数榜，支持刷新。</p>
        </div>
        <RouterLink
          :to="`/contests/${contestSlug}`"
          class="inline-flex h-10 items-center justify-center rounded-lg border border-input-border px-4 text-sm font-semibold text-text hover:border-primary hover:text-primary"
        >
          返回比赛
        </RouterLink>
      </div>

      <div class="flex items-center gap-3">
        <button
          class="inline-flex h-10 items-center justify-center rounded-lg border border-input-border px-4 text-sm font-semibold text-text hover:border-primary hover:text-primary"
          type="button"
          @click="fetchScoreboard"
        >
          刷新
        </button>
      </div>

      <div v-if="loading" class="space-y-3">
        <SkeletonBlock :count="3" height="16px" />
      </div>
      <ErrorState v-else-if="error" :message="error" retry-label="重试" @retry="fetchScoreboard" />
      <EmptyState v-else-if="!rows.length" title="暂无数据" />
      <div v-else class="overflow-x-auto rounded-xl border border-border-panel bg-panel/90 shadow-panel">
        <table class="min-w-full text-sm text-left">
          <thead class="border-b border-border-panel/70 text-muted">
            <tr>
              <th class="px-4 py-3 font-semibold w-16">排名</th>
              <th class="px-4 py-3 font-semibold">名称</th>
              <th class="px-4 py-3 font-semibold">分数</th>
              <th class="px-4 py-3 font-semibold">解题数</th>
              <th class="px-4 py-3 font-semibold">最后提交</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, idx) in rows" :key="idx" class="border-b border-border-panel/50 last:border-0">
              <td class="px-4 py-3 text-muted">#{{ idx + 1 }}</td>
              <td class="px-4 py-3 font-semibold">{{ row.name || row.team || row.user || '选手' }}</td>
              <td class="px-4 py-3 text-primary font-bold">{{ row.score ?? row.total ?? 0 }}</td>
              <td class="px-4 py-3">{{ row.solved_count ?? row.solved ?? row.solves ?? 0 }}</td>
              <td class="px-4 py-3 text-muted whitespace-nowrap">{{ row.last_submit ? formatDateTime(row.last_submit) : '--' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </AppShell>
</template>

<script setup>
import { computed, onMounted, onBeforeUnmount, ref } from 'vue'
import { useRoute, RouterLink } from 'vue-router'
import AppShell from '@/components/AppShell.vue'
import api from '@/api/client'
import { SkeletonBlock, EmptyState, ErrorState } from '@/components/ui'
import { parseApiError } from '@/api/errors'
import { useToastStore } from '@/stores/toast'
import { formatDateTime } from '@/utils/format'
import { useContestChannel } from '@/composables/useContestChannel'
import realtime from '@/utils/realtime'

const route = useRoute()
const toast = useToastStore()
const contestSlug = computed(() => route.params.contestSlug)

const contestTitle = ref('记分板')
const rows = ref([])
const loading = ref(false)
const error = ref('')

const fetchScoreboard = async () => {
  loading.value = true
  error.value = ''
  try {
    // 直接复用比赛详情中的 scoreboard 字段
    const res = await api.get(`/contests/${contestSlug.value}/`)
    const data = res?.data?.data || res?.data || {}
    contestTitle.value = data?.contest?.name || contestSlug.value || '记分板'
    rows.value = data?.scoreboard || []
  } catch (err) {
    const msg = parseApiError(err)
    error.value = msg
    toast.error(msg)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchScoreboard()
})

// 订阅比赛 WS 事件：榜单更新/快照
const { leave: leaveChannel } = useContestChannel(contestSlug.value, {
  onMessage: (evt) => {
    if (!evt || evt.contest !== contestSlug.value) return
    if (evt.event === 'scoreboard_snapshot' && evt.entries) {
      rows.value = evt.entries || []
    }
    if (evt.event === 'scoreboard_updated') {
      fetchScoreboard()
    }
  },
})

// 初始尝试使用已有快照（若存在）
const snapshot = realtime.getSnapshot(contestSlug.value)
if (snapshot?.entries) {
  rows.value = snapshot.entries
}

onBeforeUnmount(() => {
  leaveChannel()
})
</script>

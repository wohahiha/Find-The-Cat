<template>
  <AppShell>
    <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <div class="space-y-1">
          <p class="text-xs uppercase tracking-[0.08em] text-primary">战队管理</p>
          <h1 class="text-3xl font-bold leading-tight tracking-tight">队伍控制台</h1>
          <p class="text-sm text-muted">需提供 contest_slug 后查看队伍并进行管理。</p>
        </div>
        <div class="flex gap-2">
          <input
            v-model="contestSlug"
            placeholder="contest_slug"
            class="h-10 w-52 rounded-lg border border-input-border bg-input px-3 text-sm text-text placeholder:text-muted focus:border-primary focus:ring-2 focus:ring-primary/40 outline-none"
            @keyup.enter="fetchTeams"
          />
          <button
            class="inline-flex h-10 items-center justify-center rounded-lg bg-primary px-4 text-sm font-semibold text-primary-foreground hover:bg-primary/90"
            type="button"
            @click="fetchTeams"
          >
            加载
          </button>
        </div>
      </div>

      <div v-if="loading" class="space-y-3">
        <SkeletonBlock :count="3" height="16px" />
      </div>
      <ErrorState v-else-if="error" :message="error" retry-label="重试" @retry="fetchTeams" />
      <EmptyState v-else-if="!teams.length" title="暂无战队" />
      <div v-else class="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
        <div
          v-for="team in teams"
          :key="team.id"
          class="rounded-xl border border-border-panel bg-panel/90 p-4 shadow-panel space-y-2"
        >
          <div class="flex items-start justify-between gap-2">
            <div>
              <p class="text-lg font-bold leading-tight">{{ team.name }}</p>
              <p class="text-xs text-muted mt-1">邀请码：{{ team.invite_token || team.invite_code || '——' }}</p>
            </div>
            <span class="text-xs text-muted">{{ (team.members || []).length }} 人</span>
          </div>
          <div class="flex gap-2 pt-2">
            <button
              class="flex-1 h-10 rounded-lg border border-input-border text-sm font-semibold text-text hover:border-primary hover:text-primary disabled:opacity-60"
              type="button"
              :disabled="pending[team.id]"
              @click="resetInvite(team.id)"
            >
              重置邀请码
            </button>
            <button
              class="flex-1 h-10 rounded-lg border border-danger/50 text-sm font-semibold text-danger hover:border-danger hover:text-danger disabled:opacity-60"
              type="button"
              :disabled="pending[team.id]"
              @click="disbandTeam(team.id)"
            >
              解散
            </button>
          </div>
        </div>
      </div>
    </div>
  </AppShell>
</template>

<script setup>
import { reactive, ref } from 'vue'
import AppShell from '@/components/AppShell.vue'
import api from '@/api/client'
import { SkeletonBlock, EmptyState, ErrorState } from '@/components/ui'
import { parseApiError } from '@/api/errors'
import { useToastStore } from '@/stores/toast'

const contestSlug = ref('')
const teams = ref([])
const loading = ref(false)
const error = ref('')
const pending = reactive({})
const toast = useToastStore()

const fetchTeams = async () => {
  if (!contestSlug.value) {
    error.value = '请先输入 contest_slug'
    return
  }
  loading.value = true
  error.value = ''
  try {
    const res = await api.get(`/contests/${contestSlug.value}/teams/`)
    const data = res?.data?.data || res?.data || {}
    teams.value = data.items || data || []
  } catch (err) {
    const msg = parseApiError(err)
    error.value = msg
    toast.error(msg)
  } finally {
    loading.value = false
  }
}

const disbandTeam = async (id) => {
  pending[id] = true
  try {
    await api.post(`/contests/teams/${id}/disband/`, {})
    toast.success('解散成功')
    fetchTeams()
  } catch (err) {
    toast.error(parseApiError(err))
  } finally {
    pending[id] = false
  }
}

const resetInvite = async (id) => {
  pending[id] = true
  try {
    await api.post(`/contests/teams/${id}/invite/reset/`, {})
    toast.success('邀请码已重置')
    fetchTeams()
  } catch (err) {
    toast.error(parseApiError(err))
  } finally {
    pending[id] = false
  }
}
</script>

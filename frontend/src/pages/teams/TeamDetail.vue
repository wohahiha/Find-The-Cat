<template>
  <AppShell>
    <div class="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <div class="space-y-1">
          <p class="text-xs uppercase tracking-[0.08em] text-primary">战队详情</p>
          <h1 class="text-3xl font-bold leading-tight tracking-tight">
            {{ team?.name || contestTitle }}
          </h1>
          <p class="text-sm text-muted">
            {{ contest ? `比赛：${contest.name || contest.slug}` : '查看比赛下我的战队信息与成员' }}
          </p>
        </div>
        <div class="flex items-center gap-2">
          <RouterLink
            :to="{ name: 'teams' }"
            class="inline-flex h-10 items-center justify-center rounded-lg border border-input-border px-4 text-sm font-semibold text-text hover:border-primary hover:text-primary"
          >
            返回战队列表
          </RouterLink>
          <button
            class="inline-flex h-10 items-center justify-center rounded-lg bg-primary px-4 text-sm font-semibold text-primary-foreground hover:bg-primary/90"
            type="button"
            @click="fetchDetail"
          >
            刷新
          </button>
        </div>
      </div>

      <div v-if="loading" class="space-y-3">
        <SkeletonBlock :count="3" height="16px" />
      </div>
      <ErrorState v-else-if="error" :message="error" retry-label="重试" @retry="fetchDetail" />
      <EmptyState
        v-else-if="!team"
        title="暂无队伍"
        description="你当前不在此比赛的战队中，前往战队列表创建或加入。"
        action-label="返回战队列表"
        @action="router.push({ name: 'teams' })"
      />
      <div v-else class="space-y-4">
        <div class="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <div class="lg:col-span-2 rounded-xl border border-border-panel bg-panel/90 p-5 shadow-panel space-y-3">
            <div class="flex items-start justify-between gap-3">
              <div class="space-y-1">
                <p class="text-sm font-semibold text-text">队伍信息</p>
                <p class="text-xs text-muted">邀请码、队长与简介</p>
              </div>
              <span class="inline-flex items-center rounded-full bg-primary/10 px-2 py-0.5 text-xs text-primary">
                {{ roleLabel }}
              </span>
            </div>
            <div class="space-y-2 text-sm text-text">
              <div class="flex items-center gap-2">
                <span class="text-muted">邀请码：</span>
                <span class="font-mono text-primary">{{ team.invite_token || '——' }}</span>
              </div>
              <div class="flex items-center gap-2">
                <span class="text-muted">队长：</span>
                <span>{{ captainName || '未知' }}</span>
              </div>
              <div class="flex items-start gap-2">
                <span class="text-muted">简介：</span>
                <span class="text-text/90">{{ team.description || '暂无简介' }}</span>
              </div>
              <div class="flex items-center gap-2">
                <span class="text-muted">成员数：</span>
                <span>{{ members.length }} 人</span>
              </div>
            </div>
          </div>
          <div class="rounded-xl border border-border-panel bg-panel/90 p-5 shadow-panel space-y-3">
            <p class="text-sm font-semibold text-text">队伍操作</p>
            <p class="text-xs text-muted">退出后可返回战队列表重新创建或加入新的队伍。</p>
            <button
              class="h-10 w-full rounded-lg border border-danger/50 text-sm font-semibold text-danger hover:border-danger hover:text-danger disabled:opacity-60"
              type="button"
              :disabled="leaving"
              @click="leaveTeam"
            >
              退出当前队伍
            </button>
          </div>
        </div>

        <div class="rounded-xl border border-border-panel bg-panel/90 p-5 shadow-panel space-y-3">
          <div class="flex items-center justify-between">
            <div>
              <p class="text-sm font-semibold">队伍成员</p>
              <p class="text-xs text-muted">包含队长与所有有效成员</p>
            </div>
            <span class="text-xs text-muted">{{ members.length }} 人</span>
          </div>
          <div v-if="!members.length" class="text-xs text-muted">暂无成员</div>
          <div v-else class="divide-y divide-border-panel/80 rounded-lg border border-border-panel/80">
            <div v-for="member in members" :key="member.id" class="flex items-center justify-between px-4 py-3">
              <div class="space-y-0.5">
                <p class="text-sm font-semibold text-text">{{ member.username || '未知用户' }}</p>
                <p class="text-xs text-muted">加入时间：{{ formatDate(member.joined_at) }}</p>
              </div>
              <span
                class="inline-flex items-center rounded-full bg-primary/10 px-2 py-0.5 text-[11px] font-semibold text-primary"
              >
                {{ member.role === 'captain' ? '队长' : '队员' }}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </AppShell>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppShell from '@/components/AppShell.vue'
import api from '@/api/client'
import { SkeletonBlock, EmptyState, ErrorState } from '@/components/ui'
import { parseApiError } from '@/api/errors'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const toast = useToastStore()

const contestSlug = computed(() => route.params.contestSlug || '')
const contest = ref(null)
const team = ref(null)
const loading = ref(false)
const error = ref('')
const leaving = ref(false)

const members = computed(() => {
  const list = team.value?.members || []
  return [...list].sort((a, b) => {
    if (a.role === b.role) return 0
    return a.role === 'captain' ? -1 : 1
  })
})

const currentUserId = computed(() => auth.user?.id || null)

const roleLabel = computed(() => {
  if (!team.value) return '——'
  if (team.value.captain_id && currentUserId.value === team.value.captain_id) return '队长'
  const self = members.value.find((m) => m.id === currentUserId.value)
  return self?.role === 'captain' ? '队长' : '队员'
})

const captainName = computed(() => {
  if (!team.value) return ''
  const found = members.value.find((m) => m.id === team.value.captain_id)
  return found?.username || ''
})

const contestTitle = computed(() => contest.value?.name || contest.value?.slug || contestSlug.value)

const fetchDetail = async () => {
  if (!contestSlug.value) {
    error.value = '缺少比赛标识'
    return
  }
  loading.value = true
  error.value = ''
  try {
    const res = await api.get(`/contests/${contestSlug.value}/`)
    const data = res?.data?.data || res?.data || {}
    contest.value = data.contest || null
    team.value = data.my_team || null
    if (!team.value) {
      toast.info('你当前不在该比赛的战队中')
    }
  } catch (err) {
    const msg = parseApiError(err)
    error.value = msg
    toast.error(msg)
  } finally {
    loading.value = false
  }
}

const leaveTeam = async () => {
  if (!contestSlug.value) {
    toast.error('缺少比赛标识，无法退出')
    return
  }
  leaving.value = true
  try {
    await api.post(`/contests/${contestSlug.value}/teams/leave/`, {})
    toast.success('已退出队伍')
    router.push({ name: 'teams' })
  } catch (err) {
    toast.error(parseApiError(err))
  } finally {
    leaving.value = false
  }
}

const formatDate = (val) => {
  if (!val) return '未知'
  const d = new Date(val)
  if (Number.isNaN(d.getTime())) return String(val)
  const y = d.getFullYear()
  const m = `${d.getMonth() + 1}`.padStart(2, '0')
  const day = `${d.getDate()}`.padStart(2, '0')
  return `${y}-${m}-${day}`
}

onMounted(() => {
  fetchDetail()
})

watch(contestSlug, (val, oldVal) => {
  if (val && val !== oldVal) {
    fetchDetail()
  }
})
</script>

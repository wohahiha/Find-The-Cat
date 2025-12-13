<template>
  <AppShell>
    <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      <div class="rounded-xl border border-border-panel bg-panel/90 p-5 shadow-panel space-y-4">
        <div class="flex flex-wrap items-center justify-between gap-3">
          <div class="space-y-1">
            <p class="text-xs uppercase tracking-[0.08em] text-primary">战队</p>
            <h1 class="text-3xl font-bold leading-tight tracking-tight">比赛战队</h1>
            <p class="text-sm text-muted">选择比赛后创建或加入战队，可点击右侧按钮刷新“我的战队”列表。</p>
          </div>
          <div class="flex items-center gap-2">
            <button
              class="inline-flex h-10 items-center justify-center rounded-lg bg-primary px-4 text-sm font-semibold text-primary-foreground hover:bg-primary/90"
              type="button"
              @click="fetchTeams"
            >
              刷新我的战队
            </button>
          </div>
        </div>

        <div class="grid grid-cols-1 gap-3 md:grid-cols-2">
          <div class="flex flex-col gap-2">
            <label class="text-sm font-semibold">选择比赛</label>
            <select
              v-model="contestSlug"
              class="h-11 rounded-lg border border-input-border bg-input px-3 text-sm text-text focus:border-primary focus:ring-2 focus:ring-primary/40 outline-none"
              @change="fetchTeams"
            >
              <option value="">请选择比赛</option>
              <option v-for="item in contestsOptions" :key="item.slug" :value="item.slug">
                {{ item.name }}
              </option>
            </select>
          </div>
          <div class="flex flex-col gap-2">
            <label class="text-sm font-semibold">搜索比赛</label>
            <div class="relative">
              <input
                v-model="contestSearch"
                placeholder="输入比赛名称"
                class="h-11 w-full rounded-lg border border-input-border bg-input px-3 text-sm text-text placeholder:text-muted focus:border-primary focus:ring-2 focus:ring-primary/40 outline-none"
              />
              <div
                v-if="filteredContests.length"
                class="absolute z-20 mt-1 w-full rounded-lg border border-input-border bg-panel/95 shadow-panel max-h-56 overflow-y-auto"
              >
                <button
                  v-for="item in filteredContests"
                  :key="item.slug"
                  class="w-full text-left px-3 py-2 text-sm text-text hover:bg-input-border"
                  type="button"
                  @click="selectContest(item)"
                >
                  {{ item.name }}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
      <!-- 搜索战队功能暂时移除 -->

      <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
        <div class="rounded-xl border border-border-panel bg-panel/90 p-5 shadow-panel space-y-3">
          <h3 class="text-lg font-bold">创建战队</h3>
          <input
            v-model="createForm.name"
            placeholder="战队名称"
            class="h-10 w-full rounded-lg border border-input-border bg-input px-3 text-sm text-text placeholder:text-muted focus:border-primary focus:ring-2 focus:ring-primary/40 outline-none"
          />
          <input
            v-model="createForm.description"
            placeholder="战队简介（可选）"
            class="h-10 w-full rounded-lg border border-input-border bg-input px-3 text-sm text-text placeholder:text-muted focus:border-primary focus:ring-2 focus:ring-primary/40 outline-none"
          />
          <button
            class="h-10 w-full rounded-lg bg-primary text-primary-foreground text-sm font-semibold hover:bg-primary/90 disabled:opacity-60"
            type="button"
            :disabled="creating || !canOperate"
            @click="createTeam"
          >
            创建
          </button>
        </div>
        <div class="rounded-xl border border-border-panel bg-panel/90 p-5 shadow-panel space-y-3">
          <h3 class="text-lg font-bold">加入战队</h3>
          <input
            v-model="inviteToken"
            placeholder="邀请码"
            class="h-10 w-full rounded-lg border border-input-border bg-input px-3 text-sm text-text placeholder:text-muted focus:border-primary focus:ring-2 focus:ring-primary/40 outline-none"
          />
          <button
            class="h-10 w-full rounded-lg border border-input-border text-sm font-semibold text-text hover:border-primary hover:text-primary disabled:opacity-60"
            type="button"
            :disabled="joining || !canOperate"
            @click="joinTeam"
          >
            加入
          </button>
          <p v-if="!canOperate" class="text-xs text-muted">{{ disabledReason }}</p>
          <p class="text-xs text-muted">退出队伍请在下方对应的战队卡片或战队详情页操作。</p>
        </div>
      </div>

      <div v-if="loading" class="space-y-3">
        <SkeletonBlock :count="3" height="16px" />
      </div>
      <ErrorState v-else-if="error" :message="error" retry-label="重试" @retry="fetchTeams" />
      <EmptyState v-else-if="!filteredTeams.length" title="暂无战队" />
      <div v-else class="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
        <div
          v-for="team in filteredTeams"
          :key="team.id"
          class="rounded-xl border border-border-panel bg-panel/90 p-4 shadow-panel space-y-2"
        >
          <div class="space-y-1">
            <div class="flex items-start justify-between gap-2">
              <div>
                <p class="text-lg font-bold leading-tight">{{ team.name }}</p>
                <p class="text-xs text-muted mt-1">比赛：{{ team.contest?.name || team.contest?.slug || '未知' }}</p>
              </div>
              <div class="text-right space-y-1">
                <span class="inline-flex items-center rounded-full bg-primary/10 px-2 py-0.5 text-xs text-primary">
                  {{ team.role === 'captain' ? '队长' : '队员' }}
                </span>
                <p class="text-[11px] text-muted">{{ team.status || '——' }}</p>
              </div>
            </div>
            <p class="text-xs text-muted">邀请码：{{ team.invite_token || team.invite_code || '——' }}</p>
            <p class="text-xs text-muted">
              成员状态：{{ team.is_active ? '有效' : '已退出/失效' }} · 加入于 {{ formatDate(team.joined_at) }}
            </p>
          </div>
          <div class="flex items-center gap-2 pt-1">
            <RouterLink
              v-if="team.contest?.slug"
              :to="{ name: 'team-detail', params: { contestSlug: team.contest.slug } }"
              class="flex-1 inline-flex h-9 items-center justify-center rounded-lg border border-input-border text-xs font-semibold text-text hover:border-primary hover:text-primary"
            >
              战队详情
            </RouterLink>
            <button
              class="flex-1 h-9 rounded-lg border border-danger/50 text-xs font-semibold text-danger hover:border-danger hover:text-danger disabled:opacity-60"
              type="button"
              :disabled="!team.contest?.slug || leaving === team.contest?.slug"
              @click="leaveTeam(team.contest?.slug, team.name)"
            >
              退出该队伍
            </button>
          </div>
        </div>
      </div>
    </div>
  </AppShell>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import AppShell from '@/components/AppShell.vue'
import api from '@/api/client'
import { SkeletonBlock, EmptyState, ErrorState } from '@/components/ui'
import { parseApiError } from '@/api/errors'
import { useToastStore } from '@/stores/toast'
import { containsDangerousHtml } from '@/utils/validation'

const toast = useToastStore()
const contestSlug = ref('')
const contestSearch = ref('')
const contestsOptions = ref([])
// 搜索战队功能暂时移除
const teams = ref([])
const loading = ref(false)
const error = ref('')
const createForm = ref({ name: '', description: '' })
const inviteToken = ref('')
const creating = ref(false)
const joining = ref(false)
const leaving = ref('')

const filteredContests = computed(() => {
  if (!contestSearch.value) return []
  const q = contestSearch.value.toLowerCase()
  return contestsOptions.value.filter((c) => (c.name || '').toLowerCase().includes(q))
})

const selectedContest = computed(() => contestsOptions.value.find((c) => c.slug === contestSlug.value) || null)

const canOperate = computed(() => {
  const c = selectedContest.value
  if (!c) return false
  const start = c.start_time ? new Date(c.start_time).getTime() : null
  const notStarted = start ? start > Date.now() : true
  return Boolean(c.registration_status) && notStarted
})

const disabledReason = computed(() => {
  const c = selectedContest.value
  if (!c) return '请选择已报名且未开赛的比赛'
  if (!c.registration_status) return '仅显示已报名的比赛才可创建/加入战队'
  const start = c.start_time ? new Date(c.start_time).getTime() : null
  if (start && start <= Date.now()) return '比赛已开赛，当前不可创建或加入战队'
  return '当前不可进行战队操作'
})

const filteredTeams = computed(() => teams.value)

const selectContest = (item) => {
  contestSlug.value = item.slug
  contestSearch.value = item.name
}

const fetchTeams = async () => {
  loading.value = true
  error.value = ''
  try {
    const res = await api.get('/contests/teams/mine/')
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

const createTeam = async () => {
  if (!contestSlug.value || !canOperate.value) {
    toast.error(disabledReason.value)
    return
  }
  if (!createForm.value.name) {
    toast.error('请输入战队名称')
    return
  }
  if (containsDangerousHtml(createForm.value.name) || containsDangerousHtml(createForm.value.description)) {
    toast.error('战队名称或简介不能包含 script/iframe/onerror 等 HTML 片段')
    return
  }
  creating.value = true
  try {
    await api.post(`/contests/${contestSlug.value}/teams/`, {
      name: createForm.value.name,
      description: createForm.value.description || undefined,
    })
    toast.success('创建成功')
    createForm.value.name = ''
    createForm.value.description = ''
    fetchTeams()
  } catch (err) {
    toast.error(parseApiError(err))
  } finally {
    creating.value = false
  }
}

const joinTeam = async () => {
  if (!contestSlug.value || !canOperate.value) {
    toast.error(disabledReason.value)
    return
  }
  if (!inviteToken.value) {
    toast.error('请输入邀请码 (invite_token)')
    return
  }
  joining.value = true
  try {
    await api.post(`/contests/${contestSlug.value}/teams/join/`, { invite_token: inviteToken.value })
    toast.success('加入成功')
    inviteToken.value = ''
    fetchTeams()
  } catch (err) {
    toast.error(parseApiError(err))
  } finally {
    joining.value = false
  }
}

const leaveTeam = async (slug, name) => {
  const targetSlug = slug || contestSlug.value
  if (!targetSlug) {
    toast.error('未找到比赛标识，无法退出队伍')
    return
  }
  leaving.value = targetSlug
  try {
    await api.post(`/contests/${targetSlug}/teams/leave/`, {})
    toast.success(name ? `已退出「${name}」` : '已退出队伍')
    if (contestSlug.value === targetSlug) {
      contestSlug.value = ''
      contestSearch.value = ''
    }
    fetchTeams()
  } catch (err) {
    toast.error(parseApiError(err))
  } finally {
    leaving.value = ''
  }
}

const fetchContestsOptions = async () => {
  try {
    const res = await api.get('/contests/', { params: { page_size: 100, status: 'upcoming' } })
    const items = res?.data?.data?.items || res?.data?.items || []
    // 只保留已报名且未开赛的比赛
    const filtered = items.filter((c) => c.registration_status)
    contestsOptions.value = filtered
    if (!filtered.length) {
      toast.info('暂无已报名且未开赛的比赛')
    }
  } catch (err) {
    toast.error(parseApiError(err))
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
  fetchContestsOptions()
  fetchTeams()
})
</script>

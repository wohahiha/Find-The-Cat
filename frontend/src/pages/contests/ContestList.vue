<template>
  <AppShell>
    <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      <header class="flex flex-wrap justify-between gap-4 items-center">
        <div class="flex min-w-72 flex-col gap-2">
          <p class="text-4xl font-black leading-tight tracking-[-0.03em]">比赛列表</p>
          <p class="text-base text-muted leading-normal">浏览进行中/即将开始的比赛，查看规则并进入挑战。</p>
        </div>
        <div class="flex items-center gap-2 p-1 overflow-x-auto bg-input rounded-lg border border-input-border">
          <button
            v-for="tab in statusTabs"
            :key="tab.value"
            class="flex h-10 shrink-0 items-center justify-center gap-x-2 rounded-md px-4 text-sm font-semibold transition-colors"
            :class="status === tab.value ? 'bg-primary text-primary-foreground' : 'text-text hover:bg-border-panel'"
            @click="changeStatus(tab.value)"
          >
            {{ tab.label }}
          </button>
        </div>
      </header>

      <div class="flex flex-col md:flex-row gap-4 px-1">
        <div class="flex-1">
          <label class="flex flex-col min-w-40 h-12 w-full">
            <div class="flex w-full flex-1 items-stretch rounded-lg h-full">
              <div class="text-muted flex border border-r-0 border-input-border bg-input items-center justify-center pl-4 rounded-l-lg">
                <span class="material-symbols-outlined">search</span>
              </div>
              <input
                v-model.trim="keyword"
                class="form-input flex w-full min-w-0 flex-1 rounded-lg text-text focus:outline-0 focus:ring-2 focus:ring-primary border border-input-border bg-input h-full placeholder:text-muted px-4 rounded-l-none border-l-0 pl-2 text-base font-normal leading-normal"
                placeholder="按名称或描述搜索"
                type="text"
                @keyup.enter="applySearch"
              />
            </div>
          </label>
        </div>
        <div class="flex items-center gap-2">
          <button
            type="button"
            class="inline-flex h-11 items-center justify-center rounded-lg border border-input-border px-4 text-sm font-semibold text-text hover:border-primary hover:text-primary"
            @click="resetFilters"
          >
            重置
          </button>
        </div>
      </div>

      <div v-if="loading" class="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
        <div v-for="i in 6" :key="i" class="flex flex-col rounded-xl border border-border-panel bg-panel/90 p-5 shadow-panel space-y-3">
          <SkeletonBlock :count="4" height="16px" />
        </div>
      </div>

      <ErrorState v-else-if="error" :message="error" retry-label="重试" @retry="fetchContests" />
      <EmptyState v-else-if="!filteredContests.length" title="暂无匹配的比赛" description="试试切换状态或清空搜索" />

      <div v-else class="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
        <div
          v-for="contest in filteredContests"
          :key="contest.slug"
          class="flex flex-col rounded-xl border border-border-panel bg-panel/90 p-5 shadow-panel"
        >
          <div class="mb-3 flex items-start justify-between gap-2">
            <div class="flex flex-col gap-1 min-w-0">
              <RouterLink
                :to="`/contests/${contest.slug}`"
                class="text-lg font-bold hover:text-primary line-clamp-1"
              >
                {{ contest.name }}
              </RouterLink>
              <p class="text-xs text-muted leading-snug line-clamp-2">{{ contest.description }}</p>
            </div>
            <div class="flex flex-wrap justify-end gap-2">
              <span
                class="inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold whitespace-nowrap flex-shrink-0"
                :class="statusClass(contest.status)"
              >
                {{ statusLabel(contest.status) }}
              </span>
              <span
                v-if="contestBadgeLabel(contest)"
                class="inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold whitespace-nowrap flex-shrink-0"
                :class="badgeClass(contestBadgeLabel(contest))"
              >
                {{ contestBadgeLabel(contest) }}
              </span>
            </div>
          </div>

          <dl class="mb-4 text-xs text-muted space-y-1">
            <div class="flex items-center gap-2">
              <dt class="font-semibold text-text/80">开始</dt>
              <dd class="text-left">{{ formatDateTime(contest.start_time) }}</dd>
            </div>
            <div class="flex items-center gap-2">
              <dt class="font-semibold text-text/80">结束</dt>
              <dd class="text-left">{{ formatDateTime(contest.end_time) }}</dd>
            </div>
            <div class="flex items-center gap-2">
              <dt class="font-semibold text-text/80">赛制</dt>
              <dd class="text-left">{{ contest.is_team_based ? `组队赛（最多 ${contest.max_team_members || 'N/A'} 人）` : '个人赛' }}</dd>
            </div>
          </dl>

          <div class="mt-auto flex items-center gap-2">
            <RouterLink
              :to="`/contests/${contest.slug}`"
              class="flex h-10 flex-1 items-center justify-center rounded-lg bg-primary text-primary-foreground text-sm font-semibold hover:bg-primary/90"
            >
              {{ ctaLabel(contest.status) }}
            </RouterLink>
            <RouterLink
              :to="`/contests/${contest.slug}/announcements`"
              class="flex h-10 w-10 items-center justify-center rounded-lg border border-input-border text-muted hover:text-text hover:border-primary"
              title="查看公告"
            >
              <span class="material-symbols-outlined text-lg">campaign</span>
            </RouterLink>
          </div>
        </div>
      </div>

      <div v-if="filteredContests.length" class="flex items-center justify-between border-t border-border-panel/80 pt-4">
        <div class="text-sm text-muted">
          第 {{ pageMeta.page }} / {{ pageMeta.total_pages || Math.max(1, Math.ceil((pageMeta.total || 0) / pageMeta.page_size)) }} 页，
          共 {{ pageMeta.total || 0 }} 场比赛
        </div>
        <div class="flex items-center gap-2">
          <button
            class="inline-flex h-9 items-center justify-center rounded-lg border border-input-border px-3 text-sm font-semibold text-text disabled:opacity-50 disabled:cursor-not-allowed hover:border-primary hover:text-primary"
            :disabled="!pageMeta.has_previous"
            @click="goPage(pageMeta.previous_page || pageMeta.page - 1)"
          >
            上一页
          </button>
          <button
            class="inline-flex h-9 items-center justify-center rounded-lg border border-input-border px-3 text-sm font-semibold text-text disabled:opacity-50 disabled:cursor-not-allowed hover:border-primary hover:text-primary"
            :disabled="!pageMeta.has_next"
            @click="goPage(pageMeta.next_page || pageMeta.page + 1)"
          >
            下一页
          </button>
        </div>
      </div>
    </div>
  </AppShell>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { RouterLink } from 'vue-router'
import AppShell from '@/components/AppShell.vue'
import api from '@/api/client'
import { SkeletonBlock, EmptyState, ErrorState } from '@/components/ui'
import { formatDateTime } from '@/utils/format'
import { parseApiError } from '@/api/errors'
import { DEFAULT_PAGE_META, CONTEST_STATUS } from '@/constants/enums'
import { useToastStore } from '@/stores/toast'

const statusTabs = [
  { value: 'all', label: '全部' },
  { value: CONTEST_STATUS.RUNNING, label: '进行中' },
  { value: CONTEST_STATUS.UPCOMING, label: '未开始' },
  { value: CONTEST_STATUS.ENDED, label: '已结束' },
]

const contests = ref([])
const loading = ref(false)
const error = ref('')
const keyword = ref('')
const status = ref(CONTEST_STATUS.RUNNING)
const pageMeta = reactive({ ...DEFAULT_PAGE_META, total_pages: 1 })
const toast = useToastStore()

const filteredContests = computed(() => {
  if (!keyword.value) return contests.value
  const q = keyword.value.toLowerCase()
  return contests.value.filter((c) => (c.name || '').toLowerCase().includes(q) || (c.description || '').toLowerCase().includes(q))
})

const normalizeStatus = (s) => {
  const val = String(s || '').toLowerCase()
  if (val.includes('run') || val.includes('进行')) return CONTEST_STATUS.RUNNING
  if (val.includes('upcoming') || val.includes('未') || val.includes('not')) return CONTEST_STATUS.UPCOMING
  if (
    val.includes('end') ||
    val.includes('finish') ||
    val.includes('closed') ||
    val.includes('done') ||
    val.includes('完') ||
    val.includes('终') ||
    val.includes('结束')
  )
    return CONTEST_STATUS.ENDED
  return ''
}

const statusLabel = (s) => {
  const normalized = normalizeStatus(s)
  if (normalized === CONTEST_STATUS.RUNNING) return '进行中'
  if (normalized === CONTEST_STATUS.UPCOMING) return '未开始'
  if (normalized === CONTEST_STATUS.ENDED) return '已结束'
  return s || '未知'
}

const statusClass = (s) => {
  const normalized = normalizeStatus(s)
  if (normalized === CONTEST_STATUS.RUNNING) return 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/40'
  if (normalized === CONTEST_STATUS.UPCOMING) return 'bg-border-panel text-text border border-input-border'
  if (normalized === CONTEST_STATUS.ENDED) return 'bg-danger/15 text-danger border border-danger/40'
  return 'bg-border-panel text-muted'
}

const ctaLabel = (s) => {
  const normalized = normalizeStatus(s)
  if (normalized === CONTEST_STATUS.RUNNING) return '进入比赛'
  if (normalized === CONTEST_STATUS.UPCOMING) return '查看比赛'
  return '查看比赛'
}

const toDate = (val) => {
  if (!val) return null
  const d = new Date(val)
  return Number.isNaN(d.getTime()) ? null : d
}

const isRegistered = (contest) => {
  const val =
    contest?.registration_status ||
    contest?.registered ||
    contest?.is_registered ||
    contest?.has_registered ||
    contest?.enrolled ||
    contest?.joined
  if (typeof val === 'boolean') return val
  const str = String(val || '').toLowerCase()
  if (['1', 'true', 'yes', 'y'].includes(str)) return true
  if (str.includes('registered') || str.includes('enrolled') || str.includes('报名') || str.includes('已')) return true
  return false
}

const hasTeam = (contest) => {
  return !!(contest?.my_team || contest?.team || contest?.team_id || contest?.team_joined || contest?.current_team)
}

const isFrozen = (contest) => {
  const freeze = toDate(contest?.freeze_time)
  const end = toDate(contest?.end_time)
  if (!freeze) return false
  const now = Date.now()
  const freezeReached = now >= freeze.getTime()
  const notEnded = end ? now <= end.getTime() : true
  return freezeReached && notEnded
}

const isFinished = (contest) => {
  return normalizeStatus(contest?.status) === CONTEST_STATUS.ENDED && isRegistered(contest)
}

const badgeClass = (text) => {
  if (text.startsWith('已')) return 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/40'
  if (text.startsWith('未') || text.includes('无效') || text.includes('截止')) return 'bg-danger/15 text-danger border border-danger/40'
  return 'bg-border-panel text-muted border border-input-border/60'
}

const badgeLabelFromCode = (code) => {
  switch (code) {
    case 'registration_closed':
      return '报名截止'
    case 'registration_invalid':
      return '报名无效'
    case 'team_missing':
      return '未组队'
    case 'frozen':
      return '已封榜'
    case 'finished':
      return '已完赛'
    case 'registered':
      return '已报名'
    default:
      return ''
  }
}

const contestBadgeLabel = (contest) => {
  const label = badgeLabelFromCode(contest?.user_badge) || ''
  // “已封榜”仅在已报名/加入时展示
  if (label === '已封榜' && !isRegistered(contest)) return ''
  return label
}


const fetchContests = async () => {
  loading.value = true
  error.value = ''
  try {
    const params = {
      page: pageMeta.page,
      page_size: pageMeta.page_size,
    }
    if (status.value !== 'all') {
      params.status = status.value
    }
    const res = await api.get('/contests/', { params })
    const data = res?.data?.data || res?.data || {}
    contests.value = data.items || []
    Object.assign(pageMeta, { ...DEFAULT_PAGE_META, ...res?.data?.extra })
  } catch (err) {
    const msg = parseApiError(err)
    error.value = msg
    toast.error(msg)
  } finally {
    loading.value = false
  }
}

const changeStatus = (val) => {
  status.value = val
  pageMeta.page = 1
  fetchContests()
}

const goPage = (page) => {
  pageMeta.page = Math.max(1, page)
  fetchContests()
}

const resetFilters = () => {
  status.value = CONTEST_STATUS.RUNNING
  keyword.value = ''
  pageMeta.page = 1
  fetchContests()
}

const applySearch = () => {
  // 仅前端过滤当前页数据；如需后端搜索，可在接口支持后添加 params.keyword
  if (!contests.value.length) return
  // 不重新请求，保持当前数据
}

onMounted(() => {
  fetchContests()
})
</script>

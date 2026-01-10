<template>
  <div class="dark">
    <div class="relative min-h-screen bg-background-dark text-text">
      <div class="absolute inset-0">
        <div class="absolute inset-0 bg-background-dark"></div>
        <div class="absolute inset-0 bg-[radial-gradient(circle_at_center,_rgba(42,50,113,0.35),_transparent_45%)]"></div>
      </div>

      <PublicNav />

      <main class="relative z-10 max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-14">
        <!-- Hero -->
        <section class="rounded-xl border border-border-panel bg-panel shadow-panel overflow-hidden">
          <div class="relative isolate px-6 py-12 sm:px-10 sm:py-14">
            <div class="absolute inset-0 bg-[radial-gradient(circle_at_20%_20%,rgba(37,71,244,0.18),transparent_35%),radial-gradient(circle_at_80%_10%,rgba(37,71,244,0.12),transparent_40%)]"></div>
            <div class="relative flex flex-col gap-4 sm:gap-6">
              <p class="text-sm font-semibold text-primary">{{ brandName }}</p>
              <h1 class="text-4xl sm:text-5xl font-bold leading-tight tracking-tight">专注网络安全的 CTF 平台</h1>
              <p class="max-w-2xl text-base text-muted sm:text-lg">
                参与比赛、刷题训练、查看公告与排期。
              </p>
              <div class="flex flex-wrap gap-3">
                <router-link
                  to="/contests"
                  class="flex h-12 min-w-[120px] cursor-pointer items-center justify-center rounded-lg bg-primary px-5 text-base font-bold text-primary-foreground hover:bg-primary/90"
                >
                  查看比赛
                </router-link>
                <router-link
                  to="/problems"
                  class="flex h-12 min-w-[120px] cursor-pointer items-center justify-center rounded-lg bg-border-panel px-5 text-base font-bold text-text hover:bg-input-border"
                >
                  进入题库
                </router-link>
              </div>
            </div>
          </div>
        </section>

        <!-- Announcements without images -->
        <section class="space-y-6">
          <div class="flex items-center justify-between">
            <h2 class="text-2xl sm:text-3xl font-bold tracking-tight">公告</h2>
            <router-link class="text-sm text-primary hover:underline" to="/announcements">
              更多
            </router-link>
          </div>
          <div v-if="announcementsLoading" class="space-y-3">
            <SkeletonBlock :count="3" height="16px" />
          </div>
          <ErrorState v-else-if="announcementError" :message="announcementError" retry-label="重试" @retry="fetchAnnouncements(activeContestSlug)" />
          <EmptyState v-else-if="!announcements.length" title="暂无公告" />
          <div v-else class="grid grid-cols-1 gap-4 sm:gap-6">
            <router-link
              v-for="(item, idx) in announcements"
              :key="idx"
              class="rounded-xl border border-border-panel bg-panel/80 p-4 sm:p-5 shadow-panel block hover:border-primary/40 hover:-translate-y-0.5 transition-transform"
              :to="item.to || '/announcements'"
            >
              <div class="flex items-start gap-3">
                <div class="flex h-10 w-10 items-center justify-center rounded-full bg-primary/15 text-primary">
                  <span class="material-symbols-outlined">campaign</span>
                </div>
                <div class="flex-1 space-y-2">
                  <div class="flex flex-wrap items-center gap-2 justify-between">
                    <p class="text-lg font-bold">{{ item.title }}</p>
                    <span class="text-xs text-muted">{{ item.time }}</span>
                  </div>
                  <p class="text-sm text-muted leading-relaxed">{{ item.summary }}</p>
                </div>
              </div>
            </router-link>
          </div>
        </section>

        <!-- Competitions -->
        <section class="space-y-6">
          <h2 class="text-2xl sm:text-3xl font-bold tracking-tight">比赛</h2>
          <div v-if="contestsLoading" class="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
            <div v-for="i in 3" :key="i" class="flex flex-col rounded-xl border border-border-panel bg-panel/70 p-5 shadow-panel space-y-3">
              <SkeletonBlock :count="4" height="16px" />
            </div>
          </div>
          <ErrorState v-else-if="contestError" :message="contestError" retry-label="重试" @retry="refetchContests" />
          <EmptyState v-else-if="!contests.length" title="暂无可展示的比赛" />
          <div v-else class="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
            <div
              v-for="(contest, idx) in contests"
              :key="idx"
              class="flex flex-col rounded-xl border border-border-panel bg-panel/90 p-5 shadow-panel"
            >
              <div class="mb-3 flex items-center justify-between">
                <h3 class="text-lg font-bold">{{ contest.name }}</h3>
                <span
                  class="inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold"
                  :class="statusClass(contest.status)"
                >
                  {{ contest.statusLabel }}
                </span>
                <span
                  v-if="contest.badge"
                  class="inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold"
                  :class="badgeClass(contest.badge)"
                >
                  {{ contest.badge }}
                </span>
              </div>
              <p class="mb-4 text-sm text-muted leading-relaxed line-clamp-3">{{ contest.description }}</p>
              <div class="mb-4 text-xs text-muted space-y-1">
                <p><strong>开始:</strong> {{ contest.start }}</p>
                <p><strong>结束:</strong> {{ contest.end }}</p>
              </div>
              <div class="mt-auto">
                <router-link
                  v-if="contest.slug"
                  class="flex h-10 w-full cursor-pointer items-center justify-center overflow-hidden rounded-lg"
                  :class="contest.primary ? 'bg-primary text-primary-foreground hover:bg-primary/90' : 'bg-border-panel text-text hover:bg-input-border'"
                  :to="`/contests/${contest.slug}`"
                >
                  {{ contest.action }}
                </router-link>
                <button
                  v-else
                  class="flex h-10 w-full cursor-pointer items-center justify-center overflow-hidden rounded-lg bg-border-panel text-text"
                  type="button"
                >
                  {{ contest.action }}
                </button>
              </div>
            </div>
          </div>
        </section>
      </main>

      <footer class="relative z-10 flex justify-center border-t border-border-panel px-4 py-6 sm:px-6 lg:px-8">
        <div class="flex w-full max-w-6xl flex-col items-center justify-between gap-4 text-center sm:flex-row sm:text-left">
          <p class="text-sm text-muted">© 2025 {{ brandName }}</p>
          <div class="flex gap-4 text-sm text-muted">
            <a class="hover:text-text" href="#">隐私政策</a>
            <a class="hover:text-text" href="#">服务条款</a>
            <a class="hover:text-text" href="#">联系我们</a>
          </div>
        </div>
      </footer>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, onMounted } from 'vue'
import api from '@/api/client'
import { useConfigStore } from '@/stores/config'
import { formatDateTime } from '@/utils/format'
import { EmptyState, ErrorState, SkeletonBlock } from '@/components/ui'
import PublicNav from '@/components/PublicNav.vue'

const configStore = useConfigStore()
const brandName = computed(() => configStore.brand || 'Find The Cat')

const announcements = ref([])
const announcementsLoading = ref(false)
const announcementError = ref('')
const contests = ref([])
const contestsLoading = ref(false)
const contestError = ref('')
const activeContestSlug = ref('')

const statusClass = (status) => {
  const normalized = normalizeStatus(status)
  if (normalized === 'running') return 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/40'
  if (normalized === 'upcoming') return 'bg-border-panel text-text border border-input-border'
  if (normalized === 'ended') return 'bg-danger/15 text-danger border border-danger/40'
  return 'bg-border-panel text-muted'
}

const badgeClass = (text) => {
  if (text.startsWith('已')) return 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/40'
  if (text.startsWith('未') || text.includes('无效') || text.includes('截止')) return 'bg-danger/15 text-danger border border-danger/40'
  return 'bg-border-panel text-muted border border-input-border/60'
}

const statusLabel = (status) => {
  const normalized = normalizeStatus(status)
  if (normalized === 'running') return '进行中'
  if (normalized === 'upcoming') return '未开始'
  if (normalized === 'ended') return '已结束'
  return '未知状态'
}

const normalizeStatus = (value) => {
  const raw = (value || '').toString().toLowerCase()
  if (!raw) return 'unknown'
  if (raw.includes('run') || raw.includes('进行')) return 'running'
  if (raw.includes('upcoming') || raw.includes('未') || raw.includes('not')) return 'upcoming'
  if (
    raw.includes('end') ||
    raw.includes('finish') ||
    raw.includes('closed') ||
    raw.includes('done') ||
    raw.includes('完') ||
    raw.includes('终') ||
    raw.includes('结束')
  )
    return 'ended'
  return raw
}

const mapContest = (item) => {
  const normalized = normalizeStatus(item?.status)
  const badge = badgeLabelFromCode(item?.user_badge)
  return {
    slug: item?.slug || '',
    name: item?.name || '未命名比赛',
    description: item?.description || '暂无描述',
    start: formatDateTime(item?.start_time) || '待定',
    end: formatDateTime(item?.end_time) || '待定',
    status: normalized,
    statusLabel: statusLabel(normalized),
    badge,
    primary: normalized === 'running',
    action: normalized === 'running' ? '进入比赛' : normalized === 'upcoming' ? '查看详情' : '查看榜单',
  }
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


const mapAnnouncement = (item) => {
  const time = item?.created_at || item?.updated_at
  const summary = item?.summary || item?.content || ''
  const contest = item?.contest || contests.value?.[0]?.slug || ''
  return {
    id: item?.id || `announcement-${Date.now()}`,
    title: item?.title || '未命名公告',
    summary: summary.length > 120 ? `${summary.slice(0, 120)}...` : summary,
    time: formatDateTime(time) || '刚刚',
    to: contest && item?.id ? `/contests/${contest}/announcements/${item.id}` : '/announcements',
  }
}

const fetchContests = async () => {
  contestsLoading.value = true
  contestError.value = ''
  try {
    const res = await api.get('/contests/', { params: { page_size: 6 } })
    const items = res.data?.data?.items || res.data?.items || []
    contests.value = items.map(mapContest)
    activeContestSlug.value = contests.value[0]?.slug || ''
  } catch (e) {
    contestError.value = e?.response?.data?.message || '加载比赛列表失败'
    contests.value = []
  } finally {
    contestsLoading.value = false
  }
  return contests.value[0]?.slug || ''
}

const fetchAnnouncements = async (contestSlug = '') => {
  announcementsLoading.value = true
  announcementError.value = ''
  announcements.value = []
  if (!contestSlug) {
    announcementsLoading.value = false
    return
  }
  try {
    const res = await api.get(`/contests/${contestSlug}/announcements/`, { params: { page_size: 5 } })
    const items = res.data?.data?.items || res.data?.items || []
    announcements.value = items.map(mapAnnouncement)
  } catch (e) {
    announcementError.value = e?.response?.data?.message || '加载公告失败'
  } finally {
    announcementsLoading.value = false
  }
}

const refetchContests = () => fetchContests().then((slug) => fetchAnnouncements(slug))

onMounted(() => {
  // 拉取比赛与公告
  refetchContests()
})
</script>

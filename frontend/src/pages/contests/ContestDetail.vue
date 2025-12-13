<template>
  <AppShell>
    <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      <div v-if="loading" class="space-y-3">
        <SkeletonBlock :count="4" height="20px" />
      </div>
      <ErrorState v-else-if="error" :message="error" retry-label="重试" @retry="loadDetail" />
      <template v-else>
        <header class="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div class="space-y-2">
            <p class="text-xs uppercase tracking-[0.08em] text-primary">比赛详情</p>
            <h1 class="text-3xl font-bold leading-tight tracking-tight">{{ contest?.name || contestSlug }}</h1>
            <p class="text-sm text-muted leading-relaxed max-w-3xl">{{ contest?.description }}</p>
            <div class="flex flex-wrap gap-3 text-xs text-muted">
              <span v-if="registrationStart">报名开始：{{ formatDateTime(registrationStart) }}</span>
              <span v-if="registrationEnd">报名截止：{{ formatDateTime(registrationEnd) }}</span>
              <span>比赛开始：{{ formatDateTime(contest?.start_time) }}</span>
              <span>比赛结束：{{ formatDateTime(contest?.end_time) }}</span>
              <span v-if="contest?.freeze_time">封榜：{{ formatDateTime(contest?.freeze_time) }}</span>
              <span>赛制：{{ contest?.is_team_based ? `组队赛（最多 ${contest?.max_team_members || 'N/A'} 人）` : '个人赛' }}</span>
            </div>
          </div>
          <div class="flex flex-col gap-2 w-full max-w-xs">
            <div class="inline-flex items-center gap-2 self-end">
              <span class="inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold" :class="statusClass(contest?.status)">
                {{ statusLabel(contest?.status) }}
              </span>
              <span
                v-if="userBadgeLabel"
                class="inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold"
                :class="badgeClass(userBadgeLabel)"
              >
                {{ userBadgeLabel }}
              </span>
            </div>
            <button
              class="h-11 w-full rounded-lg text-sm font-semibold text-primary-foreground hover:opacity-90 disabled:opacity-60"
              :class="primaryBtnClass"
              type="button"
              :disabled="primaryDisabled || registering"
              @click="handlePrimary"
            >
              {{ primaryLabel }}
            </button>
            <button
              v-if="showSecondary"
              class="h-10 w-full rounded-lg text-sm font-semibold hover:opacity-90 disabled:opacity-60"
              :class="secondaryBtnClass"
              type="button"
              :disabled="secondaryDisabled || registering"
              @click="handleSecondary"
            >
              {{ secondaryLabel }}
            </button>
          </div>
        </header>

        <div class="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <section class="lg:col-span-2 space-y-4">
            <div class="rounded-xl border border-border-panel bg-panel/90 p-5 shadow-panel space-y-2">
              <div class="flex items-center justify-between">
                <h2 class="text-lg font-bold">公告</h2>
                <RouterLink
                  :to="`/contests/${contestSlug}/announcements`"
                  class="text-sm text-primary hover:underline"
                >
                  查看全部
                </RouterLink>
              </div>
              <template v-if="announcements && announcements.length">
                <div class="divide-y divide-border-panel/80">
                  <article v-for="item in announcements.slice(0, 3)" :key="item.id" class="py-3">
                    <div class="flex items-start gap-2">
                      <div class="h-8 w-8 rounded-full bg-primary/15 text-primary flex items-center justify-center">
                        <span class="material-symbols-outlined text-sm">campaign</span>
                      </div>
                      <div class="flex-1 min-w-0">
                        <RouterLink
                          :to="`/contests/${contestSlug}/announcements/${item.id}`"
                          class="text-base font-semibold hover:text-primary line-clamp-2"
                        >
                          {{ item.title }}
                        </RouterLink>
                        <p class="text-xs text-muted mt-1">{{ formatDateTime(item.created_at) }}</p>
                        <p class="text-sm text-muted leading-relaxed line-clamp-2 mt-1">{{ item.summary || item.content }}</p>
                      </div>
                    </div>
                  </article>
                </div>
              </template>
              <EmptyState v-else title="暂无公告" />
            </div>

            <div class="rounded-xl border border-border-panel bg-panel/90 p-5 shadow-panel space-y-4">
              <div class="flex items-center justify-between">
                <h2 class="text-lg font-bold">题目概览</h2>
                <RouterLink
                  :to="`/contests/${contestSlug}/challenges`"
                  class="text-sm text-primary hover:underline"
                >
                  查看题目
                </RouterLink>
              </div>
              <EmptyState v-if="!challenges?.length" title="暂无题目" />
              <div v-else class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div
                  v-for="chal in challenges.slice(0, 4)"
                  :key="chal.slug"
                  class="rounded-lg border border-border-panel bg-input/60 p-3 space-y-2"
                >
                  <div class="flex items-center justify-between">
                    <p class="font-semibold line-clamp-1">{{ chal.title || chal.name }}</p>
                    <span class="text-xs text-muted">{{ chal.points || chal.score || '--' }} pts</span>
                  </div>
                  <p class="text-xs text-muted line-clamp-2">{{ chal.short_description || chal.description }}</p>
                </div>
              </div>
            </div>
          </section>

          <section class="space-y-4">
            <div class="rounded-xl border border-border-panel bg-panel/90 p-4 shadow-panel space-y-3">
              <h3 class="text-lg font-bold">我的队伍</h3>
              <template v-if="myTeam">
                <p class="text-sm font-semibold">{{ myTeam.name }}</p>
                <p class="text-xs text-muted">邀请码：{{ myTeam.invite_code || '——' }}</p>
                <p class="text-xs text-muted">成员数：{{ myTeam.members?.length || 0 }}</p>
              </template>
              <EmptyState v-else title="未加入队伍" description="如为组队赛，请前往战队页创建或加入队伍。" />
            </div>

            <div class="rounded-xl border border-border-panel bg-panel/90 p-4 shadow-panel space-y-3">
              <div class="flex items-center justify-between">
                <h3 class="text-lg font-bold">积分榜</h3>
                <button
                  class="text-sm text-primary hover:underline"
                  type="button"
                  @click="refreshDetail"
                >
                  刷新
                </button>
              </div>
              <div
                v-if="isRegistered && myStanding"
                class="rounded-lg border border-input-border bg-input/50 px-3 py-2 text-sm flex items-center justify-between"
              >
                <span class="flex items-center gap-2">
                  <span class="text-muted w-10">当前</span>
                  <span class="font-semibold">{{ myStanding.name }}</span>
                </span>
                <span class="flex items-center gap-3">
                  <span class="text-muted text-xs">#{{ myStanding.rank ?? '--' }}</span>
                  <span class="text-primary font-semibold">{{ myStanding.score ?? 0 }}</span>
                </span>
              </div>
              <EmptyState v-else-if="!scoreboard?.length" title="暂无数据" />
              <ul v-if="scoreboard?.length" class="space-y-2">
                <li
                  v-for="(row, idx) in scoreboard.slice(0, 10)"
                  :key="idx"
                  class="flex items-center justify-between rounded-lg bg-input/60 px-3 py-2 text-sm"
                >
                  <span class="flex items-center gap-2">
                    <span class="text-muted w-10">#{{ row.rank ?? idx + 1 }}</span>
                    <span class="font-semibold">{{ row.name || '选手' }}</span>
                  </span>
                  <span class="text-primary font-semibold">{{ row.score ?? 0 }}</span>
                </li>
              </ul>
            </div>
          </section>
        </div>
      </template>
    </div>
  </AppShell>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import AppShell from '@/components/AppShell.vue'
import api from '@/api/client'
import { SkeletonBlock, EmptyState, ErrorState } from '@/components/ui'
import { formatDateTime } from '@/utils/format'
import { parseApiError } from '@/api/errors'
import { CONTEST_STATUS } from '@/constants/enums'
import { useToastStore } from '@/stores/toast'
import { useContestChannel } from '@/composables/useContestChannel'

const route = useRoute()
const router = useRouter()
const toast = useToastStore()

const contestSlug = computed(() => route.params.contestSlug)
const contest = ref(null)
const announcements = ref([])
const challenges = ref([])
const scoreboard = ref([])
const myTeam = ref(null)
const myStanding = ref(null)
const loading = ref(false)
const error = ref('')
const registering = ref(false)

const toDate = (val) => {
  if (!val) return null
  const d = new Date(val)
  return Number.isNaN(d.getTime()) ? null : d
}

const normalizeStatus = (s) => {
  const val = String(s || '').toLowerCase()
  if (val.includes('run') || val.includes('ongoing') || val.includes('进行')) return CONTEST_STATUS.RUNNING
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
  return val
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

const badgeClass = (text) => {
  if (text.startsWith('已')) return 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/40'
  if (text.startsWith('未') || text.includes('无效') || text.includes('截止')) return 'bg-danger/15 text-danger border border-danger/40'
  return 'bg-border-panel text-muted border border-input-border/60'
}

const registrationStart = computed(() => {
  const c = contest.value || {}
  return (
    toDate(c.registration_start_time) ||
    toDate(c.registration_start_at) ||
    toDate(c.signup_start_time) ||
    toDate(c.enroll_start_time) ||
    null
  )
})

const registrationEnd = computed(() => {
  const c = contest.value || {}
  return (
    toDate(c.registration_end_time) ||
    toDate(c.registration_deadline) ||
    toDate(c.registration_close_time) ||
    toDate(c.signup_end_time) ||
    toDate(c.enroll_end_time) ||
    null
  )
})

const registrationNotStarted = computed(() => {
  const start = registrationStart.value
  return start ? Date.now() < start.getTime() : false
})

const registrationClosed = computed(() => {
  const end = registrationEnd.value
  return end ? Date.now() > end.getTime() : false
})

const registrationOpen = computed(() => !registrationNotStarted.value && !registrationClosed.value)

const isRegistered = computed(() => {
  const val =
    contest.value?.registration_status ||
    contest.value?.registered ||
    contest.value?.is_registered ||
    contest.value?.has_registered ||
    contest.value?.enrolled ||
    contest.value?.joined
  if (typeof val === 'boolean') return val
  const str = String(val || '').toLowerCase()
  if (['1', 'true', 'yes', 'y'].includes(str)) return true
  if (str.includes('registered') || str.includes('enrolled') || str.includes('报名') || str.includes('已')) return true
  // 组队赛已加入队伍视为已报名
  if (contest.value?.is_team_based && myTeam.value) return true
  return false
})

const contestState = computed(() => normalizeStatus(contest.value?.status))

const primaryLabel = computed(() => {
  const state = contestState.value
  const badge = contest.value?.user_badge
  if (badge === 'registration_closed') return '报名已截止'
  if (badge === 'registration_invalid') return '报名无效'

  if (state === CONTEST_STATUS.UPCOMING) {
    if (!registrationOpen.value) return '报名未开启'
    return isRegistered.value ? '查看信息' : '报名参赛'
  }
  if (state === CONTEST_STATUS.RUNNING) {
    if (!isRegistered.value) return '无法报名'
    return '进入比赛'
  }
  if (state === CONTEST_STATUS.ENDED) {
    return isRegistered.value ? '查看信息' : '比赛已结束'
  }
  return '查看信息'
})

const primaryDisabled = computed(() => {
  const state = contestState.value
  const badge = contest.value?.user_badge
  if (badge === 'registration_closed' || badge === 'registration_invalid') return true
  if (state === CONTEST_STATUS.RUNNING && !isRegistered.value) return true
  if (state === CONTEST_STATUS.ENDED && !isRegistered.value) return true
  if (state === CONTEST_STATUS.UPCOMING && !registrationOpen.value && !isRegistered.value) return true
  return false
})

const primaryBtnClass = computed(() => {
  return 'bg-primary'
})

const secondaryLabel = computed(() => {
  const state = contestState.value
  const hasTeam = !!myTeam.value
  if (!contest.value?.is_team_based) return ''
  if (contest.value?.user_badge === 'registration_invalid') return '报名无效'
  if (!hasTeam && state === CONTEST_STATUS.UPCOMING) return '创建/加入队伍'
  if (!hasTeam && state === CONTEST_STATUS.RUNNING) return '未组队'
  if (hasTeam) return '已组队'
  return ''
})

const secondaryDisabled = computed(() => {
  const state = contestState.value
  const hasTeam = !!myTeam.value
  if (!contest.value?.is_team_based) return true
  if (contest.value?.user_badge === 'registration_invalid') return true
  if (!hasTeam && state === CONTEST_STATUS.UPCOMING) return false
  if (!hasTeam && state === CONTEST_STATUS.RUNNING) return true
  return true
})

const secondaryBtnClass = computed(() => {
  return secondaryDisabled.value
    ? 'bg-input-border text-text/70 cursor-not-allowed'
    : 'bg-input-border text-text hover:bg-input'
})

const showSecondary = computed(() => {
  return !!contest.value?.is_team_based && !!secondaryLabel.value
})

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

const userBadgeLabel = computed(() => badgeLabelFromCode(contest.value?.user_badge))

const loadDetail = async () => {
  loading.value = true
  error.value = ''
  try {
    const res = await api.get(`/contests/${contestSlug.value}/`)
    const data = res?.data?.data || res?.data || {}
    contest.value = data.contest || data
    announcements.value = data.announcements || []
    challenges.value = data.challenges || []
    const rows = Array.isArray(data.scoreboard) ? data.scoreboard : []
    scoreboard.value = rows.map((row, idx) => ({
      name: row.name || row.team || row.user || '选手',
      score: row.score ?? row.points ?? row.total ?? 0,
      rank: row.rank ?? row.position ?? row.place ?? row.order ?? idx + 1,
      team_id: row.team_id || row.teamId || row.id || null,
      user_id: row.user_id || row.userId || null,
      is_me: row.is_me || row.is_self || false,
    }))
    myTeam.value = data.my_team || null
    // 当前积分/排名：优先后端显式字段，再回落榜单匹配
    const explicitMy = data.my_scoreboard || data.my_score || data.my_rank
    if (isRegistered.value) {
      if (explicitMy) {
        myStanding.value = {
          name:
            explicitMy.name ||
            explicitMy.team ||
            explicitMy.user ||
            myTeam.value?.name ||
            '我',
          score: explicitMy.score ?? explicitMy.points ?? explicitMy.total ?? 0,
          rank: explicitMy.rank ?? explicitMy.position ?? explicitMy.place ?? explicitMy.order ?? '--',
        }
      } else {
        const match = scoreboard.value.find((row) => {
          if (row.is_me) return true
          if (myTeam.value?.id && row.team_id && row.team_id === myTeam.value.id) return true
          if (myTeam.value?.name && row.name && row.name === myTeam.value.name) return true
          return false
        })
        if (match) {
          myStanding.value = { name: match.name, score: match.score, rank: match.rank }
        } else {
          myStanding.value = null
        }
      }
    } else {
      myStanding.value = null
    }
  } catch (err) {
    const status = err?.response?.status
    const msg = parseApiError(err)
    error.value = msg
    if (status === 401) {
      toast.error('请先登录后查看比赛详情')
    } else if (status === 403) {
      toast.error(msg || '暂无权限查看该比赛')
    } else {
      toast.error(msg)
    }
  } finally {
    loading.value = false
  }
}

const refreshDetail = () => {
  loadDetail()
}

const registerContest = async () => {
  registering.value = true
  try {
    await api.post(`/contests/${contestSlug.value}/register/`, {})
    toast.success('报名成功')
    loadDetail()
  } catch (err) {
    toast.error(parseApiError(err))
  } finally {
    registering.value = false
  }
}

const enterContest = () => {
  router.push(`/contests/${contestSlug.value}/challenges`)
}

const handlePrimary = () => {
  const state = contestState.value
  if (!isRegistered.value && !registrationOpen.value) {
    toast.error('当前不在报名时间')
    return
  }
  if (state === CONTEST_STATUS.RUNNING && isRegistered.value) {
    enterContest()
    return
  }
  if (!isRegistered.value && registrationOpen.value && state !== CONTEST_STATUS.ENDED) {
    registerContest()
    return
  }
  if (state === CONTEST_STATUS.ENDED && isRegistered.value) {
    router.push(`/contests/${contestSlug.value}`)
    return
  }
  // 未报名且已开始/结束，按钮已禁用，不应触发
  if (!primaryDisabled.value && !isRegistered.value) {
    registerContest()
  }
}

const handleSecondary = () => {
  if (secondaryDisabled.value) return
  router.push('/teams')
}

useContestChannel(contestSlug.value, {
  onMessage: (evt) => {
    const event = evt?.event
    if (
      [
        'scoreboard_updated',
        'announcement_published',
        'challenge_updated',
        'team_joined',
        'team_left',
        'team_disbanded',
        'team_transferred',
      ].includes(event)
    ) {
      refreshDetail()
    }
  },
})

onMounted(() => {
  loadDetail()
})
</script>

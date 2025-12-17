<template>
  <AppShell>
    <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <div class="space-y-1">
          <p class="text-xs uppercase tracking-[0.08em] text-primary">比赛题目</p>
          <h1 class="text-3xl font-bold leading-tight tracking-tight">{{ contestTitle }}</h1>
          <p class="text-sm text-muted">按分类浏览题目，提交 flag 或解锁提示。</p>
        </div>
        <RouterLink
          :to="`/contests/${contestSlug}/`"
          class="inline-flex h-10 items-center justify-center rounded-lg border border-input-border px-4 text-sm font-semibold text-text hover:border-primary hover:text-primary"
        >
          返回比赛
        </RouterLink>
      </div>

      <div class="flex flex-wrap gap-3">
        <button
          v-for="cat in categories"
          :key="cat.id || cat.slug || cat.name"
          class="inline-flex items-center gap-2 rounded-full border border-input-border px-4 py-2 text-sm font-semibold text-text hover:border-primary hover:text-primary"
          :class="activeCategory === (cat.slug || cat.id) ? 'bg-primary/15 border-primary text-primary' : ''"
          @click="selectCategory(cat.slug || cat.id)"
        >
          {{ cat.name }}
        </button>
      </div>

      <div v-if="loading" class="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
        <div v-for="i in 6" :key="i" class="flex flex-col rounded-xl border border-border-panel bg-panel/90 p-5 shadow-panel space-y-3">
          <SkeletonBlock :count="4" height="16px" />
        </div>
      </div>
      <ErrorState v-else-if="error" :message="error" retry-label="重试" @retry="loadChallenges" />
      <EmptyState v-else-if="!filteredChallenges.length" title="暂无题目" />

      <div v-else class="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
        <div
          v-for="chal in filteredChallenges"
          :key="chal.slug"
          class="flex flex-col rounded-xl border border-border-panel bg-panel/90 p-5 shadow-panel space-y-3"
        >
          <div class="flex items-start justify-between gap-3">
            <div class="flex-1 min-w-0">
              <p class="text-lg font-bold leading-tight line-clamp-1">{{ chal.title || chal.name }}</p>
              <p class="text-xs text-muted mt-1 line-clamp-2">{{ chal.short_description || chal.description }}</p>
              <div class="text-xs text-muted space-y-1 mt-3">
                <p v-if="chal.category">分类：{{ chal.category }}</p>
                <p v-if="chal.tags?.length">标签：{{ chal.tags.join(' / ') }}</p>
              </div>
            </div>
            <div class="flex flex-col items-end gap-2 w-24 text-right">
              <div class="flex flex-col items-end">
                <span class="text-sm font-semibold text-primary">{{ displayPoints(chal) }} pts</span>
                <span class="text-xs text-muted">{{ chal.solved ? '已解' : '未解' }}</span>
              </div>
              <button
                class="inline-flex h-9 w-full items-center justify-center rounded-lg border border-input-border px-3 text-sm font-semibold text-text hover:border-primary hover:text-primary"
                type="button"
                @click="openModal(chal)"
              >
                查看详情
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 pb-10">
      <div class="flex flex-wrap items-center justify-between border-t border-border-panel/80 pt-4 mt-6 text-sm text-muted">
        <span>第 1 / 1 页</span>
        <div class="flex items-center gap-2">
          <button
            class="inline-flex h-9 items-center justify-center rounded-lg border border-input-border px-3 font-semibold text-text opacity-70 cursor-not-allowed"
            type="button"
            disabled
          >
            上一页
          </button>
          <button
            class="inline-flex h-9 items-center justify-center rounded-lg border border-input-border px-3 font-semibold text-text opacity-70 cursor-not-allowed"
            type="button"
            disabled
          >
            下一页
          </button>
        </div>
      </div>
    </div>

    <Teleport to="body">
      <div
        v-if="showModal"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm px-4"
        @click.self="closeModal"
      >
        <div class="w-full max-w-3xl rounded-2xl border border-border-panel bg-panel/95 shadow-2xl p-6 space-y-4">
          <div class="flex items-start justify-between gap-3">
            <div>
              <p class="text-xs uppercase tracking-[0.08em] text-primary">题目详情</p>
              <h2 class="text-2xl font-bold leading-tight">{{ selectedChallenge?.title || selectedChallenge?.name }}</h2>
              <p class="text-sm text-muted mt-1">{{ selectedChallenge?.short_description || selectedChallenge?.description }}</p>
              <div class="mt-2 flex flex-wrap gap-3 text-sm text-text font-medium">
                <span v-if="selectedChallenge?.category">分类：{{ selectedChallenge.category }}</span>
                <span>分值：{{ displayPoints(selectedChallenge || {}) }} pts</span>
                <span v-if="selectedChallenge?.difficulty">难度：{{ selectedChallenge.difficulty }}</span>
                <span v-if="selectedChallenge?.has_machine">靶机：已配置</span>
              </div>
            </div>
            <button
              class="text-muted hover:text-text"
              type="button"
              @click="closeModal"
            >
              <span class="material-symbols-outlined text-xl">close</span>
            </button>
          </div>

          <div class="rounded-lg border border-border-panel bg-input/40 p-4 text-sm text-text leading-relaxed max-h-60 overflow-auto">
            <p v-if="detailLoading" class="text-muted">加载题面中…</p>
            {{ selectedChallenge?.content || '暂无题面' }}
          </div>

          <div class="rounded-lg border border-border-panel bg-input/40 p-4 text-sm space-y-2">
            <div class="flex items-center justify-between">
              <p class="font-semibold text-text">题目附件</p>
              <span class="text-xs text-muted">{{ attachments.length ? `${attachments.length} 个附件` : '暂无附件' }}</span>
            </div>
            <EmptyState v-if="!attachments.length" title="暂无附件" />
            <div v-else class="space-y-2">
              <a
                v-for="(att, idx) in attachments"
                :key="idx"
                class="flex items-center justify-between rounded-lg border border-input-border bg-input px-3 py-2 text-sm text-text hover:border-primary hover:text-primary"
                :href="att.url || att.download_url"
                target="_blank"
                rel="noreferrer"
              >
                <span class="truncate">{{ att.name || `附件 ${idx + 1}` }}</span>
                <span class="material-symbols-outlined text-base">download</span>
              </a>
            </div>
          </div>

          <div class="rounded-lg border border-border-panel bg-input/40 p-4 text-sm space-y-2">
            <div class="flex items-center justify-between">
              <p class="font-semibold text-text">提示</p>
              <span class="text-xs text-muted">{{ hints.length ? `${hints.length} 个提示` : '暂无提示' }}</span>
            </div>
            <p v-if="hintsLoading" class="text-muted text-xs">加载提示中…</p>
            <EmptyState v-else-if="!hints.length" title="暂无提示" />
            <div v-else class="space-y-2">
              <div
                v-for="(hint, idx) in hints"
                :key="idx"
                class="rounded-lg border border-input-border bg-input/60 p-3 text-sm text-text space-y-2"
              >
                <div class="flex items-center justify-between gap-2">
                  <p class="font-semibold">{{ hint.title || `提示 ${idx + 1}` }}</p>
                  <span
                    class="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold"
                    :class="hint.is_free ? 'bg-green-500/10 text-green-300' : 'bg-danger/10 text-danger border border-danger/40'"
                  >
                    {{ hint.is_free ? '免费' : `扣 ${hint.cost || 0} 分` }}
                  </span>
                </div>
                <p class="text-muted whitespace-pre-wrap" v-if="hint.unlocked">{{ hint.content || '暂无内容' }}</p>
                <div class="flex items-center justify-between" v-else>
                  <p class="text-xs text-muted">
                    {{ hint.is_free ? '未解锁，点击后免费解锁。' : `未解锁，解锁将扣 ${hint.cost || 0} 分。` }}
                  </p>
                  <button
                    class="inline-flex items-center rounded-lg border border-input-border px-3 py-1 text-xs font-semibold text-text hover:border-primary hover:text-primary disabled:opacity-60"
                    type="button"
                    :disabled="unlocking[hint.id]"
                    @click="unlockHint(hint)"
                  >
                    {{ unlocking[hint.id] ? '解锁中…' : '解锁提示' }}
                  </button>
                </div>
              </div>
            </div>
          </div>

          <div class="flex flex-wrap items-center gap-3">
            <input
              v-model="flagInputs[selectedChallenge?.slug]"
              :placeholder="`flag{...}`"
              class="flex-1 h-11 rounded-lg border border-input-border bg-input px-3 text-sm text-text placeholder:text-muted focus:border-primary focus:ring-2 focus:ring-primary/40 outline-none"
              :disabled="submitting[selectedChallenge?.slug]"
              @keyup.enter="submitFlag(selectedChallenge?.slug)"
            />
            <button
              class="h-11 w-24 rounded-lg bg-primary text-primary-foreground text-sm font-semibold hover:bg-primary/90 disabled:opacity-60"
              :disabled="submitting[selectedChallenge?.slug]"
              @click="submitFlag(selectedChallenge?.slug)"
            >
              提交
            </button>
            <div v-if="selectedChallenge?.has_machine" class="flex flex-wrap items-center gap-2">
              <button
                class="h-11 w-28 rounded-lg border text-sm font-semibold hover:bg-primary/10 disabled:opacity-60"
                :class="machineRunning ? 'border-danger text-danger hover:bg-danger/10' : 'border-primary text-primary'"
                :disabled="machineLoading"
                type="button"
                @click="machineRunning ? stopMachine() : startMachine()"
              >
                {{ machineLoading ? (machineRunning ? '停止中…' : '启动中…') : machineRunning ? '停止' : '启动靶机' }}
              </button>
              <button
                v-if="machineRunning"
                class="h-11 w-24 rounded-lg border border-input-border text-sm font-semibold text-text hover:border-primary hover:text-primary disabled:opacity-60"
                :disabled="machineLoading || !canExtendNow"
                type="button"
                @click="extendMachine"
                :title="!canExtendNow ? '剩余时间尚多，未到可延时窗口' : ''"
              >
                {{ machineLoading ? '延时中…' : '延时' }}
              </button>
              <RouterLink
                :to="`/machines`"
                class="inline-flex h-11 items-center rounded-lg border border-input-border px-4 text-sm font-semibold text-text hover:border-primary hover:text-primary"
                @click="closeModal"
              >
                查看靶机
              </RouterLink>
            </div>
          </div>

          <div v-if="selectedChallenge?.has_machine" class="rounded-lg border border-input-border bg-input/40 p-4 text-sm space-y-3">
            <div class="grid grid-cols-1 gap-3 sm:grid-cols-[1.2fr_0.8fr] sm:items-center">
              <div class="space-y-2">
                <span class="font-semibold text-text block text-base">靶机状态</span>
                <p v-if="machineError" class="text-danger text-sm">{{ machineError }}</p>
                <p v-else-if="machineRunning" class="text-base text-text">
                  倒计时：{{ countdownDisplay || '计算中…' }}
                </p>
                <p v-else-if="machineInfo && machineInfo.status" class="text-base text-text">
                  当前状态：{{ machineInfo.status === 'running' ? '运行中' : machineInfo.status === 'stopped' ? '已停止' : machineInfo.status }}
                </p>
                <p v-else class="text-sm text-muted">{{ machineLoading ? '处理中…' : '尚未启动靶机' }}</p>
              </div>
              <div
                v-if="machineInfo?.host && machineInfo?.port"
                class="flex flex-col items-start sm:items-end gap-2 text-base text-text min-w-[200px]"
              >
                <a
                  class="text-primary hover:underline break-all"
                  :href="`http://${machineInfo.host}:${machineInfo.port}`"
                  target="_blank"
                  rel="noreferrer"
                >
                  http://{{ machineInfo.host }}:{{ machineInfo.port }}
                </a>
                <code class="text-muted">nc {{ machineInfo.host }} {{ machineInfo.port }}</code>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Teleport>
  </AppShell>
</template>

<script setup>
import { computed, onMounted, onBeforeUnmount, reactive, ref } from 'vue'
import { useRoute, RouterLink } from 'vue-router'
import AppShell from '@/components/AppShell.vue'
import api from '@/api/client'
import { SkeletonBlock, EmptyState, ErrorState } from '@/components/ui'
import { parseApiError } from '@/api/errors'
import { useToastStore } from '@/stores/toast'
import { useContestChannel } from '@/composables/useContestChannel'

const route = useRoute()
const toast = useToastStore()
const contestSlug = computed(() => route.params.contestSlug)

const contestTitle = ref('比赛题目')
const categories = ref([])
const challenges = ref([])
const activeCategory = ref(null)
const loading = ref(false)
const error = ref('')
const flagInputs = reactive({})
const submitting = reactive({})
const attachments = ref([])
const detailLoading = ref(false)
const hints = ref([])
const hintsLoading = ref(false)
const unlocking = reactive({})
const machineLoading = ref(false)
const machineError = ref('')
const machineInfo = ref(null)
const countdownSeconds = ref(null)
let countdownTimer = null

const filteredChallenges = computed(() => {
  return challenges.value.filter((c) => (c.category_slug || c.category) === activeCategory.value)
})

const machineRunning = computed(() => machineInfo.value?.status === 'running')

const displayPoints = (chal) => {
  if (chal.current_points) return chal.current_points
  if (chal.points) return chal.points
  if (chal.score) return chal.score
  if (chal.base_points) return chal.base_points
  return 0
}

const loadContestTitle = async () => {
  try {
    const res = await api.get(`/contests/${contestSlug.value}/`)
    contestTitle.value = res?.data?.data?.contest?.name || contestSlug.value || '比赛题目'
  } catch (err) {
    contestTitle.value = contestSlug.value || '比赛题目'
  }
}

const loadCategories = async () => {
  try {
    const res = await api.get(`/contests/${contestSlug.value}/categories/`)
    const data = res?.data?.data || res?.data || {}
    categories.value = data.items || data || []
    if (!activeCategory.value && categories.value.length) {
      activeCategory.value = categories.value[0].slug || categories.value[0].id
    }
  } catch (err) {
    const status = err?.response?.status
    if (status === 401) {
      toast.error('请先登录后再查看题目')
    } else if (status === 403) {
      toast.error(parseApiError(err, '暂无权限查看题目'))
    } else {
      toast.error(parseApiError(err))
    }
  }
}

const loadChallenges = async () => {
  loading.value = true
  error.value = ''
  try {
    const res = await api.get(`/contests/${contestSlug.value}/challenges/`)
    const data = res?.data?.data || res?.data || {}
    challenges.value = data.items || data || []
    // preload inputs
    challenges.value.forEach((c) => {
      if (!flagInputs[c.slug]) flagInputs[c.slug] = ''
    })
  } catch (err) {
    const status = err?.response?.status
    const msg = parseApiError(err)
    error.value = msg
    if (status === 401) {
      toast.error('请登录后查看题目')
    } else if (status === 403) {
      toast.error(msg || '暂无权限访问当前比赛题目')
    } else {
      toast.error(msg)
    }
  } finally {
    loading.value = false
  }
}

const selectCategory = (value) => {
  activeCategory.value = value
}

const submitFlag = async (slug) => {
  if (!flagInputs[slug]) {
    toast.error('请输入 flag')
    return
  }
  submitting[slug] = true
  try {
    await api.post(`/contests/${contestSlug.value}/submissions/`, {
      challenge_slug: slug,
      flag: flagInputs[slug],
    })
    toast.success('提交成功，等待判题')
    flagInputs[slug] = ''
    loadChallenges()
  } catch (err) {
    toast.error(parseApiError(err))
  } finally {
    submitting[slug] = false
  }
}

const selectedChallenge = ref(null)
const showModal = ref(false)
const modalForMachine = ref(false)

const openModal = (chal, forMachine = false) => {
  // 切换到新题目时重置靶机状态；同一题目则保留已知实例信息
  const isSameChallenge = selectedChallenge.value?.slug === chal.slug
  selectedChallenge.value = chal
  attachments.value = chal.attachments || []
  hints.value = chal.hints || []
  modalForMachine.value = !!forMachine
  flagInputs[chal.slug] = flagInputs[chal.slug] || ''
  if (!isSameChallenge) {
    machineInfo.value = null
    machineError.value = ''
    clearCountdown()
  }
  if (chal.has_machine) {
    fetchMachineForChallenge(chal)
  }
  showModal.value = true
  fetchChallengeDetail(chal.slug)
  fetchHints(chal.slug)
}

const closeModal = () => {
  showModal.value = false
  modalForMachine.value = false
  attachments.value = []
  hints.value = []
  machineLoading.value = false
  machineError.value = ''
  clearCountdown()
}

const fetchChallengeDetail = async (slug) => {
  detailLoading.value = true
  try {
    const res = await api.get(`/contests/${contestSlug.value}/challenges/${slug}/`)
    const data = res?.data?.data || res?.data || {}
    const detail = data.challenge || data
    selectedChallenge.value = { ...(selectedChallenge.value || {}), ...detail }
    attachments.value = detail.attachments || []
  } catch (err) {
    // 静默失败，保持已有数据
  } finally {
    detailLoading.value = false
  }
}

const fetchHints = async (slug) => {
  hintsLoading.value = true
  Object.keys(unlocking).forEach((k) => delete unlocking[k])
  try {
    const res = await api.get(`/contests/${contestSlug.value}/challenges/${slug}/hints/`)
    const list = res?.data?.data?.items || res?.data?.data || res?.data?.items || res?.data || []
    hints.value = Array.isArray(list) ? list : []
  } catch (err) {
    toast.error(parseApiError(err, '获取提示失败'))
  } finally {
    hintsLoading.value = false
  }
}

const unlockHint = async (hint) => {
  if (!hint?.id || hint?.unlocked) return
  unlocking[hint.id] = true
  try {
    const res = await api.post(
      `/contests/${contestSlug.value}/challenges/${selectedChallenge.value?.slug}/hints/${hint.id}/unlock/`,
      {},
    )
    const unlocked = res?.data?.data?.hint || res?.data?.hint || res?.data || {}
    hints.value = hints.value.map((h) => (h.id === hint.id ? { ...h, ...unlocked, unlocked: true } : h))
    const cost = Number(unlocked.cost ?? hint.cost ?? 0)
    const totalCost = Number(unlocked.total_cost ?? 0)
    if (selectedChallenge.value) {
      const base = selectedChallenge.value.base_points || displayPoints(selectedChallenge.value)
      const newPoints =
        unlocked.current_points !== undefined
          ? Number(unlocked.current_points)
          : Math.max(base - totalCost - cost, 0)
      selectedChallenge.value = { ...selectedChallenge.value, current_points: newPoints }
      challenges.value = challenges.value.map((c) =>
        c.slug === selectedChallenge.value.slug ? { ...c, current_points: newPoints } : c,
      )
    }
    toast.success('提示已解锁')
    // 刷新详情以获取后端最新分值/提示状态
    fetchChallengeDetail(selectedChallenge.value?.slug)
  } catch (err) {
    toast.error(parseApiError(err, '解锁提示失败'))
  } finally {
    unlocking[hint.id] = false
  }
}

const clearCountdown = () => {
  if (countdownTimer) {
    clearInterval(countdownTimer)
    countdownTimer = null
  }
}

const updateCountdown = (info) => {
  clearCountdown()
  if (!info) {
    countdownSeconds.value = null
    return
  }
  let remaining = info.remaining_seconds
  if ((remaining === null || remaining === undefined)) {
    let targetTs = null
    if (info.expires_at) {
      targetTs = new Date(info.expires_at).getTime()
    } else if (info.created_at) {
      const baseMinutes =
        selectedChallenge.value?.machine_config?.max_runtime_minutes ||
        selectedChallenge.value?.max_runtime_minutes ||
        30
      targetTs = new Date(info.created_at).getTime() + baseMinutes * 60 * 1000
    }
    if (targetTs) {
      remaining = Math.max(Math.floor((targetTs - Date.now()) / 1000), 0)
    }
  }
  if (typeof remaining !== 'number' || Number.isNaN(remaining)) {
    countdownSeconds.value = null
    return
  }
  countdownSeconds.value = remaining
  countdownTimer = setInterval(() => {
    const current = typeof countdownSeconds.value === 'number' ? countdownSeconds.value : remaining
    const next = current - 1
    if (next <= 0) {
      countdownSeconds.value = 0
      clearCountdown()
      return
    }
    countdownSeconds.value = next
  }, 1000)
}

const countdownDisplay = computed(() => {
  if (countdownSeconds.value === null || countdownSeconds.value === undefined) return ''
  const total = Math.max(Number(countdownSeconds.value) || 0, 0)
  const h = Math.floor(total / 3600)
  const m = Math.floor((total % 3600) / 60)
  const s = total % 60
  const pad = (v) => String(v).padStart(2, '0')
  return `${pad(h)}:${pad(m)}:${pad(s)}`
})

const extendThresholdSeconds = computed(() => {
  const thresholdMinutes =
    machineInfo.value?.extend_threshold_minutes ??
    selectedChallenge.value?.machine_config?.extend_threshold_minutes ??
    selectedChallenge.value?.extend_threshold_minutes ??
    0
  const num = Number(thresholdMinutes) || 0
  return num <= 0 ? 0 : num * 60
})

const canExtendNow = computed(() => {
  if (!machineRunning.value) return false
  if (extendThresholdSeconds.value <= 0) return true
  if (countdownSeconds.value === null || countdownSeconds.value === undefined) return false
  return countdownSeconds.value <= extendThresholdSeconds.value
})

const startMachine = async () => {
  if (!selectedChallenge.value) return
  machineLoading.value = true
  machineError.value = ''
  try {
    const res = await api.post('/machines/', {
      contest_slug: contestSlug.value,
      challenge_slug: selectedChallenge.value.slug,
    })
    machineInfo.value = res?.data?.data?.machine || res?.data?.machine || null
    toast.success('靶机启动中，可前往靶机页查看')
    // 启动后再拉取列表，确保实例存在于后台列表
    fetchMachineForChallenge(selectedChallenge.value)
    updateCountdown(machineInfo.value)
  } catch (err) {
    machineError.value = parseApiError(err)
    toast.error(machineError.value)
  } finally {
    machineLoading.value = false
  }
}

const stopMachine = async () => {
  if (!machineInfo.value?.id) return
  machineLoading.value = true
  machineError.value = ''
  try {
    const res = await api.post(`/machines/${machineInfo.value.id}/stop/`, {})
    machineInfo.value = res?.data?.data?.machine || res?.data?.machine || { ...machineInfo.value, status: 'stopped' }
    toast.success('靶机已停止')
    updateCountdown(machineInfo.value)
  } catch (err) {
    machineError.value = parseApiError(err)
    toast.error(machineError.value)
  } finally {
    machineLoading.value = false
  }
}

const extendMachine = async () => {
  if (!machineInfo.value?.id) return
  machineLoading.value = true
  machineError.value = ''
  try {
    const res = await api.post(`/machines/${machineInfo.value.id}/extend/`, {})
    machineInfo.value = res?.data?.data?.machine || res?.data?.machine || machineInfo.value
    updateCountdown(machineInfo.value)
    const remainingTimes = machineInfo.value?.remaining_extend_times
    const msg =
      remainingTimes === -1
        ? '靶机已延时，剩余次数不限'
        : `靶机已延时，剩余可延次数：${remainingTimes ?? '未知'}`
    toast.success(msg)
  } catch (err) {
    const status = err?.response?.status
    let msg = parseApiError(err)
    if (status === 409) {
      msg = machineInfo.value?.remaining_extend_times === 0 ? '已达到最大延时次数' : '未到可延时窗口，稍后再试'
    }
    machineError.value = msg
    toast.error(msg)
  } finally {
    machineLoading.value = false
  }
}

const fetchMachineForChallenge = async (chal) => {
  machineLoading.value = true
  machineError.value = ''
  try {
    const res = await api.get('/machines/', { params: { page_size: 50 } })
    const items = res?.data?.data?.items || res?.data?.items || []
    // 优先运行中的实例，否则取最近的同题目实例
    const candidates = items.filter(
      (m) =>
        (m.challenge === chal.slug || m.challenge_slug === chal.slug) &&
        (m.contest === contestSlug.value || m.contest_slug === contestSlug.value),
    )
    let found = candidates.find((m) => m.status === 'running')
    if (!found && candidates.length) {
      found = candidates[0]
    }
    machineInfo.value = found || null
    updateCountdown(machineInfo.value)
  } catch (err) {
    // 静默处理
  } finally {
    machineLoading.value = false
  }
}

onMounted(() => {
  loadContestTitle()
  loadCategories().catch(() => null)
  loadChallenges()
})

onBeforeUnmount(() => {
  clearCountdown()
})

useContestChannel(contestSlug.value, {
  onMessage: (evt) => {
    const event = evt?.event
    if (['challenge_updated', 'challenge_created', 'hint_unlocked', 'scoreboard_updated'].includes(event)) {
      loadCategories().catch(() => null)
      loadChallenges()
    }
  },
})
</script>

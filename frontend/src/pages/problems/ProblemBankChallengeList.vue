<template>
  <AppShell>
    <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <div class="space-y-1">
          <p class="text-xs uppercase tracking-[0.08em] text-primary">题库题目</p>
          <h1 class="text-3xl font-bold leading-tight tracking-tight">{{ bankTitle }}</h1>
          <p class="text-sm text-muted">按分类浏览题库题目，提交 flag 或查看提示。</p>
        </div>
        <RouterLink
          to="/problems"
          class="inline-flex h-10 items-center justify-center rounded-lg border border-input-border px-4 text-sm font-semibold text-text hover:border-primary hover:text-primary"
        >
          返回题库列表
        </RouterLink>
      </div>

      <div class="flex flex-wrap gap-3">
        <button
          v-for="cat in categories"
          :key="cat.value"
          class="inline-flex items-center gap-2 rounded-full border border-input-border px-4 py-2 text-sm font-semibold text-text hover:border-primary hover:text-primary"
          :class="activeCategory === cat.value ? 'bg-primary/15 border-primary text-primary' : ''"
          type="button"
          @click="selectCategory(cat.value)"
        >
          {{ cat.label || cat.value || '未分组' }}
        </button>
      </div>

      <div v-if="loading" class="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
        <div v-for="i in 6" :key="i" class="flex flex-col rounded-xl border border-border-panel bg-panel/90 p-5 shadow-panel space-y-3">
          <SkeletonBlock :count="4" height="16px" />
        </div>
      </div>
      <ErrorState v-else-if="error" :message="error" retry-label="重试" @retry="fetchChallenges" />
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
                <p v-if="categoryFromChallenge(chal)">分类：{{ categoryLabelFromChallenge(chal) }}</p>
                <p v-if="chal.difficulty">难度：{{ chal.difficulty }}</p>
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

      <div v-if="challenges.length" class="flex items-center justify-between border-t border-border-panel/80 pt-4">
        <div class="text-sm text-muted">
          第 {{ pageMeta.page }} / {{ pageMeta.total_pages || Math.max(1, Math.ceil((pageMeta.total || 0) / pageMeta.page_size)) }} 页
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

    <Teleport to="body">
      <div
        v-if="showModal"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm px-4"
        @click.self="closeModal"
      >
        <div class="w-full max-w-3xl rounded-2xl border border-border-panel bg-panel/95 shadow-2xl p-6 space-y-4">
          <div class="flex items-start justify-between gap-3">
            <div class="space-y-1">
              <p class="text-xs uppercase tracking-[0.08em] text-primary">{{ bankTitle }}</p>
              <h2 class="text-2xl font-bold leading-tight">{{ selectedChallenge?.title || selectedChallenge?.name }}</h2>
              <p class="text-sm text-muted line-clamp-2">{{ selectedChallenge?.short_description || selectedChallenge?.description }}</p>
              <div class="flex flex-wrap items-center gap-2 text-xs text-muted">
                <span
                  class="inline-flex items-center rounded-full border border-border-panel px-2 py-0.5 text-[11px] uppercase tracking-wide"
                >
                  {{ selectedChallenge?.category || selectedChallenge?.category_name || selectedChallenge?.category_slug || '未分组' }}
                </span>
                <span>分值：{{ displayPoints(selectedChallenge || {}) }} pts</span>
                <span v-if="selectedChallenge?.difficulty">难度：{{ selectedChallenge?.difficulty }}</span>
                <span class="inline-flex items-center gap-1 rounded-full border border-input-border px-2 py-0.5" v-if="selectedChallenge?.solved !== undefined">
                  <span class="material-symbols-outlined text-[14px]" :class="selectedChallenge?.solved ? 'text-emerald-400' : 'text-muted'">
                    {{ selectedChallenge?.solved ? 'check_circle' : 'radio_button_unchecked' }}
                  </span>
                  {{ selectedChallenge?.solved ? '已解' : '未解' }}
                </span>
              </div>
            </div>
            <button class="text-muted hover:text-text" type="button" @click="closeModal">
              <span class="material-symbols-outlined text-xl">close</span>
            </button>
          </div>

          <div class="rounded-lg border border-border-panel bg-input/40 p-4 text-sm text-text leading-relaxed max-h-64 overflow-auto">
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
            <EmptyState v-if="!hints.length" title="暂无提示" />
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
            <template v-if="selectedChallenge?.has_machine">
              <button
                class="h-11 w-28 rounded-lg border text-sm font-semibold hover:bg-primary/10 disabled:opacity-60"
                :class="machineRunning ? 'border-danger text-danger hover:bg-danger/10' : 'border-primary text-primary'"
                :disabled="machineLoading || !machineContext.contest || !machineContext.challenge"
                type="button"
                @click="machineRunning ? stopMachine() : startMachine()"
              >
                {{ machineLoading ? (machineRunning ? '停止中…' : '启动中…') : machineRunning ? '停止靶机' : '启动靶机' }}
              </button>
              <button
                class="h-11 w-24 rounded-lg border border-input-border text-sm font-semibold text-text hover:border-primary hover:text-primary disabled:opacity-60"
                :disabled="machineLoading || !machineRunning || !canExtendNow"
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
            </template>
          </div>

          <div
            v-if="selectedChallenge?.has_machine"
            class="rounded-lg border border-input-border bg-input/40 p-4 text-sm space-y-3"
          >
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
import { DEFAULT_PAGE_META } from '@/constants/enums'
import { useToastStore } from '@/stores/toast'

const route = useRoute()
const toast = useToastStore()
const bankSlug = computed(() => route.params.bankSlug)

const bankTitle = ref('题库题目')
const challenges = ref([])
const activeCategory = ref('')
const categories = ref([])
const loading = ref(false)
const error = ref('')
const pageMeta = reactive({ ...DEFAULT_PAGE_META, total_pages: 1 })
const selectedChallenge = ref(null)
const showModal = ref(false)
const attachments = ref([])
const hints = ref([])
const flagInputs = reactive({})
const submitting = reactive({})
const detailLoading = ref(false)
const machineLoading = ref(false)
const machineError = ref('')
const machineInfo = ref(null)
const countdownSeconds = ref(null)
let countdownTimer = null
const unlocking = reactive({})

const categoryFromChallenge = (item) => item?.category_slug || item?.category || item?.category_name || ''
const categoryLabelFromChallenge = (item) => item?.category || item?.category_name || item?.category_slug || '未分组'
const filteredChallenges = computed(() => {
  if (!activeCategory.value) return challenges.value
  const list = challenges.value.filter(
    (c) => categoryFromChallenge(c).toLowerCase() === activeCategory.value.toLowerCase(),
  )
  return list.length ? list : challenges.value
})
const displayPoints = (chal) => chal?.score || chal?.points || chal?.base_points || 0
const machineContext = computed(() => ({
  contest: selectedChallenge.value?.machine_contest_slug || '',
  challenge: selectedChallenge.value?.machine_challenge_slug || '',
}))
const machineRunning = computed(() => machineInfo.value?.status === 'running')
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

const fetchBankMeta = async () => {
  try {
    const res = await api.get(`/problem-bank/${bankSlug.value}/meta/`)
    bankTitle.value = res?.data?.data?.name || res?.data?.name || bankSlug.value || '题库题目'
  } catch (err) {
    bankTitle.value = bankSlug.value || '题库题目'
  }
}

const fetchChallenges = async () => {
  loading.value = true
  error.value = ''
  try {
    const res = await api.get(`/problem-bank/${bankSlug.value}/`, {
      params: { page: pageMeta.page, page_size: pageMeta.page_size, category: activeCategory.value || undefined },
    })
    const data = res?.data?.data || res?.data || {}
    const categoryList = Array.isArray(data?.categories) ? data.categories : []
    challenges.value = data.items || []
    challenges.value.forEach((c) => {
      if (!flagInputs[c.slug]) flagInputs[c.slug] = ''
    })
    if (categoryList.length) {
      const normalized = categoryList
        .map((c) => ({
          value: (c?.slug || c?.name || '').toString(),
          label: (c?.name || c?.slug || '未分组').toString(),
        }))
        .filter((c) => c.value)
        .filter((c, idx, arr) => arr.findIndex((x) => x.value === c.value) === idx)
      categories.value = normalized
    } else {
      const set = new Map()
      challenges.value.forEach((item) => {
        const val = categoryFromChallenge(item)
        const label = categoryLabelFromChallenge(item)
        if (!val) return
        if (!set.has(val)) set.set(val, { value: val, label })
      })
      categories.value = Array.from(set.values())
    }
    if (!activeCategory.value && categories.value.length) {
      activeCategory.value = categories.value[0].value
    }
    Object.assign(pageMeta, { ...DEFAULT_PAGE_META, ...res?.data?.extra })
  } catch (err) {
    const status = err?.response?.status
    const msg = parseApiError(err)
    error.value = msg
    if (status === 401) {
      toast.error('请先登录后查看题库')
    } else if (status === 403) {
      toast.error(msg || '暂无权限访问该题库')
    } else {
      toast.error(msg)
    }
  } finally {
    loading.value = false
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
  const expires = info.expires_at
  if ((remaining === null || remaining === undefined) && expires) {
    try {
      remaining = Math.max(Math.floor((new Date(expires).getTime() - Date.now()) / 1000), 0)
    } catch {
      remaining = null
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

const goPage = (page) => {
  pageMeta.page = Math.max(1, page)
  fetchChallenges()
}

const selectCategory = (value) => {
  activeCategory.value = value || ''
  pageMeta.page = 1
  fetchChallenges()
}

const openModal = (chal) => {
  selectedChallenge.value = chal
  attachments.value = chal.attachments || []
  hints.value = (chal.hints || []).map((h) => ({ ...h, unlocked: h.unlocked || false }))
  Object.keys(unlocking).forEach((k) => delete unlocking[k])
  flagInputs[chal.slug] = flagInputs[chal.slug] || ''
  showModal.value = true
  fetchChallengeDetail(chal.slug)
  machineInfo.value = null
  machineError.value = ''
  clearCountdown()
  if (chal.has_machine && machineContext.value.contest && machineContext.value.challenge) {
    fetchMachineForChallenge(chal)
  }
}

const closeModal = () => {
  showModal.value = false
  selectedChallenge.value = null
  attachments.value = []
  hints.value = []
  Object.keys(unlocking).forEach((k) => delete unlocking[k])
  machineError.value = ''
  machineInfo.value = null
  machineLoading.value = false
  clearCountdown()
}

const fetchChallengeDetail = async (slug) => {
  detailLoading.value = true
  try {
    const res = await api.get(`/problem-bank/${bankSlug.value}/${slug}/`)
    const data = res?.data?.data || res?.data || {}
    const detail = data.challenge || data
    selectedChallenge.value = { ...(selectedChallenge.value || {}), ...detail }
    attachments.value = detail.attachments || []
    hints.value = (detail.hints || []).map((h) => ({ ...h, unlocked: h.unlocked || false }))
    selectedChallenge.value = { ...(selectedChallenge.value || {}), ...detail }
  } catch (err) {
    // 静默
  } finally {
    detailLoading.value = false
  }
}

const unlockHint = (hint) => {
  if (!hint?.id || hint.unlocked) return
  unlocking[hint.id] = true
  setTimeout(() => {
    hints.value = hints.value.map((h) => (h.id === hint.id ? { ...h, unlocked: true } : h))
    unlocking[hint.id] = false
  }, 0)
}

const fetchMachineForChallenge = async (chal) => {
  if (!chal?.has_machine || !machineContext.value.contest || !machineContext.value.challenge) return
  machineLoading.value = true
  machineError.value = ''
  try {
    const res = await api.get('/machines/', { params: { page_size: 50 } })
    const items = res?.data?.data?.items || res?.data?.items || []
    const found = items.find(
      (m) =>
        (m.challenge === machineContext.value.challenge) &&
        (m.contest === machineContext.value.contest) &&
        m.status === 'running'
    )
    if (found) {
      machineInfo.value = found
      updateCountdown(found)
    }
  } catch (err) {
    // 静默
  } finally {
    machineLoading.value = false
  }
}

const startMachine = async () => {
  if (!machineContext.value.contest || !machineContext.value.challenge) {
    toast.error('该题未配置靶机')
    return
  }
  machineLoading.value = true
  machineError.value = ''
  try {
    const res = await api.post('/machines/', {
      contest_slug: machineContext.value.contest,
      challenge_slug: machineContext.value.challenge,
    })
    machineInfo.value = res?.data?.data?.machine || res?.data?.machine || null
    updateCountdown(machineInfo.value)
    toast.success('靶机启动中，可前往靶机页查看')
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
    updateCountdown(machineInfo.value)
    toast.success('靶机已停止')
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

const submitFlag = async (slug) => {
  if (!slug) return
  if (!flagInputs[slug]) {
    toast.error('请输入 flag')
    return
  }
  submitting[slug] = true
  try {
    await api.post(`/problem-bank/${bankSlug.value}/${slug}/submit/`, { flag: flagInputs[slug] })
    toast.success('提交成功，等待判题')
    flagInputs[slug] = ''
    fetchChallenges()
    if (selectedChallenge.value?.slug === slug) {
      selectedChallenge.value = { ...selectedChallenge.value, solved: true }
    }
  } catch (err) {
    toast.error(parseApiError(err))
  } finally {
    submitting[slug] = false
  }
}

onMounted(() => {
  fetchBankMeta()
  fetchChallenges()
})

onBeforeUnmount(() => {
  clearCountdown()
})
</script>

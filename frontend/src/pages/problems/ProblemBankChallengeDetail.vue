<template>
  <AppShell>
    <div class="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      <div class="flex items-start justify-between gap-3">
        <div class="space-y-2">
          <p class="text-xs uppercase tracking-[0.08em] text-primary">{{ bankSlug }}</p>
          <h1 class="text-3xl font-bold leading-tight tracking-tight">{{ challenge?.title || challenge?.name || '题目详情' }}</h1>
          <div class="flex flex-wrap items-center gap-3 text-xs text-muted">
            <span v-if="challenge?.category || challenge?.category_name || challenge?.category_slug">
              分类：{{ challenge?.category || challenge?.category_name || challenge?.category_slug }}
            </span>
            <span>分值：{{ displayPoints(challenge || {}) }} pts</span>
            <span v-if="challenge?.difficulty">难度：{{ challenge?.difficulty }}</span>
            <span
              v-if="challenge?.solved !== undefined"
              class="inline-flex items-center gap-1 rounded-full border border-input-border px-2 py-0.5"
            >
              <span class="material-symbols-outlined text-[14px]" :class="challenge?.solved ? 'text-emerald-400' : 'text-muted'">
                {{ challenge?.solved ? 'check_circle' : 'radio_button_unchecked' }}
              </span>
              {{ challenge?.solved ? '已解' : '未解' }}
            </span>
          </div>
        </div>
        <RouterLink
          :to="`/problems/${bankSlug}/challenges`"
          class="inline-flex h-10 items-center justify-center rounded-lg border border-input-border px-4 text-sm font-semibold text-text hover:border-primary hover:text-primary"
        >
          返回列表
        </RouterLink>
      </div>

      <div v-if="loading" class="space-y-3">
        <SkeletonBlock :count="4" height="20px" />
      </div>
      <ErrorState v-else-if="error" :message="error" retry-label="重试" @retry="loadChallenge" />
      <div v-else class="space-y-4">
        <div class="rounded-xl border border-border-panel bg-panel/90 p-5 shadow-panel space-y-3">
          <p class="text-xs uppercase tracking-[0.08em] text-primary">题目描述</p>
          <div class="text-sm text-text/90 leading-relaxed whitespace-pre-wrap">
            {{ challenge?.description || '暂无描述' }}
          </div>
        </div>

        <div class="rounded-xl border border-border-panel bg-panel/90 p-5 shadow-panel space-y-2">
          <div class="flex items-center justify-between">
            <p class="text-sm font-semibold text-text">题目附件</p>
            <span class="text-xs text-muted">{{ attachments.length ? `${attachments.length} 个附件` : '暂无附件' }}</span>
          </div>
          <EmptyState v-if="!attachments?.length" title="暂无附件" />
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

        <div class="rounded-xl border border-border-panel bg-panel/90 p-5 shadow-panel space-y-2">
          <div class="flex items-center justify-between">
            <p class="text-sm font-semibold text-text">提示</p>
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

        <div class="rounded-xl border border-border-panel bg-panel/90 p-5 shadow-panel space-y-3">
          <p class="text-xs uppercase tracking-[0.08em] text-primary">提交 Flag</p>
          <div class="flex flex-wrap items-center gap-3">
            <input
              v-model="flag"
              placeholder="flag{...}"
              class="flex-1 min-w-[220px] h-11 rounded-lg border border-input-border bg-input px-3 text-sm text-text placeholder:text-muted focus:border-primary focus:ring-2 focus:ring-primary/40 outline-none"
              :disabled="submitting"
              @keyup.enter="submitFlag"
            />
            <button
              class="h-11 w-28 rounded-lg bg-primary text-primary-foreground text-sm font-semibold hover:bg-primary/90 disabled:opacity-60"
              type="button"
              :disabled="submitting"
              @click="submitFlag"
            >
              提交
            </button>
            <template v-if="challenge?.has_machine">
              <button
                class="h-11 w-28 rounded-lg border text-sm font-semibold hover:bg-primary/10 disabled:opacity-60"
                :class="machineRunning ? 'border-danger text-danger hover:bg-danger/10' : 'border-primary text-primary'"
                :disabled="machineLoading || !machineContext.contest || !machineContext.machineChallenge"
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
              >
                查看靶机
              </RouterLink>
            </template>
          </div>

          <div
            v-if="challenge?.has_machine"
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
    </div>
  </AppShell>
</template>

<script setup>
import { computed, onMounted, onBeforeUnmount, ref, reactive } from 'vue'
import { useRoute, RouterLink } from 'vue-router'
import AppShell from '@/components/AppShell.vue'
import api from '@/api/client'
import { SkeletonBlock, ErrorState, EmptyState } from '@/components/ui'
import { parseApiError } from '@/api/errors'
import { useToastStore } from '@/stores/toast'

const route = useRoute()
const toast = useToastStore()
const bankSlug = computed(() => route.params.bankSlug)
const challengeSlug = computed(() => route.params.challengeSlug)

const challenge = ref(null)
const attachments = ref([])
const hints = ref([])
const loading = ref(false)
const error = ref('')
const flag = ref('')
const submitting = ref(false)
const displayPoints = (chal) => chal?.score || chal?.points || chal?.base_points || 0
const machineLoading = ref(false)
const machineError = ref('')
const machineInfo = ref(null)
const countdownSeconds = ref(null)
let countdownTimer = null
const unlocking = reactive({})
const machineContext = computed(() => ({
  contest: challenge.value?.machine_contest_slug || '',
  machineChallenge: challenge.value?.machine_challenge_slug || '',
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
    challenge.value?.extend_threshold_minutes ??
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

const loadChallenge = async () => {
  loading.value = true
  error.value = ''
  try {
    const res = await api.get(`/problem-bank/${bankSlug.value}/${challengeSlug.value}/`)
    const data = res?.data?.data || res?.data || {}
    challenge.value = data.challenge || data
    attachments.value = data.attachments || []
    hints.value = (data.hints || []).map((h) => ({ ...h, unlocked: h.unlocked || false }))
    Object.keys(unlocking).forEach((k) => delete unlocking[k])
    if (challenge.value?.has_machine) {
      fetchMachineForChallenge()
    }
  } catch (err) {
    const status = err?.response?.status
    const msg = parseApiError(err)
    error.value = msg
    if (status === 401) {
      toast.error('请先登录后查看题目')
    } else if (status === 403) {
      toast.error(msg || '暂无权限访问该题目')
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

const fetchMachineForChallenge = async () => {
  if (!challenge.value?.has_machine || !machineContext.value.contest || !machineContext.value.machineChallenge) return
  machineLoading.value = true
  machineError.value = ''
  try {
    const res = await api.get('/machines/', { params: { page_size: 50 } })
    const items = res?.data?.data?.items || res?.data?.items || []
    const found = items.find(
      (m) =>
        (m.challenge === machineContext.value.machineChallenge) &&
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
  if (!machineContext.value.contest || !machineContext.value.machineChallenge) {
    toast.error('该题未配置靶机')
    return
  }
  machineLoading.value = true
  machineError.value = ''
  try {
    const res = await api.post('/machines/', {
      contest_slug: machineContext.value.contest,
      challenge_slug: machineContext.value.machineChallenge,
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

const unlockHint = (hint) => {
  if (!hint?.id || hint.unlocked) return
  unlocking[hint.id] = true
  setTimeout(() => {
    hints.value = hints.value.map((h) => (h.id === hint.id ? { ...h, unlocked: true } : h))
    unlocking[hint.id] = false
  }, 0)
}

const submitFlag = async () => {
  if (!flag.value) {
    toast.error('请输入 flag')
    return
  }
  submitting.value = true
  try {
    await api.post(`/problem-bank/${bankSlug.value}/${challengeSlug.value}/submit/`, { flag: flag.value })
    toast.success('提交成功，等待判题')
    flag.value = ''
  } catch (err) {
    toast.error(parseApiError(err))
  } finally {
    submitting.value = false
  }
}

onMounted(() => {
  loadChallenge()
})

onBeforeUnmount(() => {
  clearCountdown()
})
</script>

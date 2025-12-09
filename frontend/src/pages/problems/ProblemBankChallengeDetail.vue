<template>
  <AppShell>
    <div class="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      <div class="flex items-start justify-between gap-3">
        <div class="space-y-2">
          <p class="text-xs uppercase tracking-[0.08em] text-primary">{{ bankSlug }}</p>
          <h1 class="text-3xl font-bold leading-tight tracking-tight">{{ challenge?.title || challenge?.name || '题目详情' }}</h1>
          <div class="flex flex-wrap items-center gap-3 text-xs text-muted">
            <span>分值：{{ challenge?.score || challenge?.points || '--' }}</span>
            <span v-if="challenge?.difficulty">难度：{{ challenge?.difficulty }}</span>
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
      <div v-else class="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <section class="lg:col-span-2 space-y-4">
          <div class="rounded-xl border border-border-panel bg-panel/90 p-5 shadow-panel space-y-3">
            <h2 class="text-lg font-bold">题目描述</h2>
            <div class="text-sm text-text/90 leading-relaxed whitespace-pre-wrap">
              {{ challenge?.description || '暂无描述' }}
            </div>
          </div>
          <div class="rounded-xl border border-border-panel bg-panel/90 p-5 shadow-panel space-y-3">
            <h2 class="text-lg font-bold">附件</h2>
            <EmptyState v-if="!attachments?.length" title="暂无附件" />
            <ul v-else class="space-y-2 text-sm">
              <li v-for="(att, idx) in attachments" :key="idx">
                <a :href="att.url || att.download_url" class="text-primary hover:underline" target="_blank" rel="noreferrer">
                  {{ att.name || `附件 ${idx + 1}` }}
                </a>
              </li>
            </ul>
          </div>
        </section>
        <section class="space-y-4">
          <div class="rounded-xl border border-border-panel bg-panel/90 p-4 shadow-panel space-y-3">
            <h3 class="text-lg font-bold">提交 Flag</h3>
            <input
              v-model="flag"
              placeholder="flag{...}"
              class="h-11 w-full rounded-lg border border-input-border bg-input px-3 text-sm text-text placeholder:text-muted focus:border-primary focus:ring-2 focus:ring-primary/40 outline-none"
              :disabled="submitting"
              @keyup.enter="submitFlag"
            />
            <button
              class="h-11 w-full rounded-lg bg-primary text-primary-foreground text-sm font-semibold hover:bg-primary/90 disabled:opacity-60"
              type="button"
              :disabled="submitting"
              @click="submitFlag"
            >
              提交
            </button>
          </div>
        </section>
      </div>
    </div>
  </AppShell>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
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
const loading = ref(false)
const error = ref('')
const flag = ref('')
const submitting = ref(false)

const loadChallenge = async () => {
  loading.value = true
  error.value = ''
  try {
    const res = await api.get(`/problem-bank/${bankSlug.value}/${challengeSlug.value}/`)
    const data = res?.data?.data || res?.data || {}
    challenge.value = data.challenge || data
    attachments.value = data.attachments || []
  } catch (err) {
    const msg = parseApiError(err)
    error.value = msg
    toast.error(msg)
  } finally {
    loading.value = false
  }
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
</script>

<template>
  <AppShell>
    <div class="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      <div class="flex items-start justify-between gap-3">
        <div class="space-y-2">
          <p class="text-sm uppercase tracking-[0.08em] text-primary">{{ contestTitle }}</p>
          <h1 class="text-4xl font-bold leading-tight tracking-tight">
            {{ announcement?.title || '公告详情' }}
          </h1>
          <div class="flex flex-wrap items-center gap-4 text-sm text-muted">
            <span>创建于 {{ formatDateTime(announcement?.created_at) }}</span>
            <span v-if="announcement?.updated_at">最后更新 {{ formatDateTime(announcement.updated_at) }}</span>
          </div>
        </div>
        <div class="flex items-center gap-2">
          <RouterLink
            :to="`/contests/${contestSlug}/announcements`"
            class="inline-flex h-10 items-center justify-center rounded-lg border border-input-border px-4 text-sm font-semibold text-text hover:border-primary hover:text-primary"
          >
            返回列表
          </RouterLink>
          <RouterLink
            :to="`/contests/${contestSlug}`"
            class="inline-flex h-10 items-center justify-center rounded-lg bg-primary px-4 text-sm font-semibold text-primary-foreground hover:bg-primary/90"
          >
            比赛主页
          </RouterLink>
        </div>
      </div>

      <div v-if="loading" class="space-y-3">
        <SkeletonBlock :count="4" height="20px" />
      </div>
      <ErrorState v-else-if="error" :message="error" retry-label="重试" @retry="fetchDetail" />
      <div v-else class="rounded-xl border border-border-panel bg-panel/90 p-6 shadow-panel space-y-4">
        <p v-if="announcement?.summary" class="text-lg font-semibold text-text leading-relaxed">
          {{ announcement.summary }}
        </p>
        <div class="text-base text-text/90 leading-relaxed whitespace-pre-line" v-html="safeContent"></div>
      </div>
    </div>
  </AppShell>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, RouterLink, useRouter } from 'vue-router'
import AppShell from '@/components/AppShell.vue'
import api from '@/api/client'
import { SkeletonBlock, ErrorState } from '@/components/ui'
import { formatDateTime } from '@/utils/format'
import { parseApiError } from '@/api/errors'
import { useToastStore } from '@/stores/toast'
import { sanitizeHtml } from '@/utils/validation'

const route = useRoute()
const router = useRouter()
const toast = useToastStore()

const contestSlug = computed(() => route.params.contestSlug)
const announcementId = computed(() => route.params.announcementId)
const contestTitle = ref('比赛公告')
const announcement = ref(null)
const loading = ref(false)
const error = ref('')

const safeContent = computed(() => {
  const sanitized = sanitizeHtml(announcement.value?.content || '')
  return sanitized || '暂无内容'
})

const fetchContestTitle = async () => {
  try {
    const res = await api.get(`/contests/${contestSlug.value}/`)
    contestTitle.value = res?.data?.data?.contest?.name || contestSlug.value || '比赛公告'
  } catch (err) {
    contestTitle.value = contestSlug.value || '比赛公告'
  }
}

const fetchDetail = async () => {
  loading.value = true
  error.value = ''
  try {
    const res = await api.get(`/contests/${contestSlug.value}/announcements/${announcementId.value}/`)
    const data = res?.data?.data?.announcement || res?.data?.data || res?.data || null
    announcement.value = data
  } catch (err) {
    if (err?.response?.status === 401) {
      router.replace({ path: '/login', query: { redirect: route.fullPath } })
      return
    }
    const msg = parseApiError(err)
    error.value = msg
    toast.error(msg)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchContestTitle()
  fetchDetail()
})
</script>

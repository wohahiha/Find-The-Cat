<template>
  <div>
    <PublicNav />
    <div class="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      <div class="flex items-start justify-between gap-3">
        <div class="space-y-2">
          <p class="text-xs uppercase tracking-[0.08em] text-primary">平台公告</p>
          <h1 class="text-3xl font-bold leading-tight tracking-tight">{{ announcement?.title || '公告详情' }}</h1>
          <p class="text-xs text-muted">来自比赛 {{ contestSlug || '未知' }}</p>
        </div>
        <div class="flex items-center gap-2">
          <RouterLink
            :to="`/announcements?contest=${contestSlug}`"
            class="inline-flex h-10 items-center justify-center rounded-lg border border-input-border px-4 text-sm font-semibold text-text hover:border-primary hover:text-primary"
          >
            返回列表
          </RouterLink>
        </div>
      </div>

      <div v-if="loading" class="space-y-3">
        <SkeletonBlock :count="4" height="20px" />
      </div>
      <ErrorState v-else-if="error" :message="error" retry-label="重试" @retry="fetchDetail" />
      <div v-else class="rounded-xl border border-border-panel bg-panel/90 p-6 shadow-panel space-y-4">
        <div class="text-xs text-muted">{{ formatDateTime(announcement?.created_at) }}</div>
        <div class="text-sm text-text/90 leading-relaxed whitespace-pre-wrap">
          {{ announcement?.content || '暂无内容' }}
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter, RouterLink } from 'vue-router'
import api from '@/api/client'
import { SkeletonBlock, ErrorState } from '@/components/ui'
import { parseApiError } from '@/api/errors'
import { formatDateTime } from '@/utils/format'
import { useToastStore } from '@/stores/toast'
import { useAuthStore } from '@/stores/auth'
import PublicNav from '@/components/PublicNav.vue'

const route = useRoute()
const router = useRouter()
const toast = useToastStore()
const auth = useAuthStore()

const contestSlug = computed(() => route.query.contest || '')
const announcementId = computed(() => route.params.id)
const isAuthed = computed(() => !!(auth.accessToken || sessionStorage.getItem('ftc_access') || localStorage.getItem('ftc_access')))

const announcement = ref(null)
const loading = ref(false)
const error = ref('')

const ensureAuthed = () => {
  if (isAuthed.value) return true
  toast.error('请先登录后查看公告详情')
  router.replace({ path: '/announcements' })
  return false
}

const fetchDetail = async () => {
  if (!contestSlug.value) {
    error.value = '缺少 contest 参数'
    return
  }
  if (!ensureAuthed()) return
  loading.value = true
  error.value = ''
  try {
    const res = await api.get(`/contests/${contestSlug.value}/announcements/${announcementId.value}/`)
    const data = res?.data?.data?.announcement || res?.data?.data || res?.data || null
    announcement.value = data
  } catch (err) {
    const status = err?.response?.status
    if (status === 401) {
      const msg = '登录已过期，请重新登录后查看'
      toast.error(msg)
      error.value = msg
      router.replace({ path: '/announcements' })
      return
    }
    if (status === 403) {
      const msg = '需报名/加入比赛后才能查看公告'
      toast.error(msg)
      error.value = msg
      router.replace({ path: '/announcements' })
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
  if (!ensureAuthed()) return
  fetchDetail()
})
</script>

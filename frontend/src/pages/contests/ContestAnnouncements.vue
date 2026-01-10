<template>
  <AppShell>
    <div class="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <div class="space-y-1">
          <p class="text-xs uppercase tracking-[0.08em] text-primary">比赛公告</p>
          <h1 class="text-3xl font-bold leading-tight tracking-tight">
            {{ contestTitle }}
          </h1>
          <p class="text-sm text-muted">来自比赛的最新通知、变更与重要信息。</p>
        </div>
        <div class="flex items-center gap-2">
          <RouterLink
            :to="`/contests/${contestSlug}`"
            class="inline-flex h-10 items-center justify-center rounded-lg border border-input-border px-4 text-sm font-semibold text-text hover:border-primary hover:text-primary"
          >
            返回比赛
          </RouterLink>
        </div>
      </div>

      <div v-if="loading" class="space-y-3">
        <SkeletonBlock :count="3" height="20px" />
        <SkeletonBlock :count="3" height="20px" />
        <SkeletonBlock :count="3" height="20px" />
      </div>

      <ErrorState v-else-if="error" :message="error" retry-label="重试" @retry="fetchAnnouncements" />
      <EmptyState v-else-if="!announcements.length" title="暂无公告" description="当前比赛暂未发布公告。" />

      <div v-else class="space-y-4">
        <article
          v-for="item in announcements"
          :key="item.id"
          class="rounded-xl border border-border-panel bg-panel/90 p-5 shadow-panel hover:border-primary/40 transition-colors"
        >
          <div class="flex items-start gap-3">
            <div class="flex h-10 w-10 items-center justify-center rounded-full bg-primary/15 text-primary">
              <span class="material-symbols-outlined">campaign</span>
            </div>
            <div class="flex-1 min-w-0 space-y-2">
              <div class="flex flex-wrap items-center gap-3 justify-between">
                <RouterLink
                  :to="`/contests/${contestSlug}/announcements/${item.id}`"
                  class="text-lg font-bold hover:text-primary line-clamp-2"
                >
                  {{ item.title }}
                </RouterLink>
                <span class="text-xs text-muted">{{ formatDateTime(item.created_at) }}</span>
              </div>
              <p class="text-sm text-muted leading-relaxed line-clamp-3">
                {{ item.summary || item.content }}
              </p>
            </div>
            <RouterLink
              :to="`/contests/${contestSlug}/announcements/${item.id}`"
              class="text-primary text-sm font-semibold hover:underline shrink-0"
            >
              查看
            </RouterLink>
          </div>
        </article>
      </div>

      <div v-if="announcements.length" class="flex items-center justify-between border-t border-border-panel/80 pt-4">
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
  </AppShell>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, RouterLink } from 'vue-router'
import AppShell from '@/components/AppShell.vue'
import api from '@/api/client'
import { SkeletonBlock, EmptyState, ErrorState } from '@/components/ui'
import { formatDateTime } from '@/utils/format'
import { parseApiError } from '@/api/errors'
import { DEFAULT_PAGE_META } from '@/constants/enums'
import { useToastStore } from '@/stores/toast'

const route = useRoute()
const toast = useToastStore()

const contestSlug = computed(() => route.params.contestSlug)
const contestTitle = ref('比赛公告')
const announcements = ref([])
const loading = ref(false)
const error = ref('')
const pageMeta = reactive({ ...DEFAULT_PAGE_META, total_pages: 1 })

const fetchContestTitle = async () => {
  try {
    const res = await api.get(`/contests/${contestSlug.value}/`)
    contestTitle.value = res?.data?.data?.contest?.name || contestSlug.value || '比赛公告'
  } catch (err) {
    // 不阻塞公告列表加载
    contestTitle.value = contestSlug.value || '比赛公告'
  }
}

const fetchAnnouncements = async () => {
  loading.value = true
  error.value = ''
  try {
    const res = await api.get(`/contests/${contestSlug.value}/announcements/`, {
      params: { page: pageMeta.page, page_size: pageMeta.page_size },
    })
    const data = res?.data?.data || res?.data || {}
    announcements.value = data.items || []
    Object.assign(pageMeta, { ...DEFAULT_PAGE_META, ...res?.data?.extra })
  } catch (err) {
    const msg = parseApiError(err)
    error.value = msg
    toast.error(msg)
  } finally {
    loading.value = false
  }
}

const goPage = (page) => {
  pageMeta.page = Math.max(1, page)
  fetchAnnouncements()
}

watch(
  () => contestSlug.value,
  () => {
    pageMeta.page = 1
    fetchContestTitle()
    fetchAnnouncements()
  },
)

onMounted(() => {
  fetchContestTitle()
  fetchAnnouncements()
})
</script>

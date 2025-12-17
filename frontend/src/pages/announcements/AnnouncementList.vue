<template>
  <div>
    <PublicNav />
    <div class="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      <header class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div class="space-y-2">
          <p class="text-xs uppercase tracking-[0.08em] text-primary">平台公告</p>
          <h1 class="text-3xl font-bold leading-tight tracking-tight">公告列表</h1>
          <p class="text-sm text-muted">默认展示全部公告，可按比赛名称模糊筛选。</p>
        </div>
        <div class="flex w-full sm:w-auto items-center gap-2">
          <input
            v-model="contestKeyword"
            placeholder="输入比赛名称关键词，如：classic"
            class="h-11 w-full sm:w-80 rounded-lg border border-input-border bg-input px-3 text-sm text-text placeholder:text-muted focus:border-primary focus:ring-2 focus:ring-primary/40 outline-none"
            @keyup.enter="onSearch"
          />
          <button
            class="inline-flex h-11 items-center justify-center rounded-lg bg-primary px-4 text-sm font-semibold text-primary-foreground hover:bg-primary/90 whitespace-nowrap"
            type="button"
            @click="onSearch"
          >
            搜索
          </button>
        </div>
      </header>

      <div v-if="loading" class="space-y-3">
        <SkeletonBlock :count="3" height="16px" />
      </div>
      <ErrorState v-else-if="error" :message="error" retry-label="重试" @retry="fetchAnnouncements" />
      <EmptyState v-else-if="!announcements.length" title="暂无公告" />
      <div v-else class="space-y-3">
        <article
          v-for="item in announcements"
          :key="item.id"
          role="button"
          tabindex="0"
          class="block rounded-xl border border-border-panel bg-panel/90 p-4 shadow-panel hover:border-primary/40 cursor-pointer outline-none focus:ring-2 focus:ring-primary/40"
          @click="handleItemClick(item)"
          @keyup.enter="handleItemClick(item)"
        >
          <div class="flex items-start gap-3">
            <div class="flex h-10 w-10 items-center justify-center rounded-full bg-primary/15 text-primary">
              <span class="material-symbols-outlined">campaign</span>
            </div>
            <div class="flex-1 space-y-1">
              <div class="flex items-center justify-between gap-3">
                <p class="text-lg font-bold line-clamp-2">{{ item.title }}</p>
                <span class="text-xs text-muted whitespace-nowrap">{{ formatDateTime(item.created_at) }}</span>
              </div>
              <p class="text-sm text-muted leading-relaxed line-clamp-2">{{ item.summary || item.content }}</p>
              <p class="text-xs text-muted">所属比赛：{{ item.contest || '未注明' }}</p>
            </div>
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
  </div>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '@/api/client'
import { SkeletonBlock, EmptyState, ErrorState } from '@/components/ui'
import { parseApiError } from '@/api/errors'
import { useToastStore } from '@/stores/toast'
import { formatDateTime } from '@/utils/format'
import { useAuthStore } from '@/stores/auth'
import PublicNav from '@/components/PublicNav.vue'
import { DEFAULT_PAGE_META } from '@/constants/enums'

const route = useRoute()
const router = useRouter()
const toast = useToastStore()
const auth = useAuthStore()

const contestKeyword = ref('')
const announcements = ref([])
const contests = ref([])
const loading = ref(false)
const error = ref('')
const isManualSearch = ref(false)
const pageMeta = reactive({ ...DEFAULT_PAGE_META, total_pages: 1 })

const isAuthed = computed(() => !!(auth.accessToken || sessionStorage.getItem('ftc_access') || localStorage.getItem('ftc_access')))

const normalize = (val = '') => val.toString().toLowerCase().trim()

const fetchContests = async () => {
  if (contests.value.length) return
  try {
    const res = await api.get('/contests/', { params: { page_size: 200 } })
    const data = res?.data?.data?.items || res?.data?.items || []
    contests.value = data.map((item) => ({
      slug: item.slug,
      name: item.name,
    }))
  } catch (e) {
    // 静默失败，不阻塞公告列表
    contests.value = []
  }
}

const filterByContestName = (items) => {
  const key = isManualSearch.value ? normalize(contestKeyword.value) : ''
  if (!key) return items
  return items.filter((item) => {
    const contestInfo = contests.value.find((c) => c.slug === item.contest)
    const target = normalize(`${contestInfo?.name || ''} ${contestInfo?.slug || item.contest || ''}`)
    return target.includes(key)
  })
}

const fetchAnnouncements = async () => {
  loading.value = true
  error.value = ''
  try {
    await fetchContests()
    const params = { page: pageMeta.page, page_size: pageMeta.page_size }
    const res = await api.get('/contests/announcements/', { params })
    const data = res?.data?.data || res?.data || {}
    const raw = (data.items || []).map((item) => ({
      ...item,
      contest: item.contest || '',
      created_at: item.created_at || item.updated_at,
    }))
    announcements.value = filterByContestName(raw)
    Object.assign(pageMeta, { ...DEFAULT_PAGE_META, ...res?.data?.extra })
  } catch (err) {
    const msg = parseApiError(err)
    error.value = msg
    toast.error(msg)
  } finally {
    loading.value = false
  }
}

const handleItemClick = (item) => {
  if (!isAuthed.value) {
    toast.error('请先登录后查看公告详情')
    return
  }
  const contest = item.contest || ''
  if (!contest) {
    toast.error('缺少比赛标识，无法查看公告详情')
    return
  }
  router.push({ path: `/announcements/${item.id}`, query: { contest } })
}

const onSearch = () => {
  isManualSearch.value = true
  pageMeta.page = 1
  fetchAnnouncements()
}

const goPage = (page) => {
  pageMeta.page = Math.max(1, page)
  fetchAnnouncements()
}

// 初始加载全局公告
fetchAnnouncements()
</script>

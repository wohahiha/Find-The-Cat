<template>
  <AppShell>
    <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      <header class="flex flex-wrap justify-between gap-4 items-center">
        <div class="flex min-w-72 flex-col gap-2">
          <p class="text-4xl font-black leading-tight tracking-[-0.03em]">题库列表</p>
          <p class="text-base text-muted leading-normal">浏览公开题库，进入练习或查看详情。</p>
        </div>
      </header>

      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 px-1">
        <div class="flex flex-col gap-2">
          <label class="text-xs text-muted">关键词</label>
          <div class="flex w-full items-stretch rounded-lg h-11">
            <div class="text-muted flex border border-r-0 border-input-border bg-input items-center justify-center pl-4 rounded-l-lg">
              <span class="material-symbols-outlined">search</span>
            </div>
            <input
              v-model.trim="filters.keyword"
              class="form-input flex w-full min-w-0 flex-1 rounded-lg text-text focus:outline-0 focus:ring-2 focus:ring-primary border border-input-border bg-input h-full placeholder:text-muted px-4 rounded-l-none border-l-0 pl-2 text-base font-normal leading-normal"
              placeholder="按名称或描述搜索"
              type="text"
              @keyup.enter="applySearch"
            />
          </div>
        </div>
        <div class="flex flex-col gap-2">
          <label class="text-xs text-muted">标签（逗号分隔）</label>
          <input
            v-model.trim="filters.tags"
            class="h-11 rounded-lg border border-input-border bg-input px-3 text-sm text-text placeholder:text-muted focus:border-primary focus:ring-2 focus:ring-primary/40 outline-none"
            placeholder="如 web,pwn 或分类关键字"
            @keyup.enter="applySearch"
          />
        </div>
        <div class="flex flex-col gap-2">
          <label class="text-xs text-muted">难度</label>
          <select
            v-model="filters.difficulty"
            class="h-11 rounded-lg border border-input-border bg-input px-3 text-sm text-text focus:border-primary focus:ring-2 focus:ring-primary/40 outline-none"
          >
            <option value="">全部</option>
            <option value="easy">Easy</option>
            <option value="medium">Medium</option>
            <option value="hard">Hard</option>
          </select>
        </div>
        <div class="flex flex-col gap-2">
          <label class="text-xs text-muted">作者 ID</label>
          <input
            v-model.trim="filters.author"
            class="h-11 rounded-lg border border-input-border bg-input px-3 text-sm text-text placeholder:text-muted focus:border-primary focus:ring-2 focus:ring-primary/40 outline-none"
            placeholder="填写数字 ID"
            inputmode="numeric"
            @keyup.enter="applySearch"
          />
        </div>
        <div class="flex flex-col gap-2">
          <label class="text-xs text-muted">可见性</label>
          <select
            v-model="filters.is_public"
            class="h-11 rounded-lg border border-input-border bg-input px-3 text-sm text-text focus:border-primary focus:ring-2 focus:ring-primary/40 outline-none"
          >
            <option value="">全部</option>
            <option value="true">公开</option>
            <option value="false">私有</option>
          </select>
        </div>
        <div class="flex flex-col gap-2">
          <label class="text-xs text-muted">更新时间（起/止）</label>
          <div class="flex items-center gap-2">
            <input
              v-model="filters.updated_after"
              class="h-11 flex-1 rounded-lg border border-input-border bg-input px-3 text-sm text-text focus:border-primary focus:ring-2 focus:ring-primary/40 outline-none"
              type="date"
            />
            <input
              v-model="filters.updated_before"
              class="h-11 flex-1 rounded-lg border border-input-border bg-input px-3 text-sm text-text focus:border-primary focus:ring-2 focus:ring-primary/40 outline-none"
              type="date"
            />
          </div>
        </div>
        <div class="flex items-end gap-2">
          <button
            type="button"
            class="inline-flex h-11 items-center justify-center rounded-lg bg-primary px-4 text-sm font-semibold text-primary-foreground hover:bg-primary/90"
            @click="applySearch"
          >
            筛选
          </button>
          <button
            type="button"
            class="inline-flex h-11 items-center justify-center rounded-lg border border-input-border px-4 text-sm font-semibold text-text hover:border-primary hover:text-primary"
            @click="resetFilters"
          >
            重置
          </button>
        </div>
      </div>

      <div v-if="loading" class="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
        <div v-for="i in 6" :key="i" class="flex flex-col rounded-xl border border-border-panel bg-panel/90 p-5 shadow-panel space-y-3">
          <SkeletonBlock :count="4" height="16px" />
        </div>
      </div>
      <ErrorState v-else-if="error" :message="error" retry-label="重试" @retry="fetchBanks" />
      <EmptyState v-else-if="!filteredBanks.length" title="暂无题库" description="试试清空搜索或稍后再试" />
      <div v-else class="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
        <div
          v-for="bank in filteredBanks"
          :key="bank.slug"
          class="flex flex-col rounded-xl border border-border-panel bg-panel/90 p-5 shadow-panel space-y-3"
        >
          <div class="flex items-center justify-between gap-2">
            <RouterLink
              :to="`/problems/${bank.slug}/challenges`"
              class="text-lg font-bold hover:text-primary line-clamp-1"
            >
              {{ bank.name }}
            </RouterLink>
            <span class="text-xs text-muted">{{ bank.is_public ? '公开' : '私有' }}</span>
          </div>
          <p class="text-sm text-muted leading-relaxed line-clamp-3">{{ bank.description }}</p>
          <div class="mt-auto">
            <RouterLink
              :to="`/problems/${bank.slug}/challenges`"
              class="flex h-10 w-full items-center justify-center rounded-lg bg-primary text-primary-foreground text-sm font-semibold hover:bg-primary/90"
            >
              进入题库
            </RouterLink>
          </div>
        </div>
      </div>

      <div v-if="filteredBanks.length" class="flex items-center justify-between border-t border-border-panel/80 pt-4">
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
import { RouterLink, useRoute, useRouter } from 'vue-router'
import AppShell from '@/components/AppShell.vue'
import api from '@/api/client'
import { SkeletonBlock, EmptyState, ErrorState } from '@/components/ui'
import { parseApiError } from '@/api/errors'
import { DEFAULT_PAGE_META } from '@/constants/enums'
import { useToastStore } from '@/stores/toast'

const toast = useToastStore()
const banks = ref([])
const loading = ref(false)
const error = ref('')
const pageMeta = reactive({ ...DEFAULT_PAGE_META, total_pages: 1 })
const route = useRoute()
const router = useRouter()
const filters = reactive({
  keyword: '',
  tags: '',
  difficulty: '',
  author: '',
  is_public: '',
  updated_after: '',
  updated_before: '',
})

const filteredBanks = computed(() => banks.value)

const fetchBanks = async () => {
  loading.value = true
  error.value = ''
  try {
    const res = await api.get('/problem-bank/', {
      params: {
        page: pageMeta.page,
        page_size: pageMeta.page_size,
        keyword: filters.keyword || undefined,
        tags: filters.tags || undefined,
        difficulty: filters.difficulty || undefined,
        author: filters.author || undefined,
        is_public: filters.is_public || undefined,
        updated_after: filters.updated_after || undefined,
        updated_before: filters.updated_before || undefined,
      },
    })
    const data = res?.data?.data || res?.data || {}
    banks.value = data.items || []
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
  fetchBanks()
}

const resetFilters = () => {
  filters.keyword = ''
  filters.tags = ''
  filters.difficulty = ''
  filters.author = ''
  filters.is_public = ''
  filters.updated_after = ''
  filters.updated_before = ''
  pageMeta.page = 1
  syncQuery()
  fetchBanks()
}

const applySearch = () => {
  pageMeta.page = 1
  syncQuery()
  fetchBanks()
}

const syncQuery = () => {
  router.replace({
    query: {
      ...route.query,
      keyword: filters.keyword || undefined,
      tags: filters.tags || undefined,
      difficulty: filters.difficulty || undefined,
      author: filters.author || undefined,
      is_public: filters.is_public || undefined,
      updated_after: filters.updated_after || undefined,
      updated_before: filters.updated_before || undefined,
      page: pageMeta.page !== 1 ? pageMeta.page : undefined,
    },
  })
}

const loadFromQuery = () => {
  const q = route.query
  filters.keyword = q.keyword || ''
  filters.tags = q.tags || ''
  filters.difficulty = q.difficulty || ''
  filters.author = q.author || ''
  filters.is_public = q.is_public || ''
  filters.updated_after = q.updated_after || ''
  filters.updated_before = q.updated_before || ''
  const page = parseInt(q.page || '1', 10)
  pageMeta.page = Number.isNaN(page) ? 1 : page
}

watch(
  () => route.query,
  () => {
    loadFromQuery()
    fetchBanks()
  },
)

onMounted(() => {
  loadFromQuery()
  fetchBanks()
})
</script>

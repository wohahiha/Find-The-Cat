<template>
  <AppShell>
    <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <div class="space-y-1">
          <p class="text-xs uppercase tracking-[0.08em] text-primary">题库题目</p>
          <h1 class="text-3xl font-bold leading-tight tracking-tight">{{ bankTitle }}</h1>
          <p class="text-sm text-muted">选择题目进入练习。</p>
        </div>
        <RouterLink
          to="/problems"
          class="inline-flex h-10 items-center justify-center rounded-lg border border-input-border px-4 text-sm font-semibold text-text hover:border-primary hover:text-primary"
        >
          返回题库列表
        </RouterLink>
      </div>

      <div v-if="loading" class="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
        <div v-for="i in 6" :key="i" class="flex flex-col rounded-xl border border-border-panel bg-panel/90 p-5 shadow-panel space-y-3">
          <SkeletonBlock :count="4" height="16px" />
        </div>
      </div>
      <ErrorState v-else-if="error" :message="error" retry-label="重试" @retry="fetchChallenges" />
      <EmptyState v-else-if="!challenges.length" title="暂无题目" />
      <div v-else class="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
        <RouterLink
          v-for="item in challenges"
          :key="item.slug"
          :to="`/problems/${bankSlug}/challenges/${item.slug}`"
          class="flex flex-col rounded-xl border border-border-panel bg-panel/90 p-5 shadow-panel hover:border-primary/40 transition-colors"
        >
          <div class="flex items-start justify-between gap-2">
            <div>
              <p class="text-lg font-bold leading-tight line-clamp-1">{{ item.title }}</p>
              <p class="text-xs text-muted mt-1 line-clamp-2">{{ item.short_description }}</p>
            </div>
            <span class="text-sm font-semibold text-primary">{{ item.score || item.points || '--' }} pts</span>
          </div>
          <div class="mt-auto text-xs text-muted flex items-center gap-2 pt-3">
            <span>{{ item.difficulty || '未知难度' }}</span>
            <span>·</span>
            <span>{{ item.solved ? '已解' : '未解' }}</span>
          </div>
        </RouterLink>
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
  </AppShell>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
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
const loading = ref(false)
const error = ref('')
const pageMeta = reactive({ ...DEFAULT_PAGE_META, total_pages: 1 })

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
      params: { page: pageMeta.page, page_size: pageMeta.page_size },
    })
    const data = res?.data?.data || res?.data || {}
    challenges.value = data.items || []
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
  fetchChallenges()
}

onMounted(() => {
  fetchBankMeta()
  fetchChallenges()
})
</script>

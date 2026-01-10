<template>
  <AppShell>
    <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <div class="space-y-1">
          <p class="text-xs uppercase tracking-[0.08em] text-primary">提交记录</p>
          <h1 class="text-3xl font-bold leading-tight tracking-tight">最近提交</h1>
          <p class="text-sm text-muted">查看个人提交状态，支持分页刷新。</p>
        </div>
        <RouterLink
          :to="`/contests/${contestSlug}/challenges`"
          class="inline-flex h-10 items-center justify-center rounded-lg border border-input-border px-4 text-sm font-semibold text-text hover:border-primary hover:text-primary"
        >
          返回题目
        </RouterLink>
      </div>

      <div class="flex items-center gap-3">
        <select
          v-model="scope"
          class="h-10 rounded-lg border border-input-border bg-input px-3 text-sm text-text focus:border-primary focus:ring-2 focus:ring-primary/40 outline-none"
          @change="fetchSubmissions"
        >
          <option value="personal">个人提交</option>
          <option value="team">队伍提交</option>
        </select>
        <button
          class="inline-flex h-10 items-center justify-center rounded-lg border border-input-border px-4 text-sm font-semibold text-text hover:border-primary hover:text-primary"
          type="button"
          @click="fetchSubmissions"
        >
          刷新
        </button>
      </div>

      <div v-if="loading" class="space-y-3">
        <SkeletonBlock :count="3" height="16px" />
      </div>
      <ErrorState v-else-if="error" :message="error" retry-label="重试" @retry="fetchSubmissions" />
      <EmptyState v-else-if="!submissions.length" title="暂无提交" />
      <div v-else class="overflow-x-auto rounded-xl border border-border-panel bg-panel/90 shadow-panel">
        <table class="min-w-full text-sm text-left">
          <thead class="border-b border-border-panel/70 text-muted">
            <tr>
              <th class="px-4 py-3 font-semibold">时间</th>
              <th class="px-4 py-3 font-semibold">题目</th>
              <th class="px-4 py-3 font-semibold">Flag</th>
              <th class="px-4 py-3 font-semibold">状态</th>
              <th class="px-4 py-3 font-semibold text-right">得分</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in submissions" :key="item.id || item.created_at" class="border-b border-border-panel/50 last:border-0">
              <td class="px-4 py-3 text-muted whitespace-nowrap">{{ formatDateTime(item.created_at) }}</td>
              <td class="px-4 py-3">{{ item.challenge?.title || item.challenge || '--' }}</td>
              <td class="px-4 py-3 text-muted truncate max-w-[220px]">{{ item.submission?.flag || item.flag || '***' }}</td>
              <td class="px-4 py-3">
                <span class="inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold" :class="statusClass(item.status)">
                  {{ statusLabel(item.status) }}
                </span>
              </td>
              <td class="px-4 py-3 text-right font-semibold">{{ item.awarded_points ?? item.score ?? 0 }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-if="submissions.length" class="flex items-center justify-between border-t border-border-panel/80 pt-4">
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
import { formatDateTime } from '@/utils/format'
import { parseApiError } from '@/api/errors'
import { DEFAULT_PAGE_META, SUBMISSION_STATUS } from '@/constants/enums'
import { useToastStore } from '@/stores/toast'

const route = useRoute()
const toast = useToastStore()
const contestSlug = computed(() => route.params.contestSlug)

const submissions = ref([])
const loading = ref(false)
const error = ref('')
const scope = ref('personal')
const pageMeta = reactive({ ...DEFAULT_PAGE_META, total_pages: 1 })

const statusLabel = (s) => {
  if (s === SUBMISSION_STATUS.ACCEPTED) return '正确'
  if (s === SUBMISSION_STATUS.REJECTED) return '错误'
  if (s === SUBMISSION_STATUS.PENDING) return '判题中'
  if (s === SUBMISSION_STATUS.ERROR) return '异常'
  return s || '未知'
}

const statusClass = (s) => {
  if (s === SUBMISSION_STATUS.ACCEPTED) return 'bg-green-500/15 text-green-400'
  if (s === SUBMISSION_STATUS.REJECTED) return 'bg-danger/15 text-danger'
  if (s === SUBMISSION_STATUS.PENDING) return 'bg-yellow-500/15 text-yellow-400'
  if (s === SUBMISSION_STATUS.ERROR) return 'bg-border-panel text-muted'
  return 'bg-border-panel text-muted'
}

const fetchSubmissions = async () => {
  loading.value = true
  error.value = ''
  try {
    const res = await api.get(`/contests/${contestSlug.value}/submissions/`, {
      params: {
        scope: scope.value,
        page: pageMeta.page,
        page_size: pageMeta.page_size,
      },
    })
    const data = res?.data?.data || res?.data || {}
    submissions.value = data.items || []
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
  fetchSubmissions()
}

onMounted(() => {
  fetchSubmissions()
})
</script>

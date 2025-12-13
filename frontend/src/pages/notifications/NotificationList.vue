<template>
  <AppShell>
    <section class="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
      <div class="flex items-center justify-between mb-4">
        <div>
          <h1 class="text-2xl font-semibold text-text">系统通知</h1>
          <p class="text-sm text-muted mt-1">查看未读/全部通知，点击即可标记已读并跳转</p>
        </div>
        <div class="flex items-center gap-3">
          <button
            class="rounded-lg border border-border-panel px-3 py-2 text-sm hover:bg-surface"
            @click="refresh"
            :disabled="loading"
          >
            刷新
          </button>
          <button
            class="rounded-lg bg-primary px-3 py-2 text-sm font-semibold text-primary-foreground hover:bg-primary/90"
            @click="markAll"
            :disabled="loading || unread === 0"
          >
            全部已读
          </button>
        </div>
      </div>

      <div class="flex items-center gap-3 mb-4">
        <button
          class="rounded-lg px-3 py-2 text-sm"
          :class="status === 'all' ? 'bg-primary text-primary-foreground' : 'border border-border-panel text-text hover:bg-surface'"
          @click="setStatus('all')"
        >
          全部
        </button>
        <button
          class="rounded-lg px-3 py-2 text-sm"
          :class="status === 'unread' ? 'bg-primary text-primary-foreground' : 'border border-border-panel text-text hover:bg-surface'"
          @click="setStatus('unread')"
        >
          未读 ({{ unread }})
        </button>
      </div>

      <div class="rounded-lg border border-border-panel divide-y divide-border-panel bg-background">
        <template v-if="items.length">
          <div
            v-for="item in items"
            :key="item.id"
            class="px-4 py-3 hover:bg-surface cursor-pointer"
            @click="onItemClick(item)"
          >
            <div class="flex items-start justify-between gap-3">
              <div>
                <div class="text-base font-semibold text-text">{{ item.title }}</div>
                <div class="mt-1 text-sm text-muted whitespace-pre-line">{{ item.body }}</div>
                <div class="mt-1 text-xs text-muted">{{ formatDate(item.created_at) }}</div>
              </div>
              <span
                class="mt-1 h-2 w-2 rounded-full"
                :class="item.read_at ? 'bg-border-panel' : 'bg-primary'"
                aria-hidden="true"
              />
            </div>
          </div>
          <div class="flex items-center justify-center py-3">
            <button
              class="rounded-lg border border-border-panel px-3 py-2 text-sm hover:bg-surface disabled:opacity-50"
              :disabled="loading || !hasMore"
              @click="loadMore"
            >
              {{ hasMore ? '加载更多' : '没有更多了' }}
            </button>
          </div>
        </template>
        <div v-else class="p-6 text-center text-muted text-sm">暂无通知</div>
      </div>
    </section>
  </AppShell>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useNotificationStore } from '@/stores/notifications'
import AppShell from '@/components/AppShell.vue'

const store = useNotificationStore()
const router = useRouter()

const items = computed(() => store.items)
const unread = computed(() => store.unread)
const loading = computed(() => store.loading)
const hasMore = computed(() => store.hasMore)
const status = computed(() => store.status)

const formatDate = (ts) => {
  if (!ts) return ''
  return new Date(ts).toLocaleString()
}

const onItemClick = (item) => {
  store.markRead(item.id)
  const payload = item.payload || {}
  if (payload.contest) {
    router.push(`/contests/${payload.contest}`)
  } else if (payload.bank) {
    router.push(`/problems/${payload.bank}`)
  }
}

const loadMore = () => {
  store.fetchList({ status: status.value })
}

const refresh = () => {
  store.fetchList({ reset: true, status: status.value })
  store.fetchUnreadCount()
}

const setStatus = (val) => {
  store.fetchList({ reset: true, status: val })
  store.fetchUnreadCount()
}

const markAll = () => {
  store.markAllRead()
}

onMounted(() => {
  if (!items.value.length) {
    store.fetchUnreadCount()
    store.fetchList({ reset: true, status: status.value })
  }
})
</script>

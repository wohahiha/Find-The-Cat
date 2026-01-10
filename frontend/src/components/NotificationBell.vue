<template>
  <div class="relative">
    <button
      class="flex h-9 w-9 items-center justify-center rounded-lg bg-border-panel text-muted hover:text-text hover:bg-input-border relative"
      type="button"
      aria-label="Notifications"
      @click="toggleDrawer"
    >
      <span class="material-symbols-outlined text-lg">notifications</span>
      <span
        v-if="unreadCount > 0"
        class="absolute -top-1 -right-1 inline-flex min-w-5 translate-x-1/4 -translate-y-1/4 items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-semibold text-white shadow-md"
      >
        {{ unreadCount > 99 ? '99+' : unreadCount }}
      </span>
    </button>
    <div
      v-if="drawerOpen"
      class="absolute right-0 mt-2 w-80 rounded-lg border border-border-panel bg-background-dark/95 shadow-2xl backdrop-blur-md z-50 overflow-hidden"
    >
      <div class="flex items-center justify-between px-3 py-2 border-b border-border-panel/80">
        <div class="text-sm font-semibold text-text">系统通知</div>
        <div class="flex items-center gap-2 text-xs text-muted">
          <button class="hover:text-text" @click="markAll">全部已读</button>
          <button class="hover:text-text" @click="goNotificationPage">查看全部</button>
        </div>
      </div>
      <div class="max-h-80 overflow-y-auto divide-y divide-border-panel">
        <template v-if="notifications.length">
          <div
            v-for="item in notifications"
            :key="item.id"
            class="px-3 py-2 hover:bg-surface cursor-pointer"
            @click="onItemClick(item)"
          >
            <div class="flex items-start justify-between gap-2">
              <div class="text-sm font-semibold text-text line-clamp-1">{{ item.title }}</div>
              <span
                class="mt-0.5 h-2 w-2 rounded-full"
                :class="item.read_at ? 'bg-border-panel' : 'bg-primary'"
                aria-hidden="true"
              />
            </div>
            <div class="mt-1 text-xs text-muted line-clamp-2">{{ item.body }}</div>
            <div class="mt-1 text-[11px] text-muted">
              {{ formatDate(item.created_at) }}
            </div>
          </div>
        </template>
        <div v-else class="px-3 py-6 text-center text-xs text-muted">暂无通知</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useNotificationStore } from '@/stores/notifications'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'

const router = useRouter()
const notificationStore = useNotificationStore()
const auth = useAuthStore()
const toast = useToastStore()

const hasToken = () => {
  if (typeof window === 'undefined') return false
  return (
    !!auth.accessToken ||
    !!auth.refreshToken ||
    !!localStorage.getItem('ftc_access') ||
    !!sessionStorage.getItem('ftc_access')
  )
}

const isLoggedIn = computed(() => !!auth.user || hasToken())
const unreadCount = computed(() => notificationStore.unread)
const notifications = computed(() => notificationStore.items.slice(0, 10))
const drawerOpen = computed({
  get: () => notificationStore.drawerOpen || false,
  set: (val) => {
    notificationStore.drawerOpen = val
  },
})

const toggleDrawer = () => {
  if (!isLoggedIn.value) {
    toast.error('请先登录后查看通知')
    router.push('/login')
    return
  }
  drawerOpen.value = !drawerOpen.value
  if (drawerOpen.value && notificationStore.items.length === 0) {
    notificationStore.fetchUnreadCount()
    notificationStore.fetchList({ reset: true })
  }
}

const onItemClick = (item) => {
  notificationStore.markRead(item.id)
  drawerOpen.value = false
  if (item.payload?.contest) {
    router.push(`/contests/${item.payload.contest}`)
  } else if (item.payload?.bank) {
    router.push(`/problems/${item.payload.bank}`)
  }
}

const markAll = () => {
  notificationStore.markAllRead()
}

const goNotificationPage = () => {
  drawerOpen.value = false
  router.push('/notifications')
}

const formatDate = (ts) => {
  if (!ts) return ''
  const d = new Date(ts)
  return d.toLocaleString()
}

onMounted(() => {
  if (isLoggedIn.value) {
    notificationStore.fetchUnreadCount()
    notificationStore.ensureSocket()
  }
})

watch(
  () => isLoggedIn.value,
  (val) => {
    if (val) {
      notificationStore.fetchUnreadCount()
      notificationStore.ensureSocket()
    } else {
      notificationStore.disconnect()
    }
  },
)
</script>

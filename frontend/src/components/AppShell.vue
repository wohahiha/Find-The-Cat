<template>
  <div :class="['min-h-screen', themeClass]">
    <header class="sticky top-0 z-30 border-b border-border-panel/80 bg-background-dark/85 backdrop-blur-md">
      <div class="max-w-6xl mx-auto flex h-14 items-center justify-between px-4 sm:px-6 lg:px-8">
        <div class="flex items-center gap-3">
          <div class="size-6 text-primary">
            <svg fill="none" viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
              <path
                d="M4 42.4379C4 42.4379 14.0962 36.0744 24 41.1692C35.0664 46.8624 44 42.2078 44 42.2078L44 7.01134C44 7.01134 35.068 11.6577 24.0031 5.96913C14.0971 0.876274 4 7.27094 4 42.4379Z"
                fill="currentColor"
              />
            </svg>
          </div>
          <RouterLink to="/" class="text-base font-bold text-text hover:text-primary">
            {{ brandName }}
          </RouterLink>
        </div>

        <nav class="hidden md:flex items-center gap-8 text-sm text-text">
          <RouterLink
            v-for="link in links"
            :key="link.to"
            :to="link.to"
            class="hover:text-primary"
            :class="isActive(link.to) ? 'text-primary font-semibold' : ''"
            @click.prevent="onNavClick(link, $event)"
          >
            {{ link.label }}
          </RouterLink>
        </nav>

        <div class="flex items-center gap-3">
          <NotificationBell />
          <RouterLink
            v-if="isLoggedIn"
            to="/profile"
            class="h-9 w-9 rounded-full border border-input-border block bg-center bg-cover bg-no-repeat"
            :style="{ backgroundImage: userAvatarStyle }"
            :title="user?.username || user?.email || 'Profile'"
          />
          <RouterLink
            v-else
            to="/login"
            class="flex h-9 min-w-[84px] items-center justify-center rounded-lg bg-primary px-4 text-sm font-bold text-primary-foreground hover:bg-primary/90"
          >
            登录
          </RouterLink>
        </div>
      </div>
    </header>

    <main>
      <slot />
    </main>
  </div>
</template>

<script setup>
import { computed, onMounted, watch } from 'vue'
import { useRoute, useRouter, RouterLink } from 'vue-router'
import { useConfigStore } from '@/stores/config'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import { useNotificationStore } from '@/stores/notifications'
import { NAV_LINKS } from '@/constants/navLinks'
import NotificationBell from '@/components/NotificationBell.vue'

const props = defineProps({
  theme: {
    type: String,
    default: 'blue', // 'blue' | 'green'
  },
})

const configStore = useConfigStore()
const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const toast = useToastStore()
const notificationStore = useNotificationStore()

const brandName = computed(() => configStore.brand || 'Find The Cat')
const user = computed(() => auth.user)

const resolveUrl = (url) => {
  if (!url) return ''
  const normalized = url.replace(/\\/g, '/')
  if (/^https?:\/\//i.test(normalized)) return normalized
  // 兼容后端头像为 /media/... 等相对路径的情况，优先使用后端基址，否则走 /api 代理前缀
  const backendBase = import.meta.env.VITE_BACKEND_URL || ''
  const apiPrefix = '/api'
  if (normalized.startsWith('/')) {
    const base = backendBase || apiPrefix
    return `${base.replace(/\/$/, '')}${normalized}`
  }
  try {
    return new URL(normalized, backendBase || window.location.origin).toString()
  } catch {
    return normalized
  }
}

const userAvatarStyle = computed(() => {
  const stored =
    typeof window !== 'undefined' && (localStorage.getItem('ftc_avatar') || sessionStorage.getItem('ftc_avatar'))
  const avatar = auth.user?.avatar || stored
  const fallback = 'linear-gradient(135deg,#2547f4,#1c2a5f)'
  return avatar ? `url(${resolveUrl(avatar)}), ${fallback}` : fallback
})

const links = NAV_LINKS

const isActive = (path) => {
  if (path === '/') return route.path === '/'
  return route.path.startsWith(path)
}

const themeClass = computed(() => (props.theme === 'green' ? 'theme-green' : ''))

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

const onNavClick = (link, event) => {
  if (link.requiresAuth && !isLoggedIn.value) {
    toast.error('请先登录后访问')
    event?.preventDefault()
    return
  }
  router.push(link.to)
  event?.preventDefault()
}

onMounted(() => {
  // 如果已有 token 但未拉取用户，补拉一遍，避免头像缺失
  if (!auth.user && hasToken()) {
    auth.fetchMe().then((u) => {
      if (u?.avatar) {
        try {
          localStorage.setItem('ftc_avatar', resolveUrl(u.avatar))
        } catch (e) {
          // ignore storage error
        }
      }
    }).catch(() => null)
  }
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

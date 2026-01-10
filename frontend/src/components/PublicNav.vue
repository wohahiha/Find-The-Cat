<template>
  <header class="relative z-20 border-b border-border-panel bg-background-dark/80 backdrop-blur-sm">
    <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 h-14 flex items-center justify-between">
      <div class="flex items-center gap-3">
        <div class="size-6 text-primary">
          <svg fill="none" viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
            <path
              d="M4 42.4379C4 42.4379 14.0962 36.0744 24 41.1692C35.0664 46.8624 44 42.2078 44 42.2078L44 7.01134C44 7.01134 35.068 11.6577 24.0031 5.96913C14.0971 0.876274 4 7.27094 4 42.4379Z"
              fill="currentColor"
            />
          </svg>
        </div>
        <RouterLink to="/" class="text-base font-bold text-text hover:text-primary">{{ brandName }}</RouterLink>
      </div>

      <nav class="hidden md:flex items-center gap-8 text-sm text-text">
        <button
          v-for="link in navLinks"
          :key="link.to"
          class="hover:text-text"
          :class="linkClass(link.to)"
          type="button"
          @click="onNavClick(link)"
        >
          {{ link.label }}
        </button>
      </nav>

      <div class="flex items-center gap-3">
        <NotificationBell />
        <template v-if="isAuthed">
          <RouterLink
            to="/profile"
            class="h-9 w-9 rounded-full border border-input-border block bg-center bg-cover bg-no-repeat"
            :style="{ backgroundImage: headerAvatar ? `url(${headerAvatar})` : 'linear-gradient(135deg,#2547f4,#1c2a5f)' }"
          ></RouterLink>
        </template>
        <div v-else class="flex items-center gap-2">
          <RouterLink
            class="flex h-9 min-w-[84px] cursor-pointer items-center justify-center overflow-hidden rounded-lg bg-border-panel px-4 text-sm font-bold text-text hover:bg-input-border"
            to="/login"
          >
            登录
          </RouterLink>
          <RouterLink
            class="hidden sm:flex h-9 min-w-[84px] cursor-pointer items-center justify-center overflow-hidden rounded-lg bg-primary px-4 text-sm font-bold text-primary-foreground hover:bg-primary/90"
            to="/register"
          >
            注册
          </RouterLink>
        </div>
      </div>
    </div>
  </header>
</template>

<script setup>
import { computed, ref, onMounted } from 'vue'
import { useRoute, useRouter, RouterLink } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useConfigStore } from '@/stores/config'
import { useToastStore } from '@/stores/toast'
import { NAV_LINKS } from '@/constants/navLinks'
import NotificationBell from '@/components/NotificationBell.vue'

const auth = useAuthStore()
const configStore = useConfigStore()
const toast = useToastStore()
const router = useRouter()
const route = useRoute()

const brandName = computed(() => configStore.brand || 'Find The Cat')
const navLinks = NAV_LINKS

const hasToken = () => {
  if (typeof window === 'undefined') return false
  return (
    !!auth.accessToken ||
    !!auth.refreshToken ||
    !!localStorage.getItem('ftc_access') ||
    !!sessionStorage.getItem('ftc_access')
  )
}
const isAuthed = computed(() => !!auth.user || hasToken())
const headerAvatar = ref('')

const resolveUrl = (url) => {
  if (!url) return ''
  const normalized = url.replace(/\\/g, '/')
  if (/^https?:\/\//i.test(normalized)) return normalized
  const base = import.meta.env.VITE_BACKEND_URL || window.location.origin
  try {
    return new URL(normalized, base).toString()
  } catch {
    return normalized
  }
}

const linkClass = (path) => {
  const active = route.path === path || route.path.startsWith(`${path}/`)
  return active ? 'font-semibold text-primary' : 'hover:text-text'
}

const onNavClick = (link) => {
  if (link.requiresAuth && !isAuthed.value) {
    toast.error('请先登录后访问')
    return
  }
  router.push(link.to)
}

onMounted(() => {
  // 优先使用已缓存的头像，避免额外请求
  const cachedAvatar = localStorage.getItem('ftc_avatar')
  const userAvatar = auth.user?.avatar
  headerAvatar.value = resolveUrl(userAvatar || cachedAvatar || '')
})
</script>

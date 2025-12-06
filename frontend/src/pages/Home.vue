<template>
  <div class="dark">
    <div class="relative min-h-screen bg-background-dark text-text">
      <div class="absolute inset-0">
        <div class="absolute inset-0 bg-background-dark"></div>
        <div class="absolute inset-0 bg-[radial-gradient(circle_at_center,_rgba(42,50,113,0.35),_transparent_45%)]"></div>
      </div>

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
            <router-link to="/" class="text-base font-bold text-text hover:text-primary">{{ brandName }}</router-link>
          </div>
          <nav class="hidden md:flex items-center gap-8 text-sm text-text">
            <router-link class="hover:text-text" to="/contests">比赛</router-link>
            <router-link class="hover:text-text" to="/problems">题库</router-link>
            <router-link class="hover:text-text" to="/profile">个人资料</router-link>
          </nav>
          <div class="flex items-center gap-3">
            <button class="flex h-9 w-9 items-center justify-center rounded-lg bg-border-panel text-muted hover:text-text hover:bg-input-border">
              <span class="material-symbols-outlined text-lg">notifications</span>
            </button>
            <router-link
              v-if="isAuthed"
              to="/profile"
              class="h-9 w-9 rounded-full border border-input-border block bg-center bg-cover bg-no-repeat"
              :style="{ backgroundImage: headerAvatar ? `url(${headerAvatar})` : 'linear-gradient(135deg,#2547f4,#1c2a5f)' }"
            ></router-link>
            <div v-else class="flex items-center gap-2">
              <router-link
                class="flex h-9 min-w-[84px] cursor-pointer items-center justify-center overflow-hidden rounded-lg bg-border-panel px-4 text-sm font-bold text-text hover:bg-input-border"
                to="/login"
              >
                登录
              </router-link>
              <router-link
                class="hidden sm:flex h-9 min-w-[84px] cursor-pointer items-center justify-center overflow-hidden rounded-lg bg-primary px-4 text-sm font-bold text-primary-foreground hover:bg-primary/90"
                to="/register"
              >
                注册
              </router-link>
            </div>
          </div>
        </div>
      </header>

      <main class="relative z-10 max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-14">
        <!-- Hero -->
        <section class="rounded-xl border border-border-panel bg-panel shadow-panel overflow-hidden">
          <div class="relative isolate px-6 py-12 sm:px-10 sm:py-14">
            <div class="absolute inset-0 bg-[radial-gradient(circle_at_20%_20%,rgba(37,71,244,0.18),transparent_35%),radial-gradient(circle_at_80%_10%,rgba(37,71,244,0.12),transparent_40%)]"></div>
            <div class="relative flex flex-col gap-4 sm:gap-6">
              <p class="text-sm font-semibold text-primary">{{ brandName }}</p>
              <h1 class="text-4xl sm:text-5xl font-bold leading-tight tracking-tight">专注网络安全的 CTF 平台</h1>
              <p class="max-w-2xl text-base text-muted sm:text-lg">
                参与比赛、刷题训练、查看公告与排期。
              </p>
              <div class="flex flex-wrap gap-3">
                <router-link
                  to="/contests"
                  class="flex h-12 min-w-[120px] cursor-pointer items-center justify-center rounded-lg bg-primary px-5 text-base font-bold text-primary-foreground hover:bg-primary/90"
                >
                  查看比赛
                </router-link>
                <router-link
                  to="/problems"
                  class="flex h-12 min-w-[120px] cursor-pointer items-center justify-center rounded-lg bg-border-panel px-5 text-base font-bold text-text hover:bg-input-border"
                >
                  进入题库
                </router-link>
              </div>
            </div>
          </div>
        </section>

        <!-- Announcements without images -->
        <section class="space-y-6">
          <div class="flex items-center justify-between">
            <h2 class="text-2xl sm:text-3xl font-bold tracking-tight">平台公告</h2>
            <router-link class="text-sm text-primary hover:underline" to="/announcements">更多</router-link>
          </div>
          <div class="grid grid-cols-1 gap-4 sm:gap-6">
            <article
              v-for="(item, idx) in announcements"
              :key="idx"
              class="rounded-xl border border-border-panel bg-panel/80 p-4 sm:p-5 shadow-panel"
            >
              <div class="flex items-start gap-3">
                <div class="flex h-10 w-10 items-center justify-center rounded-full bg-primary/15 text-primary">
                  <span class="material-symbols-outlined">campaign</span>
                </div>
                <div class="flex-1 space-y-2">
                  <div class="flex flex-wrap items-center gap-2 justify-between">
                    <p class="text-lg font-bold">{{ item.title }}</p>
                    <span class="text-xs text-muted">{{ item.time }}</span>
                  </div>
                  <p class="text-sm text-muted leading-relaxed">{{ item.summary }}</p>
                </div>
              </div>
            </article>
          </div>
        </section>

        <!-- Competitions -->
        <section class="space-y-6">
          <h2 class="text-2xl sm:text-3xl font-bold tracking-tight">进行中 / 即将开始的比赛</h2>
          <div class="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
            <div
              v-for="(contest, idx) in contests"
              :key="idx"
              class="flex flex-col rounded-xl border border-border-panel bg-panel/90 p-5 shadow-panel"
            >
              <div class="mb-3 flex items-center justify-between">
                <h3 class="text-lg font-bold">{{ contest.name }}</h3>
                <span
                  class="inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold"
                  :class="statusClass(contest.status)"
                >
                  {{ contest.statusLabel }}
                </span>
              </div>
              <p class="mb-4 text-sm text-muted leading-relaxed">{{ contest.description }}</p>
              <div class="mb-4 text-xs text-muted space-y-1">
                <p><strong>开始:</strong> {{ contest.start }}</p>
                <p><strong>结束:</strong> {{ contest.end }}</p>
              </div>
              <div class="mt-auto">
                <button
                  class="flex h-10 w-full cursor-pointer items-center justify-center overflow-hidden rounded-lg"
                  :class="contest.primary ? 'bg-primary text-primary-foreground hover:bg-primary/90' : 'bg-border-panel text-text hover:bg-input-border'"
                  type="button"
                >
                  {{ contest.action }}
                </button>
              </div>
            </div>
          </div>
        </section>
      </main>

      <footer class="relative z-10 flex justify-center border-t border-border-panel px-4 py-6 sm:px-6 lg:px-8">
        <div class="flex w-full max-w-6xl flex-col items-center justify-between gap-4 text-center sm:flex-row sm:text-left">
          <p class="text-sm text-muted">© 2025 {{ brandName }}</p>
          <div class="flex gap-4 text-sm text-muted">
            <a class="hover:text-text" href="#">隐私政策</a>
            <a class="hover:text-text" href="#">服务条款</a>
            <a class="hover:text-text" href="#">联系我们</a>
          </div>
        </div>
      </footer>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import api from '@/api/client'
import { useConfigStore } from '@/stores/config'

const auth = useAuthStore()
const headerAvatar = ref('')
const configStore = useConfigStore()
const brandName = computed(() => configStore.brand || 'Find The Cat')

const isAuthed = computed(() => !!(auth.accessToken || sessionStorage.getItem('ftc_access') || localStorage.getItem('ftc_access')))

const announcements = [
  { title: '平台升级维护', summary: '本周末将进行基础设施升级，预计 2 小时内完成。请提前提交关键任务。', time: '3 小时前' },
  { title: '新增题库挑战', summary: '上线 5 道最新 Web & Pwn 挑战，欢迎尝试并提交你的 flag。', time: '1 天前' },
]

const contests = [
  {
    name: '冬季攻防赛',
    status: 'live',
    statusLabel: '进行中',
    description: '综合考察 Web/Reverse/Pwn/Forensics，多人协作，实时计分。',
    start: '2025-12-10 10:00 UTC',
    end: '2025-12-12 10:00 UTC',
    primary: true,
    action: '进入比赛',
  },
  {
    name: '新手入门赛',
    status: 'upcoming',
    statusLabel: '即将开始',
    description: '适合新手的入门赛，覆盖基础安全知识与简单漏洞利用。',
    start: '2025-12-20 09:00 UTC',
    end: '2025-12-21 09:00 UTC',
    primary: false,
    action: '查看详情',
  },
  {
    name: '秋季月赛',
    status: 'ended',
    statusLabel: '已结束',
    description: '本月月赛已结束，可查看榜单与题解，复盘提升。',
    start: '2025-11-15 08:00 UTC',
    end: '2025-11-17 08:00 UTC',
    primary: false,
    action: '查看榜单',
  },
]

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

const statusClass = (status) => {
  if (status === 'live') return 'bg-green-500/20 text-green-300'
  if (status === 'upcoming') return 'bg-blue-500/20 text-blue-300'
  return 'bg-border-panel text-muted'
}

onMounted(() => {
  const existingAvatar = auth.user?.avatar
  if (existingAvatar) {
    headerAvatar.value = resolveUrl(existingAvatar)
  }
  api
    .get('/accounts/me/')
    .then((res) => {
      const data = res.data?.data?.user || res.data?.user || {}
      if (data.avatar) {
        headerAvatar.value = resolveUrl(data.avatar)
      }
    })
    .catch(() => {})
})
</script>

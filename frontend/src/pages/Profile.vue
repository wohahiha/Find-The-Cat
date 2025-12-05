<template>
  <div class="dark">
    <div class="relative min-h-screen bg-background-dark text-text">
      <div class="absolute inset-0">
        <div class="absolute inset-0 bg-background-dark"></div>
        <div class="absolute inset-0 bg-[radial-gradient(circle_at_center,_rgba(42,50,113,0.35),_transparent_45%)]"></div>
      </div>

      <!-- 顶部导航，贴合模板 -->
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
            <router-link to="/" class="text-base font-bold text-text hover:text-primary">Find The Cat</router-link>
          </div>
          <nav class="hidden md:flex items-center gap-8 text-sm text-text">
            <router-link class="hover:text-text" to="/">仪表盘</router-link>
            <router-link class="hover:text-text" to="/contests">比赛</router-link>
            <router-link class="hover:text-text" to="/problems">题库</router-link>
            <router-link class="hover:text-text" to="/profile">个人资料</router-link>
          </nav>
          <div class="flex items-center gap-3">
            <button class="flex h-9 w-9 items-center justify-center rounded-lg bg-border-panel text-muted hover:text-text hover:bg-input-border">
              <span class="material-symbols-outlined text-lg">notifications</span>
            </button>
            <router-link
              to="/profile"
              class="h-9 w-9 rounded-full border border-input-border block bg-center bg-cover bg-no-repeat"
              :style="{ backgroundImage: headerAvatar ? `url(${headerAvatar})` : 'linear-gradient(135deg,#2547f4,#1c2a5f)' }"
            ></router-link>
          </div>
        </div>
      </header>

      <div class="relative z-10 max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <header class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between mb-4">
          <div>
            <h1 class="text-3xl sm:text-4xl font-bold leading-tight tracking-tight text-text">个人资料</h1>
          </div>
          <div class="flex flex-wrap gap-3">
            <router-link
              class="flex h-10 items-center justify-center rounded-lg border border-input-border px-3 text-sm font-bold text-text hover:border-primary hover:text-primary transition-colors"
              to="/change-password"
            >
              修改密码
            </router-link>
            <button
              class="flex h-10 items-center justify-center rounded-lg bg-border-panel px-3 text-sm font-bold text-text hover:bg-input-border transition-colors"
              type="button"
              @click="logout"
            >
              退出登录
            </button>
          </div>
        </header>

        <p class="text-muted mb-6">查看并更新你的账户信息。资料保存后，部分信息可能需要重新登录才会在其他页面生效。</p>

        <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <section class="lg:col-span-2 rounded-xl bg-panel border border-border-panel shadow-panel p-6 sm:p-7 space-y-6">
            <div class="flex items-start gap-4 pb-4 border-b border-border-panel/60">
              <div class="flex flex-col items-center gap-2">
                <div class="flex items-center gap-2">
                  <button
                    class="flex flex-col items-center justify-center rounded bg-primary text-primary-foreground text-[11px] px-2 py-1.5 shadow-panel hover:bg-primary/90 leading-tight min-h-[44px] gap-1"
                    type="button"
                    @click="pickAvatar"
                    :disabled="uploadingAvatar"
                    aria-label="更换头像"
                  >
                    <span class="leading-none">更</span>
                    <span class="leading-none">换</span>
                  </button>
                  <button
                    class="bg-center bg-no-repeat aspect-square bg-cover rounded-full size-16 border border-input-border"
                    :style="{ backgroundImage: profile.avatar ? `url(${profile.avatar})` : 'linear-gradient(135deg,#2547f4,#1c2a5f)' }"
                    type="button"
                    @click="openAvatar"
                  ></button>
                </div>
                <input
                  ref="avatarInput"
                  class="hidden"
                  type="file"
                  accept="image/png,image/jpeg,image/jpg,image/webp"
                  @change="onAvatarChange"
                />
              </div>
              <div class="flex flex-col gap-2 py-0.5">
                <p class="text-2xl font-bold leading-tight">{{ profile.username || '未登录' }}</p>
                <p class="text-lg text-muted leading-tight">邮箱：{{ profile.email || '未绑定' }}</p>
              </div>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
              <label class="flex flex-col gap-2">
                <span class="text-sm font-medium">昵称</span>
                <div class="relative flex items-center">
                  <span class="material-symbols-outlined absolute left-3 text-muted text-lg">badge</span>
                  <input
                    v-model="profile.nickname"
                    class="form-input w-full rounded-lg border bg-input text-text placeholder:text-muted h-12 pl-10 pr-4 text-base focus:outline-0 focus:ring-2 focus:ring-primary/50 focus:border-primary border-input-border"
                    placeholder="填写昵称"
                    type="text"
                  />
                </div>
              </label>
              <label class="flex flex-col gap-2">
                <span class="text-sm font-medium">组织/学校</span>
                <div class="relative flex items-center">
                  <span class="material-symbols-outlined absolute left-3 text-muted text-lg">work</span>
                  <input
                    v-model="profile.organization"
                    class="form-input w-full rounded-lg border bg-input text-text placeholder:text-muted h-12 pl-10 pr-4 text-base focus:outline-0 focus:ring-2 focus:ring-primary/50 focus:border-primary border-input-border"
                    placeholder="所属团队或学校"
                    type="text"
                  />
                </div>
              </label>
              <label class="flex flex-col gap-2">
                <span class="text-sm font-medium">国家/地区</span>
                <div class="relative flex items-center">
                  <span class="material-symbols-outlined absolute left-3 text-muted text-lg">public</span>
                  <input
                    v-model="profile.country"
                    class="form-input w-full rounded-lg border bg-input text-text placeholder:text-muted h-12 pl-10 pr-4 text-base focus:outline-0 focus:ring-2 focus:ring-primary/50 focus:border-primary border-input-border"
                    placeholder="如 China / USA"
                    type="text"
                  />
                </div>
              </label>
              <label class="flex flex-col gap-2">
                <span class="text-sm font-medium">个人站点</span>
                <div class="relative flex items-center">
                  <span class="material-symbols-outlined absolute left-3 text-muted text-lg">link</span>
                  <input
                    v-model="profile.website"
                    class="form-input w-full rounded-lg border bg-input text-text placeholder:text-muted h-12 pl-10 pr-4 text-base focus:outline-0 focus:ring-2 focus:ring-primary/50 focus:border-primary border-input-border"
                    placeholder="https://example.com"
                    type="url"
                  />
                </div>
              </label>
            </div>

            <label class="flex flex-col gap-2">
              <span class="text-sm font-medium">个性签名</span>
              <textarea
                v-model="profile.bio"
                rows="4"
                class="form-textarea w-full rounded-lg border bg-input text-text placeholder:text-muted p-4 text-base focus:outline-0 focus:ring-2 focus:ring-primary/50 focus:border-primary border-input-border"
                placeholder="写点什么，展示你的风格……"
              ></textarea>
            </label>

            <div class="flex flex-col gap-2">
              <button
                class="flex w-full sm:w-auto cursor-pointer items-center justify-center overflow-hidden rounded-lg h-12 px-6 bg-primary text-primary-foreground text-base font-bold leading-normal tracking-[0.015em] hover:bg-primary/90 transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
                type="button"
                :disabled="saving || loading"
                @click="saveProfile"
              >
                <span class="truncate">{{ saving ? '保存中…' : '保存修改' }}</span>
              </button>
              <p v-if="error" class="text-sm text-danger">{{ error }}</p>
              <p v-if="success" class="text-sm text-primary">{{ success }}</p>
            </div>
          </section>

          <aside class="rounded-xl bg-panel border border-border-panel shadow-panel p-6 space-y-5">
            <div class="flex items-center justify-between">
              <p class="text-base font-bold text-text">邮箱状态</p>
              <span
                class="inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-semibold"
                :class="profile.is_email_verified ? 'bg-green-500/10 text-green-300' : 'bg-border-panel text-muted'"
              >
                <span class="material-symbols-outlined text-sm">{{ profile.is_email_verified ? 'verified' : 'error' }}</span>
                {{ profile.is_email_verified ? '已验证' : '未验证' }}
              </span>
            </div>

            <div class="space-y-2 text-sm text-muted">
              <p v-if="profile.is_email_verified">邮箱已验证，如需更换邮箱，请先修改邮箱或联系管理员。</p>
              <p v-else>若邮箱未验证，可发送验证邮件完成绑定。</p>
            </div>

            <button
              v-if="!profile.is_email_verified"
              class="flex w-full cursor-pointer items-center justify-center overflow-hidden rounded-lg h-11 px-4 bg-border-panel text-text text-sm font-bold leading-normal tracking-[0.01em] hover:bg-input-border transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
              type="button"
              :disabled="sendingEmail || countdown > 0 || !profile.email"
              @click="sendVerifyEmail"
            >
              <span v-if="countdown === 0">{{ sendingEmail ? '发送中…' : '发送验证邮件' }}</span>
              <span v-else>{{ countdown }} 秒后可重发</span>
            </button>
            <p v-else class="text-sm text-text">绑定邮箱：{{ profile.email || '-' }}</p>

            <div class="pt-2 border-t border-border-panel/70 space-y-2 text-sm text-muted">
              <p>保存后部分信息可能需要重新登录才能在其他页面生效。</p>
              <router-link class="text-primary font-bold hover:underline" to="/change-password">需要重置密码？</router-link>
            </div>
          </aside>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, reactive, ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import api from '@/api/client'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()

const profile = reactive({
  username: '',
  email: '',
  nickname: '',
  organization: '',
  country: '',
  website: '',
  bio: '',
  avatar: '',
  is_email_verified: false,
})

const initialProfile = ref({})
const loading = ref(true)
const saving = ref(false)
const error = ref('')
const success = ref('')
const sendingEmail = ref(false)
const countdown = ref(0)
let timer = null
const avatarInput = ref(null)
const uploadingAvatar = ref(false)
const resolveUrl = (url) => {
  if (!url) return ''
  const normalized = url.replace(/\\/g, '/')
  if (/^https?:\/\//i.test(normalized)) return normalized
  const base = import.meta.env.VITE_BACKEND_URL || window.location.origin
  try {
    return new URL(normalized, base).toString()
  } catch (e) {
    return normalized
  }
}

const loadProfile = async () => {
  loading.value = true
  error.value = ''
  try {
    const res = await api.get('/accounts/me/')
    const data = res.data?.data?.user || res.data?.user || {}
    profile.username = data.username || ''
    profile.email = data.email || ''
    profile.nickname = data.nickname || ''
    profile.organization = data.organization || ''
    profile.country = data.country || ''
    profile.website = data.website || ''
    profile.bio = data.bio || ''
    profile.avatar = resolveUrl(data.avatar || '')
    profile.is_email_verified = !!data.is_email_verified
    initialProfile.value = { ...profile }
    auth.user = data
  } catch (e) {
    error.value = e?.response?.data?.message || '获取资料失败，请稍后重试'
    if (e?.response?.status === 401) {
      router.replace('/login')
    }
  } finally {
    loading.value = false
  }
}

const hasChanges = () => {
  const fields = ['nickname', 'organization', 'country', 'website', 'bio']
  return fields.some((key) => (profile[key] || '') !== (initialProfile.value[key] || ''))
}

const saveProfile = async () => {
  error.value = ''
  success.value = ''
  if (!hasChanges()) {
    error.value = '没有需要更新的内容'
    return
  }

  const payload = {
    nickname: profile.nickname,
    organization: profile.organization,
    country: profile.country,
    website: profile.website,
    bio: profile.bio,
  }

  saving.value = true
  try {
    const res = await api.patch('/accounts/me/', payload)
    success.value = res.data?.message || '已保存'
    initialProfile.value = { ...initialProfile.value, ...payload }
  } catch (e) {
    error.value = e?.response?.data?.message || '保存失败，请稍后再试'
  } finally {
    saving.value = false
  }
}

const sendVerifyEmail = async () => {
  if (!profile.email) {
    error.value = '请先绑定邮箱'
    return
  }
  sendingEmail.value = true
  error.value = ''
  success.value = ''
  try {
    const res = await api.post('/accounts/email/verification/', {
      email: profile.email,
      scene: 'bind_email',
    })
    success.value = res.data?.message || '验证邮件已发送'
    countdown.value = 60
    timer = setInterval(() => {
      countdown.value -= 1
      if (countdown.value <= 0 && timer) {
        clearInterval(timer)
        timer = null
      }
    }, 1000)
  } catch (e) {
    error.value = e?.response?.data?.message || '发送失败，请稍后重试'
  } finally {
    sendingEmail.value = false
  }
}

const logout = () => {
  auth.logout()
  router.replace('/login')
}

const headerAvatar = computed(() => resolveUrl(profile.avatar || auth.user?.avatar || ''))

const pickAvatar = () => {
  if (!avatarInput.value) return
  avatarInput.value.value = ''
  avatarInput.value.click()
}

const onAvatarChange = async (e) => {
  const file = e?.target?.files?.[0]
  if (!file) return
  error.value = ''
  success.value = ''
  const maxSize = 5 * 1024 * 1024 // 5MB
  const allowed = ['image/png', 'image/jpeg', 'image/jpg', 'image/webp']
  if (!allowed.includes(file.type)) {
    error.value = '仅支持 PNG / JPG / WEBP 格式'
    return
  }
  if (file.size > maxSize) {
    error.value = '图片大小需小于 5MB'
    return
  }
  uploadingAvatar.value = true
  try {
    const formData = new FormData()
    formData.append('avatar', file)
    const res = await api.post('/accounts/me/avatar/', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    const url = res.data?.data?.avatar || res.data?.avatar || ''
    const resolved = resolveUrl(url)
    if (resolved) {
      profile.avatar = resolved
      if (auth.user) auth.user.avatar = resolved
      success.value = res.data?.message || '头像已更新'
    } else {
      success.value = res.data?.message || '上传成功'
    }
  } catch (err) {
    error.value = err?.response?.data?.message || '头像上传失败'
  } finally {
    uploadingAvatar.value = false
  }
}

const openAvatar = () => {
  if (profile.avatar) {
    window.open(profile.avatar, '_blank')
  }
}

onMounted(() => {
  // 如果完全没有 token，直接跳转登录
  if (!auth.accessToken && !sessionStorage.getItem('ftc_access') && !localStorage.getItem('ftc_access')) {
    router.replace('/login')
    return
  }
  loadProfile()
})

onBeforeUnmount(() => {
  if (timer) clearInterval(timer)
})
</script>

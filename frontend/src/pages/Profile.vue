<template>
  <AppShell>
    <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div v-if="loading" class="flex justify-center py-12">
        <LoadingSpinner>加载资料中…</LoadingSpinner>
      </div>
      <ErrorState
        v-else-if="error"
        :message="error"
        retry-label="重试"
        @retry="loadProfile"
      />
      <template v-else>
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
      </template>
    </div>
  </AppShell>
</template>

<script setup>
  import { onBeforeUnmount, onMounted, reactive, ref } from 'vue'
  import { useRouter } from 'vue-router'
  import api from '@/api/client'
  import { useAuthStore } from '@/stores/auth'
  import { parseApiError } from '@/api/errors'
  import { useToastStore } from '@/stores/toast'
  import { LoadingSpinner, ErrorState } from '@/components/ui'
  import AppShell from '@/components/AppShell.vue'

  const router = useRouter()
  const auth = useAuthStore()
  const toast = useToastStore()

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
const hasToken = () => {
  if (typeof window === 'undefined') return false
  return (
    !!auth.accessToken ||
    !!auth.refreshToken ||
    !!localStorage.getItem('ftc_access') ||
    !!sessionStorage.getItem('ftc_access')
  )
}
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
    error.value = parseApiError(e, '获取资料失败，请稍后重试')
    toast.error(error.value)
    if (e?.response?.status === 401) {
      auth.logout()
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
    toast.success(success.value)
  } catch (e) {
    error.value = parseApiError(e, '保存失败，请稍后再试')
    toast.error(error.value)
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
    toast.success(success.value)
    countdown.value = 60
    timer = setInterval(() => {
      countdown.value -= 1
      if (countdown.value <= 0 && timer) {
        clearInterval(timer)
        timer = null
      }
    }, 1000)
  } catch (e) {
    error.value = parseApiError(e, '发送失败，请稍后重试')
    countdown.value = 0
    if (timer) {
      clearInterval(timer)
      timer = null
    }
    toast.error(error.value)
  } finally {
    sendingEmail.value = false
  }
}

const logout = () => {
  auth.logout()
  router.replace('/login')
}

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
      toast.success(success.value)
    } else {
      success.value = res.data?.message || '上传成功'
      toast.success(success.value)
    }
  } catch (err) {
    error.value = parseApiError(err, '头像上传失败')
    toast.error(error.value)
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
  if (!hasToken()) {
    error.value = '请先登录后访问'
    loading.value = false
    toast.error(error.value)
    return
  }
  loadProfile()
})

onBeforeUnmount(() => {
  if (timer) clearInterval(timer)
})
</script>

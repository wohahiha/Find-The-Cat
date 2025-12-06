<template>
  <div class="dark">
    <div class="relative min-h-screen bg-background-dark text-text">
      <div class="absolute inset-0">
        <div class="absolute inset-0 bg-background-dark"></div>
        <div class="absolute inset-0 bg-[radial-gradient(circle_at_center,_rgba(42,50,113,0.35),_transparent_40%)]"></div>
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
            <router-link to="/" class="text-base font-bold text-text hover:text-primary">{{ brandName }}</router-link>
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

      <div class="relative z-10 max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-10 flex flex-col items-center gap-6">
        <div class="text-center space-y-2">
          <h1 class="text-3xl sm:text-4xl font-bold leading-tight text-text">修改密码</h1>
          <p class="text-sm text-muted">为了您的账户安全，请不要将您的密码分享给其他人</p>
        </div>

        <div class="w-full rounded-xl bg-panel border border-border-panel shadow-panel p-6 sm:p-8">
          <form class="grid grid-cols-1 lg:grid-cols-2 gap-6" @submit.prevent="submit">
            <div class="lg:col-span-2 flex flex-col gap-2">
              <label class="text-sm font-medium leading-normal" for="email">邮箱</label>
              <div class="relative flex items-center">
                <span class="material-symbols-outlined absolute left-4 text-muted text-xl">mail</span>
                <input
                  v-model="email"
                  disabled
                  class="form-input flex w-full min-w-0 flex-1 resize-none overflow-hidden rounded-lg text-text focus:outline-0 focus:ring-2 border bg-input h-12 placeholder:text-muted pl-12 pr-4 text-base font-normal leading-normal border-input-border"
                  id="email"
                  placeholder="未绑定邮箱"
                  type="email"
                />
              </div>
          <p class="text-xs text-muted">将通过邮箱验证码确认本次修改</p>
            </div>

            <div class="lg:col-span-2 flex flex-col gap-2">
              <label class="text-sm font-medium leading-normal" for="old-password">当前密码</label>
              <div class="relative flex items-center">
                <span class="material-symbols-outlined absolute left-4 text-muted text-xl">lock</span>
                <input
                  v-model="form.old_password"
                  class="form-input flex w-full min-w-0 flex-1 resize-none overflow-hidden rounded-lg text-text focus:outline-0 focus:ring-2 border bg-input h-12 placeholder:text-muted pl-12 pr-12 text-base font-normal leading-normal"
                  :class="oldError ? 'border-danger focus:border-danger focus:ring-danger/40' : 'border-input-border focus:ring-primary/50 focus:border-primary'"
                  id="old-password"
                  placeholder="请输入当前密码"
                  :type="showOld ? 'text' : 'password'"
                />
                <button
                  aria-label="Toggle old password visibility"
                  class="absolute right-0 flex h-full items-center justify-center px-4 text-muted hover:text-text"
                  type="button"
                  @click="showOld = !showOld"
                >
                  <span class="material-symbols-outlined text-xl">{{ showOld ? 'visibility_off' : 'visibility' }}</span>
                </button>
              </div>
              <p v-if="oldError" class="text-xs text-danger">请检查当前密码</p>
            </div>

            <div class="flex flex-col gap-2">
              <label class="text-sm font-medium leading-normal" for="new-password">新密码</label>
              <div class="relative flex items-center">
                <span class="material-symbols-outlined absolute left-4 text-muted text-xl">lock_open</span>
                <input
                  v-model="form.new_password"
                  class="form-input flex w-full min-w-0 flex-1 resize-none overflow-hidden rounded-lg text-text focus:outline-0 focus:ring-2 border bg-input h-12 placeholder:text-muted pl-12 pr-12 text-base font-normal leading-normal"
                  :class="newError ? 'border-danger focus:border-danger focus:ring-danger/40' : 'border-input-border focus:ring-primary/50 focus:border-primary'"
                  id="new-password"
                  placeholder="请输入新密码"
                  :type="showNew ? 'text' : 'password'"
                />
                <button
                  aria-label="Toggle new password visibility"
                  class="absolute right-0 flex h-full items-center justify-center px-4 text-muted hover:text-text"
                  type="button"
                  @click="showNew = !showNew"
                >
                  <span class="material-symbols-outlined text-xl">{{ showNew ? 'visibility_off' : 'visibility' }}</span>
                </button>
              </div>
              <p class="text-xs" :class="newError ? 'text-danger' : 'text-emerald-300'">8-64 位，需同时包含字母和数字</p>
            </div>

            <div class="flex flex-col gap-2">
              <label class="text-sm font-medium leading-normal" for="confirm-password">确认新密码</label>
              <div class="relative flex items-center">
                <span class="material-symbols-outlined absolute left-4 text-muted text-xl">verified_user</span>
                <input
                  v-model="form.confirm_password"
                  class="form-input flex w-full min-w-0 flex-1 resize-none overflow-hidden rounded-lg text-text focus:outline-0 focus:ring-2 border bg-input h-12 placeholder:text-muted pl-12 pr-12 text-base font-normal leading-normal"
                  :class="confirmError ? 'border-danger focus:border-danger focus:ring-danger/40' : 'border-input-border focus:ring-primary/50 focus:border-primary'"
                  id="confirm-password"
                  placeholder="请再次输入新密码"
                  :type="showConfirm ? 'text' : 'password'"
                />
                <button
                  aria-label="Toggle confirm password visibility"
                  class="absolute right-0 flex h-full items-center justify-center px-4 text-muted hover:text-text"
                  type="button"
                  @click="showConfirm = !showConfirm"
                >
                  <span class="material-symbols-outlined text-xl">{{ showConfirm ? 'visibility_off' : 'visibility' }}</span>
                </button>
              </div>
              <p v-if="confirmError" class="text-xs text-danger">两次输入的密码不一致</p>
            </div>

            <div class="lg:col-span-2 flex flex-col gap-2">
              <label class="text-sm font-medium leading-normal" for="email-code">邮箱验证码</label>
              <div class="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-3">
                <input
                  v-model="emailCode"
                  class="form-input flex w-full min-w-0 flex-1 resize-none overflow-hidden rounded-lg text-text focus:outline-0 focus:ring-2 border bg-input h-12 placeholder:text-muted px-4 text-base font-normal leading-normal"
                  :class="codeError ? 'border-danger focus:border-danger focus:ring-danger/40' : 'border-input-border focus:ring-primary/50 focus:border-primary'"
                  id="email-code"
                  placeholder="请输入邮箱验证码"
                  type="text"
                />
                <button
                  class="flex h-12 cursor-pointer items-center justify-center overflow-hidden rounded-lg bg-border-panel px-4 text-sm font-bold leading-normal text-text tracking-[0.015em] whitespace-nowrap hover:bg-input-border transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
                  type="button"
                  :disabled="sendingCode || countdown > 0 || !email"
                  @click="sendCode"
                >
                  <span class="truncate" v-if="countdown === 0">{{ sendingCode ? '发送中…' : '发送验证码' }}</span>
                  <span v-else class="truncate">{{ countdown }} 秒后可重发</span>
                </button>
              </div>
              <p v-if="codeError" class="text-xs text-danger">请填写邮箱验证码</p>
            </div>

            <div class="lg:col-span-2 flex flex-col gap-3 pt-2 text-center w-full">
              <button
                class="flex w-full cursor-pointer items-center justify-center overflow-hidden rounded-lg h-12 px-4 bg-primary text-primary-foreground text-base font-bold leading-normal tracking-[0.015em] hover:bg-primary/90 transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
                type="submit"
                :disabled="submitting"
              >
                <span class="truncate">{{ submitting ? '保存中…' : '更新密码' }}</span>
              </button>
              <p v-if="error" class="text-sm text-danger font-semibold">{{ error }}</p>
              <p v-if="success" class="text-sm text-emerald-400 font-semibold">{{ success }}</p>
              <p class="text-sm text-muted">
                <router-link class="font-bold text-primary hover:underline" to="/forgot-password">忘记当前密码？</router-link>
              </p>
            </div>
          </form>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
  import { computed, reactive, ref, onMounted, onBeforeUnmount } from 'vue'
  import { useRouter } from 'vue-router'
  import api from '@/api/client'
  import { useAuthStore } from '@/stores/auth'
  import { useConfigStore } from '@/stores/config'

  const router = useRouter()
  const auth = useAuthStore()
  const configStore = useConfigStore()
  const brandName = computed(() => configStore.brand || 'Find The Cat')

const form = reactive({
  old_password: '',
  new_password: '',
  confirm_password: '',
})
const email = ref('')
const emailCode = ref('')
const codeError = ref(false)
const sendingCode = ref(false)
const countdown = ref(0)
let timer = null

const showOld = ref(false)
const showNew = ref(false)
const showConfirm = ref(false)
const submitting = ref(false)
const error = ref('')
const success = ref('')
const oldError = ref(false)
const newError = ref(false)
const confirmError = ref(false)
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

const validatePassword = (pwd) => {
  if (!pwd || pwd.length < 8 || pwd.length > 64) return '密码长度需在 8-64 位之间'
  const hasLetter = /[A-Za-z]/.test(pwd)
  const hasDigit = /\d/.test(pwd)
  if (!(hasLetter && hasDigit)) return '密码需同时包含字母和数字'
  return ''
}

const submit = async () => {
  error.value = ''
  success.value = ''
  oldError.value = false
  newError.value = false
  confirmError.value = false
  codeError.value = false

  if (!form.old_password || !form.new_password || !form.confirm_password || !emailCode.value) {
    if (!form.old_password) oldError.value = true
    if (!form.new_password) newError.value = true
    if (!form.confirm_password) confirmError.value = true
    if (!emailCode.value) codeError.value = true
    error.value = '请填写所有字段'
    return
  }
  const pwdValidation = validatePassword(form.new_password)
  if (pwdValidation) {
    newError.value = true
    error.value = pwdValidation
    return
  }
  if (form.new_password !== form.confirm_password) {
    confirmError.value = true
    error.value = '两次输入的密码不一致'
    return
  }

  submitting.value = true
  try {
    const res = await api.post('/accounts/password/change/', {
      old_password: form.old_password,
      new_password: form.new_password,
      confirm_password: form.confirm_password,
      email_code: emailCode.value,
    })
    success.value = res.data?.message || '密码更新成功，请使用新密码登录'
    // 可选：更新后要求重新登录
    auth.logout()
    setTimeout(() => {
      router.push('/login')
    }, 400)
  } catch (e) {
    error.value = e?.response?.data?.message || '修改失败，请稍后重试'
    const code = e?.response?.data?.code
    if (code === 40101 || code === 40002) {
      oldError.value = true
      newError.value = true
      confirmError.value = true
    }
  } finally {
    submitting.value = false
  }
}

onMounted(() => {
  if (!auth.accessToken && !sessionStorage.getItem('ftc_access') && !localStorage.getItem('ftc_access')) {
    router.replace('/login')
    return
  }
  const existingAvatar = auth.user?.avatar
  if (existingAvatar) {
    headerAvatar.value = resolveUrl(existingAvatar)
  }
  api
    .get('/accounts/me/')
    .then((res) => {
      const data = res.data?.data?.user || res.data?.user || {}
      email.value = data.email || ''
      if (data.avatar) {
        headerAvatar.value = resolveUrl(data.avatar)
      }
    })
    .catch(() => {})
})

const sendCode = async () => {
  error.value = ''
  success.value = ''
  codeError.value = false
  if (!email.value) {
    codeError.value = true
    error.value = '请先绑定邮箱'
    return
  }
  sendingCode.value = true
  try {
    const res = await api.post('/accounts/email/verification/', {
      email: email.value,
      scene: 'change_password',
    })
    success.value = res.data?.message || '验证码已发送'
    countdown.value = 60
    timer = setInterval(() => {
      countdown.value -= 1
      if (countdown.value <= 0) {
        clearInterval(timer)
        timer = null
      }
    }, 1000)
  } catch (e) {
    error.value = e?.response?.data?.message || '发送验证码失败'
  } finally {
    sendingCode.value = false
  }
}

onBeforeUnmount(() => {
  if (timer) clearInterval(timer)
})
</script>

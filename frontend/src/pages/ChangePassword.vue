<template>
  <AppShell>
    <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-10 flex flex-col items-center gap-6">
      <div v-if="loadingUser" class="py-10">
        <LoadingSpinner>加载账户信息…</LoadingSpinner>
      </div>
      <ErrorState
        v-else-if="loadError"
        :message="loadError"
        retry-label="重试"
        @retry="loadUser"
      />
      <template v-else>
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
              <p class="text-sm text-muted">
                <router-link class="font-bold text-primary hover:underline" to="/forgot-password">忘记当前密码？</router-link>
              </p>
            </div>
          </form>
        </div>
      </template>
    </div>
  </AppShell>
</template>

<script setup>
  import { reactive, ref, onMounted, onBeforeUnmount } from 'vue'
  import { useRouter } from 'vue-router'
  import api from '@/api/client'
  import { useAuthStore } from '@/stores/auth'
  import { parseApiError } from '@/api/errors'
  import { useToastStore } from '@/stores/toast'
  import { validatePassword } from '@/utils/validation'
  import { CAPTCHA_SCENES } from '@/constants/enums'
  import { LoadingSpinner, ErrorState } from '@/components/ui'
  import AppShell from '@/components/AppShell.vue'

  const router = useRouter()
  const auth = useAuthStore()
  const toast = useToastStore()

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
const loadError = ref('')
const loadingUser = ref(false)
const oldError = ref(false)
const newError = ref(false)
const confirmError = ref(false)
const hasToken = () => {
  if (typeof window === 'undefined') return false
  return (
    !!auth.accessToken ||
    !!auth.refreshToken ||
    !!localStorage.getItem('ftc_access') ||
    !!sessionStorage.getItem('ftc_access')
  )
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
    toast.success(success.value)
    // 可选：更新后要求重新登录
    auth.logout()
    setTimeout(() => {
      router.push('/login')
    }, 400)
  } catch (e) {
    error.value = parseApiError(e, '修改失败，请稍后重试')
    toast.error(error.value)
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

const loadUser = async () => {
  loadingUser.value = true
  loadError.value = ''
  if (!hasToken()) {
    loadError.value = '请先登录后访问'
    toast.error(loadError.value)
    loadingUser.value = false
    return
  }
  if (auth.user?.email) {
    email.value = auth.user.email
  }
  try {
    const res = await api.get('/accounts/me/')
    const data = res.data?.data?.user || res.data?.user || {}
    email.value = data.email || ''
  } catch (err) {
    const status = err?.response?.status
    if (status === 401) {
      auth.logout()
      loadError.value = '请先登录后访问'
      toast.error(loadError.value)
      return
    }
    loadError.value = parseApiError(err, '获取账户信息失败')
  } finally {
    loadingUser.value = false
  }
}

onMounted(() => {
  loadUser()
})

const sendCode = async () => {
  error.value = ''
  success.value = ''
  codeError.value = false
  if (!email.value) {
    codeError.value = true
    error.value = '请先绑定邮箱后再发送验证码'
    router.replace('/profile')
    return
  }
  sendingCode.value = true
  try {
    const res = await api.post('/accounts/email/verification/', {
      email: email.value,
      scene: CAPTCHA_SCENES.CHANGE_PASSWORD,
    })
    success.value = res.data?.message || '验证码已发送'
    toast.success(success.value)
    countdown.value = 60
    timer = setInterval(() => {
      countdown.value -= 1
      if (countdown.value <= 0) {
        clearInterval(timer)
        timer = null
      }
    }, 1000)
  } catch (e) {
    error.value = parseApiError(e, '发送验证码失败，请稍后重试')
    countdown.value = 0
    if (timer) {
      clearInterval(timer)
      timer = null
    }
    toast.error(error.value)
  } finally {
    sendingCode.value = false
  }
}

onBeforeUnmount(() => {
  if (timer) clearInterval(timer)
})
</script>

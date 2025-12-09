<template>
  <div class="dark">
    <div class="relative min-h-screen bg-background-dark text-text flex items-center justify-center px-4">
      <div class="absolute inset-0">
        <div class="absolute inset-0 bg-background-dark"></div>
        <div class="absolute inset-0 bg-[radial-gradient(circle_at_center,_rgba(42,50,113,0.35),_transparent_40%)]"></div>
      </div>

      <div class="relative w-full max-w-md flex flex-col gap-6">
        <header class="flex flex-col items-center gap-3 text-center">
          <div class="flex items-center gap-3">
            <div class="size-6 text-primary">
              <svg fill="none" viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
                <path
                  d="M4 42.4379C4 42.4379 14.0962 36.0744 24 41.1692C35.0664 46.8624 44 42.2078 44 42.2078L44 7.01134C44 7.01134 35.068 11.6577 24.0031 5.96913C14.0971 0.876274 4 7.27094 4 7.27094L4 42.4379Z"
                  fill="currentColor"
                />
              </svg>
            </div>
            <h2 class="text-xl font-bold leading-tight tracking-[-0.015em]">{{ brandName }}</h2>
          </div>
          <h1 class="tracking-light text-[28px] sm:text-[32px] font-bold leading-tight">找回密码</h1>
          <p class="text-sm text-muted">输入邮箱获取验证码并重置密码</p>
        </header>

        <main class="relative w-full rounded-xl bg-panel border border-border-panel shadow-panel p-6 sm:p-8">
          <form class="space-y-4" @submit.prevent="submit">
            <div class="flex flex-col gap-2">
              <label class="text-sm font-medium leading-normal" for="email">邮箱</label>
              <div class="relative flex items-center">
                <span class="material-symbols-outlined absolute left-4 text-muted text-xl">mail</span>
                <input
                  v-model="form.email"
                  class="form-input flex w-full min-w-0 flex-1 resize-none overflow-hidden rounded-lg text-text focus:outline-0 focus:ring-2 border h-12 placeholder:text-muted pl-12 pr-4 text-base font-normal leading-normal bg-input"
                  :class="emailError ? 'border-danger focus:border-danger focus:ring-danger/40' : 'border-input-border focus:ring-primary/50 focus:border-primary'"
                  id="email"
                  placeholder="请输入邮箱"
                  type="email"
                />
              </div>
              <p v-if="emailError" class="text-xs text-danger">请输入正确的邮箱</p>
            </div>

            <div class="flex flex-col gap-2">
              <label class="text-sm font-medium leading-normal" for="code">验证码</label>
              <div class="flex items-center gap-3">
                <input
                  v-model="form.code"
                  class="form-input flex w-full flex-1 resize-none overflow-hidden rounded-lg border bg-input p-3.5 text-base font-normal leading-normal text-text placeholder:text-muted focus:outline-0 focus:ring-2 h-12"
                  :class="codeError ? 'border-danger focus:border-danger focus:ring-danger/40' : 'border-input-border focus:border-primary focus:ring-primary/40'"
                  id="code"
                  placeholder="请输入邮箱验证码"
                  type="text"
                />
                <button
                  class="flex h-12 cursor-pointer items-center justify-center overflow-hidden rounded-lg bg-border-panel px-4 text-sm font-bold leading-normal text-text tracking-[0.015em] whitespace-nowrap hover:bg-input-border transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
                  type="button"
                  :disabled="sendingCode || countdown > 0"
                  @click="sendCode"
                >
                  <span class="truncate" v-if="countdown === 0">{{ sendingCode ? '发送中…' : '发送验证码' }}</span>
                  <span v-else class="truncate">{{ countdown }} 秒后可重发</span>
                </button>
              </div>
              <p class="text-xs" :class="error ? 'text-danger' : 'text-emerald-300'">我们会把重置验证码发送到你的邮箱</p>
            </div>

            <div class="flex flex-col gap-2">
              <label class="text-sm font-medium leading-normal" for="new-password">新密码</label>
              <div class="relative flex items-center">
                <span class="material-symbols-outlined absolute left-4 text-muted text-xl">lock</span>
                <input
                  v-model="form.new_password"
                  class="form-input flex w-full min-w-0 flex-1 resize-none overflow-hidden rounded-lg text-text focus:outline-0 focus:ring-2 border bg-input h-12 placeholder:text-muted pl-12 pr-12 text-base font-normal leading-normal"
                  :class="passwordError ? 'border-danger focus:border-danger focus:ring-danger/40' : 'border-input-border focus:ring-primary/50 focus:border-primary'"
                  id="new-password"
                  placeholder="请输入新密码"
                  :type="showNew ? 'text' : 'password'"
                />
                <button
                  aria-label="Toggle password visibility"
                  class="absolute right-0 flex h-full items-center justify-center px-4 text-muted hover:text-text"
                  type="button"
                  @click="showNew = !showNew"
                >
                  <span class="material-symbols-outlined text-xl">{{ showNew ? 'visibility_off' : 'visibility' }}</span>
                </button>
              </div>
              <p class="text-xs" :class="passwordError ? 'text-danger' : 'text-emerald-300'">8-64 位，需同时包含字母和数字</p>
            </div>

            <div class="flex flex-col gap-2">
              <label class="text-sm font-medium leading-normal" for="confirm-password">确认新密码</label>
              <div class="relative flex items-center">
                <span class="material-symbols-outlined absolute left-4 text-muted text-xl">lock_reset</span>
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
            </div>

            <div class="pt-2">
              <button
                class="flex w-full cursor-pointer items-center justify-center overflow-hidden rounded-lg h-12 px-4 bg-primary text-primary-foreground text-base font-bold leading-normal tracking-[0.015em] hover:bg-primary/90 transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
                type="submit"
                :disabled="submitting"
              >
                <span class="truncate">{{ submitting ? '提交中…' : '重置密码' }}</span>
              </button>
            </div>
          </form>

          <div class="mt-4 text-center">
            <router-link class="text-sm font-bold text-primary hover:underline" to="/login">返回登录</router-link>
          </div>
        </main>
      </div>
    </div>
  </div>
</template>

<script setup>
  import { computed, onBeforeUnmount, reactive, ref } from 'vue'
  import { useRouter } from 'vue-router'
  import api from '@/api/client'
  import { useConfigStore } from '@/stores/config'
  import { parseApiError } from '@/api/errors'
  import { useToastStore } from '@/stores/toast'
  import { validatePassword, isEmail } from '@/utils/validation'
  import { CAPTCHA_SCENES } from '@/constants/enums'

  const router = useRouter()
  const configStore = useConfigStore()
  const toast = useToastStore()
  const brandName = computed(() => configStore.brand || 'Find The Cat')

const form = reactive({
  email: '',
  code: '',
  new_password: '',
  confirm_password: '',
})

const sendingCode = ref(false)
const countdown = ref(0)
let timer = null
const submitting = ref(false)
const showNew = ref(false)
const showConfirm = ref(false)
const error = ref('')
const success = ref('')
const emailError = ref(false)
const codeError = ref(false)
const passwordError = ref(false)
const confirmError = ref(false)

const sendCode = async () => {
  emailError.value = false
  error.value = ''
  success.value = ''
  codeError.value = false

  if (!form.email || !isEmail(form.email)) {
    emailError.value = true
    error.value = '请先填写正确的邮箱'
    return
  }

  sendingCode.value = true
  try {
    const res = await api.post('/accounts/password/reset/request/', { email: form.email, scene: CAPTCHA_SCENES.RESET_PASSWORD })
    success.value = res.data?.message || '验证码已发送，请检查邮箱'
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
    error.value = parseApiError(e, '发送验证码失败，请稍后再试')
    countdown.value = 0
    toast.error(error.value)
  } finally {
    sendingCode.value = false
  }
}

const submit = async () => {
  error.value = ''
  success.value = ''
  emailError.value = false
  codeError.value = false
  passwordError.value = false
  confirmError.value = false

  if (!form.email || !form.code || !form.new_password || !form.confirm_password) {
    if (!form.email) emailError.value = true
    if (!form.code) codeError.value = true
    if (!form.new_password) passwordError.value = true
    if (!form.confirm_password) confirmError.value = true
    error.value = '请完整填写所有字段'
    return
  }
  if (!isEmail(form.email)) {
    emailError.value = true
    error.value = '请输入正确的邮箱'
    return
  }

  const pwdValidation = validatePassword(form.new_password)
  if (pwdValidation) {
    passwordError.value = true
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
    const res = await api.post('/accounts/password/reset/', {
      email: form.email,
      code: form.code,
      new_password: form.new_password,
      confirm_password: form.confirm_password,
    })
    success.value = res.data?.message || '密码重置成功，请使用新密码登录'
    toast.success(success.value)
    setTimeout(() => {
      router.push('/login')
    }, 500)
  } catch (e) {
    error.value = parseApiError(e, '重置失败，请稍后再试')
    toast.error(error.value)
    const code = e?.response?.data?.code
    if (code === 40002) {
      emailError.value = true
      passwordError.value = true
      codeError.value = true
    }
  } finally {
    submitting.value = false
  }
}

onBeforeUnmount(() => {
  if (timer) clearInterval(timer)
})
</script>

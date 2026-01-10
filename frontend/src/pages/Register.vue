<template>
  <div class="dark">
    <div class="relative flex min-h-screen w-full items-center justify-center overflow-hidden p-4 md:p-6 bg-background-dark text-text">
      <div class="absolute inset-0">
        <div class="absolute inset-0 bg-background-dark"></div>
        <div class="absolute inset-0 bg-[radial-gradient(circle_at_center,_rgba(42,50,113,0.35),_transparent_40%)]"></div>
      </div>

      <div class="relative z-10 flex w-full max-w-md flex-col items-center justify-center">
        <header class="flex w-full flex-col items-center gap-4 mb-8">
          <div class="flex items-center gap-3">
            <div class="size-8 text-primary">
              <svg fill="none" viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
                <path
                  d="M4 42.4379C4 42.4379 14.0962 36.0744 24 41.1692C35.0664 46.8624 44 42.2078 44 42.2078L44 7.01134C44 7.01134 35.068 11.6577 24.0031 5.96913C14.0971 0.876274 4 7.27094 4 7.27094L4 42.4379Z"
                  fill="currentColor"
                />
              </svg>
            </div>
            <h2 class="text-2xl font-bold leading-tight tracking-[-0.015em]">{{ brandName }}</h2>
          </div>
            <h1 class="text-center text-3xl font-bold tracking-tight md:text-4xl">创建你的 FTC 账号</h1>
        </header>

        <main class="w-full rounded-xl border border-solid border-border-panel bg-panel p-6 sm:p-8 space-y-6 shadow-panel">
          <form class="space-y-4" @submit.prevent="submit">
            <div class="flex flex-col">
              <label class="text-sm font-medium leading-normal pb-2" for="username">用户名</label>
              <input
                v-model="form.username"
                class="form-input flex w-full resize-none overflow-hidden rounded-lg border bg-input p-3.5 text-base font-normal leading-normal text-text placeholder:text-muted focus:outline-0 focus:ring-2 h-12"
                :class="usernameError ? 'border-danger focus:border-danger focus:ring-danger/40' : 'border-input-border focus:border-primary focus:ring-primary/40'"
                id="username"
                placeholder="请输入用户名"
                type="text"
              />
              <p v-if="usernameError" class="text-xs text-danger mt-2">请输入用户名</p>
            </div>

            <div class="flex flex-col">
              <label class="text-sm font-medium leading-normal pb-2" for="email">邮箱</label>
              <input
                v-model="form.email"
                class="form-input flex w-full resize-none overflow-hidden rounded-lg border bg-input p-3.5 text-base font-normal leading-normal text-text placeholder:text-muted focus:outline-0 focus:ring-2 h-12"
                :class="emailError ? 'border-danger focus:border-danger focus:ring-danger/40' : 'border-input-border focus:border-primary focus:ring-primary/40'"
                id="email"
                placeholder="请输入邮箱"
                type="email"
              />
              <p v-if="emailError" class="text-xs text-danger mt-2">请输入邮箱</p>
            </div>

            <div class="flex flex-col">
              <label class="text-sm font-medium leading-normal pb-2" for="password">密码</label>
              <div class="relative w-full">
                <input
                  v-model="form.password"
                  class="form-input flex w-full resize-none overflow-hidden rounded-lg border border-input-border bg-input p-3.5 pr-10 text-base font-normal leading-normal text-text placeholder:text-muted focus:border-primary focus:outline-0 focus:ring-2 focus:ring-primary/40 h-12"
                  id="password"
                  placeholder="请输入密码"
                  :type="showPassword ? 'text' : 'password'"
                  :class="passwordError ? 'border-danger focus:border-danger focus:ring-danger/40' : ''"
                />
                <div class="absolute inset-y-0 right-0 flex items-center pr-3">
                  <span class="material-symbols-outlined text-muted cursor-pointer" style="font-size: 20px;" @click="showPassword = !showPassword">
                    {{ showPassword ? 'visibility_off' : 'visibility' }}
                  </span>
                </div>
              </div>
              <p class="text-xs mt-2" :class="passwordError ? 'text-danger' : 'text-emerald-300'">
                8-64 位，需包含字母和数字
              </p>
            </div>

            <div class="flex flex-col">
              <label class="text-sm font-medium leading-normal pb-2" for="confirm-password">确认密码</label>
              <div class="relative w-full">
                <input
                  v-model="form.confirm_password"
                  class="form-input flex w-full resize-none overflow-hidden rounded-lg border border-input-border bg-input p-3.5 pr-10 text-base font-normal leading-normal text-text placeholder:text-muted focus:border-primary focus:outline-0 focus:ring-2 focus:ring-primary/40 h-12"
                  id="confirm-password"
                  placeholder="请再次输入密码"
                  :type="showConfirm ? 'text' : 'password'"
                />
                <div class="absolute inset-y-0 right-0 flex items-center pr-3">
                  <span class="material-symbols-outlined text-muted cursor-pointer" style="font-size: 20px;" @click="showConfirm = !showConfirm">
                    {{ showConfirm ? 'visibility_off' : 'visibility' }}
                  </span>
                </div>
              </div>
            </div>

            <div class="flex flex-col space-y-2">
              <label class="text-sm font-medium leading-normal" for="verification-code">验证码</label>
              <div class="flex items-center gap-3">
                <input
                  v-model="form.email_code"
                  class="form-input flex w-full flex-1 resize-none overflow-hidden rounded-lg border border-input-border bg-input p-3.5 text-base font-normal leading-normal text-text placeholder:text-muted focus:border-primary focus:outline-0 focus:ring-2 focus:ring-primary/40 h-12"
                  id="verification-code"
                  placeholder="请输入验证码"
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
              <p class="text-xs" :class="error ? 'text-danger' : 'text-emerald-300'">60 秒后可重发</p>
            </div>

            <div class="pt-4">
              <button
                class="flex min-w-[84px] w-full cursor-pointer items-center justify-center overflow-hidden rounded-lg h-12 px-4 bg-primary text-primary-foreground text-base font-bold leading-normal tracking-[0.015em] hover:bg-primary/90 transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
                type="submit"
                :disabled="submitting"
              >
                <span class="truncate">{{ submitting ? '注册中…' : '注册' }}</span>
              </button>
            </div>
          </form>
        </main>

        <div class="mt-4 space-y-1 text-center">
        </div>

        <footer class="mt-6 text-center">
          <p class="text-sm text-muted text-center">
            已有账号？
            <router-link class="font-bold text-primary/90 hover:text-primary transition-colors" to="/login">去登录</router-link>
          </p>
        </footer>
      </div>
    </div>
  </div>
</template>

<script setup>
  import { computed, onBeforeUnmount, reactive, ref } from 'vue'
  import { useRouter } from 'vue-router'
  import api from '@/api/client'
  import { useAuthStore } from '@/stores/auth'
  import { parseApiError } from '@/api/errors'
  import { useConfigStore } from '@/stores/config'
  import { useToastStore } from '@/stores/toast'
  import { validatePassword, isEmail, isUsername } from '@/utils/validation'
  import { CAPTCHA_SCENES } from '@/constants/enums'

  const router = useRouter()
  const auth = useAuthStore()
  const configStore = useConfigStore()
  const toast = useToastStore()
  const brandName = computed(() => configStore.brand || 'Find The Cat')

const form = reactive({
  username: '',
  email: '',
  password: '',
  confirm_password: '',
  email_code: '',
})

const showPassword = ref(false)
const showConfirm = ref(false)
const submitting = ref(false)
const sendingCode = ref(false)
const countdown = ref(0)
let timer = null
const error = ref('')
const success = ref('')
const passwordError = ref(false)
const usernameError = ref(false)
const emailError = ref(false)

const sendCode = async () => {
  // reset flags
  usernameError.value = false
  emailError.value = false
  passwordError.value = false
  error.value = ''
  success.value = ''

  if (!form.username) {
    usernameError.value = true
    error.value = '请输入用户名'
    return
  }
  if (!form.email || !isEmail(form.email)) {
    emailError.value = true
    error.value = '请输入正确的邮箱'
    return
  }
  if (!isUsername(form.username)) {
    usernameError.value = true
    error.value = '用户名需为 3-32 位字母、数字或下划线'
    return
  }
  const pwdValidation = validatePassword(form.password)
  if (pwdValidation) {
    passwordError.value = true
    error.value = pwdValidation
    return
  }

  sendingCode.value = true
  try {
    const res = await api.post('/accounts/email/verification/', {
      email: form.email,
      scene: CAPTCHA_SCENES.REGISTER,
    })
    success.value = res.data?.message || '验证码已发送'
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
    error.value = parseApiError(e, '发送验证码失败，请稍后再试')
    toast.error(error.value)
  } finally {
    sendingCode.value = false
  }
}

const submit = async () => {
  error.value = ''
  success.value = ''
  passwordError.value = false
  usernameError.value = false
  emailError.value = false

  if (!form.username || !form.email || !form.password || !form.confirm_password || !form.email_code) {
    if (!form.username) usernameError.value = true
    if (!form.email) emailError.value = true
    error.value = '请填写所有字段'
    return
  }
  if (!isEmail(form.email)) {
    emailError.value = true
    error.value = '请输入正确的邮箱'
    return
  }
  if (!isUsername(form.username)) {
    usernameError.value = true
    error.value = '用户名需为 3-32 位字母、数字或下划线'
    return
  }
  const pwdValidation = validatePassword(form.password)
  if (pwdValidation) {
    error.value = pwdValidation
    passwordError.value = true
    return
  }
  if (form.password !== form.confirm_password) {
    error.value = 'Passwords do not match'
    return
  }
  submitting.value = true
  try {
    const res = await auth.register({
      username: form.username,
      email: form.email,
      password: form.password,
      confirm_password: form.confirm_password,
      email_code: form.email_code,
    })
    success.value = res?.message || '注册成功'
    toast.success(success.value)
    setTimeout(() => {
      router.push('/login')
    }, 400)
  } catch (e) {
    error.value = parseApiError(e, '注册失败，请稍后再试')
    toast.error(error.value)
  } finally {
    submitting.value = false
  }
}

onBeforeUnmount(() => {
  if (timer) {
    clearInterval(timer)
  }
})
</script>

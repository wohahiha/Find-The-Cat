<template>
  <div class="dark">
    <div class="relative min-h-screen bg-background-dark text-text flex items-center justify-center px-4">
      <div class="absolute inset-0">
        <div class="absolute inset-0 bg-background-dark"></div>
        <div class="absolute inset-0 bg-[radial-gradient(circle_at_center,_rgba(42,50,113,0.35),_transparent_40%)]"></div>
      </div>

      <div class="relative flex w-full max-w-xl flex-col items-center gap-8 rounded-xl bg-panel p-8 sm:p-12 border border-border-panel shadow-panel">
        <header class="flex flex-col items-center gap-4 text-center">
            <div class="flex items-center gap-3">
              <div class="size-6 text-primary">
                <svg fill="none" viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
                  <path
                    d="M4 42.4379C4 42.4379 14.0962 36.0744 24 41.1692C35.0664 46.8624 44 42.2078 44 42.2078L44 7.01134C44 7.01134 35.068 11.6577 24.0031 5.96913C14.0971 0.876274 4 7.27094 4 42.4379Z"
                    fill="currentColor"
                  />
                </svg>
              </div>
              <h2 class="text-xl font-bold leading-tight tracking-[-0.015em]">{{ brandName }}</h2>
            </div>
          <h1 class="tracking-light text-[36px] font-bold leading-tight">访问你的终端</h1>
        </header>

        <div class="flex w-full flex-col gap-4">
          <label class="flex flex-col w-full">
            <p class="text-base font-medium leading-normal pb-2">用户名或邮箱</p>
            <div class="relative flex w-full items-center">
              <span class="material-symbols-outlined absolute left-4 text-muted text-xl">person</span>
              <input
                v-model="form.identifier"
                class="form-input flex w-full min-w-0 flex-1 resize-none overflow-hidden rounded-lg text-text focus:outline-0 focus:ring-2 border h-14 placeholder:text-muted pl-12 pr-4 text-base font-normal leading-normal bg-input"
                :class="identifierError ? 'border-danger focus:border-danger focus:ring-danger/40' : 'border-input-border focus:ring-primary/50 focus:border-primary'"
                placeholder="请输入用户名或邮箱"
                type="text"
              />
            </div>
            <p v-if="identifierError" class="text-xs text-danger mt-1">请检查用户名或邮箱</p>
          </label>

          <label class="flex flex-col w-full">
            <p class="text-base font-medium leading-normal pb-2">密码</p>
            <div class="relative flex w-full flex-1 items-center">
              <span class="material-symbols-outlined absolute left-4 text-muted text-xl">lock</span>
              <input
                v-model="form.password"
                class="form-input flex w-full min-w-0 flex-1 resize-none overflow-hidden rounded-lg text-text focus:outline-0 focus:ring-2 border bg-input h-14 placeholder:text-muted pl-12 pr-12 text-base font-normal leading-normal"
                :class="passwordError ? 'border-danger focus:border-danger focus:ring-danger/40' : 'border-input-border focus:ring-primary/50 focus:border-primary'"
                placeholder="请输入密码"
                :type="showPassword ? 'text' : 'password'"
              />
              <button
                aria-label="Toggle password visibility"
                class="absolute right-0 flex h-full items-center justify-center px-4 text-muted hover:text-text"
                type="button"
                @click="showPassword = !showPassword"
              >
                <span class="material-symbols-outlined text-xl">{{ showPassword ? 'visibility_off' : 'visibility' }}</span>
              </button>
            </div>
            <p v-if="passwordError" class="text-xs text-danger mt-1">请检查密码</p>
          </label>

          <div class="flex flex-col gap-2">
            <p class="text-base font-medium leading-normal">验证码</p>
            <div class="flex items-center gap-3">
              <input
                v-model="form.captchaCode"
                class="form-input flex-1 min-w-[9rem] resize-none overflow-hidden rounded-lg text-text focus:outline-0 focus:ring-2 border h-14 placeholder:text-muted px-4 text-base font-normal leading-normal"
                :class="captchaError ? 'border-danger focus:border-danger focus:ring-danger/40 bg-input' : 'border-input-border bg-input focus:ring-primary/50 focus:border-primary'"
                placeholder="请输入验证码"
                type="text"
              />
              <div class="flex h-14 w-40 flex-shrink-0 items-center justify-center rounded-lg border" :class="captchaError ? 'border-danger' : 'border-input-border'">
                <img
                  alt="验证码"
                  class="h-full w-full rounded-md object-cover object-center bg-input"
                  :src="captcha.image || placeholderCaptcha"
                />
              </div>
              <button
                aria-label="刷新验证码"
                class="flex h-14 w-14 flex-shrink-0 cursor-pointer items-center justify-center overflow-hidden rounded-lg bg-border-panel text-text hover:bg-input-border"
                type="button"
                :disabled="captcha.loading"
                @click="loadCaptcha"
              >
                <span class="material-symbols-outlined" :class="{ 'animate-spin': captcha.loading }">refresh</span>
              </button>
            </div>
            <p v-if="captchaError" class="text-xs text-danger mt-1">验证码错误或已过期</p>
          </div>

          <div class="flex flex-wrap items-center justify-between gap-2">
            <label class="flex cursor-pointer items-center gap-2">
              <input v-model="form.remember" class="form-checkbox h-4 w-4 rounded border-input-border bg-input text-primary focus:ring-primary/50" type="checkbox" />
              <span class="text-sm font-medium">记住我</span>
            </label>
            <router-link class="text-sm font-medium text-primary hover:underline" to="/forgot-password">忘记密码？</router-link>
          </div>
        </div>

        <div class="flex w-full flex-col items-stretch gap-4 pt-2">
          <button
            class="flex w-full min-w-[84px] max-w-[520px] cursor-pointer items-center justify-center overflow-hidden rounded-lg h-14 px-4 bg-primary text-primary-foreground text-base font-bold leading-normal tracking-[-0.015em] hover:bg-primary/90 focus:outline-none focus:ring-2 focus:ring-primary/50 focus:ring-offset-2 focus:ring-offset-panel disabled:opacity-60 disabled:cursor-not-allowed"
            type="button"
            :disabled="submitting"
            @click="submit"
          >
            <span class="truncate">{{ submitting ? '登录中…' : '登录' }}</span>
          </button>
          <p class="text-center text-sm text-muted">
            还没有账号？
            <router-link class="font-bold text-text hover:underline" to="/register">前往注册</router-link>
          </p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import api from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import { useConfigStore } from '@/stores/config'
import { parseApiError } from '@/api/errors'
import { useToastStore } from '@/stores/toast'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const configStore = useConfigStore()
const toast = useToastStore()
const brandName = computed(() => configStore.brand || 'Find The Cat')

const form = reactive({
  identifier: '',
  password: '',
  captchaCode: '',
  remember: false,
})
const showPassword = ref(false)
const submitting = ref(false)
const error = ref('')
const success = ref('')
const captcha = reactive({
  key: '',
  image: '',
  loading: false,
})
const identifierError = ref(false)
const passwordError = ref(false)
const captchaError = ref(false)

const placeholderCaptcha =
  "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='260' height='56'><rect width='100%' height='100%' fill='%23181834'/><text x='50%' y='50%' dy='.3em' text-anchor='middle' fill='%23ffffff' font-size='18' font-family='Arial'>验证码</text></svg>"

const resolveUrl = (url) => {
  if (!url) return ''
  if (/^https?:\/\//i.test(url)) return url
  const base = import.meta.env.VITE_BACKEND_URL || ''
  return base ? `${base}${url}` : url
}

const parseCaptchaResponse = (resData) => {
  const payload = resData?.data || resData
  return {
    key: payload?.captcha_key || payload?.key || payload?.data?.captcha_key || '',
    image: payload?.image || payload?.image_url || payload?.captcha_image || payload?.data?.image || '',
  }
}

const loadCaptcha = async (keepError = false) => {
  captcha.loading = true
  if (!keepError) {
    captchaError.value = false
  }
  error.value = ''
  try {
    const res = await api.get('/accounts/auth/captcha/')
    const parsed = parseCaptchaResponse(res.data)
    captcha.key = parsed.key
    const resolved = resolveUrl(parsed.image)
    captcha.image = resolved ? `${resolved}?t=${Date.now()}` : placeholderCaptcha
  } catch (e) {
    error.value = parseApiError(e, '验证码加载失败，请重试')
    // 失败时清理旧验证码，避免提交错 key
    captcha.key = ''
    captcha.image = placeholderCaptcha
    toast.error(error.value)
  } finally {
    captcha.loading = false
  }
}

const submit = async () => {
  error.value = ''
  success.value = ''
  identifierError.value = false
  passwordError.value = false
  captchaError.value = false
  if (!form.identifier || !form.password || !form.captchaCode || !captcha.key) {
    if (!form.identifier) identifierError.value = true
    if (!form.password) passwordError.value = true
    if (!form.captchaCode || !captcha.key) captchaError.value = true
    error.value = '请填写所有字段并加载验证码'
    return
  }
  submitting.value = true
  try {
    const payload = {
      identifier: form.identifier,
      password: form.password,
      captcha_key: captcha.key,
      captcha_code: form.captchaCode,
      remember: form.remember,
    }
    const res = await auth.login(payload)
    success.value = res?.message || '登录成功'
    const redirect = route.query.redirect || '/'
    toast.success(success.value)
    setTimeout(() => {
      router.push(redirect)
    }, 300)
  } catch (e) {
    const resp = e?.response?.data || {}
    const code = resp.code
    const msg = resp.message || parseApiError(e, '登录失败，请重试')
    error.value = msg
    toast.error(error.value)
    if (code === 40104) {
      captchaError.value = true
      error.value = msg || '验证码错误或已过期'
      loadCaptcha(true)
    } else if (code === 40101) {
      identifierError.value = true
      passwordError.value = true
    } else if (code === 40103 || code === 40105) {
      identifierError.value = true
    } else if (code === 40002) {
      // 参数校验失败，回到填充全部字段
      identifierError.value = true
      passwordError.value = true
      captchaError.value = true
    } else {
      // 默认高亮所有字段
      identifierError.value = true
      passwordError.value = true
      captchaError.value = true
    }
  } finally {
    submitting.value = false
  }
}

onMounted(() => {
  loadCaptcha()
})
</script>

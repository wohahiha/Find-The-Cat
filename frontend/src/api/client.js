import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 15000,
})

const publicPaths = [
  '/accounts/auth/login/',
  '/accounts/auth/register/',
  '/accounts/auth/captcha/',
  '/accounts/password/reset/',
  '/accounts/password/reset/request/',
  '/accounts/email/verification/',
  '/accounts/auth/refresh/',
  '/system/public/brand/',
]

const hasWindow = typeof window !== 'undefined'
const stripAuth = (cfg) => {
  if (cfg?.headers?.Authorization) {
    delete cfg.headers.Authorization
  }
  return cfg
}
const readToken = (key) => {
  if (!hasWindow) return ''
  return sessionStorage.getItem(key) || localStorage.getItem(key) || ''
}
const getAccess = () => readToken('ftc_access')
const getRefresh = () => readToken('ftc_refresh')
const chooseStore = () => {
  if (!hasWindow) return null
  if (sessionStorage.getItem('ftc_refresh')) return sessionStorage
  if (localStorage.getItem('ftc_refresh')) return localStorage
  return localStorage
}
const setTokens = (access, refresh) => {
  if (!hasWindow) return
  const store = chooseStore()
  if (access) store?.setItem('ftc_access', access)
  if (refresh) store?.setItem('ftc_refresh', refresh)
  api.defaults.headers.common.Authorization = access ? `Bearer ${access}` : undefined
}
const clearTokens = () => {
  if (!hasWindow) return
  localStorage.removeItem('ftc_access')
  localStorage.removeItem('ftc_refresh')
  sessionStorage.removeItem('ftc_access')
  sessionStorage.removeItem('ftc_refresh')
  delete api.defaults.headers.common.Authorization
}

api.interceptors.request.use((config) => {
  const url = config?.url || ''
  const isPublic = publicPaths.some((p) => url.includes(p))
  if (isPublic) {
    stripAuth(config)
    delete api.defaults.headers.common.Authorization
    return config
  }
  const access = getAccess()
  if (access && !config.headers.Authorization) {
    config.headers.Authorization = `Bearer ${access}`
  }
  return config
})

let isRefreshing = false
let refreshQueue = []

const processQueue = (error, token = null) => {
  refreshQueue.forEach(({ resolve, reject }) => {
    if (error) {
      reject(error)
    } else {
      resolve(token)
    }
  })
  refreshQueue = []
}

const attemptRefresh = async () => {
  const refresh = getRefresh()
  if (!refresh) {
    throw new Error('缺少刷新令牌')
  }
  // use a raw axios call to avoid interceptor recursion
  const res = await axios.post('/api/accounts/auth/refresh/', { refresh })
  const data = res.data?.data || res.data || {}
  const newAccess = data.access || data.token || ''
  const newRefresh = data.refresh || refresh
  setTokens(newAccess, newRefresh)
  api.defaults.headers.common.Authorization = newAccess ? `Bearer ${newAccess}` : undefined
  return newAccess
}

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const { response, config } = error || {}
    const status = response?.status
    const code = response?.data?.code
    const url = config?.url || ''
    // If request is public or refresh itself, don't attempt refresh
    const isPublic = publicPaths.some((p) => url.includes(p))
    const isRefreshCall = url.includes('/accounts/auth/refresh/')

    if (!response || isRefreshCall) {
      return Promise.reject(error)
    }

    // Token invalid/expired -> try refresh
    if (status === 401 || code === 40102) {
      // 明确的用户不存在/认证失败，直接清理令牌并拒绝
      if (code === 40100) {
        clearTokens()
        window.location.href = '/login'
        return Promise.reject(error)
      }
      if (isPublic) {
        // 公开接口不刷新、不清理，直接透出
        return Promise.reject(error)
      }
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          refreshQueue.push({
            resolve: (token) => {
              if (token && config) {
                config.headers.Authorization = `Bearer ${token}`
                resolve(api(config))
              } else {
                reject(error)
              }
            },
            reject,
          })
        })
      }

      isRefreshing = true
      return new Promise(async (resolve, reject) => {
        try {
          const newToken = await attemptRefresh()
          processQueue(null, newToken)
          if (config) {
            config.headers.Authorization = `Bearer ${newToken}`
            resolve(api(config))
          } else {
            resolve()
          }
        } catch (refreshErr) {
          clearTokens()
          processQueue(refreshErr, null)
          // redirect to login
          window.location.href = '/login'
          reject(refreshErr)
        } finally {
          isRefreshing = false
        }
      })
    }

    // 403 且明确定义为未登录/登录失效：仅在没有任何 token 时才跳转登录
    if (status === 403 && (code === 40300 || code === 40301)) {
      const access = getAccess()
      const refresh = getRefresh()
      if (!access && !refresh) {
        clearTokens()
        window.location.href = '/login'
      }
      return Promise.reject(error)
    }

    return Promise.reject(error)
  },
)

export default api

import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 15000,
})

const publicPaths = [
  '/accounts/auth/login/',
  '/accounts/auth/register/',
  '/accounts/auth/captcha/',
  '/accounts/auth/password/reset/',
  '/accounts/auth/password/reset/request/',
  '/accounts/email/verification/',
  '/accounts/auth/refresh/',
  '/token/refresh/',
  '/api/token/refresh/',
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
    throw new Error('No refresh token')
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
      if (isPublic) {
        clearTokens()
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

    return Promise.reject(error)
  },
)

export default api

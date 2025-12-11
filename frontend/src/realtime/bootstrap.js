import realtime from '@/utils/realtime'
import { useNotificationStore } from '@/stores/notifications'
import { useToastStore } from '@/stores/toast'
import { useAuthStore } from '@/stores/auth'
import router from '@/router'

let initialized = false

export function initRealtimeListeners() {
  if (initialized) return
  initialized = true
  const notifications = useNotificationStore()
  const toast = useToastStore()
  const auth = useAuthStore()

  realtime.on('notification', (payload) => {
    notifications.ingestRealtime(payload)
    notifications.fetchUnreadCount()
  })

  realtime.on('force_logout', (payload) => {
    const reason = payload?.reason || '登录状态已失效，请重新登录'
    auth.logout()
    toast.warn(reason)
    router.push({ path: '/login' })
  })

  realtime.on('submission_accepted', (payload) => {
    const title = payload?.challenge || '提交正确'
    toast.success(`提交通过：${title}`)
  })

  realtime.on('first_blood', (payload) => {
    const challenge = payload?.challenge || ''
    toast.info(`首杀！${challenge}`)
  })

  realtime.on('hint_unlocked', (payload) => {
    const chal = payload?.challenge || ''
    toast.info(`提示已解锁：${chal}`)
  })

  realtime.on('announcement_published', (payload) => {
    const contest = payload?.contest || ''
    toast.info(`新公告：${payload?.title || contest}`)
  })

  realtime.onAny((payload) => {
    const evt = payload?.event
    if (!evt) return
    if (evt.startsWith('machine_')) {
      const name = payload?.challenge || '靶机'
      const status = payload?.status || evt
      toast.info(`靶机事件：${name} ${status}`)
    }
  })

  // 页面刷新且已有 token 时，尝试启动通知通道
  if (auth.accessToken || auth.refreshToken) {
    realtime.startNotify()
  }
}

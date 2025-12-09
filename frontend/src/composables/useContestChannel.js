import { onMounted, onBeforeUnmount, ref } from 'vue'

export function useContestChannel(slug, { onMessage } = {}) {
  const socketRef = ref(null)
  const pingTimer = ref(null)
  const reconnectTimer = ref(null)

  const buildUrl = () => {
    const base = import.meta.env.VITE_BACKEND_URL || window.location.origin
    const wsBase = base.replace(/^http/, 'ws').replace(/\/$/, '')
    const token =
      sessionStorage.getItem('ftc_access') ||
      localStorage.getItem('ftc_access') ||
      ''
    const query = token ? `?token=${encodeURIComponent(token)}` : ''
    return `${wsBase}/ws/contests/${slug}/${query}`
  }

  const cleanup = () => {
    if (pingTimer.value) {
      clearInterval(pingTimer.value)
      pingTimer.value = null
    }
    if (reconnectTimer.value) {
      clearTimeout(reconnectTimer.value)
      reconnectTimer.value = null
    }
    if (socketRef.value) {
      socketRef.value.close()
      socketRef.value = null
    }
  }

  const connect = () => {
    if (!slug) return
    cleanup()
    try {
      const ws = new WebSocket(buildUrl())
      ws.onopen = () => {
        socketRef.value = ws
        pingTimer.value = setInterval(() => {
          if (socketRef.value && socketRef.value.readyState === WebSocket.OPEN) {
            socketRef.value.send(JSON.stringify({ type: 'ping' }))
          }
        }, 25000)
      }
      ws.onmessage = (evt) => {
        try {
          const data = JSON.parse(evt.data)
          if (onMessage) onMessage(data)
        } catch (e) {
          // ignore
        }
      }
      ws.onerror = () => ws.close()
      ws.onclose = () => {
        socketRef.value = null
        if (pingTimer.value) {
          clearInterval(pingTimer.value)
          pingTimer.value = null
        }
        reconnectTimer.value = setTimeout(() => {
          connect()
        }, 5000)
      }
    } catch (e) {
      reconnectTimer.value = setTimeout(() => {
        connect()
      }, 5000)
    }
  }

  onMounted(connect)
  onBeforeUnmount(cleanup)

  return {
    connect,
    cleanup,
  }
}

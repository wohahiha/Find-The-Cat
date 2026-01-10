// 统一 WebSocket 管理与事件总线
// - 维护通知通道 /ws/notify/ 与比赛通道 /ws/contests/{slug}/
// - 心跳 25s，重连 5s（429/403/401 可延长回退）
// - 基于 event/seq 去重，避免重复处理

const PING_INTERVAL = 25000
const RECONNECT_DELAY = 5000

const hasWindow = typeof window !== 'undefined'

const readToken = () => {
  if (!hasWindow) return ''
  return sessionStorage.getItem('ftc_access') || localStorage.getItem('ftc_access') || ''
}

const buildWsBase = () => {
  const base = (import.meta.env.VITE_BACKEND_URL || (hasWindow ? window.location.origin : '')).replace(/\/$/, '')
  return base.replace(/^http/, 'ws')
}

class EventBus {
  constructor() {
    this.listeners = new Map()
    this.anyListeners = new Set()
  }

  on(event, handler) {
    if (!event || !handler) return () => {}
    const arr = this.listeners.get(event) || []
    arr.push(handler)
    this.listeners.set(event, arr)
    return () => this.off(event, handler)
  }

  onAny(handler) {
    if (!handler) return () => {}
    this.anyListeners.add(handler)
    return () => this.anyListeners.delete(handler)
  }

  off(event, handler) {
    const arr = this.listeners.get(event)
    if (!arr) return
    this.listeners.set(
      event,
      arr.filter((h) => h !== handler),
    )
  }

  emit(event, payload) {
    if (!event) return
    const arr = this.listeners.get(event) || []
    arr.forEach((fn) => {
      try {
        fn(payload)
      } catch (e) {
        // ignore listener errors
      }
    })
    this.anyListeners.forEach((fn) => {
      try {
        fn(payload)
      } catch (e) {
        // ignore
      }
    })
  }
}

class WsConnection {
  constructor(path, { onMessage, onClose } = {}) {
    this.path = path
    this.onMessage = onMessage
    this.onClose = onClose
    this.socket = null
    this.pingTimer = null
    this.reconnectTimer = null
    this.seqSeen = {}
  }

  _url() {
    const base = buildWsBase()
    const token = readToken()
    const query = token ? `?token=${encodeURIComponent(token)}` : ''
    return `${base}${this.path}${query}`
  }

  start(delay = 0) {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
    if (delay > 0) {
      this.reconnectTimer = setTimeout(() => this._connect(), delay)
    } else {
      this._connect()
    }
  }

  _connect() {
    this.stop()
    try {
      const ws = new WebSocket(this._url())
      ws.onopen = () => {
        this.socket = ws
        this._startPing()
      }
      ws.onmessage = (evt) => {
        try {
          const data = JSON.parse(evt.data)
          const evtName = data?.event
          const seq = data?.seq
          if (seq !== undefined) {
            if (this.seqSeen[evtName] && this.seqSeen[evtName] >= seq) return
            this.seqSeen[evtName] = seq
          }
          if (this.onMessage) this.onMessage(data)
        } catch (e) {
          // ignore parse errors
        }
      }
      ws.onerror = () => {
        ws.close()
      }
      ws.onclose = (ev) => {
        this._stopPing()
        this.socket = null
        if (this.onClose) this.onClose(ev)
        const code = ev?.code || 1000
        let wait = RECONNECT_DELAY
        // 429/403/401/4429：延长重连间隔，避免抖动
        if ([429, 4401, 4403, 4429].includes(code)) {
          wait = 15000
        }
        this.start(wait)
      }
    } catch (e) {
      this.start(RECONNECT_DELAY)
    }
  }

  _startPing() {
    this._stopPing()
    this.pingTimer = setInterval(() => {
      if (this.socket && this.socket.readyState === WebSocket.OPEN) {
        this.socket.send(JSON.stringify({ type: 'ping' }))
      }
    }, PING_INTERVAL)
  }

  _stopPing() {
    if (this.pingTimer) {
      clearInterval(this.pingTimer)
      this.pingTimer = null
    }
  }

  stop() {
    this._stopPing()
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
    if (this.socket) {
      try {
        this.socket.close()
      } catch (e) {
        // ignore
      }
      this.socket = null
    }
  }
}

class RealtimeManager {
  constructor() {
    this.bus = new EventBus()
    this.notifyConn = null
    this.contestConns = new Map()
    this.contestRef = new Map()
    this.snapshots = new Map()
  }

  on(event, handler) {
    return this.bus.on(event, handler)
  }

  onAny(handler) {
    return this.bus.onAny(handler)
  }

  emit(event, payload) {
    this.bus.emit(event, payload)
  }

  _handleMessage = (data) => {
    if (!data || !data.event) return
    if (data.event === 'scoreboard_snapshot' && data.contest && data.entries) {
      this.snapshots.set(data.contest, data)
    }
    this.emit(data.event, data)
  }

  startNotify() {
    if (this.notifyConn) return
    this.notifyConn = new WsConnection('/ws/notify/', {
      onMessage: this._handleMessage,
      onClose: (ev) => {
        if (ev?.code === 4401 || ev?.code === 4403) {
          // 登录失效时稍后再重连，由 force_logout 处理
          return
        }
      },
    })
    this.notifyConn.start()
  }

  stopNotify() {
    if (this.notifyConn) {
      this.notifyConn.stop()
      this.notifyConn = null
    }
  }

  joinContest(slug) {
    if (!slug) return
    const count = this.contestRef.get(slug) || 0
    this.contestRef.set(slug, count + 1)
    if (this.contestConns.has(slug)) return
    const conn = new WsConnection(`/ws/contests/${slug}/`, {
      onMessage: this._handleMessage,
      onClose: () => {},
    })
    this.contestConns.set(slug, conn)
    conn.start()
  }

  leaveContest(slug) {
    if (!slug) return
    const count = this.contestRef.get(slug) || 0
    if (count <= 1) {
      this.contestRef.delete(slug)
      const conn = this.contestConns.get(slug)
      if (conn) conn.stop()
      this.contestConns.delete(slug)
      this.snapshots.delete(slug)
      return
    }
    this.contestRef.set(slug, count - 1)
  }

  getSnapshot(slug) {
    return this.snapshots.get(slug)
  }

  stopAll() {
    this.stopNotify()
    this.contestConns.forEach((conn) => conn.stop())
    this.contestConns.clear()
    this.contestRef.clear()
    this.snapshots.clear()
  }
}

const realtime = new RealtimeManager()
export default realtime

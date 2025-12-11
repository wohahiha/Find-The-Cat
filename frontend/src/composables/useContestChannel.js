import { onMounted, onBeforeUnmount } from 'vue'
import realtime from '@/utils/realtime'

export function useContestChannel(slug, { onMessage } = {}) {
  const handler = (evt) => {
    if (!evt || evt.contest !== slug) return
    if (onMessage) onMessage(evt)
  }

  let offAny = null

  onMounted(() => {
    if (!slug) return
    realtime.joinContest(slug)
    offAny = realtime.onAny(handler)
  })

  onBeforeUnmount(() => {
    if (!slug) return
    realtime.leaveContest(slug)
    if (offAny) offAny()
  })

  // expose manual control
  return {
    join: () => slug && realtime.joinContest(slug),
    leave: () => slug && realtime.leaveContest(slug),
  }
}

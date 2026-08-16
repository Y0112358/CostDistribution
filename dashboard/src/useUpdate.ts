import { useCallback, useRef, useState } from 'react'

export type UpdateState = 'idle' | 'pending' | 'updating' | 'ok' | 'error'
export type UpdateMode = 'reload' | 'inplace'

const UPDATE_URL = (import.meta.env.VITE_UPDATE_URL as string | undefined)?.trim() || ''
const POLL_MS = 15_000
const MAX_POLLS = 24 // 24 × 15s = 6 分鐘

function sleep(ms: number) {
  return new Promise((r) => setTimeout(r, ms))
}

async function fetchGeneratedAt(): Promise<string | null> {
  try {
    const r = await fetch(`data/meta.json?t=${Date.now()}`, { cache: 'no-store' })
    if (!r.ok) return null
    const m = await r.json()
    return typeof m.generated_at === 'string' ? m.generated_at : null
  } catch {
    return null
  }
}

/**
 * 共用「更新資料」流程：
 *   1. 記錄更新前 generated_at（字串比較，避免時區解析 bug）
 *   2. POST worker 觸發 GitHub Actions 重算
 *   3. 輪詢 meta.json 直到 generated_at 改變
 *   4. mode='reload' → 重整頁面；mode='inplace' → 呼叫 refreshData 就地更新
 */
export function useUpdateData(refreshData?: () => Promise<void>) {
  const [state, setState] = useState<UpdateState>('idle')
  const busy = useRef(false)
  const refreshRef = useRef(refreshData)
  refreshRef.current = refreshData

  const waitForData = useCallback(async (before: string | null, mode: UpdateMode) => {
    for (let i = 0; i < MAX_POLLS; i++) {
      await sleep(POLL_MS)
      const now = await fetchGeneratedAt()
      if (now == null || now === before) continue
      if (mode === 'inplace' && refreshRef.current) {
        await refreshRef.current()
      } else {
        window.location.reload()
        return
      }
      setState('ok')
      return
    }
    setState('ok')
  }, [])

  const runUpdate = useCallback(
    async (mode: UpdateMode = 'reload') => {
      if (busy.current || !UPDATE_URL) return
      busy.current = true
      setState('pending')
      try {
        const before = await fetchGeneratedAt()
        const r = await fetch(UPDATE_URL, { method: 'POST' })
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        setState('updating')
        await waitForData(before, mode)
      } catch (e) {
        console.error(e)
        setState('error')
      } finally {
        busy.current = false
      }
    },
    [waitForData],
  )

  return { state, runUpdate }
}

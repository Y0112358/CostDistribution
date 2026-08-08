import { useState } from 'react'

const UPDATE_URL = (import.meta.env.VITE_UPDATE_URL as string | undefined)?.trim() || ''
const ACTIONS_URL =
  (import.meta.env.VITE_ACTIONS_URL as string | undefined)?.trim() ||
  'https://github.com/Y0112358/CostDistribution/actions/workflows/dashboard.yml'

const POLL_MS = 15_000
const MAX_POLLS = 12 // 12 × 15s = 3 分鐘

type State = 'idle' | 'pending' | 'updating' | 'ok' | 'error'

function sleep(ms: number) {
  return new Promise((r) => setTimeout(r, ms))
}

export default function UpdateButton() {
  const [state, setState] = useState<State>('idle')

  async function fetchGeneratedAt(): Promise<string | null> {
    try {
      const r = await fetch(`data/meta.json?t=${Date.now()}`)
      if (!r.ok) return null
      const m = await r.json()
      return typeof m.generated_at === 'string' ? m.generated_at : null
    } catch {
      return null
    }
  }

  // 輪詢 meta.json 的 generated_at，偵測到比點擊時更新就自動重整
  async function waitForUpdate(startedAt: number) {
    for (let i = 0; i < MAX_POLLS; i++) {
      await sleep(POLL_MS)
      const now = await fetchGeneratedAt()
      if (now == null) continue
      const t = Date.parse(now)
      if (!Number.isNaN(t) && t > startedAt) {
        window.location.reload()
        return
      }
    }
    setState('ok') // 3 分鐘未更新，停下來讓使用者手動
  }

  async function trigger() {
    setState('pending')
    try {
      const startedAt = Date.now()
      const r = await fetch(UPDATE_URL, { method: 'POST' })
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      setState('updating')
      void waitForUpdate(startedAt)
    } catch (e) {
      console.error(e)
      setState('error')
    }
  }

  const base =
    'rounded-lg px-3 py-1.5 text-[12px] font-medium transition-colors disabled:opacity-60'

  if (!UPDATE_URL) {
    return (
      <a
        href={ACTIONS_URL}
        target="_blank"
        rel="noreferrer"
        className={`${base} bg-sky-600 text-white hover:bg-sky-500`}
      >
        更新資料
      </a>
    )
  }

  return (
    <div className="flex items-center gap-2">
      <button
        onClick={trigger}
        disabled={state === 'pending' || state === 'updating'}
        className={`${base} ${
          state === 'error'
            ? 'bg-red-800 text-white hover:bg-red-700'
            : 'bg-sky-600 text-white hover:bg-sky-500'
        }`}
      >
        {state === 'pending'
          ? '觸發中…'
          : state === 'updating'
          ? '已觸發，重整中…'
          : state === 'ok'
          ? '已觸發 ✓'
          : state === 'error'
          ? '失敗，重試'
          : '更新資料'}
      </button>
      {state === 'updating' && (
        <span className="text-[11px] text-slate-500">已觸發，資料更新後將自動重整頁面…</span>
      )}
      {state === 'ok' && (
        <span className="text-[11px] text-slate-500">資料未在 3 分鐘內更新，可手動重整頁面</span>
      )}
      {state === 'error' && (
        <span className="text-[11px] text-slate-500">觸發失敗，請確認 Worker 設定</span>
      )}
    </div>
  )
}

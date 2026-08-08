import { useState } from 'react'

type State = 'idle' | 'pending' | 'ok' | 'error'

const UPDATE_URL = (import.meta.env.VITE_UPDATE_URL as string | undefined)?.trim() || ''
const ACTIONS_URL =
  (import.meta.env.VITE_ACTIONS_URL as string | undefined)?.trim() ||
  'https://github.com/OWNER/REPO/actions/workflows/dashboard.yml'

export default function UpdateButton() {
  const [state, setState] = useState<State>('idle')

  async function trigger() {
    setState('pending')
    try {
      const r = await fetch(UPDATE_URL, { method: 'POST' })
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      setState('ok')
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
        disabled={state === 'pending'}
        className={`${base} ${
          state === 'error'
            ? 'bg-red-800 text-white hover:bg-red-700'
            : 'bg-sky-600 text-white hover:bg-sky-500'
        }`}
      >
        {state === 'pending' ? '觸發中…' : state === 'ok' ? '已觸發 ✓' : state === 'error' ? '失敗，重試' : '更新資料'}
      </button>
      {(state === 'ok' || state === 'error') && (
        <span className="text-[11px] text-slate-500">
          幾分鐘後資料會更新，可稍後重整頁面
        </span>
      )}
    </div>
  )
}

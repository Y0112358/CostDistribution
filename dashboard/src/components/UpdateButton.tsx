import type { UpdateState } from '../useUpdate'

const ACTIONS_URL =
  (import.meta.env.VITE_ACTIONS_URL as string | undefined)?.trim() ||
  'https://github.com/Y0112358/CostDistribution/actions/workflows/dashboard.yml'

const hasUpdateUrl = (import.meta.env.VITE_UPDATE_URL as string | undefined)?.trim() !== ''

interface Props {
  state: UpdateState
  onUpdate: () => void
}

export default function UpdateButton({ state, onUpdate }: Props) {
  const base =
    'rounded-lg px-3 py-1.5 text-[12px] font-medium transition-colors disabled:opacity-60'

  if (!hasUpdateUrl) {
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

  const busy = state === 'pending' || state === 'updating'

  return (
    <div className="flex items-center gap-2">
      <button
        onClick={onUpdate}
        disabled={busy}
        className={`${base} ${
          state === 'error'
            ? 'bg-red-800 text-white hover:bg-red-700'
            : 'bg-sky-600 text-white hover:bg-sky-500'
        }`}
      >
        {state === 'pending'
          ? '觸發中…'
          : state === 'updating'
          ? '更新中…'
          : state === 'ok'
          ? '已更新 ✓'
          : state === 'error'
          ? '失敗，重試'
          : '更新資料'}
      </button>
      {state === 'error' && (
        <span className="text-[11px] text-slate-500">觸發失敗，請確認 Worker 設定</span>
      )}
    </div>
  )
}

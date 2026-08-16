import type { Signal } from '../types'

interface Props {
  signals: Signal[]
}

const LEVEL_STYLE: Record<string, { icon: string; cls: string }> = {
  warning: { icon: '⚠️', cls: 'border-amber-700/50 bg-amber-950/40 text-amber-200' },
  danger: { icon: '⚠️', cls: 'border-red-800/60 bg-red-950/40 text-red-200' },
  success: { icon: '✅', cls: 'border-emerald-700/50 bg-emerald-950/40 text-emerald-200' },
}

export default function SignalPanel({ signals }: Props) {
  if (signals.length === 0) return null

  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900/60">
      <div className="border-b border-slate-800 px-3 py-2 text-sm font-semibold text-slate-200">
        輪動訊號解讀
      </div>
      <div className="flex flex-wrap gap-2 p-3">
        {signals.map((s, i) => {
          const st = LEVEL_STYLE[s.level] ?? LEVEL_STYLE.warning
          return (
            <div
              key={i}
              className={`rounded-md border px-3 py-1.5 text-[12px] ${st.cls}`}
            >
              <span className="mr-1">{st.icon}</span>
              {s.text}
            </div>
          )
        })}
      </div>
    </div>
  )
}

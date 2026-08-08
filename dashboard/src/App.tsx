import { useCallback, useEffect, useState } from 'react'
import { loadDashboard } from './api'
import type { Loaded } from './api'
import type { TF } from './types'
import { makeColorOf } from './colors'
import UpdateButton from './components/UpdateButton'
import RankTable from './components/RankTable'
import TimeframeRow from './components/TimeframeRow'
import YearlyPanel from './components/YearlyPanel'
import RRGChart from './components/RRGChart'
import type { RrgTF } from './components/RRGChart'
import ThemeDrawer from './components/ThemeDrawer'

type Tab = 'dashboard' | 'yearly'
interface Sel {
  theme: string
  tf: TF
}

function fmtTs(s: string | null): string {
  if (!s) return '—'
  return s.replace('T', ' ').slice(0, 16)
}

export default function App() {
  const [data, setData] = useState<Loaded | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [tab, setTab] = useState<Tab>('dashboard')
  const [rrgTf, setRrgTf] = useState<RrgTF>('1m')
  const [sel, setSel] = useState<Sel | null>(null)

  useEffect(() => {
    let alive = true
    loadDashboard()
      .then((d) => {
        if (alive) setData(d)
      })
      .catch((e) => {
        if (alive) setError(String(e?.message ?? e))
      })
    return () => {
      alive = false
    }
  }, [])

  const colorOf = useCallback((name: string) => makeColorOf(data?.meta.themes ?? [])(name), [data])

  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center p-6">
        <div className="rounded-lg border border-red-900 bg-red-950/40 p-6 text-sm text-red-300">
          <p className="mb-2 font-semibold">資料載入失敗</p>
          <p>{error}</p>
          <p className="mt-2 text-red-400/70">請確認 data/*.json 已由 export_dashboard.py 產生</p>
        </div>
      </div>
    )
  }

  if (!data) {
    return (
      <div className="flex min-h-screen items-center justify-center text-sm text-slate-400">
        <span className="animate-pulse">載入儀表板資料…</span>
      </div>
    )
  }

  const themes = data.meta.themes

  return (
    <div className="mx-auto max-w-7xl px-4 py-4">
      {/* header */}
      <header className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-bold text-slate-100">主題輪動儀表板</h1>
          <p className="mt-0.5 text-[11px] text-slate-500">
            資料至 {data.meta.data_daily_through}
            {data.meta.intraday_last_ts ? ` · 盤中至 ${data.meta.intraday_last_ts} · 生成 ${fmtTs(data.meta.generated_at)}` : ''}
            {' '}· 基準 {data.themesConfig.benchmark}
          </p>
        </div>
        <div className="flex items-center gap-3">
          {data.meta.intraday_fresh && (
            <span className="rounded-full bg-emerald-900/50 px-2 py-0.5 text-[11px] text-emerald-300">盤中資料新鮮</span>
          )}
          <UpdateButton />
        </div>
      </header>

      {/* tabs */}
      <nav className="mb-3 flex gap-1">
        {(
          [
            ['dashboard', '儀表板'],
            ['yearly', '一年長期'],
          ] as [Tab, string][]
        ).map(([k, label]) => (
          <button
            key={k}
            onClick={() => setTab(k)}
            className={`rounded-t-lg px-4 py-2 text-[13px] font-medium ${
              tab === k
                ? 'border border-b-0 border-slate-800 bg-slate-900/60 text-slate-100'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            {label}
          </button>
        ))}
      </nav>

      {tab === 'dashboard' ? (
        <div className="space-y-3">
          <RankTable rows={data.latest} onSelect={(theme) => setSel({ theme, tf: '1m' })} />
          <TimeframeRow data={data} colorOf={colorOf} onSelect={(theme, tf) => setSel({ theme, tf })} />
          <RRGChart
            rrg={data.rrg}
            tf={rrgTf}
            onTf={setRrgTf}
            themes={themes}
            colorOf={colorOf}
            onSelect={(theme) => setSel({ theme, tf: rrgTf })}
          />
          <p className="text-center text-[11px] text-slate-600">點圖上的線或排名列 → 查看該主題的分數與成分股明細</p>
        </div>
      ) : (
        <YearlyPanel data={data} colorOf={colorOf} onSelect={(theme) => setSel({ theme, tf: '1y' })} />
      )}

      {sel && (
        <ThemeDrawer
          theme={sel.theme}
          tf={sel.tf}
          data={data}
          onClose={() => setSel(null)}
          onTf={(tf) => setSel({ theme: sel.theme, tf })}
        />
      )}
    </div>
  )
}

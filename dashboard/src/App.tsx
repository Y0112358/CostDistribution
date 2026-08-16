import { useCallback, useEffect, useMemo, useState } from 'react'
import { loadDashboard } from './api'
import type { DashboardData, TF } from './types'
import { makeColorOf } from './colors'
import { useUpdateData } from './useUpdate'
import UpdateButton from './components/UpdateButton'
import RankTable from './components/RankTable'
import TimeframeRow from './components/TimeframeRow'
import YearlyPanel from './components/YearlyPanel'
import RRGChart from './components/RRGChart'
import type { RrgTF } from './components/RRGChart'
import ThemeDrawer from './components/ThemeDrawer'
import ThemeFilter from './components/ThemeFilter'
import DataLegend from './components/DataLegend'
import SignalPanel from './components/SignalPanel'

type Tab = 'dashboard' | 'yearly'
interface Sel {
  theme: string
  tf: TF
}

function fmtTs(s: string | null): string {
  if (!s) return '—'
  const d = new Date(s)
  if (Number.isNaN(d.getTime())) return s
  return d.toLocaleString('zh-TW', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

export default function App() {
  const [data, setData] = useState<DashboardData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [tab, setTab] = useState<Tab>('dashboard')
  const [rrgTf, setRrgTf] = useState<RrgTF>('1m')
  const [sel, setSel] = useState<Sel | null>(null)
  const [hidden, setHidden] = useState<Set<string>>(new Set())
  const [autoUpdate, setAutoUpdate] = useState<boolean>(() => {
    try {
      return localStorage.getItem('autoUpdate') !== 'off'
    } catch {
      return true
    }
  })

  const toggleTheme = useCallback((name: string) => {
    setHidden((prev) => {
      const next = new Set(prev)
      if (next.has(name)) next.delete(name)
      else next.add(name)
      return next
    })
  }, [])

  const load = useCallback(async () => {
    try {
      const d = await loadDashboard()
      setData(d)
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  // 共用更新流程：refreshData = 就地更新資料（背景模式用）
  const { state: updateState, runUpdate } = useUpdateData(load)

  const toggleAuto = useCallback(() => {
    setAutoUpdate((v) => {
      const nv = !v
      try {
        localStorage.setItem('autoUpdate', nv ? 'on' : 'off')
      } catch {
        /* ignore */
      }
      return nv
    })
  }, [])

  // 背景每小時自動更新（頁面開啟期間；就地更新，不重整頁面）
  useEffect(() => {
    if (!autoUpdate) return
    const id = setInterval(() => {
      void runUpdate('inplace')
    }, 60 * 60 * 1000)
    return () => clearInterval(id)
  }, [autoUpdate, runUpdate])

  // 下次自動更新時間（每小時）
  const nextAuto = useMemo(() => {
    const d = new Date(Date.now() + 60 * 60 * 1000)
    return d.toLocaleTimeString('zh-TW', { hour: '2-digit', minute: '2-digit' })
  }, [data?.meta.generated_at])

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
            {autoUpdate && ` · 下次自動更新約 ${nextAuto}`}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {data.meta.intraday_fresh && (
            <span className="rounded-full bg-emerald-900/50 px-2 py-0.5 text-[11px] text-emerald-300">盤中資料新鮮</span>
          )}
          {updateState === 'updating' && (
            <span className="animate-pulse text-[11px] text-slate-400">更新中…</span>
          )}
          <button
            onClick={toggleAuto}
            title="開啟後，頁面開著期間每小時自動更新資料"
            className={`rounded-full px-2 py-0.5 text-[11px] transition-colors ${
              autoUpdate ? 'bg-emerald-900/50 text-emerald-300' : 'bg-slate-800 text-slate-500'
            }`}
          >
            每小時自動更新 {autoUpdate ? 'ON' : 'OFF'}
          </button>
          <UpdateButton state={updateState} onUpdate={() => void runUpdate('reload')} />
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
          <SignalPanel signals={data.signals} />
          <ThemeFilter
            themes={themes}
            hidden={hidden}
            onToggle={toggleTheme}
            onShowAll={() => setHidden(new Set())}
            onHideAll={() => setHidden(new Set(themes))}
            colorOf={colorOf}
          />
          <RankTable rows={data.latest} onSelect={(theme) => setSel({ theme, tf: '1m' })} />
          <TimeframeRow data={data} colorOf={colorOf} hidden={hidden} onSelect={(theme, tf) => setSel({ theme, tf })} />
          <RRGChart
            rrg={data.rrg}
            tf={rrgTf}
            onTf={setRrgTf}
            themes={themes}
            colorOf={colorOf}
            hidden={hidden}
            onSelect={(theme) => setSel({ theme, tf: rrgTf })}
          />
          <DataLegend themesConfig={data.themesConfig} colorOf={colorOf} />
          <p className="text-center text-[11px] text-slate-600">點圖上的線或排名列 → 查看該主題的分數與成分股明細</p>
        </div>
      ) : (
        <>
          <ThemeFilter
            themes={themes}
            hidden={hidden}
            onToggle={toggleTheme}
            onShowAll={() => setHidden(new Set())}
            onHideAll={() => setHidden(new Set(themes))}
            colorOf={colorOf}
          />
          <YearlyPanel data={data} colorOf={colorOf} hidden={hidden} onSelect={(theme) => setSel({ theme, tf: '1y' })} />
        </>
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

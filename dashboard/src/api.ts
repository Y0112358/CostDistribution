import type {
  HistoryDaily,
  Intraday1w,
  LatestRow,
  Meta,
  RrgData,
  Signal,
  StockDaily,
  StockIntraday,
  ThemeConfig,
} from './types'

async function j<T>(f: string): Promise<T> {
  const r = await fetch(`data/${f}`)
  if (!r.ok) throw new Error(`${f}: HTTP ${r.status}`)
  return r.json() as Promise<T>
}

export async function loadDashboard() {
  const [meta, themesConfig, history, rrg, latest, signals, stockDaily, intraday, stockIntraday] = await Promise.all([
    j<Meta>('meta.json'),
    j<{ benchmark: string; themes: Record<string, ThemeConfig> }>('themes.json'),
    j<HistoryDaily>('history_daily.json'),
    j<RrgData>('rrg.json'),
    j<LatestRow[]>('latest.json'),
    j<Signal[]>('signals.json').catch(() => []),
    j<StockDaily>('stock_daily.json'),
    j<Intraday1w>('intraday_1w.json').catch(() => null),
    j<StockIntraday>('stock_intraday.json').catch(() => null),
  ])
  return { meta, themesConfig, history, rrg, latest, signals, stockDaily, intraday, stockIntraday }
}

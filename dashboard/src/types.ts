export type TF = '1m' | '2w' | '1w' | '1y'

export interface ThemeConfig {
  type: string
  tickers: string[]
}

export type NumArr = (number | null)[]

export interface HistoryDaily {
  themes: string[]
  dates: string[]
  composite: Record<string, NumArr>
  d1: Record<string, NumArr>
  d2: Record<string, NumArr>
  d3: Record<string, NumArr>
  d4: Record<string, NumArr>
  rsr: Record<string, NumArr>
  rsm: Record<string, NumArr>
}

export interface Intraday1w {
  days: string[]
  bars: string[]
  composite: Record<string, NumArr>
  d1: Record<string, NumArr>
  d2: Record<string, NumArr>
  d3: Record<string, NumArr>
  d4: Record<string, NumArr>
  rsr: Record<string, NumArr>
  rsm: Record<string, NumArr>
  breadth: Record<string, NumArr>
}

export interface RrgEntry {
  dates: string[]
  rs_ratio: Record<string, NumArr>
  rs_momentum: Record<string, NumArr>
}

export interface RrgData {
  '1m': RrgEntry
  '2w': RrgEntry
  '1w': RrgEntry
}

export interface LatestRow {
  rank: number
  theme: string
  composite: number
  d1: number
  d2: number
  d3: number
  d4: number
  dvol_share: number
  rs_ratio: number
  rs_momentum: number
  w1_change: number | null
  m1_change: number | null
}

export interface StockTickerDaily {
  dates: string[]
  close: NumArr
  adj: NumArr
  volume: NumArr
  ma20: NumArr
  ma50: NumArr
  ma200: NumArr
  cmf20: NumArr
  above: boolean[][]
}
export type StockDaily = Record<string, Record<string, StockTickerDaily>>

export interface StockTickerIntraday {
  ts: string[]
  close: NumArr
  volume: NumArr
}
export type StockIntraday = Record<string, Record<string, StockTickerIntraday>>

export interface Meta {
  generated_at: string
  themes: string[]
  data_daily_through: string
  daily_fresh: boolean
  intraday_last_ts: string | null
  intraday_fresh: boolean
}

export interface DashboardData {
  meta: Meta
  themesConfig: { benchmark: string; themes: Record<string, ThemeConfig> }
  history: HistoryDaily
  rrg: RrgData
  latest: LatestRow[]
  stockDaily: StockDaily
  intraday: Intraday1w | null
  stockIntraday: StockIntraday | null
}

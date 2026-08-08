import type { DashboardData, NumArr, TF } from './types'

export interface SeriesDef {
  name: string
  data: NumArr
}

/** 日線切窗：1m 尾 21、2w 尾 10、1y 全部 */
export function dailyComposite(d: DashboardData, tf: '1m' | '2w' | '1y') {
  const n = tf === '1m' ? 21 : tf === '2w' ? 10 : d.history.dates.length
  const labels = d.history.dates.slice(-n)
  const series: SeriesDef[] = d.history.themes.map((th) => ({
    name: th,
    data: d.history.composite[th].slice(-n),
  }))
  return { labels, series }
}

export function intradayComposite(d: DashboardData) {
  if (!d.intraday) return { labels: [] as string[], series: [] as SeriesDef[] }
  const intra = d.intraday
  const series: SeriesDef[] = d.history.themes.map((th) => ({
    name: th,
    data: intra.composite[th],
  }))
  return { labels: intra.bars, series }
}

export interface ThemeSeries {
  labels: string[]
  composite: NumArr
  d1: NumArr
  d2: NumArr
  d3: NumArr
  rsr: NumArr
  rsm: NumArr
  breadth: NumArr | null
}

/** 單一主題在指定時間框架下的全部分數序列（明細表用） */
export function themeSeriesFor(d: DashboardData, tf: TF, theme: string): ThemeSeries {
  if (tf === '1w' && d.intraday) {
    const i = d.intraday
    return {
      labels: i.bars,
      composite: i.composite[theme],
      d1: i.d1[theme],
      d2: i.d2[theme],
      d3: i.d3[theme],
      rsr: i.rsr[theme],
      rsm: i.rsm[theme],
      breadth: i.breadth[theme] ?? null,
    }
  }
  const n = tf === '1m' ? 21 : tf === '2w' ? 10 : d.history.dates.length
  const end = d.history.dates.length
  const start = end - n
  const slice = (a: NumArr) => a.slice(start)
  const h = d.history
  return {
    labels: h.dates.slice(start),
    composite: slice(h.composite[theme]),
    d1: slice(h.d1[theme]),
    d2: slice(h.d2[theme]),
    d3: slice(h.d3[theme]),
    rsr: slice(h.rsr[theme]),
    rsm: slice(h.rsm[theme]),
    breadth: null,
  }
}

export function sma(arr: NumArr, w: number): NumArr {
  const out: NumArr = []
  for (let i = 0; i < arr.length; i++) {
    if (i < w - 1) {
      out.push(null)
      continue
    }
    let s = 0
    let c = 0
    for (let k = i - w + 1; k <= i; k++) {
      const v = arr[k]
      if (v != null) {
        s += v
        c++
      }
    }
    out.push(c > 0 ? s / c : null)
  }
  return out
}

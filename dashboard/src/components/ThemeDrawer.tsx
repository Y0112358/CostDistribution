import type { DashboardData, TF } from '../types'
import { themeSeriesFor } from '../slice'
import { fmt, fmtVol } from '../format'

interface Props {
  theme: string
  tf: TF
  data: DashboardData
  onClose: () => void
  onTf: (tf: TF) => void
}

const TFS: { tf: TF; label: string }[] = [
  { tf: '1m', label: '1月' },
  { tf: '2w', label: '2週' },
  { tf: '1w', label: '1週' },
  { tf: '1y', label: '1年' },
]

export default function ThemeDrawer({ theme, tf, data, onClose, onTf }: Props) {
  const series = themeSeriesFor(data, tf, theme)
  const isIntra = tf === '1w' && data.intraday != null
  const showBreadth = isIntra && series.breadth != null

  // 分數明細：只取最後 120 列
  const cap = 120
  const start = Math.max(0, series.labels.length - cap)
  const labels = series.labels.slice(start)
  const cols = (a: (number | null)[]) => a.slice(start)
  const scoreRows = labels.map((l, i) => ({
    label: l,
    composite: cols(series.composite)[i],
    d1: cols(series.d1)[i],
    d2: cols(series.d2)[i],
    d3: cols(series.d3)[i],
    d4: cols(series.d4)[i],
    rsr: cols(series.rsr)[i],
    rsm: cols(series.rsm)[i],
    brd: showBreadth ? cols(series.breadth ?? [])[i] : null,
  }))

  const stockTickers = data.themesConfig.themes[theme]?.tickers ?? []
  const isStockIntra = isIntra && data.stockIntraday != null

  return (
    <div className="fixed inset-0 z-50">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <aside className="absolute inset-y-0 right-0 flex w-full max-w-2xl flex-col border-l border-slate-700 bg-slate-950 shadow-2xl">
        {/* header */}
        <div className="flex items-center justify-between border-b border-slate-800 px-4 py-3">
          <div className="flex items-baseline gap-3">
            <span className="text-base font-semibold text-slate-100">{theme}</span>
            <div className="flex gap-1">
              {TFS.map(({ tf: k, label }) => (
                <button
                  key={k}
                  onClick={() => onTf(k)}
                  className={`rounded px-2 py-0.5 text-[11px] ${
                    tf === k ? 'bg-sky-600 text-white' : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
          <button onClick={onClose} className="rounded px-2 py-1 text-slate-400 hover:bg-slate-800 hover:text-slate-200">
            ✕
          </button>
        </div>

        <div className="flex flex-wrap gap-2 px-4 py-2 text-[11px] text-slate-500">
          <span className="rounded bg-slate-800 px-2 py-0.5">綜合 = 0.30×D1 + 0.40×D2 + 0.30×D3</span>
          {isIntra && <span className="rounded bg-slate-800 px-2 py-0.5">5m 盤中</span>}
          <span className="rounded bg-slate-800 px-2 py-0.5">
            成分股：{data.themesConfig.themes[theme]?.tickers.join(', ') ?? '—'}
          </span>
        </div>

        {/* body */}
        <div className="flex-1 overflow-y-auto px-3 pb-6">
          {/* 分數明細 */}
          <div className="mt-3 rounded-lg border border-slate-800 bg-slate-900/60">
            <div className="border-b border-slate-800 px-3 py-1.5 text-[12px] font-semibold text-slate-200">分數明細</div>
            <div className="overflow-x-auto">
              <table className="w-full text-[11px]">
                <thead>
                  <tr className="text-slate-500">
                    <th className="px-2 py-1.5 text-left font-medium">{isIntra ? '時間' : '日期'}</th>
                    <th className="px-2 py-1.5 text-right font-medium">綜合</th>
                    <th className="px-2 py-1.5 text-right font-medium">D1資金</th>
                    <th className="px-2 py-1.5 text-right font-medium">D2強度</th>
                    <th className="px-2 py-1.5 text-right font-medium">D3一致</th>
                    <th className="px-2 py-1.5 text-right font-medium">D4絕對</th>
                    <th className="px-2 py-1.5 text-right font-medium">RS-Ratio</th>
                    <th className="px-2 py-1.5 text-right font-medium">RS-Mom</th>
                    {showBreadth && <th className="px-2 py-1.5 text-right font-medium">一致%</th>}
                  </tr>
                </thead>
                <tbody>
                  {scoreRows.map((r, i) => (
                    <tr key={i} className="border-t border-slate-800/50 hover:bg-slate-800/40">
                      <td className="px-2 py-1 text-slate-400">{r.label}</td>
                      <td className="px-2 py-1 text-right font-medium text-sky-300">{fmt(r.composite)}</td>
                      <td className="px-2 py-1 text-right text-slate-300">{fmt(r.d1)}</td>
                      <td className="px-2 py-1 text-right text-slate-300">{fmt(r.d2)}</td>
                      <td className="px-2 py-1 text-right text-slate-300">{fmt(r.d3)}</td>
                      <td className="px-2 py-1 text-right text-slate-300">{fmt(r.d4)}</td>
                      <td className="px-2 py-1 text-right text-slate-300">{fmt(r.rsr)}</td>
                      <td className="px-2 py-1 text-right text-slate-300">{fmt(r.rsm)}</td>
                      {showBreadth && <td className="px-2 py-1 text-right text-slate-300">{fmt(r.brd)}</td>}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* 成分股明細 */}
          <div className="mt-3 rounded-lg border border-slate-800 bg-slate-900/60">
            <div className="border-b border-slate-800 px-3 py-1.5 text-[12px] font-semibold text-slate-200">成分股明細</div>
            {stockTickers.map((tk) =>
              isStockIntra ? (
                <TickerIntraTable key={tk} ticker={tk} data={data} theme={theme} />
              ) : (
                <TickerDailyTable key={tk} ticker={tk} data={data} theme={theme} />
              ),
            )}
            {stockTickers.length === 0 && <div className="px-3 py-4 text-[12px] text-slate-500">無成分股資料</div>}
          </div>
        </div>
      </aside>
    </div>
  )
}

function TickerDailyTable({ ticker, data, theme }: { ticker: string; data: DashboardData; theme: string }) {
  const st = data.stockDaily[theme]?.[ticker]
  if (!st) return null
  const rows = st.dates.map((d, i) => ({
    d,
    close: st.close[i],
    adj: st.adj[i],
    vol: st.volume[i],
    ma20: st.ma20[i],
    ma50: st.ma50[i],
    ma200: st.ma200[i],
    cmf: st.cmf20[i],
    above: st.above[i] ?? [],
  }))
  return (
    <div className="border-t border-slate-800/50">
      <div className="px-3 py-1.5 text-[12px] font-medium text-sky-400">{ticker}</div>
      <div className="overflow-x-auto">
        <table className="w-full text-[10px]">
          <thead>
            <tr className="text-slate-500">
              <th className="px-2 py-1 text-left font-medium">日期</th>
              <th className="px-2 py-1 text-right font-medium">收盤</th>
              <th className="px-2 py-1 text-right font-medium">調整</th>
              <th className="px-2 py-1 text-right font-medium">量</th>
              <th className="px-2 py-1 text-right font-medium">MA20</th>
              <th className="px-2 py-1 text-right font-medium">MA50</th>
              <th className="px-2 py-1 text-right font-medium">MA200</th>
              <th className="px-2 py-1 text-right font-medium">CMF20</th>
              <th className="px-2 py-1 text-center font-medium">↑20</th>
              <th className="px-2 py-1 text-center font-medium">↑50</th>
              <th className="px-2 py-1 text-center font-medium">↑200</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i} className="border-t border-slate-800/40 hover:bg-slate-800/40">
                <td className="px-2 py-1 text-slate-400">{r.d}</td>
                <td className="px-2 py-1 text-right text-slate-200">{fmt(r.close, 2)}</td>
                <td className="px-2 py-1 text-right text-slate-400">{fmt(r.adj, 2)}</td>
                <td className="px-2 py-1 text-right text-slate-400">{fmtVol(r.vol)}</td>
                <td className="px-2 py-1 text-right text-slate-300">{fmt(r.ma20, 2)}</td>
                <td className="px-2 py-1 text-right text-slate-300">{fmt(r.ma50, 2)}</td>
                <td className="px-2 py-1 text-right text-slate-300">{fmt(r.ma200, 2)}</td>
                <td className="px-2 py-1 text-right text-slate-300">{fmt(r.cmf, 2)}</td>
                <td className="px-2 py-1 text-center"><Flag good={r.above[0]} /></td>
                <td className="px-2 py-1 text-center"><Flag good={r.above[1]} /></td>
                <td className="px-2 py-1 text-center"><Flag good={r.above[2]} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function TickerIntraTable({ ticker, data, theme }: { ticker: string; data: DashboardData; theme: string }) {
  const st = data.stockIntraday?.[theme]?.[ticker]
  if (!st) return null
  const start = Math.max(0, st.ts.length - 39)
  return (
    <div className="border-t border-slate-800/50">
      <div className="px-3 py-1.5 text-[12px] font-medium text-sky-400">{ticker}</div>
      <div className="overflow-x-auto">
        <table className="w-full text-[10px]">
          <thead>
            <tr className="text-slate-500">
              <th className="px-2 py-1 text-left font-medium">時間</th>
              <th className="px-2 py-1 text-right font-medium">收盤</th>
              <th className="px-2 py-1 text-right font-medium">量</th>
            </tr>
          </thead>
          <tbody>
            {st.ts.slice(start).map((ts, i) => (
              <tr key={i} className="border-t border-slate-800/40 hover:bg-slate-800/40">
                <td className="px-2 py-1 text-slate-400">{ts}</td>
                <td className="px-2 py-1 text-right text-slate-200">{fmt(st.close[start + i], 2)}</td>
                <td className="px-2 py-1 text-right text-slate-400">{fmtVol(st.volume[start + i])}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function Flag({ good }: { good?: boolean }) {
  return <span className={good ? 'text-emerald-400' : 'text-red-400/70'}>{good ? '✓' : '✕'}</span>
}

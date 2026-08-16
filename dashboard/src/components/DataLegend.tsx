import { useState } from 'react'
import type { ThemeConfig } from '../types'

interface Props {
  themesConfig: { benchmark: string; themes: Record<string, ThemeConfig> }
  colorOf: (name: string) => string
}

const FORMULA: { name: string; text: string }[] = [
  { name: '綜合分數', text: '0.25×D1資金 + 0.30×D2相對強度 + 0.25×D3一致性 + 0.20×D4絕對強度' },
  { name: 'D1 資金權重', text: '0.60 × 成交額佔比(百分位) + 0.40 × 成交量佔比(百分位)' },
  { name: 'D2 族群強度', text: '0.50 × RS-Ratio(百分位) + 0.50 × RS-Momentum(百分位)' },
  { name: 'D3 一致性', text: '成分股站上 20/50/200 日均線比例 + 20 日正報酬比例（ETF 主題設中性 50）' },
  { name: 'D4 絕對強度', text: 'RS-Ratio 原始值映射（>100 真強、<100 真弱），補相對排名看不出絕對強弱' },
]

export default function DataLegend({ themesConfig, colorOf }: Props) {
  const [open, setOpen] = useState(false)
  const bench = themesConfig.benchmark

  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900/60">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between px-3 py-2 text-[13px] font-semibold text-slate-200 hover:bg-slate-800/40"
      >
        <span>📊 資料說明 — 每條線怎麼算出來的</span>
        <span className="text-slate-500">{open ? '▲ 收合' : '▼ 展開'}</span>
      </button>

      {open && (
        <div className="space-y-3 border-t border-slate-800 px-4 py-3 text-[12px] text-slate-300">
          <div className="rounded-md bg-slate-800/50 p-3">
            <div className="mb-1 font-semibold text-slate-200">計分公式</div>
            {FORMULA.map((f) => (
              <div key={f.name} className="mb-1">
                <span className="inline-block w-32 text-slate-400">{f.name}</span>
                <code className="text-sky-300">{f.text}</code>
              </div>
            ))}
            <div className="mt-2 border-t border-slate-700/60 pt-2 text-slate-400">
              基準：{bench}（RS 相對強度與成交額佔比的比較基準）
            </div>
          </div>

          <div className="rounded-md bg-slate-800/50 p-3">
            <div className="mb-2 font-semibold text-slate-200">各主題資料來源（成分股）</div>
            <div className="grid grid-cols-1 gap-1 sm:grid-cols-2">
              {Object.entries(themesConfig.themes).map(([name, cfg]) => (
                <div key={name} className="flex items-center gap-2">
                  <span className="inline-block h-2.5 w-2.5 shrink-0 rounded-full" style={{ backgroundColor: colorOf(name) }} />
                  <span className="w-24 shrink-0 text-slate-200">{name}</span>
                  <code className="text-[11px] text-slate-400">
                    {cfg.type === 'etf' ? `ETF：${cfg.tickers.join(', ')}` : cfg.tickers.join(', ')}
                  </code>
                </div>
              ))}
            </div>
          </div>

          <p className="text-[11px] text-slate-500">
            盤中（近 1 週）的線以 5 分鐘成交額/價格計算，慢速上下文（MA、CMF-20、RS 平滑）取自 1 年日線，
            收盤時收斂到日頻分數。
          </p>
        </div>
      )}
    </div>
  )
}

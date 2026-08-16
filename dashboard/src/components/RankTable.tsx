import type { LatestRow } from '../types'
import { change, changeCls, fmt } from '../format'

interface Props {
  rows: LatestRow[]
  onSelect: (theme: string) => void
}

export default function RankTable({ rows, onSelect }: Props) {
  return (
    <div className="overflow-hidden rounded-lg border border-slate-800 bg-slate-900/60">
      <div className="border-b border-slate-800 px-3 py-2 text-sm font-semibold text-slate-200">主題排名</div>
      <div className="overflow-x-auto">
        <table className="w-full text-[12px]">
          <thead>
            <tr className="text-left text-slate-500">
              <th className="px-3 py-2 font-medium">#</th>
              <th className="px-3 py-2 font-medium">主題</th>
              <th className="px-3 py-2 text-right font-medium">綜合</th>
              <th className="px-3 py-2 text-right font-medium">D1 資金</th>
              <th className="px-3 py-2 text-right font-medium">D2 強度</th>
              <th className="px-3 py-2 text-right font-medium">D3 一致</th>
              <th className="px-3 py-2 text-right font-medium">D4 絕對</th>
              <th className="px-3 py-2 text-right font-medium">成交額%</th>
              <th className="px-3 py-2 text-right font-medium">RS-Ratio</th>
              <th className="px-3 py-2 text-right font-medium">RS-Mom</th>
              <th className="px-3 py-2 text-right font-medium">1週</th>
              <th className="px-3 py-2 text-right font-medium">1月</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr
                key={r.theme}
                onClick={() => onSelect(r.theme)}
                className={`cursor-pointer border-t border-slate-800/60 hover:bg-slate-800/50 ${
                  i === 0 ? 'bg-sky-950/40' : ''
                }`}
              >
                <td className="px-3 py-1.5 text-slate-400">{r.rank}</td>
                <td className="px-3 py-1.5 font-medium text-slate-100">{r.theme}</td>
                <td className="px-3 py-1.5 text-right font-semibold text-sky-300">{fmt(r.composite)}</td>
                <td className="px-3 py-1.5 text-right text-slate-300">{fmt(r.d1)}</td>
                <td className="px-3 py-1.5 text-right text-slate-300">{fmt(r.d2)}</td>
                <td className="px-3 py-1.5 text-right text-slate-300">{fmt(r.d3)}</td>
                <td className="px-3 py-1.5 text-right text-slate-300">{fmt(r.d4)}</td>
                <td className="px-3 py-1.5 text-right text-slate-300">{fmt(r.dvol_share)}</td>
                <td className="px-3 py-1.5 text-right text-slate-300">{fmt(r.rs_ratio)}</td>
                <td className="px-3 py-1.5 text-right text-slate-300">{fmt(r.rs_momentum)}</td>
                <td className={`px-3 py-1.5 text-right ${changeCls(r.w1_change)}`}>{change(r.w1_change)}</td>
                <td className={`px-3 py-1.5 text-right ${changeCls(r.m1_change)}`}>{change(r.m1_change)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

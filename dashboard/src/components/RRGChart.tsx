import { useMemo } from 'react'
import type { EChartsOption } from 'echarts'
import Chart from './Chart'
import type { RrgData } from '../types'

export type RrgTF = '1m' | '2w' | '1w'

interface Props {
  rrg: RrgData
  tf: RrgTF
  onTf: (tf: RrgTF) => void
  themes: string[]
  colorOf: (name: string) => string
  onSelect: (theme: string) => void
}

const TF_LABEL: Record<RrgTF, string> = { '1m': '近 1 月', '2w': '近 2 週', '1w': '近 1 週' }

export default function RRGChart({ rrg, tf, onTf, themes, colorOf, onSelect }: Props) {
  const option = useMemo<EChartsOption>(() => {
    const entry = rrg[tf]
    const series: any[] = []
    themes.forEach((th) => {
      const xs = entry.rs_ratio[th] ?? []
      const ys = entry.rs_momentum[th] ?? []
      const pts: [number, number][] = []
      for (let i = 0; i < xs.length; i++) {
        if (xs[i] != null && ys[i] != null) pts.push([xs[i] as number, ys[i] as number])
      }
      const trail = pts.slice(-12)
      const cur = trail[trail.length - 1]
      const color = colorOf(th)
      series.push({
        name: th,
        type: 'line',
        data: trail,
        showSymbol: false,
        lineStyle: { color, width: 1.1, opacity: 0.6 },
        tooltip: { show: false },
        z: 1,
      })
      series.push({
        name: th,
        type: 'scatter',
        data: cur ? [cur] : [],
        symbolSize: 13,
        itemStyle: { color },
        z: 3,
      })
    })
    if (series.length) {
      series[0].markLine = {
        silent: true,
        symbol: 'none',
        lineStyle: { type: 'dashed', color: '#475569' },
        label: { show: false },
        data: [{ xAxis: 50 }, { yAxis: 50 }],
      }
    }
    return {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'item',
        backgroundColor: '#111827',
        borderColor: '#374151',
        textStyle: { color: '#e5e7eb', fontSize: 11 },
        formatter: (p: any) => `${p.seriesName}<br/>RS-Ratio ${Number(p.value[0]).toFixed(1)}<br/>RS-Momentum ${Number(p.value[1]).toFixed(1)}`,
      },
      legend: { show: true, top: 0, textStyle: { color: '#9ca3af', fontSize: 10 }, itemWidth: 14, itemHeight: 8 },
      grid: { left: 8, right: 8, top: 30, bottom: 18, containLabel: true },
      xAxis: {
        type: 'value', min: 0, max: 100,
        axisLabel: { color: '#9ca3af', fontSize: 10 },
        splitLine: { lineStyle: { color: '#1f2937' } },
        name: 'RS-Ratio', nameTextStyle: { color: '#6b7280', fontSize: 10 },
      },
      yAxis: {
        type: 'value', min: 0, max: 100,
        axisLabel: { color: '#9ca3af', fontSize: 10 },
        splitLine: { lineStyle: { color: '#1f2937' } },
        name: 'RS-Momentum', nameTextStyle: { color: '#6b7280', fontSize: 10 },
      },
      graphic: [
        { type: 'text', left: '74%', top: '2%', style: { text: '領先', fill: '#c0392b', fontSize: 12 } },
        { type: 'text', left: '4%', top: '2%', style: { text: '轉強', fill: '#27ae60', fontSize: 12 } },
        { type: 'text', left: '4%', top: '90%', style: { text: '落後', fill: '#7f8c8d', fontSize: 12 } },
        { type: 'text', left: '74%', top: '90%', style: { text: '轉弱', fill: '#e67e22', fontSize: 12 } },
      ],
      series,
    }
  }, [rrg, tf, themes, colorOf])

  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-2">
      <div className="mb-1 flex items-center justify-between px-1">
        <span className="text-sm font-semibold text-slate-200">RRG 象限圖</span>
        <div className="flex gap-1">
          {(Object.keys(TF_LABEL) as RrgTF[]).map((k) => (
            <button
              key={k}
              onClick={() => onTf(k)}
              className={`rounded px-2 py-0.5 text-[11px] ${
                tf === k ? 'bg-sky-600 text-white' : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
              }`}
            >
              {TF_LABEL[k]}
            </button>
          ))}
        </div>
      </div>
      <Chart height={380} option={option} onEvents={{ click: (p) => p?.seriesName && onSelect(p.seriesName) }} />
    </div>
  )
}

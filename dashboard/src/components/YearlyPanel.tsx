import { useMemo } from 'react'
import type { EChartsOption } from 'echarts'
import Chart from './Chart'
import { sma } from '../slice'
import type { Loaded } from '../api'

interface Props {
  data: Loaded
  colorOf: (name: string) => string
  hidden: Set<string>
  onSelect: (theme: string) => void
}

export default function YearlyPanel({ data, colorOf, hidden, onSelect }: Props) {
  const option = useMemo<EChartsOption>(() => {
    const labels = data.history.dates
    const visibleThemes = data.history.themes.filter((t) => !hidden.has(t))
    return {
      backgroundColor: 'transparent',
      color: visibleThemes.map((t) => colorOf(t)),
      tooltip: {
        trigger: 'axis',
        backgroundColor: '#111827',
        borderColor: '#374151',
        textStyle: { color: '#e5e7eb', fontSize: 11 },
      },
      legend: {
        show: true,
        top: 0,
        textStyle: { color: '#9ca3af', fontSize: 10 },
        itemWidth: 14,
        itemHeight: 8,
      },
      grid: { left: 8, right: 8, top: 30, bottom: 40, containLabel: true },
      xAxis: {
        type: 'category',
        data: labels,
        boundaryGap: false,
        axisLine: { lineStyle: { color: '#374151' } },
        axisLabel: { color: '#9ca3af', fontSize: 10, hideOverlap: true },
        axisTick: { show: false },
      },
      yAxis: {
        type: 'value',
        scale: true,
        axisLabel: { color: '#9ca3af', fontSize: 10 },
        splitLine: { lineStyle: { color: '#1f2937' } },
      },
      dataZoom: [
        { type: 'inside', throttle: 40 },
        { type: 'slider', height: 14, bottom: 4, borderColor: '#374151', backgroundColor: '#111827' },
      ],
      series: visibleThemes.map((t) => ({
        name: t,
        type: 'line',
        data: sma(data.history.composite[t], 20),
        symbol: 'none',
        lineStyle: { width: 1.8 },
        emphasis: { focus: 'series' },
        animation: false,
      })),
    }
  }, [data, colorOf, hidden])

  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-2">
      <div className="mb-1 flex items-baseline justify-between px-1">
        <span className="text-sm font-semibold text-slate-200">近 1 年綜合分數</span>
        <span className="text-[11px] text-slate-500">日線，20 日平滑</span>
      </div>
      <Chart
        height={420}
        option={option}
        onEvents={{ click: (p) => p?.seriesName && onSelect(p.seriesName) }}
      />
    </div>
  )
}

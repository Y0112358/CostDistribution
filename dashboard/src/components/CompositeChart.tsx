import { useMemo } from 'react'
import type { EChartsOption } from 'echarts'
import Chart from './Chart'
import type { SeriesDef } from '../slice'

interface Props {
  title: string
  subtitle?: string
  labels: string[]
  series: SeriesDef[]
  colorOf: (name: string) => string
  onSelect?: (theme: string) => void
  height?: number
}

export default function CompositeChart({ title, subtitle, labels, series, colorOf, onSelect, height = 340 }: Props) {
  const option = useMemo<EChartsOption>(() => {
    const zoom = labels.length > 40
    return {
      backgroundColor: 'transparent',
      color: series.map((s) => colorOf(s.name)),
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
      grid: { left: 8, right: 8, top: 30, bottom: zoom ? 40 : 18, containLabel: true },
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
      dataZoom: zoom
        ? [
            { type: 'inside', throttle: 40 },
            { type: 'slider', height: 14, bottom: 4, borderColor: '#374151', backgroundColor: '#111827' },
          ]
        : [],
      series: series.map((s) => ({
        name: s.name,
        type: 'line',
        data: s.data,
        symbol: 'none',
        lineStyle: { width: 1.8 },
        emphasis: { focus: 'series' },
        animation: false,
      })),
    }
  }, [labels, series, colorOf])

  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-2">
      <div className="mb-1 flex items-baseline justify-between px-1">
        <span className="text-sm font-semibold text-slate-200">{title}</span>
        {subtitle && <span className="text-[11px] text-slate-500">{subtitle}</span>}
      </div>
      <Chart
        height={height}
        option={option}
        onEvents={onSelect ? { click: (p) => p?.seriesName && onSelect(p.seriesName) } : undefined}
      />
    </div>
  )
}

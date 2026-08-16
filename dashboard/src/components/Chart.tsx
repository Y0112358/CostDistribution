import { useEffect, useRef } from 'react'
import * as echarts from 'echarts'
import type { EChartsOption } from 'echarts'

interface Props {
  option: EChartsOption
  onEvents?: Record<string, (params: any) => void>
  height?: number | string
  className?: string
}

export default function Chart({ option, onEvents, height = 360, className = '' }: Props) {
  const elRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<echarts.ECharts | null>(null)

  useEffect(() => {
    const el = elRef.current
    if (!el) return
    const chart = echarts.init(el)
    chartRef.current = chart
    const ro = new ResizeObserver(() => chart.resize())
    ro.observe(el)
    return () => {
      ro.disconnect()
      chart.dispose()
      chartRef.current = null
    }
  }, [])

  useEffect(() => {
    chartRef.current?.setOption(option, { notMerge: true })
  }, [option])

  useEffect(() => {
    const chart = chartRef.current
    if (!chart || !onEvents) return
    const entries = Object.entries(onEvents)
    entries.forEach(([ev, fn]) => chart.on(ev, fn))
    return () => entries.forEach(([ev, fn]) => chart.off(ev, fn))
  }, [onEvents])

  return <div ref={elRef} className={className} style={{ width: '100%', height }} />
}

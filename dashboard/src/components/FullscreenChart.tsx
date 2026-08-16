import { useEffect } from 'react'
import type { EChartsOption } from 'echarts'
import Chart from './Chart'

interface Props {
  title: string
  subtitle?: string
  option: EChartsOption
  onEvents?: Record<string, (params: any) => void>
  onClose: () => void
}

export default function FullscreenChart({ title, subtitle, option, onEvents, onClose }: Props) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    document.body.style.overflow = 'hidden'
    return () => {
      window.removeEventListener('keydown', onKey)
      document.body.style.overflow = ''
    }
  }, [onClose])

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-black/85 p-4">
      <div className="mb-2 flex items-center justify-between">
        <div className="flex items-baseline gap-2">
          <span className="text-base font-semibold text-slate-100">{title}</span>
          {subtitle && <span className="text-[12px] text-slate-500">{subtitle}</span>}
          <span className="text-[11px] text-slate-600">滾輪縮放 · 拖曳平移 · 點線看明細</span>
        </div>
        <button
          onClick={onClose}
          className="rounded-lg bg-slate-800 px-3 py-1 text-slate-300 transition-colors hover:bg-slate-700 hover:text-slate-100"
        >
          關閉 ✕
        </button>
      </div>
      <div className="min-h-0 flex-1 rounded-lg border border-slate-700 bg-slate-900/80 p-2">
        <Chart height="100%" option={option} onEvents={onEvents} className="h-full" />
      </div>
    </div>
  )
}

/** 數值格式化共用工具（表格欄位顯示）。 */

export function fmt(v: number | null, digits = 1): string {
  if (v == null || Number.isNaN(v)) return '—'
  return v.toFixed(digits)
}

export function fmtVol(v: number | null): string {
  if (v == null || Number.isNaN(v)) return '—'
  if (v >= 1e9) return `${(v / 1e9).toFixed(2)}B`
  if (v >= 1e6) return `${(v / 1e6).toFixed(1)}M`
  return `${Math.round(v)}`
}

export function change(v: number | null): string {
  if (v == null || Number.isNaN(v)) return '—'
  const s = v > 0 ? '+' : ''
  return `${s}${v.toFixed(1)}`
}

export function changeCls(v: number | null): string {
  if (v == null || Number.isNaN(v) || v === 0) return 'text-slate-400'
  return v > 0 ? 'text-emerald-400' : 'text-red-400'
}

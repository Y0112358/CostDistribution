interface Props {
  themes: string[]
  hidden: Set<string>
  onToggle: (name: string) => void
  onShowAll: () => void
  onHideAll: () => void
  colorOf: (name: string) => string
}

export default function ThemeFilter({ themes, hidden, onToggle, onShowAll, onHideAll, colorOf }: Props) {
  return (
    <div className="flex flex-wrap items-center gap-1.5 rounded-lg border border-slate-800 bg-slate-900/60 px-3 py-2">
      <span className="mr-1 text-[11px] font-semibold text-slate-400">顯示線條</span>
      <button
        onClick={onShowAll}
        className="rounded bg-slate-800 px-2 py-0.5 text-[11px] text-slate-300 hover:bg-slate-700"
      >
        全部
      </button>
      <button
        onClick={onHideAll}
        className="rounded bg-slate-800 px-2 py-0.5 text-[11px] text-slate-300 hover:bg-slate-700"
      >
        全隱藏
      </button>
      <span className="mx-1 h-4 w-px bg-slate-700" />
      {themes.map((t) => {
        const off = hidden.has(t)
        return (
          <button
            key={t}
            onClick={() => onToggle(t)}
            title={off ? '點擊顯示此線' : '點擊隱藏此線'}
            className={`flex items-center gap-1 rounded px-2 py-0.5 text-[11px] transition-colors ${
              off ? 'bg-slate-800/40 text-slate-600' : 'bg-slate-800 text-slate-200 hover:bg-slate-700'
            }`}
          >
            <span
              className={`inline-block h-2 w-2 rounded-full ${off ? 'opacity-20' : ''}`}
              style={{ backgroundColor: colorOf(t) }}
            />
            {t}
          </button>
        )
      })}
    </div>
  )
}

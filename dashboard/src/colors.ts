const TAB10 = [
  '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
  '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf',
]

export function makeColorOf(themes: string[]): (name: string) => string {
  const m = new Map<string, string>()
  themes.forEach((t, i) => m.set(t, TAB10[i % TAB10.length]))
  return (name: string) => m.get(name) ?? '#9ca3af'
}

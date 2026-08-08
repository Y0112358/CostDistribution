import type { TF } from '../types'
import type { Loaded } from '../api'
import { dailyComposite, intradayComposite } from '../slice'
import CompositeChart from './CompositeChart'

interface Props {
  data: Loaded
  colorOf: (name: string) => string
  hidden: Set<string>
  onSelect: (theme: string, tf: TF) => void
}

const CARD: { tf: TF; title: string; subtitle: string }[] = [
  { tf: '1m', title: '近 1 個月', subtitle: '日線（21 交易日）' },
  { tf: '2w', title: '近 2 週', subtitle: '日線（10 交易日）' },
  { tf: '1w', title: '近 1 週', subtitle: '5m 盤中' },
]

export default function TimeframeRow({ data, colorOf, hidden, onSelect }: Props) {
  const d1m = dailyComposite(data, '1m')
  const d2w = dailyComposite(data, '2w')
  const intra = intradayComposite(data)
  const keep = (s: { name: string }) => !hidden.has(s.name)

  const views = CARD.map((c) => {
    if (c.tf === '1w') return { ...c, labels: intra.labels, series: intra.series.filter(keep) }
    const d = c.tf === '1m' ? d1m : d2w
    return { ...c, labels: d.labels, series: d.series.filter(keep) }
  })

  return (
    <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
      {views.map((v) => (
        <CompositeChart
          key={v.tf}
          title={v.title}
          subtitle={v.subtitle}
          labels={v.labels}
          series={v.series}
          colorOf={colorOf}
          onSelect={(theme) => onSelect(theme, v.tf)}
        />
      ))}
    </div>
  )
}

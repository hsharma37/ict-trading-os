import { Wifi, WifiOff, AlertTriangle, FlaskConical } from 'lucide-react'

type Props = {
  source?: string
  stale?: boolean
  className?: string
}

/**
 * Honest indicator of where a displayed price came from and whether it's fresh.
 * MT5 (the broker feed) reads green; stale reads amber; "unavailable" reads
 * red with a clear prompt to connect the bridge — the app has no other feed.
 */
export default function PriceSourceBadge({ source, stale, className = '' }: Props) {
  if (!source) {
    return (
      <span className={`flex items-center gap-1.5 text-xs text-muted-foreground ${className}`}>
        <WifiOff className="w-3.5 h-3.5" />
        No data
      </span>
    )
  }

  const s = source.toLowerCase()

  // MT5 is the app's single price source — no bridge means no price at all.
  if (s === 'unavailable') {
    return (
      <span
        className={`flex items-center gap-1.5 text-xs font-medium text-red-500 ${className}`}
        title="MT5 bridge not connected — prices come exclusively from the broker feed"
      >
        <WifiOff className="w-3.5 h-3.5" />
        <span>Offline</span>
        <span className="text-muted-foreground font-normal">· connect MT5 bridge</span>
      </span>
    )
  }

  const isDemo = s === 'synthetic'
  const isSecondary = s === 'scraped'

  let tone: string
  let label: string
  let Icon = Wifi

  if (isDemo) {
    tone = 'text-red-500'
    label = 'DEMO'
    Icon = FlaskConical
  } else if (stale || isSecondary) {
    tone = 'text-amber-500'
    label = stale ? 'Stale' : 'Scraped'
    Icon = AlertTriangle
  } else {
    tone = 'text-green-500'
    label = 'Live'
  }

  // MT5 and manual are the only sources the backend can emit since the
  // MT5-only cutover; anything else renders raw so a regression is VISIBLE.
  const providerLabel: Record<string, string> = {
    mt5: 'MT5',
    manual: 'Manual',
  }
  const provider = providerLabel[s] || s

  return (
    <span
      className={`flex items-center gap-1.5 text-xs font-medium ${tone} ${className}`}
      title={`Price source: ${provider}${stale ? ' · stale (>2m old)' : ''}`}
    >
      <Icon className="w-3.5 h-3.5" />
      <span>{label}</span>
      <span className="text-muted-foreground font-normal">· {provider}</span>
    </span>
  )
}

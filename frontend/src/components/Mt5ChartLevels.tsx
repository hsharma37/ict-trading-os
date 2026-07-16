import { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { mt5Api } from '@/api/client'
import { PenLine, Loader2, Check, AlertTriangle, ChevronDown } from 'lucide-react'

/** Push the live ICT zones (order blocks, FVGs, liquidity, structure) to the
 *  user's MetaTrader 5 chart via the bridge + the ICTOSLevels indicator. */
export default function Mt5ChartLevels({ symbol }: { symbol: string }) {
  const [state, setState] = useState<'idle' | 'loading' | 'done' | 'error'>('idle')
  const [msg, setMsg] = useState('')
  const [showSetup, setShowSetup] = useState(false)

  const draw = async () => {
    setState('loading'); setMsg('')
    try {
      const res = await mt5Api.drawLevels(symbol)
      setState('done'); setMsg(`Sent ${res.data?.zones ?? ''} ${symbol} zones to MT5 — they'll appear on the chart within a few seconds.`)
    } catch (e: any) {
      setState('error'); setMsg(e?.response?.data?.detail || 'Failed — is the bridge running and updated?')
    }
  }

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm flex items-center gap-2">
          <PenLine className="w-4 h-4 text-primary" /> ICT Levels on your MT5 chart
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-xs text-muted-foreground">
          Draws the detected <strong>order blocks, FVGs, liquidity pools & structure</strong> for {symbol}
          directly on your MetaTrader 5 chart (green = bullish, red = bearish). The app can't draw on the
          chart itself, so a one-time indicator does it — set up once, then just click below anytime.
        </p>

        <div className="flex items-center gap-3 flex-wrap">
          <Button size="sm" onClick={draw} disabled={state === 'loading'}>
            {state === 'loading' ? <Loader2 className="w-4 h-4 mr-1 animate-spin" />
              : state === 'done' ? <Check className="w-4 h-4 mr-1 text-emerald-300" />
                : <PenLine className="w-4 h-4 mr-1" />}
            Draw {symbol} levels on MT5
          </Button>
          {msg && (
            <span className={`text-xs flex items-center gap-1 ${state === 'error' ? 'text-red-400' : 'text-emerald-400'}`}>
              {state === 'error' && <AlertTriangle className="w-3.5 h-3.5" />}{msg}
            </span>
          )}
        </div>

        <button onClick={() => setShowSetup((s) => !s)}
          className="text-[11px] text-muted-foreground hover:text-foreground inline-flex items-center gap-1">
          <ChevronDown className={`w-3 h-3 transition-transform ${showSetup ? 'rotate-180' : ''}`} /> One-time setup (do this first)
        </button>
        {showSetup && (
          <ol className="text-[11px] text-muted-foreground list-decimal ml-4 space-y-1">
            <li>MT5 → <strong>File → Open Data Folder</strong> → <code>MQL5\Indicators\</code>.</li>
            <li>Copy <code>mt5-bridge/ICTOSLevels.mq5</code> there; open it in MetaEditor and press <strong>F7</strong> to compile.</li>
            <li>Drag <strong>ICTOSLevels</strong> from the Navigator onto the chart of the symbol you want.</li>
            <li>On the bridge machine: <code>git pull</code> and restart the bridge (adds the draw route).</li>
            <li>Then click the button above — zones appear and refresh automatically. Full guide: <code>docs/MT5_CHART_LEVELS.md</code>.</li>
          </ol>
        )}
      </CardContent>
    </Card>
  )
}

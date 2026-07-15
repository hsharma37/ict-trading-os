import { useState } from 'react'
import { Button } from '@/components/ui/Button'
import { plannerApi } from '@/api/client'
import { X, Zap } from 'lucide-react'

export interface PlanSeed {
  signalId?: string
  symbol: string
  side: 'BUY' | 'SELL'
  entry_price?: number | null
  stop_loss?: number | null
  take_profits?: number[]
}

/** Create/arm a trade plan from a signal (editable entry price for limit orders). */
export default function PlanModal({ seed, onClose, onDone }: { seed: PlanSeed; onClose: () => void; onDone: () => void }) {
  const [side, setSide] = useState<'BUY' | 'SELL'>(seed.side || 'BUY')
  const [entry, setEntry] = useState(seed.entry_price != null ? String(seed.entry_price) : '')
  const [sl, setSl] = useState(seed.stop_loss != null ? String(seed.stop_loss) : '')
  const tps = seed.take_profits || []
  const [tp1, setTp1] = useState(tps[0] != null ? String(tps[0]) : '')
  const [tp2, setTp2] = useState(tps[1] != null ? String(tps[1]) : '')
  const [tp3, setTp3] = useState(tps[2] != null ? String(tps[2]) : '')
  const [riskPct, setRiskPct] = useState('1')
  const [triggerType, setTriggerType] = useState<'price' | 'time' | 'now'>('price')
  const [triggerTime, setTriggerTime] = useState('')
  const [isEvent, setIsEvent] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const submit = async (armAfter: boolean) => {
    setBusy(true); setError(null)
    try {
      const body: any = {
        symbol: seed.symbol, side,
        entry_price: entry ? parseFloat(entry) : undefined,
        stop_loss: sl ? parseFloat(sl) : undefined,
        take_profits: [tp1, tp2, tp3].map(parseFloat).filter((n) => n && n > 0),
        risk_pct: parseFloat(riskPct),
        trigger_type: triggerType,
        trigger_time: triggerType === 'time' && triggerTime ? new Date(triggerTime).toISOString() : undefined,
        is_event: isEvent,
      }
      const res = seed.signalId
        ? await plannerApi.fromSignal(seed.signalId, body)
        : await plannerApi.create(body)
      const plan = res.data?.plan || res.data
      if (armAfter && plan?.id) await plannerApi.arm(plan.id)
      onDone()
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Failed to create plan')
    } finally {
      setBusy(false)
    }
  }

  const field = 'w-full px-3 py-2 border rounded-md bg-background text-sm'
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={onClose}>
      <div className="bg-card border border-border rounded-lg w-full max-w-lg max-h-[90vh] overflow-y-auto p-5 space-y-4" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-bold">Plan trade — {seed.symbol}</h3>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground"><X className="w-5 h-5" /></button>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1">
            <label className="text-xs font-medium">Direction</label>
            <div className="flex gap-2">
              <button onClick={() => setSide('BUY')} className={`flex-1 px-3 py-2 rounded-md text-sm font-medium ${side === 'BUY' ? 'bg-green-600 text-white' : 'border bg-background'}`}>Long</button>
              <button onClick={() => setSide('SELL')} className={`flex-1 px-3 py-2 rounded-md text-sm font-medium ${side === 'SELL' ? 'bg-red-600 text-white' : 'border bg-background'}`}>Short</button>
            </div>
          </div>
          <div className="space-y-1">
            <label className="text-xs font-medium">Risk %{isEvent && <span className="text-amber-400"> (event → halved)</span>}</label>
            <input className={field} type="number" step="0.1" value={riskPct} onChange={(e) => setRiskPct(e.target.value)} />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1">
            <label className="text-xs font-medium text-primary">Entry / Limit price ✎</label>
            <input className={field} type="number" step="0.00001" value={entry} onChange={(e) => setEntry(e.target.value)} placeholder="editable" />
          </div>
          <div className="space-y-1">
            <label className="text-xs font-medium text-red-500">Stop Loss</label>
            <input className={field} type="number" step="0.00001" value={sl} onChange={(e) => setSl(e.target.value)} />
          </div>
        </div>

        <div className="grid grid-cols-3 gap-3">
          <div className="space-y-1"><label className="text-xs font-medium text-green-500">TP1</label><input className={field} type="number" step="0.00001" value={tp1} onChange={(e) => setTp1(e.target.value)} /></div>
          <div className="space-y-1"><label className="text-xs font-medium text-green-500">TP2</label><input className={field} type="number" step="0.00001" value={tp2} onChange={(e) => setTp2(e.target.value)} /></div>
          <div className="space-y-1"><label className="text-xs font-medium text-green-500">TP3</label><input className={field} type="number" step="0.00001" value={tp3} onChange={(e) => setTp3(e.target.value)} /></div>
        </div>

        <div className="space-y-1">
          <label className="text-xs font-medium">Trigger</label>
          <div className="flex gap-2">
            {(['price', 'time', 'now'] as const).map((t) => (
              <button key={t} onClick={() => setTriggerType(t)} className={`flex-1 px-3 py-2 rounded-md text-sm font-medium capitalize ${triggerType === t ? 'bg-primary text-primary-foreground' : 'border bg-background'}`}>
                {t === 'price' ? 'At limit price' : t === 'time' ? 'At time' : 'Now'}
              </button>
            ))}
          </div>
          <p className="text-xs text-muted-foreground">
            {triggerType === 'price' ? 'Rests as a native MT5 pending order and fills when price reaches your entry.'
              : triggerType === 'time' ? 'Fires as a market order at the scheduled time (needs the bridge scheduler running).'
                : 'Fills immediately as a market order when armed.'}
          </p>
          {triggerType === 'time' && (
            <input className={field} type="datetime-local" value={triggerTime} onChange={(e) => setTriggerTime(e.target.value)} />
          )}
        </div>

        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={isEvent} onChange={(e) => setIsEvent(e.target.checked)} />
          Event trade (auto risk-adjusted — half size for volatility)
        </label>

        {error && <div className="p-2 rounded bg-red-500/10 border border-red-500/20 text-red-400 text-sm">{error}</div>}

        <div className="flex gap-2 pt-1">
          <Button variant="outline" className="flex-1" disabled={busy} onClick={() => submit(false)}>Save draft</Button>
          <Button className="flex-1" disabled={busy} onClick={() => submit(true)}>
            <Zap className="w-4 h-4 mr-1" /> {busy ? 'Working…' : 'Arm now'}
          </Button>
        </div>
        <p className="text-[11px] text-muted-foreground text-center">Arming places the order on your MT5 account (pending, timed, or immediate).</p>
      </div>
    </div>
  )
}

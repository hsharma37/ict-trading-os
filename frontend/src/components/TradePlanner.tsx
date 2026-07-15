import { useState, useEffect, useCallback } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { plannerApi } from '@/api/client'
import { CalendarClock, Zap, X, RefreshCw, Target } from 'lucide-react'

interface Plan {
  id: string; symbol: string; side: string; entry_price?: number; stop_loss?: number
  take_profits: number[]; lot_size: number; risk_pct: number; trigger_type: string
  trigger_time?: string; is_event: boolean; status: string; source: string
  mt5_tickets: any[]; result?: any[]
}

const statusStyle: Record<string, string> = {
  draft: 'bg-muted text-muted-foreground',
  armed: 'bg-amber-500/15 text-amber-400',
  placed: 'bg-sky-500/15 text-sky-400',
  executed: 'bg-emerald-500/15 text-emerald-400',
  cancelled: 'bg-muted text-muted-foreground',
  failed: 'bg-red-500/15 text-red-400',
}

export default function TradePlanner({ refreshKey }: { refreshKey?: number }) {
  const [plans, setPlans] = useState<Plan[]>([])
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      const res = await plannerApi.list()
      setPlans(res.data?.plans || [])
    } catch { /* ignore */ }
  }, [])

  useEffect(() => { load() }, [load, refreshKey])

  const act = async (id: string, fn: () => Promise<any>) => {
    setBusy(id); setError(null)
    try { await fn(); await load() }
    catch (e: any) { setError(e?.response?.data?.detail || 'Action failed') }
    finally { setBusy(null) }
  }

  const active = plans.filter((p) => !['cancelled', 'failed', 'executed'].includes(p.status))
  const done = plans.filter((p) => ['cancelled', 'failed', 'executed'].includes(p.status))

  const row = (p: Plan) => (
    <div key={p.id} className="p-3 rounded-lg border border-border bg-card">
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-2">
          <span className={`text-xs px-2 py-0.5 rounded font-bold ${p.side === 'BUY' ? 'text-emerald-400' : 'text-red-400'}`}>{p.side}</span>
          <span className="font-bold">{p.symbol}</span>
          <span className={`text-[10px] px-1.5 py-0.5 rounded font-bold uppercase ${statusStyle[p.status] || 'bg-muted'}`}>{p.status}</span>
          {p.is_event && <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-400">event</span>}
          {p.source === 'telegram' && <span className="text-[10px] px-1.5 py-0.5 rounded bg-sky-500/10 text-sky-400">telegram</span>}
        </div>
        <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
          {p.trigger_type === 'price' && <><Target className="w-3 h-3" /> @ {p.entry_price}</>}
          {p.trigger_type === 'time' && <><CalendarClock className="w-3 h-3" /> {p.trigger_time ? new Date(p.trigger_time).toLocaleString() : 'timed'}</>}
          {p.trigger_type === 'now' && <>market</>}
        </div>
      </div>
      <div className="mt-1.5 text-xs text-muted-foreground flex gap-3 flex-wrap">
        <span>Lot {p.lot_size}</span>
        <span>SL {p.stop_loss ?? '—'}</span>
        <span>TP {p.take_profits?.join(' / ') || '—'}</span>
        <span>Risk {p.risk_pct}%</span>
        {p.mt5_tickets?.length > 0 && <span className="text-emerald-400">tickets {p.mt5_tickets.join(', ')}</span>}
      </div>
      {p.result?.some((r: any) => r.status === 'failed') && (
        <div className="mt-1 text-xs text-red-400">{p.result.filter((r: any) => r.status === 'failed').map((r: any) => r.error).join('; ')}</div>
      )}
      {['draft', 'armed'].includes(p.status) && (
        <div className="flex gap-2 mt-2">
          {p.status === 'draft' && (
            <Button size="sm" disabled={busy === p.id} onClick={() => act(p.id, () => plannerApi.arm(p.id))}>
              <Zap className="w-3.5 h-3.5 mr-1" /> Arm
            </Button>
          )}
          <Button size="sm" variant="outline" disabled={busy === p.id} onClick={() => act(p.id, () => plannerApi.cancel(p.id))}>
            <X className="w-3.5 h-3.5 mr-1" /> Cancel
          </Button>
        </div>
      )}
    </div>
  )

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-3">
        <CardTitle className="text-base flex items-center gap-2">
          <CalendarClock className="w-4 h-4 text-primary" /> Trade Plans
          <span className="text-xs font-normal text-muted-foreground">arm → auto-executes on price / time</span>
        </CardTitle>
        <button onClick={load} className="text-muted-foreground hover:text-foreground"><RefreshCw className="w-4 h-4" /></button>
      </CardHeader>
      <CardContent className="space-y-2">
        {error && <div className="p-2 rounded bg-red-500/10 border border-red-500/20 text-red-400 text-sm">{error}</div>}
        {plans.length === 0 && <p className="text-sm text-muted-foreground text-center py-3">No plans yet. Plan one from a Telegram signal below.</p>}
        {active.map(row)}
        {done.length > 0 && <div className="text-xs text-muted-foreground pt-2">History</div>}
        {done.slice(0, 5).map(row)}
      </CardContent>
    </Card>
  )
}

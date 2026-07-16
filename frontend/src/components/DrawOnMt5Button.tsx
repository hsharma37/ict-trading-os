import { useState } from 'react'
import { mt5Api } from '@/api/client'
import { PenLine, Loader2, Check } from 'lucide-react'

/** Pushes the live ICT zones to the MT5 chart via the bridge (the ICTOSLevels
 *  indicator must be attached to the chart to render them). */
export default function DrawOnMt5Button({ symbol }: { symbol: string }) {
  const [state, setState] = useState<'idle' | 'loading' | 'done' | 'error'>('idle')
  const [msg, setMsg] = useState('')

  const draw = async () => {
    setState('loading'); setMsg('')
    try {
      const res = await mt5Api.drawLevels(symbol)
      setState('done'); setMsg(`${res.data?.zones ?? ''} zones sent to MT5`)
      setTimeout(() => setState('idle'), 4000)
    } catch (e: any) {
      setState('error'); setMsg(e?.response?.data?.detail || 'Failed — is the bridge connected?')
      setTimeout(() => setState('idle'), 6000)
    }
  }

  return (
    <span className="inline-flex items-center gap-2">
      <button onClick={draw} disabled={state === 'loading'}
        title="Send the current ICT zones to your MT5 chart (needs the ICTOSLevels indicator attached)"
        className="text-xs inline-flex items-center gap-1 px-2 py-1 rounded-md border border-border text-muted-foreground hover:text-foreground disabled:opacity-50">
        {state === 'loading' ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
          : state === 'done' ? <Check className="w-3.5 h-3.5 text-emerald-400" />
            : <PenLine className="w-3.5 h-3.5" />}
        Draw on MT5 chart
      </button>
      {msg && <span className={`text-[11px] ${state === 'error' ? 'text-red-400' : 'text-muted-foreground'}`}>{msg}</span>}
    </span>
  )
}

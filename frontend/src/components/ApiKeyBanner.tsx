import { useEffect, useState } from 'react'
import { KeyRound, X } from 'lucide-react'
import { getApiKey, setApiKey } from '@/api/client'

/**
 * Global banner shown when an API request returns 401. Lets the owner paste
 * their API key (stored only in this browser via localStorage) so protected
 * routes authenticate. Reachable from any page, which avoids the chicken-and-egg
 * of needing to load a protected Settings page first.
 */
export default function ApiKeyBanner() {
  const [open, setOpen] = useState(false)
  const [value, setValue] = useState('')

  useEffect(() => {
    const handler = () => {
      setValue(getApiKey())
      setOpen(true)
    }
    window.addEventListener('ictos:unauthorized', handler)
    return () => window.removeEventListener('ictos:unauthorized', handler)
  }, [])

  if (!open) return null

  const hadKey = getApiKey().length > 0

  const save = () => {
    const trimmed = value.trim()
    if (!trimmed) return
    setApiKey(trimmed)
    // Reload so every request that just 401'd retries with the key attached.
    window.location.reload()
  }

  return (
    <div className="fixed inset-x-0 top-0 z-[100] flex justify-center px-4 pt-3">
      <div className="w-full max-w-2xl rounded-lg border border-amber-400/60 bg-amber-50 dark:bg-amber-950/90 shadow-lg">
        <div className="flex items-start gap-3 p-4">
          <KeyRound className="mt-0.5 h-5 w-5 shrink-0 text-amber-600 dark:text-amber-400" />
          <div className="flex-1">
            <p className="text-sm font-semibold text-amber-900 dark:text-amber-200">
              {hadKey ? 'API key rejected (401)' : 'API key required'}
            </p>
            <p className="mt-0.5 text-xs text-amber-800/80 dark:text-amber-300/80">
              {hadKey
                ? 'The saved key was not accepted. Enter a valid API key to continue.'
                : 'This page reads protected data. Paste your API key to authenticate. It is stored only in this browser.'}
            </p>
            <div className="mt-3 flex flex-col gap-2 sm:flex-row">
              <input
                type="password"
                autoFocus
                value={value}
                onChange={(e) => setValue(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && save()}
                placeholder="Paste API key (X-Api-Key)"
                className="flex-1 rounded-md border border-amber-300 bg-white px-3 py-2 text-sm text-gray-900 outline-none focus:border-amber-500 dark:border-amber-700 dark:bg-gray-900 dark:text-gray-100"
              />
              <button
                onClick={save}
                disabled={!value.trim()}
                className="rounded-md bg-amber-600 px-4 py-2 text-sm font-medium text-white hover:bg-amber-700 disabled:opacity-50"
              >
                Save &amp; reload
              </button>
            </div>
          </div>
          <button
            onClick={() => setOpen(false)}
            aria-label="Dismiss"
            className="rounded-md p-1 text-amber-700 hover:bg-amber-100 dark:text-amber-300 dark:hover:bg-amber-900"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  )
}

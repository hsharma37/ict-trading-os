/** Theme application — the missing wiring behind Settings' dark/light toggle
 *  (PROGRESS P4: the control saved a value but nothing ever applied it). */
const KEY = 'ictos_theme'

export function applyTheme(theme: string): void {
  const dark = theme === 'dark'
  document.documentElement.classList.toggle('dark', dark)
  try { localStorage.setItem(KEY, dark ? 'dark' : 'light') } catch { /* private mode */ }
}

/** Called before first render: last chosen theme, defaulting to light
 *  (the app's historical rendered appearance). */
export function initTheme(): void {
  let t = 'light'
  try { t = localStorage.getItem(KEY) || 'light' } catch { /* ignore */ }
  document.documentElement.classList.toggle('dark', t === 'dark')
}

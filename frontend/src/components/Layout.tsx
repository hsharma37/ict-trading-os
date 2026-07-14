import { Link, useLocation } from 'react-router-dom'
import { useState, useEffect, useCallback } from 'react'
import { marketApi } from '@/api/client'
import ApiKeyBanner from './ApiKeyBanner'
import PriceSourceBadge from './PriceSourceBadge'
import {
  LayoutDashboard,
  ArrowRightLeft,
  BarChart3,
  Settings,
  Menu,
  X,
  TrendingUp,
  Library,
  Activity,
  Eye,
  MessageSquare,
  Monitor,
  Brain,
  FlaskConical,
  Zap,
} from 'lucide-react'

const navItems = [
  { path: '/', label: 'Dashboard', icon: LayoutDashboard },
  { path: '/mt5', label: 'MT5 Terminal', icon: Monitor },
  { path: '/execute', label: 'Execute', icon: ArrowRightLeft },
  { path: '/analytics', label: 'Analytics', icon: BarChart3 },
  { path: '/research', label: 'Research', icon: FlaskConical },
  { path: '/signals', label: 'Signals', icon: Zap },
  { path: '/telegram', label: 'Telegram', icon: MessageSquare },
  { path: '/knowledge', label: 'Knowledge', icon: Brain },
  { path: '/library', label: 'Library', icon: Library },
  { path: '/whatsup', label: "What's Up?", icon: Eye },
  { path: '/settings', label: 'Settings', icon: Settings },
]

const INSTRUMENTS = ['NQ1!', 'ES1!', 'EURUSD', 'GBPUSD', 'XAUUSD', 'USDJPY', 'BTCUSD', 'CL1!']

interface LayoutProps {
  children: React.ReactNode
}

export default function Layout({ children }: LayoutProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const location = useLocation()
  const [selectedInstrument, setSelectedInstrument] = useState('EURUSD')
  const [livePrice, setLivePrice] = useState<{ symbol: string; price: number; change: number; change_percent: number; digits: number; source?: string; stale?: boolean } | null>(null)
  const [priceLoading, setPriceLoading] = useState(false)
  const [showDropdown, setShowDropdown] = useState(false)

  const fetchLivePrice = useCallback(async () => {
    try {
      setPriceLoading(true)
      const response = await marketApi.getPrice(selectedInstrument)
      const p = response.data
      if (p) {
        setLivePrice({
          symbol: p.symbol,
          price: p.price,
          change: p.change,
          change_percent: p.change_percent,
          digits: p.digits,
          source: p.source,
          stale: p.stale,
        })
      }
    } catch (e) {
      console.error('Live price fetch failed:', e)
    } finally {
      setPriceLoading(false)
    }
  }, [selectedInstrument])

  useEffect(() => {
    fetchLivePrice()
    const interval = setInterval(fetchLivePrice, 15000)
    return () => clearInterval(interval)
  }, [fetchLivePrice])

  const isPositive = (livePrice?.change ?? 0) >= 0

  return (
    <div className="flex h-screen bg-background text-foreground">
      <ApiKeyBanner />
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 md:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`fixed inset-y-0 left-0 z-50 w-64 transform bg-card border-r border-border transition-transform duration-200 md:static md:translate-x-0 ${
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="flex items-center justify-between h-16 px-4 border-b border-border">
          <div className="flex items-center gap-2">
            <TrendingUp className="w-6 h-6 text-primary" />
            <span className="text-lg font-bold">ICT OS</span>
          </div>
          <button
            onClick={() => setSidebarOpen(false)}
            className="p-1 rounded-md md:hidden hover:bg-muted"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <nav className="p-4 space-y-1">
          {navItems.map((item) => {
            const isActive = location.pathname === item.path
            const Icon = item.icon
            return (
              <Link
                key={item.path}
                to={item.path}
                onClick={() => setSidebarOpen(false)}
                className={`flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-primary text-primary-foreground'
                    : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                }`}
              >
                <Icon className="w-4 h-4" />
                {item.label}
              </Link>
            )
          })}
        </nav>
      </aside>

      {/* Main content */}
      <div className="flex flex-col flex-1 overflow-hidden">
        {/* Top bar */}
        <header className="flex items-center h-16 px-4 border-b border-border bg-card">
          <button
            onClick={() => setSidebarOpen(true)}
            className="p-2 mr-4 rounded-md md:hidden hover:bg-muted"
          >
            <Menu className="w-5 h-5" />
          </button>
          <div className="flex items-center gap-4">
            <span className="text-sm font-semibold">ICT Trading OS</span>
            <span className="px-2 py-0.5 text-xs rounded-full bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300">
              v9.1.0
            </span>
          </div>
          <div className="flex-1" />
          <div className="flex items-center gap-4 text-sm">
            {/* Instrument Selector + Live Price */}
            <div className="relative flex items-center gap-2 px-3 py-1.5 rounded-lg bg-muted/50 border border-border">
              <Activity className="w-4 h-4 text-muted-foreground" />
              
              <button
                onClick={() => setShowDropdown(!showDropdown)}
                className="flex items-center gap-1 font-semibold text-sm hover:text-primary transition-colors"
              >
                {selectedInstrument}
              </button>
              
              {showDropdown && (
                <div className="absolute top-full left-0 mt-1 w-32 bg-card border border-border rounded-lg shadow-lg z-50 overflow-hidden">
                  {INSTRUMENTS.map((inst) => (
                    <button
                      key={inst}
                      onClick={() => {
                        setSelectedInstrument(inst)
                        setShowDropdown(false)
                      }}
                      className={`w-full px-3 py-2 text-left text-sm hover:bg-muted transition-colors ${
                        inst === selectedInstrument ? 'bg-primary/10 text-primary font-semibold' : ''
                      }`}
                    >
                      {inst}
                    </button>
                  ))}
                </div>
              )}
              
              <div className="w-px h-4 bg-border mx-1" />
              
              {priceLoading ? (
                <span className="text-muted-foreground text-xs">Loading...</span>
              ) : livePrice ? (
                <div className="flex items-center gap-2">
                  <span className="font-mono font-bold">
                    {livePrice.price.toFixed(livePrice.digits)}
                  </span>
                  <span
                    className={`flex items-center gap-0.5 text-xs font-medium ${
                      isPositive ? 'text-green-400' : 'text-red-400'
                    }`}
                  >
                    {isPositive ? '+' : ''}
                    {livePrice.change.toFixed(livePrice.digits)} ({isPositive ? '+' : ''}
                    {livePrice.change_percent.toFixed(2)}%)
                  </span>
                </div>
              ) : (
                <span className="text-muted-foreground text-xs">No data</span>
              )}
            </div>
            
            <PriceSourceBadge source={livePrice?.source} stale={livePrice?.stale} />
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-auto p-4 md:p-6">
          {children}
        </main>
      </div>
    </div>
  )
}

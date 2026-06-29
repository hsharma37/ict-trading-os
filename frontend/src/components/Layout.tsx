import { Link, useLocation } from 'react-router-dom'
import { useState } from 'react'
import {
  LayoutDashboard,
  ClipboardList,
  ArrowRightLeft,
  BookOpen,
  BarChart3,
  FlaskConical,
  Brain,
  Settings,
  Bell,
  Zap,
  Menu,
  X,
  TrendingUp,
} from 'lucide-react'

const navItems = [
  { path: '/', label: 'Dashboard', icon: LayoutDashboard },
  { path: '/plan', label: 'Plan', icon: ClipboardList },
  { path: '/execute', label: 'Execute', icon: ArrowRightLeft },
  { path: '/journal', label: 'Journal', icon: BookOpen },
  { path: '/analytics', label: 'Analytics', icon: BarChart3 },
  { path: '/research', label: 'Research', icon: FlaskConical },
  { path: '/suggestions', label: 'Signals', icon: Zap },
  { path: '/alerts', label: 'Alerts', icon: Bell },
  { path: '/knowledge', label: 'Knowledge', icon: Brain },
  { path: '/settings', label: 'Settings', icon: Settings },
]

interface LayoutProps {
  children: React.ReactNode
}

export default function Layout({ children }: LayoutProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const location = useLocation()

  return (
    <div className="flex h-screen bg-background text-foreground">
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
              v1.0.0
            </span>
          </div>
          <div className="flex-1" />
          <div className="flex items-center gap-4 text-sm text-muted-foreground">
            <span>Price: ...</span>
            <span className="w-2 h-2 rounded-full bg-green-500" />
            <span>Connected</span>
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

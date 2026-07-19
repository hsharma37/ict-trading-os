import { lazy, Suspense } from 'react'
import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'

// Route-level code splitting (PROGRESS P3): each page loads on demand instead
// of one ~900KB bundle, and a deploy's new chunks only download when visited.
const Dashboard = lazy(() => import('./pages/Dashboard'))
const MT5Terminal = lazy(() => import('./pages/MT5Terminal'))
const Execute = lazy(() => import('./pages/Execute'))
const Analytics = lazy(() => import('./pages/Analytics'))
const Knowledge = lazy(() => import('./pages/Knowledge'))
const Settings = lazy(() => import('./pages/Settings'))
const Library = lazy(() => import('./pages/Library'))
const WhatsUp = lazy(() => import('./pages/WhatsUp'))
const TelegramFeed = lazy(() => import('./pages/TelegramFeed'))
const QuantLab = lazy(() => import('./pages/QuantLab'))
const Signals = lazy(() => import('./pages/Signals'))

const Fallback = () => (
  <div className="flex items-center justify-center py-24 text-muted-foreground text-sm">Loading…</div>
)

function App() {
  return (
    <Layout>
      <Suspense fallback={<Fallback />}>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/mt5" element={<MT5Terminal />} />
        <Route path="/execute" element={<Execute />} />
        <Route path="/analytics" element={<Analytics />} />
        <Route path="/research" element={<QuantLab />} />
        <Route path="/signals" element={<Signals />} />
        <Route path="/telegram" element={<TelegramFeed />} />
        <Route path="/knowledge" element={<Knowledge />} />
        <Route path="/library" element={<Library />} />
        <Route path="/whatsup" element={<WhatsUp />} />
        <Route path="/settings" element={<Settings />} />
      </Routes>
      </Suspense>
    </Layout>
  )
}

export default App

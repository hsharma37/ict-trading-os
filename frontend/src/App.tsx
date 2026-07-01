import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import MT5Terminal from './pages/MT5Terminal'
import Execute from './pages/Execute'
import Analytics from './pages/Analytics'
import Knowledge from './pages/Knowledge'
import Settings from './pages/Settings'
import Library from './pages/Library'
import WhatsUp from './pages/WhatsUp'
import TelegramFeed from './pages/TelegramFeed'

function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/mt5" element={<MT5Terminal />} />
        <Route path="/execute" element={<Execute />} />
        <Route path="/analytics" element={<Analytics />} />
        <Route path="/telegram" element={<TelegramFeed />} />
        <Route path="/knowledge" element={<Knowledge />} />
        <Route path="/library" element={<Library />} />
        <Route path="/whatsup" element={<WhatsUp />} />
        <Route path="/settings" element={<Settings />} />
      </Routes>
    </Layout>
  )
}

export default App

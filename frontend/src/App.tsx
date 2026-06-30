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
import QuantLab from './pages/QuantLab'
import Signals from './pages/Signals'
import Journal from './pages/Journal'
import Plan from './pages/Plan'
import Suggestions from './pages/Suggestions'
import AlertManager from './pages/AlertManager'
import Playground from './pages/Playground'

function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/mt5" element={<MT5Terminal />} />
        <Route path="/execute" element={<Execute />} />
        <Route path="/analytics" element={<Analytics />} />
        <Route path="/research" element={<QuantLab />} />
        <Route path="/quant" element={<QuantLab />} />
        <Route path="/signals" element={<Signals />} />
        <Route path="/playground" element={<Playground />} />
        <Route path="/telegram" element={<TelegramFeed />} />
        <Route path="/knowledge" element={<Knowledge />} />
        <Route path="/library" element={<Library />} />
        <Route path="/whatsup" element={<WhatsUp />} />
        <Route path="/journal" element={<Journal />} />
        <Route path="/plan" element={<Plan />} />
        <Route path="/suggestions" element={<Suggestions />} />
        <Route path="/alerts" element={<AlertManager />} />
        <Route path="/settings" element={<Settings />} />
      </Routes>
    </Layout>
  )
}

export default App

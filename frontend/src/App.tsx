import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Plan from './pages/Plan'
import Execute from './pages/Execute'
import Journal from './pages/Journal'
import Analytics from './pages/Analytics'
import Research from './pages/Research'
import Knowledge from './pages/Knowledge'
import Settings from './pages/Settings'
import AlertManager from './pages/AlertManager'
import Suggestions from './pages/Suggestions'
import Playground from './pages/Playground'
import Library from './pages/Library'
import WhatsUp from './pages/WhatsUp'
import TelegramFeed from './pages/TelegramFeed'

function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/plan" element={<Plan />} />
        <Route path="/execute" element={<Execute />} />
        <Route path="/journal" element={<Journal />} />
        <Route path="/analytics" element={<Analytics />} />
        <Route path="/research" element={<Research />} />
        <Route path="/knowledge" element={<Knowledge />} />
        <Route path="/playground" element={<Playground />} />
        <Route path="/library" element={<Library />} />
        <Route path="/whatsup" element={<WhatsUp />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="/alerts" element={<AlertManager />} />
        <Route path="/suggestions" element={<Suggestions />} />
        <Route path="/telegram" element={<TelegramFeed />} />
      </Routes>
    </Layout>
  )
}

export default App

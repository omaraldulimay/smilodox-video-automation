import { useEffect, useState, useCallback } from 'react'
import './index.css'
import './App.css'
import { api } from './api'
import Header from './components/Header'
import Dashboard from './views/Dashboard'
import BatchUpload from './views/BatchUpload'
import Info from './views/Info'

export default function App() {
  const [activeTab, setActiveTab] = useState('batch-upload')
  const [stats, setStats] = useState(null)

  const loadStats = useCallback(() => {
    api.getStats().then(setStats).catch(() => {})
  }, [])

  useEffect(() => {
    loadStats()
    // 60s, matching the backend's account-status cache TTL -- polling faster
    // than that just re-requests the same cached value. This was previously
    // 5s, which on a hosted free-tier instance (shared/limited CPU) spawned
    // a Higgsfield CLI subprocess every 5 seconds on every page, making the
    // whole app feel sluggish (confirmed 2026-09-02).
    const id = setInterval(loadStats, 60000)
    return () => clearInterval(id)
  }, [loadStats])

  return (
    <div className="app-shell">
      <Header activeTab={activeTab} onTabChange={setActiveTab} stats={stats} />
      {activeTab === 'dashboard' && <Dashboard />}
      {activeTab === 'batch-upload' && <BatchUpload onSwitchToDashboard={() => setActiveTab('dashboard')} />}
      {activeTab === 'info' && <Info />}
    </div>
  )
}

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
  // Which tabs have ever been opened. A tab is mounted on its first visit and
  // then stays mounted (just hidden) -- switching away and back used to
  // unmount the view entirely, throwing away its state and re-fetching
  // everything from scratch on return (scan results, job list, dropdowns).
  // Mounting lazily rather than all three upfront keeps the initial page load
  // from doing work for tabs the user may never open.
  const [mountedTabs, setMountedTabs] = useState({ 'batch-upload': true })

  const handleTabChange = useCallback((tab) => {
    setMountedTabs((mounted) => (mounted[tab] ? mounted : { ...mounted, [tab]: true }))
    setActiveTab(tab)
  }, [])

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

  // "contents" (rather than "block") makes this wrapper invisible to layout,
  // so the view inside stays a direct flex child of .app-shell exactly as it
  // was when rendered conditionally.
  const visibility = (tab) => ({ display: activeTab === tab ? 'contents' : 'none' })

  return (
    <div className="app-shell">
      <Header activeTab={activeTab} onTabChange={handleTabChange} stats={stats} />
      {mountedTabs['dashboard'] && (
        <div style={visibility('dashboard')}>
          {/* Dashboard polls /jobs every 5s -- paused while it's hidden, so a
              hidden tab doesn't keep querying in the background (which also
              kept the free-tier database awake unnecessarily). */}
          <Dashboard active={activeTab === 'dashboard'} />
        </div>
      )}
      {mountedTabs['batch-upload'] && (
        <div style={visibility('batch-upload')}>
          <BatchUpload onSwitchToDashboard={() => handleTabChange('dashboard')} />
        </div>
      )}
      {mountedTabs['info'] && (
        <div style={visibility('info')}>
          <Info />
        </div>
      )}
    </div>
  )
}

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
    const id = setInterval(loadStats, 5000)
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

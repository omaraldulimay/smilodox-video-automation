import { useEffect, useState, useCallback } from 'react'
import './index.css'
import './App.css'
import { api } from './api'
import Header from './components/Header'
import NewJob from './views/NewJob'
import Dashboard from './views/Dashboard'
import BatchUpload from './views/BatchUpload'

export default function App() {
  const [activeTab, setActiveTab] = useState('new-job')
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
      {activeTab === 'new-job' && <NewJob onJobCreated={loadStats} />}
      {activeTab === 'dashboard' && <Dashboard />}
      {activeTab === 'batch-upload' && <BatchUpload onSwitchToDashboard={() => setActiveTab('dashboard')} />}
    </div>
  )
}

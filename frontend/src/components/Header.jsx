import { IconCoin } from './Icons'

const TABS = [
  { id: 'batch-upload', label: 'Batch-Upload' },
  { id: 'dashboard', label: 'Dashboard' },
  { id: 'info', label: 'Info' },
]

export default function Header({ activeTab, onTabChange, stats }) {
  const counts = stats?.counts || {}
  const summary = Object.entries(counts)
    .map(([status, n]) => `${n} ${status}`)
    .join(' · ')

  const credits = stats?.account?.credits
  const creditsLabel =
    credits === undefined || credits === null ? '–' : `${credits} Credits übrig`

  return (
    <div className="header">
      <div className="header-left">
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div className="brand-mark">S</div>
          <div className="header-title">Smilodox Video Automation</div>
        </div>
        <div className="tabs">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              className={`tab ${activeTab === tab.id ? 'active' : ''}`}
              onClick={() => onTabChange(tab.id)}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>
      <div className="header-right">
        {summary && <div className="status-summary">{summary}</div>}
        <div className="credits-pill">
          <IconCoin />
          {creditsLabel}
        </div>
      </div>
    </div>
  )
}

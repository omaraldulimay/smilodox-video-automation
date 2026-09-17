import { IconCoin } from './Icons'

const TABS = [
  { id: 'batch-upload', label: 'Batch-Upload' },
  { id: 'dashboard', label: 'Dashboard' },
  { id: 'prompt', label: 'Prompt' },
  { id: 'info', label: 'Info' },
]

export default function Header({ activeTab, onTabChange, stats, budget }) {
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
        {budget?.limit_credits ? (
          <div
            className="credits-pill"
            title={`Monatsbudget: ${budget.used_eur} € von ${budget.limit_eur} € verbraucht. Pro Durchlauf max. ${budget.batch_limit_credits} Credits.`}
            style={
              budget.percent_used >= 100
                ? { borderColor: '#c0392b', color: '#c0392b' }
                : budget.percent_used >= 80
                ? { borderColor: '#d68910', color: '#d68910' }
                : undefined
            }
          >
            Budget {budget.used_credits}/{budget.limit_credits}
          </div>
        ) : null}
        <div className="credits-pill">
          <IconCoin />
          {creditsLabel}
        </div>
      </div>
    </div>
  )
}

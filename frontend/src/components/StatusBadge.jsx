// Dashboard only ever shows these 4 -- the backend tracks finer-grained statuses
// internally (completed_dry_run, failed_transient/permanent, qa_failed) for retry
// logic and credit tracking, but that distinction isn't useful for the team to see.
const DISPLAY_STATUS = {
  pending: 'pending',
  processing: 'processing',
  completed: 'completed',
  completed_dry_run: 'completed',
  qa_failed: 'failed',
  failed_transient: 'failed',
  failed_permanent: 'failed',
}

const STATUS_STYLES = {
  pending: { bg: '#f4f4f5', text: '#71717a', dot: '#a1a1aa' },
  processing: { bg: '#fef3c7', text: '#b45309', dot: '#f59e0b' },
  completed: { bg: '#dcfce7', text: '#15803d', dot: '#22c55e' },
  failed: { bg: '#fee2e2', text: '#b91c1c', dot: '#ef4444' },
}

export default function StatusBadge({ status }) {
  const display = DISPLAY_STATUS[status] || 'pending'
  const style = STATUS_STYLES[display]
  return (
    <span className="badge" style={{ background: style.bg, color: style.text }}>
      <span className="dot" style={{ background: style.dot }} />
      {display}
    </span>
  )
}

const STATUS_STYLES = {
  pending: { bg: '#f4f4f5', text: '#71717a', dot: '#a1a1aa' },
  processing: { bg: '#fef3c7', text: '#b45309', dot: '#f59e0b' },
  completed: { bg: '#dcfce7', text: '#15803d', dot: '#22c55e' },
  completed_dry_run: { bg: '#e0e7ff', text: '#4338ca', dot: '#6366f1' },
  qa_failed: { bg: '#fef3c7', text: '#b45309', dot: '#f59e0b' },
  failed_transient: { bg: '#fef3c7', text: '#b45309', dot: '#f59e0b' },
  failed_permanent: { bg: '#fee2e2', text: '#b91c1c', dot: '#ef4444' },
}

export default function StatusBadge({ status }) {
  const style = STATUS_STYLES[status] || STATUS_STYLES.pending
  return (
    <span className="badge" style={{ background: style.bg, color: style.text }}>
      <span className="dot" style={{ background: style.dot }} />
      {status}
    </span>
  )
}

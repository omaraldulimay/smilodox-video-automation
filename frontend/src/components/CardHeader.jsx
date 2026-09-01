export default function CardHeader({ icon, title, action }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        {icon && (
          <div
            style={{
              width: 28,
              height: 28,
              borderRadius: 7,
              background: 'var(--accent-bg)',
              color: 'var(--accent)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0,
            }}
          >
            {icon}
          </div>
        )}
        <div style={{ fontSize: 14, fontWeight: 700 }}>{title}</div>
      </div>
      {action}
    </div>
  )
}

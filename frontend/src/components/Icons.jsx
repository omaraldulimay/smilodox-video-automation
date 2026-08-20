const base = { fill: 'none', strokeWidth: 2, strokeLinecap: 'round', strokeLinejoin: 'round' }

export function IconCoin({ size = 14, color = '#52525b' }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" stroke={color} {...base}>
      <circle cx="12" cy="12" r="9" />
      <path d="M9 12h6" />
    </svg>
  )
}

export function IconUpload({ size = 28, color = '#71717a' }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" stroke={color} {...base}>
      <path d="M12 16V4M12 4l-4 4M12 4l4 4" />
      <path d="M4 16v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3" />
    </svg>
  )
}

export function IconRefresh({ size = 13, color = '#4338ca' }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" stroke={color} {...base}>
      <path d="M23 4v6h-6" />
      <path d="M1 20v-6h6" />
      <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10" />
      <path d="M20.49 15a9 9 0 0 1-14.85 3.36L1 14" />
    </svg>
  )
}

export function IconCheck({ size = 14, color = '#22c55e' }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" stroke={color} {...base}>
      <path d="M20 6L9 17l-5-5" />
    </svg>
  )
}

export function IconAlertTriangle({ size = 14, color = '#d97706' }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" stroke={color} {...base}>
      <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
      <path d="M12 9v4" />
      <path d="M12 17h.01" />
    </svg>
  )
}

export function IconFolder({ size = 20, color = '#4338ca' }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" stroke={color} {...base}>
      <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
    </svg>
  )
}

export function IconPlay({ size = 14, color = '#a1a1aa' }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill={color} stroke="none">
      <polygon points="6,4 20,12 6,20" />
    </svg>
  )
}

export function IconX({ size = 14, color = '#dc2626' }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" stroke={color} {...base}>
      <path d="M18 6L6 18" />
      <path d="M6 6l12 12" />
    </svg>
  )
}

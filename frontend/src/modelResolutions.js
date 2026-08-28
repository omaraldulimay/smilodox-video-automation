// Resolutions offered per model in the UI -- trims each model's full schema enum
// down to what the team actually wants selectable (cheap test tier + production
// tier).
export const RESOLUTION_ALLOWLIST = {}

// Kling's `mode` values (std/pro/4k) are quality/speed tiers, not resolutions --
// per Higgsfield's own docs (higgsfield.ai/blog/Kling-3.0-is-on-Higgsfield-User-
// Guide-AI-Video-Generation) each tier corresponds to a fixed output resolution
// (std=720p, pro=1080p, 4k=2160p/UHD), so the dropdown shows that instead of the
// bare enum value. Falls back to the raw value for any mode not listed here.
export const MODE_LABELS = {
  std: 'Standard (720p)',
  pro: 'Pro (1080p)',
  '4k': '4K (2160p / UHD)',
}

export function modeLabel(mode) {
  return MODE_LABELS[mode] || mode
}

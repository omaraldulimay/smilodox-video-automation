// Resolutions offered per model in the UI -- trims each model's full schema enum
// down to what the team actually wants selectable (cheap test tier + production
// tier).
export const RESOLUTION_ALLOWLIST = {
  // Gemini Omni Flash 1.1 can natively go up to 4k. 4k dropped per team
  // decision (90 credits, no reason to pay that when our own upscale_to_1080p
  // step gets any smaller output to at least 1080p afterwards at no extra
  // Higgsfield cost). 360p/720p/1080p all kept selectable -- 10/30/45 credits.
  gemini_omni_flash_1_1: ['360p', '720p', '1080p'],
}

// Mode options offered per model in the UI -- same idea as RESOLUTION_ALLOWLIST
// above, trimmed to what the team actually wants selectable. Falls back to the
// model's full schema enum for any model not listed here. An empty array hides
// the "Modus" field entirely -- used for gemini_omni_flash_1_1, whose `mode`
// values (text-to-video/image-to-video/reference-to-video/edit) select a
// generation workflow, not a quality tier; the backend always forces
// reference-to-video for it (see higgsfield_adapter.py), so exposing a picker
// there would offer a choice that silently does nothing.
export const MODE_ALLOWLIST = {
  // Kling keeps its full std/pro/4k range -- unlike Gemini 1.1's resolution
  // field, the team still wants 4k selectable here.
  gemini_omni_flash_1_1: [],
}

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

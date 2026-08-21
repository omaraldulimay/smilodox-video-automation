// Resolutions offered per model in the UI -- trims each model's full schema enum
// down to what the team actually wants selectable (cheap test tier + production
// tier). Shared between NewJob and BatchUpload so the two stay in sync.
export const RESOLUTION_ALLOWLIST = {
  seedance_2_0: ['480p', '1080p'],
}

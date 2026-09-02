const BASE = ''

async function request(path, options = {}) {
  const res = await fetch(BASE + path, options)
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = body.detail || JSON.stringify(body)
    } catch {
      // ignore body parse failure, fall back to statusText
    }
    throw new Error(`${res.status} ${detail}`)
  }
  return res.status === 204 ? null : res.json()
}

// Templates and models are static for the lifetime of a page load (no admin
// UI changes them live) but were being re-fetched from scratch every time
// Batch-Upload/Dashboard re-mounted (switching tabs unmounts the previous
// one, see App.jsx's conditional rendering) -- on a hosted instance that
// meant a real network round-trip (plus, for models, a Higgsfield CLI call
// per model) on every single tab switch. Cached here per page load instead.
let _templatesCache = null
let _modelsCache = null

export const api = {
  getTemplates: () => (_templatesCache ??= request('/templates')),
  getModels: () => (_modelsCache ??= request('/models')),
  getStats: () => request('/stats'),

  costEstimate: (body) =>
    request('/cost-estimate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),

  listJobs: (params = {}) => {
    const qs = new URLSearchParams(params).toString()
    return request(`/jobs${qs ? `?${qs}` : ''}`)
  },
  getJob: (jobId) => request(`/jobs/${jobId}`),
  retryJob: (jobId) => request(`/jobs/${jobId}/retry`, { method: 'POST' }),

  createJob: (formData) => request('/jobs', { method: 'POST', body: formData }),

  previewDriveScan: (body) =>
    request('/jobs/batch/drive-scan/preview', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  commitDriveScan: (body) =>
    request('/jobs/batch/drive-scan/commit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  driveScanImageUrl: (path) => `${BASE}/jobs/batch/drive-scan/image?path=${encodeURIComponent(path)}`,
  jobVideoUrl: (jobId) => `${BASE}/jobs/${jobId}/video`,
  jobThumbnailUrl: (jobId) => `${BASE}/jobs/${jobId}/thumbnail`,
}

import { useEffect, useState, useCallback } from 'react'
import { api } from '../api'
import StatusBadge from '../components/StatusBadge'
import { IconPlay, IconRefresh } from '../components/Icons'

const STATUS_OPTIONS = [
  '',
  'pending',
  'processing',
  'completed',
  'completed_dry_run',
  'qa_failed',
  'failed_transient',
  'failed_permanent',
]

function timeAgo(iso) {
  const diffMs = Date.now() - new Date(iso).getTime()
  const mins = Math.round(diffMs / 60000)
  if (mins < 1) return 'gerade eben'
  if (mins < 60) return `vor ${mins} Min`
  const hours = Math.round(mins / 60)
  if (hours < 24) return `vor ${hours} Std`
  return `vor ${Math.round(hours / 24)} Tagen`
}

export default function Dashboard() {
  const [jobs, setJobs] = useState([])
  const [status, setStatus] = useState('')
  const [model, setModel] = useState('')
  const [models, setModels] = useState([])
  const [search, setSearch] = useState('')

  const load = useCallback(() => {
    const params = {}
    if (status) params.status = status
    if (model) params.model = model
    api.listJobs(params).then(setJobs)
  }, [status, model])

  useEffect(() => {
    load()
    const id = setInterval(load, 5000)
    return () => clearInterval(id)
  }, [load])

  useEffect(() => {
    api.getModels().then(setModels)
  }, [])

  async function handleRetry(jobId) {
    await api.retryJob(jobId)
    load()
  }

  const visibleJobs = jobs.filter(
    (j) => !search || (j.product_id || '').toLowerCase().includes(search.toLowerCase())
  )

  const retryableStatuses = new Set(['failed_permanent', 'qa_failed'])

  return (
    <div className="view-body" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={{ display: 'flex', gap: 12 }}>
        <select className="select" style={{ width: 180 }} value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">Alle Status</option>
          {STATUS_OPTIONS.filter(Boolean).map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <select className="select" style={{ width: 180 }} value={model} onChange={(e) => setModel(e.target.value)}>
          <option value="">Alle Modelle</option>
          {models
            .filter((m) => !m.error)
            .map((m) => (
              <option key={m.model} value={m.model}>
                {m.schema?.display_name || m.model}
              </option>
            ))}
        </select>
        <input
          className="text-input"
          style={{ maxWidth: 280 }}
          placeholder="Produkt-ID suchen…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <table>
          <thead>
            <tr>
              <th>Vorschau</th>
              <th>Status</th>
              <th>Modell</th>
              <th>Template</th>
              <th>Credits</th>
              <th>Erstellt</th>
              <th>Aktion</th>
            </tr>
          </thead>
          <tbody>
            {visibleJobs.map((job) => (
              <tr key={job.job_id}>
                <td>
                  <div
                    style={{
                      width: 44,
                      height: 58,
                      background: 'var(--border-light)',
                      borderRadius: 4,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      overflow: 'hidden',
                    }}
                  >
                    {job.status === 'completed' && job.output_path ? (
                      <IconPlay />
                    ) : null}
                  </div>
                </td>
                <td>
                  <StatusBadge status={job.status} />
                </td>
                <td>{job.model}</td>
                <td>{job.template_key || '—'}</td>
                <td>{job.credits_estimate ?? '–'}</td>
                <td>{timeAgo(job.created_at)}</td>
                <td>
                  {retryableStatuses.has(job.status) ? (
                    <button
                      className="btn-link"
                      style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
                      onClick={() => handleRetry(job.job_id)}
                    >
                      <IconRefresh />
                      Retry
                    </button>
                  ) : (
                    <span style={{ color: 'var(--text-faint)', fontSize: 12 }}>—</span>
                  )}
                </td>
              </tr>
            ))}
            {visibleJobs.length === 0 && (
              <tr>
                <td colSpan={7} style={{ textAlign: 'center', color: 'var(--text-faint)', padding: 24 }}>
                  Keine Jobs gefunden.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

import { useEffect, useState, useCallback } from 'react'
import { api } from '../api'
import PageHeader from '../components/PageHeader'
import CardHeader from '../components/CardHeader'
import StatusBadge from '../components/StatusBadge'
import { IconPlay, IconRefresh } from '../components/Icons'

const STATUS_OPTIONS = ['', 'pending', 'processing', 'completed', 'failed']

function VideoPreview({ job }) {
  const [hovering, setHovering] = useState(false)
  const hasVideo = job.status === 'completed' && job.output_path

  return (
    <div
      onMouseEnter={() => setHovering(true)}
      onMouseLeave={() => setHovering(false)}
      style={{
        width: 90,
        height: 160,
        background: 'var(--border-light)',
        borderRadius: 4,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        overflow: 'hidden',
      }}
    >
      {!hasVideo ? (
        <IconPlay />
      ) : hovering ? (
        <video
          src={api.jobVideoUrl(job.job_id)}
          autoPlay
          muted
          loop
          playsInline
          style={{ width: '100%', height: '100%', objectFit: 'cover' }}
        />
      ) : (
        <img
          src={api.jobThumbnailUrl(job.job_id)}
          alt=""
          style={{ width: '100%', height: '100%', objectFit: 'cover' }}
        />
      )}
    </div>
  )
}

function resolutionInfo(job) {
  // job.resolution is the resolution actually requested at generation time
  // (e.g. "360p", "720p", "1080p", "4k"). Every clip gets force-upscaled to a
  // 1080p short side before QA passes it (see backend qa.upscale_to_1080p), so
  // parsing pixel dimensions out of qa_status would always read "1080x1920"
  // even for a 360p source -- misleadingly hiding the real generation quality.
  if (job.resolution) {
    const label = job.resolution
    const m = label.match(/^(\d+)p$/i)
    const shortSide = m ? parseInt(m[1], 10) : label.toLowerCase() === '4k' ? 2160 : null
    return { label, shortSide }
  }
  // Models without a resolution parameter (e.g. Kling) have no requested value
  // to fall back on -- use the actually delivered pixel dimensions instead.
  const match = (job.qa_status || '').match(/(\d+)x(\d+)/g)
  if (!match) return null
  const [w, h] = match[match.length - 1].split('x').map(Number)
  return { label: `${w}×${h}`, shortSide: Math.min(w, h) }
}

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
    // Dashboard is meant to show real generations only -- dry-runs are just cost
    // estimates, not actual videos, and would clutter the "what's finished" view.
    const params = { dry_run: 0 }
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
      <PageHeader wide title="Dashboard" description="Alle Jobs im Überblick." />

      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <div style={{ padding: '18px 20px 16px', borderBottom: '1px solid var(--border-light)' }}>
          <CardHeader
            icon={<IconPlay size={12} color="var(--accent)" />}
            title="Jobs"
            action={
              <div style={{ display: 'flex', gap: 10 }}>
                <select className="select" style={{ width: 160 }} value={status} onChange={(e) => setStatus(e.target.value)}>
                  <option value="">Alle Status</option>
                  {STATUS_OPTIONS.filter(Boolean).map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </select>
                <select className="select" style={{ width: 160 }} value={model} onChange={(e) => setModel(e.target.value)}>
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
                  style={{ width: 200 }}
                  placeholder="Produkt-ID suchen…"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
              </div>
            }
          />
        </div>
        <table>
          <thead>
            <tr>
              <th>Vorschau</th>
              <th>Status</th>
              <th>Modell</th>
              <th>Auflösung</th>
              <th>Logo</th>
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
                  <VideoPreview job={job} />
                </td>
                <td>
                  <StatusBadge status={job.status} />
                </td>
                <td>{job.model}</td>
                <td>
                  {(() => {
                    const res = resolutionInfo(job)
                    if (!res) return <span style={{ color: 'var(--text-faint)' }}>—</span>
                    const belowTarget = res.shortSide !== null && res.shortSide < 1080
                    return (
                      <span
                        style={{ color: belowTarget ? '#b45309' : 'var(--text-muted)', fontWeight: belowTarget ? 600 : 400 }}
                        title={belowTarget ? 'Unter dem 1080p-Ziel' : undefined}
                      >
                        {res.label}
                        {belowTarget && ' ⚠️'}
                      </span>
                    )
                  })()}
                </td>
                <td>
                  {(() => {
                    if (!job.logo_check) return <span style={{ color: 'var(--text-faint)' }}>—</span>
                    if (job.logo_check === 'pass') {
                      return <span style={{ color: 'var(--green-text)' }}>OK</span>
                    }
                    if (job.logo_check.startsWith('fixed_auto')) {
                      return (
                        <span style={{ color: 'var(--accent)', fontWeight: 600 }} title={`Automatisch korrigiert -- ${job.logo_check}. Original liegt als Backup neben dem Video.`}>
                          ✓ automatisch korrigiert
                        </span>
                      )
                    }
                    return (
                      <span style={{ color: '#b45309', fontWeight: 600 }} title={job.logo_check}>
                        ⚠️ prüfen
                      </span>
                    )
                  })()}
                </td>
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
                <td colSpan={9} style={{ textAlign: 'center', color: 'var(--text-faint)', padding: 24 }}>
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

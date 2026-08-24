import { useEffect, useState } from 'react'
import { api } from '../api'
import { IconCheck, IconAlertTriangle, IconRefresh, IconFolder } from '../components/Icons'
import { RESOLUTION_ALLOWLIST } from '../modelResolutions'

// 'logo' is optional (see backend/drive_scan.py OPTIONAL_SHOT_TYPES) -- shown as
// a bonus thumbnail slot but never required for a group to count as complete.
const SHOT_ORDER = ['full', 'front', 'fullback', 'detail_one', 'logo']

// Kling only ever uses full+fullback (see backend/drive_scan.py
// TWO_IMAGE_MODEL_SHOT_ORDER) -- showing all 4 thumbnails would suggest front/
// detail_one/logo matter for Kling when they're silently ignored.
const MODEL_SHOT_ORDER = {
  kling3_0: ['full', 'fullback'],
}

function ThumbnailStrip({ images, shotOrder }) {
  return (
    <div style={{ display: 'flex', gap: 10, padding: '2px 12px 10px 34px' }}>
      {shotOrder.map((shot) => {
        const path = images?.[shot]
        const filename = path ? path.split('/').pop() : null
        return (
          <div key={shot} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3, width: 64 }}>
            <div
              style={{
                width: 56,
                height: 56,
                borderRadius: 4,
                overflow: 'hidden',
                border: path ? '1px solid var(--border)' : '1px dashed var(--text-faint)',
                background: path ? 'transparent' : '#fafafa',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              {path ? (
                <img
                  src={api.driveScanImageUrl(path)}
                  alt={shot}
                  style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                />
              ) : (
                <span style={{ fontSize: 9, color: 'var(--text-faint)' }}>fehlt</span>
              )}
            </div>
            <span
              style={{
                fontSize: 9,
                color: 'var(--text-faint)',
                textAlign: 'center',
                wordBreak: 'break-all',
                lineHeight: 1.2,
              }}
              title={filename || shot}
            >
              {filename || shot}
            </span>
          </div>
        )
      })}
    </div>
  )
}

export default function BatchUpload({ onSwitchToDashboard }) {
  const [templates, setTemplates] = useState([])
  const [models, setModels] = useState([])
  const DEFAULT_DRIVE_FOLDER =
    '/path/to/project Ablagen/Smilodox Video Automation/reference-images'
  const [folderPath, setFolderPath] = useState(DEFAULT_DRIVE_FOLDER)
  const [defaultTemplateKey, setDefaultTemplateKey] = useState('')
  const [model, setModel] = useState('')
  const [resolution, setResolution] = useState('')
  const [dryRun, setDryRun] = useState(false)

  const [scanning, setScanning] = useState(false)
  const [scanError, setScanError] = useState('')
  const [scanResult, setScanResult] = useState(null)
  const [selectedFolders, setSelectedFolders] = useState(new Set())

  const [committing, setCommitting] = useState(false)
  const [commitResult, setCommitResult] = useState(null)

  const [costPerJob, setCostPerJob] = useState(null)
  const [costError, setCostError] = useState('')

  useEffect(() => {
    api.getTemplates().then((ts) => {
      setTemplates(ts)
      if (ts.length) setDefaultTemplateKey(ts[0].template_key)
    })
    api.getModels().then((ms) => {
      setModels(ms)
      const first = ms.find((m) => !m.error)
      if (first) setModel(first.model)
    })
  }, [])

  const selectedModelObj = models.find((m) => m.model === model)
  const resolutionParam = selectedModelObj?.schema?.params?.find((p) => p.name === 'resolution')
  const allowlist = RESOLUTION_ALLOWLIST[model]
  const resolutionOptions = allowlist ? (resolutionParam?.enum || []).filter((r) => allowlist.includes(r)) : resolutionParam?.enum || []
  const shotOrder = MODEL_SHOT_ORDER[model] || SHOT_ORDER

  useEffect(() => {
    // Reset resolution to the model's own default whenever the model changes --
    // a value chosen for one model may not be valid for another.
    if (resolutionParam) {
      const preferred = resolutionParam.default
      const fallback = resolutionOptions[0] || ''
      setResolution(resolutionOptions.includes(preferred) ? preferred : fallback)
    } else {
      setResolution('')
    }
  }, [model]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    // Both templates share the same duration/aspect_ratio, so a single
    // per-video estimate applies across the whole batch regardless of which
    // garment type each detected product turns out to be.
    const t = templates.find((tt) => tt.template_key === defaultTemplateKey) || templates[0]
    if (!model || !t) return
    setCostPerJob(null)
    setCostError('')
    api
      .costEstimate({
        model,
        duration: t.duration,
        aspect_ratio: t.aspect_ratio,
        resolution: resolutionParam ? resolution : t.resolution,
      })
      .then((res) => setCostPerJob(res.credits))
      .catch((err) => setCostError(err.message))
  }, [model, resolution, defaultTemplateKey, templates]) // eslint-disable-line react-hooks/exhaustive-deps

  async function handleScan() {
    if (!folderPath) return
    setScanning(true)
    setScanError('')
    setScanResult(null)
    setCommitResult(null)
    try {
      const result = await api.previewDriveScan({
        folder_path: folderPath,
        default_template_key: defaultTemplateKey || null,
        model: model || null,
      })
      setScanResult(result)

      // Default-deselect products that already have a real (non-dry-run) job,
      // so re-scanning after a completed run doesn't silently re-generate and
      // re-charge credits for the same product.
      let alreadyDone = new Set()
      try {
        const jobs = await api.listJobs()
        alreadyDone = new Set(jobs.filter((j) => !j.dry_run).map((j) => j.product_id))
      } catch {
        // If the job list fails to load, fall back to selecting everything.
      }
      setSelectedFolders(new Set(result.groups.filter((g) => !alreadyDone.has(g.variant_number)).map((g) => g.folder)))
    } catch (err) {
      setScanError(err.message)
    } finally {
      setScanning(false)
    }
  }

  function toggleFolder(folder) {
    setSelectedFolders((prev) => {
      const next = new Set(prev)
      if (next.has(folder)) next.delete(folder)
      else next.add(folder)
      return next
    })
  }

  async function handleCommit() {
    setCommitting(true)
    try {
      const result = await api.commitDriveScan({
        folder_path: folderPath,
        default_template_key: defaultTemplateKey || null,
        model,
        resolution: resolutionParam && resolution ? resolution : null,
        dry_run: dryRun,
        include_folders: Array.from(selectedFolders),
      })
      setCommitResult(result)
    } catch (err) {
      setScanError(err.message)
    } finally {
      setCommitting(false)
    }
  }

  return (
    <div className="view-body" style={{ display: 'flex', justifyContent: 'center' }}>
      <div style={{ width: 640, display: 'flex', flexDirection: 'column', gap: 16 }}>
        <div className="card">
          <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--accent)', marginBottom: 10 }}>
            Quelle
          </div>
          <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 14 }}>Google-Drive-Ordner scannen</div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div className="field">
              <div className="field-label">Ordnerpfad (synchronisierter Drive-Ordner)</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, border: '1px solid var(--border)', borderRadius: 6, padding: '10px 12px', background: '#fafafa' }}>
                <IconFolder size={18} />
                <input
                  className="text-input"
                  style={{ border: 'none', background: 'transparent', padding: 0 }}
                  placeholder="/path/to/project Drive/Zalando Videos/Referenzbilder"
                  value={folderPath}
                  onChange={(e) => setFolderPath(e.target.value)}
                />
              </div>
            </div>

            <div style={{ display: 'flex', gap: 14, alignItems: 'flex-end' }}>
              <div className="field" style={{ flex: 1 }}>
                <div className="field-label">Vorgabe-Template (falls Ordnername nicht erkannt wird)</div>
                <select className="select" value={defaultTemplateKey} onChange={(e) => setDefaultTemplateKey(e.target.value)}>
                  {templates.map((t) => (
                    <option key={t.template_key} value={t.template_key}>
                      {t.garment_type}
                    </option>
                  ))}
                </select>
              </div>
              <div className="field" style={{ flex: 1 }}>
                <div className="field-label">Modell</div>
                <select className="select" value={model} onChange={(e) => setModel(e.target.value)}>
                  {models
                    .filter((m) => !m.error)
                    .map((m) => (
                      <option key={m.model} value={m.model}>
                        {m.schema?.display_name || m.model}
                      </option>
                    ))}
                </select>
              </div>
            </div>

            {resolutionParam && resolutionOptions.length > 0 && (
              <div className="field">
                <div className="field-label">
                  Auflösung {resolutionOptions.length === 1 && <span style={{ color: 'var(--text-faint)', fontWeight: 400 }}>(fix)</span>}
                </div>
                <select
                  className="select"
                  value={resolution}
                  disabled={resolutionOptions.length === 1}
                  onChange={(e) => setResolution(e.target.value)}
                >
                  {resolutionOptions.map((r) => (
                    <option key={r} value={r}>
                      {r}
                    </option>
                  ))}
                </select>
              </div>
            )}

            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                background: 'var(--accent-bg)',
                border: '1px solid var(--accent-border)',
                borderRadius: 6,
                padding: '10px 12px',
              }}
            >
              <span style={{ fontSize: 12, color: 'var(--accent)', fontWeight: 600 }}>Geschätzte Kosten pro Video</span>
              <span style={{ fontSize: 13, color: 'var(--accent-hover)', fontWeight: 700 }}>
                {costError ? '—' : costPerJob === null ? '…' : `${costPerJob} Credits`}
              </span>
            </div>
            {costError && <div style={{ fontSize: 11, color: 'var(--red-text)' }}>{costError}</div>}

            <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: '#52525b', cursor: 'pointer' }}>
              <input type="checkbox" checked={dryRun} onChange={(e) => setDryRun(e.target.checked)} />
              Nur Kosten schätzen (Dry-Run für den gesamten Batch)
            </label>

            <button className="btn btn-primary" disabled={scanning || !folderPath} onClick={handleScan}>
              {scanning ? 'Scanne…' : 'Ordner scannen'}
            </button>
            {scanError && <div style={{ fontSize: 12, color: 'var(--red-text)' }}>{scanError}</div>}
          </div>
        </div>

        {scanResult && (
          <div className="card">
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
              <div style={{ fontSize: 14, fontWeight: 700 }}>Erkannte Produkte</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
                <button
                  className="btn-link"
                  onClick={() =>
                    setSelectedFolders((prev) =>
                      prev.size === scanResult.groups.length ? new Set() : new Set(scanResult.groups.map((g) => g.folder))
                    )
                  }
                >
                  {selectedFolders.size === scanResult.groups.length ? 'Alle abwählen' : 'Alle auswählen'}
                </button>
                <button className="btn-link" style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }} onClick={handleScan}>
                  <IconRefresh />
                  Erneut scannen
                </button>
              </div>
            </div>

            <div style={{ border: '1px solid var(--border-light)', borderRadius: 6, overflow: 'hidden', marginBottom: 12, maxHeight: 440, overflowY: 'auto' }}>
              {scanResult.groups.map((g) => {
                const selected = selectedFolders.has(g.folder)
                return (
                  <div
                    key={`${g.folder}-${g.variant_number}`}
                    style={{
                      borderBottom: '1px solid #f0f0f1',
                      background: selected ? (g.complete ? 'transparent' : '#fffbeb') : '#fafafa',
                      opacity: selected ? 1 : 0.55,
                    }}
                  >
                    <label
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 10,
                        padding: '9px 12px',
                        fontSize: 12,
                        cursor: 'pointer',
                      }}
                    >
                      <input type="checkbox" checked={selected} onChange={() => toggleFolder(g.folder)} />
                      {g.complete ? <IconCheck /> : <IconAlertTriangle />}
                      <span style={{ flex: 1, fontWeight: 600 }}>{g.variant_number}</span>
                      <span style={{ color: 'var(--text-faint)' }}>{g.template_key || 'kein Template'}</span>
                      <span style={{ color: g.complete ? 'var(--text-faint)' : 'var(--amber-text)' }}>
                        {g.image_count} Bild{g.image_count === 1 ? '' : 'er'}
                        {!g.complete && ' · unvollständig'}
                      </span>
                    </label>
                    <ThumbnailStrip images={g.images} shotOrder={shotOrder} />
                  </div>
                )
              })}
              {scanResult.groups.length === 0 && (
                <div style={{ padding: 16, fontSize: 12, color: 'var(--text-faint)' }}>
                  Keine passenden Bilder gefunden (erwartet: ein Ordner pro Produkt mit full.jpg, front.jpg, fullback.jpg, detail_one.jpg, optional logo.jpg).
                </div>
              )}
            </div>

            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
              <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                {selectedFolders.size} von {scanResult.total} ausgewählt
                {scanResult.incomplete > 0 && (
                  <>
                    {' '}
                    · <span style={{ color: 'var(--amber-text)', fontWeight: 600 }}>{scanResult.incomplete} unvollständig</span>
                  </>
                )}
                {scanResult.missing_template.length > 0 && (
                  <>
                    {' '}
                    · <span style={{ color: 'var(--red-text)', fontWeight: 600 }}>{scanResult.missing_template.length} ohne Template</span>
                  </>
                )}
              </div>
              <button className="btn btn-primary" disabled={committing || selectedFolders.size === 0} onClick={handleCommit}>
                {committing ? 'Lege Jobs an…' : `${selectedFolders.size} Job(s) anlegen`}
              </button>
            </div>

            {(() => {
              const jobCount = scanResult.groups.filter((g) => selectedFolders.has(g.folder) && (g.template_key || defaultTemplateKey)).length
              if (jobCount <= 0 || costPerJob === null) return null
              return (
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    background: 'var(--accent-bg)',
                    border: '1px solid var(--accent-border)',
                    borderRadius: 6,
                    padding: '10px 12px',
                  }}
                >
                  <span style={{ fontSize: 12, color: 'var(--accent)', fontWeight: 600 }}>
                    Geschätzte Gesamtkosten ({jobCount} Video{jobCount === 1 ? '' : 's'}
                    {dryRun && ' · Dry-Run, keine echten Credits'})
                  </span>
                  <span style={{ fontSize: 13, color: 'var(--accent-hover)', fontWeight: 700 }}>
                    {costPerJob * jobCount} Credits
                  </span>
                </div>
              )
            })()}
          </div>
        )}

        {commitResult && (
          <div className="card">
            <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 10 }}>
              {commitResult.created.length} Job(s) angelegt
              {commitResult.errors.length > 0 && `, ${commitResult.errors.length} Fehler`}
            </div>
            {commitResult.errors.length > 0 && (
              <div style={{ fontSize: 12, color: 'var(--red-text)', marginBottom: 10 }}>
                {commitResult.errors.map((e) => (
                  <div key={e.variant_number}>
                    {e.variant_number}: {e.error}
                  </div>
                ))}
              </div>
            )}
            <button className="btn" onClick={onSwitchToDashboard}>
              Fortschritt im Dashboard ansehen
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

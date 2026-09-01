import { useEffect, useState } from 'react'
import { api } from '../api'
import PageHeader from '../components/PageHeader'
import CardHeader from '../components/CardHeader'
import { IconCheck, IconAlertTriangle, IconRefresh, IconFolder } from '../components/Icons'
import { RESOLUTION_ALLOWLIST, MODE_ALLOWLIST, modeLabel } from '../modelResolutions'

const SHOT_ORDER = ['full', 'front', 'fullback', 'detail_one']

// Kling only ever uses full+fullback (see backend/drive_scan.py
// TWO_IMAGE_MODEL_SHOT_ORDER) -- showing all 4 thumbnails would suggest front/
// detail_one matter for Kling when they're silently ignored.
const MODEL_SHOT_ORDER = {
  kling3_0: ['full', 'fullback'],
}

function ThumbnailStrip({ images, shotOrder, uncertainShots, onSwap }) {
  const [dragOverShot, setDragOverShot] = useState(null)
  return (
    <div style={{ display: 'flex', gap: 10, padding: '2px 12px 10px 34px' }}>
      {shotOrder.map((shot) => {
        const path = images?.[shot]
        const filename = path ? path.split('/').pop() : null
        const uncertain = path && uncertainShots?.includes(shot)
        const isDragOver = dragOverShot === shot
        return (
          <div key={shot} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3, width: 64 }}>
            <div
              draggable={!!path}
              onDragStart={(e) => {
                e.dataTransfer.setData('text/plain', shot)
                e.dataTransfer.effectAllowed = 'move'
              }}
              onDragEnter={(e) => {
                if (!path) return
                e.preventDefault()
              }}
              onDragOver={(e) => {
                if (!path) return
                e.preventDefault()
                if (dragOverShot !== shot) setDragOverShot(shot)
              }}
              onDragLeave={() => setDragOverShot((s) => (s === shot ? null : s))}
              onDrop={(e) => {
                e.preventDefault()
                setDragOverShot(null)
                const draggedShot = e.dataTransfer.getData('text/plain')
                if (draggedShot && draggedShot !== shot) onSwap?.(draggedShot, shot)
              }}
              style={{
                position: 'relative',
                width: 56,
                height: 56,
                borderRadius: 4,
                overflow: 'hidden',
                border: isDragOver
                  ? '2px solid var(--accent)'
                  : uncertain
                  ? '2px solid #f59e0b'
                  : path
                  ? '1px solid var(--border)'
                  : '1px dashed var(--text-faint)',
                background: path ? 'transparent' : '#fafafa',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                cursor: path ? 'grab' : 'default',
                // Safari needs this explicitly -- a plain draggable div (as
                // opposed to a native <img>/<a>) otherwise often just refuses
                // to start a drag at all.
                WebkitUserDrag: path ? 'element' : 'none',
                userSelect: 'none',
                WebkitUserSelect: 'none',
              }}
              title={
                uncertain
                  ? 'Automatisch nach Reihenfolge zugeordnet -- bitte prüfen und bei Bedarf per Drag & Drop mit einem anderen Bild tauschen'
                  : path
                  ? 'Zum Tauschen auf ein anderes Bild ziehen'
                  : undefined
              }
            >
              {path ? (
                <img
                  src={api.driveScanImageUrl(path)}
                  alt={shot}
                  draggable={false}
                  style={{ width: '100%', height: '100%', objectFit: 'cover', pointerEvents: 'none', WebkitUserDrag: 'none' }}
                />
              ) : (
                <span style={{ fontSize: 9, color: 'var(--text-faint)' }}>fehlt</span>
              )}
              {uncertain && (
                <span
                  style={{
                    position: 'absolute',
                    top: 2,
                    right: 2,
                    fontSize: 12,
                    lineHeight: 1,
                    background: '#f59e0b',
                    color: '#fff',
                    borderRadius: '50%',
                    width: 16,
                    height: 16,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  !
                </span>
              )}
            </div>
            <span
              style={{
                fontSize: 9,
                color: uncertain ? '#b45309' : 'var(--text-faint)',
                fontWeight: uncertain ? 700 : 400,
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
  const [mode, setMode] = useState('')
  const [dryRun, setDryRun] = useState(false)

  const [scanning, setScanning] = useState(false)
  const [scanError, setScanError] = useState('')
  const [scanResult, setScanResult] = useState(null)
  const [selectedFolders, setSelectedFolders] = useState(new Set())

  // Drag & drop lets people fix a wrong shot-type assignment (e.g. "front" and
  // "detail_one" swapped) right in the preview instead of renaming files in
  // Drive. imageOverrides is folder -> {shot_type: path}, layered on top of the
  // scan result and sent to commit so the fix actually sticks. correctedShots
  // tracks which shots were manually touched so the uncertain-flag warning
  // clears for them once the person has confirmed/fixed them by hand.
  const [imageOverrides, setImageOverrides] = useState({})
  const [correctedShots, setCorrectedShots] = useState({})

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

  // The scan itself finds every product under folderPath regardless of garment
  // type (oberteil/unterteil folders are usually scanned together from a shared
  // parent) -- only show/select the ones matching the currently chosen template
  // so switching the dropdown acts as a live filter, not just an undetected-folder
  // fallback.
  const visibleGroups = scanResult ? scanResult.groups.filter((g) => g.template_key === defaultTemplateKey) : []

  function groupImages(g) {
    return { ...g.images, ...(imageOverrides[g.folder] || {}) }
  }

  // Only flag a group as "uncertain" for shots the currently selected model
  // actually uses (Kling only looks at full+fullback -- a swapped front/detail
  // shot doesn't matter there) and only for shots the user hasn't already
  // manually fixed via drag & drop.
  function groupUncertainShots(g) {
    const corrected = correctedShots[g.folder]
    return (g.uncertain_shots || []).filter((s) => shotOrder.includes(s) && !corrected?.has(s))
  }

  function handleSwap(folder, shotA, shotB) {
    setImageOverrides((prev) => {
      const group = scanResult.groups.find((gr) => gr.folder === folder)
      const current = { ...group.images, ...(prev[folder] || {}) }
      return { ...prev, [folder]: { ...(prev[folder] || {}), [shotA]: current[shotB], [shotB]: current[shotA] } }
    })
    setCorrectedShots((prev) => {
      const set = new Set(prev[folder] || [])
      set.add(shotA)
      set.add(shotB)
      return { ...prev, [folder]: set }
    })
  }

  useEffect(() => {
    setSelectedFolders((prev) => {
      const visibleFolders = new Set(visibleGroups.map((g) => g.folder))
      const next = new Set([...prev].filter((f) => visibleFolders.has(f)))
      return next.size === prev.size ? prev : next
    })
  }, [defaultTemplateKey, scanResult]) // eslint-disable-line react-hooks/exhaustive-deps

  const selectedModelObj = models.find((m) => m.model === model)
  const resolutionParam = selectedModelObj?.schema?.params?.find((p) => p.name === 'resolution')
  const allowlist = RESOLUTION_ALLOWLIST[model]
  const resolutionOptions = allowlist ? (resolutionParam?.enum || []).filter((r) => allowlist.includes(r)) : resolutionParam?.enum || []
  const modeParam = selectedModelObj?.schema?.params?.find((p) => p.name === 'mode')
  const modeAllowlist = MODE_ALLOWLIST[model]
  const modeOptions = modeAllowlist ? (modeParam?.enum || []).filter((m) => modeAllowlist.includes(m)) : modeParam?.enum || []
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
    // Same idea as the resolution reset above -- a mode picked for one model
    // (e.g. Kling's "4k") isn't a valid value for another.
    setMode(modeParam ? modeParam.default || modeOptions[0] || '' : '')
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
        mode: modeParam ? mode : undefined,
      })
      .then((res) => setCostPerJob(res.credits))
      .catch((err) => setCostError(err.message))
  }, [model, resolution, mode, defaultTemplateKey, templates]) // eslint-disable-line react-hooks/exhaustive-deps

  async function handleScan() {
    if (!folderPath) return
    setScanning(true)
    setScanError('')
    setScanResult(null)
    setCommitResult(null)
    setImageOverrides({})
    setCorrectedShots({})
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
      // Only auto-select groups matching the currently chosen template --
      // otherwise a new product from the OTHER garment type gets silently
      // selected too (invisible in the list, but still counted in "N Job(s)
      // anlegen" and still included when the batch is committed).
      setSelectedFolders(
        new Set(
          result.groups
            .filter((g) => g.template_key === defaultTemplateKey && !alreadyDone.has(g.variant_number))
            .map((g) => g.folder)
        )
      )
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
        mode: modeParam && mode ? mode : null,
        dry_run: dryRun,
        include_folders: Array.from(selectedFolders),
        image_overrides: imageOverrides,
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
        <PageHeader title="Batch-Upload" description="Google-Drive-Ordner scannen, erkannte Produkte prüfen und Jobs anlegen." />

        <div className="card">
          <CardHeader icon={<IconFolder size={16} />} title="Ordner scannen" />

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
              <div style={{ fontSize: 12, color: 'var(--accent)', fontWeight: 600, marginTop: 6, padding: '6px 10px', background: 'var(--accent-bg)', border: '1px solid var(--accent-border)', borderRadius: 6 }}>
                ℹ️ Hinweise zur Bild-Ablage und Modellwahl findest du auf der Info-Seite.
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

            {modeParam && modeOptions.length > 0 && (
              <div className="field">
                <div className="field-label">
                  Modus {modeOptions.length === 1 && <span style={{ color: 'var(--text-faint)', fontWeight: 400 }}>(fix)</span>}
                </div>
                <select
                  className="select"
                  value={mode}
                  disabled={modeOptions.length === 1}
                  onChange={(e) => setMode(e.target.value)}
                >
                  {modeOptions.map((m) => (
                    <option key={m} value={m}>
                      {modeLabel(m)}
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
            <CardHeader
              icon={<IconCheck size={16} color="var(--accent)" />}
              title="Erkannte Produkte"
              action={
                <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
                  <button
                    className="btn-link"
                    onClick={() =>
                      setSelectedFolders((prev) =>
                        prev.size === visibleGroups.length ? new Set() : new Set(visibleGroups.map((g) => g.folder))
                      )
                    }
                  >
                    {selectedFolders.size === visibleGroups.length ? 'Alle abwählen' : 'Alle auswählen'}
                  </button>
                  <button className="btn-link" style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }} onClick={handleScan}>
                    <IconRefresh />
                    Erneut scannen
                  </button>
                </div>
              }
            />

            <div style={{ border: '1px solid var(--border-light)', borderRadius: 6, overflow: 'hidden', marginBottom: 12, maxHeight: 440, overflowY: 'auto' }}>
              {visibleGroups.map((g) => {
                const selected = selectedFolders.has(g.folder)
                const uncertainShots = groupUncertainShots(g)
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
                      <span style={{ fontWeight: 600 }}>{g.variant_number}</span>
                      {uncertainShots.length > 0 && (
                        <span
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: 4,
                            fontSize: 10,
                            fontWeight: 700,
                            color: '#b45309',
                            background: 'var(--amber-bg)',
                            border: '1px solid #fde68a',
                            borderRadius: 999,
                            padding: '2px 8px',
                          }}
                          title="Per Reihenfolge zugeordnet -- bitte in der Vorschau unten prüfen"
                        >
                          ⚠️ unsicher: {uncertainShots.join(', ')}
                        </span>
                      )}
                      <span style={{ flex: 1 }} />
                      <span style={{ color: 'var(--text-faint)' }}>{g.template_key || 'kein Template'}</span>
                      <span style={{ color: g.complete ? 'var(--text-faint)' : 'var(--amber-text)' }}>
                        {g.image_count} Bild{g.image_count === 1 ? '' : 'er'}
                        {!g.complete && ' · unvollständig'}
                      </span>
                    </label>
                    <ThumbnailStrip
                      images={groupImages(g)}
                      shotOrder={shotOrder}
                      uncertainShots={uncertainShots}
                      onSwap={(shotA, shotB) => handleSwap(g.folder, shotA, shotB)}
                    />
                  </div>
                )
              })}
              {visibleGroups.length === 0 && (
                <div style={{ padding: 16, fontSize: 12, color: 'var(--text-faint)' }}>
                  {scanResult.groups.length === 0
                    ? 'Keine passenden Bilder gefunden (erwartet: ein Ordner pro Produkt mit full.jpg, front.jpg, fullback.jpg, detail_one.jpg).'
                    : 'Keine Produkte für dieses Template in diesem Ordner gefunden.'}
                </div>
              )}
            </div>

            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
              <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                {selectedFolders.size} von {visibleGroups.length} ausgewählt
                {visibleGroups.some((g) => !g.complete) && (
                  <>
                    {' '}
                    ·{' '}
                    <span style={{ color: 'var(--amber-text)', fontWeight: 600 }}>
                      {visibleGroups.filter((g) => !g.complete).length} unvollständig
                    </span>
                  </>
                )}
                {visibleGroups.some((g) => groupUncertainShots(g).length > 0) && (
                  <>
                    {' '}
                    ·{' '}
                    <span style={{ color: '#b45309', fontWeight: 600 }}>
                      ⚠️ unsichere Zuordnung: {visibleGroups.filter((g) => groupUncertainShots(g).length > 0).map((g) => g.variant_number).join(', ')}
                    </span>
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
              const jobCount = visibleGroups.filter((g) => selectedFolders.has(g.folder)).length
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
            <CardHeader
              icon={<IconCheck size={16} color="var(--green-text)" />}
              title={`${commitResult.created.length} Job(s) angelegt${commitResult.errors.length > 0 ? `, ${commitResult.errors.length} Fehler` : ''}`}
            />
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

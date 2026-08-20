import { useEffect, useState } from 'react'
import { api } from '../api'
import { IconCheck, IconAlertTriangle, IconRefresh, IconFolder } from '../components/Icons'

export default function BatchUpload({ onSwitchToDashboard }) {
  const [templates, setTemplates] = useState([])
  const [models, setModels] = useState([])
  const [folderPath, setFolderPath] = useState('')
  const [defaultTemplateKey, setDefaultTemplateKey] = useState('')
  const [model, setModel] = useState('')
  const [dryRun, setDryRun] = useState(false)

  const [scanning, setScanning] = useState(false)
  const [scanError, setScanError] = useState('')
  const [scanResult, setScanResult] = useState(null)

  const [committing, setCommitting] = useState(false)
  const [commitResult, setCommitResult] = useState(null)

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
      })
      setScanResult(result)
    } catch (err) {
      setScanError(err.message)
    } finally {
      setScanning(false)
    }
  }

  async function handleCommit() {
    setCommitting(true)
    try {
      const result = await api.commitDriveScan({
        folder_path: folderPath,
        default_template_key: defaultTemplateKey || null,
        model,
        dry_run: dryRun,
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

            <div style={{ display: 'flex', gap: 14 }}>
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
              <button className="btn-link" style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }} onClick={handleScan}>
                <IconRefresh />
                Erneut scannen
              </button>
            </div>

            <div style={{ border: '1px solid var(--border-light)', borderRadius: 6, overflow: 'hidden', marginBottom: 12, maxHeight: 260, overflowY: 'auto' }}>
              {scanResult.groups.map((g) => (
                <div
                  key={`${g.folder}-${g.variant_number}`}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 10,
                    padding: '9px 12px',
                    borderBottom: '1px solid #f0f0f1',
                    fontSize: 12,
                    background: g.complete ? 'transparent' : '#fffbeb',
                  }}
                >
                  {g.complete ? <IconCheck /> : <IconAlertTriangle />}
                  <span style={{ flex: 1, fontWeight: 600 }}>{g.variant_number}</span>
                  <span style={{ color: 'var(--text-faint)' }}>{g.template_key || 'kein Template'}</span>
                  <span style={{ color: g.complete ? 'var(--text-faint)' : 'var(--amber-text)' }}>
                    {g.image_count} Bild{g.image_count === 1 ? '' : 'er'}
                    {!g.complete && ' · unvollständig'}
                  </span>
                </div>
              ))}
              {scanResult.groups.length === 0 && (
                <div style={{ padding: 16, fontSize: 12, color: 'var(--text-faint)' }}>
                  Keine passenden Bilder gefunden (erwartet: _full_front, _front_closeup, _full_back, _detail_shot).
                </div>
              )}
            </div>

            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                {scanResult.total} Produktordner erkannt
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
              <button className="btn btn-primary" disabled={committing || scanResult.total === 0} onClick={handleCommit}>
                {committing ? 'Lege Jobs an…' : `${scanResult.total} Job(s) anlegen`}
              </button>
            </div>
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

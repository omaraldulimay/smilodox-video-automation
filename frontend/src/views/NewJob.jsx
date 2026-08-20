import { useEffect, useState } from 'react'
import { api } from '../api'
import { IconUpload, IconX } from '../components/Icons'

const FULL_SLOTS = ['Front', 'Close-up', 'Back', 'Detail']

// Kling only exposes start_image/end_image (2 slots: first-frame/last-frame of one
// continuous turn) instead of a free image_references array -- Front + Back gives a
// natural front-to-back turn. Every other model here (Seedance 2.0, Gemini Omni)
// takes the full 4-image reference array.
const MODEL_SLOTS = {
  kling3_0: ['Front', 'Back'],
}

// Seedance's schema also lists 720p/4k, but the team only wants the cheap
// test tier and the production tier selectable here -- not the full enum.
const RESOLUTION_ALLOWLIST = {
  seedance_2_0: ['480p', '1080p'],
}

function slotsForModel(model) {
  return MODEL_SLOTS[model] || FULL_SLOTS
}

function ImageSlot({ label, file, dragOver, onPick, onDrop, onDragOver, onDragLeave, onClear }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <label
        onDragOver={(e) => {
          e.preventDefault()
          onDragOver()
        }}
        onDragLeave={onDragLeave}
        onDrop={(e) => {
          e.preventDefault()
          onDragLeave()
          const dropped = e.dataTransfer.files?.[0]
          if (dropped) onDrop(dropped)
        }}
        style={{
          position: 'relative',
          aspectRatio: '3/4',
          borderRadius: 6,
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          overflow: 'hidden',
          border: file ? '1px solid var(--border)' : `2px dashed ${dragOver ? 'var(--accent)' : 'var(--text-faint)'}`,
          background: file ? 'transparent' : dragOver ? 'var(--accent-bg)' : '#fafafa',
        }}
      >
        {file ? (
          <img
            src={URL.createObjectURL(file)}
            alt={label}
            style={{ width: '100%', height: '100%', objectFit: 'cover' }}
          />
        ) : (
          <IconUpload size={18} />
        )}
        <input
          type="file"
          accept="image/*"
          style={{ display: 'none' }}
          onChange={(e) => {
            const picked = e.target.files?.[0]
            if (picked) onPick(picked)
            e.target.value = '' // allow re-picking the same file / re-triggering onChange
          }}
        />
      </label>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}>
        <span
          style={{
            fontSize: 11,
            fontWeight: 600,
            color: 'var(--text-muted)',
            textTransform: 'uppercase',
            letterSpacing: '0.02em',
          }}
        >
          {label}
        </span>
        {file && (
          <button
            type="button"
            onClick={onClear}
            style={{ border: 'none', background: 'none', padding: 0, display: 'flex', cursor: 'pointer' }}
            aria-label={`${label} entfernen`}
          >
            <IconX size={11} />
          </button>
        )}
      </div>
    </div>
  )
}

export default function NewJob({ onJobCreated }) {
  const [templates, setTemplates] = useState([])
  const [models, setModels] = useState([])
  const [templateKey, setTemplateKey] = useState('')
  const [model, setModel] = useState('')
  const [files, setFiles] = useState([]) // sparse array, index-aligned with `slots`
  const [dragOverIndex, setDragOverIndex] = useState(null)
  const [dryRun, setDryRun] = useState(false)
  const [resolution, setResolution] = useState('')
  const [cost, setCost] = useState(null)
  const [costError, setCostError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    api.getTemplates().then((ts) => {
      setTemplates(ts)
      if (ts.length) setTemplateKey(ts[0].template_key)
    })
    api.getModels().then((ms) => {
      setModels(ms)
      const first = ms.find((m) => !m.error)
      if (first) setModel(first.model)
    })
  }, [])

  const selectedTemplate = templates.find((t) => t.template_key === templateKey)
  const slots = slotsForModel(model)
  const selectedModelObj = models.find((m) => m.model === model)
  const resolutionParam = selectedModelObj?.schema?.params?.find((p) => p.name === 'resolution')
  const allowlist = RESOLUTION_ALLOWLIST[model]
  const resolutionOptions = allowlist ? (resolutionParam?.enum || []).filter((r) => allowlist.includes(r)) : resolutionParam?.enum || []

  useEffect(() => {
    // Model switch can change the expected image count/order (e.g. 4 -> 2 for
    // Kling) -- drop anything that no longer has a matching slot.
    setFiles((prev) => prev.slice(0, slots.length))
  }, [model]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    // Reset resolution to the model's own default whenever the model changes --
    // a value chosen for one model (e.g. 480p) may not be valid for another.
    // If the schema default isn't in our allowlisted options (e.g. Seedance's
    // real default is 720p, which we no longer offer), fall back to the
    // cheapest allowed option instead.
    if (resolutionParam) {
      const preferred = resolutionParam.default
      const fallback = resolutionOptions[0] || ''
      setResolution(resolutionOptions.includes(preferred) ? preferred : fallback)
    } else {
      setResolution('')
    }
  }, [model]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!selectedTemplate || !model) return
    setCost(null)
    setCostError('')
    api
      .costEstimate({
        model,
        duration: selectedTemplate.duration,
        aspect_ratio: selectedTemplate.aspect_ratio,
        resolution: resolutionParam ? resolution : selectedTemplate.resolution,
      })
      .then((res) => setCost(res.credits))
      .catch((err) => setCostError(err.message))
  }, [model, selectedTemplate?.template_key, resolution])

  function setFileAt(index, file) {
    setFiles((prev) => {
      const next = [...prev]
      next[index] = file
      return next
    })
  }

  function clearFileAt(index) {
    setFiles((prev) => {
      const next = [...prev]
      next[index] = undefined
      return next
    })
  }

  async function handleSubmit() {
    if (!selectedTemplate || !model) return
    setSubmitting(true)
    setError('')
    try {
      const form = new FormData()
      form.append('model', model)
      form.append('template_key', templateKey)
      form.append('dry_run', String(dryRun))
      if (resolutionParam && resolution) form.append('resolution', resolution)
      files.filter(Boolean).forEach((f) => form.append('references', f))
      const result = await api.createJob(form)
      setFiles([])
      onJobCreated?.(result.job_id)
    } catch (err) {
      setError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="view-body" style={{ display: 'flex', gap: 24 }}>
      {/* Left: form */}
      <div
        className="card"
        style={{ width: 380, flexShrink: 0, display: 'flex', flexDirection: 'column', gap: 18, alignSelf: 'flex-start' }}
      >
        <div style={{ fontSize: 14, fontWeight: 700 }}>Neuen Job erstellen</div>

        <div className="field">
          <div className="field-label">Template</div>
          <select className="select" value={templateKey} onChange={(e) => setTemplateKey(e.target.value)}>
            {templates.map((t) => (
              <option key={t.template_key} value={t.template_key}>
                {t.garment_type}
              </option>
            ))}
          </select>
        </div>

        <div className="field">
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
          <span style={{ fontSize: 12, color: 'var(--accent)', fontWeight: 600 }}>Geschätzte Kosten</span>
          <span style={{ fontSize: 13, color: 'var(--accent-hover)', fontWeight: 700 }}>
            {costError ? '—' : cost === null ? '…' : `${cost} Credits`}
          </span>
        </div>
        {costError && <div style={{ fontSize: 11, color: 'var(--red-text)' }}>{costError}</div>}

        <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: '#52525b', cursor: 'pointer' }}>
          <input type="checkbox" checked={dryRun} onChange={(e) => setDryRun(e.target.checked)} />
          Nur Kosten schätzen (Dry-Run, kein echter Job)
        </label>

        <div style={{ height: 1, background: 'var(--border-light)' }} />

        {error && <div style={{ fontSize: 12, color: 'var(--red-text)' }}>{error}</div>}

        <button className="btn btn-primary" disabled={submitting || !templateKey || !model} onClick={handleSubmit}>
          {submitting ? 'Wird erstellt…' : 'Job erstellen'}
        </button>
      </div>

      {/* Right: reference images */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 16 }}>
        <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div>
            <div style={{ fontSize: 14, fontWeight: 700 }}>Referenzbilder</div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>
              Jedes Feld ist ein eigener Slot — Auswahl in einem Feld überschreibt nur dieses Bild.
            </div>
          </div>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: `repeat(${slots.length}, minmax(0,1fr))`,
              gap: 12,
              maxWidth: slots.length <= 2 ? '50%' : '100%',
            }}
          >
            {slots.map((label, i) => (
              <ImageSlot
                key={label}
                label={label}
                file={files[i]}
                dragOver={dragOverIndex === i}
                onPick={(file) => setFileAt(i, file)}
                onDrop={(file) => setFileAt(i, file)}
                onDragOver={() => setDragOverIndex(i)}
                onDragLeave={() => setDragOverIndex((cur) => (cur === i ? null : cur))}
                onClear={() => clearFileAt(i)}
              />
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

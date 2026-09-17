import { useEffect, useState } from 'react'
import { api } from '../api'
import PageHeader from '../components/PageHeader'
import { IconLock, IconLockOpen, IconCheck, IconAlertTriangle } from '../components/Icons'

const GARMENTS = [
  { key: 'oberteil', label: 'Oberteil' },
  { key: 'unterteil', label: 'Unterteil' },
]

// Local, non-persisted JSON syntax check -- catches a broken edit the moment
// someone types it, before they even hit Speichern (the backend re-validates
// independently, this is purely so the error shows up immediately instead of
// only after a round-trip).
function jsonError(text) {
  try {
    JSON.parse(text)
    return null
  } catch (err) {
    return err.message
  }
}

function PromptColumn({ garment, value, isCustom, unlocked, onSave, onReset }) {
  const [text, setText] = useState(value)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState(null)

  useEffect(() => {
    setText(value)
    setMessage(null)
  }, [value])

  const dirty = text !== value
  const parseError = dirty ? jsonError(text) : null

  async function handleSave() {
    setSaving(true)
    setMessage(null)
    try {
      await onSave(text)
      setMessage({ tone: 'ok', text: 'Gespeichert.' })
    } catch (err) {
      setMessage({ tone: 'error', text: err.message })
    } finally {
      setSaving(false)
    }
  }

  async function handleReset() {
    setSaving(true)
    setMessage(null)
    try {
      await onReset()
      setMessage({ tone: 'ok', text: 'Auf Standard zurückgesetzt.' })
    } catch (err) {
      setMessage({ tone: 'error', text: err.message })
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 12, flex: 1, minWidth: 0 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ fontSize: 14, fontWeight: 700 }}>{garment.label}</div>
        {isCustom ? (
          <span className="badge" style={{ background: 'var(--accent-bg)', color: 'var(--accent)' }}>
            angepasst
          </span>
        ) : (
          <span className="badge" style={{ background: 'var(--surface-sunken)', color: 'var(--text-muted)' }}>
            Standard
          </span>
        )}
      </div>

      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        readOnly={!unlocked}
        spellCheck={false}
        rows={20}
        style={{
          width: '100%',
          fontFamily: '"SF Mono", Menlo, Consolas, monospace',
          fontSize: 11.5,
          lineHeight: 1.5,
          padding: 12,
          border: '1px solid var(--border)',
          borderRadius: 'var(--radius-sm)',
          background: unlocked ? 'var(--surface)' : 'var(--surface-sunken)',
          color: 'var(--text)',
          resize: 'vertical',
          outline: 'none',
        }}
      />

      {parseError && (
        <div style={{ display: 'flex', gap: 6, alignItems: 'flex-start', fontSize: 12, color: '#d97706' }}>
          <IconAlertTriangle />
          <span>Kein gültiges JSON: {parseError}</span>
        </div>
      )}

      {message && (
        <div
          style={{
            display: 'flex',
            gap: 6,
            alignItems: 'flex-start',
            fontSize: 12,
            color: message.tone === 'ok' ? '#16a34a' : '#dc2626',
          }}
        >
          {message.tone === 'ok' ? <IconCheck /> : <IconAlertTriangle color="#dc2626" />}
          <span>{message.text}</span>
        </div>
      )}

      {unlocked && (
        <div style={{ display: 'flex', gap: 8 }}>
          <button
            className="btn btn-primary"
            disabled={!dirty || !!parseError || saving}
            onClick={handleSave}
          >
            {saving ? 'Speichert…' : 'Speichern'}
          </button>
          <button className="btn" disabled={!isCustom || saving} onClick={handleReset}>
            Auf Standard zurücksetzen
          </button>
          {dirty && (
            <button className="btn-link" onClick={() => setText(value)} style={{ alignSelf: 'center' }}>
              Änderungen verwerfen
            </button>
          )}
        </div>
      )}
    </div>
  )
}

export default function Prompts() {
  const [prompts, setPrompts] = useState(null)
  const [error, setError] = useState(null)
  const [code, setCode] = useState('')
  const [unlocked, setUnlocked] = useState(false)
  const [unlocking, setUnlocking] = useState(false)
  const [unlockError, setUnlockError] = useState(null)

  useEffect(() => {
    api
      .getPrompts()
      .then(setPrompts)
      .catch((err) => setError(err.message))
  }, [])

  async function handleUnlock(e) {
    e.preventDefault()
    setUnlocking(true)
    setUnlockError(null)
    try {
      await api.unlockPrompts(code)
      setUnlocked(true)
    } catch (err) {
      setUnlockError('Falscher Code.')
    } finally {
      setUnlocking(false)
    }
  }

  function updateGarment(key, patch) {
    setPrompts((prev) => ({ ...prev, [key]: { ...prev[key], ...patch } }))
  }

  return (
    <div className="view-body" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <PageHeader
        wide
        title="Prompt"
        description="Der genaue Text, der an Kling geschickt wird -- getrennt für Oberteil und Unterteil. Änderungen wirken sofort auf alle neuen Videos."
      />

      {!unlocked && (
        <form
          onSubmit={handleUnlock}
          className="card"
          style={{ display: 'flex', alignItems: 'center', gap: 12, maxWidth: 480 }}
        >
          <IconLock />
          <input
            className="text-input"
            type="password"
            placeholder="Code zum Bearbeiten"
            value={code}
            onChange={(e) => setCode(e.target.value)}
            style={{ flex: 1 }}
          />
          <button className="btn btn-primary" type="submit" disabled={!code || unlocking}>
            {unlocking ? 'Prüft…' : 'Entsperren'}
          </button>
        </form>
      )}
      {unlocked && (
        <div
          className="card"
          style={{ display: 'flex', alignItems: 'center', gap: 8, maxWidth: 480, color: '#16a34a', fontSize: 13, fontWeight: 600 }}
        >
          <IconLockOpen />
          Bearbeitung entsperrt
        </div>
      )}
      {unlockError && (
        <div style={{ fontSize: 12, color: '#dc2626', display: 'flex', alignItems: 'center', gap: 6 }}>
          <IconAlertTriangle color="#dc2626" />
          {unlockError}
        </div>
      )}

      {error && <div style={{ color: '#dc2626', fontSize: 13 }}>{error}</div>}

      {prompts && (
        <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
          {GARMENTS.map((garment) => (
            <PromptColumn
              key={garment.key}
              garment={garment}
              value={prompts[garment.key].prompt_text}
              isCustom={prompts[garment.key].is_custom}
              unlocked={unlocked}
              onSave={async (text) => {
                const res = await api.savePrompt(garment.key, text, code)
                updateGarment(garment.key, { prompt_text: res.prompt_text, is_custom: res.is_custom })
              }}
              onReset={async () => {
                const res = await api.resetPrompt(garment.key, code)
                updateGarment(garment.key, { prompt_text: res.prompt_text, is_custom: res.is_custom })
              }}
            />
          ))}
        </div>
      )}
    </div>
  )
}

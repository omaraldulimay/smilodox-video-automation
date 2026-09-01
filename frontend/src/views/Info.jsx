import PageHeader from '../components/PageHeader'
import { IconFolder, IconFilm } from '../components/Icons'

function IconBadge({ children, tone = 'accent' }) {
  const tones = {
    accent: { background: 'var(--accent-bg)', color: 'var(--accent)' },
    amber: { background: 'var(--amber-bg)', color: 'var(--amber-text)' },
  }
  return (
    <div
      style={{
        width: 32,
        height: 32,
        borderRadius: 8,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexShrink: 0,
        ...tones[tone],
      }}
    >
      {children}
    </div>
  )
}

function Section({ icon, title, children }) {
  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <IconBadge>{icon}</IconBadge>
        <div style={{ fontSize: 14, fontWeight: 700 }}>{title}</div>
      </div>
      <div style={{ fontSize: 13, color: 'var(--text-muted)', lineHeight: 1.6, display: 'flex', flexDirection: 'column', gap: 8, paddingLeft: 42 }}>
        {children}
      </div>
    </div>
  )
}

export default function Info() {
  return (
    <div className="view-body" style={{ display: 'flex', justifyContent: 'center' }}>
      <div style={{ width: 640 }}>
        <PageHeader title="Info" description="Kurzanleitung für die Bild-Ablage und die Modellwahl im Portal." />

        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <Section icon={<IconFolder size={16} />} title="Bilder ablegen">
            <div>Bilder in die geteilte Google-Drive-Ablage "Smilodox Video Automation" legen.</div>
            <div>1 Ordner pro Produkt (oberteil/unterteil), 4 Bilder: Ganzkörper, Nahaufnahme, Rücken, Detail. Benennung nicht nötig.</div>
            <div>
              <span
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  width: 14,
                  height: 14,
                  fontSize: 10,
                  background: 'var(--amber)',
                  color: '#fff',
                  borderRadius: '50%',
                  marginRight: 5,
                  fontWeight: 700,
                }}
              >
                !
              </span>
              = unsicher zugeordnet, kurz prüfen. Falsch zugeordnet? Bild per Drag & Drop auf den richtigen Platz ziehen.
            </div>
          </Section>

          <Section icon={<IconFilm size={16} />} title="Modellwahl">
            <div>Kling: günstiger. Gemini: genauer (4 statt 2 Referenzbilder), aber:</div>
            <div
              style={{
                background: 'var(--amber-bg)',
                border: '1px solid #fde68a',
                borderRadius: 6,
                padding: '8px 10px',
                color: 'var(--amber-text)',
                fontWeight: 600,
              }}
            >
              ⚠️ Bei freizügiger Kleidung scheitert Gemini oft an NSFW → dann Kling nehmen.
            </div>
          </Section>
        </div>
      </div>
    </div>
  )
}

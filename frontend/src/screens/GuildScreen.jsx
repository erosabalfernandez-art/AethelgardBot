import { useState, useEffect } from 'react'
import { api } from '../api'

const CLASE_EMOJI = { vanguardista: '🛡️', acechante: '🗡️', tejehechizos: '🔮', maestro_caza: '🏹' }
const RANGO_ORDER = { lider: 1, oficial: 2, veterano: 3, recluta: 4, miembro: 5 }

export default function GuildScreen({ player, showToast, onNavigate }) {
  const [guildData, setGuildData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.getGuild().then(d => {
      setGuildData(d.guild)
    }).finally(() => setLoading(false))
  }, [])

  if (loading) return <div style={{ display: 'flex', justifyContent: 'center', padding: '40px' }}><div className="spinner" /></div>

  if (!guildData) {
    return (
      <div style={{ padding: '40px 20px', textAlign: 'center' }}>
        <div style={{ fontSize: '64px', marginBottom: '16px' }}>⚔️</div>
        <div style={{ fontFamily: 'Cinzel,serif', fontSize: '18px', color: 'var(--text-gold)', marginBottom: '10px' }}>Sin Gremio</div>
        <div style={{ fontSize: '13px', color: 'var(--text-muted)', marginBottom: '20px', maxWidth: '260px', margin: '0 auto 20px', lineHeight: 1.6 }}>
          No perteneces a ningún gremio. Para unirte o crear uno, habla con el Maestro de Gremios en el bot de Telegram.
        </div>
        <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '12px', padding: '16px', maxWidth: '300px', margin: '0 auto', textAlign: 'left' }}>
          <div style={{ fontFamily: 'Cinzel,serif', fontSize: '13px', color: 'var(--text-gold)', marginBottom: '10px' }}>📋 ¿Cómo unirme a un Gremio?</div>
          <div style={{ fontSize: '12px', color: 'var(--text-secondary)', lineHeight: 1.7 }}>
            1. Ve al bot de Telegram<br />
            2. Usa el comando /gremio<br />
            3. Elige "Unirme a un Gremio" o "Crear Gremio" (coste: 5,000 🪙)<br />
            4. ¡Vuelve aquí para gestionar tu gremio!
          </div>
        </div>
      </div>
    )
  }

  const guild = guildData
  const members = (guild.miembros || []).sort((a, b) => (RANGO_ORDER[a.rango] || 9) - (RANGO_ORDER[b.rango] || 9))
  const esLider = guild.rango_propio === 'lider'
  const esOficial = guild.rango_propio === 'oficial' || esLider

  return (
    <div>
      <div className="guild-banner">
        <div className="guild-tag">[{guild.tag}]</div>
        <div style={{ fontFamily: 'Cinzel,serif', fontSize: '20px', fontWeight: 700, color: 'var(--text-gold)', marginBottom: '4px' }}>{guild.nombre}</div>
        <div style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
          {guild.faccion} · Nivel {guild.nivel} · {members.length} miembros
        </div>
        {guild.rango_propio && (
          <div style={{ marginTop: '8px' }}>
            <span className="badge badge-amarilla">Tu rango: {guild.rango_propio}</span>
          </div>
        )}
      </div>

      <div style={{ padding: '12px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', marginBottom: '12px' }}>
          <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-gold)', borderRadius: '12px', padding: '14px', textAlign: 'center' }}>
            <div style={{ color: 'var(--gold)', fontFamily: 'Cinzel,serif', fontSize: '18px', fontWeight: 700 }}>{(guild.banco_oro || 0).toLocaleString()}</div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>🪙 Banco Oro</div>
          </div>
          <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '12px', padding: '14px', textAlign: 'center' }}>
            <div style={{ color: 'var(--purple-light)', fontFamily: 'Cinzel,serif', fontSize: '18px', fontWeight: 700 }}>{guild.banco_eternium || 0}</div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>💎 Banco Eternium</div>
          </div>
        </div>

        <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '14px', padding: '14px', marginBottom: '12px' }}>
          <div style={{ fontFamily: 'Cinzel,serif', fontSize: '13px', color: 'var(--text-gold)', marginBottom: '12px', letterSpacing: '0.06em' }}>
            👥 MIEMBROS ({members.length})
          </div>
          {members.map((m, i) => (
            <div key={i} className="member-row">
              <span className="member-class-emoji">{CLASE_EMOJI[m.clase] || '⚔️'}</span>
              <div className="member-info">
                <div className="member-name">{m.nombre_personaje || m.user_id}</div>
                <div className="member-sub">Nv {m.nivel} · {m.clase} · {m.faccion}</div>
              </div>
              <div className="member-rank">{m.rango}</div>
            </div>
          ))}
        </div>

        {guild.territorios && guild.territorios.length > 0 && (
          <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '14px', padding: '14px', marginBottom: '12px' }}>
            <div style={{ fontFamily: 'Cinzel,serif', fontSize: '13px', color: 'var(--text-gold)', marginBottom: '10px' }}>🗺️ TERRITORIOS CONTROLADOS</div>
            {guild.territorios.map((t, i) => (
              <div key={i} style={{ fontSize: '13px', color: 'var(--text-secondary)', padding: '4px 0' }}>🏴 {t}</div>
            ))}
          </div>
        )}

        <div style={{ background: 'rgba(212,175,55,0.05)', border: '1px solid var(--border-gold)', borderRadius: '12px', padding: '14px', fontSize: '12px', color: 'var(--text-secondary)', lineHeight: 1.7 }}>
          💡 La gestión avanzada de gremios (guerra, edificios, asedios) se realiza a través del bot de Telegram para mayor control.
          <br /><br />
          ⚡ Energía del Nexo: <strong style={{ color: 'var(--text-gold)' }}>{guild.energia_nexo || 0}</strong>
        </div>
      </div>
    </div>
  )
}

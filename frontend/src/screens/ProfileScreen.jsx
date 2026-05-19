import { useState, useEffect } from 'react'
import { api } from '../api'

const CLASS_BIG_EMOJI = {
  vanguardista: '🛡️', acechante: '🗡️', tejehechizos: '🔮', maestro_caza: '🏹'
}
const FACCION_COLOR = { Alianza: '#3b82f6', Imperio: '#ef4444', Sindicato: '#a855f7' }

export default function ProfileScreen({ player, onNavigate, showToast }) {
  const [stats, setStats] = useState(null)
  const [notifs, setNotifs] = useState([])
  const [tab, setTab] = useState('stats')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([api.getStats(), api.getNotifications()]).then(([s, n]) => {
      setStats(s)
      setNotifs(n.notifications || [])
      setLoading(false)
    }).catch(() => setLoading(false))
  }, [])

  if (!player) return null

  const fColor = FACCION_COLOR[player.faccion] || '#7c3aed'
  const classEmoji = CLASS_BIG_EMOJI[player.clase] || '⚔️'

  return (
    <div>
      <div className="profile-header">
        <span className="class-avatar">{classEmoji}</span>
        <div className="player-name">{player.nombre}</div>
        <div className="player-subtitle">
          {player.clase_nombre} · {player.faccion}
          {player.titulo && <> · <em>{player.titulo}</em></>}
        </div>
        {player.reencarnaciones > 0 && (
          <div style={{ marginTop: '6px', fontSize: '12px', color: 'var(--text-muted)' }}>
            ♾️ Reencarnaciones: {player.reencarnaciones}
          </div>
        )}
      </div>

      <div style={{ display: 'flex', gap: '4px', padding: '10px 12px 0', borderBottom: '1px solid var(--border)' }}>
        {[['stats', '📊 Stats'], ['habs', '✨ Habilidades'], ['notifs', `🔔 Notifs${notifs.length > 0 ? ` (${notifs.length})` : ''}`]].map(([id, label]) => (
          <button key={id} className={`inv-tab ${tab === id ? 'active' : ''}`} onClick={() => setTab(id)}>{label}</button>
        ))}
      </div>

      {tab === 'stats' && (
        <div style={{ padding: '14px 12px' }}>
          <div className="stats-grid">
            <div className="stat-item">
              <div className="stat-value">{player.nivel}</div>
              <div className="stat-label">Nivel</div>
            </div>
            <div className="stat-item">
              <div className="stat-value" style={{ color: 'var(--red)' }}>{player.atk}</div>
              <div className="stat-label">⚔️ ATK</div>
            </div>
            <div className="stat-item">
              <div className="stat-value" style={{ color: 'var(--blue)' }}>{player.def}</div>
              <div className="stat-label">🛡️ DEF</div>
            </div>
            <div className="stat-item">
              <div className="stat-value" style={{ color: 'var(--green)' }}>{player.hp_max}</div>
              <div className="stat-label">❤️ HP Max</div>
            </div>
            <div className="stat-item">
              <div className="stat-value" style={{ color: 'var(--gold)' }}>{(player.oro || 0).toLocaleString()}</div>
              <div className="stat-label">🪙 Oro</div>
            </div>
            <div className="stat-item">
              <div className="stat-value" style={{ color: 'var(--purple-light)' }}>{player.eternium}</div>
              <div className="stat-label">💎 Eternium</div>
            </div>
          </div>

          <div className="card" style={{ margin: '0 0 12px' }}>
            <div className="card-title">⚡ Stamina</div>
            <div style={{ marginBottom: '8px' }}>
              <div style={{ height: '10px', background: 'rgba(255,255,255,0.08)', borderRadius: '5px', overflow: 'hidden' }}>
                <div style={{ height: '100%', width: `${player.stamina_pct}%`, background: 'linear-gradient(90deg,#b45309,#f59e0b)', borderRadius: '5px', transition: 'width 0.5s' }} />
              </div>
            </div>
            <div style={{ fontSize: '13px', color: 'var(--text-secondary)', textAlign: 'center' }}>
              {player.stamina_actual} / {player.stamina_max}
            </div>
          </div>

          <div className="card" style={{ margin: '0 0 12px' }}>
            <div className="card-title">📈 Experiencia</div>
            <div style={{ marginBottom: '8px' }}>
              <div style={{ height: '10px', background: 'rgba(255,255,255,0.08)', borderRadius: '5px', overflow: 'hidden' }}>
                <div style={{ height: '100%', width: `${player.xp_pct}%`, background: 'linear-gradient(90deg,#6d28d9,#a78bfa)', borderRadius: '5px', transition: 'width 0.5s' }} />
              </div>
            </div>
            <div style={{ fontSize: '12px', color: 'var(--text-muted)', textAlign: 'center', fontFamily: 'sans-serif' }}>
              {(player.xp_progreso || 0).toLocaleString()} / {(player.xp_necesaria || 0).toLocaleString()} XP para Nv {player.nivel + 1}
            </div>
          </div>

          {stats && stats.gremio && (
            <div className="card" style={{ margin: '0 0 12px' }}>
              <div className="card-title">⚔️ Gremio</div>
              <div style={{ fontSize: '14px', color: 'var(--text-primary)', marginBottom: '4px' }}>{stats.gremio}</div>
              <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Rango: {stats.gremio_rango}</div>
            </div>
          )}

          {stats?.codigo_invitacion && (
            <div className="card" style={{ margin: '0 0 12px' }}>
              <div className="card-title">🎟️ Código de Invitación</div>
              <div style={{ fontFamily: 'monospace', fontSize: '18px', textAlign: 'center', color: 'var(--text-gold)', letterSpacing: '0.15em', padding: '8px' }}>
                {stats.codigo_invitacion}
              </div>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)', textAlign: 'center' }}>Comparte para reclutar y ganar bonificaciones</div>
            </div>
          )}
        </div>
      )}

      {tab === 'habs' && stats && (
        <div style={{ padding: '14px 12px' }}>
          <div className="card" style={{ margin: '0 0 12px' }}>
            <div className="card-title">⚔️ Habilidades Activas</div>
            {(stats.habilidades || []).map((hab, i) => (
              <div key={i} style={{ padding: '12px 0', borderBottom: i < stats.habilidades.length - 1 ? '1px solid var(--border)' : 'none' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
                  <div style={{ fontFamily: 'Cinzel,serif', fontSize: '14px', fontWeight: 700, color: 'var(--text-accent)' }}>
                    {hab.emoji} {hab.nombre}
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontFamily: 'sans-serif' }}>CD: {hab.cooldown} turnos</div>
                </div>
                <div style={{ fontSize: '12px', color: 'var(--text-secondary)', lineHeight: 1.4 }}>{hab.descripcion}</div>
                <div style={{ display: 'flex', gap: '8px', marginTop: '6px', flexWrap: 'wrap' }}>
                  {hab.daño && <span style={{ fontSize: '11px', color: 'var(--red)', fontFamily: 'sans-serif' }}>⚔️ {hab.daño} daño</span>}
                  {hab.cura && <span style={{ fontSize: '11px', color: 'var(--green)', fontFamily: 'sans-serif' }}>💚 {hab.cura} curación</span>}
                  {hab.ignora_defensa && <span style={{ fontSize: '11px', color: 'var(--orange)', fontFamily: 'sans-serif' }}>🛡️ -{Math.round(hab.ignora_defensa * 100)}% def</span>}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {tab === 'notifs' && (
        <div style={{ padding: '14px 12px' }}>
          {notifs.length === 0 ? (
            <div className="empty-state">
              <div className="empty-icon">🔔</div>
              No tienes notificaciones pendientes
            </div>
          ) : notifs.map((n, i) => (
            <div key={i} style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '10px', padding: '12px', marginBottom: '8px', fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.4 }}>
              <div style={{ fontSize: '10px', color: 'var(--text-muted)', marginBottom: '4px', fontFamily: 'sans-serif' }}>{n.fecha_creacion?.split('T')[0]}</div>
              {n.mensaje}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

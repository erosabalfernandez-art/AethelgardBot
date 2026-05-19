import { useState, useEffect } from 'react'
import { api } from '../api'

const COLOR_LABEL = { azul: '🔵 Azul', amarilla: '🟡 Amarilla', roja: '🔴 Roja', negra: '⚫ Negra' }
const DIFF_COLOR = { Normal: 'var(--green)', Difícil: 'var(--red)' }

function DungeonResult({ result, onClose }) {
  const success = result.status === 'completed'
  return (
    <div className="result-overlay">
      <div className="result-icon">{success ? '🏆' : '💀'}</div>
      <div className={`result-title ${success ? 'victory' : 'defeat'}`}>{result.resultado}</div>
      <div className="result-rewards" style={{ width: '100%', maxWidth: '300px' }}>
        <div className="reward-row"><span className="reward-label">⚔️ Salas</span><span className="reward-value">{result.salas_superadas}/{result.total_salas}</span></div>
        <div className="reward-row"><span className="reward-label">✨ XP</span><span className="reward-value">+{result.xp_ganada}</span></div>
        <div className="reward-row"><span className="reward-label">🪙 Oro</span><span className="reward-value">{result.oro_ganado >= 0 ? '+' : ''}{result.oro_ganado}</span></div>
        <div className="reward-row"><span className="reward-label">💎 Eternium</span><span className="reward-value">+{result.eternium_ganado}</span></div>
        {result.level_up && (
          <div className="reward-row" style={{ borderTop: '1px solid var(--border)', paddingTop: '8px', marginTop: '4px' }}>
            <span className="reward-label">🎉</span>
            <span className="reward-value" style={{ color: 'var(--purple-light)' }}>¡NIVEL {result.nivel_nuevo}!</span>
          </div>
        )}
      </div>
      <div style={{ maxWidth: '300px', marginBottom: '12px' }}>
        {result.log?.slice(-5).map((line, i) => (
          <div key={i} style={{ fontSize: '12px', color: 'var(--text-secondary)', padding: '3px 0', lineHeight: 1.4 }}>{line}</div>
        ))}
      </div>
      <button className="btn btn-primary" onClick={onClose}>Continuar</button>
    </div>
  )
}

export default function DungeonScreen({ player, onNavigate, showToast, onRefresh }) {
  const [dungeons, setDungeons] = useState([])
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState(null)
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState(null)
  const [partyId, setPartyId] = useState('')
  const [joinId, setJoinId] = useState('')
  const [tab, setTab] = useState('mazmorras')

  useEffect(() => {
    api.getDungeons().then(d => {
      setDungeons(d.mazmorras || [])
    }).finally(() => setLoading(false))
  }, [])

  const handleEnter = async (dungeon, solo = true) => {
    setRunning(true)
    try {
      const res = await api.startDungeon(dungeon.id, solo)
      setResult(res)
      onRefresh()
    } catch (e) { showToast(e.message, 'error') }
    setRunning(false)
    setSelected(null)
  }

  const handleCreateParty = async () => {
    try {
      const res = await api.createParty()
      setPartyId(String(res.party_id))
      showToast(res.message, 'success')
    } catch (e) { showToast(e.message, 'error') }
  }

  const handleJoinParty = async () => {
    if (!joinId) return
    try {
      const res = await api.joinParty(parseInt(joinId))
      showToast(res.message, 'success')
    } catch (e) { showToast(e.message, 'error') }
  }

  if (result) {
    return <DungeonResult result={result} onClose={() => { setResult(null); setSelected(null) }} />
  }

  if (selected) {
    return (
      <div>
        <div className="section-header">
          <button className="btn btn-ghost btn-sm" onClick={() => setSelected(null)}>← Volver</button>
          <div className="section-title">{selected.emoji} {selected.nombre}</div>
        </div>
        <div style={{ padding: '0 12px 12px' }}>
          <div style={{ background: 'rgba(0,0,0,0.3)', border: '1px solid var(--border)', borderRadius: '12px', padding: '14px', marginBottom: '12px', fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
            {selected.descripcion}
          </div>
          <div className="card" style={{ margin: '0 0 12px' }}>
            <div className="card-title">📊 Información</div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', fontSize: '13px' }}>
              <div><span style={{ color: 'var(--text-muted)' }}>Nivel mín:</span> <span style={{ color: 'var(--text-gold)' }}>{selected.nivel_req}</span></div>
              <div><span style={{ color: 'var(--text-muted)' }}>Salas:</span> <span style={{ color: 'var(--text-gold)' }}>{selected.salas}</span></div>
              <div><span style={{ color: 'var(--text-muted)' }}>Coste:</span> <span style={{ color: 'var(--gold)' }}>{selected.coste_oro.toLocaleString()} 🪙</span></div>
              <div><span style={{ color: 'var(--text-muted)' }}>Disponibles hoy:</span> <span style={{ color: 'var(--green)' }}>{selected.disponibles_hoy}</span></div>
              <div><span style={{ color: 'var(--text-muted)' }}>Zona:</span> <span>{COLOR_LABEL[selected.color]}</span></div>
              <div><span style={{ color: 'var(--text-muted)' }}>Dificultad:</span> <span style={{ color: DIFF_COLOR[selected.dificultad] }}>{selected.dificultad}</span></div>
            </div>
          </div>
          <div className="card" style={{ margin: '0 0 12px' }}>
            <div className="card-title">🎁 Recompensas</div>
            <div style={{ display: 'flex', gap: '16px', fontSize: '13px', flexWrap: 'wrap' }}>
              <div>✨ Hasta <span style={{ color: 'var(--purple-light)', fontWeight: 700 }}>{selected.xp_base.toLocaleString()} XP</span></div>
              <div>🪙 Hasta <span style={{ color: 'var(--gold)', fontWeight: 700 }}>{selected.oro_base.toLocaleString()} Oro</span></div>
              <div>💎 <span style={{ color: 'var(--blue)', fontWeight: 700 }}>{selected.eternium[0]}-{selected.eternium[1]} Eternium</span></div>
            </div>
          </div>
          <div className="card" style={{ margin: '0 0 12px', background: 'rgba(239,68,68,0.04)', borderColor: 'rgba(239,68,68,0.2)' }}>
            <div className="card-title">👹 Jefe Final</div>
            <div style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>{selected.jefe}</div>
          </div>
          {selected.disponibles_hoy === 0 ? (
            <div style={{ textAlign: 'center', padding: '16px', color: 'var(--text-muted)', fontSize: '13px', background: 'var(--bg-card)', borderRadius: '12px' }}>
              ⏰ Has alcanzado el límite diario para mazmorras {selected.color}. Vuelve mañana.
            </div>
          ) : !selected.accesible ? (
            <div style={{ textAlign: 'center', padding: '16px', color: 'var(--text-muted)', fontSize: '13px' }}>
              🔒 Necesitas nivel {selected.nivel_req} para entrar.
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <button className="btn btn-primary btn-block" onClick={() => handleEnter(selected, true)} disabled={running}>
                {running ? '⚔️ Combatiendo...' : '⚔️ Entrar Solo'}
              </button>
              <div style={{ textAlign: 'center', fontSize: '11px', color: 'var(--text-muted)' }}>
                Para entrar en grupo, crea o únete a un grupo en la pestaña de Grupos
              </div>
            </div>
          )}
        </div>
      </div>
    )
  }

  return (
    <div>
      <div className="section-header">
        <div className="section-title">🌀 Mazmorras</div>
      </div>

      <div style={{ display: 'flex', gap: '4px', padding: '0 12px 10px' }}>
        <button className={`inv-tab ${tab === 'mazmorras' ? 'active' : ''}`} onClick={() => setTab('mazmorras')}>🌀 Mazmorras</button>
        <button className={`inv-tab ${tab === 'grupo' ? 'active' : ''}`} onClick={() => setTab('grupo')}>👥 Grupos</button>
      </div>

      {tab === 'mazmorras' && (
        loading ? (
          <div style={{ display: 'flex', justifyContent: 'center', padding: '40px' }}><div className="spinner" /></div>
        ) : (
          dungeons.map(dun => (
            <div key={dun.id} className={`dungeon-card ${!dun.accesible ? 'locked' : ''}`} onClick={() => dun.accesible && setSelected(dun)}>
              <div className="dungeon-header">
                <span className="dungeon-emoji">{dun.emoji}</span>
                <div className="dungeon-info">
                  <div className="dungeon-name">{dun.nombre}</div>
                  <div className="dungeon-desc">{dun.descripcion}</div>
                </div>
              </div>
              <div className="dungeon-body">
                <div className="dungeon-stats">
                  <div className="dungeon-stat">{COLOR_LABEL[dun.color]}</div>
                  <div className="dungeon-stat">Dificultad: <span style={{ color: DIFF_COLOR[dun.dificultad] }}>{dun.dificultad}</span></div>
                  <div className="dungeon-stat">Nv: <span>{dun.nivel_req}</span></div>
                  <div className="dungeon-stat">💎 <span>{dun.eternium[0]}-{dun.eternium[1]}</span></div>
                </div>
                <div style={{ display: 'flex', gap: '8px', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                    {dun.disponibles_hoy === 0 ? <span style={{ color: 'var(--red)' }}>Límite diario alcanzado</span> : <span style={{ color: 'var(--green)' }}>✅ {dun.disponibles_hoy} disponibles hoy</span>}
                  </div>
                  {dun.accesible && dun.disponibles_hoy > 0 ? (
                    <button className="btn btn-primary btn-sm">Entrar</button>
                  ) : !dun.accesible ? (
                    <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>🔒 Nv {dun.nivel_req}</div>
                  ) : null}
                </div>
              </div>
            </div>
          ))
        )
      )}

      {tab === 'grupo' && (
        <div style={{ padding: '0 12px 12px' }}>
          <div className="card" style={{ margin: '0 0 12px' }}>
            <div className="card-title">👥 Crear Grupo</div>
            <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '12px' }}>
              Crea un grupo y comparte tu ID con tus aliados para que se unan antes de entrar a la mazmorra.
            </div>
            <button className="btn btn-primary btn-block" onClick={handleCreateParty}>
              ➕ Crear Grupo
            </button>
            {partyId && (
              <div style={{ marginTop: '12px', textAlign: 'center', padding: '10px', background: 'rgba(34,197,94,0.08)', borderRadius: '10px', border: '1px solid rgba(34,197,94,0.2)' }}>
                <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Tu ID de grupo</div>
                <div style={{ fontFamily: 'Cinzel,serif', fontSize: '24px', color: 'var(--green)', fontWeight: 700 }}>#{partyId}</div>
                <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Comparte este número con tu equipo</div>
              </div>
            )}
          </div>

          <div className="card" style={{ margin: '0 0 12px' }}>
            <div className="card-title">🔗 Unirse a Grupo</div>
            <div style={{ display: 'flex', gap: '8px' }}>
              <input
                type="number"
                placeholder="ID del grupo"
                value={joinId}
                onChange={e => setJoinId(e.target.value)}
                style={{ flex: 1, padding: '10px', borderRadius: '8px', border: '1px solid var(--border)', background: 'var(--bg-deep)', color: 'var(--text-primary)', fontSize: '14px' }}
              />
              <button className="btn btn-primary" onClick={handleJoinParty}>Unirse</button>
            </div>
          </div>

          <div style={{ fontSize: '12px', color: 'var(--text-muted)', textAlign: 'center', lineHeight: 1.6, padding: '0 8px' }}>
            Los grupos permiten hasta 5 jugadores. Una vez formado el grupo, el líder puede iniciar la mazmorra desde la pestaña de Mazmorras.
          </div>
        </div>
      )}
    </div>
  )
}

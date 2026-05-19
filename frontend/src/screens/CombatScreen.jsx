import { useState, useEffect } from 'react'
import { api } from '../api'
import { useGameStore } from '../stores/gameStore'

export default function CombatScreen({ player, showToast, onRefresh, onExit }) {
  const { combat, inCombat, setCombat } = useGameStore()
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [logLines, setLogLines] = useState([])

  useEffect(() => {
    if (!inCombat) {
      api.getCombatStatus().then(s => {
        if (s.in_combat) setCombat(s.combat, true)
      })
    }
  }, [])

  const startCombat = async () => {
    setLoading(true)
    setResult(null)
    try {
      const res = await api.startCombat()
      setCombat(res.combat, true)
      setLogLines(res.combat?.log || [])
    } catch (e) {
      showToast(e.message, 'error')
    } finally {
      setLoading(false)
    }
  }

  const doAction = async (action, skillIndex = null) => {
    if (loading) return
    setLoading(true)
    try {
      const res = await api.combatAction(action, skillIndex)
      if (res.status === 'ongoing') {
        setCombat(res.combat, true)
        setLogLines(prev => [...(res.last_log || []), ...prev].slice(0, 10))
      } else {
        setCombat(null, false)
        setResult(res)
        setLogLines(res.log || [])
        onRefresh()
      }
    } catch (e) {
      showToast(e.message, 'error')
    } finally {
      setLoading(false)
    }
  }

  if (result) {
    const isVictory = result.status === 'victory'
    return (
      <div className="result-overlay">
        <div className="result-icon">{isVictory ? '🏆' : '💀'}</div>
        <div className={`result-title ${isVictory ? 'victory' : 'defeat'}`}>
          {isVictory ? '¡Victoria!' : 'Derrotado'}
        </div>
        {result.log && (
          <div style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '12px', maxWidth: '300px', textAlign: 'center', lineHeight: 1.5 }}>
            {result.log[result.log.length - 1]}
          </div>
        )}
        {isVictory && (
          <div className="result-rewards">
            <div className="reward-row"><span className="reward-label">⚔️ XP</span><span className="reward-value">+{result.xp_gained}</span></div>
            <div className="reward-row"><span className="reward-label">🪙 Oro</span><span className="reward-value">+{result.oro_gained}</span></div>
            {result.drops?.length > 0 && <div className="reward-row"><span className="reward-label">📦 Drops</span><span className="reward-value" style={{ fontSize: '11px' }}>{result.drops.join(', ')}</span></div>}
            {result.level_up && <div className="reward-row" style={{ borderTop: '1px solid var(--border)', paddingTop: '8px', marginTop: '4px' }}><span className="reward-label">🎉 Nivel</span><span className="reward-value" style={{ color: 'var(--purple-light)' }}>¡SUBISTE AL {result.nivel_nuevo}!</span></div>}
          </div>
        )}
        {!isVictory && result.message && (
          <div style={{ fontSize: '12px', color: 'var(--text-muted)', margin: '12px', maxWidth: '280px', textAlign: 'center' }}>{result.message}</div>
        )}
        <div style={{ display: 'flex', gap: '8px', marginTop: '8px' }}>
          <button className="btn btn-primary" onClick={() => { setResult(null); startCombat() }}>⚔️ Combatir de nuevo</button>
          <button className="btn btn-ghost" onClick={onExit}>← Volver</button>
        </div>
      </div>
    )
  }

  if (!inCombat || !combat) {
    return (
      <div className="combat-arena" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '70vh', textAlign: 'center' }}>
        <div style={{ fontSize: '72px', marginBottom: '16px', filter: 'drop-shadow(0 0 20px rgba(239,68,68,0.4))' }}>⚔️</div>
        <div style={{ fontFamily: 'Cinzel,serif', fontSize: '20px', fontWeight: 700, color: 'var(--text-gold)', marginBottom: '8px' }}>
          Listo para la Batalla
        </div>
        <div style={{ fontSize: '13px', color: 'var(--text-muted)', marginBottom: '24px', maxWidth: '240px', lineHeight: 1.5 }}>
          Busca un monstruo en {player?.zona_actual || 'la zona'}. Ten pociones a mano.
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', width: '100%', maxWidth: '260px' }}>
          <button className="btn btn-red btn-block" onClick={startCombat} disabled={loading}>
            {loading ? '🔍 Buscando...' : '⚔️ Buscar Combate'}
          </button>
          <button className="btn btn-ghost btn-block btn-sm" onClick={onExit}>← Volver</button>
        </div>
      </div>
    )
  }

  const { player: cPlayer, monster, cooldowns, habilidades, turno } = combat

  const hpMonsterPct = Math.max(0, Math.round((monster.hp / monster.hp_max) * 100))
  const hpPlayerPct = Math.max(0, Math.round((cPlayer.hp / cPlayer.hp_max) * 100))

  return (
    <div className="combat-arena">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
        <div style={{ fontFamily: 'Cinzel,serif', fontSize: '13px', color: 'var(--text-muted)' }}>Turno {turno}</div>
        {monster.is_miniboss && <div className="badge badge-roja">⭐ MINI-BOSS</div>}
      </div>

      {/* Monster */}
      <div className="combatant-card" style={{ borderColor: 'rgba(239,68,68,0.3)', background: 'rgba(239,68,68,0.03)' }}>
        <div className="combatant-emoji">{monster.emoji}</div>
        <div className="combatant-name">{monster.nombre}</div>
        {monster.lore && <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '8px', fontStyle: 'italic' }}>{monster.lore}</div>}
        <div className="hp-bar-container">
          <div className="hp-label"><span>❤️ HP</span><span>{monster.hp} / {monster.hp_max}</span></div>
          <div className="hp-bar-track"><div className="hp-bar-fill" style={{ width: `${hpMonsterPct}%` }} /></div>
        </div>
        <div style={{ display: 'flex', gap: '12px', marginTop: '8px', fontSize: '11px', color: 'var(--text-muted)', fontFamily: 'sans-serif' }}>
          <span>⚔️ ATK: {monster.atk}</span><span>🛡️ DEF: {monster.def}</span>
          <span style={{ color: 'var(--gold)' }}>+{monster.xp} XP</span>
          <span style={{ color: 'var(--gold)' }}>+{monster.oro} 🪙</span>
        </div>
      </div>

      {/* Player */}
      <div className="combatant-card" style={{ borderColor: 'rgba(34,197,94,0.3)', background: 'rgba(34,197,94,0.03)' }}>
        <div className="combatant-name">{cPlayer.nombre} <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Nv {cPlayer.nivel}</span></div>
        <div className="hp-bar-container">
          <div className="hp-label"><span>❤️ HP</span><span>{cPlayer.hp} / {cPlayer.hp_max}</span></div>
          <div className="hp-bar-track"><div className="hp-bar-fill player" style={{ width: `${hpPlayerPct}%` }} /></div>
        </div>
        <div style={{ display: 'flex', gap: '12px', marginTop: '6px', fontSize: '11px', color: 'var(--text-muted)', fontFamily: 'sans-serif' }}>
          <span>⚔️ {cPlayer.atk}</span><span>🛡️ {cPlayer.def}</span>
        </div>
      </div>

      {/* Log */}
      {logLines.length > 0 && (
        <div className="combat-log">
          {logLines.map((line, i) => <div key={i} className="log-entry">{line}</div>)}
        </div>
      )}

      {/* Actions */}
      <div className="combat-actions">
        <button className="btn btn-red" onClick={() => doAction('attack')} disabled={loading}>
          ⚔️ Atacar
        </button>
        <button className="btn btn-ghost" onClick={() => doAction('item')} disabled={loading}>
          🧪 Usar Poción
        </button>
        {(habilidades || []).map((hab, i) => {
          const cd = cooldowns?.[String(i)] || 0
          return (
            <button key={i} className={`skill-btn ${cd > 0 ? 'on-cooldown' : ''}`}
              onClick={() => cd === 0 && doAction('skill', i)} disabled={loading || cd > 0}>
              <div className="skill-name">{hab.emoji} {hab.nombre}</div>
              <div className="skill-cd">{cd > 0 ? `CD: ${cd}t` : hab.descripcion?.substring(0, 40) + '...'}</div>
            </button>
          )
        })}
        <button className="btn btn-ghost btn-sm" onClick={() => doAction('flee')} disabled={loading}>
          🏃 Huir
        </button>
      </div>
    </div>
  )
}

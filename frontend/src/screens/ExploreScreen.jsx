import { useState } from 'react'
import { api } from '../api'
import CombatScreen from './CombatScreen'

const ZONE_EMOJI = { azul: '🔵', amarilla: '🟡', roja: '🔴', negra: '⚫' }

export default function ExploreScreen({ player, onNavigate, showToast, onRefresh }) {
  const [mode, setMode] = useState('menu')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)

  if (!player) return null

  const zona = player.zona_actual || ''
  const ubicacion = player.ubicacion

  if (ubicacion !== 'salvaje') {
    return (
      <div style={{ padding: '40px 20px', textAlign: 'center' }}>
        <div style={{ fontSize: '64px', marginBottom: '16px' }}>🏙️</div>
        <div style={{ fontFamily: 'Cinzel,serif', fontSize: '16px', color: 'var(--text-gold)', marginBottom: '10px' }}>
          Estás en una Ciudad
        </div>
        <div style={{ fontSize: '13px', color: 'var(--text-muted)', marginBottom: '20px', maxWidth: '260px', margin: '0 auto 20px' }}>
          Para explorar y combatir debes viajar a una zona salvaje primero.
        </div>
        <button className="btn btn-primary" onClick={() => onNavigate('map')}>
          🗺️ Ver el Mapa
        </button>
      </div>
    )
  }

  if (mode === 'combat') {
    return (
      <CombatScreen
        player={player}
        showToast={showToast}
        onRefresh={onRefresh}
        onExit={() => { setMode('menu'); onRefresh() }}
      />
    )
  }

  if (result) {
    return (
      <div style={{ padding: '20px' }}>
        <div className="card" style={{ margin: 0 }}>
          <div className="card-title">⛏️ Resultado de Recolección</div>
          <div style={{ fontSize: '14px', color: 'var(--text-secondary)', marginBottom: '12px', lineHeight: 1.5 }}>
            {result.message}
          </div>
          {result.materiales && result.materiales.length > 0 && (
            <div style={{ marginBottom: '12px' }}>
              {result.materiales.map((m, i) => (
                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '6px 0', borderBottom: '1px solid var(--border)' }}>
                  <span>🪨</span>
                  <span style={{ fontSize: '13px', color: 'var(--text-primary)' }}>{m}</span>
                </div>
              ))}
            </div>
          )}
          <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
            +{result.xp_gained} XP · ⚡ -{result.stamina_gastada} Stamina
          </div>
        </div>
        <button className="btn btn-primary btn-block" style={{ marginTop: '12px' }} onClick={() => { setResult(null); onRefresh() }}>
          Continuar
        </button>
      </div>
    )
  }

  const handleCollect = async () => {
    setLoading(true)
    try {
      const res = await api.collectResources()
      setResult(res)
      onRefresh()
    } catch (e) {
      showToast(e.message, 'error')
    } finally {
      setLoading(false)
    }
  }

  const zonaDanger = {
    azul: { label: 'Segura', desc: 'Zona de entrenamiento. PvP desactivado.', pvp: false },
    amarilla: { label: '⚠️ Zona de Peligro', desc: 'PvP posible. Perderás oro si mueres.', pvp: true },
    roja: { label: '🔴 Zona Peligrosa', desc: 'Alto riesgo. Perderás 50% del oro.', pvp: true },
    negra: { label: '⚫ Zona Extrema', desc: 'Máximo peligro. Todo se pierde al morir.', pvp: true },
  }

  const getZoneColor = () => {
    const ZONAS_COLOR = [
      'Bosque Alianza', 'Bosque Imperio', 'Cavernas Sindicato', 'Llanuras Centrales', 'Costa Brumosa', 'Desierto Ardiente',
    ]
    if (zona.toLowerCase().includes('bosque') || zona.toLowerCase().includes('llanura') || zona.toLowerCase().includes('costa') || zona.toLowerCase().includes('desierto') || zona.toLowerCase().includes('caverna')) return 'azul'
    if (zona.toLowerCase().includes('montaña') || zona.toLowerCase().includes('pantano') || zona.toLowerCase().includes('ruinas') || zona.toLowerCase().includes('valle') || zona.toLowerCase().includes('estep') || zona.toLowerCase().includes('aldea')) return 'amarilla'
    if (zona.toLowerCase().includes('fortaleza') || zona.toLowerCase().includes('corrompid') || zona.toLowerCase().includes('torre') || zona.toLowerCase().includes('ceniza') || zona.toLowerCase().includes('santuario') || zona.toLowerCase().includes('laberinto')) return 'roja'
    return 'negra'
  }

  const colorInfo = zonaDanger[player.zona_color || getZoneColor()] || zonaDanger.azul

  return (
    <div>
      <div className="section-header">
        <div className="section-title">⚔️ Explorar</div>
        <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Stamina: {player.stamina_actual}/{player.stamina_max}</div>
      </div>

      <div style={{ padding: '0 12px 12px' }}>
        <div style={{ background: 'rgba(0,0,0,0.3)', border: '1px solid var(--border)', borderRadius: '12px', padding: '12px 14px', marginBottom: '12px' }}>
          <div style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '4px' }}>
            📍 {zona} — <span style={{ color: colorInfo.pvp ? 'var(--zone-roja)' : 'var(--zone-azul)' }}>{colorInfo.label}</span>
          </div>
          <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>{colorInfo.desc}</div>
        </div>
      </div>

      <div className="explore-actions">
        <button className="explore-btn" onClick={() => setMode('combat')}>
          <span className="ex-icon">⚔️</span>
          <div className="ex-name">Combatir</div>
          <div className="ex-desc">Busca monstruos y derrótados. -5 Stamina</div>
        </button>
        <button className="explore-btn" onClick={handleCollect} disabled={loading}>
          <span className="ex-icon">⛏️</span>
          <div className="ex-name">{loading ? 'Recolectando...' : 'Recolectar'}</div>
          <div className="ex-desc">Recoge materiales del entorno. -5 Stamina</div>
        </button>
      </div>

      <div style={{ padding: '0 12px 12px' }}>
        <div className="card" style={{ margin: 0 }}>
          <div className="card-title">👥 Jugadores en la Zona</div>
          <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
            Hay otros aventureros en {zona}. El combate PvP puede activarse en zonas no seguras.
          </div>
        </div>
      </div>

      <div style={{ padding: '0 12px 12px' }}>
        <button className="btn btn-ghost btn-block" onClick={() => onNavigate('dungeon')}>
          🌀 Acceder a Mazmorras (Grupo)
        </button>
      </div>
    </div>
  )
}

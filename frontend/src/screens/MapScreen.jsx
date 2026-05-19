import { useState, useEffect } from 'react'
import { api } from '../api'

const COLOR_HEX = {
  azul: '#3b82f6', amarilla: '#f59e0b', roja: '#ef4444', negra: '#6b7280'
}
const COLOR_LABEL = {
  azul: '🔵 Azul', amarilla: '🟡 Amarilla', roja: '🔴 Roja', negra: '⚫ Negra'
}
const FACCION_NAMES = { 1: 'Alianza', 2: 'Imperio', 3: 'Sindicato' }
const FACCION_EMOJI = { 1: '⚔️', 2: '🦅', 3: '🕵️' }

function ZoneDetailPanel({ zone, player, onClose, onTravel }) {
  const [loading, setLoading] = useState(false)

  const isCurrent = zone.es_ubicacion_actual
  const canAccess = zone.accesible
  const isCity = zone.tipo === 'ciudad'

  const handleTravel = async (fast = false) => {
    setLoading(true)
    try {
      await onTravel(zone.id, fast)
      onClose()
    } catch (e) {
      alert(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="item-modal" onClick={onClose}>
      <div className="item-modal-content" onClick={e => e.stopPropagation()}>
        <div className="modal-handle" />
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '16px' }}>
          <span style={{ fontSize: '42px' }}>{zone.icono}</span>
          <div>
            <div style={{ fontFamily: 'Cinzel,serif', fontSize: '16px', fontWeight: 700, color: 'var(--text-gold)', marginBottom: '4px' }}>
              {zone.nombre}
            </div>
            <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
              <span className={`badge badge-${zone.color}`}>{COLOR_LABEL[zone.color]}</span>
              {zone.pvp ? <span className="badge badge-pvp">⚔️ PvP</span> : <span className="badge badge-safe">✅ Safe</span>}
            </div>
          </div>
        </div>

        <div style={{ background: 'rgba(0,0,0,0.2)', borderRadius: '10px', padding: '12px', marginBottom: '14px', fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
          {zone.descripcion_peligro}
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', marginBottom: '16px', fontSize: '12px' }}>
          <div style={{ color: 'var(--text-muted)' }}>Facción: <span style={{ color: 'var(--text-primary)' }}>{FACCION_EMOJI[zone.faccion_id]} {FACCION_NAMES[zone.faccion_id]}</span></div>
          <div style={{ color: 'var(--text-muted)' }}>Nivel mín: <span style={{ color: 'var(--text-gold)' }}>{zone.nivel_requerido}</span></div>
          <div style={{ color: 'var(--text-muted)' }}>Jugadores: <span style={{ color: 'var(--text-primary)' }}>{zone.jugadores_aqui}</span></div>
          <div style={{ color: 'var(--text-muted)' }}>Tipo: <span style={{ color: 'var(--text-primary)' }}>{isCity ? '🏙️ Ciudad' : '🌿 Zona Salvaje'}</span></div>
        </div>

        {isCurrent ? (
          <button className="btn btn-ghost btn-block" onClick={onClose}>✅ Estás aquí ahora</button>
        ) : !canAccess ? (
          <div style={{ textAlign: 'center', color: 'var(--text-muted)', fontSize: '13px', padding: '12px' }}>
            🔒 Necesitas nivel {zone.nivel_requerido} para acceder
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <button className="btn btn-primary btn-block" onClick={() => handleTravel(false)} disabled={loading}>
              {loading ? '...' : '🗺️ Viajar aquí'}
            </button>
            <button className="btn btn-gold btn-block btn-sm" onClick={() => handleTravel(true)} disabled={loading}>
              ✈️ Viaje rápido (30 💎)
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

export default function MapScreen({ player, onNavigate, showToast, onRefresh }) {
  const [zones, setZones] = useState([])
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState(null)
  const [viewMode, setViewMode] = useState('visual')
  const [filterColor, setFilterColor] = useState('all')
  const [filterFaction, setFilterFaction] = useState('all')

  useEffect(() => {
    api.getZones().then(d => { setZones(d.zones || []); setLoading(false) }).catch(() => setLoading(false))
  }, [])

  const handleTravel = async (zoneId, fast) => {
    const result = await api.startTravel(zoneId, fast)
    await onRefresh()
    showToast(result.message, 'success')
  }

  const filtered = zones.filter(z => {
    if (filterColor !== 'all' && z.color !== filterColor) return false
    if (filterFaction !== 'all' && z.faccion_id !== parseInt(filterFaction)) return false
    return true
  })

  const citiesForSVG = zones.filter(z => z.tipo === 'ciudad')
  const wildForSVG = zones.filter(z => z.tipo === 'salvaje')

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '60px' }}>
        <div className="spinner" />
      </div>
    )
  }

  return (
    <div>
      <div className="section-header">
        <div className="section-title">🗺️ Mapa de Aethelgard</div>
        <div style={{ display: 'flex', gap: '6px' }}>
          <button className={`btn btn-sm ${viewMode === 'visual' ? 'btn-primary' : 'btn-ghost'}`} onClick={() => setViewMode('visual')}>🗺️</button>
          <button className={`btn btn-sm ${viewMode === 'list' ? 'btn-primary' : 'btn-ghost'}`} onClick={() => setViewMode('list')}>☰</button>
        </div>
      </div>

      {viewMode === 'visual' && (
        <div className="map-wrapper">
          <div className="map-svg-container">
            <svg className="map-svg" viewBox="0 0 660 450" xmlns="http://www.w3.org/2000/svg">
              <defs>
                <radialGradient id="glow-azul" cx="50%" cy="50%" r="50%">
                  <stop offset="0%" stopColor="#3b82f6" stopOpacity="0.4" />
                  <stop offset="100%" stopColor="#3b82f6" stopOpacity="0" />
                </radialGradient>
                <radialGradient id="glow-amarilla" cx="50%" cy="50%" r="50%">
                  <stop offset="0%" stopColor="#f59e0b" stopOpacity="0.3" />
                  <stop offset="100%" stopColor="#f59e0b" stopOpacity="0" />
                </radialGradient>
                <radialGradient id="glow-roja" cx="50%" cy="50%" r="50%">
                  <stop offset="0%" stopColor="#ef4444" stopOpacity="0.3" />
                  <stop offset="100%" stopColor="#ef4444" stopOpacity="0" />
                </radialGradient>
                <radialGradient id="glow-negra" cx="50%" cy="50%" r="50%">
                  <stop offset="0%" stopColor="#7c3aed" stopOpacity="0.25" />
                  <stop offset="100%" stopColor="#7c3aed" stopOpacity="0" />
                </radialGradient>
              </defs>

              <rect width="660" height="450" fill="url(#map-bg)" />
              <image href="data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNjYwIiBoZWlnaHQ9IjQ1MCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iNjYwIiBoZWlnaHQ9IjQ1MCIgZmlsbD0iIzA3MDcxMiIvPjwvc3ZnPg==" width="660" height="450" />

              {/* Grid lines */}
              {[0,1,2,3,4,5].map(i => (
                <line key={`v${i}`} x1={i*110} y1="0" x2={i*110} y2="450" stroke="rgba(120,100,255,0.04)" strokeWidth="1" />
              ))}
              {[0,1,2,3,4].map(i => (
                <line key={`h${i}`} x1="0" y1={i*90} x2="660" y2={i*90} stroke="rgba(120,100,255,0.04)" strokeWidth="1" />
              ))}

              {/* Zone connections (faint lines) */}
              {wildForSVG.map(z => {
                const cx = (z.coord_x / 660) * 660
                const cy = (z.coord_y / 450) * 450
                const closest = wildForSVG.filter(o => o.faccion_id === z.faccion_id && o.id !== z.id)
                  .sort((a, b) => Math.hypot(a.coord_x - z.coord_x, a.coord_y - z.coord_y) - Math.hypot(b.coord_x - z.coord_x, b.coord_y - z.coord_y))
                  .slice(0, 2)
                return closest.map(o => {
                  const ox = (o.coord_x / 660) * 660
                  const oy = (o.coord_y / 450) * 450
                  return (
                    <line key={`${z.id}-${o.id}`} x1={cx} y1={cy} x2={ox} y2={oy}
                      stroke={COLOR_HEX[z.color]} strokeOpacity="0.12" strokeWidth="1" strokeDasharray="3,4" />
                  )
                })
              })}

              {/* Wild zones */}
              {wildForSVG.map(zone => {
                const cx = (zone.coord_x / 660) * 660
                const cy = (zone.coord_y / 450) * 450
                const isCurrent = zone.es_ubicacion_actual
                const locked = !zone.accesible
                const r = 9
                return (
                  <g key={zone.id} className={`zone-node ${isCurrent ? 'current' : ''} ${locked ? 'locked' : ''}`}
                    onClick={() => !locked && setSelected(zone)} style={{ cursor: locked ? 'not-allowed' : 'pointer' }}>
                    {isCurrent && <circle cx={cx} cy={cy} r={r + 8} fill={`url(#glow-${zone.color})`} />}
                    <circle cx={cx} cy={cy} r={r} fill={locked ? '#1e1e40' : COLOR_HEX[zone.color]} fillOpacity={locked ? 0.3 : 0.25} className="zone-circle"
                      stroke={isCurrent ? 'white' : COLOR_HEX[zone.color]} strokeWidth={isCurrent ? 2 : 1} strokeOpacity={locked ? 0.3 : 0.7} />
                    <text x={cx} y={cy + 1} textAnchor="middle" dominantBaseline="middle" fontSize={isCurrent ? "11" : "9"}>
                      {locked ? '🔒' : zone.icono}
                    </text>
                  </g>
                )
              })}

              {/* Cities — larger */}
              {citiesForSVG.map(zone => {
                const cx = (zone.coord_x / 660) * 660
                const cy = (zone.coord_y / 450) * 450
                const isCurrent = zone.es_ubicacion_actual
                return (
                  <g key={zone.id} className={`zone-node ${isCurrent ? 'current' : ''}`}
                    onClick={() => setSelected(zone)} style={{ cursor: 'pointer' }}>
                    {isCurrent && <circle cx={cx} cy={cy} r={22} fill="rgba(212,175,55,0.15)" />}
                    <circle cx={cx} cy={cy} r={16} fill="rgba(212,175,55,0.1)" className="zone-circle"
                      stroke={isCurrent ? '#d4af37' : 'rgba(212,175,55,0.5)'} strokeWidth={isCurrent ? 2 : 1} />
                    <text x={cx} y={cy} textAnchor="middle" dominantBaseline="middle" fontSize="14">🏙️</text>
                    <text className="zone-label" x={cx} y={cy + 24} fontSize="7.5" fill={isCurrent ? '#d4af37' : 'rgba(255,255,255,0.7)'}>
                      {zone.nombre.replace('Ciudadela ', '')}
                    </text>
                    {isCurrent && (
                      <circle cx={cx + 14} cy={cy - 14} r={5} fill="#22c55e" stroke="#0d0d1a" strokeWidth={1.5} />
                    )}
                  </g>
                )
              })}
            </svg>
          </div>

          <div className="map-legend">
            <div className="legend-item"><div className="legend-dot" style={{ background: '#3b82f6' }} />Zona Azul (Segura)</div>
            <div className="legend-item"><div className="legend-dot" style={{ background: '#f59e0b' }} />Zona Amarilla (PvP)</div>
            <div className="legend-item"><div className="legend-dot" style={{ background: '#ef4444' }} />Zona Roja</div>
            <div className="legend-item"><div className="legend-dot" style={{ background: '#6b7280' }} />Zona Negra</div>
          </div>
        </div>
      )}

      {viewMode === 'list' && (
        <>
          <div style={{ display: 'flex', gap: '6px', padding: '0 12px 10px', overflowX: 'auto' }}>
            {['all', 'azul', 'amarilla', 'roja', 'negra'].map(c => (
              <button key={c} className={`inv-tab ${filterColor === c ? 'active' : ''}`} onClick={() => setFilterColor(c)}>
                {c === 'all' ? 'Todas' : COLOR_LABEL[c]}
              </button>
            ))}
          </div>
          <div className="zone-list">
            {filtered.map(zone => (
              <div key={zone.id} className={`zone-list-item ${zone.es_ubicacion_actual ? 'current-zone' : ''} ${!zone.accesible ? 'locked' : ''}`}
                onClick={() => zone.accesible && setSelected(zone)}>
                <span className="zone-icon">{zone.accesible ? zone.icono : '🔒'}</span>
                <div className="zone-info">
                  <div className="zone-name">{zone.nombre}</div>
                  <div className="zone-meta">
                    <span className={`badge badge-${zone.color}`}>{zone.color}</span>
                    {zone.pvp && <span className="badge badge-pvp">PvP</span>}
                    {zone.jugadores_aqui > 0 && <span>👤 {zone.jugadores_aqui}</span>}
                  </div>
                </div>
                <div className="zone-right">
                  {zone.es_ubicacion_actual && <span style={{ color: '#22c55e', fontSize: '11px', fontWeight: 700 }}>📍 Aquí</span>}
                  {!zone.accesible && <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>Nv {zone.nivel_requerido}</span>}
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {selected && (
        <ZoneDetailPanel
          zone={selected}
          player={player}
          onClose={() => setSelected(null)}
          onTravel={handleTravel}
        />
      )}
    </div>
  )
}

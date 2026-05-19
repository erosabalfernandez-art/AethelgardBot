import { useState, useEffect } from 'react'
import { api } from '../api'

const TIPO_EMOJI = { arma: '⚔️', weapon: '⚔️', armadura: '🛡️', armor: '🛡️', pocion: '🧪', potion: '🧪', material: '🪨', misc: '📦' }
const TIPO_LABEL = { arma: 'Arma', weapon: 'Arma', armadura: 'Armadura', armor: 'Armadura', pocion: 'Poción', potion: 'Poción', material: 'Material', misc: 'Misc' }

function ItemModal({ item, onClose, onUse, onSell, loading }) {
  return (
    <div className="item-modal" onClick={onClose}>
      <div className="item-modal-content" onClick={e => e.stopPropagation()}>
        <div className="modal-handle" />
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px', marginBottom: '16px' }}>
          <span style={{ fontSize: '44px' }}>{item.emoji || TIPO_EMOJI[item.tipo] || '📦'}</span>
          <div>
            <div style={{ fontFamily: 'Cinzel,serif', fontSize: '16px', fontWeight: 700, color: item.rareza_color || 'var(--text-primary)', marginBottom: '4px' }}>{item.nombre}</div>
            <div style={{ display: 'flex', gap: '6px' }}>
              <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontFamily: 'sans-serif' }}>{TIPO_LABEL[item.tipo] || item.tipo}</span>
              {item.rareza_nombre && <span style={{ fontSize: '11px', color: item.rareza_color || 'var(--text-muted)', fontFamily: 'sans-serif', fontWeight: 700 }}>· {item.rareza_nombre}</span>}
            </div>
          </div>
        </div>

        {item.descripcion && (
          <div style={{ background: 'rgba(0,0,0,0.2)', borderRadius: '10px', padding: '12px', marginBottom: '14px', fontSize: '13px', color: 'var(--text-secondary)', fontStyle: 'italic', lineHeight: 1.5 }}>
            {item.descripcion}
          </div>
        )}

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', marginBottom: '16px', fontSize: '12px' }}>
          {item.daño && <div style={{ color: 'var(--text-muted)' }}>⚔️ Daño: <span style={{ color: 'var(--red)', fontWeight: 700 }}>{item.daño}</span></div>}
          {item.defensa && <div style={{ color: 'var(--text-muted)' }}>🛡️ Defensa: <span style={{ color: 'var(--blue)', fontWeight: 700 }}>{item.defensa}</span></div>}
          {item.critico && <div style={{ color: 'var(--text-muted)' }}>💥 Crítico: <span style={{ color: 'var(--orange)', fontWeight: 700 }}>{item.critico}%</span></div>}
          {item.nivel_requerido && <div style={{ color: 'var(--text-muted)' }}>Nv. req: <span style={{ color: 'var(--text-primary)', fontWeight: 700 }}>{item.nivel_requerido}</span></div>}
          {item.valor && <div style={{ color: 'var(--text-muted)' }}>Efecto: <span style={{ color: 'var(--green)', fontWeight: 700 }}>+{item.valor}</span></div>}
          {item.cantidad > 1 && <div style={{ color: 'var(--text-muted)' }}>Cantidad: <span style={{ color: 'var(--gold)', fontWeight: 700 }}>{item.cantidad}</span></div>}
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {(item.efecto || item.tipo === 'pocion' || item.tipo === 'potion') && (
            <button className="btn btn-green btn-block" onClick={() => onUse(item)} disabled={loading}>
              {loading ? '...' : '✅ Usar'}
            </button>
          )}
          <button className="btn btn-ghost btn-block btn-sm" onClick={() => onSell(item)} disabled={loading}>
            💰 Vender ({item.precio_venta_oro || Math.max(1, Math.round((item.precio_oro || 10) * 0.5))} 🪙)
          </button>
          <button className="btn btn-ghost btn-block btn-sm" onClick={onClose}>Cerrar</button>
        </div>
      </div>
    </div>
  )
}

export default function InventoryScreen({ player, showToast, onRefresh }) {
  const [inv, setInv] = useState({ armas: [], armaduras: [], pociones: [], materiales: [], misc: [] })
  const [tab, setTab] = useState('pociones')
  const [selected, setSelected] = useState(null)
  const [loading, setLoading] = useState(true)
  const [actionLoading, setActionLoading] = useState(false)

  const loadInv = async () => {
    try {
      const data = await api.getInventory()
      setInv(data)
    } catch (e) { }
    setLoading(false)
  }

  useEffect(() => { loadInv() }, [])

  const handleUse = async (item) => {
    setActionLoading(true)
    try {
      const res = await api.useItem(item.nombre)
      showToast(res.message, 'success')
      setSelected(null)
      await loadInv()
      onRefresh()
    } catch (e) { showToast(e.message, 'error') }
    setActionLoading(false)
  }

  const handleSell = async (item) => {
    setActionLoading(true)
    try {
      const res = await api.sellItem(item.nombre)
      showToast(res.message, 'success')
      setSelected(null)
      await loadInv()
      onRefresh()
    } catch (e) { showToast(e.message, 'error') }
    setActionLoading(false)
  }

  const TABS = [
    { id: 'pociones', label: '🧪 Pociones', items: [...inv.pociones] },
    { id: 'armas', label: '⚔️ Armas', items: [...inv.armas] },
    { id: 'armaduras', label: '🛡️ Armaduras', items: [...inv.armaduras] },
    { id: 'materiales', label: '🪨 Materiales', items: [...inv.materiales] },
    { id: 'misc', label: '📦 Otros', items: [...inv.misc] },
  ]

  const currentTab = TABS.find(t => t.id === tab) || TABS[0]
  const currentItems = currentTab.items

  return (
    <div>
      <div className="section-header">
        <div className="section-title">🎒 Inventario</div>
        <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
          {inv.armas.length + inv.armaduras.length + inv.pociones.length + inv.materiales.length + inv.misc.length} items
        </div>
      </div>

      <div className="inv-tabs">
        {TABS.map(t => (
          <button key={t.id} className={`inv-tab ${tab === t.id ? 'active' : ''}`} onClick={() => setTab(t.id)}>
            {t.label} {t.items.length > 0 && <span style={{ opacity: 0.7 }}>({t.items.length})</span>}
          </button>
        ))}
      </div>

      {loading ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: '40px' }}><div className="spinner" /></div>
      ) : currentItems.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">{TIPO_EMOJI[tab] || '📦'}</div>
          No tienes {currentTab.label.toLowerCase()} en tu inventario
        </div>
      ) : (
        <div className="item-grid">
          {currentItems.map((item, i) => (
            <div key={i} className="item-card" onClick={() => setSelected(item)} style={{ borderColor: item.rareza_color ? `${item.rareza_color}30` : undefined }}>
              <div className="item-emoji">{item.emoji || TIPO_EMOJI[item.tipo] || '📦'}</div>
              <div className="item-name">{item.nombre}</div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div className="item-type">{TIPO_LABEL[item.tipo] || item.tipo}</div>
                {item.cantidad > 1 && <div className="item-qty">x{item.cantidad}</div>}
              </div>
              {item.rareza_nombre && (
                <div style={{ fontSize: '9px', color: item.rareza_color || 'var(--text-muted)', fontWeight: 700, marginTop: '4px', fontFamily: 'sans-serif' }}>
                  {item.rareza_nombre}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {selected && (
        <ItemModal
          item={selected}
          onClose={() => setSelected(null)}
          onUse={handleUse}
          onSell={handleSell}
          loading={actionLoading}
        />
      )}
    </div>
  )
}

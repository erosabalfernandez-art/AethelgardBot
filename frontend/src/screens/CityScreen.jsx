import { useState, useEffect } from 'react'
import { api } from '../api'

function ShopView({ player, showToast, onRefresh, onBack }) {
  const [shop, setShop] = useState(null)
  const [loading, setLoading] = useState(true)
  const [buying, setBuying] = useState(null)

  useEffect(() => { api.getShop().then(setShop).finally(() => setLoading(false)) }, [])

  const handleBuy = async (item) => {
    setBuying(item.id)
    try {
      const res = await api.buyItem(item.id)
      showToast(res.message, 'success')
      onRefresh()
      const updated = await api.getShop()
      setShop(updated)
    } catch (e) { showToast(e.message, 'error') }
    setBuying(null)
  }

  if (loading) return <div style={{ display: 'flex', justifyContent: 'center', padding: '40px' }}><div className="spinner" /></div>

  return (
    <div>
      <div className="section-header">
        <button className="btn btn-ghost btn-sm" onClick={onBack}>← Volver</button>
        <div className="section-title">🛒 Tienda</div>
        <div style={{ fontSize: '12px', color: 'var(--gold)' }}>🪙 {(shop?.oro_jugador || 0).toLocaleString()}</div>
      </div>
      {(shop?.items || []).map(item => (
        <div key={item.id} style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '12px', margin: '0 12px 10px', padding: '14px', display: 'flex', gap: '12px', alignItems: 'center' }}>
          <span style={{ fontSize: '32px' }}>{item.emoji}</span>
          <div style={{ flex: 1 }}>
            <div style={{ fontFamily: 'Cinzel,serif', fontSize: '14px', fontWeight: 700, color: 'var(--text-gold)', marginBottom: '3px' }}>{item.nombre}</div>
            <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '4px' }}>{item.descripcion}</div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Nv. req: {item.nivel_req}</div>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '6px' }}>
            <div style={{ color: 'var(--gold)', fontWeight: 700, fontSize: '14px' }}>🪙 {item.precio_oro}</div>
            <button className="btn btn-gold btn-sm" onClick={() => handleBuy(item)} disabled={buying === item.id || (shop?.oro_jugador || 0) < item.precio_oro}>
              {buying === item.id ? '...' : 'Comprar'}
            </button>
          </div>
        </div>
      ))}
    </div>
  )
}

function BankView({ showToast, onRefresh, onBack }) {
  const [bank, setBank] = useState(null)
  const [loading, setLoading] = useState(true)
  const [monto, setMonto] = useState('')
  const [working, setWorking] = useState(false)

  useEffect(() => { api.getBank().then(setBank).finally(() => setLoading(false)) }, [])

  const handleExchange = async (a, de) => {
    if (!monto || parseInt(monto) <= 0) return showToast('Ingresa una cantidad válida', 'error')
    setWorking(true)
    try {
      const res = await api.bankExchange('cambiar', parseInt(monto), de, a)
      showToast(res.message, 'success')
      const updated = await api.getBank()
      setBank(updated)
      setMonto('')
      onRefresh()
    } catch (e) { showToast(e.message, 'error') }
    setWorking(false)
  }

  if (loading) return <div style={{ display: 'flex', justifyContent: 'center', padding: '40px' }}><div className="spinner" /></div>

  return (
    <div>
      <div className="section-header">
        <button className="btn btn-ghost btn-sm" onClick={onBack}>← Volver</button>
        <div className="section-title">🏦 Banco</div>
      </div>
      <div style={{ padding: '0 12px 12px' }}>
        <div className="card" style={{ margin: '0 0 12px' }}>
          <div className="card-title">💰 Tus Monedas</div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '10px', textAlign: 'center' }}>
            <div><div style={{ color: 'var(--gold)', fontFamily: 'Cinzel,serif', fontSize: '16px', fontWeight: 700 }}>{(bank?.oro || 0).toLocaleString()}</div><div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>🪙 Oro</div></div>
            <div><div style={{ color: 'var(--purple-light)', fontFamily: 'Cinzel,serif', fontSize: '16px', fontWeight: 700 }}>{bank?.eternium || 0}</div><div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>💎 Eternium</div></div>
            <div><div style={{ color: 'var(--teal)', fontFamily: 'Cinzel,serif', fontSize: '16px', fontWeight: 700 }}>{bank?.creditos || 0}</div><div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>🔮 Créditos</div></div>
          </div>
        </div>

        {(bank?.creditos || 0) > 0 && (
          <div className="card" style={{ margin: '0 0 12px' }}>
            <div className="card-title">🔄 Cambio de Créditos</div>
            <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '12px' }}>{bank?.info}</div>
            <input
              type="number"
              placeholder="Cantidad de créditos"
              value={monto}
              onChange={e => setMonto(e.target.value)}
              style={{ width: '100%', padding: '10px', borderRadius: '8px', border: '1px solid var(--border)', background: 'var(--bg-deep)', color: 'var(--text-primary)', fontSize: '14px', marginBottom: '10px' }}
            />
            <div style={{ display: 'flex', gap: '8px' }}>
              <button className="btn btn-primary btn-block btn-sm" onClick={() => handleExchange('eternium', 'creditos')} disabled={working}>→ Eternium</button>
              <button className="btn btn-gold btn-block btn-sm" onClick={() => handleExchange('oro', 'creditos')} disabled={working}>→ Oro</button>
            </div>
          </div>
        )}

        <div style={{ background: 'rgba(212,175,55,0.06)', border: '1px solid var(--border-gold)', borderRadius: '12px', padding: '14px', fontSize: '12px', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
          💡 Los Créditos del Vacío son la moneda premium del juego. Se obtienen completando eventos especiales, logros y retos del bot.
        </div>
      </div>
    </div>
  )
}

function TavernView({ player, showToast, onRefresh, onBack }) {
  const [loading, setLoading] = useState(false)

  const handleRest = async () => {
    setLoading(true)
    try {
      const res = await api.useTavern()
      showToast(res.message, 'success')
      onRefresh()
    } catch (e) { showToast(e.message, 'error') }
    setLoading(false)
  }

  return (
    <div>
      <div className="section-header">
        <button className="btn btn-ghost btn-sm" onClick={onBack}>← Volver</button>
        <div className="section-title">🍺 Taberna</div>
      </div>
      <div style={{ padding: '20px 12px', textAlign: 'center' }}>
        <div style={{ fontSize: '72px', marginBottom: '16px' }}>🍺</div>
        <div style={{ fontFamily: 'Cinzel,serif', fontSize: '18px', color: 'var(--text-gold)', marginBottom: '10px' }}>Taberna del Aventurero</div>
        <div style={{ fontSize: '13px', color: 'var(--text-secondary)', maxWidth: '260px', margin: '0 auto 24px', lineHeight: 1.6 }}>
          Descansa y recupera tu vitalidad. El descanso restaura toda tu vida y repone stamina. Coste: 50 🪙 Oro.
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '24px' }}>
          <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '12px', padding: '14px', textAlign: 'center' }}>
            <div style={{ color: 'var(--red)', fontFamily: 'Cinzel,serif', fontSize: '18px', fontWeight: 700 }}>{player?.hp_actual || 0}</div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>HP Actual</div>
          </div>
          <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '12px', padding: '14px', textAlign: 'center' }}>
            <div style={{ color: 'var(--orange)', fontFamily: 'Cinzel,serif', fontSize: '18px', fontWeight: 700 }}>{player?.stamina_actual || 0}</div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Stamina</div>
          </div>
        </div>

        <button className="btn btn-primary btn-block" onClick={handleRest} disabled={loading}>
          {loading ? '...' : '😴 Descansar (50 🪙)'}
        </button>
      </div>
    </div>
  )
}

const SERVICES = [
  { id: 'tienda', nombre: 'Tienda', icon: '🛒', desc: 'Compra pociones y consumibles', color: 'rgba(212,175,55,0.08)' },
  { id: 'banco', nombre: 'Banco', icon: '🏦', desc: 'Gestiona tus monedas y cambios', color: 'rgba(59,130,246,0.08)' },
  { id: 'taberna', nombre: 'Taberna', icon: '🍺', desc: 'Descansa y recupera HP', color: 'rgba(245,158,11,0.08)' },
  { id: 'herrero', nombre: 'Herrería', icon: '⚒️', desc: 'Próximamente — mejora equipamiento', color: 'rgba(107,114,128,0.08)', disabled: true },
  { id: 'mazmorra', nombre: 'Mazmorras', icon: '🌀', desc: 'Entra al calabozo en grupo', color: 'rgba(124,58,237,0.08)' },
  { id: 'gremio', nombre: 'Gremio', icon: '⚔️', desc: 'Gestiona tu gremio', color: 'rgba(239,68,68,0.08)' },
]

export default function CityScreen({ player, onNavigate, showToast, onRefresh }) {
  const [view, setView] = useState('menu')

  if (!player) return null

  if (player.ubicacion !== 'ciudad') {
    return (
      <div style={{ padding: '40px 20px', textAlign: 'center' }}>
        <div style={{ fontSize: '64px', marginBottom: '16px' }}>🌿</div>
        <div style={{ fontFamily: 'Cinzel,serif', fontSize: '16px', color: 'var(--text-gold)', marginBottom: '10px' }}>Estás en Zona Salvaje</div>
        <div style={{ fontSize: '13px', color: 'var(--text-muted)', marginBottom: '20px', maxWidth: '260px', margin: '0 auto 20px' }}>
          Los servicios de ciudad solo están disponibles dentro de una ciudadela o pueblo.
        </div>
        <button className="btn btn-primary" onClick={() => onNavigate('map')}>🗺️ Ir al Mapa</button>
      </div>
    )
  }

  if (view === 'tienda') return <ShopView player={player} showToast={showToast} onRefresh={onRefresh} onBack={() => setView('menu')} />
  if (view === 'banco') return <BankView showToast={showToast} onRefresh={onRefresh} onBack={() => setView('menu')} />
  if (view === 'taberna') return <TavernView player={player} showToast={showToast} onRefresh={onRefresh} onBack={() => setView('menu')} />
  if (view === 'mazmorra') { onNavigate('dungeon'); return null }
  if (view === 'gremio') { onNavigate('guild'); return null }

  const FACTION_BANNER = { Alianza: '⚔️', Imperio: '🦅', Sindicato: '🕵️' }

  return (
    <div>
      <div style={{ background: 'linear-gradient(180deg, rgba(212,175,55,0.08) 0%, transparent 100%)', borderBottom: '1px solid var(--border-gold)', padding: '16px', textAlign: 'center', marginBottom: '4px' }}>
        <div style={{ fontSize: '32px', marginBottom: '4px' }}>{FACTION_BANNER[player.faccion] || '🏙️'}</div>
        <div style={{ fontFamily: 'Cinzel,serif', fontSize: '15px', fontWeight: 700, color: 'var(--text-gold)' }}>{player.zona_actual}</div>
        <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{player.faccion} · Ciudad segura</div>
      </div>

      <div className="services-grid" style={{ paddingTop: '12px' }}>
        {SERVICES.map(s => (
          <div
            key={s.id}
            className="service-card"
            style={{ background: s.color, opacity: s.disabled ? 0.45 : 1, cursor: s.disabled ? 'not-allowed' : 'pointer' }}
            onClick={() => !s.disabled && setView(s.id)}
          >
            <div className="service-icon">{s.icon}</div>
            <div className="service-name">{s.nombre}</div>
            <div className="service-desc">{s.desc}</div>
          </div>
        ))}
      </div>
    </div>
  )
}

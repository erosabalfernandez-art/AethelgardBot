const TABS = [
  { id: 'map',       icon: '🗺️',  label: 'Mapa'     },
  { id: 'explore',   icon: '⚔️',  label: 'Explorar' },
  { id: 'inventory', icon: '🎒',  label: 'Mochila'  },
  { id: 'city',      icon: '🏙️',  label: 'Ciudad'   },
  { id: 'profile',   icon: '👤',  label: 'Perfil'   },
]

export default function BottomNav({ active, onChange, player, inCombat }) {
  const isInCity = player?.ubicacion === 'ciudad'
  const isInWild = player?.ubicacion === 'salvaje'

  return (
    <nav className="bottom-nav">
      {TABS.map(tab => {
        let isDisabled = false
        if (tab.id === 'city' && !isInCity) isDisabled = true
        if (tab.id === 'explore' && !isInWild) isDisabled = true

        return (
          <button
            key={tab.id}
            className={`nav-btn ${active === tab.id ? 'active' : ''}`}
            onClick={() => !isDisabled && onChange(tab.id)}
            style={{ opacity: isDisabled ? 0.35 : 1 }}
          >
            <span className="nav-icon">{tab.icon}</span>
            <span className="nav-label">{tab.label}</span>
          </button>
        )
      })}
    </nav>
  )
}

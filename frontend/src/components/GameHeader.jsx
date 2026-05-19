import { useGameStore } from '../stores/gameStore'

export default function GameHeader({ onNotif }) {
  const { player } = useGameStore()

  if (!player) return null

  const FACTION_EMOJI = { Alianza: '⚔️', Imperio: '🦅', Sindicato: '🕵️' }
  const fEmoji = FACTION_EMOJI[player.faccion] || '⚔️'

  return (
    <header className="game-header">
      <div className="header-left">
        <div className="header-name">
          {player.clase_emoji} {player.nombre}
        </div>
        <div className="header-location">
          {fEmoji} {player.faccion} · {player.zona_actual || 'Sin ubicación'}
        </div>
      </div>

      <div className="header-right">
        <div className="currency-display">
          <div className="currency-item gold">
            <span>🪙</span>
            <span>{(player.oro || 0).toLocaleString()}</span>
          </div>
          <div className="currency-item eternal">
            <span>💎</span>
            <span>{player.eternium || 0}</span>
          </div>
        </div>
        <button className="notif-btn" onClick={onNotif}>
          🔔
          {player.notificaciones_pendientes > 0 && (
            <span className="notif-badge">{player.notificaciones_pendientes}</span>
          )}
        </button>
      </div>
    </header>
  )
}

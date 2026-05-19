export default function StatBars({ player }) {
  if (!player) return null
  return (
    <div className="stat-bars">
      <div className="stat-bar-row">
        <span className="stat-bar-label">HP</span>
        <div className="stat-bar-track">
          <div className="stat-bar-fill hp" style={{ width: `${player.hp_pct}%` }} />
        </div>
        <span className="stat-bar-text">{player.hp_actual}/{player.hp_max}</span>
      </div>
      <div className="stat-bar-row">
        <span className="stat-bar-label">STA</span>
        <div className="stat-bar-track">
          <div className="stat-bar-fill stamina" style={{ width: `${player.stamina_pct}%` }} />
        </div>
        <span className="stat-bar-text">{player.stamina_actual}/{player.stamina_max}</span>
      </div>
      <div className="stat-bar-row">
        <span className="stat-bar-label">XP</span>
        <div className="stat-bar-track">
          <div className="stat-bar-fill xp" style={{ width: `${player.xp_pct}%` }} />
        </div>
        <span className="stat-bar-text">Nv {player.nivel}</span>
      </div>
    </div>
  )
}

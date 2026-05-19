import { useState, useEffect } from 'react'
import { api } from '../api'

export default function TravelingScreen({ travelInfo, onArrived }) {
  const [secondsLeft, setSecondsLeft] = useState(travelInfo?.segundos_restantes || 0)

  useEffect(() => {
    if (secondsLeft <= 0) {
      api.getTravelStatus().then(s => {
        if (!s.traveling) onArrived()
      })
      return
    }
    const iv = setInterval(() => {
      setSecondsLeft(s => {
        if (s <= 1) {
          clearInterval(iv)
          api.getTravelStatus().then(st => {
            if (!st.traveling) onArrived()
          })
          return 0
        }
        return s - 1
      })
    }, 1000)
    return () => clearInterval(iv)
  }, [])

  const mins = Math.floor(secondsLeft / 60)
  const secs = secondsLeft % 60
  const timeStr = mins > 0 ? `${mins}m ${secs}s` : `${secs}s`

  const COLOR_EMOJI = { azul: '🔵', amarilla: '🟡', roja: '🔴', negra: '⚫' }
  const destColor = travelInfo?.destino_color || 'azul'

  return (
    <div className="traveling-screen">
      <div className="travel-icon">{COLOR_EMOJI[destColor] || '🗺️'}</div>
      <div className="travel-title">Viajando...</div>
      <div className="travel-dest">Destino: <strong>{travelInfo?.destino || '...'}</strong></div>
      <div className="travel-countdown">{timeStr}</div>
      <p style={{ color: 'var(--text-muted)', fontSize: '13px', maxWidth: '260px' }}>
        Estás en camino. No puedes combatir ni explorar durante el viaje.
      </p>
      <button
        className="btn btn-ghost btn-sm"
        onClick={async () => {
          await api.cancelTravel()
          onArrived()
        }}
      >
        ✕ Cancelar viaje
      </button>
    </div>
  )
}

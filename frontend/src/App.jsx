import { useState, useEffect, useCallback, useRef } from 'react'
import { useGameStore } from './stores/gameStore'
import { api } from './api'
import BottomNav from './components/BottomNav'
import GameHeader from './components/GameHeader'
import StatBars from './components/StatBars'
import Toast from './components/Toast'
import MapScreen from './screens/MapScreen'
import ExploreScreen from './screens/ExploreScreen'
import CombatScreen from './screens/CombatScreen'
import InventoryScreen from './screens/InventoryScreen'
import CityScreen from './screens/CityScreen'
import ProfileScreen from './screens/ProfileScreen'
import DungeonScreen from './screens/DungeonScreen'
import GuildScreen from './screens/GuildScreen'
import TravelingScreen from './screens/TravelingScreen'

const SCREENS = {
  map: MapScreen,
  explore: ExploreScreen,
  combat: CombatScreen,
  inventory: InventoryScreen,
  city: CityScreen,
  profile: ProfileScreen,
  dungeon: DungeonScreen,
  guild: GuildScreen,
}

export default function App() {
  const [activeScreen, setActiveScreen] = useState('map')
  const [appReady, setAppReady] = useState(false)
  const [bootError, setBootError] = useState(null)
  const [toastMsg, setToastMsg] = useState(null)
  const [toastType, setToastType] = useState('info')

  const { player, setPlayer, traveling, travelInfo, setTraveling, inCombat } = useGameStore()
  const refreshRef = useRef(null)

  const showToast = useCallback((msg, type = 'info') => {
    setToastMsg(msg)
    setToastType(type)
    setTimeout(() => setToastMsg(null), 3500)
  }, [])

  const loadPlayerData = useCallback(async () => {
    try {
      const data = await api.getMe()
      setPlayer(data)
      return data
    } catch (e) {
      console.error('loadPlayerData error:', e)
      return null
    }
  }, [setPlayer])

  const checkTravel = useCallback(async () => {
    try {
      const status = await api.getTravelStatus()
      if (status.traveling) {
        setTraveling(true, status)
      } else {
        if (status.just_arrived) {
          showToast(`✅ ¡Llegaste a ${status.zona_actual}!`, 'success')
          await loadPlayerData()
        }
        setTraveling(false, null)
      }
    } catch (e) {
      setTraveling(false, null)
    }
  }, [setTraveling, loadPlayerData, showToast])

  useEffect(() => {
    async function boot() {
      try {
        await loadPlayerData()
        await checkTravel()
        setAppReady(true)
      } catch (e) {
        setBootError('No se pudo cargar el juego. Asegúrate de abrirlo desde Telegram.')
        setAppReady(true)
      }
    }
    boot()
  }, [])

  useEffect(() => {
    if (!appReady) return
    refreshRef.current = setInterval(async () => {
      await loadPlayerData()
      await checkTravel()
    }, 15000)
    return () => clearInterval(refreshRef.current)
  }, [appReady, loadPlayerData, checkTravel])

  if (!appReady) {
    return (
      <div className="loading-overlay">
        <div className="spinner" />
        <div className="loading-text">CARGANDO AETHELGARD...</div>
      </div>
    )
  }

  if (bootError) {
    return (
      <div className="loading-overlay">
        <div style={{textAlign:'center', padding:'24px', color:'var(--text-secondary)', maxWidth:'300px'}}>
          <div style={{fontSize:'48px', marginBottom:'16px'}}>⚔️</div>
          <div style={{fontFamily:'Cinzel,serif', fontSize:'16px', color:'var(--text-gold)', marginBottom:'12px'}}>AETHELGARD</div>
          <div style={{fontSize:'13px', marginBottom:'16px'}}>{bootError}</div>
          <div style={{fontSize:'11px', color:'var(--text-muted)'}}>
            Abre el juego desde el bot de Telegram haciendo clic en "Jugar"
          </div>
        </div>
      </div>
    )
  }

  if (traveling && activeScreen !== 'map') {
    return (
      <div className="app-container">
        <GameHeader onNotif={() => setActiveScreen('profile')} />
        <div className="screen-content">
          <TravelingScreen travelInfo={travelInfo} onArrived={() => { setTraveling(false, null); loadPlayerData(); }} />
        </div>
        <BottomNav active={activeScreen} onChange={setActiveScreen} player={player} />
        <Toast message={toastMsg} type={toastType} />
      </div>
    )
  }

  const ScreeComponent = SCREENS[activeScreen] || MapScreen

  return (
    <div className="app-container">
      <GameHeader onNotif={() => setActiveScreen('profile')} />
      <StatBars player={player} />
      <div className="screen-content">
        <ScreeComponent
          player={player}
          onNavigate={setActiveScreen}
          showToast={showToast}
          onRefresh={loadPlayerData}
        />
      </div>
      <BottomNav active={activeScreen} onChange={setActiveScreen} player={player} inCombat={inCombat} />
      <Toast message={toastMsg} type={toastType} />
    </div>
  )
}

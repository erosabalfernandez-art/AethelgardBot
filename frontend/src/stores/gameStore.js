import { create } from 'zustand'

const tg = window.Telegram?.WebApp
const initData = tg?.initData || ''

export const useGameStore = create((set, get) => ({
  player: null,
  zones: [],
  combat: null,
  inCombat: false,
  traveling: false,
  travelInfo: null,
  loading: false,
  error: null,
  notifications: 0,
  lastAction: null,

  setPlayer: (player) => set({ player }),
  setZones: (zones) => set({ zones }),
  setCombat: (combat, inCombat) => set({ combat, inCombat }),
  setTraveling: (traveling, travelInfo) => set({ traveling, travelInfo }),
  setLoading: (loading) => set({ loading }),
  setError: (error) => set({ error }),
  setNotifications: (n) => set({ notifications: n }),
  setLastAction: (msg) => set({ lastAction: msg }),

  getInitData: () => initData,
  getTgUser: () => tg?.initDataUnsafe?.user || null,
}))

const tg = window.Telegram?.WebApp
const BASE_URL = import.meta.env.VITE_API_URL || ''

function getHeaders() {
  return {
    'Content-Type': 'application/json',
    'X-Init-Data': tg?.initData || 'dev_mode',
  }
}

async function req(method, path, body) {
  const opts = {
    method,
    headers: getHeaders(),
  }
  if (body) opts.body = JSON.stringify(body)
  const res = await fetch(`${BASE_URL}/api${path}`, opts)
  const data = await res.json()
  if (!res.ok) {
    throw new Error(data.detail || 'Error del servidor')
  }
  return data
}

export const api = {
  // Player
  getMe: () => req('GET', '/player/me'),
  getStats: () => req('GET', '/player/stats'),
  getGuild: () => req('GET', '/player/guild'),
  getNotifications: () => req('GET', '/player/notifications'),

  // Map
  getZones: () => req('GET', '/map/zones'),
  getZoneDetail: (id) => req('GET', `/map/zone/${id}`),

  // Travel
  startTravel: (destination_id, fast_travel = false) => req('POST', '/travel/start', { destination_id, fast_travel }),
  getTravelStatus: () => req('GET', '/travel/status'),
  cancelTravel: () => req('POST', '/travel/cancel'),

  // Combat
  getCombatStatus: () => req('GET', '/combat/status'),
  startCombat: () => req('POST', '/combat/start'),
  combatAction: (action, skill_index = null) => req('POST', '/combat/action', { action, skill_index }),
  collectResources: () => req('POST', '/combat/collect'),

  // Inventory
  getInventory: () => req('GET', '/inventory/'),
  useItem: (item_nombre) => req('POST', '/inventory/use', { item_nombre }),
  sellItem: (item_nombre) => req('POST', '/inventory/sell', { item_nombre }),

  // City
  getCityServices: () => req('GET', '/city/services'),
  getShop: () => req('GET', '/city/shop'),
  buyItem: (item_id, cantidad = 1) => req('POST', '/city/shop/buy', { item_id, cantidad }),
  getBank: () => req('GET', '/city/bank'),
  bankExchange: (accion, monto, de, a) => req('POST', '/city/bank/exchange', { accion, monto, de, a }),
  useTavern: () => req('POST', '/city/tavern', { accion: 'descansar' }),

  // Dungeons
  getDungeons: () => req('GET', '/dungeon/list'),
  createParty: () => req('POST', '/dungeon/party/create'),
  joinParty: (id) => req('POST', `/dungeon/party/join/${id}`),
  startDungeon: (dungeon_id, solo = false) => req('POST', '/dungeon/start', { dungeon_id, solo }),
}

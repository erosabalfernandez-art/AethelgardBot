"""
guia_contextual.py
Guía emergente que acompaña cada acción del jugador.
Activable/desactivable por el jugador con /guia_on y /guia_off.
"""
import sqlite3
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler

DB_PATH = "aethelgard.db"

# ─── DB ──────────────────────────────────────────────────────────────────────

def _init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("ALTER TABLE jugadores ADD COLUMN guia_activa INTEGER DEFAULT 1")
        conn.commit()
    except sqlite3.OperationalError:
        pass
    conn.close()


def _guia_activa(user_id: int) -> bool:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT guia_activa FROM jugadores WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        return False
    return bool(row[0]) if row[0] is not None else True


def _set_guia(user_id: int, activa: bool):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE jugadores SET guia_activa = ? WHERE user_id = ?",
              (1 if activa else 0, user_id))
    conn.commit()
    conn.close()


def _params_dinamicos() -> dict:
    """Devuelve parámetros actuales del juego para sustituir en los mensajes de guía."""
    p = {
        "seg_recoleccion":        90,
        "seg_investigacion":      90,
        "min_ventana_entrada":     5,
        "min_meditacion_entrada":  2,
        "seg_jefe_cooldown":      30,
        "pct_oro_derrota_pve":    15,
        "pct_hp_derrota":          5,
        "tasa_oro_a_eternium":   500,
        "tasa_eternium_a_oro":   300,
        "tasa_credito_a_eternium": 2,
        "banco_cr_a_et":        "0.1",
        "banco_et_a_cr":        "3.0",
    }
    try:
        import jefes as _j
        p["seg_jefe_cooldown"] = _j.COOLDOWN_ATAQUE
    except Exception:
        pass
    try:
        import combate as _c
        p["pct_oro_derrota_pve"] = int(getattr(_c, "DERROTA_ORO_PORCENTAJE", 0.15) * 100)
        p["pct_hp_derrota"]      = int(getattr(_c, "DERROTA_HP_PORCENTAJE",  0.05) * 100)
    except Exception:
        pass
    try:
        conn = sqlite3.connect(DB_PATH)
        cur  = conn.cursor()
        cur.execute("SELECT clave, valor FROM bolsa_config")
        tasas = {k: v for k, v in cur.fetchall()}
        conn.close()
        if "tasa_oro_a_eternium"    in tasas:
            p["tasa_oro_a_eternium"]    = int(float(tasas["tasa_oro_a_eternium"]))
        if "tasa_eternium_a_oro"    in tasas:
            p["tasa_eternium_a_oro"]    = int(float(tasas["tasa_eternium_a_oro"]))
        if "tasa_credito_a_eternium" in tasas:
            p["tasa_credito_a_eternium"] = int(float(tasas["tasa_credito_a_eternium"]))
    except Exception:
        pass
    try:
        import economia_panel as _ec
        def _fmt_rate(v):
            f = float(v)
            return str(int(f)) if f == int(f) else str(round(f, 4))
        p["banco_cr_a_et"] = _fmt_rate(_ec.CREDITO_A_ETERNIUM)
        p["banco_et_a_cr"] = _fmt_rate(_ec.ETERNIUM_A_CREDITO)
    except Exception:
        pass
    return p


# ─── MENSAJES CONTEXTUALES ────────────────────────────────────────────────────

MENSAJES = {

    # ── CIUDAD ──────────────────────────────────────────────────────────────
    "ciudad_menu": (
        "📖 GUÍA: Has entrado a tu ciudad capital. Aquí estás completamente seguro: sin PvP.\n\n"
        "🏙️ TODO LO QUE PUEDES HACER DESDE AQUÍ\n"
        "🛠️ SERVICIOS\n"
        "• ⚒️ Craftear: fabrica armas y armaduras con materiales. Necesitas recetas "
        "(cómpralas en Tienda → Oro → Recetas).\n"
        "• ✨ Encantar: agrega efectos mágicos a tu equipo crafteado.\n"
        "• 🔧 Herrero: mejora tus armas con gemas y refuerzos.\n"
        "• 🍺 Taberna: misiones diarias, descanso y recuperación de stamina.\n"
        "• 🏦 Banco: guarda oro de forma segura; el gremio tiene su propio banco compartido.\n"
        "🛒 COMERCIO\n"
        "• 🪙 Tienda de Oro: equipo básico, recetas de crafteo, consumibles.\n"
        "• 💎 Tienda de Eternium: equipo premium exclusivo.\n"
        "• ✨ Tienda de Créditos: exclusivos de temporada.\n"
        "• 🏷️ Subastas: vende o compra items entre jugadores.\n"
        "• 💱 Mercado P2P: intercambio directo jugador a jugador.\n\n"
        "⚔️ COMBATE\n"
        "• ⚔️ Duelos PvP: reta a otro jugador. Si pierdes quedas Marcado.\n"
        "• 👹 Jefes Raid: batallas colectivas de hasta 30 jugadores.\n\n"
        "🏰 GREMIO\n"
        "• Ver nivel, subir nivel, depositar materiales, declarar guerras.\n"
        "• Crear gremio requiere nivel 15 (Zona Negra) y Eternium.\n\n"
        "🌍 CONTENIDO\n"
        "• ✈️ Viajes: sal a zonas salvajes para recolectar, investigar y combatir.\n"
        "• 🏰 Mazmorras: dungeons de grupo con jefes y recompensas garantizadas.\n"
        "💡 Consejo: /guia para ver la guía completa con todos los detalles."
    ),

    # ── VIAJES ──────────────────────────────────────────────────────────────
    "viaje_iniciado": (
        "✈️ GUÍA: Has salido de la ciudad y viajando hacia {destino}.\n"
        "⏱️ Duración del trayecto: {tiempo} segundos.\n\n"
        "🔒 MIENTRAS VIAJAS\n"
        "• ❌ No puedes usar servicios de ciudad (crafteo, tienda, gremio).\n"
        "• ❌ No puedes iniciar combates ni recolectar.\n"
        "• 🔔 Recibes notificación automática al llegar.\n\n"
        "🏙️ Si el destino es una CIUDAD: usa /ciudad al llegar para acceder a servicios.\n"
        "🌿 Si el destino es ZONA SALVAJE: podrás recolectar, investigar y combatir.\n"
        "❌ Para cancelar el viaje: /cancelar_viaje"
    ),
    "viaje_instantaneo": (
        "⚡ GUÍA: Viaje instantáneo completado hacia {destino}.\n"
        "🏙️ Si es ciudad: usa /ciudad para acceder a los servicios.\n"
        "🌿 Si es zona salvaje: recolecta, investiga o combate desde los menús."
    ),
    "viaje_llegada_ciudad": (
        "🏙️ GUÍA: Has llegado a {destino}.\n\n"
        "✅ Estás en una CIUDAD — zona completamente segura, sin PvP.\n\n"
        "🚀 QUÉ PUEDES HACER AHORA\n"
        "• /ciudad para ver el menú completo con todos los servicios.\n"
        "• 🛒 Compra recetas de crafteo: Tienda → Oro → Recetas.\n"
        "• ⚒️ Craftea equipo si ya tienes materiales: Servicios → Craftear.\n"
        "• 🍺 Descansa en la taberna para recuperar stamina.\n"
        "• 🏦 Deposita materiales al banco del gremio.\n\n"
        "⚠️ NOTA: si es ciudad de otra facción, algunos servicios pueden estar restringidos.\n"
        "Las ciudades propias de tu facción dan acceso completo a todo."
    ),
    "viaje_llegada_salvaje": (
        "🌿 GUÍA: Has llegado a {destino} — zona salvaje.\n"
        "Zona {color}: {descripcion_color}\n\n"
        "🚀 QUÉ PUEDES HACER AHORA\n"
        "⛏️ RECOLECTAR: usa el menú Ciudad → Contenido → Recolección.\n"
        "Espera {seg_recoleccion} segundos y obtendrás materiales listados en el chat.\n"
        "⚠️ Hay probabilidad de encontrar un monstruo (¡que puede ser peligroso!).\n\n"
        "🔍 INVESTIGAR: usa Ciudad → Contenido → Investigación.\n"
        "Sigue huellas durante {seg_investigacion} segundos. Encontrarás enemigos (normal o mini-boss).\n"
        "🧘 Meditar activa tu inmunidad PvP por hasta {min_meditacion_entrada} minutos.\n\n"
        "✈️ CONTINUAR: usa /viajar para moverte a zonas adyacentes.\n"
        "🛡️ Recibes una ventana de inmunidad de {min_ventana_entrada} min al llegar a cada zona nueva."
    ),
    "viaje_cancelado": (
        "❌ GUÍA: Viaje cancelado. Sigues en tu zona actual.\n"
        "✈️ Puedes iniciar otro viaje cuando quieras con /viajar."
    ),

    # ── MAZMORRAS ────────────────────────────────────────────────────────────
    "mazmorra_inicio_azul": (
        "🟦 GUÍA: Has entrado a la Mazmorra Azul.\n"
        "📊 Nivel recomendado: 1-10.\n"
        "👾 Dentro encontrarás bandidos, lobos mutados y esqueletos.\n"
        "👑 Al final te espera un jefe de mazmorra con recompensas garantizadas.\n"
        "💡 Para ganar: coordina con tu grupo, ataca en orden y cura cuando sea necesario.\n"
        "🎁 Ganarás: Oro, materiales comunes y posible equipo de bronce.\n"
        "🛡️ Consejo: el Vanguardista aguanta al frente, el Tejehechizos ataca desde atrás."
    ),
    "mazmorra_inicio_amarilla": (
        "🟨 GUÍA: Has entrado a la Mazmorra Amarilla.\n"
        "📊 Nivel recomendado: 5-15.\n"
        "👾 Dentro encontrarás golems de piedra, sacerdotes no-muertos y bestias.\n"
        "⚠️ Dificultad media. Los golems tienen alta defensa física.\n"
        "🎁 Ganarás: Oro, materiales poco comunes y equipo de acero.\n"
        "💡 Consejo: el Tejehechizos es especialmente efectivo contra no-muertos."
    ),
    "mazmorra_inicio_roja": (
        "🟥 GUÍA: Has entrado a la Mazmorra Roja.\n"
        "📊 Nivel recomendado: 10-20.\n"
        "👾 Dentro encontrarás demonios menores, necromantes y caballeros malditos.\n"
        "⚠️ ATENCIÓN: El PvP entre jugadores es posible dentro de esta mazmorra.\n"
        "🎁 Ganarás: Oro, materiales raros y equipo épico.\n"
        "💡 Consejo: desconfía de jugadores de otras facciones que entren al mismo tiempo."
    ),
    "mazmorra_inicio_negra": (
        "⬛ GUÍA: Has entrado a la Mazmorra Negra.\n"
        "📊 Nivel recomendado: 15+.\n"
        "👾 Dentro encontrarás entidades del vacío, sombras antiguas y horrores legendarios.\n"
        "☠️ DIFICULTAD EXTREMA. PvP libre. Alta penalización por muerte.\n"
        "🎁 Ganarás: materiales legendarios, equipo único y posibles Créditos del Vacío.\n"
        "💡 Consejo: solo entra con un grupo coordinado y con el mejor equipo disponible."
    ),

    # ── COMBATE PvP ─────────────────────────────────────────────────────────
    "combate_pvp_iniciado": (
        "⚔️ GUÍA: Has retado a {rival} a un duelo PvP.\n"
        "El combate se resuelve automáticamente cuando el rival acepte.\n"
        "📊 El resultado depende de: ataque, defensa, nivel, clase y equipamiento.\n"
        "✅ Si ganas: recibes XP y parte del oro del rival.\n"
        "❌ Si pierdes: quedas MARCADO. Usa /pagar_rescate para liberarte."
    ),
    "combate_pvp_victoria": (
        "🏆 GUÍA: Has ganado el duelo PvP.\n"
        "🎁 Has recibido XP y oro como recompensa.\n"
        "📈 Seguir ganando duelos mejora tu historial y puede desbloquear títulos.\n"
        "💡 Consejo: mejora tu equipamiento para aumentar tus chances en el siguiente duelo."
    ),
    "combate_pvp_derrota": (
        "💀 GUÍA: Has perdido el duelo y quedas MARCADO.\n"
        "⛔ Mientras estás marcado NO puedes:\n"
        "• ✈️ Viajar a otras zonas.\n"
        "• ⚔️ Iniciar nuevos duelos.\n"
        "• 🏙️ Usar algunas funciones de ciudad.\n"
        "⚠️ Paga el rescate con /pagar_rescate para recuperar tu libertad.\n"
        "El monto del rescate depende de tu nivel y oro actual."
    ),

    # ── COMBATE PvE ──────────────────────────────────────────────────────────
    "combate_pve_iniciado": (
        "👾 GUÍA: Has iniciado un combate contra un monstruo.\n\n"
        "⚔️ CÓMO COMBATIR\n"
        "El combate se divide en rondas.\n"
        "Usa los botones para elegir: Atacar, Habilidad especial, Huir.\n\n"
        "⚔️ ATACAR: daño normal según tu clase y equipo.\n"
        "✨ HABILIDAD: daño extra o efecto especial.\n"
        "🏃 HUIR: 60% de éxito. Si fallas, el monstruo ataca y sigues dentro.\n\n"
        "✅ AL GANAR\n"
        "Recibes XP, oro y los objetos caídos (todo detallado en el chat).\n"
        "Se abre una ventana de {min_ventana_entrada} min para meditar y activar inmunidad PvP.\n\n"
        "💀 SI PIERDES\n"
        "⚠️ Pierdes el {pct_oro_derrota_pve}% del oro que llevas encima.\n"
        "❤️ Tu HP cae al {pct_hp_derrota}% del máximo.\n"
        "Usa pociones del inventario o visita la Taberna para recuperarte antes de tu próxima batalla.\n\n"
        "💡 Consejo: si tu vida es baja, usa pociones del inventario antes de atacar."
    ),

    # ── JEFES RAID ───────────────────────────────────────────────────────────
    "jefe_convocado": (
        "👹 GUÍA: Un Jefe Raid ha sido convocado: {nombre}.\n"
        "Esta es una batalla especial de hasta 30 jugadores.\n"
        "⚡ Únete antes de que empiece con /jefe_unirse.\n"
        "Cuando la batalla comience, ataca con /jefe_atacar cada {seg_jefe_cooldown} segundos.\n"
        "🎁 Las recompensas finales son proporcionales al daño que hayas causado.\n"
        "📊 Dificultad: {dificultad}. A mayor dificultad, mejores drops."
    ),
    "jefe_unido": (
        "✅ GUÍA: Te has unido al combate contra el Jefe Raid.\n"
        "⏳ Espera a que comience la batalla.\n"
        "⚔️ Cuando empiece, usa /jefe_atacar cada {seg_jefe_cooldown} segundos.\n"
        "💡 Cuanto más daño hagas, mayor será tu parte de las recompensas."
    ),
    "jefe_ataque": (
        "⚔️ GUÍA: Has atacado al Jefe Raid.\n"
        "⏱️ Tienes un cooldown de {seg_jefe_cooldown} segundos antes de poder atacar de nuevo.\n"
        "📈 Sigue atacando regularmente para acumular más daño y mejores recompensas."
    ),
    "jefe_victoria": (
        "🏆 GUÍA: El Jefe Raid ha sido derrotado.\n"
        "🎁 Las recompensas se distribuyen según el daño causado por cada participante.\n"
        "Revisa tu /inventario y saldo para ver lo que recibiste.\n"
        "Los mejores participantes pueden recibir items especiales adicionales según su daño total."
    ),

    # ── COMERCIO ─────────────────────────────────────────────────────────────
    "tienda_compra": (
        "🛒 GUÍA: Has comprado un objeto.\n"
        "📦 El objeto está ahora en tu /inventario.\n"
        "Para equiparlo: /inventario y selecciona el objeto → Equipar.\n"
        "📈 Los objetos equipados mejoran tus stats de combate inmediatamente.\n"
        "💡 Recuerda: la tienda de Créditos del Vacío tiene objetos exclusivos "
        "que no se consiguen de ninguna otra forma."
    ),
    "subasta_puja": (
        "🏷️ GUÍA: Has pujado en una subasta.\n"
        "✅ Si eres el mejor postor cuando expire, ganas el objeto automáticamente.\n"
        "🔔 Si alguien supera tu puja recibirás una notificación.\n"
        "👁️ Monitorea subastas activas en Ciudad → Comercio → Subastas.\n"
        "💡 Consejo: las subastas en Créditos del Vacío son tu vía para "
        "ganar dinero real vendiendo equipo raro."
    ),
    "bolsa_intercambio": (
        "💱 GUÍA: Has realizado un intercambio en la Bolsa de Valores.\n"
        "📊 TASAS ACTUALES:\n"
        "• 🪙→💎 {tasa_oro_a_eternium} Oro = 1 Eternium\n"
        "• 💎→🪙 1 Eternium = {tasa_eternium_a_oro} Oro\n"
        "• ✨→💎 1 Crédito = {tasa_credito_a_eternium} Eternium\n"
        "⚠️ IMPORTANTE: El bot nunca entrega Créditos del Vacío en la bolsa.\n"
        "Los créditos SOLO se obtienen depositando USDT o comprando a otros jugadores."
    ),
    "deposito_iniciado": (
        "💵 GUÍA: Has iniciado un depósito de USDT.\n"
        "✨ Los Créditos del Vacío tienen valor real: 100 Créditos = 1 USDT.\n"
        "Una vez procesado tu envío, recibirás los créditos automáticamente.\n"
        "Con esos créditos puedes comprar items exclusivos o subastarlos para ganar oro."
    ),

    # ── GREMIO ───────────────────────────────────────────────────────────────
    "gremio_unido": (
        "🏰 GUÍA: Te has unido a un gremio.\n"
        "✅ Ahora tienes acceso a:\n"
        "• 🏦 Banco del gremio: recursos compartidos.\n"
        "• 📈 Bonificaciones de XP y Oro activas.\n"
        "• ⚔️ Participación en guerras de gremio y facciones.\n"
        "💡 Sube de rango siendo activo. Los rangos altos tienen más privilegios."
    ),
    "guerra_gremio_inicio": (
        "⚔️ GUÍA: Tu gremio ha entrado en guerra.\n"
        "🥊 Puedes participar con /guerra_gremios_duelo.\n"
        "El matchmaking te asigna un rival de nivel similar.\n"
        "🏆 El gremio con más victorias al final gana y recibe recompensas para todos.\n"
        "💡 No te quedes fuera: cada victoria cuenta para tu gremio."
    ),
    "guerra_facciones_inicio": (
        "🌍 GUÍA: Ha comenzado una Guerra de Facciones.\n"
        "⚔️ Tu facción lucha contra otra. Todos pueden participar.\n"
        "⚔️ Ataca con /guerra_facciones_atacar.\n"
        "🛡️ Defiende con /guerra_facciones_defender.\n"
        "📊 Ve el ranking con /guerra_facciones_ranking.\n"
        "🏆 La facción ganadora recibe bonificaciones de XP y Oro durante 24 horas."
    ),

    # ── RECOLECCIÓN ──────────────────────────────────────────────────────────
    "recoleccion_inicio": (
        "⛏️ GUÍA: Has iniciado la recolección de materiales.\n"
        "⏱️ Tiempo de espera: {seg_recoleccion} segundos.\n\n"
        "📊 AL TERMINAR PUEDE PASAR (varía por zona):\n"
        "🟦 Zona Azul: 60% éxito, 20% encuentro monstruo, 20% fallo.\n"
        "🟨 Zona Amarilla: 45% éxito, 30% encuentro, 25% fallo.\n"
        "🟥 Zona Roja: 20% éxito, 45% encuentro, 35% fallo.\n"
        "⬛ Zona Negra: éxito raro, 65% encuentro, 50% fallo.\n\n"
        "⚠️ Los monstruos en zonas avanzadas son MUY peligrosos.\n"
        "💀 Si un monstruo te derrota, perderás {pct_oro_derrota_pve}% de tu oro y quedarás con HP al {pct_hp_derrota}%.\n\n"
        "📦 LOS MATERIALES QUE PUEDES OBTENER SEGÚN ZONA:\n"
        "🟦 Zona Azul: materiales comunes (madera, hierro, plantas).\n"
        "🟨 Zona Amarilla: materiales poco comunes (acero, cristales).\n"
        "🟥 Zona Roja: materiales raros (esencias de fuego, fragmentos mágicos).\n"
        "⬛ Zona Negra: materiales legendarios (mithril, esencias del vacío).\n\n"
        "🔧 USOS DE LOS MATERIALES:\n"
        "• ⚒️ Crafteo: fabrica equipo (necesitas recetas de la tienda).\n"
        "• 🏦 Banco de gremio: deposita para subir el nivel del gremio.\n"
        "• 💱 Venta P2P: vende directamente a otros jugadores que los necesiten."
    ),
    "investigacion_inicio": (
        "🔍 GUÍA: Has iniciado la investigación de la zona.\n"
        "⏱️ Tiempo de espera: {seg_investigacion} segundos antes de ver resultados.\n\n"
        "📊 AL TERMINAR LOS {seg_investigacion} SEGUNDOS ENCONTRARÁS:\n"
        "🟡 65% probabilidad: mini-boss con más HP, XP y oro.\n"
        "⚪ 30% probabilidad: monstruo normal. Se inicia combate.\n"
        "❌ 5% probabilidad: rastro perdido. Sin combate, sin recompensa.\n\n"
        "⚠️ ATENCIÓN: los monstruos de Aethelgard son PELIGROSOS.\n"
        "Usa habilidades especiales y pociones para sobrevivir.\n"
        "💀 Si pierdes: -{pct_oro_derrota_pve}% oro y HP al {pct_hp_derrota}% del máximo.\n\n"
        "TRAS EL COMBATE verás en el chat todo lo que ganaste: "
        "XP, oro y cada objeto con su cantidad exacta.\n\n"
        "💡 CONSEJO: el mini-boss da hasta 3x más XP y oro que un monstruo normal.\n"
        "Si quieres protección antes o después: usa el botón Meditar del menú.\n"
        "🧘 La meditación activa inmunidad PvP temporal."
    ),

    # ── CRAFTEO ──────────────────────────────────────────────────────────────
    "crafteo_realizado": (
        "⚒️ GUÍA: ¡Has fabricado un objeto!\n\n"
        "Los objetos crafteados superan a los de tienda porque utilizan materiales "
        "de zonas salvajes avanzadas que los comerciantes normales no tienen.\n\n"
        "🚀 PRÓXIMOS PASOS\n"
        "• 🔧 El herrero puede reforzar tu arma nueva con gemas: Ciudad → Servicios → Herrero.\n"
        "• ✨ El encantador puede añadir efectos mágicos: Ciudad → Servicios → Encantar.\n"
        "• 📦 Equipa tu nueva pieza desde el menú /inventario.\n\n"
        "💡 RECUERDA: cada receta solo se compra una vez y queda permanentemente en tu cuenta.\n"
        "Para comprar más recetas: Ciudad → Comercio → Tienda → Oro → Recetas."
    ),

    # ── PROGRESIÓN ───────────────────────────────────────────────────────────
    "subida_nivel": (
        "🎉 GUÍA: Has subido al nivel {nivel}.\n"
        "🔓 Nuevos desbloqueos:\n"
        "🟨 Nivel 5: acceso a zonas amarillas. Habilidades secundarias disponibles.\n"
        "🟥 Nivel 10: acceso a zonas rojas. Habilidades avanzadas de clase.\n"
        "⬛ Nivel 15: acceso a Zona Negra (la más peligrosa) y puedes CREAR un gremio.\n"
        "📈 Tus stats base de ataque y defensa han aumentado automáticamente."
    ),
    "marcado": (
        "⛔ GUÍA: Has quedado marcado tras perder un combate.\n"
        "Mientras estás marcado NO puedes viajar ni atacar a otros jugadores.\n"
        "💡 Para liberarte: /pagar_rescate\n"
        "El monto del rescate se calcula según tu nivel y oro actual.\n"
        "💡 Consejo: mejora tu equipo antes del próximo duelo."
    ),
    "rescate_pagado": (
        "✅ GUÍA: Has pagado el rescate y eres libre.\n"
        "Ya puedes viajar y participar en combates de nuevo.\n"
        "💡 Revisa tu equipamiento con /inventario antes de tu próximo duelo."
    ),

    # ── MENÚ RÁPIDO ──────────────────────────────────────────────────────────
    "menu_actualizado": (
        "📱 GUÍA: Tu menú rápido se ha actualizado a la zona actual.\n\n"
        "🔄 BOTÓN ACTUALIZAR MENÚ\n"
        "Siempre que cambies de zona (ciudad ↔ zona salvaje) o cuando empiece "
        "una guerra de facciones, pulsa el botón 🔄 Actualizar menú para ver "
        "los botones correctos para tu situación.\n\n"
        "⚙️ EDITOR DE MENÚ (solo en ciudad)\n"
        "Si estás en ciudad, puedes personalizar qué botones quieres en tu menú. "
        "Pulsa ⚙️ Editar menú para abrir el panel de configuración.\n\n"
        "🔲 OCULTAR MENÚ\n"
        "Si prefieres usar comandos de texto, pulsa 🔲 Ocultar menú. "
        "Para recuperar el menú usa /menu o el botón que aparece al ocultarlo.\n\n"
        "💡 Usa /guia → capítulo 23 para ver la guía completa del sistema de menús."
    ),


    # ── CRAFTEO / RECETAS ──────────────────────────────────────────────────────
    "crafteo_sin_recetas": (
        "📖 GUÍA: No tienes recetas aprendidas disponibles para tu nivel y clase.\n\n"
        "📋 LAS RECETAS SON IMPRESCINDIBLES\n"
        "Sin receta no se puede fabricar ningún objeto. Es el sistema de crafteo del juego.\n"
        "Solo aparecerán en el menú de crafteo las recetas que ya hayas comprado.\n\n"
        "🛒 CÓMO COMPRAR RECETAS\n"
        "1. Ve a Ciudad → Comercio → Tienda.\n"
        "2. Elige Catálogo de Oro.\n"
        "3. Selecciona Recetas de crafteo.\n"
        "4. Elige la receta que te interese (filtra por clase y nivel).\n"
        "5. Confirma la compra con Oro.\n\n"
        "Una vez comprada, la receta aparecerá permanentemente en tu panel de crafteo.\n"
        "💡 Consejo: empieza por recetas de tu clase y nivel actual para sacarles el mayor partido."
    ),
    "receta_comprada": (
        "✅ GUÍA: Has comprado una receta de crafteo.\n\n"
        "La receta ya está en tu cuenta de forma permanente.\n"
        "📦 Ahora necesitas los materiales indicados en la receta.\n\n"
        "⛏️ CÓMO OBTENER MATERIALES\n"
        "1. Sal de la ciudad: Ciudad → Contenido → Viajes.\n"
        "2. Viaja a una zona salvaje del color indicado en la receta.\n"
        "3. Usa Recolección: espera {seg_recoleccion} segundos y recibe los materiales en el chat.\n"
        "4. Repite hasta tener la cantidad necesaria.\n\n"
        "Cuando tengas todos los materiales:\n"
        "Ciudad → Servicios → Craftear → elige tu receta → confirma."
    ),

    # ── INVENTARIO ───────────────────────────────────────────────────────────
    "inventario_abierto": (
        "📦 GUÍA: Has abierto tu inventario.\n\n"
        "📂 SECCIONES\n"
        "🗡️ Equipamiento: piezas actualmente equipadas (arma, armadura, casco, botas...).\n"
        "🎒 Objetos: materiales, gemas, miscelánea.\n"
        "🧪 Consumibles: pociones y comida que puedes usar en combate.\n"
        "💎 Mejoras: gemas y materiales de encantamiento.\n\n"
        "⚙️ CÓMO EQUIPAR\n"
        "Pulsa 'Equipar rápido' para ver todos los items que puedes equipar ahora mismo.\n"
        "Selecciona uno y confirma. Tus stats de combate se actualizan al instante.\n\n"
        "💡 Consejo: un buen equipamiento marca la diferencia en duelos PvP.\n"
        "Revisa el herrero (Ciudad → Servicios → Herrero) para mejorar tus piezas."
    ),

    # ── PERFIL ───────────────────────────────────────────────────────────────
    "perfil_abierto": (
        "👤 GUÍA: Estás viendo tu perfil de personaje.\n\n"
        "📊 QUÉ MUESTRA EL PERFIL\n"
        "⚔️ Stats base: ataque, defensa, velocidad, vida máxima.\n"
        "🧬 Clase y subclase: determinan qué habilidades especiales tienes.\n"
        "🏴 Facción: Alianza, Imperio o Sindicato.\n"
        "📈 Nivel y experiencia: progresa derrotando monstruos y completando misiones.\n"
        "💼 Saldos: oro, eternium y créditos del vacío que posees.\n\n"
        "🧬 CLASE Y SUBCLASE\n"
        "Tu clase base define tus stats. La subclase (si la tienes) da bonificaciones extra.\n"
        "Las subclases se desbloquean al avanzar de nivel y completar misiones de clase.\n\n"
        "📋 TALENTOS Y MISIONES\n"
        "Usa los botones de abajo para ver tus talentos activos y misiones pendientes.\n"
        "Completa misiones para ganar oro y XP extra."
    ),

    # ── BANCO ────────────────────────────────────────────────────────────────
    "banco_menu": (
        "🏦 GUÍA: Has abierto el Banco Central de Aethelgard.\n\n"
        "⚙️ QUÉ PUEDES HACER\n"
        "💱 Cambio Oro ↔ Eternium: convierte entre monedas según la tasa vigente.\n"
        "💱 Cambio Créditos → Eternium: consume créditos del vacío para obtener eternium.\n\n"
        "💰 LAS TRES MONEDAS\n"
        "🪙 Oro: moneda principal. Se gana en combate, misiones y comercio.\n"
        "💎 Eternium: moneda premium. Se obtiene cambiando oro o en eventos especiales.\n"
        "✨ Créditos del Vacío: moneda real (100 = 1 USDT). Solo se deposita o compra a jugadores.\n\n"
        "📊 TASAS DE CAMBIO ACTUALES\n"
        "• 🪙→💎 {tasa_oro_a_eternium} Oro = 1 Eternium\n"
        "• 💎→🪙 1 Eternium = {tasa_eternium_a_oro} Oro\n"
        "• ✨→💎 1 Crédito = {banco_cr_a_et} Eternium (banco)\n"
        "• 💎→✨ 1 Eternium = {banco_et_a_cr} Créditos (banco)\n\n"
        "📅 INTERÉS SEMANAL\n"
        "El banco paga interés sobre el oro que tengas al finalizar cada semana."
    ),
    "banco_cambio": (
        "✅ GUÍA: Has realizado un cambio de moneda.\n\n"
        "La transacción se ha procesado y tu saldo se ha actualizado.\n"
        "Puedes ver el historial de tus transacciones con el botón Historial del banco.\n\n"
        "💡 CONSEJO\n"
        "💎 El Eternium es muy útil para:\n"
        "• 🏰 Crear gremios (requisito mínimo).\n"
        "• 🛒 Comprar items en la Tienda de Eternium.\n"
        "• ⚡ Pagar vuelos rápidos entre ciudades.\n"
        "🪙 El oro se gana más fácilmente con recolección y combate continuo."
    ),

    # ── SUBASTAS ─────────────────────────────────────────────────────────────
    "subastas_menu": (
        "🏷️ GUÍA: Has abierto la Casa de Subastas.\n\n"
        "⚙️ CÓMO FUNCIONA\n"
        "👁️ Ver subastas: lista las subastas activas de todos los jugadores.\n"
        "🔨 Pujar: ofrece más que el precio actual para ganar el item.\n"
        "📦 Publicar subasta: pon tu propio item a subasta.\n\n"
        "💱 PRECIOS Y MONEDAS\n"
        "Puedes subastar por Oro, Eternium o Créditos del Vacío.\n"
        "Las subastas en Créditos son la mejor forma de ganar dinero real jugando.\n"
        "El vendedor paga una comisión sobre el precio final.\n\n"
        "🧠 ESTRATEGIA\n"
        "⬛ Los items más valiosos son armas/armaduras de mazmorras negras y jefes raid.\n"
        "Si tienes un item legendario, subástalo por Créditos del Vacío para maximizar ganancias.\n"
        "Las subastas duran entre 1 y 24 horas. Configura la duración al publicar."
    ),
    "subasta_creada": (
        "✅ GUÍA: Tu subasta ha sido publicada.\n\n"
        "🔔 Cuando alguien puje en tu item recibirás una notificación.\n"
        "Si alguien supera la mejor puja, el pujador anterior también recibe aviso.\n"
        "Al finalizar el tiempo, el mejor postor se lleva el item automáticamente.\n"
        "Tu recibirás el oro/eternium/créditos de la puja ganadora, menos la comisión.\n\n"
        "Puedes ver tus subastas activas en Casa de Subastas → Mis subastas.\n"
        "Puedes cancelar antes de que haya pujas desde el mismo menú."
    ),

    # ── P2P ──────────────────────────────────────────────────────────────────
    "p2p_menu": (
        "💱 GUÍA: Has abierto el Mercado P2P de Monedas.\n\n"
        "🔍 DIFERENCIA CON SUBASTAS\n"
        "Las subastas son para items (equipo, materiales).\n"
        "El P2P es para intercambiar monedas directamente entre jugadores.\n\n"
        "⚙️ CÓMO FUNCIONA\n"
        "Publicas una oferta indicando cuánto ofreces y cuánto pides a cambio.\n"
        "Ejemplo: ofrezco 1000 Oro, pido 10 Eternium.\n"
        "Otro jugador ve tu oferta y la acepta si le conviene.\n"
        "El intercambio es instantáneo al aceptar.\n\n"
        "⏱️ LAS OFERTAS EXPIRAN en 7 días si nadie las acepta.\n"
        "Puedes cancelar tus ofertas activas antes de que expiren."
    ),
    "p2p_oferta_creada": (
        "✅ GUÍA: Tu oferta P2P ha sido publicada.\n\n"
        "Cuando otro jugador la acepte, el intercambio ocurre automáticamente.\n"
        "Si nadie la acepta en 7 días, la oferta expira y recuperas lo ofrecido.\n"
        "Puedes ver tus ofertas activas en Mercado P2P → Mis ofertas.\n\n"
        "💡 CONSEJO: revisa las ofertas activas de otros jugadores primero.\n"
        "Si ya hay alguien ofreciendo lo que necesitas, acepta su oferta directamente "
        "en vez de crear la tuya propia."
    ),
    "p2p_oferta_aceptada": (
        "✅ GUÍA: Has aceptado una oferta P2P.\n\n"
        "El intercambio de monedas se ha completado al instante.\n"
        "🔔 El otro jugador recibirá notificación de que su oferta fue aceptada.\n\n"
        "Consulta tu nuevo saldo en /perfil o en el menú del banco.\n"
        "Si necesitas más, ve a Mercado P2P → Ver ofertas para buscar más deals."
    ),

    # ── GREMIO ───────────────────────────────────────────────────────────────
    "gremio_menu": (
        "🏰 GUÍA: Has abierto el menú de tu Gremio.\n\n"
        "📋 OPCIONES DISPONIBLES\n"
        "📊 Info del gremio: stats, nivel, bonificaciones activas.\n"
        "👥 Miembros: lista completa con rangos y actividad.\n"
        "🏦 Baúl: deposita o retira recursos del banco compartido.\n"
        "📨 Invitar: invita a nuevos jugadores (requiere rango Oficial o superior).\n"
        "⚔️ Guerras: declara guerra a otro gremio.\n\n"
        "📈 BONIFICACIONES DEL GREMIO\n"
        "Cada nivel del gremio aumenta XP%, Oro%, Stamina y capacidad.\n"
        "Para subir nivel: deposita materiales y oro en el banco del gremio.\n"
        "Los miembros más activos aceleran el progreso del gremio."
    ),

    # ── SUBMENÚS CIUDAD ──────────────────────────────────────────────────────
    "submenu_servicios": (
        "🛠️ GUÍA: Servicios de la Ciudad.\n\n"
        "⚒️ CRAFTEAR: fabrica equipo con materiales. Necesitas recetas previas "
        "(Tienda → Oro → Recetas).\n"
        "✨ ENCANTAR: agrega efectos mágicos a equipo ya fabricado.\n"
        "🔧 HERRERO: refuerza armas/armaduras con gemas para aumentar stats.\n"
        "🍺 TABERNA: descansa para recuperar stamina y acepta misiones diarias.\n"
        "🏦 BANCO: cambia entre oro, eternium y créditos "
        "(tasas: {tasa_oro_a_eternium} oro = 1 eternium; 1 crédito = {banco_cr_a_et} eternium).\n"
        "🐴 MONTURA: alquila una montura para reducir el tiempo de viaje.\n\n"
        "💡 Consejo: el orden óptimo es: recolectar materiales → comprar receta → craftear → mejorar con herrero."
    ),
    "submenu_comercio": (
        "🛒 GUÍA: Comercio de la Ciudad.\n\n"
        "🪙 TIENDA ORO: equipo básico, pociones y recetas de crafteo. Pagos en Oro.\n"
        "💎 TIENDA ETERNIUM: equipo premium exclusivo. Pagos en Eternium.\n"
        "✨ TIENDA CRÉDITOS: items únicos de temporada. Pagos en Créditos del Vacío.\n"
        "🏷️ SUBASTAS: mercado de jugadores con pujas. Mejor opción para items raros.\n"
        "💱 MERCADO P2P: intercambia monedas directamente con otros jugadores.\n"
        "📊 BOLSA DE VALORES: tipo de cambio oficial entre monedas.\n"
        "✨ CRÉDITOS DEL VACÍO: deposita USDT o retira tus créditos a billetera real.\n\n"
        "💡 Los Créditos del Vacío son la única moneda con valor real (100 = 1 USDT)."
    ),
    "submenu_combate": (
        "⚔️ GUÍA: Opciones de Combate.\n\n"
        "⚔️ DUELOS PvP: reta a otro jugador con /duelo @usuario.\n"
        "El resultado depende de: ataque, defensa, nivel, clase y equipo.\n"
        "✅ Si ganas: XP y parte del oro del rival.\n"
        "❌ Si pierdes: quedas Marcado y no puedes viajar hasta pagar rescate.\n\n"
        "👹 JEFES RAID: cuando hay un jefe activo, únete con /jefe_unirse.\n"
        "Son batallas de hasta 30 jugadores. Cuanto más daño hagas, mejor recompensa.\n\n"
        "💀 COMBATE PvE: los monstruos de zona son PELIGROSOS. Si te derrotan:\n"
        "• Pierdes {pct_oro_derrota_pve}% del oro que llevas encima.\n"
        "• Tu HP cae al {pct_hp_derrota}% del máximo.\n\n"
        "💡 Consejo: mejora tu equipo antes de retar a jugadores de nivel superior."
    ),
    "submenu_gremio": (
        "🏰 GUÍA: Gestión de Gremio.\n\n"
        "👥 MI GREMIO: ver info, baúl, miembros y gestionar si eres líder.\n"
        "🏗️ CREAR GREMIO: requiere nivel 15 (Zona Negra) y Eternium.\n"
        "🔍 BUSCAR GREMIOS: unirte a uno ya existente con invitación.\n"
        "📈 NIVEL DEL GREMIO: ver bonificaciones actuales y requisitos para subir.\n"
        "⚔️ GUERRA: declara guerra a otro gremio (líderes solamente).\n\n"
        "✅ Por qué unirte a un gremio:\n"
        "• 📈 Bonificaciones de XP y Oro activas para todos los miembros.\n"
        "• 🏦 Acceso al baúl común con recursos compartidos.\n"
        "• ⚔️ Participación en guerras de gremio y facciones con grandes recompensas."
    ),
    "submenu_mazmorras": (
        "🏰 GUÍA: Acceso a Mazmorras.\n\n"
        "Solo puedes entrar a la mazmorra de tu zona actual.\n"
        "Para cambiar de mazmorra, viaja primero a otra zona.\n\n"
        "🎨 TIPOS DE MAZMORRA\n"
        "🟦 Azul (nivel 1-10): ideal para empezar. Drops comunes.\n"
        "🟨 Amarilla (nivel 5-15): dificultad media. Drops poco comunes.\n"
        "🟥 Roja (nivel 10-20): dificultad alta. PvP posible. Drops raros.\n"
        "⬛ Negra (nivel 15+): extrema. PvP libre. Drops legendarios.\n\n"
        "Las mazmorras requieren grupo (mín. 2, máx. 5 jugadores).\n"
        "Un jugador crea la sala con /mazmorra y otros se unen con /unirme_mazmorra."
    ),
    "submenu_contenido": (
        "🌍 GUÍA: Contenido de Mundo Abierto.\n\n"
        "⛏️ RECOLECCIÓN: sal a una zona salvaje y recolecta materiales.\n"
        "Pulsa el botón, espera {seg_recoleccion}s y recibes materiales listados en el chat.\n"
        "⚠️ Probabilidad de encuentro con monstruo: 20% (azul) hasta 65% (negra).\n\n"
        "🔍 INVESTIGACIÓN: sigue huellas de criaturas durante {seg_investigacion}s.\n"
        "🟡 65% mini-boss, ⚪ 30% monstruo normal, ❌ 5% rastro perdido.\n"
        "El combate te da XP, oro y objetos detallados en el chat.\n\n"
        "💀 SI PIERDES UN COMBATE: -{pct_oro_derrota_pve}% oro y HP al {pct_hp_derrota}%. ¡Prepárate bien!\n\n"
        "🧘 MEDITACIÓN: activa inmunidad PvP temporal tras llegar a una zona.\n\n"
        "✈️ VIAJES: muévete entre las 33 zonas del mundo con /viajar.\n"
        "Cada zona tiene materiales y enemigos distintos según su color."
    ),

    # ── MISIONES ─────────────────────────────────────────────────────────────
    "misiones_menu": (
        "📋 GUÍA: Panel de Misiones.\n\n"
        "Las misiones de inicio te guían por las mecánicas básicas del juego.\n"
        "Completarlas te da Oro y XP extra para comenzar con ventaja.\n\n"
        "✅ CÓMO COMPLETAR MISIONES\n"
        "La mayoría se completan automáticamente al realizar la acción correspondiente.\n"
        "Ejemplo: la misión 'Hacer tu primer viaje' se completa al usar /viajar.\n"
        "No necesitas confirmar nada, el sistema lo detecta solo.\n\n"
        "📊 Progreso visible: la barra muestra cuántas completaste del total.\n"
        "Al completar todas: recibes una recompensa especial de fin de saga."
    ),
    "mision_completada": (
        "🎉 GUÍA: Has completado una misión.\n\n"
        "La recompensa (oro y XP) ya fue aplicada a tu cuenta automáticamente.\n"
        "Puedes ver tu progreso total con /misiones.\n\n"
        "Las misiones te introducen a todos los sistemas del juego.\n"
        "Si ya completaste todas las de inicio, los logros son el siguiente reto.\n"
        "🏆 Revisa /logros para ver qué has conseguido y qué te falta."
    ),

    # ── LOGROS ───────────────────────────────────────────────────────────────
    "logros_menu": (
        "🏆 GUÍA: Panel de Logros.\n\n"
        "Los logros son retos permanentes que recompensan la constancia y la maestría.\n"
        "Se desbloquean automáticamente al alcanzar ciertos hitos.\n\n"
        "🎯 EJEMPLOS DE LOGROS\n"
        "⚔️ Primeros pasos: ganar tu primer combate PvP.\n"
        "⛏️ Recolector: obtener X materiales en total.\n"
        "🗺️ Explorador: visitar todas las zonas del mundo.\n"
        "🏰 Maestro del gremio: subir tu gremio al nivel 10.\n\n"
        "🎁 RECOMPENSAS\n"
        "Algunos logros desbloquean títulos exclusivos que se muestran en tu perfil.\n"
        "Los títulos raros dan bonificaciones de stats adicionales.\n"
        "Usa /titulos para gestionar tus títulos desbloqueados."
    ),

    # ── GUERRA ───────────────────────────────────────────────────────────────
    "guerra_gremios_duelo": (
        "⚔️ GUÍA: Has iniciado un duelo de guerra de gremios.\n\n"
        "⚙️ CÓMO FUNCIONA\n"
        "El matchmaking te asigna un rival de nivel similar del gremio enemigo.\n"
        "El combate se resuelve automáticamente según stats y equipo.\n"
        "📈 Cada victoria suma puntos a tu gremio.\n\n"
        "El gremio con más puntos al terminar la guerra gana.\n"
        "🎁 Los ganadores reciben: Oro, Eternium y materiales especiales.\n\n"
        "💡 Consejo: equipa tu mejor armamento antes de cada duelo.\n"
        "Puedes hacer múltiples duelos durante la guerra (un duelo por ronda)."
    ),
    "guerra_facciones_ataque": (
        "⚔️ GUÍA: Has atacado en la Guerra de Facciones.\n\n"
        "Tu ataque suma puntos a tu facción.\n"
        "El enfrentamiento se calcula contra un defensor real de la facción rival.\n\n"
        "📊 PUNTUACIÓN\n"
        "✅ Victoria en ataque: suma 2 puntos a tu facción.\n"
        "❌ Derrota en ataque: suma 0 puntos, pero el rival gana 1.\n\n"
        "La facción con más puntos al terminar la guerra recibe:\n"
        "• 📈 Bonificación de +20% XP y Oro para todos sus miembros durante 24h.\n"
        "• 🎁 Recompensas individuales para los 10 mejores atacantes.\n\n"
        "Vuelve a atacar tantas veces como puedas. Cada ataque cuenta."
    ),
    "guerra_facciones_defensa": (
        "🛡️ GUÍA: Has defendido en la Guerra de Facciones.\n\n"
        "Tu defensa protege los puntos de tu facción.\n"
        "Una defensa exitosa niega los puntos del atacante.\n\n"
        "📈 Defender genera XP aunque no aporta puntos directos.\n"
        "Los 10 mejores defensores también reciben recompensas al terminar la guerra.\n\n"
        "💡 Consejo: si tu facción tiene ventaja, defender es más eficiente que atacar.\n"
        "Si van perdiendo, mejor atacar para reducir la diferencia de puntos."
    ),

    # ── PEAJE ────────────────────────────────────────────────────────────────
    "peaje_encontrado": (
        "⛔ GUÍA: Has llegado a un puesto de peaje.\n\n"
        "Algunas zonas controladas por otras facciones requieren pagar un peaje para entrar.\n"
        "El monto depende del nivel de la zona y tu facción.\n\n"
        "🔘 OPCIONES\n"
        "🪙 Pagar: pagas el oro requerido y entras normalmente.\n"
        "⚔️ Combatir al guardia: arriesgado. Si ganas, entras gratis. Si pierdes, quedas Marcado.\n"
        "🔙 Retroceder: cancelas el viaje y vuelves a tu zona anterior.\n\n"
        "💡 Consejo: si no tienes suficiente oro o eres de bajo nivel, paga el peaje.\n"
        "⬛ Los guardias de zona negra son extremadamente fuertes."
    ),

    # ── LOGIN DIARIO ─────────────────────────────────────────────────────────
    "login_diario_reclamado": (
        "🗓️ GUÍA: ¡Recompensa de login diario recibida!\n\n"
        "🔥 SISTEMA DE RACHA\n"
        "Entra al juego cada día para mantener tu racha activa.\n"
        "Cuantos más días seguidos, mayor la recompensa:\n"
        "• Día 1: 50🪙  • Día 2: 100🪙  • Día 3: 150🪙 + poción\n"
        "• Día 4: 200🪙  • Día 5: 250🪙  • Día 6: 300🪙\n"
        "• 🏆 Día 7: 500🪙 + 5💎 + Poción de Vida Mayor\n\n"
        "⚠️ Si saltas un día, la racha se reinicia desde el día 1.\n"
        "💡 Usa /login cada día para reclamar tu recompensa."
    ),

    # ── MISIONES DIARIAS ─────────────────────────────────────────────────────
    "mision_diaria_completada": (
        "📋 GUÍA: ¡Misión diaria completada!\n\n"
        "Has completado una misión del día. Las recompensas te esperan:\n"
        "Usa /misiones_hoy para reclamarlas.\n\n"
        "📌 Las misiones se renuevan cada día a las 00:00 UTC.\n"
        "💡 Completa las 3 misiones del día para maximizar tus recompensas.\n"
        "Cada misión es diferente: matar monstruos, recolectar, visitar mazmorras, etc."
    ),

    # ── CHAT DE GREMIO ───────────────────────────────────────────────────────
    "gchat_enviado": (
        "💬 GUÍA: Mensaje enviado al chat de gremio.\n\n"
        "El chat de gremio te permite comunicarte con todos tus compañeros.\n\n"
        "📌 COMANDOS DE CHAT\n"
        "• /gchat <mensaje> — enviar un mensaje a todos los miembros\n"
        "• /gchat_log — ver los últimos 10 mensajes del gremio\n\n"
        "💡 Coordínate con tu gremio para:\n"
        "• Organizar raids de jefes conjuntos\n"
        "• Planear guerras de gremios\n"
        "• Intercambiar materiales y recursos"
    ),

    # ── ZONA ACTIVA ──────────────────────────────────────────────────────────
    "zona_activa_llegada": (
        "👥 GUÍA: Has llegado a una zona con otros jugadores activos.\n\n"
        "Puedes ver quién está en tu zona con /zona_jugadores.\n\n"
        "⚠️ CUIDADO CON EL PvP\n"
        "• 🟦 Zona azul: PvP desactivado — estás seguro.\n"
        "• 🟨 Zona amarilla: PvP restringido — ten precaución.\n"
        "• 🟥 Zona roja: PvP habilitado — cuidado con jugadores rivales.\n"
        "• ⬛ Zona negra: PvP libre — cualquiera puede atacarte.\n\n"
        "🧘 Si quieres protección, usa la meditación para activar inmunidad PvP."
    ),

    # ── RESUMEN DE SESIÓN ────────────────────────────────────────────────────
    "resumen_sesion_enviado": (
        "📊 GUÍA: Has recibido el resumen de tu aventura.\n\n"
        "El resumen muestra todo lo que lograste mientras explorabas la zona:\n"
        "• Monstruos derrotados y XP ganada\n"
        "• Oro obtenido de combates y recolecciones\n"
        "• Ítems recogidos durante la aventura\n\n"
        "💡 El resumen aparece automáticamente al volver a ciudad.\n"
        "Úsalo para planificar tu próxima sesión de exploración."
    ),

    # ── COOLDOWNS ────────────────────────────────────────────────────────────
    "cooldowns_consultados": (
        "⏱️ GUÍA: Panel de cooldowns.\n\n"
        "Los cooldowns son tiempos de espera entre acciones.\n"
        "Usa /cooldowns (o /cd) para ver todos tus tiempos de espera actuales.\n\n"
        "⚡ STAMINA: se regenera automáticamente con el tiempo.\n"
        "⛏️ RECOLECCIÓN: espera antes de recolectar de nuevo.\n"
        "✈️ VUELO RÁPIDO: cooldown entre teletransportes.\n"
        "🔄 ACTIVIDAD EN CURSO: tiempo restante de tu acción actual.\n\n"
        "💡 Planifica tus acciones según tus cooldowns para maximizar tu progreso."
    ),

    # ── ITEM COMPARADO ───────────────────────────────────────────────────────
    "item_comparacion": (
        "🔍 GUÍA: Comparación de ítem.\n\n"
        "Cuando obtienes un arma o armadura, el juego la compara automáticamente "
        "con tu equipo actual.\n\n"
        "📊 QUÉ MUESTRAN LOS INDICADORES\n"
        "✅ Verde: el nuevo ítem es MEJOR en ese stat.\n"
        "⬇️ Rojo: el nuevo ítem es PEOR en ese stat.\n"
        "= Igual: mismo valor que el actual.\n\n"
        "💡 Si el ítem es una mejora, equípalo desde /inventario → Equipar.\n"
        "Si es peor, guárdalo para vender o regalar a compañeros de gremio."
    ),
}


DESCRIPCION_COLOR = {
    "azul":     "🟦 Zona segura, ideal para empezar. Sin PvP.",
    "amarilla": "🟨 Peligro medio. PvP restringido. Mejores materiales.",
    "roja":     "🟥 Peligro alto. PvP permitido. Materiales raros. Ten cuidado.",
    "negra":    "⬛ EXTREMO. PvP libre. Los mejores drops del juego. Solo para expertos.",
}

# ─── FUNCIÓN PRINCIPAL ────────────────────────────────────────────────────────

async def enviar(user_id: int, context, tipo: str, datos: dict = None):
    """
    Envía un mensaje de guía contextual al jugador si lo tiene activado.
    Llama a esta función desde cualquier módulo tras una acción importante.
    Si falla, el error se suprime para no interrumpir el flujo del juego.
    """
    if datos is None:
        datos = {}
    try:
        if not _guia_activa(user_id):
            return
        plantilla = MENSAJES.get(tipo)
        if not plantilla:
            return
        if "color" in datos and "descripcion_color" not in datos:
            datos["descripcion_color"] = DESCRIPCION_COLOR.get(datos["color"], "")
        # Parámetros dinámicos del juego (datos del llamador tienen prioridad)
        params = _params_dinamicos()
        params.update(datos)
        try:
            texto = plantilla.format(**params)
        except Exception:
            texto = plantilla
        await context.bot.send_message(chat_id=user_id, text=texto)
    except Exception:
        pass  # La guía nunca debe romper el flujo principal

# ─── COMANDOS DE TOGGLE ───────────────────────────────────────────────────────

async def cmd_guia_on(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    _set_guia(user_id, True)
    await update.effective_message.reply_text(
        "🔔 Guía emergente ACTIVADA.\n"
        "Recibirás una explicación después de cada acción importante.\n"
        "Para desactivar: /guia_off"
    )


async def cmd_guia_off(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    _set_guia(user_id, False)
    await update.effective_message.reply_text(
        "🔕 Guía emergente DESACTIVADA.\n"
        "Ya no recibirás mensajes automáticos.\n"
        "Para reactivar: /guia_on\n"
        "Para ver la guía completa: /guia"
    )


async def cmd_estado_guia(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    activa = _guia_activa(user_id)
    estado = "🔔 ACTIVADA" if activa else "🔕 DESACTIVADA"
    await update.effective_message.reply_text(
        f"📖 Estado de tu guía emergente: {estado}\n\n"
        f"/guia_on para activar\n"
        f"/guia_off para desactivar\n"
        f"/guia para ver el índice completo"
    )

# ─── REGISTRO ─────────────────────────────────────────────────────────────────

def registrar_handlers(app):
    _init_db()
    app.add_handler(CommandHandler("guia_on",   cmd_guia_on))
    app.add_handler(CommandHandler("guia_off",  cmd_guia_off))
    app.add_handler(CommandHandler("mi_guia",   cmd_estado_guia))

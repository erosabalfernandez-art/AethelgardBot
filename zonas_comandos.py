"""
zonas_comandos.py — Actualiza la lista de sugerencias "/" del bot
adaptada a la zona y ubicación (ciudad/salvaje) del jugador.

Llamar a actualizar_comandos_jugador(bot, user_id) cada vez que
el jugador llegue a una nueva zona o se registre.
"""
from telegram import BotCommand, BotCommandScopeChat, MenuButtonCommands
import db_helper


def _es_admin(user_id: int) -> bool:
    try:
        import superadmin as _sa
        return _sa._es_admin(user_id)
    except Exception:
        return False

# ── Siempre visibles ──────────────────────────────────────────────────────────

_COMUNES = [
    BotCommand("teclado",         "⌨️ Mostrar/ocultar el teclado del bot"),
    BotCommand("perfil",          "👤 Tu personaje, stats y equipamiento"),
    BotCommand("inventario",      "🎒 Ver y gestionar tu inventario"),
    BotCommand("viajar",          "✈️ Viajar a otra zona del mundo"),
    BotCommand("cancelar_viaje",  "✈️ Cancelar el viaje en curso"),
    BotCommand("mis_titulos",     "🎖️ Tus títulos desbloqueados y activo"),
    BotCommand("misiones",        "📋 Misiones activas y recompensas"),
    BotCommand("logros",          "🏆 Logros y títulos desbloqueados"),
    BotCommand("notificaciones",  "🔔 Bandeja de mensajes pendientes"),
    BotCommand("estado_viaje",    "🗺️ Ver destino y tiempo de llegada"),
    BotCommand("mapa",            "🗺️ Ver tu posición y zonas adyacentes"),
    BotCommand("comandos",        "📋 Ver todos los comandos de esta zona"),
    BotCommand("guia",            "📖 Guía completa del juego"),
    BotCommand("ayuda",           "❓ Ayuda y lista de comandos"),
    BotCommand("corrupcion",      "🌑 Ver el nivel de corrupción del Vacío"),
    BotCommand("mi_codigo",       "🔗 Tu código de invitación"),
    # ── Nuevos sistemas ───────────────────────────────────────────────────────
    BotCommand("login",           "🗓️ Reclamar recompensa de login diario"),
    BotCommand("misiones_hoy",    "📋 Ver misiones diarias rotativas"),
    BotCommand("cooldowns",       "⏱️ Ver todos tus cooldowns con tiempo restante"),
    BotCommand("gchat",           "💬 Enviar mensaje al chat del gremio"),
    BotCommand("gchat_log",       "💬 Ver últimos mensajes del chat de gremio"),
    BotCommand("zona_jugadores",  "👥 Ver jugadores activos en tu zona"),
]

# ── Solo en ciudad ────────────────────────────────────────────────────────────

_CIUDAD = [
    BotCommand("ciudad",          "🏙️ Menú principal: tiendas, crafteo, banco"),
    BotCommand("gremio",          "🏰 Tu gremio, rangos y baúl"),
    BotCommand("tienda",          "🛒 Comprar objetos y equipamiento"),
    BotCommand("banco",           "🏦 Cambiar Oro, Eternium y Créditos"),
    BotCommand("subastas",        "🏷️ Ver y pujar en subastas activas"),
    BotCommand("craftear",        "⚒️ Fabricar armas, armaduras y consumibles"),
    BotCommand("mercado",         "💱 Compraventa directa entre jugadores"),
    BotCommand("duelo",           "⚔️ Retar a duelo PvP a otro jugador"),
    BotCommand("jefe_unirse",     "👹 Unirse a raid de jefe activo"),
    BotCommand("jefe_atacar",     "⚔️ Atacar al jefe durante el raid"),
    BotCommand("jefe_info",       "👹 Ver estado del jefe raid activo"),
    BotCommand("vuelo_rapido",    "⚡ Volar directamente a ciudad (Eternium)"),
    BotCommand("rankings",        "🏆 Rankings de jugadores y gremios"),
    BotCommand("guerra_facciones_estado", "🌍 Estado de la guerra de facciones"),
    BotCommand("bolsa",           "💱 Bolsa de Valores — intercambio de monedas"),
    BotCommand("creditos",        "💵 Depositar USDT → Créditos del Vacío"),
    BotCommand("mis_monturas",    "🐴 Ver y gestionar tus monturas"),
    BotCommand("umbral",          "🌌 Panel del Umbral del Vacío"),
    BotCommand("umbral_donar",    "🏺 Donar a la Caldera del Ritual"),
]

# ── Solo en zona salvaje ──────────────────────────────────────────────────────

_SALVAJE = [
    BotCommand("recolectar",      "⛏️ Recolectar materiales (90 segundos)"),
    BotCommand("investigar",      "🔍 Buscar criaturas y entrar en combate"),
    BotCommand("mazmorra",        "🏰 Crear sala de mazmorra"),
    BotCommand("unirme_mazmorra", "🚪 Unirse a sala de mazmorra existente"),
    BotCommand("jefe_unirse",     "👹 Unirse a raid de jefe activo"),
    BotCommand("jefe_atacar",     "⚔️ Atacar al jefe durante el raid"),
    BotCommand("jefe_info",       "👹 Ver estado del jefe raid activo"),
    BotCommand("desactivar_paz",  "🛡️ Desactivar inmunidad PvP manual"),
]

# ── Zonas de alto nivel (roja y negra) ────────────────────────────────────────

_ZONA_ALTA = [
    BotCommand("guerra_facciones_atacar",    "⚔️ Atacar en guerra de facciones activa"),
    BotCommand("guerra_facciones_defender",  "🛡️ Defender tu facción en la guerra"),
    BotCommand("guerra_facciones_estado",    "📊 Estado de la guerra de facciones"),
    BotCommand("guerra_facciones_ranking",   "🏆 Ranking de la guerra de facciones"),
]

# ── Cuando el jugador está marcado ────────────────────────────────────────────

_MARCADO = [
    BotCommand("pagar_rescate",   "💰 Pagar rescate y librarte de la marca"),
]

# ── Comandos de gremio siempre disponibles ────────────────────────────────────

_GREMIO = [
    BotCommand("gremio_nivel",              "📈 Nivel y bonificaciones del gremio"),
    BotCommand("gremio_subir_nivel",        "⬆️ Subir nivel del gremio"),
    BotCommand("gremio_depositar_material", "📦 Depositar material en banco del gremio"),
    BotCommand("gremio_bonificaciones",     "✨ Ver bonificaciones activas"),
    BotCommand("guerra_gremios_declarar",   "⚔️ Declarar guerra a otro gremio"),
    BotCommand("guerra_gremios_aceptar",    "✅ Aceptar declaración de guerra"),
    BotCommand("guerra_gremios_rechazar",   "❌ Rechazar declaración de guerra"),
    BotCommand("guerra_gremios_duelo",      "🥊 Participar en duelo de guerra"),
    BotCommand("guerra_gremios_ranking",    "🏆 Ranking de la guerra de gremios"),
    BotCommand("guerra_gremios_estado",     "📊 Estado actual de la guerra"),
    BotCommand("guerra_gremios_rendirse",   "🏳️ Rendirse en la guerra de gremios"),
]

# ── Comandos de admin nivel 1 — solo visibles a admins, según permisos ────────
# NOTA: sa_panel y comandos exclusivos de superadmin NO están aquí.

_ADMIN = [
    BotCommand("panel_admin",               "🔐 Panel de administración"),
    BotCommand("panel_debug",               "🐛 Detector de bugs"),
    BotCommand("estado_bot",                "📡 Estado general del bot"),
    # Economía
    BotCommand("dar_oro",                   "🪙 Dar oro a un jugador"),
    BotCommand("quitar_oro",               "🪙 Quitar oro a un jugador"),
    BotCommand("dar_eternium",              "💎 Dar eternium a un jugador"),
    BotCommand("quitar_eternium",           "💎 Quitar eternium"),
    BotCommand("dar_creditos",              "✨ Dar créditos del vacío"),
    BotCommand("quitar_creditos",           "✨ Quitar créditos del vacío"),
    BotCommand("dar_experiencia",           "⭐ Dar XP a un jugador"),
    BotCommand("dar_masivo",               "💰 Dar recompensa masiva"),
    # Objetos y progresión
    BotCommand("dar_objeto",               "🎁 Dar objeto a un jugador"),
    BotCommand("quitar_objeto",            "🗑️ Quitar objeto a un jugador"),
    BotCommand("dar_titulo",               "🎖️ Dar título a un jugador"),
    BotCommand("cambiar_nivel",            "📈 Cambiar nivel de jugador"),
    BotCommand("cambiar_clase",            "⚔️ Cambiar clase de jugador"),
    BotCommand("cambiar_faccion",          "🏛️ Cambiar facción de jugador"),
    BotCommand("set_hp",                   "❤️ Establecer HP de jugador"),
    BotCommand("revivir",                  "❤️ Revivir jugador"),
    # Moderación
    BotCommand("banear",                   "🔨 Banear jugador"),
    BotCommand("desbanear",               "✅ Desbanear jugador"),
    BotCommand("silenciar",               "🔇 Silenciar jugador"),
    BotCommand("desilenciar",             "🔊 Desilenciar jugador"),
    BotCommand("marcar",                  "🎯 Marcar jugador"),
    BotCommand("desmarcar",               "✅ Desmarcar jugador"),
    BotCommand("reset_actividad",          "🔄 Resetear actividad de jugador"),
    BotCommand("resetear_cooldowns",       "⏱️ Resetear cooldowns de jugador"),
    # Inspección
    BotCommand("ver_inventario",           "🎒 Ver inventario de jugador"),
    BotCommand("ver_estadisticas",         "📊 Ver estadísticas de jugador"),
    BotCommand("ver_perfil_completo",      "👤 Ver perfil completo de jugador"),
    BotCommand("lista_jugadores",          "📋 Listar jugadores registrados"),
    # Premios
    BotCommand("premios_entregar",         "🏆 Entregar premio a jugador"),
    BotCommand("panel_premios",            "🏆 Panel de premios"),
    # Jefes Raid
    BotCommand("jefe_iniciar",             "👹 Iniciar convocatoria de jefe raid"),
    BotCommand("jefe_comenzar",            "▶️ Comenzar la batalla del raid"),
    BotCommand("jefe_cancelar",            "❌ Cancelar raid de jefe"),
    BotCommand("jefe_recompensa",          "🎁 Entregar recompensa especial del raid"),
    # Guerras
    BotCommand("guerra_facciones_iniciar",   "🌍 Iniciar guerra de facciones"),
    BotCommand("guerra_facciones_finalizar", "🏁 Finalizar guerra de facciones"),
    BotCommand("admin_guerra_gremios_resolver", "⚔️ Resolver guerra de gremios"),
    BotCommand("panel_guerras",            "⚔️ Panel de guerras"),
    # Paneles
    BotCommand("panel_auto",               "⚙️ Panel de automatizaciones"),
    BotCommand("panel_viajes",             "✈️ Panel de viajes activos"),
    # Mundo y eventos
    BotCommand("cambiar_clima",            "🌤️ Cambiar clima del mundo"),
    BotCommand("iniciar_evento_global",    "🌍 Iniciar evento global"),
    BotCommand("rotar_tienda_creditos",    "🔄 Rotar tienda de créditos"),
    BotCommand("anular_subasta",           "🏷️ Anular subasta activa"),
    # Gremios
    BotCommand("admin_gremio_forzar_nivel", "🏰 Forzar nivel de gremio"),
    # Facciones
    BotCommand("faccion_libre",            "🏛️ Activar selección libre de facción"),
    BotCommand("faccion_auto",             "🏛️ Desactivar selección libre"),
    BotCommand("faccion_estado",           "🏛️ Estado de facciones"),
    # Umbral
    BotCommand("umbral_admin",             "🌑 Panel admin del Umbral del Vacío"),
    BotCommand("umbral_set",               "⚙️ Editar config del Umbral del Vacío"),
    BotCommand("umbral_avanzar",           "⚔️ Avanzar ronda del combate del Umbral"),
]

# ── Lista organizada para el superadmin (todos los comandos, max 100) ─────────

_SUPERADMIN_TODO = [
    # 🔑 Control superadmin
    BotCommand("sa_panel",                   "👑 Panel superadmin completo"),
    BotCommand("panel_admin",                "🔐 Panel de administración"),
    BotCommand("panel_debug",                "🐛 Detector de bugs"),
    BotCommand("estado_bot",                 "📡 Estado general del bot"),
    BotCommand("balance_global",             "📊 Balance económico global"),
    BotCommand("sa_numeros",                 "📊 Estadísticas numéricas globales"),
    BotCommand("superadmin_crear_admin",     "👑 Crear nuevo admin"),
    BotCommand("superadmin_lista_admins",    "📋 Lista de admins registrados"),
    BotCommand("superadmin_quitar_admin",    "🗑️ Quitar admin"),
    BotCommand("superadmin_permisos_cmd",    "🔑 Gestionar permisos de comandos"),
    # 🪙 Economía jugadores
    BotCommand("dar_oro",                    "🪙 Dar oro"),
    BotCommand("quitar_oro",                "🪙 Quitar oro"),
    BotCommand("dar_eternium",               "💎 Dar eternium"),
    BotCommand("quitar_eternium",            "💎 Quitar eternium"),
    BotCommand("dar_creditos",               "✨ Dar créditos del vacío"),
    BotCommand("quitar_creditos",            "✨ Quitar créditos del vacío"),
    BotCommand("dar_experiencia",            "⭐ Dar XP"),
    BotCommand("dar_masivo",                "💰 Dar recompensa masiva"),
    BotCommand("admin_creditar",             "💳 Creditar créditos manualmente"),
    # 🎁 Objetos y progresión
    BotCommand("dar_objeto",                "🎁 Dar objeto"),
    BotCommand("quitar_objeto",             "🗑️ Quitar objeto"),
    BotCommand("dar_titulo",                "🎖️ Dar título"),
    BotCommand("cambiar_nivel",             "📈 Cambiar nivel"),
    BotCommand("cambiar_clase",             "⚔️ Cambiar clase"),
    BotCommand("cambiar_faccion",           "🏛️ Cambiar facción"),
    BotCommand("set_hp",                    "❤️ Establecer HP"),
    BotCommand("revivir",                   "❤️ Revivir jugador"),
    BotCommand("modificar_stamina",         "⚡ Modificar stamina"),
    # 🔨 Moderación
    BotCommand("banear",                    "🔨 Banear jugador"),
    BotCommand("desbanear",                "✅ Desbanear jugador"),
    BotCommand("silenciar",                "🔇 Silenciar jugador"),
    BotCommand("desilenciar",              "🔊 Desilenciar jugador"),
    BotCommand("marcar",                   "🎯 Marcar jugador"),
    BotCommand("desmarcar",               "✅ Desmarcar jugador"),
    BotCommand("reset_actividad",          "🔄 Resetear actividad"),
    BotCommand("limpiar_penalizaciones",   "✅ Limpiar penalizaciones"),
    BotCommand("limpiar_actividad",        "🔄 Limpiar actividad"),
    BotCommand("resetear_cooldowns",       "⏱️ Resetear cooldowns"),
    # 🔍 Inspección
    BotCommand("lista_jugadores",          "📋 Listar jugadores"),
    BotCommand("ver_perfil_completo",      "👤 Ver perfil completo"),
    BotCommand("ver_inventario",           "🎒 Ver inventario de jugador"),
    BotCommand("ver_estadisticas",         "📊 Ver estadísticas"),
    # 🏆 Premios
    BotCommand("premios_entregar",         "🏆 Entregar premio"),
    BotCommand("panel_premios",            "🏆 Panel de premios"),
    BotCommand("premios_buscar",           "🔍 Buscar premios"),
    # 👹 Jefes Raid
    BotCommand("jefe_iniciar",             "👹 Iniciar convocatoria de jefe raid"),
    BotCommand("jefe_comenzar",            "▶️ Comenzar batalla del raid"),
    BotCommand("jefe_cancelar",            "❌ Cancelar raid de jefe"),
    BotCommand("jefe_recompensa",          "🎁 Entregar recompensa especial del raid"),
    # ⚔️ Guerras
    BotCommand("guerra_facciones_iniciar",   "🌍 Iniciar guerra de facciones"),
    BotCommand("guerra_facciones_finalizar", "🏁 Finalizar guerra de facciones"),
    BotCommand("guerra_facciones_estado",    "📊 Estado de la guerra de facciones"),
    BotCommand("guerra_facciones_ranking",   "🏆 Ranking guerra de facciones"),
    BotCommand("admin_guerra_gremios_resolver", "⚔️ Resolver guerra de gremios"),
    BotCommand("guerra_limpiar",           "🗑️ Limpiar datos de guerra"),
    BotCommand("panel_guerras",            "⚔️ Panel de guerras"),
    # 🏰 Gremios
    BotCommand("admin_gremio_forzar_nivel", "🏰 Forzar nivel de gremio"),
    BotCommand("panel_gremio_niveles",     "🏰 Panel de niveles de gremio"),
    # 🌍 Mundo y eventos
    BotCommand("cambiar_clima",            "🌤️ Cambiar clima del mundo"),
    BotCommand("iniciar_evento_global",    "🌍 Iniciar evento global"),
    BotCommand("ajuste_global",            "⚙️ Ajuste global de parámetros"),
    BotCommand("rotar_tienda_creditos",    "🔄 Rotar tienda de créditos"),
    BotCommand("anular_subasta",           "🏷️ Anular subasta activa"),
    BotCommand("bolsa_admin_tasa",         "💱 Ajustar tasas de la bolsa"),
    # ⚙️ Paneles admin
    BotCommand("panel_auto",               "⚙️ Panel de automatizaciones"),
    BotCommand("panel_viajes",             "✈️ Panel de viajes activos"),
    BotCommand("panel_peaje",              "⛔ Panel de peajes"),
    BotCommand("panel_economia",           "💰 Panel de economía"),
    # 🏛️ Facciones y umbral
    BotCommand("faccion_libre",            "🏛️ Activar selección libre de facción"),
    BotCommand("faccion_auto",             "🏛️ Desactivar selección libre"),
    BotCommand("faccion_estado",           "🏛️ Estado de facciones"),
    BotCommand("umbral_admin",             "🌑 Panel admin del Umbral del Vacío"),
    BotCommand("umbral_set",               "⚙️ Configurar Umbral del Vacío"),
    BotCommand("umbral_avanzar",           "⚔️ Avanzar ronda del Umbral"),
    # 🌩️ Modo dios y superadmin exclusivos
    BotCommand("dios_activar",             "⚡ Activar modo dios"),
    BotCommand("dios_desactivar",          "❌ Desactivar modo dios"),
    BotCommand("dios_max_stats",           "💪 Stats máximos modo dios"),
    BotCommand("broadcast_todos",          "📢 Broadcast a todos los jugadores"),
    BotCommand("broadcast_activos",        "📢 Broadcast a jugadores activos"),
    BotCommand("admin_solicitudes_creditos", "💳 Ver solicitudes de créditos"),
    # 👤 Comandos propios del superadmin como jugador
    BotCommand("perfil",                   "👤 Mi personaje"),
    BotCommand("inventario",               "🎒 Mi inventario"),
    BotCommand("mapa",                     "🗺️ Mi posición"),
    BotCommand("rankings",                 "🏆 Rankings del juego"),
    BotCommand("guia",                     "📖 Guía del juego"),
    # ── Nuevos sistemas (visibles también al superadmin) ─────────────────────
    BotCommand("login",                    "🗓️ Login diario con racha"),
    BotCommand("misiones_hoy",             "📋 Misiones diarias del día"),
    BotCommand("cooldowns",                "⏱️ Ver cooldowns activos"),
    BotCommand("gchat",                    "💬 Chat de gremio"),
    BotCommand("gchat_log",                "💬 Historial chat de gremio"),
    BotCommand("zona_jugadores",           "👥 Jugadores activos en zona"),
]

# ─────────────────────────────────────────────────────────────────────────────

_GUERRA_PENDIENTE = [
    BotCommand("guerra_facciones_atacar",   "⚔️ Registrar tu ataque en la guerra"),
    BotCommand("guerra_facciones_defender", "🛡️ Registrar tu defensa en la guerra"),
    BotCommand("saltar_guerra",             "⏭️ No participar en esta guerra"),
    BotCommand("guerra_facciones_estado",   "📊 Marcador provisional de la guerra"),
]

_GUERRA_YA_ACTUO = [
    BotCommand("inventario",               "🎒 Ver y gestionar tu inventario"),
    BotCommand("perfil",                   "👤 Tu personaje, stats y equipamiento"),
    BotCommand("guia",                     "📖 Guía completa del juego"),
    BotCommand("notificaciones",           "🔔 Bandeja de mensajes pendientes"),
    BotCommand("guerra_facciones_estado",  "📊 Marcador provisional de la guerra"),
]


def _construir_lista_comandos(user_id: int) -> list:
    """
    Devuelve la lista de BotCommand correspondiente a la zona actual
    del jugador (sin tocar la API de Telegram).

    Niveles:
    - Superadmin → _SUPERADMIN_TODO (lista fija organizada, 85 cmds)
    - Admin nivel 1 → comandos jugador + comandos de admin autorizados
    - Jugador normal → comandos según zona (ciudad / salvaje / etc.)
    """
    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        return []

    # ── Superadmin: lista organizada completa ─────────────────────────────
    _sa = None
    try:
        import superadmin as _sa
        if _sa._es_superadmin(user_id):
            return list(_SUPERADMIN_TODO)[:100]
    except Exception:
        _sa = None

    # ── Modo guerra activa ────────────────────────────────────────────────
    try:
        import guerra_facciones as _gf
        if _gf.hay_guerra_activa():
            if _gf.jugador_ya_actuo_publico(user_id):
                base = list(_GUERRA_YA_ACTUO)
            else:
                base = list(_GUERRA_PENDIENTE)
            if _es_admin(user_id):
                try:
                    if _sa is None:
                        import superadmin as _sa
                    cmds_set = _sa.obtener_cmds_admin_permitidos(user_id)
                    if cmds_set is None:
                        base += _ADMIN
                    else:
                        permitidos = [c for c in _ADMIN if c.command in cmds_set]
                        panel = next((c for c in _ADMIN if c.command == "panel_admin"), None)
                        if panel and not any(c.command == "panel_admin" for c in permitidos):
                            permitidos.insert(0, panel)
                        base += permitidos
                except Exception:
                    base += _ADMIN
            return base[:100]
    except Exception:
        pass

    zona_actual = jug.get("zona_actual", "") or ""
    marcado = db_helper.esta_marcado(user_id)

    tipo_zona = "ciudad"
    color = "azul"
    try:
        from datos_zona import ZONAS
        zona_info = next((z for z in ZONAS if z["nombre"] == zona_actual), None)
        if zona_info:
            tipo_zona = zona_info.get("tipo", "salvaje")
            color     = zona_info.get("color", "azul")
    except Exception:
        pass

    comandos = list(_COMUNES)
    if tipo_zona == "ciudad":
        comandos += _CIUDAD
        comandos += _GREMIO
    else:
        comandos += _SALVAJE
    if color in ("roja", "negra"):
        comandos += _ZONA_ALTA
    if marcado:
        comandos += _MARCADO

    # ── Comandos de admin nivel 1 (solo sus permisos) ─────────────────────
    if _es_admin(user_id):
        try:
            cmds_set = _sa.obtener_cmds_admin_permitidos(user_id)
            if cmds_set is None:
                # sin restricción (no debería ocurrir para nivel 1, pero cubrimos el caso)
                comandos += _ADMIN
            else:
                permitidos = [c for c in _ADMIN if c.command in cmds_set]
                # Siempre garantizar panel_admin como acceso básico
                panel = next((c for c in _ADMIN if c.command == "panel_admin"), None)
                if panel and not any(c.command == "panel_admin" for c in permitidos):
                    permitidos.insert(0, panel)
                comandos += permitidos
        except Exception:
            comandos += _ADMIN

    vistos: set = set()
    unicos = []
    for cmd in comandos:
        if cmd.command not in vistos:
            vistos.add(cmd.command)
            unicos.append(cmd)
    return unicos[:100]


async def _preparar_comandos_sin_toggle(bot, user_id: int):
    """
    Sube la lista de comandos al servidor de Telegram (delete+set) sin
    disparar el toggle visual Default→Commands.
    Llamar ANTES de enviar el mensaje de llegada.
    """
    try:
        unicos = _construir_lista_comandos(user_id)
        if not unicos:
            return
        try:
            await bot.delete_my_commands(scope=BotCommandScopeChat(chat_id=user_id))
        except Exception:
            pass
        await bot.set_my_commands(unicos, scope=BotCommandScopeChat(chat_id=user_id))
    except Exception:
        pass


async def _disparar_toggle_menu(bot, user_id: int):
    """
    Ciclos Default→Commands para que el cliente Telegram invalide
    su caché del menú "/".  Llamar DESPUÉS de enviar el mensaje de llegada y
    el teclado.  El sleep inicial da tiempo a que Telegram propague
    set_my_commands antes de que el cliente reciba el toggle.
    """
    import asyncio as _asyncio_zc
    from telegram import MenuButtonDefault
    # Re-subir comandos justo antes del toggle para máxima coherencia
    await _preparar_comandos_sin_toggle(bot, user_id)
    await _asyncio_zc.sleep(2.0)          # propagación del set_my_commands
    for _ in range(3):                     # triple ciclo para mayor fiabilidad
        try:
            await bot.set_chat_menu_button(chat_id=user_id, menu_button=MenuButtonDefault())
        except Exception:
            pass
        await _asyncio_zc.sleep(0.8)
        try:
            await bot.set_chat_menu_button(chat_id=user_id, menu_button=MenuButtonCommands())
        except Exception:
            pass
        await _asyncio_zc.sleep(0.8)


async def actualizar_comandos_jugador(bot, user_id: int):
    """
    Lee la zona actual del jugador y actualiza la lista de comandos
    que le aparece al escribir "/" en el chat del bot.
    Durante una guerra activa, el menú cambia según si el jugador ya actuó o no.
    """
    try:
        await _preparar_comandos_sin_toggle(bot, user_id)
        await _disparar_toggle_menu(bot, user_id)
    except Exception:
        pass


async def sincronizar_todos_jugadores(bot):
    """
    Actualiza la lista "/" para todos los jugadores registrados.
    Llamar una vez al arrancar el bot.
    """
    import asyncio as _asyncio
    jugadores = db_helper.obtener_todos_jugadores()
    for jug in jugadores:
        await actualizar_comandos_jugador(bot, jug["user_id"])
        await _asyncio.sleep(0.05)

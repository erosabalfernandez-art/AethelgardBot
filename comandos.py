"""
comandos.py — Menú contextual de comandos disponibles según la zona del jugador.
/comandos  →  muestra un menú inline con todo lo que puedes hacer aquí.
/destrabar →  limpia estados bloqueados (combate, mazmorra, viaje atascados).
/menu      →  muestra u oculta el menú rápido inferior.
"""

import sqlite3 as _sqlite3
import json as _json
import time as _time

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler

import db_helper

# ─── colores de zona ────────────────────────────────────────────────────────

def _color_zona(zona_nombre: str) -> str:
    """Devuelve el color de la zona o 'azul' por defecto."""
    try:
        from viajes import _obtener_destinos
        for z in _obtener_destinos():
            if z["nombre"] == zona_nombre:
                return z.get("color", "azul")
    except Exception:
        pass
    return "azul"

def _tipo_zona(zona_nombre: str) -> str:
    """Devuelve 'ciudad' o 'salvaje'."""
    try:
        from viajes import _obtener_destinos
        for z in _obtener_destinos():
            if z["nombre"] == zona_nombre:
                return z.get("tipo", "salvaje")
    except Exception:
        pass
    return "salvaje"

# ─── icono de zona ────────────────────────────────────────────────────────────

EMOJI_COLOR = {
    "azul":     "🔵",
    "amarilla": "🟡",
    "roja":     "🔴",
    "negra":    "⚫",
}

NIVEL_MIN_COLOR = {
    "azul":     1,
    "amarilla": 5,
    "roja":     10,
    "negra":    15,
}

# ─── valores dinámicos ────────────────────────────────────────────────────────

def _seg_recoleccion() -> int:
    try:
        return int(db_helper.obtener_config("recoleccion_duracion_seg", "90"))
    except Exception:
        return 90

def _seg_investigacion() -> int:
    try:
        return int(db_helper.obtener_config("investigacion_duracion_seg", "90"))
    except Exception:
        return 90

def _min_meditacion() -> int:
    try:
        import sistema_paz as _sp
        import inspect, re
        src = inspect.getsource(_sp)
        m = re.search(r"timedelta\(minutes=(\d+)\)", src)
        return int(m.group(1)) if m else 5
    except Exception:
        return 5

def _seg_jefe_cooldown() -> int:
    try:
        import jefes as _j
        return _j.COOLDOWN_ATAQUE
    except Exception:
        return 30

def _pct_oro_derrota() -> int:
    try:
        import combate as _c
        return int(getattr(_c, "DERROTA_ORO_PORCENTAJE", 0.15) * 100)
    except Exception:
        return 15

def _pct_hp_derrota() -> int:
    try:
        import combate as _c
        return int(getattr(_c, "DERROTA_HP_PORCENTAJE", 0.05) * 100)
    except Exception:
        return 5

# ─── construcción del texto ────────────────────────────────────────────────────

def _construir_texto(jug: dict, ubicacion: str, color: str, marcado: bool) -> str:
    zona_nombre = jug.get("zona_actual", "Zona desconocida")
    nivel = jug.get("nivel", 1)
    emoji = EMOJI_COLOR.get(color, "🔵")

    seg_rec  = _seg_recoleccion()
    seg_inv  = _seg_investigacion()
    min_med  = _min_meditacion()
    cd_jefe  = _seg_jefe_cooldown()
    pct_oro  = _pct_oro_derrota()
    pct_hp   = _pct_hp_derrota()

    if ubicacion == "ciudad":
        icono_ubi = "🏙️ Ciudad"
    else:
        icono_ubi = f"🌲 Zona salvaje {emoji}"

    lineas = [
        f"📍 *{zona_nombre}* — {icono_ubi}",
        f"Nivel {nivel} | Color: {color.capitalize()}",
        "",
    ]

    # ── Siempre disponibles ───────────────────────────────────────────────────
    lineas += [
        "━━━ *SIEMPRE DISPONIBLES* ━━━",
        "`/perfil`           — Tu personaje, stats y equipamiento",
        "`/inventario`       — Objetos y equipamiento",
        "`/cofre`            — Cofre personal (almacén extra)",
        "`/misiones`         — Misiones de progreso",
        "`/logros`           — Logros desbloqueados",
        "`/mis_titulos`      — Tus títulos y cuál tienes activo",
        "`/membresia`        — Ver tu membresía y sus beneficios",
        "`/guia`             — Guía completa del juego",
        "`/menu`             — Mostrar u ocultar el menú rápido inferior",
        "`/viajar`           — Viajar a otra zona",
        "`/estado_viaje`     — Ver destino y tiempo restante",
        "`/cancelar_viaje`   — Cancelar viaje en curso",
        "`/corrupcion`       — Nivel de corrupción del Vacío",
        "`/notificaciones`   — Bandeja de mensajes pendientes",
        "`/mi_codigo`        — Tu código de invitación de recluta",
        "`/destrabar`        — ⚠️ Limpiar si estás atascado",
        "",
    ]

    # ── Ciudad ────────────────────────────────────────────────────────────────
    if ubicacion == "ciudad":
        lineas += [
            "━━━ *EN CIUDAD* ━━━",
            "`/ciudad`         — Menú principal (tiendas, crafteo, banco…)",
        "  🔄 *Actualizar menú:* primer botón del menú inferior — sincroniza zona/guerra",
        "  ⚙️ *Editar menú:* personaliza qué botones aparecen en cada menú (solo en ciudad)",
            "  🛠️ *Servicios:* crafteo · encantar · herrero · taberna",
            "  🛒 *Comercio:* tienda · subastas · mercado P2P",
            "  🏦 *Banco:* cambio de monedas (Oro ↔ Eternium)",
            "  🐎 *Montura:* reduce tiempo de viaje",
            "`/vuelo_rapido`   — Volar a ciudad instantáneo (cuesta Eternium)",
            "`/jefe_info`      — Ver estado del raid de jefe activo",
            "`/rankings`       — Rankings de jugadores y gremios",
            "`/bolsa`          — Bolsa de Valores (intercambio de monedas)",
            "`/creditos`       — Depositar USDT → Créditos del Vacío",
            "`/mis_monturas`   — Ver y gestionar tus monturas",
            "`/umbral`         — Panel del Umbral del Vacío",
            "`/umbral_donar`   — Donar a la Caldera del Ritual",
            "",
        ]

    # ── Zona salvaje ──────────────────────────────────────────────────────────
    if ubicacion == "salvaje":
        lineas += [
            "━━━ *EN ZONA SALVAJE* ━━━",
            f"`/recolectar`         — Recolectar materiales ({seg_rec}s)",
            f"`/investigar`         — Buscar criaturas y combatir ({seg_inv}s)",
            f"`/meditar`            — Activar inmunidad PvP temporal ({min_med} min)",
            "`/desactivar_paz`     — Desactivar inmunidad PvP manual",
            "`/auto_recoleccion`   — Panel de recolección automática (Membresía)",
            "`/mazmorra`           — Crear sala de mazmorra",
            "`/unirme_mazmorra`    — Unirse a sala existente",
            "`/jefe_info`          — Ver estado del raid de jefe activo",
            "",
        ]

    # ── Combate ───────────────────────────────────────────────────────────────
    lineas += [
        "━━━ *COMBATE* ━━━",
        "`/duelo @usuario`    — Retar a duelo PvP",
        f"`/jefe_unirse`       — Unirse a raid de jefe (si hay uno activo)",
        f"`/jefe_atacar`       — Atacar al jefe (cooldown {cd_jefe}s)",
        f"💀 Derrota PvE: -{pct_oro}% oro · HP baja al {pct_hp}%",
    ]
    if color in ("roja", "negra") or ubicacion == "ciudad":
        lineas += [
            "`/guerra_facciones_atacar`   — Atacar en guerra de facciones",
            "`/guerra_facciones_defender` — Defender tu facción",
            "`/guerra_facciones_estado`   — Ver estado de la guerra",
            "`/guerra_facciones_ranking`  — Ranking de la guerra",
        ]
    lineas.append("")

    # ── Gremio ────────────────────────────────────────────────────────────────
    lineas += [
        "━━━ *GREMIO* ━━━",
        "`/gremio`                    — Panel de tu gremio",
        "`/gremio_nivel`              — Nivel y bonificaciones",
        "`/gremio_subir_nivel`        — Subir el nivel del gremio",
        "`/gremio_bonificaciones`     — Ver bonificaciones activas",
        "`/gremio_depositar_material` — Depositar material en el banco del gremio",
        "`/depositar_baul`            — Depositar item en el baúl compartido",
        "`/tomar_baul`                — Tomar item del baúl compartido",
        "`/invitar_gremio @u`         — Invitar jugador (Oficiales+)",
        "`/guerra_gremios_declarar`   — Declarar guerra a otro gremio",
        "`/guerra_gremios_aceptar`    — Aceptar declaración de guerra",
        "`/guerra_gremios_rechazar`   — Rechazar declaración de guerra",
        "`/guerra_gremios_duelo`      — Participar en duelo de guerra",
        "`/guerra_gremios_ranking`    — Ranking de la guerra de gremios",
        "`/guerra_gremios_estado`     — Ver estado de la guerra",
        "`/guerra_gremios_rendirse`   — Rendirse en la guerra",
        "",
    ]

    # ── Urgente ───────────────────────────────────────────────────────────────
    if marcado:
        lineas += [
            "━━━ *⚠️ ESTAS MARCADO* ━━━",
            "`/pagar_rescate` — Paga rescate para poder moverte",
            "",
        ]

    # ── Viaje ────────────────────────────────────────────────────────────────
    lineas += [
        "━━━ *VIAJE* ━━━",
        "`/mapa`           — Ver tu posición y zonas adyacentes",
        "`/estado_viaje`   — Ver destino y tiempo restante",
        "`/cancelar_viaje` — Cancelar viaje en curso",
        "`/vuelo_rapido`   — Viaje instantáneo (cuesta Eternium)",
    ]

    return "\n".join(lineas)

# ─── teclado inline ──────────────────────────────────────────────────────────

def _construir_teclado(ubicacion: str, color: str, marcado: bool):
    kb = []

    if ubicacion == "ciudad":
        kb.append([InlineKeyboardButton("🏙️ Ir a Ciudad",    callback_data="ciudad_menu_principal")])
        kb.append([
            InlineKeyboardButton("🛒 Comercio",  callback_data="submenu_comercio"),
            InlineKeyboardButton("🛠️ Servicios", callback_data="submenu_servicios"),
        ])
        kb.append([
            InlineKeyboardButton("🏰 Gremio",    callback_data="submenu_gremio"),
            InlineKeyboardButton("⚔️ Combate",   callback_data="submenu_combate"),
        ])
        kb.append([InlineKeyboardButton("🌀 Mazmorras",  callback_data="submenu_mazmorras")])
    else:
        emoji = EMOJI_COLOR.get(color, "🔵")
        cb_maz = f"cb_mazmorra_{color}"
        kb.append([
            InlineKeyboardButton(f"{emoji} Mazmorra {color.capitalize()}", callback_data=cb_maz),
        ])

    kb.append([
        InlineKeyboardButton("🗺️ Viajar",      callback_data="submenu_contenido"),
        InlineKeyboardButton("🏰 Gremio",       callback_data="submenu_gremio"),
    ])

    if marcado:
        kb.append([InlineKeyboardButton("💀 Pagar rescate → /pagar_rescate", callback_data="cmd_noop")])

    kb.append([InlineKeyboardButton("❌ Cerrar", callback_data="cmd_cerrar_comandos")])
    return kb

# ─── handler ────────────────────────────────────────────────────────────────

async def cmd_comandos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    jug = db_helper.obtener_jugador(user_id)

    if not jug:
        await update.effective_message.reply_text(
            "❌ No tienes personaje todavía. Usa /start para crear uno."
        )
        return

    zona_nombre = jug.get("zona_actual", "Zona desconocida")
    ubicacion   = jug.get("ubicacion", "salvaje")
    color       = _color_zona(zona_nombre)

    # Si ubicacion no está bien seteado, inferir del tipo de zona
    if not ubicacion or ubicacion not in ("ciudad", "salvaje"):
        ubicacion = _tipo_zona(zona_nombre)

    marcado = db_helper.esta_marcado(user_id)

    texto   = _construir_texto(jug, ubicacion, color, marcado)
    teclado = _construir_teclado(ubicacion, color, marcado)

    await update.effective_message.reply_text(
        texto,
        reply_markup=InlineKeyboardMarkup(teclado),
        parse_mode="Markdown",
    )


async def cb_cerrar_comandos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("📋 Menú de comandos cerrado. Escribe /comandos para volver a abrirlo.")


async def cb_noop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer("Escribe ese comando en el chat.")


# ─── /destrabar ──────────────────────────────────────────────────────────────

_DESTRABAR_CD: dict = {}   # user_id → timestamp último uso


def _detectar_bloqueos(user_id: int, jug: dict, context) -> dict:
    """Devuelve {'bloqueado': bool, 'detalles': [str]}."""
    from datetime import datetime as _dt
    detalles = []

    actividad = jug.get("actividad_actual")
    if actividad:
        detalles.append(f"Actividad activa: *{actividad}*")

    viaje_hasta = jug.get("viaje_hasta")
    if viaje_hasta:
        try:
            if _dt.fromisoformat(str(viaje_hasta)) > _dt.now():
                detalles.append(f"Viaje en curso sin terminar")
        except Exception:
            detalles.append("Viaje residual detectado")

    if context.user_data.get("viaje_pendiente"):
        detalles.append("Viaje pendiente en memoria")
    if context.user_data.get("duelo_pendiente"):
        detalles.append("Duelo pendiente en memoria")

    try:
        conn = _sqlite3.connect(db_helper.DB_PATH)
        c = conn.cursor()
        c.execute(
            "SELECT mazmorra_id FROM mazmorras_activas "
            "WHERE (lider_id = ? OR jugadores LIKE ?) AND estado IN ('formando','en_curso')",
            (user_id, f'%{user_id}%')
        )
        row = c.fetchone()
        conn.close()
        if row:
            detalles.append(f"Atrapado en mazmorra #{row[0]}")
    except Exception:
        pass

    try:
        conn = _sqlite3.connect(db_helper.DB_PATH)
        c = conn.cursor()
        c.execute(
            "SELECT id FROM partys WHERE lider_id = ? OR miembros LIKE ?",
            (user_id, f'%{user_id}%')
        )
        row = c.fetchone()
        conn.close()
        if row:
            detalles.append(f"Enganchado en grupo/party #{row[0]}")
    except Exception:
        pass

    try:
        import combate as _combate
        for cid, cb in list(_combate.combates_activos.items()):
            participantes = set()
            participantes.add(cb.get("atacante_id"))
            participantes.add(cb.get("defensor_id"))
            participantes.update(cb.get("jugadores", {}).keys())
            participantes.update(str(k) for k in cb.get("jugadores", {}).keys())
            if user_id in participantes or str(user_id) in participantes:
                detalles.append(f"Combate #{cid} activo en memoria")
                break
    except Exception:
        pass

    return {"bloqueado": len(detalles) > 0, "detalles": detalles}


def _ejecutar_destrabar(user_id: int, context) -> list:
    """Limpia todos los estados bloqueados. Devuelve lista de lo que se limpió."""
    from datetime import datetime as _dt
    limpiados = []

    # 1. actividad_actual + viaje_hasta en jugadores
    try:
        conn = _sqlite3.connect(db_helper.DB_PATH)
        c = conn.cursor()
        jug = db_helper.obtener_jugador(user_id)
        if jug:
            actividad = jug.get("actividad_actual")
            viaje = jug.get("viaje_hasta")
            cambios = []
            if actividad:
                cambios.append("actividad_actual = NULL")
                cambios.append("actividad_expira = NULL")
                limpiados.append(f"Actividad '{actividad}' desbloqueada")
            if viaje:
                try:
                    if _dt.fromisoformat(str(viaje)) > _dt.now():
                        limpiados.append("Viaje cancelado")
                except Exception:
                    limpiados.append("Viaje residual eliminado")
                cambios.append("viaje_hasta = NULL")
                cambios.append("viaje_destino_id = NULL")
            if cambios:
                c.execute(
                    f"UPDATE jugadores SET {', '.join(cambios)} WHERE user_id = ?",
                    (user_id,)
                )
        conn.commit()
        conn.close()
    except Exception as ex:
        limpiados.append(f"Aviso DB actividad: {ex}")

    # 2. Mazmorras activas
    try:
        conn = _sqlite3.connect(db_helper.DB_PATH)
        c = conn.cursor()
        c.execute(
            "SELECT mazmorra_id, lider_id, jugadores FROM mazmorras_activas "
            "WHERE (lider_id = ? OR jugadores LIKE ?) AND estado IN ('formando','en_curso')",
            (user_id, f'%{user_id}%')
        )
        rows = c.fetchall()
        for (maz_id, lider_id, jugadores_json) in rows:
            if lider_id == user_id:
                c.execute("DELETE FROM mazmorras_activas WHERE mazmorra_id = ?", (maz_id,))
                limpiados.append(f"Mazmorra #{maz_id} disuelta (eras el líder)")
            else:
                try:
                    jgs = _json.loads(jugadores_json or "[]")
                    jgs = [j for j in jgs if j != user_id and j != str(user_id)]
                    c.execute("UPDATE mazmorras_activas SET jugadores = ? WHERE mazmorra_id = ?",
                              (_json.dumps(jgs), maz_id))
                    limpiados.append(f"Saliste de la mazmorra #{maz_id}")
                except Exception:
                    pass
        conn.commit()
        conn.close()
    except Exception:
        pass

    # 3. Partys / grupos
    try:
        conn = _sqlite3.connect(db_helper.DB_PATH)
        c = conn.cursor()
        c.execute(
            "SELECT id, lider_id, miembros FROM partys "
            "WHERE lider_id = ? OR miembros LIKE ?",
            (user_id, f'%{user_id}%')
        )
        rows = c.fetchall()
        for (pid, lider_id, miembros_json) in rows:
            if lider_id == user_id:
                c.execute("DELETE FROM partys WHERE id = ?", (pid,))
                limpiados.append(f"Grupo #{pid} disuelto (eras el líder)")
            else:
                try:
                    mbs = _json.loads(miembros_json or "[]")
                    mbs = [m for m in mbs if m != user_id and m != str(user_id)]
                    c.execute("UPDATE partys SET miembros = ? WHERE id = ?",
                              (_json.dumps(mbs), pid))
                    limpiados.append(f"Saliste del grupo #{pid}")
                except Exception:
                    pass
        conn.commit()
        conn.close()
    except Exception:
        pass

    # 4. Combates en memoria (combate.py)
    try:
        import combate as _combate
        ids_borrar = []
        for cid, cb in list(_combate.combates_activos.items()):
            participantes = {cb.get("atacante_id"), cb.get("defensor_id")}
            participantes.update(cb.get("jugadores", {}).keys())
            participantes.update(str(k) for k in cb.get("jugadores", {}).keys())
            if user_id in participantes or str(user_id) in participantes:
                ids_borrar.append(cid)
        for cid in ids_borrar:
            _combate.combates_activos.pop(cid, None)
            limpiados.append(f"Combate activo #{cid} liberado")
    except Exception:
        pass

    # 5. user_data en memoria
    for clave in ("viaje_pendiente", "duelo_pendiente", "peaje_pendiente"):
        if context.user_data.pop(clave, None) is not None:
            limpiados.append(f"Estado '{clave}' limpiado")

    return limpiados


async def cmd_destrabar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Detecta bloqueos del jugador y ofrece limpiarlos."""
    user_id = update.effective_user.id
    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        await update.effective_message.reply_text("❌ No tienes personaje. Usa /start para crear uno.")
        return

    ahora = _time.time()
    ultimo = _DESTRABAR_CD.get(user_id, 0)
    if ahora - ultimo < 120:
        restante = int(120 - (ahora - ultimo))
        await update.effective_message.reply_text(
            f"⏳ Espera {restante}s antes de volver a usar /destrabar."
        )
        return

    estado = _detectar_bloqueos(user_id, jug, context)

    if not estado["bloqueado"]:
        await update.effective_message.reply_text(
            "✅ No estás trabado en ninguna actividad activa.\n\n"
            "Si un comando no responde, espera 10 segundos y vuelve a intentarlo.\n"
            "Si el problema persiste, contacta a un admin."
        )
        return

    lineas = ["⚠️ *Estado bloqueado detectado:*\n"]
    for item in estado["detalles"]:
        lineas.append(f"• {item}")
    lineas += [
        "",
        "¿Confirmas limpiar todos estos estados?",
        "_⚠️ El estado 'marcado' (deuda de rescate) NO se elimina._"
    ]

    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Sí, destrabarme", callback_data="destrabar_ok"),
        InlineKeyboardButton("❌ Cancelar",         callback_data="destrabar_cancel"),
    ]])
    await update.effective_message.reply_text(
        "\n".join(lineas), parse_mode="Markdown", reply_markup=kb
    )


async def cb_destrabar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback de confirmación del destrabar."""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    if query.data == "destrabar_cancel":
        await query.edit_message_text("❌ Operación cancelada. Sigue usando el bot con normalidad.")
        return

    _DESTRABAR_CD[user_id] = _time.time()
    limpiados = _ejecutar_destrabar(user_id, context)

    if limpiados:
        resumen = "\n".join(f"  ✅ {item}" for item in limpiados)
        texto = (
            f"🔓 *¡Desbloqueado!*\n\n"
            f"Se limpió lo siguiente:\n{resumen}\n\n"
            f"Ya puedes unirte a mazmorras, raids, viajar y combatir con normalidad."
        )
    else:
        texto = (
            "✅ No había nada que limpiar en este momento.\n"
            "Si sigues con problemas, contacta a un admin."
        )

    await query.edit_message_text(texto, parse_mode="Markdown")


# ─── registro ────────────────────────────────────────────────────────────────

def registrar_handlers(app):
    app.add_handler(CommandHandler("comandos",  cmd_comandos))
    app.add_handler(CommandHandler("ayuda",     cmd_comandos))
    app.add_handler(CommandHandler("destrabar", cmd_destrabar))
    app.add_handler(CallbackQueryHandler(cb_cerrar_comandos, pattern="^cmd_cerrar_comandos$"))
    app.add_handler(CallbackQueryHandler(cb_noop,            pattern="^cmd_noop$"))
    app.add_handler(CallbackQueryHandler(cb_destrabar,       pattern="^destrabar_"))

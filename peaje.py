# peaje.py
# Sistema de peaje para entrar a ciudades de facción contraria.
# Integrado con el sistema de viajes (viajes.py).

import random
import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, CommandHandler, CallbackQueryHandler,
    ConversationHandler, MessageHandler, filters,
)

import economia
import db_helper
from datos_zona import ZONAS
from combate import iniciar_combate, COMBATE_PEAJE
from viajes import (
    reanudar_viaje, _obtener_destino, _iniciar_viaje_directo,
    _obtener_montura_activa, _agregar_montura_inventario, _equipar_montura
)

DB_PATH = "aethelgard.db"

def _esc_md(s: str) -> str:
    return str(s).replace("_", "\\_").replace("*", "\\*").replace("`", "\\`").replace("[", "\\[")

# ==================== CONSTANTES ====================
MULTIPLICADOR_HORARIO_PICO = 1.5
MULTIPLICADOR_HORARIO_VALLE = 0.7
RECOMPENSA_CAZADOR_PORCENTAJE = 0.5
REPUTACION_POR_DERROTAR_MARCADO = 10
RESPITE_MINUTOS_TRAS_DERROTA = 10
RESPITE_MARCA_TRAS_DERROTA_MINUTOS = 15

# Estado para ConversationHandler del panel
_PANEL_PEAJE_EDIT = 1

# Metadatos de cada clave configurable del peaje
_PEAJE_META = {
    "peaje_base":              ("🪙 Peaje base (oro)",                 "oro",      50,   0,   99999),
    "peaje_por_nivel":         ("📈 Incremento por nivel",             "oro",       2,   0,    1000),
    "duracion_marca_min":      ("⏱️ Duración de la marca",             "minutos",  30,   1,   1440),
    "infracciones_limite":     ("⚠️ Infracciones antes de x2",         "veces",     3,   1,     50),
    "infracciones_ventana_h":  ("🕐 Ventana de infracciones",          "horas",    24,   1,    168),
    "costo_rescate_mult":      ("💸 Multiplicador costo rescate",       "x",         2,   1,     20),
}

# ==================== CONFIG PEAJE ====================
def _get_cfg(clave: str, default) -> str:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT valor FROM config_peaje WHERE clave = ?", (clave,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else str(default)

def _set_cfg(clave: str, valor):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO config_peaje (clave, valor) VALUES (?, ?)", (clave, str(valor)))
    conn.commit()
    conn.close()

def _peaje_base() -> int:
    return int(_get_cfg("peaje_base", 50))

def _peaje_por_nivel() -> int:
    return int(_get_cfg("peaje_por_nivel", 2))

def _duracion_marca() -> int:
    return int(_get_cfg("duracion_marca_min", 30))

def _infracciones_limite() -> int:
    return int(_get_cfg("infracciones_limite", 3))

def _infracciones_ventana() -> int:
    return int(_get_cfg("infracciones_ventana_h", 24))

def _costo_rescate_mult() -> int:
    return int(_get_cfg("costo_rescate_mult", 2))

# Alias dinámicos para compatibilidad con el resto del módulo
def _PEAJE_BASE() -> int:          return _peaje_base()
def _PEAJE_POR_NIVEL() -> int:     return _peaje_por_nivel()
def _DURACION_MARCA() -> int:      return _duracion_marca()
def _INFRACCIONES_LIMITE() -> int: return _infracciones_limite()
def _INFRACCIONES_VENTANA() -> int: return _infracciones_ventana()
def _COSTO_RESCATE() -> int:       return _costo_rescate_mult()

# ==================== TABLAS ADICIONALES ====================
def _init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    for stmt in [
        'ALTER TABLE jugadores ADD COLUMN estado_marcado INTEGER DEFAULT 0',
        'ALTER TABLE jugadores ADD COLUMN marca_expiracion TIMESTAMP',
        'ALTER TABLE jugadores ADD COLUMN ultima_infraccion TIMESTAMP',
        'ALTER TABLE jugadores ADD COLUMN infracciones_24h INTEGER DEFAULT 0',
    ]:
        try:
            c.execute(stmt)
        except sqlite3.OperationalError:
            pass
    c.execute('''CREATE TABLE IF NOT EXISTS config_peaje (
        clave TEXT PRIMARY KEY,
        valor TEXT NOT NULL
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS combate_guardia (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ciudad_faccion TEXT,
        intruso_id INTEGER,
        intruso_nombre TEXT,
        peaje_original INTEGER,
        inicio TIMESTAMP,
        guardia_id INTEGER
    )''')
    conn.commit()
    conn.close()

_init_db()

# ==================== AUXILIARES ====================
def _obtener_multiplicador_horario() -> float:
    hora = datetime.now().hour
    if 18 <= hora < 22:
        return MULTIPLICADOR_HORARIO_PICO
    elif 2 <= hora < 8:
        return MULTIPLICADOR_HORARIO_VALLE
    return 1.0

def calcular_peaje(nivel: int, reputacion: int = 0) -> int:
    base = _peaje_base() + nivel * _peaje_por_nivel()
    descuento = min(20, reputacion // 100)
    peaje = int(base * (1 - descuento / 100))
    peaje = int(peaje * _obtener_multiplicador_horario())
    return max(1, peaje)

def _aplicar_marca(user_id: int, minutos: int = 0):
    if minutos == 0:
        minutos = _duracion_marca()
    expiracion = datetime.now() + timedelta(minutes=minutos)
    db_helper.actualizar_jugador(user_id, estado_marcado=1, marca_expiracion=expiracion.isoformat())

def _eliminar_marca(user_id: int):
    db_helper.actualizar_jugador(user_id, estado_marcado=0, marca_expiracion=None)

def _esta_marcado(user_id: int) -> bool:
    jug = db_helper.obtener_jugador(user_id)
    if not jug or not jug.get("estado_marcado"):
        return False
    expiracion = jug.get("marca_expiracion")
    if expiracion and datetime.now() < datetime.fromisoformat(expiracion):
        return True
    _eliminar_marca(user_id)
    return False

def _registrar_infraccion(user_id: int):
    ahora = datetime.now()
    ventana = ahora - timedelta(hours=_infracciones_ventana())
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Resetear solo las infracciones caducadas de ESTE jugador (no de todos)
    c.execute('UPDATE jugadores SET infracciones_24h = 0 WHERE user_id = ? AND ultima_infraccion < ?',
              (user_id, ventana.isoformat()))
    c.execute('SELECT infracciones_24h FROM jugadores WHERE user_id = ?', (user_id,))
    row = c.fetchone()
    nuevas = (row[0] + 1) if row else 1
    c.execute('UPDATE jugadores SET infracciones_24h = ?, ultima_infraccion = ? WHERE user_id = ?',
              (nuevas, ahora.isoformat(), user_id))
    conn.commit()
    conn.close()

def _obtener_guardias_disponibles(ciudad_faccion: str, excluir_id: int) -> List[Dict]:
    # Placeholder - en un sistema real se consultarían jugadores de la facción en la ciudad
    # Por ahora retornamos lista vacía para no romper flujo
    return []

# ==================== FUNCIONES PRINCIPALES ====================
async def solicitar_peaje(update: Update, context: ContextTypes.DEFAULT_TYPE, ciudad_info: dict):
    """Llamada desde ciudad.py cuando un jugador intenta entrar a ciudad de otra facción"""
    user_id = update.effective_user.id
    try:
        import guia_contextual as _gc
        await _gc.enviar(user_id, context, "peaje_encontrado")
    except Exception:
        pass
    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        await update.effective_message.reply_text("Primero crea un personaje.")
        return
    nivel = jug.get("nivel", 1)
    reputacion = jug.get("reputacion", 0)
    infracciones = jug.get("infracciones_24h", 0)
    peaje = calcular_peaje(nivel, reputacion)
    if infracciones >= _infracciones_limite():
        peaje *= 2
    context.user_data["peaje_pendiente"] = {
        "ciudad_faccion": ciudad_info["faccion"],
        "ciudad_nombre": ciudad_info["nombre"],
        "peaje_original": peaje
    }
    keyboard = [
        [InlineKeyboardButton(f"🪙 Pagar {peaje} oro", callback_data="peaje_pagar")],
        [InlineKeyboardButton("⚔️ No pagar (quedar marcado)", callback_data="peaje_marcado")]
    ]
    await update.effective_message.reply_text(
        f"⚠️ Estás entrando a *{ciudad_info['nombre']}* (territorio de {ciudad_info['faccion']}).\n"
        f"Peaje: *{peaje} de oro*.\n"
        f"Si no pagas, quedarás *marcado* y los guardias te atacarán.\n",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def procesar_pago(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    pendiente = context.user_data.get("peaje_pendiente")
    if not pendiente:
        await query.edit_message_text("No hay peaje pendiente.")
        return
    user_id = update.effective_user.id
    peaje = pendiente["peaje_original"]
    saldos = economia.obtener_saldos(user_id)
    if saldos.get("oro", 0) < peaje:
        await query.edit_message_text(f"No tienes suficiente oro. Necesitas {peaje}.")
        return
    economia.modificar_saldo(user_id, "oro", -peaje, f"pago peaje en {pendiente['ciudad_nombre']}")
    _eliminar_marca(user_id)
    await query.edit_message_text(f"✅ Peaje pagado. Entras a {pendiente['ciudad_nombre']}.")
    context.user_data.pop("peaje_pendiente", None)

async def procesar_marcado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    pendiente = context.user_data.get("peaje_pendiente")
    if not pendiente:
        await query.edit_message_text("No hay peaje pendiente.")
        return
    user_id = update.effective_user.id
    peaje = pendiente["peaje_original"]
    _aplicar_marca(user_id)
    _registrar_infraccion(user_id)
    await query.edit_message_text(
        f"⚠️ No pagas. Quedas *marcado* durante {_duracion_marca()} min.\n"
        f"Entras a {pendiente['ciudad_nombre']}. Los guardias pueden atacarte.\n"
        f"Penalizaciones: sin teletransporte, sin servicios, sin regeneración.")
    context.user_data.pop("peaje_pendiente", None)

    guardias = _obtener_guardias_disponibles(pendiente["ciudad_faccion"], user_id)
    if guardias:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''INSERT INTO combate_guardia (ciudad_faccion, intruso_id, intruso_nombre, peaje_original, inicio)
                     VALUES (?, ?, ?, ?, ?)''',
                  (pendiente["ciudad_faccion"], user_id,
                   (db_helper.obtener_jugador(user_id) or {}).get("nombre_personaje", "Desconocido"),
                   peaje, datetime.now().isoformat()))
        combate_id = c.lastrowid
        conn.commit()
        conn.close()
        for g in guardias:
            try:
                await context.bot.send_message(
                    chat_id=g["user_id"],
                    text=f"⚠️ Intruso marcado *{_esc_md((db_helper.obtener_jugador(user_id) or {}).get('nombre_personaje', 'Desconocido'))}* en la ciudad.\n"
                         f"Recompensa: {int(peaje * RECOMPENSA_CAZADOR_PORCENTAJE)} oro + {REPUTACION_POR_DERROTAR_MARCADO} reputación.\n"
                         f"El primero en aceptar el combate será el guardia.",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚔️ Aceptar", callback_data=f"pelea_guardia_{combate_id}")]])
                )
            except:
                pass

async def aceptar_combate_guardia(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        combate_id = int(query.data.split("_")[2])
    except (ValueError, IndexError):
        await query.edit_message_text("❌ Combate no válido.")
        return
    guardia_id = update.effective_user.id
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT intruso_id, guardia_id, intruso_nombre, peaje_original, ciudad_faccion FROM combate_guardia WHERE id = ?', (combate_id,))
    row = c.fetchone()
    if not row:
        await query.edit_message_text("Combate no disponible.")
        return
    intruso_id, guardia_asignado, intruso_nombre, peaje_original, ciudad_faccion = row
    if guardia_asignado is not None:
        await query.edit_message_text("Combate ya aceptado por otro guardia.")
        return
    c.execute('UPDATE combate_guardia SET guardia_id = ? WHERE id = ?', (guardia_id, combate_id))
    conn.commit()
    conn.close()
    # Notificar al intruso que un guardia aceptó cazarle
    jug_guardia = db_helper.obtener_jugador(guardia_id)
    nombre_guardia = jug_guardia["nombre_personaje"] if jug_guardia else "Un guardia"
    db_helper.agregar_notificacion(intruso_id,
        f"⚠️ ¡{nombre_guardia} aceptó cazarte! El combate ha comenzado. Prepárate para defenderte.")
    await iniciar_combate(
        update=update,
        context=context,
        user_id=guardia_id,
        enemigo_id=intruso_id,
        tipo_combate=COMBATE_PEAJE,
        datos_extra={
            "peaje_original": peaje_original,
            "recompensa_base_oro": int(peaje_original * RECOMPENSA_CAZADOR_PORCENTAJE),
            "reputacion_ganada": REPUTACION_POR_DERROTAR_MARCADO,
            "ciudad_faccion": ciudad_faccion,
            "combate_id": combate_id,
            "rol": "guardia"
        }
    )
    await query.edit_message_text("Combate iniciado. ¡Usa los botones para pelear!")

async def cmd_pagar_rescate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not _esta_marcado(user_id):
        await update.effective_message.reply_text("No estás marcado.")
        return
    jug = db_helper.obtener_jugador(user_id)
    peaje_original = calcular_peaje(jug.get("nivel", 1), jug.get("reputacion", 0))
    rescate = peaje_original * _costo_rescate_mult()
    saldos = economia.obtener_saldos(user_id)
    if saldos.get("oro", 0) < rescate:
        await update.effective_message.reply_text(f"No tienes {rescate} de oro para pagar rescate.")
        return
    economia.modificar_saldo(user_id, "oro", -rescate, "pago rescate por marca")
    _eliminar_marca(user_id)
    await update.effective_message.reply_text("✅ Marca levantada. ¡Ya puedes usar los servicios de la ciudad!")

# ==================== FUNCIONES PARA INTEGRACIÓN CON VIAJES ====================
async def solicitar_peaje_para_viaje(update: Update, context: ContextTypes.DEFAULT_TYPE, ciudad_destino: dict):
    user_id = update.effective_user.id
    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        await update.callback_query.edit_message_text("Error: jugador no encontrado.")
        return
    nivel = jug.get("nivel", 1)
    reputacion = jug.get("reputacion", 0)
    peaje = calcular_peaje(nivel, reputacion)
    context.user_data["peaje_pendiente"] = {
        "ciudad_faccion": ciudad_destino.get("faccion_nombre", ciudad_destino.get("faccion", "Desconocida")),
        "ciudad_nombre": ciudad_destino["nombre"],
        "peaje_original": peaje,
        "viaje_pendiente": context.user_data.get("viaje_pendiente")
    }
    keyboard = [
        [InlineKeyboardButton(f"🪙 Pagar {peaje} oro", callback_data="peaje_pagar_viaje")],
        [InlineKeyboardButton("⚔️ No pagar (quedar marcado)", callback_data="peaje_marcado_viaje")]
    ]
    await update.callback_query.edit_message_text(
        f"⚠️ Estás intentando entrar a *{ciudad_destino['nombre']}* (territorio de {ciudad_destino.get('faccion_nombre', ciudad_destino.get('faccion', '?'))}).\n"
        f"Peaje: *{peaje} de oro*.\n"
        f"Si no pagas, quedarás *marcado* y los guardias te atacarán.\n\n*Nota:* el viaje continuará después de decidir.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def procesar_pago_viaje(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    pendiente = context.user_data.get("peaje_pendiente")
    if not pendiente:
        await query.edit_message_text("No hay peaje pendiente.")
        return
    user_id = update.effective_user.id
    peaje = pendiente["peaje_original"]
    saldos = economia.obtener_saldos(user_id)
    if saldos.get("oro", 0) < peaje:
        await query.edit_message_text(f"No tienes suficiente oro. Necesitas {peaje}.")
        return
    economia.modificar_saldo(user_id, "oro", -peaje, f"pago peaje en {pendiente['ciudad_nombre']}")
    _eliminar_marca(user_id)
    viaje_pend = pendiente.get("viaje_pendiente")
    if viaje_pend:
        destino = _obtener_destino(viaje_pend["destino_id"])
        origen = _obtener_destino(viaje_pend["origen_id"])
        if destino and origen:
            # skip_ciudad_cost=True: el peaje en oro YA es el costo, no cobrar Eternium adicional
            await _iniciar_viaje_directo(update, context, destino, origen, skip_ciudad_cost=True)
        else:
            await query.edit_message_text(f"✅ Peaje pagado. Entras a {pendiente['ciudad_nombre']}.")
    else:
        await query.edit_message_text(f"✅ Peaje pagado. Entras a {pendiente['ciudad_nombre']}.")
    context.user_data.pop("peaje_pendiente", None)

async def procesar_marcado_viaje(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    pendiente = context.user_data.get("peaje_pendiente")
    if not pendiente:
        await query.edit_message_text("No hay peaje pendiente.")
        return
    user_id = update.effective_user.id
    _aplicar_marca(user_id)
    _registrar_infraccion(user_id)
    await query.edit_message_text(
        f"⚠️ No pagas. Quedas *marcado* durante {_duracion_marca()} min.\n"
        f"El viaje continuará, pero estarás marcado en la ciudad.")
    viaje_pend = pendiente.get("viaje_pendiente")
    if viaje_pend:
        # cobrar_ciudad=False: ya se eligió entrar sin pagar, no cobrar Eternium adicional
        await reanudar_viaje(update, context, viaje_pend, cobrar_ciudad=False)
    context.user_data.pop("peaje_pendiente", None)

# ==================== PANEL ADMIN PEAJE ====================
def _es_admin_peaje(user_id: int) -> bool:
    try:
        import superadmin as sa
        return sa._es_admin(user_id)
    except Exception:
        import os
        return str(user_id) == os.environ.get("SUPERADMIN_ID", "")

def _texto_panel_peaje() -> str:
    lineas = ["⚙️ *Panel de configuración de Peajes*\n"]
    for clave, (label, unidad, defecto, minimo, maximo) in _PEAJE_META.items():
        valor = int(_get_cfg(clave, defecto))
        lineas.append(f"{label}: *{valor}* {unidad}")
    lineas.append(f"\nPeaje ejemplo (Nv.10, 0 rep): *{calcular_peaje(10)}* oro")
    return "\n".join(lineas)

def _teclado_panel_peaje() -> InlineKeyboardMarkup:
    botones = []
    for clave, (label, unidad, defecto, minimo, maximo) in _PEAJE_META.items():
        valor = int(_get_cfg(clave, defecto))
        botones.append([InlineKeyboardButton(
            f"✏️ {label}: {valor} {unidad}",
            callback_data=f"pp_edit_{clave}"
        )])
    botones.append([InlineKeyboardButton("❌ Cerrar", callback_data="pp_cerrar")])
    return InlineKeyboardMarkup(botones)

async def cmd_panel_peaje(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not _es_admin_peaje(user_id):
        await update.effective_message.reply_text("❌ Sin permiso.")
        return
    await update.effective_message.reply_text(
        _texto_panel_peaje(),
        reply_markup=_teclado_panel_peaje(),
        parse_mode="Markdown"
    )

async def _cb_panel_peaje_nav(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    if not _es_admin_peaje(user_id):
        await query.answer("❌ Sin permiso.", show_alert=True)
        return
    context.user_data.pop("pp_clave", None)
    await query.edit_message_text(
        _texto_panel_peaje(),
        reply_markup=_teclado_panel_peaje(),
        parse_mode="Markdown"
    )

async def _cb_panel_peaje_iniciar_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    if not _es_admin_peaje(user_id):
        await query.answer("❌ Sin permiso.", show_alert=True)
        return ConversationHandler.END
    clave = query.data[len("pp_edit_"):]
    if clave not in _PEAJE_META:
        await query.answer("❌ Clave desconocida.", show_alert=True)
        return ConversationHandler.END
    label, unidad, defecto, minimo, maximo = _PEAJE_META[clave]
    valor_actual = int(_get_cfg(clave, defecto))
    context.user_data["pp_clave"] = clave
    await query.edit_message_text(
        f"✏️ *Editando:* {label}\n\n"
        f"Valor actual: *{valor_actual}* {unidad}\n"
        f"Rango permitido: {minimo} – {maximo}\n\n"
        f"Escribe el nuevo valor numérico o pulsa Cancelar.",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ Cancelar", callback_data="pp_cancelar")
        ]]),
        parse_mode="Markdown"
    )
    return _PANEL_PEAJE_EDIT

async def _panel_peaje_recibir_valor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not _es_admin_peaje(user_id):
        return ConversationHandler.END
    clave = context.user_data.get("pp_clave")
    if not clave or clave not in _PEAJE_META:
        await update.effective_message.reply_text("❌ Sin clave activa. Usa /panel_peaje.")
        return ConversationHandler.END
    label, unidad, defecto, minimo, maximo = _PEAJE_META[clave]
    try:
        nuevo = int(update.message.text.strip())
    except ValueError:
        await update.effective_message.reply_text(f"❌ Valor no válido. Escribe un número entre {minimo} y {maximo}.")
        return _PANEL_PEAJE_EDIT
    if not (minimo <= nuevo <= maximo):
        await update.effective_message.reply_text(f"❌ Fuera de rango ({minimo}–{maximo}). Inténtalo de nuevo.")
        return _PANEL_PEAJE_EDIT
    _set_cfg(clave, nuevo)
    context.user_data.pop("pp_clave", None)
    await update.effective_message.reply_text(
        f"✅ *{label}* actualizado a *{nuevo}* {unidad}.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 Volver al panel", callback_data="pp_menu")
        ]])
    )
    return ConversationHandler.END

async def _panel_peaje_cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("pp_clave", None)
    return ConversationHandler.END


# ==================== REGISTRO DE HANDLERS ====================
def registrar_handlers(app):
    app.add_handler(CallbackQueryHandler(procesar_pago, pattern="^peaje_pagar$"))
    app.add_handler(CallbackQueryHandler(procesar_marcado, pattern="^peaje_marcado$"))
    app.add_handler(CallbackQueryHandler(aceptar_combate_guardia, pattern="^pelea_guardia_"))
    app.add_handler(CommandHandler("pagar_rescate", cmd_pagar_rescate))
    app.add_handler(CallbackQueryHandler(procesar_pago_viaje, pattern="^peaje_pagar_viaje$"))
    app.add_handler(CallbackQueryHandler(procesar_marcado_viaje, pattern="^peaje_marcado_viaje$"))

    # Panel admin de peaje
    conv_panel_peaje = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(_cb_panel_peaje_iniciar_edit, pattern=r"^pp_edit_"),
        ],
        states={
            _PANEL_PEAJE_EDIT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _panel_peaje_recibir_valor),
                CallbackQueryHandler(_cb_panel_peaje_nav, pattern=r"^pp_cancelar$"),
            ],
        },
        fallbacks=[
            CommandHandler("cancelar", _panel_peaje_cancelar),
            CommandHandler("panel_peaje", cmd_panel_peaje),
        ],
        allow_reentry=True,
        per_message=False,
    )
    app.add_handler(conv_panel_peaje)
    app.add_handler(CallbackQueryHandler(_cb_panel_peaje_nav, pattern=r"^pp_(menu|cancelar|cerrar)$"))
    app.add_handler(CommandHandler("panel_peaje", cmd_panel_peaje))
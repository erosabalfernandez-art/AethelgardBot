"""
teclado_rapido.py
Teclado persistente (Reply Keyboard) que aparece en la parte inferior del chat.
Se muestra automáticamente al registrarse (/start) y al abrir /ciudad.
Los botones ejecutan los comandos más importantes del juego.

Comandos de toggle:
  🔲 Ocultar menú    — botón en la última fila del menú (lo oculta)
  /menu              — muestra el menú si estaba oculto, o lo oculta si está visible
  /teclado           — alias de /menu (compatibilidad)

Botones especiales:
  🔄 Actualizar menú — primer botón de todos los menús; sincroniza el menú a la zona actual
  ⚙️ Editar menú     — solo en ciudad; permite elegir qué botones aparecen en cada menú
"""
import sqlite3 as _sqlite3
import json as _json

from telegram import (
    Update, ReplyKeyboardMarkup, KeyboardButton,
    ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
)
from telegram.ext import ContextTypes, MessageHandler, CommandHandler, CallbackQueryHandler, filters
import db_helper


# ─── TABLA PERSONALIZACIÓN ────────────────────────────────────────────────────

def _init_menu_db():
    """Crea la tabla de personalización de menús si no existe."""
    try:
        conn = _sqlite3.connect(db_helper.DB_PATH)
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS menu_personalizado (
                user_id     INTEGER,
                menu_tipo   TEXT,
                botones_ocultos TEXT DEFAULT '[]',
                PRIMARY KEY (user_id, menu_tipo)
            )
        """)
        conn.commit()
        conn.close()
    except Exception:
        pass

_init_menu_db()


def _get_ocultos(user_id: int, menu_tipo: str) -> list:
    """Devuelve lista de nombres de botones ocultos por el usuario."""
    try:
        conn = _sqlite3.connect(db_helper.DB_PATH)
        c = conn.cursor()
        c.execute(
            "SELECT botones_ocultos FROM menu_personalizado WHERE user_id=? AND menu_tipo=?",
            (user_id, menu_tipo)
        )
        row = c.fetchone()
        conn.close()
        if row:
            return _json.loads(row[0] or "[]")
    except Exception:
        pass
    return []


def _set_ocultos(user_id: int, menu_tipo: str, lista: list):
    """Guarda la lista de botones ocultos para el usuario en ese tipo de menú."""
    try:
        conn = _sqlite3.connect(db_helper.DB_PATH)
        c = conn.cursor()
        c.execute("""
            INSERT INTO menu_personalizado (user_id, menu_tipo, botones_ocultos)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, menu_tipo) DO UPDATE SET botones_ocultos=excluded.botones_ocultos
        """, (user_id, menu_tipo, _json.dumps(lista, ensure_ascii=False)))
        conn.commit()
        conn.close()
    except Exception:
        pass


def _toggle_boton(user_id: int, menu_tipo: str, boton: str):
    """Alterna la visibilidad de un botón."""
    lista = _get_ocultos(user_id, menu_tipo)
    if boton in lista:
        lista.remove(boton)
    else:
        lista.append(boton)
    _set_ocultos(user_id, menu_tipo, lista)


# ─── BOTONES CONFIGURABLES POR MENÚ ──────────────────────────────────────────

_BOTONES_CIUDAD_CONFIG = [
    "👤 Perfil",
    "🏙️ Ciudad",
    "🎒 Inventario",
    "✈️ Viajar",
    "⚔️ Duelos",
    "🏰 Gremio",
    "🏆 Rankings",
    "🌑 Umbral",
    "📋 Comandos",
    "📖 Guía",
]

_BOTONES_SALVAJE_CONFIG = [
    "⛏️ Recolectar",
    "🔍 Investigar",
    "🏰 Mazmorra",
    "✈️ Viajar",
    "👤 Perfil",
    "🎒 Inventario",
    "📋 Comandos",
    "📖 Guía",
]

_FE0F = "\ufe0f"


def _filtrar(botones_planos: list, user_id: int, menu_tipo: str) -> list:
    """Elimina de la lista los botones que el usuario ocultó."""
    if not user_id:
        return botones_planos
    ocultos = [b.replace(_FE0F, "") for b in _get_ocultos(user_id, menu_tipo)]
    return [b for b in botones_planos if b.replace(_FE0F, "") not in ocultos]


# ─── PREFERENCIA POR JUGADOR ──────────────────────────────────────────────────

def _teclado_esta_oculto(user_id: int) -> bool:
    jug = db_helper.obtener_jugador(user_id)
    return bool(jug.get("teclado_oculto", 0)) if jug else False


def _set_teclado_oculto(user_id: int, oculto: bool):
    db_helper.actualizar_jugador(user_id, teclado_oculto=1 if oculto else 0)


# ─── TRACKER DE TIPO DE TECLADO ACTIVO ───────────────────────────────────────

_TIPO_TECLADO: dict = {}


def marcar_tipo(user_id: int, tipo: str):
    """Registra el tipo de menú enviado ('ciudad' | 'salvaje' | 'guerra')."""
    _TIPO_TECLADO[user_id] = tipo


def _tipo_correcto(zona_actual: str) -> str:
    """Devuelve 'ciudad' o 'salvaje' según la zona actual del jugador."""
    color = _detectar_color(zona_actual)
    return "ciudad" if color in ("ciudad", "") else "salvaje"


# ─── COMPROBACIÓN SUPERADMIN ──────────────────────────────────────────────────

def _es_superadmin(user_id: int) -> bool:
    try:
        import superadmin as _sa
        return _sa.verificar_superadmin(user_id)
    except Exception:
        return False


# ─── TECLADO PRINCIPAL (CIUDAD) ───────────────────────────────────────────────

def get_teclado_principal(user_id: int = 0) -> ReplyKeyboardMarkup:
    """Menú inferior para zonas de ciudad."""
    base = [
        "👤 Perfil",       "🏙️ Ciudad",
        "🎒 Inventario",   "✈️ Viajar",
        "⚔️ Duelos",       "🏰 Gremio",
        "🏆 Rankings",     "🌑 Umbral",
        "📋 Comandos",     "📖 Guía",
    ]
    visibles = _filtrar(base, user_id, "ciudad")

    botones = []
    for i in range(0, len(visibles), 2):
        fila = [KeyboardButton(visibles[i])]
        if i + 1 < len(visibles):
            fila.append(KeyboardButton(visibles[i + 1]))
        botones.append(fila)

    if user_id and _es_superadmin(user_id):
        botones.append([KeyboardButton("🔐 Admin"), KeyboardButton("🐛 Debug")])

    # Botones fijos: primero y último
    botones.insert(0, [
        KeyboardButton("🔄 Actualizar menú"),
        KeyboardButton("⚙️ Editar menú"),
    ])
    botones.append([KeyboardButton("🔲 Ocultar menú")])

    return ReplyKeyboardMarkup(
        botones,
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Escribe un comando o pulsa un botón…"
    )


def get_teclado_salvaje(user_id: int = 0) -> ReplyKeyboardMarkup:
    """Menú cuando el jugador está en zona salvaje."""
    base = [
        "⛏️ Recolectar",  "🔍 Investigar",
        "🏰 Mazmorra",
        "✈️ Viajar",       "👤 Perfil",
        "🎒 Inventario",   "📋 Comandos",
        "📖 Guía",
    ]
    visibles = _filtrar(base, user_id, "salvaje")

    botones: list = []
    i = 0
    while i < len(visibles):
        b = visibles[i]
        if b.replace(_FE0F, "") == "🏰 Mazmorra":
            botones.append([KeyboardButton(b)])
            i += 1
        else:
            fila = [KeyboardButton(b)]
            if i + 1 < len(visibles) and visibles[i + 1].replace(_FE0F, "") != "🏰 Mazmorra":
                fila.append(KeyboardButton(visibles[i + 1]))
                i += 2
            else:
                i += 1
            botones.append(fila)

    if user_id:
        try:
            import recoleccion_auto as _ra
            if _ra.tiene_auto_recoleccion(user_id):
                botones.insert(2, [KeyboardButton("🤖 Auto-Recolección")])
        except Exception:
            pass
        try:
            _jug = db_helper.obtener_jugador(user_id)
            if _jug:
                from datos_zona import ZONAS as _ZG_tr
                _zid = _jug.get("zona_actual_id")
                _color = next((z.get("color", "") for z in _ZG_tr if z.get("id") == _zid), "")
                if _color in ("amarilla", "roja", "negra"):
                    _em = {"amarilla": "🟡", "roja": "🔴", "negra": "⬛"}.get(_color, "")
                    botones.insert(1, [
                        KeyboardButton("⚔️ Emboscada PvP"),
                        KeyboardButton(f"🌐 Emboscada Zonas {_em}"),
                    ])
        except Exception:
            pass

    if user_id and _es_superadmin(user_id):
        botones.append([KeyboardButton("🔐 Admin"), KeyboardButton("🐛 Debug")])

    botones.insert(0, [KeyboardButton("🔄 Actualizar menú")])
    botones.append([KeyboardButton("🔲 Ocultar menú")])

    return ReplyKeyboardMarkup(
        botones,
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Zona salvaje — ¿qué haces?"
    )


def get_teclado_guerra(user_id: int = 0) -> ReplyKeyboardMarkup:
    """Menú de emergencia durante la Guerra de Facciones."""
    botones = [
        [KeyboardButton("🔄 Actualizar menú")],
        [KeyboardButton("⚔️ Atacar en guerra"),  KeyboardButton("🛡️ Defender en guerra")],
        [KeyboardButton("⏭️ Saltar guerra"),      KeyboardButton("👤 Perfil")],
        [KeyboardButton("🎒 Inventario"),          KeyboardButton("📖 Guía")],
        [KeyboardButton("🔲 Ocultar menú")],
    ]
    return ReplyKeyboardMarkup(
        botones,
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="⚔️ ¡Guerra de Facciones activa! Elige tu acción."
    )


# ─── EDITOR DE MENÚ ───────────────────────────────────────────────────────────

def _build_editor_keyboard(user_id: int, menu_tipo: str) -> InlineKeyboardMarkup:
    """Construye el teclado inline del editor de menú."""
    config = _BOTONES_CIUDAD_CONFIG if menu_tipo == "ciudad" else _BOTONES_SALVAJE_CONFIG
    ocultos = [b.replace(_FE0F, "") for b in _get_ocultos(user_id, menu_tipo)]
    filas = []
    for btn in config:
        nombre_norm = btn.replace(_FE0F, "")
        estado = "✅" if nombre_norm not in ocultos else "❌"
        filas.append([InlineKeyboardButton(
            f"{estado} {btn}",
            callback_data=f"editormenu_{menu_tipo}_{nombre_norm}"
        )])
    filas.append([
        InlineKeyboardButton("🏙️ Menú Ciudad",   callback_data="editormenu_ver_ciudad"),
        InlineKeyboardButton("🌲 Menú Salvaje",  callback_data="editormenu_ver_salvaje"),
    ])
    filas.append([
        InlineKeyboardButton("↩️ Restaurar todo", callback_data=f"editormenu_reset_{menu_tipo}"),
        InlineKeyboardButton("✅ Listo",           callback_data="editormenu_cerrar"),
    ])
    return InlineKeyboardMarkup(filas)


async def handle_editar_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Abre el panel de edición del menú. Solo disponible en ciudad."""
    user_id = update.effective_user.id
    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        return
    zona = jug.get("zona_actual", "")
    color = _detectar_color(zona)
    if color not in ("ciudad", ""):
        await update.message.reply_text(
            "⚙️ El editor de menú solo está disponible desde la ciudad.\n"
            "Viaja a tu ciudad y pulsa el botón ⚙️ Editar menú de nuevo."
        )
        return
    kb = _build_editor_keyboard(user_id, "ciudad")
    await update.message.reply_text(
        "⚙️ <b>EDITOR DE MENÚ</b>\n\n"
        "Aquí puedes elegir qué botones quieres ver en cada menú.\n"
        "✅ = visible  |  ❌ = oculto\n\n"
        "Toca un botón para activarlo o desactivarlo.\n"
        "Cambia entre menús con los botones de abajo.",
        parse_mode="HTML",
        reply_markup=kb
    )


async def cb_editor_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback del editor de menú."""
    query = update.callback_query
    try:
        await query.answer()
    except Exception:
        pass
    user_id = query.from_user.id
    data = query.data

    if data == "editormenu_cerrar":
        try:
            await query.edit_message_text(
                "✅ Configuración guardada.\n\nPulsa 🔄 Actualizar menú para ver los cambios."
            )
        except Exception:
            pass
        return

    if data.startswith("editormenu_ver_"):
        tipo = data.replace("editormenu_ver_", "")
        kb = _build_editor_keyboard(user_id, tipo)
        nombre_menu = "Ciudad" if tipo == "ciudad" else "Zona Salvaje"
        try:
            await query.edit_message_text(
                f"⚙️ <b>EDITOR DE MENÚ — {nombre_menu}</b>\n\n"
                "✅ = visible  |  ❌ = oculto\n\n"
                "Toca un botón para activarlo o desactivarlo.",
                parse_mode="HTML",
                reply_markup=kb
            )
        except Exception:
            pass
        return

    if data.startswith("editormenu_reset_"):
        tipo = data.replace("editormenu_reset_", "")
        _set_ocultos(user_id, tipo, [])
        kb = _build_editor_keyboard(user_id, tipo)
        nombre_menu = "Ciudad" if tipo == "ciudad" else "Zona Salvaje"
        try:
            await query.edit_message_text(
                f"⚙️ <b>EDITOR DE MENÚ — {nombre_menu}</b>\n\n"
                "↩️ Todos los botones restaurados.\n\n"
                "✅ = visible  |  ❌ = oculto",
                parse_mode="HTML",
                reply_markup=kb
            )
        except Exception:
            pass
        return

    if data.startswith("editormenu_"):
        partes = data.split("_", 2)
        if len(partes) == 3:
            _, tipo, boton_norm = partes
            config = _BOTONES_CIUDAD_CONFIG if tipo == "ciudad" else _BOTONES_SALVAJE_CONFIG
            nombre_real = None
            for b in config:
                if b.replace(_FE0F, "") == boton_norm:
                    nombre_real = b
                    break
            if nombre_real:
                _toggle_boton(user_id, tipo, nombre_real)
            kb = _build_editor_keyboard(user_id, tipo)
            try:
                await query.edit_message_reply_markup(reply_markup=kb)
            except Exception:
                pass
        return


# ─── HANDLER: botón ACTUALIZAR MENÚ ──────────────────────────────────────────

async def handle_actualizar_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Detecta zona/guerra actual y envía el menú correcto.
    Usa el campo 'ubicacion' de la BD (la fuente de verdad) en lugar de
    intentar inferirlo desde el nombre de zona, evitando fallos de cache o
    desajustes de nombre.
    """
    user_id = update.effective_user.id

    # Leer directamente desde la BD sin caché para tener el estado más reciente
    try:
        import sqlite3 as _sq
        conn = _sq.connect(db_helper.DB_PATH)
        c = conn.cursor()
        c.execute("SELECT zona_actual, ubicacion FROM jugadores WHERE user_id = ?", (user_id,))
        row = c.fetchone()
        conn.close()
    except Exception:
        row = None

    if not row:
        await update.message.reply_text("❌ Primero crea tu personaje con /start.")
        return

    zona_nombre, ubicacion = row
    ubicacion = ubicacion or "ciudad"  # por defecto ciudad si NULL

    guerra_activa = False
    try:
        from guerra_facciones import hay_guerra_activa as _hga
        guerra_activa = _hga()
    except Exception:
        pass

    if guerra_activa:
        kb = get_teclado_guerra(user_id)
        marcar_tipo(user_id, "guerra")
        await update.message.reply_text(
            "🔄 Menú actualizado — ⚔️ *¡Guerra de Facciones activa!*",
            parse_mode="Markdown",
            reply_markup=kb
        )
        return

    # Usar el campo 'ubicacion' directamente — es la fuente de verdad
    if ubicacion == "salvaje":
        kb = get_teclado_salvaje(user_id)
        zona_display = zona_nombre or "zona salvaje"
        msg = f"🔄 Menú actualizado — 🌲 {zona_display}"
        marcar_tipo(user_id, "salvaje")
    else:
        kb = get_teclado_principal(user_id)
        zona_display = zona_nombre or "ciudad"
        msg = f"🔄 Menú actualizado — 🏙️ {zona_display}"
        marcar_tipo(user_id, "ciudad")

    await update.message.reply_text(msg, reply_markup=kb)


# ─── MAPA DE BOTONES → COMANDOS ───────────────────────────────────────────────

_MAPA = {
    "👤 Perfil":              "/perfil",
    "🏙️ Ciudad":              "/ciudad",
    "🎒 Inventario":           "/inventario",
    "✈️ Viajar":               "/viajar",
    "⚔️ Duelos":               "/duelo_menu",
    "🏰 Gremio":               "/gremio",
    "⛏️ Recolectar":           "/recolectar",
    "🔍 Investigar":           "/investigar",
    "🏰 Mazmorra":             "/mazmorra",
    "⚔️ Atacar jugador":       "/pvp_buscar",
    "🔐 Admin":                "/superadmin",
    "🐛 Debug":                "/panel_debug",
    "📋 Comandos":             "/comandos",
    "📖 Guía":                 "/guia",
    "🏆 Rankings":             "/rankings",
    "🌑 Umbral":               "/umbral",
    "⚔️ Atacar en guerra":     "/guerra_facciones_atacar",
    "🛡️ Defender en guerra":   "/guerra_facciones_defender",
    "⏭️ Saltar guerra":        "/saltar_guerra",
    "🤖 Auto-Recolección":     "/auto_recoleccion",
    "⚔️ Emboscada PvP":        "/pvp_buscar",
    "🌐 Emboscada Zonas 🟡":   "/pvp_multi",
    "🌐 Emboscada Zonas 🔴":   "/pvp_multi",
    "🌐 Emboscada Zonas ⬛":   "/pvp_multi",
}


# ─── HANDLER: botón OCULTAR MENÚ ─────────────────────────────────────────────

_BTN_MOSTRAR = InlineKeyboardMarkup([[
    InlineKeyboardButton("📱 Activar y mostrar menú", callback_data="teclado_mostrar")
]])


async def handle_ocultar_teclado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Oculta el menú y guarda la preferencia."""
    user_id = update.effective_user.id
    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        return
    _set_teclado_oculto(user_id, True)
    await update.message.reply_text(
        "🔲 Menú ocultado.",
        reply_markup=ReplyKeyboardRemove()
    )
    await update.message.reply_text(
        "Pulsa el botón para volver a mostrarlo:",
        reply_markup=_BTN_MOSTRAR
    )


async def cb_teclado_mostrar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback del botón inline 📱 Activar y mostrar menú."""
    query = update.callback_query
    try:
        await query.answer()
    except Exception:
        pass
    user_id = update.effective_user.id
    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        return
    _set_teclado_oculto(user_id, False)
    guerra_ok = False
    try:
        from guerra_facciones import hay_guerra_activa as _hga
        if _hga():
            kb = get_teclado_guerra(user_id)
            marcar_tipo(user_id, "guerra")
            guerra_ok = True
    except Exception:
        pass
    if not guerra_ok:
        ubicacion = jug.get("ubicacion", "ciudad") or "ciudad"
        if ubicacion == "salvaje":
            kb = get_teclado_salvaje(user_id)
            marcar_tipo(user_id, "salvaje")
        else:
            kb = get_teclado_principal(user_id)
            marcar_tipo(user_id, "ciudad")
    try:
        await query.edit_message_text("📱 Menú activado.")
    except Exception:
        pass
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="📱 Aquí tienes tu menú:",
        reply_markup=kb
    )


# ─── COMANDO /menu (y alias /teclado) ────────────────────────────────────────

async def cmd_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /menu — muestra el menú si estaba oculto, lo oculta si estaba visible.
    /teclado — alias de /menu (compatibilidad hacia atrás).
    """
    user_id = update.effective_user.id
    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        await update.effective_message.reply_text("❌ Primero crea tu personaje con /start.")
        return

    oculto = _teclado_esta_oculto(user_id)
    if oculto:
        _set_teclado_oculto(user_id, False)
        guerra_ok = False
        try:
            from guerra_facciones import hay_guerra_activa as _hga
            if _hga():
                kb = get_teclado_guerra(user_id)
                marcar_tipo(user_id, "guerra")
                guerra_ok = True
        except Exception:
            pass
        if not guerra_ok:
            # Usar ubicacion de la BD directamente (fuente de verdad)
            ubicacion = jug.get("ubicacion", "ciudad") or "ciudad"
            if ubicacion == "salvaje":
                kb = get_teclado_salvaje(user_id)
                marcar_tipo(user_id, "salvaje")
            else:
                kb = get_teclado_principal(user_id)
                marcar_tipo(user_id, "ciudad")
        await update.effective_message.reply_text(
            "📱 Menú activado.",
            reply_markup=kb
        )
    else:
        _set_teclado_oculto(user_id, True)
        await update.effective_message.reply_text(
            "🔲 Menú ocultado.",
            reply_markup=ReplyKeyboardRemove()
        )
        await update.effective_message.reply_text(
            "Pulsa el botón para volver a mostrarlo:",
            reply_markup=_BTN_MOSTRAR
        )


# Alias para compatibilidad
cmd_teclado = cmd_menu


# ─── HANDLER: convierte pulsaciones de botón en comandos ─────────────────────

_MAPA_NORM = {k.replace(_FE0F, ""): v for k, v in _MAPA.items()}

async def handle_boton_rapido(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Intercepta el texto del botón y lo despacha como el comando correspondiente.
    Normaliza U+FE0F para compatibilidad con todos los clientes de Telegram.
    Auto-sincroniza el menú si el tipo no coincide con la zona actual.
    """
    texto_raw = update.message.text.strip() if update.message and update.message.text else ""
    texto = texto_raw.replace(_FE0F, "")
    if texto not in _MAPA_NORM:
        return

    user_id = update.effective_user.id
    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        await update.effective_message.reply_text("❌ Primero crea tu personaje con /start.")
        return

    # ── AUTO-SYNC DE MENÚ ──────────────────────────────────────────────────────
    if not _teclado_esta_oculto(user_id):
        zona = jug.get("zona_actual", "")
        tipo_actual = _tipo_correcto(zona)
        tipo_guardado = _TIPO_TECLADO.get(user_id)

        guerra_activa = False
        try:
            from guerra_facciones import hay_guerra_activa as _hga_sync
            guerra_activa = _hga_sync()
        except Exception:
            pass

        necesita_sync = (
            tipo_guardado != tipo_actual
            or (tipo_guardado == "guerra" and not guerra_activa)
        )

        if necesita_sync:
            kb = get_teclado_salvaje(user_id) if tipo_actual == "salvaje" else get_teclado_principal(user_id)
            try:
                await update.message.reply_text("📍 Menú actualizado.", reply_markup=kb)
                marcar_tipo(user_id, tipo_actual)
            except Exception:
                pass

    comando_destino = _MAPA_NORM[texto]

    # ── LOCKDOWN POR GUERRA DE FACCIONES ──────────────────────────────────────
    _CMDS_GUERRA_OK = {
        "/guerra_facciones_atacar", "/guerra_facciones_defender",
        "/saltar_guerra", "/perfil", "/inventario", "/guia",
    }
    try:
        from guerra_facciones import hay_guerra_activa as _hga_btn
        if _hga_btn() and comando_destino not in _CMDS_GUERRA_OK:
            if not _teclado_esta_oculto(user_id):
                kb_g = get_teclado_guerra(user_id)
                await update.message.reply_text(
                    "🔒 *¡Los servicios están suspendidos durante la Guerra de Facciones!*\n\n"
                    "Usa los botones de tu menú de guerra o espera a que termine.",
                    parse_mode="Markdown",
                    reply_markup=kb_g
                )
                marcar_tipo(user_id, "guerra")
            else:
                await update.effective_message.reply_text(
                    "🔒 Durante la guerra no puedes hacer eso.\n"
                    "Usa /guerra_facciones_atacar, /guerra_facciones_defender o /saltar_guerra."
                )
            return
    except Exception:
        pass

    try:
        if comando_destino == "/perfil":
            from perfil import cmd_perfil
            await cmd_perfil(update, context)
        elif comando_destino == "/ciudad":
            from ciudad import cmd_ciudad
            await cmd_ciudad(update, context)
        elif comando_destino == "/inventario":
            from inventario import cmd_inventario
            await cmd_inventario(update, context)
        elif comando_destino == "/viajar":
            from viajes import cmd_viajar
            await cmd_viajar(update, context)
        elif comando_destino == "/gremio":
            from gremios import cmd_gremio
            await cmd_gremio(update, context)
        elif comando_destino == "/recolectar":
            zona = jug.get("zona_actual", "")
            color = _detectar_color(zona)
            if color == "azul":
                from recoleccion_azul import cmd_recolectar
            elif color == "amarilla":
                from recoleccion_amarilla import cmd_recolectar
            elif color == "roja":
                from recoleccion_roja import cmd_recolectar
            elif color == "negra":
                from recoleccion_negra import cmd_recolectar
            else:
                await update.effective_message.reply_text("⚠️ Solo puedes recolectar en zonas salvajes.")
                return
            await cmd_recolectar(update, context)
        elif comando_destino == "/investigar":
            zona = jug.get("zona_actual", "")
            color = _detectar_color(zona)
            if color == "azul":
                from investigacion_azul import cmd_investigar
            elif color == "amarilla":
                from investigacion_amarilla import cmd_investigar
            elif color == "roja":
                from investigacion_roja import cmd_investigar
            elif color == "negra":
                from investigacion_negra import cmd_investigar
            else:
                await update.effective_message.reply_text("⚠️ Solo puedes investigar en zonas salvajes.")
                return
            await cmd_investigar(update, context)
        elif comando_destino == "/mazmorra":
            zona = jug.get("zona_actual", "")
            color = _detectar_color(zona)
            if color == "azul":
                from mazmorra_azul import cmd_mazmorra
            elif color == "amarilla":
                from mazmorra_amarilla import cmd_mazmorra
            elif color == "roja":
                from mazmorra_roja import cmd_mazmorra
            elif color == "negra":
                from mazmorra_negra import cmd_mazmorra
            else:
                await update.effective_message.reply_text("⚠️ Solo puedes entrar a mazmorras en zonas salvajes.")
                return
            await cmd_mazmorra(update, context)
        elif comando_destino == "/duelo_menu":
            await _handle_duelo_menu(update, context, jug)
        elif comando_destino == "/atacar_zona":
            await _handle_atacar_zona(update, context, jug)
        elif comando_destino == "/superadmin":
            from superadmin import cmd_panel_admin
            await cmd_panel_admin(update, context)
        elif comando_destino == "/panel_debug":
            from panel_debug import cmd_panel_debug
            await cmd_panel_debug(update, context)
        elif comando_destino == "/comandos":
            from comandos import cmd_comandos
            await cmd_comandos(update, context)
        elif comando_destino == "/guia":
            from guia import cmd_guia
            await cmd_guia(update, context)
        elif comando_destino == "/rankings":
            try:
                from rankings import cmd_rankings
                await cmd_rankings(update, context)
            except ImportError:
                await update.effective_message.reply_text("🏆 Rankings: usa /rankings para ver las clasificaciones.")
        elif comando_destino == "/umbral":
            try:
                from umbral_vacio import cmd_umbral
                await cmd_umbral(update, context)
            except ImportError:
                await update.effective_message.reply_text("🌑 Umbral del Vacío: usa /umbral para ver el estado.")
        elif comando_destino == "/guerra_facciones_atacar":
            from guerra_facciones import cmd_guerra_facciones_atacar
            await cmd_guerra_facciones_atacar(update, context)
        elif comando_destino == "/guerra_facciones_defender":
            from guerra_facciones import cmd_guerra_facciones_defender
            await cmd_guerra_facciones_defender(update, context)
        elif comando_destino == "/saltar_guerra":
            from guerra_facciones import cmd_saltar_guerra
            await cmd_saltar_guerra(update, context)
        elif comando_destino == "/auto_recoleccion":
            from recoleccion_auto import cmd_auto_recoleccion
            await cmd_auto_recoleccion(update, context)
        elif comando_destino == "/pvp_buscar":
            from pvp_mortal import cmd_pvp_buscar
            await cmd_pvp_buscar(update, context)
        elif comando_destino == "/pvp_multi":
            from pvp_mortal import cmd_pvp_multi
            await cmd_pvp_multi(update, context)
    except Exception as e:
        await update.effective_message.reply_text(f"⚠️ Error: {e}")


async def _handle_duelo_menu(update, context, jug: dict):
    """Botón ⚔️ Duelos — muestra jugadores disponibles para retar."""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    user_id = jug["user_id"]
    todos = db_helper.obtener_todos_jugadores()
    rivales = [j for j in todos if j["user_id"] != user_id and j.get("ubicacion", "ciudad") != "viaje"]
    if not rivales:
        await update.effective_message.reply_text(
            "⚔️ No hay otros jugadores disponibles.\n\n"
            "También puedes retar con <code>/duelo &lt;user_id&gt;</code>.",
            parse_mode="HTML"
        )
        return
    botones = [
        [InlineKeyboardButton(
            f"⚔️ {j['nombre_personaje']}  —  Nv.{j.get('nivel', 1)} {j.get('clase', '')}",
            callback_data=f"tkpvp_{j['user_id']}"
        )]
        for j in rivales[:8]
    ]
    botones.append([InlineKeyboardButton("❌ Cancelar", callback_data="tkpvp_cancel")])
    await update.effective_message.reply_text(
        "⚔️ <b>Duelos PvP</b>\n\nElige a quién retar:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(botones)
    )


async def _handle_atacar_zona(update, context, jug: dict):
    """Muestra inline keyboard con jugadores en la misma zona."""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    user_id = jug["user_id"]
    zona = jug.get("zona_actual", "")
    color = _detectar_color(zona)
    if color in ("ciudad", ""):
        await update.effective_message.reply_text("⚔️ No puedes atacar en ciudad.")
        return
    todos = db_helper.obtener_todos_jugadores()
    en_zona = [j for j in todos if j.get("zona_actual") == zona and j["user_id"] != user_id and j.get("ubicacion") == "salvaje"]
    if not en_zona:
        await update.effective_message.reply_text(f"⚔️ No hay otros jugadores en <b>{zona}</b>.", parse_mode="HTML")
        return
    botones = [
        [InlineKeyboardButton(
            f"⚔️ {j['nombre_personaje']}  —  Nv.{j.get('nivel', 1)} {j.get('clase', '')}",
            callback_data=f"tkpvp_{j['user_id']}"
        )]
        for j in en_zona[:8]
    ]
    botones.append([InlineKeyboardButton("❌ Cancelar", callback_data="tkpvp_cancel")])
    await update.effective_message.reply_text(
        f"⚔️ <b>Jugadores en {zona}:</b>\n\nElige a quién retar:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(botones)
    )


async def cb_tkpvp(update, context):
    """Callback del selector PvP."""
    query = update.callback_query
    await query.answer()
    if query.data == "tkpvp_cancel":
        try:
            await query.edit_message_text("❌ Cancelado.")
        except Exception:
            pass
        return
    try:
        oponente_id = int(query.data.split("_")[1])
    except (ValueError, IndexError):
        await query.edit_message_text("❌ Error al procesar.")
        return
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass
    context.args = [str(oponente_id)]
    from combate import cmd_duelo
    await cmd_duelo(update, context)


def _detectar_color(zona_nombre: str) -> str:
    """Detecta el color de la zona a partir del nombre."""
    try:
        from datos_zona import ZONAS
        for z in ZONAS:
            if z["nombre"] == zona_nombre:
                tipo = z.get("tipo", "salvaje")
                if tipo == "ciudad":
                    return "ciudad"
                return z.get("color", "azul")
    except Exception:
        pass
    return "azul"


# ─── FUNCIÓN AUXILIAR: enviar/actualizar el menú ──────────────────────────────

async def enviar_teclado(update_or_message, context: ContextTypes.DEFAULT_TYPE,
                         texto: str = "⚡ Accesos rápidos actualizados.",
                         ubicacion: str = "ciudad"):
    """Envía un mensaje que actualiza el menú inferior. Respeta preferencia del jugador."""
    if hasattr(update_or_message, "message") and update_or_message.message:
        msg = update_or_message.message
    elif hasattr(update_or_message, "callback_query") and update_or_message.callback_query:
        msg = update_or_message.callback_query.message
    else:
        msg = update_or_message

    user_id = None
    if hasattr(update_or_message, "effective_user") and update_or_message.effective_user:
        user_id = update_or_message.effective_user.id
    elif hasattr(msg, "from_user") and msg.from_user:
        user_id = msg.from_user.id

    if user_id and _teclado_esta_oculto(user_id):
        await msg.reply_text(texto)
        return

    kb = get_teclado_salvaje(user_id or 0) if ubicacion == "salvaje" else get_teclado_principal(user_id or 0)
    await msg.reply_text(texto, reply_markup=kb)


# ─── REGISTRO ─────────────────────────────────────────────────────────────────

def registrar_handlers(app):
    # Botón "Ocultar menú" (prioridad alta)
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.Regex(r"^🔲 Ocultar menú$"),
            handle_ocultar_teclado
        ),
        group=0
    )
    # Botón "Actualizar menú"
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.Regex(r"^🔄 Actualizar menú$"),
            handle_actualizar_menu
        ),
        group=0
    )
    # Botón "Editar menú" (con y sin U+FE0F)
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.Regex(r"^⚙️? Editar menú$"),
            handle_editar_menu
        ),
        group=0
    )
    # Comandos /menu y /teclado (alias)
    app.add_handler(CommandHandler("menu", cmd_menu))
    app.add_handler(CommandHandler("teclado", cmd_menu))
    # Interceptar pulsaciones de botones de juego
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.Regex(
                "^(👤 Perfil|🏙\ufe0f? Ciudad|🎒 Inventario|✈\ufe0f? Viajar|"
                "⚔\ufe0f? Duelos|🏰 Gremio|⛏\ufe0f? Recolectar|🔍 Investigar|"
                "🏰 Mazmorra|⚔\ufe0f? Atacar jugador|🔐 Admin|🐛 Debug|📋 Comandos|📖 Guía|"
                "🏆 Rankings|🌑 Umbral|"
                "⚔\ufe0f? Atacar en guerra|🛡\ufe0f? Defender en guerra|⏭\ufe0f? Saltar guerra|"
                "🤖 Auto-Recolección|"
                "⚔\ufe0f? Emboscada PvP|"
                "🌐 Emboscada Zonas 🟡|🌐 Emboscada Zonas 🔴|🌐 Emboscada Zonas ⬛)$"
            ),
            handle_boton_rapido
        ),
        group=0
    )
    # Callback: mostrar menú desde botón inline
    app.add_handler(CallbackQueryHandler(cb_teclado_mostrar, pattern=r"^teclado_mostrar$"))
    # Callback selector PvP
    app.add_handler(CallbackQueryHandler(cb_tkpvp, pattern=r"^tkpvp_"))
    # Callback editor de menú
    app.add_handler(CallbackQueryHandler(cb_editor_menu, pattern=r"^editormenu_"))

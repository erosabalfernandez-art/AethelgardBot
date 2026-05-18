#!/usr/bin/env python3
# gremios.py — Sistema completo de gestión de gremios
#
# Flujo creación:
#   Botón "Crear Gremio" → pregunta nombre → pregunta descripción → confirmar → gremio creado
#
# Rangos (de mayor a menor):  fundador > lider > oficial > veterano > recluta > miembro
#   - Baúl (depositar): todos los rangos
#   - Baúl (tomar):     veterano o superior
#   - Invitar/expulsar: oficial o superior
#   - Cambiar rango:    lider o superior (no puede superar su propio rango)
#   - Editar descripción: lider o superior
#   - Disolver gremio:  solo fundador

import sqlite3
import os
from datetime import datetime
from typing import Optional, Dict, List
from html import escape as _he

def _esc_md(s: str) -> str:
    return str(s).replace("_", "\\_").replace("*", "\\*").replace("`", "\\`").replace("[", "\\[")

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, CommandHandler, CallbackQueryHandler,
    ConversationHandler, MessageHandler, filters
)

import db_helper
import economia
import superadmin as sa

DB_PATH = "aethelgard.db"

CONV_NOMBRE = 200
CONV_DESC   = 201
ADMIN_GREMIO_EDIT = 210

RANGOS_ORDEN = ["miembro", "recluta", "veterano", "oficial", "lider", "fundador"]

RANGO_PUEDE_INVITAR   = {"fundador", "lider", "oficial"}
RANGO_PUEDE_EXPULSAR  = {"fundador", "lider", "oficial"}
RANGO_PUEDE_ASCENDER  = {"fundador", "lider"}
RANGO_PUEDE_TOMAR_BAUL = {"fundador", "lider", "oficial", "veterano"}


# ==================== DB SETUP ====================
def _init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS baul_gremio (
        gremio_id INTEGER,
        nombre_item TEXT,
        cantidad INTEGER DEFAULT 0,
        PRIMARY KEY (gremio_id, nombre_item)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS config_gremios (
        clave TEXT PRIMARY KEY,
        valor TEXT
    )''')

    migraciones = [
        "ALTER TABLE gremios ADD COLUMN descripcion TEXT DEFAULT ''",
        "ALTER TABLE gremios ADD COLUMN lider_id INTEGER",
    ]
    for sql in migraciones:
        try:
            c.execute(sql)
        except Exception:
            pass

    conn.commit()
    conn.close()

_init_db()


# ==================== CONFIG ====================
def _get_config(clave: str, default) -> str:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT valor FROM config_gremios WHERE clave = ?", (clave,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else str(default)

def _set_config(clave: str, valor):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO config_gremios (clave, valor) VALUES (?, ?)", (clave, str(valor)))
    conn.commit()
    conn.close()

def _costo_creacion() -> int:
    return int(_get_config("costo_creacion_gremio", 5000))

def _nivel_minimo() -> int:
    return int(_get_config("nivel_minimo_gremio", 15))

def _capacidad_inicial() -> int:
    return int(_get_config("capacidad_inicial_gremio", 20))

def _max_invitaciones() -> int:
    return int(_get_config("max_invitaciones_gremio", 5))

def _max_miembros_gremio(gremio_id: int) -> int:
    """Capacidad efectiva según el nivel del gremio (delegada a gremios_niveles)."""
    try:
        import gremios_niveles as _gn
        return _gn.obtener_capacidad_gremio(gremio_id)
    except Exception:
        return _capacidad_inicial()

# Metadatos de cada clave configurable (para el panel)
_CONFIG_META = {
    "nivel_minimo_gremio":      ("📊 Nivel mínimo para crear",       "nivel",     15,   1,   100),
    "costo_creacion_gremio":    ("💎 Costo de creación (Eternium)",  "eternium",  5000, 0,  999999),
    "capacidad_inicial_gremio": ("👥 Capacidad inicial de miembros", "miembros",  20,   5,   500),
    "max_invitaciones_gremio":  ("✉️ Máx. invitaciones pendientes",  "invites",   5,    1,   50),
}

def _stats_gremios() -> dict:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM gremios")
    total_gremios = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM miembros_gremio")
    total_miembros = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM gremios WHERE nivel >= 5")
    gremios_alto_nivel = c.fetchone()[0]
    conn.close()
    return {"total": total_gremios, "miembros": total_miembros, "alto_nivel": gremios_alto_nivel}


# ==================== HELPERS ====================
def _obtener_gremio_de_jugador(user_id: int) -> Optional[Dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(
        "SELECT g.* FROM gremios g JOIN miembros_gremio m ON g.id = m.gremio_id WHERE m.jugador_id = ?",
        (user_id,)
    )
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def _obtener_gremio_por_id(gremio_id: int) -> Optional[Dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM gremios WHERE id = ?", (gremio_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def _obtener_gremio_por_nombre(nombre: str) -> Optional[Dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM gremios WHERE LOWER(nombre) = LOWER(?)", (nombre,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def _rango_de_jugador(user_id: int, gremio_id: int) -> Optional[str]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT rango FROM miembros_gremio WHERE jugador_id = ? AND gremio_id = ?", (user_id, gremio_id))
    row = c.fetchone()
    conn.close()
    return row["rango"] if row else None

def _rango_indice(rango: str) -> int:
    return RANGOS_ORDEN.index(rango) if rango in RANGOS_ORDEN else -1

def _obtener_miembros(gremio_id: int) -> List[Dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(
        """SELECT m.jugador_id, m.rango, m.fecha_ingreso, j.nombre_personaje
           FROM miembros_gremio m LEFT JOIN jugadores j ON j.user_id = m.jugador_id
           WHERE m.gremio_id = ? ORDER BY m.rowid""",
        (gremio_id,)
    )
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def _num_miembros(gremio_id: int) -> int:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM miembros_gremio WHERE gremio_id = ?", (gremio_id,))
    n = c.fetchone()[0]
    conn.close()
    return n

def _obtener_baul(gremio_id: int) -> List[Dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT nombre_item, cantidad FROM baul_gremio WHERE gremio_id = ? AND cantidad > 0", (gremio_id,))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def _agregar_baul(gremio_id: int, item: str, cantidad: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO baul_gremio (gremio_id, nombre_item, cantidad) VALUES (?, ?, ?) "
        "ON CONFLICT(gremio_id, nombre_item) DO UPDATE SET cantidad = cantidad + ?",
        (gremio_id, item, cantidad, cantidad)
    )
    conn.commit()
    conn.close()

def _quitar_baul(gremio_id: int, item: str, cantidad: int) -> bool:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT cantidad FROM baul_gremio WHERE gremio_id = ? AND nombre_item = ?", (gremio_id, item))
    row = c.fetchone()
    if not row or row[0] < cantidad:
        conn.close()
        return False
    c.execute("UPDATE baul_gremio SET cantidad = cantidad - ? WHERE gremio_id = ? AND nombre_item = ?",
              (cantidad, gremio_id, item))
    conn.commit()
    conn.close()
    return True

def _emoji_rango(rango: str) -> str:
    return {"fundador": "👑", "lider": "⭐", "oficial": "🔹", "veterano": "🛡️",
            "recluta": "⚔️", "miembro": "👤"}.get(rango, "👤")

def _en_ciudad(user_id: int) -> bool:
    """Retorna True si el jugador está en una ciudad."""
    try:
        import datos_zona as _dz
        zona_nombre = db_helper.obtener_zona_actual(user_id)
        return any(z["nombre"] == zona_nombre and z["tipo"] == "ciudad" for z in _dz.ZONAS)
    except Exception:
        return False


# ==================== SUBMENÚ MI GREMIO ====================
async def cb_mi_gremio_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    if not _en_ciudad(user_id):
        await query.edit_message_text("🏙️ Las actividades de gremio solo están disponibles en ciudades.")
        return
    try:
        import guia_contextual as _gc
        await _gc.enviar(user_id, context, "gremio_menu")
    except Exception:
        pass
    gremio = _obtener_gremio_de_jugador(user_id)
    if not gremio:
        kb_sin_gremio = InlineKeyboardMarkup([
            [InlineKeyboardButton("🏰 Crear Gremio",    callback_data="gremio_crear_inicio")],
            [InlineKeyboardButton("🔍 Buscar Gremios",  callback_data="gremio_buscar")],
            [InlineKeyboardButton("🔙 Volver",          callback_data="submenu_gremio")],
        ])
        await query.edit_message_text(
            "⚠️ *No perteneces a ningún gremio.*\n\n"
            "Puedes fundar el tuyo o buscar uno al que unirte:",
            parse_mode="Markdown",
            reply_markup=kb_sin_gremio
        )
        return

    rango = _rango_de_jugador(user_id, gremio["id"])
    miembros = _num_miembros(gremio["id"])
    kb = [
        [InlineKeyboardButton("📋 Info del Gremio",      callback_data="gremio_info")],
        [InlineKeyboardButton("👥 Ver Miembros",          callback_data="gremio_miembros")],
        [InlineKeyboardButton("📦 Baúl del Gremio",       callback_data="gremio_baul_ver")],
    ]
    if rango in RANGO_PUEDE_INVITAR:
        kb.append([InlineKeyboardButton("✉️ Invitar Jugador",    callback_data="gremio_invitar_info")])
    if rango in RANGO_PUEDE_EXPULSAR:
        kb.append([InlineKeyboardButton("👢 Expulsar Miembro",   callback_data="gremio_expulsar_info")])
    if rango in RANGO_PUEDE_ASCENDER:
        kb.append([InlineKeyboardButton("🎭 Cambiar Rango",      callback_data="gremio_rango_info")])
    if rango in {"fundador", "lider"}:
        kb.append([InlineKeyboardButton("📝 Editar Descripción",  callback_data="gremio_editar_desc")])
    if rango == "fundador":
        kb.append([InlineKeyboardButton("💥 Disolver Gremio",    callback_data="gremio_disolver_confirm")])
    if rango != "fundador":
        kb.append([InlineKeyboardButton("🚪 Abandonar Gremio",   callback_data="gremio_abandonar_confirm")])
    kb.append([InlineKeyboardButton("🔙 Volver",                callback_data="submenu_gremio")])

    await query.edit_message_text(
        f"🛡️ *{_esc_md(gremio['nombre'])}* — Nivel {gremio.get('nivel', 1)}\n"
        f"Tu rango: {_emoji_rango(rango)} {rango.capitalize()}\n"
        f"Miembros: {miembros}",
        reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown"
    )


# ==================== INFO DEL GREMIO ====================
async def cb_gremio_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    if not _en_ciudad(user_id):
        await query.edit_message_text("🏙️ Las actividades de gremio solo están disponibles en ciudades.")
        return
    gremio = _obtener_gremio_de_jugador(user_id)
    if not gremio:
        await query.edit_message_text("❌ No perteneces a ningún gremio.")
        return

    miembros = _num_miembros(gremio["id"])
    desc = gremio.get("descripcion") or "_Sin descripción_"
    fundador = db_helper.obtener_jugador(gremio.get("fundador_id") or 0)
    nombre_fundador = fundador["nombre_personaje"] if fundador else "Desconocido"
    nivel = gremio.get("nivel", 1)
    oro = gremio.get("banco_oro", 0)
    et  = gremio.get("banco_eternium", 0)

    texto = (
        f"🏰 *{_esc_md(gremio['nombre'])}*\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📖 {desc}\n\n"
        f"🌟 Nivel: {nivel}   |   👥 Miembros: {miembros}\n"
        f"⚔️ Facción: {gremio.get('faccion', '—')}\n"
        f"👑 Fundador: {nombre_fundador}\n"
        f"🪙 Banco: {oro} oro | {et} eternium\n"
        f"📅 Creado: {str(gremio.get('fecha_creacion', ''))[:10]}"
    )
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver", callback_data="cb_mi_gremio_menu")]])
    await query.edit_message_text(texto, reply_markup=kb, parse_mode="Markdown")


# ==================== LISTA MIEMBROS ====================
async def cb_gremio_miembros(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    if not _en_ciudad(user_id):
        await query.edit_message_text("🏙️ Las actividades de gremio solo están disponibles en ciudades.")
        return
    gremio = _obtener_gremio_de_jugador(user_id)
    if not gremio:
        await query.edit_message_text("❌ No perteneces a ningún gremio.")
        return

    miembros = _obtener_miembros(gremio["id"])
    lineas = [f"👥 *Miembros de {gremio['nombre']}*\n"]
    for m in miembros:
        nombre = m.get("nombre_personaje") or f"ID:{m['jugador_id']}"
        emoji = _emoji_rango(m["rango"])
        lineas.append(f"{emoji} {nombre} — {m['rango'].capitalize()}")
    texto = "\n".join(lineas)
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver", callback_data="cb_mi_gremio_menu")]])
    await query.edit_message_text(texto, reply_markup=kb, parse_mode="Markdown")


# ==================== BAÚL DEL GREMIO ====================
async def cb_gremio_baul_ver(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    if not _en_ciudad(user_id):
        await query.edit_message_text("🏙️ Las actividades de gremio solo están disponibles en ciudades.")
        return
    gremio = _obtener_gremio_de_jugador(user_id)
    if not gremio:
        await query.edit_message_text("❌ No perteneces a ningún gremio.")
        return

    rango = _rango_de_jugador(user_id, gremio["id"])
    items = _obtener_baul(gremio["id"])
    if items:
        lista = "\n".join(f"• {it['nombre_item']}: x{it['cantidad']}" for it in items)
    else:
        lista = "_El baúl está vacío._"

    # Límite de baúl por nivel
    try:
        from gremios_niveles import obtener_limite_baul_gremio
        limite_baul = obtener_limite_baul_gremio(gremio["id"])
        slots_usados = len(items)
        info_slots = f"📊 Slots: {slots_usados}/{limite_baul}"
    except Exception:
        info_slots = ""

    puede_tomar = rango in RANGO_PUEDE_TOMAR_BAUL
    kb = [
        [InlineKeyboardButton("📥 Depositar ítem", callback_data="gremio_baul_depositar_info")],
    ]
    if puede_tomar and items:
        kb.append([InlineKeyboardButton("📤 Tomar ítem", callback_data="gremio_baul_tomar_info")])
    kb.append([InlineKeyboardButton("🔙 Volver", callback_data="cb_mi_gremio_menu")])

    permisos = "_Puedes depositar y tomar ítems._" if puede_tomar else "_Solo puedes depositar. Para tomar necesitas rango Veterano o superior._"
    slots_line = f"\n{info_slots}" if info_slots else ""
    await query.edit_message_text(
        f"📦 *Baúl de {gremio['nombre']}*{slots_line}\n\n{lista}\n\n{permisos}",
        reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown"
    )

async def cb_gremio_baul_depositar_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver", callback_data="gremio_baul_ver")]])
    await query.edit_message_text(
        "📥 *Depositar ítem en el baúl*\n\nUsa el comando:\n`/depositar_baul <nombre_item> <cantidad>`\n\n"
        "_Ejemplo:_ `/depositar_baul mineral_hierro 10`",
        reply_markup=kb, parse_mode="Markdown"
    )

async def cb_gremio_baul_tomar_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    if not _en_ciudad(user_id):
        await query.edit_message_text("🏙️ Las actividades de gremio solo están disponibles en ciudades.")
        return
    gremio = _obtener_gremio_de_jugador(user_id)
    if not gremio:
        await query.edit_message_text("❌ No perteneces a ningún gremio.")
        return

    items = _obtener_baul(gremio["id"])
    if not items:
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver", callback_data="gremio_baul_ver")]])
        await query.edit_message_text("El baúl está vacío.", reply_markup=kb)
        return

    kb_rows = [[InlineKeyboardButton(f"📤 {it['nombre_item']} (x{it['cantidad']})",
               callback_data=f"gremio_tomar_item_{it['nombre_item']}_1")] for it in items]
    kb_rows.append([InlineKeyboardButton("🔙 Volver", callback_data="gremio_baul_ver")])
    await query.edit_message_text(
        "📤 *Tomar del baúl*\n\nSelecciona un ítem (se tomará 1 unidad):\n\n"
        "_O usa:_ `/tomar_baul <item> <cantidad>`",
        reply_markup=InlineKeyboardMarkup(kb_rows), parse_mode="Markdown"
    )

async def cb_gremio_tomar_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    if not _en_ciudad(user_id):
        await query.answer("🏙️ Solo disponible en ciudades.", show_alert=True)
        return
    parts = query.data.split("_", 4)
    if len(parts) < 5:
        await query.answer("Error en datos.", show_alert=True)
        return
    nombre_item = parts[3]
    try:
        cantidad = int(parts[4])
    except (ValueError, IndexError):
        await query.answer("❌ Error en los datos del ítem.", show_alert=True)
        return

    gremio = _obtener_gremio_de_jugador(user_id)
    if not gremio:
        await query.edit_message_text("❌ No perteneces a ningún gremio.")
        return
    rango = _rango_de_jugador(user_id, gremio["id"])
    if rango not in RANGO_PUEDE_TOMAR_BAUL:
        await query.answer("❌ No tienes permiso para tomar del baúl.", show_alert=True)
        return
    if not _quitar_baul(gremio["id"], nombre_item, cantidad):
        await query.answer("❌ No hay suficiente cantidad en el baúl.", show_alert=True)
        return
    db_helper.agregar_item(user_id, nombre_item, cantidad)
    await query.edit_message_text(
        f"✅ Tomaste {cantidad}x *{_esc_md(nombre_item)}* del baúl del gremio.",
        parse_mode="Markdown"
    )


# ==================== COMANDOS DE BAÚL ====================
async def cmd_depositar_baul(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not _en_ciudad(user_id):
        await update.effective_message.reply_text("🏙️ Las actividades de gremio solo están disponibles en ciudades.")
        return
    gremio = _obtener_gremio_de_jugador(user_id)
    if not gremio:
        await update.effective_message.reply_text("❌ No perteneces a ningún gremio.")
        return
    if not context.args or len(context.args) < 2:
        await update.effective_message.reply_text("Uso: /depositar_baul <nombre_item> <cantidad>")
        return
    nombre_item = context.args[0]
    try:
        cantidad = int(context.args[1])
        if cantidad <= 0:
            raise ValueError
    except ValueError:
        await update.effective_message.reply_text("La cantidad debe ser un número positivo.")
        return

    inv = db_helper.obtener_inventario(user_id)
    en_inv = next((it for it in inv if it["nombre"] == nombre_item), None)
    if not en_inv or en_inv["cantidad"] < cantidad:
        await update.effective_message.reply_text(f"❌ No tienes {cantidad}x {nombre_item} en tu inventario.")
        return

    # Verificar límite del baúl según nivel del gremio
    try:
        from gremios_niveles import obtener_limite_baul_gremio
        limite_baul = obtener_limite_baul_gremio(gremio["id"])
        items_actuales = _obtener_baul(gremio["id"])
        slots_usados = len(items_actuales)
        if slots_usados >= limite_baul:
            await update.effective_message.reply_text(
                f"❌ El baúl del gremio está lleno ({slots_usados}/{limite_baul} tipos de objeto).\n"
                f"Sube el nivel del gremio para ampliar el espacio."
            )
            return
    except Exception:
        pass

    db_helper.quitar_item(user_id, nombre_item, cantidad)
    _agregar_baul(gremio["id"], nombre_item, cantidad)
    await update.effective_message.reply_text(
        f"✅ Depositaste {cantidad}x *{_esc_md(nombre_item)}* en el baúl de {_esc_md(gremio['nombre'])}.",
        parse_mode="Markdown"
    )

async def cmd_tomar_baul(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not _en_ciudad(user_id):
        await update.effective_message.reply_text("🏙️ Las actividades de gremio solo están disponibles en ciudades.")
        return
    gremio = _obtener_gremio_de_jugador(user_id)
    if not gremio:
        await update.effective_message.reply_text("❌ No perteneces a ningún gremio.")
        return
    rango = _rango_de_jugador(user_id, gremio["id"])
    if rango not in RANGO_PUEDE_TOMAR_BAUL:
        await update.effective_message.reply_text("❌ Necesitas rango Veterano o superior para tomar del baúl.")
        return
    if not context.args or len(context.args) < 2:
        await update.effective_message.reply_text("Uso: /tomar_baul <nombre_item> <cantidad>")
        return
    nombre_item = context.args[0]
    try:
        cantidad = int(context.args[1])
        if cantidad <= 0:
            raise ValueError
    except ValueError:
        await update.effective_message.reply_text("La cantidad debe ser un número positivo.")
        return

    if not _quitar_baul(gremio["id"], nombre_item, cantidad):
        await update.effective_message.reply_text(f"❌ El baúl no tiene {cantidad}x {nombre_item}.")
        return
    db_helper.agregar_item(user_id, nombre_item, cantidad)
    # Notificar a líderes y fundador sobre la extracción del baúl
    jug = db_helper.obtener_jugador(user_id)
    nombre_toma = jug["nombre_personaje"] if jug else str(user_id)
    for m in _obtener_miembros(gremio["id"]):
        if m["jugador_id"] != user_id and m["rango"] in ("fundador", "lider"):
            db_helper.agregar_notificacion(m["jugador_id"],
                f"🎒 {nombre_toma} extrajo {cantidad}x {nombre_item} del baúl del gremio {gremio['nombre']}.")
    await update.effective_message.reply_text(
        f"✅ Tomaste {cantidad}x *{_esc_md(nombre_item)}* del baúl del gremio.",
        parse_mode="Markdown"
    )


# ==================== INVITAR / EXPULSAR / RANGOS ====================
async def cb_gremio_invitar_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver", callback_data="cb_mi_gremio_menu")]])
    await query.edit_message_text(
        "✉️ *Invitar jugador*\n\nUsa:\n`/invitar_gremio <user_id>`\n\n"
        "El jugador debe darte su ID de usuario de Telegram.\n"
        "Puede obtenerlo usando el comando /perfil.",
        reply_markup=kb, parse_mode="Markdown"
    )

async def cmd_invitar_gremio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not _en_ciudad(user_id):
        await update.effective_message.reply_text("🏙️ Las actividades de gremio solo están disponibles en ciudades.")
        return
    gremio = _obtener_gremio_de_jugador(user_id)
    if not gremio:
        await update.effective_message.reply_text("❌ No perteneces a ningún gremio.")
        return
    rango = _rango_de_jugador(user_id, gremio["id"])
    if rango not in RANGO_PUEDE_INVITAR:
        await update.effective_message.reply_text("❌ Necesitas rango Oficial o superior para invitar miembros.")
        return
    if not context.args:
        await update.effective_message.reply_text("Uso: /invitar_gremio <user_id>")
        return
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.effective_message.reply_text("El user_id debe ser un número.")
        return
    if _obtener_gremio_de_jugador(target_id):
        await update.effective_message.reply_text("❌ Ese jugador ya pertenece a un gremio.")
        return
    jug_target = db_helper.obtener_jugador(target_id)
    if not jug_target:
        await update.effective_message.reply_text("❌ Jugador no encontrado.")
        return

    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Aceptar", callback_data=f"gremio_inv_aceptar_{gremio['id']}_{user_id}"),
        InlineKeyboardButton("❌ Rechazar", callback_data=f"gremio_inv_rechazar_{gremio['id']}_{user_id}"),
    ]])
    try:
        await context.bot.send_message(
            chat_id=target_id,
            text=(
                f"📩 *¡Invitación de gremio!*\n\n"
                f"El gremio *{_esc_md(gremio['nombre'])}* te invita a unirte.\n"
                f"Nivel del gremio: {gremio.get('nivel', 1)}\n"
                f"Miembros: {_num_miembros(gremio['id'])}\n\n"
                f"¿Aceptas?"
            ),
            reply_markup=kb, parse_mode="Markdown"
        )
        await update.effective_message.reply_text(f"✅ Invitación enviada a {jug_target['nombre_personaje']}.")
    except Exception:
        await update.effective_message.reply_text(f"❌ No se pudo enviar la invitación. El jugador puede tener bloqueado el bot.")

async def cb_gremio_inv_aceptar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    parts = query.data.split("_")
    try:
        gremio_id = int(parts[3])
        invitador_id = int(parts[4])
    except (ValueError, IndexError):
        await query.edit_message_text("❌ Error al procesar la invitación.")
        return

    if _obtener_gremio_de_jugador(user_id):
        await query.edit_message_text("⚠️ Ya perteneces a un gremio.")
        return
    gremio = _obtener_gremio_por_id(gremio_id)
    if not gremio:
        await query.edit_message_text("⚠️ El gremio ya no existe.")
        return

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO miembros_gremio (gremio_id, jugador_id, rango) VALUES (?, ?, 'recluta')",
              (gremio_id, user_id))
    conn.commit()
    conn.close()

    jug = db_helper.obtener_jugador(user_id)
    nombre = jug["nombre_personaje"] if jug else str(user_id)
    await query.edit_message_text(f"✅ ¡Bienvenido al gremio <b>{_he(gremio['nombre'])}</b>! Tu rango inicial: Recluta.", parse_mode="HTML")
    db_helper.agregar_notificacion(invitador_id, f"✅ {nombre} aceptó la invitación y se unió a {gremio['nombre']}.")
    try:
        import misiones as _mis
        _mis.completar_mision(user_id, "unirse_gremio", context)
    except Exception:
        pass

async def cb_gremio_inv_rechazar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_")
    # callback: gremio_inv_rechazar_{gremio_id}_{invitador_id}
    if len(parts) >= 5:
        try:
            gremio_id_inv = int(parts[3])
            invitador_id = int(parts[4])
            jug = db_helper.obtener_jugador(query.from_user.id)
            nombre = jug["nombre_personaje"] if jug else str(query.from_user.id)
            gremio_inv = _obtener_gremio_por_id(gremio_id_inv)
            g_nombre = gremio_inv["nombre"] if gremio_inv else "el gremio"
            db_helper.agregar_notificacion(invitador_id,
                f"❌ {nombre} rechazó la invitación al gremio {g_nombre}.")
        except Exception:
            pass
    await query.edit_message_text("❌ Invitación rechazada.")

async def cb_gremio_expulsar_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    if not _en_ciudad(user_id):
        await query.edit_message_text("🏙️ Las actividades de gremio solo están disponibles en ciudades.")
        return
    gremio = _obtener_gremio_de_jugador(user_id)
    if not gremio:
        await query.edit_message_text("❌ No perteneces a ningún gremio.")
        return

    miembros = _obtener_miembros(gremio["id"])
    mi_rango = _rango_de_jugador(user_id, gremio["id"])
    mi_idx = _rango_indice(mi_rango)
    expulsables = [m for m in miembros if m["jugador_id"] != user_id and _rango_indice(m["rango"]) < mi_idx]

    if not expulsables:
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver", callback_data="cb_mi_gremio_menu")]])
        await query.edit_message_text("No hay miembros que puedas expulsar.", reply_markup=kb)
        return

    kb_rows = [[InlineKeyboardButton(
        f"👢 {m.get('nombre_personaje') or m['jugador_id']} ({m['rango']})",
        callback_data=f"gremio_expulsar_{m['jugador_id']}"
    )] for m in expulsables]
    kb_rows.append([InlineKeyboardButton("🔙 Volver", callback_data="cb_mi_gremio_menu")])
    await query.edit_message_text("Selecciona al miembro que deseas expulsar:", reply_markup=InlineKeyboardMarkup(kb_rows))

async def cb_gremio_expulsar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    if not _en_ciudad(user_id):
        await query.edit_message_text("🏙️ Las actividades de gremio solo están disponibles en ciudades.")
        return
    try:
        target_id = int(query.data.split("_")[-1])
    except (ValueError, IndexError):
        await query.answer("❌ Error de datos al expulsar.", show_alert=True)
        return
    gremio = _obtener_gremio_de_jugador(user_id)
    if not gremio:
        await query.edit_message_text("❌ No perteneces a ningún gremio.")
        return
    mi_rango = _rango_de_jugador(user_id, gremio["id"])
    su_rango = _rango_de_jugador(target_id, gremio["id"])
    if not su_rango or _rango_indice(su_rango) >= _rango_indice(mi_rango):
        await query.answer("❌ No puedes expulsar a alguien de igual o mayor rango.", show_alert=True)
        return

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM miembros_gremio WHERE gremio_id = ? AND jugador_id = ?", (gremio["id"], target_id))
    conn.commit()
    conn.close()
    jug_target = db_helper.obtener_jugador(target_id)
    nombre = jug_target["nombre_personaje"] if jug_target else str(target_id)
    await query.edit_message_text(f"✅ <b>{_he(nombre)}</b> ha sido expulsado del gremio.", parse_mode="HTML")
    db_helper.agregar_notificacion(target_id, f"⚠️ Has sido expulsado del gremio {gremio['nombre']}.")
    # Notificar a líderes y fundador (excepto al que expulsó)
    jug_expulsor = db_helper.obtener_jugador(user_id)
    nombre_expulsor = jug_expulsor["nombre_personaje"] if jug_expulsor else str(user_id)
    for m in _obtener_miembros(gremio["id"]):
        if m["jugador_id"] != user_id and m["rango"] in ("fundador", "lider"):
            db_helper.agregar_notificacion(m["jugador_id"],
                f"👢 {nombre} fue expulsado del gremio {gremio['nombre']} por {nombre_expulsor}.")

async def cb_gremio_rango_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver", callback_data="cb_mi_gremio_menu")]])
    await query.edit_message_text(
        "🎭 *Cambiar rango de un miembro*\n\n"
        "Usa:\n`/rango_gremio <user_id> <rango>`\n\n"
        "Rangos disponibles:\n"
        "👑 `fundador` — solo hay uno\n"
        "⭐ `lider` — co-lider del gremio\n"
        "🔹 `oficial` — puede invitar y expulsar\n"
        "🛡️ `veterano` — puede tomar del baúl\n"
        "⚔️ `recluta` — puede depositar\n"
        "👤 `miembro` — miembro básico",
        reply_markup=kb, parse_mode="Markdown"
    )

async def cmd_rango_gremio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not _en_ciudad(user_id):
        await update.effective_message.reply_text("🏙️ Las actividades de gremio solo están disponibles en ciudades.")
        return
    gremio = _obtener_gremio_de_jugador(user_id)
    if not gremio:
        await update.effective_message.reply_text("❌ No perteneces a ningún gremio.")
        return
    mi_rango = _rango_de_jugador(user_id, gremio["id"])
    if mi_rango not in RANGO_PUEDE_ASCENDER:
        await update.effective_message.reply_text("❌ Necesitas ser Líder o Fundador para cambiar rangos.")
        return
    if not context.args or len(context.args) < 2:
        await update.effective_message.reply_text("Uso: /rango_gremio <user_id> <rango>")
        return
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.effective_message.reply_text("El user_id debe ser un número.")
        return
    nuevo_rango = context.args[1].lower()
    if nuevo_rango not in RANGOS_ORDEN:
        await update.effective_message.reply_text(f"Rango inválido. Opciones: {', '.join(RANGOS_ORDEN)}")
        return
    if nuevo_rango == "fundador":
        await update.effective_message.reply_text("❌ No puedes asignar el rango de Fundador.")
        return
    su_rango = _rango_de_jugador(target_id, gremio["id"])
    if not su_rango:
        await update.effective_message.reply_text("❌ Ese jugador no está en tu gremio.")
        return
    if _rango_indice(nuevo_rango) >= _rango_indice(mi_rango):
        await update.effective_message.reply_text("❌ No puedes asignar un rango igual o superior al tuyo.")
        return

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE miembros_gremio SET rango = ? WHERE gremio_id = ? AND jugador_id = ?",
              (nuevo_rango, gremio["id"], target_id))
    conn.commit()
    conn.close()
    jug_t = db_helper.obtener_jugador(target_id)
    nombre = jug_t["nombre_personaje"] if jug_t else str(target_id)
    emoji = _emoji_rango(nuevo_rango)
    await update.effective_message.reply_text(f"✅ {_he(nombre)} ahora tiene el rango {emoji} <b>{_he(nuevo_rango.capitalize())}</b>.", parse_mode="HTML")
    db_helper.agregar_notificacion(target_id, f"🎭 Tu rango en {gremio['nombre']} cambió a: {nuevo_rango.capitalize()}.")


# ==================== EDITAR DESCRIPCIÓN ====================
async def cb_gremio_editar_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    if not _en_ciudad(user_id):
        await query.edit_message_text("🏙️ Las actividades de gremio solo están disponibles en ciudades.")
        return ConversationHandler.END
    gremio = _obtener_gremio_de_jugador(user_id)
    if not gremio:
        await query.edit_message_text("❌ No perteneces a ningún gremio.")
        return
    mi_rango = _rango_de_jugador(user_id, gremio["id"])
    if mi_rango not in {"fundador", "lider"}:
        await query.answer("❌ Solo el líder puede editar la descripción.", show_alert=True)
        return
    context.user_data["gremio_editando_desc"] = gremio["id"]
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancelar", callback_data="cb_mi_gremio_menu")]])
    await query.edit_message_text(
        "📝 Escribe la nueva descripción del gremio (máx. 150 caracteres):",
        reply_markup=kb
    )
    return CONV_DESC

async def _recibir_desc_edicion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    gremio_id = context.user_data.get("gremio_editando_desc")
    if not gremio_id:
        return ConversationHandler.END
    desc = update.message.text.strip()[:150]
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE gremios SET descripcion = ? WHERE id = ?", (desc, gremio_id))
    conn.commit()
    conn.close()
    context.user_data.pop("gremio_editando_desc", None)
    await update.effective_message.reply_text("✅ Descripción del gremio actualizada.")
    return ConversationHandler.END


# ==================== ABANDONAR / DISOLVER ====================
async def cb_gremio_abandonar_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Confirmar abandono", callback_data="gremio_abandonar_ok"),
        InlineKeyboardButton("❌ Cancelar", callback_data="cb_mi_gremio_menu"),
    ]])
    await query.edit_message_text("⚠️ ¿Seguro que quieres abandonar el gremio?\nPerderás tu rango y acceso al baúl.", reply_markup=kb)

async def cb_gremio_abandonar_ok(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    if not _en_ciudad(user_id):
        await query.edit_message_text("🏙️ Las actividades de gremio solo están disponibles en ciudades.")
        return
    gremio = _obtener_gremio_de_jugador(user_id)
    if not gremio:
        await query.edit_message_text("Ya no perteneces a ningún gremio.")
        return
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    miembros_antes = _obtener_miembros(gremio["id"])
    c.execute("DELETE FROM miembros_gremio WHERE gremio_id = ? AND jugador_id = ?", (gremio["id"], user_id))
    conn.commit()
    conn.close()
    await query.edit_message_text(f"✅ Has abandonado el gremio <b>{_he(gremio['nombre'])}</b>.", parse_mode="HTML")
    # Notificar a líderes y fundador
    jug = db_helper.obtener_jugador(user_id)
    nombre = jug["nombre_personaje"] if jug else str(user_id)
    for m in miembros_antes:
        if m["jugador_id"] != user_id and m["rango"] in ("fundador", "lider"):
            db_helper.agregar_notificacion(m["jugador_id"],
                f"🚪 {nombre} ha abandonado el gremio {gremio['nombre']}.")

async def cb_gremio_disolver_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    if not _en_ciudad(user_id):
        await query.edit_message_text("🏙️ Las actividades de gremio solo están disponibles en ciudades.")
        return
    gremio = _obtener_gremio_de_jugador(user_id)
    if not gremio or _rango_de_jugador(user_id, gremio["id"]) != "fundador":
        await query.answer("❌ Solo el fundador puede disolver el gremio.", show_alert=True)
        return
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("💥 Disolver definitivamente", callback_data="gremio_disolver_ok"),
        InlineKeyboardButton("❌ Cancelar", callback_data="cb_mi_gremio_menu"),
    ]])
    await query.edit_message_text(
        f"⚠️ ¿Disolver <b>{_he(gremio['nombre'])}</b> permanentemente?\n"
        f"Todos los miembros serán expulsados y el baúl se vaciará.",
        reply_markup=kb, parse_mode="HTML"
    )

async def cb_gremio_disolver_ok(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    if not _en_ciudad(user_id):
        await query.edit_message_text("🏙️ Las actividades de gremio solo están disponibles en ciudades.")
        return
    gremio = _obtener_gremio_de_jugador(user_id)
    if not gremio or _rango_de_jugador(user_id, gremio["id"]) != "fundador":
        await query.answer("❌ Sin permiso.", show_alert=True)
        return

    miembros = _obtener_miembros(gremio["id"])
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM miembros_gremio WHERE gremio_id = ?", (gremio["id"],))
    c.execute("DELETE FROM baul_gremio WHERE gremio_id = ?", (gremio["id"],))
    c.execute("DELETE FROM gremios WHERE id = ?", (gremio["id"],))
    conn.commit()
    conn.close()

    for m in miembros:
        if m["jugador_id"] != user_id:
            db_helper.agregar_notificacion(m["jugador_id"], f"💥 El gremio {gremio['nombre']} ha sido disuelto.")
    await query.edit_message_text(f"💥 El gremio <b>{_he(gremio['nombre'])}</b> ha sido disuelto.", parse_mode="HTML")


# ==================== BUSCAR GREMIOS / RANKING ====================
async def cb_gremio_buscar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(
        "SELECT g.*, COUNT(m.jugador_id) as total_miembros "
        "FROM gremios g LEFT JOIN miembros_gremio m ON g.id = m.gremio_id "
        "GROUP BY g.id ORDER BY g.nivel DESC, total_miembros DESC LIMIT 15"
    )
    gremios = [dict(r) for r in c.fetchall()]
    conn.close()

    if not gremios:
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver", callback_data="submenu_gremio")]])
        await query.edit_message_text("Aún no hay gremios creados.", reply_markup=kb)
        return

    lineas = ["🏆 *Ranking de Gremios*\nPulsa un gremio para ver detalles y solicitar unirte:\n"]
    medallas = ["🥇", "🥈", "🥉"]
    botones = []
    for i, g in enumerate(gremios):
        medal = medallas[i] if i < 3 else f"{i+1}."
        lineas.append(f"{medal} *{_esc_md(g['nombre'])}* (Nv.{g.get('nivel',1)}) | 👥{g['total_miembros']}")
        botones.append([InlineKeyboardButton(
            f"{medal} {g['nombre']} (Nv.{g.get('nivel',1)}) 👥{g['total_miembros']}",
            callback_data=f"gremio_ver_{g['id']}"
        )])

    botones.append([InlineKeyboardButton("🔙 Volver", callback_data="submenu_gremio")])
    kb = InlineKeyboardMarkup(botones)
    await query.edit_message_text("\n".join(lineas), reply_markup=kb, parse_mode="Markdown")


async def cb_gremio_ver(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    try:
        gremio_id = int(query.data.split("_")[2])
    except (ValueError, IndexError):
        await query.edit_message_text("❌ Gremio no válido.")
        return

    gremio = _obtener_gremio_por_id(gremio_id)
    if not gremio:
        await query.edit_message_text("❌ Gremio no encontrado.")
        return

    miembros_count = _num_miembros(gremio_id)
    max_m = _max_miembros_gremio(gremio_id)
    desc = gremio.get("descripcion") or "_Sin descripción_"
    fundador = db_helper.obtener_jugador(gremio.get("fundador_id") or 0)
    nombre_fundador = fundador["nombre_personaje"] if fundador else "Desconocido"

    texto = (
        f"🏰 *{_esc_md(gremio['nombre'])}*\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📖 {desc}\n\n"
        f"🌟 Nivel: {gremio.get('nivel', 1)}   |   👥 {miembros_count}/{max_m} miembros\n"
        f"⚔️ Facción: {gremio.get('faccion', '—')}\n"
        f"👑 Fundador: {_esc_md(nombre_fundador)}\n"
        f"📅 Creado: {str(gremio.get('fecha_creacion', ''))[:10]}"
    )

    mi_gremio = _obtener_gremio_de_jugador(user_id)
    botones = []
    if mi_gremio:
        botones.append([InlineKeyboardButton("ℹ️ Ya perteneces a un gremio", callback_data="gremio_buscar")])
    elif miembros_count >= max_m:
        botones.append([InlineKeyboardButton("🔒 Gremio lleno", callback_data="gremio_buscar")])
    else:
        botones.append([InlineKeyboardButton("📨 Solicitar unirse", callback_data=f"gremio_solicitar_{gremio_id}")])
    botones.append([InlineKeyboardButton("🔙 Volver", callback_data="gremio_buscar")])
    await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(botones), parse_mode="Markdown")


async def cb_gremio_solicitar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    try:
        gremio_id = int(query.data.split("_")[2])
    except (ValueError, IndexError):
        await query.edit_message_text("❌ Solicitud no válida.")
        return

    if _obtener_gremio_de_jugador(user_id):
        await query.edit_message_text("⚠️ Ya perteneces a un gremio. Abandónalo antes de solicitar unirte a otro.")
        return

    gremio = _obtener_gremio_por_id(gremio_id)
    if not gremio:
        await query.edit_message_text("❌ Gremio no encontrado.")
        return

    if _num_miembros(gremio_id) >= _max_miembros_gremio(gremio_id):
        await query.edit_message_text("🔒 El gremio está lleno.")
        return

    jug = db_helper.obtener_jugador(user_id)
    nombre_solicitante = jug["nombre_personaje"] if jug else f"ID:{user_id}"

    lider_id = gremio.get("lider_id") or gremio.get("fundador_id")
    if lider_id:
        kb_lider = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Aceptar", callback_data=f"gremio_req_aceptar_{gremio_id}_{user_id}")],
            [InlineKeyboardButton("❌ Rechazar", callback_data=f"gremio_req_rechazar_{gremio_id}_{user_id}")]
        ])
        try:
            await context.bot.send_message(
                chat_id=lider_id,
                text=(
                    f"📨 *{_esc_md(nombre_solicitante)}* quiere unirse a *{_esc_md(gremio['nombre'])}*.\n"
                    f"¿Aceptas la solicitud?"
                ),
                reply_markup=kb_lider,
                parse_mode="Markdown"
            )
        except Exception:
            pass

    await query.edit_message_text(
        f"✅ Solicitud enviada al líder de *{_esc_md(gremio['nombre'])}*.\n"
        f"Recibirás una notificación cuando acepten o rechacen tu solicitud.",
        parse_mode="Markdown"
    )


async def cb_gremio_req_aceptar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_")
    try:
        gremio_id = int(parts[3])
        solicitante_id = int(parts[4])
    except (ValueError, IndexError):
        await query.edit_message_text("❌ Error al procesar la solicitud.")
        return

    gremio = _obtener_gremio_por_id(gremio_id)
    if not gremio:
        await query.edit_message_text("⚠️ El gremio ya no existe.")
        return

    if _obtener_gremio_de_jugador(solicitante_id):
        await query.edit_message_text("⚠️ El solicitante ya pertenece a otro gremio.")
        return

    if _num_miembros(gremio_id) >= _max_miembros_gremio(gremio_id):
        await query.edit_message_text("🔒 El gremio está lleno.")
        return

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO miembros_gremio (gremio_id, jugador_id, rango) VALUES (?, ?, 'recluta')",
              (gremio_id, solicitante_id))
    conn.commit()
    conn.close()

    jug = db_helper.obtener_jugador(solicitante_id)
    nombre = jug["nombre_personaje"] if jug else str(solicitante_id)
    await query.edit_message_text(
        f"✅ <b>{_he(nombre)}</b> ha sido aceptado en el gremio <b>{_he(gremio['nombre'])}</b>.",
        parse_mode="HTML"
    )
    db_helper.agregar_notificacion(solicitante_id,
        f"✅ Tu solicitud para unirte a {gremio['nombre']} fue aceptada. ¡Bienvenido/a!")
    try:
        import misiones as _mis
        _mis.completar_mision(solicitante_id, "unirse_gremio", context)
    except Exception:
        pass


async def cb_gremio_req_rechazar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_")
    try:
        gremio_id = int(parts[3])
        solicitante_id = int(parts[4])
    except (ValueError, IndexError):
        await query.edit_message_text("❌ Error al procesar la solicitud.")
        return

    gremio = _obtener_gremio_por_id(gremio_id)
    g_nombre = gremio["nombre"] if gremio else "el gremio"
    await query.edit_message_text("❌ Solicitud rechazada.")
    db_helper.agregar_notificacion(solicitante_id,
        f"❌ Tu solicitud para unirte a {g_nombre} fue rechazada.")


# ==================== CREAR GREMIO (ConversationHandler) ====================
async def cb_gremio_crear_inicio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    if sa.verificar_baneado(user_id):
        await query.edit_message_text("❌ Estás baneado.")
        return ConversationHandler.END

    if not _en_ciudad(user_id):
        await query.edit_message_text("🏙️ Solo puedes crear un gremio desde una ciudad.")
        return ConversationHandler.END

    if _obtener_gremio_de_jugador(user_id):
        await query.edit_message_text("⚠️ Ya perteneces a un gremio. Abandónalo antes de crear uno nuevo.")
        return ConversationHandler.END

    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        await query.edit_message_text("❌ Jugador no encontrado.")
        return ConversationHandler.END

    nivel_min = _nivel_minimo()
    if jug.get("nivel", 1) < nivel_min:
        await query.edit_message_text(
            f"❌ Necesitas nivel *{nivel_min}* para crear un gremio.\n"
            f"Tu nivel actual: *{jug.get('nivel', 1)}*\n\n"
            f"_(El nivel mínimo corresponde a poder acceder a la Zona Negra)_",
            parse_mode="Markdown"
        )
        return ConversationHandler.END

    costo = _costo_creacion()
    saldos = economia.obtener_saldos(user_id)
    if saldos["eternium"] < costo:
        await query.edit_message_text(
            f"❌ Necesitas *{costo} eternium* para crear un gremio.\n"
            f"Tienes: *{saldos['eternium']} eternium*",
            parse_mode="Markdown"
        )
        return ConversationHandler.END

    context.user_data["crear_gremio_faccion"] = jug.get("faccion", "Neutral")
    context.user_data["crear_gremio_fundador"] = user_id
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancelar", callback_data="gremio_crear_cancelar")]])
    await query.edit_message_text(
        f"🏰 *Crear Gremio*\n\n"
        f"Costo: *{costo} eternium*\n\n"
        f"Escribe el *nombre* de tu gremio (3–24 caracteres, sin espacios):",
        reply_markup=kb, parse_mode="Markdown"
    )
    return CONV_NOMBRE

async def _recibir_nombre_gremio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nombre = update.message.text.strip()
    if len(nombre) < 3 or len(nombre) > 24 or " " in nombre:
        await update.effective_message.reply_text(
            "❌ Nombre inválido. Debe tener entre 3 y 24 caracteres sin espacios. Intenta de nuevo:"
        )
        return CONV_NOMBRE

    if _obtener_gremio_por_nombre(nombre):
        await update.effective_message.reply_text("❌ Ya existe un gremio con ese nombre. Elige otro:")
        return CONV_NOMBRE

    context.user_data["crear_gremio_nombre"] = nombre
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("➡️ Sin descripción", callback_data="gremio_crear_skip_desc"),
        InlineKeyboardButton("❌ Cancelar", callback_data="gremio_crear_cancelar"),
    ]])
    await update.effective_message.reply_text(
        f"✅ Nombre: *{nombre}*\n\nAhora escribe una *descripción* para tu gremio (máx. 150 caracteres)\n"
        f"o pulsa *Sin descripción* para omitirla:",
        reply_markup=kb, parse_mode="Markdown"
    )
    return CONV_DESC

async def _recibir_desc_gremio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    desc = update.message.text.strip()[:150]
    context.user_data["crear_gremio_desc"] = desc
    return await _confirmar_creacion_gremio(update, context, via_callback=False)

async def cb_gremio_crear_skip_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["crear_gremio_desc"] = ""
    return await _confirmar_creacion_gremio(update, context, via_callback=True, query=query)

async def _confirmar_creacion_gremio(update, context, via_callback=False, query=None):
    nombre = context.user_data.get("crear_gremio_nombre", "")
    desc   = context.user_data.get("crear_gremio_desc", "")
    costo  = _costo_creacion()
    tag    = nombre[:4].upper()

    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Confirmar creación", callback_data="gremio_crear_confirmar"),
        InlineKeyboardButton("❌ Cancelar",           callback_data="gremio_crear_cancelar"),
    ]])
    texto = (
        f"🏰 *Resumen de tu Gremio*\n\n"
        f"Nombre: *{nombre}*\n"
        f"Tag: *[{tag}]*\n"
        f"Descripción: _{desc or 'Sin descripción'}_\n"
        f"Costo: *{costo} eternium*\n\n"
        f"¿Confirmas la creación?"
    )
    if via_callback and query:
        await query.edit_message_text(texto, reply_markup=kb, parse_mode="Markdown")
    else:
        await update.effective_message.reply_text(texto, reply_markup=kb, parse_mode="Markdown")
    return ConversationHandler.END

async def cb_gremio_crear_confirmar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    nombre = context.user_data.get("crear_gremio_nombre")
    desc   = context.user_data.get("crear_gremio_desc", "")
    faccion = context.user_data.get("crear_gremio_faccion", "Neutral")

    if not nombre:
        await query.edit_message_text("❌ Sesión expirada. Vuelve a iniciar el proceso.")
        return

    if _obtener_gremio_de_jugador(user_id):
        await query.edit_message_text("⚠️ Ya perteneces a un gremio.")
        context.user_data.clear()
        return

    if _obtener_gremio_por_nombre(nombre):
        await query.edit_message_text("❌ Ya existe un gremio con ese nombre. El proceso fue cancelado.")
        context.user_data.clear()
        return

    costo = _costo_creacion()
    saldos = economia.obtener_saldos(user_id)
    if saldos["eternium"] < costo:
        await query.edit_message_text(f"❌ No tienes suficiente eternium ({costo} requerido).")
        context.user_data.clear()
        return

    tag = nombre[:4].upper()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute(
            "INSERT INTO gremios (nombre, tag, faccion, nivel, fundador_id, lider_id, descripcion) VALUES (?,?,?,1,?,?,?)",
            (nombre, tag, faccion, user_id, user_id, desc)
        )
        gremio_id = c.lastrowid
        c.execute("INSERT INTO miembros_gremio (gremio_id, jugador_id, rango) VALUES (?,?,'fundador')",
                  (gremio_id, user_id))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        await query.edit_message_text("❌ Ya existe un gremio con ese nombre.")
        context.user_data.clear()
        return
    conn.close()

    economia.modificar_saldo(user_id, "eternium", -costo, f"creación de gremio {nombre}")
    context.user_data.clear()

    await query.edit_message_text(
        f"🎉 *¡Gremio creado!*\n\n"
        f"🏰 *{nombre}* [{tag}]\n"
        f"Eres el *Fundador*.\n\n"
        f"Invita miembros con `/invitar_gremio <user_id>`\n"
        f"Consulta tu gremio con el botón *Mi Gremio* en el menú.",
        parse_mode="Markdown"
    )

async def cb_gremio_crear_cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    await query.edit_message_text("❌ Creación de gremio cancelada.")
    return ConversationHandler.END


# ==================== COMANDOS ADMIN ====================
async def cmd_admin_gremio_config(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /admin_gremio_config costo_creacion <valor>
    /admin_gremio_config nivel_minimo <valor>
    """
    user_id = update.effective_user.id
    superadmin_id = os.environ.get("SUPERADMIN_ID")
    if not superadmin_id or str(user_id) != superadmin_id:
        if not sa._es_admin(user_id):
            await update.effective_message.reply_text("❌ Sin permiso.")
            return

    if not context.args or len(context.args) < 2:
        costo  = _costo_creacion()
        nivel  = _nivel_minimo()
        await update.effective_message.reply_text(
            f"⚙️ *Configuración de Gremios*\n\n"
            f"Costo de creación: *{costo} eternium*\n"
            f"Nivel mínimo para crear: *{nivel}*\n\n"
            f"Uso:\n"
            f"`/admin_gremio_config costo_creacion <valor>`\n"
            f"`/admin_gremio_config nivel_minimo <valor>`",
            parse_mode="Markdown"
        )
        return

    clave = context.args[0].lower()
    try:
        valor = int(context.args[1])
        if valor <= 0:
            raise ValueError
    except ValueError:
        await update.effective_message.reply_text("El valor debe ser un número positivo.")
        return

    if clave in ("costo_creacion", "costo"):
        _set_config("costo_creacion_gremio", valor)
        await update.effective_message.reply_text(f"✅ Costo de creación de gremio actualizado a *{valor} eternium*.", parse_mode="Markdown")
    elif clave in ("nivel_minimo", "nivel"):
        _set_config("nivel_minimo_gremio", valor)
        await update.effective_message.reply_text(f"✅ Nivel mínimo para crear gremio actualizado a *{valor}*.", parse_mode="Markdown")
    else:
        await update.effective_message.reply_text("Clave no reconocida. Usa `costo_creacion` o `nivel_minimo`.", parse_mode="Markdown")

async def cmd_admin_disolver_gremio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin force-disuelve un gremio por nombre"""
    user_id = update.effective_user.id
    superadmin_id = os.environ.get("SUPERADMIN_ID")
    if not superadmin_id or str(user_id) != superadmin_id:
        if not sa._es_admin(user_id):
            await update.effective_message.reply_text("❌ Sin permiso.")
            return
    if not context.args:
        await update.effective_message.reply_text("Uso: /admin_disolver_gremio <nombre>")
        return
    nombre = " ".join(context.args)
    gremio = _obtener_gremio_por_nombre(nombre)
    if not gremio:
        await update.effective_message.reply_text(f"❌ Gremio '{nombre}' no encontrado.")
        return
    miembros = _obtener_miembros(gremio["id"])
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM miembros_gremio WHERE gremio_id = ?", (gremio["id"],))
    c.execute("DELETE FROM baul_gremio WHERE gremio_id = ?", (gremio["id"],))
    c.execute("DELETE FROM gremios WHERE id = ?", (gremio["id"],))
    conn.commit()
    conn.close()
    for m in miembros:
        db_helper.agregar_notificacion(m["jugador_id"], f"💥 El gremio {gremio['nombre']} fue disuelto por el administrador.")
    await update.effective_message.reply_text(f"✅ Gremio <b>{_he(gremio['nombre'])}</b> disuelto.", parse_mode="HTML")


# ==================== CALLBACK DISPATCHER ====================
async def cb_gremio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    dispatch = {
        "cb_mi_gremio_menu":           cb_mi_gremio_menu,
        "gremio_info":                 cb_gremio_info,
        "gremio_miembros":             cb_gremio_miembros,
        "gremio_baul_ver":             cb_gremio_baul_ver,
        "gremio_baul_depositar_info":  cb_gremio_baul_depositar_info,
        "gremio_baul_tomar_info":      cb_gremio_baul_tomar_info,
        "gremio_invitar_info":         cb_gremio_invitar_info,
        "gremio_expulsar_info":        cb_gremio_expulsar_info,
        "gremio_rango_info":           cb_gremio_rango_info,
        "gremio_editar_desc":          cb_gremio_editar_desc,
        "gremio_abandonar_confirm":    cb_gremio_abandonar_confirm,
        "gremio_abandonar_ok":         cb_gremio_abandonar_ok,
        "gremio_disolver_confirm":     cb_gremio_disolver_confirm,
        "gremio_disolver_ok":          cb_gremio_disolver_ok,
        "gremio_buscar":               cb_gremio_buscar,
        "gremio_crear_inicio":         cb_gremio_crear_inicio,
        "gremio_crear_confirmar":      cb_gremio_crear_confirmar,
        "gremio_crear_cancelar":       cb_gremio_crear_cancelar,
        "gremio_crear_skip_desc":      cb_gremio_crear_skip_desc,
    }

    if data in dispatch:
        await dispatch[data](update, context)
    elif data.startswith("gremio_expulsar_") and not data.endswith("_info"):
        await cb_gremio_expulsar(update, context)
    elif data.startswith("gremio_inv_aceptar_"):
        await cb_gremio_inv_aceptar(update, context)
    elif data.startswith("gremio_inv_rechazar_"):
        await cb_gremio_inv_rechazar(update, context)
    elif data.startswith("gremio_req_aceptar_"):
        await cb_gremio_req_aceptar(update, context)
    elif data.startswith("gremio_req_rechazar_"):
        await cb_gremio_req_rechazar(update, context)
    elif data.startswith("gremio_ver_"):
        await cb_gremio_ver(update, context)
    elif data.startswith("gremio_solicitar_"):
        await cb_gremio_solicitar(update, context)
    elif data.startswith("gremio_tomar_item_"):
        await cb_gremio_tomar_item(update, context)
    else:
        await query.answer()


# ==================== CMD GREMIO (entrada desde teclado rápido / comando) ====================
async def cmd_gremio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Versión para mensajes normales del menú de gremio (teclado rápido / /gremio)."""
    user_id = update.effective_user.id
    try:
        from guerra_facciones import check_lockdown
        if await check_lockdown(update):
            return
    except Exception:
        pass
    if not _en_ciudad(user_id):
        await update.effective_message.reply_text("🏙️ Las actividades de gremio solo están disponibles en ciudades.")
        return
    try:
        import guia_contextual as _gc
        await _gc.enviar(user_id, context, "gremio_menu")
    except Exception:
        pass
    gremio = _obtener_gremio_de_jugador(user_id)
    if not gremio:
        kb_sin_gremio = InlineKeyboardMarkup([
            [InlineKeyboardButton("🏰 Crear Gremio",    callback_data="gremio_crear_inicio")],
            [InlineKeyboardButton("🔍 Buscar Gremios",  callback_data="gremio_buscar")],
        ])
        await update.effective_message.reply_text(
            "⚠️ *No perteneces a ningún gremio.*\n\n"
            "Puedes fundar el tuyo o buscar uno al que unirte:",
            parse_mode="Markdown",
            reply_markup=kb_sin_gremio
        )
        return
    rango = _rango_de_jugador(user_id, gremio["id"])
    miembros = _num_miembros(gremio["id"])
    kb = [
        [InlineKeyboardButton("📋 Info del Gremio",      callback_data="gremio_info")],
        [InlineKeyboardButton("👥 Ver Miembros",          callback_data="gremio_miembros")],
        [InlineKeyboardButton("📦 Baúl del Gremio",       callback_data="gremio_baul_ver")],
    ]
    if rango in RANGO_PUEDE_INVITAR:
        kb.append([InlineKeyboardButton("✉️ Invitar Jugador",    callback_data="gremio_invitar_info")])
    if rango in RANGO_PUEDE_EXPULSAR:
        kb.append([InlineKeyboardButton("👢 Expulsar Miembro",   callback_data="gremio_expulsar_info")])
    if rango in RANGO_PUEDE_ASCENDER:
        kb.append([InlineKeyboardButton("🎭 Cambiar Rango",      callback_data="gremio_rango_info")])
    if rango in {"fundador", "lider"}:
        kb.append([InlineKeyboardButton("📝 Editar Descripción",  callback_data="gremio_editar_desc")])
    if rango == "fundador":
        kb.append([InlineKeyboardButton("💥 Disolver Gremio",    callback_data="gremio_disolver_confirm")])
    if rango != "fundador":
        kb.append([InlineKeyboardButton("🚪 Abandonar Gremio",   callback_data="gremio_abandonar_confirm")])
    await update.effective_message.reply_text(
        f"🛡️ *{_esc_md(gremio['nombre'])}* — Nivel {gremio.get('nivel', 1)}\n"
        f"Tu rango: {_emoji_rango(rango)} {rango.capitalize()}\n"
        f"Miembros: {miembros}",
        reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown"
    )


# ==================== PANEL ADMIN GREMIOS ====================

def _es_admin_gremio(user_id: int) -> bool:
    superadmin_id = os.environ.get("SUPERADMIN_ID")
    if superadmin_id and str(user_id) == superadmin_id:
        return True
    return sa._es_admin(user_id)

def _texto_panel_gremio() -> str:
    stats = _stats_gremios()
    lineas = ["⚙️ *Panel de Configuración de Gremios*\n"]
    lineas.append("📋 *Requisitos de creación:*")
    for clave, (label, unidad, defecto, _, _2) in _CONFIG_META.items():
        valor = int(_get_config(clave, defecto))
        lineas.append(f"  • {label}: *{valor}* {unidad}")
    lineas.append("")
    lineas.append("📊 *Estadísticas actuales:*")
    lineas.append(f"  • Gremios activos: *{stats['total']}*")
    lineas.append(f"  • Total de miembros: *{stats['miembros']}*")
    lineas.append(f"  • Gremios nivel 5+: *{stats['alto_nivel']}*")
    return "\n".join(lineas)

def _teclado_panel_gremio() -> InlineKeyboardMarkup:
    filas = []
    for clave, (label, unidad, defecto, _, _2) in _CONFIG_META.items():
        valor = int(_get_config(clave, defecto))
        filas.append([InlineKeyboardButton(
            f"{label}: {valor} {unidad}  ✏️",
            callback_data=f"agp_edit_{clave}"
        )])
    filas.append([InlineKeyboardButton("🔄 Actualizar", callback_data="agp_menu")])
    return InlineKeyboardMarkup(filas)

async def cmd_admin_gremio_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/panel_gremios — Panel visual de configuración de gremios (solo admins)."""
    user_id = update.effective_user.id
    if not _es_admin_gremio(user_id):
        await update.effective_message.reply_text("❌ Sin permiso.")
        return
    await update.effective_message.reply_text(
        _texto_panel_gremio(),
        reply_markup=_teclado_panel_gremio(),
        parse_mode="Markdown"
    )

async def cb_admin_gremio_nav(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback de navegación simple: agp_menu y agp_cancelar (fuera del ConversationHandler)."""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    if not _es_admin_gremio(user_id):
        await query.answer("❌ Sin permiso.", show_alert=True)
        return
    context.user_data.pop("agp_clave", None)
    await query.edit_message_text(
        _texto_panel_gremio(),
        reply_markup=_teclado_panel_gremio(),
        parse_mode="Markdown"
    )

async def cb_admin_gremio_iniciar_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry point del ConversationHandler: usuario pulsó ✏️ en una clave."""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    if not _es_admin_gremio(user_id):
        await query.answer("❌ Sin permiso.", show_alert=True)
        return ConversationHandler.END

    clave = query.data[len("agp_edit_"):]
    if clave not in _CONFIG_META:
        await query.answer("❌ Clave desconocida.", show_alert=True)
        return ConversationHandler.END

    label, unidad, defecto, minimo, maximo = _CONFIG_META[clave]
    valor_actual = int(_get_config(clave, defecto))
    context.user_data["agp_clave"] = clave
    await query.edit_message_text(
        f"✏️ *Editando:* {label}\n\n"
        f"Valor actual: *{valor_actual}* {unidad}\n"
        f"Rango permitido: {minimo} – {maximo}\n\n"
        f"Escribe el nuevo valor numérico o pulsa Cancelar.",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ Cancelar", callback_data="agp_cancelar")
        ]]),
        parse_mode="Markdown"
    )
    return ADMIN_GREMIO_EDIT

async def _admin_gremio_recibir_valor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recibe el nuevo valor numérico escrito por el admin."""
    user_id = update.effective_user.id
    if not _es_admin_gremio(user_id):
        return ConversationHandler.END

    clave = context.user_data.get("agp_clave")
    if not clave or clave not in _CONFIG_META:
        await update.effective_message.reply_text("❌ Sesión expirada. Usa /panel_gremios de nuevo.")
        return ConversationHandler.END

    label, unidad, defecto, minimo, maximo = _CONFIG_META[clave]
    texto = update.effective_message.text.strip()
    try:
        nuevo_valor = int(texto)
        if not (minimo <= nuevo_valor <= maximo):
            raise ValueError
    except ValueError:
        await update.effective_message.reply_text(
            f"❌ Valor inválido. Debe ser un número entero entre {minimo} y {maximo}.\n"
            f"Escribe de nuevo o usa /panel_gremios para cancelar."
        )
        return ADMIN_GREMIO_EDIT

    _set_config(clave, nuevo_valor)
    await update.effective_message.reply_text(
        f"✅ *{label}* actualizado a *{nuevo_valor}* {unidad}.",
        parse_mode="Markdown"
    )
    await update.effective_message.reply_text(
        _texto_panel_gremio(),
        reply_markup=_teclado_panel_gremio(),
        parse_mode="Markdown"
    )
    context.user_data.pop("agp_clave", None)
    context.user_data.pop("agp_msg_id", None)
    return ConversationHandler.END

async def _admin_gremio_cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("agp_clave", None)
    context.user_data.pop("agp_msg_id", None)
    await update.effective_message.reply_text(
        "❌ Edición cancelada.",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 Volver al panel", callback_data="agp_menu")
        ]])
    )
    return ConversationHandler.END


# ==================== REGISTRAR HANDLERS ====================
async def _gremio_nav_cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fallback de navegación para ConversationHandlers de gremios."""
    context.user_data.pop("crear_gremio_nombre", None)
    context.user_data.pop("crear_gremio_desc", None)
    text = (update.effective_message.text or "").strip() if update.effective_message else ""
    _DESPACHO = {
        "/ciudad":     ("ciudad",     "cmd_ciudad"),
        "/perfil":     ("perfil",     "cmd_perfil"),
        "/viajar":     ("viajes",     "cmd_viajar"),
        "/inventario": ("inventario", "cmd_inventario"),
        "/gremio":     ("gremios",    "cmd_gremio"),
    }
    try:
        for cmd_txt, (mod_name, func_name) in _DESPACHO.items():
            if text.startswith(cmd_txt):
                import importlib
                m = importlib.import_module(mod_name)
                await getattr(m, func_name)(update, context)
                return ConversationHandler.END
        from teclado_rapido import handle_boton_rapido, _MAPA
        if text in _MAPA:
            await handle_boton_rapido(update, context)
            return ConversationHandler.END
    except Exception:
        pass
    if update.effective_message:
        await update.effective_message.reply_text("❌ Creación de gremio cancelada.")
    return ConversationHandler.END

def registrar_handlers(app):
    # ConversationHandler para crear gremio
    _GREMIO_NAV = [
        CallbackQueryHandler(cb_gremio_crear_cancelar, pattern="^gremio_crear_cancelar$"),
        CommandHandler("cancel",     _gremio_nav_cancelar),
        CommandHandler("ciudad",     _gremio_nav_cancelar),
        CommandHandler("perfil",     _gremio_nav_cancelar),
        CommandHandler("viajar",     _gremio_nav_cancelar),
        CommandHandler("inventario", _gremio_nav_cancelar),
        CommandHandler("gremio",     _gremio_nav_cancelar),
        CommandHandler("start",      _gremio_nav_cancelar),
        MessageHandler(filters.Regex("^(👤|🏙️?|🎒|✈️?|⚔️?|🏰|⛏️?|🔍|📋|📖)"), _gremio_nav_cancelar),
    ]
    conv_crear = ConversationHandler(
        entry_points=[CallbackQueryHandler(cb_gremio_crear_inicio, pattern="^gremio_crear_inicio$")],
        states={
            CONV_NOMBRE: [MessageHandler(filters.TEXT & ~filters.COMMAND, _recibir_nombre_gremio)],
            CONV_DESC:   [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _recibir_desc_gremio),
                CallbackQueryHandler(cb_gremio_crear_skip_desc, pattern="^gremio_crear_skip_desc$"),
            ],
        },
        fallbacks=_GREMIO_NAV,
        allow_reentry=True,
    )
    app.add_handler(conv_crear)

    # ConversationHandler para editar descripción
    conv_desc = ConversationHandler(
        entry_points=[CallbackQueryHandler(cb_gremio_editar_desc, pattern="^gremio_editar_desc$")],
        states={
            CONV_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, _recibir_desc_edicion)],
        },
        fallbacks=[
            CallbackQueryHandler(cb_mi_gremio_menu, pattern="^cb_mi_gremio_menu$"),
            CommandHandler("cancel",     _gremio_nav_cancelar),
            CommandHandler("ciudad",     _gremio_nav_cancelar),
            CommandHandler("perfil",     _gremio_nav_cancelar),
            CommandHandler("viajar",     _gremio_nav_cancelar),
            CommandHandler("inventario", _gremio_nav_cancelar),
            CommandHandler("gremio",     _gremio_nav_cancelar),
            CommandHandler("start",      _gremio_nav_cancelar),
            MessageHandler(filters.Regex("^(👤|🏙️?|🎒|✈️?|⚔️?|🏰|⛏️?|🔍|📋|📖)"), _gremio_nav_cancelar),
        ],
        allow_reentry=True,
    )
    app.add_handler(conv_desc)

    # Dispatcher general para todos los callbacks de gremio
    app.add_handler(CallbackQueryHandler(cb_gremio, pattern=r"^(cb_mi_gremio|gremio_)"))

    # ConversationHandler para editar valores del panel de gremios (admin)
    conv_admin_gremio = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(cb_admin_gremio_iniciar_edit, pattern=r"^agp_edit_"),
        ],
        states={
            ADMIN_GREMIO_EDIT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _admin_gremio_recibir_valor),
                CallbackQueryHandler(cb_admin_gremio_nav, pattern=r"^agp_cancelar$"),
            ],
        },
        fallbacks=[
            CommandHandler("cancelar", _admin_gremio_cancelar),
            CommandHandler("panel_gremios", cmd_admin_gremio_panel),
        ],
        allow_reentry=True,
        per_message=False,
    )
    app.add_handler(conv_admin_gremio)

    # Navegación del panel (agp_menu y agp_cancelar — fuera del ConversationHandler)
    app.add_handler(CallbackQueryHandler(cb_admin_gremio_nav, pattern=r"^agp_(menu|cancelar)$"))

    # Comandos
    app.add_handler(CommandHandler("invitar_gremio",       cmd_invitar_gremio))
    app.add_handler(CommandHandler("rango_gremio",         cmd_rango_gremio))
    app.add_handler(CommandHandler("depositar_baul",       cmd_depositar_baul))
    app.add_handler(CommandHandler("tomar_baul",           cmd_tomar_baul))
    app.add_handler(CommandHandler("admin_gremio_config",  cmd_admin_gremio_config))
    app.add_handler(CommandHandler("admin_disolver_gremio",cmd_admin_disolver_gremio))
    app.add_handler(CommandHandler("panel_gremios",        cmd_admin_gremio_panel))

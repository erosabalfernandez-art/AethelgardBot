#!/usr/bin/env python3
# superadmin.py
# Sistema completo de administración con niveles de permiso.
# Nivel 0 = jugador normal
# Nivel 1 = admin normal  (dar objetos/monedas, gestionar jugadores, eventos)
# Nivel 2 = dios          (todos los poderes + modo dios personal)
# SUPERADMIN_ID = único dueño, puede crear/quitar admins, es inmutable.

import os
import sqlite3
import importlib
import json
from datetime import datetime
from typing import Optional, List, Dict, Tuple

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler

import db_helper
import economia

DB_PATH = "aethelgard.db"

def _esc_md(s: str) -> str:
    return str(s).replace("_", "\\_").replace("*", "\\*").replace("`", "\\`").replace("[", "\\[")

# ==================== SUPERADMIN ID ====================
# Configura tu user_id de Telegram aquí o como variable de entorno.
SUPERADMIN_ID = int(os.environ.get("SUPERADMIN_ID", "0"))

# ==================== TABLAS ====================
def _init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS admins (
        user_id INTEGER PRIMARY KEY,
        nivel INTEGER DEFAULT 1,
        otorgado_por INTEGER,
        fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS jugadores_baneados (
        user_id INTEGER PRIMARY KEY,
        motivo TEXT,
        fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS jugadores_silenciados (
        user_id INTEGER PRIMARY KEY,
        fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS modo_dios_activo (
        user_id INTEGER PRIMARY KEY
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS admin_permisos (
        user_id  INTEGER NOT NULL,
        categoria TEXT NOT NULL,
        PRIMARY KEY (user_id, categoria)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS admin_cmd_permisos (
        user_id  INTEGER NOT NULL,
        comando  TEXT NOT NULL,
        PRIMARY KEY (user_id, comando)
    )''')
    conn.commit()
    conn.close()

_init_db()

# ==================== HELPERS DE PERMISOS ====================
def _nivel_admin(user_id: int) -> int:
    if user_id == SUPERADMIN_ID:
        return 99
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT nivel FROM admins WHERE user_id = ?', (user_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0

def _es_superadmin(user_id: int) -> bool:
    return user_id == SUPERADMIN_ID

def _es_admin(user_id: int, nivel_minimo: int = 1) -> bool:
    return _nivel_admin(user_id) >= nivel_minimo

# ── permisos por categoría ────────────────────────────────────────────────────

def _categorias_admin(user_id: int) -> set:
    """Devuelve el set de claves de categoría a las que este admin tiene acceso."""
    if _es_superadmin(user_id):
        return set(PANEL_CATEGORIAS.keys())
    n = _nivel_admin(user_id)
    if n < 1:
        return set()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT categoria FROM admin_permisos WHERE user_id = ?", (user_id,))
    rows = c.fetchall()
    conn.close()
    granted = {r[0] for r in rows}
    if n >= 2:
        granted.add("dios")   # Dios siempre ve su categoría propia
    return granted

def _tiene_permiso(user_id: int, categoria: str) -> bool:
    if _es_superadmin(user_id):
        return True
    return categoria in _categorias_admin(user_id)

def _verificar_cmd(user_id: int, categoria: str, nivel_minimo: int = 1) -> bool:
    """True si el usuario puede ejecutar comandos de esta categoría."""
    if _es_superadmin(user_id):
        return True
    if not _es_admin(user_id, nivel_minimo):
        return False
    if nivel_minimo >= 2:
        return True  # check de nivel es suficiente para dios
    return _tiene_permiso(user_id, categoria)

# ── UI: teclado de selección de permisos ─────────────────────────────────────

def _cats_grantables() -> dict:
    """Categorías que se pueden otorgar a admins regulares (nivel <= 1)."""
    return {k: v for k, v in PANEL_CATEGORIAS.items() if v.get("nivel", 1) <= 1}

def _kb_permisos(uid: int, seleccion: set, modo: str) -> InlineKeyboardMarkup:
    cats  = _cats_grantables()
    filas = []
    fila  = []
    for clave, cat in cats.items():
        activo = clave in seleccion
        fila.append(InlineKeyboardButton(
            f"{'✅' if activo else '☐'} {cat['emoji']} {cat['titulo']}",
            callback_data=f"perm_t_{modo}_{uid}_{clave}"
        ))
        if len(fila) == 2:
            filas.append(fila)
            fila = []
    if fila:
        filas.append(fila)
    filas.append([
        InlineKeyboardButton("✅ Todas",    callback_data=f"perm_all_{modo}_{uid}"),
        InlineKeyboardButton("☐ Ninguna",  callback_data=f"perm_none_{modo}_{uid}"),
    ])
    if modo == "c":
        filas.append([InlineKeyboardButton("✅ Crear admin con estos permisos", callback_data=f"perm_ok_{uid}")])
    else:
        filas.append([InlineKeyboardButton("💾 Guardar cambios", callback_data=f"perm_save_{uid}")])
    filas.append([InlineKeyboardButton("❌ Cancelar", callback_data="perm_cancel")])
    return InlineKeyboardMarkup(filas)

def _texto_perm_panel(uid: int, modo: str, seleccion: set) -> str:
    titulo = "➕ *Crear nuevo admin*" if modo == "c" else "✏️ *Editar permisos del admin*"
    return (
        f"{titulo}\n\nID: `{uid}`\n"
        f"Categorías activas: *{len(seleccion)}*\n\n"
        f"Pulsa cada categoría para activarla ✅ o desactivarla ☐.\n"
        f"Cuando termines, confirma con el botón de abajo."
    )

def _guardar_permisos_db(uid: int, seleccion: set, otorgado_por: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO admins (user_id, nivel, otorgado_por, fecha) VALUES (?,?,?,?)',
              (uid, 1, otorgado_por, datetime.now().isoformat()))
    c.execute('DELETE FROM admin_permisos WHERE user_id = ?', (uid,))
    for cat in seleccion:
        c.execute('INSERT OR IGNORE INTO admin_permisos (user_id, categoria) VALUES (?,?)', (uid, cat))
    conn.commit()
    conn.close()

def _solo_actualizar_permisos_db(uid: int, seleccion: set):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('DELETE FROM admin_permisos WHERE user_id = ?', (uid,))
    for cat in seleccion:
        c.execute('INSERT OR IGNORE INTO admin_permisos (user_id, categoria) VALUES (?,?)', (uid, cat))
    conn.commit()
    conn.close()

def _es_baneado(user_id: int) -> bool:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT 1 FROM jugadores_baneados WHERE user_id = ?', (user_id,))
    r = c.fetchone()
    conn.close()
    return r is not None

def _es_silenciado(user_id: int) -> bool:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT 1 FROM jugadores_silenciados WHERE user_id = ?', (user_id,))
    r = c.fetchone()
    conn.close()
    return r is not None

def _modo_dios_activo(user_id: int) -> bool:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT 1 FROM modo_dios_activo WHERE user_id = ?', (user_id,))
    r = c.fetchone()
    conn.close()
    return r is not None

# ==================== MIDDLEWARE DE BANEO ====================
def verificar_baneado(user_id: int) -> bool:
    """Retorna True si el jugador está baneado (bloquear el comando)."""
    return _es_baneado(user_id)

def verificar_superadmin(user_id: int) -> bool:
    """Alias público de _es_superadmin."""
    return _es_superadmin(user_id)

def verificar_nivel(user_id: int, nivel_minimo: int) -> bool:
    """Alias público de _es_admin con nivel mínimo."""
    return _es_admin(user_id, nivel_minimo=nivel_minimo)

# ==================== COMANDOS SUPERADMIN ====================

async def cmd_superadmin_mi_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from html import escape
    user = update.effective_user
    await update.effective_message.reply_text(
        f"🆔 Tu user_id de Telegram: <code>{user.id}</code>\n"
        f"Nombre: {escape(user.full_name)}\n"
        f"Nivel admin: {_nivel_admin(user.id)}",
        parse_mode="HTML"
    )

async def cmd_superadmin_crear_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not _es_superadmin(user_id):
        await update.effective_message.reply_text("❌ Solo el superadmin puede crear admins.")
        return
    if not context.args:
        await update.effective_message.reply_text(
            "Uso: `/superadmin_crear_admin <user_id>`\n\nSe abrirá un panel para elegir los permisos.",
            parse_mode="Markdown"
        )
        return
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.effective_message.reply_text("user_id debe ser un número.")
        return
    if target_id == SUPERADMIN_ID:
        await update.effective_message.reply_text("El superadmin ya tiene todos los permisos.")
        return
    # Cargar permisos actuales si ya existe como admin
    seleccion = _categorias_admin(target_id) - {"superadmin", "dios", "restricciones"}
    context.user_data[f"perm_sel_{target_id}"] = list(seleccion)
    await update.effective_message.reply_text(
        _texto_perm_panel(target_id, "c", seleccion),
        reply_markup=_kb_permisos(target_id, seleccion, "c"),
        parse_mode="Markdown"
    )

async def cmd_superadmin_editar_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not _es_superadmin(user_id):
        await update.effective_message.reply_text("❌ Solo el superadmin puede editar admins.")
        return
    if not context.args:
        await update.effective_message.reply_text("Uso: `/superadmin_editar_admin <user_id>`", parse_mode="Markdown")
        return
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.effective_message.reply_text("user_id debe ser un número.")
        return
    if target_id == SUPERADMIN_ID:
        await update.effective_message.reply_text("El superadmin siempre tiene todos los permisos.")
        return
    if _nivel_admin(target_id) < 1:
        await update.effective_message.reply_text(f"❌ El usuario {target_id} no es admin. Usa /superadmin_crear_admin primero.")
        return
    seleccion = _categorias_admin(target_id) - {"superadmin", "dios", "restricciones"}
    context.user_data[f"perm_sel_{target_id}"] = list(seleccion)
    await update.effective_message.reply_text(
        _texto_perm_panel(target_id, "e", seleccion),
        reply_markup=_kb_permisos(target_id, seleccion, "e"),
        parse_mode="Markdown"
    )

async def cb_perm_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja todos los callbacks perm_* del sistema de permisos de admin."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if not _es_superadmin(user_id):
        await query.answer("❌ Solo el superadmin.", show_alert=True)
        return

    data = query.data

    if data == "perm_cancel":
        await query.edit_message_text("❌ Operación cancelada.")
        return

    # perm_t_{modo}_{uid}_{clave} — toggle de categoría
    if data.startswith("perm_t_"):
        resto  = data[len("perm_t_"):]
        partes = resto.split("_", 2)
        modo, uid, clave = partes[0], int(partes[1]), partes[2]
        sel = set(context.user_data.get(f"perm_sel_{uid}", []))
        if clave in sel:
            sel.discard(clave)
        else:
            sel.add(clave)
        context.user_data[f"perm_sel_{uid}"] = list(sel)
        await query.edit_message_text(
            _texto_perm_panel(uid, modo, sel),
            reply_markup=_kb_permisos(uid, sel, modo),
            parse_mode="Markdown"
        )
        return

    # perm_all_{modo}_{uid} — seleccionar todas
    if data.startswith("perm_all_"):
        resto  = data[len("perm_all_"):]
        modo, uid = resto.split("_", 1)
        uid = int(uid)
        sel = set(_cats_grantables().keys())
        context.user_data[f"perm_sel_{uid}"] = list(sel)
        await query.edit_message_text(
            _texto_perm_panel(uid, modo, sel),
            reply_markup=_kb_permisos(uid, sel, modo),
            parse_mode="Markdown"
        )
        return

    # perm_none_{modo}_{uid} — deseleccionar todas
    if data.startswith("perm_none_"):
        resto  = data[len("perm_none_"):]
        modo, uid = resto.split("_", 1)
        uid = int(uid)
        sel = set()
        context.user_data[f"perm_sel_{uid}"] = []
        await query.edit_message_text(
            _texto_perm_panel(uid, modo, sel),
            reply_markup=_kb_permisos(uid, sel, modo),
            parse_mode="Markdown"
        )
        return

    # perm_ok_{uid} — confirmar creación
    if data.startswith("perm_ok_"):
        uid = int(data[len("perm_ok_"):])
        sel = set(context.user_data.pop(f"perm_sel_{uid}", []))
        _guardar_permisos_db(uid, sel, user_id)
        cats_txt = ", ".join(
            PANEL_CATEGORIAS.get(c, {}).get("titulo", c) for c in sorted(sel)
        ) or "Ninguna"
        await query.edit_message_text(
            f"✅ *Admin creado correctamente*\n\n"
            f"ID: `{uid}`\n"
            f"Permisos otorgados:\n_{cats_txt}_\n\n"
            f"Este admin ya puede usar `/panel_admin` para ver sus comandos.",
            parse_mode="Markdown"
        )
        return

    # perm_save_{uid} — guardar edición de permisos
    if data.startswith("perm_save_"):
        uid = int(data[len("perm_save_"):])
        sel = set(context.user_data.pop(f"perm_sel_{uid}", []))
        _solo_actualizar_permisos_db(uid, sel)
        cats_txt = ", ".join(
            PANEL_CATEGORIAS.get(c, {}).get("titulo", c) for c in sorted(sel)
        ) or "Ninguna"
        await query.edit_message_text(
            f"✅ *Permisos actualizados*\n\n"
            f"Admin ID: `{uid}`\n"
            f"Permisos activos:\n_{cats_txt}_",
            parse_mode="Markdown"
        )
        return

    # perm_edit_{uid} — abrir edición desde lista_admins
    if data.startswith("perm_edit_"):
        uid = int(data[len("perm_edit_"):])
        sel = _categorias_admin(uid) - {"superadmin", "dios", "restricciones"}
        context.user_data[f"perm_sel_{uid}"] = list(sel)
        await query.edit_message_text(
            _texto_perm_panel(uid, "e", sel),
            reply_markup=_kb_permisos(uid, sel, "e"),
            parse_mode="Markdown"
        )
        return

    # perm_rem_{uid} — revocar admin desde lista
    if data.startswith("perm_rem_"):
        uid = int(data[len("perm_rem_"):])
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('DELETE FROM admins WHERE user_id = ?', (uid,))
        c.execute('DELETE FROM admin_permisos WHERE user_id = ?', (uid,))
        conn.commit()
        conn.close()
        await query.edit_message_text(f"✅ Admin `{uid}` eliminado y permisos revocados.", parse_mode="Markdown")

async def cmd_superadmin_quitar_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not _es_superadmin(user_id):
        await update.effective_message.reply_text("❌ Solo el superadmin puede quitar admins.")
        return
    if not context.args:
        await update.effective_message.reply_text("Uso: /superadmin_quitar_admin <user_id>")
        return
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.effective_message.reply_text("user_id debe ser un número.")
        return
    if target_id == SUPERADMIN_ID:
        await update.effective_message.reply_text("No puedes quitarte permisos a ti mismo.")
        return
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('DELETE FROM admins WHERE user_id = ?', (target_id,))
    c.execute('DELETE FROM admin_permisos WHERE user_id = ?', (target_id,))
    conn.commit()
    conn.close()
    await update.effective_message.reply_text(f"✅ Usuario {target_id} ya no tiene permisos de admin.")

async def cmd_superadmin_lista_admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not _es_superadmin(user_id):
        await update.effective_message.reply_text("❌ Solo el superadmin puede ver la lista de admins.")
        return
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM admins ORDER BY nivel DESC')
    rows = c.fetchall()
    conn.close()
    if not rows:
        await update.effective_message.reply_text(
            f"No hay admins registrados.\n\n⭐ Superadmin: `{SUPERADMIN_ID}`",
            parse_mode="Markdown"
        )
        return
    botones = []
    for r in rows:
        tipo = "🔱 Dios" if r["nivel"] == 2 else "🛡️ Admin"
        uid  = r["user_id"]
        cats = _categorias_admin(uid) - {"dios", "superadmin", "restricciones"}
        cats_nombres = ", ".join(
            PANEL_CATEGORIAS.get(c, {}).get("titulo", c) for c in sorted(cats)
        ) or "Ninguna"
        botones.append([
            InlineKeyboardButton(
                f"{tipo} · {uid} — {cats_nombres}",
                callback_data=f"perm_edit_{uid}"
            )
        ])
        botones.append([
            InlineKeyboardButton(f"✏️ Editar permisos ({uid})", callback_data=f"perm_edit_{uid}"),
            InlineKeyboardButton(f"🗑️ Revocar ({uid})",        callback_data=f"perm_rem_{uid}"),
        ])
    texto = (
        f"👑 *Lista de Administradores*\n\n"
        f"⭐ Superadmin: `{SUPERADMIN_ID}`\n\n"
        f"Pulsa *Editar permisos* para cambiar lo que puede hacer cada admin,\n"
        f"o *Revocar* para quitarle el rango."
    )
    await update.effective_message.reply_text(
        texto,
        reply_markup=InlineKeyboardMarkup(botones),
        parse_mode="Markdown"
    )

# ==================== MODO DIOS ====================

async def cmd_dios_activar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not _es_admin(user_id, nivel_minimo=2):
        await update.effective_message.reply_text("❌ Solo los administradores de nivel 2 (Dios) pueden activar el modo dios.")
        return
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('INSERT OR IGNORE INTO modo_dios_activo (user_id) VALUES (?)', (user_id,))
    conn.commit()
    conn.close()
    await update.effective_message.reply_text("🔱 Modo Dios ACTIVADO. Todas las restricciones del juego se ignoran para tu cuenta.")

async def cmd_dios_desactivar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('DELETE FROM modo_dios_activo WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()
    await update.effective_message.reply_text("✅ Modo Dios desactivado. Volviste al modo normal.")

async def cmd_dios_subir_nivel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not _es_admin(user_id, nivel_minimo=2):
        await update.effective_message.reply_text("❌ Sin permiso.")
        return
    cantidad = int(context.args[0]) if context.args else 1
    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        await update.effective_message.reply_text("No tienes personaje registrado.")
        return
    nuevo_nivel = min(jug["nivel"] + cantidad, 100)
    db_helper.actualizar_jugador(user_id, nivel=nuevo_nivel)
    await update.effective_message.reply_text(f"⬆️ Nivel subido a {nuevo_nivel}.")

async def cmd_dios_max_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not _es_admin(user_id, nivel_minimo=2):
        await update.effective_message.reply_text("❌ Sin permiso.")
        return
    db_helper.actualizar_jugador(user_id, hp_actual=9999, hp_max=9999, nivel=100)
    await update.effective_message.reply_text("💪 Stats maximizados (HP 9999, nivel 100).")

async def cmd_dios_recolectar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not _es_admin(user_id, nivel_minimo=2):
        await update.effective_message.reply_text("❌ Sin permiso.")
        return
    db_helper.actualizar_jugador(user_id, stamina_actual=100, ultima_recoleccion=None, fatiga_acumulada=0)
    await update.effective_message.reply_text("🔄 Stamina y fatiga reseteados. Puedes recolectar sin restricciones.")

# ==================== DAR / QUITAR MONEDAS ====================

async def _cmd_dar_moneda(update, context, moneda: str):
    user_id = update.effective_user.id
    if not _verificar_cmd(user_id, "monedas"):
        await update.effective_message.reply_text("❌ Sin permiso para gestionar monedas.")
        return
    if len(context.args) < 2:
        await update.effective_message.reply_text(f"Uso: /dar_{moneda} <user_id> <cantidad>")
        return
    try:
        target_id = int(context.args[0])
        cantidad = int(context.args[1])
    except ValueError:
        await update.effective_message.reply_text("Valores inválidos.")
        return
    if cantidad <= 0:
        await update.effective_message.reply_text("La cantidad debe ser positiva.")
        return
    ok = economia.modificar_saldo(target_id, moneda, cantidad, f"admin_dar ({user_id})")
    if ok:
        await update.effective_message.reply_text(f"✅ Se dieron {cantidad} {moneda} al jugador {target_id}.")
    else:
        await update.effective_message.reply_text("❌ Error. ¿Existe ese jugador?")

async def _cmd_quitar_moneda(update, context, moneda: str):
    user_id = update.effective_user.id
    if not _verificar_cmd(user_id, "monedas"):
        await update.effective_message.reply_text("❌ Sin permiso para gestionar monedas.")
        return
    if len(context.args) < 2:
        await update.effective_message.reply_text(f"Uso: /quitar_{moneda} <user_id> <cantidad>")
        return
    try:
        target_id = int(context.args[0])
        cantidad = int(context.args[1])
    except ValueError:
        await update.effective_message.reply_text("Valores inválidos.")
        return
    if cantidad <= 0:
        await update.effective_message.reply_text("La cantidad debe ser positiva.")
        return
    ok = economia.modificar_saldo(target_id, moneda, -cantidad, f"admin_quitar ({user_id})")
    if ok:
        await update.effective_message.reply_text(f"✅ Se quitaron {cantidad} {moneda} al jugador {target_id}.")
    else:
        await update.effective_message.reply_text("❌ Error. ¿Ese jugador tiene suficiente saldo?")

async def cmd_dar_oro(update, context): await _cmd_dar_moneda(update, context, "oro")
async def cmd_quitar_oro(update, context): await _cmd_quitar_moneda(update, context, "oro")
async def cmd_dar_eternium(update, context): await _cmd_dar_moneda(update, context, "eternium")
async def cmd_quitar_eternium(update, context): await _cmd_quitar_moneda(update, context, "eternium")
async def cmd_dar_creditos(update, context): await _cmd_dar_moneda(update, context, "creditos_vacio")
async def cmd_quitar_creditos(update, context): await _cmd_quitar_moneda(update, context, "creditos_vacio")

async def cmd_dar_experiencia(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not _verificar_cmd(user_id, "monedas"):
        await update.effective_message.reply_text("❌ Sin permiso para esta acción.")
        return
    if len(context.args) < 2:
        await update.effective_message.reply_text("Uso: /dar_experiencia <user_id> <cantidad>")
        return
    try:
        target_id = int(context.args[0])
        xp = int(context.args[1])
    except ValueError:
        await update.effective_message.reply_text("Valores inválidos.")
        return
    jug = db_helper.obtener_jugador(target_id)
    if not jug:
        await update.effective_message.reply_text("Jugador no encontrado.")
        return
    nueva_xp = jug["experiencia"] + xp
    db_helper.actualizar_jugador(target_id, experiencia=nueva_xp)
    await update.effective_message.reply_text(f"✅ +{xp} XP al jugador {target_id}. Total XP: {nueva_xp}.")

# ==================== DAR / QUITAR OBJETOS ====================

async def cmd_dar_objeto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not _verificar_cmd(user_id, "objetos"):
        await update.effective_message.reply_text("❌ Sin permiso para gestionar objetos.")
        return
    if len(context.args) < 2:
        await update.effective_message.reply_text("Uso: /dar_objeto <user_id> <nombre_objeto> [cantidad]")
        return
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.effective_message.reply_text("user_id debe ser un número.")
        return
    nombre_objeto = context.args[1]
    cantidad = int(context.args[2]) if len(context.args) > 2 else 1
    if not db_helper.existe_jugador(target_id):
        await update.effective_message.reply_text("Jugador no encontrado.")
        return
    db_helper.agregar_item(target_id, nombre_objeto, cantidad)
    db_helper.agregar_notificacion(target_id, f"🎁 El administrador te dio {cantidad}x {nombre_objeto}.")
    await update.effective_message.reply_text(f"✅ {cantidad}x '{nombre_objeto}' enviado al jugador {target_id}.")

async def cmd_quitar_objeto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not _verificar_cmd(user_id, "objetos"):
        await update.effective_message.reply_text("❌ Sin permiso para gestionar objetos.")
        return
    if len(context.args) < 2:
        await update.effective_message.reply_text("Uso: /quitar_objeto <user_id> <nombre_objeto> [cantidad]")
        return
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.effective_message.reply_text("user_id debe ser un número.")
        return
    nombre_objeto = context.args[1]
    cantidad = int(context.args[2]) if len(context.args) > 2 else 1
    ok = db_helper.quitar_item(target_id, nombre_objeto, cantidad)
    if ok:
        await update.effective_message.reply_text(f"✅ Se quitó {cantidad}x '{nombre_objeto}' al jugador {target_id}.")
    else:
        await update.effective_message.reply_text("❌ El jugador no tiene ese objeto o cantidad insuficiente.")

async def cmd_premios_entregar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entrega un premio a un jugador. Alias de dar_objeto más descriptivo."""
    await cmd_dar_objeto(update, context)

# ==================== GESTIÓN DE JUGADORES ====================

async def cmd_ver_inventario(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not _verificar_cmd(user_id, "objetos"):
        await update.effective_message.reply_text("❌ Sin permiso para ver inventarios.")
        return
    if not context.args:
        await update.effective_message.reply_text("Uso: /ver_inventario <user_id>")
        return
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.effective_message.reply_text("user_id debe ser un número.")
        return
    inv = db_helper.obtener_inventario(target_id)
    if not inv:
        await update.effective_message.reply_text(f"El inventario del jugador {target_id} está vacío.")
        return
    texto = f"🎒 *Inventario del jugador {target_id}:*\n\n"
    for item in inv:
        texto += f"• {item['nombre']} x{item['cantidad']}\n"
    await update.effective_message.reply_text(texto, parse_mode="Markdown")

async def cmd_ver_estadisticas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not _verificar_cmd(user_id, "jugadores"):
        await update.effective_message.reply_text("❌ Sin permiso para esta acción.")
        return
    if not context.args:
        await update.effective_message.reply_text("Uso: /ver_estadisticas <user_id>")
        return
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.effective_message.reply_text("user_id debe ser un número.")
        return
    jug = db_helper.obtener_jugador(target_id)
    if not jug:
        await update.effective_message.reply_text("Jugador no encontrado.")
        return
    saldos = economia.obtener_saldos(target_id)
    texto = (
        f"📊 *Stats de {jug['nombre_personaje']} (ID:{target_id})*\n\n"
        f"Nivel: {jug['nivel']} | Clase: {jug['clase']} | Facción: {jug['faccion']}\n"
        f"HP: {jug['hp_actual']}/{jug['hp_max']}\n"
        f"XP: {jug['experiencia']}\n"
        f"Stamina: {jug.get('stamina_actual',100)}/{jug.get('stamina_maxima',100)}\n"
        f"Zona: {jug.get('zona_actual','?')}\n"
        f"🪙 Oro: {saldos['oro']} | 💎 Eternium: {saldos['eternium']} | ✨ Créditos: {saldos['creditos_vacio']}\n"
        f"Reencarnaciones: {jug.get('reencarnaciones',0)}\n"
        f"Marcado: {'Sí' if db_helper.esta_marcado(target_id) else 'No'}\n"
        f"Baneado: {'Sí' if _es_baneado(target_id) else 'No'}"
    )
    await update.effective_message.reply_text(texto, parse_mode="Markdown")

async def cmd_cambiar_nivel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not _verificar_cmd(user_id, "jugadores"):
        await update.effective_message.reply_text("❌ Sin permiso para esta acción.")
        return
    if len(context.args) < 2:
        await update.effective_message.reply_text("Uso: /cambiar_nivel <user_id> <nivel>")
        return
    try:
        target_id = int(context.args[0])
        nivel = int(context.args[1])
    except ValueError:
        await update.effective_message.reply_text("Valores inválidos.")
        return
    if not db_helper.existe_jugador(target_id):
        await update.effective_message.reply_text("Jugador no encontrado.")
        return
    db_helper.actualizar_jugador(target_id, nivel=max(1, min(nivel, 100)))
    await update.effective_message.reply_text(f"✅ Nivel del jugador {target_id} cambiado a {nivel}.")

async def cmd_cambiar_clase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not _verificar_cmd(user_id, "jugadores"):
        await update.effective_message.reply_text("❌ Sin permiso para esta acción.")
        return
    if len(context.args) < 2:
        await update.effective_message.reply_text("Uso: /cambiar_clase <user_id> <clase>")
        return
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.effective_message.reply_text("user_id debe ser un número.")
        return
    nueva_clase = context.args[1]
    if not db_helper.existe_jugador(target_id):
        await update.effective_message.reply_text("Jugador no encontrado.")
        return
    db_helper.actualizar_jugador(target_id, clase=nueva_clase)
    await update.effective_message.reply_text(f"✅ Clase del jugador {target_id} cambiada a '{nueva_clase}'.")

async def cmd_cambiar_faccion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not _verificar_cmd(user_id, "jugadores"):
        await update.effective_message.reply_text("❌ Sin permiso para esta acción.")
        return
    if len(context.args) < 2:
        await update.effective_message.reply_text("Uso: /cambiar_faccion <user_id> <faccion>")
        return
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.effective_message.reply_text("user_id debe ser un número.")
        return
    nueva_faccion = context.args[1]
    if not db_helper.existe_jugador(target_id):
        await update.effective_message.reply_text("Jugador no encontrado.")
        return
    db_helper.actualizar_jugador(target_id, faccion=nueva_faccion)
    await update.effective_message.reply_text(f"✅ Facción del jugador {target_id} cambiada a '{nueva_faccion}'.")

async def cmd_revivir(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not _verificar_cmd(user_id, "jugadores"):
        await update.effective_message.reply_text("❌ Sin permiso para esta acción.")
        return
    if not context.args:
        await update.effective_message.reply_text("Uso: /revivir <user_id>")
        return
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.effective_message.reply_text("user_id debe ser un número.")
        return
    jug = db_helper.obtener_jugador(target_id)
    if not jug:
        await update.effective_message.reply_text("Jugador no encontrado.")
        return
    db_helper.actualizar_jugador(target_id, hp_actual=jug["hp_max"], stamina_actual=jug.get("stamina_maxima", 100))
    db_helper.agregar_notificacion(target_id, "✨ Un administrador te revivió. ¡HP y stamina restaurados!")
    await update.effective_message.reply_text(f"✅ Jugador {target_id} revivido.")

async def cmd_reset_actividad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not _verificar_cmd(user_id, "jugadores"):
        await update.effective_message.reply_text("❌ Sin permiso para esta acción.")
        return
    if not context.args:
        await update.effective_message.reply_text("Uso: /reset_actividad <user_id>")
        return
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.effective_message.reply_text("user_id debe ser un número.")
        return
    jug = db_helper.obtener_jugador(target_id)
    if not jug:
        await update.effective_message.reply_text("Jugador no encontrado.")
        return
    actividad_anterior = db_helper.get_actividad(target_id) or "ninguna"
    db_helper.set_actividad(target_id, None)
    db_helper.agregar_notificacion(target_id, "🔄 Un administrador ha limpiado tu estado de actividad. Ya puedes actuar con normalidad.")
    await update.effective_message.reply_text(
        f"✅ Actividad de {target_id} limpiada.\n"
        f"Estado anterior: <code>{actividad_anterior}</code>",
        parse_mode="HTML"
    )

async def cmd_marcar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not _verificar_cmd(user_id, "jugadores"):
        await update.effective_message.reply_text("❌ Sin permiso para esta acción.")
        return
    if not context.args:
        await update.effective_message.reply_text("Uso: /marcar <user_id> [segundos]")
        return
    try:
        target_id = int(context.args[0])
        segundos = int(context.args[1]) if len(context.args) > 1 else 3600
    except ValueError:
        await update.effective_message.reply_text("Valores inválidos.")
        return
    db_helper.marcar_jugador(target_id, segundos)
    await update.effective_message.reply_text(f"✅ Jugador {target_id} marcado por {segundos} segundos.")

async def cmd_desmarcar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not _verificar_cmd(user_id, "jugadores"):
        await update.effective_message.reply_text("❌ Sin permiso para esta acción.")
        return
    if not context.args:
        await update.effective_message.reply_text("Uso: /desmarcar <user_id>")
        return
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.effective_message.reply_text("user_id debe ser un número.")
        return
    db_helper.desmarcar_jugador(target_id)
    await update.effective_message.reply_text(f"✅ Marca quitada al jugador {target_id}.")

async def cmd_banear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not _verificar_cmd(user_id, "jugadores"):
        await update.effective_message.reply_text("❌ Sin permiso para esta acción.")
        return
    if not context.args:
        await update.effective_message.reply_text("Uso: /banear <user_id> [motivo]")
        return
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.effective_message.reply_text("user_id debe ser un número.")
        return
    if _es_admin(target_id):
        await update.effective_message.reply_text("No puedes banear a otro admin.")
        return
    motivo = " ".join(context.args[1:]) if len(context.args) > 1 else "Sin motivo"
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO jugadores_baneados (user_id, motivo) VALUES (?, ?)', (target_id, motivo))
    conn.commit()
    conn.close()
    await update.effective_message.reply_text(f"🚫 Jugador {target_id} baneado. Motivo: {motivo}")

async def cmd_desbanear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not _verificar_cmd(user_id, "jugadores"):
        await update.effective_message.reply_text("❌ Sin permiso para esta acción.")
        return
    if not context.args:
        await update.effective_message.reply_text("Uso: /desbanear <user_id>")
        return
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.effective_message.reply_text("user_id debe ser un número.")
        return
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('DELETE FROM jugadores_baneados WHERE user_id = ?', (target_id,))
    conn.commit()
    conn.close()
    await update.effective_message.reply_text(f"✅ Jugador {target_id} desbaneado.")

async def cmd_silenciar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not _verificar_cmd(user_id, "jugadores"):
        await update.effective_message.reply_text("❌ Sin permiso para esta acción.")
        return
    if not context.args:
        await update.effective_message.reply_text("Uso: /silenciar <user_id>")
        return
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.effective_message.reply_text("user_id debe ser un número.")
        return
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('INSERT OR IGNORE INTO jugadores_silenciados (user_id) VALUES (?)', (target_id,))
    conn.commit()
    conn.close()
    await update.effective_message.reply_text(f"🔇 Jugador {target_id} silenciado.")

async def cmd_desilenciar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not _verificar_cmd(user_id, "jugadores"):
        await update.effective_message.reply_text("❌ Sin permiso para esta acción.")
        return
    if not context.args:
        await update.effective_message.reply_text("Uso: /desilenciar <user_id>")
        return
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.effective_message.reply_text("user_id debe ser un número.")
        return
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('DELETE FROM jugadores_silenciados WHERE user_id = ?', (target_id,))
    conn.commit()
    conn.close()
    await update.effective_message.reply_text(f"✅ Jugador {target_id} desilenciado.")

async def cmd_resetear_cooldowns(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not _es_admin(user_id, nivel_minimo=2):
        await update.effective_message.reply_text("❌ Sin permiso (requiere nivel 2).")
        return
    if not context.args:
        await update.effective_message.reply_text("Uso: /resetear_cooldowns <user_id>")
        return
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.effective_message.reply_text("user_id debe ser un número.")
        return
    db_helper.actualizar_jugador(target_id,
        ultima_recoleccion=None,
        fatiga_acumulada=0,
        habilidades_cooldown='{}',
        stamina_actual=100
    )
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('DELETE FROM teletransporte_cooldown WHERE jugador_id = ?', (target_id,))
    conn.commit()
    conn.close()
    await update.effective_message.reply_text(f"✅ Cooldowns del jugador {target_id} reseteados.")

async def cmd_modificar_stamina(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not _verificar_cmd(user_id, "jugadores"):
        await update.effective_message.reply_text("❌ Sin permiso para esta acción.")
        return
    if len(context.args) < 2:
        await update.effective_message.reply_text("Uso: /modificar_stamina <user_id> <cantidad>")
        return
    try:
        target_id = int(context.args[0])
        cantidad = int(context.args[1])
    except ValueError:
        await update.effective_message.reply_text("Valores inválidos.")
        return
    jug = db_helper.obtener_jugador(target_id)
    if not jug:
        await update.effective_message.reply_text("Jugador no encontrado.")
        return
    stamina_actual = jug.get("stamina_actual", 100)
    stamina_max = jug.get("stamina_maxima", 100)
    nueva = max(0, min(stamina_actual + cantidad, stamina_max))
    db_helper.actualizar_jugador(target_id, stamina_actual=nueva)
    await update.effective_message.reply_text(f"✅ Stamina del jugador {target_id}: {stamina_actual} → {nueva} (máx {stamina_max}).")

async def cmd_dar_titulo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not _verificar_cmd(user_id, "jugadores"):
        await update.effective_message.reply_text("❌ Sin permiso para esta acción.")
        return
    if len(context.args) < 2:
        await update.effective_message.reply_text("Uso: /dar_titulo <user_id> <titulo>")
        return
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.effective_message.reply_text("user_id debe ser un número.")
        return
    titulo = " ".join(context.args[1:])
    jug = db_helper.obtener_jugador(target_id)
    if not jug:
        await update.effective_message.reply_text("Jugador no encontrado.")
        return
    logros = json.loads(jug.get("logros_desbloqueados", "[]"))
    if titulo not in logros:
        logros.append(titulo)
        db_helper.actualizar_jugador(target_id, logros_desbloqueados=json.dumps(logros))
    db_helper.agregar_notificacion(target_id, f"🏆 ¡Recibiste el título '{titulo}'!")
    await update.effective_message.reply_text(f"✅ Título '{titulo}' otorgado al jugador {target_id}.")

# ==================== MUNDO Y EVENTOS ====================

async def cmd_cambiar_clima(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not _verificar_cmd(user_id, "mundo"):
        await update.effective_message.reply_text("❌ Sin permiso para gestionar el mundo.")
        return
    if not context.args:
        await update.effective_message.reply_text("Uso: /cambiar_clima <tipo>\nTipos: Soleado, Lluvioso, Tormenta, Nevado, Niebla")
        return
    tipo = context.args[0]
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('UPDATE clima_actual SET tipo_clima = ? WHERE id = 1', (tipo,))
    conn.commit()
    conn.close()
    await update.effective_message.reply_text(f"🌤️ Clima global cambiado a: {tipo}")

async def cmd_iniciar_evento_global(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not _verificar_cmd(user_id, "mundo"):
        await update.effective_message.reply_text("❌ Sin permiso para gestionar el mundo.")
        return
    if len(context.args) < 4:
        await update.effective_message.reply_text("Uso: /iniciar_evento_global <nombre> <efecto> <valor> <horas>")
        return
    nombre = context.args[0]
    efecto = context.args[1]
    try:
        valor = float(context.args[2])
        horas = int(context.args[3])
    except ValueError:
        await update.effective_message.reply_text("valor y horas deben ser números.")
        return
    db_helper.registrar_evento(f"evt_{nombre}", nombre, efecto, valor, horas)
    await update.effective_message.reply_text(f"🌟 Evento '{nombre}' iniciado por {horas} horas.")

async def cmd_rotar_tienda_creditos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not _verificar_cmd(user_id, "mundo"):
        await update.effective_message.reply_text("❌ Sin permiso para gestionar el mundo.")
        return
    try:
        import tienda
        await tienda.generar_rotacion_creditos()
        await update.effective_message.reply_text("🔄 Tienda de créditos rotada exitosamente.")
    except Exception as e:
        await update.effective_message.reply_text(f"❌ Error: {e}")

async def cmd_anular_subasta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not _verificar_cmd(user_id, "mundo"):
        await update.effective_message.reply_text("❌ Sin permiso para gestionar el mundo.")
        return
    if not context.args:
        await update.effective_message.reply_text("Uso: /anular_subasta <id_subasta>")
        return
    try:
        subasta_id = int(context.args[0])
    except ValueError:
        await update.effective_message.reply_text("id_subasta debe ser un número.")
        return
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT vendedor_id, objeto_nombre, cantidad, activa FROM subastas WHERE id = ?', (subasta_id,))
    row = c.fetchone()
    if not row or not row[3]:
        conn.close()
        await update.effective_message.reply_text("Subasta no encontrada o ya inactiva.")
        return
    vendedor_id, objeto_nombre, cantidad, _ = row
    db_helper.agregar_item(vendedor_id, objeto_nombre, cantidad)
    c.execute('UPDATE subastas SET activa = 0 WHERE id = ?', (subasta_id,))
    conn.commit()
    conn.close()
    await update.effective_message.reply_text(f"✅ Subasta #{subasta_id} anulada. Objeto devuelto al vendedor.")

async def cmd_estado_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not _verificar_cmd(user_id, "mundo"):
        await update.effective_message.reply_text("❌ Sin permiso para gestionar el mundo.")
        return
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM jugadores')
    total_jugadores = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM subastas WHERE activa = 1")
    subastas_activas = c.fetchone()[0]
    conn.close()
    nivel = _nivel_admin(user_id)
    tipo = "Superadmin" if _es_superadmin(user_id) else ("Dios" if nivel >= 2 else "Admin")
    await update.effective_message.reply_text(
        f"🤖 *Estado del Bot Aethelgard*\n\n"
        f"👥 Jugadores registrados: {total_jugadores}\n"
        f"🏛️ Subastas activas: {subastas_activas}\n"
        f"👮 Tu nivel: {tipo} (nivel {nivel})",
        parse_mode="Markdown"
    )

# ==================== COMANDOS ADMIN AVANZADOS ====================

async def cmd_ver_perfil_completo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/ver_perfil_completo <user_id> — Muestra TODOS los datos del jugador."""
    user_id = update.effective_user.id
    if not _verificar_cmd(user_id, "jugadores"):
        await update.effective_message.reply_text("❌ Sin permiso.")
        return
    if not context.args:
        await update.effective_message.reply_text("Uso: /ver_perfil_completo <user_id>")
        return
    try:
        tid = int(context.args[0])
    except ValueError:
        await update.effective_message.reply_text("user_id debe ser número.")
        return
    jug = db_helper.obtener_jugador(tid)
    if not jug:
        await update.effective_message.reply_text("Jugador no encontrado.")
        return
    # Monedas
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM transacciones WHERE user_id=? ORDER BY id DESC LIMIT 1", (tid,))
    t = c.fetchone()
    conn.close()
    baneado   = bool(db_helper.obtener_jugador_baneado(tid) if hasattr(db_helper, 'obtener_jugador_baneado') else False)
    inv       = db_helper.obtener_inventario(tid) or []
    n_items   = sum(i.get("cantidad", 1) for i in inv)
    saldo_oro = economia.obtener_saldo(tid, "oro")
    saldo_eth = economia.obtener_saldo(tid, "eternium")
    saldo_cr  = economia.obtener_saldo(tid, "creditos")
    texto = (
        f"👤 *Perfil completo — {jug['nombre_personaje']}*\n"
        f"ID: `{tid}`\n\n"
        f"*📊 Stats base:*\n"
        f"  Nivel: {jug.get('nivel',1)} | XP: {jug.get('experiencia',0)}\n"
        f"  HP: {jug.get('hp_actual',0)}/{jug.get('hp_max',0)}\n"
        f"  Stamina: {jug.get('stamina_actual',0)}/{jug.get('stamina_maxima',100)}\n"
        f"  ATK: {jug.get('ataque',0)} | DEF: {jug.get('defensa',0)}\n\n"
        f"*🏛️ Identidad:*\n"
        f"  Clase: {jug.get('clase','—')} | Facción: {jug.get('faccion','—')}\n"
        f"  Ubicación: {jug.get('ubicacion','ciudad')}\n\n"
        f"*💰 Monedas:*\n"
        f"  Oro: {saldo_oro} | Eternium: {saldo_eth} | Créditos: {saldo_cr}\n\n"
        f"*🎒 Inventario:* {n_items} objetos en {len(inv)} tipos\n\n"
        f"*⚙️ Estado:*\n"
        f"  Baneado: {'❌ Sí' if baneado else '✅ No'}\n"
        f"  Registro: {str(jug.get('fecha_registro','—'))[:16]}"
    )
    botones = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✏️ Editar stats", callback_data=f"ej_menu_{tid}"),
            InlineKeyboardButton("🎒 Ver inventario", callback_data=f"ej_inv_{tid}"),
        ],
        [
            InlineKeyboardButton("💰 Dar recursos", callback_data=f"ej_dar_{tid}"),
            InlineKeyboardButton("🔄 Revivir", callback_data=f"ej_revivir_{tid}"),
        ],
        [InlineKeyboardButton("🔁 Actualizar", callback_data=f"ej_refresh_{tid}")],
    ])
    await update.effective_message.reply_text(texto, reply_markup=botones, parse_mode="Markdown")


async def cb_editar_jugador(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callbacks ej_* del editor de jugador inline."""
    query   = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    if not _es_admin(user_id):
        await query.answer("❌ Sin permiso.", show_alert=True)
        return
    data  = query.data
    parts = data.split("_")

    # ej_revivir_{tid}
    if data.startswith("ej_revivir_"):
        try:
            tid = int(parts[-1])
        except (ValueError, IndexError):
            return
        jug = db_helper.obtener_jugador(tid)
        if jug:
            db_helper.actualizar_jugador(tid, hp_actual=jug["hp_max"],
                                          stamina_actual=jug.get("stamina_maxima", 100))
            db_helper.agregar_notificacion(tid, "✨ Un admin te revivió. HP y stamina restaurados.")
        await query.answer("✅ Jugador revivido.", show_alert=True)
        return

    # ej_refresh_{tid}
    if data.startswith("ej_refresh_"):
        try:
            tid = int(parts[-1])
        except (ValueError, IndexError):
            return
        jug = db_helper.obtener_jugador(tid)
        if not jug:
            await query.edit_message_text("Jugador no encontrado.")
            return
        saldo_oro = economia.obtener_saldo(tid, "oro")
        saldo_eth = economia.obtener_saldo(tid, "eternium")
        saldo_cr  = economia.obtener_saldo(tid, "creditos")
        inv       = db_helper.obtener_inventario(tid) or []
        n_items   = sum(i.get("cantidad", 1) for i in inv)
        texto = (
            f"👤 *Perfil — {jug['nombre_personaje']}*  ID:`{tid}`\n\n"
            f"Nivel {jug.get('nivel',1)} | XP {jug.get('experiencia',0)}\n"
            f"HP {jug.get('hp_actual',0)}/{jug.get('hp_max',0)} | "
            f"STM {jug.get('stamina_actual',0)}/{jug.get('stamina_maxima',100)}\n"
            f"ATK {jug.get('ataque',0)} | DEF {jug.get('defensa',0)}\n"
            f"Clase {jug.get('clase','—')} | Facción {jug.get('faccion','—')}\n"
            f"💰 Oro {saldo_oro} | ETH {saldo_eth} | CR {saldo_cr}\n"
            f"🎒 {n_items} objetos"
        )
        botones = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✏️ Editar stats", callback_data=f"ej_menu_{tid}"),
                InlineKeyboardButton("💰 Dar recursos", callback_data=f"ej_dar_{tid}"),
            ],
            [
                InlineKeyboardButton("🔄 Revivir", callback_data=f"ej_revivir_{tid}"),
                InlineKeyboardButton("🔁 Actualizar", callback_data=f"ej_refresh_{tid}"),
            ],
        ])
        await query.edit_message_text(texto, reply_markup=botones, parse_mode="Markdown")
        return

    # ej_menu_{tid}
    if data.startswith("ej_menu_"):
        try:
            tid = int(parts[-1])
        except (ValueError, IndexError):
            return
        jug = db_helper.obtener_jugador(tid)
        if not jug:
            await query.edit_message_text("Jugador no encontrado.")
            return
        botones = InlineKeyboardMarkup([
            [InlineKeyboardButton("⚔️ ATK", callback_data=f"ej_edit_{tid}_ataque"),
             InlineKeyboardButton("🛡️ DEF", callback_data=f"ej_edit_{tid}_defensa")],
            [InlineKeyboardButton("❤️ HP Max", callback_data=f"ej_edit_{tid}_hp_max"),
             InlineKeyboardButton("💚 HP Actual", callback_data=f"ej_edit_{tid}_hp_actual")],
            [InlineKeyboardButton("⚡ Nivel",   callback_data=f"ej_edit_{tid}_nivel"),
             InlineKeyboardButton("⭐ XP",      callback_data=f"ej_edit_{tid}_experiencia")],
            [InlineKeyboardButton("🏃 Stamina", callback_data=f"ej_edit_{tid}_stamina_actual"),
             InlineKeyboardButton("🏃 STM Max", callback_data=f"ej_edit_{tid}_stamina_maxima")],
            [InlineKeyboardButton("↩️ Volver",  callback_data=f"ej_refresh_{tid}")],
        ])
        await query.edit_message_text(
            f"✏️ *Editar stats de {jug['nombre_personaje']}*\n\n"
            f"ATK:{jug.get('ataque',0)} DEF:{jug.get('defensa',0)} "
            f"HP:{jug.get('hp_actual',0)}/{jug.get('hp_max',0)} "
            f"Niv:{jug.get('nivel',1)} XP:{jug.get('experiencia',0)}\n\n"
            f"Elige el campo a editar:",
            reply_markup=botones, parse_mode="Markdown"
        )
        return

    # ej_edit_{tid}_{campo}
    if data.startswith("ej_edit_"):
        try:
            tid   = int(parts[2])
            campo = "_".join(parts[3:])
        except (ValueError, IndexError):
            return
        context.user_data["ej_tid"]   = tid
        context.user_data["ej_campo"] = campo
        await query.edit_message_text(
            f"✏️ Editar *{campo}* del jugador `{tid}`\n\nEscribe el nuevo valor numérico:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Cancelar", callback_data=f"ej_refresh_{tid}")]
            ]),
            parse_mode="Markdown"
        )
        return

    # ej_dar_{tid}
    if data.startswith("ej_dar_"):
        try:
            tid = int(parts[-1])
        except (ValueError, IndexError):
            return
        context.user_data["ej_dar_tid"] = tid
        await query.edit_message_text(
            f"💰 *Dar recursos al jugador* `{tid}`\n\n"
            f"Escribe en formato:\n`oro:1000 eternium:500 creditos:100`\n"
            f"_(puedes omitir los que no quieras cambiar)_",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Cancelar", callback_data=f"ej_refresh_{tid}")]
            ]),
            parse_mode="Markdown"
        )
        return

    # ej_inv_{tid}
    if data.startswith("ej_inv_"):
        try:
            tid = int(parts[-1])
        except (ValueError, IndexError):
            return
        inv = db_helper.obtener_inventario(tid) or []
        if not inv:
            await query.answer("El inventario está vacío.", show_alert=True)
            return
        texto = f"🎒 *Inventario de* `{tid}`\n\n"
        for item in inv[:20]:
            texto += f"• {item['nombre']} ×{item.get('cantidad',1)}\n"
        if len(inv) > 20:
            texto += f"\n_...y {len(inv)-20} más_"
        await query.edit_message_text(
            texto,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Volver", callback_data=f"ej_refresh_{tid}")]]),
            parse_mode="Markdown"
        )
        return


async def _ej_recibir_texto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recibe valores del editor inline de jugador."""
    user_id = update.effective_user.id
    if not _es_admin(user_id):
        return
    texto = update.effective_message.text.strip()

    # Edición de campo de stat
    if "ej_tid" in context.user_data and "ej_campo" in context.user_data:
        tid   = context.user_data.pop("ej_tid")
        campo = context.user_data.pop("ej_campo")
        try:
            val = int(texto)
        except ValueError:
            await update.effective_message.reply_text("❌ Debe ser un número entero.")
            return
        db_helper.actualizar_jugador(tid, **{campo: val})
        db_helper.agregar_notificacion(tid, f"⚙️ Un administrador modificó tu {campo} a {val}.")
        jug = db_helper.obtener_jugador(tid)
        nombre = jug["nombre_personaje"] if jug else str(tid)
        await update.effective_message.reply_text(
            f"✅ *{campo}* de *{nombre}* → *{val}*\n\n"
            f"Usa /ver_perfil_completo {tid} para ver el perfil actualizado.",
            parse_mode="Markdown"
        )
        return

    # Dar recursos en formato "oro:1000 eternium:500 creditos:100"
    if "ej_dar_tid" in context.user_data:
        tid = context.user_data.pop("ej_dar_tid")
        if not db_helper.existe_jugador(tid):
            await update.effective_message.reply_text("Jugador no encontrado.")
            return
        try:
            partes = {}
            for par in texto.split():
                k, v = par.split(":")
                partes[k.strip().lower()] = int(v.strip())
        except Exception:
            await update.effective_message.reply_text(
                "❌ Formato inválido. Usa: `oro:1000 eternium:500 creditos:100`",
                parse_mode="Markdown"
            )
            return
        lines = []
        for mon in ["oro", "eternium", "creditos"]:
            if mon in partes and partes[mon] != 0:
                economia.modificar_saldo(tid, mon, partes[mon], "admin_dar")
                lines.append(f"+{partes[mon]} {mon}")
        if lines:
            db_helper.agregar_notificacion(tid, f"🎁 Admin te dio: {', '.join(lines)}.")
            await update.effective_message.reply_text(
                f"✅ Recursos entregados al jugador `{tid}`:\n" + "\n".join(f"• {l}" for l in lines),
                parse_mode="Markdown"
            )
        else:
            await update.effective_message.reply_text("❌ No se especificó ningún recurso válido.")
        return


async def cmd_ajuste_global(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/ajuste_global <tipo> <porcentaje> — Ajuste porcentual masivo a todos los jugadores.
    tipo: oro | eternium | xp | hp
    Ej: /ajuste_global oro +10  (da +10% del saldo actual a todos los jugadores)
    """
    user_id = update.effective_user.id
    if not _es_superadmin(user_id):
        await update.effective_message.reply_text("❌ Solo el superadmin puede usar ajustes globales.")
        return
    if len(context.args) < 2:
        await update.effective_message.reply_text(
            "Uso: /ajuste_global <tipo> <±porcentaje>\n"
            "Tipos: oro | eternium | xp | hp\n"
            "Ej: `/ajuste_global oro +10` (da 10% del saldo a cada jugador)",
            parse_mode="Markdown"
        )
        return
    tipo = context.args[0].lower()
    if tipo not in ("oro", "eternium", "xp", "hp"):
        await update.effective_message.reply_text("Tipo inválido. Usa: oro | eternium | xp | hp")
        return
    try:
        pct = float(context.args[1].replace("+", ""))
    except ValueError:
        await update.effective_message.reply_text("Porcentaje inválido. Ej: +10 o -5")
        return
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT user_id FROM jugadores")
    uids = [r[0] for r in c.fetchall()]
    conn.close()
    afectados = 0
    for uid in uids:
        try:
            if tipo in ("oro", "eternium"):
                saldo_actual = economia.obtener_saldo(uid, tipo)
                delta = int(saldo_actual * pct / 100)
                if delta != 0:
                    economia.modificar_saldo(uid, tipo, delta, "ajuste_global_admin")
                    afectados += 1
            elif tipo == "xp":
                jug = db_helper.obtener_jugador(uid)
                if jug:
                    delta = int(jug["experiencia"] * pct / 100)
                    if delta != 0:
                        db_helper.actualizar_jugador(uid, experiencia=max(0, jug["experiencia"] + delta))
                        afectados += 1
            elif tipo == "hp":
                jug = db_helper.obtener_jugador(uid)
                if jug:
                    delta = int(jug["hp_max"] * pct / 100)
                    nuevo_hp = max(1, min(jug["hp_actual"] + delta, jug["hp_max"]))
                    db_helper.actualizar_jugador(uid, hp_actual=nuevo_hp)
                    afectados += 1
        except Exception:
            pass
    await update.effective_message.reply_text(
        f"✅ *Ajuste global aplicado*\n\n"
        f"Tipo: *{tipo}* | Porcentaje: *{pct:+.1f}%*\n"
        f"Jugadores afectados: *{afectados}*",
        parse_mode="Markdown"
    )


async def cmd_dar_masivo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/dar_masivo <tipo> <cantidad> — Da la cantidad fija a TODOS los jugadores.
    tipo: oro | eternium | creditos | xp
    Ej: /dar_masivo oro 500
    """
    user_id = update.effective_user.id
    if not _es_superadmin(user_id):
        await update.effective_message.reply_text("❌ Solo el superadmin puede usar esto.")
        return
    if len(context.args) < 2:
        await update.effective_message.reply_text("Uso: /dar_masivo <oro|eternium|creditos|xp> <cantidad>")
        return
    tipo = context.args[0].lower()
    if tipo not in ("oro", "eternium", "creditos", "xp"):
        await update.effective_message.reply_text("Tipo inválido. Usa: oro | eternium | creditos | xp")
        return
    try:
        cantidad = int(context.args[1])
    except ValueError:
        await update.effective_message.reply_text("Cantidad debe ser número entero.")
        return
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT user_id FROM jugadores")
    uids = [r[0] for r in c.fetchall()]
    conn.close()
    afectados = 0
    for uid in uids:
        try:
            if tipo == "xp":
                jug = db_helper.obtener_jugador(uid)
                if jug:
                    db_helper.actualizar_jugador(uid, experiencia=max(0, jug["experiencia"] + cantidad))
            else:
                economia.modificar_saldo(uid, tipo, cantidad, "dar_masivo_admin")
            db_helper.agregar_notificacion(uid, f"🎁 Regalo global: +{cantidad} {tipo}.")
            afectados += 1
        except Exception:
            pass
    await update.effective_message.reply_text(
        f"✅ *{cantidad} {tipo}* enviado a *{afectados}* jugadores.",
        parse_mode="Markdown"
    )


async def cmd_limpiar_penalizaciones(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/limpiar_penalizaciones <user_id> — Borra todas las penalizaciones, bans y cooldowns."""
    user_id = update.effective_user.id
    if not _verificar_cmd(user_id, "jugadores"):
        await update.effective_message.reply_text("❌ Sin permiso.")
        return
    if not context.args:
        await update.effective_message.reply_text("Uso: /limpiar_penalizaciones <user_id>")
        return
    try:
        tid = int(context.args[0])
    except ValueError:
        await update.effective_message.reply_text("user_id debe ser número.")
        return
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM jugadores_baneados WHERE user_id=?", (tid,))
    c.execute("DELETE FROM jugadores_silenciados WHERE user_id=?", (tid,))
    c.execute("DELETE FROM penalizacion_peleas WHERE user_id=?", (tid,))
    c.execute("DELETE FROM estado_paz WHERE user_id=?", (tid,))
    c.execute("DELETE FROM teletransporte_cooldown WHERE user_id=?", (tid,))
    conn.commit()
    conn.close()
    db_helper.agregar_notificacion(tid, "✅ Un administrador limpió todas tus penalizaciones.")
    await update.effective_message.reply_text(
        f"✅ Penalizaciones, ban, silencio y cooldowns de `{tid}` eliminados.", parse_mode="Markdown"
    )


async def cmd_limpiar_actividad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/limpiar_actividad <user_id> — Libera a un jugador atascado en combate/mazmorra."""
    user_id = update.effective_user.id
    if not _verificar_cmd(user_id, "jugadores"):
        await update.effective_message.reply_text("❌ Sin permiso.")
        return
    if not context.args:
        await update.effective_message.reply_text("Uso: /limpiar_actividad <user_id>")
        return
    try:
        tid = int(context.args[0])
    except ValueError:
        await update.effective_message.reply_text("user_id debe ser número.")
        return
    jug = db_helper.obtener_jugador(tid)
    if not jug:
        await update.effective_message.reply_text(f"❌ Jugador {tid} no encontrado.")
        return
    actividad_anterior = jug.get("actividad_actual") or "ninguna"
    db_helper.set_actividad(tid, None)
    db_helper.agregar_notificacion(tid, "✅ Un administrador liberó tu actividad bloqueada.")
    await update.effective_message.reply_text(
        f"✅ Actividad de `{jug['nombre_personaje']}` ({tid}) liberada.\n"
        f"Estado anterior: `{actividad_anterior}`",
        parse_mode="Markdown"
    )


async def cmd_set_hp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/set_hp <user_id> <valor> — Establece el HP actual de un jugador."""
    user_id = update.effective_user.id
    if not _verificar_cmd(user_id, "jugadores"):
        await update.effective_message.reply_text("❌ Sin permiso.")
        return
    if len(context.args) < 2:
        await update.effective_message.reply_text("Uso: /set_hp <user_id> <valor>")
        return
    try:
        tid = int(context.args[0])
        val = int(context.args[1])
    except ValueError:
        await update.effective_message.reply_text("Valores inválidos.")
        return
    jug = db_helper.obtener_jugador(tid)
    if not jug:
        await update.effective_message.reply_text("Jugador no encontrado.")
        return
    hp_nuevo = max(0, min(val, jug["hp_max"]))
    db_helper.actualizar_jugador(tid, hp_actual=hp_nuevo)
    await update.effective_message.reply_text(f"✅ HP de `{tid}` → *{hp_nuevo}/{jug['hp_max']}*", parse_mode="Markdown")


async def cmd_set_atk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/set_atk <user_id> <valor> — Establece el ataque de un jugador."""
    user_id = update.effective_user.id
    if not _verificar_cmd(user_id, "jugadores"):
        await update.effective_message.reply_text("❌ Sin permiso.")
        return
    if len(context.args) < 2:
        await update.effective_message.reply_text("Uso: /set_atk <user_id> <valor>")
        return
    try:
        tid = int(context.args[0])
        val = int(context.args[1])
    except ValueError:
        await update.effective_message.reply_text("Valores inválidos.")
        return
    if not db_helper.existe_jugador(tid):
        await update.effective_message.reply_text("Jugador no encontrado.")
        return
    db_helper.actualizar_jugador(tid, ataque=max(1, val))
    await update.effective_message.reply_text(f"✅ ATK de `{tid}` → *{val}*", parse_mode="Markdown")


async def cmd_set_def(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/set_def <user_id> <valor> — Establece la defensa de un jugador."""
    user_id = update.effective_user.id
    if not _verificar_cmd(user_id, "jugadores"):
        await update.effective_message.reply_text("❌ Sin permiso.")
        return
    if len(context.args) < 2:
        await update.effective_message.reply_text("Uso: /set_def <user_id> <valor>")
        return
    try:
        tid = int(context.args[0])
        val = int(context.args[1])
    except ValueError:
        await update.effective_message.reply_text("Valores inválidos.")
        return
    if not db_helper.existe_jugador(tid):
        await update.effective_message.reply_text("Jugador no encontrado.")
        return
    db_helper.actualizar_jugador(tid, defensa=max(0, val))
    await update.effective_message.reply_text(f"✅ DEF de `{tid}` → *{val}*", parse_mode="Markdown")


async def cmd_set_xp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/set_xp <user_id> <valor> — Establece la XP exacta de un jugador."""
    user_id = update.effective_user.id
    if not _verificar_cmd(user_id, "jugadores"):
        await update.effective_message.reply_text("❌ Sin permiso.")
        return
    if len(context.args) < 2:
        await update.effective_message.reply_text("Uso: /set_xp <user_id> <valor>")
        return
    try:
        tid = int(context.args[0])
        val = int(context.args[1])
    except ValueError:
        await update.effective_message.reply_text("Valores inválidos.")
        return
    if not db_helper.existe_jugador(tid):
        await update.effective_message.reply_text("Jugador no encontrado.")
        return
    db_helper.actualizar_jugador(tid, experiencia=max(0, val))
    await update.effective_message.reply_text(f"✅ XP de `{tid}` → *{val}*", parse_mode="Markdown")


async def cmd_set_stamina_exacta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/set_stamina <user_id> <actual> [max] — Establece stamina actual y opcionalmente la máxima."""
    user_id = update.effective_user.id
    if not _verificar_cmd(user_id, "jugadores"):
        await update.effective_message.reply_text("❌ Sin permiso.")
        return
    if len(context.args) < 2:
        await update.effective_message.reply_text("Uso: /set_stamina <user_id> <actual> [max]")
        return
    try:
        tid  = int(context.args[0])
        act  = int(context.args[1])
        maxi = int(context.args[2]) if len(context.args) > 2 else None
    except ValueError:
        await update.effective_message.reply_text("Valores inválidos.")
        return
    if not db_helper.existe_jugador(tid):
        await update.effective_message.reply_text("Jugador no encontrado.")
        return
    kwargs: dict = {"stamina_actual": max(0, act)}
    if maxi is not None:
        kwargs["stamina_maxima"] = max(1, maxi)
    db_helper.actualizar_jugador(tid, **kwargs)
    sufijo = f"/{maxi}" if maxi else ""
    await update.effective_message.reply_text(f"✅ Stamina de `{tid}` → *{act}{sufijo}*", parse_mode="Markdown")


async def cmd_lista_jugadores(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/lista_jugadores [pagina] — Lista todos los jugadores registrados."""
    user_id = update.effective_user.id
    if not _verificar_cmd(user_id, "jugadores"):
        await update.effective_message.reply_text("❌ Sin permiso.")
        return
    try:
        pag = int(context.args[0]) if context.args else 1
    except ValueError:
        pag = 1
    pag   = max(1, pag)
    limit = 15
    off   = (pag - 1) * limit
    conn  = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM jugadores")
    total = c.fetchone()[0]
    c.execute(
        "SELECT user_id, nombre_personaje, nivel, clase, faccion FROM jugadores "
        "ORDER BY nivel DESC, user_id LIMIT ? OFFSET ?",
        (limit, off)
    )
    rows = c.fetchall()
    conn.close()
    if not rows:
        await update.effective_message.reply_text("No hay jugadores registrados.")
        return
    texto = f"👥 *Jugadores* (p.{pag} — {total} total)\n\n"
    for r in rows:
        texto += (f"`{r['user_id']}` — *{_esc_md(r['nombre_personaje'])}* "
                  f"Niv.{r['nivel']} {r['clase'] or '?'} [{r['faccion'] or '?'}]\n")
    paginas = (total + limit - 1) // limit
    texto += f"\n_Página {pag}/{paginas}_\n/lista\\_jugadores {pag+1} para siguiente"
    await update.effective_message.reply_text(texto, parse_mode="Markdown")


# ==================== BUSCADOR DE PREMIOS ====================

async def cmd_premios_buscar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not _verificar_cmd(user_id, "objetos"):
        await update.effective_message.reply_text("❌ Sin permiso para gestionar objetos.")
        return
    try:
        from armas import ARMAS
        from armaduras import ARMADURAS
        from materiales import MATERIALES
        from monturas import MONTURAS
        import random
        pool = []
        for k, v in ARMAS.items():
            pool.append({"id": k, "nombre": v["nombre"], "tipo": "Arma"})
        for k, v in ARMADURAS.items():
            pool.append({"id": k, "nombre": v["nombre"], "tipo": "Armadura"})
        for k, v in MATERIALES.items():
            pool.append({"id": k, "nombre": v["nombre"], "tipo": "Material"})
        for k, v in MONTURAS.items():
            pool.append({"id": k, "nombre": v["nombre"], "tipo": "Montura"})

        seleccion = random.sample(pool, min(5, len(pool)))
        context.user_data["premios_seleccionados"] = context.user_data.get("premios_seleccionados", [])

        texto = "🎁 *Buscador de Premios* (muestra aleatoria)\n\n"
        botones = []
        for item in seleccion:
            texto += f"• [{item['tipo']}] {item['nombre']} (ID: {item['id']})\n"
            botones.append([InlineKeyboardButton(f"✅ Seleccionar {item['nombre']}", callback_data=f"premio_sel_{item['id']}_{item['nombre']}")])
        botones.append([InlineKeyboardButton("🔄 Nueva búsqueda", callback_data="premios_buscar_nuevo")])
        botones.append([InlineKeyboardButton("📋 Ver seleccionados", callback_data="premios_ver_lista")])
        botones.append([InlineKeyboardButton("🗑️ Limpiar lista", callback_data="premios_limpiar")])

        msg = update.effective_message
        await msg.reply_text(texto, reply_markup=InlineKeyboardMarkup(botones), parse_mode="Markdown")
    except ImportError as e:
        await update.effective_message.reply_text(f"❌ Error cargando catálogos: {e}")

async def cb_premios_buscar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    if not _es_admin(user_id):
        await query.edit_message_text("❌ Sin permiso.")
        return
    data = query.data

    if data == "premios_buscar_nuevo":
        try:
            from armas import ARMAS
            from armaduras import ARMADURAS
            from materiales import MATERIALES
            from monturas import MONTURAS
            import random
            pool = []
            for k, v in ARMAS.items():
                pool.append({"id": k, "nombre": v["nombre"], "tipo": "Arma"})
            for k, v in ARMADURAS.items():
                pool.append({"id": k, "nombre": v["nombre"], "tipo": "Armadura"})
            for k, v in MATERIALES.items():
                pool.append({"id": k, "nombre": v["nombre"], "tipo": "Material"})
            for k, v in MONTURAS.items():
                pool.append({"id": k, "nombre": v["nombre"], "tipo": "Montura"})
            seleccion = random.sample(pool, min(5, len(pool)))
            import html as _hl
            texto = "🎁 <b>Buscador de Premios</b> (muestra aleatoria)\n\n"
            botones = []
            for item in seleccion:
                texto += f"• [{_hl.escape(item['tipo'])}] {_hl.escape(item['nombre'])}\n"
                nombre_cb = item['nombre'][:20].replace(" ", "_")
                botones.append([InlineKeyboardButton(
                    f"✅ {item['nombre'][:28]}", callback_data=f"premio_sel_{item['id']}_{nombre_cb}"
                )])
            botones.append([InlineKeyboardButton("🔄 Nueva búsqueda", callback_data="premios_buscar_nuevo")])
            botones.append([InlineKeyboardButton("📋 Ver seleccionados", callback_data="premios_ver_lista")])
            botones.append([InlineKeyboardButton("🗑️ Limpiar lista", callback_data="premios_limpiar")])
            await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(botones), parse_mode="HTML")
        except Exception as e:
            await query.edit_message_text(f"❌ Error en búsqueda: {e}")
    elif data.startswith("premio_sel_"):
        parts = data.split("_", 3)
        obj_id = parts[2] if len(parts) > 2 else "?"
        obj_nombre = parts[3].replace("_", " ") if len(parts) > 3 else obj_id
        lista = context.user_data.get("premios_seleccionados", [])
        lista.append({"id": obj_id, "nombre": obj_nombre})
        context.user_data["premios_seleccionados"] = lista
        await query.answer(f"✅ Añadido a la lista.", show_alert=False)
    elif data == "premios_ver_lista":
        lista = context.user_data.get("premios_seleccionados", [])
        if not lista:
            await query.answer("La lista está vacía.", show_alert=True)
            return
        texto = "📋 *Premios seleccionados:*\n\n"
        for item in lista:
            texto += f"• {item['nombre']} (ID: {item['id']})\n"
        texto += "\nUsa /premios_entregar <user_id> <nombre_objeto> [cantidad] para entregar."
        botones = [[InlineKeyboardButton("« Volver", callback_data="premios_buscar_nuevo"),
                    InlineKeyboardButton("🗑️ Limpiar", callback_data="premios_limpiar")]]
        await query.edit_message_text(texto, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(botones))
    elif data == "premios_limpiar":
        context.user_data["premios_seleccionados"] = []
        await query.answer("🗑️ Lista vaciada.", show_alert=False)

# ==================== PANEL DE PREMIOS ====================
import random as _rnd
import html as _html_mod

def _e(s) -> str:
    """Escapa caracteres especiales HTML para textos dinámicos."""
    return _html_mod.escape(str(s))

_PP_TIPOS = ["arma", "armadura", "material", "montura"]
_PP_ZONAS = ["azul", "amarilla", "roja", "negra"]

def _pp_crear_evento(evento_tipo: str, evento_desc: str, ganadores_json: str) -> int:
    conn = sqlite3.connect(db_helper.DB_PATH)
    c = conn.cursor()
    fecha = datetime.now().strftime("%Y-%m-%d %H:%M")
    c.execute(
        "INSERT INTO premios_pendientes (evento_tipo,evento_desc,ganadores_json,estado,fecha) VALUES (?,?,?,?,?)",
        (evento_tipo, evento_desc, ganadores_json, "pendiente", fecha)
    )
    eid = c.lastrowid
    conn.commit(); conn.close()
    return eid

def _pp_obtener_pendientes() -> List[Dict]:
    conn = sqlite3.connect(db_helper.DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM premios_pendientes WHERE estado='pendiente' ORDER BY id DESC LIMIT 20")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows

def _pp_obtener_evento(eid: int) -> Optional[Dict]:
    conn = sqlite3.connect(db_helper.DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM premios_pendientes WHERE id=?", (eid,))
    r = c.fetchone()
    conn.close()
    return dict(r) if r else None

def _pp_marcar_estado(eid: int, estado: str):
    conn = sqlite3.connect(db_helper.DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE premios_pendientes SET estado=? WHERE id=?", (estado, eid))
    conn.commit(); conn.close()

def _pp_filtro(clave: str, default: str) -> str:
    return db_helper.obtener_config(f"ap_{clave}", default)

def _pp_set_filtro(clave: str, val: str):
    db_helper.establecer_config(f"ap_{clave}", val)

def _pp_auto_activo() -> bool:
    return db_helper.obtener_config("auto_premios_activo", "0") == "1"

def _pp_pool() -> List[Dict]:
    tipos_ok = set(_pp_filtro("tipos", "arma,armadura,material,montura").split(","))
    zonas_ok = set(_pp_filtro("zonas", "azul,amarilla,roja,negra").split(","))
    try: rmin = int(_pp_filtro("rmin", "1"))
    except: rmin = 1
    try: rmax = int(_pp_filtro("rmax", "12"))
    except: rmax = 12
    try: nmin = int(_pp_filtro("nmin", "1"))
    except: nmin = 1
    try: nmax = int(_pp_filtro("nmax", "100"))
    except: nmax = 100
    clases_raw = _pp_filtro("clases", "")
    clases_ok = set(clases_raw.split(",")) if clases_raw else set()
    pool: List[Dict] = []
    try:
        if "arma" in tipos_ok:
            from armas import ARMAS
            for k, v in ARMAS.items():
                if v.get("unica") and v.get("dueño_actual"): continue
                if v.get("zona") not in zonas_ok: continue
                if not (rmin <= v.get("rareza", 1) <= rmax): continue
                if not (nmin <= v.get("nivel_requerido", 1) <= nmax): continue
                if clases_ok and v.get("clase_requerida") not in clases_ok: continue
                pool.append({"id": k, "nombre": v["nombre"], "tipo": "Arma", "rareza": v.get("rareza", 1), "zona": v.get("zona","?")})
    except Exception: pass
    try:
        if "armadura" in tipos_ok:
            from armaduras import ARMADURAS
            for k, v in ARMADURAS.items():
                if v.get("zona") not in zonas_ok: continue
                if not (rmin <= v.get("rareza", 1) <= rmax): continue
                if not (nmin <= v.get("nivel_requerido", 1) <= nmax): continue
                if clases_ok and v.get("clase_requerida") not in clases_ok: continue
                pool.append({"id": k, "nombre": v["nombre"], "tipo": "Armadura", "rareza": v.get("rareza", 1), "zona": v.get("zona","?")})
    except Exception: pass
    try:
        if "material" in tipos_ok:
            from materiales import MATERIALES
            for k, v in MATERIALES.items():
                if v.get("zona") not in zonas_ok: continue
                if not (rmin <= v.get("rareza", 1) <= rmax): continue
                pool.append({"id": k, "nombre": v["nombre"], "tipo": "Material", "rareza": v.get("rareza", 1), "zona": v.get("zona","?")})
    except Exception: pass
    try:
        if "montura" in tipos_ok:
            from monturas import MONTURAS
            for k, v in MONTURAS.items():
                pool.append({"id": k, "nombre": v["nombre"], "tipo": "Montura", "rareza": v.get("rareza", 1), "zona": "todas"})
    except Exception: pass
    return pool

_PP_TIPOS_EVENTO = ["guerra_facciones", "guerra_gremios", "jefes", "umbral_vacio"]
_PP_NOMBRE_EVENTO = {
    "guerra_facciones": "⚔️ Guerra Facciones",
    "guerra_gremios":   "🏰 Guerra Gremios",
    "jefes":            "🐉 Jefes Zona",
    "umbral_vacio":     "🌑 Umbral del Vacío",
}

def _pp_auto_activo_ev(tipo: str) -> bool:
    """Auto-premio activo para un tipo de evento específico. Si no está configurado usa el global."""
    val = db_helper.obtener_config(f"auto_premios_{tipo}", "")
    if val == "": return _pp_auto_activo()
    return val == "1"

def _pp_set_auto_ev(tipo: str, activo: bool):
    db_helper.establecer_config(f"auto_premios_{tipo}", "1" if activo else "0")

def _pp_oro_ev(tipo: str) -> int:
    """Oro automático por ganador para este tipo de evento."""
    try: return int(db_helper.obtener_config(f"pp_oro_{tipo}", "0"))
    except: return 0

def _pp_set_oro_ev(tipo: str, val: int):
    db_helper.establecer_config(f"pp_oro_{tipo}", str(max(0, val)))

def _pp_eternium_ev(tipo: str) -> int:
    """Eternium automático por ganador para este tipo de evento."""
    try: return int(db_helper.obtener_config(f"pp_eternium_{tipo}", "0"))
    except: return 0

def _pp_set_eternium_ev(tipo: str, val: int):
    db_helper.establecer_config(f"pp_eternium_{tipo}", str(max(0, val)))

def _pp_batch_size() -> int:
    """Tamaño del lote para el modo colectivo por grupos."""
    try: return max(1, int(db_helper.obtener_config("pp_batch_size", "5")))
    except: return 5

def _pp_set_batch_size(val: int):
    db_helper.establecer_config("pp_batch_size", str(max(1, val)))

def _pp_random_item(pool: Optional[List[Dict]] = None) -> Optional[Dict]:
    if pool is None:
        pool = _pp_pool()
    if not pool:
        return None
    weights = [max(1, 14 - item.get("rareza", 1)) for item in pool]
    return _rnd.choices(pool, weights=weights, k=1)[0]

def _pp_roll_all(ev: Dict, bd: dict):
    gans = json.loads(ev["ganadores_json"])
    pool = _pp_pool()
    sel: Dict = {}
    for g in gans:
        item = _pp_random_item(pool)
        if item:
            sel[str(g["user_id"])] = item
    bd[f"pp_sel_{ev['id']}"] = sel

def _pp_entregar_item_db(user_id: int, item: Dict):
    db_helper.agregar_item(user_id, item["nombre"], 1)
    db_helper.agregar_notificacion(user_id,
        f"🎁 *¡Premio especial recibido!*\n"
        f"🏆 {item['nombre']} ({item['tipo']}, ★{item.get('rareza',1)}) — zonas {item.get('zona','?')}\n"
        f"_Otorgado por los administradores. ¡Úsalo bien!_")

def _pp_entregar_economia(user_id: int, oro: int, eternium: int, evento_desc: str):
    """Entrega oro y/o eternium a un jugador con notificación."""
    try:
        import economia as _eco
        lineas = []
        if oro > 0:
            _eco.modificar_saldo(user_id, "oro", oro, f"premio evento: {evento_desc}")
            lineas.append(f"💰 +{oro:,} oro")
        if eternium > 0:
            _eco.modificar_saldo(user_id, "eternium", eternium, f"premio evento: {evento_desc}")
            lineas.append(f"💎 +{eternium} eternium")
        if lineas:
            db_helper.agregar_notificacion(user_id,
                f"🎁 *¡Premio de evento recibido!*\n" +
                "\n".join(lineas) +
                f"\n_Evento: {evento_desc}_")
    except Exception:
        pass

async def _pp_send_admin(bot, text: str, reply_markup=None):
    if SUPERADMIN_ID:
        try:
            await bot.send_message(SUPERADMIN_ID, text, parse_mode="HTML", reply_markup=reply_markup)
        except Exception:
            pass

async def notificar_admin_victoria(bot, evento_tipo: str, evento_desc: str, ganadores: List[Dict]):
    if not ganadores:
        return
    gan_json = json.dumps(ganadores, ensure_ascii=False)
    eid = _pp_crear_evento(evento_tipo, evento_desc, gan_json)

    # Oro y eternium automáticos configurados para este tipo de evento
    oro_auto      = _pp_oro_ev(evento_tipo)
    eternium_auto = _pp_eternium_ev(evento_tipo)

    def _linea_base(g: dict) -> str:
        partes = []
        if g.get("xp"):    partes.append(f"✨ +{g['xp']:,} XP")
        if g.get("oro"):   partes.append(f"💰 +{g['oro']:,} Oro")
        if oro_auto > 0:   partes.append(f"💰 +{oro_auto:,} Oro extra")
        if eternium_auto > 0: partes.append(f"💎 +{eternium_auto} Eternium")
        return "  ".join(partes)

    if _pp_auto_activo_ev(evento_tipo):
        pool = _pp_pool()
        lineas_admin = []
        for g in ganadores:
            # Entregar oro/eternium automáticos
            _pp_entregar_economia(g["user_id"], oro_auto, eternium_auto, evento_desc)
            item = _pp_random_item(pool)
            base_str = _linea_base(g)
            if item:
                _pp_entregar_item_db(g["user_id"], item)
                lineas_admin.append(f"• {_e(g['nombre'])}: {_e(item['nombre'])} ({_e(item['tipo'])})"
                                    + (f" + 💰{oro_auto:,}" if oro_auto > 0 else "")
                                    + (f" + 💎{eternium_auto}" if eternium_auto > 0 else ""))
                msg_ganador = (
                    f"🏆 <b>¡Victoria!</b>\n"
                    f"📌 {_e(evento_desc)}\n\n"
                    f"<b>Recompensas recibidas:</b>\n"
                )
                if base_str:
                    msg_ganador += f"{base_str}\n"
                msg_ganador += (
                    f"🎁 <b>Premio especial: {_e(item['nombre'])}</b>\n"
                    f"   Tipo: {_e(item['tipo'])} · ★ Rareza {item.get('rareza', 1)}"
                    f" · Zona {_e(item.get('zona', '?'))}\n\n"
                    f"<i>El objeto ya está en tu inventario. ¡Úsalo bien!</i>"
                )
            else:
                lineas_admin.append(f"• {_e(g['nombre'])}: (sin ítem)"
                                    + (f" + 💰{oro_auto:,}" if oro_auto > 0 else "")
                                    + (f" + 💎{eternium_auto}" if eternium_auto > 0 else ""))
                msg_ganador = (
                    f"🏆 <b>¡Victoria!</b>\n"
                    f"📌 {_e(evento_desc)}\n\n"
                    + (f"<b>Ya recibiste:</b>\n{base_str}\n\n" if base_str else "")
                    + "<i>(No hay ítems disponibles con los filtros actuales.)</i>"
                )
            try:
                await bot.send_message(g["user_id"], msg_ganador, parse_mode="HTML")
            except Exception:
                pass
        _pp_marcar_estado(eid, "auto_entregado")
        resumen = "\n".join(lineas_admin) if lineas_admin else "<i>Sin ítems con los filtros actuales.</i>"
        await _pp_send_admin(bot,
            f"🤖 <b>Auto-Premio [{_PP_NOMBRE_EVENTO.get(evento_tipo, evento_tipo)}] — #{eid}</b>\n"
            f"📌 {_e(evento_desc)}\n\n"
            f"<b>Entregado a {len(ganadores)} ganadores:</b>\n{resumen}")
    else:
        nombres = ", ".join(_e(g["nombre"]) for g in ganadores[:5])
        extra = f" (+{len(ganadores)-5} más)" if len(ganadores) > 5 else ""
        auto_ev = "🟢 Auto" if _pp_auto_activo() else "🔴 Manual"
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("🎁 Abrir Panel de Premios", callback_data=f"pp_ev_{eid}")
        ]])
        await _pp_send_admin(bot,
            f"🏆 <b>¡Victoria!</b> [{_PP_NOMBRE_EVENTO.get(evento_tipo, evento_tipo)}] — #{eid}\n"
            f"📌 <b>{_e(evento_desc)}</b>\n\n"
            f"👥 Ganadores ({len(ganadores)}): {nombres}{extra}\n"
            f"💰 Oro auto/ganador: {oro_auto:,} | 💎 Eternium auto: {eternium_auto}\n\n"
            f"<i>Pulsa para otorgar premios especiales.</i>",
            reply_markup=kb)
        # Avisar a cada ganador que sus premios especiales están siendo calculados
        for g in ganadores:
            base_str = _linea_base(g)
            # Entregar oro/eternium automáticos aunque el ítem sea manual
            _pp_entregar_economia(g["user_id"], oro_auto, eternium_auto, evento_desc)
            msg_ganador = f"🏆 <b>¡Victoria!</b>\n📌 {_e(evento_desc)}\n\n"
            if base_str:
                msg_ganador += f"<b>Ya recibiste:</b>\n{base_str}\n\n"
            msg_ganador += (
                f"⏳ <b>El admin está calculando tu premio especial.</b>\n"
                f"El ítem será otorgado en breve."
            )
            try:
                await bot.send_message(g["user_id"], msg_ganador, parse_mode="HTML")
            except Exception:
                pass

def _pp_texto_lista() -> str:
    eventos = _pp_obtener_pendientes()
    auto_txt = "🟢 ACTIVO" if _pp_auto_activo() else "🔴 INACTIVO"
    txt = f"🎁 <b>PANEL DE PREMIOS</b>\n⚙️ Auto-Premio: {auto_txt}\n\n"
    if not eventos:
        txt += "<i>No hay eventos pendientes de premios.</i>"
    else:
        for ev in eventos:
            gans = json.loads(ev["ganadores_json"])
            txt += (f"<b>#{ev['id']}</b> ┆ {_e(ev['evento_tipo'].upper())} ┆ "
                    f"{len(gans)} ganadores ┆ {ev['fecha'][:10]}\n"
                    f"  📌 {_e(ev['evento_desc'][:50])}\n\n")
    return txt

def _pp_kb_lista(eventos: List[Dict]) -> InlineKeyboardMarkup:
    rows = []
    for ev in eventos:
        gans = json.loads(ev["ganadores_json"])
        rows.append([InlineKeyboardButton(
            f"#{ev['id']} {ev['evento_tipo'].upper()} ({len(gans)}👥) {ev['fecha'][:10]}",
            callback_data=f"pp_ev_{ev['id']}"
        )])
    rows.append([
        InlineKeyboardButton("⚙️ Auto Global", callback_data="pp_at"),
        InlineKeyboardButton("🔧 Filtros Pool", callback_data="pp_fl"),
    ])
    rows.append([
        InlineKeyboardButton("🎛️ Config por Evento", callback_data="pp_cfg_ev"),
    ])
    rows.append([InlineKeyboardButton("🔄 Actualizar", callback_data="pp_lst")])
    return InlineKeyboardMarkup(rows)

def _pp_texto_cfg_eventos() -> str:
    bs = _pp_batch_size()
    global_txt = "🟢 ACTIVO" if _pp_auto_activo() else "🔴 INACTIVO"
    txt = (
        f"🎛️ <b>CONFIG POR TIPO DE EVENTO</b>\n"
        f"⚙️ Auto global: {global_txt}\n"
        f"📦 Tamaño de lote colectivo: <b>{bs}</b>\n\n"
    )
    for tipo in _PP_TIPOS_EVENTO:
        nombre = _PP_NOMBRE_EVENTO.get(tipo, tipo)
        auto_val = db_helper.obtener_config(f"auto_premios_{tipo}", "")
        if auto_val == "":
            auto_txt = "🔄 Global"
        elif auto_val == "1":
            auto_txt = "🟢 Auto"
        else:
            auto_txt = "🔴 Manual"
        oro = _pp_oro_ev(tipo)
        eth = _pp_eternium_ev(tipo)
        txt += (
            f"<b>{nombre}</b>: {auto_txt}\n"
            f"  💰 Oro/ganador: {oro:,}   💎 Eternium/ganador: {eth}\n\n"
        )
    return txt

def _pp_kb_cfg_eventos() -> InlineKeyboardMarkup:
    bs = _pp_batch_size()
    B = InlineKeyboardButton
    rows = []
    # Batch size
    rows.append([
        B(f"⬇️ Lote({bs})", callback_data="pp_bat_dn"),
        B(f"Tamaño lote: {bs}", callback_data="pp_nop"),
        B(f"⬆️ Lote({bs})", callback_data="pp_bat_up"),
    ])
    rows.append([B("━━━━━━━━━━━━━━━━━━", callback_data="pp_nop")])
    for tipo in _PP_TIPOS_EVENTO:
        nombre = _PP_NOMBRE_EVENTO.get(tipo, tipo)
        auto_val = db_helper.obtener_config(f"auto_premios_{tipo}", "")
        if auto_val == "": icono = "🔄"
        elif auto_val == "1": icono = "🟢"
        else: icono = "🔴"
        oro = _pp_oro_ev(tipo)
        eth = _pp_eternium_ev(tipo)
        rows.append([B(f"{icono} {nombre}", callback_data=f"pp_cev_at_{tipo}")])
        rows.append([
            B(f"⬇️💰{oro:,}", callback_data=f"pp_cev_odn_{tipo}"),
            B(f"💰 {oro:,}", callback_data="pp_nop"),
            B(f"💰{oro:,}⬆️", callback_data=f"pp_cev_oup_{tipo}"),
            B(f"⬇️💎{eth}", callback_data=f"pp_cev_edn_{tipo}"),
            B(f"💎{eth}⬆️", callback_data=f"pp_cev_eup_{tipo}"),
        ])
    rows.append([B("« Volver al panel", callback_data="pp_lst")])
    return InlineKeyboardMarkup(rows)

def _pp_texto_evento(ev: Dict) -> str:
    gans = json.loads(ev["ganadores_json"])
    names = "\n".join(
        f"  {i+1}. {_e(g['nombre'])} (score: {g.get('score',0):,})"
        for i, g in enumerate(gans)
    )
    return (
        f"🏆 <b>Evento #{ev['id']} — {_e(ev['evento_tipo'].upper())}</b>\n"
        f"📌 {_e(ev['evento_desc'])}\n"
        f"📅 {ev['fecha']}\n\n"
        f"👥 <b>Ganadores ({len(gans)}):</b>\n{names}\n\n"
        f"¿Cómo quieres otorgar los premios?"
    )

def _pp_kb_evento(eid: int) -> InlineKeyboardMarkup:
    bs = _pp_batch_size()
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👤 Individual",        callback_data=f"pp_ind_{eid}"),
         InlineKeyboardButton("👥 Colectivo todo",    callback_data=f"pp_col_{eid}")],
        [InlineKeyboardButton(f"📦 Lotes de {bs}",   callback_data=f"pp_bat_{eid}_0")],
        [InlineKeyboardButton("❌ Cancelar evento",   callback_data=f"pp_can_{eid}")],
        [InlineKeyboardButton("« Lista",              callback_data="pp_lst")],
    ])

def _pp_texto_individual(ev: Dict, idx: int, bd: dict) -> str:
    gans = json.loads(ev["ganadores_json"])
    g = gans[idx]
    eid = ev["id"]
    sel = bd.get(f"pp_sel_{eid}", {})
    item = sel.get(str(g["user_id"]))
    conf = bd.get(f"pp_conf_{eid}", set())
    oro_extra = bd.get(f"pp_ioro_{eid}", {}).get(str(g["user_id"]), 0)
    eth_extra  = bd.get(f"pp_ieth_{eid}", {}).get(str(g["user_id"]), 0)
    item_txt = (f"<b>{_e(item['nombre'])}</b> ({_e(item['tipo'])}, ★{item.get('rareza',1)}, zona {_e(item.get('zona','?'))})"
                if item else "<i>Sin asignar — pulsa Re-roll</i>")
    estado_txt = "✅ Confirmado" if str(g["user_id"]) in conf else "⬜ Pendiente"
    extra_txt = ""
    if oro_extra > 0 or eth_extra > 0:
        partes = []
        if oro_extra > 0: partes.append(f"💰 +{oro_extra:,} oro")
        if eth_extra > 0:  partes.append(f"💎 +{eth_extra} eternium")
        extra_txt = f"\n💵 Extra: {' · '.join(partes)}"
    return (
        f"👤 <b>Individual — Evento #{eid}</b>\n"
        f"Jugador {idx+1}/{len(gans)}: <b>{_e(g['nombre'])}</b> (ID: {g['user_id']})\n\n"
        f"🎁 Ítem: {item_txt}{extra_txt}\n"
        f"Estado: {estado_txt}"
    )

def _pp_kb_individual(ev: Dict, idx: int, bd: dict) -> InlineKeyboardMarkup:
    gans = json.loads(ev["ganadores_json"])
    eid = ev["id"]
    uid_str = str(gans[idx]["user_id"])
    oro_extra = bd.get(f"pp_ioro_{eid}", {}).get(uid_str, 0)
    eth_extra  = bd.get(f"pp_ieth_{eid}", {}).get(uid_str, 0)
    B = InlineKeyboardButton
    rows = [
        [B("🎲 Re-roll ítem",      callback_data=f"pp_inr_{eid}_{idx}"),
         B("✅ Confirmar este",    callback_data=f"pp_inc_{eid}_{idx}")],
        # Preset de oro
        [B("💰 +100",  callback_data=f"pp_og_{eid}_{idx}_100"),
         B("💰 +500",  callback_data=f"pp_og_{eid}_{idx}_500"),
         B("💰 +1000", callback_data=f"pp_og_{eid}_{idx}_1000"),
         B("💰 +5000", callback_data=f"pp_og_{eid}_{idx}_5000")],
        # Preset de eternium
        [B("💎 +10",  callback_data=f"pp_oe_{eid}_{idx}_10"),
         B("💎 +50",  callback_data=f"pp_oe_{eid}_{idx}_50"),
         B("💎 +100", callback_data=f"pp_oe_{eid}_{idx}_100"),
         B("💎 +500", callback_data=f"pp_oe_{eid}_{idx}_500")],
        # Reset oro/eternium extra
        [B(f"🔄 Reset extra ({oro_extra:,}💰 {eth_extra}💎)", callback_data=f"pp_ors_{eid}_{idx}")],
    ]
    nav = []
    if idx > 0:
        nav.append(B(f"◀ {gans[idx-1]['nombre'][:10]}", callback_data=f"pp_ipl_{eid}_{idx-1}"))
    if idx < len(gans) - 1:
        nav.append(B(f"{gans[idx+1]['nombre'][:10]} ▶", callback_data=f"pp_ipl_{eid}_{idx+1}"))
    if nav:
        rows.append(nav)
    rows.append([B("📦 Entregar TODOS confirmados", callback_data=f"pp_ica_{eid}")])
    rows.append([B("« Volver al evento", callback_data=f"pp_ev_{eid}")])
    return InlineKeyboardMarkup(rows)

def _pp_texto_lote(ev: Dict, bd: dict, page: int) -> str:
    """Texto para el modo colectivo por lotes de N jugadores."""
    gans = json.loads(ev["ganadores_json"])
    bs = _pp_batch_size()
    total = len(gans)
    total_pages = max(1, (total + bs - 1) // bs)
    page = max(0, min(page, total_pages - 1))
    inicio = page * bs
    fin    = min(inicio + bs, total)
    lote   = gans[inicio:fin]
    sel    = bd.get(f"pp_sel_{ev['id']}", {})
    txt = (
        f"📦 <b>Lotes — Evento #{ev['id']}</b>\n"
        f"Página {page+1}/{total_pages} · Jugadores {inicio+1}–{fin} de {total}\n\n"
    )
    for g in lote:
        item = sel.get(str(g["user_id"]))
        item_txt = f"{_e(item['nombre'])} (★{item.get('rareza',1)})" if item else "— sin roll"
        txt += f"• <b>{_e(g['nombre'])}</b>: {item_txt}\n"
    return txt

def _pp_kb_lote(ev: Dict, bd: dict, page: int) -> InlineKeyboardMarkup:
    gans = json.loads(ev["ganadores_json"])
    bs = _pp_batch_size()
    eid = ev["id"]
    total_pages = max(1, (len(gans) + bs - 1) // bs)
    page = max(0, min(page, total_pages - 1))
    B = InlineKeyboardButton
    rows = [
        [B("🎲 Re-roll este lote", callback_data=f"pp_btr_{eid}_{page}"),
         B("✅ Entregar este lote", callback_data=f"pp_btc_{eid}_{page}")],
    ]
    nav = []
    if page > 0:
        nav.append(B(f"◀ Pág {page}", callback_data=f"pp_bat_{eid}_{page-1}"))
    if page < total_pages - 1:
        nav.append(B(f"Pág {page+2} ▶", callback_data=f"pp_bat_{eid}_{page+1}"))
    if nav:
        rows.append(nav)
    rows.append([B("« Volver al evento", callback_data=f"pp_ev_{eid}")])
    return InlineKeyboardMarkup(rows)

def _pp_texto_colectivo(ev: Dict, bd: dict) -> str:
    gans = json.loads(ev["ganadores_json"])
    sel = bd.get(f"pp_sel_{ev['id']}", {})
    txt = f"👥 <b>Colectivo — Evento #{ev['id']}</b>\n\n"
    for g in gans:
        item = sel.get(str(g["user_id"]))
        item_txt = f"{_e(item['nombre'])} ({_e(item['tipo'])}, ★{item.get('rareza',1)})" if item else "—"
        txt += f"• <b>{_e(g['nombre'])}</b>: {item_txt}\n"
    return txt

def _pp_kb_colectivo(eid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎲 Re-roll masivo",  callback_data=f"pp_cnr_{eid}"),
         InlineKeyboardButton("✅ Entregar TODO",   callback_data=f"pp_cco_{eid}")],
        [InlineKeyboardButton("« Volver al evento", callback_data=f"pp_ev_{eid}")],
    ])

def _pp_texto_filtros() -> str:
    tipos = _pp_filtro("tipos", "arma,armadura,material,montura")
    zonas = _pp_filtro("zonas", "azul,amarilla,roja,negra")
    rmin  = _pp_filtro("rmin", "1")
    rmax  = _pp_filtro("rmax", "12")
    nmin  = _pp_filtro("nmin", "1")
    nmax  = _pp_filtro("nmax", "100")
    clases = _pp_filtro("clases", "")
    pool_size = len(_pp_pool())
    return (
        "🔧 <b>FILTROS DE PREMIOS</b>\n\n"
        f"📦 Tipos activos: <code>{_e(tipos)}</code>\n"
        f"🗺️ Zonas activas: <code>{_e(zonas)}</code>\n"
        f"⭐ Rareza: {rmin}–{rmax} (1=común, 12=único)\n"
        f"🎚️ Nivel requerido: {nmin}–{nmax}\n"
        f"🧙 Clases: {_e(clases) if clases else 'todas'}\n\n"
        f"🎲 <b>Pool actual: {pool_size} ítems disponibles</b>\n\n"
        "<i>Pulsa un tipo o zona para activar/desactivar.</i>"
    )

def _pp_kb_filtros() -> InlineKeyboardMarkup:
    tipos_on = set(_pp_filtro("tipos", "arma,armadura,material,montura").split(","))
    zonas_on = set(_pp_filtro("zonas", "azul,amarilla,roja,negra").split(","))
    rmin = int(_pp_filtro("rmin", "1"))
    rmax = int(_pp_filtro("rmax", "12"))
    nmin = int(_pp_filtro("nmin", "1"))
    nmax = int(_pp_filtro("nmax", "100"))
    B = InlineKeyboardButton
    rows = [
        [B(f"{'✅' if t in tipos_on else '❌'} {t}", callback_data=f"pf_t_{t}") for t in _PP_TIPOS],
        [B(f"{'✅' if z in zonas_on else '❌'} {z}", callback_data=f"pf_z_{z}") for z in _PP_ZONAS],
        [B(f"⬇️ ★min({rmin})", callback_data="pf_rmn_dn"),
         B(f"⬆️ ★min({rmin})", callback_data="pf_rmn_up"),
         B(f"⬇️ ★max({rmax})", callback_data="pf_rmx_dn"),
         B(f"⬆️ ★max({rmax})", callback_data="pf_rmx_up")],
        [B(f"⬇️ Nv.min({nmin})", callback_data="pf_nmn_dn"),
         B(f"⬆️ Nv.min({nmin})", callback_data="pf_nmn_up"),
         B(f"⬇️ Nv.max({nmax})", callback_data="pf_nmx_dn"),
         B(f"⬆️ Nv.max({nmax})", callback_data="pf_nmx_up")],
        [B("♻️ Reset filtros", callback_data="pf_rst")],
        [B("« Volver al panel", callback_data="pp_lst")],
    ]
    return InlineKeyboardMarkup(rows)

async def cmd_panel_premios(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _verificar_cmd(update.effective_user.id, "objetos"):
        await update.effective_message.reply_text("❌ Sin permiso.")
        return
    eventos = _pp_obtener_pendientes()
    await update.effective_message.reply_text(
        _pp_texto_lista(), parse_mode="HTML", reply_markup=_pp_kb_lista(eventos)
    )

async def cmd_auto_premios(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _verificar_cmd(update.effective_user.id, "objetos"):
        await update.effective_message.reply_text("❌ Sin permiso.")
        return
    nuevo = "0" if _pp_auto_activo() else "1"
    db_helper.establecer_config("auto_premios_activo", nuevo)
    estado = "🟢 ACTIVADO" if nuevo == "1" else "🔴 DESACTIVADO"
    await update.effective_message.reply_text(
        f"⚙️ Auto-Premio: <b>{_e(estado)}</b>\n\n"
        f"{'Premios se otorgarán automáticamente según los filtros configurados.' if nuevo == '1' else 'Recibirás una notificación para otorgar premios manualmente cuando haya victorias.'}",
        parse_mode="HTML"
    )

async def cmd_filtros_premios(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _verificar_cmd(update.effective_user.id, "objetos"):
        await update.effective_message.reply_text("❌ Sin permiso.")
        return
    await update.effective_message.reply_text(
        _pp_texto_filtros(), parse_mode="HTML", reply_markup=_pp_kb_filtros()
    )

async def cb_panel_premios(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not _verificar_cmd(update.effective_user.id, "objetos"):
        await query.edit_message_text("❌ Sin permiso.")
        return
    data = query.data
    bd = context.bot_data
    parts = data.split("_")

    async def _edit(txt, kb=None):
        try:
            await query.edit_message_text(txt, parse_mode="HTML", reply_markup=kb)
        except Exception as _ex:
            try:
                await query.edit_message_text(f"⚠️ Error mostrando panel: {_ex}")
            except Exception:
                pass

    if data == "pp_lst":
        eventos = _pp_obtener_pendientes()
        await _edit(_pp_texto_lista(), _pp_kb_lista(eventos))
        return

    if data == "pp_at":
        nuevo = "0" if _pp_auto_activo() else "1"
        db_helper.establecer_config("auto_premios_activo", nuevo)
        eventos = _pp_obtener_pendientes()
        await _edit(_pp_texto_lista(), _pp_kb_lista(eventos))
        return

    if data == "pp_fl":
        await _edit(_pp_texto_filtros(), _pp_kb_filtros())
        return

    if data.startswith("pp_ev_"):
        eid = int(parts[2])
        ev = _pp_obtener_evento(eid)
        if not ev:
            await _edit("❌ Evento no encontrado o ya entregado\\.")
            return
        await _edit(_pp_texto_evento(ev), _pp_kb_evento(eid))
        return

    if data.startswith("pp_can_"):
        eid = int(parts[2])
        _pp_marcar_estado(eid, "cancelado")
        bd.pop(f"pp_sel_{eid}", None)
        bd.pop(f"pp_conf_{eid}", None)
        await _edit(f"❌ Evento \\#{eid} cancelado\\. No se entregaron premios\\.")
        return

    if data.startswith("pp_ind_"):
        eid = int(parts[2])
        ev = _pp_obtener_evento(eid)
        if not ev: return
        if f"pp_sel_{eid}" not in bd:
            _pp_roll_all(ev, bd)
        if f"pp_conf_{eid}" not in bd:
            bd[f"pp_conf_{eid}"] = set()
        await _edit(_pp_texto_individual(ev, 0, bd), _pp_kb_individual(ev, 0, bd))
        return

    if data.startswith("pp_ipl_"):
        eid = int(parts[2]); idx = int(parts[3])
        ev = _pp_obtener_evento(eid)
        if not ev: return
        await _edit(_pp_texto_individual(ev, idx, bd), _pp_kb_individual(ev, idx, bd))
        return

    if data.startswith("pp_inr_"):
        eid = int(parts[2]); idx = int(parts[3])
        ev = _pp_obtener_evento(eid)
        if not ev: return
        gans = json.loads(ev["ganadores_json"])
        g = gans[idx]
        item = _pp_random_item()
        if item:
            sel = bd.get(f"pp_sel_{eid}", {})
            sel[str(g["user_id"])] = item
            bd[f"pp_sel_{eid}"] = sel
        await _edit(_pp_texto_individual(ev, idx, bd), _pp_kb_individual(ev, idx, bd))
        return

    if data.startswith("pp_inc_"):
        eid = int(parts[2]); idx = int(parts[3])
        ev = _pp_obtener_evento(eid)
        if not ev: return
        gans = json.loads(ev["ganadores_json"])
        g = gans[idx]
        uid_str = str(g["user_id"])
        sel = bd.get(f"pp_sel_{eid}", {})
        if uid_str not in sel:
            await query.answer("⚠️ Haz re-roll primero para asignar un ítem.", show_alert=True)
            return
        conf = bd.get(f"pp_conf_{eid}", set())
        conf.add(uid_str)
        bd[f"pp_conf_{eid}"] = conf
        await query.answer(f"✅ Confirmado para {g['nombre']}.", show_alert=False)
        await _edit(_pp_texto_individual(ev, idx, bd), _pp_kb_individual(ev, idx, bd))
        return

    if data.startswith("pp_ica_"):
        eid = int(parts[2])
        ev = _pp_obtener_evento(eid)
        if not ev: return
        gans = json.loads(ev["ganadores_json"])
        sel  = bd.get(f"pp_sel_{eid}", {})
        conf = bd.get(f"pp_conf_{eid}", set())
        oro_dic = bd.get(f"pp_ioro_{eid}", {})
        eth_dic = bd.get(f"pp_ieth_{eid}", {})
        if not sel and not oro_dic and not eth_dic:
            await query.answer("⚠️ No hay premios asignados.", show_alert=True)
            return
        lineas = []
        for g in gans:
            uid_str = str(g["user_id"])
            item    = sel.get(uid_str)
            oro_ex  = oro_dic.get(uid_str, 0)
            eth_ex  = eth_dic.get(uid_str, 0)
            # Solo confirmar si está marcado o si tiene oro/eternium extra
            if uid_str not in conf and not (oro_ex > 0 or eth_ex > 0):
                continue
            extras_str = ""
            if oro_ex > 0 or eth_ex > 0:
                _pp_entregar_economia(g["user_id"], oro_ex, eth_ex, ev["evento_desc"])
                partes = []
                if oro_ex > 0: partes.append(f"💰+{oro_ex:,}")
                if eth_ex > 0: partes.append(f"💎+{eth_ex}")
                extras_str = " " + " ".join(partes)
            if item:
                _pp_entregar_item_db(g["user_id"], item)
                lineas.append(f"• {_e(g['nombre'])}: {_e(item['nombre'])}{extras_str}")
                msg_txt = (
                    f"🎁 <b>¡Premio especial!</b>\n"
                    f"🏆 <b>{_e(item['nombre'])}</b> ({_e(item['tipo'])}, ★{item.get('rareza',1)})"
                    + (f"\n{extras_str}" if extras_str else "") +
                    f"\n\n<i>¡Disfrútalo!</i>"
                )
            else:
                lineas.append(f"• {_e(g['nombre'])}: (sin ítem){extras_str}")
                msg_txt = f"🎁 <b>Premio recibido</b>: {extras_str}" if extras_str else None
            if msg_txt:
                try:
                    await context.bot.send_message(g["user_id"], msg_txt, parse_mode="HTML")
                except Exception:
                    pass
        _pp_marcar_estado(eid, "entregado")
        bd.pop(f"pp_sel_{eid}", None)
        bd.pop(f"pp_conf_{eid}", None)
        bd.pop(f"pp_ioro_{eid}", None)
        bd.pop(f"pp_ieth_{eid}", None)
        resumen = "\n".join(lineas) if lineas else "Ningún jugador tenía premio confirmado."
        await _edit(f"✅ <b>Premios entregados #{eid}</b>\n\n{resumen}")
        return

    if data.startswith("pp_col_"):
        eid = int(parts[2])
        ev = _pp_obtener_evento(eid)
        if not ev: return
        _pp_roll_all(ev, bd)
        await _edit(_pp_texto_colectivo(ev, bd), _pp_kb_colectivo(eid))
        return

    if data.startswith("pp_cnr_"):
        eid = int(parts[2])
        ev = _pp_obtener_evento(eid)
        if not ev: return
        _pp_roll_all(ev, bd)
        await _edit(_pp_texto_colectivo(ev, bd), _pp_kb_colectivo(eid))
        return

    if data.startswith("pp_cco_"):
        eid = int(parts[2])
        ev = _pp_obtener_evento(eid)
        if not ev: return
        gans = json.loads(ev["ganadores_json"])
        sel = bd.get(f"pp_sel_{eid}", {})
        if not sel:
            await query.answer("⚠️ Haz re-roll primero.", show_alert=True)
            return
        lineas = []
        for g in gans:
            item = sel.get(str(g["user_id"]))
            if item:
                _pp_entregar_item_db(g["user_id"], item)
                lineas.append(f"• {_e(g['nombre'])}: {_e(item['nombre'])}")
                try:
                    await context.bot.send_message(
                        g["user_id"],
                        f"🎁 <b>¡Premio especial!</b> Recibiste <b>{_e(item['nombre'])}</b> ({_e(item['tipo'])}, ★{item.get('rareza',1)}). ¡Disfrútalo!",
                        parse_mode="HTML"
                    )
                except Exception:
                    pass
        _pp_marcar_estado(eid, "entregado")
        bd.pop(f"pp_sel_{eid}", None)
        resumen = "\n".join(lineas) if lineas else "Sin ítems disponibles con los filtros actuales."
        await _edit(f"✅ <b>Premios colectivos entregados #{eid}</b>\n\n{resumen}")
        return

    # ── No-op (botones decorativos/etiquetas) ──────────────────────────────
    if data == "pp_nop":
        await query.answer()
        return

    # ── Panel de config por tipo de evento ─────────────────────────────────
    if data == "pp_cfg_ev":
        await _edit(_pp_texto_cfg_eventos(), _pp_kb_cfg_eventos())
        return

    if data in ("pp_bat_up", "pp_bat_dn"):
        bs = _pp_batch_size()
        delta = 1 if data == "pp_bat_up" else -1
        _pp_set_batch_size(bs + delta)
        await _edit(_pp_texto_cfg_eventos(), _pp_kb_cfg_eventos())
        return

    if data.startswith("pp_cev_at_"):
        tipo = data[len("pp_cev_at_"):]
        if tipo in _PP_TIPOS_EVENTO:
            val_actual = db_helper.obtener_config(f"auto_premios_{tipo}", "")
            # Ciclo: global → auto → manual → global
            if val_actual == "":   _pp_set_auto_ev(tipo, True)
            elif val_actual == "1": _pp_set_auto_ev(tipo, False)
            else:
                db_helper.establecer_config(f"auto_premios_{tipo}", "")  # volver a global
            await _edit(_pp_texto_cfg_eventos(), _pp_kb_cfg_eventos())
        return

    if data.startswith("pp_cev_oup_") or data.startswith("pp_cev_odn_"):
        up = data.startswith("pp_cev_oup_")
        tipo = data[len("pp_cev_oup_"):] if up else data[len("pp_cev_odn_"):]
        if tipo in _PP_TIPOS_EVENTO:
            actual = _pp_oro_ev(tipo)
            pasos  = [0, 100, 250, 500, 1000, 2500, 5000, 10000]
            idx_a  = next((i for i, v in enumerate(pasos) if v >= actual), len(pasos)-1)
            nuevo  = pasos[min(idx_a+1, len(pasos)-1)] if up else pasos[max(idx_a-1, 0)]
            _pp_set_oro_ev(tipo, nuevo)
            await _edit(_pp_texto_cfg_eventos(), _pp_kb_cfg_eventos())
        return

    if data.startswith("pp_cev_eup_") or data.startswith("pp_cev_edn_"):
        up = data.startswith("pp_cev_eup_")
        tipo = data[len("pp_cev_eup_"):] if up else data[len("pp_cev_edn_"):]
        if tipo in _PP_TIPOS_EVENTO:
            actual = _pp_eternium_ev(tipo)
            pasos  = [0, 10, 25, 50, 100, 250, 500, 1000]
            idx_a  = next((i for i, v in enumerate(pasos) if v >= actual), len(pasos)-1)
            nuevo  = pasos[min(idx_a+1, len(pasos)-1)] if up else pasos[max(idx_a-1, 0)]
            _pp_set_eternium_ev(tipo, nuevo)
            await _edit(_pp_texto_cfg_eventos(), _pp_kb_cfg_eventos())
        return

    # ── Modo por lotes ─────────────────────────────────────────────────────
    if data.startswith("pp_bat_") and len(parts) == 4:
        # pp_bat_{eid}_{page}
        try:
            eid = int(parts[2]); page = int(parts[3])
        except (ValueError, IndexError):
            return
        ev = _pp_obtener_evento(eid)
        if not ev: return
        if f"pp_sel_{eid}" not in bd:
            _pp_roll_all(ev, bd)
        await _edit(_pp_texto_lote(ev, bd, page), _pp_kb_lote(ev, bd, page))
        return

    if data.startswith("pp_btr_"):
        # Re-roll del lote actual
        try: eid = int(parts[2]); page = int(parts[3])
        except (ValueError, IndexError): return
        ev = _pp_obtener_evento(eid)
        if not ev: return
        gans = json.loads(ev["ganadores_json"])
        bs = _pp_batch_size()
        inicio = page * bs
        fin    = min(inicio + bs, len(gans))
        pool   = _pp_pool()
        sel    = bd.get(f"pp_sel_{eid}", {})
        for g in gans[inicio:fin]:
            item = _pp_random_item(pool)
            if item:
                sel[str(g["user_id"])] = item
        bd[f"pp_sel_{eid}"] = sel
        await _edit(_pp_texto_lote(ev, bd, page), _pp_kb_lote(ev, bd, page))
        return

    if data.startswith("pp_btc_"):
        # Entregar premios del lote actual
        try: eid = int(parts[2]); page = int(parts[3])
        except (ValueError, IndexError): return
        ev = _pp_obtener_evento(eid)
        if not ev: return
        gans = json.loads(ev["ganadores_json"])
        bs = _pp_batch_size()
        inicio = page * bs
        fin    = min(inicio + bs, len(gans))
        sel    = bd.get(f"pp_sel_{eid}", {})
        if not sel:
            await query.answer("⚠️ Haz re-roll primero.", show_alert=True)
            return
        lineas = []
        for g in gans[inicio:fin]:
            item = sel.get(str(g["user_id"]))
            if item:
                _pp_entregar_item_db(g["user_id"], item)
                lineas.append(f"• {_e(g['nombre'])}: {_e(item['nombre'])}")
                sel.pop(str(g["user_id"]), None)
                try:
                    await context.bot.send_message(
                        g["user_id"],
                        f"🎁 <b>¡Premio especial!</b> Recibiste <b>{_e(item['nombre'])}</b> ({_e(item['tipo'])}, ★{item.get('rareza',1)}). ¡Disfrútalo!",
                        parse_mode="HTML"
                    )
                except Exception: pass
        bd[f"pp_sel_{eid}"] = sel
        # Si ya no queda ninguno pendiente, marcar como entregado
        if not sel:
            _pp_marcar_estado(eid, "entregado")
            bd.pop(f"pp_sel_{eid}", None)
            resumen = "\n".join(lineas) if lineas else "Sin ítems asignados."
            await _edit(f"✅ <b>Último lote entregado — Evento #{eid} COMPLETADO</b>\n\n{resumen}")
        else:
            resumen = "\n".join(lineas) if lineas else "Sin ítems asignados en este lote."
            await query.answer(f"✅ {len(lineas)} premios del lote entregados.", show_alert=False)
            total_pages = max(1, (len(gans) + bs - 1) // bs)
            next_page   = min(page + 1, total_pages - 1)
            await _edit(_pp_texto_lote(ev, bd, next_page), _pp_kb_lote(ev, bd, next_page))
        return

    # ── Oro extra individual ────────────────────────────────────────────────
    if data.startswith("pp_og_"):
        # pp_og_{eid}_{idx}_{amt}
        try: eid = int(parts[2]); idx = int(parts[3]); amt = int(parts[4])
        except (ValueError, IndexError): return
        ev = _pp_obtener_evento(eid)
        if not ev: return
        gans = json.loads(ev["ganadores_json"])
        if not (0 <= idx < len(gans)): return
        uid_str = str(gans[idx]["user_id"])
        dic = bd.get(f"pp_ioro_{eid}", {})
        dic[uid_str] = dic.get(uid_str, 0) + amt
        bd[f"pp_ioro_{eid}"] = dic
        await query.answer(f"💰 +{amt:,} oro añadido (total: {dic[uid_str]:,})", show_alert=False)
        await _edit(_pp_texto_individual(ev, idx, bd), _pp_kb_individual(ev, idx, bd))
        return

    # ── Eternium extra individual ───────────────────────────────────────────
    if data.startswith("pp_oe_"):
        # pp_oe_{eid}_{idx}_{amt}
        try: eid = int(parts[2]); idx = int(parts[3]); amt = int(parts[4])
        except (ValueError, IndexError): return
        ev = _pp_obtener_evento(eid)
        if not ev: return
        gans = json.loads(ev["ganadores_json"])
        if not (0 <= idx < len(gans)): return
        uid_str = str(gans[idx]["user_id"])
        dic = bd.get(f"pp_ieth_{eid}", {})
        dic[uid_str] = dic.get(uid_str, 0) + amt
        bd[f"pp_ieth_{eid}"] = dic
        await query.answer(f"💎 +{amt} eternium añadido (total: {dic[uid_str]})", show_alert=False)
        await _edit(_pp_texto_individual(ev, idx, bd), _pp_kb_individual(ev, idx, bd))
        return

    # ── Reset extra oro/eternium individual ────────────────────────────────
    if data.startswith("pp_ors_"):
        try: eid = int(parts[2]); idx = int(parts[3])
        except (ValueError, IndexError): return
        ev = _pp_obtener_evento(eid)
        if not ev: return
        gans = json.loads(ev["ganadores_json"])
        if not (0 <= idx < len(gans)): return
        uid_str = str(gans[idx]["user_id"])
        bd.get(f"pp_ioro_{eid}", {}).pop(uid_str, None)
        bd.get(f"pp_ieth_{eid}", {}).pop(uid_str, None)
        await query.answer("🔄 Extra de oro/eternium reseteado.", show_alert=False)
        await _edit(_pp_texto_individual(ev, idx, bd), _pp_kb_individual(ev, idx, bd))
        return

async def cb_filtros_premios(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not _verificar_cmd(update.effective_user.id, "objetos"):
        await query.edit_message_text("❌ Sin permiso.")
        return
    data = query.data

    if data == "pf_rst":
        for k, v in [("tipos","arma,armadura,material,montura"), ("zonas","azul,amarilla,roja,negra"),
                     ("rmin","1"), ("rmax","12"), ("nmin","1"), ("nmax","100"), ("clases","")]:
            _pp_set_filtro(k, v)
    elif data.startswith("pf_t_"):
        tipo = data[5:]
        tipos = set(_pp_filtro("tipos", "arma,armadura,material,montura").split(","))
        if tipo in tipos: tipos.discard(tipo)
        else: tipos.add(tipo)
        _pp_set_filtro("tipos", ",".join(sorted(tipos)))
    elif data.startswith("pf_z_"):
        zona = data[5:]
        zonas = set(_pp_filtro("zonas", "azul,amarilla,roja,negra").split(","))
        if zona in zonas: zonas.discard(zona)
        else: zonas.add(zona)
        _pp_set_filtro("zonas", ",".join(sorted(zonas)))
    elif data in ("pf_rmn_up","pf_rmn_dn","pf_rmx_up","pf_rmx_dn"):
        rmin = int(_pp_filtro("rmin", "1")); rmax = int(_pp_filtro("rmax", "12"))
        if data == "pf_rmn_up": rmin = min(rmin+1, rmax)
        elif data == "pf_rmn_dn": rmin = max(1, rmin-1)
        elif data == "pf_rmx_up": rmax = min(12, rmax+1)
        elif data == "pf_rmx_dn": rmax = max(rmin, rmax-1)
        _pp_set_filtro("rmin", str(rmin)); _pp_set_filtro("rmax", str(rmax))
    elif data in ("pf_nmn_up","pf_nmn_dn","pf_nmx_up","pf_nmx_dn"):
        nmin = int(_pp_filtro("nmin", "1")); nmax = int(_pp_filtro("nmax", "100"))
        if data == "pf_nmn_up": nmin = min(nmin+10, nmax)
        elif data == "pf_nmn_dn": nmin = max(1, nmin-10)
        elif data == "pf_nmx_up": nmax = min(100, nmax+10)
        elif data == "pf_nmx_dn": nmax = max(nmin, nmax-10)
        _pp_set_filtro("nmin", str(nmin)); _pp_set_filtro("nmax", str(nmax))
    try:
        await query.edit_message_text(_pp_texto_filtros(), parse_mode="HTML", reply_markup=_pp_kb_filtros())
    except Exception as _e:
        if "not modified" not in str(_e).lower():
            await query.message.reply_text(f"⚠️ Error al actualizar filtros: {_e}")

# ==================== REGISTRO DE HANDLERS ====================


# ==================== LIMPIAR GUERRAS PEGADAS ====================
async def cmd_guerra_limpiar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/guerra_limpiar — Fuerza el cierre de cualquier guerra de facciones o gremios que haya quedado bloqueada."""
    if not _verificar_cmd(update.effective_user.id, "eventos"):
        await update.effective_message.reply_text("❌ Sin permiso.")
        return
    import sqlite3 as _sql
    conn = _sql.connect(db_helper.DB_PATH)
    c = conn.cursor()
    # Guerras de facciones activas
    c.execute("SELECT id FROM guerras_facciones WHERE estado='activa'")
    gf_rows = c.fetchall()
    c.executemany("UPDATE guerras_facciones SET estado='finalizada' WHERE id=?", gf_rows)
    # Guerras de gremios activas
    try:
        c.execute("SELECT id FROM guerras_gremios WHERE estado='activa'")
        gg_rows = c.fetchall()
        c.executemany("UPDATE guerras_gremios SET estado='finalizada' WHERE id=?", gg_rows)
    except Exception:
        gg_rows = []
    conn.commit()
    conn.close()
    total_gf = len(gf_rows)
    total_gg = len(gg_rows)
    if total_gf == 0 and total_gg == 0:
        await update.effective_message.reply_text(
            "✅ No había ninguna guerra bloqueada en la base de datos.\n"
            "Todos los estados de guerra están en orden."
        )
    else:
        lineas = []
        if total_gf: lineas.append(f"⚔️ {total_gf} guerra(s) de facciones cerradas")
        if total_gg: lineas.append(f"🏰 {total_gg} guerra(s) de gremios cerradas")
        await update.effective_message.reply_text(
            f"🔧 <b>Guerras bloqueadas limpiadas:</b>\n" + "\n".join(lineas) +
            "\n\n<i>Los jugadores ya pueden viajar y usar el menú normal.</i>",
            parse_mode="HTML"
        )

# ==================== CONTROL DE FACCIONES ====================
async def cmd_faccion_libre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Activa la elección libre de facción al registrarse."""
    if not verificar_superadmin(update.effective_user.id):
        await update.effective_message.reply_text("❌ Solo el superadmin puede hacer esto.")
        return
    db_helper.establecer_config("faccion_libre", "1")
    conteo = db_helper.contar_jugadores_por_faccion()
    conteo_txt = " | ".join(f"{f}: {c}" for f, c in conteo.items())
    await update.effective_message.reply_text(
        "✅ *Elección de facción ACTIVADA.*\n\n"
        "Ahora los nuevos jugadores podrán elegir a qué facción se unen.\n\n"
        f"📊 Reparto actual: {conteo_txt}",
        parse_mode="Markdown"
    )

async def cmd_faccion_auto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Desactiva la elección libre: los nuevos jugadores van a la facción con menos miembros."""
    if not verificar_superadmin(update.effective_user.id):
        await update.effective_message.reply_text("❌ Solo el superadmin puede hacer esto.")
        return
    db_helper.establecer_config("faccion_libre", "0")
    conteo = db_helper.contar_jugadores_por_faccion()
    conteo_txt = " | ".join(f"{f}: {c}" for f, c in conteo.items())
    menos = db_helper.obtener_faccion_menos_poblada()
    await update.effective_message.reply_text(
        "🔄 *Asignación automática de facción ACTIVADA.*\n\n"
        "Los nuevos jugadores se unirán automáticamente a la facción con menos miembros.\n"
        f"Próximo jugador → *{menos}*\n\n"
        f"📊 Reparto actual: {conteo_txt}",
        parse_mode="Markdown"
    )

# ==================== PANEL ADMIN ====================

PANEL_CATEGORIAS = {
    "comunicacion": {
        "emoji": "📢", "titulo": "Comunicación", "nivel": 1,
        "comandos": [
            ("/broadcast_activos <mensaje>", "📡 Anuncio solo a jugadores activos en los últimos 10 min"),
            ("/broadcast_todos <mensaje>",   "📢 Anuncio a TODOS los jugadores registrados"),
        ]
    },
    "simulaciones": {
        "emoji": "🎮", "titulo": "Simulaciones", "nivel": 99,
        "comandos": [
            ("/simulaciones", "🎮 Panel interactivo para simular PvP, jefes, guerras, umbral y detectar bugs"),
        ]
    },
    "superadmin": {
        "emoji": "👑", "titulo": "Superadmin Exclusivo", "nivel": 99,
        "comandos": [
            ("/superadmin_mi_id", "Ver tu ID de Telegram"),
            ("/superadmin_crear_admin <user_id>", "Crear admin con panel de permisos granular"),
            ("/superadmin_editar_admin <user_id>", "Editar los permisos de un admin existente"),
            ("/superadmin_quitar_admin <user_id>", "Revocar el rango de admin y todos sus permisos"),
            ("/superadmin_lista_admins", "Ver todos los admins con sus categorías y botones de edición"),
            ("/superadmin_permisos_cmd <user_id>", "Asignar comandos admin individuales a un admin"),
            ("/broadcast_activos <msg>", "📡 Envía un mensaje solo a jugadores activos en los últimos 10 min — no bloquea el bot"),
            ("/broadcast_todos <msg>",   "📢 Envía un mensaje a TODOS los jugadores registrados — no bloquea el bot"),
            ("/reporte <mensaje>",       "📩 Enviar un reporte de error/bug al agente IA para que lo revise"),
            ("/reportes_ver",            "📋 Ver los últimos 10 reportes enviados al agente"),
        ]
    },
    "dios": {
        "emoji": "⚡", "titulo": "Modo Dios", "nivel": 2,
        "comandos": [
            ("/dios_activar", "Activar modo dios — stats infinitos e inmunidad total"),
            ("/dios_desactivar", "Volver a stats y comportamiento normales"),
            ("/dios_subir_nivel", "Subir tu nivel al instante"),
            ("/dios_max_stats", "Maximizar todos tus atributos (HP, ATK, DEF…)"),
            ("/dios_recolectar", "Recolectar materiales sin restricciones de zona o stamina"),
        ]
    },
    "membresia": {
        "emoji": "🎫", "titulo": "Membresías y Cofre", "nivel": 1,
        "comandos": [
            ("/membresia_admin", "🎫 Panel interactivo de gestión de membresías (precios, duración, activar/desactivar)"),
            ("/dar_membresia <user_id> <tipo> <dias>", "Otorgar membresía a un jugador. Tipos: plantillas, completa"),
        ]
    },
    "monedas": {
        "emoji": "💰", "titulo": "Monedas", "nivel": 1,
        "comandos": [
            ("/dar_oro <user_id> <cantidad>", "Dar oro a un jugador"),
            ("/quitar_oro <user_id> <cantidad>", "Quitar oro a un jugador"),
            ("/dar_eternium <user_id> <cantidad>", "Dar eternium a un jugador"),
            ("/quitar_eternium <user_id> <cantidad>", "Quitar eternium a un jugador"),
            ("/dar_creditos <user_id> <cantidad>", "Dar créditos del vacío"),
            ("/quitar_creditos <user_id> <cantidad>", "Quitar créditos del vacío"),
            ("/dar_experiencia <user_id> <cantidad>", "Dar XP a un jugador (puede subir de nivel)"),
        ]
    },
    "objetos": {
        "emoji": "🎒", "titulo": "Objetos e Inventario", "nivel": 1,
        "comandos": [
            ("/dar_objeto <user_id> <id_objeto> [cant]", "Añadir un objeto al inventario del jugador"),
            ("/quitar_objeto <user_id> <id_objeto> [cant]", "Quitar objeto del inventario del jugador"),
            ("/premios_buscar", "Buscador interactivo — encuentra objetos por nombre"),
            ("/premios_entregar <user_id>", "Entregar premio al jugador usando el buscador"),
            ("/ver_inventario <user_id>", "Ver el inventario completo de cualquier jugador"),
        ]
    },
    "jugadores": {
        "emoji": "👤", "titulo": "Gestión de Jugadores", "nivel": 1,
        "comandos": [
            ("/ver_perfil_completo <user_id>", "🔍 Ver TODOS los datos + botones para editar/dar recursos inline"),
            ("/lista_jugadores [pag]", "📋 Lista todos los jugadores (nivel, clase, facción)"),
            ("/ver_estadisticas <user_id>", "Ver stats básicos del jugador"),
            ("/cambiar_nivel <user_id> <nivel>", "Cambiar el nivel del jugador"),
            ("/cambiar_clase <user_id> <clase>", "Cambiar la clase del jugador"),
            ("/cambiar_faccion <user_id> <faccion>", "Cambiar la facción del jugador"),
            ("/revivir <user_id>", "Revivir HP al máximo"),
            ("/set_hp <user_id> <valor>", "⚙️ Establecer HP actual exacto"),
            ("/set_atk <user_id> <valor>", "⚙️ Establecer ATK exacto"),
            ("/set_def <user_id> <valor>", "⚙️ Establecer DEF exacta"),
            ("/set_xp <user_id> <valor>", "⚙️ Establecer XP exacta"),
            ("/set_stamina <user_id> <actual> [max]", "⚙️ Establecer stamina actual y máxima"),
            ("/limpiar_penalizaciones <user_id>", "🧹 Eliminar ban, silencio y todos los cooldowns"),
            ("/limpiar_actividad <user_id>", "🔓 Liberar jugador atascado en combate o mazmorra"),
            ("/reset_actividad <user_id>", "Limpiar actividad atascada"),
            ("/marcar <user_id>", "Poner marca de buscado"),
            ("/desmarcar <user_id>", "Quitar la marca de buscado"),
            ("/banear <user_id> [motivo]", "Banear jugador"),
            ("/desbanear <user_id>", "Quitar el baneo"),
            ("/silenciar <user_id>", "Silenciar jugador"),
            ("/desilenciar <user_id>", "Quitar el silencio"),
            ("/resetear_cooldowns <user_id>", "Limpiar cooldowns del jugador"),
            ("/modificar_stamina <user_id> <+/-cant>", "Añadir/quitar stamina"),
            ("/dar_titulo <user_id> <titulo>", "Dar un título especial"),
        ]
    },
    "jefes": {
        "emoji": "🐉", "titulo": "Jefes Raid", "nivel": 1,
        "comandos": [
            ("/jefe_iniciar <nombre> [hp] [dificultad]", "Invocar un jefe (Facil/Normal/Dificil/Legendario) — notifica a todos"),
            ("/jefe_comenzar", "Iniciar el combate cuando haya participantes unidos"),
            ("/jefe_cancelar", "Cancelar el jefe activo y terminar el evento"),
            ("/jefe_recompensa <user_id> <objeto> [cant]", "Entregar recompensa especial al jugador"),
            ("/jefe_info", "Ver estado detallado: HP, participantes y daño causado"),
        ]
    },
    "mundo": {
        "emoji": "🌍", "titulo": "Mundo y Eventos", "nivel": 1,
        "comandos": [
            ("/cambiar_clima <clima>", "Cambiar el clima global del mundo"),
            ("/iniciar_evento_global <nombre> <efecto> <valor> <horas>", "Lanzar evento global"),
            ("/rotar_tienda_creditos", "Forzar rotación de la tienda de créditos"),
            ("/anular_subasta <id_subasta>", "Cancelar y anular una subasta activa"),
            ("/estado_bot", "Ver estadísticas generales del bot"),
            ("/ajuste_global <tipo> <±%>", "🌍 Ajuste porcentual masivo: oro|eternium|xp|hp a TODOS"),
            ("/dar_masivo <tipo> <cantidad>", "🎁 Dar cantidad fija de oro|eth|cr|xp a TODOS los jugadores"),
        ]
    },
    "viajes": {
        "emoji": "🗺️", "titulo": "Tiempos de Viaje y Zonas", "nivel": 1,
        "comandos": [
            ("/panel_viajes", "🗺️ Panel interactivo para ajustar los tiempos de cada tipo de viaje con botones +-"),
            ("/panel_zonas",  "⏳ Panel interactivo para editar el tiempo de espera antes de salir de zona roja/negra"),
        ]
    },
    "guerra": {
        "emoji": "⚔️", "titulo": "Guerra y Facciones", "nivel": 1,
        "comandos": [
            ("/panel_guerras", "🎮 Panel de control completo de guerras con botones (iniciar, config, stats…)"),
            ("/guerra_facciones_iniciar", "Activar una guerra de facciones ahora (10 min)"),
            ("/guerra_facciones_finalizar", "Terminar la guerra activa y distribuir recompensas"),
            ("/guerra_facciones_estado", "Ver marcador en tiempo real"),
            ("/guerra_facciones_ranking", "Ver ranking de participantes"),
            ("/admin_guerra_gremios_resolver", "Resolver una guerra de gremios pendiente"),
            ("/guerra_limpiar", "🧹 Limpiar el estado de guerra activa (elimina flags atascados)"),
            ("/saltar_guerra", "⏩ Saltar/terminar anticipadamente la guerra de facciones activa"),
            ("/faccion_libre", "Permitir que los jugadores elijan su facción"),
            ("/faccion_auto", "Asignación automática de facciones"),
            ("/faccion_estado", "Ver distribución de jugadores por facción"),
        ]
    },
    "gremios": {
        "emoji": "🏰", "titulo": "Gremios (Admin)", "nivel": 1,
        "comandos": [
            ("/panel_gremios",                                              "🏰 Panel interactivo — config general de gremios (coste creación, capacidad inicial, etc.)"),
            ("/panel_gremio_niveles",                                       "🏛️ Panel interactivo — ver y editar valores de cada nivel 1-10 (capacidad, baúl, coste, bonos)"),
            ("/admin_gremio_config_nivel <nivel> <campo> <valor>",          "Editar un campo de configuración de un nivel por comando. Campos: capacidad | limite_baul | coste_oro | xp_bonus | oro_bonus | stamina_bonus | crafting_descuento"),
            ("/admin_gremio_forzar_nivel <gremio_id> <nivel>",             "Forzar el nivel de un gremio concreto (1-10)"),
            ("/admin_gremio_config <gremio>",                              "Configurar opciones básicas de un gremio específico"),
            ("/admin_disolver_gremio <gremio>",                            "Disolver completamente un gremio"),
        ]
    },
    "rankings": {
        "emoji": "🏆", "titulo": "Rankings (Admin)", "nivel": 1,
        "comandos": [
            ("/admin_rankings",                           "🏆 Panel interactivo de rankings con pestañas: semanal, total XP, daño, gremios, riqueza"),
            ("/admin_ranking_reset_semana",              "🗡️ Reiniciar el contador semanal de monstruos matados para todos los jugadores"),
            ("/admin_ranking_reset_dano",                "💥 Reiniciar todos los acumuladores de daño personal del ranking opt-in"),
            ("/admin_ranking_opt_forzar <uid> <0|1>",   "Forzar la participación (opt-in/out) de un jugador en el ranking de daño"),
            ("/admin_ranking_stats",                     "📊 Ver estadísticas generales de participación en rankings"),
            ("/ranking_dano_opt",                        "(Jugador) Activar o desactivar la participación en el ranking de daño personal"),
            ("/rankings",                                "(Jugador) Abrir el menú principal de rankings (solo en ciudad)"),
        ]
    },
    "stats": {
        "emoji": "📊", "titulo": "Editor de Stats / Items", "nivel": 1,
        "comandos": [
            ("/panel", "🗃️ Panel maestro visual — navega y ve todos los objetos del juego (armas, armaduras, materiales, monturas, monstruos, pociones)"),
            ("/ver_stamina <user_id>", "Ver stamina actual de un jugador"),
            ("/set_stamina <user_id> <cantidad>", "Establecer stamina a un valor concreto"),
            ("/buscar_monstruo <nombre>", "Buscar monstruo por nombre parcial"),
            ("/ver_monstruo <id>", "Ver todos los datos de un monstruo"),
            ("/editar_monstruo <id> <campo> <valor>", "Editar un campo del monstruo (hp, atk, def…)"),
            ("/reset_monstruo <id>", "Resetear monstruo a sus valores base"),
            ("/ver_arma <id>", "Ver todos los datos de un arma"),
            ("/editar_arma <id> <campo> <valor>", "Editar un campo de un arma (atk, precio…)"),
            ("/reset_arma <id>", "Resetear arma a valores base"),
            ("/ver_armadura <id>", "Ver todos los datos de una armadura"),
            ("/editar_armadura <id> <campo> <valor>", "Editar un campo de una armadura"),
            ("/reset_armadura <id>", "Resetear armadura a valores base"),
            ("/editar_precio <id_obj> <oro> [eter]", "Cambiar el precio de un objeto en tienda"),
        ]
    },
    "restricciones": {
        "emoji": "🔒", "titulo": "Restricciones de Combate", "nivel": 99,
        "comandos": [
            ("/restricciones_combate", "Abre el panel interactivo — activa/desactiva cada restricción con botones"),
            ("/rc_duelos",             "Toggle rápido: bloquear o permitir duelos PvP entre jugadores"),
            ("/rc_combate",            "Toggle rápido: bloquear o permitir combate PvE (mazmorras, jefes, investigación)"),
            ("/rc_habilidades",        "Toggle global: bloquear o permitir habilidades en TODO el combate"),
            ("/rc_habilidades_pve",    "Toggle fino: habilidades solo en combate PvE (jefes, investigación)"),
            ("/rc_habilidades_pvp",    "Toggle fino: habilidades solo en duelos PvP"),
            ("/rc_habilidades_caza",   "Toggle fino: habilidades solo en zona de caza"),
            ("/rc_habilidades_mazmorra", "Toggle fino: habilidades solo en mazmorras"),
            ("/rc_criticos",           "Toggle rápido: bloquear o permitir golpes críticos en todo combate"),
            ("/rc_huir",               "Toggle rápido: bloquear o permitir la opción de huir en todo combate"),
        ]
    },
    "automatizaciones": {
        "emoji": "🤖", "titulo": "Automatizaciones", "nivel": 99,
        "comandos": [
            ("/panel_auto",                "🤖 Panel interactivo con botones — gestiona todas las automatizaciones"),
            ("/auto_estado",               "Ver estado actual de todas las automatizaciones activas"),
            ("/auto_guerra_on",            "Activar guerra de facciones automática diaria"),
            ("/auto_guerra_off",           "Desactivar guerra de facciones automática diaria"),
            ("/auto_jefes_on",             "Activar sistema de jefes automáticos (normal + difícil)"),
            ("/auto_jefes_off",            "Desactivar todos los jefes automáticos"),
            ("/auto_jefe_normal_on",       "Activar solo el jefe de dificultad Normal automático"),
            ("/auto_jefe_normal_off",      "Desactivar el jefe de dificultad Normal automático"),
            ("/auto_jefe_dificil_on",      "Activar solo el jefe de dificultad Difícil automático"),
            ("/auto_jefe_dificil_off",     "Desactivar el jefe de dificultad Difícil automático"),
            ("/auto_reprogramar_jefes",    "Reprogramar los horarios de jefes automáticos ahora mismo"),
        ]
    },
    "creditos_depositos": {
        "emoji": "💳", "titulo": "Créditos & Depósitos", "nivel": 1,
        "comandos": [
            ("/admin_wallet_bsc [dirección]",   "Ver o cambiar la wallet de recepción para depósitos cripto"),
            ("/admin_wallet_red <red>",          "Cambiar la red de depósitos (ej: BSC BEP20)"),
            ("/admin_creditar <user_id> <cant>", "Acreditar créditos del vacío manualmente a un jugador"),
            ("/admin_solicitudes_creditos",      "Ver y gestionar solicitudes de depósito/retiro pendientes"),
        ]
    },
    "reclutas": {
        "emoji": "🧑‍🤝‍🧑", "titulo": "Sistema de Reclutas", "nivel": 1,
        "comandos": [
            ("/ver_reclutas_config",     "Ver la configuración actual del sistema de reclutas (bonus y nivel)"),
            ("/set_recluta_bonus <N>",   "Cambiar la stamina extra que gana el reclutador por cada recluta"),
            ("/set_recluta_nivel <N>",   "Nivel al que el recluta activa el bonus (0 = instantáneo al usar código)"),
        ]
    },
    "economia_tiendas": {
        "emoji": "💹", "titulo": "Economía & Tiendas", "nivel": 1,
        "comandos": [
            ("/panel_economia", "🟢 Abre el panel interactivo — edita tasas de bolsa y precios de tiendas con botones"),
            ("/bolsa_admin_tasa <tipo> <valor>", "Cambiar tasa directamente (tipos: oro_eternium, eternium_oro, credito_eternium)"),
            ("/ver_precio <item_id>", "Ver los precios actuales de un ítem específico"),
            ("/editar_precio <item_id> <moneda> <valor>", "Editar el precio de un ítem (moneda: oro, eth, cr)"),
            ("/ajustar_precio_tienda <tienda> <moneda> +/-N", "Ajuste masivo por tienda (tienda: oro, eth, cr)"),
            ("/ajustar_precio_todos <moneda> +/-N", "Ajuste masivo en TODOS los ítems del juego"),
        ],
        "boton_panel": ("💹 Abrir Panel de Economía", "ep_abrir"),
    },
    "editor_sa": {
        "emoji": "🛠️", "titulo": "Editor Maestro (SA)", "nivel": 99,
        "comandos": [
            ("/sa_numeros", "📊 Ver TODA la configuración actual del juego: tasas, fórmulas XP, stats de clases, precio de vuelo"),
            ("/sa_jugador <nombre_o_id>", "👤 Editor interactivo paso a paso — busca un jugador y edita cualquier stat (HP, ATK, DEF, XP, nivel, clase…)"),
            ("/sa_monstruo", "🐲 Editor interactivo paso a paso — busca un monstruo y edita cualquier stat (HP, ATK, DEF, XP, oro, drop…)"),
            ("/sa_arma", "⚔️ Editor interactivo paso a paso — busca un arma y edita cualquier campo (daño, crítico, velocidad, precio…)"),
            ("/sa_armadura", "🛡️ Editor interactivo paso a paso — busca una armadura y edita cualquier campo (defensa, resistencia, precio…)"),
            ("/sa_precio", "💰 Editor interactivo de precios — busca un ítem y cambia su precio en oro, eternium o créditos"),
            ("/sa_tasas", "💱 Editor interactivo de tasas de cambio — modifica las tasas del banco (oro↔eternium, créditos↔eternium)"),
            ("/sa_xp", "⭐ Editor interactivo de la fórmula XP — ajusta base y exponente de la curva de progresión"),
            ("/sa_clase", "🧬 Editor interactivo de stats de clases — modifica HP, ATK, DEF, velocidad base de cada clase"),
        ]
    },
    "items_custom": {
        "emoji": "✨", "titulo": "Creación de Items Custom (SA)", "nivel": 99,
        "comandos": [
            ("/crear_arma", "⚔️ Wizard interactivo — crea un arma personalizada con nombre, stats, rareza y clase objetivo. El arma queda disponible en la tienda."),
            ("/crear_armadura", "🛡️ Wizard interactivo — crea una armadura personalizada con nombre, stats, rareza y clase objetivo."),
            ("/mis_items_custom", "📋 Ver todos los items custom creados con sus IDs (útil para borrar o referenciarlos)"),
            ("/borrar_item_custom <id>", "🗑️ Eliminar permanentemente un item custom del juego por su ID"),
        ]
    },
    "umbral_vacio": {
        "emoji": "🌑", "titulo": "Umbral del Vacío", "nivel": 1,
        "comandos": [
            ("/umbral_admin",               "🌑 Panel de administración del Umbral del Vacío con botones"),
            ("/umbral_set corrupcion <N>",  "Fijar corrupción a N%  (0-100)"),
            ("/umbral_set tasa_diaria <N>", "Tasa de corrupción diaria en % (por defecto 3)"),
            ("/umbral_set multiplicador_precios <N>", "Multiplicador de precios durante escasez (por defecto 2.0)"),
            ("/umbral_set hp_monstruo_base <N>",      "HP base de cada monstruo de facción"),
            ("/umbral_set hp_jefe_base <N>",          "HP del Jefe Final"),
            ("/umbral_set rondas_monstruo <N>",       "Rondas por monstruo"),
            ("/umbral_set rondas_jefe <N>",           "Rondas del jefe final"),
            ("/umbral_set max_ataques_jugador <N>",   "Ataques permitidos por jugador por monstruo"),
            ("/umbral_set min_jugadores_monstruo <N>","Mínimo de jugadores requeridos para el monstruo"),
            ("/umbral_avanzar",             "⚔️ Avanzar manualmente a la siguiente ronda de combate"),
        ]
    },
    "config_juego": {
        "emoji": "⚙️", "titulo": "Config Permanente del Juego", "nivel": 1,
        "comandos": [
            ("/config_juego", "⚙️ Panel interactivo con botones — edita y guarda para siempre TODOS los valores del juego: precios, stamina, cooldowns, monstruos, mazmorras, crafteo, subastas, gremios, jefes, economía y mucho más"),
        ]
    },
    "balance": {
        "emoji": "⚖️", "titulo": "Balance Global del Juego", "nivel": 1,
        "comandos": [
            ("/balance_global", "⚖️ Panel interactivo con botones — sube o baja en ±10% la vida/daño/defensa de TODOS los monstruos, armas, armaduras y pociones del juego de golpe. Incluye auto-balance y reset total."),
            ("/ajustar_monstruos_zona <color> <stat> +/-N", "Ajuste relativo de un stat en todos los monstruos de una zona (azul/amarilla/roja/negra). Ej: /ajustar_monstruos_zona roja daño +50"),
            ("/editar_monstruos_zona <color> <stat> <valor>", "Fijar valor absoluto de un stat en todos los monstruos de una zona. Ej: /editar_monstruos_zona negra vida 2000"),
            ("/ajustar_armas <stat> +/-N", "Ajuste relativo de un stat en TODAS las armas del juego. Stats: daño, critico, velocidad, vida_extra, defensa_extra"),
            ("/ajustar_armaduras <stat> +/-N", "Ajuste relativo de un stat en TODAS las armaduras del juego. Stats: defensa, resistencia_critico, vida_extra, defensa_extra"),
            ("/ajustar_precio_tienda <tienda> <moneda> +/-N", "Ajuste masivo de precios por tienda completa (tienda: oro, eth, cr)"),
            ("/ajustar_precio_todos <moneda> +/-N", "Ajuste masivo de precios en TODOS los ítems del juego"),
            ("/ajuste_global <tipo> <±%>", "Ajuste porcentual masivo de oro|eternium|xp|hp a TODOS los jugadores activos"),
            ("/dar_masivo <tipo> <cantidad>", "Dar cantidad fija de oro|eth|cr|xp a TODOS los jugadores activos"),
        ],
        "boton_panel": ("⚖️ Abrir Panel de Balance", "bgp_open"),
    },
}


# ── PERMISOS GRANULARES POR COMANDO INDIVIDUAL ───────────────────────────────

_perm_cmd_tmp: dict = {}  # {uid_editor: {"uid": uid_target, "sel": set}}


def _todos_cmds_por_categoria() -> dict:
    """Devuelve {cat_clave: [(cmd_name, desc), ...]} para categorías accesibles por admins nivel 1."""
    result = {}
    for clave, cat in PANEL_CATEGORIAS.items():
        if cat.get("nivel", 1) > 1:
            continue
        cmds = []
        for cmd_line, desc in cat.get("comandos", []):
            cmd_name = cmd_line.lstrip("/").split()[0]
            cmds.append((cmd_name, desc))
        if cmds:
            result[clave] = cmds
    return result


def _cmds_individuales(user_id: int):
    """Devuelve set de comandos si está en modo individual, o None si usa modo categorías."""
    if _es_superadmin(user_id):
        return None
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT comando FROM admin_cmd_permisos WHERE user_id = ?", (user_id,))
    rows = c.fetchall()
    conn.close()
    return {r[0] for r in rows} if rows else None


def _guardar_cmds_individuales(user_id: int, comandos: set):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM admin_cmd_permisos WHERE user_id = ?", (user_id,))
    for cmd in comandos:
        c.execute("INSERT OR IGNORE INTO admin_cmd_permisos (user_id, comando) VALUES (?,?)",
                  (user_id, cmd))
    conn.commit()
    conn.close()


def _borrar_cmds_individuales(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM admin_cmd_permisos WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


def obtener_cmds_admin_permitidos(user_id: int):
    """
    Función pública para zonas_comandos.py.
    Devuelve set de nombres de comando que el admin puede usar, o None (sin restricción).
    """
    if _es_superadmin(user_id):
        return None
    cmds_ind = _cmds_individuales(user_id)
    if cmds_ind is not None:
        return cmds_ind
    cats = _categorias_admin(user_id)
    if not cats:
        return set()
    result = set()
    for clave, cat in PANEL_CATEGORIAS.items():
        if clave in cats:
            for cmd_line, _ in cat.get("comandos", []):
                result.add(cmd_line.lstrip("/").split()[0])
    return result if result else None


def _kb_pcmd_categoria(uid_target: int, cat_clave: str, seleccion: set) -> InlineKeyboardMarkup:
    todos = _todos_cmds_por_categoria()
    cmds  = todos.get(cat_clave, [])
    filas = []
    for cmd_name, _desc in cmds:
        activo = cmd_name in seleccion
        filas.append([InlineKeyboardButton(
            f"{'✅' if activo else '☐'} /{cmd_name}",
            callback_data=f"pcmd_t_{uid_target}_{cmd_name}"
        )])
    filas.append([
        InlineKeyboardButton("✅ Todos",   callback_data=f"pcmd_all_{uid_target}_{cat_clave}"),
        InlineKeyboardButton("☐ Ninguno", callback_data=f"pcmd_none_{uid_target}_{cat_clave}"),
    ])
    filas.append([InlineKeyboardButton("🔙 Volver", callback_data=f"pcmd_back_{uid_target}")])
    return InlineKeyboardMarkup(filas)


def _kb_pcmd_overview(uid_target: int, seleccion: set) -> InlineKeyboardMarkup:
    todos = _todos_cmds_por_categoria()
    filas = []
    for cat_clave, cmds in todos.items():
        cat_info = PANEL_CATEGORIAS[cat_clave]
        n_sel   = sum(1 for cn, _ in cmds if cn in seleccion)
        filas.append([InlineKeyboardButton(
            f"{cat_info['emoji']} {cat_info['titulo']} ({n_sel}/{len(cmds)})",
            callback_data=f"pcmd_cat_{uid_target}_{cat_clave}"
        )])
    filas.append([
        InlineKeyboardButton("💾 Guardar",          callback_data=f"pcmd_save_{uid_target}"),
        InlineKeyboardButton("🔄 Modo categorías",  callback_data=f"pcmd_reset_{uid_target}"),
    ])
    filas.append([InlineKeyboardButton("❌ Cancelar", callback_data="pcmd_cancel")])
    return InlineKeyboardMarkup(filas)


async def cmd_superadmin_permisos_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Abre el selector de comandos individuales para un admin."""
    user_id = update.effective_user.id
    if not _es_superadmin(user_id):
        await update.effective_message.reply_text("❌ Solo el superadmin puede usar este comando.")
        return
    args = context.args
    if not args:
        await update.effective_message.reply_text(
            "Uso: `/superadmin_permisos_cmd <user_id>`\n\n"
            "Selecciona exactamente qué comandos admin puede usar ese admin\\.",
            parse_mode="Markdown"
        )
        return
    try:
        uid_target = int(args[0])
    except ValueError:
        await update.effective_message.reply_text("❌ user\\_id inválido\\.", parse_mode="Markdown")
        return
    if _nivel_admin(uid_target) < 1:
        await update.effective_message.reply_text(
            f"❌ El usuario `{uid_target}` no es admin\\. Créalo primero con `/superadmin_crear_admin`\\.",
            parse_mode="Markdown"
        )
        return
    seleccion = _cmds_individuales(uid_target) or set()
    _perm_cmd_tmp[user_id] = {"uid": uid_target, "sel": set(seleccion)}
    modo = "individual" if _cmds_individuales(uid_target) is not None else "categorías"
    await update.effective_message.reply_text(
        f"🔐 *Permisos por comando individual*\n\n"
        f"Admin: `{uid_target}`\nModo actual: *{modo}*\n\n"
        f"Selecciona categorías para activar/desactivar comandos concretos\\.\n"
        f"Al guardar se activa el modo individual para este admin\\.",
        reply_markup=_kb_pcmd_overview(uid_target, seleccion),
        parse_mode="Markdown"
    )


async def cb_pcmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja todos los callbacks pcmd_*"""
    query   = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    data    = query.data

    if not _es_superadmin(user_id):
        await query.answer("❌ Sin permiso.", show_alert=True)
        return

    if data == "pcmd_cancel":
        _perm_cmd_tmp.pop(user_id, None)
        try:
            await query.edit_message_text("❌ Cancelado.")
        except Exception:
            pass
        return

    parts = data.split("_")

    if data.startswith("pcmd_save_"):
        uid_target = int(parts[2])
        tmp = _perm_cmd_tmp.get(user_id, {})
        if tmp.get("uid") != uid_target:
            await query.answer("❌ Sesión expirada.", show_alert=True)
            return
        sel = tmp.get("sel", set())
        _guardar_cmds_individuales(uid_target, sel)
        _perm_cmd_tmp.pop(user_id, None)
        await query.edit_message_text(
            f"✅ *Permisos individuales guardados*\n\nAdmin: `{uid_target}`\n"
            f"Comandos activos: *{len(sel)}*\n\n"
            f"El menú `/` y el panel de ese admin mostrarán solo esos comandos\\.",
            parse_mode="Markdown"
        )
        return

    if data.startswith("pcmd_reset_"):
        uid_target = int(parts[2])
        _borrar_cmds_individuales(uid_target)
        _perm_cmd_tmp.pop(user_id, None)
        await query.edit_message_text(
            f"🔄 Permisos individuales eliminados para `{uid_target}`\\.\n"
            f"Ahora usa el modo de *categorías*\\.",
            parse_mode="Markdown"
        )
        return

    if data.startswith("pcmd_back_"):
        uid_target = int(parts[2])
        tmp = _perm_cmd_tmp.get(user_id, {})
        if tmp.get("uid") != uid_target:
            await query.answer("❌ Sesión expirada.", show_alert=True)
            return
        sel = tmp.get("sel", set())
        try:
            await query.edit_message_text(
                f"🔐 *Permisos por comando individual*\n\nAdmin: `{uid_target}`",
                reply_markup=_kb_pcmd_overview(uid_target, sel),
                parse_mode="Markdown"
            )
        except Exception:
            pass
        return

    if data.startswith("pcmd_cat_"):
        uid_target = int(parts[2])
        cat_clave  = "_".join(parts[3:])
        tmp = _perm_cmd_tmp.get(user_id, {})
        if tmp.get("uid") != uid_target:
            await query.answer("❌ Sesión expirada.", show_alert=True)
            return
        sel      = tmp.get("sel", set())
        cat_info = PANEL_CATEGORIAS.get(cat_clave, {})
        try:
            await query.edit_message_text(
                f"{cat_info.get('emoji','🔧')} *{cat_info.get('titulo','Categoría')}*\n\n"
                f"Activa o desactiva comandos individuales:",
                reply_markup=_kb_pcmd_categoria(uid_target, cat_clave, sel),
                parse_mode="Markdown"
            )
        except Exception:
            pass
        return

    if data.startswith("pcmd_t_"):
        uid_target = int(parts[2])
        cmd_name   = "_".join(parts[3:])
        tmp = _perm_cmd_tmp.get(user_id, {})
        if tmp.get("uid") != uid_target:
            await query.answer("❌ Sesión expirada.", show_alert=True)
            return
        sel = tmp["sel"]
        sel.discard(cmd_name) if cmd_name in sel else sel.add(cmd_name)
        todos     = _todos_cmds_por_categoria()
        cat_clave = next((ck for ck, cmds in todos.items() if any(cn == cmd_name for cn, _ in cmds)), None)
        if cat_clave:
            try:
                await query.edit_message_reply_markup(
                    reply_markup=_kb_pcmd_categoria(uid_target, cat_clave, sel)
                )
            except Exception:
                pass
        return

    if data.startswith("pcmd_all_"):
        uid_target = int(parts[2])
        cat_clave  = "_".join(parts[3:])
        tmp = _perm_cmd_tmp.get(user_id, {})
        if tmp.get("uid") != uid_target:
            await query.answer("❌ Sesión expirada.", show_alert=True)
            return
        sel = tmp["sel"]
        for cn, _ in _todos_cmds_por_categoria().get(cat_clave, []):
            sel.add(cn)
        try:
            await query.edit_message_reply_markup(
                reply_markup=_kb_pcmd_categoria(uid_target, cat_clave, sel)
            )
        except Exception:
            pass
        return

    if data.startswith("pcmd_none_"):
        uid_target = int(parts[2])
        cat_clave  = "_".join(parts[3:])
        tmp = _perm_cmd_tmp.get(user_id, {})
        if tmp.get("uid") != uid_target:
            await query.answer("❌ Sesión expirada.", show_alert=True)
            return
        sel = tmp["sel"]
        for cn, _ in _todos_cmds_por_categoria().get(cat_clave, []):
            sel.discard(cn)
        try:
            await query.edit_message_reply_markup(
                reply_markup=_kb_pcmd_categoria(uid_target, cat_clave, sel)
            )
        except Exception:
            pass
        return


def _teclado_panel(user_id: int):
    """Genera el teclado del panel según las categorías autorizadas de este admin."""
    nivel         = _nivel_admin(user_id)
    cats_visibles = _categorias_admin(user_id)
    cmds_ind      = _cmds_individuales(user_id)  # None = modo categorías
    todos_cat     = _todos_cmds_por_categoria()
    fila = []
    kb   = []
    for clave, cat in PANEL_CATEGORIAS.items():
        if not _es_superadmin(user_id):
            if nivel < cat["nivel"]:
                continue
            if cmds_ind is not None:
                # Modo individual: mostrar sección solo si tiene algún comando permitido
                cat_cmds = {cn for cn, _ in todos_cat.get(clave, [])}
                if not cat_cmds.intersection(cmds_ind):
                    continue
            else:
                if clave not in cats_visibles:
                    continue
        btn = InlineKeyboardButton(
            f"{cat['emoji']} {cat['titulo']}",
            callback_data=f"panel_cat_{clave}"
        )
        fila.append(btn)
        if len(fila) == 2:
            kb.append(fila)
            fila = []
    if fila:
        kb.append(fila)
    if _es_superadmin(user_id):
        kb.append([InlineKeyboardButton("🗃️ Panel Maestro", callback_data="abrir_panel_maestro")])
        kb.append([InlineKeyboardButton("⚙️ Automatizaciones", callback_data="paut_ver")])
    kb.append([InlineKeyboardButton("❌ Cerrar panel", callback_data="panel_cerrar")])
    return kb


async def cmd_panel_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra el panel de comandos admin por categorías."""
    user_id = update.effective_user.id
    nivel = _nivel_admin(user_id)
    if nivel < 1:
        await update.effective_message.reply_text("❌ No tienes permisos de administrador.")
        return
    tipo = "Superadmin" if _es_superadmin(user_id) else ("Dios" if nivel >= 2 else "Admin")
    cats = _categorias_admin(user_id) - {"superadmin", "dios", "restricciones"}
    if not cats and not _es_superadmin(user_id) and nivel < 2:
        await update.effective_message.reply_text(
            "⚠️ Tu cuenta de admin no tiene ningún permiso asignado todavía.\n"
            "Contacta al superadmin para que te otorgue acceso a categorías."
        )
        return
    await update.effective_message.reply_text(
        f"🛡️ *Panel de Administración* [{tipo}]\n\nSelecciona una categoría:",
        reply_markup=InlineKeyboardMarkup(_teclado_panel(user_id)),
        parse_mode="Markdown"
    )


async def cb_admin_panel_boton(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback del botón '🛡️ Menú Admin' del menú de ciudad."""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    nivel = _nivel_admin(user_id)
    if nivel < 1:
        await query.answer("❌ No tienes permisos de administrador.", show_alert=True)
        return
    tipo = "Superadmin" if _es_superadmin(user_id) else ("Dios" if nivel >= 2 else "Admin")
    await query.edit_message_text(
        f"🛡️ *Panel de Administración* [{tipo}]\n\nSelecciona una categoría:",
        reply_markup=InlineKeyboardMarkup(_teclado_panel(user_id)),
        parse_mode="Markdown"
    )


async def cb_panel_categoria(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    nivel = _nivel_admin(user_id)
    clave = query.data.replace("panel_cat_", "")
    if clave not in PANEL_CATEGORIAS:
        return
    cat = PANEL_CATEGORIAS[clave]
    if nivel < cat["nivel"] or not _tiene_permiso(user_id, clave):
        await query.answer("❌ No tienes permiso para esta categoría.", show_alert=True)
        return
    # Categorías con panel interactivo propio: abrirlo directamente sin botón intermedio
    if clave == "simulaciones":
        import simulaciones as _sim
        await _sim.cmd_simulaciones(update, context)
        return
    if clave == "economia_tiendas":
        import economia_panel as _ep
        await _ep._abrir_panel(update, context)
        return
    if clave == "balance":
        import admin_stats as _as
        await _as.cb_balance_global(update, context)
        return
    if clave == "membresia":
        import membresia as _mb
        await _mb._panel_admin_memb(update, context, editar=True)
        return
    if clave == "viajes":
        texto, kb = _panel_viajes_texto_teclado()
        try:
            await query.edit_message_text(texto, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            await update.effective_message.reply_text(texto, reply_markup=kb, parse_mode="Markdown")
        return
    if clave == "config_juego":
        texto, kb = _menu_categorias_cfg()
        try:
            await query.edit_message_text(texto, reply_markup=kb, parse_mode="HTML")
        except Exception:
            await update.effective_message.reply_text(texto, reply_markup=kb, parse_mode="HTML")
        return
    if clave == "comunicacion":
        texto, kb = _panel_broadcast_texto_teclado()
        try:
            await query.edit_message_text(texto, reply_markup=kb, parse_mode="HTML")
        except Exception:
            await update.effective_message.reply_text(texto, reply_markup=kb, parse_mode="HTML")
        return

    import html as _html
    titulo_esc = _html.escape(cat['titulo'])
    texto = f"{cat['emoji']} <b>{titulo_esc}</b>\n\n"
    # Filtrar comandos según permisos individuales (si están activos)
    cmds_ind = _cmds_individuales(user_id) if not _es_superadmin(user_id) else None
    for cmd, desc in cat["comandos"]:
        cmd_name = cmd.lstrip("/").split()[0]
        if cmds_ind is not None and cmd_name not in cmds_ind:
            continue  # no tiene permiso individual para este comando
        # Separar comando de sus argumentos: el comando queda como enlace azul tocable,
        # los argumentos van en <code> como referencia de sintaxis
        _parts = cmd.split(None, 1)
        _cmd_link = _html.escape(_parts[0])
        if len(_parts) > 1:
            _cmd_link += f" <code>{_html.escape(_parts[1])}</code>"
        texto += f"{_cmd_link}\n   ↳ {_html.escape(desc)}\n\n"
    teclado = []
    if clave == "restricciones":
        teclado.append([InlineKeyboardButton("🔒 Abrir Panel de Restricciones", callback_data="panel_abrir_restricciones")])
    teclado.append([InlineKeyboardButton("◀️ Volver al panel", callback_data="panel_volver")])
    await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(teclado), parse_mode="HTML")


async def cb_panel_volver(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    nivel = _nivel_admin(user_id)
    tipo  = "Superadmin" if _es_superadmin(user_id) else ("Dios" if nivel >= 2 else "Admin")
    await query.edit_message_text(
        f"🛡️ *Panel de Administración* [{tipo}]\n\nSelecciona una categoría:",
        reply_markup=InlineKeyboardMarkup(_teclado_panel(user_id)),
        parse_mode="Markdown"
    )


async def cb_panel_cerrar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("🛡️ Panel cerrado. Usa /panel_admin para volver a abrirlo.")


async def cb_broadcast_modo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback: el admin eligió a quién enviar el broadcast. Pide el mensaje."""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    if _nivel_admin(user_id) < 1:
        await query.answer("❌ Sin permisos.", show_alert=True)
        return
    data = query.data
    if data == "bc_modo_activos":
        modo = "activos"
        n = len(db_helper.obtener_jugadores_activos(600))
        label = f"🟢 jugadores activos ({n})"
    elif data == "bc_modo_todos":
        modo = "todos"
        n = len(db_helper.obtener_todos_jugadores())
        label = f"📢 TODOS los jugadores ({n})"
    elif data.startswith("bc_modo_faccion_"):
        faccion = data.replace("bc_modo_faccion_", "")
        modo = f"faccion_{faccion}"
        label = f"⚔️ jugadores de {faccion}"
        n = "?"
    elif data == "bc_cancelar":
        context.user_data.pop("broadcast_modo", None)
        texto, kb = _panel_broadcast_texto_teclado()
        await query.edit_message_text(texto, reply_markup=kb, parse_mode="HTML")
        return
    else:
        modo = "todos"
        label = "TODOS"
    context.user_data["broadcast_modo"] = modo
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Cancelar envío", callback_data="bc_cancelar")]
    ])
    await query.edit_message_text(
        f"📢 <b>Mensaje para: {label}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        "✏️ <b>Escribe tu mensaje ahora</b> (este chat, texto normal):\n\n"
        "📝 <b>Ejemplos de formato HTML:</b>\n"
        "  • <code>&lt;b&gt;texto en negrita&lt;/b&gt;</code>\n"
        "  • <code>&lt;i&gt;texto en cursiva&lt;/i&gt;</code>\n"
        "  • <code>&lt;code&gt;texto tipo código&lt;/code&gt;</code>\n"
        "  • Emojis normales directamente: ⚔️🐉💎\n\n"
        "⚠️ <b>Antes de enviar verás una vista previa para confirmar.</b>\n\n"
        "Pulsa Cancelar si no quieres enviar nada.",
        parse_mode="HTML",
        reply_markup=kb,
    )


async def mh_broadcast_mensaje(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """MessageHandler: captura el texto del admin cuando tiene un broadcast pendiente."""
    user_id = update.effective_user.id
    if _nivel_admin(user_id) < 1:
        return
    modo = context.user_data.get("broadcast_modo")
    if not modo:
        return
    texto_msg = update.message.text or ""
    if texto_msg.strip().lower() in ("/cancelar_broadcast", "cancelar_broadcast", "/cancelar", "cancelar"):
        context.user_data.pop("broadcast_modo", None)
        await update.message.reply_text(
            "❌ <b>Envío cancelado.</b> No se envió ningún mensaje.",
            parse_mode="HTML"
        )
        return
    # Guardar el mensaje pendiente y mostrar vista previa
    context.user_data["broadcast_preview"] = texto_msg
    import html as _ht
    preview_cortado = texto_msg[:800] + ("..." if len(texto_msg) > 800 else "")
    if modo == "activos":
        destino_label = f"🟢 jugadores activos ({len(db_helper.obtener_jugadores_activos(600))})"
    elif modo == "todos":
        destino_label = f"📢 TODOS los jugadores ({len(db_helper.obtener_todos_jugadores())})"
    elif modo.startswith("faccion_"):
        faccion = modo.replace("faccion_", "")
        destino_label = f"⚔️ jugadores de {faccion}"
    else:
        destino_label = modo
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Confirmar y Enviar", callback_data="bc_confirmar")],
        [InlineKeyboardButton("✏️ Reescribir mensaje", callback_data=f"bc_reescribir_{modo}")],
        [InlineKeyboardButton("❌ Cancelar", callback_data="bc_cancelar")],
    ])
    await update.message.reply_text(
        f"👁️ <b>VISTA PREVIA DEL MENSAJE</b>\n"
        f"Destinatarios: {destino_label}\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"{preview_cortado}\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "¿Enviar este mensaje?",
        parse_mode="HTML",
        reply_markup=kb,
    )


async def cb_broadcast_confirmar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback: el admin confirma (o cancela) el envío después de ver la vista previa."""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    if _nivel_admin(user_id) < 1:
        await query.answer("❌ Sin permisos.", show_alert=True)
        return
    data = query.data
    if data == "bc_cancelar":
        context.user_data.pop("broadcast_modo", None)
        context.user_data.pop("broadcast_preview", None)
        await query.edit_message_text("❌ <b>Envío cancelado.</b> No se envió ningún mensaje.", parse_mode="HTML")
        return
    if data.startswith("bc_reescribir_"):
        modo = data.replace("bc_reescribir_", "")
        context.user_data["broadcast_modo"] = modo
        context.user_data.pop("broadcast_preview", None)
        if modo == "activos":
            label = f"🟢 jugadores activos ({len(db_helper.obtener_jugadores_activos(600))})"
        elif modo == "todos":
            label = f"📢 TODOS los jugadores ({len(db_helper.obtener_todos_jugadores())})"
        elif modo.startswith("faccion_"):
            faccion = modo.replace("faccion_", "")
            label = f"⚔️ jugadores de {faccion}"
        else:
            label = modo
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Cancelar envío", callback_data="bc_cancelar")]
        ])
        await query.edit_message_text(
            f"✏️ <b>Reescribe el mensaje para: {label}</b>\n\n"
            "Escribe el nuevo mensaje en este chat (texto normal):\n"
            "Puedes usar HTML: <b>negrita</b>, <i>cursiva</i>, <code>código</code>\n\n"
            "Pulsa Cancelar si no quieres enviar nada.",
            parse_mode="HTML",
            reply_markup=kb,
        )
        return
    if data == "bc_confirmar":
        texto_msg = context.user_data.pop("broadcast_preview", None)
        modo = context.user_data.pop("broadcast_modo", None)
        if not texto_msg or not modo:
            await query.edit_message_text("❌ Error: no hay mensaje pendiente. Vuelve a iniciar.")
            return
        import broadcast as _bc
        if modo == "activos":
            jugadores_dest = db_helper.obtener_jugadores_activos(600)
            n = len(jugadores_dest)
            await query.edit_message_text(
                f"⏳ Enviando a <b>{n}</b> jugadores activos...",
                parse_mode="HTML"
            )
            task = await _bc.broadcast_activos(context.bot, texto_msg, parse_mode="HTML")
            import asyncio as _asyncio
            async def _done(t, q):
                try:
                    env, fall = await t
                    await q.edit_message_text(
                        f"✅ <b>Envío completado.</b>\n📤 Enviados: <b>{env}</b>  ❌ Fallidos: <b>{fall}</b>",
                        parse_mode="HTML"
                    )
                except Exception:
                    pass
            _asyncio.create_task(_done(task, query))
        elif modo == "todos":
            jugadores_dest = db_helper.obtener_todos_jugadores()
            n = len(jugadores_dest)
            await query.edit_message_text(
                f"⏳ Enviando a <b>{n}</b> jugadores registrados...",
                parse_mode="HTML"
            )
            task = await _bc.broadcast_global(context.bot, texto_msg, parse_mode="HTML")
            import asyncio as _asyncio
            async def _done2(t, q):
                try:
                    env, fall = await t
                    await q.edit_message_text(
                        f"✅ <b>Envío completado.</b>\n📤 Enviados: <b>{env}</b>  ❌ Fallidos: <b>{fall}</b>",
                        parse_mode="HTML"
                    )
                except Exception:
                    pass
            _asyncio.create_task(_done2(task, query))
        elif modo.startswith("faccion_"):
            faccion = modo.replace("faccion_", "")
            try:
                todos = db_helper.obtener_todos_jugadores()
                dest = [j for j in todos if j.get("faccion") == faccion]
            except Exception:
                dest = []
            n = len(dest)
            await query.edit_message_text(
                f"⏳ Enviando a <b>{n}</b> jugadores de {faccion}...",
                parse_mode="HTML"
            )
            import asyncio as _asyncio
            enviados, fallidos = 0, 0
            for jug in dest:
                try:
                    await context.bot.send_message(
                        chat_id=jug["user_id"],
                        text=texto_msg,
                        parse_mode="HTML",
                    )
                    enviados += 1
                except Exception:
                    fallidos += 1
                await _asyncio.sleep(0.05)
            await query.edit_message_text(
                f"✅ <b>Enviado a {faccion}.</b>\n📤 Enviados: <b>{enviados}</b>  ❌ Fallidos: <b>{fallidos}</b>",
                parse_mode="HTML"
            )


async def cb_abrir_panel_maestro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Abre el Panel Maestro (panel_admin) desde el botón inline del panel de superadmin."""
    query = update.callback_query
    await query.answer()
    try:
        import panel_admin as _pa
        await _pa.cmd_panel_admin(update, context)
    except Exception as e:
        await query.edit_message_text(f"❌ Error al abrir Panel Maestro: {e}")


async def cb_panel_abrir_restricciones(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Abre el panel interactivo de restricciones de combate desde el menú admin."""
    query = update.callback_query
    await query.answer()
    if not _es_superadmin(update.effective_user.id):
        await query.answer("❌ Exclusivo del superadmin.", show_alert=True)
        return
    try:
        import restricciones_combate as _rc
        texto, markup = _rc._construir_panel()
        await query.edit_message_text(texto, reply_markup=markup, parse_mode="Markdown")
    except Exception as e:
        await query.edit_message_text(f"❌ Error al abrir panel de restricciones: {e}")


async def cmd_faccion_estado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra el estado actual del sistema de facciones."""
    if not verificar_nivel(update.effective_user.id, 1):
        await update.effective_message.reply_text("❌ Acceso denegado.")
        return
    libre = db_helper.faccion_libre()
    conteo = db_helper.contar_jugadores_por_faccion()
    menos = db_helper.obtener_faccion_menos_poblada()
    total = sum(conteo.values())
    estado_txt = "✅ Los jugadores *eligen* su facción" if libre else "🔄 *Asignación automática* (facción con menos miembros)"
    barras = ""
    for f, c in sorted(conteo.items()):
        pct = int(c / total * 20) if total else 0
        barras += f"  {'⚔️' if f=='Alianza' else '🏛️' if f=='Imperio' else '🗡️'} *{f}*: {'█'*pct}{'░'*(20-pct)} {c} jugadores\n"
    await update.effective_message.reply_text(
        f"🏛️ *Estado del Sistema de Facciones*\n\n"
        f"Modo: {estado_txt}\n"
        f"Próximo auto-asignado → *{menos}*\n\n"
        f"Distribución:\n{barras}",
        parse_mode="Markdown"
    )


# ==================== PANEL DE TIEMPOS DE VIAJE ====================

_VIAJE_CAMPOS = [
    ("viaje_t_dif1",  "🟦↔️🟨  Colores adyacentes",          30,  5,  1,  3600),
    ("viaje_t_dif2",  "🟦↔️🟥  2 niveles de diferencia",     60,  10, 1,  7200),
    ("viaje_t_dif3",  "🟦↔️⬛  3 niveles de diferencia",     120, 15, 1,  7200),
    ("viaje_t_cross", "🔀  Mismo color, distinta facción",  150, 15, 1,  7200),
]

def _fmt_seg(s: int) -> str:
    if s == 0:
        return "0s (instantáneo)"
    m, seg = divmod(s, 60)
    if m:
        return f"{m}m {seg}s" if seg else f"{m}m"
    return f"{seg}s"

def _panel_broadcast_texto_teclado():
    """Genera el texto e InlineKeyboard del panel de comunicación."""
    jugadores = db_helper.obtener_todos_jugadores()
    activos   = db_helper.obtener_jugadores_activos(600)
    total     = len(jugadores)
    n_activos = len(activos)
    texto = (
        "📢 <b>PANEL DE COMUNICACIÓN</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👥 Jugadores registrados: <b>{total}</b>\n"
        f"🟢 Activos últimos 10 min: <b>{n_activos}</b>\n\n"
        "<b>¿A quién quieres enviar el mensaje?</b>\n"
        "<i>Elige un destino y luego escribe tu mensaje.</i>\n\n"
        "💡 <b>Formatos disponibles:</b>\n"
        "  <code>&lt;b&gt;negrita&lt;/b&gt;</code> → <b>negrita</b>\n"
        "  <code>&lt;i&gt;cursiva&lt;/i&gt;</code> → <i>cursiva</i>\n"
        "  <code>&lt;code&gt;código&lt;/code&gt;</code> → <code>código</code>\n"
        "  Emojis normales: ⚔️🏹🐉💎 ✅❌"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🟢 Solo ACTIVOS ({n_activos})", callback_data="bc_modo_activos")],
        [InlineKeyboardButton(f"📢 TODOS los jugadores ({total})", callback_data="bc_modo_todos")],
        [InlineKeyboardButton("⚔️ Jugadores de Alianza", callback_data="bc_modo_faccion_Alianza")],
        [InlineKeyboardButton("🏛️ Jugadores de Imperio", callback_data="bc_modo_faccion_Imperio")],
        [InlineKeyboardButton("🗡️ Jugadores de Rebeldes", callback_data="bc_modo_faccion_Rebeldes")],
        [InlineKeyboardButton("◀️ Volver al panel", callback_data="panel_volver")],
    ])
    return texto, kb


def _panel_viajes_texto_teclado():
    lineas = ["🗺️ *Panel de Tiempos de Viaje*\n"]
    lineas.append("Ajusta cuánto tarda cada tipo de desplazamiento.")
    lineas.append("_Los viajes ya en curso no se ven afectados._\n")
    lineas.append("━━━━━━━━━━━━━━━━")
    kb = []
    for clave, etiqueta, defecto, paso, minimo, maximo in _VIAJE_CAMPOS:
        valor = max(minimo, min(maximo, int(db_helper.obtener_config(clave, str(defecto)))))
        lineas.append(f"\n*{etiqueta}*\n⏱ `{_fmt_seg(valor)}` (defecto: {_fmt_seg(defecto)})")
        kb.append([
            InlineKeyboardButton(f"➖ -{paso}s", callback_data=f"pv_dec_{clave}"),
            InlineKeyboardButton(f"⏱ {_fmt_seg(valor)}",  callback_data="pv_noop"),
            InlineKeyboardButton(f"➕ +{paso}s", callback_data=f"pv_inc_{clave}"),
        ])
        kb.append([
            InlineKeyboardButton(f"➖ -{paso*5}s",  callback_data=f"pv_dec5_{clave}"),
            InlineKeyboardButton("↩️ Resetear",      callback_data=f"pv_rst_{clave}"),
            InlineKeyboardButton(f"➕ +{paso*5}s",  callback_data=f"pv_inc5_{clave}"),
        ])
        kb.append([InlineKeyboardButton("─────────────────", callback_data="pv_noop")])
    kb.append([InlineKeyboardButton("⏳ Ver Cooldowns de Zona →", callback_data="pv_open_zonas")])
    kb.append([
        InlineKeyboardButton("⚙️ Volver a Config",  callback_data="cfg_volver"),
        InlineKeyboardButton("✅ Cerrar panel",       callback_data="pv_cerrar"),
    ])
    return "\n".join(lineas), InlineKeyboardMarkup(kb)

async def cmd_panel_viajes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not _verificar_cmd(user_id, "mundo"):
        await update.effective_message.reply_text("❌ Acceso denegado.")
        return
    texto, kb = _panel_viajes_texto_teclado()
    await update.effective_message.reply_text(texto, reply_markup=kb, parse_mode="Markdown")

async def cb_panel_viajes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if not _verificar_cmd(user_id, "mundo"):
        await query.answer("❌ Sin permiso.", show_alert=True)
        return
    data = query.data  # pv_inc_clave | pv_dec_clave | pv_inc5_clave | pv_dec5_clave | pv_rst_clave | pv_noop | pv_cerrar | pv_open_zonas
    if data == "pv_noop":
        return
    if data == "pv_cerrar":
        try:
            await query.message.delete()
        except Exception:
            await query.edit_message_reply_markup(reply_markup=None)
        return
    if data == "pv_open_zonas":
        texto, kb = _panel_zonas_texto_teclado()
        try:
            await query.edit_message_text(texto, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            await query.message.reply_text(texto, reply_markup=kb, parse_mode="Markdown")
        return
    partes = data.split("_", 2)  # ['pv', 'inc'/'dec'/'inc5'/'dec5'/'rst', clave]
    if len(partes) < 3:
        return
    _, accion, clave = partes
    # Buscar metadatos de ese campo
    meta = next((x for x in _VIAJE_CAMPOS if x[0] == clave), None)
    if not meta:
        return
    _, _, defecto, paso, minimo, maximo = meta
    valor_actual = int(db_helper.obtener_config(clave, str(defecto)))
    if accion == "inc":
        nuevo = min(maximo, valor_actual + paso)
    elif accion == "dec":
        nuevo = max(minimo, valor_actual - paso)
    elif accion == "inc5":
        nuevo = min(maximo, valor_actual + paso * 5)
    elif accion == "dec5":
        nuevo = max(minimo, valor_actual - paso * 5)
    elif accion == "rst":
        nuevo = defecto
    else:
        return
    db_helper.establecer_config(clave, str(nuevo))
    texto, kb = _panel_viajes_texto_teclado()
    try:
        await query.edit_message_text(texto, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        pass


# ==================== PANEL DE COOLDOWNS DE ZONA ====================

_ZONA_CAMPOS = [
    # (clave_bd, etiqueta, defecto_s, paso_s, minimo_s, maximo_s)
    ("cooldown_zona_roja",    "🟥 Espera para salir de Zona Roja",   600,  60,  0,  86400),
    ("cooldown_zona_negra",   "⬛ Espera para salir de Zona Negra", 1800, 300,  0,  86400),
    ("cooldown_zona_amarilla","🟨 Espera para salir de Zona Amarilla",  0,  30,  0,  86400),
    ("cooldown_zona_azul",    "🟦 Espera para salir de Zona Azul",       0,  30,  0,  86400),
]

def _panel_zonas_texto_teclado():
    lineas = ["⏳ *Panel de Cooldowns de Zona*\n"]
    lineas.append("Configura cuánto tiempo debe esperar un jugador antes de poder salir de cada tipo de zona.")
    lineas.append("_Valor 0 = sin espera (salida instantánea)._\n")
    lineas.append("━━━━━━━━━━━━━━━━")
    kb = []
    for clave, etiqueta, defecto, paso, minimo, maximo in _ZONA_CAMPOS:
        valor = max(minimo, min(maximo, int(db_helper.obtener_config(clave, str(defecto)))))
        lineas.append(f"\n*{etiqueta}*\n⏳ `{_fmt_seg(valor)}` (defecto: {_fmt_seg(defecto)})")
        kb.append([
            InlineKeyboardButton(f"➖ -{_fmt_seg(paso)}", callback_data=f"pz_dec_{clave}"),
            InlineKeyboardButton(f"⏳ {_fmt_seg(valor)}",  callback_data="pz_noop"),
            InlineKeyboardButton(f"➕ +{_fmt_seg(paso)}", callback_data=f"pz_inc_{clave}"),
        ])
        kb.append([
            InlineKeyboardButton(f"➖ -{_fmt_seg(paso*5)}",  callback_data=f"pz_dec5_{clave}"),
            InlineKeyboardButton("↩️ Resetear",               callback_data=f"pz_rst_{clave}"),
            InlineKeyboardButton(f"➕ +{_fmt_seg(paso*5)}",  callback_data=f"pz_inc5_{clave}"),
        ])
        kb.append([InlineKeyboardButton("─────────────────", callback_data="pz_noop")])
    kb.append([InlineKeyboardButton("🗺️ Ver Tiempos de Viaje →", callback_data="pz_open_viajes")])
    kb.append([
        InlineKeyboardButton("⚙️ Volver a Config",  callback_data="cfg_volver"),
        InlineKeyboardButton("✅ Cerrar panel",       callback_data="pz_cerrar"),
    ])
    return "\n".join(lineas), InlineKeyboardMarkup(kb)

async def cmd_panel_zonas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not _verificar_cmd(user_id, "mundo"):
        await update.effective_message.reply_text("❌ Acceso denegado.")
        return
    texto, kb = _panel_zonas_texto_teclado()
    await update.effective_message.reply_text(texto, reply_markup=kb, parse_mode="Markdown")

async def cb_panel_zonas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if not _verificar_cmd(user_id, "mundo"):
        await query.answer("❌ Sin permiso.", show_alert=True)
        return
    data = query.data  # pz_inc_clave | pz_dec_clave | pz_inc5_clave | pz_dec5_clave | pz_rst_clave | pz_noop | pz_cerrar | pz_open_viajes
    if data == "pz_noop":
        return
    if data == "pz_cerrar":
        try:
            await query.message.delete()
        except Exception:
            await query.edit_message_reply_markup(reply_markup=None)
        return
    if data == "pz_open_viajes":
        texto, kb = _panel_viajes_texto_teclado()
        try:
            await query.edit_message_text(texto, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            await query.message.reply_text(texto, reply_markup=kb, parse_mode="Markdown")
        return
    partes = data.split("_", 2)  # ['pz', 'inc'/'dec'/'rst', clave]
    if len(partes) < 3:
        return
    _, accion, clave = partes
    meta = next((x for x in _ZONA_CAMPOS if x[0] == clave), None)
    if not meta:
        return
    _, _, defecto, paso, minimo, maximo = meta
    valor_actual = int(db_helper.obtener_config(clave, str(defecto)))
    if accion == "inc":
        nuevo = min(maximo, valor_actual + paso)
    elif accion == "dec":
        nuevo = max(minimo, valor_actual - paso)
    elif accion == "inc5":
        nuevo = min(maximo, valor_actual + paso * 5)
    elif accion == "dec5":
        nuevo = max(minimo, valor_actual - paso * 5)
    elif accion == "rst":
        nuevo = defecto
    else:
        return
    db_helper.establecer_config(clave, str(nuevo))
    texto, kb = _panel_zonas_texto_teclado()
    try:
        await query.edit_message_text(texto, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════════════
# PANEL DE CONFIGURACIÓN DEL JUEGO (/config_juego)
# Edita todos los valores de balance de forma persistente desde el panel admin.
# Los cambios se guardan en la DB y sobreviven reinicios del bot.
# ═══════════════════════════════════════════════════════════════════════════════

# ── Estado de espera del panel config ────────────────────────────────────────
_cfg_esperando: dict = {}   # user_id → {"clave": str, "cat_idx": int}
_cfg_am_estado: dict = {}   # user_id → {"tipo": str}  (acción masiva esperando cantidad)


def _es_admin_config(user_id: int) -> bool:
    """Solo superadmin y admins nivel 1+ pueden usar el panel de config."""
    try:
        return _es_superadmin(user_id) or _get_nivel_admin(user_id) >= 1
    except Exception:
        return _es_superadmin(user_id)


def _cfg_val_display(item: dict) -> str:
    """Formatea el valor actual de forma legible."""
    val  = item["valor_actual"]
    tipo = item["tipo"]
    if tipo == "bool":
        return "✅ Sí" if val else "❌ No"
    return str(val)


# ── Menú de categorías ────────────────────────────────────────────────────────
def _menu_categorias_cfg() -> tuple:
    import config_db as _cdb
    cats    = list(_cdb.get_categories().keys())
    botones = []
    fila    = []
    for i, cat in enumerate(cats):
        fila.append(InlineKeyboardButton(cat, callback_data=f"cfg_cat_{i}"))
        if len(fila) == 2:
            botones.append(fila)
            fila = []
    if fila:
        botones.append(fila)
    botones.append([
        InlineKeyboardButton("💱 Economía & Tiendas", callback_data="cfg_economia"),
        InlineKeyboardButton("🗺️ Viajes & Zonas",     callback_data="cfg_viajes"),
    ])
    botones.append([
        InlineKeyboardButton("🌍 Acciones Masivas", callback_data="cfg_acciones"),
        InlineKeyboardButton("⚡ Eventos Rápidos",  callback_data="cfg_eventos"),
    ])
    botones.append([
        InlineKeyboardButton("🛠️ Editor Maestro",  callback_data="cfg_editor_sa"),
        InlineKeyboardButton("✨ Items Custom",     callback_data="cfg_items_custom"),
    ])
    botones.append([InlineKeyboardButton("❌ Cerrar", callback_data="cfg_cerrar")])
    texto = (
        "🎛️ <b>CONFIGURACIÓN PERMANENTE DEL JUEGO</b>\n\n"
        "Cambios guardados en DB — sobreviven reinicios del bot.\n"
        "• <b>➕/➖</b> ajusta en pasos · <b>✏️</b> escribe valor exacto · <b>🔄</b> restaura default\n\n"
        "Elige una categoría:"
    )
    return texto, InlineKeyboardMarkup(botones)


# ── Menú de valores de una categoría ─────────────────────────────────────────
def _menu_valores_cfg(cat_idx: int) -> tuple:
    import config_db as _cdb
    cats       = _cdb.get_categories()
    cat_nombres = list(cats.keys())
    if cat_idx >= len(cat_nombres):
        return "Categoría no encontrada.", None
    cat   = cat_nombres[cat_idx]
    items = cats[cat]
    texto = f"🎛️ <b>{cat}</b>\n\n"
    botones = []
    for item in items:
        clave   = item["clave"]
        tipo    = item["tipo"]
        step    = item.get("step", 1)
        label   = item["label"]
        display = _cfg_val_display(item)
        texto  += f"• <b>{label}</b> — <code>{display}</code>\n"
        if tipo == "bool":
            val = item["valor_actual"]
            txt = f"❌ Desactivar" if val else "✅ Activar"
            botones.append([InlineKeyboardButton(f"{txt}: {label[:28]}", callback_data=f"cfg_tog_{cat_idx}_{clave}")])
        else:
            botones.append([
                InlineKeyboardButton(f"➖{step}",          callback_data=f"cfg_m_{cat_idx}_{clave}"),
                InlineKeyboardButton("🔢→0",                callback_data=f"cfg_zero_{cat_idx}_{clave}"),
                InlineKeyboardButton(f"💾 Guardar",        callback_data=f"cfg_edit_{cat_idx}_{clave}"),
                InlineKeyboardButton(f"➕{step}",          callback_data=f"cfg_p_{cat_idx}_{clave}"),
                InlineKeyboardButton("🔄 Reset",           callback_data=f"cfg_rst_{cat_idx}_{clave}"),
            ])
        texto += "\n"
    botones.append([InlineKeyboardButton("◀️ Categorías", callback_data="cfg_volver")])
    return texto, InlineKeyboardMarkup(botones)


# ── Menú de acciones masivas ─────────────────────────────────────────────────
def _menu_acciones_masivas() -> tuple:
    botones = [
        [InlineKeyboardButton("💰 Ajuste % Oro",      callback_data="cfg_am_oro"),
         InlineKeyboardButton("💎 Ajuste % Eternium",  callback_data="cfg_am_eternium")],
        [InlineKeyboardButton("⭐ Ajuste % XP",        callback_data="cfg_am_xp"),
         InlineKeyboardButton("❤️ Ajuste % HP",        callback_data="cfg_am_hp")],
        [InlineKeyboardButton("─── Dar cantidad fija a todos ───", callback_data="cfg_noop")],
        [InlineKeyboardButton("🎁 Dar Oro",            callback_data="cfg_dm_oro"),
         InlineKeyboardButton("🎁 Dar Eternium",       callback_data="cfg_dm_eternium")],
        [InlineKeyboardButton("🎁 Dar Créditos",       callback_data="cfg_dm_creditos"),
         InlineKeyboardButton("🎁 Dar XP",             callback_data="cfg_dm_xp")],
        [InlineKeyboardButton("◀️ Volver",              callback_data="cfg_volver")],
    ]
    texto = (
        "🌍 <b>ACCIONES MASIVAS</b>\n\n"
        "<b>Ajuste % masivo</b> — sube o baja un % del recurso actual de "
        "<u>todos</u> los jugadores registrados.\n"
        "Ej: +10% Oro → cada jugador recibe el 10% de su oro actual.\n\n"
        "<b>Dar masivo</b> — añade una cantidad fija a <u>todos</u> los jugadores.\n"
        "Escribe la cantidad cuando se te pida.\n\n"
        "⚠️ Estas acciones son inmediatas e irreversibles."
    )
    return texto, InlineKeyboardMarkup(botones)


# ── Menú de selección de % para ajuste masivo ────────────────────────────────
def _menu_ajuste_pct(tipo: str) -> tuple:
    nombres = {"oro": "💰 Oro", "eternium": "💎 Eternium", "xp": "⭐ XP", "hp": "❤️ HP"}
    nombre  = nombres.get(tipo, tipo)
    t = tipo
    botones = [
        [InlineKeyboardButton("+5%",  callback_data=f"cfg_amx_{t}_p5"),
         InlineKeyboardButton("+10%", callback_data=f"cfg_amx_{t}_p10"),
         InlineKeyboardButton("+25%", callback_data=f"cfg_amx_{t}_p25"),
         InlineKeyboardButton("+50%", callback_data=f"cfg_amx_{t}_p50")],
        [InlineKeyboardButton("-5%",  callback_data=f"cfg_amx_{t}_m5"),
         InlineKeyboardButton("-10%", callback_data=f"cfg_amx_{t}_m10"),
         InlineKeyboardButton("-25%", callback_data=f"cfg_amx_{t}_m25"),
         InlineKeyboardButton("-50%", callback_data=f"cfg_amx_{t}_m50")],
        [InlineKeyboardButton("◀️ Volver", callback_data="cfg_acciones")],
    ]
    texto = (
        f"💱 <b>Ajuste masivo — {nombre}</b>\n\n"
        f"Elige el porcentaje a aplicar sobre el recurso actual de <u>todos</u> los jugadores:"
    )
    return texto, InlineKeyboardMarkup(botones)


# ── Menú de confirmación de ajuste masivo ────────────────────────────────────
def _menu_ajuste_confirm(tipo: str, signo: str, pct: int) -> tuple:
    pct_val = pct if signo == "p" else -pct
    nombres = {"oro": "Oro", "eternium": "Eternium", "xp": "XP", "hp": "HP"}
    t = tipo
    botones = [
        [InlineKeyboardButton(f"✅ Confirmar {pct_val:+d}% {nombres.get(tipo, tipo)}",
                              callback_data=f"cfg_amok_{t}_{signo}{pct}")],
        [InlineKeyboardButton("❌ Cancelar", callback_data=f"cfg_am_{tipo}")],
    ]
    texto = (
        f"⚠️ <b>CONFIRMAR AJUSTE MASIVO</b>\n\n"
        f"Tipo: <b>{nombres.get(tipo, tipo)}</b> | Cambio: <b>{pct_val:+d}%</b>\n\n"
        f"Esto modificará el recurso de <u>TODOS</u> los jugadores registrados.\n"
        f"¿Confirmas?"
    )
    return texto, InlineKeyboardMarkup(botones)


# ── Menú de eventos rápidos ───────────────────────────────────────────────────
def _menu_eventos_rapidos() -> tuple:
    import config_db as _cdb
    xp_on   = _cdb.get("evento_bonus_xp_activo")
    oro_on  = _cdb.get("evento_bonus_oro_activo")
    xp_mult = _cdb.get("evento_bonus_xp_mult")
    or_mult = _cdb.get("evento_bonus_oro_mult")
    txt_xp  = "✅ ACTIVO" if xp_on  else "❌ Desactivado"
    txt_oro = "✅ ACTIVO" if oro_on else "❌ Desactivado"
    botones = [
        [InlineKeyboardButton(
            f"{'❌ Desactivar' if xp_on  else '✅ Activar'} Doble XP  (×{xp_mult})",
            callback_data="cfg_ev_xp_0" if xp_on else "cfg_ev_xp_1"
        )],
        [InlineKeyboardButton(
            f"{'❌ Desactivar' if oro_on else '✅ Activar'} Doble Oro (×{or_mult})",
            callback_data="cfg_ev_oro_0" if oro_on else "cfg_ev_oro_1"
        )],
        [InlineKeyboardButton("◀️ Categorías", callback_data="cfg_volver")],
    ]
    texto = (
        "⚡ <b>EVENTOS RÁPIDOS</b>\n\n"
        f"Doble XP:  {txt_xp}  (multiplicador ×{xp_mult})\n"
        f"Doble Oro: {txt_oro} (multiplicador ×{or_mult})\n\n"
        "Pulsa para activar o desactivar al instante.\n"
        "Los multiplicadores se editan en <b>⏰ Eventos Auto</b>."
    )
    return texto, InlineKeyboardMarkup(botones)


# ── Menú: Editor Maestro ──────────────────────────────────────────────────────
def _menu_editor_sa() -> tuple:
    botones = [
        [InlineKeyboardButton("📊 Ver Config Actual",  callback_data="cfg_esa_numeros")],
        [InlineKeyboardButton("👤 Editar Jugador",     callback_data="cfg_esa_jugador"),
         InlineKeyboardButton("🐲 Editar Monstruo",   callback_data="cfg_esa_monstruo")],
        [InlineKeyboardButton("⚔️ Editar Arma",       callback_data="cfg_esa_arma"),
         InlineKeyboardButton("🛡️ Editar Armadura",   callback_data="cfg_esa_armadura")],
        [InlineKeyboardButton("💰 Editar Precio",     callback_data="cfg_esa_precio"),
         InlineKeyboardButton("💱 Editar Tasas",      callback_data="cfg_esa_tasas")],
        [InlineKeyboardButton("⭐ Fórmula XP",        callback_data="cfg_esa_xp"),
         InlineKeyboardButton("🧬 Stats Clases",      callback_data="cfg_esa_clase")],
        [InlineKeyboardButton("🧪 Editar Poción",     callback_data="cfg_esa_pocion"),
         InlineKeyboardButton("🪨 Editar Material",   callback_data="cfg_esa_material")],
        [InlineKeyboardButton("◀️ Volver",            callback_data="cfg_volver")],
    ]
    texto = (
        "🛠️ <b>EDITOR MAESTRO</b>\n\n"
        "• <b>📊 Ver Config Actual</b> — muestra tasas, fórmula XP y stats de clases\n"
        "• <b>👤 Editar Jugador</b> — busca un jugador y edita HP, ATK, DEF, XP, oro…\n"
        "• <b>🐲 Editar Monstruo</b> — busca y edita stats de cualquier monstruo\n"
        "• <b>⚔️ Editar Arma</b> — busca y edita daño, crítico, velocidad, precio\n"
        "• <b>🛡️ Editar Armadura</b> — busca y edita defensa, resistencia, precio\n"
        "• <b>💰 Editar Precio</b> — cambia el precio de cualquier ítem\n"
        "• <b>💱 Tasas de Cambio</b> — modifica tasas del banco\n"
        "• <b>⭐ Fórmula XP</b> — ajusta base y exponente de progresión\n"
        "• <b>🧬 Stats Clases</b> — edita HP/ATK/DEF base por clase\n"
        "• <b>🧪 Editar Poción</b> — busca y edita cualquier poción (efecto, precio, nivel)\n"
        "• <b>🪨 Editar Material</b> — busca y edita cualquier material (valor crafteo, precio venta)\n\n"
        "Pulsa cada botón para ver el comando y lanzar el asistente."
    )
    return texto, InlineKeyboardMarkup(botones)


# ── Menú: Items Custom ────────────────────────────────────────────────────────
def _menu_items_custom() -> tuple:
    botones = [
        [InlineKeyboardButton("⚔️ Crear Arma Custom",      callback_data="cfg_ic_arma"),
         InlineKeyboardButton("🛡️ Crear Armadura Custom",  callback_data="cfg_ic_armadura")],
        [InlineKeyboardButton("📋 Ver Mis Items Custom",   callback_data="cfg_ic_listar")],
        [InlineKeyboardButton("🗑️ Borrar Item Custom",    callback_data="cfg_ic_borrar")],
        [InlineKeyboardButton("◀️ Volver",                callback_data="cfg_volver")],
    ]
    texto = (
        "✨ <b>ITEMS CUSTOM</b>\n\n"
        "Crea armas y armaduras únicas que se cargan en el juego al arrancar.\n\n"
        "• <b>⚔️ Crear Arma</b> — asistente: nombre, daño, crítico, velocidad, precio\n"
        "• <b>🛡️ Crear Armadura</b> — asistente: nombre, defensa, resistencia, precio\n"
        "• <b>📋 Ver Items</b> — lista todos los items personalizados creados\n"
        "• <b>🗑️ Borrar Item</b> — elimina un item por su ID\n\n"
        "Los asistentes son conversacionales — pulsa el botón para iniciarlos."
    )
    return texto, InlineKeyboardMarkup(botones)


# ── Helpers de ejecución de acciones masivas ─────────────────────────────────
async def _ejecutar_ajuste_global_inline(tipo: str, pct: float) -> int:
    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()
    c.execute("SELECT user_id FROM jugadores")
    uids = [r[0] for r in c.fetchall()]
    conn.close()
    afectados = 0
    for uid in uids:
        try:
            if tipo in ("oro", "eternium"):
                saldo  = economia.obtener_saldo(uid, tipo)
                delta  = int(saldo * pct / 100)
                if delta != 0:
                    economia.modificar_saldo(uid, tipo, delta, "ajuste_global_panel")
                    afectados += 1
            elif tipo == "xp":
                jug = db_helper.obtener_jugador(uid)
                if jug:
                    delta = int(jug["experiencia"] * pct / 100)
                    if delta != 0:
                        db_helper.actualizar_jugador(uid, experiencia=max(0, jug["experiencia"] + delta))
                        afectados += 1
            elif tipo == "hp":
                jug = db_helper.obtener_jugador(uid)
                if jug:
                    delta   = int(jug["hp_max"] * pct / 100)
                    nuevo   = max(1, min(jug["hp_actual"] + delta, jug["hp_max"]))
                    db_helper.actualizar_jugador(uid, hp_actual=nuevo)
                    afectados += 1
        except Exception:
            pass
    return afectados


async def _ejecutar_dar_masivo_inline(tipo: str, cantidad: int) -> int:
    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()
    c.execute("SELECT user_id FROM jugadores")
    uids = [r[0] for r in c.fetchall()]
    conn.close()
    afectados = 0
    for uid in uids:
        try:
            if tipo == "xp":
                jug = db_helper.obtener_jugador(uid)
                if jug:
                    db_helper.actualizar_jugador(uid, experiencia=max(0, jug["experiencia"] + cantidad))
            else:
                economia.modificar_saldo(uid, tipo, cantidad, "dar_masivo_panel")
            db_helper.agregar_notificacion(uid, f"🎁 Regalo global del admin: +{cantidad} {tipo}.")
            afectados += 1
        except Exception:
            pass
    return afectados


# ── Comando /config_juego ─────────────────────────────────────────────────────
async def cmd_config_juego(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not _es_admin_config(user_id):
        await update.message.reply_text("⛔ Sin permisos.")
        return
    texto, kb = _menu_categorias_cfg()
    await update.message.reply_text(texto, reply_markup=kb, parse_mode="HTML")


# ── Callback principal del panel de configuración ────────────────────────────
async def cb_config_juego(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    user_id = query.from_user.id
    data    = query.data

    # Ignorar el botón separador sin permisos check (es solo estético)
    if data == "cfg_noop":
        await query.answer()
        return

    await query.answer()

    if not _es_admin_config(user_id):
        await query.answer("⛔ Sin permisos.", show_alert=True)
        return

    async def _edit(texto, kb=None):
        try:
            await query.edit_message_text(texto, reply_markup=kb, parse_mode="HTML")
        except Exception:
            pass

    # ── Navegación básica ─────────────────────────────────────────────────────
    if data == "cfg_volver":
        texto, kb = _menu_categorias_cfg()
        await _edit(texto, kb)
        return

    if data == "cfg_cerrar":
        await _edit("🎛️ Panel de configuración cerrado.")
        return

    if data == "cfg_acciones":
        texto, kb = _menu_acciones_masivas()
        await _edit(texto, kb)
        return

    if data == "cfg_eventos":
        texto, kb = _menu_eventos_rapidos()
        await _edit(texto, kb)
        return

    # ── Eventos rápidos (toggle) ──────────────────────────────────────────────
    if data.startswith("cfg_ev_xp_"):
        import config_db as _cdb
        val = int(data[-1])
        _cdb.set("evento_bonus_xp_activo", val)
        texto, kb = _menu_eventos_rapidos()
        await _edit(texto, kb)
        await query.answer(f"Doble XP {'✅ activado' if val else '❌ desactivado'}", show_alert=False)
        return

    if data.startswith("cfg_ev_oro_"):
        import config_db as _cdb
        val = int(data[-1])
        _cdb.set("evento_bonus_oro_activo", val)
        texto, kb = _menu_eventos_rapidos()
        await _edit(texto, kb)
        await query.answer(f"Doble Oro {'✅ activado' if val else '❌ desactivado'}", show_alert=False)
        return

    # ── Selección de categoría ────────────────────────────────────────────────
    if data.startswith("cfg_cat_"):
        try:
            cat_idx = int(data[len("cfg_cat_"):])
        except (ValueError, IndexError):
            return
        texto, kb = _menu_valores_cfg(cat_idx)
        await _edit(texto, kb)
        return

    # ── Toggle de valor bool ──────────────────────────────────────────────────
    # cfg_tog_{cat_idx}_{clave}
    if data.startswith("cfg_tog_"):
        resto  = data[len("cfg_tog_"):]
        partes = resto.split("_", 1)
        if len(partes) < 2:
            return
        try:
            cat_idx = int(partes[0])
        except ValueError:
            return
        clave = partes[1]
        import config_db as _cdb
        nuevo = 0 if _cdb.get(clave) else 1
        _cdb.set(clave, nuevo)
        schema = _cdb.CONFIG_SCHEMA.get(clave, {})
        texto, kb = _menu_valores_cfg(cat_idx)
        await _edit(texto, kb)
        await query.answer(f"💾 Guardado — {'✅ Activado' if nuevo else '❌ Desactivado'}: {schema.get('label', clave)[:35]}", show_alert=False)
        return

    # ── Step ± ───────────────────────────────────────────────────────────────
    # cfg_p_{cat_idx}_{clave}  /  cfg_m_{cat_idx}_{clave}
    if data.startswith("cfg_p_") or data.startswith("cfg_m_"):
        es_suma = data.startswith("cfg_p_")
        resto   = data[6:]          # quita "cfg_p_" o "cfg_m_"
        partes  = resto.split("_", 1)
        if len(partes) < 2:
            return
        try:
            cat_idx = int(partes[0])
        except ValueError:
            return
        clave = partes[1]
        import config_db as _cdb
        schema  = _cdb.CONFIG_SCHEMA.get(clave, {})
        if not schema:
            return
        step    = schema.get("step", 1)
        val_act = _cdb.get(clave)
        if schema["tipo"] == "int":
            nuevo = int(val_act) + (step if es_suma else -step)
        else:
            nuevo = round(float(val_act) + (step if es_suma else -step), 6)
        _cdb.set(clave, nuevo)
        texto, kb = _menu_valores_cfg(cat_idx)
        await _edit(texto, kb)
        await query.answer(f"💾 Guardado — {schema.get('label', clave)[:30]}: {nuevo}", show_alert=False)
        return

    # ── Reset a default ───────────────────────────────────────────────────────
    # cfg_rst_{cat_idx}_{clave}
    if data.startswith("cfg_rst_"):
        resto  = data[len("cfg_rst_"):]
        partes = resto.split("_", 1)
        if len(partes) < 2:
            return
        try:
            cat_idx = int(partes[0])
        except ValueError:
            return
        clave = partes[1]
        import config_db as _cdb
        schema  = _cdb.CONFIG_SCHEMA.get(clave, {})
        default = schema.get("default")
        _cdb.set(clave, default)
        texto, kb = _menu_valores_cfg(cat_idx)
        await _edit(texto, kb)
        await query.answer(f"💾 Guardado — 🔄 Restaurado al valor original: {default}", show_alert=False)
        return

    # ── Poner a cero ──────────────────────────────────────────────────────────
    # cfg_zero_{cat_idx}_{clave}
    if data.startswith("cfg_zero_"):
        resto  = data[len("cfg_zero_"):]
        partes = resto.split("_", 1)
        if len(partes) < 2:
            return
        try:
            cat_idx = int(partes[0])
        except ValueError:
            return
        clave = partes[1]
        import config_db as _cdb
        schema = _cdb.CONFIG_SCHEMA.get(clave, {})
        if not schema:
            return
        cero = 0.0 if schema.get("tipo") == "float" else 0
        _cdb.set(clave, cero)
        texto, kb = _menu_valores_cfg(cat_idx)
        await _edit(texto, kb)
        await query.answer(f"💾 Guardado — {schema.get('label', clave)[:35]} = 0", show_alert=False)
        return

    # ── Edición por texto ─────────────────────────────────────────────────────
    # cfg_edit_{cat_idx}_{clave}
    if data.startswith("cfg_edit_"):
        resto  = data[len("cfg_edit_"):]
        partes = resto.split("_", 1)
        if len(partes) < 2:
            return
        try:
            cat_idx = int(partes[0])
        except ValueError:
            return
        clave = partes[1]
        import config_db as _cdb
        schema = _cdb.CONFIG_SCHEMA.get(clave)
        if not schema:
            return
        val_actual = _cdb.get(clave)
        tipo_desc  = {"int": "número entero", "float": "número decimal", "bool": "1=sí / 0=no"}.get(schema["tipo"], "valor")
        _cfg_esperando[user_id] = {"clave": clave, "cat_idx": cat_idx}
        kb_cancel = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancelar edición", callback_data="cfg_cancel")]])
        await _edit(
            f"✏️ <b>Editando:</b> {schema['label']}\n\n"
            f"Categoría: {schema['cat']}\n"
            f"Valor actual: <code>{val_actual}</code>\n"
            f"Default: <code>{schema.get('default')}</code>\n"
            f"Tipo esperado: {tipo_desc}\n\n"
            f"Escribe el nuevo valor ahora (o pulsa ❌ para cancelar):",
            kb_cancel
        )
        return

    # ── Economía & Tiendas — abre economia_panel inline ─────────────────────────
    if data == "cfg_economia":
        try:
            import economia_panel as _ep
            await _ep._abrir_panel(update, context)
        except Exception as e:
            kb_v = InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Volver", callback_data="cfg_volver")]])
            await _edit(
                f"❌ No se pudo abrir el panel de economía: {e}

"
                "Usa el comando /panel_economia directamente.",
                kb_v
            )
        return

    # ── Viajes & Zonas — abre paneles de viajes y zonas inline ───────────────
    if data == "cfg_viajes":
        texto, kb_v = _panel_viajes_texto_teclado()
        await _edit(texto, kb_v)
        return

    if data == "cfg_cancel":
        _cfg_esperando.pop(user_id, None)
        texto, kb = _menu_categorias_cfg()
        await _edit(texto, kb)
        return

    # ── Acciones masivas: selección de tipo (ajuste %) ───────────────────────
    # cfg_am_{tipo}  (oro / eternium / xp / hp)
    if data.startswith("cfg_am_") and not data.startswith("cfg_amx_") and not data.startswith("cfg_amok_"):
        tipo = data[len("cfg_am_"):]
        if tipo in ("oro", "eternium", "xp", "hp"):
            texto, kb = _menu_ajuste_pct(tipo)
            await _edit(texto, kb)
        return

    # cfg_amx_{tipo}_{signo}{pct}  — seleccionó un porcentaje → confirmar
    if data.startswith("cfg_amx_"):
        resto  = data[len("cfg_amx_"):]
        partes = resto.split("_", 1)
        if len(partes) < 2:
            return
        tipo = partes[0]
        sp   = partes[1]          # p10, m25, …
        signo = sp[0]
        try:
            pct = int(sp[1:])
        except ValueError:
            return
        texto, kb = _menu_ajuste_confirm(tipo, signo, pct)
        await _edit(texto, kb)
        return

    # cfg_amok_{tipo}_{signo}{pct}  — confirmado → ejecutar
    if data.startswith("cfg_amok_"):
        resto  = data[len("cfg_amok_"):]
        partes = resto.split("_", 1)
        if len(partes) < 2:
            return
        tipo  = partes[0]
        sp    = partes[1]
        signo = sp[0]
        try:
            pct = int(sp[1:])
        except ValueError:
            return
        pct_val = pct if signo == "p" else -pct
        await _edit(f"⏳ Aplicando {pct_val:+d}% de <b>{tipo}</b> a todos los jugadores…")
        afectados = await _ejecutar_ajuste_global_inline(tipo, pct_val)
        nombres   = {"oro": "Oro", "eternium": "Eternium", "xp": "XP", "hp": "HP"}
        kb_volver = InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ Acciones Masivas", callback_data="cfg_acciones"),
            InlineKeyboardButton("🏠 Inicio",           callback_data="cfg_volver"),
        ]])
        await _edit(
            f"✅ <b>Ajuste masivo aplicado</b>\n\n"
            f"Tipo: <b>{nombres.get(tipo, tipo)}</b> | Cambio: <b>{pct_val:+d}%</b>\n"
            f"Jugadores afectados: <b>{afectados}</b>",
            kb_volver
        )
        return

    # ── Dar masivo: selección de tipo (pide cantidad por texto) ──────────────
    # cfg_dm_{tipo}
    if data.startswith("cfg_dm_"):
        tipo = data[len("cfg_dm_"):]
        if tipo not in ("oro", "eternium", "creditos", "xp"):
            return
        _cfg_am_estado[user_id] = {"tipo": tipo}
        nombres = {"oro": "💰 Oro", "eternium": "💎 Eternium", "creditos": "💳 Créditos", "xp": "⭐ XP"}
        kb_c    = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancelar", callback_data="cfg_cancel_am")]])
        await _edit(
            f"🎁 <b>Dar {nombres.get(tipo, tipo)} a TODOS los jugadores</b>\n\n"
            f"Escribe la cantidad que recibirá cada jugador:",
            kb_c
        )
        return

    if data == "cfg_cancel_am":
        _cfg_am_estado.pop(user_id, None)
        texto, kb = _menu_acciones_masivas()
        await _edit(texto, kb)
        return

    # ── Editor Maestro: menú principal ───────────────────────────────────────
    if data == "cfg_editor_sa":
        texto, kb = _menu_editor_sa()
        await _edit(texto, kb)
        return

    # ── Editor Maestro: Ver Config Actual (no es wizard, responde directo) ───
    if data == "cfg_esa_numeros":
        try:
            import editor_maestro as _em
            await _em.cmd_sa_numeros(update, context)
        except ImportError:
            await query.message.reply_text(
                "📊 Para ver la configuración actual usa el comando:\n\n"
                "/sa_numeros"
            )
        return

    # ── Editor Maestro: wizards conversacionales (lanza el comando) ──────────
    _WIZARDS_ESA = {
        "cfg_esa_jugador":  ("/sa_jugador",  "👤 Editar Jugador",
                             "buscar un jugador por nombre o ID"),
        "cfg_esa_monstruo": ("/sa_monstruo", "🐲 Editar Monstruo",
                             "buscar un monstruo por nombre"),
        "cfg_esa_arma":     ("/sa_arma",     "⚔️ Editar Arma",
                             "buscar un arma por nombre"),
        "cfg_esa_armadura": ("/sa_armadura", "🛡️ Editar Armadura",
                             "buscar una armadura por nombre"),
        "cfg_esa_precio":   ("/sa_precio",   "💰 Editar Precio",
                             "buscar un ítem para cambiar su precio"),
        "cfg_esa_tasas":    ("/sa_tasas",    "💱 Editar Tasas",
                             "elegir la tasa que quieres modificar"),
        "cfg_esa_xp":       ("/sa_xp",       "⭐ Fórmula XP",
                             "elegir si ajustas base, exponente o un nivel concreto"),
        "cfg_esa_clase":    ("/sa_clase",    "🧬 Stats Clases",
                             "elegir la clase que quieres editar"),
        "cfg_esa_pocion":   ("/sa_pocion",   "🧪 Editar Poción",
                             "el nombre o ID de la poción que quieres editar"),
        "cfg_esa_material": ("/sa_material", "🪨 Editar Material",
                             "el nombre o ID del material que quieres editar"),
    }
    if data in _WIZARDS_ESA:
        cmd, titulo, prompt = _WIZARDS_ESA[data]
        kb_volver = InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ Editor Maestro", callback_data="cfg_editor_sa")
        ]])
        await query.message.reply_text(
            f"🛠️ <b>{titulo}</b>\n\n"
            f"Escribe en el chat el siguiente comando para iniciar el asistente "
            f"(te pedirá {prompt}):\n\n"
            f"<code>{cmd}</code>\n\n"
            f"<i>El asistente es paso a paso — escribe /cancelar para salir en cualquier momento.</i>",
            parse_mode="HTML",
            reply_markup=kb_volver
        )
        return

    # ── Items Custom: menú principal ─────────────────────────────────────────
    if data == "cfg_items_custom":
        texto, kb = _menu_items_custom()
        await _edit(texto, kb)
        return

    # ── Items Custom: Ver lista (no es wizard, responde directo) ─────────────
    if data == "cfg_ic_listar":
        try:
            import crear_items as _ci
            await _ci.cmd_mis_items_custom(update, context)
        except ImportError:
            await query.message.reply_text(
                "📋 Para ver tus items personalizados usa:\n\n"
                "/mis_items_custom"
            )
        return

    # ── Items Custom: wizards conversacionales ────────────────────────────────
    _WIZARDS_IC = {
        "cfg_ic_arma":     ("/crear_arma",     "⚔️ Crear Arma Custom",
                            "el nombre del arma para comenzar"),
        "cfg_ic_armadura": ("/crear_armadura",  "🛡️ Crear Armadura Custom",
                            "el nombre de la armadura para comenzar"),
        "cfg_ic_borrar":   ("/borrar_item_custom <id>", "🗑️ Borrar Item Custom",
                            "el ID del item a eliminar (lo ves en /mis_items_custom)"),
    }
    if data in _WIZARDS_IC:
        cmd, titulo, prompt = _WIZARDS_IC[data]
        kb_volver = InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ Items Custom", callback_data="cfg_items_custom")
        ]])
        await query.message.reply_text(
            f"✨ <b>{titulo}</b>\n\n"
            f"Escribe en el chat el siguiente comando para iniciar:\n\n"
            f"<code>{cmd}</code>\n\n"
            f"<i>Te pedirá {prompt}.</i>",
            parse_mode="HTML",
            reply_markup=kb_volver
        )
        return


# ── Receptor de texto del panel config ───────────────────────────────────────
async def _cfg_recibir_texto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # ── Dar masivo (esperando cantidad por texto) ─────────────────────────────
    if user_id in _cfg_am_estado:
        if not _es_admin_config(user_id):
            _cfg_am_estado.pop(user_id, None)
            return
        estado = _cfg_am_estado.pop(user_id)
        tipo   = estado["tipo"]
        try:
            cantidad = int(float(update.message.text.strip()))
            if cantidad <= 0:
                raise ValueError
        except (ValueError, TypeError):
            await update.message.reply_text(
                "❌ Cantidad inválida. Debe ser un número entero positivo.\n"
                "Usa /config_juego para intentarlo de nuevo."
            )
            return
        afectados = await _ejecutar_dar_masivo_inline(tipo, cantidad)
        nombres   = {"oro": "Oro", "eternium": "Eternium", "creditos": "Créditos del Vacío", "xp": "XP"}
        await update.message.reply_text(
            f"✅ <b>Dar masivo completado</b>\n\n"
            f"+{cantidad:,} <b>{nombres.get(tipo, tipo)}</b> enviado a <b>{afectados}</b> jugadores.\n"
            f"Todos han recibido una notificación en el juego.",
            parse_mode="HTML"
        )
        return

    # ── Edición de valor de config ────────────────────────────────────────────
    if user_id not in _cfg_esperando:
        return
    if not _es_admin_config(user_id):
        _cfg_esperando.pop(user_id, None)
        return

    estado      = _cfg_esperando.pop(user_id)
    clave       = estado["clave"]
    cat_idx     = estado["cat_idx"]
    texto_nuevo = update.message.text.strip()

    import config_db as _cdb
    schema = _cdb.CONFIG_SCHEMA.get(clave, {})
    tipo   = schema.get("tipo", "str")

    try:
        if tipo == "int":
            valor_validado = int(float(texto_nuevo))
        elif tipo == "float":
            valor_validado = float(texto_nuevo)
        elif tipo == "bool":
            valor_validado = 1 if texto_nuevo.lower() in ("1", "true", "si", "sí", "yes") else 0
        else:
            valor_validado = texto_nuevo
    except (ValueError, TypeError):
        await update.message.reply_text(
            f"❌ Valor inválido para «{schema.get('label', clave)}».\n"
            f"Se esperaba: {tipo}. Usa /config_juego para intentarlo de nuevo."
        )
        return

    ok = _cdb.set(clave, valor_validado)
    if ok:
        await update.message.reply_text(
            f"✅ <b>{schema.get('label', clave)}</b>\n"
            f"Nuevo valor: <code>{valor_validado}</code>\n"
            f"Cambio activo de inmediato y guardado permanentemente.",
            parse_mode="HTML"
        )
        try:
            texto_cat, kb_cat = _menu_valores_cfg(cat_idx)
            await update.message.reply_text(texto_cat, reply_markup=kb_cat, parse_mode="HTML")
        except Exception:
            pass
    else:
        await update.message.reply_text("❌ Error al guardar en la base de datos. Inténtalo de nuevo.")


def registrar_handlers(app):
    # Superadmin exclusivos
    app.add_handler(CommandHandler("superadmin_mi_id",         cmd_superadmin_mi_id))
    app.add_handler(CommandHandler("superadmin_crear_admin",   cmd_superadmin_crear_admin))
    app.add_handler(CommandHandler("superadmin_editar_admin",  cmd_superadmin_editar_admin))
    app.add_handler(CommandHandler("superadmin_quitar_admin",  cmd_superadmin_quitar_admin))
    app.add_handler(CommandHandler("superadmin_lista_admins",  cmd_superadmin_lista_admins))
    # Sistema de permisos granulares (todos los perm_*)
    app.add_handler(CallbackQueryHandler(cb_perm_toggle, pattern="^perm_"))

    # Modo dios (nivel 2)
    app.add_handler(CommandHandler("dios_activar",    cmd_dios_activar))
    app.add_handler(CommandHandler("dios_desactivar", cmd_dios_desactivar))
    app.add_handler(CommandHandler("dios_subir_nivel",cmd_dios_subir_nivel))
    app.add_handler(CommandHandler("dios_max_stats",  cmd_dios_max_stats))
    app.add_handler(CommandHandler("dios_recolectar", cmd_dios_recolectar))

    # Dar/quitar monedas (nivel 1+)
    app.add_handler(CommandHandler("dar_oro",         cmd_dar_oro))
    app.add_handler(CommandHandler("quitar_oro",      cmd_quitar_oro))
    app.add_handler(CommandHandler("dar_eternium",    cmd_dar_eternium))
    app.add_handler(CommandHandler("quitar_eternium", cmd_quitar_eternium))
    app.add_handler(CommandHandler("dar_creditos",    cmd_dar_creditos))
    app.add_handler(CommandHandler("quitar_creditos", cmd_quitar_creditos))
    app.add_handler(CommandHandler("dar_experiencia", cmd_dar_experiencia))

    # Dar/quitar objetos
    app.add_handler(CommandHandler("dar_objeto",      cmd_dar_objeto))
    app.add_handler(CommandHandler("quitar_objeto",   cmd_quitar_objeto))
    app.add_handler(CommandHandler("premios_entregar",cmd_premios_entregar))

    # Gestión de jugadores
    app.add_handler(CommandHandler("ver_inventario",   cmd_ver_inventario))
    app.add_handler(CommandHandler("ver_estadisticas", cmd_ver_estadisticas))
    app.add_handler(CommandHandler("cambiar_nivel",    cmd_cambiar_nivel))
    app.add_handler(CommandHandler("cambiar_clase",    cmd_cambiar_clase))
    app.add_handler(CommandHandler("cambiar_faccion",  cmd_cambiar_faccion))
    app.add_handler(CommandHandler("revivir",          cmd_revivir))
    app.add_handler(CommandHandler("reset_actividad",  cmd_reset_actividad))
    app.add_handler(CommandHandler("marcar",           cmd_marcar))
    app.add_handler(CommandHandler("desmarcar",        cmd_desmarcar))
    app.add_handler(CommandHandler("banear",           cmd_banear))
    app.add_handler(CommandHandler("desbanear",        cmd_desbanear))
    app.add_handler(CommandHandler("silenciar",        cmd_silenciar))
    app.add_handler(CommandHandler("desilenciar",      cmd_desilenciar))
    app.add_handler(CommandHandler("resetear_cooldowns",cmd_resetear_cooldowns))
    app.add_handler(CommandHandler("modificar_stamina",cmd_modificar_stamina))
    app.add_handler(CommandHandler("dar_titulo",       cmd_dar_titulo))

    # Jugadores — comandos extendidos
    app.add_handler(CommandHandler("ver_perfil_completo",    cmd_ver_perfil_completo))
    app.add_handler(CommandHandler("lista_jugadores",        cmd_lista_jugadores))
    app.add_handler(CommandHandler("set_hp",                 cmd_set_hp))
    app.add_handler(CommandHandler("set_atk",                cmd_set_atk))
    app.add_handler(CommandHandler("set_def",                cmd_set_def))
    app.add_handler(CommandHandler("set_xp",                 cmd_set_xp))
    app.add_handler(CommandHandler("set_stamina",            cmd_set_stamina_exacta))
    app.add_handler(CommandHandler("limpiar_penalizaciones", cmd_limpiar_penalizaciones))
    app.add_handler(CommandHandler("limpiar_actividad",     cmd_limpiar_actividad))
    app.add_handler(CallbackQueryHandler(cb_editar_jugador,  pattern="^ej_"))

    # Editor inline de jugador (recibe texto de configuración)
    from telegram.ext import MessageHandler, filters as _f
    app.add_handler(MessageHandler(_f.TEXT & ~_f.COMMAND, _ej_recibir_texto), group=11)

    # Mundo y eventos
    app.add_handler(CommandHandler("cambiar_clima",         cmd_cambiar_clima))
    app.add_handler(CommandHandler("iniciar_evento_global", cmd_iniciar_evento_global))
    app.add_handler(CommandHandler("rotar_tienda_creditos", cmd_rotar_tienda_creditos))
    app.add_handler(CommandHandler("anular_subasta",        cmd_anular_subasta))
    app.add_handler(CommandHandler("estado_bot",            cmd_estado_bot))
    app.add_handler(CommandHandler("ajuste_global",         cmd_ajuste_global))
    app.add_handler(CommandHandler("dar_masivo",            cmd_dar_masivo))

    # Buscador de premios
    app.add_handler(CommandHandler("premios_buscar",  cmd_premios_buscar))
    app.add_handler(CallbackQueryHandler(cb_premios_buscar, pattern="^(premios_|premio_sel_)"))
    app.add_handler(CommandHandler("panel_premios",   cmd_panel_premios))
    app.add_handler(CommandHandler("auto_premios",    cmd_auto_premios))
    app.add_handler(CommandHandler("filtros_premios", cmd_filtros_premios))
    app.add_handler(CallbackQueryHandler(cb_panel_premios,   pattern="^pp_"))
    app.add_handler(CallbackQueryHandler(cb_filtros_premios, pattern="^pf_"))
    # Panel de tiempos de viaje
    app.add_handler(CommandHandler("panel_viajes", cmd_panel_viajes))
    app.add_handler(CallbackQueryHandler(cb_panel_viajes, pattern="^pv_"))
    # Panel de cooldowns de zona
    app.add_handler(CommandHandler("panel_zonas", cmd_panel_zonas))
    app.add_handler(CallbackQueryHandler(cb_panel_zonas, pattern="^pz_"))

    # Limpiar guerras bloqueadas
    app.add_handler(CommandHandler("guerra_limpiar", cmd_guerra_limpiar))
    # Control de facciones (superadmin)
    app.add_handler(CommandHandler("faccion_libre",   cmd_faccion_libre))
    app.add_handler(CommandHandler("faccion_auto",    cmd_faccion_auto))
    app.add_handler(CommandHandler("faccion_estado",  cmd_faccion_estado))

    # Permisos granulares por comando individual
    app.add_handler(CommandHandler("superadmin_permisos_cmd", cmd_superadmin_permisos_cmd))
    app.add_handler(CallbackQueryHandler(cb_pcmd, pattern="^pcmd_"))

    # Panel de comandos admin
    app.add_handler(CommandHandler("panel_admin", cmd_panel_admin))
    app.add_handler(CallbackQueryHandler(cb_admin_panel_boton, pattern="^admin_panel_menu$"))
    app.add_handler(CallbackQueryHandler(cb_panel_categoria,   pattern="^panel_cat_"))
    app.add_handler(CallbackQueryHandler(cb_panel_volver,      pattern="^panel_volver$"))
    app.add_handler(CallbackQueryHandler(cb_panel_cerrar,       pattern="^panel_cerrar$"))
    app.add_handler(CallbackQueryHandler(cb_abrir_panel_maestro,        pattern="^abrir_panel_maestro$"))
    app.add_handler(CallbackQueryHandler(cb_panel_abrir_restricciones,  pattern="^panel_abrir_restricciones$"))

    # Broadcast interactivo desde el panel admin
    app.add_handler(CallbackQueryHandler(cb_broadcast_modo, pattern="^bc_modo_"))
    app.add_handler(CallbackQueryHandler(cb_broadcast_confirmar, pattern="^bc_(confirmar|cancelar|reescribir_)"))
    from telegram.ext import MessageHandler, filters as _f_bc
    app.add_handler(MessageHandler(_f_bc.TEXT & ~_f_bc.COMMAND, mh_broadcast_mensaje), group=11)

    # ── Panel de configuración permanente del juego ──────────────────────────
    app.add_handler(CommandHandler("config_juego", cmd_config_juego))
    app.add_handler(CallbackQueryHandler(cb_config_juego, pattern="^cfg_"))
    from telegram.ext import MessageHandler, filters as _f2
    app.add_handler(MessageHandler(_f2.TEXT & ~_f2.COMMAND, _cfg_recibir_texto), group=12)

    # ── Simulador PvE (superadmin) ───────────────────────────────────────────
    import simulador_pve as _sim_pve
    _sim_pve.registrar_handlers_simulador(app)

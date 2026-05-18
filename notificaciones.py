#!/usr/bin/env python3
# notificaciones.py — Bandeja de notificaciones del jugador
#
# Comandos:
#   /notificaciones   — Ver mensajes pendientes y marcarlos como leídos

import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler

import db_helper

DB_PATH = "aethelgard.db"
POR_PAGINA = 5


def _marcar_leida(notif_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE notificaciones SET leida = 1 WHERE id = ?", (notif_id,))
    conn.commit()
    conn.close()


def _borrar_todas(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM notificaciones WHERE jugador_id = ?", (user_id,))
    conn.commit()
    conn.close()


def _contar_no_leidas(user_id: int) -> int:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM notificaciones WHERE jugador_id = ? AND leida = 0", (user_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0


def _obtener_pagina(user_id: int, pagina: int):
    offset = (pagina - 1) * POR_PAGINA
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(
        "SELECT id, mensaje, leida, fecha_creacion FROM notificaciones "
        "WHERE jugador_id = ? ORDER BY leida ASC, fecha_creacion DESC "
        "LIMIT ? OFFSET ?",
        (user_id, POR_PAGINA, offset)
    )
    rows = [dict(r) for r in c.fetchall()]
    c.execute("SELECT COUNT(*) FROM notificaciones WHERE jugador_id = ?", (user_id,))
    total_row = c.fetchone()
    total = total_row[0] if total_row else 0
    conn.close()
    return rows, total


def _construir_mensaje(user_id: int, pagina: int):
    notifs, total = _obtener_pagina(user_id, pagina)
    no_leidas = _contar_no_leidas(user_id)
    total_paginas = max(1, (total + POR_PAGINA - 1) // POR_PAGINA)

    texto = f"🔔 *Notificaciones* ({no_leidas} sin leer / {total} total)\n\n"

    botones = []
    if not notifs:
        texto += "_No tienes notificaciones._"
    else:
        for n in notifs:
            estado = "📩" if not n["leida"] else "📭"
            fecha = n["fecha_creacion"][:16] if n["fecha_creacion"] else ""
            texto += f"{estado} _{fecha}_\n{n['mensaje']}\n\n"
            if not n["leida"]:
                botones.append([InlineKeyboardButton(
                    f"✅ Marcar leída #{n['id']}",
                    callback_data=f"notif_leer_{n['id']}_{pagina}"
                )])

    nav = []
    if pagina > 1:
        nav.append(InlineKeyboardButton("◀️", callback_data=f"notif_pag_{pagina-1}"))
    nav.append(InlineKeyboardButton(f"{pagina}/{total_paginas}", callback_data="notif_noop"))
    if pagina < total_paginas:
        nav.append(InlineKeyboardButton("▶️", callback_data=f"notif_pag_{pagina+1}"))
    if nav:
        botones.append(nav)

    acciones = []
    if no_leidas > 0:
        acciones.append(InlineKeyboardButton("✅ Marcar todas leídas", callback_data="notif_todas_leidas"))
    if total > 0:
        acciones.append(InlineKeyboardButton("🗑️ Borrar todas", callback_data="notif_borrar_todas"))
    if acciones:
        botones.append(acciones)

    return texto, InlineKeyboardMarkup(botones) if botones else None


async def _safe_edit(query, texto, markup=None, parse_mode=None):
    """Edita el mensaje ignorando errores de Telegram (mensaje ya modificado, no encontrado)."""
    try:
        await query.edit_message_text(texto, reply_markup=markup, parse_mode=parse_mode)
    except Exception:
        pass


async def cmd_notificaciones(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not db_helper.existe_jugador(user_id):
        await update.effective_message.reply_text("❌ No tienes personaje. Usa /start para crear uno.")
        return
    texto, markup = _construir_mensaje(user_id, 1)
    await update.effective_message.reply_text(texto, reply_markup=markup, parse_mode="Markdown")


async def cb_notificaciones(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    data = query.data

    if data == "notif_noop":
        return

    if data.startswith("notif_leer_"):
        partes = data.split("_")
        try:
            notif_id = int(partes[2])
            pagina   = int(partes[3]) if len(partes) > 3 else 1
        except (ValueError, IndexError):
            return
        _marcar_leida(notif_id)
        texto, markup = _construir_mensaje(user_id, pagina)
        await _safe_edit(query, texto, markup=markup, parse_mode="Markdown")

    elif data == "notif_todas_leidas":
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("UPDATE notificaciones SET leida = 1 WHERE jugador_id = ?", (user_id,))
        conn.commit()
        conn.close()
        texto, markup = _construir_mensaje(user_id, 1)
        await _safe_edit(query, texto, markup=markup, parse_mode="Markdown")

    elif data == "notif_borrar_todas":
        _borrar_todas(user_id)
        await _safe_edit(query, "🗑️ Todas las notificaciones eliminadas.")

    elif data.startswith("notif_pag_"):
        try:
            pagina = int(data.split("_")[-1])
        except (ValueError, IndexError):
            pagina = 1
        texto, markup = _construir_mensaje(user_id, pagina)
        await _safe_edit(query, texto, markup=markup, parse_mode="Markdown")


def registrar_handlers(app):
    app.add_handler(CommandHandler("notificaciones", cmd_notificaciones))
    app.add_handler(CallbackQueryHandler(cb_notificaciones, pattern=r"^notif_"))

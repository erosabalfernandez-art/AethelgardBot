#!/usr/bin/env python3
"""
gchat.py — Chat de gremio dentro del bot.

Comandos:
  /gchat <mensaje>  — Envía un mensaje a todos los miembros del gremio
  /gchat_log        — Ver los últimos 10 mensajes del chat del gremio

Admin: activable/desactivable desde panel de automatizaciones
"""

import sqlite3
import logging
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
import db_helper

logger = logging.getLogger(__name__)
DB_PATH = "aethelgard.db"

# ── Tabla ──────────────────────────────────────────────────────────────────────

def _init_tabla():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS gchat_mensajes (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            gremio_id   INTEGER NOT NULL,
            user_id     INTEGER NOT NULL,
            nombre      TEXT,
            mensaje     TEXT,
            fecha       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_gchat_gremio ON gchat_mensajes(gremio_id)")
    conn.commit()
    conn.close()

# ── Configuración ──────────────────────────────────────────────────────────────

def _activo() -> bool:
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT valor FROM config_bot WHERE clave = 'gchat_activo'")
        row = c.fetchone()
        conn.close()
        return (row[0] if row else "1") == "1"
    except Exception:
        return True

# ── Helpers ────────────────────────────────────────────────────────────────────

def _obtener_gremio_jugador(user_id: int) -> dict | None:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
        SELECT g.id, g.nombre, g.tag, mg.rango
        FROM gremios g
        JOIN miembros_gremio mg ON g.id = mg.gremio_id
        WHERE mg.jugador_id = ?
    """, (user_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def _miembros_gremio(gremio_id: int) -> list[int]:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT jugador_id FROM miembros_gremio WHERE gremio_id = ?", (gremio_id,))
    rows = c.fetchall()
    conn.close()
    return [r[0] for r in rows]

def _guardar_mensaje(gremio_id: int, user_id: int, nombre: str, mensaje: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO gchat_mensajes (gremio_id, user_id, nombre, mensaje)
        VALUES (?, ?, ?, ?)
    """, (gremio_id, user_id, nombre, mensaje))
    # Limitar a 100 mensajes por gremio
    c.execute("""
        DELETE FROM gchat_mensajes
        WHERE gremio_id = ? AND id NOT IN (
            SELECT id FROM gchat_mensajes WHERE gremio_id = ? ORDER BY id DESC LIMIT 100
        )
    """, (gremio_id, gremio_id))
    conn.commit()
    conn.close()

def _obtener_log(gremio_id: int, limite: int = 10) -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
        SELECT nombre, mensaje, fecha FROM gchat_mensajes
        WHERE gremio_id = ? ORDER BY id DESC LIMIT ?
    """, (gremio_id, limite))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return list(reversed(rows))

# ── Handlers ──────────────────────────────────────────────────────────────────

async def cmd_gchat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not db_helper.existe_jugador(user_id):
        await update.message.reply_text("⚠️ Primero regístrate con /start.")
        return
    if not _activo():
        await update.message.reply_text("⚠️ El chat de gremio está desactivado.")
        return

    gremio = _obtener_gremio_jugador(user_id)
    if not gremio:
        await update.message.reply_text("❌ No perteneces a ningún gremio. Únete con /gremio.")
        return

    if not context.args:
        await update.message.reply_text(
            "💬 <b>Chat de Gremio</b>\n\n"
            "Uso: <code>/gchat &lt;mensaje&gt;</code>\n"
            "Ver historial: /gchat_log",
            parse_mode="HTML"
        )
        return

    mensaje = " ".join(context.args)
    if len(mensaje) > 300:
        await update.message.reply_text("❌ El mensaje es demasiado largo (máximo 300 caracteres).")
        return

    jug = db_helper.obtener_jugador(user_id)
    nombre = jug["nombre_personaje"] if jug else "Desconocido"
    rango_emoji = {"lider": "👑", "oficial": "⭐", "veterano": "🔸", "recluta": "🔰", "miembro": "⚔️"}
    rango_ico = rango_emoji.get(gremio["rango"], "⚔️")

    _guardar_mensaje(gremio["id"], user_id, nombre, mensaje)

    texto_envio = (
        f"🏰 <b>[{gremio['tag']}] Chat de Gremio</b>\n"
        f"{rango_ico} <b>{nombre}</b>:\n"
        f"💬 {mensaje}"
    )

    miembros = _miembros_gremio(gremio["id"])
    enviados = 0
    from telegram_queue import rate_limiter
    for mid in miembros:
        if mid == user_id:
            continue
        try:
            await rate_limiter.send(context.bot, mid, texto_envio, parse_mode="HTML")
            enviados += 1
        except Exception:
            pass

    await update.message.reply_text(
        f"✅ Mensaje enviado a {enviados} miembro(s) del gremio.",
        parse_mode="HTML"
    )


async def cmd_gchat_log(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not db_helper.existe_jugador(user_id):
        await update.message.reply_text("⚠️ Primero regístrate con /start.")
        return
    if not _activo():
        await update.message.reply_text("⚠️ El chat de gremio está desactivado.")
        return

    gremio = _obtener_gremio_jugador(user_id)
    if not gremio:
        await update.message.reply_text("❌ No perteneces a ningún gremio.")
        return

    mensajes = _obtener_log(gremio["id"])
    if not mensajes:
        await update.message.reply_text(
            f"🏰 <b>[{gremio['tag']}] Chat de Gremio</b>\n\nNo hay mensajes aún.",
            parse_mode="HTML"
        )
        return

    lineas = [f"🏰 <b>[{gremio['tag']}] Últimos mensajes del gremio:</b>\n"]
    for m in mensajes:
        fecha = m["fecha"][:16] if m["fecha"] else ""
        lineas.append(f"<i>{fecha}</i> <b>{m['nombre']}</b>: {m['mensaje']}")

    await update.message.reply_text("\n".join(lineas), parse_mode="HTML")


def registrar_handlers(app):
    _init_tabla()
    app.add_handler(CommandHandler("gchat", cmd_gchat))
    app.add_handler(CommandHandler("gchat_log", cmd_gchat_log))

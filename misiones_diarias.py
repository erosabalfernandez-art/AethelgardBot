#!/usr/bin/env python3
"""
misiones_diarias.py — Misiones que rotan cada 24h y dan recompensas.

Cada día se generan 3 misiones aleatorias para cada jugador.
Son independientes de las misiones de tutorial (misiones.py).

Comandos: /misiones_hoy  — ver misiones diarias actuales
          /mdcheck       — comprobar progreso (alias)
Admin: activable/desactivable desde panel de automatizaciones
"""

import sqlite3
import random
import logging
from datetime import datetime, date
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
import db_helper

logger = logging.getLogger(__name__)
DB_PATH = "aethelgard.db"

# ── Catálogo de misiones posibles ─────────────────────────────────────────────

CATALOGO = [
    {
        "id": "md_matar5",
        "titulo": "⚔️ Cazador del Día",
        "descripcion": "Derrota 5 monstruos en cualquier zona.",
        "tipo": "matar",
        "objetivo": 5,
        "recompensa_oro": 200,
        "recompensa_xp": 150,
    },
    {
        "id": "md_recolectar3",
        "titulo": "⛏️ Recolector",
        "descripcion": "Recolecta materiales 3 veces.",
        "tipo": "recolectar",
        "objetivo": 3,
        "recompensa_oro": 150,
        "recompensa_xp": 100,
    },
    {
        "id": "md_mazmorra1",
        "titulo": "🏰 Explorador de Mazmorras",
        "descripcion": "Completa 1 mazmorra.",
        "tipo": "mazmorra",
        "objetivo": 1,
        "recompensa_oro": 300,
        "recompensa_xp": 300,
    },
    {
        "id": "md_mercado1",
        "titulo": "💱 Comerciante",
        "descripcion": "Realiza 1 transacción en el mercado P2P o subasta.",
        "tipo": "mercado",
        "objetivo": 1,
        "recompensa_oro": 100,
        "recompensa_xp": 50,
    },
    {
        "id": "md_viaje2",
        "titulo": "✈️ Viajero",
        "descripcion": "Viaja a 2 zonas diferentes.",
        "tipo": "viaje",
        "objetivo": 2,
        "recompensa_oro": 120,
        "recompensa_xp": 80,
    },
    {
        "id": "md_investigar2",
        "titulo": "🔍 Investigador",
        "descripcion": "Investiga el terreno 2 veces.",
        "tipo": "investigar",
        "objetivo": 2,
        "recompensa_oro": 180,
        "recompensa_xp": 120,
    },
    {
        "id": "md_matar_boss1",
        "titulo": "👑 Cazador de Élite",
        "descripcion": "Derrota 1 mini-boss.",
        "tipo": "matar_boss",
        "objetivo": 1,
        "recompensa_oro": 400,
        "recompensa_xp": 400,
    },
    {
        "id": "md_tienda1",
        "titulo": "🛒 Comprador",
        "descripcion": "Compra algo en la tienda.",
        "tipo": "tienda",
        "objetivo": 1,
        "recompensa_oro": 80,
        "recompensa_xp": 40,
    },
    {
        "id": "md_duelo1",
        "titulo": "🥊 Duelista",
        "descripcion": "Participa en 1 duelo PvP.",
        "tipo": "pvp",
        "objetivo": 1,
        "recompensa_oro": 250,
        "recompensa_xp": 200,
    },
    {
        "id": "md_craftear1",
        "titulo": "⚒️ Artesano",
        "descripcion": "Craftea 1 objeto.",
        "tipo": "craftear",
        "objetivo": 1,
        "recompensa_oro": 200,
        "recompensa_xp": 150,
    },
]

# ── Tabla ──────────────────────────────────────────────────────────────────────

def _init_tabla():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS misiones_diarias (
            user_id     INTEGER,
            fecha       DATE,
            mision_id   TEXT,
            progreso    INTEGER DEFAULT 0,
            objetivo    INTEGER,
            completada  INTEGER DEFAULT 0,
            reclamada   INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, fecha, mision_id)
        )
    """)
    conn.commit()
    conn.close()

# ── Configuración ──────────────────────────────────────────────────────────────

def _activo() -> bool:
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT valor FROM config_bot WHERE clave = 'misiones_diarias_activo'")
        row = c.fetchone()
        conn.close()
        return (row[0] if row else "1") == "1"
    except Exception:
        return True

# ── Generación de misiones del día ────────────────────────────────────────────

def _generar_misiones_jugador(user_id: int, hoy: str):
    """Genera 3 misiones aleatorias para el jugador si no tiene las de hoy."""
    _init_tabla()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM misiones_diarias WHERE user_id = ? AND fecha = ?", (user_id, hoy))
    count = c.fetchone()[0]
    if count == 0:
        seleccionadas = random.sample(CATALOGO, min(3, len(CATALOGO)))
        for m in seleccionadas:
            c.execute("""
                INSERT OR IGNORE INTO misiones_diarias
                    (user_id, fecha, mision_id, objetivo)
                VALUES (?, ?, ?, ?)
            """, (user_id, hoy, m["id"], m["objetivo"]))
        conn.commit()
    conn.close()

def _obtener_misiones_hoy(user_id: int) -> list[dict]:
    hoy = date.today().isoformat()
    _generar_misiones_jugador(user_id, hoy)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
        SELECT mision_id, progreso, objetivo, completada, reclamada
        FROM misiones_diarias WHERE user_id = ? AND fecha = ?
    """, (user_id, hoy))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    # Enriquecer con datos del catálogo
    cat_index = {m["id"]: m for m in CATALOGO}
    result = []
    for r in rows:
        info = cat_index.get(r["mision_id"], {})
        result.append({**info, **r})
    return result

# ── Progresar misión ───────────────────────────────────────────────────────────

def avanzar_mision(user_id: int, tipo: str, cantidad: int = 1):
    """Llamar desde otros módulos cuando el jugador realiza una acción."""
    if not _activo():
        return
    hoy = date.today().isoformat()
    _generar_misiones_jugador(user_id, hoy)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Buscar misiones del tipo que no estén completadas
    misiones_tipo = [m["id"] for m in CATALOGO if m["tipo"] == tipo]
    for mid in misiones_tipo:
        c.execute("""
            UPDATE misiones_diarias
            SET progreso = MIN(progreso + ?, objetivo),
                completada = CASE WHEN progreso + ? >= objetivo THEN 1 ELSE 0 END
            WHERE user_id = ? AND fecha = ? AND mision_id = ? AND completada = 0
        """, (cantidad, cantidad, user_id, hoy, mid))
    conn.commit()
    conn.close()

def reclamar_mision(user_id: int, mision_id: str) -> dict | None:
    """Reclama la recompensa de una misión completada. Retorna la recompensa o None."""
    hoy = date.today().isoformat()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT completada, reclamada FROM misiones_diarias
        WHERE user_id = ? AND fecha = ? AND mision_id = ?
    """, (user_id, hoy, mision_id))
    row = c.fetchone()
    if not row or not row[0] or row[1]:
        conn.close()
        return None
    c.execute("""
        UPDATE misiones_diarias SET reclamada = 1
        WHERE user_id = ? AND fecha = ? AND mision_id = ?
    """, (user_id, hoy, mision_id))
    conn.commit()
    conn.close()

    info = next((m for m in CATALOGO if m["id"] == mision_id), None)
    if not info:
        return None

    if info["recompensa_oro"] > 0:
        db_helper.sumar_oro(user_id, info["recompensa_oro"])
    if info.get("recompensa_xp", 0) > 0:
        db_helper.sumar_xp(user_id, info["recompensa_xp"])

    return info

# ── Texto del panel ────────────────────────────────────────────────────────────

def _texto_misiones(user_id: int) -> tuple[str, InlineKeyboardMarkup]:
    misiones = _obtener_misiones_hoy(user_id)
    hoy = date.today().strftime("%d/%m/%Y")

    lineas = [f"📋 <b>MISIONES DIARIAS</b> — {hoy}\n"]
    botones = []

    for m in misiones:
        prog = m.get("progreso", 0)
        obj = m.get("objetivo", 1)
        completada = m.get("completada", 0)
        reclamada = m.get("reclamada", 0)

        barra = "▓" * prog + "░" * (obj - prog) if obj <= 10 else f"{prog}/{obj}"
        estado = "✅" if completada else "🔄"

        premio = f"{m.get('recompensa_oro',0)}🪙 + {m.get('recompensa_xp',0)}⭐XP"
        lineas.append(f"\n{estado} <b>{m.get('titulo','?')}</b>")
        lineas.append(f"📝 {m.get('descripcion','')}")
        lineas.append(f"📊 Progreso: [{barra}]  🎁 {premio}")

        if completada and not reclamada:
            botones.append([InlineKeyboardButton(
                f"🎁 Reclamar: {m.get('titulo','?')[:25]}",
                callback_data=f"md_reclamar_{m['mision_id']}"
            )])

    if not misiones:
        lineas.append("⚠️ No se generaron misiones para hoy. Usa /misiones_hoy de nuevo.")

    lineas.append(f"\n🔄 Las misiones se renuevan cada día a las 00:00 UTC.")

    teclado = botones + [[InlineKeyboardButton("❌ Cerrar", callback_data="md_cerrar")]]
    return "\n".join(lineas), InlineKeyboardMarkup(teclado)

# ── Handlers ──────────────────────────────────────────────────────────────────

async def cmd_misiones_hoy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not db_helper.existe_jugador(user_id):
        await update.message.reply_text("⚠️ Primero debes registrarte con /start.")
        return
    if not _activo():
        await update.message.reply_text("⚠️ Las misiones diarias están desactivadas.")
        return
    texto, teclado = _texto_misiones(user_id)
    await update.message.reply_text(texto, parse_mode="HTML", reply_markup=teclado)


async def cb_misiones(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    if query.data == "md_cerrar":
        await query.delete_message()
        return

    if query.data.startswith("md_reclamar_"):
        mision_id = query.data[len("md_reclamar_"):]
        resultado = reclamar_mision(user_id, mision_id)
        if resultado:
            await query.answer(
                f"🎁 ¡Misión completada! +{resultado['recompensa_oro']}🪙 +{resultado['recompensa_xp']}⭐",
                show_alert=True
            )
            texto, teclado = _texto_misiones(user_id)
            try:
                await query.edit_message_text(texto, parse_mode="HTML", reply_markup=teclado)
            except Exception:
                pass
        else:
            await query.answer("❌ No se pudo reclamar.", show_alert=True)


def job_reset_misiones_diarias(context):
    """Limpia misiones de días anteriores (llamar a las 00:00 UTC)."""
    logger.info("Limpiando misiones diarias de días anteriores...")
    try:
        from datetime import timedelta
        ayer = (date.today() - timedelta(days=1)).isoformat()
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("DELETE FROM misiones_diarias WHERE fecha < ?", (ayer,))
        eliminadas = c.rowcount
        conn.commit()
        conn.close()
        logger.info(f"Eliminadas {eliminadas} misiones diarias vencidas.")
    except Exception as e:
        logger.error(f"Error limpiando misiones diarias: {e}")


def registrar_handlers(app):
    _init_tabla()
    app.add_handler(CommandHandler("misiones_hoy", cmd_misiones_hoy))
    app.add_handler(CommandHandler("mdcheck", cmd_misiones_hoy))
    app.add_handler(CallbackQueryHandler(cb_misiones, pattern="^md_"))

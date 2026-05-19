#!/usr/bin/env python3
"""
zona_activa.py — Muestra cuántos jugadores están activos en la misma zona.

Se integra en la llegada a zonas salvajes (viajes.py) y como comando.

Comandos: /zona_jugadores  — ver jugadores activos en tu zona actual
Admin: activable/desactivable desde panel de automatizaciones
"""

import sqlite3
import logging
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
import db_helper

logger = logging.getLogger(__name__)
DB_PATH = "aethelgard.db"

VENTANA_ACTIVO_MINUTOS = 15  # Jugador "activo" si interactuó en los últimos 15 min

# ── Configuración ──────────────────────────────────────────────────────────────

def _activo() -> bool:
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT valor FROM config_bot WHERE clave = 'zona_activa_activo'")
        row = c.fetchone()
        conn.close()
        return (row[0] if row else "1") == "1"
    except Exception:
        return True

# ── Lógica ────────────────────────────────────────────────────────────────────

def obtener_jugadores_en_zona(zona: str, excluir_uid: int = None) -> list[dict]:
    """Retorna lista de jugadores activos en la zona en los últimos 15 min."""
    desde = (datetime.now() - timedelta(minutes=VENTANA_ACTIVO_MINUTOS)).isoformat()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    query = """
        SELECT user_id, nombre_personaje, nivel, clase, faccion
        FROM jugadores
        WHERE zona_actual = ?
          AND ubicacion = 'salvaje'
          AND ultima_interaccion > ?
    """
    params = [zona, desde]
    if excluir_uid:
        query += " AND user_id != ?"
        params.append(excluir_uid)
    c.execute(query, params)
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def texto_jugadores_zona(zona: str, jugadores: list[dict], mi_faccion: str = None) -> str:
    """Genera el texto informativo de jugadores en la zona."""
    if not jugadores:
        return f"👥 No hay otros aventureros activos en esta zona ahora mismo."

    total = len(jugadores)
    faccion_emoji = {"Alianza": "⚜️", "Imperio": "⚙️", "Sindicato": "🐍"}

    # Agrupar por facción
    por_faccion: dict[str, list] = {}
    for j in jugadores:
        f = j.get("faccion", "?")
        por_faccion.setdefault(f, []).append(j)

    lineas = [f"👥 <b>{total} aventurero(s) activo(s) en {zona}:</b>"]
    for faccion, miembros in sorted(por_faccion.items()):
        ico = faccion_emoji.get(faccion, "🔹")
        if mi_faccion and faccion == mi_faccion:
            etiqueta = f"{ico} {faccion} (tu facción)"
        else:
            etiqueta = f"{ico} {faccion}"
        lineas.append(f"\n{etiqueta}: {len(miembros)} jugador(es)")
        for j in miembros[:3]:  # Mostrar máx 3 nombres por facción
            clase_ico = {"vanguardista": "🛡️", "acechante": "🗡️",
                         "tejehechizos": "🔮", "maestro_caza": "🏹"}.get(j.get("clase", ""), "⚔️")
            lineas.append(f"  {clase_ico} {j['nombre_personaje']} (Nv.{j['nivel']})")
        if len(miembros) > 3:
            lineas.append(f"  ...y {len(miembros) - 3} más")

    lineas.append("\n⚠️ ¡Cuidado con jugadores de otras facciones en zonas PvP!")
    return "\n".join(lineas)


async def mostrar_zona_activa_llegada(bot, user_id: int, zona: str):
    """Llamar desde viajes.py al llegar a zona salvaje."""
    if not _activo():
        return
    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        return
    jugadores = obtener_jugadores_en_zona(zona, excluir_uid=user_id)
    texto = texto_jugadores_zona(zona, jugadores, jug.get("faccion"))
    try:
        from telegram_queue import rate_limiter
        await rate_limiter.send(bot, user_id, texto, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error mostrando zona activa a {user_id}: {e}")

# ── Handlers ──────────────────────────────────────────────────────────────────

async def cmd_zona_jugadores(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    msg = update.effective_message
    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        await msg.reply_text("⚠️ Primero regístrate con /start.")
        return
    if not _activo():
        await msg.reply_text("⚠️ El indicador de zona activa está desactivado.")
        return

    zona = jug.get("zona_actual", "Desconocida")
    ubicacion = jug.get("ubicacion", "ciudad")

    if ubicacion != "salvaje":
        await msg.reply_text(
            "🏙️ Estás en una ciudad. Este comando solo funciona en zonas salvajes.\n"
            "Viaja a una zona con /viajar."
        )
        return

    jugadores = obtener_jugadores_en_zona(zona, excluir_uid=user_id)
    texto = texto_jugadores_zona(zona, jugadores, jug.get("faccion"))
    await msg.reply_text(texto, parse_mode="HTML")


def registrar_handlers(app):
    app.add_handler(CommandHandler("zona_jugadores", cmd_zona_jugadores))

#!/usr/bin/env python3
"""
anuncio_jefe.py — Anuncio global cuando cae un Jefe Raid.

Se llama desde jefes.py cuando la batalla termina con victoria.
Envía un mensaje épico a todos los jugadores registrados.
Admin: activable/desactivable desde panel de automatizaciones
"""

import sqlite3
import logging
from datetime import datetime

logger = logging.getLogger(__name__)
DB_PATH = "aethelgard.db"

# ── Configuración ──────────────────────────────────────────────────────────────

def _activo() -> bool:
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT valor FROM config_bot WHERE clave = 'anuncio_jefe_activo'")
        row = c.fetchone()
        conn.close()
        return (row[0] if row else "1") == "1"
    except Exception:
        return True

# ── Plantillas de anuncio ─────────────────────────────────────────────────────

PLANTILLAS = [
    (
        "☠️ <b>¡{nombre_jefe} HA CAÍDO!</b>\n\n"
        "🏆 La épica batalla ha concluido. Los valientes aventureros de Aethelgard "
        "han derrotado a esta terrible criatura.\n\n"
        "⚔️ <b>Mejor atacante:</b> {top_jugador} con {top_daño} de daño total.\n"
        "👥 Participantes: {participantes}\n\n"
        "🎁 Las recompensas ya han sido distribuidas entre los héroes.\n"
        "¡Sus nombres serán recordados en las crónicas de Aethelgard!"
    ),
    (
        "🌟 <b>¡VICTORIA ÉPICA!</b>\n\n"
        "Los aventureros de Aethelgard han conseguido lo imposible: "
        "<b>{nombre_jefe}</b> yace derrotado.\n\n"
        "⚔️ <b>Héroe del día:</b> {top_jugador}\n"
        "💀 Daño infligido: {top_daño}\n"
        "👥 Guerreros involucrados: {participantes}\n\n"
        "🔔 Si no participaste esta vez, ¡prepárate para la próxima convocatoria!"
    ),
    (
        "💀 <b>¡{nombre_jefe} FUE DERROTADO!</b>\n\n"
        "El poder de {participantes} valientes aventureros fue suficiente para acabar "
        "con esta bestia ancestral. El mundo de Aethelgard respiró aliviado.\n\n"
        "🏆 MVP: <b>{top_jugador}</b>\n\n"
        "⚔️ Permanece alerta — las sombras del vacío nunca descansan..."
    ),
]

import random

async def anunciar_victoria_jefe(
    bot,
    nombre_jefe: str,
    participantes_data: list[dict],
    excluir_uid: int = None
):
    """
    Envía el anuncio de victoria global a todos los jugadores.

    participantes_data: lista de {'user_id': int, 'nombre': str, 'dano': int}
    """
    if not _activo():
        return

    # Calcular top jugador
    top = max(participantes_data, key=lambda x: x.get("dano", 0)) if participantes_data else None
    top_jugador = top["nombre"] if top else "Un héroe anónimo"
    top_daño = f"{top['dano']:,}" if top else "0"
    n_participantes = len(participantes_data)

    plantilla = random.choice(PLANTILLAS)
    texto = plantilla.format(
        nombre_jefe=nombre_jefe,
        top_jugador=top_jugador,
        top_daño=top_daño,
        participantes=n_participantes
    )

    # Obtener todos los jugadores
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT user_id FROM jugadores")
        rows = c.fetchall()
        conn.close()
        todos = [r[0] for r in rows]
    except Exception as e:
        logger.error(f"Error obteniendo jugadores para anuncio: {e}")
        return

    from telegram_queue import rate_limiter
    enviados = 0
    for uid in todos:
        try:
            await rate_limiter.send(bot, uid, texto, parse_mode="HTML")
            enviados += 1
        except Exception:
            pass

    logger.info(f"Anuncio de victoria de {nombre_jefe} enviado a {enviados} jugadores.")
    return enviados

#!/usr/bin/env python3
"""
stamina_notif.py — Notificación automática cuando la stamina del jugador se llena.

Job que corre cada 3 minutos revisando qué jugadores llegaron a stamina máxima
y notificándolos una sola vez (sin spam repetido).

Admin: activable/desactivable desde panel de automatizaciones
"""

import sqlite3
import logging
from datetime import datetime, timedelta
import db_helper

logger = logging.getLogger(__name__)
DB_PATH = "aethelgard.db"

# ── Tabla de estado de notificaciones de stamina ──────────────────────────────

def _init_tabla():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS stamina_notif_estado (
            user_id             INTEGER PRIMARY KEY,
            notificado_llena    INTEGER DEFAULT 0,
            ultima_notificacion TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

# ── Configuración ──────────────────────────────────────────────────────────────

def _activo() -> bool:
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT valor FROM config_bot WHERE clave = 'stamina_notif_activo'")
        row = c.fetchone()
        conn.close()
        return (row[0] if row else "1") == "1"
    except Exception:
        return True


def marcar_stamina_gastada(user_id: int):
    """Llamar cuando el jugador gasta stamina — resetea flag para poder notificar de nuevo."""
    _init_tabla()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO stamina_notif_estado (user_id, notificado_llena)
        VALUES (?, 0)
        ON CONFLICT(user_id) DO UPDATE SET notificado_llena = 0
    """, (user_id,))
    conn.commit()
    conn.close()


async def job_stamina_notif(context):
    """Job que corre cada 3 minutos revisando staminas llenas."""
    if not _activo():
        return

    _init_tabla()
    try:
        from config_balance import STAMINA_REGENERACION_SEGUNDOS as seg_regen
    except ImportError:
        seg_regen = 180

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Jugadores con stamina_actual < stamina_maxima que no han sido notificados
    c.execute("""
        SELECT j.user_id, j.stamina_actual, j.stamina_maxima, j.ultima_regeneracion_stamina
        FROM jugadores j
        LEFT JOIN stamina_notif_estado sne ON j.user_id = sne.user_id
        WHERE j.stamina_actual < j.stamina_maxima
          AND (sne.notificado_llena IS NULL OR sne.notificado_llena = 0)
    """)
    jugadores = c.fetchall()
    conn.close()

    from telegram_queue import rate_limiter
    ahora = datetime.now()
    notificados = 0

    for jug in jugadores:
        user_id = jug["user_id"]
        actual = jug["stamina_actual"]
        maxi = jug["stamina_maxima"]
        ultima = jug["ultima_regeneracion_stamina"]

        if not ultima:
            continue

        # Calcular cuándo llegará a máximo
        ult_dt = datetime.fromisoformat(ultima)
        tiempo_pasado = (ahora - ult_dt).total_seconds()
        ya_regenerado = int(tiempo_pasado // seg_regen)
        nueva = min(maxi, actual + ya_regenerado)

        if nueva >= maxi:
            # Stamina llena — notificar
            try:
                await rate_limiter.send(
                    context.bot, user_id,
                    "⚡ <b>¡Tu stamina está al máximo!</b>\n"
                    f"Tienes {maxi}/{maxi} stamina disponible.\n"
                    "¡Es hora de salir a explorar, recolectar o investigar!\n\n"
                    "✈️ Usa /viajar para moverte a una zona salvaje.",
                    parse_mode="HTML"
                )
                # Marcar como notificado
                conn2 = sqlite3.connect(DB_PATH)
                c2 = conn2.cursor()
                c2.execute("""
                    INSERT INTO stamina_notif_estado (user_id, notificado_llena, ultima_notificacion)
                    VALUES (?, 1, ?)
                    ON CONFLICT(user_id) DO UPDATE SET
                        notificado_llena = 1,
                        ultima_notificacion = excluded.ultima_notificacion
                """, (user_id, ahora.isoformat()))
                conn2.commit()
                conn2.close()
                notificados += 1
            except Exception:
                pass

    if notificados:
        logger.info(f"Stamina notif: notificados {notificados} jugadores con stamina llena.")

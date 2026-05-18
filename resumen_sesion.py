#!/usr/bin/env python3
"""
resumen_sesion.py — Resumen automático al regresar a la ciudad.

Cuando el jugador viaja de una zona salvaje a una ciudad, recibe
un resumen de lo que ganó durante su sesión en esa zona.

Se integra con viajes.py llamando a iniciar_sesion()/finalizar_sesion().
Admin: activable/desactivable desde panel de automatizaciones
"""

import sqlite3
import logging
from datetime import datetime
from telegram.ext import ContextTypes
import db_helper

logger = logging.getLogger(__name__)
DB_PATH = "aethelgard.db"

# ── Tabla de sesiones ──────────────────────────────────────────────────────────

def _init_tabla():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS sesiones_zona (
            user_id         INTEGER PRIMARY KEY,
            zona            TEXT,
            inicio          TIMESTAMP,
            monstruos       INTEGER DEFAULT 0,
            oro_ganado      INTEGER DEFAULT 0,
            xp_ganada       INTEGER DEFAULT 0,
            items_obtenidos TEXT DEFAULT '[]',
            recolecciones   INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

# ── Configuración ──────────────────────────────────────────────────────────────

def _activo() -> bool:
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT valor FROM config_bot WHERE clave = 'resumen_sesion_activo'")
        row = c.fetchone()
        conn.close()
        return (row[0] if row else "1") == "1"
    except Exception:
        return True

# ── API pública ────────────────────────────────────────────────────────────────

def iniciar_sesion(user_id: int, zona: str):
    """Llamar cuando el jugador llega a una zona salvaje."""
    if not _activo():
        return
    _init_tabla()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    import json
    c.execute("""
        INSERT OR REPLACE INTO sesiones_zona
            (user_id, zona, inicio, monstruos, oro_ganado, xp_ganada, items_obtenidos, recolecciones)
        VALUES (?, ?, ?, 0, 0, 0, '[]', 0)
    """, (user_id, zona, datetime.now().isoformat()))
    conn.commit()
    conn.close()


def registrar_monstruo(user_id: int):
    if not _activo():
        return
    _init_tabla()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE sesiones_zona SET monstruos = monstruos + 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


def registrar_oro(user_id: int, cantidad: int):
    if not _activo():
        return
    _init_tabla()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE sesiones_zona SET oro_ganado = oro_ganado + ? WHERE user_id = ?", (cantidad, user_id))
    conn.commit()
    conn.close()


def registrar_xp(user_id: int, cantidad: int):
    if not _activo():
        return
    _init_tabla()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE sesiones_zona SET xp_ganada = xp_ganada + ? WHERE user_id = ?", (cantidad, user_id))
    conn.commit()
    conn.close()


def registrar_item(user_id: int, item_nombre: str):
    if not _activo():
        return
    _init_tabla()
    import json
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT items_obtenidos FROM sesiones_zona WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    if row:
        items = json.loads(row[0])
        items.append(item_nombre)
        c.execute("UPDATE sesiones_zona SET items_obtenidos = ? WHERE user_id = ?",
                  (json.dumps(items), user_id))
        conn.commit()
    conn.close()


def registrar_recoleccion(user_id: int):
    if not _activo():
        return
    _init_tabla()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE sesiones_zona SET recolecciones = recolecciones + 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


async def enviar_resumen(bot, user_id: int):
    """Llamar cuando el jugador viaja de vuelta a ciudad. Envía el resumen y limpia la sesión."""
    if not _activo():
        return
    _init_tabla()
    import json
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM sesiones_zona WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return
    sesion = dict(row)
    c.execute("DELETE FROM sesiones_zona WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

    # Solo mostrar si hizo algo
    if sesion["monstruos"] == 0 and sesion["oro_ganado"] == 0 and sesion["recolecciones"] == 0:
        return

    inicio = datetime.fromisoformat(sesion["inicio"]) if sesion["inicio"] else None
    duracion = ""
    if inicio:
        delta = datetime.now() - inicio
        mins = int(delta.total_seconds() // 60)
        duracion = f"⏱️ Tiempo en zona: {mins} min\n"

    items = json.loads(sesion["items_obtenidos"])
    items_str = ""
    if items:
        from collections import Counter
        conteo = Counter(items)
        items_str = "\n🎒 Ítems obtenidos:\n" + "\n".join(
            f"  • {nombre} ×{cant}" for nombre, cant in conteo.most_common(5)
        )
        if len(conteo) > 5:
            items_str += f"\n  • ...y {len(conteo) - 5} más"

    texto = (
        f"📊 <b>Resumen de tu aventura en {sesion['zona']}</b>\n"
        f"{duracion}"
        f"⚔️ Monstruos derrotados: {sesion['monstruos']}\n"
        f"⛏️ Recolecciones: {sesion['recolecciones']}\n"
        f"🪙 Oro ganado: {sesion['oro_ganado']:,}\n"
        f"⭐ XP ganada: {sesion['xp_ganada']:,}"
        f"{items_str}\n\n"
        f"🏙️ ¡Bienvenido de vuelta a la ciudad!"
    )

    try:
        from telegram_queue import rate_limiter
        await rate_limiter.send(bot, user_id, texto, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error enviando resumen de sesión a {user_id}: {e}")

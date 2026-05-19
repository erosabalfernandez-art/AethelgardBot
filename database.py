import sqlite3
import json
import os
from typing import Optional, Dict, List, Any

DB_PATH = os.environ.get("DB_PATH", "aethelgard.db")

def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA synchronous=NORMAL")
    c.execute("PRAGMA cache_size=-16000")
    c.execute("PRAGMA temp_store=MEMORY")
    c.execute("PRAGMA busy_timeout=30000")
    return conn

def row_to_dict(row) -> Optional[Dict]:
    if row is None:
        return None
    return dict(row)

def get_player(user_id: int) -> Optional[Dict]:
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM jugadores WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row_to_dict(row)

def update_player(user_id: int, **kwargs):
    if not kwargs:
        return
    conn = get_conn()
    c = conn.cursor()
    fields = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values()) + [user_id]
    c.execute(f"UPDATE jugadores SET {fields} WHERE user_id = ?", values)
    conn.commit()
    conn.close()

def get_config(key: str, default: str = "0") -> str:
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT valor FROM config_bot WHERE clave = ?", (key,))
    row = c.fetchone()
    conn.close()
    return row["valor"] if row else default

def get_player_inventory(user_id: int) -> List[Dict]:
    player = get_player(user_id)
    if not player:
        return []
    raw = player.get("inventario", "[]")
    try:
        return json.loads(raw) if raw else []
    except Exception:
        return []

def set_player_inventory(user_id: int, inventory: List[Dict]):
    update_player(user_id, inventario=json.dumps(inventory, ensure_ascii=False))

def get_notifications(user_id: int, limit: int = 20) -> List[Dict]:
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "SELECT * FROM notificaciones WHERE jugador_id = ? AND leida = 0 ORDER BY fecha_creacion DESC LIMIT ?",
        (user_id, limit)
    )
    rows = [row_to_dict(r) for r in c.fetchall()]
    conn.close()
    return rows

def mark_notifications_read(user_id: int):
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE notificaciones SET leida = 1 WHERE jugador_id = ?", (user_id,))
    conn.commit()
    conn.close()

def add_notification(user_id: int, message: str):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "INSERT INTO notificaciones (jugador_id, mensaje) VALUES (?, ?)",
        (user_id, message)
    )
    conn.commit()
    conn.close()

def get_guild_of_player(user_id: int) -> Optional[Dict]:
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT g.*, mg.rango FROM gremios g
        JOIN miembros_gremio mg ON g.id = mg.gremio_id
        WHERE mg.jugador_id = ?
    """, (user_id,))
    row = c.fetchone()
    conn.close()
    return row_to_dict(row)

def get_guild_members(guild_id: int) -> List[Dict]:
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT j.user_id, j.nombre_personaje, j.clase, j.nivel, j.faccion,
               mg.rango, j.ultima_interaccion
        FROM jugadores j
        JOIN miembros_gremio mg ON j.user_id = mg.jugador_id
        WHERE mg.gremio_id = ?
        ORDER BY mg.rango DESC, j.nivel DESC
    """, (guild_id,))
    rows = [row_to_dict(r) for r in c.fetchall()]
    conn.close()
    return rows

def get_active_parties() -> List[Dict]:
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM partys WHERE estado = 'formando' ORDER BY fecha_creacion DESC")
    rows = [row_to_dict(r) for r in c.fetchall()]
    conn.close()
    return rows

def get_party_of_player(user_id: int) -> Optional[Dict]:
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "SELECT * FROM partys WHERE miembros LIKE ? AND estado != 'disuelta'",
        (f"%{user_id}%",)
    )
    rows = [row_to_dict(r) for r in c.fetchall()]
    conn.close()
    for p in rows:
        members = json.loads(p.get("miembros", "[]"))
        if user_id in members:
            return p
    return None

def players_in_zone(zone_name: str) -> List[Dict]:
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT user_id, nombre_personaje, clase, nivel, faccion
        FROM jugadores WHERE zona_actual = ? AND ubicacion != 'viajando'
    """, (zone_name,))
    rows = [row_to_dict(r) for r in c.fetchall()]
    conn.close()
    return rows

def get_active_auction() -> List[Dict]:
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM subastas WHERE activa = 1 ORDER BY fecha_fin ASC LIMIT 20")
    rows = [row_to_dict(r) for r in c.fetchall()]
    conn.close()
    return rows

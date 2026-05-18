#!/usr/bin/env python3
# sistema_paz.py — Módulo centralizado de inmunidad PvP por meditación

import sqlite3
from datetime import datetime, timedelta
from typing import Optional, Tuple

DB_PATH = "aethelgard.db"

def _init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS estado_paz (
        user_id INTEGER PRIMARY KEY,
        activo BOOLEAN DEFAULT 0,
        fin_inmunidad TIMESTAMP,
        ventana_activa_hasta TIMESTAMP,
        cooldown_hasta TIMESTAMP,
        tipo_ventana TEXT,
        color_actual TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS penalizacion_peleas (
        user_id INTEGER,
        color_zona TEXT,
        peleas_pve INTEGER DEFAULT 0,
        PRIMARY KEY (user_id, color_zona)
    )''')
    conn.commit()
    conn.close()

_init_db()

# ==================== LECTURA ====================
def esta_en_paz(user_id: int) -> bool:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT activo, fin_inmunidad FROM estado_paz WHERE user_id=?', (user_id,))
    row = c.fetchone()
    conn.close()
    if row and row[0] and row[1]:
        try:
            return datetime.fromisoformat(row[1]) > datetime.now()
        except Exception:
            return False
    return False

def obtener_ventana_paz(user_id: int) -> Optional[Tuple[str, datetime]]:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT tipo_ventana, ventana_activa_hasta FROM estado_paz WHERE user_id=?', (user_id,))
    row = c.fetchone()
    conn.close()
    if row and row[0] and row[1]:
        try:
            hasta = datetime.fromisoformat(row[1])
            if hasta > datetime.now():
                return row[0], hasta
        except Exception:
            pass
    return None

def obtener_cooldown_zona(user_id: int) -> Optional[int]:
    """Segundos restantes de cooldown entre zonas, o None si no hay."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT cooldown_hasta FROM estado_paz WHERE user_id=?', (user_id,))
    row = c.fetchone()
    conn.close()
    if row and row[0]:
        try:
            cd = datetime.fromisoformat(row[0])
            if cd > datetime.now():
                return max(1, int((cd - datetime.now()).total_seconds()))
        except Exception:
            pass
    return None

def calcular_duracion_post_combate(user_id: int, color_zona: str) -> int:
    """120s base − 15s por pelea PvE en esa zona. Mínimo 15s."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT peleas_pve FROM penalizacion_peleas WHERE user_id=? AND color_zona=?', (user_id, color_zona))
    row = c.fetchone()
    peleas = row[0] if row else 0
    conn.close()
    return max(15, 120 - peleas * 15)

# ==================== ESCRITURA ====================
def activar_paz(user_id: int, duracion_segundos: int):
    """Activa la inmunidad y pone 15s de cooldown entre zonas."""
    fin = datetime.now() + timedelta(seconds=duracion_segundos)
    cd = datetime.now() + timedelta(seconds=15)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT user_id FROM estado_paz WHERE user_id=?', (user_id,))
    if c.fetchone():
        c.execute(
            'UPDATE estado_paz SET activo=1, fin_inmunidad=?, ventana_activa_hasta=NULL, tipo_ventana=NULL, cooldown_hasta=? WHERE user_id=?',
            (fin.isoformat(), cd.isoformat(), user_id)
        )
    else:
        c.execute(
            'INSERT INTO estado_paz (user_id, activo, fin_inmunidad, cooldown_hasta) VALUES (?,1,?,?)',
            (user_id, fin.isoformat(), cd.isoformat())
        )
    conn.commit()
    conn.close()

def desactivar_paz(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('UPDATE estado_paz SET activo=0, fin_inmunidad=NULL WHERE user_id=?', (user_id,))
    conn.commit()
    conn.close()

def abrir_ventana_entrada(user_id: int):
    """Abre ventana tipo 'entrada' al viajar a zona salvaje (válida 5 min para meditar)."""
    hasta = datetime.now() + timedelta(minutes=5)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT user_id FROM estado_paz WHERE user_id=?', (user_id,))
    if c.fetchone():
        c.execute(
            'UPDATE estado_paz SET ventana_activa_hasta=?, tipo_ventana=? WHERE user_id=?',
            (hasta.isoformat(), 'entrada', user_id)
        )
    else:
        c.execute(
            'INSERT INTO estado_paz (user_id, activo, ventana_activa_hasta, tipo_ventana) VALUES (?,0,?,?)',
            (user_id, hasta.isoformat(), 'entrada')
        )
    conn.commit()
    conn.close()

def abrir_ventana_post_combate(user_id: int, color_zona: str):
    """Tras ganar combate PvE: registra pelea + abre ventana 5 min para meditar."""
    hasta = datetime.now() + timedelta(minutes=5)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Registrar pelea (suma penalización)
    c.execute('SELECT peleas_pve FROM penalizacion_peleas WHERE user_id=? AND color_zona=?', (user_id, color_zona))
    row = c.fetchone()
    if row:
        c.execute('UPDATE penalizacion_peleas SET peleas_pve=peleas_pve+1 WHERE user_id=? AND color_zona=?', (user_id, color_zona))
    else:
        c.execute('INSERT INTO penalizacion_peleas (user_id, color_zona, peleas_pve) VALUES (?,?,1)', (user_id, color_zona))
    # Abrir ventana
    c.execute('SELECT user_id FROM estado_paz WHERE user_id=?', (user_id,))
    if c.fetchone():
        c.execute(
            'UPDATE estado_paz SET ventana_activa_hasta=?, tipo_ventana=?, color_actual=? WHERE user_id=?',
            (hasta.isoformat(), 'post_combate', color_zona, user_id)
        )
    else:
        c.execute(
            'INSERT INTO estado_paz (user_id, activo, ventana_activa_hasta, tipo_ventana, color_actual) VALUES (?,0,?,?,?)',
            (user_id, hasta.isoformat(), 'post_combate', color_zona)
        )
    conn.commit()
    conn.close()

def texto_estado_paz(user_id: int) -> str:
    """Retorna texto descriptivo del estado de paz del jugador."""
    if esta_en_paz(user_id):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('SELECT fin_inmunidad FROM estado_paz WHERE user_id=?', (user_id,))
        row = c.fetchone()
        conn.close()
        if row and row[0]:
            try:
                fin = datetime.fromisoformat(row[0])
                secs = int((fin - datetime.now()).total_seconds())
                mins, s = divmod(secs, 60)
                if mins:
                    return f"🧘 Paz activa: {mins}m {s}s"
                return f"🧘 Paz activa: {s}s"
            except Exception:
                pass
    return ""

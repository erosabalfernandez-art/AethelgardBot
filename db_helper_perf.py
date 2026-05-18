#!/usr/bin/env python3
"""
db_helper_perf.py — Mejoras de rendimiento para db_helper.py

MEJORAS IMPLEMENTADAS:
  1. Cache en memoria con TTL=10s para datos de jugadores (evita lecturas repetidas)
  2. Locks por usuario para operaciones de inventario (evita condiciones de carrera)
  3. Decorador de reintento con backoff para operaciones de BD fallidas
  4. Funciones atómicas para operaciones numéricas (oro, XP, eternium, reputación)
     usando UPDATE directo en SQL (evita read-modify-write race conditions)

USO:
    Este módulo se importa desde db_helper.py y reemplaza/complementa sus funciones.
    No lo importes directamente desde otros módulos — usa db_helper normal.
"""

import sqlite3
import threading
import time
import logging
import functools
from collections import defaultdict
from datetime import datetime
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

DB_PATH = "aethelgard.db"

# ── 1. Cache de jugadores con TTL ──────────────────────────────────────────────

class PlayerCache:
    """Cache LRU-like con TTL de 10 segundos para datos de jugadores."""
    def __init__(self, ttl: float = 10.0, max_size: int = 500):
        self._cache: dict[int, tuple[dict, float]] = {}
        self._ttl = ttl
        self._max_size = max_size
        self._lock = threading.Lock()

    def get(self, user_id: int) -> Optional[dict]:
        with self._lock:
            entry = self._cache.get(user_id)
            if entry is None:
                return None
            data, ts = entry
            if time.monotonic() - ts > self._ttl:
                del self._cache[user_id]
                return None
            return dict(data)  # copia defensiva

    def set(self, user_id: int, data: dict):
        with self._lock:
            if len(self._cache) >= self._max_size:
                # Evictar la entrada más antigua
                oldest = min(self._cache.items(), key=lambda x: x[1][1])
                del self._cache[oldest[0]]
            self._cache[user_id] = (dict(data), time.monotonic())

    def invalidar(self, user_id: int):
        with self._lock:
            self._cache.pop(user_id, None)

    def limpiar_expirados(self):
        ahora = time.monotonic()
        with self._lock:
            expirados = [uid for uid, (_, ts) in self._cache.items()
                         if ahora - ts > self._ttl]
            for uid in expirados:
                del self._cache[uid]


# Singleton del cache
player_cache = PlayerCache(ttl=10.0, max_size=500)


# ── 2. Locks por usuario para inventario ──────────────────────────────────────

class UserLockManager:
    """Un lock por usuario para operaciones que modifican inventario."""
    def __init__(self):
        self._locks: dict[int, threading.Lock] = defaultdict(threading.Lock)
        self._meta_lock = threading.Lock()

    def lock(self, user_id: int) -> threading.Lock:
        with self._meta_lock:
            return self._locks[user_id]

    def inventario_lock(self, user_id: int):
        """Context manager para proteger operaciones de inventario."""
        return self._locks[user_id]


user_lock_manager = UserLockManager()


# ── 3. Decorador de reintento con backoff exponencial ─────────────────────────

def con_reintento(max_intentos: int = 3, espera_base: float = 0.2):
    """
    Decorador que reintenta una función de BD si falla con OperationalError
    (base de datos bloqueada temporalmente).
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for intento in range(max_intentos):
                try:
                    return func(*args, **kwargs)
                except sqlite3.OperationalError as e:
                    if "locked" in str(e).lower() and intento < max_intentos - 1:
                        espera = espera_base * (2 ** intento)
                        logger.warning(f"DB bloqueada en {func.__name__}, reintento {intento+1} en {espera:.2f}s")
                        time.sleep(espera)
                        continue
                    raise
            return None  # nunca llega aquí
        return wrapper
    return decorator


# ── 4. Funciones atómicas de monedas y stats ──────────────────────────────────

@con_reintento()
def atomic_sumar_campo(user_id: int, campo: str, cantidad: int,
                        minimo: int = 0, maximo: Optional[int] = None) -> int:
    """
    Incrementa/decrementa un campo numérico de forma atómica usando SQL.
    Más eficiente que read-modify-write porque es una sola operación de BD.
    Retorna el nuevo valor.
    """
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=30000")
    c = conn.cursor()

    if maximo is not None:
        c.execute(f"""
            UPDATE jugadores
            SET {campo} = MIN(MAX({campo} + ?, ?), ?)
            WHERE user_id = ?
        """, (cantidad, minimo, maximo, user_id))
    else:
        c.execute(f"""
            UPDATE jugadores
            SET {campo} = MAX({campo} + ?, ?)
            WHERE user_id = ?
        """, (cantidad, minimo, user_id))

    conn.commit()
    c.execute(f"SELECT {campo} FROM jugadores WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()

    # Invalidar cache
    player_cache.invalidar(user_id)
    return row[0] if row else 0


def sumar_oro_atomico(user_id: int, cantidad: int) -> int:
    """Suma/resta oro de forma atómica. Nunca baja de 0."""
    return atomic_sumar_campo(user_id, "oro", cantidad, minimo=0)


def sumar_xp_atomico(user_id: int, cantidad: int) -> int:
    """Suma XP de forma atómica."""
    return atomic_sumar_campo(user_id, "experiencia", cantidad, minimo=0)


def sumar_eternium_atomico(user_id: int, cantidad: int) -> int:
    """Suma eternium de forma atómica. Nunca baja de 0."""
    return atomic_sumar_campo(user_id, "eternium", cantidad, minimo=0)


def sumar_reputacion_atomica(user_id: int, cantidad: int) -> int:
    """Suma/resta reputación de forma atómica."""
    return atomic_sumar_campo(user_id, "reputacion", cantidad, minimo=0)


# ── 5. obtener_jugador con cache ───────────────────────────────────────────────

@con_reintento()
def obtener_jugador_cached(user_id: int) -> Optional[Dict]:
    """
    Versión cacheada de obtener_jugador.
    Cache TTL=10s — para datos en tiempo real (HP, oro, stamina)
    usa obtener_jugador directamente.
    """
    cached = player_cache.get(user_id)
    if cached is not None:
        return cached

    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    c = conn.cursor()
    c.execute('SELECT * FROM jugadores WHERE user_id = ?', (user_id,))
    row = c.fetchone()
    conn.close()

    if row is None:
        return None

    data = dict(row)
    player_cache.set(user_id, data)
    return data


@con_reintento()
def actualizar_jugador_con_invalidacion(user_id: int, **kwargs) -> None:
    """
    Versión de actualizar_jugador que invalida el cache automáticamente.
    """
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=30000")
    c = conn.cursor()
    campos = ", ".join([f"{k} = ?" for k in kwargs])
    valores = list(kwargs.values()) + [user_id]
    c.execute(f'UPDATE jugadores SET {campos} WHERE user_id = ?', valores)
    conn.commit()
    conn.close()
    # Invalida cache para que la próxima lectura vaya a BD
    player_cache.invalidar(user_id)


# ── 6. agregar/quitar item con lock por usuario ────────────────────────────────

@con_reintento()
def agregar_item_seguro(user_id: int, item_nombre: str, cantidad: int = 1) -> bool:
    """Versión thread-safe de agregar_item con lock por usuario."""
    import json
    # Resolver nombre de material si aplica
    try:
        from materiales import resolver_nombre as _rn
        item_nombre = _rn(item_nombre)
    except Exception:
        pass

    with user_lock_manager.inventario_lock(user_id):
        conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        c = conn.cursor()
        c.execute('SELECT inventario FROM jugadores WHERE user_id = ?', (user_id,))
        row = c.fetchone()
        if row is None:
            conn.close()
            return False
        inv = json.loads(row[0])
        for item in inv:
            if item["nombre"] == item_nombre:
                item["cantidad"] += cantidad
                break
        else:
            inv.append({"nombre": item_nombre, "cantidad": cantidad})
        c.execute('UPDATE jugadores SET inventario = ? WHERE user_id = ?',
                  (json.dumps(inv), user_id))
        conn.commit()
        conn.close()
        player_cache.invalidar(user_id)
        return True


@con_reintento()
def quitar_item_seguro(user_id: int, item_nombre: str, cantidad: int = 1) -> bool:
    """Versión thread-safe de quitar_item con lock por usuario."""
    import json
    with user_lock_manager.inventario_lock(user_id):
        conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        c = conn.cursor()
        c.execute('SELECT inventario FROM jugadores WHERE user_id = ?', (user_id,))
        row = c.fetchone()
        if row is None:
            conn.close()
            return False
        inv = json.loads(row[0])
        for i, item in enumerate(inv):
            if item["nombre"] == item_nombre:
                if item["cantidad"] >= cantidad:
                    item["cantidad"] -= cantidad
                    if item["cantidad"] == 0:
                        inv.pop(i)
                    c.execute('UPDATE jugadores SET inventario = ? WHERE user_id = ?',
                              (json.dumps(inv), user_id))
                    conn.commit()
                    conn.close()
                    player_cache.invalidar(user_id)
                    return True
                else:
                    conn.close()
                    return False
        conn.close()
        return False

"""
modo_debug.py — Modo Detector de Bugs para Superadmin de Aethelgard.

Permite al superadmin jugar sin ninguna restricción del juego para probar
todas las funcionalidades. Integrado en db_helper, viajes, guerra, etc.
"""
import json
import os
from pathlib import Path
from datetime import datetime

_BASE = Path(__file__).parent
_ESTADO_FILE = _BASE / "debug_estado.json"
_QUEUE_FILE  = _BASE / "reportes_queue.jsonl"

# ── Usuarios en modo debug (en memoria, se limpia al reiniciar el bot) ────────
_DEBUG_USERS: set[int] = set()


def esta_en_debug(user_id: int) -> bool:
    """True si el usuario tiene el modo debug activo."""
    return user_id in _DEBUG_USERS


def activar_debug(user_id: int):
    _DEBUG_USERS.add(user_id)


def desactivar_debug(user_id: int):
    _DEBUG_USERS.discard(user_id)


def toggle_debug(user_id: int) -> bool:
    """Alterna el modo debug. Devuelve True si quedó activado."""
    if user_id in _DEBUG_USERS:
        _DEBUG_USERS.discard(user_id)
        return False
    else:
        _DEBUG_USERS.add(user_id)
        return True


# ── Persistencia del estado de testing ───────────────────────────────────────

def _cargar_estado() -> dict:
    if _ESTADO_FILE.exists():
        try:
            return json.loads(_ESTADO_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _guardar_estado(estado: dict):
    try:
        _ESTADO_FILE.write_text(
            json.dumps(estado, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception:
        pass


def get_estado_cmd(key: str) -> str:
    """Devuelve el estado de un item: 'ok', 'error', o 'pendiente'."""
    return _cargar_estado().get(key, "pendiente")


def marcar_estado_cmd(key: str, estado_nuevo: str):
    """Marca un item de testing como 'ok', 'error' o 'pendiente'."""
    estado = _cargar_estado()
    estado[key] = estado_nuevo
    _guardar_estado(estado)


def get_todos_estados() -> dict:
    return _cargar_estado()


def get_resumen() -> dict:
    """Retorna {ok, error, pendiente} sobre el total de items del catálogo."""
    from panel_debug import CATALOGO
    estado = _cargar_estado()
    total = sum(len(c["items"]) for c in CATALOGO)
    ok     = sum(1 for v in estado.values() if v == "ok")
    error  = sum(1 for v in estado.values() if v == "error")
    return {
        "ok": ok,
        "error": error,
        "pendiente": total - ok - error,
        "total": total,
    }


def resetear_todo():
    """Borra todos los estados de testing."""
    _guardar_estado({})


# ── Generación automática de reportes ────────────────────────────────────────

def generar_reporte_error(key: str, label: str, categoria: str, ruta: list, user_id: int):
    """
    Genera un reporte automático en reportes_queue.jsonl cuando el admin
    marca un comando como error desde el panel de detección de bugs.
    """
    pasos = " → ".join(ruta) if ruta else label
    n_pasos = len(ruta)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    msg = (
        f"🐛 [AUTO-DEBUG] Error detectado: {label}\n"
        f"Categoría: {categoria}\n"
        f"Pasos para llegar ({n_pasos}): {pasos}\n"
        f"Marcado como ❌ Error desde el panel de detección de bugs."
    )
    entrada = {
        "ts": ts,
        "user_id": user_id,
        "msg": msg,
        "done": False,
        "auto_debug": True,
        "debug_key": key,
    }
    try:
        with open(_QUEUE_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entrada, ensure_ascii=False) + "\n")
        print(f"🐛 AUTO-REPORTE [{ts}] error en: {label}", flush=True)
    except Exception as e:
        print(f"ERROR al guardar reporte debug: {e}", flush=True)

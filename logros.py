#!/usr/bin/env python3
# logros.py — Sistema de Logros y Medallas
#
# Logros se desbloquean automáticamente al completar hazañas.
# Cada logro da recompensas únicas (oro, XP, título especial).
# Comandos:
#   /logros          — Ver mis logros desbloqueados y progreso
#   /logros_todos    — Ver catálogo completo
#   /logros_top      — Ranking global de jugadores con más logros
#
# Integración: llama a verificar_logros(user_id, contexto) desde otros módulos.

import sqlite3
import json
from datetime import datetime
from typing import Optional, Dict, List, Tuple

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler

import db_helper
import economia

DB_PATH = "aethelgard.db"

def _esc_md(s: str) -> str:
    return str(s).replace("_", "\\_").replace("*", "\\*").replace("`", "\\`").replace("[", "\\[")

# ==================== TABLAS ====================
def _init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS logros_desbloqueados_v2 (
        user_id INTEGER,
        logro_id TEXT,
        fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (user_id, logro_id)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS stats_jugadores (
        user_id INTEGER PRIMARY KEY,
        mazmorras_completadas INTEGER DEFAULT 0,
        victorias_pvp         INTEGER DEFAULT 0,
        derrotas_pvp          INTEGER DEFAULT 0,
        jefes_participados    INTEGER DEFAULT 0,
        jefes_derrotados      INTEGER DEFAULT 0,
        items_crafteados      INTEGER DEFAULT 0,
        recolecciones         INTEGER DEFAULT 0,
        investigaciones       INTEGER DEFAULT 0,
        viajes_realizados     INTEGER DEFAULT 0,
        guerras_facciones     INTEGER DEFAULT 0,
        guerras_gremios       INTEGER DEFAULT 0,
        guerras_ganadas       INTEGER DEFAULT 0,
        subastas_vendidas     INTEGER DEFAULT 0,
        transacciones_p2p     INTEGER DEFAULT 0,
        duelos_ciudad         INTEGER DEFAULT 0,
        oro_total_acumulado   INTEGER DEFAULT 0,
        muertes               INTEGER DEFAULT 0
    )''')
    conn.commit()
    conn.close()

_init_db()

# ==================== CATÁLOGO DE LOGROS ====================
# Estructura de cada logro:
# id, nombre, emoji, descripcion, categoria,
# condicion_campo (columna de stats_jugadores o 'especial'),
# condicion_valor (umbral numérico, o None para logros especiales),
# recompensa_oro, recompensa_xp, recompensa_titulo (None si no hay)

LOGROS: Dict[str, Dict] = {

    # ───── PERSONAJE ─────────────────────────────────────────────
    "nivel_5": {
        "nombre": "Aprendiz Valiente",
        "emoji": "🌱",
        "descripcion": "Alcanza el nivel 5.",
        "categoria": "Personaje",
        "condicion_campo": "nivel",    # campo en tabla jugadores
        "condicion_valor": 5,
        "recompensa_oro": 500,
        "recompensa_xp": 100,
        "recompensa_titulo": None,
    },
    "nivel_10": {
        "nombre": "Aventurero Consagrado",
        "emoji": "⚔️",
        "descripcion": "Alcanza el nivel 10.",
        "categoria": "Personaje",
        "condicion_campo": "nivel",
        "condicion_valor": 10,
        "recompensa_oro": 1500,
        "recompensa_xp": 300,
        "recompensa_titulo": "Aventurero",
    },
    "nivel_25": {
        "nombre": "Héroe en Ascenso",
        "emoji": "🦅",
        "descripcion": "Alcanza el nivel 25.",
        "categoria": "Personaje",
        "condicion_campo": "nivel",
        "condicion_valor": 25,
        "recompensa_oro": 5000,
        "recompensa_xp": 1000,
        "recompensa_titulo": "Héroe",
    },
    "nivel_50": {
        "nombre": "Campeón de Aethelgard",
        "emoji": "🏆",
        "descripcion": "Alcanza el nivel 50.",
        "categoria": "Personaje",
        "condicion_campo": "nivel",
        "condicion_valor": 50,
        "recompensa_oro": 20000,
        "recompensa_xp": 5000,
        "recompensa_titulo": "Campeón",
    },
    "nivel_75": {
        "nombre": "Leyenda Viva",
        "emoji": "🌟",
        "descripcion": "Alcanza el nivel 75.",
        "categoria": "Personaje",
        "condicion_campo": "nivel",
        "condicion_valor": 75,
        "recompensa_oro": 50000,
        "recompensa_xp": 15000,
        "recompensa_titulo": "Leyenda",
    },
    "nivel_100": {
        "nombre": "Inmortal de Aethelgard",
        "emoji": "💫",
        "descripcion": "Alcanza el nivel máximo 100.",
        "categoria": "Personaje",
        "condicion_campo": "nivel",
        "condicion_valor": 100,
        "recompensa_oro": 100000,
        "recompensa_xp": 50000,
        "recompensa_titulo": "Inmortal",
    },
    "primera_reencarnacion": {
        "nombre": "Renacido",
        "emoji": "🔄",
        "descripcion": "Completa tu primera reencarnación.",
        "categoria": "Personaje",
        "condicion_campo": "reencarnaciones",
        "condicion_valor": 1,
        "recompensa_oro": 10000,
        "recompensa_xp": 3000,
        "recompensa_titulo": "Renacido",
    },

    # ───── EXPLORADOR / MAZMORRAS ────────────────────────────────
    "primera_mazmorra": {
        "nombre": "Primera Incursión",
        "emoji": "🌀",
        "descripcion": "Completa tu primera mazmorra.",
        "categoria": "Explorador",
        "condicion_campo": "mazmorras_completadas",
        "condicion_valor": 1,
        "recompensa_oro": 300,
        "recompensa_xp": 100,
        "recompensa_titulo": None,
    },
    "mazmorras_10": {
        "nombre": "Explorador Curtido",
        "emoji": "🗺️",
        "descripcion": "Completa 10 mazmorras.",
        "categoria": "Explorador",
        "condicion_campo": "mazmorras_completadas",
        "condicion_valor": 10,
        "recompensa_oro": 1000,
        "recompensa_xp": 500,
        "recompensa_titulo": None,
    },
    "mazmorras_50": {
        "nombre": "Conquistador de Calabozos",
        "emoji": "🏰",
        "descripcion": "Completa 50 mazmorras.",
        "categoria": "Explorador",
        "condicion_campo": "mazmorras_completadas",
        "condicion_valor": 50,
        "recompensa_oro": 8000,
        "recompensa_xp": 3000,
        "recompensa_titulo": "Conquistador",
    },
    "mazmorras_100": {
        "nombre": "Señor de las Sombras",
        "emoji": "👁️",
        "descripcion": "Completa 100 mazmorras.",
        "categoria": "Explorador",
        "condicion_campo": "mazmorras_completadas",
        "condicion_valor": 100,
        "recompensa_oro": 30000,
        "recompensa_xp": 15000,
        "recompensa_titulo": "Señor de las Sombras",
    },

    # ───── GUERRERO / PvP ─────────────────────────────────────────
    "primera_victoria_pvp": {
        "nombre": "Primer Duelo Ganado",
        "emoji": "⚔️",
        "descripcion": "Gana tu primer combate PvP.",
        "categoria": "Guerrero",
        "condicion_campo": "victorias_pvp",
        "condicion_valor": 1,
        "recompensa_oro": 500,
        "recompensa_xp": 150,
        "recompensa_titulo": None,
    },
    "victorias_pvp_10": {
        "nombre": "Duelista Feroz",
        "emoji": "🗡️",
        "descripcion": "Gana 10 combates PvP.",
        "categoria": "Guerrero",
        "condicion_campo": "victorias_pvp",
        "condicion_valor": 10,
        "recompensa_oro": 3000,
        "recompensa_xp": 800,
        "recompensa_titulo": "Duelista",
    },
    "victorias_pvp_50": {
        "nombre": "Azote del Campo de Batalla",
        "emoji": "💀",
        "descripcion": "Gana 50 combates PvP.",
        "categoria": "Guerrero",
        "condicion_campo": "victorias_pvp",
        "condicion_valor": 50,
        "recompensa_oro": 20000,
        "recompensa_xp": 8000,
        "recompensa_titulo": "Azote",
    },
    "victorias_pvp_100": {
        "nombre": "Terror de Aethelgard",
        "emoji": "☠️",
        "descripcion": "Gana 100 combates PvP.",
        "categoria": "Guerrero",
        "condicion_campo": "victorias_pvp",
        "condicion_valor": 100,
        "recompensa_oro": 75000,
        "recompensa_xp": 25000,
        "recompensa_titulo": "Terror",
    },

    # ───── CAZADOR DE JEFES ──────────────────────────────────────
    "primer_jefe": {
        "nombre": "Cazador de Bestias",
        "emoji": "🐉",
        "descripcion": "Participa en tu primer combate contra un jefe.",
        "categoria": "Jefes",
        "condicion_campo": "jefes_participados",
        "condicion_valor": 1,
        "recompensa_oro": 1000,
        "recompensa_xp": 300,
        "recompensa_titulo": None,
    },
    "jefe_derrotado": {
        "nombre": "Asesino de Dragones",
        "emoji": "🔱",
        "descripcion": "Contribuye a derrotar un jefe raid.",
        "categoria": "Jefes",
        "condicion_campo": "jefes_derrotados",
        "condicion_valor": 1,
        "recompensa_oro": 5000,
        "recompensa_xp": 2000,
        "recompensa_titulo": "Asesino de Dragones",
    },
    "jefes_derrotados_5": {
        "nombre": "Azote de Titanes",
        "emoji": "⚡",
        "descripcion": "Contribuye a derrotar 5 jefes raid.",
        "categoria": "Jefes",
        "condicion_campo": "jefes_derrotados",
        "condicion_valor": 5,
        "recompensa_oro": 25000,
        "recompensa_xp": 10000,
        "recompensa_titulo": "Azote de Titanes",
    },

    # ───── ARTESANO ──────────────────────────────────────────────
    "primer_crafteo": {
        "nombre": "Manos a la Obra",
        "emoji": "🔨",
        "descripcion": "Craftea tu primer objeto.",
        "categoria": "Artesano",
        "condicion_campo": "items_crafteados",
        "condicion_valor": 1,
        "recompensa_oro": 200,
        "recompensa_xp": 50,
        "recompensa_titulo": None,
    },
    "crafteos_10": {
        "nombre": "Aprendiz de Herrero",
        "emoji": "⚒️",
        "descripcion": "Craftea 10 objetos.",
        "categoria": "Artesano",
        "condicion_campo": "items_crafteados",
        "condicion_valor": 10,
        "recompensa_oro": 1000,
        "recompensa_xp": 400,
        "recompensa_titulo": None,
    },
    "crafteos_50": {
        "nombre": "Maestro Artesano",
        "emoji": "🛠️",
        "descripcion": "Craftea 50 objetos.",
        "categoria": "Artesano",
        "condicion_campo": "items_crafteados",
        "condicion_valor": 50,
        "recompensa_oro": 8000,
        "recompensa_xp": 3000,
        "recompensa_titulo": "Maestro Artesano",
    },

    # ───── RECOLECTOR ────────────────────────────────────────────
    "primera_recoleccion": {
        "nombre": "Del Campo a la Mochila",
        "emoji": "⛏️",
        "descripcion": "Realiza tu primera recolección.",
        "categoria": "Recolector",
        "condicion_campo": "recolecciones",
        "condicion_valor": 1,
        "recompensa_oro": 100,
        "recompensa_xp": 30,
        "recompensa_titulo": None,
    },
    "recolecciones_25": {
        "nombre": "Mano de Hierro",
        "emoji": "🪨",
        "descripcion": "Realiza 25 recolecciones.",
        "categoria": "Recolector",
        "condicion_campo": "recolecciones",
        "condicion_valor": 25,
        "recompensa_oro": 1500,
        "recompensa_xp": 500,
        "recompensa_titulo": None,
    },
    "recolecciones_100": {
        "nombre": "Eterno Recolector",
        "emoji": "💎",
        "descripcion": "Realiza 100 recolecciones.",
        "categoria": "Recolector",
        "condicion_campo": "recolecciones",
        "condicion_valor": 100,
        "recompensa_oro": 10000,
        "recompensa_xp": 4000,
        "recompensa_titulo": "Recolector Eterno",
    },

    # ───── INVESTIGADOR ──────────────────────────────────────────
    "primera_investigacion": {
        "nombre": "Mente Curiosa",
        "emoji": "🔬",
        "descripcion": "Completa tu primera investigación.",
        "categoria": "Investigador",
        "condicion_campo": "investigaciones",
        "condicion_valor": 1,
        "recompensa_oro": 200,
        "recompensa_xp": 80,
        "recompensa_titulo": None,
    },
    "investigaciones_20": {
        "nombre": "Erudito de Aethelgard",
        "emoji": "📚",
        "descripcion": "Completa 20 investigaciones.",
        "categoria": "Investigador",
        "condicion_campo": "investigaciones",
        "condicion_valor": 20,
        "recompensa_oro": 5000,
        "recompensa_xp": 2000,
        "recompensa_titulo": "Erudito",
    },

    # ───── VIAJERO ───────────────────────────────────────────────
    "primer_viaje": {
        "nombre": "Pies en la Ruta",
        "emoji": "🗺️",
        "descripcion": "Completa tu primer viaje.",
        "categoria": "Viajero",
        "condicion_campo": "viajes_realizados",
        "condicion_valor": 1,
        "recompensa_oro": 150,
        "recompensa_xp": 50,
        "recompensa_titulo": None,
    },
    "viajes_50": {
        "nombre": "Nómada Incansable",
        "emoji": "🌍",
        "descripcion": "Completa 50 viajes.",
        "categoria": "Viajero",
        "condicion_campo": "viajes_realizados",
        "condicion_valor": 50,
        "recompensa_oro": 7000,
        "recompensa_xp": 2500,
        "recompensa_titulo": "Nómada",
    },

    # ───── GREMIO ────────────────────────────────────────────────
    "gremio_nivel_5": {
        "nombre": "Gremio en Auge",
        "emoji": "🏛️",
        "descripcion": "Tu gremio alcanza el nivel 5.",
        "categoria": "Gremio",
        "condicion_campo": "especial_gremio_nivel",
        "condicion_valor": 5,
        "recompensa_oro": 3000,
        "recompensa_xp": 1000,
        "recompensa_titulo": None,
    },
    "gremio_nivel_10": {
        "nombre": "Legado Legendario",
        "emoji": "👑",
        "descripcion": "Tu gremio alcanza el nivel máximo (10).",
        "categoria": "Gremio",
        "condicion_campo": "especial_gremio_nivel",
        "condicion_valor": 10,
        "recompensa_oro": 20000,
        "recompensa_xp": 10000,
        "recompensa_titulo": "Fundador Legendario",
    },

    # ───── GUERRAS ───────────────────────────────────────────────
    "guerra_facciones_participar": {
        "nombre": "Soldado de Facción",
        "emoji": "🔥",
        "descripcion": "Participa en tu primera guerra de facciones.",
        "categoria": "Guerras",
        "condicion_campo": "guerras_facciones",
        "condicion_valor": 1,
        "recompensa_oro": 500,
        "recompensa_xp": 200,
        "recompensa_titulo": None,
    },
    "guerra_gremio_participar": {
        "nombre": "Soldado del Gremio",
        "emoji": "⚔️",
        "descripcion": "Participa en tu primera guerra de gremios.",
        "categoria": "Guerras",
        "condicion_campo": "guerras_gremios",
        "condicion_valor": 1,
        "recompensa_oro": 500,
        "recompensa_xp": 200,
        "recompensa_titulo": None,
    },
    "guerras_ganadas_3": {
        "nombre": "Conquistador de Guerras",
        "emoji": "🎖️",
        "descripcion": "Gana 3 guerras (facciones o gremios).",
        "categoria": "Guerras",
        "condicion_campo": "guerras_ganadas",
        "condicion_valor": 3,
        "recompensa_oro": 15000,
        "recompensa_xp": 6000,
        "recompensa_titulo": "Conquistador",
    },

    # ───── ECONOMISTA ────────────────────────────────────────────
    "oro_1000": {
        "nombre": "Primera Fortuna",
        "emoji": "🪙",
        "descripcion": "Acumula 1.000 de oro total a lo largo del juego.",
        "categoria": "Economista",
        "condicion_campo": "oro_total_acumulado",
        "condicion_valor": 1000,
        "recompensa_oro": 0,
        "recompensa_xp": 100,
        "recompensa_titulo": None,
    },
    "oro_50000": {
        "nombre": "Mercader Próspero",
        "emoji": "💰",
        "descripcion": "Acumula 50.000 de oro total.",
        "categoria": "Economista",
        "condicion_campo": "oro_total_acumulado",
        "condicion_valor": 50000,
        "recompensa_oro": 0,
        "recompensa_xp": 2000,
        "recompensa_titulo": "Mercader",
    },
    "oro_500000": {
        "nombre": "Barón del Oro",
        "emoji": "💎",
        "descripcion": "Acumula 500.000 de oro total.",
        "categoria": "Economista",
        "condicion_campo": "oro_total_acumulado",
        "condicion_valor": 500000,
        "recompensa_oro": 0,
        "recompensa_xp": 15000,
        "recompensa_titulo": "Barón del Oro",
    },

    # ───── SUPERVIVIENTE ─────────────────────────────────────────
    "sin_morir": {
        "nombre": "Intocable",
        "emoji": "🛡️",
        "descripcion": "Alcanza el nivel 20 sin morir ninguna vez.",
        "categoria": "Superviviente",
        "condicion_campo": "especial_sin_morir",
        "condicion_valor": None,
        "recompensa_oro": 10000,
        "recompensa_xp": 5000,
        "recompensa_titulo": "Intocable",
    },
}

# Agrupación por categorías (para mostrar)
CATEGORIAS_ORDEN = [
    "Personaje", "Explorador", "Guerrero", "Jefes",
    "Artesano", "Recolector", "Investigador", "Viajero",
    "Gremio", "Guerras", "Economista", "Superviviente",
]

# ==================== STATS HELPERS ====================
def obtener_stats(user_id: int) -> Dict:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM stats_jugadores WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return dict(row)
    return {}

def _ensure_stats_row(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO stats_jugadores (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()

def sumar_stat(user_id: int, campo: str, cantidad: int = 1):
    """Suma al contador de estadística y luego verifica logros."""
    _ensure_stats_row(user_id)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(f"UPDATE stats_jugadores SET {campo} = {campo} + ? WHERE user_id = ?", (cantidad, user_id))
    conn.commit()
    conn.close()

def obtener_logros_desbloqueados(user_id: int) -> List[str]:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT logro_id FROM logros_desbloqueados_v2 WHERE user_id = ?", (user_id,))
    rows = c.fetchall()
    conn.close()
    return [r[0] for r in rows]

def _ya_tiene_logro(user_id: int, logro_id: str) -> bool:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT 1 FROM logros_desbloqueados_v2 WHERE user_id = ? AND logro_id = ?", (user_id, logro_id))
    r = c.fetchone()
    conn.close()
    return r is not None

def _guardar_logro(user_id: int, logro_id: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO logros_desbloqueados_v2 (user_id, logro_id, fecha) VALUES (?, ?, ?)",
              (user_id, logro_id, datetime.now().isoformat()))
    conn.commit()
    conn.close()

# ==================== CORE: VERIFICAR LOGROS ====================
def verificar_logros(user_id: int, contexto_extra: Optional[Dict] = None) -> List[str]:
    """
    Verifica todos los logros del jugador y desbloquea los que correspondan.
    Retorna lista de IDs de logros recién desbloqueados.
    Llamar desde cualquier módulo después de una acción significativa.
    contexto_extra: dict opcional con {'gremio_nivel': X, 'sin_morir': bool}
    """
    if not db_helper.existe_jugador(user_id):
        return []

    _ensure_stats_row(user_id)
    jug    = db_helper.obtener_jugador(user_id)
    stats  = obtener_stats(user_id)
    recien = []

    # Combinar jugador + stats en un solo dict de consulta
    data = {**stats, **jug}
    if contexto_extra:
        data.update(contexto_extra)

    for logro_id, logro in LOGROS.items():
        if _ya_tiene_logro(user_id, logro_id):
            continue

        campo = logro["condicion_campo"]
        valor = logro["condicion_valor"]

        cumple = False

        if campo.startswith("especial_"):
            # Logros especiales: necesitan contexto externo
            if campo == "especial_gremio_nivel" and "gremio_nivel" in data:
                cumple = data["gremio_nivel"] >= valor
            elif campo == "especial_sin_morir":
                cumple = (data.get("nivel", 0) >= 20) and (data.get("muertes", 999) == 0)
        elif valor is not None:
            val_actual = data.get(campo, 0) or 0
            cumple = int(val_actual) >= int(valor)

        if cumple:
            _entregar_logro(user_id, logro_id, logro, jug)
            recien.append(logro_id)

    return recien

def _entregar_logro(user_id: int, logro_id: str, logro: Dict, jug: Dict):
    """Registra el logro, da recompensas y envía notificación."""
    _guardar_logro(user_id, logro_id)

    oro = logro.get("recompensa_oro", 0)
    xp  = logro.get("recompensa_xp",  0)
    titulo = logro.get("recompensa_titulo")

    if oro > 0:
        economia.modificar_saldo(user_id, "oro", oro, f"logro_{logro_id}")
    if xp > 0:
        nueva_xp = (jug.get("experiencia") or 0) + xp
        db_helper.actualizar_jugador(user_id, experiencia=nueva_xp)
    if titulo:
        logros_actuales = json.loads(jug.get("logros_desbloqueados") or "[]")
        if titulo not in logros_actuales:
            logros_actuales.append(titulo)
            db_helper.actualizar_jugador(user_id, logros_desbloqueados=json.dumps(logros_actuales))

    # Notificación en bandeja del juego
    recompensas_txt = ""
    partes = []
    if oro > 0:  partes.append(f"+{oro:,} oro")
    if xp  > 0:  partes.append(f"+{xp:,} XP")
    if titulo:   partes.append(f"título '{titulo}'")
    if partes:   recompensas_txt = " | ".join(partes)

    db_helper.agregar_notificacion(
        user_id,
        f"🏅 *¡LOGRO DESBLOQUEADO!*\n"
        f"{logro['emoji']} {logro['nombre']}\n"
        f"📜 {logro['descripcion']}\n"
        + (f"🎁 Recompensa: {recompensas_txt}" if recompensas_txt else "")
    )

# ==================== REGISTRO DE ACCIONES (API pública) ====================
def registrar_mazmorra_completada(user_id: int):
    sumar_stat(user_id, "mazmorras_completadas")
    return verificar_logros(user_id)

def registrar_victoria_pvp(user_id: int):
    sumar_stat(user_id, "victorias_pvp")
    return verificar_logros(user_id)

def registrar_derrota_pvp(user_id: int):
    sumar_stat(user_id, "derrotas_pvp")

def registrar_jefe_participado(user_id: int):
    sumar_stat(user_id, "jefes_participados")
    return verificar_logros(user_id)

def registrar_jefe_derrotado(user_id: int):
    sumar_stat(user_id, "jefes_derrotados")
    return verificar_logros(user_id)

def registrar_crafteo(user_id: int, cantidad: int = 1):
    sumar_stat(user_id, "items_crafteados", cantidad)
    return verificar_logros(user_id)

def registrar_recoleccion(user_id: int):
    sumar_stat(user_id, "recolecciones")
    return verificar_logros(user_id)

def registrar_investigacion(user_id: int):
    sumar_stat(user_id, "investigaciones")
    return verificar_logros(user_id)

def registrar_viaje(user_id: int):
    sumar_stat(user_id, "viajes_realizados")
    return verificar_logros(user_id)

def registrar_guerra_facciones(user_id: int):
    sumar_stat(user_id, "guerras_facciones")
    return verificar_logros(user_id)

def registrar_guerra_gremio(user_id: int):
    sumar_stat(user_id, "guerras_gremios")
    return verificar_logros(user_id)

def registrar_guerra_ganada(user_id: int):
    sumar_stat(user_id, "guerras_ganadas")
    return verificar_logros(user_id)

def registrar_oro_acumulado(user_id: int, cantidad: int):
    if cantidad > 0:
        sumar_stat(user_id, "oro_total_acumulado", cantidad)
        return verificar_logros(user_id)
    return []

def registrar_muerte(user_id: int):
    sumar_stat(user_id, "muertes")

def verificar_logros_nivel(user_id: int):
    """Llamar cuando el jugador sube de nivel."""
    return verificar_logros(user_id)

def verificar_logros_gremio(user_id: int, nivel_gremio: int):
    """Llamar cuando el gremio del jugador sube de nivel."""
    return verificar_logros(user_id, contexto_extra={"gremio_nivel": nivel_gremio})

# ==================== COMANDOS BOT ====================

def _texto_barra_progreso(actual: int, meta: int, largo: int = 10) -> str:
    if meta <= 0:
        return "✅"
    pct = min(1.0, actual / meta)
    llenos = int(pct * largo)
    return "🟦" * llenos + "⬜" * (largo - llenos) + f" {actual}/{meta}"

async def cmd_logros(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra los logros desbloqueados del jugador con progreso."""
    user_id = update.effective_user.id
    try:
        import guia_contextual as _gc
        await _gc.enviar(user_id, context, "logros_menu")
    except Exception:
        pass
    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        await update.effective_message.reply_text("❌ No tienes personaje. Usa /start para crear uno.")
        return

    desbloqueados = set(obtener_logros_desbloqueados(user_id))
    stats = obtener_stats(user_id)
    data  = {**stats, **jug}

    total_logros = len(LOGROS)
    total_desbloqueados = len(desbloqueados)

    # Mostrar por categorías, comprimido
    try:
        pagina = int(context.args[0]) if context.args else 1
    except (ValueError, IndexError):
        pagina = 1
    cats = CATEGORIAS_ORDEN
    cats_por_pagina = 3
    inicio = (pagina - 1) * cats_por_pagina
    cats_pagina = cats[inicio: inicio + cats_por_pagina]

    texto = (
        f"🏅 *Mis Logros — {jug['nombre_personaje']}*\n"
        f"📊 Progreso: {total_desbloqueados}/{total_logros} "
        f"({'%.0f' % (total_desbloqueados/total_logros*100)}%)\n\n"
    )

    for cat in cats_pagina:
        logros_cat = [(lid, l) for lid, l in LOGROS.items() if l["categoria"] == cat]
        if not logros_cat:
            continue
        texto += f"*{cat}*\n"
        for lid, logro in logros_cat:
            if lid in desbloqueados:
                texto += f"  ✅ {logro['emoji']} {logro['nombre']}\n"
            else:
                campo = logro["condicion_campo"]
                meta  = logro["condicion_valor"]
                if campo.startswith("especial_") or meta is None:
                    texto += f"  🔒 {logro['emoji']} {logro['nombre']}\n"
                else:
                    actual = int(data.get(campo, 0) or 0)
                    barra = _texto_barra_progreso(actual, meta, 8)
                    texto += f"  🔒 {logro['emoji']} {logro['nombre']}\n     {barra}\n"
        texto += "\n"

    total_paginas = (len(cats) + cats_por_pagina - 1) // cats_por_pagina
    botones = []
    nav = []
    if pagina > 1:
        nav.append(InlineKeyboardButton("◀️ Anterior", callback_data=f"logros_pag_{pagina-1}"))
    if pagina < total_paginas:
        nav.append(InlineKeyboardButton("Siguiente ▶️", callback_data=f"logros_pag_{pagina+1}"))
    if nav:
        botones.append(nav)
    botones.append([InlineKeyboardButton("🏆 Ranking global", callback_data="logros_ranking")])

    await update.effective_message.reply_text(
        texto,
        reply_markup=InlineKeyboardMarkup(botones) if botones else None,
        parse_mode="Markdown"
    )

async def cmd_logros_todos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lista completa del catálogo de logros disponibles."""
    user_id = update.effective_user.id
    desbloqueados = set(obtener_logros_desbloqueados(user_id))

    try:
        pagina = int(context.args[0]) if context.args else 1
    except (ValueError, IndexError):
        pagina = 1
    todos_ids = list(LOGROS.keys())
    por_pagina = 8
    inicio = (pagina - 1) * por_pagina
    fin = inicio + por_pagina
    pagina_logros = todos_ids[inicio:fin]
    total_paginas = (len(todos_ids) + por_pagina - 1) // por_pagina

    texto = f"📜 *Catálogo de Logros* (pág. {pagina}/{total_paginas})\n\n"
    for lid in pagina_logros:
        logro = LOGROS[lid]
        estado = "✅" if lid in desbloqueados else "🔒"
        rew = []
        if logro["recompensa_oro"]: rew.append(f"{logro['recompensa_oro']:,} oro")
        if logro["recompensa_xp"]:  rew.append(f"{logro['recompensa_xp']:,} XP")
        if logro["recompensa_titulo"]: rew.append(f"título '{logro['recompensa_titulo']}'")
        rew_txt = " | ".join(rew) if rew else "—"
        texto += (
            f"{estado} {logro['emoji']} *{_esc_md(logro['nombre'])}*\n"
            f"   _{logro['descripcion']}_\n"
            f"   🎁 {rew_txt}\n\n"
        )

    nav = []
    if pagina > 1:
        nav.append(InlineKeyboardButton("◀️", callback_data=f"logros_todos_pag_{pagina-1}"))
    if pagina < total_paginas:
        nav.append(InlineKeyboardButton("▶️", callback_data=f"logros_todos_pag_{pagina+1}"))
    botones = [nav] if nav else []

    await update.effective_message.reply_text(
        texto,
        reply_markup=InlineKeyboardMarkup(botones) if botones else None,
        parse_mode="Markdown"
    )

async def cmd_logros_top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ranking global de jugadores con más logros desbloqueados."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(
        "SELECT user_id, COUNT(*) as total FROM logros_desbloqueados_v2 "
        "GROUP BY user_id ORDER BY total DESC LIMIT 10"
    )
    rows = c.fetchall()
    conn.close()

    if not rows:
        await update.effective_message.reply_text("Aún no hay jugadores con logros desbloqueados.")
        return

    medallas = ["🥇", "🥈", "🥉"] + ["🏅"] * 7
    texto = "🏆 *Ranking Global de Logros*\n\n"
    for i, row in enumerate(rows):
        jug = db_helper.obtener_jugador(row["user_id"])
        nombre = jug["nombre_personaje"] if jug else f"Jugador {row['user_id']}"
        pct = int(row["total"] / len(LOGROS) * 100)
        texto += f"{medallas[i]} {nombre}: {row['total']}/{len(LOGROS)} ({pct}%)\n"

    await update.effective_message.reply_text(texto, parse_mode="Markdown")

# ==================== CALLBACKS ====================
async def cb_logros(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("logros_pag_"):
        try:
            pagina = int(data.split("_")[-1])
        except (ValueError, IndexError):
            pagina = 1
        context.args = [str(pagina)]
        await cmd_logros(update, context)
    elif data.startswith("logros_todos_pag_"):
        try:
            pagina = int(data.split("_")[-1])
        except (ValueError, IndexError):
            pagina = 1
        context.args = [str(pagina)]
        await cmd_logros_todos(update, context)
    elif data == "logros_ranking":
        context.args = []
        await cmd_logros_top(update, context)

# ==================== REGISTRO DE HANDLERS ====================
def registrar_handlers(app):
    app.add_handler(CommandHandler("logros",       cmd_logros))
    app.add_handler(CommandHandler("logros_todos", cmd_logros_todos))
    app.add_handler(CommandHandler("logros_top",   cmd_logros_top))
    app.add_handler(CallbackQueryHandler(cb_logros, pattern=r"^logros_"))

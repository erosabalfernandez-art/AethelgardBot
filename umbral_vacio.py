#!/usr/bin/env python3
# umbral_vacio.py — Sistema del Umbral del Vacío (Aethelgard)
#
# Mecánica global:
#   La corrupción sube cada día. A 80% los jugadores ven el panel del Umbral.
#   A 100% comienza una cuenta regresiva de 4 horas con mensajes de lore por hora.
#   Después ocurre la Noche del Vacío: 3 monstruos facción por facción, luego
#   un jefe final invencible que toda la comunidad debe repeler.
#   Si los monstruos no son derrotados → escasez global (precios altos, subastas
#   P2P y bolsa desactivadas por N días).

import sqlite3
import random
import asyncio
import os
import logging
from datetime import datetime, timedelta
from typing import Optional

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
import db_helper

logger = logging.getLogger(__name__)

DB_PATH   = "aethelgard.db"
FACCIONES = ["Alianza", "Imperio", "Sindicato"]

# ── Lore de la cuenta regresiva (4 mensajes, uno cada hora) ──────────────────

_LORE_CUENTA = [
    # hora 0 → mensaje al llegar a 100% (0 horas de countdown cumplidas)
    (
        "🌑✨💀✨🌑\n\n"
        "*— Las Crónicas del Vacío, Capítulo Final —*\n\n"
        "Un temblor inexplicable recorre la tierra de Aethelgard... "
        "Los ancianos miran el cielo con terror en los ojos.\n\n"
        "Las estrellas están desapareciendo. Una a una, borradas por una "
        "oscuridad sin nombre que se extiende desde el horizonte.\n\n"
        "💀 *La corrupción ha alcanzado su umbral máximo.*\n"
        "El Vacío ha despertado.\n\n"
        "⏳ En *4 horas* la Noche del Vacío caerá sobre el mundo.\n"
        "Preparad vuestras pociones. Afilad vuestras armas.\n"
        "El destino de Aethelgard está en vuestras manos. 🗡️"
    ),
    # hora 1 → mensaje tras 1 hora de countdown
    (
        "⚫🌀⚫🌀⚫\n\n"
        "*— Segundo presagio del Fin —*\n\n"
        "Las sombras se mueven donde no deberían moverse. "
        "Los monstruos de las zonas salvajes... huyen. "
        "Eso nunca había ocurrido antes en la historia de Aethelgard.\n\n"
        "Algo mucho más terrible se acerca desde el más allá del velo.\n\n"
        "🔮 *Los tres reinos sienten el miedo en sus entrañas.*\n"
        "Alianza, Imperio y Sindicato: todos son presas esta noche.\n\n"
        "⏳ Quedan *3 horas* para la Noche del Vacío.\n"
        "Tomad vuestras pociones de vida. 🧪 Cambiad vuestro armamento. ⚔️\n"
        "El mundo necesita de sus héroes."
    ),
    # hora 2
    (
        "🌀💀⚡💀🌀\n\n"
        "*— El cielo se rasga —*\n\n"
        "El firmamento se tiñe de violeta enfermizo.\n"
        "Grietas de Vacío puro desgarran el horizonte, "
        "vomitando oscuridad sobre los campos y aldeas.\n\n"
        "Los sacerdotes de los tres reinos entonan sus últimas profecías:\n"
        "*\"¡EL DEVORADOR VIENE! ¡EL DEVORADOR VIENE!\"*\n\n"
        "🔴 Las tiendas cierran. Los mercados se vacían.\n"
        "Las subastas y los mercados P2P cierran sus puertas por seguridad.\n\n"
        "⏳ *2 horas* quedan antes del apocalipsis.\n"
        "Solo los valientes permanecen en pie. 🛡️\n"
        "Usad /umbral para preparar vuestra estrategia."
    ),
    # hora 3
    (
        "🔴💥🔴💥🔴\n\n"
        "*¡— ÚLTIMO AVISO — EL FIN ES INMINENTE —!*\n\n"
        "Los cielos ARDEN. La tierra TIEMBLA bajo vuestros pies.\n"
        "El Vacío ya es visible a simple vista:\n"
        "un agujero negro en el corazón del cielo de Aethelgard, "
        "devorando la luz de las estrellas.\n\n"
        "💀💀💀\n\n"
        "⚠️ En *1 HORA* comenzará la Noche del Vacío.\n"
        "Cuando llegue, *criaturas del Vacío* atacarán cada facción.\n\n"
        "🏹 Cada facción tendrá su propia bestia que derrotar.\n"
        "⚔️ Los jugadores podrán atacar hasta *3 veces*.\n"
        "🧪 Entre rondas podréis tomar pociones y cambiar armamento.\n\n"
        "¡ESTAD LISTOS, GUERREROS DE AETHELGARD! 🌑"
    ),
]

# ── DB ────────────────────────────────────────────────────────────────────────

def _init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS umbral_config (
            clave TEXT PRIMARY KEY,
            valor TEXT NOT NULL DEFAULT ''
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS umbral_contribuciones (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            tipo    TEXT    NOT NULL,
            valor   INTEGER NOT NULL DEFAULT 0,
            ts      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS umbral_ataques (
            user_id       INTEGER NOT NULL,
            monstruo_id   INTEGER NOT NULL,
            ataques_usados INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, monstruo_id)
        )
    """)
    # Valores por defecto
    defaults = {
        "corrupcion":             "0",
        "estado":                 "normal",
        "modo_auto":              "1",
        "tasa_diaria":            "3",
        "cuenta_regresiva_inicio":"",
        "notif_hora":             "-1",
        "escasez_dias_restantes": "0",
        "escasez_inicio":         "",
        "monstruo_actual_faccion":"",
        "monstruo_actual_id":     "0",
        "monstruo_actual_hp":        "0",
        "monstruo_actual_hp_max":    "0",
        "monstruo_ronda_actual":     "1",
        "monstruos_derrotados":      "0",
        "jefe_hp":                   "0",
        "jefe_hp_max":               "0",
        "jefe_ronda_actual":         "1",
        "multiplicador_precios":     "2.0",
        "max_ataques_jugador":       "3",
        "hp_monstruo_base":          "3000",
        "hp_jefe_base":              "15000",
        "rondas_monstruo":           "3",
        "rondas_jefe":               "5",
        "tiempo_ronda_min":          "15",
        "jugadores_atacados_mon":    "5",
        "jugadores_atacados_jefe":   "15",
        "min_jugadores_monstruo":    "3",
        # ── Escasez acumulada ─────────────────────────────────────────────────
        "dias_escasez_por_monstruo": "1",
        "dias_escasez_jefe":         "2",
        "escasez_acumulada":         "0",
        # ── Escalado HP por stats de jugadores ────────────────────────────────
        "hp_monstruo_override":      "0",   # 0 = calculado; >0 = override fijo
        "hp_jefe_override":          "0",
        "mult_escalado_mon":         "30",  # HP_mon  = avg_atk × n_jugadores × mult
        "mult_escalado_jefe":        "50",  # HP_jefe = avg_atk × n_totales × mult
        # ── Tiempos de ronda ─────────────────────────────────────────────────
        "duracion_ronda_minutos":    "30",  # minutos de ventana de ataque
        "entre_rondas_minutos":      "5",   # minutos de pausa entre rondas
        "ronda_fin_en":              "",    # ISO timestamp fin de ronda actual
        # ── Aparición del jefe final ──────────────────────────────────────────
        # 1 = el jefe aparece si los 3 monstruos son derrotados (comportamiento original)
        # 0 = victoria directa si los 3 monstruos mueren (sin jefe final)
        "jefe_auto":                 "1",
        # ── ATK override de monstruos y jefe (daño de contraataque) ──────────
        # 0 = calculado automáticamente (nivel/stats jugadores)
        "atk_monstruo_override":     "0",
        "atk_jefe_override":         "0",
    }
    for k, v in defaults.items():
        c.execute("INSERT OR IGNORE INTO umbral_config (clave, valor) VALUES (?, ?)", (k, v))
    conn.commit()
    conn.close()

_init_db()

# ── Helpers de config ─────────────────────────────────────────────────────────

def _get(clave: str, default: str = "") -> str:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT valor FROM umbral_config WHERE clave = ?", (clave,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else default

def _set(clave: str, valor):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO umbral_config (clave, valor) VALUES (?, ?)", (clave, str(valor)))
    conn.commit()
    conn.close()

def _geti(clave: str, default: int = 0) -> int:
    try:
        return int(_get(clave, str(default)))
    except (ValueError, TypeError):
        return default

def _getf(clave: str, default: float = 1.0) -> float:
    try:
        return float(_get(clave, str(default)))
    except (ValueError, TypeError):
        return default

# ── API pública (importable desde otros módulos) ──────────────────────────────

def get_corrupcion() -> int:
    return min(100, max(0, _geti("corrupcion", 0)))

def get_estado() -> str:
    return _get("estado", "normal")

def hay_escasez_activa() -> bool:
    return get_estado() == "escasez"

def get_multiplicador_precios() -> float:
    if not hay_escasez_activa():
        return 1.0
    return max(1.0, _getf("multiplicador_precios", 2.0))

def _aviso_escasez() -> str:
    return (
        "\n\n⚠️ *Escasez Global activa* — los precios están aumentados "
        "por la Noche del Vacío."
    )

# ── Escalado de HP por stats reales de jugadores ─────────────────────────────

def _calcular_hp_monstruo(faccion: str) -> int:
    """HP del monstruo escalado por ATK medio de la facción. Respeta override."""
    override = _geti("hp_monstruo_override", 0)
    if override > 0:
        return override
    try:
        jugadores = db_helper.obtener_todos_jugadores()
        miembros  = [j for j in jugadores if j.get("faccion") == faccion]
        if not miembros:
            return _geti("hp_monstruo_base", 3000)
        avg_atk = sum(j.get("ataque", 50) or 50 for j in miembros) / len(miembros)
        mult    = _getf("mult_escalado_mon", 30.0)
        return max(500, int(avg_atk * len(miembros) * mult))
    except Exception:
        return _geti("hp_monstruo_base", 3000)

def _calcular_hp_jefe() -> int:
    """HP del jefe escalado por ATK medio de todos los jugadores. Respeta override."""
    override = _geti("hp_jefe_override", 0)
    if override > 0:
        return override
    try:
        jugadores = db_helper.obtener_todos_jugadores()
        if not jugadores:
            return _geti("hp_jefe_base", 15000)
        avg_atk = sum(j.get("ataque", 50) or 50 for j in jugadores) / len(jugadores)
        mult    = _getf("mult_escalado_jefe", 50.0)
        return max(1000, int(avg_atk * len(jugadores) * mult))
    except Exception:
        return _geti("hp_jefe_base", 15000)

def _preview_stats_mon(faccion: str) -> str:
    """Texto informativo con los stats calculados para el monstruo de esa facción."""
    try:
        jugadores = db_helper.obtener_todos_jugadores()
        miembros  = [j for j in jugadores if j.get("faccion") == faccion]
        n = len(miembros)
        avg_atk = (sum(j.get("ataque", 50) or 50 for j in miembros) / n) if n else 0
        mult = _getf("mult_escalado_mon", 30.0)
        hp_calc = max(500, int(avg_atk * n * mult)) if n else 0
        ov = _geti("hp_monstruo_override", 0)
        hp_final = ov if ov > 0 else hp_calc
        return (f"  {faccion}: {n} jugadores | ATK medio {avg_atk:.0f} "
                f"→ HP calc {hp_calc:,} | HP usado: {hp_final:,}")
    except Exception:
        return f"  {faccion}: error al calcular"

def _preview_stats_jefe() -> str:
    """Texto informativo con los stats calculados para el jefe final."""
    try:
        jugadores = db_helper.obtener_todos_jugadores()
        n = len(jugadores)
        avg_atk = (sum(j.get("ataque", 50) or 50 for j in jugadores) / n) if n else 0
        mult = _getf("mult_escalado_jefe", 50.0)
        hp_calc = max(1000, int(avg_atk * n * mult)) if n else 0
        ov = _geti("hp_jefe_override", 0)
        hp_final = ov if ov > 0 else hp_calc
        return (f"  {n} jugadores totales | ATK medio {avg_atk:.0f} "
                f"→ HP calc {hp_calc:,} | HP usado: {hp_final:,}")
    except Exception:
        return "  error al calcular"

# ── Contribuciones ────────────────────────────────────────────────────────────

def _registrar_contribucion(user_id: int, tipo: str, valor: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO umbral_contribuciones (user_id, tipo, valor) VALUES (?, ?, ?)",
        (user_id, tipo, valor)
    )
    conn.commit()
    conn.close()

def _top_contribuyentes(n: int = 10) -> list:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
        SELECT user_id, SUM(valor) as total
        FROM umbral_contribuciones
        GROUP BY user_id
        ORDER BY total DESC
        LIMIT ?
    """, (n,))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ── Ataques a monstruo/jefe ───────────────────────────────────────────────────

def _ataques_usados(user_id: int, monstruo_id: int) -> int:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT ataques_usados FROM umbral_ataques WHERE user_id = ? AND monstruo_id = ?",
        (user_id, monstruo_id)
    )
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0

def _registrar_ataque(user_id: int, monstruo_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO umbral_ataques (user_id, monstruo_id, ataques_usados)
        VALUES (?, ?, 1)
        ON CONFLICT(user_id, monstruo_id) DO UPDATE SET ataques_usados = ataques_usados + 1
    """, (user_id, monstruo_id))
    conn.commit()
    conn.close()

# ── Broadcast helpers ─────────────────────────────────────────────────────────

async def _broadcast(bot, mensaje: str, faccion: Optional[str] = None):
    """Envía un mensaje a todos los jugadores (o solo a la facción indicada)."""
    jugadores = db_helper.obtener_todos_jugadores()
    for jug in jugadores:
        if faccion and jug.get("faccion") != faccion:
            continue
        try:
            await bot.send_message(
                chat_id=jug["user_id"],
                text=mensaje,
                parse_mode="Markdown"
            )
        except Exception:
            pass
        await asyncio.sleep(0.05)

# ── Inicio de monstruo ────────────────────────────────────────────────────────

async def _iniciar_monstruo(bot, faccion: str):
    """Convoca el monstruo de la facción indicada y notifica a sus jugadores."""
    mon_id   = _geti("monstruo_actual_id", 0) + 1
    hp_max   = _calcular_hp_monstruo(faccion)
    dur_min  = _geti("duracion_ronda_minutos", 30)
    _set("monstruo_actual_id",      mon_id)
    _set("monstruo_actual_faccion", faccion)
    _set("monstruo_actual_hp",      hp_max)
    _set("monstruo_actual_hp_max",  hp_max)
    _set("monstruo_ronda_actual",   1)
    _set("estado",                  "noche_vacio")
    _set("ronda_fin_en",            (datetime.now() + timedelta(minutes=dur_min)).isoformat())

    nombres = {
        "Alianza":   "El Devorador de Luz",
        "Imperio":   "El Señor de las Sombras",
        "Sindicato": "El Corruptor Eterno",
    }
    nombre = nombres.get(faccion, "El Monstruo del Vacío")

    msg = (
        f"🌑💀🌑\n\n"
        f"*¡UN MONSTRUO DEL VACÍO HA APARECIDO!*\n\n"
        f"⚫ *{nombre}* ha emergido de las tinieblas para devorar a la facción *{faccion}*.\n\n"
        f"❤️ Vida: *{hp_max:,}* / {hp_max:,}\n"
        f"⚔️ Cada guerrero puede atacar hasta *{_geti('max_ataques_jugador', 3)} veces*.\n"
        f"🧪 Entre rondas podéis tomar pociones y cambiar armamento.\n\n"
        f"Usa /umbral\\_atacar para luchar contra él.\n\n"
        f"💀 *¡El destino de {faccion} está en vuestras manos!*"
    )
    await _broadcast(bot, msg, faccion=faccion)

async def _iniciar_jefe_final(bot):
    """Convoca el jefe final cuando los 3 monstruos caen (o cuando el admin lo invoca)."""
    hp_max  = _calcular_hp_jefe()
    mon_id  = _geti("monstruo_actual_id", 0) + 1
    dur_min = _geti("duracion_ronda_minutos", 30)
    _set("monstruo_actual_id",    mon_id)
    _set("monstruo_actual_faccion", "todos")
    _set("jefe_hp",               hp_max)
    _set("jefe_hp_max",           hp_max)
    _set("jefe_ronda_actual",     1)
    _set("estado",                "jefe_final")
    _set("ronda_fin_en",          (datetime.now() + timedelta(minutes=dur_min)).isoformat())

    msg = (
        "💀🌑⚡🌑💀\n\n"
        "*¡¡EL JEFE FINAL DEL VACÍO HA APARECIDO!!*\n\n"
        "Los tres monstruos faccionarios han caído... pero eso solo era el preludio.\n\n"
        "🌌 *El Dios del Vacío — Aetheron el Devorador* ha descendido sobre Aethelgard.\n"
        "No puede ser destruido. Solo puede ser *repelido* con el esfuerzo "
        "de TODA la comunidad.\n\n"
        f"❤️ Vida: *{hp_max:,}*\n"
        f"⚔️ Cada guerrero puede atacar hasta *{_geti('max_ataques_jugador', 3)} veces*.\n\n"
        "Usa /umbral\\_atacar para unirte a la batalla.\n\n"
        "🌍 *¡TODA AETHELGARD DEBE LUCHAR UNIDA!* 🌍"
    )
    await _broadcast(bot, msg)

async def _resolver_escasez(bot, victoria: bool):
    """Termina la noche: victoria (jefe derrotado) o escasez acumulada."""
    _set("ronda_fin_en", "")
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM umbral_ataques")
    conn.commit()
    conn.close()

    if victoria:
        _set("estado",                 "normal")
        _set("corrupcion",             "0")
        _set("monstruos_derrotados",   "0")
        _set("escasez_acumulada",      "0")
        _set("escasez_dias_restantes", "0")

        # Recompensas para top contribuyentes
        tops = _top_contribuyentes(5)
        recompensas = ""
        for i, t in enumerate(tops, 1):
            jug = db_helper.obtener_jugador(t["user_id"])
            nombre = jug["nombre_personaje"] if jug else str(t["user_id"])
            import economia
            economia.modificar_saldo(t["user_id"], "oro", 5000, "recompensa umbral vacio")
            economia.modificar_saldo(t["user_id"], "eternium", 100, "recompensa umbral vacio")
            recompensas += f"  {i}. {nombre} — {t['total']:,} pts\n"

        msg = (
            "🌅✨🌅\n\n"
            "*¡VICTORIA! — El Vacío ha sido repelido*\n\n"
            "Los guerreros de Aethelgard han dado todo lo que tenían. "
            "El Dios del Vacío retrocede hacia las tinieblas, "
            "maldiciendo a quienes se atrevieron a resistir.\n\n"
            "🌟 La corrupción se reinicia. El mundo respira de nuevo.\n\n"
            "🏆 *Los héroes más destacados de esta noche:*\n"
            f"{recompensas}\n"
            "Cada uno recibe *5.000 oro* y *100 eternium* de recompensa. 🎁\n\n"
            "El ciclo comienza de nuevo... ¿cuánto tardaréis en detenerlo? 🌑"
        )
        # Notificar al admin para premios especiales adicionales
        try:
            import superadmin as _sa
            tops_ext = _top_contribuyentes(20)
            ganadores_pp = []
            for t in tops_ext:
                jug = db_helper.obtener_jugador(t["user_id"])
                nombre = jug["nombre_personaje"] if jug else str(t["user_id"])
                ganadores_pp.append({
                    "user_id": t["user_id"],
                    "nombre":  nombre,
                    "score":   t["total"],
                    "oro":     5000,
                    "xp":      0,
                })
            if ganadores_pp:
                import asyncio as _aio
                _aio.create_task(_sa.notificar_admin_victoria(
                    bot,
                    "umbral_vacio",
                    "Noche del Vacío — Jefe Final repelido",
                    ganadores_pp
                ))
        except Exception:
            pass
    else:
        # Acumular días por el jefe no derrotado
        dias_jefe = _geti("dias_escasez_jefe", 2)
        acum      = _geti("escasez_acumulada", 0) + dias_jefe
        dias      = max(1, acum)

        _set("estado",                 "escasez")
        _set("escasez_dias_restantes", str(dias))
        _set("escasez_inicio",         datetime.now().isoformat())
        _set("corrupcion",             "0")
        _set("monstruos_derrotados",   "0")
        _set("escasez_acumulada",      "0")

        msg = (
            "💀⚫💀\n\n"
            "*El Vacío ha triunfado esta noche...*\n\n"
            "Los monstruos han arrasado sin encontrar resistencia suficiente.\n"
            "Las aldeas arden. Los campos están devastados.\n\n"
            f"📉 *ESCASEZ GLOBAL activa por {dias} día(s):*\n"
            "• Los precios en todas las tiendas han subido.\n"
            "• Las subastas, el mercado P2P y la bolsa están cerrados.\n"
            "• Los recursos de recolección son escasos.\n\n"
            f"☀️ La escasez terminará en {dias} día(s). La corrupción reinicia al 0%.\n"
            "Preparaos mejor para la próxima vez... 🌑"
        )
    await _broadcast(bot, msg)


async def _monstruo_escapado(bot, faccion: str):
    """Se llama cuando el tiempo de ronda expira y el monstruo de la facción sobrevive."""
    dias_por_mon = _geti("dias_escasez_por_monstruo", 1)
    acum = _geti("escasez_acumulada", 0) + dias_por_mon
    _set("escasez_acumulada", acum)

    nombres = {
        "Alianza":   "El Devorador de Luz",
        "Imperio":   "El Señor de las Sombras",
        "Sindicato": "El Corruptor Eterno",
    }
    nombre = nombres.get(faccion, "El Monstruo del Vacío")

    msg = (
        f"⚫💨 *{nombre}* ha escapado de vuelta al Vacío...\n\n"
        f"La facción *{faccion}* no pudo derrotarlo a tiempo.\n"
        f"📉 Escasez acumulada: *+{dias_por_mon} día(s)* "
        f"(total acumulado: *{acum} día(s)*)\n\n"
        "El siguiente enemigo se aproxima..."
    )
    await _broadcast(bot, msg, faccion=faccion)

    # Avanzar al siguiente monstruo o al jefe
    der = _geti("monstruos_derrotados", 0)
    siguiente_idx = FACCIONES.index(faccion) + 1 if faccion in FACCIONES else len(FACCIONES)
    if siguiente_idx >= len(FACCIONES):
        await _iniciar_jefe_final(bot)
    else:
        await _iniciar_monstruo(bot, FACCIONES[siguiente_idx])

# ── Comprobación diaria de escasez ────────────────────────────────────────────

async def _check_escasez_fin(bot):
    if get_estado() != "escasez":
        return
    dias = _geti("escasez_dias_restantes", 0)
    if dias <= 0:
        _set("estado", "normal")
        await _broadcast(
            bot,
            "☀️ *La Escasez Global ha terminado.*\n\n"
            "Los mercados abren de nuevo. Los precios vuelven a la normalidad.\n"
            "¡La vida regresa a Aethelgard! 🌿"
        )
    else:
        _set("escasez_dias_restantes", dias - 1)

# ── Jobs periódicos ───────────────────────────────────────────────────────────

async def job_corrupcion_diaria(context: ContextTypes.DEFAULT_TYPE):
    """Incrementa la corrupción cada día y dispara eventos si es necesario."""
    estado = get_estado()
    if estado in ("cuenta_regresiva", "noche_vacio", "jefe_final"):
        return

    await _check_escasez_fin(context.bot)

    if get_estado() == "escasez":
        return

    if _get("modo_auto", "1") != "1":
        return

    tasa  = _geti("tasa_diaria", 3)
    actual = get_corrupcion()
    nueva = min(100, actual + tasa)
    _set("corrupcion", nueva)

    if actual < 80 <= nueva:
        await _broadcast(
            context.bot,
            "⚠️🌑⚠️\n\n"
            "*¡AVISO! La Corrupción del Vacío ha alcanzado el 80%*\n\n"
            "El Umbral del Vacío se acerca. El mundo está en peligro.\n"
            "Purificad zonas, matad monstruos, donad a la Caldera del Ritual.\n\n"
            "Usa /umbral para ver el estado completo del evento. 🌑"
        )

    if nueva >= 100 and estado == "alerta":
        await _disparar_cuenta_regresiva(context.bot)
    elif nueva >= 80:
        _set("estado", "alerta")

async def _disparar_cuenta_regresiva(bot):
    """Inicia la cuenta regresiva de 4 horas al llegar a 100%."""
    _set("estado",                 "cuenta_regresiva")
    _set("cuenta_regresiva_inicio", datetime.now().isoformat())
    _set("notif_hora",             "-1")
    # Primer mensaje de lore (hora 0)
    await _broadcast(bot, _LORE_CUENTA[0])
    _set("notif_hora", "0")


async def job_monitor_umbral(context: ContextTypes.DEFAULT_TYPE):
    """Corre cada 5 minutos: gestiona la cuenta regresiva y las noches."""
    estado = get_estado()

    # ── Cuenta regresiva: enviar lore horario y disparar noche ───────────────
    if estado == "cuenta_regresiva":
        inicio_str = _get("cuenta_regresiva_inicio", "")
        if not inicio_str:
            return
        inicio    = datetime.fromisoformat(inicio_str)
        horas_pas = int((datetime.now() - inicio).total_seconds() / 3600)
        notif_ant = _geti("notif_hora", -1)

        if horas_pas >= 4:
            # ¡Empieza la noche!
            _set("monstruos_derrotados", "0")
            await _iniciar_monstruo(context.bot, FACCIONES[0])
        elif horas_pas > notif_ant and horas_pas < len(_LORE_CUENTA):
            await _broadcast(context.bot, _LORE_CUENTA[horas_pas])
            _set("notif_hora", str(horas_pas))
        return

    # ── Comprobación de rondas automáticas en noche/jefe ─────────────────────
    if estado in ("noche_vacio", "jefe_final"):
        await _check_ronda_automatica(context)


async def _check_ronda_automatica(context):
    """Si el tiempo de ronda expiró, avanza automáticamente o hace escapar al monstruo."""
    ronda_fin_str = _get("ronda_fin_en", "")
    if not ronda_fin_str:
        return
    try:
        ronda_fin = datetime.fromisoformat(ronda_fin_str)
    except Exception:
        return

    if datetime.now() < ronda_fin:
        return  # Ronda aún activa

    # La ronda ha expirado
    estado = get_estado()
    bot    = context.bot

    if estado == "noche_vacio":
        ronda     = _geti("monstruo_ronda_actual", 1)
        max_ronda = _geti("rondas_monstruo", 3)
        faccion   = _get("monstruo_actual_faccion", FACCIONES[0])
        hp_actual = _geti("monstruo_actual_hp", 0)

        if hp_actual <= 0:
            return  # Ya fue derrotado por un jugador

        if ronda < max_ronda:
            # Avanzar a la siguiente ronda del mismo monstruo
            nueva   = ronda + 1
            dur_min = _geti("duracion_ronda_minutos", 30)
            _set("monstruo_ronda_actual", nueva)
            _set("ronda_fin_en", (datetime.now() + timedelta(minutes=dur_min)).isoformat())
            await _broadcast(
                bot,
                f"⚔️ *¡Ronda {nueva}/{max_ronda} — Monstruo de {faccion}!*\n\n"
                f"❤️ Vida restante: *{hp_actual:,}*\n"
                f"¡El monstruo vuelve a atacar! Usa /umbral\\_atacar ahora.\n"
                f"🧪 Tomad pociones si las necesitáis.",
                faccion=faccion
            )
        else:
            # Última ronda agotada → el monstruo escapa
            await _monstruo_escapado(bot, faccion)

    elif estado == "jefe_final":
        ronda     = _geti("jefe_ronda_actual", 1)
        max_ronda = _geti("rondas_jefe", 5)
        hp_actual = _geti("jefe_hp", 0)

        if hp_actual <= 0:
            return  # Ya fue derrotado

        if ronda < max_ronda:
            nueva   = ronda + 1
            dur_min = _geti("duracion_ronda_minutos", 30)
            _set("jefe_ronda_actual", nueva)
            _set("ronda_fin_en", (datetime.now() + timedelta(minutes=dur_min)).isoformat())
            await _broadcast(
                bot,
                f"⚡ *¡Ronda {nueva}/{max_ronda} — El Jefe Final contraataca!*\n\n"
                f"❤️ Vida restante: *{hp_actual:,}*\n"
                "¡Toda Aethelgard debe seguir atacando! Usa /umbral\\_atacar"
            )
        else:
            # Últimas rondas del jefe agotadas → derrota global
            await _resolver_escasez(bot, victoria=False)


# ── COMANDOS DE JUGADORES ─────────────────────────────────────────────────────

async def cmd_corrupcion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/corrupcion — Muestra el nivel de corrupción global."""
    jug = db_helper.obtener_jugador(update.effective_user.id)
    if not jug:
        await update.effective_message.reply_text("❌ Primero crea tu personaje con /start.")
        return

    corr   = get_corrupcion()
    estado = get_estado()
    barra  = _barra_progreso(corr, 20)

    if estado == "normal" and corr < 80:
        desc = "🌿 El mundo está relativamente en calma."
    elif estado in ("normal", "alerta") and corr < 100:
        desc = "⚠️ El Vacío avanza. ¡Purificad el mundo antes de que sea demasiado tarde!"
    elif estado == "cuenta_regresiva":
        inicio_str = _get("cuenta_regresiva_inicio", "")
        if inicio_str:
            inicio = datetime.fromisoformat(inicio_str)
            restante = timedelta(hours=4) - (datetime.now() - inicio)
            h, rem  = divmod(int(restante.total_seconds()), 3600)
            m       = rem // 60
            desc    = f"💀 *LA NOCHE DEL VACÍO LLEGA EN {h}h {m}min*"
        else:
            desc = "💀 La Noche del Vacío es inminente."
    elif estado == "noche_vacio":
        faccion = _get("monstruo_actual_faccion", "")
        desc = f"🌑 *NOCHE DEL VACÍO ACTIVA* — El monstruo de *{faccion}* está siendo combatido."
    elif estado == "jefe_final":
        desc = "⚡ *JEFE FINAL ACTIVO* — ¡Toda Aethelgard lucha unida!"
    elif estado == "escasez":
        dias = _geti("escasez_dias_restantes", 0)
        desc = f"📉 *ESCASEZ GLOBAL* — {dias} día(s) restante(s). Mercados cerrados."
    else:
        desc = "🌿 El mundo está en calma."

    texto = (
        f"🌑 *Corrupción del Vacío*\n\n"
        f"{barra} *{corr}%*\n\n"
        f"{desc}\n\n"
    )
    if corr >= 80:
        texto += "👉 Usa /umbral para ver el panel completo del Umbral del Vacío."
    else:
        texto += (
            "🏺 Puedes donar objetos a la Caldera del Ritual en la ciudad "
            "usando /umbral\\_donar para retrasar la corrupción."
        )

    await update.effective_message.reply_text(texto, parse_mode="Markdown")


def _barra_progreso(valor: int, ancho: int = 20) -> str:
    lleno  = int(valor / 100 * ancho)
    vacio  = ancho - lleno
    return "█" * lleno + "░" * vacio


async def cmd_umbral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/umbral — Panel del Umbral del Vacío."""
    user_id = update.effective_user.id
    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        await update.effective_message.reply_text("❌ Primero crea tu personaje con /start.")
        return

    corr   = get_corrupcion()
    estado = get_estado()

    if corr < 80 and estado not in ("noche_vacio", "jefe_final", "escasez", "cuenta_regresiva"):
        await update.effective_message.reply_text(
            f"🌑 *Umbral del Vacío*\n\n"
            f"Corrupción actual: {_barra_progreso(corr)} *{corr}%*\n\n"
            f"El Umbral del Vacío no está activo todavía.\n"
            f"Cuando la corrupción alcance el *80%*, este panel se abrirá "
            f"con todas las mecánicas del evento.\n\n"
            f"Puedes donar objetos en la ciudad con /umbral\\_donar.",
            parse_mode="Markdown"
        )
        return

    await _mostrar_panel_umbral(update, context, jug)


async def _mostrar_panel_umbral(update, context, jug, editar=False):
    corr    = get_corrupcion()
    estado  = get_estado()
    user_id = jug["user_id"]

    texto = f"🌌 *Panel del Umbral del Vacío*\n\n"
    texto += f"💀 Corrupción: {_barra_progreso(corr)} *{corr}%*\n"
    texto += f"📊 Estado: *{_nombre_estado(estado)}*\n\n"

    botones = []

    if estado == "cuenta_regresiva":
        inicio_str = _get("cuenta_regresiva_inicio", "")
        if inicio_str:
            inicio   = datetime.fromisoformat(inicio_str)
            restante = timedelta(hours=4) - (datetime.now() - inicio)
            secs     = max(0, int(restante.total_seconds()))
            h, rem   = divmod(secs, 3600)
            m        = rem // 60
            texto   += f"⏳ *La Noche comienza en: {h}h {m}min*\n\n"
        texto += (
            "⚠️ *Mecánica de la Noche del Vacío:*\n"
            "• Aparecerán 3 monstruos, uno por facción (en secuencia).\n"
            "• Cada jugador solo puede atacar al monstruo de *su* facción.\n"
            "• Cada guerrero puede atacar *3 veces* por monstruo.\n"
            "• Los monstruos atacan masivamente cada ronda.\n"
            "• Si los 3 caen → aparece el Jefe Final.\n"
            "• Si no se derrotan → Escasez Global de 1 día.\n\n"
            "🧪 Preparad pociones de vida antes de que empiece."
        )

    elif estado == "noche_vacio":
        faccion = _get("monstruo_actual_faccion", "")
        hp      = _geti("monstruo_actual_hp", 0)
        hp_max  = _geti("monstruo_actual_hp_max", 1)
        ronda   = _geti("monstruo_ronda_actual", 1)
        rondas  = _geti("rondas_monstruo", 3)
        der     = _geti("monstruos_derrotados", 0)
        mon_id  = _geti("monstruo_actual_id", 0)
        porcentaje = int(hp / hp_max * 100) if hp_max > 0 else 0
        texto += (
            f"🌑 *Monstruo activo: facción {faccion}*\n"
            f"❤️ {_barra_progreso(porcentaje)} {hp:,} / {hp_max:,}\n"
            f"⚔️ Ronda: *{ronda} / {rondas}*\n"
            f"💀 Monstruos derrotados: *{der} / 3*\n\n"
        )
        ataques = _ataques_usados(user_id, mon_id)
        max_at  = _geti("max_ataques_jugador", 3)
        if jug.get("faccion") == faccion:
            texto += f"Tu facción: *{faccion}* ✅\n"
            texto += f"Tus ataques restantes: *{max(0, max_at - ataques)} / {max_at}*\n"
            if ataques < max_at:
                botones.append([InlineKeyboardButton("⚔️ ¡ATACAR AL MONSTRUO!", callback_data="umbral_atacar")])
        else:
            texto += f"⚠️ Este monstruo pertenece a *{faccion}*. Tú eres de *{jug.get('faccion')}*.\n"
            texto += "Solo los jugadores de esa facción pueden atacarlo."

    elif estado == "jefe_final":
        hp      = _geti("jefe_hp", 0)
        hp_max  = _geti("jefe_hp_max", 1)
        ronda   = _geti("jefe_ronda_actual", 1)
        rondas  = _geti("rondas_jefe", 5)
        mon_id  = _geti("monstruo_actual_id", 0)
        porcentaje = int(hp / hp_max * 100) if hp_max > 0 else 0
        texto += (
            f"⚡ *JEFE FINAL: Aetheron el Devorador*\n"
            f"❤️ {_barra_progreso(porcentaje)} {hp:,} / {hp_max:,}\n"
            f"⚔️ Ronda: *{ronda} / {rondas}*\n\n"
            "¡TODOS los jugadores pueden atacar al jefe final!\n"
        )
        ataques = _ataques_usados(user_id, mon_id)
        max_at  = _geti("max_ataques_jugador", 3)
        texto += f"Tus ataques restantes: *{max(0, max_at - ataques)} / {max_at}*\n"
        if ataques < max_at:
            botones.append([InlineKeyboardButton("⚡ ¡ATACAR AL JEFE FINAL!", callback_data="umbral_atacar")])

    elif estado == "escasez":
        dias = _geti("escasez_dias_restantes", 0)
        texto += (
            f"📉 *ESCASEZ GLOBAL* — {dias} día(s) restante(s)\n\n"
            "• Los precios en las tiendas están aumentados.\n"
            "• Las subastas, mercado P2P y bolsa están cerrados.\n"
            "• La corrupción se reiniciará al terminar la escasez.\n"
        )

    if estado in ("normal", "alerta"):
        botones.append([InlineKeyboardButton("🏺 Donar a la Caldera del Ritual", callback_data="umbral_donar_menu")])
    botones.append([InlineKeyboardButton("🔄 Actualizar", callback_data="umbral_refrescar")])

    markup = InlineKeyboardMarkup(botones) if botones else None
    if editar and update.callback_query:
        try:
            await update.callback_query.edit_message_text(
                texto, parse_mode="Markdown", reply_markup=markup
            )
            return
        except Exception:
            pass
    await update.effective_message.reply_text(
        texto, parse_mode="Markdown", reply_markup=markup
    )


def _nombre_estado(estado: str) -> str:
    nombres = {
        "normal":           "🌿 Normal",
        "alerta":           "⚠️ Alerta — Corrupción alta",
        "cuenta_regresiva": "⏳ Cuenta atrás — La Noche se acerca",
        "noche_vacio":      "🌑 NOCHE DEL VACÍO",
        "jefe_final":       "⚡ JEFE FINAL",
        "escasez":          "📉 Escasez Global",
    }
    return nombres.get(estado, estado)


async def cmd_umbral_donar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/umbral_donar <cantidad_oro> — Dona oro a la Caldera del Ritual."""
    user_id = update.effective_user.id
    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        await update.effective_message.reply_text("❌ Primero crea tu personaje con /start.")
        return

    if jug.get("ubicacion", "ciudad") != "ciudad" and (jug.get("zona_actual") or "").find("Ciudadela") == -1:
        await update.effective_message.reply_text(
            "🏺 La Caldera del Ritual solo está disponible en la ciudad.\n"
            "Viaja a tu ciudad con /viajar."
        )
        return

    estado = get_estado()
    if estado in ("noche_vacio", "jefe_final", "escasez"):
        await update.effective_message.reply_text(
            "❌ La Caldera del Ritual ya no acepta donaciones en este momento.\n"
            "Espera al próximo ciclo."
        )
        return

    if not context.args:
        corr = get_corrupcion()
        saldos = db_helper.obtener_jugador(user_id) or {}
        await update.effective_message.reply_text(
            f"🏺 *Caldera del Ritual*\n\n"
            f"La Caldera acepta oro y reduce la corrupción del Vacío.\n"
            f"Cada *500 oro* reduce la corrupción en *1%*.\n\n"
            f"Corrupción actual: *{corr}%*\n"
            f"Tu oro: *{saldos.get('oro', 0):,}*\n\n"
            f"Uso: /umbral\\_donar <cantidad\\_oro>",
            parse_mode="Markdown"
        )
        return

    try:
        cantidad = int(context.args[0])
        if cantidad <= 0:
            raise ValueError
    except (ValueError, IndexError):
        await update.effective_message.reply_text("❌ Escribe una cantidad válida. Ej: /umbral_donar 500")
        return

    saldos = db_helper.obtener_jugador(user_id) or {}
    oro_actual = saldos.get("oro", 0)
    if oro_actual < cantidad:
        await update.effective_message.reply_text(f"❌ No tienes suficiente oro. Tienes {oro_actual:,}.")
        return

    import economia
    economia.modificar_saldo(user_id, "oro", -cantidad, "donacion caldera ritual umbral")
    reduccion = max(1, cantidad // 500)
    nueva = max(0, get_corrupcion() - reduccion)
    _set("corrupcion", nueva)
    _registrar_contribucion(user_id, "donacion_oro", cantidad)
    if nueva >= 80:
        _set("estado", "alerta")
    else:
        _set("estado", "normal")

    await update.effective_message.reply_text(
        f"🏺 *¡Donación realizada!*\n\n"
        f"Has donado *{cantidad:,} oro* a la Caldera del Ritual.\n"
        f"La corrupción ha bajado *{reduccion}%*.\n\n"
        f"Corrupción actual: *{nueva}%*\n\n"
        f"El Vacío retrocede... por ahora. 🌿",
        parse_mode="Markdown"
    )


async def cmd_umbral_atacar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/umbral_atacar — Ataca al monstruo o jefe activo."""
    user_id = update.effective_user.id
    jug     = db_helper.obtener_jugador(user_id)
    if not jug:
        await update.effective_message.reply_text("❌ Primero crea tu personaje con /start.")
        return

    estado = get_estado()
    if estado not in ("noche_vacio", "jefe_final"):
        await update.effective_message.reply_text(
            "⚔️ No hay ningún monstruo activo ahora mismo.\n"
            "Usa /umbral para ver el estado del evento."
        )
        return

    mon_id  = _geti("monstruo_actual_id", 0)
    max_at  = _geti("max_ataques_jugador", 3)
    usados  = _ataques_usados(user_id, mon_id)
    if usados >= max_at:
        await update.effective_message.reply_text(
            f"⚔️ Ya has usado todos tus ataques ({max_at}/{max_at}) contra este enemigo.\n"
            "Espera la próxima ronda o el siguiente monstruo."
        )
        return

    faccion_mon = _get("monstruo_actual_faccion", "")
    if estado == "noche_vacio" and jug.get("faccion") != faccion_mon:
        await update.effective_message.reply_text(
            f"❌ Este monstruo pertenece a la facción *{faccion_mon}*.\n"
            f"Solo sus jugadores pueden atacarlo.",
            parse_mode="Markdown"
        )
        return

    # Calcular daño
    atk  = jug.get("ataque", 50) or 50
    dano = random.randint(int(atk * 0.8), int(atk * 1.5))
    _registrar_ataque(user_id, mon_id)
    _registrar_contribucion(user_id, "ataque_umbral", dano)

    if estado == "noche_vacio":
        hp_actual = _geti("monstruo_actual_hp", 0)
        nuevo_hp  = max(0, hp_actual - dano)
        _set("monstruo_actual_hp", nuevo_hp)
        hp_max    = _geti("monstruo_actual_hp_max", 1)
        porcentaje = int(nuevo_hp / hp_max * 100) if hp_max > 0 else 0
        ataques_restantes = max_at - usados - 1

        respuesta = (
            f"⚔️ *¡ATACAS AL MONSTRUO DEL VACÍO!*\n\n"
            f"💥 Daño infligido: *{dano:,}*\n"
            f"❤️ Vida del monstruo: {_barra_progreso(porcentaje)} *{nuevo_hp:,}*\n"
            f"⚔️ Tus ataques restantes: *{ataques_restantes}*\n"
        )

        if nuevo_hp <= 0:
            der = _geti("monstruos_derrotados", 0) + 1
            _set("monstruos_derrotados", der)
            _bot = context.bot if hasattr(context, 'bot') else context.application.bot
            if der >= 3:
                jefe_auto = _get("jefe_auto", "1")
                if jefe_auto == "1":
                    respuesta += f"\n💀 *¡EL MONSTRUO HA CAÍDO!* ({der}/3 derrotados)\n"
                    respuesta += "\n⚡ ¡Los tres monstruos han sido vencidos! El Jefe Final aparece..."
                    await update.effective_message.reply_text(respuesta, parse_mode="Markdown")
                    await _iniciar_jefe_final(_bot)
                else:
                    # Admin decidió que si matan los 3 monstruos, hay victoria directa sin jefe
                    respuesta += f"\n💀 *¡EL MONSTRUO HA CAÍDO!* ({der}/3 derrotados)\n"
                    respuesta += "\n🌟 *¡Victoria! Los 3 monstruos han sido derrotados.*\n"
                    respuesta += "El Jefe Final no hará su aparición esta vez..."
                    await update.effective_message.reply_text(respuesta, parse_mode="Markdown")
                    await _resolver_escasez(_bot, victoria=True)
            else:
                siguiente = FACCIONES[der] if der < len(FACCIONES) else None
                respuesta += f"\n💀 *¡EL MONSTRUO HA CAÍDO!* ({der}/3 derrotados)\n"
                respuesta += f"\n🌑 El siguiente monstruo ({siguiente}) aparecerá en breve..."
                await update.effective_message.reply_text(respuesta, parse_mode="Markdown")
                siguiente_faccion = FACCIONES[der]
                await _iniciar_monstruo(_bot, siguiente_faccion)
            return

    elif estado == "jefe_final":
        hp_actual = _geti("jefe_hp", 0)
        nuevo_hp  = max(0, hp_actual - dano)
        _set("jefe_hp", nuevo_hp)
        hp_max    = _geti("jefe_hp_max", 1)
        porcentaje = int(nuevo_hp / hp_max * 100) if hp_max > 0 else 0
        ataques_restantes = max_at - usados - 1

        respuesta = (
            f"⚡ *¡ATACAS AL JEFE FINAL!*\n\n"
            f"💥 Daño infligido: *{dano:,}*\n"
            f"❤️ Vida del jefe: {_barra_progreso(porcentaje)} *{nuevo_hp:,}*\n"
            f"⚔️ Tus ataques restantes: *{ataques_restantes}*\n"
        )

        if nuevo_hp <= 0:
            respuesta += "\n🌟 *¡¡EL JEFE FINAL HA SIDO REPELIDO!! ¡VICTORIA!*"
            await update.effective_message.reply_text(respuesta, parse_mode="Markdown")
            await _resolver_escasez(
                context.bot if hasattr(context, 'bot') else context.application.bot,
                victoria=True
            )
            return

    await update.effective_message.reply_text(respuesta, parse_mode="Markdown")


# ── Callbacks inline ──────────────────────────────────────────────────────────

async def cb_umbral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    data    = query.data
    user_id = update.effective_user.id
    jug     = db_helper.obtener_jugador(user_id)
    if not jug:
        await query.answer("❌ Primero crea tu personaje con /start.", show_alert=True)
        return

    if data == "umbral_refrescar":
        await query.answer("🔄 Panel actualizado.")
        await _mostrar_panel_umbral(update, context, jug, editar=True)

    elif data == "umbral_atacar":
        await query.answer()
        await cmd_umbral_atacar(update, context)

    elif data == "umbral_donar_menu":
        corr   = get_corrupcion()
        saldos = db_helper.obtener_jugador(user_id) or {}
        oro    = saldos.get("oro", 0)
        teclado = [
            [InlineKeyboardButton("🏺 100 oro (−0%)",   callback_data="umbral_donar_100"),
             InlineKeyboardButton("🏺 500 oro (−1%)",   callback_data="umbral_donar_500")],
            [InlineKeyboardButton("🏺 1.000 oro (−2%)", callback_data="umbral_donar_1000"),
             InlineKeyboardButton("🏺 5.000 oro (−10%)", callback_data="umbral_donar_5000")],
            [InlineKeyboardButton("🏺 10.000 oro (−20%)", callback_data="umbral_donar_10000")],
            [InlineKeyboardButton("🔙 Volver",            callback_data="umbral_refrescar")],
        ]
        await query.answer()
        await query.edit_message_text(
            f"🏺 *Caldera del Ritual*\n\n"
            f"Corrupción actual: *{corr}%*\n"
            f"Tu oro: *{oro:,}*\n\n"
            f"Cada *500 oro* reduce la corrupción en *1%*.\n"
            f"Selecciona cuánto quieres donar:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(teclado)
        )

    elif data.startswith("umbral_donar_"):
        try:
            cantidad = int(data.split("_")[2])
        except (ValueError, IndexError):
            await query.answer("❌ Cantidad inválida.", show_alert=True)
            return
        estado = get_estado()
        if estado in ("noche_vacio", "jefe_final", "escasez"):
            await query.answer("❌ La Caldera no acepta donaciones en este momento.", show_alert=True)
            return
        saldos  = db_helper.obtener_jugador(user_id) or {}
        oro_act = saldos.get("oro", 0)
        if oro_act < cantidad:
            await query.answer(f"❌ No tienes suficiente oro ({oro_act:,}).", show_alert=True)
            return
        import economia
        economia.modificar_saldo(user_id, "oro", -cantidad, "donacion caldera ritual umbral")
        reduccion = max(1, cantidad // 500)
        nueva = max(0, get_corrupcion() - reduccion)
        _set("corrupcion", nueva)
        _registrar_contribucion(user_id, "donacion_oro", cantidad)
        _set("estado", "alerta" if nueva >= 80 else "normal")
        await query.answer(
            f"🏺 ¡Donados {cantidad:,} oro! Corrupción −{reduccion}% → {nueva}%",
            show_alert=True
        )
        await _mostrar_panel_umbral(update, context, jug, editar=True)

    else:
        await query.answer()


# ── COMANDOS DE ADMIN ─────────────────────────────────────────────────────────

def _es_admin(user_id: int) -> bool:
    try:
        import superadmin as _sa
        return _sa._es_admin(user_id)
    except Exception:
        return False

def _es_superadmin(user_id: int) -> bool:
    try:
        import superadmin as _sa
        return _sa.verificar_superadmin(user_id)
    except Exception:
        return False


async def cmd_umbral_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/umbral_admin — Panel de administración del Umbral del Vacío."""
    user_id = update.effective_user.id
    if not _es_admin(user_id):
        await update.effective_message.reply_text("⛔ Solo los administradores pueden usar /umbral_admin.")
        return
    await _mostrar_panel_admin(update, context)


async def _mostrar_panel_admin(update, context, pagina: int = 1):
    """Panel admin paginado. pagina=1 → Control evento | pagina=2 → Monstruos/tiempos."""
    corr   = get_corrupcion()
    estado = get_estado()

    if pagina == 2:
        # ── Página 2: configuración de monstruos, escasez y tiempos ─────────
        dias_mon   = _geti("dias_escasez_por_monstruo", 1)
        dias_jefe  = _geti("dias_escasez_jefe", 2)
        acum       = _geti("escasez_acumulada", 0)
        mult_mon   = _getf("mult_escalado_mon", 30.0)
        mult_jefe  = _getf("mult_escalado_jefe", 50.0)
        ov_mon     = _geti("hp_monstruo_override", 0)
        ov_jefe    = _geti("hp_jefe_override", 0)
        dur_ronda  = _geti("duracion_ronda_minutos", 30)
        entre_ron  = _geti("entre_rondas_minutos", 5)
        rondas_mon = _geti("rondas_monstruo", 3)
        rondas_jefe= _geti("rondas_jefe", 5)
        max_at     = _geti("max_ataques_jugador", 3)

        atk_mon  = _geti("atk_monstruo_override", 0)
        atk_jefe = _geti("atk_jefe_override", 0)

        texto = (
            f"🌑 *Panel Admin — Monstruos & Tiempos* _(p.2)_\n\n"
            f"📊 Estado: *{_nombre_estado(estado)}* | Escasez acumulada: *{acum} día(s)*\n\n"
            f"📉 *Escasez por monstruo escapado:* *{dias_mon} día(s)*\n"
            f"💀 *Escasez por jefe no derrotado:* *{dias_jefe} día(s)*\n\n"
            f"🔢 *HP monstruo*: {'🔒 Override: ' + str(ov_mon) if ov_mon > 0 else '📐 Escalado (ATK × jugadores)'}\n"
            f"   Multiplicador: *×{mult_mon:.0f}*\n"
            f"   Previews:\n" +
            "\n".join(f"   {_preview_stats_mon(f)}" for f in FACCIONES) +
            f"\n\n🔢 *HP jefe final*: {'🔒 Override: ' + str(ov_jefe) if ov_jefe > 0 else '📐 Escalado (ATK × jugadores)'}\n"
            f"   Multiplicador: *×{mult_jefe:.0f}*\n"
            f"   {_preview_stats_jefe()}\n\n"
            f"⚔️ *ATK monstruo* (daño/ronda): {'🔒 Override: ' + str(atk_mon) if atk_mon > 0 else '📐 Auto (nivel jugadores)'}\n"
            f"⚔️ *ATK jefe final* (daño/ronda): {'🔒 Override: ' + str(atk_jefe) if atk_jefe > 0 else '📐 Auto (nivel jugadores)'}\n\n"
            f"⏱️ *Duración de ronda:* *{dur_ronda} min* | *Entre rondas:* *{entre_ron} min*\n"
            f"🔄 Rondas monstruo: *{rondas_mon}* | Rondas jefe: *{rondas_jefe}*\n"
            f"⚔️ Ataques/jugador: *{max_at}*\n\n"
            "_Usa_ `/umbral_set hp_monstruo_override 5000` _para fijar HP._\n"
            "_Usa_ `/umbral_set hp_monstruo_override 0` _para volver al escalado._"
        )

        teclado = [
            [InlineKeyboardButton(f"📉 Días/mon -{dias_mon-1 if dias_mon>1 else dias_mon}",
                                  callback_data="uadm_dias_mon_menos"),
             InlineKeyboardButton(f"Días/mon: {dias_mon}d", callback_data="uadm_noop"),
             InlineKeyboardButton(f"📈 +días/mon", callback_data="uadm_dias_mon_mas")],
            [InlineKeyboardButton(f"📉 Días/jefe -{dias_jefe-1 if dias_jefe>1 else dias_jefe}",
                                  callback_data="uadm_dias_jefe_menos"),
             InlineKeyboardButton(f"Días/jefe: {dias_jefe}d", callback_data="uadm_noop"),
             InlineKeyboardButton(f"📈 +días/jefe", callback_data="uadm_dias_jefe_mas")],
            [InlineKeyboardButton(f"👹 Mult.mon -{mult_mon:.0f}", callback_data="uadm_mult_mon_menos"),
             InlineKeyboardButton(f"×{mult_mon:.0f}", callback_data="uadm_noop"),
             InlineKeyboardButton(f"Mult.mon +", callback_data="uadm_mult_mon_mas")],
            [InlineKeyboardButton(f"⚡ Mult.jefe -{mult_jefe:.0f}", callback_data="uadm_mult_jefe_menos"),
             InlineKeyboardButton(f"×{mult_jefe:.0f}", callback_data="uadm_noop"),
             InlineKeyboardButton(f"Mult.jefe +", callback_data="uadm_mult_jefe_mas")],
            [InlineKeyboardButton(f"⏱️ Ronda -{dur_ronda}min", callback_data="uadm_dur_menos"),
             InlineKeyboardButton(f"{dur_ronda}min", callback_data="uadm_noop"),
             InlineKeyboardButton(f"Ronda +5min", callback_data="uadm_dur_mas")],
            [InlineKeyboardButton(f"⏳ Pausa -{entre_ron}min", callback_data="uadm_entre_menos"),
             InlineKeyboardButton(f"{entre_ron}min", callback_data="uadm_noop"),
             InlineKeyboardButton(f"Pausa +5min", callback_data="uadm_entre_mas")],
            [InlineKeyboardButton("🔒 Reset override monstruo", callback_data="uadm_ov_mon_reset"),
             InlineKeyboardButton("🔒 Reset override jefe",     callback_data="uadm_ov_jefe_reset")],
            [InlineKeyboardButton(f"⚔️ ATK mon −50",  callback_data="uadm_atk_mon_menos"),
             InlineKeyboardButton(f"ATK mon: {atk_mon if atk_mon>0 else 'Auto'}", callback_data="uadm_noop"),
             InlineKeyboardButton(f"ATK mon +50",  callback_data="uadm_atk_mon_mas")],
            [InlineKeyboardButton(f"⚔️ ATK jefe −50", callback_data="uadm_atk_jefe_menos"),
             InlineKeyboardButton(f"ATK jefe: {atk_jefe if atk_jefe>0 else 'Auto'}", callback_data="uadm_noop"),
             InlineKeyboardButton(f"ATK jefe +50", callback_data="uadm_atk_jefe_mas")],
            [InlineKeyboardButton("🔓 Reset ATK mon",  callback_data="uadm_atk_mon_reset"),
             InlineKeyboardButton("🔓 Reset ATK jefe", callback_data="uadm_atk_jefe_reset")],
            [InlineKeyboardButton("🗑️ Limpiar escasez acumulada", callback_data="uadm_reset_escasez_acum")],
            [InlineKeyboardButton("◀️ Volver al panel principal", callback_data="uadm_pag1")],
        ]

    else:
        # ── Página 1: control de evento ──────────────────────────────────────
        tasa    = _geti("tasa_diaria", 3)
        modo    = "🤖 Automático" if _get("modo_auto", "1") == "1" else "✋ Manual"
        mult    = _getf("multiplicador_precios", 2.0)
        acum    = _geti("escasez_acumulada", 0)
        dias_r  = _geti("escasez_dias_restantes", 0)
        ronda_fin_str = _get("ronda_fin_en", "")
        ronda_fin_txt = ""
        if ronda_fin_str:
            try:
                ronda_fin = datetime.fromisoformat(ronda_fin_str)
                mins_rest = max(0, int((ronda_fin - datetime.now()).total_seconds() / 60))
                ronda_fin_txt = f"\n⏱️ Fin de ronda en: *{mins_rest} min*"
            except Exception:
                pass

        texto = (
            f"🌑 *Panel Admin — Umbral del Vacío* _(p.1)_\n\n"
            f"📊 Corrupción: *{corr}%* | Estado: *{_nombre_estado(estado)}*\n"
            f"📈 Tasa diaria: *+{tasa}%/día*\n"
            f"⚙️ Modo: *{modo}*\n"
            f"💰 Mult. precios escasez: *x{mult}*\n"
            f"📉 Escasez acumulada esta noche: *{acum} día(s)*\n"
            f"☀️ Escasez activa restante: *{dias_r} día(s)*"
            f"{ronda_fin_txt}"
        )

        jefe_auto   = _get("jefe_auto", "1")
        ja_label    = "👹 Jefe si todos caen: ✅ ON" if jefe_auto == "1" else "👹 Jefe si todos caen: ❌ OFF"
        teclado = [
            [InlineKeyboardButton("🤖 Auto ON/OFF",     callback_data="uadm_toggle_auto"),
             InlineKeyboardButton("📉 -10% corrupción", callback_data="uadm_corr_menos")],
            [InlineKeyboardButton("📈 +10% corrupción", callback_data="uadm_corr_mas"),
             InlineKeyboardButton("💯 Corrupción = 100%", callback_data="uadm_corr_max")],
            [InlineKeyboardButton("🌑 Invocar Noche ahora", callback_data="uadm_invocar")],
            [InlineKeyboardButton(ja_label,               callback_data="uadm_toggle_jefe_auto")],
            [InlineKeyboardButton("✅ Resolver Victoria",   callback_data="uadm_victoria"),
             InlineKeyboardButton("📉 Resolver Escasez",    callback_data="uadm_escasez")],
            [InlineKeyboardButton("🔄 Reiniciar ciclo",     callback_data="uadm_reset"),
             InlineKeyboardButton("❌ Cancelar evento",     callback_data="uadm_cancelar")],
            [InlineKeyboardButton("👹 Monstruos & Tiempos ▶️", callback_data="uadm_pag2"),
             InlineKeyboardButton("🔄 Actualizar",           callback_data="uadm_refrescar")],
        ]

    msg = getattr(update, 'effective_message', None)
    if not msg and hasattr(update, 'callback_query'):
        msg = update.callback_query.message
    try:
        await update.callback_query.edit_message_text(
            texto, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(teclado)
        )
    except Exception:
        await msg.reply_text(
            texto, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(teclado)
        )


async def cb_umbral_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    user_id = update.effective_user.id
    if not _es_admin(user_id):
        await query.answer("⛔ Sin permiso.", show_alert=True)
        return
    data = query.data

    if data == "uadm_refrescar":
        await query.answer("🔄 Panel actualizado.")
        await _mostrar_panel_admin(update, context)
    elif data == "uadm_toggle_auto":
        nuevo = "0" if _get("modo_auto", "1") == "1" else "1"
        _set("modo_auto", nuevo)
        label = "ON 🟢" if nuevo == "1" else "OFF 🔴"
        await query.answer(f"🤖 Modo automático: {label}", show_alert=True)
        await _mostrar_panel_admin(update, context)
    elif data == "uadm_corr_menos":
        nuevo_corr = max(0, get_corrupcion() - 10)
        _set("corrupcion", nuevo_corr)
        await query.answer(f"📉 Corrupción → {nuevo_corr}%", show_alert=True)
        await _mostrar_panel_admin(update, context)
    elif data == "uadm_corr_mas":
        nuevo_corr = min(100, get_corrupcion() + 10)
        _set("corrupcion", nuevo_corr)
        await query.answer(f"📈 Corrupción → {nuevo_corr}%", show_alert=True)
        await _mostrar_panel_admin(update, context)
    elif data == "uadm_corr_max":
        _set("corrupcion", 100)
        _set("estado", "alerta")
        await query.answer("💯 Corrupción al 100%. Estado → Alerta.", show_alert=True)
        await _mostrar_panel_admin(update, context)
    elif data == "uadm_invocar":
        _set("corrupcion", 100)
        await _disparar_cuenta_regresiva(context.bot)
        await query.answer("🌑 ¡Cuenta regresiva iniciada! La Noche se acerca.", show_alert=True)
        await _mostrar_panel_admin(update, context)
    elif data == "uadm_victoria":
        await _resolver_escasez(context.bot, victoria=True)
        await query.answer("✅ Victoria resuelta. Recompensas distribuidas.", show_alert=True)
        await _mostrar_panel_admin(update, context)
    elif data == "uadm_escasez":
        await _resolver_escasez(context.bot, victoria=False)
        await query.answer("📉 Escasez Global activada.", show_alert=True)
        await _mostrar_panel_admin(update, context)
    elif data == "uadm_cancelar":
        _set("estado", "normal")
        _set("monstruos_derrotados", "0")
        _set("ronda_fin_en", "")
        await query.answer("✅ Evento cancelado. Estado → Normal.", show_alert=True)
        await _mostrar_panel_admin(update, context)
    elif data == "uadm_reset":
        _set("estado", "normal")
        _set("corrupcion", "0")
        _set("monstruos_derrotados", "0")
        _set("escasez_dias_restantes", "0")
        _set("escasez_acumulada", "0")
        _set("ronda_fin_en", "")
        conn = sqlite3.connect(DB_PATH)
        conn.execute("DELETE FROM umbral_ataques")
        conn.execute("DELETE FROM umbral_contribuciones")
        conn.commit()
        conn.close()
        await query.answer("🔄 Ciclo reiniciado. Corrupción a 0%.", show_alert=True)
        await _mostrar_panel_admin(update, context)
    # ── Navegación de páginas ─────────────────────────────────────────────────
    elif data == "uadm_pag1":
        await query.answer()
        await _mostrar_panel_admin(update, context, pagina=1)
    elif data == "uadm_pag2":
        await query.answer()
        await _mostrar_panel_admin(update, context, pagina=2)
    elif data == "uadm_noop":
        await query.answer()
    # ── Días de escasez por monstruo ─────────────────────────────────────────
    elif data == "uadm_dias_mon_mas":
        v = _geti("dias_escasez_por_monstruo", 1) + 1
        _set("dias_escasez_por_monstruo", v)
        await query.answer(f"📈 Días/monstruo → {v}", show_alert=True)
        await _mostrar_panel_admin(update, context, pagina=2)
    elif data == "uadm_dias_mon_menos":
        v = max(0, _geti("dias_escasez_por_monstruo", 1) - 1)
        _set("dias_escasez_por_monstruo", v)
        await query.answer(f"📉 Días/monstruo → {v}", show_alert=True)
        await _mostrar_panel_admin(update, context, pagina=2)
    # ── Días de escasez por jefe ──────────────────────────────────────────────
    elif data == "uadm_dias_jefe_mas":
        v = _geti("dias_escasez_jefe", 2) + 1
        _set("dias_escasez_jefe", v)
        await query.answer(f"📈 Días/jefe → {v}", show_alert=True)
        await _mostrar_panel_admin(update, context, pagina=2)
    elif data == "uadm_dias_jefe_menos":
        v = max(0, _geti("dias_escasez_jefe", 2) - 1)
        _set("dias_escasez_jefe", v)
        await query.answer(f"📉 Días/jefe → {v}", show_alert=True)
        await _mostrar_panel_admin(update, context, pagina=2)
    # ── Multiplicadores de escalado ───────────────────────────────────────────
    elif data == "uadm_mult_mon_mas":
        v = _getf("mult_escalado_mon", 30.0) + 5
        _set("mult_escalado_mon", f"{v:.0f}")
        await query.answer(f"👹 Mult. monstruo → ×{v:.0f}", show_alert=True)
        await _mostrar_panel_admin(update, context, pagina=2)
    elif data == "uadm_mult_mon_menos":
        v = max(1, _getf("mult_escalado_mon", 30.0) - 5)
        _set("mult_escalado_mon", f"{v:.0f}")
        await query.answer(f"👹 Mult. monstruo → ×{v:.0f}", show_alert=True)
        await _mostrar_panel_admin(update, context, pagina=2)
    elif data == "uadm_mult_jefe_mas":
        v = _getf("mult_escalado_jefe", 50.0) + 5
        _set("mult_escalado_jefe", f"{v:.0f}")
        await query.answer(f"⚡ Mult. jefe → ×{v:.0f}", show_alert=True)
        await _mostrar_panel_admin(update, context, pagina=2)
    elif data == "uadm_mult_jefe_menos":
        v = max(1, _getf("mult_escalado_jefe", 50.0) - 5)
        _set("mult_escalado_jefe", f"{v:.0f}")
        await query.answer(f"⚡ Mult. jefe → ×{v:.0f}", show_alert=True)
        await _mostrar_panel_admin(update, context, pagina=2)
    # ── Tiempo de ronda ───────────────────────────────────────────────────────
    elif data == "uadm_dur_mas":
        v = _geti("duracion_ronda_minutos", 30) + 5
        _set("duracion_ronda_minutos", v)
        await query.answer(f"⏱️ Duración ronda → {v} min", show_alert=True)
        await _mostrar_panel_admin(update, context, pagina=2)
    elif data == "uadm_dur_menos":
        v = max(5, _geti("duracion_ronda_minutos", 30) - 5)
        _set("duracion_ronda_minutos", v)
        await query.answer(f"⏱️ Duración ronda → {v} min", show_alert=True)
        await _mostrar_panel_admin(update, context, pagina=2)
    elif data == "uadm_entre_mas":
        v = _geti("entre_rondas_minutos", 5) + 5
        _set("entre_rondas_minutos", v)
        await query.answer(f"⏳ Pausa entre rondas → {v} min", show_alert=True)
        await _mostrar_panel_admin(update, context, pagina=2)
    elif data == "uadm_entre_menos":
        v = max(0, _geti("entre_rondas_minutos", 5) - 5)
        _set("entre_rondas_minutos", v)
        await query.answer(f"⏳ Pausa entre rondas → {v} min", show_alert=True)
        await _mostrar_panel_admin(update, context, pagina=2)
    # ── Overrides de HP ───────────────────────────────────────────────────────
    elif data == "uadm_ov_mon_reset":
        _set("hp_monstruo_override", 0)
        await query.answer("🔓 Override monstruo eliminado → HP escalado.", show_alert=True)
        await _mostrar_panel_admin(update, context, pagina=2)
    elif data == "uadm_ov_jefe_reset":
        _set("hp_jefe_override", 0)
        await query.answer("🔓 Override jefe eliminado → HP escalado.", show_alert=True)
        await _mostrar_panel_admin(update, context, pagina=2)
    # ── Toggle jefe_auto ──────────────────────────────────────────────────────
    elif data == "uadm_toggle_jefe_auto":
        nuevo = "0" if _get("jefe_auto", "1") == "1" else "1"
        _set("jefe_auto", nuevo)
        label = "✅ ON — Jefe aparece si los 3 monstruos mueren" if nuevo == "1" else "❌ OFF — Victoria directa si los 3 monstruos mueren"
        await query.answer(f"👹 Jefe Final: {label}", show_alert=True)
        await _mostrar_panel_admin(update, context, pagina=1)
    # ── ATK override monstruo ─────────────────────────────────────────────────
    elif data == "uadm_atk_mon_mas":
        v = _geti("atk_monstruo_override", 0) + 50
        _set("atk_monstruo_override", v)
        await query.answer(f"⚔️ ATK monstruo → {v}", show_alert=True)
        await _mostrar_panel_admin(update, context, pagina=2)
    elif data == "uadm_atk_mon_menos":
        v = max(0, _geti("atk_monstruo_override", 0) - 50)
        _set("atk_monstruo_override", v)
        lbl = str(v) if v > 0 else "Auto"
        await query.answer(f"⚔️ ATK monstruo → {lbl}", show_alert=True)
        await _mostrar_panel_admin(update, context, pagina=2)
    elif data == "uadm_atk_mon_reset":
        _set("atk_monstruo_override", 0)
        await query.answer("🔓 ATK monstruo → Auto (escalado).", show_alert=True)
        await _mostrar_panel_admin(update, context, pagina=2)
    # ── ATK override jefe ─────────────────────────────────────────────────────
    elif data == "uadm_atk_jefe_mas":
        v = _geti("atk_jefe_override", 0) + 50
        _set("atk_jefe_override", v)
        await query.answer(f"⚔️ ATK jefe → {v}", show_alert=True)
        await _mostrar_panel_admin(update, context, pagina=2)
    elif data == "uadm_atk_jefe_menos":
        v = max(0, _geti("atk_jefe_override", 0) - 50)
        _set("atk_jefe_override", v)
        lbl = str(v) if v > 0 else "Auto"
        await query.answer(f"⚔️ ATK jefe → {lbl}", show_alert=True)
        await _mostrar_panel_admin(update, context, pagina=2)
    elif data == "uadm_atk_jefe_reset":
        _set("atk_jefe_override", 0)
        await query.answer("🔓 ATK jefe → Auto (escalado).", show_alert=True)
        await _mostrar_panel_admin(update, context, pagina=2)
    # ── Limpiar escasez acumulada ─────────────────────────────────────────────
    elif data == "uadm_reset_escasez_acum":
        _set("escasez_acumulada", 0)
        await query.answer("🗑️ Escasez acumulada reiniciada a 0.", show_alert=True)
        await _mostrar_panel_admin(update, context, pagina=2)
    else:
        await query.answer()


async def cmd_umbral_set(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/umbral_set <clave> <valor> — Edita una config del Umbral.
    Sin argumentos abre el panel interactivo con botones."""
    user_id = update.effective_user.id
    if not _es_admin(user_id):
        await update.effective_message.reply_text("⛔ Solo los administradores pueden usar /umbral_set.")
        return
    # Sin argumentos → abrir panel interactivo (igual que /umbral_admin)
    if not context.args or len(context.args) < 2:
        await _mostrar_panel_admin(update, context, pagina=1)
        return
    clave, valor = context.args[0], context.args[1]
    _set(clave, valor)
    await update.effective_message.reply_text(f"✅ `{clave}` = `{valor}`", parse_mode="Markdown")


async def cmd_umbral_avanzar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/umbral_avanzar — Avanza manualmente a la siguiente ronda del combate."""
    user_id = update.effective_user.id
    if not _es_admin(user_id):
        await update.effective_message.reply_text("⛔ Solo los administradores pueden usar /umbral_avanzar.")
        return
    estado = get_estado()
    if estado == "noche_vacio":
        ronda     = _geti("monstruo_ronda_actual", 1)
        max_ronda = _geti("rondas_monstruo", 3)
        if ronda >= max_ronda:
            await update.effective_message.reply_text(
                "⚠️ Última ronda. Usa /umbral_admin → Resolver para terminar el combate."
            )
            return
        nueva = ronda + 1
        _set("monstruo_ronda_actual", nueva)
        faccion = _get("monstruo_actual_faccion", "")
        await _broadcast(
            context.bot,
            f"⚔️ *Ronda {nueva} del combate contra el monstruo de {faccion}*\n\n"
            f"¡La bestia ataca de nuevo! Usa /umbral\\_atacar ahora.\n"
            f"🧪 Tomad pociones si las necesitáis.",
            faccion=faccion
        )
        await update.effective_message.reply_text(f"✅ Ronda {nueva} iniciada para {faccion}.")
    elif estado == "jefe_final":
        ronda     = _geti("jefe_ronda_actual", 1)
        max_ronda = _geti("rondas_jefe", 5)
        if ronda >= max_ronda:
            await update.effective_message.reply_text(
                "⚠️ Última ronda del jefe. Usa /umbral_admin → Resolver."
            )
            return
        nueva = ronda + 1
        _set("jefe_ronda_actual", nueva)
        await _broadcast(
            context.bot,
            f"⚡ *¡Ronda {nueva}! El Jefe Final ataca a Aethelgard!*\n\n"
            "¡Seguid atacando! Usa /umbral\\_atacar\n"
            "🧪 Tomad pociones entre rondas."
        )
        await update.effective_message.reply_text(f"✅ Ronda {nueva} del jefe final iniciada.")
    else:
        await update.effective_message.reply_text("❌ No hay combate activo ahora mismo.")


# ── Registro ──────────────────────────────────────────────────────────────────

def registrar_handlers(app):
    app.add_handler(CommandHandler("corrupcion",       cmd_corrupcion))
    app.add_handler(CommandHandler("umbral",           cmd_umbral))
    app.add_handler(CommandHandler("umbral_donar",     cmd_umbral_donar))
    app.add_handler(CommandHandler("umbral_atacar",    cmd_umbral_atacar))
    app.add_handler(CommandHandler("umbral_admin",     cmd_umbral_admin))
    app.add_handler(CommandHandler("umbral_set",       cmd_umbral_set))
    app.add_handler(CommandHandler("umbral_avanzar",   cmd_umbral_avanzar))
    app.add_handler(CallbackQueryHandler(cb_umbral,       pattern="^umbral_"))
    app.add_handler(CallbackQueryHandler(cb_umbral_admin, pattern="^uadm_"))

    # Job diario de corrupción (a las 12:00 UTC)
    import datetime as _dt
    app.job_queue.run_daily(
        job_corrupcion_diaria,
        time=_dt.time(12, 0, 0, tzinfo=_dt.timezone.utc),
        name="job_corrupcion_umbral"
    )
    # Monitor cada 5 minutos (cuenta regresiva, lore, transiciones de noche)
    app.job_queue.run_repeating(
        job_monitor_umbral,
        interval=300,
        first=60,
        name="job_monitor_umbral"
    )

#!/usr/bin/env python3
# recoleccion_auto.py
# Membresía: Recolección Automática
# El bot recolecta automáticamente en las zonas configuradas, sin monstruos,
# respetando el cooldown normal de 90 segundos por colecta.
# La stamina del jugador se gasta igual que en la recolección manual.

import sqlite3
import json
import importlib
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler

import db_helper
import economia

DB_PATH = "aethelgard.db"

COLORES         = ["azul", "amarilla", "roja", "negra"]
EMOJI_COLOR     = {"azul": "🔵", "amarilla": "🟡", "roja": "🔴", "negra": "⚫"}
NOMBRE_COLOR    = {"azul": "Zona Azul", "amarilla": "Zona Amarilla", "roja": "Zona Roja", "negra": "Zona Negra"}
MOD_POR_COLOR   = {
    "azul":     "recoleccion_azul",
    "amarilla": "recoleccion_amarilla",
    "roja":     "recoleccion_roja",
    "negra":    "recoleccion_negra",
}
COOLDOWN_SEG  = 90   # igual que la recolección manual
MAX_COLECTAS  = 50   # límite de colectas por zona por sesión


# ==================== INIT DB ====================

def _init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS auto_recoleccion (
        user_id    INTEGER PRIMARY KEY,
        activo     INTEGER DEFAULT 0,
        ultimo_ts  TEXT    DEFAULT NULL,
        zonas_json TEXT    DEFAULT '[]'
    )''')
    # zonas_json = [{"color": "azul", "total": 5, "hecho": 0}, ...]
    conn.commit()
    conn.close()

_init_db()


# ==================== DB HELPERS ====================

def _get_row(user_id: int) -> dict:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT activo, ultimo_ts, zonas_json FROM auto_recoleccion WHERE user_id = ?', (user_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        return {"activo": 0, "ultimo_ts": None, "zonas": []}
    try:
        zonas = json.loads(row[2] or "[]")
    except Exception:
        zonas = []
    return {"activo": row[0], "ultimo_ts": row[1], "zonas": zonas}


def _save_row(user_id: int, activo: int, ultimo_ts: Optional[str], zonas: list):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT OR REPLACE INTO auto_recoleccion (user_id, activo, ultimo_ts, zonas_json)
                 VALUES (?, ?, ?, ?)''',
              (user_id, activo, ultimo_ts, json.dumps(zonas, ensure_ascii=False)))
    conn.commit()
    conn.close()


def _get_zona(zonas: list, color: str) -> Optional[dict]:
    return next((z for z in zonas if z["color"] == color), None)


def _remove_zona(zonas: list, color: str) -> list:
    return [z for z in zonas if z["color"] != color]


# ==================== LÓGICA DE RECOLECCIÓN ====================

def _obtener_zona_config_color(color: str) -> Optional[dict]:
    """Devuelve la primera configuración de zona disponible para ese color."""
    try:
        mod = importlib.import_module(MOD_POR_COLOR[color])
        cfgs = getattr(mod, "CONFIG_RECOLECCION", {})
        if cfgs:
            return next(iter(cfgs.values()))
    except Exception:
        pass
    return None


async def _ejecutar_una_recoleccion(user_id: int, color: str, bot) -> Optional[str]:
    """
    Ejecuta una recolección automática (sin monstruos) en la zona del color dado.
    Gasta la stamina normal del jugador. Devuelve texto del resultado o None si
    no hay stamina suficiente.
    """
    costo = int(db_helper.obtener_config("stamina_recolectar", "5"))
    stamina_antes, stamina_max, _ = db_helper.obtener_stamina(user_id)

    if not db_helper.gastar_stamina(user_id, costo):
        return None  # sin stamina — señal para pausar

    zona_config = _obtener_zona_config_color(color)
    if not zona_config:
        return None

    stamina_nueva = stamina_antes - costo

    # Probabilidad de fallo (igual que manual, sin monstruos)
    if random.random() < zona_config.get("prob_fallo", 0):
        frases = zona_config.get("frases_fallo", ["La recolección no dio frutos esta vez."])
        frase  = random.choice(frases)
        return f"❌ *{NOMBRE_COLOR[color]}* — {frase}\n⚡ Stamina: {stamina_nueva}/{stamina_max}"

    # Otorgar recompensa usando la función del módulo
    try:
        mod = importlib.import_module(MOD_POR_COLOR[color])
        oro, materiales = mod._otorgar_recompensa(user_id, zona_config)
    except Exception:
        return None

    lineas  = [f"• {nom}: x{cant}" for nom, cant in materiales] if materiales else ["_(nada esta vez)_"]
    mat_txt = "\n".join(lineas)
    return (
        f"✅ *{NOMBRE_COLOR[color]}*\n"
        f"📦 {mat_txt}\n"
        f"🪙 +{oro} oro  ⚡ {stamina_nueva}/{stamina_max}"
    )


# ==================== JOB PERIÓDICO ====================

async def job_auto_recoleccion(context: ContextTypes.DEFAULT_TYPE):
    """Corre cada 30 s. Procesa una colecta por usuario activo (respetando cooldown de 90 s)."""
    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()
    c.execute('SELECT user_id, ultimo_ts, zonas_json FROM auto_recoleccion WHERE activo = 1')
    rows = c.fetchall()
    conn.close()

    ahora = datetime.now()

    for user_id, ultimo_ts, zonas_json in rows:
        # Comprobar cooldown
        if ultimo_ts:
            try:
                if (ahora - datetime.fromisoformat(ultimo_ts)).total_seconds() < COOLDOWN_SEG:
                    continue
            except Exception:
                pass

        try:
            zonas = json.loads(zonas_json or "[]")
        except Exception:
            continue

        # Buscar la primera zona con trabajo pendiente
        zona_pendiente = next(
            (z for z in zonas if z.get("hecho", 0) < z.get("total", 0)),
            None
        )

        if not zona_pendiente:
            # Sesión terminada: desactivar
            _save_row(user_id, 0, ultimo_ts, zonas)
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=(
                        "⛏️ *Recolección Automática completada.*\n"
                        "Todas las colectas de tu sesión han terminado.\n"
                        "_Configura una nueva sesión con /auto\\_recoleccion._"
                    ),
                    parse_mode="Markdown"
                )
            except Exception:
                pass
            continue

        color     = zona_pendiente["color"]
        resultado = await _ejecutar_una_recoleccion(user_id, color, context.bot)

        if resultado is None:
            # Sin stamina: pausar
            _save_row(user_id, 0, ahora.isoformat(), zonas)
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=(
                        "⛏️ *Recolección Automática pausada* — sin stamina.\n"
                        "Cuando recuperes stamina, vuelve a iniciar con /auto\\_recoleccion."
                    ),
                    parse_mode="Markdown"
                )
            except Exception:
                pass
            continue

        zona_pendiente["hecho"] = zona_pendiente.get("hecho", 0) + 1
        _save_row(user_id, 1, ahora.isoformat(), zonas)

        # Calcular cuántas colectas quedan en total
        pendientes = sum(
            max(0, z.get("total", 0) - z.get("hecho", 0)) for z in zonas
        )
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=(
                    f"⛏️ *Auto-recolección* ({pendientes} pendientes)\n\n"
                    f"{resultado}"
                ),
                parse_mode="Markdown"
            )
        except Exception:
            pass


# ==================== HELPERS ====================

def tiene_auto_recoleccion(user_id: int) -> bool:
    try:
        import membresia as _mem
        return _mem.tiene_membresia(user_id, "auto_recoleccion")
    except Exception:
        return False


# ==================== PANEL JUGADOR ====================

async def cmd_auto_recoleccion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not db_helper.obtener_jugador(user_id):
        await update.effective_message.reply_text("Primero crea un personaje con /start.")
        return
    if not tiene_auto_recoleccion(user_id):
        await update.effective_message.reply_text(
            "⛏️ *Recolección Automática* no disponible.\n\n"
            "Requiere la membresía *⛏️ Recolección Automática* o la *👑 Membresía Completa*.\n"
            "Compra desde /membresia.",
            parse_mode="Markdown"
        )
        return
    await _panel_auto(update, context, user_id, editar=False)


async def _panel_auto(update, context, user_id: int, editar: bool = True):
    row    = _get_row(user_id)
    activo = row["activo"]
    zonas  = row["zonas"]

    # Texto de próxima colecta
    proximo_txt = ""
    if activo and row["ultimo_ts"]:
        try:
            dt     = datetime.fromisoformat(row["ultimo_ts"])
            faltan = int(COOLDOWN_SEG - (datetime.now() - dt).total_seconds())
            if faltan > 0:
                proximo_txt = f" — próxima en {faltan}s"
        except Exception:
            pass

    estado_txt      = f"🟢 En progreso{proximo_txt}" if activo else "🔴 Detenida"
    total_pendientes = sum(max(0, z.get("total", 0) - z.get("hecho", 0)) for z in zonas)

    texto = (
        f"⛏️ *Recolección Automática*\n\n"
        f"Estado: {estado_txt}\n"
        f"Cola total: *{total_pendientes}* colectas pendientes\n\n"
        "*Zonas:*\n"
    )
    if not zonas:
        texto += "_Ninguna zona añadida. Usa los botones de abajo._\n"
    for z in zonas:
        em    = EMOJI_COLOR.get(z["color"], "❓")
        nb    = NOMBRE_COLOR.get(z["color"], z["color"])
        hecho = z.get("hecho", 0)
        total = z.get("total", 0)
        texto += f"{em} {nb}: {hecho}/{total} completadas\n"

    texto += "\n_Stamina gastada = colectas realizadas × coste normal._"

    # ── Teclado ──
    kb = []

    costo = int(db_helper.obtener_config("stamina_recolectar", "5"))
    st_actual, st_max, _ = db_helper.obtener_stamina(user_id)
    kb.append([InlineKeyboardButton(f"⚡ Stamina: {st_actual}/{st_max}  (coste: {costo}/colecta)", callback_data="arc_noop")])

    for color in COLORES:
        z     = _get_zona(zonas, color)
        em    = EMOJI_COLOR[color]
        nb    = NOMBRE_COLOR[color]
        total = z["total"] if z else 0
        hecho = z.get("hecho", 0) if z else 0
        rest  = total - hecho

        if z and total > 0:
            kb.append([
                InlineKeyboardButton(f"❌ {em} {nb}", callback_data=f"arc_qtar_{color}"),
                InlineKeyboardButton("➖5", callback_data=f"arc_adj_{color}_m5"),
                InlineKeyboardButton("➖1", callback_data=f"arc_adj_{color}_m1"),
                InlineKeyboardButton(f"{rest}", callback_data="arc_noop"),
                InlineKeyboardButton("➕1", callback_data=f"arc_adj_{color}_p1"),
                InlineKeyboardButton("➕5", callback_data=f"arc_adj_{color}_p5"),
            ])
        else:
            kb.append([
                InlineKeyboardButton(f"➕ {em} {nb} (añadir)", callback_data=f"arc_add_{color}")
            ])

    if activo:
        kb.append([InlineKeyboardButton("⏹️ Detener", callback_data="arc_detener")])
    else:
        if total_pendientes > 0:
            kb.append([InlineKeyboardButton("▶️ Iniciar", callback_data="arc_iniciar")])
        else:
            kb.append([InlineKeyboardButton("▶️ Iniciar (añade zonas primero)", callback_data="arc_noop")])

    kb.append([
        InlineKeyboardButton("🔄 Actualizar", callback_data="arc_panel"),
        InlineKeyboardButton("🔙 Membresías", callback_data="memb_panel"),
    ])

    markup = InlineKeyboardMarkup(kb)
    if editar and update.callback_query:
        try:
            await update.callback_query.edit_message_text(texto, reply_markup=markup, parse_mode="Markdown")
            return
        except Exception:
            pass
    await update.effective_message.reply_text(texto, reply_markup=markup, parse_mode="Markdown")


# ==================== CALLBACKS ====================

async def _cb_noop(update, context):
    await update.callback_query.answer()


async def _cb_panel(update, context):
    await update.callback_query.answer()
    await _panel_auto(update, context, update.effective_user.id, editar=True)


async def _cb_add_zona(update, context):
    query   = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    color   = query.data.replace("arc_add_", "")
    if color not in COLORES:
        return
    row   = _get_row(user_id)
    zonas = row["zonas"]
    if not _get_zona(zonas, color):
        zonas.append({"color": color, "total": 5, "hecho": 0})
    _save_row(user_id, row["activo"], row["ultimo_ts"], zonas)
    await _panel_auto(update, context, user_id, editar=True)


async def _cb_quitar_zona(update, context):
    query   = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    color   = query.data.replace("arc_qtar_", "")
    row     = _get_row(user_id)
    zonas   = _remove_zona(row["zonas"], color)
    _save_row(user_id, row["activo"], row["ultimo_ts"], zonas)
    await _panel_auto(update, context, user_id, editar=True)


async def _cb_adj_zona(update, context):
    """arc_adj_{color}_{p1|m1|p5|m5} — p = plus, m = minus."""
    query   = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    # data = "arc_adj_azul_p5"
    parts = query.data.split("_")
    if len(parts) < 4:
        return
    color    = parts[2]
    raw      = parts[3]          # p1 / m1 / p5 / m5
    sign     = 1 if raw[0] == "p" else -1
    try:
        cantidad = int(raw[1:]) * sign
    except ValueError:
        return

    row = _get_row(user_id)
    z   = _get_zona(row["zonas"], color)
    if not z:
        return
    z["total"] = max(1, min(MAX_COLECTAS, z["total"] + cantidad))
    _save_row(user_id, row["activo"], row["ultimo_ts"], row["zonas"])
    await _panel_auto(update, context, user_id, editar=True)


async def _cb_iniciar(update, context):
    query   = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    if not tiene_auto_recoleccion(user_id):
        await query.answer("❌ Necesitas la membresía de Recolección Automática.", show_alert=True)
        return

    row   = _get_row(user_id)
    zonas = row["zonas"]

    if not zonas or all(z.get("total", 0) <= 0 for z in zonas):
        await query.answer("⚠️ Añade al menos una zona antes de iniciar.", show_alert=True)
        return

    # Reiniciar contadores "hecho"
    for z in zonas:
        z["hecho"] = 0

    _save_row(user_id, 1, None, zonas)
    await _panel_auto(update, context, user_id, editar=True)


async def _cb_detener(update, context):
    query   = update.callback_query
    await query.answer("⏹️ Recolección detenida.")
    user_id = update.effective_user.id
    row     = _get_row(user_id)
    _save_row(user_id, 0, row["ultimo_ts"], row["zonas"])
    await _panel_auto(update, context, user_id, editar=True)


# ==================== REGISTRO ====================

def registrar_handlers(app):
    app.add_handler(CommandHandler("auto_recoleccion", cmd_auto_recoleccion))

    app.add_handler(CallbackQueryHandler(_cb_noop,       pattern="^arc_noop$"))
    app.add_handler(CallbackQueryHandler(_cb_panel,      pattern="^arc_panel$"))
    app.add_handler(CallbackQueryHandler(_cb_add_zona,   pattern="^arc_add_"))
    app.add_handler(CallbackQueryHandler(_cb_quitar_zona, pattern="^arc_qtar_"))
    app.add_handler(CallbackQueryHandler(_cb_adj_zona,   pattern="^arc_adj_"))
    app.add_handler(CallbackQueryHandler(_cb_iniciar,    pattern="^arc_iniciar$"))
    app.add_handler(CallbackQueryHandler(_cb_detener,    pattern="^arc_detener$"))

    # Job: cada 30 s revisa si hay colectas pendientes (respeta cooldown de 90 s internamente)
    app.job_queue.run_repeating(job_auto_recoleccion, interval=30, first=15)

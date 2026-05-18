#!/usr/bin/env python3
"""
login_diario.py — Sistema de recompensa por login diario con racha.

Cada día que el jugador interactúa por primera vez recibe una recompensa.
Si no entra un día, la racha se reinicia.

Recompensas de racha:
  Día 1:  50 oro
  Día 2: 100 oro
  Día 3: 150 oro + 1 Poción de Vida Menor
  Día 4: 200 oro
  Día 5: 250 oro
  Día 6: 300 oro
  Día 7: 500 oro + 5 Eternium + 1 Poción de Vida Mayor  ← Racha completa
  Día 8+: vuelve a día 1

Comandos jugador: /login  — reclamar recompensa del día
Admin: activable/desactivable desde panel de automatizaciones
"""

import sqlite3
import logging
from datetime import datetime, date, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
import db_helper

logger = logging.getLogger(__name__)
DB_PATH = "aethelgard.db"

# ── Tabla ──────────────────────────────────────────────────────────────────────

def _init_tabla():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS login_diario (
            user_id     INTEGER PRIMARY KEY,
            racha       INTEGER DEFAULT 0,
            ultimo_login DATE,
            total_logins INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

# ── Configuración activo/inactivo ──────────────────────────────────────────────

def _activo() -> bool:
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT valor FROM config_bot WHERE clave = 'login_diario_activo'")
        row = c.fetchone()
        conn.close()
        return (row[0] if row else "1") == "1"
    except Exception:
        return True

# ── Recompensas por día de racha ───────────────────────────────────────────────

RECOMPENSAS = {
    1: {"oro": 50,  "eternium": 0, "item": None,                     "emoji": "🌅"},
    2: {"oro": 100, "eternium": 0, "item": None,                     "emoji": "🌤️"},
    3: {"oro": 150, "eternium": 0, "item": "Poción de Vida Menor",   "emoji": "⭐"},
    4: {"oro": 200, "eternium": 0, "item": None,                     "emoji": "🌟"},
    5: {"oro": 250, "eternium": 0, "item": None,                     "emoji": "💫"},
    6: {"oro": 300, "eternium": 0, "item": None,                     "emoji": "✨"},
    7: {"oro": 500, "eternium": 5, "item": "Poción de Vida Mayor",   "emoji": "🏆"},
}

def _recompensa_dia(racha: int) -> dict:
    dia = min(racha, 7)
    return RECOMPENSAS.get(dia, RECOMPENSAS[1])

# ── Estado del login del jugador ───────────────────────────────────────────────

def _estado_login(user_id: int) -> dict:
    """Devuelve {racha, ultimo_login, puede_reclamar, total_logins}."""
    _init_tabla()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT racha, ultimo_login, total_logins FROM login_diario WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()

    hoy = date.today()
    if not row:
        return {"racha": 0, "ultimo_login": None, "puede_reclamar": True, "total_logins": 0}

    racha, ultimo_str, total = row
    ultimo = date.fromisoformat(ultimo_str) if ultimo_str else None

    if ultimo is None:
        return {"racha": racha, "ultimo_login": None, "puede_reclamar": True, "total_logins": total}

    if ultimo == hoy:
        return {"racha": racha, "ultimo_login": ultimo, "puede_reclamar": False, "total_logins": total}

    if (hoy - ultimo).days == 1:
        return {"racha": racha, "ultimo_login": ultimo, "puede_reclamar": True, "total_logins": total}

    # Racha rota (faltó más de un día)
    return {"racha": 0, "ultimo_login": ultimo, "puede_reclamar": True, "total_logins": total}


def _reclamar_login(user_id: int) -> dict | None:
    """Registra el login y entrega la recompensa. Retorna dict con la recompensa o None si ya reclamó."""
    _init_tabla()
    estado = _estado_login(user_id)

    if not estado["puede_reclamar"]:
        return None

    nueva_racha = estado["racha"] + 1
    if nueva_racha > 7:
        nueva_racha = 1

    recompensa = _recompensa_dia(nueva_racha)
    hoy = date.today().isoformat()

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO login_diario (user_id, racha, ultimo_login, total_logins)
        VALUES (?, ?, ?, 1)
        ON CONFLICT(user_id) DO UPDATE SET
            racha        = excluded.racha,
            ultimo_login = excluded.ultimo_login,
            total_logins = total_logins + 1
    """, (user_id, nueva_racha, hoy))
    conn.commit()
    conn.close()

    # Entregar recompensas
    if recompensa["oro"] > 0:
        db_helper.sumar_oro(user_id, recompensa["oro"])
    if recompensa["eternium"] > 0:
        db_helper.sumar_eternium(user_id, recompensa["eternium"])
    if recompensa["item"]:
        db_helper.agregar_item(user_id, recompensa["item"], 1)

    return {"racha": nueva_racha, **recompensa}


# ── Texto del panel de login ───────────────────────────────────────────────────

def _texto_panel(user_id: int) -> tuple[str, InlineKeyboardMarkup]:
    estado = _estado_login(user_id)
    racha_actual = estado["racha"]
    puede = estado["puede_reclamar"]
    total = estado["total_logins"]

    lineas = ["🗓️ <b>LOGIN DIARIO</b>\n"]

    # Barra de progreso de racha
    for dia in range(1, 8):
        r = RECOMPENSAS[dia]
        if dia < racha_actual:
            icono = "✅"
        elif dia == racha_actual and not puede:
            icono = r["emoji"]
        else:
            icono = "⬜"
        item_str = f" + {r['item']}" if r['item'] else ""
        lineas.append(f"{icono} Día {dia}: {r['oro']}🪙"
                      + (f" + {r['eternium']}💎" if r['eternium'] else "")
                      + item_str)

    lineas.append(f"\n🔥 Racha actual: <b>{racha_actual}/7 días</b>")
    lineas.append(f"📊 Logins totales: {total}")

    if puede:
        dia_prox = min(racha_actual + 1, 7) if racha_actual < 7 else 1
        prox = RECOMPENSAS[dia_prox]
        prox_str = f"{prox['oro']}🪙"
        if prox['eternium']:
            prox_str += f" + {prox['eternium']}💎"
        if prox['item']:
            prox_str += f" + {prox['item']}"
        lineas.append(f"\n🎁 Recompensa de hoy (día {dia_prox}): <b>{prox_str}</b>")
        boton = InlineKeyboardButton("🎁 ¡Reclamar recompensa de hoy!", callback_data="login_reclamar")
    else:
        lineas.append("\n✅ Ya reclamaste tu recompensa de hoy. ¡Vuelve mañana!")
        boton = InlineKeyboardButton("✅ Ya reclamado hoy", callback_data="login_ya_reclamado")

    teclado = InlineKeyboardMarkup([[boton], [InlineKeyboardButton("❌ Cerrar", callback_data="login_cerrar")]])
    return "\n".join(lineas), teclado


# ── Handlers ──────────────────────────────────────────────────────────────────

async def cmd_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not db_helper.existe_jugador(user_id):
        await update.message.reply_text("⚠️ Primero debes registrarte con /start.")
        return
    if not _activo():
        await update.message.reply_text("⚠️ El sistema de login diario está desactivado temporalmente.")
        return

    texto, teclado = _texto_panel(user_id)
    await update.message.reply_text(texto, parse_mode="HTML", reply_markup=teclado)


async def cb_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    if query.data == "login_cerrar":
        await query.delete_message()
        return

    if query.data == "login_ya_reclamado":
        await query.answer("✅ Ya reclamaste hoy. Vuelve mañana.", show_alert=True)
        return

    if query.data == "login_reclamar":
        if not _activo():
            await query.answer("⚠️ Sistema desactivado.", show_alert=True)
            return
        resultado = _reclamar_login(user_id)
        if resultado is None:
            await query.answer("✅ Ya reclamaste hoy.", show_alert=True)
        else:
            premio = f"{resultado['oro']}🪙"
            if resultado['eternium']:
                premio += f" + {resultado['eternium']}💎"
            if resultado['item']:
                premio += f" + {resultado['item']}"
            await query.answer(f"🎁 Día {resultado['racha']}! Recibiste: {premio}", show_alert=True)

            # Actualizar el panel
            texto, teclado = _texto_panel(user_id)
            try:
                await query.edit_message_text(texto, parse_mode="HTML", reply_markup=teclado)
            except Exception:
                pass

            # Guía contextual
            try:
                import guia_contextual as _gc
                if _gc._guia_activa(user_id):
                    from telegram_queue import rate_limiter
                    await rate_limiter.send(
                        context.bot, user_id,
                        f"📖 <b>GUÍA:</b> ¡Reclamaste tu recompensa de login diario!\n"
                        f"🔥 Racha actual: {resultado['racha']}/7 días.\n"
                        f"💡 Vuelve cada día para mantener tu racha y obtener recompensas mayores.",
                        parse_mode="HTML"
                    )
            except Exception:
                pass


def registrar_handlers(app):
    _init_tabla()
    app.add_handler(CommandHandler("login", cmd_login))
    app.add_handler(CallbackQueryHandler(cb_login, pattern="^login_"))

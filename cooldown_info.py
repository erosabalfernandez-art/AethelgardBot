#!/usr/bin/env python3
"""
cooldown_info.py — Muestra todos los cooldowns activos del jugador con tiempo restante.

Comandos: /cooldowns  — ver todos los cooldowns activos
Admin: activable/desactivable desde panel de automatizaciones
"""

import sqlite3
import logging
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
import db_helper

logger = logging.getLogger(__name__)
DB_PATH = "aethelgard.db"


def _activo() -> bool:
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT valor FROM config_bot WHERE clave = 'cooldown_info_activo'")
        row = c.fetchone()
        conn.close()
        return (row[0] if row else "1") == "1"
    except Exception:
        return True


def _fmt_tiempo(segundos: float) -> str:
    """Formatea segundos en formato legible."""
    if segundos <= 0:
        return "¡Listo!"
    s = int(segundos)
    if s < 60:
        return f"{s}s"
    m, s = divmod(s, 60)
    if m < 60:
        return f"{m}m {s}s"
    h, m = divmod(m, 60)
    return f"{h}h {m}m"


def obtener_cooldowns(user_id: int) -> list[dict]:
    """Recopila todos los cooldowns activos del jugador."""
    cooldowns = []
    ahora = datetime.now()

    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        return []

    # Stamina
    try:
        actual, maxi, _ = db_helper.obtener_stamina(user_id)
        if actual < maxi:
            try:
                from config_balance import STAMINA_REGENERACION_SEGUNDOS as seg_regen
            except ImportError:
                seg_regen = 180
            faltante = maxi - actual
            segundos_total = faltante * seg_regen
            cooldowns.append({
                "nombre": "⚡ Stamina",
                "estado": f"{actual}/{maxi}",
                "restante": segundos_total,
                "texto": f"⚡ Stamina: {actual}/{maxi} — llena en {_fmt_tiempo(segundos_total)}"
            })
        else:
            cooldowns.append({
                "nombre": "⚡ Stamina",
                "estado": f"{actual}/{maxi} ✅",
                "restante": 0,
                "texto": f"⚡ Stamina: {actual}/{maxi} — ¡Completa!"
            })
    except Exception:
        pass

    # Recolección
    try:
        ultima = jug.get("ultima_recoleccion")
        if ultima:
            from config_balance import RECOLECCION_COOLDOWN_SEGUNDOS as cd_rec
            ult_dt = datetime.fromisoformat(ultima)
            diff = (ahora - ult_dt).total_seconds()
            restante = max(0, cd_rec - diff)
            if restante > 0:
                cooldowns.append({
                    "nombre": "⛏️ Recolección",
                    "restante": restante,
                    "texto": f"⛏️ Recolección: disponible en {_fmt_tiempo(restante)}"
                })
            else:
                cooldowns.append({
                    "nombre": "⛏️ Recolección",
                    "restante": 0,
                    "texto": "⛏️ Recolección: ¡Lista!"
                })
    except Exception:
        pass

    # Actividad actual (viaje, mazmorra, recolección en curso)
    try:
        actividad = jug.get("actividad_actual")
        expira_str = jug.get("actividad_expira")
        if actividad and expira_str:
            expira = datetime.fromisoformat(expira_str)
            restante = max(0, (expira - ahora).total_seconds())
            if restante > 0:
                nombres_act = {
                    "recoleccion": "⛏️ Recolección en curso",
                    "investigacion": "🔍 Investigación en curso",
                    "viaje": "✈️ Viaje en curso",
                    "mazmorra": "🏰 En mazmorra",
                }
                nombre_act = nombres_act.get(actividad, f"🔄 {actividad.capitalize()} en curso")
                cooldowns.append({
                    "nombre": nombre_act,
                    "restante": restante,
                    "texto": f"{nombre_act}: termina en {_fmt_tiempo(restante)}"
                })
    except Exception:
        pass

    # Teletransporte
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT ultimo_uso FROM teletransporte_cooldown WHERE jugador_id = ?", (user_id,))
        row = c.fetchone()
        conn.close()
        if row and row[0]:
            from config_balance import VUELO_RAPIDO_COOLDOWN_SEGUNDOS as cd_vuelo
            ult = datetime.fromisoformat(row[0])
            restante = max(0, cd_vuelo - (ahora - ult).total_seconds())
            if restante > 0:
                cooldowns.append({
                    "nombre": "⚡ Vuelo rápido",
                    "restante": restante,
                    "texto": f"⚡ Vuelo rápido: disponible en {_fmt_tiempo(restante)}"
                })
    except Exception:
        pass

    # Marcado (rescate)
    try:
        if jug.get("estado_marcado") and jug.get("marca_expiracion"):
            expira = datetime.fromisoformat(jug["marca_expiracion"])
            restante = max(0, (expira - ahora).total_seconds())
            if restante > 0:
                cooldowns.append({
                    "nombre": "🎯 Marcado",
                    "restante": restante,
                    "texto": f"🎯 Marcado (rescate pendiente): expira en {_fmt_tiempo(restante)}"
                })
    except Exception:
        pass

    return cooldowns


async def cmd_cooldowns(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        await update.message.reply_text("⚠️ Primero regístrate con /start.")
        return
    if not _activo():
        await update.message.reply_text("⚠️ El panel de cooldowns está desactivado.")
        return

    cds = obtener_cooldowns(user_id)
    if not cds:
        await update.message.reply_text("✅ No tienes cooldowns activos. ¡Todo listo para jugar!")
        return

    lineas = ["⏱️ <b>TUS COOLDOWNS ACTIVOS</b>\n"]
    pendientes = [c for c in cds if c["restante"] > 0]
    listos = [c for c in cds if c["restante"] == 0]

    if pendientes:
        lineas.append("🔴 <b>En espera:</b>")
        for c in sorted(pendientes, key=lambda x: x["restante"]):
            lineas.append(f"  • {c['texto']}")

    if listos:
        lineas.append("\n🟢 <b>Listos para usar:</b>")
        for c in listos:
            lineas.append(f"  • {c['texto']}")

    lineas.append("\n💡 <i>Usa /misiones_hoy para ver tus misiones diarias.</i>")

    await update.message.reply_text("\n".join(lineas), parse_mode="HTML")


def registrar_handlers(app):
    app.add_handler(CommandHandler("cooldowns", cmd_cooldowns))
    app.add_handler(CommandHandler("cd", cmd_cooldowns))

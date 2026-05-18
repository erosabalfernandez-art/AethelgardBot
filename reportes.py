"""
reportes.py — Canal directo superadmin → agente IA.

Uso en Telegram:
  /reporte <mensaje>   — envía un reporte al agente
  /reportes_ver        — muestra los últimos 10 reportes enviados

Flujo de trabajo con el agente:
  1. Superadmin envía /reporte <error> en Telegram
  2. Superadmin escribe cualquier cosa en el chat de Replit (p.ej. "r")
  3. El agente lee reportes_queue.jsonl, arregla el error, reinicia el bot
  4. El agente llama push_notif.py → el superadmin recibe confirmación en Telegram

Archivos:
  reportes_ia.log      — historial legible (todos los reportes)
  reportes_queue.jsonl — cola con estado done:true/false (solo pendientes activos)
"""
import os
import json
import html as _html
from datetime import datetime
from pathlib import Path

from telegram import Update
from telegram.ext import ContextTypes, CommandHandler

import superadmin as sa

# ── Rutas ─────────────────────────────────────────────────────────────────────
_BASE      = Path(__file__).parent
LOG_FILE   = _BASE / "reportes_ia.log"
QUEUE_FILE = _BASE / "reportes_queue.jsonl"


def _e(s) -> str:
    return _html.escape(str(s) if s is not None else "")


# ── Escritura ─────────────────────────────────────────────────────────────────

def _guardar(user_id: int, mensaje: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Log legible (historial permanente)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] USER:{user_id} | {mensaje}\n")

    # Cola con estado (para que el agente sepa qué está pendiente)
    entrada = {"ts": ts, "user_id": user_id, "msg": mensaje, "done": False}
    with open(QUEUE_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entrada, ensure_ascii=False) + "\n")

    # Visible en los logs del workflow
    print(f"📩 REPORTE_IA [{ts}] {user_id} | {mensaje}", flush=True)


# ── Lectura de cola ───────────────────────────────────────────────────────────

def obtener_pendientes() -> list[dict]:
    """Devuelve los reportes aún no resueltos (done=False)."""
    if not QUEUE_FILE.exists():
        return []
    pendientes = []
    for line in QUEUE_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
            if not entry.get("done", False):
                pendientes.append(entry)
        except json.JSONDecodeError:
            pass
    return pendientes


def marcar_todos_resueltos():
    """Marca todos los reportes pendientes como resueltos."""
    if not QUEUE_FILE.exists():
        return
    lineas = QUEUE_FILE.read_text(encoding="utf-8").splitlines()
    nuevas = []
    for line in lineas:
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
            entry["done"] = True
            nuevas.append(json.dumps(entry, ensure_ascii=False))
        except json.JSONDecodeError:
            nuevas.append(line)
    QUEUE_FILE.write_text("\n".join(nuevas) + "\n", encoding="utf-8")


def _leer_ultimos(n: int = 10) -> list[str]:
    if not LOG_FILE.exists():
        return []
    lineas = LOG_FILE.read_text(encoding="utf-8").splitlines()
    return [l for l in lineas if l.strip()][-n:]


# ── Comandos ──────────────────────────────────────────────────────────────────

async def cmd_reporte(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /reporte <mensaje>
    Envía un mensaje/error al agente IA para que lo revise.
    """
    user_id = update.effective_user.id
    if not sa.verificar_superadmin(user_id):
        await update.effective_message.reply_text("❌ Solo el superadmin puede usar este comando.")
        return

    if not context.args:
        await update.effective_message.reply_text(
            "📩 Uso: <code>/reporte &lt;mensaje&gt;</code>\n\n"
            "Ejemplos:\n"
            "• <code>/reporte /ciudad → botón Servicios no responde</code>\n"
            "• <code>/reporte al hacer /duelo sale error de None</code>\n\n"
            "Después de enviar el reporte, escribe cualquier cosa en el chat de Replit "
            "y el agente lo arreglará y te avisará aquí.",
            parse_mode="HTML"
        )
        return

    mensaje = " ".join(context.args)
    _guardar(user_id, mensaje)

    resumen = mensaje[:300] + ("…" if len(mensaje) > 300 else "")
    await update.effective_message.reply_text(
        f"📩 <b>Reporte enviado.</b>\n\n"
        f"📝 <code>{_e(resumen)}</code>\n\n"
        f"🕐 {datetime.now().strftime('%H:%M:%S')}\n\n"
        f"⏳ Ahora ve al chat de Replit y escribe cualquier cosa — "
        f"el agente leerá esto, lo arreglará y te confirmará aquí en Telegram.",
        parse_mode="HTML"
    )


async def cmd_reportes_ver(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /reportes_ver
    Muestra los últimos 10 reportes enviados.
    """
    user_id = update.effective_user.id
    if not sa.verificar_superadmin(user_id):
        await update.effective_message.reply_text("❌ Solo el superadmin puede usar este comando.")
        return

    ultimos = _leer_ultimos(10)
    if not ultimos:
        await update.effective_message.reply_text("📭 No hay reportes enviados todavía.")
        return

    pendientes = {e["ts"] + "|" + e["msg"] for e in obtener_pendientes()}

    lineas = []
    for l in ultimos:
        # Extraer ts y msg del formato "[ts] USER:xxx | msg"
        partes = l.split(" | ", 1)
        estado = "⏳" if any(p in l for p in pendientes) else "✅"
        lineas.append(f"{estado} <code>{_e(l)}</code>")

    await update.effective_message.reply_text(
        f"📋 <b>Últimos {len(ultimos)} reportes:</b>\n\n" + "\n".join(lineas),
        parse_mode="HTML"
    )


# ── Registro ──────────────────────────────────────────────────────────────────

def registrar_handlers(app):
    app.add_handler(CommandHandler("reporte",      cmd_reporte))
    app.add_handler(CommandHandler("reportes_ver", cmd_reportes_ver))

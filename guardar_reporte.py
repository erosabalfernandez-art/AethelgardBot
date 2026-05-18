"""
guardar_reporte.py — Comando /guardar_reporte para admins.
Guarda un reporte de texto en un archivo .py independiente con timestamp.
Solo accesible por superadmin y admins de nivel 1+.
"""

import os
import re
from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes, CommandHandler

import superadmin as _sa

REPORTES_DIR = os.path.join(os.path.dirname(__file__), "reportes_guardados")


def _sanitizar(texto: str) -> str:
    return re.sub(r'[^\w\sáéíóúÁÉÍÓÚñÑüÜ.,;:!?@#\-_()/\n]', '', texto)


async def cmd_guardar_reporte(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not _sa._es_admin(user_id, nivel_minimo=1):
        await update.effective_message.reply_text("❌ Solo los admins pueden usar este comando.")
        return

    texto = " ".join(context.args).strip() if context.args else ""
    if not texto:
        await update.effective_message.reply_text(
            "✍️ Escribe el reporte después del comando.\n"
            "Ejemplo: `/guardar_reporte Hoy los jugadores reportaron lag en mazmorra roja.`",
            parse_mode="Markdown",
        )
        return

    os.makedirs(REPORTES_DIR, exist_ok=True)

    now = datetime.now()
    ts_nombre = now.strftime("%Y%m%d_%H%M%S")
    ts_legible = now.strftime("%Y-%m-%d %H:%M:%S")

    nombre_archivo = f"reporte_{ts_nombre}.py"
    ruta = os.path.join(REPORTES_DIR, nombre_archivo)

    autor_nombre = update.effective_user.full_name or str(user_id)
    nivel = _sa._nivel_admin(user_id)
    rol = "Superadmin" if nivel == 99 else f"Admin nivel {nivel}"

    contenido = (
        f'"""\n'
        f'Reporte guardado por {autor_nombre} ({rol})\n'
        f'Fecha: {ts_legible}\n'
        f'"""\n\n'
        f'FECHA    = "{ts_legible}"\n'
        f'AUTOR    = "{autor_nombre}"\n'
        f'ROL      = "{rol}"\n'
        f'REPORTE  = """\n{texto}\n"""\n'
    )

    with open(ruta, "w", encoding="utf-8") as f:
        f.write(contenido)

    await update.effective_message.reply_text(
        f"✅ *Reporte guardado correctamente.*\n\n"
        f"📄 Archivo: `reportes_guardados/{nombre_archivo}`\n"
        f"🕐 Fecha: {ts_legible}",
        parse_mode="Markdown",
    )


def registrar_handlers(app):
    app.add_handler(CommandHandler("guardar_reporte", cmd_guardar_reporte))

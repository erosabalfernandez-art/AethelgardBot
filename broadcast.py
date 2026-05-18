"""
broadcast.py — Sistema de notificaciones push con control de tráfico.

Funciones públicas:
  broadcast_activos(bot, mensaje, parse_mode, ventana)
      → envía solo a jugadores activos en los últimos N segundos (por defecto 10 min)
      → rate-limit: 20 mensajes/segundo
      → ejecución asíncrona (no bloquea el bot)

  broadcast_global(bot, mensaje, reply_markup, parse_mode)
      → envía a TODOS los jugadores (sin filtro de actividad)
      → mismo rate-limit y ejecución asíncrona
      → backward-compatible con jefes.py, automatizaciones.py, guerra_facciones.py

  push_a_jugador(bot, user_id, mensaje, reply_markup)
      → envía a un jugador específico y guarda en su bandeja

Comandos de superadmin:
  /broadcast_activos <mensaje>  — envía a jugadores activos (últimos 10 min)
  /broadcast_todos   <mensaje>  — envía a todos los jugadores registrados
"""
import asyncio
import html as _html

from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, TypeHandler

import db_helper
import superadmin as sa

# ── Constantes ────────────────────────────────────────────────────────────────
_MSG_POR_SEGUNDO = 20                       # límite seguro para bots de Telegram
_DELAY           = 1.0 / _MSG_POR_SEGUNDO   # 0.05 s entre mensajes
_VENTANA_ACTIVOS = 600                      # 10 minutos en segundos


# ── Helper de escape HTML ─────────────────────────────────────────────────────
def _e(s) -> str:
    return _html.escape(str(s) if s is not None else "")


# ── Tracker de actividad (TypeHandler en grupo -1) ───────────────────────────
async def _registrar_actividad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Intercepta CUALQUIER actualización y registra la marca de tiempo del usuario.
    Corre en paralelo (block=False) para no añadir latencia a los handlers normales.
    """
    user = update.effective_user
    if user and not user.is_bot:
        try:
            db_helper.registrar_actividad(user.id)
        except Exception:
            pass


# ── Tarea interna de envío masivo ─────────────────────────────────────────────
async def _tarea_envio(bot, jugadores: list, mensaje: str,
                       parse_mode: str, reply_markup=None) -> tuple:
    """
    Envía `mensaje` a cada jugador de la lista respetando el rate-limit.
    Devuelve (enviados, fallidos).
    """
    enviados = 0
    fallidos = 0
    for jug in jugadores:
        uid = jug["user_id"]
        try:
            await bot.send_message(
                chat_id=uid,
                text=mensaje,
                parse_mode=parse_mode,
                reply_markup=reply_markup,
            )
            enviados += 1
        except Exception:
            fallidos += 1
        try:
            db_helper.agregar_notificacion(uid, mensaje)
        except Exception:
            pass
        await asyncio.sleep(_DELAY)
    return enviados, fallidos


# ── API pública ───────────────────────────────────────────────────────────────
async def broadcast_activos(
    bot,
    mensaje: str,
    parse_mode: str = "HTML",
    ventana: int = _VENTANA_ACTIVOS,
    reply_markup=None,
) -> asyncio.Task:
    """
    Envía `mensaje` a los jugadores que han interactuado en los últimos
    `ventana` segundos. La tarea corre en segundo plano; el bot sigue
    respondiendo normalmente durante el envío.
    """
    jugadores = db_helper.obtener_jugadores_activos(ventana)
    return asyncio.create_task(
        _tarea_envio(bot, jugadores, mensaje, parse_mode, reply_markup)
    )


async def broadcast_global(
    bot,
    mensaje: str,
    reply_markup=None,
    parse_mode: str = "HTML",
) -> asyncio.Task:
    """
    Envía `mensaje` a TODOS los jugadores registrados.
    Backward-compatible con jefes.py, automatizaciones.py y guerra_facciones.py.
    La tarea corre en segundo plano.
    """
    jugadores = db_helper.obtener_todos_jugadores()
    return asyncio.create_task(
        _tarea_envio(bot, jugadores, mensaje, parse_mode, reply_markup)
    )


async def push_a_jugador(
    bot,
    user_id: int,
    mensaje: str,
    reply_markup=None,
    parse_mode: str = "HTML",
):
    """
    Envía un mensaje push a un jugador específico y lo guarda en su bandeja.
    """
    try:
        await bot.send_message(
            chat_id=user_id,
            text=mensaje,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
        )
    except Exception:
        pass
    try:
        db_helper.agregar_notificacion(user_id, mensaje)
    except Exception:
        pass


# ── Comandos de superadmin ────────────────────────────────────────────────────
async def cmd_broadcast_activos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /broadcast_activos <mensaje>
    Envía a jugadores activos en los últimos 10 minutos.
    """
    if not sa.verificar_superadmin(update.effective_user.id):
        await update.effective_message.reply_text("❌ Solo el superadmin puede usar este comando.")
        return

    if not context.args:
        await update.effective_message.reply_text(
            "Uso: <code>/broadcast_activos &lt;mensaje&gt;</code>\n\n"
            "Envía el mensaje solo a jugadores activos en los últimos 10 minutos.",
            parse_mode="HTML"
        )
        return

    mensaje = " ".join(context.args)
    jugadores = db_helper.obtener_jugadores_activos(_VENTANA_ACTIVOS)
    total = len(jugadores)

    if total == 0:
        await update.effective_message.reply_text(
            "⚠️ No hay jugadores activos en los últimos 10 minutos."
        )
        return

    segundos_est = max(1, total // _MSG_POR_SEGUNDO + 1)
    aviso = await update.effective_message.reply_text(
        f"📡 Enviando a <b>{total}</b> jugador(es) activo(s)...\n"
        f"⏱️ Tiempo estimado: <b>~{segundos_est}s</b>\n"
        f"El bot sigue respondiendo durante el envío.",
        parse_mode="HTML"
    )

    task = await broadcast_activos(context.bot, mensaje)

    async def _fin(t, msg):
        try:
            enviados, fallidos = await t
            await msg.edit_text(
                f"✅ Broadcast completado.\n"
                f"📤 Enviados: <b>{enviados}</b>  ❌ Fallidos: <b>{fallidos}</b>",
                parse_mode="HTML"
            )
        except Exception:
            pass

    asyncio.create_task(_fin(task, aviso))


async def cmd_broadcast_todos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /broadcast_todos <mensaje>
    Envía a TODOS los jugadores registrados.
    """
    if not sa.verificar_superadmin(update.effective_user.id):
        await update.effective_message.reply_text("❌ Solo el superadmin puede usar este comando.")
        return

    if not context.args:
        await update.effective_message.reply_text(
            "Uso: <code>/broadcast_todos &lt;mensaje&gt;</code>\n\n"
            "⚠️ Envía a <b>todos</b> los jugadores registrados, estén activos o no.",
            parse_mode="HTML"
        )
        return

    mensaje = " ".join(context.args)
    jugadores = db_helper.obtener_todos_jugadores()
    total = len(jugadores)
    segundos_est = max(1, total // _MSG_POR_SEGUNDO + 1)

    aviso = await update.effective_message.reply_text(
        f"📡 Enviando a <b>{total}</b> jugador(es) registrado(s)...\n"
        f"⏱️ Tiempo estimado: <b>~{segundos_est}s</b>\n"
        f"El bot sigue respondiendo durante el envío.",
        parse_mode="HTML"
    )

    task = await broadcast_global(context.bot, mensaje)

    async def _fin(t, msg):
        try:
            enviados, fallidos = await t
            await msg.edit_text(
                f"✅ Broadcast completado.\n"
                f"📤 Enviados: <b>{enviados}</b>  ❌ Fallidos: <b>{fallidos}</b>",
                parse_mode="HTML"
            )
        except Exception:
            pass

    asyncio.create_task(_fin(task, aviso))


# ── Registro de handlers ──────────────────────────────────────────────────────
def registrar_handlers(app):
    # Tracker de actividad: intercepta toda actualización sin bloquear el flujo
    app.add_handler(
        TypeHandler(Update, _registrar_actividad, block=False),
        group=-1
    )
    # Comandos de broadcast para superadmin
    app.add_handler(CommandHandler("broadcast_activos", cmd_broadcast_activos))
    app.add_handler(CommandHandler("broadcast_todos",   cmd_broadcast_todos))

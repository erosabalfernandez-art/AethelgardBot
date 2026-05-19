"""
broadcast.py — Sistema de notificaciones push con control de tráfico.

Funciones públicas:
  broadcast_activos(bot, mensaje, parse_mode, ventana)
      -> envia solo a jugadores activos en los ultimos N segundos (por defecto 10 min)
      -> rate-limit: 20 mensajes/segundo
      -> ejecucion asincrona (no bloquea el bot)

  broadcast_global(bot, mensaje, reply_markup, parse_mode)
      -> envia a TODOS los jugadores (sin filtro de actividad)
      -> mismo rate-limit y ejecucion asincrona
      -> backward-compatible con jefes.py, automatizaciones.py, guerra_facciones.py

  push_a_jugador(bot, user_id, mensaje, reply_markup)
      -> envia a un jugador especifico y guarda en su bandeja

Comandos de superadmin:
  /broadcast_activos <mensaje>  -- envia a jugadores activos (ultimos 10 min)
  /broadcast_todos   <mensaje>  -- envia a todos los jugadores registrados
  /comunicar                    -- abre el wizard interactivo de comunicacion
"""
import asyncio
import html as _html

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, CommandHandler, ConversationHandler,
    MessageHandler, CallbackQueryHandler, TypeHandler, filters
)

import db_helper
import superadmin as sa

# -- Constantes ---------------------------------------------------------------
_MSG_POR_SEGUNDO = 20
_DELAY           = 1.0 / _MSG_POR_SEGUNDO
_VENTANA_ACTIVOS = 600  # 10 minutos

# ConversationHandler states
_BC_ELIGIENDO   = 0   # seleccionando destino
_BC_ESCRIBIENDO = 1   # escribiendo mensaje
_BC_VISTA_PREV  = 2   # viendo preview / confirmando


def _e(s) -> str:
    return _html.escape(str(s) if s is not None else "")


# -- Tracker de actividad (TypeHandler en grupo -1) ---------------------------
async def _registrar_actividad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user and not user.is_bot:
        try:
            db_helper.registrar_actividad(user.id)
        except Exception:
            pass


# -- Tarea interna de envio masivo ---------------------------------------------
async def _tarea_envio(bot, jugadores: list, mensaje: str,
                       parse_mode: str, reply_markup=None) -> tuple:
    enviados = 0
    fallidos = 0
    for jug in jugadores:
        uid = jug["user_id"] if isinstance(jug, dict) else jug
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


# -- API publica ---------------------------------------------------------------
async def broadcast_activos(
    bot,
    mensaje: str,
    parse_mode: str = "HTML",
    ventana: int = _VENTANA_ACTIVOS,
    reply_markup=None,
) -> asyncio.Task:
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


# -- Teclado del wizard -------------------------------------------------------
def _kb_elegir_destino() -> InlineKeyboardMarkup:
    try:
        n_todos   = len(db_helper.obtener_todos_jugadores())
        n_activos = len(db_helper.obtener_jugadores_activos(_VENTANA_ACTIVOS))
    except Exception:
        n_todos = n_activos = 0
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🟢 Solo ACTIVOS ({n_activos})",        callback_data="wbc_dest_activos")],
        [InlineKeyboardButton(f"📢 TODOS los jugadores ({n_todos})",   callback_data="wbc_dest_todos")],
        [InlineKeyboardButton("⚔️ Faccion — Alianza",                  callback_data="wbc_dest_fac_Alianza")],
        [InlineKeyboardButton("🏛️ Faccion — Imperio",                  callback_data="wbc_dest_fac_Imperio")],
        [InlineKeyboardButton("🗡️ Faccion — Rebeldes",                 callback_data="wbc_dest_fac_Rebeldes")],
        [InlineKeyboardButton("❌ Cancelar",                            callback_data="wbc_cancelar")],
    ])


def _kb_cancelar() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Cancelar envio", callback_data="wbc_cancelar")]
    ])


def _kb_confirmar(modo: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Enviar ahora",        callback_data="wbc_confirmar")],
        [InlineKeyboardButton("✏️ Reescribir",          callback_data=f"wbc_reescribir|{modo}")],
        [InlineKeyboardButton("❌ Cancelar",             callback_data="wbc_cancelar")],
    ])


def _label_destino(modo: str) -> str:
    try:
        n_todos   = len(db_helper.obtener_todos_jugadores())
        n_activos = len(db_helper.obtener_jugadores_activos(_VENTANA_ACTIVOS))
    except Exception:
        n_todos = n_activos = 0
    if modo == "activos":
        return f"🟢 jugadores activos ({n_activos})"
    if modo == "todos":
        return f"📢 TODOS ({n_todos})"
    if modo.startswith("fac_"):
        f = modo.replace("fac_", "")
        return f"⚔️ Faccion {f}"
    return modo


# -- Wizard: /comunicar -------------------------------------------------------
async def cmd_comunicar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Abre el wizard interactivo de comunicacion masiva."""
    if not sa.verificar_superadmin(update.effective_user.id):
        if not sa.verificar_nivel(update.effective_user.id, 1):
            await update.effective_message.reply_text("❌ Solo admins pueden usar este comando.")
            return ConversationHandler.END
    try:
        n_todos   = len(db_helper.obtener_todos_jugadores())
        n_activos = len(db_helper.obtener_jugadores_activos(_VENTANA_ACTIVOS))
    except Exception:
        n_todos = n_activos = 0
    await update.effective_message.reply_text(
        "📢 <b>WIZARD DE COMUNICACION MASIVA</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👥 Registrados: <b>{n_todos}</b>   🟢 Activos: <b>{n_activos}</b>\n\n"
        "<b>Paso 1 de 3 — ¿A quienes envias?</b>\n"
        "Selecciona el grupo destinatario:\n\n"
        "💡 Despues escogeras el mensaje y verasas una <b>vista previa</b> antes de enviar.",
        parse_mode="HTML",
        reply_markup=_kb_elegir_destino(),
    )
    return _BC_ELIGIENDO


async def cb_wbc_destino(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Paso 1: usuario eligio el destino."""
    query = update.callback_query
    await query.answer()
    data = query.data
    if data == "wbc_cancelar":
        context.user_data.pop("wbc_modo", None)
        context.user_data.pop("wbc_preview", None)
        await query.edit_message_text("❌ <b>Envio cancelado.</b>", parse_mode="HTML")
        return ConversationHandler.END
    modo_map = {
        "wbc_dest_activos":      "activos",
        "wbc_dest_todos":        "todos",
        "wbc_dest_fac_Alianza":  "fac_Alianza",
        "wbc_dest_fac_Imperio":  "fac_Imperio",
        "wbc_dest_fac_Rebeldes": "fac_Rebeldes",
    }
    modo = modo_map.get(data)
    if not modo:
        return _BC_ELIGIENDO
    context.user_data["wbc_modo"] = modo
    label = _label_destino(modo)
    await query.edit_message_text(
        f"📢 <b>Destino seleccionado:</b> {label}\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        "<b>Paso 2 de 3 — Escribe tu mensaje</b>\n\n"
        "✏️ Escribe ahora el texto (en este mismo chat):\n\n"
        "📝 <b>Ejemplos de formato HTML:</b>\n"
        "  <code>&lt;b&gt;negrita&lt;/b&gt;</code>\n"
        "  <code>&lt;i&gt;cursiva&lt;/i&gt;</code>\n"
        "  <code>&lt;code&gt;texto codigo&lt;/code&gt;</code>\n"
        "  Emojis directos: ⚔️🐉💎✅❌🎉\n\n"
        "Ejemplo de mensaje:\n"
        "<code>⚔️ &lt;b&gt;¡Evento especial!&lt;/b&gt;\n"
        "Esta noche a las 20:00 habrá doble XP.\n"
        "¡No te lo pierdas!&lt;i&gt; — El equipo de Aethelgard&lt;/i&gt;</code>\n\n"
        "⚠️ Antes de enviar veras una vista previa para confirmar.",
        parse_mode="HTML",
        reply_markup=_kb_cancelar(),
    )
    return _BC_ESCRIBIENDO


async def mh_wbc_texto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Paso 2: usuario escribio el mensaje. Mostramos vista previa."""
    modo = context.user_data.get("wbc_modo")
    if not modo:
        return ConversationHandler.END
    texto_msg = update.message.text or ""
    if not texto_msg.strip():
        await update.message.reply_text(
            "⚠️ El mensaje no puede estar vacio. Escribe algo o pulsa Cancelar.",
            reply_markup=_kb_cancelar()
        )
        return _BC_ESCRIBIENDO
    context.user_data["wbc_preview"] = texto_msg
    label = _label_destino(modo)
    preview = texto_msg[:600] + ("..." if len(texto_msg) > 600 else "")
    await update.message.reply_text(
        f"👁️ <b>PASO 3 — VISTA PREVIA</b>\n"
        f"Destinatarios: {label}\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"{preview}\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        "¿Enviar este mensaje exactamente asi?",
        parse_mode="HTML",
        reply_markup=_kb_confirmar(modo),
    )
    return _BC_VISTA_PREV


async def cb_wbc_confirmar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Paso 3: usuario confirma, reescribe o cancela."""
    query = update.callback_query
    await query.answer()
    data = query.data
    if data == "wbc_cancelar":
        context.user_data.pop("wbc_modo", None)
        context.user_data.pop("wbc_preview", None)
        await query.edit_message_text("❌ <b>Envio cancelado.</b> No se envio ningun mensaje.", parse_mode="HTML")
        return ConversationHandler.END
    if data.startswith("wbc_reescribir|"):
        modo = data.split("|", 1)[1]
        context.user_data["wbc_modo"] = modo
        context.user_data.pop("wbc_preview", None)
        label = _label_destino(modo)
        await query.edit_message_text(
            f"✏️ <b>Reescribe el mensaje para: {label}</b>\n\n"
            "Escribe el nuevo texto en este chat (texto normal):\n"
            "Puedes usar HTML: <b>negrita</b>, <i>cursiva</i>, <code>codigo</code>",
            parse_mode="HTML",
            reply_markup=_kb_cancelar(),
        )
        return _BC_ESCRIBIENDO
    if data == "wbc_confirmar":
        texto_msg = context.user_data.pop("wbc_preview", None)
        modo      = context.user_data.pop("wbc_modo", None)
        if not texto_msg or not modo:
            await query.edit_message_text("❌ Error: no hay mensaje pendiente. Reinicia con /comunicar.")
            return ConversationHandler.END
        if modo == "activos":
            dest   = db_helper.obtener_jugadores_activos(_VENTANA_ACTIVOS)
            label  = f"jugadores activos ({len(dest)})"
        elif modo == "todos":
            dest   = db_helper.obtener_todos_jugadores()
            label  = f"todos los jugadores ({len(dest)})"
        elif modo.startswith("fac_"):
            faccion = modo.replace("fac_", "")
            try:
                todos = db_helper.obtener_todos_jugadores()
                dest  = [j for j in todos if j.get("faccion") == faccion]
            except Exception:
                dest = []
            label = f"faccion {faccion} ({len(dest)})"
        else:
            dest  = db_helper.obtener_todos_jugadores()
            label = f"todos ({len(dest)})"
        n = len(dest)
        seg_est = max(1, n // _MSG_POR_SEGUNDO + 1)
        await query.edit_message_text(
            f"⏳ Enviando a <b>{n}</b> {label}...\n"
            f"⏱️ Tiempo estimado: ~{seg_est}s\n"
            "El bot sigue respondiendo durante el envio.",
            parse_mode="HTML",
        )
        task = asyncio.create_task(_tarea_envio(context.bot, dest, texto_msg, "HTML"))
        async def _done(t, q):
            try:
                env, fall = await t
                await q.edit_message_text(
                    f"✅ <b>Envio completado.</b>\n"
                    f"📤 Enviados: <b>{env}</b>   ❌ Fallidos: <b>{fall}</b>",
                    parse_mode="HTML",
                )
            except Exception:
                pass
        asyncio.create_task(_done(task, query))
        return ConversationHandler.END
    return _BC_VISTA_PREV


async def cmd_cancelar_wbc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("wbc_modo", None)
    context.user_data.pop("wbc_preview", None)
    await update.effective_message.reply_text("❌ Envio cancelado.")
    return ConversationHandler.END


# -- Comandos directos de superadmin ------------------------------------------
async def cmd_broadcast_activos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/broadcast_activos <mensaje> — Envia a jugadores activos en los ultimos 10 minutos."""
    if not sa.verificar_superadmin(update.effective_user.id):
        await update.effective_message.reply_text("❌ Solo el superadmin puede usar este comando.")
        return
    if not context.args:
        await update.effective_message.reply_text(
            "ℹ️ <b>Uso:</b> <code>/broadcast_activos &lt;mensaje&gt;</code>\n\n"
            "Envia el mensaje solo a jugadores activos en los ultimos 10 minutos.\n\n"
            "💡 Alternativa mas intuitiva: /comunicar",
            parse_mode="HTML"
        )
        return
    mensaje = " ".join(context.args)
    jugadores = db_helper.obtener_jugadores_activos(_VENTANA_ACTIVOS)
    total = len(jugadores)
    if total == 0:
        await update.effective_message.reply_text("⚠️ No hay jugadores activos en los ultimos 10 minutos.")
        return
    seg_est = max(1, total // _MSG_POR_SEGUNDO + 1)
    aviso = await update.effective_message.reply_text(
        f"📡 Enviando a <b>{total}</b> jugador(es) activo(s)...\n"
        f"⏱️ Tiempo estimado: <b>~{seg_est}s</b>",
        parse_mode="HTML"
    )
    task = await broadcast_activos(context.bot, mensaje)
    async def _fin(t, msg):
        try:
            env, fall = await t
            await msg.edit_text(
                f"✅ Broadcast completado.\n📤 Enviados: <b>{env}</b>  ❌ Fallidos: <b>{fall}</b>",
                parse_mode="HTML"
            )
        except Exception:
            pass
    asyncio.create_task(_fin(task, aviso))


async def cmd_broadcast_todos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/broadcast_todos <mensaje> — Envia a TODOS los jugadores registrados."""
    if not sa.verificar_superadmin(update.effective_user.id):
        await update.effective_message.reply_text("❌ Solo el superadmin puede usar este comando.")
        return
    if not context.args:
        await update.effective_message.reply_text(
            "ℹ️ <b>Uso:</b> <code>/broadcast_todos &lt;mensaje&gt;</code>\n\n"
            "⚠️ Envia a <b>todos</b> los jugadores registrados, esten activos o no.\n\n"
            "💡 Alternativa mas intuitiva: /comunicar",
            parse_mode="HTML"
        )
        return
    mensaje = " ".join(context.args)
    jugadores = db_helper.obtener_todos_jugadores()
    total = len(jugadores)
    seg_est = max(1, total // _MSG_POR_SEGUNDO + 1)
    aviso = await update.effective_message.reply_text(
        f"📡 Enviando a <b>{total}</b> jugador(es)...\n"
        f"⏱️ Tiempo estimado: <b>~{seg_est}s</b>",
        parse_mode="HTML"
    )
    task = await broadcast_global(context.bot, mensaje)
    async def _fin(t, msg):
        try:
            env, fall = await t
            await msg.edit_text(
                f"✅ Broadcast completado.\n📤 Enviados: <b>{env}</b>  ❌ Fallidos: <b>{fall}</b>",
                parse_mode="HTML"
            )
        except Exception:
            pass
    asyncio.create_task(_fin(task, aviso))


# -- Registro de handlers ------------------------------------------------------
def registrar_handlers(app):
    app.add_handler(
        TypeHandler(Update, _registrar_actividad, block=False),
        group=-1
    )
    # Wizard conversacional /comunicar
    texto_no_cmd = filters.TEXT & ~filters.COMMAND
    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("comunicar", cmd_comunicar)],
        states={
            _BC_ELIGIENDO:   [CallbackQueryHandler(cb_wbc_destino,   pattern="^wbc_")],
            _BC_ESCRIBIENDO: [
                MessageHandler(texto_no_cmd, mh_wbc_texto),
                CallbackQueryHandler(cb_wbc_destino, pattern="^wbc_cancelar$"),
            ],
            _BC_VISTA_PREV:  [CallbackQueryHandler(cb_wbc_confirmar, pattern="^wbc_")],
        },
        fallbacks=[
            CommandHandler("cancelar", cmd_cancelar_wbc),
            CommandHandler("cancelar_broadcast", cmd_cancelar_wbc),
        ],
        per_message=False,
        allow_reentry=True,
    ))
    # Comandos directos (compatibilidad)
    app.add_handler(CommandHandler("broadcast_activos", cmd_broadcast_activos))
    app.add_handler(CommandHandler("broadcast_todos",   cmd_broadcast_todos))

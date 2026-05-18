#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# invitaciones.py - Sistema de invitaciones: código de recluta, stamina bonus configurable

import os, sys
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler

_DIR = os.path.dirname(os.path.abspath(__file__))
if _DIR not in sys.path:
    sys.path.insert(0, _DIR)

import db_helper

# ==================== SISTEMA DE RECLUTAS ====================
# Los jugadores pueden invitar a amigos con su código personal.
# Cuando el recluta alcanza el nivel configurado (def. 15), el reclutador
# recibe stamina_max extra. Es la ÚNICA forma de aumentar stamina_max.
#
# Config keys (config_bot):
#   recluta_bonus_stamina   — stamina extra por recluta (def. 5)
#   recluta_nivel_activacion — nivel en que se activa (def. 15, 0 = instantáneo)

# ==================== HOOK (llamado desde db_helper al subir nivel) ====================

def comprobar_recompensa_recluta(user_id: int, nivel_nuevo: int):
    """Llamar cada vez que un jugador sube de nivel. Otorga stamina al reclutador si corresponde."""
    nivel_req = int(db_helper.obtener_config("recluta_nivel_activacion", "15"))
    if nivel_req == 0:
        return  # modo instantáneo: se maneja en procesar_invitacion
    if nivel_nuevo != nivel_req:
        return  # solo actúa exactamente al llegar al nivel configurado
    db_helper.recluta_alcanzo_nivel_configurado(user_id)

# ==================== COMANDOS DE JUGADOR ====================

async def cmd_mi_codigo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra tu código de invitación y estadísticas de reclutamiento."""
    user_id = update.effective_user.id
    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        await update.effective_message.reply_text("❌ Primero debes registrarte con /start.")
        return
    codigo = jug.get("codigo_invitacion", "N/A")
    completados = jug.get("reclutas_completados", 0)
    stamina_max = jug.get("stamina_maxima", 100)
    bonus_cfg = int(db_helper.obtener_config("recluta_bonus_stamina", "5"))
    nivel_cfg = int(db_helper.obtener_config("recluta_nivel_activacion", "15"))
    cond_txt = f"cuando lleguen a nivel *{nivel_cfg}*" if nivel_cfg > 0 else "al unirse instantáneamente"
    await update.effective_message.reply_text(
        f"🔗 <b>Tu código de invitación:</b> <code>{codigo}</code>\n\n"
        f"📊 Reclutas que completaron el requisito: <b>{completados}</b>\n"
        f"💨 Stamina máxima actual: <b>{stamina_max}</b>\n\n"
        f"<b>¿Cómo funciona?</b>\n"
        f"Comparte tu código con amigos. Cuando usen <code>/usar_codigo {codigo}</code> y {cond_txt.replace('*','')}, "
        f"tu stamina máxima sube <b>+{bonus_cfg}</b> por cada uno.\n\n"
        f"<i>Usa /usar_codigo &lt;CODIGO&gt; si tú también tienes un código de alguien.</i>",
        parse_mode="HTML"
    )

async def cmd_usar_codigo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Usa el código de invitación de otro jugador."""
    user_id = update.effective_user.id
    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        await update.effective_message.reply_text("❌ Primero debes registrarte con /start.")
        return
    if jug.get("invitado_por"):
        await update.effective_message.reply_text("❌ Ya tienes un código de invitación registrado. Solo puedes usar uno.")
        return
    if not context.args:
        await update.effective_message.reply_text("Uso: `/usar_codigo <CODIGO>`", parse_mode="Markdown")
        return
    codigo = context.args[0].strip().upper()
    exito = db_helper.procesar_invitacion(user_id, codigo)
    if not exito:
        await update.effective_message.reply_text("❌ Código inválido, ya lo usaste antes, o es el tuyo propio.")
        return
    # Si el nivel de activación es 0 (instantáneo), dar recompensa ya
    nivel_req = int(db_helper.obtener_config("recluta_nivel_activacion", "15"))
    bonus = int(db_helper.obtener_config("recluta_bonus_stamina", "5"))
    msg_extra = ""
    if nivel_req == 0:
        db_helper.recluta_alcanzo_nivel_configurado(user_id)
        msg_extra = f"\n\n✨ El reclutador ya recibió +{bonus} stamina máxima (activación instantánea)."
    else:
        msg_extra = f"\n\n_El reclutador recibirá +{bonus} stamina máxima cuando llegues al nivel {nivel_req}._"
    await update.effective_message.reply_text(
        f"✅ ¡Código registrado correctamente!{msg_extra}",
        parse_mode="Markdown"
    )

# ==================== COMANDOS DE ADMIN ====================

async def cmd_ver_reclutas_config(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not db_helper.verificar_nivel(update.effective_user.id, 1):
        await update.effective_message.reply_text("❌ Sin acceso.")
        return
    bonus  = db_helper.obtener_config("recluta_bonus_stamina", "5")
    nivel  = db_helper.obtener_config("recluta_nivel_activacion", "15")
    stamina_base = db_helper.obtener_config("stamina_base", "100")
    cond_txt = f"nivel *{nivel}*" if int(nivel) > 0 else "*instantáneo* (al usar el código)"
    await update.effective_message.reply_text(
        f"📋 *Configuración del Sistema de Reclutas*\n\n"
        f"💨 Stamina extra por recluta: *+{bonus}*\n"
        f"🎯 Se activa en: {cond_txt}\n\n"
        f"_Comandos:_\n"
        f"• `/set_recluta_bonus <N>` — stamina por recluta\n"
        f"• `/set_recluta_nivel <N>` — nivel de activación (0 = instantáneo)\n",
        parse_mode="Markdown"
    )

async def cmd_set_recluta_bonus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not db_helper.verificar_nivel(update.effective_user.id, 1):
        await update.effective_message.reply_text("❌ Sin acceso.")
        return
    if not context.args:
        await update.effective_message.reply_text("Uso: `/set_recluta_bonus <N>`", parse_mode="Markdown")
        return
    try:
        val = int(context.args[0])
        if val < 0:
            raise ValueError
    except ValueError:
        await update.effective_message.reply_text("❌ Debe ser entero ≥ 0.")
        return
    db_helper.establecer_config("recluta_bonus_stamina", str(val))
    await update.effective_message.reply_text(
        f"✅ Los reclutas ahora dan *+{val} stamina* máxima al reclutador.",
        parse_mode="Markdown"
    )

async def cmd_set_recluta_nivel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not db_helper.verificar_nivel(update.effective_user.id, 1):
        await update.effective_message.reply_text("❌ Sin acceso.")
        return
    if not context.args:
        await update.effective_message.reply_text("Uso: `/set_recluta_nivel <N>` (0 = instantáneo)", parse_mode="Markdown")
        return
    try:
        val = int(context.args[0])
        if val < 0:
            raise ValueError
    except ValueError:
        await update.effective_message.reply_text("❌ Debe ser entero ≥ 0 (0 = instantáneo).")
        return
    db_helper.establecer_config("recluta_nivel_activacion", str(val))
    if val == 0:
        desc = "La recompensa se dará *instantáneamente* al usar el código."
    else:
        desc = f"La recompensa se dará cuando el recluta llegue al *nivel {val}*."
    await update.effective_message.reply_text(f"✅ {desc}", parse_mode="Markdown")

# ==================== REGISTRO ====================

def registrar_handlers(app):
    app.add_handler(CommandHandler("mi_codigo",          cmd_mi_codigo))
    app.add_handler(CommandHandler("usar_codigo",        cmd_usar_codigo))
    app.add_handler(CommandHandler("ver_reclutas_config",cmd_ver_reclutas_config))
    app.add_handler(CommandHandler("set_recluta_bonus",  cmd_set_recluta_bonus))
    app.add_handler(CommandHandler("set_recluta_nivel",  cmd_set_recluta_nivel))

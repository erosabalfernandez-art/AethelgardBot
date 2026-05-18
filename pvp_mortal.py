"""
pvp_mortal.py — PvP mortal genérico para zonas amarilla, roja y negra.

Botones (callbacks):
  pvpm_local_{color}           → Emboscada local: busca rivales en todas las zonas del mismo color
  pvpm_multi_{color}           → Caza multizonal: busca en zonas del mismo color y facción
  pvpm_atk_{color}_{uid}       → Atacar a un rival específico
  pvpm_ok_{color}_{atk}_{def}  → Rival acepta el combate
  pvpm_huir_{color}_{atk}_{def}→ Rival huye (pierde % de oro)
  pvpm_volver                  → Volver
"""

import asyncio
import random
import sqlite3
import os
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler

import db_helper
import economia

# ─── Estado de sesión PvP en memoria ─────────────────────────────────────────
# Sustituye context.application.user_data (mappingproxy, solo lectura en PTB v20)
_PVPM_UDATA: dict = {}   # {user_id: {"pvp_multi_usos": int, "pvp_multi_ultimo": str, "pvpm_pendiente": dict}}

DB_PATH = "aethelgard.db"

# ── Constantes ────────────────────────────────────────────────────────────────

ZONAS_PVP = {"amarilla", "roja", "negra"}   # azul excluida
EMOJI_COLOR  = {"amarilla": "🟨", "roja": "🟥", "negra": "⬛"}
NOMBRE_COLOR = {"amarilla": "Zona Amarilla", "roja": "Zona Roja", "negra": "Zona Negra"}
PCT_ORO_HUIDA = {"amarilla": 0.10, "roja": 0.50, "negra": 1.00}
PENALIZACION_TXT = {
    "amarilla": "10% de tu oro + 1 objeto",
    "roja":     "50% de tu oro + 5 objetos",
    "negra":    "TODO tu oro y objetos",
}

MULTI_BASE_CD    = 120   # 2 minutos de cooldown base
MULTI_INCR_CD    = 20    # +20s por cada uso
MULTI_RESET_MIN  = 10    # minutos de inactividad para resetear el contador de usos


def _get_combate_tipo(color: str) -> str:
    from combate import COMBATE_PVP_AMARILLA, COMBATE_PVP_ROJA, COMBATE_PVP_NEGRA
    return {"amarilla": COMBATE_PVP_AMARILLA, "roja": COMBATE_PVP_ROJA,
            "negra": COMBATE_PVP_NEGRA}.get(color, COMBATE_PVP_NEGRA)


def _he(text: str) -> str:
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _get_color_jugador(user_id: int) -> str:
    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        return ""
    zona = jug.get("zona_actual", "")
    try:
        from datos_zona import ZONAS as _ZG
        zid = jug.get("zona_actual_id")
        color = next((z.get("color", "") for z in _ZG if z.get("id") == zid), "")
        return color
    except Exception:
        return ""


def _zonas_ids_color(color: str) -> list:
    try:
        from datos_zona import ZONAS as _ZG
        return [z["id"] for z in _ZG if z.get("color") == color]
    except Exception:
        return []


def _zonas_ids_color_faccion(color: str, faccion: str, faccion_id: int) -> list:
    try:
        from datos_zona import ZONAS as _ZG
        ids = [z["id"] for z in _ZG
               if z.get("color") == color and
               (z.get("faccion") == faccion or z.get("faccion_id") == faccion_id)]
        return ids if ids else _zonas_ids_color(color)
    except Exception:
        return _zonas_ids_color(color)


def _buscar_rivales(zona_ids: list, user_id: int) -> list:
    if not zona_ids:
        return []
    try:
        import sistema_paz as _sp
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        ph = ",".join("?" * len(zona_ids))
        c.execute(
            f"SELECT user_id, nombre_personaje, nivel, faccion, zona_actual "
            f"FROM jugadores WHERE zona_actual_id IN ({ph}) AND user_id != ?",
            zona_ids + [user_id]
        )
        rows = c.fetchall()
        conn.close()
        return [(uid, n or "?", lvl or 1, fac or "?", zona or "?")
                for uid, n, lvl, fac, zona in rows
                if not _sp.esta_en_paz(uid)]
    except Exception:
        return []


# ── Comandos de texto (para el teclado rápido) ───────────────────────────────

async def cmd_pvp_buscar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Emboscada local desde teclado. Detecta el color del jugador y muestra rivales."""
    user_id = update.effective_user.id
    if db_helper.esta_marcado(user_id):
        await update.effective_message.reply_text("❌ Estás marcado. No puedes iniciar PvP.")
        return
    try:
        import sistema_paz as _sp
        if _sp.esta_en_paz(user_id):
            await update.effective_message.reply_text("🧘 Estás en estado de paz. No puedes atacar.")
            return
    except Exception:
        pass
    color = _get_color_jugador(user_id)
    if color not in ZONAS_PVP:
        await update.effective_message.reply_text(
            "⚔️ Solo puedes iniciar PvP mortal en zonas amarilla, roja o negra.")
        return
    zona_ids = _zonas_ids_color(color)
    rivales = _buscar_rivales(zona_ids, user_id)
    emoji = EMOJI_COLOR[color]
    nombre = NOMBRE_COLOR[color]
    if not rivales:
        await update.effective_message.reply_text(
            f"{emoji} *Emboscada — {nombre}*\n\nNo hay jugadores atacables ahora mismo.",
            parse_mode="Markdown"
        )
        return
    texto = f"⚔️ *Emboscada — {nombre}*\n\nElige a quién atacar:\n"
    kb = [[InlineKeyboardButton(f"⚔️ {n} (Nv.{lvl} — {zona})",
                                callback_data=f"pvpm_atk_{color}_{uid}")]
          for uid, n, lvl, fac, zona in rivales[:10]]
    kb.append([InlineKeyboardButton("❌ Cerrar", callback_data="pvpm_volver")])
    await update.effective_message.reply_text(texto, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")


async def cmd_pvp_multi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Caza multizonal desde teclado. Misma lógica que el botón inline."""
    user_id = update.effective_user.id
    if db_helper.esta_marcado(user_id):
        await update.effective_message.reply_text("❌ Estás marcado. No puedes iniciar PvP.")
        return
    try:
        import sistema_paz as _sp
        if _sp.esta_en_paz(user_id):
            await update.effective_message.reply_text("🧘 Estás en estado de paz. No puedes atacar.")
            return
    except Exception:
        pass
    color = _get_color_jugador(user_id)
    if color not in ZONAS_PVP:
        await update.effective_message.reply_text(
            "🌐 Solo puedes hacer caza multizonal en zonas amarilla, roja o negra.")
        return
    # Reutilizar lógica de cooldown: disparar el callback inline equivalente
    # enviando un mensaje con el botón pvpm_multi_{color} que el jugador presiona
    emoji = EMOJI_COLOR[color]
    nombre = NOMBRE_COLOR[color]
    kb = [[InlineKeyboardButton(f"🌐 Iniciar caza en {nombre}", callback_data=f"pvpm_multi_{color}")]]
    await update.effective_message.reply_text(
        f"🌐 *Caza Multizonal* — {emoji} {nombre}\n\nBuscará rivales en todas las zonas de tu color y facción.",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown"
    )


# ── Callbacks de Emboscada local ─────────────────────────────────────────────

async def pvpm_local_buscar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """pvpm_local_{color}"""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    color = query.data.replace("pvpm_local_", "", 1)
    if color not in ZONAS_PVP:
        return
    if db_helper.esta_marcado(user_id):
        await query.edit_message_text("❌ Estás marcado. No puedes iniciar PvP.")
        return
    try:
        import sistema_paz as _sp
        if _sp.esta_en_paz(user_id):
            await query.edit_message_text("🧘 Estás en estado de paz. No puedes atacar.")
            return
    except Exception:
        pass
    zona_ids = _zonas_ids_color(color)
    rivales = _buscar_rivales(zona_ids, user_id)
    emoji, nombre = EMOJI_COLOR[color], NOMBRE_COLOR[color]
    if not rivales:
        await query.edit_message_text(
            f"{emoji} *Emboscada — {nombre}*\n\n"
            "No hay jugadores atacables ahora mismo. Inténtalo más tarde.\n"
            "• Los jugadores meditando (🧘) no pueden ser atacados.",
            parse_mode="Markdown"
        )
        return
    texto = f"⚔️ *Emboscada — {nombre}*\n\nElige a quién atacar:\n"
    kb = [[InlineKeyboardButton(f"⚔️ {n} (Nv.{lvl} — {zona})",
                                callback_data=f"pvpm_atk_{color}_{uid}")]
          for uid, n, lvl, fac, zona in rivales[:10]]
    kb.append([InlineKeyboardButton("🔙 Volver", callback_data="pvpm_volver")])
    try:
        await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
    except Exception:
        await query.message.reply_text(texto, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")


# ── Callbacks de Caza multizonal ─────────────────────────────────────────────

async def pvpm_multi_buscar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """pvpm_multi_{color} — cooldown progresivo con reset tras inactividad."""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    color = query.data.replace("pvpm_multi_", "", 1)
    if color not in ZONAS_PVP:
        return
    if db_helper.esta_marcado(user_id):
        await query.edit_message_text("❌ Estás marcado. No puedes iniciar PvP.")
        return
    try:
        import sistema_paz as _sp
        if _sp.esta_en_paz(user_id):
            await query.edit_message_text("🧘 Estás en estado de paz. No puedes atacar.")
            return
    except Exception:
        pass

    # ── Cooldown progresivo ─────────────────────────────────────────────────
    udata = _PVPM_UDATA.setdefault(user_id, {})
    usos = udata.get("pvp_multi_usos", 0)
    ultimo = udata.get("pvp_multi_ultimo")
    if ultimo:
        transcurrido = (datetime.now() - datetime.fromisoformat(ultimo)).total_seconds()
        if transcurrido >= MULTI_RESET_MIN * 60:
            # Más de 10 min de inactividad → resetear el contador de usos
            usos = 0
            udata["pvp_multi_usos"] = 0
        else:
            restante = int(MULTI_BASE_CD + usos * MULTI_INCR_CD - transcurrido)
            if restante > 0:
                m, s = divmod(restante, 60)
                t = f"{m}m {s}s" if m else f"{s}s"
                await query.edit_message_text(
                    f"⏳ *Caza multizonal en recarga*\n\n"
                    f"Podrás usarla en: `{t}`\n"
                    f"_(El cooldown sube {MULTI_INCR_CD}s por uso y se reinicia "
                    f"tras {MULTI_RESET_MIN} min de inactividad)_",
                    parse_mode="Markdown"
                )
                return

    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        await query.edit_message_text("❌ Error al obtener tus datos.")
        return
    faccion    = jug.get("faccion", "")
    faccion_id = jug.get("faccion_id") or 0
    zona_ids   = _zonas_ids_color_faccion(color, faccion, faccion_id)
    rivales    = _buscar_rivales(zona_ids, user_id)

    if not rivales:
        await query.edit_message_text(
            f"🌐 *Caza Multizonal — {NOMBRE_COLOR[color]}*\n\n"
            f"No hay rivales en las zonas {color} de tu facción ahora mismo.",
            parse_mode="Markdown"
        )
        return

    # Registrar uso y calcular próximo cooldown
    nuevo_usos = usos + 1
    udata["pvp_multi_usos"]   = nuevo_usos
    udata["pvp_multi_ultimo"] = datetime.now().isoformat()
    prox = MULTI_BASE_CD + nuevo_usos * MULTI_INCR_CD
    m2, s2 = divmod(prox, 60)
    prox_txt = f"{m2}m {s2}s" if m2 else f"{s2}s"

    emoji, nombre = EMOJI_COLOR[color], NOMBRE_COLOR[color]
    texto = (
        f"🌐 *Caza Multizonal — {nombre} ({faccion})*\n\n"
        f"Rivales encontrados en zonas de tu facción. Elige a quién atacar:\n"
        f"_(Próximo cooldown: {prox_txt})_\n"
    )
    kb = [[InlineKeyboardButton(f"⚔️ {n} (Nv.{lvl} — {zona})",
                                callback_data=f"pvpm_atk_{color}_{uid}")]
          for uid, n, lvl, fac, zona in rivales[:10]]
    kb.append([InlineKeyboardButton("🔙 Volver", callback_data="pvpm_volver")])
    try:
        await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
    except Exception:
        await query.message.reply_text(texto, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")


# ── Atacar rival ──────────────────────────────────────────────────────────────

async def pvpm_atacar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """pvpm_atk_{color}_{uid}"""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    # pvpm_atk_negra_123  →  split("_") = ["pvpm","atk","negra","123"]
    parts = query.data.split("_")
    try:
        oponente_id = int(parts[-1])
        color       = parts[-2]   # amarilla/roja/negra — sin guiones bajos internos
    except (ValueError, IndexError):
        await query.answer("❌ Error en datos del ataque.", show_alert=True)
        return

    if user_id == oponente_id:
        await query.edit_message_text("No puedes atacarte a ti mismo.")
        return
    try:
        import sistema_paz as _sp
        if _sp.esta_en_paz(user_id):
            await query.edit_message_text("🧘 Desactiva tu paz con /desactivar_paz para atacar.")
            return
        if _sp.esta_en_paz(oponente_id):
            await query.edit_message_text("🛡️ Ese jugador está meditando. No puedes atacarlo ahora.")
            return
    except Exception:
        pass
    oponente = db_helper.obtener_jugador(oponente_id)
    if not oponente:
        await query.edit_message_text("❌ El jugador ya no está disponible.")
        return
    jug = db_helper.obtener_jugador(user_id)
    atk_nombre = jug.get("nombre_personaje", "?") if jug else "?"
    def_nombre  = oponente.get("nombre_personaje", "?")
    emoji  = EMOJI_COLOR.get(color, "⚔️")
    nombre = NOMBRE_COLOR.get(color, "Zona")
    pen_txt = PENALIZACION_TXT.get(color, "penalización")

    kb_rival = [[
        InlineKeyboardButton("⚔️ Pelear",    callback_data=f"pvpm_ok_{color}_{user_id}_{oponente_id}"),
        InlineKeyboardButton("🏃 Huir",      callback_data=f"pvpm_huir_{color}_{user_id}_{oponente_id}"),
    ]]
    try:
        await context.bot.send_message(
            chat_id=oponente_id,
            text=f"{emoji} <b>¡Emboscada en {nombre}!</b>\n\n"
                 f"<b>{_he(atk_nombre)}</b> te está atacando. ¡30 segundos para responder!\n\n"
                 f"⚠️ Si huyes perderás: {pen_txt}",
            reply_markup=InlineKeyboardMarkup(kb_rival),
            parse_mode="HTML"
        )
    except Exception:
        await query.edit_message_text("❌ No se pudo contactar al rival. Puede estar desconectado.")
        return

    _PVPM_UDATA.setdefault(user_id, {})["pvpm_pendiente"] = {
        "oponente_id": oponente_id, "color": color,
        "timestamp": datetime.now().isoformat()
    }
    try:
        await query.edit_message_text(
            f"⚔️ Desafío enviado a <b>{_he(def_nombre)}</b>.\n"
            f"Esperando respuesta (30 segundos)...",
            parse_mode="HTML"
        )
    except Exception:
        pass
    await asyncio.sleep(30)
    datos = _PVPM_UDATA.get(user_id, {}).get("pvpm_pendiente")
    if datos and datos.get("oponente_id") == oponente_id:
        _PVPM_UDATA.get(user_id, {}).pop("pvpm_pendiente", None)
        # Sin respuesta = penalizaciones completas de muerte (igual que perder el combate)
        try:
            from combate import _aplicar_perdidas_y_transferir
            tipo = _get_combate_tipo(color)
            _aplicar_perdidas_y_transferir(oponente_id, user_id, tipo)
        except Exception:
            # Fallback: solo transferir el oro si falla combate
            try:
                pct = PCT_ORO_HUIDA.get(color, 0.10)
                saldos = economia.obtener_saldos(oponente_id)
                pen = max(1, int(saldos.get("oro", 0) * pct))
                economia.modificar_saldo(oponente_id, "oro", -pen, f"sin respuesta zona {color}")
                economia.modificar_saldo(user_id,     "oro",  pen, f"cobro sin respuesta zona {color}")
            except Exception:
                pass
        try:
            await context.bot.send_message(
                user_id,
                f"⏰ {_he(def_nombre)} no respondió. Se aplican las penalizaciones completas de derrota.\n"
                f"Recibes el botín correspondiente a la zona {color}.",
            )
        except Exception:
            pass
        try:
            await context.bot.send_message(
                oponente_id,
                f"⏰ No respondiste al desafío de {_he(atk_nombre)}.\n"
                f"Se te han aplicado las penalizaciones de derrota en zona {color}.",
            )
        except Exception:
            pass


# ── Aceptar combate ───────────────────────────────────────────────────────────

async def pvpm_aceptar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """pvpm_ok_{color}_{atk}_{def}"""
    query = update.callback_query
    await query.answer()
    # pvpm_ok_negra_111_222 → ["pvpm","ok","negra","111","222"]
    parts = query.data.split("_")
    try:
        defensor_id = int(parts[-1])
        atacante_id = int(parts[-2])
        color       = parts[-3]
    except (ValueError, IndexError):
        await query.answer("❌ Error en los datos del combate.", show_alert=True)
        return
    if update.effective_user.id != defensor_id:
        await query.edit_message_text("Este desafío no es para ti.")
        return
    _PVPM_UDATA.get(atacante_id, {}).pop("pvpm_pendiente", None)
    atacante = db_helper.obtener_jugador(atacante_id)
    if not atacante:
        await query.edit_message_text("❌ El atacante ya no está disponible.")
        return
    try:
        await context.bot.send_message(atacante_id, "⚔️ ¡Tu rival aceptó el combate!")
    except Exception:
        pass
    await query.edit_message_text("⚔️ ¡Combate iniciado! Preparando arena...")
    from combate import iniciar_combate
    tipo = _get_combate_tipo(color)
    await iniciar_combate(update, context, atacante_id, defensor_id, tipo, enemigo=None, datos_extra={})


# ── Huir del combate ──────────────────────────────────────────────────────────

async def pvpm_huir(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """pvpm_huir_{color}_{atk}_{def}
    La huida tiene solo un 10% de efectividad:
    - 10% → escapas sin penalización
    - 90% → te atrapan y el combate se inicia igualmente
    """
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_")
    try:
        defensor_id = int(parts[-1])
        atacante_id = int(parts[-2])
        color       = parts[-3]
    except (ValueError, IndexError):
        await query.answer("❌ Error en los datos del combate.", show_alert=True)
        return
    if update.effective_user.id != defensor_id:
        await query.edit_message_text("Esta acción no es para ti.")
        return
    _PVPM_UDATA.get(atacante_id, {}).pop("pvpm_pendiente", None)
    def_jug    = db_helper.obtener_jugador(defensor_id)
    def_nombre = def_jug.get("nombre_personaje", "?") if def_jug else "?"

    # ── Tirada de huida: 10% éxito ──────────────────────────────────────────
    if random.random() < 0.10:
        # ¡Escapó!
        try:
            await context.bot.send_message(
                atacante_id,
                f"💨 *{_he(def_nombre)}* consiguió escapar. El combate se cancela.",
                parse_mode="Markdown"
            )
        except Exception:
            pass
        try:
            await query.edit_message_text(
                "💨 *¡Escapaste!* Conseguiste huir del combate sin penalización.\n"
                "_(Solo hay un 10% de probabilidad de lograrlo)_",
                parse_mode="Markdown"
            )
        except Exception:
            pass
        return

    # ── No escapó (90%): el combate se inicia igualmente ────────────────────
    try:
        await context.bot.send_message(
            atacante_id,
            f"⚔️ *{_he(def_nombre)}* intentó huir pero ¡lo atrapaste! ¡Combate iniciado!",
            parse_mode="Markdown"
        )
    except Exception:
        pass
    try:
        await query.edit_message_text(
            "🏃 Intentaste huir... pero te han atrapado. ¡El combate comienza igualmente!\n"
            "_(Solo hay un 10% de probabilidad de escapar)_",
            parse_mode="Markdown"
        )
    except Exception:
        pass
    from combate import iniciar_combate
    tipo = _get_combate_tipo(color)
    await iniciar_combate(update, context, atacante_id, defensor_id, tipo, enemigo=None, datos_extra={})


async def pvpm_volver(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        await query.edit_message_text("Usa /investigar para volver al menú de investigación.")
    except Exception:
        pass


# ── Registro de handlers ──────────────────────────────────────────────────────

def registrar_handlers(app):
    app.add_handler(CommandHandler("pvp_buscar", cmd_pvp_buscar))
    app.add_handler(CommandHandler("pvp_multi",  cmd_pvp_multi))
    app.add_handler(CallbackQueryHandler(pvpm_local_buscar, pattern="^pvpm_local_"))
    app.add_handler(CallbackQueryHandler(pvpm_multi_buscar, pattern="^pvpm_multi_"))
    app.add_handler(CallbackQueryHandler(pvpm_atacar,       pattern="^pvpm_atk_"))
    app.add_handler(CallbackQueryHandler(pvpm_aceptar,      pattern="^pvpm_ok_"))
    app.add_handler(CallbackQueryHandler(pvpm_huir,         pattern="^pvpm_huir_"))
    app.add_handler(CallbackQueryHandler(pvpm_volver,       pattern="^pvpm_volver$"))

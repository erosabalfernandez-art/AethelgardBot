#!/usr/bin/env python3
# restricciones_combate.py — Control de restricciones globales de combate
#
# EXCLUSIVO SUPERADMIN. Comandos disponibles:
#   /restricciones_combate           — Panel interactivo con botones toggle
#   /rc_duelos                       — Toggle: duelos PvP
#   /rc_combate                      — Toggle: combate PvE/mazmorras/jefes
#   /rc_habilidades                  — Toggle maestro: habilidades en TODOS los modos
#   /rc_habilidades_pve              — Toggle: habilidades solo en PvE
#   /rc_habilidades_pvp              — Toggle: habilidades solo en PvP/duelos
#   /rc_habilidades_caza             — Toggle: habilidades solo en Sistema de Caza
#   /rc_habilidades_mazmorra         — Toggle: habilidades solo en Mazmorras
#   /rc_criticos                     — Toggle: golpes críticos
#   /rc_huir                         — Toggle: opción de huir
#
# Los combates activos NO se ven afectados; las restricciones solo
# aplican a combates que empiecen DESPUÉS del cambio.
# El ataque normal NUNCA puede ser restringido.

import json
import os
import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler

import superadmin as sa

logger = logging.getLogger(__name__)

_RUTA_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "restricciones_combate.json")

# ── Estado en memoria (True = PERMITIDO) ─────────────────────────────────────
_RESTRICCIONES: dict = {
    "duelos":               True,
    "combate":              True,
    "habilidades_pve":      True,
    "habilidades_pvp":      True,
    "habilidades_caza":     True,
    "habilidades_mazmorra": True,
    "criticos":             True,
    "huir":                 True,
}

_NOMBRES = {
    "duelos":               "⚔️ Duelos PvP",
    "combate":              "🐉 Combate general (PvE / mazmorras / jefes)",
    "habilidades_pve":      "✨ Habilidades — PvE",
    "habilidades_pvp":      "✨ Habilidades — PvP / Duelos",
    "habilidades_caza":     "✨ Habilidades — Sistema de Caza",
    "habilidades_mazmorra": "✨ Habilidades — Mazmorras",
    "criticos":             "💥 Golpes críticos",
    "huir":                 "🏃 Opción de huir",
}

_CLAVES_HABILIDADES = ("habilidades_pve", "habilidades_pvp", "habilidades_caza", "habilidades_mazmorra")

# ── Persistencia ──────────────────────────────────────────────────────────────

def _cargar():
    global _RESTRICCIONES
    try:
        if os.path.exists(_RUTA_JSON):
            with open(_RUTA_JSON, "r", encoding="utf-8") as f:
                datos = json.load(f)
            for k in list(_RESTRICCIONES):
                if k in datos:
                    _RESTRICCIONES[k] = bool(datos[k])
            # Migrar clave antigua "habilidades" → las 4 nuevas si estaba guardada
            if "habilidades" in datos and not any(k in datos for k in _CLAVES_HABILIDADES):
                v = bool(datos["habilidades"])
                for k in _CLAVES_HABILIDADES:
                    _RESTRICCIONES[k] = v
    except Exception as e:
        logger.warning(f"[restricciones] No se pudo cargar: {e}")


def _guardar():
    try:
        with open(_RUTA_JSON, "w", encoding="utf-8") as f:
            json.dump(_RESTRICCIONES, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"[restricciones] No se pudo guardar: {e}")


_cargar()

# ── API pública (usada por combate.py) ────────────────────────────────────────

def get_restriccion(clave: str) -> bool:
    """True = la funcionalidad está PERMITIDA."""
    return _RESTRICCIONES.get(clave, True)


def get_snapshot() -> dict:
    """Copia del estado actual. Se embebe en cada combate al iniciarse."""
    return dict(_RESTRICCIONES)

# ── Helpers internos ──────────────────────────────────────────────────────────

def _construir_panel():
    lineas = ["🔒 *Panel de Restricciones de Combate*\n"]
    for clave, nombre in _NOMBRES.items():
        estado = "✅ Permitido" if _RESTRICCIONES[clave] else "🚫 Restringido"
        lineas.append(f"{nombre}: {estado}")
    lineas.append(
        "\n⚠️ _Los combates activos no se ven afectados._\n"
        "_Solo aplica a nuevos combates._"
    )
    texto = "\n".join(lineas)

    botones = []
    for clave, nombre in _NOMBRES.items():
        if _RESTRICCIONES[clave]:
            etiqueta = f"🔒 Restringir {nombre}"
        else:
            etiqueta = f"🔓 Permitir {nombre}"
        botones.append([InlineKeyboardButton(etiqueta, callback_data=f"restcomb_toggle_{clave}")])

    botones.append([
        InlineKeyboardButton("🚫 Restringir TODAS las habilidades", callback_data="restcomb_hab_todo_off"),
        InlineKeyboardButton("✅ Permitir TODAS las habilidades",    callback_data="restcomb_hab_todo_on"),
    ])
    botones.append([
        InlineKeyboardButton("✅ Restaurar todo", callback_data="restcomb_reset_todo"),
        InlineKeyboardButton("❌ Cerrar",          callback_data="restcomb_cerrar"),
    ])
    return texto, InlineKeyboardMarkup(botones)


def _toggle(clave: str) -> tuple[bool, str]:
    """Cambia una restricción y devuelve (nuevo_estado, texto_confirmación)."""
    _RESTRICCIONES[clave] = not _RESTRICCIONES[clave]
    _guardar()
    permitido = _RESTRICCIONES[clave]
    nombre = _NOMBRES.get(clave, clave)
    if permitido:
        msg = f"✅ *{nombre}* → PERMITIDO"
    else:
        msg = f"🚫 *{nombre}* → RESTRINGIDO"
    logger.info(f"[restricciones] Superadmin toggleó '{clave}' → {'PERMITIDO' if permitido else 'RESTRINGIDO'}")
    return permitido, msg

# ── Handler del panel interactivo ─────────────────────────────────────────────

async def cmd_restricciones_combate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not sa._es_superadmin(update.effective_user.id):
        await update.effective_message.reply_text("❌ Comando exclusivo del superadmin.")
        return
    texto, markup = _construir_panel()
    await update.effective_message.reply_text(texto, reply_markup=markup, parse_mode="Markdown")


async def cb_restricciones_combate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not sa._es_superadmin(update.effective_user.id):
        try:
            await query.edit_message_text("❌ Sin permiso.")
        except Exception:
            pass
        return

    data = query.data

    if data == "restcomb_cerrar":
        try:
            await query.edit_message_text("Panel de restricciones cerrado.")
        except Exception:
            pass
        return

    if data == "restcomb_reset_todo":
        for k in list(_RESTRICCIONES):
            _RESTRICCIONES[k] = True
        _guardar()
        logger.info(f"[restricciones] Superadmin {update.effective_user.id}: RESTAURÓ TODO")
        texto, markup = _construir_panel()
        try:
            await query.edit_message_text(texto, reply_markup=markup, parse_mode="Markdown")
        except Exception:
            pass
        return

    if data == "restcomb_hab_todo_off":
        for k in _CLAVES_HABILIDADES:
            _RESTRICCIONES[k] = False
        _guardar()
        logger.info(f"[restricciones] Superadmin {update.effective_user.id}: RESTRINGIÓ TODAS las habilidades")
        texto, markup = _construir_panel()
        try:
            await query.edit_message_text(texto, reply_markup=markup, parse_mode="Markdown")
        except Exception:
            pass
        return

    if data == "restcomb_hab_todo_on":
        for k in _CLAVES_HABILIDADES:
            _RESTRICCIONES[k] = True
        _guardar()
        logger.info(f"[restricciones] Superadmin {update.effective_user.id}: PERMITIÓ TODAS las habilidades")
        texto, markup = _construir_panel()
        try:
            await query.edit_message_text(texto, reply_markup=markup, parse_mode="Markdown")
        except Exception:
            pass
        return

    if data.startswith("restcomb_toggle_"):
        clave = data[len("restcomb_toggle_"):]
        if clave in _RESTRICCIONES:
            _toggle(clave)
        texto, markup = _construir_panel()
        try:
            await query.edit_message_text(texto, reply_markup=markup, parse_mode="Markdown")
        except Exception:
            pass

# ── Comandos toggle individuales ──────────────────────────────────────────────

async def _cmd_toggle_individual(update: Update, clave: str):
    if not sa._es_superadmin(update.effective_user.id):
        await update.effective_message.reply_text("❌ Comando exclusivo del superadmin.")
        return
    _, msg = _toggle(clave)
    await update.effective_message.reply_text(
        msg + "\n\n_Usa /restricciones\\_combate para ver el panel completo._",
        parse_mode="Markdown"
    )

async def cmd_rc_duelos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _cmd_toggle_individual(update, "duelos")

async def cmd_rc_combate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _cmd_toggle_individual(update, "combate")

async def cmd_rc_habilidades(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Toggle maestro: activa o desactiva habilidades en TODOS los modos a la vez."""
    if not sa._es_superadmin(update.effective_user.id):
        await update.effective_message.reply_text("❌ Comando exclusivo del superadmin.")
        return
    alguna_activa = any(_RESTRICCIONES[k] for k in _CLAVES_HABILIDADES)
    nuevo_estado = not alguna_activa
    for k in _CLAVES_HABILIDADES:
        _RESTRICCIONES[k] = nuevo_estado
    _guardar()
    estado_txt = "PERMITIDAS ✅" if nuevo_estado else "RESTRINGIDAS 🚫"
    logger.info(f"[restricciones] Superadmin {update.effective_user.id}: habilidades maestro → {estado_txt}")
    await update.effective_message.reply_text(
        f"✨ *Habilidades (todos los modos)* → {estado_txt}\n\n"
        f"_Usa /restricciones\\_combate para control individual por modo._",
        parse_mode="Markdown"
    )

async def cmd_rc_habilidades_pve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _cmd_toggle_individual(update, "habilidades_pve")

async def cmd_rc_habilidades_pvp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _cmd_toggle_individual(update, "habilidades_pvp")

async def cmd_rc_habilidades_caza(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _cmd_toggle_individual(update, "habilidades_caza")

async def cmd_rc_habilidades_mazmorra(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _cmd_toggle_individual(update, "habilidades_mazmorra")

async def cmd_rc_criticos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _cmd_toggle_individual(update, "criticos")

async def cmd_rc_huir(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _cmd_toggle_individual(update, "huir")

# ── Registro de handlers ──────────────────────────────────────────────────────

def registrar_handlers(app):
    app.add_handler(CommandHandler("restricciones_combate",   cmd_restricciones_combate))
    app.add_handler(CommandHandler("rc_duelos",               cmd_rc_duelos))
    app.add_handler(CommandHandler("rc_combate",              cmd_rc_combate))
    app.add_handler(CommandHandler("rc_habilidades",          cmd_rc_habilidades))
    app.add_handler(CommandHandler("rc_habilidades_pve",      cmd_rc_habilidades_pve))
    app.add_handler(CommandHandler("rc_habilidades_pvp",      cmd_rc_habilidades_pvp))
    app.add_handler(CommandHandler("rc_habilidades_caza",     cmd_rc_habilidades_caza))
    app.add_handler(CommandHandler("rc_habilidades_mazmorra", cmd_rc_habilidades_mazmorra))
    app.add_handler(CommandHandler("rc_criticos",             cmd_rc_criticos))
    app.add_handler(CommandHandler("rc_huir",                 cmd_rc_huir))
    app.add_handler(CallbackQueryHandler(cb_restricciones_combate, pattern=r"^restcomb_"))

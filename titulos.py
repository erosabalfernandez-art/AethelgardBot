#!/usr/bin/env python3
# titulos.py — Sistema de Títulos Equipables
#
# Los jugadores coleccionan títulos de múltiples fuentes:
#   • Logros del sistema de logros (logros.py)
#   • Gloria acumulada en el sistema de progresión
#   • Hitos de nivel en progresion_clase.py
#   • Títulos de clase base al crear el personaje
#
# Comandos:
#   /mis_titulos      — Ver todos mis títulos y elegir cuál equipar
#   /titulo_equipar   — Alias rápido de /mis_titulos
#
# El título activo se muestra en el perfil y en el chat de grupo
# bajo el nombre del personaje.

import json
import sqlite3
from typing import List, Optional
from html import escape as _he

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler

import db_helper

DB_PATH = "aethelgard.db"

# ==================== TÍTULOS PREDETERMINADOS POR CLASE ====================
TITULOS_CLASE = {
    "guerrero":   "el Guerrero",
    "mago":       "el Mago",
    "arquero":    "el Arquero",
    "clerigo":    "el Clérigo",
    "ladron":     "el Ladrón",
    "paladin":    "el Paladín",
    "druida":     "el Druida",
    "berserker":  "el Berserker",
    "nigromante": "el Nigromante",
    "monje":      "el Monje",
}

# Títulos especiales que se pueden ganar en diferentes sistemas
# (clave de reconocimiento → texto visible)
TITULOS_ESPECIALES = {
    # De logros (logros.py recompensa_titulo)
    "Aventurero":              "el Aventurero",
    "Héroe":                   "el Héroe",
    "Campeón":                 "el Campeón",
    "Leyenda":                 "la Leyenda",
    "Inmortal":                "el Inmortal",
    "Renacido":                "el Renacido",
    "Conquistador":            "el Conquistador",
    "Señor de las Sombras":    "el Señor de las Sombras",
    "Duelista":                "el Duelista",
    "Azote":                   "el Azote",
    "Terror":                  "el Terror",
    "Asesino de Dragones":     "el Asesino de Dragones",
    "Azote de Titanes":        "el Azote de Titanes",
    "Maestro Artesano":        "el Maestro Artesano",
    "Recolector Eterno":       "el Recolector Eterno",
    "Erudito":                 "el Erudito",
    "Nómada":                  "el Nómada",
    "Fundador Legendario":     "el Fundador Legendario",
    "Mercader":                "el Mercader",
    "Barón del Oro":           "el Barón del Oro",
    "Intocable":               "el Intocable",
    # De gloria (IDs con formato gloria_N)
    # Se generan dinámicamente
}

# ==================== HELPERS ====================

def obtener_todos_los_titulos(user_id: int) -> List[str]:
    """
    Recopila todos los títulos desbloqueados del jugador de todas las fuentes.
    Retorna lista de strings con los títulos visibles (para mostrar).
    """
    titulos = set()

    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        return []

    # 1. Título base de clase
    clase = (jug.get("clase") or "").lower()
    if clase in TITULOS_CLASE:
        titulos.add(TITULOS_CLASE[clase])

    # 2. Títulos de logros (almacenados como texto legible en logros_desbloqueados)
    try:
        logros_lista = json.loads(jug.get("logros_desbloqueados") or "[]")
        for t in logros_lista:
            if isinstance(t, str) and not t.lstrip("-").isdigit():
                visible = TITULOS_ESPECIALES.get(t, t)
                titulos.add(visible)
    except Exception:
        pass

    # 3. Títulos de gloria
    try:
        import progresion_clase
        titulos_gloria = progresion_clase.obtener_titulos_gloria(user_id) or []
        for tid in titulos_gloria:
            if isinstance(tid, str) and tid.startswith("gloria_"):
                nivel = tid.replace("gloria_", "")
                titulos.add(f"Glorioso {nivel}")
            elif isinstance(tid, str):
                titulos.add(TITULOS_ESPECIALES.get(tid, tid))
    except Exception:
        pass

    # 4. Títulos de hitos de nivel (Conquistador de Nivel N)
    try:
        import progresion_clase
        hitos = progresion_clase.obtener_hitos_reclamados(user_id) or []
        for h in hitos:
            if isinstance(h, (int, str)):
                titulos.add(f"Conquistador de Nivel {h}")
    except Exception:
        pass

    return sorted(titulos)


def obtener_titulo_activo(user_id: int) -> Optional[str]:
    """Retorna el título activo del jugador o None si no tiene."""
    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        return None
    return jug.get("titulo_activo") or None


def establecer_titulo_activo(user_id: int, titulo: Optional[str]):
    """Establece o quita el título activo del jugador."""
    db_helper.actualizar_jugador(user_id, titulo_activo=titulo)


def texto_titulo_para_perfil(user_id: int) -> str:
    """Retorna el texto del título formateado para mostrar en el perfil."""
    t = obtener_titulo_activo(user_id)
    if t:
        return f"🎖️ *{t}*"
    return ""


# ==================== COMANDOS BOT ====================

async def cmd_mis_titulos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra todos los títulos del jugador y permite elegir el activo."""
    user_id = update.effective_user.id
    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        await update.effective_message.reply_text("❌ No tienes personaje. Usa /start para crear uno.")
        return

    todos = obtener_todos_los_titulos(user_id)
    activo = obtener_titulo_activo(user_id)

    if not todos:
        await update.effective_message.reply_text(
            "🎖️ Aún no tienes títulos desbloqueados.\n"
            "Sube de nivel, completa mazmorras y gana combates para ganarlos."
        )
        return

    texto = (
        f"🎖️ *Mis Títulos — {jug['nombre_personaje']}*\n"
        f"{'Título activo: *' + activo + '*' if activo else 'Sin título equipado'}\n\n"
        "Selecciona un título para equiparlo:\n"
    )

    # Paginar: 8 por página
    try:
        pagina = int(context.args[0]) if context.args else 1
    except (ValueError, IndexError):
        pagina = 1
    por_pagina = 8
    inicio = (pagina - 1) * por_pagina
    fin = inicio + por_pagina
    pagina_titulos = todos[inicio:fin]
    total_paginas = max(1, (len(todos) + por_pagina - 1) // por_pagina)

    botones = []
    for t in pagina_titulos:
        marcador = "✅ " if t == activo else ""
        botones.append([InlineKeyboardButton(
            f"{marcador}{t}",
            callback_data=f"titulo_equipar_{t[:40]}"
        )])

    nav = []
    if pagina > 1:
        nav.append(InlineKeyboardButton("◀️", callback_data=f"titulo_pag_{pagina-1}"))
    if pagina < total_paginas:
        nav.append(InlineKeyboardButton("▶️", callback_data=f"titulo_pag_{pagina+1}"))
    if nav:
        botones.append(nav)

    if activo:
        botones.append([InlineKeyboardButton("❌ Quitar título", callback_data="titulo_quitar")])

    await update.effective_message.reply_text(
        texto,
        reply_markup=InlineKeyboardMarkup(botones),
        parse_mode="Markdown"
    )


# ==================== CALLBACKS ====================

async def cb_titulos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    data = query.data

    if not db_helper.existe_jugador(user_id):
        await query.edit_message_text("❌ No tienes personaje.")
        return

    if data.startswith("titulo_equipar_"):
        titulo = data[len("titulo_equipar_"):]
        # Verificar que el título realmente le pertenece
        todos = obtener_todos_los_titulos(user_id)
        # El título puede estar truncado a 40 chars, comparar por prefijo
        coincidencia = next((t for t in todos if t[:40] == titulo), None)
        if not coincidencia:
            await query.edit_message_text("❌ No tienes ese título.")
            return
        establecer_titulo_activo(user_id, coincidencia)
        jug = db_helper.obtener_jugador(user_id)
        await query.edit_message_text(
            f"✅ Título equipado: <b>{_he(coincidencia)}</b>\n\n"
            f"Tu perfil ahora muestra: <b>{_he(jug['nombre_personaje'])}</b>, {_he(coincidencia)}",
            parse_mode="HTML"
        )

    elif data == "titulo_quitar":
        establecer_titulo_activo(user_id, None)
        await query.edit_message_text("✅ Has quitado tu título activo.")

    elif data.startswith("titulo_pag_"):
        try:
            pagina = int(data.split("_")[-1])
        except (ValueError, IndexError):
            pagina = 1
        context.args = [str(pagina)]
        await cmd_mis_titulos(update, context)

    elif data == "titulo_menu":
        context.args = []
        await cmd_mis_titulos(update, context)


# ==================== REGISTRO ====================

def registrar_handlers(app):
    app.add_handler(CommandHandler("mis_titulos",    cmd_mis_titulos))
    app.add_handler(CommandHandler("titulo_equipar", cmd_mis_titulos))
    app.add_handler(CallbackQueryHandler(cb_titulos, pattern=r"^titulo_"))

#!/usr/bin/env python3
# crear_items.py — Asistente de creación de armas y armaduras personalizadas
#
# Solo el SUPERADMIN puede usar estos comandos.
# Los items creados se guardan permanentemente en la tabla items_custom
# y se cargan en ARMAS/ARMADURAS al arrancar el bot.
#
# Comandos:
#   /crear_arma        — Asistente para crear un arma personalizada
#   /crear_armadura    — Asistente para crear un set de armadura personalizada
#   /mis_items_custom  — Listar todos los items creados por el admin
#   /borrar_item_custom <id> — Eliminar un item custom (¡cuidado!)

import sqlite3
import json
import os
import html as _html
from typing import Optional, Dict, Any

def _e(s) -> str:
    return _html.escape(str(s) if s is not None else "")

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ConversationHandler
)

import db_helper
import superadmin as sa

DB_PATH  = "aethelgard.db"

# ==================== TABLA ====================
def _init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS items_custom (
        id          TEXT PRIMARY KEY,
        tipo_item   TEXT NOT NULL,       -- 'arma' o 'armadura'
        datos_json  TEXT NOT NULL,       -- JSON completo del item
        creado_por  INTEGER,
        fecha       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.commit()
    conn.close()

_init_db()

# ==================== CARGA EN RUNTIME ====================
def cargar_items_custom():
    """Inyecta los items custom en los dicts ARMAS y ARMADURAS en tiempo de ejecución."""
    try:
        import armas as mod_armas
        import armaduras as mod_armaduras
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT id, tipo_item, datos_json FROM items_custom")
        rows = c.fetchall()
        conn.close()
        for row in rows:
            datos = json.loads(row["datos_json"])
            if row["tipo_item"] == "arma":
                mod_armas.ARMAS[row["id"]] = datos
            else:
                mod_armaduras.ARMADURAS[row["id"]] = datos
    except Exception as e:
        print(f"[crear_items] Error cargando items custom: {e}")

# ==================== ESTADOS DE CONVERSACIÓN ====================
(
    # Arma
    A_NOMBRE, A_TIPO, A_CLASE, A_NIVEL, A_DAÑO, A_CRITICO,
    A_VELOCIDAD, A_PESO, A_VIDA_EXTRA, A_DEFENSA_EXTRA,
    A_RAREZA, A_HABILIDAD_ACTIVA, A_HABILIDAD_PASIVA,
    A_ZONA, A_UNICA, A_PRECIO_ORO, A_PRECIO_ETH, A_PRECIO_CR,
    A_CONFIRMAR,
    # Armadura (set)
    S_NOMBRE_SET, S_CLASE, S_NIVEL, S_TIPOS, S_DEFENSA, S_RES_CRIT,
    S_VEL_MOV, S_PESO, S_VIDA_EXTRA, S_DEFENSA_EXTRA,
    S_RAREZA, S_ZONA, S_UNICA, S_PRECIO_ORO, S_PRECIO_ETH,
    S_CONFIRMAR,
) = range(35)

TIPOS_ARMA    = ["espada", "daga", "hacha", "maza", "martillo", "lanza", "arco", "ballesta", "baston", "grimorio", "guadaña", "hoz"]
TIPOS_ARMADURA = ["casco", "pechera", "grebas", "botas", "guantes", "capa"]
ZONAS         = ["azul", "amarilla", "roja", "negra"]
CLASES_VALIDAS = [None, "vanguardista", "acechante", "tejehechizos", "maestro_de_caza"]

def _get_next_id(tipo: str) -> str:
    """Genera el siguiente ID único para el item."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    prefix = "custom_arma_" if tipo == "arma" else "custom_armadura_"
    c.execute("SELECT COUNT(*) FROM items_custom WHERE tipo_item = ?", (tipo,))
    n = c.fetchone()[0] + 1
    conn.close()
    return f"{prefix}{n:04d}"

def _guardar_item(item_id: str, tipo: str, datos: Dict, user_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT OR REPLACE INTO items_custom (id, tipo_item, datos_json, creado_por) VALUES (?, ?, ?, ?)",
        (item_id, tipo, json.dumps(datos, ensure_ascii=False), user_id)
    )
    conn.commit()
    conn.close()

def _build_arma(d: Dict, item_id: str) -> Dict:
    return {
        "id":                 item_id,
        "nombre":             d["nombre"],
        "tipo":               d["tipo"],
        "clase_requerida":    d.get("clase") or None,
        "nivel_requerido":    int(d.get("nivel", 1)),
        "daño":               int(d.get("daño", 50)),
        "critico":            int(d.get("critico", 10)),
        "velocidad":          int(d.get("velocidad", 100)),
        "peso":               float(d.get("peso", 5.0)),
        "vida_extra":         int(d.get("vida_extra", 0)),
        "defensa_extra":      int(d.get("defensa_extra", 0)),
        "precio_oro":         int(d.get("precio_oro", 0)),
        "precio_eternium":    int(d.get("precio_eternium", 0)),
        "precio_creditos":    int(d.get("precio_creditos", 0)),
        "precio_venta_oro":   int(d.get("precio_oro", 0)) // 2,
        "precio_venta_eternium": int(d.get("precio_eternium", 0)) // 2,
        "rareza":             int(d.get("rareza", 5)),
        "descripcion":        f"Arma personalizada creada por el admin. Tipo: {d['tipo']}. Origen: admin.",
        "origen":             "admin_custom",
        "zona":               d.get("zona", "azul"),
        "stock_global":       1 if d.get("unica") else None,
        "stock_restante":     1 if d.get("unica") else None,
        "unica":              bool(d.get("unica")),
        "dueño_actual":       None,
        "habilidad_activa":   d.get("hab_activa") or None,
        "habilidad_pasiva":   d.get("hab_pasiva") or None,
    }

def _build_armadura(d: Dict, item_id: str, tipo_pieza: str, nombre_pieza: str) -> Dict:
    return {
        "id":                     item_id,
        "nombre":                 nombre_pieza,
        "tipo":                   tipo_pieza,
        "clase_requerida":        d.get("clase") or None,
        "nivel_requerido":        int(d.get("nivel", 1)),
        "defensa":                int(d.get("defensa", 10)),
        "resistencia_critico":    int(d.get("res_crit", 5)),
        "velocidad_movimiento":   int(d.get("vel_mov", 0)),
        "peso":                   float(d.get("peso", 5.0)),
        "vida_extra":             int(d.get("vida_extra", 0)),
        "defensa_extra":          int(d.get("defensa_extra", 0)),
        "precio_oro":             int(d.get("precio_oro", 0)),
        "precio_eternium":        int(d.get("precio_eternium", 0)),
        "precio_creditos":        0,
        "precio_venta_oro":       int(d.get("precio_oro", 0)) // 2,
        "precio_venta_eternium":  int(d.get("precio_eternium", 0)) // 2,
        "rareza":                 int(d.get("rareza", 5)),
        "descripcion":            f"Armadura personalizada: set {d.get('nombre_set','?')}. Pieza: {tipo_pieza}. Origen: admin.",
        "origen":                 "admin_custom",
        "zona":                   d.get("zona", "azul"),
        "stock_global":           1 if d.get("unica") else None,
        "stock_restante":         1 if d.get("unica") else None,
        "unica":                  bool(d.get("unica")),
        "dueño_actual":           None,
        "habilidad_activa":       None,
        "habilidad_pasiva":       None,
    }

# ==================== FLUJO: CREAR ARMA ====================

async def cmd_crear_arma(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not sa.verificar_superadmin(update.effective_user.id):
        await update.effective_message.reply_text("❌ Solo el superadmin puede crear items.")
        return ConversationHandler.END
    context.user_data["arma_data"] = {}
    await update.effective_message.reply_text(
        "⚔️ <b>Crear Arma Personalizada</b> — Paso 1/18\n\n"
        "📝 Escribe el <b>nombre</b> del arma:",
        parse_mode="HTML"
    )
    return A_NOMBRE

async def a_nombre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "arma_data" not in context.user_data:
        await update.effective_message.reply_text("⚠️ Sesión expirada. Usa /crear_arma para empezar de nuevo.")
        return ConversationHandler.END
    context.user_data["arma_data"]["nombre"] = update.message.text.strip()
    kb = [[InlineKeyboardButton(t.capitalize(), callback_data=f"a_tipo_{t}")] for t in TIPOS_ARMA]
    await update.effective_message.reply_text(
        "🗡️ Paso 2/18 — Elige el <b>tipo</b> de arma:",
        reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML"
    )
    return A_TIPO

async def a_tipo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["arma_data"]["tipo"] = query.data.replace("a_tipo_", "")
    kb = [
        [InlineKeyboardButton("Todas las clases", callback_data="a_clase_none")],
        *[[InlineKeyboardButton(c.replace("_", " ").capitalize(), callback_data=f"a_clase_{c}")] for c in CLASES_VALIDAS[1:]]
    ]
    await query.edit_message_text(
        "🛡️ Paso 3/18 — <b>Clase requerida</b> (¿quién puede equiparla?):",
        reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML"
    )
    return A_CLASE

async def a_clase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    valor = query.data.replace("a_clase_", "")
    context.user_data["arma_data"]["clase"] = None if valor == "none" else valor
    await query.edit_message_text("📊 Paso 4/18 — <b>Nivel mínimo requerido</b> (1–100):", parse_mode="HTML")
    return A_NIVEL

async def a_nivel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        n = max(1, min(100, int(update.message.text.strip())))
    except ValueError:
        await update.effective_message.reply_text("❌ Escribe un número del 1 al 100.")
        return A_NIVEL
    context.user_data["arma_data"]["nivel"] = n
    await update.effective_message.reply_text("⚔️ Paso 5/18 — <b>Daño base</b> del arma (1–9999):", parse_mode="HTML")
    return A_DAÑO

async def a_daño(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        n = max(1, min(9999, int(update.message.text.strip())))
    except ValueError:
        await update.effective_message.reply_text("❌ Escribe un número válido.")
        return A_DAÑO
    context.user_data["arma_data"]["daño"] = n
    await update.effective_message.reply_text("🎯 Paso 6/18 — <b>% de Crítico</b> (0–100):", parse_mode="HTML")
    return A_CRITICO

async def a_critico(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        n = max(0, min(100, int(update.message.text.strip())))
    except ValueError:
        await update.effective_message.reply_text("❌ Escribe un número del 0 al 100.")
        return A_CRITICO
    context.user_data["arma_data"]["critico"] = n
    await update.effective_message.reply_text("💨 Paso 7/18 — <b>Velocidad de ataque</b> (1–999):", parse_mode="HTML")
    return A_VELOCIDAD

async def a_velocidad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        n = max(1, min(999, int(update.message.text.strip())))
    except ValueError:
        await update.effective_message.reply_text("❌ Escribe un número válido.")
        return A_VELOCIDAD
    context.user_data["arma_data"]["velocidad"] = n
    await update.effective_message.reply_text("⚖️ Paso 8/18 — <b>Peso</b> del arma (ej: 5.5):", parse_mode="HTML")
    return A_PESO

async def a_peso(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        n = float(update.message.text.strip().replace(",", "."))
    except ValueError:
        await update.effective_message.reply_text("❌ Escribe un número decimal válido.")
        return A_PESO
    context.user_data["arma_data"]["peso"] = n
    await update.effective_message.reply_text("❤️ Paso 9/18 — <b>Vida extra</b> que añade (0 si ninguna):", parse_mode="HTML")
    return A_VIDA_EXTRA

async def a_vida_extra(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        n = max(0, int(update.message.text.strip()))
    except ValueError:
        await update.effective_message.reply_text("❌ Escribe un número.")
        return A_VIDA_EXTRA
    context.user_data["arma_data"]["vida_extra"] = n
    await update.effective_message.reply_text("🛡️ Paso 10/18 — <b>Defensa extra</b> que añade (0 si ninguna):", parse_mode="HTML")
    return A_DEFENSA_EXTRA

async def a_defensa_extra(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        n = max(0, int(update.message.text.strip()))
    except ValueError:
        await update.effective_message.reply_text("❌ Escribe un número.")
        return A_DEFENSA_EXTRA
    context.user_data["arma_data"]["defensa_extra"] = n
    kb = [[InlineKeyboardButton(f"{'⭐'*min(r,5)} Rareza {r}", callback_data=f"a_rareza_{r}")] for r in range(1, 13)]
    await update.effective_message.reply_text(
        "✨ Paso 11/18 — <b>Rareza</b> (1=Común, 6=Raro, 10=Épico, 12=Legendario):",
        reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML"
    )
    return A_RAREZA

async def a_rareza(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["arma_data"]["rareza"] = int(query.data.replace("a_rareza_", ""))
    await query.edit_message_text(
        "⚡ Paso 12/18 — <b>Habilidad ACTIVA</b> del arma\n"
        "Escribe la descripción o escribe <code>ninguna</code>:",
        parse_mode="HTML"
    )
    return A_HABILIDAD_ACTIVA

async def a_hab_activa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    context.user_data["arma_data"]["hab_activa"] = None if txt.lower() in ("ninguna", "no", "none", "-") else txt
    await update.effective_message.reply_text(
        "🔮 Paso 13/18 — <b>Habilidad PASIVA</b> del arma\n"
        "Escribe la descripción o escribe <code>ninguna</code>:",
        parse_mode="HTML"
    )
    return A_HABILIDAD_PASIVA

async def a_hab_pasiva(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    context.user_data["arma_data"]["hab_pasiva"] = None if txt.lower() in ("ninguna", "no", "none", "-") else txt
    kb = [[InlineKeyboardButton(z.capitalize(), callback_data=f"a_zona_{z}")] for z in ZONAS]
    await update.effective_message.reply_text(
        "🗺️ Paso 14/18 — <b>Zona</b> del mundo donde se puede encontrar/usar:",
        reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML"
    )
    return A_ZONA

async def a_zona(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["arma_data"]["zona"] = query.data.replace("a_zona_", "")
    kb = [
        [InlineKeyboardButton("⭐ Única (stock 1, 1 solo dueño)", callback_data="a_unica_si")],
        [InlineKeyboardButton("📦 Normal (sin límite de stock)", callback_data="a_unica_no")],
    ]
    await query.edit_message_text("🔑 Paso 15/18 — ¿El arma es <b>única</b>?", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
    return A_UNICA

async def a_unica(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["arma_data"]["unica"] = query.data == "a_unica_si"
    await query.edit_message_text("🪙 Paso 16/18 — <b>Precio en ORO</b> (0 si se obtiene solo por drop):", parse_mode="HTML")
    return A_PRECIO_ORO

async def a_precio_oro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        n = max(0, int(update.message.text.strip()))
    except ValueError:
        await update.effective_message.reply_text("❌ Escribe un número.")
        return A_PRECIO_ORO
    context.user_data["arma_data"]["precio_oro"] = n
    await update.effective_message.reply_text("💎 Paso 17/18 — <b>Precio en ETERNIUM</b> (0 si no aplica):", parse_mode="HTML")
    return A_PRECIO_ETH

async def a_precio_eth(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        n = max(0, int(update.message.text.strip()))
    except ValueError:
        await update.effective_message.reply_text("❌ Escribe un número.")
        return A_PRECIO_ETH
    context.user_data["arma_data"]["precio_eternium"] = n
    await update.effective_message.reply_text("✨ Paso 18/18 — <b>Precio en CRÉDITOS DEL VACÍO</b> (0 si no aplica):", parse_mode="HTML")
    return A_PRECIO_CR

async def a_precio_cr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        n = max(0, int(update.message.text.strip()))
    except ValueError:
        await update.effective_message.reply_text("❌ Escribe un número.")
        return A_PRECIO_CR
    context.user_data["arma_data"]["precio_creditos"] = n
    d = context.user_data["arma_data"]
    clase_txt = d.get("clase") or "Todas"
    unica_txt = "Sí (única)" if d.get("unica") else "No"
    texto = (
        "📋 <b>Resumen del Arma</b>\n\n"
        f"🏷️ Nombre: <b>{_e(d['nombre'])}</b>\n"
        f"🗡️ Tipo: {_e(d['tipo'])}\n"
        f"🛡️ Clase: {_e(clase_txt)}\n"
        f"📊 Nivel mín: {_e(d['nivel'])}\n"
        f"⚔️ Daño: {_e(d['daño'])} | 🎯 Crítico: {_e(d['critico'])}%\n"
        f"💨 Velocidad: {_e(d['velocidad'])} | ⚖️ Peso: {_e(d['peso'])}\n"
        f"❤️ Vida extra: {_e(d['vida_extra'])} | 🛡️ Def extra: {_e(d['defensa_extra'])}\n"
        f"✨ Rareza: {_e(d['rareza'])}\n"
        f"🗺️ Zona: {_e(d['zona'])} | 🔑 Única: {_e(unica_txt)}\n"
        f"⚡ Hab. activa: {_e(d.get('hab_activa') or '—')}\n"
        f"🔮 Hab. pasiva: {_e(d.get('hab_pasiva') or '—')}\n"
        f"🪙 Oro: {_e(d['precio_oro'])} | 💎 Eth: {_e(d['precio_eternium'])} | ✨ Cr: {_e(d['precio_creditos'])}\n\n"
        "¿Confirmar creación?"
    )
    kb = [
        [InlineKeyboardButton("✅ Crear arma", callback_data="a_confirmar_si")],
        [InlineKeyboardButton("❌ Cancelar",   callback_data="a_confirmar_no")],
    ]
    await update.effective_message.reply_text(texto, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
    return A_CONFIRMAR

async def a_confirmar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "a_confirmar_no":
        context.user_data.pop("arma_data", None)
        await query.edit_message_text("❌ Creación cancelada.")
        return ConversationHandler.END
    d = context.user_data["arma_data"]
    user_id = update.effective_user.id
    item_id = _get_next_id("arma")
    datos = _build_arma(d, item_id)
    _guardar_item(item_id, "arma", datos, user_id)
    # Inyectar en runtime
    try:
        import armas as mod_armas
        mod_armas.ARMAS[item_id] = datos
    except Exception:
        pass
    context.user_data.pop("arma_data", None)
    await query.edit_message_text(
        f"✅ <b>¡Arma creada con éxito!</b>\n"
        f"🆔 ID: <code>{_e(item_id)}</code>\n"
        f"🏷️ Nombre: <b>{_e(datos['nombre'])}</b>\n\n"
        f"El arma ya está disponible en el juego.\n"
        f"Usa <code>/dar_item &lt;user_id&gt; {_e(datos['nombre'])} 1</code> para entregarla a un jugador.",
        parse_mode="HTML"
    )
    return ConversationHandler.END

# ==================== FLUJO: CREAR SET DE ARMADURA ====================

async def cmd_crear_armadura(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not sa.verificar_superadmin(update.effective_user.id):
        await update.effective_message.reply_text("❌ Solo el superadmin puede crear items.")
        return ConversationHandler.END
    context.user_data["set_data"] = {}
    await update.effective_message.reply_text(
        "🛡️ <b>Crear Set de Armadura Personalizada</b> — Paso 1\n\n"
        "📝 Escribe el <b>nombre del set</b> (ej: Armadura del Caos):",
        parse_mode="HTML"
    )
    return S_NOMBRE_SET

async def s_nombre_set(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "set_data" not in context.user_data:
        await update.effective_message.reply_text("⚠️ Sesión expirada. Usa /crear_armadura para empezar de nuevo.")
        return ConversationHandler.END
    context.user_data["set_data"]["nombre_set"] = update.message.text.strip()
    kb = [
        [InlineKeyboardButton("Todas las clases", callback_data="s_clase_none")],
        *[[InlineKeyboardButton(c.replace("_", " ").capitalize(), callback_data=f"s_clase_{c}")] for c in CLASES_VALIDAS[1:]]
    ]
    await update.effective_message.reply_text(
        "🛡️ Paso 2 — <b>Clase requerida</b> para usar el set:",
        reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML"
    )
    return S_CLASE

async def s_clase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    valor = query.data.replace("s_clase_", "")
    context.user_data["set_data"]["clase"] = None if valor == "none" else valor
    await query.edit_message_text("📊 Paso 3 — <b>Nivel mínimo requerido</b> (1–100):", parse_mode="HTML")
    return S_NIVEL

async def s_nivel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        n = max(1, min(100, int(update.message.text.strip())))
    except ValueError:
        await update.effective_message.reply_text("❌ Escribe un número del 1 al 100.")
        return S_NIVEL
    context.user_data["set_data"]["nivel"] = n
    kb = [[InlineKeyboardButton(t.capitalize(), callback_data=f"s_tipo_{t}")] for t in TIPOS_ARMADURA]
    kb.append([InlineKeyboardButton("✅ Listo (confirmar piezas)", callback_data="s_tipo_listo")])
    context.user_data["set_data"]["tipos_elegidos"] = []
    await update.effective_message.reply_text(
        "🧩 Paso 4 — <b>Piezas del set</b> (puedes elegir varias o todas):\n"
        "Toca cada pieza que quieras incluir. Cuando termines, toca '✅ Listo'.",
        reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML"
    )
    return S_TIPOS

async def s_tipos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    d = context.user_data["set_data"]
    if query.data == "s_tipo_listo":
        if not d.get("tipos_elegidos"):
            await query.answer("Debes elegir al menos una pieza.", show_alert=True)
            return S_TIPOS
        elegidos = ", ".join(d["tipos_elegidos"])
        await query.edit_message_text(f"✅ Piezas del set: <b>{_e(elegidos)}</b>\n\n🛡️ Paso 5 — <b>Defensa base</b> por pieza:", parse_mode="HTML")
        return S_DEFENSA
    pieza = query.data.replace("s_tipo_", "")
    if pieza not in d["tipos_elegidos"]:
        d["tipos_elegidos"].append(pieza)
    else:
        d["tipos_elegidos"].remove(pieza)
    elegidos = ", ".join(d["tipos_elegidos"]) if d["tipos_elegidos"] else "ninguna"
    kb = []
    for t in TIPOS_ARMADURA:
        marca = "✅ " if t in d["tipos_elegidos"] else ""
        kb.append([InlineKeyboardButton(f"{marca}{t.capitalize()}", callback_data=f"s_tipo_{t}")])
    kb.append([InlineKeyboardButton("✅ Listo", callback_data="s_tipo_listo")])
    # nota: elegidos se usa solo para mostrar en el mensaje de edición debajo
    await query.edit_message_text(
        f"🧩 Piezas seleccionadas: <b>{_e(elegidos)}</b>\nSigue eligiendo o toca '✅ Listo'.",
        reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML"
    )
    return S_TIPOS

async def s_defensa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        n = max(0, int(update.message.text.strip()))
    except ValueError:
        await update.effective_message.reply_text("❌ Escribe un número.")
        return S_DEFENSA
    context.user_data["set_data"]["defensa"] = n
    await update.effective_message.reply_text("🎯 Paso 6 — <b>Resistencia al Crítico</b> (0–100):", parse_mode="HTML")
    return S_RES_CRIT

async def s_res_crit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        n = max(0, min(100, int(update.message.text.strip())))
    except ValueError:
        await update.effective_message.reply_text("❌ Escribe un número.")
        return S_RES_CRIT
    context.user_data["set_data"]["res_crit"] = n
    await update.effective_message.reply_text("💨 Paso 7 — <b>Velocidad de movimiento</b> bonus (puede ser negativo, 0 si nada):", parse_mode="HTML")
    return S_VEL_MOV

async def s_vel_mov(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        n = int(update.message.text.strip())
    except ValueError:
        await update.effective_message.reply_text("❌ Escribe un número.")
        return S_VEL_MOV
    context.user_data["set_data"]["vel_mov"] = n
    await update.effective_message.reply_text("⚖️ Paso 8 — <b>Peso por pieza</b> (ej: 8.5):", parse_mode="HTML")
    return S_PESO

async def s_peso(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        n = float(update.message.text.strip().replace(",", "."))
    except ValueError:
        await update.effective_message.reply_text("❌ Escribe un número decimal.")
        return S_PESO
    context.user_data["set_data"]["peso"] = n
    await update.effective_message.reply_text("❤️ Paso 9 — <b>Vida extra</b> por pieza (0 si ninguna):", parse_mode="HTML")
    return S_VIDA_EXTRA

async def s_vida_extra(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        n = max(0, int(update.message.text.strip()))
    except ValueError:
        await update.effective_message.reply_text("❌ Escribe un número.")
        return S_VIDA_EXTRA
    context.user_data["set_data"]["vida_extra"] = n
    await update.effective_message.reply_text("🛡️ Paso 10 — <b>Defensa extra</b> por pieza (0 si ninguna):", parse_mode="HTML")
    return S_DEFENSA_EXTRA

async def s_defensa_extra(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        n = max(0, int(update.message.text.strip()))
    except ValueError:
        await update.effective_message.reply_text("❌ Escribe un número.")
        return S_DEFENSA_EXTRA
    context.user_data["set_data"]["defensa_extra"] = n
    kb = [[InlineKeyboardButton(f"{'⭐'*min(r,5)} Rareza {r}", callback_data=f"s_rareza_{r}")] for r in range(1, 13)]
    await update.effective_message.reply_text(
        "✨ Paso 11 — <b>Rareza del set</b> (1=Común … 12=Legendario):",
        reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML"
    )
    return S_RAREZA

async def s_rareza(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["set_data"]["rareza"] = int(query.data.replace("s_rareza_", ""))
    kb = [[InlineKeyboardButton(z.capitalize(), callback_data=f"s_zona_{z}")] for z in ZONAS]
    await query.edit_message_text("🗺️ Paso 12 — <b>Zona</b> del mundo:", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
    return S_ZONA

async def s_zona(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["set_data"]["zona"] = query.data.replace("s_zona_", "")
    kb = [
        [InlineKeyboardButton("⭐ Única (1 set en el mundo)", callback_data="s_unica_si")],
        [InlineKeyboardButton("📦 Normal",                   callback_data="s_unica_no")],
    ]
    await query.edit_message_text("🔑 Paso 13 — ¿El set es <b>único</b>?", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
    return S_UNICA

async def s_unica(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["set_data"]["unica"] = query.data == "s_unica_si"
    await query.edit_message_text("🪙 Paso 14 — <b>Precio en ORO por pieza</b> (0 si solo drop):", parse_mode="HTML")
    return S_PRECIO_ORO

async def s_precio_oro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        n = max(0, int(update.message.text.strip()))
    except ValueError:
        await update.effective_message.reply_text("❌ Escribe un número.")
        return S_PRECIO_ORO
    context.user_data["set_data"]["precio_oro"] = n
    await update.effective_message.reply_text("💎 Paso 15 — <b>Precio en ETERNIUM por pieza</b> (0 si no aplica):", parse_mode="HTML")
    return S_PRECIO_ETH

async def s_precio_eth(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        n = max(0, int(update.message.text.strip()))
    except ValueError:
        await update.effective_message.reply_text("❌ Escribe un número.")
        return S_PRECIO_ETH
    context.user_data["set_data"]["precio_eternium"] = n
    d = context.user_data["set_data"]
    clase_txt = d.get("clase") or "Todas"
    unica_txt = "Sí" if d.get("unica") else "No"
    piezas_txt = ", ".join(d.get("tipos_elegidos", []))
    piezas_html = "\n".join(f"  • {_e(d['nombre_set'])} ({_e(p.capitalize())})" for p in d['tipos_elegidos'])
    texto = (
        "📋 <b>Resumen del Set</b>\n\n"
        f"🏷️ Nombre del set: <b>{_e(d['nombre_set'])}</b>\n"
        f"🧩 Piezas: {_e(piezas_txt)}\n"
        f"🛡️ Clase: {_e(clase_txt)} | 📊 Nivel mín: {_e(d['nivel'])}\n"
        f"🛡️ Defensa: {_e(d['defensa'])} | 🎯 Res.Crit: {_e(d['res_crit'])}%\n"
        f"💨 Vel. mov: {_e(d['vel_mov'])} | ⚖️ Peso: {_e(d['peso'])}\n"
        f"❤️ Vida extra: {_e(d['vida_extra'])} | 🛡️ Def extra: {_e(d['defensa_extra'])}\n"
        f"✨ Rareza: {_e(d['rareza'])} | 🗺️ Zona: {_e(d['zona'])} | 🔑 Única: {_e(unica_txt)}\n"
        f"🪙 Oro/pieza: {_e(d['precio_oro'])} | 💎 Eth/pieza: {_e(d['precio_eternium'])}\n\n"
        f"Se crearán <b>{len(d['tipos_elegidos'])} piezas</b> con el nombre:\n"
        + piezas_html +
        "\n\n¿Confirmar creación del set?"
    )
    kb = [
        [InlineKeyboardButton("✅ Crear set", callback_data="s_confirmar_si")],
        [InlineKeyboardButton("❌ Cancelar",  callback_data="s_confirmar_no")],
    ]
    await update.effective_message.reply_text(texto, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
    return S_CONFIRMAR

async def s_confirmar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "s_confirmar_no":
        context.user_data.pop("set_data", None)
        await query.edit_message_text("❌ Creación cancelada.")
        return ConversationHandler.END
    d = context.user_data["set_data"]
    user_id = update.effective_user.id
    ids_creados = []
    try:
        import armaduras as mod_arm
    except ImportError:
        mod_arm = None
    for pieza in d["tipos_elegidos"]:
        item_id = _get_next_id("armadura")
        nombre_pieza = f"{d['nombre_set']} ({pieza.capitalize()})"
        datos = _build_armadura(d, item_id, pieza, nombre_pieza)
        _guardar_item(item_id, "armadura", datos, user_id)
        if mod_arm:
            mod_arm.ARMADURAS[item_id] = datos
        ids_creados.append((item_id, nombre_pieza))
    context.user_data.pop("set_data", None)
    lineas = "\n".join(f"  • <code>{_e(iid)}</code> — {_e(nom)}" for iid, nom in ids_creados)
    await query.edit_message_text(
        f"✅ <b>¡Set creado con éxito!</b> ({len(ids_creados)} piezas)\n\n{lineas}\n\n"
        "Los items ya están disponibles en el juego.",
        parse_mode="HTML"
    )
    return ConversationHandler.END

# ==================== LISTAR Y BORRAR ====================

async def cmd_mis_items_custom(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not sa.verificar_superadmin(update.effective_user.id):
        await update.effective_message.reply_text("❌ Acceso denegado.")
        return
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT id, tipo_item, datos_json, fecha FROM items_custom ORDER BY fecha DESC")
    rows = c.fetchall()
    conn.close()
    if not rows:
        await update.effective_message.reply_text("No hay items personalizados creados aún.")
        return
    texto = f"🗃️ <b>Items Personalizados</b> ({len(rows)} total)\n\n"
    for r in rows[:20]:
        d = json.loads(r["datos_json"])
        fecha = r["fecha"][:10] if r["fecha"] else "?"
        texto += f"• <code>{_e(r['id'])}</code> — {_e(d['nombre'])} ({_e(r['tipo_item'])}) [{_e(fecha)}]\n"
    if len(rows) > 20:
        texto += f"\n<i>...y {len(rows)-20} más</i>"
    texto += "\n\n<i>Usa /borrar_item_custom &lt;id&gt; para eliminar uno.</i>"
    await update.effective_message.reply_text(texto, parse_mode="HTML")

async def cmd_borrar_item_custom(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not sa.verificar_superadmin(update.effective_user.id):
        await update.effective_message.reply_text("❌ Acceso denegado.")
        return
    if not context.args:
        await update.effective_message.reply_text("Uso: /borrar_item_custom <id>")
        return
    item_id = context.args[0].strip()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT tipo_item, datos_json FROM items_custom WHERE id = ?", (item_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        await update.effective_message.reply_text(f"❌ Item <code>{_e(item_id)}</code> no encontrado.", parse_mode="HTML")
        return
    datos = json.loads(row["datos_json"])
    c.execute("DELETE FROM items_custom WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
    # Quitar de runtime
    try:
        if row["tipo_item"] == "arma":
            import armas as m; m.ARMAS.pop(item_id, None)
        else:
            import armaduras as m; m.ARMADURAS.pop(item_id, None)
    except Exception:
        pass
    await update.effective_message.reply_text(
        f"🗑️ Item eliminado: <code>{_e(item_id)}</code> — <b>{_e(datos['nombre'])}</b>\n"
        "⚠️ Los jugadores que lo tengan en el inventario lo conservarán.",
        parse_mode="HTML"
    )

# ==================== CANCELAR CONVERSACIONES ====================
async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("arma_data", None)
    context.user_data.pop("set_data", None)
    await update.effective_message.reply_text("❌ Creación cancelada.")
    return ConversationHandler.END

# ==================== REGISTRO ====================
def registrar_handlers(app):
    conv_arma = ConversationHandler(
        entry_points=[CommandHandler("crear_arma", cmd_crear_arma)],
        states={
            A_NOMBRE:           [MessageHandler(filters.TEXT & ~filters.COMMAND, a_nombre)],
            A_TIPO:             [CallbackQueryHandler(a_tipo,          pattern=r"^a_tipo_")],
            A_CLASE:            [CallbackQueryHandler(a_clase,         pattern=r"^a_clase_")],
            A_NIVEL:            [MessageHandler(filters.TEXT & ~filters.COMMAND, a_nivel)],
            A_DAÑO:             [MessageHandler(filters.TEXT & ~filters.COMMAND, a_daño)],
            A_CRITICO:          [MessageHandler(filters.TEXT & ~filters.COMMAND, a_critico)],
            A_VELOCIDAD:        [MessageHandler(filters.TEXT & ~filters.COMMAND, a_velocidad)],
            A_PESO:             [MessageHandler(filters.TEXT & ~filters.COMMAND, a_peso)],
            A_VIDA_EXTRA:       [MessageHandler(filters.TEXT & ~filters.COMMAND, a_vida_extra)],
            A_DEFENSA_EXTRA:    [MessageHandler(filters.TEXT & ~filters.COMMAND, a_defensa_extra)],
            A_RAREZA:           [CallbackQueryHandler(a_rareza,        pattern=r"^a_rareza_")],
            A_HABILIDAD_ACTIVA: [MessageHandler(filters.TEXT & ~filters.COMMAND, a_hab_activa)],
            A_HABILIDAD_PASIVA: [MessageHandler(filters.TEXT & ~filters.COMMAND, a_hab_pasiva)],
            A_ZONA:             [CallbackQueryHandler(a_zona,          pattern=r"^a_zona_")],
            A_UNICA:            [CallbackQueryHandler(a_unica,         pattern=r"^a_unica_")],
            A_PRECIO_ORO:       [MessageHandler(filters.TEXT & ~filters.COMMAND, a_precio_oro)],
            A_PRECIO_ETH:       [MessageHandler(filters.TEXT & ~filters.COMMAND, a_precio_eth)],
            A_PRECIO_CR:        [MessageHandler(filters.TEXT & ~filters.COMMAND, a_precio_cr)],
            A_CONFIRMAR:        [CallbackQueryHandler(a_confirmar,     pattern=r"^a_confirmar_")],
        },
        fallbacks=[CommandHandler("cancelar", cancelar)],
        allow_reentry=True,
    )

    conv_armadura = ConversationHandler(
        entry_points=[CommandHandler("crear_armadura", cmd_crear_armadura)],
        states={
            S_NOMBRE_SET:   [MessageHandler(filters.TEXT & ~filters.COMMAND, s_nombre_set)],
            S_CLASE:        [CallbackQueryHandler(s_clase,      pattern=r"^s_clase_")],
            S_NIVEL:        [MessageHandler(filters.TEXT & ~filters.COMMAND, s_nivel)],
            S_TIPOS:        [CallbackQueryHandler(s_tipos,      pattern=r"^s_tipo_")],
            S_DEFENSA:      [MessageHandler(filters.TEXT & ~filters.COMMAND, s_defensa)],
            S_RES_CRIT:     [MessageHandler(filters.TEXT & ~filters.COMMAND, s_res_crit)],
            S_VEL_MOV:      [MessageHandler(filters.TEXT & ~filters.COMMAND, s_vel_mov)],
            S_PESO:         [MessageHandler(filters.TEXT & ~filters.COMMAND, s_peso)],
            S_VIDA_EXTRA:   [MessageHandler(filters.TEXT & ~filters.COMMAND, s_vida_extra)],
            S_DEFENSA_EXTRA:[MessageHandler(filters.TEXT & ~filters.COMMAND, s_defensa_extra)],
            S_RAREZA:       [CallbackQueryHandler(s_rareza,     pattern=r"^s_rareza_")],
            S_ZONA:         [CallbackQueryHandler(s_zona,       pattern=r"^s_zona_")],
            S_UNICA:        [CallbackQueryHandler(s_unica,      pattern=r"^s_unica_")],
            S_PRECIO_ORO:   [MessageHandler(filters.TEXT & ~filters.COMMAND, s_precio_oro)],
            S_PRECIO_ETH:   [MessageHandler(filters.TEXT & ~filters.COMMAND, s_precio_eth)],
            S_CONFIRMAR:    [CallbackQueryHandler(s_confirmar,  pattern=r"^s_confirmar_")],
        },
        fallbacks=[CommandHandler("cancelar", cancelar)],
        allow_reentry=True,
    )

    app.add_handler(conv_arma)
    app.add_handler(conv_armadura)
    app.add_handler(CommandHandler("mis_items_custom",   cmd_mis_items_custom))
    app.add_handler(CommandHandler("borrar_item_custom", cmd_borrar_item_custom))

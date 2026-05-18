#!/usr/bin/env python3
# gremios_niveles.py — Sistema de niveles para gremios
#
# Niveles 1-10, cada uno requiere objetos/materiales y sube capacidad + bonificaciones.
# Comandos:
#   /gremio_nivel         — Ver nivel actual y requisitos del siguiente
#   /gremio_subir_nivel   — Intentar subir de nivel (consume materiales del banco del gremio)
#   /gremio_bonificaciones — Ver bonificaciones activas del nivel
# Admin:
#   /admin_gremio_forzar_nivel <gremio_id> <nivel> — Forzar nivel

import sqlite3
import json
from datetime import datetime
from typing import Optional, Dict, List

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters

import db_helper
import superadmin as sa

DB_PATH = "aethelgard.db"

def _esc_md(s: str) -> str:
    return str(s).replace("_", "\\_").replace("*", "\\*").replace("`", "\\`").replace("[", "\\[")

# ==================== DEFINICIÓN DE NIVELES ====================
# Cada nivel define: capacidad máxima de miembros, requisitos de materiales,
# coste en oro del banco del gremio, y bonificaciones activas.
NIVELES_GREMIO = {
    1: {
        "capacidad": 10, "limite_baul": 20,
        "requisitos_items": {},
        "coste_oro": 0,
        "bonificaciones": {"xp_bonus": 0, "oro_bonus": 0, "stamina_bonus": 0, "crafting_descuento": 0},
        "descripcion": "Gremio recién fundado."
    },
    2: {
        "capacidad": 15, "limite_baul": 30,
        "requisitos_items": {"Madera Común": 50, "Piedra Bruta": 30},
        "coste_oro": 5000,
        "bonificaciones": {"xp_bonus": 5, "oro_bonus": 3, "stamina_bonus": 0, "crafting_descuento": 0},
        "descripcion": "+5% XP al completar mazmorras."
    },
    3: {
        "capacidad": 20, "limite_baul": 40,
        "requisitos_items": {"Madera Común": 100, "Piedra Bruta": 80, "Hierro Bruto": 40},
        "coste_oro": 15000,
        "bonificaciones": {"xp_bonus": 10, "oro_bonus": 5, "stamina_bonus": 5, "crafting_descuento": 0},
        "descripcion": "+10% XP, +5% Oro, +5 stamina máxima."
    },
    4: {
        "capacidad": 25, "limite_baul": 60,
        "requisitos_items": {"Madera Reforzada": 50, "Hierro Bruto": 100, "Cuero Grueso": 40},
        "coste_oro": 40000,
        "bonificaciones": {"xp_bonus": 15, "oro_bonus": 8, "stamina_bonus": 10, "crafting_descuento": 5},
        "descripcion": "+15% XP, +8% Oro, +10 stamina, -5% coste crafteo."
    },
    5: {
        "capacidad": 30, "limite_baul": 80,
        "requisitos_items": {"Acero Puro": 50, "Madera Reforzada": 80, "Seda de Araña": 30},
        "coste_oro": 100000,
        "bonificaciones": {"xp_bonus": 20, "oro_bonus": 12, "stamina_bonus": 15, "crafting_descuento": 10},
        "descripcion": "+20% XP, +12% Oro, +15 stamina, -10% crafteo."
    },
    6: {
        "capacidad": 40, "limite_baul": 100,
        "requisitos_items": {"Acero Puro": 100, "Gema Azul": 20, "Esencia Mágica": 30},
        "coste_oro": 250000,
        "bonificaciones": {"xp_bonus": 25, "oro_bonus": 15, "stamina_bonus": 20, "crafting_descuento": 15},
        "descripcion": "+25% XP, +15% Oro, +20 stamina, -15% crafteo."
    },
    7: {
        "capacidad": 50, "limite_baul": 120,
        "requisitos_items": {"Cristal Estelar": 20, "Acero Puro": 150, "Gema Azul": 40},
        "coste_oro": 500000,
        "bonificaciones": {"xp_bonus": 30, "oro_bonus": 20, "stamina_bonus": 25, "crafting_descuento": 20},
        "descripcion": "+30% XP, +20% Oro, +25 stamina, -20% crafteo."
    },
    8: {
        "capacidad": 60, "limite_baul": 150,
        "requisitos_items": {"Cristal Estelar": 50, "Esencia Oscura": 30, "Runa Antigua": 10},
        "coste_oro": 1000000,
        "bonificaciones": {"xp_bonus": 40, "oro_bonus": 25, "stamina_bonus": 30, "crafting_descuento": 25},
        "descripcion": "+40% XP, +25% Oro, +30 stamina, -25% crafteo."
    },
    9: {
        "capacidad": 80, "limite_baul": 175,
        "requisitos_items": {"Núcleo de Dragón": 5, "Cristal Estelar": 80, "Runa Antigua": 20},
        "coste_oro": 2500000,
        "bonificaciones": {"xp_bonus": 50, "oro_bonus": 30, "stamina_bonus": 40, "crafting_descuento": 30},
        "descripcion": "+50% XP, +30% Oro, +40 stamina, -30% crafteo."
    },
    10: {
        "capacidad": 100, "limite_baul": 200,
        "requisitos_items": {"Fragmento del Vacío": 3, "Núcleo de Dragón": 10, "Runa Antigua": 30},
        "coste_oro": 5000000,
        "bonificaciones": {"xp_bonus": 60, "oro_bonus": 40, "stamina_bonus": 50, "crafting_descuento": 40},
        "descripcion": "Nivel máximo: +60% XP, +40% Oro, +50 stamina, -40% crafteo."
    },
}
NIVEL_MAXIMO = 10

# ==================== TABLAS ====================
def _init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS gremios_nivel (
        gremio_id INTEGER PRIMARY KEY,
        nivel INTEGER DEFAULT 1,
        ultimo_subida TIMESTAMP
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS gremios_banco_materiales (
        gremio_id INTEGER,
        material TEXT,
        cantidad INTEGER DEFAULT 0,
        PRIMARY KEY (gremio_id, material)
    )''')
    conn.commit()
    conn.close()

_init_db()

# ==================== HELPERS ====================
def _obtener_nivel_gremio(gremio_id: int) -> int:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT nivel FROM gremios_nivel WHERE gremio_id = ?', (gremio_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 1

def _set_nivel_gremio(gremio_id: int, nivel: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        'INSERT OR REPLACE INTO gremios_nivel (gremio_id, nivel, ultimo_subida) VALUES (?, ?, ?)',
        (gremio_id, nivel, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

def _obtener_materiales_banco(gremio_id: int) -> Dict[str, int]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT material, cantidad FROM gremios_banco_materiales WHERE gremio_id = ?', (gremio_id,))
    rows = c.fetchall()
    conn.close()
    return {r['material']: r['cantidad'] for r in rows}

def _consumir_materiales(gremio_id: int, requisitos: Dict[str, int]) -> bool:
    """Intenta consumir materiales. Retorna True si tuvo éxito, False si no alcanza."""
    banco = _obtener_materiales_banco(gremio_id)
    for mat, cantidad in requisitos.items():
        if banco.get(mat, 0) < cantidad:
            return False
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    for mat, cantidad in requisitos.items():
        nuevo = banco.get(mat, 0) - cantidad
        c.execute(
            'INSERT OR REPLACE INTO gremios_banco_materiales (gremio_id, material, cantidad) VALUES (?, ?, ?)',
            (gremio_id, mat, nuevo)
        )
    conn.commit()
    conn.close()
    return True

def _depositar_material_banco(gremio_id: int, material: str, cantidad: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT cantidad FROM gremios_banco_materiales WHERE gremio_id = ? AND material = ?',
              (gremio_id, material))
    row = c.fetchone()
    actual = row[0] if row else 0
    c.execute(
        'INSERT OR REPLACE INTO gremios_banco_materiales (gremio_id, material, cantidad) VALUES (?, ?, ?)',
        (gremio_id, material, actual + cantidad)
    )
    conn.commit()
    conn.close()

def _obtener_gremio_de_jugador(user_id: int) -> Optional[Dict]:
    """Retorna dict con info del gremio al que pertenece el jugador."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('''SELECT g.* FROM gremios g
                 JOIN miembros_gremio m ON g.id = m.gremio_id
                 WHERE m.jugador_id = ?''', (user_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def _es_lider_o_oficial(user_id: int, gremio_id: int) -> bool:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT rango FROM miembros_gremio WHERE gremio_id = ? AND jugador_id = ?', (gremio_id, user_id))
    row = c.fetchone()
    conn.close()
    if not row:
        return False
    return row[0] in ('lider', 'oficial', 'fundador')

def _oro_banco_gremio(gremio_id: int) -> int:
    """Obtiene el oro del banco del gremio (tabla gremios, campo banco_oro)."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT banco_oro FROM gremios WHERE id = ?', (gremio_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0

def _gastar_oro_banco(gremio_id: int, cantidad: int) -> bool:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT banco_oro FROM gremios WHERE id = ?', (gremio_id,))
    row = c.fetchone()
    if not row or row[0] < cantidad:
        conn.close()
        return False
    c.execute('UPDATE gremios SET banco_oro = banco_oro - ? WHERE id = ?', (cantidad, gremio_id))
    conn.commit()
    conn.close()
    return True

def obtener_bonificaciones_gremio(user_id: int) -> Dict:
    """Exportable: devuelve el dict de bonificaciones del gremio del jugador."""
    gremio = _obtener_gremio_de_jugador(user_id)
    if not gremio:
        return {"xp_bonus": 0, "oro_bonus": 0, "stamina_bonus": 0, "crafting_descuento": 0}
    nivel = _obtener_nivel_gremio(gremio["id"])
    return NIVELES_GREMIO.get(nivel, NIVELES_GREMIO[1])["bonificaciones"]

def obtener_capacidad_gremio(gremio_id: int) -> int:
    """Exportable: retorna la capacidad máxima de miembros según el nivel."""
    nivel = _obtener_nivel_gremio(gremio_id)
    return NIVELES_GREMIO.get(nivel, NIVELES_GREMIO[1])["capacidad"]

def obtener_limite_baul_gremio(gremio_id: int) -> int:
    """Exportable: retorna el límite de slots del baúl según el nivel."""
    nivel = _obtener_nivel_gremio(gremio_id)
    return NIVELES_GREMIO.get(nivel, NIVELES_GREMIO[1]).get("limite_baul", 20)

def _en_ciudad(user_id: int) -> bool:
    """Retorna True si el jugador está en una ciudad."""
    try:
        import datos_zona as _dz
        zona_nombre = db_helper.obtener_zona_actual(user_id)
        return any(z["nombre"] == zona_nombre and z["tipo"] == "ciudad" for z in _dz.ZONAS)
    except Exception:
        return False

# ==================== COMANDO /gremio_nivel ====================
async def cmd_gremio_nivel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not _en_ciudad(user_id):
        await update.effective_message.reply_text("🏙️ Las actividades de gremio solo están disponibles en ciudades.")
        return
    gremio = _obtener_gremio_de_jugador(user_id)
    if not gremio:
        await update.effective_message.reply_text("❌ No perteneces a ningún gremio.")
        return

    gremio_id = gremio["id"]
    nivel_actual = _obtener_nivel_gremio(gremio_id)
    cfg_actual = NIVELES_GREMIO[nivel_actual]
    banco_materiales = _obtener_materiales_banco(gremio_id)
    oro_banco = _oro_banco_gremio(gremio_id)

    texto = (
        f"🏛️ *{_esc_md(gremio['nombre'])}* — Nivel {nivel_actual}\n"
        f"Capacidad: {cfg_actual['capacidad']} miembros\n"
        f"📜 {cfg_actual['descripcion']}\n\n"
        f"*Bonificaciones activas:*\n"
        f"• XP: +{cfg_actual['bonificaciones']['xp_bonus']}%\n"
        f"• Oro: +{cfg_actual['bonificaciones']['oro_bonus']}%\n"
        f"• Stamina extra: +{cfg_actual['bonificaciones']['stamina_bonus']}\n"
        f"• Descuento crafteo: -{cfg_actual['bonificaciones']['crafting_descuento']}%\n\n"
    )

    if nivel_actual >= NIVEL_MAXIMO:
        texto += "🌟 *¡Nivel máximo alcanzado!*"
        await update.effective_message.reply_text(texto, parse_mode="Markdown")
        return

    siguiente = nivel_actual + 1
    cfg_sig = NIVELES_GREMIO[siguiente]
    texto += f"*Para subir al nivel {siguiente}:*\n"
    texto += f"🪙 Oro del banco: {cfg_sig['coste_oro']:,} (disponible: {oro_banco:,})\n"

    if cfg_sig["requisitos_items"]:
        texto += "📦 Materiales del banco:\n"
        for mat, cant_req in cfg_sig["requisitos_items"].items():
            actual = banco_materiales.get(mat, 0)
            ok = "✅" if actual >= cant_req else "❌"
            texto += f"  {ok} {mat}: {actual}/{cant_req}\n"

    botones = []
    if _es_lider_o_oficial(user_id, gremio_id):
        botones.append([InlineKeyboardButton("⬆️ Subir de nivel", callback_data=f"gremio_subir_{gremio_id}")])
    botones.append([InlineKeyboardButton("💰 Depositar materiales", callback_data=f"gremio_depositar_mat_{gremio_id}")])

    await update.effective_message.reply_text(texto, reply_markup=InlineKeyboardMarkup(botones), parse_mode="Markdown")

# ==================== COMANDO /gremio_subir_nivel ====================
async def cmd_gremio_subir_nivel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not _en_ciudad(user_id):
        await update.effective_message.reply_text("🏙️ Las actividades de gremio solo están disponibles en ciudades.")
        return
    gremio = _obtener_gremio_de_jugador(user_id)
    if not gremio:
        await update.effective_message.reply_text("❌ No perteneces a ningún gremio.")
        return

    gremio_id = gremio["id"]
    nivel_actual = _obtener_nivel_gremio(gremio_id)

    if nivel_actual >= NIVEL_MAXIMO:
        await update.effective_message.reply_text("🌟 Tu gremio ya está en el nivel máximo.")
        return

    if not _es_lider_o_oficial(user_id, gremio_id):
        await update.effective_message.reply_text("❌ Solo el líder u oficiales pueden subir el nivel del gremio.")
        return

    siguiente = nivel_actual + 1
    cfg_sig = NIVELES_GREMIO[siguiente]

    # Verificar oro
    coste_oro = cfg_sig["coste_oro"]
    if _oro_banco_gremio(gremio_id) < coste_oro:
        falta = coste_oro - _oro_banco_gremio(gremio_id)
        await update.effective_message.reply_text(
            f"❌ El banco del gremio no tiene suficiente oro.\n"
            f"Necesario: {coste_oro:,} | Disponible: {_oro_banco_gremio(gremio_id):,}\n"
            f"Faltan: {falta:,} oro"
        )
        return

    # Verificar materiales
    banco_mat = _obtener_materiales_banco(gremio_id)
    faltantes = []
    for mat, cant_req in cfg_sig["requisitos_items"].items():
        if banco_mat.get(mat, 0) < cant_req:
            faltantes.append(f"{mat}: {banco_mat.get(mat,0)}/{cant_req}")
    if faltantes:
        await update.effective_message.reply_text(
            f"❌ Materiales insuficientes en el banco del gremio:\n" +
            "\n".join(f"• {f}" for f in faltantes)
        )
        return

    # Consumir recursos
    _gastar_oro_banco(gremio_id, coste_oro)
    _consumir_materiales(gremio_id, cfg_sig["requisitos_items"])
    _set_nivel_gremio(gremio_id, siguiente)

    cfg_nuevo = NIVELES_GREMIO[siguiente]

    # Notificar a todos los miembros
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT jugador_id FROM miembros_gremio WHERE gremio_id = ?', (gremio_id,))
    miembros = [r[0] for r in c.fetchall()]
    conn.close()
    for mid in miembros:
        db_helper.agregar_notificacion(mid,
            f"🎉 ¡El gremio {gremio['nombre']} subió al nivel {siguiente}!\n"
            f"Nueva capacidad: {cfg_nuevo['capacidad']} miembros.\n"
            f"{cfg_nuevo['descripcion']}"
        )

    await update.effective_message.reply_text(
        f"🎉 *¡EL GREMIO SUBIÓ AL NIVEL {siguiente}!*\n\n"
        f"🏛️ {gremio['nombre']}\n"
        f"👥 Nueva capacidad: {cfg_nuevo['capacidad']} miembros\n"
        f"📜 {cfg_nuevo['descripcion']}\n\n"
        f"*Nuevas bonificaciones:*\n"
        f"• XP: +{cfg_nuevo['bonificaciones']['xp_bonus']}%\n"
        f"• Oro: +{cfg_nuevo['bonificaciones']['oro_bonus']}%\n"
        f"• Stamina extra: +{cfg_nuevo['bonificaciones']['stamina_bonus']}\n"
        f"• Descuento crafteo: -{cfg_nuevo['bonificaciones']['crafting_descuento']}%",
        parse_mode="Markdown"
    )

# ==================== COMANDO /gremio_bonificaciones ====================
async def cmd_gremio_bonificaciones(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not _en_ciudad(user_id):
        await update.effective_message.reply_text("🏙️ Las actividades de gremio solo están disponibles en ciudades.")
        return
    gremio = _obtener_gremio_de_jugador(user_id)
    if not gremio:
        await update.effective_message.reply_text("❌ No perteneces a ningún gremio.")
        return

    nivel = _obtener_nivel_gremio(gremio["id"])
    cfg = NIVELES_GREMIO[nivel]
    bon = cfg["bonificaciones"]

    await update.effective_message.reply_text(
        f"📊 *Bonificaciones del gremio {gremio['nombre']} (Nivel {nivel}):*\n\n"
        f"⚡ XP extra en mazmorras: +{bon['xp_bonus']}%\n"
        f"🪙 Oro extra en mazmorras: +{bon['oro_bonus']}%\n"
        f"💪 Stamina extra: +{bon['stamina_bonus']}\n"
        f"🔨 Descuento en crafteo: -{bon['crafting_descuento']}%\n\n"
        f"📜 {cfg['descripcion']}",
        parse_mode="Markdown"
    )

# ==================== COMANDO /gremio_depositar_material ====================
async def cmd_gremio_depositar_material(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Uso: /gremio_depositar_material <material> <cantidad>"""
    user_id = update.effective_user.id
    if not _en_ciudad(user_id):
        await update.effective_message.reply_text("🏙️ Las actividades de gremio solo están disponibles en ciudades.")
        return
    gremio = _obtener_gremio_de_jugador(user_id)
    if not gremio:
        await update.effective_message.reply_text("❌ No perteneces a ningún gremio.")
        return

    if len(context.args) < 2:
        await update.effective_message.reply_text("Uso: /gremio_depositar_material <nombre_material> <cantidad>")
        return

    material = context.args[0].replace("_", " ")
    try:
        cantidad = int(context.args[1])
    except ValueError:
        await update.effective_message.reply_text("La cantidad debe ser un número.")
        return

    if cantidad <= 0:
        await update.effective_message.reply_text("La cantidad debe ser positiva.")
        return

    # Quitar del inventario del jugador
    ok = db_helper.quitar_item(user_id, material, cantidad)
    if not ok:
        await update.effective_message.reply_text(f"❌ No tienes {cantidad}x {material} en tu inventario.")
        return

    _depositar_material_banco(gremio["id"], material, cantidad)
    await update.effective_message.reply_text(
        f"✅ Depositaste {cantidad}x *{material}* en el banco de materiales del gremio.",
        parse_mode="Markdown"
    )

# ==================== ADMIN: FORZAR NIVEL ====================
async def cmd_admin_gremio_forzar_nivel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not sa._es_admin(user_id):
        await update.effective_message.reply_text("❌ Sin permiso de administrador.")
        return

    if len(context.args) < 2:
        await update.effective_message.reply_text("Uso: /admin_gremio_forzar_nivel <gremio_id> <nivel (1-10)>")
        return

    try:
        gremio_id = int(context.args[0])
        nivel = int(context.args[1])
    except ValueError:
        await update.effective_message.reply_text("Valores inválidos.")
        return

    if nivel < 1 or nivel > NIVEL_MAXIMO:
        await update.effective_message.reply_text(f"El nivel debe estar entre 1 y {NIVEL_MAXIMO}.")
        return

    _set_nivel_gremio(gremio_id, nivel)
    cfg = NIVELES_GREMIO[nivel]
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT nombre FROM gremios WHERE id = ?', (gremio_id,))
    row = c.fetchone()
    nombre = row[0] if row else f"Gremio {gremio_id}"
    conn.close()

    await update.effective_message.reply_text(
        f"✅ Gremio '{nombre}' (ID:{gremio_id}) forzado al nivel {nivel}.\n"
        f"Nueva capacidad: {cfg['capacidad']} miembros."
    )

# ==================== CALLBACKS ====================
async def cb_gremio_subir(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Botón ⬆️ Subir de nivel — replica la lógica de cmd_gremio_subir_nivel sobre el mensaje del query."""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    try:
        gremio_id = int(query.data.split("_")[-1])
    except (ValueError, IndexError):
        return

    gremio = _obtener_gremio_de_jugador(user_id)
    if not gremio or gremio["id"] != gremio_id:
        await query.edit_message_text("❌ Ya no perteneces a ese gremio.")
        return

    nivel_actual = _obtener_nivel_gremio(gremio_id)
    if nivel_actual >= NIVEL_MAXIMO:
        await query.edit_message_text("🌟 Tu gremio ya está en el nivel máximo.")
        return
    if not _es_lider_o_oficial(user_id, gremio_id):
        await query.edit_message_text("❌ Solo el líder u oficiales pueden subir el nivel del gremio.")
        return

    siguiente = nivel_actual + 1
    cfg_sig = NIVELES_GREMIO[siguiente]

    if _oro_banco_gremio(gremio_id) < cfg_sig["coste_oro"]:
        falta = cfg_sig["coste_oro"] - _oro_banco_gremio(gremio_id)
        await query.edit_message_text(
            f"❌ Oro insuficiente en el banco.\nNecesario: {cfg_sig['coste_oro']:,} | Faltan: {falta:,}"
        )
        return

    banco_mat = _obtener_materiales_banco(gremio_id)
    faltantes = [
        f"{mat}: {banco_mat.get(mat,0)}/{cant}"
        for mat, cant in cfg_sig["requisitos_items"].items()
        if banco_mat.get(mat, 0) < cant
    ]
    if faltantes:
        await query.edit_message_text(
            "❌ Materiales insuficientes en el banco:\n" + "\n".join(f"• {f}" for f in faltantes)
        )
        return

    _gastar_oro_banco(gremio_id, cfg_sig["coste_oro"])
    _consumir_materiales(gremio_id, cfg_sig["requisitos_items"])
    _set_nivel_gremio(gremio_id, siguiente)
    cfg_nuevo = NIVELES_GREMIO[siguiente]

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT jugador_id FROM miembros_gremio WHERE gremio_id = ?', (gremio_id,))
    miembros = [r[0] for r in c.fetchall()]
    conn.close()
    for mid in miembros:
        db_helper.agregar_notificacion(mid,
            f"🎉 ¡El gremio {gremio['nombre']} subió al nivel {siguiente}!\n"
            f"Nueva capacidad: {cfg_nuevo['capacidad']} miembros | Baúl: {cfg_nuevo['limite_baul']} slots.\n"
            f"{cfg_nuevo['descripcion']}"
        )

    await query.edit_message_text(
        f"🎉 *¡EL GREMIO SUBIÓ AL NIVEL {siguiente}!*\n\n"
        f"🏛️ {gremio['nombre']}\n"
        f"👥 Nueva capacidad: {cfg_nuevo['capacidad']} miembros\n"
        f"📦 Baúl: {cfg_nuevo['limite_baul']} slots\n"
        f"📜 {cfg_nuevo['descripcion']}\n\n"
        f"*Nuevas bonificaciones:*\n"
        f"• XP: +{cfg_nuevo['bonificaciones']['xp_bonus']}%\n"
        f"• Oro: +{cfg_nuevo['bonificaciones']['oro_bonus']}%\n"
        f"• Stamina extra: +{cfg_nuevo['bonificaciones']['stamina_bonus']}\n"
        f"• Descuento crafteo: -{cfg_nuevo['bonificaciones']['crafting_descuento']}%",
        parse_mode="Markdown"
    )

# ==================== ADMIN: PANEL DE NIVELES ====================
async def cmd_panel_gremio_niveles(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Panel interactivo para ver y editar configuración por nivel."""
    user_id = update.effective_user.id
    if not sa._es_admin(user_id):
        await update.effective_message.reply_text("❌ Sin permiso de administrador.")
        return
    await _mostrar_panel_niveles(update.effective_message, nivel=1, editar=False)

async def _mostrar_panel_niveles(msg, nivel: int, editar: bool):
    cfg = NIVELES_GREMIO.get(nivel, NIVELES_GREMIO[1])
    bon = cfg["bonificaciones"]
    texto = (
        f"🏛️ <b>Configuración — Nivel {nivel}</b>\n\n"
        f"👥 Capacidad miembros: <b>{cfg['capacidad']}</b>\n"
        f"📦 Límite baúl (slots): <b>{cfg['limite_baul']}</b>\n"
        f"🪙 Coste oro banco: <b>{cfg['coste_oro']:,}</b>\n\n"
        f"<b>Bonificaciones:</b>\n"
        f"  ⚡ XP: +{bon['xp_bonus']}%\n"
        f"  💰 Oro: +{bon['oro_bonus']}%\n"
        f"  💪 Stamina: +{bon['stamina_bonus']}\n"
        f"  🔨 Crafteo: -{bon['crafting_descuento']}%\n\n"
        f"<b>Requisitos para subir A este nivel:</b>\n"
    )
    if cfg["requisitos_items"]:
        for mat, cant in cfg["requisitos_items"].items():
            texto += f"  • {mat}: {cant}\n"
    else:
        texto += "  (ninguno — nivel inicial)\n"
    texto += f"\n📜 {cfg['descripcion']}"

    filas = []
    nav = []
    if nivel > 1:
        nav.append(InlineKeyboardButton("◀️", callback_data=f"gnpanel_nav_{nivel-1}"))
    nav.append(InlineKeyboardButton(f"Nv {nivel}/{NIVEL_MAXIMO}", callback_data="gnpanel_noop"))
    if nivel < NIVEL_MAXIMO:
        nav.append(InlineKeyboardButton("▶️", callback_data=f"gnpanel_nav_{nivel+1}"))
    filas.append(nav)
    filas.append([
        InlineKeyboardButton("✏️ Capacidad",  callback_data=f"gnpanel_edit_{nivel}_capacidad"),
        InlineKeyboardButton("✏️ Límite baúl", callback_data=f"gnpanel_edit_{nivel}_limite_baul"),
    ])
    filas.append([
        InlineKeyboardButton("✏️ Coste oro",  callback_data=f"gnpanel_edit_{nivel}_coste_oro"),
        InlineKeyboardButton("✏️ XP bonus",   callback_data=f"gnpanel_edit_{nivel}_xp_bonus"),
    ])
    filas.append([
        InlineKeyboardButton("✏️ Oro bonus",      callback_data=f"gnpanel_edit_{nivel}_oro_bonus"),
        InlineKeyboardButton("✏️ Stamina bonus",  callback_data=f"gnpanel_edit_{nivel}_stamina_bonus"),
    ])
    filas.append([
        InlineKeyboardButton("✏️ Desc. crafteo", callback_data=f"gnpanel_edit_{nivel}_crafting_descuento"),
    ])

    kb = InlineKeyboardMarkup(filas)
    try:
        await msg.edit_text(texto, reply_markup=kb, parse_mode="HTML")
    except Exception:
        await msg.reply_text(texto, reply_markup=kb, parse_mode="HTML")

async def cb_gnpanel_nav(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        nivel = int(query.data.split("_")[-1])
    except (ValueError, IndexError):
        return
    await _mostrar_panel_niveles(query.message, nivel=nivel, editar=False)

async def cb_gnpanel_noop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()

async def cb_gnpanel_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    if not sa._es_admin(user_id):
        return
    parts = query.data.split("_")
    # formato: gnpanel_edit_<nivel>_<campo>
    try:
        nivel = int(parts[2])
        campo = parts[3]
    except (IndexError, ValueError):
        return
    context.user_data["gnpanel_nivel"] = nivel
    context.user_data["gnpanel_campo"] = campo
    nombres = {
        "capacidad": "capacidad máxima de miembros",
        "limite_baul": "límite de slots del baúl",
        "coste_oro": "coste en oro del banco",
        "xp_bonus": "bonus de XP (%)",
        "oro_bonus": "bonus de oro (%)",
        "stamina_bonus": "stamina extra",
        "crafting_descuento": "descuento de crafteo (%)",
    }
    await query.edit_message_text(
        f"✏️ <b>Editando nivel {nivel}</b> — {nombres.get(campo, campo)}\n\n"
        f"Envía el nuevo valor numérico:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ Cancelar", callback_data=f"gnpanel_cancelar_{nivel}")
        ]])
    )

async def cb_gnpanel_cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        nivel = int(query.data.split("_")[-1])
    except (ValueError, IndexError):
        nivel = 1
    context.user_data.pop("gnpanel_nivel", None)
    context.user_data.pop("gnpanel_campo", None)
    await _mostrar_panel_niveles(query.message, nivel=nivel, editar=False)

async def _gnpanel_recibir_valor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recibe el valor numérico para editar un campo del nivel."""
    user_id = update.effective_user.id
    if not sa._es_admin(user_id):
        return
    nivel = context.user_data.get("gnpanel_nivel")
    campo = context.user_data.get("gnpanel_campo")
    if nivel is None or campo is None:
        return
    # Guard: si el texto es un botón del teclado rápido, no interferir
    try:
        from teclado_rapido import _MAPA_NORM, _FE0F
        texto_norm = (update.message.text or "").strip().replace(_FE0F, "")
        if texto_norm in _MAPA_NORM:
            return
    except Exception:
        pass

    try:
        valor = int(update.message.text.strip())
        if valor < 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Valor inválido. Debe ser un número entero positivo.")
        return

    cfg = NIVELES_GREMIO.get(nivel)
    if cfg is None:
        await update.message.reply_text(f"❌ Nivel {nivel} no existe.")
        return

    campos_bon = {"xp_bonus", "oro_bonus", "stamina_bonus", "crafting_descuento"}
    if campo in campos_bon:
        cfg["bonificaciones"][campo] = valor
    elif campo in ("capacidad", "limite_baul", "coste_oro"):
        cfg[campo] = valor
    else:
        await update.message.reply_text(f"❌ Campo desconocido: {campo}")
        return

    context.user_data.pop("gnpanel_nivel", None)
    context.user_data.pop("gnpanel_campo", None)
    await update.message.reply_text(
        f"✅ Nivel {nivel} → <b>{campo}</b> actualizado a <b>{valor}</b>.\n"
        f"(Cambio en memoria; se aplica hasta reinicio del bot.)",
        parse_mode="HTML"
    )
    # Mostrar panel actualizado
    await _mostrar_panel_niveles(update.message, nivel=nivel, editar=False)

# ==================== ADMIN: EDITAR NIVEL POR COMANDO ====================
async def cmd_admin_gremio_config_nivel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Uso: /admin_gremio_config_nivel <nivel> <campo> <valor>
    Campos: capacidad | limite_baul | coste_oro | xp_bonus | oro_bonus | stamina_bonus | crafting_descuento
    """
    user_id = update.effective_user.id
    if not sa._es_admin(user_id):
        await update.effective_message.reply_text("❌ Sin permiso de administrador.")
        return
    if len(context.args) < 3:
        await update.effective_message.reply_text(
            "Uso: /admin_gremio_config_nivel <nivel 1-10> <campo> <valor>\n\n"
            "Campos disponibles:\n"
            "  capacidad | limite_baul | coste_oro\n"
            "  xp_bonus | oro_bonus | stamina_bonus | crafting_descuento"
        )
        return
    try:
        nivel = int(context.args[0])
        campo = context.args[1]
        valor = int(context.args[2])
        if valor < 0 or nivel < 1 or nivel > NIVEL_MAXIMO:
            raise ValueError
    except ValueError:
        await update.effective_message.reply_text("❌ Parámetros inválidos.")
        return

    cfg = NIVELES_GREMIO.get(nivel)
    if cfg is None:
        await update.effective_message.reply_text(f"❌ Nivel {nivel} no existe.")
        return

    campos_bon = {"xp_bonus", "oro_bonus", "stamina_bonus", "crafting_descuento"}
    if campo in campos_bon:
        cfg["bonificaciones"][campo] = valor
    elif campo in ("capacidad", "limite_baul", "coste_oro"):
        cfg[campo] = valor
    else:
        await update.effective_message.reply_text(
            f"❌ Campo '{campo}' desconocido.\n"
            "Campos válidos: capacidad, limite_baul, coste_oro, xp_bonus, oro_bonus, stamina_bonus, crafting_descuento"
        )
        return

    await update.effective_message.reply_text(
        f"✅ Nivel {nivel} → <b>{campo}</b> = <b>{valor}</b>.\n"
        f"⚠️ El cambio es en memoria y se aplica hasta el próximo reinicio del bot.",
        parse_mode="HTML"
    )

# ==================== REGISTRO DE HANDLERS ====================
def registrar_handlers(app):
    app.add_handler(CommandHandler("gremio_nivel",                  cmd_gremio_nivel))
    app.add_handler(CommandHandler("gremio_subir_nivel",            cmd_gremio_subir_nivel))
    app.add_handler(CommandHandler("gremio_bonificaciones",         cmd_gremio_bonificaciones))
    app.add_handler(CommandHandler("gremio_depositar_material",     cmd_gremio_depositar_material))
    app.add_handler(CommandHandler("admin_gremio_forzar_nivel",     cmd_admin_gremio_forzar_nivel))
    app.add_handler(CommandHandler("panel_gremio_niveles",          cmd_panel_gremio_niveles))
    app.add_handler(CommandHandler("admin_gremio_config_nivel",     cmd_admin_gremio_config_nivel))
    app.add_handler(CallbackQueryHandler(cb_gremio_subir,           pattern=r"^gremio_subir_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_gnpanel_nav,            pattern=r"^gnpanel_nav_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_gnpanel_noop,           pattern=r"^gnpanel_noop$"))
    app.add_handler(CallbackQueryHandler(cb_gnpanel_edit,           pattern=r"^gnpanel_edit_\d+_\w+$"))
    app.add_handler(CallbackQueryHandler(cb_gnpanel_cancelar,       pattern=r"^gnpanel_cancelar_\d+$"))
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        _gnpanel_recibir_valor
    ), group=5)

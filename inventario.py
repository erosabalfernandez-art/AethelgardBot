#!/usr/bin/env python3
# inventario.py
# Sistema de inventario y equipamiento para Aethelgard.
# Proporciona funciones para equipar, desequipar, usar consumibles,
# calcular bonos de equipo y gestionar el peso.

import sqlite3
import json
import random
import html as _html
from typing import Dict, List, Optional, Tuple

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters

import db_helper
import economia
import clases

DB_PATH = "aethelgard.db"

# ==================== TABLAS ====================
def _init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Tabla de equipamiento (lo que lleva puesto el jugador)
    c.execute('''CREATE TABLE IF NOT EXISTS equipamiento (
        user_id INTEGER PRIMARY KEY,
        arma TEXT,
        armadura TEXT,
        casco TEXT,
        botas TEXT,
        guantes TEXT,
        accesorio1 TEXT,
        accesorio2 TEXT,
        montura TEXT
    )''')
    conn.commit()
    conn.close()

_init_db()

# ==================== FUNCIONES DE PESO ====================
def _obtener_peso_objeto(nombre_objeto: str) -> float:
    """Devuelve el peso de un objeto, basado en su nombre (provisional).
       Si se dispone de los diccionarios reales, se podría leer de allí."""
    nombre = nombre_objeto.lower()
    # Intentar obtener de diccionarios de objetos reales si están disponibles
    try:
        from armas import ARMAS
        from armaduras import ARMADURAS
        from pociones import POCIONES
        from materiales import MATERIALES
        if nombre_objeto in ARMAS:
            return ARMAS[nombre_objeto].get("peso", 1.0)
        if nombre_objeto in ARMADURAS:
            return ARMADURAS[nombre_objeto].get("peso", 1.0)
        if nombre_objeto in POCIONES:
            return POCIONES[nombre_objeto].get("peso", 0.2)
        if nombre_objeto in MATERIALES:
            return MATERIALES[nombre_objeto].get("peso", 1.0)
    except ImportError:
        pass
    # Fallback por nombre
    if "pocion" in nombre:
        return 0.2
    if "comida" in nombre or "pan" in nombre or "pescado" in nombre:
        return 0.5
    if "hacha" in nombre or "pico" in nombre or "caña" in nombre:
        return 2.0
    if "mineral" in nombre or "madera" in nombre or "piel" in nombre:
        return 1.0
    if "daga" in nombre or "arco" in nombre or "baston" in nombre:
        return 2.5
    if "espada" in nombre or "hacha" in nombre or "maza" in nombre:
        return 5.0
    if "pechera" in nombre or "armadura" in nombre:
        return 8.0
    if "casco" in nombre or "yelmo" in nombre:
        return 3.0
    if "botas" in nombre:
        return 2.0
    if "guantes" in nombre:
        return 1.5
    if "anillo" in nombre or "amuleto" in nombre:
        return 0.5
    if "caballo" in nombre or "lobo" in nombre or "corcel" in nombre:
        return 20.0
    return 1.0

def _obtener_estadisticas_objeto(nombre_objeto: str) -> Dict[str, int]:
    """
    Devuelve las estadísticas que aporta un objeto equipable.
    Lee de los diccionarios reales si están disponibles.
    """
    try:
        from armas import ARMAS
        from armaduras import ARMADURAS
        from pociones import POCIONES
        if nombre_objeto in ARMAS:
            data = ARMAS[nombre_objeto]
            return {
                "daño": data.get("daño", 0),
                "vida": data.get("vida_extra", 0),
                "defensa": data.get("defensa_extra", 0),
                "critico": data.get("critico", 0),
                "velocidad": data.get("velocidad", 0)
            }
        if nombre_objeto in ARMADURAS:
            data = ARMADURAS[nombre_objeto]
            return {
                "defensa": data.get("defensa", 0) + data.get("defensa_extra", 0),
                "vida": data.get("vida_extra", 0),
                "velocidad": data.get("velocidad_movimiento", 0),
                "critico": data.get("resistencia_critico", 0)
            }
        if nombre_objeto in POCIONES:
            return {}  # las pociones no dan stats equipables
    except ImportError:
        pass
    # Fallback por nombre
    nombre = nombre_objeto.lower()
    if "espada" in nombre:
        return {"daño": 15, "vida": 10}
    if "hacha" in nombre:
        return {"daño": 20, "defensa": -2}
    if "daga" in nombre:
        return {"daño": 12, "critico": 5}
    if "arco" in nombre:
        return {"daño": 14, "velocidad": 5}
    if "baston" in nombre:
        return {"daño": 18, "vida": 20}
    if "pechera" in nombre:
        return {"defensa": 15, "vida": 30}
    if "casco" in nombre:
        return {"defensa": 8, "vida": 5}
    if "botas" in nombre:
        return {"defensa": 5, "velocidad": 10}
    if "guantes" in nombre:
        return {"defensa": 4, "daño": 5}
    if "anillo" in nombre:
        return {"vida": 20, "daño": 3}
    if "amuleto" in nombre:
        return {"defensa": 5, "vida": 10}
    if "caballo" in nombre or "lobo" in nombre or "corcel" in nombre:
        return {"velocidad": 30}
    return {}

# ==================== EQUIPAMIENTO ====================
def obtener_equipamiento(user_id: int) -> Dict[str, Optional[str]]:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT arma, armadura, casco, botas, guantes, accesorio1, accesorio2, montura FROM equipamiento WHERE user_id = ?', (user_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return {
            "arma": row[0], "armadura": row[1], "casco": row[2],
            "botas": row[3], "guantes": row[4], "accesorio1": row[5],
            "accesorio2": row[6], "montura": row[7]
        }
    return {k: None for k in ["arma", "armadura", "casco", "botas", "guantes", "accesorio1", "accesorio2", "montura"]}

def guardar_equipamiento(user_id: int, equip: Dict[str, Optional[str]]):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT OR REPLACE INTO equipamiento (user_id, arma, armadura, casco, botas, guantes, accesorio1, accesorio2, montura)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
              (user_id, equip["arma"], equip["armadura"], equip["casco"], equip["botas"],
               equip["guantes"], equip["accesorio1"], equip["accesorio2"], equip["montura"]))
    conn.commit()
    conn.close()

def equipar(user_id: int, nombre_objeto: str) -> Tuple[bool, str]:
    """Equipa un objeto desde el inventario."""
    inv = db_helper.obtener_inventario(user_id)
    item = next((it for it in inv if it["nombre"] == nombre_objeto), None)
    if not item:
        return False, "No tienes ese objeto en tu inventario."
    # Determinar ranura según tipo (simple por palabras clave)
    nombre_lower = nombre_objeto.lower()
    if "espada" in nombre_lower or "hacha" in nombre_lower or "daga" in nombre_lower or "arco" in nombre_lower or "baston" in nombre_lower:
        ranura = "arma"
    elif "pechera" in nombre_lower or "armadura" in nombre_lower:
        ranura = "armadura"
    elif "casco" in nombre_lower or "yelmo" in nombre_lower:
        ranura = "casco"
    elif "botas" in nombre_lower:
        ranura = "botas"
    elif "guantes" in nombre_lower:
        ranura = "guantes"
    elif "anillo" in nombre_lower:
        ranura = "accesorio1"
    elif "amuleto" in nombre_lower:
        ranura = "accesorio2"
    elif "caballo" in nombre_lower or "lobo" in nombre_lower or "corcel" in nombre_lower or "montura" in nombre_lower:
        ranura = "montura"
    else:
        return False, "Este objeto no se puede equipar."
    # Desequipar si ya hay algo en esa ranura
    equip = obtener_equipamiento(user_id)
    if equip[ranura]:
        db_helper.agregar_item(user_id, equip[ranura], 1)
    # Equipar nuevo objeto
    equip[ranura] = nombre_objeto
    guardar_equipamiento(user_id, equip)
    db_helper.quitar_item(user_id, nombre_objeto, 1)
    return True, f"✅ Equipaste {nombre_objeto} en {ranura}."

def desequipar(user_id: int, ranura: str) -> Tuple[bool, str]:
    ranuras_validas = ["arma", "armadura", "casco", "botas", "guantes", "accesorio1", "accesorio2", "montura"]
    if ranura not in ranuras_validas:
        return False, "Ranura inválida."
    equip = obtener_equipamiento(user_id)
    objeto = equip.get(ranura)
    if not objeto:
        return False, "No tienes nada equipado en esa ranura."
    db_helper.agregar_item(user_id, objeto, 1)
    equip[ranura] = None
    guardar_equipamiento(user_id, equip)
    return True, f"✅ Desequipaste {objeto} de {ranura}."

def calcular_bonos_equipo(user_id: int) -> Dict[str, int]:
    """Suma las estadísticas de todos los objetos equipados."""
    equip = obtener_equipamiento(user_id)
    bonos = {"vida": 0, "daño": 0, "defensa": 0, "critico": 0, "velocidad": 0}
    for slot, obj in equip.items():
        if obj:
            stats = _obtener_estadisticas_objeto(obj)
            for key, value in stats.items():
                if key in bonos:
                    bonos[key] += value
                else:
                    bonos[key] = bonos.get(key, 0) + value
    return bonos

# ==================== USO DE CONSUMIBLES ====================
def usar_consumible(user_id: int, nombre_objeto: str, cantidad: int = 1) -> Tuple[bool, str]:
    """Usa un consumible y aplica su efecto."""
    inv = db_helper.obtener_inventario(user_id)
    item = next((it for it in inv if it["nombre"] == nombre_objeto), None)
    if not item or item["cantidad"] < cantidad:
        return False, "No tienes suficientes consumibles."
    nombre_lower = nombre_objeto.lower()
    # Efectos según el tipo
    if "pocion_vida" in nombre_lower or "pocion de vida" in nombre_lower or "cura" in nombre_lower:
        # Extraer cantidad de curación de los datos reales si es posible
        try:
            from pociones import POCIONES
            if nombre_objeto in POCIONES:
                efecto = POCIONES[nombre_objeto].get("efecto", "")
                import re
                numeros = re.findall(r'\d+', efecto)
                cura = int(numeros[0]) if numeros else 30
            else:
                cura = 30
        except:
            cura = 30
        jug = db_helper.obtener_jugador(user_id)
        if not jug:
            return False, "❌ Error al acceder a tus estadísticas."
        nueva_vida = min(jug["hp_max"], jug["hp_actual"] + cura)
        db_helper.actualizar_jugador(user_id, hp_actual=nueva_vida)
        db_helper.quitar_item(user_id, nombre_objeto, cantidad)
        return True, f"🧪 Usaste {nombre_objeto} y recuperaste {cura} HP."
    elif "pocion_mana" in nombre_lower or "mana" in nombre_lower:
        # Simulación de maná (si no existe campo, se puede agregar)
        db_helper.quitar_item(user_id, nombre_objeto, cantidad)
        return True, f"💧 Usaste {nombre_objeto} y recuperaste maná."
    elif "pocion_experiencia" in nombre_lower or "experiencia" in nombre_lower:
        # Sumar experiencia (pendiente de implementar función)
        db_helper.quitar_item(user_id, nombre_objeto, cantidad)
        return True, f"✨ Usaste {nombre_objeto} y ganaste experiencia."
    elif "comida" in nombre_lower or "pan" in nombre_lower or "pescado" in nombre_lower:
        # Buff temporal (simplificado)
        db_helper.quitar_item(user_id, nombre_objeto, cantidad)
        return True, f"🍽️ Comiste {nombre_objeto}. Te sientes más fuerte (buff temporal)."
    else:
        return False, "No se puede usar ese objeto."

# ==================== CLASIFICACIÓN DE INVENTARIO ====================
def clasificar_inventario(user_id: int) -> Dict[str, List[Dict]]:
    inv = db_helper.obtener_inventario(user_id)
    equip_actual = obtener_equipamiento(user_id)
    normales = []
    consumibles = []
    mejoras = []
    equipables = []
    for item in inv:
        nombre = item["nombre"]
        nombre_lower = nombre.lower()
        if "pocion" in nombre_lower or "comida" in nombre_lower or "pan" in nombre_lower or "pescado" in nombre_lower:
            consumibles.append(item)
        elif "gema" in nombre_lower or "mejora" in nombre_lower or "encantamiento" in nombre_lower:
            mejoras.append(item)
        elif any(x in nombre_lower for x in ["espada", "hacha", "daga", "arco", "baston", "pechera", "casco", "botas", "guantes", "anillo", "amuleto", "caballo", "lobo", "corcel", "montura"]):
            equipables.append(item)
        else:
            normales.append(item)
    return {
        "equipado": equip_actual,
        "normales": normales,
        "consumibles": consumibles,
        "mejoras": mejoras,
        "equipables": equipables
    }

def _calcular_carga_maxima(user_id: int) -> int:
    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        return 100
    base = 100 + (jug["nivel"] - 1) * 2
    reenc = jug.get("reencarnaciones", 0)
    multiplicador = 1 + reenc * 0.05
    total = int(base * multiplicador)
    if jug["clase"] == "vanguardista":
        total = int(total * 1.5)
    return max(100, total)

def _peso_total(user_id: int, incluir_equipado: bool = True) -> float:
    inv = db_helper.obtener_inventario(user_id)
    peso = sum(_obtener_peso_objeto(item["nombre"]) * item["cantidad"] for item in inv)
    if incluir_equipado:
        equip = obtener_equipamiento(user_id)
        for slot, obj in equip.items():
            if obj:
                peso += _obtener_peso_objeto(obj)
    return peso

# ==================== MANEJADORES DE TELEGRAM ====================
async def cmd_inventario(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    clasif = clasificar_inventario(user_id)
    peso_actual = _peso_total(user_id)
    peso_max = _calcular_carga_maxima(user_id)
    texto = f"🎒 *Inventario*\n⚖️ Peso: {peso_actual:.1f}/{peso_max} kg\n\n"
    keyboard = [
        [InlineKeyboardButton("⚔️ Equipamento", callback_data="inv_equipado"),
         InlineKeyboardButton("🎒 Objetos",      callback_data="inv_normales")],
        [InlineKeyboardButton("🧪 Consumibles",  callback_data="inv_consumibles"),
         InlineKeyboardButton("✨ Mejoras",       callback_data="inv_mejoras")],
        [InlineKeyboardButton("🗡️ Equipar objeto", callback_data="inv_equipables"),
         InlineKeyboardButton("🐴 Monturas",     callback_data="inv_monturas")],
        [InlineKeyboardButton("❌ Cerrar", callback_data="inv_cerrar")]
    ]
    # Botón de Plantillas de Equipo Rápido si tiene membresía
    try:
        import membresia as _mb
        if _mb.tiene_membresia(user_id, "plantillas"):
            keyboard.insert(-1, [InlineKeyboardButton("⚡ Plantillas de Equipo Rápido", callback_data="pt_panel")])
    except Exception:
        pass
    await update.effective_message.reply_text(texto, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    try:
        import misiones as _mis
        _mis.completar_mision(user_id, "ver_inventario", context)
    except Exception:
        pass
    try:
        import guia_contextual as _gc
        await _gc.enviar(user_id, context, "inventario_abierto")
    except Exception:
        pass

async def mostrar_apartado(update: Update, context: ContextTypes.DEFAULT_TYPE, apartado: str = None):
    query = update.callback_query
    await query.answer()
    if apartado is None:
        # Llamado directamente por Telegram como callback: extraer apartado del data
        # Formato: "inv_equipado", "inv_normales", etc. → quitar prefijo "inv_"
        apartado = query.data[4:]  # "inv_equipado" → "equipado"
    user_id = update.effective_user.id
    clasif = clasificar_inventario(user_id)
    def _e(s): return _html.escape(str(s))
    if apartado == "equipado":
        equip = clasif["equipado"]
        texto = "<b>⚔️ Equipamento actual</b>\n"
        for slot, obj in equip.items():
            texto += f"• {_e(slot)}: {_e(obj) if obj else 'Vacío'}\n"
        keyboard = []
        for slot, obj in equip.items():
            if obj:
                keyboard.append([InlineKeyboardButton(f"Desequipar {obj}", callback_data=f"inv_desequipar_{slot}")])
        keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data="inv_volver")])
        await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    elif apartado == "normales":
        items = clasif["normales"]
        if not items:
            await query.edit_message_text(
                "🎒 No tienes objetos normales.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver", callback_data="inv_volver")]])
            )
            return
        texto = "<b>🎒 Objetos normales</b>\n"
        botones = []
        for it in items:
            texto += f"• {_e(it['nombre'])} x{it['cantidad']}\n"
            botones.append([InlineKeyboardButton(f"Soltar {it['nombre']}", callback_data=f"inv_soltar_{it['nombre']}")])
        botones.append([InlineKeyboardButton("🔙 Volver", callback_data="inv_volver")])
        await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(botones), parse_mode="HTML")
    elif apartado == "consumibles":
        items = clasif["consumibles"]
        if not items:
            await query.edit_message_text(
                "🧪 No tienes consumibles.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver", callback_data="inv_volver")]])
            )
            return
        texto = "<b>🧪 Consumibles</b>\n"
        botones = []
        for it in items:
            texto += f"• {_e(it['nombre'])} x{it['cantidad']}\n"
            botones.append([InlineKeyboardButton(f"Usar {it['nombre']}", callback_data=f"inv_usar_{it['nombre']}")])
        botones.append([InlineKeyboardButton("🔙 Volver", callback_data="inv_volver")])
        await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(botones), parse_mode="HTML")
    elif apartado == "mejoras":
        items = clasif["mejoras"]
        if not items:
            await query.edit_message_text(
                "✨ No tienes mejoras.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver", callback_data="inv_volver")]])
            )
            return
        texto = "<b>✨ Mejoras</b>\n"
        botones = []
        for it in items:
            texto += f"• {_e(it['nombre'])} x{it['cantidad']}\n"
            botones.append([InlineKeyboardButton(f"Usar {it['nombre']}", callback_data=f"inv_mejora_{it['nombre']}")])
        botones.append([InlineKeyboardButton("🔙 Volver", callback_data="inv_volver")])
        await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(botones), parse_mode="HTML")
    elif apartado == "equipables":
        items = clasif["equipables"]
        if not items:
            await query.edit_message_text(
                "⚔️ No tienes equipamiento sin equipar.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver", callback_data="inv_volver")]])
            )
            return
        texto = "<b>⚔️ Equipamiento sin equipar</b>\n"
        botones = []
        for it in items:
            texto += f"• {_e(it['nombre'])} x{it['cantidad']}\n"
            botones.append([InlineKeyboardButton(f"Equipar {it['nombre']}", callback_data=f"inv_equipar_{it['nombre']}")])
        botones.append([InlineKeyboardButton("🔙 Volver", callback_data="inv_volver")])
        await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(botones), parse_mode="HTML")

async def procesar_accion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    parts = data.split("_")
    accion = parts[1]
    user_id = update.effective_user.id
    if accion == "desequipar":
        ranura = parts[2]
        ok, msg = desequipar(user_id, ranura)
        await query.edit_message_text(msg)
        await cmd_inventario(update, context)
    elif accion == "soltar":
        nombre = "_".join(parts[2:])
        ok = db_helper.quitar_item(user_id, nombre, 1)
        if not ok:
            await query.edit_message_text(
                f"❌ No se pudo soltar <b>{_html.escape(nombre)}</b>.\nEl objeto no fue encontrado en tu inventario.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver", callback_data="inv_normales")]]),
                parse_mode="HTML"
            )
            return
        quedan = clasificar_inventario(user_id)["normales"]
        if quedan:
            await mostrar_apartado(update, context, "normales")
        else:
            peso_actual = _peso_total(user_id)
            peso_max    = _calcular_carga_maxima(user_id)
            keyboard = [
                [InlineKeyboardButton("⚔️ Equipamento",    callback_data="inv_equipado")],
                [InlineKeyboardButton("🎒 Objetos",         callback_data="inv_normales")],
                [InlineKeyboardButton("🧪 Consumibles",     callback_data="inv_consumibles")],
                [InlineKeyboardButton("✨ Mejoras",          callback_data="inv_mejoras")],
                [InlineKeyboardButton("⚔️ Equipar rápido", callback_data="inv_equipables")],
                [InlineKeyboardButton("❌ Cerrar",           callback_data="inv_cerrar")],
            ]
            await query.edit_message_text(
                f"✅ Soltaste <b>{_html.escape(nombre)}</b>.\n\n"
                f"🎒 <b>Inventario</b>\n⚖️ Peso: {peso_actual:.1f}/{peso_max} kg",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="HTML"
            )
    elif accion == "usar":
        nombre = "_".join(parts[2:])
        ok, msg = usar_consumible(user_id, nombre, 1)
        await query.edit_message_text(msg)
        await mostrar_apartado(update, context, "consumibles")
    elif accion == "mejora":
        nombre = "_".join(parts[2:])
        await query.edit_message_text(f"¿Sobre qué objeto quieres usar {nombre}? (responde con el nombre exacto)")
        context.user_data["mejora_pendiente"] = nombre
        return
    elif accion == "equipar":
        nombre = "_".join(parts[2:])
        ok, msg = equipar(user_id, nombre)
        await query.edit_message_text(msg)
        await mostrar_apartado(update, context, "equipables")
    elif accion == "volver":
        await cmd_inventario(update, context)
    elif accion == "cerrar":
        await query.edit_message_text("🎒 Inventario cerrado.")

async def recibir_objetivo_mejora(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mejora = context.user_data.get("mejora_pendiente")
    if not mejora:
        return
    objetivo = update.message.text.strip()
    user_id = update.effective_user.id
    # Verificar que el objetivo está en el inventario
    inv = db_helper.obtener_inventario(user_id)
    if not any(it["nombre"] == objetivo for it in inv):
        await update.effective_message.reply_text("No tienes ese objeto en tu inventario.")
        context.user_data.pop("mejora_pendiente", None)
        return
    # Aplicar mejora (cambiar nombre agregando sufijo _mejorado)
    db_helper.quitar_item(user_id, objetivo, 1)
    nuevo_nombre = f"{objetivo}_mejorado"
    db_helper.agregar_item(user_id, nuevo_nombre, 1)
    db_helper.quitar_item(user_id, mejora, 1)
    await update.effective_message.reply_text(f"✨ Aplicaste {mejora} a {objetivo}. Ahora es {nuevo_nombre}.")
    context.user_data.pop("mejora_pendiente", None)
    await cmd_inventario(update, context)

# ==================== PANEL DE MONTURAS ====================

def _teclado_inventario_principal(user_id: int = 0):
    filas = [
        [InlineKeyboardButton("⚔️ Equipamento", callback_data="inv_equipado"),
         InlineKeyboardButton("🎒 Objetos",      callback_data="inv_normales")],
        [InlineKeyboardButton("🧪 Consumibles",  callback_data="inv_consumibles"),
         InlineKeyboardButton("✨ Mejoras",       callback_data="inv_mejoras")],
        [InlineKeyboardButton("🗡️ Equipar objeto", callback_data="inv_equipables"),
         InlineKeyboardButton("🐴 Monturas",     callback_data="inv_monturas")],
        [InlineKeyboardButton("❌ Cerrar",        callback_data="inv_cerrar")],
    ]
    if user_id:
        try:
            import membresia as _mb
            if _mb.tiene_membresia(user_id, "plantillas"):
                filas.insert(-1, [InlineKeyboardButton("⚡ Plantillas de Equipo Rápido", callback_data="pt_panel")])
        except Exception:
            pass
    return InlineKeyboardMarkup(filas)

async def mostrar_monturas_inv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Panel de monturas en el inventario: lista todas las que posee el jugador."""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    try:
        import sqlite3 as _s
        from monturas import MONTURAS as _MON
        import viajes as _viajes
        montura_activa = _viajes._obtener_montura_activa(user_id)
        mid_activa = montura_activa["montura_id"] if montura_activa else None

        conn = _s.connect(DB_PATH)
        c = conn.cursor()
        c.execute(
            "SELECT montura_id, expira FROM inventario_monturas WHERE user_id = ? AND cantidad > 0",
            (user_id,)
        )
        rows = c.fetchall()
        conn.close()
    except Exception as e:
        await query.edit_message_text(f"❌ Error al cargar monturas: {e}")
        return

    if not rows:
        await query.edit_message_text(
            "🐴 <b>Tus Monturas</b>\n\nNo tienes ninguna montura.\nCómpralas en la Tienda → Comercio.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver", callback_data="inv_volver")]]),
            parse_mode="HTML"
        )
        return

    try:
        from monturas import MONTURAS as _MON
    except ImportError:
        _MON = {}

    texto = "🐴 <b>Tus Monturas</b>\nPulsa una para ver sus stats.\n\n"
    botones = []
    for mid, expira in rows:
        datos = _MON.get(mid, {})
        nombre = _html.escape(datos.get("nombre", mid))
        activa = (mid == mid_activa)
        tipo_str = expira if expira else "permanente"
        badge = " ✅ <b>[EQUIPADA]</b>" if activa else ""
        texto += f"• {nombre}{badge}\n"
        label = f"{'✅ ' if activa else '🐴 '}{datos.get('nombre', mid)}"
        if len(label) > 60:
            label = label[:57] + "..."
        botones.append([InlineKeyboardButton(label, callback_data=f"inv_mdet_{mid}")])

    botones.append([InlineKeyboardButton("🔙 Volver", callback_data="inv_volver")])
    await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(botones), parse_mode="HTML")


async def montura_detalle_inv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra stats completos de una montura y botones para equipar/desmontar."""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    mid = query.data[len("inv_mdet_"):]

    try:
        from monturas import MONTURAS as _MON
        import viajes as _viajes
        datos = _MON.get(mid)
        if not datos:
            await query.edit_message_text("❌ Montura no encontrada en el catálogo.")
            return

        montura_activa = _viajes._obtener_montura_activa(user_id)
        mid_activa = montura_activa["montura_id"] if montura_activa else None
        es_activa = (mid == mid_activa)

        import sqlite3 as _s
        conn = _s.connect(DB_PATH)
        c = conn.cursor()
        c.execute(
            "SELECT expira FROM inventario_monturas WHERE user_id = ? AND montura_id = ? AND cantidad > 0",
            (user_id, mid)
        )
        row = c.fetchone()
        conn.close()
        if not row:
            await query.edit_message_text("❌ No tienes esa montura en tu inventario.")
            return
        expira = row[0]
    except Exception as e:
        await query.edit_message_text(f"❌ Error: {e}")
        return

    nombre    = _html.escape(datos.get("nombre", mid))
    subtipo   = datos.get("subtipo", "?").capitalize()
    zona      = datos.get("zona", "?").capitalize()
    calidad   = datos.get("calidad", "?").capitalize()
    rareza    = datos.get("rareza", 1)
    vel       = datos.get("velocidad", 0)
    carga     = datos.get("carga", 0)
    sigilo    = datos.get("sigilo", 0)
    defensa   = datos.get("defensa", 0)
    ataque    = datos.get("ataque", 0)
    nivel_req = datos.get("nivel_requerido", 1)
    desc      = _html.escape(datos.get("descripcion", ""))
    duracion  = "Permanente" if not expira else f"Temporal (expira: {expira[:10]})"
    estrellas = "⭐" * rareza

    texto  = f"🐴 <b>{nombre}</b> {estrellas}\n"
    texto += f"🦁 Tipo: <b>{subtipo}</b>  •  🌐 Zona: <b>{zona}</b>\n"
    texto += f"💎 Calidad: <b>{calidad}</b>  •  🎯 Nivel mín: <b>{nivel_req}</b>\n"
    texto += f"📋 Duración: <b>{duracion}</b>\n\n"
    texto += "<b>📊 Stats:</b>\n"
    texto += f"  ⚡ Velocidad viaje: <b>+{vel}%</b>\n"
    texto += f"  🎒 Carga extra: <b>+{carga} kg</b>\n"
    if ataque:
        texto += f"  ⚔️ Ataque: <b>+{ataque}</b>\n"
    if defensa:
        texto += f"  🛡️ Defensa: <b>+{defensa}</b>\n"
    if sigilo:
        texto += f"  👁️ Sigilo: <b>+{sigilo}</b>\n"
    if desc:
        texto += f"\n💬 {desc}"

    botones = []
    if es_activa:
        texto += "\n\n✅ <b>Esta montura está equipada actualmente.</b>"
        botones.append([InlineKeyboardButton("🔴 Desmontar (ir a pie)", callback_data="inv_mdesmontar")])
    else:
        botones.append([InlineKeyboardButton("✅ Equipar esta montura", callback_data=f"inv_mequipar_{mid}")])
        if mid_activa:
            botones.append([InlineKeyboardButton("🔴 Desmontar la activa", callback_data="inv_mdesmontar")])

    botones.append([InlineKeyboardButton("🔙 Volver a Monturas", callback_data="inv_monturas")])
    await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(botones), parse_mode="HTML")


async def montura_accion_inv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Procesa equipar o desmontar desde el panel de inventario."""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    data = query.data

    try:
        import viajes as _viajes
        from monturas import MONTURAS as _MON

        if data.startswith("inv_mequipar_"):
            mid = data[len("inv_mequipar_"):]
            if not _viajes._tiene_montura_en_inventario(user_id, mid):
                await query.answer("❌ No tienes esa montura o ha expirado.", show_alert=True)
                return
            ok = _viajes._equipar_montura(user_id, mid)
            nombre = _MON.get(mid, {}).get("nombre", mid)
            if ok:
                await query.answer(f"✅ {nombre} equipada.", show_alert=True)
            else:
                await query.answer("❌ No se pudo equipar la montura.", show_alert=True)
                return

        elif data == "inv_mdesmontar":
            montura_activa = _viajes._obtener_montura_activa(user_id)
            if not montura_activa:
                await query.answer("No tienes ninguna montura equipada.", show_alert=True)
                return
            _viajes._desmontar(user_id)
            nombre = _MON.get(montura_activa["montura_id"], {}).get("nombre", "montura")
            await query.answer(f"🔴 {nombre} desmontada. Viajas a pie.", show_alert=True)

    except Exception as e:
        await query.answer(f"Error: {e}", show_alert=True)
        return

    # Refrescar panel de monturas
    await mostrar_monturas_inv(update, context)


# ==================== REGISTRO DE HANDLERS ====================
def registrar_handlers(app):
    app.add_handler(CommandHandler("inventario", cmd_inventario))
    app.add_handler(CallbackQueryHandler(mostrar_apartado, pattern="^inv_(equipado|normales|consumibles|mejoras|equipables)$"))
    app.add_handler(CallbackQueryHandler(mostrar_monturas_inv, pattern="^inv_monturas$"))
    app.add_handler(CallbackQueryHandler(montura_detalle_inv, pattern="^inv_mdet_"))
    app.add_handler(CallbackQueryHandler(montura_accion_inv, pattern="^inv_mequipar_|^inv_mdesmontar$"))
    app.add_handler(CallbackQueryHandler(procesar_accion, pattern="^inv_(desequipar|soltar|usar|mejora|equipar|volver|cerrar)"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_objetivo_mejora), group=10)
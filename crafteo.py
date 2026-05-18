#!/usr/bin/env python3
# crafteo.py
# Sistema de crafteo (fabricación) de objetos en la Zona Azul.
# Solo se permite craftear si el jugador está en zona azul.

import sys
import os
import asyncio
import sqlite3
from datetime import datetime
from typing import List, Dict, Tuple, Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters

import db_helper

DB_PATH = db_helper.DB_PATH

def _esc(texto: str) -> str:
    if not texto:
        return ""
    return str(texto).replace("_", "\\_").replace("*", "\\*").replace("`", "\\`").replace("[", "\\[")

import economia
from datos_zona import ZONAS
from combate import iniciar_combate  # por si se necesita en el futuro

# Añadir la carpeta globales (un nivel arriba) para importar catálogos
ruta_globales = os.path.join(os.path.dirname(__file__), '..', 'globales')
if ruta_globales not in sys.path:
    sys.path.insert(0, ruta_globales)

# Añadir la raíz del proyecto para importar db_helper, economia, etc.
ruta_raiz = os.path.join(os.path.dirname(__file__), '..')
if ruta_raiz not in sys.path:
    sys.path.insert(0, ruta_raiz)

from armas import ARMAS
from armaduras import ARMADURAS
from pociones import POCIONES
from materiales import MATERIALES
from recetas import RECETAS

# ==================== CONSTANTES ====================
ITEMS_POR_PAGINA = 10

# ==================== FUNCIONES AUXILIARES ====================
def obtener_nombre_objeto(objeto_id: str) -> str:
    """Devuelve el nombre de un objeto a partir de su ID buscando en los catálogos."""
    if objeto_id in ARMAS:
        return ARMAS[objeto_id]["nombre"]
    if objeto_id in ARMADURAS:
        return ARMADURAS[objeto_id]["nombre"]
    if objeto_id in POCIONES:
        return POCIONES[objeto_id]["nombre"]
    return objeto_id

def obtener_material_nombre(material_id: str) -> str:
    """Devuelve el nombre de un material a partir de su ID."""
    mat = MATERIALES.get(material_id)
    return mat["nombre"] if mat else material_id

def _en_zona_azul_ciudad(user_id: int) -> bool:
    """Verifica que el jugador esté en una ciudad de zona azul."""
    try:
        zona_nombre = db_helper.obtener_zona_actual(user_id)
        for zona in ZONAS:
            if zona["nombre"] == zona_nombre and zona["tipo"] == "ciudad" and zona["color"] == "azul":
                return True
    except:
        pass
    return False

def puede_fabricar(user_id: int, receta: dict, cantidad: int) -> tuple[bool, str]:
    """
    Verifica si el jugador puede fabricar 'cantidad' unidades de la receta.
    Retorna (True, "") o (False, mensaje de error).
    """
    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        return False, "Jugador no encontrado."
    nivel_jugador = jug.get("nivel", 0)
    if nivel_jugador < receta["nivel_requerido"]:
        return False, f"Necesitas nivel {receta['nivel_requerido']} para fabricar esto."
    clase_jugador = jug.get("clase", "")
    if receta.get("clase_requerida") and clase_jugador != receta["clase_requerida"]:
        return False, f"Solo la clase {receta['clase_requerida']} puede fabricar esto."
    inventario = db_helper.obtener_inventario(user_id)
    inv_dict = {it["nombre"]: it["cantidad"] for it in inventario}
    for mat_id, cant_necesaria in receta["materiales"].items():
        nombre_mat = obtener_material_nombre(mat_id)
        total_necesario = cant_necesaria * cantidad
        if inv_dict.get(nombre_mat, 0) < total_necesario:
            return False, f"No tienes suficientes {nombre_mat}. Necesitas {total_necesario}."
    # Comprobar si el objeto resultante tiene stock global limitado
    objeto_id = None
    for rid, r in RECETAS.items():
        if r == receta:
            objeto_id = rid
            break
    if objeto_id:
        obj_data = None
        if objeto_id in ARMAS:
            obj_data = ARMAS[objeto_id]
        elif objeto_id in ARMADURAS:
            obj_data = ARMADURAS[objeto_id]
        elif objeto_id in POCIONES:
            obj_data = POCIONES[objeto_id]
        if obj_data and obj_data.get("stock_global") is not None:
            stock_rest = obj_data.get("stock_restante", obj_data["stock_global"])
            if stock_rest < cantidad:
                return False, f"Solo quedan {stock_rest} unidades de este objeto en el mundo."
    return True, ""

def consumir_materiales(user_id: int, receta: dict, cantidad: int):
    """Elimina los materiales del inventario del jugador."""
    for mat_id, cant_necesaria in receta["materiales"].items():
        nombre_mat = obtener_material_nombre(mat_id)
        total_necesario = cant_necesaria * cantidad
        db_helper.quitar_item(user_id, nombre_mat, total_necesario)

def entregar_objeto(user_id: int, receta: dict, cantidad: int):
    """Añade el objeto fabricado al inventario del jugador y reduce stock global si es necesario."""
    objeto_id = None
    for rid, r in RECETAS.items():
        if r == receta:
            objeto_id = rid
            break
    if not objeto_id:
        return
    objeto_nombre = obtener_nombre_objeto(objeto_id)
    db_helper.agregar_item(user_id, objeto_nombre, cantidad)
    # Reducir stock global si existe
    obj_data = None
    if objeto_id in ARMAS:
        obj_data = ARMAS[objeto_id]
    elif objeto_id in ARMADURAS:
        obj_data = ARMADURAS[objeto_id]
    elif objeto_id in POCIONES:
        obj_data = POCIONES[objeto_id]
    if obj_data and obj_data.get("stock_global") is not None:
        obj_data["stock_restante"] = obj_data.get("stock_restante", obj_data["stock_global"]) - cantidad

async def tarea_crafteo(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, receta: dict, cantidad: int, tiempo: int):
    """Tarea asíncrona que espera el tiempo de crafteo y luego entrega el objeto."""
    await asyncio.sleep(tiempo)
    consumir_materiales(user_id, receta, cantidad)
    entregar_objeto(user_id, receta, cantidad)
    # Hook logros
    try:
        import logros as _logros
        nuevos = _logros.registrar_crafteo(user_id, cantidad)
        if nuevos:
            db_helper.agregar_notificacion(user_id, f"🏅 ¡{len(nuevos)} logro(s) desbloqueado(s)! Revisa /logros")
    except Exception:
        pass
    # Hook misiones
    try:
        import misiones as _mis
        _mis.completar_mision(user_id, "primer_crafteo", context)
    except Exception:
        pass
    try:
        await update.effective_message.reply_text(f"✅ ¡Crafteo completado! Has fabricado {cantidad}x {receta['nombre']}.")
    except:
        await context.bot.send_message(chat_id=user_id, text=f"✅ ¡Crafteo completado! Has fabricado {cantidad}x {receta['nombre']}.")
    db_helper.agregar_notificacion(user_id, f"⚒️ Has fabricado {cantidad}x {receta['nombre']}.")

# ==================== HANDLERS DE TELEGRAM ====================

# ==================== RECETAS DEL JUGADOR ====================
def obtener_recetas_jugador(user_id: int) -> set:
    """Retorna los IDs de recetas que el jugador ha comprado."""
    import sqlite3 as _sqlite3
    conn = _sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT receta_id FROM recetas_jugador WHERE user_id = ?", (user_id,))
    rows = c.fetchall()
    conn.close()
    return {row[0] for row in rows}

async def _responder(update, texto, **kwargs):
    """Envía o edita según el contexto (callback vs comando)."""
    msg = update.effective_message
    if getattr(update, "callback_query", None):
        try:
            await update.callback_query.edit_message_text(texto, **kwargs)
            return
        except Exception:
            pass
    await msg.reply_text(texto, **kwargs)

async def cmd_craftear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if db_helper.esta_marcado(user_id):
        await _responder(update, "❌ Estás marcado. No puedes craftear hasta que pagues rescate con /pagar_rescate.")
        return
    if not _en_zona_azul_ciudad(user_id):
        await _responder(update, "❌ Solo puedes craftear en ciudades de la zona azul. Regresa a tu ciudad para usar el taller.")
        return
    jug = db_helper.obtener_jugador(user_id)
    nivel = jug.get("nivel", 0)
    clase = jug.get("clase", "")
    recetas_propias = obtener_recetas_jugador(user_id)
    recetas_disponibles = []
    for rid, rec in RECETAS.items():
        if rid not in recetas_propias:
            continue
        if nivel >= rec["nivel_requerido"] and (rec.get("clase_requerida") is None or rec["clase_requerida"] == clase):
            recetas_disponibles.append((rid, rec))
    if not recetas_disponibles:
        await _responder(
            update,
            "📜 No tienes recetas aprendidas para tu nivel y clase.\n\n"
            "Las recetas son el unico requisito previo para craftear.\n"
            "Compralas en: 🏪 Ciudad → Comercio → Tienda → 🪙 Oro → 📜 Recetas\n\n"
            "Una vez compradas apareceran aqui automaticamente."
        )
        try:
            import guia_contextual as _gc
            await _gc.enviar(user_id, context, "crafteo_sin_recetas")
        except Exception:
            pass
        return
    context.user_data["crafteo_recetas"] = recetas_disponibles
    context.user_data["crafteo_pagina"] = 0
    await mostrar_pagina_recetas(update, context)

async def mostrar_pagina_recetas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    recetas = context.user_data.get("crafteo_recetas", [])
    pagina = context.user_data.get("crafteo_pagina", 0)
    total = len(recetas)
    if total == 0:
        await _responder(update, "No hay recetas disponibles.")
        return
    start = pagina * ITEMS_POR_PAGINA
    end = start + ITEMS_POR_PAGINA
    sublist = recetas[start:end]
    texto = f"*🔨 Recetas de crafteo (Zona Azul)*\nPágina {pagina+1}/{ (total+ITEMS_POR_PAGINA-1)//ITEMS_POR_PAGINA }\n\n"
    botones = []
    for rid, rec in sublist:
        texto += f"• *{_esc(rec['nombre'])}* (Nv. {rec['nivel_requerido']})\n"
        tiempo = rec["tiempo_segundos"]
        if tiempo > 0:
            texto += f"  ⏱️ {tiempo} segundos\n"
        else:
            texto += f"  ⚡ Instantáneo\n"
        mats = list(rec["materiales"].items())[:3]
        texto += "  🧪 " + ", ".join([f"{obtener_material_nombre(mid)} x{cant}" for mid, cant in mats])
        if len(rec["materiales"]) > 3:
            texto += "..."
        texto += "\n"
        botones.append([InlineKeyboardButton(f"🔨 {rec['nombre']}", callback_data=f"craf_sel_{rid}")])
    nav = []
    if pagina > 0:
        nav.append(InlineKeyboardButton("◀ Anterior", callback_data="craf_pag_ant"))
    if end < total:
        nav.append(InlineKeyboardButton("Siguiente ▶", callback_data="craf_pag_sig"))
    if nav:
        botones.append(nav)
    botones.append([InlineKeyboardButton("❌ Cerrar", callback_data="craf_cerrar")])
    markup = InlineKeyboardMarkup(botones)
    await _responder(update, texto, reply_markup=markup, parse_mode="Markdown")

async def craftear_paginar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    delta = 1 if "sig" in query.data else -1
    pagina_actual = context.user_data.get("crafteo_pagina", 0)
    nueva = pagina_actual + delta
    if nueva < 0:
        nueva = 0
    context.user_data["crafteo_pagina"] = nueva
    await mostrar_pagina_recetas(update, context)

async def craftear_seleccionar_receta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    partes_craf = query.data.split("_", 2)
    if len(partes_craf) < 3:
        await query.edit_message_text("❌ Error al seleccionar receta. Vuelve a intentarlo.")
        return
    receta_id = partes_craf[2]
    receta = RECETAS.get(receta_id)
    if not receta:
        await query.edit_message_text("Receta no encontrada.")
        return
    context.user_data["crafteo_receta_actual"] = receta
    context.user_data["crafteo_receta_id"] = receta_id
    texto = f"*{_esc(receta['nombre'])}*\n"
    texto += f"📜 {_esc(receta['descripcion'])}\n\n"
    texto += "*Materiales necesarios por unidad:*\n"
    for mat_id, cant in receta["materiales"].items():
        texto += f"- {obtener_material_nombre(mat_id)}: {cant}\n"
    if receta["tiempo_segundos"] > 0:
        texto += f"⏱️ Tiempo de crafteo: {receta['tiempo_segundos']} segundos\n"
    else:
        texto += "⚡ Instantáneo\n"
    texto += f"🏷️ Nivel requerido: {receta['nivel_requerido']}\n"
    if receta.get("clase_requerida"):
        texto += f"👥 Clase: {receta['clase_requerida']}\n"
    texto += "\n¿Cuántas unidades deseas fabricar? (1-9999, o 0 para cancelar)"
    await query.edit_message_text(texto, parse_mode="Markdown")
    context.user_data["esperando_cantidad"] = True

async def craftear_recibir_cantidad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("esperando_cantidad"):
        return
    try:
        cantidad = int(update.message.text.strip())
    except ValueError:
        await update.effective_message.reply_text("Cantidad inválida. Ingresa un número entero.")
        return
    if cantidad <= 0:
        await update.effective_message.reply_text("Crafteo cancelado.")
        context.user_data.pop("esperando_cantidad", None)
        return
    receta = context.user_data.get("crafteo_receta_actual")
    if not receta:
        await update.effective_message.reply_text("Error: receta no encontrada. Vuelve a intentar.")
        context.user_data.pop("esperando_cantidad", None)
        return
    user_id = update.effective_user.id
    if not _en_zona_azul_ciudad(user_id):
        await update.effective_message.reply_text("❌ Solo puedes craftear en ciudades de la zona azul. Regresa a tu ciudad para usar el taller.")
        context.user_data.pop("esperando_cantidad", None)
        return
    # Verificar si puede fabricar esa cantidad
    puede, msg = puede_fabricar(user_id, receta, cantidad)
    if not puede:
        await update.effective_message.reply_text(f"❌ {msg}")
        context.user_data.pop("esperando_cantidad", None)
        return
    # Verificar costes de oro/eternium (si los tiene la receta)
    costo_oro = receta.get("oro", 0) * cantidad
    costo_et = receta.get("eternium", 0) * cantidad
    if costo_oro > 0 or costo_et > 0:
        saldos = economia.obtener_saldos(user_id)
        if costo_oro > 0 and saldos["oro"] < costo_oro:
            await update.effective_message.reply_text(f"No tienes suficiente oro. Necesitas {costo_oro}.")
            return
        if costo_et > 0 and saldos["eternium"] < costo_et:
            await update.effective_message.reply_text(f"No tienes suficiente eternium. Necesitas {costo_et}.")
            return
        if costo_oro > 0:
            economia.modificar_saldo(user_id, "oro", -costo_oro, f"crafteo de {cantidad} {receta['nombre']}")
        if costo_et > 0:
            economia.modificar_saldo(user_id, "eternium", -costo_et, f"crafteo de {cantidad} {receta['nombre']}")
    tiempo = receta["tiempo_segundos"] * cantidad
    if tiempo > 0:
        await update.effective_message.reply_text(f"⚙️ Comenzando crafteo de {cantidad}x {receta['nombre']}.\nEsto tomará {tiempo} segundos. Te avisaré cuando termine.")
        asyncio.create_task(tarea_crafteo(update, context, user_id, receta, cantidad, tiempo))
    else:
        consumir_materiales(user_id, receta, cantidad)
        entregar_objeto(user_id, receta, cantidad)
        await update.effective_message.reply_text(f"✅ ¡Crafteo completado! Has fabricado {cantidad}x {receta['nombre']}.")
    context.user_data.pop("esperando_cantidad", None)

async def craftear_cerrar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("🔨 Taller de crafteo cerrado. ¡Vuelve pronto!")

# ==================== REGISTRO DE HANDLERS ====================
def registrar_handlers(app):
    app.add_handler(CommandHandler("craftear", cmd_craftear))
    app.add_handler(CallbackQueryHandler(craftear_paginar, pattern="^craf_pag_(ant|sig)$"))
    app.add_handler(CallbackQueryHandler(craftear_seleccionar_receta, pattern="^craf_sel_"))
    app.add_handler(CallbackQueryHandler(craftear_cerrar, pattern="^craf_cerrar$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, craftear_recibir_cantidad), group=10)
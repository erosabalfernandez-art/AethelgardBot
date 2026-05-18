#!/usr/bin/env python3
# subastas.py
# Sistema de subastas de objetos entre jugadores.
# Permite subastar armas, armaduras, materiales y monturas.
# Cantidad: 1-100 unidades. Duración: 20 min a 5 días (en horas).
# Publicación con retención del objeto, pujas con retención de saldo.
# Comisión para el vendedor, incremento mínimo, duración configurable.
# Incluye notificaciones, historial y cancelación de subastas propias.

import sys
import os
import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, CommandHandler, CallbackQueryHandler,
    ConversationHandler, MessageHandler, filters
)

def _esc(texto: str) -> str:
    if not texto:
        return ""
    return str(texto).replace("_", "\\_").replace("*", "\\*").replace("`", "\\`").replace("[", "\\[")

import economia
import db_helper
from datos_zona import ZONAS

# Añadir la carpeta "globales" (un nivel arriba) al path para importar catálogos
ruta_globales = os.path.join(os.path.dirname(__file__), '..', 'globales')
if ruta_globales not in sys.path:
    sys.path.insert(0, ruta_globales)

# También añadir la raíz del proyecto para importar economia y db_helper
ruta_raiz = os.path.join(os.path.dirname(__file__), '..')
if ruta_raiz not in sys.path:
    sys.path.insert(0, ruta_raiz)

# Importar catálogos globales para validar objetos subastables
from armas import ARMAS
from armaduras import ARMADURAS
from materiales import MATERIALES
from monturas import MONTURAS

DB_PATH = "aethelgard.db"

_BOTONES_RAPIDOS = frozenset({
    "👤 Perfil", "🏙️ Ciudad", "🎒 Inventario", "✈️ Viajar",
    "⚔️ Combate", "🏰 Gremio", "⛏️ Recolectar", "🔍 Investigar",
    "🏰 Mazmorra", "📋 Comandos", "📖 Guía",
})

# ==================== CONSTANTES ====================
DURACION_POR_DEFECTO_HORAS = 24            # 24 horas
MIN_DURACION_HORAS = 20 / 60               # 20 minutos = 0.333 horas
MAX_DURACION_HORAS = 5 * 24                # 5 días = 120 horas
INCREMENTO_MINIMO_PORCENTAJE = 10
COMISION_PORCENTAJE = 5
CANTIDAD_MINIMA = 1
CANTIDAD_MAXIMA = 100

# Estados para la conversación de publicación
(ESP_SELECCIONAR_OBJETO, ESP_CANTIDAD, ESP_PRECIO_INICIAL, ESP_MONEDA, ESP_DURACION) = range(5)

# ==================== FUNCIÓN AUXILIAR _en_ciudad ====================
def _en_ciudad(user_id: int) -> bool:
    try:
        zona_nombre = db_helper.obtener_zona_actual(user_id)
        for zona in ZONAS:
            if zona["nombre"] == zona_nombre and zona["tipo"] == "ciudad":
                return True
    except:
        pass
    return False

# ==================== TABLAS ====================
def _init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS subastas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        vendedor_id INTEGER,
        objeto_nombre TEXT,
        cantidad INTEGER,
        moneda TEXT,
        precio_inicial INTEGER,
        precio_actual INTEGER,
        puja_maxima_id INTEGER,
        fecha_inicio TIMESTAMP,
        fecha_fin TIMESTAMP,
        activa BOOLEAN DEFAULT 1
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS pujas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        subasta_id INTEGER,
        postor_id INTEGER,
        cantidad INTEGER,
        retenida BOOLEAN DEFAULT 1,
        fecha TIMESTAMP
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS historial_subastas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        subasta_id INTEGER,
        vendedor_id INTEGER,
        comprador_id INTEGER,
        objeto_nombre TEXT,
        precio_final INTEGER,
        moneda TEXT,
        comision INTEGER,
        fecha TIMESTAMP
    )''')
    conn.commit()
    conn.close()

_init_db()

# ==================== FUNCIONES AUXILIARES ====================
def _formatear_moneda(moneda: str) -> str:
    return {"oro": "🪙 Oro", "eternium": "💎 Eternium", "creditos_vacio": "✨ Créditos"}.get(moneda, moneda)

def _formatear_duracion(horas: float) -> str:
    if horas < 1:
        minutos = int(horas * 60)
        return f"{minutos} minutos"
    elif horas < 24:
        return f"{horas:.1f} horas"
    else:
        dias = int(horas / 24)
        resto_horas = horas % 24
        if resto_horas < 0.1:
            return f"{dias} días"
        else:
            return f"{dias} días y {resto_horas:.1f} horas"

def _es_objeto_subastable(nombre_objeto: str) -> bool:
    # Buscar en armas
    for arma in ARMAS.values():
        if arma["nombre"] == nombre_objeto:
            return True
    # Buscar en armaduras
    for armadura in ARMADURAS.values():
        if armadura["nombre"] == nombre_objeto:
            return True
    # Buscar en materiales
    for material in MATERIALES.values():
        if material["nombre"] == nombre_objeto:
            return True
    # Buscar en monturas
    for montura in MONTURAS.values():
        if montura["nombre"] == nombre_objeto:
            return True
    return False

def _obtener_subastas_activas() -> List[Dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    ahora = datetime.now().isoformat()
    c.execute('SELECT * FROM subastas WHERE activa = 1 AND fecha_fin > ?', (ahora,))
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def _obtener_subastas_por_vendedor(vendedor_id: int) -> List[Dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM subastas WHERE vendedor_id = ? AND activa = 1', (vendedor_id,))
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def _devolver_retenciones_subasta(subasta_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT p.postor_id, p.cantidad, s.moneda FROM pujas p JOIN subastas s ON p.subasta_id = s.id WHERE p.subasta_id = ? AND p.retenida = 1', (subasta_id,))
    pujas = c.fetchall()
    for postor_id, cantidad, moneda in pujas:
        economia.modificar_saldo(postor_id, moneda, cantidad, f"devolución puja subasta #{subasta_id}")
        c.execute('UPDATE pujas SET retenida = 0 WHERE subasta_id = ? AND postor_id = ?', (subasta_id, postor_id))
    conn.commit()
    conn.close()

def _finalizar_subasta(subasta_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT vendedor_id, objeto_nombre, cantidad, precio_actual, puja_maxima_id, moneda FROM subastas WHERE id = ? AND activa = 1', (subasta_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return
    vendedor_id, objeto_nombre, cantidad, precio_final, ganador_id, moneda = row
    if ganador_id == 0:
        # Sin pujas: devolver objeto al vendedor
        db_helper.agregar_item(vendedor_id, objeto_nombre, cantidad)
        c.execute('UPDATE subastas SET activa = 0 WHERE id = ?', (subasta_id,))
        conn.commit()
        conn.close()
        db_helper.agregar_notificacion(vendedor_id, f"📦 Tu subasta de '{objeto_nombre}' finalizó sin pujas. Se te ha devuelto el objeto.")
        return
    comision = int(precio_final * COMISION_PORCENTAJE / 100)
    cantidad_vendedor = precio_final - comision
    economia.modificar_saldo(vendedor_id, moneda, cantidad_vendedor, f"venta subasta #{subasta_id}")
    db_helper.agregar_item(ganador_id, objeto_nombre, cantidad)
    c.execute('''INSERT INTO historial_subastas (subasta_id, vendedor_id, comprador_id, objeto_nombre, precio_final, moneda, comision, fecha)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
              (subasta_id, vendedor_id, ganador_id, objeto_nombre, precio_final, moneda, comision, datetime.now().isoformat()))
    c.execute('UPDATE subastas SET activa = 0 WHERE id = ?', (subasta_id,))
    conn.commit()
    _devolver_retenciones_subasta(subasta_id)
    conn.close()
    db_helper.agregar_notificacion(vendedor_id, f"🎉 Tu subasta de '{objeto_nombre}' se cerró. Recibiste {cantidad_vendedor} {_formatear_moneda(moneda)} (comisión {comision}).")
    db_helper.agregar_notificacion(ganador_id, f"🎉 Ganaste la subasta de '{objeto_nombre}'. Pagaste {precio_final} {_formatear_moneda(moneda)} y recibiste el objeto.")

async def _comprobar_subastas_expiradas(context=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    ahora = datetime.now().isoformat()
    c.execute('SELECT id FROM subastas WHERE activa = 1 AND fecha_fin <= ?', (ahora,))
    for (subasta_id,) in c.fetchall():
        _finalizar_subasta(subasta_id)
    conn.close()

# ==================== COMANDO PRINCIPAL ====================
async def cmd_subastas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        from guerra_facciones import check_lockdown
        if await check_lockdown(update):
            return
    except Exception:
        pass
    try:
        import umbral_vacio as _uv
        if _uv.hay_escasez_activa():
            await update.effective_message.reply_text(
                "🔒 *Las subastas están cerradas*\n\n"
                "La Escasez Global causada por la Noche del Vacío ha cerrado "
                "temporalmente la casa de subastas.\n"
                "Termina cuando acabe el período de escasez. Usa /corrupcion para ver el estado.",
                parse_mode="Markdown"
            )
            return
    except Exception:
        pass
    if db_helper.esta_marcado(user_id):
        await update.effective_message.reply_text("❌ Estás marcado. No puedes usar la casa de subastas hasta que pagues rescate.")
        return
    if not _en_ciudad(user_id):
        await update.effective_message.reply_text("🏙️ La casa de subastas solo está disponible dentro de las ciudades. Vuelve a la ciudad para usarla.")
        return
    keyboard = [
        [InlineKeyboardButton("📜 Ver subastas activas", callback_data="sub_ver")],
        [InlineKeyboardButton("➕ Publicar subasta", callback_data="sub_publicar")],
        [InlineKeyboardButton("❌ Cancelar mis subastas", callback_data="sub_cancelar")],
        [InlineKeyboardButton("📋 Mis subastas activas", callback_data="sub_mis")],
        [InlineKeyboardButton("📜 Historial", callback_data="sub_historial")],
        [InlineKeyboardButton("❌ Cerrar", callback_data="sub_cerrar")]
    ]
    await update.effective_message.reply_text(
        "🏛️ *Casa de Subastas*\n\n"
        f"Comisión: {COMISION_PORCENTAJE}% (vendedor).\n"
        f"Incremento mínimo: {INCREMENTO_MINIMO_PORCENTAJE}%.\n"
        f"Duración permitida: 20 minutos a 5 días.\n"
        f"Cantidad por lote: {CANTIDAD_MINIMA} a {CANTIDAD_MAXIMA} unidades.\n\n"
        "Selecciona una opción:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

    try:
        import guia_contextual as _gc
        await _gc.enviar(user_id, context, "subastas_menu")
    except Exception:
        pass

# ==================== VER SUBASTAS ====================
def _rareza_emoji_sub(rareza: int) -> str:
    tabla = {1:"⚪",2:"🟢",3:"🔵",4:"🟣",5:"🟠",6:"🔴",7:"⭐",8:"💫",9:"✨",10:"👑",11:"🌟",12:"💎"}
    return tabla.get(rareza, "⚪")

def _stats_resumen(nombre_obj: str) -> str:
    """Intenta buscar stats resumidas del objeto por nombre en los catálogos disponibles."""
    try:
        import importlib, os, sys
        raiz = os.path.dirname(os.path.abspath(__file__))
        for mod_name, var_name in [("armas","ARMAS"),("armaduras","ARMADURAS"),("pociones","POCIONES"),("monturas","MONTURAS")]:
            ruta = os.path.join(raiz, f"{mod_name}.py")
            if not os.path.isfile(ruta):
                continue
            spec = importlib.util.spec_from_file_location(mod_name, ruta)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            catalogo = getattr(mod, var_name, {})
            for obj in catalogo.values():
                if obj.get("nombre") == nombre_obj:
                    tipo = obj.get("tipo","")
                    rar = obj.get("rareza",1)
                    rar_e = _rareza_emoji_sub(rar)
                    nv = obj.get("nivel_requerido",1)
                    if tipo == "arma" or "daño" in obj:
                        return f"{rar_e} Nv{nv} | ⚔️{obj.get('daño',0)} 🎯{obj.get('critico',0)} ⚡{obj.get('velocidad',0)}"
                    elif tipo == "armadura" or "defensa" in obj:
                        return f"{rar_e} Nv{nv} | 🛡️{obj.get('defensa',0)} 🎯R.Crit:{obj.get('resistencia_critico',0)}"
                    elif "velocidad" in obj and "carga" in obj:
                        return f"{rar_e} Nv{nv} | 🚀+{obj.get('velocidad',0)}% 📦+{obj.get('carga',0)}"
                    elif "efecto" in obj:
                        ef = obj.get("efecto","")
                        return f"{rar_e} Nv{nv} | {ef[:40]}"
    except Exception:
        pass
    return ""

async def sub_ver_subastas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    subastas = _obtener_subastas_activas()
    user_id = update.effective_user.id
    subastas = [s for s in subastas if s["vendedor_id"] != user_id]
    if not subastas:
        await query.edit_message_text("No hay subastas activas en este momento.")
        return
    texto = "📜 *Subastas activas*\n_Pulsa una subasta para ver los stats y pujar._"
    botones = []
    for s in subastas[:10]:
        vendedor = db_helper.obtener_jugador(s["vendedor_id"])
        nombre_vend = vendedor.get("nombre_personaje", "?") if vendedor else "?"
        stats = _stats_resumen(s["objeto_nombre"])
        stats_txt = f"\n   _{stats}_" if stats else ""
        moneda_txt = _formatear_moneda(s["moneda"])
        btn_txt = f"🏷️ {s['objeto_nombre']} (x{s['cantidad']}) — {s['precio_actual']} {moneda_txt}"
        if len(btn_txt) > 62:
            btn_txt = btn_txt[:59] + "..."
        botones.append([InlineKeyboardButton(btn_txt, callback_data=f"sub_pujar_{s['id']}")])
    botones.append([InlineKeyboardButton("🔙 Volver", callback_data="sub_volver")])
    await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(botones), parse_mode="Markdown")

# ==================== PUJAR ====================
async def sub_pujar_inicio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        subasta_id = int(query.data.split("_")[2])
    except (ValueError, IndexError):
        await query.edit_message_text("❌ Error al procesar la subasta.")
        return
    context.user_data["pujar_subasta_id"] = subasta_id
    sub = next((s for s in _obtener_subastas_activas() if s["id"] == subasta_id), None)
    if not sub:
        await query.edit_message_text("La subasta ya no está activa.")
        return
    incremento = max(1, int(sub["precio_actual"] * INCREMENTO_MINIMO_PORCENTAJE / 100))
    vendedor = db_helper.obtener_jugador(sub["vendedor_id"])
    nombre_vend = vendedor.get("nombre_personaje", "?") if vendedor else "?"
    stats = _stats_resumen(sub["objeto_nombre"])
    stats_bloque = f"\n📊 _{stats}_" if stats else ""
    moneda_txt = _formatear_moneda(sub["moneda"])
    texto = (
        f"🏷️ *{_esc(sub['objeto_nombre'])}* (x{sub['cantidad']})"
        f"{stats_bloque}\n\n"
        f"👤 Vendedor: *{_esc(nombre_vend)}*\n"
        f"💰 Precio actual: *{sub['precio_actual']} {moneda_txt}*\n"
        f"📈 Puja mínima: *{sub['precio_actual'] + incremento} {moneda_txt}* (+{incremento})\n"
        f"🕒 Fin: {sub['fecha_fin'][:16]}\n\n"
        "Ingresa tu oferta (número entero):"
    )
    await query.edit_message_text(texto, parse_mode="Markdown")
    context.user_data["esperando_puja"] = True

async def sub_recibir_puja(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("esperando_puja"):
        return
    user_id = update.effective_user.id
    subasta_id = context.user_data.get("pujar_subasta_id")
    if not subasta_id:
        return
    try:
        cantidad = int(update.message.text.strip())
    except ValueError:
        await update.effective_message.reply_text("Cantidad inválida. Ingresa un número entero.")
        return
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT vendedor_id, precio_actual, puja_maxima_id, moneda, activa, fecha_fin FROM subastas WHERE id = ?', (subasta_id,))
    row = c.fetchone()
    if not row or not row[4] or datetime.now().isoformat() > row[5]:
        await update.effective_message.reply_text("La subasta ya no está activa.")
        context.user_data.pop("esperando_puja", None)
        conn.close()
        return
    vendedor_id, precio_actual, actual_max_id, moneda, activa, fecha_fin = row
    conn.close()
    if user_id == vendedor_id:
        await update.effective_message.reply_text("No puedes pujar en tu propia subasta.")
        context.user_data.pop("esperando_puja", None)
        return
    incremento_min = max(1, int(precio_actual * INCREMENTO_MINIMO_PORCENTAJE / 100))
    if cantidad < precio_actual + incremento_min:
        await update.effective_message.reply_text(f"La puja debe ser al menos {precio_actual + incremento_min} {_formatear_moneda(moneda)}.")
        return
    saldos = economia.obtener_saldos(user_id)
    if saldos.get(moneda, 0) < cantidad:
        await update.effective_message.reply_text(f"No tienes suficiente {_formatear_moneda(moneda)}.")
        context.user_data.pop("esperando_puja", None)
        return
    # Retener saldo
    economia.modificar_saldo(user_id, moneda, -cantidad, f"puja subasta #{subasta_id}")
    # Devolver al anterior postor y notificarle
    if actual_max_id != 0:
        economia.modificar_saldo(actual_max_id, moneda, precio_actual, f"devolución puja superada subasta #{subasta_id}")
        db_helper.agregar_notificacion(actual_max_id,
            f"📢 Tu puja en la subasta #{subasta_id} fue superada. Se te devolvieron {precio_actual} {_formatear_moneda(moneda)}.")
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('UPDATE pujas SET retenida = 0 WHERE subasta_id = ? AND postor_id = ?', (subasta_id, actual_max_id))
        conn.commit()
        conn.close()
    # Actualizar subasta
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('UPDATE subastas SET precio_actual = ?, puja_maxima_id = ? WHERE id = ?', (cantidad, user_id, subasta_id))
    c.execute('INSERT INTO pujas (subasta_id, postor_id, cantidad, retenida, fecha) VALUES (?, ?, ?, 1, ?)',
              (subasta_id, user_id, cantidad, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    await update.effective_message.reply_text(f"✅ Puja registrada. Eres el mejor postor con {cantidad} {_formatear_moneda(moneda)}.")
    context.user_data.pop("esperando_puja", None)
    db_helper.agregar_notificacion(vendedor_id, f"💰 Nueva puja en tu subasta #{subasta_id}: {cantidad} {_formatear_moneda(moneda)}.")

# ==================== PUBLICAR SUBASTA (CONVERSACIÓN) ====================
async def sub_publicar_inicio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    inv = db_helper.obtener_inventario(user_id)
    if not inv:
        await query.edit_message_text("No tienes ningún objeto en tu inventario.")
        return
    inv_filtrado = [it for it in inv if _es_objeto_subastable(it["nombre"])]
    if not inv_filtrado:
        await query.edit_message_text("No tienes objetos que se puedan subastar (solo armas, armaduras, materiales y monturas).")
        return
    keyboard = [[InlineKeyboardButton(f"{it['nombre']} (x{it['cantidad']})", callback_data=f"sub_obj_{it['nombre']}")] for it in inv_filtrado]
    keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data="sub_volver")])
    await query.edit_message_text("Selecciona el objeto a subastar:", reply_markup=InlineKeyboardMarkup(keyboard))
    return ESP_SELECCIONAR_OBJETO

async def sub_seleccionar_objeto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    partes_sub = query.data.split("_", 2)
    if len(partes_sub) < 3:
        await query.edit_message_text("❌ Error al seleccionar objeto. Vuelve a intentarlo.")
        return
    obj_nombre = partes_sub[2]
    context.user_data["sub_objeto"] = obj_nombre
    inv = db_helper.obtener_inventario(update.effective_user.id)
    cantidad_total = next((it["cantidad"] for it in inv if it["nombre"] == obj_nombre), 0)
    max_permitido = min(cantidad_total, CANTIDAD_MAXIMA)
    await query.edit_message_text(
        f"Tienes {cantidad_total} de '{obj_nombre}'.\n"
        f"¿Cuántos subastas? (mínimo {CANTIDAD_MINIMA}, máximo {max_permitido})"
    )
    return ESP_CANTIDAD

async def sub_cantidad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.strip()
    if texto in _BOTONES_RAPIDOS:
        await sub_cancelar_publicacion(update, context)
        return ConversationHandler.END
    try:
        cantidad = int(texto)
    except ValueError:
        await update.effective_message.reply_text("Cantidad inválida. Ingresa un número entero.")
        return ESP_CANTIDAD
    obj = context.user_data["sub_objeto"]
    inv = db_helper.obtener_inventario(update.effective_user.id)
    total = next((it["cantidad"] for it in inv if it["nombre"] == obj), 0)
    max_permitido = min(total, CANTIDAD_MAXIMA)
    if cantidad < CANTIDAD_MINIMA or cantidad > max_permitido:
        await update.effective_message.reply_text(f"Cantidad debe estar entre {CANTIDAD_MINIMA} y {max_permitido}.")
        return ESP_CANTIDAD
    context.user_data["sub_cantidad"] = cantidad
    # Retener objeto (quitarlo del inventario)
    db_helper.quitar_item(update.effective_user.id, obj, cantidad)
    await update.effective_message.reply_text("Precio inicial (número entero):")
    return ESP_PRECIO_INICIAL

async def sub_precio_inicial(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.strip()
    if texto in _BOTONES_RAPIDOS:
        await sub_cancelar_publicacion(update, context)
        return ConversationHandler.END
    try:
        precio = int(texto)
    except ValueError:
        await update.effective_message.reply_text("Precio inicial debe ser un número entero.")
        return ESP_PRECIO_INICIAL
    if precio <= 0:
        await update.effective_message.reply_text("El precio debe ser mayor a cero.")
        return ESP_PRECIO_INICIAL
    context.user_data["sub_precio"] = precio
    keyboard = [
        [InlineKeyboardButton("🪙 Oro", callback_data="sub_moneda_oro")],
        [InlineKeyboardButton("💎 Eternium", callback_data="sub_moneda_eternium")],
        [InlineKeyboardButton("✨ Créditos", callback_data="sub_moneda_creditos")]
    ]
    await update.effective_message.reply_text("Moneda de la subasta:", reply_markup=InlineKeyboardMarkup(keyboard))
    return ESP_MONEDA

async def sub_moneda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    partes_mon = query.data.split("_")
    if len(partes_mon) < 3:
        await query.edit_message_text("❌ Error al seleccionar moneda.")
        return
    moneda = partes_mon[2]
    context.user_data["sub_moneda"] = moneda
    await query.edit_message_text(
        f"Duración de la subasta (en horas).\n"
        f"Mínimo: {MIN_DURACION_HORAS:.2f} horas (20 minutos)\n"
        f"Máximo: {MAX_DURACION_HORAS:.0f} horas (5 días)\n"
        f"Default: {DURACION_POR_DEFECTO_HORAS} horas\n\n"
        "Escribe un número (puede ser decimal, ej. 0.5 para 30 minutos) o 'default'."
    )
    return ESP_DURACION

async def sub_duracion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.strip()
    if texto in _BOTONES_RAPIDOS:
        await sub_cancelar_publicacion(update, context)
        return ConversationHandler.END
    if texto.lower() == "default":
        horas = float(DURACION_POR_DEFECTO_HORAS)
    else:
        try:
            horas = float(texto)
        except ValueError:
            await update.effective_message.reply_text("Número inválido. Usa 'default' o un número decimal.")
            return ESP_DURACION
        if horas < MIN_DURACION_HORAS or horas > MAX_DURACION_HORAS:
            await update.effective_message.reply_text(f"Duración debe estar entre {MIN_DURACION_HORAS:.2f} horas (20 min) y {MAX_DURACION_HORAS:.0f} horas (5 días).")
            return ESP_DURACION
    user_id = update.effective_user.id
    objeto = context.user_data["sub_objeto"]
    cantidad = context.user_data["sub_cantidad"]
    precio = context.user_data["sub_precio"]
    moneda = context.user_data["sub_moneda"]
    ahora = datetime.now()
    fin = ahora + timedelta(hours=horas)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT INTO subastas 
        (vendedor_id, objeto_nombre, cantidad, moneda, precio_inicial, precio_actual, puja_maxima_id, fecha_inicio, fecha_fin, activa)
        VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?, 1)''',
              (user_id, objeto, cantidad, moneda, precio, precio, ahora.isoformat(), fin.isoformat()))
    subasta_id = c.lastrowid
    conn.commit()
    conn.close()
    await update.effective_message.reply_text(
        f"✅ Subasta publicada con ID #{subasta_id}.\n"
        f"Finaliza en {_formatear_duracion(horas)}."
    )
    try:
        import guia_contextual as _gc
        await _gc.enviar(user_id, context, "subasta_creada")
    except Exception:
        pass
    context.user_data.clear()
    return ConversationHandler.END

async def sub_cancelar_publicacion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Siempre devolver el objeto retenido si lo hay
    obj = context.user_data.get("sub_objeto")
    cant = context.user_data.get("sub_cantidad")
    if obj and cant:
        db_helper.agregar_item(update.effective_user.id, obj, cant)
    text = (update.effective_message.text or "").strip() if update.effective_message else ""
    context.user_data.clear()
    # Si fue por navegación, redirigir al destino sin mostrar "cancelado"
    _DESPACHO = {
        "/ciudad":     ("ciudad",     "cmd_ciudad"),
        "/perfil":     ("perfil",     "cmd_perfil"),
        "/viajar":     ("viajes",     "cmd_viajar"),
        "/inventario": ("inventario", "cmd_inventario"),
        "/gremio":     ("gremios",    "cmd_gremio"),
    }
    try:
        for cmd_txt, (mod_name, func_name) in _DESPACHO.items():
            if text.startswith(cmd_txt):
                import importlib
                m = importlib.import_module(mod_name)
                await getattr(m, func_name)(update, context)
                return ConversationHandler.END
        from teclado_rapido import handle_boton_rapido, _MAPA
        if text in _MAPA:
            await handle_boton_rapido(update, context)
            return ConversationHandler.END
    except Exception:
        pass
    await update.effective_message.reply_text("❌ Publicación cancelada. Objeto devuelto a tu inventario.")
    return ConversationHandler.END

# ==================== CANCELAR MIS SUBASTAS ====================
async def sub_cancelar_mis_subastas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    subastas = _obtener_subastas_por_vendedor(user_id)
    if not subastas:
        await query.edit_message_text("No tienes subastas activas.")
        return
    texto = "Tus subastas activas:\n"
    botones = []
    for s in subastas:
        texto += f"#{s['id']}: {s['objeto_nombre']} x{s['cantidad']} - Precio: {s['precio_actual']} {_formatear_moneda(s['moneda'])}\n"
        botones.append([InlineKeyboardButton(f"Cancelar #{s['id']}", callback_data=f"sub_cancelar_{s['id']}")])
    botones.append([InlineKeyboardButton("🔙 Volver", callback_data="sub_volver")])
    await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(botones), parse_mode="Markdown")

async def sub_cancelar_subasta_individual(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        subasta_id = int(query.data.split("_")[2])
    except (ValueError, IndexError):
        await query.edit_message_text("❌ Error al procesar la subasta.")
        return
    user_id = update.effective_user.id
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT vendedor_id, objeto_nombre, cantidad, activa FROM subastas WHERE id = ?', (subasta_id,))
    row = c.fetchone()
    if not row or not row[3] or row[0] != user_id:
        await query.edit_message_text("No puedes cancelar esta subasta.")
        conn.close()
        return
    obj, cant = row[1], row[2]
    # Guardar postores con puja activa antes de liberar retenciones
    c.execute(
        'SELECT p.postor_id, p.cantidad, s.moneda FROM pujas p '
        'JOIN subastas s ON p.subasta_id = s.id '
        'WHERE p.subasta_id = ? AND p.retenida = 1',
        (subasta_id,)
    )
    postores_activos = c.fetchall()
    db_helper.agregar_item(user_id, obj, cant)
    _devolver_retenciones_subasta(subasta_id)
    c.execute('UPDATE subastas SET activa = 0 WHERE id = ?', (subasta_id,))
    conn.commit()
    conn.close()
    # Notificar a cada postor afectado
    for postor_id, cantidad_puja, moneda_puja in postores_activos:
        db_helper.agregar_notificacion(postor_id,
            f"❌ La subasta #{subasta_id} ({obj}) fue cancelada por el vendedor. "
            f"Se te devolvieron {cantidad_puja} {_formatear_moneda(moneda_puja)}.")
    await query.edit_message_text(f"Subasta #{subasta_id} cancelada. Objeto devuelto y pujas liberadas.")

# ==================== MIS SUBASTAS ACTIVAS ====================
async def sub_mis_subastas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    subastas = _obtener_subastas_por_vendedor(user_id)
    if not subastas:
        await query.edit_message_text("No tienes subastas activas.")
        return
    texto = "📋 *Tus subastas activas*\n\n"
    for s in subastas:
        fin = datetime.fromisoformat(s["fecha_fin"])
        ahora = datetime.now()
        if fin > ahora:
            resto = fin - ahora
            horas_rest = resto.total_seconds() / 3600
            texto += f"ID {s['id']}: {s['objeto_nombre']} x{s['cantidad']}\n"
            texto += f"  Precio actual: {s['precio_actual']} {_formatear_moneda(s['moneda'])}\n"
            texto += f"  Resta: {_formatear_duracion(horas_rest)}\n\n"
        else:
            texto += f"ID {s['id']}: {s['objeto_nombre']} x{s['cantidad']} (finalizada)\n"
    await query.edit_message_text(texto, parse_mode="Markdown")

# ==================== HISTORIAL ====================
async def sub_historial(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''SELECT subasta_id, vendedor_id, comprador_id, objeto_nombre, precio_final, moneda, comision, fecha
                 FROM historial_subastas WHERE vendedor_id = ? OR comprador_id = ?
                 ORDER BY fecha DESC LIMIT 10''', (user_id, user_id))
    rows = c.fetchall()
    conn.close()
    if not rows:
        await query.edit_message_text("No hay historial.")
        return
    texto = "📜 *Historial de subastas*\n\n"
    for row in rows:
        sub_id, v, c_id, obj, precio, moneda, comision, fecha = row
        if v == user_id:
            texto += f"Vendiste {obj} por {precio} {_formatear_moneda(moneda)} (comisión {comision})\n"
        else:
            texto += f"Compraste {obj} por {precio} {_formatear_moneda(moneda)}\n"
        texto += f"  {fecha[:19]}\n\n"
    await query.edit_message_text(texto, parse_mode="Markdown")

# ==================== NAVEGACIÓN ====================
async def sub_volver(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await cmd_subastas(update, context)

async def sub_cerrar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("🏛️ Casa de Subastas cerrada. ¡Vuelve pronto!")

# ==================== REGISTRO DE HANDLERS ====================
def registrar_handlers(app):
    app.add_handler(CommandHandler("subastas", cmd_subastas))
    app.add_handler(CallbackQueryHandler(sub_ver_subastas, pattern="^sub_ver$"))
    app.add_handler(CallbackQueryHandler(sub_pujar_inicio, pattern="^sub_pujar_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, sub_recibir_puja), group=10)
    app.add_handler(CallbackQueryHandler(sub_cancelar_mis_subastas, pattern="^sub_cancelar$"))
    app.add_handler(CallbackQueryHandler(sub_cancelar_subasta_individual, pattern="^sub_cancelar_"))
    app.add_handler(CallbackQueryHandler(sub_mis_subastas, pattern="^sub_mis$"))
    app.add_handler(CallbackQueryHandler(sub_historial, pattern="^sub_historial$"))
    app.add_handler(CallbackQueryHandler(sub_volver, pattern="^sub_volver$"))
    app.add_handler(CallbackQueryHandler(sub_cerrar, pattern="^sub_cerrar$"))
    conv_publicar = ConversationHandler(
        entry_points=[CallbackQueryHandler(sub_publicar_inicio, pattern="^sub_publicar$")],
        states={
            ESP_SELECCIONAR_OBJETO: [CallbackQueryHandler(sub_seleccionar_objeto, pattern="^sub_obj_")],
            ESP_CANTIDAD: [MessageHandler(filters.TEXT & ~filters.COMMAND, sub_cantidad)],
            ESP_PRECIO_INICIAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, sub_precio_inicial)],
            ESP_MONEDA: [CallbackQueryHandler(sub_moneda, pattern="^sub_moneda_")],
            ESP_DURACION: [MessageHandler(filters.TEXT & ~filters.COMMAND, sub_duracion)],
        },
        fallbacks=[
            CommandHandler("cancel",     sub_cancelar_publicacion),
            CommandHandler("ciudad",     sub_cancelar_publicacion),
            CommandHandler("perfil",     sub_cancelar_publicacion),
            CommandHandler("viajar",     sub_cancelar_publicacion),
            CommandHandler("inventario", sub_cancelar_publicacion),
            CommandHandler("gremio",     sub_cancelar_publicacion),
            CommandHandler("start",      sub_cancelar_publicacion),
            MessageHandler(filters.Regex("^(👤|🏙️?|🎒|✈️?|⚔️?|🏰|⛏️?|🔍|📋|📖)"), sub_cancelar_publicacion),
        ]
    )
    app.add_handler(conv_publicar)
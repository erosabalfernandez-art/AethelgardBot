# banco.py
# Sistema completo de cambio de monedas con tasas dinámicas opcionales,
# límites diarios, comisiones, bonificaciones, historial, estadísticas e interés semanal.
# El banco NUNCA entrega Créditos del Vacío: solo los recibe (los absorbe) a cambio de Eternium.

import sqlite3
import math
from datetime import datetime, timedelta
from typing import Dict, Tuple, Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, CommandHandler, CallbackQueryHandler,
    ConversationHandler, MessageHandler, filters
)

import economia
import db_helper
from datos_zona import ZONAS

DB_PATH = "aethelgard.db"

# ==================== CONSTANTES ====================
ORO_A_ETERNIUM_TASA = 1000          # 1000 Oro → 1 Eternium
ETERNIUM_A_ORO_TASA = 900           # 1 Eternium → 900 Oro
CREDITO_A_ETERNIUM_TASA = 5         # 1 Crédito → 5 Eternium (el banco absorbe créditos)

COMISION_PORCENTAJE = 2.0           # 2%

UMBRAL_BONIFICACION_ETERNIUM = 10
BONIFICACION_PORCENTAJE = 5.0       # +5% extra

LIMITE_DIARIO_ORO = 50000
LIMITE_DIARIO_ETERNIUM = 50
LIMITE_DIARIO_CREDITOS = 10

INTERES_SEMANAL_PORCENTAJE = 0.1
SALDO_MINIMO_INTERES = 100

# Estados para las conversaciones
(ESP_ORO, ESP_ETERNIUM, ESP_CREDITOS) = range(3)

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

# ==================== TABLAS ADICIONALES ====================
def _init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS limites_conversion (
        user_id INTEGER,
        fecha TEXT,
        creditos_convertidos INTEGER DEFAULT 0,
        oro_convertido INTEGER DEFAULT 0,
        eternium_convertido INTEGER DEFAULT 0,
        PRIMARY KEY (user_id, fecha)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS historial_banco (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        tipo TEXT,
        cantidad_origen INTEGER,
        cantidad_destino INTEGER,
        comision INTEGER,
        timestamp TIMESTAMP
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS ultimo_interes (
        user_id INTEGER PRIMARY KEY,
        fecha TIMESTAMP
    )''')
    conn.commit()
    conn.close()

_init_db()

# ==================== FUNCIONES AUXILIARES ====================
def _obtener_limites_hoy(user_id: int) -> Dict[str, int]:
    hoy = datetime.now().date().isoformat()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT creditos_convertidos, oro_convertido, eternium_convertido FROM limites_conversion WHERE user_id = ? AND fecha = ?', (user_id, hoy))
    row = c.fetchone()
    conn.close()
    if row:
        return {"creditos": row[0], "oro": row[1], "eternium": row[2]}
    return {"creditos": 0, "oro": 0, "eternium": 0}

def _registrar_transaccion(user_id: int, tipo: str, cantidad_origen: int, cantidad_destino: int, comision: int):
    hoy = datetime.now().date().isoformat()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT INTO historial_banco (user_id, tipo, cantidad_origen, cantidad_destino, comision, timestamp)
                 VALUES (?, ?, ?, ?, ?, ?)''',
              (user_id, tipo, cantidad_origen, cantidad_destino, comision, datetime.now().isoformat()))
    if tipo == "oro_a_et":
        c.execute('''INSERT INTO limites_conversion (user_id, fecha, oro_convertido) VALUES (?, ?, ?)
                     ON CONFLICT(user_id, fecha) DO UPDATE SET oro_convertido = oro_convertido + ?''',
                  (user_id, hoy, cantidad_origen, cantidad_origen))
    elif tipo == "et_a_oro":
        c.execute('''INSERT INTO limites_conversion (user_id, fecha, eternium_convertido) VALUES (?, ?, ?)
                     ON CONFLICT(user_id, fecha) DO UPDATE SET eternium_convertido = eternium_convertido + ?''',
                  (user_id, hoy, cantidad_origen, cantidad_origen))
    elif tipo == "credito_a_et":
        c.execute('''INSERT INTO limites_conversion (user_id, fecha, creditos_convertidos) VALUES (?, ?, ?)
                     ON CONFLICT(user_id, fecha) DO UPDATE SET creditos_convertidos = creditos_convertidos + ?''',
                  (user_id, hoy, cantidad_origen, cantidad_origen))
    conn.commit()
    conn.close()

def _puede_intercambiar(user_id: int, tipo: str, cantidad: int) -> Tuple[bool, str]:
    limites = _obtener_limites_hoy(user_id)
    if tipo == "credito_a_et":
        usado = limites["creditos"]
        if usado + cantidad > LIMITE_DIARIO_CREDITOS:
            return False, f"Límite diario de créditos alcanzado. Puedes cambiar hasta {LIMITE_DIARIO_CREDITOS - usado} créditos hoy."
    elif tipo == "oro_a_et":
        usado = limites["oro"]
        if usado + cantidad > LIMITE_DIARIO_ORO:
            return False, f"Límite diario de oro alcanzado. Puedes cambiar hasta {LIMITE_DIARIO_ORO - usado} oro hoy."
    elif tipo == "et_a_oro":
        usado = limites["eternium"]
        if usado + cantidad > LIMITE_DIARIO_ETERNIUM:
            return False, f"Límite diario de eternium alcanzado. Puedes cambiar hasta {LIMITE_DIARIO_ETERNIUM - usado} eternium hoy."
    return True, ""

def aplicar_comision_y_bonificacion(cantidad_original: int, es_salida_eternium: bool) -> Tuple[int, int]:
    comision = int(cantidad_original * COMISION_PORCENTAJE / 100.0)
    cantidad_despues_comision = cantidad_original - comision
    if es_salida_eternium and cantidad_original >= UMBRAL_BONIFICACION_ETERNIUM:
        bonificacion = int(cantidad_despues_comision * BONIFICACION_PORCENTAJE / 100.0)
        cantidad_final = cantidad_despues_comision + bonificacion
    else:
        cantidad_final = cantidad_despues_comision
    return cantidad_final, comision

# ==================== MENÚ PRINCIPAL ====================
async def banco_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if db_helper.esta_marcado(user_id):
        await update.effective_message.reply_text("❌ Estás marcado. No puedes usar el banco hasta que pagues rescate con /pagar_rescate.")
        return
    if not _en_ciudad(user_id):
        await update.effective_message.reply_text("🏙️ El banco solo está disponible dentro de las ciudades. Vuelve a la ciudad para usar este servicio.")
        return
    saldos = economia.obtener_saldos(user_id)
    limites = _obtener_limites_hoy(user_id)
    texto = (
        "🏦 *Banco Central de Aethelgard*\n\n"
        f"🪙 Oro: {saldos['oro']}\n"
        f"💎 Eternium: {saldos['eternium']}\n"
        f"✨ Créditos: {saldos['creditos_vacio']}\n\n"
        f"*Tasas vigentes*\n"
        f"{ORO_A_ETERNIUM_TASA} Oro → 1 Eternium\n"
        f"1 Eternium → {ETERNIUM_A_ORO_TASA} Oro\n"
        f"1 Crédito → {CREDITO_A_ETERNIUM_TASA} Eternium (se elimina el crédito)\n\n"
        f"*Límites diarios restantes*\n"
        f"Oro: {LIMITE_DIARIO_ORO - limites['oro']}\n"
        f"Eternium: {LIMITE_DIARIO_ETERNIUM - limites['eternium']}\n"
        f"Créditos: {LIMITE_DIARIO_CREDITOS - limites['creditos']}\n\n"
        f"Comisión: {COMISION_PORCENTAJE}%\n"
        f"Bonificación: +{BONIFICACION_PORCENTAJE}% al recibir {UMBRAL_BONIFICACION_ETERNIUM}+ eternium\n\n"
        "¿Qué deseas hacer?"
    )
    keyboard = [
        [InlineKeyboardButton("⬇️ Oro → Eternium", callback_data="banco_oro_a_et")],
        [InlineKeyboardButton("⬆️ Eternium → Oro", callback_data="banco_et_a_oro")],
        [InlineKeyboardButton("💸 Créditos → Eternium", callback_data="banco_creditos_a_et")],
        [InlineKeyboardButton("📜 Historial", callback_data="banco_historial")],
        [InlineKeyboardButton("📊 Mis estadísticas", callback_data="banco_estadisticas")],
        [InlineKeyboardButton("❌ Cerrar", callback_data="banco_cerrar")]
    ]
    await update.effective_message.reply_text(texto, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    try:
        import guia_contextual as _gc
        await _gc.enviar(user_id, context, "banco_menu")
    except Exception:
        pass

# ==================== ORO → ETERNIO (conversación) ====================
async def inicio_oro_a_et(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("¿Cuánto oro deseas cambiar a eternium? (Escribe un número o 'todo'):")
    return ESP_ORO

async def recibir_cantidad_oro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    texto = update.message.text.strip()
    saldos = economia.obtener_saldos(user_id)
    if texto.lower() == "todo":
        cantidad_oro = saldos["oro"]
    else:
        try:
            cantidad_oro = int(texto)
        except ValueError:
            await update.effective_message.reply_text("Por favor, ingresa un número entero o 'todo'.")
            return ESP_ORO
    if cantidad_oro <= 0:
        await update.effective_message.reply_text("La cantidad debe ser positiva.")
        return ESP_ORO
    puede, msg = _puede_intercambiar(user_id, "oro_a_et", cantidad_oro)
    if not puede:
        await update.effective_message.reply_text(msg)
        return ESP_ORO
    if cantidad_oro > saldos["oro"]:
        await update.effective_message.reply_text(f"No tienes suficiente oro. Tienes {saldos['oro']}.")
        return ESP_ORO
    et_bruto = cantidad_oro // ORO_A_ETERNIUM_TASA
    if et_bruto == 0:
        await update.effective_message.reply_text(f"Mínimo {ORO_A_ETERNIUM_TASA} oro para obtener 1 eternium.")
        return ESP_ORO
    et_final, comision = aplicar_comision_y_bonificacion(et_bruto, es_salida_eternium=True)
    context.user_data["cambio"] = {
        "tipo": "oro_a_et",
        "origen": cantidad_oro,
        "destino": et_final,
        "comision": comision
    }
    keyboard = [[InlineKeyboardButton("✅ Confirmar", callback_data="confirmar_cambio"), InlineKeyboardButton("❌ Cancelar", callback_data="cancelar_cambio")]]
    await update.effective_message.reply_text(
        f"Vas a cambiar *{cantidad_oro} oro*.\n"
        f"Recibirás *{et_final} eternium* (comisión: {comision}).\n"
        f"¿Confirmas la operación?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    return ConversationHandler.END

# ==================== ETERNIO → ORO (conversación) ====================
async def inicio_et_a_oro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("¿Cuánto eternium deseas cambiar a oro? (Escribe un número entero):")
    return ESP_ETERNIUM

async def recibir_cantidad_eternium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        cantidad_et = int(update.message.text.strip())
    except ValueError:
        await update.effective_message.reply_text("Por favor, ingresa un número entero.")
        return ESP_ETERNIUM
    if cantidad_et <= 0:
        await update.effective_message.reply_text("La cantidad debe ser positiva.")
        return ESP_ETERNIUM
    puede, msg = _puede_intercambiar(user_id, "et_a_oro", cantidad_et)
    if not puede:
        await update.effective_message.reply_text(msg)
        return ESP_ETERNIUM
    saldos = economia.obtener_saldos(user_id)
    if cantidad_et > saldos["eternium"]:
        await update.effective_message.reply_text(f"No tienes suficiente eternium. Tienes {saldos['eternium']}.")
        return ESP_ETERNIUM
    oro_bruto = cantidad_et * ETERNIO_A_ORO_TASA
    oro_final, comision = aplicar_comision_y_bonificacion(oro_bruto, es_salida_eternium=False)
    context.user_data["cambio"] = {
        "tipo": "et_a_oro",
        "origen": cantidad_et,
        "destino": oro_final,
        "comision": comision
    }
    keyboard = [[InlineKeyboardButton("✅ Confirmar", callback_data="confirmar_cambio"), InlineKeyboardButton("❌ Cancelar", callback_data="cancelar_cambio")]]
    await update.effective_message.reply_text(
        f"Vas a cambiar *{cantidad_et} eternium*.\n"
        f"Recibirás *{oro_final} oro* (comisión: {comision}).\n"
        f"¿Confirmas la operación?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    return ConversationHandler.END

# ==================== CRÉDITOS → ETERNIO (conversación) ====================
async def inicio_creditos_a_et(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("¿Cuántos créditos deseas convertir a eternium? (Escribe un número entero):")
    return ESP_CREDITOS

async def recibir_cantidad_creditos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        cantidad_cr = int(update.message.text.strip())
    except ValueError:
        await update.effective_message.reply_text("Por favor, ingresa un número entero.")
        return ESP_CREDITOS
    if cantidad_cr <= 0:
        await update.effective_message.reply_text("La cantidad debe ser positiva.")
        return ESP_CREDITOS
    puede, msg = _puede_intercambiar(user_id, "credito_a_et", cantidad_cr)
    if not puede:
        await update.effective_message.reply_text(msg)
        return ESP_CREDITOS
    saldos = economia.obtener_saldos(user_id)
    if cantidad_cr > saldos["creditos_vacio"]:
        await update.effective_message.reply_text(f"No tienes suficientes créditos. Tienes {saldos['creditos_vacio']}.")
        return ESP_CREDITOS
    et_bruto = cantidad_cr * CREDITO_A_ETERNIUM_TASA
    et_final, comision = aplicar_comision_y_bonificacion(et_bruto, es_salida_eternium=True)
    context.user_data["cambio"] = {
        "tipo": "credito_a_et",
        "origen": cantidad_cr,
        "destino": et_final,
        "comision": comision
    }
    keyboard = [[InlineKeyboardButton("✅ Confirmar", callback_data="confirmar_cambio"), InlineKeyboardButton("❌ Cancelar", callback_data="cancelar_cambio")]]
    await update.effective_message.reply_text(
        f"Vas a convertir *{cantidad_cr} créditos*.\n"
        f"Recibirás *{et_final} eternium* (comisión: {comision}).\n"
        f"*Los créditos serán eliminados del juego.*\n"
        f"¿Confirmas la operación?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    return ConversationHandler.END

# ==================== CONFIRMACIÓN / CANCELACIÓN GENÉRICA ====================
async def confirmar_cambio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    datos = context.user_data.get("cambio")
    if not datos:
        await query.edit_message_text("Error: no hay cambio pendiente.")
        return
    tipo = datos["tipo"]
    origen = datos["origen"]
    destino = datos["destino"]
    comision = datos["comision"]
    exito = False
    if tipo == "oro_a_et":
        if economia.modificar_saldo(user_id, "oro", -origen, f"cambio a eternium (banco)"):
            economia.modificar_saldo(user_id, "eternium", destino, f"cambio desde oro (banco)")
            _registrar_transaccion(user_id, "oro_a_et", origen, destino, comision)
            exito = True
    elif tipo == "et_a_oro":
        if economia.modificar_saldo(user_id, "eternium", -origen, f"cambio a oro (banco)"):
            economia.modificar_saldo(user_id, "oro", destino, f"cambio desde eternium (banco)")
            _registrar_transaccion(user_id, "et_a_oro", origen, destino, comision)
            exito = True
    elif tipo == "credito_a_et":
        if economia.modificar_saldo(user_id, "creditos_vacio", -origen, f"conversión a eternium (banco)"):
            economia.modificar_saldo(user_id, "eternium", destino, f"conversión desde créditos (banco)")
            _registrar_transaccion(user_id, "credito_a_et", origen, destino, comision)
            exito = True
    if exito:
        await query.edit_message_text(f"✅ Operación completada. Recibiste {destino} {'eternium' if tipo!='et_a_oro' else 'oro'}.")
    else:
        await query.edit_message_text("❌ Error al realizar el cambio. Verifica tu saldo.")
    context.user_data.pop("cambio", None)
    await banco_menu(update, context)

async def cancelar_cambio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data.pop("cambio", None)
    await query.edit_message_text("Operación cancelada.")
    await banco_menu(update, context)

async def _banco_nav_cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fallback de navegación para ConversationHandlers del banco."""
    context.user_data.pop("cambio", None)
    text = (update.effective_message.text or "").strip() if update.effective_message else ""
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
    if update.effective_message:
        await update.effective_message.reply_text("❌ Operación cancelada.")
    return ConversationHandler.END

# ==================== HISTORIAL Y ESTADÍSTICAS ====================
async def cmd_historial(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''SELECT tipo, cantidad_origen, cantidad_destino, comision, timestamp FROM historial_banco
                 WHERE user_id = ? ORDER BY timestamp DESC LIMIT 10''', (user_id,))
    rows = c.fetchall()
    conn.close()
    if not rows:
        await update.effective_message.reply_text("No tienes transacciones en el banco.")
        return
    texto = "🏦 *Historial de transacciones (últimas 10)*\n\n"
    for tipo, orig, dest, com, ts in rows:
        if tipo == "oro_a_et":
            texto += f"• {orig} oro → {dest} eternium (comisión {com})\n"
        elif tipo == "et_a_oro":
            texto += f"• {orig} eternium → {dest} oro (comisión {com})\n"
        else:
            texto += f"• {orig} créditos → {dest} eternium (comisión {com})\n"
        texto += f"  _{ts[:19]}_\n\n"
    await update.effective_message.reply_text(texto, parse_mode="Markdown")

async def cmd_estadisticas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT SUM(cantidad_origen) FROM historial_banco WHERE user_id = ? AND tipo = "credito_a_et"', (user_id,))
    total_creditos = c.fetchone()[0] or 0
    c.execute('SELECT SUM(cantidad_origen) FROM historial_banco WHERE user_id = ? AND tipo = "oro_a_et"', (user_id,))
    total_oro = c.fetchone()[0] or 0
    c.execute('SELECT SUM(cantidad_origen) FROM historial_banco WHERE user_id = ? AND tipo = "et_a_oro"', (user_id,))
    total_et = c.fetchone()[0] or 0
    conn.close()
    texto = (f"📊 *Tus estadísticas en el banco*\n\n"
             f"💸 Créditos convertidos: {total_creditos}\n"
             f"🪙 Oro cambiado a eternium: {total_oro}\n"
             f"💎 Eternium cambiado a oro: {total_et}\n")
    await update.effective_message.reply_text(texto, parse_mode="Markdown")

# ==================== INTERÉS SEMANAL ====================
async def aplicar_interes_semanal(context: ContextTypes.DEFAULT_TYPE = None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    ahora = datetime.now()
    c.execute('SELECT user_id, eternium, creditos_vacio FROM jugadores')
    rows = c.fetchall()
    for user_id, eternium, creditos in rows:
        c.execute('SELECT fecha FROM ultimo_interes WHERE user_id = ?', (user_id,))
        row = c.fetchone()
        if row:
            try:
                ultimo = datetime.fromisoformat(row[0])
            except (ValueError, TypeError):
                ultimo = ahora - timedelta(days=8)
            if (ahora - ultimo).days < 7:
                continue
        if eternium >= SALDO_MINIMO_INTERES:
            interes_et = int(eternium * INTERES_SEMANAL_PORCENTAJE / 100.0)
            if interes_et > 0:
                economia.modificar_saldo(user_id, "eternium", interes_et, "interés semanal banco")
        if creditos >= SALDO_MINIMO_INTERES:
            interes_cr = int(creditos * INTERES_SEMANAL_PORCENTAJE / 100.0)
            if interes_cr > 0:
                economia.modificar_saldo(user_id, "creditos_vacio", interes_cr, "interés semanal banco")
        c.execute('INSERT OR REPLACE INTO ultimo_interes (user_id, fecha) VALUES (?, ?)', (user_id, ahora.isoformat()))
    conn.commit()
    conn.close()

# ==================== CIERRE Y NAVEGACIÓN ====================
async def banco_historial_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await cmd_historial(update, context)

async def banco_estadisticas_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await cmd_estadisticas(update, context)

async def banco_cerrar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("🏦 Banco cerrado. ¡Vuelve pronto!")

# ==================== REGISTRO DE HANDLERS ====================
def registrar_handlers(app):
    app.add_handler(CommandHandler("banco", banco_menu))
    app.add_handler(CommandHandler("banco_historial", cmd_historial))
    app.add_handler(CommandHandler("banco_stats", cmd_estadisticas))
    app.add_handler(CallbackQueryHandler(banco_historial_callback, pattern="^banco_historial$"))
    app.add_handler(CallbackQueryHandler(banco_estadisticas_callback, pattern="^banco_estadisticas$"))
    app.add_handler(CallbackQueryHandler(banco_cerrar, pattern="^banco_cerrar$"))
    _BANCO_NAV = [
        CommandHandler("cancel",     _banco_nav_cancelar),
        CommandHandler("ciudad",     _banco_nav_cancelar),
        CommandHandler("perfil",     _banco_nav_cancelar),
        CommandHandler("viajar",     _banco_nav_cancelar),
        CommandHandler("inventario", _banco_nav_cancelar),
        CommandHandler("gremio",     _banco_nav_cancelar),
        CommandHandler("start",      _banco_nav_cancelar),
        MessageHandler(filters.Regex("^(👤|🏙️?|🎒|✈️?|⚔️?|🏰|⛏️?|🔍|📋|📖)"), _banco_nav_cancelar),
    ]
    conv_oro = ConversationHandler(
        entry_points=[CallbackQueryHandler(inicio_oro_a_et, pattern="^banco_oro_a_et$")],
        states={ESP_ORO: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_cantidad_oro)]},
        fallbacks=_BANCO_NAV,
        allow_reentry=True,
    )
    conv_et = ConversationHandler(
        entry_points=[CallbackQueryHandler(inicio_et_a_oro, pattern="^banco_et_a_oro$")],
        states={ESP_ETERNIUM: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_cantidad_eternium)]},
        fallbacks=_BANCO_NAV,
        allow_reentry=True,
    )
    conv_cr = ConversationHandler(
        entry_points=[CallbackQueryHandler(inicio_creditos_a_et, pattern="^banco_creditos_a_et$")],
        states={ESP_CREDITOS: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_cantidad_creditos)]},
        fallbacks=_BANCO_NAV,
        allow_reentry=True,
    )
    app.add_handler(conv_oro)
    app.add_handler(conv_et)
    app.add_handler(conv_cr)
    app.add_handler(CallbackQueryHandler(confirmar_cambio, pattern="^confirmar_cambio$"))
    app.add_handler(CallbackQueryHandler(cancelar_cambio, pattern="^cancelar_cambio$"))
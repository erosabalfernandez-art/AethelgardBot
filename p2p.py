# p2p.py
# Mercado P2P de intercambio de monedas (Oro, Eternium, Créditos).
# Los jugadores publican ofertas con retención de saldo (escrow), expiración en 7 días.
# Al aceptar, se intercambian las monedas y se aplica una comisión del 1% sobre la cantidad ofrecida (se quema).

import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, ConversationHandler, MessageHandler, filters

import economia
import db_helper
from datos_zona import ZONAS

DB_PATH = "aethelgard.db"

_BOTONES_RAPIDOS = frozenset({
    "👤 Perfil", "🏙️ Ciudad", "🎒 Inventario", "✈️ Viajar",
    "⚔️ Combate", "🏰 Gremio", "⛏️ Recolectar", "🔍 Investigar",
    "🏰 Mazmorra", "📋 Comandos", "📖 Guía",
})

# ==================== CONSTANTES ====================
COMISION_PORCENTAJE = 1          # 1%
EXPIRACION_DIAS = 7
MAX_OFERTAS_POR_JUGADOR = 5

# Estados para la conversación de publicar oferta
(ESP_OFERTA_MONEDA_OFERECE, ESP_OFERTA_CANTIDAD_OFERECE, ESP_OFERTA_MONEDA_PIDE, ESP_OFERTA_CANTIDAD_PIDE, ESP_OFERTA_CONFIRMAR) = range(5)

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
    c.execute('''CREATE TABLE IF NOT EXISTS ofertas_p2p (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        vendedor_id INTEGER,
        ofrece_tipo TEXT,
        ofrece_cantidad INTEGER,
        pide_tipo TEXT,
        pide_cantidad INTEGER,
        fecha_creacion TIMESTAMP,
        fecha_expiracion TIMESTAMP,
        activa BOOLEAN DEFAULT 1
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS historial_p2p (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        vendedor_id INTEGER,
        comprador_id INTEGER,
        ofrece_tipo TEXT,
        ofrece_cantidad INTEGER,
        pide_tipo TEXT,
        pide_cantidad INTEGER,
        comision INTEGER,
        fecha TIMESTAMP
    )''')
    conn.commit()
    conn.close()

_init_db()

# ==================== FUNCIONES AUXILIARES ====================
def _validar_moneda(moneda: str) -> bool:
    return moneda in ("oro", "eternium", "creditos_vacio")

def _formatear_moneda(moneda: str) -> str:
    if moneda == "oro":
        return "🪙 Oro"
    elif moneda == "eternium":
        return "💎 Eternium"
    return "✨ Créditos"

def _obtener_ofertas_activas() -> List[Dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    ahora = datetime.now().isoformat()
    c.execute('SELECT * FROM ofertas_p2p WHERE activa = 1 AND fecha_expiracion > ?', (ahora,))
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def _obtener_ofertas_por_vendedor(vendedor_id: int) -> List[Dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM ofertas_p2p WHERE vendedor_id = ? AND activa = 1', (vendedor_id,))
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def _cancelar_oferta_interna(oferta_id: int, devolver_monedas: bool = True):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT vendedor_id, ofrece_tipo, ofrece_cantidad FROM ofertas_p2p WHERE id = ?', (oferta_id,))
    row = c.fetchone()
    if row:
        vendedor_id, tipo, cantidad = row
        if devolver_monedas:
            economia.modificar_saldo(vendedor_id, tipo, cantidad, f"devolución oferta cancelada #{oferta_id}")
    c.execute('UPDATE ofertas_p2p SET activa = 0 WHERE id = ?', (oferta_id,))
    conn.commit()
    conn.close()

async def _comprobar_expiracion(context=None):
    """Devuelve las monedas de ofertas expiradas. Debe ejecutarse periódicamente (en main)."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    ahora = datetime.now().isoformat()
    c.execute('SELECT id, vendedor_id, ofrece_tipo, ofrece_cantidad FROM ofertas_p2p WHERE activa = 1 AND fecha_expiracion <= ?', (ahora,))
    expiradas = c.fetchall()
    for oferta_id, vendedor_id, tipo, cantidad in expiradas:
        economia.modificar_saldo(vendedor_id, tipo, cantidad, f"devolución oferta expirada #{oferta_id}")
        db_helper.agregar_notificacion(vendedor_id,
            f"⏰ Tu oferta P2P #{oferta_id} expiró tras 7 días. "
            f"Se te devolvieron {cantidad} {_formatear_moneda(tipo)}.")
        c.execute('UPDATE ofertas_p2p SET activa = 0 WHERE id = ?', (oferta_id,))
    conn.commit()
    conn.close()

# ==================== COMANDO PRINCIPAL ====================
async def cmd_mercado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        import umbral_vacio as _uv
        if _uv.hay_escasez_activa():
            await update.effective_message.reply_text(
                "🔒 *El Mercado P2P está cerrado*\n\n"
                "La Escasez Global causada por la Noche del Vacío ha cerrado "
                "temporalmente el mercado P2P.\n"
                "Usa /corrupcion para ver el estado del evento.",
                parse_mode="Markdown"
            )
            return
    except Exception:
        pass
    if db_helper.esta_marcado(user_id):
        await update.effective_message.reply_text("❌ Estás marcado. No puedes usar el mercado P2P hasta que pagues rescate.")
        return
    if not _en_ciudad(user_id):
        await update.effective_message.reply_text("🏙️ El mercado P2P solo está disponible dentro de las ciudades. Vuelve a la ciudad para usarlo.")
        return
    keyboard = [
        [InlineKeyboardButton("📜 Ver ofertas", callback_data="p2p_ver")],
        [InlineKeyboardButton("➕ Publicar oferta", callback_data="p2p_publicar")],
        [InlineKeyboardButton("❌ Cancelar mis ofertas", callback_data="p2p_cancelar")],
        [InlineKeyboardButton("📋 Mis ofertas activas", callback_data="p2p_mis_ofertas")],
        [InlineKeyboardButton("📜 Historial de intercambios", callback_data="p2p_historial")],
        [InlineKeyboardButton("❌ Cerrar", callback_data="p2p_cerrar")]
    ]
    await update.effective_message.reply_text(
        "🏪 *Mercado P2P de Monedas*\n\n"
        "Intercambia Oro, Eternium o Créditos con otros jugadores.\n"
        "Las ofertas expiran en 7 días.\n"
        f"Comisión: {COMISION_PORCENTAJE}% sobre la cantidad ofrecida (se quema).\n\n"
        "Selecciona una opción:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

    try:
        import guia_contextual as _gc
        await _gc.enviar(user_id, context, "p2p_menu")
    except Exception:
        pass

# ==================== VER OFERTAS ====================
async def p2p_ver_ofertas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ofertas = _obtener_ofertas_activas()
    user_id = update.effective_user.id
    ofertas = [o for o in ofertas if o["vendedor_id"] != user_id]
    if not ofertas:
        await query.edit_message_text("No hay ofertas activas en este momento.")
        return
    texto = "📜 *Ofertas activas*\n\n"
    botones = []
    for oferta in ofertas[:10]:
        vendedor = db_helper.obtener_jugador(oferta["vendedor_id"])
        nombre_vendedor = vendedor.get("nombre_personaje", "Desconocido") if vendedor else "Desconocido"
        texto += f"👤 {nombre_vendedor}:\n"
        texto += f"  Ofrece: {oferta['ofrece_cantidad']} {_formatear_moneda(oferta['ofrece_tipo'])}\n"
        texto += f"  Pide: {oferta['pide_cantidad']} {_formatear_moneda(oferta['pide_tipo'])}\n\n"
        botones.append([InlineKeyboardButton(f"Aceptar oferta #{oferta['id']}", callback_data=f"p2p_aceptar_{oferta['id']}")])
    botones.append([InlineKeyboardButton("🔙 Volver", callback_data="p2p_volver")])
    await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(botones), parse_mode="Markdown")

# ==================== ACEPTAR OFERTA ====================
async def p2p_aceptar_oferta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    try:
        import guia_contextual as _gc
        await _gc.enviar(user_id, context, "p2p_oferta_aceptada")
    except Exception:
        pass
    try:
        oferta_id = int(query.data.split("_")[2])
    except (ValueError, IndexError):
        await query.edit_message_text("❌ Oferta no válida.")
        return
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT vendedor_id, ofrece_tipo, ofrece_cantidad, pide_tipo, pide_cantidad, activa FROM ofertas_p2p WHERE id = ?', (oferta_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        await query.edit_message_text("Oferta no encontrada.")
        return
    vendedor_id, ofrece_tipo, ofrece_cant, pide_tipo, pide_cant, activa = row
    if not activa:
        await query.edit_message_text("Esta oferta ya no está activa.")
        return
    if vendedor_id == user_id:
        await query.edit_message_text("No puedes aceptar tu propia oferta.")
        return
    saldos_comprador = economia.obtener_saldos(user_id)
    if saldos_comprador.get(pide_tipo, 0) < pide_cant:
        await query.edit_message_text(f"No tienes suficiente {_formatear_moneda(pide_tipo)} para aceptar esta oferta.")
        return
    comision = (ofrece_cant * COMISION_PORCENTAJE) // 100
    cantidad_comprador_recibe = ofrece_cant - comision
    if not economia.modificar_saldo(user_id, pide_tipo, -pide_cant, f"aceptar oferta #{oferta_id}"):
        await query.edit_message_text("Error al descontar monedas. Intenta de nuevo.")
        return
    economia.modificar_saldo(user_id, ofrece_tipo, cantidad_comprador_recibe, f"recibido de oferta #{oferta_id}")
    economia.modificar_saldo(vendedor_id, pide_tipo, pide_cant, f"venta por oferta #{oferta_id}")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('UPDATE ofertas_p2p SET activa = 0 WHERE id = ?', (oferta_id,))
    conn.commit()
    conn.close()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT INTO historial_p2p (vendedor_id, comprador_id, ofrece_tipo, ofrece_cantidad, pide_tipo, pide_cantidad, comision, fecha)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
              (vendedor_id, user_id, ofrece_tipo, ofrece_cant, pide_tipo, pide_cant, comision, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    db_helper.agregar_notificacion(vendedor_id, f"✅ Tu oferta #{oferta_id} ha sido aceptada. Recibiste {pide_cant} {_formatear_moneda(pide_tipo)}.")
    db_helper.agregar_notificacion(user_id, f"✅ Aceptaste la oferta #{oferta_id}. Recibiste {cantidad_comprador_recibe} {_formatear_moneda(ofrece_tipo)} (comisión {comision} {_formatear_moneda(ofrece_tipo)}).")
    await query.edit_message_text(f"¡Intercambio completado! Recibiste {cantidad_comprador_recibe} {_formatear_moneda(ofrece_tipo)}.")

# ==================== PUBLICAR OFERTA (conversación) ====================
async def p2p_publicar_inicio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ofertas = _obtener_ofertas_por_vendedor(update.effective_user.id)
    if len(ofertas) >= MAX_OFERTAS_POR_JUGADOR:
        await query.edit_message_text(f"Ya tienes {MAX_OFERTAS_POR_JUGADOR} ofertas activas. Cancela alguna antes de publicar otra.")
        return
    keyboard = [
        [InlineKeyboardButton("🪙 Oro", callback_data="p2p_ofrece_oro")],
        [InlineKeyboardButton("💎 Eternium", callback_data="p2p_ofrece_eternium")],
        [InlineKeyboardButton("✨ Créditos del Vacío", callback_data="p2p_ofrece_creditos_vacio")]
    ]
    await query.edit_message_text("Selecciona la moneda que vas a OFRECER:", reply_markup=InlineKeyboardMarkup(keyboard))
    return ESP_OFERTA_MONEDA_OFERECE

async def p2p_ofrece_moneda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tipo = "_".join(query.data.split("_")[2:])
    context.user_data["ofrece_tipo"] = tipo
    await query.edit_message_text(f"Has elegido ofrecer {_formatear_moneda(tipo)}. ¿Qué cantidad ofreces? (número entero)")
    return ESP_OFERTA_CANTIDAD_OFERECE

async def p2p_ofrece_cantidad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.strip()
    if texto in _BOTONES_RAPIDOS:
        await p2p_cancelar_publicar(update, context)
        return ConversationHandler.END
    try:
        cantidad = int(texto)
    except ValueError:
        await update.effective_message.reply_text("Por favor, ingresa un número entero.")
        return ESP_OFERTA_CANTIDAD_OFERECE
    if cantidad <= 0:
        await update.effective_message.reply_text("La cantidad debe ser mayor a cero.")
        return ESP_OFERTA_CANTIDAD_OFERECE
    user_id = update.effective_user.id
    saldos = economia.obtener_saldos(user_id)
    tipo_ofrece = context.user_data["ofrece_tipo"]
    if saldos.get(tipo_ofrece, 0) < cantidad:
        await update.effective_message.reply_text(f"No tienes suficiente {_formatear_moneda(tipo_ofrece)}. Tienes {saldos[tipo_ofrece]}.")
        return ESP_OFERTA_CANTIDAD_OFERECE
    context.user_data["ofrece_cantidad"] = cantidad
    keyboard = []
    for moneda in ["oro", "eternium", "creditos_vacio"]:
        if moneda != tipo_ofrece:
            keyboard.append([InlineKeyboardButton(_formatear_moneda(moneda), callback_data=f"p2p_pide_{moneda}")])
    await update.effective_message.reply_text("¿Qué moneda quieres recibir a cambio?", reply_markup=InlineKeyboardMarkup(keyboard))
    return ESP_OFERTA_MONEDA_PIDE

async def p2p_pide_moneda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tipo = "_".join(query.data.split("_")[2:])
    context.user_data["pide_tipo"] = tipo
    await query.edit_message_text(f"Recibirás {_formatear_moneda(tipo)}. ¿Qué cantidad pides? (número entero)")
    return ESP_OFERTA_CANTIDAD_PIDE

async def p2p_pide_cantidad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.strip()
    if texto in _BOTONES_RAPIDOS:
        await p2p_cancelar_publicar(update, context)
        return ConversationHandler.END
    try:
        cantidad = int(texto)
    except ValueError:
        await update.effective_message.reply_text("Por favor, ingresa un número entero.")
        return ESP_OFERTA_CANTIDAD_PIDE
    if cantidad <= 0:
        await update.effective_message.reply_text("La cantidad debe ser mayor a cero.")
        return ESP_OFERTA_CANTIDAD_PIDE
    context.user_data["pide_cantidad"] = cantidad
    ofrece_tipo = context.user_data["ofrece_tipo"]
    ofrece_cant = context.user_data["ofrece_cantidad"]
    pide_tipo = context.user_data["pide_tipo"]
    pide_cant = context.user_data["pide_cantidad"]
    texto = f"*Resumen de la oferta*\n\n"
    texto += f"Ofreces: {ofrece_cant} {_formatear_moneda(ofrece_tipo)}\n"
    texto += f"Pides: {pide_cant} {_formatear_moneda(pide_tipo)}\n"
    texto += f"Comisión: {COMISION_PORCENTAJE}% sobre la cantidad ofrecida (se quema).\n"
    texto += f"Expira en {EXPIRACION_DIAS} días.\n\n"
    texto += "¿Publicar esta oferta?"
    keyboard = [[InlineKeyboardButton("✅ Sí, publicar", callback_data="p2p_confirmar"), InlineKeyboardButton("❌ Cancelar", callback_data="p2p_cancelar_publicar")]]
    await update.effective_message.reply_text(texto, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    return ESP_OFERTA_CONFIRMAR

async def p2p_confirmar_publicar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    try:
        import guia_contextual as _gc
        await _gc.enviar(user_id, context, "p2p_oferta_creada")
    except Exception:
        pass
    ofrece_tipo = context.user_data["ofrece_tipo"]
    ofrece_cant = context.user_data["ofrece_cantidad"]
    pide_tipo = context.user_data["pide_tipo"]
    pide_cant = context.user_data["pide_cantidad"]
    if not economia.modificar_saldo(user_id, ofrece_tipo, -ofrece_cant, f"retención por oferta P2P"):
        await query.edit_message_text("Error al retener las monedas. No se pudo publicar la oferta.")
        return
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    fecha_creacion = datetime.now()
    fecha_expiracion = fecha_creacion + timedelta(days=EXPIRACION_DIAS)
    c.execute('''INSERT INTO ofertas_p2p (vendedor_id, ofrece_tipo, ofrece_cantidad, pide_tipo, pide_cantidad, fecha_creacion, fecha_expiracion, activa)
                 VALUES (?, ?, ?, ?, ?, ?, ?, 1)''',
              (user_id, ofrece_tipo, ofrece_cant, pide_tipo, pide_cant, fecha_creacion.isoformat(), fecha_expiracion.isoformat()))
    conn.commit()
    conn.close()
    await query.edit_message_text(f"✅ Oferta publicada. Recibirás notificación cuando alguien la acepte o expire en {EXPIRACION_DIAS} días.")
    context.user_data.clear()
    return ConversationHandler.END

async def p2p_cancelar_publicar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        # Cancelación explícita por botón inline
        await query.answer()
        context.user_data.clear()
        await query.edit_message_text("❌ Publicación cancelada.")
        return ConversationHandler.END
    # Cancelación por navegación — redirigir al destino
    context.user_data.clear()
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
    await update.effective_message.reply_text("❌ Publicación cancelada.")
    return ConversationHandler.END

# ==================== CANCELAR MIS OFERTAS ====================
async def p2p_cancelar_mis_ofertas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    ofertas = _obtener_ofertas_por_vendedor(user_id)
    if not ofertas:
        await query.edit_message_text("No tienes ofertas activas.")
        return
    texto = "Tus ofertas activas:\n\n"
    botones = []
    for oferta in ofertas:
        texto += f"#{oferta['id']}: {oferta['ofrece_cantidad']} {_formatear_moneda(oferta['ofrece_tipo'])} → {oferta['pide_cantidad']} {_formatear_moneda(oferta['pide_tipo'])}\n"
        botones.append([InlineKeyboardButton(f"Cancelar oferta #{oferta['id']}", callback_data=f"p2p_cancelar_oferta_{oferta['id']}")])
    botones.append([InlineKeyboardButton("🔙 Volver", callback_data="p2p_volver")])
    await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(botones), parse_mode="Markdown")

async def p2p_cancelar_oferta_individual(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        oferta_id = int(query.data.split("_")[3])
    except (ValueError, IndexError):
        await query.edit_message_text("❌ Oferta no válida.")
        return
    _cancelar_oferta_interna(oferta_id, devolver_monedas=True)
    await query.edit_message_text(f"Oferta #{oferta_id} cancelada. Las monedas retenidas te han sido devueltas.")
    await p2p_cancelar_mis_ofertas(update, context)

# ==================== MIS OFERTAS ACTIVAS ====================
async def p2p_mis_ofertas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    ofertas = _obtener_ofertas_por_vendedor(user_id)
    if not ofertas:
        await query.edit_message_text("No tienes ofertas activas.")
        return
    texto = "📋 *Tus ofertas activas*\n\n"
    for oferta in ofertas:
        texto += f"ID {oferta['id']}: {oferta['ofrece_cantidad']} {_formatear_moneda(oferta['ofrece_tipo'])} → {oferta['pide_cantidad']} {_formatear_moneda(oferta['pide_tipo'])}\n"
        texto += f"  Expira: {oferta['fecha_expiracion'][:10]}\n"
    texto += "\nUsa 'Cancelar mis ofertas' para eliminarlas."
    await query.edit_message_text(texto, parse_mode="Markdown")

# ==================== HISTORIAL ====================
async def p2p_historial(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''SELECT vendedor_id, comprador_id, ofrece_tipo, ofrece_cantidad, pide_tipo, pide_cantidad, comision, fecha
                 FROM historial_p2p WHERE vendedor_id = ? OR comprador_id = ? ORDER BY fecha DESC LIMIT 10''', (user_id, user_id))
    rows = c.fetchall()
    conn.close()
    if not rows:
        await query.edit_message_text("No tienes intercambios registrados.")
        return
    texto = "📜 *Últimos intercambios*\n\n"
    for row in rows:
        vendedor, comprador, of_tipo, of_cant, pi_tipo, pi_cant, comision, fecha = row
        if vendedor == user_id:
            texto += f"Vendiste {of_cant} {_formatear_moneda(of_tipo)} a cambio de {pi_cant} {_formatear_moneda(pi_tipo)}.\n"
        else:
            texto += f"Compraste {of_cant - comision} {_formatear_moneda(of_tipo)} (comisión {comision}) pagando {pi_cant} {_formatear_moneda(pi_tipo)}.\n"
        texto += f"  {fecha[:19]}\n\n"
    await query.edit_message_text(texto, parse_mode="Markdown")

# ==================== NAVEGACIÓN ====================
async def p2p_volver(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await cmd_mercado(update, context)

async def p2p_cerrar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("🔒 Mercado P2P cerrado. ¡Vuelve pronto!")

# ==================== REGISTRO DE HANDLERS ====================
def registrar_handlers(app):
    app.add_handler(CommandHandler("mercado", cmd_mercado))
    app.add_handler(CallbackQueryHandler(p2p_ver_ofertas, pattern="^p2p_ver$"))
    app.add_handler(CallbackQueryHandler(p2p_aceptar_oferta, pattern="^p2p_aceptar_"))
    app.add_handler(CallbackQueryHandler(p2p_cancelar_mis_ofertas, pattern="^p2p_cancelar$"))
    app.add_handler(CallbackQueryHandler(p2p_cancelar_oferta_individual, pattern="^p2p_cancelar_oferta_"))
    app.add_handler(CallbackQueryHandler(p2p_mis_ofertas, pattern="^p2p_mis_ofertas$"))
    app.add_handler(CallbackQueryHandler(p2p_historial, pattern="^p2p_historial$"))
    app.add_handler(CallbackQueryHandler(p2p_volver, pattern="^p2p_volver$"))
    app.add_handler(CallbackQueryHandler(p2p_cerrar, pattern="^p2p_cerrar$"))
    conv_publicar = ConversationHandler(
        entry_points=[CallbackQueryHandler(p2p_publicar_inicio, pattern="^p2p_publicar$")],
        states={
            ESP_OFERTA_MONEDA_OFERECE: [CallbackQueryHandler(p2p_ofrece_moneda, pattern="^p2p_ofrece_")],
            ESP_OFERTA_CANTIDAD_OFERECE: [MessageHandler(filters.TEXT & ~filters.COMMAND, p2p_ofrece_cantidad)],
            ESP_OFERTA_MONEDA_PIDE: [CallbackQueryHandler(p2p_pide_moneda, pattern="^p2p_pide_")],
            ESP_OFERTA_CANTIDAD_PIDE: [MessageHandler(filters.TEXT & ~filters.COMMAND, p2p_pide_cantidad)],
            ESP_OFERTA_CONFIRMAR: [CallbackQueryHandler(p2p_confirmar_publicar, pattern="^p2p_confirmar$"),
                                   CallbackQueryHandler(p2p_cancelar_publicar, pattern="^p2p_cancelar_publicar$")]
        },
        fallbacks=[
            CommandHandler("cancel",     p2p_cancelar_publicar),
            CommandHandler("ciudad",     p2p_cancelar_publicar),
            CommandHandler("perfil",     p2p_cancelar_publicar),
            CommandHandler("viajar",     p2p_cancelar_publicar),
            CommandHandler("inventario", p2p_cancelar_publicar),
            CommandHandler("gremio",     p2p_cancelar_publicar),
            CommandHandler("start",      p2p_cancelar_publicar),
            MessageHandler(filters.Regex("^(👤|🏙️?|🎒|✈️?|⚔️?|🏰|⛏️?|🔍|📋|📖)"), p2p_cancelar_publicar),
        ]
    )
    app.add_handler(conv_publicar)
import os
import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, CommandHandler, CallbackQueryHandler,
    ConversationHandler, MessageHandler, filters,
)
import db_helper

DB_PATH = "aethelgard.db"

# Textos del teclado rápido — si el usuario los envía durante una conversación, se cancela
_BOTONES_RAPIDOS = frozenset({
    "👤 Perfil", "🏙️ Ciudad", "🎒 Inventario", "✈️ Viajar",
    "⚔️ Combate", "🏰 Gremio", "⛏️ Recolectar", "🔍 Investigar",
    "🏰 Mazmorra", "📋 Comandos", "📖 Guía",
})

# Estados de la conversacion
BOLSA_TIPO  = 0
BOLSA_MONTO = 1

# Tasas por defecto
_TASA_ORO_A_ETERNIUM      = 500   # 500 oro compran 1 eternium
_TASA_ETERNIUM_A_ORO      = 300   # 1 eternium vende por 300 oro
_TASA_CREDITO_A_ETERNIUM  = 2     # 1 credito compra 2 eternium (antes era 50 — roto)

TIPOS = {
    "oro_eternium":     {"label": "Oro a Eternium",      "fuente": "oro",            "destino": "eternium"},
    "eternium_oro":     {"label": "Eternium a Oro",      "fuente": "eternium",       "destino": "oro"},
    "credito_eternium": {"label": "Creditos a Eternium", "fuente": "creditos_vacio", "destino": "eternium"},
}

NOMBRES_MONEDA = {
    "oro":            "Oro",
    "eternium":       "Eternium",
    "creditos_vacio": "Creditos del Vacio",
}

# ─── BD ──────────────────────────────────────────────────────────────────────

def _init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS bolsa_config (
        clave TEXT PRIMARY KEY,
        valor REAL NOT NULL
    )""")
    for k, v in [
        ("tasa_oro_a_eternium",     _TASA_ORO_A_ETERNIUM),
        ("tasa_eternium_a_oro",     _TASA_ETERNIUM_A_ORO),
        ("tasa_credito_a_eternium", _TASA_CREDITO_A_ETERNIUM),
    ]:
        c.execute("INSERT OR IGNORE INTO bolsa_config (clave, valor) VALUES (?, ?)", (k, v))
    conn.commit()
    conn.close()


def _tasas() -> dict:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT clave, valor FROM bolsa_config")
    rows = c.fetchall()
    conn.close()
    return {k: v for k, v in rows}


def _calcular(tipo: str, cantidad: int, tasas: dict) -> int:
    if tipo == "oro_eternium":
        tasa = tasas.get("tasa_oro_a_eternium", _TASA_ORO_A_ETERNIUM)
        return max(0, int(cantidad / tasa))
    if tipo == "eternium_oro":
        tasa = tasas.get("tasa_eternium_a_oro", _TASA_ETERNIUM_A_ORO)
        return max(0, int(cantidad * tasa))
    if tipo == "credito_eternium":
        tasa = tasas.get("tasa_credito_a_eternium", _TASA_CREDITO_A_ETERNIUM)
        return max(0, int(cantidad * tasa))
    return 0

# ─── TEXTOS / TECLADOS ───────────────────────────────────────────────────────

def _texto_menu(tasas: dict) -> str:
    oe  = int(tasas.get("tasa_oro_a_eternium",     _TASA_ORO_A_ETERNIUM))
    eo  = int(tasas.get("tasa_eternium_a_oro",     _TASA_ETERNIUM_A_ORO))
    ce  = int(tasas.get("tasa_credito_a_eternium", _TASA_CREDITO_A_ETERNIUM))
    return (
        "*Bolsa de Valores de Aethelgard*\n\n"
        "*Tasas actuales:*\n"
        f"Oro a Eternium: {oe} Oro = 1 Eternium\n"
        f"Eternium a Oro: 1 Eternium = {eo} Oro\n"
        f"Creditos a Eternium: 1 Credito = {ce} Eternium\n\n"
        "El bot nunca entrega Creditos del Vacio.\n"
        "Los creditos solo se obtienen depositando USDT\n"
        "o comprando a otros jugadores via subastas.\n\n"
        "Selecciona el intercambio:"
    )


def _teclado_menu(tasas: dict) -> InlineKeyboardMarkup:
    oe = int(tasas.get("tasa_oro_a_eternium",     _TASA_ORO_A_ETERNIUM))
    eo = int(tasas.get("tasa_eternium_a_oro",     _TASA_ETERNIUM_A_ORO))
    ce = int(tasas.get("tasa_credito_a_eternium", _TASA_CREDITO_A_ETERNIUM))
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"Oro a Eternium  ({oe} Oro = 1 Et)",      callback_data="bolsa_tipo_oro_eternium")],
        [InlineKeyboardButton(f"Eternium a Oro  (1 Et = {eo} Oro)",      callback_data="bolsa_tipo_eternium_oro")],
        [InlineKeyboardButton(f"Creditos a Eternium  (1 Cred = {ce} Et)", callback_data="bolsa_tipo_credito_eternium")],
        [InlineKeyboardButton("Cancelar", callback_data="bolsa_cancelar")],
    ])

# ─── HANDLERS ────────────────────────────────────────────────────────────────

async def _abrir_bolsa_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        import umbral_vacio as _uv
        if _uv.hay_escasez_activa():
            await update.effective_message.reply_text(
                "🔒 *La Bolsa de Valores está cerrada*\n\n"
                "La Escasez Global causada por la Noche del Vacío ha cerrado "
                "temporalmente la bolsa.\nUsa /corrupcion para ver el estado.",
                parse_mode="Markdown"
            )
            return ConversationHandler.END
    except Exception:
        pass
    jug = db_helper.obtener_jugador(update.effective_user.id)
    if not jug:
        await update.effective_message.reply_text("Primero crea un personaje con /start.")
        return ConversationHandler.END
    t = _tasas()
    await update.effective_message.reply_text(_texto_menu(t), reply_markup=_teclado_menu(t), parse_mode="Markdown")
    return BOLSA_TIPO


async def _abrir_bolsa_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    jug = db_helper.obtener_jugador(query.from_user.id)
    if not jug:
        await query.edit_message_text("Primero crea un personaje con /start.")
        return ConversationHandler.END
    t = _tasas()
    await query.edit_message_text(_texto_menu(t), reply_markup=_teclado_menu(t), parse_mode="Markdown")
    return BOLSA_TIPO


async def _elegir_tipo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tipo = query.data.replace("bolsa_tipo_", "")
    info = TIPOS.get(tipo)
    if not info:
        await query.edit_message_text("Opcion no valida.")
        return ConversationHandler.END

    user_id = query.from_user.id
    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        await query.edit_message_text("Error: personaje no encontrado.")
        return ConversationHandler.END

    fuente     = info["fuente"]
    saldo      = jug.get(fuente, 0)
    nombre_src = NOMBRES_MONEDA[fuente]
    nombre_dst = NOMBRES_MONEDA[info["destino"]]

    t = _tasas()
    if tipo == "oro_eternium":
        tasa_txt = f"{int(t.get('tasa_oro_a_eternium', _TASA_ORO_A_ETERNIUM))} Oro = 1 Eternium"
    elif tipo == "eternium_oro":
        tasa_txt = f"1 Eternium = {int(t.get('tasa_eternium_a_oro', _TASA_ETERNIUM_A_ORO))} Oro"
    else:
        tasa_txt = f"1 Credito = {int(t.get('tasa_credito_a_eternium', _TASA_CREDITO_A_ETERNIUM))} Eternium"

    context.user_data.update({
        "bolsa_tipo":        tipo,
        "bolsa_fuente":      fuente,
        "bolsa_saldo":       saldo,
        "bolsa_nombre_src":  nombre_src,
        "bolsa_nombre_dst":  nombre_dst,
    })

    try:
        await query.edit_message_text(
            f"*{info['label']}*\n\n"
            f"Tasa: {tasa_txt}\n"
            f"Tu saldo: *{saldo:,} {nombre_src}*\n\n"
            f"Cuantos {nombre_src} quieres cambiar?\n"
            f"(escribe solo el numero)",
            parse_mode="Markdown"
        )
    except Exception:
        await query.edit_message_text(
            f"{info['label']}\n\n"
            f"Tasa: {tasa_txt}\n"
            f"Tu saldo: {saldo:,} {nombre_src}\n\n"
            f"Cuantos {nombre_src} quieres cambiar? (escribe el numero)"
        )
    return BOLSA_MONTO


async def _cancelar_por_nav(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancela la conversación y redirige al destino que el usuario quería usar."""
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
    await update.effective_message.reply_text("❌ Intercambio cancelado.")
    return ConversationHandler.END

async def _procesar_monto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.strip()
    if texto in _BOTONES_RAPIDOS:
        context.user_data.clear()
        await update.effective_message.reply_text("❌ Intercambio cancelado. Usa /bolsa para iniciar uno nuevo.")
        return ConversationHandler.END
    texto = texto.replace(",", "").replace(".", "")
    tipo       = context.user_data.get("bolsa_tipo")
    saldo      = context.user_data.get("bolsa_saldo", 0)
    nombre_src = context.user_data.get("bolsa_nombre_src", "moneda")
    nombre_dst = context.user_data.get("bolsa_nombre_dst", "moneda")

    try:
        cantidad = int(texto)
        if cantidad <= 0:
            raise ValueError
    except ValueError:
        await update.effective_message.reply_text("Escribe un numero entero mayor que 0.")
        return BOLSA_MONTO

    if cantidad > saldo:
        await update.effective_message.reply_text(
            f"No tienes suficiente {nombre_src}. Tienes: {saldo:,}."
        )
        return BOLSA_MONTO

    t = _tasas()
    resultado = _calcular(tipo, cantidad, t)
    if resultado <= 0:
        await update.effective_message.reply_text(
            f"La cantidad es demasiado pequeña para ese intercambio. "
            f"Intenta con una cantidad mayor."
        )
        return BOLSA_MONTO

    context.user_data["bolsa_cantidad"]  = cantidad
    context.user_data["bolsa_resultado"] = resultado

    teclado = InlineKeyboardMarkup([
        [InlineKeyboardButton("Confirmar", callback_data="bolsa_confirmar"),
         InlineKeyboardButton("Cancelar",  callback_data="bolsa_cancelar")],
    ])
    try:
        await update.effective_message.reply_text(
            f"*Resumen del intercambio:*\n\n"
            f"Entregas: *{cantidad:,} {nombre_src}*\n"
            f"Recibes:  *{resultado:,} {nombre_dst}*\n\n"
            f"Confirmas?",
            reply_markup=teclado,
            parse_mode="Markdown"
        )
    except Exception:
        await update.effective_message.reply_text(
            f"Entregas {cantidad:,} {nombre_src} | Recibes {resultado:,} {nombre_dst}",
            reply_markup=teclado
        )
    return BOLSA_MONTO


async def _confirmar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    tipo       = context.user_data.get("bolsa_tipo")
    cantidad   = context.user_data.get("bolsa_cantidad", 0)
    resultado  = context.user_data.get("bolsa_resultado", 0)
    nombre_src = context.user_data.get("bolsa_nombre_src", "moneda")
    nombre_dst = context.user_data.get("bolsa_nombre_dst", "moneda")
    fuente     = context.user_data.get("bolsa_fuente")

    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        await query.edit_message_text("Error: personaje no encontrado.")
        return ConversationHandler.END

    if jug.get(fuente, 0) < cantidad:
        await query.edit_message_text(f"Ya no tienes suficiente {nombre_src}.")
        return ConversationHandler.END

    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()
    try:
        if tipo == "oro_eternium":
            c.execute(
                "UPDATE jugadores SET oro = oro - ?, eternium = eternium + ? WHERE user_id = ?",
                (cantidad, resultado, user_id)
            )
        elif tipo == "eternium_oro":
            c.execute(
                "UPDATE jugadores SET eternium = eternium - ?, oro = oro + ? WHERE user_id = ?",
                (cantidad, resultado, user_id)
            )
        elif tipo == "credito_eternium":
            c.execute(
                "UPDATE jugadores SET creditos_vacio = creditos_vacio - ?, eternium = eternium + ? WHERE user_id = ?",
                (cantidad, resultado, user_id)
            )
        conn.commit()
    except Exception as e:
        conn.rollback()
        conn.close()
        await query.edit_message_text(f"Error al procesar el intercambio: {e}")
        return ConversationHandler.END
    conn.close()

    jug2    = db_helper.obtener_jugador(user_id)
    saldo_txt = (
        f"Oro: {jug2.get('oro', 0):,}  |  "
        f"Eternium: {jug2.get('eternium', 0):,}  |  "
        f"Creditos: {jug2.get('creditos_vacio', 0):,}"
    )
    try:
        await query.edit_message_text(
            f"*Intercambio realizado con exito*\n\n"
            f"Entregaste: *{cantidad:,} {nombre_src}*\n"
            f"Recibiste:  *{resultado:,} {nombre_dst}*\n\n"
            f"Saldo: {saldo_txt}",
            parse_mode="Markdown"
        )
    except Exception:
        await query.edit_message_text(
            f"Intercambio OK: -{cantidad:,} {nombre_src} | +{resultado:,} {nombre_dst}\n{saldo_txt}"
        )
    context.user_data.clear()
    return ConversationHandler.END


async def _cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    try:
        await query.edit_message_text("Intercambio cancelado.")
    except Exception:
        pass
    return ConversationHandler.END

# ─── ADMIN ───────────────────────────────────────────────────────────────────

async def cmd_bolsa_admin_tasa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    superadmin_id = int(os.environ.get("SUPERADMIN_ID", 0))
    user_id = update.effective_user.id
    jug = db_helper.obtener_jugador(user_id)
    try:
        import superadmin as _sa
        es_admin = _sa._nivel_admin(user_id) >= 1
    except Exception:
        es_admin = (user_id == superadmin_id)
    if not es_admin:
        await update.effective_message.reply_text("Sin permisos.")
        return

    args = context.args if context.args else []
    claves = {
        "oro_eternium":     "tasa_oro_a_eternium",
        "eternium_oro":     "tasa_eternium_a_oro",
        "credito_eternium": "tasa_credito_a_eternium",
    }
    if len(args) < 2 or args[0] not in claves:
        t = _tasas()
        await update.effective_message.reply_text(
            f"Uso: /bolsa_admin_tasa <tipo> <valor>\n\n"
            f"Tipos: {', '.join(claves.keys())}\n\n"
            f"Tasas actuales:\n"
            f"oro_eternium = {int(t.get('tasa_oro_a_eternium', _TASA_ORO_A_ETERNIUM))}\n"
            f"eternium_oro = {int(t.get('tasa_eternium_a_oro', _TASA_ETERNIUM_A_ORO))}\n"
            f"credito_eternium = {int(t.get('tasa_credito_a_eternium', _TASA_CREDITO_A_ETERNIUM))}"
        )
        return

    try:
        valor = float(args[1])
        if valor <= 0:
            raise ValueError
    except ValueError:
        await update.effective_message.reply_text("El valor debe ser un numero positivo.")
        return

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO bolsa_config (clave, valor) VALUES (?, ?)", (claves[args[0]], valor))
    conn.commit()
    conn.close()
    await update.effective_message.reply_text(f"Tasa {args[0]} actualizada a {valor}.")


async def cmd_bolsa_ver_tasas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    t = _tasas()
    await update.effective_message.reply_text(
        f"Tasas de la Bolsa:\n"
        f"oro_eternium = {int(t.get('tasa_oro_a_eternium', _TASA_ORO_A_ETERNIUM))} Oro por 1 Eternium\n"
        f"eternium_oro = {int(t.get('tasa_eternium_a_oro', _TASA_ETERNIUM_A_ORO))} Oro por 1 Eternium vendido\n"
        f"credito_eternium = {int(t.get('tasa_credito_a_eternium', _TASA_CREDITO_A_ETERNIUM))} Eternium por 1 Credito"
    )

# ─── REGISTRO ────────────────────────────────────────────────────────────────

def registrar_handlers(app):
    _init_db()

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("bolsa", _abrir_bolsa_msg),
            CallbackQueryHandler(_abrir_bolsa_cb, pattern="^ciudad_bolsa$"),
        ],
        states={
            BOLSA_TIPO: [
                CallbackQueryHandler(_elegir_tipo,  pattern="^bolsa_tipo_"),
                CallbackQueryHandler(_cancelar,     pattern="^bolsa_cancelar$"),
            ],
            BOLSA_MONTO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _procesar_monto),
                CallbackQueryHandler(_confirmar, pattern="^bolsa_confirmar$"),
                CallbackQueryHandler(_cancelar,  pattern="^bolsa_cancelar$"),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(_cancelar, pattern="^bolsa_cancelar$"),
            CommandHandler("cancel",     _cancelar_por_nav),
            CommandHandler("ciudad",     _cancelar_por_nav),
            CommandHandler("perfil",     _cancelar_por_nav),
            CommandHandler("viajar",     _cancelar_por_nav),
            CommandHandler("inventario", _cancelar_por_nav),
            CommandHandler("gremio",     _cancelar_por_nav),
            CommandHandler("start",      _cancelar_por_nav),
            MessageHandler(filters.Regex("^(👤|🏙️?|🎒|✈️?|⚔️?|🏰|⛏️?|🔍|📋|📖)"), _cancelar_por_nav),
        ],
        per_message=False,
        allow_reentry=True,
    )
    app.add_handler(conv)
    app.add_handler(CommandHandler("bolsa_admin_tasa", cmd_bolsa_admin_tasa))
    app.add_handler(CommandHandler("bolsa_tasas",      cmd_bolsa_ver_tasas))

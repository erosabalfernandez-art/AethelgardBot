import db_helper
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler

# Zonas donde recolección está disponible (cargado dinámicamente desde el módulo correcto)
COLORES_SALVAJE = {"azul", "amarilla", "roja", "negra"}

# Módulos de recolección e investigación por color
_MOD_RECOL = {
    "azul":    "recoleccion_azul",
    "amarilla":"recoleccion_amarilla",
    "roja":    "recoleccion_roja",
    "negra":   "recoleccion_negra",
}
_MOD_INVEST = {
    "azul":    "investigacion_azul",
    "amarilla":"investigacion_amarilla",
    "roja":    "investigacion_roja",
    "negra":   "investigacion_negra",
}

EMOJI_COLOR = {
    "azul":    "🔵",
    "amarilla":"🟡",
    "roja":    "🔴",
    "negra":   "⚫",
}


def _obtener_zona_color(user_id: int):
    """Retorna (zona_nombre, color) o (None, None) si no está en zona salvaje."""
    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        return None, None
    zona_nombre = jug.get("zona_actual", "")
    try:
        from datos_zona import ZONAS
        zona_info = next((z for z in ZONAS if z["nombre"] == zona_nombre), None)
        if not zona_info:
            return zona_nombre, None
        color = zona_info.get("color")
        # Ciudades tienen salvaje=False o tipo=ciudad; excluirlas
        if zona_info.get("tipo") == "ciudad" or not zona_info.get("salvaje", True):
            return zona_nombre, None
        if color not in COLORES_SALVAJE:
            return zona_nombre, None
        return zona_nombre, color
    except Exception:
        return zona_nombre, None


def _stamina_info(user_id: int) -> str:
    try:
        stamina_actual = db_helper.obtener_jugador(user_id).get("stamina", 0)
        stamina_max = int(db_helper.obtener_config("stamina_max", "100"))
        return f"⚡ Stamina: {stamina_actual}/{stamina_max}"
    except Exception:
        return ""


async def cmd_explorar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if db_helper.esta_marcado(user_id):
        await update.effective_message.reply_text(
            "❌ Estás marcado. No puedes explorar hasta que pagues rescate con /pagar_rescate."
        )
        return

    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        await update.effective_message.reply_text("❌ No tienes personaje. Usa /start para crear uno.")
        return

    zona_nombre, color = _obtener_zona_color(user_id)
    stamina_txt = _stamina_info(user_id)

    if not color:
        nombre_zona = zona_nombre or "Ciudad"
        await update.effective_message.reply_text(
            f"🏙️ *{nombre_zona}*\n\n"
            f"No puedes explorar aquí. Las acciones de exploración solo están disponibles en *zonas salvajes*.\n\n"
            f"Usa /mapa o /viajar para ir a una zona salvaje.",
            parse_mode="Markdown"
        )
        return

    emoji = EMOJI_COLOR.get(color, "🌿")
    costo_recol = int(db_helper.obtener_config("stamina_recolectar", "5"))
    costo_invest = int(db_helper.obtener_config("stamina_explorar", "5"))

    texto = (
        f"{emoji} *Exploración — {zona_nombre}*\n\n"
        f"{stamina_txt}\n\n"
        f"¿Qué deseas hacer?\n\n"
        f"⛏️ *Recolectar* — Reúne materiales del entorno. Coste: {costo_recol} stamina\n"
        f"🔍 *Investigar* — Sigue rastros y descubre criaturas. Coste: {costo_invest} stamina"
    )
    keyboard = [
        [
            InlineKeyboardButton("⛏️ Recolectar", callback_data="explorar_recol"),
            InlineKeyboardButton("🔍 Investigar", callback_data="explorar_invest"),
        ],
        [InlineKeyboardButton("🗺️ Ver mapa",  callback_data="explorar_mapa"),
         InlineKeyboardButton("❌ Cerrar",    callback_data="explorar_cerrar")],
    ]
    await update.effective_message.reply_text(texto, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")


async def explorar_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data == "explorar_cerrar":
        await query.edit_message_text("🗺️ Exploración cerrada. Usa /explorar para volver.")
        return

    if data == "explorar_mapa":
        await query.edit_message_text("Usa /mapa para ver el mapa del mundo.")
        return

    zona_nombre, color = _obtener_zona_color(user_id)

    if data == "explorar_recol":
        if not color:
            await query.edit_message_text("❌ No estás en una zona salvaje. Viaja primero con /viajar.")
            return
        mod_name = _MOD_RECOL.get(color)
        if not mod_name:
            await query.edit_message_text("❌ No hay recolección disponible en esta zona.")
            return
        try:
            import importlib
            mod = importlib.import_module(mod_name)
            # Adaptar el update para usar message (no query)
            await mod.cmd_recolectar(update, context)
        except Exception as e:
            await query.edit_message_text(f"❌ Error al cargar la recolección: {e}")
        return

    if data == "explorar_invest":
        if not color:
            await query.edit_message_text("❌ No estás en una zona salvaje. Viaja primero con /viajar.")
            return
        mod_name = _MOD_INVEST.get(color)
        if not mod_name:
            await query.edit_message_text("❌ No hay investigación disponible en esta zona.")
            return
        try:
            import importlib
            mod = importlib.import_module(mod_name)
            await mod.cmd_investigar(update, context)
        except Exception as e:
            await query.edit_message_text(f"❌ Error al cargar la investigación: {e}")
        return


def registrar_handlers(app):
    app.add_handler(CommandHandler("explorar", cmd_explorar))
    app.add_handler(CallbackQueryHandler(explorar_callback, pattern="^explorar_"))

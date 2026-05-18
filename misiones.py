import asyncio
import sqlite3
from datetime import datetime
import db_helper
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler

DB_PATH = db_helper.DB_PATH

# Total de recompensas = 300 oro (precio de la armadura más barata de tienda_oro)
MISIONES = {
    "leer_guia": {
        "titulo": "📖 Leer la Guía",
        "descripcion": "Abre la guía interactiva de Aethelgard.",
        "recompensa_oro": 5,
        "orden": 1,
    },
    "visitar_ciudad": {
        "titulo": "🏙️ Visitar la Ciudad",
        "descripcion": "Entra al menú principal de tu ciudad con /ciudad.",
        "recompensa_oro": 5,
        "orden": 2,
    },
    "ver_perfil": {
        "titulo": "👤 Consultar tu Perfil",
        "descripcion": "Abre tu perfil de aventurero con /perfil.",
        "recompensa_oro": 5,
        "orden": 3,
    },
    "ver_inventario": {
        "titulo": "🎒 Ver tu Inventario",
        "descripcion": "Abre tu inventario con /inventario.",
        "recompensa_oro": 5,
        "orden": 4,
    },
    "ver_mapa": {
        "titulo": "🗺️ Explorar el Mapa",
        "descripcion": "Consulta el mapa del mundo con /mapa.",
        "recompensa_oro": 5,
        "orden": 5,
    },
    "visitar_tienda": {
        "titulo": "🏪 Visitar la Tienda",
        "descripcion": "Entra a la tienda con /tienda.",
        "recompensa_oro": 10,
        "orden": 6,
    },
    "usar_taberna": {
        "titulo": "🍺 Visitar la Taberna",
        "descripcion": "Descansa en la taberna desde el menú Ciudad.",
        "recompensa_oro": 10,
        "orden": 7,
    },
    "primer_viaje": {
        "titulo": "✈️ Tu Primer Viaje",
        "descripcion": "Viaja a una zona salvaje por primera vez con /viajar.",
        "recompensa_oro": 15,
        "orden": 8,
    },
    "primera_recoleccion": {
        "titulo": "⛏️ Primera Recolección",
        "descripcion": "Recolecta materiales en una zona salvaje con /recolectar.",
        "recompensa_oro": 20,
        "orden": 9,
    },
    "primera_investigacion": {
        "titulo": "🔬 Primera Investigación",
        "descripcion": "Investiga una zona para descubrir sus secretos con /investigar.",
        "recompensa_oro": 20,
        "orden": 10,
    },
    "primer_combate": {
        "titulo": "⚔️ Tu Primer Combate",
        "descripcion": "Participa en tu primer combate contra un monstruo.",
        "recompensa_oro": 25,
        "orden": 11,
    },
    "primera_mazmorra": {
        "titulo": "🌀 Tu Primera Mazmorra",
        "descripcion": "Completa tu primera mazmorra azul.",
        "recompensa_oro": 40,
        "orden": 12,
    },
    "subir_nivel_3": {
        "titulo": "📈 Alcanzar Nivel 3",
        "descripcion": "Sube tu personaje al nivel 3 ganando experiencia.",
        "recompensa_oro": 20,
        "orden": 13,
    },
    "subir_nivel_5": {
        "titulo": "📈 Alcanzar Nivel 5",
        "descripcion": "Sube al nivel 5. Las zonas amarillas te llamarán pronto.",
        "recompensa_oro": 25,
        "orden": 14,
    },
    "ganar_duelo": {
        "titulo": "🏆 Ganar tu Primer Duelo",
        "descripcion": "Derrota a otro aventurero en combate PvP.",
        "recompensa_oro": 25,
        "orden": 15,
    },
    "primer_crafteo": {
        "titulo": "🔨 Tu Primer Crafteo",
        "descripcion": "Fabrica un objeto en el taller de artesanía.",
        "recompensa_oro": 20,
        "orden": 16,
    },
    "unirse_gremio": {
        "titulo": "🏰 Unirse a un Gremio",
        "descripcion": "Únete a un gremio para aventurar en compañía.",
        "recompensa_oro": 25,
        "orden": 17,
    },
    "explorar_zona_amarilla": {
        "titulo": "🟡 Explorar Zona Amarilla",
        "descripcion": "Viaja a una zona amarilla por primera vez.",
        "recompensa_oro": 20,
        "orden": 18,
    },
}
# Verificación: total = 5+5+5+5+5+10+10+15+20+20+25+40+20+25+25+20+25+20 = 300


def _init_misiones_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS misiones_progreso (
        user_id INTEGER NOT NULL,
        mision_id TEXT NOT NULL,
        completada INTEGER DEFAULT 0,
        completada_en TIMESTAMP,
        PRIMARY KEY (user_id, mision_id)
    )''')
    conn.commit()
    conn.close()


_init_misiones_db()


def esta_completada(user_id: int, mision_id: str) -> bool:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT completada FROM misiones_progreso WHERE user_id=? AND mision_id=?', (user_id, mision_id))
    row = c.fetchone()
    conn.close()
    return bool(row and row[0])


def obtener_progreso(user_id: int) -> dict:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT mision_id, completada FROM misiones_progreso WHERE user_id=?', (user_id,))
    rows = c.fetchall()
    conn.close()
    return {r[0]: bool(r[1]) for r in rows}


def mision_actual(user_id: int):
    """Retorna (mision_id, datos) de la primera misión pendiente en orden, o (None, None) si todas están completadas."""
    progreso = obtener_progreso(user_id)
    for mid, m in sorted(MISIONES.items(), key=lambda x: x[1]["orden"]):
        if not progreso.get(mid, False):
            return mid, m
    return None, None


async def _push_notif(context, user_id: int, texto: str):
    try:
        await context.bot.send_message(chat_id=user_id, text=texto, parse_mode="Markdown")
    except Exception:
        pass


def completar_mision(user_id: int, mision_id: str, context=None) -> bool:
    """Marca misión como completada y entrega recompensa. Retorna True si fue nueva.
    Envía notificación inmediata al jugador si se pasa context."""
    if mision_id not in MISIONES:
        return False
    if esta_completada(user_id, mision_id):
        return False
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        'INSERT OR REPLACE INTO misiones_progreso (user_id, mision_id, completada, completada_en) VALUES (?,?,1,?)',
        (user_id, mision_id, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

    mision = MISIONES[mision_id]
    recompensa_oro = mision["recompensa_oro"]
    recompensa_xp = mision.get("recompensa_xp", 0)
    recompensa_items = mision.get("recompensa_items", [])

    try:
        import economia
        economia.modificar_saldo(user_id, "oro", recompensa_oro, f"mision:{mision_id}")
    except Exception:
        pass

    if recompensa_xp > 0:
        try:
            import db_helper as _db
            jug = _db.obtener_jugador(user_id)
            if jug:
                _db.actualizar_jugador(user_id, experiencia=jug["experiencia"] + recompensa_xp)
        except Exception:
            pass

    items_obtenidos = []
    for item in recompensa_items:
        try:
            import db_helper as _db
            _db.agregar_item(user_id, item["id"], item.get("cantidad", 1))
            items_obtenidos.append((item.get("nombre", item["id"]), item.get("cantidad", 1)))
        except Exception:
            pass

    siguiente_id, siguiente = mision_actual(user_id)

    lineas = [
        f"✅ *¡Misión completada!*",
        f"📋 {mision['titulo']}\n",
    ]
    if recompensa_oro:
        lineas.append(f"🪙 Oro: *+{recompensa_oro}*")
    if recompensa_xp:
        lineas.append(f"✨ Experiencia: *+{recompensa_xp}*")
    for nombre_i, cant_i in items_obtenidos:
        lineas.append(f"📦 {nombre_i}: *x{cant_i}*")

    if siguiente:
        lineas.append(f"\n📌 *Siguiente misión:*\n{siguiente['titulo']}\n_{siguiente['descripcion']}_")
    else:
        lineas.append("\n🏆 *¡Has completado todas las misiones de inicio!*")

    texto_notif = "\n".join(lineas)

    try:
        db_helper.agregar_notificacion(user_id, texto_notif)
    except Exception:
        pass

    if context is not None:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(_push_notif(context, user_id, texto_notif))
        except Exception:
            pass

    return True


def _texto_misiones(user_id: int) -> str:
    progreso = obtener_progreso(user_id)
    total = len(MISIONES)
    completadas_n = sum(1 for m in MISIONES if progreso.get(m, False))

    actual_id, actual = mision_actual(user_id)

    if actual is None:
        total_oro = sum(m["recompensa_oro"] for m in MISIONES.values())
        return (
            f"📋 *Misiones de Inicio* — ¡Todas completadas!\n\n"
            f"✅ Has completado las {total} misiones de inicio.\n"
            f"🪙 Oro total ganado: *{total_oro}*\n\n"
            f"_¡Estás listo para explorar Aethelgard!_"
        )

    return "\n".join([
        f"📋 *Misión actual* ({completadas_n}/{total} completadas)\n",
        f"⬜ *{actual['titulo']}*",
        f"_{actual['descripcion']}_",
        f"🪙 Recompensa: *{actual['recompensa_oro']} oro*",
    ])


def _texto_todas_misiones(user_id: int) -> str:
    progreso = obtener_progreso(user_id)
    total = len(MISIONES)
    completadas_n = sum(1 for m in MISIONES if progreso.get(m, False))
    ganado = sum(MISIONES[m]["recompensa_oro"] for m in MISIONES if progreso.get(m, False))
    total_posible = sum(m["recompensa_oro"] for m in MISIONES.values())

    lines = [
        f"📋 *Todas las Misiones de Inicio*",
        f"Progreso: {completadas_n}/{total}  |  Oro ganado: *{ganado}/{total_posible}*\n",
    ]
    for mid, m in sorted(MISIONES.items(), key=lambda x: x[1]["orden"]):
        estado = "✅" if progreso.get(mid, False) else "⬜"
        lines.append(f"{estado} {m['titulo']} — {m['recompensa_oro']} oro")
    return "\n".join(lines)


async def mostrar_misiones_inicio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Panel de misiones mostrado al crear personaje."""
    user_id = update.effective_user.id
    texto = (
        "🗺️ *¡Bienvenido a Aethelgard, aventurero!*\n\n"
        "Antes de lanzarte al mundo, completa tus *Misiones de Inicio*.\n"
        "Te enseñarán el juego paso a paso y te darán tu primer oro.\n\n"
        + _texto_misiones(user_id)
    )
    keyboard = [
        [InlineKeyboardButton("📖 Ver Guía",        callback_data="misiones_ir_guia"),
         InlineKeyboardButton("🏙️ Ir a la Ciudad", callback_data="misiones_ir_ciudad")],
        [InlineKeyboardButton("📋 Ver todas",       callback_data="misiones_ver_todas"),
         InlineKeyboardButton("❌ Cerrar",           callback_data="misiones_cerrar")],
    ]
    await update.effective_message.reply_text(
        texto, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
    )


async def cmd_misiones(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        import guia_contextual as _gc
        await _gc.enviar(user_id, context, "misiones_menu")
    except Exception:
        pass
    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        await update.effective_message.reply_text("❌ Crea un personaje primero con /start.")
        return
    texto = _texto_misiones(user_id)
    keyboard = [
        [InlineKeyboardButton("🔄 Actualizar",  callback_data="misiones_actualizar"),
         InlineKeyboardButton("📋 Ver todas",   callback_data="misiones_ver_todas")],
        [InlineKeyboardButton("❌ Cerrar",       callback_data="misiones_cerrar")],
    ]
    await update.effective_message.reply_text(texto, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")


async def misiones_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data == "misiones_cerrar":
        await query.edit_message_text("📋 Misiones cerradas. Usa /misiones para volver.")
        return

    if data in ("misiones_actualizar", "misiones_inicio"):
        texto = _texto_misiones(user_id)
        keyboard = [
            [InlineKeyboardButton("🔄 Actualizar", callback_data="misiones_actualizar"),
             InlineKeyboardButton("📋 Ver todas",  callback_data="misiones_ver_todas")],
            [InlineKeyboardButton("❌ Cerrar",      callback_data="misiones_cerrar")],
        ]
        try:
            await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        except Exception as _e:
            if "not modified" not in str(_e).lower():
                await query.message.reply_text(f"⚠️ Error al actualizar misiones: {_e}")
        return

    if data == "misiones_ver_todas":
        texto = _texto_todas_misiones(user_id)
        keyboard = [
            [InlineKeyboardButton("🔙 Volver", callback_data="misiones_actualizar"),
             InlineKeyboardButton("❌ Cerrar", callback_data="misiones_cerrar")],
        ]
        await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return

    if data == "misiones_ir_guia":
        completar_mision(user_id, "leer_guia", context)
        try:
            from guia import cmd_guia
            await cmd_guia(update, context)
        except Exception:
            await query.edit_message_text("Usa /guia para abrir la guía interactiva.")
        return

    if data == "misiones_ir_ciudad":
        completar_mision(user_id, "visitar_ciudad", context)
        try:
            from ciudad import cmd_ciudad
            await cmd_ciudad(update, context)
        except Exception:
            await query.edit_message_text("Usa /ciudad para ir a la ciudad.")
        return


def registrar_handlers(app):
    app.add_handler(CommandHandler("misiones", cmd_misiones))
    app.add_handler(CallbackQueryHandler(misiones_callback, pattern="^misiones_"))

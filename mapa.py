import db_helper
from datos_zona import ZONAS
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler

COLORES_EMOJI = {
    "azul":     "🔵",
    "amarilla": "🟡",
    "amarillo": "🟡",
    "roja":     "🔴",
    "rojo":     "🔴",
    "negra":    "⬛",
    "negro":    "⬛",
}

COLOR_LABEL = {
    "azul":     "Zona Azul",
    "amarilla": "Zona Amarilla",
    "roja":     "Zona Roja",
    "negra":    "Zona Negra",
}

ACTIVIDADES_POR_TIPO = {
    "ciudad":  ["🏪 Tienda", "🏛️ Subastas", "⚔️ Duelos", "🌀 Mazmorras", "✈️ Viajes"],
    "salvaje": ["⛏️ Recolección", "🔬 Investigación", "⚔️ Combate", "✈️ Viajes"],
}


# ── Helpers ──────────────────────────────────────────────────────────────────

def _emoji_zona(zona: dict) -> str:
    nombre = zona.get("nombre", "").lower()
    tipo   = zona.get("tipo", "salvaje")
    if tipo == "ciudad":
        if "alianza"   in nombre: return "🏰"
        if "imperio"   in nombre: return "🏛️"
        if "sindicato" in nombre: return "🏙️"
        return "🏙️"
    if "bosque"   in nombre: return "🌳"
    if "desierto" in nombre: return "🏜️"
    if "ruinas"   in nombre: return "🏚️"
    if "oasis"    in nombre: return "🌴"
    if "magm"     in nombre: return "🌋"
    if "dragón"   in nombre or "dragon" in nombre: return "🐉"
    if "forja"    in nombre: return "⚙️"
    if "abismo"   in nombre: return "🕳️"
    if "costa"    in nombre: return "🌊"
    if "nexo"     in nombre: return "🌀"
    color = zona.get("color", "azul")
    return COLORES_EMOJI.get(color, "🔵")


def _obtener_destino_por_id(zona_id: int):
    for z in ZONAS:
        if z["id"] == zona_id:
            return z
    return None


def _tiempo_str(segundos: int) -> str:
    if segundos == 0:
        return "⚡ Inst."
    if segundos < 60:
        return f"{segundos}s"
    m, s = divmod(segundos, 60)
    return f"{m}m {s}s" if s else f"{m}m"


def _calc_tiempo(color_origen: str, faccion_origen: int,
                 color_destino: str, faccion_destino: int,
                 velocidad: int) -> str:
    """Calcula el tiempo de viaje usando la función de viajes.py."""
    try:
        from viajes import _calcular_tiempo_viaje
        t = _calcular_tiempo_viaje(
            color_origen, color_destino, velocidad,
            faccion_origen, faccion_destino
        )
        return _tiempo_str(t)
    except Exception:
        return "?"


def _montura_velocidad(user_id: int) -> int:
    try:
        from viajes import _obtener_montura_activa
        m = _obtener_montura_activa(user_id)
        return m["velocidad"] if m else 0
    except Exception:
        return 0


# ── Texto informativo ─────────────────────────────────────────────────────────

def _construir_texto_mapa(jug: dict) -> str:
    zona_id = jug.get("zona_actual_id")
    zona = _obtener_destino_por_id(zona_id) if zona_id else None

    if not zona:
        zona_nombre = jug.get("zona_actual", "desconocida")
        zona = next((z for z in ZONAS if z["nombre"] == zona_nombre), None)

    if not zona:
        return (
            "🗺️ *Tu Mapa*\n\n"
            "❓ No se pudo determinar tu ubicación.\n"
            "Usa /ciudad para ir a la ciudad."
        )

    color      = zona.get("color", "azul")
    tipo       = zona.get("tipo",  "salvaje")
    emoji_c    = COLORES_EMOJI.get(color, "🔵")
    emoji_z    = _emoji_zona(zona)
    faccion_id = jug.get("faccion_id", 0)

    actividades = ACTIVIDADES_POR_TIPO.get(tipo, [])
    act_texto   = " · ".join(actividades) if actividades else "—"
    fm_actual   = "⭐ " if zona.get("faccion_id") == faccion_id else ""

    return (
        f"🗺️ *Tu Mapa*\n\n"
        f"📍 *Zona actual:*\n"
        f"   {fm_actual}{emoji_z} {zona['nombre']} {emoji_c}\n"
        f"   Tipo: {'Ciudad' if tipo == 'ciudad' else 'Zona salvaje'} · {COLOR_LABEL.get(color, color)}\n\n"
        f"🎯 *Actividades disponibles:*\n"
        f"   {act_texto}\n\n"
        f"👇 *Toca una zona para viajar allí:*\n"
        f"💡 ⭐ = tu facción · ⚡ = instantáneo · 🔒 = nivel insuficiente"
    )


def _construir_texto_zonas_mundo(jug: dict) -> str:
    nivel      = jug.get("nivel", 1)
    faccion_id = jug.get("faccion_id", 0)
    zona_id    = jug.get("zona_actual_id")
    zona_actual = _obtener_destino_por_id(zona_id) if zona_id else None
    nombre_actual = zona_actual["nombre"] if zona_actual else "desconocida"

    return (
        f"🌐 *Todas las Zonas del Mundo*\n\n"
        f"📍 Estás en: *{nombre_actual}*\n\n"
        f"👇 Toca cualquier zona para viajar:\n"
        f"💡 ⭐ = tu facción · ⚡ = instantáneo · 🔒 = nivel insuficiente"
    )


# ── Teclados con botones de viaje ─────────────────────────────────────────────

def _teclado_mi_zona(jug: dict) -> InlineKeyboardMarkup:
    """Teclado de 'Mi Zona': zonas accesibles desde la ubicación actual."""
    user_id    = jug["user_id"]
    zona_id    = jug.get("zona_actual_id")
    nivel      = jug.get("nivel", 1)
    faccion_id = jug.get("faccion_id", 0)
    zona       = _obtener_destino_por_id(zona_id) if zona_id else None
    vel        = _montura_velocidad(user_id)

    color_orig   = zona.get("color",      "azul") if zona else "azul"
    faccion_orig = zona.get("faccion_id", 1)      if zona else 1

    # Zonas accesibles: misma facción O mismo color, nivel suficiente, distinto a actual
    accesibles = []
    for z in ZONAS:
        if z["id"] == zona_id:
            continue
        if nivel < z.get("nivel_requerido", 1):
            continue
        misma_faccion = z.get("faccion_id") == faccion_id
        mismo_color   = z.get("color") == color_orig
        if misma_faccion or mismo_color:
            accesibles.append(z)

    filas = []
    if accesibles:
        # Agrupar por color
        for color in ["azul", "amarilla", "roja", "negra"]:
            grupo = [z for z in accesibles if z.get("color") == color]
            if not grupo:
                continue
            ec = COLORES_EMOJI.get(color, "🔵")
            filas.append([InlineKeyboardButton(
                f"── {ec} {COLOR_LABEL.get(color, color)} ──",
                callback_data="mapa_noop"
            )])
            for z in grupo:
                ez       = _emoji_zona(z)
                tipo_ico = "🏙️" if z.get("tipo") == "ciudad" else "🌿"
                fm       = "⭐" if z.get("faccion_id") == faccion_id else "  "
                t_str    = _calc_tiempo(color_orig, faccion_orig,
                                        z.get("color", "azul"), z.get("faccion_id", 1), vel)
                label = f"{fm}{ez} {z['nombre']} {tipo_ico} · {t_str}"
                filas.append([InlineKeyboardButton(
                    f"✈️ {label}",
                    callback_data=f"viaje_destino_{z['id']}"
                )])
    else:
        filas.append([InlineKeyboardButton("(Sin zonas accesibles desde aquí)", callback_data="mapa_noop")])

    filas.append([
        InlineKeyboardButton("🌐 Ver todas las zonas", callback_data="mapa_mundo"),
        InlineKeyboardButton("❌ Cerrar",              callback_data="mapa_cerrar"),
    ])
    return InlineKeyboardMarkup(filas)


def _teclado_mundo(jug: dict) -> InlineKeyboardMarkup:
    """Teclado de 'Todas las Zonas': todas las zonas del mundo como botones de viaje."""
    user_id    = jug["user_id"]
    nivel      = jug.get("nivel", 1)
    faccion_id = jug.get("faccion_id", 0)
    zona_id    = jug.get("zona_actual_id")
    zona       = _obtener_destino_por_id(zona_id) if zona_id else None
    vel        = _montura_velocidad(user_id)

    color_orig   = zona.get("color",      "azul") if zona else "azul"
    faccion_orig = zona.get("faccion_id", 1)      if zona else 1

    filas = []
    for color in ["azul", "amarilla", "roja", "negra"]:
        grupo = [z for z in ZONAS if z.get("color") == color and z["id"] != zona_id]
        if not grupo:
            continue

        ec = COLORES_EMOJI.get(color, "🔵")
        filas.append([InlineKeyboardButton(
            f"── {ec} {COLOR_LABEL.get(color, color)} ──",
            callback_data="mapa_noop"
        )])
        for z in grupo:
            ez       = _emoji_zona(z)
            tipo_ico = "🏙️" if z.get("tipo") == "ciudad" else "🌿"
            fm       = "⭐" if z.get("faccion_id") == faccion_id else "  "
            locked   = nivel < z.get("nivel_requerido", 1)

            if locked:
                t_str = f"🔒 nv.{z['nivel_requerido']}"
            else:
                t_str = _calc_tiempo(color_orig, faccion_orig,
                                     z.get("color", "azul"), z.get("faccion_id", 1), vel)

            label = f"{fm}{ez} {z['nombre']} {tipo_ico} · {t_str}"
            filas.append([InlineKeyboardButton(
                f"✈️ {label}",
                callback_data=f"viaje_destino_{z['id']}"
            )])

    filas.append([
        InlineKeyboardButton("📍 Mi Zona", callback_data="mapa_mi_zona"),
        InlineKeyboardButton("❌ Cerrar",  callback_data="mapa_cerrar"),
    ])
    return InlineKeyboardMarkup(filas)


# ── Handlers ──────────────────────────────────────────────────────────────────

async def cmd_mapa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        await update.effective_message.reply_text("❌ Primero crea un personaje con /start.")
        return
    texto   = _construir_texto_mapa(jug)
    teclado = _teclado_mi_zona(jug)
    await update.effective_message.reply_text(texto, reply_markup=teclado, parse_mode="Markdown")
    try:
        import misiones as _mis
        _mis.completar_mision(user_id, "ver_mapa", context)
    except Exception:
        pass


async def mapa_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data    = query.data

    if data == "mapa_noop":
        return

    if data == "mapa_cerrar":
        await query.message.delete()
        return

    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        await query.edit_message_text("❌ Primero crea un personaje con /start.")
        return

    if data == "mapa_mi_zona":
        texto   = _construir_texto_mapa(jug)
        teclado = _teclado_mi_zona(jug)
        await query.edit_message_text(texto, reply_markup=teclado, parse_mode="Markdown")

    elif data == "mapa_mundo":
        texto   = _construir_texto_zonas_mundo(jug)
        teclado = _teclado_mundo(jug)
        await query.edit_message_text(texto, reply_markup=teclado, parse_mode="Markdown")


# ── Registro ──────────────────────────────────────────────────────────────────

def registrar_handlers(app):
    app.add_handler(CommandHandler("mapa", cmd_mapa))
    app.add_handler(CallbackQueryHandler(mapa_callback, pattern="^mapa_"))

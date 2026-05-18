"""
teclado_rapido.py
Teclado persistente (Reply Keyboard) que aparece en la parte inferior del chat.
Se muestra automáticamente al registrarse (/start) y al abrir /ciudad.
Los botones ejecutan los comandos más importantes del juego.

Comandos de toggle:
  🔲 Ocultar teclado  — botón en la última fila del teclado (lo oculta)
  /teclado            — muestra el teclado si estaba oculto, o lo oculta si está visible
"""
from telegram import (
    Update, ReplyKeyboardMarkup, KeyboardButton,
    ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
)
from telegram.ext import ContextTypes, MessageHandler, CommandHandler, CallbackQueryHandler, filters
import db_helper


# ─── PREFERENCIA POR JUGADOR ──────────────────────────────────────────────────

def _teclado_esta_oculto(user_id: int) -> bool:
    jug = db_helper.obtener_jugador(user_id)
    return bool(jug.get("teclado_oculto", 0)) if jug else False


def _set_teclado_oculto(user_id: int, oculto: bool):
    db_helper.actualizar_jugador(user_id, teclado_oculto=1 if oculto else 0)


# ─── TRACKER DE TIPO DE TECLADO ACTIVO ───────────────────────────────────────
# Registra qué teclado ("ciudad" o "salvaje") fue enviado por última vez a cada
# jugador.  Se limpia en cada reinicio del bot, por eso hacemos re-sync en la
# primera interacción después de un reinicio.

_TIPO_TECLADO: dict = {}   # {user_id: "ciudad" | "salvaje"}


def marcar_tipo(user_id: int, tipo: str):
    """Registra el tipo de teclado enviado ('ciudad' o 'salvaje')."""
    _TIPO_TECLADO[user_id] = tipo


def _tipo_correcto(zona_actual: str) -> str:
    """Devuelve 'ciudad' o 'salvaje' según la zona actual del jugador."""
    color = _detectar_color(zona_actual)
    return "ciudad" if color in ("ciudad", "") else "salvaje"


# ─── COMPROBACIÓN SUPERADMIN ──────────────────────────────────────────────────

def _es_superadmin(user_id: int) -> bool:
    try:
        import superadmin as _sa
        return _sa.verificar_superadmin(user_id)
    except Exception:
        return False


# ─── TECLADO PRINCIPAL ────────────────────────────────────────────────────────

def get_teclado_principal(user_id: int = 0) -> ReplyKeyboardMarkup:
    """Teclado inferior para zonas de ciudad — sin acciones de zona salvaje."""
    botones = [
        [KeyboardButton("👤 Perfil"),        KeyboardButton("🏙️ Ciudad")],
        [KeyboardButton("🎒 Inventario"),     KeyboardButton("✈️ Viajar")],
        [KeyboardButton("⚔️ Duelos"),         KeyboardButton("🏰 Gremio")],
        [KeyboardButton("🏆 Rankings"),       KeyboardButton("🌑 Umbral")],
        [KeyboardButton("📋 Comandos"),       KeyboardButton("📖 Guía")],
    ]
    if user_id and _es_superadmin(user_id):
        botones.append([KeyboardButton("🔐 Admin"), KeyboardButton("🐛 Debug")])
    botones.append([KeyboardButton("🔲 Ocultar teclado")])
    return ReplyKeyboardMarkup(
        botones,
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Escribe un comando o pulsa un botón…"
    )


def get_teclado_salvaje(user_id: int = 0) -> ReplyKeyboardMarkup:
    """Teclado cuando el jugador está en zona salvaje."""
    botones = [
        [KeyboardButton("⛏️ Recolectar"),      KeyboardButton("🔍 Investigar")],
        [KeyboardButton("🏰 Mazmorra")],
        [KeyboardButton("✈️ Viajar"),           KeyboardButton("👤 Perfil")],
        [KeyboardButton("🎒 Inventario"),       KeyboardButton("📋 Comandos")],
        [KeyboardButton("📖 Guía")],
    ]
    if user_id:
        try:
            import recoleccion_auto as _ra
            if _ra.tiene_auto_recoleccion(user_id):
                botones.insert(2, [KeyboardButton("🤖 Auto-Recolección")])
        except Exception:
            pass
        try:
            _jug = db_helper.obtener_jugador(user_id)
            if _jug:
                from datos_zona import ZONAS as _ZG_tr
                _zid = _jug.get("zona_actual_id")
                _color = next((z.get("color", "") for z in _ZG_tr if z.get("id") == _zid), "")
                if _color in ("amarilla", "roja", "negra"):
                    _em = {"amarilla": "🟡", "roja": "🔴", "negra": "⬛"}.get(_color, "")
                    botones.insert(1, [
                        KeyboardButton("⚔️ Emboscada PvP"),
                        KeyboardButton(f"🌐 Emboscada Zonas {_em}"),
                    ])
        except Exception:
            pass
    if user_id and _es_superadmin(user_id):
        botones.append([KeyboardButton("🔐 Admin"), KeyboardButton("🐛 Debug")])
    botones.append([KeyboardButton("🔲 Ocultar teclado")])
    return ReplyKeyboardMarkup(
        botones,
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Zona salvaje — ¿qué haces?"
    )


def get_teclado_guerra(user_id: int = 0) -> ReplyKeyboardMarkup:
    """Teclado de emergencia durante la Guerra de Facciones.
    Solo muestra las acciones permitidas mientras la guerra está activa."""
    botones = [
        [KeyboardButton("⚔️ Atacar en guerra"),  KeyboardButton("🛡️ Defender en guerra")],
        [KeyboardButton("⏭️ Saltar guerra"),      KeyboardButton("👤 Perfil")],
        [KeyboardButton("🎒 Inventario"),          KeyboardButton("📖 Guía")],
    ]
    botones.append([KeyboardButton("🔲 Ocultar teclado")])
    return ReplyKeyboardMarkup(
        botones,
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="⚔️ ¡Guerra de Facciones activa! Elige tu acción."
    )


# ─── MAPA DE BOTONES → COMANDOS ───────────────────────────────────────────────

_MAPA = {
    "👤 Perfil":              "/perfil",
    "🏙️ Ciudad":              "/ciudad",
    "🎒 Inventario":           "/inventario",
    "✈️ Viajar":               "/viajar",
    "⚔️ Duelos":               "/duelo_menu",
    "🏰 Gremio":               "/gremio",
    "⛏️ Recolectar":           "/recolectar",
    "🔍 Investigar":           "/investigar",
    "🏰 Mazmorra":             "/mazmorra",
    "⚔️ Atacar jugador":       "/pvp_buscar",
    "🔐 Admin":                "/superadmin",
    "🐛 Debug":                "/panel_debug",
    "📋 Comandos":             "/comandos",
    "📖 Guía":                 "/guia",
    "🏆 Rankings":             "/rankings",
    "🌑 Umbral":               "/umbral",
    "⚔️ Atacar en guerra":     "/guerra_facciones_atacar",
    "🛡️ Defender en guerra":   "/guerra_facciones_defender",
    "⏭️ Saltar guerra":        "/saltar_guerra",
    "🤖 Auto-Recolección":     "/auto_recoleccion",
    "⚔️ Emboscada PvP":        "/pvp_buscar",
    "🌐 Emboscada Zonas 🟡":   "/pvp_multi",
    "🌐 Emboscada Zonas 🔴":   "/pvp_multi",
    "🌐 Emboscada Zonas ⬛":   "/pvp_multi",
}


# ─── HANDLER: botón OCULTAR ──────────────────────────────────────────────────

_BTN_MOSTRAR = InlineKeyboardMarkup([[
    InlineKeyboardButton("⌨️ Mostrar teclado", callback_data="teclado_mostrar")
]])


async def handle_ocultar_teclado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Oculta el teclado y guarda la preferencia."""
    user_id = update.effective_user.id
    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        return
    _set_teclado_oculto(user_id, True)
    await update.message.reply_text(
        "🔲 Teclado ocultado.",
        reply_markup=ReplyKeyboardRemove()
    )
    await update.message.reply_text(
        "Pulsa el botón para volver a mostrarlo:",
        reply_markup=_BTN_MOSTRAR
    )


async def cb_teclado_mostrar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback del botón inline ⌨️ Mostrar teclado."""
    query = update.callback_query
    try:
        await query.answer()
    except Exception:
        pass
    user_id = update.effective_user.id
    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        return
    _set_teclado_oculto(user_id, False)
    try:
        from guerra_facciones import hay_guerra_activa as _hga
        if _hga():
            kb = get_teclado_guerra(user_id)
            marcar_tipo(user_id, "guerra")
        else:
            raise Exception("no war")
    except Exception:
        zona = jug.get("zona_actual", "")
        tipo = _tipo_correcto(zona)
        kb = get_teclado_salvaje(user_id) if tipo == "salvaje" else get_teclado_principal(user_id)
        marcar_tipo(user_id, tipo)
    try:
        await query.edit_message_text("📱 Teclado activado.")
    except Exception:
        pass
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="📱 Aquí tienes el teclado:",
        reply_markup=kb
    )


# ─── COMANDO /teclado (toggle) ────────────────────────────────────────────────

async def cmd_teclado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /teclado — muestra el teclado si estaba oculto, lo oculta si estaba visible.
    """
    user_id = update.effective_user.id
    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        await update.effective_message.reply_text("❌ Primero crea tu personaje con /start.")
        return

    oculto = _teclado_esta_oculto(user_id)
    if oculto:
        # Mostrar
        _set_teclado_oculto(user_id, False)
        try:
            from guerra_facciones import hay_guerra_activa as _hga
            if _hga():
                kb = get_teclado_guerra(user_id)
                marcar_tipo(user_id, "guerra")
            else:
                raise Exception("no war")
        except Exception:
            zona = jug.get("zona_actual", "")
            tipo = _tipo_correcto(zona)
            kb = get_teclado_salvaje(user_id) if tipo == "salvaje" else get_teclado_principal(user_id)
            marcar_tipo(user_id, tipo)
        await update.effective_message.reply_text(
            "📱 Teclado activado.",
            reply_markup=kb
        )
    else:
        # Ocultar
        _set_teclado_oculto(user_id, True)
        await update.effective_message.reply_text(
            "🔲 Teclado ocultado.",
            reply_markup=ReplyKeyboardRemove()
        )
        await update.effective_message.reply_text(
            "Pulsa el botón para volver a mostrarlo:",
            reply_markup=_BTN_MOSTRAR
        )


# ─── HANDLER: convierte pulsaciones de botón en comandos ─────────────────────

_FE0F = "\ufe0f"
_MAPA_NORM = {k.replace(_FE0F, ""): v for k, v in _MAPA.items()}

async def handle_boton_rapido(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Intercepta el texto del botón y lo despacha como si fuera el comando.
    Normaliza U+FE0F (selector de variante emoji) para compatibilidad con todos los clientes de Telegram.
    Auto-sincroniza el teclado si el tipo no coincide con la zona actual (p.ej. tras reinicio del bot).
    """
    texto_raw = update.message.text.strip() if update.message and update.message.text else ""
    texto = texto_raw.replace(_FE0F, "")
    if texto not in _MAPA_NORM:
        return  # No es un botón nuestro, dejar pasar

    user_id = update.effective_user.id
    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        await update.effective_message.reply_text(
            "❌ Primero crea tu personaje con /start."
        )
        return

    # ── AUTO-SYNC DE TECLADO ──────────────────────────────────────────────────
    # Si el tracker está vacío (reinicio del bot), la zona cambió, o el jugador
    # aún tiene el teclado de guerra pero la guerra ya terminó, lo corregimos.
    if not _teclado_esta_oculto(user_id):
        zona = jug.get("zona_actual", "")
        tipo_actual = _tipo_correcto(zona)   # "ciudad" o "salvaje"
        tipo_guardado = _TIPO_TECLADO.get(user_id)

        # Detectar si la guerra terminó pero el teclado sigue en modo guerra
        guerra_activa = False
        try:
            from guerra_facciones import hay_guerra_activa as _hga_sync
            guerra_activa = _hga_sync()
        except Exception:
            pass

        necesita_sync = (
            tipo_guardado != tipo_actual                        # zona cambió o bot reinició
            or (tipo_guardado == "guerra" and not guerra_activa) # guerra terminó pero teclado pegado
        )

        if necesita_sync:
            kb = get_teclado_salvaje(user_id) if tipo_actual == "salvaje" else get_teclado_principal(user_id)
            try:
                await update.message.reply_text("📍 Teclado actualizado.", reply_markup=kb)
                marcar_tipo(user_id, tipo_actual)  # solo marcar si el envío fue exitoso
            except Exception:
                pass

    comando_destino = _MAPA_NORM[texto]

    # ── LOCKDOWN POR GUERRA DE FACCIONES ──────────────────────────────────────
    # Durante la guerra solo se permiten los botones de guerra + perfil + inventario + guía
    _CMDS_GUERRA_OK = {
        "/guerra_facciones_atacar", "/guerra_facciones_defender",
        "/saltar_guerra", "/perfil", "/inventario", "/guia",
    }
    try:
        from guerra_facciones import hay_guerra_activa as _hga_btn
        if _hga_btn() and comando_destino not in _CMDS_GUERRA_OK:
            if not _teclado_esta_oculto(user_id):
                kb_g = get_teclado_guerra(user_id)
                await update.message.reply_text(
                    "🔒 *¡Los servicios están suspendidos durante la Guerra de Facciones!*\n\n"
                    "Usa los botones de tu teclado de guerra o espera a que termine.",
                    parse_mode="Markdown",
                    reply_markup=kb_g
                )
                marcar_tipo(user_id, "guerra")
            else:
                await update.effective_message.reply_text(
                    "🔒 Durante la guerra no puedes hacer eso.\n"
                    "Usa /guerra_facciones_atacar, /guerra_facciones_defender o /saltar_guerra."
                )
            return
    except Exception:
        pass

    # Importar y ejecutar el handler correspondiente
    try:
        if comando_destino == "/perfil":
            from perfil import cmd_perfil
            await cmd_perfil(update, context)

        elif comando_destino == "/ciudad":
            from ciudad import cmd_ciudad
            await cmd_ciudad(update, context)

        elif comando_destino == "/inventario":
            from inventario import cmd_inventario
            await cmd_inventario(update, context)

        elif comando_destino == "/viajar":
            from viajes import cmd_viajar
            await cmd_viajar(update, context)

        elif comando_destino == "/gremio":
            from gremios import cmd_gremio
            await cmd_gremio(update, context)

        elif comando_destino == "/recolectar":
            # Detectar zona actual y despachar al módulo correcto
            zona = jug.get("zona_actual", "")
            color = _detectar_color(zona)
            if color == "azul":
                from recoleccion_azul import cmd_recolectar
            elif color == "amarilla":
                from recoleccion_amarilla import cmd_recolectar
            elif color == "roja":
                from recoleccion_roja import cmd_recolectar
            elif color == "negra":
                from recoleccion_negra import cmd_recolectar
            else:
                await update.effective_message.reply_text(
                    "⚠️ Solo puedes recolectar en zonas salvajes. Viaja primero a una."
                )
                return
            await cmd_recolectar(update, context)

        elif comando_destino == "/investigar":
            zona = jug.get("zona_actual", "")
            color = _detectar_color(zona)
            if color == "azul":
                from investigacion_azul import cmd_investigar
            elif color == "amarilla":
                from investigacion_amarilla import cmd_investigar
            elif color == "roja":
                from investigacion_roja import cmd_investigar
            elif color == "negra":
                from investigacion_negra import cmd_investigar
            else:
                await update.effective_message.reply_text(
                    "⚠️ Solo puedes investigar en zonas salvajes. Viaja primero a una."
                )
                return
            await cmd_investigar(update, context)

        elif comando_destino == "/mazmorra":
            zona = jug.get("zona_actual", "")
            color = _detectar_color(zona)
            if color == "azul":
                from mazmorra_azul import cmd_mazmorra
            elif color == "amarilla":
                from mazmorra_amarilla import cmd_mazmorra
            elif color == "roja":
                from mazmorra_roja import cmd_mazmorra
            elif color == "negra":
                from mazmorra_negra import cmd_mazmorra
            else:
                await update.effective_message.reply_text(
                    "⚠️ Solo puedes entrar a mazmorras en zonas salvajes."
                )
                return
            await cmd_mazmorra(update, context)

        elif comando_destino == "/duelo_menu":
            await _handle_duelo_menu(update, context, jug)

        elif comando_destino == "/atacar_zona":
            await _handle_atacar_zona(update, context, jug)

        elif comando_destino == "/superadmin":
            from superadmin import cmd_panel_admin
            await cmd_panel_admin(update, context)

        elif comando_destino == "/panel_debug":
            from panel_debug import cmd_panel_debug
            await cmd_panel_debug(update, context)

        elif comando_destino == "/comandos":
            from comandos import cmd_comandos
            await cmd_comandos(update, context)

        elif comando_destino == "/guia":
            from guia import cmd_guia
            await cmd_guia(update, context)

        elif comando_destino == "/rankings":
            try:
                from rankings import cmd_rankings
                await cmd_rankings(update, context)
            except ImportError:
                await update.effective_message.reply_text("🏆 Rankings: usa el comando /rankings para ver las clasificaciones.")

        elif comando_destino == "/umbral":
            try:
                from umbral_vacio import cmd_umbral
                await cmd_umbral(update, context)
            except ImportError:
                await update.effective_message.reply_text("🌑 Umbral del Vacío: usa el comando /umbral para ver el estado de la corrupción.")

        elif comando_destino == "/guerra_facciones_atacar":
            from guerra_facciones import cmd_guerra_facciones_atacar
            await cmd_guerra_facciones_atacar(update, context)

        elif comando_destino == "/guerra_facciones_defender":
            from guerra_facciones import cmd_guerra_facciones_defender
            await cmd_guerra_facciones_defender(update, context)

        elif comando_destino == "/saltar_guerra":
            from guerra_facciones import cmd_saltar_guerra
            await cmd_saltar_guerra(update, context)

        elif comando_destino == "/auto_recoleccion":
            from recoleccion_auto import cmd_auto_recoleccion
            await cmd_auto_recoleccion(update, context)

        elif comando_destino == "/pvp_buscar":
            from pvp_mortal import cmd_pvp_buscar
            await cmd_pvp_buscar(update, context)

        elif comando_destino == "/pvp_multi":
            from pvp_mortal import cmd_pvp_multi
            await cmd_pvp_multi(update, context)

    except Exception as e:
        await update.effective_message.reply_text(f"⚠️ Error: {e}")


async def _handle_duelo_menu(update, context, jug: dict):
    """Botón ⚔️ Duelos — muestra jugadores disponibles para retar, sin abrir el menú ciudad."""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    user_id = jug["user_id"]
    zona    = jug.get("zona_actual", "")

    todos   = db_helper.obtener_todos_jugadores()
    rivales = [
        j for j in todos
        if j["user_id"] != user_id
        and j.get("ubicacion", "ciudad") != "viaje"
    ]

    if not rivales:
        await update.effective_message.reply_text(
            "⚔️ No hay otros jugadores disponibles para duelo ahora mismo.\n\n"
            "También puedes retar directamente con <code>/duelo &lt;user_id&gt;</code>.",
            parse_mode="HTML"
        )
        return

    botones = [
        [InlineKeyboardButton(
            f"⚔️ {j['nombre_personaje']}  —  Nv.{j.get('nivel', 1)} {j.get('clase', '')}",
            callback_data=f"tkpvp_{j['user_id']}"
        )]
        for j in rivales[:8]
    ]
    botones.append([InlineKeyboardButton("❌ Cancelar", callback_data="tkpvp_cancel")])

    await update.effective_message.reply_text(
        "⚔️ <b>Duelos PvP</b>\n\nElige a quién retar:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(botones)
    )


async def _handle_atacar_zona(update, context, jug: dict):
    """Muestra inline keyboard con jugadores en la misma zona para retar a duelo."""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    user_id = jug["user_id"]
    zona    = jug.get("zona_actual", "")
    color   = _detectar_color(zona)

    if color in ("ciudad", ""):
        await update.effective_message.reply_text(
            "⚔️ No puedes atacar jugadores en ciudad.\nViaja a una zona salvaje primero."
        )
        return

    todos   = db_helper.obtener_todos_jugadores()
    en_zona = [
        j for j in todos
        if j.get("zona_actual") == zona
        and j["user_id"] != user_id
        and j.get("ubicacion", "ciudad") == "salvaje"
    ]

    if not en_zona:
        await update.effective_message.reply_text(
            f"⚔️ No hay otros jugadores en <b>{zona}</b> en este momento.",
            parse_mode="HTML"
        )
        return

    botones = [
        [InlineKeyboardButton(
            f"⚔️ {j['nombre_personaje']}  —  Nv.{j.get('nivel', 1)} {j.get('clase', '')}",
            callback_data=f"tkpvp_{j['user_id']}"
        )]
        for j in en_zona[:8]
    ]
    botones.append([InlineKeyboardButton("❌ Cancelar", callback_data="tkpvp_cancel")])

    await update.effective_message.reply_text(
        f"⚔️ <b>Jugadores en {zona}:</b>\n\nElige a quién retar a duelo:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(botones)
    )


async def cb_tkpvp(update, context):
    """Callback del selector de objetivo PvP — inicia el duelo directamente."""
    query = update.callback_query
    await query.answer()

    if query.data == "tkpvp_cancel":
        try:
            await query.edit_message_text("❌ Cancelado.")
        except Exception:
            pass
        return

    try:
        oponente_id = int(query.data.split("_")[1])
    except (ValueError, IndexError):
        await query.edit_message_text("❌ Error al procesar la selección.")
        return

    # Cerrar el selector
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass

    # Lanzar el duelo usando la lógica de combate
    context.args = [str(oponente_id)]
    from combate import cmd_duelo
    await cmd_duelo(update, context)


def _detectar_color(zona_nombre: str) -> str:
    """Detecta el color de la zona a partir del nombre."""
    try:
        from datos_zona import ZONAS
        for z in ZONAS:
            if z["nombre"] == zona_nombre:
                tipo = z.get("tipo", "salvaje")
                if tipo == "ciudad":
                    return "ciudad"
                return z.get("color", "azul")
    except Exception:
        pass
    return "azul"


# ─── FUNCIÓN AUXILIAR: enviar/actualizar el teclado ──────────────────────────

async def enviar_teclado(update_or_message, context: ContextTypes.DEFAULT_TYPE,
                         texto: str = "⚡ Accesos rápidos actualizados.",
                         ubicacion: str = "ciudad"):
    """
    Envía un mensaje silencioso que actualiza el teclado inferior.
    Respeta la preferencia del jugador: si lo tiene oculto, no lo fuerza.
    Llamar desde /start, /ciudad, viaje_llegada, etc.
    """
    # Resolver mensaje
    if hasattr(update_or_message, "message") and update_or_message.message:
        msg = update_or_message.message
    elif hasattr(update_or_message, "callback_query") and update_or_message.callback_query:
        msg = update_or_message.callback_query.message
    else:
        msg = update_or_message  # ya es un Message

    # Obtener user_id para comprobar preferencia
    user_id = None
    if hasattr(update_or_message, "effective_user") and update_or_message.effective_user:
        user_id = update_or_message.effective_user.id
    elif hasattr(msg, "from_user") and msg.from_user:
        user_id = msg.from_user.id

    # Si el jugador tiene el teclado oculto, respetar su preferencia
    if user_id and _teclado_esta_oculto(user_id):
        await msg.reply_text(texto)
        return

    if ubicacion == "salvaje":
        kb = get_teclado_salvaje(user_id or 0)
    else:
        kb = get_teclado_principal(user_id or 0)

    await msg.reply_text(texto, reply_markup=kb)


# ─── REGISTRO ─────────────────────────────────────────────────────────────────

def registrar_handlers(app):
    # Botón "Ocultar teclado" (prioridad alta para que no pase a otros handlers)
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.Regex(r"^🔲 Ocultar teclado$"),
            handle_ocultar_teclado
        ),
        group=0
    )
    # Comando /teclado (toggle)
    app.add_handler(CommandHandler("teclado", cmd_teclado))
    # Interceptar pulsaciones de botón (MessageHandler con texto exacto).
    # \ufe0f? hace el selector de variante emoji opcional (Telegram a veces lo omite).
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.Regex(
                "^(👤 Perfil|🏙\ufe0f? Ciudad|🎒 Inventario|✈\ufe0f? Viajar|"
                "⚔\ufe0f? Duelos|🏰 Gremio|⛏\ufe0f? Recolectar|🔍 Investigar|"
                "🏰 Mazmorra|⚔\ufe0f? Atacar jugador|🔐 Admin|🐛 Debug|📋 Comandos|📖 Guía|"
                "🏆 Rankings|🌑 Umbral|"
                "⚔\ufe0f? Atacar en guerra|🛡\ufe0f? Defender en guerra|⏭\ufe0f? Saltar guerra|"
                "🤖 Auto-Recolección|"
                "⚔\ufe0f? Emboscada PvP|"
                "🌐 Emboscada Zonas 🟡|🌐 Emboscada Zonas 🔴|🌐 Emboscada Zonas ⬛)$"
            ),
            handle_boton_rapido
        ),
        group=0
    )
    # Callback: mostrar teclado desde botón inline
    app.add_handler(CallbackQueryHandler(cb_teclado_mostrar, pattern=r"^teclado_mostrar$"))
    # Callback del selector PvP por zona
    app.add_handler(CallbackQueryHandler(cb_tkpvp, pattern=r"^tkpvp_"))

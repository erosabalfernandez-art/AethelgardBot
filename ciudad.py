# ciudad.py
# Módulo de la ciudad principal (zona azul).
# Contiene: crafteo, encantamientos, herrero, duelos de práctica,
# taberna, banco personal, alquiler de monturas, portal a mazmorra y salida al exterior.
# Integrado con el sistema de viajes (viajes.py) y monturas unificado.

import sqlite3
import random
import types
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, CommandHandler, CallbackQueryHandler,
    ConversationHandler, MessageHandler, filters
)

import economia
import db_helper
from combate import iniciar_combate, COMBATE_PVP_AMISTOSO

def _esc_md(s: str) -> str:
    return str(s).replace("_", "\\_").replace("*", "\\*").replace("`", "\\`").replace("[", "\\[")

# Importaciones de otros módulos (asumimos que existen y tienen lo necesario)
from crafteo import cmd_craftear
from viajes import (
    _obtener_montura_activa, _agregar_montura_inventario, _equipar_montura,
    reanudar_viaje, _obtener_destino, _iniciar_viaje_directo,
    _obtener_destinos_por_faccion, _obtener_destinos
)
from datos_zona import ZONAS
from clases import CLASES
from tienda import cmd_tienda  # para redirigir tiendas

DB_PATH = "aethelgard.db"

def _wrap_query(query):
    """PTB v20+: update.message es solo lectura. Devuelve un namespace con .message y .effective_message apuntando al mensaje del callback."""
    ns = types.SimpleNamespace()
    ns.message = query.message
    ns.effective_message = query.message
    ns.effective_user = query.from_user
    ns.effective_chat = query.message.chat
    ns.callback_query = None
    return ns

# Estados para las conversaciones
(ESP_CRAFT_SELECCION, ESP_CRAFT_CANTIDAD, ESP_ENCANTAR_SELECCION, ESP_ENCANTAR_CONFIRMAR,
 ESP_HERRERO_SELECCION, ESP_DUELO_INVITAR, ESP_TABERNA_DESCANSAR,
 ESP_BANCO_DEPOSITAR, ESP_BANCO_RETIRAR, ESP_BANCO_CANTIDAD,
 ESP_ALQUILER_CONFIRMAR) = range(11)

# Estados para el flujo de registro /start
START_NOMBRE, START_CLASE, START_FACCION = range(100, 103)

# ==================== FUNCIÓN AUXILIAR _en_ciudad ====================
def _en_ciudad(user_id: int) -> bool:
    """Retorna True si el jugador está en una ciudad (tipo 'ciudad' en datos_zona)."""
    try:
        zona_nombre = db_helper.obtener_zona_actual(user_id)
        for zona in ZONAS:
            if zona["nombre"] == zona_nombre and zona["tipo"] == "ciudad":
                return True
    except:
        pass
    return False

# ==================== TABLAS ADICIONALES (banco personal) ====================
def _init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS banco_personal (
        user_id INTEGER PRIMARY KEY,
        items TEXT DEFAULT '[]'
    )''')
    conn.commit()
    conn.close()

_init_db()

# ==================== RECETAS DE CRAFTEO ====================
# Nota: Las recetas se extraen de crafteo.py o recetas.py.
# Para no duplicar, en ciudad.py solo redirigimos a crafteo.
# Por lo tanto, no definimos RECETAS aquí.

# ==================== ENCANTAMIENTOS ====================
ENCANTAMIENTOS = {
    ".1": {"nombre": "Raro", "bonus_daño": 10, "bonus_vida": 20, "costo_eternium": 50, "material": "esencia_naturaleza"},
    ".2": {"nombre": "Épico", "bonus_daño": 20, "bonus_vida": 40, "costo_eternium": 150, "material": "alma_atrapada"},
    ".3": {"nombre": "Legendario", "bonus_daño": 30, "bonus_vida": 60, "costo_eternium": 400, "material": "reliquia_vacio"}
}

# ==================== MONTURAS PARA ALQUILER ====================
MONTURAS_ALQUILER = {
    "caballo": {"nombre": "🐎 Caballo", "precio_oro": 200, "precio_eternium": 0, "velocidad": 30, "duracion_horas": 1},
    "lobo": {"nombre": "🐺 Lobo de Guerra", "precio_oro": 500, "precio_eternium": 5, "velocidad": 50, "duracion_horas": 2},
    "corcel": {"nombre": "🐴 Corcel de Sombras", "precio_oro": 0, "precio_eternium": 20, "velocidad": 80, "duracion_horas": 4}
}

# ==================== FUNCIONES AUXILIARES (banco personal) ====================
def _obtener_banco(user_id: int) -> List[Dict]:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT items FROM banco_personal WHERE user_id = ?', (user_id,))
    row = c.fetchone()
    conn.close()
    if row and row[0]:
        return eval(row[0])
    return []

def _guardar_banco(user_id: int, items: List[Dict]):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO banco_personal (user_id, items) VALUES (?, ?)', (user_id, str(items)))
    conn.commit()
    conn.close()

# ==================== FUNCIONES DE MONTURAS ====================
def _tiene_montura_activa(user_id: int) -> bool:
    """Verifica si el jugador tiene una montura activa (alquilada o permanente) usando viajes."""
    try:
        return _obtener_montura_activa(user_id) is not None
    except:
        return False

def _obtener_montura_activa_nombre(user_id: int) -> Optional[str]:
    """Devuelve el nombre de la montura activa si existe."""
    try:
        montura = _obtener_montura_activa(user_id)
        if montura:
            from monturas import MONTURAS
            datos = MONTURAS.get(montura["montura_id"])
            return datos.get("nombre") if datos else montura["montura_id"]
    except:
        pass
    return None

def _alquilar_montura_viajes(user_id: int, montura_id: str, duracion_horas: int, velocidad: int) -> bool:
    """Añade la montura al inventario con expiración y la equipa automáticamente."""
    try:
        expira = datetime.now() + timedelta(hours=duracion_horas)
        _agregar_montura_inventario(user_id, montura_id, expira=expira)
        _equipar_montura(user_id, montura_id)
        return True
    except Exception:
        return False

# ==================== COMANDO PRINCIPAL ====================
async def cmd_ciudad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        await update.effective_message.reply_text("Primero crea un personaje con /start.")
        return
    try:
        from guerra_facciones import check_lockdown
        if await check_lockdown(update):
            return
    except Exception:
        pass
    # Solo marcar como 'en ciudad' si el jugador realmente está en una ciudad
    en_ciudad = _en_ciudad(user_id)
    if en_ciudad:
        try:
            db_helper.actualizar_jugador(user_id, ubicacion="ciudad")
        except Exception:
            pass
    await _mostrar_menu_principal_msg(update, context, user_id, jug)
    # Teclado persistente inferior — respetar la zona real del jugador
    msg = update.message or (update.callback_query.message if update.callback_query else None)
    if msg:
        try:
            from teclado_rapido import get_teclado_principal, get_teclado_salvaje
            kb = get_teclado_principal(user_id) if en_ciudad else get_teclado_salvaje(user_id)
            await msg.reply_text(
                f"📍 *{_esc_md(jug['nombre_personaje'])}* · Nv.{jug['nivel']} · "
                f"🪙 {jug.get('oro', 0):,} · 💎 {jug.get('eternium', 0)}",
                reply_markup=kb,
                parse_mode="Markdown"
            )
        except Exception:
            pass

async def _mostrar_menu_principal_msg(update, context, user_id: int, jug=None, editar: bool = False):
    if jug is None:
        jug = db_helper.obtener_jugador(user_id)
    montura = _obtener_montura_activa_nombre(user_id)
    texto = (
        f"🏙️ *Bienvenido a la Ciudad*\n\n"
        f"🧙 {jug['nombre_personaje']} | Nivel {jug['nivel']} | {jug['clase']}\n"
        f"❤️ HP: {jug['hp_actual']}/{jug['hp_max']}\n"
    )
    if montura:
        texto += f"🐎 Montura activa: {montura}\n"
    texto += "\n¿Qué deseas hacer?"
    # ── Comprobar si hay guerra de facciones activa ────────────────────────
    guerra_activa = None
    try:
        import guerra_facciones as _gf
        guerra_activa = _gf._obtener_guerra_activa()
    except Exception:
        pass

    if guerra_activa:
        gid = guerra_activa["id"]
        # Texto especial de guerra
        try:
            marcador_txt = _gf._texto_marcador(guerra_activa)
        except Exception:
            marcador_txt = "⚔️ *GUERRA DE FACCIONES ACTIVA*"
        texto = (
            f"🏙️ *{jug['nombre_personaje']}* — Ciudad en pie de guerra\n\n"
            f"{marcador_txt}\n\n"
            "🔒 _Las actividades normales están suspendidas. Elige tu acción:_"
        )
        # Comprobar si ya actuó
        try:
            ya_actuo = _gf._jugador_ya_actuo(gid, user_id)
        except Exception:
            ya_actuo = False
        if ya_actuo:
            keyboard = [
                [InlineKeyboardButton("📊 Ver marcador",   callback_data=f"gf_marcador_solo"),
                 InlineKeyboardButton("👤 Perfil",         callback_data="ciudad_perfil")],
                [InlineKeyboardButton("🎒 Inventario",     callback_data="ciudad_inventario"),
                 InlineKeyboardButton("📖 Guía",           callback_data="ciudad_guia")],
                [InlineKeyboardButton("❌ Cerrar",         callback_data="ciudad_cerrar")],
            ]
            texto += "\n\n✅ *Ya has registrado tu acción.* Espera a que termine la batalla."
        else:
            keyboard = [
                [InlineKeyboardButton("⚔️ ATACAR",         callback_data=f"gf_menu_atk_{gid}"),
                 InlineKeyboardButton("🛡️ DEFENDER",       callback_data=f"gf_menu_def_{gid}")],
                [InlineKeyboardButton("⏭️ Saltarse",       callback_data=f"gf_saltar_{gid}"),
                 InlineKeyboardButton("📊 Marcador",        callback_data=f"gf_estado_{gid}")],
                [InlineKeyboardButton("👤 Perfil",          callback_data="ciudad_perfil"),
                 InlineKeyboardButton("🎒 Inventario",      callback_data="ciudad_inventario")],
                [InlineKeyboardButton("📖 Guía",            callback_data="ciudad_guia"),
                 InlineKeyboardButton("❌ Cerrar",          callback_data="ciudad_cerrar")],
            ]
    else:
        keyboard = [
            [InlineKeyboardButton("🛠️ Servicios",      callback_data="submenu_servicios"),
             InlineKeyboardButton("🛒 Comercio",        callback_data="submenu_comercio")],
            [InlineKeyboardButton("⚔️ Combate",         callback_data="submenu_combate"),
             InlineKeyboardButton("🏰 Gremio",          callback_data="submenu_gremio")],
            [InlineKeyboardButton("🌀 Mazmorras",       callback_data="submenu_mazmorras"),
             InlineKeyboardButton("⚗️ Contenido",       callback_data="submenu_contenido")],
            # ── Nuevos sistemas ──────────────────────────────────────────────
            [InlineKeyboardButton("🗓️ Diario",          callback_data="submenu_diario"),
             InlineKeyboardButton("⚡ Utilidades",       callback_data="submenu_utilidades")],
            # ────────────────────────────────────────────────────────────────
            [InlineKeyboardButton("🏆 Rankings",         callback_data="ciudad_rankings"),
             InlineKeyboardButton("🕯️ Donar al Ritual",  callback_data="ciudad_umbral_donar")],
            [InlineKeyboardButton("🗺️ Mi Mapa",          callback_data="ciudad_mapa"),
             InlineKeyboardButton("📖 Guía",             callback_data="ciudad_guia")],
            [InlineKeyboardButton("👤 Perfil",           callback_data="ciudad_perfil"),
             InlineKeyboardButton("🎒 Inventario",       callback_data="ciudad_inventario")],
            [InlineKeyboardButton("🌳 Salir al salvaje", callback_data="ciudad_salir")],
            [InlineKeyboardButton("❌ Cerrar",           callback_data="ciudad_cerrar")],
        ]
        # Botones opcionales: Membresía y Cofre Personal (según preferencias del jugador)
        try:
            import cofre_personal as _cp
            _prefs = _cp._get_prefs(user_id)
            _fila_extra = []
            if _prefs.get("mostrar_membresia", True):
                _fila_extra.append(InlineKeyboardButton("🎫 Membresía", callback_data="ciudad_membresia"))
            if _prefs.get("mostrar_cofre", True):
                _fila_extra.append(InlineKeyboardButton("📦 Cofre Personal", callback_data="ciudad_cofre"))
            if _fila_extra:
                keyboard.insert(-2, _fila_extra)
        except Exception:
            pass
    # Botón de admin solo visible para admins y superadmin (siempre visible)
    try:
        import superadmin as _sa
        if _sa._nivel_admin(user_id) >= 1:
            keyboard.insert(-1, [InlineKeyboardButton("🛡️ Menú Admin", callback_data="admin_panel_menu")])
    except Exception:
        pass
    markup = InlineKeyboardMarkup(keyboard)
    if editar:
        try:
            cb = update.callback_query
            await cb.edit_message_text(texto, reply_markup=markup, parse_mode="Markdown")
            return
        except Exception:
            pass
    msg = update.effective_message
    if msg is None:
        return
    await msg.reply_text(texto, reply_markup=markup, parse_mode="Markdown")

async def ciudad_submenu_servicios(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    keyboard = [
        [InlineKeyboardButton("🔨 Craftear",        callback_data="ciudad_craftear_redirect")],
        [InlineKeyboardButton("✨ Encantar",         callback_data="ciudad_encantar")],
        [InlineKeyboardButton("🔧 Herrero",          callback_data="ciudad_herrero")],
        [InlineKeyboardButton("🍺 Taberna",          callback_data="ciudad_taberna")],
        [InlineKeyboardButton("🏦 Banco Personal",   callback_data="ciudad_banco")],
        [InlineKeyboardButton("🐎 Alquilar montura", callback_data="ciudad_alquilar")],
        [InlineKeyboardButton("🔙 Volver",           callback_data="ciudad_menu_principal")],
    ]
    await query.edit_message_text(
        "🛠️ *Servicios de la Ciudad*\nElige un servicio:",
        reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
    )
    try:
        import guia_contextual as _gc
        await _gc.enviar(user_id, context, "submenu_servicios")
    except Exception:
        pass

async def ciudad_submenu_comercio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    keyboard = [
        [InlineKeyboardButton("🪙 Tienda Oro",          callback_data="ciudad_tienda_oro")],
        [InlineKeyboardButton("💎 Tienda Eternium",    callback_data="ciudad_tienda_eternium")],
        [InlineKeyboardButton("✨ Tienda Créditos",    callback_data="ciudad_tienda_creditos")],
        [InlineKeyboardButton("🏛️ Subastas",          callback_data="ciudad_subastas")],
        [InlineKeyboardButton("🤝 Mercado P2P",        callback_data="ciudad_p2p")],
        [InlineKeyboardButton("📈 Bolsa de Valores",   callback_data="ciudad_bolsa")],
        [InlineKeyboardButton("✨ Créditos del Vacío", callback_data="ciudad_depositos")],
        [InlineKeyboardButton("🔙 Volver",             callback_data="ciudad_menu_principal")],
    ]
    await query.edit_message_text(
        "🛒 *Comercio*\nElige dónde ir:",
        reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
    )
    try:
        import guia_contextual as _gc
        await _gc.enviar(user_id, context, "submenu_comercio")
    except Exception:
        pass

async def ciudad_submenu_combate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    keyboard = [
        [InlineKeyboardButton("⚔️ Duelos PvP",    callback_data="ciudad_duelos")],
    ]
    try:
        import jefes as _jefes
        jefe_activo = _jefes._obtener_jefe_activo(chat_id)
        if jefe_activo:
            nombre_jefe = jefe_activo.get("nombre", "Jefe")
            estado_jefe = jefe_activo.get("estado", "")
            if estado_jefe == "reclutando":
                keyboard.append([InlineKeyboardButton(f"👹 Unirse: {nombre_jefe}", callback_data="jefe_unirse_btn")])
            elif estado_jefe == "combatiendo":
                keyboard.append([InlineKeyboardButton(f"⚔️ Atacar: {nombre_jefe}", callback_data="jefe_atacar_btn")])
            else:
                keyboard.append([InlineKeyboardButton(f"👹 Jefe Raid: {nombre_jefe}", callback_data="jefe_info_btn")])
        else:
            keyboard.append([InlineKeyboardButton("👹 Jefes Raid (sin jefe activo)", callback_data="jefe_info_btn")])
    except Exception:
        pass
    keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data="ciudad_menu_principal")])
    await query.edit_message_text(
        "⚔️ *Combate*\nElige tu tipo de combate:",
        reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
    )
    try:
        import guia_contextual as _gc
        await _gc.enviar(user_id, context, "submenu_combate")
    except Exception:
        pass

async def ciudad_submenu_gremio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    keyboard = [
        [InlineKeyboardButton("🛡️ Mi Gremio",           callback_data="cb_mi_gremio_menu")],
        [InlineKeyboardButton("🏰 Crear Gremio",         callback_data="gremio_crear_inicio")],
        [InlineKeyboardButton("🔍 Buscar Gremios",       callback_data="gremio_buscar")],
        [InlineKeyboardButton("📊 Nivel del Gremio",     callback_data="ciudad_gremio_nivel")],
        [InlineKeyboardButton("💬 Chat del Gremio",      callback_data="ciudad_gchat_log")],
        [InlineKeyboardButton("⚔️ Solicitar Guerra",     callback_data="ciudad_guerra_gremios_info")],
        [InlineKeyboardButton("🔙 Volver",               callback_data="ciudad_menu_principal")],
    ]
    await query.edit_message_text(
        "🏰 *Gremio*\nGestiona tu gremio:",
        reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
    )
    try:
        import guia_contextual as _gc
        await _gc.enviar(user_id, context, "submenu_gremio")
    except Exception:
        pass

async def ciudad_submenu_mazmorras(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    jug = db_helper.obtener_jugador(user_id)

    zona_color = "azul"
    if jug:
        try:
            from viajes import _obtener_destino
            zona_id = jug.get("zona_actual_id")
            if zona_id:
                destino = _obtener_destino(zona_id)
                if destino and destino.get("color"):
                    zona_color = destino["color"]
        except Exception:
            pass

    mapa_zonas = {
        "azul":     ("🔵", "Zona Azul — Fácil",    "cb_mazmorra_azul"),
        "amarilla": ("🟡", "Zona Amarilla — Medio", "cb_mazmorra_amarilla"),
        "roja":     ("🔴", "Zona Roja — Difícil",   "cb_mazmorra_roja"),
        "negra":    ("⚫", "Zona Negra — Élite",    "cb_mazmorra_negra"),
    }
    emoji, label, cb = mapa_zonas.get(zona_color, mapa_zonas["azul"])
    keyboard = [
        [InlineKeyboardButton(f"{emoji} {label}", callback_data=cb)],
        [InlineKeyboardButton("🔙 Volver", callback_data="ciudad_menu_principal")],
    ]
    await query.edit_message_text(
        f"🌀 *Mazmorras*\nEstás en zona *{zona_color}*.\nSolo puedes acceder a la mazmorra de tu zona actual:",
        reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
    )
    try:
        import guia_contextual as _gc
        await _gc.enviar(user_id, context, "submenu_mazmorras")
    except Exception:
        pass

async def ciudad_submenu_contenido(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    try:
        import guia_contextual as _gc
        await _gc.enviar(user_id, context, "submenu_contenido")
    except Exception:
        pass
    keyboard = [
        [InlineKeyboardButton("⛏️ Recolección",        callback_data="ciudad_recoleccion")],
        [InlineKeyboardButton("🔬 Investigación",       callback_data="ciudad_investigacion")],
        [InlineKeyboardButton("🗺️ Viajes",              callback_data="ciudad_viajes")],
        [InlineKeyboardButton("⚡ Stamina & Invitación", callback_data="ciudad_stamina_info")],
        [InlineKeyboardButton("⏳ Mis Cooldowns",       callback_data="util_cooldowns")],
        [InlineKeyboardButton("👥 Jugadores en Zona",   callback_data="util_zona_jugadores")],
        [InlineKeyboardButton("🔙 Volver",              callback_data="ciudad_menu_principal")],
    ]
    await query.edit_message_text(
        "⚗️ *Contenido del Mundo*\nElige una actividad:",
        reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
    )

async def ciudad_submenu_diario(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Submenú 🗓️ Diario — login, misiones diarias, racha."""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    # Mostrar racha actual si está disponible
    racha_txt = ""
    try:
        import login_diario as _ld
        estado_ld = _ld._estado_login(user_id)
        racha = estado_ld.get("racha", 0)
        puede = estado_ld.get("puede_reclamar", False)
        if racha and racha > 0:
            icono = "🎁" if puede else "✅"
            racha_txt = f"\n🔥 Racha: *{racha} día(s)* {icono}"
    except Exception:
        pass

    keyboard = [
        [InlineKeyboardButton("🎁 Recompensa diaria",    callback_data="diario_login_hoy")],
        [InlineKeyboardButton("📋 Misiones del día",     callback_data="diario_misiones_hoy")],
        [InlineKeyboardButton("📊 Resumen de sesión",    callback_data="diario_resumen_sesion")],
        [InlineKeyboardButton("🔙 Volver",               callback_data="ciudad_menu_principal")],
    ]
    await query.edit_message_text(
        f"🗓️ *Actividades Diarias*\nCompleta tus tareas del día y mantén tu racha.{racha_txt}",
        reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
    )
    try:
        import guia_contextual as _gc
        await _gc.enviar(user_id, context, "submenu_diario")
    except Exception:
        pass


async def ciudad_submenu_utilidades(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Submenú ⚡ Utilidades — cooldowns, zona activa."""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    keyboard = [
        [InlineKeyboardButton("⏳ Ver mis cooldowns",         callback_data="util_cooldowns")],
        [InlineKeyboardButton("👥 Jugadores en mi zona",      callback_data="util_zona_jugadores")],
        [InlineKeyboardButton("⚡ Estado de Stamina",         callback_data="ciudad_stamina_info")],
        [InlineKeyboardButton("🔙 Volver",                    callback_data="ciudad_menu_principal")],
    ]
    await query.edit_message_text(
        "⚡ *Utilidades*\nHerramientas e información rápida:",
        reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
    )


async def _diario_login_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        import login_diario as _ld
        await _ld.cmd_login(update, context)
    except Exception as e:
        await query.message.reply_text(f"❌ Error: {e}")


async def _diario_misiones_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        import misiones_diarias as _md
        await _md.cmd_misiones_hoy(update, context)
    except Exception as e:
        await query.message.reply_text(f"❌ Error: {e}")


async def _diario_resumen_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    try:
        import resumen_sesion as _rs
        conn = __import__("sqlite3").connect(_rs.DB_PATH)
        conn.row_factory = __import__("sqlite3").Row
        c = conn.cursor()
        c.execute("SELECT * FROM sesiones_zona WHERE user_id = ?", (user_id,))
        row = c.fetchone()
        conn.close()
        if not row:
            await query.message.reply_text("📊 No hay sesión activa. Viaja al salvaje para empezar.")
            return
        r = dict(row)
        txt = (
            f"📊 *Resumen de sesión — {r.get('zona','Desconocida')}*\n\n"
            f"⚔️ Monstruos: *{r.get('monstruos',0)}*\n"
            f"🪙 Oro ganado: *{r.get('oro_ganado',0)}*\n"
            f"✨ XP ganada: *{r.get('xp_ganada',0)}*\n"
            f"⛏️ Recolecciones: *{r.get('recolecciones',0)}*\n"
            f"📦 Ítems: *{r.get('items_obtenidos','[]')}*"
        )
        await query.message.reply_text(txt, parse_mode="Markdown")
    except Exception as e:
        await query.message.reply_text(f"❌ Error al obtener resumen: {e}")


async def _util_cooldowns_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        import cooldown_info as _ci
        await _ci.cmd_cooldowns(update, context)
    except Exception as e:
        await query.message.reply_text(f"❌ Error: {e}")


async def _util_zona_jugadores_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        import zona_activa as _za
        await _za.cmd_zona_jugadores(update, context)
    except Exception as e:
        await query.message.reply_text(f"❌ Error: {e}")


async def _gchat_log_desde_ciudad_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        import gchat as _gc_mod
        await _gc_mod.cmd_gchat_log(update, context)
    except Exception as e:
        await query.message.reply_text(f"❌ Error: {e}")


async def ciudad_menu_principal_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    jug = db_helper.obtener_jugador(user_id)
    if _en_ciudad(user_id):
        try:
            db_helper.actualizar_jugador(user_id, ubicacion="ciudad")
        except Exception:
            pass
    await _mostrar_menu_principal_msg(update, context, user_id, jug, editar=True)
    try:
        import guia_contextual as _gc
        await _gc.enviar(user_id, context, "ciudad_menu")
    except Exception:
        pass

async def ciudad_jefes_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id
    try:
        import jefes as jefes_mod
        jefe = jefes_mod._obtener_jefe_activo(chat_id)
        if jefe:
            barra = jefes_mod._barra_hp(jefe["hp_actual"], jefe["hp_max"])
            await query.edit_message_text(
                f"🐉 *Jefe Activo: {jefe['nombre']}*\n"
                f"❤️ {barra}\n"
                f"Estado: {jefe['estado']} | Dificultad: {jefe['dificultad']}\n\n"
                f"/jefe_unirse — unirse | /jefe_atacar — atacar",
                parse_mode="Markdown"
            )
        else:
            await query.edit_message_text(
                "🐉 *Jefes (Raid Bosses)*\n\n"
                "No hay ningún jefe activo ahora mismo.\n"
                "Los admins pueden invocar uno con /jefe_iniciar",
                parse_mode="Markdown"
            )
    except ImportError:
        await query.edit_message_text("El sistema de jefes no está disponible.")

async def ciudad_gremio_nivel_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        import gremios_niveles
        await gremios_niveles.cmd_gremio_nivel(_wrap_query(query), context)
    except ImportError:
        await query.edit_message_text("Sistema de niveles de gremio no disponible.")

async def ciudad_guerra_facciones_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        import guerra_facciones
        await guerra_facciones.cmd_guerra_facciones_estado(_wrap_query(query), context)
    except ImportError:
        await query.edit_message_text("Sistema de guerra de facciones no disponible.")

async def ciudad_guerra_gremios_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        import guerra_gremios
        await guerra_gremios.cmd_guerra_gremios_estado(_wrap_query(query), context)
    except ImportError:
        await query.edit_message_text("Sistema de guerra de gremios no disponible.")


# ==================== COMANDO /start ====================
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from telegram.ext import ConversationHandler
    user_id = update.effective_user.id

    await update.effective_message.reply_text(
        "⚔️ *Aethelgard — Beta Abierta*\n\n"
        "Este juego se encuentra en su última beta abierta.\n"
        "Si notas cualquier error dentro del juego, por favor notifica al encargado de solución de bugs:\n\n"
        "📞 Telegram: +5588992543996\n"
        "👤 @Sterben033\n\n"
        "_Aethelgardbot2026 — Todos los derechos reservados._",
        parse_mode="Markdown"
    )

    jug = db_helper.obtener_jugador(user_id)
    if jug:
        await cmd_ciudad(update, context)
        return ConversationHandler.END
    await update.effective_message.reply_text(
        "✨ ¡Bienvenido a Aethelgard! ✨\n\n"
        "Eres un aventurero recién llegado.\n"
        "Primero, dime el nombre de tu personaje (máximo 20 caracteres, sin espacios):"
    )
    return START_NOMBRE

async def start_recibir_nombre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from telegram.ext import ConversationHandler
    nombre = update.message.text.strip()
    if len(nombre) > 20 or " " in nombre:
        await update.effective_message.reply_text("❌ Nombre inválido. Usa máximo 20 caracteres sin espacios. Intenta de nuevo:")
        return START_NOMBRE
    context.user_data["start_nombre"] = nombre
    context.user_data["start_estado"] = "esperando_clase"
    keyboard = []
    for clase_id, clase_data in CLASES.items():
        keyboard.append([InlineKeyboardButton(clase_data["nombre"], callback_data=f"start_clase_{clase_id}")])
    await update.effective_message.reply_text(
        "⚔️ *Elige tu Clase* ⚔️\n\n"
        "🛡️ *Vanguardista* — Guerrero de primera línea. Alta vida y defensa, protege a sus aliados con escudo y espada. Ideal para quien disfruta aguantar y controlar el combate.\n\n"
        "🗡️ *Acechante* — Asesino de las sombras. Baja vida pero daño crítico devastador. Golpea rápido, desaparece antes de que el enemigo pueda reaccionar.\n\n"
        "🔮 *Tejehechizos* — Maestro arcano. Lanza hechizos de gran potencia mágica. Frágil en cuerpo a cuerpo, pero imparable a distancia con el arte del vacío.\n\n"
        "🏹 *Maestro de Caza* — Arquero y explorador. Equilibrio entre daño, movilidad y supervivencia. Domina el terreno y elimina a los enemigos antes de que se acerquen.\n\n"
        "_Elige con cuidado — esta decisión marcará tu destino en Aethelgard._",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    # Fin del ConversationHandler — los callbacks de clase/facción los manejan
    # handlers independientes que leen context.user_data["start_estado"]
    return ConversationHandler.END

async def start_seleccionar_clase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler independiente (fuera del ConversationHandler) para la selección de clase."""
    query = update.callback_query
    await query.answer()
    # Solo actuar si el usuario está en el estado correcto
    if context.user_data.get("start_estado") not in ("esperando_clase",):
        return
    # Eliminar prefijo completo; clase_id puede tener guiones bajos (e.g. maestro_caza)
    clase_id = query.data[len("start_clase_"):]
    if clase_id not in CLASES:
        await query.edit_message_text("❌ Clase no válida. Usa /start para reiniciar.")
        context.user_data.clear()
        return
    context.user_data["start_clase"] = clase_id
    if db_helper.faccion_libre():
        context.user_data["start_estado"] = "esperando_faccion"
        facciones = ["Alianza", "Imperio", "Sindicato"]
        emojis    = {"Alianza": "⚔️", "Imperio": "🏛️", "Sindicato": "🗡️"}
        kb = [[InlineKeyboardButton(f"{emojis.get(f,'🏳️')} {f}", callback_data=f"start_faccion_{f}")] for f in facciones]
        await query.edit_message_text(
            "🏛️ *Elige tu Facción* 🏛️\n\n"
            "⚔️ *Alianza* — Guardianes del antiguo pacto. Sus caballeros defienden las ciudades libres con honor inquebrantable. Tienen acceso a los mejores herreros y curanderos del reino. Para quienes creen en la justicia y la hermandad.\n\n"
            "🏛️ *Imperio* — Los herederos del trono eterno. Expansionistas y ambiciosos, dominan la economía y la política de Aethelgard. Sus miembros gozan de ventajas comerciales y acceso a tecnología de guerra avanzada. Para quienes buscan poder y riqueza.\n\n"
            "🗡️ *Sindicato* — La red de sombras. Ladrones, espías y mercenarios que operan en los márgenes de la ley. Maestros de la información, el veneno y el engaño. Para quienes prefieren la libertad por encima de todo.\n\n"
            "_Esta elección determinará tus aliados, enemigos y oportunidades en Aethelgard. No la tomes a la ligera._",
            reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown"
        )
    else:
        faccion = db_helper.obtener_faccion_menos_poblada() or "Alianza"
        await _finalizar_registro(query, context, clase_id, faccion)

async def start_seleccionar_faccion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler independiente (fuera del ConversationHandler) para la selección de facción."""
    query = update.callback_query
    await query.answer()
    if context.user_data.get("start_estado") != "esperando_faccion":
        return
    faccion = query.data.replace("start_faccion_", "")
    clase_id = context.user_data.get("start_clase")
    if not clase_id:
        await query.edit_message_text("❌ Error en el registro. Usa /start de nuevo.")
        context.user_data.clear()
        return
    await _finalizar_registro(query, context, clase_id, faccion)

async def _finalizar_registro(query, context, clase_id: str, faccion: str):
    nombre  = context.user_data.get("start_nombre", "Aventurero")
    user_id = query.from_user.id
    exito   = db_helper.crear_jugador(user_id, nombre, clase_id, faccion)
    if not exito:
        await query.edit_message_text("Error al crear personaje. Contacta con administración.")
        context.user_data.clear()
        return
    context.user_data.clear()
    texto  = f"✅ *¡{nombre} ha nacido en Aethelgard!*\n\n"
    texto += f"🛡️ *Clase:* {CLASES[clase_id]['nombre']}\n"
    texto += f"🏛️ *Facción:* {faccion}\n"
    texto += "⚔️ Tus estadísticas han sido calculadas.\n\n"
    texto += "¡Tu aventura comienza ahora! Completa tus misiones de inicio para aprender el juego."
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("📋 Misiones de Inicio →", callback_data="misiones_inicio")]])
    await query.edit_message_text(texto, parse_mode="Markdown", reply_markup=kb)
    # Teclado persistente — primer contacto del jugador con los accesos rápidos
    try:
        user_id_kb = query.from_user.id if query.from_user else 0
        from teclado_rapido import get_teclado_principal
        await query.message.reply_text(
            "⚡ *¡Accesos rápidos activados!*\n"
            "Usa los botones de abajo para moverte rápido por el juego.\n"
            "Escribe /ciudad para empezar tu aventura.",
            reply_markup=get_teclado_principal(user_id_kb),
            parse_mode="Markdown"
        )
    except Exception:
        pass
    try:
        import misiones as _mis
        class _FakeUpdate:
            effective_user = query.from_user
            effective_message = query.message
        await _mis.mostrar_misiones_inicio(_FakeUpdate(), context)
    except Exception:
        pass

# ==================== REDIRECCIÓN A TIENDA ====================
async def ciudad_tienda_oro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await cmd_tienda(_wrap_query(query), context)

async def ciudad_tienda_eternium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await cmd_tienda(_wrap_query(query), context)

async def ciudad_tienda_creditos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await cmd_tienda(_wrap_query(query), context)

# ==================== SUBASTAS ====================
async def ciudad_subastas_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        import subastas as sub_mod
        await sub_mod.cmd_subastas(_wrap_query(query), context)
    except Exception as e:
        await query.message.reply_text(f"❌ Error al abrir subastas: {e}")

# ==================== MERCADO P2P ====================
async def ciudad_p2p_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        import p2p as p2p_mod
        await p2p_mod.cmd_mercado(_wrap_query(query), context)
    except Exception as e:
        await query.message.reply_text(f"❌ Error al abrir mercado P2P: {e}")

# ==================== RECOLECCIÓN ====================
async def ciudad_recoleccion_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        jug = db_helper.obtener_jugador(update.effective_user.id)
        zona_color = "azul"
        if jug:
            try:
                from viajes import _obtener_destino
                d = _obtener_destino(jug.get("zona_actual_id"))
                if d and d.get("color"):
                    zona_color = d["color"]
            except Exception:
                pass
        modulo = __import__(f"recoleccion_{zona_color}")
        await modulo.cmd_recolectar(_wrap_query(query), context)
    except Exception as e:
        await query.message.reply_text(f"❌ Recolección no disponible en tu zona: {e}")

# ==================== INVESTIGACIÓN ====================
async def ciudad_investigacion_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        await query.message.delete()
    except Exception:
        pass
    try:
        jug = db_helper.obtener_jugador(update.effective_user.id)
        zona_color = "azul"
        if jug:
            try:
                from viajes import _obtener_destino
                d = _obtener_destino(jug.get("zona_actual_id"))
                if d and d.get("color"):
                    zona_color = d["color"]
            except Exception:
                pass
        modulo = __import__(f"investigacion_{zona_color}")
        await modulo.cmd_investigar(_wrap_query(query), context)
    except Exception as e:
        await query.message.chat.send_message(f"❌ Investigación no disponible en tu zona: {e}")

# ==================== VIAJES ====================
async def ciudad_viajes_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        import viajes as viajes_mod
        await viajes_mod.cmd_viajar(_wrap_query(query), context)
    except Exception as e:
        await query.message.reply_text(f"❌ Sistema de viajes no disponible: {e}")

async def ciudad_stamina_info_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        await query.edit_message_text("❌ No estás registrado. Usa /start.")
        return
    stamina_actual, stamina_max, _ = db_helper.obtener_stamina(user_id)
    codigo = jug.get("codigo_invitacion", "N/A")
    completados = jug.get("reclutas_completados", 0)
    try:
        bonus_cfg = int(db_helper.obtener_config("recluta_bonus_stamina", "5"))
        nivel_cfg = int(db_helper.obtener_config("recluta_nivel_activacion", "15"))
        cond_txt = f"nivel {nivel_cfg}" if nivel_cfg > 0 else "al unirse"
    except Exception:
        bonus_cfg, nivel_cfg, cond_txt = 5, 15, "nivel 15"
    barras = int((stamina_actual / max(stamina_max, 1)) * 10)
    barra_txt = "█" * barras + "░" * (10 - barras)
    keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="submenu_contenido")]]
    await query.edit_message_text(
        f"⚡ *Stamina*\n"
        f"{barra_txt} {stamina_actual}/{stamina_max}\n\n"
        f"🔗 *Tu código de invitación:* `{codigo}`\n"
        f"👥 Reclutas completados: *{completados}*\n\n"
        f"*¿Cómo aumentar la stamina máxima?*\n"
        f"Comparte tu código con amigos. Cuando usen `/usar_codigo {codigo}` "
        f"y lleguen a {cond_txt}, tu stamina máxima sube *+{bonus_cfg}* por cada uno.\n\n"
        f"_También puedes usar_ /mi\\_codigo _en cualquier momento._",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ==================== MAZMORRAS (callbacks desde submenu) ====================
async def _mazmorra_cb(update: Update, context: ContextTypes.DEFAULT_TYPE, color: str):
    query = update.callback_query
    await query.answer()
    try:
        modulo = __import__(f"mazmorra_{color}")
        await modulo.cmd_mazmorra(_wrap_query(query), context)
    except Exception as e:
        await query.message.reply_text(f"❌ Mazmorra no disponible: {e}")

async def cb_mazmorra_azul(update, context):      await _mazmorra_cb(update, context, "azul")
async def cb_mazmorra_amarilla(update, context):  await _mazmorra_cb(update, context, "amarilla")
async def cb_mazmorra_roja(update, context):      await _mazmorra_cb(update, context, "roja")
async def cb_mazmorra_negra(update, context):     await _mazmorra_cb(update, context, "negra")

# ==================== GUERRA DE GREMIOS - INFO ====================
async def ciudad_guerra_gremios_info_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver", callback_data="submenu_gremio")]])
    await query.edit_message_text(
        "⚔️ *Guerra de Gremios*\n\n"
        "Para solicitar una guerra entre gremios:\n\n"
        "1️⃣ El líder de tu gremio usa el comando:\n"
        "   `/solicitar_guerra <nombre_gremio_rival>`\n\n"
        "2️⃣ El líder del gremio rival recibirá una notificación para aceptar o rechazar.\n\n"
        "3️⃣ Si el rival acepta, la solicitud llegará al administrador para aprobación final.\n\n"
        "4️⃣ Una vez aprobada por el administrador, ¡la guerra comienza!\n\n"
        "_Solo los líderes de gremio pueden solicitar guerras._",
        reply_markup=kb, parse_mode="Markdown"
    )

# ==================== CRAFTEO ====================
async def ciudad_craftear_redirect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await cmd_craftear(_wrap_query(query), context)

# (Las funciones de crafteo conversacional no están aquí porque redirigen a crafteo.py)

# ==================== ENCANTAMIENTOS ====================
async def ciudad_encantar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    inv = db_helper.obtener_inventario(update.effective_user.id)
    items = [it for it in inv if (it["nombre"].startswith("arma_") or it["nombre"].startswith("armadura_")) and not it["nombre"].endswith((".1", ".2", ".3"))]
    if not items:
        await query.edit_message_text("No tienes armas ni armaduras sin encantar en tu inventario.")
        return
    keyboard = [[InlineKeyboardButton(f"{it['nombre']} (x{it['cantidad']})", callback_data=f"encantar_obj_{it['nombre']}")] for it in items]
    keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data="ciudad_volver")])
    await query.edit_message_text("Selecciona un objeto para encantar:", reply_markup=InlineKeyboardMarkup(keyboard))
    return ESP_ENCANTAR_SELECCION

async def encantar_seleccionar_objeto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    partes_enc = query.data.split("_", 2)
    if len(partes_enc) < 3:
        await query.edit_message_text("❌ Error al seleccionar objeto. Vuelve a intentarlo.")
        return
    obj_nombre = partes_enc[2]
    context.user_data["encantar_objeto"] = obj_nombre
    keyboard = [[InlineKeyboardButton(f"{nivel} ({datos['nombre']}) - {datos['costo_eternium']} eternium", callback_data=f"encantar_nivel_{nivel}")] for nivel, datos in ENCANTAMIENTOS.items()]
    keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data="ciudad_volver")])
    await query.edit_message_text(f"Objeto: {obj_nombre}\nSelecciona el nivel de encantamiento:", reply_markup=InlineKeyboardMarkup(keyboard))
    return ESP_ENCANTAR_CONFIRMAR

async def encantar_confirmar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _partes_enc = query.data.split("_")
    nivel = _partes_enc[2] if len(_partes_enc) > 2 else None
    user_id = update.effective_user.id
    obj_nombre = context.user_data.get("encantar_objeto")
    if not nivel or nivel not in ENCANTAMIENTOS or not obj_nombre:
        await query.edit_message_text("❌ Error al seleccionar encantamiento. Vuelve a intentarlo.")
        return
    enc = ENCANTAMIENTOS[nivel]
    inv = db_helper.obtener_inventario(user_id)
    item = next((it for it in inv if it["nombre"] == obj_nombre), None)
    if not item or item["cantidad"] < 1:
        await query.edit_message_text("Ya no tienes ese objeto.")
        return
    saldos = economia.obtener_saldos(user_id)
    if saldos["eternium"] < enc["costo_eternium"]:
        await query.edit_message_text(f"No tienes suficiente eternium. Necesitas {enc['costo_eternium']}.")
        return
    # Consumir material
    mat_nombre = enc["material"]
    tiene_mat = False
    for it in inv:
        if it["nombre"] == mat_nombre and it["cantidad"] >= 1:
            tiene_mat = True
            break
    if not tiene_mat:
        await query.edit_message_text(f"No tienes {mat_nombre}. Necesitas 1 unidad.")
        return
    economia.modificar_saldo(user_id, "eternium", -enc["costo_eternium"], f"encantamiento {nivel} a {obj_nombre}")
    db_helper.quitar_item(user_id, mat_nombre, 1)
    db_helper.quitar_item(user_id, obj_nombre, 1)
    nuevo_nombre = f"{obj_nombre}_{nivel}"
    db_helper.agregar_item(user_id, nuevo_nombre, 1)
    await query.edit_message_text(f"✅ Has encantado {obj_nombre} a nivel {nivel}. ¡Ahora tiene {enc['bonus_daño']}% más daño y {enc['bonus_vida']}% más vida!")
    context.user_data.clear()
    await cmd_ciudad(update, context)
    return ConversationHandler.END

# ==================== HERRERO ====================
async def ciudad_herrero(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    inv = db_helper.obtener_inventario(update.effective_user.id)
    if not inv:
        await query.edit_message_text("No tienes objetos para reparar.")
        return
    keyboard = [[InlineKeyboardButton(f"{it['nombre']} (x{it['cantidad']})", callback_data=f"reparar_{it['nombre']}")] for it in inv]
    keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data="ciudad_volver")])
    await query.edit_message_text("¿Qué objeto quieres reparar? (coste en materiales y oro)", reply_markup=InlineKeyboardMarkup(keyboard))
    return ESP_HERRERO_SELECCION

async def reparar_objeto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    obj_nombre = query.data.split("_", 1)[1]
    user_id = update.effective_user.id
    coste_oro = 50
    materiales = {"mineral_hierro": 2}
    saldos = economia.obtener_saldos(user_id)
    if saldos["oro"] < coste_oro:
        await query.edit_message_text(f"No tienes suficiente oro. Necesitas {coste_oro}.")
        return
    inv = db_helper.obtener_inventario(user_id)
    tiene_mat = True
    for mat, cant in materiales.items():
        if next((it["cantidad"] for it in inv if it["nombre"] == mat), 0) < cant:
            tiene_mat = False
            break
    if not tiene_mat:
        await query.edit_message_text(f"No tienes los materiales necesarios: {materiales}.")
        return
    economia.modificar_saldo(user_id, "oro", -coste_oro, f"reparación de {obj_nombre}")
    for mat, cant in materiales.items():
        db_helper.quitar_item(user_id, mat, cant)
    await query.edit_message_text(f"✅ Has reparado {obj_nombre}.")
    await cmd_ciudad(update, context)
    return ConversationHandler.END

# ==================== JEFE RAID BOTONES INLINE ====================
async def _jefe_btn_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Redirige los botones inline de Jefe Raid al módulo jefes."""
    query = update.callback_query
    await query.answer()
    accion = query.data  # jefe_unirse_btn / jefe_atacar_btn / jefe_info_btn
    try:
        import jefes as _jefes
        if accion == "jefe_unirse_btn":
            await _jefes.cmd_jefe_unirse(update, context)
        elif accion == "jefe_atacar_btn":
            await _jefes.cmd_jefe_atacar(update, context)
        else:
            await _jefes.cmd_jefe_info(update, context)
    except Exception as e:
        await query.edit_message_text(f"❌ Error al procesar acción de jefe: {e}")

# ==================== DUELOS ====================
async def ciudad_duelos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    jug = db_helper.obtener_jugador(user_id)
    nombre = jug["nombre_personaje"] if jug else query.from_user.first_name
    texto = (
        f"⚔️ *Duelos PvP*\n\n"
        f"👤 *Tu ID numérico:* `{user_id}`\n"
        f"_(cópialo y dáselo a otros jugadores para que puedan retarte)_\n\n"
        f"Para retar a alguien usa:\n"
        f"`/duelo <ID_numérico>`\n\n"
        f"*Ejemplo:* `/duelo 123456789`\n\n"
        f"⚠️ Solo puedes iniciar duelos desde dentro de una ciudad.\n"
        f"El rival recibirá una solicitud y tendrá 30 segundos para aceptar."
    )
    await query.edit_message_text(texto, parse_mode="Markdown")
    return ConversationHandler.END

async def cmd_duelo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if db_helper.esta_marcado(user_id):
        await update.effective_message.reply_text("❌ Estás marcado. No puedes iniciar duelo hasta que pagues rescate con /pagar_rescate.")
        return
    if not _en_ciudad(user_id):
        await update.effective_message.reply_text("🏙️ Los duelos solo pueden iniciarse dentro de las ciudades.")
        return
    if not context.args:
        await update.effective_message.reply_text("Uso: `/duelo @usuario`", parse_mode="Markdown")
        return
    nombre = context.args[0].replace("@", "")
    try:
        oponente_id = int(nombre)
    except:
        await update.effective_message.reply_text("Debes proporcionar el ID numérico del usuario (puedes obtenerlo con /info).")
        return
    if user_id == oponente_id:
        await update.effective_message.reply_text("No puedes desafiarte a ti mismo.")
        return
    if not db_helper.obtener_jugador(oponente_id):
        await update.effective_message.reply_text("El usuario no existe en el juego.")
        return
    keyboard = [
        [InlineKeyboardButton("Aceptar duelo", callback_data=f"duelo_aceptar_{user_id}_{oponente_id}"),
         InlineKeyboardButton("Rechazar", callback_data=f"duelo_rechazar_{user_id}_{oponente_id}")]
    ]
    await context.bot.send_message(
        chat_id=oponente_id,
        text=f"⚔️ {update.effective_user.first_name} te ha retado a un duelo amistoso. ¿Aceptas?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    await update.effective_message.reply_text("Solicitud de duelo enviada.")

async def aceptar_duelo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    parts = data.split("_")
    try:
        retador_id = int(parts[2])
        retado_id = int(parts[3])
    except (ValueError, IndexError):
        await query.answer("❌ Error en los datos del duelo.", show_alert=True)
        return
    if update.effective_user.id != retado_id:
        await query.edit_message_text("No puedes aceptar este duelo.")
        return
    await iniciar_combate(update, context, retador_id, retado_id, COMBATE_PVP_AMISTOSO)
    await query.edit_message_text("¡Duelo aceptado! El combate va a comenzar.")

async def rechazar_duelo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Has rechazado el duelo.")

# ==================== TABERNA ====================
async def _hook_mision_taberna(user_id: int, context):
    try:
        import misiones as _mis
        _mis.completar_mision(user_id, "usar_taberna", context)
    except Exception:
        pass

async def ciudad_taberna(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [[InlineKeyboardButton("🍺 Descansar (recuperar HP/MP - 50 oro)", callback_data="taberna_descansar")],
                [InlineKeyboardButton("📜 Escuchar lore", callback_data="taberna_lore")],
                [InlineKeyboardButton("🔙 Volver", callback_data="ciudad_volver")]]
    await query.edit_message_text("🍺 *Taberna*\n\n¿Qué deseas hacer?", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    user_id = update.effective_user.id
    await _hook_mision_taberna(user_id, context)
    return ESP_TABERNA_DESCANSAR

async def taberna_descansar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    saldos = economia.obtener_saldos(user_id)
    if saldos["oro"] < 50:
        await query.edit_message_text("❌ No tienes 50 oro para descansar.")
        return
    economia.modificar_saldo(user_id, "oro", -50, "descanso en taberna")
    jug = db_helper.obtener_jugador(user_id)
    if jug:
        db_helper.actualizar_jugador(user_id, hp_actual=jug["hp_max"])
    await query.edit_message_text("🍺 Has descansado. Tus HP y MP se han recuperado por completo.")
    await cmd_ciudad(update, context)
    return ConversationHandler.END

async def taberna_lore(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lore = [
        "Los antiguos héroes forjaron esta ciudad con sangre y sudor.",
        "Se dice que en las profundidades de la mazmorra duerme un dragón ancestral.",
        "El Consejo de Hierro controla las rutas comerciales.",
        "El Vacío corrompe todo lo que toca, pero aquí aún resistimos."
    ]
    await query.edit_message_text(f"📜 {random.choice(lore)}\n\n(Usa /ciudad para volver)")
    return ConversationHandler.END

# ==================== BANCO PERSONAL ====================
async def ciudad_banco(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("📥 Depositar objeto", callback_data="banco_depositar")],
        [InlineKeyboardButton("📤 Retirar objeto", callback_data="banco_retirar")],
        [InlineKeyboardButton("📋 Ver banco", callback_data="banco_ver")],
        [InlineKeyboardButton("🔙 Volver", callback_data="ciudad_volver")]
    ]
    await query.edit_message_text("🏦 *Banco personal*\n\nGuarda objetos que no quieras llevar en tu mochila.", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    return ESP_BANCO_DEPOSITAR

async def banco_depositar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    inv = db_helper.obtener_inventario(user_id)
    if not inv:
        await query.edit_message_text("No tienes objetos en tu inventario para depositar.")
        return
    keyboard = [[InlineKeyboardButton(f"{it['nombre']} (x{it['cantidad']})", callback_data=f"depositar_{it['nombre']}")] for it in inv]
    keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data="ciudad_volver")])
    await query.edit_message_text("Selecciona el objeto a depositar:", reply_markup=InlineKeyboardMarkup(keyboard))
    return ESP_BANCO_DEPOSITAR

async def banco_ejecutar_depositar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    obj_nombre = query.data.split("_", 1)[1]
    user_id = update.effective_user.id
    inv = db_helper.obtener_inventario(user_id)
    item = next((it for it in inv if it["nombre"] == obj_nombre), None)
    if not item:
        await query.edit_message_text("Ya no tienes ese objeto.")
        return
    cantidad = 1
    db_helper.quitar_item(user_id, obj_nombre, cantidad)
    banco = _obtener_banco(user_id)
    banco_item = next((it for it in banco if it["nombre"] == obj_nombre), None)
    if banco_item:
        banco_item["cantidad"] += cantidad
    else:
        banco.append({"nombre": obj_nombre, "cantidad": cantidad})
    _guardar_banco(user_id, banco)
    await query.edit_message_text(f"✅ Depositaste {cantidad} x {obj_nombre} en el banco.")
    await ciudad_banco(update, context)
    return ConversationHandler.END

async def banco_retirar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    banco = _obtener_banco(user_id)
    if not banco:
        await query.edit_message_text("El banco está vacío.")
        return
    keyboard = [[InlineKeyboardButton(f"{it['nombre']} (x{it['cantidad']})", callback_data=f"retirar_{it['nombre']}")] for it in banco]
    keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data="ciudad_volver")])
    await query.edit_message_text("Selecciona el objeto a retirar:", reply_markup=InlineKeyboardMarkup(keyboard))
    return ESP_BANCO_RETIRAR

async def banco_ejecutar_retirar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    obj_nombre = query.data.split("_", 1)[1]
    user_id = update.effective_user.id
    banco = _obtener_banco(user_id)
    item = next((it for it in banco if it["nombre"] == obj_nombre), None)
    if not item:
        await query.edit_message_text("Ese objeto ya no está en el banco.")
        return
    cantidad = 1
    item["cantidad"] -= cantidad
    if item["cantidad"] == 0:
        banco.remove(item)
    _guardar_banco(user_id, banco)
    db_helper.agregar_item(user_id, obj_nombre, cantidad)
    await query.edit_message_text(f"✅ Retiraste {cantidad} x {obj_nombre} del banco.")
    await ciudad_banco(update, context)
    return ConversationHandler.END

async def banco_ver(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    banco = _obtener_banco(user_id)
    if not banco:
        await query.edit_message_text("Tu banco está vacío.")
        return
    texto = "🏦 *Contenido del banco*\n\n"
    for it in banco:
        texto += f"• {it['nombre']}: x{it['cantidad']}\n"
    await query.edit_message_text(texto, parse_mode="Markdown")

# ==================== ALQUILER DE MONTURAS ====================
async def ciudad_alquilar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if _tiene_montura_activa(update.effective_user.id):
        await query.edit_message_text("Ya tienes una montura activa. Espera a que expire o úsala.")
        return
    keyboard = [[InlineKeyboardButton(f"{v['nombre']} - {v['precio_oro']} oro / {v['precio_eternium']} eternium", callback_data=f"alquilar_{k}")] for k, v in MONTURAS_ALQUILER.items()]
    keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data="ciudad_volver")])
    await query.edit_message_text("🐎 *Alquiler de monturas*\n\nSelecciona una:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    return ESP_ALQUILER_CONFIRMAR

async def alquilar_confirmar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    montura_id = query.data.split("_")[1]
    user_id = update.effective_user.id
    if _tiene_montura_activa(user_id):
        await query.edit_message_text("Ya tienes una montura activa.")
        return
    montura = MONTURAS_ALQUILER.get(montura_id)
    if not montura:
        await query.edit_message_text("Montura no válida.")
        return
    costo_oro = montura.get("precio_oro", 0)
    costo_et = montura.get("precio_eternium", 0)
    saldos = economia.obtener_saldos(user_id)
    if costo_oro > 0 and saldos["oro"] < costo_oro:
        await query.edit_message_text(f"No tienes suficiente oro. Necesitas {costo_oro}.")
        return
    if costo_et > 0 and saldos["eternium"] < costo_et:
        await query.edit_message_text(f"No tienes suficiente eternium. Necesitas {costo_et}.")
        return
    if costo_oro > 0:
        economia.modificar_saldo(user_id, "oro", -costo_oro, f"alquiler de {montura['nombre']}")
    if costo_et > 0:
        economia.modificar_saldo(user_id, "eternium", -costo_et, f"alquiler de {montura['nombre']}")
    exito = _alquilar_montura_viajes(user_id, montura_id, montura["duracion_horas"], montura["velocidad"])
    if exito:
        await query.edit_message_text(f"✅ ¡Has alquilado {montura['nombre']} por {montura['duracion_horas']} horas! +{montura['velocidad']}% de velocidad en viajes.")
    else:
        await query.edit_message_text("Error interno al registrar la montura. Contacta con administrador.")
    await cmd_ciudad(update, context)
    return ConversationHandler.END

# ==================== MAZMORRA ====================
async def ciudad_mazmorra(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        import mazmorra
        await mazmorra.cmd_mazmorra(update, context)
    except ImportError:
        await query.edit_message_text("🌀 La mazmorra aún no está disponible. Pronto será implementada.")
    except AttributeError:
        await query.edit_message_text("🌀 La mazmorra no tiene comando definido todavía.")

# ==================== SALIR AL SALVAJE ====================
async def ciudad_salir(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        await query.edit_message_text("Error: jugador no encontrado.")
        return
    faccion_id = jug.get("faccion_id", 1)
    try:
        # Buscar zona salvaje azul de la facción del jugador
        destinos = _obtener_destinos_por_faccion(faccion_id)
        salvaje = next((d for d in destinos if d["tipo"] == "salvaje" and d["color"] == "azul"), None)
        if not salvaje:
            # Fallback: buscar en todas las zonas salvajes azules
            todos = _obtener_destinos()
            salvaje = next((d for d in todos if d["tipo"] == "salvaje" and d["color"] == "azul"), None)
        if not salvaje:
            await query.edit_message_text("⚠️ No hay zonas salvajes disponibles. Contacta con el administrador.")
            return
        # Determinar origen: zona actual del jugador
        origen = _obtener_destino(jug.get("zona_actual_id"))
        if not origen:
            # Si el jugador aún no tiene zona_actual_id, buscar su ciudad por facción
            todos = _obtener_destinos()
            ciudad = next((d for d in todos if d["tipo"] == "ciudad" and d["faccion_id"] == faccion_id), None)
            if not ciudad:
                ciudad = next((d for d in todos if d["tipo"] == "ciudad"), None)
            origen = ciudad
        if not origen:
            await query.edit_message_text("Error al determinar tu ubicación actual.")
            return
        await _iniciar_viaje_directo(update, context, salvaje, origen)
    except Exception as e:
        await query.edit_message_text(f"❌ Error al salir al salvaje: {e}")

# ==================== NAVEGACIÓN ====================
async def ciudad_volver(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await cmd_ciudad(update, context)

async def ciudad_cerrar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("🏙️ Hasta pronto. Vuelve a la ciudad cuando necesites.")

async def _ciudad_rankings_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        import rankings as _rk
        user_id = query.from_user.id
        await query.edit_message_text(
            "🏆 <b>RANKINGS DE AETHELGARD</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Elige un ranking para ver la clasificación:",
            reply_markup=_rk._kb_rankings_principal(),
            parse_mode="HTML"
        )
    except Exception as e:
        await query.edit_message_text(f"❌ Error al cargar los rankings: {e}")

async def _ciudad_umbral_donar_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Abre el menú de donación a la Caldera del Ritual desde el botón de Ciudad."""
    query = update.callback_query
    await query.answer()
    try:
        import umbral_vacio as _uv
        user_id = query.from_user.id
        jug = db_helper.obtener_jugador(user_id)
        if not jug:
            await query.edit_message_text("❌ Primero crea un personaje con /start.")
            return
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        corr  = _uv.get_corrupcion()
        estado = _uv.get_estado()
        texto = (
            f"🕯️ <b>CALDERA DEL RITUAL</b>\n\n"
            f"📊 Corrupción actual: <b>{corr}%</b>\n"
            f"Estado: <b>{estado}</b>\n\n"
            "Donando oro a la Caldera retrasarás la llegada de la Noche del Vacío.\n\n"
            "¿Cuánto oro quieres donar?"
        )
        teclado = [
            [InlineKeyboardButton("🪙 100 oro",   callback_data="umbral_donar_100"),
             InlineKeyboardButton("🪙 500 oro",   callback_data="umbral_donar_500")],
            [InlineKeyboardButton("🪙 1.000 oro", callback_data="umbral_donar_1000"),
             InlineKeyboardButton("🪙 5.000 oro", callback_data="umbral_donar_5000")],
            [InlineKeyboardButton("🪙 10.000 oro",callback_data="umbral_donar_10000")],
            [InlineKeyboardButton("🔙 Volver a Ciudad", callback_data="ciudad_menu_principal")],
        ]
        await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(teclado), parse_mode="HTML")
    except Exception as e:
        await query.edit_message_text(f"❌ Error: {e}")

async def ciudad_mapa_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        import mapa as _mapa_mod
        user_id = query.from_user.id
        jug = db_helper.obtener_jugador(user_id)
        if not jug:
            await query.edit_message_text("❌ Primero crea un personaje con /start.")
            return
        texto = _mapa_mod._construir_texto_mapa(jug)
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        keyboard = [
            [InlineKeyboardButton("🌐 Ver todas las zonas", callback_data="mapa_mundo"),
             InlineKeyboardButton("✈️ Viajar", callback_data="mapa_viajar")],
            [InlineKeyboardButton("🔙 Volver a Ciudad", callback_data="ciudad_menu_principal")],
        ]
        await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    except Exception as e:
        await query.edit_message_text(f"❌ Error al cargar el mapa: {e}")

async def ciudad_guia_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        import guia as _guia_mod
        await query.edit_message_text(
            "📖 *Guía Interactiva de Aethelgard*\n\nElige un tema:",
            reply_markup=_guia_mod._indice_keyboard(),
            parse_mode="Markdown"
        )
    except Exception as e:
        await query.edit_message_text(f"❌ Error al cargar la guía: {e}")

async def ciudad_depositos_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        import depositos as _dep_mod
        user_id = query.from_user.id
        jug = db_helper.obtener_jugador(user_id)
        if not jug:
            await query.edit_message_text("❌ Primero crea un personaje con /start.")
            return
        creditos = jug.get("creditos_vacio", 0)
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        texto = (
            f"✨ *Créditos del Vacío*\n\n"
            f"Tu saldo: *{creditos} créditos*\n\n"
            f"📈 Tasa: *1 USDT = {_dep_mod.TASA} créditos*\n"
            f"📉 Comisión retiro: *20%* (recibes el 80%)\n\n"
            f"¿Qué deseas hacer?"
        )
        keyboard = [
            [InlineKeyboardButton("📤 Depositar USDT",  callback_data="cred_dep_inicio")],
            [InlineKeyboardButton("📥 Retirar USDT",    callback_data="cred_ret_inicio")],
            [InlineKeyboardButton("📋 Mis solicitudes", callback_data="cred_mis_solicitudes")],
            [InlineKeyboardButton("🔙 Volver a Comercio", callback_data="submenu_comercio")],
        ]
        await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    except Exception as e:
        await query.edit_message_text(f"❌ Error al cargar créditos: {e}")

async def _ciudad_nav_cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fallback para ConversationHandlers de ciudad: cancela y redirige al destino."""
    context.user_data.pop("ciudad_conv", None)
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
    return ConversationHandler.END

# ==================== REGISTRO DE HANDLERS ====================
def registrar_handlers(app):
    app.add_handler(CommandHandler("ciudad", cmd_ciudad))
    app.add_handler(CommandHandler("duelo", cmd_duelo))
    # START — ConversationHandler solo para capturar el nombre (texto libre)
    conv_start = ConversationHandler(
        entry_points=[CommandHandler("start", cmd_start)],
        states={
            START_NOMBRE: [MessageHandler(filters.TEXT & ~filters.COMMAND, start_recibir_nombre)],
        },
        fallbacks=[CommandHandler("start", cmd_start)],
        allow_reentry=True,
    )
    # Callbacks perfil e inventario desde el menú de ciudad
    async def ciudad_cb_perfil(upd, ctx):
        q = upd.callback_query
        await q.answer()
        try:
            from perfil import cmd_perfil
            await cmd_perfil(upd, ctx)
        except Exception as e:
            await q.message.reply_text(f"❌ Error al abrir perfil: {e}")

    async def ciudad_cb_inventario(upd, ctx):
        q = upd.callback_query
        await q.answer()
        try:
            from inventario import cmd_inventario
            await cmd_inventario(upd, ctx)
        except Exception as e:
            await q.message.reply_text(f"❌ Error al abrir inventario: {e}")

    app.add_handler(conv_start)
    # Clase y facción: handlers independientes (evitan bugs de CallbackQuery en ConversationHandler)
    app.add_handler(CallbackQueryHandler(start_seleccionar_clase, pattern="^start_clase_"))
    app.add_handler(CallbackQueryHandler(start_seleccionar_faccion, pattern="^start_faccion_"))
    # Menú principal (volver)
    app.add_handler(CallbackQueryHandler(ciudad_menu_principal_cb, pattern="^ciudad_menu_principal$"))
    # === SUBMENÚS ===
    app.add_handler(CallbackQueryHandler(ciudad_submenu_servicios,  pattern="^submenu_servicios$"))
    app.add_handler(CallbackQueryHandler(ciudad_submenu_comercio,   pattern="^submenu_comercio$"))
    app.add_handler(CallbackQueryHandler(ciudad_submenu_combate,    pattern="^submenu_combate$"))
    app.add_handler(CallbackQueryHandler(ciudad_submenu_gremio,     pattern="^submenu_gremio$"))
    app.add_handler(CallbackQueryHandler(ciudad_submenu_mazmorras,  pattern="^submenu_mazmorras$"))
    app.add_handler(CallbackQueryHandler(ciudad_submenu_contenido,  pattern="^submenu_contenido$"))
    app.add_handler(CallbackQueryHandler(_ciudad_rankings_cb,       pattern="^ciudad_rankings$"))
    app.add_handler(CallbackQueryHandler(_ciudad_umbral_donar_cb,   pattern="^ciudad_umbral_donar$"))
    # Membresía y Cofre desde menú ciudad
    async def _ciudad_membresia_cb(upd, ctx):
        q = upd.callback_query
        await q.answer()
        try:
            import membresia as _mb
            await _mb._panel_membresia(upd, ctx, upd.effective_user.id, editar=False)
        except Exception as e:
            await q.message.reply_text(f"❌ Error al abrir membresía: {e}")
    async def _ciudad_cofre_cb(upd, ctx):
        q = upd.callback_query
        await q.answer()
        try:
            import cofre_personal as _cp
            await _cp._panel_cofre(upd, ctx, upd.effective_user.id, editar=False)
        except Exception as e:
            await q.message.reply_text(f"❌ Error al abrir cofre: {e}")
    app.add_handler(CallbackQueryHandler(_ciudad_membresia_cb, pattern="^ciudad_membresia$"))
    app.add_handler(CallbackQueryHandler(_ciudad_cofre_cb,     pattern="^ciudad_cofre$"))
    # ── Submenús nuevos: Diario y Utilidades ────────────────────────────
    app.add_handler(CallbackQueryHandler(ciudad_submenu_diario,     pattern="^submenu_diario$"))
    app.add_handler(CallbackQueryHandler(ciudad_submenu_utilidades, pattern="^submenu_utilidades$"))
    # Acciones del submenú Diario
    app.add_handler(CallbackQueryHandler(_diario_login_cb,          pattern="^diario_login_hoy$"))
    app.add_handler(CallbackQueryHandler(_diario_misiones_cb,       pattern="^diario_misiones_hoy$"))
    app.add_handler(CallbackQueryHandler(_diario_resumen_cb,        pattern="^diario_resumen_sesion$"))
    # Acciones del submenú Utilidades
    app.add_handler(CallbackQueryHandler(_util_cooldowns_cb,        pattern="^util_cooldowns$"))
    app.add_handler(CallbackQueryHandler(_util_zona_jugadores_cb,   pattern="^util_zona_jugadores$"))
    # Chat del gremio desde submenú Gremio
    app.add_handler(CallbackQueryHandler(_gchat_log_desde_ciudad_cb, pattern="^ciudad_gchat_log$"))
    # ────────────────────────────────────────────────────────────────────
    # Submenú gremio
    app.add_handler(CallbackQueryHandler(ciudad_gremio_nivel_cb,         pattern="^ciudad_gremio_nivel$"))
    app.add_handler(CallbackQueryHandler(ciudad_guerra_gremios_info_cb,  pattern="^ciudad_guerra_gremios_info$"))
    # Redirección a tienda
    app.add_handler(CallbackQueryHandler(ciudad_tienda_oro,      pattern="^ciudad_tienda_oro$"))
    app.add_handler(CallbackQueryHandler(ciudad_tienda_eternium, pattern="^ciudad_tienda_eternium$"))
    app.add_handler(CallbackQueryHandler(ciudad_tienda_creditos, pattern="^ciudad_tienda_creditos$"))
    # Subastas, P2P
    app.add_handler(CallbackQueryHandler(ciudad_subastas_cb,     pattern="^ciudad_subastas$"))
    app.add_handler(CallbackQueryHandler(ciudad_p2p_cb,          pattern="^ciudad_p2p$"))
    # Contenido
    app.add_handler(CallbackQueryHandler(ciudad_recoleccion_cb,   pattern="^ciudad_recoleccion$"))
    app.add_handler(CallbackQueryHandler(ciudad_investigacion_cb, pattern="^ciudad_investigacion$"))
    app.add_handler(CallbackQueryHandler(ciudad_viajes_cb,        pattern="^ciudad_viajes$"))
    app.add_handler(CallbackQueryHandler(ciudad_stamina_info_cb,  pattern="^ciudad_stamina_info$"))
    # Mazmorras (desde el submenu filtrado por zona)
    app.add_handler(CallbackQueryHandler(cb_mazmorra_azul,       pattern="^cb_mazmorra_azul$"))
    app.add_handler(CallbackQueryHandler(cb_mazmorra_amarilla,   pattern="^cb_mazmorra_amarilla$"))
    app.add_handler(CallbackQueryHandler(cb_mazmorra_roja,       pattern="^cb_mazmorra_roja$"))
    app.add_handler(CallbackQueryHandler(cb_mazmorra_negra,      pattern="^cb_mazmorra_negra$"))
    _NAV_FALLBACKS_CIUDAD = [
        CommandHandler("cancel",     _ciudad_nav_cancelar),
        CommandHandler("ciudad",     _ciudad_nav_cancelar),
        CommandHandler("perfil",     _ciudad_nav_cancelar),
        CommandHandler("viajar",     _ciudad_nav_cancelar),
        CommandHandler("inventario", _ciudad_nav_cancelar),
        CommandHandler("gremio",     _ciudad_nav_cancelar),
        CommandHandler("start",      _ciudad_nav_cancelar),
        MessageHandler(filters.Regex("^(👤|🏙️?|🎒|✈️?|⚔️?|🏰|⛏️?|🔍|📋|📖)"), _ciudad_nav_cancelar),
    ]
    # Crafteo: conv_craft eliminado (los lambdas silenciaban todos los mensajes).
    # ciudad_craftear_redirect llama directamente a cmd_craftear de crafteo.py.
    app.add_handler(CallbackQueryHandler(ciudad_craftear_redirect, pattern="^ciudad_craftear_redirect$"))
    # Encantamiento
    conv_encantar = ConversationHandler(
        entry_points=[CallbackQueryHandler(ciudad_encantar, pattern="^ciudad_encantar$")],
        states={
            ESP_ENCANTAR_SELECCION: [CallbackQueryHandler(encantar_seleccionar_objeto, pattern="^encantar_obj_")],
            ESP_ENCANTAR_CONFIRMAR: [CallbackQueryHandler(encantar_confirmar, pattern="^encantar_nivel_")],
        },
        fallbacks=_NAV_FALLBACKS_CIUDAD,
        allow_reentry=True,
    )
    # Herrero
    conv_herrero = ConversationHandler(
        entry_points=[CallbackQueryHandler(ciudad_herrero, pattern="^ciudad_herrero$")],
        states={ESP_HERRERO_SELECCION: [CallbackQueryHandler(reparar_objeto, pattern="^reparar_")]},
        fallbacks=_NAV_FALLBACKS_CIUDAD,
        allow_reentry=True,
    )
    # Taberna
    conv_taberna = ConversationHandler(
        entry_points=[CallbackQueryHandler(ciudad_taberna, pattern="^ciudad_taberna$")],
        states={ESP_TABERNA_DESCANSAR: [CallbackQueryHandler(taberna_descansar, pattern="^taberna_descansar$"),
                                        CallbackQueryHandler(taberna_lore, pattern="^taberna_lore$")]},
        fallbacks=_NAV_FALLBACKS_CIUDAD,
        allow_reentry=True,
    )
    # Banco personal
    app.add_handler(CallbackQueryHandler(ciudad_banco, pattern="^ciudad_banco$"))
    app.add_handler(CallbackQueryHandler(banco_depositar, pattern="^banco_depositar$"))
    app.add_handler(CallbackQueryHandler(banco_ejecutar_depositar, pattern="^depositar_"))
    app.add_handler(CallbackQueryHandler(banco_retirar, pattern="^banco_retirar$"))
    app.add_handler(CallbackQueryHandler(banco_ejecutar_retirar, pattern="^retirar_"))
    app.add_handler(CallbackQueryHandler(banco_ver, pattern="^banco_ver$"))
    # Alquiler monturas
    conv_alquiler = ConversationHandler(
        entry_points=[CallbackQueryHandler(ciudad_alquilar, pattern="^ciudad_alquilar$")],
        states={ESP_ALQUILER_CONFIRMAR: [CallbackQueryHandler(alquilar_confirmar, pattern="^alquilar_")]},
        fallbacks=_NAV_FALLBACKS_CIUDAD,
        allow_reentry=True,
    )
    # Navegación
    app.add_handler(CallbackQueryHandler(ciudad_volver, pattern="^ciudad_volver$"))
    app.add_handler(CallbackQueryHandler(ciudad_cerrar, pattern="^ciudad_cerrar$"))
    app.add_handler(CallbackQueryHandler(ciudad_mazmorra, pattern="^ciudad_mazmorra$"))
    app.add_handler(CallbackQueryHandler(ciudad_salir, pattern="^ciudad_salir$"))
    app.add_handler(CallbackQueryHandler(ciudad_duelos, pattern="^ciudad_duelos$"))
    app.add_handler(CallbackQueryHandler(_jefe_btn_handler, pattern="^jefe_(unirse|atacar|info)_btn$"))
    app.add_handler(CallbackQueryHandler(ciudad_mapa_cb,      pattern="^ciudad_mapa$"))
    app.add_handler(CallbackQueryHandler(ciudad_guia_cb,      pattern="^ciudad_guia$"))
    app.add_handler(CallbackQueryHandler(ciudad_cb_perfil,    pattern="^ciudad_perfil$"))
    app.add_handler(CallbackQueryHandler(ciudad_cb_inventario, pattern="^ciudad_inventario$"))
    app.add_handler(CallbackQueryHandler(ciudad_depositos_cb, pattern="^ciudad_depositos$"))
    # Añadir conversaciones
    app.add_handler(conv_encantar)
    app.add_handler(conv_herrero)
    app.add_handler(conv_taberna)
    app.add_handler(conv_alquiler)
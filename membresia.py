#!/usr/bin/env python3
# membresia.py
# Sistema de Membresía + Plantillas de Equipo Rápido.
# Membresías disponibles: plantillas (equipo rápido), completa (todo incluido).
# Plantillas: 5 configuraciones de equipo guardadas, equipar todo de golpe.

import sqlite3
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler

import db_helper

DB_PATH = "aethelgard.db"

RANURAS = ["arma", "armadura", "casco", "botas", "guantes", "accesorio1", "accesorio2"]
RANURA_EMOJI = {
    "arma": "⚔️", "armadura": "🛡️", "casco": "🪖",
    "botas": "👟", "guantes": "🧤", "accesorio1": "💍", "accesorio2": "📿"
}
RANURA_NOMBRES = {
    "arma": "Arma", "armadura": "Armadura", "casco": "Casco",
    "botas": "Botas", "guantes": "Guantes", "accesorio1": "Accesorio 1", "accesorio2": "Accesorio 2"
}

TIPOS_MEMBRESIA = {
    "plantillas": {
        "nombre": "⚡ Plantillas de Equipo Rápido",
        "desc": (
            "Guarda hasta *5 configuraciones completas* de equipo.\n"
            "Con un solo toque equípate entero al instante desde tu inventario o tu cofre.\n\n"
            "_Solo puedes configurar las plantillas en la ciudad de tu facción._\n"
            "_Puedes equiparlas desde cualquier lugar._"
        ),
        "precio_oro_default": 500,
        "precio_eth_default": 20,
        "precio_creditos_default": 100,
        "duracion_dias_default": 30,
    },
    "auto_recoleccion": {
        "nombre": "⛏️ Recolección Automática",
        "desc": (
            "El bot recolecta por ti, sin que tengas que pulsar botones.\n\n"
            "• Elige 1 o varias zonas (Azul, Amarilla, Roja, Negra)\n"
            "• Define cuántas veces recolectar en cada zona\n"
            "• *Sin aparición de monstruos* — solo recursos\n"
            "• Respeta el mismo tiempo de espera (90s por colecta)\n"
            "• Tu stamina se gasta igual que en la recolección manual\n\n"
            "_Ideal para acumular materiales mientras estás ausente._"
        ),
        "precio_oro_default": 600,
        "precio_eth_default": 25,
        "precio_creditos_default": 150,
        "duracion_dias_default": 30,
    },
    "completa": {
        "nombre": "👑 Membresía Completa",
        "desc": (
            "Incluye *todas las membresías* actuales y futuras:\n\n"
            "• ⚡ Plantillas de Equipo Rápido (5 slots)\n"
            "• ⛏️ Recolección Automática (sin monstruos)\n"
            "• 🎁 Acceso a beneficios futuros sin coste extra\n\n"
            "_La opción más económica si quieres todo._"
        ),
        "precio_oro_default": 1200,
        "precio_eth_default": 50,
        "precio_creditos_default": 250,
        "duracion_dias_default": 30,
    },
}

def _esc(s: str) -> str:
    return str(s).replace("_", "\\_").replace("*", "\\*").replace("`", "\\`").replace("[", "\\[")


# ==================== INIT DB ====================
def _init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS membresia_config (
        tipo            TEXT PRIMARY KEY,
        nombre          TEXT,
        precio_oro      INTEGER DEFAULT 500,
        precio_eth      INTEGER DEFAULT 20,
        precio_creditos INTEGER DEFAULT 100,
        duracion_dias   INTEGER DEFAULT 30,
        activo          INTEGER DEFAULT 1
    )''')
    try:
        c.execute('ALTER TABLE membresia_config ADD COLUMN precio_creditos INTEGER DEFAULT 100')
    except Exception:
        pass

    c.execute('''CREATE TABLE IF NOT EXISTS membresia_solicitudes (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id        INTEGER,
        tipos_json     TEXT,
        total_creditos INTEGER,
        ts             TEXT,
        estado         TEXT DEFAULT 'pendiente'
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS membresia_jugador (
        user_id  INTEGER,
        tipo     TEXT,
        fecha_fin TEXT,
        PRIMARY KEY (user_id, tipo)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS plantillas_equipo (
        user_id   INTEGER,
        slot      INTEGER,
        nombre    TEXT DEFAULT 'Plantilla',
        arma      TEXT,
        armadura  TEXT,
        casco     TEXT,
        botas     TEXT,
        guantes   TEXT,
        accesorio1 TEXT,
        accesorio2 TEXT,
        PRIMARY KEY (user_id, slot)
    )''')

    # Insertar configs por defecto si no existen
    for tipo, datos in TIPOS_MEMBRESIA.items():
        c.execute('''INSERT OR IGNORE INTO membresia_config (tipo, nombre, precio_oro, precio_eth, precio_creditos, duracion_dias, activo)
                     VALUES (?, ?, ?, ?, ?, ?, 1)''',
                  (tipo, datos["nombre"], datos["precio_oro_default"],
                   datos["precio_eth_default"], datos.get("precio_creditos_default", 100),
                   datos["duracion_dias_default"]))
        # Actualizar precio_creditos para filas ya existentes que tengan 0
        c.execute('''UPDATE membresia_config SET precio_creditos = ?
                     WHERE tipo = ? AND precio_creditos = 0''',
                  (datos.get("precio_creditos_default", 100), tipo))
    conn.commit()
    conn.close()

_init_db()


# ==================== HELPERS DB ====================
def get_config(tipo: str) -> Optional[Dict]:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT tipo, nombre, precio_oro, precio_eth, precio_creditos, duracion_dias, activo FROM membresia_config WHERE tipo = ?', (tipo,))
    row = c.fetchone()
    conn.close()
    if row:
        return {"tipo": row[0], "nombre": row[1], "precio_oro": row[2],
                "precio_eth": row[3], "precio_creditos": row[4],
                "duracion_dias": row[5], "activo": bool(row[6])}
    return None

def get_todos_configs() -> List[Dict]:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT tipo, nombre, precio_oro, precio_eth, precio_creditos, duracion_dias, activo FROM membresia_config')
    rows = c.fetchall()
    conn.close()
    return [{"tipo": r[0], "nombre": r[1], "precio_oro": r[2], "precio_eth": r[3],
             "precio_creditos": r[4], "duracion_dias": r[5], "activo": bool(r[6])} for r in rows]

def get_membresia_jugador(user_id: int, tipo: str) -> Optional[Dict]:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT fecha_fin FROM membresia_jugador WHERE user_id = ? AND tipo = ?', (user_id, tipo))
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    return {"fecha_fin": row[0]}

def tiene_membresia(user_id: int, tipo: str) -> bool:
    """Retorna True si el jugador tiene membresía activa del tipo dado (o completa)."""
    for t in ([tipo, "completa"] if tipo != "completa" else ["completa"]):
        m = get_membresia_jugador(user_id, t)
        if m:
            try:
                fin = datetime.fromisoformat(m["fecha_fin"])
                if fin > datetime.now():
                    return True
            except Exception:
                pass
    return False

def _dias_restantes(user_id: int, tipo: str) -> int:
    for t in ([tipo, "completa"] if tipo != "completa" else ["completa"]):
        m = get_membresia_jugador(user_id, t)
        if m:
            try:
                fin = datetime.fromisoformat(m["fecha_fin"])
                delta = (fin - datetime.now()).days
                if delta > 0:
                    return delta
            except Exception:
                pass
    return 0

def _otorgar_membresia(user_id: int, tipo: str, dias: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Extender si ya existe
    c.execute('SELECT fecha_fin FROM membresia_jugador WHERE user_id = ? AND tipo = ?', (user_id, tipo))
    row = c.fetchone()
    if row:
        try:
            base = max(datetime.now(), datetime.fromisoformat(row[0]))
        except Exception:
            base = datetime.now()
        nueva_fin = base + timedelta(days=dias)
    else:
        nueva_fin = datetime.now() + timedelta(days=dias)
    c.execute('INSERT OR REPLACE INTO membresia_jugador (user_id, tipo, fecha_fin) VALUES (?, ?, ?)',
              (user_id, tipo, nueva_fin.isoformat()))
    conn.commit()
    conn.close()

def get_suscriptores_activos(tipo: str) -> int:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    ahora = datetime.now().isoformat()
    c.execute('SELECT COUNT(*) FROM membresia_jugador WHERE tipo = ? AND fecha_fin > ?', (tipo, ahora))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0

def update_config(tipo: str, campo: str, valor):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(f'UPDATE membresia_config SET {campo} = ? WHERE tipo = ?', (valor, tipo))
    conn.commit()
    conn.close()


# ==================== PLANTILLAS (EQUIPO RÁPIDO) ====================
def get_plantilla(user_id: int, slot: int) -> Dict:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT nombre, arma, armadura, casco, botas, guantes, accesorio1, accesorio2 '
              'FROM plantillas_equipo WHERE user_id = ? AND slot = ?', (user_id, slot))
    row = c.fetchone()
    conn.close()
    if row:
        return {"nombre": row[0] or f"Plantilla {slot}", "arma": row[1], "armadura": row[2],
                "casco": row[3], "botas": row[4], "guantes": row[5], "accesorio1": row[6], "accesorio2": row[7]}
    return {"nombre": f"Plantilla {slot}", "arma": None, "armadura": None, "casco": None,
            "botas": None, "guantes": None, "accesorio1": None, "accesorio2": None}

def save_plantilla(user_id: int, slot: int, datos: Dict):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT OR REPLACE INTO plantillas_equipo
                 (user_id, slot, nombre, arma, armadura, casco, botas, guantes, accesorio1, accesorio2)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
              (user_id, slot, datos.get("nombre", f"Plantilla {slot}"),
               datos.get("arma"), datos.get("armadura"), datos.get("casco"),
               datos.get("botas"), datos.get("guantes"), datos.get("accesorio1"), datos.get("accesorio2")))
    conn.commit()
    conn.close()

def get_items_equipables(user_id: int) -> List[str]:
    """Devuelve todos los items equipables del inventario + cofre personal."""
    items = []
    inv = db_helper.obtener_inventario(user_id) or []
    for it in inv:
        nombre = it['nombre'].lower()
        if any(x in nombre for x in ["espada", "hacha", "daga", "arco", "baston",
                                       "pechera", "armadura", "casco", "yelmo", "botas",
                                       "guantes", "anillo", "amuleto"]):
            items.append(it['nombre'])
    try:
        import cofre_personal as _cp
        for it in _cp.get_cofre(user_id):
            nombre = it['nombre'].lower()
            if any(x in nombre for x in ["espada", "hacha", "daga", "arco", "baston",
                                           "pechera", "armadura", "casco", "yelmo", "botas",
                                           "guantes", "anillo", "amuleto"]):
                if it['nombre'] not in items:
                    items.append(it['nombre'])
    except Exception:
        pass
    return items

def _ranura_de_item(nombre: str) -> Optional[str]:
    n = nombre.lower()
    if any(x in n for x in ["espada", "hacha", "daga", "arco", "baston"]):
        return "arma"
    if any(x in n for x in ["pechera", "armadura"]):
        return "armadura"
    if any(x in n for x in ["casco", "yelmo"]):
        return "casco"
    if "botas" in n:
        return "botas"
    if "guantes" in n:
        return "guantes"
    if "anillo" in n:
        return "accesorio1"
    if "amuleto" in n:
        return "accesorio2"
    return None


# ==================== PANEL PRINCIPAL MEMBRESÍA ====================
async def cmd_membresia(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        await update.effective_message.reply_text("Primero crea un personaje con /start.")
        return
    await _panel_membresia(update, context, user_id, editar=False)

async def _panel_membresia(update, context, user_id: int, editar: bool = False):
    configs  = get_todos_configs()
    activas  = [c for c in configs if c["activo"]]

    texto  = "🎫 *Membresías de Aethelgard*\n\n"
    texto += (
        "💡 _A continuación puedes ver un sistema de membresías *pasivo*, "
        "el cual no otorga ninguna mejora real a los jugadores. "
        "Solo ofrece opciones de automatización para hacer el juego más cómodo de lo que ya es. "
        "Este sistema opcional ayuda a los devs a recaudar fondos para las futuras actualizaciones del juego._\n\n"
        "━━━━━━━━━━━━━━━━\n\n"
    )

    tiene_alguna = False
    for cfg in activas:
        dias = _dias_restantes(user_id, cfg["tipo"])
        if dias > 0:
            tiene_alguna = True
            texto += f"✅ *{_esc(cfg['nombre'])}*\n   _Activa — {dias} días restantes_\n\n"
        else:
            texto += f"🔒 *{_esc(cfg['nombre'])}*\n   💰 {cfg['precio_oro']:,} oro  |  💎 {cfg['precio_eth']} eternium\n   📅 {cfg['duracion_dias']} días\n\n"

    if not tiene_alguna:
        texto += "_Compra una membresía para desbloquear sus beneficios._\n"

    texto += "\n_Usa_ `/mostrar_membresia` _y_ `/ocultar_membresia` _para controlar este botón._"

    kb = []
    for cfg in activas:
        kb.append([InlineKeyboardButton(
            f"{'✅' if _dias_restantes(user_id, cfg['tipo']) > 0 else '🔒'} {cfg['nombre']}",
            callback_data=f"memb_info_{cfg['tipo']}"
        )])
    # Botón carrito de compra
    kb.append([InlineKeyboardButton("🛒 Comprar membresías (carrito)", callback_data="memb_carrito")])
    # Accesos directos a funciones activas
    if tiene_membresia(user_id, "plantillas"):
        kb.append([InlineKeyboardButton("⚡ Mis Plantillas de Equipo", callback_data="pt_panel")])
    if tiene_membresia(user_id, "auto_recoleccion"):
        kb.append([InlineKeyboardButton("⛏️ Recolección Automática", callback_data="arc_panel")])
    kb.append([InlineKeyboardButton("❌ Cerrar", callback_data="memb_cerrar")])

    markup = InlineKeyboardMarkup(kb)
    if editar and update.callback_query:
        try:
            await update.callback_query.edit_message_text(texto, reply_markup=markup, parse_mode="Markdown")
            return
        except Exception:
            pass
    await update.effective_message.reply_text(texto, reply_markup=markup, parse_mode="Markdown")


async def memb_info_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    tipo = query.data[len("memb_info_"):]
    cfg  = get_config(tipo)
    if not cfg:
        await query.answer("❌ Membresía no encontrada.", show_alert=True)
        return

    datos_estaticos = TIPOS_MEMBRESIA.get(tipo, {})
    dias_r = _dias_restantes(user_id, tipo)
    activa = dias_r > 0
    precio_c = cfg.get("precio_creditos", 0)

    texto  = f"{'✅' if activa else '🔒'} *{_esc(cfg['nombre'])}*\n\n"
    texto += datos_estaticos.get("desc", cfg.get("nombre", "")) + "\n\n"
    if activa:
        texto += f"✅ *Membresía activa* — {dias_r} días restantes\n"
    else:
        texto += f"💫 *Precio:* {precio_c:,} créditos del vacío\n"
        texto += f"📅 *Duración:* {cfg['duracion_dias']} días\n"

    modo = _obtener_modo_aprobacion()
    modo_txt = "🤖 Aprobación automática" if modo == "auto" else "🕐 Revisión manual del admin"
    if not activa:
        texto += f"📋 Modo: _{modo_txt}_\n"

    kb = []
    if activa:
        if tipo in ("plantillas", "completa"):
            kb.append([InlineKeyboardButton("⚡ Ver mis Plantillas", callback_data="pt_panel")])
        kb.append([InlineKeyboardButton("🔄 Renovar (+días)", callback_data=f"memb_pagar_{tipo}_cred")])
    else:
        kb.append([InlineKeyboardButton(
            f"💫 Pagar con Créditos del Vacío", callback_data=f"memb_pagar_{tipo}_cred"
        )])
    kb.append([InlineKeyboardButton("🔙 Volver", callback_data="memb_panel")])
    await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")


async def memb_pagar_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra confirmación de compra individual con créditos del vacío."""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    partes = query.data.split("_")
    # memb_pagar_TIPO_cred
    if len(partes) < 4:
        await query.answer("❌ Error de datos.", show_alert=True)
        return
    tipo = partes[2]
    cfg  = get_config(tipo)
    if not cfg or not cfg["activo"]:
        await query.answer("❌ Membresía no disponible.", show_alert=True)
        return

    precio_c = cfg.get("precio_creditos", 0)
    import economia as _eco
    saldos = _eco.obtener_saldos(user_id)
    saldo_c = saldos.get("creditos_vacio", 0)

    if saldo_c < precio_c:
        await query.answer(
            f"❌ Necesitas {precio_c:,} créditos del vacío. Tienes {saldo_c:,}.",
            show_alert=True
        )
        return

    modo = _obtener_modo_aprobacion()
    modo_txt = "🤖 Aprobación automática" if modo == "auto" else "🕐 Revisión manual del admin"

    await query.edit_message_text(
        f"🔐 *Confirmar solicitud*\n\n"
        f"Membresía: *{_esc(cfg['nombre'])}*\n"
        f"💫 Precio: *{precio_c:,} créditos del vacío*\n"
        f"📅 Duración: *{cfg['duracion_dias']} días*\n\n"
        f"Tu saldo: {saldo_c:,} créditos\n"
        f"📋 Modo: _{modo_txt}_\n\n"
        f"¿Confirmar el pago y enviar la solicitud?",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Confirmar", callback_data=f"memb_conf_{tipo}_cred"),
            InlineKeyboardButton("❌ Cancelar",  callback_data=f"memb_info_{tipo}"),
        ]]),
        parse_mode="Markdown"
    )


async def memb_confirmar_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Procesa el pago individual con créditos y crea la solicitud."""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    partes = query.data.split("_")
    # memb_conf_TIPO_cred
    if len(partes) < 4:
        await query.answer("❌ Error de datos.", show_alert=True)
        return
    tipo = partes[2]
    cfg  = get_config(tipo)
    if not cfg:
        await query.answer("❌ Membresía no encontrada.", show_alert=True)
        return

    precio_c = cfg.get("precio_creditos", 0)
    import economia as _eco
    saldos = _eco.obtener_saldos(user_id)
    if saldos.get("creditos_vacio", 0) < precio_c:
        await query.answer("❌ No tienes suficientes créditos del vacío.", show_alert=True)
        return

    # Descontar créditos
    _eco.modificar_saldo(user_id, "creditos_vacio", -precio_c, f"solicitud membresía {tipo}")

    # Crear solicitud
    sol_id = _crear_solicitud(user_id, [tipo], precio_c)

    modo = _obtener_modo_aprobacion()
    jug  = db_helper.obtener_jugador(user_id)
    nombre_jug = jug.get("nombre_personaje", "Desconocido") if jug else "Desconocido"
    item_txt = f"• {cfg['nombre']} — {cfg['duracion_dias']} días"

    try:
        import os
        admin_id = int(os.environ.get("SUPERADMIN_ID", "0"))
        if admin_id:
            if modo == "auto":
                _otorgar_membresia(user_id, tipo, cfg["duracion_dias"])
                _actualizar_estado_solicitud(sol_id, "aprobada")
                await context.bot.send_message(
                    admin_id,
                    f"🤖 *[AUTO] Membresía otorgada automáticamente*\n\n"
                    f"👤 Jugador: *{_esc(nombre_jug)}* (ID: `{user_id}`)\n"
                    f"🆔 Solicitud: #{sol_id}\n"
                    f"{item_txt}\n"
                    f"💫 Pagó: *{precio_c:,} créditos del vacío*\n\n"
                    f"✅ _Se otorgó automáticamente._",
                    parse_mode="Markdown"
                )
            else:
                kb_admin = [[
                    InlineKeyboardButton("✅ Aprobar", callback_data=f"ma_sol_apr_{sol_id}"),
                    InlineKeyboardButton("❌ Rechazar", callback_data=f"ma_sol_rec_{sol_id}"),
                ]]
                await context.bot.send_message(
                    admin_id,
                    f"📩 *Nueva solicitud de membresía*\n\n"
                    f"👤 Jugador: *{_esc(nombre_jug)}* (ID: `{user_id}`)\n"
                    f"🆔 Solicitud: #{sol_id}\n"
                    f"{item_txt}\n"
                    f"💫 Pagó: *{precio_c:,} créditos del vacío*\n\n"
                    f"¿Qué deseas hacer?",
                    reply_markup=InlineKeyboardMarkup(kb_admin),
                    parse_mode="Markdown"
                )
    except Exception:
        pass

    if modo == "auto":
        texto = (
            f"🎉 *¡Membresía activada!*\n\n"
            f"✅ *{_esc(cfg['nombre'])}*\n"
            f"📅 Válida por *{cfg['duracion_dias']} días*\n\n"
        )
        if tipo in ("plantillas", "completa"):
            texto += "Ahora puedes usar ⚡ *Plantillas de Equipo Rápido* desde tu inventario.\n"
        texto += "\n_¡Disfruta tu membresía!_"
    else:
        texto = (
            f"📩 *Solicitud enviada*\n\n"
            f"✅ *{_esc(cfg['nombre'])}*\n"
            f"💫 Pagaste: *{precio_c:,} créditos del vacío*\n\n"
            f"⏳ _El administrador revisará tu solicitud. Recibirás una notificación cuando sea aprobada o rechazada._"
        )

    kb = []
    if modo == "auto" and tipo in ("plantillas", "completa"):
        kb.append([InlineKeyboardButton("⚡ Ir a mis Plantillas", callback_data="pt_panel")])
    kb.append([InlineKeyboardButton("🔙 Volver al menú", callback_data="memb_panel")])
    await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")


# ==================== PLANTILLAS DE EQUIPO RÁPIDO ====================
async def _panel_plantillas(update, context, user_id: int, editar: bool = True):
    if not tiene_membresia(user_id, "plantillas"):
        texto = (
            "⚡ *Plantillas de Equipo Rápido*\n\n"
            "Esta función requiere la membresía *Plantillas de Equipo Rápido* o la *Membresía Completa*.\n\n"
            "Compra tu membresía desde el menú de Membresías."
        )
        kb = [[InlineKeyboardButton("🎫 Ver Membresías", callback_data="memb_panel")]]
        markup = InlineKeyboardMarkup(kb)
    else:
        from cofre_personal import en_ciudad_propia
        en_cp = en_ciudad_propia(user_id)
        dias  = _dias_restantes(user_id, "plantillas")

        texto  = "⚡ *Plantillas de Equipo Rápido*\n\n"
        texto += f"📅 Membresía activa — {dias} días restantes\n\n"
        texto += "*Tus 5 plantillas:*\n"

        kb = []
        row_eq = []
        for slot in range(1, 6):
            p    = get_plantilla(user_id, slot)
            nom  = p.get("nombre", f"Plantilla {slot}")
            piezas = sum(1 for r in RANURAS if p.get(r))
            badge = f"({piezas}/7)" if piezas > 0 else "(vacía)"
            texto += f"  *{slot}.* {_esc(nom)} {badge}\n"
            row_eq.append(InlineKeyboardButton(f"⚡{slot}", callback_data=f"pt_equipar_{slot}"))
            kb.append([InlineKeyboardButton(f"✏️ Configurar plantilla {slot}", callback_data=f"pt_cfg_{slot}")])

        texto += "\n*Equipar de golpe* → toca el número de la plantilla:\n"
        kb.insert(0, row_eq)

        if en_cp:
            texto += "\n✅ _Estás en tu ciudad — puedes configurar plantillas._\n"
        else:
            texto += "\n⚠️ _Ve a tu ciudad para configurar plantillas._\n"

        kb.append([InlineKeyboardButton("🎫 Mis Membresías", callback_data="memb_panel"),
                   InlineKeyboardButton("❌ Cerrar",         callback_data="pt_cerrar")])
        markup = InlineKeyboardMarkup(kb)

    if editar and update.callback_query:
        try:
            await update.callback_query.edit_message_text(texto, reply_markup=markup, parse_mode="Markdown")
            return
        except Exception:
            pass
    await update.effective_message.reply_text(texto, reply_markup=markup, parse_mode="Markdown")


async def pt_panel_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await _panel_plantillas(update, context, update.effective_user.id, editar=True)


async def pt_equipar_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Equipa todos los items de una plantilla de golpe."""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    if not tiene_membresia(user_id, "plantillas"):
        await query.answer("❌ Necesitas membresía activa.", show_alert=True)
        return

    try:
        slot = int(query.data.split("_")[-1])
    except (ValueError, IndexError):
        await query.answer("❌ Error de datos.", show_alert=True)
        return

    plantilla = get_plantilla(user_id, slot)
    if not any(plantilla.get(r) for r in RANURAS):
        await query.answer(f"⚠️ La plantilla {slot} está vacía. Configúrala primero.", show_alert=True)
        return

    from inventario import equipar, obtener_equipamiento, desequipar
    import cofre_personal as _cp

    equipados   = []
    fallidos    = []
    cofre_movs  = []

    for ranura in RANURAS:
        item_nombre = plantilla.get(ranura)
        if not item_nombre:
            continue

        inv = db_helper.obtener_inventario(user_id)
        en_inv = any(it['nombre'] == item_nombre for it in inv)

        if not en_inv:
            # Intentar mover del cofre al inventario
            cofre = _cp.get_cofre(user_id)
            en_cofre = next((x for x in cofre if x['nombre'] == item_nombre), None)
            if en_cofre and en_cofre.get('cantidad', 0) > 0:
                en_cofre['cantidad'] -= 1
                cofre = [x for x in cofre if x.get('cantidad', 0) > 0]
                _cp.save_cofre(user_id, cofre)
                db_helper.agregar_item(user_id, item_nombre, 1)
                cofre_movs.append(item_nombre)
            else:
                fallidos.append((ranura, item_nombre))
                continue

        ok, msg_eq = equipar(user_id, item_nombre)
        if ok:
            equipados.append(item_nombre)
        else:
            fallidos.append((ranura, item_nombre))

    # Construir mensaje de resultado
    nom_plantilla = plantilla.get("nombre", f"Plantilla {slot}")
    texto = f"⚡ *{_esc(nom_plantilla)}* equipada\n\n"
    if equipados:
        texto += "*Equipado:*\n"
        for e in equipados:
            texto += f"  ✅ {_esc(e)}\n"
    if cofre_movs:
        texto += "\n_Objetos traídos del cofre automáticamente._\n"
    if fallidos:
        texto += "\n*No encontrado:*\n"
        for r, n in fallidos:
            texto += f"  ❌ {_esc(n)} ({RANURA_NOMBRES.get(r, r)})\n"
        texto += "_Añade estos objetos a tu inventario o cofre._\n"

    kb = [[InlineKeyboardButton("🔙 Volver a plantillas", callback_data="pt_panel")]]
    await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")


async def pt_cfg_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Panel de configuración de una plantilla."""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    if not tiene_membresia(user_id, "plantillas"):
        await query.answer("❌ Necesitas membresía activa.", show_alert=True)
        return

    from cofre_personal import en_ciudad_propia
    if not en_ciudad_propia(user_id):
        await query.answer("⚠️ Solo puedes configurar plantillas en tu ciudad.", show_alert=True)
        return

    try:
        slot = int(query.data.split("_")[-1])
    except (ValueError, IndexError):
        await query.answer("❌ Error de datos.", show_alert=True)
        return

    await _panel_cfg_slot(update, context, user_id, slot, editar=True)


async def _panel_cfg_slot(update, context, user_id: int, slot: int, editar: bool = True):
    plantilla = get_plantilla(user_id, slot)
    nom = plantilla.get("nombre", f"Plantilla {slot}")

    texto  = f"✏️ *Configurar: {_esc(nom)}* (slot {slot})\n\n"
    texto += "*Piezas configuradas:*\n"
    for r in RANURAS:
        v = plantilla.get(r)
        texto += f"  {RANURA_EMOJI[r]} {RANURA_NOMBRES[r]}: {_esc(v) if v else '_Vacío_'}\n"
    texto += "\n_Elige qué pieza quieres cambiar:_"

    # Botones 2 por fila para las ranuras
    kb = []
    fila = []
    for i, r in enumerate(RANURAS):
        v   = plantilla.get(r)
        lbl = f"{RANURA_EMOJI[r]} {RANURA_NOMBRES[r]}" + (" ✅" if v else "")
        fila.append(InlineKeyboardButton(lbl, callback_data=f"pt_sel_{slot}_{r}"))
        if len(fila) == 2:
            kb.append(fila)
            fila = []
    if fila:
        kb.append(fila)

    kb.append([InlineKeyboardButton("🔙 Volver a plantillas", callback_data="pt_panel")])
    markup = InlineKeyboardMarkup(kb)

    if editar and update.callback_query:
        try:
            await update.callback_query.edit_message_text(texto, reply_markup=markup, parse_mode="Markdown")
            return
        except Exception:
            pass
    await update.effective_message.reply_text(texto, reply_markup=markup, parse_mode="Markdown")


async def pt_sel_ranura_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Selecciona qué item poner en una ranura de la plantilla."""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    from cofre_personal import en_ciudad_propia
    if not en_ciudad_propia(user_id):
        await query.answer("⚠️ Solo puedes configurar en tu ciudad.", show_alert=True)
        return

    partes = query.data.split("_")
    # pt_sel_SLOT_RANURA
    if len(partes) < 4:
        await query.answer("❌ Error de datos.", show_alert=True)
        return
    try:
        slot   = int(partes[2])
        ranura = partes[3]
    except (ValueError, IndexError):
        await query.answer("❌ Error de datos.", show_alert=True)
        return

    items = get_items_equipables(user_id)
    # Filtrar por la ranura
    compatibles = [n for n in items if _ranura_de_item(n) == ranura]

    if not compatibles:
        await query.answer(f"❌ No tienes items equipables en {RANURA_NOMBRES.get(ranura, ranura)}.\n"
                           f"Los items deben estar en tu inventario o cofre.", show_alert=True)
        return

    texto  = f"⚔️ *{RANURA_NOMBRES.get(ranura, ranura)}* — slot {slot}\n\n"
    texto += "_Elige qué item asignar:_\n\n"
    for n in compatibles[:10]:
        texto += f"  • {_esc(n)}\n"
    if len(compatibles) > 10:
        texto += f"_...y {len(compatibles)-10} más_\n"

    kb = []
    for n in compatibles[:12]:
        kb.append([InlineKeyboardButton(n, callback_data=f"pt_asig_{slot}_{ranura}_{n[:20]}")])
    kb.append([InlineKeyboardButton("🗑️ Vaciar ranura", callback_data=f"pt_asig_{slot}_{ranura}_VACIO")])
    kb.append([InlineKeyboardButton("🔙 Volver", callback_data=f"pt_cfg_{slot}")])

    await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")


async def pt_asignar_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Asigna un item a una ranura de plantilla."""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    from cofre_personal import en_ciudad_propia
    if not en_ciudad_propia(user_id):
        await query.answer("⚠️ Solo puedes configurar en tu ciudad.", show_alert=True)
        return

    partes = query.data.split("_")
    # pt_asig_SLOT_RANURA_NOMBRE (nombre puede tener guiones bajos)
    if len(partes) < 5:
        await query.answer("❌ Error de datos.", show_alert=True)
        return
    try:
        slot   = int(partes[2])
        ranura = partes[3]
        nombre_k = "_".join(partes[4:])
    except (ValueError, IndexError):
        await query.answer("❌ Error de datos.", show_alert=True)
        return

    plantilla = get_plantilla(user_id, slot)

    if nombre_k == "VACIO":
        plantilla[ranura] = None
        save_plantilla(user_id, slot, plantilla)
        await query.answer(f"✅ {RANURA_NOMBRES.get(ranura, ranura)} vaciada.", show_alert=True)
    else:
        # Buscar item real (puede que el nombre esté truncado)
        items = get_items_equipables(user_id)
        nombre_real = next((n for n in items if n[:20] == nombre_k or nombre_k in n), nombre_k)
        plantilla[ranura] = nombre_real
        save_plantilla(user_id, slot, plantilla)
        await query.answer(f"✅ {_esc(nombre_real)} asignado.", show_alert=True)

    await _panel_cfg_slot(update, context, user_id, slot, editar=True)


# ==================== TOGGLE BOTÓN MEMBRESÍA ====================
async def cmd_mostrar_membresia(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    import cofre_personal as _cp
    _cp._set_pref(user_id, "mostrar_membresia", 1)
    await update.effective_message.reply_text(
        "✅ El botón *🎫 Membresía* ya aparece en el menú de la ciudad.\n"
        "Usa `/ocultar_membresia` para quitarlo.",
        parse_mode="Markdown"
    )

async def cmd_ocultar_membresia(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    import cofre_personal as _cp
    _cp._set_pref(user_id, "mostrar_membresia", 0)
    await update.effective_message.reply_text(
        "✅ El botón *🎫 Membresía* ya no aparece en el menú de la ciudad.\n"
        "Usa `/mostrar_membresia` para activarlo de nuevo.",
        parse_mode="Markdown"
    )


# ==================== PANEL ADMIN MEMBRESÍAS ====================
async def cmd_membresia_panel_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    import superadmin as _sa
    if not _sa._es_admin(user_id):
        await update.effective_message.reply_text("❌ Acceso denegado.")
        return
    await _panel_admin_memb(update, context, editar=False)

async def _panel_admin_memb(update, context, editar: bool = False):
    configs = get_todos_configs()
    import cofre_personal as _cp
    cofre_max  = _cp.get_cofre_max()
    modo       = _obtener_modo_aprobacion()
    pendientes = _contar_solicitudes_pendientes()

    modo_lbl = "🤖 AUTOMÁTICO" if modo == "auto" else "🕐 MANUAL"
    texto  = "🎛️ *Gestión de Membresías*\n\n"
    for cfg in configs:
        subs = get_suscriptores_activos(cfg["tipo"])
        est  = "🟢 Activa" if cfg["activo"] else "🔴 Inactiva"
        texto += (
            f"*{_esc(cfg['nombre'])}* [{est}]\n"
            f"  💫 {cfg.get('precio_creditos', 0):,} créditos  |  📅 {cfg['duracion_dias']} días\n"
            f"  👥 Suscriptores activos: {subs}\n\n"
        )
    texto += f"📦 *Cofre personal:* máx {cofre_max} tipos de objetos\n\n"
    texto += f"⚙️ *Modo de aprobación:* {modo_lbl}\n"
    if pendientes > 0:
        texto += f"📩 *Solicitudes pendientes:* {pendientes}\n"

    kb = []
    for cfg in configs:
        kb.append([InlineKeyboardButton(
            f"✏️ Editar: {cfg['nombre']}",
            callback_data=f"ma_tipo_{cfg['tipo']}"
        )])
    modo_btn = "🔄 Cambiar a MANUAL" if modo == "auto" else "🔄 Cambiar a AUTOMÁTICO"
    kb.append([InlineKeyboardButton(modo_btn, callback_data="ma_modo_tog")])
    kb.append([InlineKeyboardButton("📦 Config Cofre Personal", callback_data="ma_cofre_cfg")])
    kb.append([InlineKeyboardButton("❌ Cerrar", callback_data="ma_cerrar")])

    markup = InlineKeyboardMarkup(kb)
    if editar and update.callback_query:
        try:
            await update.callback_query.edit_message_text(texto, reply_markup=markup, parse_mode="Markdown")
            return
        except Exception:
            pass
    await update.effective_message.reply_text(texto, reply_markup=markup, parse_mode="Markdown")


async def ma_tipo_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    try:
        import superadmin as _sa
        if _sa._nivel_admin(user_id) < 1:
            await query.answer("❌ Acceso denegado.", show_alert=True)
            return
    except Exception:
        return

    tipo = query.data[len("ma_tipo_"):]
    cfg  = get_config(tipo)
    if not cfg:
        await query.answer("❌ No encontrado.", show_alert=True)
        return

    subs     = get_suscriptores_activos(tipo)
    est      = "🟢 Activa" if cfg["activo"] else "🔴 Inactiva"
    precio_c = cfg.get("precio_creditos", 0)
    texto = (
        f"✏️ *Editar: {_esc(cfg['nombre'])}*\n\n"
        f"Estado: {est}\n"
        f"💫 Precio créditos: *{precio_c:,}*\n"
        f"📅 Duración: *{cfg['duracion_dias']} días*\n"
        f"👥 Suscriptores activos: *{subs}*\n"
    )
    kb = [
        [InlineKeyboardButton("💫 Créditos +100", callback_data=f"ma_ec_{tipo}_up"),
         InlineKeyboardButton("💫 Créditos -100", callback_data=f"ma_ec_{tipo}_dn")],
        [InlineKeyboardButton("💫 Créditos +500", callback_data=f"ma_ec_{tipo}_up500"),
         InlineKeyboardButton("💫 Créditos -500", callback_data=f"ma_ec_{tipo}_dn500")],
        [InlineKeyboardButton("📅 Días +5",        callback_data=f"ma_ed_{tipo}_up"),
         InlineKeyboardButton("📅 Días -5",         callback_data=f"ma_ed_{tipo}_dn")],
        [InlineKeyboardButton("🟢 Activar" if not cfg["activo"] else "🔴 Desactivar",
                              callback_data=f"ma_toggle_{tipo}")],
        [InlineKeyboardButton("🔙 Volver", callback_data="ma_panel")],
    ]
    await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")


async def _ma_ec_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Editar precio en créditos de una membresía. Patrón: ma_ec_TIPO_dir"""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    try:
        import superadmin as _sa
        if _sa._nivel_admin(user_id) < 1:
            await query.answer("❌ Acceso denegado.", show_alert=True)
            return
    except Exception:
        return

    # Parseo seguro: ma_ec_TIPO_DIR — rsplit desde la derecha
    raw  = query.data[len("ma_ec_"):]          # "auto_recoleccion_up500"
    tipo, direc = raw.rsplit("_", 1)            # ("auto_recoleccion", "up500")
    cfg  = get_config(tipo)
    if not cfg:
        await query.answer("❌ Membresía no encontrada.", show_alert=True)
        return

    paso = 500 if "500" in direc else 100
    actual = cfg.get("precio_creditos", 0)
    nuevo  = actual + (paso if direc.startswith("up") else -paso)
    nuevo  = max(1, nuevo)
    update_config(tipo, "precio_creditos", nuevo)
    await query.answer(f"✅ Precio créditos → {nuevo:,}")
    await ma_tipo_cb(update, context)


async def _ma_ed_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Editar duración en días de una membresía. Patrón: ma_ed_TIPO_dir"""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    try:
        import superadmin as _sa
        if _sa._nivel_admin(user_id) < 1:
            await query.answer("❌ Acceso denegado.", show_alert=True)
            return
    except Exception:
        return

    raw  = query.data[len("ma_ed_"):]
    tipo, direc = raw.rsplit("_", 1)
    cfg  = get_config(tipo)
    if not cfg:
        await query.answer("❌ Membresía no encontrada.", show_alert=True)
        return

    actual = cfg.get("duracion_dias", 30)
    nuevo  = actual + (5 if direc == "up" else -5)
    nuevo  = max(1, nuevo)
    update_config(tipo, "duracion_dias", nuevo)
    await query.answer(f"✅ Duración → {nuevo} días")
    await ma_tipo_cb(update, context)


async def ma_toggle_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    try:
        import superadmin as _sa
        if _sa._nivel_admin(user_id) < 1:
            await query.answer("❌ Acceso denegado.", show_alert=True)
            return
    except Exception:
        return

    tipo = query.data[len("ma_toggle_"):]
    cfg  = get_config(tipo)
    if not cfg:
        await query.answer("❌ No encontrado.", show_alert=True)
        return
    nuevo = 0 if cfg["activo"] else 1
    update_config(tipo, "activo", nuevo)
    await query.answer(f"✅ Membresía {'activada' if nuevo else 'desactivada'}.", show_alert=True)
    await ma_tipo_cb(update, context)


async def ma_cofre_cfg_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    try:
        import superadmin as _sa
        if _sa._nivel_admin(user_id) < 1:
            await query.answer("❌ Acceso denegado.", show_alert=True)
            return
    except Exception:
        return

    import cofre_personal as _cp
    max_i = _cp.get_cofre_max()
    texto = (
        f"📦 *Config Cofre Personal*\n\n"
        f"Máximo de tipos de objeto por jugador: *{max_i}*\n\n"
        f"_Ajusta con los botones:_"
    )
    kb = [
        [InlineKeyboardButton("⬆️ +5",  callback_data="ma_cofre_up"),
         InlineKeyboardButton("⬇️ -5",  callback_data="ma_cofre_dn"),
         InlineKeyboardButton("⬆️ +10", callback_data="ma_cofre_up10"),
         InlineKeyboardButton("⬇️ -10", callback_data="ma_cofre_dn10")],
        [InlineKeyboardButton("🔙 Volver", callback_data="ma_panel")],
    ]
    await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")


async def ma_cofre_adj_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    try:
        import superadmin as _sa
        if _sa._nivel_admin(user_id) < 1:
            await query.answer("❌ Acceso denegado.", show_alert=True)
            return
    except Exception:
        return

    import cofre_personal as _cp
    max_i = _cp.get_cofre_max()
    data  = query.data
    if data == "ma_cofre_up":    nuevo = max_i + 5
    elif data == "ma_cofre_dn":  nuevo = max(5, max_i - 5)
    elif data == "ma_cofre_up10":nuevo = max_i + 10
    else:                        nuevo = max(5, max_i - 10)
    _cp.set_cofre_max(nuevo)
    await query.answer(f"✅ Máximo cofre: {nuevo}")
    await ma_cofre_cfg_cb(update, context)


async def _ma_panel_cb(update, context):
    query = update.callback_query
    await query.answer()
    await _panel_admin_memb(update, context, editar=True)

async def _ma_cerrar_cb(update, context):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("🎛️ Panel de membresías cerrado.")

async def _pt_cerrar_cb(update, context):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("⚡ Plantillas cerradas.")

async def _memb_cerrar_cb(update, context):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("🎫 Membresías cerradas.")


# ==================== ADMIN: dar membresía a jugador ====================
async def cmd_dar_membresia(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        import superadmin as _sa
        if _sa._nivel_admin(user_id) < 1:
            await update.effective_message.reply_text("❌ Acceso denegado.")
            return
    except Exception:
        return
    args = context.args
    if len(args) < 3:
        await update.effective_message.reply_text(
            "Uso: `/dar_membresia <user_id> <tipo> <dias>`\n"
            "Tipos: `plantillas`, `completa`",
            parse_mode="Markdown"
        )
        return
    try:
        target = int(args[0])
        tipo   = args[1]
        dias   = int(args[2])
    except (ValueError, IndexError):
        await update.effective_message.reply_text("❌ Parámetros inválidos.")
        return
    if tipo not in TIPOS_MEMBRESIA:
        await update.effective_message.reply_text(f"❌ Tipo inválido. Usa: {', '.join(TIPOS_MEMBRESIA.keys())}")
        return
    _otorgar_membresia(target, tipo, dias)
    await update.effective_message.reply_text(
        f"✅ Membresía `{tipo}` otorgada al jugador `{target}` por {dias} días.", parse_mode="Markdown"
    )


# ==================== CARRITO DE COMPRA ====================
# Estado del carrito guardado en context.user_data["memb_cart"] = set de tipos

def _cart_get(context) -> set:
    return set(context.user_data.get("memb_cart", []))

def _cart_set(context, cart: set):
    context.user_data["memb_cart"] = list(cart)

def _cart_total(cart: set) -> tuple:
    """Devuelve (total_oro, total_eth) del carrito."""
    configs = get_todos_configs()
    cfg_map = {c["tipo"]: c for c in configs}
    oro = eth = 0
    for tipo in cart:
        cfg = cfg_map.get(tipo)
        if cfg and cfg["activo"]:
            oro += cfg["precio_oro"]
            eth += cfg["precio_eth"]
    return oro, eth


def _cart_total_creditos(cart: set) -> int:
    """Devuelve el total en créditos del vacío del carrito."""
    configs = get_todos_configs()
    cfg_map = {c["tipo"]: c for c in configs}
    total = 0
    for tipo in cart:
        cfg = cfg_map.get(tipo)
        if cfg and cfg["activo"]:
            total += cfg.get("precio_creditos", 0)
    return total


# ==================== MODO APROBACIÓN Y SOLICITUDES ====================

def _obtener_modo_aprobacion() -> str:
    return db_helper.obtener_config("memb_modo_aprobacion", "auto")

def _establecer_modo_aprobacion(modo: str):
    db_helper.establecer_config("memb_modo_aprobacion", modo)

def _crear_solicitud(user_id: int, tipos: list, total_creditos: int) -> int:
    import json, datetime
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        'INSERT INTO membresia_solicitudes (user_id, tipos_json, total_creditos, ts, estado) VALUES (?, ?, ?, ?, ?)',
        (user_id, json.dumps(tipos), total_creditos, datetime.datetime.utcnow().isoformat(), "pendiente")
    )
    sol_id = c.lastrowid
    conn.commit()
    conn.close()
    return sol_id

def _get_solicitud(sol_id: int) -> Optional[Dict]:
    import json
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT id, user_id, tipos_json, total_creditos, ts, estado FROM membresia_solicitudes WHERE id = ?', (sol_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    return {"id": row[0], "user_id": row[1], "tipos": json.loads(row[2]),
            "total_creditos": row[3], "ts": row[4], "estado": row[5]}

def _actualizar_estado_solicitud(sol_id: int, estado: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('UPDATE membresia_solicitudes SET estado = ? WHERE id = ?', (estado, sol_id))
    conn.commit()
    conn.close()

def _contar_solicitudes_pendientes() -> int:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM membresia_solicitudes WHERE estado = 'pendiente'")
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0


async def _panel_carrito(update, context, user_id: int, editar: bool = True):
    configs = [c for c in get_todos_configs() if c["activo"]]
    cart    = _cart_get(context)

    texto  = "🛒 *Tienda de Membresías*\n\n"
    texto += (
        "Añade al carrito las membresías que quieras y paga todo de una sola vez.\n"
        "💫 *El pago es exclusivamente con Créditos del Vacío.*\n"
        "_Si compras la_ *Membresía Completa* _incluye todas las demás._\n\n"
    )
    texto += "━━━━━━━━━━━━━━━━\n\n"

    for cfg in configs:
        en_carrito = cfg["tipo"] in cart
        dias_act   = _dias_restantes(user_id, cfg["tipo"])
        precio_c   = cfg.get("precio_creditos", 0)
        estado     = "✅ *Activa*" if dias_act > 0 else f"💫 {precio_c:,} créditos del vacío"
        texto += f"{'✅' if en_carrito else '🔲'} *{_esc(cfg['nombre'])}*\n"
        texto += f"   {estado}  ·  📅 {cfg['duracion_dias']} días\n\n"

    total_cred = _cart_total_creditos(cart)
    if cart:
        texto += "━━━━━━━━━━━━━━━━\n"
        texto += f"🛒 En el carrito: *{len(cart)}* membresía(s)\n"
        texto += f"💫 Total: *{total_cred:,} créditos del vacío*\n"
    else:
        texto += "_El carrito está vacío. Añade membresías con los botones._"

    kb = []
    for cfg in configs:
        en_carrito = cfg["tipo"] in cart
        ya_activa  = _dias_restantes(user_id, cfg["tipo"]) > 0
        if ya_activa:
            kb.append([InlineKeyboardButton(
                f"✅ {cfg['nombre']} (activa)", callback_data="memb_cnoop"
            )])
        elif en_carrito:
            kb.append([InlineKeyboardButton(
                f"➖ Quitar {cfg['nombre']}", callback_data=f"memb_cart_tog_{cfg['tipo']}"
            )])
        else:
            kb.append([InlineKeyboardButton(
                f"➕ {cfg['nombre']}", callback_data=f"memb_cart_tog_{cfg['tipo']}"
            )])

    if cart:
        jug = db_helper.obtener_jugador(user_id)
        saldo_cred = jug.get("creditos_vacio", 0) if jug else 0
        label_cred = f"💫 Pagar {total_cred:,} créditos" + (" ✓" if saldo_cred >= total_cred else " ✗")
        kb.append([InlineKeyboardButton(label_cred, callback_data="memb_cart_pago_cred")])
        import os as _os
        _superadmin_id = int(_os.environ.get("SUPERADMIN_ID", "0"))
        if user_id == _superadmin_id:
            modo = _obtener_modo_aprobacion()
            modo_txt = "🤖 Auto" if modo == "auto" else "🕐 Revisión manual"
            kb.append([InlineKeyboardButton(f"📋 Modo aprobación: {modo_txt}", callback_data="memb_cnoop")])

    kb.append([InlineKeyboardButton("🔙 Volver", callback_data="memb_panel")])

    markup = InlineKeyboardMarkup(kb)
    if editar and update.callback_query:
        try:
            await update.callback_query.edit_message_text(texto, reply_markup=markup, parse_mode="Markdown")
            return
        except Exception:
            pass
    await update.effective_message.reply_text(texto, reply_markup=markup, parse_mode="Markdown")


async def _cb_carrito(update, context):
    await update.callback_query.answer()
    await _panel_carrito(update, context, update.effective_user.id, editar=True)


async def _cb_cart_noop(update, context):
    await update.callback_query.answer("Esta membresía ya está activa.", show_alert=False)


async def _cb_cart_toggle(update, context):
    query   = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    tipo    = query.data.replace("memb_cart_tog_", "")
    cart    = _cart_get(context)
    if tipo in cart:
        cart.discard(tipo)
    else:
        # Si se añade "completa", limpiar individuales (la completa ya incluye todo)
        if tipo == "completa":
            cart = {tipo}
        else:
            cart.discard("completa")  # no mezclar con completa
            cart.add(tipo)
    _cart_set(context, cart)
    await _panel_carrito(update, context, user_id, editar=True)


async def _cb_cart_pago(update, context):
    """Muestra pantalla de confirmación del carrito (pago en créditos del vacío)."""
    query   = update.callback_query
    user_id = update.effective_user.id
    cart    = _cart_get(context)

    if not cart:
        await query.answer("El carrito está vacío.", show_alert=True)
        return

    configs    = {c["tipo"]: c for c in get_todos_configs()}
    total_cred = _cart_total_creditos(cart)

    jug = db_helper.obtener_jugador(user_id)
    saldo_cred = jug.get("creditos_vacio", 0) if jug else 0

    lineas = []
    for tipo in cart:
        cfg = configs.get(tipo)
        if cfg:
            lineas.append(f"• {cfg['nombre']} — {cfg['duracion_dias']} días — {cfg.get('precio_creditos', 0):,} créditos")
    items_txt = "\n".join(lineas)

    if saldo_cred < total_cred:
        await query.answer(
            f"❌ No tienes suficientes créditos del vacío (necesitas {total_cred:,}, tienes {saldo_cred:,}).",
            show_alert=True
        )
        return

    modo = _obtener_modo_aprobacion()
    modo_txt = "🤖 Aprobación automática — recibirás la membresía al instante" if modo == "auto" \
               else "🕐 Revisión manual — el administrador aprobará tu solicitud"

    texto = (
        f"💳 *Confirmar solicitud de membresía*\n\n"
        f"*En tu carrito:*\n{items_txt}\n\n"
        f"💫 *Total: {total_cred:,} créditos del vacío*\n"
        f"Tu saldo: {saldo_cred:,} créditos\n\n"
        f"📋 _{modo_txt}_\n\n"
        f"¿Confirmar el pago y enviar la solicitud?"
    )
    kb = [[
        InlineKeyboardButton("✅ Confirmar", callback_data="memb_cart_conf_cred"),
        InlineKeyboardButton("❌ Cancelar",  callback_data="memb_carrito"),
    ]]
    await query.answer()
    await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")


async def _cb_cart_conf(update, context):
    """Procesa el pago en créditos y crea la solicitud de membresía."""
    query   = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    cart    = _cart_get(context)

    if not cart:
        await query.answer("El carrito está vacío.", show_alert=True)
        return

    configs    = {c["tipo"]: c for c in get_todos_configs()}
    total_cred = _cart_total_creditos(cart)

    import economia as _eco
    saldos = _eco.obtener_saldos(user_id)
    if saldos["creditos_vacio"] < total_cred:
        await query.answer("❌ Ya no tienes créditos suficientes.", show_alert=True)
        return

    # Descontar créditos del vacío
    _eco.modificar_saldo(user_id, "creditos_vacio", -total_cred, "solicitud membresía")

    # Crear solicitud en DB
    tipos_lista = list(cart)
    sol_id = _crear_solicitud(user_id, tipos_lista, total_cred)

    # Vaciar carrito
    _cart_set(context, set())

    # Preparar texto de ítems
    lineas = []
    for tipo in tipos_lista:
        cfg = configs.get(tipo)
        if cfg:
            lineas.append(f"• {cfg['nombre']} — {cfg['duracion_dias']} días")
    items_txt = "\n".join(lineas)

    # Notificar al admin y actuar según el modo configurado
    modo = _obtener_modo_aprobacion()
    jug  = db_helper.obtener_jugador(user_id)
    nombre_jug = jug.get("nombre_personaje", "Desconocido") if jug else "Desconocido"

    try:
        import os
        admin_id = int(os.environ.get("SUPERADMIN_ID", "0"))
        if admin_id:
            if modo == "auto":
                for tipo in tipos_lista:
                    cfg = configs.get(tipo)
                    if cfg and cfg["activo"]:
                        _otorgar_membresia(user_id, tipo, cfg["duracion_dias"])
                _actualizar_estado_solicitud(sol_id, "aprobada")
                await context.bot.send_message(
                    admin_id,
                    f"🤖 *\\[AUTO\\] Membresía otorgada automáticamente*\n\n"
                    f"👤 Jugador: *{_esc(nombre_jug)}* \\(ID: `{user_id}`\\)\n"
                    f"🆔 Solicitud: \\#{sol_id}\n"
                    f"*Membresías:*\n{items_txt}\n"
                    f"💫 Pagó: *{total_cred:,} créditos del vacío*\n\n"
                    f"✅ _Se otorgó automáticamente\\._",
                    parse_mode="MarkdownV2"
                )
            else:
                kb_admin = [[
                    InlineKeyboardButton("✅ Aprobar", callback_data=f"ma_sol_apr_{sol_id}"),
                    InlineKeyboardButton("❌ Rechazar", callback_data=f"ma_sol_rec_{sol_id}"),
                ]]
                await context.bot.send_message(
                    admin_id,
                    f"📩 *Nueva solicitud de membresía*\n\n"
                    f"👤 Jugador: *{_esc(nombre_jug)}* (ID: `{user_id}`)\n"
                    f"🆔 Solicitud: #{sol_id}\n"
                    f"*Membresías solicitadas:*\n{items_txt}\n"
                    f"💫 Pagó: *{total_cred:,} créditos del vacío*\n\n"
                    f"¿Qué deseas hacer?",
                    reply_markup=InlineKeyboardMarkup(kb_admin),
                    parse_mode="Markdown"
                )
    except Exception:
        pass

    # Confirmar al jugador
    if modo == "auto":
        texto_jug = (
            f"🎉 *¡Membresía activada!*\n\n"
            f"{items_txt}\n\n"
            f"💫 Pagaste: *{total_cred:,} créditos del vacío*\n\n"
            f"_¡Disfruta tus membresías!_"
        )
    else:
        texto_jug = (
            f"📩 *Solicitud enviada correctamente*\n\n"
            f"{items_txt}\n\n"
            f"💫 Pagaste: *{total_cred:,} créditos del vacío*\n\n"
            f"⏳ _El administrador revisará tu solicitud y recibirás una notificación cuando sea aprobada o rechazada._"
        )
    kb = [[InlineKeyboardButton("🔙 Volver a membresías", callback_data="memb_panel")]]
    await query.edit_message_text(texto_jug, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")


# ==================== REGISTRO ====================
def registrar_handlers(app):
    app.add_handler(CommandHandler("membresia",         cmd_membresia))
    app.add_handler(CommandHandler("mostrar_membresia", cmd_mostrar_membresia))
    app.add_handler(CommandHandler("ocultar_membresia", cmd_ocultar_membresia))
    app.add_handler(CommandHandler("membresia_admin",   cmd_membresia_panel_admin))
    app.add_handler(CommandHandler("dar_membresia",     cmd_dar_membresia))

    # Panel membresía jugador
    app.add_handler(CallbackQueryHandler(_panel_membresia_cb, pattern="^memb_panel$"))
    app.add_handler(CallbackQueryHandler(memb_info_cb,        pattern="^memb_info_"))
    app.add_handler(CallbackQueryHandler(memb_pagar_cb,       pattern="^memb_pagar_"))
    app.add_handler(CallbackQueryHandler(memb_confirmar_cb,   pattern="^memb_conf_"))
    app.add_handler(CallbackQueryHandler(_memb_cerrar_cb,     pattern="^memb_cerrar$"))

    # Plantillas
    app.add_handler(CallbackQueryHandler(pt_panel_cb,       pattern="^pt_panel$"))
    app.add_handler(CallbackQueryHandler(pt_equipar_cb,     pattern="^pt_equipar_"))
    app.add_handler(CallbackQueryHandler(pt_cfg_cb,         pattern="^pt_cfg_\\d+$"))
    app.add_handler(CallbackQueryHandler(pt_sel_ranura_cb,  pattern="^pt_sel_"))
    app.add_handler(CallbackQueryHandler(pt_asignar_cb,     pattern="^pt_asig_"))
    app.add_handler(CallbackQueryHandler(_pt_cerrar_cb,     pattern="^pt_cerrar$"))

    # Admin membresías
    app.add_handler(CallbackQueryHandler(_ma_panel_cb,      pattern="^ma_panel$"))
    app.add_handler(CallbackQueryHandler(ma_tipo_cb,        pattern="^ma_tipo_"))
    app.add_handler(CallbackQueryHandler(_ma_ec_cb,         pattern="^ma_ec_"))
    app.add_handler(CallbackQueryHandler(_ma_ed_cb,         pattern="^ma_ed_"))
    app.add_handler(CallbackQueryHandler(ma_toggle_cb,      pattern="^ma_toggle_"))
    app.add_handler(CallbackQueryHandler(ma_cofre_cfg_cb,   pattern="^ma_cofre_cfg$"))
    app.add_handler(CallbackQueryHandler(ma_cofre_adj_cb,   pattern="^ma_cofre_(up|dn|up10|dn10)$"))
    app.add_handler(CallbackQueryHandler(_ma_cerrar_cb,     pattern="^ma_cerrar$"))

    # Carrito de compra
    app.add_handler(CallbackQueryHandler(_cb_carrito,      pattern="^memb_carrito$"))
    app.add_handler(CallbackQueryHandler(_cb_cart_noop,    pattern="^memb_cnoop$"))
    app.add_handler(CallbackQueryHandler(_cb_cart_toggle,  pattern="^memb_cart_tog_"))
    app.add_handler(CallbackQueryHandler(_cb_cart_pago,    pattern="^memb_cart_pago_"))
    app.add_handler(CallbackQueryHandler(_cb_cart_conf,    pattern="^memb_cart_conf_"))

    # Admin: modo aprobación y gestión de solicitudes
    app.add_handler(CallbackQueryHandler(_ma_modo_tog_cb,  pattern="^ma_modo_tog$"))
    app.add_handler(CallbackQueryHandler(_ma_sol_apr_cb,   pattern="^ma_sol_apr_"))
    app.add_handler(CallbackQueryHandler(_ma_sol_rec_cb,   pattern="^ma_sol_rec_"))


async def _ma_modo_tog_cb(update, context):
    """Alterna el modo de aprobación entre automático y manual."""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    import superadmin as _sa
    if _sa._nivel_admin(user_id) < 1:
        await query.answer("❌ Acceso denegado.", show_alert=True)
        return
    modo_actual = _obtener_modo_aprobacion()
    nuevo_modo  = "manual" if modo_actual == "auto" else "auto"
    _establecer_modo_aprobacion(nuevo_modo)
    modo_txt = "Manual — tú apruebas cada solicitud" if nuevo_modo == "manual" \
               else "Automático — se otorga al instante"
    await query.answer(f"✅ Modo cambiado a: {modo_txt}", show_alert=True)
    await _panel_admin_memb(update, context, editar=True)


async def _ma_sol_apr_cb(update, context):
    """Aprueba una solicitud de membresía pendiente."""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    import superadmin as _sa
    if _sa._nivel_admin(user_id) < 1:
        await query.answer("❌ Acceso denegado.", show_alert=True)
        return
    try:
        sol_id = int(query.data.replace("ma_sol_apr_", ""))
    except ValueError:
        await query.answer("❌ ID inválido.", show_alert=True)
        return
    sol = _get_solicitud(sol_id)
    if not sol:
        await query.answer("❌ Solicitud no encontrada.", show_alert=True)
        return
    if sol["estado"] != "pendiente":
        await query.answer(f"⚠️ Esta solicitud ya fue {sol['estado']}.", show_alert=True)
        return

    configs = {c["tipo"]: c for c in get_todos_configs()}
    lineas  = []
    for tipo in sol["tipos"]:
        cfg = configs.get(tipo)
        if cfg and cfg["activo"]:
            _otorgar_membresia(sol["user_id"], tipo, cfg["duracion_dias"])
            lineas.append(f"✅ {cfg['nombre']} — {cfg['duracion_dias']} días")
    _actualizar_estado_solicitud(sol_id, "aprobada")
    items_txt = "\n".join(lineas)

    try:
        await context.bot.send_message(
            sol["user_id"],
            f"🎉 *¡Tu solicitud de membresía fue aprobada!*\n\n"
            f"{items_txt}\n\n"
            f"_¡Disfruta tus beneficios!_",
            parse_mode="Markdown"
        )
    except Exception:
        pass

    jug_info   = db_helper.obtener_jugador(sol["user_id"])
    nombre_jug = jug_info.get("nombre_personaje", "Desconocido") if jug_info else "Desconocido"
    await query.edit_message_text(
        f"✅ *Solicitud \\#{sol_id} APROBADA*\n\n"
        f"👤 Jugador: *{_esc(nombre_jug)}* \\(ID: `{sol['user_id']}`\\)\n"
        f"*Membresías otorgadas:*\n{items_txt}\n\n"
        f"_El jugador fue notificado\\._",
        parse_mode="MarkdownV2"
    )


async def _ma_sol_rec_cb(update, context):
    """Rechaza una solicitud de membresía y reembolsa los créditos."""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    import superadmin as _sa
    if _sa._nivel_admin(user_id) < 1:
        await query.answer("❌ Acceso denegado.", show_alert=True)
        return
    try:
        sol_id = int(query.data.replace("ma_sol_rec_", ""))
    except ValueError:
        await query.answer("❌ ID inválido.", show_alert=True)
        return
    sol = _get_solicitud(sol_id)
    if not sol:
        await query.answer("❌ Solicitud no encontrada.", show_alert=True)
        return
    if sol["estado"] != "pendiente":
        await query.answer(f"⚠️ Esta solicitud ya fue {sol['estado']}.", show_alert=True)
        return

    import economia as _eco
    _eco.modificar_saldo(sol["user_id"], "creditos_vacio", sol["total_creditos"],
                         "reembolso solicitud membresía rechazada")
    _actualizar_estado_solicitud(sol_id, "rechazada")

    configs   = {c["tipo"]: c for c in get_todos_configs()}
    lineas    = [f"• {configs[t]['nombre']}" for t in sol["tipos"] if t in configs]
    items_txt = "\n".join(lineas)

    try:
        await context.bot.send_message(
            sol["user_id"],
            f"❌ *Tu solicitud de membresía fue rechazada*\n\n"
            f"{items_txt}\n\n"
            f"💫 Se te reembolsaron *{sol['total_creditos']:,} créditos del vacío*.\n\n"
            f"_Puedes contactar al administrador si tienes dudas._",
            parse_mode="Markdown"
        )
    except Exception:
        pass

    jug_info   = db_helper.obtener_jugador(sol["user_id"])
    nombre_jug = jug_info.get("nombre_personaje", "Desconocido") if jug_info else "Desconocido"
    await query.edit_message_text(
        f"❌ *Solicitud \\#{sol_id} RECHAZADA*\n\n"
        f"👤 Jugador: *{_esc(nombre_jug)}* \\(ID: `{sol['user_id']}`\\)\n"
        f"*Membresías:*\n{items_txt}\n\n"
        f"💫 Reembolsados: *{sol['total_creditos']:,} créditos al jugador\\.*\n"
        f"_El jugador fue notificado\\._",
        parse_mode="MarkdownV2"
    )


async def _panel_membresia_cb(update, context):
    query = update.callback_query
    await query.answer()
    await _panel_membresia(update, context, update.effective_user.id, editar=True)

#!/usr/bin/env python3
# investigacion_negra.py
# Generado automáticamente por generar_investigacion.py para zona negra

import asyncio
import random
import sqlite3
import os
import importlib.util
from datetime import datetime, timedelta
from html import escape as _he
from typing import Optional, Tuple

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler

import db_helper
import config_balance
from combate import iniciar_combate, COMBATE_PVE_AZUL, COMBATE_PVE_AMARILLA, COMBATE_PVE_ROJA, COMBATE_PVE_NEGRA, COMBATE_PVP_NEGRA

DB_PATH = "aethelgard.db"

CARPETA_POR_COLOR = {
    'azul': 'zonas azules',
    'amarilla': 'zonas amarillas',
    'roja': 'zonas rojas',
    'negra': 'zonas negras',
}

ZONAS_INFO = {
    'Abismo Alianza': {'zona_id': 9, 'nivel': 70, 'color': 'negra'},
    'Costa de los Lamentos Alianza': {'zona_id': 10, 'nivel': 75, 'color': 'negra'},
    'Nexo de la Nada Alianza': {'zona_id': 11, 'nivel': 80, 'color': 'negra'},
    'Abismo Imperio': {'zona_id': 20, 'nivel': 70, 'color': 'negra'},
    'Costa de los Lamentos Imperio': {'zona_id': 21, 'nivel': 75, 'color': 'negra'},
    'Nexo de la Nada Imperio': {'zona_id': 22, 'nivel': 80, 'color': 'negra'},
    'Abismo Sindicato': {'zona_id': 31, 'nivel': 70, 'color': 'negra'},
    'Costa de los Lamentos Sindicato': {'zona_id': 32, 'nivel': 75, 'color': 'negra'},
    'Nexo de la Nada Sindicato': {'zona_id': 33, 'nivel': 80, 'color': 'negra'},
}

STAMINA_MAX = 100
STAMINA_RECARGA_POR_MINUTO = 0.2

def _obtener_stamina(user_id: int) -> Tuple[int, int]:
    try:
        result = db_helper.obtener_stamina(user_id)
        actual = int(result[0] or 0)
        maximo = int(result[1] or 100)
        return actual, maximo
    except Exception:
        return 100, 100

def _gastar_stamina(user_id: int, costo: int) -> bool:
    return db_helper.gastar_stamina(user_id, costo)

def _init_paz_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS estado_paz (
        user_id INTEGER PRIMARY KEY,
        activo BOOLEAN DEFAULT 0,
        fin_inmunidad TIMESTAMP,
        ventana_activa_hasta TIMESTAMP,
        cooldown_hasta TIMESTAMP,
        tipo_ventana TEXT,
        color_actual TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS penalizacion_peleas (
        user_id INTEGER,
        color_zona TEXT,
        peleas_pve INTEGER DEFAULT 0,
        PRIMARY KEY (user_id, color_zona)
    )''')
    conn.commit()
    conn.close()
_init_paz_db()

def _obtener_ventana_paz(user_id: int) -> Optional[Tuple[str, datetime]]:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT tipo_ventana, ventana_activa_hasta FROM estado_paz WHERE user_id = ?', (user_id,))
    row = c.fetchone()
    conn.close()
    if row and row[1]:
        hasta = datetime.fromisoformat(row[1])
        if hasta > datetime.now():
            return row[0], hasta
    return None

def _calcular_duracion_paz_post_combate(user_id: int, color_zona: str) -> int:
    base = 120
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT peleas_pve FROM penalizacion_peleas WHERE user_id = ? AND color_zona = ?', (user_id, color_zona))
    row = c.fetchone()
    peleas = row[0] if row else 0
    conn.close()
    penalizacion = peleas * 15
    return max(15, base - penalizacion)

def _activar_paz(user_id: int, duracion_segundos: int):
    fin = datetime.now() + timedelta(seconds=duracion_segundos)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT OR REPLACE INTO estado_paz (user_id, activo, fin_inmunidad, ventana_activa_hasta, cooldown_hasta)
                 VALUES (?, 1, ?, NULL, NULL)''', (user_id, fin.isoformat()))
    conn.commit()
    conn.close()

def _desactivar_paz(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('UPDATE estado_paz SET activo = 0, fin_inmunidad = NULL WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

def _esta_en_paz(user_id: int) -> bool:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT activo, fin_inmunidad FROM estado_paz WHERE user_id = ?', (user_id,))
    row = c.fetchone()
    conn.close()
    if row and row[0] and row[1]:
        return datetime.fromisoformat(row[1]) > datetime.now()
    return False

def _abrir_ventana_paz(user_id: int, tipo: str, duracion_segundos: int):
    hasta = datetime.now() + timedelta(seconds=duracion_segundos)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT OR REPLACE INTO estado_paz (user_id, ventana_activa_hasta, tipo_ventana)
                 VALUES (?, ?, ?)''', (user_id, hasta.isoformat(), tipo))
    conn.commit()
    conn.close()

async def cmd_investigar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if db_helper.esta_marcado(user_id):
        await update.effective_message.reply_text("❌ Estás marcado. No puedes investigar hasta que pagues rescate con /pagar_rescate.")
        return
    try:
        from guerra_facciones import check_lockdown
        if await check_lockdown(update):
            return
    except Exception:
        pass
    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        await update.effective_message.reply_text("No estás registrado.")
        return
    zona_nombre = jug.get("zona_actual", "")
    if zona_nombre not in ZONAS_INFO:
        # Fallback: buscar por zona_actual_id
        _zid = jug.get("zona_actual_id")
        zona_nombre = next((k for k, v in ZONAS_INFO.items() if v.get("zona_id") == _zid), zona_nombre)
    if zona_nombre not in ZONAS_INFO:
        await update.effective_message.reply_text("❌ No estás en una zona válida para investigar. Viaja a una zona de esta categoría.")
        return
    # Abrir ventana de meditación automáticamente al acceder al menú de investigación
    try:
        import sistema_paz as _sp
        _sp.abrir_ventana_entrada(user_id)
    except Exception:
        pass
    stamina_actual, stamina_max = _obtener_stamina(user_id)
    texto = (
        f"⚫ *Zona Negra — {zona_nombre}* ⚫\n\n"
        f"⚡ Stamina: {stamina_actual}/{stamina_max}\n\n"
        "Selecciona una acción:\n"
        "👣 *Seguir huellas* — Encuentra monstruos\n"
        "⚔️ *Emboscada local* — Ataca jugadores en esta zona (PvP mortal)\n"
        "🌐 *Caza multizonal* — Busca rivales en todas las zonas negras de tu facción\n"
        "🧘‍♂️ *Meditar* — Activa inmunidad PvP temporal\n"
    )
    keyboard = [
        [InlineKeyboardButton("👣 Seguir huellas", callback_data=f"investigar_huellas_negra_{zona_nombre}")],
        [InlineKeyboardButton("⚔️ Emboscada local (PvP)", callback_data="pvpm_local_negra")],
        [InlineKeyboardButton("🌐 Caza multizonal (PvP)", callback_data="pvpm_multi_negra")],
        [InlineKeyboardButton("🧘‍♂️ Meditar", callback_data=f"investigar_meditar_negra_{zona_nombre}")],
        [InlineKeyboardButton("👥 Jugadores en zona", callback_data="investigar_zona_jug")],
        [InlineKeyboardButton("❌ Cerrar", callback_data="investigar_cerrar")]
    ]
    await update.effective_message.reply_text(texto, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def seguir_huellas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    zona_nombre = query.data.replace("investigar_huellas_negra_", "", 1)
    user_id = update.effective_user.id
    if db_helper.esta_marcado(user_id):
        await query.edit_message_text("❌ Estás marcado. No puedes seguir huellas hasta que pagues rescate con /pagar_rescate.")
        return
    # Verificar y gastar stamina (configurable por admin)
    costo_stamina = int(db_helper.obtener_config("stamina_explorar", "5"))
    stamina_antes, stamina_max = _obtener_stamina(user_id)
    stamina_despues = max(0, stamina_antes - costo_stamina)
    if not _gastar_stamina(user_id, costo_stamina):
        await query.edit_message_text(
            f"❌ No tienes suficiente stamina.\n"
            f"⚡ Stamina actual: {stamina_antes}/{stamina_max} | Necesitas: {costo_stamina}\n"
            f"Se regenera automáticamente con el tiempo."
        )
        return
    # Hook logros investigacion
    try:
        import logros as _logros
        _logros.registrar_investigacion(user_id)
    except Exception:
        pass
    # Espera de 90 segundos antes del resultado
    await query.edit_message_text(
        f"🔍 Siguiendo huellas... (90 segundos)\n"
        f"⚡ Stamina: {stamina_antes}/{stamina_max} → {stamina_despues}/{stamina_max} (coste: -{costo_stamina})"
    )
    await asyncio.sleep(90)
    r = random.random()
    if r < 0.30:
        tipo = "normal"
    elif r < 0.95:
        tipo = "mini_boss"
    else:
        mensajes_lore = [
            "Sigues unas huellas que se pierden entre las rocas. No encuentras nada.",
            "Las pisadas te llevan a un claro vacío. Parece que la criatura se esfumó.",
            "Tras un rato siguiendo el rastro, desaparece en un arroyo. No hay nada."
        ]
        lore = random.choice(mensajes_lore)
        await query.edit_message_text(
            f"{lore}\n\n⚡ Stamina restante: {stamina_despues}/{stamina_max}"
        )
        return
    zona_data = ZONAS_INFO.get(zona_nombre)
    if not zona_data:
        await query.edit_message_text("Error: zona no encontrada.")
        return
    zona_id = zona_data['zona_id']
    color = zona_data['color']
    carpeta = CARPETA_POR_COLOR[color]
    if tipo == "normal":
        archivo = os.path.join(carpeta, f"monstruos_normales_zona_{zona_id}.py")
        clave = "MONSTRUOS_NORMALES"
    else:
        archivo = os.path.join(carpeta, f"monstruos_mini_boss_zona_{zona_id}.py")
        clave = "MONSTRUOS_MINI_BOSS"
    if not os.path.exists(archivo):
        # Monstruo inline cuando no existe el archivo
        _jug_d = db_helper.obtener_jugador(user_id)
        _niv = _jug_d.get("nivel", 1) if _jug_d else 1
        if tipo == "mini_boss":
            monstruo_data = {
                'nombre': f"Mini-Jefe de {zona_nombre}",
                'descripcion': f"Un poderoso guardián que domina los rincones más peligrosos de {zona_nombre}.",
                'vida_max': 100 + _niv * 15,
                'daño': 10 + _niv * 3,
                'defensa': 5 + _niv * 2,
                'xp': 30 + _niv * 5,
                'oro': 20 + _niv * 3,
                'drops': []
            }
        else:
            monstruo_data = {
                'nombre': f"Criatura de {zona_nombre}",
                'descripcion': f"Una bestia salvaje que merodea los senderos de {zona_nombre}.",
                'vida_max': 50 + _niv * 8,
                'daño': 5 + _niv * 2,
                'defensa': 2 + _niv,
                'xp': 10 + _niv * 3,
                'oro': 10 + _niv * 2,
                'drops': []
            }
        enemigo = {
            'nombre': monstruo_data['nombre'],
            'descripcion': monstruo_data.get('descripcion', ''),
            'vida_max': monstruo_data['vida_max'],
            'vida_actual': monstruo_data['vida_max'],
            'daño': monstruo_data['daño'],
            'defensa': monstruo_data['defensa'],
            'xp': monstruo_data['xp'],
            'oro': monstruo_data['oro'],
            'drops': []
        }
        tipo_combate_map = {'azul':'pve_zona_azul','amarilla':'pve_zona_amarilla','roja':'pve_zona_roja','negra':'pve_zona_negra'}
        tipo_combate = tipo_combate_map.get(zona_data['color'], 'pve_zona_azul')
        await query.delete_message()
        await iniciar_combate(update, context, user_id, 0, tipo_combate, enemigo=enemigo, datos_extra={})
        return
    spec = importlib.util.spec_from_file_location(f"monstruos_{zona_id}", archivo)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    monstruos_dict = getattr(modulo, clave, {})
    if not monstruos_dict:
        await query.edit_message_text("No hay monstruos disponibles.")
        return
    mon_id = random.choice(list(monstruos_dict.keys()))
    monstruo_data = monstruos_dict[mon_id]
    enemigo = {
        'nombre': monstruo_data['nombre'],
        'descripcion': monstruo_data.get('descripcion', ''),
        'vida_max': monstruo_data['vida_max'],
        'vida_actual': monstruo_data['vida_max'],
        'daño': monstruo_data['daño'],
        'defensa': monstruo_data['defensa'],
        'xp': monstruo_data['xp'],
        'oro': monstruo_data['oro'],
        'drops': monstruo_data.get('drops', [])
    }
    tipo_combate_map = {
        'azul': 'pve_zona_azul',
        'amarilla': 'pve_zona_amarilla',
        'roja': 'pve_zona_roja',
        'negra': 'pve_zona_negra'
    }
    tipo_combate = tipo_combate_map.get(color, 'pve_zona_azul')
    await query.delete_message()
    await iniciar_combate(update, context, user_id, 0, tipo_combate, enemigo=enemigo, datos_extra={})

async def buscar_rivales_pvp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra jugadores en zona negra que pueden ser atacados."""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    if db_helper.esta_marcado(user_id):
        await query.edit_message_text("❌ Estás marcado. No puedes iniciar PvP.")
        return
    import sistema_paz as _sp
    if _sp.esta_en_paz(user_id):
        await query.edit_message_text("🧘 Estás en estado de paz. No puedes atacar a otros jugadores.")
        return
    from datos_zona import ZONAS as _ZONAS
    negra_ids = [z["id"] for z in _ZONAS if z.get("color") == "negra"]
    if not negra_ids:
        await query.edit_message_text("No se encontraron zonas negras.")
        return
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    placeholders = ",".join("?" * len(negra_ids))
    c.execute(
        f"SELECT user_id, nombre_personaje, nivel, faccion FROM jugadores "
        f"WHERE zona_actual_id IN ({placeholders}) AND user_id != ?",
        negra_ids + [user_id]
    )
    rows = c.fetchall()
    conn.close()
    # Filtrar los que están en paz
    rivales = []
    for uid, nombre, nivel, faccion in rows:
        if not _sp.esta_en_paz(uid):
            rivales.append((uid, nombre or "Desconocido", nivel or 1, faccion or "?"))
    if not rivales:
        await query.edit_message_text(
            "⚔️ *Zona Negra — Sin rivales disponibles*\n\n"
            "No hay jugadores atacables en zona negra ahora mismo.\n"
            "• Los que están en paz (🧘) no pueden ser atacados.\n"
            "• Vuelve más tarde o explora para encontrar rivales.",
            parse_mode="Markdown"
        )
        return
    texto = "⚔️ *Rivales en Zona Negra*\n\nElige a quién atacar:\n"
    keyboard = []
    for uid, nombre, nivel, faccion in rivales[:10]:
        keyboard.append([InlineKeyboardButton(
            f"⚔️ {nombre} (Nv.{nivel} — {faccion})",
            callback_data=f"pvp_negra_atacar_{uid}"
        )])
    keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data="pvp_negra_volver")])
    try:
        await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    except Exception:
        await query.message.reply_text(texto, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def atacar_rival_pvp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inicia combate PvP contra el rival seleccionado en zona negra."""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    oponente_id = int(query.data.replace("pvp_negra_atacar_", "", 1))
    if user_id == oponente_id:
        await query.edit_message_text("No puedes atacarte a ti mismo.")
        return
    import sistema_paz as _sp
    if _sp.esta_en_paz(user_id):
        await query.edit_message_text("🧘 Estás en estado de paz. Desactívala con /desactivar_paz para atacar.")
        return
    if _sp.esta_en_paz(oponente_id):
        await query.edit_message_text("🛡️ Ese jugador está meditando. No puedes atacarlo mientras tenga paz activa.")
        return
    oponente = db_helper.obtener_jugador(oponente_id)
    if not oponente:
        await query.edit_message_text("❌ El jugador ya no está disponible.")
        return
    jug = db_helper.obtener_jugador(user_id)
    atacante_nombre = jug.get("nombre_personaje", "Desconocido") if jug else "Desconocido"
    oponente_nombre = oponente.get("nombre_personaje", "Desconocido")
    # Enviar desafío al rival con posibilidad de huir
    keyboard_rival = [[
        InlineKeyboardButton("⚔️ Pelear", callback_data=f"pvp_negra_aceptar_{user_id}_{oponente_id}"),
        InlineKeyboardButton("🏃 Huir (pierde 10% oro)", callback_data=f"pvp_negra_huir_{user_id}_{oponente_id}")
    ]]
    try:
        await context.bot.send_message(
            chat_id=oponente_id,
            text=f"⚔️ <b>¡Emboscada en Zona Negra!</b>\n\n"
                 f"<b>{_he(atacante_nombre)}</b> te está atacando. ¡Tienes 30 segundos para responder!\n\n"
                 f"⚠️ En zona negra el ganador toma todo el oro del perdedor.",
            reply_markup=InlineKeyboardMarkup(keyboard_rival),
            parse_mode="HTML"
        )
    except Exception:
        await query.edit_message_text("❌ No se pudo contactar al rival. Puede estar desconectado.")
        return
    # Guardar datos del combate pendiente
    context.application.user_data.setdefault(user_id, {})["pvp_negra_pendiente"] = {
        "oponente_id": oponente_id,
        "timestamp": datetime.now().isoformat()
    }
    try:
        await query.edit_message_text(
            f"⚔️ Desafío enviado a <b>{_he(oponente_nombre)}</b>.\n"
            f"Esperando respuesta (30 segundos)...",
            parse_mode="HTML"
        )
    except Exception:
        await query.message.reply_text(f"⚔️ Desafío enviado a <b>{_he(oponente_nombre)}</b>.", parse_mode="HTML")
    # Cancelar si no responde en 30s
    await asyncio.sleep(30)
    datos = context.application.user_data.get(user_id, {}).get("pvp_negra_pendiente")
    if datos and datos.get("oponente_id") == oponente_id:
        context.application.user_data[user_id].pop("pvp_negra_pendiente", None)
        try:
            await context.bot.send_message(user_id, f"⏰ {oponente_nombre} no respondió al desafío. El combate se canceló.")
        except Exception:
            pass

async def aceptar_pvp_negra(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """El rival acepta el combate PvP en zona negra."""
    query = update.callback_query
    await query.answer()
    # callback: pvp_negra_aceptar_{atacante_id}_{defensor_id}
    # split("_") → ["pvp","negra","aceptar", atacante_id, defensor_id]
    parts = query.data.split("_")
    try:
        atacante_id = int(parts[3])
        defensor_id = int(parts[4])
    except (ValueError, IndexError):
        await query.answer("❌ Error en los datos del combate.", show_alert=True)
        return
    if update.effective_user.id != defensor_id:
        await query.edit_message_text("Este desafío no es para ti.")
        return
    # Limpiar pendiente
    context.application.user_data.get(atacante_id, {}).pop("pvp_negra_pendiente", None)
    atacante = db_helper.obtener_jugador(atacante_id)
    if not atacante:
        await query.edit_message_text("❌ El atacante ya no está disponible.")
        return
    try:
        await context.bot.send_message(atacante_id, "⚔️ ¡Tu rival aceptó el combate! ¡Que comience la batalla!")
    except Exception:
        pass
    await query.edit_message_text("⚔️ ¡Combate iniciado! Preparando arena...")
    await iniciar_combate(update, context, atacante_id, defensor_id, COMBATE_PVP_NEGRA, enemigo=None, datos_extra={})

async def huir_pvp_negra(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """El rival huye del combate PvP en zona negra (pierde 10% del oro)."""
    query = update.callback_query
    await query.answer()
    # callback: pvp_negra_huir_{atacante_id}_{defensor_id}
    # split("_") → ["pvp","negra","huir", atacante_id, defensor_id]
    parts = query.data.split("_")
    try:
        atacante_id = int(parts[3])
        defensor_id = int(parts[4])
    except (ValueError, IndexError):
        await query.answer("❌ Error en los datos del combate.", show_alert=True)
        return
    if update.effective_user.id != defensor_id:
        await query.edit_message_text("Esta acción no es para ti.")
        return
    context.application.user_data.get(atacante_id, {}).pop("pvp_negra_pendiente", None)
    import economia
    saldos = economia.obtener_saldos(defensor_id)
    penalizacion = max(1, int(saldos.get("oro", 0) * 0.10))
    economia.modificar_saldo(defensor_id, "oro", -penalizacion, "huida de zona negra")
    economia.modificar_saldo(atacante_id, "oro", penalizacion, "recompensa persecucion zona negra")
    defensor = db_helper.obtener_jugador(defensor_id)
    def_nombre = defensor.get("nombre_personaje", "Desconocido") if defensor else "Desconocido"
    try:
        await context.bot.send_message(
            atacante_id,
            f"🏃 *{def_nombre}* huyó del combate.\n"
            f"Recibes *{penalizacion} oro* como recompensa por la persecución.",
            parse_mode="Markdown"
        )
    except Exception:
        pass
    try:
        await query.edit_message_text(
            f"🏃 Has huido. Pierdes *{penalizacion} oro* (10% de tu bolsa).",
            parse_mode="Markdown"
        )
    except Exception:
        await query.message.reply_text(f"🏃 Has huido. Pierdes {penalizacion} oro.")

async def volver_menu_negra(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        await query.edit_message_text("Usa /investigar para volver al menú de investigación.")
    except Exception:
        pass

async def meditar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    zona_nombre = query.data.replace("investigar_meditar_negra_", "", 1)
    user_id = update.effective_user.id
    if db_helper.esta_marcado(user_id):
        try:
            await query.edit_message_text("❌ Estás marcado. No puedes meditar.")
        except Exception:
            await query.message.reply_text("❌ Estás marcado. No puedes meditar.")
        return
    import sistema_paz as _sp
    if _sp.esta_en_paz(user_id):
        fin_paz = ""
        try:
            await query.edit_message_text(
                f"🧘‍♂️ Ya estás en estado de paz.\nUsa /desactivar_paz para cancelarla.")
        except Exception:
            await query.message.reply_text("🧘‍♂️ Ya estás en estado de paz.")
        return
    cd_secs = _sp.obtener_cooldown_zona(user_id)
    if cd_secs:
        try:
            await query.edit_message_text(f"⏳ Cooldown activo: {cd_secs}s antes de poder meditar de nuevo.")
        except Exception:
            await query.message.reply_text(f"⏳ Cooldown activo: {cd_secs}s.")
        return
    ventana = _sp.obtener_ventana_paz(user_id)
    if not ventana:
        # Abrir ventana ahora mismo si estamos en zona salvaje
        _sp.abrir_ventana_entrada(user_id)
        ventana = _sp.obtener_ventana_paz(user_id)
    if not ventana:
        try:
            await query.edit_message_text(
                "🧘 No puedes meditar ahora.\n"
                "Solo puedes hacerlo al llegar a una nueva zona o tras ganar un combate."
            )
        except Exception:
            await query.message.reply_text("🧘 No puedes meditar ahora.")
        return
    tipo_ventana, _ = ventana
    if tipo_ventana == "entrada":
        duracion = 120
    else:
        zona_data2 = ZONAS_INFO.get(zona_nombre, {})
        color = zona_data2.get("color", "negra")
        duracion = _sp.calcular_duracion_post_combate(user_id, color)
    _sp.activar_paz(user_id, duracion)
    mins, segs = divmod(duracion, 60)
    tiempo_txt = f"{mins}m {segs}s" if mins else f"{segs}s"
    try:
        await query.edit_message_text(
            f"🧘‍♂️ *Estado de Paz activado*\n\n"
            f"⏱️ Duración: {tiempo_txt}\n"
            f"No podrás ser atacado por otros jugadores durante este tiempo.\n"
            f"Usa /desactivar_paz para cancelarla antes de tiempo.",
            parse_mode="Markdown"
        )
    except Exception:
        await query.message.reply_text(
            f"🧘‍♂️ Estado de Paz activado durante {tiempo_txt}.\n"
            f"No podrás ser atacado. Usa /desactivar_paz para cancelarla."
        )

async def cmd_desactivar_paz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if _esta_en_paz(user_id):
        _desactivar_paz(user_id)
        await update.effective_message.reply_text("Has abandonado el estado de paz.")
    else:
        await update.effective_message.reply_text("No estás en estado de paz.")

async def meditar_auto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    partes_med = query.data.split("_")
    if len(partes_med) < 3:
        await query.edit_message_text("❌ Error al procesar meditación.")
        return
    tipo = partes_med[2]
    user_id = update.effective_user.id
    if db_helper.esta_marcado(user_id):
        await query.edit_message_text("❌ Estás marcado. No puedes meditar hasta que pagues rescate con /pagar_rescate.")
        return
    import sistema_paz as _sp
    jug = db_helper.obtener_jugador(user_id)
    zona_nombre2 = jug.get("zona_actual", "") if jug else ""
    if tipo == "entrada":
        duracion = 120
    else:
        zona_data3 = ZONAS_INFO.get(zona_nombre2, {})
        color3 = zona_data3.get("color", "azul")
        duracion = _sp.calcular_duracion_post_combate(user_id, color3)
    _sp.activar_paz(user_id, duracion)
    mins, segs = divmod(duracion, 60)
    tiempo_txt = f"{mins}m {segs}s" if mins else f"{segs}s"
    await query.edit_message_text(
        f"🧘‍♂️ *Estado de Paz activado*\n\n⏱️ Duración: {tiempo_txt}\n"
        f"No podrás ser atacado por otros jugadores durante este tiempo.",
        parse_mode="Markdown"
    )

async def buscar_rivales_multi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Caza multizonal: busca rivales PvP en todas las zonas negras de la misma facción."""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    if db_helper.esta_marcado(user_id):
        await query.edit_message_text("❌ Estás marcado. No puedes iniciar PvP.")
        return
    import sistema_paz as _sp
    if _sp.esta_en_paz(user_id):
        await query.edit_message_text("🧘 Estás en estado de paz. No puedes atacar a otros jugadores.")
        return

    # --- Cooldown progresivo (2 min base, +20s por uso) ---
    BASE_CD = 120   # 2 minutos
    INCREMENTO = 20  # +20s por uso
    udata = context.application.user_data.setdefault(user_id, {})
    usos = udata.get("pvp_multi_usos", 0)
    ultimo_uso = udata.get("pvp_multi_ultimo")
    cooldown_actual = BASE_CD + usos * INCREMENTO
    if ultimo_uso:
        transcurrido = (datetime.now() - datetime.fromisoformat(ultimo_uso)).total_seconds()
        restante = int(cooldown_actual - transcurrido)
        if restante > 0:
            mins, segs = divmod(restante, 60)
            tiempo_txt = f"{mins}m {segs}s" if mins else f"{segs}s"
            await query.edit_message_text(
                f"⏳ *Caza multizonal en recarga*\n\n"
                f"Podrás usarla de nuevo en: `{tiempo_txt}`\n"
                f"_(El cooldown aumenta 20s con cada uso)_",
                parse_mode="Markdown"
            )
            return

    # --- Obtener facción del jugador ---
    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        await query.edit_message_text("❌ Error al obtener tus datos.")
        return
    faccion_jugador = jug.get("faccion", "")

    # --- Buscar zonas negras de la misma facción ---
    from datos_zona import ZONAS as _ZONAS
    negra_ids_propias = [
        z["id"] for z in _ZONAS
        if z.get("color") == "negra" and z.get("faccion") == faccion_jugador
    ]
    # Fallback: si no hay campo "faccion" en zona, buscar por faccion_id del jugador
    if not negra_ids_propias:
        faccion_id_jugador = None
        conn2 = sqlite3.connect(DB_PATH)
        c2 = conn2.cursor()
        c2.execute("SELECT faccion_id FROM facciones WHERE nombre = ?", (faccion_jugador,))
        row2 = c2.fetchone()
        conn2.close()
        if row2:
            faccion_id_jugador = row2[0]
        if faccion_id_jugador:
            negra_ids_propias = [
                z["id"] for z in _ZONAS
                if z.get("color") == "negra" and z.get("faccion_id") == faccion_id_jugador
            ]
        # Segundo fallback: todas las zonas negras
        if not negra_ids_propias:
            negra_ids_propias = [z["id"] for z in _ZONAS if z.get("color") == "negra"]

    if not negra_ids_propias:
        await query.edit_message_text("❌ No se encontraron zonas negras de tu facción.")
        return

    # --- Buscar jugadores rivales en esas zonas ---
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    placeholders = ",".join("?" * len(negra_ids_propias))
    c.execute(
        f"SELECT user_id, nombre_personaje, nivel, faccion, zona_actual FROM jugadores "
        f"WHERE zona_actual_id IN ({placeholders}) AND user_id != ?",
        negra_ids_propias + [user_id]
    )
    rows = c.fetchall()
    conn.close()

    rivales = []
    for uid, nombre, nivel, faccion, zona_actual in rows:
        if not _sp.esta_en_paz(uid):
            rivales.append((uid, nombre or "Desconocido", nivel or 1, faccion or "?", zona_actual or "?"))

    if not rivales:
        await query.edit_message_text(
            "🌐 *Caza multizonal — Sin rivales*\n\n"
            "No hay jugadores atacables en las zonas negras de tu facción ahora mismo.\n"
            "• Los que meditan (🧘) no pueden ser atacados.\n"
            "• Inténtalo de nuevo más tarde.",
            parse_mode="Markdown"
        )
        return

    # Registrar uso y actualizar cooldown
    udata["pvp_multi_usos"] = usos + 1
    udata["pvp_multi_ultimo"] = datetime.now().isoformat()
    siguiente_cd = BASE_CD + (usos + 1) * INCREMENTO
    mins_s, segs_s = divmod(siguiente_cd, 60)
    sig_txt = f"{mins_s}m {segs_s}s" if mins_s else f"{segs_s}s"

    texto = (
        f"🌐 *Caza Multizonal — Zona Negra ({faccion_jugador})*\n\n"
        f"Rivales encontrados en {len(negra_ids_propias)} zona(s). Elige a quién atacar:\n"
        f"_(Próximo cooldown: {sig_txt})_\n"
    )
    keyboard = []
    for uid, nombre, nivel, faccion, zona in rivales[:10]:
        keyboard.append([InlineKeyboardButton(
            f"⚔️ {nombre} (Nv.{nivel} — {zona})",
            callback_data=f"pvp_negra_atacar_{uid}"
        )])
    keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data="pvp_negra_volver")])
    try:
        await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    except Exception:
        await query.message.reply_text(texto, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")


async def investigar_cerrar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Investigación cerrada.")

async def investigar_zona_jug(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        import zona_activa as _za
        await _za.cmd_zona_jugadores(update, context)
    except Exception as e:
        await query.edit_message_text(f"❌ Error al obtener jugadores en zona: {e}")

def registrar_handlers(app):
    app.add_handler(CommandHandler("investigar", cmd_investigar))
    app.add_handler(CommandHandler("desactivar_paz", cmd_desactivar_paz))
    app.add_handler(CallbackQueryHandler(seguir_huellas,      pattern="^investigar_huellas_negra_"))
    app.add_handler(CallbackQueryHandler(meditar,             pattern="^investigar_meditar_negra_"))
    app.add_handler(CallbackQueryHandler(meditar_auto,        pattern="^meditar_auto_"))
    app.add_handler(CallbackQueryHandler(investigar_cerrar,   pattern="^investigar_cerrar$"))
    app.add_handler(CallbackQueryHandler(investigar_zona_jug, pattern="^investigar_zona_jug$"))
    app.add_handler(CallbackQueryHandler(buscar_rivales_pvp,   pattern="^pvp_negra_buscar$"))
    app.add_handler(CallbackQueryHandler(atacar_rival_pvp,     pattern="^pvp_negra_atacar_"))
    app.add_handler(CallbackQueryHandler(aceptar_pvp_negra,    pattern="^pvp_negra_aceptar_"))
    app.add_handler(CallbackQueryHandler(huir_pvp_negra,       pattern="^pvp_negra_huir_"))
    app.add_handler(CallbackQueryHandler(volver_menu_negra,    pattern="^pvp_negra_volver$"))

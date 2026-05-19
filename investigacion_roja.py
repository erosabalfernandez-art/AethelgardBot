#!/usr/bin/env python3
# investigacion_roja.py
# Generado automáticamente por generar_investigacion.py para zona roja

import asyncio
import random
import sqlite3
import os
import importlib.util
from datetime import datetime, timedelta
from typing import Optional, Tuple

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler

import db_helper
import config_balance
from combate import iniciar_combate, COMBATE_PVE_AZUL, COMBATE_PVE_AMARILLA, COMBATE_PVE_ROJA, COMBATE_PVE_NEGRA

DB_PATH = "aethelgard.db"

CARPETA_POR_COLOR = {
    'azul': 'zonas azules',
    'amarilla': 'zonas amarillas',
    'roja': 'zonas rojas',
    'negra': 'zonas negras',
}

ZONAS_INFO = {
    'Tierras Magmáticas Alianza': {'zona_id': 6, 'nivel': 45, 'color': 'roja'},
    'Cima del Dragón Alianza': {'zona_id': 7, 'nivel': 50, 'color': 'roja'},
    'Forja Abandonada Alianza': {'zona_id': 8, 'nivel': 55, 'color': 'roja'},
    'Tierras Magmáticas Imperio': {'zona_id': 17, 'nivel': 45, 'color': 'roja'},
    'Cima del Dragón Imperio': {'zona_id': 18, 'nivel': 50, 'color': 'roja'},
    'Forja Abandonada Imperio': {'zona_id': 19, 'nivel': 55, 'color': 'roja'},
    'Tierras Magmáticas Sindicato': {'zona_id': 28, 'nivel': 45, 'color': 'roja'},
    'Cima del Dragón Sindicato': {'zona_id': 29, 'nivel': 50, 'color': 'roja'},
    'Forja Abandonada Sindicato': {'zona_id': 30, 'nivel': 55, 'color': 'roja'},
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
    try:
        import sistema_paz as _sp
        _sp.abrir_ventana_entrada(user_id)
    except Exception:
        pass
    stamina_actual, stamina_max = _obtener_stamina(user_id)
    texto = (
        f"🔍 *Investigación - Zona: {zona_nombre}* 🔍\n\n"
        f"⚡ Stamina: {stamina_actual}/{stamina_max}\n\n"
        "Selecciona una acción:\n"
        "👣 *Seguir huellas* - Encuentra monstruos (30% normal, 65% mini boss, 5% nada)\n"
        "🧘‍♂️ *Meditar* - Entra en estado de paz para evitar ataques PvP\n"
    )
    keyboard = [
        [InlineKeyboardButton("👣 Seguir huellas", callback_data=f"investigar_huellas_roja_{zona_nombre}")],
        [InlineKeyboardButton("🧘‍♂️ Meditar", callback_data=f"investigar_meditar_roja_{zona_nombre}")],
        [InlineKeyboardButton("⚔️ Emboscada local (PvP)", callback_data="pvpm_local_roja")],
        [InlineKeyboardButton("🌐 Caza multizonal (PvP)", callback_data="pvpm_multi_roja")],
        [InlineKeyboardButton("👥 Jugadores en zona", callback_data="investigar_zona_jug")],
        [InlineKeyboardButton("❌ Cerrar", callback_data="investigar_cerrar")]
    ]
    await update.effective_message.reply_text(texto, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def seguir_huellas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    zona_nombre = query.data.replace("investigar_huellas_roja_", "", 1)
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

async def meditar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    zona_nombre = query.data.replace("investigar_meditar_roja_", "", 1)
    user_id = update.effective_user.id
    if db_helper.esta_marcado(user_id):
        await query.edit_message_text("❌ Estás marcado. No puedes meditar.")
        return
    import sistema_paz as _sp
    cd_secs = _sp.obtener_cooldown_zona(user_id)
    if cd_secs:
        await query.edit_message_text(f"⏳ Cooldown entre zonas: {cd_secs}s restantes antes de poder meditar.")
        return
    ventana = _sp.obtener_ventana_paz(user_id)
    if not ventana:
        await query.edit_message_text(
            "🧘 No puedes meditar ahora.\n"
            "Solo puedes hacerlo al llegar a una nueva zona o tras ganar un combate."
        )
        return
    tipo_ventana, _ = ventana
    if tipo_ventana == "entrada":
        duracion = 120
    else:
        zona_data2 = ZONAS_INFO.get(zona_nombre, {})
        color = zona_data2.get("color", "azul")
        duracion = _sp.calcular_duracion_post_combate(user_id, color)
    _sp.activar_paz(user_id, duracion)
    mins, segs = divmod(duracion, 60)
    tiempo_txt = f"{mins}m {segs}s" if mins else f"{segs}s"
    await query.edit_message_text(
        f"🧘‍♂️ *Estado de Paz activado*\n\n"
        f"⏱️ Duración: {tiempo_txt}\n"
        f"No podrás ser atacado por otros jugadores durante este tiempo.\n"
        f"Al entrar a otra zona habrá 15s de cooldown.",
        parse_mode="Markdown"
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
    app.add_handler(CallbackQueryHandler(seguir_huellas, pattern="^investigar_huellas_roja_"))
    app.add_handler(CallbackQueryHandler(meditar, pattern="^investigar_meditar_roja_"))
    app.add_handler(CallbackQueryHandler(meditar_auto, pattern="^meditar_auto_"))
    app.add_handler(CallbackQueryHandler(investigar_cerrar, pattern="^investigar_cerrar$"))
    app.add_handler(CallbackQueryHandler(investigar_zona_jug, pattern="^investigar_zona_jug$"))

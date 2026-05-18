#!/usr/bin/env python3
# mazmorra_azul.py
# Generado automáticamente por generar_mazmorras.py para color azul
# Comando: /mazmorra (acceso grupal)

import random
import sqlite3
import os
import importlib.util
import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler

import db_helper
import economia
import config_balance
from combate import iniciar_combate_grupal_mazmorra, COMBATE_MAZMORRA

DB_PATH = "aethelgard.db"

COLOR = 'azul'
COSTO_ORO = 200
COSTO_STAMINA = 0  # Sin coste de stamina en mazmorras
COSTO_ETERNIUM = 0
LIMITE_POCIONES = 3
CLASES_ROTACION = ['vanguardista', 'acechante', 'tejehechizos', 'maestro_caza']
def _clase_del_dia() -> str:
    dias = (datetime.now().day - 1) % 4
    return CLASES_ROTACION[dias]
def _init_mazmorra_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS mazmorras_activas (
        mazmorra_id TEXT PRIMARY KEY,
        lider_id INTEGER,
        zona_nombre TEXT,
        color TEXT,
        dificultad TEXT,
        sala_actual INTEGER DEFAULT 1,
        monstruos JSON,
        jugadores JSON,
        estado TEXT DEFAULT 'formando',
        fecha_creacion TIMESTAMP
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS espectadores (
        mazmorra_id TEXT,
        espectador_id INTEGER,
        PRIMARY KEY (mazmorra_id, espectador_id)
    )''')
    conn.commit()
    conn.close()
_init_mazmorra_db()

def _puede_entrar(user_id: int) -> Tuple[bool, str]:
    # Verificar límite diario
    if not db_helper.comprobar_limite_mazmorra(user_id, COLOR):
        return False, f"Ya has usado tus {config_balance.MAZMORRAS_LIMITE_DIARIO} entradas diarias para mazmorras {COLOR}. Vuelve mañana."
    if db_helper.esta_marcado(user_id):
        return False, "❌ Estás marcado. No puedes entrar a la mazmorra hasta que pagues rescate con /pagar_rescate."
    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        return False, "No estás registrado."
    clase_jug = jug['clase']
    clase_requerida = _clase_del_dia()
    if clase_jug != clase_requerida:
        return False, f"Hoy solo pueden entrar los {clase_requerida}. Tu clase es {clase_jug}."
    if COSTO_ORO > 0 and jug.get('oro', 0) < COSTO_ORO:
        return False, f"Necesitas {COSTO_ORO} de oro. Tienes {jug.get('oro', 0)}."
    if COSTO_ETERNIUM > 0 and jug.get('eternium', 0) < COSTO_ETERNIUM:
        return False, f"Necesitas {COSTO_ETERNIUM} de eternium. Tienes {jug.get('eternium', 0)}."
    if COSTO_STAMINA > 0 and not db_helper.gastar_stamina(user_id, COSTO_STAMINA):
        return False, f"No tienes suficiente stamina. Necesitas {COSTO_STAMINA}."
    return True, "OK"

def _cobrar_entrada(user_id: int):
    if COSTO_ORO > 0:
        economia.modificar_saldo(user_id, 'oro', -COSTO_ORO, f'Entrada mazmorra {COLOR}')
    if COSTO_ETERNIUM > 0:
        economia.modificar_saldo(user_id, 'eternium', -COSTO_ETERNIUM, f'Entrada mazmorra {COLOR}')
    if COSTO_STAMINA > 0:
        db_helper.gastar_stamina(user_id, COSTO_STAMINA)  # ya se gastó en _puede_entrar, pero se confirma
    db_helper.registrar_entrada_mazmorra(user_id, COLOR)

async def cmd_mazmorra(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if db_helper.esta_marcado(user_id):
        await update.effective_message.reply_text("❌ Estás marcado. No puedes usar /mazmorra hasta que pagues rescate con /pagar_rescate.")
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
    zona_nombre = jug.get('zona_actual', '')
    from datos_zona import ZONAS
    zona_info = next((z for z in ZONAS if z['nombre'] == zona_nombre), None)
    if not zona_info or zona_info['color'] != COLOR:
        await update.effective_message.reply_text(f"No estás en una zona de color {COLOR} adecuada para esta mazmorra.")
        return
    if zona_info['tipo'] != 'ciudad':
        await update.effective_message.reply_text("La mazmorra azul solo se puede acceder desde una ciudad.")
        return
    ok, msg = _puede_entrar(user_id)
    if not ok:
        await update.effective_message.reply_text(f"❌ {msg}")
        return
    keyboard = [
        [InlineKeyboardButton("⚔️ Jugar en solitario", callback_data=f"mazmorra_solo_{COLOR}")],
        [InlineKeyboardButton("👥 Formar grupo", callback_data=f"mazmorra_formar_{COLOR}")],
        [InlineKeyboardButton("🔍 Ver grupos disponibles", callback_data=f"mazmorra_ver_grupos_{COLOR}")],
        [InlineKeyboardButton("👁️ Espectar", callback_data=f"mazmorra_espectar_{COLOR}")]
    ]
    await update.effective_message.reply_text(f"🏰 *Mazmorra {COLOR.capitalize()}*\n\n¿Qué deseas hacer?", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    try:
        import guia_contextual as _gc
        await _gc.enviar(user_id, context, f"mazmorra_inicio_{COLOR}")
    except Exception:
        pass

async def _formar_grupo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    if db_helper.esta_marcado(user_id):
        await query.edit_message_text("❌ Estás marcado. No puedes formar un grupo para la mazmorra hasta que pagues rescate con /pagar_rescate.")
        return
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT mazmorra_id, fecha_creacion FROM mazmorras_activas WHERE lider_id = ? AND estado IN ("formando", "en_curso")', (user_id,))
    row_maz = c.fetchone()
    if row_maz:
        maz_id_stuck, fecha_str = row_maz
        try:
            edad_seg = (datetime.now() - datetime.fromisoformat(fecha_str)).total_seconds()
        except Exception:
            edad_seg = 9999
        if edad_seg > 3600:
            c.execute('DELETE FROM mazmorras_activas WHERE mazmorra_id = ?', (maz_id_stuck,))
            conn.commit()
        else:
            await query.edit_message_text("⚠️ Ya tienes una mazmorra activa. Usa /abandonar_mazmorra para cancelarla.")
            conn.close()
            return
    ok, msg = _puede_entrar(user_id)
    if not ok:
        conn.close()
        await query.edit_message_text(f"No puedes entrar: {msg}")
        return
    _cobrar_entrada(user_id)
    mazmorra_id = f"{COLOR}_{user_id}_{datetime.now().timestamp()}"
    jug = db_helper.obtener_jugador(user_id)
    zona_nombre = jug.get('zona_actual', '')
    c.execute('''INSERT INTO mazmorras_activas (mazmorra_id, lider_id, zona_nombre, color, estado, jugadores, fecha_creacion)
                 VALUES (?, ?, ?, ?, 'formando', ?, ?)''',
                 (mazmorra_id, user_id, zona_nombre, COLOR, json.dumps([user_id]), datetime.now().isoformat()))
    conn.commit()
    conn.close()
    await query.edit_message_text(
        f"Grupo formado.\n📋 ID: <code>{mazmorra_id}</code>\nUsa /unirme_mazmorra <code>{mazmorra_id}</code> para unirte.",
        parse_mode="HTML"
    )

async def _unirse_grupo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Envía el ID de la mazmorra a la que quieres unirte usando `/unirme_mazmorra <id>`")

async def _espectar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Envía el ID de la mazmorra que quieres espectar usando `/espectar <id>`")

async def cmd_unirme_mazmorra(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.effective_message.reply_text("Uso: `/unirme_mazmorra <ID>`")
        return
    mazmorra_id = context.args[0]
    user_id = update.effective_user.id
    if db_helper.esta_marcado(user_id):
        await update.effective_message.reply_text("❌ Estás marcado. No puedes unirte a una mazmorra hasta que pagues rescate con /pagar_rescate.")
        return
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT jugadores, lider_id, estado FROM mazmorras_activas WHERE mazmorra_id = ?', (mazmorra_id,))
    row = c.fetchone()
    if not row:
        await update.effective_message.reply_text("Mazmorra no encontrada.")
        conn.close()
        return
    jugadores = json.loads(row[0])
    lider = row[1]
    estado = row[2]
    if estado != 'formando':
        await update.effective_message.reply_text("La mazmorra ya comenzó o terminó.")
        conn.close()
        return
    if user_id in jugadores:
        await update.effective_message.reply_text("Ya estás en este grupo.")
        conn.close()
        return
    if len(jugadores) >= 5:
        await update.effective_message.reply_text("El grupo está completo (máximo 5).")
        conn.close()
        return
    ok, msg = _puede_entrar(user_id)
    if not ok:
        await update.effective_message.reply_text(f"❌ {msg}")
        conn.close()
        return
    _cobrar_entrada(user_id)
    jugadores.append(user_id)
    c.execute('UPDATE mazmorras_activas SET jugadores = ? WHERE mazmorra_id = ?', (json.dumps(jugadores), mazmorra_id))
    conn.commit()
    conn.close()
    await update.effective_message.reply_text(f"Te has unido a la mazmorra {mazmorra_id}. Espera a que el líder la inicie con /iniciar_mazmorra {mazmorra_id}")

async def cmd_iniciar_mazmorra(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.effective_message.reply_text("Uso: `/iniciar_mazmorra <ID>`")
        return
    mazmorra_id = context.args[0]
    user_id = update.effective_user.id
    if db_helper.esta_marcado(user_id):
        await update.effective_message.reply_text("❌ Estás marcado. No puedes iniciar la mazmorra hasta que pagues rescate con /pagar_rescate.")
        return
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT lider_id, jugadores, zona_nombre, estado FROM mazmorras_activas WHERE mazmorra_id = ?', (mazmorra_id,))
    row = c.fetchone()
    if not row or row[0] != user_id:
        await update.effective_message.reply_text("No eres el líder de esta mazmorra.")
        conn.close()
        return
    if row[3] != 'formando':
        await update.effective_message.reply_text("La mazmorra ya comenzó o terminó.")
        conn.close()
        return
    jugadores = json.loads(row[1])
    zona_nombre = row[2]
    from datos_zona import ZONAS
    zona_info = next((z for z in ZONAS if z['nombre'] == zona_nombre), None)
    if not zona_info:
        await update.effective_message.reply_text("Error: zona no encontrada.")
        conn.close()
        return
    c.execute('UPDATE mazmorras_activas SET estado = "en_curso", sala_actual = 1 WHERE mazmorra_id = ?', (mazmorra_id,))
    conn.commit()
    conn.close()
    import combate as _combate
    maz_dict = {
        "id": mazmorra_id,
        "lider": user_id,
        "dificultad": "normal",
        "miembros": jugadores,
        "sala_actual": 0,
        "salas_totales": 5,
        "fase": "activo",
        "creacion": datetime.now(),
        "combate_id": None,
        "monstruos_sala": []
    }
    _combate.mazmorras_activas[mazmorra_id] = maz_dict
    await update.effective_message.reply_text("¡La mazmorra ha comenzado! Prepárate para la primera sala.")
    await _combate.siguiente_sala_mazmorra(update, context, mazmorra_id)

async def cmd_espectar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.effective_message.reply_text("Uso: `/espectar <ID_mazmorra>`")
        return
    mazmorra_id = context.args[0]
    user_id = update.effective_user.id
    if db_helper.esta_marcado(user_id):
        await update.effective_message.reply_text("❌ Estás marcado. No puedes espectar una mazmorra hasta que pagues rescate con /pagar_rescate.")
        return
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT estado FROM mazmorras_activas WHERE mazmorra_id = ?', (mazmorra_id,))
    row = c.fetchone()
    if not row or row[0] != 'en_curso':
        await update.effective_message.reply_text("No hay ninguna mazmorra activa con ese ID.")
        conn.close()
        return
    c.execute('INSERT OR IGNORE INTO espectadores (mazmorra_id, espectador_id) VALUES (?, ?)', (mazmorra_id, user_id))
    conn.commit()
    conn.close()
    await update.effective_message.reply_text(f"Ahora eres espectador de la mazmorra {mazmorra_id}. Recibirás actualizaciones del combate.")

async def cmd_abandonar_mazmorra(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Buscar si el usuario es líder o miembro de una mazmorra en estado 'formando'
    c.execute('SELECT mazmorra_id, lider_id, jugadores FROM mazmorras_activas WHERE (lider_id = ? OR jugadores LIKE ?) AND estado = "formando"', (user_id, f'%"{user_id}"%'))
    row = c.fetchone()
    if not row:
        await update.effective_message.reply_text("No perteneces a ninguna mazmorra en formación.")
        conn.close()
        return
    mazmorra_id, lider_id, jugadores_json = row
    jugadores = json.loads(jugadores_json)
    if lider_id == user_id:
        # El líder abandona: eliminar la mazmorra
        c.execute('DELETE FROM mazmorras_activas WHERE mazmorra_id = ?', (mazmorra_id,))
        await update.effective_message.reply_text("Has cancelado la mazmorra. El grupo se disuelve.")
    else:
        # Un miembro abandona
        jugadores.remove(user_id)
        if jugadores:
            c.execute('UPDATE mazmorras_activas SET jugadores = ? WHERE mazmorra_id = ?', (json.dumps(jugadores), mazmorra_id))
            await update.effective_message.reply_text("Has abandonado la mazmorra.")
        else:
            c.execute('DELETE FROM mazmorras_activas WHERE mazmorra_id = ?', (mazmorra_id,))
            await update.effective_message.reply_text("Has abandonado la mazmorra. Al no quedar miembros, se cancela.")
    conn.commit()
    conn.close()


async def _jugar_solo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    if db_helper.esta_marcado(user_id):
        await query.edit_message_text("Estas marcado. No puedes entrar a la mazmorra hasta que pagues rescate con /pagar_rescate.")
        return
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT mazmorra_id, fecha_creacion FROM mazmorras_activas WHERE lider_id = ? AND estado IN ("formando", "en_curso")', (user_id,))
    row_maz = c.fetchone()
    if row_maz:
        maz_id_stuck, fecha_str = row_maz
        try:
            edad_seg = (datetime.now() - datetime.fromisoformat(fecha_str)).total_seconds()
        except Exception:
            edad_seg = 9999
        if edad_seg > 3600:
            c.execute('DELETE FROM mazmorras_activas WHERE mazmorra_id = ?', (maz_id_stuck,))
            conn.commit()
        else:
            conn.close()
            await query.edit_message_text("⚠️ Ya tienes una mazmorra activa. Usa /abandonar_mazmorra para cancelarla.")
            return
    ok, msg = _puede_entrar(user_id)
    if not ok:
        conn.close()
        await query.edit_message_text(f"No puedes entrar: {msg}")
        return
    _cobrar_entrada(user_id)
    mazmorra_id = f"{COLOR}_{user_id}_{datetime.now().timestamp()}"
    jug = db_helper.obtener_jugador(user_id)
    zona_nombre = jug.get('zona_actual', '')
    c.execute("""INSERT INTO mazmorras_activas (mazmorra_id, lider_id, zona_nombre, color, estado, jugadores, fecha_creacion)
                 VALUES (?, ?, ?, ?, 'en_curso', ?, ?)""",
                 (mazmorra_id, user_id, zona_nombre, COLOR, __import__('json').dumps([user_id]), datetime.now().isoformat()))
    conn.commit()
    conn.close()
    await query.edit_message_text(f"Entrando en solitario a la Mazmorra {COLOR.capitalize()}. Preparate...")
    import combate as _combate
    maz_dict = {
        "id": mazmorra_id,
        "lider": user_id,
        "dificultad": "normal",
        "miembros": [user_id],
        "sala_actual": 0,
        "salas_totales": 5,
        "fase": "activo",
        "creacion": datetime.now(),
        "combate_id": None,
        "monstruos_sala": []
    }
    _combate.mazmorras_activas[mazmorra_id] = maz_dict
    await _combate.siguiente_sala_mazmorra(update, context, mazmorra_id)

async def _ver_grupos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT mazmorra_id, lider_id, jugadores FROM mazmorras_activas WHERE color = ? AND estado = 'formando'", (COLOR,))
    rows = c.fetchall()
    conn.close()
    if not rows:
        await query.edit_message_text(
            f"No hay grupos abiertos en la Mazmorra {COLOR.capitalize()} ahora mismo.\n"
            "Puedes crear uno con el boton Formar grupo.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Volver", callback_data=f"mazmorra_menu_{COLOR}")]])
        )
        return
    keyboard = []
    texto = f"Grupos disponibles en Mazmorra {COLOR.capitalize()}:\n\n"
    for mazmorra_id, lider_id, jugadores_json in rows:
        jugadores = __import__('json').loads(jugadores_json)
        lider_jug = db_helper.obtener_jugador(lider_id)
        lider_nombre = lider_jug.get('nombre_personaje', str(lider_id)) if lider_jug else str(lider_id)
        texto += f"Lider: {lider_nombre} ({len(jugadores)}/5 jugadores)\n"
        keyboard.append([InlineKeyboardButton(
            f"Unirse al grupo de {lider_nombre} ({len(jugadores)}/5)",
            callback_data=f"mazmorra_unir_d_{mazmorra_id}"
        )])
    keyboard.append([InlineKeyboardButton("Actualizar lista", callback_data=f"mazmorra_ver_grupos_{COLOR}")])
    await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(keyboard))

async def _unir_directo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    data = query.data
    mazmorra_id = data[len("mazmorra_unir_d_"):]
    if db_helper.esta_marcado(user_id):
        await query.edit_message_text("Estas marcado. Paga rescate con /pagar_rescate.")
        return
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT jugadores, lider_id, estado FROM mazmorras_activas WHERE mazmorra_id = ?', (mazmorra_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        await query.edit_message_text("Mazmorra no encontrada. Puede que se haya cancelado.")
        return
    jugadores = __import__('json').loads(row[0])
    estado = row[2]
    if estado != 'formando':
        conn.close()
        await query.edit_message_text("La mazmorra ya comenzo o termino.")
        return
    if user_id in jugadores:
        conn.close()
        await query.edit_message_text("Ya estas en este grupo.")
        return
    if len(jugadores) >= 5:
        conn.close()
        await query.edit_message_text("El grupo esta completo (maximo 5 jugadores).")
        return
    ok, msg = _puede_entrar(user_id)
    if not ok:
        conn.close()
        await query.edit_message_text(f"No puedes unirte: {msg}")
        return
    _cobrar_entrada(user_id)
    jugadores.append(user_id)
    c.execute('UPDATE mazmorras_activas SET jugadores = ? WHERE mazmorra_id = ?', (__import__('json').dumps(jugadores), mazmorra_id))
    conn.commit()
    conn.close()
    await query.edit_message_text(
        f"Te has unido al grupo de la Mazmorra {COLOR.capitalize()}.\n"
        f"Jugadores: {len(jugadores)}/5\n"
        f"Espera a que el lider la inicie con /iniciar_mazmorra {mazmorra_id}"
    )

def registrar_handlers(app):
    app.add_handler(CommandHandler("mazmorra", cmd_mazmorra))
    app.add_handler(CommandHandler("unirme_mazmorra", cmd_unirme_mazmorra))
    app.add_handler(CommandHandler("iniciar_mazmorra", cmd_iniciar_mazmorra))
    app.add_handler(CommandHandler("espectar", cmd_espectar))
    app.add_handler(CommandHandler("abandonar_mazmorra", cmd_abandonar_mazmorra))
    app.add_handler(CallbackQueryHandler(_jugar_solo, pattern=f"^mazmorra_solo_{COLOR}$"))
    app.add_handler(CallbackQueryHandler(_formar_grupo, pattern="^mazmorra_formar_"))
    app.add_handler(CallbackQueryHandler(_ver_grupos, pattern=f"^mazmorra_ver_grupos_{COLOR}$"))
    app.add_handler(CallbackQueryHandler(_unir_directo, pattern="^mazmorra_unir_d_"))
    app.add_handler(CallbackQueryHandler(_unirse_grupo, pattern="^mazmorra_unirse_"))
    app.add_handler(CallbackQueryHandler(_espectar, pattern="^mazmorra_espectar_"))

#!/usr/bin/env python3
# jefes.py — Sistema de Combate contra Jefes (Raid Bosses)
#
# Flujo:
#   Admin activa con /jefe_iniciar <nombre> [hp] [dificultad]
#   Jugadores se unen con /jefe_unirse (hasta 30 min o inicio manual)
#   Admin inicia el combate con /jefe_comenzar
#   Jugadores atacan con /jefe_atacar (cooldown 30s)
#   40% victoria / 60% huida (sin muertes permanentes, solo HP reducido)
#   Admin entrega recompensas con /jefe_recompensa <user_id> <objeto> [cantidad]

import sqlite3
import random
import json
import re
from datetime import datetime, timedelta
from typing import Optional, Dict, List

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler

import db_helper
import economia
import superadmin as sa

DB_PATH = "aethelgard.db"

# ==================== TABLAS ====================
def _init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS jefes_activos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL,
        hp_max INTEGER NOT NULL,
        hp_actual INTEGER NOT NULL,
        dificultad TEXT DEFAULT 'Normal',
        estado TEXT DEFAULT 'reclutando',
        iniciado_por INTEGER,
        fecha_inicio TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        chat_id INTEGER
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS jefes_participantes (
        jefe_id INTEGER,
        user_id INTEGER,
        dano_total INTEGER DEFAULT 0,
        intentos INTEGER DEFAULT 0,
        vivo BOOLEAN DEFAULT 1,
        PRIMARY KEY (jefe_id, user_id)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS jefes_cooldown (
        user_id INTEGER,
        jefe_id INTEGER,
        ultimo_ataque TIMESTAMP,
        PRIMARY KEY (user_id, jefe_id)
    )''')
    conn.commit()
    conn.close()

_init_db()

# ==================== CONSTANTES ====================
DIFICULTADES = {
    "Facil":   {"multiplicador_hp": 0.5, "dano_base": (50, 150),  "prob_victoria": 0.55, "xp_base": 200,  "oro_base": 500},
    "Normal":  {"multiplicador_hp": 1.0, "dano_base": (100, 300), "prob_victoria": 0.40, "xp_base": 500,  "oro_base": 1500},
    "Dificil": {"multiplicador_hp": 2.0, "dano_base": (200, 600), "prob_victoria": 0.30, "xp_base": 1000, "oro_base": 4000},
    "Legendario": {"multiplicador_hp": 4.0, "dano_base": (400, 1200), "prob_victoria": 0.20, "xp_base": 3000, "oro_base": 10000},
}
COOLDOWN_ATAQUE = 30  # segundos

def _esc(texto: str) -> str:
    """Escapa caracteres especiales de Markdown v1 en texto de usuario."""
    return re.sub(r'([*_`\[\]])', r'\\\1', str(texto))

# ==================== HELPERS ====================
def _obtener_jefe_activo(chat_id: int) -> Optional[Dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    # 1) Buscar en el chat exacto
    c.execute("SELECT * FROM jefes_activos WHERE chat_id = ? AND estado != 'terminado' ORDER BY id DESC LIMIT 1", (chat_id,))
    row = c.fetchone()
    # 2) Si no hay, buscar jefe global automático (chat_id=0)
    if not row:
        c.execute("SELECT * FROM jefes_activos WHERE chat_id = 0 AND estado != 'terminado' ORDER BY id DESC LIMIT 1")
        row = c.fetchone()
    # 3) Si tampoco, buscar CUALQUIER jefe activo (jugadores desde chat privado)
    if not row:
        c.execute("SELECT * FROM jefes_activos WHERE estado != 'terminado' ORDER BY id DESC LIMIT 1")
        row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def _obtener_participantes(jefe_id: int) -> List[Dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM jefes_participantes WHERE jefe_id = ? ORDER BY dano_total DESC", (jefe_id,))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def _segundos_cooldown(user_id: int, jefe_id: int) -> int:
    """Retorna segundos restantes de cooldown (0 si puede atacar)."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT ultimo_ataque FROM jefes_cooldown WHERE user_id = ? AND jefe_id = ?", (user_id, jefe_id))
    row = c.fetchone()
    conn.close()
    if not row:
        return 0
    ultimo = datetime.fromisoformat(row[0])
    transcurrido = (datetime.now() - ultimo).total_seconds()
    restante = int(COOLDOWN_ATAQUE - transcurrido)
    return max(0, restante)

def _actualizar_cooldown(user_id: int, jefe_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO jefes_cooldown (user_id, jefe_id, ultimo_ataque) VALUES (?, ?, ?)",
              (user_id, jefe_id, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def _calcular_dano_jugador(user_id: int, dificultad: str) -> int:
    """Calcula el daño que hace el jugador según sus stats."""
    jug = db_helper.obtener_jugador(user_id)
    cfg = DIFICULTADES.get(dificultad, DIFICULTADES["Normal"])
    dano_min, dano_max = cfg["dano_base"]
    if jug:
        nivel = jug.get("nivel", 1)
        multiplicador = 1 + (nivel * 0.05)
        dano_min = int(dano_min * multiplicador)
        dano_max = int(dano_max * multiplicador)
    return random.randint(dano_min, dano_max)

def _barra_hp(hp_actual: int, hp_max: int, largo: int = 20) -> str:
    """Genera una barra de HP visual."""
    porcentaje = max(0, hp_actual / hp_max)
    llenos = int(porcentaje * largo)
    vacios = largo - llenos
    if porcentaje > 0.5:
        emoji = "🟩"
    elif porcentaje > 0.25:
        emoji = "🟨"
    else:
        emoji = "🟥"
    return emoji * llenos + "⬛" * vacios + f" {hp_actual}/{hp_max}"

# ==================== COMANDOS ADMIN ====================

async def _broadcast_jefe(context, nombre: str, dificultad: str, hp_max: int, jefe_id: int):
    """Envía la notificación del jefe a TODOS los jugadores registrados."""
    todos = db_helper.obtener_todos_jugadores()
    teclado = InlineKeyboardMarkup([[
        InlineKeyboardButton("⚔️ ¡Unirme a la batalla!", callback_data=f"jefe_unirse_{jefe_id}")
    ]])
    texto = (
        f"🐉 *¡ALERTA DE JEFE: {nombre.upper()}!*\n\n"
        f"💀 Dificultad: {dificultad}\n"
        f"❤️ HP: {_barra_hp(hp_max, hp_max)}\n\n"
        f"🛡️ ¡Únete a la batalla con el botón de abajo o con /jefe\\_unirse!\n"
        f"El combate comenzará pronto. ¡Prepárate!"
    )
    for jug in todos:
        try:
            await context.bot.send_message(
                chat_id=jug["user_id"],
                text=texto,
                reply_markup=teclado,
                parse_mode="Markdown"
            )
        except Exception:
            pass


async def cmd_jefe_iniciar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: /jefe_iniciar <nombre> [hp] [dificultad]"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    if not sa._es_admin(user_id):
        await update.effective_message.reply_text("❌ Solo los administradores pueden invocar jefes.")
        return

    existente = _obtener_jefe_activo(chat_id)
    if existente:
        await update.effective_message.reply_text(
            f"⚠️ Ya hay un jefe activo: {existente['nombre']} (Estado: {existente['estado']})\n"
            f"Usa /jefe_cancelar para cancelarlo primero."
        )
        return

    if not context.args:
        await update.effective_message.reply_text(
            "Uso: /jefe_iniciar <nombre> [hp] [dificultad]\n"
            "Dificultades: Facil, Normal, Dificil, Legendario\n"
            "Ejemplo: /jefe_iniciar Dragón 50000 Dificil"
        )
        return

    nombre = context.args[0].replace("_", " ")
    dificultad = "Normal"
    hp_base = 10000
    hp_explicito = False

    if len(context.args) >= 2:
        try:
            hp_base = int(context.args[1])
            hp_explicito = True
        except ValueError:
            dificultad = context.args[1] if context.args[1] in DIFICULTADES else "Normal"

    if len(context.args) >= 3:
        if context.args[2] in DIFICULTADES:
            dificultad = context.args[2]

    cfg = DIFICULTADES[dificultad]
    hp_max = hp_base if hp_explicito else int(hp_base * cfg["multiplicador_hp"])

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO jefes_activos (nombre, hp_max, hp_actual, dificultad, estado, iniciado_por, chat_id) "
        "VALUES (?, ?, ?, ?, 'reclutando', ?, ?)",
        (nombre, hp_max, hp_max, dificultad, user_id, chat_id)
    )
    jefe_id = c.lastrowid
    conn.commit()
    conn.close()

    teclado = InlineKeyboardMarkup([[
        InlineKeyboardButton("⚔️ ¡Unirme a la batalla!", callback_data=f"jefe_unirse_{jefe_id}")
    ]])

    await update.effective_message.reply_text(
        f"🐉 *¡JEFE INVOCADO: {nombre.upper()}!*\n\n"
        f"💀 Dificultad: {dificultad}\n"
        f"❤️ HP: {_barra_hp(hp_max, hp_max)}\n\n"
        f"🛡️ ¡Aventureros, uníos a la batalla!\n"
        f"Usa el botón o /jefe_unirse para participar.\n\n"
        f"Usa /jefe_comenzar para iniciar el combate cuando haya participantes.",
        reply_markup=teclado,
        parse_mode="Markdown"
    )
    # Notificar a todos los jugadores registrados
    await _broadcast_jefe(context, nombre, dificultad, hp_max, jefe_id)

async def cmd_jefe_comenzar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: inicia el combate (cambia estado a 'combatiendo')."""
    import logging as _log
    _logger = _log.getLogger(__name__)

    async def _safe_reply(text, **kwargs):
        """Envía un mensaje garantizando siempre respuesta; en caso de error Markdown reintenta en texto plano."""
        try:
            await update.effective_message.reply_text(text, **kwargs)
        except Exception as e1:
            _logger.error("[jefe_comenzar] reply con kwargs=%s falló: %s", kwargs, e1)
            try:
                plain = text.replace("*", "").replace("_", "").replace("`", "").replace("[", "").replace("\\", "")
                await update.effective_message.reply_text(plain)
            except Exception as e2:
                _logger.error("[jefe_comenzar] reply plano también falló: %s", e2)

    try:
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        _logger.info("[jefe_comenzar] invocado por user_id=%s chat_id=%s", user_id, chat_id)
    except Exception as e:
        _logger.error("[jefe_comenzar] no se pudo obtener user_id/chat_id: %s", e)
        return

    try:
        es_admin = sa._es_admin(user_id)
    except Exception as e:
        _logger.error("[jefe_comenzar] error en _es_admin: %s", e)
        await _safe_reply("❌ Error interno al verificar permisos. Revisa los logs.")
        return

    if not es_admin:
        await _safe_reply("❌ Sin permiso.")
        return

    try:
        jefe = _obtener_jefe_activo(chat_id)
        _logger.info("[jefe_comenzar] jefe encontrado: %s", jefe)
    except Exception as e:
        _logger.error("[jefe_comenzar] error en _obtener_jefe_activo: %s", e)
        await _safe_reply("❌ Error interno al buscar el jefe. Revisa los logs.")
        return

    if not jefe:
        await _safe_reply("No hay ningún jefe activo en este chat.")
        return

    if jefe["estado"] != "reclutando":
        await _safe_reply(f"El jefe ya está en estado '{jefe['estado']}'.")
        return

    try:
        participantes = _obtener_participantes(jefe["id"])
        _logger.info("[jefe_comenzar] participantes: %s", len(participantes))
    except Exception as e:
        _logger.error("[jefe_comenzar] error en _obtener_participantes: %s", e)
        await _safe_reply("❌ Error interno al obtener participantes. Revisa los logs.")
        return

    if not participantes:
        teclado_opciones = InlineKeyboardMarkup([
            [InlineKeyboardButton("⏳ Seguir esperando", callback_data=f"jefe_esperar_{jefe['id']}")],
            [InlineKeyboardButton("❌ Cancelar jefe", callback_data=f"jefe_cancelar_cb_{jefe['id']}")],
        ])
        await _safe_reply(
            f"⚠️ No hay ningún participante unido a '{jefe['nombre']}'.\n\n¿Qué deseas hacer?",
            reply_markup=teclado_opciones,
        )
        return

    nombres_participantes = []
    for p in participantes:
        try:
            jug = db_helper.obtener_jugador(p["user_id"])
            nombre_pj = _esc(jug["nombre_personaje"]) if jug else f"Jugador {p['user_id']}"
        except Exception as e:
            _logger.error("[jefe_comenzar] error obteniendo nombre de jugador %s: %s", p.get("user_id"), e)
            nombre_pj = f"Jugador {p.get('user_id', '?')}"
        nombres_participantes.append(nombre_pj)

    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("UPDATE jefes_activos SET estado = 'combatiendo' WHERE id = ?", (jefe["id"],))
        conn.commit()
        conn.close()
        _logger.info("[jefe_comenzar] estado actualizado a 'combatiendo' para jefe id=%s", jefe["id"])
    except Exception as e:
        _logger.error("[jefe_comenzar] error actualizando DB: %s", e)
        await _safe_reply("❌ Error interno al iniciar el combate. Revisa los logs.")
        return

    nombres_plain = [n.replace("*", "").replace("\\_", "_") for n in nombres_participantes]
    lista_nombres = "\n".join(f"• {n}" for n in nombres_plain)
    texto_final = (
        f"⚔️ ¡EL COMBATE COMIENZA!\n\n"
        f"🐉 {jefe['nombre']} — {jefe['dificultad']}\n"
        f"❤️ {_barra_hp(jefe['hp_actual'], jefe['hp_max'])}\n\n"
        f"👥 Participantes ({len(participantes)}):\n"
        f"{lista_nombres}\n\n"
        f"⚔️ Usa /jefe_atacar para atacar (cooldown: {COOLDOWN_ATAQUE}s)"
    )
    await _safe_reply(texto_final)

async def cmd_jefe_cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: cancela el jefe activo (cualquier estado)."""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    if not sa._es_admin(user_id):
        try:
            await update.effective_message.reply_text("❌ Sin permiso.")
        except Exception:
            pass
        return

    jefe = _obtener_jefe_activo(chat_id)
    if not jefe:
        try:
            await update.effective_message.reply_text("No hay ningún jefe activo.")
        except Exception:
            pass
        return

    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("UPDATE jefes_activos SET estado = 'terminado' WHERE id = ?", (jefe["id"],))
        conn.commit()
        conn.close()
    except Exception as e:
        try:
            await update.effective_message.reply_text(f"❌ Error al cancelar en DB: {e}")
        except Exception:
            pass
        return

    try:
        await update.effective_message.reply_text(f"✅ Jefe '{jefe['nombre']}' cancelado. Estado anterior: {jefe['estado']}.")
    except Exception:
        pass


async def cmd_jefe_resetear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Superadmin: marca TODOS los jefes no terminados como terminados (limpieza de emergencia)."""
    user_id = update.effective_user.id

    if not sa._es_admin(user_id):
        try:
            await update.effective_message.reply_text("❌ Sin permiso.")
        except Exception:
            pass
        return

    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT id, nombre, estado FROM jefes_activos WHERE estado != 'terminado'")
        activos = c.fetchall()
        if not activos:
            conn.close()
            await update.effective_message.reply_text("No hay jefes activos que resetear.")
            return
        c.execute("UPDATE jefes_activos SET estado = 'terminado' WHERE estado != 'terminado'")
        conn.commit()
        conn.close()
        lista = "\n".join(f"• id={r[0]} {r[1]} ({r[2]})" for r in activos)
        await update.effective_message.reply_text(f"✅ Reseteados {len(activos)} jefe(s):\n{lista}")
    except Exception as e:
        try:
            await update.effective_message.reply_text(f"❌ Error al resetear: {e}")
        except Exception:
            pass

async def cmd_jefe_recompensa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: /jefe_recompensa <user_id> <objeto> [cantidad]"""
    user_id = update.effective_user.id

    if not sa._es_admin(user_id):
        await update.effective_message.reply_text("❌ Sin permiso.")
        return

    if len(context.args) < 2:
        await update.effective_message.reply_text("Uso: /jefe_recompensa <user_id> <objeto> [cantidad]")
        return

    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.effective_message.reply_text("user_id debe ser un número.")
        return

    objeto = context.args[1]
    try:
        cantidad = int(context.args[2]) if len(context.args) > 2 else 1
    except (ValueError, IndexError):
        await update.effective_message.reply_text("La cantidad debe ser un número entero.")
        return

    if not db_helper.existe_jugador(target_id):
        await update.effective_message.reply_text("Jugador no encontrado.")
        return

    db_helper.agregar_item(target_id, objeto, cantidad)
    db_helper.agregar_notificacion(target_id, f"🏆 ¡Recompensa de jefe recibida: {cantidad}x {objeto}!")
    await update.effective_message.reply_text(
        f"✅ Recompensa entregada:\n"
        f"👤 Jugador: {target_id}\n"
        f"🎁 {cantidad}x {objeto}"
    )

async def cmd_jefe_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: estado detallado del jefe actual."""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    if not sa._es_admin(user_id):
        await update.effective_message.reply_text("❌ Sin permiso.")
        return

    jefe = _obtener_jefe_activo(chat_id)
    if not jefe:
        await update.effective_message.reply_text("No hay ningún jefe activo.")
        return

    participantes = _obtener_participantes(jefe["id"])

    texto = (
        f"📊 *Estado del Jefe: {_esc(jefe['nombre'])}*\n\n"
        f"Estado: {jefe['estado']}\n"
        f"Dificultad: {jefe['dificultad']}\n"
        f"❤️ HP: {_barra_hp(jefe['hp_actual'], jefe['hp_max'])}\n"
        f"Iniciado: {jefe['fecha_inicio'][:16]}\n\n"
        f"👥 *Participantes ({len(participantes)}):*\n"
    )
    for p in participantes:
        jug = db_helper.obtener_jugador(p["user_id"])
        nombre = _esc(jug["nombre_personaje"]) if jug else f"Jugador {p['user_id']}"
        estado_pj = "💀" if not p["vivo"] else "⚔️"
        texto += f"{estado_pj} {nombre} — {p['dano_total']:,} daño | {p['intentos']} ataques\n"

    await update.effective_message.reply_text(texto, parse_mode="Markdown")

# ==================== COMANDOS JUGADOR ====================

async def cmd_jefe_unirse(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Jugador se une al combate."""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    if sa.verificar_baneado(user_id):
        await update.effective_message.reply_text("❌ Estás baneado.")
        return

    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        await update.effective_message.reply_text("❌ No tienes personaje. Usa /start para crear uno.")
        return

    jefe = _obtener_jefe_activo(chat_id)
    if not jefe:
        await update.effective_message.reply_text("No hay ningún jefe activo en este chat.")
        return

    if jefe["estado"] == "terminado":
        await update.effective_message.reply_text("Este combate ya ha terminado.")
        return

    if jefe["estado"] == "combatiendo":
        await update.effective_message.reply_text(
            "El combate ya comenzó. Ya no puedes unirte, ¡pero puedes atacar si ya estás registrado!\n"
            "Usa /jefe_atacar"
        )
        return

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT 1 FROM jefes_participantes WHERE jefe_id = ? AND user_id = ?", (jefe["id"], user_id))
    ya_esta = c.fetchone()
    if ya_esta:
        conn.close()
        await update.effective_message.reply_text("Ya estás registrado en este combate. ¡Espera que comience!")
        return

    c.execute(
        "INSERT INTO jefes_participantes (jefe_id, user_id, dano_total, intentos, vivo) VALUES (?, ?, 0, 0, 1)",
        (jefe["id"], user_id)
    )
    conn.commit()
    # Hook logros
    try:
        import logros as _logros
        _logros.registrar_jefe_participado(user_id)
    except Exception:
        pass
    conn.close()

    participantes = _obtener_participantes(jefe["id"])
    await update.effective_message.reply_text(
        f"⚔️ *{_esc(jug['nombre_personaje'])}* se unió al combate contra *{_esc(jefe['nombre'])}*!\n"
        f"👥 Total: {len(participantes)} participantes.\n"
        f"El combate comenzará en breve. ¡Mantente alerta!",
        parse_mode="Markdown"
    )

async def cmd_jefe_atacar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Jugador ataca al jefe."""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    if sa.verificar_baneado(user_id):
        await update.effective_message.reply_text("❌ Estás baneado.")
        return

    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        await update.effective_message.reply_text("❌ No tienes personaje.")
        return

    jefe = _obtener_jefe_activo(chat_id)
    if not jefe:
        await update.effective_message.reply_text("No hay ningún jefe activo.")
        return

    if jefe["estado"] != "combatiendo":
        await update.effective_message.reply_text(
            f"⏳ El combate aún no ha comenzado. ¡Espera la señal de inicio!"
        )
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM jefes_participantes WHERE jefe_id = ? AND user_id = ?", (jefe["id"], user_id))
    participante = c.fetchone()
    conn.close()

    if not participante:
        await update.effective_message.reply_text(
            "❌ No estás registrado en este combate.\n"
            "La próxima vez usa /jefe_unirse antes de que comience."
        )
        return

    if not participante["vivo"]:
        await update.effective_message.reply_text(
            "💀 Estás fuera de combate. Espera al final para recibir posibles recompensas."
        )
        return

    # Cooldown
    restante = _segundos_cooldown(user_id, jefe["id"])
    if restante > 0:
        await update.effective_message.reply_text(f"⏳ Debes esperar {restante}s antes de atacar de nuevo.")
        return

    cfg = DIFICULTADES[jefe["dificultad"]]
    prob_victoria = cfg["prob_victoria"]

    # Tirada de combate: éxito o huida
    exito = random.random() < prob_victoria
    dano = _calcular_dano_jugador(user_id, jefe["dificultad"]) if exito else 0

    # Actualizar HP del jefe si hay daño
    nuevo_hp = max(0, jefe["hp_actual"] - dano)

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    dano_recibido = 0
    hp_nuevo_jug = jug["hp_actual"]

    if exito:
        c.execute(
            "UPDATE jefes_activos SET hp_actual = ? WHERE id = ?",
            (nuevo_hp, jefe["id"])
        )
        c.execute(
            "UPDATE jefes_participantes SET dano_total = dano_total + ?, intentos = intentos + 1 WHERE jefe_id = ? AND user_id = ?",
            (dano, jefe["id"], user_id)
        )
    else:
        # Huida: el jugador recibe daño del jefe
        dano_recibido = random.randint(
            jefe["hp_max"] // 100,
            jefe["hp_max"] // 30
        )
        hp_nuevo_jug = max(1, jug["hp_actual"] - dano_recibido)
        db_helper.actualizar_jugador(user_id, hp_actual=hp_nuevo_jug)
        # Si llega al 2% o menos de su HP máximo, queda fuera de combate
        umbral_caida = max(1, int(jug["hp_max"] * 0.02))
        if hp_nuevo_jug <= umbral_caida:
            c.execute(
                "UPDATE jefes_participantes SET intentos = intentos + 1, vivo = 0 WHERE jefe_id = ? AND user_id = ?",
                (jefe["id"], user_id)
            )
        else:
            c.execute(
                "UPDATE jefes_participantes SET intentos = intentos + 1 WHERE jefe_id = ? AND user_id = ?",
                (jefe["id"], user_id)
            )

    conn.commit()
    conn.close()

    _actualizar_cooldown(user_id, jefe["id"])

    # Recargar datos del jefe para tener HP actualizado
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT hp_actual, hp_max FROM jefes_activos WHERE id = ?", (jefe["id"],))
    jefe_updated = c.fetchone()
    conn.close()
    hp_real = jefe_updated["hp_actual"] if jefe_updated else nuevo_hp

    if exito:
        texto = (
            f"⚔️ *{_esc(jug['nombre_personaje'])}* ataca a *{_esc(jefe['nombre'])}*!\n"
            f"💥 Daño infligido: *{dano:,}*\n"
            f"❤️ HP del jefe: {_barra_hp(hp_real, jefe['hp_max'])}\n"
        )
    else:
        umbral_caida = max(1, int(jug["hp_max"] * 0.02))
        if hp_nuevo_jug <= umbral_caida:
            texto = (
                f"💀 *{_esc(jug['nombre_personaje'])}* ha caído ante el poder de *{_esc(jefe['nombre'])}*!\n"
                f"💔 Daño recibido: *{dano_recibido:,}*\n"
                f"❤️ Tu HP: {hp_nuevo_jug:,} / {jug['hp_max']:,}\n\n"
                f"🚑 Tus compañeros te rescatan del campo de batalla, pero quedas *fuera de combate*.\n"
                f"⚠️ No podrás seguir atacando ni recibirás recompensas al terminar.\n"
                f"🐉 HP del jefe: {_barra_hp(hp_real, jefe['hp_max'])}\n"
            )
        else:
            texto = (
                f"💨 *{_esc(jug['nombre_personaje'])}* intenta atacar pero el jefe contraataca!\n"
                f"💔 Daño recibido: *{dano_recibido:,}*\n"
                f"❤️ Tu HP: {hp_nuevo_jug:,} / {jug['hp_max']:,}\n"
                f"🐉 HP del jefe: {_barra_hp(hp_real, jefe['hp_max'])}\n"
            )

    # ¿El jefe fue derrotado?
    if hp_real <= 0:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("UPDATE jefes_activos SET estado = 'terminado' WHERE id = ?", (jefe["id"],))
        conn.commit()
        conn.close()

        participantes = _obtener_participantes(jefe["id"])
        xp_base = cfg["xp_base"]
        oro_base = cfg["oro_base"]

        recompensas_texto = f"\n🏆 *¡{_esc(jefe['nombre']).upper()} DERROTADO!*\n\n"
        recompensas_texto += "🎖️ *Recompensas automáticas (XP y Oro):*\n"

        # Solo reciben premio los que siguen vivos (vivo = 1)
        participantes_vivos = [p for p in participantes if p.get("vivo", 1)]
        caidos = [p for p in participantes if not p.get("vivo", 1)]

        total_dano = sum(p["dano_total"] for p in participantes_vivos)
        _jefe_recomp = {}
        for p in participantes_vivos:
            pj = db_helper.obtener_jugador(p["user_id"])
            nombre_pj = _esc(pj["nombre_personaje"]) if pj else f"Jugador {p['user_id']}"
            proporcion = (p["dano_total"] / total_dano) if total_dano > 0 else (1 / len(participantes_vivos))
            xp_ganada = int(xp_base * proporcion * len(participantes_vivos))
            oro_ganado = int(oro_base * proporcion * len(participantes_vivos))
            nueva_xp = (pj["experiencia"] if pj else 0) + xp_ganada
            db_helper.actualizar_jugador(p["user_id"], experiencia=nueva_xp)
            economia.modificar_saldo(p["user_id"], "oro", oro_ganado, "recompensa_jefe")
            db_helper.agregar_notificacion(p["user_id"],
                f"🏆 El jefe {jefe['nombre']} fue derrotado! Obtuviste {xp_ganada} XP y {oro_ganado} oro.")
            recompensas_texto += f"• {nombre_pj}: +{xp_ganada} XP, +{oro_ganado} oro\n"
            _jefe_recomp[p["user_id"]] = {"xp": xp_ganada, "oro": oro_ganado}

        if caidos:
            nombres_caidos = []
            for p in caidos:
                pj = db_helper.obtener_jugador(p["user_id"])
                nombres_caidos.append(_esc(pj["nombre_personaje"]) if pj else f"Jugador {p['user_id']}")
            recompensas_texto += f"\n💀 *Caídos en combate (sin recompensa):*\n"
            recompensas_texto += "\n".join(f"• {n}" for n in nombres_caidos) + "\n"

        recompensas_texto += "\n🎁 ¡Los admins podrían entregar recompensas especiales a los más valientes!"
        texto += recompensas_texto

        try:
            _gan_pp = []
            for _p in participantes:
                _pj = db_helper.obtener_jugador(_p["user_id"])
                _r = _jefe_recomp.get(_p["user_id"], {})
                _gan_pp.append({
                    "user_id": _p["user_id"],
                    "nombre": _pj["nombre_personaje"] if _pj else f"Jugador {_p['user_id']}",
                    "score": _p["dano_total"],
                    "xp": _r.get("xp", 0),
                    "oro": _r.get("oro", 0),
                })
            await sa.notificar_admin_victoria(
                context.bot,
                "jefe",
                f"Jefe '{jefe['nombre']}' derrotado ({jefe['dificultad']})",
                _gan_pp
            )
        except Exception:
            pass

        # ── Hook anuncio_jefe: aviso global épico a todos los jugadores ──────
        try:
            import anuncio_jefe as _aj
            _participantes_anuncio = [
                {
                    "user_id": _p["user_id"],
                    "nombre": (db_helper.obtener_jugador(_p["user_id"]) or {}).get(
                        "nombre_personaje", f"Jugador {_p['user_id']}"
                    ),
                    "dano": _p["dano_total"],
                }
                for _p in participantes
            ]
            await _aj.anunciar_victoria_jefe(
                context.bot,
                jefe["nombre"],
                _participantes_anuncio,
            )
        except Exception:
            pass

        # ── Hook misiones diarias: participar en raid de jefe ────────────────
        try:
            import misiones_diarias as _md_jefe
            for _p in participantes:
                _md_jefe.registrar_progreso(_p["user_id"], "jefe", 1)
        except Exception:
            pass

    kb_refrescar = InlineKeyboardMarkup([[
        InlineKeyboardButton("🔄 Ver estado del jefe", callback_data=f"jefe_actualizar_{jefe['id']}")
    ]])
    await update.effective_message.reply_text(texto, parse_mode="Markdown", reply_markup=kb_refrescar)

# ==================== CALLBACK ACTUALIZAR ESTADO JEFE ====================

async def cb_jefe_actualizar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra el estado actual del jefe al pulsar el botón de actualizar."""
    query = update.callback_query
    await query.answer("🔄 Actualizando...")
    try:
        jefe_id = int(query.data.split("_")[-1])
    except (ValueError, IndexError):
        await query.answer("Error al procesar.", show_alert=True)
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM jefes_activos WHERE id = ?", (jefe_id,))
    jefe = c.fetchone()
    conn.close()

    if not jefe:
        await query.answer("Este jefe ya no existe.", show_alert=True)
        return

    estado_txt = {"reclutando": "🟡 Reclutando", "combatiendo": "🔴 En combate", "terminado": "⚫ Terminado"}.get(jefe["estado"], jefe["estado"])
    texto = (
        f"🐉 *{_esc(jefe['nombre'])}*\n"
        f"💀 Dificultad: {jefe['dificultad']}\n"
        f"❤️ HP: {_barra_hp(jefe['hp_actual'], jefe['hp_max'])}\n"
        f"📊 Estado: {estado_txt}\n"
    )
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("🔄 Actualizar de nuevo", callback_data=f"jefe_actualizar_{jefe_id}")
    ]])
    try:
        await query.edit_message_text(texto, parse_mode="Markdown", reply_markup=kb)
    except Exception:
        await query.answer(f"❤️ HP: {jefe['hp_actual']}/{jefe['hp_max']}", show_alert=True)

# ==================== CALLBACK BOTÓN UNIRSE ====================

async def cb_jefe_unirse(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id
    data = query.data  # jefe_unirse_<jefe_id>

    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        await query.answer("❌ No tienes personaje registrado.", show_alert=True)
        return

    # Verificar si el jugador está ocupado
    if db_helper.es_ocupado(user_id):
        actividad = db_helper.nombre_actividad(user_id)
        await query.answer(
            f"⚠️ Estás {actividad} ahora mismo.\n"
            f"Termina lo que estás haciendo y vuelve a pulsar este botón.",
            show_alert=True
        )
        return

    try:
        jefe_id = int(data.split("_")[-1])
    except (ValueError, IndexError):
        await query.answer("Error al procesar la solicitud.", show_alert=True)
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM jefes_activos WHERE id = ?", (jefe_id,))
    jefe = c.fetchone()
    if not jefe or jefe["estado"] == "terminado":
        conn.close()
        await query.answer("Este combate ya no está disponible.", show_alert=True)
        return

    if jefe["estado"] == "combatiendo":
        conn.close()
        await query.answer("El combate ya comenzó, no puedes unirte ahora.", show_alert=True)
        return

    c.execute("SELECT 1 FROM jefes_participantes WHERE jefe_id = ? AND user_id = ?", (jefe_id, user_id))
    ya_esta = c.fetchone()
    if ya_esta:
        conn.close()
        await query.answer("¡Ya estás registrado en este combate!", show_alert=True)
        return

    c.execute(
        "INSERT INTO jefes_participantes (jefe_id, user_id, dano_total, intentos, vivo) VALUES (?, ?, 0, 0, 1)",
        (jefe_id, user_id)
    )
    conn.commit()
    c.execute("SELECT COUNT(*) FROM jefes_participantes WHERE jefe_id = ?", (jefe_id,))
    total = c.fetchone()[0]
    conn.close()

    await query.answer(f"¡{jug['nombre_personaje']} se unió al combate! ({total} total)", show_alert=True)


async def cb_jefe_esperar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin pulsa 'Seguir esperando' — refresca el conteo de participantes."""
    query = update.callback_query
    await query.answer()
    if not sa._es_admin(update.effective_user.id):
        return
    try:
        jefe_id = int(query.data.split("_")[-1])
    except (ValueError, IndexError):
        return
    participantes = _obtener_participantes(jefe_id)
    if participantes:
        await query.edit_message_text(
            f"✅ ¡Te has unido! Hay {len(participantes)} participante(s) en la batalla. El combate comenzará pronto."
        )
    else:
        teclado = InlineKeyboardMarkup([
            [InlineKeyboardButton("⏳ Seguir esperando", callback_data=f"jefe_esperar_{jefe_id}")],
            [InlineKeyboardButton("❌ Cancelar jefe",    callback_data=f"jefe_cancelar_cb_{jefe_id}")],
        ])
        await query.edit_message_text(
            "⚠️ *Aún no hay participantes.* Pulsa 'Seguir esperando' para refrescar o cancela el jefe.",
            reply_markup=teclado,
            parse_mode="Markdown"
        )


async def cb_jefe_cancelar_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin pulsa 'Cancelar jefe' desde el menú de sin-participantes."""
    query = update.callback_query
    await query.answer()
    if not sa._es_admin(update.effective_user.id):
        return
    try:
        jefe_id = int(query.data.split("_")[-1])
    except (ValueError, IndexError):
        return
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE jefes_activos SET estado = 'terminado' WHERE id = ?", (jefe_id,))
    conn.commit()
    conn.close()
    await query.edit_message_text("✅ Jefe cancelado. El evento ha sido eliminado.")


# ==================== FUNCIONES PARA AUTOMATIZACIONES ====================

async def crear_jefe_automatico(nombre: str, hp: int, dificultad: str, context) -> int:
    """Crea un jefe de raid global (chat_id=0) y notifica a todos los jugadores."""
    cfg = DIFICULTADES.get(dificultad, DIFICULTADES["Normal"])
    hp_max = int(hp * cfg["multiplicador_hp"])
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO jefes_activos (nombre, hp_max, hp_actual, dificultad, estado, iniciado_por, chat_id) "
        "VALUES (?, ?, ?, ?, 'reclutando', 0, 0)",
        (nombre, hp_max, hp_max, dificultad)
    )
    jefe_id = c.lastrowid
    conn.commit()
    conn.close()
    await _broadcast_jefe(context, nombre, dificultad, hp_max, jefe_id)
    return jefe_id

async def iniciar_combate_automatico(context, jefe_id: int):
    """Auto-inicia el combate de un jefe automatico tras el periodo de reclutamiento."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM jefes_activos WHERE id = ? AND estado = 'reclutando'", (jefe_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return
    jefe = dict(row)
    c.execute("SELECT COUNT(*) as total FROM jefes_participantes WHERE jefe_id = ?", (jefe_id,))
    total = c.fetchone()["total"]
    if total == 0:
        # Nadie se unio, cancelar
        c.execute("UPDATE jefes_activos SET estado = 'terminado' WHERE id = ?", (jefe_id,))
        conn.commit()
        conn.close()
        try:
            from broadcast import broadcast_global
            await broadcast_global(context.bot, f"⚠️ El jefe *{_esc(jefe['nombre'])}* fue cancelado por falta de participantes.")
        except Exception:
            pass
        return
    c.execute("UPDATE jefes_activos SET estado = 'combatiendo' WHERE id = ?", (jefe_id,))
    conn.commit()
    conn.close()
    texto = (
        f"⚔️ *¡EL COMBATE COMIENZA!*\n\n"
        f"🐉 *{_esc(jefe['nombre'])}* — {jefe['dificultad']}\n"
        f"❤️ {_barra_hp(jefe['hp_actual'], jefe['hp_max'])}\n\n"
        f"⚔️ Usa /jefe\\_atacar para atacar! (cooldown: {COOLDOWN_ATAQUE}s)\n"
        f"💪 {total} guerrero(s) en batalla."
    )
    try:
        from broadcast import broadcast_global
        await broadcast_global(context.bot, texto)
    except Exception:
        pass


# ==================== REGISTRO DE HANDLERS ====================

def registrar_handlers(app):
    # Comandos de admin
    app.add_handler(CommandHandler("jefe_iniciar",    cmd_jefe_iniciar))
    app.add_handler(CommandHandler("jefe_comenzar",   cmd_jefe_comenzar))
    app.add_handler(CommandHandler("jefe_cancelar",   cmd_jefe_cancelar))
    app.add_handler(CommandHandler("jefe_resetear",   cmd_jefe_resetear))
    app.add_handler(CommandHandler("jefe_recompensa", cmd_jefe_recompensa))
    app.add_handler(CommandHandler("jefe_info",       cmd_jefe_info))
    # Comandos de jugador
    app.add_handler(CommandHandler("jefe_unirse",     cmd_jefe_unirse))
    app.add_handler(CommandHandler("jefe_atacar",     cmd_jefe_atacar))
    # Callbacks de botones
    app.add_handler(CallbackQueryHandler(cb_jefe_unirse,      pattern=r"^jefe_unirse_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_jefe_actualizar,  pattern=r"^jefe_actualizar_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_jefe_esperar,     pattern=r"^jefe_esperar_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_jefe_cancelar_cb, pattern=r"^jefe_cancelar_cb_\d+$"))
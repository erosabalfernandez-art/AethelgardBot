#!/usr/bin/env python3
# guerra_gremios.py — Sistema de Guerra de Gremios (Guild War)
#
# Flujo:
#   /guerra_gremios_declarar <gremio_rival_id|nombre>  — Líder desafía a otro gremio
#   Rival acepta con /guerra_gremios_aceptar <guerra_id> o rechaza con /guerra_gremios_rechazar
#   El sistema crea enfrentamientos 1v1 entre miembros (matchmaking inteligente por nivel)
#   /guerra_gremios_duelo   — Peleas individuales (cooldown 45s)
#   /guerra_gremios_estado  — Marcador en tiempo real
#   /guerra_gremios_rendirse — Líder abandona (penalización de puntos)
#   Admin: /admin_guerra_gremios_resolver <guerra_id> <ganador_gremio_id>

import sqlite3
import random
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
from html import escape as _he

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler

import db_helper
import economia
import superadmin as sa

DB_PATH = "aethelgard.db"

COOLDOWN_DUELO_GUERRA = 45  # segundos
PUNTOS_VICTORIA_DUELO = 15
PUNTOS_DEFENSA_EXITOSA = 8
ORO_DERROTA_PORCENTAJE = 0.05   # 5% del oro del banco del gremio perdedor
XP_POR_DUELO_VICTORIA = 100
XP_POR_DUELO_DERROTA  = 30
DURACION_GUERRA_HORAS  = 24

# ==================== TABLAS ====================
def _init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS guerras_gremios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        gremio_atacante_id INTEGER NOT NULL,
        gremio_defensor_id INTEGER NOT NULL,
        puntos_atacante INTEGER DEFAULT 0,
        puntos_defensor INTEGER DEFAULT 0,
        estado TEXT DEFAULT 'pendiente',
        declarada_por INTEGER,
        fecha_declaracion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        fecha_inicio TIMESTAMP,
        fecha_fin TIMESTAMP
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS guerras_gremios_participantes (
        guerra_id INTEGER,
        user_id INTEGER,
        gremio_id INTEGER,
        duelos INTEGER DEFAULT 0,
        victorias INTEGER DEFAULT 0,
        puntos_aportados INTEGER DEFAULT 0,
        PRIMARY KEY (guerra_id, user_id)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS guerras_gremios_cooldown (
        user_id INTEGER,
        guerra_id INTEGER,
        ultimo_duelo TIMESTAMP,
        PRIMARY KEY (user_id, guerra_id)
    )''')
    conn.commit()
    conn.close()

_init_db()

# ==================== HELPERS ====================
def _obtener_guerra_activa_gremio(gremio_id: int) -> Optional[Dict]:
    """Retorna la guerra activa donde participa este gremio."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(
        "SELECT * FROM guerras_gremios WHERE (gremio_atacante_id = ? OR gremio_defensor_id = ?) "
        "AND estado IN ('activa', 'pendiente') ORDER BY id DESC LIMIT 1",
        (gremio_id, gremio_id)
    )
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def _obtener_guerra_por_id(guerra_id: int) -> Optional[Dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM guerras_gremios WHERE id = ?", (guerra_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def _obtener_gremio(gremio_id: int) -> Optional[Dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM gremios WHERE id = ?", (gremio_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def _obtener_gremio_de_jugador(user_id: int) -> Optional[Dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('''SELECT g.*, m.rango FROM gremios g
                 JOIN miembros_gremio m ON g.id = m.gremio_id
                 WHERE m.jugador_id = ?''', (user_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def _es_lider(user_id: int, gremio_id: int) -> bool:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT rango FROM miembros_gremio WHERE gremio_id = ? AND jugador_id = ?", (gremio_id, user_id))
    row = c.fetchone()
    conn.close()
    return row and row[0] in ('lider', 'fundador')

def _segundos_cooldown(user_id: int, guerra_id: int) -> int:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT ultimo_duelo FROM guerras_gremios_cooldown WHERE user_id = ? AND guerra_id = ?",
              (user_id, guerra_id))
    row = c.fetchone()
    conn.close()
    if not row:
        return 0
    transcurrido = (datetime.now() - datetime.fromisoformat(row[0])).total_seconds()
    return max(0, int(COOLDOWN_DUELO_GUERRA - transcurrido))

def _actualizar_cooldown(user_id: int, guerra_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO guerras_gremios_cooldown (user_id, guerra_id, ultimo_duelo) VALUES (?, ?, ?)",
              (user_id, guerra_id, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def _registrar_participante(guerra_id: int, user_id: int, gremio_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO guerras_gremios_participantes (guerra_id, user_id, gremio_id) VALUES (?, ?, ?)",
              (guerra_id, user_id, gremio_id))
    conn.commit()
    conn.close()

def _actualizar_participante(guerra_id: int, user_id: int, duelos_d: int = 0,
                              victorias_d: int = 0, puntos_d: int = 0):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "UPDATE guerras_gremios_participantes SET duelos = duelos + ?, victorias = victorias + ?, "
        "puntos_aportados = puntos_aportados + ? WHERE guerra_id = ? AND user_id = ?",
        (duelos_d, victorias_d, puntos_d, guerra_id, user_id)
    )
    conn.commit()
    conn.close()

def _sumar_puntos_gremio(guerra_id: int, es_atacante: bool, puntos: int):
    campo = "puntos_atacante" if es_atacante else "puntos_defensor"
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(f"UPDATE guerras_gremios SET {campo} = {campo} + ? WHERE id = ?", (puntos, guerra_id))
    conn.commit()
    conn.close()

def _matchmake_rival(guerra_id: int, gremio_rival_id: int, user_id: int, nivel_ref: int) -> Optional[Dict]:
    """Busca el rival más equilibrado del gremio enemigo que esté disponible."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(
        "SELECT m.jugador_id, j.nivel FROM miembros_gremio m "
        "JOIN jugadores j ON j.user_id = m.jugador_id "
        "WHERE m.gremio_id = ? AND j.hp_actual > 0 "
        "ORDER BY ABS(j.nivel - ?) LIMIT 5",
        (gremio_rival_id, nivel_ref)
    )
    candidatos = c.fetchall()
    conn.close()
    if not candidatos:
        return None
    seleccionado = candidatos[0]
    return db_helper.obtener_jugador(seleccionado["jugador_id"])

def _simular_duelo_gremio(atacante: Dict, defensor: Dict) -> Tuple[bool, int, int]:
    """Simulación de duelo 1v1. Retorna (victoria_atacante, dano_inf, dano_rec)."""
    atk_n = atacante.get("nivel", 1)
    def_n = defensor.get("nivel", 1)
    factor_atk = atk_n * random.uniform(0.8, 1.3)
    factor_def = def_n * random.uniform(0.7, 1.2)
    hp_atk = max(0.3, atacante.get("hp_actual", 100) / max(1, atacante.get("hp_max", 100)))
    hp_def = max(0.3, defensor.get("hp_actual", 100) / max(1, defensor.get("hp_max", 100)))
    poder_atk = factor_atk * hp_atk * random.randint(5, 15)
    poder_def = factor_def * hp_def * random.randint(4, 12)
    total = poder_atk + poder_def
    victoria = random.random() < (poder_atk / total)
    dano_inf = int(poder_atk * 10)
    dano_rec = int(poder_def * 8)
    return victoria, dano_inf, dano_rec

def _en_ciudad(user_id: int) -> bool:
    """Retorna True si el jugador está en una ciudad."""
    try:
        import datos_zona as _dz
        zona_nombre = db_helper.obtener_zona_actual(user_id)
        return any(z["nombre"] == zona_nombre and z["tipo"] == "ciudad" for z in _dz.ZONAS)
    except Exception:
        return False

def _obtener_top_participantes(guerra_id: int, gremio_id: int, limite: int = 5) -> List[Dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(
        "SELECT * FROM guerras_gremios_participantes WHERE guerra_id = ? AND gremio_id = ? "
        "ORDER BY puntos_aportados DESC LIMIT ?",
        (guerra_id, gremio_id, limite)
    )
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ==================== COMANDOS ====================

async def cmd_guerra_gremios_declarar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Líder desafía a otro gremio. /guerra_gremios_declarar <gremio_id_o_nombre>"""
    user_id = update.effective_user.id

    if sa.verificar_baneado(user_id):
        await update.effective_message.reply_text("❌ Estás baneado.")
        return

    if not _en_ciudad(user_id):
        await update.effective_message.reply_text("🏙️ Las actividades de gremio solo están disponibles en ciudades.")
        return

    gremio_mio = _obtener_gremio_de_jugador(user_id)
    if not gremio_mio:
        await update.effective_message.reply_text("❌ No perteneces a ningún gremio.")
        return

    if not _es_lider(user_id, gremio_mio["id"]):
        await update.effective_message.reply_text("❌ Solo el líder del gremio puede declarar guerras.")
        return

    guerra_existente = _obtener_guerra_activa_gremio(gremio_mio["id"])
    if guerra_existente:
        await update.effective_message.reply_text("⚠️ Tu gremio ya está en una guerra activa. Termínala primero.")
        return

    if not context.args:
        await update.effective_message.reply_text("Uso: /guerra_gremios_declarar <nombre_gremio_rival>\n"
                                        "Ejemplo: /guerra_gremios_declarar Dragones_del_Norte")
        return

    nombre_rival = " ".join(context.args).replace("_", " ")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM gremios WHERE nombre = ? AND id != ?", (nombre_rival, gremio_mio["id"]))
    gremio_rival = c.fetchone()
    conn.close()

    if not gremio_rival:
        await update.effective_message.reply_text(f"❌ No se encontró ningún gremio llamado '{nombre_rival}'.")
        return

    gremio_rival = dict(gremio_rival)

    # Verificar que el rival no esté ya en guerra
    guerra_rival = _obtener_guerra_activa_gremio(gremio_rival["id"])
    if guerra_rival:
        await update.effective_message.reply_text(f"❌ El gremio {nombre_rival} ya está en una guerra activa.")
        return

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO guerras_gremios (gremio_atacante_id, gremio_defensor_id, estado, declarada_por, fecha_declaracion) "
        "VALUES (?, ?, 'pendiente', ?, ?)",
        (gremio_mio["id"], gremio_rival["id"], user_id, datetime.now().isoformat())
    )
    guerra_id = c.lastrowid
    conn.commit()
    conn.close()

    # Notificar al líder del gremio rival
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT jugador_id FROM miembros_gremio WHERE gremio_id = ? AND rango IN ('lider', 'fundador')",
              (gremio_rival["id"],))
    lideres_rival = [r["jugador_id"] for r in c.fetchall()]
    conn.close()

    for lid in lideres_rival:
        db_helper.agregar_notificacion(lid,
            f"⚔️ ¡El gremio {gremio_mio['nombre']} te ha declarado la guerra!\n"
            f"Guerra ID: #{guerra_id}\n"
            f"Usa /guerra_gremios_aceptar {guerra_id} para aceptar o /guerra_gremios_rechazar {guerra_id} para rechazar.")

    # Notificar a los miembros del propio gremio (excepto al líder que lo declaró)
    conn_prop = sqlite3.connect(DB_PATH)
    conn_prop.row_factory = sqlite3.Row
    c_prop = conn_prop.cursor()
    c_prop.execute(
        "SELECT jugador_id FROM miembros_gremio WHERE gremio_id = ? AND jugador_id != ?",
        (gremio_mio["id"], user_id)
    )
    for r in c_prop.fetchall():
        db_helper.agregar_notificacion(r["jugador_id"],
            f"⚔️ Tu líder ha declarado guerra al gremio {nombre_rival}. "
            f"Guerra ID: #{guerra_id}. Prepárate para combatir.")
    conn_prop.close()

    teclado = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Aceptar", callback_data=f"gg_aceptar_{guerra_id}"),
        InlineKeyboardButton("❌ Rechazar", callback_data=f"gg_rechazar_{guerra_id}")
    ]])

    await update.effective_message.reply_text(
        f"⚔️ <b>¡Declaración de guerra enviada!</b>\n\n"
        f"Tu gremio: <b>{_he(gremio_mio['nombre'])}</b>\n"
        f"Rival: <b>{_he(nombre_rival)}</b>\n"
        f"Guerra ID: #{guerra_id}\n\n"
        f"Esperando que el líder del gremio rival acepte...",
        reply_markup=teclado,
        parse_mode="HTML"
    )

async def cmd_guerra_gremios_aceptar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not _en_ciudad(user_id):
        await update.effective_message.reply_text("🏙️ Las actividades de gremio solo están disponibles en ciudades.")
        return
    if not context.args:
        await update.effective_message.reply_text("Uso: /guerra_gremios_aceptar <guerra_id>")
        return
    try:
        guerra_id = int(context.args[0])
    except ValueError:
        await update.effective_message.reply_text("guerra_id debe ser un número.")
        return
    await _procesar_respuesta_guerra(update, user_id, guerra_id, aceptar=True)

async def cmd_guerra_gremios_rechazar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not _en_ciudad(user_id):
        await update.effective_message.reply_text("🏙️ Las actividades de gremio solo están disponibles en ciudades.")
        return
    if not context.args:
        await update.effective_message.reply_text("Uso: /guerra_gremios_rechazar <guerra_id>")
        return
    try:
        guerra_id = int(context.args[0])
    except ValueError:
        await update.effective_message.reply_text("guerra_id debe ser un número.")
        return
    await _procesar_respuesta_guerra(update, user_id, guerra_id, aceptar=False)

async def _procesar_respuesta_guerra(update, user_id: int, guerra_id: int, aceptar: bool):
    gremio = _obtener_gremio_de_jugador(user_id)
    if not gremio:
        await update.effective_message.reply_text("❌ No perteneces a ningún gremio.")
        return

    guerra = _obtener_guerra_por_id(guerra_id)
    if not guerra:
        await update.effective_message.reply_text("Guerra no encontrada.")
        return

    if guerra["estado"] != "pendiente":
        await update.effective_message.reply_text("Esta guerra ya no está pendiente.")
        return

    if gremio["id"] != guerra["gremio_defensor_id"]:
        await update.effective_message.reply_text("Solo el gremio defensor puede responder a esta declaración de guerra.")
        return

    if not _es_lider(user_id, gremio["id"]):
        await update.effective_message.reply_text("Solo el líder del gremio puede responder a declaraciones de guerra.")
        return

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if aceptar:
        gremio_atacante = _obtener_gremio(guerra["gremio_atacante_id"])

        # Comprobar si la aprobación automática está activada
        _sin_aprobacion = False
        try:
            import automatizaciones as _auto_mod
            _sin_aprobacion = _auto_mod._get("gg_sin_aprobacion") == "1"
        except Exception:
            pass

        if _sin_aprobacion:
            # Auto-aprobar: activar guerra directamente
            fecha_fin = datetime.now() + timedelta(hours=DURACION_GUERRA_HORAS)
            c.execute(
                "UPDATE guerras_gremios SET estado='activa', fecha_inicio=?, fecha_fin=? WHERE id=?",
                (datetime.now().isoformat(), fecha_fin.isoformat(), guerra_id)
            )
            conn.commit()
            conn.close()
            # Notificar a ambos gremios
            for gid in (guerra["gremio_atacante_id"], guerra["gremio_defensor_id"]):
                cn = sqlite3.connect(DB_PATH)
                cn.row_factory = sqlite3.Row
                cr = cn.cursor()
                cr.execute("SELECT jugador_id FROM miembros_gremio WHERE gremio_id = ?", (gid,))
                for r in cr.fetchall():
                    db_helper.agregar_notificacion(r["jugador_id"],
                        f"⚔️ ¡La guerra entre {gremio_atacante['nombre']} y {gremio['nombre']} ha comenzado!\n"
                        f"Usa /guerra_gremios_duelo para combatir.")
                cn.close()
            await update.effective_message.reply_text(
                f"⚔️ <b>¡GUERRA INICIADA!</b>\n\n"
                f"🔴 {_he(gremio_atacante['nombre'])} vs 🔵 {_he(gremio['nombre'])}\n\n"
                f"La guerra ha comenzado automáticamente. ¡Que empiece el combate!",
                parse_mode="HTML"
            )
            return
        else:
            # Flujo estándar: pendiente de aprobación del superadmin
            c.execute(
                "UPDATE guerras_gremios SET estado = 'esperando_superadmin' WHERE id = ?",
                (guerra_id,)
            )
            conn.commit()
            conn.close()

        # Notificar al superadmin
        import os
        superadmin_id = os.environ.get("SUPERADMIN_ID")
        if superadmin_id:
            try:
                teclado_admin = InlineKeyboardMarkup([[
                    InlineKeyboardButton("✅ Aprobar guerra", callback_data=f"gg_aprobar_{guerra_id}"),
                    InlineKeyboardButton("❌ Rechazar",       callback_data=f"gg_rechazar_admin_{guerra_id}"),
                ]])
                await update.get_bot().send_message(
                    chat_id=int(superadmin_id),
                    text=(
                        f"⚔️ <b>Solicitud de Guerra de Gremios</b>\n\n"
                        f"🔴 Gremio atacante: <b>{_he(gremio_atacante['nombre'])}</b>\n"
                        f"🔵 Gremio defensor: <b>{_he(gremio['nombre'])}</b>\n"
                        f"Guerra ID: #{guerra_id}\n\n"
                        f"Ambos líderes han aceptado. Aprueba para iniciar la guerra:"
                    ),
                    reply_markup=teclado_admin,
                    parse_mode="HTML"
                )
            except Exception:
                pass

        await update.effective_message.reply_text(
            f"✅ <b>¡Solicitud enviada al administrador!</b>\n\n"
            f"🔴 Atacante: <b>{_he(gremio_atacante['nombre'])}</b>\n"
            f"🔵 Defensor: <b>{_he(gremio['nombre'])}</b>\n\n"
            f"La guerra comenzará cuando el administrador la apruebe.\n"
            f"Recibirás una notificación cuando inicie.",
            parse_mode="HTML"
        )
        # Notificar al líder del gremio atacante que el rival aceptó
        conn_atac = sqlite3.connect(DB_PATH)
        conn_atac.row_factory = sqlite3.Row
        c_atac = conn_atac.cursor()
        c_atac.execute(
            "SELECT jugador_id FROM miembros_gremio WHERE gremio_id = ? AND rango IN ('lider', 'fundador')",
            (guerra["gremio_atacante_id"],)
        )
        for r in c_atac.fetchall():
            db_helper.agregar_notificacion(r["jugador_id"],
                f"✅ El gremio {gremio['nombre']} aceptó tu declaración de guerra #{guerra_id}. "
                f"Esperando aprobación del administrador.")
        conn_atac.close()
    else:
        c.execute("UPDATE guerras_gremios SET estado = 'rechazada' WHERE id = ?", (guerra_id,))
        conn.commit()
        conn.close()
        gremio_atacante = _obtener_gremio(guerra["gremio_atacante_id"])
        await update.effective_message.reply_text(
            f"❌ <b>Guerra rechazada.</b>\n"
            f"El gremio {_he(gremio['nombre'])} rechazó el desafío de {_he(gremio_atacante['nombre'])}.",
            parse_mode="HTML"
        )
        # Notificar al atacante
        conn2 = sqlite3.connect(DB_PATH)
        conn2.row_factory = sqlite3.Row
        c2 = conn2.cursor()
        c2.execute("SELECT jugador_id FROM miembros_gremio WHERE gremio_id = ? AND rango IN ('lider', 'fundador')",
                   (guerra["gremio_atacante_id"],))
        lideres = [r["jugador_id"] for r in c2.fetchall()]
        conn2.close()
        for lid in lideres:
            db_helper.agregar_notificacion(lid,
                f"❌ El gremio {gremio['nombre']} rechazó tu declaración de guerra.")

async def cmd_guerra_gremios_estado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not _en_ciudad(user_id):
        await update.effective_message.reply_text("🏙️ Las actividades de gremio solo están disponibles en ciudades.")
        return
    gremio = _obtener_gremio_de_jugador(user_id)
    if not gremio:
        await update.effective_message.reply_text("❌ No perteneces a ningún gremio.")
        return

    guerra = _obtener_guerra_activa_gremio(gremio["id"])
    if not guerra:
        await update.effective_message.reply_text("Tu gremio no está en ninguna guerra activa.")
        return

    ga = _obtener_gremio(guerra["gremio_atacante_id"])
    gd = _obtener_gremio(guerra["gremio_defensor_id"])
    pa = guerra["puntos_atacante"]
    pd = guerra["puntos_defensor"]
    total = pa + pd or 1
    barra_a = int(20 * pa / total)
    barra_d = 20 - barra_a

    tiempo = ""
    if guerra["estado"] == "activa" and guerra.get("fecha_fin"):
        fin = datetime.fromisoformat(guerra["fecha_fin"])
        restante = (fin - datetime.now()).total_seconds()
        if restante > 0:
            h, m = int(restante // 3600), int((restante % 3600) // 60)
            tiempo = f"⏱️ Tiempo restante: {h}h {m}m\n"
        else:
            tiempo = "⏱️ ¡Tiempo finalizado!\n"

    await update.effective_message.reply_text(
        f"⚔️ <b>GUERRA DE GREMIOS</b> (#{guerra['id']})\n\n"
        f"🔴 <b>{_he(ga['nombre'])}</b>: {pa} pts\n"
        f"{'🟥' * barra_a}{'⬛' * barra_d}\n\n"
        f"🔵 <b>{_he(gd['nombre'])}</b>: {pd} pts\n"
        f"{'⬛' * barra_a}{'🟦' * barra_d}\n\n"
        f"{tiempo}"
        f"Estado: {guerra['estado']}",
        parse_mode="HTML"
    )

async def cmd_guerra_gremios_duelo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Jugador pelea contra un miembro del gremio rival."""
    user_id = update.effective_user.id
    try:
        import guia_contextual as _gc
        await _gc.enviar(user_id, context, "guerra_gremios_duelo")
    except Exception:
        pass

    if sa.verificar_baneado(user_id):
        await update.effective_message.reply_text("❌ Estás baneado.")
        return

    if not _en_ciudad(user_id):
        await update.effective_message.reply_text("🏙️ Las actividades de gremio solo están disponibles en ciudades.")
        return

    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        await update.effective_message.reply_text("❌ No tienes personaje.")
        return

    gremio = _obtener_gremio_de_jugador(user_id)
    if not gremio:
        await update.effective_message.reply_text("❌ No perteneces a ningún gremio.")
        return

    guerra = _obtener_guerra_activa_gremio(gremio["id"])
    if not guerra or guerra["estado"] != "activa":
        await update.effective_message.reply_text("Tu gremio no está en una guerra activa.")
        return

    restante = _segundos_cooldown(user_id, guerra["id"])
    if restante > 0:
        await update.effective_message.reply_text(f"⏳ Debes esperar {restante}s antes del próximo duelo.")
        return

    es_atacante = gremio["id"] == guerra["gremio_atacante_id"]
    gremio_rival_id = guerra["gremio_defensor_id"] if es_atacante else guerra["gremio_atacante_id"]

    rival = _matchmake_rival(guerra["id"], gremio_rival_id, user_id, jug.get("nivel", 1))
    if not rival:
        rival = {"nombre_personaje": "Guardia rival", "nivel": max(1, jug.get("nivel",1)-1),
                 "hp_actual": 100, "hp_max": 100, "clase": ""}

    victoria, dano_inf, dano_rec = _simular_duelo_gremio(jug, rival)

    _registrar_participante(guerra["id"], user_id, gremio["id"])
    _actualizar_cooldown(user_id, guerra["id"])

    if victoria:
        _sumar_puntos_gremio(guerra["id"], es_atacante, PUNTOS_VICTORIA_DUELO)
        _actualizar_participante(guerra["id"], user_id, duelos_d=1, victorias_d=1, puntos_d=PUNTOS_VICTORIA_DUELO)
        nueva_xp = jug["experiencia"] + XP_POR_DUELO_VICTORIA
        db_helper.actualizar_jugador(user_id, experiencia=nueva_xp)
        nuevo_hp_rival = max(0, rival.get("hp_actual", 100) - dano_inf)
        if rival.get("user_id"):
            db_helper.actualizar_jugador(rival["user_id"], hp_actual=nuevo_hp_rival)
            db_helper.agregar_notificacion(rival["user_id"],
                f"⚔️ {jug['nombre_personaje']} te derrotó en la guerra de gremios. -{dano_inf} HP.")
        await update.effective_message.reply_text(
            f"⚔️ <b>{_he(jug['nombre_personaje'])}</b> vs <b>{_he(rival['nombre_personaje'])}</b>\n\n"
            f"✅ ¡VICTORIA!\n"
            f"💥 Daño infligido: {dano_inf}\n"
            f"+{PUNTOS_VICTORIA_DUELO} puntos para <b>{_he(gremio['nombre'])}</b>\n"
            f"⭐ +{XP_POR_DUELO_VICTORIA} XP",
            parse_mode="HTML"
        )
        # Notificar log de guerra a los miembros del propio gremio
        cn_v = sqlite3.connect(DB_PATH)
        cn_v.row_factory = sqlite3.Row
        cr_v = cn_v.cursor()
        cr_v.execute(
            "SELECT jugador_id FROM miembros_gremio WHERE gremio_id = ? AND jugador_id != ?",
            (gremio["id"], user_id)
        )
        for rv in cr_v.fetchall():
            db_helper.agregar_notificacion(rv["jugador_id"],
                f"⚔️ ¡Victoria! {jug['nombre_personaje']} derrotó a {rival['nombre_personaje']} "
                f"en la guerra. +{PUNTOS_VICTORIA_DUELO} pts para {gremio['nombre']}.")
        cn_v.close()
    else:
        _actualizar_participante(guerra["id"], user_id, duelos_d=1)
        nueva_xp = jug["experiencia"] + XP_POR_DUELO_DERROTA
        nuevo_hp = max(1, jug["hp_actual"] - dano_rec)
        db_helper.actualizar_jugador(user_id, hp_actual=nuevo_hp, experiencia=nueva_xp)
        if rival.get("user_id"):
            db_helper.agregar_notificacion(rival["user_id"],
                f"🛡️ {jug['nombre_personaje']} te atacó en la guerra de gremios pero ganaste.")
        await update.effective_message.reply_text(
            f"⚔️ <b>{_he(jug['nombre_personaje'])}</b> vs <b>{_he(rival['nombre_personaje'])}</b>\n\n"
            f"❌ Derrota. Daño recibido: {dano_rec}\n"
            f"HP: {nuevo_hp}/{jug['hp_max']}\n"
            f"⭐ +{XP_POR_DUELO_DERROTA} XP por el intento",
            parse_mode="HTML"
        )
        # Notificar log de guerra a los miembros del propio gremio
        cn_d = sqlite3.connect(DB_PATH)
        cn_d.row_factory = sqlite3.Row
        cr_d = cn_d.cursor()
        cr_d.execute(
            "SELECT jugador_id FROM miembros_gremio WHERE gremio_id = ? AND jugador_id != ?",
            (gremio["id"], user_id)
        )
        for rd in cr_d.fetchall():
            db_helper.agregar_notificacion(rd["jugador_id"],
                f"⚔️ {jug['nombre_personaje']} perdió un duelo contra {rival['nombre_personaje']} "
                f"en la guerra de gremios.")
        cn_d.close()

async def cmd_guerra_gremios_rendirse(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Líder abandona la guerra (penalización)."""
    user_id = update.effective_user.id
    if not _en_ciudad(user_id):
        await update.effective_message.reply_text("🏙️ Las actividades de gremio solo están disponibles en ciudades.")
        return
    gremio = _obtener_gremio_de_jugador(user_id)
    if not gremio:
        await update.effective_message.reply_text("❌ No perteneces a ningún gremio.")
        return
    if not _es_lider(user_id, gremio["id"]):
        await update.effective_message.reply_text("Solo el líder puede rendir el gremio.")
        return

    guerra = _obtener_guerra_activa_gremio(gremio["id"])
    if not guerra or guerra["estado"] != "activa":
        await update.effective_message.reply_text("Tu gremio no está en una guerra activa.")
        return

    teclado = InlineKeyboardMarkup([[
        InlineKeyboardButton("⚠️ Sí, rendirse", callback_data=f"gg_rendirse_{guerra['id']}_{gremio['id']}"),
        InlineKeyboardButton("❌ Cancelar", callback_data="gg_cancelar")
    ]])
    await update.effective_message.reply_text(
        "⚠️ ¿Estás seguro de rendirte?\n"
        "Perderás el 10% de los puntos del gremio y el rival ganará.\n"
        "Esta acción no se puede deshacer.",
        reply_markup=teclado
    )

async def cmd_guerra_gremios_ranking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not _en_ciudad(user_id):
        await update.effective_message.reply_text("🏙️ Las actividades de gremio solo están disponibles en ciudades.")
        return
    gremio = _obtener_gremio_de_jugador(user_id)
    if not gremio:
        await update.effective_message.reply_text("❌ No perteneces a ningún gremio.")
        return

    guerra = _obtener_guerra_activa_gremio(gremio["id"])
    if not guerra:
        await update.effective_message.reply_text("Tu gremio no está en ninguna guerra activa.")
        return

    ga_id = guerra["gremio_atacante_id"]
    gd_id = guerra["gremio_defensor_id"]
    ga = _obtener_gremio(ga_id)
    gd = _obtener_gremio(gd_id)

    top_a = _obtener_top_participantes(guerra["id"], ga_id, 5)
    top_d = _obtener_top_participantes(guerra["id"], gd_id, 5)

    texto = f"🏆 <b>Ranking — Guerra #{guerra['id']}</b>\n\n"
    texto += f"🔴 <b>{_he(ga['nombre'])}</b> — {guerra['puntos_atacante']} pts\n"
    for i, p in enumerate(top_a):
        j = db_helper.obtener_jugador(p["user_id"])
        n = _he(j["nombre_personaje"]) if j else str(p["user_id"])
        texto += f"  #{i+1} {n}: {p['puntos_aportados']} pts ({p['victorias']}V/{p['duelos']}D)\n"

    texto += f"\n🔵 <b>{_he(gd['nombre'])}</b> — {guerra['puntos_defensor']} pts\n"
    for i, p in enumerate(top_d):
        j = db_helper.obtener_jugador(p["user_id"])
        n = _he(j["nombre_personaje"]) if j else str(p["user_id"])
        texto += f"  #{i+1} {n}: {p['puntos_aportados']} pts ({p['victorias']}V/{p['duelos']}D)\n"

    await update.effective_message.reply_text(texto, parse_mode="HTML")

# ==================== ADMIN ====================

async def cmd_admin_guerra_gremios_resolver(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin resuelve manualmente una guerra. /admin_guerra_gremios_resolver <guerra_id> <gremio_ganador_id>"""
    user_id = update.effective_user.id
    if not sa._es_admin(user_id):
        await update.effective_message.reply_text("❌ Sin permiso.")
        return
    if len(context.args) < 2:
        await update.effective_message.reply_text("Uso: /admin_guerra_gremios_resolver <guerra_id> <gremio_ganador_id>")
        return
    try:
        guerra_id = int(context.args[0])
        ganador_id = int(context.args[1])
    except ValueError:
        await update.effective_message.reply_text("Valores inválidos.")
        return
    guerra = _obtener_guerra_por_id(guerra_id)
    if not guerra:
        await update.effective_message.reply_text("Guerra no encontrada.")
        return
    if ganador_id not in (guerra["gremio_atacante_id"], guerra["gremio_defensor_id"]):
        await update.effective_message.reply_text("El gremio ganador debe ser uno de los participantes.")
        return
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE guerras_gremios SET estado = 'finalizada' WHERE id = ?", (guerra_id,))
    conn.commit()
    conn.close()
    ganador = _obtener_gremio(ganador_id)
    perdedor_id = guerra["gremio_defensor_id"] if ganador_id == guerra["gremio_atacante_id"] else guerra["gremio_atacante_id"]
    perdedor = _obtener_gremio(perdedor_id)

    # Premiar ganadores
    top = _obtener_top_participantes(guerra_id, ganador_id, 3)
    _gg_recomp = {}
    for i, p in enumerate(top):
        bonus = [3000, 1500, 750][i]
        xp = [600, 300, 150][i]
        economia.modificar_saldo(p["user_id"], "oro", bonus, "premio_guerra_gremios")
        jug = db_helper.obtener_jugador(p["user_id"])
        if jug:
            db_helper.actualizar_jugador(p["user_id"], experiencia=jug["experiencia"] + xp)
        db_helper.agregar_notificacion(p["user_id"],
            f"🏆 Tu gremio {ganador['nombre']} ganó la guerra. +{bonus} oro, +{xp} XP (posición #{i+1}).")
        _gg_recomp[p["user_id"]] = {"xp": xp, "oro": bonus}

    await update.effective_message.reply_text(
        f"✅ Guerra #{guerra_id} resuelta.\n"
        f"🏆 Ganador: <b>{_he(ganador['nombre'])}</b>\n"
        f"💀 Perdedor: <b>{_he(perdedor['nombre'])}</b>\n"
        f"Recompensas distribuidas al top 3.",
        parse_mode="HTML"
    )

    try:
        _top_all = _obtener_top_participantes(guerra_id, ganador_id, 10)
        _gan_pp = []
        for _p in _top_all:
            _j = db_helper.obtener_jugador(_p["user_id"])
            _r = _gg_recomp.get(_p["user_id"], {})
            _gan_pp.append({
                "user_id": _p["user_id"],
                "nombre": _j["nombre_personaje"] if _j else str(_p["user_id"]),
                "score": _p["puntos_aportados"],
                "xp": _r.get("xp", 0),
                "oro": _r.get("oro", 0),
            })
        await sa.notificar_admin_victoria(
            context.bot,
            "guerra_gremios",
            f"Guerra Gremios #{guerra_id}: {ganador['nombre']} venció a {perdedor['nombre']}",
            _gan_pp
        )
    except Exception:
        pass

# ==================== CALLBACKS ====================
async def cb_gg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    data = query.data

    if data == "gg_cancelar":
        await query.edit_message_text("❌ Acción cancelada.")
        return

    if data.startswith("gg_aceptar_"):
        try:
            guerra_id = int(data.split("_")[-1])
        except (ValueError, IndexError):
            await query.answer("❌ Error de datos.", show_alert=True)
            return
        update.message = query.message
        context.args = [str(guerra_id)]
        await cmd_guerra_gremios_aceptar(update, context)
    elif data.startswith("gg_aprobar_"):
        try:
            guerra_id = int(data.split("_")[-1])
        except (ValueError, IndexError):
            await query.answer("❌ Error de datos.", show_alert=True)
            return
        import os
        superadmin_id = os.environ.get("SUPERADMIN_ID")
        if superadmin_id and user_id == int(superadmin_id):
            guerra = _obtener_guerra_por_id(guerra_id)
            if not guerra or guerra["estado"] != "esperando_superadmin":
                await query.edit_message_text("⚠️ Esta guerra ya no está pendiente de aprobación.")
                return
            fecha_fin = datetime.now() + timedelta(hours=DURACION_GUERRA_HORAS)
            conn2 = sqlite3.connect(DB_PATH)
            c2 = conn2.cursor()
            c2.execute(
                "UPDATE guerras_gremios SET estado='activa', fecha_inicio=?, fecha_fin=? WHERE id=?",
                (datetime.now().isoformat(), fecha_fin.isoformat(), guerra_id)
            )
            conn2.commit()
            conn2.close()
            g_atac = _obtener_gremio(guerra["gremio_atacante_id"])
            g_def  = _obtener_gremio(guerra["gremio_defensor_id"])
            await query.edit_message_text(
                f"✅ <b>¡GUERRA APROBADA!</b>\n\n"
                f"🔴 {_he(g_atac['nombre'])} vs 🔵 {_he(g_def['nombre'])}\n"
                f"La guerra ya está activa. ¡Que comience el combate!",
                parse_mode="HTML"
            )
            # Notificar a ambos gremios
            for gid in (guerra["gremio_atacante_id"], guerra["gremio_defensor_id"]):
                cn = sqlite3.connect(DB_PATH)
                cn.row_factory = sqlite3.Row
                cr = cn.cursor()
                cr.execute("SELECT jugador_id FROM miembros_gremio WHERE gremio_id = ?", (gid,))
                for r in cr.fetchall():
                    db_helper.agregar_notificacion(r["jugador_id"],
                        f"⚔️ La guerra entre {g_atac['nombre']} y {g_def['nombre']} ha sido aprobada y ya está ACTIVA.\n"
                        f"Usa /guerra_gremios_duelo para combatir.")
                cn.close()
        else:
            await query.answer("⛔ No tienes permiso para aprobar guerras.", show_alert=True)
    elif data.startswith("gg_rechazar_admin_"):
        try:
            guerra_id = int(data.split("_")[-1])
        except (ValueError, IndexError):
            await query.answer("❌ Error de datos.", show_alert=True)
            return
        import os
        superadmin_id = os.environ.get("SUPERADMIN_ID")
        if superadmin_id and user_id == int(superadmin_id):
            conn2 = sqlite3.connect(DB_PATH)
            c2 = conn2.cursor()
            c2.execute("UPDATE guerras_gremios SET estado='rechazada' WHERE id=?", (guerra_id,))
            conn2.commit()
            conn2.close()
            await query.edit_message_text(f"❌ Guerra #{guerra_id} rechazada por el administrador.")
        else:
            await query.answer("⛔ No tienes permiso.", show_alert=True)
    elif data.startswith("gg_rechazar_"):
        try:
            guerra_id = int(data.split("_")[-1])
        except (ValueError, IndexError):
            await query.answer("❌ Error de datos.", show_alert=True)
            return
        update.message = query.message
        context.args = [str(guerra_id)]
        await cmd_guerra_gremios_rechazar(update, context)
    elif data.startswith("gg_rendirse_"):
        parts = data.split("_")
        try:
            guerra_id = int(parts[2])
            gremio_id = int(parts[3])
        except (ValueError, IndexError):
            await query.answer("❌ Error de datos.", show_alert=True)
            return
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("UPDATE guerras_gremios SET estado = 'finalizada' WHERE id = ?", (guerra_id,))
        conn.commit()
        conn.close()
        gremio = _obtener_gremio(gremio_id)
        await query.edit_message_text(
            f"🏳️ El gremio <b>{_he(gremio['nombre'])}</b> se ha rendido.\n"
            f"La guerra #{guerra_id} ha terminado.",
            parse_mode="HTML"
        )
        guerra_info = _obtener_guerra_por_id(guerra_id)
        if guerra_info:
            rival_gid = (guerra_info["gremio_defensor_id"]
                         if gremio_id == guerra_info["gremio_atacante_id"]
                         else guerra_info["gremio_atacante_id"])
            gremio_rival_obj = _obtener_gremio(rival_gid)
            nombre_rival_r = gremio_rival_obj["nombre"] if gremio_rival_obj else "el gremio rival"
            # Notificar al gremio rival (ganadores)
            cn_r = sqlite3.connect(DB_PATH)
            cn_r.row_factory = sqlite3.Row
            cr_r = cn_r.cursor()
            cr_r.execute("SELECT jugador_id FROM miembros_gremio WHERE gremio_id = ?", (rival_gid,))
            for rv in cr_r.fetchall():
                db_helper.agregar_notificacion(rv["jugador_id"],
                    f"🏆 ¡Victoria! El gremio {gremio['nombre']} se rindió. "
                    f"¡{nombre_rival_r} gana la guerra #{guerra_id}!")
            cn_r.close()
            # Notificar a los miembros del gremio que se rinde
            cn_p = sqlite3.connect(DB_PATH)
            cn_p.row_factory = sqlite3.Row
            cr_p = cn_p.cursor()
            cr_p.execute("SELECT jugador_id FROM miembros_gremio WHERE gremio_id = ?", (gremio_id,))
            for rv in cr_p.fetchall():
                db_helper.agregar_notificacion(rv["jugador_id"],
                    f"🏳️ Tu gremio {gremio['nombre']} se rindió en la guerra #{guerra_id}. "
                    f"El gremio {nombre_rival_r} ha ganado.")
            cn_p.close()

# ==================== REGISTRO DE HANDLERS ====================
def registrar_handlers(app):
    app.add_handler(CommandHandler("guerra_gremios_declarar",  cmd_guerra_gremios_declarar))
    app.add_handler(CommandHandler("solicitar_guerra",         cmd_guerra_gremios_declarar))
    app.add_handler(CommandHandler("guerra_gremios_aceptar",   cmd_guerra_gremios_aceptar))
    app.add_handler(CommandHandler("guerra_gremios_rechazar",  cmd_guerra_gremios_rechazar))
    app.add_handler(CommandHandler("guerra_gremios_estado",    cmd_guerra_gremios_estado))
    app.add_handler(CommandHandler("guerra_gremios_duelo",     cmd_guerra_gremios_duelo))
    app.add_handler(CommandHandler("guerra_gremios_rendirse",  cmd_guerra_gremios_rendirse))
    app.add_handler(CommandHandler("guerra_gremios_ranking",   cmd_guerra_gremios_ranking))
    app.add_handler(CommandHandler("admin_guerra_gremios_resolver", cmd_admin_guerra_gremios_resolver))
    app.add_handler(CallbackQueryHandler(cb_gg, pattern=r"^gg_"))

"""
simulaciones.py — Panel de Simulación para Superadmin.

Permite al superadmin probar todas las mecánicas del juego al instante,
simular resultados, forzar eventos y detectar bugs en todos los sistemas.

Acceso: solo superadmin (nivel 99).
Comando: /simulaciones
Callbacks: sim_*
"""

import sqlite3
import random
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler

import db_helper
import economia

DB_PATH = "aethelgard.db"

# ── Helpers ───────────────────────────────────────────────────────────────────

def _es_superadmin(user_id: int) -> bool:
    import os
    try:
        return str(user_id) == str(os.environ.get("SUPERADMIN_ID", ""))
    except Exception:
        return False


def _he(text: str) -> str:
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _menu_principal() -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton("⚔️ PvP Mortal",          callback_data="sim_cat_pvp"),
         InlineKeyboardButton("🏰 Jefes de Zona",        callback_data="sim_cat_jefes")],
        [InlineKeyboardButton("🔥 Guerra de Facciones",  callback_data="sim_cat_guerra"),
         InlineKeyboardButton("🌀 Guerra de Gremios",    callback_data="sim_cat_ggremios")],
        [InlineKeyboardButton("🌑 Noche del Vacío",      callback_data="sim_cat_umbral"),
         InlineKeyboardButton("🗡️ Caza de Asesinos",    callback_data="sim_cat_caza")],
        [InlineKeyboardButton("🛡️ PvE / Mazmorras",     callback_data="sim_cat_pve"),
         InlineKeyboardButton("🐛 Estado del sistema",   callback_data="sim_cat_bugs")],
        [InlineKeyboardButton("❌ Cerrar", callback_data="sim_cerrar")],
    ]
    return InlineKeyboardMarkup(kb)


def _btn_volver() -> list:
    return [InlineKeyboardButton("◀️ Menú simulaciones", callback_data="sim_volver")]


# ── Comando principal ─────────────────────────────────────────────────────────

async def cmd_simulaciones(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not _es_superadmin(user_id):
        await update.effective_message.reply_text("❌ Solo el superadmin puede usar este panel.")
        return
    await update.effective_message.reply_text(
        "🎮 <b>Panel de Simulaciones — Aethelgard</b>\n\n"
        "Selecciona el sistema que quieres simular o inspeccionar.\n"
        "Todas las acciones están sincronizadas con el juego real.",
        reply_markup=_menu_principal(),
        parse_mode="HTML"
    )


async def sim_volver(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not _es_superadmin(update.effective_user.id):
        return
    try:
        await query.edit_message_text(
            "🎮 <b>Panel de Simulaciones — Aethelgard</b>\n\n"
            "Selecciona el sistema que quieres simular o inspeccionar.",
            reply_markup=_menu_principal(),
            parse_mode="HTML"
        )
    except Exception:
        pass


async def sim_cerrar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        await query.edit_message_text("🎮 Panel de simulaciones cerrado.")
    except Exception:
        pass


# ── Categoría: PvP Mortal ─────────────────────────────────────────────────────

async def sim_cat_pvp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not _es_superadmin(update.effective_user.id):
        return
    # Listar PvP pendientes activos en user_data
    app = context.application
    pendientes = []
    for uid, udata in app.user_data.items():
        p = udata.get("pvpm_pendiente") or udata.get("pvp_negra_pendiente")
        if p:
            oponente = p.get("oponente_id", "?")
            color    = p.get("color", "?")
            ts       = p.get("timestamp", "")
            pendientes.append((uid, oponente, color, ts))

    texto = "⚔️ <b>Simulación — PvP Mortal</b>\n\n"
    if pendientes:
        texto += f"<b>Combates PvP pendientes ({len(pendientes)}):</b>\n"
        for uid, op, col, ts in pendientes:
            jug  = db_helper.obtener_jugador(uid)
            jug2 = db_helper.obtener_jugador(op)
            n1 = jug.get("nombre_personaje", str(uid)) if jug else str(uid)
            n2 = jug2.get("nombre_personaje", str(op)) if jug2 else str(op)
            texto += f"• {_he(n1)} → {_he(n2)} [{col}] {ts[:19]}\n"
    else:
        texto += "No hay combates PvP pendientes ahora mismo.\n"

    texto += "\n<b>Acciones disponibles:</b>"
    kb = [
        [InlineKeyboardButton("🎲 Simular resultado (atk gana)",   callback_data="sim_pvp_forzar_atk")],
        [InlineKeyboardButton("🎲 Simular resultado (def gana)",   callback_data="sim_pvp_forzar_def")],
        [InlineKeyboardButton("📊 Estadísticas PvP globales",      callback_data="sim_pvp_stats")],
        _btn_volver()
    ]
    try:
        await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
    except Exception:
        pass


async def sim_pvp_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        # Jugadores en zonas PvP
        c.execute("SELECT zona_actual, COUNT(*) FROM jugadores WHERE zona_actual_id IS NOT NULL GROUP BY zona_actual")
        zonas = c.fetchall()
        # Total combates si hay tabla historial
        try:
            c.execute("SELECT COUNT(*) FROM combates_historial WHERE tipo LIKE 'pvp%'")
            total_pvp = c.fetchone()[0]
        except Exception:
            total_pvp = "N/A"
        conn.close()

        texto = "📊 <b>Estadísticas PvP</b>\n\n"
        texto += "<b>Jugadores por zona:</b>\n"
        for zona, cnt in zonas:
            texto += f"  • {_he(str(zona))}: {cnt} jugadores\n"
        texto += f"\n<b>Combates PvP históricos:</b> {total_pvp}"
    except Exception as e:
        texto = f"❌ Error obteniendo estadísticas: {_he(str(e))}"
    kb = [_btn_volver()]
    try:
        await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
    except Exception:
        pass


async def sim_pvp_forzar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fuerza el resultado de todos los PvP pendientes."""
    query = update.callback_query
    await query.answer()
    if not _es_superadmin(update.effective_user.id):
        return
    ganador_rol = "atk" if "atk" in query.data else "def"
    app = context.application
    cancelados = 0
    for uid, udata in list(app.user_data.items()):
        for key in ("pvpm_pendiente", "pvp_negra_pendiente"):
            p = udata.pop(key, None)
            if p:
                cancelados += 1
                oponente = p.get("oponente_id")
                color    = p.get("color", "negra")
                # Aplicar penalizaciones
                try:
                    from combate import _aplicar_perdidas_y_transferir
                    from pvp_mortal import _get_combate_tipo
                    tipo = _get_combate_tipo(color)
                    if ganador_rol == "atk":
                        _aplicar_perdidas_y_transferir(oponente, uid, tipo)
                        ganador_id, perdedor_id = uid, oponente
                    else:
                        _aplicar_perdidas_y_transferir(uid, oponente, tipo)
                        ganador_id, perdedor_id = oponente, uid
                    jg = db_helper.obtener_jugador(ganador_id)
                    jp = db_helper.obtener_jugador(perdedor_id)
                    ng = jg.get("nombre_personaje","?") if jg else "?"
                    np = jp.get("nombre_personaje","?") if jp else "?"
                    try:
                        await context.bot.send_message(ganador_id, f"🏆 [SIM] Ganaste el combate PvP vs {_he(np)}.")
                    except Exception:
                        pass
                    try:
                        await context.bot.send_message(perdedor_id, f"💀 [SIM] Perdiste el combate PvP vs {_he(ng)}.")
                    except Exception:
                        pass
                except Exception:
                    pass
    kb = [_btn_volver()]
    try:
        await query.edit_message_text(
            f"✅ Se resolvieron <b>{cancelados}</b> combates PvP pendientes.\n"
            f"Ganador: <b>{'atacante' if ganador_rol=='atk' else 'defensor'}</b>",
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="HTML"
        )
    except Exception:
        pass


# ── Categoría: Jefes de Zona ──────────────────────────────────────────────────

async def sim_cat_jefes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not _es_superadmin(update.effective_user.id):
        return
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM jefes_activos WHERE estado != 'terminado' ORDER BY id DESC LIMIT 5")
        jefes = [dict(r) for r in c.fetchall()]
        conn.close()
    except Exception:
        jefes = []

    texto = "🏰 <b>Simulación — Jefes de Zona</b>\n\n"
    if jefes:
        for j in jefes:
            pct = int((j.get("hp_actual", 0) / max(j.get("hp_max", 1), 1)) * 100)
            texto += (f"• <b>{_he(j.get('nombre','?'))}</b> — "
                      f"HP: {j.get('hp_actual','?')}/{j.get('hp_max','?')} ({pct}%) "
                      f"[{j.get('dificultad','?')}] Estado: {j.get('estado','?')}\n")
    else:
        texto += "No hay jefes activos ahora mismo.\n"
    texto += "\n<b>Acciones:</b>"

    kb = [
        [InlineKeyboardButton("⚡ Matar jefe activo al instante",   callback_data="sim_jefe_matar")],
        [InlineKeyboardButton("📊 Estadísticas de participantes",   callback_data="sim_jefe_stats")],
        [InlineKeyboardButton("🗡️ Simular 1 ataque masivo (todos)", callback_data="sim_jefe_atacar")],
        _btn_volver()
    ]
    try:
        await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
    except Exception:
        pass


async def sim_jefe_matar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not _es_superadmin(update.effective_user.id):
        return
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT id, nombre FROM jefes_activos WHERE estado != 'terminado' ORDER BY id DESC LIMIT 1")
        row = c.fetchone()
        if not row:
            conn.close()
            await query.edit_message_text("No hay jefe activo.", reply_markup=InlineKeyboardMarkup([_btn_volver()]), parse_mode="HTML")
            return
        jefe_id, nombre = row
        # Bajar HP a 0 y marcar como terminado
        c.execute("UPDATE jefes_activos SET hp_actual = 0, estado = 'terminado' WHERE id = ?", (jefe_id,))
        conn.commit()
        conn.close()
        texto = f"⚡ Jefe <b>{_he(nombre)}</b> eliminado al instante (HP → 0).\nLas recompensas se distribuirán cuando el sistema las procese."
    except Exception as e:
        texto = f"❌ Error: {_he(str(e))}"
    kb = [_btn_volver()]
    try:
        await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
    except Exception:
        pass


async def sim_jefe_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM jefes_activos WHERE estado != 'terminado' ORDER BY id DESC LIMIT 1")
        jefe = c.fetchone()
        if not jefe:
            conn.close()
            await query.edit_message_text("No hay jefe activo.", reply_markup=InlineKeyboardMarkup([_btn_volver()]), parse_mode="HTML")
            return
        j = dict(jefe)
        # Participantes
        try:
            c.execute("SELECT user_id, danio_total FROM participantes_jefe WHERE jefe_id = ? ORDER BY danio_total DESC", (j["id"],))
            parts = c.fetchall()
        except Exception:
            parts = []
        conn.close()
        texto = f"📊 <b>Jefe: {_he(j.get('nombre','?'))}</b>\n"
        texto += f"HP: {j.get('hp_actual','?')}/{j.get('hp_max','?')}\n"
        texto += f"Dificultad: {j.get('dificultad','?')} | Estado: {j.get('estado','?')}\n\n"
        if parts:
            texto += f"<b>Participantes ({len(parts)}):</b>\n"
            for row in parts[:10]:
                uid = row[0] if isinstance(row, tuple) else row["user_id"]
                dmg = row[1] if isinstance(row, tuple) else row["danio_total"]
                jug = db_helper.obtener_jugador(uid)
                nombre = jug.get("nombre_personaje", str(uid)) if jug else str(uid)
                texto += f"  • {_he(nombre)}: {dmg} daño\n"
        else:
            texto += "Sin participantes registrados."
    except Exception as e:
        texto = f"❌ Error: {_he(str(e))}"
    kb = [_btn_volver()]
    try:
        await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
    except Exception:
        pass


async def sim_jefe_atacar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Simula un ataque masivo de todos los participantes sobre el jefe activo."""
    query = update.callback_query
    await query.answer()
    if not _es_superadmin(update.effective_user.id):
        return
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT id, nombre, hp_actual, hp_max FROM jefes_activos WHERE estado != 'terminado' ORDER BY id DESC LIMIT 1")
        row = c.fetchone()
        if not row:
            conn.close()
            await query.edit_message_text("No hay jefe activo.", reply_markup=InlineKeyboardMarkup([_btn_volver()]), parse_mode="HTML")
            return
        jefe_id, nombre, hp_actual, hp_max = row
        # Daño simulado: 20-30% del HP máximo
        dmg = int(hp_max * random.uniform(0.20, 0.30))
        nuevo_hp = max(0, hp_actual - dmg)
        c.execute("UPDATE jefes_activos SET hp_actual = ? WHERE id = ?", (nuevo_hp, jefe_id))
        if nuevo_hp == 0:
            c.execute("UPDATE jefes_activos SET estado = 'terminado' WHERE id = ?", (jefe_id,))
        conn.commit()
        conn.close()
        pct = int((nuevo_hp / max(hp_max, 1)) * 100)
        estado = "¡Derrotado!" if nuevo_hp == 0 else f"HP restante: {nuevo_hp}/{hp_max} ({pct}%)"
        texto = (f"🗡️ Ataque masivo simulado sobre <b>{_he(nombre)}</b>.\n"
                 f"Daño infligido: <b>{dmg}</b>\n{estado}")
    except Exception as e:
        texto = f"❌ Error: {_he(str(e))}"
    kb = [_btn_volver()]
    try:
        await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
    except Exception:
        pass


# ── Categoría: Guerra de Facciones ───────────────────────────────────────────

async def sim_cat_guerra(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not _es_superadmin(update.effective_user.id):
        return
    try:
        from guerra_facciones import _obtener_guerra_activa
        guerra = _obtener_guerra_activa()
    except Exception:
        guerra = None

    texto = "🔥 <b>Simulación — Guerra de Facciones</b>\n\n"
    if guerra:
        texto += (f"<b>Guerra activa:</b> {_he(guerra.get('faccion1','?'))} vs {_he(guerra.get('faccion2','?'))}\n"
                  f"Puntos: {guerra.get('puntos_f1',0)} — {guerra.get('puntos_f2',0)}\n"
                  f"Estado: {guerra.get('estado','?')}\n")
    else:
        texto += "No hay guerra de facciones activa.\n"
    texto += "\n<b>Acciones:</b>"

    kb = [
        [InlineKeyboardButton("🚀 Iniciar guerra de prueba (10 min)",   callback_data="sim_gf_iniciar")],
        [InlineKeyboardButton("⚡ Simular 10 ataques aleatorios",        callback_data="sim_gf_atacar")],
        [InlineKeyboardButton("🏁 Finalizar guerra activa al instante",  callback_data="sim_gf_finalizar")],
        [InlineKeyboardButton("📊 Estado completo de la guerra",         callback_data="sim_gf_estado")],
        _btn_volver()
    ]
    try:
        await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
    except Exception:
        pass


async def sim_gf_iniciar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not _es_superadmin(update.effective_user.id):
        return
    try:
        # Obtener las dos facciones principales
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT nombre FROM facciones ORDER BY id LIMIT 2")
        facs = [r[0] for r in c.fetchall()]
        conn.close()
        if len(facs) < 2:
            facs = ["Facción 1", "Facción 2"]
        from guerra_facciones import _obtener_guerra_activa
        if _obtener_guerra_activa():
            texto = "Ya hay una guerra activa. Finalizala primero."
        else:
            conn2 = sqlite3.connect(DB_PATH)
            c2 = conn2.cursor()
            fin = "datetime('now', '+10 minutes')"
            c2.execute(
                f"INSERT INTO guerras_facciones (faccion1, faccion2, puntos_f1, puntos_f2, estado, inicio, fin) "
                f"VALUES (?, ?, 0, 0, 'activa', datetime('now'), {fin})",
                (facs[0], facs[1])
            )
            conn2.commit()
            conn2.close()
            texto = f"🚀 Guerra iniciada: <b>{_he(facs[0])}</b> vs <b>{_he(facs[1])}</b> (10 minutos)"
    except Exception as e:
        texto = f"❌ Error: {_he(str(e))}"
    kb = [_btn_volver()]
    try:
        await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
    except Exception:
        pass


async def sim_gf_atacar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Simula 10 ataques aleatorios en la guerra activa."""
    query = update.callback_query
    await query.answer()
    if not _es_superadmin(update.effective_user.id):
        return
    try:
        from guerra_facciones import _obtener_guerra_activa
        guerra = _obtener_guerra_activa()
        if not guerra:
            await query.edit_message_text("No hay guerra activa.", reply_markup=InlineKeyboardMarkup([_btn_volver()]), parse_mode="HTML")
            return
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        puntos_f1 = guerra.get("puntos_f1", 0)
        puntos_f2 = guerra.get("puntos_f2", 0)
        for _ in range(10):
            if random.random() < 0.5:
                puntos_f1 += random.randint(5, 25)
            else:
                puntos_f2 += random.randint(5, 25)
        c.execute("UPDATE guerras_facciones SET puntos_f1 = ?, puntos_f2 = ? WHERE id = ?",
                  (puntos_f1, puntos_f2, guerra["id"]))
        conn.commit()
        conn.close()
        texto = (f"🎲 10 ataques simulados.\n\n"
                 f"<b>{_he(guerra.get('faccion1','?'))}:</b> {puntos_f1} pts\n"
                 f"<b>{_he(guerra.get('faccion2','?'))}:</b> {puntos_f2} pts")
    except Exception as e:
        texto = f"❌ Error: {_he(str(e))}"
    kb = [_btn_volver()]
    try:
        await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
    except Exception:
        pass


async def sim_gf_finalizar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not _es_superadmin(update.effective_user.id):
        return
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT id, faccion1, faccion2, puntos_f1, puntos_f2 FROM guerras_facciones WHERE estado='activa' ORDER BY id DESC LIMIT 1")
        row = c.fetchone()
        if not row:
            conn.close()
            texto = "⚠️ No hay guerra de facciones activa para finalizar."
        else:
            gid, f1, f2, p1, p2 = row
            ganadora = f1 if p1 >= p2 else f2
            c.execute("UPDATE guerras_facciones SET estado='terminada' WHERE id=?", (gid,))
            conn.commit()
            conn.close()
            texto = (f"🏁 <b>Guerra finalizada.</b>\n\n"
                     f"<b>{_he(f1)}</b>: {p1} pts\n"
                     f"<b>{_he(f2)}</b>: {p2} pts\n\n"
                     f"🏆 Ganadora: <b>{_he(ganadora)}</b>")
    except Exception as e:
        texto = f"❌ Error: {_he(str(e))}"
    kb = [_btn_volver()]
    try:
        await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
    except Exception:
        pass


async def sim_gf_estado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        from guerra_facciones import _obtener_guerra_activa
        guerra = _obtener_guerra_activa()
        if not guerra:
            texto = "⚠️ No hay guerra de facciones activa ahora mismo."
        else:
            f1 = guerra.get("faccion1", "?")
            f2 = guerra.get("faccion2", "?")
            p1 = guerra.get("puntos_f1", 0)
            p2 = guerra.get("puntos_f2", 0)
            estado = guerra.get("estado", "?")
            fin = guerra.get("fin", "?")
            texto = (f"📊 <b>Estado — Guerra de Facciones</b>\n\n"
                     f"<b>{_he(f1)}</b>: {p1} pts\n"
                     f"<b>{_he(f2)}</b>: {p2} pts\n"
                     f"Estado: {_he(estado)}\n"
                     f"Fin programado: {_he(str(fin))}")
    except Exception as e:
        texto = f"❌ Error: {_he(str(e))}"
    kb = [_btn_volver()]
    try:
        await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
    except Exception:
        pass


# ── Categoría: Guerra de Gremios ──────────────────────────────────────────────

async def sim_cat_ggremios(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not _es_superadmin(update.effective_user.id):
        return
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM guerras_gremios WHERE estado = 'activa'")
        activas = c.fetchone()[0]
        conn.close()
    except Exception:
        activas = "?"
    texto = (f"🌀 <b>Simulación — Guerra de Gremios</b>\n\n"
             f"Guerras de gremios activas: <b>{activas}</b>\n\n"
             "<b>Acciones:</b>")
    kb = [
        [InlineKeyboardButton("🏁 Resolver todas las guerras activas", callback_data="sim_gg_resolver")],
        [InlineKeyboardButton("📊 Ver guerras activas",                callback_data="sim_gg_estado")],
        _btn_volver()
    ]
    try:
        await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
    except Exception:
        pass


async def sim_gg_resolver(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not _es_superadmin(update.effective_user.id):
        return
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM guerras_gremios WHERE estado = 'activa'")
        cnt = c.fetchone()[0]
        c.execute("UPDATE guerras_gremios SET estado = 'terminada' WHERE estado = 'activa'")
        conn.commit()
        conn.close()
        texto = f"✅ {cnt} guerra(s) de gremios marcadas como terminadas."
    except Exception as e:
        texto = f"❌ Error: {_he(str(e))}"
    kb = [_btn_volver()]
    try:
        await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
    except Exception:
        pass


async def sim_gg_estado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM guerras_gremios WHERE estado = 'activa' LIMIT 5")
        rows = [dict(r) for r in c.fetchall()]
        conn.close()
        if not rows:
            texto = "🌀 No hay guerras de gremios activas."
        else:
            texto = f"🌀 <b>Guerras de gremios activas ({len(rows)}):</b>\n\n"
            for r in rows:
                texto += (f"• <b>{_he(r.get('gremio1_nombre','?'))}</b> vs "
                          f"<b>{_he(r.get('gremio2_nombre','?'))}</b> — "
                          f"Duelos: {r.get('duelos_g1',0)}-{r.get('duelos_g2',0)}\n")
    except Exception as e:
        texto = f"❌ Error: {_he(str(e))}"
    kb = [_btn_volver()]
    try:
        await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
    except Exception:
        pass


# ── Categoría: Noche del Vacío (Umbral) ──────────────────────────────────────

def _umbral_get(c, clave: str, default: str = "") -> str:
    """Lee una clave de umbral_config directamente."""
    try:
        c.execute("SELECT valor FROM umbral_config WHERE clave=?", (clave,))
        row = c.fetchone()
        return row[0] if row else default
    except Exception:
        return default


async def sim_cat_umbral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not _es_superadmin(update.effective_user.id):
        return
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        estado   = _umbral_get(c, "estado", "normal")
        corr     = _umbral_get(c, "corrupcion", "0")
        mon_hp   = _umbral_get(c, "monstruo_actual_hp", "0")
        mon_hpmax= _umbral_get(c, "monstruo_actual_hp_max", "0")
        conn.close()
    except Exception:
        estado, corr, mon_hp, mon_hpmax = "?", "?", "0", "0"

    texto = "🌑 <b>Simulación — Noche del Vacío (Umbral)</b>\n\n"
    texto += f"Estado actual: <b>{_he(estado)}</b>\n"
    texto += f"Corrupción: <b>{corr}%</b>\n"
    if estado != "normal":
        texto += f"HP Monstruo: <b>{mon_hp}/{mon_hpmax}</b>\n"
    texto += "\n<b>Acciones:</b>"

    kb = [
        [InlineKeyboardButton("🌑 Activar Noche del Vacío",     callback_data="sim_umbral_activar")],
        [InlineKeyboardButton("☀️ Resetear a estado Normal",    callback_data="sim_umbral_avanzar")],
        [InlineKeyboardButton("📊 Ver estado completo",         callback_data="sim_umbral_estado")],
        _btn_volver()
    ]
    try:
        await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
    except Exception:
        pass


async def sim_umbral_activar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Activa la Noche del Vacío directamente vía SQL."""
    query = update.callback_query
    await query.answer()
    if not _es_superadmin(update.effective_user.id):
        return
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        estado = _umbral_get(c, "estado", "normal")
        if estado != "normal":
            conn.close()
            texto = f"⚠️ El Umbral ya está activo (estado: <b>{_he(estado)}</b>).\nUsa 'Resetear a Normal' primero."
        else:
            # Activar: poner estado noche_vacio con monstruo básico
            import random as _rnd
            hp = 3000
            facciones = ["fuego", "agua", "tierra", "viento"]
            faccion = _rnd.choice(facciones)
            c.execute("INSERT OR REPLACE INTO umbral_config (clave, valor) VALUES ('estado', 'noche_vacio')")
            c.execute("INSERT OR REPLACE INTO umbral_config (clave, valor) VALUES ('monstruo_actual_faccion', ?)", (faccion,))
            c.execute("INSERT OR REPLACE INTO umbral_config (clave, valor) VALUES ('monstruo_actual_hp', ?)", (str(hp),))
            c.execute("INSERT OR REPLACE INTO umbral_config (clave, valor) VALUES ('monstruo_actual_hp_max', ?)", (str(hp),))
            conn.commit()
            conn.close()
            texto = (f"🌑 <b>Noche del Vacío activada.</b>\n\n"
                     f"Monstruo de facción <b>{_he(faccion)}</b> invocado (HP: {hp}).\n"
                     f"Los jugadores ya pueden atacarlo con /umbral_atacar.")
    except Exception as e:
        texto = f"❌ Error al activar el Umbral: {_he(str(e))}"
    kb = [_btn_volver()]
    try:
        await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
    except Exception:
        pass


async def sim_umbral_avanzar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Resetea el Umbral a estado normal directamente vía SQL."""
    query = update.callback_query
    await query.answer()
    if not _es_superadmin(update.effective_user.id):
        return
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        estado = _umbral_get(c, "estado", "normal")
        if estado == "normal":
            conn.close()
            texto = "☀️ El Umbral ya está en estado <b>Normal</b>. No hay nada que resetear."
        else:
            c.execute("INSERT OR REPLACE INTO umbral_config (clave, valor) VALUES ('estado', 'normal')")
            c.execute("INSERT OR REPLACE INTO umbral_config (clave, valor) VALUES ('monstruo_actual_hp', '0')")
            c.execute("INSERT OR REPLACE INTO umbral_config (clave, valor) VALUES ('monstruo_actual_hp_max', '0')")
            c.execute("INSERT OR REPLACE INTO umbral_config (clave, valor) VALUES ('jefe_hp', '0')")
            c.execute("INSERT OR REPLACE INTO umbral_config (clave, valor) VALUES ('jefe_hp_max', '0')")
            conn.commit()
            conn.close()
            texto = f"☀️ Umbral reseteado a <b>Normal</b> (era: {_he(estado)})."
    except Exception as e:
        texto = f"❌ Error al resetear el Umbral: {_he(str(e))}"
    kb = [_btn_volver()]
    try:
        await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
    except Exception:
        pass


async def sim_umbral_estado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra el estado completo del Umbral leyendo umbral_config."""
    query = update.callback_query
    await query.answer()
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        estado    = _umbral_get(c, "estado", "normal")
        corr      = _umbral_get(c, "corrupcion", "0")
        mon_hp    = _umbral_get(c, "monstruo_actual_hp", "0")
        mon_hpmax = _umbral_get(c, "monstruo_actual_hp_max", "0")
        mon_fac   = _umbral_get(c, "monstruo_actual_faccion", "—")
        jefe_hp   = _umbral_get(c, "jefe_hp", "0")
        jefe_hpmax= _umbral_get(c, "jefe_hp_max", "0")
        ronda_fin = _umbral_get(c, "ronda_fin_en", "—")
        conn.close()
        texto = (f"📊 <b>Estado Umbral del Vacío</b>\n\n"
                 f"Estado: <b>{_he(estado)}</b>\n"
                 f"Corrupción: <b>{corr}%</b>\n"
                 f"Monstruo HP: {mon_hp}/{mon_hpmax} (facción: {_he(mon_fac)})\n"
                 f"Jefe HP: {jefe_hp}/{jefe_hpmax}\n"
                 f"Fin de ronda: {_he(ronda_fin)}")
    except Exception as e:
        texto = f"❌ Error: {_he(str(e))}"
    kb = [_btn_volver()]
    try:
        await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
    except Exception:
        pass


# ── Categoría: Caza de Asesinos ───────────────────────────────────────────────

async def _render_caza_panel(query) -> None:
    """Renderiza el panel de caza de asesinos sobre un query ya respondido."""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT user_id, nombre_personaje, faccion FROM jugadores WHERE estado_marcado = 1 LIMIT 20")
        marcados = c.fetchall()
        conn.close()
    except Exception:
        marcados = []

    texto = "🗡️ <b>Simulación — Caza de Asesinos</b>\n\n"
    if marcados:
        texto += f"<b>Jugadores marcados ({len(marcados)}):</b>\n"
        for uid, nombre, fac in marcados:
            texto += f"  • {_he(nombre)} [{_he(fac or '?')}] (ID: {uid})\n"
    else:
        texto += "No hay jugadores marcados actualmente.\n"

    texto += "\n<b>Acciones:</b>"
    kb = [
        [InlineKeyboardButton("🗡️ Cómo marcar jugadores",          callback_data="sim_caza_marcar")],
        [InlineKeyboardButton("✅ Desmarcar todos",                  callback_data="sim_caza_desmarcar_todos")],
        [InlineKeyboardButton("🔄 Actualizar lista",                 callback_data="sim_caza_ver")],
        _btn_volver()
    ]
    try:
        await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
    except Exception:
        pass


async def sim_cat_caza(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not _es_superadmin(update.effective_user.id):
        await query.answer("⛔ Sin acceso.", show_alert=True)
        return
    await query.answer()
    await _render_caza_panel(query)


async def sim_caza_desmarcar_todos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not _es_superadmin(update.effective_user.id):
        await query.answer("⛔ Sin acceso.", show_alert=True)
        return
    await query.answer()
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("UPDATE jugadores SET estado_marcado = 0, marca_expiracion = NULL WHERE estado_marcado = 1")
        cnt = c.rowcount
        conn.commit()
        conn.close()
        texto = f"✅ {cnt} jugador(es) desmarcado(s) correctamente."
    except Exception as e:
        texto = f"❌ Error al desmarcar: {_he(str(e))}"
    kb = [[InlineKeyboardButton("🔄 Ver lista", callback_data="sim_caza_ver")], _btn_volver()]
    try:
        await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
    except Exception:
        pass


async def sim_caza_ver(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Actualizar vista del panel de caza."""
    query = update.callback_query
    await query.answer()
    if not _es_superadmin(update.effective_user.id):
        return
    await _render_caza_panel(query)


async def sim_caza_marcar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        await query.edit_message_text(
            "Para marcar a un jugador usa el comando:\n<code>/marcar_jugador &lt;user_id&gt;</code>\n"
            "o desde el panel de superadmin con el ID del jugador.",
            reply_markup=InlineKeyboardMarkup([_btn_volver()]),
            parse_mode="HTML"
        )
    except Exception:
        pass


# ── Categoría: PvE / Mazmorras ────────────────────────────────────────────────

async def sim_cat_pve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not _es_superadmin(update.effective_user.id):
        return
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM jugadores")
        total = c.fetchone()[0]
        c.execute("SELECT zona_actual, COUNT(*) as cnt FROM jugadores GROUP BY zona_actual ORDER BY cnt DESC LIMIT 8")
        zonas = c.fetchall()
        conn.close()
    except Exception:
        total, zonas = 0, []

    texto = f"🛡️ <b>Simulación — PvE / Mazmorras</b>\n\nJugadores registrados: <b>{total}</b>\n\n"
    if zonas:
        texto += "<b>Distribución por zona:</b>\n"
        for zona, cnt in zonas:
            texto += f"  • {_he(str(zona or 'Ciudad'))}: {cnt}\n"

    kb = [
        [InlineKeyboardButton("🎲 Dar 500 oro a todos los online",    callback_data="sim_pve_oro_todos")],
        [InlineKeyboardButton("⚡ Dar 1000 XP a todos los online",    callback_data="sim_pve_xp_todos")],
        [InlineKeyboardButton("📊 Ver jugadores en mazmorras",        callback_data="sim_pve_mazmorras")],
        _btn_volver()
    ]
    try:
        await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
    except Exception:
        pass


async def sim_pve_oro_todos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not _es_superadmin(update.effective_user.id):
        return
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        hace_10 = "datetime('now', '-10 minutes')"
        try:
            c.execute(f"SELECT user_id FROM jugadores WHERE ultimo_acceso >= {hace_10}")
            uids = [r[0] for r in c.fetchall()]
        except Exception:
            c.execute("SELECT user_id FROM jugadores LIMIT 20")
            uids = [r[0] for r in c.fetchall()]
        conn.close()
        for uid in uids:
            economia.modificar_saldo(uid, "oro", 500, "simulación PvE — regalo superadmin")
        texto = f"✅ 500 oro entregados a <b>{len(uids)}</b> jugadores."
    except Exception as e:
        texto = f"❌ Error: {_he(str(e))}"
    kb = [_btn_volver()]
    try:
        await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
    except Exception:
        pass


async def sim_pve_xp_todos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not _es_superadmin(update.effective_user.id):
        return
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        hace_10 = "datetime('now', '-10 minutes')"
        try:
            c.execute(f"SELECT user_id FROM jugadores WHERE ultimo_acceso >= {hace_10}")
            uids = [r[0] for r in c.fetchall()]
        except Exception:
            c.execute("SELECT user_id FROM jugadores LIMIT 20")
            uids = [r[0] for r in c.fetchall()]
        conn.close()
        for uid in uids:
            try:
                db_helper.dar_xp(uid, 1000)
            except Exception:
                pass
        texto = f"✅ 1000 XP entregados a <b>{len(uids)}</b> jugadores."
    except Exception as e:
        texto = f"❌ Error: {_he(str(e))}"
    kb = [_btn_volver()]
    try:
        await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
    except Exception:
        pass


async def sim_pve_mazmorras(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM combates_activos")
        activos = c.fetchone()[0]
        conn.close()
        texto = f"🏰 Combates de mazmorra activos: <b>{activos}</b>"
    except Exception:
        texto = "🏰 No hay datos de combates activos de mazmorra."
    kb = [_btn_volver()]
    try:
        await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
    except Exception:
        pass


# ── Categoría: Estado del Sistema / Bugs ─────────────────────────────────────

async def sim_cat_bugs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not _es_superadmin(update.effective_user.id):
        return
    import json, os
    pendientes = []
    resueltos  = []
    ruta = "reportes_queue.jsonl"
    try:
        if os.path.exists(ruta):
            with open(ruta) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    r = json.loads(line)
                    if r.get("done"):
                        resueltos.append(r)
                    else:
                        pendientes.append(r)
    except Exception:
        pass

    texto = "🐛 <b>Estado del Sistema — Detección de Bugs</b>\n\n"
    texto += f"Reportes pendientes: <b>{len(pendientes)}</b>\n"
    texto += f"Reportes resueltos:  <b>{len(resueltos)}</b>\n\n"

    if pendientes:
        texto += "<b>Últimos reportes pendientes:</b>\n"
        for r in pendientes[-5:]:
            ts  = r.get("ts", "?")
            msg = r.get("msg", "")[:80]
            texto += f"• [{ts}] {_he(msg)}...\n"

    # Estado de módulos en memoria
    app = context.application
    pvp_activos = sum(1 for ud in app.user_data.values() if ud.get("pvpm_pendiente") or ud.get("pvp_negra_pendiente"))
    texto += f"\n<b>Estado en memoria:</b>\n• PvP pendientes: {pvp_activos}"

    kb = [
        [InlineKeyboardButton("📋 Ver todos los reportes pendientes",  callback_data="sim_bugs_ver")],
        [InlineKeyboardButton("✅ Marcar todos como resueltos",        callback_data="sim_bugs_limpiar")],
        [InlineKeyboardButton("🔄 Recargar estado del bot",           callback_data="sim_bugs_estado")],
        _btn_volver()
    ]
    try:
        await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
    except Exception:
        pass


async def sim_bugs_ver(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    import json, os
    try:
        ruta = "reportes_queue.jsonl"
        pendientes = []
        if os.path.exists(ruta):
            with open(ruta) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    r = json.loads(line)
                    if not r.get("done"):
                        pendientes.append(r)
        if not pendientes:
            texto = "✅ No hay reportes pendientes."
        else:
            texto = f"📋 <b>Reportes pendientes ({len(pendientes)}):</b>\n\n"
            for r in pendientes:
                ts  = r.get("ts", "?")
                msg = r.get("msg", "")[:120]
                texto += f"[{ts}]\n{_he(msg)}\n\n"
    except Exception as e:
        texto = f"❌ Error: {_he(str(e))}"
    kb = [_btn_volver()]
    try:
        await query.edit_message_text(texto[:4000], reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
    except Exception:
        pass


async def sim_bugs_limpiar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not _es_superadmin(update.effective_user.id):
        return
    import json, os
    try:
        ruta = "reportes_queue.jsonl"
        lines = []
        with open(ruta) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                r = json.loads(line)
                r["done"] = True
                lines.append(json.dumps(r, ensure_ascii=False))
        with open(ruta, "w") as f:
            f.write("\n".join(lines) + "\n")
        texto = f"✅ {len(lines)} reportes marcados como resueltos."
    except Exception as e:
        texto = f"❌ Error: {_he(str(e))}"
    kb = [_btn_volver()]
    try:
        await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
    except Exception:
        pass


async def sim_bugs_estado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    app = context.application
    try:
        ud_total = len(app.user_data)
        pvp = sum(1 for ud in app.user_data.values() if ud.get("pvpm_pendiente") or ud.get("pvp_negra_pendiente"))
        multi = sum(1 for ud in app.user_data.values() if ud.get("pvp_multi_ultimo"))
        texto = (f"🔄 <b>Estado en memoria del bot:</b>\n\n"
                 f"• Sesiones de usuario activas: <b>{ud_total}</b>\n"
                 f"• PvP pendientes de respuesta: <b>{pvp}</b>\n"
                 f"• Usuarios con cooldown multizonal: <b>{multi}</b>\n")
        # DB size
        import os
        if os.path.exists(DB_PATH):
            size_kb = os.path.getsize(DB_PATH) // 1024
            texto += f"• Tamaño de la base de datos: <b>{size_kb} KB</b>\n"
    except Exception as e:
        texto = f"❌ Error: {_he(str(e))}"
    kb = [_btn_volver()]
    try:
        await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
    except Exception:
        pass


# ── Registro de handlers ──────────────────────────────────────────────────────

def registrar_handlers(app):
    app.add_handler(CommandHandler("simulaciones", cmd_simulaciones))
    # Navegación
    app.add_handler(CallbackQueryHandler(sim_volver,  pattern="^sim_volver$"))
    app.add_handler(CallbackQueryHandler(sim_cerrar,  pattern="^sim_cerrar$"))
    # Categorías
    app.add_handler(CallbackQueryHandler(sim_cat_pvp,     pattern="^sim_cat_pvp$"))
    app.add_handler(CallbackQueryHandler(sim_cat_jefes,   pattern="^sim_cat_jefes$"))
    app.add_handler(CallbackQueryHandler(sim_cat_guerra,  pattern="^sim_cat_guerra$"))
    app.add_handler(CallbackQueryHandler(sim_cat_ggremios,pattern="^sim_cat_ggremios$"))
    app.add_handler(CallbackQueryHandler(sim_cat_umbral,  pattern="^sim_cat_umbral$"))
    app.add_handler(CallbackQueryHandler(sim_cat_caza,    pattern="^sim_cat_caza$"))
    app.add_handler(CallbackQueryHandler(sim_cat_pve,     pattern="^sim_cat_pve$"))
    app.add_handler(CallbackQueryHandler(sim_cat_bugs,    pattern="^sim_cat_bugs$"))
    # PvP
    app.add_handler(CallbackQueryHandler(sim_pvp_stats,   pattern="^sim_pvp_stats$"))
    app.add_handler(CallbackQueryHandler(sim_pvp_forzar,  pattern="^sim_pvp_forzar_"))
    # Jefes
    app.add_handler(CallbackQueryHandler(sim_jefe_matar,  pattern="^sim_jefe_matar$"))
    app.add_handler(CallbackQueryHandler(sim_jefe_stats,  pattern="^sim_jefe_stats$"))
    app.add_handler(CallbackQueryHandler(sim_jefe_atacar, pattern="^sim_jefe_atacar$"))
    # Guerra facciones
    app.add_handler(CallbackQueryHandler(sim_gf_iniciar,   pattern="^sim_gf_iniciar$"))
    app.add_handler(CallbackQueryHandler(sim_gf_atacar,    pattern="^sim_gf_atacar$"))
    app.add_handler(CallbackQueryHandler(sim_gf_finalizar, pattern="^sim_gf_finalizar$"))
    app.add_handler(CallbackQueryHandler(sim_gf_estado,    pattern="^sim_gf_estado$"))
    # Guerra gremios
    app.add_handler(CallbackQueryHandler(sim_gg_resolver,  pattern="^sim_gg_resolver$"))
    app.add_handler(CallbackQueryHandler(sim_gg_estado,    pattern="^sim_gg_estado$"))
    # Umbral
    app.add_handler(CallbackQueryHandler(sim_umbral_activar, pattern="^sim_umbral_activar$"))
    app.add_handler(CallbackQueryHandler(sim_umbral_avanzar, pattern="^sim_umbral_avanzar$"))
    app.add_handler(CallbackQueryHandler(sim_umbral_estado,  pattern="^sim_umbral_estado$"))
    # Caza
    app.add_handler(CallbackQueryHandler(sim_caza_desmarcar_todos, pattern="^sim_caza_desmarcar_todos$"))
    app.add_handler(CallbackQueryHandler(sim_caza_ver,     pattern="^sim_caza_ver$"))
    app.add_handler(CallbackQueryHandler(sim_caza_marcar,  pattern="^sim_caza_marcar$"))
    # PvE
    app.add_handler(CallbackQueryHandler(sim_pve_oro_todos,  pattern="^sim_pve_oro_todos$"))
    app.add_handler(CallbackQueryHandler(sim_pve_xp_todos,   pattern="^sim_pve_xp_todos$"))
    app.add_handler(CallbackQueryHandler(sim_pve_mazmorras,  pattern="^sim_pve_mazmorras$"))
    # Bugs
    app.add_handler(CallbackQueryHandler(sim_bugs_ver,     pattern="^sim_bugs_ver$"))
    app.add_handler(CallbackQueryHandler(sim_bugs_limpiar, pattern="^sim_bugs_limpiar$"))
    app.add_handler(CallbackQueryHandler(sim_bugs_estado,  pattern="^sim_bugs_estado$"))

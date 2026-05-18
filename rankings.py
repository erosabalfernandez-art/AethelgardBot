#!/usr/bin/env python3
# rankings.py — Sistema de rankings de Aethelgard
#
# Rankings disponibles (solo accesibles en ciudades):
#   1. 🗡️  Monstruos matados esta semana
#   2. ☠️  Jugadores eliminados (PvP acumulado)
#   3. 🔥  Daño en guerras de facciones
#   4. 🏆  Más logros desbloqueados
#   5. ⚔️  Gremios más poderosos (guerras de gremios)
#   6. 🌐  Facciones más poderosas (guerras de facciones)
#   7. 💥  Daño personal total (opt-in)
#
# Comandos de jugador:
#   /rankings            — Menú principal de rankings
#   /ranking_dano_opt    — Activar/desactivar participación en ranking de daño
#
# Comandos admin:
#   /admin_ranking_reset_semana          — Reiniciar contador semanal de monstruos
#   /admin_ranking_reset_dano            — Reiniciar acumuladores de daño personal
#   /admin_ranking_opt_forzar <uid> <0|1>— Forzar opt-in/out de un jugador

import sqlite3
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler

import db_helper
import superadmin as sa

DB_PATH = "aethelgard.db"
MEDALLAS = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
TOP_N = 10

# ── Config del módulo (clave/valor en tabla rankings_config) ───────────────────
def _rk_get(clave: str, default: str = "") -> str:
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("CREATE TABLE IF NOT EXISTS rankings_config (clave TEXT PRIMARY KEY, valor TEXT)")
        c.execute("SELECT valor FROM rankings_config WHERE clave = ?", (clave,))
        row = c.fetchone()
        conn.close()
        return row[0] if row else default
    except Exception:
        return default

def _rk_set(clave: str, valor) -> None:
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("CREATE TABLE IF NOT EXISTS rankings_config (clave TEXT PRIMARY KEY, valor TEXT)")
        conn.execute(
            "INSERT INTO rankings_config (clave, valor) VALUES (?, ?) "
            "ON CONFLICT(clave) DO UPDATE SET valor = excluded.valor",
            (clave, str(valor))
        )
        conn.commit()
        conn.close()
    except Exception:
        pass

def _dias_modo() -> int:
    """Retorna los días del período de reset según el modo configurado."""
    modo = _rk_get("reset_modo", "semanal")
    return {"semanal": 7, "mensual": 30}.get(modo, 0)  # 0 = nunca auto

# ==================== INIT DB ====================
def _init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    migraciones = [
        "ALTER TABLE stats_jugadores ADD COLUMN monstruos_semana INTEGER DEFAULT 0",
        "ALTER TABLE stats_jugadores ADD COLUMN monstruos_total  INTEGER DEFAULT 0",
        "ALTER TABLE stats_jugadores ADD COLUMN semana_inicio_kills TEXT DEFAULT NULL",
        "ALTER TABLE stats_jugadores ADD COLUMN opt_in_ranking_dano INTEGER DEFAULT 0",
        "ALTER TABLE stats_jugadores ADD COLUMN dano_personal_total INTEGER DEFAULT 0",
    ]
    for sql in migraciones:
        try:
            c.execute(sql)
        except Exception:
            pass
    conn.commit()
    conn.close()

_init_db()

# ==================== HELPERS ====================
def _en_ciudad(user_id: int) -> bool:
    try:
        import datos_zona as _dz
        zona_nombre = db_helper.obtener_zona_actual(user_id)
        return any(z["nombre"] == zona_nombre and z["tipo"] == "ciudad" for z in _dz.ZONAS)
    except Exception:
        return False

def _nombre_jugador(user_id: int) -> str:
    jug = db_helper.obtener_jugador(user_id)
    return jug["nombre_personaje"] if jug else f"Jugador {user_id}"

def _reset_semana_si_necesario(user_id: int):
    """Reinicia monstruos_semana si ha pasado el período configurado."""
    dias = _dias_modo()
    if dias == 0:
        return  # modo "nunca" — no auto-reset
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT semana_inicio_kills FROM stats_jugadores WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    if row and row[0]:
        try:
            inicio = datetime.fromisoformat(row[0])
            if datetime.now() - inicio > timedelta(days=dias):
                c.execute(
                    "UPDATE stats_jugadores SET monstruos_semana = 0, semana_inicio_kills = ? WHERE user_id = ?",
                    (datetime.now().isoformat(), user_id)
                )
                conn.commit()
        except Exception:
            pass
    conn.close()

def _asegurar_row_stats(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO stats_jugadores (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()

# ==================== REGISTRO DE KILLS ====================
def registrar_kill_monstruo(user_id: int, cantidad: int = 1):
    """Llamar desde combate.py cada vez que un monstruo muere."""
    try:
        _asegurar_row_stats(user_id)
        _reset_semana_si_necesario(user_id)
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(
            "SELECT semana_inicio_kills FROM stats_jugadores WHERE user_id = ?", (user_id,)
        )
        row = c.fetchone()
        inicio = row[0] if row and row[0] else datetime.now().isoformat()
        c.execute(
            "UPDATE stats_jugadores SET monstruos_semana = monstruos_semana + ?, "
            "monstruos_total = monstruos_total + ?, semana_inicio_kills = COALESCE(semana_inicio_kills, ?) "
            "WHERE user_id = ?",
            (cantidad, cantidad, inicio, user_id)
        )
        conn.commit()
        conn.close()
    except Exception:
        pass

def registrar_dano_guerra(user_id: int, dano: int):
    """Llamar desde guerras cuando un jugador causa daño (si tiene opt-in)."""
    try:
        _asegurar_row_stats(user_id)
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(
            "UPDATE stats_jugadores SET dano_personal_total = dano_personal_total + ? WHERE user_id = ?",
            (dano, user_id)
        )
        conn.commit()
        conn.close()
    except Exception:
        pass

# ==================== QUERIES DE RANKINGS ====================
def _get_ranking_monstruos_semana() -> List[Tuple[int, int]]:
    """Retorna [(user_id, kills)] top-10 del período activo."""
    dias = _dias_modo()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if dias > 0:
        c.execute(
            "UPDATE stats_jugadores SET monstruos_semana = 0 "
            "WHERE semana_inicio_kills IS NOT NULL "
            "AND (julianday('now') - julianday(semana_inicio_kills)) > ?",
            (dias,)
        )
    c.execute(
        "SELECT user_id, monstruos_semana FROM stats_jugadores "
        "WHERE monstruos_semana > 0 ORDER BY monstruos_semana DESC LIMIT ?",
        (TOP_N,)
    )
    rows = c.fetchall()
    conn.commit()
    conn.close()
    return rows

def _get_ranking_pvp() -> List[Tuple[int, int]]:
    """Retorna [(user_id, kills_pvp)] top-10 por asesinatos totales."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT user_id, "
        "COALESCE(asesinatos_amarilla,0) + COALESCE(asesinatos_roja,0) + COALESCE(asesinatos_negra,0) AS total_pvp "
        "FROM jugadores WHERE total_pvp > 0 ORDER BY total_pvp DESC LIMIT ?",
        (TOP_N,)
    )
    rows = c.fetchall()
    conn.close()
    return rows

def _get_ranking_dano_facciones() -> List[Tuple[int, int]]:
    """Retorna [(user_id, puntos_aportados)] top-10 de guerras de facciones."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT user_id, SUM(puntos_aportados) as total "
        "FROM guerras_facciones_participantes "
        "GROUP BY user_id HAVING total > 0 ORDER BY total DESC LIMIT ?",
        (TOP_N,)
    )
    rows = c.fetchall()
    conn.close()
    return rows

def _get_ranking_logros() -> List[Tuple[int, int]]:
    """Retorna [(user_id, num_logros)] top-10 por logros desbloqueados."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT user_id, COUNT(*) as total FROM logros_desbloqueados_v2 "
        "GROUP BY user_id ORDER BY total DESC LIMIT ?",
        (TOP_N,)
    )
    rows = c.fetchall()
    conn.close()
    return rows

def _get_ranking_gremios() -> List[Tuple[int, str, int]]:
    """Retorna [(gremio_id, nombre, puntos)] top-10 de guerras de gremios."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT p.gremio_id, g.nombre, SUM(p.puntos_aportados) as total "
        "FROM guerras_gremios_participantes p "
        "JOIN gremios g ON g.id = p.gremio_id "
        "GROUP BY p.gremio_id HAVING total > 0 ORDER BY total DESC LIMIT ?",
        (TOP_N,)
    )
    rows = c.fetchall()
    conn.close()
    return rows

def _get_ranking_facciones() -> List[Tuple[str, int]]:
    """Retorna [(faccion, puntos_totales)] para el ranking de facciones."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT faccion1, SUM(puntos_f1) FROM guerras_facciones GROUP BY faccion1"
    )
    datos: Dict[str, int] = {}
    for faccion, pts in (c.fetchall() or []):
        datos[faccion] = datos.get(faccion, 0) + (pts or 0)
    c.execute(
        "SELECT faccion2, SUM(puntos_f2) FROM guerras_facciones GROUP BY faccion2"
    )
    for faccion, pts in (c.fetchall() or []):
        datos[faccion] = datos.get(faccion, 0) + (pts or 0)
    c.execute(
        "SELECT faccion3, SUM(puntos_f3) FROM guerras_facciones WHERE faccion3 IS NOT NULL GROUP BY faccion3"
    )
    for faccion, pts in (c.fetchall() or []):
        if faccion:
            datos[faccion] = datos.get(faccion, 0) + (pts or 0)
    conn.close()
    ordenado = sorted(datos.items(), key=lambda x: x[1], reverse=True)
    return ordenado[:TOP_N]

def _get_ranking_dano_personal() -> List[Tuple[int, int]]:
    """Retorna [(user_id, dano)] top-10 solo de jugadores opt-in."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT user_id, dano_personal_total FROM stats_jugadores "
        "WHERE opt_in_ranking_dano = 1 AND dano_personal_total > 0 "
        "ORDER BY dano_personal_total DESC LIMIT ?",
        (TOP_N,)
    )
    rows = c.fetchall()
    conn.close()
    return rows

def _total_participantes_dano() -> int:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM stats_jugadores WHERE opt_in_ranking_dano = 1")
    n = c.fetchone()[0] or 0
    conn.close()
    return n

def _get_opt_in(user_id: int) -> bool:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT opt_in_ranking_dano FROM stats_jugadores WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return bool(row[0]) if row else False

def _set_opt_in(user_id: int, valor: bool):
    _asegurar_row_stats(user_id)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "UPDATE stats_jugadores SET opt_in_ranking_dano = ? WHERE user_id = ?",
        (1 if valor else 0, user_id)
    )
    conn.commit()
    conn.close()

# ==================== FORMATEO ====================
def _medalla(pos: int) -> str:
    return MEDALLAS[pos] if pos < len(MEDALLAS) else f"{pos+1}."

def _formatear_top_jugadores(rows: List[Tuple[int, int]], unidad: str = "") -> str:
    if not rows:
        return "  <i>Sin datos todavía.</i>"
    lines = []
    for i, (uid, valor) in enumerate(rows):
        nombre = _nombre_jugador(uid)
        lines.append(f"  {_medalla(i)} <b>{nombre}</b> — {valor:,}{(' '+unidad) if unidad else ''}")
    return "\n".join(lines)

def _formatear_top_gremios(rows: List[Tuple[int, str, int]]) -> str:
    if not rows:
        return "  <i>Sin datos todavía.</i>"
    lines = []
    for i, (_, nombre, pts) in enumerate(rows):
        lines.append(f"  {_medalla(i)} <b>{nombre}</b> — {pts:,} pts")
    return "\n".join(lines)

def _formatear_top_facciones(rows: List[Tuple[str, int]]) -> str:
    if not rows:
        return "  <i>Sin datos todavía.</i>"
    lines = []
    for i, (faccion, pts) in enumerate(rows):
        lines.append(f"  {_medalla(i)} <b>{faccion}</b> — {pts:,} pts")
    return "\n".join(lines)

# ==================== TECLADO PRINCIPAL ====================
def _kb_rankings_principal() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🗡️ Monstruos (semana)",     callback_data="rk_monstruos")],
        [InlineKeyboardButton("☠️ Asesinos PvP",            callback_data="rk_pvp")],
        [InlineKeyboardButton("🔥 Daño en facciones",       callback_data="rk_dano_faccion")],
        [InlineKeyboardButton("🏆 Más logros",              callback_data="rk_logros")],
        [InlineKeyboardButton("⚔️ Gremios (guerra)",        callback_data="rk_gremios"),
         InlineKeyboardButton("🌐 Facciones",               callback_data="rk_facciones")],
        [InlineKeyboardButton("💥 Daño personal (opt-in)",  callback_data="rk_dano_personal")],
        [InlineKeyboardButton("❌ Cerrar",                   callback_data="rk_cerrar")],
    ])

def _kb_volver() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver", callback_data="rk_menu")]])

def _kb_opt() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Activar mi participación",   callback_data="rk_opt_in"),
         InlineKeyboardButton("❌ Desactivar",                callback_data="rk_opt_out")],
        [InlineKeyboardButton("🔙 Volver",                    callback_data="rk_menu")],
    ])

# ==================== TEXTOS DE CADA RANKING ====================
def _texto_monstruos() -> str:
    rows = _get_ranking_monstruos_semana()
    modo = _rk_get("reset_modo", "semanal")
    notas = {"semanal": "Contador se reinicia automáticamente cada 7 días.",
              "mensual": "Contador se reinicia automáticamente cada 30 días.",
              "nunca":   "Sin reinicio automático — solo reinicio manual por el admin."}
    nota = notas.get(modo, "")
    return (
        "🗡️ <b>RANKING — Monstruos Matados</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        + _formatear_top_jugadores(rows, "kills") +
        f"\n\n<i>{nota}</i>"
    )

def _texto_pvp() -> str:
    rows = _get_ranking_pvp()
    return (
        "☠️ <b>RANKING — Asesinos PvP</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        + _formatear_top_jugadores(rows, "bajas") +
        "\n\n<i>Total acumulado de jugadores eliminados en zonas PvP.</i>"
    )

def _texto_dano_faccion() -> str:
    rows = _get_ranking_dano_facciones()
    return (
        "🔥 <b>RANKING — Daño en Guerras de Facciones</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        + _formatear_top_jugadores(rows, "pts") +
        "\n\n<i>Puntos aportados acumulados en todas las guerras de facciones.</i>"
    )

def _texto_logros() -> str:
    rows = _get_ranking_logros()
    return (
        "🏆 <b>RANKING — Más Logros Desbloqueados</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        + _formatear_top_jugadores(rows, "logros") +
        "\n\n<i>Basado en el total de logros obtenidos.</i>"
    )

def _texto_gremios() -> str:
    rows = _get_ranking_gremios()
    return (
        "⚔️ <b>RANKING — Gremios Más Poderosos</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        + _formatear_top_gremios(rows) +
        "\n\n<i>Puntos acumulados en todas las guerras de gremios.</i>"
    )

def _texto_facciones() -> str:
    rows = _get_ranking_facciones()
    return (
        "🌐 <b>RANKING — Facciones Más Poderosas</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        + _formatear_top_facciones(rows) +
        "\n\n<i>Puntos totales acumulados en todas las guerras de facciones.</i>"
    )

def _texto_dano_personal(user_id: int) -> str:
    rows = _get_ranking_dano_personal()
    total_part = _total_participantes_dano()
    opt = _get_opt_in(user_id)
    estado = "✅ <b>Tu participación está ACTIVA</b>" if opt else "❌ <b>No participas en este ranking</b>"
    return (
        "💥 <b>RANKING — Daño Personal Total (Opt-In)</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        + _formatear_top_jugadores(rows, "pts") +
        f"\n\n👥 Participantes inscritos: {total_part}\n"
        f"{estado}\n\n"
        "<i>Activa tu participación para aparecer en el ranking.\n"
        "Registra el daño causado en guerras de facciones y gremios.</i>"
    )

# ==================== MENÚ PRINCIPAL ====================
async def cmd_rankings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not _en_ciudad(user_id):
        await update.effective_message.reply_text(
            "🏙️ Los rankings solo están disponibles en ciudades."
        )
        return
    await update.effective_message.reply_text(
        "🏆 <b>RANKINGS DE AETHELGARD</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Elige un ranking para ver la clasificación:",
        reply_markup=_kb_rankings_principal(),
        parse_mode="HTML"
    )

# ==================== CALLBACKS ====================
async def cb_rk_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    if not _en_ciudad(user_id):
        await query.edit_message_text("🏙️ Los rankings solo están disponibles en ciudades.")
        return
    await query.edit_message_text(
        "🏆 <b>RANKINGS DE AETHELGARD</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Elige un ranking para ver la clasificación:",
        reply_markup=_kb_rankings_principal(),
        parse_mode="HTML"
    )

async def cb_rk_monstruos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(_texto_monstruos(), reply_markup=_kb_volver(), parse_mode="HTML")

async def cb_rk_pvp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(_texto_pvp(), reply_markup=_kb_volver(), parse_mode="HTML")

async def cb_rk_dano_faccion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(_texto_dano_faccion(), reply_markup=_kb_volver(), parse_mode="HTML")

async def cb_rk_logros(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(_texto_logros(), reply_markup=_kb_volver(), parse_mode="HTML")

async def cb_rk_gremios(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(_texto_gremios(), reply_markup=_kb_volver(), parse_mode="HTML")

async def cb_rk_facciones(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(_texto_facciones(), reply_markup=_kb_volver(), parse_mode="HTML")

async def cb_rk_dano_personal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    await query.edit_message_text(
        _texto_dano_personal(user_id),
        reply_markup=_kb_opt(),
        parse_mode="HTML"
    )

async def cb_rk_opt_in(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("✅ Participación activada.")
    user_id = update.effective_user.id
    _set_opt_in(user_id, True)
    await query.edit_message_text(
        _texto_dano_personal(user_id),
        reply_markup=_kb_opt(),
        parse_mode="HTML"
    )

async def cb_rk_opt_out(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("❌ Participación desactivada.")
    user_id = update.effective_user.id
    _set_opt_in(user_id, False)
    await query.edit_message_text(
        _texto_dano_personal(user_id),
        reply_markup=_kb_opt(),
        parse_mode="HTML"
    )

async def cb_rk_cerrar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        await query.delete_message()
    except Exception:
        await query.edit_message_text("Rankings cerrados.")

# ==================== COMANDO JUGADOR: OPT-IN ====================
async def cmd_ranking_dano_opt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not _en_ciudad(user_id):
        await update.effective_message.reply_text("🏙️ Usa este comando desde una ciudad.")
        return
    opt = _get_opt_in(user_id)
    estado = "✅ activa" if opt else "❌ inactiva"
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Activar",   callback_data="rk_opt_in"),
         InlineKeyboardButton("❌ Desactivar", callback_data="rk_opt_out")],
    ])
    await update.effective_message.reply_text(
        f"💥 <b>Ranking de Daño Personal</b>\n\n"
        f"Tu participación está: {estado}\n\n"
        "Al activarla, tu daño acumulado en guerras aparecerá en el ranking público.",
        reply_markup=kb, parse_mode="HTML"
    )

# ==================== ADMIN COMMANDS ====================
async def cmd_admin_ranking_reset_semana(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not sa._es_admin(user_id):
        await update.effective_message.reply_text("❌ Sin permiso de administrador.")
        return
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "UPDATE stats_jugadores SET monstruos_semana = 0, semana_inicio_kills = ?",
        (datetime.now().isoformat(),)
    )
    afectados = conn.total_changes
    conn.commit()
    conn.close()
    await update.effective_message.reply_text(
        f"✅ Contador semanal de monstruos reiniciado.\n"
        f"Filas actualizadas: {afectados}"
    )

async def cmd_admin_ranking_reset_dano(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not sa._es_admin(user_id):
        await update.effective_message.reply_text("❌ Sin permiso de administrador.")
        return
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE stats_jugadores SET dano_personal_total = 0")
    afectados = conn.total_changes
    conn.commit()
    conn.close()
    await update.effective_message.reply_text(
        f"✅ Acumuladores de daño personal reiniciados.\n"
        f"Filas actualizadas: {afectados}"
    )

async def cmd_admin_ranking_opt_forzar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Uso: /admin_ranking_opt_forzar <user_id> <0|1>"""
    user_id = update.effective_user.id
    if not sa._es_admin(user_id):
        await update.effective_message.reply_text("❌ Sin permiso de administrador.")
        return
    if len(context.args) < 2:
        await update.effective_message.reply_text(
            "Uso: /admin_ranking_opt_forzar <user_id> <0|1>"
        )
        return
    try:
        target_id = int(context.args[0])
        valor = int(context.args[1])
        if valor not in (0, 1):
            raise ValueError
    except ValueError:
        await update.effective_message.reply_text("❌ Parámetros inválidos. Usa 0 o 1.")
        return
    _asegurar_row_stats(target_id)
    _set_opt_in(target_id, bool(valor))
    jug = db_helper.obtener_jugador(target_id)
    nombre = jug["nombre_personaje"] if jug else str(target_id)
    estado = "activado" if valor else "desactivado"
    await update.effective_message.reply_text(
        f"✅ Ranking de daño de <b>{nombre}</b> (ID:{target_id}) {estado}.",
        parse_mode="HTML"
    )

async def cmd_admin_ranking_ver_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra estadísticas generales de participación en rankings."""
    user_id = update.effective_user.id
    if not sa._es_admin(user_id):
        await update.effective_message.reply_text("❌ Sin permiso de administrador.")
        return
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM stats_jugadores WHERE monstruos_semana > 0")
    act_semana = c.fetchone()[0] or 0
    c.execute("SELECT SUM(monstruos_semana) FROM stats_jugadores")
    tot_mobs = c.fetchone()[0] or 0
    c.execute("SELECT COUNT(*) FROM stats_jugadores WHERE opt_in_ranking_dano = 1")
    opt_in_n = c.fetchone()[0] or 0
    c.execute("SELECT COUNT(*) FROM guerras_facciones_participantes")
    partic_gf = c.fetchone()[0] or 0
    c.execute("SELECT COUNT(*) FROM guerras_gremios_participantes")
    partic_gg = c.fetchone()[0] or 0
    conn.close()
    await update.effective_message.reply_text(
        "📊 <b>Estadísticas de Rankings</b>\n\n"
        f"🗡️ Jugadores activos esta semana: {act_semana}\n"
        f"🗡️ Total mobs matados (semana): {tot_mobs:,}\n"
        f"💥 Inscritos en ranking de daño: {opt_in_n}\n"
        f"🔥 Registros en guerras de facciones: {partic_gf:,}\n"
        f"⚔️ Registros en guerras de gremios: {partic_gg:,}",
        parse_mode="HTML"
    )

# ==================== PANEL ADMIN DE RANKINGS ====================

def _label_modo(modo: str) -> str:
    return {"semanal": "🔄 Semanal (7 días)", "mensual": "📅 Mensual (30 días)", "nunca": "🚫 Sin auto-reinicio"}.get(modo, modo)

def _proximo_reset_txt() -> str:
    modo = _rk_get("reset_modo", "semanal")
    dias = _dias_modo()
    if dias == 0:
        return "—"
    ultimo = _rk_get("ultimo_reset_kills", "")
    if not ultimo:
        return "No iniciado"
    try:
        dt = datetime.fromisoformat(ultimo) + timedelta(days=dias)
        return dt.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return "—"

def _texto_panel_admin_rk() -> str:
    modo = _rk_get("reset_modo", "semanal")
    ultimo_k = _rk_get("ultimo_reset_kills", "Nunca")
    ultimo_d = _rk_get("ultimo_reset_dano", "Nunca")
    proximo  = _proximo_reset_txt()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM stats_jugadores WHERE monstruos_semana > 0")
    activos = c.fetchone()[0] or 0
    c.execute("SELECT COUNT(*) FROM stats_jugadores WHERE opt_in_ranking_dano = 1")
    opt_in  = c.fetchone()[0] or 0
    conn.close()
    try:
        uk = datetime.fromisoformat(ultimo_k).strftime("%d/%m/%Y %H:%M")
    except Exception:
        uk = "Nunca"
    try:
        ud = datetime.fromisoformat(ultimo_d).strftime("%d/%m/%Y %H:%M")
    except Exception:
        ud = "Nunca"
    return (
        "📊 <b>Panel Admin — Rankings</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"⚙️ Modo de reinicio: <b>{_label_modo(modo)}</b>\n"
        f"⏰ Próximo reset kills: <b>{proximo}</b>\n\n"
        f"🗡️ Jugadores activos (kills): <b>{activos}</b>\n"
        f"💥 Inscritos en daño (opt-in): <b>{opt_in}</b>\n\n"
        f"🕐 Último reset kills: {uk}\n"
        f"🕐 Último reset daño: {ud}"
    )

def _kb_panel_admin_rk(modo: str) -> InlineKeyboardMarkup:
    def marca(m): return "✅ " if modo == m else ""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"{marca('semanal')}🔄 Semanal (7d)",  callback_data="rkadm_modo_semanal"),
         InlineKeyboardButton(f"{marca('mensual')}📅 Mensual (30d)", callback_data="rkadm_modo_mensual")],
        [InlineKeyboardButton(f"{marca('nunca')}🚫 Sin auto-reinicio", callback_data="rkadm_modo_nunca")],
        [InlineKeyboardButton("🗑️ Reiniciar kills ahora",  callback_data="rkadm_reset_kills"),
         InlineKeyboardButton("🗑️ Reiniciar daño ahora",   callback_data="rkadm_reset_dano")],
        [InlineKeyboardButton("🗑️ Reiniciar TODO ahora",   callback_data="rkadm_reset_todo")],
        [InlineKeyboardButton("📊 Stats detalladas",        callback_data="rkadm_stats"),
         InlineKeyboardButton("🔄 Actualizar",              callback_data="rkadm_refrescar")],
    ])

async def _mostrar_panel_admin_rk(update, context, editar: bool = False):
    modo  = _rk_get("reset_modo", "semanal")
    texto = _texto_panel_admin_rk()
    kb    = _kb_panel_admin_rk(modo)
    if editar and update.callback_query:
        try:
            await update.callback_query.edit_message_text(texto, parse_mode="HTML", reply_markup=kb)
            return
        except Exception:
            pass
    await update.effective_message.reply_text(texto, parse_mode="HTML", reply_markup=kb)

async def cmd_admin_rankings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/admin_rankings — Panel de control de rankings."""
    user_id = update.effective_user.id
    if not sa._es_admin(user_id):
        await update.effective_message.reply_text("⛔ Solo los administradores pueden usar /admin_rankings.")
        return
    await _mostrar_panel_admin_rk(update, context, editar=False)

async def cb_admin_rk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    user_id = update.effective_user.id
    if not sa._es_admin(user_id):
        await query.answer("⛔ Sin permiso.", show_alert=True)
        return
    data = query.data

    if data == "rkadm_refrescar":
        await query.answer("🔄 Panel actualizado.")
        await _mostrar_panel_admin_rk(update, context, editar=True)

    elif data == "rkadm_modo_semanal":
        _rk_set("reset_modo", "semanal")
        await query.answer("✅ Modo: Semanal (reinicio cada 7 días).", show_alert=True)
        await _mostrar_panel_admin_rk(update, context, editar=True)

    elif data == "rkadm_modo_mensual":
        _rk_set("reset_modo", "mensual")
        await query.answer("✅ Modo: Mensual (reinicio cada 30 días).", show_alert=True)
        await _mostrar_panel_admin_rk(update, context, editar=True)

    elif data == "rkadm_modo_nunca":
        _rk_set("reset_modo", "nunca")
        await query.answer("✅ Auto-reinicio desactivado. Solo manual.", show_alert=True)
        await _mostrar_panel_admin_rk(update, context, editar=True)

    elif data == "rkadm_reset_kills":
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("UPDATE stats_jugadores SET monstruos_semana = 0, semana_inicio_kills = ?",
                  (datetime.now().isoformat(),))
        afectados = conn.total_changes
        conn.commit()
        conn.close()
        _rk_set("ultimo_reset_kills", datetime.now().isoformat())
        await query.answer(f"✅ Kills reiniciadas ({afectados} jugadores).", show_alert=True)
        await _mostrar_panel_admin_rk(update, context, editar=True)

    elif data == "rkadm_reset_dano":
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("UPDATE stats_jugadores SET dano_personal_total = 0")
        afectados = conn.total_changes
        conn.commit()
        conn.close()
        _rk_set("ultimo_reset_dano", datetime.now().isoformat())
        await query.answer(f"✅ Daño personal reiniciado ({afectados} jugadores).", show_alert=True)
        await _mostrar_panel_admin_rk(update, context, editar=True)

    elif data == "rkadm_reset_todo":
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("UPDATE stats_jugadores SET monstruos_semana = 0, semana_inicio_kills = ?, dano_personal_total = 0",
                  (datetime.now().isoformat(),))
        afectados = conn.total_changes
        conn.commit()
        conn.close()
        ahora = datetime.now().isoformat()
        _rk_set("ultimo_reset_kills", ahora)
        _rk_set("ultimo_reset_dano", ahora)
        await query.answer(f"✅ Todos los contadores reiniciados ({afectados} jugadores).", show_alert=True)
        await _mostrar_panel_admin_rk(update, context, editar=True)

    elif data == "rkadm_stats":
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM stats_jugadores WHERE monstruos_semana > 0")
        act_s = c.fetchone()[0] or 0
        c.execute("SELECT SUM(monstruos_semana) FROM stats_jugadores")
        tot_k = c.fetchone()[0] or 0
        c.execute("SELECT COUNT(*) FROM stats_jugadores WHERE opt_in_ranking_dano = 1")
        opt_n = c.fetchone()[0] or 0
        c.execute("SELECT COUNT(*) FROM guerras_facciones_participantes")
        gf = c.fetchone()[0] or 0
        c.execute("SELECT COUNT(*) FROM guerras_gremios_participantes")
        gg = c.fetchone()[0] or 0
        conn.close()
        await query.answer()
        await update.effective_message.reply_text(
            "📊 <b>Estadísticas de Rankings</b>\n\n"
            f"🗡️ Jugadores activos (kills): {act_s}\n"
            f"🗡️ Total kills período actual: {tot_k:,}\n"
            f"💥 Inscritos en ranking daño: {opt_n}\n"
            f"🔥 Registros guerras facciones: {gf:,}\n"
            f"⚔️ Registros guerras gremios: {gg:,}",
            parse_mode="HTML"
        )

    else:
        await query.answer()


# ==================== REGISTRO DE HANDLERS ====================
def registrar_handlers(app):
    app.add_handler(CommandHandler("rankings",                       cmd_rankings))
    app.add_handler(CommandHandler("ranking_dano_opt",               cmd_ranking_dano_opt))
    app.add_handler(CommandHandler("admin_rankings",                 cmd_admin_rankings))
    app.add_handler(CommandHandler("admin_ranking_reset_semana",     cmd_admin_ranking_reset_semana))
    app.add_handler(CommandHandler("admin_ranking_reset_dano",       cmd_admin_ranking_reset_dano))
    app.add_handler(CommandHandler("admin_ranking_opt_forzar",       cmd_admin_ranking_opt_forzar))
    app.add_handler(CommandHandler("admin_ranking_stats",            cmd_admin_ranking_ver_stats))
    app.add_handler(CallbackQueryHandler(cb_admin_rk,            pattern=r"^rkadm_"))
    app.add_handler(CallbackQueryHandler(cb_rk_menu,             pattern=r"^rk_menu$"))
    app.add_handler(CallbackQueryHandler(cb_rk_monstruos,        pattern=r"^rk_monstruos$"))
    app.add_handler(CallbackQueryHandler(cb_rk_pvp,              pattern=r"^rk_pvp$"))
    app.add_handler(CallbackQueryHandler(cb_rk_dano_faccion,     pattern=r"^rk_dano_faccion$"))
    app.add_handler(CallbackQueryHandler(cb_rk_logros,           pattern=r"^rk_logros$"))
    app.add_handler(CallbackQueryHandler(cb_rk_gremios,          pattern=r"^rk_gremios$"))
    app.add_handler(CallbackQueryHandler(cb_rk_facciones,        pattern=r"^rk_facciones$"))
    app.add_handler(CallbackQueryHandler(cb_rk_dano_personal,    pattern=r"^rk_dano_personal$"))
    app.add_handler(CallbackQueryHandler(cb_rk_opt_in,           pattern=r"^rk_opt_in$"))
    app.add_handler(CallbackQueryHandler(cb_rk_opt_out,          pattern=r"^rk_opt_out$"))
    app.add_handler(CallbackQueryHandler(cb_rk_cerrar,           pattern=r"^rk_cerrar$"))

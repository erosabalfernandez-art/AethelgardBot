#!/usr/bin/env python3
# guerra_facciones.py — Guerra de Facciones (10 min, 1 acción/jugador, botón persistente)
#
# Flujo:
#   Admin activa la guerra → broadcast a TODOS los jugadores con botón persistente
#   Cada jugador puede atacar O defender UNA sola vez (elige facción objetivo)
#   A los 10 min (configurable) el bot calcula resultados automáticamente
#   Se anuncian 1er, 2do, 3er lugar y el botón de todos desaparece

import sqlite3
import random
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, List

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters

import db_helper
import economia
import superadmin as sa

DB_PATH = "aethelgard.db"

def _esc_md(s: str) -> str:
    return str(s).replace("_", "\\_").replace("*", "\\*").replace("`", "\\`").replace("[", "\\[")

FACCIONES_VALIDAS = ["Alianza", "Imperio", "Sindicato"]
FACCIONES_EMOJIS  = {"Alianza": "⚔️", "Imperio": "🏛️", "Sindicato": "🗡️"}

# Config key defaults
_DEFAULTS = {
    "gf_duracion_minutos": "10",
    "gf_recompensa_1er":   "2000",
    "gf_recompensa_2do":   "800",
    "gf_recompensa_3er":   "300",
    "gf_recompensa_resto": "150",
    "gf_xp_participacion": "100",
    "gf_puntos_ataque":    "10",
    "gf_puntos_defensa":   "5",
    "gf_guerra_diaria":    "0",
    "gf_hora_diaria":      "12:00",
}

# Referencia global a la aplicación (para programar jobs)
_app = None


# ==================== DB SETUP ====================
def _init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS guerras_facciones (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        faccion1 TEXT NOT NULL,
        faccion2 TEXT NOT NULL,
        faccion3 TEXT,
        puntos_f1 INTEGER DEFAULT 0,
        puntos_f2 INTEGER DEFAULT 0,
        puntos_f3 INTEGER DEFAULT 0,
        estado TEXT DEFAULT 'activa',
        iniciada_por INTEGER,
        fecha_inicio TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        fecha_fin TIMESTAMP
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS guerras_facciones_participantes (
        guerra_id INTEGER,
        user_id INTEGER,
        faccion TEXT,
        tipo_accion TEXT DEFAULT '',
        faccion_objetivo TEXT DEFAULT '',
        ataques INTEGER DEFAULT 0,
        defensas INTEGER DEFAULT 0,
        victorias INTEGER DEFAULT 0,
        puntos_aportados INTEGER DEFAULT 0,
        accion_realizada INTEGER DEFAULT 0,
        PRIMARY KEY (guerra_id, user_id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS guerras_facciones_notifs (
        guerra_id INTEGER,
        user_id INTEGER,
        chat_id INTEGER,
        message_id INTEGER,
        PRIMARY KEY (guerra_id, user_id)
    )''')

    # Migraciones compatibles con DB existente
    migs = [
        "ALTER TABLE guerras_facciones ADD COLUMN faccion3 TEXT",
        "ALTER TABLE guerras_facciones ADD COLUMN puntos_f3 INTEGER DEFAULT 0",
        "ALTER TABLE guerras_facciones_participantes ADD COLUMN accion_realizada INTEGER DEFAULT 0",
        "ALTER TABLE guerras_facciones_participantes ADD COLUMN tipo_accion TEXT DEFAULT ''",
        "ALTER TABLE guerras_facciones_participantes ADD COLUMN faccion_objetivo TEXT DEFAULT ''",
    ]
    for sql in migs:
        try:
            c.execute(sql)
        except Exception:
            pass

    conn.commit()
    conn.close()

_init_db()


# ==================== CONFIG ====================
def _cfg(clave: str) -> str:
    return db_helper.obtener_config(clave, _DEFAULTS.get(clave, ""))

def _set_cfg(clave: str, valor):
    db_helper.establecer_config(clave, str(valor))

def _duracion_minutos() -> int:
    try:
        return max(1, int(_cfg("gf_duracion_minutos")))
    except Exception:
        return 10

def _recompensa(pos: str) -> int:
    try:
        return int(_cfg(f"gf_recompensa_{pos}"))
    except Exception:
        return {"1er": 2000, "2do": 800, "3er": 300, "resto": 150}.get(pos, 100)

def _puntos_ataque() -> int:
    try:
        return int(_cfg("gf_puntos_ataque"))
    except Exception:
        return 10

def _puntos_defensa() -> int:
    try:
        return int(_cfg("gf_puntos_defensa"))
    except Exception:
        return 5


# ==================== HELPERS DB ====================
def _obtener_guerra_activa() -> Optional[Dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM guerras_facciones WHERE estado='activa' ORDER BY id DESC LIMIT 1")
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def _reload_guerra(guerra_id: int) -> Optional[Dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM guerras_facciones WHERE id=?", (guerra_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def _facciones_de_guerra(guerra: Dict) -> List[str]:
    facs = [guerra["faccion1"], guerra["faccion2"]]
    if guerra.get("faccion3"):
        facs.append(guerra["faccion3"])
    return facs

def _campo_puntos(faccion: str, guerra: Dict) -> Optional[str]:
    if faccion == guerra["faccion1"]: return "puntos_f1"
    if faccion == guerra["faccion2"]: return "puntos_f2"
    if guerra.get("faccion3") and faccion == guerra["faccion3"]: return "puntos_f3"
    return None

def _puntos_de_faccion(faccion: str, guerra: Dict) -> int:
    campo = _campo_puntos(faccion, guerra)
    if not campo:
        return 0
    return guerra.get(campo, 0) or 0

def _jugador_ya_actuo(guerra_id: int, user_id: int) -> bool:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT accion_realizada FROM guerras_facciones_participantes WHERE guerra_id=? AND user_id=?",
        (guerra_id, user_id)
    )
    row = c.fetchone()
    conn.close()
    return bool(row and row[0])

def _sumar_puntos(guerra_id: int, campo: str, pts: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(f"UPDATE guerras_facciones SET {campo}={campo}+? WHERE id=?", (pts, guerra_id))
    conn.commit()
    conn.close()

def _registrar_accion_pendiente(guerra_id: int, user_id: int, faccion: str,
                                tipo: str, objetivo: str):
    """Registra la intención del jugador SIN calcular puntos (cálculo diferido al fin de guerra)."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT OR IGNORE INTO guerras_facciones_participantes "
        "(guerra_id,user_id,faccion,tipo_accion,faccion_objetivo,ataques,defensas,victorias,puntos_aportados,accion_realizada) "
        "VALUES (?,?,?,?,?,0,0,0,0,0)",
        (guerra_id, user_id, faccion, tipo, objetivo)
    )
    c.execute(
        "UPDATE guerras_facciones_participantes SET "
        "tipo_accion=?, faccion_objetivo=?, accion_realizada=1 "
        "WHERE guerra_id=? AND user_id=?",
        (tipo, objetivo, guerra_id, user_id)
    )
    conn.commit()
    conn.close()

def _registrar_accion_db(guerra_id: int, user_id: int, faccion: str,
                          tipo: str, objetivo: str, pts: int, victoria: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT OR IGNORE INTO guerras_facciones_participantes "
        "(guerra_id,user_id,faccion,tipo_accion,faccion_objetivo,ataques,defensas,victorias,puntos_aportados,accion_realizada) "
        "VALUES (?,?,?,?,?,0,0,0,0,0)",
        (guerra_id, user_id, faccion, tipo, objetivo)
    )
    ataques_d  = 1 if tipo == "atacar"   else 0
    defensas_d = 1 if tipo == "defender" else 0
    c.execute(
        "UPDATE guerras_facciones_participantes SET "
        "ataques=ataques+?, defensas=defensas+?, victorias=victorias+?, "
        "puntos_aportados=puntos_aportados+?, tipo_accion=?, faccion_objetivo=?, accion_realizada=1 "
        "WHERE guerra_id=? AND user_id=?",
        (ataques_d, defensas_d, victoria, pts, tipo, objetivo, guerra_id, user_id)
    )
    conn.commit()
    conn.close()


# ── Helpers públicos para otros módulos ───────────────────────────────────────
def hay_guerra_activa() -> bool:
    """Devuelve True si hay una guerra de facciones en curso."""
    return _obtener_guerra_activa() is not None

def jugador_en_lockdown(user_id: int) -> bool:
    """Devuelve True si hay guerra activa (el jugador está bloqueado de actividades normales)."""
    return hay_guerra_activa()

async def check_lockdown(update) -> bool:
    """Retorna True y envía mensaje si hay guerra activa.
    Llama desde cualquier comando que deba bloquearse durante la guerra."""
    try:
        from modo_debug import esta_en_debug
        if esta_en_debug(update.effective_user.id):
            return False  # Debug: lockdown desactivado para el superadmin
    except Exception:
        pass
    if not hay_guerra_activa():
        return False
    await update.effective_message.reply_text(
        "🔒 *¡Los servicios están suspendidos durante la Guerra de Facciones!*\n\n"
        "Solo puedes:\n"
        "⚔️ /guerra\\_facciones\\_atacar — Atacar\n"
        "🛡️ /guerra\\_facciones\\_defender — Defender\n"
        "⏭️ /saltar\\_guerra — No participar\n\n"
        "También puedes consultar 👤 /perfil, 🎒 /inventario y 📖 /guia.",
        parse_mode="Markdown"
    )
    return True

def jugador_ya_actuo_publico(user_id: int) -> bool:
    """Devuelve True si el jugador ya registró su acción en la guerra activa."""
    guerra = _obtener_guerra_activa()
    if not guerra:
        return False
    return _jugador_ya_actuo(guerra["id"], user_id)

def _obtener_top(guerra_id: int, faccion: str, limite: int = 5) -> List[Dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(
        "SELECT * FROM guerras_facciones_participantes WHERE guerra_id=? AND faccion=? "
        "ORDER BY puntos_aportados DESC LIMIT ?",
        (guerra_id, faccion, limite)
    )
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def _todos_los_jugadores_ids() -> List[int]:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT user_id FROM jugadores")
    rows = c.fetchall()
    conn.close()
    return [r[0] for r in rows]

def _guardar_notif(guerra_id: int, user_id: int, chat_id: int, message_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT OR REPLACE INTO guerras_facciones_notifs (guerra_id,user_id,chat_id,message_id) VALUES (?,?,?,?)",
        (guerra_id, user_id, chat_id, message_id)
    )
    conn.commit()
    conn.close()

def _obtener_notifs(guerra_id: int) -> List[Dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM guerras_facciones_notifs WHERE guerra_id=?", (guerra_id,))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ==================== TECLADOS ====================
def _teclado_guerra_activa(guerra_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⚔️ ATACAR",      callback_data=f"gf_menu_atk_{guerra_id}"),
            InlineKeyboardButton("🛡️ DEFENDER",    callback_data=f"gf_menu_def_{guerra_id}"),
        ],
        [
            InlineKeyboardButton("⏭️ Saltarse",    callback_data=f"gf_saltar_{guerra_id}"),
            InlineKeyboardButton("📊 Marcador",     callback_data=f"gf_estado_{guerra_id}"),
        ],
    ])

def _teclado_ya_actuo() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Ver marcador provisional", callback_data="gf_marcador_solo")],
    ])

def _teclado_elegir_faccion(guerra_id: int, accion: str, facs: List[str]) -> InlineKeyboardMarkup:
    botones = []
    for f in facs:
        emoji = FACCIONES_EMOJIS.get(f, "🏳️")
        botones.append([InlineKeyboardButton(
            f"{emoji} {f}",
            callback_data=f"gf_{accion}_{guerra_id}_{f}"
        )])
    botones.append([InlineKeyboardButton("↩️ Volver", callback_data=f"gf_notif_{guerra_id}")])
    return InlineKeyboardMarkup(botones)


# ==================== TEXTO DE MARCADOR ====================
def _texto_marcador(guerra: Dict) -> str:
    facs   = _facciones_de_guerra(guerra)
    puntos = {f: _puntos_de_faccion(f, guerra) for f in facs}
    total  = sum(puntos.values()) or 1
    try:
        fin      = datetime.fromisoformat(guerra["fecha_fin"])
        seg      = max(0, int((fin - datetime.now()).total_seconds()))
        t_txt    = f"{seg // 60}m {seg % 60}s restantes"
    except Exception:
        t_txt    = "—"

    facs_ord = sorted(facs, key=lambda f: puntos[f], reverse=True)
    medallas = ["🥇", "🥈", "🥉"]
    lineas   = [f"⚔️ *GUERRA DE FACCIONES*  ⏱️ {t_txt}\n"]
    for i, f in enumerate(facs_ord):
        emoji = FACCIONES_EMOJIS.get(f, "🏳️")
        pts   = puntos[f]
        barra = int(12 * pts / total)
        med   = medallas[i] if i < 3 else "  "
        lineas.append(f"{med} {emoji} *{f}*: {pts} pts\n{'█'*barra}{'░'*(12-barra)}")
    return "\n".join(lineas)


# ==================== NOTIFICACIONES MASIVAS ====================
async def _broadcast_inicio_guerra(bot, guerra: Dict):
    """Envía el mensaje de lore + botones a TODOS los jugadores. Actualiza menú '/'."""
    guerra_id = guerra["id"]
    minutos   = _duracion_minutos()
    texto = (
        f"⚔️ <b>¡LA GUERRA DE FACCIONES HA COMENZADO!</b>\n\n"
        f"Los tambores de guerra resuenan por todo Aethelgard...\n"
        f"Las tres grandes facciones se lanzan al combate por el dominio del mundo.\n\n"
        f"⚔️ <b>Alianza</b>  vs  🏛️ <b>Imperio</b>  vs  🗡️ <b>Sindicato</b>\n\n"
        f"⏱️ Duración: <b>{minutos} minutos</b>\n"
        f"⚡ Cada guerrero puede actuar <b>una sola vez</b> — ¡elige con sabiduría!\n\n"
        f"🔒 <i>Durante la guerra, todas las actividades quedan suspendidas.</i>\n\n"
        f"👇 <b>Usa los botones de abajo para atacar, defender o ver el marcador:</b>"
    )
    teclado = _teclado_guerra_activa(guerra_id)
    uids    = _todos_los_jugadores_ids()
    for uid in uids:
        try:
            msg = await bot.send_message(
                chat_id=uid, text=texto,
                reply_markup=teclado, parse_mode="HTML"
            )
            _guardar_notif(guerra_id, uid, uid, msg.message_id)
            await asyncio.sleep(0.06)
        except Exception:
            pass
    # Actualizar menú "/" de todos los jugadores a modo guerra
    try:
        from zonas_comandos import actualizar_comandos_jugador
        for uid in uids:
            try:
                await actualizar_comandos_jugador(bot, uid)
                await asyncio.sleep(0.04)
            except Exception:
                pass
    except Exception:
        pass
    # Enviar teclado de guerra (Reply Keyboard) a todos los jugadores
    try:
        from teclado_rapido import get_teclado_guerra, marcar_tipo
        for uid in uids:
            try:
                await bot.send_message(
                    chat_id=uid,
                    text="⚔️ Tus acciones rápidas de guerra:",
                    reply_markup=get_teclado_guerra(uid)
                )
                marcar_tipo(uid, "guerra")
                await asyncio.sleep(0.06)
            except Exception:
                pass
    except Exception:
        pass

async def _editar_notifs_fin(bot, guerra_id: int, texto_final: str):
    """Edita todos los mensajes persistentes al terminar la guerra (quita los botones)."""
    notifs = _obtener_notifs(guerra_id)
    for n in notifs:
        try:
            await bot.edit_message_text(
                chat_id=n["chat_id"],
                message_id=n["message_id"],
                text=texto_final,
                parse_mode="Markdown"
            )
            await asyncio.sleep(0.06)
        except Exception:
            pass


# ==================== FINALIZAR GUERRA ====================
async def _terminar_guerra_impl(bot, guerra: Dict):
    guerra_id = guerra["id"]

    # Marcar como finalizada en DB
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE guerras_facciones SET estado='finalizada' WHERE id=?", (guerra_id,))
    conn.commit()
    conn.close()

    # ── Calcular todas las acciones diferidas ─────────────────────────────
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(
        "SELECT * FROM guerras_facciones_participantes "
        "WHERE guerra_id=? AND accion_realizada=1 AND tipo_accion IN ('atacar','defender')",
        (guerra_id,)
    )
    acciones = [dict(r) for r in c.fetchall()]
    conn.close()

    facs_guerra = _facciones_de_guerra(guerra)
    puntos_calc = {f: 0 for f in facs_guerra}
    resultados_calc: dict = {}  # user_id → {pts, xp, victoria, tipo, objetivo, faccion}

    for accion in acciones:
        uid        = accion["user_id"]
        tipo       = accion.get("tipo_accion", "")
        objetivo   = accion.get("faccion_objetivo", "")
        fac_jug    = accion.get("faccion", "")
        jug        = db_helper.obtener_jugador(uid)
        if not jug:
            continue

        if tipo == "atacar":
            atk = jug.get("nivel", 1) * random.randint(8, 15)
            conn2 = sqlite3.connect(DB_PATH)
            c2    = conn2.cursor()
            c2.execute("SELECT nivel FROM jugadores WHERE faccion=? ORDER BY RANDOM() LIMIT 1",
                       (objetivo,))
            row2 = c2.fetchone()
            conn2.close()
            rival_niv = row2[0] if row2 else 1
            def_p     = rival_niv * random.randint(6, 12)
            victoria  = random.random() < (atk / max(1, atk + def_p))
            pts       = _puntos_ataque() if victoria else 0
            xp        = int(_cfg("gf_xp_participacion")) if victoria else 0
            if victoria and fac_jug in puntos_calc:
                puntos_calc[fac_jug] += pts
            resultados_calc[uid] = {
                "pts": pts, "xp": xp, "victoria": victoria,
                "tipo": "atacar", "objetivo": objetivo, "faccion": fac_jug,
                "nombre": jug["nombre_personaje"],
            }

        elif tipo == "defender":
            exito  = random.random() < 0.70
            pts    = _puntos_defensa() if exito else 0
            xp     = int(_cfg("gf_xp_participacion")) // 2 if exito else 0
            if exito and fac_jug in puntos_calc:
                puntos_calc[fac_jug] += pts
            resultados_calc[uid] = {
                "pts": pts, "xp": xp, "victoria": exito,
                "tipo": "defender", "objetivo": objetivo, "faccion": fac_jug,
                "nombre": jug["nombre_personaje"],
            }

    # Actualizar puntos en DB y puntos por participante
    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()
    for f in facs_guerra:
        campo = _campo_puntos(f, guerra)
        if campo:
            c.execute(f"UPDATE guerras_facciones SET {campo}=? WHERE id=?",
                      (puntos_calc.get(f, 0), guerra_id))
    for uid, res in resultados_calc.items():
        c.execute(
            "UPDATE guerras_facciones_participantes SET "
            "puntos_aportados=?, victorias=?, "
            "ataques=CASE WHEN tipo_accion='atacar' THEN 1 ELSE 0 END, "
            "defensas=CASE WHEN tipo_accion='defender' THEN 1 ELSE 0 END "
            "WHERE guerra_id=? AND user_id=?",
            (res["pts"], 1 if res["victoria"] else 0, guerra_id, uid)
        )
    conn.commit()
    conn.close()

    # Enviar resultado personal a cada jugador que actuó
    for uid, res in resultados_calc.items():
        try:
            e_fac  = FACCIONES_EMOJIS.get(res["faccion"], "")
            e_obj  = FACCIONES_EMOJIS.get(res["objetivo"], "")
            if res["tipo"] == "atacar":
                if res["victoria"]:
                    txt = (f"⚔️ *¡Atacaste a {e_obj}{_esc_md(res['objetivo'])} y venciste!*\n"
                           f"+{res['pts']} pts para {e_fac}{_esc_md(res['faccion'])}\n"
                           f"+{res['xp']} XP")
                else:
                    txt = (f"⚔️ *Atacaste a {e_obj}{_esc_md(res['objetivo'])} pero fuiste repelido.*\n"
                           f"El rival fue más fuerte esta vez.")
            else:
                if res["victoria"]:
                    txt = (f"🛡️ *¡Defendiste a {e_fac}{_esc_md(res['faccion'])} con éxito!*\n"
                           f"+{res['pts']} pts\n+{res['xp']} XP")
                else:
                    txt = (f"🛡️ *Intentaste defender a {e_fac}{_esc_md(res['faccion'])}, "
                           f"pero la defensa cedió.*")
            await bot.send_message(uid, txt, parse_mode="Markdown")
            await asyncio.sleep(0.06)
        except Exception:
            pass

    # Recargar puntos frescos
    guerra = _reload_guerra(guerra_id) or guerra

    facs     = _facciones_de_guerra(guerra)
    puntos   = {f: _puntos_de_faccion(f, guerra) for f in facs}
    facs_ord = sorted(facs, key=lambda f: puntos[f], reverse=True)
    max_pts  = max(puntos.values()) if puntos else 0
    lideres  = [f for f in facs_ord if puntos[f] == max_pts]
    medallas = ["🥇", "🥈", "🥉"]

    # Construir texto de resultado
    texto_resultado = f"🏆 *¡GUERRA DE FACCIONES FINALIZADA!*\n\n"
    for i, f in enumerate(facs_ord):
        emoji = FACCIONES_EMOJIS.get(f, "🏳️")
        med   = medallas[i] if i < 3 else "  "
        texto_resultado += f"{med} {emoji} *{f}*: {puntos[f]} pts\n"

    _gf_recomp = {}
    if len(lideres) > 1:
        texto_resultado += "\n⚖️ *EMPATE* — todos los participantes reciben 150 oro de consolación.\n"
        for f in facs:
            for p in _obtener_top(guerra_id, f, 200):
                economia.modificar_saldo(p["user_id"], "oro", 150, "guerra_empate")
                db_helper.agregar_notificacion(p["user_id"],
                    "⚖️ La guerra terminó en empate. +150 oro de consolación.")
                _gf_recomp[p["user_id"]] = {"xp": 0, "oro": 150}
    else:
        texto_resultado += "\n*🌟 Recompensas distribuidas:*\n"
        recompensas_por_pos = [
            ("1er", _recompensa("1er")),
            ("2do", _recompensa("2do")),
            ("3er", _recompensa("3er")),
        ]
        for i, f in enumerate(facs_ord):
            if i < len(recompensas_por_pos):
                pos_label, oro_base = recompensas_por_pos[i]
            else:
                pos_label, oro_base = "resto", _recompensa("resto")
            top3 = _obtener_top(guerra_id, f, 3)
            texto_resultado += f"\n{medallas[i] if i < 3 else '  '} *{f}*\n"
            top_ids = set()
            for j, p in enumerate(top3):
                top_ids.add(p["user_id"])
                bonus_oro = [oro_base, oro_base // 2, oro_base // 4][j]
                bonus_xp  = int(_cfg("gf_xp_participacion")) * (3 - j)
                economia.modificar_saldo(p["user_id"], "oro", bonus_oro, f"guerra_{pos_label}")
                jug = db_helper.obtener_jugador(p["user_id"])
                if jug:
                    db_helper.actualizar_jugador(p["user_id"],
                        experiencia=jug["experiencia"] + bonus_xp)
                nombre = jug["nombre_personaje"] if jug else str(p["user_id"])
                db_helper.agregar_notificacion(p["user_id"],
                    f"{'🏆' if i==0 else '🎖️'} Tu facción {f} quedó #{i+1}. "
                    f"+{bonus_oro} oro, +{bonus_xp} XP (puesto #{j+1}).")
                texto_resultado += f"  #{j+1} {nombre}: +{bonus_oro} oro\n"
                _gf_recomp[p["user_id"]] = {"xp": bonus_xp, "oro": bonus_oro}
            # Resto de participantes
            _resto_oro = _recompensa("resto")
            for p in _obtener_top(guerra_id, f, 200):
                if p["user_id"] not in top_ids:
                    economia.modificar_saldo(
                        p["user_id"], "oro", _resto_oro, "guerra_facciones_resto")
                    db_helper.agregar_notificacion(p["user_id"],
                        f"🎖️ Participaste en la guerra. Tu facción {f} quedó #{i+1}. "
                        f"+{_resto_oro} oro.")
                    _gf_recomp[p["user_id"]] = {"xp": 0, "oro": _resto_oro}

    texto_fin = texto_resultado + "\n\n_La guerra ha terminado. Todas las actividades se han reanudado._"

    # Editar todos los mensajes persistentes (quita los botones)
    await _editar_notifs_fin(bot, guerra_id, texto_fin)

    # Restaurar menú "/" normal a todos los jugadores
    try:
        from zonas_comandos import actualizar_comandos_jugador
        uids_todos = _todos_los_jugadores_ids()
        for uid in uids_todos:
            try:
                await actualizar_comandos_jugador(bot, uid)
                await asyncio.sleep(0.04)
            except Exception:
                pass
    except Exception:
        pass
    # Restaurar teclado normal (Reply Keyboard) a cada jugador según su zona
    try:
        import db_helper as _dh_rest
        from teclado_rapido import (get_teclado_principal, get_teclado_salvaje,
                                    marcar_tipo as _mt)
        uids_todos = _todos_los_jugadores_ids()
        for uid in uids_todos:
            try:
                jug_r = _dh_rest.obtener_jugador(uid)
                if not jug_r or jug_r.get("teclado_oculto", 0):
                    continue
                zona_r  = jug_r.get("zona_actual", "")
                # Detectar color de zona sin importar _detectar_color (privado)
                from datos_zona import ZONAS as _ZR
                zi = next((z for z in _ZR if z["nombre"] == zona_r), None)
                es_salvaje = zi and zi.get("tipo") == "salvaje"
                kb_r = get_teclado_salvaje(uid) if es_salvaje else get_teclado_principal(uid)
                _mt(uid, "salvaje" if es_salvaje else "ciudad")
                await bot.send_message(
                    chat_id=uid,
                    text="🕊️ La guerra ha terminado. Todas tus actividades se han reanudado.",
                    reply_markup=kb_r
                )
                await asyncio.sleep(0.06)
            except Exception:
                pass
    except Exception:
        pass

    # Broadcast del resultado
    try:
        from broadcast import broadcast_global
        await broadcast_global(bot, texto_resultado)
    except Exception:
        pass

    try:
        _gan_pp = []
        for _f in facs_ord:
            for _p in _obtener_top(guerra_id, _f, 10):
                _j = db_helper.obtener_jugador(_p["user_id"])
                _r = _gf_recomp.get(_p["user_id"], {})
                _gan_pp.append({
                    "user_id": _p["user_id"],
                    "nombre": _j["nombre_personaje"] if _j else str(_p["user_id"]),
                    "score": _p["puntos_aportados"],
                    "xp": _r.get("xp", 0),
                    "oro": _r.get("oro", 0),
                })
        if _gan_pp:
            await sa.notificar_admin_victoria(
                bot,
                "guerra_facciones",
                f"Guerra Facciones finalizada. Ganadora: {facs_ord[0] if facs_ord else '?'}",
                _gan_pp
            )
    except Exception:
        pass


async def _job_terminar_guerra(context: ContextTypes.DEFAULT_TYPE):
    """Job automático — se dispara al terminar los 10 min."""
    guerra = _obtener_guerra_activa()
    if guerra:
        await _terminar_guerra_impl(context.bot, guerra)


# ==================== CREAR GUERRA ====================
def _crear_guerra(iniciada_por: int = 0) -> Optional[Dict]:
    if _obtener_guerra_activa():
        return None
    f1, f2, f3 = FACCIONES_VALIDAS
    fecha_fin  = datetime.now() + timedelta(minutes=_duracion_minutos())
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(
        "INSERT INTO guerras_facciones "
        "(faccion1,faccion2,faccion3,puntos_f1,puntos_f2,puntos_f3,estado,iniciada_por,fecha_inicio,fecha_fin) "
        "VALUES (?,?,?,0,0,0,'activa',?,?,?)",
        (f1, f2, f3, iniciada_por, datetime.now().isoformat(), fecha_fin.isoformat())
    )
    gid = c.lastrowid
    conn.commit()
    c.execute("SELECT * FROM guerras_facciones WHERE id=?", (gid,))
    guerra = dict(c.fetchone())
    conn.close()
    return guerra

def _programar_fin_guerra(guerra_id: int):
    """Programa el job de fin de guerra usando la referencia global al app."""
    if _app:
        try:
            _app.job_queue.run_once(
                _job_terminar_guerra,
                when=timedelta(minutes=_duracion_minutos()),
                name=f"gf_fin_{guerra_id}"
            )
        except Exception:
            pass


# ==================== COMANDOS ADMIN ====================
async def cmd_guerra_facciones_iniciar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/guerra_facciones_iniciar — Admin activa la guerra inmediatamente."""
    user_id = update.effective_user.id
    if not sa._es_admin(user_id):
        await update.effective_message.reply_text("❌ Sin permiso de administrador.")
        return
    if _obtener_guerra_activa():
        await update.effective_message.reply_text(
            "⚠️ Ya hay una guerra activa.\nUsa /guerra_facciones_finalizar para terminarla.")
        return
    guerra = _crear_guerra(user_id)
    if not guerra:
        await update.effective_message.reply_text("❌ No se pudo crear la guerra.")
        return
    _programar_fin_guerra(guerra["id"])
    await update.effective_message.reply_text(
        f"✅ *¡Guerra iniciada!*  ⏱️ {_duracion_minutos()} min\nEnviando notificaciones...",
        parse_mode="Markdown"
    )
    await _broadcast_inicio_guerra(context.bot, guerra)
    await update.effective_message.reply_text("📢 Notificaciones enviadas a todos los jugadores.")

async def cmd_guerra_facciones_finalizar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/guerra_facciones_finalizar — Admin termina la guerra al instante."""
    user_id = update.effective_user.id
    if not sa._es_admin(user_id):
        await update.effective_message.reply_text("❌ Sin permiso.")
        return
    guerra = _obtener_guerra_activa()
    if not guerra:
        await update.effective_message.reply_text("No hay ninguna guerra activa.")
        return
    await update.effective_message.reply_text("⏳ Calculando resultados...")
    await _terminar_guerra_impl(context.bot, guerra)
    await update.effective_message.reply_text("✅ Guerra finalizada y recompensas distribuidas.")


# ==================== COMANDOS JUGADORES ====================
async def cmd_guerra_facciones_estado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    guerra = _obtener_guerra_activa()
    if not guerra:
        await update.effective_message.reply_text("No hay ninguna guerra de facciones activa.")
        return
    await update.effective_message.reply_text(
        _texto_marcador(guerra),
        reply_markup=_teclado_guerra_activa(guerra["id"]),
        parse_mode="Markdown"
    )

async def cmd_guerra_facciones_atacar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        await update.effective_message.reply_text("❌ Primero crea un personaje con /start.")
        return
    guerra = _obtener_guerra_activa()
    if not guerra:
        await update.effective_message.reply_text("⚠️ No hay ninguna guerra de facciones activa ahora mismo.")
        return
    if _jugador_ya_actuo(guerra["id"], user_id):
        await update.effective_message.reply_text("⚠️ Ya has actuado en esta guerra. Espera a la siguiente.")
        return
    faccion_jug = jug.get("faccion", "")
    rivales = [f for f in _facciones_de_guerra(guerra) if f != faccion_jug]
    if not rivales:
        await update.effective_message.reply_text("❌ No hay facciones rivales en esta guerra.")
        return
    await update.effective_message.reply_text(
        f"⚔️ *Atacar — Elige tu objetivo*\n\n"
        f"Tu facción: {FACCIONES_EMOJIS.get(faccion_jug,'')}{faccion_jug or '(ninguna)'}\n\n"
        f"¿A cuál facción rival atacas?",
        reply_markup=_teclado_elegir_faccion(guerra["id"], "atk", rivales),
        parse_mode="Markdown"
    )

async def cmd_guerra_facciones_defender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        await update.effective_message.reply_text("❌ Primero crea un personaje con /start.")
        return
    guerra = _obtener_guerra_activa()
    if not guerra:
        await update.effective_message.reply_text("⚠️ No hay ninguna guerra de facciones activa ahora mismo.")
        return
    if _jugador_ya_actuo(guerra["id"], user_id):
        await update.effective_message.reply_text("⚠️ Ya has actuado en esta guerra. Espera a la siguiente.")
        return
    faccion_jug = jug.get("faccion", "")
    aliadas = [f for f in _facciones_de_guerra(guerra) if f == faccion_jug]
    if not aliadas:
        await update.effective_message.reply_text("❌ Tu facción no participa en esta guerra.")
        return
    await update.effective_message.reply_text(
        f"🛡️ *Defender — Refuerza tu facción*\n\n"
        f"Tu facción: {FACCIONES_EMOJIS.get(faccion_jug,'')}{faccion_jug or '(ninguna)'}\n\n"
        f"¿Defiendes tu propia facción?",
        reply_markup=_teclado_elegir_faccion(guerra["id"], "def", aliadas),
        parse_mode="Markdown"
    )

async def cmd_saltar_guerra(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/saltar_guerra — El jugador elige no participar en la guerra activa."""
    user_id = update.effective_user.id
    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        await update.effective_message.reply_text("❌ Primero crea un personaje con /start.")
        return
    guerra = _obtener_guerra_activa()
    if not guerra:
        await update.effective_message.reply_text("⚠️ No hay ninguna guerra de facciones activa.")
        return
    if _jugador_ya_actuo(guerra["id"], user_id):
        await update.effective_message.reply_text("⏳ Ya registraste tu decisión. Espera el resultado final.")
        return
    faccion_jug = jug.get("faccion", "") or "Ninguna"
    _registrar_accion_pendiente(guerra["id"], user_id, faccion_jug, "saltar", "")
    await update.effective_message.reply_text(
        f"⏭️ *{_esc_md(jug['nombre_personaje'])}* decidió mantenerse al margen del conflicto.\n\n"
        f"🕊️ _No participarás en esta guerra._\n"
        f"⏳ Espera a que la batalla termine para reanudar tus actividades.\n"
        f"📦 Mientras tanto, puedes consultar /inventario, /perfil y /guia.",
        parse_mode="Markdown"
    )

async def cmd_guerra_facciones_ranking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    guerra = _obtener_guerra_activa()
    if not guerra:
        await update.effective_message.reply_text("No hay ninguna guerra activa.")
        return
    facs  = _facciones_de_guerra(guerra)
    texto = "🏆 *Ranking — Guerra de Facciones*\n\n"
    for f in sorted(facs, key=lambda x: _puntos_de_faccion(x, guerra), reverse=True):
        emoji = FACCIONES_EMOJIS.get(f, "🏳️")
        top   = _obtener_top(guerra["id"], f, 5)
        texto += f"{emoji} *{f}* — {_puntos_de_faccion(f, guerra)} pts\n"
        for i, p in enumerate(top):
            jug = db_helper.obtener_jugador(p["user_id"])
            n   = jug["nombre_personaje"] if jug else str(p["user_id"])
            texto += f"  #{i+1} {n}: {p['puntos_aportados']} pts\n"
        if not top:
            texto += "  (sin participantes)\n"
        texto += "\n"
    await update.effective_message.reply_text(texto, parse_mode="Markdown")


# ==================== CALLBACKS JUGADORES ====================
async def _cb_ataque(query, guerra: Dict, jug: Dict, faccion_objetivo: str):
    """Registra la orden de ataque de forma diferida — el resultado se calcula al fin de la guerra."""
    guerra_id   = guerra["id"]
    user_id     = jug["user_id"]
    faccion_jug = jug.get("faccion", "")

    if _jugador_ya_actuo(guerra_id, user_id):
        await query.edit_message_text(
            "⏳ *Ya sellaste tu acción en esta guerra.*\n\nEspera el veredicto final.",
            reply_markup=_teclado_ya_actuo(),
            parse_mode="Markdown"
        )
        return

    campo = _campo_puntos(faccion_jug, guerra)
    if not campo:
        await query.edit_message_text(
            f"❌ Tu facción *{faccion_jug or 'ninguna'}* no participa en esta guerra.\n"
            f"Facciones en guerra: {', '.join(_facciones_de_guerra(guerra))}",
            parse_mode="Markdown"
        )
        return

    e_jug = FACCIONES_EMOJIS.get(faccion_jug, "")
    e_obj = FACCIONES_EMOJIS.get(faccion_objetivo, "")
    _registrar_accion_pendiente(guerra_id, user_id, faccion_jug, "atacar", faccion_objetivo)
    await query.edit_message_text(
        f"⚔️ *{_esc_md(jug['nombre_personaje'])}* {e_jug} marchará contra {e_obj}*{_esc_md(faccion_objetivo)}*\n\n"
        f"🗡️ _¡Tu orden de ataque ha sido sellada en el grimorio de guerra!_\n\n"
        f"⏳ Los combates se resolverán todos a la vez al final de la batalla.\n"
        f"📦 Mientras tanto, solo puedes consultar tu inventario, perfil y la guía.",
        reply_markup=_teclado_ya_actuo(),
        parse_mode="Markdown"
    )


async def _cb_defensa(query, guerra: Dict, jug: Dict, faccion_objetivo: str):
    """Registra la orden de defensa de forma diferida — el resultado se calcula al fin de la guerra."""
    guerra_id   = guerra["id"]
    user_id     = jug["user_id"]
    faccion_jug = jug.get("faccion", "")

    if _jugador_ya_actuo(guerra_id, user_id):
        await query.edit_message_text(
            "⏳ *Ya sellaste tu acción en esta guerra.*\n\nEspera el veredicto final.",
            reply_markup=_teclado_ya_actuo(),
            parse_mode="Markdown"
        )
        return

    campo = _campo_puntos(faccion_jug, guerra)
    if not campo:
        await query.edit_message_text(
            f"❌ Tu facción *{faccion_jug or 'ninguna'}* no participa en esta guerra.",
            parse_mode="Markdown"
        )
        return

    e_jug = FACCIONES_EMOJIS.get(faccion_jug, "")
    e_obj = FACCIONES_EMOJIS.get(faccion_objetivo, "")
    _registrar_accion_pendiente(guerra_id, user_id, faccion_jug, "defender", faccion_objetivo)
    await query.edit_message_text(
        f"🛡️ *{_esc_md(jug['nombre_personaje'])}* {e_jug} defenderá las murallas de {e_obj}*{_esc_md(faccion_objetivo)}*\n\n"
        f"🛡️ _¡Tu juramento de defensa ha sido sellado!_\n\n"
        f"⏳ Los resultados se revelarán al finalizar la batalla.\n"
        f"📦 Mientras tanto, solo puedes consultar tu inventario, perfil y la guía.",
        reply_markup=_teclado_ya_actuo(),
        parse_mode="Markdown"
    )


async def _cb_saltar(query, guerra: Dict, jug: Dict):
    """El jugador opta por no participar — queda bloqueado hasta fin de guerra."""
    guerra_id = guerra["id"]
    user_id   = jug["user_id"]

    if _jugador_ya_actuo(guerra_id, user_id):
        await query.edit_message_text(
            "⏳ *Ya registraste tu decisión.*\n\nEspera a que termine la guerra.",
            reply_markup=_teclado_ya_actuo(),
            parse_mode="Markdown"
        )
        return

    faccion_jug = jug.get("faccion", "") or "Ninguna"
    _registrar_accion_pendiente(guerra_id, user_id, faccion_jug, "saltar", "")
    await query.edit_message_text(
        f"⏭️ *{_esc_md(jug['nombre_personaje'])}* decidió mantenerse al margen del conflicto.\n\n"
        f"🕊️ _No participarás en esta guerra._\n\n"
        f"⏳ Espera a que la batalla termine para reanudar tus actividades.\n"
        f"📦 Mientras tanto, solo puedes consultar tu inventario, perfil y la guía.",
        reply_markup=_teclado_ya_actuo(),
        parse_mode="Markdown"
    )


async def cb_gf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Dispatcher central de todos los callbacks gf_*"""
    query   = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    data    = query.data

    if sa.verificar_baneado(user_id):
        await query.answer("❌ Estás baneado.", show_alert=True)
        return

    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        await query.answer("❌ No tienes personaje creado.", show_alert=True)
        return

    parts = data.split("_")

    # gf_ciudad_{gid}
    if data.startswith("gf_ciudad_"):
        try:
            gid = int(parts[-1])
        except (ValueError, IndexError):
            return
        db_helper.actualizar_jugador(user_id, ubicacion="ciudad")
        guerra = _obtener_guerra_activa()
        if not guerra or guerra["id"] != gid:
            await query.edit_message_text("⚠️ La guerra ya terminó.")
            return
        await query.edit_message_text(
            f"🏙️ *¡Llegaste a la ciudad!*\n\n" + _texto_marcador(guerra),
            reply_markup=_teclado_guerra_activa(gid),
            parse_mode="Markdown"
        )
        return

    # gf_estado_{gid}
    if data.startswith("gf_estado_"):
        try:
            gid = int(parts[-1])
        except (ValueError, IndexError):
            return
        guerra = _obtener_guerra_activa()
        if not guerra:
            await query.edit_message_text("La guerra ya terminó.")
            return
        await query.edit_message_text(
            _texto_marcador(guerra),
            reply_markup=_teclado_guerra_activa(gid),
            parse_mode="Markdown"
        )
        return

    # gf_notif_{gid} — volver a la notificación original
    if data.startswith("gf_notif_"):
        try:
            gid = int(parts[-1])
        except (ValueError, IndexError):
            return
        guerra = _obtener_guerra_activa()
        if not guerra:
            await query.edit_message_text("La guerra ya terminó.")
            return
        await query.edit_message_text(
            f"⚔️ *¡GUERRA DE FACCIONES ACTIVA!*\n\n" + _texto_marcador(guerra),
            reply_markup=_teclado_guerra_activa(gid),
            parse_mode="Markdown"
        )
        return

    # gf_menu_atk_{gid} — mostrar selector de facción para atacar
    if data.startswith("gf_menu_atk_"):
        try:
            gid = int(parts[-1])
        except (ValueError, IndexError):
            return
        guerra = _obtener_guerra_activa()
        if not guerra or guerra["id"] != gid:
            await query.edit_message_text("⚠️ La guerra ya terminó.")
            return
        if _jugador_ya_actuo(gid, user_id):
            await query.answer("⚠️ Ya actuaste en esta guerra.", show_alert=True)
            return
        faccion_jug = jug.get("faccion", "")
        rivales = [f for f in _facciones_de_guerra(guerra) if f != faccion_jug]
        if not rivales:
            await query.answer("❌ No hay facciones rivales.", show_alert=True)
            return
        await query.edit_message_text(
            f"⚔️ *Atacar — Elige tu objetivo*\n\n"
            f"Tu facción: {FACCIONES_EMOJIS.get(faccion_jug,'')}{faccion_jug or '(ninguna)'}\n\n"
            f"¿A cuál facción rival atacas?",
            reply_markup=_teclado_elegir_faccion(gid, "atk", rivales),
            parse_mode="Markdown"
        )
        return

    # gf_menu_def_{gid} — mostrar selector de facción para defender
    if data.startswith("gf_menu_def_"):
        try:
            gid = int(parts[-1])
        except (ValueError, IndexError):
            return
        guerra = _obtener_guerra_activa()
        if not guerra or guerra["id"] != gid:
            await query.edit_message_text("⚠️ La guerra ya terminó.")
            return
        if _jugador_ya_actuo(gid, user_id):
            await query.answer("⚠️ Ya actuaste en esta guerra.", show_alert=True)
            return
        faccion_jug = jug.get("faccion", "")
        # Defender = reforzar la propia facción
        if not faccion_jug or faccion_jug not in _facciones_de_guerra(guerra):
            await query.answer("❌ Tu facción no participa en esta guerra.", show_alert=True)
            return
        await query.edit_message_text(
            f"🛡️ *Defender — Refuerza tus murallas*\n\n"
            f"Tu facción: {FACCIONES_EMOJIS.get(faccion_jug,'')}{faccion_jug or '(ninguna)'}\n\n"
            f"Defenderás tu propia facción. ¿Confirmas?",
            reply_markup=_teclado_elegir_faccion(gid, "def", [faccion_jug]),
            parse_mode="Markdown"
        )
        return

    # gf_atk_{gid}_{Faccion}
    if data.startswith("gf_atk_"):
        # formato: gf_atk_<gid>_<FaccionConMayusculas>
        try:
            gid = int(parts[2])
            faccion_obj = "_".join(parts[3:])
        except (ValueError, IndexError):
            return
        guerra = _obtener_guerra_activa()
        if not guerra or guerra["id"] != gid:
            await query.edit_message_text("⚠️ La guerra ya terminó.")
            return
        await _cb_ataque(query, guerra, jug, faccion_obj)
        return

    # gf_def_{gid}_{Faccion}
    if data.startswith("gf_def_"):
        try:
            gid = int(parts[2])
            faccion_obj = "_".join(parts[3:])
        except (ValueError, IndexError):
            return
        guerra = _obtener_guerra_activa()
        if not guerra or guerra["id"] != gid:
            await query.edit_message_text("⚠️ La guerra ya terminó.")
            return
        await _cb_defensa(query, guerra, jug, faccion_obj)
        return

    # gf_saltar_{gid} — el jugador se salta la guerra
    if data.startswith("gf_saltar_"):
        try:
            gid = int(parts[-1])
        except (ValueError, IndexError):
            return
        guerra = _obtener_guerra_activa()
        if not guerra or guerra["id"] != gid:
            await query.edit_message_text("⚠️ La guerra ya terminó.")
            return
        await _cb_saltar(query, guerra, jug)
        return

    # gf_marcador_solo — ver marcador sin botones de acción
    if data == "gf_marcador_solo":
        guerra = _obtener_guerra_activa()
        if not guerra:
            await query.answer("La guerra ya terminó.", show_alert=True)
            return
        try:
            await query.edit_message_text(
                _texto_marcador(guerra),
                reply_markup=_teclado_ya_actuo(),
                parse_mode="Markdown"
            )
        except Exception:
            pass
        return


# ==================== PANEL ADMIN GUERRAS ====================
def _panel_texto() -> str:
    guerra  = _obtener_guerra_activa()
    diaria  = _cfg("gf_guerra_diaria") == "1"
    hora    = _cfg("gf_hora_diaria")
    if guerra:
        facs     = _facciones_de_guerra(guerra)
        pts_txt  = "  ".join(
            f"{FACCIONES_EMOJIS.get(f,'')}{f}: {_puntos_de_faccion(f, guerra)}"
            for f in facs
        )
        estado_txt = (f"🟢 *ACTIVA* — Guerra #{guerra['id']}\n"
                      f"Inicio: {guerra['fecha_inicio'][:16]}\n"
                      f"Fin:    {guerra['fecha_fin'][:16]}\n"
                      f"Puntos: {pts_txt}")
    else:
        estado_txt = "🔴 Sin guerra activa"
    return (
        f"⚔️ *Panel de Guerra de Facciones*\n\n"
        f"Estado: {estado_txt}\n\n"
        f"*Configuración actual:*\n"
        f"  ⏱️ Duración: *{_duracion_minutos()} min*\n"
        f"  📅 Guerra diaria: *{'✅ ON' if diaria else '❌ OFF'}* a las {hora}\n"
        f"  🏆 1er: {_recompensa('1er')} | 🥈 2do: {_recompensa('2do')} | "
        f"🥉 3er: {_recompensa('3er')} | Resto: {_recompensa('resto')} oro\n"
        f"  ⚔️ Pts/ataque: {_puntos_ataque()} | 🛡️ Pts/defensa: {_puntos_defensa()}\n"
        f"  ⭐ XP participación: {_cfg('gf_xp_participacion')}"
    )

def _panel_teclado() -> InlineKeyboardMarkup:
    guerra = _obtener_guerra_activa()
    diaria = _cfg("gf_guerra_diaria") == "1"
    kb = []
    if not guerra:
        kb.append([InlineKeyboardButton("🚀 Iniciar Guerra Ahora", callback_data="pgf_iniciar")])
    else:
        kb.append([InlineKeyboardButton("⏹ Finalizar Guerra Ya",   callback_data="pgf_finalizar")])
        kb.append([InlineKeyboardButton("📊 Ver Marcador",          callback_data="pgf_marcador")])
        kb.append([InlineKeyboardButton("📢 Reenviar Notificación", callback_data="pgf_renotificar")])
    kb.append([InlineKeyboardButton(
        f"📅 Guerra Diaria: {'✅ ON' if diaria else '❌ OFF'}",
        callback_data="pgf_toggle_diaria"
    )])
    kb.append([
        InlineKeyboardButton("⏱️ Duración",    callback_data="pgf_dur"),
        InlineKeyboardButton("🏆 Recompensas", callback_data="pgf_rec"),
    ])
    kb.append([
        InlineKeyboardButton("⚔️ Pts Ataque",  callback_data="pgf_pta"),
        InlineKeyboardButton("🛡️ Pts Defensa", callback_data="pgf_ptd"),
    ])
    kb.append([
        InlineKeyboardButton("⭐ XP Participación", callback_data="pgf_xp"),
        InlineKeyboardButton("🕐 Hora Diaria",      callback_data="pgf_hora"),
    ])
    kb.append([InlineKeyboardButton("🔄 Actualizar", callback_data="pgf_refresh")])
    return InlineKeyboardMarkup(kb)

async def cmd_panel_guerras(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/panel_guerras — Panel de control de guerras de facciones."""
    user_id = update.effective_user.id
    if not sa._es_admin(user_id):
        await update.effective_message.reply_text("❌ Sin permiso.")
        return
    await update.effective_message.reply_text(
        _panel_texto(), reply_markup=_panel_teclado(), parse_mode="Markdown"
    )

async def cb_panel_guerras(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callbacks del panel de guerras pgf_*"""
    query   = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    if not sa._es_admin(user_id):
        await query.answer("❌ Sin permiso.", show_alert=True)
        return
    data = query.data

    if data == "pgf_refresh":
        try:
            await query.edit_message_text(
                _panel_texto(), reply_markup=_panel_teclado(), parse_mode="Markdown"
            )
        except Exception as _e:
            if "not modified" not in str(_e).lower():
                await query.message.reply_text(f"⚠️ Error al actualizar panel: {_e}")
        return

    if data == "pgf_marcador":
        guerra = _obtener_guerra_activa()
        if not guerra:
            await query.answer("ℹ️ No hay ninguna guerra activa ahora mismo.", show_alert=True)
            return
        try:
            kb_volver = InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Volver al panel", callback_data="pgf_refresh")
            ]])
            await query.edit_message_text(
                _texto_marcador(guerra), reply_markup=kb_volver, parse_mode="Markdown"
            )
        except Exception as _e:
            if "not modified" not in str(_e).lower():
                await query.message.reply_text(f"⚠️ Error al mostrar marcador: {_e}")
        return

    if data == "pgf_iniciar":
        if _obtener_guerra_activa():
            await query.answer("⚠️ Ya hay una guerra activa.", show_alert=True)
            return
        guerra = _crear_guerra(user_id)
        if not guerra:
            await query.answer("❌ Error al crear la guerra.", show_alert=True)
            return
        _programar_fin_guerra(guerra["id"])
        await query.edit_message_text(
            _panel_texto() + "\n\n⏳ _Enviando notificaciones a todos los jugadores..._",
            reply_markup=_panel_teclado(), parse_mode="Markdown"
        )
        await _broadcast_inicio_guerra(context.bot, guerra)
        try:
            await query.edit_message_text(
                _panel_texto(), reply_markup=_panel_teclado(), parse_mode="Markdown"
            )
        except Exception:
            pass
        return

    if data == "pgf_finalizar":
        guerra = _obtener_guerra_activa()
        if not guerra:
            await query.answer("No hay guerra activa.", show_alert=True)
            return
        await query.edit_message_text("⏳ Calculando resultados y distribuyendo recompensas...")
        await _terminar_guerra_impl(context.bot, guerra)
        try:
            await query.edit_message_text(
                _panel_texto(), reply_markup=_panel_teclado(), parse_mode="Markdown"
            )
        except Exception:
            pass
        return

    if data == "pgf_renotificar":
        guerra = _obtener_guerra_activa()
        if not guerra:
            await query.answer("No hay guerra activa para notificar.", show_alert=True)
            return
        try:
            await query.edit_message_text(
                _panel_texto() + "\n\n📢 _Reenviando notificaciones..._",
                reply_markup=_panel_teclado(), parse_mode="Markdown"
            )
        except Exception:
            pass
        await _broadcast_inicio_guerra(context.bot, guerra)
        try:
            await query.edit_message_text(
                _panel_texto() + "\n\n✅ _Notificaciones reenviadas._",
                reply_markup=_panel_teclado(), parse_mode="Markdown"
            )
        except Exception:
            pass
        return

    if data == "pgf_toggle_diaria":
        actual = _cfg("gf_guerra_diaria") == "1"
        nuevo_val = "0" if actual else "1"
        _set_cfg("gf_guerra_diaria", nuevo_val)
        # Sincronizar con la tabla de automatizaciones para que job_auto_guerra lo use
        try:
            import automatizaciones as _auto
            _auto._set("auto_guerra", nuevo_val)
        except Exception:
            pass
        nuevo  = not actual
        await query.answer(f"📅 Guerra diaria {'activada ✅' if nuevo else 'desactivada ❌'}")
        try:
            await query.edit_message_text(
                _panel_texto(), reply_markup=_panel_teclado(), parse_mode="Markdown"
            )
        except Exception:
            pass
        return

    # Ediciones de config numéricas
    _edit_map = {
        "pgf_dur":  ("gf_duracion_minutos", "⏱️ Duración en minutos",      1,   1440),
        "pgf_pta":  ("gf_puntos_ataque",    "⚔️ Puntos por ataque",         1,   500),
        "pgf_ptd":  ("gf_puntos_defensa",   "🛡️ Puntos por defensa",        1,   500),
        "pgf_xp":   ("gf_xp_participacion", "⭐ XP base por participación",  0,  9999),
    }
    if data in _edit_map:
        clave, label, mn, mx = _edit_map[data]
        context.user_data["pgf_clave"]  = clave
        context.user_data["pgf_label"]  = label
        context.user_data["pgf_mn"]     = mn
        context.user_data["pgf_mx"]     = mx
        context.user_data["pgf_edit"]   = True
        await query.edit_message_text(
            f"✏️ *{label}*\n\nValor actual: *{_cfg(clave)}*\nRango válido: {mn}–{mx}\n\n"
            f"Escribe el nuevo valor:",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("❌ Cancelar", callback_data="pgf_refresh")]]
            ),
            parse_mode="Markdown"
        )
        return

    if data == "pgf_rec":
        context.user_data["pgf_edit_rec"] = True
        await query.edit_message_text(
            f"✏️ *Recompensas de guerra (oro)*\n\n"
            f"Valores actuales:\n"
            f"  1er: {_recompensa('1er')} | 2do: {_recompensa('2do')} | "
            f"3er: {_recompensa('3er')} | Resto: {_recompensa('resto')}\n\n"
            f"Escribe en formato:\n`1er:2000 2do:1000 3er:500 resto:200`",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("❌ Cancelar", callback_data="pgf_refresh")]]
            ),
            parse_mode="Markdown"
        )
        return

    if data == "pgf_hora":
        context.user_data["pgf_edit_hora"] = True
        await query.edit_message_text(
            f"✏️ *Hora de guerra diaria*\n\nValor actual: *{_cfg('gf_hora_diaria')}*\n\n"
            f"Escribe la hora en formato HH:MM (ej: `14:00`):",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("❌ Cancelar", callback_data="pgf_refresh")]]
            ),
            parse_mode="Markdown"
        )
        return


async def pgf_recibir_texto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recibe los valores de configuración del panel de guerras."""
    user_id = update.effective_user.id
    if not sa._es_admin(user_id):
        return
    texto = update.effective_message.text.strip()

    if context.user_data.get("pgf_edit_rec"):
        context.user_data.pop("pgf_edit_rec", None)
        try:
            partes = {}
            for par in texto.split():
                k, v = par.split(":")
                partes[k.strip().lower()] = int(v.strip())
            for pos in ["1er", "2do", "3er", "resto"]:
                if pos in partes:
                    _set_cfg(f"gf_recompensa_{pos}", partes[pos])
            await update.effective_message.reply_text("✅ Recompensas actualizadas.")
        except Exception:
            await update.effective_message.reply_text(
                "❌ Formato inválido. Usa: `1er:2000 2do:1000 3er:500 resto:200`",
                parse_mode="Markdown"
            )
        await update.effective_message.reply_text(
            _panel_texto(), reply_markup=_panel_teclado(), parse_mode="Markdown"
        )
        return

    if context.user_data.get("pgf_edit_hora"):
        context.user_data.pop("pgf_edit_hora", None)
        import re
        if re.match(r"^\d{2}:\d{2}$", texto):
            _set_cfg("gf_hora_diaria", texto)
            await update.effective_message.reply_text(f"✅ Hora diaria establecida a *{texto}*.", parse_mode="Markdown")
        else:
            await update.effective_message.reply_text("❌ Formato inválido. Usa HH:MM (ej: `14:00`)", parse_mode="Markdown")
        await update.effective_message.reply_text(
            _panel_texto(), reply_markup=_panel_teclado(), parse_mode="Markdown"
        )
        return

    if context.user_data.get("pgf_edit"):
        clave = context.user_data.pop("pgf_clave",  None)
        label = context.user_data.pop("pgf_label",  "Valor")
        mn    = context.user_data.pop("pgf_mn",     0)
        mx    = context.user_data.pop("pgf_mx",     99999)
        context.user_data.pop("pgf_edit", None)
        if not clave:
            return
        try:
            val = int(texto)
            if not (mn <= val <= mx):
                raise ValueError
        except ValueError:
            await update.effective_message.reply_text(
                f"❌ Valor inválido. Debe estar entre {mn} y {mx}.")
            return
        _set_cfg(clave, val)
        await update.effective_message.reply_text(
            f"✅ *{label}* → *{val}*", parse_mode="Markdown"
        )
        await update.effective_message.reply_text(
            _panel_texto(), reply_markup=_panel_teclado(), parse_mode="Markdown"
        )


# ==================== FUNCIONES PARA AUTOMATIZACIONES ====================
def iniciar_guerra_automatica(iniciada_por: int = 0) -> Optional[Dict]:
    return _crear_guerra(iniciada_por)

async def terminar_guerra_automatica(guerra: dict, bot):
    await _terminar_guerra_impl(bot, guerra)


# ==================== REGISTRO DE HANDLERS ====================
def registrar_handlers(app):
    global _app
    _app = app

    # Admin — panel de guerra
    app.add_handler(CommandHandler("panel_guerras",              cmd_panel_guerras))
    app.add_handler(CallbackQueryHandler(cb_panel_guerras,       pattern="^pgf_"))

    # Admin — comandos clásicos
    app.add_handler(CommandHandler("guerra_facciones_iniciar",   cmd_guerra_facciones_iniciar))
    app.add_handler(CommandHandler("guerra_facciones_finalizar", cmd_guerra_facciones_finalizar))

    # Jugadores
    app.add_handler(CommandHandler("guerra_facciones_atacar",    cmd_guerra_facciones_atacar))
    app.add_handler(CommandHandler("guerra_facciones_defender",  cmd_guerra_facciones_defender))
    app.add_handler(CommandHandler("guerra_facciones_estado",    cmd_guerra_facciones_estado))
    app.add_handler(CommandHandler("guerra_facciones_ranking",   cmd_guerra_facciones_ranking))
    app.add_handler(CommandHandler("saltar_guerra",              cmd_saltar_guerra))

    # Callbacks de los botones persistentes (mensajes enviados a jugadores)
    app.add_handler(CallbackQueryHandler(cb_gf, pattern="^gf_"))

    # Recibir texto de configuración del panel (valida internamente con user_data)
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        pgf_recibir_texto
    ), group=10)

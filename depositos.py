"""
Sistema de Créditos del Vacío — Depósitos y Retiros USDT (paso a paso)
=======================================================================
DEPÓSITO (USDT → Créditos):
  1. Jugador solicita → admin aprueba → wallet revelada al jugador
  2. Jugador envía dinero → pulsa "Ya envié"
  3. Admin verifica → libera los créditos

RETIRO (Créditos → USDT):
  1. Jugador solicita con su wallet BSC → admin aprueba → créditos descontados
  2. Admin envía USDT manualmente → marca como completado
  Comisión: 20% (el jugador recibe el 80%)
"""

import sqlite3
import os
import datetime
import db_helper

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, CommandHandler, CallbackQueryHandler,
    ConversationHandler, MessageHandler, filters
)

# ==================== CONFIGURACIÓN ====================

DB_PATH       = os.path.join(os.path.dirname(__file__), "aethelgard.db")
TASA          = 10       # 1 USDT = 10 créditos
FEE_RETIRO    = 0.20     # 20 % de comisión al retirar
MIN_DEP_USDT  = 5        # Mínimo en USDT para depositar
MIN_RET_CRED  = 50       # Mínimo en créditos para retirar

# Estados del ConversationHandler
DEP_MONTO, DEP_CONFIRMAR = range(2)
RET_MONTO, RET_WALLET, RET_CONFIRMAR = range(3)

# ==================== BASE DE DATOS ====================

def _init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS solicitudes_creditos (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        tipo        TEXT    NOT NULL,           -- 'deposito' | 'retiro'
        user_id     INTEGER NOT NULL,
        cantidad    REAL    NOT NULL,           -- USDT (deposito) | créditos (retiro)
        creditos    INTEGER NOT NULL,           -- créditos a dar/quitar
        usdt_neto   REAL    DEFAULT 0,          -- USDT neto que recibe el jugador (retiro)
        wallet      TEXT    DEFAULT '',         -- Wallet BEP20 del jugador (retiro)
        estado      TEXT    DEFAULT 'pendiente_admin',
        nota        TEXT    DEFAULT '',
        creado      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        actualizado TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS config_creditos (
        clave TEXT PRIMARY KEY,
        valor TEXT
    )''')
    c.execute("INSERT OR IGNORE INTO config_creditos VALUES ('wallet_bsc','No configurada - usa /admin_wallet_bsc')")
    c.execute("INSERT OR IGNORE INTO config_creditos VALUES ('red','BSC BEP20')")
    conn.commit()
    conn.close()

_init_db()


def _cfg(clave: str) -> str:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT valor FROM config_creditos WHERE clave=?", (clave,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else "—"


def _set_cfg(clave: str, valor: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO config_creditos VALUES (?,?)", (clave, valor))
    conn.commit()
    conn.close()


def _crear(tipo, user_id, cantidad, creditos, usdt_neto=0, wallet="") -> int:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO solicitudes_creditos (tipo,user_id,cantidad,creditos,usdt_neto,wallet) VALUES (?,?,?,?,?,?)",
        (tipo, user_id, cantidad, creditos, usdt_neto, wallet)
    )
    sid = c.lastrowid
    conn.commit()
    conn.close()
    return sid


def _get(sid: int) -> dict:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM solicitudes_creditos WHERE id=?", (sid,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def _estado(sid: int, estado: str, nota: str = ""):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "UPDATE solicitudes_creditos SET estado=?, nota=?, actualizado=CURRENT_TIMESTAMP WHERE id=?",
        (estado, nota, sid)
    )
    conn.commit()
    conn.close()


def _dar_creditos(user_id: int, cantidad: int):
    jug = db_helper.obtener_jugador(user_id)
    if jug:
        db_helper.actualizar_jugador(user_id, creditos_vacio=jug.get("creditos_vacio", 0) + cantidad)


def _quitar_creditos(user_id: int, cantidad: int) -> bool:
    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        return False
    actual = jug.get("creditos_vacio", 0)
    if actual < cantidad:
        return False
    db_helper.actualizar_jugador(user_id, creditos_vacio=actual - cantidad)
    return True


def _es_admin(user_id: int) -> bool:
    superadmin = int(os.environ.get("SUPERADMIN_ID", 0))
    if user_id == superadmin:
        return True
    try:
        import superadmin as _sa
        return _sa._nivel_admin(user_id) >= 1
    except Exception:
        return False


# ==================== MENÚ PRINCIPAL DE CRÉDITOS ====================

async def _mostrar_menu_creditos(update_or_query, user_id: int, editar: bool = False):
    jug = db_helper.obtener_jugador(user_id)
    creditos = jug.get("creditos_vacio", 0) if jug else 0
    texto = (
        f"✨ *Créditos del Vacío*\n\n"
        f"Tu saldo: *{creditos} créditos*\n\n"
        f"📈 Tasa: *1 USDT = {TASA} créditos*\n"
        f"📉 Comisión retiro: *20%* (recibes el 80%)\n\n"
        f"¿Qué deseas hacer?"
    )
    keyboard = [
        [InlineKeyboardButton("📤 Depositar USDT",  callback_data="cred_dep_inicio")],
        [InlineKeyboardButton("📥 Retirar USDT",    callback_data="cred_ret_inicio")],
        [InlineKeyboardButton("📋 Mis solicitudes", callback_data="cred_mis_solicitudes")],
        [InlineKeyboardButton("❌ Cerrar",          callback_data="cred_cerrar")],
    ]
    markup = InlineKeyboardMarkup(keyboard)
    if editar:
        await update_or_query.edit_message_text(texto, reply_markup=markup, parse_mode="Markdown")
    else:
        await update_or_query.message.reply_text(texto, reply_markup=markup, parse_mode="Markdown")


async def cmd_creditos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not db_helper.obtener_jugador(user_id):
        await update.effective_message.reply_text("❌ Primero crea un personaje con /start.")
        return
    await _mostrar_menu_creditos(update, user_id, editar=False)


async def creditos_menu_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await _mostrar_menu_creditos(query, query.from_user.id, editar=True)


async def cred_cerrar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        await query.message.delete()
    except Exception:
        await query.edit_message_text("👋 Hasta pronto.")


# ==================== MIS SOLICITUDES ====================

async def cred_mis_solicitudes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM solicitudes_creditos WHERE user_id=? ORDER BY creado DESC LIMIT 8", (user_id,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()

    ICONOS_ESTADO = {
        "pendiente_admin":     "⏳",
        "aceptada_wallet":     "💳",
        "pago_enviado":        "📨",
        "completada":          "✅",
        "rechazada":           "❌",
        "aceptada_procesando": "🔄",
    }
    NOMBRES_ESTADO = {
        "pendiente_admin":     "Esperando aprobación",
        "aceptada_wallet":     "Wallet enviada - pendiente pago",
        "pago_enviado":        "Pago notificado - verificando",
        "completada":          "Completada",
        "rechazada":           "Rechazada",
        "aceptada_procesando": "Aprobada - enviando USDT",
    }

    if not rows:
        texto = "📋 *Mis Solicitudes*\n\nNo tienes solicitudes registradas."
    else:
        lines = ["📋 *Mis Solicitudes (últimas 8):*\n"]
        for r in rows:
            ic = ICONOS_ESTADO.get(r["estado"], "❓")
            nom = NOMBRES_ESTADO.get(r["estado"], r["estado"])
            tipo_icon = "📤" if r["tipo"] == "deposito" else "📥"
            if r["tipo"] == "deposito":
                desc = f"{r['cantidad']} USDT → {r['creditos']} créditos"
            else:
                desc = f"{r['creditos']} créditos → {r['usdt_neto']:.2f} USDT"
            nota = f"\n   _{r['nota']}_" if r.get("nota") else ""
            lines.append(f"{tipo_icon} #{r['id']} — {desc}\n   {ic} {nom}{nota}")
        texto = "\n".join(lines)

    keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="creditos_menu"),
                 InlineKeyboardButton("❌ Cerrar", callback_data="cred_cerrar")]]
    await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")


# ==================== FLUJO DEPÓSITO ====================

async def dep_inicio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Punto de entrada: jugador pulsa Depositar USDT"""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if not db_helper.obtener_jugador(user_id):
        await query.edit_message_text("❌ Primero crea un personaje con /start.")
        return ConversationHandler.END
    await query.edit_message_text(
        f"📤 *Depositar USDT*\n\n"
        f"Tasa: *1 USDT = {TASA} créditos*\n"
        f"Mínimo: *{MIN_DEP_USDT} USDT*\n\n"
        f"¿Cuántos USDT deseas depositar?\n"
        f"_(Escribe solo el número, por ejemplo: `10`)_\n\n"
        f"Escribe /cancelar para salir.",
        parse_mode="Markdown"
    )
    context.user_data["dep_msg_id"] = query.message.message_id
    return DEP_MONTO


async def dep_recibir_monto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Jugador escribe el monto en USDT"""
    texto = update.message.text.strip()
    try:
        monto = float(texto.replace(",", "."))
    except ValueError:
        await update.effective_message.reply_text(
            f"❌ Escribe solo el número. Ejemplo: `{MIN_DEP_USDT}`\nO escribe /cancelar.",
            parse_mode="Markdown"
        )
        return DEP_MONTO

    if monto < MIN_DEP_USDT:
        await update.effective_message.reply_text(
            f"❌ El mínimo es *{MIN_DEP_USDT} USDT*. Escribe otro monto o /cancelar.",
            parse_mode="Markdown"
        )
        return DEP_MONTO

    creditos = int(monto * TASA)
    context.user_data["dep_monto"] = monto
    context.user_data["dep_creditos"] = creditos

    keyboard = [
        [InlineKeyboardButton("✅ Confirmar solicitud", callback_data="dep_confirmar")],
        [InlineKeyboardButton("❌ Cancelar",            callback_data="dep_cancelar")],
    ]
    await update.effective_message.reply_text(
        f"📋 *Confirmar depósito*\n\n"
        f"💵 Enviarás: *{monto} USDT*\n"
        f"✨ Recibirás: *{creditos} Créditos del Vacío*\n\n"
        f"Al confirmar, enviaremos tu solicitud al administrador.\n"
        f"Él la revisará y, si la aprueba, te enviará la dirección de pago.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    return DEP_CONFIRMAR


async def dep_confirmar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Jugador pulsa Confirmar"""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    monto   = context.user_data.get("dep_monto", 0)
    creditos = context.user_data.get("dep_creditos", 0)

    if not monto or not creditos:
        await query.edit_message_text("❌ Error al procesar la solicitud. Inténtalo de nuevo.")
        return ConversationHandler.END

    sid = _crear("deposito", user_id, monto, creditos)
    jug = db_helper.obtener_jugador(user_id)
    nombre = jug["nombre_personaje"] if jug else "?"
    tg_user = query.from_user
    username = f"@{tg_user.username}" if tg_user.username else f"ID:{user_id}"

    # Notificar al admin
    notif_admin_ok = False
    notif_admin_error = ""
    try:
        superadmin_id = int(os.environ.get("SUPERADMIN_ID", 0))
        if superadmin_id:
            kb_admin = [
                [InlineKeyboardButton("✅ Aceptar y enviar wallet", callback_data=f"cadm_dep_ok_{sid}")],
                [InlineKeyboardButton("❌ Rechazar",                callback_data=f"cadm_dep_no_{sid}")],
            ]
            enlace = f"tg://user?id={user_id}"
            await context.bot.send_message(
                superadmin_id,
                f"📤 *Nueva solicitud de depósito #{sid}*\n\n"
                f"👤 Jugador: {nombre} ({username})\n"
                f"🔗 [Contactar]({enlace})\n"
                f"💵 Monto: *{monto} USDT*\n"
                f"✨ Créditos a dar: *{creditos}*\n\n"
                f"Si aceptas, le enviarás tu wallet para que haga el pago.",
                reply_markup=InlineKeyboardMarkup(kb_admin),
                parse_mode="Markdown",
                disable_web_page_preview=True
            )
            notif_admin_ok = True
        else:
            notif_admin_error = "SUPERADMIN_ID no configurado"
    except Exception as e:
        notif_admin_error = str(e)

    if notif_admin_ok:
        estado_notif = "✅ El administrador ha sido notificado."
    elif notif_admin_error:
        estado_notif = f"⚠️ No se pudo notificar al admin: `{notif_admin_error}`\nUsa `/admin_solicitudes_creditos` para revisarla manualmente."
    else:
        estado_notif = "⚠️ El admin no está configurado. Contacta al administrador manualmente."

    await query.edit_message_text(
        f"✅ *Solicitud #{sid} registrada*\n\n"
        f"💵 Monto: {monto} USDT\n"
        f"✨ Créditos a recibir: {creditos}\n\n"
        f"{estado_notif}\n\n"
        f"Puedes ver el estado en *Mis Solicitudes*.",
        parse_mode="Markdown"
    )
    return ConversationHandler.END


async def dep_cancelar_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("❌ Solicitud de depósito cancelada.")
    return ConversationHandler.END


async def dep_cancelar_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text("❌ Operación cancelada.")
    return ConversationHandler.END


# ==================== ADMIN: GESTIÓN DE DEPÓSITOS ====================

async def admin_dep_aceptar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin acepta depósito → envía wallet al jugador"""
    query = update.callback_query
    await query.answer()
    if not _es_admin(query.from_user.id):
        await query.answer("Sin permiso.", show_alert=True)
        return

    try:
        sid = int(query.data.split("_")[-1])
    except (ValueError, IndexError):
        await query.edit_message_text("❌ Error al procesar solicitud.")
        return
    sol = _get(sid)
    if not sol:
        await query.edit_message_text("❌ Solicitud no encontrada.")
        return
    if sol["estado"] != "pendiente_admin":
        await query.edit_message_text(f"⚠️ Estado actual: {sol['estado']}. No se puede aceptar.")
        return

    wallet = _cfg("wallet_bsc")
    red    = _cfg("red")
    _estado(sid, "aceptada_wallet")

    # Enviar wallet al jugador
    kb_jugador = [[InlineKeyboardButton("💸 Ya envié el dinero", callback_data=f"cred_ya_envie_{sid}")]]
    try:
        await context.bot.send_message(
            sol["user_id"],
            f"✅ *¡Tu solicitud de depósito #{sid} fue aprobada!*\n\n"
            f"Envía exactamente *{sol['cantidad']} USDT* a esta dirección:\n\n"
            f"💳 `{wallet}`\n"
            f"🌐 Red: *{red}*\n\n"
            f"⚠️ Asegúrate de enviar en la red correcta.\n"
            f"Cuando hayas enviado el dinero, pulsa el botón de abajo.",
            reply_markup=InlineKeyboardMarkup(kb_jugador),
            parse_mode="Markdown"
        )
    except Exception:
        pass

    jug = db_helper.obtener_jugador(sol["user_id"])
    nombre = jug["nombre_personaje"] if jug else "?"
    await query.edit_message_text(
        f"✅ Solicitud #{sid} aprobada.\n"
        f"Wallet enviada a {nombre}. Esperando que confirme el pago."
    )


async def admin_dep_rechazar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin rechaza depósito"""
    query = update.callback_query
    await query.answer()
    if not _es_admin(query.from_user.id):
        await query.answer("Sin permiso.", show_alert=True)
        return

    try:
        sid = int(query.data.split("_")[-1])
    except (ValueError, IndexError):
        await query.edit_message_text("❌ Error al procesar solicitud.")
        return
    sol = _get(sid)
    if not sol:
        await query.edit_message_text("❌ Solicitud no encontrada.")
        return

    _estado(sid, "rechazada", "Rechazada por el administrador")
    try:
        await context.bot.send_message(
            sol["user_id"],
            f"❌ *Tu solicitud de depósito #{sid} fue rechazada.*\n\n"
            f"Puedes intentarlo de nuevo o contactar al administrador.",
            parse_mode="Markdown"
        )
    except Exception:
        pass

    await query.edit_message_text(f"❌ Solicitud #{sid} rechazada.")


async def cred_ya_envie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Jugador pulsa 'Ya envié el dinero'"""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    try:
        sid = int(query.data.split("_")[-1])
    except (ValueError, IndexError):
        await query.answer("❌ Error al procesar solicitud.", show_alert=True)
        return
    sol = _get(sid)

    if not sol or sol["user_id"] != user_id:
        await query.answer("Solicitud no encontrada.", show_alert=True)
        return
    if sol["estado"] != "aceptada_wallet":
        await query.answer(f"Estado: {sol['estado']}", show_alert=True)
        return

    _estado(sid, "pago_enviado")

    # Notificar al admin para verificar
    try:
        superadmin_id = int(os.environ.get("SUPERADMIN_ID", 0))
        if superadmin_id:
            jug = db_helper.obtener_jugador(user_id)
            nombre = jug["nombre_personaje"] if jug else "?"
            tg_user = query.from_user
            username = f"@{tg_user.username}" if tg_user.username else f"ID:{user_id}"
            enlace = f"tg://user?id={user_id}"
            kb_admin = [
                [InlineKeyboardButton("✅ Verificado - Liberar créditos", callback_data=f"cadm_dep_lib_{sid}")],
                [InlineKeyboardButton("❌ No recibido / Problema",        callback_data=f"cadm_dep_nopag_{sid}")],
            ]
            await context.bot.send_message(
                superadmin_id,
                f"📨 *Pago notificado — Solicitud #{sid}*\n\n"
                f"👤 {nombre} ({username})\n"
                f"🔗 [Contactar]({enlace})\n"
                f"💵 Monto: *{sol['cantidad']} USDT*\n"
                f"✨ Créditos a liberar: *{sol['creditos']}*\n\n"
                f"El jugador dice que ya envió el dinero.\n"
                f"Verifica en tu wallet y luego libera los créditos.",
                reply_markup=InlineKeyboardMarkup(kb_admin),
                parse_mode="Markdown",
                disable_web_page_preview=True
            )
    except Exception:
        pass

    await query.edit_message_text(
        f"📨 *Pago notificado - Solicitud #{sid}*\n\n"
        f"Hemos avisado al administrador. En cuanto verifique\n"
        f"que recibió el pago, te llegará un mensaje con los\n"
        f"*{sol['creditos']} Créditos del Vacío*.\n\n"
        f"Tiempo estimado: menos de 24 horas.",
        parse_mode="Markdown"
    )


async def admin_dep_liberar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin libera créditos tras verificar el pago"""
    query = update.callback_query
    await query.answer()
    if not _es_admin(query.from_user.id):
        await query.answer("Sin permiso.", show_alert=True)
        return

    try:
        sid = int(query.data.split("_")[-1])
    except (ValueError, IndexError):
        await query.edit_message_text("❌ Error al procesar solicitud.")
        return
    sol = _get(sid)
    if not sol:
        await query.edit_message_text("❌ Solicitud no encontrada.")
        return
    if sol["estado"] != "pago_enviado":
        await query.edit_message_text(f"⚠️ Estado actual: {sol['estado']}.")
        return

    _dar_creditos(sol["user_id"], sol["creditos"])
    _estado(sid, "completada")

    jug = db_helper.obtener_jugador(sol["user_id"])
    nombre = jug["nombre_personaje"] if jug else "?"
    nuevos = jug.get("creditos_vacio", 0) if jug else 0

    try:
        await context.bot.send_message(
            sol["user_id"],
            f"💎 *¡Depósito completado!*\n\n"
            f"Se han añadido *{sol['creditos']} Créditos del Vacío* a tu cuenta.\n"
            f"Saldo total: *{nuevos} créditos*\n\n"
            f"¡Gracias por depositar! Solicitud #{sid}.",
            parse_mode="Markdown"
        )
    except Exception:
        pass

    await query.edit_message_text(
        f"✅ Solicitud #{sid} completada.\n"
        f"+{sol['creditos']} créditos → {nombre} (Total: {nuevos})"
    )


async def admin_dep_nopago(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin marca pago como no recibido"""
    query = update.callback_query
    await query.answer()
    if not _es_admin(query.from_user.id):
        await query.answer("Sin permiso.", show_alert=True)
        return

    try:
        sid = int(query.data.split("_")[-1])
    except (ValueError, IndexError):
        await query.edit_message_text("❌ Error al procesar solicitud.")
        return
    sol = _get(sid)
    if not sol:
        await query.edit_message_text("❌ Solicitud no encontrada.")
        return

    _estado(sid, "rechazada", "Pago no verificado por el administrador")
    try:
        await context.bot.send_message(
            sol["user_id"],
            f"⚠️ *Problema con tu depósito #{sid}*\n\n"
            f"El administrador no pudo verificar el pago de {sol['cantidad']} USDT.\n"
            f"Por favor, contacta al administrador para resolverlo.",
            parse_mode="Markdown"
        )
    except Exception:
        pass

    await query.edit_message_text(f"⚠️ Solicitud #{sid} marcada como pago no verificado.")


# ==================== FLUJO RETIRO ====================

async def ret_inicio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Punto de entrada: jugador pulsa Retirar USDT"""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        await query.edit_message_text("❌ Primero crea un personaje con /start.")
        return ConversationHandler.END

    creditos = jug.get("creditos_vacio", 0)
    usdt_ejemplo = (MIN_RET_CRED / TASA) * (1 - FEE_RETIRO)

    await query.edit_message_text(
        f"📥 *Retirar USDT*\n\n"
        f"Tu saldo: *{creditos} créditos*\n"
        f"Tasa: *{TASA} créditos = 1 USDT*\n"
        f"Comisión: *20%* (recibes el 80%)\n"
        f"Mínimo: *{MIN_RET_CRED} créditos* (= {usdt_ejemplo:.1f} USDT netos)\n\n"
        f"¿Cuántos créditos deseas retirar?\n"
        f"_(Escribe solo el número, por ejemplo: `100`)_\n\n"
        f"Escribe /cancelar para salir.",
        parse_mode="Markdown"
    )
    return RET_MONTO


async def ret_recibir_monto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Jugador escribe cuántos créditos retirar"""
    texto = update.message.text.strip()
    try:
        cred = int(texto.replace(",", "").replace(".", ""))
    except ValueError:
        await update.effective_message.reply_text(
            f"❌ Escribe solo el número. Ejemplo: `100`\nO /cancelar.",
            parse_mode="Markdown"
        )
        return RET_MONTO

    user_id = update.effective_user.id
    jug = db_helper.obtener_jugador(user_id)
    disponibles = jug.get("creditos_vacio", 0) if jug else 0

    if cred < MIN_RET_CRED:
        await update.effective_message.reply_text(
            f"❌ El mínimo son *{MIN_RET_CRED} créditos*. Escribe otro monto o /cancelar.",
            parse_mode="Markdown"
        )
        return RET_MONTO

    if cred > disponibles:
        await update.effective_message.reply_text(
            f"❌ No tienes suficientes créditos. Tienes *{disponibles}*. Escribe otro monto o /cancelar.",
            parse_mode="Markdown"
        )
        return RET_MONTO

    usdt_bruto = cred / TASA
    usdt_neto  = round(usdt_bruto * (1 - FEE_RETIRO), 2)
    context.user_data["ret_creditos"] = cred
    context.user_data["ret_usdt_neto"] = usdt_neto

    await update.effective_message.reply_text(
        f"📋 *Resumen del retiro:*\n"
        f"✨ Créditos a retirar: *{cred}*\n"
        f"💵 USDT bruto: {usdt_bruto:.2f}\n"
        f"📉 Comisión (20%): -{usdt_bruto * FEE_RETIRO:.2f} USDT\n"
        f"💵 USDT que recibirás: *{usdt_neto:.2f} USDT*\n\n"
        f"¿A qué dirección BSC BEP20 quieres recibir el USDT?\n"
        f"_(Escribe tu wallet, por ejemplo: `0x123...abc`)_\n\n"
        f"Escribe /cancelar para salir.",
        parse_mode="Markdown"
    )
    return RET_WALLET


async def ret_recibir_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Jugador escribe su wallet BSC"""
    wallet = update.message.text.strip()
    if len(wallet) < 10:
        await update.effective_message.reply_text(
            "❌ Dirección inválida. Escribe una wallet BSC BEP20 válida o /cancelar."
        )
        return RET_WALLET

    context.user_data["ret_wallet"] = wallet
    cred      = context.user_data.get("ret_creditos", 0)
    usdt_neto = context.user_data.get("ret_usdt_neto", 0)

    keyboard = [
        [InlineKeyboardButton("✅ Confirmar retiro", callback_data="ret_confirmar")],
        [InlineKeyboardButton("❌ Cancelar",         callback_data="ret_cancelar")],
    ]
    await update.effective_message.reply_text(
        f"📋 *Confirmar retiro*\n\n"
        f"✨ Créditos a descontar: *{cred}*\n"
        f"💵 USDT a recibir: *{usdt_neto:.2f} USDT*\n"
        f"🌐 Red: *BSC BEP20*\n"
        f"💳 Tu wallet:\n`{wallet}`\n\n"
        f"Al confirmar, tu solicitud irá al administrador.\n"
        f"Los créditos se descontarán al ser aprobada.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    return RET_CONFIRMAR


async def ret_confirmar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Jugador confirma el retiro"""
    query = update.callback_query
    await query.answer()
    user_id  = query.from_user.id
    cred     = context.user_data.get("ret_creditos", 0)
    usdt_neto = context.user_data.get("ret_usdt_neto", 0)
    wallet   = context.user_data.get("ret_wallet", "")

    if not cred or not wallet:
        await query.edit_message_text("❌ Error al procesar. Inténtalo de nuevo.")
        return ConversationHandler.END

    sid = _crear("retiro", user_id, cred, cred, usdt_neto=usdt_neto, wallet=wallet)
    jug = db_helper.obtener_jugador(user_id)
    nombre = jug["nombre_personaje"] if jug else "?"
    tg_user = query.from_user
    username = f"@{tg_user.username}" if tg_user.username else f"ID:{user_id}"

    # Notificar al admin
    try:
        superadmin_id = int(os.environ.get("SUPERADMIN_ID", 0))
        if superadmin_id:
            enlace = f"tg://user?id={user_id}"
            kb_admin = [
                [InlineKeyboardButton("✅ Aceptar solicitud", callback_data=f"cadm_ret_ok_{sid}")],
                [InlineKeyboardButton("❌ Rechazar",          callback_data=f"cadm_ret_no_{sid}")],
            ]
            await context.bot.send_message(
                superadmin_id,
                f"📥 *Nueva solicitud de retiro #{sid}*\n\n"
                f"👤 {nombre} ({username})\n"
                f"🔗 [Contactar]({enlace})\n"
                f"✨ Créditos a descontar: *{cred}*\n"
                f"💵 USDT a enviar: *{usdt_neto:.2f} USDT (BSC BEP20)*\n"
                f"💳 Wallet del jugador:\n`{wallet}`\n\n"
                f"Si aceptas, los créditos se descuentan inmediatamente\n"
                f"y debes enviar el USDT manualmente.",
                reply_markup=InlineKeyboardMarkup(kb_admin),
                parse_mode="Markdown",
                disable_web_page_preview=True
            )
    except Exception:
        pass

    await query.edit_message_text(
        f"✅ *Solicitud de retiro #{sid} enviada*\n\n"
        f"✨ Créditos: {cred}\n"
        f"💵 Recibirás: {usdt_neto:.2f} USDT\n"
        f"💳 A tu wallet: `{wallet}`\n\n"
        f"El administrador revisará tu solicitud.\n"
        f"Puedes ver el estado en *Mis Solicitudes*.",
        parse_mode="Markdown"
    )
    return ConversationHandler.END


async def ret_cancelar_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("❌ Solicitud de retiro cancelada.")
    return ConversationHandler.END


async def ret_cancelar_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text("❌ Operación cancelada.")
    return ConversationHandler.END


# ==================== ADMIN: GESTIÓN DE RETIROS ====================

async def admin_ret_aceptar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin acepta retiro → descuenta créditos, debe enviar USDT"""
    query = update.callback_query
    await query.answer()
    if not _es_admin(query.from_user.id):
        await query.answer("Sin permiso.", show_alert=True)
        return

    try:
        sid = int(query.data.split("_")[-1])
    except (ValueError, IndexError):
        await query.edit_message_text("❌ Error al procesar solicitud.")
        return
    sol = _get(sid)
    if not sol:
        await query.edit_message_text("❌ Solicitud no encontrada.")
        return
    if sol["estado"] != "pendiente_admin":
        await query.edit_message_text(f"⚠️ Estado actual: {sol['estado']}.")
        return

    # Descontar créditos
    if not _quitar_creditos(sol["user_id"], sol["creditos"]):
        await query.edit_message_text(
            f"❌ El jugador no tiene suficientes créditos ({sol['creditos']})."
        )
        _estado(sid, "rechazada", "Saldo insuficiente al aceptar")
        return

    _estado(sid, "aceptada_procesando")

    jug = db_helper.obtener_jugador(sol["user_id"])
    nombre = jug["nombre_personaje"] if jug else "?"
    nuevos = jug.get("creditos_vacio", 0) if jug else 0

    # Botón para el admin de marcar como completado
    kb_completar = [[InlineKeyboardButton("✅ Marcar como enviado", callback_data=f"cadm_ret_done_{sid}")]]

    try:
        await context.bot.send_message(
            sol["user_id"],
            f"✅ *Tu solicitud de retiro #{sid} fue aprobada*\n\n"
            f"Se descontaron *{sol['creditos']} créditos* de tu cuenta.\n"
            f"Saldo restante: *{nuevos} créditos*\n\n"
            f"Recibirás *{sol['usdt_neto']:.2f} USDT* en tu wallet:\n"
            f"`{sol['wallet']}`\n\n"
            f"El envío se procesará en breve. Te avisaremos cuando se complete.",
            parse_mode="Markdown"
        )
    except Exception:
        pass

    await query.edit_message_text(
        f"✅ Solicitud #{sid} aceptada.\n"
        f"Créditos descontados de {nombre}.\n\n"
        f"Envía *{sol['usdt_neto']:.2f} USDT* a:\n`{sol['wallet']}`\n\n"
        f"Cuando lo hayas enviado, marca como completado:",
        reply_markup=InlineKeyboardMarkup(kb_completar),
        parse_mode="Markdown"
    )


async def admin_ret_rechazar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin rechaza retiro"""
    query = update.callback_query
    await query.answer()
    if not _es_admin(query.from_user.id):
        await query.answer("Sin permiso.", show_alert=True)
        return

    try:
        sid = int(query.data.split("_")[-1])
    except (ValueError, IndexError):
        await query.edit_message_text("❌ Error al procesar solicitud.")
        return
    sol = _get(sid)
    if not sol:
        await query.edit_message_text("❌ Solicitud no encontrada.")
        return

    _estado(sid, "rechazada", "Rechazada por el administrador")
    try:
        await context.bot.send_message(
            sol["user_id"],
            f"❌ *Tu solicitud de retiro #{sid} fue rechazada.*\n\n"
            f"Tus créditos NO fueron descontados.\n"
            f"Contacta al administrador si tienes dudas.",
            parse_mode="Markdown"
        )
    except Exception:
        pass

    await query.edit_message_text(f"❌ Solicitud #{sid} rechazada.")


async def admin_ret_completar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin marca retiro como completado (USDT enviado)"""
    query = update.callback_query
    await query.answer()
    if not _es_admin(query.from_user.id):
        await query.answer("Sin permiso.", show_alert=True)
        return

    try:
        sid = int(query.data.split("_")[-1])
    except (ValueError, IndexError):
        await query.edit_message_text("❌ Error al procesar solicitud.")
        return
    sol = _get(sid)
    if not sol:
        await query.edit_message_text("❌ Solicitud no encontrada.")
        return
    if sol["estado"] != "aceptada_procesando":
        await query.edit_message_text(f"⚠️ Estado actual: {sol['estado']}.")
        return

    _estado(sid, "completada")
    try:
        await context.bot.send_message(
            sol["user_id"],
            f"💵 *¡Tu retiro #{sid} fue completado!*\n\n"
            f"Se enviaron *{sol['usdt_neto']:.2f} USDT* a tu wallet:\n"
            f"`{sol['wallet']}`\n\n"
            f"Si no lo recibes en las próximas horas, contacta al administrador.",
            parse_mode="Markdown"
        )
    except Exception:
        pass

    jug = db_helper.obtener_jugador(sol["user_id"])
    nombre = jug["nombre_personaje"] if jug else "?"
    await query.edit_message_text(
        f"✅ Retiro #{sid} marcado como completado.\n"
        f"{sol['usdt_neto']:.2f} USDT enviados a {nombre}."
    )


# ==================== COMANDOS ADMIN ADICIONALES ====================

async def cmd_admin_wallet_bsc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _es_admin(update.effective_user.id):
        await update.effective_message.reply_text("❌ Sin permiso.")
        return
    if not context.args:
        wallet = _cfg("wallet_bsc")
        red    = _cfg("red")
        await update.effective_message.reply_text(
            f"💳 *Wallet de recepción (depósitos):*\n`{wallet}`\n"
            f"🌐 Red: {red}\n\n"
            f"Cambiar wallet: `/admin_wallet_bsc <dirección>`\n"
            f"Cambiar red: `/admin_wallet_red <red>`",
            parse_mode="Markdown"
        )
        return
    nueva = context.args[0]
    _set_cfg("wallet_bsc", nueva)
    await update.effective_message.reply_text(f"✅ Wallet de recepción actualizada:\n`{nueva}`", parse_mode="Markdown")


async def cmd_admin_wallet_red(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _es_admin(update.effective_user.id):
        await update.effective_message.reply_text("❌ Sin permiso.")
        return
    if not context.args:
        await update.effective_message.reply_text("Uso: `/admin_wallet_red <red>`\nEjemplo: `BSC BEP20`", parse_mode="Markdown")
        return
    red = " ".join(context.args)
    _set_cfg("red", red)
    await update.effective_message.reply_text(f"✅ Red actualizada: {red}")


async def cmd_admin_creditar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _es_admin(update.effective_user.id):
        await update.effective_message.reply_text("❌ Sin permiso.")
        return
    if len(context.args) < 2:
        await update.effective_message.reply_text("Uso: `/admin_creditar <user_id> <creditos>`", parse_mode="Markdown")
        return
    try:
        target = int(context.args[0])
        cant   = int(context.args[1])
    except ValueError:
        await update.effective_message.reply_text("❌ Parámetros inválidos.")
        return
    jug = db_helper.obtener_jugador(target)
    if not jug:
        await update.effective_message.reply_text("❌ Jugador no encontrado.")
        return
    _dar_creditos(target, cant)
    jug2 = db_helper.obtener_jugador(target)
    nuevos = jug2.get("creditos_vacio", 0) if jug2 else 0
    await update.effective_message.reply_text(f"✅ +{cant} créditos → {jug['nombre_personaje']} (Total: {nuevos})")
    try:
        await context.bot.send_message(target,
            f"✨ *Recibiste {cant} Créditos del Vacío* (admin).\nTotal: {nuevos}.",
            parse_mode="Markdown"
        )
    except Exception:
        pass


async def cmd_admin_solicitudes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _es_admin(update.effective_user.id):
        await update.effective_message.reply_text("❌ Sin permiso.")
        return
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM solicitudes_creditos WHERE estado NOT IN ('completada','rechazada') ORDER BY creado")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    if not rows:
        await update.effective_message.reply_text("✅ No hay solicitudes pendientes.")
        return
    lines = [f"📋 *Solicitudes activas ({len(rows)}):*\n"]
    for r in rows:
        jug = db_helper.obtener_jugador(r["user_id"])
        nombre = jug["nombre_personaje"] if jug else "?"
        tipo = "📤 Depósito" if r["tipo"] == "deposito" else "📥 Retiro"
        lines.append(f"#{r['id']} {tipo} — {nombre}\n   Estado: {r['estado']}\n   Creado: {r['creado'][:16]}")
    await update.effective_message.reply_text("\n".join(lines), parse_mode="Markdown")


async def _depositos_nav_cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fallback de navegación para ConversationHandlers de depósitos."""
    for k in ("dep_monto", "ret_monto", "ret_wallet"):
        context.user_data.pop(k, None)
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
    if update.effective_message:
        await update.effective_message.reply_text("❌ Operación cancelada.")
    return ConversationHandler.END

# ==================== REGISTRO ====================

def registrar_handlers(app):
    # Menú principal de créditos
    app.add_handler(CommandHandler("creditos", cmd_creditos))
    app.add_handler(CallbackQueryHandler(creditos_menu_cb,     pattern="^creditos_menu$"))
    app.add_handler(CallbackQueryHandler(cred_cerrar,          pattern="^cred_cerrar$"))
    app.add_handler(CallbackQueryHandler(cred_mis_solicitudes, pattern="^cred_mis_solicitudes$"))

    # Jugador: "Ya envié el dinero" (depósito)
    app.add_handler(CallbackQueryHandler(cred_ya_envie, pattern=r"^cred_ya_envie_\d+$"))

    # Conversación de DEPÓSITO
    _DEP_NAV = [
        CommandHandler("cancelar",   dep_cancelar_cmd),
        CallbackQueryHandler(dep_cancelar_cb, pattern="^dep_cancelar$"),
        CommandHandler("cancel",     _depositos_nav_cancelar),
        CommandHandler("ciudad",     _depositos_nav_cancelar),
        CommandHandler("perfil",     _depositos_nav_cancelar),
        CommandHandler("viajar",     _depositos_nav_cancelar),
        CommandHandler("inventario", _depositos_nav_cancelar),
        CommandHandler("gremio",     _depositos_nav_cancelar),
        CommandHandler("start",      _depositos_nav_cancelar),
        MessageHandler(filters.Regex("^(👤|🏙️?|🎒|✈️?|⚔️?|🏰|⛏️?|🔍|📋|📖)"), _depositos_nav_cancelar),
    ]
    conv_dep = ConversationHandler(
        entry_points=[CallbackQueryHandler(dep_inicio, pattern="^cred_dep_inicio$")],
        states={
            DEP_MONTO:    [MessageHandler(filters.TEXT & ~filters.COMMAND, dep_recibir_monto)],
            DEP_CONFIRMAR:[CallbackQueryHandler(dep_confirmar,   pattern="^dep_confirmar$"),
                           CallbackQueryHandler(dep_cancelar_cb, pattern="^dep_cancelar$")],
        },
        fallbacks=_DEP_NAV,
        per_message=False,
        allow_reentry=True,
    )
    app.add_handler(conv_dep)

    # Conversación de RETIRO
    conv_ret = ConversationHandler(
        entry_points=[CallbackQueryHandler(ret_inicio, pattern="^cred_ret_inicio$")],
        states={
            RET_MONTO:    [MessageHandler(filters.TEXT & ~filters.COMMAND, ret_recibir_monto)],
            RET_WALLET:   [MessageHandler(filters.TEXT & ~filters.COMMAND, ret_recibir_wallet)],
            RET_CONFIRMAR:[CallbackQueryHandler(ret_confirmar,   pattern="^ret_confirmar$"),
                           CallbackQueryHandler(ret_cancelar_cb, pattern="^ret_cancelar$")],
        },
        fallbacks=[
            CommandHandler("cancelar", ret_cancelar_cmd),
            CallbackQueryHandler(ret_cancelar_cb, pattern="^ret_cancelar$"),
            CommandHandler("cancel",     _depositos_nav_cancelar),
            CommandHandler("ciudad",     _depositos_nav_cancelar),
            CommandHandler("perfil",     _depositos_nav_cancelar),
            CommandHandler("viajar",     _depositos_nav_cancelar),
            CommandHandler("inventario", _depositos_nav_cancelar),
            CommandHandler("gremio",     _depositos_nav_cancelar),
            CommandHandler("start",      _depositos_nav_cancelar),
            MessageHandler(filters.Regex("^(👤|🏙️?|🎒|✈️?|⚔️?|🏰|⛏️?|🔍|📋|📖)"), _depositos_nav_cancelar),
        ],
        per_message=False,
        allow_reentry=True,
    )
    app.add_handler(conv_ret)

    # Acciones de ADMIN — depósitos
    app.add_handler(CallbackQueryHandler(admin_dep_aceptar, pattern=r"^cadm_dep_ok_\d+$"))
    app.add_handler(CallbackQueryHandler(admin_dep_rechazar, pattern=r"^cadm_dep_no_\d+$"))
    app.add_handler(CallbackQueryHandler(admin_dep_liberar,  pattern=r"^cadm_dep_lib_\d+$"))
    app.add_handler(CallbackQueryHandler(admin_dep_nopago,   pattern=r"^cadm_dep_nopag_\d+$"))

    # Acciones de ADMIN — retiros
    app.add_handler(CallbackQueryHandler(admin_ret_aceptar,  pattern=r"^cadm_ret_ok_\d+$"))
    app.add_handler(CallbackQueryHandler(admin_ret_rechazar, pattern=r"^cadm_ret_no_\d+$"))
    app.add_handler(CallbackQueryHandler(admin_ret_completar,pattern=r"^cadm_ret_done_\d+$"))

    # Comandos admin
    app.add_handler(CommandHandler("admin_wallet_bsc",   cmd_admin_wallet_bsc))
    app.add_handler(CommandHandler("admin_wallet_red",   cmd_admin_wallet_red))
    app.add_handler(CommandHandler("admin_creditar",     cmd_admin_creditar))
    app.add_handler(CommandHandler("admin_solicitudes_creditos", cmd_admin_solicitudes))

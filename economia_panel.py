"""
economia_panel.py
Panel interactivo para administradores: gestión de tasas de la Bolsa de Valores
y precios de todas las tiendas del juego (Oro, Eternium, Créditos).
"""

import sqlite3
import os

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, CallbackQueryHandler, ConversationHandler,
    MessageHandler, filters, CommandHandler,
)

import db_helper

DB_PATH = "aethelgard.db"

def _esc_md(s: str) -> str:
    return str(s).replace("_", "\\_").replace("*", "\\*").replace("`", "\\`").replace("[", "\\[")

# ─── Estado del ConversationHandler ──────────────────────────────────────────
EP_ESPERANDO = 0

# ─── Items por página en la lista de tienda ──────────────────────────────────
ITEMS_POR_PAGINA = 8

# ─── Guard de permisos ───────────────────────────────────────────────────────
def _es_admin(user_id: int) -> bool:
    try:
        import superadmin as _sa
        return _sa._nivel_admin(user_id) >= 1
    except Exception:
        return user_id == int(os.environ.get("SUPERADMIN_ID", 0))


# ═══════════════════════════════════════════════════════════════════════════════
# BOLSA DE VALORES
# ═══════════════════════════════════════════════════════════════════════════════

_BOLSA_DEFAULTS = {
    "tasa_oro_a_eternium":     500,
    "tasa_eternium_a_oro":     300,
    "tasa_credito_a_eternium": 2,
}
_BOLSA_LABELS = {
    "tasa_oro_a_eternium":     ("🪙→💎", "Oro necesario para comprar 1 Eternium"),
    "tasa_eternium_a_oro":     ("💎→🪙", "Oro que da 1 Eternium al vender"),
    "tasa_credito_a_eternium": ("✨→💎", "Eternium que da 1 Crédito"),
}


def _leer_bolsa() -> dict:
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT clave, valor FROM bolsa_config")
        rows = c.fetchall()
        conn.close()
        return {k: float(v) for k, v in rows}
    except Exception:
        return {}


def _guardar_bolsa(clave: str, valor: float):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT OR REPLACE INTO bolsa_config (clave, valor) VALUES (?,?)",
        (clave, valor)
    )
    conn.commit()
    conn.close()


def _fmt_num(v) -> str:
    f = float(v)
    return str(int(f)) if f == int(f) else str(round(f, 4))


def _texto_bolsa(tasas: dict) -> str:
    lines = ["💱 *BOLSA DE VALORES — Tasas actuales*\n"]
    for clave, (icono, desc) in _BOLSA_LABELS.items():
        val = tasas.get(clave, _BOLSA_DEFAULTS[clave])
        lines.append(f"{icono}  {desc}: *{_fmt_num(val)}*")
    lines.append("\n✏️ Pulsa una tasa para editarla.")
    return "\n".join(lines)


def _kb_bolsa(tasas: dict) -> InlineKeyboardMarkup:
    rows = []
    for clave, (icono, desc) in _BOLSA_LABELS.items():
        val = tasas.get(clave, _BOLSA_DEFAULTS[clave])
        rows.append([InlineKeyboardButton(
            f"✏️ {icono} {desc}: {_fmt_num(val)}",
            callback_data=f"ep_bolsa_ed_{clave}"
        )])
    rows.append([InlineKeyboardButton("🔙 Menú principal", callback_data="ep_menu")])
    return InlineKeyboardMarkup(rows)


# ═══════════════════════════════════════════════════════════════════════════════
# TIENDAS
# ═══════════════════════════════════════════════════════════════════════════════

_TIENDAS = {
    "oro": ("🪙", "Tienda de Oro",     "precio_oro",      "oro"),
    "eth": ("💎", "Tienda de Eternium","precio_eternium",  "eth"),
    "cr":  ("🔮", "Tienda de Créditos","precio_creditos",  "cr"),
}

_MONEDAS_CAMPOS = {
    "oro": "precio_oro",
    "eth": "precio_eternium",
    "cr":  "precio_creditos",
}


def _catalogo(tipo: str) -> list:
    try:
        import tienda as _t
        if tipo == "oro":
            return list(_t.CATALOGO_ORO)
        if tipo == "eth":
            return list(_t.CATALOGO_ETERNIUM)
        if tipo == "cr":
            return list(_t.OBJETOS_CREDITOS_MAESTROS)
    except Exception:
        pass
    return []


def _precio_actual(item: dict, tipo: str) -> int:
    campo = _TIENDAS[tipo][2]
    return item.get(campo, 0)


def _guardar_precio(item_id: str, moneda: str, valor: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT OR REPLACE INTO stats_overrides_precios (item_id, moneda, valor) VALUES (?,?,?)",
        (item_id, moneda, valor)
    )
    conn.commit()
    conn.close()
    try:
        import admin_stats as _as
        _as._patch_precios()
    except Exception:
        pass


def _kb_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💱 Bolsa de Valores", callback_data="ep_bolsa")],
        [InlineKeyboardButton("🛒 Tiendas",          callback_data="ep_tiendas")],
        [InlineKeyboardButton("❌ Cerrar",            callback_data="ep_cerrar")],
    ])


def _kb_tiendas() -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(f"{em} {lab}", callback_data=f"ep_lista_{tipo}_0")]
            for tipo, (em, lab, *_) in _TIENDAS.items()]
    rows.append([InlineKeyboardButton("🔙 Menú principal", callback_data="ep_menu")])
    return InlineKeyboardMarkup(rows)


def _kb_lista(tipo: str, page: int, cat: list) -> InlineKeyboardMarkup:
    total = len(cat)
    total_pg = max(1, (total + ITEMS_POR_PAGINA - 1) // ITEMS_POR_PAGINA)
    start = page * ITEMS_POR_PAGINA
    items_pg = cat[start:start + ITEMS_POR_PAGINA]
    em, lab, campo, _ = _TIENDAS[tipo]
    rows = []
    for idx, item in enumerate(items_pg):
        global_idx = start + idx
        nombre = item.get("nombre", item.get("id", "?"))[:24]
        precio = item.get(campo, 0)
        rows.append([InlineKeyboardButton(
            f"{nombre}  —  {precio:,}",
            callback_data=f"ep_item_{tipo}_{global_idx}"
        )])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️", callback_data=f"ep_lista_{tipo}_{page-1}"))
    nav.append(InlineKeyboardButton(f"Pág {page+1}/{total_pg}", callback_data="ep_noop"))
    if page < total_pg - 1:
        nav.append(InlineKeyboardButton("▶️", callback_data=f"ep_lista_{tipo}_{page+1}"))
    rows.append(nav)
    rows.append([
        InlineKeyboardButton(f"⚡ Ajuste masivo", callback_data=f"ep_ajuste_{tipo}"),
        InlineKeyboardButton("🔙 Tiendas",        callback_data="ep_tiendas"),
    ])
    return InlineKeyboardMarkup(rows)


def _kb_item(tipo: str, idx: int) -> InlineKeyboardMarkup:
    cat = _catalogo(tipo)
    em, lab, campo, moneda_tipo = _TIENDAS[tipo]
    rows = []
    monedas_edit = [
        ("oro", "🪙 Precio en Oro"),
        ("eth", "💎 Precio en Eternium"),
        ("cr",  "🔮 Precio en Créditos"),
    ]
    for mon, label in monedas_edit:
        rows.append([InlineKeyboardButton(
            f"✏️ {label}",
            callback_data=f"ep_editar_{tipo}_{idx}_{mon}"
        )])
    pg = idx // ITEMS_POR_PAGINA
    rows.append([InlineKeyboardButton(f"↩️ Lista", callback_data=f"ep_lista_{tipo}_{pg}")])
    return InlineKeyboardMarkup(rows)


def _texto_item(item: dict) -> str:
    nombre = item.get("nombre", item.get("id", "?"))
    tipo   = item.get("tipo", "—")
    nivel  = item.get("nivel", "—")
    p_oro  = item.get("precio_oro", 0)
    v_oro  = item.get("precio_venta_oro", 0)
    p_eth  = item.get("precio_eternium", 0)
    v_eth  = item.get("precio_venta_eternium", 0)
    p_cr   = item.get("precio_creditos", 0)
    return (
        f"🗡️ *{_esc_md(nombre)}*\n"
        f"Tipo: {tipo}  |  Nivel requerido: {nivel}\n\n"
        f"💰 *Precios actuales:*\n"
        f"🪙 Oro: *{p_oro:,}*  (venta: {v_oro:,})\n"
        f"💎 Eternium: *{p_eth:,}*  (venta: {v_eth:,})\n"
        f"🔮 Créditos: *{p_cr:,}*\n\n"
        f"Elige qué precio quieres editar:"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# HANDLER PRINCIPAL DE NAVEGACIÓN (sin estado)
# ═══════════════════════════════════════════════════════════════════════════════

import logging as _logging
_ep_log = _logging.getLogger("economia_panel")

async def _abrir_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Abre el panel desde /panel_economia o botón del panel admin."""
    _ep_log.info(f"[EP] _abrir_panel invocado, data={update.callback_query.data if update.callback_query else 'cmd'}")
    user_id = update.effective_user.id
    if not _es_admin(user_id):
        if update.callback_query:
            await update.callback_query.answer("❌ Sin permisos.", show_alert=True)
        else:
            await update.effective_message.reply_text("❌ Sin permisos.")
        return
    texto = "💹 <b>PANEL — Economía &amp; Tiendas</b>\n\nElige qué quieres gestionar:"
    kb = _kb_menu()
    if update.callback_query:
        try:
            await update.callback_query.answer()
        except Exception:
            pass
        await update.callback_query.edit_message_text(texto, reply_markup=kb, parse_mode="HTML")
    else:
        await update.effective_message.reply_text(texto, reply_markup=kb, parse_mode="HTML")


async def cb_nav(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja todos los callbacks de navegación (sin esperar texto)."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if not _es_admin(user_id):
        await query.answer("❌ Sin permisos.", show_alert=True)
        return

    data = query.data

    if data == "ep_menu":
        await query.edit_message_text(
            "💹 *PANEL — Economía & Tiendas*\n\nElige qué quieres gestionar:",
            reply_markup=_kb_menu(), parse_mode="Markdown"
        )
        return

    if data == "ep_cerrar":
        await query.delete_message()
        return

    if data == "ep_noop":
        return

    if data == "ep_bolsa":
        tasas = _leer_bolsa()
        await query.edit_message_text(
            _texto_bolsa(tasas), reply_markup=_kb_bolsa(tasas), parse_mode="Markdown"
        )
        return

    if data == "ep_tiendas":
        await query.edit_message_text(
            "🛍️ *TIENDAS — ¿Cuál quieres editar?*\n\nElige la tienda:",
            reply_markup=_kb_tiendas(), parse_mode="Markdown"
        )
        return

    if data.startswith("ep_lista_"):
        partes = data.split("_")
        tipo = partes[2]
        page = int(partes[3]) if len(partes) > 3 else 0
        cat  = _catalogo(tipo)
        em, lab, *_ = _TIENDAS.get(tipo, ("🛒", tipo, "", ""))
        await query.edit_message_text(
            f"{em} *{lab}* — {len(cat)} ítems\n\nPulsa un ítem para ver o editar su precio:",
            reply_markup=_kb_lista(tipo, page, cat),
            parse_mode="Markdown"
        )
        return

    if data.startswith("ep_item_"):
        partes = data.split("_")
        tipo = partes[2]
        idx  = int(partes[3])
        cat  = _catalogo(tipo)
        if idx < 0 or idx >= len(cat):
            await query.answer("Ítem no encontrado.", show_alert=True)
            return
        item = cat[idx]
        await query.edit_message_text(
            _texto_item(item), reply_markup=_kb_item(tipo, idx), parse_mode="Markdown"
        )
        return


# ═══════════════════════════════════════════════════════════════════════════════
# CONVERSACIÓN: editar valor (bolsa, precio individual, ajuste masivo)
# ═══════════════════════════════════════════════════════════════════════════════

async def cb_edit_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry point del ConversationHandler: el admin pulsó un botón de edición."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if not _es_admin(user_id):
        await query.answer("❌ Sin permisos.", show_alert=True)
        return ConversationHandler.END

    data = query.data

    # ── Editar tasa de la bolsa ───────────────────────────────────────────────
    if data.startswith("ep_bolsa_ed_"):
        clave = data[len("ep_bolsa_ed_"):]
        icono, desc = _BOLSA_LABELS.get(clave, ("", clave))
        tasas = _leer_bolsa()
        actual = _fmt_num(tasas.get(clave, _BOLSA_DEFAULTS.get(clave, 0)))
        context.user_data.update({"ep_modo": "bolsa", "ep_clave": clave,
                                   "ep_desc": f"{icono} {desc}"})
        await query.edit_message_text(
            f"✏️ *Editando tasa de la Bolsa*\n\n"
            f"{icono} {desc}\nValor actual: *{actual}*\n\n"
            f"Escribe el nuevo valor _(número positivo)_:\n"
            f"Ejemplo: `500` o `2.5`\n\n"
            f"_/cancelar para cancelar._",
            parse_mode="Markdown"
        )
        return EP_ESPERANDO

    # ── Editar precio de un ítem ──────────────────────────────────────────────
    if data.startswith("ep_editar_"):
        partes = data.split("_")
        tipo   = partes[2]
        idx    = int(partes[3])
        moneda = partes[4]
        cat = _catalogo(tipo)
        if idx < 0 or idx >= len(cat):
            await query.answer("Ítem no encontrado.", show_alert=True)
            return ConversationHandler.END
        item   = cat[idx]
        nombre = item.get("nombre", item.get("id", "?"))
        campo  = _MONEDAS_CAMPOS.get(moneda, "precio_oro")
        actual = item.get(campo, 0)
        moneda_labels = {"oro": "🪙 Oro", "eth": "💎 Eternium", "cr": "🔮 Créditos"}
        context.user_data.update({
            "ep_modo":   "precio",
            "ep_tipo":   tipo,
            "ep_idx":    idx,
            "ep_moneda": moneda,
            "ep_nombre": nombre,
            "ep_item_id": item.get("id", ""),
        })
        await query.edit_message_text(
            f"✏️ *Editando precio*\n\n"
            f"Ítem: *{_esc_md(nombre)}*\n"
            f"Moneda: {moneda_labels.get(moneda, moneda)}\n"
            f"Precio actual: *{actual:,}*\n\n"
            f"Escribe el nuevo precio _(número entero ≥ 0)_:\n\n"
            f"_/cancelar para cancelar._",
            parse_mode="Markdown"
        )
        return EP_ESPERANDO

    # ── Ajuste masivo ─────────────────────────────────────────────────────────
    if data.startswith("ep_ajuste_"):
        tipo = data[len("ep_ajuste_"):]
        em, lab, *_ = _TIENDAS.get(tipo, ("🛒", tipo, "", ""))
        context.user_data.update({"ep_modo": "ajuste", "ep_tipo": tipo})
        await query.edit_message_text(
            f"⚡ *Ajuste masivo — {em} {lab}*\n\n"
            f"Escribe el ajuste de precio.\n"
            f"Positivo para subir, negativo para bajar.\n\n"
            f"Ejemplos:\n"
            f"• `+500` → todos los precios suben 500\n"
            f"• `-200` → todos los precios bajan 200\n"
            f"• `1000` → todos los precios suben 1000\n\n"
            f"El ajuste aplica al precio principal de esa tienda.\n"
            f"_(Los precios nunca bajan de 0)_\n\n"
            f"_/cancelar para cancelar._",
            parse_mode="Markdown"
        )
        return EP_ESPERANDO

    return ConversationHandler.END


async def recibir_valor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recibe el valor que escribió el admin y aplica el cambio."""
    user_id = update.effective_user.id
    if not _es_admin(user_id):
        return ConversationHandler.END

    texto = update.message.text.strip()
    modo  = context.user_data.get("ep_modo")

    # ── Bolsa ─────────────────────────────────────────────────────────────────
    if modo == "bolsa":
        clave = context.user_data.get("ep_clave", "")
        desc  = context.user_data.get("ep_desc", clave)
        try:
            valor = float(texto.replace(",", "."))
            if valor <= 0:
                raise ValueError
        except ValueError:
            await update.message.reply_text(
                "❌ Valor inválido. Escribe un número positivo (ej: `500` o `2.5`).",
                parse_mode="Markdown"
            )
            return EP_ESPERANDO
        _guardar_bolsa(clave, valor)
        tasas = _leer_bolsa()
        await update.message.reply_text(
            f"✅ *Tasa actualizada*\n\n"
            f"{desc}: *{_fmt_num(valor)}*\n\n"
            f"La Bolsa y la Guía ya reflejan el cambio.",
            parse_mode="Markdown",
            reply_markup=_kb_bolsa(tasas)
        )
        return ConversationHandler.END

    # ── Precio individual ─────────────────────────────────────────────────────
    if modo == "precio":
        item_id = context.user_data.get("ep_item_id", "")
        moneda  = context.user_data.get("ep_moneda", "oro")
        nombre  = context.user_data.get("ep_nombre", item_id)
        tipo    = context.user_data.get("ep_tipo", "oro")
        idx     = context.user_data.get("ep_idx", 0)
        try:
            valor = int(texto.replace(",", "").replace(".", ""))
            if valor < 0:
                raise ValueError
        except ValueError:
            await update.message.reply_text(
                "❌ Valor inválido. Escribe un número entero ≥ 0 (ej: `3000`).",
                parse_mode="Markdown"
            )
            return EP_ESPERANDO
        _guardar_precio(item_id, moneda, valor)
        cat  = _catalogo(tipo)
        item = cat[idx] if 0 <= idx < len(cat) else None
        moneda_labels = {"oro": "🪙 Oro", "eth": "💎 Eternium", "cr": "🔮 Créditos"}
        resp = (
            f"✅ *Precio actualizado*\n\n"
            f"Ítem: *{_esc_md(nombre)}*\n"
            f"Moneda: {moneda_labels.get(moneda, moneda)}\n"
            f"Nuevo precio: *{valor:,}*"
        )
        kb = _kb_item(tipo, idx) if item else None
        if item:
            resp = _texto_item(item) + f"\n\n✅ Precio en {moneda_labels.get(moneda, moneda)} → *{valor:,}* actualizado."
        await update.message.reply_text(resp, parse_mode="Markdown", reply_markup=kb)
        return ConversationHandler.END

    # ── Ajuste masivo ─────────────────────────────────────────────────────────
    if modo == "ajuste":
        tipo = context.user_data.get("ep_tipo", "oro")
        em, lab, campo, moneda = _TIENDAS.get(tipo, ("", tipo, "precio_oro", "oro"))
        try:
            valor = int(texto.replace("+", "").replace(",", "").strip())
        except ValueError:
            await update.message.reply_text(
                "❌ Valor inválido. Escribe un número como `+500`, `-200` o `1000`.",
                parse_mode="Markdown"
            )
            return EP_ESPERANDO
        cat   = _catalogo(tipo)
        count = 0
        for item in cat:
            precio_actual = item.get(campo, 0)
            nuevo         = max(0, precio_actual + valor)
            _guardar_precio(item.get("id", ""), moneda, nuevo)
            count += 1
        signo = "+" if valor >= 0 else ""
        await update.message.reply_text(
            f"✅ *Ajuste masivo completado*\n\n"
            f"Tienda: {em} {lab}\n"
            f"Ajuste: *{signo}{valor:,}*\n"
            f"Ítems actualizados: *{count}*\n\n"
            f"Los cambios ya están activos en la tienda.",
            parse_mode="Markdown",
            reply_markup=_kb_tiendas()
        )
        return ConversationHandler.END

    await update.message.reply_text("❌ Error interno. Usa /cancelar.")
    return ConversationHandler.END


async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("ep_modo", None)
    if update.message:
        await update.message.reply_text("❌ Edición cancelada.", reply_markup=_kb_menu())
    elif update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("❌ Edición cancelada.")
    return ConversationHandler.END


async def _escapar_a_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Escape del ConversationHandler hacia el panel de economía.
    Se activa cuando el usuario pulsa ep_abrir mientras estaba en espera de texto."""
    context.user_data.pop("ep_modo", None)
    await _abrir_panel(update, context)
    return ConversationHandler.END


async def _escapar_cb_nav(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Escape del ConversationHandler hacia la navegación normal del panel."""
    context.user_data.pop("ep_modo", None)
    await cb_nav(update, context)
    return ConversationHandler.END


# ═══════════════════════════════════════════════════════════════════════════════
# REGISTRO DE HANDLERS
# ═══════════════════════════════════════════════════════════════════════════════

def registrar_handlers(app):
    conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(
                cb_edit_entry,
                pattern=r"^ep_bolsa_ed_|^ep_editar_|^ep_ajuste_"
            )
        ],
        states={
            EP_ESPERANDO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_valor),
                CommandHandler("cancelar", cancelar),
                # Escapar a navegación sin perder el contexto del panel
                CallbackQueryHandler(_escapar_a_panel,  pattern=r"^ep_abrir$"),
                CallbackQueryHandler(_escapar_cb_nav,   pattern=r"^ep_menu$|^ep_cerrar$|^ep_bolsa$|^ep_tiendas$"),
            ]
        },
        fallbacks=[
            CommandHandler("cancelar", cancelar),
            CallbackQueryHandler(_escapar_a_panel, pattern=r"^ep_abrir$"),
            CallbackQueryHandler(_escapar_cb_nav,  pattern=r"^ep_menu$|^ep_cerrar$|^ep_bolsa$|^ep_tiendas$"),
        ],
        per_message=False,
        allow_reentry=True,
    )
    app.add_handler(conv)

    app.add_handler(CallbackQueryHandler(
        cb_nav,
        pattern=r"^ep_menu$|^ep_cerrar$|^ep_noop$|^ep_bolsa$|^ep_tiendas$|^ep_lista_|^ep_item_"
    ))

    # Grupo -1 = mayor prioridad que cualquier ConversationHandler en grupo 0.
    # Garantiza que ep_abrir siempre llega aunque haya una conversación activa.
    app.add_handler(CallbackQueryHandler(
        _abrir_panel,
        pattern=r"^ep_abrir$"
    ), group=-1)

    app.add_handler(CommandHandler("panel_economia", _abrir_panel))

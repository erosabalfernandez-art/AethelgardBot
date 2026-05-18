#!/usr/bin/env python3
# cofre_personal.py
# Cofre personal del jugador — solo accesible en la ciudad de su facción.
# Comparte la tabla jugador_ui_prefs con membresia.py.

import sqlite3
import json
from typing import List, Dict, Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler

import db_helper

DB_PATH = "aethelgard.db"
COFRE_MAX_DEFAULT = 30


def _esc(s: str) -> str:
    return str(s).replace("_", "\\_").replace("*", "\\*").replace("`", "\\`").replace("[", "\\[")


# ==================== CATEGORÍAS ====================
_CAT_INFO = {
    "armas":       ("🗡️", "Armas"),
    "armaduras":   ("🛡️", "Armaduras"),
    "accesorios":  ("💍", "Accesorios"),
    "monturas":    ("🐎", "Monturas"),
    "consumibles": ("🧪", "Consumibles"),
    "materiales":  ("🪨", "Materiales"),
    "otros":       ("📦", "Otros"),
}

_ARMAS_KW  = {"espada","hacha","daga","arco","baston","ballesta","martillo","hoz","grimorio","lanza","maza","guadaña","estoque","cimitarra","sable","garrote","alabarda","katana","tridente"}
_ARMAD_KW  = {"pechera","armadura","casco","botas","guantes","capa","escudo","manoplas","grebas","yelmo","chaleco"}
_ACCES_KW  = {"anillo","amuleto","accesorio","collar","colgante","brazalete"}
_MONTU_KW  = {"caballo","lobo","corcel","montura","drake","grifo","pegaso"}
_CONSU_KW  = {"pocion","poción","comida","pan","pescado","elixir","veneno","brebaje","fruta","carne","bebida","hierba","ungüento","antidoto"}
_MATER_KW  = {"mineral","madera","cuero","hierro","acero","mithril","tela","hueso","gema","cristal","fragmento","tronco","piedra","polvo","fibra","resina","carbon","plata","metal","esencia","savia","piel","cola","sangre","escama"}


def _cat_item(nombre: str) -> str:
    n = nombre.lower()
    try:
        from armas import ARMAS
        if nombre in ARMAS:
            return "armas"
    except ImportError:
        pass
    try:
        from armaduras import ARMADURAS
        if nombre in ARMADURAS:
            for kw in _ACCES_KW:
                if kw in n:
                    return "accesorios"
            for kw in _MONTU_KW:
                if kw in n:
                    return "monturas"
            return "armaduras"
    except ImportError:
        pass
    try:
        from pociones import POCIONES
        if nombre in POCIONES:
            return "consumibles"
    except ImportError:
        pass
    for kw in _ARMAS_KW:
        if kw in n:
            return "armas"
    for kw in _ARMAD_KW:
        if kw in n:
            return "armaduras"
    for kw in _ACCES_KW:
        if kw in n:
            return "accesorios"
    for kw in _MONTU_KW:
        if kw in n:
            return "monturas"
    for kw in _CONSU_KW:
        if kw in n:
            return "consumibles"
    for kw in _MATER_KW:
        if kw in n:
            return "materiales"
    return "otros"


def _clasificar_cofre(items: List[Dict]) -> Dict[str, List[Dict]]:
    cats: Dict[str, List[Dict]] = {k: [] for k in _CAT_INFO}
    for it in items:
        cat = _cat_item(it["nombre"])
        cats[cat].append(it)
    return cats


def _info_item_completo(nombre: str) -> Dict:
    stats: Dict = {}
    desc = ""
    try:
        from armas import ARMAS
        if nombre in ARMAS:
            d = ARMAS[nombre]
            for k, etq in [("daño","⚔️ Daño"),("vida_extra","❤️ Vida+"),("defensa_extra","🛡 Def+"),("critico","🎯 Crítico"),("velocidad","⚡ Vel")]:
                if d.get(k):
                    stats[etq] = d[k]
            desc = d.get("descripcion", "")
    except ImportError:
        pass
    try:
        from armaduras import ARMADURAS
        if nombre in ARMADURAS:
            d = ARMADURAS[nombre]
            for k, etq in [("defensa","🛡 Defensa"),("vida_extra","❤️ Vida+"),("velocidad_movimiento","⚡ Vel"),("resistencia_critico","🎯 R.Crit")]:
                if d.get(k):
                    stats[etq] = d[k]
            desc = d.get("descripcion", "")
    except ImportError:
        pass
    try:
        from pociones import POCIONES
        if nombre in POCIONES:
            d = POCIONES[nombre]
            desc = d.get("descripcion", d.get("desc", ""))
    except ImportError:
        pass
    if not stats:
        try:
            from inventario import _obtener_estadisticas_objeto
            raw = _obtener_estadisticas_objeto(nombre)
            etq_map = {"daño":"⚔️ Daño","vida":"❤️ Vida+","defensa":"🛡 Defensa","critico":"🎯 Crítico","velocidad":"⚡ Vel"}
            for k, v in raw.items():
                if v:
                    stats[etq_map.get(k, k)] = v
        except Exception:
            pass
    return {"stats": stats, "desc": desc}


# ==================== INIT DB ====================
def _init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS cofre_personal (
        user_id INTEGER PRIMARY KEY,
        items   TEXT DEFAULT '[]'
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS jugador_ui_prefs (
        user_id           INTEGER PRIMARY KEY,
        mostrar_membresia INTEGER DEFAULT 1,
        mostrar_cofre     INTEGER DEFAULT 1
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS cofre_config (
        clave TEXT PRIMARY KEY,
        valor TEXT
    )''')
    conn.commit()
    conn.close()

_init_db()


# ==================== UI PREFS (compartido con membresia.py) ====================
def _get_prefs(user_id: int) -> Dict:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT mostrar_membresia, mostrar_cofre FROM jugador_ui_prefs WHERE user_id = ?', (user_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return {"mostrar_membresia": bool(row[0]), "mostrar_cofre": bool(row[1])}
    return {"mostrar_membresia": True, "mostrar_cofre": True}

def _set_pref(user_id: int, campo: str, valor: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(f'INSERT INTO jugador_ui_prefs (user_id, {campo}) VALUES (?, ?)'
              f' ON CONFLICT(user_id) DO UPDATE SET {campo} = excluded.{campo}',
              (user_id, valor))
    conn.commit()
    conn.close()

def get_mostrar_membresia(user_id: int) -> bool:
    return _get_prefs(user_id)["mostrar_membresia"]

def get_mostrar_cofre(user_id: int) -> bool:
    return _get_prefs(user_id)["mostrar_cofre"]


# ==================== HELPERS COFRE ====================
def get_cofre(user_id: int) -> List[Dict]:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT items FROM cofre_personal WHERE user_id = ?', (user_id,))
    row = c.fetchone()
    conn.close()
    if row and row[0]:
        try:
            return json.loads(row[0])
        except Exception:
            try:
                return eval(row[0])
            except Exception:
                return []
    return []

def save_cofre(user_id: int, items: List[Dict]):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO cofre_personal (user_id, items) VALUES (?, ?)',
              (user_id, json.dumps(items, ensure_ascii=False)))
    conn.commit()
    conn.close()

def get_cofre_max() -> int:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT valor FROM cofre_config WHERE clave = 'max_items'")
    row = c.fetchone()
    conn.close()
    return int(row[0]) if row else COFRE_MAX_DEFAULT

def set_cofre_max(valor: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO cofre_config (clave, valor) VALUES (?, ?)', ('max_items', str(valor)))
    conn.commit()
    conn.close()


def en_ciudad_propia(user_id: int) -> bool:
    """Retorna True si el jugador está en la ciudad de su propia facción."""
    try:
        jug = db_helper.obtener_jugador(user_id)
        if not jug:
            return False
        faccion = jug.get("faccion", "")
        zona_actual = db_helper.obtener_zona_actual(user_id)
        from datos_zona import ZONAS
        fac_id = {"Alianza": 1, "Imperio": 2, "Sindicato": 3}
        for zona in ZONAS:
            if zona["nombre"] == zona_actual and zona.get("tipo") == "ciudad":
                if zona.get("faccion_id") == fac_id.get(faccion, -1):
                    return True
    except Exception:
        pass
    return False


# ==================== PANEL PRINCIPAL ====================
async def cmd_cofre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        await update.effective_message.reply_text("Primero crea un personaje con /start.")
        return
    await _panel_cofre(update, context, user_id, editar=False)


async def _panel_cofre(update, context, user_id: int, editar: bool = False):
    en_cp = en_ciudad_propia(user_id)
    items = get_cofre(user_id)
    max_i = get_cofre_max()
    jug   = db_helper.obtener_jugador(user_id)
    faccion = jug.get("faccion", "?") if jug else "?"

    texto = "📦 *Cofre Personal*\n\n"
    texto += f"🏰 Ciudad de *{_esc(faccion)}*\n"
    texto += f"📊 Objetos: *{len(items)}/{max_i}*\n"

    if not en_cp:
        texto += "\n⚠️ _Debes estar en la ciudad de tu facción para depositar o retirar._\n"

    kb = []
    if items:
        cats = _clasificar_cofre(items)
        texto += "\n*Contenido por categoría:*\n"
        fila: list = []
        for cat_key, (emoji, label) in _CAT_INFO.items():
            n = len(cats.get(cat_key, []))
            if n:
                texto += f"  {emoji} {label}: {n}\n"
                fila.append(InlineKeyboardButton(
                    f"{emoji} {label} ({n})", callback_data=f"cofre_cat_{cat_key}"
                ))
                if len(fila) == 2:
                    kb.append(fila)
                    fila = []
        if fila:
            kb.append(fila)
        texto += "\n_Pulsa una categoría para ver e inspeccionar los objetos._\n"
    else:
        texto += "\n_El cofre está vacío._\n"

    texto += "\n_Usa_ `/mostrar_cofre` _o_ `/ocultar_cofre` _para controlar este botón en el menú._"

    fila_acc: list = []
    if en_cp:
        fila_acc.append(InlineKeyboardButton("📥 Depositar", callback_data="cofre_depositar"))
        fila_acc.append(InlineKeyboardButton("📤 Retirar",   callback_data="cofre_retirar"))
    if fila_acc:
        kb.append(fila_acc)
    kb.append([InlineKeyboardButton("🔄 Actualizar", callback_data="cofre_ver")])
    kb.append([InlineKeyboardButton("❌ Cerrar",     callback_data="cofre_cerrar")])

    markup = InlineKeyboardMarkup(kb)
    if editar and update.callback_query:
        try:
            await update.callback_query.edit_message_text(texto, reply_markup=markup, parse_mode="Markdown")
            return
        except Exception:
            pass
    await update.effective_message.reply_text(texto, reply_markup=markup, parse_mode="Markdown")


async def _panel_cofre_cat(update, context, user_id: int, cat_key: str):
    """Muestra los objetos de una categoría del cofre con botones de inspección."""
    query = update.callback_query
    items = get_cofre(user_id)
    cats  = _clasificar_cofre(items)
    cat_items = cats.get(cat_key, [])
    emoji, label = _CAT_INFO.get(cat_key, ("📦", cat_key.title()))

    texto = f"{emoji} *{label} en el cofre*\n\n"
    if not cat_items:
        texto += "_No tienes objetos en esta categoría._\n"
    else:
        texto += f"_{len(cat_items)} objeto(s). Pulsa uno para ver stats y descripción._\n\n"

    kb = []
    for it in cat_items[:20]:
        nombre = it["nombre"]
        cant   = it.get("cantidad", 1)
        kb.append([InlineKeyboardButton(
            f"{emoji} {nombre} ×{cant}",
            callback_data=f"cofre_insp_{nombre[:20]}"
        )])
    if len(cat_items) > 20:
        texto += f"_...y {len(cat_items)-20} más_\n"
    kb.append([InlineKeyboardButton("🔙 Volver al cofre", callback_data="cofre_ver")])

    await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")


async def _cb_cofre_cat(update, context):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    cat_key = query.data[len("cofre_cat_"):]
    await _panel_cofre_cat(update, context, user_id, cat_key)


async def _cb_cofre_insp(update, context):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    nombre_k = query.data[len("cofre_insp_"):]
    items = get_cofre(user_id)
    item  = next((it for it in items if it["nombre"][:20] == nombre_k or nombre_k in it["nombre"]), None)
    if not item:
        await query.answer("❌ Objeto no encontrado.", show_alert=True)
        return
    nombre = item["nombre"]
    cant   = item.get("cantidad", 1)
    info   = _info_item_completo(nombre)
    cat    = _cat_item(nombre)
    emoji, _ = _CAT_INFO.get(cat, ("📦", ""))

    texto  = f"{emoji} *{_esc(nombre)}*\n"
    texto += f"📊 En cofre: ×{cant}\n"
    if info["desc"]:
        texto += f"\n📝 _{_esc(info['desc'])}_\n"
    if info["stats"]:
        texto += "\n*Stats:*\n"
        for etq, val in info["stats"].items():
            texto += f"  {etq}: `{val}`\n"
    elif not info["desc"]:
        texto += "\n_Sin información adicional._\n"

    kb = [[InlineKeyboardButton("🔙 Volver", callback_data=f"cofre_cat_{cat}")]]
    await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")


# ==================== DEPOSITAR ====================
async def cofre_depositar_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    if not en_ciudad_propia(user_id):
        await query.answer("⚠️ Solo puedes depositar estando en tu ciudad.", show_alert=True)
        return

    inv   = db_helper.obtener_inventario(user_id)
    cofre = get_cofre(user_id)
    max_i = get_cofre_max()

    if not inv:
        await query.edit_message_text(
            "📥 *Depositar*\n\n_No tienes objetos en el inventario._",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver", callback_data="cofre_ver")]]),
            parse_mode="Markdown"
        )
        return

    texto  = "📥 *¿Qué objeto quieres depositar?*\n\n"
    texto += f"_Cofre: {len(cofre)}/{max_i} objetos_\n\n"
    botones = []
    for it in inv[:24]:
        nombre = it['nombre']
        cant   = it.get('cantidad', 1)
        texto += f"  • {_esc(nombre)} ×{cant}\n"
        botones.append([InlineKeyboardButton(
            f"📥 {nombre} ×{cant}",
            callback_data=f"cofre_dep_{nombre[:28]}"
        )])
    if len(inv) > 24:
        texto += f"_...y {len(inv)-24} más_\n"
    botones.append([InlineKeyboardButton("🔙 Volver", callback_data="cofre_ver")])

    await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(botones), parse_mode="Markdown")


async def cofre_dep_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    if not en_ciudad_propia(user_id):
        await query.answer("⚠️ Solo puedes depositar estando en tu ciudad.", show_alert=True)
        return

    nombre_k = query.data[len("cofre_dep_"):]
    inv  = db_helper.obtener_inventario(user_id)
    item = next((it for it in inv if it['nombre'][:28] == nombre_k or nombre_k in it['nombre']), None)
    if not item:
        await query.answer("❌ Objeto no encontrado.", show_alert=True)
        return

    nombre = item['nombre']
    cant   = item.get('cantidad', 1)
    cofre  = get_cofre(user_id)
    max_i  = get_cofre_max()
    en_cofre = next((x for x in cofre if x['nombre'] == nombre), None)
    if not en_cofre and len(cofre) >= max_i:
        await query.answer(f"❌ Cofre lleno ({max_i} tipos de objeto máx).", show_alert=True)
        return

    opciones = sorted({1, min(5, cant), min(10, cant), cant})
    row = [InlineKeyboardButton(f"×{op}", callback_data=f"cofre_dep2_{nombre[:22]}|{op}") for op in opciones]
    botones = [row, [InlineKeyboardButton("🔙 Cancelar", callback_data="cofre_depositar")]]

    await query.edit_message_text(
        f"📥 *Depositar:* {_esc(nombre)}\n*Tienes:* ×{cant}\n\n¿Cuántos?",
        reply_markup=InlineKeyboardMarkup(botones),
        parse_mode="Markdown"
    )


async def cofre_dep2_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    if not en_ciudad_propia(user_id):
        await query.answer("⚠️ Solo puedes depositar estando en tu ciudad.", show_alert=True)
        return

    raw = query.data[len("cofre_dep2_"):]
    if "|" not in raw:
        await query.answer("❌ Error de datos.", show_alert=True)
        return
    nombre_k, cant_s = raw.rsplit("|", 1)
    try:
        cantidad = int(cant_s)
    except ValueError:
        await query.answer("❌ Cantidad inválida.", show_alert=True)
        return

    inv  = db_helper.obtener_inventario(user_id)
    item = next((it for it in inv if it['nombre'][:22] == nombre_k or nombre_k in it['nombre']), None)
    if not item or item.get('cantidad', 1) < cantidad:
        await query.answer("❌ No tienes esa cantidad.", show_alert=True)
        return

    nombre = item['nombre']
    ok = db_helper.quitar_item(user_id, nombre, cantidad)
    if not ok:
        await query.answer("❌ Error al retirar del inventario.", show_alert=True)
        return

    cofre = get_cofre(user_id)
    ex = next((x for x in cofre if x['nombre'] == nombre), None)
    if ex:
        ex['cantidad'] = ex.get('cantidad', 0) + cantidad
    else:
        cofre.append({"nombre": nombre, "cantidad": cantidad})
    save_cofre(user_id, cofre)

    await query.answer(f"✅ {nombre} ×{cantidad} depositado.", show_alert=True)
    await _panel_cofre(update, context, user_id, editar=True)


# ==================== RETIRAR ====================
async def cofre_retirar_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    if not en_ciudad_propia(user_id):
        await query.answer("⚠️ Solo puedes retirar estando en tu ciudad.", show_alert=True)
        return

    cofre = get_cofre(user_id)
    if not cofre:
        await query.edit_message_text(
            "📤 *Retirar del cofre*\n\n_El cofre está vacío._",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver", callback_data="cofre_ver")]]),
            parse_mode="Markdown"
        )
        return

    texto   = "📤 *¿Qué objeto quieres retirar?*\n\n"
    botones = []
    for it in cofre[:24]:
        nombre = it['nombre']
        cant   = it.get('cantidad', 1)
        texto += f"  • {_esc(nombre)} ×{cant}\n"
        botones.append([InlineKeyboardButton(
            f"📤 {nombre} ×{cant}",
            callback_data=f"cofre_ret_{nombre[:28]}"
        )])
    if len(cofre) > 24:
        texto += f"_...y {len(cofre)-24} más_\n"
    botones.append([InlineKeyboardButton("🔙 Volver", callback_data="cofre_ver")])

    await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(botones), parse_mode="Markdown")


async def cofre_ret_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    if not en_ciudad_propia(user_id):
        await query.answer("⚠️ Solo puedes retirar estando en tu ciudad.", show_alert=True)
        return

    nombre_k = query.data[len("cofre_ret_"):]
    cofre = get_cofre(user_id)
    item  = next((x for x in cofre if x['nombre'][:28] == nombre_k or nombre_k in x['nombre']), None)
    if not item:
        await query.answer("❌ Objeto no encontrado en el cofre.", show_alert=True)
        return

    nombre = item['nombre']
    cant   = item.get('cantidad', 1)
    opciones = sorted({1, min(5, cant), min(10, cant), cant})
    row = [InlineKeyboardButton(f"×{op}", callback_data=f"cofre_ret2_{nombre[:22]}|{op}") for op in opciones]
    botones = [row, [InlineKeyboardButton("🔙 Cancelar", callback_data="cofre_retirar")]]

    await query.edit_message_text(
        f"📤 *Retirar:* {_esc(nombre)}\n*En cofre:* ×{cant}\n\n¿Cuántos?",
        reply_markup=InlineKeyboardMarkup(botones),
        parse_mode="Markdown"
    )


async def cofre_ret2_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    if not en_ciudad_propia(user_id):
        await query.answer("⚠️ Solo puedes retirar estando en tu ciudad.", show_alert=True)
        return

    raw = query.data[len("cofre_ret2_"):]
    if "|" not in raw:
        await query.answer("❌ Error de datos.", show_alert=True)
        return
    nombre_k, cant_s = raw.rsplit("|", 1)
    try:
        cantidad = int(cant_s)
    except ValueError:
        await query.answer("❌ Cantidad inválida.", show_alert=True)
        return

    cofre = get_cofre(user_id)
    item  = next((x for x in cofre if x['nombre'][:22] == nombre_k or nombre_k in x['nombre']), None)
    if not item or item.get('cantidad', 1) < cantidad:
        await query.answer("❌ No hay suficiente cantidad.", show_alert=True)
        return

    nombre = item['nombre']
    item['cantidad'] = item.get('cantidad', 0) - cantidad
    cofre = [x for x in cofre if x.get('cantidad', 0) > 0]
    save_cofre(user_id, cofre)
    db_helper.agregar_item(user_id, nombre, cantidad)

    await query.answer(f"✅ {nombre} ×{cantidad} retirado al inventario.", show_alert=True)
    await _panel_cofre(update, context, user_id, editar=True)


# ==================== COMANDOS DE TOGGLE ====================
async def cmd_mostrar_cofre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    _set_pref(user_id, "mostrar_cofre", 1)
    await update.effective_message.reply_text(
        "✅ El botón *📦 Cofre Personal* ya aparece en el menú de la ciudad.\n"
        "Usa `/ocultar_cofre` para quitarlo.",
        parse_mode="Markdown"
    )

async def cmd_ocultar_cofre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    _set_pref(user_id, "mostrar_cofre", 0)
    await update.effective_message.reply_text(
        "✅ El botón *📦 Cofre Personal* ya no aparece en el menú de la ciudad.\n"
        "Usa `/mostrar_cofre` para activarlo de nuevo.",
        parse_mode="Markdown"
    )


# ==================== REGISTRO ====================
def registrar_handlers(app):
    app.add_handler(CommandHandler("cofre",         cmd_cofre))
    app.add_handler(CommandHandler("mostrar_cofre", cmd_mostrar_cofre))
    app.add_handler(CommandHandler("ocultar_cofre", cmd_ocultar_cofre))
    app.add_handler(CallbackQueryHandler(cofre_depositar_cb, pattern="^cofre_depositar$"))
    app.add_handler(CallbackQueryHandler(cofre_retirar_cb,   pattern="^cofre_retirar$"))
    app.add_handler(CallbackQueryHandler(cofre_dep_cb,       pattern="^cofre_dep_"))
    app.add_handler(CallbackQueryHandler(cofre_dep2_cb,      pattern="^cofre_dep2_"))
    app.add_handler(CallbackQueryHandler(cofre_ret_cb,       pattern="^cofre_ret_"))
    app.add_handler(CallbackQueryHandler(cofre_ret2_cb,      pattern="^cofre_ret2_"))
    app.add_handler(CallbackQueryHandler(_cb_cofre_cat,      pattern="^cofre_cat_"))
    app.add_handler(CallbackQueryHandler(_cb_cofre_insp,     pattern="^cofre_insp_"))

    async def _ver_cb(upd, ctx):
        q = upd.callback_query
        await q.answer()
        await _panel_cofre(upd, ctx, upd.effective_user.id, editar=True)

    async def _cerrar_cb(upd, ctx):
        q = upd.callback_query
        await q.answer()
        await q.edit_message_text("📦 Cofre cerrado.")

    app.add_handler(CallbackQueryHandler(_ver_cb,    pattern="^cofre_ver$"))
    app.add_handler(CallbackQueryHandler(_cerrar_cb, pattern="^cofre_cerrar$"))

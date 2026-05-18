#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# admin_stats.py - Editor completo de stats: monstruos, armas, armaduras, precios y stamina

import re as _re
import sqlite3
import importlib
import os
import sys
import glob
import html as _html

def _e(s) -> str:
    return _html.escape(str(s) if s is not None else "")

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler

_DIR = os.path.dirname(os.path.abspath(__file__))
if _DIR not in sys.path:
    sys.path.insert(0, _DIR)

import db_helper

# ==================== CARGA DE OVERRIDES AL INICIO ====================

def cargar_overrides():
    """Aplica todos los overrides de la BD en memoria. Llamar al arrancar el bot."""
    _patch_items()
    _patch_precios()
    _patch_monstruos()

# -------- items --------
def _patch_items():
    try:
        from armas import ARMAS
        from armaduras import ARMADURAS
    except ImportError:
        return
    rows = _get_rows("SELECT item_id, stat, valor FROM stats_overrides_items")
    for item_id, stat, valor in rows:
        item = ARMAS.get(item_id) or ARMADURAS.get(item_id)
        if item is None:
            continue
        current = item.get(stat)
        if current is None:
            continue
        try:
            item[stat] = int(valor) if isinstance(current, int) else float(valor) if isinstance(current, float) else valor
        except (ValueError, TypeError):
            pass

# -------- precios --------
def _patch_precios():
    try:
        import tienda
        catalogs = [tienda.CATALOGO_ORO, tienda.CATALOGO_ETERNIUM]
    except ImportError:
        return
    rows = _get_rows("SELECT item_id, moneda, valor FROM stats_overrides_precios")
    mapa = {(r[0], r[1]): int(r[2]) for r in rows}
    if not mapa:
        return
    campo_map = {"oro": ("precio_oro","precio_venta_oro"), "eth": ("precio_eternium","precio_venta_eternium"), "cr": ("precio_creditos", None)}
    for cat in catalogs:
        for item in cat:
            iid = item.get("id")
            if not iid:
                continue
            for moneda, (campo, campo_venta) in campo_map.items():
                if (iid, moneda) in mapa:
                    item[campo] = mapa[(iid, moneda)]
                    if campo_venta:
                        item[campo_venta] = int(mapa[(iid, moneda)] * 0.7)

# -------- monstruos --------
def _patch_monstruos():
    rows = _get_rows("SELECT monstruo_id, stat, valor FROM stats_overrides_monstruos")
    if not rows:
        return
    por_id = {}
    for mid, stat, valor in rows:
        por_id.setdefault(mid, {})[stat] = valor
    for archivo in glob.glob(os.path.join(_DIR, "monstruos_*zona_*.py")):
        mod_name = os.path.basename(archivo)[:-3]
        try:
            mod = importlib.import_module(mod_name)
        except ImportError:
            continue
        for attr in ["MONSTRUOS_MAZMORRAS_NORMAL", "MONSTRUOS_MAZMORRAS_DIFICIL", "MONSTRUOS_NORMALES"]:
            d = getattr(mod, attr, None)
            if not isinstance(d, dict):
                continue
            for mid, patches in por_id.items():
                if mid not in d:
                    continue
                for stat, valor in patches.items():
                    current = d[mid].get(stat)
                    if current is None:
                        continue
                    try:
                        d[mid][stat] = int(valor) if isinstance(current, int) else float(valor) if isinstance(current, float) else valor
                    except (ValueError, TypeError):
                        pass

# ==================== HELPERS DB ====================

def _get_rows(sql, params=()):
    conn = sqlite3.connect(db_helper.DB_PATH)
    c = conn.cursor()
    c.execute(sql, params)
    rows = c.fetchall()
    conn.close()
    return rows

def _upsert(sql, params):
    conn = sqlite3.connect(db_helper.DB_PATH)
    c = conn.cursor()
    c.execute(sql, params)
    conn.commit()
    conn.close()

def _delete(sql, params):
    conn = sqlite3.connect(db_helper.DB_PATH)
    c = conn.cursor()
    c.execute(sql, params)
    conn.commit()
    conn.close()

# ==================== BÚSQUEDA DE ITEMS Y MONSTRUOS ====================

def _buscar_item(item_id):
    try:
        from armas import ARMAS
        if item_id in ARMAS:
            return ARMAS[item_id], "arma"
    except ImportError:
        pass
    try:
        from armaduras import ARMADURAS
        if item_id in ARMADURAS:
            return ARMADURAS[item_id], "armadura"
    except ImportError:
        pass
    return None, None

def _buscar_monstruo_dict(mid):
    for archivo in glob.glob(os.path.join(_DIR, "monstruos_*zona_*.py")):
        mod_name = os.path.basename(archivo)[:-3]
        try:
            mod = importlib.import_module(mod_name)
        except ImportError:
            continue
        for attr in ["MONSTRUOS_MAZMORRAS_NORMAL", "MONSTRUOS_MAZMORRAS_DIFICIL", "MONSTRUOS_NORMALES"]:
            d = getattr(mod, attr, None)
            if isinstance(d, dict) and mid in d:
                return d[mid]
    return None

# ==================== STAMINA ====================

async def cmd_ver_stamina(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not db_helper.verificar_nivel(update.effective_user.id, 1):
        await update.effective_message.reply_text("❌ Sin acceso.")
        return
    rec = db_helper.obtener_config("stamina_recolectar", "5")
    exp = db_helper.obtener_config("stamina_explorar", "5")
    await update.effective_message.reply_text(
        f"💨 *Costes de Stamina actuales:*\n\n"
        f"🌿 Recolectar: *{rec}* stamina\n"
        f"🔍 Explorar / Seguir huellas: *{exp}* stamina\n\n"
        "_Las mazmorras no consumen stamina._\n\n"
        "Usa `/set_stamina recolectar <N>` o `/set_stamina explorar <N>` para cambiar.",
        parse_mode="Markdown"
    )

async def cmd_set_stamina(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not db_helper.verificar_nivel(update.effective_user.id, 1):
        await update.effective_message.reply_text("❌ Sin acceso.")
        return
    args = context.args
    if len(args) != 2:
        await update.effective_message.reply_text("Uso: `/set_stamina <recolectar|explorar> <cantidad>`", parse_mode="Markdown")
        return
    tipo, val_str = args[0].lower(), args[1]
    if tipo not in ("recolectar", "explorar"):
        await update.effective_message.reply_text("❌ Tipo: `recolectar` o `explorar`.", parse_mode="Markdown")
        return
    try:
        val = int(val_str)
        if val < 0:
            raise ValueError
    except ValueError:
        await update.effective_message.reply_text("❌ Cantidad debe ser entero ≥ 0.")
        return
    db_helper.establecer_config(f"stamina_{tipo}", str(val))
    emoji = "🌿" if tipo == "recolectar" else "🔍"
    await update.effective_message.reply_text(
        f"✅ {emoji} Stamina de *{tipo}* → *{val}* puntos.",
        parse_mode="Markdown"
    )

# ==================== MONSTRUOS ====================

STATS_MONSTRUO_VALIDOS = {"vida", "vida_max", "daño", "defensa", "xp", "oro", "nivel"}

async def cmd_buscar_monstruo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not db_helper.verificar_nivel(update.effective_user.id, 1):
        await update.effective_message.reply_text("❌ Sin acceso.")
        return
    if not context.args:
        await update.effective_message.reply_text("Uso: `/buscar_monstruo <nombre_parcial>`", parse_mode="Markdown")
        return
    qry = " ".join(context.args).lower()
    resultados = []
    for archivo in glob.glob(os.path.join(_DIR, "monstruos_*zona_*.py")):
        mod_name = os.path.basename(archivo)[:-3]
        try:
            mod = importlib.import_module(mod_name)
        except ImportError:
            continue
        for attr in ["MONSTRUOS_MAZMORRAS_NORMAL", "MONSTRUOS_MAZMORRAS_DIFICIL", "MONSTRUOS_NORMALES"]:
            d = getattr(mod, attr, None)
            if not isinstance(d, dict):
                continue
            for mid, mdata in d.items():
                if qry in mdata.get("nombre","").lower() or qry in mid.lower():
                    resultados.append((mid, mdata.get("nombre","?"), mdata.get("nivel",0)))
                if len(resultados) >= 25:
                    break
        if len(resultados) >= 25:
            break
    if not resultados:
        await update.effective_message.reply_text(f"❌ Sin resultados para `{qry}`.", parse_mode="Markdown")
        return
    txt = f"🔍 *{len(resultados)} resultado(s)*:\n\n"
    for mid, nom, nv in resultados[:25]:
        txt += f"• `{mid}` — {nom} (Nv {nv})\n"
    await update.effective_message.reply_text(txt, parse_mode="Markdown")

async def cmd_ver_monstruo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not db_helper.verificar_nivel(update.effective_user.id, 1):
        await update.effective_message.reply_text("❌ Sin acceso.")
        return
    if not context.args:
        await update.effective_message.reply_text("Uso: `/ver_monstruo <id>`", parse_mode="Markdown")
        return
    mid = context.args[0]
    m = _buscar_monstruo_dict(mid)
    if m is None:
        await update.effective_message.reply_text(f"❌ Monstruo `{mid}` no encontrado.", parse_mode="Markdown")
        return
    txt = f"👾 *{m.get('nombre',mid)}* (`{mid}`)\n\n"
    for s in sorted(STATS_MONSTRUO_VALIDOS):
        txt += f"  `{s}`: *{m.get(s,'N/A')}*\n"
    txt += f"\n🗡️ Clase: {m.get('clase','?')} | Nv {m.get('nivel','?')}"
    await update.effective_message.reply_text(txt, parse_mode="Markdown")

async def cmd_editar_monstruo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not db_helper.verificar_nivel(update.effective_user.id, 1):
        await update.effective_message.reply_text("❌ Sin acceso.")
        return
    args = context.args
    if len(args) != 3:
        await update.effective_message.reply_text(
            "Uso: `/editar_monstruo <id> <stat> <valor>`\n\n"
            f"Stats: `{'` | `'.join(sorted(STATS_MONSTRUO_VALIDOS))}`",
            parse_mode="Markdown"
        )
        return
    mid, stat, val_str = args[0], args[1].lower(), args[2]
    if stat not in STATS_MONSTRUO_VALIDOS:
        await update.effective_message.reply_text(
            f"❌ Stat `{stat}` no válido.\nUsa: `{'` | `'.join(sorted(STATS_MONSTRUO_VALIDOS))}`",
            parse_mode="Markdown"
        )
        return
    try:
        val = int(val_str)
        if val < 0:
            raise ValueError
    except ValueError:
        await update.effective_message.reply_text("❌ Valor debe ser entero ≥ 0.")
        return
    m = _buscar_monstruo_dict(mid)
    if m is None:
        await update.effective_message.reply_text(f"❌ Monstruo `{mid}` no encontrado.", parse_mode="Markdown")
        return
    antiguo = m.get(stat, "N/A")
    _upsert("INSERT OR REPLACE INTO stats_overrides_monstruos (monstruo_id, stat, valor) VALUES (?,?,?)", (mid, stat, str(val)))
    _patch_monstruos()
    await update.effective_message.reply_text(
        f"✅ *{m.get('nombre',mid)}* — `{stat}` actualizado:\n"
        f"  {antiguo} → *{val}*\n\n_Guardado en BD, persistente al reiniciar._",
        parse_mode="Markdown"
    )

async def cmd_reset_monstruo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not db_helper.verificar_nivel(update.effective_user.id, 1):
        await update.effective_message.reply_text("❌ Sin acceso.")
        return
    if not context.args:
        await update.effective_message.reply_text("Uso: `/reset_monstruo <id>`", parse_mode="Markdown")
        return
    _delete("DELETE FROM stats_overrides_monstruos WHERE monstruo_id=?", (context.args[0],))
    await update.effective_message.reply_text(
        f"✅ Monstruo `{context.args[0]}` restablecido a valores originales.\n_Reinicia el bot para ver los cambios en memoria._",
        parse_mode="Markdown"
    )

# ==================== ARMAS ====================

STATS_ARMA = {"daño","critico","velocidad","peso","vida_extra","defensa_extra",
              "nivel_requerido","precio_oro","precio_eternium","precio_creditos",
              "precio_venta_oro","precio_venta_eternium"}
STATS_ARMADURA = {"defensa","resistencia_critico","velocidad_movimiento","peso",
                  "vida_extra","defensa_extra","nivel_requerido",
                  "precio_oro","precio_eternium","precio_creditos",
                  "precio_venta_oro","precio_venta_eternium"}

def _fmt_item(item, tipo):
    stats = STATS_ARMA if tipo == "arma" else STATS_ARMADURA
    txt  = f"⚔️ *{item.get('nombre',item.get('id','?'))}* (`{item.get('id','?')}`)\n"
    txt += f"Tipo: {item.get('tipo','?')} | Clase: {item.get('clase_requerida','?')} | Rareza: {item.get('rareza','?')}\n\n"
    for s in sorted(stats):
        txt += f"  `{s}`: *{item.get(s,'N/A')}*\n"
    return txt

async def cmd_ver_arma(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not db_helper.verificar_nivel(update.effective_user.id, 1):
        await update.effective_message.reply_text("❌ Sin acceso.")
        return
    if not context.args:
        await update.effective_message.reply_text("Uso: `/ver_arma <id>`", parse_mode="Markdown")
        return
    item, tipo = _buscar_item(context.args[0])
    if item is None or tipo != "arma":
        await update.effective_message.reply_text(f"❌ Arma `{context.args[0]}` no encontrada.", parse_mode="Markdown")
        return
    await update.effective_message.reply_text(_fmt_item(item, "arma"), parse_mode="Markdown")

async def cmd_ver_armadura(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not db_helper.verificar_nivel(update.effective_user.id, 1):
        await update.effective_message.reply_text("❌ Sin acceso.")
        return
    if not context.args:
        await update.effective_message.reply_text("Uso: `/ver_armadura <id>`", parse_mode="Markdown")
        return
    item, tipo = _buscar_item(context.args[0])
    if item is None or tipo != "armadura":
        await update.effective_message.reply_text(f"❌ Armadura `{context.args[0]}` no encontrada.", parse_mode="Markdown")
        return
    await update.effective_message.reply_text(_fmt_item(item, "armadura"), parse_mode="Markdown")

async def _editar_item_cmd(update, context, tipo_esperado, stats_validos):
    if not db_helper.verificar_nivel(update.effective_user.id, 1):
        await update.effective_message.reply_text("❌ Sin acceso.")
        return
    args = context.args
    if len(args) != 3:
        await update.effective_message.reply_text(
            f"Uso: `/editar_{tipo_esperado} <id> <stat> <valor>`\n\n"
            f"Stats: `{'` | `'.join(sorted(stats_validos))}`",
            parse_mode="Markdown"
        )
        return
    item_id, stat, val_str = args[0], args[1].lower(), args[2]
    if stat not in stats_validos:
        await update.effective_message.reply_text(
            f"❌ Stat `{stat}` no válido.\nUsa: `{'` | `'.join(sorted(stats_validos))}`",
            parse_mode="Markdown"
        )
        return
    try:
        val = int(val_str)
    except ValueError:
        try:
            val = float(val_str)
        except ValueError:
            await update.effective_message.reply_text("❌ Valor debe ser numérico.")
            return
    item, tipo = _buscar_item(item_id)
    if item is None or tipo != tipo_esperado:
        await update.effective_message.reply_text(f"❌ {tipo_esperado.capitalize()} `{item_id}` no encontrada.", parse_mode="Markdown")
        return
    antiguo = item.get(stat, "N/A")
    _upsert("INSERT OR REPLACE INTO stats_overrides_items (item_id, stat, valor) VALUES (?,?,?)", (item_id, stat, str(val)))
    item[stat] = val
    await update.effective_message.reply_text(
        f"✅ *{item.get('nombre',item_id)}* — `{stat}`:\n"
        f"  {antiguo} → *{val}*",
        parse_mode="Markdown"
    )

async def cmd_editar_arma(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _editar_item_cmd(update, context, "arma", STATS_ARMA)

async def cmd_editar_armadura(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _editar_item_cmd(update, context, "armadura", STATS_ARMADURA)

async def cmd_reset_arma(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not db_helper.verificar_nivel(update.effective_user.id, 1):
        await update.effective_message.reply_text("❌ Sin acceso.")
        return
    if not context.args:
        await update.effective_message.reply_text("Uso: `/reset_arma <id>`", parse_mode="Markdown")
        return
    _delete("DELETE FROM stats_overrides_items WHERE item_id=?", (context.args[0],))
    await update.effective_message.reply_text(f"✅ Arma `{context.args[0]}` restablecida.\n_Reinicia el bot para aplicar valores base._", parse_mode="Markdown")

async def cmd_reset_armadura(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not db_helper.verificar_nivel(update.effective_user.id, 1):
        await update.effective_message.reply_text("❌ Sin acceso.")
        return
    if not context.args:
        await update.effective_message.reply_text("Uso: `/reset_armadura <id>`", parse_mode="Markdown")
        return
    _delete("DELETE FROM stats_overrides_items WHERE item_id=?", (context.args[0],))
    await update.effective_message.reply_text(f"✅ Armadura `{context.args[0]}` restablecida.\n_Reinicia el bot para aplicar valores base._", parse_mode="Markdown")

# ==================== PRECIOS ====================

MONEDAS = {"oro": ("precio_oro","precio_venta_oro"), "eth": ("precio_eternium","precio_venta_eternium"), "cr": ("precio_creditos",None)}

async def cmd_ver_precio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not db_helper.verificar_nivel(update.effective_user.id, 1):
        await update.effective_message.reply_text("❌ Sin acceso.")
        return
    if not context.args:
        await update.effective_message.reply_text("Uso: `/ver_precio <item_id>`", parse_mode="Markdown")
        return
    item, _ = _buscar_item(context.args[0])
    if item is None:
        await update.effective_message.reply_text(f"❌ Ítem `{context.args[0]}` no encontrado.", parse_mode="Markdown")
        return
    txt = (
        f"💰 *Precios de {item.get('nombre',context.args[0])}*\n\n"
        f"🪙 Oro: *{item.get('precio_oro',0):,}* (venta: {item.get('precio_venta_oro',0):,})\n"
        f"💎 Eternium: *{item.get('precio_eternium',0):,}* (venta: {item.get('precio_venta_eternium',0):,})\n"
        f"✨ Créditos: *{item.get('precio_creditos',0):,}*\n\n"
        f"_Usa `/editar_precio {context.args[0]} <moneda> <valor>` para cambiar._"
    )
    await update.effective_message.reply_text(txt, parse_mode="Markdown")

async def cmd_editar_precio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not db_helper.verificar_nivel(update.effective_user.id, 1):
        await update.effective_message.reply_text("❌ Sin acceso.")
        return
    args = context.args
    if len(args) != 3:
        await update.effective_message.reply_text(
            "Uso: `/editar_precio <item_id> <moneda> <valor>`\n\n"
            "Monedas: `oro` | `eth` | `cr`\n"
            "Ejemplo: `/editar_precio arma_1 oro 5000`",
            parse_mode="Markdown"
        )
        return
    item_id, moneda, val_str = args[0], args[1].lower(), args[2]
    if moneda not in MONEDAS:
        await update.effective_message.reply_text("❌ Moneda: `oro`, `eth` o `cr`.", parse_mode="Markdown")
        return
    try:
        val = int(val_str)
        if val < 0:
            raise ValueError
    except ValueError:
        await update.effective_message.reply_text("❌ Valor debe ser entero ≥ 0.")
        return
    item, _ = _buscar_item(item_id)
    if item is None:
        await update.effective_message.reply_text(f"❌ Ítem `{item_id}` no encontrado.", parse_mode="Markdown")
        return
    campo, campo_venta = MONEDAS[moneda]
    antiguo = item.get(campo, 0)
    _upsert("INSERT OR REPLACE INTO stats_overrides_precios (item_id, moneda, valor) VALUES (?,?,?)", (item_id, moneda, val))
    item[campo] = val
    if campo_venta:
        item[campo_venta] = int(val * 0.7)
    _patch_precios()
    emoji = {"oro":"🪙","eth":"💎","cr":"✨"}[moneda]
    await update.effective_message.reply_text(
        f"✅ *{item.get('nombre',item_id)}* — precio {emoji}:\n"
        f"  {antiguo:,} → *{val:,}*",
        parse_mode="Markdown"
    )


# ==================== EDICIÓN MASIVA — MONSTRUOS POR ZONA ====================

COLORES_ZONA = {"azul", "amarilla", "roja", "negra"}

def _iter_monstruos_zona(color: str):
    """Itera (dict_origen, mid) de todos los monstruos de una zona."""
    for archivo in glob.glob(os.path.join(_DIR, "monstruos_*zona_*.py")):
        mod_name = os.path.basename(archivo)[:-3]
        try:
            mod = importlib.import_module(mod_name)
        except ImportError:
            continue
        for attr in ["MONSTRUOS_MAZMORRAS_NORMAL", "MONSTRUOS_MAZMORRAS_DIFICIL", "MONSTRUOS_NORMALES"]:
            d = getattr(mod, attr, None)
            if not isinstance(d, dict):
                continue
            for mid in list(d.keys()):
                if mid.startswith(color):
                    yield d, mid

async def cmd_editar_monstruos_zona(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fija un stat absoluto en TODOS los monstruos de una zona: /editar_monstruos_zona <color> <stat> <valor>"""
    if not db_helper.verificar_nivel(update.effective_user.id, 1):
        await update.effective_message.reply_text("❌ Sin acceso.")
        return
    args = context.args
    if len(args) != 3:
        await update.effective_message.reply_text(
            "Uso: `/editar_monstruos_zona <color> <stat> <valor>`\n\n"
            f"Colores: `{'` | `'.join(sorted(COLORES_ZONA))}`\n"
            f"Stats: `{'` | `'.join(sorted(STATS_MONSTRUO_VALIDOS))}`",
            parse_mode="Markdown"
        )
        return
    color, stat, val_str = args[0].lower(), args[1].lower(), args[2]
    if color not in COLORES_ZONA:
        await update.effective_message.reply_text(f"❌ Color debe ser: `{'` | `'.join(sorted(COLORES_ZONA))}`", parse_mode="Markdown")
        return
    if stat not in STATS_MONSTRUO_VALIDOS:
        await update.effective_message.reply_text(f"❌ Stat debe ser: `{'` | `'.join(sorted(STATS_MONSTRUO_VALIDOS))}`", parse_mode="Markdown")
        return
    try:
        val = int(val_str)
        if val < 0:
            raise ValueError
    except ValueError:
        await update.effective_message.reply_text("❌ Valor debe ser entero ≥ 0.")
        return
    n = 0
    for d, mid in _iter_monstruos_zona(color):
        _upsert("INSERT OR REPLACE INTO stats_overrides_monstruos (monstruo_id, stat, valor) VALUES (?,?,?)", (mid, stat, str(val)))
        d[mid][stat] = val
        if stat == "vida":
            d[mid]["vida_max"] = val
        n += 1
    await update.effective_message.reply_text(
        f"✅ *{n} monstruos* de zona *{color}* — `{stat}` → *{val}*\n_Cambio aplicado en memoria y guardado en BD._",
        parse_mode="Markdown"
    )

async def cmd_ajustar_monstruos_zona(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ajuste relativo (+/-N) de un stat en todos los monstruos de una zona: /ajustar_monstruos_zona <color> <stat> +/-N"""
    if not db_helper.verificar_nivel(update.effective_user.id, 1):
        await update.effective_message.reply_text("❌ Sin acceso.")
        return
    args = context.args
    if len(args) != 3:
        await update.effective_message.reply_text(
            "Uso: `/ajustar_monstruos_zona <color> <stat> +/-N`\n\n"
            "Ejemplo: `/ajustar_monstruos_zona roja daño +50`\n"
            f"Colores: `{'` | `'.join(sorted(COLORES_ZONA))}`",
            parse_mode="Markdown"
        )
        return
    color, stat, delta_str = args[0].lower(), args[1].lower(), args[2]
    if color not in COLORES_ZONA:
        await update.effective_message.reply_text(f"❌ Color debe ser: `{'` | `'.join(sorted(COLORES_ZONA))}`", parse_mode="Markdown")
        return
    if stat not in STATS_MONSTRUO_VALIDOS:
        await update.effective_message.reply_text(f"❌ Stat debe ser: `{'` | `'.join(sorted(STATS_MONSTRUO_VALIDOS))}`", parse_mode="Markdown")
        return
    try:
        delta = int(delta_str)
    except ValueError:
        await update.effective_message.reply_text("❌ Delta debe ser entero con signo, ej: `+50` o `-20`", parse_mode="Markdown")
        return
    n = 0
    for d, mid in _iter_monstruos_zona(color):
        actual = d[mid].get(stat, 0)
        nuevo = max(1, actual + delta)
        _upsert("INSERT OR REPLACE INTO stats_overrides_monstruos (monstruo_id, stat, valor) VALUES (?,?,?)", (mid, stat, str(nuevo)))
        d[mid][stat] = nuevo
        if stat == "vida":
            d[mid]["vida_max"] = nuevo
        n += 1
    signo = "+" if delta >= 0 else ""
    await update.effective_message.reply_text(
        f"✅ *{n} monstruos* de zona *{color}* — `{stat}` ajustado *{signo}{delta}*\n_Cambio aplicado y guardado._",
        parse_mode="Markdown"
    )

# ==================== EDICIÓN MASIVA — ARMAS Y ARMADURAS ====================

def _ajustar_coleccion(coleccion: dict, stat: str, delta: int, tipo_filtro: str = None) -> int:
    """Aplica ajuste relativo a todos los ítems de la colección. Retorna N modificados."""
    n = 0
    for iid, item in coleccion.items():
        if tipo_filtro and item.get("tipo") != tipo_filtro:
            continue
        if stat not in item:
            continue
        current = item[stat]
        if not isinstance(current, (int, float)):
            continue
        nuevo = max(0, int(current + delta))
        _upsert("INSERT OR REPLACE INTO stats_overrides_items (item_id, stat, valor) VALUES (?,?,?)", (iid, stat, str(nuevo)))
        item[stat] = nuevo
        n += 1
    return n

async def cmd_ajustar_armas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ajuste relativo de un stat en TODAS las armas: /ajustar_armas <stat> +/-N"""
    if not db_helper.verificar_nivel(update.effective_user.id, 1):
        await update.effective_message.reply_text("❌ Sin acceso.")
        return
    args = context.args
    if len(args) != 2:
        await update.effective_message.reply_text(
            "Uso: `/ajustar_armas <stat> +/-N`\n\n"
            "Ejemplo: `/ajustar_armas daño +100`\n"
            f"Stats: `{'` | `'.join(sorted(STATS_ARMA))}`",
            parse_mode="Markdown"
        )
        return
    stat, delta_str = args[0].lower(), args[1]
    if stat not in STATS_ARMA:
        await update.effective_message.reply_text(f"❌ Stat no válido.\nUsa: `{'` | `'.join(sorted(STATS_ARMA))}`", parse_mode="Markdown")
        return
    try:
        delta = int(delta_str)
    except ValueError:
        await update.effective_message.reply_text("❌ Delta debe ser entero con signo, ej: `+100` o `-20`", parse_mode="Markdown")
        return
    from armas import ARMAS
    n = _ajustar_coleccion(ARMAS, stat, delta)
    signo = "+" if delta >= 0 else ""
    await update.effective_message.reply_text(
        f"✅ *{n} armas* — `{stat}` ajustado *{signo}{delta}*\n_Cambio aplicado y guardado._",
        parse_mode="Markdown"
    )

async def cmd_ajustar_armaduras(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ajuste relativo de un stat en TODAS las armaduras: /ajustar_armaduras <stat> +/-N"""
    if not db_helper.verificar_nivel(update.effective_user.id, 1):
        await update.effective_message.reply_text("❌ Sin acceso.")
        return
    args = context.args
    if len(args) != 2:
        await update.effective_message.reply_text(
            "Uso: `/ajustar_armaduras <stat> +/-N`\n\n"
            "Ejemplo: `/ajustar_armaduras defensa +50`\n"
            f"Stats: `{'` | `'.join(sorted(STATS_ARMADURA))}`",
            parse_mode="Markdown"
        )
        return
    stat, delta_str = args[0].lower(), args[1]
    if stat not in STATS_ARMADURA:
        await update.effective_message.reply_text(f"❌ Stat no válido.\nUsa: `{'` | `'.join(sorted(STATS_ARMADURA))}`", parse_mode="Markdown")
        return
    try:
        delta = int(delta_str)
    except ValueError:
        await update.effective_message.reply_text("❌ Delta debe ser entero con signo, ej: `+50` o `-10`", parse_mode="Markdown")
        return
    from armaduras import ARMADURAS
    n = _ajustar_coleccion(ARMADURAS, stat, delta)
    signo = "+" if delta >= 0 else ""
    await update.effective_message.reply_text(
        f"✅ *{n} armaduras* — `{stat}` ajustado *{signo}{delta}*\n_Cambio aplicado y guardado._",
        parse_mode="Markdown"
    )

# ==================== EDICIÓN MASIVA — PRECIOS ====================

async def cmd_ajustar_precio_tienda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/ajustar_precio_tienda <oro|eth|cr> <moneda> +/-N — todos los ítems de una tienda"""
    if not db_helper.verificar_nivel(update.effective_user.id, 1):
        await update.effective_message.reply_text("❌ Sin acceso.")
        return
    args = context.args
    if len(args) != 3:
        await update.effective_message.reply_text(
            "Uso: `/ajustar_precio_tienda <tienda> <moneda> +/-N`\n\n"
            "Tiendas: `oro` | `eth` | `cr`\n"
            "Monedas: `oro` | `eth` | `cr`\n"
            "Ejemplo: `/ajustar_precio_tienda oro oro +20` (sube 20 oro a todo en la tienda de oro)",
            parse_mode="Markdown"
        )
        return
    tienda, moneda, delta_str = args[0].lower(), args[1].lower(), args[2]
    if tienda not in ("oro", "eth", "cr") or moneda not in MONEDAS:
        await update.effective_message.reply_text("❌ Tienda y moneda deben ser `oro`, `eth` o `cr`.", parse_mode="Markdown")
        return
    try:
        delta = int(delta_str)
    except ValueError:
        await update.effective_message.reply_text("❌ Delta debe ser entero con signo, ej: `+20` o `-100`", parse_mode="Markdown")
        return
    import tienda as tienda_mod
    catalogo_map = {"oro": tienda_mod.CATALOGO_ORO, "eth": tienda_mod.CATALOGO_ETERNIUM}
    catalogo = catalogo_map.get(tienda)
    if catalogo is None:
        # tienda de créditos (rotación): buscar en CATALOGO_ORO con origen tienda_creditos
        catalogo = [i for i in tienda_mod.CATALOGO_ORO + tienda_mod.CATALOGO_ETERNIUM
                    if i.get("origen") == "tienda_creditos"]
    campo, campo_venta = MONEDAS[moneda]
    n = 0
    for item in catalogo:
        iid = item.get("id")
        if not iid:
            continue
        actual = item.get(campo, 0)
        nuevo = max(0, actual + delta)
        _upsert("INSERT OR REPLACE INTO stats_overrides_precios (item_id, moneda, valor) VALUES (?,?,?)", (iid, moneda, nuevo))
        item[campo] = nuevo
        if campo_venta:
            item[campo_venta] = int(nuevo * 0.7)
        n += 1
    signo = "+" if delta >= 0 else ""
    emoji_t = {"oro":"🪙","eth":"💎","cr":"✨"}[tienda]
    await update.effective_message.reply_text(
        f"✅ *{n} ítems* de tienda {emoji_t} — precio *{moneda}* ajustado *{signo}{delta}*\n_Guardado en BD._",
        parse_mode="Markdown"
    )

async def cmd_ajustar_precio_todos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/ajustar_precio_todos <moneda> +/-N — ajusta precio en TODOS los ítems"""
    if not db_helper.verificar_nivel(update.effective_user.id, 1):
        await update.effective_message.reply_text("❌ Sin acceso.")
        return
    args = context.args
    if len(args) != 2:
        await update.effective_message.reply_text(
            "Uso: `/ajustar_precio_todos <moneda> +/-N`\n\n"
            "Ejemplo: `/ajustar_precio_todos oro +50` (sube 50 oro a TODOS los ítems)",
            parse_mode="Markdown"
        )
        return
    moneda, delta_str = args[0].lower(), args[1]
    if moneda not in MONEDAS:
        await update.effective_message.reply_text("❌ Moneda: `oro`, `eth` o `cr`.", parse_mode="Markdown")
        return
    try:
        delta = int(delta_str)
    except ValueError:
        await update.effective_message.reply_text("❌ Delta debe ser entero con signo, ej: `+50` o `-100`", parse_mode="Markdown")
        return
    from armas import ARMAS
    from armaduras import ARMADURAS
    campo, campo_venta = MONEDAS[moneda]
    n = 0
    for coleccion in (ARMAS, ARMADURAS):
        for iid, item in coleccion.items():
            actual = item.get(campo, 0)
            if actual <= 0:
                continue
            nuevo = max(0, actual + delta)
            _upsert("INSERT OR REPLACE INTO stats_overrides_precios (item_id, moneda, valor) VALUES (?,?,?)", (iid, moneda, nuevo))
            item[campo] = nuevo
            if campo_venta:
                item[campo_venta] = int(nuevo * 0.7)
            n += 1
    _patch_precios()
    signo = "+" if delta >= 0 else ""
    await update.effective_message.reply_text(
        f"✅ *{n} ítems* — precio *{moneda}* ajustado *{signo}{delta}* en todos los ítems.\n_Guardado en BD._",
        parse_mode="Markdown"
    )

# ==================== BALANCE GLOBAL PANEL ====================

_BG_M_VIDA = "bg_m_vida"
_BG_M_DAÑO = "bg_m_daño"
_BG_M_DEF  = "bg_m_def"

def _bg_get(key: str) -> float:
    try:
        return float(db_helper.obtener_config(key, "1.0"))
    except Exception:
        return 1.0

def _bg_set(key: str, val: float) -> None:
    db_helper.establecer_config(key, f"{val:.4f}")

def _bg_step_monster(keys: list, factor: float) -> None:
    for k in keys:
        _bg_set(k, max(0.05, round(_bg_get(k) * factor, 4)))

def _bg_step_weapons(stat_keys: list, factor: float) -> int:
    from armas import ARMAS
    n = 0
    for iid, item in ARMAS.items():
        for sk in stat_keys:
            v = item.get(sk)
            if isinstance(v, (int, float)) and v > 0:
                nv = max(1, int(round(v * factor)))
                if nv != v:
                    item[sk] = nv
                    _upsert("INSERT OR REPLACE INTO stats_overrides_items (item_id, stat, valor) VALUES (?,?,?)", (iid, sk, str(nv)))
                    n += 1
    return n

def _bg_step_armors(stat_keys: list, factor: float) -> int:
    from armaduras import ARMADURAS
    n = 0
    for iid, item in ARMADURAS.items():
        for sk in stat_keys:
            v = item.get(sk)
            if isinstance(v, (int, float)) and v > 0:
                nv = max(1, int(round(v * factor)))
                if nv != v:
                    item[sk] = nv
                    _upsert("INSERT OR REPLACE INTO stats_overrides_items (item_id, stat, valor) VALUES (?,?,?)", (iid, sk, str(nv)))
                    n += 1
    return n

def _bg_step_pociones(factor: float) -> int:
    from pociones import POCIONES
    n = 0
    for pid, poc in POCIONES.items():
        ef = poc.get("efecto", "")
        if not ef or not _re.search(r'\d+', ef):
            continue
        def _scale(m, _f=factor):
            return str(max(1, int(round(int(m.group(0)) * _f))))
        nuevo = _re.sub(r'\d+', _scale, ef)
        if nuevo != ef:
            poc["efecto"] = nuevo
            _upsert("INSERT OR REPLACE INTO stats_overrides_items (item_id, stat, valor) VALUES (?,?,?)", (pid, "efecto", nuevo))
            n += 1
    return n

def _bg_reset_weapons():
    try:
        old_mod = importlib.import_module("armas")
        old_ref = old_mod.ARMAS
        conn = sqlite3.connect(db_helper.DB_PATH)
        c = conn.cursor()
        for iid in list(old_ref.keys()):
            c.execute("DELETE FROM stats_overrides_items WHERE item_id = ?", (iid,))
        conn.commit(); conn.close()
        fresh = importlib.reload(old_mod).ARMAS
        old_ref.clear(); old_ref.update(fresh)
    except Exception:
        pass

def _bg_reset_armors():
    try:
        old_mod = importlib.import_module("armaduras")
        old_ref = old_mod.ARMADURAS
        conn = sqlite3.connect(db_helper.DB_PATH)
        c = conn.cursor()
        for iid in list(old_ref.keys()):
            c.execute("DELETE FROM stats_overrides_items WHERE item_id = ?", (iid,))
        conn.commit(); conn.close()
        fresh = importlib.reload(old_mod).ARMADURAS
        old_ref.clear(); old_ref.update(fresh)
    except Exception:
        pass

def _bg_reset_pociones():
    try:
        old_mod = importlib.import_module("pociones")
        old_ref = old_mod.POCIONES
        conn = sqlite3.connect(db_helper.DB_PATH)
        c = conn.cursor()
        for iid in list(old_ref.keys()):
            c.execute("DELETE FROM stats_overrides_items WHERE item_id = ?", (iid,))
        conn.commit(); conn.close()
        fresh = importlib.reload(old_mod).POCIONES
        old_ref.clear(); old_ref.update(fresh)
    except Exception:
        pass

def _bg_reset_monsters():
    _bg_set(_BG_M_VIDA, 1.0)
    _bg_set(_BG_M_DAÑO, 1.0)
    _bg_set(_BG_M_DEF,  1.0)

def _bg_auto_balance() -> str:
    rows = _get_rows("SELECT nivel, hp_max FROM jugadores WHERE nivel > 1 AND hp_max > 0 LIMIT 200")
    if not rows:
        return "❌ Sin jugadores registrados para analizar."
    avg_nivel = sum(r[0] for r in rows) / len(rows)
    avg_hp    = sum(r[1] for r in rows) / len(rows)
    poder_est = (avg_hp / 10.0) ** 2
    vida_mon_base = int(poder_est ** 0.5 * 20)
    vida_mon_act  = max(1, int(vida_mon_base * _bg_get(_BG_M_VIDA)))
    target_ratio  = 2.0
    current_ratio = vida_mon_act / avg_hp if avg_hp > 0 else 1.0
    if abs(current_ratio - target_ratio) < 0.15:
        return (f"⚖️ Balance OK — ratio monstruo/HP: {current_ratio:.2f}\n"
                f"Nivel prom: {avg_nivel:.0f} | HP prom: {avg_hp:.0f}")
    factor = target_ratio / current_ratio
    _bg_step_monster([_BG_M_VIDA, _BG_M_DAÑO, _BG_M_DEF], factor)
    direction = "subidos" if factor > 1 else "bajados"
    return (f"🤖 Auto-balance: monstruos <b>{direction}</b> ×{factor:.2f}\n"
            f"Nivel prom: {avg_nivel:.0f} | HP prom: {avg_hp:.0f} | ratio: {current_ratio:.2f}→{target_ratio:.2f}")

def _bg_panel_text() -> str:
    mv  = _bg_get(_BG_M_VIDA)
    md  = _bg_get(_BG_M_DAÑO)
    mdf = _bg_get(_BG_M_DEF)
    try:
        from armas import ARMAS
        vals = [v.get("daño", 0) for v in ARMAS.values() if isinstance(v.get("daño"), (int, float))]
        avg_w = int(sum(vals) / len(vals)) if vals else 0
    except Exception:
        avg_w = 0
    try:
        from armaduras import ARMADURAS
        vdef = [v.get("defensa", 0) for v in ARMADURAS.values() if isinstance(v.get("defensa"), (int, float)) and v.get("defensa", 0) > 0]
        avg_a = int(sum(vdef) / len(vdef)) if vdef else 0
    except Exception:
        avg_a = 0
    return (
        "⚖️ <b>PANEL DE BALANCE GLOBAL</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "👹 <b>Monstruos</b> <i>(procedural)</i>\n"
        f"  Vida ×{mv:.2f} | Daño ×{md:.2f} | Def ×{mdf:.2f}\n\n"
        f"⚔️ <b>Armas</b> — daño promedio: <b>{avg_w}</b>\n"
        f"🛡️ <b>Armaduras</b> — defensa promedio: <b>{avg_a}</b>\n\n"
        "<i>+10% sube el valor, -10% lo baja. Reset restaura los valores originales del archivo fuente.</i>"
    )

def _bg_kb() -> InlineKeyboardMarkup:
    B = InlineKeyboardButton
    return InlineKeyboardMarkup([
        [B("👹 Vida +10%", callback_data="bgp_m_vida_up"), B("👹 Vida -10%", callback_data="bgp_m_vida_dn")],
        [B("👹 Daño +10%", callback_data="bgp_m_daño_up"), B("👹 Daño -10%", callback_data="bgp_m_daño_dn")],
        [B("👹 Def +10%",  callback_data="bgp_m_def_up"),  B("👹 Def -10%",  callback_data="bgp_m_def_dn")],
        [B("👹 TODO +10%", callback_data="bgp_m_all_up"),  B("👹 TODO -10%", callback_data="bgp_m_all_dn"), B("♻️ Reset Mon", callback_data="bgp_m_rst")],
        [B("⚔️ Daño +10%", callback_data="bgp_w_daño_up"), B("⚔️ Daño -10%", callback_data="bgp_w_daño_dn")],
        [B("⚔️ Crít +10%", callback_data="bgp_w_crit_up"), B("⚔️ Crít -10%", callback_data="bgp_w_crit_dn")],
        [B("⚔️ TODO +10%", callback_data="bgp_w_all_up"),  B("⚔️ TODO -10%", callback_data="bgp_w_all_dn"),  B("♻️ Reset Armas", callback_data="bgp_w_rst")],
        [B("🛡️ Def +10%",  callback_data="bgp_a_def_up"),  B("🛡️ Def -10%",  callback_data="bgp_a_def_dn")],
        [B("🛡️ Res +10%",  callback_data="bgp_a_res_up"),  B("🛡️ Res -10%",  callback_data="bgp_a_res_dn")],
        [B("🛡️ TODO +10%", callback_data="bgp_a_all_up"),  B("🛡️ TODO -10%", callback_data="bgp_a_all_dn"),  B("♻️ Reset Arm", callback_data="bgp_a_rst")],
        [B("🧪 Efecto +10%", callback_data="bgp_p_up"),    B("🧪 Efecto -10%", callback_data="bgp_p_dn"),    B("♻️ Reset Poc", callback_data="bgp_p_rst")],
        [B("🤖 Auto-Balance", callback_data="bgp_auto"),   B("💥 Reset TODO",  callback_data="bgp_rst_all")],
        [B("🔄 Actualizar",   callback_data="bgp_ref"),    B("◀️ Volver",       callback_data="panel_volver")],
    ])

async def cmd_balance_global(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not db_helper.verificar_nivel(update.effective_user.id, 1):
        await update.effective_message.reply_text("❌ Sin acceso.")
        return
    await update.effective_message.reply_text(
        _bg_panel_text(), parse_mode="HTML", reply_markup=_bg_kb()
    )

async def cb_balance_global(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not db_helper.verificar_nivel(update.effective_user.id, 1):
        await query.answer("❌ Sin acceso.", show_alert=True)
        return
    data = query.data
    UP, DN = 1.10, 1.0 / 1.10
    msg = ""
    try:
        if   data == "bgp_m_vida_up": _bg_step_monster([_BG_M_VIDA], UP);  msg = f"👹 Vida monstruo → ×{_bg_get(_BG_M_VIDA):.2f}"
        elif data == "bgp_m_vida_dn": _bg_step_monster([_BG_M_VIDA], DN);  msg = f"👹 Vida monstruo → ×{_bg_get(_BG_M_VIDA):.2f}"
        elif data == "bgp_m_daño_up": _bg_step_monster([_BG_M_DAÑO], UP);  msg = f"👹 Daño monstruo → ×{_bg_get(_BG_M_DAÑO):.2f}"
        elif data == "bgp_m_daño_dn": _bg_step_monster([_BG_M_DAÑO], DN);  msg = f"👹 Daño monstruo → ×{_bg_get(_BG_M_DAÑO):.2f}"
        elif data == "bgp_m_def_up":  _bg_step_monster([_BG_M_DEF],  UP);  msg = f"👹 Def monstruo → ×{_bg_get(_BG_M_DEF):.2f}"
        elif data == "bgp_m_def_dn":  _bg_step_monster([_BG_M_DEF],  DN);  msg = f"👹 Def monstruo → ×{_bg_get(_BG_M_DEF):.2f}"
        elif data == "bgp_m_all_up":  _bg_step_monster([_BG_M_VIDA, _BG_M_DAÑO, _BG_M_DEF], UP);  msg = "👹 Todos los stats de monstruo +10% aplicado"
        elif data == "bgp_m_all_dn":  _bg_step_monster([_BG_M_VIDA, _BG_M_DAÑO, _BG_M_DEF], DN);  msg = "👹 Todos los stats de monstruo -10% aplicado"
        elif data == "bgp_m_rst":     _bg_reset_monsters();  msg = "♻️ Monstruos restaurados a multiplicador ×1.00"
        elif data == "bgp_w_daño_up": n = _bg_step_weapons(["daño"], UP);  msg = f"⚔️ Daño +10% aplicado a {n} armas"
        elif data == "bgp_w_daño_dn": n = _bg_step_weapons(["daño"], DN);  msg = f"⚔️ Daño -10% aplicado a {n} armas"
        elif data == "bgp_w_crit_up": n = _bg_step_weapons(["critico", "velocidad"], UP);  msg = f"⚔️ Crítico/Velocidad +10% en {n} armas"
        elif data == "bgp_w_crit_dn": n = _bg_step_weapons(["critico", "velocidad"], DN);  msg = f"⚔️ Crítico/Velocidad -10% en {n} armas"
        elif data == "bgp_w_all_up":  n = _bg_step_weapons(["daño", "critico", "velocidad", "vida_extra", "defensa_extra"], UP);  msg = f"⚔️ Todos los stats +10% en {n} armas"
        elif data == "bgp_w_all_dn":  n = _bg_step_weapons(["daño", "critico", "velocidad", "vida_extra", "defensa_extra"], DN);  msg = f"⚔️ Todos los stats -10% en {n} armas"
        elif data == "bgp_w_rst":     _bg_reset_weapons();  msg = "♻️ Armas restauradas a valores originales"
        elif data == "bgp_a_def_up":  n = _bg_step_armors(["defensa"], UP);  msg = f"🛡️ Defensa +10% en {n} armaduras"
        elif data == "bgp_a_def_dn":  n = _bg_step_armors(["defensa"], DN);  msg = f"🛡️ Defensa -10% en {n} armaduras"
        elif data == "bgp_a_res_up":  n = _bg_step_armors(["resistencia_critico"], UP);  msg = f"🛡️ Resistencia crítico +10% en {n} armaduras"
        elif data == "bgp_a_res_dn":  n = _bg_step_armors(["resistencia_critico"], DN);  msg = f"🛡️ Resistencia crítico -10% en {n} armaduras"
        elif data == "bgp_a_all_up":  n = _bg_step_armors(["defensa", "resistencia_critico", "vida_extra", "defensa_extra"], UP);  msg = f"🛡️ Todos los stats +10% en {n} armaduras"
        elif data == "bgp_a_all_dn":  n = _bg_step_armors(["defensa", "resistencia_critico", "vida_extra", "defensa_extra"], DN);  msg = f"🛡️ Todos los stats -10% en {n} armaduras"
        elif data == "bgp_a_rst":     _bg_reset_armors();  msg = "♻️ Armaduras restauradas a valores originales"
        elif data == "bgp_p_up":      n = _bg_step_pociones(UP);  msg = f"🧪 Efectos de pociones +10% en {n} pociones"
        elif data == "bgp_p_dn":      n = _bg_step_pociones(DN);  msg = f"🧪 Efectos de pociones -10% en {n} pociones"
        elif data == "bgp_p_rst":     _bg_reset_pociones();  msg = "♻️ Pociones restauradas a valores originales"
        elif data == "bgp_rst_all":
            _bg_reset_monsters(); _bg_reset_weapons(); _bg_reset_armors(); _bg_reset_pociones()
            msg = "💥 Todo el balance reseteado a valores base del archivo"
        elif data == "bgp_auto":
            msg = _bg_auto_balance()
        elif data == "bgp_ref":
            msg = "🔄 Panel actualizado con valores actuales"
    except Exception as e:
        await query.answer(f"❌ Error al ejecutar acción: {e}"[:200], show_alert=True)
        return
    # Toast de confirmación — visible aunque el panel no cambie visualmente
    try:
        await query.answer(msg[:200] if msg else "✅ Hecho")
    except Exception:
        pass
    # Actualizar el panel con el resultado
    text = _bg_panel_text()
    if msg:
        text = f"✅ {msg}\n\n" + text
    try:
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=_bg_kb())
    except Exception as e:
        if "not modified" not in str(e).lower():
            await query.message.reply_text(f"⚠️ No se pudo actualizar el panel:\n{e}")


# ==================== REGISTRO DE HANDLERS ====================

def registrar_handlers(app):
    app.add_handler(CommandHandler("ver_stamina",      cmd_ver_stamina))
    app.add_handler(CommandHandler("set_stamina",      cmd_set_stamina))
    app.add_handler(CommandHandler("buscar_monstruo",  cmd_buscar_monstruo))
    app.add_handler(CommandHandler("ver_monstruo",     cmd_ver_monstruo))
    app.add_handler(CommandHandler("editar_monstruo",  cmd_editar_monstruo))
    app.add_handler(CommandHandler("reset_monstruo",   cmd_reset_monstruo))
    app.add_handler(CommandHandler("editar_arma",      cmd_editar_arma))
    app.add_handler(CommandHandler("editar_armadura",  cmd_editar_armadura))
    app.add_handler(CommandHandler("ver_arma",         cmd_ver_arma))
    app.add_handler(CommandHandler("ver_armadura",     cmd_ver_armadura))
    app.add_handler(CommandHandler("reset_arma",       cmd_reset_arma))
    app.add_handler(CommandHandler("reset_armadura",   cmd_reset_armadura))
    app.add_handler(CommandHandler("editar_precio",          cmd_editar_precio))
    app.add_handler(CommandHandler("ver_precio",             cmd_ver_precio))
    app.add_handler(CommandHandler("editar_monstruos_zona",  cmd_editar_monstruos_zona))
    app.add_handler(CommandHandler("ajustar_monstruos_zona", cmd_ajustar_monstruos_zona))
    app.add_handler(CommandHandler("ajustar_armas",          cmd_ajustar_armas))
    app.add_handler(CommandHandler("ajustar_armaduras",      cmd_ajustar_armaduras))
    app.add_handler(CommandHandler("ajustar_precio_tienda",  cmd_ajustar_precio_tienda))
    app.add_handler(CommandHandler("ajustar_precio_todos",   cmd_ajustar_precio_todos))
    app.add_handler(CommandHandler("balance_global",         cmd_balance_global))
    app.add_handler(CallbackQueryHandler(cb_balance_global,  pattern=r"^bgp_"))

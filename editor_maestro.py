#!/usr/bin/env python3
# editor_maestro.py
# Sistema de edición conversacional para el superadmin.
# Comandos: /sa_jugador, /sa_monstruo, /sa_arma, /sa_armadura,
#            /sa_precio, /sa_tasas, /sa_xp, /sa_clase, /sa_numeros

import os
import sqlite3
import glob
import importlib
from telegram import Update
from telegram.ext import (
    ContextTypes, CommandHandler, MessageHandler,
    ConversationHandler, filters
)

import html as _html
import db_helper
import superadmin as sa

DB_PATH = "aethelgard.db"
SUPERADMIN_ID = int(os.environ.get("SUPERADMIN_ID", 0))

def _esc_md(s: str) -> str:
    return _html.escape(str(s))

# ── ConversationHandler states ─────────────────────────────────────────────
(
    JUGADOR_BUSCAR, JUGADOR_STAT, JUGADOR_VALOR,
    MONST_BUSCAR,   MONST_STAT,   MONST_VALOR,
    ARMA_BUSCAR,    ARMA_STAT,    ARMA_VALOR,
    ARMAD_BUSCAR,   ARMAD_STAT,   ARMAD_VALOR,
    PRECIO_BUSCAR,  PRECIO_MONEDA, PRECIO_VALOR,
    TASAS_ELEGIR,   TASAS_VALOR,
    XP_MODO,        XP_NIVEL,      XP_VALOR,
    CLASE_ELEGIR,   CLASE_STAT,    CLASE_VALOR,
    POCION_BUSCAR,  POCION_STAT,   POCION_VALOR,
    MATERIAL_BUSCAR,MATERIAL_STAT, MATERIAL_VALOR,
) = range(29)

CANCELAR_FILTER = filters.Regex(r"^/?(cancelar|cancel)$")
SEP = " | "  # separador para listas de opciones


async def _safe_reply(msg, text, pm="Markdown", **kw):
    """Send reply; if Markdown/HTML parse fails, retry as plain text."""
    try:
        await msg.reply_text(text, parse_mode=pm, **kw)
    except Exception:
        try:
            await msg.reply_text(text, **kw)
        except Exception:
            pass



# ── Helpers internos ───────────────────────────────────────────────────────

def _sa(user_id: int) -> bool:
    return user_id == SUPERADMIN_ID

def _gcfg(key: str, default) -> str:
    return db_helper.obtener_config(key, str(default))

def _scfg(key: str, value) -> None:
    db_helper.establecer_config(key, str(value))
    try:
        import config_balance as _cb
        _cb.recargar()
    except Exception:
        pass

def _gcfg_float(key: str, default: float) -> float:
    try:
        return float(_gcfg(key, default))
    except Exception:
        return default

def _gcfg_int(key: str, default: int) -> int:
    try:
        return int(_gcfg(key, default))
    except Exception:
        return default

async def _deny(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _safe_reply(update.effective_message, "\u274c Acceso denegado.")
    return ConversationHandler.END

async def _cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await _safe_reply(update.effective_message, "Edici\u00f3n cancelada.")
    return ConversationHandler.END

def _fmt_dict(d: dict, campos: list) -> str:
    lines = []
    for c in campos:
        if c in d:
            lines.append(f"  \u2022 {c}: {d[c]}")
    return "\n".join(lines) if lines else "(sin datos)"

# ═══════════════════════════════════════════════════════════════════════════
#  PATCH DE CONSTANTES AL ARRANCAR
# ═══════════════════════════════════════════════════════════════════════════

def cargar_overrides_maestro():
    """Aplica todos los overrides guardados en config_bot al iniciar el bot."""
    _patch_tasas()
    _patch_xp()
    _patch_stats_clase()
    _patch_items_overrides()
    _patch_config_balance()


def _patch_config_balance():
    """Re-aplica todos los valores de config_bot al módulo config_balance en memoria."""
    try:
        import config_balance as _cb
        _cb.recargar()
    except Exception:
        pass


def _patch_items_overrides():
    """Aplica todos los overrides de items (armas/armaduras/pociones/mat/monturas) al arrancar."""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT item_id, stat, valor FROM stats_overrides_items")
        rows = c.fetchall()
        conn.close()
    except Exception:
        return

    catalogos = {}
    for item_id, stat, valor_str in rows:
        # Determinar a qué catálogo pertenece el item_id buscando en todos
        if item_id not in catalogos:
            for mod_name, attr in [
                ("armas", "ARMAS"),
                ("armaduras", "ARMADURAS"),
                ("pociones", "POCIONES"),
                ("materiales", "MATERIALES"),
                ("monturas", "MONTURAS"),
            ]:
                try:
                    mod = importlib.import_module(mod_name)
                    d = getattr(mod, attr, {})
                    if item_id in d:
                        catalogos[item_id] = d[item_id]
                        break
                except Exception:
                    continue

        item = catalogos.get(item_id)
        if item is None:
            continue

        # Convertir valor al tipo correcto según el actual
        current = item.get(stat)
        try:
            if valor_str in ("None", "null", "none", ""):
                valor = None
            elif isinstance(current, bool):
                valor = valor_str.lower() in ("true", "1", "si", "sí", "yes")
            elif isinstance(current, int):
                valor = int(float(valor_str))
            elif isinstance(current, float):
                valor = float(valor_str)
            else:
                try:
                    valor = int(valor_str)
                except ValueError:
                    try:
                        valor = float(valor_str)
                    except ValueError:
                        valor = valor_str
        except Exception:
            valor = valor_str
        item[stat] = valor

def _patch_tasas():
    try:
        import banco
        banco.ORO_A_ETERNIUM_TASA = _gcfg_int("banco_oro_a_eth", 1000)
        banco.ETERNIUM_A_ORO_TASA  = _gcfg_int("banco_eth_a_oro",  900)
    except Exception:
        pass
    try:
        import economia
        economia.CREDITO_A_ETERNIUM = _gcfg_float("eco_cred_a_eth", 0.1)
        economia.ETERNIUM_A_CREDITO = _gcfg_float("eco_eth_a_cred", 3.0)
    except Exception:
        pass
    try:
        import viajes
        viajes.PRECIO_VUELO_RAPIDO = _gcfg_int("viaje_vuelo_rapido", 50)
    except Exception:
        pass

def _patch_xp():
    try:
        import clases
        def _xp_override(nivel: int) -> int:
            ov = db_helper.obtener_config(f"xp_nivel_{nivel}", "")
            if ov:
                return int(ov)
            base = _gcfg_float("xp_formula_base", 200.0)
            exp  = _gcfg_float("xp_formula_exp",  1.5)
            return int(base * (nivel ** exp))
        clases._calcular_xp_necesaria       = _xp_override
        clases.calcular_experiencia_necesaria = lambda n: _xp_override(n) if n > 0 else 0
    except Exception:
        pass

def _patch_stats_clase():
    try:
        import clases
        for clase in ["vanguardista", "acechante", "tejehechizos", "maestro_caza"]:
            for stat in ["vida_max", "daño_base", "defensa_base", "carga_base"]:
                v = db_helper.obtener_config(f"clase_{clase}_{stat}", "")
                if v:
                    clases.STATS_BASE[clase][stat] = int(v)
        for const, default in [("VIDA_POR_NIVEL", 5), ("DAÑO_POR_NIVEL", 0.5),
                                ("DEFENSA_POR_NIVEL", 1/3), ("CARGA_POR_NIVEL", 2)]:
            v = db_helper.obtener_config(f"crec_{const.lower()}", "")
            if v:
                setattr(clases, const, float(v))
    except Exception:
        pass

# ═══════════════════════════════════════════════════════════════════════════
#  /sa_numeros — VER TODA LA CONFIGURACIÓN ACTUAL
# ═══════════════════════════════════════════════════════════════════════════

async def cmd_sa_numeros(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _sa(update.effective_user.id):
        return await _deny(update, context)

    oro_a_eth = _gcfg_int("banco_oro_a_eth", 1000)
    eth_a_oro = _gcfg_int("banco_eth_a_oro",  900)
    cred_a_eth = _gcfg_float("eco_cred_a_eth", 0.1)
    eth_a_cred = _gcfg_float("eco_eth_a_cred", 3.0)
    vuelo      = _gcfg_int("viaje_vuelo_rapido", 50)
    xp_base    = _gcfg_float("xp_formula_base", 200.0)
    xp_exp     = _gcfg_float("xp_formula_exp",  1.5)

    texto = (
        "\u2699\ufe0f *CONFIGURACI\u00d3N ACTUAL DEL JUEGO*\n\n"
        "\U0001f4b1 *TASAS DE CAMBIO (banco)*\n"
        f"  \u2022 1000 \U0001fa99 = 1 \U0001f48e  |  actualmente: {oro_a_eth} \U0001fa99 = 1 \U0001f48e\n"
        f"  \u2022 1 \U0001f48e = {eth_a_oro} \U0001fa99\n"
        f"  \u2022 1 \u2728 = {cred_a_eth} \U0001f48e\n"
        f"  \u2022 1 \U0001f48e = {eth_a_cred} \u2728\n"
        f"  \u2022 Vuelo r\u00e1pido: {vuelo} \U0001f48e\n\n"
        "\U0001f31f *F\u00d3RMULA XP*\n"
        f"  int({xp_base} \u00d7 nivel^{xp_exp})\n"
        f"  Ejemplos: Lv1={int(xp_base*1**xp_exp)} | Lv5={int(xp_base*5**xp_exp)} | Lv10={int(xp_base*10**xp_exp)} | Lv50={int(xp_base*50**xp_exp)}\n\n"
        "\U0001f9f1 *STATS BASE DE CLASES*\n"
    )

    try:
        import clases
        for clase, emoji in [("vanguardista","\U0001f6e1\ufe0f"),("acechante","\U0001f5e1\ufe0f"),
                              ("tejehechizos","\U0001f52e"),("maestro_caza","\U0001f3f9")]:
            s = clases.STATS_BASE[clase]
            texto += f"  {emoji} {clase}: vida={s['vida_max']} | daño={s['daño_base']} | def={s['defensa_base']} | carga={s['carga_base']}\n"
        texto += (
            f"\n  Crecimiento/nivel: vida+{clases.VIDA_POR_NIVEL} | "
            f"daño+{clases.DAÑO_POR_NIVEL} | def+{round(clases.DEFENSA_POR_NIVEL,3)}\n"
        )
    except Exception:
        texto += "  (no disponible)\n"

    texto += "\n_Usa /sa\_tasas, /sa\_xp, /sa\_clase, /sa\_jugador, /sa\_monstruo, /sa\_arma, /sa\_armadura, /sa\_precio para editar._"
    await _safe_reply(update.effective_message, texto, pm="Markdown")

# ═══════════════════════════════════════════════════════════════════════════
#  /sa_jugador — EDITAR STATS DE UN JUGADOR
# ═══════════════════════════════════════════════════════════════════════════

STATS_JUGADOR = {
    "nivel": int, "xp": int, "hp_actual": int, "hp_max": int,
    "oro": int, "eternium": int, "creditos_vacio": int,
    "reputacion": int, "stamina_actual": int, "stamina_maxima": int,
    "clase": str, "faccion": str,
}
STATS_JUG_LABEL = {
    "nivel":"Nivel","xp":"Experiencia","hp_actual":"HP Actual","hp_max":"HP Máximo",
    "oro":"\U0001fa99 Oro","eternium":"\U0001f48e Eternium","creditos_vacio":"\u2728 Créditos",
    "reputacion":"Reputación","stamina_actual":"Stamina Actual","stamina_maxima":"Stamina Máxima",
    "clase":"Clase","faccion":"Facción",
}

async def sa_jugador_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _sa(update.effective_user.id):
        return await _deny(update, context)
    await _safe_reply(update.effective_message, 
        "\U0001f464 *Editar stats de jugador*\n\n"
        "¿ID de Telegram o nombre del personaje?\n_(Escribe /cancelar para salir)_",
        pm="Markdown"
    )
    return JUGADOR_BUSCAR

async def sa_jugador_buscar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.strip()
    jug = None
    # Intentar por ID
    try:
        uid = int(texto)
        jug = db_helper.obtener_jugador(uid)
    except ValueError:
        pass
    # Intentar por nombre
    if not jug:
        todos = db_helper.obtener_todos_jugadores()
        for j in todos:
            if j.get("nombre_personaje", "").lower() == texto.lower():
                jug = j; break
    if not jug:
        await _safe_reply(update.effective_message, "\u274c Jugador no encontrado. Intenta con otro ID/nombre o /cancelar.")
        return JUGADOR_BUSCAR

    context.user_data["jug_id"] = jug["user_id"]
    stats_txt = "\n".join([
        f"  \u2022 {STATS_JUG_LABEL.get(k,k)}: {jug.get(k,'—')}"
        for k in STATS_JUGADOR
    ])
    claves = " | ".join(STATS_JUGADOR.keys())
    await _safe_reply(update.effective_message, 
        f"\U0001f464 *{_esc_md(jug['nombre_personaje'])}* (ID: {jug['user_id']})"
        f"\n\n{stats_txt}\n\n"
        f"¿Qué stat editar?\n`{claves}`",
        pm="Markdown"
    )
    return JUGADOR_STAT

async def sa_jugador_stat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stat = update.message.text.strip().lower()
    if stat not in STATS_JUGADOR:
        await _safe_reply(update.effective_message, f"\u274c Stat no válido. Opciones: {list(STATS_JUGADOR.keys())}")
        return JUGADOR_STAT
    context.user_data["jug_stat"] = stat
    jug = db_helper.obtener_jugador(context.user_data["jug_id"])
    actual = jug.get(stat, "—") if jug else "—"
    await _safe_reply(update.effective_message, 
        f"Stat: *{STATS_JUG_LABEL.get(stat, stat)}*\nValor actual: `{actual}`\n\n¿Nuevo valor?",
        pm="Markdown"
    )
    return JUGADOR_VALOR

async def sa_jugador_valor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stat = context.user_data["jug_stat"]
    uid  = context.user_data["jug_id"]
    raw  = update.message.text.strip()
    tipo = STATS_JUGADOR[stat]
    try:
        valor = tipo(raw)
    except ValueError:
        await _safe_reply(update.effective_message, f"\u274c Valor inválido para {stat} (esperado {tipo.__name__}).")
        return JUGADOR_VALOR

    db_helper.actualizar_jugador(uid, **{stat: valor})
    jug = db_helper.obtener_jugador(uid)
    nombre = jug["nombre_personaje"] if jug else str(uid)
    await _safe_reply(update.effective_message, 
        f"\u2705 *{_esc_md(nombre)}* — {STATS_JUG_LABEL.get(stat, stat)} actualizado a `{valor}`.",
        pm="Markdown"
    )
    context.user_data.clear()
    return ConversationHandler.END

# ═══════════════════════════════════════════════════════════════════════════
#  /sa_monstruo — EDITAR STATS DE UN MONSTRUO
# ═══════════════════════════════════════════════════════════════════════════

STATS_MONST = ["hp", "ataque", "defensa", "xp", "oro_min", "oro_max", "nombre"]

def _buscar_monstruo(texto: str):
    """Devuelve (mid, mdict, modname) o None."""
    texto = texto.lower()
    for archivo in glob.glob("monstruos_*zona_*.py"):
        mod_name = archivo[:-3]
        try:
            mod = importlib.import_module(mod_name)
        except Exception:
            continue
        for attr in ["MONSTRUOS_MAZMORRAS_NORMAL","MONSTRUOS_MAZMORRAS_DIFICIL","MONSTRUOS_NORMALES"]:
            d = getattr(mod, attr, None)
            if not isinstance(d, dict):
                continue
            for mid, mdata in d.items():
                if mid.lower() == texto or mdata.get("nombre","").lower() == texto:
                    return mid, mdata, mod_name, attr
    return None

async def sa_monstruo_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _sa(update.effective_user.id):
        return await _deny(update, context)
    await _safe_reply(update.effective_message, 
        "\U0001f9df *Editar monstruo*\n\n"
        "¿Nombre o ID del monstruo?\n_(Tip: usa /buscar\_monstruo <nombre> primero)_\n/cancelar para salir.",
        pm="Markdown"
    )
    return MONST_BUSCAR

async def sa_monstruo_buscar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.strip()
    resultado = _buscar_monstruo(texto)
    if not resultado:
        await _safe_reply(update.effective_message, "\u274c Monstruo no encontrado. Intenta otro nombre/ID o /cancelar.")
        return MONST_BUSCAR
    mid, mdata, mod_name, attr = resultado
    context.user_data.update({"monst_id": mid, "monst_mod": mod_name, "monst_attr": attr})
    stats_txt = _fmt_dict(mdata, STATS_MONST)
    await _safe_reply(update.effective_message, 
        f"\U0001f9df *{_esc_md(mdata.get('nombre', mid))}* (`{mid}`)\n\n{stats_txt}\n\n"
        f"¿Qué stat editar?\n`{SEP.join(STATS_MONST)}`",
        pm="Markdown"
    )
    return MONST_STAT

async def sa_monstruo_stat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stat = update.message.text.strip().lower()
    if stat not in STATS_MONST:
        await _safe_reply(update.effective_message, f"\u274c Stat no válido. Opciones: {STATS_MONST}")
        return MONST_STAT
    context.user_data["monst_stat"] = stat
    mid = context.user_data["monst_id"]
    resultado = _buscar_monstruo(mid)
    actual = resultado[1].get(stat, "—") if resultado else "—"
    await _safe_reply(update.effective_message, 
        f"Stat: *{stat}*\nValor actual: `{actual}`\n\n¿Nuevo valor?",
        pm="Markdown"
    )
    return MONST_VALOR

async def sa_monstruo_valor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mid  = context.user_data["monst_id"]
    stat = context.user_data["monst_stat"]
    raw  = update.message.text.strip()
    resultado = _buscar_monstruo(mid)
    if not resultado:
        await _safe_reply(update.effective_message, "\u274c Monstruo no encontrado ya.")
        context.user_data.clear()
        return ConversationHandler.END
    _, mdata, _, _ = resultado
    actual = mdata.get(stat)
    try:
        if stat == "nombre":
            valor = raw
        elif isinstance(actual, float):
            valor = float(raw)
        else:
            valor = int(raw)
    except ValueError:
        await _safe_reply(update.effective_message, "\u274c Valor inválido.")
        return MONST_VALOR

    # Guardar en BD + parchear en memoria
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO stats_overrides_monstruos (monstruo_id, stat, valor) VALUES (?,?,?)",
              (mid, stat, str(valor)))
    conn.commit(); conn.close()
    mdata[stat] = valor

    await _safe_reply(update.effective_message, 
        f"\u2705 Monstruo *{_esc_md(mdata.get('nombre', mid))}* — `{stat}` → `{valor}`",
        pm="Markdown"
    )
    context.user_data.clear()
    return ConversationHandler.END

# ═══════════════════════════════════════════════════════════════════════════
#  /sa_arma y /sa_armadura — EDITAR STATS DE ITEMS
# ═══════════════════════════════════════════════════════════════════════════

STATS_ARMA    = ["daño","critico","velocidad","peso","vida_extra","defensa_extra","nivel_requerido","rareza"]
STATS_ARMAD   = ["defensa","resistencia_critico","velocidad_movimiento","peso","vida_extra","defensa_extra","nivel_requerido","rareza"]
STATS_POCION  = ["nivel_requerido","rareza","precio_oro","precio_venta_oro","precio_eternium","precio_venta_eternium","precio_creditos"]
STATS_MATERIAL= ["nivel_requerido","rareza","valor_crafteo","precio_venta_oro","precio_venta_eternium","precio_creditos"]

def _buscar_item(texto: str, tipo: str):
    """tipo = 'arma' o 'armadura'"""
    try:
        if tipo == "arma":
            from armas import ARMAS as D
        else:
            from armaduras import ARMADURAS as D
    except ImportError:
        return None, None
    texto = texto.lower()
    for iid, item in D.items():
        if iid.lower() == texto or item.get("nombre","").lower() == texto:
            return iid, item
    return None, None

async def _item_start(update, context, tipo):
    if not _sa(update.effective_user.id):
        return await _deny(update, context)
    context.user_data["item_tipo"] = tipo
    nombre_tipo = "arma" if tipo == "arma" else "armadura"
    await _safe_reply(update.effective_message, 
        f"\u2694\ufe0f *Editar {nombre_tipo}*\n\n"
        f"¿Nombre o ID de la {nombre_tipo}?\n/cancelar para salir.",
        pm="Markdown"
    )
    return ARMA_BUSCAR if tipo == "arma" else ARMAD_BUSCAR

async def sa_arma_start(update, context):    return await _item_start(update, context, "arma")
async def sa_armadura_start(update, context): return await _item_start(update, context, "armadura")

async def _item_buscar(update, context, next_stat_state):
    tipo  = context.user_data.get("item_tipo", "arma")
    texto = update.message.text.strip()
    iid, item = _buscar_item(texto, tipo)
    if not item:
        await _safe_reply(update.effective_message, f"\u274c {tipo.capitalize()} no encontrada. Intenta otro nombre/ID o /cancelar.")
        return ARMA_BUSCAR if tipo == "arma" else ARMAD_BUSCAR
    context.user_data["item_id"] = iid
    campos = STATS_ARMA if tipo == "arma" else STATS_ARMAD
    stats_txt = _fmt_dict(item, campos + ["precio_oro","precio_eternium","precio_creditos"])
    await _safe_reply(update.effective_message, 
        f"\u2694\ufe0f *{_esc_md(item.get('nombre', iid))}* (`{iid}`)\n\n{stats_txt}\n\n"
        f"¿Qué stat editar?\n`{SEP.join(campos)}`",
        pm="Markdown"
    )
    return next_stat_state

async def sa_arma_buscar(update, context):    return await _item_buscar(update, context, ARMA_STAT)
async def sa_armadura_buscar(update, context): return await _item_buscar(update, context, ARMAD_STAT)

async def _item_stat(update, context, campos, next_val_state, buscar_state):
    stat = update.message.text.strip().lower()
    if stat not in campos:
        await _safe_reply(update.effective_message, f"\u274c Stat no válido. Opciones: {campos}")
        return buscar_state
    context.user_data["item_stat"] = stat
    tipo = context.user_data.get("item_tipo", "arma")
    iid  = context.user_data["item_id"]
    _, item = _buscar_item(iid, tipo)
    actual = item.get(stat, "—") if item else "—"
    await _safe_reply(update.effective_message, 
        f"Stat: *{stat}*\nValor actual: `{actual}`\n\n¿Nuevo valor?",
        pm="Markdown"
    )
    return next_val_state

async def sa_arma_stat(update, context):
    return await _item_stat(update, context, STATS_ARMA, ARMA_VALOR, ARMA_STAT)
async def sa_armadura_stat(update, context):
    return await _item_stat(update, context, STATS_ARMAD, ARMAD_VALOR, ARMAD_STAT)

async def _item_valor(update, context):
    tipo = context.user_data.get("item_tipo", "arma")
    iid  = context.user_data["item_id"]
    stat = context.user_data["item_stat"]
    raw  = update.message.text.strip()
    _, item = _buscar_item(iid, tipo)
    if not item:
        await _safe_reply(update.effective_message, "\u274c Item no encontrado.")
        context.user_data.clear(); return ConversationHandler.END
    actual = item.get(stat)
    try:
        valor = float(raw) if isinstance(actual, float) else int(raw)
    except ValueError:
        await _safe_reply(update.effective_message, "\u274c Valor inválido (debe ser número).")
        return ARMA_VALOR if tipo == "arma" else ARMAD_VALOR

    # Guardar override en BD + parchear memoria
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO stats_overrides_items (item_id, stat, valor) VALUES (?,?,?)",
              (iid, stat, str(valor)))
    conn.commit(); conn.close()
    item[stat] = valor

    await _safe_reply(update.effective_message, 
        f"\u2705 *{_esc_md(item.get('nombre', iid))}* — `{stat}` → `{valor}`",
        pm="Markdown"
    )
    context.user_data.clear()
    return ConversationHandler.END

async def sa_arma_valor(update, context):    return await _item_valor(update, context)
async def sa_armadura_valor(update, context): return await _item_valor(update, context)


# ═══════════════════════════════════════════════════════════════════════════
#  /sa_pocion — EDITAR STATS DE UNA POCIÓN
# ═══════════════════════════════════════════════════════════════════════════

def _buscar_pocion(texto: str):
    """Busca una poción por nombre o ID. Devuelve (pid, dict) o (None, None)."""
    try:
        import pociones as mod
        datos = mod.POCIONES
    except Exception:
        return None, None
    txt = texto.strip().lower()
    if txt in datos:
        return txt, datos[txt]
    for pid, p in datos.items():
        if txt in p.get("nombre", "").lower():
            return pid, p
    return None, None

async def sa_pocion_start(update, context):
    if not _sa(update.effective_user.id):
        return await _deny(update, context)
    await _safe_reply(update.effective_message,
        "🧪 *Editar Poción*\n\n"
        "¿Nombre o ID de la poción?\n/cancelar para salir.",
        pm="Markdown"
    )
    return POCION_BUSCAR

async def sa_pocion_buscar(update, context):
    texto = update.message.text.strip()
    pid, p = _buscar_pocion(texto)
    if not p:
        await _safe_reply(update.effective_message,
            "❌ Poción no encontrada. Prueba otro nombre/ID o /cancelar.")
        return POCION_BUSCAR
    context.user_data["pocion_id"] = pid
    stats_txt = _fmt_dict(p, STATS_POCION)
    await _safe_reply(update.effective_message,
        f"🧪 *{_esc_md(p.get('nombre', pid))}* (`{pid}`)\n\n{stats_txt}\n\n"
        f"¿Qué campo editar?\n`{SEP.join(STATS_POCION)}`",
        pm="Markdown"
    )
    return POCION_STAT

async def sa_pocion_stat(update, context):
    stat = update.message.text.strip().lower()
    if stat not in STATS_POCION:
        await _safe_reply(update.effective_message,
            f"❌ Campo no válido. Opciones: {STATS_POCION}")
        return POCION_STAT
    context.user_data["pocion_stat"] = stat
    pid = context.user_data["pocion_id"]
    _, p = _buscar_pocion(pid)
    actual = p.get(stat, "—") if p else "—"
    await _safe_reply(update.effective_message,
        f"Campo: *{stat}*\nValor actual: `{actual}`\n\n¿Nuevo valor?",
        pm="Markdown"
    )
    return POCION_VALOR

async def sa_pocion_valor(update, context):
    pid  = context.user_data["pocion_id"]
    stat = context.user_data["pocion_stat"]
    raw  = update.message.text.strip()
    _, p = _buscar_pocion(pid)
    if not p:
        await _safe_reply(update.effective_message, "❌ Poción no encontrada.")
        context.user_data.clear(); return ConversationHandler.END
    actual = p.get(stat)
    try:
        valor = float(raw) if isinstance(actual, float) else int(raw)
    except ValueError:
        await _safe_reply(update.effective_message, "❌ Valor inválido (debe ser número).")
        return POCION_VALOR
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO stats_overrides_items (item_id, stat, valor) VALUES (?,?,?)",
              (pid, stat, str(valor)))
    conn.commit(); conn.close()
    p[stat] = valor
    await _safe_reply(update.effective_message,
        f"✅ *{_esc_md(p.get('nombre', pid))}* — `{stat}` → `{valor}`",
        pm="Markdown"
    )
    context.user_data.clear()
    return ConversationHandler.END


# ═══════════════════════════════════════════════════════════════════════════
#  /sa_material — EDITAR STATS DE UN MATERIAL
# ═══════════════════════════════════════════════════════════════════════════

def _buscar_material(texto: str):
    """Busca un material por nombre o ID. Devuelve (mid, dict) o (None, None)."""
    try:
        import materiales as mod
        datos = mod.MATERIALES
    except Exception:
        return None, None
    txt = texto.strip().lower()
    if txt in datos:
        return txt, datos[txt]
    for mid, m in datos.items():
        if txt in m.get("nombre", "").lower():
            return mid, m
    return None, None

async def sa_material_start(update, context):
    if not _sa(update.effective_user.id):
        return await _deny(update, context)
    await _safe_reply(update.effective_message,
        "🪨 *Editar Material*\n\n"
        "¿Nombre o ID del material?\n/cancelar para salir.",
        pm="Markdown"
    )
    return MATERIAL_BUSCAR

async def sa_material_buscar(update, context):
    texto = update.message.text.strip()
    mid, m = _buscar_material(texto)
    if not m:
        await _safe_reply(update.effective_message,
            "❌ Material no encontrado. Prueba otro nombre/ID o /cancelar.")
        return MATERIAL_BUSCAR
    context.user_data["material_id"] = mid
    stats_txt = _fmt_dict(m, STATS_MATERIAL)
    await _safe_reply(update.effective_message,
        f"🪨 *{_esc_md(m.get('nombre', mid))}* (`{mid}`)\n\n{stats_txt}\n\n"
        f"¿Qué campo editar?\n`{SEP.join(STATS_MATERIAL)}`",
        pm="Markdown"
    )
    return MATERIAL_STAT

async def sa_material_stat(update, context):
    stat = update.message.text.strip().lower()
    if stat not in STATS_MATERIAL:
        await _safe_reply(update.effective_message,
            f"❌ Campo no válido. Opciones: {STATS_MATERIAL}")
        return MATERIAL_STAT
    context.user_data["material_stat"] = stat
    mid = context.user_data["material_id"]
    _, m = _buscar_material(mid)
    actual = m.get(stat, "—") if m else "—"
    await _safe_reply(update.effective_message,
        f"Campo: *{stat}*\nValor actual: `{actual}`\n\n¿Nuevo valor?",
        pm="Markdown"
    )
    return MATERIAL_VALOR

async def sa_material_valor(update, context):
    mid  = context.user_data["material_id"]
    stat = context.user_data["material_stat"]
    raw  = update.message.text.strip()
    _, m = _buscar_material(mid)
    if not m:
        await _safe_reply(update.effective_message, "❌ Material no encontrado.")
        context.user_data.clear(); return ConversationHandler.END
    actual = m.get(stat)
    try:
        valor = float(raw) if isinstance(actual, float) else int(raw)
    except ValueError:
        await _safe_reply(update.effective_message, "❌ Valor inválido (debe ser número).")
        return MATERIAL_VALOR
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO stats_overrides_items (item_id, stat, valor) VALUES (?,?,?)",
              (mid, stat, str(valor)))
    conn.commit(); conn.close()
    m[stat] = valor
    await _safe_reply(update.effective_message,
        f"✅ *{_esc_md(m.get('nombre', mid))}* — `{stat}` → `{valor}`",
        pm="Markdown"
    )
    context.user_data.clear()
    return ConversationHandler.END

# ═══════════════════════════════════════════════════════════════════════════
#  /sa_precio — EDITAR PRECIO DE UN ITEM EN LA TIENDA
# ═══════════════════════════════════════════════════════════════════════════

async def sa_precio_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _sa(update.effective_user.id):
        return await _deny(update, context)
    await _safe_reply(update.effective_message, 
        "\U0001f3f7\ufe0f *Editar precio de item*\n\n"
        "¿Nombre o ID del item (arma o armadura)?\n/cancelar para salir.",
        pm="Markdown"
    )
    return PRECIO_BUSCAR

async def sa_precio_buscar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.strip()
    iid, item = _buscar_item(texto, "arma")
    if not item:
        iid, item = _buscar_item(texto, "armadura")
    if not item:
        await _safe_reply(update.effective_message, "\u274c Item no encontrado. Intenta otro nombre/ID o /cancelar.")
        return PRECIO_BUSCAR
    context.user_data["precio_id"] = iid
    precios = (
        f"  \u2022 \U0001fa99 Oro: {item.get('precio_oro',0)}\n"
        f"  \u2022 \U0001f48e Eternium: {item.get('precio_eternium',0)}\n"
        f"  \u2022 \u2728 Créditos: {item.get('precio_creditos',0)}"
    )
    await _safe_reply(update.effective_message, 
        f"\U0001f3f7\ufe0f *{_esc_md(item.get('nombre', iid))}*\n\n{precios}\n\n"
        "¿Qué moneda editar?\n`oro | eth | cr`",
        pm="Markdown"
    )
    return PRECIO_MONEDA

async def sa_precio_moneda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    moneda = update.message.text.strip().lower()
    if moneda not in ("oro", "eth", "cr"):
        await _safe_reply(update.effective_message, "\u274c Escribe: `oro`, `eth` o `cr`", pm="Markdown")
        return PRECIO_MONEDA
    context.user_data["precio_moneda"] = moneda
    iid = context.user_data["precio_id"]
    item = None
    for t in ("arma","armadura"):
        _, item = _buscar_item(iid, t)
        if item: break
    campo = {"oro":"precio_oro","eth":"precio_eternium","cr":"precio_creditos"}[moneda]
    actual = item.get(campo, 0) if item else 0
    await _safe_reply(update.effective_message, 
        f"Moneda: `{moneda}`\nPrecio actual: `{actual}`\n\n¿Nuevo precio?",
        pm="Markdown"
    )
    return PRECIO_VALOR

async def sa_precio_valor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    iid    = context.user_data["precio_id"]
    moneda = context.user_data["precio_moneda"]
    raw    = update.message.text.strip()
    try:
        precio = int(raw)
        if precio < 0: raise ValueError
    except ValueError:
        await _safe_reply(update.effective_message, "\u274c Ingresa un número entero positivo.")
        return PRECIO_VALOR

    # Parchear en la BD
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO stats_overrides_precios (item_id, moneda, valor) VALUES (?,?,?)",
              (iid, moneda, precio))
    conn.commit(); conn.close()

    # Parchear en memoria
    campo = {"oro":"precio_oro","eth":"precio_eternium","cr":"precio_creditos"}[moneda]
    for t in ("arma","armadura"):
        _, item = _buscar_item(iid, t)
        if item:
            item[campo] = precio
            nombre = item.get("nombre", iid)
            break
    else:
        nombre = iid

    await _safe_reply(update.effective_message, 
        f"\u2705 *{_esc_md(nombre)}* — precio `{moneda}` → `{precio}`",
        pm="Markdown"
    )
    context.user_data.clear()
    return ConversationHandler.END

# ═══════════════════════════════════════════════════════════════════════════
#  /sa_tasas — EDITAR TASAS DE CAMBIO
# ═══════════════════════════════════════════════════════════════════════════

TASAS_OPCIONES = {
    "1": ("banco_oro_a_eth",   "Oro → Eth (cuántos oros por 1 Eth)",       1000,  int),
    "2": ("banco_eth_a_oro",   "Eth → Oro (cuántos oros da 1 Eth)",         900,  int),
    "3": ("eco_cred_a_eth",    "Crédito → Eth (cuántos Eth da 1 Crédito)",  0.1, float),
    "4": ("eco_eth_a_cred",    "Eth → Créditos (cuántos Cred da 1 Eth)",    3.0, float),
    "5": ("viaje_vuelo_rapido","Precio vuelo rápido (Eternium)",             50,  int),
}

async def sa_tasas_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _sa(update.effective_user.id):
        return await _deny(update, context)

    lineas = "\U0001f4b1 *TASAS DE CAMBIO ACTUALES*\n\n"
    for num, (key, desc, default, _) in TASAS_OPCIONES.items():
        actual = _gcfg(key, default)
        lineas += f"  *{num}.* {desc}\n      Actual: `{actual}`\n"
    lineas += "\n¿Qué tasa cambiar? Responde con el número (1-5) o /cancelar."
    await _safe_reply(update.effective_message, lineas, pm="Markdown")
    return TASAS_ELEGIR

async def sa_tasas_elegir(update: Update, context: ContextTypes.DEFAULT_TYPE):
    op = update.message.text.strip()
    if op not in TASAS_OPCIONES:
        await _safe_reply(update.effective_message, "\u274c Elige un número del 1 al 5.")
        return TASAS_ELEGIR
    context.user_data["tasa_op"] = op
    key, desc, default, tipo = TASAS_OPCIONES[op]
    actual = _gcfg(key, default)
    await _safe_reply(update.effective_message, 
        f"Tasa seleccionada: *{desc}*\nValor actual: `{actual}`\n\n¿Nuevo valor?",
        pm="Markdown"
    )
    return TASAS_VALOR

async def sa_tasas_valor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    op  = context.user_data["tasa_op"]
    key, desc, default, tipo = TASAS_OPCIONES[op]
    raw = update.message.text.strip()
    try:
        valor = tipo(raw)
        if valor <= 0: raise ValueError
    except ValueError:
        await _safe_reply(update.effective_message, f"\u274c Valor inválido (debe ser {tipo.__name__} > 0).")
        return TASAS_VALOR

    _scfg(key, valor)
    _patch_tasas()  # aplicar en caliente

    await _safe_reply(update.effective_message, 
        f"\u2705 *{desc}* → `{valor}`\n_Aplicado de inmediato._",
        pm="Markdown"
    )
    context.user_data.clear()
    return ConversationHandler.END

# ═══════════════════════════════════════════════════════════════════════════
#  /sa_xp — EDITAR FÓRMULA DE EXPERIENCIA
# ═══════════════════════════════════════════════════════════════════════════

async def sa_xp_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _sa(update.effective_user.id):
        return await _deny(update, context)
    base = _gcfg_float("xp_formula_base", 200.0)
    exp  = _gcfg_float("xp_formula_exp",  1.5)
    await _safe_reply(update.effective_message, 
        "\U0001f31f *FÓRMULA DE EXPERIENCIA*\n\n"
        f"Fórmula actual: `int({base} × nivel ^ {exp})`\n"
        f"Ejemplos: Lv1={int(base*1**exp)} | Lv5={int(base*5**exp)} | Lv10={int(base*10**exp)} | Lv20={int(base*20**exp)} | Lv50={int(base*50**exp)}\n\n"
        "¿Qué editar?\n"
        "  *1.* Base de la fórmula (actualmente: `" + str(base) + "`)\n"
        "  *2.* Exponente de la fórmula (actualmente: `" + str(exp) + "`)\n"
        "  *3.* XP específica para un nivel concreto\n"
        "  *4.* Ver/limpiar todos los overrides de nivel\n"
        "/cancelar para salir.",
        pm="Markdown"
    )
    return XP_MODO

async def sa_xp_modo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    modo = update.message.text.strip()
    if modo not in ("1","2","3","4"):
        await _safe_reply(update.effective_message, "\u274c Elige 1, 2, 3 o 4.")
        return XP_MODO
    context.user_data["xp_modo"] = modo

    if modo == "4":
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT clave, valor FROM config_bot WHERE clave LIKE 'xp_nivel_%' ORDER BY clave")
        rows = c.fetchall(); conn.close()
        if rows:
            txt = "\n".join([f"  Lv{r[0].replace('xp_nivel_','')} → {r[1]} XP" for r in rows])
            await _safe_reply(update.effective_message, 
                f"\U0001f4cb Overrides de XP por nivel:\n{txt}\n\n"
                "Escribe el nivel para borrarlo, o 'limpiar' para borrar todos.",
                pm="Markdown"
            )
        else:
            await _safe_reply(update.effective_message, "No hay overrides de nivel. Todo usa la fórmula base.")
        context.user_data.clear()
        return ConversationHandler.END

    if modo in ("1","2"):
        clave = "xp_formula_base" if modo == "1" else "xp_formula_exp"
        actual = _gcfg(clave, 200.0 if modo == "1" else 1.5)
        await _safe_reply(update.effective_message, 
            f"Valor actual: `{actual}`\n\n¿Nuevo valor?",
            pm="Markdown"
        )
        context.user_data["xp_clave"] = clave
        return XP_VALOR

    # modo == 3
    await _safe_reply(update.effective_message, "¿Para qué nivel? (1-100)")
    return XP_NIVEL

async def sa_xp_nivel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw = update.message.text.strip()

    # Manejar limpiar overrides
    if raw.lower() == "limpiar":
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("DELETE FROM config_bot WHERE clave LIKE 'xp_nivel_%'")
        conn.commit(); conn.close()
        _patch_xp()
        await _safe_reply(update.effective_message, "\u2705 Todos los overrides de XP por nivel eliminados.")
        context.user_data.clear()
        return ConversationHandler.END

    try:
        nivel = int(raw)
        if not 1 <= nivel <= 200: raise ValueError
    except ValueError:
        await _safe_reply(update.effective_message, "\u274c Nivel debe ser entre 1 y 200.")
        return XP_NIVEL

    context.user_data["xp_nivel"] = nivel
    base = _gcfg_float("xp_formula_base", 200.0)
    exp  = _gcfg_float("xp_formula_exp",  1.5)
    formula = int(base * (nivel ** exp))
    override = _gcfg(f"xp_nivel_{nivel}", "")
    actual = override if override else f"{formula} (fórmula)"
    await _safe_reply(update.effective_message, 
        f"Nivel *{nivel}*\nXP actual: `{actual}`\n\n¿Nueva XP requerida?",
        pm="Markdown"
    )
    return XP_VALOR

async def sa_xp_valor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw  = update.message.text.strip()
    modo = context.user_data.get("xp_modo")

    if modo in ("1","2"):
        clave = context.user_data["xp_clave"]
        try:
            valor = float(raw)
            if valor <= 0: raise ValueError
        except ValueError:
            await _safe_reply(update.effective_message, "\u274c Valor inválido (número > 0).")
            return XP_VALOR
        _scfg(clave, valor)
        _patch_xp()
        await _safe_reply(update.effective_message, 
            f"\u2705 `{clave}` → `{valor}`\n_Fórmula actualizada y aplicada._",
            pm="Markdown"
        )
    else:
        nivel = context.user_data.get("xp_nivel")
        try:
            xp = int(raw)
            if xp <= 0: raise ValueError
        except ValueError:
            await _safe_reply(update.effective_message, "\u274c XP debe ser entero positivo.")
            return XP_VALOR
        _scfg(f"xp_nivel_{nivel}", xp)
        _patch_xp()
        await _safe_reply(update.effective_message, 
            f"\u2705 Nivel *{nivel}* → `{xp}` XP requerida.\n_Aplicado de inmediato._",
            pm="Markdown"
        )

    context.user_data.clear()
    return ConversationHandler.END

# ═══════════════════════════════════════════════════════════════════════════
#  /sa_clase — EDITAR STATS BASE DE CLASE
# ═══════════════════════════════════════════════════════════════════════════

CLASES_VALIDAS = ["vanguardista","acechante","tejehechizos","maestro_caza"]
STATS_CLASE_BASE = ["vida_max","daño_base","defensa_base","carga_base"]
CREC_GLOBALES = {
    "vida_por_nivel":    ("VIDA_POR_NIVEL",    5.0),
    "daño_por_nivel":    ("DAÑO_POR_NIVEL",    0.5),
    "defensa_por_nivel": ("DEFENSA_POR_NIVEL", 1/3),
    "carga_por_nivel":   ("CARGA_POR_NIVEL",   2.0),
}

async def sa_clase_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _sa(update.effective_user.id):
        return await _deny(update, context)
    try:
        import clases
        info = ""
        for cl in CLASES_VALIDAS:
            s = clases.STATS_BASE[cl]
            info += f"  \u2022 {cl}: vida={s['vida_max']} daño={s['daño_base']} def={s['defensa_base']} carga={s['carga_base']}\n"
        info += (
            f"\nCrecimiento/nivel:\n"
            f"  vida+{clases.VIDA_POR_NIVEL} | daño+{clases.DAÑO_POR_NIVEL} | "
            f"def+{round(clases.DEFENSA_POR_NIVEL,3)} | carga+{clases.CARGA_POR_NIVEL}"
        )
    except Exception:
        info = "(no disponible)"

    await _safe_reply(update.effective_message, 
        "\U0001f9f1 *Editar stats de clase*\n\n" + info +
        "\n\n¿Qué clase editar?\n`vanguardista | acechante | tejehechizos | maestro_caza | global`\n"
        "_(global = crecimiento por nivel para todas las clases)_\n/cancelar para salir.",
        pm="Markdown"
    )
    return CLASE_ELEGIR

async def sa_clase_elegir(update: Update, context: ContextTypes.DEFAULT_TYPE):
    clase = update.message.text.strip().lower()
    if clase not in CLASES_VALIDAS and clase != "global":
        await _safe_reply(update.effective_message, "\u274c Clase no válida. Opciones: " + str(CLASES_VALIDAS + ["global"]))
        return CLASE_ELEGIR
    context.user_data["clase_sel"] = clase

    if clase == "global":
        opciones = "\n".join([f"  `{k}` (actual: {_gcfg(f'crec_{k}', v[1])})" for k, v in CREC_GLOBALES.items()])
        await _safe_reply(update.effective_message, 
            f"\U0001f310 *Crecimiento global por nivel*\n\n{opciones}\n\n¿Qué stat editar?",
            pm="Markdown"
        )
    else:
        try:
            import clases
            s = clases.STATS_BASE[clase]
            stats_txt = "\n".join([f"  \u2022 {stat}: {s.get(stat,'—')}" for stat in STATS_CLASE_BASE])
        except Exception:
            stats_txt = "(no disponible)"
        await _safe_reply(update.effective_message, 
            f"\U0001f9f1 *{clase}*\n\n{stats_txt}\n\n"
            f"¿Qué stat editar?\n`{SEP.join(STATS_CLASE_BASE)}`",
            pm="Markdown"
        )
    return CLASE_STAT

async def sa_clase_stat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    clase = context.user_data["clase_sel"]
    stat  = update.message.text.strip().lower()

    if clase == "global":
        if stat not in CREC_GLOBALES:
            await _safe_reply(update.effective_message, f"\u274c Opciones: {list(CREC_GLOBALES.keys())}")
            return CLASE_STAT
    else:
        if stat not in STATS_CLASE_BASE:
            await _safe_reply(update.effective_message, f"\u274c Opciones: {STATS_CLASE_BASE}")
            return CLASE_STAT

    context.user_data["clase_stat"] = stat

    if clase == "global":
        const_name, default = CREC_GLOBALES[stat]
        actual = _gcfg(f"crec_{stat}", default)
    else:
        try:
            import clases
            actual = clases.STATS_BASE[clase].get(stat, "—")
        except Exception:
            actual = "—"

    await _safe_reply(update.effective_message, 
        f"Stat: *{stat}*\nValor actual: `{actual}`\n\n¿Nuevo valor?",
        pm="Markdown"
    )
    return CLASE_VALOR

async def sa_clase_valor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    clase = context.user_data["clase_sel"]
    stat  = context.user_data["clase_stat"]
    raw   = update.message.text.strip()

    try:
        valor = float(raw)
    except ValueError:
        await _safe_reply(update.effective_message, "\u274c Valor inválido (número).")
        return CLASE_VALOR

    if clase == "global":
        _scfg(f"crec_{stat}", valor)
    else:
        _scfg(f"clase_{clase}_{stat}", int(valor))

    _patch_stats_clase()

    await _safe_reply(update.effective_message, 
        f"\u2705 *{clase if clase != 'global' else 'Global'}* — `{stat}` → `{valor}`\n_Aplicado de inmediato._",
        pm="Markdown"
    )
    context.user_data.clear()
    return ConversationHandler.END

# ═══════════════════════════════════════════════════════════════════════════
#  REGISTRO DE HANDLERS
# ═══════════════════════════════════════════════════════════════════════════

def registrar_handlers(app):
    # Comando informativo (sin conversación)
    app.add_handler(CommandHandler("sa_numeros", cmd_sa_numeros))

    texto_no_cmd = filters.TEXT & ~filters.COMMAND

    # ── /sa_jugador ────────────────────────────────────────────────────────
    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("sa_jugador", sa_jugador_start)],
        states={
            JUGADOR_BUSCAR: [MessageHandler(texto_no_cmd, sa_jugador_buscar)],
            JUGADOR_STAT:   [MessageHandler(texto_no_cmd, sa_jugador_stat)],
            JUGADOR_VALOR:  [MessageHandler(texto_no_cmd, sa_jugador_valor)],
        },
        fallbacks=[MessageHandler(CANCELAR_FILTER, _cancel),
                   CommandHandler("cancelar", _cancel)],
        allow_reentry=True
    ))

    # ── /sa_monstruo ──────────────────────────────────────────────────────
    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("sa_monstruo", sa_monstruo_start)],
        states={
            MONST_BUSCAR: [MessageHandler(texto_no_cmd, sa_monstruo_buscar)],
            MONST_STAT:   [MessageHandler(texto_no_cmd, sa_monstruo_stat)],
            MONST_VALOR:  [MessageHandler(texto_no_cmd, sa_monstruo_valor)],
        },
        fallbacks=[MessageHandler(CANCELAR_FILTER, _cancel),
                   CommandHandler("cancelar", _cancel)],
        allow_reentry=True
    ))

    # ── /sa_arma ──────────────────────────────────────────────────────────
    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("sa_arma", sa_arma_start)],
        states={
            ARMA_BUSCAR: [MessageHandler(texto_no_cmd, sa_arma_buscar)],
            ARMA_STAT:   [MessageHandler(texto_no_cmd, sa_arma_stat)],
            ARMA_VALOR:  [MessageHandler(texto_no_cmd, sa_arma_valor)],
        },
        fallbacks=[MessageHandler(CANCELAR_FILTER, _cancel),
                   CommandHandler("cancelar", _cancel)],
        allow_reentry=True
    ))

    # ── /sa_armadura ──────────────────────────────────────────────────────
    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("sa_armadura", sa_armadura_start)],
        states={
            ARMAD_BUSCAR: [MessageHandler(texto_no_cmd, sa_armadura_buscar)],
            ARMAD_STAT:   [MessageHandler(texto_no_cmd, sa_armadura_stat)],
            ARMAD_VALOR:  [MessageHandler(texto_no_cmd, sa_armadura_valor)],
        },
        fallbacks=[MessageHandler(CANCELAR_FILTER, _cancel),
                   CommandHandler("cancelar", _cancel)],
        allow_reentry=True
    ))

    # ── /sa_precio ────────────────────────────────────────────────────────
    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("sa_precio", sa_precio_start)],
        states={
            PRECIO_BUSCAR:  [MessageHandler(texto_no_cmd, sa_precio_buscar)],
            PRECIO_MONEDA:  [MessageHandler(texto_no_cmd, sa_precio_moneda)],
            PRECIO_VALOR:   [MessageHandler(texto_no_cmd, sa_precio_valor)],
        },
        fallbacks=[MessageHandler(CANCELAR_FILTER, _cancel),
                   CommandHandler("cancelar", _cancel)],
        allow_reentry=True
    ))

    # ── /sa_tasas ─────────────────────────────────────────────────────────
    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("sa_tasas", sa_tasas_start)],
        states={
            TASAS_ELEGIR: [MessageHandler(texto_no_cmd, sa_tasas_elegir)],
            TASAS_VALOR:  [MessageHandler(texto_no_cmd, sa_tasas_valor)],
        },
        fallbacks=[MessageHandler(CANCELAR_FILTER, _cancel),
                   CommandHandler("cancelar", _cancel)],
        allow_reentry=True
    ))

    # ── /sa_xp ────────────────────────────────────────────────────────────
    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("sa_xp", sa_xp_start)],
        states={
            XP_MODO:  [MessageHandler(texto_no_cmd, sa_xp_modo)],
            XP_NIVEL: [MessageHandler(texto_no_cmd, sa_xp_nivel)],
            XP_VALOR: [MessageHandler(texto_no_cmd, sa_xp_valor)],
        },
        fallbacks=[MessageHandler(CANCELAR_FILTER, _cancel),
                   CommandHandler("cancelar", _cancel)],
        allow_reentry=True
    ))

    # ── /sa_clase ─────────────────────────────────────────────────────────
    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("sa_clase", sa_clase_start)],
        states={
            CLASE_ELEGIR: [MessageHandler(texto_no_cmd, sa_clase_elegir)],
            CLASE_STAT:   [MessageHandler(texto_no_cmd, sa_clase_stat)],
            CLASE_VALOR:  [MessageHandler(texto_no_cmd, sa_clase_valor)],
        },
        fallbacks=[MessageHandler(CANCELAR_FILTER, _cancel),
                   CommandHandler("cancelar", _cancel)],
        allow_reentry=True
    ))

    # ── /sa_pocion ────────────────────────────────────────────────────────
    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("sa_pocion", sa_pocion_start)],
        states={
            POCION_BUSCAR: [MessageHandler(texto_no_cmd, sa_pocion_buscar)],
            POCION_STAT:   [MessageHandler(texto_no_cmd, sa_pocion_stat)],
            POCION_VALOR:  [MessageHandler(texto_no_cmd, sa_pocion_valor)],
        },
        fallbacks=[MessageHandler(CANCELAR_FILTER, _cancel),
                   CommandHandler("cancelar", _cancel)],
        allow_reentry=True
    ))

    # ── /sa_material ──────────────────────────────────────────────────────
    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("sa_material", sa_material_start)],
        states={
            MATERIAL_BUSCAR: [MessageHandler(texto_no_cmd, sa_material_buscar)],
            MATERIAL_STAT:   [MessageHandler(texto_no_cmd, sa_material_stat)],
            MATERIAL_VALOR:  [MessageHandler(texto_no_cmd, sa_material_valor)],
        },
        fallbacks=[MessageHandler(CANCELAR_FILTER, _cancel),
                   CommandHandler("cancelar", _cancel)],
        allow_reentry=True
    ))

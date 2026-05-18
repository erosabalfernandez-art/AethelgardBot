#!/usr/bin/env python3
# simulador_pve.py
# Simulador PvE para superadmin: prueba combates contra todos los enemigos del juego.
# Comando: /simulador_pve  (solo superadmin)

from __future__ import annotations

import random
from typing import Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters

from datos_zona import ZONAS
from armas import ARMAS
from armaduras import ARMADURAS
from pociones import POCIONES
import db_helper

# ═══════════════════════════════════════════════════════════════════════════
# ESTADO EN MEMORIA
# ═══════════════════════════════════════════════════════════════════════════

_sim: dict = {}  # uid -> estado

def _estado(uid: int) -> dict:
    if uid not in _sim:
        _sim[uid] = _estado_inicial()
    return _sim[uid]

def _estado_inicial() -> dict:
    return {
        "paso": "menu",
        "tipo": None,         # z / m / r / v
        "color": None,        # azul / amarilla / roja / negra
        "zona_id": None,
        "subtipo": None,
        "mon_idx": 0,
        "clase": "vanguardista",
        "nivel": 50,
        "reenc": 0,
        "arma": None,         # arma_N
        "armaduras": {},      # slot -> armadura_N
        "poc_sel": None,      # pocion_N
        "combate_activo": False,
        "hp_j": 0, "hp_j_max": 0,
        "atk_j": 0, "def_j": 0, "crit_j": 0,
        "hp_m": 0, "hp_m_max": 0,
        "atk_m": 0, "def_m": 0,
        "atk_m_base": 0, "def_m_base": 0, "hp_m_base": 0,
        "mon_nombre": "",
        "log": [],
        "ronda": 0,
        "busqueda": None,     # arma / armadura / pocion
        "busq_slot": None,
    }

# ═══════════════════════════════════════════════════════════════════════════
# CONSTANTES DEL JUEGO
# ═══════════════════════════════════════════════════════════════════════════

STATS_BASE = {
    "vanguardista": {"vida_max": 140, "daño_base": 12, "defensa_base": 14},
    "acechante":    {"vida_max": 90,  "daño_base": 20, "defensa_base": 5},
    "tejehechizos": {"vida_max": 80,  "daño_base": 18, "defensa_base": 4},
    "maestro_caza": {"vida_max": 100, "daño_base": 16, "defensa_base": 7},
}
VIDA_POR_NIVEL    = 5
DAÑO_POR_NIVEL    = 0.5
DEFENSA_POR_NIVEL = 1/3
BONO_REENC        = 0.05

MULT_SUBTIPO = {
    "normales":           1.0,
    "mini_boss":          2.5,
    "jefes_zona_normal":  8.0,
    "jefes_zona_dificil": 20.0,
    "mazmorras_normal":   1.8,
    "mazmorras_dificil":  2.5,
    "vacio_faccion":      15.0,
    "vacio_jefe":         50.0,
}

MULT_RAID = {
    "raid_facil":      {"hp": 5000,  "atk_min": 50,  "atk_max": 150,  "def": 20},
    "raid_normal":     {"hp": 10000, "atk_min": 100, "atk_max": 300,  "def": 40},
    "raid_dificil":    {"hp": 20000, "atk_min": 200, "atk_max": 600,  "def": 80},
    "raid_legendario": {"hp": 40000, "atk_min": 400, "atk_max": 1200, "def": 150},
}

MONSTRUOS_VACIO = [
    {"nombre": "El Devorador de Luz",     "lore": "Faccion Alianza — Entidad del vacio que consume la luz."},
    {"nombre": "El Senor de las Sombras", "lore": "Faccion Imperio — Corrupcion encarnada que acecha al Imperio."},
    {"nombre": "El Corruptor Eterno",     "lore": "Faccion Sindicato — Criatura ancestral devoradora de almas."},
]
AETHERON = {"nombre": "Aetheron el Devorador", "lore": "El Dios del Vacio en persona. Su presencia borra la existencia."}

COLOR_EMOJI   = {"azul": "🔵", "amarilla": "🟡", "roja": "🔴", "negra": "⚫"}
ORDEN_ZONAS   = ["azul", "amarilla", "roja", "negra"]
CLASE_EMOJI   = {"vanguardista": "🛡️", "acechante": "🗡️", "tejehechizos": "🔮", "maestro_caza": "🏹"}
SUBTIPO_LABEL = {
    "normales":           "Monstruos normales",
    "mini_boss":          "Mini-jefes",
    "jefes_zona_normal":  "Jefe de zona (Normal)",
    "jefes_zona_dificil": "Jefe de zona (Dificil)",
    "mazmorras_normal":   "Mazmorra Normal",
    "mazmorras_dificil":  "Mazmorra Dificil",
    "raid_facil":         "Raid — Facil",
    "raid_normal":        "Raid — Normal",
    "raid_dificil":       "Raid — Dificil",
    "raid_legendario":    "Raid — Legendario",
    "vacio_faccion":      "Noche del Vacio — Monstruos",
    "vacio_jefe":         "Noche del Vacio — Aetheron",
}

# ═══════════════════════════════════════════════════════════════════════════
# CALCULOS DE STATS
# ═══════════════════════════════════════════════════════════════════════════

def _vida_base(clase: str, nivel: int, reenc: int) -> int:
    base  = STATS_BASE[clase]["vida_max"]
    total = base + (nivel - 1) * VIDA_POR_NIVEL
    return int(total * (1 + BONO_REENC * reenc))

def _atk_base(clase: str, nivel: int, reenc: int) -> int:
    base  = STATS_BASE[clase]["daño_base"]
    total = base + int((nivel - 1) * DAÑO_POR_NIVEL)
    return int(total * (1 + BONO_REENC * reenc))

def _def_base(clase: str, nivel: int, reenc: int) -> int:
    base  = STATS_BASE[clase]["defensa_base"]
    total = base + int((nivel - 1) * DEFENSA_POR_NIVEL)
    return int(total * (1 + BONO_REENC * reenc))

def _calc_stats_jugador(e: dict) -> tuple:
    """Devuelve (hp_max, atk, def, crit_pct)."""
    clase = e["clase"]
    nivel = e["nivel"]
    reenc = e["reenc"]
    vida = _vida_base(clase, nivel, reenc)
    atk  = _atk_base(clase, nivel, reenc)
    defn = _def_base(clase, nivel, reenc)
    crit = 0
    if e.get("arma") and e["arma"] in ARMAS:
        a     = ARMAS[e["arma"]]
        atk  += a.get("daño", 0)
        vida += a.get("vida_extra", 0)
        defn += a.get("defensa_extra", 0)
        crit  = a.get("critico", 0)
    for slot, ak in e.get("armaduras", {}).items():
        if ak in ARMADURAS:
            arm  = ARMADURAS[ak]
            defn += arm.get("defensa", 0)
            vida += arm.get("vida_extra", 0)
            defn += arm.get("defensa_extra", 0)
    return vida, atk, defn, crit

def _poder_jugador_sim(e: dict) -> float:
    hp, atk, defn, crit = _calc_stats_jugador(e)
    dps = atk * (1 + crit / 100)
    return dps * hp * (1 + defn / 100)

def _gen_monster_stats(e: dict, subtipo: str, nombre: str) -> tuple:
    """Devuelve (hp, atk, def) escalados al poder del jugador simulado."""
    if subtipo.startswith("raid_"):
        cfg  = MULT_RAID[subtipo]
        return cfg["hp"], (cfg["atk_min"] + cfg["atk_max"]) // 2, cfg["def"]
    poder_jug = _poder_jugador_sim(e)
    mult      = MULT_SUBTIPO.get(subtipo, 1.0)
    pm        = poder_jug * mult
    vida    = max(1, int(pm ** 0.5 * 20))
    daño    = max(1, int(pm ** 0.5 * 4))
    defensa = max(1, int(pm ** 0.5 * 2))
    return vida, daño, defensa

def _calc_daño(atk: int, def_: int, crit_pct: int = 0) -> tuple:
    """Devuelve (daño_infligido, es_critico)."""
    red = def_ / (def_ + 100) if def_ > 0 else 0.0
    dmg = max(1, int(atk * (1 - red)))
    es_crit = random.random() < (0.05 + crit_pct / 100)
    if es_crit:
        dmg = int(dmg * 1.5)
    return dmg, es_crit

# ═══════════════════════════════════════════════════════════════════════════
# EQUIPAMIENTO (mejor/peor por zona y clase)
# ═══════════════════════════════════════════════════════════════════════════

def _zonas_accesibles(zona_color: str) -> list:
    idx = ORDEN_ZONAS.index(zona_color) if zona_color in ORDEN_ZONAS else 0
    return ORDEN_ZONAS[:idx + 1]

def _get_zona_color(e: dict) -> str:
    if e.get("zona_id"):
        zona = next((z for z in ZONAS if z["id"] == e["zona_id"]), None)
        if zona:
            return zona.get("color", "azul")
    return "azul"

def _filtrar_armas(clase: str, zona_color: str, nivel: int) -> list:
    accesibles = _zonas_accesibles(zona_color)
    result = []
    for k, a in ARMAS.items():
        if a.get("clase_requerida") and a["clase_requerida"] != clase:
            continue
        if a.get("zona") and a["zona"] not in accesibles:
            continue
        if a.get("nivel_requerido", 0) > nivel:
            continue
        result.append({**a, "id": k})
    return result

def _filtrar_armaduras(clase: str, zona_color: str, nivel: int, slot: Optional[str] = None) -> list:
    accesibles = _zonas_accesibles(zona_color)
    result = []
    for k, arm in ARMADURAS.items():
        if arm.get("clase_requerida") and arm["clase_requerida"] != clase:
            continue
        if arm.get("zona") and arm["zona"] not in accesibles:
            continue
        if arm.get("nivel_requerido", 0) > nivel:
            continue
        if slot and arm.get("tipo") != slot:
            continue
        result.append({**arm, "id": k})
    return result

def _equipar_mejor(e: dict):
    zona_color = _get_zona_color(e)
    clase, nivel = e["clase"], e["nivel"]
    armas_disp = _filtrar_armas(clase, zona_color, nivel)
    if armas_disp:
        e["arma"] = max(armas_disp, key=lambda a: (a.get("rareza", 0), a.get("daño", 0)))["id"]
    e["armaduras"] = {}
    for slot in ["casco", "pechera", "grebas", "botas", "guantes", "capa"]:
        arms = _filtrar_armaduras(clase, zona_color, nivel, slot)
        if arms:
            e["armaduras"][slot] = max(arms, key=lambda a: (a.get("rareza", 0), a.get("defensa", 0)))["id"]

def _equipar_peor(e: dict):
    zona_color = _get_zona_color(e)
    clase, nivel = e["clase"], e["nivel"]
    armas_disp = _filtrar_armas(clase, zona_color, nivel)
    if armas_disp:
        e["arma"] = min(armas_disp, key=lambda a: (a.get("rareza", 0), a.get("daño", 0)))["id"]
    e["armaduras"] = {}
    for slot in ["casco", "pechera", "grebas", "botas", "guantes", "capa"]:
        arms = _filtrar_armaduras(clase, zona_color, nivel, slot)
        if arms:
            e["armaduras"][slot] = min(arms, key=lambda a: (a.get("rareza", 0), a.get("defensa", 0)))["id"]

# ═══════════════════════════════════════════════════════════════════════════
# LISTA DE MONSTRUOS
# ═══════════════════════════════════════════════════════════════════════════

def _get_lista_monstruos(e: dict) -> list:
    subtipo = e.get("subtipo", "normales")
    if subtipo.startswith("raid_"):
        dif_map = {"raid_facil": "Facil", "raid_normal": "Normal", "raid_dificil": "Dificil", "raid_legendario": "Legendario"}
        dif = dif_map.get(subtipo, "Normal")
        return [{"nombre": f"Jefe Raid — {dif}", "lore": f"Jefe convocado por el admin en dificultad {dif}."}]
    if subtipo == "vacio_faccion":
        return MONSTRUOS_VACIO
    if subtipo == "vacio_jefe":
        return [AETHERON]
    zona = next((z for z in ZONAS if z["id"] == e.get("zona_id")), None)
    if not zona:
        return [{"nombre": "Monstruo desconocido", "lore": ""}]
    lista = zona.get("monstruos", {}).get(subtipo, [])
    return lista if lista else [{"nombre": f"Criatura de {zona['nombre']}", "lore": ""}]

# ═══════════════════════════════════════════════════════════════════════════
# INICIALIZAR COMBATE
# ═══════════════════════════════════════════════════════════════════════════

def _inicializar_combate(e: dict):
    monstruos = _get_lista_monstruos(e)
    idx       = min(e.get("mon_idx", 0), max(0, len(monstruos) - 1))
    mon       = monstruos[idx]
    nombre    = mon["nombre"]
    hp_j, atk_j, def_j, crit_j = _calc_stats_jugador(e)
    hp_m, atk_m, def_m = _gen_monster_stats(e, e.get("subtipo", "normales"), nombre)
    e.update({
        "hp_j": hp_j, "hp_j_max": hp_j,
        "atk_j": atk_j, "def_j": def_j, "crit_j": crit_j,
        "hp_m": hp_m, "hp_m_max": hp_m,
        "atk_m": atk_m, "def_m": def_m,
        "atk_m_base": atk_m, "def_m_base": def_m, "hp_m_base": hp_m,
        "mon_nombre": nombre,
        "log": ["Combate listo. Pulsa Atacar para comenzar."],
        "ronda": 0,
        "combate_activo": True,
    })

# ═══════════════════════════════════════════════════════════════════════════
# BUILDERS DE TEXTO
# ═══════════════════════════════════════════════════════════════════════════

def _barra(actual: int, maximo: int, largo: int = 10) -> str:
    if maximo <= 0:
        return "░" * largo
    llenos = max(0, min(largo, int((actual / maximo) * largo)))
    return "█" * llenos + "░" * (largo - llenos)

def _resumen_arma(e: dict) -> str:
    if e.get("arma") and e["arma"] in ARMAS:
        a = ARMAS[e["arma"]]
        return f"{a['nombre'][:28]} (dmg:{a.get('daño',0)} crit:{a.get('critico',0)}%)"
    return "Sin arma"

def _resumen_armaduras(e: dict) -> str:
    if not e.get("armaduras"):
        return "Sin armaduras"
    slot_emoji = {"casco": "🪖", "pechera": "🦺", "grebas": "👖", "botas": "👢", "guantes": "🧤", "capa": "🧣"}
    partes = []
    for slot, ak in e["armaduras"].items():
        if ak in ARMADURAS:
            arm = ARMADURAS[ak]
            partes.append(f"{slot_emoji.get(slot, '')}+{arm.get('defensa', 0)}")
    return " ".join(partes) if partes else "Sin armaduras"

def _resumen_pocion(e: dict) -> str:
    pk = e.get("poc_sel")
    if pk and pk in POCIONES:
        p = POCIONES[pk]
        return f"{p['nombre'][:28]} ({p.get('efecto','')[:20]})"
    return "Sin pocion"

def _texto_panel(e: dict) -> str:
    monstruos = _get_lista_monstruos(e)
    total_mon  = len(monstruos)
    idx        = min(e.get("mon_idx", 0), max(0, total_mon - 1))
    mon        = monstruos[idx]
    subtipo_str = SUBTIPO_LABEL.get(e.get("subtipo", "normales"), e.get("subtipo", ""))

    # Zona header
    zona_nombre = ""
    zona_color  = ""
    if e.get("zona_id"):
        zona = next((z for z in ZONAS if z["id"] == e["zona_id"]), None)
        if zona:
            zona_nombre = zona["nombre"]
            zona_color  = zona.get("color", "")
    if e.get("subtipo", "").startswith("raid_"):
        header = "SIMULADOR PvE — Jefe Raid"
    elif e.get("subtipo", "") in ("vacio_faccion", "vacio_jefe"):
        header = "SIMULADOR PvE — Noche del Vacio"
    else:
        ce = COLOR_EMOJI.get(zona_color, "")
        header = f"SIMULADOR PvE — {zona_nombre} ({ce}{zona_color})"

    # Stats jugador
    if e["combate_activo"]:
        hp_j, hp_j_max = e["hp_j"], e["hp_j_max"]
        atk_j, def_j, crit_j = e["atk_j"], e["def_j"], e["crit_j"]
        hp_m, hp_m_max = e["hp_m"], e["hp_m_max"]
        atk_m, def_m   = e["atk_m"], e["def_m"]
        mon_nombre     = e["mon_nombre"]
    else:
        hp_j, atk_j, def_j, crit_j = _calc_stats_jugador(e)
        hp_j_max = hp_j
        hp_m, atk_m, def_m = _gen_monster_stats(e, e.get("subtipo", "normales"), mon["nombre"])
        hp_m_max   = hp_m
        mon_nombre = mon["nombre"]

    lore = mon.get("lore", "")[:90]
    log_lines = e.get("log", [])
    log_txt = "\n".join(f"  {l}" for l in log_lines[-3:]) if log_lines else "  (sin combate)"

    clase_disp = e["clase"].replace("_", " ").title()
    ce         = CLASE_EMOJI.get(e["clase"], "")

    return (
        f"*{header}*\n"
        f"Tipo: {subtipo_str} | #{idx+1}/{total_mon}\n"
        f"---\n"
        f"{ce} *{clase_disp}* Nv.{e['nivel']} Reencar:{e['reenc']}\n"
        f"HP `{_barra(hp_j, hp_j_max)}` {hp_j}/{hp_j_max}\n"
        f"ATK:{atk_j}  DEF:{def_j}  CRIT:{crit_j}%\n"
        f"Arma: {_resumen_arma(e)}\n"
        f"Armad: {_resumen_armaduras(e)}\n"
        f"Pocion: {_resumen_pocion(e)}\n"
        f"---\n"
        f"*{mon_nombre}*\n"
        f"_{lore}_\n"
        f"HP `{_barra(hp_m, hp_m_max)}` {hp_m}/{hp_m_max}\n"
        f"ATK:{atk_m}  DEF:{def_m}\n"
        f"---\n"
        f"Ronda: {e.get('ronda',0)}\n"
        f"{log_txt}"
    )

# ═══════════════════════════════════════════════════════════════════════════
# BUILDERS DE TECLADO
# ═══════════════════════════════════════════════════════════════════════════

def _kb_main():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🌍 Zonas de Campo",  callback_data="sim_t_z"),
         InlineKeyboardButton("🏰 Mazmorras",       callback_data="sim_t_m")],
        [InlineKeyboardButton("🐉 Jefes Raid",      callback_data="sim_t_r"),
         InlineKeyboardButton("👁 Noche del Vacio",  callback_data="sim_t_v")],
        [InlineKeyboardButton("❌ Cerrar",           callback_data="sim_exit")],
    ])

def _kb_colores(tipo_back: str):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔵 Azules",    callback_data="sim_col_az"),
         InlineKeyboardButton("🟡 Amarillas", callback_data="sim_col_am")],
        [InlineKeyboardButton("🔴 Rojas",     callback_data="sim_col_ro"),
         InlineKeyboardButton("⚫ Negras",    callback_data="sim_col_ne")],
        [InlineKeyboardButton("◀️ Atras",      callback_data="sim_main")],
    ])

def _kb_zonas_color(color: str, modo: str):
    """Lista zonas salvajes del color. modo='z' o 'm'."""
    zonas = [z for z in ZONAS if z.get("color") == color and z.get("tipo") == "salvaje"]
    cb_prefix = "sim_z_" if modo == "z" else "sim_mz_"
    ce = COLOR_EMOJI.get(color, "")
    rows = [[InlineKeyboardButton(f"{ce} {z['nombre']}", callback_data=f"{cb_prefix}{z['id']}")] for z in zonas]
    rows.append([InlineKeyboardButton("◀️ Atras", callback_data=f"sim_t_{modo}")])
    return InlineKeyboardMarkup(rows)

def _kb_subtipos_zona():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👻 Normales",    callback_data="sim_sub_n"),
         InlineKeyboardButton("💀 Mini-Jefes",  callback_data="sim_sub_mb")],
        [InlineKeyboardButton("🐉 Jefe Normal", callback_data="sim_sub_jn"),
         InlineKeyboardButton("🔥 Jefe Dificil",callback_data="sim_sub_jd")],
        [InlineKeyboardButton("◀️ Atras",        callback_data="sim_back_zona")],
    ])

def _kb_subtipos_maz():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏰 Mazmorra Normal",  callback_data="sim_sub_mn"),
         InlineKeyboardButton("🔥 Mazmorra Dificil", callback_data="sim_sub_md")],
        [InlineKeyboardButton("◀️ Atras",              callback_data="sim_back_maz")],
    ])

def _kb_raid():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⚪ Facil",     callback_data="sim_sub_rf"),
         InlineKeyboardButton("🔵 Normal",    callback_data="sim_sub_rn")],
        [InlineKeyboardButton("🔴 Dificil",   callback_data="sim_sub_rd"),
         InlineKeyboardButton("🌑 Legendario",callback_data="sim_sub_rl")],
        [InlineKeyboardButton("◀️ Atras",      callback_data="sim_main")],
    ])

def _kb_vacio():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👁 Monstruos de Faccion", callback_data="sim_sub_vf")],
        [InlineKeyboardButton("💀 Aetheron el Devorador", callback_data="sim_sub_vj")],
        [InlineKeyboardButton("◀️ Atras",                  callback_data="sim_main")],
    ])

def _kb_monstruos(e: dict):
    monstruos = _get_lista_monstruos(e)
    rows = []
    for i, mon in enumerate(monstruos):
        marca = "▶" if i == e.get("mon_idx", 0) else "○"
        rows.append([InlineKeyboardButton(f"{marca} {mon['nombre'][:32]}", callback_data=f"sim_mon_{i}")])
    rows.append([InlineKeyboardButton("◀️ Atras", callback_data="sim_back_sub")])
    return InlineKeyboardMarkup(rows)

def _kb_clases():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🛡️ Vanguardista", callback_data="sim_cls_v"),
         InlineKeyboardButton("🗡️ Acechante",    callback_data="sim_cls_a")],
        [InlineKeyboardButton("🔮 Tejehechizos", callback_data="sim_cls_t"),
         InlineKeyboardButton("🏹 Maestro Caza", callback_data="sim_cls_mc")],
        [InlineKeyboardButton("◀️ Atras",         callback_data="sim_back_mon")],
    ])

def _kb_niveles():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Nv.10",  callback_data="sim_niv_10"),
         InlineKeyboardButton("Nv.30",  callback_data="sim_niv_30"),
         InlineKeyboardButton("Nv.50",  callback_data="sim_niv_50")],
        [InlineKeyboardButton("Nv.75",  callback_data="sim_niv_75"),
         InlineKeyboardButton("Nv.100", callback_data="sim_niv_100")],
        [InlineKeyboardButton("◀️ Atras", callback_data="sim_back_cls")],
    ])

def _kb_reencarnaciones():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("0x", callback_data="sim_reenc_0"),
         InlineKeyboardButton("1x", callback_data="sim_reenc_1"),
         InlineKeyboardButton("2x", callback_data="sim_reenc_2"),
         InlineKeyboardButton("3x", callback_data="sim_reenc_3")],
        [InlineKeyboardButton("5x", callback_data="sim_reenc_5"),
         InlineKeyboardButton("7x", callback_data="sim_reenc_7"),
         InlineKeyboardButton("10x",callback_data="sim_reenc_10")],
        [InlineKeyboardButton("◀️ Atras", callback_data="sim_back_niv")],
    ])

def _kb_equipo_preset():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⭐ Mejor equipo de la zona", callback_data="sim_eq_best")],
        [InlineKeyboardButton("💢 Peor equipo de la zona",  callback_data="sim_eq_worst")],
        [InlineKeyboardButton("🚫 Sin equipamiento",         callback_data="sim_eq_none")],
        [InlineKeyboardButton("◀️ Atras",                    callback_data="sim_back_reenc")],
    ])

def _kb_combate(e: dict):
    monstruos = _get_lista_monstruos(e)
    total     = len(monstruos)
    idx       = e.get("mon_idx", 0)
    tiene_poc = bool(e.get("poc_sel"))
    prev_cb   = "sim_prv" if idx > 0 else "sim_noop"
    next_cb   = "sim_nxt" if idx < total - 1 else "sim_noop"
    prev_lbl  = "◀️ Anterior" if idx > 0 else "◀️ —"
    next_lbl  = "Siguiente ▶️" if idx < total - 1 else "— ▶️"
    poc_lbl   = "🧪 Pocion" if tiene_poc else "🧪 Sel.Pocion"
    poc_cb    = "sim_poc" if tiene_poc else "sim_bus_p"
    return InlineKeyboardMarkup([
        # Acciones de combate
        [InlineKeyboardButton("⚔️ Atacar", callback_data="sim_atk"),
         InlineKeyboardButton(poc_lbl,     callback_data=poc_cb),
         InlineKeyboardButton("🏃 Huir",   callback_data="sim_hui")],
        # Ajuste monstruo
        [InlineKeyboardButton("👹↑ATK", callback_data="sim_mx_ap"),
         InlineKeyboardButton("👹↓ATK", callback_data="sim_mx_am"),
         InlineKeyboardButton("👹↑DEF", callback_data="sim_mx_dp"),
         InlineKeyboardButton("👹↓DEF", callback_data="sim_mx_dm")],
        [InlineKeyboardButton("👹↑HP",  callback_data="sim_mx_hp"),
         InlineKeyboardButton("👹↓HP",  callback_data="sim_mx_hm"),
         InlineKeyboardButton("🔄 Reset👹", callback_data="sim_mx_rst")],
        # Ajuste jugador
        [InlineKeyboardButton("👤↑ATK", callback_data="sim_jx_ap"),
         InlineKeyboardButton("👤↓ATK", callback_data="sim_jx_am"),
         InlineKeyboardButton("👤↑DEF", callback_data="sim_jx_dp"),
         InlineKeyboardButton("👤↓DEF", callback_data="sim_jx_dm")],
        [InlineKeyboardButton("👤↑HP",  callback_data="sim_jx_hp"),
         InlineKeyboardButton("👤↓HP",  callback_data="sim_jx_hm"),
         InlineKeyboardButton("🔄 Reset👤", callback_data="sim_jx_rst")],
        # Equipo
        [InlineKeyboardButton("🗡️ Buscar Arma",   callback_data="sim_bus_w"),
         InlineKeyboardButton("🛡️ Buscar Armad.", callback_data="sim_bus_a"),
         InlineKeyboardButton("🧪 Buscar Pocion", callback_data="sim_bus_p")],
        [InlineKeyboardButton("⭐ Mejor equipo", callback_data="sim_eq_best"),
         InlineKeyboardButton("💢 Peor equipo",  callback_data="sim_eq_worst")],
        # Navegacion
        [InlineKeyboardButton(prev_lbl, callback_data=prev_cb),
         InlineKeyboardButton(next_lbl, callback_data=next_cb)],
        # Extra
        [InlineKeyboardButton("📊 Cambiar clase/nivel", callback_data="sim_recfg"),
         InlineKeyboardButton("🔄 Reiniciar",            callback_data="sim_rst")],
        [InlineKeyboardButton("💾 Aplicar al juego", callback_data="sim_aplc"),
         InlineKeyboardButton("❌ Salir",              callback_data="sim_exit")],
    ])

def _kb_aplicar(e: dict):
    hp_m  = e.get("hp_m_max", 0)
    atk_m = e.get("atk_m", 0)
    def_m = e.get("def_m", 0)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"❤️ Aplicar vida monstruo (HP:{hp_m})", callback_data="sim_apl_mv")],
        [InlineKeyboardButton(f"⚔️ Aplicar daño monstruo (ATK:{atk_m})", callback_data="sim_apl_md")],
        [InlineKeyboardButton(f"🛡️ Aplicar defensa monstruo (DEF:{def_m})", callback_data="sim_apl_mdf")],
        [InlineKeyboardButton("◀️ Volver al simulador", callback_data="sim_go")],
    ])

def _kb_resultados_arma(resultados: list):
    rows = []
    for a in resultados[:6]:
        txt = f"{a['nombre'][:26]} (dmg:{a.get('daño',0)} R{a.get('rareza',0)})"
        rows.append([InlineKeyboardButton(txt, callback_data=f"sim_wa_{a['id']}")])
    rows.append([InlineKeyboardButton("🔍 Nueva busqueda", callback_data="sim_bus_w"),
                 InlineKeyboardButton("◀️ Volver",          callback_data="sim_go")])
    return InlineKeyboardMarkup(rows)

def _kb_slot_armadura():
    slots = [("casco","🪖"),("pechera","🦺"),("grebas","👖"),("botas","👢"),("guantes","🧤"),("capa","🧣")]
    rows  = [[InlineKeyboardButton(f"{em} {s.title()}", callback_data=f"sim_arsl_{s}")] for s, em in slots]
    rows.append([InlineKeyboardButton("◀️ Volver", callback_data="sim_go")])
    return InlineKeyboardMarkup(rows)

def _kb_resultados_armadura(resultados: list, slot: str):
    rows = []
    for a in resultados[:6]:
        txt = f"{a['nombre'][:26]} (def:{a.get('defensa',0)} R{a.get('rareza',0)})"
        rows.append([InlineKeyboardButton(txt, callback_data=f"sim_aa_{a['id']}")])
    rows.append([InlineKeyboardButton("🔍 Nueva busqueda", callback_data=f"sim_arsl_{slot}"),
                 InlineKeyboardButton("◀️ Volver",          callback_data="sim_go")])
    return InlineKeyboardMarkup(rows)

def _kb_resultados_pocion(resultados: list):
    rows = []
    for p in resultados[:6]:
        efecto = p.get("efecto", "")[:18]
        txt    = f"{p['nombre'][:26]} ({efecto})"
        rows.append([InlineKeyboardButton(txt, callback_data=f"sim_pa_{p['id']}")])
    rows.append([InlineKeyboardButton("🔍 Nueva busqueda", callback_data="sim_bus_p"),
                 InlineKeyboardButton("◀️ Volver",          callback_data="sim_go")])
    return InlineKeyboardMarkup(rows)

# ═══════════════════════════════════════════════════════════════════════════
# HELPERS DE NAVEGACION "ATRAS"
# ═══════════════════════════════════════════════════════════════════════════

async def _mostrar_subtipos(q, e: dict):
    if e.get("tipo") == "m":
        zona = next((z for z in ZONAS if z["id"] == e.get("zona_id")), None)
        nom  = zona["nombre"] if zona else "?"
        await q.edit_message_text(f"🏰 *Mazmorra — {nom}*\nElige la dificultad:",
                                  parse_mode="Markdown", reply_markup=_kb_subtipos_maz())
    else:
        zona = next((z for z in ZONAS if z["id"] == e.get("zona_id")), None)
        nom  = zona["nombre"] if zona else "?"
        ce   = COLOR_EMOJI.get(zona.get("color", "") if zona else "", "")
        await q.edit_message_text(f"{ce} *{nom}*\nElige el tipo de enemigo:",
                                  parse_mode="Markdown", reply_markup=_kb_subtipos_zona())

async def _mostrar_zonas_color(q, e: dict, modo: str):
    color = e.get("color", "azul")
    ce    = COLOR_EMOJI.get(color, "")
    txt   = "Mazmorras" if modo == "m" else "Zonas"
    await q.edit_message_text(f"{ce} *{txt} {color.title()}*\nElige la zona:",
                               parse_mode="Markdown", reply_markup=_kb_zonas_color(color, modo))

# ═══════════════════════════════════════════════════════════════════════════
# COMANDO /simulador_pve
# ═══════════════════════════════════════════════════════════════════════════

async def cmd_simulador_pve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from superadmin import _es_superadmin
    uid = update.effective_user.id
    if not _es_superadmin(uid):
        await update.message.reply_text("❌ Solo para superadmin.")
        return
    _sim[uid] = _estado_inicial()
    await update.message.reply_text(
        "🔬 *SIMULADOR PvE — Aethelgard*\n\nElige el tipo de contenido a simular:",
        parse_mode="Markdown",
        reply_markup=_kb_main(),
    )

# ═══════════════════════════════════════════════════════════════════════════
# CALLBACK HANDLER PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════════

SUBTIPO_MAP = {
    "sim_sub_n":  "normales",
    "sim_sub_mb": "mini_boss",
    "sim_sub_jn": "jefes_zona_normal",
    "sim_sub_jd": "jefes_zona_dificil",
    "sim_sub_mn": "mazmorras_normal",
    "sim_sub_md": "mazmorras_dificil",
    "sim_sub_rf": "raid_facil",
    "sim_sub_rn": "raid_normal",
    "sim_sub_rd": "raid_dificil",
    "sim_sub_rl": "raid_legendario",
    "sim_sub_vf": "vacio_faccion",
    "sim_sub_vj": "vacio_jefe",
}
CLASE_MAP = {
    "sim_cls_v":  "vanguardista",
    "sim_cls_a":  "acechante",
    "sim_cls_t":  "tejehechizos",
    "sim_cls_mc": "maestro_caza",
}

async def cb_simulador(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from superadmin import _es_superadmin
    q   = update.callback_query
    await q.answer()
    uid = q.from_user.id
    if not _es_superadmin(uid):
        return
    data = q.data
    e    = _estado(uid)

    # ── Menú principal ─────────────────────────────────────────────────────
    if data == "sim_main":
        e["paso"] = "menu"
        await q.edit_message_text("🔬 *SIMULADOR PvE — Aethelgard*\n\nElige el tipo de contenido:",
                                  parse_mode="Markdown", reply_markup=_kb_main())
        return

    # ── Tipos ───────────────────────────────────────────────────────────────
    if data == "sim_t_z":
        e["tipo"] = "z"
        await q.edit_message_text("🌍 *Zonas de Campo*\nElige el color de zona:",
                                  parse_mode="Markdown", reply_markup=_kb_colores("z"))
        return
    if data == "sim_t_m":
        e["tipo"] = "m"
        await q.edit_message_text("🏰 *Mazmorras*\nElige el color de zona:",
                                  parse_mode="Markdown", reply_markup=_kb_colores("m"))
        return
    if data == "sim_t_r":
        e["tipo"] = "r"
        e["zona_id"] = None
        await q.edit_message_text("🐉 *Jefes Raid*\nElige la dificultad:",
                                  parse_mode="Markdown", reply_markup=_kb_raid())
        return
    if data == "sim_t_v":
        e["tipo"] = "v"
        e["zona_id"] = None
        await q.edit_message_text("👁 *Noche del Vacio*\nElige el tipo de enemigo:",
                                  parse_mode="Markdown", reply_markup=_kb_vacio())
        return

    # ── Colores ─────────────────────────────────────────────────────────────
    if data.startswith("sim_col_"):
        cod   = data[8:]
        cmap  = {"az": "azul", "am": "amarilla", "ro": "roja", "ne": "negra"}
        color = cmap.get(cod, "azul")
        e["color"] = color
        modo  = e.get("tipo", "z")
        ce    = COLOR_EMOJI.get(color, "")
        tipo_txt = "Mazmorras" if modo == "m" else "Zonas"
        await q.edit_message_text(f"{ce} *{tipo_txt} {color.title()}*\nElige la zona:",
                                  parse_mode="Markdown", reply_markup=_kb_zonas_color(color, modo))
        return

    # ── Selección zona salvaje (campo) ──────────────────────────────────────
    if data.startswith("sim_z_"):
        zona_id = int(data[6:])
        e["zona_id"] = zona_id
        e["mon_idx"] = 0
        zona = next((z for z in ZONAS if z["id"] == zona_id), None)
        nom  = zona["nombre"] if zona else "?"
        ce   = COLOR_EMOJI.get(zona.get("color", "") if zona else "", "")
        await q.edit_message_text(f"{ce} *{nom}*\nElige el tipo de enemigo:",
                                  parse_mode="Markdown", reply_markup=_kb_subtipos_zona())
        return

    # ── Selección zona (mazmorra) ───────────────────────────────────────────
    if data.startswith("sim_mz_"):
        zona_id = int(data[7:])
        e["zona_id"] = zona_id
        e["mon_idx"] = 0
        zona = next((z for z in ZONAS if z["id"] == zona_id), None)
        nom  = zona["nombre"] if zona else "?"
        await q.edit_message_text(f"🏰 *Mazmorra — {nom}*\nElige la dificultad:",
                                  parse_mode="Markdown", reply_markup=_kb_subtipos_maz())
        return

    # ── Subtipos ─────────────────────────────────────────────────────────────
    if data in SUBTIPO_MAP:
        e["subtipo"] = SUBTIPO_MAP[data]
        e["mon_idx"] = 0
        monstruos = _get_lista_monstruos(e)
        if not monstruos:
            await q.edit_message_text("⚠️ No hay monstruos para este subtipo.",
                                      reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Atras", callback_data="sim_main")]]))
            return
        await q.edit_message_text(f"👹 *Selecciona el monstruo* ({len(monstruos)} disponibles):",
                                  parse_mode="Markdown", reply_markup=_kb_monstruos(e))
        return

    # ── Selección monstruo ───────────────────────────────────────────────────
    if data.startswith("sim_mon_"):
        e["mon_idx"] = int(data[8:])
        await q.edit_message_text("👤 *Clase del jugador simulado:*",
                                  parse_mode="Markdown", reply_markup=_kb_clases())
        return

    # ── Clase ────────────────────────────────────────────────────────────────
    if data in CLASE_MAP:
        e["clase"] = CLASE_MAP[data]
        await q.edit_message_text(f"📊 *Clase: {e['clase'].replace('_',' ').title()}*\nElige el nivel:",
                                  parse_mode="Markdown", reply_markup=_kb_niveles())
        return

    # ── Nivel ────────────────────────────────────────────────────────────────
    if data.startswith("sim_niv_"):
        e["nivel"] = int(data[8:])
        await q.edit_message_text(f"🔄 *Nivel {e['nivel']}*\nElige reencarnaciones:",
                                  parse_mode="Markdown", reply_markup=_kb_reencarnaciones())
        return

    # ── Reencarnaciones ──────────────────────────────────────────────────────
    if data.startswith("sim_reenc_"):
        e["reenc"] = int(data[10:])
        await q.edit_message_text("⚔️ *Equipamiento inicial*\nElige un preset de equipo:",
                                  parse_mode="Markdown", reply_markup=_kb_equipo_preset())
        return

    # ── Presets de equipo ────────────────────────────────────────────────────
    if data == "sim_eq_best":
        _equipar_mejor(e)
        _inicializar_combate(e)
        await q.edit_message_text(_texto_panel(e), parse_mode="Markdown", reply_markup=_kb_combate(e))
        return
    if data == "sim_eq_worst":
        _equipar_peor(e)
        _inicializar_combate(e)
        await q.edit_message_text(_texto_panel(e), parse_mode="Markdown", reply_markup=_kb_combate(e))
        return
    if data == "sim_eq_none":
        e["arma"] = None
        e["armaduras"] = {}
        _inicializar_combate(e)
        await q.edit_message_text(_texto_panel(e), parse_mode="Markdown", reply_markup=_kb_combate(e))
        return

    # ── Panel de combate (volver) ─────────────────────────────────────────────
    if data == "sim_go":
        e["busqueda"] = None
        if not e.get("combate_activo"):
            _inicializar_combate(e)
        await q.edit_message_text(_texto_panel(e), parse_mode="Markdown", reply_markup=_kb_combate(e))
        return

    # ── ATACAR ────────────────────────────────────────────────────────────────
    if data == "sim_atk":
        if not e.get("combate_activo"):
            _inicializar_combate(e)
        e["ronda"] += 1
        log = e.setdefault("log", [])

        # Jugador ataca al monstruo
        dmg_j, crit_j = _calc_daño(e["atk_j"], e["def_m"], e["crit_j"])
        e["hp_m"] = max(0, e["hp_m"] - dmg_j)
        ctxt = " CRITICO!" if crit_j else ""
        log.append(f"[{e['ronda']}] Atacas: -{dmg_j}{ctxt} | Monstruo HP:{e['hp_m']}/{e['hp_m_max']}")

        if e["hp_m"] <= 0:
            log.append(f"Victoria! {e['mon_nombre']} derrotado.")
            e["combate_activo"] = False
            e["log"] = log[-4:]
            await q.edit_message_text(_texto_panel(e), parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Reiniciar combate", callback_data="sim_rst"),
                     InlineKeyboardButton("▶️ Sig. monstruo",     callback_data="sim_nxt")],
                    [InlineKeyboardButton("◀️ Cambiar config",     callback_data="sim_recfg"),
                     InlineKeyboardButton("❌ Salir",               callback_data="sim_exit")],
                ]))
            return

        # Monstruo contraataca
        dmg_m, crit_m = _calc_daño(e["atk_m"], e["def_j"])
        e["hp_j"] = max(0, e["hp_j"] - dmg_m)
        ctxtm = " CRITICO!" if crit_m else ""
        log.append(f"      Monstruo: -{dmg_m}{ctxtm} | Tu HP:{e['hp_j']}/{e['hp_j_max']}")

        if e["hp_j"] <= 0:
            log.append(f"Derrota! Tu personaje murio.")
            e["combate_activo"] = False
            e["log"] = log[-4:]
            await q.edit_message_text(_texto_panel(e), parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Reiniciar combate", callback_data="sim_rst"),
                     InlineKeyboardButton("◀️ Menu principal",    callback_data="sim_main")],
                    [InlineKeyboardButton("❌ Salir",               callback_data="sim_exit")],
                ]))
            return

        e["log"] = log[-3:]
        await q.edit_message_text(_texto_panel(e), parse_mode="Markdown", reply_markup=_kb_combate(e))
        return

    # ── POCION ────────────────────────────────────────────────────────────────
    if data == "sim_poc":
        pk = e.get("poc_sel")
        if pk and pk in POCIONES:
            poc   = POCIONES[pk]
            efect = poc.get("efecto", "0")
            try:
                cura = int("".join(c for c in efect if c.isdigit()))
            except Exception:
                cura = 30
            e["hp_j"] = min(e["hp_j_max"], e["hp_j"] + cura)
            e.setdefault("log", []).append(f"Pocion: +{cura} HP | Tu HP:{e['hp_j']}/{e['hp_j_max']}")
        else:
            e.setdefault("log", []).append("Sin pocion seleccionada.")
        e["log"] = e["log"][-3:]
        await q.edit_message_text(_texto_panel(e), parse_mode="Markdown", reply_markup=_kb_combate(e))
        return

    # ── HUIR ──────────────────────────────────────────────────────────────────
    if data == "sim_hui":
        e.setdefault("log", []).append("Huiste del combate.")
        e["combate_activo"] = False
        e["log"] = e["log"][-3:]
        await q.edit_message_text(_texto_panel(e), parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Reiniciar combate", callback_data="sim_rst"),
                 InlineKeyboardButton("◀️ Menu principal",    callback_data="sim_main")],
                [InlineKeyboardButton("❌ Salir",               callback_data="sim_exit")],
            ]))
        return

    # ── REINICIAR COMBATE ─────────────────────────────────────────────────────
    if data == "sim_rst":
        _inicializar_combate(e)
        await q.edit_message_text(_texto_panel(e), parse_mode="Markdown", reply_markup=_kb_combate(e))
        return

    # ── AJUSTES MONSTRUO ──────────────────────────────────────────────────────
    if data == "sim_mx_ap":
        e["atk_m"] = e.get("atk_m", 10) + 10
    elif data == "sim_mx_am":
        e["atk_m"] = max(1, e.get("atk_m", 10) - 10)
    elif data == "sim_mx_dp":
        e["def_m"] = e.get("def_m", 5) + 5
    elif data == "sim_mx_dm":
        e["def_m"] = max(0, e.get("def_m", 5) - 5)
    elif data == "sim_mx_hp":
        inc = 50
        e["hp_m"]     = e.get("hp_m", 100) + inc
        e["hp_m_max"] = e.get("hp_m_max", 100) + inc
    elif data == "sim_mx_hm":
        e["hp_m"]     = max(1, e.get("hp_m", 100) - 50)
        e["hp_m_max"] = max(1, e.get("hp_m_max", 100) - 50)
    elif data == "sim_mx_rst":
        e["atk_m"]    = e.get("atk_m_base", e.get("atk_m", 10))
        e["def_m"]    = e.get("def_m_base", e.get("def_m", 5))
        e["hp_m"]     = e.get("hp_m_base", e.get("hp_m_max", 100))
        e["hp_m_max"] = e.get("hp_m_base", e.get("hp_m_max", 100))
    # ── AJUSTES JUGADOR ───────────────────────────────────────────────────────
    elif data == "sim_jx_ap":
        e["atk_j"] = e.get("atk_j", 10) + 10
    elif data == "sim_jx_am":
        e["atk_j"] = max(1, e.get("atk_j", 10) - 10)
    elif data == "sim_jx_dp":
        e["def_j"] = e.get("def_j", 5) + 5
    elif data == "sim_jx_dm":
        e["def_j"] = max(0, e.get("def_j", 5) - 5)
    elif data == "sim_jx_hp":
        inc = 50
        e["hp_j"]     = e.get("hp_j", 100) + inc
        e["hp_j_max"] = e.get("hp_j_max", 100) + inc
    elif data == "sim_jx_hm":
        e["hp_j"]     = max(1, e.get("hp_j", 100) - 50)
        e["hp_j_max"] = max(1, e.get("hp_j_max", 100) - 50)
    elif data == "sim_jx_rst":
        hp_j, atk_j, def_j, crit_j = _calc_stats_jugador(e)
        e.update({"atk_j": atk_j, "def_j": def_j, "hp_j": hp_j, "hp_j_max": hp_j, "crit_j": crit_j})

    if data.startswith("sim_mx_") or data.startswith("sim_jx_"):
        if not e.get("combate_activo"):
            e["combate_activo"] = True
        await q.edit_message_text(_texto_panel(e), parse_mode="Markdown", reply_markup=_kb_combate(e))
        return

    # ── SIGUIENTE / ANTERIOR MONSTRUO ─────────────────────────────────────────
    if data == "sim_nxt":
        monstruos = _get_lista_monstruos(e)
        if e.get("mon_idx", 0) < len(monstruos) - 1:
            e["mon_idx"] = e.get("mon_idx", 0) + 1
        _inicializar_combate(e)
        await q.edit_message_text(_texto_panel(e), parse_mode="Markdown", reply_markup=_kb_combate(e))
        return
    if data == "sim_prv":
        if e.get("mon_idx", 0) > 0:
            e["mon_idx"] = e.get("mon_idx", 0) - 1
        _inicializar_combate(e)
        await q.edit_message_text(_texto_panel(e), parse_mode="Markdown", reply_markup=_kb_combate(e))
        return

    # ── BUSCAR ARMA ───────────────────────────────────────────────────────────
    if data == "sim_bus_w":
        e["busqueda"] = "arma"
        await q.edit_message_text(
            "🔍 *Buscar Arma*\nEscribe el nombre (o parte) del arma:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Cancelar", callback_data="sim_go")]]),
        )
        return

    # ── BUSCAR ARMADURA ───────────────────────────────────────────────────────
    if data == "sim_bus_a":
        e["busqueda"] = "armadura_slot"
        await q.edit_message_text("🛡️ *Buscar Armadura*\nElige el slot:",
                                  parse_mode="Markdown", reply_markup=_kb_slot_armadura())
        return

    if data.startswith("sim_arsl_"):
        slot = data[9:]
        e["busqueda"]  = "armadura"
        e["busq_slot"] = slot
        await q.edit_message_text(
            f"🔍 *Buscar Armadura — {slot.title()}*\nEscribe el nombre (o parte):",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Cancelar", callback_data="sim_go")]]),
        )
        return

    # ── BUSCAR POCION ─────────────────────────────────────────────────────────
    if data == "sim_bus_p":
        e["busqueda"] = "pocion"
        await q.edit_message_text(
            "🧪 *Buscar Pocion*\nEscribe el nombre (o parte):",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Cancelar", callback_data="sim_go")]]),
        )
        return

    # ── EQUIPAR ARMA (resultado) ───────────────────────────────────────────────
    if data.startswith("sim_wa_"):
        ak = data[7:]
        if ak in ARMAS:
            e["arma"] = ak
            e.setdefault("log", []).append(f"Arma equipada: {ARMAS[ak]['nombre'][:22]}")
            e["log"] = e["log"][-3:]
        _inicializar_combate(e)
        await q.edit_message_text(_texto_panel(e), parse_mode="Markdown", reply_markup=_kb_combate(e))
        return

    # ── EQUIPAR ARMADURA (resultado) ──────────────────────────────────────────
    if data.startswith("sim_aa_"):
        ak = data[7:]
        if ak in ARMADURAS:
            arm  = ARMADURAS[ak]
            slot = arm.get("tipo", "casco")
            e.setdefault("armaduras", {})[slot] = ak
            e.setdefault("log", []).append(f"Armadura equipada: {arm['nombre'][:20]}")
            e["log"] = e["log"][-3:]
        _inicializar_combate(e)
        await q.edit_message_text(_texto_panel(e), parse_mode="Markdown", reply_markup=_kb_combate(e))
        return

    # ── EQUIPAR POCION (resultado) ────────────────────────────────────────────
    if data.startswith("sim_pa_"):
        pk = data[7:]
        if pk in POCIONES:
            e["poc_sel"] = pk
            e.setdefault("log", []).append(f"Pocion seleccionada: {POCIONES[pk]['nombre'][:20]}")
            e["log"] = e["log"][-3:]
        if not e.get("combate_activo"):
            _inicializar_combate(e)
        await q.edit_message_text(_texto_panel(e), parse_mode="Markdown", reply_markup=_kb_combate(e))
        return

    # ── RECONFIGURAR CLASE/NIVEL ──────────────────────────────────────────────
    if data == "sim_recfg":
        e["combate_activo"] = False
        await q.edit_message_text("👤 *Cambiar clase del jugador simulado:*",
                                  parse_mode="Markdown", reply_markup=_kb_clases())
        return

    # ── APLICAR AL JUEGO ──────────────────────────────────────────────────────
    if data == "sim_aplc":
        await q.edit_message_text(
            "*Aplicar al juego*\n\n"
            "Esto ajusta los multiplicadores globales de monstruos "
            "(bg\\_m\\_vida, bg\\_m\\_daño, bg\\_m\\_def) en la config del juego, "
            "basandose en los stats actuales del simulador.\n\n"
            f"Stats actuales del monstruo:\n"
            f"HP: {e.get('hp_m_max',0)}  ATK: {e.get('atk_m',0)}  DEF: {e.get('def_m',0)}",
            parse_mode="Markdown",
            reply_markup=_kb_aplicar(e),
        )
        return

    if data.startswith("sim_apl_"):
        accion = data[8:]
        msg_ok = ""
        try:
            poder_jug = _poder_jugador_sim(e)
            mult      = MULT_SUBTIPO.get(e.get("subtipo", "normales"), 1.0)
            pm        = poder_jug * mult
            if accion == "mv":
                hp_base = max(1, int(pm ** 0.5 * 20))
                nuevo   = round(e.get("hp_m_max", hp_base) / hp_base, 3)
                db_helper.establecer_config("bg_m_vida", str(nuevo))
                msg_ok = f"bg_m_vida = {nuevo}"
            elif accion == "md":
                atk_base = max(1, int(pm ** 0.5 * 4))
                nuevo    = round(e.get("atk_m", atk_base) / atk_base, 3)
                db_helper.establecer_config("bg_m_daño", str(nuevo))
                msg_ok = f"bg_m_daño = {nuevo}"
            elif accion == "mdf":
                def_base = max(1, int(pm ** 0.5 * 2))
                nuevo    = round(e.get("def_m", def_base) / def_base, 3)
                db_helper.establecer_config("bg_m_def", str(nuevo))
                msg_ok = f"bg_m_def = {nuevo}"
        except Exception as ex:
            msg_ok = f"Error: {ex}"
        await q.answer(f"✅ Aplicado: {msg_ok}", show_alert=True)
        return

    # ── NAVEGACION "ATRAS" ────────────────────────────────────────────────────
    if data == "sim_back_zona":
        # Desde subtipos zona → volver a lista de zonas del color
        await _mostrar_zonas_color(q, e, "z")
        return

    if data == "sim_back_maz":
        await _mostrar_zonas_color(q, e, "m")
        return

    if data == "sim_back_sub":
        # Desde lista de monstruos → volver a subtipos
        await _mostrar_subtipos(q, e)
        return

    if data == "sim_back_mon":
        monstruos = _get_lista_monstruos(e)
        await q.edit_message_text(f"👹 *Selecciona el monstruo* ({len(monstruos)} disponibles):",
                                  parse_mode="Markdown", reply_markup=_kb_monstruos(e))
        return

    if data == "sim_back_cls":
        await q.edit_message_text("👤 *Clase del jugador simulado:*",
                                  parse_mode="Markdown", reply_markup=_kb_clases())
        return

    if data == "sim_back_niv":
        await q.edit_message_text(f"📊 Clase: *{e['clase'].replace('_',' ').title()}*\nElige el nivel:",
                                  parse_mode="Markdown", reply_markup=_kb_niveles())
        return

    if data == "sim_back_reenc":
        await q.edit_message_text(f"🔄 Nivel *{e['nivel']}*\nElige reencarnaciones:",
                                  parse_mode="Markdown", reply_markup=_kb_reencarnaciones())
        return

    # ── SALIR ─────────────────────────────────────────────────────────────────
    if data == "sim_exit":
        _sim.pop(uid, None)
        await q.edit_message_text("🔬 Simulador PvE cerrado.")
        return

    # ── NOOP ──────────────────────────────────────────────────────────────────
    if data == "sim_noop":
        return

# ═══════════════════════════════════════════════════════════════════════════
# MESSAGE HANDLER — búsqueda por texto
# ═══════════════════════════════════════════════════════════════════════════

async def msg_busqueda_sim(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from superadmin import _es_superadmin
    uid = update.effective_user.id
    if not _es_superadmin(uid):
        return
    if uid not in _sim:
        return
    e    = _sim[uid]
    modo = e.get("busqueda")
    if not modo or modo == "armadura_slot":
        return
    texto = (update.message.text or "").strip().lower()
    if not texto:
        return

    if modo == "arma":
        resultados = sorted(
            [{**a, "id": k} for k, a in ARMAS.items() if texto in a.get("nombre", "").lower()],
            key=lambda a: (-a.get("rareza", 0), -a.get("daño", 0)),
        )
        e["busqueda"] = None
        if not resultados:
            await update.message.reply_text(
                f"❌ Sin resultados para '{texto}'.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔍 Buscar de nuevo", callback_data="sim_bus_w"),
                    InlineKeyboardButton("◀️ Volver",           callback_data="sim_go"),
                ]]),
            )
        else:
            await update.message.reply_text(
                f"🗡️ *Resultados arma '{texto[:20]}':*",
                parse_mode="Markdown",
                reply_markup=_kb_resultados_arma(resultados),
            )

    elif modo == "armadura":
        slot = e.get("busq_slot", "casco")
        resultados = sorted(
            [{**a, "id": k} for k, a in ARMADURAS.items()
             if texto in a.get("nombre", "").lower() and a.get("tipo") == slot],
            key=lambda a: (-a.get("rareza", 0), -a.get("defensa", 0)),
        )
        e["busqueda"] = None
        if not resultados:
            await update.message.reply_text(
                f"❌ Sin resultados de '{slot}' para '{texto}'.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔍 Buscar de nuevo", callback_data=f"sim_arsl_{slot}"),
                    InlineKeyboardButton("◀️ Volver",           callback_data="sim_go"),
                ]]),
            )
        else:
            await update.message.reply_text(
                f"🛡️ *Resultados '{slot}' para '{texto[:20]}':*",
                parse_mode="Markdown",
                reply_markup=_kb_resultados_armadura(resultados, slot),
            )

    elif modo == "pocion":
        todos = [{**p, "id": k} for k, p in POCIONES.items() if texto in p.get("nombre", "").lower()]
        # Preferir pociones de vida/curativas
        vida_first = sorted(
            [p for p in todos if p.get("subtipo") in ("vida", "curativa", "salud", "curar")],
            key=lambda p: -p.get("rareza", 0),
        )
        resto = sorted(
            [p for p in todos if p.get("subtipo") not in ("vida", "curativa", "salud", "curar")],
            key=lambda p: -p.get("rareza", 0),
        )
        resultados = vida_first + resto
        e["busqueda"] = None
        if not resultados:
            await update.message.reply_text(
                f"❌ Sin resultados para '{texto}'.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔍 Buscar de nuevo", callback_data="sim_bus_p"),
                    InlineKeyboardButton("◀️ Volver",           callback_data="sim_go"),
                ]]),
            )
        else:
            await update.message.reply_text(
                f"🧪 *Resultados pocion '{texto[:20]}':*",
                parse_mode="Markdown",
                reply_markup=_kb_resultados_pocion(resultados),
            )

# ═══════════════════════════════════════════════════════════════════════════
# REGISTRO DE HANDLERS
# ═══════════════════════════════════════════════════════════════════════════

def registrar_handlers_simulador(app):
    app.add_handler(CommandHandler("simulador_pve", cmd_simulador_pve))
    app.add_handler(CallbackQueryHandler(cb_simulador, pattern="^sim_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, msg_busqueda_sim), group=20)

# panel_admin.py — Panel visual de administración (solo superadmin)
# Comando: /sa_panel
# Navega por todos los objetos del juego con paginación de 5 por página.

import os
import glob
import importlib.util
import sys
from typing import Dict, List, Tuple, Any, Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    CallbackQueryHandler, CommandHandler, ConversationHandler,
    MessageHandler, ContextTypes, filters,
)
import sqlite3
import html as _html

SUPERADMIN_ID = int(os.environ.get("SUPERADMIN_ID", 0))
PAGE_SIZE = 5

def _e(s) -> str:
    """HTML-escape dinámico seguro."""
    return _html.escape(str(s) if s is not None else "")

def _esc_md(s: str) -> str:
    return str(s).replace("_", "\\_").replace("*", "\\*").replace("`", "\\`").replace("[", "\\[")

# ══════════════════════════════════════════════════════════════
# CONSTANTES
# ══════════════════════════════════════════════════════════════

ZONA_EMOJI = {"azul": "🔵", "amarilla": "🟡", "roja": "🔴", "negra": "⚫"}
RAREZA_EMOJI = {1: "⬜", 2: "🟩", 3: "🟦", 4: "🟪", 5: "🟧", 6: "🔴"}
RAREZA_NOMBRE = {1: "Común", 2: "Poco común", 3: "Raro", 4: "Épico", 5: "Legendario", 6: "Único"}

SECCIONES = {
    "arm": ("⚔️", "Armas"),
    "ard": ("🛡️", "Armaduras"),
    "poc": ("🧪", "Pociones"),
    "mat": ("🪨", "Materiales"),
    "mnt": ("🐎", "Monturas"),
    "mon": ("👹", "Monstruos"),
}

FILTROS_SECCION: Dict[str, List[Tuple[str, str]]] = {
    "arm": [("z", "🗺️ Por zona"), ("t", "🗡️ Por tipo"), ("c", "👤 Por clase"), ("o", "📦 Por origen")],
    "ard": [("z", "🗺️ Por zona"), ("t", "🎽 Por tipo"), ("c", "👤 Por clase"), ("o", "📦 Por origen")],
    "poc": [("z", "🗺️ Por zona"), ("s", "🧴 Por subtipo"), ("q", "⭐ Por calidad")],
    "mat": [("z", "🗺️ Por zona"), ("t", "💎 Por tipo"), ("q", "⭐ Por calidad")],
    "mnt": [("z", "🗺️ Por zona"), ("s", "🦄 Por subtipo")],
    "mon": [("z", "🗺️ Por zona"), ("t", "⚔️ Por tipo")],
}

FIELD_MAP = {
    "z": "zona", "t": "tipo", "c": "clase_requerida",
    "o": "origen", "s": "subtipo", "q": "calidad",
}

CLASE_NOMBRES = {
    None: "Libre", "None": "Libre",
    "vanguardista": "Vanguardista", "acechante": "Acechante",
    "tejehechizos": "Tejehechizos", "maestro_caza": "Maestro de Caza",
}

ORIGEN_NOMBRES = {
    "mazmorra_normal": "Mazmorra Normal", "mazmorra_dificil": "Mazmorra Difícil",
    "tienda_oro": "Tienda (🪙)", "tienda_eternium": "Tienda (💎)",
    "tienda_creditos": "Tienda (✨)", "crafteo": "Crafteo",
    "evento": "Evento", "jefe_zona": "Jefe de Zona",
    "mini_boss": "Mini Boss", "unica": "Única",
}

EDIT_CMD = {
    "arm": "/sa_arma",
    "ard": "/sa_armadura",
    "poc": "/sa_precio",
    "mat": None,
    "mnt": "/sa_precio",
    "mon": "/editar_monstruo",
}

DB_PATH = "aethelgard.db"
PANEL_EDIT_VALOR = 9001  # estado ConversationHandler

# Campos editables por sección, agrupados por categoría
CAMPOS_EDICION: Dict[str, Dict[str, List[str]]] = {
    "arm": {
        "📊 Stats":    ["daño", "critico", "velocidad", "peso", "vida_extra", "defensa_extra"],
        "🏷 Meta":     ["nombre", "tipo", "zona", "clase_requerida", "origen", "nivel_requerido", "rareza"],
        "💰 Precios":  ["precio_oro", "precio_eternium", "precio_creditos", "precio_venta_oro", "precio_venta_eternium"],
        "⚡ Especial": ["habilidad_activa", "habilidad_pasiva", "unica", "stock_global", "descripcion"],
    },
    "ard": {
        "📊 Stats":    ["defensa", "resistencia_critico", "velocidad_movimiento", "peso", "vida_extra", "defensa_extra"],
        "🏷 Meta":     ["nombre", "tipo", "zona", "clase_requerida", "origen", "nivel_requerido", "rareza"],
        "💰 Precios":  ["precio_oro", "precio_eternium", "precio_creditos", "precio_venta_oro", "precio_venta_eternium"],
        "⚡ Especial": ["habilidad_activa", "habilidad_pasiva", "unica", "stock_global", "descripcion"],
    },
    "poc": {
        "🏷 Meta":    ["nombre", "subtipo", "zona", "calidad", "nivel_requerido", "rareza", "origen"],
        "✨ Efecto":  ["efecto", "descripcion"],
        "💰 Precios": ["precio_oro", "precio_eternium", "precio_creditos", "precio_venta_oro", "precio_venta_eternium"],
        "📦 Stock":   ["stock_global"],
    },
    "mat": {
        "🏷 Meta":    ["nombre", "tipo", "zona", "calidad", "nivel_requerido", "rareza", "origen", "valor_crafteo"],
        "💰 Precios": ["precio_venta_oro", "precio_venta_eternium", "precio_creditos"],
        "📦 Stock":   ["stock_global"],
    },
    "mnt": {
        "📊 Stats":   ["velocidad", "carga", "sigilo", "defensa", "ataque"],
        "🏷 Meta":    ["nombre", "subtipo", "zona", "calidad", "nivel_requerido", "rareza"],
        "✨ Efecto":  ["efecto", "descripcion"],
        "💰 Precios": ["precio_oro", "precio_eternium", "precio_creditos", "precio_venta_oro", "precio_venta_eternium"],
    },
    "mon": {
        "📊 Stats":  ["vida_max", "daño", "defensa", "xp", "oro"],
        "🏷 Meta":   ["nombre", "tipo", "zona", "nivel"],
    },
}

# ══════════════════════════════════════════════════════════════
# CARGA LAZY DE CATÁLOGOS
# ══════════════════════════════════════════════════════════════

_CAT: Dict[str, List[Tuple[str, Dict[str, Any]]]] = {}


def _base() -> str:
    return os.path.dirname(os.path.abspath(__file__))


def _importar_archivo(ruta: str):
    nombre = os.path.basename(ruta).replace(".py", "")
    spec = importlib.util.spec_from_file_location(nombre, ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _cargar_seccion(sec: str):
    base = _base()
    if sec == "arm":
        from armas import ARMAS
        _CAT["arm"] = sorted(
            ARMAS.items(),
            key=lambda x: (x[1].get("zona", ""), x[1].get("nombre", ""))
        )
    elif sec == "ard":
        from armaduras import ARMADURAS
        _CAT["ard"] = sorted(
            ARMADURAS.items(),
            key=lambda x: (x[1].get("zona", ""), x[1].get("tipo", ""), x[1].get("nombre", ""))
        )
    elif sec == "poc":
        from pociones import POCIONES
        _CAT["poc"] = sorted(
            POCIONES.items(),
            key=lambda x: (x[1].get("zona", ""), x[1].get("nombre", ""))
        )
    elif sec == "mat":
        from materiales import MATERIALES
        _CAT["mat"] = sorted(
            MATERIALES.items(),
            key=lambda x: (x[1].get("zona", ""), x[1].get("tipo", ""), x[1].get("nombre", ""))
        )
    elif sec == "mnt":
        from monturas import MONTURAS
        _CAT["mnt"] = sorted(
            MONTURAS.items(),
            key=lambda x: (x[1].get("zona", ""), x[1].get("nombre", ""))
        )
    elif sec == "mon":
        _CAT["mon"] = _cargar_monstruos(base)


def _cargar_monstruos(base: str) -> List[Tuple[str, Dict[str, Any]]]:
    result: List[Tuple[str, Dict[str, Any]]] = []
    zonas = sorted({
        f.split("zona_")[1].split("_")[0].split(".")[0]
        for f in glob.glob(os.path.join(base, "monstruos_*zona_*.py"))
    }, key=lambda z: int(z) if z.isdigit() else 99)

    for zona in zonas:
        # Normales de campo
        arch = os.path.join(base, f"monstruos_normales_zona_{zona}.py")
        if os.path.exists(arch):
            mod = _importar_archivo(arch)
            d = getattr(mod, "MONSTRUOS_NORMALES", {})
            for k, v in d.items():
                result.append((f"no_z{zona}_{k}", dict(v, zona=zona, tipo="normal")))

        # Mazmorras normal
        arch = os.path.join(base, f"monstruos_mazmorras_zona_{zona}_normal.py")
        if os.path.exists(arch):
            mod = _importar_archivo(arch)
            d = getattr(mod, "MONSTRUOS_MAZMORRAS_NORMAL", {})
            for k, v in d.items():
                result.append((f"mn_z{zona}_{k}", dict(v, zona=zona, tipo="mazmorra_normal")))

        # Mazmorras difícil
        arch = os.path.join(base, f"monstruos_mazmorras_zona_{zona}_dificil.py")
        if os.path.exists(arch):
            mod = _importar_archivo(arch)
            d = getattr(mod, "MONSTRUOS_MAZMORRAS_DIFICIL", {})
            for k, v in d.items():
                result.append((f"md_z{zona}_{k}", dict(v, zona=zona, tipo="mazmorra_dificil")))

        # Mini boss
        arch = os.path.join(base, f"monstruos_mini_boss_zona_{zona}.py")
        if os.path.exists(arch):
            mod = _importar_archivo(arch)
            d = getattr(mod, "MONSTRUOS_MINI_BOSS", {})
            for k, v in d.items():
                result.append((f"mb_z{zona}_{k}", dict(v, zona=zona, tipo="mini_boss")))

    return sorted(result, key=lambda x: (int(x[1].get("zona", 99)) if str(x[1].get("zona", "")).isdigit() else 99,
                                          x[1].get("tipo", ""), x[1].get("nombre", "")))


def _cat(sec: str) -> List[Tuple[str, Dict[str, Any]]]:
    if sec not in _CAT:
        _cargar_seccion(sec)
    return _CAT[sec]


# ══════════════════════════════════════════════════════════════
# HELPERS DE EDICIÓN
# ══════════════════════════════════════════════════════════════

def _get_live_item(sec: str, kid: str) -> Optional[Dict]:
    """Devuelve referencia mutable al dict del item en memoria."""
    try:
        if sec == "arm":
            from armas import ARMAS
            return ARMAS.get(kid)
        elif sec == "ard":
            from armaduras import ARMADURAS
            return ARMADURAS.get(kid)
        elif sec == "poc":
            from pociones import POCIONES
            return POCIONES.get(kid)
        elif sec == "mat":
            from materiales import MATERIALES
            return MATERIALES.get(kid)
        elif sec == "mnt":
            from monturas import MONTURAS
            return MONTURAS.get(kid)
    except ImportError:
        pass
    return None


def _convert_valor(current_val: Any, raw: str) -> Any:
    """Convierte texto ingresado al tipo correcto según el valor actual."""
    raw = raw.strip()
    if raw.lower() in ("none", "null", "ninguno", "-", ""):
        return None
    if isinstance(current_val, bool):
        return raw.lower() in ("true", "si", "sí", "1", "yes", "verdadero")
    if isinstance(current_val, int):
        try:
            return int(raw)
        except ValueError:
            try:
                return int(float(raw))
            except Exception:
                return raw
    if isinstance(current_val, float):
        try:
            return float(raw)
        except ValueError:
            return raw
    # str o None: intenta int → float → str
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        pass
    return raw


def _save_item_override(sec: str, kid: str, field: str, valor: Any) -> None:
    """Guarda el override en BD y actualiza el dict en memoria."""
    valor_str = str(valor) if valor is not None else "None"
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if sec == "mon":
        c.execute(
            "INSERT OR REPLACE INTO stats_overrides_monstruos (monstruo_id, stat, valor) VALUES (?,?,?)",
            (kid, field, valor_str),
        )
    else:
        c.execute(
            "INSERT OR REPLACE INTO stats_overrides_items (item_id, stat, valor) VALUES (?,?,?)",
            (kid, field, valor_str),
        )
    conn.commit()
    conn.close()
    # Parchear en memoria
    item = _get_live_item(sec, kid)
    if item is not None:
        item[field] = valor
    # Invalidar caché del panel para que la próxima navegación refleje el cambio
    _CAT.pop(sec, None)


def _jugadores_con_item(item_nombre: str) -> List[int]:
    """Devuelve user_ids de jugadores que tienen este item equipado."""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(
            "SELECT user_id FROM jugadores WHERE arma_equipada = ? OR armadura_equipada = ?",
            (item_nombre, item_nombre),
        )
        rows = c.fetchall()
        conn.close()
        return [r[0] for r in rows]
    except Exception:
        return []


def _filtrar(sec: str, fk: str, fv: str) -> List[Tuple[str, Dict[str, Any]]]:
    campo = FIELD_MAP.get(fk, fk)
    return [(k, v) for k, v in _cat(sec) if str(v.get(campo, "")).lower() == fv.lower()]


def _valores_filtro(sec: str, fk: str) -> List[str]:
    campo = FIELD_MAP.get(fk, fk)
    vistos = []
    for _, v in _cat(sec):
        val = str(v.get(campo, ""))
        if val and val not in vistos:
            vistos.append(val)
    return sorted(vistos, key=lambda x: (int(x) if x.isdigit() else 0, x))


# ══════════════════════════════════════════════════════════════
# TEXTO DE DETALLE
# ══════════════════════════════════════════════════════════════

def _rareza_str(r) -> str:
    r = int(r) if r else 1
    return f"{RAREZA_EMOJI.get(r, '?')} {RAREZA_NOMBRE.get(r, str(r))}"


def _precio_str(v: Dict, campo_o: str, campo_et: str, campo_cr: str) -> str:
    o = v.get(campo_o, 0) or 0
    et = v.get(campo_et, 0) or 0
    cr = v.get(campo_cr, 0) or 0
    partes = []
    if o:
        partes.append(f"🪙 {o:,}")
    if et:
        partes.append(f"💎 {et:,}")
    if cr:
        partes.append(f"✨ {cr:,}")
    return " | ".join(partes) if partes else "—"


def _texto_detalle(sec: str, kid: str, v: Dict) -> str:
    """Devuelve HTML listo para parse_mode='HTML'."""
    emoji, nombre_sec = SECCIONES[sec]
    nom = _e(v.get("nombre", kid))
    zona = v.get("zona", "?")
    ze = ZONA_EMOJI.get(str(zona).lower(), "🌐")
    zona_txt = _e(str(zona).capitalize())
    lineas = [f"{emoji} <b>{nom.upper()}</b>", "━━━━━━━━━━━━━━━━━━━━━"]

    if sec in ("arm", "ard"):
        clase = v.get("clase_requerida")
        lineas.append(f"🏷️ Tipo: <code>{_e(v.get('tipo','?'))}</code> | Zona: {ze} {zona_txt}")
        lineas.append(f"⭐ {_e(_rareza_str(v.get('rareza', 1)))} | Nivel req.: <code>{v.get('nivel_requerido', 1)}</code>")
        lineas.append(f"👤 Clase: <code>{_e(CLASE_NOMBRES.get(str(clase), str(clase)))}</code>")
        lineas.append(f"📦 Origen: <code>{_e(ORIGEN_NOMBRES.get(v.get('origen','?'), v.get('origen','?')))}</code>")
        lineas.append("")
        lineas.append("📊 <b>STATS</b>")
        if sec == "arm":
            lineas.append(f"⚔️ Daño: <code>{_e(v.get('daño','?'))}</code>  💥 Crítico: <code>{_e(v.get('critico','?'))}%</code>")
            lineas.append(f"💨 Velocidad: <code>{_e(v.get('velocidad','?'))}</code>  ⚖️ Peso: <code>{_e(v.get('peso','?'))}</code>")
        else:
            lineas.append(f"🛡️ Defensa: <code>{_e(v.get('defensa','?'))}</code>  🔰 Res.crítico: <code>{_e(v.get('resistencia_critico','?'))}%</code>")
            lineas.append(f"💨 Vel.mov.: <code>{_e(v.get('velocidad_movimiento','?'))}</code>  ⚖️ Peso: <code>{_e(v.get('peso','?'))}</code>")
        lineas.append(f"❤️ Vida extra: <code>{_e(v.get('vida_extra', 0))}</code>  🛡️ Def.extra: <code>{_e(v.get('defensa_extra', 0))}</code>")
        ha = v.get("habilidad_activa")
        hp = v.get("habilidad_pasiva")
        if ha:
            lineas.append(f"⚡ Activa: {_e(ha)}")
        if hp:
            lineas.append(f"🌀 Pasiva: {_e(hp)}")
        lineas.append("")
        lineas.append("💰 <b>PRECIOS</b>")
        lineas.append(f"Tienda: {_e(_precio_str(v,'precio_oro','precio_eternium','precio_creditos'))}")
        lineas.append(f"Venta: {_e(_precio_str(v,'precio_venta_oro','precio_venta_eternium',''))}")
        lineas.append("")
        lineas.append(f"📦 Stock: <code>{_e(v.get('stock_restante','?'))} / {_e(v.get('stock_global','?'))}</code>")
        lineas.append(f"🔒 Única: <code>{'Sí' if v.get('unica') else 'No'}</code>")

    elif sec == "poc":
        lineas.append(f"🧴 Subtipo: <code>{_e(v.get('subtipo','?'))}</code> | Calidad: <code>{_e(v.get('calidad','?'))}</code>")
        lineas.append(f"Zona: {ze} {zona_txt} | Nivel req.: <code>{v.get('nivel_requerido', 1)}</code>")
        lineas.append(f"⭐ {_e(_rareza_str(v.get('rareza', 1)))}")
        lineas.append(f"📦 Origen: <code>{_e(ORIGEN_NOMBRES.get(v.get('origen','?'), v.get('origen','?')))}</code>")
        lineas.append("")
        lineas.append("✨ <b>EFECTO</b>")
        lineas.append(_e(str(v.get("efecto", "—"))))
        lineas.append("")
        lineas.append("💰 <b>PRECIOS</b>")
        lineas.append(f"Tienda: {_e(_precio_str(v,'precio_oro','precio_eternium','precio_creditos'))}")
        lineas.append(f"Venta: {_e(_precio_str(v,'precio_venta_oro','precio_venta_eternium',''))}")
        lineas.append(f"📦 Stock: <code>{_e(v.get('stock_restante','?'))} / {_e(v.get('stock_global','?'))}</code>")

    elif sec == "mat":
        lineas.append(f"💎 Tipo: <code>{_e(v.get('tipo','?'))}</code> | Calidad: <code>{_e(v.get('calidad','?'))}</code>")
        lineas.append(f"Zona: {ze} {zona_txt} | Nivel req.: <code>{v.get('nivel_requerido', 1)}</code>")
        lineas.append(f"⭐ {_e(_rareza_str(v.get('rareza', 1)))}")
        lineas.append(f"📦 Origen: <code>{_e(ORIGEN_NOMBRES.get(v.get('origen','?'), v.get('origen','?')))}</code>")
        lineas.append(f"⚗️ Valor crafteo: <code>{_e(v.get('valor_crafteo', '?'))}</code>")
        lineas.append("")
        lineas.append("💰 <b>VENTA</b>")
        lineas.append(f"🪙 {v.get('precio_venta_oro',0):,} | 💎 {v.get('precio_venta_eternium',0) or 0:,} | ✨ {v.get('precio_creditos',0) or 0:,}")
        lineas.append(f"📦 Stock: <code>{_e(v.get('stock_restante','?'))} / {_e(v.get('stock_global','?'))}</code>")

    elif sec == "mnt":
        lineas.append(f"🦄 Subtipo: <code>{_e(v.get('subtipo','?'))}</code> | Calidad: <code>{_e(v.get('calidad','?'))}</code>")
        lineas.append(f"Zona: {ze} {zona_txt} | Nivel req.: <code>{v.get('nivel_requerido', 1)}</code>")
        lineas.append(f"⭐ {_e(_rareza_str(v.get('rareza', 1)))}")
        lineas.append("")
        lineas.append("📊 <b>STATS</b>")
        lineas.append(f"💨 Velocidad: <code>{_e(v.get('velocidad','?'))}</code>  📦 Carga: <code>{_e(v.get('carga','?'))}</code>")
        lineas.append(f"🫥 Sigilo: <code>{_e(v.get('sigilo','?'))}</code>  🛡️ Defensa: <code>{_e(v.get('defensa','?'))}</code>  ⚔️ Ataque: <code>{_e(v.get('ataque','?'))}</code>")
        efecto = v.get("efecto")
        if efecto:
            lineas.append(f"✨ Efecto: {_e(efecto)}")
        lineas.append("")
        lineas.append("💰 <b>PRECIOS</b>")
        lineas.append(f"Tienda: {_e(_precio_str(v,'precio_oro','precio_eternium','precio_creditos'))}")
        lineas.append(f"Venta: {_e(_precio_str(v,'precio_venta_oro','precio_venta_eternium',''))}")
        lineas.append(f"📦 Stock: <code>{_e(v.get('stock_restante','?'))} / {_e(v.get('stock_global','?'))}</code>")

    elif sec == "mon":
        tipo_label = {
            "normal": "🌿 Normal (campo)",
            "mazmorra_normal": "🏰 Mazmorra Normal",
            "mazmorra_dificil": "🔥 Mazmorra Difícil",
            "mini_boss": "💀 Mini Boss",
        }.get(v.get("tipo", "?"), v.get("tipo", "?"))
        lineas.append(f"Zona: {ze} {_e(str(zona))} | {tipo_label}")
        lineas.append(f"👤 Clase: <code>{_e(CLASE_NOMBRES.get(str(v.get('clase')), str(v.get('clase','?'))))}</code>")
        lineas.append(f"⚔️ Nivel: <code>{_e(v.get('nivel','?'))}</code>")
        lineas.append("")
        lineas.append("📊 <b>STATS</b>")
        lineas.append(f"❤️ Vida: <code>{_e(v.get('vida_max', v.get('vida','?')))}</code>  ⚔️ Daño: <code>{_e(v.get('daño','?'))}</code>  🛡️ Defensa: <code>{_e(v.get('defensa','?'))}</code>")
        lineas.append(f"⭐ XP: <code>{_e(v.get('xp','?'))}</code>  🪙 Oro: <code>{_e(v.get('oro','?'))}</code>")
        drops = v.get("drops", [])
        if drops:
            lineas.append("")
            lineas.append(f"🎁 <b>DROPS</b> ({len(drops)})")
            for dr in drops[:4]:
                prob = int(dr.get("probabilidad", 0) * 100)
                lineas.append(f"  • <code>{_e(dr.get('nombre','?'))}</code> — {prob}%")
            if len(drops) > 4:
                lineas.append(f"  <i>(+{len(drops)-4} más)</i>")
        lineas.append("")
        lineas.append(f"🔑 ID: <code>{_e(kid)}</code>")

    desc = v.get("descripcion", "")
    if desc:
        lineas.append("")
        desc_txt = _e(str(desc)[:180]) + ("..." if len(str(desc)) > 180 else "")
        lineas.append(f"📝 <i>{desc_txt}</i>")

    lineas.append("━━━━━━━━━━━━━━━━━━━━━")
    if CAMPOS_EDICION.get(sec):
        lineas.append("✏️ <i>Usa los botones de edición de abajo</i>")
    else:
        cmd = EDIT_CMD.get(sec)
        if cmd:
            lineas.append(f"✏️ Editar con: <code>{_e(cmd)}</code>")

    return "\n".join(lineas)


# ══════════════════════════════════════════════════════════════
# TECLADOS
# ══════════════════════════════════════════════════════════════

def _btn(texto: str, cb: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(texto, callback_data=cb)


def _teclado_main() -> InlineKeyboardMarkup:
    filas = []
    for sec, (emoji, nombre) in SECCIONES.items():
        n = len(_cat(sec))
        filas.append([_btn(f"{emoji} {nombre} ({n})", f"p|{sec}")])
    return InlineKeyboardMarkup(filas)


def _teclado_seccion(sec: str) -> InlineKeyboardMarkup:
    filtros = FILTROS_SECCION[sec]
    filas = [[_btn(label, f"p|{sec}|{fk}")] for fk, label in filtros]
    filas.append([_btn("🔙 Volver al panel", "p|home")])
    return InlineKeyboardMarkup(filas)


def _teclado_filtro_valores(sec: str, fk: str) -> InlineKeyboardMarkup:
    valores = _valores_filtro(sec, fk)
    filas = []
    fila_actual = []
    for val in valores:
        # etiqueta legible
        if fk == "z":
            ze = ZONA_EMOJI.get(str(val).lower(), "")
            label = f"{ze} {val.capitalize()}"
        elif fk == "c":
            label = CLASE_NOMBRES.get(str(val), str(val))
        elif fk == "o":
            label = ORIGEN_NOMBRES.get(str(val), str(val))
        elif fk == "t" and sec == "mon":
            label = {"normal": "🌿 Normal", "mazmorra_normal": "🏰 Maz.Normal",
                     "mazmorra_dificil": "🔥 Maz.Difícil", "mini_boss": "💀 Mini Boss"}.get(val, val)
        else:
            label = str(val).replace("_", " ").capitalize()

        n = len(_filtrar(sec, fk, val))
        cb = f"p|{sec}|{fk}|{val}|0"
        fila_actual.append(_btn(f"{label} ({n})", cb))
        if len(fila_actual) == 2:
            filas.append(fila_actual)
            fila_actual = []
    if fila_actual:
        filas.append(fila_actual)
    filas.append([_btn(f"🔙 Volver", f"p|{sec}")])
    return InlineKeyboardMarkup(filas)


def _teclado_lista(sec: str, fk: str, fv: str, pagina: int,
                   items: List[Tuple[str, Dict]], total: int) -> InlineKeyboardMarkup:
    total_pags = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    inicio = pagina * PAGE_SIZE
    filas = []
    for idx_abs, (kid, v) in enumerate(items, start=inicio):
        nom = v.get("nombre", kid)
        label = nom[:38] + ("…" if len(nom) > 38 else "")
        cb = f"pi|{sec}|{fk}|{fv}|{idx_abs}"
        filas.append([_btn(label, cb)])

    # Paginación
    nav = []
    if pagina > 0:
        nav.append(_btn("⬅️ Anterior", f"p|{sec}|{fk}|{fv}|{pagina-1}"))
    nav.append(_btn(f"📄 {pagina+1}/{total_pags}", "p|noop"))
    if (pagina + 1) < total_pags:
        nav.append(_btn("Siguiente ➡️", f"p|{sec}|{fk}|{fv}|{pagina+1}"))
    filas.append(nav)
    filas.append([_btn("🔙 Volver", f"p|{sec}|{fk}")])
    return InlineKeyboardMarkup(filas)


def _teclado_detalle(sec: str, fk: str, fv: str, idx_abs: int, pagina: int) -> InlineKeyboardMarkup:
    """Teclado del detalle: botones de grupo de edición + volver."""
    grupos = list(CAMPOS_EDICION.get(sec, {}).keys())
    filas: List[List[InlineKeyboardButton]] = []
    fila: List[InlineKeyboardButton] = []
    for i, grp in enumerate(grupos):
        fila.append(_btn(f"✏️ {grp}", f"peg|{i}"))
        if len(fila) == 2:
            filas.append(fila)
            fila = []
    if fila:
        filas.append(fila)
    filas.append([_btn("🔙 Volver a la lista", f"p|{sec}|{fk}|{fv}|{pagina}")])
    return InlineKeyboardMarkup(filas)


# ══════════════════════════════════════════════════════════════
# HANDLERS
# ══════════════════════════════════════════════════════════════

async def cmd_panel_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != SUPERADMIN_ID:
        return
    # Pre-cargar armas y armaduras para mostrar totales (el resto lazy)
    for sec in SECCIONES:
        _cat(sec)

    emoji_tot = " | ".join(f"{e} {len(_cat(s))}" for s, (e, _) in SECCIONES.items())
    texto = (
        "🗃️ <b>PANEL MAESTRO</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"{emoji_tot}\n\n"
        "Selecciona una categoría:"
    )
    await update.effective_message.reply_text(texto, parse_mode="HTML",
                                              reply_markup=_teclado_main())


async def cb_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return
    if query.from_user.id != SUPERADMIN_ID:
        await query.answer("Solo superadmin.", show_alert=True)
        return
    await query.answer()

    data = query.data  # e.g. "p|arm|z|azul|0" or "pi|arm|z|azul|3"
    partes = data.split("|")

    # ── Item detail ──────────────────────────────────────────
    if partes[0] == "pi":
        # pi|sec|fk|fv|idx_abs
        _, sec, fk, fv, idx_abs_s = partes
        idx_abs = int(idx_abs_s)
        todos = _filtrar(sec, fk, fv)
        if idx_abs >= len(todos):
            await query.edit_message_text("❌ Item no encontrado.")
            return
        kid, v = todos[idx_abs]
        pagina = idx_abs // PAGE_SIZE
        # Guardar contexto para los handlers de edición inline
        context.user_data["pe_sec"] = sec
        context.user_data["pe_kid"] = kid
        context.user_data["pe_fk"] = fk
        context.user_data["pe_fv"] = fv
        context.user_data["pe_idx"] = idx_abs
        texto = _texto_detalle(sec, kid, v)
        await query.edit_message_text(
            texto, parse_mode="HTML",
            reply_markup=_teclado_detalle(sec, fk, fv, idx_abs, pagina)
        )
        return

    # ── Navegación p| ────────────────────────────────────────
    if partes[0] != "p":
        return

    if len(partes) < 2:
        return

    ruta = partes[1:]

    # Noop (botón de página actual)
    if ruta[0] == "noop":
        return

    # Panel principal
    if ruta[0] == "home":
        emoji_tot = " | ".join(f"{e} {len(_cat(s))}" for s, (e, _) in SECCIONES.items())
        texto = (
            "🗃️ <b>PANEL MAESTRO</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            f"{emoji_tot}\n\n"
            "Selecciona una categoría:"
        )
        await query.edit_message_text(texto, parse_mode="HTML",
                                      reply_markup=_teclado_main())
        return

    # Sección sin filtro → menú de filtros
    if len(ruta) == 1:
        sec = ruta[0]
        if sec not in SECCIONES:
            return
        emoji, nombre = SECCIONES[sec]
        total = len(_cat(sec))
        texto = f"{emoji} <b>{_e(nombre.upper())}</b>\n━━━━━━━━━━━━━━━━━━━━━\nTotal: <code>{total}</code> objetos\n\nFiltrar por:"
        await query.edit_message_text(texto, parse_mode="HTML",
                                      reply_markup=_teclado_seccion(sec))
        return

    # Sección + filtro key → selector de valores
    if len(ruta) == 2:
        sec, fk = ruta
        if sec not in SECCIONES:
            return
        emoji, nombre = SECCIONES[sec]
        campo = FIELD_MAP.get(fk, fk)
        label_fk = next((lb for k, lb in FILTROS_SECCION.get(sec, []) if k == fk), fk)
        texto = f"{emoji} <b>{_e(nombre.upper())}</b> — {_e(label_fk)}\n━━━━━━━━━━━━━━━━━━━━━\nElige un valor:"
        await query.edit_message_text(texto, parse_mode="HTML",
                                      reply_markup=_teclado_filtro_valores(sec, fk))
        return

    # Lista paginada: p|sec|fk|fv|pagina
    if len(ruta) == 4:
        sec, fk, fv, pag_s = ruta
        pagina = int(pag_s)
        todos = _filtrar(sec, fk, fv)
        total = len(todos)
        if total == 0:
            await query.edit_message_text("❌ Sin resultados.")
            return
        total_pags = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
        pagina = max(0, min(pagina, total_pags - 1))
        inicio = pagina * PAGE_SIZE
        items_pag = todos[inicio: inicio + PAGE_SIZE]

        emoji, nombre = SECCIONES[sec]
        ze = ZONA_EMOJI.get(fv.lower(), "") if fk == "z" else ""
        label_fv = f"{ze} {fv.capitalize()}" if fk == "z" else fv.replace("_", " ").capitalize()
        campo = FIELD_MAP.get(fk, fk)
        label_fk = next((lb for k, lb in FILTROS_SECCION.get(sec, []) if k == fk), fk)

        texto = (
            f"{emoji} <b>{_e(nombre.upper())}</b>\n"
            f"📂 {_e(label_fk.lstrip('🗺️🗡️👤📦🎽🧴⭐💎🦄⚔️ '))}: {_e(label_fv)}\n"
            f"Total: <code>{total}</code> | Página <code>{pagina+1}/{total_pags}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            "<i>Toca un objeto para ver sus stats:</i>"
        )
        await query.edit_message_text(
            texto, parse_mode="HTML",
            reply_markup=_teclado_lista(sec, fk, fv, pagina, items_pag, total)
        )
        return


# ══════════════════════════════════════════════════════════════
# HANDLERS DE EDICIÓN INLINE
# ══════════════════════════════════════════════════════════════

async def cb_panel_grupo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Usuario pulsó un botón de grupo de edición (peg|n)."""
    query = update.callback_query
    if query.from_user.id != SUPERADMIN_ID:
        await query.answer("Solo superadmin.", show_alert=True)
        return
    await query.answer()
    try:
        n = int(query.data.split("|")[1])
    except (ValueError, IndexError):
        await query.answer("❌ Error al procesar.", show_alert=True)
        return
    sec = context.user_data.get("pe_sec", "")
    kid = context.user_data.get("pe_kid", "")
    grupos = list(CAMPOS_EDICION.get(sec, {}).items())
    if n >= len(grupos):
        await query.answer("Grupo no válido.", show_alert=True)
        return
    grp_label, campos = grupos[n]
    context.user_data["pe_grp"] = n
    item = _get_live_item(sec, kid)
    texto = f"✏️ <b>{_e(grp_label)}</b>\n📦 <code>{_e(kid)}</code>\n\nElige el campo a editar:\n\n"
    for campo in campos:
        val = item.get(campo, "—") if item else "—"
        texto += f"  • <code>{_e(campo)}</code>: {_e(str(val))}\n"
    keyboard: List[List[InlineKeyboardButton]] = []
    fila_k: List[InlineKeyboardButton] = []
    for i, campo in enumerate(campos):
        fila_k.append(_btn(campo, f"pef|{i}"))
        if len(fila_k) == 3:
            keyboard.append(fila_k)
            fila_k = []
    if fila_k:
        keyboard.append(fila_k)
    keyboard.append([_btn("🔙 Volver al objeto", "pbd")])
    await query.edit_message_text(
        texto, parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def cb_panel_back_detalle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Vuelve al detalle del objeto desde la vista de grupos (pbd)."""
    query = update.callback_query
    if query.from_user.id != SUPERADMIN_ID:
        await query.answer("Solo superadmin.", show_alert=True)
        return
    await query.answer()
    sec = context.user_data.get("pe_sec", "")
    kid = context.user_data.get("pe_kid", "")
    fk = context.user_data.get("pe_fk", "z")
    fv = context.user_data.get("pe_fv", "")
    idx_abs = context.user_data.get("pe_idx", 0)
    pagina = idx_abs // PAGE_SIZE
    item = _get_live_item(sec, kid)
    if item is None:
        todos = _cat(sec)
        for k, v in todos:
            if k == kid:
                item = v
                break
    if item:
        texto = _texto_detalle(sec, kid, item)
    else:
        texto = f"❌ Item <code>{_e(kid)}</code> no encontrado."
    await query.edit_message_text(
        texto, parse_mode="HTML",
        reply_markup=_teclado_detalle(sec, fk, fv, idx_abs, pagina),
    )


async def cb_panel_campo_inicio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry point del ConversationHandler: usuario pulsó un campo concreto (pef|n)."""
    query = update.callback_query
    if query.from_user.id != SUPERADMIN_ID:
        await query.answer("Solo superadmin.", show_alert=True)
        return ConversationHandler.END
    await query.answer()
    try:
        n = int(query.data.split("|")[1])
    except (ValueError, IndexError):
        await query.answer("❌ Error al procesar.", show_alert=True)
        return ConversationHandler.END
    sec = context.user_data.get("pe_sec", "")
    grp_n = context.user_data.get("pe_grp", 0)
    grupos = list(CAMPOS_EDICION.get(sec, {}).values())
    if grp_n >= len(grupos):
        return ConversationHandler.END
    campos = grupos[grp_n]
    if n >= len(campos):
        return ConversationHandler.END
    campo = campos[n]
    context.user_data["pe_campo"] = campo
    kid = context.user_data.get("pe_kid", "?")
    item = _get_live_item(sec, kid)
    valor_actual = item.get(campo, "—") if item else "—"
    tipo_hint = ""
    if isinstance(valor_actual, bool):
        tipo_hint = " <i>(escribe: true/false)</i>"
    elif isinstance(valor_actual, int):
        tipo_hint = " <i>(número entero)</i>"
    elif isinstance(valor_actual, float):
        tipo_hint = " <i>(número decimal)</i>"
    elif valor_actual is None or str(valor_actual) == "None":
        tipo_hint = " <i>(o 'none' para vacío)</i>"
    else:
        tipo_hint = " <i>(texto)</i>"
    await query.edit_message_text(
        f"✏️ <b>Editando campo:</b> <code>{_e(campo)}</code>{tipo_hint}\n"
        f"📦 Objeto: <code>{_e(kid)}</code>\n"
        f"📌 Valor actual: <code>{_e(str(valor_actual))}</code>\n\n"
        f"Escribe el nuevo valor (o /cancelar para salir):",
        parse_mode="HTML",
    )
    return PANEL_EDIT_VALOR


async def panel_edit_aplicar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recibe el nuevo valor escrito, lo valida, guarda y confirma."""
    if update.effective_user.id != SUPERADMIN_ID:
        return ConversationHandler.END
    sec = context.user_data.get("pe_sec", "")
    kid = context.user_data.get("pe_kid", "")
    campo = context.user_data.get("pe_campo", "")
    if not all([sec, kid, campo]):
        await update.effective_message.reply_text("❌ Sesión expirada. Usa /sa_panel.")
        return ConversationHandler.END
    raw = update.message.text.strip()
    item = _get_live_item(sec, kid)
    current_val = item.get(campo) if item else None
    try:
        valor = _convert_valor(current_val, raw)
    except Exception as e:
        await update.effective_message.reply_text(
            f"❌ Valor inválido: {e}\nIntenta de nuevo o /cancelar."
        )
        return PANEL_EDIT_VALOR
    _save_item_override(sec, kid, campo, valor)
    nombre_item = item.get("nombre", kid) if item else kid
    nota_eq = ""
    if sec in ("arm", "ard") and campo in (
        "daño", "defensa", "critico", "velocidad", "vida_extra", "defensa_extra"
    ):
        uids = _jugadores_con_item(nombre_item)
        if uids:
            nota_eq = f"\n⚔️ {len(uids)} jugador(es) con este item equipado — stats actualizados automáticamente."
    await update.effective_message.reply_text(
        f"✅ <b>{_e(nombre_item)}</b>\n<code>{_e(campo)}</code> → <code>{_e(str(valor))}</code>{_e(nota_eq)}\n\n"
        f"Pulsa 🔙 <i>Volver al objeto</i> si volviste al panel, o elige otro campo.",
        parse_mode="HTML",
    )
    return ConversationHandler.END


async def panel_edit_cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("pe_campo", None)
    await update.effective_message.reply_text(
        "Edición cancelada. Usa /sa_panel para volver al panel."
    )
    return ConversationHandler.END


# ══════════════════════════════════════════════════════════════
# REGISTRO
# ══════════════════════════════════════════════════════════════

def registrar_handlers(app):
    texto_no_cmd = filters.TEXT & ~filters.COMMAND

    # ConversationHandler de edición (prioridad alta, va primero)
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(cb_panel_campo_inicio, pattern=r"^pef\|\d+$")],
        states={
            PANEL_EDIT_VALOR: [MessageHandler(texto_no_cmd, panel_edit_aplicar)],
        },
        fallbacks=[CommandHandler("cancelar", panel_edit_cancelar)],
        per_message=False,
        allow_reentry=True,
    ))

    # Navegación de grupos y vuelta al detalle
    app.add_handler(CallbackQueryHandler(cb_panel_grupo, pattern=r"^peg\|\d+$"))
    app.add_handler(CallbackQueryHandler(cb_panel_back_detalle, pattern=r"^pbd$"))

    # Panel principal
    app.add_handler(CommandHandler("sa_panel", cmd_panel_admin))
    app.add_handler(CommandHandler("panel", cmd_panel_admin))
    app.add_handler(CallbackQueryHandler(cb_panel, pattern=r"^p[i]?\|"))

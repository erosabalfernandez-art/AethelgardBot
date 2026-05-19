#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# tienda.py - Versión definitiva COMPLETA con precios dinámicos, catálogos completos y todo el registro de handlers.

import sys
import os
import random
import sqlite3
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional

logger = logging.getLogger(__name__)

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler

# ==================== ESCAPE MARKDOWN ====================
def _esc(texto: str) -> str:
    """Escapa caracteres especiales de Markdown v1 de Telegram en texto dinámico."""
    if not texto:
        return ""
    return str(texto).replace("_", "\\_").replace("*", "\\*").replace("`", "\\`").replace("[", "\\[")

# ==================== BÚSQUEDA RECURSIVA ====================
def buscar_archivo(nombre_archivo, directorio_inicio):
    actual = os.path.abspath(directorio_inicio)
    while True:
        ruta = os.path.join(actual, nombre_archivo)
        if os.path.isfile(ruta):
            return ruta
        padre = os.path.dirname(actual)
        if padre == actual:
            break
        actual = padre
    for raiz, dirs, archivos in os.walk(directorio_inicio):
        if nombre_archivo in archivos:
            return os.path.join(raiz, nombre_archivo)
    return None

def encontrar_raiz_proyecto():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    ruta = buscar_archivo("datos_zona.py", script_dir)
    if ruta:
        return os.path.dirname(ruta)
    return os.path.dirname(script_dir)

RAIZ = encontrar_raiz_proyecto()
sys.path.insert(0, RAIZ)

import economia
from recetas import RECETAS
from materiales import MATERIALES as _MATERIALES_DATA
import db_helper
import config_balance
from datos_zona import ZONAS

# Cargar módulos de catálogos
def cargar_modulo(nombre):
    ruta = buscar_archivo(nombre, RAIZ)
    if ruta:
        import importlib.util
        spec = importlib.util.spec_from_file_location(nombre.replace('.py',''), ruta)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    return None

armas_mod = cargar_modulo("armas.py")
armaduras_mod = cargar_modulo("armaduras.py")
pociones_mod = cargar_modulo("pociones.py")
monturas_mod = cargar_modulo("monturas.py")

ARMAS = armas_mod.ARMAS if armas_mod else {}
ARMADURAS = armaduras_mod.ARMADURAS if armaduras_mod else {}
POCIONES = pociones_mod.POCIONES if pociones_mod else {}
MONTURAS = monturas_mod.MONTURAS if monturas_mod else {}

# ==================== FUNCIÓN AUXILIAR _en_ciudad ====================
def _en_ciudad(user_id: int) -> bool:
    try:
        jug = db_helper.obtener_jugador(user_id)
        if not jug:
            return False
        return jug.get("ubicacion", "ciudad") == "ciudad"
    except:
        pass
    return False

# ==================== PRECIOS DINÁMICOS ====================
def _mult_escasez() -> float:
    try:
        import umbral_vacio as _uv
        return _uv.get_multiplicador_precios()
    except Exception:
        return 1.0

def calcular_precio_oro(nivel, rareza):
    # factor_oro=400 → precios exigentes pero alcanzables con juego constante.
    # Admin puede sobreescribir via panel con "tienda_factor_oro".
    try:
        import config_db as _cdb
        factor = _cdb.get("tienda_factor_oro", 400)
    except Exception:
        factor = 400
    return int(nivel * factor * rareza * _mult_escasez())

def calcular_precio_eternium(nivel, rareza):
    # factor_eternium=12 → equilibra con la escasez de eternium en el juego.
    try:
        import config_db as _cdb
        factor = _cdb.get("tienda_factor_eternium", 12)
    except Exception:
        factor = 12
    return max(20, int(nivel * rareza * factor * _mult_escasez()))

def calcular_precio_creditos(nivel, rareza):
    # factor_creditos=5 → créditos son premium, precios proporcionalmente altos.
    try:
        import config_db as _cdb
        factor = _cdb.get("tienda_factor_creditos", 5)
    except Exception:
        factor = 5
    return max(5, nivel * rareza * factor)

# ==================== CATÁLOGOS ====================
CATALOGO_ORO = []
CATALOGO_ETERNIUM = []
OBJETOS_CREDITOS_MAESTROS = []

def agregar_objeto(objeto, origen, tipo, nombre, nivel, rareza, clase, descripcion, efecto_extra=""):
    precio_oro = calcular_precio_oro(nivel, rareza) if origen == "tienda_oro" else 0
    precio_eternium = calcular_precio_eternium(nivel, rareza) if origen == "tienda_eternium" else 0
    precio_creditos = calcular_precio_creditos(nivel, rareza) if origen == "tienda_creditos" else 0
    item = {
        "id": objeto.get("id", f"{tipo}_{nombre}"),
        "nombre": nombre,
        "descripcion": descripcion,
        "tipo": tipo,
        "clase": clase,
        "precio_oro": precio_oro,
        "precio_venta_oro": int(precio_oro * config_balance.TIENDA_VENTA_PORCENTAJE),
        "precio_eternium": precio_eternium,
        "precio_venta_eternium": int(precio_eternium * config_balance.TIENDA_VENTA_PORCENTAJE),
        "precio_creditos": precio_creditos,
        "efecto": efecto_extra,
        "nivel": nivel,
        "rareza": rareza,
        "zona": objeto.get("zona", "azul")
    }
    if origen == "tienda_oro":
        CATALOGO_ORO.append(item)
    elif origen == "tienda_eternium":
        CATALOGO_ETERNIUM.append(item)
    elif origen == "tienda_creditos":
        OBJETOS_CREDITOS_MAESTROS.append(item)

def construir_catalogos():
    for arma in ARMAS.values():
        nivel = arma.get("nivel_requerido", 1)
        rareza = arma.get("rareza", 1)
        clase = arma.get("clase_requerida")
        origen = arma.get("origen", "")
        if not origen:
            continue
        efecto = f"⚔️ Daño {arma['daño']} | Crítico {arma['critico']} | Velocidad {arma['velocidad']}"
        agregar_objeto(arma, origen, "arma", arma["nombre"], nivel, rareza, clase, arma["descripcion"], efecto)
    for armadura in ARMADURAS.values():
        nivel = armadura.get("nivel_requerido", 1)
        rareza = armadura.get("rareza", 1)
        clase = armadura.get("clase_requerida")
        origen = armadura.get("origen", "")
        if not origen:
            continue
        efecto = f"🛡️ Defensa {armadura['defensa']} | Resistencia crítico {armadura['resistencia_critico']} | Velocidad mov. {armadura['velocidad_movimiento']}"
        agregar_objeto(armadura, origen, "armadura", armadura["nombre"], nivel, rareza, clase, armadura["descripcion"], efecto)
    for pocion in POCIONES.values():
        nivel = pocion.get("nivel_requerido", 1)
        rareza = pocion.get("rareza", 1)
        clase = pocion.get("clase_requerida")
        origen = pocion.get("origen", "")
        if not origen:
            continue
        efecto = pocion.get("efecto", "")
        agregar_objeto(pocion, origen, "pocion", pocion["nombre"], nivel, rareza, clase, pocion["descripcion"], efecto)
    for montura in MONTURAS.values():
        nivel = montura.get("nivel_requerido", 1)
        rareza = montura.get("rareza", 1)
        clase = montura.get("clase_requerida")
        origen = montura.get("origen", "")
        if not origen:
            continue
        efecto = f"🐎 Velocidad +{montura.get('velocidad',0)}%"
        agregar_objeto(montura, origen, "montura", montura["nombre"], nivel, rareza, clase, montura["descripcion"], efecto)

construir_catalogos()

# ==================== FILTRO POR NIVEL Y ZONA ====================
# Espejo de viajes.py — determina que zonas puede acceder el jugador
_COLOR_INDICE_TIENDA = {"azul": 1, "amarilla": 2, "roja": 3, "negra": 4}
_NIVEL_DESBLOQUEO_TIENDA = {1: 1, 5: 2, 10: 3, 15: 4}

def _color_max_idx(nivel: int) -> int:
    """Devuelve el indice de color maximo para un nivel de jugador."""
    max_idx = 1
    for min_niv, idx in sorted(_NIVEL_DESBLOQUEO_TIENDA.items()):
        if nivel >= min_niv:
            max_idx = idx
    return max_idx

def _filtrar_items_jugador(catalogo: list, user_id: int) -> list:
    """Filtra el catalogo: solo items con nivel <= jugador y zona desbloqueada."""
    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        return []
    nivel = jug.get("nivel", 1)
    max_idx = _color_max_idx(nivel)
    return [
        item for item in catalogo
        if item.get("nivel", 1) <= nivel
        and _COLOR_INDICE_TIENDA.get(item.get("zona", "azul"), 1) <= max_idx
    ]

def _filtrar_recetas_lista(lista: list, user_id: int) -> list:
    """Filtra lista de (rid, receta) por nivel y zona del jugador."""
    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        return []
    nivel = jug.get("nivel", 1)
    max_idx = _color_max_idx(nivel)
    return [
        (rid, rec) for rid, rec in lista
        if rec.get("nivel_requerido", 1) <= nivel
        and _COLOR_INDICE_TIENDA.get(rec.get("zona_crafteo", "azul"), 1) <= max_idx
    ]


# ==================== TIENDA DE CRÉDITOS (ROTACIÓN) ====================
DB_PATH = "aethelgard.db"
ROTACION_HORAS = config_balance.TIENDA_ROTACION_CREDITOS_DIAS * 24

def _crear_tabla_creditos():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS tienda_creditos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            objeto_id TEXT,
            nombre TEXT,
            descripcion TEXT,
            tipo TEXT,
            clase_requerida TEXT,
            precio_creditos INTEGER,
            stock INTEGER,
            efecto TEXT,
            fecha_inicio TIMESTAMP,
            fecha_fin TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

_crear_tabla_creditos()

async def generar_rotacion_creditos(context=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('DELETE FROM tienda_creditos')
    candidatos = OBJETOS_CREDITOS_MAESTROS.copy()
    seleccionados = random.sample(candidatos, min(8, len(candidatos)))
    ahora = datetime.now()
    fin = ahora + timedelta(hours=ROTACION_HORAS)
    for obj in seleccionados:
        c.execute('''
            INSERT INTO tienda_creditos 
            (objeto_id, nombre, descripcion, tipo, clase_requerida, precio_creditos, stock, efecto, fecha_inicio, fecha_fin)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (obj["id"], obj["nombre"], obj["descripcion"], obj["tipo"], obj["clase"], obj["precio_creditos"],
              5, obj["efecto"], ahora.isoformat(), fin.isoformat()))
    conn.commit()
    conn.close()

def obtener_rotacion_creditos() -> List[Dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    ahora = datetime.now().isoformat()
    c.execute('SELECT * FROM tienda_creditos WHERE fecha_inicio <= ? AND fecha_fin >= ?', (ahora, ahora))
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

# ==================== COMPRA/VENTA ====================
def comprar_oro(user_id: int, item_id: str) -> Tuple[bool, str]:
    for item in CATALOGO_ORO:
        if item["id"] == item_id:
            precio = item["precio_oro"]
            if precio <= 0:
                return False, "Este objeto no se puede comprar con oro."
            saldos = economia.obtener_saldos(user_id)
            if saldos.get("oro", 0) < precio:
                return False, f"No tienes suficiente oro. Necesitas {precio}."
            economia.modificar_saldo(user_id, "oro", -precio, f"compra tienda oro: {item['nombre']}")
            db_helper.agregar_item(user_id, item["nombre"], 1)
            return True, f"✅ Compraste {item['nombre']} por {precio} oro."
    return False, "Objeto no encontrado."

def comprar_eternium(user_id: int, item_id: str) -> Tuple[bool, str]:
    for item in CATALOGO_ETERNIUM:
        if item["id"] == item_id:
            precio = item["precio_eternium"]
            if precio <= 0:
                return False, "Este objeto no se puede comprar con eternium."
            saldos = economia.obtener_saldos(user_id)
            if saldos.get("eternium", 0) < precio:
                return False, f"No tienes suficiente eternium. Necesitas {precio}."
            economia.modificar_saldo(user_id, "eternium", -precio, f"compra tienda eternium: {item['nombre']}")
            db_helper.agregar_item(user_id, item["nombre"], 1)
            return True, f"✅ Compraste {item['nombre']} por {precio} eternium."
    return False, "Objeto no encontrado."

def comprar_credito(user_id: int, item_id: int) -> Tuple[bool, str]:
    rotacion = obtener_rotacion_creditos()
    item = next((i for i in rotacion if i["id"] == item_id), None)
    if not item:
        return False, "Ese objeto ya no está disponible en la tienda."
    if item["stock"] <= 0:
        return False, "El stock de este objeto se ha agotado."
    precio = item["precio_creditos"]
    saldos = economia.obtener_saldos(user_id)
    if saldos.get("creditos_vacio", 0) < precio:
        return False, f"No tienes suficientes créditos. Necesitas {precio}."
    economia.modificar_saldo(user_id, "creditos_vacio", -precio, f"compra tienda créditos: {item['nombre']}")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('UPDATE tienda_creditos SET stock = stock - 1 WHERE id = ?', (item_id,))
    conn.commit()
    conn.close()
    db_helper.agregar_item(user_id, item["nombre"], 1)
    return True, f"✅ Compraste {item['nombre']} por {precio} créditos."

def vender_item(user_id: int, item_nombre: str, cantidad: int) -> Tuple[bool, str]:
    for item in CATALOGO_ORO + CATALOGO_ETERNIUM:
        if item["nombre"] == item_nombre:
            precio_oro = item.get("precio_venta_oro", 0)
            precio_et = item.get("precio_venta_eternium", 0)
            if precio_oro == 0 and precio_et == 0:
                return False, "La tienda no compra este objeto."
            inv = db_helper.obtener_inventario(user_id)
            for it in inv:
                if it["nombre"] == item_nombre and it["cantidad"] >= cantidad:
                    break
            else:
                return False, f"No tienes {cantidad}x {item_nombre}."
            db_helper.quitar_item(user_id, item_nombre, cantidad)
            if precio_oro > 0:
                economia.modificar_saldo(user_id, "oro", precio_oro * cantidad, f"venta de {item_nombre}")
            if precio_et > 0:
                economia.modificar_saldo(user_id, "eternium", precio_et * cantidad, f"venta de {item_nombre}")
            return True, f"Vendiste {cantidad}x {item_nombre}."
    return False, "No se pudo vender el objeto."

# ==================== INTERFAZ DE USUARIO ====================
ITEMS_POR_PAGINA = 8

RAREZA_EMOJI = {1:"⚪",2:"🟢",3:"🔵",4:"🟣",5:"🟠",6:"🔴",7:"⭐",8:"💫",9:"✨",10:"👑",11:"🌟",12:"💎"}
RAREZA_NOMBRE = {
    1:"Común", 2:"Poco común", 3:"Raro", 4:"Épico", 5:"Legendario",
    6:"Mítico", 7:"Divino", 8:"Cósmico", 9:"Sublime", 10:"Celestial",
    11:"Ancestral", 12:"Trascendente"
}
MONEDA_EMOJI = {"oro":"🪙", "eternium":"💎", "creditos":"✨"}

# Índice de sets de armaduras (nombre_base -> lista de piezas)
_SET_INDEX: Dict[str, List[Dict]] = {}

def _construir_set_index():
    import re as _re
    for arm in ARMADURAS.values():
        m = _re.match(r'^(.+?) \(', arm.get("nombre", ""))
        if m:
            base = m.group(1)
            _SET_INDEX.setdefault(base, []).append(arm)

_construir_set_index()

def paginar_items(items: List[Dict], page: int) -> Tuple[List[Dict], int]:
    total = len(items)
    start = page * ITEMS_POR_PAGINA
    end = start + ITEMS_POR_PAGINA
    return items[start:end], total

def _buscar_item_en_datos(item_id: str) -> Dict:
    return ARMAS.get(item_id) or ARMADURAS.get(item_id) or POCIONES.get(item_id) or MONTURAS.get(item_id) or {}

def _nombre_material(mat_id: str) -> str:
    if mat_id in _MATERIALES_DATA:
        return _MATERIALES_DATA[mat_id].get("nombre", mat_id)
    for entry in _MATERIALES_DATA.values():
        if entry.get("id") == mat_id:
            return entry.get("nombre", mat_id)
    return mat_id

_TIPO_EMOJI_REC = {"arma": "⚔️", "armadura": "🛡️", "pocion": "🧪"}

def _texto_detalle_receta(receta_id: str, receta: dict, precio: int, tiene: bool) -> str:
    tipo = receta.get("tipo", "?")
    nombre = _esc(receta.get("nombre", "?"))
    clase_raw = receta.get("clase_requerida") or "Todas las clases"
    clase_txt = _esc(clase_raw.replace("_", " ").capitalize())
    zona = _esc(receta.get("zona_crafteo", "?").capitalize())
    nivel = receta.get("nivel_requerido", 1)
    emoji = _TIPO_EMOJI_REC.get(tipo, "📜")
    lineas = [
        f"{emoji} *{nombre}*",
        f"📦 Tipo: *{tipo.capitalize()}*  •  🌐 Zona crafteo: *{zona}*",
        f"🏰 Clase: *{clase_txt}*  •  🎯 Nivel mín: *{nivel}*",
    ]
    datos = _buscar_item_en_datos(receta_id)
    if datos:
        if tipo == "arma":
            lineas += [
                "",
                "*Stats del arma crafteada:*",
                f"⚔️ Daño: *{datos.get('daño', 0)}*",
                f"🎯 Crítico: *{datos.get('critico', 0)}*",
                f"⚡ Velocidad: *{datos.get('velocidad', 0)}*",
            ]
            if datos.get("vida_extra", 0):
                lineas.append(f"❤️ Vida extra: *{datos['vida_extra']}*")
            if datos.get("defensa_extra", 0):
                lineas.append(f"🛡️ Defensa extra: *{datos['defensa_extra']}*")
        elif tipo == "armadura":
            lineas += [
                "",
                "*Stats de la armadura crafteada:*",
                f"🛡️ Defensa: *{datos.get('defensa', 0)}*",
                f"🎯 Resist. crítico: *{datos.get('resistencia_critico', 0)}*",
                f"🏃 Velocidad mov.: *{datos.get('velocidad_movimiento', 0)}*",
            ]
            if datos.get("vida_extra", 0):
                lineas.append(f"❤️ Vida extra: *{datos['vida_extra']}*")
        elif tipo == "pocion":
            efecto = _esc(str(datos.get("efecto", datos.get("descripcion", ""))))
            if efecto:
                lineas += ["", f"✨ Efecto: {efecto}"]
    materiales_d = receta.get("materiales", {})
    if materiales_d:
        lineas += ["", "*Materiales necesarios:*"]
        for mat_id, cantidad in materiales_d.items():
            lineas.append(f"  • {_esc(_nombre_material(mat_id))}: *{cantidad}*")
    tiempo = receta.get("tiempo_segundos", 0)
    if tiempo and tiempo > 0:
        mins, secs = divmod(int(tiempo), 60)
        t_txt = f"{mins}m {secs}s" if mins else f"{secs}s"
        lineas.append(f"\n⏱️ Tiempo de crafteo: *{t_txt}*")
    if tiene:
        lineas.append("\n✅ *Ya tienes esta receta aprendida*")
    else:
        lineas.append(f"\n🏷️ Precio de la receta: *{precio} 🪙*")
    return "\n".join(lineas)

def _texto_detalle_arma(a: Dict, precio: int, moneda: str) -> str:
    rar = a.get("rareza", 1)
    clase = _esc((a.get("clase_requerida") or "Todas las clases").replace("_", " ").capitalize())
    zona = _esc(a.get("zona", "?").capitalize())
    nombre = _esc(a.get("nombre", "?"))
    descripcion = _esc(a.get("descripcion", "Sin descripción."))
    lineas = [
        f"⚔️ *{nombre}*",
        f"{RAREZA_EMOJI.get(rar,'⚪')} *{RAREZA_NOMBRE.get(rar,f'Rareza {rar}')}*  •  Nivel mín: *{a.get('nivel_requerido',1)}*",
        f"🏰 Clase: *{clase}*  •  🌐 Zona: *{zona}*",
        "",
        "*Estadísticas:*",
        f"⚔️ Daño: *{a.get('daño',0)}*",
        f"🎯 Crítico: *{a.get('critico',0)}*",
        f"⚡ Velocidad: *{a.get('velocidad',0)}*",
    ]
    if a.get("vida_extra", 0):
        lineas.append(f"❤️ Vida extra: *{a['vida_extra']}*")
    if a.get("defensa_extra", 0):
        lineas.append(f"🛡️ Defensa extra: *{a['defensa_extra']}*")
    lineas.append(f"⚖️ Peso: *{a.get('peso', 0)} kg*")
    lineas += ["", f"📝 {descripcion}", "",
               f"🏷️ Precio: *{precio} {MONEDA_EMOJI.get(moneda, moneda)}*"]
    return "\n".join(lineas)

def _texto_detalle_armadura(a: Dict, precio: int, moneda: str) -> str:
    import re as _re
    rar = a.get("rareza", 1)
    clase = _esc((a.get("clase_requerida") or "Todas las clases").replace("_", " ").capitalize())
    zona = _esc(a.get("zona", "?").capitalize())
    nombre = _esc(a.get("nombre", "?"))
    descripcion = _esc(a.get("descripcion", "Sin descripción."))
    m = _re.match(r'^(.+?) \(', a.get("nombre", ""))
    set_nombre_raw = m.group(1) if m else a.get("nombre", "")
    set_nombre = _esc(set_nombre_raw)
    lineas = [
        f"🛡️ *{nombre}*",
        f"{RAREZA_EMOJI.get(rar,'⚪')} *{RAREZA_NOMBRE.get(rar,f'Rareza {rar}')}*  •  Nivel mín: *{a.get('nivel_requerido',1)}*",
        f"🏰 Clase: *{clase}*  •  🌐 Zona: *{zona}*",
        "",
        "*Estadísticas:*",
        f"🛡️ Defensa: *{a.get('defensa',0)}*",
        f"🎯 Resistencia crítico: *{a.get('resistencia_critico',0)}*",
        f"🏃 Velocidad de movimiento: *{a.get('velocidad_movimiento',0)}*",
    ]
    if a.get("vida_extra", 0):
        lineas.append(f"❤️ Vida extra: *{a['vida_extra']}*")
    if a.get("defensa_extra", 0):
        lineas.append(f"🛡️ Defensa extra: *{a['defensa_extra']}*")
    lineas.append(f"⚖️ Peso: *{a.get('peso', 0)} kg*")
    if a.get("habilidad_pasiva"):
        lineas.append(f"🔮 Pasiva: _{_esc(a['habilidad_pasiva'])}_")
    if a.get("habilidad_activa"):
        lineas.append(f"⚡ Activa: _{_esc(a['habilidad_activa'])}_")
    piezas = [p for p in _SET_INDEX.get(set_nombre_raw, []) if p.get("nombre") != a.get("nombre")]
    if piezas:
        lineas += ["", f"*Set: {set_nombre}*"]
        for p in sorted(piezas[:8], key=lambda x: x.get("tipo", "")):
            lineas.append(f"  • {_esc(p['nombre'])}  Def:{p.get('defensa',0)}  Nv:{p.get('nivel_requerido',1)}")
    lineas += ["", f"📝 {descripcion}", "",
               f"🏷️ Precio: *{precio} {MONEDA_EMOJI.get(moneda, moneda)}*"]
    return "\n".join(lineas)

def _texto_detalle_pocion(a: Dict, precio: int, moneda: str) -> str:
    rar = a.get("rareza", 1)
    nombre = _esc(a.get("nombre", "?"))
    zona = _esc(a.get("zona", "?").capitalize())
    calidad = _esc(a.get("calidad", "?").capitalize())
    efecto = _esc(a.get("efecto", "?"))
    descripcion = _esc(a.get("descripcion", "Sin descripción."))
    lineas = [
        f"🧪 *{nombre}*",
        f"{RAREZA_EMOJI.get(rar,'⚪')} *{RAREZA_NOMBRE.get(rar,f'Rareza {rar}')}*  •  Nivel mín: *{a.get('nivel_requerido',1)}*",
        f"🌐 Zona: *{zona}*  •  Calidad: *{calidad}*",
        "",
        "*Efecto:*",
        f"✨ {efecto}",
        "",
        f"📝 {descripcion}",
        "",
        f"🏷️ Precio: *{precio} {MONEDA_EMOJI.get(moneda, moneda)}*",
    ]
    return "\n".join(lineas)

def _texto_detalle_montura(a: Dict, precio: int, moneda: str) -> str:
    rar = a.get("rareza", 1)
    nombre = _esc(a.get("nombre", "?"))
    zona = _esc(a.get("zona", "?").capitalize())
    subtipo = _esc(a.get("subtipo", "?").capitalize())
    descripcion = _esc(a.get("descripcion", "Sin descripción."))
    lineas = [
        f"🐎 *{nombre}*",
        f"{RAREZA_EMOJI.get(rar,'⚪')} *{RAREZA_NOMBRE.get(rar,f'Rareza {rar}')}*  •  Nivel mín: *{a.get('nivel_requerido',1)}*",
        f"🌐 Zona: *{zona}*  •  Tipo: *{subtipo}*",
        "",
        "*Estadísticas:*",
        f"🚀 Velocidad: *+{a.get('velocidad',0)}%*",
        f"📦 Carga extra: *+{a.get('carga',0)}*",
        f"🌑 Sigilo: *+{a.get('sigilo',0)}*",
        f"🛡️ Defensa: *+{a.get('defensa',0)}*",
        f"⚔️ Ataque: *+{a.get('ataque',0)}*",
        "",
        f"📝 {descripcion}",
        "",
        f"🏷️ Precio: *{precio} {MONEDA_EMOJI.get(moneda, moneda)}*",
    ]
    return "\n".join(lineas)

async def listar_items(update, context, items, titulo, callback_prefix, moneda, volver_callback="tienda_volver"):
    query = update.callback_query
    await query.answer()
    if not items:
        await query.edit_message_text(f"*{titulo}*\n\nNo hay objetos en esta categoría.", parse_mode="Markdown")
        return
    page_key = f"{callback_prefix}_page"
    page = context.user_data.get(page_key, 0)
    paginated, total = paginar_items(items, page)
    paginas_total = max(1, (total + ITEMS_POR_PAGINA - 1) // ITEMS_POR_PAGINA)
    context.user_data["tienda_lista_ctx"] = {
        "items_ids": [i["id"] for i in items],
        "titulo": titulo,
        "callback_prefix": callback_prefix,
        "moneda": moneda,
        "volver_callback": volver_callback,
    }
    texto = f"*{titulo}*\nPágina {page+1}/{paginas_total}\n_Pulsa un objeto para ver sus estadísticas y comprarlo._"
    botones = []
    moneda_e = MONEDA_EMOJI.get(moneda, moneda)
    for item in paginated:
        rar_e = RAREZA_EMOJI.get(item.get("rareza", 1), "⚪")
        precio = item.get(f"precio_{moneda}", 0)
        btn = f"{rar_e} {item['nombre']} — {precio} {moneda_e}"
        if len(btn) > 62:
            btn = btn[:59] + "..."
        botones.append([InlineKeyboardButton(btn, callback_data=f"tdet_{item['id']}")])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀ Anterior", callback_data=f"{callback_prefix}_prev"))
    if (page + 1) * ITEMS_POR_PAGINA < total:
        nav.append(InlineKeyboardButton("Siguiente ▶", callback_data=f"{callback_prefix}_next"))
    if nav:
        botones.append(nav)
    botones.append([InlineKeyboardButton("🔙 Volver", callback_data=volver_callback)])
    await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(botones), parse_mode="Markdown")

async def tienda_detalle_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    item_id = query.data[len("tdet_"):]
    item_cat = None
    moneda = "oro"
    for it in CATALOGO_ORO:
        if it["id"] == item_id:
            item_cat = it
            moneda = "oro"
            break
    if not item_cat:
        for it in CATALOGO_ETERNIUM:
            if it["id"] == item_id:
                item_cat = it
                moneda = "eternium"
                break
    if not item_cat:
        await query.edit_message_text("❌ Objeto no encontrado en el catálogo.")
        return
    precio = item_cat.get(f"precio_{moneda}", 0)
    datos = _buscar_item_en_datos(item_id)
    merged = {**datos, **item_cat} if datos else dict(item_cat)
    tipo = merged.get("tipo")
    if tipo == "arma":
        texto = _texto_detalle_arma(merged, precio, moneda)
    elif tipo == "armadura":
        texto = _texto_detalle_armadura(merged, precio, moneda)
    elif tipo == "pocion":
        texto = _texto_detalle_pocion(merged, precio, moneda)
    elif tipo == "montura":
        texto = _texto_detalle_montura(merged, precio, moneda)
    else:
        texto = (
            f"📦 *{_esc(merged['nombre'])}*\n\n"
            f"_{_esc(merged.get('descripcion',''))}_\n\n"
            f"{_esc(merged.get('efecto',''))}\n\n"
            f"🏷️ Precio: *{precio} {MONEDA_EMOJI.get(moneda, moneda)}*"
        )
    botones = [
        [InlineKeyboardButton(f"🛒 Comprar", callback_data=f"comprar_{moneda}_{item_id}")],
        [InlineKeyboardButton("🔙 Volver a la lista", callback_data="tdetv")],
    ]
    try:
        await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(botones), parse_mode="Markdown")
    except Exception as e:
        logger.error(f"tienda_detalle_handler edit error [{item_id}]: {e}", exc_info=True)
        try:
            texto_plain = texto.replace("*", "").replace("_", "").replace("\\", "")
            await query.edit_message_text(texto_plain, reply_markup=InlineKeyboardMarkup(botones))
        except Exception as e2:
            logger.error(f"tienda_detalle_handler fallback error [{item_id}]: {e2}")

async def tienda_detalle_credito_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    db_id = int(query.data[len("tdetcr_"):])
    rotacion = obtener_rotacion_creditos()
    item = next((r for r in rotacion if r["id"] == db_id), None)
    if not item:
        await query.edit_message_text("Este objeto ya no está disponible.")
        return
    precio = item.get("precio_creditos", 0)
    obj_id = item.get("objeto_id", "")
    datos = _buscar_item_en_datos(obj_id) if obj_id else {}
    tipo = item.get("tipo")
    if tipo == "arma" and datos:
        texto = _texto_detalle_arma({**datos, "nombre": item["nombre"]}, precio, "creditos")
    elif tipo == "armadura" and datos:
        texto = _texto_detalle_armadura({**datos, "nombre": item["nombre"]}, precio, "creditos")
    elif tipo == "pocion" and datos:
        texto = _texto_detalle_pocion({**datos, "nombre": item["nombre"]}, precio, "creditos")
    elif tipo == "montura" and datos:
        texto = _texto_detalle_montura({**datos, "nombre": item["nombre"]}, precio, "creditos")
    else:
        texto = (
            f"📦 *{_esc(item['nombre'])}*\n\n"
            f"_{_esc(item.get('descripcion',''))}_\n\n"
            f"{_esc(item.get('efecto',''))}\n\n"
            f"✨ Precio: *{precio} ✨*\n"
            f"📦 Stock: *{item.get('stock', 0)}*"
        )
    botones = [
        [InlineKeyboardButton(f"✨ Comprar ({precio} ✨)", callback_data=f"comprar_credito_{db_id}")],
        [InlineKeyboardButton("🔙 Volver", callback_data="tienda_creditos")],
    ]
    try:
        await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(botones), parse_mode="Markdown")
    except Exception as e:
        logger.error(f"tienda_detalle_credito_handler edit error: {e}", exc_info=True)
        try:
            texto_plain = texto.replace("*", "").replace("_", "").replace("\\", "")
            await query.edit_message_text(texto_plain, reply_markup=InlineKeyboardMarkup(botones))
        except Exception as e2:
            logger.error(f"tienda_detalle_credito_handler fallback error: {e2}")

async def tvolver_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ctx = context.user_data.get("tienda_lista_ctx")
    if not ctx:
        await tienda_volver(update, context)
        return
    ids_set = set(ctx["items_ids"])
    all_items = CATALOGO_ORO + CATALOGO_ETERNIUM
    items = [i for i in all_items if i["id"] in ids_set]
    id_order = {iid: idx for idx, iid in enumerate(ctx["items_ids"])}
    items.sort(key=lambda x: id_order.get(x["id"], 9999))
    if not items:
        await tienda_volver(update, context)
        return
    await listar_items(update, context, items, ctx["titulo"], ctx["callback_prefix"], ctx["moneda"], ctx["volver_callback"])

# -------------------- Menús principales --------------------
TEXTO_TIENDA = (
    "🏪 *Tienda de Aethelgard*\n\n"
    "🪙 Oro: objetos básicos (compra/venta)\n"
    "💎 Eternium: objetos de élite (compra/venta)\n"
    "✨ Créditos: objetos exclusivos (solo compra, stock limitado, rotación semanal)\n"
)

KEYBOARD_TIENDA = [
    [InlineKeyboardButton("🪙 Catálogo de Oro", callback_data="tienda_oro")],
    [InlineKeyboardButton("💎 Catálogo de Eternium", callback_data="tienda_eternium")],
    [InlineKeyboardButton("✨ Catálogo de Créditos", callback_data="tienda_creditos")],
    [InlineKeyboardButton("🛒 Vender objetos", callback_data="tienda_vender")],
    [InlineKeyboardButton("❌ Cerrar", callback_data="tienda_cerrar")]
]

async def cmd_tienda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    msg = update.effective_message
    if db_helper.esta_marcado(user_id):
        await msg.reply_text("❌ Estás marcado. No puedes usar la tienda hasta que pagues rescate.")
        return
    try:
        from guerra_facciones import check_lockdown
        if await check_lockdown(update):
            return
    except Exception:
        pass
    if not _en_ciudad(user_id):
        await msg.reply_text("🏙️ La tienda solo está disponible dentro de las ciudades. Vuelve a la ciudad para usarla.")
        return
    await msg.reply_text(
        TEXTO_TIENDA,
        reply_markup=InlineKeyboardMarkup(KEYBOARD_TIENDA),
        parse_mode="Markdown"
    )
    try:
        import misiones as _mis
        _mis.completar_mision(user_id, "visitar_tienda", context)
    except Exception:
        pass

# -------------------- Catálogo Oro --------------------
async def tienda_oro_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("🛡️ Objetos comunes", callback_data="oro_comunes")],
        [InlineKeyboardButton("⚔️ Armas por clase", callback_data="oro_armas_clase")],
        [InlineKeyboardButton("🛡️ Armaduras por clase", callback_data="oro_armaduras_clase")],
        [InlineKeyboardButton("🐎 Monturas", callback_data="oro_monturas")],
        [InlineKeyboardButton("🧪 Pociones", callback_data="oro_pociones")],
        [InlineKeyboardButton("📜 Recetas de crafteo", callback_data="oro_recetas")],
        [InlineKeyboardButton("🔙 Volver", callback_data="tienda_volver")]
    ]
    await query.edit_message_text("🪙 *Catálogo de Oro*\nElige categoría:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def oro_armas_clase_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("🛡️ Vanguardista", callback_data="oro_armas_vanguardista")],
        [InlineKeyboardButton("🗡️ Acechante", callback_data="oro_armas_acechante")],
        [InlineKeyboardButton("🔮 Tejehechizos", callback_data="oro_armas_tejehechizos")],
        [InlineKeyboardButton("🏹 Maestro Caza", callback_data="oro_armas_maestro_caza")],
        [InlineKeyboardButton("🔙 Volver", callback_data="tienda_oro")]
    ]
    await query.edit_message_text("Selecciona una clase para ver sus armas:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def oro_armaduras_clase_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("🛡️ Vanguardista", callback_data="oro_armaduras_vanguardista")],
        [InlineKeyboardButton("🗡️ Acechante", callback_data="oro_armaduras_acechante")],
        [InlineKeyboardButton("🔮 Tejehechizos", callback_data="oro_armaduras_tejehechizos")],
        [InlineKeyboardButton("🏹 Maestro Caza", callback_data="oro_armaduras_maestro_caza")],
        [InlineKeyboardButton("🔙 Volver", callback_data="tienda_oro")]
    ]
    await query.edit_message_text("Selecciona una clase para ver sus armaduras:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def oro_comunes(update: Update, context):
    uid = update.effective_user.id
    base = [i for i in CATALOGO_ORO if i.get("clase") is None]
    items = _filtrar_items_jugador(base, uid)
    await listar_items(update, context, items, "🧰 Objetos comunes", "oro_comunes", "oro", "tienda_oro")

async def oro_armas_por_clase(update: Update, context, clase: str):
    uid = update.effective_user.id
    base = [i for i in CATALOGO_ORO if i["tipo"] == "arma" and i.get("clase") == clase]
    items = _filtrar_items_jugador(base, uid)
    await listar_items(update, context, items, f"⚔️ Armas de {clase.capitalize()}", f"oro_armas_{clase}", "oro", "tienda_oro")

async def oro_armaduras_por_clase(update: Update, context, clase: str):
    uid = update.effective_user.id
    base = [i for i in CATALOGO_ORO if i["tipo"] == "armadura" and i.get("clase") == clase]
    items = _filtrar_items_jugador(base, uid)
    await listar_items(update, context, items, f"🛡️ Armaduras de {clase.capitalize()}", f"oro_armaduras_{clase}", "oro", "tienda_oro")

async def oro_monturas(update: Update, context):
    uid = update.effective_user.id
    base = [i for i in CATALOGO_ORO if i["tipo"] == "montura"]
    items = _filtrar_items_jugador(base, uid)
    await listar_items(update, context, items, "🐎 Monturas", "oro_monturas", "oro", "tienda_oro")

async def oro_pociones(update: Update, context):
    uid = update.effective_user.id
    base = [i for i in CATALOGO_ORO if i["tipo"] == "pocion"]
    items = _filtrar_items_jugador(base, uid)
    await listar_items(update, context, items, "🧪 Pociones", "oro_pociones", "oro", "tienda_oro")

# -------------------- Catálogo Eternium --------------------
async def tienda_eternium_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("🛡️ Objetos comunes", callback_data="et_comunes")],
        [InlineKeyboardButton("⚔️ Armas por clase", callback_data="et_armas_clase")],
        [InlineKeyboardButton("🛡️ Armaduras por clase", callback_data="et_armaduras_clase")],
        [InlineKeyboardButton("🐎 Monturas", callback_data="et_monturas")],
        [InlineKeyboardButton("🧪 Pociones", callback_data="et_pociones")],
        [InlineKeyboardButton("🔙 Volver", callback_data="tienda_volver")]
    ]
    await query.edit_message_text("💎 *Catálogo de Eternium*\nElige categoría:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def et_armas_clase_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("🛡️ Vanguardista", callback_data="et_armas_vanguardista")],
        [InlineKeyboardButton("🗡️ Acechante", callback_data="et_armas_acechante")],
        [InlineKeyboardButton("🔮 Tejehechizos", callback_data="et_armas_tejehechizos")],
        [InlineKeyboardButton("🏹 Maestro Caza", callback_data="et_armas_maestro_caza")],
        [InlineKeyboardButton("🔙 Volver", callback_data="tienda_eternium")]
    ]
    await query.edit_message_text("Selecciona una clase para ver sus armas élite:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def et_armaduras_clase_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("🛡️ Vanguardista", callback_data="et_armaduras_vanguardista")],
        [InlineKeyboardButton("🗡️ Acechante", callback_data="et_armaduras_acechante")],
        [InlineKeyboardButton("🔮 Tejehechizos", callback_data="et_armaduras_tejehechizos")],
        [InlineKeyboardButton("🏹 Maestro Caza", callback_data="et_armaduras_maestro_caza")],
        [InlineKeyboardButton("🔙 Volver", callback_data="tienda_eternium")]
    ]
    await query.edit_message_text("Selecciona una clase para ver sus armaduras élite:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def et_comunes(update: Update, context):
    uid = update.effective_user.id
    base = [i for i in CATALOGO_ETERNIUM if i.get("clase") is None]
    items = _filtrar_items_jugador(base, uid)
    await listar_items(update, context, items, "💎 Objetos comunes", "et_comunes", "eternium", "tienda_eternium")

async def et_armas_por_clase(update: Update, context, clase: str):
    uid = update.effective_user.id
    base = [i for i in CATALOGO_ETERNIUM if i["tipo"] == "arma" and i.get("clase") == clase]
    items = _filtrar_items_jugador(base, uid)
    await listar_items(update, context, items, f"⚔️ Armas élite de {clase.capitalize()}", f"et_armas_{clase}", "eternium", "tienda_eternium")

async def et_armaduras_por_clase(update: Update, context, clase: str):
    uid = update.effective_user.id
    base = [i for i in CATALOGO_ETERNIUM if i["tipo"] == "armadura" and i.get("clase") == clase]
    items = _filtrar_items_jugador(base, uid)
    await listar_items(update, context, items, f"🛡️ Armaduras élite de {clase.capitalize()}", f"et_armaduras_{clase}", "eternium", "tienda_eternium")

async def et_monturas(update: Update, context):
    uid = update.effective_user.id
    base = [i for i in CATALOGO_ETERNIUM if i["tipo"] == "montura"]
    items = _filtrar_items_jugador(base, uid)
    await listar_items(update, context, items, "🐎 Monturas élite", "et_monturas", "eternium", "tienda_eternium")

async def et_pociones(update: Update, context):
    uid = update.effective_user.id
    base = [i for i in CATALOGO_ETERNIUM if i["tipo"] == "pocion"]
    items = _filtrar_items_jugador(base, uid)
    await listar_items(update, context, items, "🧪 Pociones élite", "et_pociones", "eternium", "tienda_eternium")

# -------------------- Catálogo Créditos --------------------
async def tienda_creditos_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    rotacion = obtener_rotacion_creditos()
    if not rotacion:
        generar_rotacion_creditos()
        rotacion = obtener_rotacion_creditos()
    if not rotacion:
        await query.edit_message_text("✨ *Catálogo de Créditos*\n\nNo hay objetos en rotación ahora mismo.", parse_mode="Markdown")
        return
    texto = "✨ *Catálogo de Créditos*\n_Rotación semanal — stock limitado_\n\n_Pulsa un objeto para ver sus estadísticas._"
    botones = []
    uid_cred = update.effective_user.id
    jug_cred = db_helper.obtener_jugador(uid_cred)
    nivel_cred = jug_cred.get("nivel", 1) if jug_cred else 1
    max_idx_cred = _color_max_idx(nivel_cred)
    for item in rotacion:
        obj_id = item.get("objeto_id", "")
        datos_raw = _buscar_item_en_datos(obj_id) if obj_id else {}
        if datos_raw.get("nivel_requerido", 1) > nivel_cred:
            continue
        zona_item = datos_raw.get("zona", "azul")
        if _COLOR_INDICE_TIENDA.get(zona_item, 1) > max_idx_cred:
            continue
        rar = datos_raw.get("rareza", 1)
        rar_e = RAREZA_EMOJI.get(rar, "⚪")
        btn = f"{rar_e} {item['nombre']} — {item['precio_creditos']} 💎 (x{item['stock']})"
        if len(btn) > 62:
            btn = btn[:59] + "..."
        botones.append([InlineKeyboardButton(btn, callback_data=f"tdetcr_{item['id']}")])
    botones.append([InlineKeyboardButton("🔙 Volver", callback_data="tienda_volver")])
    await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(botones), parse_mode="Markdown")

# -------------------- Venta de objetos --------------------
async def tienda_vender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    inv = db_helper.obtener_inventario(user_id)
    if not inv:
        await query.edit_message_text("Tu inventario está vacío.")
        return
    texto = "🛒 *Vender objetos a la tienda*\n(Recibirás Oro o Eternium)\n\n"
    botones = []
    for item in inv:
        for cat_item in CATALOGO_ORO + CATALOGO_ETERNIUM:
            if cat_item["nombre"] == item["nombre"] and (cat_item.get("precio_venta_oro", 0) > 0 or cat_item.get("precio_venta_eternium", 0) > 0):
                texto += f"• {item['nombre']} x{item['cantidad']} → "
                if cat_item.get("precio_venta_oro", 0) > 0:
                    texto += f"{cat_item['precio_venta_oro']} oro"
                if cat_item.get("precio_venta_eternium", 0) > 0:
                    texto += f" {cat_item['precio_venta_eternium']} eternium"
                texto += "\n"
                botones.append([InlineKeyboardButton(f"Vender {item['nombre']}", callback_data=f"vender_{item['nombre']}")])
                break
    if not botones:
        await query.edit_message_text("No tienes objetos que la tienda quiera comprar.")
        return
    botones.append([InlineKeyboardButton("🔙 Volver", callback_data="tienda_volver")])
    await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(botones), parse_mode="Markdown")

async def vender_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    item_nombre = query.data.split("_", 1)[1]
    user_id = update.effective_user.id
    inv = db_helper.obtener_inventario(user_id)
    for it in inv:
        if it["nombre"] == item_nombre:
            cantidad = it["cantidad"]
            break
    else:
        await query.edit_message_text("Ya no tienes ese objeto.")
        return
    ok, msg = vender_item(user_id, item_nombre, cantidad)
    await query.edit_message_text(msg)
    await tienda_vender(update, context)

# -------------------- Handlers de compra --------------------
async def comprar_oro_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        item_id = query.data.split("_", 2)[2]
    except IndexError:
        await query.edit_message_text("❌ Error al procesar la compra.")
        return
    ok, msg = comprar_oro(update.effective_user.id, item_id)
    await query.edit_message_text(msg)

async def comprar_eternium_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        item_id = query.data.split("_", 2)[2]
    except IndexError:
        await query.edit_message_text("❌ Error al procesar la compra.")
        return
    ok, msg = comprar_eternium(update.effective_user.id, item_id)
    await query.edit_message_text(msg)

async def comprar_credito_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        item_id = int(query.data.split("_", 2)[2])
    except (ValueError, IndexError):
        await query.edit_message_text("❌ Error al procesar la compra.")
        return
    ok, msg = comprar_credito(update.effective_user.id, item_id)
    await query.edit_message_text(msg)

# -------------------- Navegación y paginación --------------------
async def tienda_volver(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        TEXTO_TIENDA,
        reply_markup=InlineKeyboardMarkup(KEYBOARD_TIENDA),
        parse_mode="Markdown"
    )

async def tienda_cerrar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("🏪 Tienda cerrada. ¡Vuelve pronto!")

def crear_paginador(key_prefix, list_func):
    async def paginador(update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        delta = 1 if "next" in query.data else -1
        page_key = f"{key_prefix}_page"
        page = context.user_data.get(page_key, 0) + delta
        context.user_data[page_key] = max(0, page)
        await list_func(update, context)
    return paginador


# ==================== TIENDA DE RECETAS ====================
def _precio_receta(receta: dict) -> int:
    """Precio en oro basado en nivel requerido y zonas de materiales."""
    base = max(150, receta["nivel_requerido"] * 50)
    zonas = receta.get("zona_materiales", [])
    if "negra" in zonas:
        base = int(base * 2.5)
    elif "roja" in zonas:
        base = int(base * 1.8)
    elif "amarilla" in zonas:
        base = int(base * 1.3)
    return base

def _jugador_tiene_receta(user_id: int, receta_id: str) -> bool:
    import sqlite3 as _s
    conn = _s.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT 1 FROM recetas_jugador WHERE user_id=? AND receta_id=?", (user_id, receta_id))
    tiene = c.fetchone() is not None
    conn.close()
    return tiene

def _registrar_receta_jugador(user_id: int, receta_id: str):
    import sqlite3 as _s
    conn = _s.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO recetas_jugador (user_id, receta_id) VALUES (?,?)", (user_id, receta_id))
    conn.commit()
    conn.close()

ITEMS_RECETA_POR_PAG = 5

async def _listar_recetas(update, context, recetas_lista: list, titulo: str, key: str, volver_cb: str, lista_cb: str = "oro_recetas"):
    """Muestra lista paginada de recetas — cada receta es un botón que abre el detalle."""
    query = update.callback_query
    if query:
        await query.answer()
    context.user_data["rdet_volver_cb"] = lista_cb
    pagina = context.user_data.get(f"rec_pag_{key}", 0)
    total = len(recetas_lista)
    if total == 0:
        await query.edit_message_text(f"*{titulo}*\n\nNo hay recetas en esta categoría.", parse_mode="Markdown")
        return
    start = pagina * ITEMS_RECETA_POR_PAG
    end = min(start + ITEMS_RECETA_POR_PAG, total)
    sublist = recetas_lista[start:end]
    user_id = update.effective_user.id
    paginas_total = max(1, (total + ITEMS_RECETA_POR_PAG - 1) // ITEMS_RECETA_POR_PAG)
    texto = f"*{titulo}*\nPágina {pagina+1}/{paginas_total}\n_Pulsa una receta para ver sus detalles y comprarla._"
    botones = []
    for rid, rec in sublist:
        precio = _precio_receta(rec)
        tiene = _jugador_tiene_receta(user_id, rid)
        emoji = _TIPO_EMOJI_REC.get(rec.get("tipo", ""), "📜")
        if tiene:
            label = f"✅ {rec['nombre']}"
        else:
            label = f"{emoji} {rec['nombre']} — {precio}🪙"
        if len(label) > 62:
            label = label[:59] + "..."
        botones.append([InlineKeyboardButton(label, callback_data=f"rdet_{rid}")])
    nav = []
    if pagina > 0:
        nav.append(InlineKeyboardButton("◀ Anterior", callback_data=f"recpag_{key}_prev"))
    if end < total:
        nav.append(InlineKeyboardButton("Siguiente ▶", callback_data=f"recpag_{key}_next"))
    if nav:
        botones.append(nav)
    botones.append([InlineKeyboardButton("🔙 Volver", callback_data=volver_cb)])
    await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(botones), parse_mode="Markdown")

async def tienda_recetas_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("⚔️ Recetas de Armas", callback_data="rec_armas")],
        [InlineKeyboardButton("🛡️ Recetas de Armaduras", callback_data="rec_armaduras_menu")],
        [InlineKeyboardButton("🧪 Recetas de Pociones", callback_data="rec_pociones")],
        [InlineKeyboardButton("🔙 Volver", callback_data="tienda_oro")]
    ]
    await query.edit_message_text(
        "📜 *Recetas de Crafteo*\n\nCompra recetas para aprender a fabricar equipamiento.\nUna vez comprada, podrás usarla en el taller de crafteo.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def recetas_armas_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id
    base = [(rid, r) for rid, r in RECETAS.items() if r["tipo"] == "arma"]
    lista = sorted(_filtrar_recetas_lista(base, uid), key=lambda x: x[1]["nivel_requerido"])
    await _listar_recetas(update, context, lista, "⚔️ Recetas de Armas", "armas", "oro_recetas", lista_cb="rec_armas")

async def recetas_armaduras_menu_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("🛡️ Vanguardista", callback_data="rec_arm_vanguardista")],
        [InlineKeyboardButton("🗡️ Acechante", callback_data="rec_arm_acechante")],
        [InlineKeyboardButton("🔮 Tejehechizos", callback_data="rec_arm_tejehechizos")],
        [InlineKeyboardButton("🏹 Maestro Caza", callback_data="rec_arm_maestro_caza")],
        [InlineKeyboardButton("🔓 Sin restricción de clase", callback_data="rec_arm_comun")],
        [InlineKeyboardButton("🔙 Volver", callback_data="oro_recetas")]
    ]
    await query.edit_message_text("🛡️ *Recetas de Armaduras*\nSelecciona categoría:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def recetas_armaduras_por_clase_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    partes = query.data.split("_", 2)
    clase = partes[2] if len(partes) > 2 else ""
    if clase == "comun":
        uid = update.effective_user.id
        base = [(rid, r) for rid, r in RECETAS.items() if r["tipo"] == "armadura" and not r.get("clase_requerida")]
        lista = sorted(_filtrar_recetas_lista(base, uid), key=lambda x: x[1]["nivel_requerido"])
        titulo = "🔓 Armaduras sin restricción"
    else:
        uid = update.effective_user.id
        base = [(rid, r) for rid, r in RECETAS.items() if r["tipo"] == "armadura" and r.get("clase_requerida") == clase]
        lista = sorted(_filtrar_recetas_lista(base, uid), key=lambda x: x[1]["nivel_requerido"])
        titulo = f"🛡️ Armaduras de {clase.replace('_', ' ').capitalize()}"
    await _listar_recetas(update, context, lista, titulo, f"arm_{clase}", "rec_armaduras_menu", lista_cb=f"rec_arm_{clase}")

async def recetas_pociones_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id
    base = [(rid, r) for rid, r in RECETAS.items() if r["tipo"] == "pocion"]
    lista = sorted(_filtrar_recetas_lista(base, uid), key=lambda x: x[1]["nivel_requerido"])
    await _listar_recetas(update, context, lista, "🧪 Recetas de Pociones", "pociones", "oro_recetas", lista_cb="rec_pociones")

async def recetas_paginar_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    # callback: recpag_{key}_prev/next
    data = query.data  # e.g. "recpag_armas_next"
    partes = data.split("_")
    # partes[0]=recpag, partes[-1]=prev/next, key=partes[1:-1]
    direccion = partes[-1]
    key = "_".join(partes[1:-1])
    pag_key = f"rec_pag_{key}"
    pagina = context.user_data.get(pag_key, 0)
    if direccion == "next":
        context.user_data[pag_key] = pagina + 1
    else:
        context.user_data[pag_key] = max(0, pagina - 1)
    # Re-dispatch to right list
    if key == "armas":
        await recetas_armas_cb(update, context)
    elif key == "pociones":
        await recetas_pociones_cb(update, context)
    elif key.startswith("arm_"):
        await recetas_armaduras_por_clase_cb(update, context)

async def receta_detalle_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra detalle de una receta con stats e ítem crafteado."""
    query = update.callback_query
    await query.answer()
    receta_id = query.data[len("rdet_"):]
    receta = RECETAS.get(receta_id)
    if not receta:
        await query.edit_message_text("❌ Receta no encontrada.")
        return
    user_id = update.effective_user.id
    precio = _precio_receta(receta)
    tiene = _jugador_tiene_receta(user_id, receta_id)
    texto = _texto_detalle_receta(receta_id, receta, precio, tiene)
    botones = []
    if not tiene:
        botones.append([InlineKeyboardButton(f"🛒 Comprar receta ({precio} 🪙)", callback_data=f"crec_{receta_id}")])
    volver_cb = context.user_data.get("rdet_volver_cb", "oro_recetas")
    botones.append([InlineKeyboardButton("🔙 Volver a la lista", callback_data=volver_cb)])
    try:
        await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(botones), parse_mode="Markdown")
    except Exception as e:
        logger.error(f"receta_detalle_handler error [{receta_id}]: {e}", exc_info=True)
        try:
            plain = texto.replace("*", "").replace("_", "").replace("\\", "")
            await query.edit_message_text(plain, reply_markup=InlineKeyboardMarkup(botones))
        except Exception as e2:
            logger.error(f"receta_detalle_handler fallback error: {e2}")

async def comprar_receta_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    partes_crec = query.data.split("_", 1)
    if len(partes_crec) < 2:
        await query.edit_message_text("❌ Error al procesar compra de receta.")
        return
    receta_id = partes_crec[1]
    user_id = update.effective_user.id
    receta = RECETAS.get(receta_id)
    if not receta:
        await query.edit_message_text("❌ Receta no encontrada.")
        return
    if _jugador_tiene_receta(user_id, receta_id):
        await query.answer("✅ Ya tienes esta receta.", show_alert=True)
        return
    precio = _precio_receta(receta)
    saldos = economia.obtener_saldos(user_id)
    if saldos.get("oro", 0) < precio:
        await query.answer(f"❌ Necesitas {precio} oro. Tienes {saldos.get('oro',0)}.", show_alert=True)
        return
    economia.modificar_saldo(user_id, "oro", -precio, f"compra receta: {receta['nombre']}")
    _registrar_receta_jugador(user_id, receta_id)
    await query.answer(f"✅ ¡Receta '{receta['nombre']}' aprendida! Ya puedes craftearla.", show_alert=True)
    # Actualizar la vista de detalle para mostrar estado ✅
    texto_ok = _texto_detalle_receta(receta_id, receta, precio, tiene=True)
    volver_cb = context.user_data.get("rdet_volver_cb", "oro_recetas")
    try:
        await query.edit_message_text(
            texto_ok,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver a la lista", callback_data=volver_cb)]]),
            parse_mode="Markdown"
        )
    except Exception:
        pass
    try:
        import guia_contextual as _gc
        await _gc.enviar(user_id, context, "receta_comprada")
    except Exception:
        pass

# ==================== REGISTRO DE HANDLERS ====================
def registrar_handlers(app):
    app.add_handler(CommandHandler("tienda", cmd_tienda))
    app.add_handler(CallbackQueryHandler(tienda_volver, pattern="^tienda_volver$"))
    app.add_handler(CallbackQueryHandler(tienda_cerrar, pattern="^tienda_cerrar$"))
    app.add_handler(CallbackQueryHandler(tienda_vender, pattern="^tienda_vender$"))
    app.add_handler(CallbackQueryHandler(vender_handler, pattern="^vender_"))
    app.add_handler(CallbackQueryHandler(tienda_oro_menu, pattern="^tienda_oro$"))
    app.add_handler(CallbackQueryHandler(tienda_eternium_menu, pattern="^tienda_eternium$"))
    app.add_handler(CallbackQueryHandler(tienda_creditos_menu, pattern="^tienda_creditos$"))

    # Oro
    app.add_handler(CallbackQueryHandler(oro_comunes, pattern="^oro_comunes$"))
    app.add_handler(CallbackQueryHandler(crear_paginador("oro_comunes", oro_comunes), pattern="^oro_comunes_prev$"))
    app.add_handler(CallbackQueryHandler(crear_paginador("oro_comunes", oro_comunes), pattern="^oro_comunes_next$"))
    app.add_handler(CallbackQueryHandler(oro_armas_clase_menu, pattern="^oro_armas_clase$"))
    app.add_handler(CallbackQueryHandler(oro_armaduras_clase_menu, pattern="^oro_armaduras_clase$"))
    for clase in ["vanguardista", "acechante", "tejehechizos", "maestro_caza"]:
        app.add_handler(CallbackQueryHandler(lambda u, c, cl=clase: oro_armas_por_clase(u, c, cl), pattern=f"^oro_armas_{clase}$"))
        app.add_handler(CallbackQueryHandler(crear_paginador(f"oro_armas_{clase}", lambda u, c, cl=clase: oro_armas_por_clase(u, c, cl)), pattern=f"^oro_armas_{clase}_prev$"))
        app.add_handler(CallbackQueryHandler(crear_paginador(f"oro_armas_{clase}", lambda u, c, cl=clase: oro_armas_por_clase(u, c, cl)), pattern=f"^oro_armas_{clase}_next$"))
        app.add_handler(CallbackQueryHandler(lambda u, c, cl=clase: oro_armaduras_por_clase(u, c, cl), pattern=f"^oro_armaduras_{clase}$"))
        app.add_handler(CallbackQueryHandler(crear_paginador(f"oro_armaduras_{clase}", lambda u, c, cl=clase: oro_armaduras_por_clase(u, c, cl)), pattern=f"^oro_armaduras_{clase}_prev$"))
        app.add_handler(CallbackQueryHandler(crear_paginador(f"oro_armaduras_{clase}", lambda u, c, cl=clase: oro_armaduras_por_clase(u, c, cl)), pattern=f"^oro_armaduras_{clase}_next$"))
    app.add_handler(CallbackQueryHandler(oro_monturas, pattern="^oro_monturas$"))
    app.add_handler(CallbackQueryHandler(crear_paginador("oro_monturas", oro_monturas), pattern="^oro_monturas_prev$"))
    app.add_handler(CallbackQueryHandler(crear_paginador("oro_monturas", oro_monturas), pattern="^oro_monturas_next$"))
    app.add_handler(CallbackQueryHandler(oro_pociones, pattern="^oro_pociones$"))
    app.add_handler(CallbackQueryHandler(crear_paginador("oro_pociones", oro_pociones), pattern="^oro_pociones_prev$"))
    app.add_handler(CallbackQueryHandler(crear_paginador("oro_pociones", oro_pociones), pattern="^oro_pociones_next$"))

    # Eternium
    app.add_handler(CallbackQueryHandler(et_comunes, pattern="^et_comunes$"))
    app.add_handler(CallbackQueryHandler(crear_paginador("et_comunes", et_comunes), pattern="^et_comunes_prev$"))
    app.add_handler(CallbackQueryHandler(crear_paginador("et_comunes", et_comunes), pattern="^et_comunes_next$"))
    app.add_handler(CallbackQueryHandler(et_armas_clase_menu, pattern="^et_armas_clase$"))
    app.add_handler(CallbackQueryHandler(et_armaduras_clase_menu, pattern="^et_armaduras_clase$"))
    for clase in ["vanguardista", "acechante", "tejehechizos", "maestro_caza"]:
        app.add_handler(CallbackQueryHandler(lambda u, c, cl=clase: et_armas_por_clase(u, c, cl), pattern=f"^et_armas_{clase}$"))
        app.add_handler(CallbackQueryHandler(crear_paginador(f"et_armas_{clase}", lambda u, c, cl=clase: et_armas_por_clase(u, c, cl)), pattern=f"^et_armas_{clase}_prev$"))
        app.add_handler(CallbackQueryHandler(crear_paginador(f"et_armas_{clase}", lambda u, c, cl=clase: et_armas_por_clase(u, c, cl)), pattern=f"^et_armas_{clase}_next$"))
        app.add_handler(CallbackQueryHandler(lambda u, c, cl=clase: et_armaduras_por_clase(u, c, cl), pattern=f"^et_armaduras_{clase}$"))
        app.add_handler(CallbackQueryHandler(crear_paginador(f"et_armaduras_{clase}", lambda u, c, cl=clase: et_armaduras_por_clase(u, c, cl)), pattern=f"^et_armaduras_{clase}_prev$"))
        app.add_handler(CallbackQueryHandler(crear_paginador(f"et_armaduras_{clase}", lambda u, c, cl=clase: et_armaduras_por_clase(u, c, cl)), pattern=f"^et_armaduras_{clase}_next$"))
    app.add_handler(CallbackQueryHandler(et_monturas, pattern="^et_monturas$"))
    app.add_handler(CallbackQueryHandler(crear_paginador("et_monturas", et_monturas), pattern="^et_monturas_prev$"))
    app.add_handler(CallbackQueryHandler(crear_paginador("et_monturas", et_monturas), pattern="^et_monturas_next$"))
    app.add_handler(CallbackQueryHandler(et_pociones, pattern="^et_pociones$"))
    app.add_handler(CallbackQueryHandler(crear_paginador("et_pociones", et_pociones), pattern="^et_pociones_prev$"))
    app.add_handler(CallbackQueryHandler(crear_paginador("et_pociones", et_pociones), pattern="^et_pociones_next$"))

    # Detalle de item y volver
    app.add_handler(CallbackQueryHandler(tienda_detalle_handler, pattern="^tdet_"))
    app.add_handler(CallbackQueryHandler(tienda_detalle_credito_handler, pattern="^tdetcr_"))
    app.add_handler(CallbackQueryHandler(tvolver_handler, pattern="^tdetv$"))

    # Créditos y compras
    app.add_handler(CallbackQueryHandler(comprar_oro_handler, pattern="^comprar_oro_"))
    app.add_handler(CallbackQueryHandler(comprar_eternium_handler, pattern="^comprar_eternium_"))

    # Recetas
    app.add_handler(CallbackQueryHandler(tienda_recetas_menu, pattern="^oro_recetas$"))
    app.add_handler(CallbackQueryHandler(recetas_armas_cb, pattern="^rec_armas$"))
    app.add_handler(CallbackQueryHandler(recetas_armaduras_menu_cb, pattern="^rec_armaduras_menu$"))
    app.add_handler(CallbackQueryHandler(recetas_armaduras_por_clase_cb, pattern="^rec_arm_"))
    app.add_handler(CallbackQueryHandler(recetas_pociones_cb, pattern="^rec_pociones$"))
    app.add_handler(CallbackQueryHandler(recetas_paginar_cb, pattern="^recpag_"))
    app.add_handler(CallbackQueryHandler(receta_detalle_handler, pattern="^rdet_"))
    app.add_handler(CallbackQueryHandler(comprar_receta_handler, pattern="^crec_"))
    app.add_handler(CallbackQueryHandler(comprar_credito_handler, pattern="^comprar_credito_"))
#!/usr/bin/env python3
# combate.py
# Motor de combate global para Aethelgard.
# Incluye: duelos, caza, mazmorras, peaje, pérdidas/transferencias,
# búsqueda recursiva, temporizadores, objetos únicos.
# PvE normales/mini-boss: 50% fijo / 50% escalable (con drops por zona).
# Mazmorras: siempre escalable. Mejora de huida para monstruos fijos muy fuertes.
# Versión completamente funcional (caza y mazmorras implementadas).

import random
import sqlite3
import importlib.util
import os
import sys
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler, CommandHandler

def _esc_md(s: str) -> str:
    return str(s).replace("_", "\\_").replace("*", "\\*").replace("`", "\\`").replace("[", "\\[")

# ==================== BÚSQUEDA RECURSIVA DE ARCHIVOS ====================
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
    print("❌ No se encontró 'datos_zona.py'. El bot no puede iniciar.")
    sys.exit(1)

def esta_marcado(user_id: int) -> bool:
    jug = db_helper.obtener_jugador(user_id)
    if not jug or not jug.get("estado_marcado", 0):
        return False
    expiracion = jug.get("marca_expiracion")
    if expiracion and datetime.now() < datetime.fromisoformat(expiracion):
        return True
    db_helper.actualizar_jugador(user_id, estado_marcado=0, marca_expiracion=None)
    return False

RAIZ = encontrar_raiz_proyecto()
sys.path.insert(0, RAIZ)

# ==================== VERIFICACIÓN DE ARCHIVOS CRÍTICOS ====================
ARCHIVOS_CRITICOS = [
    "db_helper.py",
    "economia.py",
    "clases.py",
    "inventario.py",
    "progresion_clase.py",
    "armas.py",
    "armaduras.py",
    "pociones.py",
    "materiales.py",
    "combate.py",
]

print("\n🔍 Verificando archivos necesarios para COMBATE...")
# Verificar archivos críticos recursivamente
for archivo in ARCHIVOS_CRITICOS:
    ruta = buscar_archivo(archivo, RAIZ)
    if ruta:
        print(f"✅ Encontrado: {archivo} en {ruta}")
        directorio = os.path.dirname(ruta)
        if directorio not in sys.path:
            sys.path.insert(0, directorio)
    else:
        print(f"❌ ERROR CRÍTICO: No se encontró {archivo}")
        sys.exit(1)

# ==================== IMPORTACIONES ====================
import db_helper
import economia
import config_balance
import clases
import inventario
from datos_zona import ZONAS
try:
    from armas import ARMAS
except ImportError:
    ARMAS = {}
try:
    from armaduras import ARMADURAS
except ImportError:
    ARMADURAS = {}
try:
    from pociones import POCIONES
except ImportError:
    POCIONES = {}
try:
    from materiales import MATERIALES
except ImportError:
    MATERIALES = {}
try:
    from progresion_clase import obtener_bonos_totales, obtener_hitos_reclamados, obtener_bonos_insignias
except ImportError:
    obtener_bonos_totales = lambda uid: {}
    obtener_hitos_reclamados = lambda uid: []
    obtener_bonos_insignias = lambda uid: {}

# Cargar drops_config (estructura DROPS_POR_MONSTRUO)
drops_path = buscar_archivo("drops_config.py", RAIZ)
spec = importlib.util.spec_from_file_location("drops_config", drops_path)
drops_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(drops_mod)
# Verificar que exista DROPS_POR_MONSTRUO como dict
if hasattr(drops_mod, "DROPS_POR_MONSTRUO"):
    DROPS_POR_MONSTRUO = drops_mod.DROPS_POR_MONSTRUO
else:
    print("❌ ERROR: drops_config.py debe contener DROPS_POR_MONSTRUO (estructura por zona y nombre de monstruo).")
    sys.exit(1)
print("✅ drops_config.py cargado (estructura DROPS_POR_MONSTRUO)")

DB_PATH = "aethelgard.db"

# ==================== CONSTANTES DE TIPOS DE COMBATE ====================
COMBATE_PVP_AMISTOSO = "pvp_amistoso"
COMBATE_PVP_AMARILLA = "pvp_zona_amarilla"
COMBATE_PVP_ROJA = "pvp_zona_roja"
COMBATE_PVP_NEGRA = "pvp_zona_negra"
COMBATE_PEAJE = "pvp_peaje"
COMBATE_CAZA_AMARILLA = "caza_amarilla"
COMBATE_CAZA_ROJA = "caza_roja"
COMBATE_CAZA_NEGRA = "caza_negra"
COMBATE_MAZMORRA = "mazmorra"
COMBATE_PVE_AZUL = "pve_zona_azul"
COMBATE_PVE_AMARILLA = "pve_zona_amarilla"
COMBATE_PVE_ROJA = "pve_zona_roja"
COMBATE_PVE_NEGRA = "pve_zona_negra"
COMBATE_PVE_MINI = "pve_mini_boss"

# ==================== PENALIZACIONES Y RECOMPENSAS ====================
PENALIZACIONES_PVP = {
    COMBATE_PVP_AMARILLA: {"oro_porcentaje": 0.10, "objetos_cantidad": 1},
    COMBATE_PVP_ROJA:     {"oro_porcentaje": 0.50, "objetos_cantidad": 5},
    COMBATE_PVP_NEGRA:    {"oro_porcentaje": 1.00, "objetos_cantidad": "todo"},
    COMBATE_CAZA_AMARILLA: {"oro_porcentaje": 0.10, "objetos_cantidad": 1},
    COMBATE_CAZA_ROJA:     {"oro_porcentaje": 0.50, "objetos_cantidad": 5},
    COMBATE_CAZA_NEGRA:    {"oro_porcentaje": 1.00, "objetos_cantidad": "todo"},
}

def _get_penalizacion_pvp(tipo: str) -> dict:
    """Devuelve las penalizaciones PvP/Caza desde config_db (configurable por panel)."""
    import config_db as _cfgdb
    _mapa_oro = {
        COMBATE_PVP_AMARILLA:  "pvp_muerte_oro_amarilla",
        COMBATE_PVP_ROJA:      "pvp_muerte_oro_roja",
        COMBATE_PVP_NEGRA:     "pvp_muerte_oro_negra",
        COMBATE_CAZA_AMARILLA: "pvp_muerte_oro_amarilla",
        COMBATE_CAZA_ROJA:     "pvp_muerte_oro_roja",
        COMBATE_CAZA_NEGRA:    "pvp_muerte_oro_negra",
    }
    _mapa_items = {
        COMBATE_PVP_AMARILLA:  "pvp_muerte_items_amarilla",
        COMBATE_PVP_ROJA:      "pvp_muerte_items_roja",
        COMBATE_PVP_NEGRA:     "pvp_muerte_items_negra",
        COMBATE_CAZA_AMARILLA: "pvp_muerte_items_amarilla",
        COMBATE_CAZA_ROJA:     "pvp_muerte_items_roja",
        COMBATE_CAZA_NEGRA:    "pvp_muerte_items_negra",
    }
    fallback = PENALIZACIONES_PVP.get(tipo, {"oro_porcentaje": 0.0, "objetos_cantidad": 0})
    if tipo not in _mapa_oro:
        return fallback
    _fallback_oro_pct = int(fallback["oro_porcentaje"] * 100)
    _fallback_items   = -1 if fallback["objetos_cantidad"] == "todo" else fallback["objetos_cantidad"]
    oro_pct   = _cfgdb.get(_mapa_oro[tipo],   _fallback_oro_pct) / 100.0
    items_raw = _cfgdb.get(_mapa_items[tipo],  _fallback_items)
    objetos   = "todo" if items_raw < 0 else items_raw
    return {"oro_porcentaje": oro_pct, "objetos_cantidad": objetos}
_FACCION_CIUDADES = {
    "Alianza":   {"nombre": "Ciudadela Alianza",   "id": 1},
    "Imperio":   {"nombre": "Ciudadela Imperio",   "id": 12},
    "Sindicato": {"nombre": "Ciudadela Sindicato", "id": 23},
}

_LORE_MUERTE = [
    "Las sombras se cierran sobre tus ojos. El frío penetra tus heridas mientras el mundo se desvanece... Cuando despiertas, los muros de tu ciudad te rodean.",
    "Tu último pensamiento fue el fragor del combate. Alguien te arrastró lejos, entre sombras y susurros. Abres los ojos: estás en casa, pero más pobre que antes.",
    "La tierra bebió tu sangre. Los cuervos ya sobrevolaban tu cuerpo cuando tus aliados te encontraron y te trajeron de vuelta. Reapareces en la ciudadela, malherido y con menos de lo que partiste.",
    "El enemigo fue más fuerte esta vez. Caíste entre el polvo del campo de batalla... pero la muerte aún no reclamó tu alma. Despiertas en la ciudad, marcado por la derrota.",
    "Un silencio extraño lo cubre todo. Después, dolor. Después, las voces familiares de tu ciudad natal. Sobreviviste, pero el precio fue alto.",
]

async def _manejar_muerte_jugador(
    user_id: int,
    context,
    nombre_enemigo: str = "el enemigo",
    tipo_combate: str = "",
    oro_perdido: int = 0,
    items_perdidos: list = None
):
    """Teleporta al jugador a su ciudad, aplica penalización de HP y envía mensaje de muerte con lore."""
    if items_perdidos is None:
        items_perdidos = []
    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        return

    # HP máximo real (clase+nivel+equipo), no el campo DB que puede estar desfasado
    hp_max = obtener_estadisticas_jugador(user_id)[0]
    nuevo_hp = hp_max
    # Sincronizar hp_max en DB para que perfil y otros módulos vean el valor correcto
    db_helper.actualizar_jugador(user_id, hp_max=hp_max)

    faccion = jug.get("faccion", "Alianza")
    ciudad_data = _FACCION_CIUDADES.get(faccion, {"nombre": "Ciudadela Alianza", "id": 1})

    db_helper.actualizar_jugador(
        user_id,
        hp_actual=nuevo_hp,
        zona_actual=ciudad_data["nombre"],
        zona_actual_id=ciudad_data["id"],
        ubicacion="ciudad"
    )
    db_helper.set_actividad(user_id, None)

    lore = random.choice(_LORE_MUERTE)

    perdidas_txt = f"❤️ HP restaurado: *{nuevo_hp}/{hp_max}* _(vida completa)_\n"
    if oro_perdido > 0:
        perdidas_txt += f"🪙 Oro perdido: *{oro_perdido}*\n"
    if items_perdidos:
        perdidas_txt += "📦 Objetos perdidos:\n" + "\n".join(f"  • {it}" for it in items_perdidos) + "\n"
    if not oro_perdido and not items_perdidos:
        perdidas_txt += "_Sin pérdidas adicionales._\n"

    tipo_l = tipo_combate.lower()
    if "negra" in tipo_l:
        tips = (
            "⚫ *Zona Negra — máximo riesgo:*\n"
            "• Sube de nivel en zonas más seguras antes de volver.\n"
            "• Usa encantamientos defensivos de alto nivel.\n"
            "• Nunca viajes solo: únete a un gremio.\n"
            "• 🏦 Guarda tu oro en el *banco* antes de salir."
        )
    elif "roja" in tipo_l:
        tips = (
            "🔴 *Zona Roja — tierra hostil:*\n"
            "• Lleva pociones de vida en el inventario.\n"
            "• Mejora tu equipamiento en la *herrería* y el *encantador*.\n"
            "• 🏦 Deposita tu oro en el *banco* para no arriesgarlo.\n"
            "• Completa mazmorras para subir de nivel con más seguridad."
        )
    elif any(x in tipo_l for x in ("pvp", "duelo", "caza")):
        tips = (
            "⚔️ *Derrota en combate PvP:*\n"
            "• Mejora armas y armaduras en la *herrería*.\n"
            "• Añade *encantamientos* a tu equipo para subir stats.\n"
            "• 🏦 Deposita tu oro en el *banco* antes de ir a zonas PvP.\n"
            "• Practica con *duelos amistosos* para mejorar tu estrategia.\n"
            "• Sube de nivel en mazmorras para desbloquear habilidades de clase."
        )
    elif "mazmorra" in tipo_l:
        tips = (
            "🌀 *Derrota en mazmorra:*\n"
            "• Coordínate mejor con tu grupo antes de entrar.\n"
            "• Lleva pociones para cada miembro del equipo.\n"
            "• Prueba dificultades menores mientras mejoras tu equipo.\n"
            "• Usa la *taberna* para recuperar vida completa antes de entrar.\n"
            "• Mejora tus habilidades de clase subiendo de nivel."
        )
    else:
        tips = (
            "💡 *Cómo mejorar para la próxima:*\n"
            "• 🛠️ *Herrería*: mejora tus armas y armaduras.\n"
            "• ✨ *Encantador*: añade bonificaciones a tu equipo.\n"
            "• 🌀 *Mazmorras*: consigue experiencia y objetos raros.\n"
            "• 🏦 *Banco*: guarda tu oro para no perderlo al morir.\n"
            "• 🍺 *Taberna*: descansa y recupera toda tu vida al instante.\n"
            "• 🔬 *Investigación*: desbloquea mejoras permanentes de stats."
        )

    mensaje = (
        f"💀 *Has caído en batalla...*\n\n"
        f"_{lore}_\n\n"
        f"📍 Has reaparecido en *{ciudad_data['nombre']}*.\n\n"
        f"📉 *Lo que perdiste:*\n{perdidas_txt}\n"
        f"🗡️ *Derrotado por:* {nombre_enemigo}\n\n"
        f"{tips}"
    )

    try:
        if _bot_context:
            await _bot_context.bot.send_message(
                chat_id=user_id,
                text=mensaje,
                parse_mode="Markdown"
            )
    except Exception:
        pass


RECOMPENSA_ORO_PORCENTAJE = {
    COMBATE_PVP_AMARILLA: 100,
    COMBATE_PVP_ROJA: 100,
    COMBATE_PVP_NEGRA: 100,
    COMBATE_CAZA_AMARILLA: 100,
    COMBATE_CAZA_ROJA: 100,
    COMBATE_CAZA_NEGRA: 100,
    COMBATE_PVP_AMISTOSO: 0,
}
HUIR_PROB_BASE = {
    COMBATE_PVE_AZUL: 0.9,
    COMBATE_PVE_AMARILLA: 0.7,
    COMBATE_PVE_ROJA: 0.4,
    COMBATE_PVE_NEGRA: 0.2,
    COMBATE_PVE_MINI: 0.6,
    COMBATE_PVP_AMISTOSO: 0.0,
    COMBATE_PVP_AMARILLA: 0.5,
    COMBATE_PVP_ROJA: 0.3,
    COMBATE_PVP_NEGRA: 0.1,
    COMBATE_CAZA_AMARILLA: 0.3,
    COMBATE_CAZA_ROJA: 0.0,
    COMBATE_CAZA_NEGRA: 0.3,
    COMBATE_PEAJE: 0.0,
}
TIEMPO_ACEPTAR_DUELO = 30
TIEMPO_UNIRSE_CAZA = 90
TIEMPO_TURNO = 90
TIEMPO_SALA_MAZMORRA = 300

# ==================== ESTRUCTURAS DE DATOS EN MEMORIA ====================
combates_activos = {}          # duelos y PvE simples
eventos_caza = {}              # eventos de caza (group combats)
mazmorras_activas = {}         # mazmorras (group combats)
_bot_context = None            # Referencia global para enviar mensajes desde tareas async

# ==================== FUNCIONES AUXILIARES DE ESTADÍSTICAS ====================
def _obtener_estadisticas_objeto_real(nombre_objeto: str) -> dict:
    if nombre_objeto in ARMAS:
        return ARMAS[nombre_objeto].copy()
    if nombre_objeto in ARMADURAS:
        return ARMADURAS[nombre_objeto].copy()
    if nombre_objeto in POCIONES:
        return POCIONES[nombre_objeto].copy()
    if nombre_objeto in MATERIALES:
        return MATERIALES[nombre_objeto].copy()
    return {}

def _obtener_equipo_completo_stats(user_id: int) -> dict:
    equip = inventario.obtener_equipamiento(user_id)
    total = {"daño":0, "vida":0, "defensa":0, "critico":0, "velocidad":0, "vida_extra":0, "defensa_extra":0}
    for slot, obj_nombre in equip.items():
        if obj_nombre:
            stats = _obtener_estadisticas_objeto_real(obj_nombre)
            if stats:
                total["daño"] += stats.get("daño", 0)
                total["vida"] += stats.get("vida", 0) + stats.get("vida_extra", 0)
                total["defensa"] += stats.get("defensa", 0) + stats.get("defensa_extra", 0)
                total["critico"] += stats.get("critico", 0)
                total["velocidad"] += stats.get("velocidad", 0) + stats.get("velocidad_movimiento", 0)
    return total

def _obtener_bonos_progresion(user_id: int) -> dict:
    bonos = {"daño":1.0, "vida":1.0, "defensa":1.0, "critico":0, "velocidad":0}
    talentos = obtener_bonos_totales(user_id)
    # obtener_bonos_totales ya devuelve porcentajes como fracción (0.01 = 1%), no dividir de nuevo
    bonos["daño"] += talentos.get("daño", 0)
    bonos["critico"] += talentos.get("critico", 0)
    bonos["velocidad"] += talentos.get("velocidad_ataque", 0)
    bonos["vida"] += talentos.get("vida", 0)
    bonos["defensa"] += talentos.get("defensa", 0)
    hitos = obtener_hitos_reclamados(user_id)
    hito_bonus = len(hitos)*0.02
    bonos["daño"] += hito_bonus
    bonos["vida"] += hito_bonus
    bonos["defensa"] += hito_bonus
    insignias = obtener_bonos_insignias(user_id)
    bonos["vida"] += insignias.get("vida",0)/100
    bonos["daño"] += insignias.get("daño",0)/100
    bonos["defensa"] += insignias.get("defensa",0)/100
    return bonos

def obtener_estadisticas_jugador(user_id: int) -> Tuple[int, int, int]:
    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        return 100, 10, 5
    vida_base = clases.calcular_vida_maxima(jug["clase"], jug["nivel"], jug.get("reencarnaciones",0))
    daño_base = clases.calcular_daño_base(jug["clase"], jug["nivel"], jug.get("reencarnaciones",0))
    defensa_base = clases.calcular_defensa(jug["clase"], jug["nivel"], jug.get("reencarnaciones",0))
    equipo = _obtener_equipo_completo_stats(user_id)
    vida_max = vida_base + equipo.get("vida",0)
    daño = daño_base + equipo.get("daño",0)
    defensa = defensa_base + equipo.get("defensa",0) + equipo.get("defensa_extra",0)
    return vida_max, daño, defensa

def calcular_poder_jugador(user_id: int) -> dict:
    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        return {"dps":10, "vida_efectiva":100, "defensa":5, "poder_total":1000}
    vida_base, daño_base, defensa_base = obtener_estadisticas_jugador(user_id)
    bonos = _obtener_bonos_progresion(user_id)
    daño_final = daño_base * bonos["daño"]
    vida_final = vida_base * bonos["vida"]
    defensa_final = defensa_base * bonos["defensa"]
    equipo = _obtener_equipo_completo_stats(user_id)
    critico = equipo.get("critico",0) + bonos["critico"]
    velocidad = equipo.get("velocidad",0) + bonos["velocidad"]
    dps = daño_final * (1+critico/100) * (1+velocidad/100)
    inv = db_helper.obtener_inventario(user_id)
    mejor_cura = 0
    for item in inv:
        nombre = item["nombre"]
        if "pocion" in nombre.lower() and ("vida" in nombre.lower() or "curativa" in nombre.lower()):
            stats = _obtener_estadisticas_objeto_real(nombre)
            cura_str = stats.get("efecto", "")
            try:
                cura = int(''.join(filter(str.isdigit, cura_str)))
            except:
                cura = 0
            if cura > mejor_cura:
                mejor_cura = cura
    curacion_total = mejor_cura * 3
    vida_efectiva = vida_final + curacion_total
    poder_total = dps * vida_efectiva * (1 + defensa_final/100)
    return {"dps":dps, "vida_efectiva":vida_efectiva, "defensa":defensa_final, "poder_total":poder_total}

def _otorgar_experiencia(user_id: int, xp_ganada: int) -> int:
    if xp_ganada <= 0:
        return 0
    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        return 0
    nueva_xp = jug["experiencia"] + xp_ganada
    nivel_actual = jug["nivel"]
    subidas = 0
    while True:
        xp_necesaria = clases.calcular_experiencia_necesaria(nivel_actual)
        if nueva_xp >= xp_necesaria:
            nueva_xp -= xp_necesaria
            nivel_actual += 1
            subidas += 1
        else:
            break
    if subidas > 0:
        db_helper.actualizar_jugador(user_id, nivel=nivel_actual, experiencia=nueva_xp)
        vida_max_nueva = clases.calcular_vida_maxima(jug["clase"], nivel_actual, jug.get("reencarnaciones",0))
        db_helper.actualizar_jugador(user_id, hp_max=vida_max_nueva, hp_actual=vida_max_nueva)
        # Hook: comprobar recompensa de recluta al subir de nivel
        try:
            db_helper.recluta_alcanzo_nivel_configurado(user_id)
        except Exception:
            pass
        # Hook misiones de nivel
        try:
            import misiones as _mis
            if nivel_actual >= 3:
                _mis.completar_mision(user_id, "subir_nivel_3")
            if nivel_actual >= 5:
                _mis.completar_mision(user_id, "subir_nivel_5")
        except Exception:
            pass
        return subidas
    else:
        db_helper.actualizar_jugador(user_id, experiencia=nueva_xp)
        return 0

def calcular_daño(daño_base: int, defensa_enemigo: int, es_habilidad: bool = False,
                  permitir_critico: bool = True) -> int:
    reduccion = defensa_enemigo / (defensa_enemigo + 100) if defensa_enemigo > 0 else 0
    daño_final = max(1, int(daño_base * (1 - reduccion)))
    if permitir_critico and random.random() < 0.05:
        daño_final = int(daño_final * 1.5)
    if es_habilidad:
        daño_final = int(daño_final * 1.2)
    return daño_final

def _obtener_oro_encima(user_id: int) -> int:
    jug = db_helper.obtener_jugador(user_id)
    return jug.get("oro", 0) if jug else 0

def _modificar_oro_encima(user_id: int, cantidad: int, motivo: str):
    economia.modificar_saldo(user_id, "oro", cantidad, motivo)

def _objetos_perdibles(user_id: int, excluir_unicos=True):
    inv = db_helper.obtener_inventario(user_id)
    equip = inventario.obtener_equipamiento(user_id)
    todos = []
    for item in inv:
        nombre = item["nombre"]
        if excluir_unicos:
            stats = _obtener_estadisticas_objeto_real(nombre)
            if stats.get("unica", False):
                continue
        todos.append(nombre)
    for slot, nombre in equip.items():
        if nombre:
            if excluir_unicos:
                stats = _obtener_estadisticas_objeto_real(nombre)
                if stats.get("unica", False):
                    continue
            todos.append(nombre)
    return todos

def _transferir_objeto(de_user: int, a_user: int, nombre_objeto: str, cantidad: int = 1):
    db_helper.quitar_item(de_user, nombre_objeto, cantidad)
    db_helper.agregar_item(a_user, nombre_objeto, cantidad)

def _transferir_oro(de_user: int, a_user: int, cantidad: int):
    _modificar_oro_encima(de_user, -cantidad, f"Perdido en combate contra {a_user}")
    _modificar_oro_encima(a_user, cantidad, f"Ganado en combate contra {de_user}")

def _aplicar_perdidas_y_transferir(perdedor: int, ganador: int, tipo_combate: str):
    if tipo_combate in PENALIZACIONES_PVP:
        p = _get_penalizacion_pvp(tipo_combate)
        oro_encima = _obtener_oro_encima(perdedor)
        oro_perdido = int(oro_encima * p["oro_porcentaje"])
        if oro_perdido > 0:
            _transferir_oro(perdedor, ganador, oro_perdido)
        if p["objetos_cantidad"] == "todo" or (isinstance(p["objetos_cantidad"], int) and p["objetos_cantidad"] < 0):
            objetos = _objetos_perdibles(perdedor, excluir_unicos=True)
            for obj in objetos:
                equip = inventario.obtener_equipamiento(perdedor)
                for slot, nombre in equip.items():
                    if nombre == obj:
                        inventario.desequipar(perdedor, slot)
                        break
                _transferir_objeto(perdedor, ganador, obj, 1)
        else:
            objetos_posibles = _objetos_perdibles(perdedor, excluir_unicos=True)
            cantidad = min(p["objetos_cantidad"], len(objetos_posibles))
            if cantidad > 0:
                seleccionados = random.sample(objetos_posibles, cantidad)
                for obj in seleccionados:
                    equip = inventario.obtener_equipamiento(perdedor)
                    for slot, nombre in equip.items():
                        if nombre == obj:
                            inventario.desequipar(perdedor, slot)
                            break
                    _transferir_objeto(perdedor, ganador, obj, 1)

def _calcular_xp_pvp(perdedor_id: int) -> int:
    jug = db_helper.obtener_jugador(perdedor_id)
    nivel = jug.get("nivel", 1) if jug else 1
    return max(10, nivel * 20)

# ==================== DROPS Y MONSTRUOS ====================
def _obtener_drops_para_monstruo(zona_nombre: str, nombre_monstruo: str) -> List[dict]:
    """
    Devuelve los drops exclusivos de un monstruo específico en una zona.
    Busca en DROPS_POR_MONSTRUO[zona_nombre][nombre_monstruo].
    Si no existe, retorna lista vacía.
    """
    if zona_nombre in DROPS_POR_MONSTRUO and nombre_monstruo in DROPS_POR_MONSTRUO[zona_nombre]:
        return DROPS_POR_MONSTRUO[zona_nombre][nombre_monstruo]
    return []

def _calcular_poder_monstruo(monstruo: dict) -> float:
    vida = monstruo.get("vida", 100)
    daño = monstruo.get("daño", 20)
    defensa = monstruo.get("defensa", 10)
    return (vida * daño) / (defensa + 1)

def generar_monstruo_escalable(atacante_id: int, zona_nombre: str, color_zona: str, tipo_monstruo: str) -> dict:
    poder_jug = calcular_poder_jugador(atacante_id)
    poder_total = poder_jug["poder_total"]
    if tipo_monstruo == "normales":
        mult = 1.0
    elif tipo_monstruo == "mini_boss":
        mult = 2.5
    elif tipo_monstruo == "mazmorras_normal":
        mult = 1.8
    elif tipo_monstruo == "mazmorras_dificil":
        mult = 2.5
    else:
        mult = 1.0
    poder_mon = poder_total * mult
    try:
        _bg_vida = float(db_helper.obtener_config("bg_m_vida", "1.0"))
        _bg_daño = float(db_helper.obtener_config("bg_m_daño", "1.0"))
        _bg_def  = float(db_helper.obtener_config("bg_m_def",  "1.0"))
        _bg_xp   = float(db_helper.obtener_config("bg_m_xp",  "1.0"))
        _bg_oro  = float(db_helper.obtener_config("bg_m_oro",  "1.0"))
    except Exception:
        _bg_vida = _bg_daño = _bg_def = _bg_xp = _bg_oro = 1.0
    vida    = max(1, int(poder_mon ** 0.5 * 20 * _bg_vida))
    daño    = max(1, int(poder_mon ** 0.5 * 4  * _bg_daño))
    defensa = max(1, int(poder_mon ** 0.5 * 2  * _bg_def))
    xp  = max(10, int(poder_total / 10 * _bg_xp))
    oro = max(5,  int(poder_total / 20 * _bg_oro))
    # Los drops se asignarán después, al momento de la creación, basados en el nombre del monstruo.
    # Para monstruos escalables, el nombre se genera aquí y luego se buscarán sus drops.
    # Intentar usar un nombre real de la lista de monstruos de la zona en datos_zona
    _zd_gen = next((z for z in ZONAS if z["nombre"] == zona_nombre), None)
    _lista_mon = (_zd_gen.get("monstruos", {}).get(tipo_monstruo, [])) if _zd_gen else []
    if _lista_mon:
        nombre_base = random.choice(_lista_mon)["nombre"]
    else:
        nombre_base = f"Criatura de {zona_nombre}"
    # Creamos el monstruo sin drops todavía, los drops se asignarán al final de esta función
    monstruo = {
        "nombre": nombre_base,
        "descripcion": "Una criatura dinámica que se adapta a tu poder.",
        "vida": vida,
        "vida_max": vida,
        "daño": daño,
        "defensa": defensa,
        "xp": xp,
        "oro": oro,
        # drops se calcularán después
    }
    # Ahora obtener drops exclusivos para este monstruo (si existen en DROPS_POR_MONSTRUO)
    drops = _obtener_drops_para_monstruo(zona_nombre, nombre_base)
    monstruo["drops"] = drops
    return monstruo

def cargar_monstruo_fijo(zona_nombre: str, tipo_monstruo: str) -> Optional[dict]:
    zona_data = next((z for z in ZONAS if z["nombre"] == zona_nombre), None)
    if not zona_data:
        return None
    zona_id = zona_data["id"]
    color = zona_data["color"]
    if tipo_monstruo == "normales":
        archivo = f"monstruos_normales_zona_{zona_id}.py"
        clave = "MONSTRUOS_NORMALES"
    elif tipo_monstruo == "mini_boss":
        archivo = f"monstruos_mini_boss_zona_{zona_id}.py"
        clave = "MONSTRUOS_MINI_BOSS"
    else:
        return None
    carpeta = CARPETA_POR_COLOR.get(color, f"zonas_{color}s")
    ruta = os.path.join(carpeta, archivo)
    if not os.path.exists(ruta):
        return None
    spec = importlib.util.spec_from_file_location(f"temp_{zona_id}", ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    monstruos_dict = getattr(modulo, clave, {})
    if not monstruos_dict:
        return None
    mon_id = random.choice(list(monstruos_dict.keys()))
    monstruo = monstruos_dict[mon_id].copy()
    if "vida_actual" not in monstruo:
        monstruo["vida_actual"] = monstruo.get("vida", monstruo.get("vida_max", 100))
    if "vida_max" not in monstruo:
        monstruo["vida_max"] = monstruo.get("vida", 100)
    monstruo["vida"] = monstruo["vida_actual"]
    # Asegurar que tiene campo "drops" (si no, lista vacía)
    if "drops" not in monstruo:
        # Intentar obtener drops exclusivos de DROPS_POR_MONSTRUO usando nombre del monstruo y zona
        nombre_monstruo = monstruo.get("nombre", "")
        drops = _obtener_drops_para_monstruo(zona_nombre, nombre_monstruo)
        monstruo["drops"] = drops
    return monstruo
# Continuación de combate.py

# ==================== CONSTANTES DE CARPETAS PARA MONSTRUOS FIJOS ====================
CARPETA_POR_COLOR = {
    "azul": "zonas_azules",
    "amarilla": "zonas_amarillas",
    "roja": "zonas_rojas",
    "negra": "zonas_negras"
}

# ==================== DUELOS (PvP) ====================
async def cmd_duelo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        import restricciones_combate as _rc_duelo
        if not _rc_duelo.get_restriccion("duelos"):
            await update.effective_message.reply_text(
                "⚔️ Los duelos están restringidos temporalmente por los administradores."
            )
            return
    except Exception:
        pass
    try:
        from guerra_facciones import check_lockdown
        if await check_lockdown(update):
            return
    except Exception:
        pass
    if not context.args:
        await update.effective_message.reply_text("Uso: `/duelo @usuario`", parse_mode="Markdown")
        return
    nombre = context.args[0].replace("@","")
    try:
        oponente_id = int(nombre)
    except:
        await update.effective_message.reply_text("Debes proporcionar el ID numérico del usuario.")
        return
    user_id = update.effective_user.id
    if user_id == oponente_id:
        await update.effective_message.reply_text("No puedes desafiarte a ti mismo.")
        return
    if not db_helper.obtener_jugador(oponente_id):
        await update.effective_message.reply_text("El usuario no existe en el juego.")
        return
    if db_helper.esta_marcado(user_id):
        await update.effective_message.reply_text("❌ Estás marcado. No puedes iniciar duelo hasta que pagues rescate con /pagar_rescate.")
        return
    jug = db_helper.obtener_jugador(user_id)
    zona_actual = jug.get("zona_actual", "Bosque Alianza")
    zona_data = next((z for z in ZONAS if z["nombre"] == zona_actual), None)
    if not zona_data:
        await update.effective_message.reply_text("No se pudo determinar tu zona actual.")
        return
    color = zona_data["color"]
    if color == "azul":
        tipo_combate = COMBATE_PVP_AMISTOSO
    elif color == "amarilla":
        tipo_combate = COMBATE_PVP_AMARILLA
    elif color == "roja":
        tipo_combate = COMBATE_PVP_ROJA
    elif color == "negra":
        tipo_combate = COMBATE_PVP_NEGRA
    else:
        tipo_combate = COMBATE_PVP_AMISTOSO
    context.user_data["duelo_pendiente"] = {
        "retador": user_id,
        "oponente": oponente_id,
        "tipo": tipo_combate,
        "timestamp": datetime.now()
    }
    keyboard = [[
        InlineKeyboardButton("Aceptar duelo", callback_data=f"duelo_aceptar_{user_id}_{oponente_id}"),
        InlineKeyboardButton("Rechazar", callback_data=f"duelo_rechazar_{user_id}_{oponente_id}")
    ]]
    await context.bot.send_message(
        chat_id=oponente_id,
        text=f"⚔️ {update.effective_user.first_name} te ha retado a un duelo en {zona_actual}. ¿Aceptas? (30 segundos)",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    asyncio.create_task(_cancelar_duelo_despues(context, user_id, oponente_id, TIEMPO_ACEPTAR_DUELO))

async def _cancelar_duelo_despues(context, retador, oponente, segundos):
    await asyncio.sleep(segundos)
    if "duelo_pendiente" in context.user_data:
        pend = context.user_data["duelo_pendiente"]
        if pend["retador"] == retador and pend["oponente"] == oponente:
            del context.user_data["duelo_pendiente"]
            await context.bot.send_message(chat_id=retador, text="⏰ El duelo ha expirado porque el oponente no respondió a tiempo.")
            await context.bot.send_message(chat_id=oponente, text="⏰ El duelo ha expirado por tiempo de espera.")

async def aceptar_duelo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    parts = data.split("_")
    try:
        retador_id = int(parts[2])
        retado_id = int(parts[3])
    except (ValueError, IndexError):
        await query.answer("❌ Error en los datos del duelo.", show_alert=True)
        return
    if update.effective_user.id != retado_id:
        await query.edit_message_text("❌ No puedes aceptar este duelo.")
        return
    # duelo_pendiente se guarda en el contexto del RETADOR, no del retado
    retador_data = context.application.user_data.get(retador_id, {})
    pend = retador_data.get("duelo_pendiente")
    if pend and pend.get("retador") == retador_id and pend.get("oponente") == retado_id:
        tipo = pend.get("tipo", COMBATE_PVP_AMISTOSO)
        retador_data.pop("duelo_pendiente", None)
    else:
        # Sin pendiente almacenado: duelo amistoso estándar
        tipo = COMBATE_PVP_AMISTOSO
    if not db_helper.obtener_jugador(retador_id):
        await query.edit_message_text("❌ El retador ya no existe en el juego.")
        return
    # Notificar al retador que su reto fue aceptado
    retado_nombre = update.effective_user.first_name or "Tu oponente"
    try:
        await context.bot.send_message(
            chat_id=retador_id,
            text=f"✅ {retado_nombre} aceptó tu duelo. ¡Que comience el combate!"
        )
    except Exception:
        pass
    # Iniciar combate — esto envía el panel al retado (quien aceptó, vía update.effective_message)
    await iniciar_combate(update, context, retador_id, retado_id, tipo, enemigo=None, datos_extra={})
    # Buscar el combate recién creado y enviar el panel también al retador
    combate_id_nuevo = next(
        (cid for cid, c in combates_activos.items()
         if c.get("atacante_id") == retador_id and c.get("defensor_id") == retado_id),
        None
    )
    if combate_id_nuevo:
        await _enviar_panel_pvp_a(context, combate_id_nuevo, retador_id)

async def rechazar_duelo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    # Extraer retador_id del callback_data (duelo_rechazar_<retador_id>_<retado_id>)
    parts = query.data.split("_")
    try:
        retador_id = int(parts[2])
    except (ValueError, IndexError):
        await query.edit_message_text("❌ Has rechazado el duelo.")
        return
    await query.edit_message_text("❌ Has rechazado el duelo.")
    # Limpiar duelo_pendiente del RETADOR (se guardó en su contexto, no en el del retado)
    retador_data = context.application.user_data.get(retador_id, {})
    retador_data.pop("duelo_pendiente", None)
    # Notificar al retador
    try:
        await context.bot.send_message(chat_id=retador_id, text="❌ Tu oponente rechazó el duelo.")
    except Exception:
        pass

# ==================== INICIO DE COMBATE (GENÉRICO) ====================
async def iniciar_combate(update: Update, context: ContextTypes.DEFAULT_TYPE,
                          atacante_id: int, defensor_id: int,
                          tipo_combate: str,
                          enemigo: dict = None,
                          datos_extra: dict = None):
    # Verificar restricciones globales antes de iniciar
    try:
        import restricciones_combate as _rc_ic
        if tipo_combate.startswith("pve") and not _rc_ic.get_restriccion("combate"):
            try:
                await update.effective_message.reply_text(
                    "⚔️ El combate está restringido temporalmente por los administradores."
                )
            except Exception:
                pass
            return
        _snapshot_restricciones = _rc_ic.get_snapshot()
    except Exception:
        _snapshot_restricciones = {}
    # Guía contextual: avisa al jugador cuando inicia combate PvE
    if tipo_combate.startswith("pve"):
        try:
            import guia_contextual as _gc
            await _gc.enviar(atacante_id, context, "combate_pve_iniciado")
        except Exception:
            pass
    # Si es PvE y no hay enemigo, se genera con la regla del 50%
    if tipo_combate.startswith("pve") and enemigo is None:
        jug = db_helper.obtener_jugador(atacante_id)
        zona_nombre = jug.get("zona_actual", "Bosque Alianza")
        zona_data = next((z for z in ZONAS if z["nombre"] == zona_nombre), None)
        if not zona_data:
            if update.message:
                await update.effective_message.reply_text("No se pudo determinar la zona.")
            return
        color = zona_data["color"]
        if tipo_combate == COMBATE_PVE_MINI:
            tipo_mon = "mini_boss"
        else:
            tipo_mon = "normales"
        # Regla 50%
        if random.random() < 0.5:
            monstruo = cargar_monstruo_fijo(zona_nombre, tipo_mon)
            if monstruo is None:
                monstruo = generar_monstruo_escalable(atacante_id, zona_nombre, color, tipo_mon)
            es_fijo = True
        else:
            monstruo = generar_monstruo_escalable(atacante_id, zona_nombre, color, tipo_mon)
            es_fijo = False
        poder_jug = calcular_poder_jugador(atacante_id)["poder_total"]
        poder_mon = _calcular_poder_monstruo(monstruo)
        prob_huida = HUIR_PROB_BASE.get(tipo_combate, 0.5)
        if es_fijo and poder_mon > poder_jug * 1.2:
            diferencia = poder_mon / poder_jug
            prob_huida = min(0.9, prob_huida + (diferencia - 1) * 0.3)
        enemigo = monstruo
        datos_extra = {"prob_huida": prob_huida}
    # Normalizar enemigo PvE — garantizar que 'vida', 'vida_max' y 'vida_actual' existen
    if enemigo is not None and tipo_combate.startswith("pve"):
        if "vida" not in enemigo:
            enemigo["vida"] = enemigo.get("vida_actual", enemigo.get("vida_max", 100))
        if "vida_max" not in enemigo:
            enemigo["vida_max"] = enemigo.get("vida", 100)
        if "vida_actual" not in enemigo:
            enemigo["vida_actual"] = enemigo["vida"]
        # Alinear todas las claves de HP
        enemigo["vida"] = enemigo["vida_actual"]
    # Crear combate simple
    combate_id = f"{atacante_id}.{defensor_id}.{int(datetime.now().timestamp())}"
    vida_at, daño_at, defensa_at = obtener_estadisticas_jugador(atacante_id)
    # Sincronizar hp_max en DB para evitar desincronía entre combate y perfil
    db_helper.actualizar_jugador(atacante_id, hp_max=vida_at)
    jug_at = db_helper.obtener_jugador(atacante_id)
    vida_actual_at = min(jug_at["hp_actual"] if jug_at else vida_at, vida_at)
    if tipo_combate.startswith("pve") and enemigo:
        vida_max_def = enemigo["vida_max"]
        vida_actual_def = enemigo["vida"]
        daño_def = enemigo["daño"]
        defensa_def = enemigo.get("defensa", 0)
    else:
        vida_max_def, daño_def, defensa_def = obtener_estadisticas_jugador(defensor_id)
        jug_def = db_helper.obtener_jugador(defensor_id)
        vida_actual_def = min(jug_def["hp_actual"], vida_max_def) if jug_def else vida_max_def
    combates_activos[combate_id] = {
        "atacante_id": atacante_id,
        "defensor_id": defensor_id,
        "tipo": tipo_combate,
        "turno": 0,
        "vida_atacante": vida_actual_at,
        "vida_defensor": vida_actual_def,
        "vida_max_atacante": vida_at,
        "vida_max_defensor": vida_max_def,
        "daño_atacante": daño_at,
        "daño_defensor": daño_def,
        "defensa_atacante": defensa_at,
        "defensa_defensor": defensa_def,
        "ultima_accion": datetime.now(),
        "enemigo_data": enemigo if tipo_combate.startswith("pve") else None,
        "datos_extra": datos_extra or {},
        "modo": "simple",
        "en_grupo": False,
        "prob_huida": datos_extra.get("prob_huida", HUIR_PROB_BASE.get(tipo_combate, 0.5)) if tipo_combate.startswith("pve") else 0,
        "restricciones": _snapshot_restricciones,
    }
    # Marcar como ocupado en DB
    db_helper.set_actividad(atacante_id, "combate")
    if defensor_id and defensor_id != 0:
        db_helper.set_actividad(defensor_id, "combate")
    await mostrar_mensaje_combate(update, context, combate_id)

def _barra_vida(actual: int, maximo: int, longitud: int = 8) -> str:
    if maximo <= 0:
        return "░" * longitud
    lleno = max(0, min(longitud, int(longitud * actual / maximo)))
    return "█" * lleno + "░" * (longitud - lleno)

def _construir_panel_pve(combate_id: str) -> tuple:
    """Devuelve (texto, InlineKeyboardMarkup) del panel PvE para editar en lugar de enviar mensaje nuevo."""
    combate = combates_activos.get(combate_id)
    if not combate:
        return "El combate ha terminado.", None
    enemigo_data = combate["enemigo_data"]
    nombre = enemigo_data["nombre"]
    vida_e = combate["vida_defensor"]
    vida_e_max = combate["vida_max_defensor"]
    daño_e = combate["daño_defensor"]
    def_e = combate["defensa_defensor"]
    barra_e = _barra_vida(vida_e, vida_e_max)
    vida_j = combate["vida_atacante"]
    vida_j_max = combate["vida_max_atacante"]
    barra_j = _barra_vida(vida_j, vida_j_max)
    descripcion = enemigo_data.get("descripcion", "")
    xp = enemigo_data.get("xp", 0)
    oro = enemigo_data.get("oro", 0)
    texto = (
        f"⚔️ *{nombre}*\n"
        f"❤️ `{barra_e}` {vida_e}/{vida_e_max}\n"
        f"⚔️ Daño: *{daño_e}*  🛡️ Defensa: *{def_e}*\n"
    )
    if descripcion:
        texto += f"📖 _{descripcion}_\n"
    texto += (
        f"🏆 Recompensa: *{xp} XP* · *{oro} oro*\n"
        f"\n"
        f"👤 *Tú*\n"
        f"❤️ `{barra_j}` {vida_j}/{vida_j_max}\n"
    )
    tipo = combate["tipo"]
    prob_huida = combate.get("prob_huida", 0)
    _rest = combate.get("restricciones", {})
    _permit_hab  = _rest.get("habilidades_pve", True)
    _permit_huir = _rest.get("huir", True)
    keyboard = [
        [InlineKeyboardButton("⚔️ Atacar", callback_data=f"combate_accion_{combate_id}_ataque")],
    ]
    if _permit_hab:
        keyboard.append([
            InlineKeyboardButton("✨ Habilidad 1", callback_data=f"combate_accion_{combate_id}_habilidad1"),
            InlineKeyboardButton("🔮 Habilidad 2", callback_data=f"combate_accion_{combate_id}_habilidad2"),
        ])
    keyboard.append([InlineKeyboardButton("🧪 Usar poción", callback_data=f"combate_accion_{combate_id}_pocion")])
    if _permit_huir and prob_huida > 0:
        pct = int(prob_huida * 100)
        keyboard.append([InlineKeyboardButton(f"🏃 Huir ({pct}% éxito)", callback_data=f"combate_accion_{combate_id}_huir")])
    keyboard.append([InlineKeyboardButton("🔄 Actualizar", callback_data=f"combate_refresh_{combate_id}")])
    return texto, InlineKeyboardMarkup(keyboard)


async def mostrar_mensaje_combate(update: Update, context: ContextTypes.DEFAULT_TYPE, combate_id: str):
    combate = combates_activos.get(combate_id)
    if not combate:
        return
    tipo = combate["tipo"]
    prob_huida = combate.get("prob_huida", 0)
    if tipo.startswith("pve"):
        texto, markup = _construir_panel_pve(combate_id)
    else:
        defensor = db_helper.obtener_jugador(combate["defensor_id"])
        nombre_def = defensor["nombre_personaje"] if defensor else "?"
        vida_e = combate["vida_defensor"]
        vida_e_max = combate["vida_max_defensor"]
        barra_e = _barra_vida(vida_e, vida_e_max)
        vida_j = combate["vida_atacante"]
        vida_j_max = combate["vida_max_atacante"]
        barra_j = _barra_vida(vida_j, vida_j_max)
        texto = (
            f"⚔️ *Duelo vs {nombre_def}*\n"
            f"❤️ Rival `{barra_e}` {vida_e}/{vida_e_max}\n"
            f"🛡️ Def rival: *{combate['defensa_defensor']}*\n"
            f"\n"
            f"👤 *Tú*\n"
            f"❤️ `{barra_j}` {vida_j}/{vida_j_max}\n"
        )
        _rest = combate.get("restricciones", {})
        _permit_hab  = _rest.get("habilidades_pvp", True)
        _permit_huir = _rest.get("huir", True)
        keyboard = [
            [InlineKeyboardButton("⚔️ Atacar", callback_data=f"combate_accion_{combate_id}_ataque")],
        ]
        if _permit_hab:
            keyboard.append([
                InlineKeyboardButton("✨ Habilidad 1", callback_data=f"combate_accion_{combate_id}_habilidad1"),
                InlineKeyboardButton("🔮 Habilidad 2", callback_data=f"combate_accion_{combate_id}_habilidad2"),
            ])
        keyboard.append([InlineKeyboardButton("🧪 Usar poción", callback_data=f"combate_accion_{combate_id}_pocion")])
        if _permit_huir and prob_huida > 0 and not tipo.startswith("caza"):
            pct = int(prob_huida * 100)
            keyboard.append([InlineKeyboardButton(f"🏃 Huir ({pct}% éxito)", callback_data=f"combate_accion_{combate_id}_huir")])
        if tipo == COMBATE_PVP_AMISTOSO:
            keyboard.append([InlineKeyboardButton("🏳️ Rendirse", callback_data=f"combate_accion_{combate_id}_rendirse")])
        markup = InlineKeyboardMarkup(keyboard)
    await update.effective_message.reply_text(texto, reply_markup=markup, parse_mode="Markdown")

async def _enviar_panel_pvp_a(context, combate_id: str, chat_id: int):
    """Envía el panel de combate PvP directamente a un chat_id (para el retador)."""
    combate = combates_activos.get(combate_id)
    if not combate:
        return
    tipo = combate["tipo"]
    defensor = db_helper.obtener_jugador(combate["defensor_id"])
    nombre_def = defensor["nombre_personaje"] if defensor else "?"
    vida_e = combate["vida_defensor"]
    vida_e_max = combate["vida_max_defensor"]
    barra_e = _barra_vida(vida_e, vida_e_max)
    vida_j = combate["vida_atacante"]
    vida_j_max = combate["vida_max_atacante"]
    barra_j = _barra_vida(vida_j, vida_j_max)
    texto = (
        f"⚔️ *Duelo vs {nombre_def}*\n"
        f"❤️ Rival `{barra_e}` {vida_e}/{vida_e_max}\n"
        f"🛡️ Def rival: *{combate['defensa_defensor']}*\n"
        f"\n"
        f"👤 *Tú*\n"
        f"❤️ `{barra_j}` {vida_j}/{vida_j_max}\n"
    )
    _rest_pvp = combate.get("restricciones", {})
    _permit_hab_pvp = _rest_pvp.get("habilidades", True)
    keyboard = [
        [InlineKeyboardButton("⚔️ Atacar", callback_data=f"combate_accion_{combate_id}_ataque")],
    ]
    if _permit_hab_pvp:
        keyboard.append([
            InlineKeyboardButton("✨ Habilidad 1", callback_data=f"combate_accion_{combate_id}_habilidad1"),
            InlineKeyboardButton("🔮 Habilidad 2", callback_data=f"combate_accion_{combate_id}_habilidad2"),
        ])
    keyboard.append([InlineKeyboardButton("🧪 Usar poción", callback_data=f"combate_accion_{combate_id}_pocion")])
    if tipo == COMBATE_PVP_AMISTOSO:
        keyboard.append([InlineKeyboardButton("🏳️ Rendirse", callback_data=f"combate_accion_{combate_id}_rendirse")])
    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text=texto,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    except Exception:
        pass


def _construir_panel_pvp(combate_id: str, viewer_id: int) -> tuple:
    """
    Devuelve (texto, InlineKeyboardMarkup) del panel PvP desde la perspectiva de viewer_id.
    viewer_id puede ser el atacante_id o el defensor_id del combate.
    """
    combate = combates_activos.get(combate_id)
    if not combate:
        return "El combate ya terminó.", None

    tipo = combate["tipo"]
    es_atacante = (viewer_id == combate["atacante_id"])
    rival_id = combate["defensor_id"] if es_atacante else combate["atacante_id"]
    rival = db_helper.obtener_jugador(rival_id)
    nombre_rival = rival["nombre_personaje"] if rival else "?"

    if es_atacante:
        vida_yo     = combate["vida_atacante"]
        vida_yo_max = combate["vida_max_atacante"]
        vida_rival     = combate["vida_defensor"]
        vida_rival_max = combate["vida_max_defensor"]
        def_rival   = combate["defensa_defensor"]
    else:
        vida_yo     = combate["vida_defensor"]
        vida_yo_max = combate["vida_max_defensor"]
        vida_rival     = combate["vida_atacante"]
        vida_rival_max = combate["vida_max_atacante"]
        def_rival   = combate["defensa_atacante"]

    barra_rival = _barra_vida(vida_rival, vida_rival_max)
    barra_yo    = _barra_vida(vida_yo, vida_yo_max)

    es_mi_turno = (combate["turno"] == 0 and es_atacante) or \
                  (combate["turno"] == 1 and not es_atacante)
    turno_txt = "🎯 *¡Es tu turno!*" if es_mi_turno else "⏳ *Esperando al rival...*"

    texto = (
        f"⚔️ *Duelo vs {nombre_rival}*\n"
        f"❤️ Rival `{barra_rival}` {vida_rival}/{vida_rival_max}\n"
        f"🛡️ Def rival: *{def_rival}*\n"
        f"\n"
        f"👤 *Tú*\n"
        f"❤️ `{barra_yo}` {vida_yo}/{vida_yo_max}\n"
        f"\n{turno_txt}\n"
    )

    _rest_pvp2 = combate.get("restricciones", {})
    _permit_hab_pvp2 = _rest_pvp2.get("habilidades_pvp", True)
    keyboard = [
        [InlineKeyboardButton("⚔️ Atacar", callback_data=f"combate_accion_{combate_id}_ataque")],
    ]
    if _permit_hab_pvp2:
        keyboard.append([
            InlineKeyboardButton("✨ Habilidad 1", callback_data=f"combate_accion_{combate_id}_habilidad1"),
            InlineKeyboardButton("🔮 Habilidad 2", callback_data=f"combate_accion_{combate_id}_habilidad2"),
        ])
    keyboard.append([InlineKeyboardButton("🧪 Usar poción", callback_data=f"combate_accion_{combate_id}_pocion")])
    if tipo == COMBATE_PVP_AMISTOSO:
        keyboard.append([InlineKeyboardButton("🏳️ Rendirse", callback_data=f"combate_accion_{combate_id}_rendirse")])
    keyboard.append([InlineKeyboardButton("🔄 Actualizar", callback_data=f"pvp_refresh_{combate_id}_{viewer_id}")])

    return texto, InlineKeyboardMarkup(keyboard)


async def _notificar_pvp(context, combate_id: str, chat_id: int, viewer_id: int, prefijo: str = ""):
    """Envía mensaje nuevo con el panel PvP actualizado a chat_id."""
    texto, markup = _construir_panel_pvp(combate_id, viewer_id)
    if prefijo:
        texto = prefijo + "\n\n" + texto
    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text=texto,
            reply_markup=markup,
            parse_mode="Markdown"
        )
    except Exception:
        pass

async def procesar_accion_combate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    parts = data.split("_")
    combate_id = parts[2]
    accion = parts[3]
    combate = combates_activos.get(combate_id)
    if not combate:
        await query.edit_message_text("El combate ya ha terminado.")
        return
    user_id = update.effective_user.id
    es_turno = (combate["turno"] == 0 and user_id == combate["atacante_id"]) or \
               (combate["turno"] == 1 and user_id == combate["defensor_id"])
    if not es_turno:
        # Mostrar panel actualizado con indicador de espera en lugar de solo texto
        await query.answer("⏳ Aún no es tu turno.", show_alert=False)
        texto_panel, markup_panel = _construir_panel_pvp(combate_id, user_id)
        try:
            await query.edit_message_text(texto_panel, reply_markup=markup_panel, parse_mode="Markdown")
        except Exception:
            pass
        return
    if (datetime.now() - combate["ultima_accion"]).total_seconds() > TIEMPO_TURNO:
        ganador = combate["defensor_id"] if user_id == combate["atacante_id"] else combate["atacante_id"]
        await query.edit_message_text("⏰ Has tardado demasiado. Pierdes el combate.")
        await finalizar_combate(update, context, combate_id, ganador)
        return
    combate["ultima_accion"] = datetime.now()
    if user_id == combate["atacante_id"]:
        daño_base = combate["daño_atacante"]
        defensa_enemigo = combate["defensa_defensor"]
    else:
        daño_base = combate["daño_defensor"]
        defensa_enemigo = combate["defensa_atacante"]
    mensaje = ""
    _rest_accion = combate.get("restricciones", {})
    _criticos_ok = _rest_accion.get("criticos", True)
    _huir_ok     = _rest_accion.get("huir", True)
    _tipo_accion = combate.get("tipo", "")
    if _tipo_accion.startswith("pve"):
        _habs_ok = _rest_accion.get("habilidades_pve", True)
    elif _tipo_accion in PENALIZACIONES_PVP:
        _habs_ok = _rest_accion.get("habilidades_pvp", True)
    else:
        _habs_ok = True
    if accion == "ataque":
        daño = calcular_daño(daño_base, defensa_enemigo, False, permitir_critico=_criticos_ok)
        if user_id == combate["atacante_id"]:
            combate["vida_defensor"] -= daño
        else:
            combate["vida_atacante"] -= daño
        mensaje = f"⚔️ Causas {daño} de daño."
    elif accion == "habilidad1":
        if not _habs_ok:
            mensaje = "🚫 Las habilidades están restringidas temporalmente."
        else:
            jug = db_helper.obtener_jugador(user_id)
            if jug:
                habilidades = clases.obtener_habilidades_activas(jug["clase"])
                if habilidades:
                    hab = habilidades[0]
                    _d1 = max(1, hab.get("daño", 10))
                    daño = random.randint(max(1, _d1-5), _d1+5)
                    daño = calcular_daño(daño, defensa_enemigo, True, permitir_critico=_criticos_ok)
                    if user_id == combate["atacante_id"]:
                        combate["vida_defensor"] -= daño
                    else:
                        combate["vida_atacante"] -= daño
                    mensaje = f"✨ Usas {hab['nombre']} y causas {daño} de daño."
                else:
                    mensaje = "❌ No tienes habilidades activas."
    elif accion == "habilidad2":
        if not _habs_ok:
            mensaje = "🚫 Las habilidades están restringidas temporalmente."
        else:
            jug = db_helper.obtener_jugador(user_id)
            if jug:
                habilidades = clases.obtener_habilidades_activas(jug["clase"])
                if len(habilidades) >= 2:
                    hab = habilidades[1]
                    if "cura" in hab and hab["cura"] > 0:
                        cura = max(0, hab["cura"] + random.randint(-5, 5))
                        if user_id == combate["atacante_id"]:
                            combate["vida_atacante"] = min(combate["vida_max_atacante"], combate["vida_atacante"]+cura)
                        else:
                            combate["vida_defensor"] = min(combate["vida_max_defensor"], combate["vida_defensor"]+cura)
                        mensaje = f"🔮 Usas {hab['nombre']} y recuperas {cura} de vida."
                    elif "daño" in hab:
                        _d2 = max(1, hab.get("daño", 10))
                        daño = random.randint(max(1, _d2-5), _d2+5)
                        daño = calcular_daño(daño, defensa_enemigo, True, permitir_critico=_criticos_ok)
                        if user_id == combate["atacante_id"]:
                            combate["vida_defensor"] -= daño
                        else:
                            combate["vida_atacante"] -= daño
                        mensaje = f"🔮 Usas {hab['nombre']} y causas {daño} de daño."
                    else:
                        mensaje = f"🔮 Usas {hab['nombre']}. Su efecto especial está activo."
                else:
                    mensaje = "❌ No tienes segunda habilidad."
    elif accion == "pocion":
        inv = db_helper.obtener_inventario(user_id)
        pocion = None
        for item in inv:
            if "pocion" in item["nombre"].lower() and ("vida" in item["nombre"].lower() or "curativa" in item["nombre"].lower()):
                pocion = item["nombre"]
                break
        if not pocion:
            mensaje = "❌ No tienes ninguna poción de vida."
        else:
            ok, msg = inventario.usar_consumible(user_id, pocion, 1)
            if ok:
                stats = _obtener_estadisticas_objeto_real(pocion)
                cura_str = stats.get("efecto", "")
                try:
                    curacion = int(''.join(filter(str.isdigit, cura_str)))
                except:
                    curacion = 30
                if user_id == combate["atacante_id"]:
                    combate["vida_atacante"] = min(combate["vida_max_atacante"], combate["vida_atacante"]+curacion)
                else:
                    combate["vida_defensor"] = min(combate["vida_max_defensor"], combate["vida_defensor"]+curacion)
                mensaje = f"🧪 Usas {pocion}. Recuperas {curacion} de vida."
            else:
                mensaje = f"❌ {msg}"
    elif accion == "huir":
        if not _huir_ok:
            mensaje = "🚫 Huir está restringido temporalmente. ¡Sigue luchando!"
        else:
            prob = combate.get("prob_huida", 0.5)
            if random.random() < prob:
                await query.edit_message_text("🏃 ¡Has huido del combate!")
                del combates_activos[combate_id]
                return
            else:
                mensaje = "⚠️ Fallaste al huir. El enemigo ataca."
                daño = calcular_daño(daño_base, defensa_enemigo, False, permitir_critico=_criticos_ok)
                if user_id == combate["atacante_id"]:
                    combate["vida_atacante"] -= daño
                else:
                    combate["vida_defensor"] -= daño
    elif accion == "rendirse":
        ganador = combate["defensor_id"] if user_id == combate["atacante_id"] else combate["atacante_id"]
        await finalizar_combate(update, context, combate_id, ganador)
        return
    # ── Contrataque automático del monstruo (PvE) ──────────────────────
    # En PvE el monstruo siempre responde inmediatamente; nunca hay "turno del monstruo"
    # porque el monstruo no tiene Update para pulsar botón.
    if combate["tipo"].startswith("pve") and accion not in ("huir", "rendirse"):
        if combate["vida_defensor"] > 0:
            _edata = combate.get("enemigo_data") or {}
            _nombre_mon = _edata.get("nombre", "El monstruo")
            daño_mon = calcular_daño(
                combate["daño_defensor"],
                combate["defensa_atacante"],
                False,
                permitir_critico=_criticos_ok
            )
            combate["vida_atacante"] -= daño_mon
            mensaje += f"\n🐾 *{_nombre_mon}* contraataca y te causa *{daño_mon}* de daño."

    if combate["vida_atacante"] <= 0:
        await query.edit_message_text(mensaje, parse_mode="Markdown")
        await finalizar_combate(update, context, combate_id, combate["defensor_id"])
        return
    if combate["vida_defensor"] <= 0:
        await query.edit_message_text(mensaje, parse_mode="Markdown")
        await finalizar_combate(update, context, combate_id, combate["atacante_id"])
        return
    # En PvE el turno siempre es del jugador (0); en PvP alternamos
    if not combate["tipo"].startswith("pve"):
        combate["turno"] = 1 - combate["turno"]

    # ── Actualizar panel en el mismo mensaje ────────────────────────────
    if not combate["tipo"].startswith("pve"):
        atacante_id = combate["atacante_id"]
        defensor_id = combate["defensor_id"]
        rival_id = defensor_id if user_id == atacante_id else atacante_id

        # Editar el mensaje del jugador que actuó con resultado + panel actualizado
        texto_self, markup_self = _construir_panel_pvp(combate_id, user_id)
        try:
            await query.edit_message_text(
                mensaje + "\n\n" + texto_self,
                reply_markup=markup_self,
                parse_mode="Markdown"
            )
        except Exception:
            pass

        # Enviar nuevo panel al rival (su turno ahora)
        rival_jug = db_helper.obtener_jugador(user_id)
        nombre_atacante = rival_jug["nombre_personaje"] if rival_jug else "Tu rival"
        prefijo = f"⚔️ *{_esc_md(nombre_atacante)}* actuó.\n🎯 *¡Ahora es tu turno!*"
        await _notificar_pvp(context, combate_id, rival_id, rival_id, prefijo=prefijo)
    else:
        # PvE: editar el mismo mensaje con resultado + panel actualizado con barras
        texto_panel, markup_panel = _construir_panel_pve(combate_id)
        try:
            await query.edit_message_text(
                mensaje + "\n\n" + texto_panel,
                reply_markup=markup_panel,
                parse_mode="Markdown"
            )
        except Exception:
            pass

async def finalizar_combate(update: Update, context: ContextTypes.DEFAULT_TYPE, combate_id: str, ganador_id: int):
    combate = combates_activos.pop(combate_id, None)
    if not combate:
        return
    perdedor_id = combate["defensor_id"] if ganador_id == combate["atacante_id"] else combate["atacante_id"]
    tipo = combate["tipo"]
    if tipo.startswith("pve"):
        enemigo = combate["enemigo_data"]
        if ganador_id != 0:
            # ── Jugador victorioso ──────────────────────────────────────────
            xp = enemigo.get("xp", 0)
            oro = enemigo.get("oro", 0)
            drops = enemigo.get("drops", [])
            datos_extra = {"xp": xp, "oro": oro, "drops": drops}
            items_obtenidos = aplicar_recompensa_ganador(ganador_id, tipo, datos_extra)
            # Hook misiones PvE
            try:
                import misiones as _mis
                _mis.completar_mision(ganador_id, "primer_combate", context)
            except Exception:
                pass
            # Hook misiones diarias — contabilizar kill
            try:
                import misiones_diarias as _md
                _md.registrar_progreso(ganador_id, "matar", 1)
            except Exception:
                pass
            # Hook resumen_sesion — contabilizar kill, oro y xp ganados
            try:
                import resumen_sesion as _rs
                _rs.registrar_monstruo(ganador_id)
                if oro > 0:
                    _rs.registrar_oro(ganador_id, oro)
                if xp > 0:
                    _rs.registrar_xp(ganador_id, xp)
                for _n_it, _q_it in items_obtenidos:
                    _rs.registrar_item(ganador_id, _n_it)
            except Exception:
                pass
            if items_obtenidos:
                drops_lineas = "\n".join(f"  • {n}: *x{c}*" for n, c in items_obtenidos)
                drops_txt = f"\n📦 *Objetos obtenidos:*\n{drops_lineas}"
            elif drops:
                drops_txt = "\n📦 No obtuviste objetos esta vez."
            else:
                drops_txt = ""
            await update.effective_message.reply_text(
                f"⚔️ *¡Victoria!*\n"
                f"Derrotaste a {enemigo.get('nombre', 'el enemigo')}.\n"
                f"✨ Experiencia: *+{xp}*\n"
                f"🪙 Oro: *+{oro}*"
                f"{drops_txt}",
                parse_mode="Markdown"
            )
            # Hook item_comparar — comparar armas/armaduras obtenidas con el equipo actual
            try:
                import item_comparar as _ic
                for _nombre_drop, _cant_drop in items_obtenidos:
                    _cmp_txt = _ic.comparar_item(ganador_id, _nombre_drop)
                    if _cmp_txt:
                        await update.effective_message.reply_text(_cmp_txt, parse_mode="HTML")
            except Exception:
                pass
        else:
            # ── Jugador derrotado — penalización y respawn en ciudad ────────
            jugador_id = perdedor_id
            jug_data = db_helper.obtener_jugador(jugador_id)
            if jug_data:
                oro_actual = jug_data.get("oro", 0)
                import config_db as _cfgdb_pve
                _pve_zona_cfg = {
                    COMBATE_PVE_AZUL:     "pve_muerte_oro_azul",
                    COMBATE_PVE_AMARILLA: "pve_muerte_oro_amarilla",
                    COMBATE_PVE_ROJA:     "pve_muerte_oro_roja",
                    COMBATE_PVE_NEGRA:    "pve_muerte_oro_negra",
                }
                _pve_pct = _cfgdb_pve.get(_pve_zona_cfg.get(tipo, "pve_muerte_oro_azul"), 15) / 100.0
                oro_perdido_pve = max(0, int(oro_actual * _pve_pct))
                if oro_perdido_pve > 0:
                    economia.modificar_saldo(jugador_id, "oro", -oro_perdido_pve, "derrota en combate PvE")
                nombre_enemigo_pve = enemigo.get("nombre", "el monstruo") if enemigo else "el monstruo"
                await _manejar_muerte_jugador(
                    jugador_id, context,
                    nombre_enemigo=nombre_enemigo_pve,
                    tipo_combate=tipo,
                    oro_perdido=oro_perdido_pve
                )
        # Abrir ventana post-combate para meditación
        _color_map = {'pve_zona_azul': 'azul', 'pve_zona_amarilla': 'amarilla', 'pve_zona_roja': 'roja', 'pve_zona_negra': 'negra'}
        _color_pve = _color_map.get(tipo)
        if _color_pve:
            try:
                import sistema_paz as _sp
                _sp.abrir_ventana_post_combate(ganador_id, _color_pve)
            except Exception:
                pass
    elif tipo in PENALIZACIONES_PVP:
        _aplicar_perdidas_y_transferir(perdedor_id, ganador_id, tipo)
        xp = _calcular_xp_pvp(perdedor_id)
        _otorgar_experiencia(ganador_id, xp)
        oro_perdido = int(_obtener_oro_encima(perdedor_id) * PENALIZACIONES_PVP[tipo]["oro_porcentaje"])
        # Hook logros PvP
        try:
            import logros as _logros
            _logros.registrar_victoria_pvp(ganador_id)
            _logros.registrar_derrota_pvp(perdedor_id)
            _logros.registrar_muerte(perdedor_id)
        except Exception:
            pass
        # ── Sistema de Caza: registrar asesinato por zona ───────────────────
        _zona_pvp_map = {
            COMBATE_PVP_AMARILLA: "amarilla",
            COMBATE_PVP_ROJA: "roja",
            COMBATE_PVP_NEGRA: "negra",
        }
        _zona_caza = _zona_pvp_map.get(tipo)
        if _zona_caza:
            try:
                asyncio.create_task(registrar_asesinato(ganador_id, perdedor_id, _zona_caza))
            except Exception:
                pass
        # Hook misiones PvP
        try:
            import misiones as _mis
            _mis.completar_mision(ganador_id, "primer_combate", context)
            _mis.completar_mision(ganador_id, "ganar_duelo", context)
        except Exception:
            pass
        _jug_g = db_helper.obtener_jugador(ganador_id)
        _jug_p = db_helper.obtener_jugador(perdedor_id)
        nombre_g = _jug_g["nombre_personaje"] if _jug_g else str(ganador_id)
        nombre_p = _jug_p["nombre_personaje"] if _jug_p else str(perdedor_id)
        await update.effective_message.reply_text(
            f"⚔️ *Combate finalizado*\n"
            f"Ganador: {nombre_g}\n"
            f"Perdedor: {nombre_p}\n"
            f"🪙 Ganaste {oro_perdido} de oro.\n✨ +{xp} de experiencia.",
            parse_mode="Markdown"
        )
    elif tipo == COMBATE_PVP_AMISTOSO:
        await update.effective_message.reply_text("🏆 El duelo amistoso ha terminado. ¡Buen combate!")
    else:
        await update.effective_message.reply_text("Combate finalizado.")
    # Guia contextual PvP
    if tipo in PENALIZACIONES_PVP:
        try:
            import guia_contextual as _gc
            await _gc.enviar(ganador_id, context, "combate_pvp_victoria")
            await _gc.enviar(perdedor_id, context, "combate_pvp_derrota")
        except Exception:
            pass
    db_helper.actualizar_jugador(ganador_id, hp_actual=combate["vida_atacante"] if ganador_id == combate["atacante_id"] else combate["vida_defensor"])
    # Teleportar y notificar al perdedor PvP si corresponde
    if tipo in PENALIZACIONES_PVP and perdedor_id and perdedor_id != 0:
        _jug_p_data = db_helper.obtener_jugador(perdedor_id)
        _oro_perd_pvp = max(0, int(_obtener_oro_encima(perdedor_id) * _get_penalizacion_pvp(tipo)["oro_porcentaje"])) if _jug_p_data else 0
        await _manejar_muerte_jugador(
            perdedor_id, context,
            nombre_enemigo=db_helper.obtener_jugador(ganador_id)["nombre_personaje"] if db_helper.obtener_jugador(ganador_id) else "tu rival",
            tipo_combate=tipo,
            oro_perdido=_oro_perd_pvp
        )
    else:
        db_helper.actualizar_jugador(perdedor_id, hp_actual=combate["vida_atacante"] if perdedor_id == combate["atacante_id"] else combate["vida_defensor"])
        # Liberar estado ocupado para ambos jugadores
        db_helper.set_actividad(ganador_id, None)
        if perdedor_id and perdedor_id != 0:
            db_helper.set_actividad(perdedor_id, None)

def aplicar_recompensa_ganador(user_id: int, tipo_combate: str, datos_extra: dict) -> list:
    """Aplica recompensas y retorna lista de (nombre, cantidad) de drops obtenidos."""
    xp = datos_extra.get("xp", 0)
    if xp > 0:
        _otorgar_experiencia(user_id, xp)
    oro = datos_extra.get("oro", 0)
    if oro > 0:
        economia.modificar_saldo(user_id, "oro", oro, f"recompensa combate {tipo_combate}")
    drops = datos_extra.get("drops", [])
    items_obtenidos = []
    for drop in drops:
        nombre = drop["nombre"]
        prob = drop.get("probabilidad", 1.0)
        if random.random() > prob:
            continue
        cantidad = random.randint(drop.get("min", 1), drop.get("max", 1))
        db_helper.agregar_item(user_id, nombre, cantidad)
        items_obtenidos.append((nombre, cantidad))
    return items_obtenidos

# ==================== SISTEMA DE CAZA (COMPLETO) ====================
def _init_caza_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    for zona in ["amarilla", "roja", "negra"]:
        try:
            c.execute(f'ALTER TABLE jugadores ADD COLUMN asesinatos_{zona} INTEGER DEFAULT 0')
        except sqlite3.OperationalError:
            pass
    c.execute('''CREATE TABLE IF NOT EXISTS eventos_caza (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        zona TEXT,
        asesino_id INTEGER,
        asesino_nombre TEXT,
        pelea_iniciada BOOLEAN DEFAULT 0,
        inicio TIMESTAMP,
        fin TIMESTAMP
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS cazadores_invitados (
        evento_id INTEGER,
        cazador_id INTEGER,
        aceptado BOOLEAN DEFAULT 0,
        PRIMARY KEY (evento_id, cazador_id)
    )''')
    conn.commit()
    conn.close()
_init_caza_db()

def _incrementar_asesinato(user_id, zona):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(f'UPDATE jugadores SET asesinatos_{zona} = asesinatos_{zona} + 1 WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

def _resetear_asesinatos(user_id, zona):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(f'UPDATE jugadores SET asesinatos_{zona} = 0 WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

def _obtener_asesinatos(user_id, zona):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(f'SELECT asesinatos_{zona} FROM jugadores WHERE user_id = ?', (user_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0

async def registrar_asesinato(asesino_id, victima_id, zona_color):
    if zona_color not in ("amarilla", "roja", "negra"):
        return
    _incrementar_asesinato(asesino_id, zona_color)
    kills = _obtener_asesinatos(asesino_id, zona_color)
    limite = {"amarilla":2, "roja":4, "negra":6}[zona_color]
    if kills >= limite:
        await iniciar_caza(asesino_id, zona_color)

async def iniciar_caza(asesino_id, zona_color):
    # Evitar múltiples eventos en la misma zona
    for ev in eventos_caza.values():
        if ev["zona"] == zona_color and ev["fase"] != "terminado":
            return
    jug = db_helper.obtener_jugador(asesino_id)
    if not jug:
        return
    zona_nombre = jug.get("zona_actual", "")
    zona_data = next((z for z in ZONAS if z["nombre"] == zona_nombre and z["color"] == zona_color), None)
    if not zona_data:
        return
    zona_id = zona_data["id"]
    evento_id = random.randint(1000, 9999)  # ID simple para el evento
    eventos_caza[evento_id] = {
        "id": evento_id,
        "zona": zona_color,
        "zona_nombre": zona_nombre,
        "asesino_id": asesino_id,
        "asesino_nombre": jug["nombre_personaje"],
        "cazadores": [],  # lista de user_ids
        "fase": "espera",  # espera, combate, terminado
        "inicio": datetime.now(),
        "limite_cazadores": {"amarilla":3, "roja":2, "negra":1}[zona_color],
        "combate_id": None,
        "monstruo_asesino": None,  # se creará al iniciar combate
    }
    # Notificar a jugadores en la misma zona usando el bot global
    if _bot_context is None:
        print("ERROR: _bot_context no inicializado")
        return
    all_jugadores = db_helper.obtener_todos_jugadores()
    for jugador in all_jugadores:
        if jugador.get("zona_actual") == zona_nombre and jugador["user_id"] != asesino_id:
            texto = f"⚠️ ¡Un asesino ({jug['nombre_personaje']}) ha aparecido en {zona_nombre}!\n"
            texto += f"Los cazadores pueden unirse con /unirse_caza durante {TIEMPO_UNIRSE_CAZA} segundos."
            await _bot_context.bot.send_message(chat_id=jugador["user_id"], text=texto)
    asyncio.create_task(_iniciar_fase_combate_caza(evento_id))

async def _iniciar_fase_combate_caza(evento_id):
    await asyncio.sleep(TIEMPO_UNIRSE_CAZA)
    ev = eventos_caza.get(evento_id)
    if not ev or ev["fase"] != "espera":
        return
    if len(ev["cazadores"]) == 0:
        _resetear_asesinatos(ev["asesino_id"], ev["zona"])
        if _bot_context:
            await _bot_context.bot.send_message(chat_id=ev["asesino_id"], text="No se unieron cazadores a tiempo. Tu contador de asesinatos se ha reiniciado.")
        del eventos_caza[evento_id]
        return
    ev["fase"] = "combate"
    # Crear el monstruo (asesino) con stats basadas en el jugador asesino
    asesino_id = ev["asesino_id"]
    jug = db_helper.obtener_jugador(asesino_id)
    vida_max, daño, defensa = obtener_estadisticas_jugador(asesino_id)
    # Escalar un poco para que sea un desafío grupal
    mult = 1 + (len(ev["cazadores"]) * 0.3)
    vida = int(vida_max * mult)
    daño = int(daño * (1 + len(ev["cazadores"])*0.2))
    defensa = int(defensa * (1 + len(ev["cazadores"])*0.1))
    monstruo = {
        "nombre": f"Asesino {ev['asesino_nombre']}",
        "descripcion": "Un peligroso criminal que acecha en la zona.",
        "vida": vida,
        "vida_max": vida,
        "daño": daño,
        "defensa": defensa,
        "xp": 500 + jug["nivel"]*20,
        "oro": 200 + jug["nivel"]*10,
        "drops": []  # No hay drops por ahora para asesinos
    }
    ev["monstruo_asesino"] = monstruo
    # Iniciar combate grupal
    await iniciar_combate_grupal_caza(ev)

async def iniciar_combate_grupal_caza(evento):
    # Creamos un combate grupal donde los cazadores atacan por turnos al asesino
    combate_id = f"z.{evento['id']}.{int(datetime.now().timestamp())}"
    evento["combate_id"] = combate_id
    # Estructura del combate grupal
    try:
        import restricciones_combate as _rc_caza
        _snap_caza = _rc_caza.get_snapshot()
    except Exception:
        _snap_caza = {}
    combates_activos[combate_id] = {
        "tipo": f"caza_{evento['zona']}",
        "fase": "turno_cazador",  # o "turno_asesino"
        "indice_turno": 0,
        "cazadores": evento["cazadores"],  # lista de user_ids
        "vidas_cazadores": {},
        "vidas_max_cazadores": {},
        "daños_cazadores": {},
        "defensas_cazadores": {},
        "asesino_data": evento["monstruo_asesino"],
        "vida_asesino": evento["monstruo_asesino"]["vida"],
        "vida_max_asesino": evento["monstruo_asesino"]["vida_max"],
        "evento_id": evento["id"],
        "estado": "activo",
        "restricciones": _snap_caza,
        "zona": evento.get("zona", ""),
        "asesino_nombre": evento.get("asesino_nombre", ""),
        "ultima_accion": datetime.now()
    }
    for uid in evento["cazadores"]:
        vida_max, daño, defensa = obtener_estadisticas_jugador(uid)
        jug = db_helper.obtener_jugador(uid)
        vida_actual = min(jug["hp_actual"] if jug else vida_max, vida_max)
        combates_activos[combate_id]["vidas_cazadores"][uid] = vida_actual
        combates_activos[combate_id]["vidas_max_cazadores"][uid] = vida_max
        combates_activos[combate_id]["daños_cazadores"][uid] = daño
        combates_activos[combate_id]["defensas_cazadores"][uid] = defensa
    # Notificar a todos
    if _bot_context:
        texto = f"⚔️ *¡Caza comenzó en {evento['zona_nombre']}!*\n"
        texto += f"Enemigo: {evento['monstruo_asesino']['nombre']}\n"
        texto += f"Vida: {evento['monstruo_asesino']['vida']}/{evento['monstruo_asesino']['vida_max']}\n"
        for uid in evento["cazadores"]:
            await _bot_context.bot.send_message(chat_id=uid, text=texto)
    await siguiente_turno_caza(combate_id)

async def siguiente_turno_caza(combate_id):
    combate = combates_activos.get(combate_id)
    if not combate or combate["estado"] != "activo":
        return
    if combate["fase"] == "turno_cazador":
        # Elegir siguiente cazador
        idx = combate["indice_turno"]
        if idx >= len(combate["cazadores"]):
            # Cambiar a turno del asesino
            combate["fase"] = "turno_asesino"
            combate["indice_turno"] = 0
            await realizar_ataque_asesino_caza(combate_id)
        else:
            uid = combate["cazadores"][idx]
            # Verificar que el cazador siga vivo
            if combate["vidas_cazadores"].get(uid, 0) <= 0:
                combate["indice_turno"] += 1
                await siguiente_turno_caza(combate_id)
                return
            # Pedir acción al cazador
            if _bot_context:
                keyboard = [[
                    InlineKeyboardButton("⚔️ Atacar", callback_data=f"caza_accion_{combate_id}_atacar_{uid}"),
                    InlineKeyboardButton("🧪 Usar poción", callback_data=f"caza_accion_{combate_id}_pocion_{uid}")
                ]]
                keyboard.append([InlineKeyboardButton("🔄 Actualizar", callback_data=f"caza_refresh_{combate_id}_{uid}")])
                b_as = _barra_vida(combate["vida_asesino"], combate["vida_max_asesino"])
                b_ca = _barra_vida(combate["vidas_cazadores"][uid], combate["vidas_max_cazadores"][uid])
                texto = (
                    f"🎯 *Tu turno en la caza*\n\n"
                    f"👹 *{_esc_md(combate['asesino_data']['nombre'])}*\n"
                    f"❤️ `{b_as}` {combate['vida_asesino']}/{combate['vida_max_asesino']}\n\n"
                    f"👤 *Tu vida*\n"
                    f"❤️ `{b_ca}` {combate['vidas_cazadores'][uid]}/{combate['vidas_max_cazadores'][uid]}\n"
                )
                await _bot_context.bot.send_message(chat_id=uid, text=texto, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
                # Timeout: 90 segundos
                asyncio.create_task(_timeout_turno_caza(combate_id, uid))
    else:
        # Turno asesino, ya se maneja en realizar_ataque_asesino_caza
        pass

async def _timeout_turno_caza(combate_id, uid):
    await asyncio.sleep(TIEMPO_TURNO)
    combate = combates_activos.get(combate_id)
    if combate and combate["estado"] == "activo" and combate["fase"] == "turno_cazador" and combate["cazadores"][combate["indice_turno"]] == uid:
        # Saltar turno
        if _bot_context:
            await _bot_context.bot.send_message(chat_id=uid, text="⏰ Has tardado demasiado. Pierdes tu turno.")
        combate["indice_turno"] += 1
        await siguiente_turno_caza(combate_id)

async def procesar_accion_caza(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    parts = data.split("_")
    combate_id = parts[2]
    accion = parts[3]
    uid = int(parts[4])
    if update.effective_user.id != uid:
        await query.edit_message_text("No es tu turno o no eres el jugador indicado.")
        return
    combate = combates_activos.get(combate_id)
    if not combate or combate["estado"] != "activo" or combate["fase"] != "turno_cazador" or combate["cazadores"][combate["indice_turno"]] != uid:
        await query.edit_message_text("No es tu turno ahora.")
        return
    def _panel_caza(resultado_txt):
        b_asesino = _barra_vida(combate["vida_asesino"], combate["vida_max_asesino"])
        b_cazador = _barra_vida(combate["vidas_cazadores"][uid], combate["vidas_max_cazadores"][uid])
        return (
            f"{resultado_txt}\n\n"
            f"👹 *{_esc_md(combate['asesino_data']['nombre'])}*\n"
            f"❤️ `{b_asesino}` {combate['vida_asesino']}/{combate['vida_max_asesino']}\n\n"
            f"👤 *Tu vida*\n"
            f"❤️ `{b_cazador}` {combate['vidas_cazadores'][uid]}/{combate['vidas_max_cazadores'][uid]}\n"
        )
    _permit_hab_caza = combate.get("restricciones", {}).get("habilidades_caza", True)
    kb_caza = [[
        InlineKeyboardButton("⚔️ Atacar", callback_data=f"caza_accion_{combate_id}_atacar_{uid}"),
        InlineKeyboardButton("🧪 Usar poción", callback_data=f"caza_accion_{combate_id}_pocion_{uid}")
    ]]
    if _permit_hab_caza:
        kb_caza.append([
            InlineKeyboardButton("✨ Habilidad 1", callback_data=f"caza_accion_{combate_id}_habilidad1_{uid}"),
            InlineKeyboardButton("🔮 Habilidad 2", callback_data=f"caza_accion_{combate_id}_habilidad2_{uid}"),
        ])
    kb_caza.append([InlineKeyboardButton("🔄 Actualizar", callback_data=f"caza_refresh_{combate_id}_{uid}")])
    if accion == "atacar":
        daño_cazador = combate["daños_cazadores"][uid]
        defensa_asesino = combate["asesino_data"]["defensa"]
        daño = calcular_daño(daño_cazador, defensa_asesino, False)
        combate["vida_asesino"] -= daño
        resultado = f"⚔️ Atacas al asesino y causas *{daño}* de daño."
        # Verificar si asesino muere
        if combate["vida_asesino"] <= 0:
            await query.edit_message_text(resultado + "\n💀 ¡Has derrotado al asesino!", parse_mode="Markdown")
            await finalizar_caza(combate_id, ganadores=True)
            return
        # Editar con panel actualizado
        try:
            await query.edit_message_text(_panel_caza(resultado), reply_markup=InlineKeyboardMarkup(kb_caza), parse_mode="Markdown")
        except Exception:
            pass
        # Siguiente turno
        combate["indice_turno"] += 1
        await siguiente_turno_caza(combate_id)
    elif accion == "pocion":
        inv = db_helper.obtener_inventario(uid)
        pocion = None
        for item in inv:
            if "pocion" in item["nombre"].lower() and ("vida" in item["nombre"].lower() or "curativa" in item["nombre"].lower()):
                pocion = item["nombre"]
                break
        if not pocion:
            await query.edit_message_text("❌ No tienes ninguna poción de vida.")
            return
        ok, msg = inventario.usar_consumible(uid, pocion, 1)
        if ok:
            stats = _obtener_estadisticas_objeto_real(pocion)
            cura_str = stats.get("efecto", "")
            try:
                curacion = int(''.join(filter(str.isdigit, cura_str)))
            except:
                curacion = 30
            combate["vidas_cazadores"][uid] = min(combate["vidas_max_cazadores"][uid], combate["vidas_cazadores"][uid] + curacion)
            resultado = f"🧪 Usas *{pocion}* y recuperas *{curacion}* de vida."
            try:
                await query.edit_message_text(_panel_caza(resultado), reply_markup=InlineKeyboardMarkup(kb_caza), parse_mode="Markdown")
            except Exception:
                pass
        else:
            await query.edit_message_text(f"❌ {msg}")
            return
        combate["indice_turno"] += 1
        await siguiente_turno_caza(combate_id)
    elif accion in ("habilidad1", "habilidad2"):
        if not _permit_hab_caza:
            await query.edit_message_text("🚫 Las habilidades están restringidas en este combate.")
            return
        jug_h = db_helper.obtener_jugador(uid)
        if not jug_h:
            await query.edit_message_text("❌ Error al obtener datos del jugador.")
            return
        habilidades_c = clases.obtener_habilidades_activas(jug_h["clase"])
        idx_hab = 0 if accion == "habilidad1" else 1
        if len(habilidades_c) <= idx_hab:
            resultado = "❌ No tienes esa habilidad disponible."
        else:
            hab_c = habilidades_c[idx_hab]
            if "cura" in hab_c and hab_c["cura"] > 0:
                cura_c = max(0, hab_c["cura"] + random.randint(-5, 5))
                combate["vidas_cazadores"][uid] = min(combate["vidas_max_cazadores"][uid], combate["vidas_cazadores"][uid] + cura_c)
                resultado = f"{'✨' if idx_hab == 0 else '🔮'} Usas *{hab_c['nombre']}* y te curas *{cura_c}* de vida."
            elif "daño" in hab_c:
                _dh = max(1, hab_c.get("daño", 10))
                daño_h = random.randint(max(1, _dh - 5), _dh + 5)
                daño_h = calcular_daño(daño_h, combate["asesino_data"]["defensa"], True)
                combate["vida_asesino"] -= daño_h
                resultado = f"{'✨' if idx_hab == 0 else '🔮'} Usas *{hab_c['nombre']}* y causas *{daño_h}* de daño."
                if combate["vida_asesino"] <= 0:
                    await query.edit_message_text(resultado + "\n\U0001f480 ¡Has derrotado al asesino!", parse_mode="Markdown")
                    await finalizar_caza(combate_id, ganadores=True)
                    return
            else:
                resultado = f"{'✨' if idx_hab == 0 else '🔮'} Usas *{hab_c['nombre']}*. Su efecto especial está activo."
        try:
            await query.edit_message_text(_panel_caza(resultado), reply_markup=InlineKeyboardMarkup(kb_caza), parse_mode="Markdown")
        except Exception:
            pass
        combate["indice_turno"] += 1
        await siguiente_turno_caza(combate_id)

async def realizar_ataque_asesino_caza(combate_id):
    combate = combates_activos.get(combate_id)
    if not combate or combate["estado"] != "activo":
        return
    # Elegir un cazador vivo aleatoriamente
    vivos = [uid for uid, vida in combate["vidas_cazadores"].items() if vida > 0]
    if not vivos:
        await finalizar_caza(combate_id, ganadores=False)
        return
    victima = random.choice(vivos)
    daño_asesino = combate["asesino_data"]["daño"]
    defensa_cazador = combate["defensas_cazadores"][victima]
    daño = calcular_daño(daño_asesino, defensa_cazador, False)
    combate["vidas_cazadores"][victima] -= daño
    if _bot_context:
        await _bot_context.bot.send_message(chat_id=victima, text=f"😈 El asesino te ataca y causa {daño} de daño. Te quedan {combate['vidas_cazadores'][victima]}/{combate['vidas_max_cazadores'][victima]} de vida.")
    # Verificar si murió
    if combate["vidas_cazadores"][victima] <= 0:
        await _manejar_muerte_jugador(
            victima, None,
            nombre_enemigo=combate.get("asesino_nombre", "el asesino"),
            tipo_combate="caza_" + combate.get("zona", "")
        )
        # Eliminar de la lista de cazadores activos
        combate["cazadores"] = [uid for uid in combate["cazadores"] if uid != victima]
        # Si no quedan cazadores, derrota
        if not any(vida > 0 for vida in combate["vidas_cazadores"].values()):
            await finalizar_caza(combate_id, ganadores=False)
            return
    # Pasar al siguiente turno cazador
    combate["fase"] = "turno_cazador"
    combate["indice_turno"] = 0
    await siguiente_turno_caza(combate_id)

async def finalizar_caza(combate_id, ganadores: bool):
    combate = combates_activos.pop(combate_id, None)
    if not combate:
        return
    evento_id = combate["evento_id"]
    evento = eventos_caza.pop(evento_id, None)
    if not evento:
        return
    if ganadores:
        # Cazadores ganan: repartir recompensas
        total_xp = combate["asesino_data"]["xp"]
        total_oro = combate["asesino_data"]["oro"]
        drops = combate["asesino_data"]["drops"]
        cazadores_vivos = [uid for uid, vida in combate["vidas_cazadores"].items() if vida > 0]
        for uid in cazadores_vivos:
            xp_share = total_xp // len(cazadores_vivos)
            oro_share = total_oro // len(cazadores_vivos)
            _otorgar_experiencia(uid, xp_share)
            economia.modificar_saldo(uid, "oro", oro_share, "recompensa caza")
            for drop in drops:
                if random.random() < drop.get("probabilidad", 1.0):
                    cantidad = random.randint(drop.get("min",1), drop.get("max",1))
                    db_helper.agregar_item(uid, drop["nombre"], cantidad)
        if _bot_context:
            texto = f"🏆 *¡Caza finalizada! Los cazadores han derrotado al asesino.*\nRecompensas repartidas."
            for uid in cazadores_vivos:
                await _bot_context.bot.send_message(chat_id=uid, text=texto)
            await _bot_context.bot.send_message(chat_id=evento["asesino_id"], text="Fuiste derrotado en la caza. Tu contador de asesinatos se ha reiniciado.")
        _resetear_asesinatos(evento["asesino_id"], evento["zona"])
    else:
        # Asesino gana
        if _bot_context:
            await _bot_context.bot.send_message(chat_id=evento["asesino_id"], text="¡Has sobrevivido a la caza! Tu contador de asesinatos sigue activo.")
            for uid in combate["cazadores"]:
                await _bot_context.bot.send_message(chat_id=uid, text="La caza ha fallado. El asesino escapó.")
        # No se resetea el contador del asesino

async def cmd_unirse_caza(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        return
    if db_helper.esta_marcado(user_id):
        await update.effective_message.reply_text("❌ Estás marcado. No puedes participar en caza hasta que pagues rescate.")
        return
    zona_actual = jug.get("zona_actual", "")
    for evento_id, ev in eventos_caza.items():
        if ev["fase"] == "espera" and ev["zona_nombre"] == zona_actual and user_id not in ev["cazadores"] and len(ev["cazadores"]) < ev["limite_cazadores"]:
            ev["cazadores"].append(user_id)
            await update.effective_message.reply_text("Te has unido a la cacería. Espera a que comience.")
            return
    await update.effective_message.reply_text("No hay cacerías activas en tu zona o ya estás participando.")

# ==================== SISTEMA DE MAZMORRAS (COMPLETO) ====================
async def cmd_crear_mazmorra(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Crea una nueva mazmorra (el líder)."""
    user_id = update.effective_user.id
    if db_helper.esta_marcado(user_id):
        await update.effective_message.reply_text("❌ Estás marcado. No puedes crear mazmorras.")
        return
    args = context.args
    dificultad = "normal"
    if args and args[0].lower() in ["facil", "normal", "dificil"]:
        dificultad = args[0].lower()
    # Verificar límite diario del líder (solo para la primera sala, pero se aplica al entrar)
    jug = db_helper.obtener_jugador(user_id)
    zona_actual = jug.get("zona_actual", "")
    zona_data = next((z for z in ZONAS if z["nombre"] == zona_actual), None)
    if not zona_data:
        await update.effective_message.reply_text("No se pudo determinar tu zona.")
        return
    color = zona_data["color"]
    if not db_helper.comprobar_limite_mazmorra(user_id, color):
        await update.effective_message.reply_text(f"Ya has alcanzado el límite diario de mazmorras en zona {color}.")
        return
    mazmorra_id = random.randint(10000, 99999)
    while mazmorra_id in mazmorras_activas:
        mazmorra_id = random.randint(10000, 99999)
    mazmorras_activas[mazmorra_id] = {
        "id": mazmorra_id,
        "lider": user_id,
        "dificultad": dificultad,
        "miembros": [user_id],
        "sala_actual": 0,
        "salas_totales": 5,
        "fase": "espera",  # espera, activo, terminado
        "creacion": datetime.now(),
        "combate_id": None,
        "monstruos_sala": []
    }
    await update.effective_message.reply_text(f"Mazmorra creada con dificultad {dificultad}. Usa `/unirse_mazmorra {mazmorra_id}` para unirte. El líder puede iniciar con `/iniciar_mazmorra {mazmorra_id}`.")

async def cmd_unirse_mazmorra(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if db_helper.esta_marcado(user_id):
        await update.effective_message.reply_text("❌ Estás marcado. No puedes unirte a mazmorras.")
        return
    if not context.args:
        await update.effective_message.reply_text("Uso: `/unirse_mazmorra <id>`")
        return
    try:
        mazmorra_id = int(context.args[0])
    except:
        await update.effective_message.reply_text("ID inválido.")
        return
    maz = mazmorras_activas.get(mazmorra_id)
    if not maz:
        await update.effective_message.reply_text("Mazmorra no encontrada.")
        return
    if maz["fase"] != "espera":
        await update.effective_message.reply_text("La mazmorra ya está en curso.")
        return
    if len(maz["miembros"]) >= 5:
        await update.effective_message.reply_text("La mazmorra está llena (máx 5).")
        return
    if user_id in maz["miembros"]:
        await update.effective_message.reply_text("Ya estás en esa mazmorra.")
        return
    # Verificar límite diario del jugador
    jug = db_helper.obtener_jugador(user_id)
    zona_actual = jug.get("zona_actual", "")
    zona_data = next((z for z in ZONAS if z["nombre"] == zona_actual), None)
    if not zona_data:
        await update.effective_message.reply_text("No se pudo determinar tu zona.")
        return
    color = zona_data["color"]
    if not db_helper.comprobar_limite_mazmorra(user_id, color):
        await update.effective_message.reply_text(f"Ya has alcanzado el límite diario de mazmorras en zona {color}.")
        return
    maz["miembros"].append(user_id)
    await update.effective_message.reply_text(f"Te has unido a la mazmorra {mazmorra_id}. Actualmente {len(maz['miembros'])}/5 miembros.")

async def cmd_iniciar_mazmorra(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not context.args:
        await update.effective_message.reply_text("Uso: `/iniciar_mazmorra <id>`")
        return
    try:
        mazmorra_id = int(context.args[0])
    except:
        await update.effective_message.reply_text("ID inválido.")
        return
    maz = mazmorras_activas.get(mazmorra_id)
    if not maz:
        await update.effective_message.reply_text("Mazmorra no encontrada.")
        return
    if maz["lider"] != user_id:
        await update.effective_message.reply_text("Solo el líder puede iniciar la mazmorra.")
        return
    if maz["fase"] != "espera":
        await update.effective_message.reply_text("La mazmorra ya está en curso o terminada.")
        return
    if len(maz["miembros"]) < 2:
        await update.effective_message.reply_text("Se necesita al menos 2 jugadores para iniciar.")
        return
    # Registrar entrada para cada miembro (descontar límite diario)
    jug = db_helper.obtener_jugador(user_id)
    zona_actual = jug.get("zona_actual", "")
    zona_data = next((z for z in ZONAS if z["nombre"] == zona_actual), None)
    if not zona_data:
        await update.effective_message.reply_text("Error de zona.")
        return
    color = zona_data["color"]
    for uid in maz["miembros"]:
        if not db_helper.comprobar_limite_mazmorra(uid, color):
            await update.effective_message.reply_text(f"El jugador {uid} ha superado el límite diario de mazmorras.")
            return
    for uid in maz["miembros"]:
        db_helper.registrar_entrada_mazmorra(uid, color)
    maz["fase"] = "activo"
    await update.effective_message.reply_text("¡La mazmorra ha comenzado! Prepárate para la primera sala.")
    await siguiente_sala_mazmorra(update, context, mazmorra_id)

async def siguiente_sala_mazmorra(update: Update, context: ContextTypes.DEFAULT_TYPE, mazmorra_id: int):
    maz = mazmorras_activas.get(mazmorra_id)
    if not maz or maz["fase"] != "activo":
        return
    maz["sala_actual"] += 1
    sala = maz["sala_actual"]
    total = maz["salas_totales"]
    if sala > total:
        # Mazmorra completada
        await finalizar_mazmorra(mazmorra_id, exito=True)
        return
    # Determinar si es jefe (última sala)
    es_jefe = (sala == total)
    # Generar monstruos escalables para el grupo
    lider_id = maz["lider"]
    jug = db_helper.obtener_jugador(lider_id)
    zona_nombre = jug.get("zona_actual", "Bosque Alianza")
    zona_data = next((z for z in ZONAS if z["nombre"] == zona_nombre), None)
    if not zona_data:
        await context.bot.send_message(chat_id=lider_id, text="Error: no se pudo determinar la zona.")
        return
    # Si el líder está en una ciudad, usar la zona salvaje de la misma facción y color para monstruos
    if zona_data.get("tipo") == "ciudad":
        _faccion = zona_data.get("faccion_id")
        _color = zona_data["color"]
        _zona_wild = next((z for z in ZONAS if z["color"] == _color and z.get("tipo") == "salvaje" and z.get("faccion_id") == _faccion), None)
        if _zona_wild:
            zona_data = _zona_wild
            zona_nombre = _zona_wild["nombre"]
    color = zona_data["color"]
    num_monstruos = 1 if es_jefe else random.randint(1, 3)
    monstruos = []
    for i in range(num_monstruos):
        tipo = "mazmorras_normal" if maz["dificultad"] == "normal" else "mazmorras_dificil"
        mon = generar_monstruo_escalable(lider_id, zona_nombre, color, tipo)
        # Ajustar poder según dificultad y sala
        factor = {"facil":0.8, "normal":1.0, "dificil":1.3}[maz["dificultad"]]
        factor_sala = 1 + (sala / total) * 0.5
        mon["vida"] = int(mon["vida"] * factor * factor_sala)
        mon["vida_max"] = mon["vida"]
        mon["daño"] = int(mon["daño"] * factor * factor_sala)
        mon["defensa"] = int(mon["defensa"] * factor * factor_sala)
        mon["xp"] = int(mon["xp"] * factor * factor_sala)
        mon["oro"] = int(mon["oro"] * factor * factor_sala)
        if es_jefe:
            mon["nombre"] = f"Jefe de Mazmorra - {mon['nombre']}"
        monstruos.append(mon)
    maz["monstruos_sala"] = monstruos
    # Iniciar combate grupal contra estos monstruos
    await iniciar_combate_grupal_mazmorra(mazmorra_id, maz, update, context)

async def iniciar_combate_grupal_mazmorra(mazmorra_id: int, maz: dict, update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Similar a caza pero contra varios monstruos
    # ID corto para no superar el límite de 64 bytes de Telegram en callback_data
    combate_id = f"mz{int(datetime.now().timestamp()) % 10000000}{random.randint(10, 99)}"
    maz["combate_id"] = combate_id
    # Estructura
    try:
        import restricciones_combate as _rc_maz
        _snap_maz = _rc_maz.get_snapshot()
    except Exception:
        _snap_maz = {}
    combates_activos[combate_id] = {
        "tipo": "mazmorra",
        "fase": "turno_jugador",
        "indice_turno": 0,
        "jugadores": maz["miembros"],
        "vidas_jugadores": {},
        "vidas_max_jugadores": {},
        "daños_jugadores": {},
        "defensas_jugadores": {},
        "monstruos": maz["monstruos_sala"],
        "vidas_monstruos": [m["vida"] for m in maz["monstruos_sala"]],
        "monstruos_data": maz["monstruos_sala"],
        "mazmorra_id": mazmorra_id,
        "estado": "activo",
        "restricciones": _snap_maz,
        "color": maz.get("color", "azul"),
        "ultima_accion": datetime.now()
    }
    for uid in maz["miembros"]:
        vida_max, daño, defensa = obtener_estadisticas_jugador(uid)
        jug = db_helper.obtener_jugador(uid)
        vida_actual = min(jug["hp_actual"], vida_max)
        combates_activos[combate_id]["vidas_jugadores"][uid] = vida_actual
        combates_activos[combate_id]["vidas_max_jugadores"][uid] = vida_max
        combates_activos[combate_id]["daños_jugadores"][uid] = daño
        combates_activos[combate_id]["defensas_jugadores"][uid] = defensa
    # Notificar inicio
    texto = f"⚔️ *Sala {maz['sala_actual']}/{maz['salas_totales']}*\nEnemigos:\n"
    for i, mon in enumerate(maz["monstruos_sala"]):
        texto += f"{i+1}. {mon['nombre']} (❤️ {mon['vida']})\n"
    for uid in maz["miembros"]:
        if _bot_context:
            await _bot_context.bot.send_message(chat_id=uid, text=texto)
    await siguiente_turno_mazmorra(combate_id)

async def siguiente_turno_mazmorra(combate_id: str):
    combate = combates_activos.get(combate_id)
    if not combate or combate["estado"] != "activo":
        return
    if combate["fase"] == "turno_jugador":
        idx = combate["indice_turno"]
        if idx >= len(combate["jugadores"]):
            # Cambiar a turno de monstruos
            combate["fase"] = "turno_monstruos"
            combate["indice_turno"] = 0
            await realizar_ataque_monstruos_mazmorra(combate_id)
        else:
            uid = combate["jugadores"][idx]
            if combate["vidas_jugadores"].get(uid, 0) <= 0:
                combate["indice_turno"] += 1
                await siguiente_turno_mazmorra(combate_id)
                return
            # Pedir acción
            keyboard = [[
                InlineKeyboardButton("⚔️ Atacar", callback_data=f"mazmorra_accion_{combate_id}_atacar_{uid}"),
                InlineKeyboardButton("🧪 Poción", callback_data=f"mazmorra_accion_{combate_id}_pocion_{uid}")
            ]]
            # Seleccionar objetivo entre monstruos vivos
            vivos = [i for i, vida in enumerate(combate["vidas_monstruos"]) if vida > 0]
            if vivos:
                for i in vivos:
                    keyboard.append([InlineKeyboardButton(f"🎯 Atacar a {combate['monstruos_data'][i]['nombre']}", callback_data=f"mazmorra_accion_{combate_id}_atobj_{uid}_{i}")])
            keyboard.append([InlineKeyboardButton("🔄 Actualizar", callback_data=f"mazmorra_refresh_{combate_id}_{uid}")])
            lineas_mon = "\n".join(
                f"  {'💀' if combate['vidas_monstruos'][i] <= 0 else '👹'} {m['nombre']} "
                f"❤️ `{_barra_vida(combate['vidas_monstruos'][i], m['vida_max'])}` "
                f"{max(0, combate['vidas_monstruos'][i])}/{m['vida_max']}"
                for i, m in enumerate(combate["monstruos_data"])
            )
            b_jug = _barra_vida(combate["vidas_jugadores"].get(uid, 0), combate["vidas_max_jugadores"].get(uid, 1))
            texto = (
                f"⚔️ *¡Tu turno en la mazmorra!*\n\n"
                f"Monstruos:\n{lineas_mon}\n\n"
                f"👤 *Tu vida*\n"
                f"❤️ `{b_jug}` {combate['vidas_jugadores'].get(uid, 0)}/{combate['vidas_max_jugadores'].get(uid, 1)}\n"
            )
            if _bot_context:
                await _bot_context.bot.send_message(chat_id=uid, text=texto, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
                asyncio.create_task(_timeout_turno_mazmorra(combate_id, uid))
    else:
        # Turno monstruos
        pass

async def _timeout_turno_mazmorra(combate_id: str, uid: int):
    await asyncio.sleep(TIEMPO_TURNO)
    combate = combates_activos.get(combate_id)
    if combate and combate["estado"] == "activo" and combate["fase"] == "turno_jugador" and combate["jugadores"][combate["indice_turno"]] == uid:
        if _bot_context:
            await _bot_context.bot.send_message(chat_id=uid, text="⏰ Has tardado demasiado. Pierdes tu turno.")
        combate["indice_turno"] += 1
        await siguiente_turno_mazmorra(combate_id)

async def procesar_accion_mazmorra(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    parts = data.split("_")
    combate_id = parts[2]
    accion = parts[3]
    uid = int(parts[4])
    if update.effective_user.id != uid:
        await query.edit_message_text("No es tu turno o no eres el jugador indicado.")
        return
    combate = combates_activos.get(combate_id)
    if not combate or combate["estado"] != "activo" or combate["fase"] != "turno_jugador" or combate["jugadores"][combate["indice_turno"]] != uid:
        await query.edit_message_text("No es tu turno ahora.")
        return
    def _panel_mazmorra(resultado_txt):
        lineas_mon = "\n".join(
            f"  {'💀' if combate['vidas_monstruos'][i] <= 0 else '👹'} {m['nombre']} "
            f"❤️ `{_barra_vida(combate['vidas_monstruos'][i], m['vida_max'])}` "
            f"{max(0, combate['vidas_monstruos'][i])}/{m['vida_max']}"
            for i, m in enumerate(combate["monstruos_data"])
        )
        b_jugador = _barra_vida(combate["vidas_jugadores"].get(uid, 0), combate["vidas_max_jugadores"].get(uid, 1))
        return (
            f"{resultado_txt}\n\n"
            f"⚔️ *Mazmorra — tu turno*\n"
            f"Monstruos:\n{lineas_mon}\n\n"
            f"👤 *Tu vida*\n"
            f"❤️ `{b_jugador}` {combate['vidas_jugadores'].get(uid, 0)}/{combate['vidas_max_jugadores'].get(uid, 1)}\n"
        )
    def _kb_mazmorra():
        _permit_hab_maz = combate.get("restricciones", {}).get("habilidades_mazmorra", True)
        vivos_idx = [i for i, v in enumerate(combate["vidas_monstruos"]) if v > 0]
        kb = [
            [InlineKeyboardButton("⚔️ Atacar", callback_data=f"mazmorra_accion_{combate_id}_atacar_{uid}"),
             InlineKeyboardButton("🧪 Poción", callback_data=f"mazmorra_accion_{combate_id}_pocion_{uid}")]
        ]
        if _permit_hab_maz:
            kb.append([
                InlineKeyboardButton("✨ Habilidad 1", callback_data=f"mazmorra_accion_{combate_id}_habilidad1_{uid}"),
                InlineKeyboardButton("🔮 Habilidad 2", callback_data=f"mazmorra_accion_{combate_id}_habilidad2_{uid}"),
            ])
        for i in vivos_idx:
            kb.append([InlineKeyboardButton(
                f"🎯 Atacar a {combate['monstruos_data'][i]['nombre']}",
                callback_data=f"mazmorra_accion_{combate_id}_atobj_{uid}_{i}"
            )])
        kb.append([InlineKeyboardButton("🔄 Actualizar", callback_data=f"mazmorra_refresh_{combate_id}_{uid}")])
        return InlineKeyboardMarkup(kb)

    if accion == "atacar":
        # Ataque genérico al primer monstruo vivo
        vivos = [i for i, vida in enumerate(combate["vidas_monstruos"]) if vida > 0]
        if not vivos:
            await finalizar_mazmorra(combate["mazmorra_id"], exito=True)
            return
        objetivo = vivos[0]
        daño_calc = calcular_daño(combate["daños_jugadores"].get(uid, 10), combate["monstruos_data"][objetivo]["defensa"], False)
        combate["vidas_monstruos"][objetivo] -= daño_calc
        muerto_txt = f"\n💀 *{combate['monstruos_data'][objetivo]['nombre']}* ha caído." if combate["vidas_monstruos"][objetivo] <= 0 else ""
        if combate["vidas_monstruos"][objetivo] <= 0:
            try:
                import rankings as _rk
                _rk.registrar_kill_monstruo(uid)
            except Exception:
                pass
        resultado = f"⚔️ Atacas a *{combate['monstruos_data'][objetivo]['nombre']}* y causas *{daño_calc}* de daño.{muerto_txt}"
        if all(v <= 0 for v in combate["vidas_monstruos"]):
            await query.edit_message_text(resultado, parse_mode="Markdown")
            await finalizar_mazmorra(combate["mazmorra_id"], exito=True)
            return
        try:
            await query.edit_message_text(_panel_mazmorra(resultado), reply_markup=_kb_mazmorra(), parse_mode="Markdown")
        except Exception:
            pass
        combate["indice_turno"] += 1
        await siguiente_turno_mazmorra(combate_id)
    elif accion == "atobj":
        # Formato: mazmorra_accion_{combate_id}_atobj_{uid}_{indice}
        indice = int(parts[5])
        daño_calc = calcular_daño(combate["daños_jugadores"].get(uid, 10), combate["monstruos_data"][indice]["defensa"], False)
        combate["vidas_monstruos"][indice] -= daño_calc
        muerto_txt = f"\n💀 *{combate['monstruos_data'][indice]['nombre']}* ha caído." if combate["vidas_monstruos"][indice] <= 0 else ""
        if combate["vidas_monstruos"][indice] <= 0:
            try:
                import rankings as _rk
                _rk.registrar_kill_monstruo(uid)
            except Exception:
                pass
        resultado = f"⚔️ Atacas a *{combate['monstruos_data'][indice]['nombre']}* y causas *{daño_calc}* de daño.{muerto_txt}"
        if all(v <= 0 for v in combate["vidas_monstruos"]):
            await query.edit_message_text(resultado, parse_mode="Markdown")
            await finalizar_mazmorra(combate["mazmorra_id"], exito=True)
            return
        try:
            await query.edit_message_text(_panel_mazmorra(resultado), reply_markup=_kb_mazmorra(), parse_mode="Markdown")
        except Exception:
            pass
        combate["indice_turno"] += 1
        await siguiente_turno_mazmorra(combate_id)
    elif accion == "pocion":
        inv = db_helper.obtener_inventario(uid)
        pocion = None
        for item in inv:
            if "pocion" in item["nombre"].lower() and ("vida" in item["nombre"].lower() or "curativa" in item["nombre"].lower()):
                pocion = item["nombre"]
                break
        if not pocion:
            await query.edit_message_text("❌ No tienes ninguna poción de vida.")
            return
        ok, msg = inventario.usar_consumible(uid, pocion, 1)
        if ok:
            stats = _obtener_estadisticas_objeto_real(pocion)
            cura_str = stats.get("efecto", "")
            try:
                curacion = int(''.join(filter(str.isdigit, cura_str)))
            except:
                curacion = 30
            combate["vidas_jugadores"][uid] = min(combate["vidas_max_jugadores"][uid], combate["vidas_jugadores"][uid] + curacion)
            resultado = f"🧪 Usas *{pocion}* y recuperas *{curacion}* de vida."
            try:
                await query.edit_message_text(_panel_mazmorra(resultado), reply_markup=_kb_mazmorra(), parse_mode="Markdown")
            except Exception:
                pass
        else:
            await query.edit_message_text(f"❌ {msg}")
            return
        combate["indice_turno"] += 1
        await siguiente_turno_mazmorra(combate_id)
    elif accion in ("habilidad1", "habilidad2"):
        _permit_hab_maz2 = combate.get("restricciones", {}).get("habilidades_mazmorra", True)
        if not _permit_hab_maz2:
            await query.edit_message_text("🚫 Las habilidades están restringidas en esta mazmorra.")
            return
        jug_m = db_helper.obtener_jugador(uid)
        if not jug_m:
            await query.edit_message_text("❌ Error al obtener datos del jugador.")
            return
        habilidades_m = clases.obtener_habilidades_activas(jug_m["clase"])
        idx_m = 0 if accion == "habilidad1" else 1
        if len(habilidades_m) <= idx_m:
            resultado = "❌ No tienes esa habilidad disponible."
            try:
                await query.edit_message_text(_panel_mazmorra(resultado), reply_markup=_kb_mazmorra(), parse_mode="Markdown")
            except Exception:
                pass
            return
        hab_m = habilidades_m[idx_m]
        vivos_m = [i for i, v in enumerate(combate["vidas_monstruos"]) if v > 0]
        if "cura" in hab_m and hab_m["cura"] > 0:
            cura_m = max(0, hab_m["cura"] + random.randint(-5, 5))
            combate["vidas_jugadores"][uid] = min(combate["vidas_max_jugadores"][uid], combate["vidas_jugadores"][uid] + cura_m)
            resultado = f"{'✨' if idx_m == 0 else '🔮'} Usas *{hab_m['nombre']}* y te curas *{cura_m}* de vida."
        elif vivos_m and "daño" in hab_m:
            objetivo_m = vivos_m[0]
            _dm = max(1, hab_m.get("daño", 10))
            daño_m = random.randint(max(1, _dm - 5), _dm + 5)
            daño_m = calcular_daño(daño_m, combate["monstruos_data"][objetivo_m]["defensa"], True)
            combate["vidas_monstruos"][objetivo_m] -= daño_m
            muerto_m = f"\n💀 *{combate['monstruos_data'][objetivo_m]['nombre']}* ha caído." if combate["vidas_monstruos"][objetivo_m] <= 0 else ""
            resultado = f"{'✨' if idx_m == 0 else '🔮'} Usas *{hab_m['nombre']}* y causas *{daño_m}* de daño.{muerto_m}"
            if all(v <= 0 for v in combate["vidas_monstruos"]):
                await query.edit_message_text(resultado, parse_mode="Markdown")
                await finalizar_mazmorra(combate["mazmorra_id"], exito=True)
                return
        elif vivos_m:
            resultado = f"{'✨' if idx_m == 0 else '🔮'} Usas *{hab_m['nombre']}*. Su efecto especial está activo."
        else:
            resultado = "❌ No hay enemigos vivos."
        try:
            await query.edit_message_text(_panel_mazmorra(resultado), reply_markup=_kb_mazmorra(), parse_mode="Markdown")
        except Exception:
            pass
        combate["indice_turno"] += 1
        await siguiente_turno_mazmorra(combate_id)

async def realizar_ataque_monstruos_mazmorra(combate_id: str):
    combate = combates_activos.get(combate_id)
    if not combate or combate["estado"] != "activo":
        return
    # Cada monstruo vivo ataca a un jugador aleatorio vivo
    vivos_jugadores = [uid for uid, vida in combate["vidas_jugadores"].items() if vida > 0]
    if not vivos_jugadores:
        await finalizar_mazmorra(combate["mazmorra_id"], exito=False)
        return
    for i, vida in enumerate(combate["vidas_monstruos"]):
        if vida <= 0:
            continue
        monstruo = combate["monstruos_data"][i]
        victima = random.choice(vivos_jugadores)
        daño = calcular_daño(monstruo["daño"], combate["defensas_jugadores"][victima], False)
        combate["vidas_jugadores"][victima] -= daño
        if _bot_context:
            await _bot_context.bot.send_message(chat_id=victima, text=f"😈 {monstruo['nombre']} te ataca y causa {daño} de daño. Te quedan {combate['vidas_jugadores'][victima]}/{combate['vidas_max_jugadores'][victima]}")
        if combate["vidas_jugadores"][victima] <= 0:
            await _manejar_muerte_jugador(
                victima, None,
                nombre_enemigo=monstruo.get("nombre", "un monstruo"),
                tipo_combate="mazmorra_" + combate.get("color", "")
            )
            # Eliminar de los jugadores activos para turnos
            combate["jugadores"] = [uid for uid in combate["jugadores"] if uid != victima]
            vivos_jugadores = [uid for uid in combate["jugadores"] if combate["vidas_jugadores"].get(uid,0) > 0]
            if not vivos_jugadores:
                await finalizar_mazmorra(combate["mazmorra_id"], exito=False)
                return
    # Pasar el turno a jugadores
    combate["fase"] = "turno_jugador"
    combate["indice_turno"] = 0
    await siguiente_turno_mazmorra(combate_id)

async def finalizar_mazmorra(mazmorra_id: int, exito: bool):
    maz = mazmorras_activas.pop(mazmorra_id, None)
    if not maz:
        return
    combate_id = maz.get("combate_id")
    if combate_id and combate_id in combates_activos:
        combates_activos.pop(combate_id, None)
    if exito:
        if maz["sala_actual"] == maz["salas_totales"]:
            # Mazmorra completada
            total_xp = 0
            total_oro = 0
            drops_totales = []
            # Acumular recompensas de todas las salas (simplificado, dar recompensa fija)
            recompensa_base = {"facil": 500, "normal": 1000, "dificil": 2000}[maz["dificultad"]]
            for uid in maz["miembros"]:
                xp = recompensa_base + random.randint(-100,100)
                oro = recompensa_base // 2 + random.randint(-50,50)
                _otorgar_experiencia(uid, xp)
                economia.modificar_saldo(uid, "oro", oro, "recompensa mazmorra")
                try:
                    import logros as _logros
                    _logros.registrar_mazmorra_completada(uid)
                    _logros.registrar_oro_acumulado(uid, oro)
                except Exception:
                    pass
                # Hook misiones mazmorra
                try:
                    import misiones as _mis
                    _mis.completar_mision(uid, "primera_mazmorra")
                except Exception:
                    pass
                # Drops aleatorios con nombre real
                drops_nombres = ["material_1_normal", "material_2_raro", "material_3_epico"]
                items_maz = []
                for drop_nombre in drops_nombres:
                    if random.random() < 0.5:
                        cant = random.randint(1, 3)
                        db_helper.agregar_item(uid, drop_nombre, cant)
                        items_maz.append((drop_nombre, cant))
                # Mensaje detallado al jugador
                if _bot_context:
                    drops_lineas = ("\n" + "\n".join(f"  • {n}: x{c}" for n, c in items_maz)) if items_maz else "\n  (ninguno esta vez)"
                    await _bot_context.bot.send_message(
                        chat_id=uid,
                        text=(
                            f"🏆 *¡Mazmorra completada!*\n\n"
                            f"✨ Experiencia: *+{xp}*\n"
                            f"🪙 Oro: *+{oro}*\n"
                            f"📦 Objetos:{drops_lineas}"
                        ),
                        parse_mode="Markdown"
                    )
        else:
            # Derrota antes de completar
            _color_maz = maz.get("color", "")
            for uid in maz["miembros"]:
                await _manejar_muerte_jugador(
                    uid, None,
                    nombre_enemigo="los monstruos de la mazmorra",
                    tipo_combate="mazmorra_" + _color_maz
                )
    else:
        _color_maz = maz.get("color", "")
        for uid in maz["miembros"]:
            await _manejar_muerte_jugador(
                uid, None,
                nombre_enemigo="los monstruos de la mazmorra",
                tipo_combate="mazmorra_" + _color_maz
            )
    if exito:
        maz = mazmorras_activas.get(mazmorra_id)
        if maz:
            color = maz.get("color", "azul")
            dificultad = maz.get("dificultad", "normal")
            if dificultad == "normal":
                rango = config_balance.MAZMORRAS_RECOMPENSA_ETERNIUM_NORMAL.get(color, (2,5))
            else:
                rango = config_balance.MAZMORRAS_RECOMPENSA_ETERNIUM_DIFICIL.get(color, (6,10))
            eternium = random.randint(rango[0], rango[1])
            for uid in maz.get("miembros", []):
                economia.modificar_saldo(uid, "eternium", eternium, f"recompensa mazmorra {color} {dificultad}")


def get_combate_de_usuario(user_id: int):
    """Devuelve (combate_id, combate) del primer combate activo del jugador, o (None, None)."""
    for cid, c in combates_activos.items():
        if c.get("atacante_id") == user_id or c.get("defensor_id") == user_id:
            return cid, c
    return None, None

async def cmd_retomar_combate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Re-muestra la pantalla del combate activo del jugador. Limpia estado si ya no hay combate."""
    user_id = update.effective_user.id
    combate_id, combate = get_combate_de_usuario(user_id)
    if combate_id:
        await mostrar_mensaje_combate(update, context, combate_id)
        return
    actividad = db_helper.get_actividad(user_id)
    if actividad == "combate":
        db_helper.set_actividad(user_id, None)
        await update.effective_message.reply_text(
            "✅ Tu combate anterior ya no está activo (el bot se reinició). Estado liberado. ¡Puedes actuar con normalidad!"
        )
    else:
        await update.effective_message.reply_text("No tienes ningún combate activo en este momento.")

async def cmd_abandonar_mazmorra(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    import sqlite3 as _sq3
    db_hit = False
    try:
        _conn = _sq3.connect("aethelgard.db")
        _c = _conn.cursor()
        _c.execute(
            'SELECT mazmorra_id FROM mazmorras_activas WHERE (lider_id = ? OR jugadores LIKE ?) AND estado IN ("formando", "en_curso")',
            (user_id, f'%"{user_id}"%')
        )
        _row = _c.fetchone()
        if _row:
            _c.execute('DELETE FROM mazmorras_activas WHERE mazmorra_id = ?', (_row[0],))
            _conn.commit()
            db_hit = True
        _conn.close()
    except Exception:
        pass
    mem_hit = False
    for mid, maz in list(mazmorras_activas.items()):
        if user_id in maz.get("miembros", []):
            del mazmorras_activas[mid]
            mem_hit = True
            break
    if db_hit or mem_hit:
        await update.effective_message.reply_text("✅ Mazmorra cancelada. Puedes entrar a una nueva.")
    else:
        await update.effective_message.reply_text("No tienes ninguna mazmorra activa.")

# ==================== CALLBACKS DE REFRESH ====================

async def cb_refresh_pve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Actualiza el panel PvE sin consumir turno."""
    query = update.callback_query
    await query.answer("🔄 Actualizado")
    combate_id = query.data[len("combate_refresh_"):]
    texto, markup = _construir_panel_pve(combate_id)
    try:
        await query.edit_message_text(texto, reply_markup=markup, parse_mode="Markdown")
    except Exception:
        pass

async def cb_refresh_pvp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Actualiza el panel PvP para el jugador que lo solicita."""
    query = update.callback_query
    await query.answer("🔄 Actualizado")
    parts = query.data.split("_")  # pvp_refresh_{combate_id}_{viewer_id}
    try:
        viewer_id = int(parts[-1])
        combate_id = parts[2]
    except (ValueError, IndexError):
        return
    if update.effective_user.id != viewer_id:
        await query.answer("❌ Este panel no es tuyo.", show_alert=True)
        return
    texto, markup = _construir_panel_pvp(combate_id, viewer_id)
    try:
        await query.edit_message_text(texto, reply_markup=markup, parse_mode="Markdown")
    except Exception:
        pass

async def cb_caza_refresh(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra el estado actual de la caza al jugador."""
    query = update.callback_query
    await query.answer("🔄 Actualizado")
    parts = query.data.split("_")  # caza_refresh_{combate_id}_{uid}
    try:
        uid = int(parts[-1])
        combate_id = parts[2]
    except (ValueError, IndexError):
        return
    if update.effective_user.id != uid:
        await query.answer("❌ Este panel no es tuyo.", show_alert=True)
        return
    combate = combates_activos.get(combate_id)
    if not combate:
        try:
            await query.edit_message_text("❌ Esta caza ya ha terminado.")
        except Exception:
            pass
        return
    b_as = _barra_vida(combate["vida_asesino"], combate["vida_max_asesino"])
    b_ca = _barra_vida(combate["vidas_cazadores"].get(uid, 0), combate["vidas_max_cazadores"].get(uid, 1))
    texto = (
        f"🔄 *Estado actualizado*\n\n"
        f"👹 *{_esc_md(combate['asesino_data']['nombre'])}*\n"
        f"❤️ `{b_as}` {combate['vida_asesino']}/{combate['vida_max_asesino']}\n\n"
        f"👤 *Tu vida*\n"
        f"❤️ `{b_ca}` {combate['vidas_cazadores'].get(uid, 0)}/{combate['vidas_max_cazadores'].get(uid, 1)}\n"
    )
    _permit_hab = combate.get("restricciones", {}).get("habilidades_caza", True)
    kb = [[
        InlineKeyboardButton("⚔️ Atacar", callback_data=f"caza_accion_{combate_id}_atacar_{uid}"),
        InlineKeyboardButton("🧪 Usar poción", callback_data=f"caza_accion_{combate_id}_pocion_{uid}")
    ]]
    if _permit_hab:
        kb.append([
            InlineKeyboardButton("✨ Habilidad 1", callback_data=f"caza_accion_{combate_id}_habilidad1_{uid}"),
            InlineKeyboardButton("🔮 Habilidad 2", callback_data=f"caza_accion_{combate_id}_habilidad2_{uid}"),
        ])
    kb.append([InlineKeyboardButton("🔄 Actualizar", callback_data=f"caza_refresh_{combate_id}_{uid}")])
    try:
        await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
    except Exception:
        pass

async def cb_mazmorra_refresh(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra el estado actual de la mazmorra al jugador."""
    query = update.callback_query
    await query.answer("🔄 Actualizado")
    parts = query.data.split("_")  # mazmorra_refresh_{combate_id}_{uid}
    try:
        uid = int(parts[-1])
        combate_id = parts[2]
    except (ValueError, IndexError):
        return
    if update.effective_user.id != uid:
        await query.answer("❌ Este panel no es tuyo.", show_alert=True)
        return
    combate = combates_activos.get(combate_id)
    if not combate:
        try:
            await query.edit_message_text("❌ Esta mazmorra ya ha terminado.")
        except Exception:
            pass
        return
    lineas_mon = "\n".join(
        f"  {'💀' if combate['vidas_monstruos'][i] <= 0 else '👹'} {m['nombre']} "
        f"❤️ `{_barra_vida(combate['vidas_monstruos'][i], m['vida_max'])}` "
        f"{max(0, combate['vidas_monstruos'][i])}/{m['vida_max']}"
        for i, m in enumerate(combate["monstruos_data"])
    )
    b_jug = _barra_vida(combate["vidas_jugadores"].get(uid, 0), combate["vidas_max_jugadores"].get(uid, 1))
    texto = (
        f"🔄 *Estado actualizado*\n\n"
        f"⚔️ *Mazmorra*\n"
        f"Monstruos:\n{lineas_mon}\n\n"
        f"👤 *Tu vida*\n"
        f"❤️ `{b_jug}` {combate['vidas_jugadores'].get(uid, 0)}/{combate['vidas_max_jugadores'].get(uid, 1)}\n"
    )
    _permit_hab_maz = combate.get("restricciones", {}).get("habilidades_mazmorra", True)
    vivos_idx = [i for i, v in enumerate(combate["vidas_monstruos"]) if v > 0]
    kb = [[
        InlineKeyboardButton("⚔️ Atacar", callback_data=f"mazmorra_accion_{combate_id}_atacar_{uid}"),
        InlineKeyboardButton("🧪 Poción", callback_data=f"mazmorra_accion_{combate_id}_pocion_{uid}")
    ]]
    if _permit_hab_maz:
        kb.append([
            InlineKeyboardButton("✨ Habilidad 1", callback_data=f"mazmorra_accion_{combate_id}_habilidad1_{uid}"),
            InlineKeyboardButton("🔮 Habilidad 2", callback_data=f"mazmorra_accion_{combate_id}_habilidad2_{uid}"),
        ])
    for i in vivos_idx:
        kb.append([InlineKeyboardButton(
            f"🎯 Atacar a {combate['monstruos_data'][i]['nombre']}",
            callback_data=f"mazmorra_accion_{combate_id}_atobj_{uid}_{i}"
        )])
    kb.append([InlineKeyboardButton("🔄 Actualizar", callback_data=f"mazmorra_refresh_{combate_id}_{uid}")])
    try:
        await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
    except Exception:
        pass

# ==================== REGISTRO DE HANDLERS ====================
def registrar_handlers(app):
    global _bot_context
    _bot_context = app  # Guardamos referencia para usar en tareas async
    app.add_handler(CommandHandler("duelo", cmd_duelo))
    app.add_handler(CommandHandler("retomar_combate", cmd_retomar_combate))
    app.add_handler(CallbackQueryHandler(aceptar_duelo, pattern="^duelo_aceptar_"))
    app.add_handler(CallbackQueryHandler(rechazar_duelo, pattern="^duelo_rechazar_"))
    app.add_handler(CallbackQueryHandler(procesar_accion_combate, pattern="^combate_accion_"))
    app.add_handler(CommandHandler("unirse_caza", cmd_unirse_caza))
    app.add_handler(CallbackQueryHandler(procesar_accion_caza, pattern="^caza_accion_"))
    app.add_handler(CommandHandler("crear_mazmorra", cmd_crear_mazmorra))
    app.add_handler(CommandHandler("unirse_mazmorra", cmd_unirse_mazmorra))
    app.add_handler(CommandHandler("iniciar_mazmorra", cmd_iniciar_mazmorra))
    app.add_handler(CommandHandler("abandonar_mazmorra", cmd_abandonar_mazmorra))
    app.add_handler(CallbackQueryHandler(procesar_accion_mazmorra, pattern="^mazmorra_accion_"))
    app.add_handler(CallbackQueryHandler(cb_refresh_pve,      pattern="^combate_refresh_"))
    app.add_handler(CallbackQueryHandler(cb_refresh_pvp,      pattern="^pvp_refresh_"))
    app.add_handler(CallbackQueryHandler(cb_caza_refresh,     pattern="^caza_refresh_"))
    app.add_handler(CallbackQueryHandler(cb_mazmorra_refresh, pattern="^mazmorra_refresh_"))
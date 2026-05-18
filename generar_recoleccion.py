#!/usr/bin/env python3
# generar_recoleccion.py
# Genera archivos de recolección (/recolectar) para zonas salvajes.
# Soporta --all y respeta las carpetas reales mediante búsqueda recursiva.

import argparse
import os
import sys
import importlib.util
import random
from datetime import datetime

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
    print("❌ No se encontró 'datos_zona.py'.")
    sys.exit(1)

RAIZ = encontrar_raiz_proyecto()
sys.path.insert(0, RAIZ)

# ==================== VERIFICACIÓN DE ARCHIVOS ====================
ARCHIVOS_CRITICOS = {
    "datos_zona.py": "Definición de zonas",
    "materiales.py": "Catálogo de materiales (buscar recursivamente)"
}
ARCHIVOS_OPCIONALES = {
    "combate.py": "Para iniciar combate (se importa en el archivo generado)",
    "db_helper.py": "Base de datos",
    "economia.py": "Manejo de oro"
}

print("\n🔍 VERIFICANDO ARCHIVOS PARA GENERADOR DE RECOLECCIÓN...")
todos_ok = True
rutas_criticas = {}

for archivo, desc in ARCHIVOS_CRITICOS.items():
    ruta = buscar_archivo(archivo, RAIZ)
    if ruta:
        print(f"✅ Encontrado: {archivo} en {ruta}")
        rutas_criticas[archivo] = ruta
    else:
        print(f"❌ ERROR CRÍTICO: No se encontró {archivo} ({desc})")
        todos_ok = False

if not todos_ok:
    print("❌ Faltan archivos críticos. El generador no puede continuar.")
    sys.exit(1)

for archivo, desc in ARCHIVOS_OPCIONALES.items():
    ruta = buscar_archivo(archivo, RAIZ)
    if ruta:
        print(f"✅ Encontrado (opcional): {archivo}")
    else:
        print(f"⚠️ No se encontró {archivo} ({desc}) - el archivo generado aún funcionará pero faltará esa importación.")
print("✅ Todos los archivos críticos están presentes.\n")

# ==================== IMPORTAR DATOS NECESARIOS ====================
try:
    from datos_zona import ZONAS
    print(f"✅ Se cargaron {len(ZONAS)} zonas desde datos_zona.py")
except ImportError:
    print("❌ Error al importar datos_zona.py")
    sys.exit(1)

# Importar materiales desde la ruta encontrada
ruta_materiales = rutas_criticas["materiales.py"]
spec = importlib.util.spec_from_file_location("materiales_mod", ruta_materiales)
materiales_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(materiales_mod)
MATERIALES = getattr(materiales_mod, "MATERIALES", None)
if MATERIALES is None:
    print("❌ El archivo materiales.py no contiene la variable MATERIALES")
    sys.exit(1)
print(f"✅ Se cargaron {len(MATERIALES)} materiales desde {ruta_materiales}")

# ==================== MAPEO A CARPETAS (solo para salida) ====================
CARPETA_POR_COLOR = {
    "azul": "zonas azules",
    "amarilla": "zonas amarillas",
    "roja": "zonas rojas",
    "negra": "zonas negras"
}

# ==================== PARÁMETROS DE DIFICULTAD ====================
BASE_PROB_FALLO = {"azul": 0.05, "amarilla": 0.10, "roja": 0.15, "negra": 0.20}
BASE_PROB_MONSTRUO = {"azul": 0.10, "amarilla": 0.15, "roja": 0.20, "negra": 0.25}
RANGO_ORO_BASE = {"azul": (5, 15), "amarilla": (10, 30), "roja": (20, 60), "negra": (40, 120)}
PROB_ORO_EXTRA_BASE = {"azul": 0.05, "amarilla": 0.10, "roja": 0.15, "negra": 0.20}

FRASES_FALLO_GENERICAS = [
    "Te distraes con el paisaje y no encuentras nada útil.",
    "El terreno es demasiado duro, no logras extraer nada.",
    "Un ruido te asusta y abandonas la recolección.",
    "Parece que hoy no es tu día, no aparece nada.",
    "Tus herramientas resbalan y no obtienes recursos."
]

# ==================== FUNCIONES DE GENERACIÓN ====================
def cargar_monstruos_zona(zona_id, carpeta_base_ignorada):
    """
    Carga los monstruos normales de una zona desde su archivo generado.
    Busca recursivamente el archivo sin depender de una ruta fija.
    """
    nombre_archivo = f"monstruos_normales_zona_{zona_id}.py"
    archivo = buscar_archivo(nombre_archivo, RAIZ)
    if not archivo:
        print(f"⚠️ No se encontró {nombre_archivo} para zona ID {zona_id}. No se asignarán monstruos a recolección.")
        return {}
    try:
        spec = importlib.util.spec_from_file_location(f"monstruos_zona_{zona_id}", archivo)
        modulo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modulo)
        if hasattr(modulo, "MONSTRUOS_NORMALES"):
            return getattr(modulo, "MONSTRUOS_NORMALES")
        else:
            print(f"⚠️ No se encontró MONSTRUOS_NORMALES en {archivo}")
            return {}
    except Exception as e:
        print(f"⚠️ Error al cargar {archivo}: {e}")
        return {}

def asignar_materiales_a_zona(zonas_salvajes, materiales_disponibles):
    """Asigna una lista de materiales a cada zona."""
    zonas_ordenadas = sorted(zonas_salvajes, key=lambda z: z["nivel_requerido"])
    mats_ordenados = sorted(materiales_disponibles, key=lambda m: (m["nivel_requerido"], m["rareza"]))
    num_zonas = len(zonas_ordenadas)
    if num_zonas == 0:
        return {}
    total_mats = len(mats_ordenados)
    mats_por_zona = max(4, total_mats // num_zonas if total_mats >= num_zonas else 4)
    repetir = total_mats < (mats_por_zona * num_zonas)
    resultado = {}
    idx = 0
    for zona in zonas_ordenadas:
        zona_nivel = zona["nivel_requerido"]
        candidatos = [m for m in mats_ordenados if abs(m["nivel_requerido"] - zona_nivel) <= 10]
        if len(candidatos) < mats_por_zona:
            candidatos = mats_ordenados
        zona_materials = []
        usados_ids = set()
        for _ in range(mats_por_zona):
            if not repetir:
                if idx >= total_mats:
                    idx = 0
                mat = mats_ordenados[idx % total_mats]
                idx += 1
            else:
                disponibles = [m for m in candidatos if m["id"] not in usados_ids]
                if not disponibles:
                    disponibles = candidatos
                mat = random.choice(disponibles)
                usados_ids.add(mat["id"])
            peso = 1.0 / (mat["rareza"] + 0.1)
            zona_materials.append({
                "id": mat["id"],
                "nombre": mat["nombre"],
                "peso": peso,
                "min": 1,
                "max": 2 if mat["calidad"] == "baja" else (2 if mat["calidad"] == "media" else 1)
            })
        suma = sum(m["peso"] for m in zona_materials)
        for m in zona_materials:
            m["probabilidad"] = m["peso"] / suma
            del m["peso"]
        resultado[zona["nombre"]] = zona_materials
    return resultado

def generar_recoleccion(color: str, output_dir: str = None):
    zonas = [z for z in ZONAS if z["color"] == color and z["tipo"] == "salvaje"]
    if not zonas:
        print(f"⚠️ No hay zonas salvajes de color {color}.")
        return
    print(f"📝 Generando recolección para {len(zonas)} zonas {color}.")

    mats = [m for m in MATERIALES.values() if m.get("zona") == color]
    if not mats:
        print(f"⚠️ Advertencia: No hay materiales para color {color}.")
    asignacion_materiales = asignar_materiales_a_zona(zonas, mats)

    if output_dir is None:
        output_dir = CARPETA_POR_COLOR.get(color, f"zonas_{color}s")
    os.makedirs(output_dir, exist_ok=True)

    asignacion_monstruos = {}
    for zona in zonas:
        zona_id = zona["id"]
        monstruos_dict = cargar_monstruos_zona(zona_id, None)
        if monstruos_dict:
            lista_monstruos = []
            total_peso = 0
            for mid, mdata in monstruos_dict.items():
                nivel = mdata.get("nivel", 1)
                peso = 1.0 / (nivel + 0.1)
                lista_monstruos.append({
                    "id": mid,
                    "nombre": mdata.get("nombre", mid),
                    "nivel": nivel,
                    "peso": peso
                })
                total_peso += peso
            if total_peso > 0:
                for m in lista_monstruos:
                    m["probabilidad"] = m["peso"] / total_peso
                    del m["peso"]
            asignacion_monstruos[zona["nombre"]] = lista_monstruos
        else:
            asignacion_monstruos[zona["nombre"]] = []

    config = {}
    for zona in zonas:
        nombre = zona["nombre"]
        nivel = zona["nivel_requerido"]
        peligrosidad = zona.get("peligrosidad_base", 1.0)
        prob_fallo = min(0.5, BASE_PROB_FALLO[color] * peligrosidad)
        prob_monstruo = min(0.6, BASE_PROB_MONSTRUO[color] * peligrosidad)
        factor_nivel = nivel / 100.0
        oro_min_base, oro_max_base = RANGO_ORO_BASE[color]
        oro_min = max(1, int(oro_min_base * (1 + factor_nivel)))
        oro_max = max(oro_min+1, int(oro_max_base * (1 + factor_nivel)))
        prob_oro_extra = min(0.4, PROB_ORO_EXTRA_BASE[color] * (1 + factor_nivel))
        config[nombre] = {
            "id": zona["id"],
            "nivel": nivel,
            "prob_fallo": round(prob_fallo, 3),
            "prob_monstruo": round(prob_monstruo, 3),
            "min_oro": oro_min,
            "max_oro": oro_max,
            "prob_oro_extra": round(prob_oro_extra, 3),
            "frases_fallo": FRASES_FALLO_GENERICAS,
            "materiales": asignacion_materiales.get(nombre, []),
            "monstruos": asignacion_monstruos.get(nombre, [])
        }

    if output_dir is None:
        output_dir = CARPETA_POR_COLOR.get(color, f"zonas_{color}s")
    os.makedirs(output_dir, exist_ok=True)
    archivo_salida = os.path.join(output_dir, f"recoleccion_{color}.py")
    print(f"📁 Generando archivo de recolección en: {archivo_salida}")
    with open(archivo_salida, "w", encoding="utf-8") as f:
        f.write(f"#!/usr/bin/env python3\n")
        f.write(f"# recoleccion_{color}.py\n")
        f.write(f"# Generado automáticamente por generar_recoleccion.py para zona {color}\n\n")

        f.write("import random\n")
        f.write("import sqlite3\n")
        f.write("from datetime import datetime\n")
        f.write("from typing import Tuple, Optional\n\n")
        f.write("from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup\n")
        f.write("from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler\n\n")
        f.write("import db_helper\n")
        f.write("import economia\n")
        f.write("import config_balance\n")
        f.write("from combate import iniciar_combate, COMBATE_PVE_AZUL, COMBATE_PVE_AMARILLA, COMBATE_PVE_ROJA, COMBATE_PVE_NEGRA\n\n")
        f.write("DB_PATH = \"aethelgard.db\"\n\n")

        f.write("# ==================== MAPEO DE CARPETAS POR COLOR ====================\n")
        f.write("CARPETA_POR_COLOR = {\n")
        for c, carpeta in CARPETA_POR_COLOR.items():
            f.write(f"    {repr(c)}: {repr(carpeta)},\n")
        f.write("}\n\n")

        f.write("# ==================== CONFIGURACIÓN DE RECOLECCIÓN ====================\n")
        f.write("CONFIG_RECOLECCION = {\n")
        for nombre_zona, data in config.items():
            f.write(f"    {repr(nombre_zona)}: {{\n")
            f.write(f"        'zona_id': {data['id']},\n")
            f.write(f"        'nivel_zona': {data['nivel']},\n")
            f.write(f"        'prob_fallo': {data['prob_fallo']},\n")
            f.write(f"        'prob_monstruo': {data['prob_monstruo']},\n")
            f.write(f"        'min_oro': {data['min_oro']},\n")
            f.write(f"        'max_oro': {data['max_oro']},\n")
            f.write(f"        'prob_oro_extra': {data['prob_oro_extra']},\n")
            f.write(f"        'frases_fallo': {repr(data['frases_fallo'])},\n")
            f.write(f"        'materiales': [\n")
            for mat in data['materiales']:
                f.write(f"            {{'id': {repr(mat['id'])}, 'nombre': {repr(mat['nombre'])}, 'probabilidad': {mat['probabilidad']:.4f}, 'min': {mat['min']}, 'max': {mat['max']}}},\n")
            f.write(f"        ],\n")
            f.write(f"        'monstruos': [\n")
            for mon in data['monstruos']:
                f.write(f"            {{'id': {repr(mon['id'])}, 'nombre': {repr(mon['nombre'])}, 'probabilidad': {mon['probabilidad']:.4f}}},\n")
            f.write(f"        ]\n")
            f.write(f"    }},\n")
        f.write("}\n\n")

        f.write("def _obtener_config_zona_actual(user_id: int) -> Optional[dict]:\n")
        f.write("    jug = db_helper.obtener_jugador(user_id)\n")
        f.write("    if not jug:\n")
        f.write("        return None\n")
        f.write("    zona_nombre = jug.get(\"zona_actual\", \"\")\n")
        f.write("    return CONFIG_RECOLECCION.get(zona_nombre)\n\n")

        f.write("def _otorgar_recompensa(user_id: int, zona_config: dict):\n")
        f.write("    materiales = zona_config['materiales']\n")
        f.write("    for mat in materiales:\n")
        f.write("        if random.random() < mat['probabilidad']:\n")
        f.write("            cantidad = random.randint(mat['min'], mat['max'])\n")
        f.write("            db_helper.agregar_item(user_id, mat['id'], cantidad)\n")
        f.write("    oro_base = random.randint(zona_config['min_oro'], zona_config['max_oro'])\n")
        f.write("    if random.random() < zona_config['prob_oro_extra']:\n")
        f.write("        oro_extra = random.randint(1, oro_base)\n")
        f.write("        oro_base += oro_extra\n")
        f.write("    economia.modificar_saldo(user_id, 'oro', oro_base, f'recolección')\n")
        f.write("    return oro_base\n\n")

        f.write("def _cargar_monstruo_real(zona_id: int, mon_id: str, carpeta_base: str) -> Optional[dict]:\n")
        f.write("    import importlib.util, os\n")
        f.write("    archivo = os.path.join(carpeta_base, f'monstruos_normales_zona_{zona_id}.py')\n")
        f.write("    if not os.path.exists(archivo):\n")
        f.write("        return None\n")
        f.write("    spec = importlib.util.spec_from_file_location(f'monstruos_zona_{zona_id}', archivo)\n")
        f.write("    modulo = importlib.util.module_from_spec(spec)\n")
        f.write("    spec.loader.exec_module(modulo)\n")
        f.write("    if hasattr(modulo, 'MONSTRUOS_NORMALES'):\n")
        f.write("        return modulo.MONSTRUOS_NORMALES.get(mon_id)\n")
        f.write("    return None\n\n")

        f.write("async def cmd_recolectar(update: Update, context: ContextTypes.DEFAULT_TYPE):\n")
        f.write("    user_id = update.effective_user.id\n")
        f.write("    if db_helper.esta_marcado(user_id):\n")
        f.write("        await update.effective_message.reply_text(\"❌ Estás marcado. No puedes recolectar hasta que pagues rescate con /pagar_rescate.\")\n")
        f.write("        return\n")
        f.write("    # Verificar y gastar stamina según la zona\n")
        f.write("    jug = db_helper.obtener_jugador(user_id)\n")
        f.write("    if not jug:\n")
        f.write("        await update.effective_message.reply_text(\"No estás registrado.\")\n")
        f.write("        return\n")
        f.write("    zona_nombre = jug.get(\"zona_actual\", \"\")\n")
        f.write("    from datos_zona import ZONAS\n")
        f.write("    zona_info = next((z for z in ZONAS if z[\"nombre\"] == zona_nombre), None)\n")
        f.write("    if not zona_info:\n")
        f.write("        await update.effective_message.reply_text(\"No se pudo determinar tu zona.\")\n")
        f.write("        return\n")
        f.write("    color_zona = zona_info[\"color\"]\n")
        f.write("    costo_stamina = config_balance.STAMINA_COSTE_POR_ZONA.get(color_zona, 20)\n")
        f.write("    if not db_helper.gastar_stamina(user_id, costo_stamina):\n")
        f.write("        await update.effective_message.reply_text(f\"❌ No tienes suficiente stamina. Necesitas {costo_stamina}. Espera a que se regenere.\")\n")
        f.write("        return\n")
        f.write("    zona_config = _obtener_config_zona_actual(user_id)\n")
        f.write("    if not zona_config:\n")
        f.write("        await update.effective_message.reply_text(\"No estás en una zona donde puedas recolectar.\")\n")
        f.write("        return\n")
        f.write("    if random.random() < zona_config['prob_fallo']:\n")
        f.write("        frase = random.choice(zona_config['frases_fallo'])\n")
        f.write("        await update.effective_message.reply_text(f\"❌ {frase}\")\n")
        f.write("        return\n")
        f.write("    if random.random() < zona_config['prob_monstruo'] and zona_config['monstruos']:\n")
        f.write("        monstruos = zona_config['monstruos']\n")
        f.write("        r = random.random()\n")
        f.write("        acum = 0\n")
        f.write("        monstruo_elegido = None\n")
        f.write("        for m in monstruos:\n")
        f.write("            acum += m['probabilidad']\n")
        f.write("            if r <= acum:\n")
        f.write("                monstruo_elegido = m\n")
        f.write("                break\n")
        f.write("        if monstruo_elegido:\n")
        f.write("            from datos_zona import ZONAS\n")
        f.write("            zona_nombre = [k for k, v in CONFIG_RECOLECCION.items() if v == zona_config][0]\n")
        f.write("            zona_data = next((z for z in ZONAS if z['nombre'] == zona_nombre), None)\n")
        f.write("            if zona_data:\n")
        f.write("                color_zona = zona_data['color']\n")
        f.write("                carpeta = CARPETA_POR_COLOR.get(color_zona, f'zonas_{color_zona}s')\n")
        f.write("            else:\n")
        f.write("                carpeta = 'zonas azules'\n")
        f.write("            monstruo_real = _cargar_monstruo_real(zona_config['zona_id'], monstruo_elegido['id'], carpeta)\n")
        f.write("            if monstruo_real:\n")
        f.write("                enemigo = {\n")
        f.write("                    'nombre': monstruo_real['nombre'],\n")
        f.write("                    'vida_max': monstruo_real['vida_max'],\n")
        f.write("                    'vida_actual': monstruo_real['vida_max'],\n")
        f.write("                    'daño': monstruo_real['daño'],\n")
        f.write("                    'defensa': monstruo_real['defensa'],\n")
        f.write("                    'xp': monstruo_real['xp'],\n")
        f.write("                    'oro': monstruo_real['oro'],\n")
        f.write("                    'drops': monstruo_real.get('drops', [])\n")
        f.write("                }\n")
        f.write("                await update.effective_message.reply_text(f\"¡Un {monstruo_real['nombre']} aparece! Prepárate para combatir.\")\n")
        f.write("                tipo_combate_map = {\n")
        f.write("                    'azul': 'pve_zona_azul',\n")
        f.write("                    'amarilla': 'pve_zona_amarilla',\n")
        f.write("                    'roja': 'pve_zona_roja',\n")
        f.write("                    'negra': 'pve_zona_negra'\n")
        f.write("                }\n")
        f.write("                tipo_combate = tipo_combate_map.get(color_zona, 'pve_zona_azul')\n")
        f.write("                await iniciar_combate(update, context, user_id, 0, tipo_combate, enemigo=enemigo, datos_extra={})\n")
        f.write("                return\n")
        f.write("            else:\n")
        f.write("                await update.effective_message.reply_text(\"Error al cargar el monstruo. Recolectando sin combate.\")\n")
        f.write("    oro_ganado = _otorgar_recompensa(user_id, zona_config)\n")
        f.write("    await update.effective_message.reply_text(f\"✅ Recolectaste recursos y obtuviste {oro_ganado} de oro.\")\n\n")

        f.write("def registrar_handlers(app):\n")
        f.write("    app.add_handler(CommandHandler(\"recolectar\", cmd_recolectar))\n")

    print(f"✅ Archivo generado: {archivo_salida}")

def generar_todas_recolecciones():
    print("\n🚀 GENERANDO RECOLECCIÓN PARA TODOS LOS COLORES...\n")
    for color in CARPETA_POR_COLOR.keys():
        generar_recoleccion(color)
    print("\n✨ ¡Generación completa!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generar sistema de recolección completo para una o todas las zonas.")
    parser.add_argument("--color", choices=["azul", "amarilla", "roja", "negra"], help="Color de zona (si no se usa --all)")
    parser.add_argument("--output-dir", default=None, help="Carpeta donde están los monstruos y donde se guardará el resultado")
    parser.add_argument("--all", action="store_true", help="Generar recolección para todos los colores")
    args = parser.parse_args()
    if args.all or (args.color is None):
        generar_todas_recolecciones()
    else:
        generar_recoleccion(args.color, args.output_dir)
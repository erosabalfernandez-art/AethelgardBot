#!/usr/bin/env python3
# generador_monstruos.py
# Genera TODOS los archivos de monstruos (normales, mini_boss, mazmorras)
# en las carpetas: "zonas azules", "zonas amarillas", "zonas rojas", "zonas negras"

import argparse
import os
import sys
import importlib.util

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
    "drops_config.py": "Configuración de drops"
}
print("\n🔍 VERIFICANDO ARCHIVOS...")
for archivo, desc in ARCHIVOS_CRITICOS.items():
    ruta = buscar_archivo(archivo, RAIZ)
    if ruta:
        print(f"✅ Encontrado: {archivo} en {ruta}")
    else:
        print(f"❌ No se encontró {archivo} ({desc})")
        sys.exit(1)

# ==================== IMPORTAR MÓDULOS ====================
from datos_zona import ZONAS
print(f"✅ Cargadas {len(ZONAS)} zonas desde datos_zona.py")

drops_path = buscar_archivo("drops_config.py", RAIZ)
spec = importlib.util.spec_from_file_location("drops_config", drops_path)
drops_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(drops_mod)

if hasattr(drops_mod, 'DROPS_POR_MONSTRUO'):
    DROPS_POR_MONSTRUO = drops_mod.DROPS_POR_MONSTRUO
    print("✅ drops_config.py cargado (DROPS_POR_MONSTRUO)")
else:
    print("❌ drops_config.py no tiene DROPS_POR_MONSTRUO")
    sys.exit(1)

# ==================== MAPEO A CARPETAS REALES ====================
CARPETA_POR_COLOR = {
    "azul": "zonas azules",
    "amarilla": "zonas amarillas",
    "roja": "zonas rojas",
    "negra": "zonas negras"
}

# ==================== MULTIPLICADORES Y CÁLCULO DE STATS ====================
MULT_COLOR = {
    "azul":   {"vida": 1.0, "daño": 1.0, "xp": 1.0, "oro": 1.0, "defensa": 1.0},
    "amarilla":{"vida": 1.5, "daño": 1.4, "xp": 1.8, "oro": 1.6, "defensa": 1.3},
    "roja":   {"vida": 2.2, "daño": 1.9, "xp": 2.8, "oro": 2.4, "defensa": 1.7},
    "negra":  {"vida": 3.5, "daño": 2.8, "xp": 5.0, "oro": 4.0, "defensa": 2.2}
}
MULT_DIFICULTAD_MAZMORRA = {"normal": 1.0, "dificil": 1.3}

def calcular_stats_monstruo(zona_nivel, color, tipo, dificultad_mazmorra=None):
    vida_base = 60 + zona_nivel * 12
    daño_base = 15 + zona_nivel * 2.5
    defensa_base = 5 + zona_nivel * 2
    xp_base = 30 + zona_nivel * 5
    oro_base = 20 + zona_nivel * 4

    if tipo == "normales":
        mult = (1.0, 1.0, 1.0, 1.0, 1.0)
    elif tipo == "mini_boss":
        mult = (2.5, 1.8, 1.5, 3.0, 2.5)
    elif tipo in ("mazmorras_normal", "mazmorras_dificil"):
        mult = (1.5, 1.3, 1.2, 1.8, 1.6)
    else:
        mult = (1.0, 1.0, 1.0, 1.0, 1.0)
    mult_vida, mult_daño, mult_def, mult_xp, mult_oro = mult

    mc = MULT_COLOR[color]
    vida = vida_base * mc["vida"] * mult_vida
    daño = daño_base * mc["daño"] * mult_daño
    defensa = defensa_base * mc["defensa"] * mult_def
    xp = xp_base * mc["xp"] * mult_xp
    oro = oro_base * mc["oro"] * mult_oro

    if tipo.startswith("mazmorras") and dificultad_mazmorra:
        md = MULT_DIFICULTAD_MAZMORRA.get(dificultad_mazmorra, 1.0)
        vida *= md
        daño *= md
        defensa *= md
        xp *= md
        oro *= md

    return {
        "vida": int(vida),
        "daño": int(daño),
        "defensa": int(defensa),
        "xp": int(xp),
        "oro": int(oro)
    }

# ==================== GENERADOR PRINCIPAL ====================
def generar_archivos_por_color(color, tipo, dificultad=None, output_dir=None):
    tipos_validos = ["normales", "mini_boss", "mazmorras"]
    if tipo not in tipos_validos:
        print(f"⚠️ Tipo '{tipo}' no será generado (solo normales, mini_boss, mazmorras).")
        return

    zonas = [z for z in ZONAS if z["color"] == color and z["tipo"] == "salvaje"]
    if not zonas:
        print(f"⚠️ No hay zonas salvajes de color {color}.")
        return

    if output_dir is None:
        output_dir = CARPETA_POR_COLOR.get(color, f"zonas_{color}s")
    os.makedirs(output_dir, exist_ok=True)
    print(f"📁 Carpeta de salida: {output_dir}")

    for zona in zonas:
        zona_id = zona["id"]
        zona_nivel = zona["nivel_requerido"]
        zona_nombre = zona["nombre"]
        monstruos_data = zona.get("monstruos", {})
        if not monstruos_data:
            print(f"⚠️ Zona {zona_nombre} (id {zona_id}) no tiene monstruos. Saltando.")
            continue

        if tipo == "normales":
            lista = monstruos_data.get("normales", [])
            if not lista:
                print(f"⚠️ Zona {zona_nombre} no tiene normales. Saltando.")
                continue
            fname = f"monstruos_normales_zona_{zona_id}.py"
            stats_tipo = "normales"
        elif tipo == "mini_boss":
            lista = monstruos_data.get("mini_boss", [])
            if not lista:
                print(f"⚠️ Zona {zona_nombre} no tiene mini_boss. Saltando.")
                continue
            fname = f"monstruos_mini_boss_zona_{zona_id}.py"
            stats_tipo = "mini_boss"
        elif tipo == "mazmorras":
            if dificultad == "normal":
                lista = monstruos_data.get("mazmorras_normal", [])
                if not lista:
                    print(f"⚠️ Zona {zona_nombre} no tiene mazmorras normales. Saltando.")
                    continue
                fname = f"monstruos_mazmorras_zona_{zona_id}_normal.py"
                stats_tipo = "mazmorras_normal"
            elif dificultad == "dificil":
                lista = monstruos_data.get("mazmorras_dificil", [])
                if not lista:
                    print(f"⚠️ Zona {zona_nombre} no tiene mazmorras difíciles. Saltando.")
                    continue
                fname = f"monstruos_mazmorras_zona_{zona_id}_dificil.py"
                stats_tipo = "mazmorras_dificil"
            else:
                print(f"❌ Error: Para mazmorras se necesita --dificultad normal o dificil")
                return
        else:
            continue

        monstruos_dict = {}
        for idx, mon in enumerate(lista, start=1):
            nombre = mon["nombre"]
            lore = mon.get("lore", "Sin descripción.")
            # Obtener la clase del monstruo (si no tiene, se asigna aleatoriamente entre las 4)
            clase = mon.get("clase")
            if not clase:
                # Asignación aleatoria por si falta (aunque el script asignar_clases_jefes.py debería haberla puesto)
                import random
                CLASES = ['vanguardista', 'acechante', 'tejehechizos', 'maestro_caza']
                clase = random.choice(CLASES)
            stats = calcular_stats_monstruo(zona_nivel, color, stats_tipo, dificultad if tipo=="mazmorras" else None)
            mon_id = f"{color}_{tipo}_{zona_id}_{idx}".replace("_", "")

            drops = []
            if DROPS_POR_MONSTRUO and zona_nombre in DROPS_POR_MONSTRUO:
                zona_drops = DROPS_POR_MONSTRUO[zona_nombre]
                if nombre in zona_drops:
                    drops = zona_drops[nombre]
                else:
                    print(f"  ⚠️ Monstruo '{nombre}' en zona '{zona_nombre}' no tiene entrada en DROPS_POR_MONSTRUO")
            else:
                print(f"  ⚠️ Zona '{zona_nombre}' no encontrada en DROPS_POR_MONSTRUO")

            monstruos_dict[mon_id] = {
                "nombre": nombre,
                "descripcion": lore,
                "clase": clase,
                "nivel": zona_nivel,
                "vida": stats["vida"],
                "vida_max": stats["vida"],
                "daño": stats["daño"],
                "defensa": stats["defensa"],
                "xp": stats["xp"],
                "oro": stats["oro"],
                "drops": drops
            }

        ruta_salida = os.path.join(output_dir, fname)
        with open(ruta_salida, "w", encoding="utf-8") as f:
            f.write(f"# Archivo generado para zona ID={zona_id} ({zona_nombre})\n")
            f.write(f"# No modificar directamente, usar generador_monstruos.py\n\n")
            var_name = f"MONSTRUOS_{tipo.upper()}"
            if dificultad:
                var_name += f"_{dificultad.upper()}"
            f.write(f"{var_name} = {repr(monstruos_dict)}\n")
        print(f"✅ Generado: {ruta_salida}")

# ==================== GENERAR TODO ====================
def generar_todo():
    colores = ["azul", "amarilla", "roja", "negra"]
    tipos = ["normales", "mini_boss"]
    dificultades = ["normal", "dificil"]

    print("\n🚀 GENERANDO TODOS LOS MONSTRUOS PARA TODAS LAS ZONAS...\n")
    for color in colores:
        for tipo in tipos:
            generar_archivos_por_color(color, tipo)
        for dificultad in dificultades:
            generar_archivos_por_color(color, "mazmorras", dificultad)
    print("\n✨ ¡Generación completa!")

# ==================== MAIN ====================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generador de monstruos fijos (normales, mini_boss, mazmorras)")
    parser.add_argument("--color", choices=["azul", "amarilla", "roja", "negra"], help="Color de zona")
    parser.add_argument("--tipo", choices=["normales", "mini_boss", "mazmorras"], help="Tipo de monstruos")
    parser.add_argument("--dificultad", choices=["normal", "dificil"], default=None, help="Necesario para mazmorras")
    parser.add_argument("--output-dir", default=None, help="Carpeta de salida (por defecto 'zonas azules', etc.)")
    parser.add_argument("--all", action="store_true", help="Generar TODOS los monstruos de todas las zonas")

    args = parser.parse_args()

    if args.all or (args.color is None and args.tipo is None):
        generar_todo()
    else:
        if args.tipo == "mazmorras" and not args.dificultad:
            print("❌ Error: Para mazmorras se requiere --dificultad (normal o dificil)")
            sys.exit(1)
        generar_archivos_por_color(args.color, args.tipo, args.dificultad, args.output_dir)
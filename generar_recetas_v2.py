#!/usr/bin/env python3
# generar_recetas_v2.py
# Genera recetas SOLO para objetos con origen 'crafteo' (armas, armaduras, pociones).
# Usa los IDs de materiales tal como están en materiales.py (incluyendo sufijos _normal, etc.).
# Tiempos: negra=180s, roja=60s, otras=0s. Pociones siempre 0s.

import sys
import os
import random

# Añadir carpeta globales para importar catálogos
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'globales'))

from armas import ARMAS
from armaduras import ARMADURAS
from pociones import POCIONES
from materiales import MATERIALES

ARCHIVO_SALIDA = "recetas.py"

# Configuración
NUM_MATERIALES_MIN = 2
NUM_MATERIALES_MAX = 5

# Para resultados reproducibles (opcional, comenta si quieres aleatorio total)
# random.seed(42)

def obtener_zona_materiales(material_ids):
    """Devuelve lista de zonas únicas de los materiales."""
    zonas = set()
    for mid in material_ids:
        mat = MATERIALES.get(mid)
        if mat:
            zonas.add(mat["zona"])
    return list(zonas)

def calcular_tiempo(zonas_materiales, tipo_objeto):
    """Calcula tiempo según reglas: negra=180, roja=60, otras=0. Pociones siempre 0."""
    if tipo_objeto == "pocion":
        return 0
    if "negra" in zonas_materiales:
        return 180
    if "roja" in zonas_materiales:
        return 60
    return 0

def seleccionar_materiales(zona_obj, rareza_obj, nivel_obj, num_mats):
    """Elige materiales de zonas igual o inferior a la del objeto, priorizando coherencia."""
    orden_zona = {"azul": 0, "amarilla": 1, "roja": 2, "negra": 3}
    obj_val = orden_zona.get(zona_obj, 0)
    candidatos = []
    for mid, mat in MATERIALES.items():
        mat_zona = mat.get("zona", "azul")
        mat_val = orden_zona.get(mat_zona, 0)
        if mat_val <= obj_val:
            candidatos.append(mid)
    if len(candidatos) < num_mats:
        # Si no hay suficientes, ampliamos a todos los materiales (pero no debería ocurrir)
        candidatos = list(MATERIALES.keys())
    seleccion = random.sample(candidatos, min(num_mats, len(candidatos)))
    cantidades = {}
    for mid in seleccion:
        mat = MATERIALES[mid]
        rareza_mat = mat.get("rareza", 1)
        # A mayor rareza del objeto, menos cantidad del material (opcional)
        if rareza_mat > rareza_obj:
            cant = random.randint(1, 2)
        else:
            cant = random.randint(2, 5)
        cantidades[mid] = max(1, cant)
    return cantidades

def generar_receta_objeto(objeto, tipo, nivel, rareza, clase, zona_obj):
    """Genera una receta para un objeto dado."""
    num_mats = random.randint(NUM_MATERIALES_MIN, NUM_MATERIALES_MAX)
    materiales = seleccionar_materiales(zona_obj, rareza, nivel, num_mats)
    zonas_mats = obtener_zona_materiales(materiales.keys())
    tiempo = calcular_tiempo(zonas_mats, tipo)
    receta = {
        "nombre": objeto["nombre"],
        "tipo": tipo,
        "zona_crafteo": "azul",  # siempre azul? podrías parametrizar
        "nivel_requerido": nivel,
        "clase_requerida": clase,
        "materiales": materiales,
        "zona_materiales": zonas_mats,
        "tiempo_segundos": tiempo,
        "descripcion": f"Fabricar {objeto['nombre']} requiriendo materiales de {', '.join(zonas_mats)}."
    }
    return receta

def main():
    recetas = {}

    # Armas con origen 'crafteo'
    for aid, arma in ARMAS.items():
        if arma.get("origen") == "crafteo":
            nivel = arma.get("nivel_requerido", 1)
            rareza = arma.get("rareza", 1)
            clase = arma.get("clase_requerida", None)
            zona = arma.get("zona", "azul")
            receta = generar_receta_objeto(arma, "arma", nivel, rareza, clase, zona)
            recetas[aid] = receta

    # Armaduras con origen 'crafteo'
    for arid, armadura in ARMADURAS.items():
        if armadura.get("origen") == "crafteo":
            nivel = armadura.get("nivel_requerido", 1)
            rareza = armadura.get("rareza", 1)
            clase = armadura.get("clase_requerida", None)
            zona = armadura.get("zona", "azul")
            receta = generar_receta_objeto(armadura, "armadura", nivel, rareza, clase, zona)
            recetas[arid] = receta

    # Pociones con origen 'crafteo' (solo las que se pueden fabricar)
    for pid, pocion in POCIONES.items():
        if pocion.get("origen") == "crafteo":
            nivel = pocion.get("nivel_requerido", 1)
            rareza = pocion.get("rareza", 1)
            clase = None  # las pociones no tienen clase
            zona = pocion.get("zona", "azul")
            receta = generar_receta_objeto(pocion, "pocion", nivel, rareza, clase, zona)
            # Sobrescribimos tiempo a 0 por si acaso (la función ya lo pone a 0 por tipo)
            receta["tiempo_segundos"] = 0
            recetas[pid] = receta

    # Escribir archivo
    with open(ARCHIVO_SALIDA, "w", encoding="utf-8") as f:
        f.write("#!/usr/bin/env python3\n")
        f.write("# recetas.py\n")
        f.write("# Catálogo de recetas de crafteo con tiempos según zona de materiales.\n")
        f.write("# Tiempos: negra=180s, roja=60s, otras=0s. Pociones siempre 0s.\n")
        f.write("# Solo objetos con origen 'crafteo' (armas, armaduras, pociones).\n")
        f.write("# IDs de materiales respetan los sufijos de materiales.py.\n\n")
        f.write("RECETAS = {\n")
        items = list(recetas.items())
        for i, (rid, rec) in enumerate(items):
            f.write(f"    \"{rid}\": {repr(rec)}")
            if i < len(items)-1:
                f.write(",\n")
            else:
                f.write("\n")
        f.write("}\n\n")
        # Añadir funciones auxiliares
        f.write("""
def obtener_receta(id_objeto):
    return RECETAS.get(id_objeto)

def listar_recetas_por_clase(clase):
    return [r for r in RECETAS.values() if r.get(\"clase_requerida\") is None or r[\"clase_requerida\"] == clase]

def listar_recetas_por_tipo(tipo):
    return [r for r in RECETAS.values() if r[\"tipo\"] == tipo]

def listar_recetas_por_zona_material(zona):
    return [r for r in RECETAS.values() if zona in r[\"zona_materiales\"]]

def validar_recetas():
    print(f\"Total recetas generadas: {len(RECETAS)}\")
    for rid, rec in RECETAS.items():
        for mat_id in rec[\"materiales\"]:
            if mat_id not in __import__('materiales').MATERIALES:
                print(f\"Advertencia: material {mat_id} no encontrado en receta {rid}\")
    print(\"Validación completada.\")

if __name__ == \"__main__\":
    validar_recetas()
""")
    print(f"✅ Archivo generado: {ARCHIVO_SALIDA} con {len(recetas)} recetas (solo objetos crafteables).")

if __name__ == "__main__":
    main()
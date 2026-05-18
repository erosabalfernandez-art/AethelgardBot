#!/usr/bin/env python3
# arreglar_bot.py
# Script automático para unificar crafteo, viajes y peaje en el bot de Telegram.
# Debe ejecutarse desde la raíz del proyecto.

import os
import re
import sys
from pathlib import Path

# ==================== CONFIGURACIÓN ====================
ARCHIVOS_BUSCAR = ["ciudad.py", "crafteo.py", "viajes.py", "peaje.py"]
# Los archivos se buscarán recursivamente desde el directorio actual.

# ==================== FUNCIONES AUXILIARES ====================
def buscar_archivo(nombre: str, directorio_actual: Path) -> Path | None:
    """Busca un archivo recursivamente, retorna la primera ruta encontrada o None."""
    for ruta in directorio_actual.rglob(nombre):
        if ruta.is_file():
            return ruta
    return None

def leer_archivo(ruta: Path) -> str:
    with open(ruta, "r", encoding="utf-8") as f:
        return f.read()

def guardar_archivo(ruta: Path, contenido: str) -> bool:
    try:
        with open(ruta, "w", encoding="utf-8") as f:
            f.write(contenido)
        return True
    except Exception as e:
        print(f"❌ Error al guardar {ruta}: {e}")
        return False

def eliminar_seccion(contenido: str, inicio_marca: str, fin_marca: str = None) -> str:
    """
    Elimina desde la línea que contiene inicio_marca hasta la línea que contiene fin_marca.
    Si fin_marca es None, elimina solo la línea que contiene inicio_marca.
    """
    lineas = contenido.splitlines(keepends=True)
    nuevas = []
    eliminar = False
    for linea in lineas:
        if not eliminar and re.search(inicio_marca, linea):
            eliminar = True
            if fin_marca is None:
                eliminar = False  # solo elimina esta línea
                continue
            # si hay fin_marca, seguimos eliminando hasta encontrarla
        if eliminar and fin_marca and re.search(fin_marca, linea):
            eliminar = False
            continue
        if not eliminar:
            nuevas.append(linea)
    return "".join(nuevas)

def reemplazar_funcion(contenido: str, nombre_funcion: str, nueva_funcion: str) -> str:
    """
    Reemplaza el cuerpo de una función completa (desde 'def nombre_funcion' hasta la siguiente 'def' o fin de archivo).
    Mantiene la indentación original? Mejor usar búsqueda con regex multilínea.
    """
    patron = rf'(def {nombre_funcion}\(.*?\):.*?)(?=\n\S|\n{re.escape("def ")}|\Z)'
    return re.sub(patron, nueva_funcion, contenido, flags=re.DOTALL)

# ==================== MODIFICACIONES ESPECÍFICAS ====================
def modificar_ciudad(contenido: str) -> str:
    """Elimina crafteo interno y redirige al comando de crafteo.py"""
    # 1. Eliminar diccionario RECETAS
    contenido = eliminar_seccion(contenido, r'^RECETAS\s*=\s*\{', r'^\}')
    # 2. Eliminar funciones ciudad_craftear, craft_seleccionar, craft_cantidad
    for func in ["ciudad_craftear", "craft_seleccionar", "craft_cantidad"]:
        contenido = eliminar_seccion(contenido, rf'^async def {func}\(', r'^(?=\s*async def|\Z)')
    # 3. Eliminar conv_craft y su registro
    contenido = eliminar_seccion(contenido, r'^conv_craft\s*=\s*ConversationHandler\(', r'^\)\s*$')
    contenido = eliminar_seccion(contenido, r'app\.add_handler\(conv_craft\)')
    # 4. Añadir import al inicio (si no existe)
    if "from crafteo import cmd_craftear" not in contenido:
        # Insertar justo después de otros imports (buscar 'import' o 'from' al inicio)
        lineas = contenido.splitlines(keepends=True)
        insertado = False
        for i, linea in enumerate(lineas):
            if linea.startswith("import ") or linea.startswith("from "):
                if i+1 < len(lineas) and (lineas[i+1].startswith("import ") or lineas[i+1].startswith("from ")):
                    continue
                lineas.insert(i+1, "from crafteo import cmd_craftear\n")
                insertado = True
                break
        if not insertado:
            lineas.insert(0, "from crafteo import cmd_craftear\n")
        contenido = "".join(lineas)
    # 5. Añadir función redirect
    redirect_func = '''
async def ciudad_craftear_redirect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await cmd_craftear(update, context)
    await update.callback_query.answer()
'''
    if "ciudad_craftear_redirect" not in contenido:
        # Insertar antes de la última función o al final
        contenido += redirect_func
    # 6. Modificar botón en cmd_ciudad
    # Buscar la línea del botón y reemplazar callback_data
    contenido = re.sub(
        r'InlineKeyboardButton\("🔨 Craftear", callback_data="ciudad_craftear"\)',
        'InlineKeyboardButton("🔨 Craftear", callback_data="ciudad_craftear_redirect")',
        contenido
    )
    # 7. Registrar nuevo callback
    registro = '\n    app.add_handler(CallbackQueryHandler(ciudad_craftear_redirect, pattern="^ciudad_craftear_redirect$"))\n'
    if "ciudad_craftear_redirect" not in contenido:
        # Buscar la función registrar_handlers y añadir al final
        contenido = contenido.replace(
            "def registrar_handlers(app):",
            "def registrar_handlers(app):" + registro,
            1
        )
    return contenido

def modificar_crafteo(contenido: str) -> str:
    """Añade verificación de ciudad azul usando datos_zona"""
    # 1. Añadir import de ZONAS
    if "from datos_zona import ZONAS" not in contenido:
        lineas = contenido.splitlines(keepends=True)
        for i, linea in enumerate(lineas):
            if linea.startswith("import ") or linea.startswith("from "):
                if i+1 < len(lineas) and (lineas[i+1].startswith("import ") or lineas[i+1].startswith("from ")):
                    continue
                lineas.insert(i+1, "from datos_zona import ZONAS\n")
                break
        else:
            lineas.insert(0, "from datos_zona import ZONAS\n")
        contenido = "".join(lineas)
    # 2. Reemplazar la verificación de zona en cmd_craftear
    # Buscar el bloque actual que compara zona != "azul" y reemplazar
    patron_verificacion = r'(zona = db_helper\.obtener_zona_actual\(user_id\))\s*\n\s*(if zona != "azul":.*?\n\s*return)'
    nuevo_bloque = r'''\1
    # Buscar la zona en datos_zona para verificar color y tipo
    zona_info = next((z for z in ZONAS if z["nombre"] == zona), None)
    if not zona_info or zona_info["color"] != "azul" or zona_info["tipo"] != "ciudad":
        await update.effective_message.reply_text("❌ Solo puedes craftear en ciudades de la zona azul.\nRegresa a tu ciudad para usar el taller.")
        return'''
    contenido = re.sub(patron_verificacion, nuevo_bloque, contenido, flags=re.DOTALL)
    return contenido

def modificar_viajes(contenido: str) -> str:
    """Elimina tablas destinos/facciones, añade lectura desde ZONAS y función reanudar_viaje"""
    # 1. Eliminar creación de tablas y ALTER TABLE problemáticos en _init_db
    inicio_init = re.search(r'def _init_db\(\):.*?(?=\n\S|\Z)', contenido, re.DOTALL)
    if inicio_init:
        init_block = inicio_init.group(0)
        # Eliminar líneas que crean 'facciones' y 'destinos'
        nuevo_init = re.sub(r"c\.execute\('''CREATE TABLE IF NOT EXISTS facciones.*?'''\)\s*\n", "", init_block, flags=re.DOTALL)
        nuevo_init = re.sub(r"c\.execute\('''CREATE TABLE IF NOT EXISTS destinos.*?'''\)\s*\n", "", nuevo_init, flags=re.DOTALL)
        # También eliminar los ALTER TABLE para jugadores (opcional, pero los dejamos)
        contenido = contenido.replace(init_block, nuevo_init)
    # 2. Reemplazar las funciones de destinos
    nuevas_funciones = '''
def _obtener_destinos() -> List[Dict]:
    from datos_zona import ZONAS
    destinos = []
    for zona in ZONAS:
        destinos.append({
            "id": zona["id"],
            "nombre": zona["nombre"],
            "color": zona["color"],
            "tipo": zona["tipo"],
            "faccion_id": zona["faccion_id"],
            "nivel_requerido": zona.get("nivel_requerido", 1),
            "orden": zona.get("orden", 999),
        })
    return destinos

def _obtener_destino(destino_id: int) -> Optional[Dict]:
    from datos_zona import ZONAS
    for zona in ZONAS:
        if zona["id"] == destino_id:
            return {
                "id": zona["id"],
                "nombre": zona["nombre"],
                "color": zona["color"],
                "tipo": zona["tipo"],
                "faccion_id": zona["faccion_id"],
                "nivel_requerido": zona.get("nivel_requerido", 1),
            }
    return None

def _obtener_destinos_por_faccion(faccion_id: int) -> List[Dict]:
    return [d for d in _obtener_destinos() if d["faccion_id"] == faccion_id]
'''
    # Eliminar las funciones antiguas (definiciones completas)
    contenido = re.sub(r'def _obtener_destinos\(\) -> List\[Dict\]:.*?(?=\ndef |\Z)', '', contenido, flags=re.DOTALL)
    contenido = re.sub(r'def _obtener_destino\(destino_id: int\) -> Optional\[Dict\]:.*?(?=\ndef |\Z)', '', contenido, flags=re.DOTALL)
    contenido = re.sub(r'def _obtener_destinos_por_faccion\(faccion_id: int\) -> List\[Dict\]:.*?(?=\ndef |\Z)', '', contenido, flags=re.DOTALL)
    # Insertar las nuevas funciones justo después de los imports o al inicio de la sección
    contenido = contenido.replace('import db_helper', 'import db_helper\n\n' + nuevas_funciones)
    # 3. Añadir función reanudar_viaje
    reanudar = '''
async def reanudar_viaje(update: Update, context: ContextTypes.DEFAULT_TYPE, viaje_pendiente: dict):
    destino = _obtener_destino(viaje_pendiente["destino_id"])
    origen = _obtener_destino(viaje_pendiente["origen_id"])
    if destino and origen:
        await _iniciar_viaje_directo(update, context, destino, origen)
'''
    if "reanudar_viaje" not in contenido:
        contenido += reanudar
    return contenido

def modificar_peaje(contenido: str) -> str:
    """Cambia importación para usar reanudar_viaje en lugar de import interna"""
    # 1. Añadir import al inicio
    if "from viajes import reanudar_viaje" not in contenido:
        lineas = contenido.splitlines(keepends=True)
        for i, linea in enumerate(lineas):
            if linea.startswith("import ") or linea.startswith("from "):
                if i+1 < len(lineas) and (lineas[i+1].startswith("import ") or lineas[i+1].startswith("from ")):
                    continue
                lineas.insert(i+1, "from viajes import reanudar_viaje\n")
                break
        else:
            lineas.insert(0, "from viajes import reanudar_viaje\n")
        contenido = "".join(lineas)
    # 2. Reemplazar en procesar_pago_viaje y procesar_marcado_viaje el código que importaba y usaba _iniciar_viaje_directo
    patron_viejo = r'(if viaje_pend:\s+from viajes import _iniciar_viaje_directo, _obtener_destino\s+destino = _obtener_destino\(viaje_pend\["destino_id"\]\)\s+origen = _obtener_destino\(viaje_pend\["origen_id"\]\)\s+if destino and origen:\s+await _iniciar_viaje_directo\(update, context, destino, origen\))'
    nuevo_codigo = 'if viaje_pend:\n        await reanudar_viaje(update, context, viaje_pend)'
    contenido = re.sub(patron_viejo, nuevo_codigo, contenido, flags=re.DOTALL)
    # También limpiar imports dentro de funciones (si las hay)
    contenido = re.sub(r'from viajes import _iniciar_viaje_directo, _obtener_destino', '', contenido)
    return contenido

# ==================== MAIN ====================
def main():
    print("🔍 Buscando archivos en:", os.getcwd())
    raiz = Path.cwd()
    encontrados = {}
    for nombre in ARCHIVOS_BUSCAR:
        ruta = buscar_archivo(nombre, raiz)
        if ruta:
            encontrados[nombre] = ruta
            print(f"✅ Encontrado: {ruta}")
        else:
            print(f"❌ No encontrado: {nombre}")
            print("Abortando. No se realizarán cambios.")
            return
    # Todos encontrados, proceder a leer y modificar en memoria
    modificados = {}
    try:
        contenido = leer_archivo(encontrados["ciudad.py"])
        modificados["ciudad.py"] = modificar_ciudad(contenido)
        print("✔️ ciudad.py modificado en memoria")
    except Exception as e:
        print(f"❌ Error al modificar ciudad.py: {e}")
        return
    try:
        contenido = leer_archivo(encontrados["crafteo.py"])
        modificados["crafteo.py"] = modificar_crafteo(contenido)
        print("✔️ crafteo.py modificado en memoria")
    except Exception as e:
        print(f"❌ Error al modificar crafteo.py: {e}")
        return
    try:
        contenido = leer_archivo(encontrados["viajes.py"])
        modificados["viajes.py"] = modificar_viajes(contenido)
        print("✔️ viajes.py modificado en memoria")
    except Exception as e:
        print(f"❌ Error al modificar viajes.py: {e}")
        return
    try:
        contenido = leer_archivo(encontrados["peaje.py"])
        modificados["peaje.py"] = modificar_peaje(contenido)
        print("✔️ peaje.py modificado en memoria")
    except Exception as e:
        print(f"❌ Error al modificar peaje.py: {e}")
        return
    # Si llegamos aquí, guardar cambios
    print("\n📝 Guardando cambios...")
    for nombre, ruta in encontrados.items():
        if guardar_archivo(ruta, modificados[nombre]):
            print(f"✅ Guardado: {ruta}")
        else:
            print(f"❌ Falló guardado: {ruta}")
            print("Se aborta la operación para evitar inconsistencias.")
            return
    print("\n🎉 ¡Todos los cambios aplicados correctamente!")

if __name__ == "__main__":
    main()
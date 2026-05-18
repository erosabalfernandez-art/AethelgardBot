#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para implementar el comando /start con selección de clase,
asignación de facción equilibrada y creación de personaje en Aethelgard.

Requiere que existan los archivos:
- ciudad.py
- db_helper.py
- clases.py
- datos_zona.py

Realiza backups y cancela si hay errores.
"""

import os
import sys
import re
import shutil
from datetime import datetime
from pathlib import Path

RAIZ = Path.cwd()
BACKUP_DIR = RAIZ / "backups_start"
BACKUP_DIR.mkdir(exist_ok=True)
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
ERRORES = []
MODIFICACIONES = []
OMITIDOS = []

# Colores
class bcolors:
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    OKCYAN = '\033[96m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_ok(msg): print(f"{bcolors.OKGREEN}✅ {msg}{bcolors.ENDC}")
def print_warning(msg): print(f"{bcolors.WARNING}⚠️ {msg}{bcolors.ENDC}")
def print_error(msg): print(f"{bcolors.FAIL}❌ {msg}{bcolors.ENDC}")
def print_info(msg): print(f"{bcolors.OKCYAN}ℹ️ {msg}{bcolors.ENDC}")

def buscar_archivo(nombre_archivo, directorio_inicio=None):
    if directorio_inicio is None:
        directorio_inicio = RAIZ
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

def verificar_archivos():
    archivos_necesarios = ["ciudad.py", "db_helper.py", "clases.py", "datos_zona.py"]
    rutas = {}
    for arch in archivos_necesarios:
        ruta = buscar_archivo(arch)
        if not ruta:
            ERRORES.append(f"No se encontró {arch}")
            print_error(f"No se encontró {arch}")
        else:
            rutas[arch] = ruta
            print_ok(f"Encontrado: {arch}")
    return rutas

def backup_archivo(ruta):
    if not os.path.exists(ruta):
        return None
    backup_path = BACKUP_DIR / f"{Path(ruta).name}.{timestamp}.bak"
    shutil.copy2(ruta, backup_path)
    return backup_path

def aplicar_modificacion(archivo, funcion_modificadora):
    ruta = buscar_archivo(archivo)
    if not ruta:
        ERRORES.append(f"No se encontró {archivo}")
        return False
    try:
        with open(ruta, "r", encoding="utf-8") as f:
            contenido_original = f.read()
    except Exception as e:
        ERRORES.append(f"No se pudo leer {archivo}: {e}")
        return False
    
    backup = backup_archivo(ruta)
    print_info(f"Backup de {archivo} guardado en {backup}")
    
    try:
        nuevo_contenido = funcion_modificadora(contenido_original, ruta)
        if nuevo_contenido == contenido_original:
            OMITIDOS.append(f"{archivo}: ya estaba modificado, sin cambios")
            return True
        compile(nuevo_contenido, ruta, 'exec')
        with open(ruta, "w", encoding="utf-8") as f:
            f.write(nuevo_contenido)
        MODIFICACIONES.append(f"{archivo} modificado correctamente")
        return True
    except SyntaxError as e:
        ERRORES.append(f"Error de sintaxis en {archivo}: {e}. Se restauró backup.")
        if backup:
            shutil.copy2(backup, ruta)
        return False
    except Exception as e:
        ERRORES.append(f"Error inesperado en {archivo}: {e}. Se restauró backup.")
        if backup:
            shutil.copy2(backup, ruta)
        return False

def modificar_db_helper(contenido, ruta):
    """Añade funciones contar_jugadores_por_faccion y obtener_faccion_menos_poblada."""
    if "def contar_jugadores_por_faccion" in contenido:
        OMITIDOS.append("db_helper.py ya tiene funciones de facciones")
        return contenido
    
    funciones = '''

# ==================== FUNCIONES PARA EQUILIBRIO DE FACCIONES ====================
def contar_jugadores_por_faccion() -> dict:
    """Retorna diccionario con número de jugadores por facción."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT faccion, COUNT(*) FROM jugadores GROUP BY faccion')
    rows = c.fetchall()
    conn.close()
    resultado = {}
    for faccion, cuenta in rows:
        resultado[faccion] = cuenta
    # Asegurar que las tres facciones base estén presentes
    for fac in ["Alianza", "Imperio", "Sindicato"]:
        if fac not in resultado:
            resultado[fac] = 0
    return resultado

def obtener_faccion_menos_poblada() -> str:
    """Retorna la facción con menos jugadores (aleatorio si empate)."""
    conteo = contar_jugadores_por_faccion()
    if not conteo:
        return "Alianza"
    min_cuenta = min(conteo.values())
    candidatas = [f for f, c in conteo.items() if c == min_cuenta]
    import random
    return random.choice(candidatas)
'''
    contenido += funciones
    return contenido

def modificar_ciudad(contenido, ruta):
    """Añade el comando /start con flujo completo de registro."""
    # Verificar si ya existe cmd_start
    if "async def cmd_start" in contenido:
        OMITIDOS.append("ciudad.py ya tiene comando /start")
        return contenido
    
    # Buscar el lugar para insertar: después de la sección de imports o antes de registrar_handlers
    # Primero, añadimos las funciones al principio del archivo después de los imports
    bloque_start = '''
# ==================== COMANDO /start (registro de nuevo jugador) ====================
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    jug = db_helper.obtener_jugador(user_id)
    if jug:
        await cmd_ciudad(update, context)
        return
    await update.effective_message.reply_text(
        "✨ ¡Bienvenido a Aethelgard! ✨\\n\\n"
        "Eres un aventurero recién llegado.\\n"
        "Dime el nombre de tu personaje (máximo 20 caracteres, sin espacios):"
    )
    context.user_data["start_estado"] = "esperando_nombre"

async def start_recibir_nombre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("start_estado") != "esperando_nombre":
        return
    nombre = update.message.text.strip()
    if len(nombre) > 20 or " " in nombre:
        await update.effective_message.reply_text("Nombre inválido. Usa máximo 20 caracteres sin espacios. Intenta de nuevo:")
        return
    context.user_data["start_nombre"] = nombre
    context.user_data["start_estado"] = "esperando_clase"
    from clases import CLASES
    keyboard = []
    for clase_id, clase_data in CLASES.items():
        keyboard.append([InlineKeyboardButton(clase_data["nombre"], callback_data=f"start_clase_{clase_id}")])
    await update.effective_message.reply_text(
        "¡Excelente! Ahora elige tu clase. Cada clase tiene habilidades únicas.\\n"
        "No podrás cambiarla fácilmente.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def start_seleccionar_clase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    partes_clase = query.data.split("_")
    if len(partes_clase) < 3:
        await query.edit_message_text("❌ Error al seleccionar clase.")
        return
    clase_id = partes_clase[2]
    from clases import CLASES
    if clase_id not in CLASES:
        await query.edit_message_text("Clase no válida.")
        return
    context.user_data["start_clase"] = clase_id
    faccion = db_helper.obtener_faccion_menos_poblada()
    nombre = context.user_data["start_nombre"]
    user_id = update.effective_user.id
    exito = db_helper.crear_jugador(user_id, nombre, clase_id, faccion)
    if not exito:
        await query.edit_message_text("Hubo un error al crear tu personaje. Contacta con administración.")
        context.user_data.clear()
        return
    context.user_data.clear()
    texto = f"✅ **¡{nombre} ha nacido en Aethelgard!**\\n\\n"
    texto += f"🛡️ **Clase:** {CLASES[clase_id]['nombre']}\\n"
    texto += f"🏛️ **Facción:** {faccion}\\n"
    texto += "⚔️ Tus estadísticas han sido calculadas.\\n"
    texto += "🛡️ Dirígete a la ciudad con /ciudad para comenzar tu aventura."
    await query.edit_message_text(texto, parse_mode="Markdown")
    await cmd_ciudad(update, context)
'''
    # Insertar justo después de los imports (antes de la primera función)
    # Buscar un punto donde añadirlo, por ejemplo después de la línea "import db_helper"
    # O simplemente al principio del archivo, después de los imports.
    # Usaremos un patrón para insertar después de la última importación o después de un comentario específico.
    # Buscar línea "from telegram.ext import" o similar.
    patron_imports = r'(from telegram.ext import.*\n)(?=\n|async def)'
    if re.search(patron_imports, contenido):
        contenido = re.sub(patron_imports, r'\1' + bloque_start + '\n', contenido)
    else:
        # Fallback: añadir al principio después del shebang
        contenido = re.sub(r'(#!/usr/bin/env python3.*?\n)', r'\1' + bloque_start + '\n', contenido, flags=re.DOTALL)
    
    # Registrar el handler de start y los callbacks en registrar_handlers
    # Buscar la función registrar_handlers
    patron_registro = r'(def registrar_handlers\(app\):.*?)(?=\n\s*app\.add_handler)'
    nuevo_handler = '''
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, start_recibir_nombre))
    app.add_handler(CallbackQueryHandler(start_seleccionar_clase, pattern="^start_clase_"))
'''
    # Insertar después de la línea def registrar_handlers
    if "def registrar_handlers" in contenido:
        contenido = re.sub(r'(def registrar_handlers\(app\):.*?\n)', r'\1' + nuevo_handler, contenido, flags=re.DOTALL)
    else:
        # Si no hay registrar_handlers, crear uno al final
        contenido += '''

def registrar_handlers(app):
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, start_recibir_nombre))
    app.add_handler(CallbackQueryHandler(start_seleccionar_clase, pattern="^start_clase_"))
    # Aquí podrían ir otros handlers
'''
    # Asegurar que se importen filtros de mensaje
    if "from telegram.ext import filters" not in contenido:
        contenido = contenido.replace("from telegram.ext import (", "from telegram.ext import (\n    filters,")
        contenido = contenido.replace("from telegram.ext import ", "from telegram.ext import filters, ")
    
    return contenido

def main():
    print(f"{bcolors.BOLD}{bcolors.HEADER}")
    print("="*60)
    print("   IMPLEMENTACIÓN DE COMANDO /start Y SELECCIÓN DE CLASE")
    print("="*60)
    print(f"{bcolors.ENDC}")
    
    rutas = verificar_archivos()
    if ERRORES:
        print_error(f"Faltan archivos: {ERRORES}")
        sys.exit(1)
    
    print_info("\nModificando db_helper.py...")
    if not aplicar_modificacion("db_helper.py", modificar_db_helper):
        print_error("No se pudo modificar db_helper.py. Cancelando.")
        sys.exit(1)
    
    print_info("\nModificando ciudad.py...")
    if not aplicar_modificacion("ciudad.py", modificar_ciudad):
        print_error("No se pudo modificar ciudad.py. Cancelando.")
        sys.exit(1)
    
    print("\n" + "="*60)
    if ERRORES:
        print_error("Se produjeron errores:")
        for e in ERRORES:
            print_error(f"  - {e}")
    else:
        print_ok("¡Implementación completada con éxito!")
    
    if MODIFICACIONES:
        print_ok("\nModificaciones realizadas:")
        for m in MODIFICACIONES:
            print_ok(f"  - {m}")
    
    if OMITIDOS:
        print_info("\nElementos ya existentes (no modificados):")
        for o in OMITIDOS:
            print_info(f"  - {o}")
    
    print_info(f"\nBackups guardados en: {BACKUP_DIR}")
    print_info("Si todo funciona, puedes eliminar la carpeta de backups.")

if __name__ == "__main__":
    main()
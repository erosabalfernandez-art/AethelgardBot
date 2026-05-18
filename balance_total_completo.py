#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SCRIPT DE BALANCE TOTAL COMPLETO PARA AETHELGARD
- Cancela la operación si algo falla o no encuentra patrones
- NO modifica db_helper.py (ya está actualizado manualmente)
- Hace backup y restaura si hay error
- Incluye todas las modificaciones del séptimo script original
"""

import os
import sys
import re
import shutil
import importlib.util
import random
from datetime import datetime
from pathlib import Path

# ==================== CONFIGURACIÓN ====================
RAIZ = Path.cwd()
BACKUP_DIR = RAIZ / "backups_balance_completo"
BACKUP_DIR.mkdir(exist_ok=True)
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

ERRORES = []
MODIFICACIONES = []
OMITIDOS = []
BACKUPS_REALIZADOS = []

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_ok(msg):
    print(f"{bcolors.OKGREEN}✅ {msg}{bcolors.ENDC}")
def print_warning(msg):
    print(f"{bcolors.WARNING}⚠️ {msg}{bcolors.ENDC}")
def print_error(msg):
    print(f"{bcolors.FAIL}❌ {msg}{bcolors.ENDC}")
def print_info(msg):
    print(f"{bcolors.OKCYAN}ℹ️ {msg}{bcolors.ENDC}")

# ==================== BÚSQUEDA RECURSIVA ====================
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

# ==================== VERIFICACIÓN DE ARCHIVOS ====================
ARCHIVOS_NECESARIOS = [
    "tienda.py",
    "combate.py",
    "economia.py",
    "generar_recoleccion.py",
    "generar_investigacion.py"
]

ARCHIVOS_OPCIONALES = [
    "generar_mazmorras.py"
]

def verificar_archivos():
    print_info("Verificando archivos necesarios...")
    rutas = {}
    for arch in ARCHIVOS_NECESARIOS:
        ruta = buscar_archivo(arch)
        if not ruta:
            ERRORES.append(f"No se encontró {arch}")
            print_error(f"No se encontró {arch}")
        else:
            rutas[arch] = ruta
            print_ok(f"Encontrado: {arch}")
    for arch in ARCHIVOS_OPCIONALES:
        ruta = buscar_archivo(arch)
        if ruta:
            rutas[arch] = ruta
            print_info(f"Encontrado (opcional): {arch}")
        else:
            print_warning(f"No se encontró {arch} (opcional, se omitirá)")
    return rutas

# ==================== COPIA DE SEGURIDAD ====================
def backup_archivo(ruta):
    if not os.path.exists(ruta):
        return None
    backup_path = BACKUP_DIR / f"{Path(ruta).name}.{timestamp}.bak"
    shutil.copy2(ruta, backup_path)
    BACKUPS_REALIZADOS.append(backup_path)
    return backup_path

def restaurar_todo():
    print_error("\n⚠️ CANCELANDO OPERACIÓN. Restaurando backups...")
    for backup in BACKUPS_REALIZADOS:
        original = Path(str(backup).replace(f".{timestamp}.bak", ""))
        if original.exists():
            shutil.copy2(backup, original)
            print_info(f"Restaurado: {original.name}")
    print_info("Backups restaurados. Tus archivos originales están intactos.")

# ==================== APLICAR MODIFICACIÓN SEGURA ====================
def aplicar_modificacion(archivo, nombre, funcion_modificadora, ruta):
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
        if nuevo_contenido is None:
            OMITIDOS.append(f"{archivo}: ya estaba modificado, no se hicieron cambios")
            return True
        if nuevo_contenido == contenido_original:
            OMITIDOS.append(f"{archivo}: no hubo cambios necesarios")
            return True
        compile(nuevo_contenido, ruta, 'exec')
        with open(ruta, "w", encoding="utf-8") as f:
            f.write(nuevo_contenido)
        MODIFICACIONES.append(f"{archivo} modificado correctamente")
        return True
    except SyntaxError as e:
        ERRORES.append(f"Error de sintaxis en {archivo} después de modificar: {e}")
        return False
    except Exception as e:
        ERRORES.append(f"Error inesperado al modificar {archivo}: {e}")
        return False

# ==================== CREAR config_balance.py ====================
def crear_config_balance():
    ruta = RAIZ / "config_balance.py"
    if ruta.exists():
        OMITIDOS.append("config_balance.py ya existe, no se sobrescribe")
        return True
    contenido = '''# config_balance.py
# Archivo de configuración de balance del juego.

# ==================== STAMINA ====================
STAMINA_MAX_BASE = 100
STAMINA_REGENERACION_SEGUNDOS = 180
STAMINA_COSTE_POR_ZONA = {
    "azul": 15,
    "amarilla": 25,
    "roja": 40,
    "negra": 60
}
STAMINA_BONUS_POR_RECLUTA = 5
STAMINA_MAX_EXTRA = 200

# ==================== INVITACIONES ====================
INVITACION_RECLUTA_RECIBE_POCIONES = 2
INVITACION_NIVEL_REQUERIDO_BONUS = 15

# ==================== MAZMORRAS ====================
MAZMORRAS_LIMITE_DIARIO = 2
MAZMORRAS_COSTES_ENTRADA = {"azul": 200, "amarilla": 300, "roja": 400, "negra": 20}
MAZMORRAS_RECOMPENSA_ETERNIUM_NORMAL = {"azul": (2,5), "amarilla": (5,10), "roja": (10,20), "negra": (20,40)}
MAZMORRAS_RECOMPENSA_ETERNIUM_DIFICIL = {"azul": (6,10), "amarilla": (12,20), "roja": (25,40), "negra": (50,80)}

# ==================== BANCO ====================
BANCO_CREDITO_A_ETERNIUM = 10
BANCO_CREDITO_A_ORO = 10000
BANCO_PERMITIR_COMPRA_ETERNIUM_CON_ORO = False
BANCO_PERMITIR_VENTA_ETERNIUM_POR_ORO = False

# ==================== TIENDA ====================
TIENDA_ROTACION_CREDITOS_DIAS = 5
TIENDA_VENTA_PORCENTAJE = 0.5

# ==================== TABERNA ====================
TABERNA_RECUPERA_STAMINA = False
TABERNA_COSTO_DESCANSAR = 50
'''
    try:
        with open(ruta, "w", encoding="utf-8") as f:
            f.write(contenido)
        MODIFICACIONES.append("config_balance.py creado")
        return True
    except Exception as e:
        ERRORES.append(f"No se pudo crear config_balance.py: {e}")
        return False

# ==================== MODIFICACIONES COMPLETAS ====================
def modificar_ciudad(contenido, ruta):
    if "ciudad_tienda_oro" in contenido:
        OMITIDOS.append("ciudad.py ya tiene botones de tienda")
        return None
    
    redirects = '''
async def ciudad_tienda_oro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from tienda import cmd_tienda
    await cmd_tienda(update, context)
    await update.callback_query.answer()

async def ciudad_tienda_eternium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from tienda import cmd_tienda
    await cmd_tienda(update, context)
    await update.callback_query.answer()

async def ciudad_tienda_creditos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from tienda import cmd_tienda
    await cmd_tienda(update, context)
    await update.callback_query.answer()
'''
    contenido += redirects
    
    patron = r'(keyboard = \[.*?\n)(.*?)(?=\n\s*await update\.message\.reply_text)'
    nuevos_botones = '        [InlineKeyboardButton("🪙 Tienda Oro", callback_data="ciudad_tienda_oro")],\n        [InlineKeyboardButton("💎 Tienda Eternium", callback_data="ciudad_tienda_eternium")],\n        [InlineKeyboardButton("✨ Tienda Créditos", callback_data="ciudad_tienda_creditos")],\n'
    if not re.search(patron, contenido, re.DOTALL):
        ERRORES.append("No se encontró la lista de botones en ciudad.py")
        return None
    contenido = re.sub(patron, r'\1' + nuevos_botones + r'\2', contenido, flags=re.DOTALL)
    
    if "ciudad_tienda_oro" not in contenido:
        contenido = contenido.replace("def registrar_handlers(app):", 
            "def registrar_handlers(app):\n    app.add_handler(CallbackQueryHandler(ciudad_tienda_oro, pattern=\"^ciudad_tienda_oro$\"))\n    app.add_handler(CallbackQueryHandler(ciudad_tienda_eternium, pattern=\"^ciudad_tienda_eternium$\"))\n    app.add_handler(CallbackQueryHandler(ciudad_tienda_creditos, pattern=\"^ciudad_tienda_creditos$\"))\n")
    return contenido

def modificar_combate(contenido, ruta):
    if "MAZMORRAS_RECOMPENSA_ETERNIUM_NORMAL" in contenido:
        OMITIDOS.append("combate.py ya tiene recompensa de eternium")
        return None
    
    if "import config_balance" not in contenido:
        contenido = contenido.replace("import economia", "import economia\nimport config_balance")
    
    patron = r'(async def finalizar_mazmorra\(.*?\):.*?)(?=\n\s*async def|\Z)'
    bloque = r'''\1
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
'''
    if not re.search(patron, contenido, re.DOTALL):
        ERRORES.append("No se encontró la función finalizar_mazmorra en combate.py")
        return None
    contenido = re.sub(patron, bloque, contenido, flags=re.DOTALL, count=1)
    return contenido

def modificar_banco(contenido, ruta):
    if "BANCO_CREDITO_A_ETERNIUM" in contenido:
        OMITIDOS.append("banco.py ya está modificado")
        return None
    
    if "import config_balance" not in contenido:
        contenido = contenido.replace("import economia", "import economia\nimport config_balance")
    
    patron_menu = r'(keyboard = \[.*?\])(?=\s*await query\.edit_message_text)'
    nuevo_menu = '''keyboard = [
        [InlineKeyboardButton("⬇️ Créditos → Eternium", callback_data="banco_creditos_a_et")],
        [InlineKeyboardButton("⬇️ Créditos → Oro", callback_data="banco_creditos_a_oro")],
        [InlineKeyboardButton("📜 Historial", callback_data="banco_historial")],
        [InlineKeyboardButton("📊 Mis estadísticas", callback_data="banco_estadisticas")],
        [InlineKeyboardButton("❌ Cerrar", callback_data="banco_cerrar")]
    ]'''
    if re.search(patron_menu, contenido, re.DOTALL):
        contenido = re.sub(patron_menu, nuevo_menu, contenido, flags=re.DOTALL)
    else:
        ERRORES.append("No se encontró el menú del banco en banco.py")
        return None
    
    if "async def inicio_creditos_a_et" not in contenido:
        funciones_banco = '''
async def inicio_creditos_a_et(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("¿Cuántos créditos deseas convertir a eternium? (Escribe un número entero):")
    return 10

async def recibir_cantidad_creditos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        cantidad = int(update.message.text.strip())
    except ValueError:
        await update.effective_message.reply_text("Cantidad inválida.")
        return 10
    if cantidad <= 0:
        await update.effective_message.reply_text("La cantidad debe ser positiva.")
        return 10
    saldos = economia.obtener_saldos(user_id)
    if saldos["creditos_vacio"] < cantidad:
        await update.effective_message.reply_text(f"No tienes suficientes créditos. Tienes {saldos['creditos_vacio']}.")
        return 10
    et_obtenido = cantidad * config_balance.BANCO_CREDITO_A_ETERNIUM
    context.user_data["cambio"] = {
        "tipo": "credito_a_et",
        "origen": cantidad,
        "destino": et_obtenido,
        "comision": 0
    }
    keyboard = [[InlineKeyboardButton("✅ Confirmar", callback_data="confirmar_cambio"), InlineKeyboardButton("❌ Cancelar", callback_data="cancelar_cambio")]]
    await update.effective_message.reply_text(
        f"Vas a convertir {cantidad} créditos.\nRecibirás {et_obtenido} eternium.\n¿Confirmas la operación?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return -1

async def inicio_creditos_a_oro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("¿Cuántos créditos deseas convertir a oro? (Escribe un número entero):")
    return 10

async def recibir_cantidad_creditos_oro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        cantidad = int(update.message.text.strip())
    except ValueError:
        await update.effective_message.reply_text("Cantidad inválida.")
        return 10
    if cantidad <= 0:
        await update.effective_message.reply_text("La cantidad debe ser positiva.")
        return 10
    saldos = economia.obtener_saldos(user_id)
    if saldos["creditos_vacio"] < cantidad:
        await update.effective_message.reply_text(f"No tienes suficientes créditos. Tienes {saldos['creditos_vacio']}.")
        return 10
    oro_obtenido = cantidad * config_balance.BANCO_CREDITO_A_ORO
    context.user_data["cambio"] = {
        "tipo": "credito_a_oro",
        "origen": cantidad,
        "destino": oro_obtenido,
        "comision": 0
    }
    keyboard = [[InlineKeyboardButton("✅ Confirmar", callback_data="confirmar_cambio"), InlineKeyboardButton("❌ Cancelar", callback_data="cancelar_cambio")]]
    await update.effective_message.reply_text(
        f"Vas a convertir {cantidad} créditos.\nRecibirás {oro_obtenido} oro.\n¿Confirmas la operación?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return -1
'''
        contenido += funciones_banco
    
    patron_confirmar = r'(async def confirmar_cambio\(update: Update, context: ContextTypes\.DEFAULT_TYPE\):.*?)(?=\n\s*async def|\Z)'
    nuevo_confirmar = r'''\1
    if tipo == "credito_a_et":
        exito = economia.modificar_saldo(user_id, "creditos_vacio", -origen, f"conversión a eternium (banco)")
        if exito:
            economia.modificar_saldo(user_id, "eternium", destino, f"conversión desde créditos (banco)")
    elif tipo == "credito_a_oro":
        exito = economia.modificar_saldo(user_id, "creditos_vacio", -origen, f"conversión a oro (banco)")
        if exito:
            economia.modificar_saldo(user_id, "oro", destino, f"conversión desde créditos (banco)")
'''
    if re.search(patron_confirmar, contenido, re.DOTALL):
        contenido = re.sub(patron_confirmar, nuevo_confirmar, contenido, flags=re.DOTALL)
    else:
        print_warning("No se encontró la función confirmar_cambio en banco.py")
    
    return contenido

def modificar_economia(contenido, ruta):
    if "TIEMPO_ROTACION_HORAS = 120" in contenido:
        OMITIDOS.append("economia.py ya tiene rotación de 120 horas")
        return None
    contenido = re.sub(r'TIEMPO_ROTACION_HORAS\s*=\s*\d+', 'TIEMPO_ROTACION_HORAS = 120', contenido)
    return contenido

def modificar_tienda(contenido, ruta):
    if "import config_balance" in contenido:
        OMITIDOS.append("tienda.py ya tiene config_balance")
        return None
    contenido = contenido.replace("import economia", "import economia\nimport config_balance")
    contenido = re.sub(r'TIENDA_VENTA_PORCENTAJE\s*=\s*0\.5', 'TIENDA_VENTA_PORCENTAJE = config_balance.TIENDA_VENTA_PORCENTAJE', contenido)
    contenido = re.sub(r'ROTACION_HORAS\s*=\s*\d+\*24', 'ROTACION_HORAS = config_balance.TIENDA_ROTACION_CREDITOS_DIAS * 24', contenido)
    return contenido

def modificar_generador_recoleccion(contenido, ruta):
    if "gastar_stamina" in contenido:
        OMITIDOS.append("generar_recoleccion.py ya tiene verificación de stamina")
        return None
    
    patron = r'(async def cmd_recolectar\(update: Update, context: ContextTypes\.DEFAULT_TYPE\):.*?)(?=zona_config = _obtener_config_zona_actual)'
    bloque = '''
    user_id = update.effective_user.id
    from datos_zona import ZONAS
    import config_balance
    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        await update.effective_message.reply_text("No estás registrado.")
        return
    zona_nombre = jug.get("zona_actual", "")
    zona_info = next((z for z in ZONAS if z["nombre"] == zona_nombre), None)
    if not zona_info:
        await update.effective_message.reply_text("No se pudo determinar tu zona.")
        return
    color = zona_info["color"]
    costo = config_balance.STAMINA_COSTE_POR_ZONA.get(color, 20)
    if not db_helper.gastar_stamina(user_id, costo):
        await update.effective_message.reply_text(f"❌ No tienes suficiente stamina. Necesitas {costo}. Espera a que se regenere.")
        return
'''
    if not re.search(patron, contenido, re.DOTALL):
        ERRORES.append("No se encontró el patrón para stamina en generar_recoleccion.py")
        return None
    contenido = re.sub(patron, r'\1' + bloque, contenido, flags=re.DOTALL)
    return contenido

def modificar_generador_investigacion(contenido, ruta):
    if "gastar_stamina" in contenido:
        OMITIDOS.append("generar_investigacion.py ya tiene verificación de stamina")
        return None
    
    patron = r'(async def seguir_huellas\(update: Update, context: ContextTypes\.DEFAULT_TYPE, zona_nombre: str\):.*?)(?=if not _gastar_stamina)'
    bloque = '''
    user_id = update.effective_user.id
    from datos_zona import ZONAS
    import config_balance
    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        await query.edit_message_text("No estás registrado.")
        return
    zona_info = next((z for z in ZONAS if z["nombre"] == zona_nombre), None)
    if not zona_info:
        color = "azul"
    else:
        color = zona_info["color"]
    costo = config_balance.STAMINA_COSTE_POR_ZONA.get(color, 20)
    if not db_helper.gastar_stamina(user_id, costo):
        await query.edit_message_text(f"❌ No tienes suficiente stamina. Necesitas {costo}. Espera a que se regenere.")
        return
'''
    if not re.search(patron, contenido, re.DOTALL):
        ERRORES.append("No se encontró el patrón para stamina en generar_investigacion.py")
        return None
    contenido = re.sub(patron, r'\1' + bloque, contenido, flags=re.DOTALL)
    return contenido

def modificar_generador_mazmorras(contenido, ruta):
    if "comprobar_limite_mazmorra" in contenido:
        OMITIDOS.append("generar_mazmorras.py ya tiene límites diarios")
        return None
    
    if "import config_balance" not in contenido:
        contenido = contenido.replace("import db_helper", "import db_helper\nimport config_balance")
    
    patron = r'(def _puede_entrar\(user_id: int\) -> Tuple\[bool, str\]:.*?)(?=\n\s*def _cobrar_entrada|\Z)'
    bloque = r'''\1
    # Verificar límite diario
    if not db_helper.comprobar_limite_mazmorra(user_id, COLOR):
        return False, f"Ya has usado tus {config_balance.MAZMORRAS_LIMITE_DIARIO} entradas diarias para mazmorras {COLOR}. Vuelve mañana."
    # Verificar estado marcado
    if db_helper.esta_marcado(user_id):
        return False, "❌ Estás marcado. No puedes entrar a la mazmorra hasta que pagues rescate con /pagar_rescate."
    # Verificar stamina
    if COSTO_STAMINA > 0 and not db_helper.gastar_stamina(user_id, COSTO_STAMINA):
        return False, f"No tienes suficiente stamina. Necesitas {COSTO_STAMINA}."
'''
    if not re.search(patron, contenido, re.DOTALL):
        print_warning("No se encontró la función _puede_entrar en generar_mazmorras.py")
        return contenido
    
    contenido = re.sub(patron, bloque, contenido, flags=re.DOTALL)
    
    # Reemplazar costes con los de config_balance (como string literal, no variable)
    costes_literal = str(config_balance.MAZMORRAS_COSTES_ENTRADA)
    contenido = re.sub(r'COSTES = \{.*?\}', f'COSTES = {costes_literal}', contenido)
    return contenido

# ==================== MAIN ====================
def main():
    print(f"{bcolors.HEADER}{bcolors.BOLD}")
    print("="*60)
    print("      BALANCE TOTAL COMPLETO PARA AETHELGARD")
    print("="*60)
    print(f"{bcolors.ENDC}")
    
    rutas = verificar_archivos()
    if ERRORES:
        print_error(f"\nSe encontraron {len(ERRORES)} errores. Cancelando operación.")
        for err in ERRORES:
            print_error(f"  - {err}")
        sys.exit(1)
    
    print_info("\nCreando config_balance.py...")
    if not crear_config_balance():
        print_error("No se pudo crear config_balance.py. Cancelando.")
        restaurar_todo()
        sys.exit(1)
    
    modificadores = [
        ("ciudad.py", modificar_ciudad),
        ("combate.py", modificar_combate),
        ("banco.py", modificar_banco),
        ("economia.py", modificar_economia),
        ("tienda.py", modificar_tienda),
        ("generar_recoleccion.py", modificar_generador_recoleccion),
        ("generar_investigacion.py", modificar_generador_investigacion)
    ]
    
    if "generar_mazmorras.py" in rutas:
        modificadores.append(("generar_mazmorras.py", modificar_generador_mazmorras))
    
    for nombre, mod_func in modificadores:
        if nombre not in rutas:
            print_warning(f"No se encontró {nombre}, se omite.")
            continue
        print_info(f"Modificando {nombre}...")
        exito = aplicar_modificacion(nombre, nombre, mod_func, rutas[nombre])
        if not exito:
            print_error(f"Fallo al modificar {nombre}. Cancelando todo.")
            restaurar_todo()
            sys.exit(1)
    
    print("\n" + "="*60)
    if ERRORES:
        print_error("Se produjeron errores:")
        for e in ERRORES:
            print_error(f"  - {e}")
        restaurar_todo()
        sys.exit(1)
    else:
        print_ok("¡Balance completado con éxito!")
    
    if MODIFICACIONES:
        print_ok("\nModificaciones realizadas:")
        for m in MODIFICACIONES:
            print_ok(f"  - {m}")
    
    if OMITIDOS:
        print_info("\nElementos ya existentes (no se modificaron):")
        for o in OMITIDOS:
            print_info(f"  - {o}")
    
    print_info(f"\nBackups guardados en: {BACKUP_DIR}")
    print_info("Si todo funciona, puedes eliminar la carpeta de backups.")
    print_info("\n⚠️ IMPORTANTE: Después de ejecutar este script, debes regenerar tus archivos de recolección e investigación con:")
    print_info("   python generar_recoleccion.py --all")
    print_info("   python generar_investigacion.py --all")

if __name__ == "__main__":
    main()
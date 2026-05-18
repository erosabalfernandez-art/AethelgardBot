#!/usr/bin/env python3
# generar_investigacion.py
# Genera archivos de investigación (/investigar) para zonas salvajes.
# Soporta --all y respeta las carpetas con espacios.

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
    "combate.py": "Motor de combate (iniciar_combate)",
    "db_helper.py": "Base de datos"
}

print("\n🔍 VERIFICANDO ARCHIVOS PARA GENERADOR DE INVESTIGACIÓN...")
todos_ok = True
for archivo, desc in ARCHIVOS_CRITICOS.items():
    ruta = buscar_archivo(archivo, RAIZ)
    if ruta:
        print(f"✅ Encontrado: {archivo} en {ruta}")
    else:
        print(f"❌ ERROR CRÍTICO: No se encontró {archivo} ({desc})")
        todos_ok = False
if not todos_ok:
    print("❌ Faltan archivos críticos. El generador no puede continuar.")
    sys.exit(1)

print("✅ Todos los archivos críticos están presentes.\n")

try:
    from datos_zona import ZONAS
    print(f"✅ Se cargaron {len(ZONAS)} zonas desde datos_zona.py")
except ImportError:
    print("❌ Error al importar datos_zona.py")
    sys.exit(1)

CARPETA_POR_COLOR = {
    "azul": "zonas azules",
    "amarilla": "zonas amarillas",
    "roja": "zonas rojas",
    "negra": "zonas negras"
}

def generar_investigacion(color: str, output_dir: str = None):
    zonas = [z for z in ZONAS if z["color"] == color and z["tipo"] == "salvaje"]
    if not zonas:
        print(f"⚠️ No hay zonas salvajes de color {color}.")
        return
    print(f"📝 Generando investigación para {len(zonas)} zonas {color}.")

    zonas_info = {}
    for zona in zonas:
        zonas_info[zona["nombre"]] = {
            "zona_id": zona["id"],
            "nivel": zona["nivel_requerido"],
            "color": color
        }

    if output_dir is None:
        output_dir = CARPETA_POR_COLOR.get(color, f"zonas_{color}s")
    os.makedirs(output_dir, exist_ok=True)
    archivo_salida = os.path.join(output_dir, f"investigacion_{color}.py")

    with open(archivo_salida, "w", encoding="utf-8") as f:
        f.write("#!/usr/bin/env python3\n")
        f.write(f"# investigacion_{color}.py\n")
        f.write(f"# Generado automáticamente por generar_investigacion.py para zona {color}\n\n")

        f.write("import random\n")
        f.write("import sqlite3\n")
        f.write("import os\n")
        f.write("import importlib.util\n")
        f.write("from datetime import datetime, timedelta\n")
        f.write("from typing import Optional, Tuple\n\n")
        f.write("from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup\n")
        f.write("from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler\n\n")
        f.write("import db_helper\n")
        f.write("import config_balance\n")
        f.write("from combate import iniciar_combate, COMBATE_PVE_AZUL, COMBATE_PVE_AMARILLA, COMBATE_PVE_ROJA, COMBATE_PVE_NEGRA\n\n")
        f.write("DB_PATH = \"aethelgard.db\"\n\n")

        f.write("CARPETA_POR_COLOR = {\n")
        for c, carpeta in CARPETA_POR_COLOR.items():
            f.write(f"    {repr(c)}: {repr(carpeta)},\n")
        f.write("}\n\n")

        f.write("ZONAS_INFO = {\n")
        for nombre, info in zonas_info.items():
            f.write(f"    {repr(nombre)}: {{'zona_id': {info['zona_id']}, 'nivel': {info['nivel']}, 'color': {repr(info['color'])}}},\n")
        f.write("}\n\n")

        f.write("STAMINA_MAX = 100\n")
        f.write("STAMINA_RECARGA_POR_MINUTO = 0.2\n\n")
        
        # Funciones de stamina reales usando db_helper
        f.write("def _obtener_stamina(user_id: int) -> Tuple[int, int]:\n")
        f.write("    actual, maximo, _ = db_helper.obtener_stamina(user_id)\n")
        f.write("    return actual, maximo\n\n")
        f.write("def _gastar_stamina(user_id: int, costo: int) -> bool:\n")
        f.write("    return db_helper.gastar_stamina(user_id, costo)\n\n")

        f.write("def _init_paz_db():\n")
        f.write("    conn = sqlite3.connect(DB_PATH)\n")
        f.write("    c = conn.cursor()\n")
        f.write("    c.execute('''CREATE TABLE IF NOT EXISTS estado_paz (\n")
        f.write("        user_id INTEGER PRIMARY KEY,\n")
        f.write("        activo BOOLEAN DEFAULT 0,\n")
        f.write("        fin_inmunidad TIMESTAMP,\n")
        f.write("        ventana_activa_hasta TIMESTAMP,\n")
        f.write("        cooldown_hasta TIMESTAMP,\n")
        f.write("        tipo_ventana TEXT,\n")
        f.write("        color_actual TEXT\n")
        f.write("    )''')\n")
        f.write("    c.execute('''CREATE TABLE IF NOT EXISTS penalizacion_peleas (\n")
        f.write("        user_id INTEGER,\n")
        f.write("        color_zona TEXT,\n")
        f.write("        peleas_pve INTEGER DEFAULT 0,\n")
        f.write("        PRIMARY KEY (user_id, color_zona)\n")
        f.write("    )''')\n")
        f.write("    conn.commit()\n")
        f.write("    conn.close()\n")
        f.write("_init_paz_db()\n\n")

        f.write("def _obtener_ventana_paz(user_id: int) -> Optional[Tuple[str, datetime]]:\n")
        f.write("    conn = sqlite3.connect(DB_PATH)\n")
        f.write("    c = conn.cursor()\n")
        f.write("    c.execute('SELECT tipo_ventana, ventana_activa_hasta FROM estado_paz WHERE user_id = ?', (user_id,))\n")
        f.write("    row = c.fetchone()\n")
        f.write("    conn.close()\n")
        f.write("    if row and row[1]:\n")
        f.write("        hasta = datetime.fromisoformat(row[1])\n")
        f.write("        if hasta > datetime.now():\n")
        f.write("            return row[0], hasta\n")
        f.write("    return None\n\n")

        f.write("def _calcular_duracion_paz_post_combate(user_id: int, color_zona: str) -> int:\n")
        f.write("    base = 120\n")
        f.write("    conn = sqlite3.connect(DB_PATH)\n")
        f.write("    c = conn.cursor()\n")
        f.write("    c.execute('SELECT peleas_pve FROM penalizacion_peleas WHERE user_id = ? AND color_zona = ?', (user_id, color_zona))\n")
        f.write("    row = c.fetchone()\n")
        f.write("    peleas = row[0] if row else 0\n")
        f.write("    conn.close()\n")
        f.write("    penalizacion = peleas * 15\n")
        f.write("    return max(15, base - penalizacion)\n\n")

        f.write("def _activar_paz(user_id: int, duracion_segundos: int):\n")
        f.write("    fin = datetime.now() + timedelta(seconds=duracion_segundos)\n")
        f.write("    conn = sqlite3.connect(DB_PATH)\n")
        f.write("    c = conn.cursor()\n")
        f.write("    c.execute('''INSERT OR REPLACE INTO estado_paz (user_id, activo, fin_inmunidad, ventana_activa_hasta, cooldown_hasta)\n")
        f.write("                 VALUES (?, 1, ?, NULL, NULL)''', (user_id, fin.isoformat()))\n")
        f.write("    conn.commit()\n")
        f.write("    conn.close()\n\n")

        f.write("def _desactivar_paz(user_id: int):\n")
        f.write("    conn = sqlite3.connect(DB_PATH)\n")
        f.write("    c = conn.cursor()\n")
        f.write("    c.execute('UPDATE estado_paz SET activo = 0, fin_inmunidad = NULL WHERE user_id = ?', (user_id,))\n")
        f.write("    conn.commit()\n")
        f.write("    conn.close()\n\n")

        f.write("def _esta_en_paz(user_id: int) -> bool:\n")
        f.write("    conn = sqlite3.connect(DB_PATH)\n")
        f.write("    c = conn.cursor()\n")
        f.write("    c.execute('SELECT activo, fin_inmunidad FROM estado_paz WHERE user_id = ?', (user_id,))\n")
        f.write("    row = c.fetchone()\n")
        f.write("    conn.close()\n")
        f.write("    if row and row[0] and row[1]:\n")
        f.write("        return datetime.fromisoformat(row[1]) > datetime.now()\n")
        f.write("    return False\n\n")

        f.write("def _abrir_ventana_paz(user_id: int, tipo: str, duracion_segundos: int):\n")
        f.write("    hasta = datetime.now() + timedelta(seconds=duracion_segundos)\n")
        f.write("    conn = sqlite3.connect(DB_PATH)\n")
        f.write("    c = conn.cursor()\n")
        f.write("    c.execute('''INSERT OR REPLACE INTO estado_paz (user_id, ventana_activa_hasta, tipo_ventana)\n")
        f.write("                 VALUES (?, ?, ?)''', (user_id, hasta.isoformat(), tipo))\n")
        f.write("    conn.commit()\n")
        f.write("    conn.close()\n\n")

        f.write("async def cmd_investigar(update: Update, context: ContextTypes.DEFAULT_TYPE):\n")
        f.write("    user_id = update.effective_user.id\n")
        f.write("    if db_helper.esta_marcado(user_id):\n")
        f.write("        await update.effective_message.reply_text(\"❌ Estás marcado. No puedes investigar hasta que pagues rescate con /pagar_rescate.\")\n")
        f.write("        return\n")
        f.write("    jug = db_helper.obtener_jugador(user_id)\n")
        f.write("    if not jug:\n")
        f.write("        await update.effective_message.reply_text(\"No estás registrado.\")\n")
        f.write("        return\n")
        f.write("    zona_nombre = jug.get(\"zona_actual\", \"\")\n")
        f.write("    if zona_nombre not in ZONAS_INFO:\n")
        f.write("        await update.effective_message.reply_text(\"No estás en una zona válida para investigar.\")\n")
        f.write("        return\n")
        f.write("    stamina_actual, stamina_max = _obtener_stamina(user_id)\n")
        f.write("    texto = (\n")
        f.write("        f\"🔍 **Investigación - Zona: {zona_nombre}** 🔍\\n\\n\"\n")
        f.write("        f\"⚡ Stamina: {stamina_actual}/{stamina_max}\\n\\n\"\n")
        f.write("        \"Selecciona una acción:\\n\"\n")
        f.write("        \"👣 **Seguir huellas** - Encuentra monstruos (30% normal, 65% mini boss, 5% nada)\\n\"\n")
        f.write("        \"🧘‍♂️ **Meditar** - Entra en estado de paz para evitar ataques PvP\\n\"\n")
        f.write("    )\n")
        f.write("    keyboard = [\n")
        f.write("        [InlineKeyboardButton(\"👣 Seguir huellas\", callback_data=f\"investigar_huellas_{zona_nombre}\")],\n")
        f.write("        [InlineKeyboardButton(\"🧘‍♂️ Meditar\", callback_data=f\"investigar_meditar_{zona_nombre}\")],\n")
        f.write("        [InlineKeyboardButton(\"❌ Cerrar\", callback_data=\"investigar_cerrar\")]\n")
        f.write("    ]\n")
        f.write("    await update.effective_message.reply_text(texto, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=\"Markdown\")\n\n")
        f.write("async def seguir_huellas(update: Update, context: ContextTypes.DEFAULT_TYPE, zona_nombre: str):\n")
        f.write("    query = update.callback_query\n")
        f.write("    await query.answer()\n")
        f.write("    user_id = update.effective_user.id\n")
        f.write("    if db_helper.esta_marcado(user_id):\n")
        f.write("        await query.edit_message_text(\"❌ Estás marcado. No puedes seguir huellas hasta que pagues rescate con /pagar_rescate.\")\n")
        f.write("        return\n")
        f.write("    # Verificar y gastar stamina (costo fijo de 5)\n")
        f.write("    costo_stamina = 5\n")
        f.write("    if not _gastar_stamina(user_id, costo_stamina):\n")
        f.write("        await query.edit_message_text(f\"❌ No tienes suficiente stamina. Necesitas {costo_stamina}. Espera a que se regenere.\")\n")
        f.write("        return\n")
        f.write("    r = random.random()\n")
        f.write("    if r < 0.30:\n")
        f.write("        tipo = \"normal\"\n")
        f.write("    elif r < 0.95:\n")
        f.write("        tipo = \"mini_boss\"\n")
        f.write("    else:\n")
        f.write("        mensajes_lore = [\n")
        f.write("            \"Sigues unas huellas que se pierden entre las rocas. No encuentras nada.\",\n")
        f.write("            \"Las pisadas te llevan a un claro vacío. Parece que la criatura se esfumó.\",\n")
        f.write("            \"Tras un rato siguiendo el rastro, desaparece en un arroyo. No hay nada.\"\n")
        f.write("        ]\n")
        f.write("        await query.edit_message_text(random.choice(mensajes_lore))\n")
        f.write("        return\n")
        f.write("    zona_data = ZONAS_INFO.get(zona_nombre)\n")
        f.write("    if not zona_data:\n")
        f.write("        await query.edit_message_text(\"Error: zona no encontrada.\")\n")
        f.write("        return\n")
        f.write("    zona_id = zona_data['zona_id']\n")
        f.write("    color = zona_data['color']\n")
        f.write("    carpeta = CARPETA_POR_COLOR[color]\n")
        f.write("    if tipo == \"normal\":\n")
        f.write("        archivo = os.path.join(carpeta, f\"monstruos_normales_zona_{zona_id}.py\")\n")
        f.write("        clave = \"MONSTRUOS_NORMALES\"\n")
        f.write("    else:\n")
        f.write("        archivo = os.path.join(carpeta, f\"monstruos_mini_boss_zona_{zona_id}.py\")\n")
        f.write("        clave = \"MONSTRUOS_MINI_BOSS\"\n")
        f.write("    if not os.path.exists(archivo):\n")
        f.write("        await query.edit_message_text(f\"No se encontraron monstruos de tipo {tipo} en esta zona.\")\n")
        f.write("        return\n")
        f.write("    spec = importlib.util.spec_from_file_location(f\"monstruos_{zona_id}\", archivo)\n")
        f.write("    modulo = importlib.util.module_from_spec(spec)\n")
        f.write("    spec.loader.exec_module(modulo)\n")
        f.write("    monstruos_dict = getattr(modulo, clave, {})\n")
        f.write("    if not monstruos_dict:\n")
        f.write("        await query.edit_message_text(\"No hay monstruos disponibles.\")\n")
        f.write("        return\n")
        f.write("    mon_id = random.choice(list(monstruos_dict.keys()))\n")
        f.write("    monstruo_data = monstruos_dict[mon_id]\n")
        f.write("    enemigo = {\n")
        f.write("        'nombre': monstruo_data['nombre'],\n")
        f.write("        'vida_max': monstruo_data['vida_max'],\n")
        f.write("        'vida_actual': monstruo_data['vida_max'],\n")
        f.write("        'daño': monstruo_data['daño'],\n")
        f.write("        'defensa': monstruo_data['defensa'],\n")
        f.write("        'xp': monstruo_data['xp'],\n")
        f.write("        'oro': monstruo_data['oro'],\n")
        f.write("        'drops': monstruo_data.get('drops', [])\n")
        f.write("    }\n")
        f.write("    tipo_combate_map = {\n")
        f.write("        'azul': 'pve_zona_azul',\n")
        f.write("        'amarilla': 'pve_zona_amarilla',\n")
        f.write("        'roja': 'pve_zona_roja',\n")
        f.write("        'negra': 'pve_zona_negra'\n")
        f.write("    }\n")
        f.write("    tipo_combate = tipo_combate_map.get(color, 'pve_zona_azul')\n")
        f.write("    await query.delete_message()\n")
        f.write("    await iniciar_combate(update, context, user_id, 0, tipo_combate, enemigo=enemigo, datos_extra={})\n\n")

        f.write("async def meditar(update: Update, context: ContextTypes.DEFAULT_TYPE, zona_nombre: str):\n")
        f.write("    query = update.callback_query\n")
        f.write("    await query.answer()\n")
        f.write("    user_id = update.effective_user.id\n")
        f.write("    if db_helper.esta_marcado(user_id):\n")
        f.write("        await query.edit_message_text(\"❌ Estás marcado. No puedes meditar hasta que pagues rescate con /pagar_rescate.\")\n")
        f.write("        return\n")
        f.write("    conn = sqlite3.connect(DB_PATH)\n")
        f.write("    c = conn.cursor()\n")
        f.write("    c.execute('SELECT cooldown_hasta FROM estado_paz WHERE user_id = ?', (user_id,))\n")
        f.write("    row = c.fetchone()\n")
        f.write("    if row and row[0]:\n")
        f.write("        cd = datetime.fromisoformat(row[0])\n")
        f.write("        if cd > datetime.now():\n")
        f.write("            seg = (cd - datetime.now()).seconds\n")
        f.write("            await query.edit_message_text(f\"⏳ Debes esperar {seg} segundos antes de volver a meditar.\")\n")
        f.write("            conn.close()\n")
        f.write("            return\n")
        f.write("    conn.close()\n")
        f.write("    ventana = _obtener_ventana_paz(user_id)\n")
        f.write("    if not ventana:\n")
        f.write("        await query.edit_message_text(\"No estás en un momento adecuado para meditar. Solo puedes hacerlo tras entrar a una zona o tras un combate.\")\n")
        f.write("        return\n")
        f.write("    tipo_ventana, hasta = ventana\n")
        f.write("    if tipo_ventana == \"entrada\":\n")
        f.write("        duracion = 30\n")
        f.write("    else:\n")
        f.write("        color_zona = ZONAS_INFO[zona_nombre]['color']\n")
        f.write("        duracion = _calcular_duracion_paz_post_combate(user_id, color_zona)\n")
        f.write("    _activar_paz(user_id, duracion)\n")
        f.write("    conn = sqlite3.connect(DB_PATH)\n")
        f.write("    c = conn.cursor()\n")
        f.write("    c.execute('UPDATE estado_paz SET ventana_activa_hasta = NULL, tipo_ventana = NULL WHERE user_id = ?', (user_id,))\n")
        f.write("    conn.commit()\n")
        f.write("    conn.close()\n")
        f.write("    await query.edit_message_text(f\"🧘‍♂️ Entras en estado de paz por {duracion} segundos. No podrás ser atacado por otros jugadores.\")\n\n")

        f.write("async def cmd_desactivar_paz(update: Update, context: ContextTypes.DEFAULT_TYPE):\n")
        f.write("    user_id = update.effective_user.id\n")
        f.write("    if _esta_en_paz(user_id):\n")
        f.write("        _desactivar_paz(user_id)\n")
        f.write("        await update.effective_message.reply_text(\"Has abandonado el estado de paz.\")\n")
        f.write("    else:\n")
        f.write("        await update.effective_message.reply_text(\"No estás en estado de paz.\")\n\n")

        f.write("async def meditar_auto(update: Update, context: ContextTypes.DEFAULT_TYPE):\n")
        f.write("    query = update.callback_query\n")
        f.write("    await query.answer()\n")
        f.write("    tipo = query.data.split(\"_\")[2]\n")
        f.write("    user_id = update.effective_user.id\n")
        f.write("    if db_helper.esta_marcado(user_id):\n")
        f.write("        await query.edit_message_text(\"❌ Estás marcado. No puedes meditar hasta que pagues rescate con /pagar_rescate.\")\n")
        f.write("        return\n")
        f.write("    jug = db_helper.obtener_jugador(user_id)\n")
        f.write("    zona_nombre = jug.get(\"zona_actual\", \"\")\n")
        f.write("    if tipo == \"entrada\":\n")
        f.write("        duracion = 30\n")
        f.write("        _activar_paz(user_id, duracion)\n")
        f.write("        await query.edit_message_text(f\"🧘‍♂️ Activas la meditación. Estarás en paz durante {duracion} segundos.\")\n")
        f.write("    elif tipo == \"post_combate\":\n")
        f.write("        color_zona = ZONAS_INFO[zona_nombre]['color']\n")
        f.write("        duracion = _calcular_duracion_paz_post_combate(user_id, color_zona)\n")
        f.write("        _activar_paz(user_id, duracion)\n")
        f.write("        await query.edit_message_text(f\"🧘‍♂️ Meditas tras el combate. Estarás en paz durante {duracion} segundos.\")\n")
        f.write("    conn = sqlite3.connect(DB_PATH)\n")
        f.write("    c = conn.cursor()\n")
        f.write("    c.execute('UPDATE estado_paz SET ventana_activa_hasta = NULL, tipo_ventana = NULL WHERE user_id = ?', (user_id,))\n")
        f.write("    conn.commit()\n")
        f.write("    conn.close()\n\n")

        f.write("async def investigar_cerrar(update: Update, context: ContextTypes.DEFAULT_TYPE):\n")
        f.write("    query = update.callback_query\n")
        f.write("    await query.answer()\n")
        f.write("    await query.edit_message_text(\"Investigación cerrada.\")\n\n")

        f.write("def registrar_handlers(app):\n")
        f.write("    app.add_handler(CommandHandler(\"investigar\", cmd_investigar))\n")
        f.write("    app.add_handler(CommandHandler(\"desactivar_paz\", cmd_desactivar_paz))\n")
        f.write("    app.add_handler(CallbackQueryHandler(seguir_huellas, pattern=\"^investigar_huellas_\"))\n")
        f.write("    app.add_handler(CallbackQueryHandler(meditar, pattern=\"^investigar_meditar_\"))\n")
        f.write("    app.add_handler(CallbackQueryHandler(meditar_auto, pattern=\"^meditar_auto_\"))\n")
        f.write("    app.add_handler(CallbackQueryHandler(investigar_cerrar, pattern=\"^investigar_cerrar$\"))\n")

    print(f"✅ Archivo generado: {archivo_salida}")

def generar_todas_investigaciones():
    print("\n🚀 GENERANDO INVESTIGACIÓN PARA TODOS LOS COLORES...\n")
    for color in CARPETA_POR_COLOR.keys():
        generar_investigacion(color)
    print("\n✨ ¡Generación completa!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generar sistema de investigación completo para una o todas las zonas.")
    parser.add_argument("--color", choices=["azul", "amarilla", "roja", "negra"], help="Color de zona")
    parser.add_argument("--output-dir", default=None, help="Carpeta de salida")
    parser.add_argument("--all", action="store_true", help="Generar investigación para todos los colores")
    args = parser.parse_args()
    if args.all or (args.color is None):
        generar_todas_investigaciones()
    else:
        generar_investigacion(args.color, args.output_dir)
#!/usr/bin/env python3
# generar_mazmorras.py
# Genera archivos de mazmorra grupal (comandos /mazmorra) por color de zona.
# Soporta --all y las reglas definidas (acceso, costes, límite pociones, modo espectador).

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
    "combate.py": "Motor de combate grupal",
    "db_helper.py": "Base de datos"
}
print("\n🔍 VERIFICANDO ARCHIVOS PARA GENERADOR DE MAZMORRAS...")
for archivo, desc in ARCHIVOS_CRITICOS.items():
    ruta = buscar_archivo(archivo, RAIZ)
    if ruta:
        print(f"✅ Encontrado: {archivo} en {ruta}")
    else:
        print(f"❌ ERROR CRÍTICO: No se encontró {archivo} ({desc})")
        sys.exit(1)
print("✅ Todos los archivos críticos están presentes.\n")

# ==================== IMPORTAR DATOS ====================
from datos_zona import ZONAS
print(f"✅ Se cargaron {len(ZONAS)} zonas desde datos_zona.py")

# ==================== MAPEO A CARPETAS REALES ====================
CARPETA_POR_COLOR = {
    "azul": "zonas azules",
    "amarilla": "zonas amarillas",
    "roja": "zonas rojas",
    "negra": "zonas negras"
}

# ==================== COSTES Y LIMITES (ajustables) ====================
# COSTES modificados para usar los valores de config_balance (como haría el script de balance)
from config_balance import MAZMORRAS_COSTES_ENTRADA
COSTES = {
    "azul": {"oro": MAZMORRAS_COSTES_ENTRADA["azul"], "stamina": 20, "eternium": 0},
    "amarilla": {"oro": MAZMORRAS_COSTES_ENTRADA["amarilla"], "stamina": 20, "eternium": 0},
    "roja": {"oro": MAZMORRAS_COSTES_ENTRADA["roja"], "stamina": 20, "eternium": 0},
    "negra": {"oro": 0, "stamina": 0, "eternium": MAZMORRAS_COSTES_ENTRADA["negra"]}
}
LIMITE_POCIONES = {
    "azul": 3,
    "amarilla": 2,
    "roja": 1,
    "negra": 0
}

# ==================== GENERACIÓN POR COLOR ====================
def generar_mazmorra(color: str, output_dir: str = None):
    if color == "azul":
        zonas_acceso = [z for z in ZONAS if z["color"] == color and z["tipo"] == "ciudad"]
        if not zonas_acceso:
            print(f"⚠️ No hay ciudades de color {color} para acceder a la mazmorra.")
            return
    else:
        zonas_acceso = [z for z in ZONAS if z["color"] == color and z["tipo"] == "salvaje"]
        if not zonas_acceso:
            print(f"⚠️ No hay zonas salvajes de color {color} para acceder a la mazmorra.")
            return
    print(f"📝 Generando mazmorra para color {color} (acceso desde {len(zonas_acceso)} zonas).")

    if output_dir is None:
        output_dir = CARPETA_POR_COLOR.get(color, f"zonas_{color}s")
    os.makedirs(output_dir, exist_ok=True)
    archivo_salida = os.path.join(output_dir, f"mazmorra_{color}.py")

    with open(archivo_salida, "w", encoding="utf-8") as f:
        f.write(f"#!/usr/bin/env python3\n")
        f.write(f"# mazmorra_{color}.py\n")
        f.write(f"# Generado automáticamente por generar_mazmorras.py para color {color}\n")
        f.write("# Comando: /mazmorra (acceso grupal)\n\n")

        f.write("import random\n")
        f.write("import sqlite3\n")
        f.write("import os\n")
        f.write("import importlib.util\n")
        f.write("import json\n")
        f.write("from datetime import datetime, timedelta\n")
        f.write("from typing import Optional, List, Dict, Tuple\n\n")
        f.write("from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup\n")
        f.write("from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler\n\n")
        f.write("import db_helper\n")
        f.write("import economia\n")
        f.write("import config_balance\n")
        f.write("from combate import iniciar_combate_grupal_mazmorra, COMBATE_MAZMORRA\n\n")
        f.write("DB_PATH = \"aethelgard.db\"\n\n")

        # Constantes del color
        f.write(f"COLOR = {repr(color)}\n")
        f.write(f"COSTO_ORO = {COSTES[color]['oro']}\n")
        f.write(f"COSTO_STAMINA = {COSTES[color]['stamina']}\n")
        f.write(f"COSTO_ETERNIUM = {COSTES[color]['eternium']}\n")
        f.write(f"LIMITE_POCIONES = {LIMITE_POCIONES[color]}\n")
        if color == "azul":
            f.write("CLASES_ROTACION = ['vanguardista', 'acechante', 'tejehechizos', 'maestro_caza']\n")
            f.write("def _clase_del_dia() -> str:\n")
            f.write("    dias = (datetime.now().day - 1) % 4\n")
            f.write("    return CLASES_ROTACION[dias]\n")
        else:
            f.write("def _clase_del_dia() -> str:\n")
            f.write("    return None\n\n")

        # Tablas de mazmorras y espectadores
        f.write("def _init_mazmorra_db():\n")
        f.write("    conn = sqlite3.connect(DB_PATH)\n")
        f.write("    c = conn.cursor()\n")
        f.write("    c.execute('''CREATE TABLE IF NOT EXISTS mazmorras_activas (\n")
        f.write("        mazmorra_id TEXT PRIMARY KEY,\n")
        f.write("        lider_id INTEGER,\n")
        f.write("        zona_nombre TEXT,\n")
        f.write("        color TEXT,\n")
        f.write("        dificultad TEXT,\n")
        f.write("        sala_actual INTEGER DEFAULT 1,\n")
        f.write("        monstruos JSON,\n")
        f.write("        jugadores JSON,\n")
        f.write("        estado TEXT DEFAULT 'formando',\n")
        f.write("        fecha_creacion TIMESTAMP\n")
        f.write("    )''')\n")
        f.write("    c.execute('''CREATE TABLE IF NOT EXISTS espectadores (\n")
        f.write("        mazmorra_id TEXT,\n")
        f.write("        espectador_id INTEGER,\n")
        f.write("        PRIMARY KEY (mazmorra_id, espectador_id)\n")
        f.write("    )''')\n")
        f.write("    conn.commit()\n")
        f.write("    conn.close()\n")
        f.write("_init_mazmorra_db()\n\n")

        f.write("def _puede_entrar(user_id: int) -> Tuple[bool, str]:\n")
        f.write("    # Verificar límite diario\n")
        f.write("    if not db_helper.comprobar_limite_mazmorra(user_id, COLOR):\n")
        f.write("        return False, f\"Ya has usado tus {config_balance.MAZMORRAS_LIMITE_DIARIO} entradas diarias para mazmorras {COLOR}. Vuelve mañana.\"\n")
        f.write("    if db_helper.esta_marcado(user_id):\n")
        f.write("        return False, \"❌ Estás marcado. No puedes entrar a la mazmorra hasta que pagues rescate con /pagar_rescate.\"\n")
        f.write("    jug = db_helper.obtener_jugador(user_id)\n")
        f.write("    if not jug:\n")
        f.write("        return False, \"No estás registrado.\"\n")
        if color == "azul":
            f.write("    clase_jug = jug['clase']\n")
            f.write("    clase_requerida = _clase_del_dia()\n")
            f.write("    if clase_jug != clase_requerida:\n")
            f.write("        return False, f\"Hoy solo pueden entrar los {clase_requerida}. Tu clase es {clase_jug}.\"\n")
        f.write("    if COSTO_ORO > 0 and jug.get('oro', 0) < COSTO_ORO:\n")
        f.write("        return False, f\"Necesitas {COSTO_ORO} de oro. Tienes {jug.get('oro', 0)}.\"\n")
        f.write("    if COSTO_ETERNIUM > 0 and jug.get('eternium', 0) < COSTO_ETERNIUM:\n")
        f.write("        return False, f\"Necesitas {COSTO_ETERNIUM} de eternium. Tienes {jug.get('eternium', 0)}.\"\n")
        f.write("    if COSTO_STAMINA > 0 and not db_helper.gastar_stamina(user_id, COSTO_STAMINA):\n")
        f.write("        return False, f\"No tienes suficiente stamina. Necesitas {COSTO_STAMINA}.\"\n")
        f.write("    return True, \"OK\"\n\n")

        f.write("def _cobrar_entrada(user_id: int):\n")
        f.write("    if COSTO_ORO > 0:\n")
        f.write("        economia.modificar_saldo(user_id, 'oro', -COSTO_ORO, f'Entrada mazmorra {COLOR}')\n")
        f.write("    if COSTO_ETERNIUM > 0:\n")
        f.write("        economia.modificar_saldo(user_id, 'eternium', -COSTO_ETERNIUM, f'Entrada mazmorra {COLOR}')\n")
        f.write("    if COSTO_STAMINA > 0:\n")
        f.write("        db_helper.gastar_stamina(user_id, COSTO_STAMINA)  # ya se gastó en _puede_entrar, pero se confirma\n")
        f.write("    db_helper.registrar_entrada_mazmorra(user_id, COLOR)\n\n")

        f.write("async def cmd_mazmorra(update: Update, context: ContextTypes.DEFAULT_TYPE):\n")
        f.write("    user_id = update.effective_user.id\n")
        f.write("    if db_helper.esta_marcado(user_id):\n")
        f.write("        await update.effective_message.reply_text(\"❌ Estás marcado. No puedes usar /mazmorra hasta que pagues rescate con /pagar_rescate.\")\n")
        f.write("        return\n")
        f.write("    jug = db_helper.obtener_jugador(user_id)\n")
        f.write("    if not jug:\n")
        f.write("        await update.effective_message.reply_text(\"No estás registrado.\")\n")
        f.write("        return\n")
        f.write("    zona_nombre = jug.get('zona_actual', '')\n")
        f.write("    from datos_zona import ZONAS\n")
        f.write("    zona_info = next((z for z in ZONAS if z['nombre'] == zona_nombre), None)\n")
        f.write("    if not zona_info or zona_info['color'] != COLOR:\n")
        f.write("        await update.effective_message.reply_text(f\"No estás en una zona de color {COLOR} adecuada para esta mazmorra.\")\n")
        f.write("        return\n")
        if color == "azul":
            f.write("    if zona_info['tipo'] != 'ciudad':\n")
            f.write("        await update.effective_message.reply_text(\"La mazmorra azul solo se puede acceder desde una ciudad.\")\n")
            f.write("        return\n")
        f.write("    ok, msg = _puede_entrar(user_id)\n")
        f.write("    if not ok:\n")
        f.write("        await update.effective_message.reply_text(f\"❌ {msg}\")\n")
        f.write("        return\n")
        f.write("    _cobrar_entrada(user_id)\n")
        f.write("    keyboard = [\n")
        f.write("        [InlineKeyboardButton(\"Formar grupo\", callback_data=f\"mazmorra_formar_{COLOR}\")],\n")
        f.write("        [InlineKeyboardButton(\"Unirme a grupo\", callback_data=f\"mazmorra_unirse_{COLOR}\")],\n")
        f.write("        [InlineKeyboardButton(\"Espectar\", callback_data=f\"mazmorra_espectar_{COLOR}\")]\n")
        f.write("    ]\n")
        f.write("    await update.effective_message.reply_text(f\"🏰 **Mazmorra {COLOR.capitalize()}**\\n\\n¿Qué deseas hacer?\", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=\"Markdown\")\n\n")

        f.write("async def _formar_grupo(update: Update, context: ContextTypes.DEFAULT_TYPE):\n")
        f.write("    query = update.callback_query\n")
        f.write("    await query.answer()\n")
        f.write("    user_id = update.effective_user.id\n")
        f.write("    if db_helper.esta_marcado(user_id):\n")
        f.write("        await query.edit_message_text(\"❌ Estás marcado. No puedes formar un grupo para la mazmorra hasta que pagues rescate con /pagar_rescate.\")\n")
        f.write("        return\n")
        f.write("    conn = sqlite3.connect(DB_PATH)\n")
        f.write("    c = conn.cursor()\n")
        f.write("    c.execute('SELECT mazmorra_id FROM mazmorras_activas WHERE lider_id = ? AND estado IN (\"formando\", \"en_curso\")', (user_id,))\n")
        f.write("    if c.fetchone():\n")
        f.write("        await query.edit_message_text(\"Ya tienes una mazmorra activa. Termínala o abandónala antes de crear otra.\")\n")
        f.write("        conn.close()\n")
        f.write("        return\n")
        f.write("    mazmorra_id = f\"{COLOR}_{user_id}_{datetime.now().timestamp()}\"\n")
        f.write("    jug = db_helper.obtener_jugador(user_id)\n")
        f.write("    zona_nombre = jug.get('zona_actual', '')\n")
        f.write("    c.execute('''INSERT INTO mazmorras_activas (mazmorra_id, lider_id, zona_nombre, color, estado, jugadores, fecha_creacion)\n")
        f.write("                 VALUES (?, ?, ?, ?, 'formando', ?, ?)''',\n")
        f.write("                 (mazmorra_id, user_id, zona_nombre, COLOR, json.dumps([user_id]), datetime.now().isoformat()))\n")
        f.write("    conn.commit()\n")
        f.write("    conn.close()\n")
        f.write("    await query.edit_message_text(f\"Grupo formado. ID: `{mazmorra_id}`\\nUsa /unirme_mazmorra {mazmorra_id} para unirte.\", parse_mode=\"Markdown\")\n\n")

        f.write("async def _unirse_grupo(update: Update, context: ContextTypes.DEFAULT_TYPE):\n")
        f.write("    query = update.callback_query\n")
        f.write("    await query.answer()\n")
        f.write("    await query.edit_message_text(\"Envía el ID de la mazmorra a la que quieres unirte usando `/unirme_mazmorra <id>`\")\n\n")

        f.write("async def _espectar(update: Update, context: ContextTypes.DEFAULT_TYPE):\n")
        f.write("    query = update.callback_query\n")
        f.write("    await query.answer()\n")
        f.write("    await query.edit_message_text(\"Envía el ID de la mazmorra que quieres espectar usando `/espectar <id>`\")\n\n")

        f.write("async def cmd_unirme_mazmorra(update: Update, context: ContextTypes.DEFAULT_TYPE):\n")
        f.write("    if not context.args:\n")
        f.write("        await update.effective_message.reply_text(\"Uso: `/unirme_mazmorra <ID>`\")\n")
        f.write("        return\n")
        f.write("    mazmorra_id = context.args[0]\n")
        f.write("    user_id = update.effective_user.id\n")
        f.write("    if db_helper.esta_marcado(user_id):\n")
        f.write("        await update.effective_message.reply_text(\"❌ Estás marcado. No puedes unirte a una mazmorra hasta que pagues rescate con /pagar_rescate.\")\n")
        f.write("        return\n")
        f.write("    conn = sqlite3.connect(DB_PATH)\n")
        f.write("    c = conn.cursor()\n")
        f.write("    c.execute('SELECT jugadores, lider_id, estado FROM mazmorras_activas WHERE mazmorra_id = ?', (mazmorra_id,))\n")
        f.write("    row = c.fetchone()\n")
        f.write("    if not row:\n")
        f.write("        await update.effective_message.reply_text(\"Mazmorra no encontrada.\")\n")
        f.write("        conn.close()\n")
        f.write("        return\n")
        f.write("    jugadores = json.loads(row[0])\n")
        f.write("    lider = row[1]\n")
        f.write("    estado = row[2]\n")
        f.write("    if estado != 'formando':\n")
        f.write("        await update.effective_message.reply_text(\"La mazmorra ya comenzó o terminó.\")\n")
        f.write("        conn.close()\n")
        f.write("        return\n")
        f.write("    if user_id in jugadores:\n")
        f.write("        await update.effective_message.reply_text(\"Ya estás en este grupo.\")\n")
        f.write("        conn.close()\n")
        f.write("        return\n")
        f.write("    if len(jugadores) >= 5:\n")
        f.write("        await update.effective_message.reply_text(\"El grupo está completo (máximo 5).\")\n")
        f.write("        conn.close()\n")
        f.write("        return\n")
        f.write("    ok, msg = _puede_entrar(user_id)\n")
        f.write("    if not ok:\n")
        f.write("        await update.effective_message.reply_text(f\"❌ {msg}\")\n")
        f.write("        conn.close()\n")
        f.write("        return\n")
        f.write("    _cobrar_entrada(user_id)\n")
        f.write("    jugadores.append(user_id)\n")
        f.write("    c.execute('UPDATE mazmorras_activas SET jugadores = ? WHERE mazmorra_id = ?', (json.dumps(jugadores), mazmorra_id))\n")
        f.write("    conn.commit()\n")
        f.write("    conn.close()\n")
        f.write("    await update.effective_message.reply_text(f\"Te has unido a la mazmorra {mazmorra_id}. Espera a que el líder la inicie con /iniciar_mazmorra {mazmorra_id}\")\n\n")

        f.write("async def cmd_iniciar_mazmorra(update: Update, context: ContextTypes.DEFAULT_TYPE):\n")
        f.write("    if not context.args:\n")
        f.write("        await update.effective_message.reply_text(\"Uso: `/iniciar_mazmorra <ID>`\")\n")
        f.write("        return\n")
        f.write("    mazmorra_id = context.args[0]\n")
        f.write("    user_id = update.effective_user.id\n")
        f.write("    if db_helper.esta_marcado(user_id):\n")
        f.write("        await update.effective_message.reply_text(\"❌ Estás marcado. No puedes iniciar la mazmorra hasta que pagues rescate con /pagar_rescate.\")\n")
        f.write("        return\n")
        f.write("    conn = sqlite3.connect(DB_PATH)\n")
        f.write("    c = conn.cursor()\n")
        f.write("    c.execute('SELECT lider_id, jugadores, zona_nombre, estado FROM mazmorras_activas WHERE mazmorra_id = ?', (mazmorra_id,))\n")
        f.write("    row = c.fetchone()\n")
        f.write("    if not row or row[0] != user_id:\n")
        f.write("        await update.effective_message.reply_text(\"No eres el líder de esta mazmorra.\")\n")
        f.write("        conn.close()\n")
        f.write("        return\n")
        f.write("    if row[3] != 'formando':\n")
        f.write("        await update.effective_message.reply_text(\"La mazmorra ya comenzó o terminó.\")\n")
        f.write("        conn.close()\n")
        f.write("        return\n")
        f.write("    jugadores = json.loads(row[1])\n")
        f.write("    zona_nombre = row[2]\n")
        f.write("    from datos_zona import ZONAS\n")
        f.write("    zona_info = next((z for z in ZONAS if z['nombre'] == zona_nombre), None)\n")
        f.write("    if not zona_info:\n")
        f.write("        await update.effective_message.reply_text(\"Error: zona no encontrada.\")\n")
        f.write("        conn.close()\n")
        f.write("        return\n")
        f.write("    zona_id = zona_info['id']\n")
        f.write("    carpeta = CARPETA_POR_COLOR[COLOR]\n")
        f.write("    archivo_mons = os.path.join(carpeta, f'monstruos_mazmorras_zona_{zona_id}_normal.py')\n")
        f.write("    if not os.path.exists(archivo_mons):\n")
        f.write("        await update.effective_message.reply_text(f\"No se encontraron monstruos para la mazmorra normal de esta zona.\")\n")
        f.write("        conn.close()\n")
        f.write("        return\n")
        f.write("    spec = importlib.util.spec_from_file_location(f'mazmorra_mons_{zona_id}', archivo_mons)\n")
        f.write("    modulo = importlib.util.module_from_spec(spec)\n")
        f.write("    spec.loader.exec_module(modulo)\n")
        f.write("    monstruos_dict = getattr(modulo, 'MONSTRUOS_MAZMORRAS_NORMAL', {})\n")
        f.write("    if not monstruos_dict:\n")
        f.write("        await update.effective_message.reply_text(\"El archivo de monstruos no contiene la variable MONSTRUOS_MAZMORRAS_NORMAL.\")\n")
        f.write("        conn.close()\n")
        f.write("        return\n")
        f.write("    lista_monstruos = list(monstruos_dict.values())\n")
        f.write("    c.execute('UPDATE mazmorras_activas SET monstruos = ?, estado = \"en_curso\", sala_actual = 1 WHERE mazmorra_id = ?', (json.dumps(lista_monstruos), mazmorra_id))\n")
        f.write("    conn.commit()\n")
        f.write("    conn.close()\n")
        f.write("    await iniciar_combate_grupal_mazmorra(update, context, mazmorra_id, jugadores, lista_monstruos[0])\n\n")

        f.write("async def cmd_espectar(update: Update, context: ContextTypes.DEFAULT_TYPE):\n")
        f.write("    if not context.args:\n")
        f.write("        await update.effective_message.reply_text(\"Uso: `/espectar <ID_mazmorra>`\")\n")
        f.write("        return\n")
        f.write("    mazmorra_id = context.args[0]\n")
        f.write("    user_id = update.effective_user.id\n")
        f.write("    if db_helper.esta_marcado(user_id):\n")
        f.write("        await update.effective_message.reply_text(\"❌ Estás marcado. No puedes espectar una mazmorra hasta que pagues rescate con /pagar_rescate.\")\n")
        f.write("        return\n")
        f.write("    conn = sqlite3.connect(DB_PATH)\n")
        f.write("    c = conn.cursor()\n")
        f.write("    c.execute('SELECT estado FROM mazmorras_activas WHERE mazmorra_id = ?', (mazmorra_id,))\n")
        f.write("    row = c.fetchone()\n")
        f.write("    if not row or row[0] != 'en_curso':\n")
        f.write("        await update.effective_message.reply_text(\"No hay ninguna mazmorra activa con ese ID.\")\n")
        f.write("        conn.close()\n")
        f.write("        return\n")
        f.write("    c.execute('INSERT OR IGNORE INTO espectadores (mazmorra_id, espectador_id) VALUES (?, ?)', (mazmorra_id, user_id))\n")
        f.write("    conn.commit()\n")
        f.write("    conn.close()\n")
        f.write("    await update.effective_message.reply_text(f\"Ahora eres espectador de la mazmorra {mazmorra_id}. Recibirás actualizaciones del combate.\")\n\n")

        f.write("async def cmd_abandonar_mazmorra(update: Update, context: ContextTypes.DEFAULT_TYPE):\n")
        f.write("    user_id = update.effective_user.id\n")
        f.write("    conn = sqlite3.connect(DB_PATH)\n")
        f.write("    c = conn.cursor()\n")
        f.write("    # Buscar si el usuario es líder o miembro de una mazmorra en estado 'formando'\n")
        f.write("    c.execute('SELECT mazmorra_id, lider_id, jugadores FROM mazmorras_activas WHERE (lider_id = ? OR jugadores LIKE ?) AND estado = \"formando\"', (user_id, f'%\"{user_id}\"%'))\n")
        f.write("    row = c.fetchone()\n")
        f.write("    if not row:\n")
        f.write("        await update.effective_message.reply_text(\"No perteneces a ninguna mazmorra en formación.\")\n")
        f.write("        conn.close()\n")
        f.write("        return\n")
        f.write("    mazmorra_id, lider_id, jugadores_json = row\n")
        f.write("    jugadores = json.loads(jugadores_json)\n")
        f.write("    if lider_id == user_id:\n")
        f.write("        # El líder abandona: eliminar la mazmorra\n")
        f.write("        c.execute('DELETE FROM mazmorras_activas WHERE mazmorra_id = ?', (mazmorra_id,))\n")
        f.write("        await update.effective_message.reply_text(\"Has cancelado la mazmorra. El grupo se disuelve.\")\n")
        f.write("    else:\n")
        f.write("        # Un miembro abandona\n")
        f.write("        jugadores.remove(user_id)\n")
        f.write("        if jugadores:\n")
        f.write("            c.execute('UPDATE mazmorras_activas SET jugadores = ? WHERE mazmorra_id = ?', (json.dumps(jugadores), mazmorra_id))\n")
        f.write("            await update.effective_message.reply_text(\"Has abandonado la mazmorra.\")\n")
        f.write("        else:\n")
        f.write("            c.execute('DELETE FROM mazmorras_activas WHERE mazmorra_id = ?', (mazmorra_id,))\n")
        f.write("            await update.effective_message.reply_text(\"Has abandonado la mazmorra. Al no quedar miembros, se cancela.\")\n")
        f.write("    conn.commit()\n")
        f.write("    conn.close()\n\n")

        f.write("def registrar_handlers(app):\n")
        f.write("    app.add_handler(CommandHandler(\"mazmorra\", cmd_mazmorra))\n")
        f.write("    app.add_handler(CommandHandler(\"unirme_mazmorra\", cmd_unirme_mazmorra))\n")
        f.write("    app.add_handler(CommandHandler(\"iniciar_mazmorra\", cmd_iniciar_mazmorra))\n")
        f.write("    app.add_handler(CommandHandler(\"espectar\", cmd_espectar))\n")
        f.write("    app.add_handler(CommandHandler(\"abandonar_mazmorra\", cmd_abandonar_mazmorra))\n")
        f.write("    app.add_handler(CallbackQueryHandler(_formar_grupo, pattern=\"^mazmorra_formar_\"))\n")
        f.write("    app.add_handler(CallbackQueryHandler(_unirse_grupo, pattern=\"^mazmorra_unirse_\"))\n")
        f.write("    app.add_handler(CallbackQueryHandler(_espectar, pattern=\"^mazmorra_espectar_\"))\n")

    print(f"✅ Archivo generado: {archivo_salida}")

def generar_todas_mazmorras():
    print("\n🚀 GENERANDO MAZMORRAS PARA TODOS LOS COLORES...\n")
    for color in CARPETA_POR_COLOR.keys():
        generar_mazmorra(color)
    print("\n✨ ¡Generación completa!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generar sistema de mazmorras grupal por color.")
    parser.add_argument("--color", choices=["azul", "amarilla", "roja", "negra"], help="Color de zona")
    parser.add_argument("--all", action="store_true", help="Generar para todos los colores")
    args = parser.parse_args()
    if args.all or (args.color is None):
        generar_todas_mazmorras()
    else:
        generar_mazmorra(args.color)
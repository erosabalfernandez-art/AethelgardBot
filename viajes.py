#!/usr/bin/env python3
# viajes.py - Sistema completo de viajes con monturas, peajes, cooldowns y más.

import asyncio
import sqlite3
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler

import db_helper
import superadmin as sa

# Referencia global al bot para usarla en tasks asíncronos donde context puede
# ser None (viajes restaurados tras reinicio) o stale (context de CallbackQuery).
_bot_ref = None


FACCION_NOMBRES = {1: "Alianza", 2: "Imperio", 3: "Sindicato"}

def _obtener_destinos() -> List[Dict]:
    from datos_zona import ZONAS
    destinos = []
    for zona in ZONAS:
        fid = zona["faccion_id"]
        destinos.append({
            "id": zona["id"],
            "nombre": zona["nombre"],
            "color": zona["color"],
            "tipo": zona["tipo"],
            "faccion_id": fid,
            "faccion_nombre": FACCION_NOMBRES.get(fid, "???"),
            "nivel_requerido": zona.get("nivel_requerido", 1),
            "orden": zona.get("orden", 999),
        })
    return destinos

def _obtener_destino(destino_id: int) -> Optional[Dict]:
    from datos_zona import ZONAS
    for zona in ZONAS:
        if zona["id"] == destino_id:
            fid = zona["faccion_id"]
            return {
                "id": zona["id"],
                "nombre": zona["nombre"],
                "color": zona["color"],
                "tipo": zona["tipo"],
                "faccion_id": fid,
                "faccion_nombre": FACCION_NOMBRES.get(fid, "???"),
                "nivel_requerido": zona.get("nivel_requerido", 1),
            }
    return None

def _obtener_destinos_por_faccion(faccion_id: int) -> List[Dict]:
    return [d for d in _obtener_destinos() if d["faccion_id"] == faccion_id]

import economia
from monturas import MONTURAS    # tu catálogo de monturas

# ==================== CONSTANTES ====================
DB_PATH = "aethelgard.db"

# Mapa de colores a índice y viceversa
COLOR_INDICE = {"azul": 1, "amarilla": 2, "roja": 3, "negra": 4}
INDICE_COLOR = {v: k for k, v in COLOR_INDICE.items()}

SEGUNDOS_POR_SALTO = 30           # base: 30s por salto de color
def _cooldown_zona(color: str) -> int:
    """Lee el cooldown de salida de zona desde la BD (configurable en /panel_zonas)."""
    defectos = {"roja": 600, "negra": 1800, "amarilla": 0, "azul": 0}
    defecto = defectos.get(color, 0)
    try:
        return max(0, int(db_helper.obtener_config(f"cooldown_zona_{color}", str(defecto))))
    except Exception:
        return defecto

COOLDOWN_ROJA  = 10 * 60   # legacy — se usa _cooldown_zona() en runtime
COOLDOWN_NEGRA = 30 * 60   # legacy — se usa _cooldown_zona() en runtime

NIVEL_DESBLOQUEO = {1: 1, 5: 2, 10: 3, 15: 4}   # nivel mínimo para cada color máximo

# Precios de viaje
PRECIO_VUELO_RAPIDO = 50          # Eternium para vuelo instantáneo entre ciudades
PRECIO_VIAJE_CIUDAD = 10          # Eternium para viaje normal entre ciudades

# ==================== INICIALIZACIÓN DE BD ====================
def _init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Tabla de facciones
        # Tabla de destinos (zonas)
        # Columnas adicionales en jugadores
    try:
        c.execute('ALTER TABLE jugadores ADD COLUMN zona_actual_id INTEGER')
        c.execute('ALTER TABLE jugadores ADD COLUMN viaje_hasta TIMESTAMP')
        c.execute('ALTER TABLE jugadores ADD COLUMN viaje_destino_id INTEGER')
        c.execute('ALTER TABLE jugadores ADD COLUMN red_enter_time TIMESTAMP')
        c.execute('ALTER TABLE jugadores ADD COLUMN black_enter_time TIMESTAMP')
        c.execute('ALTER TABLE jugadores ADD COLUMN faccion_id INTEGER DEFAULT 1')
    except sqlite3.OperationalError:
        pass

    # Migración: poblar faccion_id basado en faccion texto
    try:
        c.execute("""
            UPDATE jugadores SET faccion_id =
                CASE faccion
                    WHEN 'Alianza'   THEN 1
                    WHEN 'Imperio'   THEN 2
                    WHEN 'Sindicato' THEN 3
                    ELSE 1
                END
            WHERE faccion_id IS NULL OR faccion_id = 0 OR faccion_id = 1
        """)
    except Exception:
        pass

    # Migración: corregir zona_actual incorrecta ('Ciudadela Blanca' o nula)
    try:
        c.execute("""
            UPDATE jugadores SET
                zona_actual = CASE faccion
                    WHEN 'Alianza'   THEN 'Ciudadela Alianza'
                    WHEN 'Imperio'   THEN 'Ciudadela Imperio'
                    WHEN 'Sindicato' THEN 'Ciudadela Sindicato'
                    ELSE 'Ciudadela Alianza'
                END,
                zona_actual_id = CASE faccion
                    WHEN 'Alianza'   THEN 1
                    WHEN 'Imperio'   THEN 12
                    WHEN 'Sindicato' THEN 23
                    ELSE 1
                END,
                ubicacion = 'ciudad'
            WHERE zona_actual = 'Ciudadela Blanca'
               OR zona_actual IS NULL
               OR zona_actual_id IS NULL
        """)
    except Exception:
        pass

    # Tabla de monturas equipadas (solo una activa a la vez)
    c.execute('''CREATE TABLE IF NOT EXISTS monturas_equipadas (
        user_id INTEGER PRIMARY KEY,
        montura_id TEXT,
        velocidad INTEGER,
        expira TIMESTAMP,   -- NULL = permanente
        FOREIGN KEY(user_id) REFERENCES jugadores(user_id)
    )''')

    # Tabla de inventario de monturas (las que posee el jugador)
    c.execute('''CREATE TABLE IF NOT EXISTS inventario_monturas (
        user_id INTEGER,
        montura_id TEXT,
        cantidad INTEGER DEFAULT 1,
        adquirida TIMESTAMP,
        expira TIMESTAMP,   -- NULL = permanente, fecha = alquiler expira
        PRIMARY KEY (user_id, montura_id)
    )''')

    conn.commit()
    conn.close()

_init_db()

# ==================== FUNCIONES AUXILIARES DE DESTINOS ====================



def _actualizar_zona_jugador(user_id: int, destino_id: int):
    destino = _obtener_destino(destino_id)
    if not destino:
        return
    ubicacion = "ciudad" if destino.get("tipo") == "ciudad" else "salvaje"
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('UPDATE jugadores SET zona_actual_id = ?, zona_actual = ?, ubicacion = ? WHERE user_id = ?',
              (destino_id, destino["nombre"], ubicacion, user_id))
    conn.commit()
    conn.close()
    # Abrir ventana de meditación al entrar a zona salvaje
    if ubicacion == "salvaje":
        try:
            import sistema_paz as _sp
            _sp.abrir_ventana_entrada(user_id)
        except Exception:
            pass

def _color_permitido_por_nivel(nivel: int, color: str) -> bool:
    max_indice = 1
    for min_nivel, idx in sorted(NIVEL_DESBLOQUEO.items()):
        if nivel >= min_nivel:
            max_indice = idx
        else:
            break
    return COLOR_INDICE[color] <= max_indice

def _get_tiempo_cfg(clave: str, defecto: int) -> int:
    """Lee un tiempo de viaje configurable desde la BD."""
    try:
        v = db_helper.obtener_config(clave, str(defecto))
        return max(0, int(v))
    except Exception:
        return defecto

def _calcular_tiempo_viaje(color_origen: str, color_destino: str, velocidad_montura: int = 0,
                           faccion_origen: int = 0, faccion_destino: int = 0) -> int:
    """Tiempos de viaje configurables desde el panel admin.
    Claves en config_bot:
      viaje_t_dif1  → colores con 1 nivel de diferencia (defecto 30s)
      viaje_t_dif2  → colores con 2 niveles de diferencia (defecto 60s)
      viaje_t_dif3  → colores con 3 niveles de diferencia (defecto 120s)
      viaje_t_cross → mismo color, distinta facción (defecto 150s)
    azul→azul misma facción = siempre 0 (instantáneo)
    """
    misma_faccion = (not faccion_origen or not faccion_destino or faccion_origen == faccion_destino)
    if color_origen == color_destino:
        if misma_faccion:
            return 0
        base = _get_tiempo_cfg("viaje_t_cross", 150)
    else:
        dif = abs(COLOR_INDICE.get(color_origen, 1) - COLOR_INDICE.get(color_destino, 1))
        if dif == 1:   base = _get_tiempo_cfg("viaje_t_dif1", 30)
        elif dif == 2: base = _get_tiempo_cfg("viaje_t_dif2", 60)
        else:          base = _get_tiempo_cfg("viaje_t_dif3", 120)
    if velocidad_montura >= 100:
        return 0
    if velocidad_montura > 0:
        base = base * (100 - velocidad_montura) // 100
    return max(1, base)

def _emoji_por_color(color: str) -> str:
    return {"azul": "🟦", "amarilla": "🟨", "roja": "🟥", "negra": "⬛"}.get(color, "🟩")

_COLORES_EMOJI_MAPA = {"azul": "🔵", "amarilla": "🟡", "roja": "🔴", "negra": "⬛"}

def _emoji_zona(zona: dict) -> str:
    """Emoji temático por nombre/tipo de zona, igual que el mapa global."""
    nombre = zona.get("nombre", "").lower()
    tipo   = zona.get("tipo", "salvaje")
    if tipo == "ciudad":
        if "alianza"   in nombre: return "🏰"
        if "imperio"   in nombre: return "🏛️"
        if "sindicato" in nombre: return "🏙️"
        return "🏙️"
    if "bosque"   in nombre: return "🌳"
    if "desierto" in nombre: return "🏜️"
    if "ruinas"   in nombre: return "🏚️"
    if "oasis"    in nombre: return "🌴"
    if "magm"     in nombre: return "🌋"
    if "dragón"   in nombre or "dragon" in nombre: return "🐉"
    if "forja"    in nombre: return "⚙️"
    if "abismo"   in nombre: return "🕳️"
    if "costa"    in nombre: return "🌊"
    if "nexo"     in nombre: return "🌀"
    color = zona.get("color", "azul")
    return _COLORES_EMOJI_MAPA.get(color, "🔵")

# ==================== FUNCIONES DE MONTURAS ====================
def _obtener_montura_activa(user_id: int) -> Optional[Dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT montura_id, velocidad, expira FROM monturas_equipadas WHERE user_id = ?', (user_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    montura = dict(row)
    if montura["expira"] and datetime.now() > datetime.fromisoformat(montura["expira"]):
        # Expirada, eliminarla
        conn2 = sqlite3.connect(DB_PATH)
        c2 = conn2.cursor()
        c2.execute('DELETE FROM monturas_equipadas WHERE user_id = ?', (user_id,))
        conn2.commit()
        conn2.close()
        return None
    return montura

def _tiene_montura_en_inventario(user_id: int, montura_id: str) -> bool:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT cantidad FROM inventario_monturas WHERE user_id = ? AND montura_id = ? AND (expira IS NULL OR expira > ?)',
              (user_id, montura_id, datetime.now().isoformat()))
    row = c.fetchone()
    conn.close()
    return row is not None and row[0] > 0

def _agregar_montura_inventario(user_id: int, montura_id: str, expira: datetime = None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT INTO inventario_monturas (user_id, montura_id, cantidad, adquirida, expira)
                 VALUES (?, ?, 1, ?, ?)
                 ON CONFLICT(user_id, montura_id) DO UPDATE SET cantidad = cantidad + 1''',
              (user_id, montura_id, datetime.now().isoformat(), expira.isoformat() if expira else None))
    conn.commit()
    conn.close()

def _remover_montura_inventario(user_id: int, montura_id: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('UPDATE inventario_monturas SET cantidad = cantidad - 1 WHERE user_id = ? AND montura_id = ? AND cantidad > 0',
              (user_id, montura_id))
    c.execute('DELETE FROM inventario_monturas WHERE user_id = ? AND montura_id = ? AND cantidad <= 0',
              (user_id, montura_id))
    conn.commit()
    conn.close()

def _equipar_montura(user_id: int, montura_id: str):
    """Equipa una montura que el jugador posea (permanente o alquilada no expirada)."""
    # Verificar que la tiene en inventario y no expirada
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT expira FROM inventario_monturas WHERE user_id = ? AND montura_id = ? AND cantidad > 0',
              (user_id, montura_id))
    row = c.fetchone()
    if not row:
        conn.close()
        return False
    expira = row[0]
    if expira and datetime.now() > datetime.fromisoformat(expira):
        conn.close()
        return False
    # Obtener velocidad del catálogo
    datos = MONTURAS.get(montura_id)
    if not datos:
        conn.close()
        return False
    velocidad = datos.get("velocidad", 0)
    # Insertar/actualizar equipada
    c.execute('INSERT OR REPLACE INTO monturas_equipadas (user_id, montura_id, velocidad, expira) VALUES (?, ?, ?, ?)',
              (user_id, montura_id, velocidad, expira))
    conn.commit()
    conn.close()
    return True

def _desmontar(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('DELETE FROM monturas_equipadas WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

# ==================== COOLDOWN ZONAS ROJA/NEGRA ====================
def _actualizar_cooldown_entrada(user_id: int, color: str):
    ahora = datetime.now()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if color == "roja":
        c.execute('UPDATE jugadores SET red_enter_time = ? WHERE user_id = ?', (ahora.isoformat(), user_id))
    elif color == "negra":
        c.execute('UPDATE jugadores SET black_enter_time = ? WHERE user_id = ?', (ahora.isoformat(), user_id))
    conn.commit()
    conn.close()

def _puede_cambiar_color(user_id: int, color_actual: str, color_destino: str) -> Tuple[bool, int]:
    if color_actual == color_destino:
        return True, 0
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if color_actual == "roja":
        c.execute('SELECT red_enter_time FROM jugadores WHERE user_id = ?', (user_id,))
        row = c.fetchone()
        if row and row[0]:
            entrada = datetime.fromisoformat(row[0])
            fin = entrada + timedelta(seconds=_cooldown_zona("roja"))
            ahora = datetime.now()
            if ahora < fin:
                restante = int((fin - ahora).total_seconds())
                conn.close()
                return False, restante
    elif color_actual == "negra":
        c.execute('SELECT black_enter_time FROM jugadores WHERE user_id = ?', (user_id,))
        row = c.fetchone()
        if row and row[0]:
            entrada = datetime.fromisoformat(row[0])
            fin = entrada + timedelta(seconds=_cooldown_zona("negra"))
            ahora = datetime.now()
            if ahora < fin:
                restante = int((fin - ahora).total_seconds())
                conn.close()
                return False, restante
    conn.close()
    return True, 0

# ==================== VIAJES ASÍNCRONOS ====================
_viajes_tasks = {}

async def _iniciar_viaje(user_id: int, destino_id: int, tiempo_segundos: int, context: ContextTypes.DEFAULT_TYPE):
    destino = _obtener_destino(destino_id)
    if not destino:
        return
    hasta = datetime.now() + timedelta(seconds=tiempo_segundos)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('UPDATE jugadores SET viaje_hasta = ?, viaje_destino_id = ? WHERE user_id = ?',
              (hasta.isoformat(), destino_id, user_id))
    conn.commit()
    conn.close()
    import db_helper as _dbh
    _dbh.set_actividad(user_id, "viaje")
    await asyncio.sleep(tiempo_segundos)
    await _completar_viaje(user_id, destino_id, context)

async def _completar_viaje(user_id: int, destino_id: int, context: ContextTypes.DEFAULT_TYPE):
    destino = _obtener_destino(destino_id)
    if not destino:
        return
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('UPDATE jugadores SET viaje_hasta = NULL, viaje_destino_id = NULL WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()
    _actualizar_zona_jugador(user_id, destino_id)
    _actualizar_cooldown_entrada(user_id, destino["color"])
    # Hook logros
    try:
        import logros as _logros
        _logros.registrar_viaje(user_id)
    except Exception:
        pass
    # Hook misiones
    try:
        import misiones as _mis
        _mis.completar_mision(user_id, "primer_viaje", context)
        if destino.get("color") == "amarilla":
            _mis.completar_mision(user_id, "explorar_zona_amarilla", context)
    except Exception:
        pass

    # Usar _bot_ref global para garantizar acceso al bot incluso cuando
    # context es None (viaje restaurado tras reinicio) o stale.
    bot = _bot_ref or (context.bot if context else None)
    if not bot:
        return

    # Liberar actividad "viaje"
    import db_helper as _dbh
    _dbh.set_actividad(user_id, None)

    # Pre-cargar comandos en el servidor de Telegram ANTES del mensaje, sin
    # disparar todavía el toggle visual (ese se hace después del teclado para
    # que el cliente ya haya renderizado el mensaje cuando recibe el cambio).
    try:
        from zonas_comandos import _preparar_comandos_sin_toggle
        await _preparar_comandos_sin_toggle(bot, user_id)
    except Exception:
        pass

    # Mensaje de llegada (sin botón, limpio)
    await bot.send_message(
        chat_id=user_id,
        text=f"✨ Has llegado a *{destino['nombre']}* (Territorio {destino['faccion_nombre']}).",
        parse_mode="Markdown",
    )

    # Enviar teclado rápido actualizado según tipo de zona
    if destino["tipo"] == "ciudad":
        try:
            from teclado_rapido import get_teclado_principal, _teclado_esta_oculto, marcar_tipo
            if _teclado_esta_oculto(user_id):
                await bot.send_message(user_id, "🏙️ Usa `/ciudad` para acceder a los servicios.", parse_mode="Markdown")
            else:
                await bot.send_message(user_id, "🏙️ Usa `/ciudad` para acceder a los servicios.", parse_mode="Markdown", reply_markup=get_teclado_principal(user_id))
            marcar_tipo(user_id, "ciudad")
        except Exception:
            await bot.send_message(user_id, "🏙️ Usa `/ciudad` para acceder a los servicios.", parse_mode="Markdown")
    else:
        try:
            from teclado_rapido import get_teclado_salvaje, _teclado_esta_oculto, marcar_tipo
            _lore = destino.get("descripcion", destino["nombre"])
            if _teclado_esta_oculto(user_id):
                await bot.send_message(user_id, f"_{_lore}_", parse_mode="Markdown")
            else:
                await bot.send_message(user_id, f"_{_lore}_", parse_mode="Markdown", reply_markup=get_teclado_salvaje(user_id))
            marcar_tipo(user_id, "salvaje")
        except Exception:
            pass

    # ── Hook resumen_sesion ──
    if destino["tipo"] == "ciudad":
        try:
            import resumen_sesion as _rs
            await _rs.enviar_resumen(bot, user_id)
        except Exception:
            pass
    else:
        try:
            import resumen_sesion as _rs
            _rs.iniciar_sesion(user_id, destino["nombre"])
        except Exception:
            pass

    # ── Hook zona_activa: mostrar quién hay en la zona al llegar al salvaje ──
    if destino["tipo"] != "ciudad":
        try:
            import zona_activa as _za
            jugadores_zona = _za.obtener_jugadores_en_zona(destino["nombre"], excluir_uid=user_id)
            if jugadores_zona:
                lineas = [f"  • {j['nombre_personaje']} (Nv.{j.get('nivel',1)} {j.get('faccion','')})"
                          for j in jugadores_zona[:5]]
                extra = f"  ...y {len(jugadores_zona)-5} más" if len(jugadores_zona) > 5 else ""
                txt = (f"👥 *Jugadores activos en {destino['nombre']}:*\n"
                       + "\n".join(lineas)
                       + (f"\n{extra}" if extra else "")
                       + "\n\nUsa /zona_jugadores para ver la lista completa.")
                await bot.send_message(chat_id=user_id, text=txt, parse_mode="Markdown")
        except Exception:
            pass

    # Guia contextual
    try:
        import guia_contextual as _gc
        tipo_llegada = "viaje_llegada_ciudad" if destino["tipo"] == "ciudad" else "viaje_llegada_salvaje"
        await _gc.enviar(user_id, context, tipo_llegada, {
            "destino": destino["nombre"],
            "color": destino.get("color", "azul"),
        })
    except Exception:
        pass

    # ── Botón al final (último mensaje = el más visible) ──────────────────────
    # Se envía DESPUÉS de todos los demás mensajes para que el jugador lo vea
    # inmediatamente sin tener que hacer scroll hacia arriba.
    _kb_zona = InlineKeyboardMarkup([[
        InlineKeyboardButton("📋 Ver comandos de zona", callback_data=f"viaje_ver_comandos_{user_id}")
    ]])
    await bot.send_message(
        chat_id=user_id,
        text="👆 *Toca el botón para actualizar el menú de comandos de tu nueva zona.*",
        parse_mode="Markdown",
        reply_markup=_kb_zona,
    )

async def _cancelar_viaje(user_id: int, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT viaje_hasta FROM jugadores WHERE user_id = ?', (user_id,))
    row = c.fetchone()
    if not row or not row[0]:
        await context.bot.send_message(user_id, "No estás viajando actualmente.")
        return
    c.execute('UPDATE jugadores SET viaje_hasta = NULL, viaje_destino_id = NULL WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()
    task = _viajes_tasks.pop(user_id, None)
    if task and not task.done():
        task.cancel()
    await context.bot.send_message(user_id, "Viaje cancelado. Sigues en tu zona actual.")

def _obtener_viaje_activo(user_id: int) -> Optional[Dict]:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT viaje_hasta, viaje_destino_id FROM jugadores WHERE user_id = ?', (user_id,))
    row = c.fetchone()
    conn.close()
    if row and row[0]:
        hasta = datetime.fromisoformat(row[0])
        if hasta > datetime.now():
            destino = _obtener_destino(row[1])
            return {"hasta": hasta, "destino": destino}
    return None

# ==================== PEaje (integración) ====================
async def _solicitar_peaje_para_viaje(update: Update, context: ContextTypes.DEFAULT_TYPE, ciudad_destino: dict):
    """Llama al peaje desde viajes."""
    user_id = update.effective_user.id
    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        await update.callback_query.edit_message_text("Error: jugador no encontrado.")
        return
    nivel = jug.get("nivel", 1)
    reputacion = jug.get("reputacion", 0)
    # Función calcular_peaje debe estar accesible (la importaremos desde peaje)
    from peaje import calcular_peaje
    peaje = calcular_peaje(nivel, reputacion)
    context.user_data["peaje_pendiente"] = {
        "ciudad_faccion": ciudad_destino["faccion_nombre"],
        "ciudad_nombre": ciudad_destino["nombre"],
        "peaje_original": peaje,
        "viaje_pendiente": context.user_data.get("viaje_pendiente")
    }
    keyboard = [
        [InlineKeyboardButton(f"🪙 Pagar {peaje} oro", callback_data="peaje_pagar_viaje")],
        [InlineKeyboardButton("⚔️ No pagar (quedar marcado)", callback_data="peaje_marcado_viaje")]
    ]
    await update.callback_query.edit_message_text(
        f"⚠️ Estás intentando entrar a *{ciudad_destino['nombre']}* (territorio de {ciudad_destino['faccion_nombre']}).\n"
        f"Peaje: *{peaje} de oro*.\n"
        f"Si no pagas, quedarás *marcado* y los guardias te atacarán.\n\n*Nota:* el viaje se iniciará después de decidir.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ==================== COMANDOS DE VIAJES ====================
async def cmd_viajar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        await update.effective_message.reply_text("Primero crea un personaje con /start.")
        return
    if db_helper.esta_marcado(user_id):
        await update.effective_message.reply_text("❌ Estás marcado. No puedes viajar hasta que pagues rescate con `/pagar_rescate`.")
        return
    try:
        import guerra_facciones as _gf
        if _gf.jugador_en_lockdown(user_id):
            await update.effective_message.reply_text(
                "🔒 *¡Los viajes están suspendidos durante la Guerra de Facciones!*\n\n"
                "Registra tu acción (⚔️ atacar, 🛡️ defender o ⏭️ saltarte) para esperar el resultado.\n"
                "Podrás viajar de nuevo cuando la guerra termine.",
                parse_mode="Markdown"
            )
            return
    except Exception:
        pass
    viaje = _obtener_viaje_activo(user_id)
    if viaje:
        restante = int((viaje["hasta"] - datetime.now()).total_seconds())
        await update.effective_message.reply_text(f"⏳ Ya estás de viaje hacia {viaje['destino']['nombre']}. Tiempo restante: {restante} segundos. Usa `/cancelar_viaje`.")
        return
    zona_actual_id = jug.get("zona_actual_id")
    origen = _obtener_destino(zona_actual_id) if zona_actual_id else None
    if not origen:
        await update.effective_message.reply_text("No se pudo determinar tu zona actual.")
        return
    faccion_id = jug.get("faccion_id", 1)
    nivel = jug["nivel"]
    todos = _obtener_destinos()
    propios = []
    enemigos = []
    es_dios = sa._modo_dios_activo(user_id)
    for d in todos:
        if d["id"] == origen["id"]:
            continue
        # Modo dios: acceso total, sin filtros de color ni nivel
        if not es_dios:
            if not _color_permitido_por_nivel(nivel, d["color"]):
                continue
            if nivel < d["nivel_requerido"]:
                continue
        if d["faccion_id"] == faccion_id:
            propios.append(d)
        else:
            enemigos.append(d)
    keyboard = []
    if propios:
        keyboard.append([InlineKeyboardButton("🏰 Tus zonas", callback_data="viaje_show_propios")])
    if enemigos:
        keyboard.append([InlineKeyboardButton("🌍 Incursión a territorio enemigo", callback_data="viaje_show_enemigos")])
    keyboard.append([InlineKeyboardButton("✈️ Vuelo rápido (ciudades)", callback_data="viaje_vuelo_rapido")])
    keyboard.append([InlineKeyboardButton("❌ Cerrar", callback_data="viaje_cerrar")])
    await update.effective_message.reply_text(
        f"🌍 *Sistema de viajes*\nUbicación: {origen['nombre']} ({origen['faccion_nombre']}) - Color {origen['color'].capitalize()}\n\nSelecciona:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def viaje_show_propios(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        return
    origen = _obtener_destino(jug["zona_actual_id"])
    if not origen:
        return
    nivel = jug["nivel"]
    faccion_id = jug.get("faccion_id", 1)
    es_dios = sa._modo_dios_activo(user_id)
    todos = _obtener_destinos()
    if es_dios:
        # Modo dios: todas las zonas sin filtro de color/nivel
        propios = [d for d in todos if d["id"] != origen["id"]]
    else:
        propios = [d for d in todos if d["faccion_id"] == faccion_id and d["id"] != origen["id"] and _color_permitido_por_nivel(nivel, d["color"]) and nivel >= d["nivel_requerido"]]
    if not propios:
        await query.edit_message_text("No hay destinos disponibles de tu facción.")
        return
    keyboard = []
    for d in propios:
        tipo_ico = "🏙️" if d["tipo"] == "ciudad" else "🌿"
        texto = f"{_emoji_zona(d)} {d['nombre']} {tipo_ico}"
        keyboard.append([InlineKeyboardButton(texto, callback_data=f"viaje_destino_{d['id']}")])
    keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data="viaje_volver")])
    titulo = "👑 Todas las zonas (Modo Dios):" if es_dios else "🏰 Tus zonas (misma facción):"
    await query.edit_message_text(titulo, reply_markup=InlineKeyboardMarkup(keyboard))

async def viaje_show_enemigos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        return
    origen = _obtener_destino(jug["zona_actual_id"])
    if not origen:
        await query.edit_message_text("No se pudo determinar tu zona actual.")
        return
    nivel = jug["nivel"]
    faccion_id = jug.get("faccion_id", 1)
    enemigos = [d for d in _obtener_destinos() if d["faccion_id"] != faccion_id and d["id"] != origen["id"] and _color_permitido_por_nivel(nivel, d["color"]) and nivel >= d["nivel_requerido"]]
    if not enemigos:
        await query.edit_message_text("No hay zonas enemigas disponibles (quizás por nivel).")
        return
    por_faccion = {}
    for e in enemigos:
        por_faccion.setdefault(e["faccion_nombre"], []).append(e)
    keyboard = []
    for fac, zonas in por_faccion.items():
        keyboard.append([InlineKeyboardButton(f"🏴‍☠️ {fac}", callback_data="viaje_faccion_noop")])
        for z in zonas:
            tipo_ico = "🏙️" if z["tipo"] == "ciudad" else "🌿"
            texto = f"   {_emoji_zona(z)} {z['nombre']} {tipo_ico}"
            keyboard.append([InlineKeyboardButton(texto, callback_data=f"viaje_destino_{z['id']}")])
    keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data="viaje_volver")])
    await query.edit_message_text("🌍 Incursión a territorio enemigo:", reply_markup=InlineKeyboardMarkup(keyboard))

async def viaje_destino_seleccionado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        destino_id = int(query.data.split("_")[2])
    except (ValueError, IndexError):
        await query.edit_message_text("❌ Error al seleccionar destino.")
        return
    user_id = update.effective_user.id
    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        await query.edit_message_text("❌ No tienes personaje registrado.")
        return
    destino = _obtener_destino(destino_id)
    origen = _obtener_destino(jug["zona_actual_id"])
    if not origen or not destino:
        await query.edit_message_text("Error con origen/destino.")
        return
    puede, restante = _puede_cambiar_color(user_id, origen["color"], destino["color"])
    if not puede:
        await query.edit_message_text(f"⚠️ No puedes salir de zona {origen['color'].capitalize()} hacia otro color todavía. Espera {restante} segundos.")
        return
    es_enemigo = (destino["faccion_id"] != jug.get("faccion_id", 1))
    if es_enemigo and destino["tipo"] == "ciudad":
        # Guardar pendiente
        context.user_data["viaje_pendiente"] = {
            "user_id": user_id,
            "destino_id": destino_id,
            "origen_id": origen["id"],
            "tiempo_base": _calcular_tiempo_viaje(origen["color"], destino["color"], 0, origen.get("faccion_id", 0), destino.get("faccion_id", 0))
        }
        await _solicitar_peaje_para_viaje(update, context, destino)
        return
    await _iniciar_viaje_directo(update, context, destino, origen)

async def _iniciar_viaje_directo(update: Update, context: ContextTypes.DEFAULT_TYPE, destino: dict, origen: dict, skip_ciudad_cost: bool = False):
    user_id = update.effective_user.id
    # Debug: viaje instantáneo y gratuito para el superadmin
    try:
        from modo_debug import esta_en_debug
        if esta_en_debug(user_id):
            await update.callback_query.edit_message_text(
                f"🐛 [DEBUG] Viaje instantáneo a *{destino['nombre']}*.", parse_mode="Markdown"
            )
            # Zona PRIMERO, comandos al servidor (sin toggle), teclado, y LUEGO toggle
            _actualizar_zona_jugador(user_id, destino["id"])
            _actualizar_cooldown_entrada(user_id, destino["color"])
            import db_helper as _dbh_d
            _dbh_d.set_actividad(user_id, None)
            try:
                from zonas_comandos import _preparar_comandos_sin_toggle, _disparar_toggle_menu
                await _preparar_comandos_sin_toggle(context.bot, user_id)
            except Exception:
                pass
            from teclado_rapido import get_teclado_principal, get_teclado_salvaje, _teclado_esta_oculto, marcar_tipo
            oculto = _teclado_esta_oculto(user_id)
            if destino["tipo"] == "ciudad":
                if not oculto:
                    await update.callback_query.message.reply_text(
                        "🏙️ Usa `/ciudad` para acceder a los servicios.", parse_mode="Markdown",
                        reply_markup=get_teclado_principal(user_id)
                    )
                marcar_tipo(user_id, "ciudad")
            else:
                _lore = destino.get("descripcion", destino["nombre"])
                if not oculto:
                    await update.callback_query.message.reply_text(
                        f"_{_lore}_",
                        parse_mode="Markdown",
                        reply_markup=get_teclado_salvaje(user_id)
                    )
                marcar_tipo(user_id, "salvaje")
            # Botón al final — el más visible para el jugador
            _kb_debug = InlineKeyboardMarkup([[
                InlineKeyboardButton("📋 Ver comandos de zona", callback_data=f"viaje_ver_comandos_{user_id}")
            ]])
            await context.bot.send_message(
                chat_id=user_id,
                text="👆 *Toca el botón para actualizar el menú de comandos de tu nueva zona.*",
                parse_mode="Markdown",
                reply_markup=_kb_debug,
            )
            return
    except Exception:
        pass
    # Costo Eternium para viajes entre ciudades (se omite si ya se pagó peaje)
    if not skip_ciudad_cost and origen.get("tipo") == "ciudad" and destino.get("tipo") == "ciudad":
        try:
            saldos = economia.obtener_saldos(user_id)
            if saldos["eternium"] < PRECIO_VIAJE_CIUDAD:
                await update.callback_query.edit_message_text(
                    f"⚡ Para viajar entre ciudades necesitas {PRECIO_VIAJE_CIUDAD} Eternium.\n"
                    f"Tienes: {saldos['eternium']} Eternium.\n"
                    f"Consigue más en mazmorras o eventos, o usa /vuelo_rapido."
                )
                return
            economia.modificar_saldo(user_id, "eternium", -PRECIO_VIAJE_CIUDAD, "viaje entre ciudades")
        except Exception:
            pass
    montura = _obtener_montura_activa(user_id)
    velocidad = montura["velocidad"] if montura else 0
    tiempo = _calcular_tiempo_viaje(origen["color"], destino["color"], velocidad, origen.get("faccion_id", 0), destino.get("faccion_id", 0))
    if tiempo == 0:
        await update.callback_query.edit_message_text(f"🔄 Viajando instantáneamente a {destino['nombre']}...")
        _actualizar_zona_jugador(user_id, destino["id"])
        _actualizar_cooldown_entrada(user_id, destino["color"])
        await update.callback_query.message.reply_text(f"✨ Has llegado a {destino['nombre']}.")
        if destino["tipo"] == "ciudad":
            await update.callback_query.message.reply_text("🏙️ Usa /ciudad.")
        else:
            _lore = destino.get("descripcion", destino["nombre"])
            await update.callback_query.message.reply_text(f"_{_lore}_", parse_mode="Markdown")
        return
    await update.callback_query.edit_message_text(f"⏳ Viajando hacia {destino['nombre']}. Llegarás en {tiempo} segundos.")
    task = asyncio.create_task(_iniciar_viaje(user_id, destino["id"], tiempo, context))
    _viajes_tasks[user_id] = task
    # Guia contextual
    try:
        import guia_contextual as _gc
        await _gc.enviar(user_id, context, "viaje_iniciado", {
            "destino": destino["nombre"],
            "tiempo": tiempo,
        })
    except Exception:
        pass

# ==================== VUELO RÁPIDO ====================
async def cmd_vuelo_rapido(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        await update.effective_message.reply_text("Crea un personaje primero.")
        return
    if db_helper.esta_marcado(user_id):
        await update.effective_message.reply_text("Estás marcado, no puedes usar vuelo rápido.")
        return
    ciudades = [d for d in _obtener_destinos() if d["tipo"] == "ciudad"]
    if not ciudades:
        await update.effective_message.reply_text("No hay ciudades disponibles.")
        return
    keyboard = []
    for c in ciudades:
        keyboard.append([InlineKeyboardButton(f"{_emoji_por_color(c['color'])} {c['nombre']} ({c['faccion_nombre']}) - {PRECIO_VUELO_RAPIDO} Eternium", callback_data=f"vuelo_destino_{c['id']}")])
    keyboard.append([InlineKeyboardButton("❌ Cancelar", callback_data="viaje_cerrar")])
    await update.effective_message.reply_text("✈️ *Vuelo rápido*\nSelecciona ciudad destino:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def vuelo_destino_seleccionado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        destino_id = int(query.data.split("_")[2])
    except (ValueError, IndexError):
        await query.edit_message_text("❌ Error al seleccionar destino.")
        return
    user_id = update.effective_user.id
    destino = _obtener_destino(destino_id)
    if not destino:
        await query.edit_message_text("Destino inválido.")
        return
    saldos = economia.obtener_saldos(user_id)
    if saldos["eternium"] < PRECIO_VUELO_RAPIDO:
        await query.edit_message_text(f"No tienes suficiente Eternium. Necesitas {PRECIO_VUELO_RAPIDO}.")
        return
    economia.modificar_saldo(user_id, "eternium", -PRECIO_VUELO_RAPIDO, "vuelo rápido")
    _actualizar_zona_jugador(user_id, destino_id)
    _actualizar_cooldown_entrada(user_id, destino["color"])
    # Pre-cargar comandos en el servidor de Telegram sin disparar el toggle visual
    try:
        from zonas_comandos import _preparar_comandos_sin_toggle
        await _preparar_comandos_sin_toggle(context.bot, user_id)
    except Exception:
        pass
    await query.edit_message_text(f"✈️ Has llegado instantáneamente a *{destino['nombre']}*.", parse_mode="Markdown")
    # Actualizar teclado persistente según zona de destino
    try:
        from teclado_rapido import get_teclado_principal, get_teclado_salvaje, _teclado_esta_oculto, marcar_tipo
        oculto = _teclado_esta_oculto(user_id)
        if destino["tipo"] == "ciudad":
            if oculto:
                await query.message.reply_text("🏙️ Usa `/ciudad` para acceder a los servicios.", parse_mode="Markdown")
            else:
                await query.message.reply_text("🏙️ Usa `/ciudad` para acceder a los servicios.", parse_mode="Markdown", reply_markup=get_teclado_principal(user_id))
            marcar_tipo(user_id, "ciudad")
        else:
            _lore = destino.get("descripcion", destino["nombre"])
            if oculto:
                await query.message.reply_text(f"_{_lore}_", parse_mode="Markdown")
            else:
                await query.message.reply_text(f"_{_lore}_", parse_mode="Markdown", reply_markup=get_teclado_salvaje(user_id))
            marcar_tipo(user_id, "salvaje")
    except Exception:
        if destino["tipo"] == "ciudad":
            await query.message.reply_text("🏙️ Usa `/ciudad`.", parse_mode="Markdown")
    # Botón al final — el más visible para el jugador
    _kb_vuelo = InlineKeyboardMarkup([[
        InlineKeyboardButton("📋 Ver comandos de zona", callback_data=f"viaje_ver_comandos_{user_id}")
    ]])
    await query.message.reply_text(
        "👆 *Toca el botón para actualizar el menú de comandos de tu nueva zona.*",
        parse_mode="Markdown",
        reply_markup=_kb_vuelo,
    )

# ==================== COMANDOS DE MONTURAS ====================
async def cmd_comprar_montura(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Compra una montura del catálogo usando oro/eternium y la añade al inventario."""
    user_id = update.effective_user.id
    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        await update.effective_message.reply_text("Primero crea un personaje.")
        return
    nivel = jug["nivel"]
    # Filtrar monturas que el jugador puede comprar (nivel)
    disponibles = []
    for mid, data in MONTURAS.items():
        if data.get("nivel_requerido", 1) <= nivel:
            disponibles.append(mid)
    if not disponibles:
        await update.effective_message.reply_text("No hay monturas disponibles para tu nivel.")
        return
    keyboard = []
    for mid in disponibles[:20]:  # límite por mensaje
        data = MONTURAS[mid]
        texto = f"{data['nombre']} (nivel {data['nivel_requerido']}) - Vel {data['velocidad']}%"
        if data.get("precio_oro"):
            texto += f" {data['precio_oro']} oro"
        if data.get("precio_eternium"):
            texto += f" {data['precio_eternium']} eternium"
        keyboard.append([InlineKeyboardButton(texto, callback_data=f"comprar_montura_{mid}")])
    keyboard.append([InlineKeyboardButton("❌ Cancelar", callback_data="viaje_cerrar")])
    await update.effective_message.reply_text("🛒 *Comprar montura*\nSelecciona una:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def comprar_montura_seleccionada(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        mid = query.data.split("_")[2]
    except IndexError:
        await query.edit_message_text("❌ Error al seleccionar montura.")
        return
    data = MONTURAS.get(mid)
    if not data:
        await query.edit_message_text("Montura no encontrada.")
        return
    user_id = update.effective_user.id
    # Verificar nivel
    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        await query.edit_message_text("❌ No tienes personaje registrado.")
        return
    if jug["nivel"] < data.get("nivel_requerido", 1):
        await query.edit_message_text("No cumples el nivel requerido.")
        return
    # Verificar si ya la tiene (no se puede comprar duplicada si es única, pero permitimos)
    # Descontar precios
    oro = data.get("precio_oro", 0)
    eternium = data.get("precio_eternium", 0)
    saldos = economia.obtener_saldos(user_id)
    if oro > 0 and saldos["oro"] < oro:
        await query.edit_message_text(f"No tienes suficiente oro. Necesitas {oro}.")
        return
    if eternium > 0 and saldos["eternium"] < eternium:
        await query.edit_message_text(f"No tienes suficiente eternium. Necesitas {eternium}.")
        return
    if oro > 0:
        economia.modificar_saldo(user_id, "oro", -oro, f"compra montura {data['nombre']}")
    if eternium > 0:
        economia.modificar_saldo(user_id, "eternium", -eternium, f"compra montura {data['nombre']}")
    # Añadir al inventario (permanente)
    _agregar_montura_inventario(user_id, mid, expira=None)
    await query.edit_message_text(f"✅ Has comprado {data['nombre']} y está en tu inventario. Usa `/equipar_montura {mid}` para equiparla.")

async def cmd_equipar_montura(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Equipa una montura que el jugador posea."""
    if not context.args:
        await update.effective_message.reply_text("Uso: `/equipar_montura <id_montura>`\nEjemplo: `/equipar_montura montura_5`")
        return
    mid = context.args[0]
    user_id = update.effective_user.id
    if not _tiene_montura_en_inventario(user_id, mid):
        await update.effective_message.reply_text("No posees esa montura o ha expirado.")
        return
    if _equipar_montura(user_id, mid):
        data = MONTURAS.get(mid, {})
        nombre = data.get("nombre", mid)
        await update.effective_message.reply_text(f"🐎 Has equipado {nombre}. Velocidad +{data.get('velocidad',0)}% en viajes.")
    else:
        await update.effective_message.reply_text("No se pudo equipar la montura.")

async def cmd_desmontar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    montura = _obtener_montura_activa(user_id)
    if not montura:
        await update.effective_message.reply_text("No tienes ninguna montura equipada.")
        return
    _desmontar(user_id)
    await update.effective_message.reply_text("Has desmontado. Ahora viajas a pie.")

async def cmd_mis_monturas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT montura_id, expira FROM inventario_monturas WHERE user_id = ? AND cantidad > 0', (user_id,))
    rows = c.fetchall()
    conn.close()
    if not rows:
        await update.effective_message.reply_text("No tienes monturas. Compra una con `/comprar_montura`.")
        return
    texto = "📦 *Tus monturas:*\n"
    for mid, expira in rows:
        data = MONTURAS.get(mid, {})
        nombre = data.get("nombre", mid)
        estado = " (permanente)" if not expira else " (temporal)"
        texto += f"• {nombre}{estado}\n"
    await update.effective_message.reply_text(texto, parse_mode="Markdown")

# ==================== ESTADO Y CANCELAR ====================
async def cmd_estado_viaje(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    viaje = _obtener_viaje_activo(user_id)
    if not viaje:
        await update.effective_message.reply_text("No estás viajando.")
        return
    restante = int((viaje["hasta"] - datetime.now()).total_seconds())
    await update.effective_message.reply_text(f"⏳ Viaje hacia {viaje['destino']['nombre']}. Tiempo restante: {restante} segundos.")

async def cmd_cancelar_viaje(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _cancelar_viaje(update.effective_user.id, context)

# ==================== NAVEGACIÓN ====================
async def viaje_volver(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reconstruye el menu principal de viajes editando el mensaje actual."""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        await query.edit_message_text("Error: personaje no encontrado.")
        return
    zona_actual_id = jug.get("zona_actual_id")
    origen = _obtener_destino(zona_actual_id) if zona_actual_id else None
    if not origen:
        await query.edit_message_text("No se pudo determinar tu zona actual.")
        return
    faccion_id = jug.get("faccion_id", 1)
    nivel = jug["nivel"]
    es_dios = sa._modo_dios_activo(user_id)
    todos = _obtener_destinos()
    propios = []
    enemigos = []
    for d in todos:
        if d["id"] == origen["id"]:
            continue
        if not es_dios:
            if not _color_permitido_por_nivel(nivel, d["color"]):
                continue
            if nivel < d["nivel_requerido"]:
                continue
        if d["faccion_id"] == faccion_id:
            propios.append(d)
        else:
            if es_dios or origen["color"] in ("roja", "negra"):
                enemigos.append(d)
    keyboard = []
    if propios:
        keyboard.append([InlineKeyboardButton("🏰 Tus zonas", callback_data="viaje_show_propios")])
    if enemigos:
        keyboard.append([InlineKeyboardButton("🌍 Incursión a territorio enemigo", callback_data="viaje_show_enemigos")])
    keyboard.append([InlineKeyboardButton("✈️ Vuelo rápido (ciudades)", callback_data="viaje_vuelo_rapido")])
    keyboard.append([InlineKeyboardButton("❌ Cerrar", callback_data="viaje_cerrar")])
    titulo = "👑 *Modo Dios — acceso total*" if es_dios else "🌍 *Sistema de viajes*"
    await query.edit_message_text(
        f"{titulo}\nUbicación: {origen['nombre']} ({origen['faccion_nombre']}) - Color {origen['color'].capitalize()}\n\nSelecciona:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def viaje_cerrar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("🗺️ Viajes cerrados.")

async def viaje_vuelo_rapido(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        await query.edit_message_text("❌ Crea un personaje primero con /start.")
        return
    if db_helper.esta_marcado(user_id):
        await query.edit_message_text("⛔ Estás marcado. Paga el rescate antes de usar el vuelo rápido.")
        return
    ciudades = [d for d in _obtener_destinos() if d["tipo"] == "ciudad"]
    if not ciudades:
        await query.edit_message_text("❌ No hay ciudades disponibles.")
        return
    keyboard = []
    for c in ciudades:
        keyboard.append([InlineKeyboardButton(
            f"{_emoji_por_color(c['color'])} {c['nombre']} ({c['faccion_nombre']}) — {PRECIO_VUELO_RAPIDO} ⚡",
            callback_data=f"vuelo_destino_{c['id']}"
        )])
    keyboard.append([InlineKeyboardButton("❌ Cancelar", callback_data="viaje_cerrar")])
    await query.edit_message_text(
        "✈️ *Vuelo rápido*\nElige ciudad destino (instantáneo, cuesta Eternium):",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def viaje_faccion_noop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()

# ==================== BLOQUEO DE ACCIONES ====================
async def check_viaje_activo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Función para llamar al inicio de cada comando de acción."""
    user_id = update.effective_user.id
    viaje = _obtener_viaje_activo(user_id)
    if viaje:
        restante = int((viaje["hasta"] - datetime.now()).total_seconds())
        await update.effective_message.reply_text(f"⏳ No puedes hacer eso mientras viajas. Llegarás a {viaje['destino']['nombre']} en {restante} segundos. Usa /cancelar_viaje.")
        return False
    return True

# ==================== RESTAURACIÓN AL INICIAR BOT ====================
async def _cb_ver_comandos_zona(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback del botón 'Ver comandos de zona' en el mensaje de llegada."""
    query = update.callback_query
    await query.answer("🔄 Actualizando…", show_alert=False)
    user_id = update.effective_user.id
    bot = context.bot
    # Editar el mensaje para quitar el botón (evita que se presione varias veces)
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass
    # Disparar el toggle del menú "/"
    try:
        from zonas_comandos import _disparar_toggle_menu
        await _disparar_toggle_menu(bot, user_id)
    except Exception:
        pass
    # Confirmación visible para que el jugador sepa que funcionó
    await bot.send_message(
        chat_id=user_id,
        text="✅ *Menú actualizado.* Escribe `/` para ver los comandos disponibles en esta zona.",
        parse_mode="Markdown",
    )


async def restaurar_viajes_pendientes(app):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT user_id, viaje_hasta, viaje_destino_id FROM jugadores WHERE viaje_hasta > ?', (datetime.now().isoformat(),))
    rows = c.fetchall()
    conn.close()
    for user_id, hasta_str, destino_id in rows:
        hasta = datetime.fromisoformat(hasta_str)
        restante = (hasta - datetime.now()).total_seconds()
        if restante > 0:
            task = asyncio.create_task(_iniciar_viaje(user_id, destino_id, restante, None))
            _viajes_tasks[user_id] = task
            try:
                await app.bot.send_message(user_id, f"Se ha reanudado tu viaje. Llegarás en {int(restante)} segundos.")
            except:
                pass

# ==================== REGISTRO DE HANDLERS ====================
def registrar_handlers(app):
    global _bot_ref
    _bot_ref = app.bot
    app.add_handler(CommandHandler("viajar", cmd_viajar))
    app.add_handler(CommandHandler("estado_viaje", cmd_estado_viaje))
    app.add_handler(CommandHandler("cancelar_viaje", cmd_cancelar_viaje))
    app.add_handler(CommandHandler("vuelo_rapido", cmd_vuelo_rapido))
    app.add_handler(CommandHandler("comprar_montura", cmd_comprar_montura))
    app.add_handler(CommandHandler("equipar_montura", cmd_equipar_montura))
    app.add_handler(CommandHandler("desmontar", cmd_desmontar))
    app.add_handler(CommandHandler("mis_monturas", cmd_mis_monturas))
    app.add_handler(CallbackQueryHandler(viaje_show_propios, pattern="^viaje_show_propios$"))
    app.add_handler(CallbackQueryHandler(viaje_show_enemigos, pattern="^viaje_show_enemigos$"))
    app.add_handler(CallbackQueryHandler(viaje_destino_seleccionado, pattern="^viaje_destino_"))
    app.add_handler(CallbackQueryHandler(viaje_volver, pattern="^viaje_volver$"))
    app.add_handler(CallbackQueryHandler(viaje_cerrar, pattern="^viaje_cerrar$"))
    app.add_handler(CallbackQueryHandler(viaje_vuelo_rapido, pattern="^viaje_vuelo_rapido$"))
    app.add_handler(CallbackQueryHandler(viaje_faccion_noop, pattern="^viaje_faccion_noop$"))
    app.add_handler(CallbackQueryHandler(vuelo_destino_seleccionado, pattern="^vuelo_destino_"))
    app.add_handler(CallbackQueryHandler(comprar_montura_seleccionada, pattern="^comprar_montura_"))
    app.add_handler(CallbackQueryHandler(_cb_ver_comandos_zona, pattern=r"^viaje_ver_comandos_"))
async def reanudar_viaje(update: Update, context: ContextTypes.DEFAULT_TYPE, viaje_pendiente: dict, cobrar_ciudad: bool = True):
    destino = _obtener_destino(viaje_pendiente["destino_id"])
    origen = _obtener_destino(viaje_pendiente["origen_id"])
    if destino and origen:
        await _iniciar_viaje_directo(update, context, destino, origen, skip_ciudad_cost=not cobrar_ciudad)

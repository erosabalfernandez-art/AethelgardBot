#!/usr/bin/env python3
# db_helper.py
# Módulo de base de datos para Aethelgard (zona azul + expansiones futuras)
# Todas las tablas se crean con posibilidad de añadir columnas después.

import sqlite3
import json
import random
import string
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple, Any

DB_PATH = "aethelgard.db"  # Nombre de la base de datos

# ── MEJORAS DE RENDIMIENTO (importadas desde db_helper_perf.py) ──────────────
try:
    from db_helper_perf import (
        player_cache,
        user_lock_manager,
        con_reintento,
        sumar_oro_atomico,
        sumar_xp_atomico,
        sumar_eternium_atomico,
        sumar_reputacion_atomica,
        agregar_item_seguro,
        quitar_item_seguro,
        obtener_jugador_cached,
        actualizar_jugador_con_invalidacion,
    )
    _PERF_DISPONIBLE = True
except ImportError:
    _PERF_DISPONIBLE = False
    import logging as _log
    _log.getLogger(__name__).warning("db_helper_perf no disponible — usando funciones estándar.")

# ==================== INICIALIZACIÓN DE TABLAS ====================
def _get_conn() -> sqlite3.Connection:
    """Abre una conexión SQLite con todas las optimizaciones de concurrencia activadas."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    # WAL: múltiples lecturas simultáneas sin bloquear escrituras
    c.execute("PRAGMA journal_mode=WAL")
    # Balance velocidad/seguridad (no borra datos, solo puede perder la última transacción en corte de luz)
    c.execute("PRAGMA synchronous=NORMAL")
    # Caché de páginas en RAM (≈16 MB por conexión)
    c.execute("PRAGMA cache_size=-16000")
    # Tablas temporales en RAM en vez de disco
    c.execute("PRAGMA temp_store=MEMORY")
    # Espera hasta 30 s si la DB está ocupada por otra escritura
    c.execute("PRAGMA busy_timeout=30000")
    return conn


def init_db():
    """Crea todas las tablas si no existen (estructura completa)."""
    conn = _get_conn()
    c = conn.cursor()

    # 1. Jugadores (tabla principal)
    c.execute('''CREATE TABLE IF NOT EXISTS jugadores (
        user_id INTEGER PRIMARY KEY,
        nombre_personaje TEXT NOT NULL,
        clase TEXT NOT NULL,
        subclase TEXT,
        faccion TEXT NOT NULL,
        nivel INTEGER DEFAULT 1,
        experiencia INTEGER DEFAULT 0,
        hp_actual INTEGER,
        hp_max INTEGER,
        oro INTEGER DEFAULT 0,
        eternium INTEGER DEFAULT 0,
        creditos_vacio INTEGER DEFAULT 0,
        reputacion INTEGER DEFAULT 0,
        reencarnaciones INTEGER DEFAULT 0,
        ultimo_cambio_faccion TIMESTAMP,
        zona_actual TEXT,
        ubicacion TEXT,  -- 'ciudad' o 'salvaje'
        estado_marcado INTEGER DEFAULT 0,
        marca_expiracion TIMESTAMP,
        inventario TEXT DEFAULT '[]',  -- JSON
        misiones_activas TEXT DEFAULT '[]',  -- JSON
        logros_desbloqueados TEXT DEFAULT '[]',
        habilidades_cooldown TEXT DEFAULT '{}',
        ultima_recoleccion TIMESTAMP,
        fatiga_acumulada INTEGER DEFAULT 0,
        fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        stamina_actual INTEGER DEFAULT 100,
        stamina_maxima INTEGER DEFAULT 100,
        ultima_regeneracion_stamina TIMESTAMP,
        codigo_invitacion TEXT UNIQUE,
        invitado_por INTEGER,
        reclutas_completados INTEGER DEFAULT 0,
        mazmorras_azul_hoy INTEGER DEFAULT 0,
        mazmorras_amarilla_hoy INTEGER DEFAULT 0,
        mazmorras_roja_hoy INTEGER DEFAULT 0,
        mazmorras_negra_hoy INTEGER DEFAULT 0,
        ultimo_reset_mazmorras TIMESTAMP
    )''')

    # Para compatibilidad con versiones anteriores, si alguna columna no existe, se añade
    columnas_nuevas = [
        ("stamina_actual", "INTEGER DEFAULT 100"),
        ("stamina_maxima", "INTEGER DEFAULT 100"),
        ("ultima_regeneracion_stamina", "TIMESTAMP"),
        ("codigo_invitacion", "TEXT UNIQUE"),
        ("invitado_por", "INTEGER"),
        ("reclutas_completados", "INTEGER DEFAULT 0"),
        ("recluta_recompensa_dada", "INTEGER DEFAULT 0"),
        ("mazmorras_azul_hoy", "INTEGER DEFAULT 0"),
        ("mazmorras_amarilla_hoy", "INTEGER DEFAULT 0"),
        ("mazmorras_roja_hoy", "INTEGER DEFAULT 0"),
        ("mazmorras_negra_hoy", "INTEGER DEFAULT 0"),
        ("ultimo_reset_mazmorras", "TIMESTAMP"),
        ("marca_expiracion", "TIMESTAMP"),
        ("titulo_activo", "TEXT DEFAULT NULL"),
        ("actividad_actual", "TEXT DEFAULT NULL"),
        ("actividad_expira", "TIMESTAMP DEFAULT NULL"),
        ("ultima_interaccion", "TIMESTAMP DEFAULT NULL"),
        ("teclado_oculto", "INTEGER DEFAULT 0")
    ]
    for col, tipo in columnas_nuevas:
        try:
            c.execute(f'ALTER TABLE jugadores ADD COLUMN {col} {tipo}')
        except sqlite3.OperationalError:
            pass  # ya existe

    # 2. Transacciones de monedas (para auditoría y retiros)
    c.execute('''CREATE TABLE IF NOT EXISTS transacciones (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        tipo TEXT,
        cantidad INTEGER,
        moneda TEXT,
        motivo TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    # Migración: añadir columna moneda si no existe (bases de datos antiguas)
    try:
        c.execute("ALTER TABLE transacciones ADD COLUMN moneda TEXT")
    except sqlite3.OperationalError:
        pass  # la columna ya existe

    # 3. Solicitudes de retiro de créditos a dinero real
    c.execute('''CREATE TABLE IF NOT EXISTS retiros_solicitados (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        creditos INTEGER,
        estado TEXT DEFAULT 'pendiente',  -- 'pendiente', 'aprobado', 'rechazado'
        fecha_solicitud TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        fecha_procesado TIMESTAMP
    )''')

    # Recetas aprendidas por el jugador (compradas en tienda)
    c.execute('''CREATE TABLE IF NOT EXISTS recetas_jugador (
        user_id INTEGER NOT NULL,
        receta_id TEXT NOT NULL,
        fecha_compra TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (user_id, receta_id)
    )''')


    # 4. Gremios
    c.execute('''CREATE TABLE IF NOT EXISTS gremios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT UNIQUE NOT NULL,
        tag TEXT UNIQUE NOT NULL,
        faccion TEXT NOT NULL,
        nivel INTEGER DEFAULT 1,
        fundador_id INTEGER,
        fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        banco_oro INTEGER DEFAULT 0,
        banco_eternium INTEGER DEFAULT 0,
        energia_nexo INTEGER DEFAULT 0,
        territorios_controlados TEXT DEFAULT '[]'  -- JSON lista de ids o nombres
    )''')

    # 5. Miembros de gremios
    c.execute('''CREATE TABLE IF NOT EXISTS miembros_gremio (
        gremio_id INTEGER,
        jugador_id INTEGER,
        rango TEXT DEFAULT 'miembro',  -- 'lider', 'oficial', 'veterano', 'recluta', 'miembro'
        fecha_ingreso TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (gremio_id, jugador_id)
    )''')

    # 6. Auditoría de movimientos del banco del gremio
    c.execute('''CREATE TABLE IF NOT EXISTS log_gremio (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        gremio_id INTEGER,
        jugador_id INTEGER,
        accion TEXT,  -- 'depositar', 'retirar'
        moneda TEXT,  -- 'oro', 'eternium'
        cantidad INTEGER,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # 7. Edificios de gremio (por gremio, cada edificio tiene nivel)
    c.execute('''CREATE TABLE IF NOT EXISTS edificios_gremio (
        gremio_id INTEGER,
        edificio TEXT,  -- 'refineria', 'forja_maestra', 'cuartel', 'torreta', 'muralla'
        nivel INTEGER DEFAULT 1,
        PRIMARY KEY (gremio_id, edificio)
    )''')

    # 8. Territorios (nexos) del mapa
    c.execute('''CREATE TABLE IF NOT EXISTS territorios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre_zona TEXT UNIQUE NOT NULL,
        tipo_zona TEXT,  -- 'azul', 'amarilla', 'roja', 'negra'
        faccion_controladora TEXT,  -- facción dueña (si la hay)
        gremio_controlador_id INTEGER,  -- gremio específico
        fecha_conquista TIMESTAMP,
        impuesto_actual REAL DEFAULT 0.05,  -- 5%
        nivel_defensa INTEGER DEFAULT 1
    )''')

    # 9. Asedios programados
    c.execute('''CREATE TABLE IF NOT EXISTS asedios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        territorio_id INTEGER,
        gremio_atacante_id INTEGER,
        gremio_defensor_id INTEGER,
        fecha_declaracion TIMESTAMP,
        fecha_batalla TIMESTAMP,
        estado TEXT DEFAULT 'pendiente',  -- 'pendiente', 'en_curso', 'finalizado'
        ganador_id INTEGER
    )''')

    # 10. Mazmorras predefinidas (catálogo)
    c.execute('''CREATE TABLE IF NOT EXISTS mazmorras (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL,
        tier INTEGER DEFAULT 1,
        dificultad_base INTEGER DEFAULT 1,
        jefe_id INTEGER,
        recompensa_xp INTEGER,
        recompensa_oro INTEGER
    )''')

    # 11. Partys (grupos temporales)
    c.execute('''CREATE TABLE IF NOT EXISTS partys (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        lider_id INTEGER NOT NULL,
        tamanio_max INTEGER DEFAULT 5,
        mazmorra_id INTEGER,
        estado TEXT DEFAULT 'formando',  -- 'formando', 'dentro_mazmorra', 'completada', 'disuelta'
        fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        fecha_entrada TIMESTAMP,
        miembros TEXT DEFAULT '[]'  -- JSON lista de user_ids (alternativa a tabla separada)
    )''')

    # 12. Progreso de grupo dentro de una mazmorra
    c.execute('''CREATE TABLE IF NOT EXISTS progreso_mazmorra (
        party_id INTEGER PRIMARY KEY,
        sala_actual INTEGER DEFAULT 1,
        enemigos_restantes TEXT DEFAULT '[]',
        jefe_vivo INTEGER DEFAULT 1
    )''')

    # 13. Clima actual del mundo (una sola fila)
    c.execute('''CREATE TABLE IF NOT EXISTS clima_actual (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        tipo_clima TEXT DEFAULT 'Soleado',
        inicio TIMESTAMP,
        fin TIMESTAMP,
        efecto_activo TEXT DEFAULT 'normal'
    )''')
    # Insertar clima inicial si no existe
    c.execute('INSERT OR IGNORE INTO clima_actual (id, tipo_clima, inicio, fin) VALUES (1, "Soleado", datetime("now"), datetime("now", "+1 hour"))')

    # 14. Eventos activos
    c.execute('''CREATE TABLE IF NOT EXISTS eventos_activos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        evento_id TEXT,
        nombre TEXT,
        efecto TEXT,
        valor REAL,
        fecha_inicio TIMESTAMP,
        fecha_fin TIMESTAMP
    )''')

    # 15. Catálogo de logros (maestra)
    c.execute('''CREATE TABLE IF NOT EXISTS logros (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT UNIQUE,
        descripcion TEXT,
        requisito_tipo TEXT,  -- 'recolectar', 'matar', 'pescar', 'reputacion', 'nivel', etc.
        requisito_cantidad INTEGER,
        recompensa_tipo TEXT,  -- 'oro', 'eternium', 'xp', 'titulo'
        recompensa_valor INTEGER
    )''')

    # 16. Mascotas del jugador
    c.execute('''CREATE TABLE IF NOT EXISTS mascotas_jugador (
        jugador_id INTEGER,
        mascota_id INTEGER,
        nivel INTEGER DEFAULT 1,
        experiencia INTEGER DEFAULT 0,
        activa BOOLEAN DEFAULT 0,
        PRIMARY KEY (jugador_id, mascota_id)
    )''')

    # 17. Monturas del jugador
    c.execute('''CREATE TABLE IF NOT EXISTS monturas_jugador (
        jugador_id INTEGER,
        montura_id INTEGER,
        nivel INTEGER DEFAULT 1,
        experiencia INTEGER DEFAULT 0,
        activa BOOLEAN DEFAULT 0,
        PRIMARY KEY (jugador_id, montura_id)
    )''')

    # 18. Recetas de crafteo desbloqueadas por el jugador
    c.execute('''CREATE TABLE IF NOT EXISTS recetas_desbloqueadas (
        jugador_id INTEGER,
        receta_id INTEGER,
        PRIMARY KEY (jugador_id, receta_id)
    )''')

    # 19. Subastas (mercado) — esquema unificado con subastas.py
    c.execute('''CREATE TABLE IF NOT EXISTS subastas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        vendedor_id INTEGER,
        objeto_nombre TEXT,
        cantidad INTEGER,
        moneda TEXT DEFAULT 'oro',
        precio_inicial INTEGER,
        precio_actual INTEGER,
        puja_maxima_id INTEGER DEFAULT 0,
        fecha_inicio TIMESTAMP,
        fecha_fin TIMESTAMP,
        activa BOOLEAN DEFAULT 1
    )''')

    # 20. Notificaciones pendientes
    c.execute('''CREATE TABLE IF NOT EXISTS notificaciones (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        jugador_id INTEGER,
        mensaje TEXT,
        leida BOOLEAN DEFAULT 0,
        fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # 21. Cooldowns de teletransporte
    c.execute('''CREATE TABLE IF NOT EXISTS teletransporte_cooldown (
        jugador_id INTEGER PRIMARY KEY,
        ultimo_uso TIMESTAMP
    )''')

    # 22. Configuración global del bot
    c.execute('''CREATE TABLE IF NOT EXISTS config_bot (
        clave   TEXT PRIMARY KEY,
        valor   TEXT NOT NULL
    )''')
    c.execute("INSERT OR IGNORE INTO config_bot (clave, valor) VALUES ('faccion_libre', '1')")
    c.execute("INSERT OR IGNORE INTO config_bot (clave, valor) VALUES ('recluta_bonus_stamina', '5')")
    c.execute("INSERT OR IGNORE INTO config_bot (clave, valor) VALUES ('recluta_nivel_activacion', '15')")

    # 23. Overrides de stats para items (armas/armaduras)
    c.execute('''CREATE TABLE IF NOT EXISTS stats_overrides_items (
        item_id TEXT NOT NULL,
        stat    TEXT NOT NULL,
        valor   TEXT NOT NULL,
        PRIMARY KEY (item_id, stat)
    )''')

    # 24. Overrides de stats para monstruos
    c.execute('''CREATE TABLE IF NOT EXISTS stats_overrides_monstruos (
        monstruo_id TEXT NOT NULL,
        stat        TEXT NOT NULL,
        valor       TEXT NOT NULL,
        PRIMARY KEY (monstruo_id, stat)
    )''')

    # 25. Overrides de precios de tienda
    c.execute('''CREATE TABLE IF NOT EXISTS stats_overrides_precios (
        item_id TEXT NOT NULL,
        moneda  TEXT NOT NULL,
        valor   INTEGER NOT NULL,
        PRIMARY KEY (item_id, moneda)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS premios_pendientes (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        evento_tipo   TEXT    NOT NULL,
        evento_desc   TEXT    NOT NULL,
        ganadores_json TEXT   NOT NULL,
        estado        TEXT    DEFAULT 'pendiente',
        fecha         TEXT    NOT NULL
    )''')

    # ==================== ÍNDICES para rendimiento ====================
    c.execute('CREATE INDEX IF NOT EXISTS idx_jugadores_faccion ON jugadores(faccion)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_miembros_gremio_gremio ON miembros_gremio(gremio_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_subastas_activa ON subastas(activa)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_notificaciones_no_leidas ON notificaciones(jugador_id, leida)')

    # Migraciones: añadir columnas nuevas a tablas existentes (seguro si ya existen)
    migraciones = [
        "ALTER TABLE ofertas_p2p ADD COLUMN fecha_expiracion TIMESTAMP",
    ]
    for sql in migraciones:
        try:
            c.execute(sql)
        except Exception:
            pass  # columna ya existe

    conn.commit()
    conn.close()

# ==================== FUNCIONES DE JUGADORES ====================
def existe_jugador(user_id: int) -> bool:
    conn = _get_conn()
    c = conn.cursor()
    c.execute('SELECT 1 FROM jugadores WHERE user_id = ?', (user_id,))
    existe = c.fetchone() is not None
    conn.close()
    return existe

def crear_jugador(user_id: int, nombre: str, clase: str, faccion: str) -> bool:
    if existe_jugador(user_id):
        return False
    conn = _get_conn()
    c = conn.cursor()
    from clases import obtener_stats_iniciales
    hp_max = obtener_stats_iniciales(clase)["vida_max"]
    # Generar código de invitación único
    codigo = generar_codigo_invitacion()
    while True:
        c.execute('SELECT 1 FROM jugadores WHERE codigo_invitacion = ?', (codigo,))
        if c.fetchone() is None:
            break
        codigo = generar_codigo_invitacion()
    _FACCION_CIUDAD = {
        "Alianza":   {"nombre": "Ciudadela Alianza",   "id": 1,  "faccion_id": 1},
        "Imperio":   {"nombre": "Ciudadela Imperio",   "id": 12, "faccion_id": 2},
        "Sindicato": {"nombre": "Ciudadela Sindicato", "id": 23, "faccion_id": 3},
    }
    ciudad = _FACCION_CIUDAD.get(faccion, {"nombre": "Ciudadela Alianza", "id": 1, "faccion_id": 1})
    c.execute('''INSERT INTO jugadores
        (user_id, nombre_personaje, clase, faccion, faccion_id, hp_actual, hp_max, zona_actual, zona_actual_id, ubicacion, codigo_invitacion)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
        (user_id, nombre, clase, faccion, ciudad["faccion_id"], hp_max, hp_max,
         ciudad["nombre"], ciudad["id"], "ciudad", codigo))
    conn.commit()
    conn.close()
    return True

def obtener_jugador(user_id: int) -> Optional[Dict]:
    # MEJORA RENDIMIENTO: usar cache TTL=10s cuando esté disponible
    if _PERF_DISPONIBLE:
        return obtener_jugador_cached(user_id)
    conn = _get_conn()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM jugadores WHERE user_id = ?', (user_id,))
    row = c.fetchone()
    conn.close()
    if row is None:
        return None
    return dict(row)

def actualizar_jugador(user_id: int, **kwargs):
    # MEJORA RENDIMIENTO: invalidar cache automáticamente al actualizar
    if _PERF_DISPONIBLE:
        actualizar_jugador_con_invalidacion(user_id, **kwargs)
        return
    conn = _get_conn()
    c = conn.cursor()
    campos = ", ".join([f"{k} = ?" for k in kwargs])
    valores = list(kwargs.values()) + [user_id]
    c.execute(f'UPDATE jugadores SET {campos} WHERE user_id = ?', valores)
    conn.commit()
    conn.close()

# ── Funciones atómicas de monedas/stats (MEJORA RENDIMIENTO) ──────────────────

def sumar_oro(user_id: int, cantidad: int) -> int:
    """Suma oro de forma atómica (evita race conditions). Nunca baja de 0."""
    if _PERF_DISPONIBLE:
        return sumar_oro_atomico(user_id, cantidad)
    jug = obtener_jugador(user_id)
    if jug:
        nuevo = max(0, jug.get("oro", 0) + cantidad)
        actualizar_jugador(user_id, oro=nuevo)
        return nuevo
    return 0

def restar_oro(user_id: int, cantidad: int) -> int:
    """Resta oro de forma atómica. Nunca baja de 0."""
    return sumar_oro(user_id, -cantidad)

def sumar_xp(user_id: int, cantidad: int) -> int:
    """Suma experiencia de forma atómica."""
    if _PERF_DISPONIBLE:
        return sumar_xp_atomico(user_id, cantidad)
    jug = obtener_jugador(user_id)
    if jug:
        nuevo = max(0, jug.get("experiencia", 0) + cantidad)
        actualizar_jugador(user_id, experiencia=nuevo)
        return nuevo
    return 0

def sumar_eternium(user_id: int, cantidad: int) -> int:
    """Suma eternium de forma atómica. Nunca baja de 0."""
    if _PERF_DISPONIBLE:
        return sumar_eternium_atomico(user_id, cantidad)
    jug = obtener_jugador(user_id)
    if jug:
        nuevo = max(0, jug.get("eternium", 0) + cantidad)
        actualizar_jugador(user_id, eternium=nuevo)
        return nuevo
    return 0

def restar_eternium(user_id: int, cantidad: int) -> int:
    """Resta eternium de forma atómica. Nunca baja de 0."""
    return sumar_eternium(user_id, -cantidad)

def obtener_todos_jugadores() -> List[Dict]:
    """
    Devuelve una lista de diccionarios con todos los jugadores registrados.
    Cada diccionario contiene al menos: user_id, nombre_personaje, zona_actual.
    Es utilizada por el sistema de caza para notificar eventos.
    """
    conn = _get_conn()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT user_id, nombre_personaje, zona_actual FROM jugadores')
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def registrar_actividad(user_id: int):
    """Actualiza la marca de tiempo de última interacción del jugador."""
    conn = _get_conn()
    c = conn.cursor()
    c.execute(
        "UPDATE jugadores SET ultima_interaccion = ? WHERE user_id = ?",
        (datetime.now().isoformat(), user_id)
    )
    conn.commit()
    conn.close()


def obtener_jugadores_activos(ventana_segundos: int = 600) -> List[Dict]:
    """
    Retorna jugadores que han interactuado en los últimos `ventana_segundos` segundos.
    Solo devuelve user_id y nombre_personaje.
    """
    desde = (datetime.now() - timedelta(seconds=ventana_segundos)).isoformat()
    conn = _get_conn()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(
        "SELECT user_id, nombre_personaje FROM jugadores "
        "WHERE ultima_interaccion > ?",
        (desde,)
    )
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

# ==================== MARCADO ====================
def esta_marcado(user_id: int) -> bool:
    try:
        from modo_debug import esta_en_debug
        if esta_en_debug(user_id):
            return False
    except Exception:
        pass
    jug = obtener_jugador(user_id)
    if not jug or not jug.get("estado_marcado", 0):
        return False
    expiracion = jug.get("marca_expiracion")
    if expiracion and datetime.now() < datetime.fromisoformat(expiracion):
        return True
    actualizar_jugador(user_id, estado_marcado=0, marca_expiracion=None)
    return False

def marcar_jugador(user_id: int, duracion_segundos: int = 3600) -> bool:
    """Marca al jugador por un tiempo (por defecto 1 hora). Retorna True si se marcó."""
    expiracion = datetime.now() + timedelta(seconds=duracion_segundos)
    actualizar_jugador(user_id, estado_marcado=1, marca_expiracion=expiracion.isoformat())
    return True

def desmarcar_jugador(user_id: int) -> bool:
    actualizar_jugador(user_id, estado_marcado=0, marca_expiracion=None)
    return True

# ==================== INVENTARIO ====================
def obtener_inventario(user_id: int) -> List[Dict]:
    jug = obtener_jugador(user_id)
    if not jug:
        return []
    return json.loads(jug["inventario"])

def guardar_inventario(user_id: int, inventario: List[Dict]):
    actualizar_jugador(user_id, inventario=json.dumps(inventario))

def agregar_item(user_id: int, item_nombre: str, cantidad: int = 1) -> bool:
    # MEJORA RENDIMIENTO: versión thread-safe con lock por usuario
    if _PERF_DISPONIBLE:
        return agregar_item_seguro(user_id, item_nombre, cantidad)
    # Fallback sin lock
    try:
        from materiales import resolver_nombre as _rn
        item_nombre = _rn(item_nombre)
    except Exception:
        pass
    inv = obtener_inventario(user_id)
    for item in inv:
        if item["nombre"] == item_nombre:
            item["cantidad"] += cantidad
            break
    else:
        inv.append({"nombre": item_nombre, "cantidad": cantidad})
    guardar_inventario(user_id, inv)
    return True

def quitar_item(user_id: int, item_nombre: str, cantidad: int = 1) -> bool:
    # MEJORA RENDIMIENTO: versión thread-safe con lock por usuario
    if _PERF_DISPONIBLE:
        return quitar_item_seguro(user_id, item_nombre, cantidad)
    # Fallback sin lock
    inv = obtener_inventario(user_id)
    for i, item in enumerate(inv):
        if item["nombre"] == item_nombre:
            if item["cantidad"] >= cantidad:
                item["cantidad"] -= cantidad
                if item["cantidad"] == 0:
                    inv.pop(i)
                guardar_inventario(user_id, inv)
                return True
            else:
                return False
    return False

# ==================== REPUTACIÓN ====================
def obtener_reputacion(user_id: int) -> int:
    jug = obtener_jugador(user_id)
    return jug["reputacion"] if jug else 0

def sumar_reputacion(user_id: int, puntos: int):
    # MEJORA RENDIMIENTO: operación atómica
    if _PERF_DISPONIBLE:
        sumar_reputacion_atomica(user_id, puntos)
        return
    actual = obtener_reputacion(user_id)
    actualizar_jugador(user_id, reputacion=actual + puntos)

def restar_reputacion(user_id: int, puntos: int):
    sumar_reputacion(user_id, -puntos)

# ==================== MISIONES ====================
def obtener_misiones_activas(user_id: int) -> List[Dict]:
    jug = obtener_jugador(user_id)
    if not jug:
        return []
    return json.loads(jug["misiones_activas"])

def guardar_misiones_activas(user_id: int, misiones: List[Dict]):
    actualizar_jugador(user_id, misiones_activas=json.dumps(misiones))

def actualizar_progreso_mision(user_id: int, mision_id: str, avance: int = 1):
    misiones = obtener_misiones_activas(user_id)
    for m in misiones:
        if m["id"] == mision_id:
            m["progreso"] = min(m["progreso"] + avance, m["objetivo"])
            if m["progreso"] >= m["objetivo"]:
                m["completada"] = True
            break
    guardar_misiones_activas(user_id, misiones)

def completar_mision(user_id: int, mision_id: str) -> Dict:
    misiones = obtener_misiones_activas(user_id)
    for m in misiones:
        if m["id"] == mision_id and m.get("completada") and not m.get("reclamada"):
            m["reclamada"] = True
            guardar_misiones_activas(user_id, misiones)
            return m["recompensa"]
    return {}

def reiniciar_misiones_diarias():
    pass

# ==================== PARTYS ====================
def crear_party(lider_id: int, tamanio_max: int = 5, mazmorra_id: int = None) -> int:
    conn = _get_conn()
    c = conn.cursor()
    c.execute('''INSERT INTO partys (lider_id, tamanio_max, mazmorra_id, miembros)
                 VALUES (?, ?, ?, ?)''', (lider_id, tamanio_max, mazmorra_id, json.dumps([lider_id])))
    party_id = c.lastrowid
    conn.commit()
    conn.close()
    return party_id

def invitar_a_party(party_id: int, invitado_id: int):
    conn = _get_conn()
    c = conn.cursor()
    c.execute('SELECT miembros FROM partys WHERE id = ?', (party_id,))
    row = c.fetchone()
    if row:
        miembros = json.loads(row[0])
        if invitado_id not in miembros:
            miembros.append(invitado_id)
            c.execute('UPDATE partys SET miembros = ? WHERE id = ?', (json.dumps(miembros), party_id))
            conn.commit()
    conn.close()

def aceptar_invitacion(party_id: int, jugador_id: int):
    pass

def salir_de_party(party_id: int, jugador_id: int):
    conn = _get_conn()
    c = conn.cursor()
    c.execute('SELECT miembros, lider_id FROM partys WHERE id = ?', (party_id,))
    row = c.fetchone()
    if row:
        miembros = json.loads(row[0])
        lider = row[1]
        if jugador_id in miembros:
            miembros.remove(jugador_id)
            if jugador_id == lider and miembros:
                nuevo_lider = miembros[0]
                c.execute('UPDATE partys SET lider_id = ?, miembros = ? WHERE id = ?', (nuevo_lider, json.dumps(miembros), party_id))
            else:
                c.execute('UPDATE partys SET miembros = ? WHERE id = ?', (json.dumps(miembros), party_id))
            conn.commit()
    conn.close()

def eliminar_party(party_id: int):
    conn = _get_conn()
    c = conn.cursor()
    c.execute('DELETE FROM partys WHERE id = ?', (party_id,))
    c.execute('DELETE FROM progreso_mazmorra WHERE party_id = ?', (party_id,))
    conn.commit()
    conn.close()

# ==================== EVENTOS ====================
def obtener_evento_activo() -> Optional[Dict]:
    conn = _get_conn()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    ahora = datetime.now().isoformat()
    c.execute('SELECT * FROM eventos_activos WHERE fecha_inicio <= ? AND fecha_fin >= ?', (ahora, ahora))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def registrar_evento(evento_id: str, nombre: str, efecto: str, valor: float, horas_duracion: int):
    conn = _get_conn()
    c = conn.cursor()
    inicio = datetime.now()
    fin = inicio + timedelta(hours=horas_duracion)
    c.execute('''INSERT INTO eventos_activos (evento_id, nombre, efecto, valor, fecha_inicio, fecha_fin)
                 VALUES (?, ?, ?, ?, ?, ?)''', (evento_id, nombre, efecto, valor, inicio.isoformat(), fin.isoformat()))
    conn.commit()
    conn.close()

# ==================== TELEPORTE Y CAMBIO DE FACCION ====================
def registrar_teletransporte(user_id: int):
    conn = _get_conn()
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO teletransporte_cooldown (jugador_id, ultimo_uso) VALUES (?, ?)',
              (user_id, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def puede_teletransportarse(user_id: int, cooldown_minutos: int = 60) -> bool:
    conn = _get_conn()
    c = conn.cursor()
    c.execute('SELECT ultimo_uso FROM teletransporte_cooldown WHERE jugador_id = ?', (user_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        return True
    ultimo = datetime.fromisoformat(row[0])
    return datetime.now() >= ultimo + timedelta(minutes=cooldown_minutos)

def registrar_cambio_faccion(user_id: int, nueva_faccion: str):
    actualizar_jugador(user_id, faccion=nueva_faccion, ultimo_cambio_faccion=datetime.now().isoformat())

def puede_cambiar_faccion(user_id: int) -> bool:
    jug = obtener_jugador(user_id)
    if not jug or jug["ultimo_cambio_faccion"] is None:
        return True
    ultimo = datetime.fromisoformat(jug["ultimo_cambio_faccion"])
    return datetime.now() >= ultimo + timedelta(days=30)

# ==================== NIVEL 100, SUBCLASE Y REENCARNACIÓN ====================
def alcanzo_nivel_100(user_id: int) -> bool:
    jug = obtener_jugador(user_id)
    return jug and jug["nivel"] >= 100

def avanzar_subclase(user_id: int, subclase: str):
    actualizar_jugador(user_id, subclase=subclase)

def reencarnar_con_bonificadores(user_id: int, nueva_clase: str = None):
    jug = obtener_jugador(user_id)
    if not jug or jug["nivel"] < 100:
        return False
    reenc = jug["reencarnaciones"] + 1
    nuevos_datos = {
        "nivel": 1,
        "experiencia": 0,
        "reencarnaciones": reenc,
        "hp_actual": 100,
        "hp_max": 100,
    }
    if nueva_clase:
        nuevos_datos["clase"] = nueva_clase
    actualizar_jugador(user_id, **nuevos_datos)
    return True

def obtener_bonificacion_reencarnacion(user_id: int) -> float:
    jug = obtener_jugador(user_id)
    if not jug:
        return 1.0
    return 1.0 + (jug["reencarnaciones"] * 0.05)


# ==================== CONFIG BOT ====================
def obtener_config(clave: str, defecto: str = "") -> str:
    conn = _get_conn()
    c = conn.cursor()
    c.execute("SELECT valor FROM config_bot WHERE clave = ?", (clave,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else defecto

def establecer_config(clave: str, valor: str):
    conn = _get_conn()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO config_bot (clave, valor) VALUES (?, ?)", (clave, valor))
    conn.commit()
    conn.close()

def faccion_libre() -> bool:
    """True si los jugadores pueden elegir su facción al registrarse."""
    return obtener_config("faccion_libre", "1") == "1"

# ==================== LOGROS ====================
def obtener_logros_desbloqueados(user_id: int) -> List[int]:
    jug = obtener_jugador(user_id)
    if not jug:
        return []
    return json.loads(jug["logros_desbloqueados"])

def desbloquear_logro(user_id: int, logro_id: int):
    logros = obtener_logros_desbloqueados(user_id)
    if logro_id not in logros:
        logros.append(logro_id)
        actualizar_jugador(user_id, logros_desbloqueados=json.dumps(logros))

# ==================== NOTIFICACIONES ====================
def agregar_notificacion(user_id: int, mensaje: str):
    conn = _get_conn()
    c = conn.cursor()
    c.execute('INSERT INTO notificaciones (jugador_id, mensaje) VALUES (?, ?)', (user_id, mensaje))
    conn.commit()
    conn.close()

def obtener_notificaciones_no_leidas(user_id: int) -> List[Dict]:
    conn = _get_conn()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT id, mensaje, fecha_creacion FROM notificaciones WHERE jugador_id = ? AND leida = 0', (user_id,))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def marcar_notificacion_leida(notif_id: int):
    conn = _get_conn()
    c = conn.cursor()
    c.execute('UPDATE notificaciones SET leida = 1 WHERE id = ?', (notif_id,))
    conn.commit()
    conn.close()

# ==================== ACTIVIDAD / ESTADO OCUPADO ====================

def set_actividad(user_id: int, actividad):
    """
    Registra la actividad actual del jugador.
    actividad puede ser: None, "recoleccion", "combate", "mazmorra", "investigacion", "viaje"
    """
    from datetime import datetime as _dt, timedelta as _td
    _duraciones = {
        "recoleccion":  _td(minutes=5),
        "combate":      _td(minutes=20),
        "investigacion":_td(minutes=35),
        "mazmorra":     _td(hours=2),
        "viaje":        _td(hours=24),
    }
    expira = None
    if actividad and actividad in _duraciones:
        expira = (_dt.now() + _duraciones[actividad]).isoformat()
    conn = _get_conn()
    c = conn.cursor()
    c.execute(
        'UPDATE jugadores SET actividad_actual = ?, actividad_expira = ? WHERE user_id = ?',
        (actividad, expira, user_id)
    )
    conn.commit()
    conn.close()

def get_actividad(user_id: int):
    """Devuelve la actividad actual del jugador o None si está libre."""
    jug = obtener_jugador(user_id)
    if not jug:
        return None
    return jug.get("actividad_actual")

def es_ocupado(user_id: int) -> bool:
    """
    Devuelve True si el jugador está realizando una actividad activa
    (recolección, combate, mazmorra, investigación o viaje en curso).
    Auto-limpia estados caducados para evitar bloqueos permanentes.
    """
    try:
        from modo_debug import esta_en_debug
        if esta_en_debug(user_id):
            return False  # Debug: nunca ocupado, todo disponible
    except Exception:
        pass
    from datetime import datetime as _dt
    jug = obtener_jugador(user_id)
    if not jug:
        return False
    actividad = jug.get("actividad_actual")
    if actividad:
        # Comprobar expiración
        expira_str = jug.get("actividad_expira")
        if expira_str:
            try:
                if _dt.fromisoformat(expira_str) <= _dt.now():
                    # Actividad caducada → limpiar automáticamente
                    conn = _get_conn()
                    c = conn.cursor()
                    c.execute(
                        'UPDATE jugadores SET actividad_actual = NULL, actividad_expira = NULL WHERE user_id = ?',
                        (user_id,)
                    )
                    conn.commit()
                    conn.close()
                    actividad = None
            except Exception:
                pass
        else:
            # actividad_expira es NULL pero actividad_actual está puesta → estado residual, limpiar
            try:
                conn = _get_conn()
                c = conn.cursor()
                c.execute(
                    'UPDATE jugadores SET actividad_actual = NULL, actividad_expira = NULL WHERE user_id = ?',
                    (user_id,)
                )
                conn.commit()
                conn.close()
            except Exception:
                pass
            actividad = None
        if actividad:
            return True
    # Comprobación adicional: viaje por timestamp
    viaje_hasta = jug.get("viaje_hasta")
    if viaje_hasta:
        try:
            if _dt.fromisoformat(viaje_hasta) > _dt.now():
                return True
        except Exception:
            pass
    # Comprobación adicional: mazmorra activa en DB
    try:
        conn = _get_conn()
        c = conn.cursor()
        c.execute(
            "SELECT mazmorra_id, fecha_creacion FROM mazmorras_activas "
            "WHERE jugadores LIKE ? AND estado IN ('formando','en_curso') LIMIT 1",
            (f'%{user_id}%',)
        )
        row_maz = c.fetchone()
        conn.close()
        if row_maz:
            maz_id, fecha_str = row_maz
            try:
                edad = (_dt.now() - _dt.fromisoformat(fecha_str)).total_seconds()
            except Exception:
                edad = 0
            if edad > 7200:  # más de 2 horas → limpiar
                conn2 = _get_conn()
                c2 = conn2.cursor()
                c2.execute('DELETE FROM mazmorras_activas WHERE mazmorra_id = ?', (maz_id,))
                conn2.commit()
                conn2.close()
            else:
                return True
    except Exception:
        pass
    return False

def nombre_actividad(user_id: int) -> str:
    """Devuelve un texto legible con la actividad actual del jugador."""
    actividad = get_actividad(user_id)
    mapa = {
        "recoleccion":  "recolectando materiales",
        "combate":      "en combate",
        "mazmorra":     "en una mazmorra",
        "investigacion":"investigando la zona",
        "viaje":        "viajando",
    }
    if actividad in mapa:
        return mapa[actividad]
    # Fallback: comprobar viaje por timestamp
    jug = obtener_jugador(user_id)
    if jug and jug.get("viaje_hasta"):
        from datetime import datetime as _dt
        try:
            if _dt.fromisoformat(jug["viaje_hasta"]) > _dt.now():
                return "viajando"
        except Exception:
            pass
    return "ocupado"

# ==================== FUNCIONES NUEVAS PARA CRAFTEO Y MONTURAS ====================
def obtener_zona_actual(user_id: int) -> str:
    jug = obtener_jugador(user_id)
    if not jug:
        return "desconocida"
    return jug.get("zona_actual", "azul")

def actualizar_zona(user_id: int, nueva_zona: str):
    actualizar_jugador(user_id, zona_actual=nueva_zona)

def obtener_nivel(user_id: int) -> int:
    jug = obtener_jugador(user_id)
    return jug["nivel"] if jug else 1

def verificar_nivel(user_id: int, nivel_minimo: int = 1) -> bool:
    """Verifica si user_id tiene nivel de admin >= nivel_minimo en la tabla admins."""
    import os as _os
    _SUPERADMIN_ID = int(_os.environ.get("SUPERADMIN_ID", "0"))
    if _SUPERADMIN_ID and user_id == _SUPERADMIN_ID:
        return True
    try:
        conn = _get_conn()
        c = conn.cursor()
        c.execute('SELECT nivel FROM admins WHERE user_id = ?', (user_id,))
        row = c.fetchone()
        conn.close()
        return row is not None and row[0] >= nivel_minimo
    except Exception:
        return False

def obtener_clase(user_id: int) -> Optional[str]:
    jug = obtener_jugador(user_id)
    return jug["clase"] if jug else None

def equipar_montura(user_id: int, montura_id: int):
    conn = _get_conn()
    c = conn.cursor()
    c.execute('UPDATE monturas_jugador SET activa = 0 WHERE jugador_id = ?', (user_id,))
    c.execute('UPDATE monturas_jugador SET activa = 1 WHERE jugador_id = ? AND montura_id = ?', (user_id, montura_id))
    conn.commit()
    conn.close()

def obtener_montura_equipada(user_id: int) -> Optional[Dict]:
    conn = _get_conn()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM monturas_jugador WHERE jugador_id = ? AND activa = 1', (user_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def desbloquear_receta(user_id: int, receta_id: str):
    conn = _get_conn()
    c = conn.cursor()
    c.execute('INSERT OR IGNORE INTO recetas_desbloqueadas (jugador_id, receta_id) VALUES (?, ?)', (user_id, receta_id))
    conn.commit()
    conn.close()

def tiene_receta_desbloqueada(user_id: int, receta_id: str) -> bool:
    conn = _get_conn()
    c = conn.cursor()
    c.execute('SELECT 1 FROM recetas_desbloqueadas WHERE jugador_id = ? AND receta_id = ?', (user_id, receta_id))
    existe = c.fetchone() is not None
    conn.close()
    return existe

# ==================== STAMINA ====================
def obtener_stamina(user_id: int) -> tuple:
    """Retorna (stamina_actual, stamina_maxima, ultima_recarga_timestamp) regenerando automáticamente por tiempo."""
    jug = obtener_jugador(user_id)
    if not jug:
        return 100, 100, None
    actual = jug.get("stamina_actual", 100)
    maxi = jug.get("stamina_maxima", 100)
    ultima = jug.get("ultima_regeneracion_stamina")
    ultima_dt = datetime.fromisoformat(ultima) if ultima else None
    if ultima_dt:
        ahora = datetime.now()
        segundos = (ahora - ultima_dt).total_seconds()
        # Usar constante de configuración (por defecto 180 segundos)
        try:
            from config_balance import STAMINA_REGENERACION_SEGUNDOS
        except ImportError:
            STAMINA_REGENERACION_SEGUNDOS = 180
        regenerado = int(segundos // STAMINA_REGENERACION_SEGUNDOS)
        if regenerado > 0:
            actual = min(maxi, actual + regenerado)
            actualizar_jugador(user_id, stamina_actual=actual, ultima_regeneracion_stamina=ahora.isoformat())
    return actual, maxi, ultima

def gastar_stamina(user_id: int, costo: int) -> bool:
    try:
        from modo_debug import esta_en_debug
        if esta_en_debug(user_id):
            return True  # Debug: stamina ilimitada, nunca se gasta
    except Exception:
        pass
    actual, maxi, _ = obtener_stamina(user_id)
    if actual < costo:
        return False
    nueva = actual - costo
    actualizar_jugador(user_id, stamina_actual=nueva)
    return True

def regenerar_stamina(user_id: int):
    """Fuerza la regeneración manual (suele llamarse a obtener_stamina automáticamente)."""
    obtener_stamina(user_id)

# ==================== INVITACIONES ====================
def generar_codigo_invitacion() -> str:
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

def procesar_invitacion(user_id: int, codigo: str) -> bool:
    conn = _get_conn()
    c = conn.cursor()
    c.execute('SELECT user_id FROM jugadores WHERE codigo_invitacion = ?', (codigo,))
    row = c.fetchone()
    if not row:
        conn.close()
        return False
    reclutador_id = row[0]
    if reclutador_id == user_id:
        conn.close()
        return False
    c.execute('SELECT invitado_por FROM jugadores WHERE user_id = ?', (user_id,))
    _row_inv = c.fetchone()
    if _row_inv is not None and _row_inv[0] is not None:
        conn.close()
        return False
    c.execute('UPDATE jugadores SET invitado_por = ? WHERE user_id = ?', (reclutador_id, user_id))
    try:
        from pociones import POCIONES
        import config_balance
        pocion_id = None
        for pid, pdata in POCIONES.items():
            if pdata.get("nivel_requerido", 1) == 1 and "vida" in pdata.get("nombre", "").lower():
                pocion_id = pdata["nombre"]
                break
        if pocion_id:
            agregar_item(user_id, pocion_id, config_balance.INVITACION_RECLUTA_RECIBE_POCIONES)
    except:
        pass
    conn.commit()
    conn.close()
    return True

def recluta_alcanzo_nivel_15(recluta_id: int):
    """Compatibilidad legacy — redirige a la versión configurable."""
    recluta_alcanzo_nivel_configurado(recluta_id)

def recluta_alcanzo_nivel_configurado(recluta_id: int):
    """Otorga stamina al reclutador cuando el recluta cumple el requisito. Guard anti-doble."""
    conn = _get_conn()
    c = conn.cursor()
    # Verificar que el recluta no haya dado recompensa ya
    c.execute('SELECT invitado_por, recluta_recompensa_dada FROM jugadores WHERE user_id = ?', (recluta_id,))
    row = c.fetchone()
    if not row or not row[0] or row[1]:
        conn.close()
        return
    reclutador = row[0]
    # Marcar como recompensa dada (anti-doble)
    c.execute('UPDATE jugadores SET recluta_recompensa_dada = 1 WHERE user_id = ?', (recluta_id,))
    # Incrementar contador del reclutador
    c.execute('UPDATE jugadores SET reclutas_completados = reclutas_completados + 1 WHERE user_id = ?', (reclutador,))
    c.execute('SELECT reclutas_completados, stamina_maxima FROM jugadores WHERE user_id = ?', (reclutador,))
    row2 = c.fetchone()
    if not row2:
        conn.close()
        return
    completados = row2[0]
    bonus_por_recluta = int(obtener_config("recluta_bonus_stamina", "5"))
    import config_balance
    max_base   = config_balance.STAMINA_MAX_BASE
    max_extra  = config_balance.STAMINA_MAX_EXTRA
    nueva_max  = min(max_base + max_extra, max_base + completados * bonus_por_recluta)
    c.execute('UPDATE jugadores SET stamina_maxima = ? WHERE user_id = ?', (nueva_max, reclutador))
    conn.commit()
    conn.close()

# ==================== LÍMITES DIARIOS DE MAZMORRAS ====================
def _resetear_mazmorras_diarias(user_id: int):
    conn = _get_conn()
    c = conn.cursor()
    c.execute('UPDATE jugadores SET mazmorras_azul_hoy = 0, mazmorras_amarilla_hoy = 0, mazmorras_roja_hoy = 0, mazmorras_negra_hoy = 0, ultimo_reset_mazmorras = ? WHERE user_id = ?',
              (datetime.now().isoformat(), user_id))
    conn.commit()
    conn.close()

def comprobar_limite_mazmorra(user_id: int, color: str) -> bool:
    try:
        from modo_debug import esta_en_debug
        if esta_en_debug(user_id):
            return True  # Debug: límite diario de mazmorras desactivado
    except Exception:
        pass
    conn = _get_conn()
    c = conn.cursor()
    c.execute('SELECT ultimo_reset_mazmorras, mazmorras_azul_hoy, mazmorras_amarilla_hoy, mazmorras_roja_hoy, mazmorras_negra_hoy FROM jugadores WHERE user_id = ?', (user_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return False
    ultimo_reset = row[0]
    if ultimo_reset:
        ultimo = datetime.fromisoformat(ultimo_reset)
        if (datetime.now() - ultimo).days >= 1:
            _resetear_mazmorras_diarias(user_id)
            conn = _get_conn()
            c = conn.cursor()
            c.execute('SELECT mazmorras_azul_hoy, mazmorras_amarilla_hoy, mazmorras_roja_hoy, mazmorras_negra_hoy FROM jugadores WHERE user_id = ?', (user_id,))
            row = c.fetchone()
    col_map = {"azul":0, "amarilla":1, "roja":2, "negra":3}
    usado = row[col_map[color] + 1]  # indice 1..4
    conn.close()
    import config_balance
    return usado < config_balance.MAZMORRAS_LIMITE_DIARIO

def registrar_entrada_mazmorra(user_id: int, color: str):
    conn = _get_conn()
    c = conn.cursor()
    columna = f"mazmorras_{color}_hoy"
    c.execute(f'UPDATE jugadores SET {columna} = {columna} + 1 WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

def obtener_entradas_mazmorra_hoy(user_id: int, color: str) -> int:
    conn = _get_conn()
    c = conn.cursor()
    columna = f"mazmorras_{color}_hoy"
    c.execute(f'SELECT {columna} FROM jugadores WHERE user_id = ?', (user_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0

# ==================== SISTEMA DE PAZ (INMUNIDAD PvP) ====================
# Nota: Las tablas de paz NO se crean aquí para evitar conflictos.
# Se crearán desde los módulos de investigación.

# ==================== FUNCIONES PARA CONTAR JUGADORES POR FACCION ====================
def contar_jugadores_por_faccion() -> Dict[str, int]:
    conn = _get_conn()
    c = conn.cursor()
    c.execute('SELECT faccion, COUNT(*) FROM jugadores GROUP BY faccion')
    rows = c.fetchall()
    conn.close()
    resultado = {}
    for faccion, cuenta in rows:
        resultado[faccion] = cuenta
    for fac in ["Alianza", "Imperio", "Sindicato"]:
        if fac not in resultado:
            resultado[fac] = 0
    return resultado

def obtener_faccion_menos_poblada() -> str:
    conteo = contar_jugadores_por_faccion()
    min_cuenta = min(conteo.values())
    candidatas = [f for f, c in conteo.items() if c == min_cuenta]
    return random.choice(candidatas)
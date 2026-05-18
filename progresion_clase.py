#!/usr/bin/env python3
# progresion_clase.py
# Módulo de progresión a largo plazo: talentos, hitos, insignias, misiones de clase,
# paragon, gloria, reset de talentos, antigüedad, maestría de subclase, cofres de legado,
# récords personales y prestigio.

import sqlite3
import json
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any

import db_helper
import clases

DB_PATH = "aethelgard.db"

# ==================== CONSTANTES ====================
PUNTOS_TALENTO_POR_NIVEL = 20  # hasta nivel 100: 1 cada 5 niveles → 20 puntos
COSTO_RESETEO_ETERNIUM = 50
COSTO_RESETEO_CREDITOS = 10
XP_POR_PUNTO_PARAGONE = 10000   # 10.000 XP extra después de nivel 100 = 1 punto
MAX_PUNTOS_PARAGON = 100
GLORIA_POR_TITULO = 1000
COOLDOWN_MISION_SEMANAL_DIAS = 7
TIEMPO_HORAS_X_PUNTO_VETERANO = 10
PUNTOS_VETERANO_MAX_ANUAL = 12
PRESTIGIO_BONO_PASIVA_POR_PRESTIGIO = 0.02  # 2% acumulativo, máx 50% (25 prestigios)

# ==================== TABLAS (se crean en db_helper.init_db, pero aseguramos) ====================
def _crear_tablas_si_no_existen():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Talentos del jugador
    c.execute('''CREATE TABLE IF NOT EXISTS talentos_jugador (
        jugador_id INTEGER,
        talento_id TEXT,
        nivel INTEGER DEFAULT 1,
        PRIMARY KEY (jugador_id, talento_id)
    )''')
    # Hitos reclamados
    c.execute('''CREATE TABLE IF NOT EXISTS hitos_reclamados (
        jugador_id INTEGER,
        nivel_hito INTEGER,
        PRIMARY KEY (jugador_id, nivel_hito)
    )''')
    # Insignias desbloqueadas
    c.execute('''CREATE TABLE IF NOT EXISTS insignias (
        jugador_id INTEGER,
        insignia_id TEXT,
        PRIMARY KEY (jugador_id, insignia_id)
    )''')
    # Misión semanal activa
    c.execute('''CREATE TABLE IF NOT EXISTS mision_semanal (
        jugador_id INTEGER PRIMARY KEY,
        mision_id TEXT,
        objetivo_tipo TEXT,
        objetivo_cantidad INTEGER,
        progreso INTEGER DEFAULT 0,
        recompensa TEXT,
        fecha_inicio TIMESTAMP,
        fecha_fin TIMESTAMP
    )''')
    # Misión legendaria (etapas)
    c.execute('''CREATE TABLE IF NOT EXISTS mision_legendaria (
        jugador_id INTEGER PRIMARY KEY,
        etapa INTEGER DEFAULT 1,
        progreso INTEGER DEFAULT 0,
        completada BOOLEAN DEFAULT 0
    )''')
    # Puntos Paragon
    c.execute('''CREATE TABLE IF NOT EXISTS paragon (
        jugador_id INTEGER PRIMARY KEY,
        puntos INTEGER DEFAULT 0,
        distribuido_en TEXT DEFAULT '{}'  -- JSON con mejoras elegidas
    )''')
    # Gloria acumulada
    c.execute('''CREATE TABLE IF NOT EXISTS gloria (
        jugador_id INTEGER PRIMARY KEY,
        total_gloria INTEGER DEFAULT 0,
        titulos_desbloqueados TEXT DEFAULT '[]'
    )''')
    # Antigüedad (tiempo jugado por mes)
    c.execute('''CREATE TABLE IF NOT EXISTS antiguedad (
        jugador_id INTEGER PRIMARY KEY,
        minutos_mes_actual INTEGER DEFAULT 0,
        ultimo_registro TIMESTAMP,
        puntos_veterano INTEGER DEFAULT 0,
        puntos_veterano_usados INTEGER DEFAULT 0,
        ultimo_canje_talento_extra BOOLEAN DEFAULT 0
    )''')
    # Maestría de subclase (nivel)
    c.execute('''CREATE TABLE IF NOT EXISTS maestria_subclase (
        jugador_id INTEGER PRIMARY KEY,
        nivel INTEGER DEFAULT 1,
        xp INTEGER DEFAULT 0
    )''')
    # Cofres de legado reclamados
    c.execute('''CREATE TABLE IF NOT EXISTS cofres_legado (
        jugador_id INTEGER PRIMARY KEY,
        ultimo_cofre_puntos INTEGER DEFAULT 0
    )''')
    # Récords personales
    c.execute('''CREATE TABLE IF NOT EXISTS records (
        jugador_id INTEGER,
        record_id TEXT,
        valor INTEGER,
        fecha TIMESTAMP,
        PRIMARY KEY (jugador_id, record_id)
    )''')
    # Prestigio
    c.execute('''CREATE TABLE IF NOT EXISTS prestigio (
        jugador_id INTEGER PRIMARY KEY,
        nivel INTEGER DEFAULT 0
    )''')
    conn.commit()
    conn.close()

# ==================== 1. ÁRBOL DE TALENTOS ====================
# Ramas genéricas (todas las clases) + ramas exclusivas por clase
RAMAS_GENERICAS = ["ofensiva", "defensiva", "utilidad"]
RAMAS_CLASE_ESPECIFICA = {"vanguardista", "acechante", "tejehechizos", "maestro_caza"}

TALENTOS = {
    # ---- RAMAS GENÉRICAS ----
    "ofensiva": [
        {"id": "daño_1",           "nombre": "Fuerza Bruta",      "efecto": "daño",            "valor_por_nivel": 1, "max_nivel": 5, "descripcion": "+1% daño por nivel"},
        {"id": "critico_1",        "nombre": "Precisión Mortal",  "efecto": "critico",          "valor_por_nivel": 1, "max_nivel": 5, "descripcion": "+1 prob. crítico por nivel"},
        {"id": "velocidad_ataque", "nombre": "Rapidez",           "efecto": "velocidad_ataque", "valor_por_nivel": 1, "max_nivel": 5, "descripcion": "+1 velocidad de ataque por nivel"},
    ],
    "defensiva": [
        {"id": "vida_1",       "nombre": "Corazón Firme", "efecto": "vida",         "valor_por_nivel": 1, "max_nivel": 5, "descripcion": "+1% vida máxima por nivel"},
        {"id": "defensa_1",    "nombre": "Piel de Hierro","efecto": "defensa",      "valor_por_nivel": 1, "max_nivel": 5, "descripcion": "+1% defensa por nivel"},
        {"id": "regeneracion", "nombre": "Regeneración",  "efecto": "regeneracion", "valor_por_nivel": 1, "max_nivel": 5, "descripcion": "+1 HP regenerado/turno por nivel"},
    ],
    "utilidad": [
        {"id": "carga_1",       "nombre": "Mochila Grande",     "efecto": "carga",                 "valor_por_nivel": 1, "max_nivel": 5, "descripcion": "+1 capacidad de carga por nivel"},
        {"id": "recoleccion_1", "nombre": "Eficiencia",         "efecto": "recoleccion_velocidad", "valor_por_nivel": 1, "max_nivel": 5, "descripcion": "+1% velocidad de recolección por nivel"},
        {"id": "xp_extra",      "nombre": "Aprendizaje Rápido", "efecto": "xp_extra",              "valor_por_nivel": 1, "max_nivel": 5, "descripcion": "+1% XP extra por nivel"},
    ],
    # ---- RAMA EXCLUSIVA: VANGUARDISTA ----
    "vanguardista": [
        {"id": "vg_escudo",       "nombre": "Escudo Férreo",       "efecto": "defensa",        "valor_por_nivel": 1, "max_nivel": 5, "descripcion": "+1% defensa adicional por nivel"},
        {"id": "vg_vitalidad",    "nombre": "Vitalidad Heroica",   "efecto": "vida",           "valor_por_nivel": 1, "max_nivel": 5, "descripcion": "+1% vida máxima por nivel"},
        {"id": "vg_recuperacion", "nombre": "Recuperación Rápida", "efecto": "regeneracion",   "valor_por_nivel": 1, "max_nivel": 5, "descripcion": "+1 HP regenerado/turno por nivel"},
        {"id": "vg_reduccion",    "nombre": "Piel de Piedra",      "efecto": "reduccion_daño", "valor_por_nivel": 1, "max_nivel": 5, "descripcion": "-1% daño recibido por nivel"},
        {"id": "vg_carga",        "nombre": "Porte Guerrero",      "efecto": "carga",          "valor_por_nivel": 1, "max_nivel": 5, "descripcion": "+1 capacidad de carga por nivel"},
    ],
    # ---- RAMA EXCLUSIVA: ACECHANTE ----
    "acechante": [
        {"id": "ac_filo",        "nombre": "Filo Envenenado", "efecto": "daño",            "valor_por_nivel": 1, "max_nivel": 5, "descripcion": "+1% daño base por nivel"},
        {"id": "ac_evasion",     "nombre": "Paso en Sombras", "efecto": "evasion",         "valor_por_nivel": 1, "max_nivel": 5, "descripcion": "+1% probabilidad de evadir ataques por nivel"},
        {"id": "ac_critico_dmg", "nombre": "Golpe Fatal",     "efecto": "daño_critico",    "valor_por_nivel": 1, "max_nivel": 5, "descripcion": "+1% multiplicador de golpe crítico por nivel"},
        {"id": "ac_saqueo",      "nombre": "Saqueo Experto",  "efecto": "oro_extra",       "valor_por_nivel": 1, "max_nivel": 5, "descripcion": "+1% oro extra al ganar combates por nivel"},
        {"id": "ac_cuchillo",    "nombre": "Cuchillo Ágil",   "efecto": "velocidad_ataque","valor_por_nivel": 1, "max_nivel": 5, "descripcion": "+1 velocidad de ataque por nivel"},
    ],
    # ---- RAMA EXCLUSIVA: TEJEHECHIZOS ----
    "tejehechizos": [
        {"id": "tj_arcano",  "nombre": "Canalización Arcana", "efecto": "daño",              "valor_por_nivel": 1, "max_nivel": 5, "descripcion": "+1% daño mágico por nivel"},
        {"id": "tj_mente",   "nombre": "Mente Ágil",          "efecto": "cooldown_reduccion","valor_por_nivel": 1, "max_nivel": 5, "descripcion": "-1 turno de cooldown de habilidades por nivel"},
        {"id": "tj_saber",   "nombre": "Tomo del Saber",      "efecto": "xp_extra",          "valor_por_nivel": 1, "max_nivel": 5, "descripcion": "+1% XP extra por nivel"},
        {"id": "tj_stamina", "nombre": "Eficiencia Arcana",   "efecto": "stamina_max",       "valor_por_nivel": 1, "max_nivel": 5, "descripcion": "+1 stamina máxima por nivel"},
        {"id": "tj_curacion","nombre": "Canal Vital",         "efecto": "curacion_extra",    "valor_por_nivel": 1, "max_nivel": 5, "descripcion": "+1% eficiencia de curación por nivel"},
    ],
    # ---- RAMA EXCLUSIVA: MAESTRO DE CAZA ----
    "maestro_caza": [
        {"id": "mc_punteria","nombre": "Ojo de Águila",    "efecto": "critico",               "valor_por_nivel": 1, "max_nivel": 5, "descripcion": "+1 probabilidad de crítico por nivel"},
        {"id": "mc_disparo", "nombre": "Disparo Veloz",    "efecto": "velocidad_ataque",      "valor_por_nivel": 1, "max_nivel": 5, "descripcion": "+1 velocidad de ataque por nivel"},
        {"id": "mc_rastreo", "nombre": "Rastreo Experto",  "efecto": "recoleccion_velocidad", "valor_por_nivel": 1, "max_nivel": 5, "descripcion": "+1% velocidad de recolección por nivel"},
        {"id": "mc_cazador", "nombre": "Cazador Nato",     "efecto": "oro_extra",             "valor_por_nivel": 1, "max_nivel": 5, "descripcion": "+1% oro extra al ganar combates por nivel"},
        {"id": "mc_flecha",  "nombre": "Flecha Brutal",    "efecto": "daño",                  "valor_por_nivel": 1, "max_nivel": 5, "descripcion": "+1% daño a distancia por nivel"},
    ],
}
def _puntos_talento_totales(jugador_id):
    jug = db_helper.obtener_jugador(jugador_id)
    if not jug:
        return 0
    nivel = jug["nivel"]
    return nivel // 5

def talentos_gastados(jugador_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT nivel FROM talentos_jugador WHERE jugador_id = ?', (jugador_id,))
    gastados = sum(nivel for (nivel,) in c.fetchall())
    conn.close()
    return gastados

def desbloquear_talento(jugador_id, talento_id, nivel):
    talento_info = None
    rama_del_talento = None
    for rama_nombre, rama_lista in TALENTOS.items():
        for t in rama_lista:
            if t["id"] == talento_id:
                talento_info = t
                rama_del_talento = rama_nombre
                break
        if talento_info:
            break
    if not talento_info:
        return False, "Talento no existe"
    if nivel > talento_info["max_nivel"]:
        return False, "Nivel máximo superado"
    # Verificar restricción de clase en ramas exclusivas
    if rama_del_talento in RAMAS_CLASE_ESPECIFICA:
        jug_cls = db_helper.obtener_jugador(jugador_id)
        if not jug_cls or jug_cls.get("clase") != rama_del_talento:
            return False, f"Talento exclusivo de la clase {rama_del_talento}"
    total_puntos = _puntos_talento_totales(jugador_id)
    gastados = talentos_gastados(jugador_id)
    disponibles = total_puntos - gastados
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT nivel FROM talentos_jugador WHERE jugador_id = ? AND talento_id = ?', (jugador_id, talento_id))
    row = c.fetchone()
    nivel_actual = row[0] if row else 0
    if nivel != nivel_actual + 1:
        return False, "Solo se puede subir de nivel uno a la vez"
    if disponibles < 1:
        return False, "No tienes suficientes puntos de talento"
    if row:
        c.execute('UPDATE talentos_jugador SET nivel = ? WHERE jugador_id = ? AND talento_id = ?', (nivel, jugador_id, talento_id))
    else:
        c.execute('INSERT INTO talentos_jugador (jugador_id, talento_id, nivel) VALUES (?, ?, ?)', (jugador_id, talento_id, nivel))
    conn.commit()
    conn.close()
    return True, "Talento desbloqueado/subido"

def obtener_bonos_totales(jugador_id):
    """Retorna un diccionario con la suma de todos los talentos activos del jugador."""
    _EFECTOS_PORCENTAJE = {"daño", "vida", "defensa", "xp_extra", "daño_critico", "reduccion_daño", "oro_extra", "curacion_extra"}
    bonos = {
        "daño": 0.0,
        "critico": 0,
        "velocidad_ataque": 0,
        "vida": 0.0,
        "defensa": 0.0,
        "regeneracion": 0,
        "carga": 0,
        "recoleccion_velocidad": 0,
        "xp_extra": 0.0,
        "evasion": 0,
        "daño_critico": 0.0,
        "reduccion_daño": 0.0,
        "oro_extra": 0.0,
        "stamina_max": 0,
        "cooldown_reduccion": 0,
        "curacion_extra": 0.0,
    }
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT talento_id, nivel FROM talentos_jugador WHERE jugador_id = ?', (jugador_id,))
    filas = c.fetchall()
    conn.close()
    for talento_id, nivel in filas:
        for rama in TALENTOS.values():
            for t in rama:
                if t["id"] == talento_id:
                    efecto = t["efecto"]
                    valor = t["valor_por_nivel"] * nivel
                    if efecto in _EFECTOS_PORCENTAJE:
                        bonos[efecto] = bonos.get(efecto, 0.0) + valor / 100.0
                    else:
                        bonos[efecto] = bonos.get(efecto, 0) + valor
                    break
    return bonos


# ==================== 2. HITOS DE CLASE ====================
NIVELES_HITO = [20, 40, 60, 80, 100]
def verificar_hito_nivel(jugador_id, nivel_actual):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    for hito in NIVELES_HITO:
        if nivel_actual >= hito:
            c.execute('SELECT 1 FROM hitos_reclamados WHERE jugador_id = ? AND nivel_hito = ?', (jugador_id, hito))
            if not c.fetchone():
                # Otorgar recompensa (bonos se aplican en perfil)
                c.execute('INSERT INTO hitos_reclamados (jugador_id, nivel_hito) VALUES (?, ?)', (jugador_id, hito))
                titulo = f"Conquistador de Nivel {hito}"
                db_helper.agregar_notificacion(jugador_id, f"🏆 Has alcanzado el hito nivel {hito} y recibes el título '{titulo}' y bonos permanentes.")
    conn.commit()
    conn.close()

def obtener_hitos_reclamados(jugador_id) -> List[int]:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT nivel_hito FROM hitos_reclamados WHERE jugador_id = ?', (jugador_id,))
    hitos = [row[0] for row in c.fetchall()]
    conn.close()
    return hitos

# ==================== 3. INSIGNIAS DE MAESTRÍA ====================
INSIGNIAS_NIVEL = [10,20,30,40,50,60,70,80,90,100]
def desbloquear_insignia(jugador_id, insignia_id, bono_stat, bono_valor):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('INSERT OR IGNORE INTO insignias (jugador_id, insignia_id) VALUES (?, ?)', (jugador_id, insignia_id))
    if c.rowcount:
        db_helper.agregar_notificacion(jugador_id, f"🎖️ Has desbloqueado la insignia '{insignia_id}' con +{bono_valor}% a {bono_stat}.")
    conn.commit()
    conn.close()

def obtener_bonos_insignias(jugador_id) -> Dict[str, float]:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT count(*) FROM insignias WHERE jugador_id = ?', (jugador_id,))
    count = c.fetchone()[0]
    conn.close()
    return {"vida": count * 0.5, "daño": count * 0.5, "defensa": count * 0.5}

# ==================== 4. MISIONES SEMANALES DE CLASE ====================
MISIONES_POR_CLASE = {
    "vanguardista": [
        {"nombre": "Bloquea 500 daño total", "objetivo_tipo": "daño_bloqueado", "cantidad": 500, "recompensa": "punto_talento"},
        {"nombre": "Derrota 20 monstruos", "objetivo_tipo": "matar", "cantidad": 20, "recompensa": "cofre_plata"}
    ],
    "acechante": [
        {"nombre": "Haz 1000 daño crítico", "objetivo_tipo": "daño_critico", "cantidad": 1000, "recompensa": "punto_talento"},
        {"nombre": "Recolecta 50 minerales", "objetivo_tipo": "recolectar_mineral", "cantidad": 50, "recompensa": "pergamino_mejora"}
    ],
    "tejehechizos": [
        {"nombre": "Cura 500 HP a aliados", "objetivo_tipo": "cura_total", "cantidad": 500, "recompensa": "punto_talento"},
        {"nombre": "Lanza 30 hechizos", "objetivo_tipo": "lanzar_hechizo", "cantidad": 30, "recompensa": "gema_mana"}
    ],
    "maestro_caza": [
        {"nombre": "Haz 15 ataques a distancia", "objetivo_tipo": "ataque_distancia", "cantidad": 15, "recompensa": "punto_talento"},
        {"nombre": "Pesca 10 peces raros", "objetivo_tipo": "pescar_raros", "cantidad": 10, "recompensa": "caña_mejorada"}
    ]
}

def generar_mision_clase(jugador_id):
    jug = db_helper.obtener_jugador(jugador_id)
    if not jug:
        return None
    clase = jug["clase"]
    misiones_posibles = MISIONES_POR_CLASE.get(clase, MISIONES_POR_CLASE["vanguardista"])
    mision = random.choice(misiones_posibles).copy()
    mision_id = f"semanal_{clase}_{datetime.now().strftime('%Y%m%d')}"
    fecha_inicio = datetime.now()
    fecha_fin = fecha_inicio + timedelta(days=COOLDOWN_MISION_SEMANAL_DIAS)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT OR REPLACE INTO mision_semanal 
        (jugador_id, mision_id, objetivo_tipo, objetivo_cantidad, progreso, recompensa, fecha_inicio, fecha_fin)
        VALUES (?, ?, ?, ?, 0, ?, ?, ?)''',
        (jugador_id, mision_id, mision["objetivo_tipo"], mision["cantidad"], mision["recompensa"], 
         fecha_inicio.isoformat(), fecha_fin.isoformat()))
    conn.commit()
    conn.close()
    return mision

def obtener_mision_activa(jugador_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM mision_semanal WHERE jugador_id = ?', (jugador_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def actualizar_progreso_mision(jugador_id, tipo_evento, cantidad=1):
    mision = obtener_mision_activa(jugador_id)
    if not mision:
        return
    if mision["objetivo_tipo"] == tipo_evento:
        nuevo_progreso = mision["progreso"] + cantidad
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('UPDATE mision_semanal SET progreso = ? WHERE jugador_id = ?', (nuevo_progreso, jugador_id))
        conn.commit()
        conn.close()
        if nuevo_progreso >= mision["objetivo_cantidad"]:
            completar_mision_clase(jugador_id)

def completar_mision_clase(jugador_id):
    mision = obtener_mision_activa(jugador_id)
    if not mision or mision["progreso"] < mision["objetivo_cantidad"]:
        return
    recompensa = mision["recompensa"]
    if recompensa == "punto_talento":
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('INSERT OR REPLACE INTO talentos_jugador (jugador_id, talento_id, nivel) VALUES (?, ?, 1)',
                  (jugador_id, "punto_extra_semanal"))
        conn.commit()
        conn.close()
    else:
        db_helper.agregar_item(jugador_id, recompensa, 1)
    db_helper.agregar_notificacion(jugador_id, f"✅ ¡Has completado la misión de clase! Recompensa: {recompensa}")

# ==================== 5. MISIONES LEGENDARIAS ====================
MISION_LEGENDARIA_ETAPAS = [
    {"nombre": "El Primer Paso", "objetivo": "Derrota 10 monstruos", "cantidad": 10},
    {"nombre": "Recolector de Recursos", "objetivo": "Recolecta 100 recursos", "cantidad": 100},
    {"nombre": "Cazador de Goblins", "objetivo": "Mata 20 goblins", "cantidad": 20},
    {"nombre": "Maestro de la Pesca", "objetivo": "Pesca 15 peces", "cantidad": 15},
    {"nombre": "Defensor de la Ciudad", "objetivo": "Completa 5 misiones diarias", "cantidad": 5},
    {"nombre": "Aprendiz de Artesano", "objetivo": "Fabrica 10 objetos", "cantidad": 10},
    {"nombre": "Explorador de Mazmorras", "objetivo": "Completa una mazmorra", "cantidad": 1},
    {"nombre": "El Vínculo Fraternal", "objetivo": "Ayuda a 3 jugadores en mazmorra", "cantidad": 3},
    {"nombre": "Senda de la Gloria", "objetivo": "Alcanza 5000 puntos de gloria", "cantidad": 5000},
    {"nombre": "Sabio de Aethelgard", "objetivo": "Llega a nivel 100", "cantidad": 100}
]

def iniciar_mision_legendaria(jugador_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('INSERT OR IGNORE INTO mision_legendaria (jugador_id, etapa, progreso, completada) VALUES (?, 1, 0, 0)', (jugador_id,))
    conn.commit()
    conn.close()

def avanzar_etapa_legendaria(jugador_id, tipo_evento, cantidad=1):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT etapa, progreso, completada FROM mision_legendaria WHERE jugador_id = ?', (jugador_id,))
    row = c.fetchone()
    if not row or row[2]:
        return
    etapa, progreso, completada = row
    if completada:
        conn.close()
        return
    etapa_actual = MISION_LEGENDARIA_ETAPAS[etapa-1]
    if tipo_evento == etapa_actual["objetivo"].split()[0].lower():
        nuevo_progreso = progreso + cantidad
        if nuevo_progreso >= etapa_actual["cantidad"]:
            if etapa == len(MISION_LEGENDARIA_ETAPAS):
                c.execute('UPDATE mision_legendaria SET completada = 1 WHERE jugador_id = ?', (jugador_id,))
                db_helper.agregar_item(jugador_id, "Título Leyenda Viviente", 1)
                db_helper.agregar_notificacion(jugador_id, "🏆 ¡Has completado la misión legendaria! Recibes el título 'Leyenda Viviente'.")
            else:
                c.execute('UPDATE mision_legendaria SET etapa = ?, progreso = 0 WHERE jugador_id = ?', (etapa+1, jugador_id))
                db_helper.agregar_notificacion(jugador_id, f"🎉 Completaste la etapa {etapa} de la misión legendaria. Siguiente: {MISION_LEGENDARIA_ETAPAS[etapa]['nombre']}")
        else:
            c.execute('UPDATE mision_legendaria SET progreso = ? WHERE jugador_id = ?', (nuevo_progreso, jugador_id))
    conn.commit()
    conn.close()

# ==================== 6. EVENTOS DE CLASE MENSUALES ====================
def obtener_evento_clase_activo():
    mes = datetime.now().month
    clases_list = list(clases.CLASES.keys())
    clase_evento = clases_list[(mes-1) % len(clases_list)]
    return clase_evento

def aplicar_bono_evento(jugador, event_clase):
    return jugador["clase"] == event_clase

# ==================== 7. SISTEMA PARAGON ====================
def calcular_puntos_paragon(jugador_id):
    jug = db_helper.obtener_jugador(jugador_id)
    if not jug or jug["nivel"] < 100:
        return 0
    xp_total_100 = sum(clases.calcular_experiencia_necesaria(lvl) for lvl in range(1,101))
    xp_actual = jug["experiencia"]
    if xp_actual <= xp_total_100:
        return 0
    xp_sobrante = xp_actual - xp_total_100
    return min(MAX_PUNTOS_PARAGON, xp_sobrante // XP_POR_PUNTO_PARAGONE)

def aplicar_bonos_paragon(jugador_id, stats):
    puntos = calcular_puntos_paragon(jugador_id)
    bono = 0.002 * puntos
    stats["vida"] = int(stats["vida"] * (1 + bono))
    stats["daño"] = int(stats["daño"] * (1 + bono))
    stats["defensa"] = int(stats["defensa"] * (1 + bono))
    stats["carga"] = int(stats["carga"] * (1 + bono))
    return stats

# ==================== 8. SISTEMA DE GLORIA ====================
TIPOS_MONSTRUO_GLORIA = {
    "bestia": "maestro_caza",
    "no-muerto": "vanguardista",
    "demonio": "tejehechizos",
    "humanoide": "acechante"
}

def agregar_gloria(jugador_id, tipo_monstruo, puntos):
    jug = db_helper.obtener_jugador(jugador_id)
    if not jug:
        return
    clase_jugador = jug["clase"]
    clase_esperada = TIPOS_MONSTRUO_GLORIA.get(tipo_monstruo)
    if clase_esperada != clase_jugador:
        puntos = puntos // 2
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT total_gloria FROM gloria WHERE jugador_id = ?', (jugador_id,))
    row = c.fetchone()
    total = row[0] if row else 0
    nuevo_total = total + puntos
    c.execute('INSERT OR REPLACE INTO gloria (jugador_id, total_gloria) VALUES (?, ?)', (jugador_id, nuevo_total))
    titulos = nuevo_total // GLORIA_POR_TITULO
    for i in range(1, titulos+1):
        titulo_id = f"gloria_{i*1000}"
        c.execute('SELECT 1 FROM gloria WHERE jugador_id = ? AND json_extract(titulos_desbloqueados, "$") LIKE ?', (jugador_id, f'%{titulo_id}%'))
        if not c.fetchone():
            c.execute('UPDATE gloria SET titulos_desbloqueados = json_insert(COALESCE(titulos_desbloqueados, "[]"), "$[#]", ?) WHERE jugador_id = ?', (titulo_id, jugador_id))
    conn.commit()
    conn.close()

def obtener_gloria_total(jugador_id) -> int:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT total_gloria FROM gloria WHERE jugador_id = ?', (jugador_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0

def obtener_titulos_gloria(jugador_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT titulos_desbloqueados FROM gloria WHERE jugador_id = ?', (jugador_id,))
    row = c.fetchone()
    conn.close()
    return json.loads(row[0]) if row and row[0] else []

# ==================== 9. RESETEO DE TALENTOS ====================
def calcular_costo_reseteo():
    return {"eternium": COSTO_RESETEO_ETERNIUM, "creditos": COSTO_RESETEO_CREDITOS}

def resetear_talentos(jugador_id, moneda_usar):
    jug = db_helper.obtener_jugador(jugador_id)
    if not jug:
        return False, "Jugador no existe"
    if moneda_usar == "eternium":
        if jug["eternium"] < COSTO_RESETEO_ETERNIUM:
            return False, "Falta Eternium"
        db_helper.actualizar_jugador(jugador_id, eternium=jug["eternium"] - COSTO_RESETEO_ETERNIUM)
    elif moneda_usar == "creditos":
        if jug["creditos_vacio"] < COSTO_RESETEO_CREDITOS:
            return False, "Faltan Créditos"
        db_helper.actualizar_jugador(jugador_id, creditos_vacio=jug["creditos_vacio"] - COSTO_RESETEO_CREDITOS)
    else:
        return False, "Moneda no válida"
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('DELETE FROM talentos_jugador WHERE jugador_id = ?', (jugador_id,))
    conn.commit()
    conn.close()
    db_helper.agregar_notificacion(jugador_id, "🔄 Tus talentos han sido reiniciados.")
    return True, "Talentos reiniciados"

# ==================== 10. BONIFICACIÓN POR ANTIGÜEDAD ====================
def registrar_tiempo_juego(jugador_id, minutos):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    ahora = datetime.now()
    c.execute('SELECT minutos_mes_actual, ultimo_registro FROM antiguedad WHERE jugador_id = ?', (jugador_id,))
    row = c.fetchone()
    if row:
        minutos_mes = row[0]
        ultimo = datetime.fromisoformat(row[1]) if row[1] else ahora
        if ultimo.month != ahora.month or ultimo.year != ahora.year:
            minutos_mes = 0
        nuevo_minutos = minutos_mes + minutos
        c.execute('UPDATE antiguedad SET minutos_mes_actual = ?, ultimo_registro = ? WHERE jugador_id = ?',
                  (nuevo_minutos, ahora.isoformat(), jugador_id))
    else:
        c.execute('INSERT INTO antiguedad (jugador_id, minutos_mes_actual, ultimo_registro) VALUES (?, ?, ?)',
                  (jugador_id, minutos, ahora.isoformat()))
        nuevo_minutos = minutos
    if nuevo_minutos >= 600:
        c.execute('SELECT puntos_veterano, ultimo_registro FROM antiguedad WHERE jugador_id = ?', (jugador_id,))
        data = c.fetchone()
        if data and data[0] is not None:
            ultimo_registro = datetime.fromisoformat(data[1])
            if ultimo_registro.month == ahora.month:
                conn.commit()
                conn.close()
                return
        c.execute('UPDATE antiguedad SET puntos_veterano = COALESCE(puntos_veterano,0)+1 WHERE jugador_id = ?', (jugador_id,))
        db_helper.agregar_notificacion(jugador_id, "🌟 Has recibido 1 Punto de Veterano por tu constancia mensual.")
    conn.commit()
    conn.close()

def canjear_punto_veterano(jugador_id, opcion_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT puntos_veterano, puntos_veterano_usados, ultimo_canje_talento_extra FROM antiguedad WHERE jugador_id = ?', (jugador_id,))
    row = c.fetchone()
    if not row:
        return False, "No tienes puntos de veterano"
    puntos = row[0] - row[1]
    if opcion_id == 1 and puntos >= 1:
        db_helper.agregar_item(jugador_id, "Cosmético_Estrella", 1)
        c.execute('UPDATE antiguedad SET puntos_veterano_usados = puntos_veterano_usados + 1 WHERE jugador_id = ?', (jugador_id,))
    elif opcion_id == 2 and puntos >= 3:
        c.execute('UPDATE antiguedad SET puntos_veterano_usados = puntos_veterano_usados + 3 WHERE jugador_id = ?', (jugador_id,))
        db_helper.agregar_item(jugador_id, "Título Veterano", 1)
    elif opcion_id == 3 and puntos >= 6:
        if row[2]:
            return False, "Ya has usado esta opción este año"
        c.execute('UPDATE antiguedad SET puntos_veterano_usados = puntos_veterano_usados + 6, ultimo_canje_talento_extra = 1 WHERE jugador_id = ?', (jugador_id,))
        db_helper.agregar_item(jugador_id, "Punto_Talento_Extra", 1)
    elif opcion_id == 4 and puntos >= 12:
        c.execute('UPDATE antiguedad SET puntos_veterano_usados = puntos_veterano_usados + 12 WHERE jugador_id = ?', (jugador_id,))
        db_helper.agregar_item(jugador_id, "Montura_Corcel_Tiempo", 1)
    else:
        return False, "No tienes suficientes puntos"
    conn.commit()
    conn.close()
    return True, "Canje exitoso"

# ==================== 11. MAESTRÍA DE SUBCLASE ====================
def subir_nivel_subclase(jugador_id, xp_ganada):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT nivel, xp FROM maestria_subclase WHERE jugador_id = ?', (jugador_id,))
    row = c.fetchone()
    if not row:
        c.execute('INSERT INTO maestria_subclase (jugador_id, nivel, xp) VALUES (?, 1, 0)', (jugador_id,))
        nivel = 1
        xp = 0
    else:
        nivel, xp = row
    xp += xp_ganada
    subido = False
    while xp >= 100 and nivel < 10:
        xp -= 100
        nivel += 1
        subido = True
    c.execute('UPDATE maestria_subclase SET nivel = ?, xp = ? WHERE jugador_id = ?', (nivel, xp, jugador_id))
    if subido:
        db_helper.agregar_notificacion(jugador_id, f"✨ Tu subclase ha subido al nivel {nivel}.")
    conn.commit()
    conn.close()
    return nivel

def obtener_bono_subclase(jugador_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT nivel FROM maestria_subclase WHERE jugador_id = ?', (jugador_id,))
    row = c.fetchone()
    nivel = row[0] if row else 1
    conn.close()
    return 1 + (nivel-1) * 0.1

# ==================== 12. COFRES DE LEGADO ====================
def reclamar_cofre_legado(jugador_id):
    puntos_gastados = talentos_gastados(jugador_id)
    if puntos_gastados == 0:
        return False, "No has gastado ningún punto de talento."
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT ultimo_cofre_puntos FROM cofres_legado WHERE jugador_id = ?', (jugador_id,))
    row = c.fetchone()
    ultimo = row[0] if row else 0
    if puntos_gastados - ultimo >= 10:
        db_helper.agregar_item(jugador_id, "Cofre de Legado", 1)
        c.execute('INSERT OR REPLACE INTO cofres_legado (jugador_id, ultimo_cofre_puntos) VALUES (?, ?)', (jugador_id, puntos_gastados))
        conn.commit()
        conn.close()
        return True, "Cofre de legado reclamado"
    conn.close()
    return False, "Necesitas gastar 10 puntos de talento más para el siguiente cofre"

# ==================== 13. RÉCORDS PERSONALES ====================
RECORDS_ID = ["mayor_daño", "monstruos_dia", "recoleccion_dia", "pesca_dia"]

def actualizar_record(jugador_id, record_id, valor):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT valor FROM records WHERE jugador_id = ? AND record_id = ?', (jugador_id, record_id))
    row = c.fetchone()
    if not row or valor > row[0]:
        c.execute('INSERT OR REPLACE INTO records (jugador_id, record_id, valor, fecha) VALUES (?, ?, ?, ?)',
                  (jugador_id, record_id, valor, datetime.now().isoformat()))
        db_helper.agregar_notificacion(jugador_id, f"🏅 ¡Nuevo récord personal en {record_id}: {valor}!")
        db_helper.agregar_item(jugador_id, "Punto_Talento_Extra", 1)
    conn.commit()
    conn.close()

def verificar_record_superado(jugador_id, record_id, nuevo_valor):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT valor FROM records WHERE jugador_id = ? AND record_id = ?', (jugador_id, record_id))
    row = c.fetchone()
    superado = (row is None) or (nuevo_valor > row[0])
    conn.close()
    if superado:
        actualizar_record(jugador_id, record_id, nuevo_valor)
    return superado

# ==================== 14. PRESTIGIO DE CLASE ====================
def prestigiar_clase(jugador_id):
    jug = db_helper.obtener_jugador(jugador_id)
    if not jug or jug["nivel"] < 100:
        return False, "Necesitas nivel 100 para prestigiar"
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT nivel FROM prestigio WHERE jugador_id = ?', (jugador_id,))
    row = c.fetchone()
    prestigio_actual = row[0] if row else 0
    if prestigio_actual >= 25:
        return False, "Has alcanzado el máximo prestigio (25)"
    nuevo_prestigio = prestigio_actual + 1
    c.execute('INSERT OR REPLACE INTO prestigio (jugador_id, nivel) VALUES (?, ?)', (jugador_id, nuevo_prestigio))
    db_helper.actualizar_jugador(jugador_id, nivel=1, experiencia=0,
                                 hp_actual=clases.calcular_vida_maxima(jug["clase"], 1, 0),
                                 hp_max=clases.calcular_vida_maxima(jug["clase"], 1, 0))
    db_helper.agregar_notificacion(jugador_id, f"🌟 ¡Has alcanzado el prestigio {nuevo_prestigio}! Tu habilidad pasiva mejora.")
    conn.commit()
    conn.close()
    return True, f"Prestigio {nuevo_prestigio} alcanzado"

def calcular_bono_prestigio(jugador_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT nivel FROM prestigio WHERE jugador_id = ?', (jugador_id,))
    row = c.fetchone()
    prestigio = row[0] if row else 0
    conn.close()
    return 1 + prestigio * PRESTIGIO_BONO_PASIVA_POR_PRESTIGIO

def obtener_nivel_prestigio(jugador_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT nivel FROM prestigio WHERE jugador_id = ?', (jugador_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0

# ==================== INICIALIZACIÓN ====================
_crear_tablas_si_no_existen()
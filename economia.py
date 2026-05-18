#!/usr/bin/env python3
# economia.py
# Sistema de 3 monedas, mercado P2P, retiros/depósitos manuales, tienda premium,
# rotación aleatoria, cambio de facción con créditos, y ganancia neta del admin.

import sqlite3
import json
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any

import db_helper

DB_PATH = "aethelgard.db"

# ==================== CONSTANTES ====================
# Relación Crédito <-> USDT (1 crédito = 0.01 USD)
CREDITO_A_USDT = 0.01
USDT_A_CREDITO = 100  # 1 USDT = 100 créditos

# Tasas de cambio con el banco (spread)
# 1 crédito = 0.4 eternium (pierde valor)
CREDITO_A_ETERNIUM = 0.1
# 1 eternium = 1.8 créditos (pagas más créditos por eternium)
ETERNIUM_A_CREDITO = 3.0

# Retiros
COMISION_RETIRO = 0.20          # 20%
MINIMO_RETIRO_CREDITOS = 100    # mínimo retirar 100 créditos (1 USDT antes de comisión)
COSTO_RED_BSC_USDT = 0.01       # 0.01 USDT por transacción (para retiros que envías)

# Mercado P2P
MAX_OFERTAS_POR_JUGADOR = 5

# Tienda premium
TIEMPO_ROTACION_HORAS = 120     # 7 días
CANTIDAD_OBJETOS_ROTACION = 10   # número de objetos que aparecen cada rotación

# Cambio de facción con créditos
COSTO_CAMBIO_FACCION_CREDITOS = 500

# ==================== TABLA MAESTRA DE OBJETOS PREMIUM ====================
# Estos objetos están disponibles para rotación aleatoria en la tienda.
OBJETOS_PREMIUM_MAESTROS = [
    # Skins (cambian apariencia)
    {"id": "skin_espada_fuego", "nombre": "Skin Espada de Fuego", "tipo": "skin_arma", "clase_requerida": None, "precio_creditos": 50, "stock_maximo": 10, "rareza": 1, "descripcion": "Tu espada arde en llamas."},
    {"id": "skin_armadura_dragon", "nombre": "Skin Armadura de Dragón", "tipo": "skin_armadura", "clase_requerida": "vanguardista", "precio_creditos": 80, "stock_maximo": 8, "rareza": 1, "descripcion": "Escamas de dragón cubren tu armadura."},
    {"id": "skin_capa_sombra", "nombre": "Capa de la Sombra", "tipo": "skin_capa", "clase_requerida": "acechante", "precio_creditos": 60, "stock_maximo": 12, "rareza": 1, "descripcion": "Te vuelves más sigiloso visualmente."},
    
    # Armas ultralegendarias (stats altas)
    {"id": "espada_vacio_supremo", "nombre": "Hoja del Vacío Supremo", "tipo": "arma", "clase_requerida": "vanguardista", "precio_creditos": 1500, "stock_maximo": 3, "rareza": 5, "descripcion": "Daño +80, vida +200."},
    {"id": "arco_almas", "nombre": "Arco de las 1000 Almas", "tipo": "arma", "clase_requerida": "maestro_caza", "precio_creditos": 1200, "stock_maximo": 3, "rareza": 5, "descripcion": "Daño +70, velocidad +15%."},
    {"id": "báculo_ancestral", "nombre": "Báculo del Hechicero Ancestral", "tipo": "arma", "clase_requerida": "tejehechizos", "precio_creditos": 1300, "stock_maximo": 3, "rareza": 5, "descripcion": "Daño mágico +90, mana +100."},
    
    # Armaduras especiales
    {"id": "coraza_guardian", "nombre": "Coraza del Guardián", "tipo": "armadura", "clase_requerida": "vanguardista", "precio_creditos": 800, "stock_maximo": 5, "rareza": 4, "descripcion": "Defensa +50, vida +150."},
    {"id": "tunica_hechicero", "nombre": "Túnica del Hechicero Ancestral", "tipo": "armadura", "clase_requerida": "tejehechizos", "precio_creditos": 750, "stock_maximo": 5, "rareza": 4, "descripcion": "Defensa mágica +40, mana +80."},
    
    # Monturas exclusivas
    {"id": "corcel_sombras", "nombre": "Corcel de Sombras", "tipo": "montura", "clase_requerida": None, "precio_creditos": 2500, "stock_maximo": 2, "rareza": 6, "descripcion": "Velocidad +50%, habilidad 'Paso sombrío'."},
    {"id": "dragon_cristal", "nombre": "Dragón de Cristal", "tipo": "montura", "clase_requerida": None, "precio_creditos": 3000, "stock_maximo": 1, "rareza": 7, "descripcion": "Vuela sobre obstáculos, +80% velocidad."},
    
    # Mascotas raras
    {"id": "fenix_emplumado", "nombre": "Fénix Emplumado", "tipo": "mascota", "clase_requerida": None, "precio_creditos": 500, "stock_maximo": 10, "rareza": 2, "descripcion": "Pequeno bonus de recolección (+5%)."},
    {"id": "lobo_estelar", "nombre": "Lobo Estelar", "tipo": "mascota", "clase_requerida": None, "precio_creditos": 600, "stock_maximo": 8, "rareza": 2, "descripcion": "Aumenta la probabilidad de encontrar cofres."}
]

# ==================== FUNCIONES BASE DE MONEDAS ====================
def obtener_saldos(user_id: int) -> Dict[str, int]:
    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        return {"oro": 0, "eternium": 0, "creditos_vacio": 0}
    return {
        "oro": jug.get("oro", 0),
        "eternium": jug.get("eternium", 0),
        "creditos_vacio": jug.get("creditos_vacio", 0)
    }

def modificar_saldo(user_id: int, moneda: str, cantidad: int, motivo: str) -> bool:
    if cantidad == 0:
        return True
    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        return False
    saldo_actual = jug.get(moneda, 0)
    nuevo_saldo = saldo_actual + cantidad
    if nuevo_saldo < 0:
        return False
    db_helper.actualizar_jugador(user_id, **{moneda: nuevo_saldo})
    # Registrar transacción
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Aseguramos que la tabla transacciones existe (ya la crea db_helper, pero por si acaso)
    c.execute('''CREATE TABLE IF NOT EXISTS transacciones (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        tipo TEXT,
        cantidad INTEGER,
        moneda TEXT,
        motivo TEXT,
        timestamp TIMESTAMP
    )''')
    c.execute('''INSERT INTO transacciones (user_id, tipo, cantidad, moneda, motivo, timestamp)
                 VALUES (?, ?, ?, ?, ?, ?)''',
              (user_id, "modificacion", cantidad, moneda, motivo, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return True

def registrar_transaccion(user_id: int, tipo: str, cantidad: int, moneda: str, motivo: str):
    """Registro genérico de transacciones (sin modificar saldo)."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT INTO transacciones (user_id, tipo, cantidad, moneda, motivo, timestamp)
                 VALUES (?, ?, ?, ?, ?, ?)''',
              (user_id, tipo, cantidad, moneda, motivo, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def transferir_creditos_p2p(from_id: int, to_id: int, cantidad: int) -> Tuple[bool, str]:
    if cantidad <= 0:
        return False, "Cantidad inválida"
    # Verificar saldo
    saldos = obtener_saldos(from_id)
    if saldos["creditos_vacio"] < cantidad:
        return False, "No tienes suficientes créditos"
    # Modificar saldos
    if not modificar_saldo(from_id, "creditos_vacio", -cantidad, f"transferencia a {to_id}"):
        return False, "Error al transferir"
    if not modificar_saldo(to_id, "creditos_vacio", cantidad, f"transferencia de {from_id}"):
        # Revertir (poco probable, pero por seguridad)
        modificar_saldo(from_id, "creditos_vacio", cantidad, "reversión por error")
        return False, "Error en el destino"
    registrar_transaccion(from_id, "transferencia_envio", cantidad, "creditos_vacio", f"a usuario {to_id}")
    registrar_transaccion(to_id, "transferencia_recibo", cantidad, "creditos_vacio", f"de usuario {from_id}")
    return True, f"Transferiste {cantidad} créditos a usuario {to_id}"

# ==================== INTERCAMBIO CON EL BANCO ====================
def cambiar_creditos_por_eternium(user_id: int, cantidad_creditos: int) -> Tuple[bool, str]:
    """Jugador entrega créditos (se destruyen) y recibe eternium según tasa fija."""
    if cantidad_creditos <= 0:
        return False, "Cantidad inválida"
    saldos = obtener_saldos(user_id)
    if saldos["creditos_vacio"] < cantidad_creditos:
        return False, "No tienes suficientes créditos"
    eternium_recibido = int(cantidad_creditos * CREDITO_A_ETERNIUM)
    if eternium_recibido < 1:
        return False, "Mínimo 3 créditos para obtener 1 eternium"
    # Destruir créditos, añadir eternium
    modificar_saldo(user_id, "creditos_vacio", -cantidad_creditos, f"cambio a eternium (banco)")
    modificar_saldo(user_id, "eternium", eternium_recibido, f"cambio desde creditos (banco)")
    registrar_transaccion(user_id, "cambio_banco", cantidad_creditos, "creditos_vacio", "convertidos a eternium")
    registrar_transaccion(user_id, "cambio_banco", eternium_recibido, "eternium", "recibidos desde creditos")
    return True, f"Cambiaste {cantidad_creditos} créditos por {eternium_recibido} eternium."

def cambiar_eternium_por_creditos(user_id: int, cantidad_eternium: int) -> Tuple[bool, str]:
    """Jugador entrega eternium (se destruye) y recibe créditos según tasa desfavorable."""
    if cantidad_eternium <= 0:
        return False, "Cantidad inválida"
    saldos = obtener_saldos(user_id)
    if saldos["eternium"] < cantidad_eternium:
        return False, "No tienes suficiente eternium"
    creditos_recibidos = int(cantidad_eternium * ETERNIUM_A_CREDITO)
    # Destruir eternium, añadir créditos
    modificar_saldo(user_id, "eternium", -cantidad_eternium, f"cambio a creditos (banco)")
    modificar_saldo(user_id, "creditos_vacio", creditos_recibidos, f"cambio desde eternium (banco)")
    registrar_transaccion(user_id, "cambio_banco", cantidad_eternium, "eternium", "convertidos a creditos")
    registrar_transaccion(user_id, "cambio_banco", creditos_recibidos, "creditos_vacio", "recibidos desde eternium")
    return True, f"Cambiaste {cantidad_eternium} eternium por {creditos_recibidos} créditos."

# ==================== MERCADO P2P (OFERTAS) ====================
def _crear_tablas_si_no_existen():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Nota: No creamos ofertas_p2p aquí porque se creará desde p2p.py si es necesario.
    # Pero por compatibilidad, la creamos si no existe (aunque p2p.py también la creará).
    c.execute('''CREATE TABLE IF NOT EXISTS ofertas_p2p (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        vendedor_id INTEGER,
        ofrece_tipo TEXT,  -- 'creditos_vacio', 'eternium', 'oro'
        ofrece_cantidad INTEGER,
        pide_tipo TEXT,
        pide_cantidad INTEGER,
        fecha_creacion TIMESTAMP,
        activa BOOLEAN DEFAULT 1
    )''')
    # Tabla para rotación de tienda
    c.execute('''CREATE TABLE IF NOT EXISTS tienda_actual (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        objeto_id TEXT,
        nombre TEXT,
        tipo TEXT,
        clase_requerida TEXT,
        precio_creditos INTEGER,
        stock INTEGER,
        descripcion TEXT,
        fecha_inicio TIMESTAMP,
        fecha_fin TIMESTAMP
    )''')
    conn.commit()
    conn.close()

_crear_tablas_si_no_existen()

def publicar_oferta(vendedor_id: int, ofrece_tipo: str, ofrece_cant: int, pide_tipo: str, pide_cant: int) -> Tuple[bool, str]:
    # Validar tipos
    tipos_validos = ["creditos_vacio", "eternium", "oro"]
    if ofrece_tipo not in tipos_validos or pide_tipo not in tipos_validos:
        return False, "Tipo de moneda inválido"
    if ofrece_cant <= 0 or pide_cant <= 0:
        return False, "Cantidades deben ser positivas"
    # Verificar que el vendedor tiene suficiente
    saldos = obtener_saldos(vendedor_id)
    if saldos[ofrece_tipo] < ofrece_cant:
        return False, f"No tienes suficiente {ofrece_tipo}"
    # Limitar número de ofertas activas
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM ofertas_p2p WHERE vendedor_id = ? AND activa = 1', (vendedor_id,))
    count = c.fetchone()[0]
    if count >= MAX_OFERTAS_POR_JUGADOR:
        conn.close()
        return False, f"Máximo {MAX_OFERTAS_POR_JUGADOR} ofertas activas"
    c.execute('''INSERT INTO ofertas_p2p (vendedor_id, ofrece_tipo, ofrece_cantidad, pide_tipo, pide_cantidad, fecha_creacion, activa)
                 VALUES (?, ?, ?, ?, ?, ?, 1)''',
              (vendedor_id, ofrece_tipo, ofrece_cant, pide_tipo, pide_cant, datetime.now().isoformat()))
    oferta_id = c.lastrowid
    conn.commit()
    conn.close()
    return True, f"Oferta #{oferta_id} publicada"

def aceptar_oferta(oferta_id: int, comprador_id: int) -> Tuple[bool, str]:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT vendedor_id, ofrece_tipo, ofrece_cantidad, pide_tipo, pide_cantidad, activa FROM ofertas_p2p WHERE id = ?', (oferta_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return False, "Oferta no encontrada"
    vendedor_id, ofrece_tipo, ofrece_cant, pide_tipo, pide_cant, activa = row
    if not activa:
        conn.close()
        return False, "Oferta ya expirada o cancelada"
    if comprador_id == vendedor_id:
        conn.close()
        return False, "No puedes aceptar tu propia oferta"
    # Verificar que comprador tiene suficiente de lo que pide
    saldos_comprador = obtener_saldos(comprador_id)
    if saldos_comprador[pide_tipo] < pide_cant:
        conn.close()
        return False, f"No tienes suficiente {pide_tipo}"
    # Verificar que vendedor aún tiene suficiente de lo que ofrece (por si cambió su saldo después)
    saldos_vendedor = obtener_saldos(vendedor_id)
    if saldos_vendedor[ofrece_tipo] < ofrece_cant:
        conn.close()
        return False, "El vendedor ya no tiene suficientes fondos"
    # Realizar intercambio
    # 1. Quitar del comprador lo que pide
    modificar_saldo(comprador_id, pide_tipo, -pide_cant, f"compra de oferta {oferta_id}")
    # 2. Añadir al vendedor lo que pide
    modificar_saldo(vendedor_id, pide_tipo, pide_cant, f"venta por oferta {oferta_id}")
    # 3. Quitar del vendedor lo que ofrece
    modificar_saldo(vendedor_id, ofrece_tipo, -ofrece_cant, f"venta por oferta {oferta_id}")
    # 4. Añadir al comprador lo que ofrece
    modificar_saldo(comprador_id, ofrece_tipo, ofrece_cant, f"compra de oferta {oferta_id}")
    # Marcar oferta como inactiva
    c.execute('UPDATE ofertas_p2p SET activa = 0 WHERE id = ?', (oferta_id,))
    conn.commit()
    conn.close()
    registrar_transaccion(vendedor_id, "p2p_venta", ofrece_cant, ofrece_tipo, f"vendido a {comprador_id}")
    registrar_transaccion(comprador_id, "p2p_compra", ofrece_cant, ofrece_tipo, f"comprado a {vendedor_id}")
    return True, "Intercambio completado"

def cancelar_oferta(oferta_id: int, usuario_id: int) -> Tuple[bool, str]:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT vendedor_id, activa FROM ofertas_p2p WHERE id = ?', (oferta_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return False, "Oferta no encontrada"
    vendedor_id, activa = row
    if not activa:
        conn.close()
        return False, "Oferta ya inactiva"
    if vendedor_id != usuario_id:
        conn.close()
        return False, "No puedes cancelar oferta de otro jugador"
    c.execute('UPDATE ofertas_p2p SET activa = 0 WHERE id = ?', (oferta_id,))
    conn.commit()
    conn.close()
    return True, "Oferta cancelada"

def listar_ofertas(tipo_filtro: str = None) -> List[Dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    query = 'SELECT * FROM ofertas_p2p WHERE activa = 1'
    if tipo_filtro:
        query += f" AND (ofrece_tipo = '{tipo_filtro}' OR pide_tipo = '{tipo_filtro}')"
    c.execute(query)
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

# ==================== RETIROS Y DEPÓSITOS (MANUALES, ADMIN) ====================
def solicitar_retiro(user_id: int, cantidad_creditos: int, direccion_usdt: str) -> Tuple[bool, str]:
    """Crea una solicitud de retiro (estado pendiente). Solo admin puede aprobar."""
    if cantidad_creditos < MINIMO_RETIRO_CREDITOS:
        return False, f"Mínimo {MINIMO_RETIRO_CREDITOS} créditos para retirar"
    saldos = obtener_saldos(user_id)
    if saldos["creditos_vacio"] < cantidad_creditos:
        return False, "No tienes suficientes créditos"
    # Calcular USDT a enviar (descontando comisión y comisión de red)
    valor_usdt_bruto = cantidad_creditos * CREDITO_A_USDT
    comision = valor_usdt_bruto * COMISION_RETIRO
    usdt_a_enviar = valor_usdt_bruto - comision - COSTO_RED_BSC_USDT
    if usdt_a_enviar <= 0:
        return False, "El monto es muy pequeño después de comisiones"
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS solicitudes_retiro (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        cantidad_creditos INTEGER,
        direccion_usdt TEXT,
        usdt_a_enviar REAL,
        estado TEXT DEFAULT 'pendiente',
        fecha_solicitud TIMESTAMP
    )''')
    c.execute('''INSERT INTO solicitudes_retiro (user_id, cantidad_creditos, direccion_usdt, usdt_a_enviar, fecha_solicitud)
                 VALUES (?, ?, ?, ?, ?)''',
              (user_id, cantidad_creditos, direccion_usdt, usdt_a_enviar, datetime.now().isoformat()))
    solicitud_id = c.lastrowid
    conn.commit()
    conn.close()
    registrar_transaccion(user_id, "retiro_solicitado", cantidad_creditos, "creditos_vacio", f"ID {solicitud_id}")
    # Notificación al admin (se enviará desde main)
    return True, f"Solicitud de retiro #{solicitud_id} creada. Espera la aprobación del administrador."

def _obtener_solicitud(solicitud_id: int) -> Optional[Dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM solicitudes_retiro WHERE id = ?', (solicitud_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def aprobar_retiro(solicitud_id: int, admin_user_id: int) -> Tuple[bool, str]:
    """Solo debe llamarlo el administrador después de enviar manualmente el USDT."""
    # Solo el administrador (user_id específico) puede aprobar. Pasamos admin_user_id para verificar.
    # En main, aseguraremos que solo el dueño pueda ejecutar este comando.
    sol = _obtener_solicitud(solicitud_id)
    if not sol:
        return False, "Solicitud no encontrada"
    if sol["estado"] != "pendiente":
        return False, "Solicitud ya procesada"
    user_id = sol["user_id"]
    cantidad_creditos = sol["cantidad_creditos"]
    # Verificar que el jugador aún tiene los créditos (pudo haber gastado entre medio)
    saldos = obtener_saldos(user_id)
    if saldos["creditos_vacio"] < cantidad_creditos:
        # Cancelar solicitud automáticamente
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('UPDATE solicitudes_retiro SET estado = "cancelada" WHERE id = ?', (solicitud_id,))
        conn.commit()
        conn.close()
        return False, "El jugador ya no tiene suficientes créditos. Solicitud cancelada."
    # Restar créditos
    modificar_saldo(user_id, "creditos_vacio", -cantidad_creditos, f"retiro aprobado #{solicitud_id}")
    # Marcar solicitud como aprobada
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('UPDATE solicitudes_retiro SET estado = "aprobada", fecha_procesado = ? WHERE id = ?',
              (datetime.now().isoformat(), solicitud_id))
    conn.commit()
    conn.close()
    registrar_transaccion(user_id, "retiro_aprobado", cantidad_creditos, "creditos_vacio", f"ID {solicitud_id}")
    return True, f"Retiro #{solicitud_id} aprobado. Debes haber enviado {sol['usdt_a_enviar']} USDT a {sol['direccion_usdt']} (resta de comisión y red)."

def rechazar_retiro(solicitud_id: int) -> Tuple[bool, str]:
    sol = _obtener_solicitud(solicitud_id)
    if not sol:
        return False, "Solicitud no encontrada"
    if sol["estado"] != "pendiente":
        return False, "Solicitud ya procesada"
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('UPDATE solicitudes_retiro SET estado = "rechazada" WHERE id = ?', (solicitud_id,))
    conn.commit()
    conn.close()
    registrar_transaccion(sol["user_id"], "retiro_rechazado", sol["cantidad_creditos"], "creditos_vacio", f"ID {solicitud_id}")
    return True, "Solicitud rechazada. Los créditos no fueron descontados."

def listar_solicitudes_pendientes() -> List[Dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM solicitudes_retiro WHERE estado = "pendiente" ORDER BY fecha_solicitud ASC')
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def depositar_creditos_manual(admin_user_id: int, user_id: int, cantidad_usdt: float) -> Tuple[bool, str]:
    """Solo el administrador puede ejecutar esto después de confirmar depósito real."""
    if cantidad_usdt <= 0:
        return False, "Cantidad inválida"
    creditos = int(cantidad_usdt * USDT_A_CREDITO)
    modificar_saldo(user_id, "creditos_vacio", creditos, f"depósito manual de {cantidad_usdt} USDT")
    registrar_transaccion(user_id, "deposito_manual", creditos, "creditos_vacio", f"{cantidad_usdt} USDT")
    return True, f"Se añadieron {creditos} créditos a usuario {user_id}."

# ==================== TIENDA PREMIUM (ROTACIÓN ALEATORIA) ====================
def _obtener_rotacion_actual():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    ahora = datetime.now().isoformat()
    c.execute('SELECT * FROM tienda_actual WHERE fecha_inicio <= ? AND fecha_fin >= ?', (ahora, ahora))
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def generar_nueva_rotacion():
    """
    Selecciona aleatoriamente CANTIDAD_OBJETOS_ROTACION de la tabla maestra,
    asigna stock según rareza, y guarda en tienda_actual con fecha de inicio y fin.
    """
    # Limpiar rotación anterior
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('DELETE FROM tienda_actual')
    # Seleccionar objetos aleatorios ponderados por rareza (menor rareza = más probable)
    # Hacemos una copia de la lista para no mutar
    pool = OBJETOS_PREMIUM_MAESTROS.copy()
    # Ponderar: rareza inversa? rareza menor más probable. Usaremos peso = 1/rareza
    pesos = [1 / max(obj["rareza"], 1) for obj in pool]
    seleccionados = random.choices(pool, weights=pesos, k=CANTIDAD_OBJETOS_ROTACION)
    fecha_inicio = datetime.now()
    fecha_fin = fecha_inicio + timedelta(hours=TIEMPO_ROTACION_HORAS)
    for obj in seleccionados:
        # stock máximo = stock_maximo del objeto (limitado)
        stock = obj["stock_maximo"]
        c.execute('''INSERT INTO tienda_actual 
            (objeto_id, nombre, tipo, clase_requerida, precio_creditos, stock, descripcion, fecha_inicio, fecha_fin)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                  (obj["id"], obj["nombre"], obj["tipo"], obj["clase_requerida"],
                   obj["precio_creditos"], stock, obj["descripcion"],
                   fecha_inicio.isoformat(), fecha_fin.isoformat()))
    conn.commit()
    conn.close()

def obtener_tienda_actual() -> List[Dict]:
    """Retorna lista de objetos en la tienda vigente, con stock."""
    return _obtener_rotacion_actual()

def comprar_de_tienda(user_id: int, item_id: str, cantidad: int = 1) -> Tuple[bool, str]:
    # Buscar el item en la rotación actual
    tienda = _obtener_rotacion_actual()
    item = next((it for it in tienda if it["objeto_id"] == item_id), None)
    if not item:
        return False, "Objeto no disponible en la tienda actual"
    if item["stock"] < cantidad:
        return False, f"Solo quedan {item['stock']} unidades de este objeto"
    precio_total = item["precio_creditos"] * cantidad
    saldos = obtener_saldos(user_id)
    if saldos["creditos_vacio"] < precio_total:
        return False, "No tienes suficientes créditos"
    # Verificar clase requerida
    if item["clase_requerida"]:
        jug = db_helper.obtener_jugador(user_id)
        if not jug or jug["clase"] != item["clase_requerida"]:
            return False, f"Este objeto solo puede ser usado por {item['clase_requerida']}"
    # Realizar compra
    modificar_saldo(user_id, "creditos_vacio", -precio_total, f"compra tienda: {item['nombre']} x{cantidad}")
    # Reducir stock en BD
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('UPDATE tienda_actual SET stock = stock - ? WHERE objeto_id = ?', (cantidad, item_id))
    conn.commit()
    conn.close()
    # Añadir objeto al inventario del jugador (llamar a db_helper.agregar_item)
    db_helper.agregar_item(user_id, item["nombre"], cantidad)
    registrar_transaccion(user_id, "compra_tienda", precio_total, "creditos_vacio", f"{item['nombre']}")
    return True, f"Compraste {cantidad}x {item['nombre']} por {precio_total} créditos."

# ==================== CAMBIO DE FACCION CON CRÉDITOS ====================
def cambiar_faccion_con_creditos(user_id: int, nueva_faccion: str) -> Tuple[bool, str]:
    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        return False, "Jugador no encontrado"
    if jug["faccion"] == nueva_faccion:
        return False, "Ya eres de esa facción"
    # Verificar si puede cambiar gratis (por tiempo) o forzar con créditos
    puede_gratis = db_helper.puede_cambiar_faccion(user_id)  # función de db_helper
    if puede_gratis:
        # Cambio gratuito normal (ya implementado en otro lado)
        return False, "Aún tienes cambio gratuito disponible (usa el comando normal). Este método es solo para pagar con créditos."
    # Verificar créditos
    saldos = obtener_saldos(user_id)
    if saldos["creditos_vacio"] < COSTO_CAMBIO_FACCION_CREDITOS:
        return False, f"Necesitas {COSTO_CAMBIO_FACCION_CREDITOS} créditos para cambiar de facción ahora."
    # Realizar cambio
    modificar_saldo(user_id, "creditos_vacio", -COSTO_CAMBIO_FACCION_CREDITOS, f"cambio de facción a {nueva_faccion} (pago créditos)")
    db_helper.actualizar_jugador(user_id, faccion=nueva_faccion, ultimo_cambio_faccion=datetime.now().isoformat())
    registrar_transaccion(user_id, "cambio_faccion", COSTO_CAMBIO_FACCION_CREDITOS, "creditos_vacio", f"a {nueva_faccion}")
    return True, f"Has cambiado a la facción {nueva_faccion} usando {COSTO_CAMBIO_FACCION_CREDITOS} créditos."

# ==================== GANANCIA NETA DEL ADMIN (FUNCIÓN SECRETA) ====================
def _calcular_ganancia_neta_administrador() -> Dict[str, Any]:
    """
    Calcula la ganancia neta del administrador (en USDT) basada en transacciones registradas.
    Considera:
      - Depósitos manuales: créditos entregados por admin (los créditos se añadieron por orden del admin)
        realmente el admin recibió USDT real, entonces debe sumar ese ingreso.
      - Retiros aprobados: el admin envió USDT (cantidad usdt_a_enviar registrada en solicitud) y además pagó
        la comisión de red (0.01 USDT) por cada transacción de retiro.
      - También se pueden registrar otras transacciones (como ingreso por comisiones internas del banco, etc.)
    Para simplificar, asumimos que la única fuente de ingreso real del admin son los depósitos manuales (USDT recibidos)
    y el egreso real son los retiros aprobados (USDT enviados + costos de red).
    Además, la comisión del 20% ya está descontada en el usdt_a_enviar, por lo que no se suma aparte.
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Total USDT depositado (por admin via /depositar_creditos_manual)
    # Asumimos que cada depósito manual corresponde a un ingreso real de USDT.
    c.execute("SELECT SUM(cantidad) FROM transacciones WHERE tipo = 'deposito_manual' AND moneda = 'creditos_vacio'")
    row = c.fetchone()
    total_creditos_depositados = row[0] if row[0] else 0
    ingresos_usdt = total_creditos_depositados * CREDITO_A_USDT  # porque 1 crédito = 0.01 USDT

    # Total USDT enviado en retiros (de las solicitudes aprobadas)
    c.execute("SELECT SUM(usdt_a_enviar), COUNT(*) FROM solicitudes_retiro WHERE estado = 'aprobada'")
    row = c.fetchone()
    total_usdt_enviado = row[0] if row[0] else 0
    cantidad_retiros = row[1] if row[1] else 0
    costos_red = cantidad_retiros * COSTO_RED_BSC_USDT

    ganancia_neta = ingresos_usdt - total_usdt_enviado - costos_red
    return {
        "ingresos_por_depositos_usdt": ingresos_usdt,
        "egresos_por_retiros_usdt": total_usdt_enviado,
        "costos_red_bsc": costos_red,
        "ganancia_neta_usdt": ganancia_neta
    }

# ==================== INICIALIZACIÓN ====================
_crear_tablas_si_no_existen()
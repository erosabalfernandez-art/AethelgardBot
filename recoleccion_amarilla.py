#!/usr/bin/env python3
# recoleccion_amarilla.py
# Generado automáticamente por generar_recoleccion.py para zona amarilla

import asyncio
import random
import sqlite3
from datetime import datetime
from typing import Tuple, Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler

import db_helper
import economia
import config_balance
from combate import iniciar_combate, COMBATE_PVE_AZUL, COMBATE_PVE_AMARILLA, COMBATE_PVE_ROJA, COMBATE_PVE_NEGRA

DB_PATH = "aethelgard.db"

# ==================== MAPEO DE CARPETAS POR COLOR ====================
CARPETA_POR_COLOR = {
    'azul': 'zonas azules',
    'amarilla': 'zonas amarillas',
    'roja': 'zonas rojas',
    'negra': 'zonas negras',
}

# ==================== CONFIGURACIÓN DE RECOLECCIÓN ====================
CONFIG_RECOLECCION = {
    'Desierto Alianza': {
        'zona_id': 3,
        'nivel_zona': 20,
        'prob_fallo': 0.25,
        'prob_monstruo': 0.30,
        'min_oro': 5,
        'max_oro': 14,
        'prob_oro_extra': 0.05,
        'frases_fallo': ['Te distraes con el paisaje y no encuentras nada útil.', 'El terreno es demasiado duro, no logras extraer nada.', 'Un ruido te asusta y abandonas la recolección.', 'Parece que hoy no es tu día, no aparece nada.', 'Tus herramientas resbalan y no obtienes recursos.'],
        'materiales': [
            {'id': 'material_64', 'nombre': 'Trozo Pesado Pequeño', 'probabilidad': 0.1848, 'min': 1, 'max': 1},
            {'id': 'material_121', 'nombre': 'Corazón Sólido Menor', 'probabilidad': 0.1848, 'min': 1, 'max': 1},
            {'id': 'material_12', 'nombre': 'Sólido Corazón Medio', 'probabilidad': 0.1486, 'min': 1, 'max': 1},
            {'id': 'material_94', 'nombre': 'Corazón Áspero Refinado', 'probabilidad': 0.1486, 'min': 1, 'max': 1},
            {'id': 'material_101', 'nombre': 'Colmillo Pesado Sólido', 'probabilidad': 0.1486, 'min': 1, 'max': 1},
            {'id': 'material_140', 'nombre': 'Colmillo Pesado Frágil', 'probabilidad': 0.1848, 'min': 1, 'max': 1},
        ],
        'monstruos': [
            {'id': 'amarillanormales31', 'nombre': 'Escorpión de Arena', 'probabilidad': 0.3333},
            {'id': 'amarillanormales32', 'nombre': 'Momia Andante', 'probabilidad': 0.3333},
            {'id': 'amarillanormales33', 'nombre': 'Lagarto del Sol', 'probabilidad': 0.3333},
        ]
    },
    'Ruinas Alianza': {
        'zona_id': 4,
        'nivel_zona': 25,
        'prob_fallo': 0.25,
        'prob_monstruo': 0.30,
        'min_oro': 5,
        'max_oro': 37,
        'prob_oro_extra': 0.125,
        'frases_fallo': ['Te distraes con el paisaje y no encuentras nada útil.', 'El terreno es demasiado duro, no logras extraer nada.', 'Un ruido te asusta y abandonas la recolección.', 'Parece que hoy no es tu día, no aparece nada.', 'Tus herramientas resbalan y no obtienes recursos.'],
        'materiales': [
            {'id': 'material_142', 'nombre': 'Esquirla de Sólido Pequeño', 'probabilidad': 0.1858, 'min': 1, 'max': 1},
            {'id': 'material_101', 'nombre': 'Colmillo Pesado Sólido', 'probabilidad': 0.1073, 'min': 1, 'max': 1},
            {'id': 'material_19', 'nombre': 'Resistente Escama Roto', 'probabilidad': 0.1858, 'min': 1, 'max': 1},
            {'id': 'material_42', 'nombre': 'Cristal Duro Frágil', 'probabilidad': 0.1858, 'min': 1, 'max': 1},
            {'id': 'material_76', 'nombre': 'Lingote de Pesado Pequeño', 'probabilidad': 0.1858, 'min': 1, 'max': 1},
            {'id': 'material_66', 'nombre': 'Placa de Duro Sólido', 'probabilidad': 0.1494, 'min': 1, 'max': 1},
        ],
        'monstruos': [
            {'id': 'amarillanormales41', 'nombre': 'Momia Guerrera', 'probabilidad': 0.3333},
            {'id': 'amarillanormales42', 'nombre': 'Insecto Colosal', 'probabilidad': 0.3333},
            {'id': 'amarillanormales43', 'nombre': 'Aparición del Pasado', 'probabilidad': 0.3333},
        ]
    },
    'Oasis Alianza': {
        'zona_id': 5,
        'nivel_zona': 30,
        'prob_fallo': 0.25,
        'prob_monstruo': 0.30,
        'min_oro': 13,
        'max_oro': 39,
        'prob_oro_extra': 0.13,
        'frases_fallo': ['Te distraes con el paisaje y no encuentras nada útil.', 'El terreno es demasiado duro, no logras extraer nada.', 'Un ruido te asusta y abandonas la recolección.', 'Parece que hoy no es tu día, no aparece nada.', 'Tus herramientas resbalan y no obtienes recursos.'],
        'materiales': [
            {'id': 'material_71', 'nombre': 'Esquirla de Resistente Estable', 'probabilidad': 0.1690, 'min': 1, 'max': 1},
            {'id': 'material_129', 'nombre': 'Resistente Trozo Medio', 'probabilidad': 0.1690, 'min': 1, 'max': 1},
            {'id': 'material_46', 'nombre': 'Pesado Fragmento Simple', 'probabilidad': 0.2103, 'min': 1, 'max': 1},
            {'id': 'material_10', 'nombre': 'Núcleo Sólido Estable', 'probabilidad': 0.1690, 'min': 1, 'max': 1},
            {'id': 'material_73', 'nombre': 'Resina Resistente Primordial', 'probabilidad': 0.1413, 'min': 1, 'max': 1},
            {'id': 'material_142', 'nombre': 'Esquirla de Sólido Pequeño', 'probabilidad': 0.1413, 'min': 1, 'max': 1},
        ],
        'monstruos': [
            {'id': 'amarillanormales51', 'nombre': 'Cocodrilo del Oasis', 'probabilidad': 0.3333},
            {'id': 'amarillanormales52', 'nombre': 'Djinn Menor', 'probabilidad': 0.3333},
            {'id': 'amarillanormales53', 'nombre': 'Planta Carnívora', 'probabilidad': 0.3333},
        ]
    },
    'Desierto Imperio': {
        'zona_id': 14,
        'nivel_zona': 20,
        'prob_fallo': 0.25,
        'prob_monstruo': 0.30,
        'min_oro': 5,
        'max_oro': 14,
        'prob_oro_extra': 0.05,
        'frases_fallo': ['Te distraes con el paisaje y no encuentras nada útil.', 'El terreno es demasiado duro, no logras extraer nada.', 'Un ruido te asusta y abandonas la recolección.', 'Parece que hoy no es tu día, no aparece nada.', 'Tus herramientas resbalan y no obtienes recursos.'],
        'materiales': [
            {'id': 'material_108', 'nombre': 'Pesado Gema Refinado', 'probabilidad': 0.1523, 'min': 1, 'max': 1},
            {'id': 'material_58', 'nombre': 'Escama Resistente Mayor', 'probabilidad': 0.1273, 'min': 1, 'max': 1},
            {'id': 'material_49', 'nombre': 'Corazón de Duro Menor', 'probabilidad': 0.1894, 'min': 1, 'max': 1},
            {'id': 'material_59', 'nombre': 'Pesado Núcleo Simple', 'probabilidad': 0.1894, 'min': 1, 'max': 1},
            {'id': 'material_56', 'nombre': 'Trozo de Duro Roto', 'probabilidad': 0.1894, 'min': 1, 'max': 1},
            {'id': 'material_99', 'nombre': 'Trozo de Sólido Estable', 'probabilidad': 0.1523, 'min': 1, 'max': 1},
        ],
        'monstruos': [
            {'id': 'amarillanormales141', 'nombre': 'Gusano de las Dunas', 'probabilidad': 0.5000},
            {'id': 'amarillanormales142', 'nombre': 'Trampero Imperial', 'probabilidad': 0.5000},
        ]
    },
    'Ruinas Imperio': {
        'zona_id': 15,
        'nivel_zona': 25,
        'prob_fallo': 0.25,
        'prob_monstruo': 0.30,
        'min_oro': 5,
        'max_oro': 37,
        'prob_oro_extra': 0.125,
        'frases_fallo': ['Te distraes con el paisaje y no encuentras nada útil.', 'El terreno es demasiado duro, no logras extraer nada.', 'Un ruido te asusta y abandonas la recolección.', 'Parece que hoy no es tu día, no aparece nada.', 'Tus herramientas resbalan y no obtienes recursos.'],
        'materiales': [
            {'id': 'material_140', 'nombre': 'Colmillo Pesado Frágil', 'probabilidad': 0.1453, 'min': 1, 'max': 1},
            {'id': 'material_49', 'nombre': 'Corazón de Duro Menor', 'probabilidad': 0.1453, 'min': 1, 'max': 1},
            {'id': 'material_136', 'nombre': 'Resina Áspero Medio', 'probabilidad': 0.1738, 'min': 1, 'max': 1},
            {'id': 'material_114', 'nombre': 'Savia de Duro Sólido', 'probabilidad': 0.1738, 'min': 1, 'max': 1},
            {'id': 'material_31', 'nombre': 'Resistente Corazón Pequeño', 'probabilidad': 0.1453, 'min': 1, 'max': 1},
            {'id': 'material_9', 'nombre': 'Sólido Escama Menor', 'probabilidad': 0.2163, 'min': 1, 'max': 1},
        ],
        'monstruos': [
            {'id': 'amarillanormales151', 'nombre': 'Soldado Fantasma', 'probabilidad': 0.5000},
            {'id': 'amarillanormales152', 'nombre': 'Escarabajo de Fuego', 'probabilidad': 0.5000},
        ]
    },
    'Oasis Imperio': {
        'zona_id': 16,
        'nivel_zona': 30,
        'prob_fallo': 0.25,
        'prob_monstruo': 0.30,
        'min_oro': 13,
        'max_oro': 39,
        'prob_oro_extra': 0.13,
        'frases_fallo': ['Te distraes con el paisaje y no encuentras nada útil.', 'El terreno es demasiado duro, no logras extraer nada.', 'Un ruido te asusta y abandonas la recolección.', 'Parece que hoy no es tu día, no aparece nada.', 'Tus herramientas resbalan y no obtienes recursos.'],
        'materiales': [
            {'id': 'material_42', 'nombre': 'Cristal Duro Frágil', 'probabilidad': 0.1357, 'min': 1, 'max': 1},
            {'id': 'material_143', 'nombre': 'Esquirla Pesado Divino', 'probabilidad': 0.1357, 'min': 1, 'max': 1},
            {'id': 'material_33', 'nombre': 'Gema de Resistente Pequeño', 'probabilidad': 0.2019, 'min': 1, 'max': 1},
            {'id': 'material_105', 'nombre': 'Esquirla Sólido Pequeño', 'probabilidad': 0.2019, 'min': 1, 'max': 1},
            {'id': 'material_79', 'nombre': 'Núcleo Resistente Puro', 'probabilidad': 0.1623, 'min': 1, 'max': 1},
            {'id': 'material_122', 'nombre': 'Lingote de Sólido Refinado', 'probabilidad': 0.1623, 'min': 1, 'max': 1},
        ],
        'monstruos': [
            {'id': 'amarillanormales161', 'nombre': 'Hidra Menor', 'probabilidad': 0.5000},
            {'id': 'amarillanormales162', 'nombre': 'Bandido del Oasis', 'probabilidad': 0.5000},
        ]
    },
    'Desierto Sindicato': {
        'zona_id': 25,
        'nivel_zona': 20,
        'prob_fallo': 0.25,
        'prob_monstruo': 0.30,
        'min_oro': 5,
        'max_oro': 14,
        'prob_oro_extra': 0.05,
        'frases_fallo': ['Te distraes con el paisaje y no encuentras nada útil.', 'El terreno es demasiado duro, no logras extraer nada.', 'Un ruido te asusta y abandonas la recolección.', 'Parece que hoy no es tu día, no aparece nada.', 'Tus herramientas resbalan y no obtienes recursos.'],
        'materiales': [
            {'id': 'material_5', 'nombre': 'Resistente Colmillo Frágil', 'probabilidad': 0.1723, 'min': 1, 'max': 1},
            {'id': 'material_31', 'nombre': 'Resistente Corazón Pequeño', 'probabilidad': 0.1723, 'min': 1, 'max': 1},
            {'id': 'material_91', 'nombre': 'Tela de Sólido Simple', 'probabilidad': 0.1723, 'min': 1, 'max': 1},
            {'id': 'material_117', 'nombre': 'Corazón Resistente Simple', 'probabilidad': 0.1723, 'min': 1, 'max': 1},
            {'id': 'material_133', 'nombre': 'Trozo de Resistente Estable', 'probabilidad': 0.1385, 'min': 1, 'max': 1},
            {'id': 'material_52', 'nombre': 'Sólido Gema Menor', 'probabilidad': 0.1723, 'min': 1, 'max': 1},
        ],
        'monstruos': [
            {'id': 'amarillanormales251', 'nombre': 'Acechador del Sindicato', 'probabilidad': 0.5000},
            {'id': 'amarillanormales252', 'nombre': 'Lagarto de Fuego', 'probabilidad': 0.5000},
        ]
    },
    'Ruinas Sindicato': {
        'zona_id': 26,
        'nivel_zona': 25,
        'prob_fallo': 0.25,
        'prob_monstruo': 0.30,
        'min_oro': 5,
        'max_oro': 37,
        'prob_oro_extra': 0.125,
        'frases_fallo': ['Te distraes con el paisaje y no encuentras nada útil.', 'El terreno es demasiado duro, no logras extraer nada.', 'Un ruido te asusta y abandonas la recolección.', 'Parece que hoy no es tu día, no aparece nada.', 'Tus herramientas resbalan y no obtienes recursos.'],
        'materiales': [
            {'id': 'material_50', 'nombre': 'Alma Pesado Refinado', 'probabilidad': 0.1523, 'min': 1, 'max': 1},
            {'id': 'material_16', 'nombre': 'Resistente Colmillo Roto', 'probabilidad': 0.1894, 'min': 1, 'max': 1},
            {'id': 'material_98', 'nombre': 'Pesado Lingote Simple', 'probabilidad': 0.1894, 'min': 1, 'max': 1},
            {'id': 'material_37', 'nombre': 'Sólido Colmillo Sólido', 'probabilidad': 0.1523, 'min': 1, 'max': 1},
            {'id': 'material_95', 'nombre': 'Tela de Duro Divino', 'probabilidad': 0.1273, 'min': 1, 'max': 1},
            {'id': 'material_130', 'nombre': 'Hilo de Pesado Roto', 'probabilidad': 0.1894, 'min': 1, 'max': 1},
        ],
        'monstruos': [
            {'id': 'amarillanormales261', 'nombre': 'Robot Explorador', 'probabilidad': 0.5000},
            {'id': 'amarillanormales262', 'nombre': 'Espía Fantasma', 'probabilidad': 0.5000},
        ]
    },
    'Oasis Sindicato': {
        'zona_id': 27,
        'nivel_zona': 30,
        'prob_fallo': 0.25,
        'prob_monstruo': 0.30,
        'min_oro': 13,
        'max_oro': 39,
        'prob_oro_extra': 0.13,
        'frases_fallo': ['Te distraes con el paisaje y no encuentras nada útil.', 'El terreno es demasiado duro, no logras extraer nada.', 'Un ruido te asusta y abandonas la recolección.', 'Parece que hoy no es tu día, no aparece nada.', 'Tus herramientas resbalan y no obtienes recursos.'],
        'materiales': [
            {'id': 'material_53', 'nombre': 'Duro Trozo Divino', 'probabilidad': 0.1413, 'min': 1, 'max': 1},
            {'id': 'material_74', 'nombre': 'Polvo de Duro Roto', 'probabilidad': 0.2103, 'min': 1, 'max': 1},
            {'id': 'material_89', 'nombre': 'Polvo Duro Medio', 'probabilidad': 0.1690, 'min': 1, 'max': 1},
            {'id': 'material_92', 'nombre': 'Corazón de Sólido Sólido', 'probabilidad': 0.1690, 'min': 1, 'max': 1},
            {'id': 'material_98', 'nombre': 'Pesado Lingote Simple', 'probabilidad': 0.1413, 'min': 1, 'max': 1},
            {'id': 'material_45', 'nombre': 'Escama Resistente Sólido', 'probabilidad': 0.1690, 'min': 1, 'max': 1},
        ],
        'monstruos': [
            {'id': 'amarillanormales271', 'nombre': 'Guardaespaldas del Sindicato', 'probabilidad': 0.5000},
            {'id': 'amarillanormales272', 'nombre': 'Serpiente del Oasis', 'probabilidad': 0.5000},
        ]
    },
}

def _obtener_config_zona_actual(user_id: int) -> Optional[dict]:
    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        return None
    zona_nombre = jug.get("zona_actual", "")
    return CONFIG_RECOLECCION.get(zona_nombre)

def _otorgar_recompensa(user_id: int, zona_config: dict):
    from collections import defaultdict
    materiales_por_nombre = defaultdict(int)
    for mat in zona_config['materiales']:
        if random.random() < mat['probabilidad']:
            cantidad = random.randint(mat['min'], mat['max'])
            db_helper.agregar_item(user_id, mat['id'], cantidad)
            materiales_por_nombre[mat['nombre']] += cantidad
    materiales_obtenidos = list(materiales_por_nombre.items())
    oro_base = random.randint(zona_config['min_oro'], zona_config['max_oro'])
    if random.random() < zona_config['prob_oro_extra']:
        oro_extra = random.randint(1, oro_base)
        oro_base += oro_extra
    economia.modificar_saldo(user_id, 'oro', oro_base, 'recolección')
    try:
        import logros as _logros
        _logros.registrar_recoleccion(user_id)
        _logros.registrar_oro_acumulado(user_id, oro_base)
    except Exception:
        pass
    return oro_base, materiales_obtenidos

def _cargar_monstruo_real(zona_id: int, mon_id: str, carpeta_base: str) -> Optional[dict]:
    import importlib.util, os
    nombre_archivo = f'monstruos_normales_zona_{zona_id}.py'
    posibles = [
        os.path.join(carpeta_base, nombre_archivo),
        os.path.join(os.path.dirname(__file__), nombre_archivo),
        nombre_archivo,
    ]
    archivo = next((p for p in posibles if os.path.exists(p)), None)
    if not archivo:
        return None
    spec = importlib.util.spec_from_file_location(f'monstruos_zona_{zona_id}', archivo)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    if hasattr(modulo, 'MONSTRUOS_NORMALES'):
        return modulo.MONSTRUOS_NORMALES.get(mon_id)
    return None

async def cmd_recolectar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if db_helper.esta_marcado(user_id):
        await update.effective_message.reply_text("❌ Estás marcado. No puedes recolectar hasta que pagues rescate con /pagar_rescate.")
        return
    try:
        from guerra_facciones import check_lockdown
        if await check_lockdown(update):
            return
    except Exception:
        pass
    # Verificar y gastar stamina según la zona
    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        await update.effective_message.reply_text("No estás registrado.")
        return
    zona_nombre = jug.get("zona_actual", "")
    from datos_zona import ZONAS
    zona_info = next((z for z in ZONAS if z["nombre"] == zona_nombre), None)
    if not zona_info:
        await update.effective_message.reply_text("No se pudo determinar tu zona.")
        return
    color_zona = zona_info["color"]
    costo_stamina = int(db_helper.obtener_config("stamina_recolectar", "5"))
    stamina_antes, stamina_max, _ = db_helper.obtener_stamina(user_id)
    if not db_helper.gastar_stamina(user_id, costo_stamina):
        await update.effective_message.reply_text(
            f"❌ No tienes suficiente stamina.\n"
            f"⚡ Stamina actual: {stamina_antes}/{stamina_max}\n"
            f"Necesitas {costo_stamina}. Se regenera automáticamente con el tiempo."
        )
        return
    zona_config = _obtener_config_zona_actual(user_id)
    if not zona_config:
        await update.effective_message.reply_text("No estás en una zona donde puedas recolectar.")
        return
    if db_helper.es_ocupado(user_id):
        actividad = db_helper.nombre_actividad(user_id)
        await update.effective_message.reply_text(f"❌ Ya estás {actividad}. Termina esa actividad primero.")
        return
    stamina_nueva = stamina_antes - costo_stamina
    db_helper.set_actividad(user_id, "recoleccion")
    # Mensaje de espera + delay de 90 segundos
    await update.effective_message.reply_text(
        f"⏳ Recolectando recursos en la zona... espera 90 segundos.\n"
        f"⚡ Stamina: {stamina_antes}/{stamina_max} | Coste: -{costo_stamina} → Quedan: {stamina_nueva}/{stamina_max}"
    )
    await asyncio.sleep(90)
    # Ahora resolver el resultado
    if random.random() < zona_config['prob_fallo']:
        frase = random.choice(zona_config['frases_fallo'])
        db_helper.set_actividad(user_id, None)
        await update.effective_message.reply_text(
            f"❌ {frase}\n\n⚡ Stamina restante: {stamina_nueva}/{stamina_max}"
        )
        return
    if random.random() < zona_config['prob_monstruo'] and zona_config['monstruos']:
        monstruos = zona_config['monstruos']
        r = random.random()
        acum = 0
        monstruo_elegido = None
        for m in monstruos:
            acum += m['probabilidad']
            if r <= acum:
                monstruo_elegido = m
                break
        if monstruo_elegido:
            nivel_jug = jug.get("nivel", 1)
            monstruo_real = _cargar_monstruo_real(
                zona_config['zona_id'], monstruo_elegido['id'],
                CARPETA_POR_COLOR.get(color_zona, 'zonas azules')
            )
            if not monstruo_real:
                # Monstruo inline cuando no existe el archivo
                monstruo_real = {
                    'nombre': monstruo_elegido['nombre'],
                    'descripcion': "Una criatura salvaje que acecha esta zona.",
                    'vida_max': 200 + nivel_jug * 30,
                    'daño': 25 + nivel_jug * 8,
                    'defensa': 14 + nivel_jug * 3,
                    'xp': 25 + nivel_jug * 8,
                    'oro': random.randint(5, 15 + nivel_jug * 2),
                    'drops': []
                }
            enemigo = {
                'nombre': monstruo_real['nombre'],
                'descripcion': monstruo_real.get('descripcion', ''),
                'vida_max': monstruo_real['vida_max'],
                'vida_actual': monstruo_real['vida_max'],
                'daño': monstruo_real['daño'],
                'defensa': monstruo_real['defensa'],
                'xp': monstruo_real['xp'],
                'oro': monstruo_real['oro'],
                'drops': monstruo_real.get('drops', [])
            }
            tipo_combate_map = {
                'azul': 'pve_zona_azul', 'amarilla': 'pve_zona_amarilla',
                'roja': 'pve_zona_roja', 'negra': 'pve_zona_negra'
            }
            tipo_combate = tipo_combate_map.get(color_zona, 'pve_zona_azul')
            await update.effective_message.reply_text(
                f"⚔️ ¡Un *{monstruo_real['nombre']}* aparece mientras recolectas! Prepárate para combatir.",
                parse_mode="Markdown"
            )
            await iniciar_combate(update, context, user_id, 0, tipo_combate, enemigo=enemigo, datos_extra={})
            return
    db_helper.set_actividad(user_id, None)
    oro_ganado, materiales = _otorgar_recompensa(user_id, zona_config)
    if materiales:
        lineas = [f"• {nombre}: *x{cant}*" for nombre, cant in materiales]
        texto_mat = "\n".join(lineas)
    else:
        texto_mat = "_(ninguno esta vez)_"
    await update.effective_message.reply_text(
        f"✅ *Recolección completada*\n\n"
        f"📦 *Materiales obtenidos:*\n{texto_mat}\n\n"
        f"🪙 Oro ganado: *{oro_ganado}*\n"
        f"⚡ Stamina restante: {stamina_nueva}/{stamina_max}",
        parse_mode="Markdown"
    )

def registrar_handlers(app):
    app.add_handler(CommandHandler("recolectar", cmd_recolectar))

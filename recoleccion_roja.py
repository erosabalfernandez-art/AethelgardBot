#!/usr/bin/env python3
# recoleccion_roja.py
# Generado automáticamente por generar_recoleccion.py para zona roja

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
    'Tierras Magmáticas Alianza': {
        'zona_id': 6,
        'nivel_zona': 45,
        'prob_fallo': 0.35,
        'prob_monstruo': 0.45,
        'min_oro': 10,
        'max_oro': 30,
        'prob_oro_extra': 0.08,
        'frases_fallo': ['Te distraes con el paisaje y no encuentras nada útil.', 'El terreno es demasiado duro, no logras extraer nada.', 'Un ruido te asusta y abandonas la recolección.', 'Parece que hoy no es tu día, no aparece nada.', 'Tus herramientas resbalan y no obtienes recursos.'],
        'materiales': [
            {'id': 'material_43', 'nombre': 'Garra de Ardiente Menor', 'probabilidad': 0.2664, 'min': 1, 'max': 1},
            {'id': 'material_20', 'nombre': 'Inestable Esquirla Menor', 'probabilidad': 0.2664, 'min': 1, 'max': 1},
            {'id': 'material_11', 'nombre': 'Sangriento Polvo Puro', 'probabilidad': 0.2336, 'min': 1, 'max': 1},
            {'id': 'material_21', 'nombre': 'Gema Fracturado Sólido', 'probabilidad': 0.2336, 'min': 1, 'max': 1},
        ],
        'monstruos': [
            {'id': 'rojanormales61', 'nombre': 'Diablillo de Lava', 'probabilidad': 0.5000},
            {'id': 'rojanormales62', 'nombre': 'Golem de Ceniza', 'probabilidad': 0.5000},
        ]
    },
    'Cima del Dragón Alianza': {
        'zona_id': 7,
        'nivel_zona': 50,
        'prob_fallo': 0.35,
        'prob_monstruo': 0.45,
        'min_oro': 10,
        'max_oro': 30,
        'prob_oro_extra': 0.08,
        'frases_fallo': ['Te distraes con el paisaje y no encuentras nada útil.', 'El terreno es demasiado duro, no logras extraer nada.', 'Un ruido te asusta y abandonas la recolección.', 'Parece que hoy no es tu día, no aparece nada.', 'Tus herramientas resbalan y no obtienes recursos.'],
        'materiales': [
            {'id': 'material_17', 'nombre': 'Fragmento Sangriento Medio', 'probabilidad': 0.2415, 'min': 1, 'max': 1},
            {'id': 'material_63', 'nombre': 'Resina Sangriento Estable', 'probabilidad': 0.2415, 'min': 1, 'max': 1},
            {'id': 'material_134', 'nombre': 'Polvo Feroz Medio', 'probabilidad': 0.2415, 'min': 1, 'max': 1},
            {'id': 'material_138', 'nombre': 'Escama de Feroz Roto', 'probabilidad': 0.2755, 'min': 1, 'max': 1},
        ],
        'monstruos': [
            {'id': 'rojanormales71', 'nombre': 'Salamandra Ígnea', 'probabilidad': 0.5000},
            {'id': 'rojanormales72', 'nombre': 'Murciélago de Fuego', 'probabilidad': 0.5000},
        ]
    },
    'Forja Abandonada Alianza': {
        'zona_id': 8,
        'nivel_zona': 55,
        'prob_fallo': 0.35,
        'prob_monstruo': 0.45,
        'min_oro': 10,
        'max_oro': 30,
        'prob_oro_extra': 0.08,
        'frases_fallo': ['Te distraes con el paisaje y no encuentras nada útil.', 'El terreno es demasiado duro, no logras extraer nada.', 'Un ruido te asusta y abandonas la recolección.', 'Parece que hoy no es tu día, no aparece nada.', 'Tus herramientas resbalan y no obtienes recursos.'],
        'materiales': [
            {'id': 'material_29', 'nombre': 'Resina Feroz Sólido', 'probabilidad': 0.2645, 'min': 1, 'max': 1},
            {'id': 'material_72', 'nombre': 'Inestable Escama Eterno', 'probabilidad': 0.2355, 'min': 1, 'max': 1},
            {'id': 'material_115', 'nombre': 'Resina Fracturado Roto', 'probabilidad': 0.2355, 'min': 1, 'max': 1},
            {'id': 'material_8', 'nombre': 'Escama Inestable Refinado', 'probabilidad': 0.2645, 'min': 1, 'max': 1},
        ],
        'monstruos': [
            {'id': 'rojanormales81', 'nombre': 'Elemental de Humo', 'probabilidad': 0.5000},
            {'id': 'rojanormales82', 'nombre': 'Esclavo de Lava', 'probabilidad': 0.5000},
        ]
    },
    'Tierras Magmáticas Imperio': {
        'zona_id': 17,
        'nivel_zona': 45,
        'prob_fallo': 0.35,
        'prob_monstruo': 0.45,
        'min_oro': 10,
        'max_oro': 30,
        'prob_oro_extra': 0.08,
        'frases_fallo': ['Te distraes con el paisaje y no encuentras nada útil.', 'El terreno es demasiado duro, no logras extraer nada.', 'Un ruido te asusta y abandonas la recolección.', 'Parece que hoy no es tu día, no aparece nada.', 'Tus herramientas resbalan y no obtienes recursos.'],
        'materiales': [
            {'id': 'material_22', 'nombre': 'Inestable Colmillo Sólido', 'probabilidad': 0.2336, 'min': 1, 'max': 1},
            {'id': 'material_34', 'nombre': 'Resina de Feroz Refinado', 'probabilidad': 0.2336, 'min': 1, 'max': 1},
            {'id': 'material_144', 'nombre': 'Núcleo de Feroz Simple', 'probabilidad': 0.2664, 'min': 1, 'max': 1},
            {'id': 'material_137', 'nombre': 'Feroz Placa Roto', 'probabilidad': 0.2664, 'min': 1, 'max': 1},
        ],
        'monstruos': [
            {'id': 'rojanormales171', 'nombre': 'Legionario de Fuego', 'probabilidad': 0.5000},
            {'id': 'rojanormales172', 'nombre': 'Elemental de Piedra', 'probabilidad': 0.5000},
        ]
    },
    'Cima del Dragón Imperio': {
        'zona_id': 18,
        'nivel_zona': 50,
        'prob_fallo': 0.35,
        'prob_monstruo': 0.45,
        'min_oro': 10,
        'max_oro': 30,
        'prob_oro_extra': 0.08,
        'frases_fallo': ['Te distraes con el paisaje y no encuentras nada útil.', 'El terreno es demasiado duro, no logras extraer nada.', 'Un ruido te asusta y abandonas la recolección.', 'Parece que hoy no es tu día, no aparece nada.', 'Tus herramientas resbalan y no obtienes recursos.'],
        'materiales': [
            {'id': 'material_62', 'nombre': 'Feroz Colmillo Sólido', 'probabilidad': 0.2397, 'min': 1, 'max': 1},
            {'id': 'material_93', 'nombre': 'Resina Feroz Eterno', 'probabilidad': 0.2134, 'min': 1, 'max': 1},
            {'id': 'material_26', 'nombre': 'Polvo de Sangriento Simple', 'probabilidad': 0.2735, 'min': 1, 'max': 1},
            {'id': 'material_55', 'nombre': 'Alma de Inestable Menor', 'probabilidad': 0.2735, 'min': 1, 'max': 1},
        ],
        'monstruos': [
            {'id': 'rojanormales181', 'nombre': 'Acólito del Dragón', 'probabilidad': 0.5000},
            {'id': 'rojanormales182', 'nombre': 'Gusano de Lava', 'probabilidad': 0.5000},
        ]
    },
    'Forja Abandonada Imperio': {
        'zona_id': 19,
        'nivel_zona': 55,
        'prob_fallo': 0.35,
        'prob_monstruo': 0.45,
        'min_oro': 10,
        'max_oro': 30,
        'prob_oro_extra': 0.08,
        'frases_fallo': ['Te distraes con el paisaje y no encuentras nada útil.', 'El terreno es demasiado duro, no logras extraer nada.', 'Un ruido te asusta y abandonas la recolección.', 'Parece que hoy no es tu día, no aparece nada.', 'Tus herramientas resbalan y no obtienes recursos.'],
        'materiales': [
            {'id': 'material_146', 'nombre': 'Cristal Ardiente Estable', 'probabilidad': 0.2397, 'min': 1, 'max': 1},
            {'id': 'material_141', 'nombre': 'Lingote de Ardiente Divino', 'probabilidad': 0.2134, 'min': 1, 'max': 1},
            {'id': 'material_124', 'nombre': 'Alma de Sangriento Menor', 'probabilidad': 0.2735, 'min': 1, 'max': 1},
            {'id': 'material_125', 'nombre': 'Esquirla Ardiente Roto', 'probabilidad': 0.2735, 'min': 1, 'max': 1},
        ],
        'monstruos': [
            {'id': 'rojanormales191', 'nombre': 'Esbirro del Fuego', 'probabilidad': 0.5000},
            {'id': 'rojanormales192', 'nombre': 'Lava Lenta', 'probabilidad': 0.5000},
        ]
    },
    'Tierras Magmáticas Sindicato': {
        'zona_id': 28,
        'nivel_zona': 45,
        'prob_fallo': 0.35,
        'prob_monstruo': 0.45,
        'min_oro': 10,
        'max_oro': 30,
        'prob_oro_extra': 0.08,
        'frases_fallo': ['Te distraes con el paisaje y no encuentras nada útil.', 'El terreno es demasiado duro, no logras extraer nada.', 'Un ruido te asusta y abandonas la recolección.', 'Parece que hoy no es tu día, no aparece nada.', 'Tus herramientas resbalan y no obtienes recursos.'],
        'materiales': [
            {'id': 'material_57', 'nombre': 'Savia Feroz Refinado', 'probabilidad': 0.2481, 'min': 1, 'max': 1},
            {'id': 'material_115', 'nombre': 'Resina Fracturado Roto', 'probabilidad': 0.2830, 'min': 1, 'max': 1},
            {'id': 'material_87', 'nombre': 'Corazón de Feroz Medio', 'probabilidad': 0.2481, 'min': 1, 'max': 1},
            {'id': 'material_80', 'nombre': 'Sangriento Resina Eterno', 'probabilidad': 0.2208, 'min': 1, 'max': 1},
        ],
        'monstruos': [
            {'id': 'rojanormales281', 'nombre': 'Minero Esclavo', 'probabilidad': 0.5000},
            {'id': 'rojanormales282', 'nombre': 'Perro de Fuego', 'probabilidad': 0.5000},
        ]
    },
    'Cima del Dragón Sindicato': {
        'zona_id': 29,
        'nivel_zona': 50,
        'prob_fallo': 0.35,
        'prob_monstruo': 0.45,
        'min_oro': 10,
        'max_oro': 30,
        'prob_oro_extra': 0.08,
        'frases_fallo': ['Te distraes con el paisaje y no encuentras nada útil.', 'El terreno es demasiado duro, no logras extraer nada.', 'Un ruido te asusta y abandonas la recolección.', 'Parece que hoy no es tu día, no aparece nada.', 'Tus herramientas resbalan y no obtienes recursos.'],
        'materiales': [
            {'id': 'material_135', 'nombre': 'Garra Feroz Refinado', 'probabilidad': 0.2397, 'min': 1, 'max': 1},
            {'id': 'material_110', 'nombre': 'Esquirla Fracturado Mayor', 'probabilidad': 0.2134, 'min': 1, 'max': 1},
            {'id': 'material_111', 'nombre': 'Hilo Ardiente Menor', 'probabilidad': 0.2735, 'min': 1, 'max': 1},
            {'id': 'material_86', 'nombre': 'Tela de Feroz Roto', 'probabilidad': 0.2735, 'min': 1, 'max': 1},
        ],
        'monstruos': [
            {'id': 'rojanormales291', 'nombre': 'Ladrón de Dragones', 'probabilidad': 0.5000},
            {'id': 'rojanormales292', 'nombre': 'Elemental de Aire Caliente', 'probabilidad': 0.5000},
        ]
    },
    'Forja Abandonada Sindicato': {
        'zona_id': 30,
        'nivel_zona': 55,
        'prob_fallo': 0.35,
        'prob_monstruo': 0.45,
        'min_oro': 10,
        'max_oro': 30,
        'prob_oro_extra': 0.08,
        'frases_fallo': ['Te distraes con el paisaje y no encuentras nada útil.', 'El terreno es demasiado duro, no logras extraer nada.', 'Un ruido te asusta y abandonas la recolección.', 'Parece que hoy no es tu día, no aparece nada.', 'Tus herramientas resbalan y no obtienes recursos.'],
        'materiales': [
            {'id': 'material_81', 'nombre': 'Trozo de Ardiente Medio', 'probabilidad': 0.2571, 'min': 1, 'max': 1},
            {'id': 'material_61', 'nombre': 'Feroz Colmillo Puro', 'probabilidad': 0.2571, 'min': 1, 'max': 1},
            {'id': 'material_96', 'nombre': 'Feroz Núcleo Medio', 'probabilidad': 0.2571, 'min': 1, 'max': 1},
            {'id': 'material_123', 'nombre': 'Ardiente Colmillo Mayor', 'probabilidad': 0.2288, 'min': 1, 'max': 1},
        ],
        'monstruos': [
            {'id': 'rojanormales301', 'nombre': 'Mercenario de Fuego', 'probabilidad': 0.5000},
            {'id': 'rojanormales302', 'nombre': 'Trampa Viviente', 'probabilidad': 0.5000},
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
                    'descripcion': "Una bestia peligrosa forjada en el calor de esta zona.",
                    'vida_max': 320 + nivel_jug * 45,
                    'daño': 38 + nivel_jug * 12,
                    'defensa': 20 + nivel_jug * 5,
                    'xp': 45 + nivel_jug * 12,
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

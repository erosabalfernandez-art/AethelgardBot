#!/usr/bin/env python3
# recoleccion_negra.py
# Generado automáticamente por generar_recoleccion.py para zona negra

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
    'Abismo Alianza': {
        'zona_id': 9,
        'nivel_zona': 70,
        'prob_fallo': 0.50,
        'prob_monstruo': 0.65,
        'min_oro': 20,
        'max_oro': 65,
        'prob_oro_extra': 0.08,
        'frases_fallo': ['Te distraes con el paisaje y no encuentras nada útil.', 'El terreno es demasiado duro, no logras extraer nada.', 'Un ruido te asusta y abandonas la recolección.', 'Parece que hoy no es tu día, no aparece nada.', 'Tus herramientas resbalan y no obtienes recursos.'],
        'materiales': [
            {'id': 'material_127', 'nombre': 'Polvo Difunto Roto', 'probabilidad': 0.2725, 'min': 1, 'max': 1},
            {'id': 'material_147', 'nombre': 'Lingote de Vacío Simple', 'probabilidad': 0.2725, 'min': 1, 'max': 1},
            {'id': 'material_40', 'nombre': 'Fragmento de Difunto Mayor', 'probabilidad': 0.2275, 'min': 1, 'max': 1},
            {'id': 'material_131', 'nombre': 'Alma de Eterno Legendario', 'probabilidad': 0.2275, 'min': 1, 'max': 1},
        ],
        'monstruos': [
            {'id': 'negranormales91', 'nombre': 'Sombrío', 'probabilidad': 0.5000},
            {'id': 'negranormales92', 'nombre': 'No-muerto Rasgador', 'probabilidad': 0.5000},
        ]
    },
    'Costa de los Lamentos Alianza': {
        'zona_id': 10,
        'nivel_zona': 75,
        'prob_fallo': 0.50,
        'prob_monstruo': 0.65,
        'min_oro': 22,
        'max_oro': 68,
        'prob_oro_extra': 0.08,
        'frases_fallo': ['Te distraes con el paisaje y no encuentras nada útil.', 'El terreno es demasiado duro, no logras extraer nada.', 'Un ruido te asusta y abandonas la recolección.', 'Parece que hoy no es tu día, no aparece nada.', 'Tus herramientas resbalan y no obtienes recursos.'],
        'materiales': [
            {'id': 'material_109', 'nombre': 'Hilo de Difunto Roto', 'probabilidad': 0.2608, 'min': 1, 'max': 1},
            {'id': 'material_40', 'nombre': 'Fragmento de Difunto Mayor', 'probabilidad': 0.2177, 'min': 1, 'max': 1},
            {'id': 'material_127', 'nombre': 'Polvo Difunto Roto', 'probabilidad': 0.2608, 'min': 1, 'max': 1},
            {'id': 'material_102', 'nombre': 'Cristal de Abisal Roto', 'probabilidad': 0.2608, 'min': 1, 'max': 1},
        ],
        'monstruos': [
            {'id': 'negranormales101', 'nombre': 'Aparición Susurrante', 'probabilidad': 0.5000},
            {'id': 'negranormales102', 'nombre': 'Carroñero de Huesos', 'probabilidad': 0.5000},
        ]
    },
    'Nexo de la Nada Alianza': {
        'zona_id': 11,
        'nivel_zona': 80,
        'prob_fallo': 0.50,
        'prob_monstruo': 0.65,
        'min_oro': 24,
        'max_oro': 70,
        'prob_oro_extra': 0.08,
        'frases_fallo': ['Te distraes con el paisaje y no encuentras nada útil.', 'El terreno es demasiado duro, no logras extraer nada.', 'Un ruido te asusta y abandonas la recolección.', 'Parece que hoy no es tu día, no aparece nada.', 'Tus herramientas resbalan y no obtienes recursos.'],
        'materiales': [
            {'id': 'material_127', 'nombre': 'Polvo Difunto Roto', 'probabilidad': 0.2608, 'min': 1, 'max': 1},
            {'id': 'material_109', 'nombre': 'Hilo de Difunto Roto', 'probabilidad': 0.2608, 'min': 1, 'max': 1},
            {'id': 'material_40', 'nombre': 'Fragmento de Difunto Mayor', 'probabilidad': 0.2177, 'min': 1, 'max': 1},
            {'id': 'material_102', 'nombre': 'Cristal de Abisal Roto', 'probabilidad': 0.2608, 'min': 1, 'max': 1},
        ],
        'monstruos': [
            {'id': 'negranormales111', 'nombre': 'Ojo que Todo lo Ve', 'probabilidad': 0.5000},
            {'id': 'negranormales112', 'nombre': 'Portador del Vacío', 'probabilidad': 0.5000},
        ]
    },
    'Abismo Imperio': {
        'zona_id': 20,
        'nivel_zona': 70,
        'prob_fallo': 0.50,
        'prob_monstruo': 0.65,
        'min_oro': 20,
        'max_oro': 65,
        'prob_oro_extra': 0.08,
        'frases_fallo': ['Te distraes con el paisaje y no encuentras nada útil.', 'El terreno es demasiado duro, no logras extraer nada.', 'Un ruido te asusta y abandonas la recolección.', 'Parece que hoy no es tu día, no aparece nada.', 'Tus herramientas resbalan y no obtienes recursos.'],
        'materiales': [
            {'id': 'material_109', 'nombre': 'Hilo de Difunto Roto', 'probabilidad': 0.2608, 'min': 1, 'max': 1},
            {'id': 'material_150', 'nombre': 'Abisal Lingote Menor', 'probabilidad': 0.2608, 'min': 1, 'max': 1},
            {'id': 'material_40', 'nombre': 'Fragmento de Difunto Mayor', 'probabilidad': 0.2177, 'min': 1, 'max': 1},
            {'id': 'material_118', 'nombre': 'Abisal Trozo Frágil', 'probabilidad': 0.2608, 'min': 1, 'max': 1},
        ],
        'monstruos': [
            {'id': 'negranormales201', 'nombre': 'Centinela No-muerto', 'probabilidad': 1.0000},
        ]
    },
    'Costa de los Lamentos Imperio': {
        'zona_id': 21,
        'nivel_zona': 75,
        'prob_fallo': 0.50,
        'prob_monstruo': 0.65,
        'min_oro': 22,
        'max_oro': 68,
        'prob_oro_extra': 0.08,
        'frases_fallo': ['Te distraes con el paisaje y no encuentras nada útil.', 'El terreno es demasiado duro, no logras extraer nada.', 'Un ruido te asusta y abandonas la recolección.', 'Parece que hoy no es tu día, no aparece nada.', 'Tus herramientas resbalan y no obtienes recursos.'],
        'materiales': [
            {'id': 'material_127', 'nombre': 'Polvo Difunto Roto', 'probabilidad': 0.2608, 'min': 1, 'max': 1},
            {'id': 'material_40', 'nombre': 'Fragmento de Difunto Mayor', 'probabilidad': 0.2177, 'min': 1, 'max': 1},
            {'id': 'material_109', 'nombre': 'Hilo de Difunto Roto', 'probabilidad': 0.2608, 'min': 1, 'max': 1},
            {'id': 'material_118', 'nombre': 'Abisal Trozo Frágil', 'probabilidad': 0.2608, 'min': 1, 'max': 1},
        ],
        'monstruos': [
            {'id': 'negranormales211', 'nombre': 'Marinero Fantasma', 'probabilidad': 1.0000},
        ]
    },
    'Nexo de la Nada Imperio': {
        'zona_id': 22,
        'nivel_zona': 80,
        'prob_fallo': 0.50,
        'prob_monstruo': 0.65,
        'min_oro': 24,
        'max_oro': 70,
        'prob_oro_extra': 0.08,
        'frases_fallo': ['Te distraes con el paisaje y no encuentras nada útil.', 'El terreno es demasiado duro, no logras extraer nada.', 'Un ruido te asusta y abandonas la recolección.', 'Parece que hoy no es tu día, no aparece nada.', 'Tus herramientas resbalan y no obtienes recursos.'],
        'materiales': [
            {'id': 'material_102', 'nombre': 'Cristal de Abisal Roto', 'probabilidad': 0.2608, 'min': 1, 'max': 1},
            {'id': 'material_40', 'nombre': 'Fragmento de Difunto Mayor', 'probabilidad': 0.2177, 'min': 1, 'max': 1},
            {'id': 'material_118', 'nombre': 'Abisal Trozo Frágil', 'probabilidad': 0.2608, 'min': 1, 'max': 1},
            {'id': 'material_147', 'nombre': 'Lingote de Vacío Simple', 'probabilidad': 0.2608, 'min': 1, 'max': 1},
        ],
        'monstruos': [
            {'id': 'negranormales221', 'nombre': 'Sirviente del Vacío', 'probabilidad': 1.0000},
        ]
    },
    'Abismo Sindicato': {
        'zona_id': 31,
        'nivel_zona': 70,
        'prob_fallo': 0.50,
        'prob_monstruo': 0.65,
        'min_oro': 20,
        'max_oro': 65,
        'prob_oro_extra': 0.08,
        'frases_fallo': ['Te distraes con el paisaje y no encuentras nada útil.', 'El terreno es demasiado duro, no logras extraer nada.', 'Un ruido te asusta y abandonas la recolección.', 'Parece que hoy no es tu día, no aparece nada.', 'Tus herramientas resbalan y no obtienes recursos.'],
        'materiales': [
            {'id': 'material_150', 'nombre': 'Abisal Lingote Menor', 'probabilidad': 0.2794, 'min': 1, 'max': 1},
            {'id': 'material_131', 'nombre': 'Alma de Eterno Legendario', 'probabilidad': 0.2332, 'min': 1, 'max': 1},
            {'id': 'material_40', 'nombre': 'Fragmento de Difunto Mayor', 'probabilidad': 0.2332, 'min': 1, 'max': 1},
            {'id': 'material_4', 'nombre': 'Garra Difunto Estable', 'probabilidad': 0.2542, 'min': 1, 'max': 1},
        ],
        'monstruos': [
            {'id': 'negranormales311', 'nombre': 'Espía Sombra', 'probabilidad': 1.0000},
        ]
    },
    'Costa de los Lamentos Sindicato': {
        'zona_id': 32,
        'nivel_zona': 75,
        'prob_fallo': 0.50,
        'prob_monstruo': 0.65,
        'min_oro': 22,
        'max_oro': 68,
        'prob_oro_extra': 0.08,
        'frases_fallo': ['Te distraes con el paisaje y no encuentras nada útil.', 'El terreno es demasiado duro, no logras extraer nada.', 'Un ruido te asusta y abandonas la recolección.', 'Parece que hoy no es tu día, no aparece nada.', 'Tus herramientas resbalan y no obtienes recursos.'],
        'materiales': [
            {'id': 'material_127', 'nombre': 'Polvo Difunto Roto', 'probabilidad': 0.2608, 'min': 1, 'max': 1},
            {'id': 'material_40', 'nombre': 'Fragmento de Difunto Mayor', 'probabilidad': 0.2177, 'min': 1, 'max': 1},
            {'id': 'material_109', 'nombre': 'Hilo de Difunto Roto', 'probabilidad': 0.2608, 'min': 1, 'max': 1},
            {'id': 'material_102', 'nombre': 'Cristal de Abisal Roto', 'probabilidad': 0.2608, 'min': 1, 'max': 1},
        ],
        'monstruos': [
            {'id': 'negranormales321', 'nombre': 'Contrabandista', 'probabilidad': 1.0000},
        ]
    },
    'Nexo de la Nada Sindicato': {
        'zona_id': 33,
        'nivel_zona': 80,
        'prob_fallo': 0.50,
        'prob_monstruo': 0.65,
        'min_oro': 24,
        'max_oro': 70,
        'prob_oro_extra': 0.08,
        'frases_fallo': ['Te distraes con el paisaje y no encuentras nada útil.', 'El terreno es demasiado duro, no logras extraer nada.', 'Un ruido te asusta y abandonas la recolección.', 'Parece que hoy no es tu día, no aparece nada.', 'Tus herramientas resbalan y no obtienes recursos.'],
        'materiales': [
            {'id': 'material_150', 'nombre': 'Abisal Lingote Menor', 'probabilidad': 0.2500, 'min': 1, 'max': 1},
            {'id': 'material_109', 'nombre': 'Hilo de Difunto Roto', 'probabilidad': 0.2500, 'min': 1, 'max': 1},
            {'id': 'material_118', 'nombre': 'Abisal Trozo Frágil', 'probabilidad': 0.2500, 'min': 1, 'max': 1},
            {'id': 'material_147', 'nombre': 'Lingote de Vacío Simple', 'probabilidad': 0.2500, 'min': 1, 'max': 1},
        ],
        'monstruos': [
            {'id': 'negranormales331', 'nombre': 'Científico Loco', 'probabilidad': 1.0000},
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
                    'descripcion': "Un ser oscuro y corrupto que emerge de las profundidades de esta zona.",
                    'vida_max': 500 + nivel_jug * 65,
                    'daño': 55 + nivel_jug * 16,
                    'defensa': 28 + nivel_jug * 7,
                    'xp': 70 + nivel_jug * 20,
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

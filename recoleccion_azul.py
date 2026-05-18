#!/usr/bin/env python3
# recoleccion_azul.py
# Generado automáticamente por generar_recoleccion.py para zona azul

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
    'Bosque Alianza': {
        'zona_id': 2,
        'nivel_zona': 1,
        'prob_fallo': 0.20,
        'prob_monstruo': 0.20,
        'min_oro': 2,
        'max_oro': 7,
        'prob_oro_extra': 0.025,
        'frases_fallo': ['Te distraes con el paisaje y no encuentras nada útil.', 'El terreno es demasiado duro, no logras extraer nada.', 'Un ruido te asusta y abandonas la recolección.', 'Parece que hoy no es tu día, no aparece nada.', 'Tus herramientas resbalan y no obtienes recursos.'],
        'materiales': [
            {'id': 'material_69', 'nombre': 'Resina Ligero Roto', 'probabilidad': 0.0593, 'min': 1, 'max': 1},
            {'id': 'material_128', 'nombre': 'Hilo Ligero Menor', 'probabilidad': 0.0593, 'min': 1, 'max': 1},
            {'id': 'material_14', 'nombre': 'Tela de Suave Frágil', 'probabilidad': 0.0593, 'min': 1, 'max': 1},
            {'id': 'material_88', 'nombre': 'Escama Suave Frágil', 'probabilidad': 0.0593, 'min': 1, 'max': 1},
            {'id': 'material_38', 'nombre': 'Trozo Brillante Medio', 'probabilidad': 0.0311, 'min': 1, 'max': 1},
            {'id': 'material_83', 'nombre': 'Claro Resina Medio', 'probabilidad': 0.0311, 'min': 1, 'max': 1},
            {'id': 'material_48', 'nombre': 'Tela de Claro Roto', 'probabilidad': 0.0593, 'min': 1, 'max': 1},
            {'id': 'material_75', 'nombre': 'Ligero Corazón Roto', 'probabilidad': 0.0593, 'min': 1, 'max': 1},
            {'id': 'material_68', 'nombre': 'Alma de Templado Simple', 'probabilidad': 0.0593, 'min': 1, 'max': 1},
            {'id': 'material_120', 'nombre': 'Colmillo de Ligero Simple', 'probabilidad': 0.0593, 'min': 1, 'max': 1},
            {'id': 'material_15', 'nombre': 'Corazón de Suave Estable', 'probabilidad': 0.0311, 'min': 1, 'max': 1},
            {'id': 'material_120', 'nombre': 'Colmillo de Ligero Simple', 'probabilidad': 0.0211, 'min': 1, 'max': 1},
            {'id': 'material_44', 'nombre': 'Brillante Polvo Menor', 'probabilidad': 0.0593, 'min': 1, 'max': 1},
            {'id': 'material_90', 'nombre': 'Hilo Templado Medio', 'probabilidad': 0.0311, 'min': 1, 'max': 1},
            {'id': 'material_104', 'nombre': 'Hilo Brillante Simple', 'probabilidad': 0.0593, 'min': 1, 'max': 1},
            {'id': 'material_104', 'nombre': 'Hilo Brillante Simple', 'probabilidad': 0.0211, 'min': 1, 'max': 1},
            {'id': 'material_13', 'nombre': 'Garra de Brillante Roto', 'probabilidad': 0.0593, 'min': 1, 'max': 1},
            {'id': 'material_18', 'nombre': 'Esquirla de Templado Simple', 'probabilidad': 0.0593, 'min': 1, 'max': 1},
            {'id': 'material_112', 'nombre': 'Savia de Brillante Simple', 'probabilidad': 0.0593, 'min': 1, 'max': 1},
            {'id': 'material_25', 'nombre': 'Hilo de Ligero Refinado', 'probabilidad': 0.0311, 'min': 1, 'max': 1},
            {'id': 'material_139', 'nombre': 'Claro Lingote Puro', 'probabilidad': 0.0311, 'min': 1, 'max': 1},
        ],
        'monstruos': [
            {'id': 'azulnormales21', 'nombre': 'Goblin Rastrero', 'probabilidad': 0.2000},
            {'id': 'azulnormales22', 'nombre': 'Lobo Sombrío', 'probabilidad': 0.2000},
            {'id': 'azulnormales23', 'nombre': 'Zancudo del Pantano', 'probabilidad': 0.2000},
            {'id': 'azulnormales24', 'nombre': 'Duende Espinoso', 'probabilidad': 0.2000},
            {'id': 'azulnormales25', 'nombre': 'Salamandra Azul', 'probabilidad': 0.2000},
        ]
    },
    'Bosque Imperio': {
        'zona_id': 13,
        'nivel_zona': 1,
        'prob_fallo': 0.20,
        'prob_monstruo': 0.20,
        'min_oro': 2,
        'max_oro': 7,
        'prob_oro_extra': 0.025,
        'frases_fallo': ['Te distraes con el paisaje y no encuentras nada útil.', 'El terreno es demasiado duro, no logras extraer nada.', 'Un ruido te asusta y abandonas la recolección.', 'Parece que hoy no es tu día, no aparece nada.', 'Tus herramientas resbalan y no obtienes recursos.'],
        'materiales': [
            {'id': 'material_41', 'nombre': 'Núcleo de Ligero Divino', 'probabilidad': 0.0296, 'min': 1, 'max': 1},
            {'id': 'material_36', 'nombre': 'Templado Gema Frágil', 'probabilidad': 0.0835, 'min': 1, 'max': 1},
            {'id': 'material_84', 'nombre': 'Lingote de Brillante Roto', 'probabilidad': 0.0835, 'min': 1, 'max': 1},
            {'id': 'material_1', 'nombre': 'Hilo de Ligero Estable', 'probabilidad': 0.0438, 'min': 1, 'max': 1},
            {'id': 'material_145', 'nombre': 'Polvo de Suave Estable', 'probabilidad': 0.0438, 'min': 1, 'max': 1},
            {'id': 'material_65', 'nombre': 'Templado Tela Eterno', 'probabilidad': 0.0296, 'min': 1, 'max': 1},
            {'id': 'material_28', 'nombre': 'Templado Savia Puro', 'probabilidad': 0.0438, 'min': 1, 'max': 1},
            {'id': 'material_77', 'nombre': 'Claro Hilo Refinado', 'probabilidad': 0.0438, 'min': 1, 'max': 1},
            {'id': 'material_18', 'nombre': 'Esquirla de Templado Simple', 'probabilidad': 0.0296, 'min': 1, 'max': 1},
            {'id': 'material_119', 'nombre': 'Escama Claro Pequeño', 'probabilidad': 0.0835, 'min': 1, 'max': 1},
            {'id': 'material_85', 'nombre': 'Claro Polvo Refinado', 'probabilidad': 0.0438, 'min': 1, 'max': 1},
            {'id': 'material_36', 'nombre': 'Templado Gema Frágil', 'probabilidad': 0.0296, 'min': 1, 'max': 1},
            {'id': 'material_97', 'nombre': 'Fragmento de Brillante Primordial', 'probabilidad': 0.0296, 'min': 1, 'max': 1},
            {'id': 'material_1', 'nombre': 'Hilo de Ligero Estable', 'probabilidad': 0.0224, 'min': 1, 'max': 1},
            {'id': 'material_35', 'nombre': 'Fragmento de Suave Medio', 'probabilidad': 0.0438, 'min': 1, 'max': 1},
            {'id': 'material_39', 'nombre': 'Gema Claro Estable', 'probabilidad': 0.0438, 'min': 1, 'max': 1},
            {'id': 'material_116', 'nombre': 'Tela Suave Sólido', 'probabilidad': 0.0438, 'min': 1, 'max': 1},
            {'id': 'material_97', 'nombre': 'Fragmento de Brillante Primordial', 'probabilidad': 0.0180, 'min': 1, 'max': 1},
            {'id': 'material_32', 'nombre': 'Templado Resina Frágil', 'probabilidad': 0.0835, 'min': 1, 'max': 1},
            {'id': 'material_149', 'nombre': 'Hilo de Ligero Pequeño', 'probabilidad': 0.0835, 'min': 1, 'max': 1},
            {'id': 'material_51', 'nombre': 'Resina de Templado Estable', 'probabilidad': 0.0438, 'min': 1, 'max': 1},
        ],
        'monstruos': [
            {'id': 'azulnormales131', 'nombre': 'Soldado No-muerto', 'probabilidad': 0.3333},
            {'id': 'azulnormales132', 'nombre': 'Cuervo Gigante', 'probabilidad': 0.3333},
            {'id': 'azulnormales133', 'nombre': 'Liana Voraz', 'probabilidad': 0.3333},
        ]
    },
    'Bosque Sindicato': {
        'zona_id': 24,
        'nivel_zona': 1,
        'prob_fallo': 0.20,
        'prob_monstruo': 0.20,
        'min_oro': 2,
        'max_oro': 7,
        'prob_oro_extra': 0.025,
        'frases_fallo': ['Te distraes con el paisaje y no encuentras nada útil.', 'El terreno es demasiado duro, no logras extraer nada.', 'Un ruido te asusta y abandonas la recolección.', 'Parece que hoy no es tu día, no aparece nada.', 'Tus herramientas resbalan y no obtienes recursos.'],
        'materiales': [
            {'id': 'material_6', 'nombre': 'Corazón de Brillante Divino', 'probabilidad': 0.0280, 'min': 1, 'max': 1},
            {'id': 'material_107', 'nombre': 'Trozo Templado Roto', 'probabilidad': 0.0789, 'min': 1, 'max': 1},
            {'id': 'material_67', 'nombre': 'Fragmento Brillante Puro', 'probabilidad': 0.0413, 'min': 1, 'max': 1},
            {'id': 'material_148', 'nombre': 'Ligero Núcleo Menor', 'probabilidad': 0.0789, 'min': 1, 'max': 1},
            {'id': 'material_132', 'nombre': 'Corazón de Ligero Simple', 'probabilidad': 0.0789, 'min': 1, 'max': 1},
            {'id': 'material_30', 'nombre': 'Núcleo Claro Sólido', 'probabilidad': 0.0413, 'min': 1, 'max': 1},
            {'id': 'material_54', 'nombre': 'Claro Corazón Refinado', 'probabilidad': 0.0413, 'min': 1, 'max': 1},
            {'id': 'material_116', 'nombre': 'Tela Suave Sólido', 'probabilidad': 0.0212, 'min': 1, 'max': 1},
            {'id': 'material_60', 'nombre': 'Lingote Ligero Simple', 'probabilidad': 0.0789, 'min': 1, 'max': 1},
            {'id': 'material_126', 'nombre': 'Ligero Polvo Frágil', 'probabilidad': 0.0789, 'min': 1, 'max': 1},
            {'id': 'material_70', 'nombre': 'Suave Savia Refinado', 'probabilidad': 0.0413, 'min': 1, 'max': 1},
            {'id': 'material_2', 'nombre': 'Fragmento de Brillante Primordial', 'probabilidad': 0.0280, 'min': 1, 'max': 1},
            {'id': 'material_100', 'nombre': 'Templado Resina Roto', 'probabilidad': 0.0789, 'min': 1, 'max': 1},
            {'id': 'material_24', 'nombre': 'Tela Claro Pequeño', 'probabilidad': 0.0789, 'min': 1, 'max': 1},
            {'id': 'material_3', 'nombre': 'Suave Cristal Divino', 'probabilidad': 0.0280, 'min': 1, 'max': 1},
            {'id': 'material_78', 'nombre': 'Claro Cristal Sólido', 'probabilidad': 0.0413, 'min': 1, 'max': 1},
            {'id': 'material_82', 'nombre': 'Ligero Tela Puro', 'probabilidad': 0.0413, 'min': 1, 'max': 1},
            {'id': 'material_47', 'nombre': 'Templado Escama Legendario', 'probabilidad': 0.0280, 'min': 1, 'max': 1},
            {'id': 'material_126', 'nombre': 'Ligero Polvo Frágil', 'probabilidad': 0.0280, 'min': 1, 'max': 1},
            {'id': 'material_3', 'nombre': 'Suave Cristal Divino', 'probabilidad': 0.0170, 'min': 1, 'max': 1},
            {'id': 'material_78', 'nombre': 'Claro Cristal Sólido', 'probabilidad': 0.0212, 'min': 1, 'max': 1},
        ],
        'monstruos': [
            {'id': 'azulnormales241', 'nombre': 'Asesino Sombrío', 'probabilidad': 0.3333},
            {'id': 'azulnormales242', 'nombre': 'Serpiente Arbórea', 'probabilidad': 0.3333},
            {'id': 'azulnormales243', 'nombre': 'Planta Venenosa', 'probabilidad': 0.3333},
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
    # Buscar primero en la carpeta indicada, luego en el directorio del bot
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
    # Marcar jugador como ocupado
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
                    'vida_max': 120 + nivel_jug * 20,
                    'daño': 16 + nivel_jug * 5,
                    'defensa': 8 + nivel_jug * 2,
                    'xp': 15 + nivel_jug * 5,
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
    try:
        import misiones as _mis
        _mis.completar_mision(user_id, "primera_recoleccion", context)
    except Exception:
        pass

def registrar_handlers(app):
    app.add_handler(CommandHandler("recolectar", cmd_recolectar))

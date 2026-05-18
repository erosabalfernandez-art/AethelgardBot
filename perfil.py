#!/usr/bin/env python3
# perfil.py
# Comando /perfil para mostrar estadísticas completas del jugador.
# Solo lectura. Botones para acceder a talentos, misiones, inventario y resetear talentos.

import sys
import os
import sqlite3
from datetime import datetime

# Añadir la raíz del proyecto para importar los módulos
ruta_raiz = os.path.join(os.path.dirname(__file__), '..')
if ruta_raiz not in sys.path:
    sys.path.insert(0, ruta_raiz)

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler

import db_helper
import clases
import progresion_clase
import inventario

def _esc_md(s: str) -> str:
    return str(s).replace("_", "\\_").replace("*", "\\*").replace("`", "\\`").replace("[", "\\[")

# ==================== FUNCIONES AUXILIARES ====================
def _puntos_talento_totales(user_id: int) -> int:
    """Calcula los puntos de talento totales según nivel (1 cada 5 niveles)."""
    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        return 0
    nivel = jug["nivel"]
    return nivel // 5

def _obtener_nivel_maestria_subclase(user_id: int) -> int:
    """Obtiene el nivel de maestría de subclase (1 por defecto)."""
    conn = sqlite3.connect(db_helper.DB_PATH)
    c = conn.cursor()
    c.execute('SELECT nivel FROM maestria_subclase WHERE jugador_id = ?', (user_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 1

def _aplicar_bonos_finales(user_id: int, stats: dict) -> dict:
    """Aplica bonos de talentos, insignias, paragon y prestigio a las stats.
       Nota: los talentos devuelven aumentos porcentuales (ej. daño: 1.0 = 100%),
       pero algunos pueden ser absolutos. Se maneja según el campo."""
    # Bonos de talentos (ya vienen como multiplicadores en progresion_clase.obtener_bonos_totales)
    bonos_talento = progresion_clase.obtener_bonos_totales(user_id)
    # bonos_talento tiene claves: "daño", "critico", "velocidad_ataque", "vida", "defensa", "regeneracion", "carga", "recoleccion_velocidad", "xp_extra"
    # En progresion_clase, los bonos de daño, vida, defensa son porcentuales (ej. 0.05 para +5%)
    # Para stats base, aplicamos multiplicadores
    stats["vida"] = int(stats["vida"] * (1 + bonos_talento.get("vida", 0)))
    stats["daño"] = int(stats["daño"] * (1 + bonos_talento.get("daño", 0)))
    stats["defensa"] = int(stats["defensa"] * (1 + bonos_talento.get("defensa", 0)))
    stats["carga"] = int(stats["carga"] * (1 + bonos_talento.get("carga", 0)))
    # Los crítico y velocidad_ataque son sumas absolutas
    stats["critico"] = bonos_talento.get("critico", 0)
    stats["velocidad"] = bonos_talento.get("velocidad_ataque", 0)

    # Bonos de insignias (porcentuales)
    bonos_insignias = progresion_clase.obtener_bonos_insignias(user_id)
    for key, percent in bonos_insignias.items():
        if key == "vida":
            stats["vida"] = int(stats["vida"] * (1 + percent / 100))
        elif key == "daño":
            stats["daño"] = int(stats["daño"] * (1 + percent / 100))
        elif key == "defensa":
            stats["defensa"] = int(stats["defensa"] * (1 + percent / 100))

    # Bonos de equipo (valores absolutos)
    bonos_equipo = inventario.calcular_bonos_equipo(user_id)
    for key, value in bonos_equipo.items():
        if key in stats:
            stats[key] += value

    # Bonos de paragon (porcentual)
    puntos_paragon = progresion_clase.calcular_puntos_paragon(user_id)
    if puntos_paragon > 0:
        bono_paragon = 1 + 0.002 * puntos_paragon
        stats["vida"] = int(stats["vida"] * bono_paragon)
        stats["daño"] = int(stats["daño"] * bono_paragon)
        stats["defensa"] = int(stats["defensa"] * bono_paragon)
        stats["carga"] = int(stats["carga"] * bono_paragon)

    # Bonos de prestigio (porcentual)
    bono_prestigio = progresion_clase.calcular_bono_prestigio(user_id)
    if bono_prestigio != 1.0:
        stats["vida"] = int(stats["vida"] * bono_prestigio)
        stats["daño"] = int(stats["daño"] * bono_prestigio)
        stats["defensa"] = int(stats["defensa"] * bono_prestigio)
        stats["carga"] = int(stats["carga"] * bono_prestigio)

    return stats

def _formatear_duracion_mision(fin_timestamp: str) -> str:
    """Devuelve tiempo restante formateado."""
    if not fin_timestamp:
        return "No activa"
    fin = datetime.fromisoformat(fin_timestamp)
    ahora = datetime.now()
    if fin <= ahora:
        return "Expirada"
    resto = fin - ahora
    dias = resto.days
    horas = resto.seconds // 3600
    if dias > 0:
        return f"{dias} d {horas} h"
    return f"{horas} h"

# ==================== COMANDO PRINCIPAL ====================
async def cmd_perfil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        await update.effective_message.reply_text("❌ No tienes un personaje. Usa /inicio para crear uno.")
        return

    # ====== Datos básicos ======
    nombre = jug["nombre_personaje"]
    clase = jug["clase"]
    subclase = jug.get("subclase") or "Ninguna"
    faccion = jug["faccion"]
    nivel = jug["nivel"]
    exp = jug["experiencia"]
    exp_necesaria = clases.calcular_experiencia_necesaria(nivel)
    reencarnaciones = jug.get("reencarnaciones", 0)
    prestigio_nivel = progresion_clase.obtener_nivel_prestigio(user_id)

    # ====== Recursos ======
    oro = jug.get("oro", 0)
    eternium = jug.get("eternium", 0)
    creditos = jug.get("creditos_vacio", 0)
    reputacion = jug.get("reputacion", 0)

    # ====== Estadísticas base (sin bonos) ======
    vida_base = clases.calcular_vida_maxima(clase, nivel, reencarnaciones)
    daño_base = clases.calcular_daño_base(clase, nivel, reencarnaciones)
    defensa_base = clases.calcular_defensa(clase, nivel, reencarnaciones)
    carga_base = clases.calcular_carga_maxima(clase, nivel, reencarnaciones)

    stats = {"vida": vida_base, "daño": daño_base, "defensa": defensa_base, "carga": carga_base}
    stats = _aplicar_bonos_finales(user_id, stats)

    # ====== Inventario resumen ======
    inv = db_helper.obtener_inventario(user_id)
    num_items = sum(it["cantidad"] for it in inv)

    # ====== Equipo equipado ======
    equip = inventario.obtener_equipamiento(user_id)
    texto_equipo = ""
    if equip["arma"]:
        texto_equipo += f"⚔️ Arma: {equip['arma']}\n"
    if equip["armadura"]:
        texto_equipo += f"🛡️ Armadura: {equip['armadura']}\n"
    if equip["montura"]:
        texto_equipo += f"🐎 Montura: {equip['montura']}\n"
    if not texto_equipo:
        texto_equipo = "Nada equipado"

    # ====== Progresión especial ======
    puntos_totales = _puntos_talento_totales(user_id)
    puntos_gastados = progresion_clase.talentos_gastados(user_id)
    puntos_disponibles = puntos_totales - puntos_gastados

    gloria_total = progresion_clase.obtener_gloria_total(user_id)
    titulos_gloria = progresion_clase.obtener_titulos_gloria(user_id)
    num_titulos = len(titulos_gloria)

    puntos_paragon = progresion_clase.calcular_puntos_paragon(user_id)
    maestria_subclase = _obtener_nivel_maestria_subclase(user_id)

    hitos = progresion_clase.obtener_hitos_reclamados(user_id)
    hitos_alcanzados = len(hitos)

    # Misión semanal
    mision = progresion_clase.obtener_mision_activa(user_id)
    texto_mision = ""
    if mision:
        progreso = mision["progreso"]
        objetivo = mision["objetivo_cantidad"]
        recompensa = mision["recompensa"]
        tiempo_rest = _formatear_duracion_mision(mision.get("fecha_fin"))
        texto_mision = f"📜 {mision['objetivo_tipo'].replace('_', ' ')}: {progreso}/{objetivo}\n🎁 {recompensa}\n⏳ {tiempo_rest}"
    else:
        texto_mision = "No hay misión activa. Pronto se generará una."

    # Zona actual — enriquecida con tipo y color
    zona_nombre  = jug.get("zona_actual", "Desconocida")
    zona_ubicacion = jug.get("ubicacion", "ciudad")
    zona_id      = jug.get("zona_actual_id")
    zona_icono   = "🏙️" if zona_ubicacion == "ciudad" else "🌿"
    zona_color   = ""
    zona_tipo_txt = "Ciudad" if zona_ubicacion == "ciudad" else "Zona Salvaje"
    try:
        from datos_zona import ZONAS as _ZONAS
        _color_emoji = {"azul": "🔵", "amarilla": "🟡", "roja": "🔴", "negra": "⚫"}
        for _z in _ZONAS:
            if _z.get("id") == zona_id:
                zona_icono = _z.get("icono", zona_icono)
                zona_color = _color_emoji.get(_z.get("color", ""), "")
                break
    except Exception:
        pass
    zona = f"{zona_icono} {zona_nombre}  {zona_color} {zona_tipo_txt}"

    # ====== Título activo ======
    try:
        import titulos as _titulos
        titulo_txt = _titulos.texto_titulo_para_perfil(user_id)
    except Exception:
        titulo_txt = ""

    # ====== Construcción del mensaje ======
    texto = f"*⚔️ Perfil de {_esc_md(nombre)}*\n"
    if titulo_txt:
        texto += f"{titulo_txt}\n"
    texto += f"🛡️ *Clase:* {clases.CLASES.get(clase, {}).get('nombre', clase.capitalize())}\n"
    if subclase != "Ninguna":
        texto += f"✨ *Subclase:* {subclase}\n"
    texto += f"🏛️ *Facción:* {faccion}\n"
    texto += f"📊 *Nivel:* {nivel}  |  🌟 *Exp:* {exp}/{exp_necesaria}\n"
    texto += f"🔄 *Reencarnaciones:* {reencarnaciones}  |  🏅 *Prestigio:* {prestigio_nivel}\n\n"

    texto += f"❤️ *Vida:* {stats['vida']}\n"
    texto += f"⚔️ *Daño:* {stats['daño']}\n"
    texto += f"🛡️ *Defensa:* {stats['defensa']}\n"
    texto += f"🎒 *Carga:* {stats['carga']}\n\n"

    texto += f"🪙 *Oro:* {oro}  |  💎 *Eternium:* {eternium}  |  ✨ *Créditos:* {creditos}  |  ⭐ *Reputación:* {reputacion}\n\n"

    texto += f"*Equipo equipado:*\n{texto_equipo}\n"
    texto += f"🎒 *Inventario:* {num_items} objetos\n\n"

    texto += f"*Progresión:*\n"
    texto += f"🔧 Talentos: {puntos_gastados}/{puntos_totales} (disponibles {puntos_disponibles})\n"
    texto += f"🏆 Gloria: {gloria_total}  |  🎖️ Títulos: {num_titulos}\n"
    texto += f"📈 Puntos Paragon: {puntos_paragon}\n"
    texto += f"🔮 Maestría subclase: nivel {maestria_subclase}\n"
    texto += f"🏅 Hitos de nivel: {hitos_alcanzados}/5\n\n"

    texto += f"*Misión semanal:*\n{texto_mision}\n\n"
    texto += f"📍 *Zona actual:* {zona}"

    # Botones
    keyboard = [
        [InlineKeyboardButton("🔧 Talentos", callback_data="perf_talentos")],
        [InlineKeyboardButton("📜 Misiones", callback_data="perf_misiones")],
        [InlineKeyboardButton("🎒 Inventario", callback_data="perf_inventario")],
        [InlineKeyboardButton("🔄 Resetear talentos", callback_data="perf_resetear")],
        [InlineKeyboardButton("🏅 Mis Títulos", callback_data="titulo_menu")],
        [InlineKeyboardButton("🎫 Gestionar Membresía", callback_data="perf_membresia")],
        [InlineKeyboardButton("❌ Cerrar", callback_data="perf_cerrar")]
    ]
    await update.effective_message.reply_text(texto, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    try:
        import misiones as _mis
        _mis.completar_mision(user_id, "ver_perfil", context)
    except Exception:
        pass
    try:
        import guia_contextual as _gc
        await _gc.enviar(user_id, context, "perfil_abierto")
    except Exception:
        pass

# ==================== HANDLERS DE LOS BOTONES ====================
# ==================== ÁRBOL DE TALENTOS INTERACTIVO ====================
_EMOJIS_RAMA = {
    "ofensiva": "⚔️",
    "defensiva": "🛡️",
    "utilidad": "⚙️",
    "vanguardista": "🔰",
    "acechante": "🗡️",
    "tejehechizos": "🔮",
    "maestro_caza": "🏹",
}
_NOMBRES_RAMA = {
    "ofensiva": "Ofensiva",
    "defensiva": "Defensiva",
    "utilidad": "Utilidad",
    "vanguardista": "Vanguardista",
    "acechante": "Acechante",
    "tejehechizos": "Tejehechizos",
    "maestro_caza": "Maestro de Caza",
}


def _niveles_talentos(user_id: int) -> dict:
    conn = sqlite3.connect(db_helper.DB_PATH)
    c = conn.cursor()
    c.execute('SELECT talento_id, nivel FROM talentos_jugador WHERE jugador_id = ?', (user_id,))
    result = {row[0]: row[1] for row in c.fetchall()}
    conn.close()
    return result


async def perfil_boton_talentos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        await query.edit_message_text("❌ No tienes personaje.")
        return
    clase = jug["clase"]
    nivel = jug["nivel"]
    puntos_totales = nivel // 5
    puntos_gastados = progresion_clase.talentos_gastados(user_id)
    puntos_disponibles = puntos_totales - puntos_gastados

    texto = (
        "🔧 *Árbol de Talentos*\n"
        f"✨ Puntos disponibles: *{puntos_disponibles}* / {puntos_totales}\n\n"
        "Elige una rama para ver y mejorar tus talentos:"
    )
    emoji_clase = _EMOJIS_RAMA.get(clase, "✨")
    nombre_clase = _NOMBRES_RAMA.get(clase, clase)
    keyboard = [
        [
            InlineKeyboardButton("⚔️ Ofensiva",  callback_data="tal_rama_ofensiva"),
            InlineKeyboardButton("🛡️ Defensiva", callback_data="tal_rama_defensiva"),
        ],
        [InlineKeyboardButton("⚙️ Utilidad", callback_data="tal_rama_utilidad")],
        [InlineKeyboardButton(f"{emoji_clase} {nombre_clase} ✦exclusiva", callback_data=f"tal_rama_{clase}")],
        [InlineKeyboardButton("🔙 Volver al perfil", callback_data="tal_volver")],
    ]
    await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")


async def _mostrar_rama(update: Update, context, rama: str):
    """Muestra los talentos de una rama. Reutilizable sin necesidad de mutar query.data."""
    query = update.callback_query
    user_id = update.effective_user.id
    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        await query.edit_message_text("❌ No tienes personaje.")
        return
    clase = jug["clase"]
    if rama in progresion_clase.RAMAS_CLASE_ESPECIFICA and rama != clase:
        await query.answer("❌ Esa rama es exclusiva de otra clase.", show_alert=True)
        return
    talentos_rama = progresion_clase.TALENTOS.get(rama)
    if not talentos_rama:
        await query.answer("❌ Rama no encontrada.", show_alert=True)
        return
    nivel_jug = jug["nivel"]
    puntos_totales = nivel_jug // 5
    puntos_gastados = progresion_clase.talentos_gastados(user_id)
    puntos_disponibles = puntos_totales - puntos_gastados
    niveles = _niveles_talentos(user_id)
    emoji_rama = _EMOJIS_RAMA.get(rama, "✨")
    nombre_rama = _NOMBRES_RAMA.get(rama, rama)

    texto = f"{emoji_rama} *Rama: {nombre_rama}*\n✨ Puntos disponibles: *{puntos_disponibles}*\n\n"
    keyboard = []
    for t in talentos_rama:
        niv_actual = niveles.get(t["id"], 0)
        max_niv = t["max_nivel"]
        barra = "●" * niv_actual + "○" * (max_niv - niv_actual)
        descripcion = t.get("descripcion", "")
        texto += f"*{t['nombre']}* \\[{barra}] {niv_actual}/{max_niv}\n"
        texto += f"  _{descripcion}_\n\n"
        if niv_actual < max_niv and puntos_disponibles > 0:
            keyboard.append([InlineKeyboardButton(
                f"▲ {t['nombre']}  ({niv_actual}→{niv_actual+1})",
                callback_data=f"tal_inv_{t['id']}"
            )])
    keyboard.append([InlineKeyboardButton("🔙 Volver a ramas", callback_data="perf_talentos")])
    await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")


async def tal_rama_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    rama = query.data[len("tal_rama_"):]
    await _mostrar_rama(update, context, rama)


async def tal_invertir_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    talento_id = query.data[len("tal_inv_"):]
    niveles = _niveles_talentos(user_id)
    nivel_actual = niveles.get(talento_id, 0)
    nuevo_nivel = nivel_actual + 1
    ok, msg = progresion_clase.desbloquear_talento(user_id, talento_id, nuevo_nivel)
    if not ok:
        await query.answer(f"❌ {msg}", show_alert=True)
        return
    await query.answer(f"✅ Talento mejorado a nivel {nuevo_nivel}!", show_alert=False)
    # Encontrar la rama del talento y volver a mostrarla
    rama = None
    for r, ts in progresion_clase.TALENTOS.items():
        for t in ts:
            if t["id"] == talento_id:
                rama = r
                break
        if rama:
            break
    if rama:
        await _mostrar_rama(update, context, rama)
    else:
        await query.edit_message_text("✅ Talento mejorado correctamente.")


async def tal_volver_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await cmd_perfil(update, context)

async def perfil_boton_misiones(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("📜 Funcionalidad de misiones en desarrollo. Usa /misiones por ahora.")

async def perfil_boton_inventario(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    from inventario import cmd_inventario
    await cmd_inventario(update, context)

async def perfil_boton_resetear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    costo = progresion_clase.calcular_costo_reseteo()
    await query.edit_message_text(
        f"⚠️ *Resetear talentos* cuesta {costo['eternium']} Eternium o {costo['creditos']} Créditos.\n"
        "¿Cómo deseas pagar?",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💎 Eternium", callback_data="reset_eternium")],
            [InlineKeyboardButton("✨ Créditos", callback_data="reset_creditos")],
            [InlineKeyboardButton("🔙 Cancelar", callback_data="reset_cancelar")]
        ])
    )
    context.user_data["reset_pendiente"] = True

async def perfil_resetear_moneda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not context.user_data.get("reset_pendiente"):
        await query.edit_message_text("Operación cancelada.")
        return
    partes_reset = query.data.split("_")
    if len(partes_reset) < 2:
        await query.edit_message_text("❌ Error al procesar reset.")
        return
    moneda = partes_reset[1]  # "eternium" o "creditos"
    user_id = update.effective_user.id
    ok, msg = progresion_clase.resetear_talentos(user_id, moneda)
    if ok:
        await query.edit_message_text(f"✅ {msg}")
        # Volver a mostrar el perfil actualizado
        await cmd_perfil(update, context)
    else:
        await query.edit_message_text(f"❌ {msg}")
    context.user_data.pop("reset_pendiente", None)

async def perfil_cancelar_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data.pop("reset_pendiente", None)
    await query.edit_message_text("Reset cancelado.")
    await cmd_perfil(update, context)

async def perfil_cerrar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("📋 Perfil cerrado.")


async def perfil_membresia(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Abre el panel de membresías desde el perfil."""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    try:
        import membresia as _memb
        await _memb._panel_membresia(update, context, user_id, editar=True)
    except Exception as e:
        await query.answer("❌ No se pudo abrir el panel de membresías.", show_alert=True)




async def cmd_info(update, context):
    user_id = update.effective_user.id
    username = update.effective_user.username
    nombre_tg = update.effective_user.full_name
    jug = db_helper.obtener_jugador(user_id)
    if jug:
        nombre_personaje = jug.get("nombre_personaje", "?")
        clase = jug.get("clase", "?")
        nivel = jug.get("nivel", 1)
        faccion = jug.get("faccion", "?")
        estado_rp = "Nv" + str(nivel) + " " + clase + " (" + faccion + ")"
    else:
        nombre_personaje = "Sin personaje"
        estado_rp = "No registrado"
    username_txt = "@" + username if username else "(sin @username)"
    partes = [
        "<b>Tu ID de Telegram:</b>",
        "<code>" + str(user_id) + "</code>",
        "",
        "Comparte este numero con otro jugador para que te desafie a duelo:",
        "/duelo " + str(user_id),
        "",
        "Nombre TG: " + nombre_tg + " " + username_txt,
        "Personaje: " + nombre_personaje,
        "Estado: " + estado_rp,
    ]
    await update.effective_message.reply_text("\n".join(partes), parse_mode="HTML")


# ==================== REGISTRO ====================
def registrar_handlers(app):
    app.add_handler(CommandHandler("perfil", cmd_perfil))
    app.add_handler(CommandHandler("info", cmd_info))
    app.add_handler(CallbackQueryHandler(perfil_boton_talentos, pattern="^perf_talentos$"))
    app.add_handler(CallbackQueryHandler(tal_rama_handler,    pattern="^tal_rama_"))
    app.add_handler(CallbackQueryHandler(tal_invertir_handler,pattern="^tal_inv_"))
    app.add_handler(CallbackQueryHandler(tal_volver_handler,  pattern="^tal_volver$"))
    app.add_handler(CallbackQueryHandler(perfil_boton_misiones, pattern="^perf_misiones$"))
    app.add_handler(CallbackQueryHandler(perfil_boton_inventario, pattern="^perf_inventario$"))
    app.add_handler(CallbackQueryHandler(perfil_boton_resetear, pattern="^perf_resetear$"))
    app.add_handler(CallbackQueryHandler(perfil_cerrar,     pattern="^perf_cerrar$"))
    app.add_handler(CallbackQueryHandler(perfil_membresia,  pattern="^perf_membresia$"))
    app.add_handler(CallbackQueryHandler(perfil_resetear_moneda, pattern="^reset_(eternium|creditos)$"))
    app.add_handler(CallbackQueryHandler(perfil_cancelar_reset, pattern="^reset_cancelar$"))
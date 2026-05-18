#!/usr/bin/env python3
"""
item_comparar.py — Comparación automática de item al recoger loot.

Cuando un jugador obtiene un arma o armadura en combate, este módulo
compara el item con el equipado actualmente y muestra las diferencias de stats.

Uso:
    from item_comparar import comparar_item
    texto = comparar_item(user_id, "Espada de Hierro", tipo="arma")

Admin: activable/desactivable desde panel de automatizaciones
"""

import sqlite3
import logging
import db_helper

logger = logging.getLogger(__name__)
DB_PATH = "aethelgard.db"


def _activo() -> bool:
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT valor FROM config_bot WHERE clave = 'item_comparar_activo'")
        row = c.fetchone()
        conn.close()
        return (row[0] if row else "1") == "1"
    except Exception:
        return True


def _datos_arma(nombre: str) -> dict:
    try:
        from armas import ARMAS
        for k, v in ARMAS.items():
            if v.get("nombre") == nombre:
                return v
    except Exception:
        pass
    return {}


def _datos_armadura(nombre: str) -> dict:
    try:
        from armaduras import ARMADURAS
        for k, v in ARMADURAS.items():
            if v.get("nombre") == nombre:
                return v
    except Exception:
        pass
    return {}


def _tipo_item(nombre: str) -> str:
    """Detecta si el nombre corresponde a un arma o armadura."""
    if _datos_arma(nombre):
        return "arma"
    if _datos_armadura(nombre):
        return "armadura"
    return "otro"


def _diff(nuevo: int | float, actual: int | float) -> str:
    diff = nuevo - actual
    if diff > 0:
        return f"<b>+{diff} ✅</b>"
    elif diff < 0:
        return f"<b>{diff} ⬇️</b>"
    return "= (igual)"


def comparar_item(user_id: int, item_nombre: str) -> str | None:
    """
    Compara el item obtenido con el equipado actualmente.
    Retorna texto HTML con la comparación, o None si no aplica o está desactivado.
    """
    if not _activo():
        return None

    tipo = _tipo_item(item_nombre)
    if tipo == "otro":
        return None

    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        return None

    if tipo == "arma":
        nuevo = _datos_arma(item_nombre)
        equipado_nombre = jug.get("arma_equipada")
        equipado = _datos_arma(equipado_nombre) if equipado_nombre else {}
        stat_principal = "daño"
        stat_icono = "⚔️"
        equip_label = "arma"
        equip_emoji = "⚔️"
    else:
        nuevo = _datos_armadura(item_nombre)
        equipado_nombre = jug.get("armadura_equipada")
        equipado = _datos_armadura(equipado_nombre) if equipado_nombre else {}
        stat_principal = "defensa"
        stat_icono = "🛡️"
        equip_label = "armadura"
        equip_emoji = "🛡️"

    if not nuevo:
        return None

    lineas = [
        f"🔍 <b>Comparación de {equip_emoji} {item_nombre}</b>",
    ]

    if not equipado or not equipado_nombre:
        lineas.append(f"📦 No tienes {equip_label} equipada.")
        nuevo_sp = nuevo.get(stat_principal, 0)
        lineas.append(f"{stat_icono} {stat_principal.capitalize()}: <b>{nuevo_sp}</b> ← nuevo")
        vel = nuevo.get("velocidad", 0)
        if vel:
            lineas.append(f"💨 Velocidad: <b>{vel}</b>")
        vida_e = nuevo.get("vida_extra", 0)
        if vida_e:
            lineas.append(f"❤️ Vida extra: <b>+{vida_e}</b>")
        lineas.append(f"\n✅ ¡Sería una mejora! Equípala en /inventario → Equipar.")
    else:
        lineas.append(f"📦 Equipada: <i>{equipado_nombre}</i>")

        nuevo_sp = nuevo.get(stat_principal, 0)
        actual_sp = equipado.get(stat_principal, 0)
        lineas.append(f"{stat_icono} {stat_principal.capitalize()}: {actual_sp} → <b>{nuevo_sp}</b> {_diff(nuevo_sp, actual_sp)}")

        nueva_vel = nuevo.get("velocidad", 0)
        actual_vel = equipado.get("velocidad", 0)
        if nueva_vel or actual_vel:
            lineas.append(f"💨 Velocidad: {actual_vel} → <b>{nueva_vel}</b> {_diff(nueva_vel, actual_vel)}")

        nueva_vida = nuevo.get("vida_extra", 0)
        actual_vida = equipado.get("vida_extra", 0)
        if nueva_vida or actual_vida:
            lineas.append(f"❤️ Vida extra: {actual_vida} → <b>{nueva_vida}</b> {_diff(nueva_vida, actual_vida)}")

        nuevo_crit = nuevo.get("critico", 0)
        actual_crit = equipado.get("critico", 0)
        if nuevo_crit or actual_crit:
            lineas.append(f"💥 Crítico: {actual_crit}% → <b>{nuevo_crit}%</b> {_diff(nuevo_crit, actual_crit)}")

        # Veredicto
        nuevo_total = nuevo_sp + nueva_vel * 0.5 + nueva_vida * 0.3 + nuevo_crit * 2
        actual_total = actual_sp + actual_vel * 0.5 + actual_vida * 0.3 + actual_crit * 2
        if nuevo_total > actual_total:
            lineas.append(f"\n✅ <b>¡Mejora!</b> Equípala en /inventario → Equipar.")
        elif nuevo_total < actual_total:
            lineas.append(f"\n⬇️ <b>Peor que tu equipo actual.</b> Guárdala o véndela.")
        else:
            lineas.append(f"\n🔵 Similar a tu equipo actual. Tú decides.")

    return "\n".join(lineas)

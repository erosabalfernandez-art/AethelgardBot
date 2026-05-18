# config_balance.py
# Lee todos los valores desde la base de datos al arrancar el bot.
# Si la DB no tiene un valor (primer inicio), usa el default hardcodeado.
# Así cualquier cambio hecho desde el panel admin persiste para siempre.

def _cfg(clave, default):
    """Lee un valor de config_bot en la DB. Si falla, devuelve el default."""
    try:
        import db_helper
        raw = db_helper.obtener_config(clave, None)
        if raw is None:
            return default
        if isinstance(default, bool):
            return raw.lower() in ("1", "true", "yes")
        if isinstance(default, float):
            return float(raw)
        if isinstance(default, int):
            return int(float(raw))
        return raw
    except Exception:
        return default


# ==================== STAMINA ====================
STAMINA_MAX_BASE              = _cfg("stamina_max_base",          100)
STAMINA_REGENERACION_SEGUNDOS = _cfg("stamina_regen_segundos",    180)
STAMINA_COSTE_POR_ZONA = {
    "azul":     _cfg("stamina_coste_azul",     15),
    "amarilla": _cfg("stamina_coste_amarilla", 25),
    "roja":     _cfg("stamina_coste_roja",     40),
    "negra":    _cfg("stamina_coste_negra",    60),
}
STAMINA_BONUS_POR_RECLUTA = _cfg("stamina_bonus_por_recluta", 5)
STAMINA_MAX_EXTRA          = _cfg("stamina_max_extra",         200)

# ==================== INVITACIONES ====================
INVITACION_RECLUTA_RECIBE_POCIONES = _cfg("invitacion_pociones_recluta", 2)
INVITACION_NIVEL_REQUERIDO_BONUS   = _cfg("invitacion_nivel_bonus",      15)

# ==================== MAZMORRAS ====================
MAZMORRAS_LIMITE_DIARIO  = _cfg("mazmorra_limite_diario", 2)
MAZMORRAS_COSTES_ENTRADA = {
    "azul":     _cfg("mazmorra_coste_azul",     200),
    "amarilla": _cfg("mazmorra_coste_amarilla", 300),
    "roja":     _cfg("mazmorra_coste_roja",     400),
    "negra":    _cfg("mazmorra_coste_negra",     20),
}
MAZMORRAS_RECOMPENSA_ETERNIUM_NORMAL  = {"azul": (2, 5),   "amarilla": (5, 10),  "roja": (10, 20), "negra": (20, 40)}
MAZMORRAS_RECOMPENSA_ETERNIUM_DIFICIL = {"azul": (6, 10),  "amarilla": (12, 20), "roja": (25, 40), "negra": (50, 80)}
MAZMORRAS_XP_MULT   = _cfg("mazmorra_xp_mult",  1.0)
MAZMORRAS_ORO_MULT  = _cfg("mazmorra_oro_mult",  1.0)
MAZMORRAS_ET_MULT   = _cfg("mazmorra_et_mult",   1.0)

# ==================== BANCO ====================
BANCO_CREDITO_A_ETERNIUM               = _cfg("banco_credito_a_eternium", 10)
BANCO_CREDITO_A_ORO                    = _cfg("banco_credito_a_oro",      10000)
BANCO_PERMITIR_COMPRA_ETERNIUM_CON_ORO = False
BANCO_PERMITIR_VENTA_ETERNIUM_POR_ORO  = False

# ==================== TIENDA ====================
TIENDA_ROTACION_CREDITOS_DIAS = _cfg("tienda_rotacion_dias",    5)
TIENDA_VENTA_PORCENTAJE       = _cfg("tienda_venta_porcentaje", 0.5)

# ==================== TABERNA ====================
TABERNA_RECUPERA_STAMINA   = False
TABERNA_COSTO_DESCANSAR    = _cfg("taberna_costo_descansar",    50)
TABERNA_STAMINA_RECUPERA   = _cfg("taberna_stamina_recupera",   20)
TABERNA_COOLDOWN_SEGUNDOS  = _cfg("taberna_cooldown_segundos",  3600)
TABERNA_BUFF_XP_PORCENTAJE = _cfg("taberna_buff_xp_porcentaje", 0)
TABERNA_BUFF_DURACION_MIN  = _cfg("taberna_buff_duracion_min",  60)

# ==================== COMBATE ====================
COMBATE_TIMEOUT_TURNO         = _cfg("combate_timeout_turno",         120)
COMBATE_PROB_HUIDA            = _cfg("combate_prob_huida",            0.5)
COMBATE_CRITICO_PORCENTAJE    = _cfg("combate_critico_porcentaje",    15)
COMBATE_CRITICO_MULTIPLICADOR = _cfg("combate_critico_multiplicador", 2.0)
COMBATE_PVP_COOLDOWN_MIN      = _cfg("combate_pvp_cooldown_min",      5)
COMBATE_PVP_NIVEL_MINIMO      = _cfg("combate_pvp_nivel_minimo",      5)
COMBATE_PVP_ORO_VICTORIA      = _cfg("combate_pvp_oro_victoria",      50)
COMBATE_PVP_XP_VICTORIA       = _cfg("combate_pvp_xp_victoria",       80)
COMBATE_PVP_ORO_DERROTA       = _cfg("combate_pvp_oro_derrota",       10)

# ==================== MONSTRUOS ====================
MONSTRUO_MINIBOSS_MULT         = _cfg("monstruo_miniboss_mult",         2.5)
MONSTRUO_MAZMORRA_NORMAL_MULT  = _cfg("monstruo_mazmorra_normal_mult",  1.8)
MONSTRUO_MAZMORRA_DIFICIL_MULT = _cfg("monstruo_mazmorra_dificil_mult", 2.5)
MONSTRUO_PROB_DROP_ITEM        = _cfg("monstruo_prob_drop_item",        0.3)
MONSTRUO_PROB_DROP_MATERIAL    = _cfg("monstruo_prob_drop_material",    0.5)

# ==================== RECOLECCIÓN ====================
RECOLECCION_COOLDOWN = {
    "azul":     _cfg("recoleccion_cooldown_azul",     300),
    "amarilla": _cfg("recoleccion_cooldown_amarilla", 600),
    "roja":     _cfg("recoleccion_cooldown_roja",     900),
    "negra":    _cfg("recoleccion_cooldown_negra",    1800),
}
RECOLECCION_CANTIDAD_MULT  = _cfg("recoleccion_cantidad_mult", 1.0)
RECOLECCION_STAMINA_COSTE  = _cfg("recoleccion_stamina_coste", 10)

# ==================== INVESTIGACIÓN ====================
INVESTIGACION_COOLDOWN = {
    "azul":     _cfg("investigacion_cooldown_azul",     600),
    "amarilla": _cfg("investigacion_cooldown_amarilla", 1200),
    "roja":     _cfg("investigacion_cooldown_roja",     1800),
    "negra":    _cfg("investigacion_cooldown_negra",    3600),
}
INVESTIGACION_XP_MULT    = _cfg("investigacion_xp_mult",    1.0)
INVESTIGACION_RECOMP_MULT= _cfg("investigacion_recomp_mult", 1.0)

# ==================== CRAFTEO ====================
CRAFTEO_DESCUENTO_PORCENTAJE = _cfg("crafteo_descuento_porcentaje", 0)
CRAFTEO_COOLDOWN_SEGUNDOS    = _cfg("crafteo_cooldown_segundos",    0)
CRAFTEO_PROB_BONUS_MATERIAL  = _cfg("crafteo_prob_bonus_material",  0.1)
CRAFTEO_NIVEL_MINIMO         = _cfg("crafteo_nivel_minimo",         1)

# ==================== SUBASTAS ====================
SUBASTA_DURACION_HORAS = _cfg("subasta_duracion_horas", 24)
SUBASTA_FEE_PORCENTAJE = _cfg("subasta_fee_porcentaje", 5)
SUBASTA_MAX_ACTIVAS    = _cfg("subasta_max_activas",    3)
SUBASTA_PUJA_MINIMA    = _cfg("subasta_puja_minima",    100)
SUBASTA_NIVEL_MINIMO   = _cfg("subasta_nivel_minimo",   5)

# ==================== GREMIOS ====================
GREMIO_COSTE_CREAR           = _cfg("gremio_coste_crear",           5000)
GREMIO_CAPACIDAD_INICIAL     = _cfg("gremio_capacidad_inicial",     10)
GREMIO_EXP_POR_ACTIVIDAD     = _cfg("gremio_exp_por_actividad",     10)
GREMIO_TAX_MAX_PORCENTAJE    = _cfg("gremio_tax_max_porcentaje",    20)
GREMIO_GUERRA_DURACION_HORAS = _cfg("gremio_guerra_duracion_horas", 24)
GREMIO_WAR_NIVEL_MINIMO      = _cfg("gremio_war_nivel_minimo",      3)

# ==================== GUERRA FACCIONES ====================
GF_DURACION_HORAS           = _cfg("gf_duracion_horas",           1)
GF_COOLDOWN_ATAQUE_SEGUNDOS = _cfg("gf_cooldown_ataque_segundos", 60)
GF_RECOMPENSA_ORO           = _cfg("gf_recompensa_oro_victoria",  500)
GF_RECOMPENSA_ET            = _cfg("gf_recompensa_et_victoria",   20)
GF_PUNTOS_POR_ATAQUE        = _cfg("gf_puntos_por_ataque",        10)

# ==================== JEFES RAID ====================
JEFE_HP_BASE               = _cfg("jefe_hp_base",               10000)
JEFE_MULT_FACIL            = _cfg("jefe_mult_facil",            0.5)
JEFE_MULT_DIFICIL          = _cfg("jefe_mult_dificil",          2.0)
JEFE_MULT_LEGENDARIO       = _cfg("jefe_mult_legendario",       4.0)
JEFE_COOLDOWN_ATAQUE_SEG   = _cfg("jefe_cooldown_ataque_segundos", 30)
JEFE_XP_POR_DANO           = _cfg("jefe_xp_por_dano",           0.5)
JEFE_ORO_POR_DANO          = _cfg("jefe_oro_por_dano",          0.2)
JEFE_MAX_JUGADORES         = _cfg("jefe_max_jugadores",          30)

# ==================== MUERTE & RESPAWN ====================
MUERTE_XP_PENALIZACION       = _cfg("muerte_xp_penalizacion",       5)
MUERTE_ORO_PENALIZACION      = _cfg("muerte_oro_penalizacion",      0)
MUERTE_HP_RESPAWN_PORCENTAJE = _cfg("muerte_hp_respawn_porcentaje", 50)
MUERTE_COOLDOWN_RESPAWN_SEG  = _cfg("muerte_cooldown_respawn_seg",  300)

# ==================== ECONOMÍA ====================
ECONOMIA_PVE_XP_MULT     = _cfg("economia_pve_xp_mult",     1.0)
ECONOMIA_PVE_ORO_MULT    = _cfg("economia_pve_oro_mult",    1.0)
ECONOMIA_XP_FORMULA_BASE = _cfg("economia_xp_formula_base", 100)
ECONOMIA_XP_FORMULA_EXP  = _cfg("economia_xp_formula_exp",  1.5)
ECONOMIA_GOLD_CAP        = _cfg("economia_gold_cap",         0)

# ==================== VIAJES ====================
VIAJE_TIEMPO_BASE_SEGUNDOS = _cfg("viaje_tiempo_base_segundos", 60)
VIAJE_STAMINA_COSTE        = _cfg("viaje_stamina_coste",        5)
VIAJE_COOLDOWN_SEGUNDOS    = _cfg("viaje_cooldown_segundos",    30)

# ==================== EVENTOS AUTO ====================
EVENTO_BONUS_XP_ACTIVO  = _cfg("evento_bonus_xp_activo",  False)
EVENTO_BONUS_ORO_ACTIVO = _cfg("evento_bonus_oro_activo", False)
EVENTO_BONUS_XP_MULT    = _cfg("evento_bonus_xp_mult",    2.0)
EVENTO_BONUS_ORO_MULT   = _cfg("evento_bonus_oro_mult",   2.0)

# ==================== ARMAS (masivo) ====================
BG_ARMA_DAÑO           = _cfg("bg_a_daño",             1.0)
BG_ARMA_CRITICO        = _cfg("bg_a_critico",          1.0)
BG_ARMA_VELOCIDAD      = _cfg("bg_a_velocidad",        1.0)
BG_ARMA_PRECIO_ORO     = _cfg("bg_a_precio_oro",       1.0)
BG_ARMA_PRECIO_ETH     = _cfg("bg_a_precio_eth",       1.0)
BG_ARMA_NIVEL_OFFSET   = _cfg("bg_a_nivel_req_offset", 0)

# ==================== ARMADURAS (masivo) ====================
BG_ARMOR_DEFENSA       = _cfg("bg_ar_defensa",          1.0)
BG_ARMOR_RESISTENCIA   = _cfg("bg_ar_resistencia",      1.0)
BG_ARMOR_VIDA_EXTRA    = _cfg("bg_ar_vida_extra",       1.0)
BG_ARMOR_PRECIO_ORO    = _cfg("bg_ar_precio_oro",       1.0)
BG_ARMOR_PRECIO_ETH    = _cfg("bg_ar_precio_eth",       1.0)
BG_ARMOR_NIVEL_OFFSET  = _cfg("bg_ar_nivel_req_offset", 0)

# ==================== POCIONES (masivo) ====================
BG_POCION_EFECTO_MULT  = _cfg("bg_p_efecto_mult",      1.0)
BG_POCION_DUR_MULT     = _cfg("bg_p_duracion_mult",    1.0)
BG_POCION_PRECIO_ORO   = _cfg("bg_p_precio_oro",       1.0)
BG_POCION_PRECIO_ETH   = _cfg("bg_p_precio_eth",       1.0)
BG_POCION_NIVEL_OFFSET = _cfg("bg_p_nivel_req_offset", 0)

# ==================== MATERIALES (masivo) ====================
BG_MAT_VALOR_CRAFTEO    = _cfg("bg_mat_valor_crafteo",    1.0)
BG_MAT_PRECIO_VENTA_ORO = _cfg("bg_mat_precio_venta_oro", 1.0)
BG_MAT_PRECIO_VENTA_ETH = _cfg("bg_mat_precio_venta_eth", 1.0)
BG_MAT_DROP_MULT        = _cfg("bg_mat_drop_mult",        1.0)
BG_MAT_RAREZA_BONUS     = _cfg("bg_mat_rareza_bonus",     0)

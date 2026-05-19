#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# config_db.py — Configuración persistente del juego.
# Cada clave tiene: default, tipo, cat, label, step (paso para botones ± en el panel).

import db_helper

CONFIG_SCHEMA = {

    # ── ⚡ STAMINA ────────────────────────────────────────────────
    "stamina_max_base":               {"default": 100,   "tipo": "int",   "cat": "⚡ Stamina",          "label": "Stamina máxima base",                         "step": 10},
    "stamina_regen_segundos":         {"default": 180,   "tipo": "int",   "cat": "⚡ Stamina",          "label": "Segundos para regen 1 stamina",               "step": 30},
    "stamina_coste_azul":             {"default": 15,    "tipo": "int",   "cat": "⚡ Stamina",          "label": "Coste stamina zona azul",                     "step": 1},
    "stamina_coste_amarilla":         {"default": 25,    "tipo": "int",   "cat": "⚡ Stamina",          "label": "Coste stamina zona amarilla",                 "step": 5},
    "stamina_coste_roja":             {"default": 40,    "tipo": "int",   "cat": "⚡ Stamina",          "label": "Coste stamina zona roja",                     "step": 5},
    "stamina_coste_negra":            {"default": 60,    "tipo": "int",   "cat": "⚡ Stamina",          "label": "Coste stamina zona negra",                    "step": 5},
    "stamina_bonus_por_recluta":      {"default": 5,     "tipo": "int",   "cat": "⚡ Stamina",          "label": "Stamina extra por cada recluta",              "step": 1},
    "stamina_max_extra":              {"default": 200,   "tipo": "int",   "cat": "⚡ Stamina",          "label": "Stamina máxima con bonus de reclutas",        "step": 10},

    # ── 🧑 JUGADOR BASE ───────────────────────────────────────────
    "jugador_nivel_max":              {"default": 100,   "tipo": "int",   "cat": "🧑 Jugador Base",     "label": "Nivel máximo alcanzable",                    "step": 5},
    "jugador_hp_base":                {"default": 100,   "tipo": "int",   "cat": "🧑 Jugador Base",     "label": "HP base al nivel 1",                          "step": 10},
    "jugador_atk_base":               {"default": 20,    "tipo": "int",   "cat": "🧑 Jugador Base",     "label": "ATK base al nivel 1",                         "step": 5},
    "jugador_def_base":               {"default": 10,    "tipo": "int",   "cat": "🧑 Jugador Base",     "label": "DEF base al nivel 1",                         "step": 5},
    "jugador_hp_por_nivel":           {"default": 10,    "tipo": "int",   "cat": "🧑 Jugador Base",     "label": "HP extra que gana por nivel",                 "step": 2},
    "jugador_atk_por_nivel":          {"default": 3,     "tipo": "int",   "cat": "🧑 Jugador Base",     "label": "ATK extra que gana por nivel",                "step": 1},
    "jugador_def_por_nivel":          {"default": 2,     "tipo": "int",   "cat": "🧑 Jugador Base",     "label": "DEF extra que gana por nivel",                "step": 1},
    "jugador_velocidad_base":         {"default": 10,    "tipo": "int",   "cat": "🧑 Jugador Base",     "label": "Velocidad base (afecta orden combate)",       "step": 1},

    # ── 🌀 MAZMORRAS ──────────────────────────────────────────────
    "mazmorra_limite_diario":         {"default": 2,     "tipo": "int",   "cat": "🌀 Mazmorras",        "label": "Mazmorras por jugador al día",                "step": 1},
    "mazmorra_coste_azul":            {"default": 200,   "tipo": "int",   "cat": "🌀 Mazmorras",        "label": "Coste entrada mazmorra azul (oro)",           "step": 50},
    "mazmorra_coste_amarilla":        {"default": 500,   "tipo": "int",   "cat": "🌀 Mazmorras",        "label": "Coste entrada mazmorra amarilla (oro)",       "step": 50},
    "mazmorra_coste_roja":            {"default": 1000,  "tipo": "int",   "cat": "🌀 Mazmorras",        "label": "Coste entrada mazmorra roja (oro)",           "step": 100},
    "mazmorra_coste_negra":           {"default": 2500,  "tipo": "int",   "cat": "🌀 Mazmorras",        "label": "Coste entrada mazmorra negra (oro)",          "step": 100},
    "mazmorra_xp_mult":               {"default": 1.0,   "tipo": "float", "cat": "🌀 Mazmorras",        "label": "Multiplicador de XP en mazmorras",            "step": 0.1},
    "mazmorra_oro_mult":              {"default": 1.0,   "tipo": "float", "cat": "🌀 Mazmorras",        "label": "Multiplicador de oro en mazmorras",           "step": 0.1},
    "mazmorra_et_mult":               {"default": 1.0,   "tipo": "float", "cat": "🌀 Mazmorras",        "label": "Multiplicador de eternium en mazmorras",      "step": 0.1},
    "mazmorra_cooldown_horas":        {"default": 0,     "tipo": "int",   "cat": "🌀 Mazmorras",        "label": "Cooldown entre mazmorras (horas, 0=libre)",   "step": 1},

    # ── 🏦 BANCO ──────────────────────────────────────────────────
    "banco_credito_a_eternium":       {"default": 10,    "tipo": "int",   "cat": "🏦 Banco",            "label": "Créditos que cuesta 1 Eternium",              "step": 1},
    "banco_credito_a_oro":            {"default": 10000, "tipo": "int",   "cat": "🏦 Banco",            "label": "Créditos que cuestan 10 000 Oro",             "step": 1000},
    "banco_interes_deposito":         {"default": 0.0,   "tipo": "float", "cat": "🏦 Banco",            "label": "Interés diario del banco (0.02 = 2%)",        "step": 0.01},
    "banco_max_deposito":             {"default": 0,     "tipo": "int",   "cat": "🏦 Banco",            "label": "Máximo depositable por jugador (0=ilimitado)","step": 1000},

    # ── 🛒 TIENDA ─────────────────────────────────────────────────
    "tienda_venta_porcentaje":        {"default": 0.5,   "tipo": "float", "cat": "🛒 Tienda",           "label": "% que reciben al vender (0.5 = 50%)",         "step": 0.05},
    "tienda_rotacion_dias":           {"default": 5,     "tipo": "int",   "cat": "🛒 Tienda",           "label": "Días entre rotaciones de créditos",           "step": 1},
    "tienda_factor_oro":              {"default": 300,   "tipo": "int",   "cat": "🛒 Tienda",           "label": "Factor precio en oro (nivel×factor×rareza)",  "step": 50},
    "tienda_factor_eternium":         {"default": 10,    "tipo": "int",   "cat": "🛒 Tienda",           "label": "Factor precio en eternium",                   "step": 1},
    "tienda_factor_creditos":         {"default": 4,     "tipo": "int",   "cat": "🛒 Tienda",           "label": "Factor precio en créditos del vacío",         "step": 1},
    "tienda_stock_maximo":            {"default": 5,     "tipo": "int",   "cat": "🛒 Tienda",           "label": "Stock inicial de cada ítem (créditos)",       "step": 1},
    "tienda_items_rotacion":          {"default": 8,     "tipo": "int",   "cat": "🛒 Tienda",           "label": "Ítems por rotación de créditos",              "step": 1},

    # ── 🍺 TABERNA ────────────────────────────────────────────────
    "taberna_costo_descansar":        {"default": 50,    "tipo": "int",   "cat": "🍺 Taberna",          "label": "Costo de descansar (oro)",                    "step": 10},
    "taberna_stamina_recupera":       {"default": 20,    "tipo": "int",   "cat": "🍺 Taberna",          "label": "Stamina que recupera el descanso",            "step": 5},
    "taberna_cooldown_segundos":      {"default": 3600,  "tipo": "int",   "cat": "🍺 Taberna",          "label": "Cooldown entre descansos (segundos)",         "step": 600},
    "taberna_buff_xp_porcentaje":     {"default": 0,     "tipo": "int",   "cat": "🍺 Taberna",          "label": "Bonus % XP tras descansar (0=sin bonus)",     "step": 5},
    "taberna_buff_duracion_min":      {"default": 60,    "tipo": "int",   "cat": "🍺 Taberna",          "label": "Minutos que dura el buff de XP",              "step": 15},

    # ── ⚔️ COMBATE ────────────────────────────────────────────────
    "combate_timeout_turno":          {"default": 120,   "tipo": "int",   "cat": "⚔️ Combate",          "label": "Segundos por turno antes de auto-huida",      "step": 30},
    "combate_prob_huida":             {"default": 0.5,   "tipo": "float", "cat": "⚔️ Combate",          "label": "Probabilidad base de huir (0.0–1.0)",         "step": 0.05},
    "combate_critico_porcentaje":     {"default": 15,    "tipo": "int",   "cat": "⚔️ Combate",          "label": "Probabilidad de golpe crítico (%)",           "step": 5},
    "combate_critico_multiplicador":  {"default": 2.0,   "tipo": "float", "cat": "⚔️ Combate",          "label": "Multiplicador de daño en crítico",            "step": 0.25},
    "combate_pvp_cooldown_min":       {"default": 5,     "tipo": "int",   "cat": "⚔️ Combate",          "label": "Cooldown entre duelos PvP (minutos)",         "step": 1},
    "combate_pvp_nivel_minimo":       {"default": 5,     "tipo": "int",   "cat": "⚔️ Combate",          "label": "Nivel mínimo para PvP",                       "step": 1},
    "combate_pvp_oro_victoria":       {"default": 50,    "tipo": "int",   "cat": "⚔️ Combate",          "label": "Oro base al vencer en PvP",                   "step": 10},
    "combate_pvp_xp_victoria":        {"default": 80,    "tipo": "int",   "cat": "⚔️ Combate",          "label": "XP base al vencer en PvP",                    "step": 10},
    "combate_pvp_oro_derrota":        {"default": 10,    "tipo": "int",   "cat": "⚔️ Combate",          "label": "Oro perdido al ser derrotado en PvP",         "step": 5},

    # ── 👾 MONSTRUOS ──────────────────────────────────────────────
    "bg_m_vida":                      {"default": 1.0,   "tipo": "float", "cat": "👾 Monstruos",        "label": "×Vida de todos los monstruos",                "step": 0.1},
    "bg_m_daño":                      {"default": 1.0,   "tipo": "float", "cat": "👾 Monstruos",        "label": "×Daño de todos los monstruos",                "step": 0.1},
    "bg_m_def":                       {"default": 1.0,   "tipo": "float", "cat": "👾 Monstruos",        "label": "×Defensa de todos los monstruos",             "step": 0.1},
    "bg_m_xp":                        {"default": 1.0,   "tipo": "float", "cat": "👾 Monstruos",        "label": "×XP otorgada por monstruos",                  "step": 0.1},
    "bg_m_oro":                       {"default": 1.0,   "tipo": "float", "cat": "👾 Monstruos",        "label": "×Oro otorgado por monstruos",                 "step": 0.1},
    "monstruo_prob_drop_item":        {"default": 0.3,   "tipo": "float", "cat": "👾 Monstruos",        "label": "Prob. drop ítem por monstruo (0–1)",          "step": 0.05},
    "monstruo_prob_drop_material":    {"default": 0.5,   "tipo": "float", "cat": "👾 Monstruos",        "label": "Prob. drop material por monstruo (0–1)",      "step": 0.05},
    "monstruo_miniboss_mult":         {"default": 2.5,   "tipo": "float", "cat": "👾 Monstruos",        "label": "×Poder del mini-boss",                        "step": 0.25},
    "monstruo_mazmorra_normal_mult":  {"default": 1.8,   "tipo": "float", "cat": "👾 Monstruos",        "label": "×Poder en mazmorra normal",                   "step": 0.1},
    "monstruo_mazmorra_dificil_mult": {"default": 2.5,   "tipo": "float", "cat": "👾 Monstruos",        "label": "×Poder en mazmorra difícil",                  "step": 0.25},

    # ── 🌿 RECOLECCIÓN ────────────────────────────────────────────
    "recoleccion_cooldown_azul":      {"default": 300,   "tipo": "int",   "cat": "🌿 Recolección",      "label": "Cooldown recolección azul (segundos)",        "step": 60},
    "recoleccion_cooldown_amarilla":  {"default": 600,   "tipo": "int",   "cat": "🌿 Recolección",      "label": "Cooldown recolección amarilla (segundos)",    "step": 60},
    "recoleccion_cooldown_roja":      {"default": 900,   "tipo": "int",   "cat": "🌿 Recolección",      "label": "Cooldown recolección roja (segundos)",        "step": 60},
    "recoleccion_cooldown_negra":     {"default": 1800,  "tipo": "int",   "cat": "🌿 Recolección",      "label": "Cooldown recolección negra (segundos)",       "step": 300},
    "recoleccion_cantidad_mult":      {"default": 1.0,   "tipo": "float", "cat": "🌿 Recolección",      "label": "×Cantidad de materiales obtenidos",           "step": 0.1},
    "recoleccion_stamina_coste":      {"default": 5,     "tipo": "int",   "cat": "🌿 Recolección",      "label": "Stamina que cuesta recolectar (legacy)",      "step": 1},
    "stamina_recolectar":             {"default": 5,     "tipo": "int",   "cat": "🌿 Recolección",      "label": "Stamina que cuesta recolectar en zona",       "step": 1},

    # ── 🔬 INVESTIGACIÓN ──────────────────────────────────────────
    "investigacion_cooldown_azul":    {"default": 600,   "tipo": "int",   "cat": "🔬 Investigación",    "label": "Cooldown investigación azul (segundos)",      "step": 60},
    "investigacion_cooldown_amarilla":{"default": 1200,  "tipo": "int",   "cat": "🔬 Investigación",    "label": "Cooldown investigación amarilla (segundos)",  "step": 60},
    "investigacion_cooldown_roja":    {"default": 1800,  "tipo": "int",   "cat": "🔬 Investigación",    "label": "Cooldown investigación roja (segundos)",      "step": 300},
    "investigacion_cooldown_negra":   {"default": 3600,  "tipo": "int",   "cat": "🔬 Investigación",    "label": "Cooldown investigación negra (segundos)",     "step": 300},
    "investigacion_xp_mult":          {"default": 1.0,   "tipo": "float", "cat": "🔬 Investigación",    "label": "×XP por investigación",                       "step": 0.1},
    "investigacion_recomp_mult":      {"default": 1.0,   "tipo": "float", "cat": "🔬 Investigación",    "label": "×Recompensas de investigación",               "step": 0.1},
    "stamina_explorar":               {"default": 5,     "tipo": "int",   "cat": "🔬 Investigación",    "label": "Stamina que cuesta investigar en zona",       "step": 1},

    # ── 🔨 CRAFTEO ────────────────────────────────────────────────
    "crafteo_descuento_porcentaje":   {"default": 0,     "tipo": "int",   "cat": "🔨 Crafteo",          "label": "Descuento global de materiales en crafteo (%)", "step": 5},
    "crafteo_cooldown_segundos":      {"default": 0,     "tipo": "int",   "cat": "🔨 Crafteo",          "label": "Cooldown entre crafteos (segundos, 0=libre)", "step": 60},
    "crafteo_prob_bonus_material":    {"default": 0.1,   "tipo": "float", "cat": "🔨 Crafteo",          "label": "Prob. de material extra al craftear (0–1)",   "step": 0.05},
    "crafteo_nivel_minimo":           {"default": 1,     "tipo": "int",   "cat": "🔨 Crafteo",          "label": "Nivel mínimo para craftear",                  "step": 1},

    # ── ⚒️ HERRERO ────────────────────────────────────────────────
    "herrero_prob_exito_tier1":       {"default": 0.9,   "tipo": "float", "cat": "⚒️ Herrero",          "label": "Prob. éxito mejora nivel 1 (0–1)",            "step": 0.05},
    "herrero_prob_exito_tier2":       {"default": 0.7,   "tipo": "float", "cat": "⚒️ Herrero",          "label": "Prob. éxito mejora nivel 2 (0–1)",            "step": 0.05},
    "herrero_prob_exito_tier3":       {"default": 0.5,   "tipo": "float", "cat": "⚒️ Herrero",          "label": "Prob. éxito mejora nivel 3 (0–1)",            "step": 0.05},
    "herrero_prob_exito_tier4":       {"default": 0.3,   "tipo": "float", "cat": "⚒️ Herrero",          "label": "Prob. éxito mejora nivel 4 (0–1)",            "step": 0.05},
    "herrero_costo_base_oro":         {"default": 200,   "tipo": "int",   "cat": "⚒️ Herrero",          "label": "Costo base de mejora en el herrero (oro)",   "step": 50},
    "herrero_descuento_porcentaje":   {"default": 0,     "tipo": "int",   "cat": "⚒️ Herrero",          "label": "Descuento global en herrero (%)",             "step": 5},

    # ── 🔮 ENCANTAMIENTO ──────────────────────────────────────────
    "encantamiento_prob_tier1":       {"default": 0.8,   "tipo": "float", "cat": "🔮 Encantamiento",    "label": "Prob. éxito encantamiento nivel 1 (0–1)",     "step": 0.05},
    "encantamiento_prob_tier2":       {"default": 0.6,   "tipo": "float", "cat": "🔮 Encantamiento",    "label": "Prob. éxito encantamiento nivel 2 (0–1)",     "step": 0.05},
    "encantamiento_prob_tier3":       {"default": 0.4,   "tipo": "float", "cat": "🔮 Encantamiento",    "label": "Prob. éxito encantamiento nivel 3 (0–1)",     "step": 0.05},
    "encantamiento_prob_tier4":       {"default": 0.2,   "tipo": "float", "cat": "🔮 Encantamiento",    "label": "Prob. éxito encantamiento nivel 4 (0–1)",     "step": 0.05},
    "encantamiento_costo_base":       {"default": 100,   "tipo": "int",   "cat": "🔮 Encantamiento",    "label": "Costo base de encantamiento (oro)",           "step": 25},

    # ── 🏷️ SUBASTAS ───────────────────────────────────────────────
    "subasta_duracion_horas":         {"default": 24,    "tipo": "int",   "cat": "🏷️ Subastas",         "label": "Duración de una subasta (horas)",             "step": 6},
    "subasta_fee_porcentaje":         {"default": 5,     "tipo": "int",   "cat": "🏷️ Subastas",         "label": "Comisión de la casa en subastas (%)",         "step": 1},
    "subasta_max_activas":            {"default": 3,     "tipo": "int",   "cat": "🏷️ Subastas",         "label": "Subastas activas simultáneas por jugador",    "step": 1},
    "subasta_puja_minima":            {"default": 100,   "tipo": "int",   "cat": "🏷️ Subastas",         "label": "Puja mínima posible (oro)",                   "step": 50},
    "subasta_nivel_minimo":           {"default": 5,     "tipo": "int",   "cat": "🏷️ Subastas",         "label": "Nivel mínimo para usar subastas",             "step": 1},

    # ── 💱 MERCADO P2P ────────────────────────────────────────────
    "p2p_max_listings":               {"default": 5,     "tipo": "int",   "cat": "💱 Mercado P2P",      "label": "Anuncios P2P activos por jugador",            "step": 1},
    "p2p_fee_porcentaje":             {"default": 5,     "tipo": "int",   "cat": "💱 Mercado P2P",      "label": "Comisión del mercado P2P (%)",                "step": 1},
    "p2p_expiracion_horas":           {"default": 48,    "tipo": "int",   "cat": "💱 Mercado P2P",      "label": "Horas hasta que caduca un anuncio P2P",       "step": 12},
    "p2p_nivel_minimo":               {"default": 5,     "tipo": "int",   "cat": "💱 Mercado P2P",      "label": "Nivel mínimo para usar el mercado P2P",       "step": 1},

    # ── 🏰 GREMIOS ────────────────────────────────────────────────
    "gremio_coste_crear":             {"default": 5000,  "tipo": "int",   "cat": "🏰 Gremios",          "label": "Coste en oro para crear un gremio",           "step": 500},
    "gremio_capacidad_inicial":       {"default": 10,    "tipo": "int",   "cat": "🏰 Gremios",          "label": "Capacidad inicial de miembros (nivel 1)",     "step": 1},
    "gremio_exp_por_actividad":       {"default": 10,    "tipo": "int",   "cat": "🏰 Gremios",          "label": "EXP de gremio por actividad de miembro",     "step": 5},
    "gremio_tax_max_porcentaje":      {"default": 20,    "tipo": "int",   "cat": "🏰 Gremios",          "label": "Impuesto máximo permitido en gremio (%)",     "step": 5},
    "gremio_guerra_duracion_horas":   {"default": 24,    "tipo": "int",   "cat": "🏰 Gremios",          "label": "Duración de guerra de gremios (horas)",       "step": 6},
    "gremio_war_nivel_minimo":        {"default": 3,     "tipo": "int",   "cat": "🏰 Gremios",          "label": "Nivel de gremio mínimo para declarar guerra", "step": 1},

    # ── 🗡️ GUERRA FACCIONES ──────────────────────────────────────
    "gf_duracion_horas":              {"default": 1,     "tipo": "int",   "cat": "🗡️ Facciones",        "label": "Duración de la guerra de facciones (horas)", "step": 1},
    "gf_cooldown_ataque_segundos":    {"default": 60,    "tipo": "int",   "cat": "🗡️ Facciones",        "label": "Cooldown entre ataques en guerra (segundos)", "step": 30},
    "gf_recompensa_oro_victoria":     {"default": 500,   "tipo": "int",   "cat": "🗡️ Facciones",        "label": "Oro de recompensa al ganar guerra",           "step": 100},
    "gf_recompensa_et_victoria":      {"default": 20,    "tipo": "int",   "cat": "🗡️ Facciones",        "label": "Eternium de recompensa al ganar guerra",     "step": 5},
    "gf_puntos_por_ataque":           {"default": 10,    "tipo": "int",   "cat": "🗡️ Facciones",        "label": "Puntos ganados por ataque exitoso",           "step": 5},

    # ── 🐉 JEFES RAID ─────────────────────────────────────────────
    "jefe_hp_base":                   {"default": 10000, "tipo": "int",   "cat": "🐉 Jefes Raid",       "label": "HP base dificultad Normal",                   "step": 1000},
    "jefe_mult_facil":                {"default": 0.5,   "tipo": "float", "cat": "🐉 Jefes Raid",       "label": "×HP dificultad Fácil",                        "step": 0.1},
    "jefe_mult_dificil":              {"default": 2.0,   "tipo": "float", "cat": "🐉 Jefes Raid",       "label": "×HP dificultad Difícil",                      "step": 0.25},
    "jefe_mult_legendario":           {"default": 4.0,   "tipo": "float", "cat": "🐉 Jefes Raid",       "label": "×HP dificultad Legendario",                   "step": 0.5},
    "jefe_cooldown_ataque_segundos":  {"default": 30,    "tipo": "int",   "cat": "🐉 Jefes Raid",       "label": "Cooldown entre ataques al jefe (segundos)",   "step": 10},
    "jefe_xp_por_dano":               {"default": 0.5,   "tipo": "float", "cat": "🐉 Jefes Raid",       "label": "XP por cada punto de daño al jefe",           "step": 0.05},
    "jefe_oro_por_dano":              {"default": 0.2,   "tipo": "float", "cat": "🐉 Jefes Raid",       "label": "Oro por cada punto de daño al jefe",          "step": 0.05},
    "jefe_max_jugadores":             {"default": 30,    "tipo": "int",   "cat": "🐉 Jefes Raid",       "label": "Máximo de jugadores en una raid",             "step": 5},

    # ── 💀 MUERTE & RESPAWN ───────────────────────────────────────
    "muerte_xp_penalizacion":         {"default": 5,     "tipo": "int",   "cat": "💀 Muerte y Respawn", "label": "% XP perdida al morir (0=sin pérdida)",       "step": 1},
    "muerte_oro_penalizacion":        {"default": 0,     "tipo": "int",   "cat": "💀 Muerte y Respawn", "label": "% oro perdido al morir (0=sin pérdida)",      "step": 1},
    "muerte_hp_respawn_porcentaje":   {"default": 50,    "tipo": "int",   "cat": "💀 Muerte y Respawn", "label": "% HP con el que respawnea el jugador",        "step": 5},
    "muerte_cooldown_respawn_seg":    {"default": 300,   "tipo": "int",   "cat": "💀 Muerte y Respawn", "label": "Segundos de espera para respawnear",          "step": 60},
    "pve_muerte_oro_azul":            {"default": 15,    "tipo": "int",   "cat": "💀 Muerte y Respawn", "label": "PvE Azul: % oro perdido al morir",            "step": 5},
    "pve_muerte_oro_amarilla":        {"default": 15,    "tipo": "int",   "cat": "💀 Muerte y Respawn", "label": "PvE Amarilla: % oro perdido al morir",        "step": 5},
    "pve_muerte_oro_roja":            {"default": 15,    "tipo": "int",   "cat": "💀 Muerte y Respawn", "label": "PvE Roja: % oro perdido al morir",            "step": 5},
    "pve_muerte_oro_negra":           {"default": 15,    "tipo": "int",   "cat": "💀 Muerte y Respawn", "label": "PvE Negra: % oro perdido al morir",           "step": 5},
    "pvp_muerte_oro_amarilla":        {"default": 10,    "tipo": "int",   "cat": "💀 Muerte y Respawn", "label": "PvP/Caza Amarilla: % oro perdido al morir",   "step": 5},
    "pvp_muerte_oro_roja":            {"default": 50,    "tipo": "int",   "cat": "💀 Muerte y Respawn", "label": "PvP/Caza Roja: % oro perdido al morir",       "step": 5},
    "pvp_muerte_oro_negra":           {"default": 100,   "tipo": "int",   "cat": "💀 Muerte y Respawn", "label": "PvP/Caza Negra: % oro perdido al morir",      "step": 10},
    "pvp_muerte_items_amarilla":      {"default": 1,     "tipo": "int",   "cat": "💀 Muerte y Respawn", "label": "PvP/Caza Amarilla: objetos perdidos (-1=todos)","step": 1},
    "pvp_muerte_items_roja":          {"default": 5,     "tipo": "int",   "cat": "💀 Muerte y Respawn", "label": "PvP/Caza Roja: objetos perdidos (-1=todos)",  "step": 1},
    "pvp_muerte_items_negra":         {"default": -1,    "tipo": "int",   "cat": "💀 Muerte y Respawn", "label": "PvP/Caza Negra: objetos perdidos (-1=todos)", "step": 1},

    # ── 📊 ECONOMÍA ────────────────────────────────────────────────
    "economia_pve_xp_mult":           {"default": 1.0,   "tipo": "float", "cat": "📊 Economía",         "label": "×XP global en PvE",                           "step": 0.1},
    "economia_pve_oro_mult":          {"default": 1.0,   "tipo": "float", "cat": "📊 Economía",         "label": "×Oro global en PvE",                          "step": 0.1},
    "economia_xp_formula_base":       {"default": 100,   "tipo": "int",   "cat": "📊 Economía",         "label": "XP base para subir al nivel 2",               "step": 10},
    "economia_xp_formula_exp":        {"default": 1.5,   "tipo": "float", "cat": "📊 Economía",         "label": "Exponente curva XP (1.5=progresión media)",   "step": 0.05},
    "economia_pvp_oro_base":          {"default": 50,    "tipo": "int",   "cat": "📊 Economía",         "label": "Oro base por victoria PvP",                   "step": 10},
    "economia_pvp_xp_base":           {"default": 80,    "tipo": "int",   "cat": "📊 Economía",         "label": "XP base por victoria PvP",                    "step": 10},
    "economia_gold_cap":              {"default": 0,     "tipo": "int",   "cat": "📊 Economía",         "label": "Límite máx. oro por jugador (0=ilimitado)",   "step": 10000},

    # ── ✈️ VIAJES ─────────────────────────────────────────────────
    "viaje_tiempo_base_segundos":     {"default": 60,    "tipo": "int",   "cat": "✈️ Viajes",           "label": "Tiempo base de viaje entre zonas (segundos)", "step": 10},
    "viaje_stamina_coste":            {"default": 5,     "tipo": "int",   "cat": "✈️ Viajes",           "label": "Stamina que cuesta viajar",                   "step": 1},
    "viaje_cooldown_segundos":        {"default": 30,    "tipo": "int",   "cat": "✈️ Viajes",           "label": "Cooldown mínimo entre viajes (segundos)",     "step": 10},

    # ── 🤝 INVITACIONES ───────────────────────────────────────────
    "invitacion_pociones_recluta":    {"default": 2,     "tipo": "int",   "cat": "🤝 Invitaciones",     "label": "Pociones que recibe el recluta al unirse",    "step": 1},
    "invitacion_nivel_bonus":         {"default": 15,    "tipo": "int",   "cat": "🤝 Invitaciones",     "label": "Nivel del recluta para activar bonus",        "step": 1},
    "invitacion_oro_reclutador":      {"default": 0,     "tipo": "int",   "cat": "🤝 Invitaciones",     "label": "Oro extra que recibe el reclutador (0=no)",   "step": 100},
    "invitacion_max_reclutas":        {"default": 0,     "tipo": "int",   "cat": "🤝 Invitaciones",     "label": "Máximo de reclutas por jugador (0=ilimitado)","step": 5},

    # ── 🎲 PROBABILIDADES GLOBALES ────────────────────────────────
    "prob_objeto_raro_drop":          {"default": 0.05,  "tipo": "float", "cat": "🎲 Probabilidades",   "label": "Prob. drop raro en combate (0–1)",            "step": 0.01},
    "prob_objeto_epico_drop":         {"default": 0.01,  "tipo": "float", "cat": "🎲 Probabilidades",   "label": "Prob. drop épico (0–1)",                      "step": 0.005},
    "prob_objeto_legendario_drop":    {"default": 0.001, "tipo": "float", "cat": "🎲 Probabilidades",   "label": "Prob. drop legendario (0–1)",                 "step": 0.001},
    "prob_evento_clima_cambio":       {"default": 0.1,   "tipo": "float", "cat": "🎲 Probabilidades",   "label": "Prob. cambio de clima automático por hora",   "step": 0.05},

    # ── 🏆 RANKINGS ────────────────────────────────────────────────
    "ranking_premio_xp_top1":         {"default": 5000,  "tipo": "int",   "cat": "🏆 Rankings",         "label": "Premio XP al jugador #1 semanal",             "step": 500},
    "ranking_premio_xp_top3":         {"default": 2500,  "tipo": "int",   "cat": "🏆 Rankings",         "label": "Premio XP al Top 3 semanal",                  "step": 250},
    "ranking_premio_xp_top10":        {"default": 1000,  "tipo": "int",   "cat": "🏆 Rankings",         "label": "Premio XP al Top 10 semanal",                 "step": 100},
    "ranking_premio_oro_top1":        {"default": 10000, "tipo": "int",   "cat": "🏆 Rankings",         "label": "Premio oro al jugador #1 semanal",            "step": 1000},
    "ranking_premio_oro_top3":        {"default": 5000,  "tipo": "int",   "cat": "🏆 Rankings",         "label": "Premio oro al Top 3 semanal",                 "step": 500},
    "ranking_reset_dia_semana":       {"default": 0,     "tipo": "int",   "cat": "🏆 Rankings",         "label": "Día de reset semanal (0=lunes, 6=domingo)",   "step": 1},

    # ── ⏰ EVENTOS AUTOMÁTICOS ────────────────────────────────────
    "evento_guerra_hora_inicio":      {"default": 20,    "tipo": "int",   "cat": "⏰ Eventos Auto",     "label": "Hora de inicio de guerra auto (0–23)",        "step": 1},
    "evento_guerra_duracion_min":     {"default": 60,    "tipo": "int",   "cat": "⏰ Eventos Auto",     "label": "Duración de guerra auto (minutos)",           "step": 15},
    "evento_jefe_intervalo_horas":    {"default": 6,     "tipo": "int",   "cat": "⏰ Eventos Auto",     "label": "Horas entre apariciones de jefe automático", "step": 1},
    "evento_bonus_xp_activo":         {"default": 0,     "tipo": "bool",  "cat": "⏰ Eventos Auto",     "label": "¿Evento de doble XP activo?",                 "step": 1},
    "evento_bonus_oro_activo":        {"default": 0,     "tipo": "bool",  "cat": "⏰ Eventos Auto",     "label": "¿Evento de doble oro activo?",                "step": 1},
    "evento_bonus_xp_mult":           {"default": 2.0,   "tipo": "float", "cat": "⏰ Eventos Auto",     "label": "×XP durante el evento de doble XP",           "step": 0.5},
    "evento_bonus_oro_mult":          {"default": 2.0,   "tipo": "float", "cat": "⏰ Eventos Auto",     "label": "×Oro durante el evento de doble oro",         "step": 0.5},

    # ── ⚔️ ARMAS (masivo) ─────────────────────────────────────────
    "bg_a_daño":              {"default": 1.0,  "tipo": "float", "cat": "⚔️ Armas",     "label": "×Daño de todas las armas",                "step": 0.1},
    "bg_a_critico":           {"default": 1.0,  "tipo": "float", "cat": "⚔️ Armas",     "label": "×Crítico de todas las armas",             "step": 0.05},
    "bg_a_velocidad":         {"default": 1.0,  "tipo": "float", "cat": "⚔️ Armas",     "label": "×Velocidad de todas las armas",           "step": 0.05},
    "bg_a_precio_oro":        {"default": 1.0,  "tipo": "float", "cat": "⚔️ Armas",     "label": "×Precio oro de todas las armas",          "step": 0.1},
    "bg_a_precio_eth":        {"default": 1.0,  "tipo": "float", "cat": "⚔️ Armas",     "label": "×Precio eternium de todas las armas",     "step": 0.1},
    "bg_a_nivel_req_offset":  {"default": 0,    "tipo": "int",   "cat": "⚔️ Armas",     "label": "+/- Nivel requerido global de armas",     "step": 1},

    # ── 🛡️ ARMADURAS (masivo) ─────────────────────────────────────
    "bg_ar_defensa":          {"default": 1.0,  "tipo": "float", "cat": "🛡️ Armaduras", "label": "×Defensa de todas las armaduras",          "step": 0.1},
    "bg_ar_resistencia":      {"default": 1.0,  "tipo": "float", "cat": "🛡️ Armaduras", "label": "×Resistencia crítico de armaduras",        "step": 0.05},
    "bg_ar_vida_extra":       {"default": 1.0,  "tipo": "float", "cat": "🛡️ Armaduras", "label": "×Vida extra de todas las armaduras",       "step": 0.1},
    "bg_ar_precio_oro":       {"default": 1.0,  "tipo": "float", "cat": "🛡️ Armaduras", "label": "×Precio oro de todas las armaduras",       "step": 0.1},
    "bg_ar_precio_eth":       {"default": 1.0,  "tipo": "float", "cat": "🛡️ Armaduras", "label": "×Precio eternium de armaduras",            "step": 0.1},
    "bg_ar_nivel_req_offset": {"default": 0,    "tipo": "int",   "cat": "🛡️ Armaduras", "label": "+/- Nivel requerido global de armaduras",  "step": 1},

    # ── 🧪 POCIONES (masivo) ──────────────────────────────────────
    "bg_p_efecto_mult":       {"default": 1.0,  "tipo": "float", "cat": "🧪 Pociones",  "label": "×Efectividad de todas las pociones",       "step": 0.1},
    "bg_p_duracion_mult":     {"default": 1.0,  "tipo": "float", "cat": "🧪 Pociones",  "label": "×Duración de efectos de pociones",         "step": 0.1},
    "bg_p_precio_oro":        {"default": 1.0,  "tipo": "float", "cat": "🧪 Pociones",  "label": "×Precio oro de todas las pociones",        "step": 0.1},
    "bg_p_precio_eth":        {"default": 1.0,  "tipo": "float", "cat": "🧪 Pociones",  "label": "×Precio eternium de pociones",             "step": 0.1},
    "bg_p_nivel_req_offset":  {"default": 0,    "tipo": "int",   "cat": "🧪 Pociones",  "label": "+/- Nivel requerido global de pociones",   "step": 1},

    # ── 🪨 MATERIALES (masivo) ────────────────────────────────────
    "bg_mat_valor_crafteo":    {"default": 1.0,  "tipo": "float", "cat": "🪨 Materiales","label": "×Valor de crafteo de todos los materiales","step": 0.1},
    "bg_mat_precio_venta_oro": {"default": 1.0,  "tipo": "float", "cat": "🪨 Materiales","label": "×Precio venta oro de materiales",          "step": 0.1},
    "bg_mat_precio_venta_eth": {"default": 1.0,  "tipo": "float", "cat": "🪨 Materiales","label": "×Precio venta eternium de materiales",     "step": 0.1},
    "bg_mat_drop_mult":        {"default": 1.0,  "tipo": "float", "cat": "🪨 Materiales","label": "×Prob. drop de todos los materiales",      "step": 0.1},
    "bg_mat_rareza_bonus":     {"default": 0,    "tipo": "int",   "cat": "🪨 Materiales","label": "+/- Rareza global de materiales",          "step": 1},

    # ── 🎁 PREMIOS PvE POR ZONA ────────────────────────────────────
    "pve_azul_xp_base":               {"default": 60,    "tipo": "int",   "cat": "🎁 Premios PvE",      "label": "PvE Azul: XP base por combate ganado",       "step": 10},
    "pve_azul_oro_base":              {"default": 40,    "tipo": "int",   "cat": "🎁 Premios PvE",      "label": "PvE Azul: Oro base por combate ganado",       "step": 5},
    "pve_amarilla_xp_base":           {"default": 120,   "tipo": "int",   "cat": "🎁 Premios PvE",      "label": "PvE Amarilla: XP base por combate ganado",   "step": 10},
    "pve_amarilla_oro_base":          {"default": 80,    "tipo": "int",   "cat": "🎁 Premios PvE",      "label": "PvE Amarilla: Oro base por combate ganado",  "step": 10},
    "pve_roja_xp_base":               {"default": 220,   "tipo": "int",   "cat": "🎁 Premios PvE",      "label": "PvE Roja: XP base por combate ganado",       "step": 20},
    "pve_roja_oro_base":              {"default": 150,   "tipo": "int",   "cat": "🎁 Premios PvE",      "label": "PvE Roja: Oro base por combate ganado",      "step": 20},
    "pve_negra_xp_base":              {"default": 400,   "tipo": "int",   "cat": "🎁 Premios PvE",      "label": "PvE Negra: XP base por combate ganado",      "step": 50},
    "pve_negra_oro_base":             {"default": 280,   "tipo": "int",   "cat": "🎁 Premios PvE",      "label": "PvE Negra: Oro base por combate ganado",     "step": 50},
    "pve_negra_et_base":              {"default": 5,     "tipo": "int",   "cat": "🎁 Premios PvE",      "label": "PvE Negra: Eternium base por combate",       "step": 1},
    "pve_xp_nivel_mult":              {"default": 1.05,  "tipo": "float", "cat": "🎁 Premios PvE",      "label": "x XP extra por nivel del monstruo",          "step": 0.01},
    "pve_streak_bonus_activo":        {"default": 0,     "tipo": "bool",  "cat": "🎁 Premios PvE",      "label": "Bonus de racha activo en PvE",               "step": 1},
    "pve_streak_max_mult":            {"default": 2.0,   "tipo": "float", "cat": "🎁 Premios PvE",      "label": "Multiplicador maximo de racha PvE",           "step": 0.1},

    # ── 🏹 PREMIOS PvP POR ZONA ────────────────────────────────────
    "pvp_azul_xp_victoria":           {"default": 50,    "tipo": "int",   "cat": "🏹 Premios PvP",      "label": "PvP Azul: XP al vencer",                     "step": 10},
    "pvp_azul_oro_victoria":          {"default": 30,    "tipo": "int",   "cat": "🏹 Premios PvP",      "label": "PvP Azul: Oro al vencer",                    "step": 10},
    "pvp_amarilla_xp_victoria":       {"default": 120,   "tipo": "int",   "cat": "🏹 Premios PvP",      "label": "PvP Amarilla: XP al vencer",                 "step": 10},
    "pvp_amarilla_oro_robo_pct":      {"default": 10,    "tipo": "int",   "cat": "🏹 Premios PvP",      "label": "PvP Amarilla: % del oro del vencido robado", "step": 5},
    "pvp_roja_xp_victoria":           {"default": 250,   "tipo": "int",   "cat": "🏹 Premios PvP",      "label": "PvP Roja: XP al vencer",                     "step": 25},
    "pvp_roja_oro_robo_pct":          {"default": 25,    "tipo": "int",   "cat": "🏹 Premios PvP",      "label": "PvP Roja: % del oro del vencido robado",     "step": 5},
    "pvp_negra_xp_victoria":          {"default": 500,   "tipo": "int",   "cat": "🏹 Premios PvP",      "label": "PvP Negra: XP al vencer",                    "step": 50},
    "pvp_negra_oro_robo_pct":         {"default": 50,    "tipo": "int",   "cat": "🏹 Premios PvP",      "label": "PvP Negra: % del oro del vencido robado",    "step": 5},
    "pvp_negra_et_bonus":             {"default": 10,    "tipo": "int",   "cat": "🏹 Premios PvP",      "label": "PvP Negra: Eternium bonus al vencer",        "step": 1},
    "pvp_xp_mult_nivel":              {"default": 1.0,   "tipo": "float", "cat": "🏹 Premios PvP",      "label": "x XP si vences a jugador de mayor nivel",   "step": 0.1},
    "pvp_racha_kills_bonus":          {"default": 0,     "tipo": "bool",  "cat": "🏹 Premios PvP",      "label": "Bonus por racha de kills PvP activo",         "step": 1},

    # ── 🏰 PREMIOS MAZMORRAS POR COLOR ─────────────────────────────
    "maz_azul_xp_bonus":              {"default": 200,   "tipo": "int",   "cat": "🏰 Premios Mazmorras","label": "Mazmorra Azul: XP bonus al completar",       "step": 50},
    "maz_azul_oro_bonus":             {"default": 300,   "tipo": "int",   "cat": "🏰 Premios Mazmorras","label": "Mazmorra Azul: Oro bonus al completar",      "step": 50},
    "maz_amarilla_xp_bonus":          {"default": 400,   "tipo": "int",   "cat": "🏰 Premios Mazmorras","label": "Mazmorra Amarilla: XP bonus al completar",   "step": 50},
    "maz_amarilla_oro_bonus":         {"default": 600,   "tipo": "int",   "cat": "🏰 Premios Mazmorras","label": "Mazmorra Amarilla: Oro bonus al completar",  "step": 50},
    "maz_roja_xp_bonus":              {"default": 700,   "tipo": "int",   "cat": "🏰 Premios Mazmorras","label": "Mazmorra Roja: XP bonus al completar",       "step": 100},
    "maz_roja_oro_bonus":             {"default": 1000,  "tipo": "int",   "cat": "🏰 Premios Mazmorras","label": "Mazmorra Roja: Oro bonus al completar",      "step": 100},
    "maz_negra_xp_bonus":             {"default": 1500,  "tipo": "int",   "cat": "🏰 Premios Mazmorras","label": "Mazmorra Negra: XP bonus al completar",      "step": 200},
    "maz_negra_oro_bonus":            {"default": 2000,  "tipo": "int",   "cat": "🏰 Premios Mazmorras","label": "Mazmorra Negra: Oro bonus al completar",     "step": 200},
    "maz_negra_et_bonus":             {"default": 25,    "tipo": "int",   "cat": "🏰 Premios Mazmorras","label": "Mazmorra Negra: Eternium bonus al completar","step": 5},
    "maz_dificil_xp_extra_pct":       {"default": 50,    "tipo": "int",   "cat": "🏰 Premios Mazmorras","label": "Mazmorra Dificil: % XP extra sobre normal",  "step": 10},
    "maz_dificil_oro_extra_pct":      {"default": 50,    "tipo": "int",   "cat": "🏰 Premios Mazmorras","label": "Mazmorra Dificil: % Oro extra sobre normal", "step": 10},
    "maz_prob_item_raro":             {"default": 0.15,  "tipo": "float", "cat": "🏰 Premios Mazmorras","label": "Prob. drop item raro al terminar mazmorra",  "step": 0.05},
    "maz_prob_item_epico":            {"default": 0.05,  "tipo": "float", "cat": "🏰 Premios Mazmorras","label": "Prob. drop item epico al terminar mazmorra", "step": 0.01},

    # ── 🐉 PREMIOS JEFES RAID (detalle) ────────────────────────────
    "jefe_et_base":                   {"default": 30,    "tipo": "int",   "cat": "🐉 Jefes Raid",       "label": "Eternium base por raid completado",           "step": 5},
    "jefe_et_mult_dificil":           {"default": 2.0,   "tipo": "float", "cat": "🐉 Jefes Raid",       "label": "x Eternium en dificultad Dificil/Legendario", "step": 0.25},
    "jefe_item_prob_normal":          {"default": 0.5,   "tipo": "float", "cat": "🐉 Jefes Raid",       "label": "Prob. item drop en raid Normal",              "step": 0.05},
    "jefe_item_prob_dificil":         {"default": 0.75,  "tipo": "float", "cat": "🐉 Jefes Raid",       "label": "Prob. item drop en raid Dificil",             "step": 0.05},
    "jefe_item_prob_legendario":      {"default": 1.0,   "tipo": "float", "cat": "🐉 Jefes Raid",       "label": "Prob. item drop en raid Legendario",          "step": 0.05},
    "jefe_oro_bonus_tanque":          {"default": 200,   "tipo": "int",   "cat": "🐉 Jefes Raid",       "label": "Oro bonus al jugador mas danejado (tanque)",  "step": 50},
    "jefe_xp_bonus_mvp":              {"default": 500,   "tipo": "int",   "cat": "🐉 Jefes Raid",       "label": "XP bonus al MVP (mas dano hecho al jefe)",   "step": 100},
    "jefe_participacion_xp_min":      {"default": 100,   "tipo": "int",   "cat": "🐉 Jefes Raid",       "label": "XP minima por participar en raid sin dano",  "step": 25},

    # ── ⚔️ PREMIOS GUERRA GREMIOS ──────────────────────────────────
    "gg_oro_victoria":                {"default": 1000,  "tipo": "int",   "cat": "GG Premios Gremios",  "label": "Oro por victoria en guerra de gremios",      "step": 100},
    "gg_xp_victoria":                 {"default": 500,   "tipo": "int",   "cat": "GG Premios Gremios",  "label": "XP por victoria en guerra de gremios",       "step": 50},
    "gg_et_victoria":                 {"default": 15,    "tipo": "int",   "cat": "GG Premios Gremios",  "label": "Eternium por victoria en guerra de gremios", "step": 5},
    "gg_oro_participacion":           {"default": 200,   "tipo": "int",   "cat": "GG Premios Gremios",  "label": "Oro por participar aunque se pierda",        "step": 50},
    "gg_xp_participacion":            {"default": 100,   "tipo": "int",   "cat": "GG Premios Gremios",  "label": "XP por participar aunque se pierda",          "step": 25},
    "gg_puntos_por_kill":             {"default": 10,    "tipo": "int",   "cat": "GG Premios Gremios",  "label": "Puntos de gremio por kill en guerra",        "step": 5},
    "gg_contribucion_exp":            {"default": 50,    "tipo": "int",   "cat": "GG Premios Gremios",  "label": "EXP de gremio por contribucion en guerra",   "step": 10},
    "gg_derrota_oro":                 {"default": 50,    "tipo": "int",   "cat": "GG Premios Gremios",  "label": "Oro de consolacion al perder guerra",        "step": 25},

    # ── 🗡️ PREMIOS GUERRA FACCIONES (detalle) ──────────────────────
    "gf_recompensa_1er":              {"default": 1000,  "tipo": "int",   "cat": "GF Premios Facciones","label": "Premio 1er puesto individual (oro)",          "step": 100},
    "gf_recompensa_2do":              {"default": 600,   "tipo": "int",   "cat": "GF Premios Facciones","label": "Premio 2do puesto individual (oro)",          "step": 100},
    "gf_recompensa_3er":              {"default": 300,   "tipo": "int",   "cat": "GF Premios Facciones","label": "Premio 3er puesto individual (oro)",          "step": 50},
    "gf_recompensa_resto":            {"default": 100,   "tipo": "int",   "cat": "GF Premios Facciones","label": "Premio resto de participantes (oro)",         "step": 25},
    "gf_xp_participacion":            {"default": 200,   "tipo": "int",   "cat": "GF Premios Facciones","label": "XP por participar en guerra de facciones",   "step": 50},
    "gf_et_top3":                     {"default": 5,     "tipo": "int",   "cat": "GF Premios Facciones","label": "Eternium extra al Top 3 de la guerra",       "step": 1},
    "gf_xp_kill":                     {"default": 50,    "tipo": "int",   "cat": "GF Premios Facciones","label": "XP por cada kill durante la guerra",         "step": 10},
    "gf_puntos_kill":                 {"default": 15,    "tipo": "int",   "cat": "GF Premios Facciones","label": "Puntos individuales por kill en guerra",     "step": 5},

    # ── 🗓️ PREMIOS LOGIN DIARIO & MISIONES ────────────────────────
    "login_oro_dia1":                 {"default": 50,    "tipo": "int",   "cat": "Login y Misiones",    "label": "Oro login diario dia 1 / racha rota",        "step": 10},
    "login_xp_dia1":                  {"default": 30,    "tipo": "int",   "cat": "Login y Misiones",    "label": "XP login diario dia 1 / racha rota",          "step": 10},
    "login_racha_mult":               {"default": 0.1,   "tipo": "float", "cat": "Login y Misiones",    "label": "Extra por cada dia de racha (0.1 = +10%)",   "step": 0.05},
    "login_racha_max_dias":           {"default": 7,     "tipo": "int",   "cat": "Login y Misiones",    "label": "Dias de racha maximos para el multiplicador","step": 1},
    "login_dia7_et_bonus":            {"default": 10,    "tipo": "int",   "cat": "Login y Misiones",    "label": "Eternium bonus en dia 7 de racha",           "step": 1},
    "mision_xp_facil":                {"default": 80,    "tipo": "int",   "cat": "Login y Misiones",    "label": "XP recompensa mision facil",                  "step": 10},
    "mision_oro_facil":               {"default": 60,    "tipo": "int",   "cat": "Login y Misiones",    "label": "Oro recompensa mision facil",                 "step": 10},
    "mision_xp_media":                {"default": 200,   "tipo": "int",   "cat": "Login y Misiones",    "label": "XP recompensa mision media",                  "step": 25},
    "mision_oro_media":               {"default": 150,   "tipo": "int",   "cat": "Login y Misiones",    "label": "Oro recompensa mision media",                 "step": 25},
    "mision_xp_dificil":              {"default": 450,   "tipo": "int",   "cat": "Login y Misiones",    "label": "XP recompensa mision dificil",                "step": 50},
    "mision_oro_dificil":             {"default": 350,   "tipo": "int",   "cat": "Login y Misiones",    "label": "Oro recompensa mision dificil",               "step": 50},
    "mision_et_dificil":              {"default": 5,     "tipo": "int",   "cat": "Login y Misiones",    "label": "Eternium recompensa mision dificil",          "step": 1},
    "mision_max_diarias":             {"default": 3,     "tipo": "int",   "cat": "Login y Misiones",    "label": "Numero de misiones diarias por jugador",      "step": 1},
}



# ─── API PÚBLICA ─────────────────────────────────────────────────────────────

def get(clave: str, default=None):
    schema   = CONFIG_SCHEMA.get(clave, {})
    tipo     = schema.get("tipo", "str")
    fallback = schema.get("default", default)
    try:
        raw = db_helper.obtener_config(clave, None)
        if raw is None:
            return fallback
        if tipo == "int":
            return int(float(raw))
        if tipo == "float":
            return float(raw)
        if tipo == "bool":
            return raw.lower() in ("1", "true", "yes")
        return raw
    except Exception:
        return fallback


def set(clave: str, valor) -> bool:
    try:
        db_helper.establecer_config(clave, str(valor))
        _sync_runtime(clave, valor)
        return True
    except Exception:
        return False


def seed_defaults():
    for clave, info in CONFIG_SCHEMA.items():
        try:
            if db_helper.obtener_config(clave, None) is None:
                db_helper.establecer_config(clave, str(info["default"]))
        except Exception:
            pass


def get_categories() -> dict:
    cats: dict = {}
    for clave, info in CONFIG_SCHEMA.items():
        cat = info["cat"]
        if cat not in cats:
            cats[cat] = []
        cats[cat].append({"clave": clave, **info, "valor_actual": get(clave)})
    return cats


# ─── SINCRONIZACIÓN EN TIEMPO REAL ───────────────────────────────────────────

def _sync_runtime(clave: str, valor):
    try:
        import config_balance as _cb
        _mapa_directo = {
            "stamina_max_base":            ("STAMINA_MAX_BASE",                   int),
            "stamina_regen_segundos":      ("STAMINA_REGENERACION_SEGUNDOS",      int),
            "stamina_bonus_por_recluta":   ("STAMINA_BONUS_POR_RECLUTA",          int),
            "stamina_max_extra":           ("STAMINA_MAX_EXTRA",                   int),
            "mazmorra_limite_diario":      ("MAZMORRAS_LIMITE_DIARIO",            int),
            "banco_credito_a_eternium":    ("BANCO_CREDITO_A_ETERNIUM",           int),
            "banco_credito_a_oro":         ("BANCO_CREDITO_A_ORO",                int),
            "tienda_venta_porcentaje":     ("TIENDA_VENTA_PORCENTAJE",            float),
            "tienda_rotacion_dias":        ("TIENDA_ROTACION_CREDITOS_DIAS",      int),
            "taberna_costo_descansar":     ("TABERNA_COSTO_DESCANSAR",            int),
            "taberna_stamina_recupera":    ("TABERNA_STAMINA_RECUPERA",           int),
            "taberna_cooldown_segundos":   ("TABERNA_COOLDOWN_SEGUNDOS",          int),
            "combate_pvp_cooldown_min":    ("COMBATE_PVP_COOLDOWN_MIN",           int),
            "combate_pvp_nivel_minimo":    ("COMBATE_PVP_NIVEL_MINIMO",           int),
            "combate_pvp_oro_victoria":    ("COMBATE_PVP_ORO_VICTORIA",           int),
            "combate_pvp_xp_victoria":     ("COMBATE_PVP_XP_VICTORIA",            int),
            "subasta_duracion_horas":      ("SUBASTA_DURACION_HORAS",             int),
            "subasta_fee_porcentaje":      ("SUBASTA_FEE_PORCENTAJE",             int),
            "subasta_max_activas":         ("SUBASTA_MAX_ACTIVAS",                int),
            "gremio_coste_crear":          ("GREMIO_COSTE_CREAR",                 int),
            "gremio_capacidad_inicial":    ("GREMIO_CAPACIDAD_INICIAL",           int),
            "jefe_hp_base":                ("JEFE_HP_BASE",                       int),
            "jefe_max_jugadores":          ("JEFE_MAX_JUGADORES",                  int),
            "invitacion_pociones_recluta": ("INVITACION_RECLUTA_RECIBE_POCIONES", int),
            "invitacion_nivel_bonus":      ("INVITACION_NIVEL_REQUERIDO_BONUS",   int),
            "evento_bonus_xp_activo":      ("EVENTO_BONUS_XP_ACTIVO",             bool),
            "evento_bonus_oro_activo":     ("EVENTO_BONUS_ORO_ACTIVO",            bool),
            "evento_bonus_xp_mult":        ("EVENTO_BONUS_XP_MULT",               float),
            "evento_bonus_oro_mult":       ("EVENTO_BONUS_ORO_MULT",              float),
        }
        if clave in _mapa_directo:
            attr, tipo = _mapa_directo[clave]
            if tipo is bool:
                setattr(_cb, attr, str(valor).lower() in ("1", "true", "yes"))
            else:
                setattr(_cb, attr, tipo(valor))

        if clave.startswith("stamina_coste_"):
            zona = clave.replace("stamina_coste_", "")
            if hasattr(_cb, "STAMINA_COSTE_POR_ZONA") and zona in _cb.STAMINA_COSTE_POR_ZONA:
                _cb.STAMINA_COSTE_POR_ZONA[zona] = int(valor)

        if clave.startswith("mazmorra_coste_"):
            zona = clave.replace("mazmorra_coste_", "")
            if hasattr(_cb, "MAZMORRAS_COSTES_ENTRADA") and zona in _cb.MAZMORRAS_COSTES_ENTRADA:
                _cb.MAZMORRAS_COSTES_ENTRADA[zona] = int(valor)

        if clave.startswith("recoleccion_cooldown_"):
            zona = clave.replace("recoleccion_cooldown_", "")
            if hasattr(_cb, "RECOLECCION_COOLDOWN") and zona in _cb.RECOLECCION_COOLDOWN:
                _cb.RECOLECCION_COOLDOWN[zona] = int(valor)

        if clave.startswith("investigacion_cooldown_"):
            zona = clave.replace("investigacion_cooldown_", "")
            if hasattr(_cb, "INVESTIGACION_COOLDOWN") and zona in _cb.INVESTIGACION_COOLDOWN:
                _cb.INVESTIGACION_COOLDOWN[zona] = int(valor)

        # Claves de stamina que explorar.py lee directamente de la DB
        if clave == "stamina_recolectar":
            pass  # explorar.py lee desde DB al momento de uso; no hay cache en config_balance
        if clave == "stamina_explorar":
            pass  # explorar.py lee desde DB al momento de uso; no hay cache en config_balance

    except Exception:
        pass

    if clave in ("tienda_factor_oro", "tienda_factor_eternium",
                 "tienda_factor_creditos", "tienda_venta_porcentaje",
                 "tienda_stock_maximo", "tienda_items_rotacion"):
        try:
            import tienda as _t
            _t.CATALOGO_ORO.clear()
            _t.CATALOGO_ETERNIUM.clear()
            _t.OBJETOS_CREDITOS_MAESTROS.clear()
            _t.construir_catalogos()
        except Exception:
            pass

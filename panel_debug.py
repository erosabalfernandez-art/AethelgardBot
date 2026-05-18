"""
panel_debug.py — Panel Detector de Bugs del Superadmin.

Comando: /panel_debug
Panel separado del panel de admin. Permite:
  - Activar/desactivar el modo debug (sin restricciones del juego)
  - Marcar cada comando/botón del juego como ✅ OK o ❌ Error
  - Los errores generan reportes automáticos en reportes_queue.jsonl
  - Tracking del progreso de testing por categoría
"""
import html as _html
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler

import modo_debug as _md
import superadmin as _sa

# ── Catálogo completo de comandos/botones del juego ──────────────────────────
# Estructura: cat_id único, nombre visible, lista de items.
# Cada item: key único (≤20 chars), label descriptivo, ruta de acceso.

CATALOGO = [
    # ══════════════ COMANDOS DE JUGADOR ══════════════
    {
        "cat_id": "perfil",
        "nombre": "👤 Perfil y Personaje",
        "items": [
            {"key": "perfil",       "label": "/perfil",                 "ruta": ["/perfil"]},
            {"key": "inventario",   "label": "/inventario",             "ruta": ["/inventario"]},
            {"key": "misiones",     "label": "/misiones",               "ruta": ["/misiones"]},
            {"key": "logros",       "label": "/logros",                 "ruta": ["/logros"]},
            {"key": "mis_titulos",  "label": "/mis_titulos",            "ruta": ["/mis_titulos"]},
            {"key": "notifs",       "label": "/notificaciones",         "ruta": ["/notificaciones"]},
            {"key": "mi_codigo",    "label": "/mi_codigo",              "ruta": ["/mi_codigo"]},
            {"key": "usar_codigo",  "label": "/usar_codigo <cod>",      "ruta": ["/usar_codigo <código>"]},
            {"key": "corrupcion",   "label": "/corrupcion",             "ruta": ["/corrupcion"]},
            {"key": "guia",         "label": "/guia",                   "ruta": ["/guia"]},
            {"key": "ayuda",        "label": "/ayuda",                  "ruta": ["/ayuda"]},
            {"key": "comandos_cmd", "label": "/comandos",               "ruta": ["/comandos"]},
            {"key": "destrabar",    "label": "/destrabar",              "ruta": ["/destrabar"]},
            {"key": "rankings",     "label": "/rankings",               "ruta": ["/rankings"]},
            {"key": "teclado_cmd",  "label": "/teclado",                "ruta": ["/teclado"]},
        ],
    },
    {
        "cat_id": "viajes",
        "nombre": "✈️ Viajes y Mapa",
        "items": [
            {"key": "viajar",       "label": "/viajar",                 "ruta": ["/viajar"]},
            {"key": "mapa",         "label": "/mapa",                   "ruta": ["/mapa"]},
            {"key": "est_viaje",    "label": "/estado_viaje",           "ruta": ["/estado_viaje"]},
            {"key": "canc_viaje",   "label": "/cancelar_viaje",         "ruta": ["/cancelar_viaje"]},
            {"key": "vuelo_rap",    "label": "/vuelo_rapido",           "ruta": ["/vuelo_rapido"]},
            {"key": "monturas",     "label": "/mis_monturas",           "ruta": ["/mis_monturas"]},
            {"key": "comprar_mont", "label": "/comprar_montura",        "ruta": ["/comprar_montura"]},
        ],
    },
    {
        "cat_id": "recoleccion",
        "nombre": "⛏️ Recolección",
        "items": [
            {"key": "rec_azul",     "label": "/recolectar — zona azul",     "ruta": ["Zona azul", "/recolectar"]},
            {"key": "rec_amarilla", "label": "/recolectar — zona amarilla", "ruta": ["Zona amarilla", "/recolectar"]},
            {"key": "rec_roja",     "label": "/recolectar — zona roja",     "ruta": ["Zona roja", "/recolectar"]},
            {"key": "rec_negra",    "label": "/recolectar — zona negra",    "ruta": ["Zona negra", "/recolectar"]},
        ],
    },
    {
        "cat_id": "investigacion",
        "nombre": "🔍 Investigación",
        "items": [
            {"key": "inv_azul",     "label": "/investigar — zona azul",     "ruta": ["Zona azul", "/investigar"]},
            {"key": "inv_amarilla", "label": "/investigar — zona amarilla", "ruta": ["Zona amarilla", "/investigar"]},
            {"key": "inv_roja",     "label": "/investigar — zona roja",     "ruta": ["Zona roja", "/investigar"]},
            {"key": "inv_negra",    "label": "/investigar — zona negra",    "ruta": ["Zona negra", "/investigar"]},
        ],
    },
    {
        "cat_id": "mazmorras",
        "nombre": "🏰 Mazmorras",
        "items": [
            {"key": "maz_azul",     "label": "/mazmorra — azul",            "ruta": ["Ciudad azul", "/mazmorra"]},
            {"key": "maz_amarilla", "label": "/mazmorra — amarilla",        "ruta": ["Ciudad amarilla", "/mazmorra"]},
            {"key": "maz_roja",     "label": "/mazmorra — roja",            "ruta": ["Ciudad roja", "/mazmorra"]},
            {"key": "maz_negra",    "label": "/mazmorra — negra",           "ruta": ["Ciudad negra", "/mazmorra"]},
            {"key": "unir_maz",     "label": "/unirme_mazmorra <id>",       "ruta": ["/unirme_mazmorra <id>"]},
            {"key": "abandonar_maz","label": "/abandonar_mazmorra",         "ruta": ["Dentro de mazmorra", "/abandonar_mazmorra"]},
            {"key": "espectar",     "label": "/espectar <id sala>",         "ruta": ["/espectar <id>"]},
        ],
    },
    {
        "cat_id": "combate",
        "nombre": "⚔️ Combate PvP",
        "items": [
            {"key": "duelo",        "label": "/duelo @jugador",             "ruta": ["/duelo @jugador"]},
            {"key": "desact_paz",   "label": "/desactivar_paz",             "ruta": ["/desactivar_paz"]},
            {"key": "pagar_resc",   "label": "/pagar_rescate",              "ruta": ["/pagar_rescate"]},
            {"key": "retomar_cb",   "label": "/retomar_combate",            "ruta": ["/retomar_combate"]},
        ],
    },
    {
        "cat_id": "jefes",
        "nombre": "👹 Jefes de Zona",
        "items": [
            {"key": "jefe_info",    "label": "/jefe_info",                  "ruta": ["/jefe_info"]},
            {"key": "jefe_unirse",  "label": "/jefe_unirse",                "ruta": ["Admin inicia jefe", "/jefe_unirse"]},
            {"key": "jefe_atacar",  "label": "/jefe_atacar",                "ruta": ["Unido al raid", "/jefe_atacar"]},
        ],
    },
    {
        "cat_id": "ciudad_svc",
        "nombre": "🏙️ Ciudad — Servicios",
        "items": [
            {"key": "ciudad_menu",  "label": "/ciudad (menú principal)",           "ruta": ["/ciudad"]},
            {"key": "craftear",     "label": "Ciudad → 🛠️ Servicios → ⚒️ Craftear","ruta": ["/ciudad", "🛠️ Servicios", "⚒️ Craftear"]},
            {"key": "encantar",     "label": "Ciudad → 🛠️ Servicios → ✨ Encantar","ruta": ["/ciudad", "🛠️ Servicios", "✨ Encantar"]},
            {"key": "herrero",      "label": "Ciudad → 🛠️ Servicios → 🔨 Herrero", "ruta": ["/ciudad", "🛠️ Servicios", "🔨 Herrero"]},
            {"key": "taberna",      "label": "Ciudad → 🛠️ Servicios → 🍻 Taberna", "ruta": ["/ciudad", "🛠️ Servicios", "🍻 Taberna"]},
            {"key": "banco",        "label": "Ciudad → 🛠️ Servicios → 🏦 Banco",   "ruta": ["/ciudad", "🛠️ Servicios", "🏦 Banco"]},
            {"key": "montura_svc",  "label": "Ciudad → 🛠️ Servicios → 🐴 Montura", "ruta": ["/ciudad", "🛠️ Servicios", "🐴 Montura"]},
        ],
    },
    {
        "cat_id": "comercio",
        "nombre": "🛒 Comercio",
        "items": [
            {"key": "tienda",       "label": "Ciudad → 🛒 Comercio → Tiendas",    "ruta": ["/ciudad", "🛒 Comercio", "Tiendas"]},
            {"key": "subastas",     "label": "Ciudad → 🛒 Comercio → Subastas",   "ruta": ["/ciudad", "🛒 Comercio", "Subastas"]},
            {"key": "mercado_p2p",  "label": "Ciudad → 🛒 Comercio → Mercado P2P","ruta": ["/ciudad", "🛒 Comercio", "Mercado P2P"]},
            {"key": "bolsa",        "label": "/bolsa",                             "ruta": ["/bolsa"]},
            {"key": "creditos",     "label": "/creditos",                          "ruta": ["/creditos"]},
            {"key": "banco_hist",   "label": "/banco_historial",                   "ruta": ["/banco_historial"]},
            {"key": "bolsa_tasas",  "label": "/bolsa_tasas",                       "ruta": ["/bolsa_tasas"]},
        ],
    },
    {
        "cat_id": "gremio",
        "nombre": "🏰 Gremio",
        "items": [
            {"key": "gremio",       "label": "/gremio",                            "ruta": ["/gremio"]},
            {"key": "gremio_niv",   "label": "/gremio_nivel",                      "ruta": ["/gremio_nivel"]},
            {"key": "gremio_sub",   "label": "/gremio_subir_nivel",                "ruta": ["/gremio_subir_nivel"]},
            {"key": "gremio_dep",   "label": "/gremio_depositar_material",         "ruta": ["/gremio_depositar_material"]},
            {"key": "gremio_bon",   "label": "/gremio_bonificaciones",             "ruta": ["/gremio_bonificaciones"]},
            {"key": "dep_baul",     "label": "/depositar_baul <id> <cant>",        "ruta": ["/depositar_baul <id> <cantidad>"]},
            {"key": "tomar_baul",   "label": "/tomar_baul <id>",                   "ruta": ["/tomar_baul <id>"]},
            {"key": "invitar_gremio","label": "/invitar_gremio @usuario",          "ruta": ["/invitar_gremio @usuario"]},
            {"key": "rango_gremio", "label": "/rango_gremio",                      "ruta": ["/rango_gremio"]},
        ],
    },
    {
        "cat_id": "gf",
        "nombre": "🌍 Guerra de Facciones",
        "items": [
            {"key": "gf_atacar",    "label": "/guerra_facciones_atacar",           "ruta": ["Guerra activa", "/guerra_facciones_atacar"]},
            {"key": "gf_defender",  "label": "/guerra_facciones_defender",         "ruta": ["Guerra activa", "/guerra_facciones_defender"]},
            {"key": "gf_estado",    "label": "/guerra_facciones_estado",           "ruta": ["/guerra_facciones_estado"]},
            {"key": "gf_ranking",   "label": "/guerra_facciones_ranking",          "ruta": ["/guerra_facciones_ranking"]},
            {"key": "saltar_gf",    "label": "/saltar_guerra",                     "ruta": ["Guerra activa", "/saltar_guerra"]},
        ],
    },
    {
        "cat_id": "gg",
        "nombre": "⚔️ Guerra de Gremios",
        "items": [
            {"key": "gg_declarar",  "label": "/guerra_gremios_declarar <gremio>", "ruta": ["/guerra_gremios_declarar <nombre>"]},
            {"key": "gg_aceptar",   "label": "/guerra_gremios_aceptar",           "ruta": ["Ser desafiado", "/guerra_gremios_aceptar"]},
            {"key": "gg_rechazar",  "label": "/guerra_gremios_rechazar",          "ruta": ["Ser desafiado", "/guerra_gremios_rechazar"]},
            {"key": "gg_duelo",     "label": "/guerra_gremios_duelo",             "ruta": ["Guerra activa", "/guerra_gremios_duelo"]},
            {"key": "gg_ranking",   "label": "/guerra_gremios_ranking",           "ruta": ["/guerra_gremios_ranking"]},
            {"key": "gg_estado",    "label": "/guerra_gremios_estado",            "ruta": ["/guerra_gremios_estado"]},
            {"key": "gg_rendirse",  "label": "/guerra_gremios_rendirse",          "ruta": ["Guerra activa", "/guerra_gremios_rendirse"]},
        ],
    },
    {
        "cat_id": "umbral",
        "nombre": "🌑 Umbral del Vacío",
        "items": [
            {"key": "umbral",       "label": "/umbral",                            "ruta": ["/umbral"]},
            {"key": "umbral_donar", "label": "/umbral_donar",                      "ruta": ["/umbral_donar"]},
            {"key": "umbral_atacar","label": "/umbral_atacar",                     "ruta": ["Combate Umbral activo", "/umbral_atacar"]},
            {"key": "corrupcion2",  "label": "/corrupcion",                        "ruta": ["/corrupcion"]},
        ],
    },
    {
        "cat_id": "economia",
        "nombre": "💰 Economía y Rankings",
        "items": [
            {"key": "banco_cmd",    "label": "/banco",                             "ruta": ["/banco"]},
            {"key": "rankings2",    "label": "/rankings",                          "ruta": ["/rankings"]},
            {"key": "membresia",    "label": "/membresia",                         "ruta": ["/membresia"]},
        ],
    },
    # ══════════════ BOTONES INLINE DEL JUEGO ══════════════
    {
        "cat_id": "btn_ciudad",
        "nombre": "🏙️ Botones — Ciudad (submenús)",
        "items": [
            {"key": "btn_menu_pri", "label": "Botón: 🏙️ Menú Principal ciudad",   "ruta": ["/ciudad → ciudad_menu_principal"]},
            {"key": "btn_svc",      "label": "Botón: 🛠️ Servicios",               "ruta": ["/ciudad → submenu_servicios"]},
            {"key": "btn_comercio", "label": "Botón: 🛒 Comercio",                "ruta": ["/ciudad → submenu_comercio"]},
            {"key": "btn_gremio_c", "label": "Botón: 🏰 Gremio",                  "ruta": ["/ciudad → submenu_gremio"]},
            {"key": "btn_combate",  "label": "Botón: ⚔️ Combate",                 "ruta": ["/ciudad → submenu_combate"]},
            {"key": "btn_mazm_c",   "label": "Botón: 🌀 Mazmorras",               "ruta": ["/ciudad → submenu_mazmorras"]},
            {"key": "btn_cont",     "label": "Botón: ⚗️ Contenido",               "ruta": ["/ciudad → submenu_contenido"]},
        ],
    },
    {
        "cat_id": "btn_gremio",
        "nombre": "🏰 Botones — Gremio",
        "items": [
            {"key": "btn_gr_inv",   "label": "Botón: Invitar a gremio",           "ruta": ["/gremio → botón Invitar"]},
            {"key": "btn_gr_sal",   "label": "Botón: Salir del gremio",           "ruta": ["/gremio → botón Salir"]},
            {"key": "btn_gr_pro",   "label": "Botón: Promover miembro",           "ruta": ["/gremio → botón Promover"]},
            {"key": "btn_gr_exp",   "label": "Botón: Expulsar miembro",           "ruta": ["/gremio → botón Expulsar"]},
            {"key": "btn_gr_baul",  "label": "Botón: Ver baúl del gremio",        "ruta": ["/gremio → botón Baúl"]},
        ],
    },
    {
        "cat_id": "btn_invent",
        "nombre": "🎒 Botones — Inventario",
        "items": [
            {"key": "btn_equipar",  "label": "Botón: Equipar objeto",             "ruta": ["/inventario → Equipar"]},
            {"key": "btn_usar",     "label": "Botón: Usar consumible",            "ruta": ["/inventario → Usar"]},
            {"key": "btn_tirar",    "label": "Botón: Tirar/desechar objeto",      "ruta": ["/inventario → Tirar"]},
            {"key": "btn_vender",   "label": "Botón: Vender objeto",              "ruta": ["/inventario → Vender"]},
            {"key": "btn_subastar", "label": "Botón: Subastar objeto",            "ruta": ["/inventario → Subastar"]},
        ],
    },
    {
        "cat_id": "btn_combate",
        "nombre": "⚔️ Botones — Combate",
        "items": [
            {"key": "btn_atacar",   "label": "Botón: Atacar en combate",          "ruta": ["Combate activo → Atacar"]},
            {"key": "btn_huir",     "label": "Botón: Huir del combate",           "ruta": ["Combate activo → Huir"]},
            {"key": "btn_habilidad","label": "Botón: Usar habilidad especial",    "ruta": ["Combate activo → Habilidad"]},
            {"key": "btn_aceptar_d","label": "Botón: Aceptar duelo PvP",          "ruta": ["Desafío recibido → Aceptar"]},
            {"key": "btn_rechaz_d", "label": "Botón: Rechazar duelo PvP",         "ruta": ["Desafío recibido → Rechazar"]},
        ],
    },
    {
        "cat_id": "btn_viaje",
        "nombre": "✈️ Botones — Viaje",
        "items": [
            {"key": "btn_conf_vj",  "label": "Botón: Confirmar destino de viaje", "ruta": ["/viajar → seleccionar zona → Confirmar"]},
            {"key": "btn_llegar",   "label": "Botón: Llegar (al finalizar viaje)", "ruta": ["Fin de viaje → Llegar"]},
            {"key": "btn_conf_vrap","label": "Botón: Confirmar vuelo rápido",      "ruta": ["/vuelo_rapido → Confirmar"]},
        ],
    },
    {
        "cat_id": "teclado_bts",
        "nombre": "⌨️ Botones del Teclado Rápido",
        "items": [
            {"key": "tbl_perfil",   "label": "Teclado → 👤 Perfil",              "ruta": ["Teclado rápido → 👤 Perfil"]},
            {"key": "tbl_inv",      "label": "Teclado → 🎒 Inventario",          "ruta": ["Teclado rápido → 🎒 Inventario"]},
            {"key": "tbl_rec",      "label": "Teclado → ⛏️ Recolectar",          "ruta": ["Teclado rápido → ⛏️ Recolectar"]},
            {"key": "tbl_inv2",     "label": "Teclado → 🔍 Investigar",          "ruta": ["Teclado rápido → 🔍 Investigar"]},
            {"key": "tbl_maz",      "label": "Teclado → 🏰 Mazmorra",            "ruta": ["Teclado rápido → 🏰 Mazmorra"]},
            {"key": "tbl_duelo",    "label": "Teclado → ⚔️ Duelo",               "ruta": ["Teclado rápido → ⚔️ Duelo"]},
            {"key": "tbl_rank",     "label": "Teclado → 🏆 Rankings",            "ruta": ["Teclado rápido → 🏆 Rankings"]},
            {"key": "tbl_umbral",   "label": "Teclado → 🌑 Umbral",              "ruta": ["Teclado rápido → 🌑 Umbral"]},
            {"key": "tbl_viaje",    "label": "Teclado → ✈️ Viajar",              "ruta": ["Teclado rápido → ✈️ Viajar"]},
            {"key": "tbl_ciudad",   "label": "Teclado → 🏙️ Ciudad",              "ruta": ["Teclado rápido → 🏙️ Ciudad"]},
        ],
    },
    # ══════════════ COMANDOS DE ADMIN ══════════════
    {
        "cat_id": "adm_paneles",
        "nombre": "🔐 Admin — Paneles",
        "items": [
            {"key": "adm_panel",    "label": "/panel_admin",                       "ruta": ["/panel_admin"]},
            {"key": "adm_debug",    "label": "/panel_debug",                       "ruta": ["/panel_debug"]},
            {"key": "adm_auto",     "label": "/panel_auto",                        "ruta": ["/panel_auto"]},
            {"key": "adm_guerras",  "label": "/panel_guerras",                     "ruta": ["/panel_guerras"]},
            {"key": "adm_viajes",   "label": "/panel_viajes",                      "ruta": ["/panel_viajes"]},
            {"key": "adm_premios",  "label": "/panel_premios",                     "ruta": ["/panel_premios"]},
            {"key": "adm_prembsk",  "label": "/premios_buscar",                    "ruta": ["/premios_buscar"]},
            {"key": "adm_eco",      "label": "/panel_economia",                    "ruta": ["/panel_economia"]},
            {"key": "adm_peaje",    "label": "/panel_peaje",                       "ruta": ["/panel_peaje"]},
            {"key": "adm_estado",   "label": "/estado_bot",                        "ruta": ["/estado_bot"]},
        ],
    },
    {
        "cat_id": "adm_eco",
        "nombre": "🪙 Admin — Economía",
        "items": [
            {"key": "adm_doro",     "label": "/dar_oro @u <cant>",                 "ruta": ["/dar_oro @usuario <cantidad>"]},
            {"key": "adm_qoro",     "label": "/quitar_oro @u <cant>",              "ruta": ["/quitar_oro @usuario <cantidad>"]},
            {"key": "adm_deter",    "label": "/dar_eternium @u <cant>",            "ruta": ["/dar_eternium @usuario <cantidad>"]},
            {"key": "adm_qeter",    "label": "/quitar_eternium @u <cant>",         "ruta": ["/quitar_eternium @usuario <cantidad>"]},
            {"key": "adm_dcred",    "label": "/dar_creditos @u <cant>",            "ruta": ["/dar_creditos @usuario <cantidad>"]},
            {"key": "adm_qcred",    "label": "/quitar_creditos @u <cant>",         "ruta": ["/quitar_creditos @usuario <cantidad>"]},
            {"key": "adm_dxp",      "label": "/dar_experiencia @u <xp>",           "ruta": ["/dar_experiencia @usuario <xp>"]},
            {"key": "adm_masivo",   "label": "/dar_masivo",                        "ruta": ["/dar_masivo"]},
        ],
    },
    {
        "cat_id": "adm_obj",
        "nombre": "🎁 Admin — Objetos y Progresión",
        "items": [
            {"key": "adm_dobj",     "label": "/dar_objeto @u <obj>",               "ruta": ["/dar_objeto @usuario <objeto>"]},
            {"key": "adm_qobj",     "label": "/quitar_objeto @u <obj>",            "ruta": ["/quitar_objeto @usuario <objeto>"]},
            {"key": "adm_dtit",     "label": "/dar_titulo @u <id>",                "ruta": ["/dar_titulo @usuario <id>"]},
            {"key": "adm_cniv",     "label": "/cambiar_nivel @u <niv>",            "ruta": ["/cambiar_nivel @usuario <nivel>"]},
            {"key": "adm_cclas",    "label": "/cambiar_clase @u <clase>",          "ruta": ["/cambiar_clase @usuario <clase>"]},
            {"key": "adm_cfac",     "label": "/cambiar_faccion @u <fac>",          "ruta": ["/cambiar_faccion @usuario <facción>"]},
            {"key": "adm_sethp",    "label": "/set_hp @u <hp>",                    "ruta": ["/set_hp @usuario <hp>"]},
            {"key": "adm_revivir",  "label": "/revivir @u",                        "ruta": ["/revivir @usuario"]},
            {"key": "adm_premio",   "label": "/premios_entregar @u <id>",          "ruta": ["/premios_entregar @usuario <id>"]},
        ],
    },
    {
        "cat_id": "adm_inspect",
        "nombre": "🔍 Admin — Inspección Jugadores",
        "items": [
            {"key": "adm_vinv",     "label": "/ver_inventario @u",                 "ruta": ["/ver_inventario @usuario"]},
            {"key": "adm_vest",     "label": "/ver_estadisticas @u",               "ruta": ["/ver_estadisticas @usuario"]},
            {"key": "adm_vperfil",  "label": "/ver_perfil_completo @u",            "ruta": ["/ver_perfil_completo @usuario"]},
            {"key": "adm_lista",    "label": "/lista_jugadores",                   "ruta": ["/lista_jugadores"]},
            {"key": "adm_rcd",      "label": "/resetear_cooldowns @u",             "ruta": ["/resetear_cooldowns @usuario"]},
            {"key": "adm_ract",     "label": "/reset_actividad @u",                "ruta": ["/reset_actividad @usuario"]},
        ],
    },
    {
        "cat_id": "adm_mod",
        "nombre": "🔨 Admin — Moderación",
        "items": [
            {"key": "adm_ban",      "label": "/banear @u",                         "ruta": ["/banear @usuario"]},
            {"key": "adm_deban",    "label": "/desbanear @u",                      "ruta": ["/desbanear @usuario"]},
            {"key": "adm_sil",      "label": "/silenciar @u",                      "ruta": ["/silenciar @usuario"]},
            {"key": "adm_desil",    "label": "/desilenciar @u",                    "ruta": ["/desilenciar @usuario"]},
            {"key": "adm_marcar",   "label": "/marcar @u",                         "ruta": ["/marcar @usuario"]},
            {"key": "adm_desmar",   "label": "/desmarcar @u",                      "ruta": ["/desmarcar @usuario"]},
        ],
    },
    {
        "cat_id": "adm_jefes",
        "nombre": "👹 Admin — Jefes Raid",
        "items": [
            {"key": "adm_jini",     "label": "/jefe_iniciar <nombre> [hp] [dif]",  "ruta": ["/jefe_iniciar <nombre> [hp] [dificultad]"]},
            {"key": "adm_jcom",     "label": "/jefe_comenzar",                     "ruta": ["/jefe_comenzar"]},
            {"key": "adm_jcan",     "label": "/jefe_cancelar",                     "ruta": ["/jefe_cancelar"]},
            {"key": "adm_jrec",     "label": "/jefe_recompensa @u <obj>",          "ruta": ["/jefe_recompensa @usuario <objeto>"]},
        ],
    },
    {
        "cat_id": "adm_guerras",
        "nombre": "⚔️ Admin — Guerras y Facciones",
        "items": [
            {"key": "adm_gfi",      "label": "/guerra_facciones_iniciar",          "ruta": ["/guerra_facciones_iniciar <f1> <f2> [horas]"]},
            {"key": "adm_gff",      "label": "/guerra_facciones_finalizar",        "ruta": ["/guerra_facciones_finalizar"]},
            {"key": "adm_ggres",    "label": "/admin_guerra_gremios_resolver",     "ruta": ["/admin_guerra_gremios_resolver"]},
            {"key": "adm_glim",     "label": "/guerra_limpiar",                    "ruta": ["/guerra_limpiar"]},
            {"key": "adm_faclib",   "label": "/faccion_libre",                     "ruta": ["/faccion_libre"]},
            {"key": "adm_facauto",  "label": "/faccion_auto",                      "ruta": ["/faccion_auto"]},
            {"key": "adm_facest",   "label": "/faccion_estado",                    "ruta": ["/faccion_estado"]},
        ],
    },
    {
        "cat_id": "adm_mundo",
        "nombre": "🌤️ Admin — Mundo y Eventos",
        "items": [
            {"key": "adm_clima",    "label": "/cambiar_clima <tipo>",              "ruta": ["/cambiar_clima <tipo>"]},
            {"key": "adm_evento",   "label": "/iniciar_evento_global",             "ruta": ["/iniciar_evento_global"]},
            {"key": "adm_rotar",    "label": "/rotar_tienda_creditos",             "ruta": ["/rotar_tienda_creditos"]},
            {"key": "adm_anular",   "label": "/anular_subasta <id>",               "ruta": ["/anular_subasta <id>"]},
        ],
    },
    {
        "cat_id": "adm_gremio",
        "nombre": "🏰 Admin — Gremios",
        "items": [
            {"key": "adm_gforzar",  "label": "/admin_gremio_forzar_nivel",         "ruta": ["/admin_gremio_forzar_nivel <gremio> <nivel>"]},
            {"key": "adm_gremios",  "label": "/panel_gremios",                     "ruta": ["/panel_gremios"]},
            {"key": "adm_gniv",     "label": "/panel_gremio_niveles",              "ruta": ["/panel_gremio_niveles"]},
        ],
    },
    {
        "cat_id": "adm_umbral",
        "nombre": "🌑 Admin — Umbral del Vacío",
        "items": [
            {"key": "adm_umbral",   "label": "/umbral_admin",                      "ruta": ["/umbral_admin"]},
            {"key": "adm_umbset",   "label": "/umbral_set",                        "ruta": ["/umbral_set"]},
            {"key": "adm_umbav",    "label": "/umbral_avanzar",                    "ruta": ["/umbral_avanzar"]},
        ],
    },
    # ══════════════ COMANDOS DE SUPERADMIN ══════════════
    {
        "cat_id": "sa_panel",
        "nombre": "👑 Superadmin — Panel y Admins",
        "items": [
            {"key": "sa_panel_cmd", "label": "/sa_panel",                          "ruta": ["/sa_panel"]},
            {"key": "sa_nums",      "label": "/sa_numeros",                        "ruta": ["/sa_numeros"]},
            {"key": "sa_balance",   "label": "/balance_global",                    "ruta": ["/balance_global"]},
            {"key": "sa_crear",     "label": "/superadmin_crear_admin",            "ruta": ["/superadmin_crear_admin @usuario"]},
            {"key": "sa_lista",     "label": "/superadmin_lista_admins",           "ruta": ["/superadmin_lista_admins"]},
            {"key": "sa_quitar",    "label": "/superadmin_quitar_admin @u",        "ruta": ["/superadmin_quitar_admin @usuario"]},
            {"key": "sa_permisos",  "label": "/superadmin_permisos_cmd",           "ruta": ["/superadmin_permisos_cmd"]},
        ],
    },
    {
        "cat_id": "sa_dios",
        "nombre": "⚡ Superadmin — Modo Dios",
        "items": [
            {"key": "sa_dios_on",   "label": "/dios_activar",                      "ruta": ["/dios_activar"]},
            {"key": "sa_dios_off",  "label": "/dios_desactivar",                   "ruta": ["/dios_desactivar"]},
            {"key": "sa_dios_max",  "label": "/dios_max_stats",                    "ruta": ["/dios_max_stats"]},
            {"key": "sa_ajuste",    "label": "/ajuste_global",                     "ruta": ["/ajuste_global"]},
            {"key": "sa_mstam",     "label": "/modificar_stamina @u <val>",        "ruta": ["/modificar_stamina @usuario <valor>"]},
            {"key": "sa_limp_pen",  "label": "/limpiar_penalizaciones @u",         "ruta": ["/limpiar_penalizaciones @usuario"]},
            {"key": "sa_limp_act",  "label": "/limpiar_actividad @u",              "ruta": ["/limpiar_actividad @usuario"]},
        ],
    },
    {
        "cat_id": "sa_broadcast",
        "nombre": "📢 Superadmin — Broadcast y Créditos",
        "items": [
            {"key": "sa_bc_todos",  "label": "/broadcast_todos <msg>",             "ruta": ["/broadcast_todos <mensaje>"]},
            {"key": "sa_bc_act",    "label": "/broadcast_activos <msg>",           "ruta": ["/broadcast_activos <mensaje>"]},
            {"key": "sa_creditar",  "label": "/admin_creditar",                    "ruta": ["/admin_creditar @usuario <cantidad>"]},
            {"key": "sa_sol_cred",  "label": "/admin_solicitudes_creditos",        "ruta": ["/admin_solicitudes_creditos"]},
            {"key": "sa_bolsa_adm", "label": "/bolsa_admin_tasa",                  "ruta": ["/bolsa_admin_tasa"]},
        ],
    },
]

# ── Mapa de ejecución directa del Lanzador ───────────────────────────────────
# (modulo, funcion) → ejecutable directamente | "ZONE:xxx" → por zona | None → necesita args

LANZADOR_MAP: dict = {
    # Perfil y Personaje
    "perfil":        ("perfil",            "cmd_perfil"),
    "inventario":    ("inventario",        "cmd_inventario"),
    "misiones":      ("misiones",          "cmd_misiones"),
    "logros":        ("logros",            "cmd_logros"),
    "mis_titulos":   ("titulos",           "cmd_mis_titulos"),
    "notifs":        ("notificaciones",    "cmd_notificaciones"),
    "mi_codigo":     ("invitaciones",      "cmd_mi_codigo"),
    "usar_codigo":   None,
    "corrupcion":    ("umbral_vacio",      "cmd_corrupcion"),
    "guia":          ("guia",              "cmd_guia"),
    "ayuda":         ("ayuda",             "cmd_info"),
    "comandos_cmd":  ("comandos",          "cmd_comandos"),
    "destrabar":     ("comandos",          "cmd_destrabar"),
    "rankings":      ("rankings",          "cmd_rankings"),
    "teclado_cmd":   ("teclado_rapido",    "cmd_teclado"),
    # Viajes y Mapa
    "viajar":        ("viajes",            "cmd_viajar"),
    "mapa":          ("mapa",              "cmd_mapa"),
    "est_viaje":     ("viajes",            "cmd_estado_viaje"),
    "canc_viaje":    ("viajes",            "cmd_cancelar_viaje"),
    "vuelo_rap":     ("viajes",            "cmd_vuelo_rapido"),
    "monturas":      ("viajes",            "cmd_mis_monturas"),
    "comprar_mont":  None,
    # Recolección
    "rec_azul":      "ZONE:rec",
    "rec_amarilla":  "ZONE:rec",
    "rec_roja":      "ZONE:rec",
    "rec_negra":     "ZONE:rec",
    # Investigación
    "inv_azul":      "ZONE:inv",
    "inv_amarilla":  "ZONE:inv",
    "inv_roja":      "ZONE:inv",
    "inv_negra":     "ZONE:inv",
    # Mazmorras
    "maz_azul":      "ZONE:maz",
    "maz_amarilla":  "ZONE:maz",
    "maz_roja":      "ZONE:maz",
    "maz_negra":     "ZONE:maz",
    "unir_maz":      None,
    "abandonar_maz": None,
    "espectar":      None,
    # Combate
    "duelo":         None,
    "desact_paz":    ("combate",           "cmd_desactivar_paz"),
    "pagar_resc":    ("combate",           "cmd_pagar_rescate"),
    "retomar_cb":    ("combate",           "cmd_retomar_combate"),
    # Jefes
    "jefe_info":     ("jefes",             "cmd_jefe_info"),
    "jefe_unirse":   ("jefes",             "cmd_jefe_unirse"),
    "jefe_atacar":   ("jefes",             "cmd_jefe_atacar"),
    # Ciudad servicios
    "ciudad_menu":   ("ciudad",            "cmd_ciudad"),
    "craftear":      ("ciudad",            "cmd_ciudad"),
    "encantar":      ("ciudad",            "cmd_ciudad"),
    "herrero":       ("ciudad",            "cmd_ciudad"),
    "taberna":       ("ciudad",            "cmd_ciudad"),
    "banco":         ("ciudad",            "cmd_ciudad"),
    "montura_svc":   ("ciudad",            "cmd_ciudad"),
    # Comercio
    "tienda":        ("tienda",            "cmd_tienda"),
    "subastas":      ("subastas",          "cmd_subastas"),
    "mercado_p2p":   ("p2p",              "cmd_mercado"),
    "bolsa":         None,
    "creditos":      None,
    "banco_hist":    ("banco",             "cmd_banco_historial"),
    "bolsa_tasas":   None,
    # Gremio
    "gremio":        ("gremios",           "cmd_gremio"),
    "gremio_niv":    ("gremios_niveles",   "cmd_gremio_nivel"),
    "gremio_sub":    ("gremios_niveles",   "cmd_gremio_subir_nivel"),
    "gremio_dep":    ("gremios_niveles",   "cmd_gremio_depositar_material"),
    "gremio_bon":    ("gremios_niveles",   "cmd_gremio_bonificaciones"),
    "dep_baul":      None,
    "tomar_baul":    None,
    "invitar_gremio": None,
    "rango_gremio":  ("gremios",           "cmd_rango_gremio"),
    # Guerra Facciones
    "gf_atacar":     ("guerra_facciones",  "cmd_guerra_facciones_atacar"),
    "gf_defender":   ("guerra_facciones",  "cmd_guerra_facciones_defender"),
    "gf_estado":     ("guerra_facciones",  "cmd_guerra_facciones_estado"),
    "gf_ranking":    ("guerra_facciones",  "cmd_guerra_facciones_ranking"),
    "saltar_gf":     ("guerra_facciones",  "cmd_saltar_guerra"),
    # Guerra Gremios
    "gg_declarar":   None,
    "gg_aceptar":    ("guerra_gremios",    "cmd_guerra_gremios_aceptar"),
    "gg_rechazar":   ("guerra_gremios",    "cmd_guerra_gremios_rechazar"),
    "gg_duelo":      ("guerra_gremios",    "cmd_guerra_gremios_duelo"),
    "gg_ranking":    ("guerra_gremios",    "cmd_guerra_gremios_ranking"),
    "gg_estado":     ("guerra_gremios",    "cmd_guerra_gremios_estado"),
    "gg_rendirse":   ("guerra_gremios",    "cmd_guerra_gremios_rendirse"),
    # Umbral
    "umbral":        ("umbral_vacio",      "cmd_umbral"),
    "umbral_donar":  ("umbral_vacio",      "cmd_umbral_donar"),
    "umbral_atacar": ("umbral_vacio",      "cmd_umbral_atacar"),
    "corrupcion2":   ("umbral_vacio",      "cmd_corrupcion"),
    # Economía
    "banco_cmd":     ("ciudad",            "cmd_ciudad"),
    "rankings2":     ("rankings",          "cmd_rankings"),
    "membresia":     None,
    # Botones inline (no ejecutables directamente — solo verificación manual)
    "btn_menu_pri":  None, "btn_svc":      None, "btn_comercio": None,
    "btn_gremio_c":  None, "btn_combate":  None, "btn_mazm_c":   None,
    "btn_cont":      None, "btn_gr_inv":   None, "btn_gr_sal":   None,
    "btn_gr_pro":    None, "btn_gr_exp":   None, "btn_gr_baul":  None,
    "btn_equipar":   None, "btn_usar":     None, "btn_tirar":    None,
    "btn_vender":    None, "btn_subastar": None, "btn_atacar":   None,
    "btn_huir":      None, "btn_habilidad":None, "btn_aceptar_d":None,
    "btn_rechaz_d":  None, "btn_conf_vj":  None, "btn_llegar":   None,
    "btn_conf_vrap": None,
    # Botones teclado rápido
    "tbl_perfil":    ("perfil",            "cmd_perfil"),
    "tbl_inv":       ("inventario",        "cmd_inventario"),
    "tbl_rec":       "ZONE:rec",
    "tbl_inv2":      "ZONE:inv",
    "tbl_maz":       "ZONE:maz",
    "tbl_duelo":     ("combate",           "cmd_duelo_menu"),
    "tbl_rank":      ("rankings",          "cmd_rankings"),
    "tbl_umbral":    ("umbral_vacio",      "cmd_umbral"),
    "tbl_viaje":     ("viajes",            "cmd_viajar"),
    "tbl_ciudad":    ("ciudad",            "cmd_ciudad"),
    # Admin — Paneles (ejecutables directamente)
    "adm_panel":     ("panel_admin",       "cmd_panel_admin"),
    "adm_debug":     ("panel_debug",       "cmd_panel_debug"),
    "adm_auto":      ("automatizaciones",  "cmd_panel_auto"),
    "adm_guerras":   None,
    "adm_viajes":    None,
    "adm_premios":   ("superadmin",        "cmd_panel_premios"),
    "adm_prembsk":   None,
    "adm_eco":       None,
    "adm_peaje":     None,
    "adm_estado":    ("superadmin",        "cmd_estado_bot"),
    # Admin — Economía (necesitan argumentos)
    "adm_doro":      None, "adm_qoro":    None, "adm_deter":    None,
    "adm_qeter":     None, "adm_dcred":   None, "adm_qcred":    None,
    "adm_dxp":       None, "adm_masivo":  None,
    # Admin — Objetos
    "adm_dobj":      None, "adm_qobj":    None, "adm_dtit":     None,
    "adm_cniv":      None, "adm_cclas":   None, "adm_cfac":     None,
    "adm_sethp":     None, "adm_revivir": None, "adm_premio":   None,
    # Admin — Inspección
    "adm_vinv":      None, "adm_vest":    None, "adm_vperfil":  None,
    "adm_lista":     ("superadmin",        "cmd_lista_jugadores"),
    "adm_rcd":       None, "adm_ract":    None,
    # Admin — Moderación
    "adm_ban":       None, "adm_deban":   None, "adm_sil":      None,
    "adm_desil":     None, "adm_marcar":  None, "adm_desmar":   None,
    # Admin — Jefes Raid
    "adm_jini":      None,
    "adm_jcom":      ("jefes",             "cmd_jefe_comenzar"),
    "adm_jcan":      ("jefes",             "cmd_jefe_cancelar"),
    "adm_jrec":      None,
    # Admin — Guerras
    "adm_gfi":       None, "adm_gff":     ("guerra_facciones", "cmd_guerra_facciones_finalizar"),
    "adm_ggres":     ("guerra_gremios",    "cmd_admin_guerra_gremios_resolver"),
    "adm_glim":      None, "adm_faclib":  None, "adm_facauto":  None,
    "adm_facest":    ("guerra_facciones",  "cmd_faccion_estado"),
    # Admin — Mundo
    "adm_clima":     None, "adm_evento":  None,
    "adm_rotar":     ("tienda",            "cmd_rotar_tienda_creditos"),
    "adm_anular":    None,
    # Admin — Gremios
    "adm_gforzar":   None, "adm_gremios": None, "adm_gniv":     None,
    # Admin — Umbral
    "adm_umbral":    ("umbral_vacio",      "cmd_umbral_admin"),
    "adm_umbset":    None, "adm_umbav":   ("umbral_vacio", "cmd_umbral_avanzar"),
    # Superadmin
    "sa_panel_cmd":  ("superadmin",        "cmd_sa_panel"),
    "sa_nums":       ("superadmin",        "cmd_sa_numeros"),
    "sa_balance":    None,
    "sa_crear":      None, "sa_lista":    ("superadmin", "cmd_superadmin_lista_admins"),
    "sa_quitar":     None, "sa_permisos": None,
    "sa_dios_on":    ("superadmin",        "cmd_dios_activar"),
    "sa_dios_off":   ("superadmin",        "cmd_dios_desactivar"),
    "sa_dios_max":   ("superadmin",        "cmd_dios_max_stats"),
    "sa_ajuste":     None, "sa_mstam":    None,
    "sa_limp_pen":   None, "sa_limp_act": None,
    "sa_bc_todos":   None, "sa_bc_act":   None,
    "sa_creditar":   None, "sa_sol_cred": None, "sa_bolsa_adm": None,
}

_LANZADOR_POR_PAGINA = 6

async def _ejecutar_lanzador(key: str, update, context):
    """Importa y llama la función asociada al key. Devuelve True si OK, False si None/error."""
    import db_helper as _dbh
    valor = LANZADOR_MAP.get(key)

    # Comando que necesita argumentos o flujo especial
    if valor is None:
        await update.effective_message.reply_text(
            "⚠️ Este comando necesita argumentos o flujo especial — pruébalo directamente en el chat."
        )
        return False

    # Dispatch por zona actual del jugador
    if isinstance(valor, str) and valor.startswith("ZONE:"):
        tipo = valor.split(":")[1]
        user_id = update.effective_user.id
        jug = _dbh.obtener_jugador(user_id)
        zona = (jug.get("zona_actual") or "") if jug else ""
        # Detectar color
        color = "azul"
        try:
            from datos_zona import ZONAS
            zi = next((z for z in ZONAS if z["nombre"] == zona), None)
            if zi:
                color = zi.get("color", "azul")
        except Exception:
            pass
        modulo_map = {
            "rec": f"recoleccion_{color}",
            "inv": f"investigacion_{color}",
            "maz": f"mazmorra_{color}",
        }
        func_map = {
            "rec": "cmd_recolectar",
            "inv": "cmd_investigar",
            "maz": "cmd_mazmorra",
        }
        modulo_nombre = modulo_map.get(tipo, "")
        func_nombre   = func_map.get(tipo, "")
        try:
            import importlib
            mod = importlib.import_module(modulo_nombre)
            fn  = getattr(mod, func_nombre)
            await fn(update, context)
            return True
        except Exception as e:
            await update.effective_message.reply_text(
                f"❌ Error al ejecutar ({modulo_nombre}.{func_nombre}): {e}"
            )
            return False

    # Ejecución directa
    modulo_nombre, func_nombre = valor
    try:
        import importlib
        mod = importlib.import_module(modulo_nombre)
        fn  = getattr(mod, func_nombre)
        await fn(update, context)
        return True
    except Exception as e:
        await update.effective_message.reply_text(
            f"❌ Error al ejecutar ({modulo_nombre}.{func_nombre}): {e}"
        )
        return False


_ITEMS_POR_PAGINA = 5

# ── Helpers ───────────────────────────────────────────────────────────────────

def _e(s) -> str:
    return _html.escape(str(s))


def _icono_estado(estado: str) -> str:
    return {"ok": "✅", "error": "❌"}.get(estado, "⬜")


def _buscar_cat(cat_id: str) -> dict | None:
    return next((c for c in CATALOGO if c["cat_id"] == cat_id), None)


def _buscar_item(cat: dict, key: str) -> dict | None:
    return next((i for i in cat["items"] if i["key"] == key), None)


# ── Constructores de teclados ─────────────────────────────────────────────────

def _teclado_main(user_id: int) -> InlineKeyboardMarkup:
    activo = _md.esta_en_debug(user_id)
    modo_btn = (
        InlineKeyboardButton("🔴 Desactivar modo debug", callback_data="dbg:toggle")
        if activo else
        InlineKeyboardButton("🟢 Activar modo debug",   callback_data="dbg:toggle")
    )
    return InlineKeyboardMarkup([
        [modo_btn],
        [InlineKeyboardButton("📋 Ver categorías de testing", callback_data="dbg:cats")],
        [InlineKeyboardButton("🚀 Lanzador de comandos",     callback_data="dbg:lcat:perfil:0")],
        [InlineKeyboardButton("🔄 Resetear todo el progreso", callback_data="dbg:resetall")],
    ])


def _teclado_lanzador_cats() -> InlineKeyboardMarkup:
    filas = []
    for cat in CATALOGO:
        filas.append([InlineKeyboardButton(
            f"🚀 {cat['nombre']}",
            callback_data=f"dbg:lcat:{cat['cat_id']}:0"
        )])
    filas.append([InlineKeyboardButton("◀️ Volver al panel", callback_data="dbg:main")])
    return InlineKeyboardMarkup(filas)


def _teclado_lanzador_cat(cat: dict, page: int) -> InlineKeyboardMarkup:
    items = cat["items"]
    total_pages = max(1, (len(items) + _LANZADOR_POR_PAGINA - 1) // _LANZADOR_POR_PAGINA)
    page = max(0, min(page, total_pages - 1))
    inicio = page * _LANZADOR_POR_PAGINA
    pagina_items = items[inicio: inicio + _LANZADOR_POR_PAGINA]
    cat_id = cat["cat_id"]

    filas = []
    for item in pagina_items:
        key  = item["key"]
        val  = LANZADOR_MAP.get(key)
        if val is None:
            icono = "⚠️"
            tip   = " (args)"
        elif isinstance(val, str) and val.startswith("ZONE:"):
            icono = "🌐"
            tip   = " (zona)"
        else:
            icono = "▶️"
            tip   = ""
        label = f"{icono} {item['label'][:38]}{tip}"
        filas.append([InlineKeyboardButton(label, callback_data=f"dbg:run:{key}")])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️", callback_data=f"dbg:lcat:{cat_id}:{page-1}"))
    nav.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data=f"dbg:lcat:{cat_id}:{page}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("▶️", callback_data=f"dbg:lcat:{cat_id}:{page+1}"))
    if nav:
        filas.append(nav)

    filas.append([
        InlineKeyboardButton("📂 Categorías",  callback_data="dbg:lcats"),
        InlineKeyboardButton("◀️ Panel",        callback_data="dbg:main"),
    ])
    return InlineKeyboardMarkup(filas)


def _teclado_cats() -> InlineKeyboardMarkup:
    estados = _md.get_todos_estados()
    filas = []
    for cat in CATALOGO:
        total  = len(cat["items"])
        ok     = sum(1 for i in cat["items"] if estados.get(i["key"]) == "ok")
        errors = sum(1 for i in cat["items"] if estados.get(i["key"]) == "error")
        prog   = f"{ok}✅" + (f" {errors}❌" if errors else "") + f"/{total}"
        label  = f"{cat['nombre']}  [{prog}]"
        filas.append([InlineKeyboardButton(label, callback_data=f"dbg:cat:{cat['cat_id']}:0")])
    filas.append([InlineKeyboardButton("◀️ Volver al panel", callback_data="dbg:main")])
    return InlineKeyboardMarkup(filas)


def _teclado_cat(cat: dict, page: int, estados: dict) -> InlineKeyboardMarkup:
    items = cat["items"]
    total_pages = max(1, (len(items) + _ITEMS_POR_PAGINA - 1) // _ITEMS_POR_PAGINA)
    page = max(0, min(page, total_pages - 1))
    inicio = page * _ITEMS_POR_PAGINA
    pagina_items = items[inicio: inicio + _ITEMS_POR_PAGINA]
    cat_id = cat["cat_id"]

    filas = []
    for item in pagina_items:
        key   = item["key"]
        est   = estados.get(key, "pendiente")
        icono = _icono_estado(est)
        label = f"{icono} {item['label'][:40]}"
        # Fila de estado + botones
        filas.append([InlineKeyboardButton(label, callback_data=f"dbg:info:{key}:{cat_id}:{page}")])
        botones_fila = []
        if est != "ok":
            botones_fila.append(InlineKeyboardButton("✅ OK",    callback_data=f"dbg:ok:{key}:{cat_id}:{page}"))
        if est != "error":
            botones_fila.append(InlineKeyboardButton("❌ Error", callback_data=f"dbg:err:{key}:{cat_id}:{page}"))
        if est != "pendiente":
            botones_fila.append(InlineKeyboardButton("↩️ Reset", callback_data=f"dbg:rst:{key}:{cat_id}:{page}"))
        if botones_fila:
            filas.append(botones_fila)

    # Navegación de página
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️ Anterior", callback_data=f"dbg:cat:{cat_id}:{page-1}"))
    nav.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data=f"dbg:cat:{cat_id}:{page}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("Siguiente ▶️", callback_data=f"dbg:cat:{cat_id}:{page+1}"))
    if nav:
        filas.append(nav)

    filas.append([
        InlineKeyboardButton("📋 Categorías",   callback_data="dbg:cats"),
        InlineKeyboardButton("◀️ Panel",         callback_data="dbg:main"),
    ])
    return InlineKeyboardMarkup(filas)


# ── Textos ─────────────────────────────────────────────────────────────────────

def _texto_main(user_id: int) -> str:
    activo = _md.esta_en_debug(user_id)
    modo_str = "✅ <b>ACTIVO</b>" if activo else "❌ <b>INACTIVO</b>"
    try:
        res = _md.get_resumen()
        stats = (
            f"✅ OK: <b>{res['ok']}</b>  |  "
            f"❌ Error: <b>{res['error']}</b>  |  "
            f"⬜ Sin probar: <b>{res['pendiente']}</b>  |  "
            f"Total: {res['total']}"
        )
    except Exception:
        stats = "—"
    return (
        "🐛 <b>PANEL DETECTOR DE BUGS</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"<b>Modo debug:</b> {modo_str}\n\n"
        "<b>¿Qué hace el modo debug?</b>\n"
        "• Viajes instantáneos y sin costo\n"
        "• Sin coste de stamina en ninguna acción\n"
        "• No bloquea aunque estés marcado o en guerra\n"
        "• Límites diarios de mazmorra desactivados\n"
        "• Actividad libre (no hay estado 'ocupado')\n\n"
        f"<b>📊 Progreso de testing:</b>\n{stats}\n\n"
        "<i>Usa las categorías para marcar cada comando como ✅ OK o ❌ Error.\n"
        "Los errores generan reportes automáticos que puedo arreglar.</i>"
    )


def _texto_cats() -> str:
    return (
        "📋 <b>CATEGORÍAS DE TESTING</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Selecciona una categoría para ver y marcar sus comandos:"
    )


def _texto_cat(cat: dict, page: int, estados: dict) -> str:
    items = cat["items"]
    total_pages = max(1, (len(items) + _ITEMS_POR_PAGINA - 1) // _ITEMS_POR_PAGINA)
    page = max(0, min(page, total_pages - 1))
    ok     = sum(1 for i in items if estados.get(i["key"]) == "ok")
    errors = sum(1 for i in items if estados.get(i["key"]) == "error")
    return (
        f"{cat['nombre']}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"✅ {ok} correctos  |  ❌ {errors} con error  |  ⬜ {len(items)-ok-errors} sin probar\n"
        f"Página {page+1}/{total_pages} — Marca cada item como ✅ OK o ❌ Error:"
    )


# ── Handlers ──────────────────────────────────────────────────────────────────

async def cmd_panel_debug(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not _sa._es_superadmin(user_id):
        await update.effective_message.reply_text("⛔ Solo el superadmin puede usar este panel.")
        return
    await update.effective_message.reply_text(
        _texto_main(user_id),
        parse_mode="HTML",
        reply_markup=_teclado_main(user_id),
    )


async def _cb_panel_debug(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id

    if not _sa._es_superadmin(user_id):
        await query.answer("⛔ Solo el superadmin.", show_alert=True)
        return

    await query.answer()
    data = query.data  # ej: "dbg:cats", "dbg:cat:perfil:0", "dbg:ok:perfil:0"

    parts = data.split(":")
    accion = parts[1] if len(parts) > 1 else ""

    # ── Panel principal ────────────────────────────────────────────────────────
    if accion == "main":
        await query.edit_message_text(
            _texto_main(user_id), parse_mode="HTML",
            reply_markup=_teclado_main(user_id),
        )

    # ── Toggle modo debug ──────────────────────────────────────────────────────
    elif accion == "toggle":
        activo = _md.toggle_debug(user_id)
        estado_str = "✅ ACTIVADO" if activo else "❌ DESACTIVADO"
        await query.answer(f"Modo debug {estado_str}", show_alert=True)
        await query.edit_message_text(
            _texto_main(user_id), parse_mode="HTML",
            reply_markup=_teclado_main(user_id),
        )

    # ── Lista de categorías ────────────────────────────────────────────────────
    elif accion == "cats":
        await query.edit_message_text(
            _texto_cats(), parse_mode="HTML",
            reply_markup=_teclado_cats(),
        )

    # ── Categoría (paginada) ───────────────────────────────────────────────────
    elif accion == "cat":
        # dbg:cat:CAT_ID:PAGE
        cat_id = parts[2] if len(parts) > 2 else ""
        page   = int(parts[3]) if len(parts) > 3 else 0
        cat = _buscar_cat(cat_id)
        if not cat:
            await query.edit_message_text("Categoría no encontrada.", reply_markup=_teclado_cats())
            return
        estados = _md.get_todos_estados()
        await query.edit_message_text(
            _texto_cat(cat, page, estados), parse_mode="HTML",
            reply_markup=_teclado_cat(cat, page, estados),
        )

    # ── Info de item (no hace nada, solo confirma con answer) ─────────────────
    elif accion == "info":
        key    = parts[2] if len(parts) > 2 else ""
        cat_id = parts[3] if len(parts) > 3 else ""
        cat    = _buscar_cat(cat_id)
        if cat:
            item = _buscar_item(cat, key)
            if item:
                ruta_str = " → ".join(item["ruta"])
                await query.answer(f"Ruta: {ruta_str[:190]}", show_alert=True)
                return
        await query.answer("Item no encontrado.", show_alert=True)

    # ── Marcar OK ─────────────────────────────────────────────────────────────
    elif accion == "ok":
        # dbg:ok:KEY:CAT_ID:PAGE
        key    = parts[2] if len(parts) > 2 else ""
        cat_id = parts[3] if len(parts) > 3 else ""
        page   = int(parts[4]) if len(parts) > 4 else 0
        _md.marcar_estado_cmd(key, "ok")
        await query.answer("✅ Marcado como correcto", show_alert=False)
        cat    = _buscar_cat(cat_id)
        if cat:
            estados = _md.get_todos_estados()
            await query.edit_message_text(
                _texto_cat(cat, page, estados), parse_mode="HTML",
                reply_markup=_teclado_cat(cat, page, estados),
            )

    # ── Marcar Error ──────────────────────────────────────────────────────────
    elif accion == "err":
        # dbg:err:KEY:CAT_ID:PAGE
        key    = parts[2] if len(parts) > 2 else ""
        cat_id = parts[3] if len(parts) > 3 else ""
        page   = int(parts[4]) if len(parts) > 4 else 0
        _md.marcar_estado_cmd(key, "error")
        cat  = _buscar_cat(cat_id)
        item = _buscar_item(cat, key) if cat else None
        if item and cat:
            _md.generar_reporte_error(
                key=key,
                label=item["label"],
                categoria=cat["nombre"],
                ruta=item["ruta"],
                user_id=user_id,
            )
            await query.answer(
                f"❌ Error marcado. Reporte generado para el agente.",
                show_alert=True,
            )
        else:
            await query.answer("❌ Marcado como error", show_alert=False)
        if cat:
            estados = _md.get_todos_estados()
            await query.edit_message_text(
                _texto_cat(cat, page, estados), parse_mode="HTML",
                reply_markup=_teclado_cat(cat, page, estados),
            )

    # ── Reset de un item ──────────────────────────────────────────────────────
    elif accion == "rst":
        # dbg:rst:KEY:CAT_ID:PAGE
        key    = parts[2] if len(parts) > 2 else ""
        cat_id = parts[3] if len(parts) > 3 else ""
        page   = int(parts[4]) if len(parts) > 4 else 0
        _md.marcar_estado_cmd(key, "pendiente")
        await query.answer("↩️ Estado reseteado", show_alert=False)
        cat = _buscar_cat(cat_id)
        if cat:
            estados = _md.get_todos_estados()
            await query.edit_message_text(
                _texto_cat(cat, page, estados), parse_mode="HTML",
                reply_markup=_teclado_cat(cat, page, estados),
            )

    # ── Resetear todo ─────────────────────────────────────────────────────────
    elif accion == "resetall":
        _md.resetear_todo()
        await query.answer("🔄 Todo el progreso reseteado.", show_alert=True)
        await query.edit_message_text(
            _texto_main(user_id), parse_mode="HTML",
            reply_markup=_teclado_main(user_id),
        )

    # ── Lanzador: lista de categorías ─────────────────────────────────────────
    elif accion == "lcats":
        await query.edit_message_text(
            "🚀 <b>LANZADOR DE COMANDOS</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "Selecciona una categoría y pulsa cualquier botón para ejecutarlo directamente.\n\n"
            "▶️ = ejecutable directo\n"
            "🌐 = usa tu zona actual\n"
            "⚠️ = necesita argumentos (pruébalo en el chat)",
            parse_mode="HTML",
            reply_markup=_teclado_lanzador_cats(),
        )

    # ── Lanzador: categoría paginada ──────────────────────────────────────────
    elif accion == "lcat":
        # dbg:lcat:CAT_ID:PAGE
        cat_id = parts[2] if len(parts) > 2 else ""
        page   = int(parts[3]) if len(parts) > 3 else 0
        cat = _buscar_cat(cat_id)
        if not cat:
            await query.answer("Categoría no encontrada.", show_alert=True)
            return
        await query.edit_message_text(
            f"🚀 <b>{_e(cat['nombre'])}</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "Pulsa un botón para ejecutar el comando ahora mismo:",
            parse_mode="HTML",
            reply_markup=_teclado_lanzador_cat(cat, page),
        )

    # ── Lanzador: ejecutar comando ────────────────────────────────────────────
    elif accion == "run":
        # dbg:run:KEY
        key = parts[2] if len(parts) > 2 else ""
        await query.answer(f"⚡ Ejecutando…", show_alert=False)
        await _ejecutar_lanzador(key, update, context)

    else:
        await query.answer("Acción desconocida.", show_alert=True)


# ── Registro de handlers ──────────────────────────────────────────────────────

def registrar_handlers(app):
    app.add_handler(CommandHandler("panel_debug", cmd_panel_debug))
    app.add_handler(CallbackQueryHandler(_cb_panel_debug, pattern=r"^dbg:"))

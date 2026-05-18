#!/usr/bin/env python3
# main.py - Lanzador principal del bot Aethelgard
# Configura sys.path, registra TODOS los handlers y arranca el bot.
# MEJORAS DE RENDIMIENTO: webhook/polling automático, anti-spam throttle,
# concurrent_updates(12), drop_pending_updates, Flask threaded, job 180s.

import os
import sys
import ast
import importlib
import logging
import time
from pathlib import Path
from collections import defaultdict
from threading import Thread
from flask import Flask

# ==================== sys.path — debe ir PRIMERO ====================
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# ==================== SERVIDOR WEB (para mantener el bot despierto) ====================
web_app = Flask('')

@web_app.route('/')
@web_app.route('/health')
def health():
    return "Bot activo"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    # threaded=True mejora la concurrencia bajo carga (MEJORA DE RENDIMIENTO)
    web_app.run(host='0.0.0.0', port=port, threaded=True)

# ==================== Configuración del log ====================
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Colores ANSI para consola
class Colors:
    RED    = '\033[91m'
    GREEN  = '\033[92m'
    YELLOW = '\033[93m'
    BLUE   = '\033[94m'
    RESET  = '\033[0m'

# ==================== ANTI-SPAM THROTTLE (MEJORA DE RENDIMIENTO) ====================
# Evita que un usuario mande spam de comandos (1 update c/1.5s por usuario)
_THROTTLE_INTERVAL = 1.5  # segundos entre actualizaciones del mismo usuario
_user_last_update: dict[int, float] = defaultdict(float)

async def throttle_middleware(update, context):
    """Middleware que rechaza updates demasiado frecuentes del mismo usuario."""
    try:
        import sqlite3
        conn = sqlite3.connect("aethelgard.db")
        c = conn.cursor()
        c.execute("SELECT valor FROM config_bot WHERE clave = 'throttle_antispam_activo'")
        row = c.fetchone()
        conn.close()
        activo = (row[0] if row else "1") == "1"
    except Exception:
        activo = True

    if not activo:
        return

    if not update or not update.effective_user:
        return

    user_id = update.effective_user.id
    ahora = time.monotonic()
    ultimo = _user_last_update[user_id]

    if ahora - ultimo < _THROTTLE_INTERVAL:
        # Demasiado rápido — ignorar silenciosamente
        if update.callback_query:
            try:
                await update.callback_query.answer("⏳ Espera un momento...", show_alert=False)
            except Exception:
                pass
        raise StopIteration  # detiene el procesamiento sin error

    _user_last_update[user_id] = ahora

# ==================== ANÁLISIS DE ARCHIVOS ====================

def get_all_py_files(root_dir):
    py_files = []
    for dirpath, _, filenames in os.walk(root_dir):
        for fname in filenames:
            if fname.endswith('.py'):
                full = os.path.join(dirpath, fname)
                if os.path.abspath(full) != os.path.abspath(__file__):
                    py_files.append(full)
    return py_files

def check_syntax(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            compile(f.read(), filepath, 'exec')
        return True, None
    except SyntaxError as e:
        return False, f"{os.path.basename(filepath)}: línea {e.lineno} — {e.msg}"

def parse_imports(filepath):
    imports = set()
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read(), filename=filepath)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split('.')[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module.split('.')[0])
    except SyntaxError:
        pass
    return imports

def inspect_project(root_dir):
    errors = []
    root_dir = os.path.abspath(root_dir)
    py_files = get_all_py_files(root_dir)
    logger.info(f"Verificando {len(py_files)} archivos .py en {root_dir}")
    for filepath in py_files:
        ok, msg = check_syntax(filepath)
        if not ok:
            errors.append(("SINTAXIS", msg))
    if errors:
        print(Colors.RED + "\n=== ERRORES DE SINTAXIS ===" + Colors.RESET)
        for etype, msg in errors:
            print(f"{Colors.YELLOW}[{etype}]{Colors.RESET} {msg}")
        return True, errors
    print(Colors.GREEN + f"\n✅ Sintaxis correcta en {len(py_files)} archivos." + Colors.RESET)
    return False, []

# ==================== JOBS PERIÓDICOS ====================

async def post_init(application):
    """Configura los trabajos periódicos del bot tras el arranque."""
    logger.info("Configurando trabajos periódicos...")

    jobs = [
        ("subastas",        "_comprobar_subastas_expiradas",  900,    10),
        ("p2p",             "_comprobar_expiracion",           3600,   30),
        ("banco",           "aplicar_interes_semanal",         604800, 60),
        ("tienda",          "generar_rotacion_creditos",       604800, 120),
        # Automatizaciones: guerra diaria + verificación diaria de jefes
        ("automatizaciones", "job_auto_guerra",                86400,  300),
        ("automatizaciones", "job_check_jefes_diario",         86400,  3600),
        # ── MEJORA RENDIMIENTO: Regen HP cada 180s (era 90s) ─────────────
        ("automatizaciones", "job_regen_hp",                   180,    180),
        # ── NUEVOS SISTEMAS ───────────────────────────────────────────────
        # Notificación de stamina llena (c/3 min)
        ("stamina_notif",   "job_stamina_notif",               180,    60),
        # Misiones diarias: limpiar expiradas (c/6h)
        ("misiones_diarias", "job_reset_misiones_diarias",     21600,  600),
    ]

    # Activar botón ☰ global
    try:
        from telegram import MenuButtonCommands
        await application.bot.set_chat_menu_button(menu_button=MenuButtonCommands())
        logger.info("Botón de menú ☰ activado globalmente.")
    except Exception as e:
        logger.warning(f"No se pudo activar botón de menú global: {e}")

    # Sincronizar lista "/" de comandos
    try:
        from zonas_comandos import sincronizar_todos_jugadores
        await sincronizar_todos_jugadores(application.bot)
        logger.info("Lista de comandos '/' sincronizada para todos los jugadores.")
    except Exception as e:
        logger.warning(f"No se pudo sincronizar comandos de zona: {e}")

    for mod_name, fn_name, interval, first in jobs:
        try:
            mod = importlib.import_module(mod_name)
            fn  = getattr(mod, fn_name, None)
            if fn is None:
                logger.warning(f"{mod_name}.{fn_name} no existe — job omitido.")
                continue
            application.job_queue.run_repeating(fn, interval=interval, first=first)
            logger.info(f"Job '{mod_name}.{fn_name}' registrado (cada {interval}s).")
        except ImportError as e:
            logger.warning(f"No se pudo importar '{mod_name}' para job: {e}")
        except Exception as e:
            logger.error(f"Error configurando job '{mod_name}.{fn_name}': {e}")

# ==================== COMANDO /backup_db (solo superadmin) ====================
from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

SUPERADMIN_ID = int(os.environ.get("SUPERADMIN_ID", 0))

async def cmd_backup_db(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != SUPERADMIN_ID:
        await update.message.reply_text("❌ No tienes permiso para usar este comando.")
        return
    db_path = "aethelgard.db"
    if not os.path.exists(db_path):
        await update.message.reply_text("❌ El archivo de la base de datos no existe.")
        return
    try:
        with open(db_path, 'rb') as f:
            await update.message.reply_document(
                document=f,
                filename="aethelgard_backup.db",
                caption="📦 Copia de seguridad de la base de datos"
            )
        logger.info(f"Backup enviado por usuario {user_id}")
    except Exception as e:
        await update.message.reply_text(f"❌ Error al enviar el backup: {e}")
        logger.error(f"Error en backup: {e}")

def registrar_handler_backup(app):
    app.add_handler(CommandHandler("backup_db", cmd_backup_db))

# ==================== REGISTRO DE HANDLERS ====================

MODULES_WITH_HANDLERS = [
    # Ciudad PRIMERO
    "ciudad",
    # Comandos base y registro de jugador
    "implementar_start",
    # Perfil e inventario
    "perfil",
    "inventario",
    # Resto de servicios de ciudad
    "crafteo",
    "banco",
    "tienda",
    "subastas",
    "p2p",
    "peaje",
    "rescate",
    # Guía contextual emergente
    "guia_contextual",
    # Guía interactiva
    "guia",
    # Misiones de inicio (tutorial)
    "misiones",
    # Bolsa de Valores
    "bolsa",
    # Viajes y exploración
    "viajes",
    "explorar",
    # Combate
    "combate",
    # Mazmorras
    "mazmorra_azul",
    "mazmorra_amarilla",
    "mazmorra_roja",
    "mazmorra_negra",
    # Recolección
    "recoleccion_azul",
    "recoleccion_amarilla",
    "recoleccion_roja",
    "recoleccion_negra",
    "recoleccion_auto",
    # Investigación
    "investigacion_azul",
    "investigacion_amarilla",
    "investigacion_roja",
    "investigacion_negra",
    # PvP y simulaciones
    "pvp_mortal",
    "simulaciones",
    # Admin y superadmin
    "superadmin",
    # Jefes Raid
    "jefes",
    # Gremios
    "gremios",
    "gremios_niveles",
    # Guerras
    "guerra_facciones",
    "guerra_gremios",
    # Automatizaciones
    "automatizaciones",
    # Logros y títulos
    "logros",
    "titulos",
    # Notificaciones
    "notificaciones",
    # Herramientas admin
    "crear_items",
    "admin_stats",
    "editor_maestro",
    "panel_admin",
    "panel_debug",
    # Sistemas de jugador
    "invitaciones",
    "mapa",
    "depositos",
    "comandos",
    "teclado_rapido",
    # Broadcast y reportes
    "broadcast",
    "reportes",
    "guardar_reporte",
    # Paneles admin adicionales
    "restricciones_combate",
    "economia_panel",
    "rankings",
    "umbral_vacio",
    "membresia",
    "cofre_personal",
    # ── NUEVOS MÓDULOS AÑADIDOS ─────────────────────────────────────────
    "login_diario",        # Login diario con racha y recompensas
    "misiones_diarias",    # Misiones que rotan cada 24h
    "gchat",               # Chat de gremio
    "zona_activa",         # Indicador de jugadores activos en zona
    "cooldown_info",       # Cooldowns visibles con tiempo restante
    # stamina_notif y resumen_sesion no tienen handlers, solo jobs/funciones
]

def start_bot():
    """Inicia el bot de Telegram."""
    from telegram.ext import ApplicationBuilder

    TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "PON_TU_TOKEN_AQUI")
    if TOKEN == "PON_TU_TOKEN_AQUI":
        logger.error("⚠️  No se ha configurado TELEGRAM_BOT_TOKEN.")
        sys.exit(1)

    # ── MEJORA: error handler mejorado con soporte para callbacks expirados ──
    async def error_handler(update, context):
        import telegram.error as _tg_err
        err = context.error

        # Ignorar errores de red / timeout esperados
        if isinstance(err, (_tg_err.BadRequest, _tg_err.Forbidden,
                            _tg_err.TimedOut, _tg_err.NetworkError,
                            _tg_err.RetryAfter)):
            logger.warning(f"[Telegram ignorado] {type(err).__name__}: {err}")
            return

        # Callback expirado (bot reiniciado, botón viejo pulsado)
        if isinstance(err, _tg_err.InvalidToken):
            return
        if "query is too old" in str(err).lower() or "callback_query" in str(err).lower():
            logger.debug(f"Callback expirado ignorado: {err}")
            if update and update.callback_query:
                try:
                    await update.callback_query.answer(
                        "⚠️ Este botón ya expiró. Usa el comando de nuevo.", show_alert=False
                    )
                except Exception:
                    pass
            return

        # Message no encontrado (fue borrado por el usuario)
        if isinstance(err, _tg_err.BadRequest) and "message to edit not found" in str(err).lower():
            return

        logger.error("Excepción en handler:", exc_info=err)
        if update and hasattr(update, 'effective_message') and update.effective_message:
            try:
                await update.effective_message.reply_text(
                    "⚠️ Ocurrió un error inesperado. Por favor vuelve a intentarlo."
                )
            except Exception:
                pass

    # ── MEJORA: determinar modo webhook o polling según entorno Render ──
    RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL", "").rstrip("/")
    USE_WEBHOOK = bool(RENDER_URL)

    # ── MEJORA: concurrent_updates(12) para mayor paralelismo ──
    builder = (
        ApplicationBuilder()
        .token(TOKEN)
        .connect_timeout(30)
        .read_timeout(30)
        .write_timeout(30)
        .concurrent_updates(12)   # MEJORA: 12 workers paralelos (era True/1)
        .post_init(post_init)
    )

    # ── MEJORA: drop_pending_updates=True para no procesar mensajes viejos ──
    application = builder.build()
    application.add_error_handler(error_handler)

    # ── MEJORA: registrar throttle middleware anti-spam ──
    try:
        import sqlite3
        conn = sqlite3.connect("aethelgard.db")
        c = conn.cursor()
        c.execute("SELECT valor FROM config_bot WHERE clave = 'throttle_antispam_activo'")
        row = c.fetchone()
        conn.close()
        if (row[0] if row else "1") == "1":
            application.add_handler(
                __import__('telegram.ext', fromlist=['TypeHandler']).TypeHandler(
                    type=object,
                    callback=throttle_middleware,
                ),
                group=-1  # Prioridad máxima (antes que todos los handlers)
            )
            logger.info("Anti-spam throttle middleware registrado.")
    except Exception as e:
        logger.warning(f"No se pudo registrar throttle: {e}")

    registered = 0
    failed = 0

    for mod_name in MODULES_WITH_HANDLERS:
        try:
            mod = importlib.import_module(mod_name)
            if hasattr(mod, 'registrar_handlers'):
                mod.registrar_handlers(application)
                logger.info(f"✅ Handlers registrados: {mod_name}")
                registered += 1
            else:
                logger.warning(f"⚠️  '{mod_name}' no tiene registrar_handlers — omitido.")
        except ImportError as e:
            logger.error(f"❌ No se pudo importar '{mod_name}': {e}")
            failed += 1
        except Exception as e:
            logger.error(f"❌ Error al registrar handlers de '{mod_name}': {e}")
            failed += 1

    logger.info(f"Registro completado: {registered} módulos OK, {failed} con error.")

    # Inicializar / migrar DB
    try:
        import db_helper as _db
        _db.init_db()
        logger.info("Base de datos inicializada correctamente.")
    except Exception as e:
        logger.warning(f"Advertencia al inicializar DB: {e}")

    # Sembrar defaults de configuración
    try:
        import config_db as _cdb
        _cdb.seed_defaults()
        logger.info("Configuración de balance inicializada desde DB.")
    except Exception as e:
        logger.warning(f"Advertencia al inicializar config_db: {e}")

    # Cargar items y overrides
    try:
        from crear_items import cargar_items_custom
        cargar_items_custom()
        logger.info("Items custom cargados correctamente.")
    except Exception as e:
        logger.warning(f"No se pudieron cargar items custom: {e}")
    try:
        from admin_stats import cargar_overrides
        cargar_overrides()
        logger.info("Overrides de stats cargados correctamente.")
    except Exception as e:
        logger.warning(f"No se pudieron cargar overrides de admin_stats: {e}")
    try:
        from editor_maestro import cargar_overrides_maestro
        cargar_overrides_maestro()
        logger.info("Overrides maestro cargados correctamente.")
    except Exception as e:
        logger.warning(f"No se pudieron cargar overrides: {e}")

    registrar_handler_backup(application)

    # Lanzar servidor web
    Thread(target=run_web_server, daemon=True).start()
    logger.info(f"Servidor web iniciado.")

    # ── MEJORA: Webhook en Render, polling local ──────────────────────────────
    if USE_WEBHOOK:
        WEBHOOK_PORT = int(os.environ.get("PORT", 8443))
        WEBHOOK_PATH = f"/webhook/{TOKEN}"
        WEBHOOK_URL  = f"{RENDER_URL}{WEBHOOK_PATH}"
        logger.info(f"Iniciando en modo WEBHOOK: {WEBHOOK_URL}")
        application.run_webhook(
            listen="0.0.0.0",
            port=WEBHOOK_PORT,
            url_path=WEBHOOK_PATH,
            webhook_url=WEBHOOK_URL,
            drop_pending_updates=True,   # MEJORA: descarta mensajes acumulados al reiniciar
        )
    else:
        logger.info("Iniciando en modo POLLING (desarrollo local).")
        application.run_polling(
            bootstrap_retries=-1,
            drop_pending_updates=True,   # MEJORA: descarta mensajes acumulados al reiniciar
        )

# ==================== MAIN ====================

if __name__ == "__main__":
    # MEJORA: variable de entorno SKIP_SYNTAX_CHECK=1 para saltar verificación en producción
    skip_check = os.environ.get("SKIP_SYNTAX_CHECK", "0") == "1"

    if not skip_check:
        has_errors, _ = inspect_project(PROJECT_ROOT)
        if has_errors:
            print(Colors.RED + "\n❌ El bot NO se iniciará. Corrige los errores de sintaxis." + Colors.RESET)
            sys.exit(1)
        print(Colors.GREEN + "\n✅ Iniciando bot..." + Colors.RESET)
    else:
        logger.info("SKIP_SYNTAX_CHECK=1 — verificación de sintaxis omitida (producción).")

    start_bot()

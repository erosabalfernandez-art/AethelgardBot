import sqlite3
import db_helper
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler

# ─── HELPERS PARA VALORES DINÁMICOS ──────────────────────────────────────────

def _leer_bolsa_tasas() -> dict:
    """Lee las tasas actuales de la Bolsa desde la BD (sin depender del módulo bolsa)."""
    try:
        conn = sqlite3.connect("aethelgard.db")
        c = conn.cursor()
        c.execute("SELECT clave, valor FROM bolsa_config")
        rows = c.fetchall()
        conn.close()
        return {k: v for k, v in rows}
    except Exception:
        return {}

def _pct(v) -> str:
    """Formatea un valor 0-1 como porcentaje entero."""
    return str(int(float(v) * 100))

def _fmt(v) -> str:
    """Formatea un número: entero si es entero, decimal si tiene decimales."""
    f = float(v)
    return str(int(f)) if f == int(f) else str(f)


# ─── TEXTOS DINÁMICOS ────────────────────────────────────────────────────────

def _texto_economia():
    try:
        import bolsa as _b
        tasas = _leer_bolsa_tasas()
        oe = int(tasas.get("tasa_oro_a_eternium",     _b._TASA_ORO_A_ETERNIUM))
        eo = int(tasas.get("tasa_eternium_a_oro",     _b._TASA_ETERNIUM_A_ORO))
        ce = int(tasas.get("tasa_credito_a_eternium", _b._TASA_CREDITO_A_ETERNIUM))
    except Exception:
        oe, eo, ce = 500, 300, 2
    try:
        import economia as _ec
        ce_banco = _fmt(_ec.CREDITO_A_ETERNIUM)
        ec_banco = _fmt(_ec.ETERNIUM_A_CREDITO)
    except Exception:
        ce_banco, ec_banco = "0.1", "3.0"
    return (
        "💱 Aethelgard tiene 3 monedas con distintos usos y formas de conseguirlas.\n\n"
        "🪙 ORO\n"
        "Moneda principal del juego. Se obtiene de:\n"
        "• ⚔️ Ganar combates PvP y mazmorras.\n"
        "• 🛒 Vender objetos en tiendas y mercado P2P.\n"
        "• 📋 Quests, eventos y recolección.\n"
        "Se usa para: tiendas de oro, crafteo, banco del gremio, rescates y peajes.\n\n"
        "💎 ETERNIUM\n"
        "Moneda premium in-game. Se obtiene de:\n"
        "• 👹 Participar en jefes raid y eventos globales.\n"
        "• ⚔️ Recompensas de guerra de facciones.\n"
        f"• 💱 Cambiar Oro en la Bolsa de Valores (tasa: {oe} oro → 1 eternium).\n"
        f"• 💳 Cambiar Créditos en la Bolsa de Valores (tasa: 1 crédito → {ce} eternium).\n"
        "Se usa para: tienda de Eternium, vuelo rápido, crear gremios, títulos.\n\n"
        "🔮 CRÉDITOS DEL VACÍO\n"
        "Moneda de élite con valor real. Solo se obtiene de 2 formas:\n"
        "1. 💵 Depositando USDT (menú Comercio → Créditos del Vacío).\n"
        "2. 🏷️ Comprando a otro jugador en Subastas.\n"
        "El bot NUNCA entrega créditos directamente. "
        "La Bolsa de Valores permite cambiar Créditos → Eternium (nunca al revés).\n"
        "Se usan para: tienda de Créditos (objetos exclusivos), comercio P2P.\n\n"
        "📊 BOLSA DE VALORES (tasas actuales)\n"
        f"• 🪙→💎 {oe} Oro = 1 Eternium\n"
        f"• 💎→🪙 1 Eternium = {eo} Oro (spread incluido)\n"
        f"• ✨→💎 1 Crédito = {ce} Eternium\n"
        "Acceso en Ciudad → Comercio → Bolsa.\n\n"
        "🏦 BANCO (tasas del banco)\n"
        f"• ✨→💎 1 Crédito = {ce_banco} Eternium\n"
        f"• 💎→✨ 1 Eternium = {ec_banco} Créditos\n"
        "Los intereses bancarios se aplican semanalmente al oro guardado."
    )


def _texto_combate():
    try:
        import combate as _c
        hpb     = getattr(_c, "HUIR_PROB_BASE", {})
        pve_az  = int(hpb.get(getattr(_c, "COMBATE_PVE_AZUL",     "pve_zona_azul"),    0.9) * 100)
        pve_am  = int(hpb.get(getattr(_c, "COMBATE_PVE_AMARILLA",  "pve_zona_amarilla"),0.7) * 100)
        pve_ro  = int(hpb.get(getattr(_c, "COMBATE_PVE_ROJA",      "pve_zona_roja"),    0.4) * 100)
        pve_ne  = int(hpb.get(getattr(_c, "COMBATE_PVE_NEGRA",     "pve_zona_negra"),   0.2) * 100)
        pen_oro = int(getattr(_c, "DERROTA_ORO_PORCENTAJE", 0.15) * 100)
        pen_hp  = int(getattr(_c, "DERROTA_HP_PORCENTAJE",  0.05) * 100)
    except Exception:
        pve_az, pve_am, pve_ro, pve_ne = 90, 70, 40, 20
        pen_oro, pen_hp = 15, 5
    try:
        import jefes as _j
        cd_jefe = _j.COOLDOWN_ATAQUE
    except Exception:
        cd_jefe = 30
    return (
        "🥊 Hay 5 modos de combate en Aethelgard:\n\n"
        "1. ⚔️ DUELO PvP\n"
        "Comando: /duelo @usuario\n"
        "Reta a cualquier jugador. El combate se resuelve automáticamente "
        "basado en stats (ataque, defensa), clase y equipamiento.\n"
        "✅ Ganar: recibes XP y parte del oro que llevaba el oponente.\n"
        "❌ Perder: quedas MARCADO. Hasta no pagar rescate (/pagar_rescate) "
        "no puedes viajar ni usar ciertas funciones.\n\n"
        "2. 🤝 DUELO AMISTOSO\n"
        "Combate sin consecuencias económicas. "
        "Solo para practicar y medir fuerzas sin riesgo.\n\n"
        "3. 👾 COMBATE PvE (monstruos)\n"
        "Aparecen al recolectar o investigar en zonas salvajes.\n"
        f"⚔️ Ataca, usa habilidades o huye.\n"
        f"🏃 Probabilidad de huir: 🟦{pve_az}% · 🟨{pve_am}% · 🟥{pve_ro}% · ⬛{pve_ne}%\n"
        "✅ Victoria: XP, oro y posibles drops.\n"
        f"💀 Derrota: pierdes el {pen_oro}% del oro que llevas encima y tu HP cae "
        f"al {pen_hp}% del máximo. Necesitas descansar o usar pociones para recuperarte.\n\n"
        "4. 👹 JEFE RAID\n"
        "Cuando las energías oscuras del mundo alcanzan su cénit, criaturas ancestrales "
        "despiertan en Aethelgard. "
        "Hasta 30 aventureros pueden unirse con /jefe_unirse "
        f"y atacar con /jefe_atacar (cooldown {cd_jefe}s). "
        "Las recompensas se distribuyen según el daño causado: "
        "XP, Oro y posibles reliquias únicas.\n\n"
        "5. 🏰 GUERRA DE GREMIOS\n"
        "Tu gremio declara guerra a otro con /guerra_gremios_declarar. "
        "Se realizan duelos 1v1 entre miembros. "
        "El gremio con más victorias gana recompensas para todos.\n\n"
        "6. 🌍 GUERRA DE FACCIONES\n"
        "Cuando la tensión territorial entre las tres facciones estalla, "
        "se declara la guerra total. El mundo entero siente el cambio. "
        "Todos los miembros de cada facción pueden atacar (/guerra_facciones_atacar) "
        "o defender (/guerra_facciones_defender). "
        "La facción ganadora recibe bonificaciones de XP y Oro durante 24h.\n\n"
        "📊 STATS DE COMBATE\n"
        "⚔️ Ataque: daño base por golpe.\n"
        "🛡️ Defensa: reducción de daño recibido.\n"
        "💨 Velocidad: determina quién golpea primero.\n"
        "❤️ Vida: HP total antes de caer derrotado.\n"
        "Estos stats mejoran con el nivel y el equipamiento."
    )


def _texto_recoleccion():
    try:
        import config_balance as _cb
        bonus_st = _cb.STAMINA_BONUS_POR_RECLUTA
        nivel_ac = _cb.INVITACION_NIVEL_REQUERIDO_BONUS
    except Exception:
        bonus_st, nivel_ac = 5, 15
    return (
        "🌿 Fuera de la ciudad, en zonas salvajes, puedes recolectar materiales "
        "e investigar el terreno para obtener ventajas.\n\n"
        "⛏️ RECOLECCIÓN\n"
        "Comando: usa el menú Ciudad → Contenido → Recolección "
        "o el comando específico de tu zona.\n"
        "Solo disponible en zonas salvajes (no en ciudades).\n\n"
        "📦 Materiales por zona:\n"
        "🟦 Azul: Madera básica, Hierro, Plantas medicinales, Piedra común.\n"
        "🟨 Amarilla: Acero templado, Hierbas raras, Cristales de cuarzo.\n"
        "🟥 Roja: Minerales de guerra, Esencias de fuego, Fragmentos mágicos.\n"
        "⬛ Negra: Mithril, Esencias del vacío, Cristales de eternium, "
        "Fragmentos de equipo legendario.\n\n"
        "⚙️ USOS DE MATERIALES\n"
        "⚒️ Crafteo: fabrica armas, armaduras y accesorios.\n"
        "🏰 Subir nivel de gremio: deposita materiales al banco del gremio.\n"
        "💱 Vender en mercado P2P: a otros jugadores que los necesiten.\n"
        "✨ Encantamiento: algunos materiales mejoran armas y armaduras.\n\n"
        "🔍 INVESTIGACIÓN\n"
        "Comando: usa el menú Ciudad → Contenido → Investigación.\n"
        "• 65% probabilidad: mini-boss con más HP, XP y oro.\n"
        "• 30% probabilidad: monstruo normal.\n"
        "• 5% probabilidad: rastro perdido, sin combate.\n\n"
        "📖 HALLAZGOS DE INVESTIGACIÓN\n"
        "🗺️ Mapas secretos con ubicaciones de tesoros ocultos.\n"
        "👾 Información sobre monstruos élite locales.\n"
        "🛣️ Rutas alternativas de viaje más rápidas.\n"
        "⭐ Bonus temporal de XP en esa zona.\n\n"
        "⚡ STAMINA\n"
        "Cada acción en zona salvaje consume stamina. "
        "La stamina se regenera automáticamente con el tiempo. "
        "Puedes ver tu stamina actual en Ciudad → Contenido → Stamina & Invitación, "
        "o con el comando /mi_codigo.\n\n"
        "💨 CÓMO AUMENTAR TU STAMINA MÁXIMA\n"
        "La única forma de subir el límite máximo es invitar amigos al juego:\n"
        "1. Usa /mi_codigo para ver tu código personal de invitación.\n"
        "2. Comparte ese código con tus amigos.\n"
        f"3. Cuando ellos usen /usar_codigo &lt;TU_CÓDIGO&gt; y lleguen al nivel {nivel_ac}, "
        f"tu stamina máxima sube +{bonus_st} por cada uno.\n"
        "Los niveles superiores del gremio también otorgan bonificaciones de stamina.\n\n"
        "Usa /mapa para ver tu posición y qué zonas están disponibles."
    )


def _texto_eventos():
    try:
        import config_balance as _cb
        dias_rotacion = _cb.TIENDA_ROTACION_CREDITOS_DIAS
    except Exception:
        dias_rotacion = 5
    return (
        "🌟 Los eventos dinámicos hacen que el mundo de Aethelgard esté siempre vivo.\n\n"
        "🌤️ SISTEMA DE CLIMA\n"
        "El clima cambia periódicamente en cada zona:\n"
        "☀️ Soleado: +10% XP, condiciones normales.\n"
        "⛈️ Tormenta: -10% velocidad de viaje, +5% daño mágico.\n"
        "🌫️ Niebla: -10% precisión, +10% evasión.\n"
        "❄️ Nieve: -15% velocidad, +5% defensa.\n"
        "🔥 Calor extremo: -10% vida, +10% daño físico.\n\n"
        "🎊 EVENTOS GLOBALES\n"
        "El mundo genera eventos dinámicos que afectan a todos los jugadores:\n"
        "⭐ Doble XP: ganas el doble de experiencia durante X horas.\n"
        "🪙 Lluvia de oro: monstruos dropean más monedas.\n"
        "👿 Invasión: una facción de monstruos ataca múltiples zonas a la vez.\n"
        "🏆 Torneo de gremios: competición clasificatoria entre todos los gremios.\n\n"
        "👹 JEFES RAID\n"
        "Antiguas entidades de poder inmenso despiertan periódicamente en las zonas "
        "más peligrosas de Aethelgard. Únete con /jefe_unirse y ataca con /jefe_atacar.\n"
        "Dificultades: Fácil / Normal / Difícil / Legendario.\n"
        "A mayor dificultad, más HP del jefe y recompensas más valiosas.\n\n"
        "🔄 ROTACIÓN DE TIENDA\n"
        f"La tienda de Créditos del Vacío rota sus items cada {dias_rotacion} días. "
        "Los items disponibles cambian, creando urgencia y economía de mercado.\n\n"
        "📖 CRÓNICAS DIARIAS\n"
        "Cada noche, los bardos y cronistas de Aethelgard envían un fragmento de lore "
        "directamente a cada aventurero: historias del Gran Oscurecimiento, secretos de "
        "las facciones, leyendas de objetos legendarios, relatos de bestias antiguas y "
        "mucho más. Estas crónicas llegan puntualmente cada noche — no las pierdas.\n\n"
        "🔔 NOTIFICACIONES\n"
        "Recibes notificación automática cuando:\n"
        "• 👹 Una bestia ancestral despierta en el mundo.\n"
        "• ⚔️ Estalla una guerra de facciones.\n"
        "• 🔔 Alguien puja en tu subasta.\n"
        "• ✈️ Tu viaje llega al destino.\n"
        "• 🏰 Tu gremio es desafiado a la guerra.\n"
        "• 📖 Llega la crónica de lore nocturna.\n"
        "Gestiona tus notificaciones con /notificaciones."
    )


def _texto_recoleccion_mecanicas():
    try:
        import recoleccion_azul as _az
        zonas_az  = list(_az.ZONAS.values())
        fallo_az  = int(zonas_az[0]["prob_fallo"]    * 100)
        enc_az    = int(zonas_az[0]["prob_monstruo"] * 100)
        exito_az  = 100 - fallo_az - enc_az
        oro_az    = f"{zonas_az[0].get('min_oro', 2)}-{zonas_az[0].get('max_oro', 7)}"
    except Exception:
        fallo_az, enc_az, exito_az, oro_az = 20, 20, 60, "2-7"
    try:
        import recoleccion_amarilla as _am
        zonas_am  = list(_am.ZONAS.values())
        fallo_am  = int(zonas_am[0]["prob_fallo"]    * 100)
        enc_am    = int(zonas_am[0]["prob_monstruo"] * 100)
        exito_am  = 100 - fallo_am - enc_am
        oro_am    = f"{zonas_am[0].get('min_oro', 5)}-{zonas_am[0].get('max_oro', 14)}"
    except Exception:
        fallo_am, enc_am, exito_am, oro_am = 25, 30, 45, "5-14"
    try:
        import recoleccion_roja as _ro
        zonas_ro  = list(_ro.ZONAS.values())
        fallo_ro  = int(zonas_ro[0]["prob_fallo"]    * 100)
        enc_ro    = int(zonas_ro[0]["prob_monstruo"] * 100)
        exito_ro  = 100 - fallo_ro - enc_ro
        oro_ro    = f"{zonas_ro[0].get('min_oro', 10)}-{zonas_ro[0].get('max_oro', 30)}"
    except Exception:
        fallo_ro, enc_ro, exito_ro, oro_ro = 35, 45, 20, "10-30"
    try:
        import recoleccion_negra as _ne
        zonas_ne  = list(_ne.ZONAS.values())
        fallo_ne  = int(zonas_ne[0]["prob_fallo"]    * 100)
        enc_ne    = int(zonas_ne[0]["prob_monstruo"] * 100)
        exito_ne  = 100 - fallo_ne - enc_ne
        oro_ne    = f"{zonas_ne[0].get('min_oro', 20)}-{zonas_ne[0].get('max_oro', 70)}"
    except Exception:
        fallo_ne, enc_ne, exito_ne, oro_ne = 50, 65, 0, "20-70"
    try:
        import config_balance as _cb
        seg = _cb.STAMINA_REGENERACION_SEGUNDOS
        regen = round(60 / seg, 2) if seg > 0 else 0.33
    except Exception:
        regen = 0.33
    exito_ne_txt = f"{exito_ne}%" if exito_ne > 0 else "rara"
    return (
        "⛏️ RECOLECCIÓN\n"
        "Acceso: Ciudad → Contenido → Recolección.\n"
        "Pulsa el botón y espera 90 segundos.\n\n"
        "Tras los 90s pueden pasar 3 cosas:\n"
        "❌ Fallo (varía por zona): no obtienes nada y ves una frase de lore.\n"
        "👾 Encuentro (varía por zona): aparece un monstruo. Se inicia combate.\n"
        "✅ Éxito: obtienes materiales y oro.\n\n"
        "📊 PROBABILIDADES POR ZONA:\n"
        f"🟦 Azul: fallo {fallo_az}%, encuentro {enc_az}%, éxito {exito_az}%. Oro: {oro_az}.\n"
        f"🟨 Amarilla: fallo {fallo_am}%, encuentro {enc_am}%, éxito {exito_am}%. Oro: {oro_am}.\n"
        f"🟥 Roja: fallo {fallo_ro}%, encuentro {enc_ro}%, éxito {exito_ro}%. Oro: {oro_ro}.\n"
        f"⬛ Negra: fallo {fallo_ne}%, encuentro {enc_ne}%, éxito {exito_ne_txt}. Oro: {oro_ne}.\n\n"
        "⚠️ Las zonas avanzadas son MUY peligrosas. "
        "Los monstruos que aparecen son mucho más fuertes que tú al entrar.\n"
        "El resultado te lista TODOS los materiales obtenidos con su cantidad "
        "directamente en el chat.\n\n"
        "🔍 INVESTIGACIÓN\n"
        "Acceso: Ciudad → Contenido → Investigación (o Explorar).\n"
        "Muestra el menú con dos acciones:\n\n"
        "👣 SEGUIR HUELLAS\n"
        "Consume stamina. Espera 90 segundos.\n"
        "🟡 65% probabilidad: mini-boss (más XP y oro).\n"
        "⚪ 30% probabilidad: monstruo normal.\n"
        "❌ 5% probabilidad: no encuentras nada.\n\n"
        "🧘 MEDITAR\n"
        "Activa la inmunidad PvP. Ver capítulo siguiente.\n\n"
        "⚡ STAMINA\n"
        "Ambas acciones consumen stamina, que se regenera automáticamente con el tiempo "
        f"({regen} por minuto). "
        "Los niveles de gremio aumentan tu stamina máxima."
    )


def _texto_importante():
    try:
        import economia as _ec
        cr_usdt   = _ec.CREDITO_A_USDT
        usdt_cr   = int(_ec.USDT_A_CREDITO)
        comision  = int(_ec.COMISION_RETIRO * 100)
        min_ret   = _ec.MINIMO_RETIRO_CREDITOS
        ce_banco  = _fmt(_ec.CREDITO_A_ETERNIUM)
    except Exception:
        cr_usdt, usdt_cr, comision, min_ret, ce_banco = 0.01, 100, 20, 100, "0.1"
    try:
        import bolsa as _b
        tasas = _leer_bolsa_tasas()
        ce_bolsa = int(tasas.get("tasa_credito_a_eternium", _b._TASA_CREDITO_A_ETERNIUM))
    except Exception:
        ce_bolsa = 2
    comision_ej_bruto = usdt_cr
    comision_ej_com   = int(comision_ej_bruto * comision / 100)
    comision_ej_neto  = comision_ej_bruto - comision_ej_com
    return (
        "⚠️ LEE ESTO CON ATENCIÓN. Esta es la información más importante del juego.\n\n"
        "💵 LOS CRÉDITOS DEL VACÍO TIENEN VALOR REAL\n"
        f"1 Crédito del Vacío = {cr_usdt} USDT ({int(cr_usdt * 100)} centavo{'s' if int(cr_usdt * 100) != 1 else ''} de dólar).\n"
        f"{usdt_cr} Créditos = 1 USDT. Puedes retirarlos a tu billetera real.\n\n"
        "🔑 CÓMO OBTENER CRÉDITOS DEL VACÍO (ÚNICA FORMA)\n"
        "1. 💵 Depositar USDT: menú Comercio → Créditos del Vacío → Depositar.\n"
        "2. 🏷️ Comprar a otro jugador vía Subastas.\n"
        "El bot NUNCA te da créditos directamente. No existe otra forma.\n\n"
        "💎 CRÉDITOS → ETERNIUM (tasas de cambio)\n"
        f"🏦 Bolsa de Valores: 1 crédito = {ce_bolsa} eternium.\n"
        f"🏛️ Banco: 1 crédito = {ce_banco} eternium.\n"
        "Esta conversión es SOLO en esa dirección (créditos → eternium).\n"
        "No puedes convertir eternium en créditos.\n\n"
        "💸 CÓMO GANAR DINERO REAL JUGANDO\n"
        "1. ⬛ Consigue items valiosos: mazmorras negras y jefes raid dropean "
        "armas, armaduras y reliquias legendarias que otros jugadores quieren.\n"
        "2. 🏷️ Publica en Subastas: ve a Ciudad → Comercio → Subastas. "
        "Pon tu item a la venta pidiendo Créditos del Vacío.\n"
        "3. ✅ Otro jugador gana la subasta pagando con sus créditos.\n"
        "4. 🔮 Esos créditos pasan a tu cuenta.\n"
        "5. 💳 Retira a USDT: menú Comercio → Créditos del Vacío → Retirar.\n\n"
        "📋 CÓMO RETIRAR USDT PASO A PASO\n"
        "1. Ve a Ciudad → Comercio → Créditos del Vacío.\n"
        "2. Pulsa Retirar USDT.\n"
        "3. Escribe cuántos créditos quieres retirar.\n"
        "4. Ingresa tu dirección de billetera BSC BEP20.\n"
        "5. Confirma. Se descuentan tus créditos de inmediato.\n"
        "6. El sistema procesa y envía el USDT a tu billetera en 24-48h.\n"
        "7. Recibes confirmación cuando el envío está completo.\n\n"
        f"💸 COMISIÓN DE RETIRO: {comision}%\n"
        f"Ejemplo: retiras {usdt_cr} créditos = 1 USDT bruto. "
        f"Comisión {comision}% = {comision_ej_com / usdt_cr:.2f} USDT. "
        f"Recibes {comision_ej_neto / usdt_cr:.2f} USDT neto.\n"
        f"Mínimo de retiro: {min_ret} créditos.\n\n"
        "📲 LA GUÍA PUEDE DESACTIVARSE\n"
        "Esta guía emergente aparece automáticamente en cada acción. "
        "Para desactivarla: /guia_off\n"
        "Para reactivarla: /guia_on"
    )


# ─── PAGINAS ─────────────────────────────────────────────────────────────────

PAGINAS = {

    "inicio": {
        "titulo": "📖 GUÍA — Bienvenida a Aethelgard",
        "texto": (
            "⚔️ Aethelgard es un RPG de texto multijugador donde luchas, comercias y "
            "construyes tu leyenda junto a cientos de jugadores reales.\n\n"
            "🧬 CLASES DISPONIBLES\n"
            "🛡️ Vanguardista: guerrero de primera línea. Máxima vida y defensa física. "
            "Domina espadas, hachas y escudos. El tanque del grupo.\n"
            "🗡️ Acechante: experto en sigilo y ataques críticos. Alta evasión. "
            "Usa dagas y arcos cortos. El asesino silencioso.\n"
            "🔮 Tejehechizos: maestro de la magia arcana. Máximo daño a distancia. "
            "Empuña bastones y tomos. Frágil pero devastador.\n"
            "🏹 Maestro de Caza: equilibrio entre distancia y trampa. "
            "Arcos largos y explosivos. Versátil y preciso.\n\n"
            "🏰 FACCIONES\n"
            "⚜️ Alianza: orden y honor, zona norte. Ciudad capital: Ciudadela Alianza.\n"
            "⚙️ Imperio: conquista y poder, zona central. Ciudad capital: Ciudadela Imperio.\n"
            "🐍 Sindicato: beneficio y astucia, zona sur. Ciudad capital: Ciudadela Sindicato.\n\n"
            "🚀 CÓMO EMPEZAR\n"
            "1. Usa /start para crear tu personaje.\n"
            "2. Elige clase y facción.\n"
            "3. Usa /ciudad para acceder a los servicios de tu capital.\n"
            "4. Explora, recolecta, pelea y crece.\n\n"
            "💡 La guía emergente te acompaña en cada paso. "
            "Puedes activarla o desactivarla con el botón de abajo."
        ),
        "anterior": None,
        "siguiente": "zonas_lore",
    },

    "zonas_lore": {
        "titulo": "🗺️ GUÍA — Zonas del Mundo",
        "texto": (
            "🌍 El mundo de Aethelgard se divide en 33 zonas repartidas entre las 3 facciones. "
            "Cada zona tiene un color que indica su nivel de peligro.\n\n"
            "🎨 COLORES Y NIVEL REQUERIDO\n"
            "🟦 Azul (nivel 1+): zonas iniciales, peligro bajo, materiales comunes.\n"
            "🟨 Amarilla (nivel 20+): peligro medio, materiales poco comunes, PvP restringido.\n"
            "🟥 Roja (nivel 45+): peligro alto, PvP permitido, materiales raros.\n"
            "⬛ Negra (nivel 70+): peligro extremo, PvP libre, materiales épicos y legendarios.\n\n"
            "📜 LORE — ALIANZA (NORTE)\n"
            "⚜️ Ciudadela Alianza (azul): Fortaleza milenaria que resistió el Gran Oscurecimiento "
            "hace 500 años. Sus muros blancos brillan con magia paladín.\n"
            "🌳 Bosques del Amanecer (azul): Bosque sagrado custodiado por elfos guardianes. "
            "Sus árboles nunca mueren, dicen que esconden un portal de luz.\n"
            "💀 Llanuras de los Caídos (amarilla): Donde la Gran Batalla de las Tres Facciones "
            "terminó en tablas. Los fantasmas de los soldados aún patrullan de noche.\n"
            "🔥 Paso del Héroe Perdido (roja): Aquí el legendario Aldric sacrificó su alma "
            "para salvar a la Alianza. El terreno está impregnado de magia oscura y luz mezcladas.\n"
            "🕳️ Abismo Eterno del Norte (negra): El límite del mapa conocido. Solo 3 jugadores "
            "han llegado al fondo y ninguno quiso hablar de lo que vio.\n\n"
            "📜 LORE — IMPERIO (CENTRO)\n"
            "⚙️ Ciudadela Imperio (azul): Capital de mármol negro construida sobre 7 "
            "civilizaciones anteriores. Cada extensión revela reliquias de eras perdidas.\n"
            "🔨 Forjas del Gran Fuego (amarilla): Donde se fabrican las mejores armas del "
            "continente. El fuego lleva ardiendo 300 años sin apagarse.\n"
            "⚔️ Campos de la Conquista (roja): Tierras que el Imperio arrancó al Sindicato "
            "hace dos generaciones. El conflicto nunca terminó del todo.\n"
            "🌀 Fosa del Vacío Imperial (negra): Experimento mágico que salió mal. "
            "Ahora es un agujero dimensional donde habitan criaturas de otro plano.\n\n"
            "📜 LORE — SINDICATO (SUR)\n"
            "🐍 Ciudadela Sindicato (azul): Ciudad subterránea iluminada por cristales de "
            "eternium. Cada trato se sella con sangre y cada secreto tiene precio.\n"
            "⚓ Puerto de la Sombra (azul): Puerto natural donde el Sindicato controla el 80% "
            "del comercio marítimo. Los contrabandistas son respetados aquí.\n"
            "💀 Mercado de los Muertos (amarilla): Se llama así porque antes era un cementerio. "
            "Ahora es el mercado negro más grande del mundo.\n"
            "🔇 Cavernas del Silencio (negra): El sanctasanctórum del Sindicato. "
            "Nadie entra sin invitación y los que entran sin ella no salen."
        ),
        "anterior": "inicio",
        "siguiente": "viajes",
    },

    "viajes": {
        "titulo": "✈️ GUÍA — Sistema de Viajes",
        "texto": (
            "🧭 Viajar entre zonas es fundamental para progresar en Aethelgard.\n\n"
            "🗺️ CÓMO VIAJAR\n"
            "Usa /viajar o el botón Viajes en Ciudad → Contenido.\n"
            "Selecciona una zona destino del menú.\n"
            "El viaje toma tiempo real basado en la distancia.\n"
            "Cuando llegues recibirás una notificación automática.\n\n"
            "🚀 MODOS DE VIAJE\n"
            "🏠 Tus zonas: zonas de tu propia facción accesibles según tu nivel.\n"
            "⚔️ Incursión enemiga: entrar a territorio enemigo desde zona roja o negra.\n"
            "⚡ Vuelo rápido: teletransportarte a cualquier ciudad por Eternium.\n\n"
            "🐴 MONTURAS\n"
            "Las monturas reducen el tiempo de viaje. "
            "Las hay de bronce (5% más rápido), plata (15%) y oro (30%).\n"
            "Compra monturas en la tienda o alquílalas con /alquilar_montura.\n\n"
            "⚠️ RESTRICCIONES\n"
            "❌ No puedes viajar si estás marcado (deuda de rescate pendiente).\n"
            "⏱️ Las zonas rojas y negras tienen cooldown de salida.\n"
            "💡 Para entrar a ciudad enemiga debes pagar un peaje o ser escoltado.\n\n"
            "📊 NIVEL Y ZONAS\n"
            "🟦 Azul: nivel 1+\n"
            "🟨 Amarilla: nivel 20+\n"
            "🟥 Roja: nivel 45+\n"
            "⬛ Negra: nivel 70+\n\n"
            "📍 USA /mapa para ver tu posición actual y las zonas adyacentes disponibles."
        ),
        "anterior": "zonas_lore",
        "siguiente": "economia",
    },

    "economia": {
        "titulo": "💸 GUÍA — Economía",
        "texto": _texto_economia,
        "anterior": "viajes",
        "siguiente": "combate",
    },

    "combate": {
        "titulo": "⚔️ GUÍA — Tipos de Combate",
        "texto": _texto_combate,
        "anterior": "economia",
        "siguiente": "mazmorras",
    },

    "mazmorras": {
        "titulo": "🏰 GUÍA — Mazmorras",
        "texto": (
            "⚔️ Las mazmorras son los dungeon PvE principales. "
            "Grupos de hasta 5 jugadores las recorren juntos.\n\n"
            "🟦 MAZMORRA AZUL (nivel 1+)\n"
            "Acceso: desde cualquier ciudad azul.\n"
            "📜 Lore: Las catacumbas bajo las ciudades ocultan siglos de historia enterrada. "
            "Los primeros aventureros las exploraron buscando tesoros de la fundación.\n"
            "👾 Enemigos: bandidos, lobos mutados, esqueletos de guardias.\n"
            "🎁 Recompensas: Oro, materiales comunes, armas y armaduras de bronce.\n\n"
            "🟨 MAZMORRA AMARILLA (nivel 20+)\n"
            "Acceso: desde zonas salvajes amarillas.\n"
            "📜 Lore: Ruinas de templos de una religión olvidada. "
            "Las estatuas de sus dioses aún se mueven por la noche.\n"
            "👾 Enemigos: golems de piedra, sacerdotes no-muertos, bestias del templo.\n"
            "🎁 Recompensas: Oro, materiales poco comunes, armas y armaduras de acero.\n\n"
            "🟥 MAZMORRA ROJA (nivel 45+)\n"
            "Acceso: desde zonas salvajes rojas.\n"
            "📜 Lore: Fortalezas de guerra abandonadas donde la magia negra se practicaba. "
            "El aire dentro quema a los débiles de voluntad.\n"
            "👾 Enemigos: demonios menores, necromantes, caballeros malditos.\n"
            "🎁 Recompensas: Oro, materiales raros, armas y armaduras épicas.\n"
            "⚠️ Advertencia: PvP entre jugadores es posible dentro.\n\n"
            "⬛ MAZMORRA NEGRA (nivel 70+)\n"
            "Acceso: desde zonas negras.\n"
            "📜 Lore: Grietas al vacío donde entraron los primeros grandes héroes. "
            "La realidad se dobla dentro. El tiempo no fluye igual.\n"
            "👾 Enemigos: entidades del vacío, antiguos horrores, guardianes legendarios.\n"
            "🎁 Recompensas: materiales legendarios, equipo único, posibles Créditos del Vacío.\n"
            "⚠️ Advertencia: dificultad extrema. PvP libre. Alta penalización si mueres.\n\n"
            "🚪 CÓMO ENTRAR\n"
            "/mazmorra para iniciar. Elige Formar grupo o Unirme a grupo. "
            "El líder del grupo inicia con /iniciar_mazmorra."
        ),
        "anterior": "combate",
        "siguiente": "monstruos",
    },

    "monstruos": {
        "titulo": "👾 GUÍA — Tipos de Monstruos",
        "texto": (
            "🔍 Los monstruos se clasifican por zona y por tipo.\n\n"
            "⚪ TIPO NORMAL\n"
            "Los más comunes. Aparecen en cualquier zona salvaje. "
            "Baja recompensa individual pero abundantes.\n"
            "🟦 Ejemplos azul: Lobo Sombrío, Goblin Rastrero, Salamandra Azul.\n"
            "🟨 Ejemplos amarilla: Golem de tierra, Acechante encapuchado, Bestia del pantano.\n"
            "🟥 Ejemplos roja: Demonio de fuego menor, Necromante ambulante, Caballero maldito.\n"
            "⬛ Ejemplos negra: Entidad del vacío, Sombra anciana, Devorador de almas.\n\n"
            "⚠️ DIFICULTAD REAL\n"
            "Los monstruos de Aethelgard son PELIGROSOS. "
            "Un monstruo de zona azul de nivel 1 tiene ya más de 120 HP y golpea fuerte.\n"
            "💡 Usa habilidades especiales y pociones para sobrevivir.\n"
            "💀 Si mueres, perderás parte del oro encima y tu HP quedará muy bajo.\n\n"
            "🟡 TIPO MINI-JEFE\n"
            "Versiones élite de los normales. Más vida, más daño, mejores recompensas. "
            "Aparecen al INVESTIGAR una zona (65% de probabilidad).\n"
            "🏆 Ejemplos: Alfa de la manada, Líder de bandidos, Archilíche menor.\n\n"
            "👑 TIPO JEFE DE MAZMORRA\n"
            "El boss final de cada mazmorra. Único por sesión. "
            "Recompensas garantizadas de calidad superior. "
            "Requiere coordinar bien el grupo de 5.\n\n"
            "☠️ TIPO JEFE RAID (PvE masivo)\n"
            "Bestias ancestrales que despiertan periódicamente en el mundo "
            "cuando las energías oscuras alcanzan su punto crítico. "
            "Hasta 30 aventureros pueden unirse con /jefe_unirse y atacar con /jefe_atacar (cooldown 30s). "
            "Vida enorme, múltiples fases. "
            "Recompensas proporcionales al daño individual.\n"
            "Dificultades: Fácil / Normal / Difícil / Legendario.\n\n"
            "🔍 CÓMO ENCONTRAR MONSTRUOS\n"
            "🟦🟨 Zona azul/amarilla: recolecta o investiga en zonas salvajes.\n"
            "🟥⬛ Zona roja/negra: mayor densidad, aparecen más rápido.\n"
            "🏰 Mazmorra: combate garantizado siguiendo la estructura de salas.\n\n"
            "📦 LOOT SYSTEM\n"
            "Cada monstruo tiene tabla de drops con probabilidades. "
            "Monstruos de zonas más avanzadas tienen items de mayor rareza. "
            "Los mini-jefes tienen probabilidad extra de drops raros. "
            "Los jefes de mazmorra siempre dropean al menos 1 item de calidad garantizada."
        ),
        "anterior": "mazmorras",
        "siguiente": "equipamiento",
    },

    "equipamiento": {
        "titulo": "🗡️ GUÍA — Armas, Armaduras y Equipo",
        "texto": (
            "🛡️ El equipamiento determina tus stats de combate. "
            "Hay 5 orígenes con distintas calidades.\n\n"
            "🛒 ORIGEN 1 — TIENDA\n"
            "Comprado en la tienda con Oro o Eternium. "
            "Calidad: común y poco común. Fácil de conseguir, bueno para empezar.\n"
            "🪙 Tienda Oro: equipo básico fiable. Precio: nivel × 300 × rareza.\n"
            "💎 Tienda Eternium: calidad media-alta. Precio: nivel × rareza × 10 (mín. 20).\n"
            "🔮 Tienda Créditos del Vacío: exclusivos, stats máximos, skins únicas.\n\n"
            "⚒️ ORIGEN 2 — CRAFTEO\n"
            "Fabricado en el menú Servicios → Craftear con materiales recolectados. "
            "Calidad según materiales usados: común, poco común, raro, épico.\n"
            "✅ Ventaja: puedes elegir el tipo exacto de stats.\n\n"
            "🔧 ORIGEN 3 — HERRERO Y ENCANTAMIENTO\n"
            "Mejora cualquier arma o armadura existente. "
            "El Herrero añade gemas y mejora stats físicos. "
            "El Encantamiento añade efectos mágicos: veneno, fuego, hielo, etc.\n\n"
            "🏰 ORIGEN 4 — DROPS DE MAZMORRA\n"
            "Obtenidos al derrotar jefes de mazmorra. "
            "Calidad: raro y épico garantizados. "
            "Items únicos con nombres propios y lore propio.\n\n"
            "👹 ORIGEN 5 — DROPS DE JEFE RAID\n"
            "Los mejores items del juego. Calidad: épica y legendaria. "
            "Solo disponibles por participar en raids con alto daño.\n\n"
            "⚔️ TIPOS DE ARMA\n"
            "🗡️ Espadas (Vanguardista): alto daño físico, velocidad media.\n"
            "🪓 Hachas (Vanguardista): máximo daño, velocidad baja.\n"
            "🔪 Dagas (Acechante): daño crítico, alta velocidad, bajo daño base.\n"
            "🏹 Arcos (Acechante/Maestro): daño a distancia, precisión.\n"
            "🪄 Bastones (Tejehechizos): poder mágico, baja defensa física.\n"
            "📖 Tomos (Tejehechizos): bonus de habilidades especiales.\n\n"
            "🛡️ TIPOS DE ARMADURA\n"
            "🔩 Placa (Vanguardista): máxima defensa, penaliza velocidad.\n"
            "🧥 Cuero (Acechante): equilibrio defensa-velocidad.\n"
            "👘 Tela (Tejehechizos): mínima defensa física, máxima resistencia mágica.\n\n"
            "Para equipar items: /inventario y selecciona el objeto."
        ),
        "anterior": "monstruos",
        "siguiente": "gremios",
    },

    "gremios": {
        "titulo": "🏰 GUÍA — Gremios y Guerras",
        "texto": (
            "🤝 Los gremios son el núcleo social del juego. "
            "Comparte recursos, lucha unido y sube de nivel colectivamente.\n\n"
            "🏗️ CREAR UN GREMIO\n"
            "Requisitos: nivel 15 (Zona Negra) y pagar Eternium.\n"
            "Este requisito existe porque fundar un gremio implica liderar guerras "
            "y gestionar recursos de alto valor. Solo jugadores veteranos pueden hacerlo.\n"
            "Acceso: Ciudad → Gremio → Crear Gremio.\n"
            "Nombre único, capacidad inicial 10 miembros.\n\n"
            "👥 RANGOS DEL GREMIO\n"
            "🔵 Recluta: acceso básico, puede depositar al banco.\n"
            "🟢 Miembro: puede retirar recursos limitados.\n"
            "🟡 Oficial: puede invitar nuevos miembros.\n"
            "🟠 Lugarteniente: puede expulsar reclutas, gestionar banco.\n"
            "🔴 Líder: control total, declara guerras.\n\n"
            "📈 NIVELES DEL GREMIO (1-10)\n"
            "Sube el nivel depositando materiales raros y Oro al banco del gremio.\n"
            "Cada nivel desbloquea mejoras permanentes:\n"
            "• Nv 1-3: +5 miembros por nivel, +2% XP, +2% Oro.\n"
            "• Nv 4-6: +8 miembros, +3% stamina de mazmorra, crafteo especial.\n"
            "• Nv 7-9: +10 miembros, bonus de guerra, acceso a materiales únicos.\n"
            "• Nv 10 (élite): capacidad máxima, todas las bonificaciones activas, "
            "emblema legendario exclusivo del gremio.\n"
            "Ver nivel y bonificaciones: /gremio_nivel · /gremio_bonificaciones\n"
            "Subir nivel: /gremio_subir_nivel\n"
            "Depositar materiales: /gremio_depositar_material\n\n"
            "🏦 BANCO DEL GREMIO\n"
            "Pool de recursos compartidos. El líder gestiona el reparto. "
            "Los intereses semanales del banco se acumulan en el pool.\n\n"
            "⚔️ GUERRA DE GREMIOS\n"
            "Cuando dos gremios rivales se disputan el control de una zona, "
            "el líder lanza el desafío formal. El rival tiene 24h para aceptar.\n"
            "Declara: /guerra_gremios_declarar &lt;nombre_gremio&gt;\n"
            "Acepta: /guerra_gremios_aceptar · Rechaza: /guerra_gremios_rechazar\n"
            "Duelos: /guerra_gremios_duelo (matchmaking automático por nivel)\n"
            "Ver estado: /guerra_gremios_estado · Ranking: /guerra_gremios_ranking\n"
            "Rendirse: /guerra_gremios_rendirse\n"
            "El gremio con más victorias en duelos 1v1 gana y recibe recompensas.\n\n"
            "🌍 GUERRA DE FACCIONES\n"
            "Cuando la tensión territorial entre facciones alcanza su punto crítico, "
            "estalla la guerra total. El mundo entero se sacude.\n"
            "Todos los miembros de cada facción son convocados al campo de batalla.\n"
            "Atacar: /guerra_facciones_atacar\n"
            "Defender: /guerra_facciones_defender\n"
            "Ver marcador: /guerra_facciones_estado\n"
            "Ranking de participantes: /guerra_facciones_ranking\n"
            "Al terminar, la facción ganadora recibe bonificaciones de XP y Oro "
            "para todos sus miembros durante 24h."
        ),
        "anterior": "equipamiento",
        "siguiente": "eventos",
    },

    "eventos": {
        "titulo": "🎉 GUÍA — Eventos del Mundo",
        "texto": _texto_eventos,
        "anterior": "gremios",
        "siguiente": "recoleccion",
    },

    "recoleccion": {
        "titulo": "⛏️ GUÍA — Recolección e Investigación",
        "texto": _texto_recoleccion,
        "anterior": "eventos",
        "siguiente": "importante",
    },

    "crafteo_recetas": {
        "titulo": "⚒️ GUÍA — Crafteo y Sistema de Recetas",
        "texto": (
            "🔨 El crafteo es la forma más poderosa de conseguir equipo en Aethelgard.\n"
            "Los objetos crafteados superan en calidad a los de tienda porque utilizan "
            "materiales obtenidos en zonas avanzadas del mundo.\n\n"
            "📋 CÓMO FUNCIONA EL CRAFTEO\n"
            "1. 🛒 Compra una Receta: Ciudad → Comercio → Tienda → Oro → Recetas.\n"
            "2. ⛏️ Consigue los materiales: recolecta en zonas salvajes.\n"
            "3. ⚒️ Craftea el objeto: Ciudad → Servicios → Craftear.\n"
            "Solo verán las recetas que hayas comprado previamente.\n\n"
            "❌ SIN RECETA NO SE PUEDE CRAFTEAR\n"
            "Si intentas craftear sin recetas, el sistema te redirige automáticamente "
            "a la tienda. No existe otra forma de obtener recetas. "
            "Cada receta queda permanentemente en tu cuenta una vez comprada.\n\n"
            "🏷️ PRECIO DE LAS RECETAS\n"
            "El precio se calcula según el nivel requerido y la rareza de materiales:\n"
            "• 🟦 Receta básica (nivel 1-10): precio bajo en Oro.\n"
            "• 🟨 Receta avanzada (nivel 11-30): precio medio.\n"
            "• 🟥 Receta épica (nivel 31-50): precio alto.\n"
            "• ⬛ Receta legendaria (nivel 51+): precio muy alto.\n\n"
            "⏱️ TIEMPO DE CRAFTEO\n"
            "🟦🟨 Objetos con materiales de zona azul/amarilla: instantáneo.\n"
            "🟥 Objetos con materiales de zona roja: 60 segundos.\n"
            "⬛ Objetos con materiales de zona negra: 180 segundos.\n\n"
            "✨ ENCANTAMIENTO Y HERRERO\n"
            "Una vez crafteado, el herrero puede mejorar tu objeto con gemas. "
            "El encantador puede añadir efectos mágicos adicionales. "
            "Ambos servicios están en Ciudad → Servicios."
        ),
        "anterior": "importante",
        "siguiente": "recoleccion_mecanicas",
    },

    "recoleccion_mecanicas": {
        "titulo": "⛏️ GUÍA — Recolección e Investigación (Mecánicas)",
        "texto": _texto_recoleccion_mecanicas,
        "anterior": "crafteo_recetas",
        "siguiente": "meditacion_inmunidad",
    },

    "lore_mundo": {
        "titulo": "📜 GUÍA — Crónicas de Aethelgard",
        "texto": (
            "📖 Aethelgard no es solo un campo de batalla. Es un mundo con milenios de historia "
            "enterrada bajo sus ruinas, sus océanos y sus abismos.\n\n"
            "🌑 EL GRAN OSCURECIMIENTO\n"
            "Hace 500 años, una entidad conocida solo como El Vacío intentó consumir el plano "
            "material. Durante 7 días el sol desapareció del cielo. Las criaturas más oscuras "
            "del mundo cruzaron desde el otro lado. Solo la unión temporal de las tres facciones "
            "— Alianza, Imperio y Sindicato — logró sellar la grieta dimensional que El Vacío "
            "había abierto bajo las Cavernas del Silencio del Sindicato.\n"
            "El precio fue devastador: un tercio de la población del continente pereció. "
            "El héroe Aldric de la Alianza sacrificó su alma para reforzar el sello. "
            "Su espíritu aún protege el Paso del Héroe Perdido.\n\n"
            "⚙️ EL ETERNIUM\n"
            "No es solo una moneda. El Eternium es energía cristalizada que emana de las "
            "cicatrices dimensionales que dejó El Gran Oscurecimiento. Los alquimistas de las "
            "tres facciones aprendieron a extraerlo y refinarlo. Quien controla el Eternium "
            "controla el poder militar y mágico del continente.\n\n"
            "🔮 LOS CRÉDITOS DEL VACÍO\n"
            "Se dice que los primeros Créditos del Vacío eran fragmentos solidificados de la "
            "energía que El Vacío dejó al retirarse. El Sindicato los encontró primero, "
            "comprendió su valor y construyó todo un sistema económico alrededor de ellos. "
            "La Alianza los llama 'moneda maldita'. El Imperio los llama 'el futuro'.\n\n"
            "🗡️ LAS TRES FACCIONES HOY\n"
            "La unión que cerró El Vacío duró exactamente 3 días tras la victoria. "
            "La guerra entre facciones es endémica, parte de la naturaleza del continente. "
            "Cada generación cree que esta vez ganará definitivamente. Ninguna ha acertado.\n\n"
            "⬛ LA ZONA NEGRA\n"
            "Las zonas negras no siempre fueron así. Eran tierras normales hasta que el sello "
            "dimensional empezó a degradarse lentamente. A medida que la magia del Vacío filtra, "
            "la realidad se distorsiona: el tiempo se dobla, los monstruos mutan, "
            "y los objetos que emergen de esas zonas tienen propiedades que ningún herrero "
            "puede explicar. Los más valientes van allí por eso exactamente.\n\n"
            "📖 CRÓNICAS NOCTURNAS\n"
            "Cada noche los bardos y cronistas del mundo envían fragmentos de esta historia "
            "directamente a los aventureros. Historias de las facciones, bestiario de criaturas "
            "únicas, leyendas de objetos, relatos de héroes caídos.\n"
            "No son simples mensajes. Son piezas de un puzzle mayor.\n"
            "Los que los coleccionan dicen que juntos revelan algo sobre El Vacío que "
            "ningún libro oficial menciona."
        ),
        "anterior": "meditacion_inmunidad",
        "siguiente": None,
    },

    "meditacion_inmunidad": {
        "titulo": "🧘 GUÍA — Inmunidad PvP y Meditación",
        "texto": (
            "🛡️ La meditación te protege de ataques PvP mortales.\n\n"
            "⚙️ CÓMO FUNCIONA\n"
            "Hay dos momentos en los que puedes meditar:\n\n"
            "1. 🚀 AL LLEGAR A UNA ZONA NUEVA\n"
            "Al viajar a cualquier zona salvaje se abre una ventana de 5 minutos "
            "durante la cual puedes pulsar Meditar. "
            "Duración de la inmunidad: 2 minutos (120 segundos). "
            "Solo puedes usarla UNA VEZ por zona de entrada.\n\n"
            "2. ✅ TRAS GANAR UN COMBATE PvE\n"
            "Al derrotar a un monstruo se abre otra ventana de 5 minutos. "
            "Duración base: 120 segundos. "
            "Cada combate PvE en esa zona le resta 15 segundos. "
            "Ejemplo: si has peleado 4 veces → 120 - 60 = 60s de inmunidad. "
            "Mínimo garantizado: 15 segundos.\n\n"
            "⏱️ COOLDOWN ENTRE ZONAS\n"
            "Tras activar la inmunidad en una zona, hay 15 segundos de espera "
            "antes de poder activarla en otra zona distinta.\n\n"
            "📍 CÓMO ACCEDER\n"
            "Ve a Ciudad → Contenido → Investigación. "
            "En el menú de la zona verás el botón Meditar.\n\n"
            "❌ DESACTIVAR MANUALMENTE\n"
            "Usa /desactivar_paz si quieres salir del estado de paz antes de que termine.\n\n"
            "📌 NOTA\n"
            "La inmunidad solo protege de PvP mortal (zonas roja y negra). "
            "No afecta al combate PvE ni a los duelos amistosos."
        ),
        "anterior": "recoleccion_mecanicas",
        "siguiente": "lore_mundo",
    },

    "importante": {
        "titulo": "🔮 IMPORTANTE — Créditos del Vacío y Dinero Real",
        "texto": _texto_importante,
        "anterior": "recoleccion",
        "siguiente": "crafteo_recetas",
    },

    # ── NUEVOS SISTEMAS ────────────────────────────────────────────────────────

    "login_diario": {
        "titulo": "🗓️ GUÍA — Login Diario y Rachas",
        "texto": (
            "🔥 El sistema de login diario premia a los aventureros constantes.\n\n"
            "📌 CÓMO FUNCIONA\n"
            "Cada día puedes reclamar tu recompensa de login con /login.\n"
            "Si lo haces días consecutivos, tu racha crece y las recompensas mejoran.\n\n"
            "🎁 RECOMPENSAS POR RACHA\n"
            "• Día 1: 50🪙 Oro\n"
            "• Día 2: 100🪙 Oro\n"
            "• Día 3: 150🪙 Oro + Poción de HP Menor\n"
            "• Día 4: 200🪙 Oro\n"
            "• Día 5: 250🪙 Oro + Poción de Stamina\n"
            "• Día 6: 300🪙 Oro\n"
            "• 🏆 Día 7: 500🪙 Oro + 5💎 Eternium + Poción de Vida Mayor\n\n"
            "♻️ CICLO CONTINUO\n"
            "Al completar el día 7, el ciclo se reinicia desde el día 1.\n"
            "Las recompensas siguen acumulándose mientras mantengas la racha.\n\n"
            "⚠️ CUIDADO\n"
            "Si un día no reclamas la recompensa, la racha vuelve a 0.\n"
            "El reset ocurre a las 00:00 UTC (horario del servidor).\n\n"
            "💡 CONSEJO\n"
            "Configura una alarma diaria para no perder tu racha.\n"
            "La racha más larga de un jugador se guarda en los rankings."
        ),
        "anterior": "lore_mundo",
        "siguiente": "misiones_diarias",
    },

    "misiones_diarias": {
        "titulo": "📋 GUÍA — Misiones Diarias Rotativas",
        "texto": (
            "📋 Las misiones diarias son tareas que se renuevan cada 24 horas.\n\n"
            "📌 CÓMO ACCEDER\n"
            "Usa el comando /misiones_hoy para ver tus tres misiones del día.\n"
            "Las misiones se asignan aleatoriamente al comienzo de cada día.\n\n"
            "🎯 TIPOS DE MISIONES DIARIAS\n"
            "• ⚔️ Combate: derrota X monstruos de cierta zona.\n"
            "• ⛏️ Recolección: recoge X materiales de cierto tipo.\n"
            "• 🏰 Mazmorra: completa X mazmorras (de cualquier nivel).\n"
            "• 👹 Jefe: participa en un raid de jefe.\n"
            "• 💱 Comercio: vende/compra X ítems en el mercado.\n\n"
            "🏆 RECOMPENSAS\n"
            "Completar las 3 misiones del día otorga:\n"
            "• Recompensa individual de cada misión (oro + XP).\n"
            "• 🌟 Bonus de completitud: extra por terminar las 3.\n\n"
            "⏰ RESET\n"
            "Las misiones se renuevan cada día a las 00:00 UTC.\n"
            "Las misiones no completadas no se acumulan.\n\n"
            "💡 CONSEJO\n"
            "Revisa las misiones al iniciar sesión para planear tu día de aventuras."
        ),
        "anterior": "login_diario",
        "siguiente": "gchat_guia",
    },

    "gchat_guia": {
        "titulo": "💬 GUÍA — Chat de Gremio",
        "texto": (
            "💬 El chat de gremio te permite comunicarte en tiempo real con tus aliados.\n\n"
            "📌 COMANDOS\n"
            "• /gchat <mensaje> — envía un mensaje a todos los miembros del gremio.\n"
            "• /gchat_log — muestra los últimos 10 mensajes del chat del gremio.\n\n"
            "📝 CÓMO ENVIAR UN MENSAJE\n"
            "Escribe /gchat seguido de tu mensaje:\n"
            "Ejemplo: /gchat ¿Alguien para el raid del jefe?\n\n"
            "Todos los miembros activos del gremio recibirán tu mensaje al instante.\n\n"
            "⚠️ NORMAS\n"
            "• No se permite spam ni insultos — los admins pueden silenciarte.\n"
            "• Los mensajes se guardan durante 48 horas en el historial.\n"
            "• Solo los miembros del gremio pueden leer y enviar mensajes.\n\n"
            "🏰 REQUIERE GREMIO\n"
            "Debes ser miembro de un gremio para usar el chat.\n"
            "Si no tienes gremio, únete con /gremio o crea uno propio.\n\n"
            "💡 USOS RECOMENDADOS\n"
            "• Coordinar ataques en guerras de gremios.\n"
            "• Organizar raid de jefes con miembros.\n"
            "• Intercambiar materiales y ayuda entre aliados."
        ),
        "anterior": "misiones_diarias",
        "siguiente": "zona_activa_guia",
    },

    "zona_activa_guia": {
        "titulo": "👥 GUÍA — Jugadores Activos en Zona",
        "texto": (
            "👥 Puedes ver quién está explorando la misma zona que tú.\n\n"
            "📌 CÓMO USARLO\n"
            "Usa /zona_jugadores para ver los jugadores activos en tu zona actual.\n"
            "Se muestran los jugadores que han interactuado en los últimos 10 minutos.\n\n"
            "📊 INFORMACIÓN MOSTRADA\n"
            "• Nombre del personaje.\n"
            "• Nivel y facción.\n"
            "• Si están marcados (objetivo PvP).\n\n"
            "⚠️ AVISO POR PvP\n"
            "En zonas roja y negra, ver jugadores rivales es una alerta de peligro.\n"
            "Pon atención a jugadores de otras facciones — pueden atacarte.\n\n"
            "🤝 ZONAS SEGURAS\n"
            "En zonas azules, ver otros jugadores es útil para coordinar:\n"
            "• Mazmorras en grupo.\n"
            "• Raids de jefes.\n"
            "• Intercambio de materiales.\n\n"
            "💡 CONSEJO\n"
            "Actívalo regularmente al llegar a zonas salvajes para saber si estás solo."
        ),
        "anterior": "gchat_guia",
        "siguiente": "cooldowns_guia",
    },

    "cooldowns_guia": {
        "titulo": "⏱️ GUÍA — Sistema de Cooldowns",
        "texto": (
            "⏱️ Los cooldowns son tiempos de espera entre acciones del juego.\n\n"
            "📌 VER TUS COOLDOWNS\n"
            "Usa /cooldowns (o /cd) para ver todos los cooldowns activos con tiempo restante exacto.\n\n"
            "⚡ STAMINA\n"
            "La stamina es el recurso de energía del personaje.\n"
            "Se consume al recolectar y explorar. Se regenera automáticamente con el tiempo.\n"
            "Al llegar a 100, recibes una notificación automática (si está activada).\n\n"
            "⛏️ RECOLECCIÓN\n"
            "Tiempo de espera entre recolecciones en una misma zona.\n"
            "Varía según el nivel de la zona (azul: 90s, negra: 90s también).\n\n"
            "✈️ VUELO RÁPIDO\n"
            "Cooldown entre teletransportes de emergencia (cuesta Eternium).\n\n"
            "🔄 ACTIVIDAD EN CURSO\n"
            "Si estás en combate, mazmorra o viaje, el panel muestra el tiempo restante.\n\n"
            "💡 ESTRATEGIA\n"
            "Mientras esperas cooldowns, aprovecha para:\n"
            "• Leer el chat del gremio (/gchat_log).\n"
            "• Revisar misiones diarias (/misiones_hoy).\n"
            "• Gestionar tu inventario (/inventario)."
        ),
        "anterior": "zona_activa_guia",
        "siguiente": "nuevos_sistemas",
    },

    "nuevos_sistemas": {
        "titulo": "🆕 GUÍA — Todos los Nuevos Sistemas",
        "texto": (
            "🆕 Resumen de todos los sistemas nuevos añadidos a Aethelgard.\n\n"
            "🗓️ LOGIN DIARIO — /login\n"
            "Reclama recompensas diarias y mantén tu racha para bonificaciones mayores.\n\n"
            "📋 MISIONES DIARIAS — /misiones_hoy\n"
            "3 misiones nuevas cada día. Completa las 3 para el bonus de completitud.\n\n"
            "💬 CHAT DE GREMIO — /gchat\n"
            "Comunícate con tu gremio en tiempo real. Ver historial: /gchat_log\n\n"
            "👥 JUGADORES EN ZONA — /zona_jugadores\n"
            "Ve quién explora tu misma zona en los últimos 10 minutos.\n\n"
            "⏱️ PANEL DE COOLDOWNS — /cooldowns\n"
            "Todos tus tiempos de espera en un solo lugar con cuenta regresiva.\n\n"
            "⚡ NOTIFICACIÓN STAMINA\n"
            "Aviso automático cuando tu stamina llega al 100%. Sin necesidad de revisar.\n\n"
            "📊 RESUMEN DE SESIÓN\n"
            "Al volver a ciudad, recibes automáticamente un resumen de tu aventura:\n"
            "monstruos derrotados, oro ganado, ítems obtenidos.\n\n"
            "🔍 COMPARACIÓN DE ÍTEMS\n"
            "Al recoger un arma/armadura, se compara automáticamente con tu equipo actual.\n\n"
            "📢 ANUNCIO GLOBAL DE JEFE\n"
            "Cuando un jefe raid es derrotado, todos los jugadores reciben la noticia.\n\n"
            "🛡️ MEJORAS DE RENDIMIENTO\n"
            "El bot ahora procesa hasta 12 conversaciones en paralelo, tiene protección\n"
            "anti-spam (1 acción cada 1.5s por jugador) y cache inteligente de datos."
        ),
        "anterior": "cooldowns_guia",
        "siguiente": None,
    },
}

# ─── TECLADOS ─────────────────────────────────────────────────────────────────

def _build_keyboard(pagina_id: str, user_id: int = 0) -> InlineKeyboardMarkup:
    pag = PAGINAS[pagina_id]
    botones = []
    nav = []
    if pag["anterior"]:
        nav.append(InlineKeyboardButton("◀️ Anterior", callback_data=f"guia_{pag['anterior']}"))
    if pag["siguiente"]:
        nav.append(InlineKeyboardButton("Siguiente ▶️", callback_data=f"guia_{pag['siguiente']}"))
    if nav:
        botones.append(nav)
    botones.append([InlineKeyboardButton("📋 Índice", callback_data="guia_indice"),
                    InlineKeyboardButton("❌ Cerrar",  callback_data="guia_cerrar")])
    try:
        import guia_contextual as _gc
        activa = _gc._guia_activa(user_id) if user_id else True
        toggle_txt = "🔕 Desactivar guía emergente" if activa else "🔔 Activar guía emergente"
    except Exception:
        toggle_txt = "🔔 Activar/Desactivar guía emergente"
    botones.append([InlineKeyboardButton(toggle_txt, callback_data="toggle_guia")])
    return InlineKeyboardMarkup(botones)


def _indice_keyboard(user_id: int = 0) -> InlineKeyboardMarkup:
    try:
        import guia_contextual as _gc
        activa = _gc._guia_activa(user_id) if user_id else True
        estado_txt = "🔕 Desactivar guía emergente" if activa else "🔔 Activar guía emergente"
    except Exception:
        estado_txt = "🔔 Activar/Desactivar guía emergente"

    return InlineKeyboardMarkup([
        [InlineKeyboardButton("1 📖 Bienvenida",              callback_data="guia_inicio")],
        [InlineKeyboardButton("2 🗺️ Zonas y Lore",            callback_data="guia_zonas_lore")],
        [InlineKeyboardButton("3 ✈️ Viajes",                   callback_data="guia_viajes")],
        [InlineKeyboardButton("4 💸 Economía",                 callback_data="guia_economia")],
        [InlineKeyboardButton("5 ⚔️ Tipos de Combate",         callback_data="guia_combate")],
        [InlineKeyboardButton("6 🏰 Mazmorras",                callback_data="guia_mazmorras")],
        [InlineKeyboardButton("7 👾 Monstruos",                callback_data="guia_monstruos")],
        [InlineKeyboardButton("8 🗡️ Equipamiento",             callback_data="guia_equipamiento")],
        [InlineKeyboardButton("9 🏰 Gremios y Guerras",        callback_data="guia_gremios")],
        [InlineKeyboardButton("10 🎉 Eventos",                 callback_data="guia_eventos")],
        [InlineKeyboardButton("11 ⛏️ Recolección",             callback_data="guia_recoleccion")],
        [InlineKeyboardButton("12 ✨ Créditos del Vacío",      callback_data="guia_importante")],
        [InlineKeyboardButton("13 ⚒️ Crafteo y Recetas",       callback_data="guia_crafteo_recetas")],
        [InlineKeyboardButton("14 📊 Mecánicas Recolección",   callback_data="guia_recoleccion_mecanicas")],
        [InlineKeyboardButton("15 🧘 Meditación e Inmunidad",  callback_data="guia_meditacion_inmunidad")],
        [InlineKeyboardButton("16 📜 Crónicas de Aethelgard",  callback_data="guia_lore_mundo")],
        # ── Nuevos capítulos ──────────────────────────────────────────────────
        [InlineKeyboardButton("17 🗓️ Login Diario y Rachas",   callback_data="guia_login_diario")],
        [InlineKeyboardButton("18 📋 Misiones Diarias",         callback_data="guia_misiones_diarias")],
        [InlineKeyboardButton("19 💬 Chat de Gremio",           callback_data="guia_gchat_guia")],
        [InlineKeyboardButton("20 👥 Jugadores en Zona",        callback_data="guia_zona_activa_guia")],
        [InlineKeyboardButton("21 ⏱️ Cooldowns",                callback_data="guia_cooldowns_guia")],
        [InlineKeyboardButton("22 🆕 Todos los Nuevos Sistemas",callback_data="guia_nuevos_sistemas")],
        [InlineKeyboardButton(estado_txt,                        callback_data="toggle_guia")],
    ])


# ─── HANDLERS ─────────────────────────────────────────────────────────────────

async def cmd_guia(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    kb = _indice_keyboard(user_id)
    await update.effective_message.reply_text(
        "📖 <b>GUÍA DE AETHELGARD</b>\n\nElige un capítulo:",
        reply_markup=kb,
        parse_mode="HTML"
    )


async def _mostrar_pagina(query, pagina_id: str, user_id: int = 0):
    if pagina_id not in PAGINAS:
        await query.edit_message_text("❌ Página no encontrada.")
        return
    pag = PAGINAS[pagina_id]
    kb  = _build_keyboard(pagina_id, user_id)
    texto_raw = pag["texto"]
    if callable(texto_raw):
        try:
            texto_raw = texto_raw()
        except Exception:
            texto_raw = "⚠️ Error al cargar esta sección. Inténtalo de nuevo."
    texto = f"<b>{pag['titulo']}</b>\n\n{texto_raw}"
    await query.edit_message_text(texto, reply_markup=kb, parse_mode="HTML")


async def cb_guia(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data  = query.data

    if data == "guia_cerrar":
        await query.answer()
        await query.delete_message()
        return

    if data == "guia_indice":
        await query.answer()
        user_id = query.from_user.id
        kb = _indice_keyboard(user_id)
        await query.edit_message_text(
            "📖 <b>GUÍA DE AETHELGARD</b>\n\nElige un capítulo:",
            reply_markup=kb,
            parse_mode="HTML"
        )
        return

    if data == "toggle_guia":
        user_id = query.from_user.id
        try:
            import guia_contextual as _gc
            activa = _gc._guia_activa(user_id)
            _gc._set_guia(user_id, not activa)
            nuevo = "ACTIVADA 🔔" if not activa else "DESACTIVADA 🔕"
            await query.answer(f"Guía emergente {nuevo}", show_alert=True)
        except Exception:
            await query.answer("Error al cambiar estado de guía.", show_alert=True)
        try:
            kb = _indice_keyboard(user_id)
            await query.edit_message_reply_markup(reply_markup=kb)
        except Exception:
            pass
        return

    if data.startswith("guia_"):
        await query.answer()
        pagina_id = data[len("guia_"):]
        user_id = query.from_user.id
        await _mostrar_pagina(query, pagina_id, user_id)


# ─── REGISTRO ─────────────────────────────────────────────────────────────────

def registrar_handlers(app):
    app.add_handler(CommandHandler("guia", cmd_guia))
    app.add_handler(CallbackQueryHandler(cb_guia, pattern=r"^guia_|^toggle_guia$"))

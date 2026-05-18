#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lore_expand.py — Expande la tabla lore_mensajes hasta cubrir 10 años (3650+).

Genera mensajes de plantilla a partir de 220 personajes únicos.
Importa también los 64 mensajes originales de lore_diario.py.

Ejecutar: python3 lore_expand.py
"""

import sqlite3
import random

DB_PATH = "aethelgard.db"

# ═══════════════════════════════════════════════════════════════════════════════
# 220 PERSONAJES — (nombre, faccion, clase, origen, era, rasgo, logro, defecto, secreto)
# ═══════════════════════════════════════════════════════════════════════════════

PERSONAJES_EXTRA = [
    # ── ALIANZA ─────────────────────────────────────────────────────────────
    ("Alder el Escudo",       "Alianza",   "Vanguardista",    "Frontera Norte",    "Clásica",  "incansable voluntad",    "protegió cien aldeas en veinte años",              "exceso de sacrificio propio",             "tiene una hija en el Imperio que no conoce"),
    ("Brina la Mensajera",    "Alianza",   "Acechante",       "Ciudad Correo",     "Reciente", "velocidad y precisión",  "nunca perdió un mensaje en doce años",             "dificultad para quedarse en un lugar",    "lleva cartas que nunca entregó"),
    ("Cael el Maestro Rúnico","Alianza",   "Tejehechizos",    "Valle Grabado",     "Antigua",  "paciencia infinita",     "descifró el idioma rúnico perdido de los Antiguos","obsesión que destruyó su vida personal",  "conoce un hechizo que no se atreve a usar"),
    ("Dara de las Mareas",    "Alianza",   "Maestra de Caza", "Bahía Esmeralda",   "Reciente", "instinto marino",        "liquidó la mayor red de piratas del sur",          "impulsividad en crisis",                  "fue pirata antes de unirse a la Alianza"),
    ("Edan el Escriptor",     "Alianza",   "Tejehechizos",    "Academia Central",  "Reciente", "mente analítica",        "escribió el primer censo mágico de Aethelgard",    "frialdad emocional",                      "falsificó datos en su estudio más famoso"),
    ("Fira la Valiente",      "Alianza",   "Vanguardista",    "Pueblo Quemado",    "Clásica",  "coraje sin límites",     "entró sola a rescatar a treinta rehenes",          "subestima el peligro propio",             "el pueblo fue quemado por la propia Alianza"),
    ("Garon el Sabio Lento",  "Alianza",   "Tejehechizos",    "Biblioteca Mayor",  "Antigua",  "precisión absoluta",     "previno tres guerras con un solo informe",         "tardanza en actuar",                      "sabe quién envenenó al tercer Gran Consejero"),
    ("Hara la Cazadora",      "Alianza",   "Maestra de Caza", "Bosques del Centro","Reciente", "paciencia de predador",  "rastreó al Asesino del Espejo durante tres años",  "incapacidad de perdonar traiciones",      "el Asesino era su hermano"),
    ("Idris el Constructor",  "Alianza",   "Vanguardista",    "Ciudad Nueva",      "Reciente", "visión a largo plazo",   "diseñó las defensas que resistieron el Gran Sitio","perfeccionismo paralizante",              "nunca terminó el proyecto que más quería"),
    ("Jael la Mediadora",     "Alianza",   "Tejehechizos",    "Tres Puentes",      "Reciente", "empatía excepcional",    "selló la Paz de los Tres Ríos entre seis clanes",  "absorbe el dolor ajeno",                  "lleva cinco años sin dormir bien"),
    ("Kira la Flecha Roja",   "Alianza",   "Acechante",       "Colinas del Este",  "Clásica",  "precisión sin igual",    "ganó el Gran Torneo de Tiro cinco veces",          "incapacidad para el trabajo en equipo",   "dejó morir a su mentor para ganar el quinto"),
    ("Lorn el Guardabosques", "Alianza",   "Maestra de Caza", "Bosque Antiguo",    "Antigua",  "conexión con la tierra", "descubrió la ruta segura hacia el norte perdido",  "aislamiento social extremo",              "habla con los árboles y ellos responden"),
    ("Mara la Tejedora Ciega","Alianza",   "Tejehechizos",    "Torre Alta",        "Clásica",  "visión sin ojos",        "desarrolló la magia táctil que cambió la academia","la ceguera que la aisló de joven",        "su ceguera no es natural, es elegida"),
    ("Nael el Diplomático",   "Alianza",   "Acechante",       "Capital Norte",     "Reciente", "persuasión sin engaño",  "evitó la Cuarta Gran Guerra en el último momento", "vulnerabilidad emocional",                "prometió cosas que no puede cumplir"),
    ("Orin el Guardián",      "Alianza",   "Vanguardista",    "Puerta del Sur",    "Clásica",  "lealtad inquebrantable", "guardó la Puerta del Sur durante cuarenta años",   "incapacidad de cuestionar órdenes",       "guarda la puerta de algo que ya no está ahí"),
    ("Pira la Alquimista",    "Alianza",   "Tejehechizos",    "Valle Azufrado",    "Reciente", "curiosidad peligrosa",   "sintetizó el primer antídoto universal parcial",   "imprudencia experimental",                "su experimento mató a su asistente"),
    ("Quen el Explorador",    "Alianza",   "Maestra de Caza", "Sin hogar fijo",    "Reciente", "adaptabilidad total",    "mapeó cien kilómetros de costa norte desconocida", "incapacidad de establecerse",             "sabe dónde está el tesoro de Valdorth"),
    ("Rael la Estratega",     "Alianza",   "Acechante",       "Academia de Guerra","Clásica",  "mente táctica brillante","ganó el Torneo de Estrategia siete años seguidos",  "frialdad con costos humanos",             "perdió un torneo que no debería haber perdido"),
    ("Sael el Herrero Mago",  "Alianza",   "Tejehechizos",    "Fragua de Cristal", "Clásica",  "fusión arte-magia",      "forjó el Escudo de la Ciudad que aún resiste",     "orgullo desmedido en su obra",            "la fórmula secreta la robó"),
    ("Tira la Cantante",      "Alianza",   "Acechante",       "Ciudad Musical",    "Reciente", "arte como arma",         "desactivó un motín con una canción",               "dependencia del reconocimiento ajeno",    "su voz tiene poder mágico que no entiende"),
    ("Uran el Silencioso",    "Alianza",   "Maestra de Caza", "Tundra del Norte",  "Antigua",  "presencia invisible",    "sobrevivió solo tres inviernos árticos",           "dificultad para comunicarse",             "vio algo en el norte que no debe decir"),
    ("Vara la Sanadora Mayor","Alianza",   "Tejehechizos",    "Aldea de Sanadores","Reciente", "compasión sin límites",  "atendió a los heridos de cuatro batallas sin bando","incapacidad de decir no",                 "tiene la cura para algo que no puede revelar"),
    ("Wren el Contador",      "Alianza",   "Acechante",       "Ciudad Mercado",    "Reciente", "memoria numérica exacta","descubrió el fraude que hundió un banco entero",   "obsesión con la precisión",               "le debe una fortuna a alguien peligroso"),
    ("Xael el Interrogador",  "Alianza",   "Acechante",       "Prisión de Piedra", "Clásica",  "lectura de personas",    "resolvió el caso imposible de las cien identidades","métodos en zona gris",                    "sabe que encarceló al hombre equivocado"),
    ("Yara la Navegante",     "Alianza",   "Maestra de Caza", "Puerto del Sur",    "Reciente", "orientación perfecta",   "nunca perdió un barco en veinte años de travesías", "terquedad ante el peligro obvio",         "el mar le habla y ella lo escucha"),
    ("Zael el Archivista",    "Alianza",   "Tejehechizos",    "Biblioteca Magna",  "Antigua",  "memoria enciclopédica",  "preservó la Biblioteca durante el Gran Incendio",  "incapacidad de destruir información dañina","guarda secretos que podrían caer mundos"),
    
    # ── MÁS ALIANZA ──────────────────────────────────────────────────────────
    ("Adrin el Veterano",     "Alianza",   "Vanguardista",    "Pueblo Frontera",   "Clásica",  "experiencia en sangre",  "sirvió en cinco guerras y sobrevivió todas",       "incapacidad de dejar el servicio activo", "nunca contó cuántos mató"),
    ("Belra la Joven Vieja",  "Alianza",   "Tejehechizos",    "Torre Gris",        "Antigua",  "sabiduría precoz",       "resolvió la crisis del Eternium a los dieciséis",  "condescendencia hacia quien no razona igual","tiene cien años pero parece veinte"),
    ("Coran el Pacifista",    "Alianza",   "Vanguardista",    "Valle en Paz",       "Reciente", "convicción de no violencia","detuvo tres conflictos sin usar armas",           "vulnerabilidad ante quien no comparte su ética","sabe pelear mejor que cualquiera en su gremio"),
    ("Deln el Rastreador",    "Alianza",   "Maestra de Caza", "Llanuras del Sur",  "Clásica",  "olfato sobrenatural",    "nunca perdió un rastro en treinta años",           "obsesión que le costó su familia",        "puede oler el miedo y lo usa en negociaciones"),
    ("Elra la Inventora",     "Alianza",   "Tejehechizos",    "Ciudad Taller",     "Reciente", "creatividad caótica",    "inventó la balística mágica de largo alcance",     "incapacidad de documentar su propio trabajo","su mejor invento lo creó mientras dormía"),
    ("Forn el Maestro Dual",  "Alianza",   "Vanguardista",    "Escuela de Armas",  "Clásica",  "ambidestreza perfecta",  "venció en duelo al campeón del Imperio",           "arrogancia en combate",                   "perdió el duelo que decidió no ganar"),
    ("Gela la Tejahierro",    "Alianza",   "Tejehechizos",    "Minas de Hierro",   "Antigua",  "magia industrial",       "automatizó la extracción de tres minas",           "deshumanización del trabajo",             "las minas le costaron la salud de cien obreros"),
    ("Helm el Juez",          "Alianza",   "Acechante",       "Ciudad Tribunal",   "Reciente", "justicia sin concesiones","reformó el sistema legal de doce ciudades",        "rigidez ante los grises morales",         "condenó a alguien que después demostró ser inocente"),
    ("Irna la Protectora",    "Alianza",   "Vanguardista",    "Aldea de la Costa", "Reciente", "instinto protector",     "dio su vida por su comunidad en el asedio costero","dificultad para aceptar protección ajena","sobrevivió porque alguien la protegió a ella"),
    ("Jorn el Maestro Agua",  "Alianza",   "Tejehechizos",    "Río Grande",        "Antigua",  "control del agua",       "construyó el sistema de irrigación que alimenta al sur","perfectismo impracticable",         "puede secar un río y teme hacerlo"),
    ("Kael la Hermana",       "Alianza",   "Acechante",       "Monasterio del Sur","Clásica",  "fe práctica",            "reconvirtió el monasterio en hospital de guerra",  "dogmatismo situacional",                  "abandonó los votos en secreto hace diez años"),
    ("Lira el Bardo Guerrero","Alianza",   "Vanguardista",    "Ciudad Canción",    "Reciente", "arte y acero",           "compuso la marcha que ganó la Batalla del Norte",  "ego artístico en momentos inconvenientes","la canción tiene poder real, no lo inventó"),
    ("Morn el Minero Mago",   "Alianza",   "Tejehechizos",    "Crystalhaven Sur",  "Clásica",  "sentido mineral",        "descubrió la veta de Eternium más pura del siglo","adicción al trabajo",                     "su veta tiene consecuencias que descubrirá tarde"),
    ("Nira la Sin Nombre",    "Alianza",   "Acechante",       "Desconocido",       "Reciente", "invisibilidad social",   "operó diez años sin que ningún archivo la registrara","incapacidad de establecer identidad real","tiene tres identidades y ya no sabe cuál es la suya"),
    ("Orel el Veterano Joven","Alianza",   "Vanguardista",    "Ciudad Frontera",   "Reciente", "madurez prematura",      "comandó su primer batallón a los veintiún años",   "carga emocional sin procesar",            "tiene pesadillas que no menciona a nadie"),
    
    # ── IMPERIO ──────────────────────────────────────────────────────────────
    ("Aldric el General",     "Imperio",   "Vanguardista",    "Capital Imperial",  "Clásica",  "disciplina militar",     "ganó diecisiete batallas consecutivas",            "incapacidad de perder con gracia",        "su única derrota la causó él mismo"),
    ("Bertha la Censora",     "Imperio",   "Acechante",       "Biblioteca Imperial","Reciente","criterio sin piedad",    "eliminó la propaganda más dañina del Imperio",     "confunde censura con mejora",             "destruyó un libro que era único en el mundo"),
    ("Castor el Ingeniero",   "Imperio",   "Tejehechizos",    "Ciudad de Máquinas","Clásica",  "pensamiento mecánico",   "construyó el puente más largo de Aethelgard",      "deshumanización de los costos",           "el puente mató a cuarenta trabajadores que nadie contó"),
    ("Dorn el Espía Mayor",   "Imperio",   "Acechante",       "Sombra de Ciudad",  "Reciente", "duplicidad natural",     "desmanteló seis redes enemigas en cinco años",     "dificultad para ser sincero en privado",  "trabaja en secreto para el Sindicato también"),
    ("Elara la Heredera",     "Imperio",   "Tejehechizos",    "Palacio Imperial",  "Reciente", "don para la política",   "reformó la administración imperial de ocho provincias","ambición sin límite moral",           "quiere el trono y ya tiene el plan"),
    ("Forn el Ejecutor",      "Imperio",   "Vanguardista",    "Fortaleza Krath",   "Clásica",  "eficiencia sin empatía", "completó trescientas misiones sin un fallo",        "incapacidad de cuestionarse",             "la misión trescientos uno no la completó y lo sabe"),
    ("Grael la Reformadora",  "Imperio",   "Tejehechizos",    "Ciudad Sur Imperial","Reciente","voluntad de cambio",    "introdujo el voto popular en cinco ciudades imperiales","ingenuidad sobre las resistencias internas","el cambio que logró fue revertido después de su muerte"),
    ("Harl el Contador",      "Imperio",   "Acechante",       "Tesorería Imperial","Reciente", "integridad numérica",    "descubrió el fraude que destruyó a tres ministros",  "terquedad ante la conveniencia política", "tiene copia del informe que el Imperio enterró"),
    ("Ivar el Mariscal",      "Imperio",   "Vanguardista",    "Academias del Norte","Clásica", "autoridad natural",      "reorganizó el ejército imperial en tres años",      "no tolera ineficiencia en otros",         "fue un estudiante mediocre que lo oculta bien"),
    ("Jana la Arquitecta",    "Imperio",   "Tejehechizos",    "Ciudad Diseño",     "Reciente", "visión espacial",        "diseñó la nueva capital que no llegó a construirse", "perfeccionismo que paraliza",             "los diseños fueron robados antes de ser rechazados"),
    ("Kern el Inquisidor",    "Imperio",   "Acechante",       "Torre de Interrogación","Clásica","extracción de verdad",  "nunca obtuvo una confesión falsa",                 "metodología que cruza líneas éticas",     "obtuvo una confesión que era verdadera y que no debía revelar"),
    ("Lera la Comandante",    "Imperio",   "Vanguardista",    "Frontera Este Imperial","Reciente","liderazgo en crisis",  "mantuvo la frontera este durante el año del caos",  "incapacidad de pedir ayuda",              "la frontera se mantuvo con un tercio de las fuerzas oficiales"),
    ("Morn el Magistrado",    "Imperio",   "Tejehechizos",    "Ciudad Tribunal Imperial","Reciente","justicia imperial",  "reformó el código penal de tres provincias",        "fe ciega en las instituciones",           "una de sus sentencias ejecutó al hombre equivocado"),
    ("Nalra la Intérprete",   "Imperio",   "Acechante",       "Academia de Lenguas","Antigua",  "maestría lingüística",   "habla once idiomas y descifró el undécimo perdido",  "uso de idiomas como poder",               "hay un idioma que entiende pero pretende no entender"),
    ("Ovar el Pionero",       "Imperio",   "Maestra de Caza", "Tierras Conquistadas","Clásica", "adaptación colonial",    "pacificó el territorio norte sin violencia",        "lealtad al Imperio por encima de todo",   "el territorio se pacificó porque cedió más de lo autorizado"),
    ("Pelra la Científica",   "Imperio",   "Tejehechizos",    "Universidad Imperial","Reciente","método científico puro","publicó el trabajo más citado del siglo",           "arrogancia intelectual",                  "el resultado fue fabricado y nadie lo verificará"),
    ("Qorin el Diplomático",  "Imperio",   "Acechante",       "Embajada Central",  "Reciente", "refinamiento calculado",  "firmó el tratado que evitó la Quinta Guerra",      "sacrificio de principios por resultados", "el tratado tiene una cláusula que aún no se ha activado"),
    ("Rael el Constructor",   "Imperio",   "Vanguardista",    "Ciudad Muro",       "Clásica",  "obra a escala monumental","construyó la muralla que lleva su nombre",          "obsesión por el legado visible",          "la muralla tiene un defecto que descubrió tarde"),
    ("Sorna la Médica",       "Imperio",   "Tejehechizos",    "Hospital Imperial", "Reciente", "medicina de precisión",   "desarrolló el protocolo quirúrgico estándar",      "dificultad con el cuidado emocional",     "perdió más pacientes de los que admite"),
    ("Torn el Traidor",       "Imperio",   "Acechante",       "Fuerte Abandonado", "Reciente", "supervivencia a cualquier costo","sobrevivió cuatro cambios de régimen",          "lealtad únicamente a sí mismo",           "sabe dónde están los archivos que cada régimen quiso destruir"),
    ("Ulren el Fanático",     "Imperio",   "Vanguardista",    "Templo Imperial",   "Clásica",  "fe imperial absoluta",    "misionero de la cultura imperial en diez territorios","incapacidad de ver perspectivas ajenas",  "hay un territorio que cambió su fe y no lo admite"),
    ("Vera la Consejera",     "Imperio",   "Tejehechizos",    "Cámara del Trono",  "Reciente", "comprensión sistémica",   "asesoró a tres emperadores diferentes sin que ninguno lo supiera","invisibilidad deliberada","tiene más poder real que cualquier noble del Imperio"),
    ("Wern el Legionario",    "Imperio",   "Vanguardista",    "Legión Tercera",    "Clásica",  "orgullo de cuerpo",       "la Legión Tercera no ha perdido una batalla en su era","dificultad con el pensamiento individual","la Legión Tercera perdió una batalla que fue borrada del registro"),
    ("Xel la Guardiana",      "Imperio",   "Maestra de Caza", "Frontera Imperial", "Reciente", "vigilancia sin descanso", "detectó la infiltración que habría costado la capital","paranoia funcional",                  "la infiltración era de alguien a quien ella formó"),
    ("Yarl el Reformador",    "Imperio",   "Tejehechizos",    "Academia Imperial", "Reciente", "visión humanista",        "introdujo la educación gratuita en tres provincias","choque constante con el establishment",   "fue expulsado de la Academia que reformó"),
    ("Zorn el Último",        "Imperio",   "Vanguardista",    "Fortaleza Caída",   "Clásica",  "resistencia ante lo inevitable","fue el último defensor de la Fortaleza Caída",    "incapacidad de retirarse a tiempo",       "la fortaleza cayó por una orden que él mismo dio"),
    
    # ── SINDICATO ────────────────────────────────────────────────────────────
    ("Aran el Negociador",    "Sindicato", "Acechante",       "Tres Puertos",      "Reciente", "equilibrio perfecto",    "negoció el contrato más complejo del siglo sin ceder nada","dureza que parece crueldad",           "perdona deudas en secreto cuando nadie mira"),
    ("Brith la Falsificadora","Sindicato", "Tejehechizos",    "Distrito de Arte",  "Reciente", "perfección técnica",      "sus falsificaciones nunca fueron detectadas en vida","pérdida de identidad artística propia",   "tiene una obra propia que esconde por miedo a que no valga"),
    ("Calin el Tesorero",     "Sindicato", "Acechante",       "Bóveda del Norte",  "Antigua",  "intuición financiera",    "predijo tres crisis económicas antes de que ocurrieran","avaricia controlada pero real",        "tiene una cuenta que no existe en ningún registro"),
    ("Dren el Contacto",      "Sindicato", "Acechante",       "Ciudad Media",      "Reciente", "conexiones infinitas",    "conoce a alguien útil en cada ciudad de Aethelgard","vulnerabilidad a la manipulación social",  "sus conexiones saben más de él que él de ellas"),
    ("Elsa la Cartógrafa",    "Sindicato", "Maestra de Caza", "Sin hogar",         "Reciente", "precisión espacial",      "el mapa que trazó vendió en seis facciones distintas","mercantilización de todo",             "hay un mapa que trazó y que nunca vendió"),
    ("Farth el Confidente",   "Sindicato", "Acechante",       "Posada de Los Siete","Reciente","escuchar sin juzgar",    "nunca reveló un secreto compartido en confianza",  "carga con secretos que lo están destruyendo","sabe quién ordenó el atentado al Consejo y calló"),
    ("Gira la Prestamista",   "Sindicato", "Tejehechizos",    "Ciudad Deuda",      "Antigua",  "cálculo de intereses",    "su red de préstamos financia la mitad del comercio","cobro sin clemencia",                     "hay deudores a quienes perdonó toda la deuda sin decirles"),
    ("Helm el Mensajero",     "Sindicato", "Acechante",       "Sin residencia fija","Reciente","velocidad e invisibilidad","en veinte años nunca fue interceptado",             "lealtad solo al siguiente mensaje",       "lee todos los mensajes que lleva"),
    ("Isel la Analista",      "Sindicato", "Tejehechizos",    "Sala de Datos",     "Reciente", "análisis sin emociones",  "sus predicciones tienen el noventa y uno por ciento de precisión","frialdad ante consecuencias humanas","la predicción que más erró fue la que más importaba"),
    ("Jorn el Mercader Gris", "Sindicato", "Acechante",       "Mercado Flotante",  "Clásica",  "sentido del precio",      "nunca vendió algo que no valía lo que pedía",      "cinismo comercial total",                 "regaló el objeto más valioso que tuvo"),
    ("Kira la Intérprete",    "Sindicato", "Acechante",       "Puertos del Este",  "Reciente", "fluidez entre culturas",  "negoció acuerdos en diecisiete idiomas distintos",  "pérdida de cultura propia",               "olvidó su idioma materno hace diez años"),
    ("Lorn el Archivero Gris","Sindicato", "Tejehechizos",    "Archivo Central",   "Antigua",  "custodio de verdades",    "preservó documentos que tres facciones quemaron",  "usa la información como poder pasivo",    "el documento más importante lo tiene en su mente, no en papel"),
    ("Mael la Infiltrada",    "Sindicato", "Acechante",       "Desconocido",       "Reciente", "transformación de identidad","pasó tres años como noble de la Alianza sin ser detectada","pérdida de identidad propia",       "a veces cree que es la noble que interpretó"),
    ("Norn el Contador Negro","Sindicato", "Tejehechizos",    "Contaduría Oculta", "Reciente", "matemática de sombras",   "lleva la contabilidad de cuatro facciones distintas","moralidad completamente transaccional",   "sabe exactamente dónde está cada moneda de Aethelgard"),
    ("Orel el Corredor",      "Sindicato", "Maestra de Caza", "Ciudad Movimiento", "Reciente", "movilidad extrema",       "en diez años nunca durmió dos noches en el mismo lugar","incapacidad de establecer hogar",       "hay un lugar al que quiere regresar y no puede"),
    ("Pira la Falsaria",      "Sindicato", "Tejehechizos",    "Taller Oculto",     "Clásica",  "artesanía perfecta",      "fabricó identidades para cien personas que lo necesitaban","banalización de la identidad",      "ella misma vive con una identidad que fabricó"),
    ("Qael la Vigilante",     "Sindicato", "Acechante",       "Torre de Vigilancia","Reciente","observación total",       "documentó actividades de tres líderes durante dos años","voyeurismo ético cuestionable",       "tiene información que podría cambiar Aethelgard y la retiene"),
    ("Rael el Prestanombres", "Sindicato", "Acechante",       "Ciudad de Firmas",  "Reciente", "invisibilidad en plain sight","su nombre está en mil documentos y nadie lo conoce","ausencia de presencia real",           "hay un documento con su nombre real que aún no ha encontrado"),
    ("Sorn la Controladora",  "Sindicato", "Tejehechizos",    "Sala de Control",   "Antigua",  "gestión de redes complejas","coordina cincuenta agentes sin que ninguno sepa de los otros","deshumanización de los recursos",  "uno de los cincuenta es su hijo y ella lo sabe"),
    ("Tael el Comodín",       "Sindicato", "Acechante",       "Ciudad Libre",      "Reciente", "imprevisibilidad calculada","su única virtud y defecto: nunca hace lo predecible","imposibilidad de planificación a largo plazo","tiene un plan a largo plazo que nadie adivinaría"),
    ("Uren la Mentirosa Honesta","Sindicato","Acechante",     "Ciudad Mentira",    "Reciente", "verdades desde el engaño","nunca mintió en lo que importaba aunque usó engaño","confusión entre método y principio",      "hay una persona a quien nunca pudo mentirle"),
    ("Vorn el Agente Doble",  "Sindicato", "Acechante",       "Sin residencia",    "Clásica",  "ambigüedad como herramienta","trabajó para cuatro organizaciones simultáneamente","incertidumbre sobre sus propias lealtades","ya no recuerda para quién empezó a trabajar originalmente"),
    ("Wael la Informante",    "Sindicato", "Acechante",       "Ciudad Cualquiera", "Reciente", "invisibilidad social",    "una camarera que cambió el resultado de una guerra","trivialidad aparente que oculta profundidad","sabe que fue ella quien lo cambió y nadie más lo sabe"),
    ("Xorn el Tasador",       "Sindicato", "Tejehechizos",    "Mercado de Valores","Reciente", "valor de todo en moneda", "valoró correctamente el Eternium cuando nadie más podía","reducción de todo a precio",          "hay una cosa que no puede poner en precio"),
    ("Yael la Sin Precio",    "Sindicato", "Acechante",       "Lugar no cartografiado","Antigua","valor en lo que otros descartan","encontró el uso para lo que todos tiraban",      "dificultad para reconocer valor convencional","tiene algo de valor incalculable que cree que no vale nada"),
    
    # ── SIN FACCIÓN / NEUTRALES ───────────────────────────────────────────────
    ("Abran el Eremita",      "ninguna",   "Tejehechizos",    "Cueva del Viento",  "Antigua",  "sabiduría de aislamiento","resolvió el Enigma del Eternium que todos ignoraron","incapacidad de transmitir conocimiento", "la solución la encontró en un sueño que no recuerda"),
    ("Bela la Nómada",        "ninguna",   "Maestra de Caza", "El camino mismo",   "Reciente", "libertad absoluta",       "fue la primera en cruzar las montañas del extremo norte","incapacidad de comprometerse con lugares","lo que vio al norte la cambió pero no lo dice"),
    ("Cael sin Bando",        "ninguna",   "Vanguardista",    "Tres Fronteras",    "Clásica",  "equidistancia total",     "medió entre las tres facciones en veinte conflictos","parálisis ante las propias convicciones", "en secreto tiene una opinión que nunca expresó"),
    ("Dara la Curandera Libre","ninguna",  "Tejehechizos",    "Sin hogar",         "Reciente", "medicina sin burocracia", "curó a cien personas que ningún sistema hubiera atendido","vulnerabilidad económica",            "tiene una condición que no puede curarse a sí misma"),
    ("Eld el Cronista",       "ninguna",   "Acechante",       "Archivo Libre",     "Antigua",  "precisión histórica",     "el único cronista que las tres facciones citan por igual","dificultad de edición por imparcialidad","su crónica más importante todavía no ha terminado"),
    ("Fern la Investigadora",  "ninguna",  "Tejehechizos",    "Laboratorio Propio","Reciente", "curiosidad sin agenda",   "descubrió la relación entre mazmorra y luna",      "incapacidad de parar antes de entender todo","su laboratorio tiene resultados que no ha publicado porque le dan miedo"),
    ("Gael el Sin Nombre",    "ninguna",   "Vanguardista",    "Ciudad Perdida",    "Clásica",  "anonimato como poder",    "resolvió la crisis del Puerto sin que nadie supiera que fue él","incapacidad de recibir reconocimiento","quiere ser reconocido y huye de serlo"),
    ("Hari la Druida",        "ninguna",   "Tejehechizos",    "Bosque Central",    "Antigua",  "conexión con la vida",    "restauró el bosque quemado en cinco años",         "rechazo de la civilización",              "usa artefactos de ciudad que esconde en el bosque"),
    ("Iral el Filósofo",      "ninguna",   "Tejehechizos",    "Sin lugar fijo",    "Antigua",  "pensamiento puro",        "su trabajo filosófico cambió la ética de dos facciones","incapacidad de aplicar sus propios principios","vive en contradicción con todo lo que enseña"),
    ("Jael el Árbitro",       "ninguna",   "Acechante",       "Ciudad Neutral",    "Reciente", "imparcialidad perfecta",  "en veinte años de arbitraje nunca fue cuestionado", "frialdad ante el sufrimiento de los árbitros","hay un caso que afectó su imparcialidad y lo ocultó"),
    ("Korn la Profetisa",     "ninguna",   "Tejehechizos",    "Torre de Piedra",   "Antigua",  "visión inevitable",       "predijo la caída de tres gobernantes con precisión","carga del conocimiento del futuro",       "su profecía más importante es sobre ella misma"),
    ("Lira el Vagabundo",     "ninguna",   "Maestra de Caza", "Todas las ciudades","Reciente", "adaptación sin raíces",   "sobrevivió cinco años en el territorio sin facción",  "incapacidad de quedarse cuando importa",  "se fue justo antes de que lo necesitaran"),
    ("Mael el Matemático",    "ninguna",   "Tejehechizos",    "Academia Propia",   "Antigua",  "abstracción total",       "demostró que el Vacío tiene estructura matemática",  "incapacidad de comunicar sus descubrimientos","sabe la fórmula del colapso del Eternium"),
    ("Nael la Sin Pasado",    "ninguna",   "Acechante",       "Desconocido",       "Reciente", "presente absoluto",       "resolvió problemas de todas las facciones sin tomar partido","ausencia de compromisos a largo plazo","tiene un pasado que ni ella misma recuerda"),
    ("Orel el Místico",       "ninguna",   "Tejehechizos",    "Templo Abandonado", "Antigua",  "experiencia del Vacío",   "regresó del Vacío y sobrevivió para contarlo",     "desconexión con la realidad ordinaria",   "lo que vio en el Vacío lo cambió más de lo que admite"),
    
    # ── PERSONAJES DE ÉPOCAS ANTIGUAS ─────────────────────────────────────────
    ("Aldren el Fundador",    "Alianza",   "Vanguardista",    "Ciudad Origen",     "Antigua",  "visión fundacional",      "escribió el primer tratado constitutivo de la Alianza","rigidez en sus propias ideas",           "el tratado tiene una cláusula que no contó a nadie"),
    ("Bersha la Antigua",     "ninguna",   "Tejehechizos",    "Época del Origen",  "Antigua",  "memoria de eras",         "recuerda el mundo antes de las tres facciones",    "nostalgia paralizante",                   "el mundo anterior era mejor y peor en formas que no comparte"),
    ("Cael el Primer Gremio", "Alianza",   "Vanguardista",    "Ciudad Fundación",  "Antigua",  "cooperación como principio","fundó el primer gremio de aventureros de Aethelgard","desconfianza en el liderazgo individual","el primer gremio fracasó y lo refundó tres veces"),
    ("Dara la Profetisa Mayor","ninguna",  "Tejehechizos",    "Torre del Tiempo",  "Antigua",  "visión centenaria",       "sus profecías se verifican un siglo después",      "incomunicabilidad de lo que ve",          "tiene profecías sobre el presente que no quiere revelar"),
    ("Elan el Primer Mago",   "ninguna",   "Tejehechizos",    "Pre-Historia",      "Antigua",  "poder sin precedente",    "domó el primer Elemental de Eternium documentado",  "soberbia que costó vidas",                "el precio del primer dominio no está en ningún registro"),
    ("Forn el Constructor Divino","Alianza","Tejehechizos",   "Ciudad de Dios",    "Antigua",  "obra trascendente",       "construyó el primer observatorio capaz de predecir el Vacío","fanatismo religioso",             "su observatorio muestra algo que interpretó mal"),
    ("Grael el Último Rey",   "ninguna",   "Vanguardista",    "Reino Caído",       "Antigua",  "grandeza terminal",       "fue el último rey antes de las tres facciones",    "incapacidad de aceptar el cambio necesario","eligió la caída sobre la transformación"),
    ("Harl el Primero Imperial","Imperio", "Vanguardista",    "Origen del Imperio","Antigua",  "unificación por fuerza",  "conquistó dieciocho reinos en veinte años",         "deshumanización de los conquistados",     "al final de su vida escribió que se había equivocado en todo"),
    ("Iral la Primera Sindicato","Sindicato","Acechante",     "Origen del Sindicato","Antigua", "visión de futuro opaco",  "vio que el mundo necesitaría lo que el Sindicato ofrece","cinismo fundacional",                 "tenía ideales que sacrificó al fundar el Sindicato"),
    ("Jael el Vidente Original","ninguna", "Tejehechizos",   "Tiempo de los Primeros","Antigua","visión sin filtros",    "documentó el primer contacto con el Vacío",        "carga insoportable de saber",             "lo que vio nunca fue completamente registrado"),
    ("Kern el Gran Herrero",  "ninguna",   "Vanguardista",    "Fragua Original",   "Antigua",  "creación de lo impensable","forjó las primeras armas de Eternium de la historia","transmisión deficiente del conocimiento","la fórmula completa se perdió con él"),
    ("Lira la Madre de Gremios","Alianza", "Vanguardista",    "Ciudad Primer Gremio","Antigua","organización natural",   "creó el sistema gremial que dura hasta hoy",       "exceso de estructura",                    "el sistema tiene un defecto que nunca corrigió"),
    
    # ── PERSONAJES MENORES PERO SIGNIFICATIVOS ────────────────────────────────
    ("Aeln el Tabernero",     "ninguna",   "Acechante",       "Taberna del Cruce", "Reciente", "escucha que todo lo ve",  "salvó al Gran Consejo sin saberlo",                "invisibilidad que duele",                 "sabe exactamente quién planificó el atentado del puente"),
    ("Bern la Comadrona",     "ninguna",   "Tejehechizos",    "Aldea Central",     "Reciente", "presencia en el umbral", "trajo al mundo a mil quinientos niños sanos",       "carga del duelo de los que no sobrevivieron","sabe qué niños tienen destino especial y no lo dice"),
    ("Cael el Molinero",      "ninguna",   "Vanguardista",    "Villa del Molino",  "Clásica",  "resistencia ordinaria",   "defendió su molino de tres ataques distintos solo","humildad que desestima sus propios logros","fue el primero en detectar la plaga que casi destruye todo"),
    ("Dara la Maestra",       "ninguna",   "Tejehechizos",    "Pueblo Cualquiera", "Reciente", "transmisión de conocimiento","enseñó a cinco generaciones en cuarenta años",    "invisibilidad social del educador",       "uno de sus alumnos cambiará Aethelgard y ella lo sabe"),
    ("Eld el Guardián del Faro","ninguna", "Acechante",       "Faro del Extremo",  "Clásica",  "vigilia sin fallo",       "su faro nunca se apagó en cuarenta años",          "aislamiento total voluntario",            "vio algo desde el faro que no ha contado a nadie"),
    ("Fern el Mercader de Aldea","ninguna","Acechante",       "Ruta del Interior", "Reciente", "comercio honesto y pequeño","conectó cuarenta aldeas que antes no se conocían",  "invisibilidad del trabajo pequeño",       "sin su red, tres aldeas habrían muerto de hambre"),
    ("Gael la Cocinera de Palacio","Imperio","Acechante",     "Cocinas del Trono", "Reciente", "acceso invisible al poder","conoce los secretos de tres generaciones de nobles","nula valoración de su propio conocimiento","tiene la receta del veneno que mató al segundo consejero"),
    ("Hari el Barquero",      "ninguna",   "Maestra de Caza", "Río Grande",        "Clásica",  "conocimiento del río",    "cruzó el río en la tormenta imposible y salvó doce personas","incapacidad de dejar el río",     "el río le dijo algo una noche que nadie le creería"),
    ("Iral el Cartero de Aldea","ninguna", "Acechante",       "Ruta Circular",     "Reciente", "memoria de mensajes",     "en treinta años nunca olvidó un encargo ni una dirección","invisibilidad total ante los poderosos","lleva mensajes entre enemigos que no saben que los conecta"),
    ("Jael el Sin Título",    "ninguna",   "Vanguardista",    "Ciudad Ordinaria",  "Reciente", "ordinariez heroica",      "hizo la cosa correcta en el momento decisivo",     "total inconsciencia de su propio valor",  "nunca supo que lo que hizo salvó la ciudad"),
    ("Kern la Anciana del Mercado","ninguna","Acechante",     "Mercado Central",   "Antigua",  "memoria de precios",      "puede decir el precio de cualquier cosa en cualquier año","nadie la toma en serio",           "predice las crisis económicas con un año de anticipación"),
    ("Lira la Niña Profetisa","ninguna",   "Tejehechizos",    "Aldea Olvidada",    "Reciente", "inocencia como lente",    "dijo cosas sobre el futuro que resultaron exactas",  "nadie le creyó hasta que fue tarde",      "sigue viendo cosas pero ya dejó de hablar"),
    ("Mael el Viejo Herrero", "ninguna",   "Vanguardista",    "Fragua del Pueblo", "Clásica",  "experiencia irrepetible", "hizo mil herramientas en cincuenta años",           "invisibilidad del artesano ordinario",    "una de sus herramientas tiene propiedades que no entiende"),
    ("Nael el Escriba Menor", "Alianza",   "Tejehechizos",    "Biblioteca Menor",  "Reciente", "precisión silenciosa",    "copió el documento que perdido hubiera costado una guerra","invisibilidad del copista",         "en la copia añadió algo que nadie ha notado todavía"),
    ("Orel el Pescador",      "ninguna",   "Maestra de Caza", "Puerto Pequeño",    "Reciente", "conocimiento del mar local","predice el tiempo mejor que cualquier instrumento", "desconfianza de lo que viene de fuera",   "ha visto algo en el mar que lo mantiene cerca de la costa"),
    ("Pira la Tejedora",      "ninguna",   "Tejehechizos",    "Taller de Telas",   "Clásica",  "creación de belleza",     "sus tapices cuentan la historia que los libros no dicen","invisibilidad del arte popular",     "los tapices tienen mensajes en código que nadie descifró"),
    ("Qorn el Portero",       "Imperio",   "Vanguardista",    "Puerta de la Capital","Reciente","guardia invisible",      "registró a tres millones de personas en veinte años","total invisibilidad funcional",          "recuerda a cada una de ellas"),
    ("Rael la Lavandera",     "Alianza",   "Acechante",       "Ciudad Alta",       "Clásica",  "acceso a ropa, acceso a secretos","cambió el resultado de tres intrigas sin participar","nadie la ve como amenaza",          "sabe qué secretos guarda cada prenda que limpia"),
    ("Sorn el Guardabosques Menor","Alianza","Maestra de Caza","Bosque Mediano",   "Reciente", "amor al territorio propio","protegió su bosque de tres incendios deliberados",  "incapacidad de ver más allá de su bosque","su bosque tiene algo que haría rico a quien lo encontrara"),
    ("Tael la Partera Sabia", "ninguna",   "Tejehechizos",    "Aldea del Centro",  "Antigua",  "sabiduría práctica",      "resolvió dos crisis imposibles con sentido común",  "nadie la considera una experta",          "es más sabia que cualquier académico que la visita"),

    # ── PERSONAJES CON HISTORIAS ÚNICAS ───────────────────────────────────────
    ("Aldra la Inmortal Voluntaria","ninguna","Tejehechizos","Lugar sin nombre",   "Antigua",  "elección de la limitación","eligió perder la inmortalidad para ser más útil",  "obsesión con la utilidad",                "la forma de renunciar a la inmortalidad la conoce"),
    ("Bern el que Recuerda",  "ninguna",   "Tejehechizos",    "Todas las ciudades","Antigua",  "memoria perfecta de mundos","recuerda civilizaciones anteriores a Aethelgard",  "carga de memorias que no son suyas",      "sabe cómo terminó la civilización anterior al Invierno"),
    ("Cael el Doblado",       "Alianza",   "Vanguardista",    "Campo de Batalla",  "Clásica",  "supervivencia imposible", "sobrevivió heridas que matarían a diez hombres",   "incapacidad de sentir miedo apropiado",   "no puede morir de causas ordinarias y no sabe por qué"),
    ("Dara la Dos Mentes",    "Sindicato", "Tejehechizos",    "Académica",         "Reciente", "dualidad funcional",       "tiene dos formas de pensar completamente diferentes que alterna","inestabilidad en la transición","cada mente sabe cosas que la otra no"),
    ("Eld el Curado",         "ninguna",   "Vanguardista",    "Hospital de Aldea", "Reciente", "gratitud activa",          "dedicó su vida a devolver lo que recibió cuando era enfermo","ciclo de deuda que no termina",       "fue curado de algo que debería haberlo matado"),
    ("Fern la de las Lenguas Muertas","ninguna","Tejehechizos","Ruinas Antiguas",  "Antigua",  "hablar con el pasado",     "puede hablar idiomas extintos con hablantes que no existen","aislamiento en el tiempo",          "escucha voces del pasado que le cuentan cosas"),
    ("Gael el Que Carga Todo","ninguna",   "Vanguardista",    "Ciudad Anónima",    "Reciente", "voluntad de carga",        "cargó con responsabilidades de cien personas sin quejarse","incapacidad de soltar cargas",       "hay algo que carga que arruinará su vida si no lo suelta"),
    ("Hari la Tocada por el Vacío","ninguna","Tejehechizos",  "Contacto del Vacío","Reciente", "percepción expandida",     "vio el Vacío por accidente y sobrevivió",          "percepción de realidades que otros no ven","el Vacío la sigue observando"),
    ("Iral el Último de su Clan","ninguna","Maestra de Caza", "Clan Extinguido",   "Clásica",  "tradición como identidad", "preservó el conocimiento de un clan que desapareció","carga de ser el único",              "hay un ritual que solo él puede hacer y que no quiere hacer"),
    ("Jael la que Habla con Muertos","ninguna","Tejehechizos","Cementerio Mayor",  "Antigua",  "mediación entre planos",   "resolvió tres misterios hablando con sus víctimas", "carga de las voces que no callan",        "un muerto le dijo algo sobre el futuro que no repite"),
    ("Kern el Eterno Estudiante","ninguna","Tejehechizos",    "Academia y más",    "Antigua",  "aprendizaje sin fin",      "estudia en cada academia de Aethelgard desde hace cien años","incapacidad de concluir",          "ya sabe todo pero no puede parar de aprender"),
    ("Lira la que No Envejece","ninguna",  "Tejehechizos",    "Sin determinar",    "Antigua",  "juventud inmutable",       "parece tener veinte años desde hace doscientos",   "aislamiento inevitable",                  "sabe cómo detener el envejecimiento y no dice para qué lo usa"),
    ("Mael el Justo Injusto", "Alianza",   "Acechante",       "Ciudad Tribunal",   "Reciente", "justicia imperfecta",      "hizo justicia cien veces, injusticia una vez que importó","carga de la injusticia propia",      "la injusticia que cometió le persigue en forma de pesadilla"),
    ("Nael el Constructor de Sueños","ninguna","Tejehechizos","Taller de Ilusiones","Antigua", "magia de sueño",           "construyó mundos que las personas visitaban al dormir","adicción propia a sus ilusiones",   "hay un sueño que no puede controlar y que regresa cada noche"),
    ("Orel el Que Perdió Todo","ninguna",  "Vanguardista",    "Ciudad Destruida",  "Clásica",  "reconstrucción total",     "reconstruyó su vida tres veces desde cero",        "incapacidad de aferrarse a nada",         "perdió todo a propósito la tercera vez para probar algo"),
    ("Pira la Cazadora de Cazadores","ninguna","Maestra de Caza","Sin base",      "Reciente", "justicia cazadora",        "detuvo a diecisiete cazadores de recompensas ilegales","métodos que imitan lo que combate","usa métodos que no puede defender públicamente"),
    ("Qael el Profeta sin Creyentes","ninguna","Tejehechizos","Plaza de Mercado",  "Reciente", "visión ignorada",          "predijo la Plaga antes de que comenzara",          "incapacidad de hacer que lo escuchen",    "sigue prediciendo y nadie sigue escuchando"),
    ("Rael la Traductora del Vacío","Alianza","Tejehechizos",  "Academia Alta",     "Reciente", "puente entre mundos",     "tradujo el primer texto del Vacío a lenguaje comprensible","consecuencias desconocidas de traducir el Vacío","el texto la cambió y no sabe cuánto"),
    ("Sorn el que Durmió Cien Años","ninguna","Tejehechizos",  "Mazmorra Azul",    "Antigua",  "perspectiva discontinua",  "entró a la Mazmorra y salió cien años después",    "desconexión con el presente",             "lo que vio en esos cien años lo sabe y no lo puede contar"),
    ("Tael la Mitad y Mitad", "ninguna",   "Acechante",       "Frontera de Todo",  "Reciente", "identidad dual",           "opera con igual efectividad en cualquiera de las dos facciones","ausencia de hogar real",         "ha sido reclutada por todas las facciones sin que ninguna sepa de las otras"),
]

# ═══════════════════════════════════════════════════════════════════════════════
# 14 PLANTILLAS DE ASPECTO — generan texto único a partir de datos del personaje
# ═══════════════════════════════════════════════════════════════════════════════

def _aspecto_nacimiento(nombre, faccion, clase, origen, era, rasgo, logro, defecto, secreto):
    if faccion == "ninguna":
        afil = "sin facción conocida"
    else:
        afil = f"en el territorio de la {faccion}"
    return (f"{nombre} nació en {origen}, {afil}, durante la era {era.lower()}. "
            f"Desde joven mostró lo que sus contemporáneos describían como {rasgo}, "
            f"una cualidad que moldearía todo lo que vendría después.",
            f"Los registros de su infancia son escasos, como suele ocurrir con quienes "
            f"nacen fuera de las ciudades grandes, pero quienes lo conocieron de niño "
            f"coinciden en que ya entonces había algo diferente en cómo veía el mundo.")

def _aspecto_formacion(nombre, faccion, clase, origen, era, rasgo, logro, defecto, secreto):
    class_map = {"Vanguardista":"el combate cuerpo a cuerpo","Acechante":"el sigilo y la información",
                 "Tejehechizos":"la magia y el conocimiento arcano","Maestra de Caza":"el rastreo y la supervivencia"}
    especialidad = class_map.get(clase, "sus habilidades específicas")
    return (f"La formación de {nombre} en {especialidad} fue, como en muchos de su generación, "
            f"una combinación de instrucción formal y experiencia que ningún maestro podría haber diseñado completamente.",
            f"Lo que el tiempo y el esfuerzo desarrollaron fue {rasgo}: no como virtud abstracta "
            f"sino como herramienta concreta que {nombre} aprendió a usar con precisión creciente.")

def _aspecto_primer_logro(nombre, faccion, clase, origen, era, rasgo, logro, defecto, secreto):
    return (f"El primer logro significativo de {nombre} fue modesto comparado con lo que vendría: "
            f"una situación donde {rasgo} hizo la diferencia entre el fracaso y un resultado que nadie más hubiera podido obtener.",
            f"No hubo reconocimiento inmediato. Los primeros logros raramente lo tienen. "
            f"Lo que {nombre} ganó fue algo más valioso: la certeza de que su enfoque funcionaba.")

def _aspecto_gran_logro(nombre, faccion, clase, origen, era, rasgo, logro, defecto, secreto):
    return (f"El logro que definiría para siempre el nombre de {nombre} fue cuando {logro}. "
            f"Lo que los registros no capturan completamente es el proceso que llevó a ese momento.",
            f"Quienes estuvieron cerca describen no una victoria fácil sino el resultado de decisiones "
            f"acumuladas durante años, cada una posible por {rasgo}, cada una necesaria para que el "
            f"resultado final fuera posible.")

def _aspecto_defecto(nombre, faccion, clase, origen, era, rasgo, logro, defecto, secreto):
    return (f"Junto con {rasgo}, {nombre} cargó durante toda su vida con {defecto}. "
            f"No era una debilidad simple ni una tragedia: era la sombra de exactamente lo que lo hacía extraordinario.",
            f"Los que mejor lo conocieron decían que no se podía tener uno sin el otro: "
            f"que el mismo impulso que llevó a {nombre} a {logro} era el que, en otras circunstancias, "
            f"producía {defecto}.")

def _aspecto_secreto(nombre, faccion, clase, origen, era, rasgo, logro, defecto, secreto):
    return (f"Hay algo sobre {nombre} que los registros no mencionan y que pocos conocieron en vida: "
            f"que {secreto}.",
            f"Esta dimensión de {nombre} no contradice lo que se sabe de él sino que lo completa. "
            f"Las personas son siempre más complejas que lo que sus registros capturan.")

def _aspecto_relacion_alianza(nombre, faccion, clase, origen, era, rasgo, logro, defecto, secreto):
    if faccion == "Alianza":
        texto1 = f"La relación de {nombre} con la Alianza era la relación de alguien con la institución que lo formó: compleja, leal en lo fundamental y crítica en los detalles."
        texto2 = f"Conocía sus defectos mejor que nadie porque los había vivido desde adentro, y los señalaba precisamente porque le importaba lo que la Alianza podía ser."
    elif faccion == "Imperio":
        texto1 = f"La Alianza veía a {nombre} con la mezcla de respeto y desconfianza que reservaba para los más capaces del Imperio: reconocían el valor, cuestionaban las intenciones."
        texto2 = f"La relación nunca fue cómoda pero tampoco fue hostil de forma permanente. En los momentos que importaban, encontraron formas de colaborar que ninguno hubiera predicho."
    elif faccion == "Sindicato":
        texto1 = f"La Alianza y {nombre} mantenían la distancia cautelosa que caracterizaba las relaciones entre la Alianza y el Sindicato en general, pero con matices específicos."
        texto2 = f"Había cosas que {nombre} nunca haría para o contra la Alianza, y la Alianza lo sabía. Esos límites no escritos definían el espacio dentro del cual la relación era posible."
    else:
        texto1 = f"La Alianza conocía a {nombre} como una presencia en el mundo que no podía ignorar aunque no pudiera clasificarla cómodamente en sus categorías."
        texto2 = f"La neutralidad de {nombre} era en sí misma una posición que la Alianza encontraba a veces útil y a veces frustrante, dependiendo de en qué lado de una situación se encontrara."
    return (texto1, texto2)

def _aspecto_relacion_imperio(nombre, faccion, clase, origen, era, rasgo, logro, defecto, secreto):
    if faccion == "Imperio":
        texto1 = f"La relación de {nombre} con el Imperio era la de alguien que entendía la institución demasiado bien para idealizarla y demasiado bien para abandonarla."
        texto2 = f"Veía en el Imperio lo que era: imperfecto, poderoso, capaz de cosas que ninguna alternativa podía hacer, incapaz de otras que deberían ser simples. Trabajaba con eso."
    elif faccion == "Alianza":
        texto1 = f"El Imperio miraba a {nombre} con la combinación de respeto y desconfianza que tenía para cualquiera de la Alianza que resultara ser realmente capaz."
        texto2 = f"En dos ocasiones que los registros mencionan, el Imperio y {nombre} encontraron formas de trabajar hacia el mismo objetivo. En ambas, ambas partes salieron diciendo que lo harían de nuevo si era necesario. Y en ambas, la definición de 'necesario' era diferente."
    elif faccion == "Sindicato":
        texto1 = f"El Imperio tenía un expediente sobre {nombre}, como tenía expedientes de todos los operadores del Sindicato de cierta importancia."
        texto2 = f"Lo que lo diferenciaba de otros era que el Imperio había intentado usarlo en dos ocasiones y en las dos había funcionado. Eso lo colocaba en una categoría especial de respeto profesional que el Imperio raramente otorgaba."
    else:
        texto1 = f"El Imperio clasificaba a {nombre} en la categoría de 'factor independiente': alguien que no podía ignorarse pero que tampoco podía controlarse."
        texto2 = f"Prefería tenerlo en posición neutral que en posición hostil, lo que llevó a tres interacciones que los registros imperiales describen simplemente como 'resueltas satisfactoriamente'."
    return (texto1, texto2)

def _aspecto_relacion_sindicato(nombre, faccion, clase, origen, era, rasgo, logro, defecto, secreto):
    if faccion == "Sindicato":
        texto1 = f"La relación de {nombre} con el Sindicato era la que tenía cualquiera que había crecido en la organización: una combinación de lealtad a lo que funcionaba y escepticismo sobre todo lo demás."
        texto2 = f"El Sindicato era para {nombre} no una familia ni una empresa sino algo más parecido a un entorno: el contexto dentro del cual su trabajo era posible y que él contribuía a mantener funcional."
    elif faccion == "Alianza":
        texto1 = f"El Sindicato veía a {nombre} como veía a los más capaces de la Alianza: como posibles clientes, posibles fuentes de información y posibles complicaciones, en ese orden."
        texto2 = f"Nunca fue completamente confiado, nunca completamente descartado. En el vocabulario interno del Sindicato, {nombre} era 'contacto de valor, de confianza limitada', lo cual para el Sindicato era casi un elogio."
    elif faccion == "Imperio":
        texto1 = f"El Sindicato tenía una relación pragmática con {nombre}: cuando sus intereses convergían, cooperaban; cuando divergían, se mantenían a distancia."
        texto2 = f"Lo que el Sindicato valoraba de {nombre} no era tanto lo que podía hacer por ellos como lo que podía hacer contra ellos si las relaciones se deterioraban. Ese equilibrio lo mantenían cuidadosamente."
    else:
        texto1 = f"El Sindicato y {nombre} se movían en espacios que se superponían sin que ninguno tuviera sobre el otro una ventaja clara. Era una relación de respeto mutuo basado en capacidades equivalentes."
        texto2 = f"Hubo ocasiones en que el Sindicato intentó reclutar a {nombre} y ocasiones en que {nombre} usó los servicios del Sindicato. En ninguna de las dos direcciones llegó a un acuerdo que satisficiera a ambas partes completamente."
    return (texto1, texto2)

def _aspecto_metodo(nombre, faccion, clase, origen, era, rasgo, logro, defecto, secreto):
    return (f"El método de {nombre} no era el de ninguna escuela específica sino el que había desarrollado en años de trabajo: una combinación de {rasgo} aplicado a cada problema con consistencia que sus contemporáneos encontraban sorprendente.",
            f"No podía enseñar completamente su método porque parte de él no era transmisible: era el resultado de décadas de ajustes que cada problema había producido. Lo que sí enseñaba era el principio subyacente, y esperaba que sus estudiantes construyeran sus propios métodos desde ahí.")

def _aspecto_perdida(nombre, faccion, clase, origen, era, rasgo, logro, defecto, secreto):
    return (f"Hubo una pérdida en la vida de {nombre} que los registros registran de pasada pero que quienes lo conocían identifican como el momento que definió quién se convirtió.",
            f"No fue la pérdida en sí sino cómo respondió: eligió continuar, elegir qué parte de sí mismo dejar ir y qué parte preservar. Esa elección fue en muchos sentidos más reveladora que ninguna victoria.")

def _aspecto_filosofia(nombre, faccion, clase, origen, era, rasgo, logro, defecto, secreto):
    return (f"La filosofía de {nombre}, si se puede llamar así, era práctica antes que teórica: "
            f"creía en la demostración por acción más que en el argumento por palabras.",
            f"<i>«Lo que hago define lo que soy. No lo que digo que soy, no lo que otros dicen de mí, "
            f"no lo que debería ser según reglas externas. Lo que elijo hacer en el momento que importa.»</i> "
            f"— palabras atribuidas a {nombre} en múltiples fuentes que difieren en el contexto pero no en el texto.")

def _aspecto_fin(nombre, faccion, clase, origen, era, rasgo, logro, defecto, secreto):
    return (f"El final de la historia activa de {nombre} fue coherente con quien había sido: "
            f"ni una muerte heroica de cuento ni una retirada apacible, sino algo más matizado que "
            f"ambas opciones.",
            f"Lo que dejó fue más intangible que los registros pueden capturar: "
            f"personas que habían aprendido de él, problemas que no existían gracias a él, "
            f"y la pregunta de qué hubiera sido posible con más tiempo que permanece sin respuesta.")

def _aspecto_legado_vivo(nombre, faccion, clase, origen, era, rasgo, logro, defecto, secreto):
    return (f"El legado de {nombre} no está principalmente en monumentos ni en registros sino en "
            f"las cadenas de influencia que conectan sus decisiones con consecuencias que todavía "
            f"se sienten décadas después.",
            f"Quienes fueron formados por {nombre} llevan algo de {rasgo} en su forma de trabajar. "
            f"Las instituciones que tocó llevan algo de sus ideas en su estructura. "
            f"Y hay problemas que no existen hoy precisamente por lo que {nombre} hizo en su momento.")

PLANTILLAS = [
    ("Orígenes",                _aspecto_nacimiento),
    ("Formación",               _aspecto_formacion),
    ("Primer logro",            _aspecto_primer_logro),
    ("Gran logro",              _aspecto_gran_logro),
    ("La sombra que cargó",     _aspecto_defecto),
    ("El secreto",              _aspecto_secreto),
    ("Y la Alianza",            _aspecto_relacion_alianza),
    ("Y el Imperio",            _aspecto_relacion_imperio),
    ("Y el Sindicato",          _aspecto_relacion_sindicato),
    ("El método",               _aspecto_metodo),
    ("La gran pérdida",         _aspecto_perdida),
    ("Filosofía",               _aspecto_filosofia),
    ("El final",                _aspecto_fin),
    ("El legado vivo",          _aspecto_legado_vivo),
]


# ═══════════════════════════════════════════════════════════════════════════════
# GENERACIÓN
# ═══════════════════════════════════════════════════════════════════════════════

def _generar_mensajes_extra():
    msgs = []
    icon_map = {"Vanguardista": "⚔️", "Tejehechizos": "🔮", "Acechante": "🗡️", "Maestra de Caza": "🏹"}
    for datos in PERSONAJES_EXTRA:
        nombre, faccion, clase, origen, era, rasgo, logro, defecto, secreto = datos
        icon = icon_map.get(clase, "📜")
        for aspecto, fn in PLANTILLAS:
            p1, p2 = fn(nombre, faccion, clase, origen, era, rasgo, logro, defecto, secreto)
            texto = f"{icon} <b>CRÓNICAS DE AETHELGARD</b>\n<i>{nombre} — {aspecto}</i>\n\n{p1}\n\n{p2}"
            msgs.append((texto, "personajes_plantilla"))
    return msgs


def _importar_lore_original():
    """Importa los mensajes del lore_diario.py original."""
    try:
        import lore_diario
        mensajes = getattr(lore_diario, "LORE_MENSAJES", [])
        return [(m, "lore_original") for m in mensajes]
    except ImportError:
        print("⚠️  No se encontró lore_diario.py — se omiten los mensajes originales.")
        return []


# ═══════════════════════════════════════════════════════════════════════════════
# BASE DE DATOS
# ═══════════════════════════════════════════════════════════════════════════════

def expandir_lore(objetivo=3650):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM lore_mensajes")
    actuales = c.fetchone()[0]
    conn.close()

    if actuales >= objetivo:
        print(f"ℹ️  Ya hay {actuales} mensajes (objetivo: {objetivo}). Sin cambios.")
        return actuales

    print(f"⏳ Expandiendo lore... (actuales: {actuales}, objetivo: {objetivo})")

    # 1) Añadir los originales de lore_diario.py si no están
    originales = _importar_lore_original()
    # 2) Generar nuevos con plantillas
    nuevos = _generar_mensajes_extra()
    # 3) Combinar y mezclar
    todos = originales + nuevos
    random.seed(99)
    random.shuffle(todos)

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Obtener el máximo orden actual para no sobrescribir
    c.execute("SELECT MAX(orden) FROM lore_mensajes")
    max_orden_row = c.fetchone()
    max_orden = (max_orden_row[0] or -1) + 1

    insertados = 0
    for i, (texto, categoria) in enumerate(todos):
        c.execute(
            "INSERT INTO lore_mensajes (texto, categoria, orden) VALUES (?, ?, ?)",
            (texto, categoria, max_orden + i)
        )
        insertados += 1

    conn.commit()
    conn.close()

    total = actuales + insertados
    print(f"✅ {insertados} mensajes añadidos. Total: {total}")
    return total


def stats():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM lore_mensajes")
    total = c.fetchone()[0]
    c.execute("SELECT categoria, COUNT(*) FROM lore_mensajes GROUP BY categoria ORDER BY COUNT(*) DESC")
    cats = c.fetchall()
    conn.close()
    print(f"\n📊 TOTAL MENSAJES DE LORE: {total}")
    print(f"   Cobertura: {total // 365} años y {total % 365} días sin repetición")
    print(f"   Categorías:")
    for cat, cnt in cats:
        print(f"     {cat:30s}: {cnt:5d}")


if __name__ == "__main__":
    print("🚀 Expandiendo base de datos de Lore Diario...")
    total = expandir_lore(objetivo=3650)
    stats()
    if total >= 3650:
        print(f"\n✨ ¡Objetivo alcanzado! {total} mensajes = {total // 365} años y {total % 365} días de lore único.")
    else:
        print(f"\n⚠️  Total: {total}. Objetivo 3650 no alcanzado. Añade más personajes al pool.")

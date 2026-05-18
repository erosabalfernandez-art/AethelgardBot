#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# automatizaciones.py — Eventos automáticos periódicos (Superadmin exclusivo)
#
# Comandos:
#   /auto_estado               — estado de todas las automatizaciones
#   /auto_guerra_on/off        — guerra diaria automática
#   /auto_jefes_on/off         — jefes semanales automáticos (ambos)
#   /auto_jefe_normal_on/off   — control individual del jefe Normal
#   /auto_jefe_dificil_on/off  — control individual del jefe Difícil
#
# Jobs periódicos:
#   job_auto_guerra             — cada 24h (00:00 UTC)
#   job_check_jefes_diario      — cada 24h (verifica si toca jefe hoy y lanza lore)

import os
import sys
import sqlite3
import random
import logging
import json
from datetime import datetime, timedelta, date

from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

RAIZ = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, RAIZ)

import superadmin as sa
import db_helper

logger = logging.getLogger(__name__)

SUPERADMIN_ID = int(os.environ.get("SUPERADMIN_ID", "0"))
DB_PATH = "aethelgard.db"

# ==================== POOL DE JEFES AUTOMÁTICOS ====================

JEFES_AUTO_NORMAL = [
    {"nombre": "Gran Goblin Warchief",       "lore_tipo": "goblin"},
    {"nombre": "Golem de Piedra Anciano",     "lore_tipo": "golem"},
    {"nombre": "Dragón del Bosque",           "lore_tipo": "dragon"},
    {"nombre": "Liche Menor",                 "lore_tipo": "liche"},
    {"nombre": "Troll Gigante de las Nieves", "lore_tipo": "troll"},
    {"nombre": "Basilisco de Cristal",        "lore_tipo": "basilisco"},
    {"nombre": "Ogro Jefe de Clan",           "lore_tipo": "ogro"},
]

JEFES_AUTO_DIFICIL = [
    {"nombre": "Dragón Ancestral",           "lore_tipo": "dragon_ancestral"},
    {"nombre": "Archidemonio del Vacío",     "lore_tipo": "demonio"},
    {"nombre": "Rey Sombra Eterno",          "lore_tipo": "rey_sombra"},
    {"nombre": "Titán de Lava Primordial",   "lore_tipo": "titan"},
    {"nombre": "Heraldo del Caos",           "lore_tipo": "caos"},
    {"nombre": "Behemoth Cataclísmico",      "lore_tipo": "behemoth"},
    {"nombre": "Liche Supremo Inmortal",     "lore_tipo": "liche_supremo"},
]

FACCIONES_GUERRA = ["Alianza", "Imperio", "Sindicato"]

TIEMPO_RECLUTAMIENTO = 30 * 60   # 30 minutos tras la aparición del jefe

# ==================== MENSAJES DE LORE ====================
# 4 mensajes por tipo de jefe, espaciados 30 min cada uno.
# El jefe aparece 30 min DESPUÉS del cuarto mensaje.

LORE_NORMAL = {
    "goblin": [
        "📯 *Primer aviso — Dos horas antes de la batalla*\n\n"
        "Un mensajero exhausto acaba de llegar a la ciudad jadeando. Su ropa está desgarrada y sus ojos reflejan terror puro.\n\n"
        "«¡Los goblins! ¡Son miles! Venían del este, del Bosque de Ceniza. Han arrasado la aldea de Moldenfar... no quedó nada en pie. Ni una sola choza. El que los comanda es enorme, el doble que cualquier goblin que haya visto en mi vida. Lleva una corona de huesos y ríe... ríe mientras quema todo.»\n\n"
        "Los guardias de la ciudad tocan las campanas de alerta. Algo se acerca.",

        "🔥 *Segundo aviso — Hora y media antes de la batalla*\n\n"
        "El humo ya es visible desde las murallas. Las nubes al este se han teñido de un naranja oscuro y enfermizo.\n\n"
        "Un explorador acaba de regresar con noticias: los goblins avanzan en formación de guerra, arrasando todo a su paso. Han quemado los cultivos del Valle de Grimthorn y masacrado el ganado. El Warchief marcha al frente, golpeando su pecho con los puños, rugiendo en el dialecto tribal antiguo.\n\n"
        "Traducción del dialecto: «La ciudad será mía. Sus huesos serán mis trofeos.»\n\n"
        "Los ciudadanos buscan refugio. Las tabernas están llenas de rumores y miedo.",

        "⚔️ *Tercer aviso — Una hora antes de la batalla*\n\n"
        "Ya se pueden escuchar los tambores tribales. Un ritmo grave y constante que resuena en el suelo, en los muros, en los huesos.\n\n"
        "Bum. Bum. Bum.\n\n"
        "Los aldeanos que huían del este confirman lo peor: el Gran Goblin Warchief lleva consigo cientos de guerreros de élite, los Colmillos Negros, curtidos en décadas de guerra tribal. No son los goblins cobardes del folclore. Estos han matado Dragones menores. Han tomado fortalezas enanas.\n\n"
        "El jefe de la guardia mira el horizonte en silencio y dice en voz baja:\n«Necesitamos héroes. Los mejores que esta tierra tenga.»",

        "💀 *Cuarto aviso — Treinta minutos antes de la batalla*\n\n"
        "Las puertas de la ciudad tiemblan. Las antorchas de los goblins ya son visibles desde las almenas, un mar de fuego que avanza inexorable.\n\n"
        "El Gran Goblin Warchief se ha detenido a las afueras. Uno de sus capitanes lanza a sus pies la cabeza del guardabosques que custodiaba el paso del río. Un mensaje claro.\n\n"
        "El monstruo levanta su hacha de guerra al cielo y aúlla con toda la potencia de sus pulmones.\n\n"
        "La batalla está a punto de comenzar. Solo los más valientes de Aethelgard pueden detenerlo.\n\n"
        "🐉 *El jefe aparecerá en breve. Prepárate para usar /jefe\\_unirse*",
    ],
    "golem": [
        "📯 *Primer aviso — Dos horas antes de la batalla*\n\n"
        "Los mineros de las Canteras del Norte han enviado un pájaro mensajero con un informe perturbador.\n\n"
        "«Las piedras hablan. No es metáfora. La montaña vibra desde las profundidades y algo se está levantando. Vimos las primeras grietas hace cuatro horas, luego los derrumbes. Después... lo vimos. Dos ojos del tamaño de carruajes, hechos de roca viva y luz interior ámbar. La tierra se abre paso para dejarle camino.»\n\n"
        "El Golem de Piedra Anciano lleva dormido mil años bajo las montañas. Alguien o algo lo ha despertado.",

        "🔥 *Segundo aviso — Hora y media antes de la batalla*\n\n"
        "Los árboles del bosque al norte caen como ramitas. Se pueden sentir los pasos desde kilómetros de distancia, cada uno un pequeño terremoto.\n\n"
        "Un sabio de la Academia de Reliquias ha consultado los archivos: el último avistamiento de un Golem Anciano fue hace novecientos años. Destruyó tres ciudades antes de que un ejército de magos lograra sellarlo. Esta vez no hay magos. Solo aventureros.\n\n"
        "El golem no siente dolor. No conoce el miedo. Su única función es la devastación.",

        "⚔️ *Tercer aviso — Una hora antes de la batalla*\n\n"
        "El suelo ha empezado a crujir bajo los pies. Ventanas rotas. Copas cayendo de las mesas. Un zumbido profundo que resuena en el pecho.\n\n"
        "El Golem ya es visible en la distancia: quince metros de roca sólida, musgo y cristal de obsidiana. Sus pasos marcan cráteres en el suelo. Las aves han huido en masa del bosque cercano. El silencio que deja a su paso es aterrador.\n\n"
        "¿Cómo se mata algo que no tiene corazón que perforar, ni mente que engañar?",

        "💀 *Cuarto aviso — Treinta minutos antes de la batalla*\n\n"
        "Ha llegado. El Golem de Piedra Anciano está en las afueras, y cada paso suyo parte el suelo como si fuera arcilla húmeda.\n\n"
        "Un ingeniero de guerra calcula rápidamente: su armadura natural es equivalente a cien capas de acero forjado. Sus brazos pueden derribar una torre en un solo golpe. Ha absorbido proyectiles de catapulta sin siquiera parpadear.\n\n"
        "Pero hay algo que los libros dicen: el núcleo de energía en su interior es su punto débil. Si sufre suficiente daño acumulado, el núcleo se fractura.\n\n"
        "🐉 *El jefe aparecerá en breve. Prepárate para usar /jefe\\_unirse*",
    ],
    "dragon": [
        "📯 *Primer aviso — Dos horas antes de la batalla*\n\n"
        "Las bestias del Bosque de Esmeralda han huido en masa hacia los campos cultivados, pisoteando cosechas y sembrando el pánico.\n\n"
        "Los cazadores que se adentraron al bosque para investigar volvieron en silencio, con miradas vacías. Solo uno habló:\n\n"
        "«Hay una sombra en el bosque. Una sombra que respira. Escuché el crujido de árboles centenarios como si fueran ramas secas. Vi el fuego antes de ver al dragón. Un fuego verde, espeso, que quema incluso el agua.»\n\n"
        "El Dragón del Bosque ha despertado de su letargo.",

        "🔥 *Segundo aviso — Hora y media antes de la batalla*\n\n"
        "El humo verde se eleva sobre el bosque. Los exploradores confirman: el dragón lleva horas moviéndose en círculos concéntricos, como un depredador marcando territorio.\n\n"
        "Los registros de la orden de caballería lo describen así: «Escamas del verde del veneno. Wingspan suficiente para eclipsar el sol. Inteligente. Vengativo. No ataca por hambre. Ataca por rabia ancestral.»\n\n"
        "Hubo un tiempo en que coexistió con los mortales. Alguien rompió ese pacto.",

        "⚔️ *Tercer aviso — Una hora antes de la batalla*\n\n"
        "Un rugido que sacude el cielo. Las nubes se parten a su alrededor cuando vuela en círculos bajos sobre la ciudad.\n\n"
        "Puede verse claramente ahora: el Dragón del Bosque es todo lo que los bardos cantaban y más. Las escamas brillan con una luz enfermiza. El fuego que expulsa es verdoso y denso, y donde cae, la tierra queda corrupta durante años.\n\n"
        "Ha elegido esta ciudad. Por qué, nadie lo sabe. Pero no se irá solo.",

        "💀 *Cuarto aviso — Treinta minutos antes de la batalla*\n\n"
        "El Dragón del Bosque ha aterrizado en el exterior de la ciudad y está destruyendo las defensas perimetrales metódicamente, como si conociera cada torre y cada fortín.\n\n"
        "Un anciano druida, el único que habla el idioma del dragón, intenta negociar. El dragón lo escucha. Luego lo ignora y continúa.\n\n"
        "Solo la fuerza colectiva de los héroes de Aethelgard puede hacer lo que la diplomacia no pudo.\n\n"
        "🐉 *El jefe aparecerá en breve. Prepárate para usar /jefe\\_unirse*",
    ],
    "liche": [
        "📯 *Primer aviso — Dos horas antes de la batalla*\n\n"
        "Las tumbas del Cementerio del Cuervo han empezado a abrirse solas desde la medianoche.\n\n"
        "El custodio del cementerio llegó corriendo al amanecer, tartamudeando: «Los muertos caminan. No como zombis torpes... marchan en formación. Y algo los comanda desde el centro del mausoleo principal. Vi una luz morada. Sentí frío en el alma, no en la piel.»\n\n"
        "Un Liche. El non-muerto más temido entre los practitioners de la magia oscura. Ha elegido Aethelgard como su nuevo reino.",

        "🔥 *Segundo aviso — Hora y media antes de la batalla*\n\n"
        "Los cuervos vuelan en patrones extraños sobre el cementerio. La hierba en un radio de cien metros ha muerto de golpe, dejando el suelo negro y quebradizo.\n\n"
        "Un mago de la corte analiza la energía: «Es magia de nigromancia avanzada. El Liche no solo controla a los muertos: los crea. Cada caído cerca de él puede convertirse en un nuevo sirviente.»\n\n"
        "El ejército de no-muertos crece con cada minuto que pasa.",

        "⚔️ *Tercer aviso — Una hora antes de la batalla*\n\n"
        "Ya se puede ver al Liche desde las almenas. Una silueta alta y esquelética envuelta en túnicas que se mueven sin viento. En su mano, un báculo coronado con una calavera que emite pulsos de luz morada.\n\n"
        "El Liche habla, y su voz llega a todos los rincones de la ciudad al mismo tiempo:\n«Sus ancestros me sirvieron. Ustedes me servirán también. La muerte es solo el comienzo.»\n\n"
        "Los curanderos distribuyen amuletos de protección. No todos están convencidos de que funcionen.",

        "💀 *Cuarto aviso — Treinta minutos antes de la batalla*\n\n"
        "El Liche ha levantado un escudo de energía oscura alrededor del cementerio. Desde dentro, las catapultas no hacen daño. Solo el combate cuerpo a cuerpo puede alcanzarlo.\n\n"
        "Su ejército de no-muertos ya ronda las murallas. Cada guardia caído se une a sus filas segundos después.\n\n"
        "Hay una sola forma de detener este ciclo: encontrar al Liche y destruir su Filacteria, el objeto en el que guarda su alma. Pero primero hay que llegar a él.\n\n"
        "🐉 *El jefe aparecerá en breve. Prepárate para usar /jefe\\_unirse*",
    ],
    "troll": [
        "📯 *Primer aviso — Dos horas antes de la batalla*\n\n"
        "Los pastores de las montañas del norte traen noticias alarmantes. Sus rebaños han desaparecido en una sola noche.\n\n"
        "«Escuchamos el rugido antes del alba. Sacudió el suelo. Luego silencio. Al amanecer, las ovejas habían desaparecido. Y encontramos huellas. Cada una medía lo que mide un carro completo.»\n\n"
        "Un Troll Gigante de las Nieves. No se veía uno tan cerca de tierras habitadas desde la Gran Helada de hace tres generaciones. Y este parece más grande que todos los registrados.",

        "🔥 *Segundo aviso — Hora y media antes de la batalla*\n\n"
        "Ha cruzado el paso de montaña. Los torrentes de nieve que dejó a su paso han bloqueado los caminos al norte.\n\n"
        "El troll tiene hambre. Esa es la sencilla y aterradora verdad. El invierno fue duro en las montañas y ha bajado a buscar alimento. Los trolls no distinguen entre ganado, madera, roca o personas.\n\n"
        "Testigos lo describen: «Blanco como la nieve, tan alto como un árbol adulto. Lleva incrustadas rocas y pedazos de hielo en la piel como si fueran armadura. Sus manos... podrían aplastar una casa.»",

        "⚔️ *Tercer aviso — Una hora antes de la batalla*\n\n"
        "El troll ya está en los arrabales. Ha destruido tres graneros y volcado un molino de agua.\n\n"
        "Un veterano de las Guerras del Norte advierte: «Los trolls se regeneran en el combate. Hay que causarle daño muy rápido, sin darle tiempo a recuperarse. Y el fuego ayuda. El fuego siempre ayuda.»\n\n"
        "El troll ruge cada vez que algo le molesta. Y hay muchas cosas que le molestan. Principalmente: todo.",

        "💀 *Cuarto aviso — Treinta minutos antes de la batalla*\n\n"
        "El Troll Gigante de las Nieves está en las puertas. Literalmente. Está golpeando la puerta principal con lo que parece ser un árbol arrancado de raíz.\n\n"
        "Cada golpe hace temblar las murallas. Los niños lloran. Los viejos rezan.\n\n"
        "Los héroes de Aethelgard son la última línea de defensa. Si las puertas ceden, el troll entra en la ciudad y el caos será total.\n\n"
        "🐉 *El jefe aparecerá en breve. Prepárate para usar /jefe\\_unirse*",
    ],
    "basilisco": [
        "📯 *Primer aviso — Dos horas antes de la batalla*\n\n"
        "Un comerciante llegó paralizado de cintura para abajo. Los sanadores dicen que sus piernas están petrificadas, convertidas en piedra hasta la rodilla.\n\n"
        "Cuando recuperó la voz, dijo solo tres palabras: «La mirada mata.»\n\n"
        "El Basilisco de Cristal habita las cuevas bajo el lago Espejo desde tiempos inmemoriales. Algo o alguien lo ha expulsado de su guarida. Y ahora camina entre los vivos.",

        "🔥 *Segundo aviso — Hora y media antes de la batalla*\n\n"
        "Se han encontrado tres personas petrificadas en los caminos del este. Sus expresiones son de terror absoluto, capturadas para siempre en piedra.\n\n"
        "Un estudioso de bestias explica: «El Basilisco de Cristal no petrifica con magia. Es un veneno en su mirada, una toxina que se transmite a través de los ojos. Mirar directamente a sus ojos mata. Mirar su reflejo paraliza temporalmente.»\n\n"
        "Los herreros están fabricando escudos pulidos. Puede ser la única defensa.",

        "⚔️ *Tercer aviso — Una hora antes de la batalla*\n\n"
        "El Basilisco ha llegado a las afueras. Se pueden escuchar sus escamas de cristal arrastrándose por la piedra, un sonido como mil espadas chocando a la vez.\n\n"
        "Es hermoso y letal al mismo tiempo: sus escamas refractan la luz del sol creando arcoíris mortales. Quienes lo han visto y sobrevivido dicen que es el ser más extraño que han visto.\n\n"
        "Los ojos, sin embargo, son completamente negros. Dos pozos sin fondo.",

        "💀 *Cuarto aviso — Treinta minutos antes de la batalla*\n\n"
        "El Basilisco de Cristal está en la plaza del mercado, aplastando puestos con su cuerpo de diez metros y dejando un rastro vítreo y brillante a su paso.\n\n"
        "Los héroes que vayan a combatirlo deberán mantener la mirada baja o usar reflejos para atacar. Una mirada directa puede ser el final.\n\n"
        "«¡No lo miréis a los ojos!» — grita el jefe de guardia desde las almenas.\n\n"
        "🐉 *El jefe aparecerá en breve. Prepárate para usar /jefe\\_unirse*",
    ],
    "ogro": [
        "📯 *Primer aviso — Dos horas antes de la batalla*\n\n"
        "El clan de ogros del pantano ha roto la tregua. Otra vez.\n\n"
        "Un explorador trae el informe: «El Jefe de Clan viene en persona esta vez. Lo llaman Grakthar el Aplastador. He visto su obra: cinco aldeas arrasadas en una semana. No roban ni saquean, simplemente destruyen. Es su naturaleza.»\n\n"
        "Los ogros no son estúpidos. Grakthar, se dice, es más astuto que la mayoría. Lo que lo hace mucho más peligroso que un simple bruto.",

        "🔥 *Segundo aviso — Hora y media antes de la batalla*\n\n"
        "Grakthar ha reunido su clan alrededor de la ciudad. Se les puede escuchar en las colinas circundantes, golpeando sus mazas contra sus escudos en un ritmo unificado.\n\n"
        "BOOM. BOOM. BOOM.\n\n"
        "Es una táctica psicológica. Los ogros lo saben. Quieren que el miedo llegue antes que ellos.\n\n"
        "Funcionan. Las calles están casi vacías. Solo los guardias permanecen en sus puestos, con los nudillos blancos sobre las lanzas.",

        "⚔️ *Tercer aviso — Una hora antes de la batalla*\n\n"
        "Grakthar ha enviado un ultimátum a través de un mensajero (un ogro pequeño, apenas dos metros): «Rendíos y viviréis. Resistid y seréis el suelo que pisan mis botas.»\n\n"
        "El consejo de la ciudad ha respondido: «No.»\n\n"
        "El Jefe de Clan ha soltado una carcajada que se escuchó a kilómetros de distancia. Luego comenzó a moverse hacia las murallas.\n\n"
        "Es inmenso. Tres veces el tamaño de un humano adulto, con una maza de hierro que parece una columna de templo. Pero lo más intimidante son sus ojos inteligentes, calculadores.",

        "💀 *Cuarto aviso — Treinta minutos antes de la batalla*\n\n"
        "Grakthar el Aplastador está en las puertas. Ha ordenado a su clan que rodeen la ciudad para cortar la retirada.\n\n"
        "Está solo frente a las puertas. Solo. Sin escolta. Como señal de que no necesita ayuda para destrozar las defensas.\n\n"
        "Y tiene razón. La primera embestida ha partido la barra de la puerta principal. La segunda la ha astillado. A la tercera...\n\n"
        "🐉 *El jefe aparecerá en breve. Prepárate para usar /jefe\\_unirse*",
    ],
}

# Lore para jefes difíciles — más épico y aterrador
LORE_DIFICIL = {
    "dragon_ancestral": [
        "🌑 *Primer presagio — Dos horas antes del cataclismo*\n\n"
        "Las estrellas han desaparecido del cielo. No hay nubes. Simplemente... dejaron de estar.\n\n"
        "Los astrólogos de la torre observan el firmamento ennegrecido con terror. Esto ocurrió una vez antes, según los registros más antiguos: la noche en que el Dragón Ancestral despertó por primera vez, hace diez mil años, y su aliento convirtió el Mar Interior en un desierto de cristal negro.\n\n"
        "El Dragón Ancestral es más antiguo que las montañas. Más antiguo que el lenguaje. Más antiguo que los dioses que adoran en los templos de esta ciudad. Y está despierto.",

        "🔥 *Segundo presagio — Hora y media antes del cataclismo*\n\n"
        "La temperatura ha bajado diez grados en minutos. El aliento congela en el aire. Los pozos se han helado.\n\n"
        "Un dragón ancestral no tiene temperatura corporal porque no es solo un ser físico: existe entre este plano y el siguiente. Su despertar desequilibra el tejido de la realidad local.\n\n"
        "Se han abierto grietas luminosas en el cielo, como cicatrices en el aire. A través de ellas se ven brevemente otros mundos, otros cielos. Algunos habitantes las miran fascinados. Luego apartan la mirada, llorando sin saber por qué.\n\n"
        "El Dragón está llegando desde el plano del Éter. Y cuando cruce completamente, nada volverá a ser igual.",

        "⚡ *Tercer presagio — Una hora antes del cataclismo*\n\n"
        "El suelo sangra.\n\n"
        "No es metáfora. Grietas en la tierra manan un líquido rojo oscuro que no es agua ni magma. Los sacerdotes de todos los templos rezan simultáneamente, cada uno a su dios, sin coordinación, simplemente por instinto.\n\n"
        "El Dragón Ancestral está a punto de manifestarse. Su mero acercamiento corrompe la realidad. Los animales han entrado en un estado de trance. Los pájaros vuelan en círculos perfectos. Los perros aúllan en tonos que duelen en los oídos.\n\n"
        "Un viejo cronista anota con manos temblorosas: «Si sobrevivimos a esta noche, será el milagro más grande que haya presenciado Aethelgard.»",

        "💀 *Cuarto presagio — Treinta minutos antes del cataclismo*\n\n"
        "Ha cruzado.\n\n"
        "El Dragón Ancestral se materializa sobre la ciudad en toda su magnitud insondable. Sus alas tapan el horizonte de norte a sur. Sus escamas son negras con venas de luz dorada que pulsan como un corazón. Sus ojos son soles oscuros, imposibles, que absorben la luz en lugar de emitirla.\n\n"
        "Cuando abre la boca, no sale fuego. Sale el tiempo. Imágenes de este lugar destruido, de generaciones que nunca nacerán, de un futuro convertido en polvo.\n\n"
        "Es una advertencia. O una promesa.\n\n"
        "Solo los héroes más legendarios de Aethelgard tienen alguna posibilidad de enfrentarlo y sobrevivir.\n\n"
        "🐉 *El jefe aparecerá en breve. Solo los más valientes: /jefe\\_unirse*",
    ],
    "demonio": [
        "🌑 *Primer presagio — Dos horas antes del cataclismo*\n\n"
        "El ritual falló. No hubo sobrevivientes para explicarlo, pero los resultados son inconfundibles.\n\n"
        "La academia de magia negra en las afueras está en llamas con un fuego que no se apaga. No con agua, no con tierra, no con magia. Cinco magos de alto rango intentaron sellarlo y sus herramientas se fundieron. Uno de ellos corrió hacia el norte gritando en un idioma que nadie reconoció y no ha regresado.\n\n"
        "Algo fue invocado. Algo que no debería haber sido invocado. El Archidemonio del Vacío ha sido liberado y camina entre nosotros.",

        "🔥 *Segundo presagio — Hora y media antes del cataclismo*\n\n"
        "La realidad tiembla. No el suelo, no los edificios: la realidad misma parpadea como una llama.\n\n"
        "Hay momentos en que la ciudad desaparece por un instante y lo que aparece en su lugar es un páramo oscuro, un mundo de sombra y roca negra y cielos carmesí. El mundo que habita el Archidemonio.\n\n"
        "Quienes tienen el don de ver el éter describen al demonio: «Es enorme. Cambia de forma constantemente, pero siempre conserva esos cuernos, que llegan hasta las nubes. Sus ojos son seis, y cada uno ve un plano diferente de la realidad simultáneamente.»\n\n"
        "No hay palabras para describir el poder que emana de él.",

        "⚡ *Tercer presagio — Una hora antes del cataclismo*\n\n"
        "Los caídos están regresando.\n\n"
        "No como no-muertos, sino como marionetas del demonio, con sus voces y sus memorias pero con ojos completamente negros. Dicen el nombre de sus seres queridos. Dicen que todo estará bien. Sonríen de una forma que no es correcta.\n\n"
        "El Archidemonio se alimenta del miedo y de la esperanza corrompida. Cuanto más esperanza destruye, más poderoso se vuelve.\n\n"
        "Los paladines de la ciudad sellan sus armaduras con runas de protección. Los sacerdotes distribuyen relicarios. Nadie está seguro de que sirvan de algo.",

        "💀 *Cuarto presagio — Treinta minutos antes del cataclismo*\n\n"
        "El Archidemonio del Vacío ha cruzado completamente al plano mortal.\n\n"
        "Su presencia física es una herida en el mundo. El aire a su alrededor corrompe todo lo que toca: madera, metal, tela, carne. Sus palabras, cuando habla, no son sonidos, son conceptos que se introducen directamente en la mente y permanecen ahí para siempre.\n\n"
        "Ha hecho una pregunta a la ciudad entera, mentalmente, simultáneamente, a todos al mismo tiempo:\n«¿Quién se atreve?»\n\n"
        "Muy pocos. Pero esos pocos son suficientes.\n\n"
        "🐉 *El jefe aparecerá en breve. Solo los más valientes: /jefe\\_unirse*",
    ],
    "rey_sombra": [
        "🌑 *Primer presagio — Dos horas antes del cataclismo*\n\n"
        "Las sombras se han vuelto independientes.\n\n"
        "La sombra de un árbol apunta en dirección contraria al sol. La sombra de un guardia en la muralla mueve los brazos aunque él esté inmóvil. Los espejos muestran imágenes de un segundo antes en lugar del presente.\n\n"
        "Los estudiosos del ocultismo saben qué significa: el Rey Sombra ha roto el velo entre el mundo de la luz y el mundo de la oscuridad. Su reino se superpone al nuestro. Y donde están los dos mundos juntos, él tiene el poder.",

        "🔥 *Segundo presagio — Hora y media antes del cataclismo*\n\n"
        "Las antorchas se apagan solas. No el viento. Las llamas simplemente se rinden, como si algo las absorbiera.\n\n"
        "El Rey Sombra fue, hace mucho tiempo, el más grande rey-guerrero de Aethelgard. Gobernó con justicia durante cuarenta años. Luego buscó la inmortalidad en los lugares equivocados y encontró algo peor que la muerte.\n\n"
        "Ahora regresa. No para reclamar su reino sino para consumirlo. Todo lo que amó se convertirá en su combustible.",

        "⚡ *Tercer presagio — Una hora antes del cataclismo*\n\n"
        "La ciudad está en una penumbra permanente. La luz del sol llega atenuada, filtrada, como si hubiera un velo oscuro sobre el cielo.\n\n"
        "El Rey Sombra avanza y desde su cuerpo se desprenden sombras que se convierten en guerreros espectrales. Son los ecos de todos los que ha consumido. Luchan por él sin voluntad, sin miedo, sin cansancio.\n\n"
        "Solo hay una forma de dañarlo: con luz, con fuego, con fe. Las armas normales lo atraviesan como si fuera niebla.",

        "💀 *Cuarto presagio — Treinta minutos antes del cataclismo*\n\n"
        "El Rey Sombra Eterno está en el centro de la plaza principal, y donde pisa, el suelo se vuelve negro y frío como el espacio entre las estrellas.\n\n"
        "Su forma cambia constantemente: a veces el rey guerrero que fue, joven y orgulloso. A veces una cosa de sombra pura, sin forma definida, sin bordes, sin límites.\n\n"
        "Ha estado esperando esto. Ha esperado siglos para este momento.\n\n"
        "«Vuestras vidas son el precio», dice, y su voz suena en la cabeza de todos al mismo tiempo.\n\n"
        "🐉 *El jefe aparecerá en breve. Solo los más valientes: /jefe\\_unirse*",
    ],
    "titan": [
        "🌑 *Primer presagio — Dos horas antes del cataclismo*\n\n"
        "El volcán que todos pensaban extinto ha comenzado a erupcionar. Pero esto no es una erupción normal.\n\n"
        "El magma no baja por los flancos de la montaña: sube verticalmente, como impulsado por una voluntad. Y en el centro de esa columna de fuego, hay una forma.\n\n"
        "Alta como una montaña. Hecha de roca viva y lava en movimiento. El Titán de Lava Primordial no fue creado; existe desde antes que la tierra se enfriara. Es un recuerdo del mundo cuando todo era fuego.",

        "🔥 *Segundo presagio — Hora y media antes del cataclismo*\n\n"
        "El calor ha aumentado veinte grados. La nieve en los picos cercanos se derrite en tiempo real. Los ríos comienzan a evaporarse.\n\n"
        "El Titán camina y donde pone el pie, la roca se funde bajo su peso. Deja un rastro de lava que tardará décadas en enfriarse.\n\n"
        "Los geólogos calculan: a su ritmo actual, llegará a las murallas en hora y media. Las murallas que tardaron veinte años en construirse. El Titán las atravesará como si fueran papel.",

        "⚡ *Tercer presagio — Una hora antes del cataclismo*\n\n"
        "Las murallas del sur ya están calientes al tacto. Los guardias han sido evacuados de esa sección porque el metal de sus armaduras empieza a calentarse peligrosamente.\n\n"
        "El Titán de Lava Primordial no tiene objetivos ni rencores. Simplemente existe y su existencia destruye todo lo que no está hecho de roca o fuego.\n\n"
        "Agua. El agua es su única debilidad conocida. Grandes cantidades de agua pueden solidificar temporalmente su exterior. Pero nadie tiene suficiente agua para detenerlo completamente.",

        "💀 *Cuarto presagio — Treinta minutos antes del cataclismo*\n\n"
        "El horizonte sur brilla con luz de lava. Las nubes sobre él se han convertido en vapor. El cielo es rojo.\n\n"
        "El Titán emite un rugido que no se escucha: se siente en el estómago, en los dientes, en los huesos.\n\n"
        "Los alquimistas preparan granadas de agua helada. Los magos hidromantes concentran toda su energía. Los héroes de Aethelgard son la última esperanza de que esta ciudad no acabe convertida en un lago de lava para la posteridad.\n\n"
        "🐉 *El jefe aparecerá en breve. Solo los más valientes: /jefe\\_unirse*",
    ],
    "caos": [
        "🌑 *Primer presagio — Dos horas antes del cataclismo*\n\n"
        "Las reglas del mundo han dejado de funcionar.\n\n"
        "No de forma dramática, al principio. Pequeñas cosas: el agua fluyendo hacia arriba en los canales. Las llamas quemando hacia adentro. Los pájaros volando en reversa. Los relojes marcando el tiempo al revés.\n\n"
        "El Heraldo del Caos ha llegado. No es un ser con motivos o historia. Es la encarnación de la entropía misma, la fuerza que eventualmente disuelve todo orden en todo universo. Y ha elegido Aethelgard como punto de anclaje.",

        "🔥 *Segundo presagio — Hora y media antes del cataclismo*\n\n"
        "El lenguaje empieza a fallar. Las palabras no significan lo que se quiere decir. Un soldado grita «¡Avanzad!» y sus compañeros escuchan «¡Cantad!». Un médico pide vendajes y le traen peces.\n\n"
        "El Heraldo se alimenta de la confusión que crea. Cuanta más confusión, más se solidifica en este plano. Cuanto más se solidifica, más fuerte es su influencia.\n\n"
        "El mejor consejo que los sabios pueden dar: «Confiad en vuestros instintos, no en vuestros pensamientos. El Caos corrompe el razonamiento.»",

        "⚡ *Tercer presagio — Una hora antes del cataclismo*\n\n"
        "El Heraldo es visible ahora: una masa de colores que no existen, formas que los ojos no pueden procesar correctamente, que el cerebro interpreta diferente cada vez que se mira.\n\n"
        "Algunos lo ven como una nube de tormenta con ojos. Otros como un árbol caminante de cristal negro. Otros como una versión retorcida de alguien que conocen.\n\n"
        "Todos ven algo diferente. Esa es su naturaleza.",

        "💀 *Cuarto presagio — Treinta minutos antes del cataclismo*\n\n"
        "El radio de influencia del Heraldo se expande. Dentro de ese radio, la física es opcional.\n\n"
        "Flotan rocas. Las espadas se curvan en formas imposibles. El tiempo avanza a velocidades variables. Un minuto aquí puede ser diez segundos en el borde, o dos horas.\n\n"
        "Para combatirlo, los héroes deben entrar en ese campo de caos y mantener la coherencia mental. El que pierde la cabeza, literal y figuradamente, está perdido.\n\n"
        "🐉 *El jefe aparecerá en breve. Solo los más valientes: /jefe\\_unirse*",
    ],
    "behemoth": [
        "🌑 *Primer presagio — Dos horas antes del cataclismo*\n\n"
        "Algo ha salido del mar.\n\n"
        "El faro de la costa sur dejó de responder hace una hora. El barco de patrulla que fue a investigar envió un mensaje antes de desaparecer: «Es más grande que la ciudad.»\n\n"
        "El Behemoth Cataclísmico es la criatura más grande que existe en el mundo conocido. Los mapas antiguos lo dibujan como una isla con ojos. Vive en las profundidades oceánicas y emerge una vez cada varios siglos. Cuando lo hace, las costas se convierten en desiertos.",

        "🔥 *Segundo presagio — Hora y media antes del cataclismo*\n\n"
        "Las olas ya son visibles desde la ciudad. No olas normales: paredes de agua de veinte metros que el Behemoth desplaza simplemente caminando por el lecho marino.\n\n"
        "Cada paso suyo crea un pequeño tsunami. Está a kilómetros de distancia y ya la ciudad tiembla.\n\n"
        "Los registros históricos sobre el Behemoth son escasos porque nadie que lo viera desde cerca vivió para escribirlos. Solo hay relatos de segunda y tercera mano, de pescadores que lo vieron en la distancia y huyeron.",

        "⚡ *Tercer presagio — Una hora antes del cataclismo*\n\n"
        "Ha emergido completamente. Su cuerpo bloquea el horizonte marítimo. Es como si una nueva montaña hubiera aparecido en el mar.\n\n"
        "Su piel es negra con incrustaciones de coral, conchas y restos de barcos que ha acumulado a lo largo de siglos. Sus ojos brillan de un amarillo verdoso en las profundidades de su rostro.\n\n"
        "Camina hacia la ciudad. Lentamente. Sin apresurarse. Porque nada que haya encontrado en su historia ha podido detenerlo.",

        "💀 *Cuarto presagio — Treinta minutos antes del cataclismo*\n\n"
        "El mar ha retrocedido. El puerto está seco: barcas y peces varados en el barro, mientras el océano se acumula detrás del Behemoth como un manto líquido.\n\n"
        "Cuando llegue a tierra, si llega, el impacto de sus pisadas puede hundir edificios. Su aliento marino corroe metal y madera por igual.\n\n"
        "Los cañones de la muralla sur disparan sin efecto. Las catapultas tampoco. Su escama exterior, siglos de calcificación oceánica, es prácticamente impenetrable.\n\n"
        "Hay que buscar los puntos débiles. Hay que ser rápidos. Hay que ser muchos.\n\n"
        "🐉 *El jefe aparecerá en breve. Solo los más valientes: /jefe\\_unirse*",
    ],
    "liche_supremo": [
        "🌑 *Primer presagio — Dos horas antes del cataclismo*\n\n"
        "Los muertos de todo el continente han recordado su nombre.\n\n"
        "En cementerios a cientos de kilómetros de aquí, los difuntos se agitan bajo la tierra. No para levantarse, sino porque sienten su presencia. Como acero que siente un imán poderoso.\n\n"
        "El Liche Supremo Inmortal lleva cinco siglos encerrado en un sello que requerió el sacrificio de cien magos para crear. Hoy el sello ha fallado. No se sabe por qué. No importa por qué. Lo que importa es que está libre y que recuerda perfectamente quién lo encerró.",

        "🔥 *Segundo presagio — Hora y media antes del cataclismo*\n\n"
        "Los descendientes de los magos que lo sellaron están siendo visitados. Uno por uno.\n\n"
        "No para matarlos. Para hacerles una oferta. Nadie sabe cuál. Los que reciben la visita se quedan mudos, con ojos vacíos, durante horas. Cuando recuperan la voz, dicen que todo está bien. Con una sonrisa que no es correcta.\n\n"
        "El Liche Supremo no actúa por ira. Actúa con paciencia de cinco siglos. Ha tenido mucho tiempo para planear este momento.",

        "⚡ *Tercer presagio — Una hora antes del cataclismo*\n\n"
        "La muerte misma obedece sus órdenes. En un radio de varios kilómetros, nada muere a menos que él lo desee. Las moscas no mueren. Las flores no se marchitan. Los heridos no sucumben. La muerte está... suspendida.\n\n"
        "Eso también significa que él es libre de matar cuando lo decida. La muerte solo opera cuando él la libera.\n\n"
        "Un sacerdote de la muerte reza en voz alta: «El dios de la muerte no responde. El Liche Supremo ha tomado el trono.»",

        "💀 *Cuarto presagio — Treinta minutos antes del cataclismo*\n\n"
        "El Liche Supremo Inmortal se mueve en procesión. Delante de él, millones de polvo de huesos que se reensamblan en guerreros. A sus lados, los espíritus de los magos que lo sellaron, ahora sus sirvientes eternos. Detrás de él, el silencio absoluto.\n\n"
        "No parece furioso. Parece aburrido. Y eso es lo más aterrador de todo.\n\n"
        "Su Filacteria fue destruida hace siglos en el proceso de sellarlo. Es verdaderamente inmortal ahora. Cada vez que cae, regresa más fuerte. La única victoria posible es alejarlo de nuevo, debilitarlo tanto que no pueda actuar durante generaciones.\n\n"
        "🐉 *El jefe aparecerá en breve. Solo los más valientes: /jefe\\_unirse*",
    ],
}

# Fallback genérico si el lore_tipo no tiene mensajes específicos
LORE_FALLBACK_NORMAL = [
    "📯 *Primer aviso — Dos horas antes de la batalla*\n\n"
    "Los exploradores al norte han enviado alertas urgentes. Una criatura poderosa avanza hacia la ciudad. La descripción hiela la sangre: enorme, peligrosa, con rastros de destrucción a su paso.\n\n"
    "Se están preparando las defensas. Los mercenarios y aventureros disponibles están siendo convocados. Aethelgard necesita sus héroes.",

    "🔥 *Segundo aviso — Hora y media antes de la batalla*\n\n"
    "La criatura ya es visible desde las torres de vigilancia. Avanza sin prisa, sin miedo, arrasando todo lo que encuentra a su paso.\n\n"
    "Los guardias redoblan la vigilancia en las murallas. Los herreros afilan armas de emergencia. En las tabernas, los rumores corren como la pólvora.",

    "⚔️ *Tercer aviso — Una hora antes de la batalla*\n\n"
    "Ya se escucha. Ya se siente. Algo poderoso se aproxima y Aethelgard está en su camino.\n\n"
    "Los civiles buscan refugio. Los héroes comprueban su equipo. El ambiente en la ciudad mezcla el miedo con la adrenalina de la batalla inminente.",

    "💀 *Cuarto aviso — Treinta minutos antes de la batalla*\n\n"
    "Está aquí. Aethelgard necesita sus mejores guerreros ahora mismo.\n\n"
    "La historia recordará esta batalla. Los que participen formarán parte de la leyenda de esta ciudad.\n\n"
    "🐉 *El jefe aparecerá en breve. Prepárate para usar /jefe\\_unirse*",
]

LORE_FALLBACK_DIFICIL = [
    "🌑 *Primer presagio — Dos horas antes del cataclismo*\n\n"
    "El cielo ha cambiado de color. Los animales huyen en masa. Los videntes despiertan en sudores fríos con la misma visión: una bestia de poder inconcebible que se aproxima.\n\n"
    "Aethelgard está en peligro real. Un peligro que no se veía en generaciones.",

    "🔥 *Segundo presagio — Hora y media antes del cataclismo*\n\n"
    "El poder que emana de la criatura distorsiona el aire a su alrededor. Los pájaros caen. Los árboles se inclinan en dirección contraria a su marcha, como intentando alejarse.\n\n"
    "Los hechiceros de mayor rango intentan medir su poder y sus instrumentos explotan.",

    "⚡ *Tercer presagio — Una hora antes del cataclismo*\n\n"
    "Ya están viendo su silueta en el horizonte. La descripción supera cualquier bestia registrada en los bestiarios. Esto es algo que los libros no capturaron completamente.\n\n"
    "Los paladines de mayor rango se preparan. Los alquimistas preparan sus mejores pociones. Esta puede ser la batalla de sus vidas.",

    "💀 *Cuarto presagio — Treinta minutos antes del cataclismo*\n\n"
    "Ha llegado. Una criatura de poder cataclísmico está ante las puertas de Aethelgard.\n\n"
    "No hay palabras que hagan justicia a lo que los defensores están viendo. Solo hay acción.\n\n"
    "Solo los héroes más poderosos y valientes tienen alguna posibilidad.\n\n"
    "🐉 *El jefe aparecerá en breve. Solo los más valientes: /jefe\\_unirse*",
]


# ==================== BASE DE DATOS ====================

def _init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS automatizaciones_config (
        clave TEXT PRIMARY KEY,
        valor TEXT DEFAULT '0'
    )''')
    defaults = [
        ("auto_guerra",              "0"),
        ("auto_jefe_normal",         "0"),
        ("auto_jefe_dificil",        "0"),
        # Calendario semanal de jefes
        ("jefe_semana_inicio",       ""),   # ISO date del lunes de la semana actual
        ("jefe_normal_fecha",        ""),   # ISO date del día asignado al jefe normal
        ("jefe_dificil_fecha",       ""),   # ISO date del día asignado al jefe difícil
        ("ultimo_jefe_fecha",        ""),   # ISO date del último jefe lanzado
        ("jefe_lore_en_curso",       "0"),  # 1 si hay secuencia de lore activa
        ("jefe_lore_inicio_ts",      ""),   # ISO datetime de cuando empezó el lore
        # Nuevas claves del panel de automatizaciones
        ("lore_diario_activo",       "0"),  # 1 = enviar lore a las 23:00 UTC
        ("lore_diario_indice",       "0"),  # índice del próximo mensaje de lore
        ("gg_sin_aprobacion",        "0"),  # 1 = guerra gremios se aprueba automáticamente
    ]
    for clave, valor in defaults:
        c.execute("INSERT OR IGNORE INTO automatizaciones_config (clave, valor) VALUES (?, ?)", (clave, valor))
    conn.commit()
    conn.close()

_init_db()


def _get(clave: str) -> str:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT valor FROM automatizaciones_config WHERE clave = ?", (clave,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else ""


def _set(clave: str, valor: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO automatizaciones_config (clave, valor) VALUES (?, ?)", (clave, valor))
    conn.commit()
    conn.close()


def _es_superadmin(user_id: int) -> bool:
    return user_id == SUPERADMIN_ID


# ==================== CÁLCULO DE HP ESCALABLE ====================

def _calcular_hp_jefe(dificultad: str) -> int:
    """Calcula HP del jefe basado en el número de jugadores activos y su nivel promedio."""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT COUNT(*), AVG(nivel) FROM jugadores WHERE nivel > 0")
        row = c.fetchone()
        conn.close()
        num_jug = max(1, row[0] or 1)
        avg_nivel = max(1, row[1] or 1)
    except Exception:
        num_jug, avg_nivel = 5, 10

    if dificultad == "Normal":
        hp = int(num_jug * avg_nivel * 120)
        return max(8000, min(hp, 50000))
    else:  # Dificil
        hp = int(num_jug * avg_nivel * 250)
        return max(18000, min(hp, 120000))


# ==================== CALENDARIO SEMANAL DE JEFES ====================

def _lunes_de_semana(d: date) -> date:
    """Devuelve el lunes de la semana que contiene la fecha d."""
    return d - timedelta(days=d.weekday())


def _programar_semana():
    """
    Elige al azar los días de esta semana (lunes=0 … domingo=6) para cada jefe.
    Restricciones:
    - Al menos 3 días de diferencia entre ambos (= 2 días libres entre ellos).
    - Ambos días dentro de los 7 días de la semana actual.
    Guarda los resultados en la tabla automatizaciones_config.
    """
    lunes = _lunes_de_semana(date.today())
    _set("jefe_semana_inicio", lunes.isoformat())

    # Generar todos los pares válidos (|a-b| >= 3)
    pares_validos = [
        (a, b)
        for a in range(7)
        for b in range(7)
        if a != b and abs(a - b) >= 3
    ]
    if not pares_validos:
        return  # seguridad

    dia_n, dia_d = random.choice(pares_validos)
    # Asignar aleatoriamente cuál es normal y cuál difícil
    if random.random() < 0.5:
        dia_n, dia_d = dia_d, dia_n

    fecha_normal  = (lunes + timedelta(days=dia_n)).isoformat()
    fecha_dificil = (lunes + timedelta(days=dia_d)).isoformat()

    _set("jefe_normal_fecha",  fecha_normal)
    _set("jefe_dificil_fecha", fecha_dificil)
    logger.info("Jefes programados: Normal=%s, Difícil=%s", fecha_normal, fecha_dificil)


def _verificar_y_reprogramar():
    """
    Verifica si el calendario semanal está vigente.
    Si no hay semana registrada o ya pasó, programa la semana actual.
    """
    semana_str = _get("jefe_semana_inicio")
    lunes_actual = _lunes_de_semana(date.today())

    if not semana_str:
        _programar_semana()
        return

    try:
        semana_guardada = date.fromisoformat(semana_str)
    except ValueError:
        _programar_semana()
        return

    if semana_guardada < lunes_actual:
        _programar_semana()


# ==================== SECUENCIA DE LORE + JEFE ====================

def _obtener_lores(tipo: str, dificultad: str, nombre: str) -> list:
    """Devuelve los 4 mensajes de lore para este jefe."""
    if dificultad == "Normal":
        pool = LORE_NORMAL
        fallback = LORE_FALLBACK_NORMAL
    else:
        pool = LORE_DIFICIL
        fallback = LORE_FALLBACK_DIFICIL

    mensajes_base = pool.get(tipo, fallback)
    # Reemplazar {nombre} si aparece en el texto
    return [m.replace("{nombre}", nombre) for m in mensajes_base]


async def _enviar_lore(context: ContextTypes.DEFAULT_TYPE, mensaje: str):
    """Envía un mensaje de lore a todos los jugadores."""
    try:
        from broadcast import broadcast_global
        await broadcast_global(context.bot, mensaje)
    except Exception as e:
        logger.error("_enviar_lore broadcast error: %s", e)


async def _lanzar_jefe_tras_lore(context: ContextTypes.DEFAULT_TYPE, nombre: str, hp: int,
                                  dificultad: str):
    """Lanza el jefe real después de que terminó el lore."""
    try:
        import jefes as jf

        jefe_existente = jf._obtener_jefe_activo(0)
        if jefe_existente:
            logger.info("_lanzar_jefe_tras_lore: ya hay jefe activo, omitiendo.")
            _set("jefe_lore_en_curso", "0")
            return

        jefe_id = await jf.crear_jefe_automatico(nombre, hp, dificultad, context)
        logger.info("Jefe automático '%s' (%s) lanzado, id=%s", nombre, dificultad, jefe_id)
        _set("ultimo_jefe_fecha", date.today().isoformat())
        _set("jefe_lore_en_curso", "0")

        # Programar inicio de combate tras el periodo de reclutamiento
        async def _job_iniciar_combate_auto(ctx: ContextTypes.DEFAULT_TYPE):
            try:
                await jf.iniciar_combate_automatico(ctx, ctx.job.data)
            except Exception as _e:
                logger.error("_job_iniciar_combate_auto error: %s", _e)
        context.job_queue.run_once(
            _job_iniciar_combate_auto,
            when=TIEMPO_RECLUTAMIENTO,
            data=jefe_id,
            name=f"auto_iniciar_combate_{jefe_id}"
        )

    except Exception as e:
        logger.error("_lanzar_jefe_tras_lore error: %s", e)
        _set("jefe_lore_en_curso", "0")


async def _job_enviar_lore_delayed(context: ContextTypes.DEFAULT_TYPE):
    """Job callback para enviar un mensaje de lore diferido. Usa context.job.data como texto."""
    try:
        msg = context.job.data
        await _enviar_lore(context, msg)
    except Exception as e:
        logger.error("_job_enviar_lore_delayed error: %s", e)


async def _job_lanzar_jefe_delayed(context: ContextTypes.DEFAULT_TYPE):
    """Job callback para lanzar el jefe tras el lore. Usa context.job.data = (nombre, hp, dificultad)."""
    try:
        nombre, hp, dificultad = context.job.data
        await _lanzar_jefe_tras_lore(context, nombre, hp, dificultad)
    except Exception as e:
        logger.error("_job_lanzar_jefe_delayed error: %s", e)
        _set("jefe_lore_en_curso", "0")


async def _iniciar_secuencia_jefe(context: ContextTypes.DEFAULT_TYPE, elegido: dict,
                                   dificultad: str):
    """
    Inicia la secuencia completa de lore + aparición del jefe.
    Lore 1 → ahora
    Lore 2 → +30 min
    Lore 3 → +60 min
    Lore 4 → +90 min
    Jefe   → +120 min
    """
    nombre = elegido["nombre"]
    tipo   = elegido.get("lore_tipo", "")
    hp     = _calcular_hp_jefe(dificultad)
    lores  = _obtener_lores(tipo, dificultad, nombre)

    _set("jefe_lore_en_curso", "1")
    _set("jefe_lore_inicio_ts", datetime.now().isoformat())
    logger.info("Iniciando secuencia lore+jefe: %s (%s) HP=%s", nombre, dificultad, hp)

    # Enviar los 4 mensajes de lore escalonados
    for i, msg in enumerate(lores):
        delay_seg = i * 30 * 60  # 0, 30, 60, 90 minutos
        if delay_seg == 0:
            await _enviar_lore(context, msg)
        else:
            context.job_queue.run_once(
                _job_enviar_lore_delayed,
                when=delay_seg,
                data=msg,
                name=f"lore_{nombre}_{i}"
            )

    # Lanzar el jefe 120 minutos después
    context.job_queue.run_once(
        _job_lanzar_jefe_delayed,
        when=120 * 60,
        data=(nombre, hp, dificultad),
        name=f"launch_jefe_{nombre}"
    )


# ==================== COMANDOS SUPERADMIN ====================

async def cmd_auto_estado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _es_superadmin(update.effective_user.id):
        return

    guerra  = _get("auto_guerra")
    jefe_n  = _get("auto_jefe_normal")
    jefe_d  = _get("auto_jefe_dificil")
    fn      = _get("jefe_normal_fecha")  or "no programado"
    fd      = _get("jefe_dificil_fecha") or "no programado"
    ultimo  = _get("ultimo_jefe_fecha")  or "nunca"
    lore_ac = _get("jefe_lore_en_curso") == "1"

    def emoji(v):
        return "✅ Activa" if v == "1" else "❌ Desactivada"

    texto = (
        "⚙️ *Estado de Automatizaciones*\n\n"
        f"⚔️ *Guerra diaria automática:* {emoji(guerra)}\n\n"
        f"🐉 *Jefes semanales automáticos:*\n"
        f"  • Normal:  {emoji(jefe_n)} — {fn}\n"
        f"  • Difícil: {emoji(jefe_d)} — {fd}\n"
        f"  • Último jefe lanzado: {ultimo}\n"
        f"  • Lore en curso: {'Sí ⏳' if lore_ac else 'No'}\n\n"
        "*Comandos:*\n"
        "`/auto_guerra_on` / `_off` — guerra diaria\n"
        "`/auto_jefes_on` / `_off` — ambos jefes\n"
        "`/auto_jefe_normal_on` / `_off` — solo normal\n"
        "`/auto_jefe_dificil_on` / `_off` — solo difícil\n"
        "`/auto_reprogramar_jefes` — recalcular calendario semanal"
    )
    await update.effective_message.reply_text(texto, parse_mode="Markdown")


async def cmd_auto_guerra_on(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _es_superadmin(update.effective_user.id):
        return
    _set("auto_guerra", "1")
    await update.effective_message.reply_text(
        "✅ *Guerra diaria automática ACTIVADA.*\n"
        "Se ejecutará en el próximo ciclo de 24h o puedes iniciarla manualmente con /guerra\\_facciones\\_iniciar.",
        parse_mode="Markdown"
    )

async def cmd_auto_guerra_off(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _es_superadmin(update.effective_user.id):
        return
    _set("auto_guerra", "0")
    await update.effective_message.reply_text("❌ *Guerra diaria automática DESACTIVADA.*", parse_mode="Markdown")

async def cmd_auto_jefes_on(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _es_superadmin(update.effective_user.id):
        return
    _set("auto_jefe_normal", "1")
    _set("auto_jefe_dificil", "1")
    _verificar_y_reprogramar()
    fn = _get("jefe_normal_fecha")
    fd = _get("jefe_dificil_fecha")
    await update.effective_message.reply_text(
        f"✅ *Jefes semanales ACTIVADOS.*\n\n"
        f"📅 Jefe Normal programado: *{fn}*\n"
        f"📅 Jefe Difícil programado: *{fd}*\n\n"
        f"2 horas antes del jefe comenzarán los mensajes de lore.",
        parse_mode="Markdown"
    )

async def cmd_auto_jefes_off(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _es_superadmin(update.effective_user.id):
        return
    _set("auto_jefe_normal", "0")
    _set("auto_jefe_dificil", "0")
    await update.effective_message.reply_text("❌ *Jefes semanales automáticos DESACTIVADOS.*", parse_mode="Markdown")

async def cmd_auto_jefe_normal_on(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _es_superadmin(update.effective_user.id):
        return
    _set("auto_jefe_normal", "1")
    _verificar_y_reprogramar()
    fn = _get("jefe_normal_fecha")
    await update.effective_message.reply_text(f"✅ *Jefe semanal Normal ACTIVADO.*\n📅 Fecha: *{fn}*", parse_mode="Markdown")

async def cmd_auto_jefe_normal_off(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _es_superadmin(update.effective_user.id):
        return
    _set("auto_jefe_normal", "0")
    await update.effective_message.reply_text("❌ *Jefe semanal Normal DESACTIVADO.*", parse_mode="Markdown")

async def cmd_auto_jefe_dificil_on(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _es_superadmin(update.effective_user.id):
        return
    _set("auto_jefe_dificil", "1")
    _verificar_y_reprogramar()
    fd = _get("jefe_dificil_fecha")
    await update.effective_message.reply_text(f"✅ *Jefe semanal Difícil ACTIVADO.*\n📅 Fecha: *{fd}*", parse_mode="Markdown")

async def cmd_auto_jefe_dificil_off(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _es_superadmin(update.effective_user.id):
        return
    _set("auto_jefe_dificil", "0")
    await update.effective_message.reply_text("❌ *Jefe semanal Difícil DESACTIVADO.*", parse_mode="Markdown")

async def cmd_auto_reprogramar_jefes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fuerza un recálculo del calendario semanal de jefes."""
    if not _es_superadmin(update.effective_user.id):
        return
    _programar_semana()
    fn = _get("jefe_normal_fecha")
    fd = _get("jefe_dificil_fecha")
    await update.effective_message.reply_text(
        f"🔄 *Calendario de jefes reprogramado.*\n\n"
        f"📅 Jefe Normal: *{fn}*\n"
        f"📅 Jefe Difícil: *{fd}*",
        parse_mode="Markdown"
    )


# ==================== JOBS AUTOMÁTICOS ====================

async def job_auto_guerra(context: ContextTypes.DEFAULT_TYPE):
    """Corre cada 24h. Finaliza guerra expirada y arranca una nueva si el flag está activo."""
    try:
        import guerra_facciones as gf

        guerra = gf._obtener_guerra_activa()
        if guerra:
            fecha_fin_str = guerra.get("fecha_fin")
            if fecha_fin_str:
                try:
                    fecha_fin = datetime.fromisoformat(fecha_fin_str)
                    if datetime.now() >= fecha_fin:
                        logger.info("auto_guerra: finalizando guerra expirada id=%s", guerra["id"])
                        await gf.terminar_guerra_automatica(guerra, context.bot)
                        guerra = None
                except Exception as e:
                    logger.warning("auto_guerra: error al parsear fecha_fin: %s", e)
            else:
                return

        if guerra:
            return

        if _get("auto_guerra") != "1":
            return

        guerra = gf.iniciar_guerra_automatica()
        if not guerra:
            logger.warning("auto_guerra: no se pudo crear la guerra (ya hay una activa?)")
            return

        gf._programar_fin_guerra(guerra["id"])
        logger.info("auto_guerra: guerra %s iniciada", guerra["id"])
        await gf._broadcast_inicio_guerra(context.bot, guerra)

    except Exception as e:
        logger.error("job_auto_guerra error: %s", e)


async def job_check_jefes_diario(context: ContextTypes.DEFAULT_TYPE):
    """
    Corre cada 24h. Verifica si hoy toca jefe (normal o difícil) y lanza
    la secuencia de lore + aparición si corresponde.
    Respeta la regla de mínimo 2 días entre jefes.
    """
    try:
        # Si hay lore en curso, verificar que no lleve más de 4 horas bloqueado
        if _get("jefe_lore_en_curso") == "1":
            inicio_str = _get("jefe_lore_inicio_ts")
            if inicio_str:
                try:
                    inicio_ts = datetime.fromisoformat(inicio_str)
                    if (datetime.now() - inicio_ts).total_seconds() > 4 * 3600:
                        logger.warning("job_check_jefes_diario: lore bloqueado >4h — reseteando flag.")
                        _set("jefe_lore_en_curso", "0")
                    else:
                        return
                except Exception:
                    _set("jefe_lore_en_curso", "0")
            else:
                return

        # Verificar y actualizar el calendario semanal
        _verificar_y_reprogramar()

        hoy = date.today()
        hoy_str = hoy.isoformat()

        # Respetar el gap mínimo de 2 días desde el último jefe
        ultimo_str = _get("ultimo_jefe_fecha")
        if ultimo_str:
            try:
                ultimo = date.fromisoformat(ultimo_str)
                if (hoy - ultimo).days < 3:
                    logger.info("job_check_jefes_diario: gap mínimo no cumplido (último: %s)", ultimo_str)
                    return
            except ValueError:
                pass

        fn = _get("jefe_normal_fecha")
        fd = _get("jefe_dificil_fecha")

        jefe_elegido = None
        dificultad   = None
        pool_elegido = None

        if _get("auto_jefe_normal") == "1" and fn == hoy_str:
            jefe_elegido = random.choice(JEFES_AUTO_NORMAL)
            dificultad   = "Normal"
        elif _get("auto_jefe_dificil") == "1" and fd == hoy_str:
            jefe_elegido = random.choice(JEFES_AUTO_DIFICIL)
            dificultad   = "Dificil"

        if not jefe_elegido:
            return  # Hoy no toca jefe

        logger.info("job_check_jefes_diario: lanzando %s (%s)", jefe_elegido["nombre"], dificultad)
        await _iniciar_secuencia_jefe(context, jefe_elegido, dificultad)

    except Exception as e:
        logger.error("job_check_jefes_diario error: %s", e)


# ==================== REGENERACIÓN DE HP ====================

async def job_regen_hp(context: ContextTypes.DEFAULT_TYPE):
    """
    Corre cada 90 segundos. Regenera HP a todos los jugadores que:
    - Tengan hp_actual < hp_max
    - No estén en combate o mazmorra activos
    Regen por tick: ~10% del hp_max (mínimo 2 HP).
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        # Seleccionar jugadores con vida incompleta y sin actividad de combate activa
        c.execute("""
            SELECT user_id, hp_actual, hp_max
            FROM jugadores
            WHERE hp_actual < hp_max
              AND (actividad_actual IS NULL
                   OR actividad_actual NOT IN ('combate', 'mazmorra'))
        """)
        filas = c.fetchall()
        if not filas:
            conn.close()
            return
        for user_id, hp_actual, hp_max in filas:
            if not hp_max or hp_max <= 0:
                continue
            regen = max(2, hp_max // 10)
            nuevo_hp = min(hp_max, hp_actual + regen)
            c.execute(
                "UPDATE jugadores SET hp_actual = ? WHERE user_id = ?",
                (nuevo_hp, user_id)
            )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error("job_regen_hp error: %s", e)


# ==================== REGISTRO ====================

def _limpiar_actividades_combate_al_inicio():
    """Limpia actividades 'combate' y 'mazmorra' al arrancar el bot.
    Estos combates viven en memoria y no sobreviven reinicios."""
    try:
        import sqlite3 as _sql
        conn = _sql.connect(DB_PATH)
        c = conn.cursor()
        c.execute(
            "UPDATE jugadores SET actividad_actual = NULL, actividad_expira = NULL "
            "WHERE actividad_actual IN ('combate', 'mazmorra')"
        )
        afectados = c.rowcount
        conn.commit()
        conn.close()
        if afectados:
            logger.info("Limpieza al inicio: %d actividades de combate/mazmorra eliminadas.", afectados)
    except Exception as e:
        logger.warning("Error limpiando actividades al inicio: %s", e)


# ==================== LORE DIARIO ====================

async def job_lore_diario(context: ContextTypes.DEFAULT_TYPE):
    """
    Job periódico: envía el siguiente mensaje de lore a todos los jugadores.
    Lee primero de la tabla lore_mensajes (DB); si está vacía, usa lore_diario.py.
    """
    if _get("lore_diario_activo") != "1":
        return

    # ── Obtener mensaje ──────────────────────────────────────────────────────
    try:
        indice = int(_get("lore_diario_indice") or "0")
    except ValueError:
        indice = 0

    mensaje = None

    # 1) Intentar leer de la tabla lore_mensajes (preferido)
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM lore_mensajes")
        total_db = c.fetchone()[0]
        conn.close()

        if total_db > 0:
            indice_db = indice % total_db
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute(
                "SELECT texto FROM lore_mensajes ORDER BY orden ASC LIMIT 1 OFFSET ?",
                (indice_db,)
            )
            row = c.fetchone()
            conn.close()
            if row:
                mensaje = row["texto"]
                _set("lore_diario_indice", str((indice + 1) % total_db))
    except Exception as e:
        logger.warning(f"Error leyendo lore_mensajes DB: {e}")

    # 2) Fallback: lista Python en lore_diario.py
    if mensaje is None:
        try:
            from lore_diario import LORE_MENSAJES
            if LORE_MENSAJES:
                indice_py = indice % len(LORE_MENSAJES)
                mensaje = LORE_MENSAJES[indice_py]
                _set("lore_diario_indice", str((indice + 1) % len(LORE_MENSAJES)))
        except ImportError:
            logger.warning("lore_diario.py no encontrado — job omitido.")
            return

    if mensaje is None:
        logger.warning("No hay mensajes de lore disponibles.")
        return

    # ── Enviar a todos los jugadores ─────────────────────────────────────────
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT user_id FROM jugadores WHERE baneado = 0")
    jugadores = [r["user_id"] for r in c.fetchall()]
    conn.close()

    enviados = 0
    for uid in jugadores:
        try:
            await context.bot.send_message(
                chat_id=uid,
                text=mensaje,
                parse_mode="HTML"
            )
            enviados += 1
        except Exception:
            pass

    logger.info(f"Lore diario enviado a {enviados} jugadores (índice {indice}).")


# ==================== PANEL DE AUTOMATIZACIONES ====================

def _auto_premios_estado() -> str:
    """Lee el estado de auto_premios_activo desde config_bot."""
    try:
        import db_helper as _dbh
        return _dbh.obtener_config("auto_premios_activo") or "0"
    except Exception:
        return "0"


def _auto_premios_toggle():
    """Alterna auto_premios_activo en config_bot."""
    try:
        import db_helper as _dbh
        actual = _dbh.obtener_config("auto_premios_activo") or "0"
        _dbh.establecer_config("auto_premios_activo", "0" if actual == "1" else "1")
    except Exception:
        pass


_PANEL_ITEMS = [
    # (clave, etiqueta, tabla)  tabla: "auto" = automatizaciones_config, "bot" = config_bot
    # ── Sistemas originales ──────────────────────────────────────────────────
    ("lore_diario_activo",  "📖 Lore Diario (20:00 BR)",       "auto"),
    ("auto_jefe_normal",    "⚔️ Jefe Auto Normal (semanal)",    "auto"),
    ("auto_jefe_dificil",   "💀 Jefe Auto Difícil (semanal)",   "auto"),
    ("auto_guerra",         "🏹 Guerra Facciones (diaria)",     "auto"),
    ("gg_sin_aprobacion",   "🤝 G.Gremios sin aprobación",      "auto"),
    ("auto_premios_activo", "🎁 Auto-Premios Especiales",        "bot"),
    # ── Nuevos sistemas de jugabilidad ───────────────────────────────────────
    ("login_diario_activo",    "🗓️ Login Diario + Racha",        "bot"),
    ("misiones_diarias_activo","📋 Misiones Diarias Rotativas",  "bot"),
    ("gchat_activo",           "💬 Chat de Gremio (/gchat)",     "bot"),
    ("resumen_sesion_activo",  "📊 Resumen de Sesión (al regresar)", "bot"),
    ("zona_activa_activo",     "👥 Jugadores Activos en Zona",   "bot"),
    ("stamina_notif_activo",   "⚡ Notif. Stamina Llena",        "bot"),
    ("cooldown_info_activo",   "⏱️ Panel de Cooldowns (/cd)",    "bot"),
    ("item_comparar_activo",   "🔍 Comparar Item al Recoger",    "bot"),
    ("anuncio_jefe_activo",    "📢 Anuncio Global Kill de Jefe", "bot"),
    # ── Mejoras de rendimiento (on/off) ─────────────────────────────────────
    ("throttle_antispam_activo", "🛡️ Anti-Spam Throttle (1.5s)",  "bot"),
    ("rate_limiter_activo",    "📉 Rate Limiter Telegram (25/s)", "bot"),
]


def _paut_get(clave: str, tabla: str) -> str:
    if tabla == "bot":
        return _auto_premios_estado()
    return _get(clave)


def _paut_set(clave: str, tabla: str):
    if tabla == "bot":
        _auto_premios_toggle()
    else:
        _set(clave, "0" if _get(clave) == "1" else "1")


def _texto_panel_auto() -> str:
    lineas = ["⚙️ <b>PANEL DE AUTOMATIZACIONES</b>\n"]
    for clave, etiqueta, tabla in _PANEL_ITEMS:
        val = _paut_get(clave, tabla)
        icono = "🟢" if val == "1" else "🔴"
        lineas.append(f"{icono} {etiqueta}")
    lineas.append("\nPulsa un botón para activar/desactivar:")
    return "\n".join(lineas)


def _teclado_panel_auto():
    kb = []
    for clave, etiqueta, tabla in _PANEL_ITEMS:
        val = _paut_get(clave, tabla)
        accion = "Desactivar" if val == "1" else "Activar"
        kb.append([InlineKeyboardButton(
            f"{etiqueta} — {accion}",
            callback_data=f"paut_tgl_{clave}"
        )])
    kb.append([InlineKeyboardButton("❌ Cerrar", callback_data="paut_cerrar")])
    return InlineKeyboardMarkup(kb)


async def cmd_panel_auto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Panel unificado de automatizaciones (solo superadmin)."""
    user_id = update.effective_user.id
    if not _es_superadmin(user_id):
        await update.message.reply_text("⛔ Solo el superadmin puede usar este panel.")
        return
    await update.message.reply_text(
        _texto_panel_auto(),
        parse_mode="HTML",
        reply_markup=_teclado_panel_auto()
    )


async def cb_panel_auto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja los botones del panel de automatizaciones."""
    query = update.callback_query
    user_id = query.from_user.id
    if not _es_superadmin(user_id):
        await query.answer("⛔ Sin permiso.", show_alert=True)
        return
    await query.answer()
    data = query.data
    if data == "paut_cerrar":
        await query.edit_message_text("✅ Panel de automatizaciones cerrado.")
        return
    if data == "paut_ver":
        try:
            await query.edit_message_text(
                _texto_panel_auto(),
                parse_mode="HTML",
                reply_markup=_teclado_panel_auto()
            )
        except Exception:
            pass
        return
    if data.startswith("paut_tgl_"):
        clave = data[len("paut_tgl_"):]
        tabla = next((t for c, _, t in _PANEL_ITEMS if c == clave), None)
        if tabla is None:
            await query.answer("❌ Clave desconocida.", show_alert=True)
            return
        _paut_set(clave, tabla)
        try:
            await query.edit_message_text(
                _texto_panel_auto(),
                parse_mode="HTML",
                reply_markup=_teclado_panel_auto()
            )
        except Exception:
            pass
        return


def registrar_handlers(app):
    _limpiar_actividades_combate_al_inicio()
    app.add_handler(CommandHandler("auto_estado",              cmd_auto_estado))
    app.add_handler(CommandHandler("auto_guerra_on",           cmd_auto_guerra_on))
    app.add_handler(CommandHandler("auto_guerra_off",          cmd_auto_guerra_off))
    app.add_handler(CommandHandler("auto_jefes_on",            cmd_auto_jefes_on))
    app.add_handler(CommandHandler("auto_jefes_off",           cmd_auto_jefes_off))
    app.add_handler(CommandHandler("auto_jefe_normal_on",      cmd_auto_jefe_normal_on))
    app.add_handler(CommandHandler("auto_jefe_normal_off",     cmd_auto_jefe_normal_off))
    app.add_handler(CommandHandler("auto_jefe_dificil_on",     cmd_auto_jefe_dificil_on))
    app.add_handler(CommandHandler("auto_jefe_dificil_off",    cmd_auto_jefe_dificil_off))
    app.add_handler(CommandHandler("auto_reprogramar_jefes",   cmd_auto_reprogramar_jefes))
    app.add_handler(CommandHandler("panel_auto",               cmd_panel_auto))
    app.add_handler(CallbackQueryHandler(cb_panel_auto,        pattern="^paut_"))
    # Job de lore diario a las 23:00 UTC (20:00 Brasil/São Paulo, UTC-3)
    import datetime as _dt
    app.job_queue.run_daily(
        job_lore_diario,
        time=_dt.time(23, 0, 0, tzinfo=_dt.timezone.utc),
        name="lore_diario"
    )

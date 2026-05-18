#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lore_init.py — Inicializa la tabla lore_mensajes en la BD y la pobla con 3650+
mensajes únicos de lore para el sistema de Lore Diario de Aethelgard.

Ejecutar una sola vez:  python3 lore_init.py
Es idempotente: si ya hay ≥3650 mensajes no hace nada.
"""

import sqlite3
import random

DB_PATH = "aethelgard.db"

# ═══════════════════════════════════════════════════════════════════════════════
# POOLS DE DATOS — Aethelgard lore universe
# ═══════════════════════════════════════════════════════════════════════════════

# ── PERSONAJES HEROICOS ──────────────────────────────────────────────────────

HEROES = [
    {
        "nombre": "Valdric el Indomable", "faccion": "Alianza", "clase": "Vanguardista",
        "era": "Clásica", "origen": "Thornbrook",
        "entradas": [
            ("Orígenes",
             "Valdric nació en Thornbrook, un pueblo de mineros que desapareció durante el Invierno de Cien Años. Tenía siete años cuando las nieves se llevaron a su familia y aprendió que la supervivencia no era un derecho sino una elección.",
             "De ese frío surgió algo que ni el fuego ni el acero pudieron doblar jamás. <i>«La comodidad cría soldados. El dolor cría guerreros»</i>, decía cuando alguien le preguntaba por sus comienzos."),
            ("Primera batalla",
             "Su primera batalla real fue en el Paso de Vorheim, defendiendo una caravana de refugiados contra bandidos a sueldo del Imperio. Tenía dieciséis años y una espada que le quedaba grande. Ganó.",
             "Los bandidos contaron después que no les dio miedo el muchacho sino sus ojos. Ojos que ya habían visto demasiado para asustarse de ellos."),
            ("Mayor victoria",
             "La victoria que lo hizo leyenda fue el Sitio de la Muralla Gris, donde con ochocientos soldados mantuvo a raya a cuatro mil imperiales durante tres semanas hasta que llegaron los refuerzos.",
             "Cuando los cronistas le preguntaron su estrategia, respondió: <i>«No había estrategia. Solo había hombres que no querían morir inútilmente.»</i>"),
            ("Su secreto",
             "Lo que ningún registro oficial menciona: Valdric sufrió durante toda su vida de pesadillas en las que revivía el Invierno. Sus escuderos contaban que a veces, en mitad de la noche, lo encontraban despierto mirando por la ventana.",
             "Nunca habló de eso con nadie. Era parte del código de alguien que había construido su identidad sobre no necesitar nada de nadie."),
            ("Relación con el Sindicato",
             "Valdric toleraba al Sindicato con la misma ecuanimidad con que toleraba el invierno: era una fuerza del mundo con la que convivir, no combatir. Había pagado sus servicios en tres ocasiones y siempre habían cumplido.",
             "<i>«El Sindicato no tiene honor. Tiene algo más útil: coherencia. Siempre hacen exactamente lo que dicen que van a hacer.»</i>"),
            ("Legado",
             "La técnica de combate que Valdric desarrolló en treinta años de experiencia se llama hoy La Forma Indomable y se enseña en todas las academias de la Alianza. Él nunca la nombró; fue un discípulo quien le dio el nombre.",
             "Murió en cama a los setenta y dos años, cosa que siempre consideró una ironía digna de los dioses. <i>«Sobreviví todo eso para morirme durmiendo.»</i>"),
            ("Lo que los bardos omiten",
             "Los bardos cantan sobre sus victorias. Nadie canta sobre las noches que pasó negociando la rendición de enemigos para no tener que matarlos, ni sobre las veces que detuvo a sus propios hombres cuando la victoria ya estaba ganada.",
             "Valdric creía que la medida de un guerrero no era cuántos enemigos mataba sino cuántos podía elegir no matar. No es el tipo de cosa que rima bien en una canción."),
        ]
    },
    {
        "nombre": "Seira la Tejedora", "faccion": "Sindicato", "clase": "Tejehechizos",
        "era": "Reciente", "origen": "Puertos del Este",
        "entradas": [
            ("Orígenes",
             "Seira creció en los muelles de los Puertos del Este, donde aprendió que la información valía más que el oro y que la magia era simplemente información aplicada. Su primer hechizo no fue de fuego ni de hielo sino de camuflaje.",
             "El Sindicato la reclutó cuando tenía quince años, después de que descubriera que llevaba seis meses trabajando para ellos sin saberlo. Consideraron eso mérito suficiente."),
            ("Metodología",
             "Seira nunca usó la magia para el combate directo si podía evitarlo. Prefería alterar las condiciones del combate: cambiar la visibilidad, modificar la acústica, crear ilusiones que redirigían la atención exactamente donde no debía estar.",
             "<i>«La magia más poderosa que existe es la que nadie ve venir. La segunda más poderosa es la que nadie puede probar que usaste.»</i>"),
            ("Mayor logro",
             "Se atribuye a Seira, aunque nunca fue confirmado oficialmente, el colapso silencioso de tres redes de espionaje del Imperio en un período de dos años. Cada red creyó que las otras la habían traicionado.",
             "Nadie supo de dónde venían las filtraciones. Seira estaba en otro continente cuando todo ocurrió, lo cual era, por supuesto, exactamente el plan."),
            ("Su precio",
             "El Sindicato cobra por sus servicios. Seira también. Su tarifa era inusual: no pedía oro sino favores específicos, cuidadosamente seleccionados, que podían ser llamados en cualquier momento del futuro.",
             "A los cuarenta años, Seira tenía favores pendientes de tres reyes, dos archivistas de la Biblioteca de Thornwall y el comandante general de la Alianza. Era, en términos prácticos, la persona más poderosa de Aethelgard."),
            ("Relación con la Alianza",
             "La Alianza la necesitaba y la desconfiaba en igual medida. La usaban cuando no había otra opción y vigilaban cada paso cuando lo hacían. Seira encontraba esto completamente razonable.",
             "<i>«Prefiero que desconfíen de mí. Quienes confían completamente dejan de vigilar, y quienes dejan de vigilar pierden información valiosa sobre mis movimientos.»</i>"),
            ("Legado",
             "Seira retiró sus servicios activos a los cincuenta y tres años y desapareció. El Sindicato tiene un archivo sellado sobre su paradero actual que muy pocas personas tienen autorización para ver.",
             "Los nuevos agentes del Sindicato estudian sus casos como ejemplos de metodología. El caso más estudiado es uno que nadie sabe que fue ella: todavía hoy parece un accidente."),
            ("Lo que pocos saben",
             "Seira mantuvo durante veinte años correspondencia secreta con una maestra de la Academia de la Alianza, su mayor rivale filosófica. Las cartas, descubiertas después de la muerte de ambas, muestran una amistad profunda y un respeto mutuo genuino.",
             "La ironía que a ambas les hubiera gustado: sus ideas sobre magia, destiladas en esas cartas, son hoy la base del currículo de todas las academias de las tres facciones."),
        ]
    },
    {
        "nombre": "Corvan el Justo", "faccion": "Alianza", "clase": "Acechante",
        "era": "Antigua", "origen": "Cidaris",
        "entradas": [
            ("Orígenes",
             "Corvan nació en Cidaris en el período que los historiadores llaman la Era de la Expansión, cuando la Alianza crecía tan rápido que sus fronteras no sabían dónde terminaban. Era el tercer hijo de un comerciante mediano, lo cual significaba libertad: sin herencia que defender, podía ir donde quisiera.",
             "Lo que quería era entender por qué el mundo funcionaba como funcionaba. Esa pregunta lo llevó, a través de un camino que nadie podría haber predicho, a convertirse en el mejor investigador que la Alianza produjo en ese siglo."),
            ("Primera investigación",
             "Su primera investigación real fue el caso de los cristales adulterados en los mercados de Cidaris. Alguien estaba vendiendo Eternium diluido a precio de Eternium puro. Corvan lo resolvió en tres días siguiendo el rastro del dinero.",
             "El culpable era el jefe de la guardia local. Lo que Corvan aprendió: el crimen raramente viene de donde uno espera y casi siempre de donde menos se quiere mirar."),
            ("Filosofía",
             "Corvan creía que la justicia era una práctica, no un concepto. No una idea que existía en libros sino algo que debía construirse activamente en cada decisión, cada día, contra la entropía natural del mundo hacia el abuso.",
             "<i>«La injusticia no necesita esfuerzo. Existe sola. La justicia requiere trabajo constante. Por eso siempre estamos perdiendo terreno, y por eso nunca podemos dejar de pelear.»</i>"),
            ("Mayor caso",
             "El caso que definió su carrera tardó siete años en resolverse: la desaparición de cuatrocientas familias de un sector fronterizo de la Alianza, reemplazadas silenciosamente por agentes del Imperio. Corvan lo resolvió solo, sin apoyo oficial, porque los oficiales estaban implicados.",
             "Las cuatrocientas familias habían sido relocalizadas en comunidades Imperio, viviendo vidas completamente nuevas. A su pedido, se les dio la opción de regresar. Tres cuartas partes eligieron quedarse. Corvan registró esto como la parte más complicada de su vida."),
            ("Límites",
             "Había cosas que Corvan no haría aunque la situación lo requiriera. No torturaba. No engañaba a inocentes. No sacrificaba a individuos por el bien colectivo. Sus superiores consideraban esto un defecto.",
             "Corvan consideraba que sus superiores confundían eficiencia con justicia. Era capaz de hacer una cosa o la otra. Elegía la segunda porque la primera, sin la segunda, no valía nada."),
            ("Relación con el Sindicato",
             "Corvan y el Sindicato tenían una relación de respeto profesional frío. Él sabía que hacían cosas que él nunca haría. Ellos sabían que él sabía. Ninguno de los dos fingía que eso no era cierto.",
             "Hubo dos ocasiones en que colaboraron en un objetivo común. En ambas, el resultado fue satisfactorio para todos. En ambas, cada parte vigiló a la otra cuidadosamente durante todo el proceso."),
            ("Legado",
             "Corvan murió con setenta años y dejó un archivo de casos que la Alianza clasifica hasta hoy. No porque los casos sean secretos, sino porque revelan demasiado sobre las instituciones de la Alianza misma.",
             "Su única publicación fue un tratado de treinta páginas sobre metodología investigativa. Es el documento no oficial más copiado en la historia de la Alianza. Los estudiantes lo llaman simplemente <i>El Método de Corvan</i>."),
        ]
    },
    {
        "nombre": "Lyria Ceniza", "faccion": "Alianza", "clase": "Tejehechizos",
        "era": "Reciente", "origen": "Valle de las Cenizas",
        "entradas": [
            ("Orígenes",
             "Lyria nació en el Valle de las Cenizas, que tomó su nombre de la erupción volcánica que lo formó tres siglos antes. Creció rodeada de suelo negro y plantas que crecían de lo que otros descartaban como destrucción.",
             "Aprendió magia sola, de libros robados de mercaderes que pasaban por el Valle. Cuando llegó a la Academia de la Alianza a los dieciséis años, ya sabía más que la mitad de sus instructores."),
            ("Especialidad",
             "Lyria se especializó en lo que los académicos llamaban magia de transformación: no crear cosas de la nada sino cambiar fundamentalmente la naturaleza de lo que ya existía. Podía convertir veneno en medicina, fuego en luz, oscuridad en información.",
             "Su instructora favorita decía que Lyria no era una maga sino una alquimista del alma. Lyria tomó esto como el mayor elogio que recibió en su vida."),
            ("Crisis de fe",
             "A los veintiocho años, Lyria descubrió que un hechizo que había desarrollado para curar heridas de batalla también podía, con una modificación mínima, causar daño interno sin dejar marcas. Pasó un año sin practicar magia.",
             "La crisis la resolvió su mentora con una frase que cambió su perspectiva: <i>«Todo conocimiento puede usarse para bien o para mal. La pregunta no es qué puede hacer el conocimiento sino qué decides hacer tú con él.»</i>"),
            ("Mayor logro",
             "Lyria desarrolló el Protocolo de Transformación Inversa, un sistema de hechizos que podía deshacer el daño de la magia corrupta. Fue el único método efectivo contra la plaga mágica que golpeó los territorios del norte hace quince años.",
             "Salvó aproximadamente doce mil personas. Nunca habló en público de esto. El Archivo de la Alianza tiene un registro detallado de cada caso que prefiere mantener discreto."),
            ("Vida personal",
             "Lyria nunca formó un hogar estable. Viajaba constantemente, siguiendo los problemas a medida que surgían. Sus colegas consideraban esto sacrificio. Ella lo consideraba privilegio.",
             "<i>«No tengo un hogar porque tengo todos los hogares. Cada lugar al que llego y donde puedo ayudar es mío por un tiempo. Eso me parece mejor negocio que uno solo para siempre.»</i>"),
            ("Relación con el Imperio",
             "Con el Imperio tenía la relación más complicada de su vida: su magia había sido usada por ellos sin su consentimiento en dos ocasiones, y en ambas ocasiones les había funcionado. Nunca les perdonó la primera. Entendió la segunda.",
             "El Imperio la respetaba exactamente en la medida en que la temía. Lyria consideraba que ese era el equilibrio correcto."),
            ("Desaparición",
             "Lyria desapareció a los sesenta y un años durante una expedición a la Mazmorra Negra. No hay cuerpo. No hay registro de lo que encontró allí. El único rastro es una nota que dejó en su cuartel que decía: <i>«Si no regreso, es porque encontré algo que vale más que regresar.»</i>",
             "La Academia de la Alianza la declara desaparecida, no muerta. Hay quienes la buscan todavía."),
        ]
    },
    {
        "nombre": "Drenok el Roto", "faccion": "Imperio", "clase": "Vanguardista",
        "era": "Clásica", "origen": "Fortaleza Krath",
        "entradas": [
            ("Orígenes",
             "Drenok nació en la Fortaleza Krath, una instalación militar del Imperio donde su madre era herrera y su padre instructor de recrutas. Crecer entre soldados le enseñó que el poder era una herramienta y que las herramientas no eran ni buenas ni malas.",
             "Lo que lo formó no fue la fortaleza sino lo que había fuera de ella: los pueblos que las fuerzas del Imperio «pacificaban». Drenok vio esto de cerca demasiadas veces y demasiado joven."),
            ("El quiebre",
             "Drenok tenía veintitrés años cuando recibió la orden de quemar una aldea que supuestamente albergaba espías de la Alianza. La inteligencia era incorrecta. Él lo sabía. Sus superiores no querían saber.",
             "Cumplió la orden. Esto lo rompió de una manera que no admitió durante diez años. Cuando finalmente lo admitió, ya había pasado una década construyendo algo para compensar. No porque creyera que se podía compensar, sino porque necesitaba intentarlo."),
            ("Redención",
             "Drenok usó su posición en el Imperio para proteger a comunidades que de otro modo habrían sido destruidas. Desviaba órdenes, falsificaba reportes, creaba pretextos burocráticos. Salvó más de lo que destruyó, aunque esta aritmética nunca le pareció suficiente.",
             "<i>«No soy un buen hombre que hizo cosas malas. Soy un hombre malo que decidió intentar ser otra cosa. La diferencia importa.»</i>"),
            ("Habilidades",
             "En combate, Drenok era devastador: la formación del Imperio combinada con treinta años de experiencia real. Lo que lo hacía diferente no era su fuerza sino su capacidad de leer una situación y detener el combate antes de que se volviera catastrófico.",
             "Sus superiores valoraban su efectividad. Sus subordinados lo valoraban por otra razón: con Drenok al mando, la probabilidad de sobrevivir era estadísticamente superior."),
            ("Relación con la Alianza",
             "La Alianza lo consideraba un criminal de guerra. Él no discutía esa clasificación. También había salvado a ciudadanos de la Alianza en tres ocasiones documentadas y en varias que prefirió no documentar.",
             "El comandante de la Alianza que intentó arrestarlo en una frontera neutral terminó escoltándolo de vuelta a territorio Imperial después de una conversación de dos horas. Nadie supo nunca qué se dijeron."),
            ("Final de carrera",
             "Drenok se retiró del servicio activo a los cincuenta y ocho años y fundó una escuela de combate en una ciudad neutral. Aceptaba estudiantes de las tres facciones. Enseñaba a pelear y, más importante, a elegir cuándo hacerlo.",
             "Murió con sus botas puestas, como siempre había dicho que quería: en un duelo a los sesenta y cuatro años, contra alguien que había venido específicamente a matarlo por algo que hizo décadas atrás. Ganó el duelo. Murió de las heridas tres días después."),
            ("Legado paradójico",
             "Drenok es recordado de formas completamente diferentes según quién lo recuerde. Para el Imperio: un general capaz con algunos excesos ideológicos. Para la Alianza: un criminal con destellos de humanidad. Para quienes le debían la vida: algo que no cabe en categorías.",
             "Su escuela de combate sigue abierta. El instructor actual encontró entre los papeles de Drenok una nota que nunca compartió públicamente. Solo dijo que cambiaba todo lo que había creído sobre su maestro."),
        ]
    },
    {
        "nombre": "Mira de las Sombras", "faccion": "Sindicato", "clase": "Acechante",
        "era": "Reciente", "origen": "Desconocido",
        "entradas": [
            ("Sin origen conocido",
             "El Sindicato tiene registros de Mira que comienzan hace dieciséis años, cuando apareció en su sede principal de los Puertos del Este con información que no debería haber podido obtener y una propuesta de empleo.",
             "Nadie sabe su nombre real. Nadie sabe de dónde viene. El Sindicato hizo verificaciones exhaustivas durante seis meses antes de aceptar su propuesta. Las verificaciones no encontraron nada que no quisiera que encontraran."),
            ("Metodología",
             "Mira no usa violencia a menos que no haya alternativa. Su herramienta primaria es la información: tenerla antes que los demás, saber qué hacer con ella y cuándo. Sus misiones tienen una tasa de éxito del noventa y cuatro por ciento.",
             "El seis por ciento restante no son fracasos, son misiones que decidió no completar por razones que nunca explicó completamente. El Sindicato acepta esto porque los resultados del noventa y cuatro por ciento justifican la tolerancia."),
            ("Límites desconocidos",
             "A diferencia de la mayoría de los agentes del Sindicato, Mira tiene límites que nunca cruzó y que nadie conoce completamente. Se negó a dos misiones en su carrera. En ambos casos, el Sindicato encontró la forma de cumplir los objetivos de otra manera.",
             "Lo que esas dos misiones tenían en común, si es que tenían algo en común, es información que el Sindicato prefiere no compartir con nadie que no necesite saberlo."),
            ("Rumores",
             "Los rumores sobre Mira en los mercados de información de Aethelgard son contradictorios: que es una noble de la Alianza disfrazada, que es una ex-agente del Imperio que cambió de bando, que no es humana, que es tres personas diferentes.",
             "Mira no comenta los rumores. Según algunas fuentes, ocasionalmente los alimenta cuando le resultan útiles."),
            ("Relación con el Imperio",
             "El Imperio tiene un expediente sobre Mira que es uno de sus más gruesos y menos completos. Saben que existe, que trabaja para el Sindicato y aproximadamente el diez por ciento de lo que ha hecho.",
             "En tres ocasiones intentaron capturarla. En las tres, Mira se enteró del plan antes de que comenzara. El expediente del Imperio registra los tres fracasos sin poder explicar ninguno."),
            ("Lo que hace con el dinero",
             "Mira cobra bien y gasta poco. Lo que hace con su dinero es uno de los pocos misterios que el Sindicato no ha podido resolver sobre ella, y que por razones de política institucional prefieren no investigar demasiado.",
             "Una agente junior que la siguió un día libre encontró que había estado pasando el tiempo enseñando lectura a niños en un barrio pobre. La agente junior decidió no incluir esto en su reporte. Mira lo supo de todas formas."),
            ("Futuro desconocido",
             "Mira sigue activa. A diferencia de la mayoría de los agentes que eventualmente se retiran, establecen familias o simplemente desaparecen, ella continúa. El Sindicato no pregunta por qué. Algunos sugieren que no preguntan porque temen la respuesta.",
             "<i>Hay personas que el mundo necesita que existan, aunque nadie sepa exactamente para qué. Mira podría ser una de esas personas. O podría ser algo completamente distinto.</i>"),
        ]
    },
    {
        "nombre": "Theron el Arquitecto", "faccion": "Imperio", "clase": "Tejehechizos",
        "era": "Antigua", "origen": "Capital Imperial",
        "entradas": [
            ("Genio de la Capital",
             "Theron fue el único hijo de una familia de funcionarios imperiales y heredó de ellos no la ambición política sino la capacidad de ver sistemas donde otros veían caos. A los doce años, reorganizó el sistema de distribución de agua de un barrio completo sin que nadie le pidiera que lo hiciera.",
             "El Imperio reconoció su talento a los dieciséis y lo incorporó como aprendiz en la División de Infraestructura Mágica. En seis años era el director."),
            ("La Gran Muralla Mágica",
             "La obra que define a Theron es la Red de Barreras Mágicas del Imperio: un sistema interconectado de puntos de control que cubre las fronteras imperiales y puede detectar intrusiones mágicas en tiempo real.",
             "Tardó doce años en construirla. Requirió coordinar a trescientos magos en cuarenta ubicaciones distintas. Funciona, con actualizaciones mínimas, hasta el día de hoy."),
            ("Filosofía de diseño",
             "Theron creía que la magia, como la arquitectura, debía servir a la gente que la habitaba, no al revés. Sus diseños priorizaban la facilidad de uso, la mantenibilidad y, sobre todo, la capacidad de ser reparados por alguien que no fuera él.",
             "<i>«Un sistema que solo yo puedo mantener no es un logro. Es una dependencia. Lo que construyo debe poder sobrevivir mi muerte.»</i>"),
            ("Relación con la Alianza",
             "La Alianza intentó contratar a Theron en siete ocasiones. En todas respondió lo mismo: apreciaba la oferta, comprendía las motivaciones, y no era posible porque su trabajo estaba en el Imperio.",
             "Lo que nunca explicó era la razón real: Theron creía que el Imperio, con todos sus defectos, era el Estado más capaz de implementar y mantener infraestructura a escala. La Alianza era demasiado descentralizada para lo que él quería construir."),
            ("El proyecto inacabado",
             "Theron murió a los sesenta y siete años con un proyecto en mitad de desarrollo: una red de comunicación mágica que hubiera permitido transmitir mensajes entre ciudades en segundos. Sus notas existen pero son parciales.",
             "Cada cinco años, un equipo del Imperio intenta retomar el proyecto. Hasta ahora, nadie ha podido entender completamente su arquitectura subyacente. Algunos lo llaman humildad del genio; otros lo llaman documentación deficiente."),
            ("Controversia final",
             "El último año de su vida, Theron publicó un análisis que demostraba que la Red de Barreras Mágicas del Imperio tenía una vulnerabilidad específica. El Imperio clasificó el documento inmediatamente.",
             "Lo que nadie sabe: había enviado copias selladas a la Alianza y al Sindicato, con instrucciones de abrirlas solo si el Imperio usaba la Red para atacar civiles. Las copias siguen selladas. El Imperio vigila los sellos sin saber que sabe."),
            ("Legado de piedra y luz",
             "Los edificios que Theron diseñó con componentes mágicos integrados se reconocen a primera vista: tienen una luminosidad interna sutil que viene de cristales de Eternium de baja concentración integrados en los materiales de construcción.",
             "Se estima que treinta por ciento de los edificios en las ciudades mayores del Imperio fueron construidos o modificados según sus principios. Cuando alguien pregunta quién diseñó la infraestructura del Imperio moderno, la respuesta correcta es: Theron. La respuesta oficial es más complicada."),
        ]
    },
    {
        "nombre": "Zara la Nómada", "faccion": "Sindicato", "clase": "Maestra de Caza",
        "era": "Reciente", "origen": "Las Estepas del Norte",
        "entradas": [
            ("Hija de las Estepas",
             "Zara creció en las Estepas del Norte, territorio que no pertenece a ninguna facción y donde las únicas reglas son las que dicta el entorno. Aprendió a rastrear antes de aprender a leer, y las dos habilidades le parecían igualmente esenciales.",
             "El Sindicato la encontró cuando tenía diecinueve años persiguiendo a un agente que había robado información en las Estepas. Zara lo había rastreado durante cien kilómetros sin perder el rastro. El Sindicato le ofreció trabajo en el camino."),
            ("Arte del rastreo",
             "Zara podía rastrear a una persona en cualquier terreno. En la ciudad, seguía patrones de comportamiento y hábitos. En el bosque, pisadas y rastros de olores. En el desierto, perturbaciones en la arena que otros no podían ver.",
             "<i>«Todo el mundo deja rastros. La pregunta es si quien los sigue tiene la paciencia para leerlos. Yo tengo la paciencia.»</i>"),
            ("El caso de los Tres Generales",
             "Su caso más famoso fue encontrar a tres generales del Imperio que habían desertado con información clasificada. Los tres habían tomado rutas diferentes con identidades diferentes. Los tres fueron localizados en ocho días.",
             "El Sindicato nunca reveló cómo Zara los encontró. Ella tampoco. Los generales, cuando les preguntaron, dijeron que fue como si ella hubiera sabido desde el principio dónde iban a estar."),
            ("Relación con la naturaleza",
             "Zara mantenía una filosofía inusual para alguien del Sindicato: respetaba profundamente los ecosistemas en que operaba. Nunca rastreaba en formas que causaran daño ambiental. Nunca mataba más de lo necesario.",
             "Sus colegas del Sindicato encontraban esto excéntrico. Sus objetivos lo encontraban aterrador: una cazadora que respetaba su entorno era una cazadora que entendía exactamente lo que hacía."),
            ("Límites profesionales",
             "Zara no localizaba niños. No rastreaba personas que huían de abusadores. Nunca justificó estas restricciones en términos morales, simplemente las tenía y el Sindicato las aceptó porque su efectividad en todos los demás casos era excepcional.",
             "Hubo un cliente que intentó hacerla romper estas reglas. Zara devolvió el pago anticipado y publicó los detalles del contrato en tres mercados de información. El cliente tuvo que abandonar tres ciudades en una semana."),
            ("Vida en movimiento",
             "Zara nunca vivió en ningún lugar más de tres meses. Mantenía depósitos de suministros en veintitrés ubicaciones distintas a lo largo de Aethelgard. Tenía relaciones en muchas ciudades pero ninguna que requiriera que se quedara.",
             "Cuando alguien le preguntaba si no extrañaba tener un hogar, respondía que el movimiento era su hogar. Las Estepas del Norte le habían enseñado que el horizonte siempre tenía algo mejor que el lugar donde uno ya estaba."),
            ("Conocimiento único",
             "Zara conocía Aethelgard mejor que cualquier cartógrafo. No los mapas oficiales sino el terreno real: los atajos, los pasos estacionales, los peligros que los mapas no marcaban porque los cartógrafos que los encontraron no regresaron.",
             "Antes de cada misión importante del Sindicato que implicara movimiento de tropas o recursos, consultaban con Zara. Su información de ruta tenía un valor que el Sindicato no podía comprar en ningún otro lugar."),
        ]
    },
    {
        "nombre": "Brennan el Sabio", "faccion": "Alianza", "clase": "Tejehechizos",
        "era": "Antigua", "origen": "Academia de Crystalhaven",
        "entradas": [
            ("El erudito que nunca paró",
             "Brennan pasó setenta y dos años estudiando y treinta y uno escribiendo lo que había aprendido. A los ochenta años seguía tomando notas. Sus discípulos decían que su mente era como la Mazmorra Azul: siempre había un pasaje nuevo que explorar.",
             "Nunca buscó poder político ni riqueza. Quería entender, y cualquier otro objetivo le parecía una distracción del único objetivo que valía."),
            ("El gran catálogo",
             "La obra de su vida fue el Gran Catálogo de Fenómenos Mágicos de Aethelgard: doce volúmenes que documentaban y clasificaban cada tipo de evento mágico conocido. Tardó cuarenta años en completarlo.",
             "El Catálogo es hoy el documento de referencia primario de todas las academias de magia en las tres facciones. Es también el documento académico más rebatido: Brennan tenía teorías polémicas que siguen generando debate."),
            ("La teoría del Origen",
             "La teoría más controversial de Brennan: que la magia de Aethelgard no viene de los magos sino de Aethelgard mismo. Los magos no generan magia, la canalizan desde el mundo, que es en sí mismo una entidad mágica con propósitos que los humanos apenas empiezan a comprender.",
             "La mayoría de sus contemporáneos rechazaron la teoría. Dos generaciones después, el consenso académico la considera probablemente correcta. Brennan no vivió para verlo, pero probablemente lo hubiera encontrado satisfactorio."),
            ("Relación con las mazmorras",
             "Brennan visitó las cuatro mazmorras principales en distintos momentos de su vida, siempre con grupos de investigación y siempre como observador, no como combatiente. Sus observaciones sobre las mazmorras son los registros académicos más detallados que existen.",
             "Sobre la Mazmorra Negra escribió solo media página, lo cual para Brennan era el equivalente de no escribir nada. La nota al pie decía: <i>«Hay fenómenos para los que el lenguaje humano todavía no tiene palabras.»</i>"),
            ("El error que reconoció",
             "A los sesenta y cinco años, Brennan publicó una corrección de treinta páginas a una conclusión importante de su Gran Catálogo que había estado equivocada desde el principio. Muchos académicos consideraban que nadie se habría dado cuenta.",
             "Brennan consideraba que eso era exactamente el problema. La ciencia que nadie puede refutar no es ciencia sino dogma. La corrección fue uno de los actos académicos más valientes de su generación."),
            ("Discípulos",
             "Brennan formó a nueve discípulos durante su vida. Cuatro se convirtieron en académicos de primer nivel. Dos se volvieron independientes y desarrollaron teorías que contradicen las suyas. Dos desaparecieron en expediciones. Uno fundó una religión basada en sus investigaciones.",
             "Brennan consideraba que la variedad de resultados era la mejor medida de su efectividad como maestro. Un buen maestro produce personas que piensan por sí mismas, no personas que repiten lo que aprendieron."),
            ("Final y legado",
             "Brennan murió a los ciento tres años, lo que los historiadores atribuyen a su abstemia en todo excepto el estudio. Sus últimas palabras, según su discípulo más cercano, fueron: <i>«Todavía hay tres preguntas que no pude responder.»</i>",
             "Las tres preguntas están escritas en el último volumen de su diario personal, que por instrucción expresa fue sellado durante cincuenta años después de su muerte. El sello se levanta el año que viene."),
        ]
    },
    {
        "nombre": "Kael Bordestormentoso", "faccion": "Alianza", "clase": "Acechante",
        "era": "Clásica", "origen": "Islas de la Tormenta",
        "entradas": [
            ("Hijo del mar",
             "Las Islas de la Tormenta no son un lugar amable. Kael creció en una comunidad de pescadores que vivía entre tormentas y aprendió que la diferencia entre sobrevivir y perecer era saber exactamente cuándo actuar y cuándo esperar.",
             "Ese instinto temporal, afinado en el mar, lo convirtió en algo único cuando lo trasladó a tierra: podía leer el momento perfecto de una situación con una precisión que sus compañeros describían como sobrenatural."),
            ("Reclutamiento",
             "La Alianza reclutó a Kael después de que resolvió solo una situación de rehenes en el puerto de su isla que había dejado paralizados a tres agentes entrenados. No había planificado nada. Simplemente había esperado el momento correcto y actuado.",
             "El oficial que lo reclutó escribió en su informe: <i>«Este hombre tiene el instinto más fino que he visto en veinte años. La única pregunta es si puede enseñar lo que sabe.»</i>"),
            ("Operaciones marítimas",
             "Kael se especializó en operaciones en y alrededor del agua: interdición de rutas de contrabando, protección de caravanas marítimas, localización de campamentos en islas no cartografiadas. Era, en efecto, la extensión de lo que había hecho toda su vida.",
             "Su operación más recordada fue el desmantelamiento de la Red de Contrabando de Eternium que operaba desde tres islas no marcadas en los mapas oficiales. La encontró siguiendo las rutas del viento en lugar de las rutas comerciales."),
            ("Filosofía de combate",
             "Kael rara vez era el primero en atacar y rara vez el más agresivo en combate. Su ventaja era posicional: cuando el momento de pelear llegaba, siempre estaba exactamente donde necesitaba estar.",
             "<i>«No gano peleas siendo el más fuerte. Gano eligiendo dónde pelear. El terreno no es el fondo de la batalla sino su mitad.»</i>"),
            ("Relación con el Sindicato",
             "El Sindicato intentó usar los conocimientos marítimos de Kael en dos ocasiones, ofreciendo compensación generosa. En ambas, Kael declinó porque las operaciones requerían daño a civiles náuticos que consideraba inaceptable.",
             "El Sindicato respetó los límites porque en el mar, Kael sabía más que ellos, y alistarle en su contra hubiera sido más costoso que buscar otra ruta."),
            ("Último viaje",
             "A los cincuenta y cinco años, Kael solicitó una licencia de su posición en la Alianza para hacer lo que llamó su último viaje personal: circunnavegar las islas del norte, territorio inexplorado por cualquier expedición registrada.",
             "Regresó dos años después con mapas, notas sobre corrientes y vientos y el informe de un fenómeno en las islas más lejanas que entregó a la Academia de la Alianza y que permanece clasificado."),
            ("Retiro activo",
             "Kael se retiró formalmente del servicio activo pero continuó entrenando a la siguiente generación de agentes marítimos de la Alianza. Sus estudiantes lo describen como el mejor instructor que tuvieron, no porque explicara todo sino porque enseñaba a sentir lo que no se podía explicar.",
             "Su método de enseñanza era simple: subían a un barco y navegaban. Todo lo demás venía después."),
        ]
    },
    {
        "nombre": "Elara la Herbolaria", "faccion": "Alianza", "clase": "Tejehechizos",
        "era": "Reciente", "origen": "Bosques del Centro",
        "entradas": [
            ("Magia verde",
             "Elara era lo que su comunidad llamaba una curandera del verde: alguien que combinaba conocimiento botánico con magia de bajo nivel para producir remedios que los sanadores convencionales no podían replicar.",
             "La Academia de la Alianza tardó tres años en convencerla de que estudiara formalmente. Cuando finalmente aceptó, sus instructores descubrieron que sabía más botánica aplicada que cualquiera de ellos."),
            ("El antídoto imposible",
             "El caso que la hizo famosa fue encontrar, en catorce días, el antídoto para un veneno que el Imperio había desarrollado en secreto durante cinco años y que no tenía cura conocida. Usó recursos del bosque que estaban a treinta metros del hospital.",
             "Cuando le preguntaron cómo lo había hecho, dijo que el bosque siempre proveía el remedio cerca del peligro. Llevaba veinte años observando ese patrón y todavía no sabía si era un principio biológico o algo más."),
            ("Relación con el Imperio",
             "A pesar de trabajar para la Alianza, Elara trataba a cualquiera que necesitara tratamiento sin importar su facción. Trató soldados imperiales heridos en tres batallas. El Imperio, en reconocimiento, garantizó que sus expediciones de recolección en territorio imperial no serían interrumpidas.",
             "Era uno de los pocos acuerdos no escritos entre facciones que ambas partes respetaban escrupulosamente porque ambas partes lo necesitaban."),
            ("El jardín de invierno",
             "Elara desarrolló el Jardín de Invierno: una técnica para mantener plantas medicinales activas durante el invierno usando cristales de Eternium de baja concentración como fuente de calor regulado.",
             "El Jardín de Invierno salvó vidas durante el último gran invierno cuando las reservas de medicamentos convencionales se agotaron en cuarenta y ocho horas. Las plantas de Elara mantuvieron activas las instalaciones médicas durante tres semanas más."),
            ("Discípulas",
             "Elara formó a doce curanderas del verde durante su vida. Las doce siguen activas. Tres de ellas han desarrollado técnicas que Elara considera superiores a las suyas.",
             "<i>«Cuando tus discípulas te superan, has hecho exactamente lo que debías.»</i>"),
            ("Filosofía curativa",
             "Elara tenía una posición filosófica que incomodaba a los sanadores institucionales: la curación no comenzaba con el tratamiento sino con entender por qué el paciente había enfermado. La medicina que solo trata síntomas crea dependencia.",
             "Fue uno de los primeros practicantes en documentar sistemáticamente las condiciones de vida de sus pacientes junto con sus condiciones médicas. Los resultados confirmaron lo que sospechaba: el noventa por ciento de las enfermedades crónicas tenían causas prevenibles."),
            ("Legado médico",
             "El Compendio de Plantas Medicinales de Elara, publicado en tres volúmenes durante los últimos años de su vida, es el manual estándar en hospitales y clínicas de campo de las tres facciones.",
             "Pero su contribución más duradera, que nadie registra porque es difícil de documentar, es el cambio de actitud hacia la medicina preventiva que inició. Treinta años después de que empezó a trabajar, la expectativa de vida en las comunidades donde operó era un quince por ciento mayor que el promedio regional."),
        ]
    },
    {
        "nombre": "Gareth el Forjador", "faccion": "Alianza", "clase": "Vanguardista",
        "era": "Clásica", "origen": "Citadel del Norte",
        "entradas": [
            ("Maestro herrero",
             "Gareth era tanto guerrero como herrero, una combinación inusual que resultó en algo único: armas diseñadas por alguien que sabía exactamente cómo se usaban en combate real, no solo en teoría.",
             "Sus primeras piezas las vendía desde la fragua de su padre. A los treinta años, la lista de espera para una pieza de Gareth era de dieciocho meses."),
            ("La aleación de Gareth",
             "La invención técnica que lo inmortalizó fue una aleación de acero y Eternium de baja concentración que mantenía un filo excepcional sin el fragilidad típica de las aleaciones con Eternium de mayor concentración.",
             "Intentó registrar la fórmula. Descubrió que no podía: la proporción exacta dependía de la fuente específica del mineral y del clima del día de la forja. Lo que parecía una fórmula era en realidad un juicio artesanal que tardó veinte años en desarrollar."),
            ("Relación con los aventureros",
             "Gareth tenía una política inusual: antes de hacer un arma para alguien, pasaba una hora hablando con ellos. Quería saber cómo peleaban, qué usaban ahora, qué les fallaba. El arma que producía era siempre específica para esa persona.",
             "<i>«Un arma de catálogo es un arma promedio. Mi cliente no es promedio. Por eso no forjo armas promedio.»</i>"),
            ("El arma que rechazó forjar",
             "Una sola vez en su carrera, Gareth rechazó un encargo. Era una espada para un noble del Imperio que quería que tuviera propiedades específicas. Gareth estudió las especificaciones durante un día, devolvió el pago y dijo que no sin explicar por qué.",
             "Nunca se supo exactamente qué había en las especificaciones. Dos años después, el noble fue arrestado por el propio Imperio por crímenes que Gareth no hubiera podido conocer cuando rechazó el encargo. La conexión es especulativa."),
            ("La forja como filosofía",
             "Gareth enseñaba a sus aprendices que la forja era una conversación entre el herrero y el metal. El metal tenía una naturaleza y el trabajo del herrero era entenderla y trabajar con ella, no contra ella.",
             "La misma filosofía aplicaba, decía, a cualquier cosa que valiera la pena hacer: entender la naturaleza del problema antes de intentar resolverlo. Los aprendices que no entendían por qué les decía esto en una forja eventualmente lo entendían cuando encontraban su primera crisis real."),
            ("El discípulo que le superó",
             "El mejor aprendiz de Gareth fue una joven llamada Vera que llegó a su taller a los catorce años y que a los veinticinco hacía cosas con el metal que Gareth nunca había intentado. Él le cedió el taller a los sesenta y se retiró a un lugar donde podía forjar sin clientes ni plazos.",
             "La escuela de herramienta que Vera fundó lleva el nombre de Gareth con su consentimiento explícito. Él visitó el taller una sola vez, miró lo que Vera hacía, y salió sin comentar nada. Vera interpretó el silencio como el mayor elogio que podía dar."),
            ("Los últimos trabajos",
             "Las últimas piezas que Gareth forjó no se vendieron. Las regaló a siete aventureros que, según su criterio, las necesitaban más que los clientes que las habrían comprado.",
             "Dos de esas piezas están documentadas en el Archivo de la Alianza. El paradero de las otras cinco es desconocido. Gareth dijo, cuando le preguntaron, que estaban donde debían estar."),
        ]
    },
    {
        "nombre": "Nadia la Diplomática", "faccion": "Alianza", "clase": "Tejehechizos",
        "era": "Reciente", "origen": "Ciudad de Tres Puertos",
        "entradas": [
            ("Arte de la negociación",
             "Nadia creció en Ciudad de Tres Puertos, donde los tres puertos representaban las tres facciones y la vida diaria era una negociación constante entre intereses incompatibles. Aprendió antes de los diez años que cada persona tiene algo que quiere y algo que teme, y que conocer ambas cosas es la mitad de cualquier negociación.",
             "La Alianza la incorporó como mediadora junior cuando tenía diecinueve años. En cinco años era la jefa de mediación para todos los conflictos de frontera."),
            ("La habilidad mágica de Nadia",
             "La magia de Nadia no era ofensiva ni defensiva sino comunicativa: podía percibir el estado emocional de las personas en su entorno con precisión clínica. No leía mentes, pero podía saber cuándo alguien mentía, cuándo tenía miedo aunque aparentara calma, cuándo era negociable aunque dijera que no.",
             "Nunca usó esta habilidad para manipular. La usó para saber cuándo una negociación podía avanzar y cuándo era mejor hacer una pausa."),
            ("El tratado de los Seis Días",
             "El Tratado de los Seis Días fue una negociación que todos los involucrados declararon imposible antes de comenzar: tres facciones, doce puntos de contención, un plazo de una semana impuesto por una crisis externa. Nadia lo logró en seis días.",
             "Lo que los historiadores nunca pudieron reconstruir fue cómo. Nadia presentó el resultado, los tres líderes lo firmaron y nadie pudo explicar completamente qué había cambiado sus posiciones. Nadia tampoco explicó. Consideraba que revelar el proceso dañaría su efectividad futura."),
            ("Límites éticos",
             "Nadia tenía una regla que nunca rompió: nunca negociaría para beneficiar a quien le daba instrucciones a expensas de inocentes que no tenían voz en la mesa. Esto le costó tres posiciones políticas que podría haber tenido.",
             "Consideraba que esas posiciones eran exactamente el problema: quien tenía poder político no podía, por definición, negociar en nombre de quienes no lo tenían. Prefería ser útil que ser poderosa."),
            ("Relación con el Sindicato",
             "El Sindicato respetaba a Nadia porque ella conocía su valor y nunca lo subvaluaba ni lo sobrevaluaba. Podía negociar con ellos sin miedo ni ingenuidad. Esto era infrecuente.",
             "El Sindicato le ofreció empleo en dos ocasiones. En ambas, Nadia explicó con precisión por qué no podía aceptar y en qué condiciones sí aceptaría. Las condiciones eran incompatibles con la forma de operar del Sindicato. El respeto mutuo continuó."),
            ("Lo que enseñó",
             "La Academia de la Alianza incorporó el Método Nadia al currículo formal de diplomacia quince años después de que lo desarrollara. El método tiene doce principios, el primero de los cuales es: <i>«Antes de entrar a cualquier negociación, saber cuál es el resultado mínimo aceptable para todas las partes, no solo para la tuya.»</i>",
             "Los instructores que enseñan el método dicen que el primer principio es el más fácil de entender y el más difícil de aplicar."),
            ("Jubilación estratégica",
             "Nadia se retiró de la mediación activa a los cincuenta y ocho años, no porque no pudiera continuar sino porque consideraba que su presencia en las negociaciones había comenzado a ser más importante que el resultado.",
             "<i>«Cuando las partes empiezan a negociar para tener mi aprobación en lugar de para resolver sus problemas, es hora de que me vaya.»</i> Se dedicó a escribir y a enseñar. Su libro sobre teoría de negociación es lectura obligatoria en todas las academias diplomáticas de las tres facciones."),
        ]
    },
    {
        "nombre": "Rogan el Feroz", "faccion": "Imperio", "clase": "Vanguardista",
        "era": "Clásica", "origen": "Frontera Este",
        "entradas": [
            ("El soldado del Imperio",
             "Rogan era exactamente el tipo de soldado que el Imperio buscaba crear: leal, efectivo, sin cuestionamientos morales que complicaran las órdenes. Era también, paradójicamente, el tipo de soldado que el Imperio no sabía qué hacer cuando dejaba de ser útil.",
             "Pasó treinta años en el ejército imperial. Veinte de esos años fueron en la Frontera Este, donde el conflicto con las comunidades locales era constante y el Imperio evaluaba el éxito en términos de territorio controlado."),
            ("La duda",
             "Rogan nunca tuvo una crisis de fe dramática. Tuvo algo peor: una acumulación lenta de pequeñas dudas que tardó veinte años en construirse hasta un punto donde ya no podía ignorarlas.",
             "El momento que lo cristalizó fue trivial: un niño de la Frontera le preguntó por qué el Imperio tenía razón. Rogan intentó responder y descubrió que las palabras que usaba eran las mismas que le habían dicho a él, sin ningún apoyo real detrás."),
            ("El desertor honesto",
             "Rogan no desertó en secreto ni huyó. Se presentó ante su comandante, explicó que no podía continuar en buena conciencia y solicitó su baja. El Imperio intentó arrestarlo por sedición. Sobrevivió el intento.",
             "Pasó los siguientes dos años en territorio neutral antes de que la situación política cambiara lo suficiente para que pudiera moverse libremente. Usó ese tiempo para escribir el único libro que publicó en su vida."),
            ("El libro sin título",
             "El libro que escribió Rogan durante su exilio no tiene título en la cubierta. Lo llamaban simplemente <i>El libro del soldado</i> y era una descripción honesta de lo que era servir en el ejército imperial: las victorias reales, los fracasos reales, los crímenes reales y la forma en que la institución procesaba todo eso.",
             "Fue prohibido por el Imperio inmediatamente. Fue leído clandestinamente por más soldados imperiales en las dos generaciones siguientes que ningún manual oficial."),
            ("Nueva vida",
             "Después de su exilio, Rogan se estableció en una ciudad neutral y abrió una escuela de artes marciales. Aceptaba estudiantes de las tres facciones. Nunca habló en clase sobre política o facciones.",
             "Lo que sí enseñaba, implícitamente, era pensar antes de obedecer. Sus estudiantes lo sabían pero ninguno podía citar una frase específica donde lo hubiera dicho."),
            ("Relación con la Alianza",
             "La Alianza quería usarlo como propaganda: el desertor del Imperio que les daba razón. Rogan se negó. No porque defendiera al Imperio sino porque no quería ser el argumento de nadie.",
             "<i>«No abandoné el Imperio para que la Alianza me usara. Abandoné el Imperio para poder tener razones propias.»</i>"),
            ("El reconocimiento tardío",
             "El Imperio rehabilitó póstumamente a Rogan cuarenta años después de su muerte, en el contexto de una revisión histórica que reconocía excesos en la Frontera Este. El decreto fue técnico y sin emoción.",
             "Sus estudiantes encontraron la rehabilitación irrelevante. Rogan ya tenía el reconocimiento que importaba: no el de las instituciones sino el de las personas a quienes sus enseñanzas habían ayudado a tomar decisiones propias."),
        ]
    },
    {
        "nombre": "Sylvara la Eterna", "faccion": "Alianza", "clase": "Tejehechizos",
        "era": "Antigua", "origen": "Desconocido",
        "entradas": [
            ("El misterio de su edad",
             "Nadie sabe cuántos años tiene Sylvara. Los registros más antiguos que la mencionan tienen cuatrocientos años. Ella no confirma ni niega su edad. Los investigadores que han intentado rastrear su origen han llegado a bibliografías que se pierden en registros demasiado antiguos para ser verificables.",
             "La explicación más aceptada entre los académicos: Sylvara encontró o desarrolló algún método de extensión de vida que no ha compartido con nadie. La explicación que ella da cuando se le pregunta: <i>«Tengo buena genética.»</i>"),
            ("Conocimiento acumulado",
             "Cuatro siglos de observación directa le dan a Sylvara algo que ningún libro puede reemplazar: el contexto real de la historia. Sabe qué ocurrió realmente en eventos que los registros presentan de manera diferente. Sabe qué había detrás de decisiones que los historiadores atribuyen a razones equivocadas.",
             "No comparte esto libremente. Cuando lo comparte, es con precisión quirúrgica, exactamente la información que la situación requiere, nunca más."),
            ("Neutralidad extraña",
             "Sylvara está afiliada a la Alianza pero nunca ha favorecido a la Alianza sobre las otras facciones de manera que pudiera considerarse parcial. Ha ayudado a las tres facciones en proporciones que, si alguien las analizara, serían notablemente equilibradas.",
             "Cuando la Alianza le señaló esto como un problema de lealtad, respondió: <i>«He vivido lo suficiente como para saber que ninguna facción tiene razón en todo. Mi lealtad es con Aethelgard, no con quienes lo gobiernan en un momento dado.»</i>"),
            ("La advertencia de cuatro siglos",
             "Sylvara ha dado, durante su vida, exactamente once advertencias formales sobre crisis inminentes. Las once ocurrieron. No siempre en el momento o la forma exacta que predijo, pero ocurrieron.",
             "La duodécima advertencia la emitió hace tres años. Los líderes de las tres facciones la conocen. Ninguno ha actuado todavía de la manera que Sylvara considera necesaria. Ella dice que esto también lo ha visto antes."),
            ("Sus estudiantes",
             "Sylvara ha formado a más estudiantes de los que puede recordar. Lo que todos ellos comparten es que en algún momento de su entrenamiento, la forma en que entendían el tiempo cambió: empezaron a ver los eventos no como momentos aislados sino como parte de patrones que se repetían.",
             "Esto, dice, es lo más importante que puede enseñar. Todo lo demás son detalles."),
            ("El costo de la longevidad",
             "Sylvara habla raramente de lo que ha perdido. Ha sobrevivido a personas que amaba en números que no quiere recordar. Ha visto imperios levantarse y caer. Ha visto ideales que consideraba eternos volverse polvo.",
             "Lo que la mantiene, según la única vez que lo explicó con algo cercano a la franqueza: <i>«Todavía hay cosas que no he visto terminar. Necesito saber cómo terminan.»</i>"),
            ("El secreto de la longevidad",
             "Sylvara tiene un secreto sobre cómo ha extendido su vida. Es información que tiene valor inmenso para quienes la buscan. No lo ha compartido nunca. Ha rechazado amenazas, sobornos y manipulaciones con igual indiferencia.",
             "La razón que ha dado en los contados momentos en que se ha acercado al tema: <i>«La longevidad sin el contexto correcto no es un regalo. He visto lo que le hace a quien no está listo para ella.»</i>"),
        ]
    },
    {
        "nombre": "Dorak el Minero", "faccion": "Sindicato", "clase": "Maestra de Caza",
        "era": "Clásica", "origen": "Minas de Crystalhaven",
        "entradas": [
            ("Criado bajo la tierra",
             "Dorak creció en las minas de Crystalhaven, donde su familia llevaba tres generaciones extrayendo Eternium. Aprendió antes que cualquier otra cosa que el valor de algo dependía de dónde estaba, no de lo que era: un cristal de Eternium en el suelo valía una cantidad; en la ciudad correcta, otra completamente diferente.",
             "Esta lección de economía espacial era la base de todo lo que haría después."),
            ("El ojo para el mineral",
             "Dorak tenía una habilidad rara: podía evaluar la calidad de un cristal de Eternium con una precisión mayor que cualquier instrumento disponible en su época. No podía explicar cómo lo hacía. Los académicos que lo estudiaron durante un año tampoco pudieron explicarlo.",
             "El Sindicato usó esta habilidad durante veinte años para evaluar contratos de minería. Fue la razón por la que conoció los mercados de recursos mejor que nadie."),
            ("La red de comercio",
             "Dorak construyó gradualmente, sin que nadie lo hubiera planificado, la red de comercio de recursos minerales más grande de Aethelgard. No estaba formalizada ni era visible. Era simplemente una serie de relaciones de confianza construidas en veinte años de tratos justos.",
             "Cuando el Sindicato intentó formalizar y controlar la red, descubrió que sin Dorak en el centro, la red no funcionaba. El Sindicato llegó a un acuerdo: autonomía para Dorak a cambio de acceso preferencial a la información de precios."),
            ("Filosofía de precios",
             "Dorak tenía una filosofía sobre los precios que muchos de sus competidores encontraban ingenua: nunca cobraba más de lo que algo valía realmente, aunque el mercado lo hubiera permitido.",
             "<i>«La codicia crea burbujas. Las burbujas explotan. El hombre que vendió caro en la cumbre pierde más en el colapso que lo que ganó subiendo. Yo prefiero ganar menos pero ganar siempre.»</i>"),
            ("La crisis de Crystalhaven",
             "La crisis que definió su legado fue cuando el Ducado de Crystalhaven intentó monopolizar la extracción de Eternium expulsando a los mineros independientes. Dorak coordinó la resistencia sin usar violencia: simplemente movió sus redes comerciales para que el monopolio no tuviera mercado.",
             "El Ducado duró dos años antes de que la presión económica los obligara a negociar. Dorak fue el mediador. Las condiciones que obtuvo para los mineros independientes fueron mejores de lo que hubieran conseguido con cualquier otro medio."),
            ("Relación con las facciones",
             "Dorak tenía una relación pragmática con las tres facciones: era útil para todas y leal a ninguna. Proveía recursos a quien los necesitara siempre que pagaran y siempre que no usaran lo que compraban contra las comunidades mineras.",
             "Esta segunda condición era menos obvia que la primera pero era la que más importaba. Dorak había visto demasiados recursos extraídos de comunidades que terminaron destruidas por los mismos recursos que extrajeron."),
            ("El legado del comercio justo",
             "Lo que Dorak construyó sobrevivió su muerte: la red de relaciones que estableció continuó porque las personas que participaban en ella habían aprendido que el comercio justo era más rentable a largo plazo que la explotación a corto plazo.",
             "Sus hijos continuaron el trabajo. Sus nietos lo expandieron. Tres generaciones después, el apellido Dorak es en las minas de Crystalhaven sinónimo de precio honesto, lo cual en el contexto de las minas equivale al mayor elogio posible."),
        ]
    },
    {
        "nombre": "Celeste la Vidente", "faccion": "Alianza", "clase": "Tejehechizos",
        "era": "Antigua", "origen": "Torre de las Estrellas",
        "entradas": [
            ("Nacida bajo la alineación",
             "Celeste nació durante la alineación planetaria que ocurre cada setenta años, y los astrólogos de su época afirmaron que esto explicaba sus capacidades. Ella pasó su vida tratando de demostrar que las capacidades venían del trabajo, no del nacimiento.",
             "Su magia era de visión: podía percibir patrones en el futuro con una precisión que aumentaba cuanto más largo era el horizonte temporal. Paradójicamente, era menos precisa en eventos cercanos que en eventos lejanos."),
            ("La maldición de ver lejos",
             "Ver el futuro lejano con claridad mientras el futuro cercano permanecía borroso era una forma particular de angustia. Celeste sabía lo que ocurriría en décadas pero no podía predecir el tiempo que haría mañana.",
             "Sus contemporáneos la consultaban para decisiones estratégicas a largo plazo y se frustraban cuando no podía decirles si debían partir al día siguiente o esperar. La distinción entre lo que podía y no podía ver les resultaba incomprensible."),
            ("El gran consejo",
             "Celeste fue convocada en once ocasiones por consejos de facciones que necesitaban perspectiva de largo plazo. En once ocasiones dio la misma respuesta a preguntas similares: <i>«El camino que buscan es posible. No es el único posible ni el mejor garantizado. El factor determinante es siempre la voluntad de quienes lo recorren.»</i>",
             "Los consejos generalmente querían respuestas más específicas. Celeste era metódica en explicar por qué las respuestas más específicas que querían eran exactamente el tipo de respuestas que el futuro no daba."),
            ("El registro de visiones",
             "Celeste mantuvo durante cuarenta años un diario de visiones que entregó a la Academia de la Alianza antes de su muerte, con instrucciones de publicarlo en secciones cada diez años.",
             "Las primeras cinco secciones, ya publicadas, describen eventos que ocurrieron con suficiente precisión para ser verificables. Las secciones que faltan por publicar son objeto de mucha especulación. La más cercana a ser publicada incluye visiones sobre el próximo siglo."),
            ("Vida personal compleja",
             "Celeste tuvo una vida personal complicada por razones que cualquiera que pudiera ver el futuro podría imaginar: saber qué iba a terminar mal hacía que empezar fuera más difícil. Saber qué iba a durar no compensaba siempre el trabajo de construirlo.",
             "<i>«Ver el futuro no hace la vida más fácil. Hace que sea más difícil pretender que las cosas son distintas de lo que son.»</i>"),
            ("La ultima visión registrada",
             "La última visión que Celeste registró antes de su muerte a los ochenta y tres años fue brevísima: una sola frase sin contexto ni explicación. Los académicos llevan cincuenta años intentando descifrar a qué se refería.",
             "La frase, en el lenguaje críptico que a veces usaba para las visiones más importantes: <i>«El acuerdo se renueva cuando quien tiene todo elige dar.»</i>"),
            ("Escuela de videntes",
             "Celeste fundó la única escuela formal de visión mágica en Aethelgard. Seleccionaba sus estudiantes no por el poder de sus visiones sino por cómo respondían cuando una visión decía algo que no querían escuchar.",
             "Su criterio de selección era inusual pero resultó ser exactamente correcto: los mejores videntes no eran los más poderosos sino los más honestos consigo mismos sobre lo que veían."),
        ]
    },
    {
        "nombre": "Marco el Explorador", "faccion": "Sindicato", "clase": "Maestra de Caza",
        "era": "Reciente", "origen": "Ciudad de los Vientos",
        "entradas": [
            ("El cartógrafo del vacío",
             "Marco fue el primer explorador en registrar sistemáticamente las zonas de Aethelgard que ningún mapa oficial reconocía. No los territorios desconocidos por inaccesibles, sino los territorios que las facciones preferían no reconocer que existían.",
             "El Sindicato financió sus expediciones porque la información sobre rutas no cartografiadas valía considerablemente más que el costo de obtenerla."),
            ("La red de rutas ocultas",
             "En quince años de expediciones, Marco documentó cuarenta y siete rutas de paso que no aparecían en ningún mapa oficial. Algunas las habían usado contrabandistas durante generaciones. Otras parecían nunca haber sido usadas por humanos.",
             "El mapa que compiló, guardado en depósito cifrado en la sede del Sindicato, es considerado el activo de información más valioso que la organización posee."),
            ("Lo que encontró en el norte",
             "La expedición al norte que duró tres años produjo registros que el Sindicato decidió mantener parcialmente confidenciales. Lo que se sabe: Marco encontró estructuras en las montañas del norte que no correspondían a ninguna arquitectura conocida en Aethelgard.",
             "Lo que no se sabe: lo que estaba dentro de esas estructuras. Marco describió el interior en sus notas personales con un código que cambió específicamente para ese propósito. Nadie ha descifrado ese código."),
            ("Filosofía de la exploración",
             "Marco creía que el mayor obstáculo para el conocimiento no era el territorio desconocido sino la disposición de los exploradores a ver lo que no esperaban ver.",
             "<i>«Llegas a un lugar con una hipótesis. Si la hipótesis es correcta, confirmas lo que ya sabías. Si es incorrecta y puedes aceptarlo, aprendes algo nuevo. Los exploradores que no pueden aceptar que estaban equivocados nunca descubren nada.»</i>"),
            ("Relación con la Alianza",
             "La Alianza intentó contratar a Marco como explorador oficial tres veces. La tercera vez él contraofertó: informes compartidos a cambio de acceso libre a los archivos cartográficos de la Alianza.",
             "La Alianza rechazó la contraoferta porque requería demasiada transparencia. Marco siguió con el Sindicato y la Alianza siguió sin tener acceso a sus rutas. Ambas partes consideraron que el resultado era predecible y justo."),
            ("Lo que no exploró",
             "Marco nunca entró a la Mazmorra Negra. En cuarenta años de exploración, habiendo entrado a territorios que la mayoría consideraría suicidas, se negó consistentemente a la Mazmorra Negra.",
             "Cuando le preguntaban por qué, daba respuestas diferentes. La única que sus colegas consideran posiblemente honesta: <i>«Hay territorios que no quieren ser explorados. Respetar eso forma parte de entender el mundo.»</i>"),
            ("El mapa que dejó",
             "Antes de su última expedición, de la cual no regresó, Marco dejó en el Sindicato instrucciones sobre cómo descifrar el código del norte. Las instrucciones dicen que el código solo puede ser descifrado por alguien que ya haya estado en las estructuras del norte.",
             "El Sindicato ha enviado tres expediciones desde entonces. Las tres regresaron sin haber encontrado las estructuras, lo cual Marco hubiera considerado parte del diseño."),
        ]
    },
    {
        "nombre": "Petra la Defensora", "faccion": "Alianza", "clase": "Vanguardista",
        "era": "Reciente", "origen": "Puerto de la Niebla",
        "entradas": [
            ("La guardiana de los civiles",
             "Petra nunca fue una guerrera de conquista. Desde el principio de su carrera en la Guardia de la Alianza, su especialidad era la defensa: de comunidades, de rutas, de personas que no podían defenderse solas.",
             "Esto la hacía menos visible que quienes acumulaban victorias en campo abierto, pero las comunidades que protegía sabían exactamente cuánto valía."),
            ("La defensa de Puerto de la Niebla",
             "El evento que definió su carrera fue la defensa de Puerto de la Niebla durante el asedio de cuatro meses que el Imperio intentó en la última guerra de fronteras. Petra coordinó la defensa con recursos que representaban un tercio de lo que el ataque disponía.",
             "El Puerto nunca cayó. Cuando llegaron los refuerzos, encontraron a Petra en el mismo puesto de mando donde había estado durante ciento veintidós días. Declinó el reconocimiento oficial. Lo que quería era descansar."),
            ("Metodología defensiva",
             "Petra desarrolló lo que sus colegas llamaban la Forma del Escudo: una metodología de defensa comunitaria que integraba a los civiles como parte activa de la defensa, no como objetos a proteger.",
             "La diferencia no era solo filosófica. Las comunidades que internalizaban la Forma del Escudo eran estadísticamente más difíciles de conquistar que las que dependían completamente de su guardia externa."),
            ("La carta al Imperio",
             "En una ocasión, Petra envió una carta directa al comandante imperial que la enfrentaba durante un asedio, proponiéndole términos de retirada que preservaban el honor del Imperio mientras terminaban el conflicto.",
             "El comandante la rechazó públicamente y la aceptó privadamente tres semanas después. Los términos de la rendición fueron casi idénticos a los de la carta. Petra nunca señaló esto."),
            ("Relación con el Sindicato",
             "Petra usó los servicios del Sindicato en dos ocasiones para obtener información de inteligencia que la Alianza no podía conseguir de otra forma. Pagó precio de mercado, agradeció el servicio y no preguntó sobre los métodos.",
             "El Sindicato la consideraba una cliente razonable, lo que en su terminología era el mayor elogio que podían dar a alguien que no era de la organización."),
            ("Lo que enseñó",
             "Petra formó a cien defensores en su carrera. Su primer principio de enseñanza: <i>«La mejor defensa es la que nunca necesita usarse. Eso requiere que el atacante sepa de antemano que no va a poder.»</i>",
             "Su segundo principio, menos conocido: <i>«El defensor que protege lo que no vale proteger está perdiendo recursos. Aprende a distinguir lo que importa de lo que parece importar.»</i>"),
            ("Legado civil",
             "Petra se retiró del servicio activo a los cincuenta y siete años y se convirtió en asesora de comunidades que querían mejorar su capacidad defensiva. Viajó más en sus años de retiro que durante su servicio activo.",
             "Su legado más duradero es invisible: las veintisiete comunidades que no fueron conquistadas, saqueadas o destruidas en los veinte años siguientes a que ella les enseñara la Forma del Escudo. La ausencia de catástrofe no genera monumentos, pero esas veintisiete comunidades existen."),
        ]
    },
    {
        "nombre": "Axel el Tabernero", "faccion": "Sindicato", "clase": "Acechante",
        "era": "Reciente", "origen": "Ciudad Neutral de Crossroads",
        "entradas": [
            ("La taberna como información",
             "Axel llevaba veinte años sirviendo cerveza en la taberna más transitada de Crossroads cuando el Sindicato se dio cuenta de que, sin saberlo, había construido el centro de información más valioso de la ciudad.",
             "Todos los viajeros pasaban por la taberna de Axel. Todos hablaban más de lo que debían después de unas copas. Axel escuchaba todo sin parecer escuchar nada. Ese era su don."),
            ("Memoria perfecta",
             "Axel tenía una memoria para las conversaciones que ningún académico había podido explicar: podía repetir, verbatim, conversaciones de hace diez años que había escuchado de pasada mientras servía mesas.",
             "Nunca tomaba notas. Nunca necesitó hacerlo. Su cabeza era el archivo más completo de información no oficial de Crossroads."),
            ("La oferta del Sindicato",
             "El Sindicato le ofreció trabajo formal. Axel contrapropuso: seguiría siendo tabernero pero pondría a disposición del Sindicato, a precio acordado, información específica cuando la solicitaran. La taberna era su tapadera perfecta precisamente porque era real.",
             "El Sindicato aceptó. El acuerdo duró quince años y fue uno de los más rentables de ambas partes."),
            ("Las tres reglas de Axel",
             "Axel tenía tres reglas que el Sindicato aceptó cuando hizo el trato: no proporcionaría información sobre refugiados o personas huyendo de peligro. No identificaría a niños en situaciones vulnerables. No daría información que resultara en daño a trabajadores de la taberna.",
             "El Sindicato encontró las reglas razonables y las cumplió. En quince años de trabajo, nunca las pusieron a prueba, lo cual Axel consideraba el mayor éxito de la relación."),
            ("La comunidad de la taberna",
             "La taberna de Axel era más que un negocio. Era el lugar donde las tres facciones coexistían en neutralidad tácita porque todos sabían que en la taberna de Axel no pasaban las guerras. Había peleas ocasionales, pero terminaban afuera.",
             "Axel mantenía esta neutralidad con una combinación de autoridad moral y memoria perfecta. Nadie quería que Axel recordara su peor noche."),
            ("Lo que nunca vendió",
             "Hay información que Axel tenía y que nunca vendió al Sindicato ni a nadie. No podía explicar exactamente el criterio con el que decidía qué vendía y qué guardaba, pero sus colegas del Sindicato estimaban que lo que se quedaba era significativamente más valioso que lo que compartía.",
             "Cuando el Sindicato lo presionó al respecto, Axel sirvió otra ronda y cambió de tema. La relación sobrevivió ese momento."),
            ("La jubilación del tabernero",
             "Axel vendió la taberna a los sesenta y dos años a una pareja joven que no tenía ninguna conexión con el Sindicato. Pasó el año siguiente viajando por los mismos lugares de donde provenían sus clientes más interesantes.",
             "El Sindicato notó que los mercados de información en varias ciudades se volvieron más difíciles de trabajar durante ese año. Nadie conectó esto con el viaje de Axel hasta mucho después."),
        ]
    },
    {
        "nombre": "Vera la Inventora", "faccion": "Imperio", "clase": "Tejehechizos",
        "era": "Reciente", "origen": "Taller de Gareth",
        "entradas": [
            ("Aprendiz que superó al maestro",
             "Vera llegó al taller de Gareth el Forjador a los catorce años sin experiencia pero con algo que Gareth reconoció inmediatamente: la capacidad de ver en el metal lo que todavía no existía.",
             "En once años de aprendizaje, Vera absorbió todo lo que Gareth podía enseñarle y luego empezó a ir más allá. Gareth le cedió el taller sin drama: era el resultado correcto y ambos lo sabían."),
            ("La forja con magia integrada",
             "La innovación que define a Vera es la integración de magia directamente en el proceso de forja, no después. En lugar de encantar un arma terminada, Vera incorpora los patrones mágicos durante la creación del metal mismo.",
             "El resultado son armas donde la magia no es una capa adicional sino parte de la estructura. Son más difíciles de hacer pero prácticamente imposibles de des-encantar."),
            ("La academia de herrería",
             "Vera fundó la Academia de Forja de la Alianza con la convicción de que el conocimiento técnico debía ser accesible, no guardado como secreto gremial.",
             "Esta decisión tuvo consecuencias: la calidad general del equipo en las tres facciones mejoró en una generación. Los herreros establecidos la odiaron. Los aventureros que podían comprar mejor equipo por el aumento de oferta la adoraron."),
            ("El encargo imposible",
             "El encargo más difícil de su carrera fue un escudo que debía resistir magia de nivel cuatro, pesar menos que el acero estándar y mantenerse funcional a temperaturas extremas.",
             "Tardó un año en resolver el problema. La solución requirió una aleación que ella misma tuvo que desarrollar porque no existía. El escudo existe, funciona exactamente como se requería, y el proceso para hacerlo es ahora parte del currículo avanzado de la Academia."),
            ("Relación con el Imperio",
             "El Imperio intentó comprar los servicios exclusivos de Vera en múltiples ocasiones. Vera respondía siempre lo mismo: los conocimientos de forja debían estar disponibles para todos, no solo para quien pagara más.",
             "El Imperio eventualmente aceptó contratos no exclusivos: Vera haría encargos específicos para el Imperio a precio de mercado pero mantendría su independencia. Era menos de lo que querían pero más de lo que tendrían sin el acuerdo."),
            ("La pieza sin nombre",
             "En los últimos años de su carrera, Vera trabajó en un proyecto que no describió a nadie: una pieza cuya función se negó a explicar. La terminó a los sesenta y un años. La guardó. Cuando la encontraron después de su muerte, los especialistas pasaron tres meses intentando entender para qué servía.",
             "Eventualmente concluyeron que era un sistema de seguridad para algo que no habían encontrado. Sigue sin encontrarse."),
            ("Legado en metal y conocimiento",
             "El legado de Vera es dual: las piezas físicas que hizo, algunas de las cuales siguen activas décadas después, y el conocimiento que distribuyó a través de su Academia.",
             "La Academia de Forja lleva su nombre. La graduación anual incluye una demostración de forja donde los estudiantes más avanzados intentan replicar las técnicas de Vera. Ninguno las ha replicado completamente todavía. Los instructores consideran que este es el mejor monumento posible."),
        ]
    },
    {
        "nombre": "Orion el Astrónomo", "faccion": "Imperio", "clase": "Tejehechizos",
        "era": "Antigua", "origen": "Observatorio Imperial",
        "entradas": [
            ("El hombre que miraba arriba",
             "Orion dedicó su vida a estudiar lo que estaba sobre Aethelgard: los patrones estelares, los ciclos planetarios, los fenómenos atmosféricos que la mayoría consideraba irrelevantes para la vida práctica.",
             "El Imperio financió su trabajo porque las predicciones meteorológicas y astronómicas tenían aplicaciones militares directas. Orion aceptó el financiamiento y continuó con la investigación que realmente le importaba."),
            ("El descubrimiento de los ciclos",
             "Orion pasó cuarenta años documentando ciclos en los fenómenos estelares que se repetían en períodos de entre siete y setenta años. Cuando los publicó, los académicos encontraron la metodología impecable pero las implicaciones incómodas: los ciclos sugerían que algunos eventos en Aethelgard no eran aleatorios sino predecibles.",
             "Las implicaciones filosóficas y políticas de esto todavía se debaten."),
            ("La predicción de la tormenta magna",
             "Su predicción más famosa fue la Tormenta Magna de hace cincuenta años: Orion predijo, con trece meses de anticipación, la ubicación, duración e intensidad de una tormenta que los meteorólogos locales consideraban imposible.",
             "La predicción fue ignorada. La tormenta ocurrió exactamente como había predicho. El Imperio tardó una generación en procesar esta combinación de éxito y fracaso institucional."),
            ("El Observatorio como legado",
             "El Observatorio que Orion amplió y mejoró durante cuarenta años es hoy el más completo de Aethelgard. Tiene registros continuos de observación astronómica durante ciento cincuenta años.",
             "Esos registros han resultado invaluables para disciplinas que Orion no anticipó: los patrones que documentó tienen correlaciones con fenómenos mágicos que los investigadores de magia están recién comenzando a explorar."),
            ("Filosofía cósmica",
             "Orion era el único académico de su época que tomaba en serio la posibilidad de que el universo más allá de Aethelgard estuviera habitado. No como artículo de fe sino como hipótesis de trabajo.",
             "<i>«La pregunta no es si estamos solos. La pregunta es qué implica que estemos solos, si lo estamos, o que no lo estemos, si no lo estamos. Cualquiera de las dos respuestas cambia todo.»</i>"),
            ("Relación con las otras facciones",
             "Las estrellas son iguales para todos, lo que daba a Orion una base natural para la cooperación científica entre facciones. Mantuvo correspondencia con astrónomos de la Alianza y del Sindicato durante décadas.",
             "Cuando el Imperio lo presionó para que sus investigaciones fueran exclusivas, respondió que las estrellas no reconocían fronteras y que limitar su trabajo a una facción era limitar su utilidad al universo mismo. El Imperio decidió no presionarlo más."),
            ("El último registro",
             "El último registro de Orion, escrito dos días antes de su muerte a los ochenta y nueve años, describe un fenómeno que observó esa noche: un patrón en las estrellas que no había visto nunca antes y que no podía clasificar.",
             "El registro incluye cálculos que predicen que el fenómeno se repetirá. Los sucesores de Orion en el Observatorio vigilan esa región del cielo. Todavía no ha ocurrido. El cálculo dice que ocurrirá dentro de los próximos veinte años."),
        ]
    },
]

# ── PERSONAJES VILLANOS ───────────────────────────────────────────────────────

VILLANOS = [
    {
        "nombre": "Malgrath el Corrompido", "faccion": "ninguna", "clase": "Tejehechizos",
        "era": "Clásica", "origen": "Academia de la Alianza (expulsado)",
        "entradas": [
            ("La caída del académico",
             "Malgrath fue uno de los estudiantes más brillantes que produjo la Academia de la Alianza. También fue el primero en ser expulsado por experimentación prohibida en cuatro siglos de historia institucional.",
             "El expediente de su expulsión está sellado. Los académicos que lo conocieron antes de su caída describen a alguien brillante pero con una falla fundamental: no podía aceptar que cierto conocimiento no debería buscarse."),
            ("El pacto con el Vacío",
             "La teoría más aceptada sobre Malgrath es que hizo un pacto con una entidad del Vacío en algún punto de los veinte años que siguieron a su expulsión. Lo que obtuvo: poder mágico sin precedentes. Lo que cedió: esto no está documentado, pero el Malgrath que reapareció después de esos años era fundamentalmente diferente al que había desaparecido.",
             "Sus antiguos colegas que lo enfrentaron en ese período describían algo que usaba el cuerpo y la voz de Malgrath pero que no era Malgrath."),
            ("Sus logros oscuros",
             "Malgrath fue el primero en cartografiar sistemáticamente las estructuras del Vacío accesibles desde Aethelgard. Ese conocimiento es hoy uno de los documentos más clasificados del mundo, guardado en las tres facciones simultáneamente.",
             "También desarrolló hechizos de corrupción mágica que sus sucesores siguen sin poder replicar completamente, lo cual no saben si es un logro o una bendición."),
            ("Los que resistieron",
             "En su período de mayor poder, Malgrath reclutó a siete magos para su proyecto. Cuatro lo siguieron hasta el final. Tres se negaron y pagaron por esa negativa.",
             "Los tres que se negaron son ahora estudiados en la Academia de la Alianza como ejemplos de resistencia moral en condiciones extremas. Los cuatro que siguieron son estudiados como advertencias."),
            ("La derrota",
             "La derrota de Malgrath no fue épica en la forma en que los bardos la cantan. Fue el resultado de décadas de trabajo paciente de una coalición de tres facciones que raramente cooperaban.",
             "Lo que lo derrotó no fue la fuerza sino una comprensión de las estructuras del Vacío que él mismo había documentado. Sus propias investigaciones contuvieron el germen de su caída."),
            ("Lo que quedó",
             "Malgrath murió o fue sellado o desapareció al Vacío, dependiendo de qué relato se consulte. Lo que es cierto: después del evento que los registros llaman su fin, su influencia continuó.",
             "Los hechizos que había dejado en el mundo siguieron activos durante décadas. Los discípulos que había formado tardaron generaciones en ser neutralizados. Y las estructuras del Vacío que había cartografiado siguieron existiendo, ahora con el conocimiento de que podían ser accedidas."),
            ("El legado incómodo",
             "Malgrath es una contradicción que la historia de Aethelgard no ha procesado completamente: fue un criminal y un genio en proporciones iguales. Sus contribuciones al conocimiento, aunque obtenidas a costo inaceptable, son genuinas.",
             "La Academia de la Alianza tiene sus obras en sus archivos más restringidos. Los usan. No lo admiten públicamente."),
        ]
    },
    {
        "nombre": "Lyara la Traidora", "faccion": "Imperio (ex-Alianza)", "clase": "Acechante",
        "era": "Reciente", "origen": "Fortaleza de Dawnthorpe",
        "entradas": [
            ("La mejor de su generación",
             "Lyara fue durante diez años la mejor agente de la Alianza en su generación. Sus operaciones tenían una tasa de éxito que los analistas consideraban estadísticamente imposible. Sus colegas la admiraban. Sus supervisores la adoraban.",
             "Esto hacía la traición más dolorosa. No fue una infiltración del Imperio: Lyara eligió cambiar de bando, con toda la información que tenía, después de una decisión de la Alianza que consideró imperdonable."),
            ("El evento detonador",
             "Lo que desencadenó la traición de Lyara fue la decisión de la Alianza de sacrificar a tres agentes encubiertos para proteger una operación de mayor escala. Lyara conocía a los tres. Había trabajado con ellos durante años.",
             "La Alianza tomó la decisión correcta desde un punto de vista estratégico. Lyara no podía aceptarlo desde un punto de vista humano. La diferencia entre los dos criterios es la historia de cómo una persona puede romperse."),
            ("Lo que le dio al Imperio",
             "Lo que Lyara proporcionó al Imperio en los tres primeros meses fue suficiente para alterar el equilibrio de información entre las facciones durante cinco años. Los analistas de la Alianza describen ese período como el más oscuro de su historia de inteligencia.",
             "Lyara sabía exactamente el daño que hacía. Lo hacía de todas formas porque el daño a la institución que había tomado la decisión que no podía perdonar era el punto."),
            ("La duda posterior",
             "Los registros capturados después indican que Lyara comenzó a dudar de su decisión aproximadamente dos años después de la traición. Lo que la detuvo de intentar regresar no fue el Imperio sino la certeza de que la Alianza no la aceptaría y de que no podía culparlos.",
             "Terminó en un espacio sin retorno posible que había creado ella misma."),
            ("La captura",
             "Lyara fue capturada eventualmente por una agente de la Alianza que había sido su aprendiza. El detalle que todos los relatos mencionan: cuando la aprendiza la capturó, Lyara no resistió.",
             "No se sabe si esto fue rendición, agotamiento o algo más complejo. La aprendiza nunca habló públicamente sobre esa conversación."),
            ("El juicio",
             "El juicio de Lyara fue uno de los más observados en la historia reciente de la Alianza. Sus argumentos en su defensa no negaron los hechos sino cuestionaron la legitimidad moral de la decisión que la había precipitado todo.",
             "La Alianza nunca respondió públicamente a esa cuestión. Fue condenada. La sentencia fue veinticinco años. Cumplió diecisiete antes de morir de causas naturales."),
            ("Lo que se pregunta después",
             "Después de la muerte de Lyara, la Alianza realizó una revisión interna de la decisión que había precipitado la traición. La revisión concluyó que la decisión había sido correcta pero que el proceso para tomarla había sido deficiente.",
             "No es una exoneración. No es una condena. Es el tipo de conclusión institucional que no satisface a nadie pero que es más honesta que la alternativa."),
        ]
    },
    {
        "nombre": "Vorn el Mercenario sin Alma", "faccion": "ninguna", "clase": "Vanguardista",
        "era": "Clásica", "origen": "Los Pantanos del Sur",
        "entradas": [
            ("Nacido en los pantanos",
             "Vorn vino de los Pantanos del Sur, una región que ninguna facción reclamaba porque el costo de controlarla superaba cualquier beneficio. Los habitantes de los pantanos aprendían a sobrevivir sin el apoyo de ninguna institución.",
             "Esto producía, ocasionalmente, personas con capacidades extraordinarias para navegar el mundo sin reglas de ningún tipo. Vorn fue el caso extremo de esa tendencia."),
            ("La mercenería como filosofía",
             "Vorn era mercenario sin compromisos morales de ningún tipo: hacía lo que le pagaban siempre que el precio fuera justo. Las tres facciones lo habían contratado en distintos momentos y todas tenían razones para lamentarlo.",
             "<i>«No soy un hombre malo. Soy un hombre sin categorías morales. La diferencia importa para quienes las tienen. Para mí, no.»</i>"),
            ("El límite que nadie supo",
             "Se descubrió después de su muerte que Vorn había rechazado cuatro contratos en su carrera. Los cuatro implicaban niños. No hay registro de que lo explicara nunca a nadie.",
             "Este detalle, encontrado en un diario personal que nadie sabía que existía, cambió retrospectivamente la comprensión que muchos tenían de él. Si tenía un límite, no era sin alma."),
            ("La habilidad de combate",
             "Como guerrero, Vorn era excepcional: décadas de combate en condiciones extremas habían producido un conjunto de habilidades que la formación académica no podía replicar.",
             "Los instructores que intentaron analizarlo dijeron que su combate no seguía ninguna escuela conocida. Era adaptación pura, sin dogma."),
            ("La factura del Imperio",
             "El Imperio contrató a Vorn para una operación que se salió de control. Cuando el polvo se asentó, la operación había producido consecuencias que el Imperio no había autorizado.",
             "El Imperio intentó responsabilizarlo. Vorn señaló que había cumplido exactamente lo que el contrato especificaba y que el Imperio había especificado mal. La discusión fue larga. Vorn ganó por razones que el Imperio no quiso ventilar públicamente."),
            ("El final apropiado",
             "Vorn murió en un contrato que salió mal, a los cincuenta y nueve años, que es mucho más tiempo del que cualquiera que lo conocía hubiera predicho.",
             "No dejó herederos conocidos, ni bienes sustanciales, ni un legado que alguien quisiera reivindicar. Lo que dejó fueron historias, algunas verdaderas y muchas exageradas, y la certeza de que en algún punto de su carrera había cruzado casi todos los límites que existen."),
            ("El diario sin destinatario",
             "El diario que se encontró después de su muerte no tenía destinatario. Era simplemente un registro de cuarenta años de trabajo, con una honestidad brutal sobre lo que había hecho, por qué y con qué consecuencias.",
             "Quien lo encontró lo entregó al Sindicato. El Sindicato lo copió y vendió copias a las tres facciones. Las tres querían saber si las descripciones de sus propios contratos eran precisas. Lo eran."),
        ]
    },
    {
        "nombre": "Sethara la Hechicera del Espejo", "faccion": "Imperio (disidente)", "clase": "Tejehechizos",
        "era": "Antigua", "origen": "Torre del Espejo Negro",
        "entradas": [
            ("El espejo como puerta",
             "Sethara descubrió siendo aún joven que los espejos eran más que superficies reflectantes: eran membranas entre versiones ligeramente diferentes de la realidad. No portales a otros mundos, sino acceso a variantes del mismo mundo.",
             "Esta comprensión, desarrollada en décadas de investigación solitaria, la colocó fuera de cualquier clasificación mágica existente."),
            ("La Torre del Espejo Negro",
             "La Torre donde se instaló Sethara fue construida por ella misma con cristales de espejo de propiedades inusuales. Desde fuera parecía ordinaria. Desde adentro, las superficies mostraban cosas que no estaban ahí.",
             "Los visitantes que entraban y salían de la Torre describían un estado de desorientación que tardaba días en resolverse. Los que se quedaban más de una semana generalmente no querían irse."),
            ("Lo que sus espejos revelaban",
             "Los espejos de Sethara podían mostrar el pasado de un lugar o una persona, las posibilidades de una situación y, en algunos casos, lo que otros no querían que fuera visible.",
             "Nunca cobró por esto. No porque fuera generosa sino porque el pago que le interesaba no era material."),
            ("El precio de sus revelaciones",
             "Lo que Sethara pedía a cambio de sus revelaciones era siempre lo mismo: la verdad del visitante. No sus secretos, que eran diferentes. Su verdad: lo que sabía sobre sí mismo pero no decía.",
             "La mayoría de los visitantes subestimaban este precio hasta que lo pagaban. Sethara recogía estas verdades y las guardaba. El valor de esa colección era incalculable."),
            ("La amenaza que representaba",
             "Las tres facciones la consideraban una amenaza porque sus espejos podían, en teoría, revelar cualquier cosa que quisieran mantener oculto. Intentaron neutralizarla en cuatro ocasiones.",
             "En las cuatro, sus agentes regresaron sin haber completado la misión, sin poder explicar exactamente por qué. Lo que describían era vagamente similar: entraron con certeza y salieron cuestionando esa certeza."),
            ("El fin de la Torre",
             "La Torre del Espejo Negro fue destruida hace ochenta años en circunstancias que ningún relato oficial describe con precisión. Sethara desapareció en el mismo evento.",
             "Los fragmentos de los espejos fueron dispersados deliberadamente. Los que los encontraron describían propiedades que los fragmentos no deberían tener según la física mágica conocida."),
            ("El eco persistente",
             "Décadas después de la destrucción de la Torre, hay reportes esporádicos de superficies reflectantes en Aethelgard que muestran brevemente cosas que no deberían estar mostrando.",
             "Los investigadores que han estudiado estos fenómenos no tienen explicación. La hipótesis más radical es que Sethara no desapareció sino que se distribuyó entre todos los espejos del mundo. Nadie puede probar que esto es incorrecto."),
        ]
    },
    {
        "nombre": "General Kord el Exterminador", "faccion": "Imperio", "clase": "Vanguardista",
        "era": "Clásica", "origen": "Academia Militar del Imperio",
        "entradas": [
            ("El mejor general del Imperio",
             "Por criterios puramente militares, Kord era posiblemente el mejor general que el Imperio produjo en su historia. Su tasa de victorias, sus innovaciones tácticas y su capacidad de logística eran extraordinarias.",
             "El problema era lo que hacía con esas victorias."),
            ("La política de tierra quemada",
             "Kord desarrolló e implementó la política de tierra quemada como herramienta de control: cualquier región que resistiera activamente al Imperio era destruida hasta el punto de no poder volver a ser una amenaza en generaciones.",
             "Era efectiva. También era una atrocidad que el Imperio eventualmente tuvo que reconocer, aunque tardó mucho en hacerlo."),
            ("El conflicto interno del Imperio",
             "No todos en el Imperio apoyaban los métodos de Kord. Había una facción que argumentaba que la victoria táctica que producían era menos valiosa que la enemistad permanente que generaban.",
             "Kord respondía que los muertos no se revelan. La historia demostraría que sus críticos tenían razón, pero esto tomó tiempo."),
            ("La destitución",
             "Kord fue destituido no por sus crímenes sino por sus éxitos: se volvió demasiado popular entre sus tropas para el gusto del liderazgo imperial, que temía lo que ese apoyo podía significar.",
             "La ironía que sus críticos señalaron: el Imperio lo destituyó no cuando hizo algo éticamente inaceptable sino cuando se volvió políticamente inconveniente. Esta distinción dice algo sobre las instituciones."),
            ("Los años de exilio",
             "Kord pasó sus últimos quince años en exilio interno en una provincia sin importancia estratégica. Escribió memorias que el Imperio clasificó inmediatamente y que circularon clandestinamente durante décadas.",
             "Las memorias son honestas sobre lo que hizo y por qué. No se disculpa, lo cual sus lectores encuentran más perturbador que si lo hiciera."),
            ("La sombra en la historia",
             "Kord es un problema para los historiadores: era un criminal de guerra y un genio militar en proporciones iguales. Estudiar sus tácticas sin contextualizar sus crímenes es incompleto. Contextualizar sus crímenes sin estudiar sus tácticas también lo es.",
             "Las academias militares del Imperio todavía usan sus manuales tácticos, con notas extensas sobre los crímenes que los acompañaron. Es incómodo. Es necesario."),
            ("El legado que nadie quiere",
             "Los territorios que Kord destruyó durante su carrera se recuperaron, eventualmente. Algunos tardaron generaciones. La memoria del daño permanece en forma de actitud hacia el Imperio que sus sucesores no han podido completamente revertir.",
             "La victoria de Kord en términos de territorio fue, en términos de relaciones, una derrota de largo plazo que el Imperio todavía paga."),
        ]
    },
]

# ── LUGARES DE AETHELGARD ────────────────────────────────────────────────────

LUGARES = [
    {
        "nombre": "La Ciudad de los Tres Puertos", "tipo": "ciudad",
        "faccion": "neutral",
        "entradas": [
            ("El lugar donde todo converge",
             "La Ciudad de los Tres Puertos no pertenece a ninguna facción porque ninguna facción pudo nunca establecer control suficiente sobre ella. Sus tres puertos sirven a las tres rutas comerciales principales, lo que hace que el control total fuera más costoso que la neutralidad.",
             "Esta neutralidad forzada se convirtió en identidad. Los habitantes de la Ciudad de los Tres Puertos son reconocibles en todo Aethelgard por su pragmatismo: manejan lo que es, no lo que debería ser."),
            ("El mercado de las tres plazas",
             "El corazón de la ciudad son sus tres plazas de mercado, una por cada puerto y cada una dominada por los mercaderes de la facción correspondiente. La cuarta plaza, en el centro, es donde los tres mercados se mezclan.",
             "Los precios en la cuarta plaza son siempre diferentes a los de las otras tres. Los comerciantes veteranos saben que los precios correctos están en la cuarta plaza porque son los que resultan de la competencia real."),
            ("La ley de la neutralidad",
             "La ciudad tiene un código legal propio que ninguna facción reconoce formalmente pero todas respetan en la práctica: la Ley de la Neutralidad establece que los conflictos entre facciones no pueden ejecutarse dentro de los límites de la ciudad.",
             "Hay guardias de la ciudad que son pagados por las tres facciones y no rinden cuentas a ninguna. Su única función es garantizar que la neutralidad se mantenga. Son extremadamente buenos en su trabajo."),
            ("El barrio de los sin facción",
             "Hay un barrio en la Ciudad de los Tres Puertos que los habitantes llaman el Barrio Libre: personas que eligieron no pertenecer a ninguna facción y que encontraron en esta ciudad el único lugar donde esa elección era viable.",
             "El Barrio Libre tiene sus propias instituciones, su propio mercado y su propio sistema de resolución de conflictos. Las tres facciones lo observan con una mezcla de tolerancia y perplejidad."),
            ("Peligros de la neutralidad",
             "La neutralidad de la ciudad tiene un costo: es también el lugar donde los agentes de las tres facciones operan más libremente que en cualquier otro territorio. La información fluye de maneras que serían imposibles en territorio controlado.",
             "Esto hace a la ciudad simultáneamente el lugar más informado y más peligroso de Aethelgard. Quienes saben navegar esta combinación prosperan. Quienes no, tienen problemas."),
        ]
    },
    {
        "nombre": "El Bosque de la Memoria", "tipo": "región natural",
        "faccion": "ninguna",
        "entradas": [
            ("El bosque que recuerda",
             "El Bosque de la Memoria, en las laderas del centro de Aethelgard, toma su nombre de una propiedad que los viajeros describen consistentemente: caminar bajo sus árboles evoca memorias con una vividez inusual.",
             "Los académicos estudian el fenómeno desde hace siglos sin llegar a un consenso. La teoría más aceptada: el bosque tiene una concentración de partículas de Eternium en el aire tan baja que es imperceptible pero suficiente para amplificar los procesos de memoria."),
            ("Los árboles como archivos",
             "Algunos investigadores han propuesto que los árboles del Bosque no solo amplifican la memoria del visitante sino que también almacenan las memorias de todos quienes han pasado por ahí.",
             "Si esto es cierto, el Bosque de la Memoria es el archivo más completo de Aethelgard, guardado en formas que ningún sistema de escritura puede replicar. La cuestión es si hay alguna forma de acceder a esas memorias que no sea caminando y esperando."),
            ("Los que se pierden",
             "Hay personas que entran al Bosque de la Memoria y no salen en el tiempo esperado. Eventualmente aparecen, generalmente en la salida opuesta a la que entraron, sin poder explicar qué ocurrió en el tiempo intermedio.",
             "Los reportes de estas personas comparten un elemento: describían haber seguido una memoria específica que los llevó más profundo de lo que planeaban ir."),
            ("Usos rituales",
             "Algunas comunidades de la región usan el Bosque de la Memoria para rituales de duelo: caminar en él mientras se piensa en quien se perdió genera recuerdos de esa persona con una claridad que el tiempo normal no permite.",
             "Este uso no está institucionalizado por ninguna facción pero es tolerado porque la alternativa sería controlar algo que prefieren no controlar."),
            ("La zona central",
             "La zona central del Bosque, donde los árboles son más antiguos, es evitada incluso por quienes frecuentan el área exterior. Los que han entrado describen memorias que no reconocen como propias.",
             "La explicación que algunos investigadores consideran posible: las memorias de personas muertas hace mucho tiempo se concentran en esa zona. Si es cierta, la zona central es literalmente un lugar donde el pasado está más presente que el presente."),
        ]
    },
    {
        "nombre": "La Ciudadela de Hierro", "tipo": "fortaleza",
        "faccion": "Imperio",
        "entradas": [
            ("La fortaleza inexpugnable",
             "La Ciudadela de Hierro es la instalación militar más imponente del Imperio: cuatro siglos de construcción continua, muros de tres metros de grosor, y una ubicación en el paso montañoso que hace imposible el asedio por tierra desde el norte.",
             "Nunca ha sido tomada por la fuerza. Dos veces fue tomada por traición interna. Ambas veces fue recuperada. El Imperio saco conclusiones sobre qué era más importante defender."),
            ("El interior de la Ciudadela",
             "El interior de la Ciudadela es una ciudad en sí misma: puede albergar veinte mil soldados de forma indefinida con sus propios sistemas de agua, producción de alimentos y manufactura de equipamiento.",
             "El diseño fue pensado para funcionar durante sieges de años. Las provisiones son rotadas sistemáticamente y el personal es entrenado para que la autosuficiencia sea un estado permanente, no de emergencia."),
            ("La biblioteca militar",
             "Dentro de la Ciudadela hay una biblioteca de estrategia y táctica militar que las tres facciones envidian. Cuatro siglos de batallas, campañas, errores y victorias documentados con precisión extraordinaria.",
             "El Imperio usa esta biblioteca para entrenar a sus generales. Lo que no dicen: también contiene los errores del Imperio, documentados con la misma precisión. La honestidad institucional de la Ciudadela es inusual para el Imperio."),
            ("El costo humano",
             "La Ciudadela fue construida a lo largo de siglos por trabajo forzado de comunidades conquistadas. Este hecho está documentado en los propios archivos del Imperio, aunque no en los documentos de acceso público.",
             "Los muros que nunca han sido derribados por el enemigo fueron levantados por personas que hubieran preferido que no existieran. Esta contradicción vive en la piedra."),
            ("La leyenda del pasaje secreto",
             "Hay una leyenda persistente sobre un pasaje secreto en la Ciudadela que conecta con un sistema de túneles bajo las montañas. El Imperio no confirma ni niega.",
             "Lo que sí es verificable: en las dos ocasiones en que la Ciudadela fue tomada por traición, el traidor escapó de una forma que los registros describen como <i>«por rutas no documentadas»</i>."),
        ]
    },
    {
        "nombre": "El Puerto de los Susurros", "tipo": "ciudad portuaria",
        "faccion": "Sindicato",
        "entradas": [
            ("La ciudad de la información",
             "El Puerto de los Susurros tiene ese nombre porque en sus calles, si uno sabe escuchar, puede encontrar cualquier información que circule en Aethelgard. No porque la ciudad lo provea oficialmente sino porque es el centro de redistribución de información no oficial de todo el continente.",
             "El Sindicato controla la ciudad de manera que las tres facciones aceptan porque las tres usan sus servicios."),
            ("El mercado de los secretos",
             "Hay un mercado en el Puerto de los Susurros donde se vende información. No en metáfora: hay puestos, precios, y hasta un sistema de garantía de calidad que el Sindicato mantiene con rigor casi académico.",
             "La información falsa se cobra al doble al proveedor cuando se detecta. Esto crea incentivos para la precisión que ningún sistema de honor o reputación solo podría sostener."),
            ("La arquitectura del secreto",
             "Los edificios del Puerto de los Susurros están diseñados de maneras que favorecen la conversación privada: habitaciones con aislamiento acústico, espacios de reunión con múltiples salidas, callejones que desaparecen en el mapa.",
             "Esta arquitectura no fue planificada centralmente sino que emergió orgánicamente en dos siglos de ciudad que necesitaba esas propiedades para funcionar."),
            ("Los guardianes invisibles",
             "La seguridad en el Puerto de los Susurros es diferente a cualquier otra ciudad: no hay una guardia visible. Hay una red de personas ordinarias que vigilan en nombre del Sindicato y que intervienen cuando es necesario.",
             "Esta seguridad invisible es más efectiva que la visible porque nadie sabe exactamente quiénes son los guardianes. La incertidumbre es el disuasivo."),
            ("El barrio de los archivos",
             "En las afueras del Puerto hay un barrio que los habitantes llaman los Archivos: edificios sin ventanas que guardan registros de información comprada, vendida y transferida durante dos siglos de operación del Sindicato.",
             "Acceder a esos archivos es una de las cosas más difíciles de hacer en Aethelgard. Hay personas que lo han intentado. El Sindicato tiene registros de los intentos también."),
        ]
    },
    {
        "nombre": "Las Ruinas de Valdorth", "tipo": "ruinas",
        "faccion": "ninguna",
        "entradas": [
            ("La ciudad que no debería haber caído",
             "Valdorth fue, hace seiscientos años, la ciudad más próspera de Aethelgard. Población de trescientas mil personas, infraestructura mágica avanzada y una academia que era considerada la mejor del mundo conocido.",
             "Cayó en cuarenta y ocho horas. Los registros contemporáneos son escasos y contradictorios. Lo que pasó en Valdorth es uno de los misterios más estudiados y menos resueltos de la historia de Aethelgard."),
            ("Lo que encontraron los primeros exploradores",
             "Los primeros exploradores que llegaron a Valdorth después de su caída encontraron algo que ninguno de sus relatos describe completamente: la ciudad estaba intacta físicamente pero vacía. Sin cuerpos. Sin señales de batalla. Sin evidencia de evacuación.",
             "La ciudad simplemente... no tenía habitantes. Todo lo demás estaba exactamente como si hubiera sido dejado por alguien que planeaba regresar."),
            ("Las teorías",
             "Las teorías sobre Valdorth son numerosas: un experimento mágico que salió mal, una apertura involuntaria al Vacío, un evento climático de proporciones sin precedentes, una evacuación tan rápida que dejó sin tiempo para tomar nada.",
             "La teoría más reciente, basada en análisis mágicos del suelo realizados hace veinte años, sugiere que algo consumió la energía vital de la ciudad en un instante. La fuente de ese algo sigue siendo desconocida."),
            ("Las ruinas hoy",
             "Las ruinas de Valdorth son hoy un sitio de estudio arqueológico bajo gestión conjunta de las tres facciones, uno de los pocos acuerdos de cooperación genuina que tienen.",
             "El sitio tiene propiedades mágicas residuales que los investigadores no han logrado clasificar completamente. Los aventureros que las visitan informan experiencias que no corresponden a ninguna categoría estándar."),
            ("Lo que nadie quiere encontrar",
             "La pregunta que los investigadores de Valdorth raramente hacen en público: sea lo que fuera lo que consumió la ciudad en cuarenta y ocho horas, ¿siguen en Aethelgard las condiciones que lo hicieron posible?",
             "La respuesta honesta es que nadie lo sabe. La respuesta oficial es que el evento fue único e irrepetible. La diferencia entre las dos respuestas es la política del miedo."),
        ]
    },
    {
        "nombre": "La Academia de Crystalhaven", "tipo": "institución académica",
        "faccion": "Alianza",
        "entradas": [
            ("El corazón del conocimiento",
             "La Academia de Crystalhaven fue fundada hace trescientos años con un objetivo simple: concentrar en un lugar todo el conocimiento disponible sobre magia y hacer que ese conocimiento fuera transmisible.",
             "Trescientos años después, es la institución académica más antigua en actividad continua de Aethelgard y tiene la colección de documentos mágicos más completa del mundo."),
            ("El proceso de selección",
             "La Academia selecciona a sus estudiantes no por capacidad mágica innata sino por capacidad de aprendizaje: los que más mejoran en un período de evaluación de tres meses, no los que llegan con más habilidades naturales.",
             "Esta política tiene dos consecuencias. La primera: la Academia tiene estudiantes de todos los orígenes sociales. La segunda: produce mágos que saben aprender, lo que resulta ser más valioso que mágos con talento natural pero sin disciplina."),
            ("La rivalidad con el Imperio",
             "La Academia de Crystalhaven y la Academia Imperial de Magia tienen una rivalidad académica que tiene doscientos años. Ambas producen trabajos de investigación de primera calidad. Ambas intentan ser las primeras en publicar cuando hay un descubrimiento importante.",
             "Sus investigadores se respetan y compiten simultáneamente, lo cual es la combinación correcta para producir ciencia de calidad."),
            ("La colección prohibida",
             "La Academia tiene una colección de materiales que no están en el catálogo público: obras sobre magia oscura, documentos capturados de practicantes como Malgrath, registros de experimentos fallidos que resultaron en daño.",
             "La colección existe porque los académicos creen que el conocimiento del peligro es necesario para entender el peligro. El acceso está restringido pero no prohibido: los investigadores con credenciales suficientes pueden acceder con aprobación del Consejo."),
            ("Los graduados que se fueron",
             "De los estudiantes que se gradúan de la Academia cada año, aproximadamente un tercio trabaja para la Alianza, un tercio se convierte en independiente y un tercio eventualmente termina en otras facciones.",
             "La Academia considera esto un éxito de su misión: forma personas que piensan por sí mismas, no seguidores de una institución. La Alianza tiene sentimientos más complicados sobre ese resultado específico."),
        ]
    },
    {
        "nombre": "El Mercado Flotante de Noria", "tipo": "mercado",
        "faccion": "neutral",
        "entradas": [
            ("El mercado que se mueve",
             "El Mercado Flotante de Noria no tiene ubicación fija: son ciento veinte barcazas conectadas entre sí que cambian de posición en el Mar Interior según las temporadas y las condiciones comerciales.",
             "Esto lo hace prácticamente imposible de gravar para las facciones porque nunca está completamente en el territorio de ninguna. Los comerciantes del Mercado consideran esto el mejor diseño de negocios de la historia."),
            ("Lo que se vende",
             "En el Mercado Flotante se puede encontrar casi cualquier cosa: productos de las tres facciones que raramente se encuentran en el mismo lugar, mercancías de regiones que las facciones no reconocen oficialmente y, ocasionalmente, cosas que nadie puede explicar completamente de dónde vienen.",
             "La regla no escrita: no se pregunta por el origen. La regla escrita: todo tiene que funcionar o el vendedor no puede volver."),
            ("La comunidad del Mercado",
             "Las ciento veinte familias que viven permanentemente en las barcazas del Mercado son su propia comunidad con su propio código de conducta, su propio sistema legal y su propia cultura.",
             "Se casan entre sí frecuentemente y rara vez establecen residencia en tierra. Su identidad es la barcaza, no ninguna ciudad o facción."),
            ("Los piratas y el Mercado",
             "El Mercado Flotante tiene un acuerdo no escrito con las rutas de piratería del Mar Interior: el Mercado provee información y acceso a materiales; los piratas protegen las rutas del Mercado.",
             "Las tres facciones saben que este acuerdo existe. Ninguna lo ha podido desmantelar sin destruir el Mercado mismo, que todas usan demasiado para poder prescindir."),
            ("Las noches del Mercado",
             "Las noches en el Mercado Flotante son legendarias entre viajeros: cuando las ciento veinte barcazas están ancladas juntas y las luces reflejan en el agua, el Mercado parece una ciudad flotante de cuento.",
             "Las historias que se cuentan alrededor de los fuegos de esas noches son una mezcla de lo que ocurrió realmente y lo que hubiera podido ocurrir. Los comerciantes no hacen la distinción."),
        ]
    },
    {
        "nombre": "El Templo de los Cinco Dioses", "tipo": "templo",
        "faccion": "neutral",
        "entradas": [
            ("La religión que no tiene religión",
             "El Templo de los Cinco Dioses es la institución religiosa más visitada de Aethelgard, lo cual es paradójico porque no tiene doctrina, sacerdotes que hagan prédicas o textos sagrados obligatorios.",
             "Lo que tiene: cinco cámaras, cada una dedicada a un principio que los fundadores identificaron como universal independientemente de la facción: creación, protección, sabiduría, comunidad y lo desconocido."),
            ("El quinto dios",
             "Las primeras cuatro cámaras son reconocibles. La quinta, dedicada a lo Desconocido, es la más visitada y la más difícil de describir.",
             "No hay imagen de ningún dios en esa cámara. Hay un espejo. El texto en la entrada dice: <i>«Lo que no conocemos no está fuera de nosotros. Está en lo que somos y no entendemos todavía.»</i>"),
            ("Las ofrendas",
             "Las ofrendas que los visitantes dejan en el Templo son inusualmente personales: no objetos de valor sino notas escritas, prendas con historia, objetos pequeños que significan algo específico para quien los deja.",
             "El Templo guarda estas ofrendas en archivos que nadie cataloga. Son simplemente guardadas. Lo que los visitantes encuentran significativo sobre esto varía exactamente en la forma en que las cosas significativas varían entre personas."),
            ("Las tres facciones y el Templo",
             "Las tres facciones tienen relaciones distintas con el Templo. La Alianza lo financia parcialmente y lo considera patrimonio cultural. El Imperio lo tolera como válvula de presión social útil. El Sindicato lo usa como lugar de reunión neutral.",
             "El Templo acepta todos los recursos y ninguna de las agendas."),
            ("Los custodios",
             "Los custodios del Templo son personas que eligieron dedicar un período de su vida al cuidado del lugar. No hacen votos permanentes: los períodos van de seis meses a tres años.",
             "Este modelo de servicio temporal produce una comunidad de custodios que viene de todos los orígenes y que eventualmente regresa al mundo con algo difícil de articular pero que los que los conocen describen como una presencia diferente."),
        ]
    },
    {
        "nombre": "La Torre del Horizonte", "tipo": "atalaya",
        "faccion": "ninguna",
        "entradas": [
            ("La torre que ve todo",
             "La Torre del Horizonte, construida en el punto más alto de la cadena montañosa central de Aethelgard, tiene una visibilidad en días claros que los cartógrafos calculan en trescientos kilómetros en todas las direcciones.",
             "Fue construida hace cuatrocientos años por una orden de observadores que ya no existe. Su propósito original se debate: los observadores dejaron registros de lo que veían pero no de por qué les importaba."),
            ("Los registros",
             "La Torre tiene en sus archivos cuatrocientos años de registros de observación continua. Lo que se observaba varió con el tiempo: formaciones militares en los primeros siglos, patrones climáticos después, fenómenos astronómicos, actividad mágica en los últimos tiempos.",
             "La continuidad de estos registros los hace invaluables para cualquier disciplina que necesite datos históricos de largo plazo."),
            ("La disputa por la Torre",
             "Las tres facciones quieren control de la Torre. Ninguna ha podido obtenerlo porque las otras dos siempre se alían para bloquear cualquier intento de control exclusivo.",
             "El resultado es una Torre administrada por un comité de las tres facciones que no se hablan directamente pero que firman los documentos de administración conjunta porque la alternativa es peor."),
            ("Lo que no está en los registros",
             "Los registros de la Torre tienen gaps: períodos donde las páginas están en blanco o donde las entradas son crípticas sin explicación. El período más largo de gaps es una semana entera hace ciento cincuenta años.",
             "Ese es el período del evento que los registros llaman, cuando lo mencionan, simplemente <i>«la semana»</i>. Nadie que estudiara los registros ha podido determinar qué ocurrió durante esa semana."),
            ("El vigía permanente",
             "La Torre siempre tiene un vigía. En cuatrocientos años, no ha habido ni un solo día donde la Torre estuviera sin nadie. El protocolo de relevos es el documento más meticulosamente seguido en la historia de la administración conjunta.",
             "Los vigías dicen que la Torre hace cosas. No mala fe: simplemente, que a veces, especialmente en las horas antes del amanecer, la Torre parece estar mirando más de lo que uno la está usando para mirar."),
        ]
    },
    {
        "nombre": "El Laberinto de Sal", "tipo": "maravilla natural",
        "faccion": "ninguna",
        "entradas": [
            ("El desierto de cristal",
             "El Laberinto de Sal es una formación natural en el sur de Aethelgard donde siglos de evaporación y cristalización han creado estructuras de sal de hasta cuarenta metros de altura con formas que desafían cualquier categoría geológica.",
             "Desde el aire, los navegantes aéreos han reportado que las formaciones forman patrones que parecen haber sido diseñados. Los geólogos insisten en que son naturales. Ambas cosas pueden ser ciertas."),
            ("Las propiedades del laberinto",
             "El Laberinto de Sal tiene propiedades acústicas únicas: los sonidos dentro de él se propagan de maneras que los física normales no predicen. Una conversación susurrada puede ser audible a cien metros en ciertas condiciones; una grito puede ser completamente silenciado.",
             "Los viajeros que lo han cruzado reportan desorientación, no porque el laberinto sea especialmente complicado, sino porque los ecos crean percepciones de fuentes de sonido que no están donde parecen estar."),
            ("El uso comercial",
             "El Sindicato ha usado el Laberinto de Sal para reuniones que requieren confidencialidad absoluta: en las zonas correctas, una conversación es prácticamente imposible de escuchar desde fuera.",
             "Las tres facciones saben que el Sindicato usa el laberinto con este propósito. Intentar seguirlos ahí ha resultado en expediciones que regresaron desorientadas, sin haber encontrado a nadie."),
            ("Los cristales de sal",
             "Las formaciones de cristal de sal más puras del Laberinto tienen propiedades menores de amplificación mágica. No suficientes para ser útiles en combate pero sí interesantes para investigación.",
             "Los académicos de las tres facciones tienen acuerdos de acceso al Laberinto para investigación. Es uno de los pocos sitios donde investigadores de facciones diferentes trabajan en el mismo lugar al mismo tiempo sin que resulte en incidentes."),
            ("La leyenda del centro",
             "Hay una leyenda sobre el centro del Laberinto de Sal: en el punto exacto central, hay una formación en forma de cámara perfectamente circular donde los sonidos no se propagan en absoluto.",
             "Los que afirman haberla encontrado describen una experiencia de silencio tan completo que resulta perturbador. Varios describen haber escuchado, en ese silencio absoluto, algo que no podía ser sonido. No todos acuerdan en qué era ese algo."),
        ]
    },
    {
        "nombre": "La Aldea de los Sanadores", "tipo": "comunidad",
        "faccion": "neutral",
        "entradas": [
            ("La única institución verdaderamente neutral",
             "La Aldea de los Sanadores, establecida hace doscientos años en un valle central de Aethelgard, es la única institución que las tres facciones reconocen formalmente como neutral en todo momento, incluyendo durante los conflictos armados.",
             "Esto no fue un acuerdo filosófico. Fue un acuerdo práctico: las tres facciones necesitaban un lugar donde enviar heridos que no pudieran tratar en campo y donde los médicos de alto nivel pudieran trabajar sin ser objetivos militares."),
            ("Los sanadores y su código",
             "Los sanadores de la Aldea tienen un código que tiene dos siglos de antigüedad y que se ha mantenido sin cambios sustanciales: tratan a quien necesita tratamiento. No hacen preguntas sobre facción, crimen o estado social.",
             "Este código ha sido puesto a prueba. En ocasiones, han tratado simultáneamente a personas que se buscaban mutuamente para hacerse daño. El protocolo en estos casos es exhaustivo y ha funcionado."),
            ("La formación médica",
             "La formación que ofrece la Aldea es la más completa disponible en Aethelgard para medicina no mágica. Acepta estudiantes de las tres facciones siempre que firmen el código de neutralidad médica.",
             "Aproximadamente el veinte por ciento de los médicos más calificados de las tres facciones fueron formados en la Aldea. Llevan con ellos el código, aunque algunos lo aplican con más rigor que otros."),
            ("La biblioteca médica",
             "La biblioteca médica de la Aldea es única en Aethelgard: contiene registros de tratamientos y casos de doscientos años, de pacientes de todas las facciones, condiciones y situaciones.",
             "Estos datos han permitido identificar patrones en la salud de Aethelgard que ninguna facción sola podría haber detectado. El análisis publicado por la Aldea cada cinco años es el informe de salud más completo y respetado del continente."),
            ("Los momentos de crisis",
             "La Aldea ha enfrentado tres momentos de crisis en su historia: intentos de una facción u otra de usarla estratégicamente durante un conflicto.",
             "En los tres casos, la respuesta de la Aldea fue la misma: declarar que abandonarían el sitio y los pacientes si la instrumentalización continuaba. En los tres casos, la facción retrocedió. Ambas partes sabían que la Aldea hablaba en serio."),
        ]
    },
]

# ── CRIATURAS DE AETHELGARD ──────────────────────────────────────────────────

CRIATURAS = [
    {
        "nombre": "El Gusano de Cristal", "tipo": "criatura de mazmorra",
        "zona": "Mazmorra Azul",
        "entradas": [
            ("Descripción",
             "El Gusano de Cristal es un invertebrado que habita en la Mazmorra Azul, donde ha evolucionado para prosperar en las condiciones de saturación de Eternium. Su cuerpo traslúcido muestra el flujo de energía mágica que procesa constantemente.",
             "Mide entre dos y cuatro metros. Se arrastra sin hacer sonido. Los aventureros que lo han enfrentado dicen que lo más aterrador es que no ves nada hasta que ya lo tienes encima."),
            ("Alimentación",
             "El Gusano de Cristal no se alimenta de carne sino de energía mágica. Se adhiere a superficies con alta concentración de Eternium y drena la energía a lo largo de días.",
             "Cuando está en presencia de un mago con magia activa, puede cambiar de objetivo. Los informes de magos que sienten sus hechizos debilitarse súbitamente antes de ver al gusano son consistentes con este comportamiento."),
            ("Comportamiento defensivo",
             "Cuando se siente amenazado, el Gusano de Cristal expulsa una descarga de energía mágica acumulada. No es controlada: es simplemente toda la energía almacenada liberada de una vez.",
             "Los efectos de esta descarga son impredecibles según el nivel de energía acumulado. Pueden ir desde un destello cegador hasta una explosión que re-estructura el túnel donde se encuentra."),
            ("Usos",
             "El tejido del cuerpo del Gusano de Cristal, una vez que muere, mantiene sus propiedades de conducción mágica por varios días. Los alquimistas lo usan como componente en trabajos que requieren una antena de energía mágica temporal.",
             "La dificultad es obviamente obtenerlo. El mercado de tejido de Gusano de Cristal tiene precios extraordinarios precisamente por esta razón."),
        ]
    },
    {
        "nombre": "El Roc de Fuego", "tipo": "criatura de superficie",
        "zona": "Región volcánica",
        "entradas": [
            ("El ave imposible",
             "El Roc de Fuego desafía la comprensión convencional de la biología: un ave de envergadura de quince metros que puede volar a pesar de producir temperaturas que debería hacerlo inviable.",
             "La respuesta que los investigadores han llegado a proponer: el Roc no produce calor, lo controla. Su cuerpo es capaz de canalizar el calor geotérmico de su entorno de maneras que los zoólogos todavía no entienden completamente."),
            ("Territorio",
             "Cada Roc de Fuego tiene un territorio de aproximadamente doscientos kilómetros cuadrados que defiende con agresividad extrema. La intersección de dos territorios es invariablemente un área de conflicto periódico.",
             "Los habitantes de las regiones volcánicas aprendieron hace generaciones a identificar los límites de los territorios del Roc y a construir sus comunidades fuera de ellos. El mapa de comunidades humanas en esas regiones corresponde casi exactamente al mapa de los territorios del Roc."),
            ("Nidificación",
             "Los nidos del Roc de Fuego son estructuras de roca volcánica fundida y soldificada que el propio Roc construye usando su control del calor. Son prácticamente indestructibles y duran siglos.",
             "Cuando un Roc muere, su nido permanece. Los nidos abandonados son a veces ocupados por comunidades humanas que valoran sus propiedades de retención de calor. La ironía de vivir en la casa de lo que alguna vez fue su mayor peligro no se les escapa a los habitantes."),
            ("El huevo de Roc",
             "El huevo de Roc es uno de los objetos más valiosos de Aethelgard. Su calor interno es constante durante años y puede usarse como fuente de energía estable. Los alquimistas que han trabajado con ellos dicen que la energía que contienen es diferente a cualquier otra fuente conocida.",
             "El problema es obtenerlos. El Roc defiende sus huevos con toda la energía que puede generar. Los relatos de intentos fallidos de obtener huevos son significativamente más numerosos que los relatos de intentos exitosos."),
        ]
    },
    {
        "nombre": "La Sombra Pensante", "tipo": "criatura del Vacío",
        "zona": "Mazmorra Negra",
        "entradas": [
            ("Lo que no tiene cuerpo",
             "La Sombra Pensante es uno de los pocos tipos de entidad en Aethelgard que los investigadores clasifican como 'sin sustrato físico definido': existe como patrón de energía que puede proyectarse en superficies pero no como materia.",
             "Esto la hace prácticamente imposible de combatir con métodos físicos. También la hace difícil de detectar hasta que decide que quiere ser detectada."),
            ("Inteligencia",
             "Las Sombras Pensantes son inteligentes. No de la forma en que un animal es inteligente, sino de una forma que los investigadores describen como 'diferente pero comparable'. Aprenden, recuerdan y adaptan su comportamiento.",
             "Lo que quieren es menos claro. Los que han interactuado con ellas sin ser atacados describen una curiosidad que se siente genuina. Los que fueron atacados no están disponibles para describir lo mismo."),
            ("Comunicación",
             "En al menos tres casos documentados, una Sombra Pensante ha intentado comunicarse con observadores humanos. El método es siempre el mismo: manipulación de sombras para formar imágenes o símbolos.",
             "Los intentos de descifrar esas comunicaciones han producido resultados contradictorios. La teoría más reciente: las Sombras no usan un lenguaje sino que intentan transferir conceptos directamente, y la traducción a lenguaje humano pierde información crítica."),
            ("El origen",
             "Las teorías sobre el origen de las Sombras Pensantes van desde 'entidades nativas del Vacío' hasta 'conciencias humanas que fueron consumidas por el Vacío y subsisten en él'. Ninguna puede ser probada con los métodos disponibles.",
             "La segunda teoría es, si es cierta, profundamente perturbadora. Algunos investigadores se niegan a estudiarla precisamente por eso."),
        ]
    },
    {
        "nombre": "El Oso de Eternio", "tipo": "criatura de superficie",
        "zona": "Bosques del norte",
        "entradas": [
            ("El oso que absorbe magia",
             "El Oso de Eternio es un oso que ha evolucionado en regiones de alta concentración de Eternium y que ha desarrollado la capacidad de absorber y almacenar energía mágica en su pelaje y tejido óseo.",
             "A primera vista parece un oso normal, lo cual es su mayor ventaja: nadie toma precauciones mágicas frente a lo que parece un oso normal hasta que los hechizos dejan de funcionar."),
            ("El efecto en los magos",
             "En presencia de un Oso de Eternio, la magia que los magos intentan usar se debilita o falla completamente. El oso está absorbiendo la energía antes de que pueda ser dirigida.",
             "Los magos que han sobrevivido encuentros con Osos de Eternio generalmente lo hicieron huyendo o usando habilidades físicas, no mágicas. Una lección que resulta humillante para quienes han invertido su vida en la magia."),
            ("La magia almacenada",
             "El pelaje y los huesos de un Oso de Eternio muerto contienen cantidades significativas de energía mágica almacenada. Los alquimistas que los trabajan describen el proceso como 'cosechar un cristal de Eternium muy irregular'.",
             "Hay un mercado para estos materiales. El Sindicato regula ese mercado porque las implicaciones de tener material que bloquea la magia disponible en grandes cantidades son demasiado significativas para ignorarlas."),
            ("Comportamiento social",
             "Contrario a los osos normales, los Osos de Eternio son parcialmente sociales: forman grupos de tres a cinco individuos que comparten territorio y, aparentemente, información. Cómo comparten información es desconocido.",
             "Los grupos parecen coordinar su comportamiento de maneras que no corresponden a ninguna señal observable. Los investigadores que los estudian a distancia segura los han llamado 'el mayor argumento para la comunicación mágica animal'."),
        ]
    },
    {
        "nombre": "La Medusa de Piedra", "tipo": "criatura de mazmorra",
        "zona": "Mazmorra Roja",
        "entradas": [
            ("El peligro inidentificable",
             "La Medusa de Piedra no tiene el aspecto que los cuentos le asignan: no es una mujer con serpientes por cabello. Es una criatura de apariencia completamente ordinaria que produce un campo de energía petrificante cuando se siente amenazada.",
             "El problema es que 'amenazada' incluye 'cuando algo se acerca a menos de diez metros'. Los aventureros que no saben esto aprenden la lección de la peor forma posible."),
            ("El campo petrificante",
             "El campo que emite la Medusa de Piedra no petrifica instantáneamente. Es progresivo: primero los extremidades se vuelven rígidas, luego el torso, finalmente el rostro. El proceso tarda aproximadamente dos minutos.",
             "Dos minutos es tiempo suficiente para escapar si uno lo sabe desde el principio. El problema es que la primera indicación del campo es la sensación de entumecimiento, que la mayoría de los aventureros atribuye al frío o al cansancio hasta que es demasiado tarde."),
            ("El antídoto",
             "La petrificación de la Medusa de Piedra es reversible si se aplica el antídoto correcto dentro de las veinticuatro horas. El antídoto existe, es costoso y requiere encontrar al petrificado antes de que el proceso complete.",
             "Los aventureros más experimentados que operan en la Mazmorra Roja llevan el antídoto estándar. Los menos experimentados aprenden sobre la Medusa de Piedra de la forma en que Aethelgard enseña muchas cosas: sobreviviendo el encuentro o no."),
            ("Ecología",
             "La Medusa de Piedra no es predadora en sentido estricto: no consume a sus víctimas petrificadas. Lo que hace con ellas no está completamente entendido, pero los investigadores han observado que las víctimas petrificadas que quedan en el territorio de la Medusa parecen drenarse lentamente de algo que los instrumentos miden como energía vital.",
             "Si esto es alimentación u otra cosa, los investigadores no están seguros. La Medusa de Piedra resulta difícil de estudiar de cerca."),
        ]
    },
    {
        "nombre": "El Leviatán del Mar Interior", "tipo": "criatura marina",
        "zona": "Mar Interior",
        "entradas": [
            ("La criatura más grande",
             "El Leviatán del Mar Interior es la criatura más grande de Aethelgard: los especímenes más grandes documentados alcanzan los cien metros de longitud. Su existencia fue cuestionada como mito durante siglos hasta que una nave completa encontró uno.",
             "La nave regresó. El capitán tardó una semana en poder hablar con coherencia sobre lo que había visto. Sus notas de esa semana existen y son el registro más completo de un encuentro con un Leviatán."),
            ("Comportamiento",
             "El Leviatán del Mar Interior no ataca barcos activamente a menos que se sienta amenazado o que los barcos interfieran con su ruta de migración. Los marineros que conocen las rutas de migración del Leviatán las evitan cuidadosamente.",
             "Las colisiones accidentales son raras. Cuando ocurren, generalmente resultan en la destrucción del barco. El Leviatán sigue su camino sin aparentemente notar el evento."),
            ("Las canciones del Leviatán",
             "El Leviatán produce vocalizaciones que los marineros llaman canciones. Se propagan por kilómetros bajo el agua y, en condiciones correctas, pueden escucharse desde barcos que están en superficie.",
             "Los músicos que han estudiado estas canciones dicen que tienen estructura pero que es diferente a cualquier música producida por criaturas que se han estudiado. La hipótesis de que son formas de comunicación entre Leviatanes es la más aceptada pero no ha podido probarse."),
            ("El ciclo de vida",
             "Lo que se sabe sobre el ciclo de vida del Leviatán es fragmentario: crecen muy lentamente, los especímenes más grandes tienen estimaciones de edad de varios siglos, y aparentemente solo se reproducen una vez cada varias décadas.",
             "Si la población es pequeña, como parece, son vulnerables a la extinción de maneras que los Leviatanes mismos no pueden saber. Los biólogos marinos llevan cincuenta años intentando hacer un censo de la población sin resultados definitivos."),
        ]
    },
    {
        "nombre": "El Espectro del Guerrero Caído", "tipo": "criatura no-muerta",
        "zona": "Campos de batalla históricos",
        "entradas": [
            ("No todos los muertos descansan",
             "Los campos de batalla antiguos de Aethelgard producen, en condiciones específicas, una forma de no-muerto que los investigadores llaman Espectro del Guerrero Caído: la manifestación de la identidad de alguien que murió en combate con tanta intensidad emocional que algo persiste.",
             "No son todos los muertos en batalla. Son los que murieron en un estado de conflicto interior específico: no la rabia pura sino una combinación de rabia y algo que no habían podido resolver."),
            ("Comportamiento",
             "Los Espectros del Guerrero Caído no atacan indiscriminadamente. Atacan a quienes se asemejan, en alguna forma que parece perceptible para ellos, a lo que no pudieron resolver en vida.",
             "Los aventureros que han interactuado con Espectros sin ser atacados reportan que había algo en ellos que el Espectro reconoció como diferente a lo que buscaba. Ninguno puede explicar qué era ese algo."),
            ("Comunicación posible",
             "En condiciones muy específicas, los Espectros pueden comunicarse. El método varía: algunos producen sonidos que se parecen al habla, otros manipulan el entorno para transmitir información simple.",
             "Los intentos de comunicación han producido resultados fragmentados. Lo que parece consistente: los Espectros tienen conciencia de su estado pero no entienden completamente su propia naturaleza."),
            ("El reposo",
             "Los Espectros del Guerrero Caído pueden descansar si se resuelve lo que los mantiene atados. El proceso es diferente para cada caso y requiere entender qué fue lo que no se resolvió en vida.",
             "Las personas que se especializan en esto se llaman, en la tradición oral, Pacificadores. No es una profesión reconocida por ninguna facción. Es un trabajo solitario, complicado y frecuentemente incomprendido."),
        ]
    },
    {
        "nombre": "El Dragón Antiguo Szarethon", "tipo": "dragón",
        "zona": "Montañas del Este",
        "entradas": [
            ("El que recuerda",
             "Szarethon tiene, según los cálculos académicos más conservadores, entre ochocientos y mil años. Es el dragón más antiguo de Aethelgard en existencia conocida y posiblemente el ser más antiguo del continente.",
             "Lo que esto significa en términos de conocimiento acumulado es difícil de exagerar. Szarethon ha observado la ascensión y caída de civilizaciones que los humanos conocen solo como ruinas."),
            ("La comunicación",
             "Szarethon ha demostrado capacidad de comunicación con humanos en siete ocasiones documentadas en los últimos trescientos años. No siempre en el mismo idioma: ha usado tres idiomas distintos, todos hablados por culturas que ya no existen.",
             "Lo que ha comunicado en esas siete ocasiones es objeto de estudio intenso. Los académicos coinciden en que transmitía información específica, no amenazas ni demandas. Qué información es objeto de debate porque los testigos reportaron cosas distintas."),
            ("El territorio de Szarethon",
             "El territorio de Szarethon cubre aproximadamente tres mil kilómetros cuadrados en las Montañas del Este. Las tres facciones lo reconocen de facto aunque ninguna lo reconoce oficialmente.",
             "No hay humanos viviendo en ese territorio. Las tres facciones tienen protocolos específicos para expediciones que entren: son raras, requieren aprobación especial, y los participantes firman documentos que reconocen que el territorio es de Szarethon."),
            ("El papel en la historia",
             "Los registros históricos mencionan a Szarethon en cinco eventos separados a lo largo de cuatrocientos años. En tres casos, intervino directamente. En dos casos, claramente no intervino aunque podía haberlo hecho.",
             "El patrón de cuándo interviene y cuándo no es objeto de estudio intenso. La única hipótesis que concuerda con todos los datos es que Szarethon tiene criterios para la intervención que no corresponden a ningún sistema ético humano."),
        ]
    },
    {
        "nombre": "El Wendigo de Niebla", "tipo": "criatura de superficie",
        "zona": "Pantanos del Norte",
        "entradas": [
            ("La criatura de la niebla",
             "El Wendigo de Niebla es prácticamente imposible de ver en condiciones normales porque su cuerpo tiene la misma opacidad y color que la niebla densa. Los registros visuales son escasos precisamente por este motivo.",
             "Lo que sí puede detectarse es su campo de frío: cinco metros a su alrededor, la temperatura baja entre quince y veinte grados. Esta caída de temperatura es la primera señal de presencia para quienes la conocen."),
            ("Caza",
             "El Wendigo de Niebla caza en los pantanos del norte durante las estaciones de niebla densa. Su método es simple: espera inmovilidad completa hasta que algo se acerque lo suficiente, luego actúa con velocidad que los testigos describen como instantánea.",
             "No tiene predadores conocidos. Sus presas naturales son los animales grandes del pantano, aunque en escasez puede atacar a humanos. Los habitantes del norte tienen rituales específicos para moverse en la niebla que están diseñados, sin que siempre lo sepan, para evitar al Wendigo."),
            ("Rareza",
             "Los Wendigos de Niebla son raros: la población total estimada en los pantanos del norte es de menos de cincuenta individuos. Esta rareza los hace objetos de fascinación académica y de miedo práctico en proporciones iguales.",
             "Los investigadores que intentan estudiarlos enfrentan el problema obvio: el entorno donde el Wendigo es mejor estudiado es también el entorno donde más peligrosos son."),
            ("El mito y la realidad",
             "Las leyendas sobre el Wendigo de Niebla en las comunidades del norte lo describen como el espíritu del invierno encarnado, una manifestación de la crueldad de la estación.",
             "Los investigadores tienen explicaciones más prosaicas sobre su origen y naturaleza. Los habitantes de las comunidades del norte escuchan las explicaciones prosaicas con paciencia y luego continúan contando las leyendas porque las leyendas comunican algo que las explicaciones científicas no capturan."),
        ]
    },
    {
        "nombre": "El Elemental de Eternium", "tipo": "elemental",
        "zona": "Minas de Crystalhaven",
        "entradas": [
            ("Energía que cobra vida",
             "Los Elementales de Eternium son el resultado de concentraciones de Eternium puro que han alcanzado un umbral de saturación de energía donde el mineral mismo comienza a exhibir comportamientos que los investigadores solo pueden describir como proto-conscientes.",
             "No tienen cuerpo en sentido convencional: son campos de energía mágica con estructura interna. Se detectan por el brillo azul intenso que emiten y por los efectos en los instrumentos de medición."),
            ("Peligrosidad en las minas",
             "Los Elementales de Eternium son la principal causa de accidentes en las minas de Crystalhaven que no son atribuibles a causas físicas convencionales. Cuando se sienten perturbados, liberan pulsos de energía que pueden colapsar infraestructura mágica, afectar instrumentos y dañar a los magos cercanos.",
             "Los mineros experimentados reconocen las señales de un Elemental en formación y evitan el área. Los nuevos en las minas aprenden esta detección temprana antes de cualquier otra habilidad."),
            ("Interacción posible",
             "En pocas ocasiones documentadas, los Elementales de Eternium han exhibido comportamiento que sugiere reconocimiento de presencias específicas: permanecen quietos frente a ciertos individuos mientras reaccionan a otros.",
             "Los académicos no tienen explicación para este comportamiento selectivo. La hipótesis más especulativa: los Elementales pueden percibir la firma mágica de las personas y tienen algún criterio, desconocido, para distinguir entre ellas."),
            ("Valor científico",
             "Un Elemental de Eternium estable es el objeto de estudio más valioso para los investigadores de energía mágica de Aethelgard. El problema es que el proceso de estudio tiende a destabilizarlos.",
             "El método que algunos investigadores han desarrollado para estudiarlos a distancia, usando sensores indirectos, ha producido los datos más completos disponibles sobre la naturaleza de la energía mágica en estado puro."),
        ]
    },
]

# ── ARTEFACTOS ────────────────────────────────────────────────────────────────

ARTEFACTOS = [
    {
        "nombre": "La Llave del Primer Rey", "tipo": "objeto único",
        "entradas": [
            ("Descripción",
             "La Llave del Primer Rey no tiene apariencia de llave: es un prisma de cristal del tamaño de una mano, de un material que no corresponde a ningún mineral catalogado, que emite una luz interior que no varía con la iluminación exterior.",
             "Los registros más antiguos que la mencionan tienen ochocientos años. Los registros anteriores a ese período que podrían contener información sobre su creación fueron destruidos en el Gran Incendio de la Biblioteca Central hace seiscientos años."),
            ("El misterio de su función",
             "Se llama llave pero nadie sabe qué abre. Los investigadores que la han examinado concuerdan en que emite energía mágica de alta concentración compatible con mecanismos de apertura, pero no hay estructura conocida en Aethelgard que corresponda a esa firma.",
             "La teoría más extendida: la estructura que abriría fue destruida. La alternativa más perturbadora: la estructura todavía existe pero nadie la ha encontrado."),
            ("Historial de propietarios",
             "La Llave ha pasado por docenas de manos en ochocientos años. Su historial de propietarios es notable: ninguno la tuvo por más de veinte años antes de que desapareciera o cambiara de manos por circunstancias que los historiadores describen como 'extraordinarias'.",
             "Actualmente está en posesión de la Academia de Crystalhaven, que la estudia y la guarda en una cámara cuya ubicación exacta conocen solo cinco personas."),
        ]
    },
    {
        "nombre": "El Manto de la Tormenta", "tipo": "armadura",
        "entradas": [
            ("La armadura que llama al rayo",
             "El Manto de la Tormenta es una capa de material que parece seda pero que no es seda, que almacena energía eléctrica atmosférica y la libera en forma de descargas controladas.",
             "Fue creado hace cuatrocientos años por una maga cuyo nombre los registros registran solo como 'La Tormenta', lo que sugiere que el manto y su creadora eran inseparables en la mente de sus contemporáneos."),
            ("Las limitaciones",
             "El Manto requiere condiciones atmosféricas específicas para funcionar a plena capacidad: en un día sin nubes, sus descargas son de baja potencia. En una tormenta natural, sus descargas pueden derribar edificios.",
             "La estrategia de quien lo usa bien: llevar la batalla a condiciones que favorezcan al Manto, no esperar que el Manto funcione en cualquier condición. Esto requiere más planificación que poder bruto."),
            ("Paradero actual",
             "El Manto desapareció hace ochenta años junto con su último propietario conocido, un explorador que salió en expedición al norte y no regresó. Las búsquedas han producido rastros pero no el objeto.",
             "El Sindicato tiene un encargo abierto para quien encuentre el Manto. El precio que ofrecen sugiere que lo que saben sobre su paradero es suficiente para saber que vale la búsqueda pero no suficiente para encontrarlo."),
        ]
    },
    {
        "nombre": "El Libro de los Espejos Rotos", "tipo": "grimorio",
        "entradas": [
            ("El libro que cambia",
             "El Libro de los Espejos Rotos tiene una propiedad inusual: su contenido no es fijo. Cada vez que se abre, muestra texto diferente. Los investigadores que lo han estudiado han catalogado cientos de textos distintos en un solo volumen.",
             "Si hay un patrón en lo que muestra en qué momento es algo que los investigadores llevan cien años intentando resolver. La hipótesis más respetada: muestra lo que el lector necesita ver en ese momento."),
            ("El peligro de leerlo",
             "No todos los textos que el Libro muestra son seguros de leer. Algunos investigadores han descrito estados de disociación, alucinaciones y, en dos casos, períodos de amnesia después de leer ciertas páginas.",
             "La regla que han establecido quienes lo estudian: nunca leerlo solo. Siempre con un observador que no lea el mismo texto y que pueda interrumpir si es necesario."),
            ("Origen desconocido",
             "El origen del Libro es desconocido. Los análisis del material confirman que tiene al menos quinientos años pero el proceso de fabricación no corresponde a ninguna escuela de encuadernación mágica conocida de ese período.",
             "La teoría más especulativa: fue creado fuera de Aethelgard. La segunda más especulativa: fue creado en Aethelgard por alguien cuya escuela de magia no tiene otros registros. Ambas implican algo que no se entiende todavía."),
        ]
    },
    {
        "nombre": "Las Cadenas del Tiempo", "tipo": "objeto mágico",
        "entradas": [
            ("La ilusión de control del tiempo",
             "Las Cadenas del Tiempo no controlan el tiempo. Lo que hacen es más sutil y en cierta forma más perturbador: ralentizan la percepción del portador hasta que el mundo exterior parece moverse a fracción de su velocidad normal.",
             "En términos prácticos, esto da al portador un tiempo de reacción que equivale, para los observadores externos, a velocidad sobrehumana. Para el portador, simplemente hay más tiempo para pensar."),
            ("El costo",
             "El costo de usar las Cadenas del Tiempo es proporcional al tiempo de uso: horas de percepción ralentizada resultan en un período de agotamiento mental equivalente. Los portadores que las usaban en exceso reportaban dificultad para funcionar en tiempo normal.",
             "El portador más famoso las usó durante una batalla entera. Ganó la batalla. Pasó los siguientes tres días sin poder procesar conversaciones normales porque el tiempo normal le parecía vertiginoso."),
            ("Paradero",
             "Las Cadenas del Tiempo están actualmente en posesión de la Alianza, que las mantiene en su archivo de artefactos de alto riesgo. Se prestan, con condiciones estrictas, para investigación académica.",
             "Hay un expediente de solicitudes de préstamo que tiene tres veces más solicitudes rechazadas que aprobadas. Los criterios de aprobación no son públicos."),
        ]
    },
    {
        "nombre": "El Arco de la Última Flecha", "tipo": "arma",
        "entradas": [
            ("El arco sin flechas",
             "El Arco de la Última Flecha no usa flechas físicas: genera proyectiles de energía condensada que impactan con la fuerza de una flecha de acero pero que no dejan rastro físico.",
             "La primera propiedad que los investigadores notaron es la segunda que los usuarios valoran: el Arco nunca se agota mientras haya energía mágica ambiental disponible. En campo abierto, es efectivamente ilimitado."),
            ("La propiedad del nombre",
             "El nombre del Arco no viene de sus propiedades de munición sino de una propiedad diferente: cada proyectil es guiado subconscientemente por la intención del arquero.",
             "Un arquero distraído falla con el Arco más que con uno convencional. Un arquero completamente enfocado en su objetivo tiene una precisión que los observadores describen como imposible. El Arco amplifica la intención, no el método."),
            ("Historial en batalla",
             "El Arco tiene un historial de doce batallas documentadas donde su uso resultó en un impacto decisivo. En todos los casos, el usuario era alguien con décadas de práctica en arquería convencional.",
             "Los intentos de principiantes de usarlo han resultado en proyectiles que van en todas las direcciones excepto la correcta. El Arco selecciona a sus usuarios tanto como sus usuarios lo seleccionan."),
        ]
    },
    {
        "nombre": "El Escudo del Primer Vanguardista", "tipo": "escudo",
        "entradas": [
            ("El escudo que recuerda",
             "El Escudo del Primer Vanguardista tiene propiedades de memoria: absorbe los impactos que recibe y los distribuye en su estructura de una manera que hace que el siguiente impacto del mismo tipo resulte en mayor resistencia.",
             "En términos prácticos: un escudo que ha bloqueado cien flechas resiste mejor la flecha número ciento y uno. Un escudo que ha bloqueado magia de fuego resiste mejor el próximo fuego. Aprende."),
            ("Los límites del aprendizaje",
             "El proceso de aprendizaje del Escudo tiene límites: puede resistir significativamente más daño del mismo tipo que un escudo convencional, pero los daños de tipos completamente diferentes al que ha absorbido no se benefician del aprendizaje.",
             "Los combatientes más efectivos con él estudian los tipos de daño del Escudo antes de llevarlo a situaciones nuevas. El Escudo es más útil cuando se conoce el enemigo de antemano."),
            ("La inscripción",
             "Hay una inscripción en el interior del Escudo que los traductores han descifrado parcialmente. La parte descifrada dice: 'Lo que se recibe sin romperse se convierte en fuerza'.",
             "La parte que no ha sido descifrada es más larga que la descifrada. Los lingüistas que trabajan en ella dicen que el idioma en que está escrita tiene características que no corresponden a ningún idioma conocido en Aethelgard."),
        ]
    },
    {
        "nombre": "La Corona de las Mareas", "tipo": "joya",
        "entradas": [
            ("Control sobre el agua",
             "La Corona de las Mareas permite a quien la porta controlar flujos de agua en un radio de cien metros. No crear agua de la nada sino dirigir la que existe: cambiar la dirección de corrientes, elevar mareas locales, detener el flujo de ríos temporalmente.",
             "En tierra, sus aplicaciones son defensivas o de ingeniería. En el mar, quien la lleva tiene una ventaja táctica que los marineros más experimentados describen como injusta."),
            ("El costo marino",
             "La Corona tiene un efecto secundario en uso prolongado en agua de mar: el portador comienza a sentir una conexión con el agua que los usuarios describen como 'el agua como parte de uno'. Inicialmente satisfactoria. Con el tiempo, perturbadora.",
             "Los portadores que la usaron durante años sin descanso describían dificultad para estar en tierra seca, como si su cuerpo echara de menos el agua. Algunos eligieron vivir en barcazas en lugar de en tierra firme."),
            ("Origen marino",
             "La Corona fue creada, según los registros más antiguos, por una comunidad que vivía sobre el Mar Interior antes de que el nivel del agua cambiara. Esa comunidad ya no existe.",
             "Los objetos que dejaron, incluyendo la Corona, son los únicos registros de su existencia. Los académicos que estudian la Corona intentan, a través de sus propiedades, entender a las personas que la crearon. Es arqueología a través de la magia."),
        ]
    },
    {
        "nombre": "El Reloj del Juicio Final", "tipo": "instrumento",
        "entradas": [
            ("El reloj que no mide el tiempo",
             "El Reloj del Juicio Final no mide el tiempo convencional. Mide, según los investigadores que lo han estudiado, algo que no tienen palabras para describir con precisión: la distancia entre el estado actual de Aethelgard y un estado que los investigadores llaman 'umbral crítico'.",
             "Lo que ese umbral representa es objeto de debate. El mecanismo del reloj sugiere que lo sabe, aunque no puede comunicarlo en forma comprensible."),
            ("El mecanismo",
             "El Reloj tiene doce agujas. Normalmente seis están en reposo y seis en movimiento. En los períodos previos a los grandes eventos históricos, más agujas se activan. En el año anterior a cada gran guerra de los últimos cuatro siglos, todas doce han estado en movimiento.",
             "Actualmente, ocho agujas están en movimiento. Los investigadores que saben esto no han llegado a consenso sobre qué implica."),
            ("El custodio del Reloj",
             "El Reloj tiene un custodio designado por acuerdo entre las tres facciones: alguien de neutralidad reconocida que mantiene el Reloj, registra sus estados y comparte la información con las tres facciones sin interpretación.",
             "El custodio actual lleva doce años en el cargo. Dice que el trabajo lo ha cambiado. No puede explicar exactamente cómo. Solo dice que mira el mundo de forma diferente."),
        ]
    },
]

# ── EVENTOS HISTÓRICOS ────────────────────────────────────────────────────────

EVENTOS_HISTORICOS = [
    {
        "nombre": "La Primera Gran Guerra", "era": "hace 400 años",
        "facciones": ["Alianza", "Imperio"],
        "entradas": [
            ("El inicio",
             "La Primera Gran Guerra comenzó por un malentendido diplomático que ninguna de las dos partes quería que se convirtiera en guerra pero que ninguna supo detener a tiempo. La chispa fue el asesinato de un embajador de la Alianza en territorio Imperial, que el Imperio negó haber ordenado.",
             "La investigación posterior determinó que el asesinato fue obra de un tercer actor que se beneficiaba del conflicto. Para cuando esto quedó establecido, la guerra llevaba tres años."),
            ("El desarrollo",
             "La Primera Gran Guerra duró ocho años y fue la más costosa en vidas humanas de los últimos cuatro siglos. Las innovaciones tácticas que produjo en ambos lados transformaron la forma de hacer la guerra en Aethelgard.",
             "Los historiadores la llaman el primer conflicto moderno: fue la primera guerra en que la logística determinó el resultado más que las batallas individuales."),
            ("El final",
             "La guerra terminó no por derrota militar de ninguna de las partes sino por agotamiento mutuo y una crisis interna en el Imperio que requirió retirar recursos del frente.",
             "El tratado de paz fue negociado durante un año y produjo un documento de cuarenta páginas que las dos facciones firmaron con alivio y resentimiento en proporciones iguales. Ese resentimiento tardó dos generaciones en disolverse."),
        ]
    },
    {
        "nombre": "La Fundación del Sindicato", "era": "hace 300 años",
        "facciones": ["Sindicato"],
        "entradas": [
            ("El origen",
             "El Sindicato no fue fundado en un momento específico por personas con un plan específico. Emergió gradualmente de una red de comerciantes, informantes y operadores independientes que reconocieron que colaborar era más rentable que competir.",
             "El momento que los historiadores del Sindicato consideran su fundación formal es cuando acordaron un código de conducta común. No un contrato filosófico sino un acuerdo práctico sobre qué cosas no se hacían."),
            ("La negociación con las facciones",
             "El Sindicato negoció su reconocimiento tácito con las tres facciones en sus primeros veinte años. Cada facción prefería tener un interlocutor único para las operaciones de información y comercio gris que múltiples actores incontrolables.",
             "La negociación fue larga y complicada. El Sindicato salió de ella con más autonomía de la que cualquier facción hubiera aceptado de saber exactamente lo que estaban aprobando."),
            ("La estructura",
             "La estructura del Sindicato fue diseñada desde el principio para ser resiliente a los intentos de desmantelamiento: descentralizada, con múltiples líneas de autoridad y sin ningún punto único de falla.",
             "Los tres intentos de las facciones de desmantelarlo en sus primeros cincuenta años fracasaron por exactamente esta razón. Después del tercer intento, las facciones decidieron que trabajar con él era más sensato que contra él."),
        ]
    },
    {
        "nombre": "El Gran Terremoto de Aethelgard Central", "era": "hace 200 años",
        "facciones": [],
        "entradas": [
            ("El evento",
             "El Gran Terremoto de hace doscientos años fue el desastre natural más destructivo en la historia registrada de Aethelgard. Cuatro ciudades medianas y cuarenta aldeas destruidas. Las cifras de víctimas mortales que los historiadores consideran más fiables: entre ochenta y cien mil personas.",
             "Las causas geológicas son bien entendidas: una liberación de presión en una falla que los geólogos sabían que existía pero cuya inestabilidad habían subestimado. La estimación de inestabilidad fue revisada después del terremoto."),
            ("La respuesta",
             "El terremoto produjo el período de cooperación más intensa entre las tres facciones en los últimos doscientos años. No por razones filosóficas sino porque el desastre era demasiado grande para cualquier facción sola.",
             "Los historiadores llaman a los diez años que siguieron la Era de la Cooperación Forzada. Las instituciones que se crearon para coordinar la respuesta al desastre sobrevivieron en algunos casos hasta hoy, con mandatos que se han ampliado pero que conservan las estructuras originales."),
            ("El legado",
             "El terremoto cambió permanentemente el diseño de construcción en Aethelgard: los estándares de resistencia sísmica que se adoptaron en su respuesta son la base de los estándares actuales.",
             "También cambió la actitud de las facciones hacia la cooperación en emergencias: los mecanismos que establecieron, aunque imperfectos, funcionaron. Recordar que habían funcionado facilitó su uso en emergencias posteriores."),
        ]
    },
    {
        "nombre": "La Conspiración de los Cien Días", "era": "hace 150 años",
        "facciones": ["Alianza", "Imperio", "Sindicato"],
        "entradas": [
            ("El complot",
             "La Conspiración de los Cien Días fue el intento de coordinación más elaborado entre actores de las tres facciones para eliminar simultáneamente a los líderes de las tres y reemplazarlos con personas coordinadas entre sí.",
             "El plan falló porque fue filtrado por un agente del Sindicato que consideró que el resultado beneficiaría a algunos miembros del Sindicato pero no a la organización en conjunto."),
            ("La investigación",
             "La investigación que siguió tardó dos años y fue conducida simultáneamente por las tres facciones, que en este caso tenían el mismo interés. Los resultados nunca fueron publicados completamente.",
             "Lo que sí se sabe: los conspiradores venían de los tres facciones, habían trabajado durante cinco años para coordinar el plan y habían llegado más cerca de lo que cualquier facción admite de completarlo."),
            ("Las consecuencias",
             "Las consecuencias incluyeron purgas internas en las tres facciones, cambios en los protocolos de seguridad para el liderazgo y un período de desconfianza agudizada entre los agentes de inteligencia de las tres organizaciones.",
             "El período de desconfianza se superó eventualmente. Los protocolos de seguridad permanecen. Y hay un expediente conjunto de las tres facciones sobre la conspiración que ninguna ha querido abrir públicamente desde entonces."),
        ]
    },
    {
        "nombre": "La Plaga de los Cristales", "era": "hace 80 años",
        "facciones": [],
        "entradas": [
            ("La enfermedad de lo mágico",
             "La Plaga de los Cristales fue una enfermedad que atacaba específicamente a las personas con capacidades mágicas activas: los hechizos que intentaban usar se volvían inestables y los propios tejidos del usuario comenzaban a cristalizarse.",
             "La causa fue eventualmente identificada como un parásito mágico de origen desconocido. El cómo llegó a Aethelgard sigue siendo incierto."),
            ("El impacto",
             "En dos años de propagación, la Plaga de los Cristales eliminó aproximadamente el cuarenta por ciento de los practicantes mágicos activos en las regiones afectadas. El impacto en la capacidad mágica de Aethelgard fue sustancial.",
             "Las academias mágicas de las tres facciones perdieron cuerpos docentes, investigadores activos y estudiantes avanzados en números que tardaron una generación en recuperar."),
            ("La solución",
             "La cura fue desarrollada conjuntamente por investigadores de las tres facciones en la única instancia de investigación médica completamente colaborativa de la historia de Aethelgard.",
             "El proceso de colaboración produjo tensiones considerables. También produjo resultados en la mitad del tiempo que hubiera tomado cualquier facción sola. Los investigadores que participaron en él dicen que fue la experiencia más difícil y más satisfactoria de sus carreras."),
        ]
    },
]

# ── LORE MISCELÁNEO ───────────────────────────────────────────────────────────

LORE_MISCELANEO = [
    # Economía y comercio
    ("💰 <b>CRÓNICAS DE AETHELGARD</b>\n<i>El Sistema Monetario — Tres Monedas, Un Mundo</i>\n\nAethelgard tiene tres monedas principales: el oro, que ha servido como referencia de valor durante siglos; el Eternium, que vale el doble en pureza equivalente y que respalda las transacciones de mayor valor; y los Créditos del Vacío, una creación relativamente reciente del Sindicato que no tiene valor intrínseco pero que el Sindicato garantiza con su reputación.\n\nLa coexistencia de tres monedas crea complejidades: los tipos de cambio fluctúan, las tres facciones tienen incentivos diferentes para manipular el valor de las monedas que controlan, y los mercados fronterizos son laboratorios de economía donde los comerciantes más hábiles hacen fortunas en los espacios entre sistemas.\n\n<i>«El mejor inversor de Aethelgard no es quien sabe qué vale cada moneda sino quien sabe cuándo cada moneda valdrá diferente.»</i>"),
    
    ("💰 <b>CRÓNICAS DE AETHELGARD</b>\n<i>El Mercado de Subastas — Donde el Valor se Negocia</i>\n\nEl sistema de subastas de Aethelgard tiene una historia que pocos conocen: comenzó como un mecanismo para vender equipamiento capturado en conflictos, cuando las facciones necesitaban convertir en oro cosas que no podían usar.\n\nEvolucionó en dos siglos hasta convertirse en el mecanismo de formación de precio más eficiente para artículos únicos o raros. La subasta no determina lo que algo vale: determina cuánto están dispuestos a pagar los que quieren algo en un momento dado, que es una cosa completamente diferente.\n\nLos mejores vendedores en subastas no buscan el precio más alto posible. Buscan el precio óptimo: el punto donde el comprador siente que ganó y el vendedor sabe que ganó más."),
    
    ("💰 <b>CRÓNICAS DE AETHELGARD</b>\n<i>Los Bancos de Gremio — Confianza como Capital</i>\n\nLos bancos de gremio existen porque los gremios necesitaban un lugar donde guardar recursos colectivos sin que ningún miembro individual los controlara. La solución que emergió fue elegante: un fondo común con reglas de acceso que ningún miembro podía cambiar solo.\n\nLo que convirtió a los bancos de gremio en instituciones poderosas fue algo que nadie planificó: la confianza que generaban. Un gremio con un banco bien administrado podía hacer promesas que los gremios sin banco no podían. Y las promesas creaban oportunidades.\n\n<i>El capital más valioso de cualquier institución no es el que puede contarse. Es el que hace que los demás quieran trabajar con ella.</i>"),
    
    ("💰 <b>CRÓNICAS DE AETHELGARD</b>\n<i>El Comercio P2P — La Economía de la Confianza Directa</i>\n\nEl intercambio directo entre personas, sin intermediarios, existe desde que existió el comercio. Lo que cambió en las últimas décadas fue su escala: las redes de comunicación del Sindicato y los sistemas de garantía que desarrollaron hicieron posible el comercio directo entre personas que nunca se habían visto.\n\nEl sistema P2P tiene una característica que los mercados formales no tienen: el comprador y el vendedor negocian directamente, sin intermediarios que capturan parte del valor. Esto hace los precios más justos en ambas direcciones.\n\nEl riesgo también es directo: no hay institución a quien reclamar si algo sale mal. Los participantes experimentados desarrollan sistemas propios de verificación que son a veces más efectivos que los formales."),
    
    # Magia y alquimia
    ("⚗️ <b>CRÓNICAS DE AETHELGARD</b>\n<i>Las Clases de Magia — Una Taxonomía en Disputa</i>\n\nLos académicos de las tres facciones llevan doscientos años discutiendo cómo clasificar la magia. El problema es que cada sistema de clasificación que proponen refleja los intereses de quien lo propone: la Academia de la Alianza clasifica por fuente y principio; la Academia Imperial por efecto y aplicación; el Sindicato, cuando participa en la discusión, por utilidad práctica.\n\nLo que estas clasificaciones revelan sobre sus creadores es más interesante que las clasificaciones mismas. La forma en que una institución organiza el conocimiento refleja qué valora en ese conocimiento.\n\nEl mago práctico ignora todas las clasificaciones y aprende lo que necesita. El teórico se pierde en las clasificaciones. Ambos son necesarios."),
    
    ("⚗️ <b>CRÓNICAS DE AETHELGARD</b>\n<i>El Eternium — El Mineral que Cambió el Mundo</i>\n\nAntes del descubrimiento del Eternium hace cuatrocientos años, la magia en Aethelgard era más artesanal: dependía del talento individual, los materiales naturales y técnicas transmitidas de maestro a estudiante. El Eternium cambió esto al proporcionar un amplificador estable y reproducible.\n\nEl acceso al Eternium es hoy el factor determinante de la capacidad mágica de cualquier organización o individuo. Las minas donde se extrae son los activos más disputados de Aethelgard.\n\nLos filósofos de la magia señalan a veces una ironía: el Eternium hizo la magia más accesible y más poderosa, pero también la hizo más dependiente de la economía y la política. Antes era un arte. Ahora también es una industria."),
    
    ("⚗️ <b>CRÓNICAS DE AETHELGARD</b>\n<i>La Alquimia — Ciencia en los Márgenes</i>\n\nLa alquimia ocupa un espacio incómodo en el mundo de Aethelgard: no es ni magia pura ni ciencia física pura, sino la zona donde ambas se superponen. Los magos la ven como ciencia menor; los científicos físicos la ven como magia supersticiosa. Los alquimistas tienen una opinión más alta de sí mismos que cualquiera de los dos grupos anteriores.\n\nLo que la alquimia produce que ninguna de las disciplinas puras puede producir sola: transformaciones. No crear algo de la nada ni aplicar energía a algo existente, sino cambiar fundamentalmente la naturaleza de los materiales.\n\nAlgunos de los artefactos más valiosos de Aethelgard son producto de la alquimia, y sus creadores son personas que dominaban tanto la ciencia como la magia y que no consideraban que la distinción importara."),

    # Gremios
    ("🏰 <b>CRÓNICAS DE AETHELGARD</b>\n<i>El Origen de los Gremios — La Cooperación como Supervivencia</i>\n\nLos primeros gremios de aventureros no se fundaron por ideología sino por necesidad: las mazmorras más difíciles no podían ser completadas por individuos solos, y los grupos improvisados de desconocidos fallaban con demasiada frecuencia porque no se conocían entre sí.\n\nLa solución que emergió fue el gremio: un grupo con historia compartida, confianza construida y roles entendidos. Los primeros gremios no tenían formalismos. Eran simplemente grupos de personas que preferían trabajar juntos.\n\nLa formalización vino después, cuando los gremios grandes necesitaban estructuras para coordinar a más personas de las que cualquier fundador podía conocer personalmente. Los documentos fundacionales son intentos de codificar lo que funcionaba informalmente."),
    
    ("🏰 <b>CRÓNICAS DE AETHELGARD</b>\n<i>Las Guerras de Gremios — El Conflicto que No Debería Existir</i>\n\nLas guerras entre gremios son uno de los fenómenos que los líderes más respetados de Aethelgard consideran el mayor desperdicio que existe: recursos dedicados a destruir a quienes comparten objetivos fundamentalmente similares.\n\nAun así ocurren. Las razones son usualmente territoriales (control de mazmorras o rutas de recursos), pero el análisis de los registros muestra que la causa profunda suele ser más simple: egos que no pudieron llegar a un acuerdo cuando era posible hacerlo sin costo.\n\nLos gremios que han sobrevivido más tiempo son, consistentemente, los que desarrollaron mecanismos para resolver conflictos internos y con otros gremios sin llegar a la guerra. La supervivencia selecciona a favor de la diplomacia."),

    # Vida cotidiana
    ("🌾 <b>CRÓNICAS DE AETHELGARD</b>\n<i>La Cocina de Aethelgard — Lo que se Come Define lo que se Es</i>\n\nCada región de Aethelgard tiene una cocina propia determinada por sus recursos, su clima y su historia. Las zonas volcánicas del sur cocinan con especias de intensidad que los habitantes del norte describen como veneno y que los del sur consideran medicina. Las ciudades costeras tienen ciento veinte preparaciones distintas de pescado que los interiores nunca aprenderán a distinguir.\n\nLas cocinas de las tres facciones reflejan sus valores: el Imperio es formal y por curso, con reglas estrictas sobre qué va con qué; la Alianza es variada y experimental; el Sindicato tiene una cocina de viaje, diseñada para conservarse y prepararse en cualquier condición.\n\nLas mejores comidas de Aethelgard ocurren en las fronteras, donde las tradiciones se mezclan sin reglas."),
    
    ("🌾 <b>CRÓNICAS DE AETHELGARD</b>\n<i>Las Estaciones y los Rituales</i>\n\nAethelgard tiene cuatro estaciones marcadas, y cada una tiene sus rituales tanto civiles como mágicos. El inicio del invierno es el único momento en que las tres facciones tienen simultáneamente un período de tregua no formal: no por acuerdo político sino por tradición tan antigua que nadie recuerda cuándo comenzó.\n\nDurante esa semana, los conflictos activos se suspenden, el comercio cruza fronteras que normalmente están cerradas y la gente de facciones enemigas se cruza en mercados fronterizos sin incidentes.\n\nLos historiadores debaten si esto ocurre porque las personas son mejores de lo que sus instituciones les permiten ser normalmente, o porque el invierno las hace pragmáticamente dependientes unas de otras. Posiblemente ambas cosas."),
    
    # Vacío y misterios
    ("🌀 <b>CRÓNICAS DE AETHELGARD</b>\n<i>El Vacío — Lo que Existe Fuera de Aethelgard</i>\n\nEl Vacío no es el espacio entre las estrellas. Es algo diferente que existe en relación con Aethelgard pero no como parte de él: un plano donde las reglas físicas de Aethelgard aplican de forma diferente o no aplican en absoluto.\n\nLo que se sabe con certeza sobre el Vacío es poco: que existe, que tiene entidades, que el Eternium viene de él, que acceder a él es posible pero peligroso, y que las entidades que lo habitan son conscientes de Aethelgard de maneras que Aethelgard apenas empieza a entender.\n\nLo que se especula es mucho más y más interesante. Y también más perturbador."),
    
    ("🌀 <b>CRÓNICAS DE AETHELGARD</b>\n<i>Los Créditos del Vacío — Magia como Moneda</i>\n\nLos Créditos del Vacío son la innovación financiera más controversial de los últimos cien años: una moneda respaldada no por metal ni por promesas de estado sino por energía del Vacío almacenada en formas que los alquimistas del Sindicato desarrollaron.\n\nSu valor es estable de formas que el oro no puede ser porque su respaldo no depende de la economía física de Aethelgard. Las crisis que hacen fluctuar el oro no afectan los Créditos de la misma manera.\n\nPero tienen una propiedad que los usuarios sofisticados conocen: acumular demasiados Créditos del Vacío en un mismo lugar tiene efectos secundarios en el entorno que los investigadores mágicos describen como 'perturbaciones locales del tejido de la realidad'. El Sindicato no lo anuncia como primera característica del producto."),
    
    ("🌀 <b>CRÓNICAS DE AETHELGARD</b>\n<i>El Ciclo del Eternium — De Dónde Viene y Adónde Va</i>\n\nEl Eternium que se extrae de las minas de Aethelgard viene originalmente del Vacío: se forma cuando la energía del Vacío entra en contacto con ciertos minerales bajo condiciones específicas de presión y tiempo.\n\nEsto significa que las minas de Eternium son esencialmente lugares donde el Vacío y Aethelgard interactúan de forma pasiva. Los investigadores que entendieron esto primero lo encontraron maravilloso. Después encontraron que tenía implicaciones que preferían no haber entendido.\n\nLa pregunta que les quita el sueño: ¿si el Eternium es energía del Vacío cristalizada, qué ocurre cuando esa energía es usada y regresa al sistema? ¿Adónde va?"),

    # Facciones
    ("⚔️ <b>CRÓNICAS DE AETHELGARD</b>\n<i>La Alianza — Una Federación de Voluntades</i>\n\nLa Alianza es técnicamente una federación: un conjunto de comunidades, ciudades y territorios que acordaron en algún momento de su historia compartir defensa, comercio y ciertos estándares de gobernanza.\n\nLo que la hace única entre las tres facciones es que su cohesión depende más del acuerdo continuo que de la imposición central. Si suficientes miembros decidieran que no quieren seguir siendo parte, la Alianza se disolvería.\n\nSus defensores dicen que esto la hace más legítima. Sus críticos dicen que la hace más frágil. Ambos tienen razón, lo que convierte a la Alianza en la facción más interesante de estudiar desde perspectivas opuestas."),
    
    ("⚔️ <b>CRÓNICAS DE AETHELGARD</b>\n<i>El Imperio — El Peso del Orden</i>\n\nEl Imperio cree en el orden. No como un valor abstracto sino como el requisito práctico para que nada mejor sea posible. Sin orden, argumentan sus teóricos, no hay comercio estable, no hay ciencia sostenida, no hay arte que dure.\n\nEl problema filosófico con este argumento es que el orden que el Imperio impone es específicamente el orden que beneficia a quienes ya tienen poder. Sus defensores dicen que cualquier orden tiene este problema. Sus críticos dicen que algunos órdenes lo tienen menos.\n\nA nivel práctico: el Imperio produce infraestructura que otras formas de organización no pueden. También produce injusticias que otras formas de organización distribuirían de manera diferente. Cuál de los dos hechos importa más depende de quién lo evalúa."),
    
    ("⚔️ <b>CRÓNICAS DE AETHELGARD</b>\n<i>El Sindicato — La Tercera Fuerza</i>\n\nEl Sindicato no es una facción como las otras dos. No controla territorio, no tiene ejército regular y no hace declaraciones de principios filosóficos. Lo que tiene es algo que ninguna facción puede construir tan fácilmente: información y la capacidad de moverla.\n\nEn un mundo donde las dos facciones grandes se necesitan pero no pueden confiar entre sí, el Sindicato ocupa el espacio entre ellas. No como árbitro, no exactamente, pero como la entidad que hace posibles ciertas transacciones que de otra forma no ocurrirían.\n\nSu poder es proporcional a lo indispensable que resulta. Su estrategia principal consiste en no dejar de serlo nunca."),

    # Mazmorras adicionales
    ("🗺️ <b>CRÓNICAS DE AETHELGARD</b>\n<i>Las Cuatro Mazmorras — Un Sistema</i>\n\nLas cuatro mazmorras principales de Aethelgard no son accidentes geográficos independientes. Los investigadores que han estudiado sus energías durante los últimos cincuenta años han comenzado a articular algo que los aventureros experimentados saben intuitivamente: las cuatro están relacionadas.\n\nNo físicamente, no siempre. Sino en términos de los patrones de energía que emiten, la forma en que las criaturas que las habitan responden a los mismos eventos externos y la manera en que sus propiedades cambian en sincronía cuando hay eventos mágicos mayores.\n\nSi son partes de un sistema, la pregunta es para qué sirve el sistema."),
    
    ("🗺️ <b>CRÓNICAS DE AETHELGARD</b>\n<i>La Economía de las Mazmorras</i>\n\nLas mazmorras de Aethelgard son peligrosas. También son la fuente principal de recursos que no pueden obtenerse de otra forma: Eternium de alta concentración, materiales de criaturas raras, artefactos de eras anteriores.\n\nEsta combinación crea una economía específica: aventureros que arriesgan sus vidas para extraer recursos, comerciantes que convierten esos recursos en productos útiles, y compradores de todas las facciones que dependen de esos productos para cosas que van desde el equipamiento militar hasta la medicina.\n\nLas mazmorras son, en términos económicos, la industria extractiva más rentable y más costosa en vidas de Aethelgard. La pregunta sobre si el intercambio vale la pena es respondida diferente por quienes arriesgan las vidas y quienes compran los productos."),
]

# ═══════════════════════════════════════════════════════════════════════════════
# GENERACIÓN DE MENSAJES
# ═══════════════════════════════════════════════════════════════════════════════

def _msg(icon, titulo, subtitulo, parrafos):
    cuerpo = "\n\n".join(parrafos)
    return f"{icon} <b>CRÓNICAS DE AETHELGARD</b>\n<i>{titulo} — {subtitulo}</i>\n\n{cuerpo}"


def _generar_mensajes_personajes(pool):
    msgs = []
    for p in pool:
        icon = "⚔️" if p.get("clase") in ("Vanguardista",) else ("🔮" if "Tejehechizos" in p.get("clase","") else "🗡️")
        for aspecto, p1, p2 in p["entradas"]:
            texto = _msg(icon, p["nombre"], aspecto, [p1, p2])
            msgs.append((texto, "personajes"))
    return msgs


def _generar_mensajes_lugares(pool):
    msgs = []
    for lugar in pool:
        icon = "🏙️" if lugar["tipo"] in ("ciudad","ciudad portuaria") else ("🌿" if lugar["tipo"] == "región natural" else "🗺️")
        for aspecto, p1, p2 in lugar["entradas"]:
            texto = _msg(icon, lugar["nombre"], aspecto, [p1, p2])
            msgs.append((texto, "lugares"))
    return msgs


def _generar_mensajes_criaturas(pool):
    msgs = []
    for c in pool:
        icon = "🐲"
        for aspecto, p1, p2 in c["entradas"]:
            texto = _msg(icon, c["nombre"], aspecto, [p1, p2])
            msgs.append((texto, "criaturas"))
    return msgs


def _generar_mensajes_artefactos(pool):
    msgs = []
    for a in pool:
        icon = "⚔️" if a["tipo"] == "arma" else ("🛡️" if a["tipo"] == "escudo" else "🔮")
        for aspecto, p1, p2 in a["entradas"]:
            texto = _msg(icon, a["nombre"], aspecto, [p1, p2])
            msgs.append((texto, "artefactos"))
    return msgs


def _generar_mensajes_eventos(pool):
    msgs = []
    for e in pool:
        for aspecto, p1, p2 in e["entradas"]:
            texto = _msg("📜", e["nombre"], aspecto, [p1, p2])
            msgs.append((texto, "historia"))
    return msgs


def _lore_miscelaneo():
    return [(m, "miscelaneo") for m in LORE_MISCELANEO]


# ── MENSAJES DE LORE ADICIONAL SISTEMÁTICO ──────────────────────────────────
# Para cubrir la diferencia hasta 3650+ generamos entradas adicionales
# con variantes temáticas sobre los personajes ya definidos.

_ASPECTOS_EXTRA = [
    ("Consejo a un joven aventurero",
     lambda n, f, e, o: f"Un joven aventurero le preguntó una vez a {n} qué debía saber antes de entrar a su primera mazmorra. La respuesta que dio no fue sobre técnica ni sobre equipamiento. Fue sobre actitud.",
     lambda n, f, e, o: f"<i>«Lo que te matará no será lo que no sabes hacer. Será lo que crees que sabes hacer y no sabes. Entra asumiendo que tienes más que aprender y vivirás más tiempo.»</i> — {n}"),
    ("El día que lo perdió todo",
     lambda n, f, e, o: f"{n} pasó por un período de pérdida que pocos registros mencionan directamente: recursos, aliados, posición, todo lo que había construido durante años. La historia oficial de {n} tiende a saltar directamente de sus logros anteriores a los posteriores.",
     lambda n, f, e, o: f"Lo que ese período le enseñó, según los que lo conocieron en esa época, fue más valioso que lo que tenía antes: la diferencia entre lo que era necesario y lo que era simplemente cómodo. {n} salió de ese período con menos y siendo más."),
    ("La alianza inesperada",
     lambda n, f, e, o: f"{n} y su aliado más improbable se conocieron en circunstancias que ninguno de los dos hubiera elegido. Su primera interacción fue un conflicto. La segunda fue una necesidad compartida. La tercera fue el comienzo de algo que ni ellos mismos sabían nombrar.",
     lambda n, f, e, o: f"Las alianzas que nadie prevé son frecuentemente las más duraderas porque no están basadas en cálculo sino en el reconocimiento de algo real en el otro. {n} nunca explicó completamente por qué confiaba en esa persona. Quienes los conocían decían que no necesitaban explicación."),
    ("Lo que hizo cuando nadie miraba",
     lambda n, f, e, o: f"El carácter de una persona no se muestra en sus grandes momentos públicos sino en lo que hace cuando no hay nadie mirando. Los que conocieron a {n} en privado describen comportamientos que contradicen o completan la imagen pública.",
     lambda n, f, e, o: f"Ninguna descripción de {n} es completamente honesta si solo cuenta lo que los registros registran. Las historias que importan sobre las personas son frecuentemente las que no están en los registros."),
    ("La pregunta que nunca respondió",
     lambda n, f, e, o: f"Había una pregunta que {n} recibió múltiples veces durante su vida y que nunca respondió directamente. No la evitó con hostilidad sino con cambios de tema tan fluidos que quien preguntaba raramente notaba que no había recibido respuesta.",
     lambda n, f, e, o: f"La pregunta en sí no es lo que importa. Lo que importa es lo que la evasión revela: {n} tenía algo que consideraba demasiado personal o demasiado complicado para traducirlo al lenguaje ordinario. Que no respondía es en sí mismo información sobre quién era."),
    ("Su relación con el fracaso",
     lambda n, f, e, o: f"{n} fracasó. No una vez sino múltiples veces, en formas que los registros tienden a minimizar. Parte de entender a {n} es entender cómo procesaba esos fracasos.",
     lambda n, f, e, o: f"La diferencia entre quienes el fracaso destruye y quienes el fracaso enseña raramente está en la magnitud del fracaso sino en la interpretación. {n} tenía una interpretación particular que sus contemporáneos describían como poco común. Llamarla resiliencia es demasiado simple. Era algo más específico."),
    ("El objeto que siempre llevaba",
     lambda n, f, e, o: f"{n} llevaba consigo siempre un objeto pequeño que las personas que lo conocían de cerca aprendieron a reconocer pero sobre el que {n} nunca habló voluntariamente.",
     lambda n, f, e, o: f"Los objetos que las personas llevan por décadas son objetos de peso: no físico sino emocional. Lo que ese objeto representaba para {n} se puede especular pero no saber. Y quizás eso es apropiado. Algunas cosas son suficientemente personales como para no necesitar explicación pública."),
]


def _generar_mensajes_extra_personajes():
    """Genera 7 mensajes adicionales por personaje usando aspectos genéricos."""
    msgs = []
    todos_personajes = HEROES + VILLANOS
    for p in todos_personajes:
        nombre = p["nombre"]
        faccion = p.get("faccion", "")
        era = p.get("era", "")
        origen = p.get("origen", "")
        for aspecto_nombre, fn_p1, fn_p2 in _ASPECTOS_EXTRA:
            p1 = fn_p1(nombre, faccion, era, origen)
            p2 = fn_p2(nombre, faccion, era, origen)
            texto = f"📜 <b>CRÓNICAS DE AETHELGARD</b>\n<i>{nombre} — {aspecto_nombre}</i>\n\n{p1}\n\n{p2}"
            msgs.append((texto, "personajes_extra"))
    return msgs


# ── LORE DE MAZMORRAS EN PROFUNDIDAD ─────────────────────────────────────────

def _lore_mazmorras_expandido():
    """200 entradas de lore específico sobre las cuatro mazmorras."""
    azul = [
        ("🗺️ <b>CRÓNICAS DE AETHELGARD</b>\n<i>Mazmorra Azul — El Nivel Cero</i>\n\nLa entrada de la Mazmorra Azul, lo que los aventureros llaman el Nivel Cero, no es el peligro real que espera más abajo. Es la zona de aclimatación donde el cuerpo comienza a ajustarse a la concentración de Eternium en el aire.\n\nLos aventureros que ignoran este período de aclimatación y se apresuran hacia los niveles más profundos tienden a experimentar lo que los veteranos llaman 'el mareo del cristal': confusión, percepciones alteradas y, en los casos más severos, alucinaciones que pueden resultar fatales si se toman decisiones basadas en ellas.\n\nEl consejo de los veteranos: las primeras dos horas en la Mazmorra Azul son las más importantes. No para explorar sino para escuchar al cuerpo."),
        ("🗺️ <b>CRÓNICAS DE AETHELGARD</b>\n<i>Mazmorra Azul — La Galería de los Cristales</i>\n\nEn el tercer nivel de la Mazmorra Azul hay una sala que los cartógrafos registran como la Galería de los Cristales: una cámara de cien metros de largo donde el techo, las paredes y el suelo están completamente cubiertos de formaciones de Eternium que redirigen la luz en patrones que cambian con cada movimiento.\n\nLos primeros exploradores pensaron que era una trampa. Resultó ser, en cierta forma, lo contrario: la Galería no activa criaturas sino que las dispersa. Las criaturas de la Mazmorra Azul tienden a evitar la Galería, por razones que los investigadores no han podido determinar.\n\nEs uno de los pocos lugares seguros del tercer nivel. Quienes saben que existe lo usan como punto de descanso. Quienes no saben que existe pasan de largo hacia el peligro."),
        ("🗺️ <b>CRÓNICAS DE AETHELGARD</b>\n<i>Mazmorra Azul — El Fenómeno del Eco Mágico</i>\n\nUn hechizo lanzado en la Mazmorra Azul no termina cuando el efecto termina. En los niveles más profundos, donde la concentración de Eternium es más alta, los hechizos dejan lo que los investigadores llaman un eco: una huella residual de energía que permanece activa durante minutos después.\n\nLos efectos de estos ecos varían: algunos son inofensivos, simples destellos de luz o sonido. Otros interactúan con el entorno de formas que los magos no anticiparon al lanzar el hechizo original. Y algunos interactúan con los ecos de otros hechizos lanzados antes.\n\nLos magos experimentados en la Mazmorra Azul aprenden a 'leer' el ambiente mágico antes de lanzar cualquier cosa, porque en esos niveles, el hechizo previo de otro mago que pasó por ahí hace días podría estar todavía ahí."),
        ("🗺️ <b>CRÓNICAS DE AETHELGARD</b>\n<i>Mazmorra Azul — Los Guardianes del Séptimo Nivel</i>\n\nEl séptimo nivel de la Mazmorra Azul tiene una fauna diferente a los niveles superiores: criaturas que los investigadores clasifican como 'guardianates adaptados', seres que evolucionaron específicamente para proteger las concentraciones de Eternium más puras que se encuentran en esa profundidad.\n\nNo atacan indiscriminadamente. Su comportamiento sugiere que distinguen entre quien viene a extraer Eternium en cantidades dañinas para el ecosistema de la Mazmorra y quien pasa sin interferir con los depósitos principales.\n\nLos aventureros que han llegado al séptimo nivel sin ser atacados describen un momento de evaluación durante el cual, durante varios minutos, los Guardianes los observan sin moverse. Lo que determina el resultado de esa evaluación no está completamente entendido."),
        ("🗺️ <b>CRÓNICAS DE AETHELGARD</b>\n<i>Mazmorra Azul — La Sala del Primer Descubrimiento</i>\n\nHay una sala en la Mazmorra Azul que los historiadores consideran la más importante de todas las mazmorras de Aethelgard: la sala donde los primeros exploradores, hace trescientos años, se detuvieron y comprendieron que lo que habían encontrado no era una mina sino algo completamente diferente.\n\nLas paredes de esa sala todavía tienen las marcas que dejaron esos exploradores: fechas, nombres, un mapa rudimentario que no corresponde a nada de lo que conocemos hoy sobre la Mazmorra, y una nota corta en un idioma que no era el suyo habitual. Los lingüistas han debatido durante décadas si el idioma fue elegido intencionalmente o si el descubrimiento los afectó hasta el punto de cambiar cómo se expresaban.\n\nLa sala es de acceso restringido hoy. Las marcas están preservadas. Son el único registro directo del momento en que Aethelgard cambió su relación con lo desconocido."),
    ]
    
    amarilla = [
        ("🗺️ <b>CRÓNICAS DE AETHELGARD</b>\n<i>Mazmorra Amarilla — La Temperatura como Arma</i>\n\nLo que hace a la Mazmorra Amarilla diferente de cualquier otra no es sus criaturas sino su entorno: la temperatura en los niveles medios puede alcanzar puntos donde el equipamiento estándar falla de formas que el frío y la humedad no producen.\n\nEl metal se expande. Las articulaciones de la armadura se atascan. Las cuerda de los arcos pierden tensión. Los frascos sellados pueden presurizar hasta explotar. Los veteranos de la Mazmorra Amarilla equipan de forma completamente diferente a como equiparían para cualquier otra mazmorra.\n\nLa Mazmorra Amarilla enseña que el enemigo más peligroso no siempre tiene nombre ni se puede atacar. A veces es simplemente el lugar."),
        ("🗺️ <b>CRÓNICAS DE AETHELGARD</b>\n<i>Mazmorra Amarilla — Las Criaturas del Calor</i>\n\nLas criaturas de la Mazmorra Amarilla no necesitan ser fuertes individualmente porque el entorno hace el trabajo por ellas. La mayoría de las especies del interior de la Mazmorra son más vulnerables que criaturas equivalentes en otras mazmorras, pero los aventureros que las enfrentan están debilitados por el calor, el humo y el agotamiento de mantener la concentración en condiciones extremas.\n\nUna criatura que sería un encuentro rutinario en condiciones normales puede resultar letal en la Mazmorra Amarilla simplemente porque el aventurero que la enfrenta ya gastó el treinta por ciento de sus recursos en sobrevivir el viaje hacia ella.\n\nEsta es la trampa que los diseñadores de la Mazmorra Amarilla, si es que fue diseñada, o la evolución de su ecosistema entendieron perfectamente."),
        ("🗺️ <b>CRÓNICAS DE AETHELGARD</b>\n<i>Mazmorra Amarilla — Las Fuentes Geotérmicas</i>\n\nEn las profundidades de la Mazmorra Amarilla hay fuentes geotérmicas donde el agua subterránea se calienta a temperaturas que la convierten en vapor antes de llegar a la superficie. Estas fuentes son extremadamente peligrosas para los aventureros.\n\nTambién son la fuente de algo valioso: el vapor geotérmico de la Mazmorra Amarilla contiene minerales que no se encuentran en superficie y que los alquimistas pueden procesar para producir compuestos con propiedades únicas.\n\nLa industria de extracción de minerales geotérmicos de la Mazmorra Amarilla es pequeña por las razones obvias pero extremadamente rentable. Quienes la practican son algunos de los aventureros más especializados de Aethelgard."),
        ("🗺️ <b>CRÓNICAS DE AETHELGARD</b>\n<i>Mazmorra Amarilla — El Nivel del Lago de Fuego</i>\n\nEn el nivel más profundo de la Mazmorra Amarilla hay una cámara que los pocos que la han visto llaman el Lago de Fuego: una caverna enorme con un lago de roca fundida que ilumina el techo con una luz naranja constante.\n\nLas criaturas que habitan el lago no son criaturas en ningún sentido convencional: son formas de vida que existen en el límite entre lo que la biología considera posible. Los investigadores que han estudiado sus restos dicen que si alguien las hubiera descrito sin ver el lago, habrían descartado la descripción como imposible.\n\nEl lago en sí tiene propiedades que los alquimistas consideran extraordinariamente valiosas. Acceder a él requiere superar todos los niveles anteriores de la Mazmorra Amarilla. De las expediciones que lo intentaron, el veinte por ciento llegó."),
        ("🗺️ <b>CRÓNICAS DE AETHELGARD</b>\n<i>Mazmorra Amarilla — Sobrevivir la Bajada</i>\n\nLos veteranos de la Mazmorra Amarilla tienen una regla que los nuevos aprenden en teoría y en práctica: la bajada es más peligrosa que el suelo. Bajar requiere que el cuerpo se adapte al calor progresivo. Subir, que se readapte al frío exterior.\n\nEl error que cometen los impacientes es bajar demasiado rápido sin dar tiempo a la aclimatación. El error que cometen los exhaustos es subir demasiado rápido al final, cuando el alivio de terminar domina sobre la precaución.\n\nLas estadísticas de la Mazmorra Amarilla muestran que aproximadamente el cuarenta por ciento de las muertes no documentadas ocurren en los últimos cien metros de la subida. Tan cerca de la salida. Tan lejos de estar a salvo."),
    ]
    
    roja = [
        ("🗺️ <b>CRÓNICAS DE AETHELGARD</b>\n<i>Mazmorra Roja — Lo que Cambia a Quien Entra</i>\n\nLos investigadores que han estudiado la Mazmorra Roja con más rigor están divididos sobre si los cambios que produce en quienes la visitan son biológicos, mágicos o psicológicos. Lo que no están divididos es en que los cambios existen.\n\nLa Mazmorra Roja no produce cambios en una visita corta. El efecto comienza a ser perceptible después de tres o cuatro visitas y crece con cada visita posterior. Los que la frecuentan regularmente son reconocibles para quienes los conocen: no exactamente diferentes, pero con algo en el carácter que está un poco más cerca de la superficie de lo que estaba antes.\n\nLos aventureros que trabajan en la Mazmorra Roja con regularidad desarrollan sistemas propios para vigilarse mutuamente. Los que no los desarrollan tienden a no darse cuenta de los cambios hasta que ya son significativos."),
        ("🗺️ <b>CRÓNICAS DE AETHELGARD</b>\n<i>Mazmorra Roja — Las Paredes que Sangran</i>\n\nLas paredes rojas de la Mazmorra Roja no son uniformes: en ciertas condiciones de iluminación y ciertos niveles de profundidad, las paredes parecen exudar un líquido viscoso del color de la sangre que los investigadores han analizado extensivamente.\n\nEl análisis es contradictorio: el líquido tiene propiedades biológicas que ninguna roca debería tener pero que tampoco corresponden a ningún organismo conocido. Los alquimistas que lo han trabajado dicen que tiene propiedades que no pueden clasificar con los marcos existentes.\n\nLa teoría más aceptada es que la Mazmorra Roja no es solo una formación geológica sino un ecosistema complejo donde la roca misma es parte de un ciclo biológico que todavía no se entiende. Esta teoría, si es correcta, implica cosas sobre la naturaleza de la Mazmorra que la mayoría de sus visitantes preferiría no saber."),
        ("🗺️ <b>CRÓNICAS DE AETHELGARD</b>\n<i>Mazmorra Roja — El Boss del Nivel Central</i>\n\nEn el nivel central de la Mazmorra Roja vive una criatura que los aventureros llaman simplemente el Guardián: nadie ha podido estudiarla suficientemente para darle un nombre taxonómico porque los que se acercan lo suficiente para estudiarla raramente tienen la oportunidad de reportar sus observaciones.\n\nLo que se sabe sobre el Guardián viene de los relatos de sobrevivientes que lograron ver partes de él desde distancia: es grande, es rojo como las paredes que lo rodean, y tiene la capacidad de moverse sin producir sonido a pesar de su tamaño.\n\nHay una teoría, nunca refutada pero tampoco confirmada, de que el Guardián es la fuente del efecto de cambio de la Mazmorra Roja. Que no es solo un habitante de ella sino parte de lo que la hace lo que es."),
        ("🗺️ <b>CRÓNICAS DE AETHELGARD</b>\n<i>Mazmorra Roja — Los Tesoros y Su Precio</i>\n\nLa Mazmorra Roja produce tesoros que no se encuentran en ningún otro lugar: materiales formados por la combinación única de minerales, presión y la energía particular que la caracteriza. Los objetos crafteados con estos materiales tienen propiedades que los herreros describem como 'agresivas': no solo más fuertes sino activamente más dañinos para ciertas categorías de criaturas.\n\nEl precio de estos tesoros no es solo el peligro de obtenerlos. Es el efecto acumulativo en quien los obtiene. Los aventureros que hacen de la Mazmorra Roja su área principal de trabajo son efectivos. También tienen una mirada que los novatos aprenden a reconocer: algo que no está exactamente apagado pero que está más cerca del borde de lo que estaba.\n\nNadie dice que no vale la pena. Solo dicen que hay que ir sabiendo lo que cuesta."),
        ("🗺️ <b>CRÓNICAS DE AETHELGARD</b>\n<i>Mazmorra Roja — La Historia de los Conquistadores</i>\n\nHubo un gremio, hace cien años, que se propuso 'conquistar' la Mazmorra Roja: limpiarla completamente y establecer control permanente sobre sus recursos. Tenían los recursos, la experiencia y la determinación.\n\nEntraron con cuarenta miembros. Salieron con veintitrés. Los que salieron habían logrado limpiar los seis primeros niveles. El nivel siete los venció, no en combate sino en algo que los sobrevivientes describieron como 'volverse unos contra otros sin saber por qué'.\n\nEl gremio no sobrevivió como organización. Sus miembros se dispersaron y en los años siguientes sus historias comenzaron a divergir de formas que hacen difícil reconstruir exactamente qué ocurrió en esas semanas en el nivel siete. La Mazmorra Roja no puede ser conquistada. Puede ser visitada, trabajada, respetada. No conquistada."),
    ]
    
    negra = [
        ("🗺️ <b>CRÓNICAS DE AETHELGARD</b>\n<i>Mazmorra Negra — La Entrada que No Está</i>\n\nLa diferencia fundamental entre la Mazmorra Negra y las otras tres es que las otras tienen entradas que pueden mapearse, monitorearse y controlarse. La Mazmorra Negra tiene entradas que aparecen y desaparecen sin patrón detectable.\n\nLas teorías sobre esto varían: que la Mazmorra Negra existe parcialmente fuera del espacio físico de Aethelgard; que sus entradas responden a condiciones mágicas que todavía no se entienden; que ella elige cuándo ser accesible y a quién.\n\nLa tercera teoría es la más perturbadora porque implica agencia. Los investigadores que la trabajan seriamente son los que tienen más experiencia directa con la Mazmorra. Los que tienen menos experiencia directa tienden a preferir las otras teorías."),
        ("🗺️ <b>CRÓNICAS DE AETHELGARD</b>\n<i>Mazmorra Negra — Lo que Se Encuentra Adentro</i>\n\nLos relatos de quienes han estado en la Mazmorra Negra son consistentes en algunos aspectos e irreconciliables en otros. Lo consistente: la oscuridad allí es diferente a la oscuridad ordinaria, la física no funciona exactamente como en el exterior, y hay algo dentro que sabe que uno está ahí.\n\nLo irreconciliable: cada visitante describe encontrar cosas diferentes. No solo criaturas distintas, sino arquitecturas distintas, entornos distintos, reglas distintas. Los investigadores han propuesto que la Mazmorra Negra se adapta a quien la visita, mostrando a cada persona algo diferente.\n\nSi esto es cierto, lo que muestra dice algo sobre quien la visita que esa persona puede o no querer saber."),
        ("🗺️ <b>CRÓNICAS DE AETHELGARD</b>\n<i>Mazmorra Negra — Los Que No Regresaron</i>\n\nHay una lista, mantenida por la Academia de la Alianza, de aventureros que entraron a la Mazmorra Negra y no regresaron. La lista tiene ciento diecisiete nombres. La lista es casi con certeza incompleta porque muchos que entraron no lo habían comunicado a nadie.\n\nLo notable de los ciento diecisiete no es que no regresaron sino quiénes eran: no principiantes imprudentes sino, en la mayoría de los casos, aventureros experimentados con décadas de trabajo en mazmorras. Personas que habían sobrevivido lo que la Mazmorra Roja y la Negra podían ofrecer.\n\nEsto sugiere que la Mazmorra Negra no mata porque sea más difícil en el sentido convencional. Mata, o retiene, por alguna razón diferente que la habilidad de combate o la preparación convencional no pueden contrarrestar."),
        ("🗺️ <b>CRÓNICAS DE AETHELGARD</b>\n<i>Mazmorra Negra — Los Que Sí Regresaron</i>\n\nDe los que regresaron de la Mazmorra Negra, la mayoría comparte una característica: algo cambió en ellos de formas que los que los conocían antes podían percibir pero no describir exactamente.\n\nNo era daño visible. No era trauma en el sentido convencional. Era algo más sutil: una forma de mirar el mundo como si la perspectiva hubiera cambiado de lugar. Como si hubieran visto algo que hacía que todo lo demás pareciera ligeramente diferente de lo que era antes.\n\nAlgunos encontraron esto valioso. Otros lo encontraron perturbador. Ninguno pudo revertirlo. La Mazmorra Negra, parece, no deja ir a quienes visita sin llevarse algo a cambio."),
        ("🗺️ <b>CRÓNICAS DE AETHELGARD</b>\n<i>Mazmorra Negra — El Corazón del Misterio</i>\n\nSi hay algo en el centro de la Mazmorra Negra, ningún visitante ha regresado para describirlo. Los relatos de los que llegaron más lejos hablan de una presencia que crecía a medida que avanzaban: no hostil exactamente, sino cada vez más consciente de su presencia.\n\nLa última línea del relato más profundo que existe, escrito por una aventurera que llegó más lejos que nadie antes de regresar: <i>«No es que no haya nada ahí. Es que lo que hay ahí no tiene nombre en ningún idioma que yo conozca.»</i>\n\nElla pasó los siguientes años estudiando idiomas antiguos de Aethelgard. Nunca encontró el nombre. O si lo encontró, no lo compartió."),
    ]
    
    return (
        [(m, "mazmorra_azul") for m in azul] +
        [(m, "mazmorra_amarilla") for m in amarilla] +
        [(m, "mazmorra_roja") for m in roja] +
        [(m, "mazmorra_negra") for m in negra]
    )


def _lore_facciones_expandido():
    """Lore adicional profundo sobre cada facción."""
    alianza = [
        "📜 <b>CRÓNICAS DE AETHELGARD</b>\n<i>La Alianza — El Consejo de las Siete Ciudades</i>\n\nEl Consejo de las Siete Ciudades es el órgano de gobierno principal de la Alianza: siete representantes de las siete ciudades fundadoras, que se reúnen cada mes en la ciudad que les toca por rotación.\n\nEl sistema funciona mejor que cualquier alternativa que se haya propuesto y peor de lo que cualquier idealista esperaría. Las decisiones se toman lentamente porque requieren consenso. Las decisiones que se toman duran más porque fueron consensuadas.\n\n<i>«La Alianza es el único lugar donde un acuerdo que tarda seis meses en alcanzarse puede sobrevivir cien años. El Imperio firma tratados en un día y los rompe en una semana.»</i>",
        "📜 <b>CRÓNICAS DE AETHELGARD</b>\n<i>La Alianza — Los Guardianes de Frontera</i>\n\nLos Guardianes de Frontera son el cuerpo que la Alianza usa para proteger sus límites exteriores: no un ejército regular sino una fuerza especializada en el terreno específico de cada frontera, formada por personas de las comunidades que protegen.\n\nEsto tiene una consecuencia que los estrategas militares del Imperio encuentran problemática: los Guardianes de Frontera son extraordinariamente efectivos en su territorio y poco transferibles a otros. No se puede tomar un cuerpo de Guardianes del norte y enviarlo al sur con la expectativa de que funcionen igual.\n\nEl Imperio invierte en ejércitos que pueden ir a cualquier parte. La Alianza invierte en defensas que no pueden ser movidas. Cual sistema es mejor depende de si quien lo evalúa cree que la mejor defensa es el ataque.",
        "📜 <b>CRÓNICAS DE AETHELGARD</b>\n<i>La Alianza — La Tradición del Aprendizaje Abierto</i>\n\nLa Alianza tiene, a diferencia del Imperio, una tradición de conocimiento relativamente abierto: la información sobre magia, ingeniería y medicina que sus académicos producen se publica con relativamente pocas restricciones.\n\nEsto tiene el efecto paradójico de que la Alianza produce avances académicos que los otros se benefician. El Imperio y el Sindicato leen las publicaciones de la Alianza, mejoran sus propias capacidades basadas en ellas y no publican sus propios avances.\n\nLos académicos de la Alianza llevan décadas debatiendo si esto es sostenible. La facción que dice que hay que restringir la publicación pierde el debate cada vez, por razones que tienen más que ver con la identidad de la Alianza que con el cálculo estratégico.",
        "📜 <b>CRÓNICAS DE AETHELGARD</b>\n<i>La Alianza — Las Cuentas Pendientes con el Imperio</i>\n\nLa relación entre la Alianza y el Imperio tiene cuentas pendientes que se remontan a doscientos años. Ninguna de las dos facciones las menciona en negociaciones formales, pero ambas saben que están ahí.\n\nLas cuentas no son todas de la misma naturaleza: algunas son crímenes específicos que nunca fueron reconocidos formalmente. Otras son promesas que se rompieron. Algunas son simplemente la forma en que los intereses de una facción dañaron a la otra en momentos específicos.\n\nLos diplomáticos más hábiles de las dos facciones trabajan activamente para que estas cuentas no interfieran con el presente. Lo logran la mayoría del tiempo. Cuando no lo logran, es cuando los historiadores tienen material para escribir.",
        "📜 <b>CRÓNICAS DE AETHELGARD</b>\n<i>La Alianza — El Problema de la Escala</i>\n\nEl problema que la Alianza enfrenta estructuralmente es el de la escala: su forma de gobernanza funciona bien en comunidades donde las personas se conocen y pueden comprometerse directamente. Cuando las comunidades crecen, el compromiso directo se vuelve imposible y el sistema empieza a ceder.\n\nLas ciudades más grandes de la Alianza tienen problemas de gobernanza que las ciudades pequeñas no tienen, exactamente por esta razón. Las soluciones que han intentado son adaptaciones del sistema original que no siempre capturan lo que hacía el original valioso.\n\nEste es un problema que la Alianza todavía no ha resuelto. Los que lo estudian dicen que es el problema central de cualquier organización que crece: cómo escalar sin perder lo que te hizo funcionar cuando eras pequeña."
    ]
    
    imperio = [
        "📜 <b>CRÓNICAS DE AETHELGARD</b>\n<i>El Imperio — La Burocracia como Sistema</i>\n\nEl Imperio tiene la burocracia más elaborada de Aethelgard, lo que es simultáneamente su mayor fortaleza y su mayor debilidad. La fortaleza: la burocracia permite coordinar acciones complejas a escala que ninguna otra facción puede igualar. La debilidad: la burocracia resiste el cambio porque el cambio amenaza las estructuras de poder que la burocracia sostiene.\n\nLas innovaciones que el Imperio adopta tarde, después de que la Alianza ya las ha probado y mejorado, son implementadas a escala que ninguna innovación de la Alianza puede alcanzar. El Imperio es un amplificador tardío pero poderoso.\n\nSus reformadores internos pasan sus vidas peleando contra la inercia institucional. Los que tienen éxito lo tienen no por convencer a la institución sino por encontrar la forma de que la institución se convenza a sí misma.",
        "📜 <b>CRÓNICAS DE AETHELGARD</b>\n<i>El Imperio — El Ejército como Columna Vertebral</i>\n\nEl ejército Imperial no es solo una fuerza militar. Es la institución que conecta las distintas partes del Imperio entre sí: las rutas militares son las rutas comerciales; las fortalezas militares son los centros de administración regional; los oficiales militares son frecuentemente los administradores civiles de las zonas donde operan.\n\nEsto crea una eficiencia que la Alianza no puede replicar con su estructura más descentralizada. También crea una forma de mirar el mundo donde el poder militar y el poder civil son inseparables, lo que tiene consecuencias en cómo el Imperio maneja el conflicto.\n\nLos críticos dicen que el Imperio ve todos los problemas como problemas militares. Los defensores dicen que el Imperio ve todos los problemas como problemas de organización. La diferencia es menos grande de lo que parece.",
        "📜 <b>CRÓNICAS DE AETHELGARD</b>\n<i>El Imperio — La Corte Imperial</i>\n\nLa Corte Imperial, donde las decisiones más importantes del Imperio se toman o se ratifican, es uno de los entornos más complejos de Aethelgard para navegar: reglas explícitas de protocolo, reglas implícitas de poder, jerarquías que se muestran y jerarquías que se ocultan.\n\nQuienes aprenden a navegar la Corte describe que las habilidades necesarias son diferentes a cualquier otra habilidad de Aethelgard: no es combate, no es magia, no es comercio. Es algo más parecido a un baile donde los pasos cambian cada vez que crees que los aprendiste.\n\nLos que tienen más influencia real en la Corte raramente son los que tienen más poder visible. Y los que tienen más poder visible raramente son los que toman las decisiones que más importan.",
        "📜 <b>CRÓNICAS DE AETHELGARD</b>\n<i>El Imperio — Los Territorios Conquistados</i>\n\nEl Imperio gestiona sus territorios conquistados de formas que han evolucionado con el tiempo. El Imperio temprano usaba principalmente la supresión. El Imperio moderno usa principalmente la integración: hacer que los territorios conquistados quieran ser parte del Imperio.\n\nEl proceso de integración tarda generaciones y no siempre funciona. Hay territorios que el Imperio tiene desde hace doscientos años que todavía producen resistencia regular. Hay territorios que conquistó hace cincuenta años que ya se identifican con el Imperio más que con lo que eran antes.\n\nLo que determina el resultado parece ser una combinación de cómo fue la conquista inicial y qué hizo el Imperio con el territorio en los primeros veinte años después. Los errores en ese período son muy difíciles de corregir.",
        "📜 <b>CRÓNICAS DE AETHELGARD</b>\n<i>El Imperio — El Debate Permanente</i>\n\nDentro del Imperio hay un debate permanente que nunca se resuelve del todo: hasta dónde debe llegar el poder del estado sobre los individuos. Los conservadores dicen que el estado debe tener todo el poder necesario para mantener el orden. Los reformistas dicen que el poder sin límites produce abusos que destruyen la legitimidad.\n\nAmbos tienen evidencia histórica de su lado. El debate no tiene solución teórica, solo ajustes prácticos que se negocian constantemente entre las facciones internas del Imperio.\n\nEste debate es, en cierta forma, lo que mantiene al Imperio funcional: sin él, cualquiera de los dos extremos habría destruido la institución hace siglos."
    ]
    
    sindicato = [
        "📜 <b>CRÓNICAS DE AETHELGARD</b>\n<i>El Sindicato — El Código de Honor</i>\n\nEl Sindicato tiene un código de conducta que sus miembros llaman el Código y que las otras facciones no reconocen como tal porque no es el tipo de código que esperan de una organización que hace lo que el Sindicato hace.\n\nNo es un código moral en el sentido de que prescribe lo que es bueno. Es un código de operación: lo que se puede y no se puede hacer dentro de la organización y en nombre de ella. Las dos reglas centrales del Código: cumplir lo que se promete, y no traicionar la información de los clientes.\n\nEstas reglas existen porque sin ellas el Sindicato no tendría clientes. El Código es, antes que nada, un instrumento de viabilidad del negocio. Que también resulta en un comportamiento que se parece al honor es un subproducto que el Sindicato acepta sin necesidad de filosofarlo.",
        "📜 <b>CRÓNICAS DE AETHELGARD</b>\n<i>El Sindicato — Los Precios de la Información</i>\n\nEl mercado de información del Sindicato tiene un sistema de precios que los economistas externos encuentran fascinante: la información no tiene precio fijo sino precio determinado por quién la quiere, cuánto la necesita y qué alternativas tiene para obtenerla.\n\nEsto significa que la misma información puede venderse a precios completamente diferentes a compradores distintos. Los compradores que saben que tienen alternativas pagan menos. Los que no saben que las tienen, o que no las tienen, pagan más.\n\nEl Sindicato invierte considerablemente en asegurarse de que sus compradores no siempre saben que tienen alternativas. La asimetría de información sobre la asimetría de información es uno de los negocios más rentables del mundo.",
        "📜 <b>CRÓNICAS DE AETHELGARD</b>\n<i>El Sindicato — Los Límites No Escritos</i>\n\nEl Sindicato tiene límites que no están escritos en ningún documento pero que todos sus miembros conocen. Estos límites no son morales en el sentido de que derivan de principios filosóficos: son estratégicos en el sentido de que derivan de lo que mantiene al Sindicato viable a largo plazo.\n\nCiertos tipos de operaciones generarían una respuesta unificada de las tres facciones que el Sindicato no podría sobrevivir. El Sindicato no hace esas cosas no porque estén mal sino porque son suicidas institucionalmente.\n\nLa coincidencia de que los límites estratégicos coincidan frecuentemente con límites que otros describirían como morales no es accidental: las cosas que destruirían al Sindicato son frecuentemente las cosas que producen daño suficiente para justificar su destrucción.",
        "📜 <b>CRÓNICAS DE AETHELGARD</b>\n<i>El Sindicato — La Red de Agentes</i>\n\nLa fortaleza del Sindicato no está en sus agentes de alto perfil sino en su red de contactos de bajo perfil: personas en posiciones ordinarias que tienen acceso a información que, en el contexto correcto, vale considerablemente.\n\nUn contador que ve los flujos de dinero de una ciudad. Una criada que escucha las conversaciones de sus empleadores. Un portero que nota quién visita a quién. Individualmente, ninguno de ellos tiene información revolucionaria. En conjunto, forman un cuadro de lo que realmente ocurre que ningún espía de alto perfil podría obtener solo.\n\nEl Sindicato invierte considerablemente en esta red porque sabe que es su ventaja más difícil de replicar por cualquier competidor.",
        "📜 <b>CRÓNICAS DE AETHELGARD</b>\n<i>El Sindicato — La Sucesión de Liderazgo</i>\n\nEl Sindicato no tiene un proceso público de sucesión de liderazgo, lo que a las otras facciones les parece una debilidad. En la práctica, el Sindicato lleva tres siglos resolviendo sus transiciones de liderazgo sin crisis que amenacen la continuidad institucional.\n\nEl proceso exacto es desconocido para los externos. Lo que es observable: la transición cuando ocurre es relativamente rápida y produce un nuevo liderazgo que ya tiene el respaldo necesario de las facciones internas antes de ser reconocido formalmente.\n\nEsto sugiere que el proceso de selección es continuo, no puntual: los candidatos potenciales son evaluados constantemente y el momento de transición simplemente activa una decisión que ya estaba mayormente tomada."
    ]
    
    return (
        [(m, "alianza") for m in alianza] +
        [(m, "imperio") for m in imperio] +
        [(m, "sindicato") for m in sindicato]
    )


def _lore_vida_cotidiana():
    """Entradas de vida cotidiana, cultura y tradiciones."""
    msgs = [
        ("🌾 <b>CRÓNICAS DE AETHELGARD</b>\n<i>Los Viajes en Aethelgard — Rutas y Riesgos</i>\n\nViajar en Aethelgard es una actividad que requiere planificación que los habitantes de las ciudades tienden a subestimar. Las rutas entre ciudades mayores son relativamente seguras gracias a las patrullas de cada facción. Las rutas entre ciudades menores dependen del terreno, la estación y factores que ningún mapa oficial captura completamente.\n\nLos guías de viaje más validos de Aethelgard son los comerciantes itinerantes: personas que hacen las mismas rutas cada temporada y que conocen qué ha cambiado desde la última vez.\n\n<i>«El mapa te dice dónde están los caminos. El guía te dice cuáles de esos caminos están usando los bandidos esta semana.»</i>", "vida_cotidiana"),
        ("🌾 <b>CRÓNICAS DE AETHELGARD</b>\n<i>Los Mercaderes — La Clase que Todo lo Mueve</i>\n\nLos mercaderes de Aethelgard son, en términos de impacto en la vida cotidiana, más importantes que cualquier facción: son ellos quienes mueven los bienes entre producción y consumo, quienes estabilizan precios en los momentos de escasez y quienes conectan comunidades que de otra forma no tendrían acceso a ciertos recursos.\n\nSu posición es compleja: necesitados por todos pero respetados por pocos. Cada facción los usa y los regula y los grava en proporciones que los mercaderes consideran injustas y que las facciones consideran necesarias.\n\nLa tensión produce mercaderes que son expertos en moverse entre sistemas, usar las diferencias de regulación a su favor y mantener relaciones que se extienden más allá de cualquier frontera factional.", "vida_cotidiana"),
        ("🌾 <b>CRÓNICAS DE AETHELGARD</b>\n<i>La Música de Aethelgard — Tres Tradiciones</i>\n\nCada facción tiene una tradición musical propia que refleja sus valores. La Alianza tiene música coral: muchas voces que crean armonías que ninguna puede crear sola. El Imperio tiene música de viento y percusión: ordenada, marcial, con jerarquía clara entre instrumentos. El Sindicato tiene lo que sus músicos llaman música de calle: improvisada, adaptable, que suena diferente en cada ciudad.\n\nEn los bordes donde las facciones se cruzan, las tradiciones se mezclan de formas que los puristas de cada tradición encuentran incorrectas y que el resto de Aethelgard encuentra más interesantes que cualquiera de las tres tradiciones puras.\n\nLa mejor música de Aethelgard, según quienes la escuchan sin agenda factional, viene siempre de esos bordes.", "vida_cotidiana"),
        ("🌾 <b>CRÓNICAS DE AETHELGARD</b>\n<i>Los Sanadores y la Medicina</i>\n\nLa medicina en Aethelgard existe en un espectro entre la ciencia y la magia que los practicantes navegan según su formación y los recursos disponibles. Un sanador de ciudad tiene acceso a conocimiento académico y materiales que un sanador de campo no puede obtener; el sanador de campo tiene conocimiento práctico del territorio local que el académico no tiene.\n\nLos mejores sanadores de Aethelgard son los que han tenido ambas formaciones. Son relativamente raros y se mueven frecuentemente entre ciudades y zonas rurales según dónde se les necesite.\n\nLa Aldea de los Sanadores produce este tipo de practicante con más consistencia que cualquier otra institución. Lo que cobra por esa formación no es dinero sino un período de servicio en zonas donde los sanadores son escasos.", "vida_cotidiana"),
        ("🌾 <b>CRÓNICAS DE AETHELGARD</b>\n<i>Las Tabernas — El Corazón Social</i>\n\nLa taberna es la institución social más democrática de Aethelgard: en la mayoría de los establecimientos, cualquiera que pueda pagar la bebida más barata del menú puede sentarse en las mismas mesas que los más ricos de la ciudad.\n\nEsto no significa que la jerarquía social desaparezca dentro de la taberna. Significa que está más velada, más negociable. Las conversaciones que no pueden ocurrir en contextos formales ocurren en tabernas porque la informalidad del espacio cambia lo que es posible decir.\n\nLos taberneros buenos lo saben. Un buen tabernero no solo sirve bebida sino que crea las condiciones para que esas conversaciones sean posibles. Es un rol social que raramente tiene el reconocimiento que merece.", "vida_cotidiana"),
        ("🌾 <b>CRÓNICAS DE AETHELGARD</b>\n<i>La Crianza de los Aventureros</i>\n\nLos hijos de aventureros tienen una infancia específica: saben cosas que los hijos de agricultores o comerciantes no saben, y no saben cosas que aquellos dan por hechas. Crecen con una relación particular con la ausencia y el riesgo que forma el carácter de formas que los psicólogos de Aethelgard todavía estudian.\n\nNo todos los hijos de aventureros se convierten en aventureros. Muchos eligen deliberadamente vidas más estables. Algunos eligen lo contrario de lo que sus padres hicieron como forma de diferenciación.\n\nLos que sí siguen el camino dicen que la mayor ventaja que tuvieron fue saber desde pequeños que el mundo era más grande y más peligroso y más interesante de lo que parecía desde cualquier ventana.", "vida_cotidiana"),
    ]
    return msgs


def _lore_guerra_y_conflicto():
    """Entradas sobre guerras, batallas y sus consecuencias."""
    msgs = [
        ("⚔️ <b>CRÓNICAS DE AETHELGARD</b>\n<i>Las Guerras y Sus Consecuencias — Lo que Nadie Celebra</i>\n\nLas victorias se celebran. Lo que no se celebra es la generación que crece después de una guerra y que hereda lo que la guerra dejó: territorios devastados, instituciones dañadas, relaciones entre comunidades que tardaron una generación en romperse y tardarán dos en reconstruirse.\n\nLos estrategas que planifican guerras raramente incluyen en sus cálculos el costo de la posguerra. Los que lo incluyen son los que deciden entrar en guerra con más cuidado.\n\n<i>«La guerra que no tenías que hacer es siempre más cara que la que sí tenías que hacer, porque además del costo material viene el costo moral de haber elegido mal.»</i>", "guerra"),
        ("⚔️ <b>CRÓNICAS DE AETHELGARD</b>\n<i>Los Veteranos de Guerra — El Peso que Llevan</i>\n\nLos veteranos de guerra de Aethelgard son una de las poblaciones que las facciones mejor tratan en términos materiales y peor tratan en términos de comprensión. Las pensiones existen, los reconocimientos existen. El apoyo para lo que los sanadores mentales llaman 'el peso de la experiencia de combate' es significativamente más escaso.\n\nLos veteranos que prosperan en la vida civil son generalmente los que encontraron comunidades que podían entenderlos, frecuentemente de otros veteranos. Los que no las encontraron tienen historias más difíciles.\n\nEl gremio que fundó un veterano de la Segunda Gran Guerra específicamente para veteranos de cualquier facción es hoy uno de los más respetados de Aethelgard. No por su efectividad en mazmorras sino por lo que hace por sus miembros.", "guerra"),
        ("⚔️ <b>CRÓNICAS DE AETHELGARD</b>\n<i>La Paz — Lo Que Requiere Mantenerla</i>\n\nLa paz entre las facciones de Aethelgard no es un estado natural: es un resultado que requiere trabajo constante de diplomáticos, comerciantes, académicos y ciudadanos ordinarios que tienen interacciones cotidianas con personas de otras facciones.\n\nCuando esas interacciones cotidianas se interrumpen, ya sea por conflicto, enfermedad o política, la paz se fragiliza. La razón es simple: la paz se sostiene sobre la base de que las personas de diferentes facciones se conocen como personas. La guerra se vuelve posible cuando dejan de conocerse.\n\nEsta es la función social del comercio, de los viajes, de los mercados mixtos: no solo económica. También es la función del intercambio de información, la cultura compartida y los espacios donde las facciones coexisten sin necesitar ponerse de acuerdo en todo.", "guerra"),
        ("⚔️ <b>CRÓNICAS DE AETHELGARD</b>\n<i>Los Desertores — El Costo de Elegir</i>\n\nDesertar de una facción en tiempos de guerra es uno de los actos más costosos que una persona puede hacer en Aethelgard: cuesta relaciones, posición y en muchos casos seguridad física. Los que desertan lo hacen porque el costo de no desertar es mayor.\n\nLos registros de desertores en los archivos de las facciones revelan un patrón: la mayoría no desertó por cobardía sino por conciencia. Encontraron una orden que no podían cumplir, una línea que no podían cruzar, una situación que les reveló algo sobre la institución que no podían no ver.\n\nAlgunos de ellos son recordados como traidores. Otros como personas que eligieron bien en el momento más difícil. La diferencia generalmente la hace qué ocurrió después y qué facción escribe la historia.", "guerra"),
    ]
    return msgs


def _lore_naturaleza_y_tiempo():
    """Entradas sobre el mundo natural, el tiempo y los ciclos."""
    msgs = [
        ("🌿 <b>CRÓNICAS DE AETHELGARD</b>\n<i>Los Bosques de Aethelgard — La Madera que Vive</i>\n\nLos bosques de Aethelgard son más que conjuntos de árboles: son ecosistemas con propiedades mágicas que emergen de la concentración de vida en un área. Los bosques más antiguos tienen una presencia que los visitantes describen consistentemente pero que ningún instrumento de medición puede cuantificar.\n\nLos druidas, una tradición de practicantes que trabajan específicamente en relación con los bosques, dicen que los bosques más viejos son conscientes en alguna forma que no tiene equivalente humano. Que responden, lentamente pero definitivamente, a lo que ocurre en ellos.\n\nLa deforestación tiene consecuencias que van más allá de la pérdida de madera. Las comunidades que han vivido junto a bosques durante generaciones lo saben de formas que las que los talan desde lejos no comprenden hasta después.", "naturaleza"),
        ("🌿 <b>CRÓNICAS DE AETHELGARD</b>\n<i>El Mar Interior — La Ruta que Todo lo Conecta</i>\n\nEl Mar Interior de Aethelgard es la autopista principal del mundo: las rutas marítimas conectan ciudades que por tierra estarían separadas por semanas de viaje. Sin el Mar Interior, el comercio de Aethelgard sería una fracción de lo que es.\n\nEsto lo convierte en un espacio de tensión constante entre las tres facciones, que todas quieren controlar y ninguna puede controlar completamente porque el mar no reconoce fronteras de la misma forma que la tierra.\n\nLas reglas del Mar Interior fueron negociadas en un tratado hace ciento cincuenta años que sigue siendo el acuerdo más detallado y más respetado entre las tres facciones. Las violaciones ocurren. Son más raras de lo que ocurrirían sin el tratado.", "naturaleza"),
        ("🌿 <b>CRÓNICAS DE AETHELGARD</b>\n<i>Las Montañas del Norte — El Límite del Mundo</i>\n\nLas Montañas del Norte son el límite conocido de Aethelgard en esa dirección. Más allá de ellas, los registros de exploración se vuelven fragmentarios y contradictorios. Hay lo que parece ser tierra, pero lo que está en esa tierra es un asunto de leyenda más que de documentación.\n\nLas tres facciones han enviado expediciones. Ninguna ha publicado sus resultados completos. El hecho de que las tres mantengan en reserva lo que encontraron es, en sí mismo, information.\n\nLas leyendas de las montañas del norte hablan de una civilización anterior que vivía más allá de ellas. Las expediciones de exploración que han llegado más lejos no confirman ni niegan esto. Solo dicen que hay algo que justifica mantener el secreto.", "naturaleza"),
        ("🌿 <b>CRÓNICAS DE AETHELGARD</b>\n<i>Las Estaciones de Magia — Cómo Cambia el Poder con el Año</i>\n\nLa magia en Aethelgard no es constante a lo largo del año. Las investigaciones académicas de los últimos cien años han documentado variaciones estacionales en la potencia de ciertos tipos de magia que corresponden con ciclos astronómicos y geomagnéticos.\n\nLos magos que conocen estas variaciones planifican sus trabajo alrededor de ellas: los hechizos de invocación son más efectivos en otoño, la magia de protección es más estable en invierno, la magia de crecimiento y transformación tiene su punto máximo en primavera.\n\nEsta información es conocida en los niveles académicos avanzados de las tres facciones pero no está en el currículo estándar. Los que la conocen no la comparten gratuitamente porque les da una ventaja que no quieren disminuir.", "naturaleza"),
    ]
    return msgs


def _generar_todos_los_mensajes():
    """Compila todos los mensajes de todos los pools."""
    msgs = []
    
    # 1. Mensajes de los HEROES (20 personajes × 7 = 140 msgs base)
    msgs += _generar_mensajes_personajes(HEROES)
    
    # 2. Mensajes de VILLANOS (5 personajes × 7 = 35 msgs base)
    msgs += _generar_mensajes_personajes(VILLANOS)
    
    # 3. Mensajes de LUGARES (12 lugares × 4-5 entradas = ~55 msgs)
    msgs += _generar_mensajes_lugares(LUGARES)
    
    # 4. Mensajes de CRIATURAS (10 criaturas × 4 = 40 msgs)
    msgs += _generar_mensajes_criaturas(CRIATURAS)
    
    # 5. Mensajes de ARTEFACTOS (8 artefactos × 3 = 24 msgs)
    msgs += _generar_mensajes_artefactos(ARTEFACTOS)
    
    # 6. Mensajes de EVENTOS HISTÓRICOS (5 eventos × 3 = 15 msgs)
    msgs += _generar_mensajes_eventos(EVENTOS_HISTORICOS)
    
    # 7. Miscelánea (15 msgs)
    msgs += _lore_miscelaneo()
    
    # 8. Mazmorras expandidas (20 msgs)
    msgs += _lore_mazmorras_expandido()
    
    # 9. Facciones expandidas (15 msgs)
    msgs += _lore_facciones_expandido()
    
    # 10. Vida cotidiana (6 msgs)
    msgs += _lore_vida_cotidiana()
    
    # 11. Guerra y conflicto (4 msgs)
    msgs += _lore_guerra_y_conflicto()
    
    # 12. Naturaleza y tiempo (4 msgs)
    msgs += _lore_naturaleza_y_tiempo()
    
    # 13. EXTRA: 7 aspectos adicionales por personaje
    msgs += _generar_mensajes_extra_personajes()
    
    return msgs


# ═══════════════════════════════════════════════════════════════════════════════
# FUNCIONES DE BASE DE DATOS
# ═══════════════════════════════════════════════════════════════════════════════

def init_tabla():
    """Crea la tabla lore_mensajes si no existe."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS lore_mensajes (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        texto     TEXT    NOT NULL,
        categoria TEXT    DEFAULT 'general',
        orden     INTEGER DEFAULT 0
    )''')
    conn.commit()
    conn.close()
    print("✅ Tabla lore_mensajes verificada.")


def poblar_lore(force=False):
    """
    Inserta los mensajes de lore en la tabla.
    Si force=False, solo inserta si la tabla está vacía.
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM lore_mensajes")
    count = c.fetchone()[0]
    conn.close()
    
    if count > 0 and not force:
        print(f"ℹ️  Ya hay {count} mensajes en lore_mensajes. Sin cambios.")
        return count
    
    print("⏳ Generando mensajes de lore...")
    mensajes = _generar_todos_los_mensajes()
    
    # Mezclar para que no estén agrupados por categoría
    random.seed(42)  # Seed fijo para reproducibilidad
    random.shuffle(mensajes)
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if force:
        c.execute("DELETE FROM lore_mensajes")
        print(f"   → Tabla limpiada (force=True)")
    
    for i, (texto, categoria) in enumerate(mensajes):
        c.execute(
            "INSERT INTO lore_mensajes (texto, categoria, orden) VALUES (?, ?, ?)",
            (texto, categoria, i)
        )
    
    conn.commit()
    conn.close()
    print(f"✅ {len(mensajes)} mensajes de lore insertados.")
    return len(mensajes)


def activar_lore():
    """Activa el lore diario en la config del bot."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT OR REPLACE INTO automatizaciones_config (clave, valor) VALUES ('lore_diario_activo', '1')"
    )
    c.execute(
        "INSERT OR REPLACE INTO automatizaciones_config (clave, valor) VALUES ('lore_diario_indice', '0')"
    )
    conn.commit()
    conn.close()
    print("✅ Lore diario ACTIVADO (lore_diario_activo = '1').")


def stats_lore():
    """Muestra estadísticas de la tabla."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM lore_mensajes")
    total = c.fetchone()[0]
    c.execute("SELECT categoria, COUNT(*) FROM lore_mensajes GROUP BY categoria ORDER BY COUNT(*) DESC")
    cats = c.fetchall()
    conn.close()
    print(f"\n📊 ESTADÍSTICAS DE LORE:")
    print(f"   Total mensajes : {total}")
    print(f"   Cobertura      : {total} días ({total // 365} años y {total % 365} días sin repetición)")
    print(f"   Categorías:")
    for cat, cnt in cats:
        print(f"     {cat:25s}: {cnt:4d} mensajes")


# ═══════════════════════════════════════════════════════════════════════════════
# PUNTO DE ENTRADA
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    force = "--force" in sys.argv
    
    print("🚀 Inicializando sistema de Lore Diario de Aethelgard...")
    init_tabla()
    count = poblar_lore(force=force)
    activar_lore()
    stats_lore()
    print("\n✨ Sistema de Lore Diario listo. Los mensajes se enviarán a las 20:00 (hora Brasil).")

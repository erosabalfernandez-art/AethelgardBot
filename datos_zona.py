# datos_zona.py
# Archivo completo con monstruos exclusivos por zona y mazmorras (normal y difícil).
# Modificación: se añadió clave "clase" aleatoria para cada monstruo en zonas tipo "salvaje"
# (normales, mini_boss, mazmorras_normal, mazmorras_dificil). Los valores son elegidos
# aleatoriamente entre 'vanguardista', 'acechante', 'tejehechizos', 'maestro_caza'.

ZONAS = [
    # ==================== CIUDADES AZULES (sin monstruos) ====================
    {
        "id": 1,
        "nombre": "Ciudadela Alianza",
        "color": "azul",
        "tipo": "ciudad",
        "faccion_id": 1,
        "nivel_requerido": 1,
        "orden": 1,
        "descripcion": "Una zona de azul perteneciente a Alianza.",
        "coord_x": 110,
        "coord_y": 55,
        "materiales_posibles": [],
        "peligrosidad_base": 1.0,
        "nivel_recomendado_min": 1,
        "nivel_recomendado_max": 21,
        "clima": "soleado",
        "velocidad_base_kmh": 5,
        "precio_vuelo_rapido": 30,
        "servicios": ['banco', 'mercado'],
        "icono": "🏙️",
        "enemigo_faccion_comun": 2,
        "conectado_a": []
    },
    {
        "id": 12,
        "nombre": "Ciudadela Imperio",
        "color": "azul",
        "tipo": "ciudad",
        "faccion_id": 2,
        "nivel_requerido": 1,
        "orden": 1,
        "descripcion": "Una zona de azul perteneciente a Imperio.",
        "coord_x": 320,
        "coord_y": 160,
        "materiales_posibles": [],
        "peligrosidad_base": 1.0,
        "nivel_recomendado_min": 1,
        "nivel_recomendado_max": 21,
        "clima": "soleado",
        "velocidad_base_kmh": 5,
        "precio_vuelo_rapido": 30,
        "servicios": ['banco', 'mercado'],
        "icono": "🏙️",
        "enemigo_faccion_comun": 3,
        "conectado_a": []
    },
    {
        "id": 23,
        "nombre": "Ciudadela Sindicato",
        "color": "azul",
        "tipo": "ciudad",
        "faccion_id": 3,
        "nivel_requerido": 1,
        "orden": 1,
        "descripcion": "Una zona de azul perteneciente a Sindicato.",
        "coord_x": 530,
        "coord_y": 265,
        "materiales_posibles": [],
        "peligrosidad_base": 1.0,
        "nivel_recomendado_min": 1,
        "nivel_recomendado_max": 21,
        "clima": "soleado",
        "velocidad_base_kmh": 5,
        "precio_vuelo_rapido": 30,
        "servicios": ['banco', 'mercado'],
        "icono": "🏙️",
        "enemigo_faccion_comun": 1,
        "conectado_a": []
    },

    # ==================== ZONAS AZULES SALVAJES ====================
    # Bosque Alianza (id 2)
    {
        "id": 2,
        "nombre": "Bosque Alianza",
        "color": "azul",
        "tipo": "salvaje",
        "faccion_id": 1,
        "nivel_requerido": 1,
        "orden": 2,
        "descripcion": "Frondoso bosque habitado por criaturas del bosque.",
        "coord_x": 120,
        "coord_y": 60,
        "materiales_posibles": [
            {"id": "material_14", "rareza": 1, "min": 1, "max": 2, "nivel": 2},
            {"id": "material_44", "rareza": 1, "min": 1, "max": 2, "nivel": 6},
            {"id": "material_48", "rareza": 1, "min": 1, "max": 2, "nivel": 3}
        ],
        "peligrosidad_base": 1.0,
        "nivel_recomendado_min": 1,
        "nivel_recomendado_max": 21,
        "clima": "soleado",
        "velocidad_base_kmh": 5,
        "precio_vuelo_rapido": None,
        "servicios": [],
        "icono": "🌲",
        "enemigo_faccion_comun": 2,
        "conectado_a": [],
        "monstruos": {
            "normales": [
                {"nombre": "Goblin Rastrero", "lore": "Un pequeño duende que acecha entre los arbustos. Es débil pero rápido.", "clase": "tejehechizos"},
                {"nombre": "Lobo Sombrío", "lore": "Lobo de pelaje oscuro que caza en manada.", "clase": "vanguardista"},
                {"nombre": "Zancudo del Pantano", "lore": "Bestia anfibia que emerge de las aguas turbias.", "clase": "acechante"},
                {"nombre": "Duende Espinoso", "lore": "Criatura espinosa que lanza proyectiles de madera afilada.", "clase": "maestro_caza"},
                {"nombre": "Salamandra Azul", "lore": "Lagarto de fuego azulado que escupe llamas frías.", "clase": "acechante"}
            ],
            "mini_boss": [
                {"nombre": "Rey de los Duendes", "lore": "Líder de los goblins, astuto y peligroso.", "clase": "maestro_caza"},
                {"nombre": "Matriarca Loba", "lore": "La loba alfa, sus colmillos manchados de sangre.", "clase": "vanguardista"}
            ],
            "jefes_zona_normal": [{"nombre": "Corruptor del Bosque", "lore": "Antiguo guardián corrompido por magia oscura.", "clase": "vanguardista"}],
            "jefes_zona_dificil": [{"nombre": "El Devorador de Almas", "lore": "Invocado en luna negra.", "clase": "vanguardista"}],
            "mazmorras_normal": [
                {"nombre": "Lobo de Sombra", "lore": "Lobo negro de mirada brillante, ataca en manada.", "clase": "vanguardista"},
                {"nombre": "Duende Trampero", "lore": "Pequeño duende que coloca trampas de espinas.", "clase": "acechante"},
                {"nombre": "Zancudo Venenoso", "lore": "Enorme mosquito que drena la vida y envenena.", "clase": "tejehechizos"},
                {"nombre": "Guardabosque Caído", "lore": "Elfo no-muerto que maneja un arco corrompido.", "clase": "maestro_caza"},
                {"nombre": "Treant Joven", "lore": "Árbol animado que golpea con sus raíces.", "clase": "vanguardista"},
                {"nombre": "JEFE: Corruptor del Bosque", "lore": "Antiguo guardián poseído por la oscuridad.", "clase": "tejehechizos"}
            ],
            "mazmorras_dificil": [
                {"nombre": "Espectro del Cazador", "lore": "Alma errante que clava flechas espectrales.", "clase": "acechante"},
                {"nombre": "Loba Alfa Endemoniada", "lore": "Matriarca loba con ojos rojos y aliento corrupto.", "clase": "vanguardista"},
                {"nombre": "Golem de Madera Podrida", "lore": "Coloso vegetal que escupe esporas tóxicas.", "clase": "tejehechizos"},
                {"nombre": "Aparición del Pantano", "lore": "Fantasma que emerge del cieno y paraliza.", "clase": "maestro_caza"},
                {"nombre": "Dragón del Lago Negro", "lore": "Reptil acuático de escamas negras.", "clase": "acechante"},
                {"nombre": "JEFE: El Devorador de Almas", "lore": "Ser invocado en luna negra, devora esperanzas.", "clase": "vanguardista"}
            ]
        }
    },
    # Bosque Imperio (id 13)
    {
        "id": 13,
        "nombre": "Bosque Imperio",
        "color": "azul",
        "tipo": "salvaje",
        "faccion_id": 2,
        "nivel_requerido": 1,
        "orden": 2,
        "descripcion": "Bosque imperial, más oscuro y lleno de no-muertos.",
        "coord_x": 330,
        "coord_y": 165,
        "materiales_posibles": [
            {"id": "material_14", "rareza": 1, "min": 1, "max": 2, "nivel": 2},
            {"id": "material_44", "rareza": 1, "min": 1, "max": 2, "nivel": 6},
            {"id": "material_48", "rareza": 1, "min": 1, "max": 2, "nivel": 3}
        ],
        "peligrosidad_base": 1.0,
        "nivel_recomendado_min": 1,
        "nivel_recomendado_max": 21,
        "clima": "soleado",
        "velocidad_base_kmh": 5,
        "precio_vuelo_rapido": None,
        "servicios": [],
        "icono": "🌲",
        "enemigo_faccion_comun": 3,
        "conectado_a": [],
        "monstruos": {
            "normales": [
                {"nombre": "Soldado No-muerto", "lore": "Cadáver imperial que aún empuña su espada.", "clase": "vanguardista"},
                {"nombre": "Cuervo Gigante", "lore": "Ave enorme que picotea los ojos.", "clase": "maestro_caza"},
                {"nombre": "Liana Voraz", "lore": "Planta carnívora con tentáculos espinosos.", "clase": "tejehechizos"}
            ],
            "mini_boss": [
                {"nombre": "Capataz Espectral", "lore": "Antiguo oficial imperial que ronda el bosque.", "clase": "acechante"}
            ],
            "jefes_zona_normal": [{"nombre": "Árbol Ancestral", "lore": "Ente de madera que protege el bosque.", "clase": "vanguardista"}],
            "jefes_zona_dificil": [],
            "mazmorras_normal": [
                {"nombre": "Soldado Imperial Caído", "lore": "Cadáver legionario con armadura oxidada.", "clase": "vanguardista"},
                {"nombre": "Cuervo de la Muerte", "lore": "Ave gigante que anuncia fatalidad.", "clase": "acechante"},
                {"nombre": "Liana Asesina", "lore": "Planta que estrangula a sus presas.", "clase": "tejehechizos"},
                {"nombre": "Centinela Espectral", "lore": "Guardián no-muerto con lanza.", "clase": "maestro_caza"},
                {"nombre": "Murciélago Vampírico", "lore": "Murciélago que chupa la energía vital.", "clase": "acechante"},
                {"nombre": "JEFE: Árbol Ancestral", "lore": "Ente inmenso que controla el bosque imperial.", "clase": "vanguardista"}
            ],
            "mazmorras_dificil": [
                {"nombre": "Legionario Infernal", "lore": "Soldado imperial con fuego infernal en las manos.", "clase": "vanguardista"},
                {"nombre": "Basilisco de Hierro", "lore": "Reptil con mirada petrificante.", "clase": "tejehechizos"},
                {"nombre": "Golem Imperial", "lore": "Autómata de acero y magia.", "clase": "acechante"},
                {"nombre": "Capitán No-muerto", "lore": "Oficial con espada maldita.", "clase": "maestro_caza"},
                {"nombre": "Araña Sombra", "lore": "Arácnido que teje redes oscuras.", "clase": "tejehechizos"},
                {"nombre": "JEFE: Emperador Fantasma", "lore": "Antiguo emperador que ronda el bosque.", "clase": "vanguardista"}
            ]
        }
    },
    # Bosque Sindicato (id 24)
    {
        "id": 24,
        "nombre": "Bosque Sindicato",
        "color": "azul",
        "tipo": "salvaje",
        "faccion_id": 3,
        "nivel_requerido": 1,
        "orden": 2,
        "descripcion": "Bosque donde se ocultan agentes del sindicato.",
        "coord_x": 540,
        "coord_y": 270,
        "materiales_posibles": [
            {"id": "material_14", "rareza": 1, "min": 1, "max": 2, "nivel": 2},
            {"id": "material_44", "rareza": 1, "min": 1, "max": 2, "nivel": 6},
            {"id": "material_48", "rareza": 1, "min": 1, "max": 2, "nivel": 3}
        ],
        "peligrosidad_base": 1.0,
        "nivel_recomendado_min": 1,
        "nivel_recomendado_max": 21,
        "clima": "soleado",
        "velocidad_base_kmh": 5,
        "precio_vuelo_rapido": None,
        "servicios": [],
        "icono": "🌲",
        "enemigo_faccion_comun": 1,
        "conectado_a": [],
        "monstruos": {
            "normales": [
                {"nombre": "Asesino Sombrío", "lore": "Agente del sindicato que ataca desde las sombras.", "clase": "acechante"},
                {"nombre": "Serpiente Arbórea", "lore": "Víbora que cae de las ramas y paraliza.", "clase": "maestro_caza"},
                {"nombre": "Planta Venenosa", "lore": "Planta que lanza espinas tóxicas.", "clase": "tejehechizos"}
            ],
            "mini_boss": [
                {"nombre": "Jefe de la Sombra", "lore": "Líder de la célula del sindicato en el bosque.", "clase": "vanguardista"}
            ],
            "jefes_zona_normal": [{"nombre": "Eco del Pasado", "lore": "Manifestación de un antiguo agente traicionado.", "clase": "vanguardista"}],
            "jefes_zona_dificil": [],
            "mazmorras_normal": [
                {"nombre": "Agente Encubierto", "lore": "Espía que ataca con dagas envenenadas.", "clase": "acechante"},
                {"nombre": "Serpiente de las Sombras", "lore": "Víbora que sale de la maleza.", "clase": "vanguardista"},
                {"nombre": "Planta Alucinógena", "lore": "Planta que lanza polvo alucinógeno.", "clase": "tejehechizos"},
                {"nombre": "Asesino Sombrío", "lore": "Sicario con capa negra.", "clase": "maestro_caza"},
                {"nombre": "Perro de Caza", "lore": "Can adiestrado para rastrear.", "clase": "vanguardista"},
                {"nombre": "JEFE: Eco del Pasado", "lore": "Manifestación de un agente traicionado.", "clase": "tejehechizos"}
            ],
            "mazmorras_dificil": [
                {"nombre": "Maestro del Silencio", "lore": "Asesino que se vuelve invisible.", "clase": "acechante"},
                {"nombre": "Hidra del Sindicato", "lore": "Bestia de tres cabezas entrenada.", "clase": "vanguardista"},
                {"nombre": "Golem de Cristal", "lore": "Autómata transparente que refleja hechizos.", "clase": "maestro_caza"},
                {"nombre": "Jefe de la Sombra", "lore": "Líder del sindicato, maneja dos cuchillas.", "clase": "vanguardista"},
                {"nombre": "Dragón de Jade", "lore": "Criatura mágica controlada por el sindicato.", "clase": "tejehechizos"},
                {"nombre": "JEFE: El Informante", "lore": "Traidor que lucha con artimañas.", "clase": "acechante"}
            ]
        }
    },

    # ==================== ZONAS AMARILLAS SALVAJES (Alianza) ====================
    # Desierto Alianza (id 3)
    {
        "id": 3,
        "nombre": "Desierto Alianza",
        "color": "amarilla",
        "tipo": "salvaje",
        "faccion_id": 1,
        "nivel_requerido": 20,
        "orden": 3,
        "descripcion": "Extenso desierto con tormentas de arena.",
        "coord_x": 130,
        "coord_y": 65,
        "materiales_posibles": [
            {"id": "material_49", "rareza": 4, "min": 1, "max": 2, "nivel": 24},
            {"id": "material_56", "rareza": 4, "min": 1, "max": 2, "nivel": 25}
        ],
        "peligrosidad_base": 1.2,
        "nivel_recomendado_min": 20,
        "nivel_recomendado_max": 50,
        "clima": "tormenta de arena",
        "velocidad_base_kmh": 4,
        "precio_vuelo_rapido": None,
        "servicios": [],
        "icono": "🏜️",
        "enemigo_faccion_comun": 2,
        "conectado_a": [],
        "monstruos": {
            "normales": [
                {"nombre": "Escorpión de Arena", "lore": "Su aguijón inyecta veneno paralizante.", "clase": "vanguardista"},
                {"nombre": "Momia Andante", "lore": "Sacerdote envuelto en vendas malditas.", "clase": "tejehechizos"},
                {"nombre": "Lagarto del Sol", "lore": "Reptil que lanza rayos de calor.", "clase": "maestro_caza"}
            ],
            "mini_boss": [
                {"nombre": "Rey Escorpión", "lore": "Monarca de los artrópodos, su pinza aplasta armaduras.", "clase": "vanguardista"}
            ],
            "jefes_zona_normal": [{"nombre": "Faraón de la Arena", "lore": "Antiguo gobernante momificado, invoca tormentas.", "clase": "vanguardista"}],
            "jefes_zona_dificil": [{"nombre": "El Devorador de Almas", "lore": "Aparece durante las tormentas de arena.", "clase": "vanguardista"}],
            "mazmorras_normal": [
                {"nombre": "Escorpión Menor", "lore": "Pequeño escorpión de veneno rápido.", "clase": "acechante"},
                {"nombre": "Momia Rasgadora", "lore": "Vendas animadas que cortan.", "clase": "vanguardista"},
                {"nombre": "Lagarto de Fuego", "lore": "Reptil que escupe brasas.", "clase": "maestro_caza"},
                {"nombre": "Esqueleto de Guerrero", "lore": "Saqueador del desierto, con cimitarra.", "clase": "vanguardista"},
                {"nombre": "Tótem de Arena", "lore": "Estatua que lanza cegadora.", "clase": "tejehechizos"},
                {"nombre": "JEFE: Faraón de la Arena", "lore": "Gobernante momificado que invoca tormentas.", "clase": "tejehechizos"}
            ],
            "mazmorras_dificil": [
                {"nombre": "Guardián de la Pirámide", "lore": "Golem de piedra arenisca.", "clase": "vanguardista"},
                {"nombre": "Sacerdotisa de la Muerte", "lore": "Momia lanza maldiciones.", "clase": "tejehechizos"},
                {"nombre": "Dragón de Arena", "lore": "Criatura alada que escupe vidrio fundido.", "clase": "maestro_caza"},
                {"nombre": "Coloso de Arena", "lore": "Gigante de arena.", "clase": "vanguardista"},
                {"nombre": "Avatar del Sol", "lore": "Manifestación del dios solar.", "clase": "tejehechizos"},
                {"nombre": "JEFE: El Devorador de Almas", "lore": "Aparece en tormentas de arena.", "clase": "acechante"}
            ]
        }
    },
    # Ruinas Alianza (id 4)
    {
        "id": 4,
        "nombre": "Ruinas Alianza",
        "color": "amarilla",
        "tipo": "salvaje",
        "faccion_id": 1,
        "nivel_requerido": 25,
        "orden": 4,
        "descripcion": "Antiguas ruinas llenas de trampas y no-muertos.",
        "coord_x": 140,
        "coord_y": 70,
        "materiales_posibles": [
            {"id": "material_5", "rareza": 4, "min": 1, "max": 2, "nivel": 26},
            {"id": "material_19", "rareza": 4, "min": 1, "max": 2, "nivel": 30}
        ],
        "peligrosidad_base": 1.2,
        "nivel_recomendado_min": 25,
        "nivel_recomendado_max": 55,
        "clima": "tormenta de arena",
        "velocidad_base_kmh": 4,
        "precio_vuelo_rapido": None,
        "servicios": [],
        "icono": "🏛️",
        "enemigo_faccion_comun": 2,
        "conectado_a": [],
        "monstruos": {
            "normales": [
                {"nombre": "Momia Guerrera", "lore": "Porta una espada oxidada, guardiana de las ruinas.", "clase": "vanguardista"},
                {"nombre": "Insecto Colosal", "lore": "Escarabajo gigante que escupe ácido.", "clase": "maestro_caza"},
                {"nombre": "Aparición del Pasado", "lore": "Espectro que lanza lamentos paralizantes.", "clase": "tejehechizos"}
            ],
            "mini_boss": [
                {"nombre": "Guardián de las Ruinas", "lore": "Golem de piedra, inmune a la magia.", "clase": "vanguardista"}
            ],
            "jefes_zona_normal": [{"nombre": "Espíritu de la Cripta", "lore": "Alma en pena que controla a los muertos.", "clase": "vanguardista"}],
            "jefes_zona_dificil": [],
            "mazmorras_normal": [
                {"nombre": "Momia Guerrero", "lore": "Porta espada oxidada.", "clase": "vanguardista"},
                {"nombre": "Escarabajo Colosal", "lore": "Escarabajo ácido.", "clase": "acechante"},
                {"nombre": "Aparición Susurrante", "lore": "Espectro que reduce la cordura.", "clase": "tejehechizos"},
                {"nombre": "Esqueletos de Legionarios", "lore": "Grupo de esqueletos con escudos.", "clase": "vanguardista"},
                {"nombre": "Golem de Piedra", "lore": "Estatua que cobra vida.", "clase": "maestro_caza"},
                {"nombre": "JEFE: Guardián de las Ruinas", "lore": "Golem de piedra inmune a magia.", "clase": "vanguardista"}
            ],
            "mazmorras_dificil": [
                {"nombre": "Liche Oscuro", "lore": "Nigromante poderoso.", "clase": "tejehechizos"},
                {"nombre": "Vampiro de la Sombra", "lore": "No-muerto que se oculta.", "clase": "acechante"},
                {"nombre": "Gárgola de Obsidiana", "lore": "Escupe alquitrán.", "clase": "maestro_caza"},
                {"nombre": "Caballero de la Muerte", "lore": "Guerrero con armadura negra.", "clase": "vanguardista"},
                {"nombre": "Amo de las Pesadillas", "lore": "Crea ilusiones.", "clase": "tejehechizos"},
                {"nombre": "JEFE: Espectro Real", "lore": "Antiguo rey de las ruinas.", "clase": "acechante"}
            ]
        }
    },
    # Oasis Alianza (id 5)
    {
        "id": 5,
        "nombre": "Oasis Alianza",
        "color": "amarilla",
        "tipo": "salvaje",
        "faccion_id": 1,
        "nivel_requerido": 30,
        "orden": 5,
        "descripcion": "Oasis con aguas y criaturas acechantes.",
        "coord_x": 150,
        "coord_y": 75,
        "materiales_posibles": [
            {"id": "material_5", "rareza": 4, "min": 1, "max": 2, "nivel": 26},
            {"id": "material_9", "rareza": 4, "min": 1, "max": 2, "nivel": 35}
        ],
        "peligrosidad_base": 1.2,
        "nivel_recomendado_min": 30,
        "nivel_recomendado_max": 60,
        "clima": "tormenta de arena",
        "velocidad_base_kmh": 4,
        "precio_vuelo_rapido": None,
        "servicios": [],
        "icono": "🏝️",
        "enemigo_faccion_comun": 2,
        "conectado_a": [],
        "monstruos": {
            "normales": [
                {"nombre": "Cocodrilo del Oasis", "lore": "Reptil gigante, mordida letal.", "clase": "vanguardista"},
                {"nombre": "Djinn Menor", "lore": "Ser de aire que aturde con ráfagas.", "clase": "tejehechizos"},
                {"nombre": "Planta Carnívora", "lore": "Atrapa presas con lianas espinosas.", "clase": "acechante"}
            ],
            "mini_boss": [
                {"nombre": "Señor del Oasis", "lore": "Genio de la lámpara, concede deseos retorcidos.", "clase": "tejehechizos"}
            ],
            "jefes_zona_normal": [],
            "jefes_zona_dificil": [],
            "mazmorras_normal": [
                {"nombre": "Cocodrilo del Oasis", "lore": "Reptil gigante de mordida letal.", "clase": "vanguardista"},
                {"nombre": "Djinn Menor", "lore": "Ser de aire que aturde.", "clase": "tejehechizos"},
                {"nombre": "Planta Carnívora", "lore": "Atrapa con lianas espinosas.", "clase": "acechante"},
                {"nombre": "Salamandra de Agua", "lore": "Anfibio que escupe agua hirviendo.", "clase": "maestro_caza"},
                {"nombre": "Tritón Guerrero", "lore": "Humanoide con lanza.", "clase": "vanguardista"},
                {"nombre": "JEFE: Señor del Oasis", "lore": "Genio de la lámpara.", "clase": "tejehechizos"}
            ],
            "mazmorras_dificil": [
                {"nombre": "Hidra de dos Cabezas", "lore": "Serpiente acuática.", "clase": "vanguardista"},
                {"nombre": "Elemental de Agua", "lore": "Gólem líquido.", "clase": "tejehechizos"},
                {"nombre": "Sirena Maldita", "lore": "Canto hipnótico.", "clase": "maestro_caza"},
                {"nombre": "Leviatán Joven", "lore": "Bestia marina.", "clase": "acechante"},
                {"nombre": "Bruja del Oasis", "lore": "Hechicera que envenena.", "clase": "tejehechizos"},
                {"nombre": "JEFE: Dragón del Oasis", "lore": "Antiguo guardián.", "clase": "vanguardista"}
            ]
        }
    },

    # ==================== ZONAS AMARILLAS (Imperio) ====================
    # Desierto Imperio (id 14)
    {
        "id": 14,
        "nombre": "Desierto Imperio",
        "color": "amarilla",
        "tipo": "salvaje",
        "faccion_id": 2,
        "nivel_requerido": 20,
        "orden": 3,
        "descripcion": "Desierto imperial con minas abandonadas.",
        "coord_x": 340,
        "coord_y": 170,
        "materiales_posibles": [
            {"id": "material_49", "rareza": 4, "min": 1, "max": 2, "nivel": 24},
            {"id": "material_56", "rareza": 4, "min": 1, "max": 2, "nivel": 25}
        ],
        "peligrosidad_base": 1.2,
        "nivel_recomendado_min": 20,
        "nivel_recomendado_max": 50,
        "clima": "tormenta de arena",
        "velocidad_base_kmh": 4,
        "precio_vuelo_rapido": None,
        "servicios": [],
        "icono": "🏜️",
        "enemigo_faccion_comun": 3,
        "conectado_a": [],
        "monstruos": {
            "normales": [
                {"nombre": "Gusano de las Dunas", "lore": "Criatura que emerge de la arena y traga a sus víctimas.", "clase": "acechante"},
                {"nombre": "Trampero Imperial", "lore": "Soldado desertor que ataca con cuchillos envenenados.", "clase": "maestro_caza"}
            ],
            "mini_boss": [
                {"nombre": "Sultán de las Arenas", "lore": "Antiguo señor de la guerra.", "clase": "vanguardista"}
            ],
            "jefes_zona_normal": [{"nombre": "Guardián de la Tumba", "lore": "Espectro imperial que defiende un tesoro.", "clase": "vanguardista"}],
            "jefes_zona_dificil": [],
            "mazmorras_normal": [
                {"nombre": "Gusano de las Dunas", "lore": "Criatura que traga.", "clase": "acechante"},
                {"nombre": "Trampero Imperial", "lore": "Soldado desertor.", "clase": "maestro_caza"},
                {"nombre": "Escorpión Imperial", "lore": "Escorpión blindado.", "clase": "vanguardista"},
                {"nombre": "Momia Legionaria", "lore": "Restos de un soldado.", "clase": "tejehechizos"},
                {"nombre": "Elemental de Arena", "lore": "Torbellino.", "clase": "maestro_caza"},
                {"nombre": "JEFE: Sultán de las Arenas", "lore": "Antiguo señor de la guerra.", "clase": "vanguardista"}
            ],
            "mazmorras_dificil": [
                {"nombre": "Guardián de la Tumba Imperial", "lore": "Espectro imperial.", "clase": "tejehechizos"},
                {"nombre": "Golem de Obsidiana", "lore": "Gólem negro.", "clase": "vanguardista"},
                {"nombre": "Basilisco Imperial", "lore": "Mirada mortal.", "clase": "acechante"},
                {"nombre": "Sacerdote Infernal", "lore": "Lanza maldiciones.", "clase": "tejehechizos"},
                {"nombre": "Dragón de Arena Imperial", "lore": "Criatura alada.", "clase": "maestro_caza"},
                {"nombre": "JEFE: Faraón Resucitado", "lore": "Emperador momificado.", "clase": "vanguardista"}
            ]
        }
    },
    # Ruinas Imperio (id 15)
    {
        "id": 15,
        "nombre": "Ruinas Imperio",
        "color": "amarilla",
        "tipo": "salvaje",
        "faccion_id": 2,
        "nivel_requerido": 25,
        "orden": 4,
        "descripcion": "Ruinas de una antigua fortaleza imperial.",
        "coord_x": 350,
        "coord_y": 175,
        "materiales_posibles": [
            {"id": "material_5", "rareza": 4, "min": 1, "max": 2, "nivel": 26},
            {"id": "material_19", "rareza": 4, "min": 1, "max": 2, "nivel": 30}
        ],
        "peligrosidad_base": 1.2,
        "nivel_recomendado_min": 25,
        "nivel_recomendado_max": 55,
        "clima": "tormenta de arena",
        "velocidad_base_kmh": 4,
        "precio_vuelo_rapido": None,
        "servicios": [],
        "icono": "🏛️",
        "enemigo_faccion_comun": 3,
        "conectado_a": [],
        "monstruos": {
            "normales": [
                {"nombre": "Soldado Fantasma", "lore": "Alma de un legionario imperial.", "clase": "tejehechizos"},
                {"nombre": "Escarabajo de Fuego", "lore": "Escarabajo que lanza bolas de fuego.", "clase": "maestro_caza"}
            ],
            "mini_boss": [
                {"nombre": "Centurión Sombra", "lore": "Legionario no-muerto con gran defensa.", "clase": "vanguardista"}
            ],
            "jefes_zona_normal": [],
            "jefes_zona_dificil": [],
            "mazmorras_normal": [
                {"nombre": "Soldado Fantasma", "lore": "Alma legionaria.", "clase": "tejehechizos"},
                {"nombre": "Escarabajo de Fuego", "lore": "Escarabajo de lava.", "clase": "maestro_caza"},
                {"nombre": "Centinela de Piedra", "lore": "Estatua guardiana.", "clase": "vanguardista"},
                {"nombre": "Arquero Momificado", "lore": "Dispara flechas malditas.", "clase": "acechante"},
                {"nombre": "Liche Menor", "lore": "Nigromante novato.", "clase": "tejehechizos"},
                {"nombre": "JEFE: Centurión Sombra", "lore": "Legionario no-muerto.", "clase": "vanguardista"}
            ],
            "mazmorras_dificil": [
                {"nombre": "Coloso de Bronce", "lore": "Gólem metálico.", "clase": "vanguardista"},
                {"nombre": "Aparición del Emperador", "lore": "Fantasma imperial.", "clase": "tejehechizos"},
                {"nombre": "Serpiente Emplumada", "lore": "Dios menor.", "clase": "maestro_caza"},
                {"nombre": "Torturador de Almas", "lore": "Demonio de cadenas.", "clase": "acechante"},
                {"nombre": "Avatar del Caos", "lore": "Entidad cambiante.", "clase": "tejehechizos"},
                {"nombre": "JEFE: Guardián de la Cripta", "lore": "Espectro con llave.", "clase": "vanguardista"}
            ]
        }
    },
    # Oasis Imperio (id 16)
    {
        "id": 16,
        "nombre": "Oasis Imperio",
        "color": "amarilla",
        "tipo": "salvaje",
        "faccion_id": 2,
        "nivel_requerido": 30,
        "orden": 5,
        "descripcion": "Oasis codiciado por caravanas.",
        "coord_x": 360,
        "coord_y": 180,
        "materiales_posibles": [
            {"id": "material_5", "rareza": 4, "min": 1, "max": 2, "nivel": 26},
            {"id": "material_9", "rareza": 4, "min": 1, "max": 2, "nivel": 35}
        ],
        "peligrosidad_base": 1.2,
        "nivel_recomendado_min": 30,
        "nivel_recomendado_max": 60,
        "clima": "tormenta de arena",
        "velocidad_base_kmh": 4,
        "precio_vuelo_rapido": None,
        "servicios": [],
        "icono": "🏝️",
        "enemigo_faccion_comun": 3,
        "conectado_a": [],
        "monstruos": {
            "normales": [
                {"nombre": "Hidra Menor", "lore": "Serpiente de dos cabezas que escupe veneno.", "clase": "vanguardista"},
                {"nombre": "Bandido del Oasis", "lore": "Ladrón que acecha a los viajeros.", "clase": "acechante"}
            ],
            "mini_boss": [
                {"nombre": "Jefe de la Hidra", "lore": "Hidra de tres cabezas con aliento corrosivo.", "clase": "vanguardista"}
            ],
            "jefes_zona_normal": [],
            "jefes_zona_dificil": [],
            "mazmorras_normal": [
                {"nombre": "Hidra Menor", "lore": "Serpiente de dos cabezas.", "clase": "vanguardista"},
                {"nombre": "Bandido del Oasis", "lore": "Ladrón.", "clase": "acechante"},
                {"nombre": "Lagarto del Sol", "lore": "Reptil ígneo.", "clase": "maestro_caza"},
                {"nombre": "Espía Imperial", "lore": "Agente encubierto.", "clase": "acechante"},
                {"nombre": "Carroñero de Agua", "lore": "Cangrejo gigante.", "clase": "vanguardista"},
                {"nombre": "JEFE: Jefe de la Hidra", "lore": "Hidra de tres cabezas.", "clase": "vanguardista"}
            ],
            "mazmorras_dificil": [
                {"nombre": "Leviatán de Agua", "lore": "Monstruo marino.", "clase": "vanguardista"},
                {"nombre": "Elemental de Agua Sagrada", "lore": "Gólem curativo.", "clase": "tejehechizos"},
                {"nombre": "Sirena Guerrera", "lore": "Canta y ataca.", "clase": "maestro_caza"},
                {"nombre": "Tortuga Dragón", "lore": "Caparazón ardiente.", "clase": "vanguardista"},
                {"nombre": "Bruja del Lago", "lore": "Hechicera anciana.", "clase": "tejehechizos"},
                {"nombre": "JEFE: Rey del Oasis", "lore": "Genio malvado.", "clase": "tejehechizos"}
            ]
        }
    },

    # ==================== ZONAS AMARILLAS (Sindicato) ====================
    # Desierto Sindicato (id 25)
    {
        "id": 25,
        "nombre": "Desierto Sindicato",
        "color": "amarilla",
        "tipo": "salvaje",
        "faccion_id": 3,
        "nivel_requerido": 20,
        "orden": 3,
        "descripcion": "Desierto controlado por el sindicato, lleno de agentes.",
        "coord_x": 550,
        "coord_y": 275,
        "materiales_posibles": [
            {"id": "material_49", "rareza": 4, "min": 1, "max": 2, "nivel": 24},
            {"id": "material_56", "rareza": 4, "min": 1, "max": 2, "nivel": 25}
        ],
        "peligrosidad_base": 1.2,
        "nivel_recomendado_min": 20,
        "nivel_recomendado_max": 50,
        "clima": "tormenta de arena",
        "velocidad_base_kmh": 4,
        "precio_vuelo_rapido": None,
        "servicios": [],
        "icono": "🏜️",
        "enemigo_faccion_comun": 1,
        "conectado_a": [],
        "monstruos": {
            "normales": [
                {"nombre": "Acechador del Sindicato", "lore": "Mercenario que ataca con dagas.", "clase": "acechante"},
                {"nombre": "Lagarto de Fuego", "lore": "Reptil que escupe llamas.", "clase": "maestro_caza"}
            ],
            "mini_boss": [
                {"nombre": "Ejecutor del Sindicato", "lore": "Asesino con capa roja.", "clase": "vanguardista"}
            ],
            "jefes_zona_normal": [],
            "jefes_zona_dificil": [],
            "mazmorras_normal": [
                {"nombre": "Acechador del Sindicato", "lore": "Mercenario.", "clase": "acechante"},
                {"nombre": "Lagarto de Fuego", "lore": "Reptil ígneo.", "clase": "maestro_caza"},
                {"nombre": "Escorpión Venenoso", "lore": "Escorpión de gran tamaño.", "clase": "vanguardista"},
                {"nombre": "Momia del Sindicato", "lore": "Cadáver reanimado.", "clase": "tejehechizos"},
                {"nombre": "Tótem Maldito", "lore": "Estatua que maldice.", "clase": "tejehechizos"},
                {"nombre": "JEFE: Ejecutor del Sindicato", "lore": "Asesino con capa roja.", "clase": "vanguardista"}
            ],
            "mazmorras_dificil": [
                {"nombre": "Guardián de las Dunas", "lore": "Gólem de arena.", "clase": "vanguardista"},
                {"nombre": "Basilisco del Sindicato", "lore": "Mirada de piedra.", "clase": "acechante"},
                {"nombre": "Liche del Desierto", "lore": "Nigromante.", "clase": "tejehechizos"},
                {"nombre": "Dragón de Cristal", "lore": "Dragón traslúcido.", "clase": "maestro_caza"},
                {"nombre": "Avatar del Viento", "lore": "Tormenta viviente.", "clase": "tejehechizos"},
                {"nombre": "JEFE: Señor de la Arena", "lore": "Genio del sindicato.", "clase": "vanguardista"}
            ]
        }
    },
    # Ruinas Sindicato (id 26)
    {
        "id": 26,
        "nombre": "Ruinas Sindicato",
        "color": "amarilla",
        "tipo": "salvaje",
        "faccion_id": 3,
        "nivel_requerido": 25,
        "orden": 4,
        "descripcion": "Ruinas usadas como base por el sindicato.",
        "coord_x": 560,
        "coord_y": 280,
        "materiales_posibles": [
            {"id": "material_5", "rareza": 4, "min": 1, "max": 2, "nivel": 26},
            {"id": "material_19", "rareza": 4, "min": 1, "max": 2, "nivel": 30}
        ],
        "peligrosidad_base": 1.2,
        "nivel_recomendado_min": 25,
        "nivel_recomendado_max": 55,
        "clima": "tormenta de arena",
        "velocidad_base_kmh": 4,
        "precio_vuelo_rapido": None,
        "servicios": [],
        "icono": "🏛️",
        "enemigo_faccion_comun": 1,
        "conectado_a": [],
        "monstruos": {
            "normales": [
                {"nombre": "Robot Explorador", "lore": "Autómata oxidado que ataca a distancia.", "clase": "maestro_caza"},
                {"nombre": "Espía Fantasma", "lore": "Agente invisible.", "clase": "acechante"}
            ],
            "mini_boss": [
                {"nombre": "Maestro de las Ruinas", "lore": "Nigromante que controla a los muertos.", "clase": "tejehechizos"}
            ],
            "jefes_zona_normal": [],
            "jefes_zona_dificil": [],
            "mazmorras_normal": [
                {"nombre": "Robot Explorador", "lore": "Autómata oxidado.", "clase": "maestro_caza"},
                {"nombre": "Espía Fantasma", "lore": "Agente invisible.", "clase": "acechante"},
                {"nombre": "Esqueleto Artillero", "lore": "Esqueleto con ballesta.", "clase": "maestro_caza"},
                {"nombre": "Gárgola de Piedra", "lore": "Escupe alquitrán.", "clase": "vanguardista"},
                {"nombre": "Trampa Viviente", "lore": "Mecanismo espinoso.", "clase": "acechante"},
                {"nombre": "JEFE: Maestro de las Ruinas", "lore": "Nigromante del sindicato.", "clase": "tejehechizos"}
            ],
            "mazmorras_dificil": [
                {"nombre": "Golem de Acero", "lore": "Robot de combate.", "clase": "vanguardista"},
                {"nombre": "Aparición del Director", "lore": "Fantasma de un jefe.", "clase": "tejehechizos"},
                {"nombre": "Vampiro Industrial", "lore": "No-muerto con jeringas.", "clase": "acechante"},
                {"nombre": "Quimera de Metal", "lore": "Bestia mecánica.", "clase": "maestro_caza"},
                {"nombre": "Demonio de las Cadenas", "lore": "Esbirro del sindicato.", "clase": "vanguardista"},
                {"nombre": "JEFE: El Informante Supremo", "lore": "Líder corrupto.", "clase": "acechante"}
            ]
        }
    },
    # Oasis Sindicato (id 27)
    {
        "id": 27,
        "nombre": "Oasis Sindicato",
        "color": "amarilla",
        "tipo": "salvaje",
        "faccion_id": 3,
        "nivel_requerido": 30,
        "orden": 5,
        "descripcion": "Oasis donde se reúnen los líderes del sindicato.",
        "coord_x": 570,
        "coord_y": 285,
        "materiales_posibles": [
            {"id": "material_5", "rareza": 4, "min": 1, "max": 2, "nivel": 26},
            {"id": "material_9", "rareza": 4, "min": 1, "max": 2, "nivel": 35}
        ],
        "peligrosidad_base": 1.2,
        "nivel_recomendado_min": 30,
        "nivel_recomendado_max": 60,
        "clima": "tormenta de arena",
        "velocidad_base_kmh": 4,
        "precio_vuelo_rapido": None,
        "servicios": [],
        "icono": "🏝️",
        "enemigo_faccion_comun": 1,
        "conectado_a": [],
        "monstruos": {
            "normales": [
                {"nombre": "Guardaespaldas del Sindicato", "lore": "Soldado de élite con armadura pesada.", "clase": "vanguardista"},
                {"nombre": "Serpiente del Oasis", "lore": "Víbora venenosa de gran tamaño.", "clase": "acechante"}
            ],
            "mini_boss": [
                {"nombre": "Informante", "lore": "Agente que lanza cuchillos y desaparece.", "clase": "acechante"}
            ],
            "jefes_zona_normal": [],
            "jefes_zona_dificil": [],
            "mazmorras_normal": [
                {"nombre": "Guardaespaldas del Sindicato", "lore": "Soldado élite.", "clase": "vanguardista"},
                {"nombre": "Serpiente del Oasis", "lore": "Víbora venenosa.", "clase": "acechante"},
                {"nombre": "Cocodrilo Bebé", "lore": "Cría voraz.", "clase": "maestro_caza"},
                {"nombre": "Hidra Pequeña", "lore": "Dos cabezas.", "clase": "vanguardista"},
                {"nombre": "Planta Acuática", "lore": "Alga carnívora.", "clase": "tejehechizos"},
                {"nombre": "JEFE: Informante", "lore": "Agente que lanza cuchillos.", "clase": "acechante"}
            ],
            "mazmorras_dificil": [
                {"nombre": "Tritón Malvado", "lore": "Humanoide acuático.", "clase": "vanguardista"},
                {"nombre": "Leviatán Joven", "lore": "Bestia marina.", "clase": "acechante"},
                {"nombre": "Sirena Asesina", "lore": "Canto mortal.", "clase": "tejehechizos"},
                {"nombre": "Cangrejo Gigante", "lore": "Pinzas aplastantes.", "clase": "vanguardista"},
                {"nombre": "Elemental de Agua Negra", "lore": "Gólem corrupto.", "clase": "tejehechizos"},
                {"nombre": "JEFE: Dragón del Oasis Sindicato", "lore": "Criatura ancestral.", "clase": "maestro_caza"}
            ]
        }
    },

    # ==================== ZONAS ROJAS (Alianza) ====================
    # Tierras Magmáticas Alianza (id 6)
    {
        "id": 6,
        "nombre": "Tierras Magmáticas Alianza",
        "color": "roja",
        "tipo": "salvaje",
        "faccion_id": 1,
        "nivel_requerido": 45,
        "orden": 6,
        "descripcion": "Terreno volcánico con ríos de lava.",
        "coord_x": 160,
        "coord_y": 80,
        "materiales_posibles": [
            {"id": "material_115", "rareza": 7, "min": 1, "max": 2, "nivel": 47},
            {"id": "material_137", "rareza": 7, "min": 1, "max": 2, "nivel": 46},
            {"id": "material_11", "rareza": 8, "min": 1, "max": 2, "nivel": 42}
        ],
        "peligrosidad_base": 1.5,
        "nivel_recomendado_min": 45,
        "nivel_recomendado_max": 85,
        "clima": "calor extremo",
        "velocidad_base_kmh": 3,
        "precio_vuelo_rapido": None,
        "servicios": [],
        "icono": "🌋",
        "enemigo_faccion_comun": 2,
        "conectado_a": [],
        "monstruos": {
            "normales": [
                {"nombre": "Diablillo de Lava", "lore": "Pequeño demonio que arroja bolas de magma.", "clase": "maestro_caza"},
                {"nombre": "Golem de Ceniza", "lore": "Humanoide de ceniza que se dispersa al golpear.", "clase": "vanguardista"}
            ],
            "mini_boss": [
                {"nombre": "Señor de las Llamas", "lore": "Comandante de los diablillos, tridente de fuego.", "clase": "vanguardista"}
            ],
            "jefes_zona_normal": [{"nombre": "Príncipe del Fuego", "lore": "Noble demonio con alas de brasa.", "clase": "vanguardista"}],
            "jefes_zona_dificil": [{"nombre": "Señor del Abismo Ígneo", "lore": "Controla el magma del volcán.", "clase": "vanguardista"}],
            "mazmorras_normal": [
                {"nombre": "Esclavo de Lava", "lore": "Humanoide fundido.", "clase": "vanguardista"},
                {"nombre": "Golem de Ceniza", "lore": "Gólem de ceniza.", "clase": "vanguardista"},
                {"nombre": "Diablillo Lanzallamas", "lore": "Demonio menor.", "clase": "maestro_caza"},
                {"nombre": "Elemental de Magma", "lore": "Ser de fuego puro.", "clase": "tejehechizos"},
                {"nombre": "Guardián de la Forja", "lore": "Defensor con martillo.", "clase": "vanguardista"},
                {"nombre": "JEFE: Herrero Infernal", "lore": "Jefe de la mazmorra.", "clase": "vanguardista"}
            ],
            "mazmorras_dificil": [
                {"nombre": "Demonio de las Cadenas", "lore": "Arrastra a la lava.", "clase": "acechante"},
                {"nombre": "Titan de Cenizas", "lore": "Gigante de roca.", "clase": "vanguardista"},
                {"nombre": "Señor de las Llamas", "lore": "Comandante infernal.", "clase": "vanguardista"},
                {"nombre": "Dragón de Magma", "lore": "Bestia alada.", "clase": "maestro_caza"},
                {"nombre": "Avatar del Volcán", "lore": "Dios del fuego.", "clase": "tejehechizos"},
                {"nombre": "JEFE: Rey del Abismo Ígneo", "lore": "Señor supremo.", "clase": "vanguardista"}
            ]
        }
    },
    # Cima del Dragón Alianza (id 7)
    {
        "id": 7,
        "nombre": "Cima del Dragón Alianza",
        "color": "roja",
        "tipo": "salvaje",
        "faccion_id": 1,
        "nivel_requerido": 50,
        "orden": 7,
        "descripcion": "Pico volcánico donde anidan dragones.",
        "coord_x": 170,
        "coord_y": 85,
        "materiales_posibles": [
            {"id": "material_115", "rareza": 7, "min": 1, "max": 2, "nivel": 47},
            {"id": "material_137", "rareza": 7, "min": 1, "max": 2, "nivel": 46},
            {"id": "material_17", "rareza": 8, "min": 1, "max": 2, "nivel": 52}
        ],
        "peligrosidad_base": 1.5,
        "nivel_recomendado_min": 50,
        "nivel_recomendado_max": 90,
        "clima": "calor extremo",
        "velocidad_base_kmh": 3,
        "precio_vuelo_rapido": None,
        "servicios": [],
        "icono": "🐉",
        "enemigo_faccion_comun": 2,
        "conectado_a": [],
        "monstruos": {
            "normales": [
                {"nombre": "Salamandra Ígnea", "lore": "Lagarto que escupe llamaradas.", "clase": "maestro_caza"},
                {"nombre": "Murciélago de Fuego", "lore": "Aletea y esparce chispas.", "clase": "acechante"}
            ],
            "mini_boss": [
                {"nombre": "Matriarca Ígnea", "lore": "Salamandra gigante, crías ayudan en combate.", "clase": "vanguardista"}
            ],
            "jefes_zona_normal": [{"nombre": "Dragón de Magma", "lore": "Antigua bestia volcánica, aliento funde roca.", "clase": "vanguardista"}],
            "jefes_zona_dificil": [{"nombre": "El Devorador de Almas", "lore": "Aparece en la cámara de lava.", "clase": "vanguardista"}],
            "mazmorras_normal": [
                {"nombre": "Acólito del Dragón", "lore": "Humanoide adorador.", "clase": "tejehechizos"},
                {"nombre": "Gusano de Lava", "lore": "Gusano ígneo.", "clase": "acechante"},
                {"nombre": "Murciélago de Fuego", "lore": "Aletea chispas.", "clase": "acechante"},
                {"nombre": "Salamandra Ígnea", "lore": "Lagarto de fuego.", "clase": "maestro_caza"},
                {"nombre": "Elemental de Fuego", "lore": "Llama viviente.", "clase": "tejehechizos"},
                {"nombre": "JEFE: Campeón del Dragón", "lore": "Guerrero escamado.", "clase": "vanguardista"}
            ],
            "mazmorras_dificil": [
                {"nombre": "Guardia del Dragón", "lore": "Soldado con armadura de dragón.", "clase": "vanguardista"},
                {"nombre": "Matriarca Ígnea", "lore": "Salamandra gigante.", "clase": "vanguardista"},
                {"nombre": "Príncipe del Fuego", "lore": "Noble demonio.", "clase": "maestro_caza"},
                {"nombre": "Señor del Abismo Ígneo", "lore": "Controla magma.", "clase": "tejehechizos"},
                {"nombre": "Avatar de la Llama", "lore": "Incarnación del fuego.", "clase": "tejehechizos"},
                {"nombre": "JEFE: Dragón de Magma Alianza", "lore": "Antiguo dragón.", "clase": "vanguardista"}
            ]
        }
    },
    # Forja Abandonada Alianza (id 8)
    {
        "id": 8,
        "nombre": "Forja Abandonada Alianza",
        "color": "roja",
        "tipo": "salvaje",
        "faccion_id": 1,
        "nivel_requerido": 55,
        "orden": 8,
        "descripcion": "Antigua forja volcánica, llena de demonios.",
        "coord_x": 180,
        "coord_y": 90,
        "materiales_posibles": [
            {"id": "material_26", "rareza": 7, "min": 1, "max": 2, "nivel": 56},
            {"id": "material_55", "rareza": 7, "min": 1, "max": 2, "nivel": 56},
            {"id": "material_17", "rareza": 8, "min": 1, "max": 2, "nivel": 52}
        ],
        "peligrosidad_base": 1.5,
        "nivel_recomendado_min": 55,
        "nivel_recomendado_max": 95,
        "clima": "calor extremo",
        "velocidad_base_kmh": 3,
        "precio_vuelo_rapido": None,
        "servicios": [],
        "icono": "🏭",
        "enemigo_faccion_comun": 2,
        "conectado_a": [],
        "monstruos": {
            "normales": [
                {"nombre": "Elemental de Humo", "lore": "Ciega con su nube tóxica, difícil de golpear.", "clase": "tejehechizos"},
                {"nombre": "Esclavo de Lava", "lore": "Humanoide fundido, sus garras queman.", "clase": "vanguardista"}
            ],
            "mini_boss": [
                {"nombre": "Titan de Cenizas", "lore": "Gólem gigante, puñetazo en área.", "clase": "vanguardista"}
            ],
            "jefes_zona_normal": [{"nombre": "El Maestro de Hornos", "lore": "Ingeniero demoníaco, activa trampas de lava.", "clase": "vanguardista"}],
            "jefes_zona_dificil": [{"nombre": "El Rey del Abismo", "lore": "Ser divino que habita en el núcleo del volcán.", "clase": "vanguardista"}],
            "mazmorras_normal": [
                {"nombre": "Elemental de Humo", "lore": "Nube tóxica.", "clase": "tejehechizos"},
                {"nombre": "Esclavo de Lava", "lore": "Humanoide fundido.", "clase": "vanguardista"},
                {"nombre": "Diablillo Martillo", "lore": "Demonio con martillo.", "clase": "vanguardista"},
                {"nombre": "Golem de Ceniza", "lore": "Gólem frágil.", "clase": "acechante"},
                {"nombre": "Centinela de Fuego", "lore": "Soldado ígneo.", "clase": "maestro_caza"},
                {"nombre": "JEFE: El Maestro de Hornos", "lore": "Ingeniero demoníaco.", "clase": "tejehechizos"}
            ],
            "mazmorras_dificil": [
                {"nombre": "Guardia Infernal", "lore": "Guerrero ardiente.", "clase": "vanguardista"},
                {"nombre": "Titan de Cenizas", "lore": "Gigante.", "clase": "vanguardista"},
                {"nombre": "Forjador de Almas", "lore": "Demonio forjador.", "clase": "maestro_caza"},
                {"nombre": "Demonio de las Cadenas", "lore": "Esbirro infernal.", "clase": "acechante"},
                {"nombre": "Avatar del Volcán", "lore": "Dios del fuego.", "clase": "tejehechizos"},
                {"nombre": "JEFE: El Rey del Abismo", "lore": "Señor supremo.", "clase": "vanguardista"}
            ]
        }
    },

    # ==================== ZONAS ROJAS (Imperio) ====================
    # Tierras Magmáticas Imperio (id 17)
    {
        "id": 17,
        "nombre": "Tierras Magmáticas Imperio",
        "color": "roja",
        "tipo": "salvaje",
        "faccion_id": 2,
        "nivel_requerido": 45,
        "orden": 6,
        "descripcion": "Zona volcánica dominada por el imperio.",
        "coord_x": 370,
        "coord_y": 185,
        "materiales_posibles": [
            {"id": "material_115", "rareza": 7, "min": 1, "max": 2, "nivel": 47},
            {"id": "material_137", "rareza": 7, "min": 1, "max": 2, "nivel": 46},
            {"id": "material_11", "rareza": 8, "min": 1, "max": 2, "nivel": 42}
        ],
        "peligrosidad_base": 1.5,
        "nivel_recomendado_min": 45,
        "nivel_recomendado_max": 85,
        "clima": "calor extremo",
        "velocidad_base_kmh": 3,
        "precio_vuelo_rapido": None,
        "servicios": [],
        "icono": "🌋",
        "enemigo_faccion_comun": 3,
        "conectado_a": [],
        "monstruos": {
            "normales": [
                {"nombre": "Legionario de Fuego", "lore": "Soldado imperial con armadura ignífuga.", "clase": "vanguardista"},
                {"nombre": "Elemental de Piedra", "lore": "Golem de roca fundida.", "clase": "vanguardista"}
            ],
            "mini_boss": [
                {"nombre": "Centurión Inmortal", "lore": "Oficial no-muerto con gran poder.", "clase": "vanguardista"}
            ],
            "jefes_zona_normal": [],
            "jefes_zona_dificil": [],
            "mazmorras_normal": [
                {"nombre": "Legionario de Fuego", "lore": "Soldado de fuego.", "clase": "vanguardista"},
                {"nombre": "Elemental de Piedra", "lore": "Gólem rocoso.", "clase": "vanguardista"},
                {"nombre": "Diablillo Imperial", "lore": "Demonio menor.", "clase": "maestro_caza"},
                {"nombre": "Golem de Ceniza", "lore": "Gólem de ceniza.", "clase": "acechante"},
                {"nombre": "Centinela de Lava", "lore": "Guardián ígneo.", "clase": "vanguardista"},
                {"nombre": "JEFE: Centurión Inmortal", "lore": "Oficial no-muerto.", "clase": "vanguardista"}
            ],
            "mazmorras_dificil": [
                {"nombre": "General de la Llama", "lore": "Comandante supremo.", "clase": "vanguardista"},
                {"nombre": "Dragón de Magma Imperial", "lore": "Bestia alada.", "clase": "maestro_caza"},
                {"nombre": "Señor del Abismo Imperial", "lore": "Entidad del vacío.", "clase": "tejehechizos"},
                {"nombre": "Titan de Fuego", "lore": "Gigante ardiente.", "clase": "vanguardista"},
                {"nombre": "Avatar de la Destrucción", "lore": "Dios de la guerra.", "clase": "tejehechizos"},
                {"nombre": "JEFE: Emperador del Fuego", "lore": "Monarca infernal.", "clase": "vanguardista"}
            ]
        }
    },
    # Cima del Dragón Imperio (id 18)
    {
        "id": 18,
        "nombre": "Cima del Dragón Imperio",
        "color": "roja",
        "tipo": "salvaje",
        "faccion_id": 2,
        "nivel_requerido": 50,
        "orden": 7,
        "descripcion": "Cima donde reside un dragón imperial.",
        "coord_x": 380,
        "coord_y": 190,
        "materiales_posibles": [
            {"id": "material_115", "rareza": 7, "min": 1, "max": 2, "nivel": 47},
            {"id": "material_137", "rareza": 7, "min": 1, "max": 2, "nivel": 46},
            {"id": "material_17", "rareza": 8, "min": 1, "max": 2, "nivel": 52}
        ],
        "peligrosidad_base": 1.5,
        "nivel_recomendado_min": 50,
        "nivel_recomendado_max": 90,
        "clima": "calor extremo",
        "velocidad_base_kmh": 3,
        "precio_vuelo_rapido": None,
        "servicios": [],
        "icono": "🐉",
        "enemigo_faccion_comun": 3,
        "conectado_a": [],
        "monstruos": {
            "normales": [
                {"nombre": "Acólito del Dragón", "lore": "Humanoide que venera al dragón.", "clase": "tejehechizos"},
                {"nombre": "Gusano de Lava", "lore": "Criatura que sale de las grietas.", "clase": "acechante"}
            ],
            "mini_boss": [
                {"nombre": "Campeón del Dragón", "lore": "Guerrero con armadura escamada.", "clase": "vanguardista"}
            ],
            "jefes_zona_normal": [{"nombre": "Dragón de Magma Imperio", "lore": "Bestia alada que escupe fuego.", "clase": "vanguardista"}],
            "jefes_zona_dificil": [],
            "mazmorras_normal": [
                {"nombre": "Acólito del Dragón", "lore": "Adorador.", "clase": "tejehechizos"},
                {"nombre": "Gusano de Lava", "lore": "Gusano.", "clase": "acechante"},
                {"nombre": "Murciélago de Fuego", "lore": "Chispas.", "clase": "acechante"},
                {"nombre": "Salamandra Ígnea", "lore": "Lagarto.", "clase": "maestro_caza"},
                {"nombre": "Elemental de Fuego", "lore": "Llama.", "clase": "tejehechizos"},
                {"nombre": "JEFE: Campeón del Dragón", "lore": "Guerrero escamado.", "clase": "vanguardista"}
            ],
            "mazmorras_dificil": [
                {"nombre": "Guardia Imperial", "lore": "Soldado dragón.", "clase": "vanguardista"},
                {"nombre": "Matriarca Ígnea", "lore": "Salamandra.", "clase": "vanguardista"},
                {"nombre": "Príncipe del Fuego", "lore": "Demonio.", "clase": "maestro_caza"},
                {"nombre": "Señor del Abismo", "lore": "Entidad.", "clase": "tejehechizos"},
                {"nombre": "Dragón Emperador", "lore": "Rey dragón.", "clase": "vanguardista"},
                {"nombre": "JEFE: Dragón de Magma Supremo", "lore": "Ancestro.", "clase": "vanguardista"}
            ]
        }
    },
    # Forja Abandonada Imperio (id 19)
    {
        "id": 19,
        "nombre": "Forja Abandonada Imperio",
        "color": "roja",
        "tipo": "salvaje",
        "faccion_id": 2,
        "nivel_requerido": 55,
        "orden": 8,
        "descripcion": "Forja en ruinas, ahora refugio de bandidos.",
        "coord_x": 390,
        "coord_y": 195,
        "materiales_posibles": [
            {"id": "material_26", "rareza": 7, "min": 1, "max": 2, "nivel": 56},
            {"id": "material_55", "rareza": 7, "min": 1, "max": 2, "nivel": 56},
            {"id": "material_17", "rareza": 8, "min": 1, "max": 2, "nivel": 52}
        ],
        "peligrosidad_base": 1.5,
        "nivel_recomendado_min": 55,
        "nivel_recomendado_max": 95,
        "clima": "calor extremo",
        "velocidad_base_kmh": 3,
        "precio_vuelo_rapido": None,
        "servicios": [],
        "icono": "🏭",
        "enemigo_faccion_comun": 3,
        "conectado_a": [],
        "monstruos": {
            "normales": [
                {"nombre": "Esbirro del Fuego", "lore": "Diablillo armado con un martillo.", "clase": "vanguardista"},
                {"nombre": "Lava Lenta", "lore": "Gelatina de lava que ralentiza.", "clase": "tejehechizos"}
            ],
            "mini_boss": [
                {"nombre": "Forjador de Almas", "lore": "Demonio que crea golems.", "clase": "maestro_caza"}
            ],
            "jefes_zona_normal": [],
            "jefes_zona_dificil": [],
            "mazmorras_normal": [
                {"nombre": "Esbirro del Fuego", "lore": "Diablillo martillo.", "clase": "vanguardista"},
                {"nombre": "Lava Lenta", "lore": "Gelatina.", "clase": "tejehechizos"},
                {"nombre": "Golem de Ceniza", "lore": "Gólem.", "clase": "acechante"},
                {"nombre": "Elemental de Humo", "lore": "Nube tóxica.", "clase": "tejehechizos"},
                {"nombre": "Centinela de Fuego", "lore": "Soldado.", "clase": "vanguardista"},
                {"nombre": "JEFE: Forjador de Almas", "lore": "Demonio forjador.", "clase": "maestro_caza"}
            ],
            "mazmorras_dificil": [
                {"nombre": "Guardia Infernal", "lore": "Guerrero ardiente.", "clase": "vanguardista"},
                {"nombre": "Titan de Cenizas", "lore": "Gigante.", "clase": "vanguardista"},
                {"nombre": "Señor de las Llamas", "lore": "Comandante.", "clase": "vanguardista"},
                {"nombre": "Demonio de las Cadenas", "lore": "Esbirro.", "clase": "acechante"},
                {"nombre": "Avatar del Fuego", "lore": "Dios.", "clase": "tejehechizos"},
                {"nombre": "JEFE: Forjador Supremo", "lore": "Demonio maestro.", "clase": "vanguardista"}
            ]
        }
    },

    # ==================== ZONAS ROJAS (Sindicato) ====================
    # Tierras Magmáticas Sindicato (id 28)
    {
        "id": 28,
        "nombre": "Tierras Magmáticas Sindicato",
        "color": "roja",
        "tipo": "salvaje",
        "faccion_id": 3,
        "nivel_requerido": 45,
        "orden": 6,
        "descripcion": "Zona volcánica donde el sindicato extrae minerales.",
        "coord_x": 580,
        "coord_y": 290,
        "materiales_posibles": [
            {"id": "material_115", "rareza": 7, "min": 1, "max": 2, "nivel": 47},
            {"id": "material_137", "rareza": 7, "min": 1, "max": 2, "nivel": 46},
            {"id": "material_11", "rareza": 8, "min": 1, "max": 2, "nivel": 42}
        ],
        "peligrosidad_base": 1.5,
        "nivel_recomendado_min": 45,
        "nivel_recomendado_max": 85,
        "clima": "calor extremo",
        "velocidad_base_kmh": 3,
        "precio_vuelo_rapido": None,
        "servicios": [],
        "icono": "🌋",
        "enemigo_faccion_comun": 1,
        "conectado_a": [],
        "monstruos": {
            "normales": [
                {"nombre": "Minero Esclavo", "lore": "Humanoide deformado por el calor.", "clase": "vanguardista"},
                {"nombre": "Perro de Fuego", "lore": "Can que escupe bolas de fuego.", "clase": "maestro_caza"}
            ],
            "mini_boss": [
                {"nombre": "Supervisor de la Mina", "lore": "Demonio con látigo de lava.", "clase": "acechante"}
            ],
            "jefes_zona_normal": [],
            "jefes_zona_dificil": [],
            "mazmorras_normal": [
                {"nombre": "Minero Esclavo", "lore": "Humanoide.", "clase": "vanguardista"},
                {"nombre": "Perro de Fuego", "lore": "Can.", "clase": "maestro_caza"},
                {"nombre": "Diablillo Obrero", "lore": "Demonio menor.", "clase": "acechante"},
                {"nombre": "Golem de Carbón", "lore": "Gólem negro.", "clase": "vanguardista"},
                {"nombre": "Elemental de Azufre", "lore": "Gas venenoso.", "clase": "tejehechizos"},
                {"nombre": "JEFE: Supervisor de la Mina", "lore": "Demonio látigo.", "clase": "acechante"}
            ],
            "mazmorras_dificil": [
                {"nombre": "Capataz Infernal", "lore": "Supervisor jefe.", "clase": "vanguardista"},
                {"nombre": "Titan de Escoria", "lore": "Gigante.", "clase": "vanguardista"},
                {"nombre": "Dragón de Mineral", "lore": "Criatura metálica.", "clase": "maestro_caza"},
                {"nombre": "Avatar de la Mina", "lore": "Dios menor.", "clase": "tejehechizos"},
                {"nombre": "Forjador Oscuro", "lore": "Demonio.", "clase": "acechante"},
                {"nombre": "JEFE: Rey de la Forja", "lore": "Señor de la mina.", "clase": "vanguardista"}
            ]
        }
    },
    # Cima del Dragón Sindicato (id 29)
    {
        "id": 29,
        "nombre": "Cima del Dragón Sindicato",
        "color": "roja",
        "tipo": "salvaje",
        "faccion_id": 3,
        "nivel_requerido": 50,
        "orden": 7,
        "descripcion": "Cima usada como escondite del sindicato.",
        "coord_x": 590,
        "coord_y": 295,
        "materiales_posibles": [
            {"id": "material_115", "rareza": 7, "min": 1, "max": 2, "nivel": 47},
            {"id": "material_137", "rareza": 7, "min": 1, "max": 2, "nivel": 46},
            {"id": "material_17", "rareza": 8, "min": 1, "max": 2, "nivel": 52}
        ],
        "peligrosidad_base": 1.5,
        "nivel_recomendado_min": 50,
        "nivel_recomendado_max": 90,
        "clima": "calor extremo",
        "velocidad_base_kmh": 3,
        "precio_vuelo_rapido": None,
        "servicios": [],
        "icono": "🐉",
        "enemigo_faccion_comun": 1,
        "conectado_a": [],
        "monstruos": {
            "normales": [
                {"nombre": "Ladrón de Dragones", "lore": "Pícaro que roba huevos de dragón.", "clase": "acechante"},
                {"nombre": "Elemental de Aire Caliente", "lore": "Torbellino de ceniza.", "clase": "tejehechizos"}
            ],
            "mini_boss": [
                {"nombre": "Jefe de la Banda", "lore": "Líder de los ladrones.", "clase": "acechante"}
            ],
            "jefes_zona_normal": [],
            "jefes_zona_dificil": [],
            "mazmorras_normal": [
                {"nombre": "Ladrón de Dragones", "lore": "Pícaro.", "clase": "acechante"},
                {"nombre": "Elemental de Aire Caliente", "lore": "Torbellino.", "clase": "tejehechizos"},
                {"nombre": "Cazador de Huevos", "lore": "Merodeador.", "clase": "maestro_caza"},
                {"nombre": "Gusano de Lava", "lore": "Criatura.", "clase": "acechante"},
                {"nombre": "Salamandra Ígnea", "lore": "Lagarto.", "clase": "maestro_caza"},
                {"nombre": "JEFE: Jefe de la Banda", "lore": "Líder.", "clase": "acechante"}
            ],
            "mazmorras_dificil": [
                {"nombre": "Señor de los Dragones", "lore": "Rey ladrón.", "clase": "vanguardista"},
                {"nombre": "Matriarca Ígnea", "lore": "Salamandra.", "clase": "vanguardista"},
                {"nombre": "Príncipe del Fuego", "lore": "Demonio.", "clase": "maestro_caza"},
                {"nombre": "Avatar del Volcán", "lore": "Dios.", "clase": "tejehechizos"},
                {"nombre": "Dragón de Magma", "lore": "Bestia.", "clase": "vanguardista"},
                {"nombre": "JEFE: Devorador de Dragones", "lore": "Entidad suprema.", "clase": "vanguardista"}
            ]
        }
    },
    # Forja Abandonada Sindicato (id 30)
    {
        "id": 30,
        "nombre": "Forja Abandonada Sindicato",
        "color": "roja",
        "tipo": "salvaje",
        "faccion_id": 3,
        "nivel_requerido": 55,
        "orden": 8,
        "descripcion": "Forja clandestina del sindicato.",
        "coord_x": 600,
        "coord_y": 300,
        "materiales_posibles": [
            {"id": "material_26", "rareza": 7, "min": 1, "max": 2, "nivel": 56},
            {"id": "material_55", "rareza": 7, "min": 1, "max": 2, "nivel": 56},
            {"id": "material_17", "rareza": 8, "min": 1, "max": 2, "nivel": 52}
        ],
        "peligrosidad_base": 1.5,
        "nivel_recomendado_min": 55,
        "nivel_recomendado_max": 95,
        "clima": "calor extremo",
        "velocidad_base_kmh": 3,
        "precio_vuelo_rapido": None,
        "servicios": [],
        "icono": "🏭",
        "enemigo_faccion_comun": 1,
        "conectado_a": [],
        "monstruos": {
            "normales": [
                {"nombre": "Mercenario de Fuego", "lore": "Soldado a sueldo con lanzallamas.", "clase": "maestro_caza"},
                {"nombre": "Trampa Viviente", "lore": "Mecanismo que lanza cuchillas.", "clase": "acechante"}
            ],
            "mini_boss": [
                {"nombre": "Armero del Sindicato", "lore": "Enano loco que crea armas.", "clase": "tejehechizos"}
            ],
            "jefes_zona_normal": [],
            "jefes_zona_dificil": [],
            "mazmorras_normal": [
                {"nombre": "Mercenario de Fuego", "lore": "Soldado.", "clase": "maestro_caza"},
                {"nombre": "Trampa Viviente", "lore": "Mecanismo.", "clase": "acechante"},
                {"nombre": "Diablillo Mecánico", "lore": "Robot.", "clase": "maestro_caza"},
                {"nombre": "Golem de Acero", "lore": "Autómata.", "clase": "vanguardista"},
                {"nombre": "Elemental de Aceite", "lore": "Gelatina.", "clase": "tejehechizos"},
                {"nombre": "JEFE: Armero del Sindicato", "lore": "Enano loco.", "clase": "tejehechizos"}
            ],
            "mazmorras_dificil": [
                {"nombre": "Maestro de la Forja", "lore": "Armero jefe.", "clase": "vanguardista"},
                {"nombre": "Titan de Metal", "lore": "Gigante.", "clase": "vanguardista"},
                {"nombre": "Demonio de las Cadenas", "lore": "Esbirro.", "clase": "acechante"},
                {"nombre": "Avatar de la Fundición", "lore": "Dios.", "clase": "tejehechizos"},
                {"nombre": "Dragón de Hierro", "lore": "Bestia mecánica.", "clase": "maestro_caza"},
                {"nombre": "JEFE: Rey de la Forja", "lore": "Señor del sindicato.", "clase": "vanguardista"}
            ]
        }
    },

    # ==================== ZONAS NEGRAS (Alianza) ====================
    # Abismo Alianza (id 9)
    {
        "id": 9,
        "nombre": "Abismo Alianza",
        "color": "negra",
        "tipo": "salvaje",
        "faccion_id": 1,
        "nivel_requerido": 70,
        "orden": 9,
        "descripcion": "Fisura en la tierra que conecta con el vacío.",
        "coord_x": 190,
        "coord_y": 95,
        "materiales_posibles": [
            {"id": "material_127", "rareza": 10, "min": 1, "max": 2, "nivel": 73}
        ],
        "peligrosidad_base": 2.0,
        "nivel_recomendado_min": 70,
        "nivel_recomendado_max": 120,
        "clima": "oscuridad",
        "velocidad_base_kmh": 2,
        "precio_vuelo_rapido": None,
        "servicios": [],
        "icono": "🌑",
        "enemigo_faccion_comun": 2,
        "conectado_a": [],
        "monstruos": {
            "normales": [
                {"nombre": "Sombrío", "lore": "Criatura de sombra intangible.", "clase": "acechante"},
                {"nombre": "No-muerto Rasgador", "lore": "Cadáver con garras afiladas.", "clase": "vanguardista"}
            ],
            "mini_boss": [
                {"nombre": "Vampiro de la Sombra", "lore": "No-muerto que se oculta en la oscuridad.", "clase": "acechante"}
            ],
            "jefes_zona_normal": [{"nombre": "Señor de la Noche", "lore": "Antiguo rey vampiro.", "clase": "vanguardista"}],
            "jefes_zona_dificil": [{"nombre": "El Devorador de Almas", "lore": "Entidad cósmica.", "clase": "vanguardista"}],
            "mazmorras_normal": [
                {"nombre": "Sombrío", "lore": "Sombra.", "clase": "acechante"},
                {"nombre": "No-muerto Rasgador", "lore": "Cadáver.", "clase": "vanguardista"},
                {"nombre": "Aparición Susurrante", "lore": "Espectro.", "clase": "tejehechizos"},
                {"nombre": "Carroñero de Huesos", "lore": "Ensamblaje.", "clase": "vanguardista"},
                {"nombre": "Ojo que Todo lo Ve", "lore": "Esfera.", "clase": "tejehechizos"},
                {"nombre": "JEFE: Señor de la Noche", "lore": "Rey vampiro.", "clase": "maestro_caza"}
            ],
            "mazmorras_dificil": [
                {"nombre": "Vampiro de la Sombra", "lore": "No-muerto.", "clase": "acechante"},
                {"nombre": "Liche Oscuro", "lore": "Nigromante.", "clase": "tejehechizos"},
                {"nombre": "Devorador de Almas", "lore": "Entidad.", "clase": "tejehechizos"},
                {"nombre": "Espíritu del Caos", "lore": "Cambiante.", "clase": "maestro_caza"},
                {"nombre": "Avatar de la Nada", "lore": "Dios.", "clase": "tejehechizos"},
                {"nombre": "JEFE: Dios del Abismo", "lore": "Ser cósmico.", "clase": "vanguardista"}
            ]
        }
    },
    # Costa de los Lamentos Alianza (id 10)
    {
        "id": 10,
        "nombre": "Costa de los Lamentos Alianza",
        "color": "negra",
        "tipo": "salvaje",
        "faccion_id": 1,
        "nivel_requerido": 75,
        "orden": 10,
        "descripcion": "Costa rocosa bañada por aguas negras.",
        "coord_x": 200,
        "coord_y": 100,
        "materiales_posibles": [
            {"id": "material_109", "rareza": 10, "min": 1, "max": 2, "nivel": 77}
        ],
        "peligrosidad_base": 2.0,
        "nivel_recomendado_min": 75,
        "nivel_recomendado_max": 125,
        "clima": "oscuridad",
        "velocidad_base_kmh": 2,
        "precio_vuelo_rapido": None,
        "servicios": [],
        "icono": "🌊",
        "enemigo_faccion_comun": 2,
        "conectado_a": [],
        "monstruos": {
            "normales": [
                {"nombre": "Aparición Susurrante", "lore": "Espectro que reduce la cordura.", "clase": "tejehechizos"},
                {"nombre": "Carroñero de Huesos", "lore": "Ensamblaje de restos óseos.", "clase": "vanguardista"}
            ],
            "mini_boss": [
                {"nombre": "Liche Oscuro", "lore": "Nigromante poderoso.", "clase": "tejehechizos"}
            ],
            "jefes_zona_normal": [],
            "jefes_zona_dificil": [],
            "mazmorras_normal": [
                {"nombre": "Aparición Susurrante", "lore": "Espectro.", "clase": "tejehechizos"},
                {"nombre": "Carroñero de Huesos", "lore": "Huesos.", "clase": "vanguardista"},
                {"nombre": "Marinero Fantasma", "lore": "Alma.", "clase": "acechante"},
                {"nombre": "Cangrejo Gigante", "lore": "Pinzas.", "clase": "vanguardista"},
                {"nombre": "Sirena Maldita", "lore": "Canto.", "clase": "maestro_caza"},
                {"nombre": "JEFE: Liche Oscuro", "lore": "Nigromante.", "clase": "tejehechizos"}
            ],
            "mazmorras_dificil": [
                {"nombre": "Capitán del Holandés", "lore": "Espectro.", "clase": "vanguardista"},
                {"nombre": "Leviatán Negro", "lore": "Bestia.", "clase": "vanguardista"},
                {"nombre": "Bruja de los Mares", "lore": "Hechicera.", "clase": "tejehechizos"},
                {"nombre": "Avatar del Océano", "lore": "Dios.", "clase": "tejehechizos"},
                {"nombre": "Dragón Marino", "lore": "Criatura.", "clase": "maestro_caza"},
                {"nombre": "JEFE: Rey de los Lamentos", "lore": "Señor del abismo.", "clase": "vanguardista"}
            ]
        }
    },
    # Nexo de la Nada Alianza (id 11)
    {
        "id": 11,
        "nombre": "Nexo de la Nada Alianza",
        "color": "negra",
        "tipo": "salvaje",
        "faccion_id": 1,
        "nivel_requerido": 80,
        "orden": 11,
        "descripcion": "Punto donde confluyen dimensiones.",
        "coord_x": 210,
        "coord_y": 105,
        "materiales_posibles": [
            {"id": "material_102", "rareza": 10, "min": 1, "max": 2, "nivel": 82}
        ],
        "peligrosidad_base": 2.0,
        "nivel_recomendado_min": 80,
        "nivel_recomendado_max": 130,
        "clima": "oscuridad",
        "velocidad_base_kmh": 2,
        "precio_vuelo_rapido": None,
        "servicios": [],
        "icono": "🌀",
        "enemigo_faccion_comun": 2,
        "conectado_a": [],
        "monstruos": {
            "normales": [
                {"nombre": "Ojo que Todo lo Ve", "lore": "Esfera flotante que lanza rayos.", "clase": "tejehechizos"},
                {"nombre": "Portador del Vacío", "lore": "Engendro dimensional.", "clase": "vanguardista"}
            ],
            "mini_boss": [
                {"nombre": "Devorador de Almas", "lore": "Entidad que absorbe atributos.", "clase": "tejehechizos"}
            ],
            "jefes_zona_normal": [{"nombre": "Dios del Abismo", "lore": "Ser cósmico que manipula la realidad.", "clase": "vanguardista"}],
            "jefes_zona_dificil": [],
            "mazmorras_normal": [
                {"nombre": "Ojo que Todo lo Ve", "lore": "Esfera.", "clase": "tejehechizos"},
                {"nombre": "Portador del Vacío", "lore": "Engendro.", "clase": "vanguardista"},
                {"nombre": "Sirviente del Vacío", "lore": "Humanoide.", "clase": "acechante"},
                {"nombre": "Golem de Sombra", "lore": "Autómata oscuro.", "clase": "vanguardista"},
                {"nombre": "Espectro Dimensional", "lore": "Fantasma.", "clase": "tejehechizos"},
                {"nombre": "JEFE: Devorador de Almas", "lore": "Entidad.", "clase": "tejehechizos"}
            ],
            "mazmorras_dificil": [
                {"nombre": "Dios del Abismo", "lore": "Ser cósmico.", "clase": "vanguardista"},
                {"nombre": "Avatar de la Nada", "lore": "Manifestación.", "clase": "tejehechizos"},
                {"nombre": "Dragón del Vacío", "lore": "Criatura.", "clase": "maestro_caza"},
                {"nombre": "Emperador de las Sombras", "lore": "Rey.", "clase": "vanguardista"},
                {"nombre": "Aniquilador", "lore": "Entidad.", "clase": "tejehechizos"},
                {"nombre": "JEFE: El Primigenio", "lore": "Dios supremo.", "clase": "vanguardista"}
            ]
        }
    },

    # ==================== ZONAS NEGRAS (Imperio) ====================
    # Abismo Imperio (id 20)
    {
        "id": 20,
        "nombre": "Abismo Imperio",
        "color": "negra",
        "tipo": "salvaje",
        "faccion_id": 2,
        "nivel_requerido": 70,
        "orden": 9,
        "descripcion": "Abismo vigilado por el imperio.",
        "coord_x": 400,
        "coord_y": 200,
        "materiales_posibles": [
            {"id": "material_127", "rareza": 10, "min": 1, "max": 2, "nivel": 73}
        ],
        "peligrosidad_base": 2.0,
        "nivel_recomendado_min": 70,
        "nivel_recomendado_max": 120,
        "clima": "oscuridad",
        "velocidad_base_kmh": 2,
        "precio_vuelo_rapido": None,
        "servicios": [],
        "icono": "🌑",
        "enemigo_faccion_comun": 3,
        "conectado_a": [],
        "monstruos": {
            "normales": [
                {"nombre": "Centinela No-muerto", "lore": "Soldado imperial reanimado.", "clase": "vanguardista"}
            ],
            "mini_boss": [
                {"nombre": "Capitán de la Guardia", "lore": "Oficial con armadura negra.", "clase": "vanguardista"}
            ],
            "jefes_zona_normal": [],
            "jefes_zona_dificil": [],
            "mazmorras_normal": [
                {"nombre": "Centinela No-muerto", "lore": "Soldado.", "clase": "vanguardista"},
                {"nombre": "Esqueleto Legionario", "lore": "Esqueleto.", "clase": "vanguardista"},
                {"nombre": "Espectro Imperial", "lore": "Fantasma.", "clase": "tejehechizos"},
                {"nombre": "Gárgola de Obsidiana", "lore": "Estatua.", "clase": "acechante"},
                {"nombre": "Liche Menor", "lore": "Nigromante.", "clase": "tejehechizos"},
                {"nombre": "JEFE: Capitán de la Guardia", "lore": "Oficial.", "clase": "vanguardista"}
            ],
            "mazmorras_dificil": [
                {"nombre": "General No-muerto", "lore": "Comandante.", "clase": "vanguardista"},
                {"nombre": "Vampiro Imperial", "lore": "No-muerto.", "clase": "acechante"},
                {"nombre": "Titan de Hueso", "lore": "Gigante.", "clase": "vanguardista"},
                {"nombre": "Avatar del Imperio", "lore": "Dios.", "clase": "tejehechizos"},
                {"nombre": "Dragón de Hueso", "lore": "Bestia.", "clase": "maestro_caza"},
                {"nombre": "JEFE: Emperador No-muerto", "lore": "Rey.", "clase": "vanguardista"}
            ]
        }
    },
    # Costa de los Lamentos Imperio (id 21)
    {
        "id": 21,
        "nombre": "Costa de los Lamentos Imperio",
        "color": "negra",
        "tipo": "salvaje",
        "faccion_id": 2,
        "nivel_requerido": 75,
        "orden": 10,
        "descripcion": "Costa donde naufragan barcos imperiales.",
        "coord_x": 410,
        "coord_y": 205,
        "materiales_posibles": [
            {"id": "material_109", "rareza": 10, "min": 1, "max": 2, "nivel": 77}
        ],
        "peligrosidad_base": 2.0,
        "nivel_recomendado_min": 75,
        "nivel_recomendado_max": 125,
        "clima": "oscuridad",
        "velocidad_base_kmh": 2,
        "precio_vuelo_rapido": None,
        "servicios": [],
        "icono": "🌊",
        "enemigo_faccion_comun": 3,
        "conectado_a": [],
        "monstruos": {
            "normales": [
                {"nombre": "Marinero Fantasma", "lore": "Alma de un naufrago.", "clase": "acechante"}
            ],
            "mini_boss": [
                {"nombre": "Capitán del Holandés", "lore": "Espectro con un ancla oxidada.", "clase": "vanguardista"}
            ],
            "jefes_zona_normal": [],
            "jefes_zona_dificil": [],
            "mazmorras_normal": [
                {"nombre": "Marinero Fantasma", "lore": "Alma.", "clase": "acechante"},
                {"nombre": "Cangrejo Gigante", "lore": "Pinzas.", "clase": "vanguardista"},
                {"nombre": "Sirena Imperial", "lore": "Canto.", "clase": "maestro_caza"},
                {"nombre": "Esqueleto de Buceador", "lore": "Huesos.", "clase": "acechante"},
                {"nombre": "Elemental de Agua Negra", "lore": "Gólem.", "clase": "tejehechizos"},
                {"nombre": "JEFE: Capitán del Holandés", "lore": "Espectro.", "clase": "vanguardista"}
            ],
            "mazmorras_dificil": [
                {"nombre": "Almirante Fantasma", "lore": "Comandante.", "clase": "vanguardista"},
                {"nombre": "Leviatán Imperial", "lore": "Bestia.", "clase": "vanguardista"},
                {"nombre": "Bruja de la Costa", "lore": "Hechicera.", "clase": "tejehechizos"},
                {"nombre": "Avatar del Mar", "lore": "Dios.", "clase": "tejehechizos"},
                {"nombre": "Dragón Marino", "lore": "Criatura.", "clase": "maestro_caza"},
                {"nombre": "JEFE: Emperador de las Olas", "lore": "Rey.", "clase": "vanguardista"}
            ]
        }
    },
    # Nexo de la Nada Imperio (id 22)
    {
        "id": 22,
        "nombre": "Nexo de la Nada Imperio",
        "color": "negra",
        "tipo": "salvaje",
        "faccion_id": 2,
        "nivel_requerido": 80,
        "orden": 11,
        "descripcion": "Portal al vacío descubierto por el imperio.",
        "coord_x": 420,
        "coord_y": 210,
        "materiales_posibles": [
            {"id": "material_102", "rareza": 10, "min": 1, "max": 2, "nivel": 82}
        ],
        "peligrosidad_base": 2.0,
        "nivel_recomendado_min": 80,
        "nivel_recomendado_max": 130,
        "clima": "oscuridad",
        "velocidad_base_kmh": 2,
        "precio_vuelo_rapido": None,
        "servicios": [],
        "icono": "🌀",
        "enemigo_faccion_comun": 3,
        "conectado_a": [],
        "monstruos": {
            "normales": [
                {"nombre": "Sirviente del Vacío", "lore": "Humanoide deforme.", "clase": "vanguardista"}
            ],
            "mini_boss": [
                {"nombre": "Orador del Abismo", "lore": "Sacerdote que invoca sombras.", "clase": "tejehechizos"}
            ],
            "jefes_zona_normal": [],
            "jefes_zona_dificil": [],
            "mazmorras_normal": [
                {"nombre": "Sirviente del Vacío", "lore": "Humanoide.", "clase": "vanguardista"},
                {"nombre": "Portador del Vacío", "lore": "Engendro.", "clase": "acechante"},
                {"nombre": "Ojo que Todo lo Ve", "lore": "Esfera.", "clase": "tejehechizos"},
                {"nombre": "Golem de Sombra", "lore": "Autómata.", "clase": "vanguardista"},
                {"nombre": "Espectro Dimensional", "lore": "Fantasma.", "clase": "tejehechizos"},
                {"nombre": "JEFE: Orador del Abismo", "lore": "Sacerdote.", "clase": "tejehechizos"}
            ],
            "mazmorras_dificil": [
                {"nombre": "Sumo Sacerdote", "lore": "Clérigo.", "clase": "tejehechizos"},
                {"nombre": "Avatar del Vacío", "lore": "Dios.", "clase": "tejehechizos"},
                {"nombre": "Dragón del Nexo", "lore": "Criatura.", "clase": "maestro_caza"},
                {"nombre": "Emperador de la Nada", "lore": "Rey.", "clase": "vanguardista"},
                {"nombre": "Aniquilador", "lore": "Entidad.", "clase": "vanguardista"},
                {"nombre": "JEFE: El Primigenio Imperial", "lore": "Dios supremo.", "clase": "vanguardista"}
            ]
        }
    },

    # ==================== ZONAS NEGRAS (Sindicato) ====================
    # Abismo Sindicato (id 31)
    {
        "id": 31,
        "nombre": "Abismo Sindicato",
        "color": "negra",
        "tipo": "salvaje",
        "faccion_id": 3,
        "nivel_requerido": 70,
        "orden": 9,
        "descripcion": "Abismo usado como escondite del sindicato.",
        "coord_x": 610,
        "coord_y": 305,
        "materiales_posibles": [
            {"id": "material_127", "rareza": 10, "min": 1, "max": 2, "nivel": 73}
        ],
        "peligrosidad_base": 2.0,
        "nivel_recomendado_min": 70,
        "nivel_recomendado_max": 120,
        "clima": "oscuridad",
        "velocidad_base_kmh": 2,
        "precio_vuelo_rapido": None,
        "servicios": [],
        "icono": "🌑",
        "enemigo_faccion_comun": 1,
        "conectado_a": [],
        "monstruos": {
            "normales": [
                {"nombre": "Espía Sombra", "lore": "Agente invisible.", "clase": "acechante"}
            ],
            "mini_boss": [
                {"nombre": "Mercenario del Vacío", "lore": "Luchador contratado.", "clase": "vanguardista"}
            ],
            "jefes_zona_normal": [],
            "jefes_zona_dificil": [],
            "mazmorras_normal": [
                {"nombre": "Espía Sombra", "lore": "Agente.", "clase": "acechante"},
                {"nombre": "Asesino Nocturno", "lore": "Sicario.", "clase": "acechante"},
                {"nombre": "Espectro del Sindicato", "lore": "Fantasma.", "clase": "tejehechizos"},
                {"nombre": "Gárgola de Piedra", "lore": "Estatua.", "clase": "vanguardista"},
                {"nombre": "Elemental de Sombra", "lore": "Gólem.", "clase": "tejehechizos"},
                {"nombre": "JEFE: Mercenario del Vacío", "lore": "Luchador.", "clase": "vanguardista"}
            ],
            "mazmorras_dificil": [
                {"nombre": "Jefe de la Sombra", "lore": "Líder.", "clase": "acechante"},
                {"nombre": "Avatar del Vacío", "lore": "Dios.", "clase": "tejehechizos"},
                {"nombre": "Dragón de Sombra", "lore": "Criatura.", "clase": "maestro_caza"},
                {"nombre": "Emperador de las Sombras", "lore": "Rey.", "clase": "vanguardista"},
                {"nombre": "Aniquilador", "lore": "Entidad.", "clase": "vanguardista"},
                {"nombre": "JEFE: El Primigenio del Sindicato", "lore": "Dios supremo.", "clase": "vanguardista"}
            ]
        }
    },
    # Costa de los Lamentos Sindicato (id 32)
    {
        "id": 32,
        "nombre": "Costa de los Lamentos Sindicato",
        "color": "negra",
        "tipo": "salvaje",
        "faccion_id": 3,
        "nivel_requerido": 75,
        "orden": 10,
        "descripcion": "Costa utilizada para tráfico ilegal.",
        "coord_x": 620,
        "coord_y": 310,
        "materiales_posibles": [
            {"id": "material_109", "rareza": 10, "min": 1, "max": 2, "nivel": 77}
        ],
        "peligrosidad_base": 2.0,
        "nivel_recomendado_min": 75,
        "nivel_recomendado_max": 125,
        "clima": "oscuridad",
        "velocidad_base_kmh": 2,
        "precio_vuelo_rapido": None,
        "servicios": [],
        "icono": "🌊",
        "enemigo_faccion_comun": 1,
        "conectado_a": [],
        "monstruos": {
            "normales": [
                {"nombre": "Contrabandista", "lore": "Ladrón con un gancho.", "clase": "acechante"}
            ],
            "mini_boss": [
                {"nombre": "Reina de la Costa", "lore": "Pirata con una espada maldita.", "clase": "vanguardista"}
            ],
            "jefes_zona_normal": [],
            "jefes_zona_dificil": [],
            "mazmorras_normal": [
                {"nombre": "Contrabandista", "lore": "Ladrón.", "clase": "acechante"},
                {"nombre": "Marinero Borracho", "lore": "Ebrio.", "clase": "vanguardista"},
                {"nombre": "Sirena Pirata", "lore": "Canto.", "clase": "maestro_caza"},
                {"nombre": "Cangrejo Asesino", "lore": "Pinzas.", "clase": "vanguardista"},
                {"nombre": "Elemental de Sal", "lore": "Gólem.", "clase": "tejehechizos"},
                {"nombre": "JEFE: Reina de la Costa", "lore": "Pirata.", "clase": "vanguardista"}
            ],
            "mazmorras_dificil": [
                {"nombre": "Almirante Pirata", "lore": "Comandante.", "clase": "vanguardista"},
                {"nombre": "Leviatán del Sindicato", "lore": "Bestia.", "clase": "vanguardista"},
                {"nombre": "Bruja de la Costa", "lore": "Hechicera.", "clase": "tejehechizos"},
                {"nombre": "Avatar del Mar Negro", "lore": "Dios.", "clase": "tejehechizos"},
                {"nombre": "Dragón Marino", "lore": "Criatura.", "clase": "maestro_caza"},
                {"nombre": "JEFE: Rey de los Contrabandistas", "lore": "Rey.", "clase": "vanguardista"}
            ]
        }
    },
    # Nexo de la Nada Sindicato (id 33)
    {
        "id": 33,
        "nombre": "Nexo de la Nada Sindicato",
        "color": "negra",
        "tipo": "salvaje",
        "faccion_id": 3,
        "nivel_requerido": 80,
        "orden": 11,
        "descripcion": "Nexo controlado por el sindicato.",
        "coord_x": 630,
        "coord_y": 315,
        "materiales_posibles": [
            {"id": "material_102", "rareza": 10, "min": 1, "max": 2, "nivel": 82}
        ],
        "peligrosidad_base": 2.0,
        "nivel_recomendado_min": 80,
        "nivel_recomendado_max": 130,
        "clima": "oscuridad",
        "velocidad_base_kmh": 2,
        "precio_vuelo_rapido": None,
        "servicios": [],
        "icono": "🌀",
        "enemigo_faccion_comun": 1,
        "conectado_a": [],
        "monstruos": {
            "normales": [
                {"nombre": "Científico Loco", "lore": "Experimentos con el vacío.", "clase": "tejehechizos"}
            ],
            "mini_boss": [
                {"nombre": "Primera Creación", "lore": "Golem imperfecto.", "clase": "vanguardista"}
            ],
            "jefes_zona_normal": [],
            "jefes_zona_dificil": [],
            "mazmorras_normal": [
                {"nombre": "Científico Loco", "lore": "Loco.", "clase": "tejehechizos"},
                {"nombre": "Robot Experimental", "lore": "Máquina.", "clase": "maestro_caza"},
                {"nombre": "Mutante de Laboratorio", "lore": "Criatura.", "clase": "vanguardista"},
                {"nombre": "Golem de Cristal", "lore": "Autómata.", "clase": "vanguardista"},
                {"nombre": "Espectro de Prueba", "lore": "Fantasma.", "clase": "tejehechizos"},
                {"nombre": "JEFE: Primera Creación", "lore": "Golem.", "clase": "vanguardista"}
            ],
            "mazmorras_dificil": [
                {"nombre": "Creador Supremo", "lore": "Genio.", "clase": "tejehechizos"},
                {"nombre": "Avatar de la Ciencia", "lore": "Dios.", "clase": "tejehechizos"},
                {"nombre": "Dragón Mecánico", "lore": "Bestia.", "clase": "maestro_caza"},
                {"nombre": "Emperador del Nexo", "lore": "Rey.", "clase": "vanguardista"},
                {"nombre": "Aniquilador", "lore": "Entidad.", "clase": "vanguardista"},
                {"nombre": "JEFE: El Primigenio del Nexo", "lore": "Dios supremo.", "clase": "vanguardista"}
            ]
        }
    }
]
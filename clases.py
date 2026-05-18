#!/usr/bin/env python3
# clases.py
# Definición de las 4 clases, estadísticas, habilidades, subclases, afinidades y fórmulas de crecimiento.

# ==================== DATOS ESTÁTICOS DE LAS CLASES ====================
CLASES = {
    "vanguardista": {
        "nombre": "🛡️ Vanguardista",
        "emoji": "🛡️",
        "descripcion": "Tanque de primera línea. Alta defensa y vida."
    },
    "acechante": {
        "nombre": "🗡️ Acechante",
        "emoji": "🗡️",
        "descripcion": "Asesino sigiloso. Daño crítico y movilidad."
    },
    "tejehechizos": {
        "nombre": "🔮 Tejehechizos",
        "emoji": "🔮",
        "descripcion": "Mago versátil. Daño mágico y curación."
    },
    "maestro_caza": {
        "nombre": "🏹 Maestro de Caza",
        "emoji": "🏹",
        "descripcion": "Arquero preciso. Daño a distancia y control."
    }
}

# ==================== ESTADÍSTICAS BASE (nivel 1) ====================
STATS_BASE = {
    "vanguardista": {
        "vida_max": 140,
        "daño_base": 12,
        "defensa_base": 14,
        "carga_base": 60
    },
    "acechante": {
        "vida_max": 90,
        "daño_base": 20,
        "defensa_base": 5,
        "carga_base": 40
    },
    "tejehechizos": {
        "vida_max": 80,
        "daño_base": 18,
        "defensa_base": 4,
        "carga_base": 35
    },
    "maestro_caza": {
        "vida_max": 100,
        "daño_base": 16,
        "defensa_base": 7,
        "carga_base": 45
    }
}

# ==================== HABILIDADES ACTIVAS ====================
HABILIDADES_ACTIVAS = {
    "vanguardista": [
        {
            "nombre": "Golpe Escudo",
            "daño": 22,
            "efecto": "aturdimiento brevemente",
            "cooldown": 2,
            "descripcion": "Golpea con el escudo causando daño moderado y aturdiendo al enemigo 1 turno."
        },
        {
            "nombre": "Muro de Hierro",
            "cura": 25,
            "defensa_extra": 20,
            "cooldown": 3,
            "descripcion": "Te fortaleces: recuperas 25 de vida y aumentas tu resistencia."
        }
    ],
    "acechante": [
        {
            "nombre": "Golpe Crítico",
            "daño": 42,
            "efecto": "ignora defensa parcialmente",
            "cooldown": 2,
            "descripcion": "Ataque preciso que causa alto daño e ignora el 30% de defensa del enemigo."
        },
        {
            "nombre": "Golpe en la Sombra",
            "daño": 30,
            "evasion": 50,
            "cooldown": 3,
            "descripcion": "Desapareces entre las sombras y contraatacas causando 30 de daño."
        }
    ],
    "tejehechizos": [
        {
            "nombre": "Rayo Arcano",
            "daño": 32,
            "efecto": "mágico",
            "cooldown": 2,
            "descripcion": "Lanza un rayo de energía mágica que causa daño considerable."
        },
        {
            "nombre": "Bendición Curativa",
            "cura": 35,
            "cooldown": 3,
            "descripcion": "Restaura 35 puntos de vida a ti o a un aliado."
        }
    ],
    "maestro_caza": [
        {
            "nombre": "Flecha Perforante",
            "daño": 34,
            "efecto": "ignora defensa",
            "cooldown": 2,
            "descripcion": "Dispara una flecha que atraviesa la defensa enemiga."
        },
        {
            "nombre": "Trampa de Raíces",
            "daño": 20,
            "aturde": 1,
            "cooldown": 3,
            "descripcion": "Lanza una trampa que enreda al enemigo, causando 20 de daño."
        }
    ]
}

# ==================== HABILIDADES PASIVAS ====================
HABILIDADES_PASIVAS = {
    "vanguardista": {
        "nombre": "Escolta",
        "efecto": "aumenta capacidad de carga en +50%",
        "descripcion": "Puedes llevar un 50% más de peso sin penalización."
    },
    "acechante": {
        "nombre": "Ojo de Halcón",
        "efecto": "ver inventario enemigo antes del combate",
        "descripcion": "Puedes inspeccionar el inventario de un jugador enemigo antes de atacarlo."
    },
    "tejehechizos": {
        "nombre": "Eficiencia de Refinado",
        "efecto": "15% de probabilidad de no gastar materiales al craftear",
        "descripcion": "Al fabricar objetos, hay un 15% de que los materiales no se consuman."
    },
    "maestro_caza": {
        "nombre": "Rastreador de Sangre",
        "efecto": "aumenta frecuencia de recursos raros en recolección",
        "descripcion": "Encuentras objetos especiales con un 20% más de frecuencia."
    }
}

# ==================== SUBCLASES (para nivel 100+) ====================
SUBCLASES = {
    "vanguardista": [
        {
            "nombre": "Paladín Divino",
            "bono": {"vida": 20, "defensa": 10, "curación_extra": 5},
            "descripcion": "Recibes bonificación de vida y defensa, además de curación pasiva ligera."
        },
        {
            "nombre": "Bárbaro Furioso",
            "bono": {"daño": 15, "vida": 30},
            "descripcion": "Aumenta daño y vida, pero reduce defensa ligeramente."
        }
    ],
    "acechante": [
        {
            "nombre": "Sombra Letal",
            "bono": {"daño": 20, "critico": 10},
            "descripcion": "Mayor daño crítico y posibilidad de asestar golpes dobles."
        },
        {
            "nombre": "Maestro del Sigilo",
            "bono": {"evasion": 15, "velocidad_recogida": 20},
            "descripcion": "Más probabilidad de esquivar y recolectar más rápido."
        }
    ],
    "tejehechizos": [
        {
            "nombre": "Archimago",
            "bono": {"daño_magico": 25, "mana": 50},
            "descripcion": "Los hechizos causan más daño y tienes más energía mágica."
        },
        {
            "nombre": "Clérigo Sanador",
            "bono": {"cura": 20, "defensa_magica": 15},
            "descripcion": "Aumenta curación y resistencia contra magia."
        }
    ],
    "maestro_caza": [
        {
            "nombre": "Acechador de Bestias",
            "bono": {"daño_a_bestias": 30, "velocidad": 10},
            "descripcion": "Mayor daño contra bestias y algo de velocidad extra."
        },
        {
            "nombre": "Explorador Élite",
            "bono": {"alcance": 2, "vision": 1},
            "descripcion": "Mayor rango de ataque y detección temprana de enemigos."
        }
    ]
}

# ==================== TABLA DE AFINIDADES (ventaja entre clases) ====================
AFINIDADES = {
    "vanguardista": {
        "contra": "acechante",
        "multiplicador_daño": 1.4   # Vanguardista hace 40% más daño a Acechante
    },
    "acechante": {
        "contra": "tejehechizos",
        "multiplicador_daño": 1.35
    },
    "tejehechizos": {
        "contra": "maestro_caza",
        "multiplicador_daño": 1.35
    },
    "maestro_caza": {
        "contra": "vanguardista",
        "multiplicador_daño": 1.3
    }
}
# Por defecto, si no hay afinidad, multiplicador = 1.0

# ==================== FÓRMULAS DE CRECIMIENTO ====================
VIDA_POR_NIVEL = 5
DAÑO_POR_NIVEL = 0.5
DEFENSA_POR_NIVEL = 1/3  # 0.333...
CARGA_POR_NIVEL = 2
BONO_REENCARNACION = 0.05  # 5% acumulativo por reencarnación

def _calcular_xp_necesaria(nivel):
    """Retorna experiencia requerida para subir del nivel (nivel) al (nivel+1)."""
    return int(200 * (nivel ** 1.5))

# ==================== FUNCIONES PÚBLICAS ====================

def obtener_stats_iniciales(clase: str) -> dict:
    """Retorna copia de las estadísticas base de la clase."""
    return STATS_BASE.get(clase, STATS_BASE["vanguardista"]).copy()

def obtener_habilidades_activas(clase: str) -> list:
    """Retorna lista de habilidades activas de la clase."""
    return HABILIDADES_ACTIVAS.get(clase, []).copy()

def obtener_habilidades_pasivas(clase: str) -> dict:
    """Retorna la habilidad pasiva de la clase (o un dict vacío si no existe)."""
    return HABILIDADES_PASIVAS.get(clase, {}).copy()

def obtener_subclases(clase: str) -> list:
    """Retorna lista de subclases disponibles para la clase."""
    return SUBCLASES.get(clase, []).copy()

def obtener_ventaja(clase_atacante: str, clase_defensor: str) -> float:
    """Retorna multiplicador de daño por afinidad (1.0 si no hay ventaja)."""
    info = AFINIDADES.get(clase_atacante)
    if info and info["contra"] == clase_defensor:
        return info["multiplicador_daño"]
    return 1.0

def calcular_vida_maxima(clase: str, nivel: int, reencarnaciones: int = 0) -> int:
    base = STATS_BASE[clase]["vida_max"]
    aumento = (nivel - 1) * VIDA_POR_NIVEL
    total = base + aumento
    # Aplicar bono de reencarnación
    multiplicador = 1 + BONO_REENCARNACION * reencarnaciones
    return int(total * multiplicador)

def calcular_daño_base(clase: str, nivel: int, reencarnaciones: int = 0) -> int:
    base = STATS_BASE[clase]["daño_base"]
    aumento = int((nivel - 1) * DAÑO_POR_NIVEL)  # redondeo hacia abajo
    total = base + aumento
    multiplicador = 1 + BONO_REENCARNACION * reencarnaciones
    return int(total * multiplicador)

def calcular_defensa(clase: str, nivel: int, reencarnaciones: int = 0) -> int:
    base = STATS_BASE[clase]["defensa_base"]
    aumento = int((nivel - 1) * DEFENSA_POR_NIVEL)
    total = base + aumento
    multiplicador = 1 + BONO_REENCARNACION * reencarnaciones
    return int(total * multiplicador)

def calcular_carga_maxima(clase: str, nivel: int, reencarnaciones: int = 0) -> int:
    base = STATS_BASE[clase]["carga_base"]
    aumento = (nivel - 1) * CARGA_POR_NIVEL
    total = base + aumento
    multiplicador = 1 + BONO_REENCARNACION * reencarnaciones
    return int(total * multiplicador)

def calcular_experiencia_necesaria(nivel: int) -> int:
    """Retorna la experiencia requerida para el siguiente nivel (del nivel actual al siguiente)."""
    if nivel <= 0:
        return 0
    # XP necesaria del nivel 'nivel' para alcanzar nivel 'nivel+1'
    return _calcular_xp_necesaria(nivel)

def aplicar_bono_reencarnacion(stat_base: int, reencarnaciones: int) -> int:
    """Aplica el bono porcentual de reencarnación a una estadística base."""
    multiplicador = 1 + BONO_REENCARNACION * reencarnaciones
    return int(stat_base * multiplicador)

# ==================== FIN DEL MÓDULO ====================
import random
import math
from typing import Dict, List, Optional

ZONAS = [
    {"id":1,"nombre":"Ciudadela Alianza","color":"azul","tipo":"ciudad","faccion_id":1,"coord_x":110,"coord_y":55,"nivel_requerido":1,"icono":"🏙️","servicios":["banco","mercado","taberna","herrero","encantador"]},
    {"id":12,"nombre":"Ciudadela Imperio","color":"azul","tipo":"ciudad","faccion_id":2,"coord_x":320,"coord_y":160,"nivel_requerido":1,"icono":"🏙️","servicios":["banco","mercado","taberna","herrero","encantador"]},
    {"id":23,"nombre":"Ciudadela Sindicato","color":"azul","tipo":"ciudad","faccion_id":3,"coord_x":530,"coord_y":265,"nivel_requerido":1,"icono":"🏙️","servicios":["banco","mercado","taberna","herrero","encantador"]},
    {"id":2,"nombre":"Bosque Alianza","color":"azul","tipo":"salvaje","faccion_id":1,"coord_x":145,"coord_y":75,"nivel_requerido":1,"icono":"🌲","servicios":[]},
    {"id":3,"nombre":"Llanuras Centrales","color":"azul","tipo":"salvaje","faccion_id":1,"coord_x":170,"coord_y":100,"nivel_requerido":1,"icono":"🌾","servicios":[]},
    {"id":4,"nombre":"Costa Brumosa","color":"azul","tipo":"salvaje","faccion_id":1,"coord_x":80,"coord_y":90,"nivel_requerido":1,"icono":"🌊","servicios":[]},
    {"id":13,"nombre":"Bosque Imperio","color":"azul","tipo":"salvaje","faccion_id":2,"coord_x":355,"coord_y":185,"nivel_requerido":1,"icono":"🌲","servicios":[]},
    {"id":14,"nombre":"Desierto Ardiente","color":"azul","tipo":"salvaje","faccion_id":2,"coord_x":385,"coord_y":155,"nivel_requerido":1,"icono":"🏜️","servicios":[]},
    {"id":24,"nombre":"Cavernas Sindicato","color":"azul","tipo":"salvaje","faccion_id":3,"coord_x":565,"coord_y":290,"nivel_requerido":1,"icono":"🕳️","servicios":[]},
    {"id":5,"nombre":"Montañas Escarcha","color":"amarilla","tipo":"salvaje","faccion_id":1,"coord_x":200,"coord_y":55,"nivel_requerido":5,"icono":"⛰️","servicios":[]},
    {"id":6,"nombre":"Pantano Venenoso","color":"amarilla","tipo":"salvaje","faccion_id":1,"coord_x":130,"coord_y":130,"nivel_requerido":5,"icono":"🌿","servicios":[]},
    {"id":15,"nombre":"Ruinas Imperiales","color":"amarilla","tipo":"salvaje","faccion_id":2,"coord_x":420,"coord_y":190,"nivel_requerido":5,"icono":"🏚️","servicios":[]},
    {"id":16,"nombre":"Valle Sombrío","color":"amarilla","tipo":"salvaje","faccion_id":2,"coord_x":370,"coord_y":230,"nivel_requerido":5,"icono":"🌑","servicios":[]},
    {"id":25,"nombre":"Estepas Olvidadas","color":"amarilla","tipo":"salvaje","faccion_id":3,"coord_x":600,"coord_y":230,"nivel_requerido":5,"icono":"🌅","servicios":[]},
    {"id":26,"nombre":"Aldea Maldita","color":"amarilla","tipo":"salvaje","faccion_id":3,"coord_x":550,"coord_y":320,"nivel_requerido":5,"icono":"💀","servicios":[]},
    {"id":7,"nombre":"Fortaleza Caída","color":"roja","tipo":"salvaje","faccion_id":1,"coord_x":240,"coord_y":80,"nivel_requerido":10,"icono":"🔴","servicios":[]},
    {"id":8,"nombre":"Tierras Corrompidas","color":"roja","tipo":"salvaje","faccion_id":1,"coord_x":175,"coord_y":155,"nivel_requerido":10,"icono":"☠️","servicios":[]},
    {"id":17,"nombre":"Torre Oscura","color":"roja","tipo":"salvaje","faccion_id":2,"coord_x":450,"coord_y":140,"nivel_requerido":10,"icono":"🗼","servicios":[]},
    {"id":18,"nombre":"Campos de Ceniza","color":"roja","tipo":"salvaje","faccion_id":2,"coord_x":410,"coord_y":260,"nivel_requerido":10,"icono":"🌋","servicios":[]},
    {"id":27,"nombre":"Santuario Profanado","color":"roja","tipo":"salvaje","faccion_id":3,"coord_x":620,"coord_y":290,"nivel_requerido":10,"icono":"⛩️","servicios":[]},
    {"id":28,"nombre":"Laberinto Eterno","color":"roja","tipo":"salvaje","faccion_id":3,"coord_x":575,"coord_y":355,"nivel_requerido":10,"icono":"🌀","servicios":[]},
    {"id":9,"nombre":"Abismo del Norte","color":"negra","tipo":"salvaje","faccion_id":1,"coord_x":270,"coord_y":45,"nivel_requerido":15,"icono":"⚫","servicios":[]},
    {"id":10,"nombre":"Vacío Eterno","color":"negra","tipo":"salvaje","faccion_id":1,"coord_x":220,"coord_y":120,"nivel_requerido":15,"icono":"🌑","servicios":[]},
    {"id":19,"nombre":"Cripta de los Olvidados","color":"negra","tipo":"salvaje","faccion_id":2,"coord_x":475,"coord_y":110,"nivel_requerido":15,"icono":"⚰️","servicios":[]},
    {"id":20,"nombre":"Altar del Caos","color":"negra","tipo":"salvaje","faccion_id":2,"coord_x":445,"coord_y":295,"nivel_requerido":15,"icono":"🔱","servicios":[]},
    {"id":29,"nombre":"Dominio de las Sombras","color":"negra","tipo":"salvaje","faccion_id":3,"coord_x":640,"coord_y":355,"nivel_requerido":15,"icono":"👁️","servicios":[]},
    {"id":30,"nombre":"Nexo Oscuro","color":"negra","tipo":"salvaje","faccion_id":3,"coord_x":590,"coord_y":400,"nivel_requerido":15,"icono":"💠","servicios":[]},
]

MONSTRUOS_POR_COLOR = {
    "azul": [
        {"nombre":"Goblin Rastrero","hp":40,"atk":8,"def":2,"xp":15,"oro":8,"emoji":"👺","lore":"Un pequeño duende astuto que acecha entre arbustos."},
        {"nombre":"Lobo Sombrío","hp":55,"atk":12,"def":3,"xp":20,"oro":12,"emoji":"🐺","lore":"Lobo de pelaje oscuro que caza en manada."},
        {"nombre":"Duende Espinoso","hp":35,"atk":10,"def":1,"xp":18,"oro":10,"emoji":"🌵","lore":"Criatura que lanza proyectiles de madera afilada."},
        {"nombre":"Salamandra Azul","hp":45,"atk":11,"def":4,"xp":22,"oro":14,"emoji":"🦎","lore":"Lagarto que escupe llamas frías azuladas."},
        {"nombre":"Rata Gigante","hp":30,"atk":7,"def":1,"xp":12,"oro":6,"emoji":"🐀","lore":"Roedor enorme y hambriento."},
    ],
    "amarilla": [
        {"nombre":"Troll de Pantano","hp":120,"atk":22,"def":8,"xp":55,"oro":35,"emoji":"👹","lore":"Bestia enorme cubierta de lodo y algas."},
        {"nombre":"Araña Venenosa","hp":90,"atk":25,"def":5,"xp":48,"oro":30,"emoji":"🕷️","lore":"Araña colosal con veneno paralizante."},
        {"nombre":"Golem de Piedra","hp":150,"atk":18,"def":15,"xp":60,"oro":40,"emoji":"🗿","lore":"Constructo animado de roca viva."},
        {"nombre":"Harpía de las Ruinas","hp":100,"atk":28,"def":6,"xp":52,"oro":32,"emoji":"🦅","lore":"Ave humanoide que lanza vientos cortantes."},
        {"nombre":"Necrófago","hp":110,"atk":20,"def":7,"xp":50,"oro":28,"emoji":"💀","lore":"Muerto viviente que se regenera si no se destruye rápido."},
    ],
    "roja": [
        {"nombre":"Dragón Joven","hp":280,"atk":48,"def":18,"xp":140,"oro":100,"emoji":"🐲","lore":"Dragón inmaduro pero devastadoramente peligroso."},
        {"nombre":"Demonio Menor","hp":240,"atk":55,"def":12,"xp":130,"oro":90,"emoji":"😈","lore":"Criatura infernal con poderes oscuros."},
        {"nombre":"Guerrero Espectral","hp":200,"atk":50,"def":20,"xp":125,"oro":85,"emoji":"👻","lore":"Alma guerrera atrapada entre mundos."},
        {"nombre":"Quimera Roja","hp":320,"atk":42,"def":22,"xp":160,"oro":110,"emoji":"🔥","lore":"Bestia híbrida con cabeza de dragón y cuerpo de león."},
        {"nombre":"Lich Menor","hp":260,"atk":58,"def":10,"xp":145,"oro":95,"emoji":"🧙","lore":"Hechicero no-muerto que domina la magia de la muerte."},
    ],
    "negra": [
        {"nombre":"Señor de la Sombra","hp":600,"atk":95,"def":35,"xp":350,"oro":280,"emoji":"🌑","lore":"Entidad oscura que consume la luz a su alrededor."},
        {"nombre":"Dragón Ancestral","hp":800,"atk":110,"def":40,"xp":450,"oro":380,"emoji":"🐉","lore":"Dragón milenario de escamas negras como el vacío."},
        {"nombre":"Avatar del Caos","hp":700,"atk":100,"def":38,"xp":400,"oro":320,"emoji":"🔱","lore":"Manifestación física del caos primordial."},
        {"nombre":"Dios Menor Caído","hp":900,"atk":120,"def":45,"xp":500,"oro":420,"emoji":"👁️","lore":"Deidad que perdió su esencia divina y se corrompió."},
        {"nombre":"Titán de Piedra Negra","hp":750,"atk":105,"def":50,"xp":420,"oro":350,"emoji":"⚫","lore":"Coloso construido con la roca del inframundo."},
    ],
}

MINI_BOSSES = {
    "azul": {"nombre":"Rey de los Duendes","hp":180,"atk":20,"def":10,"xp":80,"oro":60,"emoji":"👑","lore":"Líder de los goblins, astuto y peligroso."},
    "amarilla": {"nombre":"Troll Anciano","hp":400,"atk":40,"def":20,"xp":200,"oro":150,"emoji":"👹","lore":"Troll que lleva siglos controlando el pantano."},
    "roja": {"nombre":"Archidemon","hp":900,"atk":80,"def":30,"xp":500,"oro":400,"emoji":"😈","lore":"Demonio de rango superior invocado por un culto."},
    "negra": {"nombre":"El Eterno","hp":2000,"atk":150,"def":60,"xp":1200,"oro":1000,"emoji":"☠️","lore":"Ser que ha vivido más allá del fin del mundo."},
}

CLASES = {
    "vanguardista": {"nombre":"🛡️ Vanguardista","emoji":"🛡️","vida_max":140,"daño_base":12,"defensa_base":14,"descripcion":"Tanque de primera línea. Alta defensa y vida."},
    "acechante": {"nombre":"🗡️ Acechante","emoji":"🗡️","vida_max":90,"daño_base":20,"defensa_base":5,"descripcion":"Asesino sigiloso. Daño crítico y movilidad."},
    "tejehechizos": {"nombre":"🔮 Tejehechizos","emoji":"🔮","vida_max":80,"daño_base":18,"defensa_base":4,"descripcion":"Mago versátil. Daño mágico y curación."},
    "maestro_caza": {"nombre":"🏹 Maestro de Caza","emoji":"🏹","vida_max":100,"daño_base":16,"defensa_base":7,"descripcion":"Arquero preciso. Daño a distancia y control."},
}

HABILIDADES = {
    "vanguardista": [
        {"nombre":"Golpe Escudo","daño":22,"cooldown":2,"descripcion":"Golpea con el escudo causando daño y aturdiendo 1 turno.","emoji":"🛡️"},
        {"nombre":"Muro de Hierro","cura":25,"defensa_extra":20,"cooldown":3,"descripcion":"Recuperas 25 HP y aumentas resistencia.","emoji":"⛏️"},
    ],
    "acechante": [
        {"nombre":"Golpe Crítico","daño":42,"ignora_defensa":0.3,"cooldown":2,"descripcion":"Ataque preciso que ignora 30% de defensa enemiga.","emoji":"⚡"},
        {"nombre":"Golpe en la Sombra","daño":30,"evasion":50,"cooldown":3,"descripcion":"Ataque desde las sombras con 50% de evasión.","emoji":"🌑"},
    ],
    "tejehechizos": [
        {"nombre":"Rayo Arcano","daño":32,"tipo":"magico","cooldown":2,"descripcion":"Lanza energía mágica imparable.","emoji":"🔮"},
        {"nombre":"Bendición Curativa","cura":35,"cooldown":3,"descripcion":"Restaura 35 HP. Si hay aliados, los cura también.","emoji":"✨"},
    ],
    "maestro_caza": [
        {"nombre":"Flecha Perforante","daño":34,"ignora_defensa":1.0,"cooldown":2,"descripcion":"Flecha que atraviesa completamente la defensa.","emoji":"🏹"},
        {"nombre":"Trampa de Raíces","daño":20,"aturde":1,"cooldown":3,"descripcion":"Trampa que enreda al enemigo 1 turno.","emoji":"🌿"},
    ],
}

POCIONES_TIENDA = [
    {"id":"pocion_vida_menor","nombre":"Poción de Vida Menor","efecto":"cura","valor":50,"precio_oro":80,"nivel_req":1,"emoji":"🧪","descripcion":"Restaura 50 HP."},
    {"id":"pocion_vida_media","nombre":"Poción de Vida Media","efecto":"cura","valor":150,"precio_oro":200,"nivel_req":5,"emoji":"🍶","descripcion":"Restaura 150 HP."},
    {"id":"pocion_vida_mayor","nombre":"Poción de Vida Mayor","efecto":"cura","valor":350,"precio_oro":450,"nivel_req":15,"emoji":"⚗️","descripcion":"Restaura 350 HP."},
    {"id":"pocion_stamina","nombre":"Elixir de Energía","efecto":"stamina","valor":30,"precio_oro":120,"nivel_req":1,"emoji":"💧","descripcion":"Restaura 30 de stamina."},
    {"id":"pocion_fuerza","nombre":"Poción de Fuerza","efecto":"atk_buff","valor":15,"precio_oro":180,"duracion":3,"nivel_req":8,"emoji":"💪","descripcion":"ATK +15 por 3 combates."},
    {"id":"antidoto","nombre":"Antídoto","efecto":"curar_veneno","valor":1,"precio_oro":60,"nivel_req":1,"emoji":"🌿","descripcion":"Elimina el veneno."},
]

MATERIALES_COMUNES = {
    "azul": ["Madera del Bosque","Piedra Ordinaria","Hierba Silvestre","Resina Clara","Fibra Vegetal"],
    "amarilla": ["Hierro Impuro","Cristal Turbio","Piel Gruesa","Plumas de Harpía","Hueso Pulido"],
    "roja": ["Acero Rojo","Gema de Fuego","Escama de Dragón","Sangre de Demonio","Roca Volcánica"],
    "negra": ["Sombra Cristalizada","Eternium Puro","Fragmento del Vacío","Alma Atrapada","Obsidiana Negra"],
}

def get_zone_by_id(zone_id: int) -> Optional[Dict]:
    return next((z for z in ZONAS if z["id"] == zone_id), None)

def get_zone_by_name(name: str) -> Optional[Dict]:
    return next((z for z in ZONAS if z["nombre"] == name), None)

def get_random_monster(color: str, is_miniboss: bool = False) -> Dict:
    if is_miniboss:
        boss = MINI_BOSSES.get(color, MINI_BOSSES["azul"])
        return dict(boss)
    monsters = MONSTRUOS_POR_COLOR.get(color, MONSTRUOS_POR_COLOR["azul"])
    return dict(random.choice(monsters))

def scale_monster(monster: Dict, player_level: int) -> Dict:
    m = dict(monster)
    scale = 1.0 + (player_level - 1) * 0.12
    m["hp"] = int(m["hp"] * scale)
    m["atk"] = int(m["atk"] * scale)
    m["def"] = int(m.get("def", 0) * scale)
    m["xp"] = int(m.get("xp", 10) * scale)
    m["oro"] = int(m.get("oro", 5) * scale)
    return m

def calc_player_atk(player: Dict) -> int:
    clase = player.get("clase", "vanguardista")
    nivel = player.get("nivel", 1)
    base_dmg = CLASES.get(clase, {}).get("daño_base", 12)
    return base_dmg + (nivel - 1) * 3

def calc_player_def(player: Dict) -> int:
    clase = player.get("clase", "vanguardista")
    nivel = player.get("nivel", 1)
    base_def = CLASES.get(clase, {}).get("defensa_base", 8)
    return base_def + (nivel - 1) * 2

def calc_player_max_hp(player: Dict) -> int:
    clase = player.get("clase", "vanguardista")
    nivel = player.get("nivel", 1)
    base_hp = CLASES.get(clase, {}).get("vida_max", 100)
    return base_hp + (nivel - 1) * 10

def xp_para_nivel(nivel: int) -> int:
    return int(100 * (nivel ** 1.5))

def get_random_material(color: str) -> str:
    materials = MATERIALES_COMUNES.get(color, MATERIALES_COMUNES["azul"])
    return random.choice(materials)

def get_travel_time(from_color: str, to_color: str) -> int:
    color_index = {"azul": 0, "amarilla": 1, "roja": 2, "negra": 3}
    from_idx = color_index.get(from_color, 0)
    to_idx = color_index.get(to_color, 0)
    diff = abs(to_idx - from_idx)
    return max(15, diff * 30 + 15)

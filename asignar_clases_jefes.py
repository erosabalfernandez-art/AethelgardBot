import re
import random
from collections import Counter

# Clases disponibles
CLASES = ['vanguardista', 'acechante', 'tejehechizos', 'maestro_caza']

def encontrar_y_asignar_clases(contenido):
    def procesar_lista(lista_texto):
        dicts = []
        patron_dict = r'\{(?:[^{}]|(?:\{[^{}]*\}))*\}'
        for match in re.finditer(patron_dict, lista_texto):
            dict_str = match.group(0)
            if '"clase"' not in dict_str:
                dicts.append(dict_str)
            else:
                dicts.append(dict_str)
        return dicts
    
    def reemplazar_lista(match):
        lista_key = match.group(1)
        contenido_lista = match.group(2)
        dicts_raw = procesar_lista(contenido_lista)
        if not dicts_raw:
            return match.group(0)
        n = len(dicts_raw)
        clases_asignadas = []
        for i in range(n):
            clases_asignadas.append(CLASES[i % len(CLASES)])
        random.shuffle(clases_asignadas)
        
        nuevos_dicts = []
        for i, dict_str in enumerate(dicts_raw):
            dict_str = dict_str.rstrip()
            if dict_str.endswith('}'):
                nuevo = dict_str[:-1] + f', "clase": "{clases_asignadas[i]}"' + '}'
            else:
                nuevo = dict_str + f', "clase": "{clases_asignadas[i]}"'
            nuevos_dicts.append(nuevo)
        nueva_lista = '[' + ', '.join(nuevos_dicts) + ']'
        return f'"{lista_key}": {nueva_lista}'
    
    patron_normal = r'"(jefes_zona_normal)"\s*:\s*(\[[\s\S]*?\])'
    patron_dificil = r'"(jefes_zona_dificil)"\s*:\s*(\[[\s\S]*?\])'
    
    contenido = re.sub(patron_normal, reemplazar_lista, contenido, flags=re.DOTALL)
    contenido = re.sub(patron_dificil, reemplazar_lista, contenido, flags=re.DOTALL)
    return contenido

with open("datos_zona.py", "r", encoding="utf-8") as f:
    data = f.read()

with open("datos_zona_backup.py", "w", encoding="utf-8") as f:
    f.write(data)

random.seed()
nuevo_contenido = encontrar_y_asignar_clases(data)

with open("datos_zona.py", "w", encoding="utf-8") as f:
    f.write(nuevo_contenido)

print("Paso 1 completado.")
print("Se han asignado las 4 clases de forma proporcional y aleatoria a todos los jefes de zona (normales y difíciles).")
print("Backup guardado como datos_zona_backup.py")
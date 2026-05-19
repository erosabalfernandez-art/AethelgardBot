from fastapi import APIRouter, Depends, HTTPException
from auth import get_current_user
import database as db
from game_data import ZONAS, get_zone_by_name, get_zone_by_id

router = APIRouter(prefix="/map", tags=["map"])

COLOR_DANGER = {
    "azul": {"nivel":"Segura","color_hex":"#4A90D9","descripcion":"Zona segura. Sin PvP. Ideal para principiantes.","pvp":False},
    "amarilla": {"nivel":"Peligrosa","color_hex":"#F5A623","descripcion":"Zona de peligro moderado. PvP posible. Pierdes 10% de oro si mueres.","pvp":True},
    "roja": {"nivel":"Muy Peligrosa","color_hex":"#D0021B","descripcion":"Zona de alto riesgo. PvP habitual. Pierdes 50% de oro si mueres.","pvp":True},
    "negra": {"nivel":"Extrema","color_hex":"#1a1a2e","descripcion":"Zona de muerte. Todo se pierde al morir. Solo para los más fuertes.","pvp":True},
}

@router.get("/zones")
async def get_all_zones(user: dict = Depends(get_current_user)):
    user_id = user["id"]
    player = db.get_player(user_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    player_level = player.get("nivel", 1)
    current_zone = player.get("zona_actual", "")
    ubicacion = player.get("ubicacion", "ciudad")

    zones_data = []
    for zona in ZONAS:
        color = zona["color"]
        danger = COLOR_DANGER.get(color, COLOR_DANGER["azul"])
        players_here = db.players_in_zone(zona["nombre"])
        can_access = player_level >= zona.get("nivel_requerido", 1)

        zones_data.append({
            "id": zona["id"],
            "nombre": zona["nombre"],
            "color": color,
            "tipo": zona["tipo"],
            "faccion_id": zona["faccion_id"],
            "coord_x": zona["coord_x"],
            "coord_y": zona["coord_y"],
            "icono": zona["icono"],
            "servicios": zona.get("servicios", []),
            "nivel_requerido": zona.get("nivel_requerido", 1),
            "peligrosidad": danger["nivel"],
            "color_hex": danger["color_hex"],
            "pvp": danger["pvp"],
            "descripcion_peligro": danger["descripcion"],
            "jugadores_aqui": len(players_here),
            "es_ubicacion_actual": zona["nombre"] == current_zone,
            "accesible": can_access,
        })

    return {
        "zones": zones_data,
        "zona_actual": current_zone,
        "zona_actual_id": player.get("zona_actual_id"),
        "ubicacion": ubicacion,
        "player_level": player_level,
    }

@router.get("/zone/{zone_id}")
async def get_zone_detail(zone_id: int, user: dict = Depends(get_current_user)):
    user_id = user["id"]
    zona = get_zone_by_id(zone_id)
    if not zona:
        raise HTTPException(status_code=404, detail="Zone not found")

    players_here = db.players_in_zone(zona["nombre"])
    color = zona["color"]
    danger = COLOR_DANGER.get(color, COLOR_DANGER["azul"])

    from game_data import MATERIALES_COMUNES
    materials = MATERIALES_COMUNES.get(color, [])

    return {
        "zona": {**zona, **danger},
        "materiales_posibles": materials,
        "jugadores": players_here[:10],
        "total_jugadores": len(players_here),
    }

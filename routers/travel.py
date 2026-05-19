from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from datetime import datetime, timedelta
from auth import get_current_user
import database as db
from game_data import get_zone_by_id, get_travel_time, ZONAS

router = APIRouter(prefix="/travel", tags=["travel"])

class TravelRequest(BaseModel):
    destination_id: int
    fast_travel: bool = False

@router.post("/start")
async def start_travel(req: TravelRequest, user: dict = Depends(get_current_user)):
    user_id = user["id"]
    player = db.get_player(user_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    ubicacion = player.get("ubicacion", "ciudad")
    if ubicacion == "viajando":
        arrive = player.get("viaje_hasta")
        raise HTTPException(status_code=400, detail=f"Ya estás viajando. Llegas: {arrive}")

    if player.get("actividad_actual"):
        raise HTTPException(status_code=400, detail="Estás en una actividad. Termínala primero.")

    destino = get_zone_by_id(req.destination_id)
    if not destino:
        raise HTTPException(status_code=404, detail="Destination zone not found")

    player_level = player.get("nivel", 1)
    if player_level < destino.get("nivel_requerido", 1):
        raise HTTPException(
            status_code=400,
            detail=f"Necesitas nivel {destino['nivel_requerido']} para viajar aquí. Tu nivel: {player_level}"
        )

    zona_actual_nombre = player.get("zona_actual", "")
    from game_data import get_zone_by_name
    zona_actual = get_zone_by_name(zona_actual_nombre)
    from_color = zona_actual["color"] if zona_actual else "azul"
    to_color = destino["color"]

    stamina = player.get("stamina_actual", 100)
    stamina_cost = int(db.get_config("viaje_stamina_coste", "5"))

    if req.fast_travel:
        eternium = player.get("eternium", 0)
        fast_cost = 30
        if eternium < fast_cost:
            raise HTTPException(status_code=400, detail=f"Necesitas {fast_cost} Eternium para viaje rápido.")
        db.update_player(user_id, eternium=eternium - fast_cost,
                         zona_actual=destino["nombre"],
                         zona_actual_id=destino["id"],
                         ubicacion="ciudad" if destino["tipo"] == "ciudad" else "salvaje")
        return {"status":"arrived","message":f"✈️ Viaje rápido a {destino['nombre']} completado.","destino":destino["nombre"],"viaje_rapido":True}

    if stamina < stamina_cost:
        raise HTTPException(status_code=400, detail=f"Stamina insuficiente. Necesitas {stamina_cost}. Tienes: {stamina}")

    travel_secs = get_travel_time(from_color, to_color)
    arrive_at = datetime.now() + timedelta(seconds=travel_secs)

    db.update_player(
        user_id,
        ubicacion="viajando",
        viaje_hasta=arrive_at.isoformat(),
        viaje_destino_id=req.destination_id,
        stamina_actual=max(0, stamina - stamina_cost),
    )

    return {
        "status": "traveling",
        "message": f"🗺️ Viajando hacia {destino['nombre']}...",
        "destino": destino["nombre"],
        "destino_id": req.destination_id,
        "llega_en_segundos": travel_secs,
        "llega_a": arrive_at.isoformat(),
        "stamina_gastada": stamina_cost,
    }

@router.get("/status")
async def get_travel_status(user: dict = Depends(get_current_user)):
    user_id = user["id"]
    player = db.get_player(user_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    ubicacion = player.get("ubicacion", "ciudad")
    if ubicacion != "viajando":
        return {"traveling": False, "ubicacion": ubicacion, "zona_actual": player.get("zona_actual")}

    viaje_hasta_str = player.get("viaje_hasta")
    destino_id = player.get("viaje_destino_id")

    if not viaje_hasta_str:
        db.update_player(user_id, ubicacion="ciudad")
        return {"traveling": False}

    try:
        viaje_hasta = datetime.fromisoformat(viaje_hasta_str)
    except Exception:
        db.update_player(user_id, ubicacion="ciudad")
        return {"traveling": False}

    now = datetime.now()
    if now >= viaje_hasta:
        destino = get_zone_by_id(destino_id) if destino_id else None
        if destino:
            new_ubicacion = "ciudad" if destino["tipo"] == "ciudad" else "salvaje"
            db.update_player(
                user_id,
                zona_actual=destino["nombre"],
                zona_actual_id=destino["id"],
                ubicacion=new_ubicacion,
                viaje_hasta=None,
                viaje_destino_id=None,
            )
            db.add_notification(user_id, f"✅ Has llegado a {destino['nombre']}.")
            return {
                "traveling": False,
                "just_arrived": True,
                "zona_actual": destino["nombre"],
                "zona_id": destino["id"],
                "ubicacion": new_ubicacion,
            }
        db.update_player(user_id, ubicacion="ciudad", viaje_hasta=None)
        return {"traveling": False}

    seconds_left = int((viaje_hasta - now).total_seconds())
    destino = get_zone_by_id(destino_id) if destino_id else None
    return {
        "traveling": True,
        "segundos_restantes": seconds_left,
        "llega_a": viaje_hasta_str,
        "destino": destino["nombre"] if destino else "Desconocido",
        "destino_id": destino_id,
        "destino_color": destino["color"] if destino else "azul",
    }

@router.post("/cancel")
async def cancel_travel(user: dict = Depends(get_current_user)):
    user_id = user["id"]
    player = db.get_player(user_id)
    if not player or player.get("ubicacion") != "viajando":
        raise HTTPException(status_code=400, detail="No estás viajando.")
    db.update_player(user_id, ubicacion="ciudad", viaje_hasta=None, viaje_destino_id=None)
    return {"status": "cancelled", "message": "Viaje cancelado. Has regresado a tu zona anterior."}

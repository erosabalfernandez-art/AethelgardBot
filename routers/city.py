import random
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from auth import get_current_user
import database as db
from game_data import POCIONES_TIENDA, calc_player_max_hp

router = APIRouter(prefix="/city", tags=["city"])

class BuyRequest(BaseModel):
    item_id: str
    cantidad: int = 1

class BankRequest(BaseModel):
    accion: str
    monto: int
    de: str = "oro"
    a: str = "eternium"

class TabernRequest(BaseModel):
    accion: str = "descansar"

@router.get("/services")
async def get_city_services(user: dict = Depends(get_current_user)):
    user_id = user["id"]
    player = db.get_player(user_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    from game_data import get_zone_by_name
    zona = get_zone_by_name(player.get("zona_actual", ""))
    if not zona or zona["tipo"] != "ciudad":
        return {"en_ciudad": False, "servicios": [], "zona": player.get("zona_actual")}

    return {
        "en_ciudad": True,
        "zona": zona["nombre"],
        "servicios": zona.get("servicios", ["banco", "mercado", "taberna"]),
        "faccion": player.get("faccion"),
    }

@router.get("/shop")
async def get_shop(user: dict = Depends(get_current_user)):
    user_id = user["id"]
    player = db.get_player(user_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    nivel = player.get("nivel", 1)
    items_available = [p for p in POCIONES_TIENDA if p.get("nivel_req", 1) <= nivel]

    return {
        "items": items_available,
        "oro_jugador": player.get("oro", 0),
        "eternium_jugador": player.get("eternium", 0),
        "creditos_jugador": player.get("creditos_vacio", 0),
    }

@router.post("/shop/buy")
async def buy_item(req: BuyRequest, user: dict = Depends(get_current_user)):
    user_id = user["id"]
    player = db.get_player(user_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    item = next((p for p in POCIONES_TIENDA if p["id"] == req.item_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="Item no encontrado en tienda.")

    if player.get("nivel", 1) < item.get("nivel_req", 1):
        raise HTTPException(status_code=400, detail=f"Necesitas nivel {item['nivel_req']} para comprar esto.")

    precio_total = item["precio_oro"] * req.cantidad
    if player.get("oro", 0) < precio_total:
        raise HTTPException(status_code=400, detail=f"Oro insuficiente. Necesitas {precio_total} 🪙")

    db.update_player(user_id, oro=player["oro"] - precio_total)
    inv = db.get_player_inventory(user_id)
    for _ in range(req.cantidad):
        existing = next((i for i in inv if isinstance(i, dict) and i.get("id") == item["id"]), None)
        if existing:
            existing["cantidad"] = existing.get("cantidad", 1) + 1
        else:
            inv.append({
                "id": item["id"],
                "nombre": item["nombre"],
                "tipo": "pocion",
                "efecto": item["efecto"],
                "valor": item["valor"],
                "emoji": item["emoji"],
                "descripcion": item["descripcion"],
                "cantidad": 1,
                "precio_venta_oro": int(item["precio_oro"] * 0.5),
            })
    db.set_player_inventory(user_id, inv)

    return {
        "status": "bought",
        "message": f"🛒 Compraste {req.cantidad}x {item['nombre']} por {precio_total} 🪙 Oro",
        "oro_restante": player["oro"] - precio_total,
    }

@router.get("/bank")
async def get_bank(user: dict = Depends(get_current_user)):
    user_id = user["id"]
    player = db.get_player(user_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    tasa_et = int(db.get_config("banco_credito_a_eternium", "10"))
    tasa_oro = int(db.get_config("banco_credito_a_oro", "10000"))

    return {
        "oro": player.get("oro", 0),
        "eternium": player.get("eternium", 0),
        "creditos": player.get("creditos_vacio", 0),
        "tasa_credito_a_eternium": tasa_et,
        "tasa_credito_a_oro": tasa_oro,
        "info": f"1 Crédito del Vacío = {tasa_et} Eternium o {tasa_oro:,} Oro",
    }

@router.post("/bank/exchange")
async def bank_exchange(req: BankRequest, user: dict = Depends(get_current_user)):
    user_id = user["id"]
    player = db.get_player(user_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    if req.monto <= 0:
        raise HTTPException(status_code=400, detail="El monto debe ser positivo.")

    if req.accion == "cambiar" and req.de == "creditos" and req.a == "eternium":
        tasa = int(db.get_config("banco_credito_a_eternium", "10"))
        creditos = player.get("creditos_vacio", 0)
        if creditos < req.monto:
            raise HTTPException(status_code=400, detail=f"No tienes suficientes créditos ({creditos}).")
        ganancia = req.monto * tasa
        db.update_player(user_id, creditos_vacio=creditos - req.monto, eternium=player.get("eternium", 0) + ganancia)
        return {"status": "ok", "message": f"✅ Cambiaste {req.monto} Créditos por {ganancia} Eternium."}

    if req.accion == "cambiar" and req.de == "creditos" and req.a == "oro":
        tasa = int(db.get_config("banco_credito_a_oro", "10000"))
        creditos = player.get("creditos_vacio", 0)
        if creditos < req.monto:
            raise HTTPException(status_code=400, detail=f"No tienes suficientes créditos ({creditos}).")
        ganancia = req.monto * tasa
        db.update_player(user_id, creditos_vacio=creditos - req.monto, oro=player.get("oro", 0) + ganancia)
        return {"status": "ok", "message": f"✅ Cambiaste {req.monto} Créditos por {ganancia:,} Oro."}

    raise HTTPException(status_code=400, detail="Operación no soportada actualmente.")

@router.post("/tavern")
async def use_tavern(req: TabernRequest, user: dict = Depends(get_current_user)):
    user_id = user["id"]
    player = db.get_player(user_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    from game_data import get_zone_by_name
    zona = get_zone_by_name(player.get("zona_actual", ""))
    if not zona or zona["tipo"] != "ciudad" or "taberna" not in zona.get("servicios", []):
        raise HTTPException(status_code=400, detail="No hay taberna disponible aquí.")

    costo = int(db.get_config("taberna_costo_descansar", "50"))
    oro = player.get("oro", 0)
    if oro < costo:
        raise HTTPException(status_code=400, detail=f"Necesitas {costo} Oro para descansar. Tienes: {oro}.")

    hp_max = calc_player_max_hp(player)
    st_max = player.get("stamina_maxima", 100)
    stamina_rec = int(db.get_config("taberna_stamina_recupera", "20"))

    new_hp = hp_max
    new_stamina = min(st_max, player.get("stamina_actual", 0) + stamina_rec)

    db.update_player(user_id, oro=oro - costo, hp_actual=new_hp, stamina_actual=new_stamina)

    return {
        "status": "rested",
        "message": f"🍺 Descansaste en la taberna. HP restaurado al máximo. +{stamina_rec} Stamina.",
        "hp_nuevo": new_hp,
        "hp_max": hp_max,
        "stamina_nueva": new_stamina,
        "oro_gastado": costo,
    }

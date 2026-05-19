import json
import random
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from auth import get_current_user
import database as db

router = APIRouter(prefix="/inventory", tags=["inventory"])

RARITY_COLORS = {1:"#9E9E9E",2:"#4CAF50",3:"#2196F3",4:"#9C27B0",5:"#FF9800",6:"#F44336",12:"#FFD700"}
RARITY_NAMES = {1:"Común",2:"Poco Común",3:"Raro",4:"Épico",5:"Legendario",6:"Único",12:"Artefacto"}

class UseItemRequest(BaseModel):
    item_nombre: str
    item_tipo: Optional[str] = None

class EquipRequest(BaseModel):
    item_nombre: str

@router.get("/")
async def get_inventory(user: dict = Depends(get_current_user)):
    user_id = user["id"]
    player = db.get_player(user_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    raw_inv = player.get("inventario", "[]")
    try:
        inv = json.loads(raw_inv) if raw_inv else []
    except Exception:
        inv = []

    weapons, armor, potions, materials, misc = [], [], [], [], []
    for item in inv:
        if not isinstance(item, dict):
            misc.append({"nombre": str(item), "tipo": "misc", "cantidad": 1})
            continue
        tipo = item.get("tipo", "misc")
        rareza = item.get("rareza", 1)
        item_full = {
            **item,
            "rareza_nombre": RARITY_NAMES.get(rareza, "Común"),
            "rareza_color": RARITY_COLORS.get(rareza, "#9E9E9E"),
        }
        if tipo in ("arma", "weapon"):
            weapons.append(item_full)
        elif tipo in ("armadura", "armor"):
            armor.append(item_full)
        elif tipo in ("pocion", "potion"):
            potions.append(item_full)
        elif tipo == "material":
            materials.append(item_full)
        else:
            misc.append(item_full)

    return {
        "armas": weapons,
        "armaduras": armor,
        "pociones": potions,
        "materiales": materials,
        "misc": misc,
        "total": len(inv),
    }

@router.post("/use")
async def use_item(req: UseItemRequest, user: dict = Depends(get_current_user)):
    user_id = user["id"]
    player = db.get_player(user_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    inv = db.get_player_inventory(user_id)
    item = next((i for i in inv if isinstance(i, dict) and i.get("nombre") == req.item_nombre), None)
    if not item:
        raise HTTPException(status_code=404, detail="Item no encontrado en inventario.")

    efecto = item.get("efecto")
    message = ""

    if efecto == "cura":
        heal = item.get("valor", 50)
        from game_data import calc_player_max_hp
        hp_max = calc_player_max_hp(player)
        new_hp = min(hp_max, player.get("hp_actual", 0) + heal)
        db.update_player(user_id, hp_actual=new_hp)
        message = f"💚 Usaste {item['nombre']}: +{heal} HP (HP: {new_hp}/{hp_max})"

    elif efecto == "stamina":
        val = item.get("valor", 30)
        st_max = player.get("stamina_maxima", 100)
        new_st = min(st_max, player.get("stamina_actual", 0) + val)
        db.update_player(user_id, stamina_actual=new_st)
        message = f"⚡ Usaste {item['nombre']}: +{val} Stamina"

    elif efecto == "atk_buff":
        message = f"💪 {item['nombre']} activado: ATK +{item.get('valor',15)} por {item.get('duracion',3)} combates."

    elif efecto == "curar_veneno":
        message = f"🌿 {item['nombre']}: Veneno eliminado."
    else:
        raise HTTPException(status_code=400, detail="Este ítem no se puede usar directamente.")

    cantidad = item.get("cantidad", 1)
    if cantidad <= 1:
        inv.remove(item)
    else:
        item["cantidad"] = cantidad - 1

    db.set_player_inventory(user_id, inv)
    return {"status": "used", "message": message}

@router.post("/sell")
async def sell_item(req: UseItemRequest, user: dict = Depends(get_current_user)):
    user_id = user["id"]
    inv = db.get_player_inventory(user_id)
    item = next((i for i in inv if isinstance(i, dict) and i.get("nombre") == req.item_nombre), None)
    if not item:
        raise HTTPException(status_code=404, detail="Item no encontrado.")

    precio_venta = item.get("precio_venta_oro", item.get("precio_oro", 10))
    precio_venta = max(1, int(precio_venta * 0.5))

    player = db.get_player(user_id)
    db.update_player(user_id, oro=player.get("oro", 0) + precio_venta)
    inv.remove(item)
    db.set_player_inventory(user_id, inv)

    return {
        "status": "sold",
        "message": f"💰 Vendiste {item['nombre']} por {precio_venta} 🪙 Oro",
        "oro_ganado": precio_venta,
    }

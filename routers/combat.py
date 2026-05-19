import random
import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from auth import get_current_user
import database as db
from game_data import (
    get_zone_by_name, get_random_monster, scale_monster,
    calc_player_atk, calc_player_def, calc_player_max_hp,
    HABILIDADES, xp_para_nivel, get_random_material
)

router = APIRouter(prefix="/combat", tags=["combat"])

_active_combats: dict = {}

class CombatAction(BaseModel):
    action: str
    skill_index: Optional[int] = None

def _get_combat(user_id: int) -> Optional[dict]:
    return _active_combats.get(user_id)

def _save_combat(user_id: int, state: dict):
    _active_combats[user_id] = state

def _end_combat(user_id: int):
    _active_combats.pop(user_id, None)

def _calc_damage(atk: int, defender_def: int, critico_pct: float = 15.0) -> dict:
    is_crit = random.random() * 100 < critico_pct
    base_dmg = max(1, atk - int(defender_def * 0.4))
    dmg = int(base_dmg * (2.0 if is_crit else 1.0))
    variance = random.uniform(0.85, 1.15)
    dmg = max(1, int(dmg * variance))
    return {"damage": dmg, "critical": is_crit}

@router.get("/status")
async def get_combat_status(user: dict = Depends(get_current_user)):
    user_id = user["id"]
    combat = _get_combat(user_id)
    if not combat:
        return {"in_combat": False}
    return {"in_combat": True, "combat": combat}

@router.post("/start")
async def start_combat(user: dict = Depends(get_current_user)):
    user_id = user["id"]

    if _get_combat(user_id):
        raise HTTPException(status_code=400, detail="Ya estás en combate. Termina el actual primero.")

    player = db.get_player(user_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    if player.get("ubicacion") == "viajando":
        raise HTTPException(status_code=400, detail="No puedes combatir mientras viajas.")

    zona_nombre = player.get("zona_actual", "")
    zona = get_zone_by_name(zona_nombre)
    if not zona or zona["tipo"] == "ciudad":
        raise HTTPException(status_code=400, detail="Solo puedes combatir en zonas salvajes.")

    color = zona["color"]
    stamina = player.get("stamina_actual", 0)
    stamina_cost = int(db.get_config("stamina_explorar", "5"))
    if stamina < stamina_cost:
        raise HTTPException(status_code=400, detail=f"Stamina insuficiente ({stamina}/{stamina_cost}). Descansa en la taberna.")

    is_miniboss = random.random() < 0.08
    monster_raw = get_random_monster(color, is_miniboss)
    monster = scale_monster(monster_raw, player.get("nivel", 1))

    player_hp_max = calc_player_max_hp(player)
    player_hp = min(player.get("hp_actual", player_hp_max), player_hp_max)
    player_atk = calc_player_atk(player)
    player_def = calc_player_def(player)

    clase = player.get("clase", "vanguardista")
    habs = HABILIDADES.get(clase, [])
    cooldowns = {str(i): 0 for i in range(len(habs))}

    combat_state = {
        "user_id": user_id,
        "zona_color": color,
        "zona_nombre": zona_nombre,
        "turno": 1,
        "player": {
            "nombre": player.get("nombre_personaje", "Héroe"),
            "clase": clase,
            "hp": player_hp,
            "hp_max": player_hp_max,
            "atk": player_atk,
            "def": player_def,
            "nivel": player.get("nivel", 1),
        },
        "monster": {
            "nombre": monster["nombre"],
            "emoji": monster.get("emoji", "👾"),
            "hp": monster["hp"],
            "hp_max": monster["hp"],
            "atk": monster["atk"],
            "def": monster.get("def", 0),
            "xp": monster.get("xp", 10),
            "oro": monster.get("oro", 5),
            "lore": monster.get("lore", ""),
            "is_miniboss": is_miniboss,
        },
        "log": [f"⚔️ ¡{monster['emoji']} {monster['nombre']} aparece!{' ¡Es un MINI-BOSS!' if is_miniboss else ''}"],
        "cooldowns": cooldowns,
        "habilidades": habs,
        "is_miniboss": is_miniboss,
        "started_at": datetime.now().isoformat(),
    }

    db.update_player(user_id, stamina_actual=max(0, stamina - stamina_cost))
    _save_combat(user_id, combat_state)
    return {"in_combat": True, "combat": combat_state}

@router.post("/action")
async def combat_action(action_req: CombatAction, user: dict = Depends(get_current_user)):
    user_id = user["id"]
    combat = _get_combat(user_id)
    if not combat:
        raise HTTPException(status_code=400, detail="No estás en combate.")

    action = action_req.action
    log = []
    result = None

    player = combat["player"]
    monster = combat["monster"]
    cooldowns = combat["cooldowns"]
    habs = combat["habilidades"]
    turno = combat["turno"]

    for k in list(cooldowns.keys()):
        if cooldowns[k] > 0:
            cooldowns[k] -= 1

    if action == "attack":
        dmg_data = _calc_damage(player["atk"], monster["def"])
        dmg = dmg_data["damage"]
        monster["hp"] = max(0, monster["hp"] - dmg)
        crit_txt = " ¡CRÍTICO! 💥" if dmg_data["critical"] else ""
        log.append(f"⚔️ Atacas: -{dmg} HP al {monster['nombre']}{crit_txt}")

    elif action == "skill" and action_req.skill_index is not None:
        idx = action_req.skill_index
        if idx < 0 or idx >= len(habs):
            raise HTTPException(status_code=400, detail="Habilidad inválida.")
        cd = cooldowns.get(str(idx), 0)
        if cd > 0:
            raise HTTPException(status_code=400, detail=f"Habilidad en cooldown ({cd} turnos).")
        hab = habs[idx]
        cooldowns[str(idx)] = hab.get("cooldown", 2)

        if "daño" in hab:
            daño_base = hab["daño"]
            ignora = hab.get("ignora_defensa", 0)
            effective_def = int(monster["def"] * (1 - ignora))
            dmg = max(1, daño_base + player["atk"] - effective_def)
            if "tipo" in hab and hab["tipo"] == "magico":
                dmg = int(dmg * 1.2)
            monster["hp"] = max(0, monster["hp"] - dmg)
            log.append(f"✨ [{hab['nombre']}]: -{dmg} HP al {monster['nombre']}! {hab['emoji']}")
        if "cura" in hab:
            heal = hab["cura"]
            player["hp"] = min(player["hp_max"], player["hp"] + heal)
            log.append(f"💚 [{hab['nombre']}]: +{heal} HP restaurado! {hab['emoji']}")
        if "aturde" in hab:
            log.append(f"😵 {monster['nombre']} queda aturdido 1 turno!")

    elif action == "item":
        inv = db.get_player_inventory(user_id)
        potions = [i for i in inv if isinstance(i, dict) and i.get("efecto") == "cura"]
        if not potions:
            raise HTTPException(status_code=400, detail="No tienes pociones de vida.")
        potion = potions[0]
        heal = potion.get("valor", 50)
        player["hp"] = min(player["hp_max"], player["hp"] + heal)
        inv.remove(potion)
        db.set_player_inventory(user_id, inv)
        log.append(f"🧪 Usas {potion.get('nombre','Poción')}: +{heal} HP.")

    elif action == "flee":
        flee_chance = float(db.get_config("combate_prob_huida", "0.5"))
        if random.random() < flee_chance:
            _end_combat(user_id)
            return {"status": "fled", "message": "🏃 ¡Huiste exitosamente!", "in_combat": False}
        else:
            log.append("🏃 Intentaste huir... ¡pero fallaste!")

    else:
        raise HTTPException(status_code=400, detail="Acción inválida.")

    if monster["hp"] <= 0:
        xp_gained = monster["xp"]
        oro_gained = monster["oro"]
        drops = []

        player_db = db.get_player(user_id)
        current_xp = player_db.get("experiencia", 0) + xp_gained
        current_oro = player_db.get("oro", 0) + oro_gained
        current_nivel = player_db.get("nivel", 1)
        leveled_up = False
        while current_xp >= xp_para_nivel(current_nivel + 1):
            current_nivel += 1
            leveled_up = True

        drop_chance = float(db.get_config("monstruo_prob_drop_material", "0.5"))
        if random.random() < drop_chance:
            mat = get_random_material(combat["zona_color"])
            drops.append(mat)
            inv = db.get_player_inventory(user_id)
            inv.append({"tipo": "material", "nombre": mat, "cantidad": 1})
            db.set_player_inventory(user_id, inv)

        db.update_player(user_id,
            experiencia=current_xp,
            nivel=current_nivel,
            oro=current_oro,
            hp_actual=player["hp"],
        )
        if leveled_up:
            db.add_notification(user_id, f"🎉 ¡Subiste al nivel {current_nivel}!")

        _end_combat(user_id)
        return {
            "status": "victory",
            "in_combat": False,
            "xp_gained": xp_gained,
            "oro_gained": oro_gained,
            "drops": drops,
            "nivel_nuevo": current_nivel if leveled_up else None,
            "level_up": leveled_up,
            "log": log + [f"⚔️ ¡Victoria! +{xp_gained} XP, +{oro_gained} 🪙 Oro" + (f", drops: {', '.join(drops)}" if drops else "")],
        }

    monster_dmg_data = _calc_damage(monster["atk"], player["def"])
    monster_dmg = monster_dmg_data["damage"]
    player["hp"] = max(0, player["hp"] - monster_dmg)
    crit_m = " ¡CRÍTICO!" if monster_dmg_data["critical"] else ""
    log.append(f"👾 {monster['nombre']} ataca: -{monster_dmg} HP a ti{crit_m}")

    if player["hp"] <= 0:
        player_db = db.get_player(user_id)
        faccion = player_db.get("faccion", "Alianza")
        ciudad_data = {"Alianza":{"nombre":"Ciudadela Alianza","id":1},"Imperio":{"nombre":"Ciudadela Imperio","id":12},"Sindicato":{"nombre":"Ciudadela Sindicato","id":23}}
        ciudad = ciudad_data.get(faccion, {"nombre":"Ciudadela Alianza","id":1})
        hp_max = calc_player_max_hp(player_db)
        db.update_player(user_id,
            hp_actual=int(hp_max * 0.3),
            zona_actual=ciudad["nombre"],
            zona_actual_id=ciudad["id"],
            ubicacion="ciudad",
        )
        _end_combat(user_id)
        return {
            "status": "defeated",
            "in_combat": False,
            "message": f"💀 Has sido derrotado por {monster['nombre']}. Reapareces en {ciudad['nombre']}.",
            "log": log + ["💀 ¡Has muerto! Teleportado a tu ciudad."],
        }

    combat["turno"] = turno + 1
    combat["log"] = log[-5:]
    combat["cooldowns"] = cooldowns
    _save_combat(user_id, combat)

    return {
        "status": "ongoing",
        "in_combat": True,
        "combat": combat,
        "last_log": log,
        "turno": turno + 1,
    }

@router.post("/collect")
async def collect_resources(user: dict = Depends(get_current_user)):
    user_id = user["id"]
    player = db.get_player(user_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    zona_nombre = player.get("zona_actual", "")
    zona = get_zone_by_name(zona_nombre)
    if not zona or zona["tipo"] == "ciudad":
        raise HTTPException(status_code=400, detail="Solo puedes recolectar en zonas salvajes.")

    color = zona["color"]
    stamina = player.get("stamina_actual", 0)
    stamina_cost = int(db.get_config("stamina_recolectar", "5"))
    if stamina < stamina_cost:
        raise HTTPException(status_code=400, detail=f"Stamina insuficiente ({stamina}/{stamina_cost}).")

    from game_data import MATERIALES_COMUNES
    materials_pool = MATERIALES_COMUNES.get(color, [])
    cantidad = random.randint(1, 3)
    collected = []
    inv = db.get_player_inventory(user_id)
    for _ in range(cantidad):
        mat = random.choice(materials_pool)
        collected.append(mat)
        existing = next((i for i in inv if isinstance(i,dict) and i.get("nombre") == mat and i.get("tipo") == "material"), None)
        if existing:
            existing["cantidad"] = existing.get("cantidad", 1) + 1
        else:
            inv.append({"tipo": "material", "nombre": mat, "cantidad": 1})

    xp_gained = random.randint(5, 15)
    current_xp = player.get("experiencia", 0) + xp_gained
    db.set_player_inventory(user_id, inv)
    db.update_player(user_id,
        stamina_actual=max(0, stamina - stamina_cost),
        experiencia=current_xp,
        ultima_recoleccion=datetime.now().isoformat(),
    )

    return {
        "status": "success",
        "materiales": collected,
        "xp_gained": xp_gained,
        "stamina_gastada": stamina_cost,
        "message": f"⛏️ Recolectaste: {', '.join(collected)} (+{xp_gained} XP)",
    }

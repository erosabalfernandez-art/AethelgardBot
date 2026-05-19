from fastapi import APIRouter, Depends, HTTPException
from typing import Dict
from auth import get_current_user
import database as db
from game_data import CLASES, calc_player_max_hp, calc_player_atk, calc_player_def, xp_para_nivel

router = APIRouter(prefix="/player", tags=["player"])

def build_player_response(user_id: int) -> Dict:
    player = db.get_player(user_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found. Register first with the bot.")

    nivel = player.get("nivel", 1)
    clase = player.get("clase", "vanguardista")
    xp = player.get("experiencia", 0)
    xp_next = xp_para_nivel(nivel + 1)
    xp_current_level = xp_para_nivel(nivel)
    xp_progress = max(0, xp - xp_current_level)
    xp_needed = max(1, xp_next - xp_current_level)

    hp_actual = player.get("hp_actual", 100)
    hp_max = calc_player_max_hp(player)
    stamina = player.get("stamina_actual", 100)
    stamina_max = player.get("stamina_maxima", 100)

    clase_info = CLASES.get(clase, {})

    notifs = db.get_notifications(user_id, limit=5)

    return {
        "user_id": user_id,
        "nombre": player.get("nombre_personaje", "Aventurero"),
        "clase": clase,
        "clase_nombre": clase_info.get("nombre", clase),
        "clase_emoji": clase_info.get("emoji", "⚔️"),
        "nivel": nivel,
        "experiencia": xp,
        "xp_siguiente_nivel": xp_next,
        "xp_progreso": xp_progress,
        "xp_necesaria": xp_needed,
        "xp_pct": min(100, int(xp_progress / xp_needed * 100)),
        "hp_actual": min(hp_actual, hp_max),
        "hp_max": hp_max,
        "hp_pct": min(100, int(min(hp_actual, hp_max) / hp_max * 100)) if hp_max else 100,
        "stamina_actual": min(stamina, stamina_max),
        "stamina_max": stamina_max,
        "stamina_pct": min(100, int(min(stamina, stamina_max) / stamina_max * 100)) if stamina_max else 100,
        "oro": player.get("oro", 0),
        "eternium": player.get("eternium", 0),
        "creditos": player.get("creditos_vacio", 0),
        "reputacion": player.get("reputacion", 0),
        "faccion": player.get("faccion", "Alianza"),
        "zona_actual": player.get("zona_actual", "Ciudadela Alianza"),
        "zona_actual_id": player.get("zona_actual_id", 1),
        "ubicacion": player.get("ubicacion", "ciudad"),
        "atk": calc_player_atk(player),
        "def": calc_player_def(player),
        "titulo": player.get("titulo_activo"),
        "notificaciones_pendientes": len(notifs),
        "reencarnaciones": player.get("reencarnaciones", 0),
    }

@router.get("/me")
async def get_me(user: dict = Depends(get_current_user)):
    user_id = user["id"]
    return build_player_response(user_id)

@router.get("/notifications")
async def get_notifications(user: dict = Depends(get_current_user)):
    user_id = user["id"]
    notifs = db.get_notifications(user_id, limit=30)
    db.mark_notifications_read(user_id)
    return {"notifications": notifs}

@router.get("/stats")
async def get_detailed_stats(user: dict = Depends(get_current_user)):
    user_id = user["id"]
    player = db.get_player(user_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    from game_data import HABILIDADES
    clase = player.get("clase", "vanguardista")
    habs = HABILIDADES.get(clase, [])

    guild = db.get_guild_of_player(user_id)

    return {
        "atk": calc_player_atk(player),
        "def": calc_player_def(player),
        "hp_max": calc_player_max_hp(player),
        "clase": clase,
        "subclase": player.get("subclase"),
        "habilidades": habs,
        "gremio": guild["nombre"] if guild else None,
        "gremio_rango": guild["rango"] if guild else None,
        "reclutas": player.get("reclutas_completados", 0),
        "mazmorras_hoy": {
            "azul": player.get("mazmorras_azul_hoy", 0),
            "amarilla": player.get("mazmorras_amarilla_hoy", 0),
            "roja": player.get("mazmorras_roja_hoy", 0),
            "negra": player.get("mazmorras_negra_hoy", 0),
        },
        "codigo_invitacion": player.get("codigo_invitacion", ""),
    }

@router.get("/guild")
async def get_my_guild(user: dict = Depends(get_current_user)):
    user_id = user["id"]
    guild = db.get_guild_of_player(user_id)
    if not guild:
        return {"guild": None}
    members = db.get_guild_members(guild["id"])
    import json
    return {
        "guild": {
            "id": guild["id"],
            "nombre": guild["nombre"],
            "tag": guild["tag"],
            "faccion": guild["faccion"],
            "nivel": guild["nivel"],
            "banco_oro": guild["banco_oro"],
            "banco_eternium": guild["banco_eternium"],
            "energia_nexo": guild["energia_nexo"],
            "rango_propio": guild["rango"],
            "miembros": members,
            "territorios": json.loads(guild.get("territorios_controlados", "[]")),
        }
    }

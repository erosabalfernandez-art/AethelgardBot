import json
import random
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from auth import get_current_user
import database as db
from game_data import (
    calc_player_atk, calc_player_def, calc_player_max_hp,
    xp_para_nivel, HABILIDADES
)

router = APIRouter(prefix="/dungeon", tags=["dungeon"])

MAZMORRAS_DISPONIBLES = [
    {"id":"maz_azul_normal","nombre":"Cripta del Bosque","color":"azul","dificultad":"Normal","nivel_req":1,"coste_oro":200,"xp_base":200,"oro_base":150,"eternium":(2,5),"emoji":"🌲","descripcion":"Mazmorra introductoria en el corazón del bosque. Monstruos débiles pero letales en grupo.","salas":5,"jefe":"Corruptor del Bosque"},
    {"id":"maz_azul_dificil","nombre":"Cripta Profunda","color":"azul","dificultad":"Difícil","nivel_req":5,"coste_oro":400,"xp_base":400,"oro_base":300,"eternium":(6,10),"emoji":"💀","descripcion":"Versión más oscura de la cripta. Monstruos más resistentes y jefe potenciado.","salas":7,"jefe":"El Devorador de Almas"},
    {"id":"maz_amarilla_normal","nombre":"Ruinas Imperiales","color":"amarilla","dificultad":"Normal","nivel_req":10,"coste_oro":500,"xp_base":500,"oro_base":400,"eternium":(5,10),"emoji":"🏚️","descripcion":"Ruinas de una fortaleza conquistada. Muertos vivientes y trampas mortales.","salas":6,"jefe":"General Espectral"},
    {"id":"maz_amarilla_dificil","nombre":"Torre del Necromante","color":"amarilla","dificultad":"Difícil","nivel_req":15,"coste_oro":800,"xp_base":800,"oro_base":700,"eternium":(12,20),"emoji":"🗼","descripcion":"La torre del necromante más poderoso de la región. Solo para héroes experimentados.","salas":8,"jefe":"Archlich Supremo"},
    {"id":"maz_roja_normal","nombre":"Caverna Ígnea","color":"roja","dificultad":"Normal","nivel_req":20,"coste_oro":1000,"xp_base":1200,"oro_base":900,"eternium":(10,20),"emoji":"🔥","descripcion":"Caverna volcánica habitada por demonios y elementales de fuego.","salas":7,"jefe":"Señor del Fuego"},
    {"id":"maz_roja_dificil","nombre":"Abismo Demoníaco","color":"roja","dificultad":"Difícil","nivel_req":30,"coste_oro":1800,"xp_base":2000,"oro_base":1600,"eternium":(25,40),"emoji":"😈","descripcion":"Puerta al inframundo. Demonios de alto rango y un archidemon aguardan.","salas":10,"jefe":"Archidemon Raz'voth"},
    {"id":"maz_negra_normal","nombre":"Sepulcro Eterno","color":"negra","dificultad":"Normal","nivel_req":40,"coste_oro":2500,"xp_base":3500,"oro_base":2800,"eternium":(20,40),"emoji":"⚰️","descripcion":"Mausoleo de reyes olvidados. Las almas más oscuras duermen aquí... o durmieron.","salas":9,"jefe":"Rey Liche Inmortal"},
    {"id":"maz_negra_dificil","nombre":"Nexo del Caos","color":"negra","dificultad":"Difícil","nivel_req":60,"coste_oro":5000,"xp_base":6000,"oro_base":5000,"eternium":(50,80),"emoji":"🌀","descripcion":"El punto donde el caos primordial filtra al mundo. Solo los más fuertes sobreviven.","salas":12,"jefe":"Avatar del Caos Supremo"},
]

_active_dungeons: dict = {}

class PartyAction(BaseModel):
    accion: str
    target_user_id: Optional[int] = None

class DungeonStart(BaseModel):
    dungeon_id: str
    solo: bool = False

@router.get("/list")
async def list_dungeons(user: dict = Depends(get_current_user)):
    user_id = user["id"]
    player = db.get_player(user_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    nivel = player.get("nivel", 1)
    limite = {
        "azul": player.get("mazmorras_azul_hoy", 0),
        "amarilla": player.get("mazmorras_amarilla_hoy", 0),
        "roja": player.get("mazmorras_roja_hoy", 0),
        "negra": player.get("mazmorras_negra_hoy", 0),
    }
    limite_diario = int(db.get_config("mazmorra_limite_diario", "2"))

    mazmorras_data = []
    for maz in MAZMORRAS_DISPONIBLES:
        color = maz["color"]
        usadas = limite.get(color, 0)
        mazmorras_data.append({
            **maz,
            "accesible": nivel >= maz["nivel_req"],
            "disponibles_hoy": max(0, limite_diario - usadas),
            "limite_diario": limite_diario,
        })

    party = db.get_party_of_player(user_id)
    active_parties = db.get_active_parties()

    return {
        "mazmorras": mazmorras_data,
        "mi_grupo": party,
        "grupos_disponibles": active_parties[:10],
    }

@router.post("/party/create")
async def create_party(user: dict = Depends(get_current_user)):
    user_id = user["id"]
    if db.get_party_of_player(user_id):
        raise HTTPException(status_code=400, detail="Ya estás en un grupo.")
    conn = db.get_conn()
    c = conn.cursor()
    c.execute(
        "INSERT INTO partys (lider_id, miembros, estado) VALUES (?, ?, 'formando')",
        (user_id, json.dumps([user_id]))
    )
    party_id = c.lastrowid
    conn.commit()
    conn.close()
    return {"status": "created", "party_id": party_id, "message": "✅ Grupo creado. Comparte tu ID para que otros se unan."}

@router.post("/party/join/{party_id}")
async def join_party(party_id: int, user: dict = Depends(get_current_user)):
    user_id = user["id"]
    if db.get_party_of_player(user_id):
        raise HTTPException(status_code=400, detail="Ya estás en un grupo.")
    conn = db.get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM partys WHERE id = ? AND estado = 'formando'", (party_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Grupo no encontrado o ya inició.")
    party = dict(row)
    members = json.loads(party.get("miembros", "[]"))
    if len(members) >= party.get("tamanio_max", 5):
        conn.close()
        raise HTTPException(status_code=400, detail="El grupo está lleno.")
    if user_id in members:
        conn.close()
        raise HTTPException(status_code=400, detail="Ya eres miembro de este grupo.")
    members.append(user_id)
    c.execute("UPDATE partys SET miembros = ? WHERE id = ?", (json.dumps(members), party_id))
    conn.commit()
    conn.close()
    return {"status": "joined", "party_id": party_id, "message": "✅ Te uniste al grupo."}

@router.post("/start")
async def start_dungeon(req: DungeonStart, user: dict = Depends(get_current_user)):
    user_id = user["id"]
    player = db.get_player(user_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    maz = next((m for m in MAZMORRAS_DISPONIBLES if m["id"] == req.dungeon_id), None)
    if not maz:
        raise HTTPException(status_code=404, detail="Mazmorra no encontrada.")

    nivel = player.get("nivel", 1)
    if nivel < maz["nivel_req"]:
        raise HTTPException(status_code=400, detail=f"Nivel mínimo requerido: {maz['nivel_req']}. Tu nivel: {nivel}")

    color = maz["color"]
    campo_hoy = f"mazmorras_{color}_hoy"
    usadas = player.get(campo_hoy, 0)
    limite = int(db.get_config("mazmorra_limite_diario", "2"))
    if usadas >= limite:
        raise HTTPException(status_code=400, detail=f"Has alcanzado el límite diario de {limite} mazmorras {color}.")

    coste = maz["coste_oro"]
    if player.get("oro", 0) < coste:
        raise HTTPException(status_code=400, detail=f"Necesitas {coste:,} 🪙 Oro para entrar. Tienes: {player.get('oro', 0):,}")

    db.update_player(user_id, oro=player["oro"] - coste, **{campo_hoy: usadas + 1})

    hp_max = calc_player_max_hp(player)
    scale = 1.0 + (nivel - 1) * 0.1

    salas_superadas = 0
    total_dmg_recibido = 0
    hp_actual = min(player.get("hp_actual", hp_max), hp_max)
    log = [f"🌀 Entrando a **{maz['nombre']}** ({maz['dificultad']})", f"💰 Coste de entrada: {coste:,} Oro"]
    xp_total = 0
    oro_total = 0

    player_atk = calc_player_atk(player)
    player_def = calc_player_def(player)

    for sala in range(1, maz["salas"] + 1):
        if hp_actual <= 0:
            break
        is_boss = sala == maz["salas"]
        hp_enemy = int((150 if is_boss else 80) * scale * sala * 0.5)
        atk_enemy = int((35 if is_boss else 18) * scale)
        def_enemy = int((12 if is_boss else 5) * scale)
        enemy_name = maz["jefe"] if is_boss else f"Guardián Sala {sala}"

        rounds = 0
        while hp_enemy > 0 and hp_actual > 0 and rounds < 20:
            p_dmg = max(1, player_atk - int(def_enemy * 0.4) + random.randint(-3, 5))
            if random.random() < 0.15:
                p_dmg = int(p_dmg * 2)
            hp_enemy -= p_dmg
            if hp_enemy <= 0:
                break
            e_dmg = max(1, atk_enemy - int(player_def * 0.4) + random.randint(-2, 4))
            hp_actual -= e_dmg
            total_dmg_recibido += e_dmg
            rounds += 1

        if hp_actual > 0:
            salas_superadas += 1
            sala_xp = int(maz["xp_base"] / maz["salas"] * (1.5 if is_boss else 1.0))
            sala_oro = int(maz["oro_base"] / maz["salas"] * (1.5 if is_boss else 1.0))
            xp_total += sala_xp
            oro_total += sala_oro
            log.append(f"{'🏆 [JEFE]' if is_boss else f'⚔️ Sala {sala}'}: {enemy_name} derrotado — +{sala_xp} XP, +{sala_oro} Oro")
        else:
            log.append(f"💀 Caíste en la sala {sala} ante {enemy_name}.")
            break

    success = salas_superadas == maz["salas"]
    et_min, et_max = maz["eternium"]
    et_ganado = random.randint(et_min, et_max) if success else random.randint(0, et_min // 2)

    current_xp = player.get("experiencia", 0) + xp_total
    current_nivel = player.get("nivel", 1)
    leveled_up = False
    while current_xp >= xp_para_nivel(current_nivel + 1):
        current_nivel += 1
        leveled_up = True

    hp_final = max(int(hp_max * 0.15), hp_actual)
    db.update_player(user_id,
        experiencia=current_xp,
        nivel=current_nivel,
        oro=player.get("oro", 0) - coste + oro_total,
        eternium=player.get("eternium", 0) + et_ganado,
        hp_actual=hp_final,
    )

    if leveled_up:
        db.add_notification(user_id, f"🎉 ¡Subiste al nivel {current_nivel} tras la mazmorra!")

    resultado_txt = "🏆 ¡COMPLETADA!" if success else f"💀 Derrotado en sala {salas_superadas + 1}/{maz['salas']}"
    return {
        "status": "completed" if success else "failed",
        "resultado": resultado_txt,
        "salas_superadas": salas_superadas,
        "total_salas": maz["salas"],
        "xp_ganada": xp_total,
        "oro_ganado": oro_total - coste,
        "eternium_ganado": et_ganado,
        "level_up": leveled_up,
        "nivel_nuevo": current_nivel if leveled_up else None,
        "hp_final": hp_final,
        "hp_max": hp_max,
        "log": log,
    }

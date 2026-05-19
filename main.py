import os
import sys
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from dotenv import load_dotenv

load_dotenv()

import auth
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
if BOT_TOKEN:
    auth.set_bot_token(BOT_TOKEN)
else:
    print("⚠️  BOT_TOKEN not set. Auth validation will fail in production.")

from routers import player, map, travel, combat, inventory, city, dungeon

app = FastAPI(title="Aethelgard Mini App API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(player.router, prefix="/api")
app.include_router(map.router, prefix="/api")
app.include_router(travel.router, prefix="/api")
app.include_router(combat.router, prefix="/api")
app.include_router(inventory.router, prefix="/api")
app.include_router(city.router, prefix="/api")
app.include_router(dungeon.router, prefix="/api")

@app.get("/api/health")
async def health():
    return {"status": "ok", "game": "Aethelgard", "version": "1.0.0"}

STATIC_DIR = Path(__file__).parent.parent / "frontend" / "dist"
if STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(STATIC_DIR / "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        index = STATIC_DIR / "index.html"
        if index.exists():
            return FileResponse(str(index))
        return JSONResponse({"error": "Frontend not built"}, status_code=404)
else:
    @app.get("/")
    async def root():
        return {"message": "Aethelgard API running. Frontend not built yet."}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)

import hashlib
import hmac
import json
import time
from urllib.parse import unquote, parse_qsl
from fastapi import HTTPException, Header, Request
from typing import Optional

BOT_TOKEN: str = ""

def set_bot_token(token: str):
    global BOT_TOKEN
    BOT_TOKEN = token

def validate_init_data(init_data: str) -> dict:
    if not init_data:
        raise HTTPException(status_code=401, detail="No init_data provided")
    if not BOT_TOKEN:
        raise HTTPException(status_code=500, detail="Bot token not configured")

    parsed = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = parsed.pop("hash", None)
    if not received_hash:
        raise HTTPException(status_code=401, detail="No hash in init_data")

    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(parsed.items())
    )
    secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    expected_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(received_hash, expected_hash):
        raise HTTPException(status_code=401, detail="Invalid hash — data tampered")

    auth_date = int(parsed.get("auth_date", 0))
    if time.time() - auth_date > 86400:
        raise HTTPException(status_code=401, detail="Init data expired")

    user_data = json.loads(parsed.get("user", "{}"))
    return user_data

async def get_current_user(x_init_data: Optional[str] = Header(None)) -> dict:
    if not x_init_data:
        raise HTTPException(status_code=401, detail="Missing X-Init-Data header")
    return validate_init_data(x_init_data)

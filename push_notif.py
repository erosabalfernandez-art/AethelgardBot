#!/usr/bin/env python3
"""
push_notif.py — Envía un mensaje a Telegram sin levantar el bot completo.
Uso: python3 push_notif.py <user_id> "<mensaje>"
El agente IA lo llama desde bash para notificar al superadmin cuando arregla un reporte.
"""
import sys
import os
import urllib.request
import urllib.parse
import json

def enviar(user_id: int, mensaje: str) -> bool:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        print("ERROR: TELEGRAM_BOT_TOKEN no configurado", file=sys.stderr)
        return False
    url  = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id":    user_id,
        "text":       mensaje,
        "parse_mode": "HTML",
    }).encode()
    try:
        with urllib.request.urlopen(url, data=data, timeout=10) as r:
            resp = json.loads(r.read())
            return resp.get("ok", False)
    except Exception as e:
        print(f"ERROR al enviar: {e}", file=sys.stderr)
        return False

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Uso: python3 push_notif.py <user_id> '<mensaje>'")
        sys.exit(1)
    uid = int(sys.argv[1])
    msg = sys.argv[2]
    ok  = enviar(uid, msg)
    print("✅ Enviado" if ok else "❌ Falló")
    sys.exit(0 if ok else 1)

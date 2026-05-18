#!/usr/bin/env python3
"""
telegram_queue.py — Rate limiter global para mensajes salientes de Telegram.

Respeta los límites de la API:
  - 30 mensajes/segundo en total
  - 1 mensaje/segundo al mismo usuario
  - Retry automático en errores 429 (RetryAfter)

Uso desde cualquier módulo:
    from telegram_queue import rate_limiter
    await rate_limiter.send(bot, chat_id, texto, parse_mode="HTML")
    await rate_limiter.edit(bot, chat_id, message_id, texto)
"""

import asyncio
import time
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)

# ── Configuración leída desde DB (activable/desactivable por admin) ────────────
import sqlite3

DB_PATH = "aethelgard.db"

def _cfg(clave: str, default: str = "1") -> str:
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT valor FROM config_bot WHERE clave = ?", (clave,))
        row = c.fetchone()
        conn.close()
        return row[0] if row else default
    except Exception:
        return default


class TelegramRateLimiter:
    """
    Cola de envío que respeta los límites de la API de Telegram.
    Thread-safe, compatible con asyncio.
    """

    def __init__(self, rate_global: float = 25.0, rate_por_usuario: float = 1.0):
        self._rate_global = rate_global
        self._min_interval_global = 1.0 / rate_global
        self._min_interval_usuario = 1.0 / rate_por_usuario

        self._last_global = 0.0
        self._last_usuario: dict[int, float] = defaultdict(float)

        self._lock_global = asyncio.Lock()
        self._locks_usuario: dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)

    def _activo(self) -> bool:
        return _cfg("rate_limiter_activo", "1") == "1"

    async def _esperar_global(self):
        async with self._lock_global:
            now = time.monotonic()
            espera = self._min_interval_global - (now - self._last_global)
            if espera > 0:
                await asyncio.sleep(espera)
            self._last_global = time.monotonic()

    async def _esperar_usuario(self, chat_id: int):
        async with self._locks_usuario[chat_id]:
            now = time.monotonic()
            espera = self._min_interval_usuario - (now - self._last_usuario[chat_id])
            if espera > 0:
                await asyncio.sleep(espera)
            self._last_usuario[chat_id] = time.monotonic()

    async def send(self, bot, chat_id: int, text: str, **kwargs) -> object:
        if not self._activo():
            return await bot.send_message(chat_id=chat_id, text=text, **kwargs)

        await self._esperar_global()
        await self._esperar_usuario(chat_id)

        for intento in range(3):
            try:
                result = await bot.send_message(chat_id=chat_id, text=text, **kwargs)
                return result
            except Exception as e:
                from telegram.error import RetryAfter, Forbidden, BadRequest
                if isinstance(e, RetryAfter):
                    espera = e.retry_after + 1
                    logger.warning(f"RetryAfter {espera}s para chat {chat_id}")
                    await asyncio.sleep(espera)
                    continue
                if isinstance(e, Forbidden):
                    logger.debug(f"Usuario {chat_id} bloqueó el bot — ignorando.")
                    return None
                if isinstance(e, BadRequest) and "chat not found" in str(e).lower():
                    return None
                if intento == 2:
                    logger.error(f"Error al enviar a {chat_id} tras 3 intentos: {e}")
                    raise
                await asyncio.sleep(0.5 * (intento + 1))
        return None

    async def edit(self, bot, chat_id: int, message_id: int, text: str, **kwargs) -> object:
        if not self._activo():
            return await bot.edit_message_text(
                chat_id=chat_id, message_id=message_id, text=text, **kwargs
            )
        await self._esperar_global()
        try:
            return await bot.edit_message_text(
                chat_id=chat_id, message_id=message_id, text=text, **kwargs
            )
        except Exception as e:
            from telegram.error import RetryAfter, BadRequest
            if isinstance(e, RetryAfter):
                await asyncio.sleep(e.retry_after + 1)
                return await bot.edit_message_text(
                    chat_id=chat_id, message_id=message_id, text=text, **kwargs
                )
            if isinstance(e, BadRequest) and "message is not modified" in str(e).lower():
                return None
            raise

    async def broadcast(self, bot, user_ids: list[int], text: str, **kwargs):
        """Envía el mismo mensaje a una lista de usuarios respetando el rate limit."""
        enviados = 0
        for uid in user_ids:
            result = await self.send(bot, uid, text, **kwargs)
            if result:
                enviados += 1
        return enviados


# Singleton global
rate_limiter = TelegramRateLimiter(rate_global=25.0, rate_por_usuario=1.0)

#!/usr/bin/env python3
# rescate.py - Comando /pagar_rescate para limpiar el estado "marcado"
import db_helper
import economia
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler

COSTO_RESCATE_ORO = 500  # Ajusta este valor según tu balance

async def cmd_pagar_rescate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    jug = db_helper.obtener_jugador(user_id)
    if not jug:
        await update.effective_message.reply_text("❌ No estás registrado. Usa /start para comenzar.")
        return
    if not db_helper.esta_marcado(user_id):
        await update.effective_message.reply_text("✅ No estás marcado. No necesitas pagar rescate.")
        return
    oro = jug.get("oro", 0)
    if oro >= COSTO_RESCATE_ORO:
        # Descontar oro
        exito = economia.modificar_saldo(user_id, "oro", -COSTO_RESCATE_ORO, "Pago de rescate")
        if not exito:
            await update.effective_message.reply_text("❌ Error al procesar el pago. Intenta de nuevo.")
            return
        # Desmarcar al jugador
        db_helper.desmarcar_jugador(user_id)  # Se espera que exista esta función
        await update.effective_message.reply_text("✅ Has pagado el rescate. ¡Ya no estás marcado!")
    else:
        await update.effective_message.reply_text(f"❌ No tienes suficiente oro. Necesitas {COSTO_RESCATE_ORO}. Tienes {oro}.")

def registrar_handlers(app):
    app.add_handler(CommandHandler("pagar_rescate", cmd_pagar_rescate))
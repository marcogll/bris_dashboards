"""Views y utilidades para integración del bot de Telegram con Django."""

import json
import logging

from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def webhook(request):
    """Recibe updates del bot de Telegram."""
    try:
        update = json.loads(request.body)
    except Exception as e:
        logger.error("Error parsing Telegram update: %s", e)
        return HttpResponseBadRequest("Invalid JSON")

    message = update.get("message")
    if message:
        chat_id = message["chat"]["id"]
        text = message.get("text", "")
        logger.info("Telegram message from %s: %s", chat_id, text)

    return HttpResponse("ok")


def enviar_notificacion_usuario(chat_id, mensaje):
    """Envía una notificación a un usuario de Telegram."""
    from django.conf import settings

    try:
        from telegram import Bot

        token = settings.TELEGRAM_BOT_TOKEN
        if not token:
            return False
        bot = Bot(token=token)
        bot.send_message(chat_id=chat_id, text=mensaje)
        return True
    except Exception as e:
        logger.error("Error sending Telegram notification: %s", e)
        return False

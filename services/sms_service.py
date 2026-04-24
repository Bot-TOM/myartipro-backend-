import logging
import os

import httpx

logger = logging.getLogger(__name__)

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER", "")


def _normaliser_numero(telephone: str) -> str:
    n = telephone.strip().replace(" ", "").replace(".", "").replace("-", "")
    if n.startswith("0"):
        return "+33" + n[1:]
    if not n.startswith("+"):
        return "+33" + n
    return n


async def envoyer_sms(to: str, message: str) -> bool:
    if not all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER]):
        logger.warning("[sms] Twilio non configuré (TWILIO_ACCOUNT_SID / AUTH_TOKEN / FROM_NUMBER manquants)")
        return False

    numero = _normaliser_numero(to)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json",
                auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN),
                data={"From": TWILIO_FROM_NUMBER, "To": numero, "Body": message},
            )
            resp.raise_for_status()
            logger.info("[sms] envoyé à %s", numero)
            return True
    except Exception as e:
        logger.warning("[sms] erreur envoi à %s : %s", numero, e)
        return False

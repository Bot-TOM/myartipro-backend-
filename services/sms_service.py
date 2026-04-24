import logging
import os

import httpx

logger = logging.getLogger(__name__)

BREVO_API_KEY = os.getenv("BREVO_API_KEY", "")
SMS_SENDER = "MyArtipro"


def _normaliser_numero(telephone: str) -> str:
    n = telephone.strip().replace(" ", "").replace(".", "").replace("-", "")
    if n.startswith("0"):
        return "+33" + n[1:]
    if not n.startswith("+"):
        return "+33" + n
    return n


async def envoyer_sms(to: str, message: str) -> tuple[bool, str]:
    if not BREVO_API_KEY:
        return False, "BREVO_API_KEY non configuré sur Railway"

    numero = _normaliser_numero(to)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                "https://api.brevo.com/v3/transactionalSMS/sms",
                headers={"api-key": BREVO_API_KEY, "Content-Type": "application/json"},
                json={"sender": SMS_SENDER, "recipient": numero, "content": message},
            )
            if resp.status_code >= 400:
                detail = resp.text[:200]
                logger.warning("[sms] erreur Brevo %s : %s", resp.status_code, detail)
                return False, f"Brevo erreur {resp.status_code} : {detail}"
            logger.info("[sms] envoyé à %s", numero)
            return True, ""
    except Exception as e:
        logger.warning("[sms] erreur envoi à %s : %s", numero, e)
        return False, str(e)

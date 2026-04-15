import os
import stripe

stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")


def creer_checkout_session(
    facture_id: str,
    facture_numero: str,
    montant_ttc: float,
    client_email: str,
    plombier_nom: str,
) -> str:
    """Crée une session Stripe Checkout et retourne l'URL de paiement."""
    app_url = os.getenv("APP_URL", "http://localhost:5173")

    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        mode="payment",
        customer_email=client_email,
        line_items=[
            {
                "price_data": {
                    "currency": "eur",
                    "unit_amount": int(round(montant_ttc * 100)),
                    "product_data": {
                        "name": f"Facture {facture_numero}",
                        "description": f"Paiement à {plombier_nom}",
                    },
                },
                "quantity": 1,
            }
        ],
        metadata={
            "facture_id": facture_id,
            "facture_numero": facture_numero,
        },
        success_url=f"{app_url}/factures?paiement=ok",
        cancel_url=f"{app_url}/factures?paiement=annule",
    )

    return session.url


def verifier_webhook(payload: bytes, sig_header: str) -> dict:
    """Vérifie et décode un événement webhook Stripe."""
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    return event

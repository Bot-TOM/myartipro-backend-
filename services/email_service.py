import resend
import os


def _init_resend():
    api_key = os.getenv("RESEND_API_KEY", "")
    if not api_key:
        raise Exception("RESEND_API_KEY non configuree dans .env")
    resend.api_key = api_key


def envoyer_devis_email(
    client_email: str,
    client_nom: str,
    plombier_nom: str,
    devis_numero: str,
    devis_id: str,
):
    """Envoie un email au client avec le lien vers le devis PDF."""
    _init_resend()
    # Lien public vers le PDF du devis (sans auth requise)
    api_url = os.getenv("API_URL", "http://localhost:8000")
    pdf_link = f"{api_url}/pdf/public/devis/{devis_id}"

    try:
        result = resend.Emails.send(
            {
                "from": os.getenv("EMAIL_FROM", "MyArtipro <onboarding@resend.dev>"),
                "to": client_email,
                "subject": f"Devis {devis_numero} — {plombier_nom}",
                "html": f"""
<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px">
    <h2 style="color:#2563eb">Bonjour {client_nom},</h2>
    <p>{plombier_nom} vous a envoye le devis <strong>{devis_numero}</strong>.</p>
    <p>Vous pouvez le consulter en cliquant sur le lien ci-dessous :</p>
    <p style="margin:24px 0">
        <a href="{pdf_link}"
           style="background:#2563eb;color:#fff;padding:12px 28px;
                  text-decoration:none;border-radius:6px;font-weight:bold">
            Telecharger le devis PDF
        </a>
    </p>
    <p>N'hesitez pas a repondre a cet email pour toute question.</p>
    <p>Cordialement,<br><strong>{plombier_nom}</strong></p>
    <hr style="border:none;border-top:1px solid #eee;margin:24px 0">
    <p style="font-size:12px;color:#999">
        Envoye via MyArtipro
    </p>
</div>
                """,
            }
        )
        print(f"[Email] Devis {devis_numero} envoye a {client_email} — ID: {result}")
        return result
    except Exception as e:
        print(f"[Email] ERREUR envoi devis {devis_numero} a {client_email}: {e}")
        raise Exception(f"Echec envoi email: {str(e)}")


def envoyer_relance_email(
    client_email: str,
    client_nom: str,
    plombier_nom: str,
    devis_numero: str,
    jours_depuis_envoi: int,
):
    """Envoie un email de relance pour un devis sans reponse."""
    _init_resend()

    try:
        result = resend.Emails.send(
            {
                "from": os.getenv("EMAIL_FROM", "MyArtipro <onboarding@resend.dev>"),
                "to": client_email,
                "subject": f"Relance — Devis {devis_numero} ({plombier_nom})",
                "html": f"""
<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px">
    <h2 style="color:#2563eb">Bonjour {client_nom},</h2>
    <p>Nous nous permettons de revenir vers vous concernant le devis
    <strong>{devis_numero}</strong> envoye il y a {jours_depuis_envoi} jours
    par {plombier_nom}.</p>
    <p>Si vous avez des questions ou souhaitez y donner suite,
    n'hesitez pas a nous contacter.</p>
    <p>Cordialement,<br><strong>{plombier_nom}</strong></p>
    <hr style="border:none;border-top:1px solid #eee;margin:24px 0">
    <p style="font-size:12px;color:#999">
        Envoye via MyArtipro
    </p>
</div>
                """,
            }
        )
        print(f"[Email] Relance {devis_numero} envoyee a {client_email} — ID: {result}")
        return result
    except Exception as e:
        print(f"[Email] ERREUR relance {devis_numero} a {client_email}: {e}")
        raise Exception(f"Echec envoi relance: {str(e)}")

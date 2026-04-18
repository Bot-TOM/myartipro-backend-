import resend
import os


def _init_resend():
    api_key = os.getenv("RESEND_API_KEY", "")
    if not api_key:
        raise Exception("RESEND_API_KEY non configuree dans .env")
    resend.api_key = api_key


def _from_with_artisan(artisan_nom: str) -> str:
    """
    Construit l'en-tête "From" affiche par le client.
    Format : "{Nom Artisan} via MyArtipro <contact@myartipro.fr>"
    Respecte EMAIL_FROM en fallback si variable non definie.
    """
    base = os.getenv("EMAIL_FROM", "MyArtipro <onboarding@resend.dev>")
    # Si EMAIL_FROM contient deja un format "Nom <adresse>", on en extrait l'adresse.
    if "<" in base and ">" in base:
        adresse = base.split("<", 1)[1].rsplit(">", 1)[0]
    else:
        adresse = base
    nom = (artisan_nom or "").strip() or "MyArtipro"
    # Echappe les guillemets pour rester un header RFC 5322 valide.
    nom_safe = nom.replace('"', '')
    return f'"{nom_safe} via MyArtipro" <{adresse}>'


def _signature_html(
    artisan_nom: str,
    artisan_email: str = "",
    artisan_telephone: str = "",
) -> str:
    """Bloc signature HTML injecte en fin de chaque email."""
    lignes = [f"<strong>{artisan_nom}</strong>"]
    if artisan_telephone:
        lignes.append(f'Tel. : <a href="tel:{artisan_telephone}" style="color:#374151;text-decoration:none">{artisan_telephone}</a>')
    if artisan_email:
        lignes.append(f'Email : <a href="mailto:{artisan_email}" style="color:#374151;text-decoration:none">{artisan_email}</a>')
    return (
        '<p style="margin:16px 0 0 0;line-height:1.5">Cordialement,<br>'
        + "<br>".join(lignes)
        + "</p>"
    )


def _send(payload: dict, reply_to: str = ""):
    """Envoi Resend avec reply_to optionnel."""
    if reply_to:
        payload["reply_to"] = reply_to
    return resend.Emails.send(payload)


def envoyer_devis_email(
    client_email: str,
    client_nom: str,
    artisan_nom: str,
    devis_numero: str,
    devis_id: str,
    acceptance_token: str = "",
    artisan_email: str = "",
    artisan_telephone: str = "",
):
    """Envoie un email au client avec le lien vers le devis + boutons accepter/refuser."""
    _init_resend()
    api_url = os.getenv("API_URL", "http://localhost:8000")
    app_url = os.getenv("APP_URL", "http://localhost:5173")
    pdf_link = f"{api_url}/pdf/public/devis/{devis_id}"
    accept_link = f"{app_url}/devis/public/{acceptance_token}" if acceptance_token else pdf_link
    signature = _signature_html(artisan_nom, artisan_email, artisan_telephone)

    try:
        result = _send(
            {
                "from": _from_with_artisan(artisan_nom),
                "to": client_email,
                "subject": f"Devis {devis_numero} — {artisan_nom}",
                "html": f"""
<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px">
    <h2 style="color:#2563eb">Bonjour {client_nom},</h2>
    <p>{artisan_nom} vous a envoye le devis <strong>{devis_numero}</strong>.</p>
    <p>Consultez-le et donnez votre reponse en cliquant ci-dessous :</p>
    <p style="margin:24px 0">
        <a href="{accept_link}"
           style="background:#2563eb;color:#fff;padding:12px 28px;
                  text-decoration:none;border-radius:6px;font-weight:bold">
            Voir le devis
        </a>
        &nbsp;&nbsp;
        <a href="{pdf_link}"
           style="background:#f3f4f6;color:#374151;padding:12px 28px;
                  text-decoration:none;border-radius:6px;font-weight:bold">
            Telecharger le PDF
        </a>
    </p>
    <p>N'hesitez pas a repondre a cet email pour toute question.</p>
    {signature}
    <hr style="border:none;border-top:1px solid #eee;margin:24px 0">
    <p style="font-size:12px;color:#999">Envoye via MyArtipro</p>
</div>
                """,
            },
            reply_to=artisan_email,
        )
        print(f"[Email] Devis {devis_numero} envoye a {client_email} — ID: {result}")
        return result
    except Exception as e:
        print(f"[Email] ERREUR envoi devis {devis_numero} a {client_email}: {e}")
        raise Exception(f"Echec envoi email: {str(e)}")


def envoyer_relance_email(
    client_email: str,
    client_nom: str,
    artisan_nom: str,
    devis_numero: str,
    jours_depuis_envoi: int,
    artisan_email: str = "",
    artisan_telephone: str = "",
):
    """Envoie un email de relance pour un devis sans reponse."""
    _init_resend()
    signature = _signature_html(artisan_nom, artisan_email, artisan_telephone)

    try:
        result = _send(
            {
                "from": _from_with_artisan(artisan_nom),
                "to": client_email,
                "subject": f"Relance — Devis {devis_numero} ({artisan_nom})",
                "html": f"""
<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px">
    <h2 style="color:#2563eb">Bonjour {client_nom},</h2>
    <p>Nous nous permettons de revenir vers vous concernant le devis
    <strong>{devis_numero}</strong> envoye il y a {jours_depuis_envoi} jours
    par {artisan_nom}.</p>
    <p>Si vous avez des questions ou souhaitez y donner suite,
    n'hesitez pas a nous contacter.</p>
    {signature}
    <hr style="border:none;border-top:1px solid #eee;margin:24px 0">
    <p style="font-size:12px;color:#999">Envoye via MyArtipro</p>
</div>
                """,
            },
            reply_to=artisan_email,
        )
        print(f"[Email] Relance {devis_numero} envoyee a {client_email} — ID: {result}")
        return result
    except Exception as e:
        print(f"[Email] ERREUR relance {devis_numero} a {client_email}: {e}")
        raise Exception(f"Echec envoi relance: {str(e)}")


# ---------------------------------------------------------------------------
# Relances factures impayées (paliers J+30, J+45, J+60)
# ---------------------------------------------------------------------------

_RELANCE_FACTURE_PALIERS = {
    1: {
        "ton": "cordial",
        "objet": "Rappel",
        "intro": (
            "Sauf erreur de notre part, nous n'avons pas encore recu le reglement "
            "de la facture <strong>{numero}</strong>, emise il y a {jours} jours."
        ),
        "conclusion": (
            "Peut-etre s'agit-il d'un oubli. Nous vous remercions par avance de "
            "proceder au reglement."
        ),
        "mention_legale": "",
    },
    2: {
        "ton": "ferme",
        "objet": "2e rappel",
        "intro": (
            "Malgre notre precedent rappel, nous n'avons toujours pas recu le "
            "reglement de la facture <strong>{numero}</strong>, emise il y a "
            "{jours} jours."
        ),
        "conclusion": (
            "Nous vous remercions de regulariser sous les meilleurs delais."
        ),
        "mention_legale": "",
    },
    3: {
        "ton": "mise_en_demeure",
        "objet": "Mise en demeure",
        "intro": (
            "La facture <strong>{numero}</strong>, emise il y a {jours} jours, "
            "demeure impayee malgre nos rappels."
        ),
        "conclusion": (
            "A defaut de reglement sous 8 jours, des penalites de retard seront "
            "appliquees au taux de 3 fois le taux d'interet legal en vigueur, "
            "ainsi qu'une indemnite forfaitaire de 40 EUR pour frais de "
            "recouvrement (art. L441-10 du Code de commerce)."
        ),
        "mention_legale": (
            "La presente vaut mise en demeure amiable avant toute procedure de "
            "recouvrement."
        ),
    },
}


def envoyer_relance_facture_email(
    client_email: str,
    client_nom: str,
    artisan_nom: str,
    facture_numero: str,
    montant_ttc: float,
    jours_depuis_emission: int,
    palier: int,
    lien_paiement: str = "",
    artisan_email: str = "",
    artisan_telephone: str = "",
):
    """
    Envoie une relance facture impayee.

    palier ∈ {1, 2, 3} :
      - 1 : J+30, ton cordial
      - 2 : J+45, ton ferme
      - 3 : J+60, mise en demeure amiable (art. L441-10)
    """
    if palier not in _RELANCE_FACTURE_PALIERS:
        raise ValueError(f"Palier invalide: {palier}")

    cfg = _RELANCE_FACTURE_PALIERS[palier]
    _init_resend()

    montant_str = f"{montant_ttc:.2f} EUR TTC".replace(".", ",")
    intro = cfg["intro"].format(numero=facture_numero, jours=jours_depuis_emission)
    mention = (
        f'<p style="font-size:13px;color:#999;font-style:italic">{cfg["mention_legale"]}</p>'
        if cfg["mention_legale"] else ""
    )
    bouton_paiement = (
        f"""<p style="margin:24px 0">
        <a href="{lien_paiement}"
           style="background:#2563eb;color:#fff;padding:12px 28px;
                  text-decoration:none;border-radius:6px;font-weight:bold">
            Regler en ligne
        </a>
    </p>"""
        if lien_paiement else
        '<p>Merci de nous contacter pour proceder au reglement.</p>'
    )

    sujet = f"{cfg['objet']} — Facture {facture_numero} ({artisan_nom})"
    signature = _signature_html(artisan_nom, artisan_email, artisan_telephone)

    try:
        result = _send(
            {
                "from": _from_with_artisan(artisan_nom),
                "to": client_email,
                "subject": sujet,
                "html": f"""
<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px">
    <h2 style="color:#2563eb">Bonjour {client_nom},</h2>
    <p>{intro}</p>
    <p><strong>Montant du :</strong> {montant_str}</p>
    {bouton_paiement}
    <p>{cfg['conclusion']}</p>
    {mention}
    {signature}
    <hr style="border:none;border-top:1px solid #eee;margin:24px 0">
    <p style="font-size:12px;color:#999">Envoye via MyArtipro</p>
</div>
                """,
            },
            reply_to=artisan_email,
        )
        print(
            f"[Email] Relance facture P{palier} {facture_numero} "
            f"envoyee a {client_email} — ID: {result}"
        )
        return result
    except Exception as e:
        print(
            f"[Email] ERREUR relance facture P{palier} {facture_numero} "
            f"a {client_email}: {e}"
        )
        raise Exception(f"Echec envoi relance facture: {str(e)}")

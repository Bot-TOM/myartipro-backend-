import base64
from fpdf import FPDF
import os
import tempfile
import httpx

FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "fonts")


class DevisPDF(FPDF):
    """PDF professionnel pour devis ou facture artisan."""

    def __init__(self, artisan: dict, doc_type: str = "devis"):
        super().__init__()
        self.artisan = artisan
        self.doc_type = doc_type  # "devis" ou "facture"
        self.set_auto_page_break(auto=True, margin=30)

    def header(self):
        # Logo si disponible
        logo_url = self.artisan.get("logo_url")
        if logo_url:
            try:
                resp = httpx.get(logo_url, timeout=5)
                if resp.status_code == 200:
                    ext = "png"
                    if "jpeg" in resp.headers.get("content-type", "") or "jpg" in logo_url.lower():
                        ext = "jpg"
                    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}")
                    tmp.write(resp.content)
                    tmp.close()
                    self.image(tmp.name, x=10, y=8, h=18)
                    os.unlink(tmp.name)
                    self.set_xy(40, 8)
            except Exception:
                pass  # Si le logo échoue, on continue sans

        # Nom entreprise
        self.set_font("Helvetica", "B", 20)
        self.set_text_color(37, 99, 235)  # primary-600
        nom = self.artisan.get("entreprise") or f"{self.artisan.get('prenom', '')} {self.artisan.get('nom', '')}"
        self.cell(0, 10, _safe(nom), new_x="LMARGIN", new_y="NEXT")

        # Coordonnées artisan
        self.set_font("Helvetica", "", 8)
        self.set_text_color(100, 100, 100)
        infos = []
        adresse = (self.artisan.get("adresse") or "").strip()
        telephone = (self.artisan.get("telephone") or "").strip()
        email = (self.artisan.get("email") or "").strip()
        siret = (self.artisan.get("siret") or "").strip()
        if adresse:
            infos.append(adresse)
        if telephone:
            infos.append(telephone)
        if email:
            infos.append(email)
        if siret:
            infos.append(f"SIRET : {siret}")
        numero_tva = (self.artisan.get("numero_tva") or "").strip()
        if numero_tva:
            infos.append(f"N° TVA : {numero_tva}")
        if infos:
            self.cell(0, 4, _safe(" | ".join(infos)), new_x="LMARGIN", new_y="NEXT")
        self.ln(5)

    def footer(self):
        self.set_y(-18)
        self.set_font("Helvetica", "", 7)
        self.set_text_color(150, 150, 150)
        nom = self.artisan.get("entreprise") or f"{self.artisan.get('prenom', '')} {self.artisan.get('nom', '')}"
        siret = f" - SIRET {self.artisan['siret']}" if self.artisan.get("siret") else ""
        self.cell(0, 4, _safe(f"{nom}{siret}"), align="C", new_x="LMARGIN", new_y="NEXT")

        # Mention TVA franchise uniquement si l'artisan n'est pas au régime réel
        if self.artisan.get("regime_tva", "franchise") != "reel":
            self.cell(
                0, 4,
                _safe("TVA non applicable, art. 293 B du CGI"),
                align="C",
                new_x="LMARGIN", new_y="NEXT",
            )

        # Mention conformité loi anti-fraude TVA (obligatoire pour logiciels de facturation)
        if self.doc_type == "facture":
            self.set_font("Helvetica", "", 6)
            self.set_text_color(180, 180, 180)
            self.cell(
                0, 3,
                _safe("Logiciel MyArtipro - conforme art. 286 I-3 bis CGI (loi anti-fraude TVA 2018) - myartipro.fr/conformite"),
                align="C",
            )


def _safe(text: str) -> str:
    """Remplace les caractères spéciaux pour compatibilité latin-1 (Helvetica)."""
    if not text:
        return ""
    replacements = {
        # Guillemets et ponctuations spéciales
        "\u2019": "'", "\u2018": "'", "\u201c": '"', "\u201d": '"',
        "\u2013": "-", "\u2014": "-", "\u2026": "...", "\u20ac": "EUR",
        "\u00ab": '"', "\u00bb": '"',
        # Ligatures
        "\u0153": "oe", "\u0152": "OE",  # œ Œ
        "\u00e6": "ae", "\u00c6": "AE",  # æ Æ
        # Voyelles accentuées minuscules
        "\u00e9": "e", "\u00e8": "e", "\u00ea": "e", "\u00eb": "e",
        "\u00e0": "a", "\u00e2": "a", "\u00e4": "a",
        "\u00f4": "o", "\u00f6": "o",
        "\u00fb": "u", "\u00fc": "u", "\u00f9": "u",
        "\u00ee": "i", "\u00ef": "i",
        "\u00e7": "c",
        "\u00f1": "n",
        "\u00ff": "y",
        # Voyelles accentuées majuscules
        "\u00c9": "E", "\u00c8": "E", "\u00ca": "E", "\u00cb": "E",
        "\u00c0": "A", "\u00c2": "A", "\u00c4": "A",
        "\u00d4": "O", "\u00d6": "O",
        "\u00db": "U", "\u00dc": "U", "\u00d9": "U",
        "\u00ce": "I", "\u00cf": "I",
        "\u00c7": "C",
        "\u00d1": "N",
        # Symboles
        "\u00b0": "°", "\u00b2": "2", "\u00b3": "3",
        "\u2032": "'", "\u2033": '"',
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    # Supprimer tout caractère restant hors latin-1
    return text.encode("latin-1", errors="replace").decode("latin-1")


def generer_pdf_devis(devis: dict, client: dict, artisan: dict) -> bytes:
    """Genere un PDF professionnel du devis."""
    pdf = DevisPDF(artisan, doc_type="devis")
    pdf.add_page()

    # === TITRE DEVIS ===
    pdf.set_font("Helvetica", "B", 24)
    pdf.set_text_color(37, 99, 235)
    pdf.cell(100, 12, "DEVIS", new_x="RIGHT")

    # Numero devis
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 12, _safe(devis.get("numero", "")), align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    # === BLOC CLIENT ===
    pdf.set_fill_color(248, 250, 252)
    pdf.set_draw_color(226, 232, 240)
    x = pdf.get_x()
    y = pdf.get_y()
    pdf.rect(x, y, 190, 28, style="DF")

    pdf.set_xy(x + 4, y + 3)
    pdf.set_font("Helvetica", "", 7)
    pdf.set_text_color(148, 163, 184)
    pdf.cell(0, 4, "CLIENT", new_x="LMARGIN", new_y="NEXT")

    pdf.set_x(x + 4)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(30, 30, 30)
    client_nom = f"{client.get('prenom', '')} {client.get('nom', '')}".strip()
    pdf.cell(0, 5, _safe(client_nom), new_x="LMARGIN", new_y="NEXT")

    pdf.set_x(x + 4)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(80, 80, 80)
    client_infos = [v.strip() for v in [
        client.get("adresse") or "",
        client.get("telephone") or "",
        client.get("email") or "",
    ] if (v or "").strip()]
    if client_infos:
        pdf.cell(0, 4, _safe(" | ".join(client_infos)), new_x="LMARGIN", new_y="NEXT")

    pdf.set_y(y + 32)

    # === META (objet, date, validite) ===
    pdf.set_font("Helvetica", "", 7)
    pdf.set_text_color(148, 163, 184)
    pdf.cell(80, 4, "OBJET", new_x="RIGHT")
    pdf.cell(50, 4, "DATE", new_x="RIGHT")
    if devis.get("date_validite"):
        pdf.cell(0, 4, "VALIDE JUSQU'AU", new_x="LMARGIN", new_y="NEXT")
    else:
        pdf.cell(0, 4, "", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(30, 30, 30)
    pdf.cell(80, 5, _safe(devis.get("titre", "")), new_x="RIGHT")

    date_creation = devis.get("date_creation", "")
    if isinstance(date_creation, str) and len(date_creation) >= 10:
        date_str = date_creation[:10]
    else:
        date_str = str(date_creation)[:10] if date_creation else ""
    pdf.cell(50, 5, _safe(date_str), new_x="RIGHT")

    if devis.get("date_validite"):
        dv = devis["date_validite"]
        dv_str = dv[:10] if isinstance(dv, str) and len(dv) >= 10 else str(dv)[:10]
        pdf.cell(0, 5, _safe(dv_str), new_x="LMARGIN", new_y="NEXT")
    else:
        pdf.cell(0, 5, "", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(8)

    # === TABLEAU PRESTATIONS ===
    col_widths = [90, 20, 40, 40]
    headers = ["Description", "Qte", "Prix unit. HT", "Total HT"]

    # En-tete
    pdf.set_fill_color(37, 99, 235)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 8)
    for i, header in enumerate(headers):
        align = "L" if i == 0 else "R"
        pdf.cell(col_widths[i], 8, header, border=0, fill=True, align=align)
    pdf.ln()

    # Lignes
    pdf.set_text_color(50, 50, 50)
    pdf.set_font("Helvetica", "", 9)
    prestations = devis.get("prestations", [])

    for j, p in enumerate(prestations):
        desc = p.get("description", "")
        qte = p.get("quantite", 1)
        prix = p.get("prix_unitaire", 0)
        total = qte * prix

        # Fond alterné
        if j % 2 == 1:
            pdf.set_fill_color(248, 250, 252)
            fill = True
        else:
            fill = False

        pdf.cell(col_widths[0], 8, _safe(desc), border=0, fill=fill)
        pdf.cell(col_widths[1], 8, str(qte), border=0, fill=fill, align="R")
        pdf.cell(col_widths[2], 8, f"{prix:.2f} EUR", border=0, fill=fill, align="R")
        pdf.cell(col_widths[3], 8, f"{total:.2f} EUR", border=0, fill=fill, align="R")
        pdf.ln()

    # Ligne de separation
    pdf.set_draw_color(37, 99, 235)
    pdf.line(pdf.get_x(), pdf.get_y(), pdf.get_x() + 190, pdf.get_y())
    pdf.ln(5)

    # === TOTAUX ===
    montant_ht = float(devis.get("montant_ht", 0))
    tva_pct = float(devis.get("tva", 20))
    montant_ttc = float(devis.get("montant_ttc", 0))
    montant_tva = montant_ttc - montant_ht

    x_label = 130
    x_value = 170

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(100, 100, 100)
    pdf.set_x(x_label)
    pdf.cell(40, 6, "Total HT", align="L")
    pdf.cell(20, 6, f"{montant_ht:.2f} EUR", align="R", new_x="LMARGIN", new_y="NEXT")

    if tva_pct == 0:
        pdf.set_x(x_label)
        pdf.set_font("Helvetica", "I", 8)
        pdf.set_text_color(180, 120, 0)
        pdf.cell(60, 6, "TVA non applicable — franchise en base (art. 293 B CGI)", align="L", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(100, 100, 100)
    else:
        pdf.set_x(x_label)
        pdf.cell(40, 6, f"TVA ({tva_pct:.0f}%)", align="L")
        pdf.cell(20, 6, f"{montant_tva:.2f} EUR", align="R", new_x="LMARGIN", new_y="NEXT")

    # Ligne
    pdf.set_draw_color(37, 99, 235)
    pdf.line(x_label, pdf.get_y(), x_label + 60, pdf.get_y())
    pdf.ln(2)

    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(37, 99, 235)
    pdf.set_x(x_label)
    pdf.cell(40, 8, "Total TTC", align="L")
    pdf.cell(20, 8, f"{montant_ttc:.2f} EUR", align="R", new_x="LMARGIN", new_y="NEXT")

    # === ACOMPTE ===
    acompte_pct = int(devis.get("acompte_pct", 0))
    if acompte_pct > 0:
        acompte_ttc = montant_ttc * acompte_pct / 100
        solde_ttc = montant_ttc - acompte_ttc

        pdf.ln(2)
        pdf.set_draw_color(200, 200, 200)
        pdf.line(x_label, pdf.get_y(), x_label + 60, pdf.get_y())
        pdf.ln(2)

        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(100, 100, 100)
        pdf.set_x(x_label)
        pdf.cell(40, 6, _safe(f"Acompte a la commande ({acompte_pct}%)"), align="L")
        pdf.cell(20, 6, f"{acompte_ttc:.2f} EUR", align="R", new_x="LMARGIN", new_y="NEXT")

        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(30, 30, 30)
        pdf.set_x(x_label)
        pdf.cell(40, 6, "Solde a la livraison", align="L")
        pdf.cell(20, 6, f"{solde_ttc:.2f} EUR", align="R", new_x="LMARGIN", new_y="NEXT")

    # === NOTES ===
    if devis.get("notes"):
        pdf.ln(8)
        pdf.set_fill_color(255, 251, 235)
        pdf.set_draw_color(253, 230, 138)
        y_notes = pdf.get_y()
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(80, 80, 80)
        pdf.set_x(pdf.get_x())
        pdf.rect(pdf.get_x(), y_notes, 190, 16, style="DF")
        pdf.set_xy(pdf.get_x() + 4, y_notes + 2)
        pdf.cell(0, 5, "Notes / Conditions :", new_x="LMARGIN", new_y="NEXT")
        pdf.set_x(pdf.get_x() + 4)
        pdf.set_font("Helvetica", "", 9)
        pdf.cell(0, 5, _safe(devis["notes"]), new_x="LMARGIN", new_y="NEXT")

    # === MENTIONS DEVIS + ZONE SIGNATURE ===
    pdf.ln(10)
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(100, 100, 100)

    signed_at = devis.get("signed_at")

    if signed_at:
        # --- Signature électronique effectuée ---
        from datetime import datetime as _dt
        try:
            dt = _dt.fromisoformat(signed_at.replace("Z", "+00:00"))
            date_sign_str = dt.strftime("%d/%m/%Y a %H:%M") + " UTC"
        except Exception:
            date_sign_str = signed_at[:16]

        pdf.multi_cell(
            190, 4,
            _safe("Devis valable 30 jours a compter de sa date d'emission. "
                  "Ce devis a ete accepte par signature electronique simple (SES)."),
        )
        pdf.set_x(pdf.l_margin)
        pdf.ln(3)

        y_sign = pdf.get_y()
        pdf.set_draw_color(34, 197, 94)   # green-500
        pdf.set_fill_color(240, 253, 244)  # green-50
        pdf.set_line_width(0.4)

        # Cadre gauche : piste d'audit
        pdf.rect(10, y_sign, 90, 30, style="DF")
        pdf.set_xy(12, y_sign + 3)
        pdf.set_font("Helvetica", "B", 7)
        pdf.set_text_color(21, 128, 61)
        pdf.cell(86, 4, "Signe electroniquement", new_x="LMARGIN", new_y="NEXT")
        pdf.set_x(12)
        pdf.set_font("Helvetica", "", 7)
        pdf.set_text_color(30, 30, 30)
        pdf.cell(86, 4, _safe(f"Le : {date_sign_str}"), new_x="LMARGIN", new_y="NEXT")
        pdf.set_x(12)
        pdf.cell(86, 4, _safe(f"Par : {devis.get('signed_name', '')}"), new_x="LMARGIN", new_y="NEXT")
        pdf.set_x(12)
        pdf.set_font("Helvetica", "", 6)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(86, 4, _safe(f"IP : {devis.get('signed_ip', '')}"), new_x="LMARGIN", new_y="NEXT")

        # Cadre droit : image signature
        pdf.set_draw_color(34, 197, 94)
        pdf.set_fill_color(255, 255, 255)
        pdf.rect(110, y_sign, 90, 30, style="DF")
        raw = devis.get("signature_data", "")
        if raw:
            try:
                if "," in raw:
                    raw = raw.split(",", 1)[1]
                img_bytes = base64.b64decode(raw)
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
                tmp.write(img_bytes)
                tmp.close()
                pdf.image(tmp.name, x=113, y=y_sign + 2, w=84, h=26)
                os.unlink(tmp.name)
            except Exception:
                pass

        pdf.set_line_width(0.2)
        pdf.set_y(y_sign + 34)

        # Ligne légale eIDAS
        pdf.ln(2)
        pdf.set_x(pdf.l_margin)
        pdf.set_font("Helvetica", "", 6)
        pdf.set_text_color(150, 150, 150)
        pdf.multi_cell(
            190, 3,
            _safe(
                f"Signature electronique simple (SES) conforme au reglement eIDAS (UE) n 910/2014, art. 3(10). "
                f"Signataire : {devis.get('signed_name', '')} | "
                f"Ref : {devis.get('numero', '')} | "
                f"IP : {devis.get('signed_ip', '')} | "
                f"Horodatage : {date_sign_str}"
            ),
        )
    else:
        # --- Pas encore signé : zone vierge ---
        # Obligatoire pour travaux > 150 EUR B2C (arrete du 2 mars 1990)
        pdf.multi_cell(
            190, 4,
            _safe("Devis valable 30 jours a compter de sa date d'emission. "
                  "Apres acceptation, merci de retourner ce devis signe avec la mention "
                  '"Bon pour accord" manuscrite.'),
        )
        pdf.set_x(pdf.l_margin)
        pdf.ln(3)

        y_sign = pdf.get_y()
        pdf.set_draw_color(200, 200, 200)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(120, 120, 120)
        pdf.rect(10, y_sign, 90, 22)
        pdf.set_xy(12, y_sign + 2)
        pdf.cell(86, 4, "Date :", new_x="LMARGIN", new_y="NEXT")
        pdf.rect(110, y_sign, 90, 22)
        pdf.set_xy(112, y_sign + 2)
        pdf.cell(86, 4, _safe('Signature du client precedee de "Bon pour accord" :'), new_x="LMARGIN", new_y="NEXT")

    return pdf.output()


def generer_pdf_facture(facture: dict, client: dict, artisan: dict) -> bytes:
    """Genere un PDF professionnel de la facture."""
    pdf = DevisPDF(artisan, doc_type="facture")
    pdf.add_page()

    # === TITRE FACTURE ===
    pdf.set_font("Helvetica", "B", 24)
    pdf.set_text_color(37, 99, 235)
    pdf.cell(100, 12, "FACTURE", new_x="RIGHT")

    # Numero facture
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 12, _safe(facture.get("numero", "")), align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    # === BLOC CLIENT ===
    pdf.set_fill_color(248, 250, 252)
    pdf.set_draw_color(226, 232, 240)
    x = pdf.get_x()
    y = pdf.get_y()
    pdf.rect(x, y, 190, 28, style="DF")

    pdf.set_xy(x + 4, y + 3)
    pdf.set_font("Helvetica", "", 7)
    pdf.set_text_color(148, 163, 184)
    pdf.cell(0, 4, "CLIENT", new_x="LMARGIN", new_y="NEXT")

    pdf.set_x(x + 4)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(30, 30, 30)
    client_nom = f"{client.get('prenom', '')} {client.get('nom', '')}".strip()
    pdf.cell(0, 5, _safe(client_nom), new_x="LMARGIN", new_y="NEXT")

    pdf.set_x(x + 4)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(80, 80, 80)
    client_infos = [v.strip() for v in [
        client.get("adresse") or "",
        client.get("telephone") or "",
        client.get("email") or "",
    ] if (v or "").strip()]
    if client_infos:
        pdf.cell(0, 4, _safe(" | ".join(client_infos)), new_x="LMARGIN", new_y="NEXT")

    pdf.set_y(y + 32)

    # === META (objet, date, echeance) ===
    pdf.set_font("Helvetica", "", 7)
    pdf.set_text_color(148, 163, 184)
    pdf.cell(80, 4, "OBJET", new_x="RIGHT")
    pdf.cell(50, 4, "DATE", new_x="RIGHT")
    if facture.get("date_echeance"):
        pdf.cell(0, 4, "ECHEANCE", new_x="LMARGIN", new_y="NEXT")
    else:
        pdf.cell(0, 4, "", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(30, 30, 30)
    pdf.cell(80, 5, _safe(facture.get("titre", "")), new_x="RIGHT")

    date_creation = facture.get("date_creation", "")
    if isinstance(date_creation, str) and len(date_creation) >= 10:
        date_str = date_creation[:10]
    else:
        date_str = str(date_creation)[:10] if date_creation else ""
    pdf.cell(50, 5, _safe(date_str), new_x="RIGHT")

    if facture.get("date_echeance"):
        de = facture["date_echeance"]
        de_str = de[:10] if isinstance(de, str) and len(de) >= 10 else str(de)[:10]
        pdf.cell(0, 5, _safe(de_str), new_x="LMARGIN", new_y="NEXT")
    else:
        pdf.cell(0, 5, "", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(8)

    # === TABLEAU PRESTATIONS ===
    col_widths = [90, 20, 40, 40]
    headers = ["Description", "Qte", "Prix unit. HT", "Total HT"]

    pdf.set_fill_color(37, 99, 235)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 8)
    for i, header in enumerate(headers):
        align = "L" if i == 0 else "R"
        pdf.cell(col_widths[i], 8, header, border=0, fill=True, align=align)
    pdf.ln()

    pdf.set_text_color(50, 50, 50)
    pdf.set_font("Helvetica", "", 9)
    prestations = facture.get("prestations", [])

    for j, p in enumerate(prestations):
        desc = p.get("description", "")
        qte = p.get("quantite", 1)
        prix = p.get("prix_unitaire", 0)
        total = qte * prix

        if j % 2 == 1:
            pdf.set_fill_color(248, 250, 252)
            fill = True
        else:
            fill = False

        pdf.cell(col_widths[0], 8, _safe(desc), border=0, fill=fill)
        pdf.cell(col_widths[1], 8, str(qte), border=0, fill=fill, align="R")
        pdf.cell(col_widths[2], 8, f"{prix:.2f} EUR", border=0, fill=fill, align="R")
        pdf.cell(col_widths[3], 8, f"{total:.2f} EUR", border=0, fill=fill, align="R")
        pdf.ln()

    pdf.set_draw_color(37, 99, 235)
    pdf.line(pdf.get_x(), pdf.get_y(), pdf.get_x() + 190, pdf.get_y())
    pdf.ln(5)

    # === TOTAUX ===
    montant_ht  = float(facture.get("montant_ht", 0))
    tva_pct     = float(facture.get("tva", 20))
    montant_ttc = float(facture.get("montant_ttc", 0))
    montant_tva = montant_ttc - montant_ht
    acompte_pct = int(facture.get("acompte_pct") or 0)

    x_label = 130

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(100, 100, 100)
    pdf.set_x(x_label)
    pdf.cell(40, 6, "Total HT", align="L")
    pdf.cell(20, 6, f"{montant_ht:.2f} EUR", align="R", new_x="LMARGIN", new_y="NEXT")

    if tva_pct == 0:
        pdf.set_x(x_label)
        pdf.set_font("Helvetica", "I", 8)
        pdf.set_text_color(180, 120, 0)
        pdf.cell(60, 6, "TVA non applicable — franchise en base (art. 293 B CGI)", align="L", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(100, 100, 100)
    else:
        pdf.set_x(x_label)
        pdf.cell(40, 6, f"TVA ({tva_pct:.0f}%)", align="L")
        pdf.cell(20, 6, f"{montant_tva:.2f} EUR", align="R", new_x="LMARGIN", new_y="NEXT")

    pdf.set_draw_color(37, 99, 235)
    pdf.line(x_label, pdf.get_y(), x_label + 60, pdf.get_y())
    pdf.ln(2)

    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(37, 99, 235)
    pdf.set_x(x_label)
    label_total = "Total HT" if tva_pct == 0 else "Total TTC"
    pdf.cell(40, 8, label_total, align="L")
    pdf.cell(20, 8, f"{montant_ttc:.2f} EUR", align="R", new_x="LMARGIN", new_y="NEXT")

    # === ACOMPTE / NET A PAYER ===
    if acompte_pct > 0:
        acompte_ttc = montant_ttc * acompte_pct / 100
        net_a_payer = montant_ttc - acompte_ttc

        pdf.ln(2)
        pdf.set_draw_color(200, 200, 200)
        pdf.line(x_label, pdf.get_y(), x_label + 60, pdf.get_y())
        pdf.ln(2)

        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(100, 100, 100)
        pdf.set_x(x_label)
        pdf.cell(40, 6, _safe(f"Acompte verse ({acompte_pct}%)"), align="L")
        pdf.cell(20, 6, f"-{acompte_ttc:.2f} EUR", align="R", new_x="LMARGIN", new_y="NEXT")

        pdf.set_draw_color(37, 99, 235)
        pdf.line(x_label, pdf.get_y(), x_label + 60, pdf.get_y())
        pdf.ln(2)

        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(30, 30, 30)
        pdf.set_x(x_label)
        pdf.cell(40, 8, "Net a payer", align="L")
        pdf.cell(20, 8, f"{net_a_payer:.2f} EUR", align="R", new_x="LMARGIN", new_y="NEXT")

    # === NOTES ===
    if facture.get("notes"):
        pdf.ln(8)
        pdf.set_fill_color(255, 251, 235)
        pdf.set_draw_color(253, 230, 138)
        y_notes = pdf.get_y()
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(80, 80, 80)
        pdf.rect(pdf.get_x(), y_notes, 190, 16, style="DF")
        pdf.set_xy(pdf.get_x() + 4, y_notes + 2)
        pdf.cell(0, 5, "Notes :", new_x="LMARGIN", new_y="NEXT")
        pdf.set_x(pdf.get_x() + 4)
        pdf.set_font("Helvetica", "", 9)
        pdf.cell(0, 5, _safe(facture["notes"]), new_x="LMARGIN", new_y="NEXT")

    # === NOTE ATTESTATION TAUX REDUIT ===
    # Obligatoire pour justifier l'application d'un taux réduit (art. 279-0 bis / 278-0 bis CGI)
    tva_pct_note = float(facture.get("tva", 20))
    if tva_pct_note in (10.0, 5.5):
        pdf.ln(5)
        pdf.set_x(pdf.l_margin)
        pdf.set_font("Helvetica", "I", 7)
        pdf.set_text_color(120, 120, 120)
        if tva_pct_note == 10.0:
            note_taux = _safe(
                "Taux de TVA reduit de 10 % applique sur la base d'une attestation simplifiee "
                "fournie par le client, conformement a l'art. 279-0 bis du CGI "
                "(travaux de renovation portant sur un local a usage d'habitation acheve depuis plus de 2 ans)."
            )
        else:
            note_taux = _safe(
                "Taux de TVA reduit de 5,5 % applique sur la base d'une attestation simplifiee "
                "fournie par le client, conformement a l'art. 278-0 bis du CGI "
                "(travaux d'amelioration de la qualite energetique des logements)."
            )
        pdf.multi_cell(190, 3.5, note_taux)

    # === MENTIONS LEGALES OBLIGATOIRES FACTURE ===
    # Art. L441-10 Code de commerce : penalites + indemnite 40 EUR + escompte
    pdf.ln(6)
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(190, 5, "Conditions de reglement", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 7)
    pdf.set_text_color(100, 100, 100)

    def _bullet(txt: str):
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(190, 3.5, _safe(txt))

    if facture.get("date_echeance"):
        de = facture["date_echeance"]
        de_str = de[:10] if isinstance(de, str) and len(de) >= 10 else str(de)[:10]
        _bullet(f"- Date limite de paiement : {de_str}")
    else:
        _bullet("- Paiement a reception de la facture.")

    _bullet("- En cas de retard de paiement, des penalites de retard seront exigibles "
            "au taux de 3 fois le taux d'interet legal en vigueur (art. L441-10 du Code de commerce), "
            "sans qu'un rappel soit necessaire.")

    _bullet("- Une indemnite forfaitaire de 40 EUR pour frais de recouvrement sera exigible "
            "en cas de retard de paiement (decret 2012-1115 du 2 octobre 2012).")

    _bullet("- Aucun escompte n'est consenti en cas de paiement anticipe.")

    # === TAMPON "FACTURE ACQUITTEE" si payee ===
    if facture.get("statut") == "payée" and facture.get("date_paiement"):
        dp = facture["date_paiement"]
        dp_str = dp[:10] if isinstance(dp, str) and len(dp) >= 10 else str(dp)[:10]
        pdf.ln(6)
        pdf.set_x(pdf.l_margin)
        y_tampon = pdf.get_y()
        pdf.set_draw_color(34, 197, 94)  # green-500
        pdf.set_text_color(34, 197, 94)
        pdf.set_line_width(0.8)
        pdf.rect(60, y_tampon, 90, 12)
        pdf.set_xy(60, y_tampon + 2)
        pdf.cell(90, 8, _safe(f"FACTURE ACQUITTEE LE {dp_str}"), align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.set_line_width(0.2)

    return pdf.output()


_MODE_LABELS = {
    "especes": "Especes",
    "cheque": "Cheque",
    "virement": "Virement",
    "carte": "Carte bancaire",
    "stripe": "Paiement en ligne",
}


def generer_livre_recettes(factures: list, artisan: dict, mois: int, annee: int) -> bytes:
    """
    Livre des recettes conforme CGI art. 50-0 (BIC / micro-entrepreneur).
    Contient uniquement les factures payees, triees par date d'encaissement.
    """
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=25)
    pdf.add_page()

    # === EN-TETE ARTISAN ===
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(37, 99, 235)
    pdf.cell(0, 9, "LIVRE DES RECETTES", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(100, 100, 100)
    nom = artisan.get("entreprise") or f"{artisan.get('prenom', '')} {artisan.get('nom', '')}".strip()
    MOIS_FR = ["", "Janvier", "Fevrier", "Mars", "Avril", "Mai", "Juin",
               "Juillet", "Aout", "Septembre", "Octobre", "Novembre", "Decembre"]
    pdf.cell(0, 5, _safe(f"Periode : {MOIS_FR[mois]} {annee}"), new_x="LMARGIN", new_y="NEXT")

    pdf.ln(3)
    pdf.set_fill_color(248, 250, 252)
    pdf.set_draw_color(226, 232, 240)
    pdf.rect(10, pdf.get_y(), 190, 22, style="DF")
    pdf.set_xy(14, pdf.get_y() + 3)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(30, 30, 30)
    pdf.cell(0, 5, _safe(nom), new_x="LMARGIN", new_y="NEXT")
    pdf.set_x(14)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(80, 80, 80)
    infos = []
    if artisan.get("siret"):
        infos.append(f"SIRET : {artisan['siret']}")
    if artisan.get("adresse"):
        infos.append(artisan["adresse"])
    if artisan.get("email"):
        infos.append(artisan["email"])
    if infos:
        pdf.cell(0, 4, _safe(" | ".join(infos)), new_x="LMARGIN", new_y="NEXT")
    pdf.set_y(pdf.get_y() + 8)

    # === TABLEAU ===
    COL = [28, 28, 40, 44, 30, 22]  # Date | N° Facture | Client | Objet | Mode | TTC
    HEADERS = ["Dt encaissement", "N Facture", "Client", "Objet / prestation", "Mode reglement", "TTC (EUR)"]

    pdf.set_fill_color(37, 99, 235)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 7)
    for i, h in enumerate(HEADERS):
        align = "R" if i == 5 else "L"
        pdf.cell(COL[i], 7, h, border=0, fill=True, align=align)
    pdf.ln()

    total_ttc = 0.0
    row_count = 0

    for f in factures:
        dp = (f.get("date_paiement") or "")[:10]
        client = f.get("clients") or {}
        client_nom = f"{client.get('prenom', '')} {client.get('nom', '')}".strip()
        mode_raw = f.get("mode_paiement") or ""
        mode_label = _MODE_LABELS.get(mode_raw, mode_raw.capitalize() if mode_raw else "-")
        ttc = float(f.get("montant_ttc") or 0)
        total_ttc += ttc

        fill = row_count % 2 == 1
        if fill:
            pdf.set_fill_color(248, 250, 252)
        pdf.set_text_color(50, 50, 50)
        pdf.set_font("Helvetica", "", 8)

        pdf.cell(COL[0], 7, _safe(dp), border=0, fill=fill)
        pdf.cell(COL[1], 7, _safe(f.get("numero", "")), border=0, fill=fill)
        pdf.cell(COL[2], 7, _safe(client_nom[:22]), border=0, fill=fill)
        pdf.cell(COL[3], 7, _safe((f.get("titre") or "")[:28]), border=0, fill=fill)
        pdf.cell(COL[4], 7, _safe(mode_label), border=0, fill=fill)
        pdf.cell(COL[5], 7, f"{ttc:.2f}", border=0, fill=fill, align="R")
        pdf.ln()
        row_count += 1

    # === TOTAL ===
    pdf.set_draw_color(37, 99, 235)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(37, 99, 235)
    label_w = sum(COL[:5])
    pdf.cell(label_w, 7, _safe(f"TOTAL RECETTES — {row_count} facture{'s' if row_count > 1 else ''}"), align="L")
    pdf.cell(COL[5], 7, f"{total_ttc:.2f}", align="R", new_x="LMARGIN", new_y="NEXT")

    # === MENTION LEGALE ===
    pdf.ln(8)
    pdf.set_font("Helvetica", "", 7)
    pdf.set_text_color(150, 150, 150)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(
        190, 3.5,
        _safe(
            "Livre des recettes tenu conformement a l'article 50-0 du Code general des impots (CGI), "
            "applicable aux micro-entreprises relevant du regime des BIC. "
            "Document genere par MyArtipro — myartipro.fr"
        ),
    )

    return pdf.output()

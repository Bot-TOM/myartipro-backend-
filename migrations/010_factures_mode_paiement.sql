-- Mode de règlement : obligatoire dans le livre des recettes (CGI art. 50-0)
-- 'stripe' est auto-renseigné par le webhook Stripe

ALTER TABLE factures
  ADD COLUMN IF NOT EXISTS mode_paiement TEXT
    CHECK (mode_paiement IN ('especes', 'cheque', 'virement', 'carte', 'stripe'));

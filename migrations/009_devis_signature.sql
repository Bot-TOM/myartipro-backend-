-- Signature électronique simple (SES) conforme eIDAS art. 3(10) — règlement UE 910/2014
-- Piste d'audit stockée en base : IP + horodatage + user-agent + dessin = SES juridiquement valide

ALTER TABLE devis
  ADD COLUMN IF NOT EXISTS signature_data     TEXT,         -- PNG base64 dessiné par le client
  ADD COLUMN IF NOT EXISTS signed_at          TIMESTAMPTZ,  -- horodatage UTC de la signature
  ADD COLUMN IF NOT EXISTS signed_ip          TEXT,         -- IP du signataire
  ADD COLUMN IF NOT EXISTS signed_name        TEXT,         -- nom saisi par le signataire
  ADD COLUMN IF NOT EXISTS signed_user_agent  TEXT;         -- navigateur / appareil

-- Migration 004 : ajout colonne regime_tva sur profiles
-- Default 'franchise' : correspond à la situation de 99% des auto-entrepreneurs au démarrage
ALTER TABLE profiles
  ADD COLUMN IF NOT EXISTS regime_tva text DEFAULT 'franchise'
    CHECK (regime_tva IN ('franchise', 'reel'));

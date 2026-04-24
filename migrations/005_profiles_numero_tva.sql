-- Migration 005 : ajout colonne numero_tva sur profiles
ALTER TABLE profiles
  ADD COLUMN IF NOT EXISTS numero_tva text DEFAULT NULL;

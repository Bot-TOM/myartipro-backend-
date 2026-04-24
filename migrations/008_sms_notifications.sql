ALTER TABLE profiles ADD COLUMN IF NOT EXISTS sms_notifications boolean NOT NULL DEFAULT false;

-- Migration for challenge team mode
ALTER TABLE challenges ADD COLUMN IF NOT EXISTS mode VARCHAR NOT NULL DEFAULT 'individual';
ALTER TABLE challenges ADD COLUMN IF NOT EXISTS team_size INTEGER NOT NULL DEFAULT 1;

ALTER TABLE challenges DROP CONSTRAINT IF EXISTS check_challenge_mode;
ALTER TABLE challenges ADD CONSTRAINT check_challenge_mode CHECK (mode IN ('individual', 'team'));

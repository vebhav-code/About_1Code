ALTER TABLE challenge_sessions ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id);

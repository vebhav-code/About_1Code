-- Migration for team sessions and team submissions support

-- Challenge sessions
ALTER TABLE challenge_sessions ADD COLUMN IF NOT EXISTS team_id INTEGER REFERENCES teams(id);
ALTER TABLE challenge_sessions ALTER COLUMN user_id DROP NOT NULL;

ALTER TABLE challenge_sessions DROP CONSTRAINT IF EXISTS check_session_owner;
ALTER TABLE challenge_sessions ADD CONSTRAINT check_session_owner CHECK (
    (user_id IS NOT NULL AND team_id IS NULL) OR (user_id IS NULL AND team_id IS NOT NULL)
);

-- Submissions
ALTER TABLE submissions ADD COLUMN IF NOT EXISTS team_id INTEGER REFERENCES teams(id);
ALTER TABLE submissions ALTER COLUMN user_id DROP NOT NULL;

ALTER TABLE submissions DROP CONSTRAINT IF EXISTS check_submission_owner;
ALTER TABLE submissions ADD CONSTRAINT check_submission_owner CHECK (
    (user_id IS NOT NULL AND team_id IS NULL) OR (user_id IS NULL AND team_id IS NOT NULL)
);

-- Chat messages
ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id);

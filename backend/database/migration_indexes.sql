CREATE INDEX IF NOT EXISTS idx_submissions_user_id ON submissions(user_id);
CREATE INDEX IF NOT EXISTS idx_submissions_challenge_id ON submissions(challenge_id);
CREATE INDEX IF NOT EXISTS idx_submissions_team_id ON submissions(team_id);
CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON challenge_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_team_id ON challenge_sessions(team_id);
CREATE INDEX IF NOT EXISTS idx_sessions_challenge_id ON challenge_sessions(challenge_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_session_id ON chat_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_user_id ON chat_messages(user_id);

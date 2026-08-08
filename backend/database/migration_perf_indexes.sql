-- Migration: Add missing database performance indexes for query optimization
CREATE INDEX IF NOT EXISTS idx_submissions_user_id ON submissions(user_id);
CREATE INDEX IF NOT EXISTS idx_submissions_team_id ON submissions(team_id);
CREATE INDEX IF NOT EXISTS idx_submissions_challenge_id ON submissions(challenge_id);

CREATE INDEX IF NOT EXISTS idx_team_members_team_id ON team_members(team_id);
CREATE INDEX IF NOT EXISTS idx_team_members_user_id ON team_members(user_id);
CREATE INDEX IF NOT EXISTS idx_team_members_team_user ON team_members(team_id, user_id);

CREATE INDEX IF NOT EXISTS idx_challenge_sessions_challenge_id ON challenge_sessions(challenge_id);
CREATE INDEX IF NOT EXISTS idx_challenge_sessions_user_id ON challenge_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_challenge_sessions_team_id ON challenge_sessions(team_id);

CREATE INDEX IF NOT EXISTS idx_chat_messages_session_id ON chat_messages(session_id);

CREATE INDEX IF NOT EXISTS idx_challenges_folder_name ON challenges(folder_name);
CREATE INDEX IF NOT EXISTS idx_challenges_is_active ON challenges(is_active);

CREATE INDEX IF NOT EXISTS idx_evaluations_submission_id ON evaluations(submission_id);

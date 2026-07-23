-- Create challenge_sessions table
CREATE TABLE IF NOT EXISTS challenge_sessions (
    id SERIAL PRIMARY KEY,
    challenge_id INTEGER NOT NULL REFERENCES challenges(id),
    name TEXT NOT NULL,
    current_code TEXT NOT NULL DEFAULT '',
    started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    submitted_at TIMESTAMP WITH TIME ZONE
);

-- Create chat_messages table
CREATE TABLE IF NOT EXISTS chat_messages (
    id SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL REFERENCES challenge_sessions(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Make file-path columns on submissions nullable (no longer needed for session-based flow)
ALTER TABLE submissions ALTER COLUMN fixed_project_path DROP NOT NULL;
ALTER TABLE submissions ALTER COLUMN debug_log_path DROP NOT NULL;

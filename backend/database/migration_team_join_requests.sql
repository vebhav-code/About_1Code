CREATE TABLE IF NOT EXISTS team_join_requests (
    id SERIAL PRIMARY KEY,
    team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    invited_user_id INTEGER NOT NULL REFERENCES users(id),
    invited_by_user_id INTEGER NOT NULL REFERENCES users(id),
    status VARCHAR NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT now()
);

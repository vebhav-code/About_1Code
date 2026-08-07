-- Create teams table
CREATE TABLE IF NOT EXISTS teams (
    id SERIAL PRIMARY KEY,
    challenge_id INTEGER NOT NULL REFERENCES challenges(id),
    name VARCHAR NOT NULL,
    invite_code VARCHAR UNIQUE NOT NULL,
    leader_user_id INTEGER NOT NULL REFERENCES users(id),
    status VARCHAR NOT NULL DEFAULT 'forming',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT check_team_status CHECK (status IN ('forming', 'active', 'submitted'))
);

-- Create team_members table
CREATE TABLE IF NOT EXISTS team_members (
    id SERIAL PRIMARY KEY,
    team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id),
    joined_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(team_id, user_id)
);

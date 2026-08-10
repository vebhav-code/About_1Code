-- Migration: Add multi-file support for challenges and submissions
-- Add run_command column to challenges table if it doesn't exist
ALTER TABLE challenges ADD COLUMN IF NOT EXISTS run_command VARCHAR(255) DEFAULT 'pytest';

-- Create challenge_files table
CREATE TABLE IF NOT EXISTS challenge_files (
    id SERIAL PRIMARY KEY,
    challenge_id INTEGER NOT NULL REFERENCES challenges(id) ON DELETE CASCADE,
    filename VARCHAR(255) NOT NULL,
    file_order INTEGER NOT NULL DEFAULT 0,
    starter_content TEXT NOT NULL DEFAULT '',
    solution_content TEXT NOT NULL DEFAULT '',
    language VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_challenge_filename UNIQUE (challenge_id, filename)
);

CREATE INDEX IF NOT EXISTS idx_challenge_files_challenge_filename ON challenge_files(challenge_id, filename);

-- Create submission_files table
CREATE TABLE IF NOT EXISTS submission_files (
    id SERIAL PRIMARY KEY,
    submission_id INTEGER NOT NULL REFERENCES submissions(id) ON DELETE CASCADE,
    filename VARCHAR(255) NOT NULL,
    content TEXT NOT NULL DEFAULT '',
    CONSTRAINT uq_submission_filename UNIQUE (submission_id, filename)
);

CREATE INDEX IF NOT EXISTS idx_submission_files_submission_filename ON submission_files(submission_id, filename);

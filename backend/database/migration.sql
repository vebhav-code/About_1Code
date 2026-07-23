-- Database Migration
-- Create evaluations table for PostgreSQL

CREATE TABLE IF NOT EXISTS evaluations (
    id SERIAL PRIMARY KEY,
    submission_id INTEGER NOT NULL REFERENCES submissions(id) ON DELETE CASCADE,
    hypothesis INTEGER NOT NULL,
    prompt_quality INTEGER NOT NULL,
    ai_collaboration INTEGER NOT NULL,
    code_correctness INTEGER NOT NULL,
    problem_solving INTEGER NOT NULL,
    total_score INTEGER NOT NULL,
    strengths JSONB NOT NULL,
    improvements JSONB NOT NULL,
    overall_feedback TEXT NOT NULL,
    evaluated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

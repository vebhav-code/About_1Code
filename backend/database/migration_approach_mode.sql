-- Migration for Approach Mode Pivot

-- 1. Challenges table
ALTER TABLE challenges ADD COLUMN IF NOT EXISTS constraints TEXT DEFAULT '[]';
ALTER TABLE challenges DROP COLUMN IF EXISTS run_command;

-- 2. Challenge Sessions table
ALTER TABLE challenge_sessions RENAME COLUMN current_code TO current_approach;

-- 3. Submissions table
ALTER TABLE submissions RENAME COLUMN problem_understanding_score TO topic_knowledge_score;
ALTER TABLE submissions RENAME COLUMN ai_collaboration_score TO open_source_usage_score;
ALTER TABLE submissions RENAME COLUMN code_correctness_score TO optimization_score;
ALTER TABLE submissions ADD COLUMN IF NOT EXISTS approach_text TEXT DEFAULT '';

-- 4. Evaluations table
ALTER TABLE evaluations RENAME COLUMN problem_solving TO topic_knowledge;
ALTER TABLE evaluations RENAME COLUMN ai_collaboration TO open_source_usage;
ALTER TABLE evaluations RENAME COLUMN code_correctness TO optimization;

-- Database Migration
-- Add user_id column to submissions table in PostgreSQL

ALTER TABLE submissions 
ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id) ON DELETE SET NULL;

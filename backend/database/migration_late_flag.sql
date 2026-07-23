-- Add late flag column to submissions table
ALTER TABLE submissions ADD COLUMN IF NOT EXISTS late BOOLEAN NOT NULL DEFAULT FALSE;
